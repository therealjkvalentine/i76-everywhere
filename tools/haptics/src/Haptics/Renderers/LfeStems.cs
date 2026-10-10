using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using Haptics.Core;
using Haptics.Effects;

namespace Haptics.Renderers
{
    // =====================================================================================================
    // Lfe.Stems: the HD sound pack's per-sound LFE stems (tools/soundhd, pack-v1\lfe\*.wav, 25-90 Hz, 16 kHz mono)
    // played to the shaker, keyed by the i76tel v3 SOUND_START / SOUND_STOP events (docs/SOUND-HD-PACK.md section 4).
    // A third shaker source beside Lfe.Synth (synthesised from the bus) and Lfe.Loopback (the game-audio bed): it is
    // summed into Lfe.Synth BEFORE its HP/LP and limiter, with per-source gains from the rig's lfe.sources, so the rig
    // chooses synth only, stems only, or both. With no stems on disk the host falls back to Lfe.Synth alone.
    // =====================================================================================================

    /// <summary>A bed that wants the core step (events) before the synth renders that step's samples.</summary>
    public interface ILfeStepBed
    {
        void OnStep(CoreStep step);
    }

    /// <summary>Several beds summed (loopback + stems). Duck is forwarded; the stems bed ignores it (stems are the transients).</summary>
    public sealed class LfeBedMix : ILfeBed, ILfeStepBed
    {
        readonly ILfeBed[] _beds;
        public LfeBedMix(params ILfeBed[] beds) { _beds = beds.Where(b => b != null).ToArray(); }
        public double Next() { double s = 0; foreach (var b in _beds) s += b.Next(); return s; }
        public void SetDuck(double f) { foreach (var b in _beds) b.SetDuck(f); }
        public void OnStep(CoreStep step) { foreach (var b in _beds) (b as ILfeStepBed)?.OnStep(step); }
    }

    /// <summary>Per-source shaker gains: rig outputs.lfe.sources {synth, stems}, overridable by I76_LFE_SOURCES="synth=0,stems=1".</summary>
    public static class LfeSources
    {
        public const string EnvVar = "I76_LFE_SOURCES";
        public static (double synth, double stems, string from) Read(RigDef rig)
        {
            double synth = 1.0, stems = 1.0; string from = "default";
            if (rig?.Output("lfe")?["sources"] is JsonObject so)
            {
                synth = EffectDef.Num(so, "synth", 1.0); stems = EffectDef.Num(so, "stems", 1.0); from = "rig";
            }
            var env = Environment.GetEnvironmentVariable(EnvVar);
            if (!string.IsNullOrWhiteSpace(env))
            {
                foreach (var part in env.Split(new[] { ',', ';' }, StringSplitOptions.RemoveEmptyEntries))
                {
                    var kv = part.Split('=');
                    if (kv.Length != 2 || !double.TryParse(kv[1].Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out var g)) continue;
                    if (kv[0].Trim().Equals("synth", StringComparison.OrdinalIgnoreCase)) synth = g;
                    if (kv[0].Trim().Equals("stems", StringComparison.OrdinalIgnoreCase)) stems = g;
                }
                from = EnvVar;
            }
            return (synth, stems, from);
        }
    }

    /// <summary>One LFE stem: samples (-1..1), its rate, loop flag, category, and the stock playback rate it was authored for.</summary>
    public sealed class Stem
    {
        public string Name, File, Category;
        public float[] Samples;
        public int Rate;
        public bool Loop;
        public double Gain = 1.0;          // the manifest's suggested_gain
        public double NominalHz;           // stock sample rate (Hz in SOUND_START is relative to this); 0 = unknown
    }

    /// <summary>
    /// lfe-manifest.json (tools/soundhd `lfe` stage): sounds{stem: {file, rate, loop, category, suggested_gain, aliases}},
    /// by_alias{name: stem}. The stock rate per stem comes from the sibling pack manifest.json (sounds[].original.rate),
    /// or a per-stem "nominal_hz", else the rig's default_nominal_hz.
    /// </summary>
    public sealed class StemManifest
    {
        public string Path, Version;
        public readonly Dictionary<string, Stem> Stems = new Dictionary<string, Stem>(StringComparer.OrdinalIgnoreCase);
        public readonly Dictionary<string, string> Alias = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public readonly List<string> Missing = new List<string>();   // listed in the manifest, no file on disk

        public static StemManifest Load(string path, double defaultNominalHz = 11025)
        {
            var opts = new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true };
            var j = JsonNode.Parse(System.IO.File.ReadAllText(path), null, opts) as JsonObject;
            var m = new StemManifest { Path = path, Version = EffectDef.Str(j, "pack_version") };
            string dir = System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(path));
            var nominal = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
            var packManifest = System.IO.Path.Combine(System.IO.Path.GetDirectoryName(dir) ?? dir, "manifest.json");
            if (System.IO.File.Exists(packManifest))
            {
                try
                {
                    var pm = JsonNode.Parse(System.IO.File.ReadAllText(packManifest), null, opts) as JsonObject;
                    if (pm?["sounds"] is JsonObject ps)
                        foreach (var kv in ps) { var r = EffectDef.Num(kv.Value?["original"] as JsonObject, "rate", 0); if (r > 0) nominal[kv.Key] = r; }
                    else if (pm?["sounds"] is JsonArray pa)
                        foreach (var n in pa) { var nm = EffectDef.Str(n as JsonObject, "name"); var r = EffectDef.Num(n?["original"] as JsonObject, "rate", 0); if (nm != null && r > 0) nominal[nm] = r; }
                }
                catch { /* nominal rates are optional */ }
            }
            if (j?["sounds"] is JsonObject s)
                foreach (var kv in s)
                {
                    var o = kv.Value as JsonObject; if (o == null) continue;
                    var file = System.IO.Path.Combine(dir, EffectDef.Str(o, "file") ?? kv.Key + ".wav");
                    if (!System.IO.File.Exists(file)) { m.Missing.Add(kv.Key); continue; }
                    var (rate, x) = Wav.Read(file);
                    var st = new Stem
                    {
                        Name = kv.Key, File = file, Rate = rate, Samples = x.Select(v => (float)v).ToArray(),
                        Loop = o["loop"] is JsonValue lv && lv.TryGetValue<bool>(out var lb) && lb,
                        Category = EffectDef.Str(o, "category") ?? "", Gain = EffectDef.Num(o, "suggested_gain", 1.0),
                    };
                    st.NominalHz = EffectDef.Num(o, "nominal_hz", nominal.TryGetValue(kv.Key, out var nh) ? nh : defaultNominalHz);
                    m.Stems[kv.Key] = st;
                    m.Alias[kv.Key] = kv.Key;
                    if (o["aliases"] is JsonArray al) foreach (var a in al) { var an = a?.GetValue<string>(); if (an != null) m.Alias[an] = kv.Key; }
                }
            if (j?["by_alias"] is JsonObject ba)
                foreach (var kv in ba) { var t = kv.Value?.GetValue<string>(); if (t != null && m.Stems.ContainsKey(t)) m.Alias[kv.Key] = t; }
            return m;
        }

        /// <summary>SOUND_START name (lowercase or not, with or without extension) -> stem, or null.</summary>
        public Stem Resolve(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            var n = name.Trim().ToLowerInvariant();
            if (Alias.TryGetValue(n, out var k) || Alias.TryGetValue(n + ".gpw", out k) || Alias.TryGetValue(n + ".wav", out k)) return Stems[k];
            int dot = n.LastIndexOf('.');
            if (dot > 0 && Alias.TryGetValue(n.Substring(0, dot), out k)) return Stems[k];
            return null;
        }
    }

    /// <summary>The rig's outputs.stems block (schema: rig.schema.json "stems").</summary>
    public sealed class StemsConfig
    {
        public string Manifest = "../soundhd/out/pack-v1/lfe/lfe-manifest.json";
        public double Gain = 1.0;                       // stems master gain (before the stems limiter)
        public int MaxVoices = 6;
        public string Curve = "inverse";                // inverse | inverse_square | linear | none
        public double RefM = 10, MaxM = 150, Rolloff = 1.0, NearM = 30;
        public double MinGain = 0.002;                  // voices quieter than this after attenuation are not started
        public string[] RateScale = { "engine_loop" };  // categories whose playback rate follows the event Hz
        public double RateMin = 0.25, RateMax = 4.0;
        public double DefaultNominalHz = 11025;
        public double FadeMs = 15;                      // release fade on SOUND_STOP / voice steal
        public double LoopMaxS = 0;                     // 0 = a loop lives until its SOUND_STOP
        public double Knee = 0.7, Ceiling = 0.95;       // the stems' own soft limiter (tanh above the knee, never above the ceiling)
        public double VolMax = 1.5;                     // clamp on vol% / 100
        public readonly Dictionary<string, double> CategoryGain = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);

        public static StemsConfig From(JsonObject o)
        {
            var c = new StemsConfig();
            if (o == null) return c;
            c.Manifest = EffectDef.Str(o, "manifest") ?? c.Manifest;
            c.Gain = EffectDef.Num(o, "gain", c.Gain);
            c.MaxVoices = (int)EffectDef.Num(o, "max_voices", c.MaxVoices);
            c.NearM = EffectDef.Num(o, "near_m", c.NearM);
            c.MinGain = EffectDef.Num(o, "min_gain", c.MinGain);
            c.FadeMs = EffectDef.Num(o, "fade_ms", c.FadeMs);
            c.LoopMaxS = EffectDef.Num(o, "loop_max_s", c.LoopMaxS);
            c.DefaultNominalHz = EffectDef.Num(o, "default_nominal_hz", c.DefaultNominalHz);
            c.VolMax = EffectDef.Num(o, "vol_max", c.VolMax);
            if (o["distance"] is JsonObject d)
            {
                c.Curve = EffectDef.Str(d, "curve") ?? c.Curve;
                c.RefM = EffectDef.Num(d, "ref_m", c.RefM); c.MaxM = EffectDef.Num(d, "max_m", c.MaxM); c.Rolloff = EffectDef.Num(d, "rolloff", c.Rolloff);
            }
            if (o["rate_scale"] is JsonObject rs)
            {
                if (rs["categories"] is JsonArray ca) c.RateScale = ca.Select(x => x.GetValue<string>()).ToArray();
                c.RateMin = EffectDef.Num(rs, "min", c.RateMin); c.RateMax = EffectDef.Num(rs, "max", c.RateMax);
            }
            if (o["limiter"] is JsonObject li) { c.Knee = EffectDef.Num(li, "knee", c.Knee); c.Ceiling = EffectDef.Num(li, "ceiling", c.Ceiling); }
            if (o["category_gain"] is JsonObject cg) foreach (var kv in cg) if (kv.Value is JsonValue v && v.TryGetValue<double>(out var g)) c.CategoryGain[kv.Key] = g;
            return c;
        }

        /// <summary>Distance attenuation, 1 at or inside ref_m, non-increasing with distance, 0 beyond max_m.</summary>
        public double Attenuation(double d)
        {
            if (Curve == "none") return 1.0;
            if (d > MaxM) return 0.0;
            if (d <= RefM) return 1.0;
            switch (Curve)
            {
                case "linear": return Math.Max(0.0, 1.0 - (d - RefM) / Math.Max(1e-9, MaxM - RefM));
                case "inverse_square": { double r = RefM / d; return r * r; }
                default: return RefM / (RefM + Rolloff * (d - RefM));   // "inverse" (DirectSound's 3D rolloff law)
            }
        }
    }

    /// <summary>
    /// The stem voice bank: SOUND_START starts a voice (looped for modes 1 and 2 until the SOUND_STOP with the same voice
    /// address), gain = vol% x distance attenuation (player's own sounds and 2D sounds full) x suggested/category gains,
    /// playback rate = event Hz / stock rate for the rate-scaled categories (engine loops), a voice budget with priority
    /// player &gt; nearby &gt; far, and a soft limiter. Events are queued by OnStep and applied at the next sample, so in
    /// file mode a voice starts on the first sample of the core update that carried its event. Thread-safe for one
    /// producer (the pipeline) and one consumer (the synth's live audio thread).
    /// </summary>
    public sealed class StemBank : ILfeBed, ILfeStepBed
    {
        sealed class V
        {
            public string Key, Name; public Stem Stem; public double Pos, Step, Gain, Fade = 1, FadeStep; public bool Loop, Releasing;
            public int Class; public long StartSample, MaxSamples;
        }
        struct Job { public bool Start; public string Key, Name; public double Hz, Vol, Dist; public int Mode; public bool Player, HasPos, Present; }

        public readonly StemManifest Manifest;
        public readonly StemsConfig Cfg;
        readonly int _rate;
        readonly List<V> _voices = new List<V>();
        readonly ConcurrentQueue<Job> _q = new ConcurrentQueue<Job>();
        public double MixGain = 1.0;           // lfe.sources.stems, applied to what the synth receives (not to Recorded)
        public List<short> Recorded;           // the stems signal after its limiter (file mode)
        public long Samples, Started, Missed, Dropped, Stolen, Inaudible, Stopped, UnmatchedStops, Limited, TimedOut;
        public int MaxActive, MaxSounding;
        public double PeakAbs;
        public readonly SortedDictionary<string, int> MissedNames = new SortedDictionary<string, int>(StringComparer.Ordinal);
        public readonly List<(long sample, string name, double gain, double step, bool loop)> StartLog = new List<(long, string, double, double, bool)>();

        public StemBank(StemManifest m, StemsConfig cfg, int rate) { Manifest = m; Cfg = cfg; _rate = rate; }

        public int ActiveCount { get { lock (_voices) return _voices.Count(v => !v.Releasing); } }
        public int SoundingCount { get { lock (_voices) return _voices.Count; } }
        public (string name, int cls, double gain)[] ActiveVoices { get { lock (_voices) return _voices.Where(v => !v.Releasing).Select(v => (v.Name, v.Class, v.Gain)).ToArray(); } }

        public void SetDuck(double f) { }   // stems are not ducked under transients: they are the transients

        public void OnStep(CoreStep step)
        {
            if (step.Events == null) return;
            bool present = step.State?.Present ?? true;
            foreach (var e in step.Events)
            {
                if (e.Type != "SOUND_START" && e.Type != "SOUND_STOP") continue;
                double voice = e["voice"];
                string key = voice != 0 ? "v:" + voice.ToString("0", CultureInfo.InvariantCulture) : "n:" + (e.Name ?? "").ToLowerInvariant() + ":" + e["obj"].ToString("0", CultureInfo.InvariantCulture);
                _q.Enqueue(new Job
                {
                    Start = e.Type == "SOUND_START", Key = key, Name = e.Name, Hz = e["hz"], Vol = e.F.ContainsKey("vol") ? e["vol"] : 100,
                    Dist = e["dist"], Mode = (int)e["mode"], Player = e["is_player"] != 0, HasPos = e["has_pos"] != 0, Present = present,
                });
            }
        }

        /// <summary>The gain a SOUND_START would get (before the limiter), and its priority class (3 player, 2 near / 2D, 1 far).</summary>
        public (double gain, int cls) GainFor(Stem st, double vol, bool player, bool hasPos, double dist, bool present)
        {
            double att; int cls;
            if (player) { att = 1; cls = 3; }
            else if (!hasPos) { att = 1; cls = 2; }
            else if (!present) { att = 0; cls = 1; }
            else { att = Cfg.Attenuation(dist); cls = dist <= Cfg.NearM ? 2 : 1; }
            double cg = st != null && Cfg.CategoryGain.TryGetValue(st.Category ?? "", out var g) ? g : 1.0;
            double v = Math.Max(0, Math.Min(Cfg.VolMax, vol / 100.0));
            return (v * att * cg * (st?.Gain ?? 1.0) * Cfg.Gain, cls);
        }

        void Apply(Job j)
        {
            if (!j.Start)
            {
                var v = _voices.FirstOrDefault(x => x.Key == j.Key && !x.Releasing);
                if (v == null) { UnmatchedStops++; return; }
                Release(v); Stopped++;
                return;
            }
            var st = Manifest.Resolve(j.Name);
            if (st == null)
            {
                Missed++; var nm = (j.Name ?? "").ToLowerInvariant();
                MissedNames[nm] = MissedNames.TryGetValue(nm, out var c) ? c + 1 : 1;
                return;
            }
            foreach (var old in _voices.Where(x => x.Key == j.Key && !x.Releasing).ToList()) Release(old);   // the game reused the voice
            var (gain, cls) = GainFor(st, j.Vol, j.Player, j.HasPos, j.Dist, j.Present);
            if (gain < Cfg.MinGain) { Inaudible++; return; }
            var active = _voices.Where(x => !x.Releasing).ToList();
            if (active.Count >= Math.Max(1, Cfg.MaxVoices))
            {
                var weakest = active.OrderBy(x => x.Class).ThenBy(x => x.Gain).ThenBy(x => x.StartSample).First();
                if (cls > weakest.Class || (cls == weakest.Class && gain > weakest.Gain)) { Release(weakest); Stolen++; }
                else { Dropped++; return; }
            }
            double ratio = 1.0;
            if (j.Hz > 0 && st.NominalHz > 0 && Cfg.RateScale.Any(c => string.Equals(c, st.Category, StringComparison.OrdinalIgnoreCase)))
                ratio = Math.Max(Cfg.RateMin, Math.Min(Cfg.RateMax, j.Hz / st.NominalHz));
            var nv = new V
            {
                Key = j.Key, Name = st.Name, Stem = st, Gain = gain, Class = cls, Loop = j.Mode == 1 || j.Mode == 2,
                Step = (double)st.Rate / _rate * ratio, StartSample = Samples,
                MaxSamples = Cfg.LoopMaxS > 0 ? (long)(Cfg.LoopMaxS * _rate) : long.MaxValue,
            };
            _voices.Add(nv); Started++;
            if (StartLog.Count < 100000) StartLog.Add((Samples, st.Name, gain, nv.Step, nv.Loop));
        }

        void Release(V v)
        {
            if (v.Releasing) return;
            v.Releasing = true;
            int n = Math.Max(1, (int)(Cfg.FadeMs * 0.001 * _rate));
            v.FadeStep = 1.0 / n;
        }

        /// <summary>The next stems sample at the shaker rate, after the stems limiter (x MixGain).</summary>
        public double Next()
        {
            double y = 0;
            lock (_voices)
            {
                while (_q.TryDequeue(out var j)) Apply(j);
                int active = 0;
                for (int i = _voices.Count - 1; i >= 0; i--)
                {
                    var v = _voices[i];
                    var x = v.Stem.Samples; int n = x.Length;
                    if (n == 0) { _voices.RemoveAt(i); continue; }
                    if (v.Pos >= n)
                    {
                        if (v.Loop) v.Pos %= n;
                        else { _voices.RemoveAt(i); continue; }
                    }
                    int i0 = (int)v.Pos; double fr = v.Pos - i0;
                    double a = x[i0], s;
                    if (fr == 0) s = a;
                    else
                    {
                        int i1 = i0 + 1;
                        double b = i1 < n ? x[i1] : v.Loop ? x[0] : 0.0;
                        s = a + (b - a) * fr;
                    }
                    y += s * v.Gain * v.Fade;
                    v.Pos += v.Step;
                    if (!v.Releasing) active++;
                    if (v.Releasing) { v.Fade -= v.FadeStep; if (v.Fade <= 0) { _voices.RemoveAt(i); continue; } }
                    else if (Samples - v.StartSample >= v.MaxSamples) { Release(v); TimedOut++; }
                }
                if (active > MaxActive) MaxActive = active;
                if (_voices.Count > MaxSounding) MaxSounding = _voices.Count;
                Samples++;
            }
            y = Limit(y);
            if (Recorded != null) Recorded.Add((short)Math.Round(y * 32767));
            return y * MixGain;
        }

        double Limit(double v)
        {
            double a = Math.Abs(v);
            if (a > PeakAbs) PeakAbs = a;
            double k = Cfg.Knee, c = Math.Max(Cfg.Ceiling, k + 1e-6);
            if (a <= k) return v;
            Limited++;
            double room = c - k;
            return (v < 0 ? -1.0 : 1.0) * (k + room * Math.Tanh((a - k) / room));
        }
    }

    /// <summary>
    /// Lfe.Stems renderer. Attached (the normal case): Session hands its StemBank to Lfe.Synth as a bed, so the stems go
    /// through the synth's HP/LP/limiter and out of the same WAV / waveOut device; this renderer then only writes
    /// &lt;tag&gt;.stems.wav (the stems signal alone, for the design view). Standalone (no lfe sink): it renders the stems
    /// itself at the rig's lfe rate into &lt;tag&gt;.stems.wav. No device of its own. Missing manifest or stems: logs once,
    /// stays silent, and the shaker is Lfe.Synth alone.
    /// </summary>
    public sealed class LfeStemsRenderer : IRenderer
    {
        public string Type => "Lfe.Stems";
        public StemBank Bank;
        public bool Attached;
        public string WavPath, Fallback, ManifestPath;
        RendererContext _ctx;
        int _rate, _perUpdate;
        (double synth, double stems, string from) _src = (1, 1, "default");

        public static string ResolveManifest(string p)
        {
            if (string.IsNullOrEmpty(p)) return null;
            return Path.IsPathRooted(p) ? p : Path.GetFullPath(Path.Combine(EffectSet.DefaultRoot(), p));
        }

        public void Open(RendererContext ctx)
        {
            _ctx = ctx;
            _rate = (int)ctx.Rig.Num("lfe", "rate", 16000);
            _perUpdate = _rate / Math.Max(1, ctx.CoreHz);
            _src = LfeSources.Read(ctx.Rig);
            var cfg = StemsConfig.From(ctx.Config);
            ManifestPath = ResolveManifest(cfg.Manifest);
            WavPath = Path.Combine(ctx.OutDir ?? ".", ctx.Tag + ".stems.wav");
            try
            {
                if (ManifestPath == null || !File.Exists(ManifestPath)) { Fallback = "no stem manifest at " + (ManifestPath ?? "(none)"); }
                else
                {
                    var m = StemManifest.Load(ManifestPath, cfg.DefaultNominalHz);
                    if (m.Stems.Count == 0) Fallback = "manifest " + ManifestPath + " lists " + m.Missing.Count + " stems, none on disk (build them: tools\\soundhd\\soundhd.py build)";
                    else
                    {
                        Bank = new StemBank(m, cfg, _rate);
                        if (!ctx.Live && ctx.OutDir != null) Bank.Recorded = new List<short>();
                        if (m.Missing.Count > 0) ctx.Log.WriteLine("Lfe.Stems: " + m.Missing.Count + " stems listed but not on disk (" + string.Join(", ", m.Missing.Take(8)) + (m.Missing.Count > 8 ? ", ..." : "") + ")");
                    }
                }
            }
            catch (Exception ex) { Fallback = "manifest " + ManifestPath + " unreadable: " + ex.Message; Bank = null; }
            if (Fallback != null) ctx.Log.WriteLine("Lfe.Stems: " + Fallback + " - shaker falls back to Lfe.Synth only");
        }

        public void Render(CoreStep step)
        {
            if (Bank == null || Attached) return;          // attached: Lfe.Synth forwards the step and pulls the samples
            Bank.OnStep(step);
            for (int k = 0; k < _perUpdate; k++) Bank.Next();
        }

        public void Close()
        {
            if (Bank?.Recorded != null && _ctx?.OutDir != null) Wav.Write(WavPath, Bank.Recorded.ToArray(), _rate);
        }

        public string Summary()
        {
            if (Bank == null) return "Lfe.Stems: off (" + Fallback + "); shaker = Lfe.Synth only";
            var b = Bank;
            string missed = b.MissedNames.Count == 0 ? "" : " [" + string.Join(" ", b.MissedNames.Take(10).Select(kv => kv.Key + "x" + kv.Value)) + (b.MissedNames.Count > 10 ? " ..." : "") + "]";
            return string.Format(CultureInfo.InvariantCulture,
                "Lfe.Stems: {0} stems ({1}); started {2}, no stem {3}{4}, budget dropped {5} / stole {6} (max {7} active of {8}), inaudible {9}, stopped {10}, unmatched stops {11}; peak {12:0.00}, limited {13:0.00}%; sources synth {14:0.##} stems {15:0.##} ({16}); {17} -> {18}",
                b.Manifest.Stems.Count, Path.GetFileName(ManifestPath), b.Started, b.Missed, missed, b.Dropped, b.Stolen, b.MaxActive, b.Cfg.MaxVoices, b.Inaudible,
                b.Stopped, b.UnmatchedStops, b.PeakAbs, 100.0 * b.Limited / Math.Max(1, b.Samples), _src.synth, _src.stems, _src.from,
                Attached ? "mixed into Lfe.Synth" : "standalone", b.Recorded != null ? WavPath : "no file");
        }

        public void Dispose() { }

        /// <summary>
        /// Session wiring: when an lfe sink is open and the rig's stems output is enabled with lfe.sources.stems &gt; 0, open
        /// Lfe.Stems even if no "stems" sink was named; then hand Lfe.Synth one bed = loopback + stems.
        /// </summary>
        public static void Wire(Pipeline p, RigDef rig, LfeSynthRenderer synth, LfeLoopbackRenderer loop, LfeStemsRenderer stems, Func<RendererContext> ctxForStems)
        {
            var src = LfeSources.Read(rig);
            if (stems == null && synth != null && rig.Output("stems") != null && rig.OutputEnabled("stems") && src.stems > 0)
            {
                stems = new LfeStemsRenderer();
                stems.Open(ctxForStems());
                p.Renderers.Add(stems);
            }
            ILfeBed bed = loop?.Bed;
            if (stems?.Bank != null && synth != null)
            {
                stems.Attached = true;
                stems.Bank.MixGain = src.stems;
                bed = bed == null ? (ILfeBed)stems.Bank : new LfeBedMix(bed, stems.Bank);
            }
            if (synth != null) synth.Bed = bed;
        }
    }
}
