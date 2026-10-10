using System;
using System.Collections.Generic;
using Haptics.Core;

namespace Haptics.Transport
{
    public sealed class TelDatagram
    {
        public TelFrame Frame;
        public List<TelEvent> Events = new List<TelEvent>();
        public I76TelLayout Layout;
        public string Warning;
    }

    /// <summary>
    /// Datagram-shaped bytes (one frame + the events appended after it, exactly what the proxy sends over UDP and
    /// what ShmReader splices together) to and from TelFrame / TelEvent. Tolerant by design:
    ///  * v2 frames always decode with the frozen v2 layout;
    ///  * a frame whose version matches the live header decodes with the live header (v3 when it lands);
    ///  * a v3 frame decodes with the frozen v3 layout (frame 664 B, event 56 B) when the live header is not v3;
    ///  * events are sized from the datagram (36 = v2, 56 = v3) rather than from a constant, and a frame shorter
    ///    than its layout decodes the fields that fit (v2 offsets never moved).
    /// </summary>
    public sealed class TelCodec
    {
        public readonly I76TelLayout Live;
        public TelCodec(I76TelLayout live = null) { Live = live; }

        public static TelCodec Default() => new TelCodec(I76TelLayout.TryLoadLive());

        public I76TelLayout LayoutFor(int version)
        {
            if (version == 2) return I76TelLayout.V2;
            if (Live != null && Live.Version == version) return Live;
            if (version == 3) return I76TelLayout.V3;
            if (version > 3) return I76TelLayout.V3;       // newer than known: every version so far only appends, so v3 offsets hold
            return null;
        }

        public TelDatagram Decode(byte[] d, int len = -1)
        {
            if (len < 0) len = d.Length;
            if (len < 8) return null;
            uint magic = BitConverter.ToUInt32(d, 0);
            if (magic != I76TelLayout.V2.Magic) return null;
            int version = BitConverter.ToUInt16(d, 4);
            int size = BitConverter.ToUInt16(d, 6);
            var L = LayoutFor(version);
            if (L == null) return new TelDatagram { Warning = "unsupported i76tel version " + version };
            if (size < 16 || size > len) size = Math.Min(len, L.Frame.Size);
            var fr = new TelFrame { Version = version, Size = size };
            foreach (var f in L.Frame.Fields)
            {
                if (f.Offset + f.Size > size) continue;
                if (f.Type == "char" && f.Count > 1)
                {
                    if (f.Name == "weapon_name") { fr.WeaponName = new byte[8]; Array.Copy(d, f.Offset, fr.WeaponName, 0, Math.Min(8, f.Count)); }
                    continue;
                }
                fr.V[f.Name] = Read(d, f.Offset, f.Type);
            }
            var dg = new TelDatagram { Frame = fr, Layout = L };
            if (L.Frame.Size != size)
                dg.Warning = "frame size " + size + " differs from the " + L.Source + " layout (" + L.Frame.Size + "); fields past " + size + " left unset";
            int count = (int)fr.EventCount;
            if (count > 0 && len > size)
            {
                int esz = (len - size) % count == 0 ? (len - size) / count : L.Event.Size;
                TelStruct es = esz == L.Event.Size ? L.Event
                             : esz == I76TelLayout.V2.Event.Size ? I76TelLayout.V2.Event
                             : esz == I76TelLayout.V3.Event.Size ? I76TelLayout.V3.Event : L.Event;
                for (int k = 0; k < count && size + (k + 1) * esz <= len; k++)
                    dg.Events.Add(DecodeEvent(d, size + k * esz, es));
            }
            return dg;
        }

        public static TelEvent DecodeEvent(byte[] d, int off, TelStruct es)
        {
            var e = new TelEvent
            {
                Seq = BitConverter.ToUInt32(d, off), Frame = BitConverter.ToUInt32(d, off + 4), Type = BitConverter.ToUInt32(d, off + 8)
            };
            for (int k = 0; k < e.F.Length; k++) { var f = es["f_" + k]; if (f != null) e.F[k] = BitConverter.ToSingle(d, off + f.Offset); }
            for (int k = 0; k < e.I.Length; k++) { var f = es["i_" + k]; if (f != null) e.I[k] = BitConverter.ToInt32(d, off + f.Offset); }
            return e;
        }

        static double Read(byte[] d, int o, string type)
        {
            switch (type)
            {
                case "uint8_t": case "char": return d[o];
                case "int8_t": return (sbyte)d[o];
                case "uint16_t": return BitConverter.ToUInt16(d, o);
                case "int16_t": return BitConverter.ToInt16(d, o);
                case "uint32_t": return BitConverter.ToUInt32(d, o);
                case "int32_t": return BitConverter.ToInt32(d, o);
                case "uint64_t": return BitConverter.ToUInt64(d, o);
                case "int64_t": return BitConverter.ToInt64(d, o);
                case "float": return BitConverter.ToSingle(d, o);
                case "double": return BitConverter.ToDouble(d, o);
            }
            return 0;
        }

        static void Write(byte[] d, int o, string type, double v)
        {
            byte[] b;
            switch (type)
            {
                case "uint8_t": case "char": case "int8_t": d[o] = (byte)(int)v; return;
                case "uint16_t": b = BitConverter.GetBytes((ushort)v); break;
                case "int16_t": b = BitConverter.GetBytes((short)v); break;
                case "uint32_t": b = BitConverter.GetBytes((uint)(long)v); break;
                case "int32_t": b = BitConverter.GetBytes((int)v); break;
                case "uint64_t": b = BitConverter.GetBytes((ulong)v); break;
                case "int64_t": b = BitConverter.GetBytes((long)v); break;
                case "float": b = BitConverter.GetBytes((float)v); break;
                case "double": b = BitConverter.GetBytes(v); break;
                default: return;
            }
            Array.Copy(b, 0, d, o, b.Length);
        }

        /// <summary>Encode a frame + events with a layout (synthetic sessions and tests). magic/version/size/event_count are set here.</summary>
        public static byte[] Encode(TelFrame fr, IList<TelEvent> evs, I76TelLayout L, int frameSize = -1)
        {
            int size = frameSize > 0 ? frameSize : L.Frame.Size;
            int esz = L.Event.Size;
            var d = new byte[size + (evs?.Count ?? 0) * esz];
            fr.V["magic"] = L.Magic; fr.V["version"] = L.Version; fr.V["size"] = size;
            fr.V["event_count"] = evs?.Count ?? 0;
            foreach (var f in L.Frame.Fields)
            {
                if (f.Offset + f.Size > size) continue;
                if (f.Type == "char" && f.Count > 1) { if (f.Name == "weapon_name") Array.Copy(fr.WeaponName, 0, d, f.Offset, Math.Min(8, f.Count)); continue; }
                if (fr.V.TryGetValue(f.Name, out var v)) Write(d, f.Offset, f.Type, v);
            }
            if (evs != null)
                for (int k = 0; k < evs.Count; k++)
                {
                    int o = size + k * esz; var e = evs[k];
                    Write(d, o, "uint32_t", e.Seq); Write(d, o + 4, "uint32_t", e.Frame); Write(d, o + 8, "uint32_t", e.Type);
                    for (int j = 0; j < e.F.Length; j++) { var f = L.Event["f_" + j]; if (f != null) Write(d, o + f.Offset, "float", e.F[j]); }
                    for (int j = 0; j < e.I.Length; j++) { var f = L.Event["i_" + j]; if (f != null) Write(d, o + f.Offset, "int32_t", e.I[j]); }
                }
            return d;
        }
    }
}
