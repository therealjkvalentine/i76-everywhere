using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;

namespace Haptics.Transport
{
    /// <summary>One flattened scalar of a struct: "speed", "pos_1", "wheel3_grip", "f_2"; char arrays stay whole.</summary>
    public sealed class TelField
    {
        public string Name, Type; public int Offset, Size, Count = 1;
        public override string ToString() => Name + "@" + Offset + ":" + Type;
    }

    public sealed class TelStruct
    {
        public string Name; public int Size;
        public readonly List<TelField> Fields = new List<TelField>();
        public readonly Dictionary<string, TelField> ByName = new Dictionary<string, TelField>(StringComparer.Ordinal);
        public TelField this[string n] => ByName.TryGetValue(n, out var f) ? f : null;
    }

    /// <summary>
    /// i76tel.h parsed at run time, the same contract tools/telemetry/i76tel.py uses ("one field per line,
    /// `type name;` or `type name[N];`"), with i76tel.py's flattened names. Two layouts are kept:
    ///  * the FROZEN v2 header embedded in this assembly (Transport/i76tel.v2.h), used for every version-2 frame;
    ///  * the LIVE header tools/telemetry/i76tel.h, used for frames whose version matches it (v3 once the proxy
    ///    agent lands it). A v3 frame with no v3 header falls back to <see cref="AssumedV3"/>.
    /// </summary>
    public sealed class I76TelLayout
    {
        public int Version, Ring, Port; public uint Magic; public string ShmName;
        public readonly Dictionary<string, long> Consts = new Dictionary<string, long>();
        public readonly Dictionary<string, TelStruct> Structs = new Dictionary<string, TelStruct>();
        public TelStruct Frame => Structs["i76tel_frame_t"];
        public TelStruct Event => Structs["i76tel_event_t"];
        public string Source;

        static readonly Dictionary<string, int> Scalar = new Dictionary<string, int>
        {
            ["uint8_t"] = 1, ["int8_t"] = 1, ["char"] = 1, ["uint16_t"] = 2, ["int16_t"] = 2, ["uint32_t"] = 4, ["int32_t"] = 4,
            ["uint64_t"] = 8, ["int64_t"] = 8, ["float"] = 4, ["double"] = 8,
        };

        public static I76TelLayout Parse(string text, string source)
        {
            var L = new I76TelLayout { Source = source };
            foreach (Match m in Regex.Matches(text, "^#define\\s+(\\w+)\\s+(\"[^\"]*\"|0x[0-9a-fA-F]+u?|\\d+)", RegexOptions.Multiline))
            {
                var v = m.Groups[2].Value;
                if (v.StartsWith("\"")) { if (m.Groups[1].Value == "I76TEL_SHM_NAME") L.ShmName = v.Trim('"').Replace("\\\\", "\\"); continue; }
                v = v.TrimEnd('u');
                L.Consts[m.Groups[1].Value] = v.StartsWith("0x") ? Convert.ToInt64(v.Substring(2), 16) : long.Parse(v, CultureInfo.InvariantCulture);
            }
            L.Version = (int)L.Consts.GetValueOrDefault("I76TEL_VERSION", 0);
            L.Ring = (int)L.Consts.GetValueOrDefault("I76TEL_RING", 64);
            L.Port = (int)L.Consts.GetValueOrDefault("I76TEL_PORT", 7676);
            L.Magic = (uint)L.Consts.GetValueOrDefault("I76TEL_MAGIC", 0x54363749);
            var raw = new Dictionary<string, List<(string type, string name, int count)>>();
            var order = new List<string>();
            foreach (Match m in Regex.Matches(text, "typedef struct (\\w+) \\{(.*?)\\} \\1;", RegexOptions.Singleline))
            {
                var fields = new List<(string, string, int)>();
                foreach (var line in m.Groups[2].Value.Split('\n'))
                {
                    var f = Regex.Match(line, "^\\s*(\\w+)\\s+(\\w+)(?:\\[(\\w+)\\])?\\s*;");
                    if (!f.Success) continue;
                    int count = 1;
                    if (f.Groups[3].Success)
                    {
                        var c = f.Groups[3].Value;
                        count = int.TryParse(c, out var ci) ? ci : (int)L.Consts[c];
                    }
                    fields.Add((f.Groups[1].Value, f.Groups[2].Value, count));
                }
                raw[m.Groups[1].Value] = fields;
                order.Add(m.Groups[1].Value);
            }
            foreach (var sn in order)
            {
                var st = new TelStruct { Name = sn };
                int off = 0;
                Flatten(L, raw, sn, "", ref off, st);
                st.Size = off;
                L.Structs[sn] = st;
            }
            return L;
        }

        static int SizeOf(I76TelLayout L, Dictionary<string, List<(string type, string name, int count)>> raw, string type)
        {
            if (Scalar.TryGetValue(type, out var s)) return s;
            int sz = 0; foreach (var f in raw[type]) sz += SizeOf(L, raw, f.type) * f.count; return sz;
        }

        static void Flatten(I76TelLayout L, Dictionary<string, List<(string type, string name, int count)>> raw, string sname, string prefix, ref int off, TelStruct st)
        {
            foreach (var (type, name, count) in raw[sname])
            {
                if (Scalar.TryGetValue(type, out var size))
                {
                    if (type == "char" && count > 1) { Add(st, prefix + name, type, off, count, count); off += count; }
                    else if (count == 1) { Add(st, prefix + name, type, off, size, 1); off += size; }
                    else for (int k = 0; k < count; k++) { Add(st, prefix + name + "_" + k, type, off, size, 1); off += size; }
                }
                else
                {
                    for (int k = 0; k < count; k++)
                        Flatten(L, raw, type, count > 1 ? prefix + name + k + "_" : prefix + name + "_", ref off, st);
                }
            }
        }

        static void Add(TelStruct st, string name, string type, int off, int size, int count)
        {
            var f = new TelField { Name = name, Type = type, Offset = off, Size = size, Count = count };
            st.Fields.Add(f); st.ByName[name] = f;
        }

        // ---- the layouts --------------------------------------------------------------------------------
        static I76TelLayout _v2;
        public static I76TelLayout V2
        {
            get
            {
                if (_v2 != null) return _v2;
                using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("i76tel.v2.h"))
                using (var r = new StreamReader(s)) _v2 = Parse(r.ReadToEnd(), "embedded i76tel.v2.h");
                return _v2;
            }
        }

        /// <summary>
        /// What a v3 frame is assumed to look like when no v3 header is available: the design (HAPTICS-ARCHITECTURE 4.1)
        /// fixes the EVENT (48 bytes: seq, frame, type, f[5], i[4]) but not where the two new frame fields go. So every
        /// v2 field is read at its v2 offset (all of them precede the additions if they are appended), event_seq /
        /// event_count are taken from the last 8 bytes of the frame (frame.size), and wheelbase / grip_cap stay unknown.
        /// </summary>
        static I76TelLayout _v3;
        /// <summary>
        /// The v3 layout as the proxy agent landed it (branch worktree-agent-a2d1aee61832dc0d1, commit 80e1667):
        /// frame 664 B (v2's 628 + fields appended after event_count, v2 offsets unchanged), event 56 B (f[6], i[5]).
        /// Embedded frozen like v2, so v3 frames decode even when tools/telemetry/i76tel.h is older or newer.
        /// </summary>
        public static I76TelLayout V3
        {
            get
            {
                if (_v3 != null) return _v3;
                using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("i76tel.v3.h"))
                using (var r = new StreamReader(s)) _v3 = Parse(r.ReadToEnd(), "embedded i76tel.v3.h");
                return _v3;
            }
        }
        /// <summary>Kept for callers written against the design doc; = <see cref="V3"/>.</summary>
        public static I76TelLayout AssumedV3 => V3;

        /// <summary>
        /// Set on a layout used for a version newer than any known one: v2/v3 offsets are read where they fit and
        /// event_seq / event_count still come from their v2 offsets (every version so far appends after them).
        /// </summary>
        public bool AssumedTail;

        public static I76TelLayout TryLoadLive(string path = null)
        {
            try
            {
                path = path ?? FindLiveHeader();
                if (path == null || !File.Exists(path)) return null;
                return Parse(File.ReadAllText(path), path);
            }
            catch { return null; }
        }

        public static string FindLiveHeader()
        {
            var env = Environment.GetEnvironmentVariable("I76TEL_HEADER");
            if (!string.IsNullOrEmpty(env)) return env;
            var d = new DirectoryInfo(AppContext.BaseDirectory);
            while (d != null)
            {
                var p = Path.Combine(d.FullName, "tools", "telemetry", "i76tel.h");
                if (File.Exists(p)) return p;
                d = d.Parent;
            }
            return null;
        }

    }
}
