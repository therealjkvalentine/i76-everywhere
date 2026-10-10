using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json.Nodes;
using Haptics.Core;
using Haptics.Effects;
using Haptics.Renderers;
using Haptics.Transport;

namespace Haptics.Tests
{
    /// <summary>
    /// Lfe.Stems (HD sound pack LFE stems as a shaker source). Synthetic SOUND_START / SOUND_STOP sessions (real v3 datagrams)
    /// rendered to WAV and checked. The fixture stems are generated here (tests/out/stems-fixture), so nothing depends on the
    /// gitignored game-derived pack; the last section checks the real pack when it has been built. Event times that must
    /// land on an exact sample are float32-exact (0.25, 0.5, 1.25 s): i76tel sim_time is a float, and an event belongs to the
    /// first 250 Hz core update at or after its frame's float time (0.2 s as a float is 0.200000003, i.e. one update later).
    /// </summary>
    static class StemsTests
    {
        const int Rate = 16000;
        static string _fx;

        static string Fixture()
        {
            if (_fx != null) return _fx;
            var dir = T.TempDir("stems-fixture");
            short[] Gen(double secs, Func<double, double> f) { int n = (int)Math.Round(secs * Rate); var o = new short[n]; for (int i = 0; i < n; i++) o[i] = (short)Math.Round(32767 * f(i / (double)Rate)); return o; }
            Wav.Write(Path.Combine(dir, "tbang.wav"), Gen(0.25, t => 0.5 * Math.Cos(2 * Math.PI * 40 * t) * Math.Exp(-t / 0.1)), Rate);
            Wav.Write(Path.Combine(dir, "tloop.wav"), Gen(0.10, t => 0.3 * Math.Sin(2 * Math.PI * 50 * t)), Rate);
            Wav.Write(Path.Combine(dir, "tengine.wav"), Gen(0.50, t => 0.4 * Math.Sin(2 * Math.PI * 40 * t)), Rate);
            Wav.Write(Path.Combine(dir, "tloud.wav"), Gen(0.25, t => 0.95 * Math.Cos(2 * Math.PI * 45 * t)), Rate);
            JsonObject S(string file, bool loop, string cat) => new JsonObject
            {
                ["file"] = file, ["rate"] = Rate, ["loop"] = loop, ["category"] = cat, ["suggested_gain"] = 1.0, ["nominal_hz"] = 11025,
                ["aliases"] = new JsonArray(Path.GetFileNameWithoutExtension(file), Path.GetFileNameWithoutExtension(file) + ".gpw"),
            };
            var m = new JsonObject
            {
                ["pack_version"] = "test fixture",
                ["sounds"] = new JsonObject
                {
                    ["tbang"] = S("tbang.wav", false, "weapon_fire"), ["tloop"] = S("tloop.wav", true, "weapon_fire"),
                    ["tengine"] = S("tengine.wav", true, "engine_loop"), ["tloud"] = S("tloud.wav", false, "explosion_impact"),
                    ["tgone"] = S("tgone.wav", false, "weapon_fire"),     // listed, never written: a stem missing on disk
                },
                ["by_alias"] = new JsonObject { ["tbang"] = "tbang", ["tbang.gpw"] = "tbang", ["tloop"] = "tloop", ["tengine"] = "tengine", ["tloud"] = "tloud" },
            };
            File.WriteAllText(Path.Combine(dir, "lfe-manifest.json"), m.ToJsonString());
            return _fx = dir;
        }

        sealed class Res
        {
            public short[] Lfe, Stems; public StemBank Bank; public LfeStemsRenderer R; public string Dir; public Pipeline P;
        }

        static Res Go(string tag, IList<SoundCue> cues, double seconds = 2.0, Action<RigDef> rig = null, string[] sinks = null, Action<Pipeline> onP = null, bool present = true)
        {
            var set = EffectSet.Load();
            var st = set.Rig.Output("stems");
            st["manifest"] = Path.Combine(Fixture(), "lfe-manifest.json");
            st["max_voices"] = 6;
            rig?.Invoke(set.Rig);
            var dir = T.TempDir("stems");
            var p = Session.Build(set, sinks ?? new[] { "lfe-wav" }, dir, tag, false, 250, 50, null, TextWriter.Null);
            onP?.Invoke(p);
            var d = new Derive(); p.Core.Configure(d);
            p.Run(Sources.FromDatagrams(SyntheticSound.Session(cues, seconds, 50, present), d, new TelCodec(null)));
            foreach (var r in p.Renderers) r.Close();
            var run = new Res { Dir = dir, P = p };
            run.R = p.Renderers.OfType<LfeStemsRenderer>().FirstOrDefault();
            run.Bank = run.R?.Bank;
            var lfe = Path.Combine(dir, tag + ".lfe.wav"); if (File.Exists(lfe)) run.Lfe = ReadPcm(lfe);
            var sw = Path.Combine(dir, tag + ".stems.wav"); if (run.Bank != null && File.Exists(sw)) run.Stems = ReadPcm(sw);
            return run;
        }

        static short[] ReadPcm(string path) { var (_, x) = Wav.Read(path); return x.Select(v => (short)Math.Round(v * 32768)).ToArray(); }
        static void SetSources(RigDef rig, double synth, double stems) { var l = rig.Output("lfe"); l["sources"] = new JsonObject { ["synth"] = synth, ["stems"] = stems }; }
        static int FirstNonZero(short[] a, int from = 0) { for (int i = from; i < a.Length; i++) if (a[i] != 0) return i; return -1; }
        static int MaxAbs(short[] a, int from, int to) { int m = 0; for (int i = Math.Max(0, from); i < Math.Min(a.Length, to); i++) m = Math.Max(m, Math.Abs((int)a[i])); return m; }
        static double ZeroCrossHz(short[] a, int from, int to)
        {
            int up = 0, first = -1, last = -1;
            for (int i = from + 1; i < to; i++) if (a[i - 1] < 0 && a[i] >= 0) { up++; if (first < 0) first = i; last = i; }
            return up > 1 ? (up - 1) * (double)Rate / (last - first) : 0;
        }

        public static void Run()
        {
            Environment.SetEnvironmentVariable(LfeSources.EnvVar, null);
            var stem = Wav.Read(Path.Combine(Fixture(), "tbang.wav")).samples;

            T.Section("Lfe.Stems: SOUND_START starts the stem on the right sample (fixture stems, standalone stems.wav and mixed lfe.wav)");
            {
                var r = Go("start", new[] { new SoundCue { Name = "tbang", At = 0.5, Player = true, Dist = 0 } }, 1.5);
                T.Check("the rig's stems output is auto-opened with the lfe sink and mixed into Lfe.Synth", r.R != null && r.R.Attached && r.Bank != null, r.R?.Summary() ?? "no renderer");
                int first = FirstNonZero(r.Stems);
                T.Check("first stems sample = 0.5 s x 16 kHz = 8000 (the first sample of the core update that carried the event)", first == 8000, "first nonzero " + first);
                bool exact = Enumerable.Range(0, stem.Length).All(i => r.Stems[8000 + i] == (short)Math.Round(stem[i] * 32767));
                T.Check("the stem is played sample-exact at rate 1 (vol 100, player, gain 1, below the limiter knee)", exact, "");
                T.Check("a one-shot ends at its own length (0.25 s): silence from sample 12000", MaxAbs(r.Stems, 12000, r.Stems.Length) == 0, MaxAbs(r.Stems, 12000, r.Stems.Length).ToString());
                T.Check("Derive passes the voice address (SOUND_START 'voice' field)", r.Bank.StartLog.Count == 1 && r.Bank.Started == 1, string.Join(";", r.Bank.StartLog));

                var s0 = Go("start_synth_only", new[] { new SoundCue { Name = "tbang", At = 0.5, Player = true, Dist = 0 } }, 1.5, rig => SetSources(rig, 1, 0));
                bool sameBefore = Enumerable.Range(0, 8000).All(i => s0.Lfe[i] == r.Lfe[i]);
                bool differAfter = Enumerable.Range(8000, 4000).Any(i => s0.Lfe[i] != r.Lfe[i]);
                T.Check("synth+stems lfe.wav equals synth-only before sample 8000 and differs after it", sameBefore && differAfter, "before same " + sameBefore + ", after differs " + differAfter);
                var so = Go("start_stems_only", new[] { new SoundCue { Name = "tbang", At = 0.5, Player = true, Dist = 0 } }, 1.5, rig => SetSources(rig, 0, 1));
                T.Check("stems only (sources.synth 0): lfe.wav is silent before the event and carries the stem after it",
                    MaxAbs(so.Lfe, 0, 8000) == 0 && MaxAbs(so.Lfe, 8000, 12000) > 3000, string.Format("before {0}, after {1}", MaxAbs(so.Lfe, 0, 8000), MaxAbs(so.Lfe, 8000, 12000)));
                var n0 = Go("synth_no_stems_output", new[] { new SoundCue { Name = "tbang", At = 0.5, Player = true, Dist = 0 } }, 1.5, rig => rig.Output("stems")["enabled"] = false);
                T.Check("synth only (sources.stems 0) is byte-identical to a rig without the stems output", n0.Lfe.SequenceEqual(s0.Lfe) && n0.R == null, "");
                var half = Go("vol50", new[] { new SoundCue { Name = "tbang", At = 0.5, Player = true, Dist = 0, Vol = 50 } }, 1.5);
                T.Check("volume 50 % halves the stem (sample 8000: 8192 vs 16384, +-1 LSB)", Math.Abs(half.Stems[8000] * 2 - r.Stems[8000]) <= 2, half.Stems[8000] + " vs " + r.Stems[8000]);

                Environment.SetEnvironmentVariable(LfeSources.EnvVar, "synth=0,stems=1");
                var env = Go("env_override", new[] { new SoundCue { Name = "tbang", At = 0.5, Player = true, Dist = 0 } }, 1.5);
                Environment.SetEnvironmentVariable(LfeSources.EnvVar, null);
                T.Check("I76_LFE_SOURCES=synth=0,stems=1 overrides the rig for one run (same as the stems-only rig)", env.Lfe.SequenceEqual(so.Lfe), "");
            }

            T.Section("Lfe.Stems: loops (modes 1 and 2) run until the matching SOUND_STOP");
            {
                foreach (int mode in new[] { 1, 2 })
                {
                    var r = Go("loop_m" + mode, new[] { new SoundCue { Name = "tloop", At = 0.2, StopAt = 1.0, Mode = mode, Player = true, Dist = 0 } }, 1.6);
                    int fade = 240;   // 15 ms at 16 kHz
                    T.Check("mode " + mode + ": the 0.1 s loop is still sounding at 0.9 s (looped 7x)", MaxAbs(r.Stems, 14400, 16000) > 9000, MaxAbs(r.Stems, 14400, 16000).ToString());
                    T.Check("mode " + mode + ": silent from STOP (sample 16000) + the 15 ms release fade", MaxAbs(r.Stems, 16000 + fade + 1, r.Stems.Length) == 0, MaxAbs(r.Stems, 16000 + fade + 1, r.Stems.Length).ToString());
                    T.Check("mode " + mode + ": release is a fade, not a cut (first fade sample > last fade sample)", MaxAbs(r.Stems, 16000, 16060) > MaxAbs(r.Stems, 16000 + fade - 60, 16000 + fade), "");
                    T.Check("mode " + mode + ": STOP matched by voice (stopped 1, unmatched 0)", r.Bank.Stopped == 1 && r.Bank.UnmatchedStops == 0, r.R.Summary());
                }
                var two = Go("loop_two", new[] {
                    new SoundCue { Name = "tloop", At = 0.25, StopAt = 0.5, Mode = 1, Player = true, Dist = 0, Voice = 0x7000 },
                    new SoundCue { Name = "tloop", At = 0.25, StopAt = 1.25, Mode = 1, Player = true, Dist = 0, Voice = 0x7040 } }, 1.6);
                T.Check("two loops of the same stem: each STOP ends only its own voice (sounding at 1.0 s, silent after 1.25 s)",
                    MaxAbs(two.Stems, 15500, 16000) > 3000 && MaxAbs(two.Stems, 20000 + 241, two.Stems.Length) == 0 && two.Bank.Stopped == 2, two.R.Summary());
                var un = Go("loop_unmatched", new[] { new SoundCue { Name = "tbang", At = -1, StopAt = 0.4, Player = true, Dist = 0 } }, 0.8);
                T.Check("a SOUND_STOP with no live voice is counted and ignored", un.Bank.UnmatchedStops == 1 && MaxAbs(un.Stems, 0, un.Stems.Length) == 0, un.R.Summary());
                var cap = Go("loop_max", new[] { new SoundCue { Name = "tloop", At = 0.25, Mode = 1, Player = true, Dist = 0 } }, 1.6, rig => rig.Output("stems")["loop_max_s"] = 0.5);
                T.Check("loop_max_s 0.5: a loop whose STOP never comes is released after 0.5 s", cap.Bank.TimedOut == 1 && MaxAbs(cap.Stems, 12000 + 241, cap.Stems.Length) == 0 && MaxAbs(cap.Stems, 11500, 12000) > 3000, cap.R.Summary());
            }

            T.Section("Lfe.Stems: distance attenuation (configurable curve; player's own sounds at full level)");
            {
                var cfg = StemsConfig.From(EffectSet.Load().Rig.Output("stems"));
                foreach (var curve in new[] { "inverse", "inverse_square", "linear", "none" })
                {
                    cfg.Curve = curve; double prev = double.MaxValue; bool mono = true;
                    for (double dd = 0; dd <= 400; dd += 0.5) { double g = cfg.Attenuation(dd); if (g > prev + 1e-12 || g < 0 || g > 1) mono = false; prev = g; }
                    T.Check("curve " + curve + ": 0..1 and non-increasing over 0-400 m", mono, "");
                }
                var dists = new[] { 0.0, 5, 10, 20, 40, 80, 120, 149 };
                var peaks = dists.Select(dd => MaxAbs(Go("dist_" + dd, new[] { new SoundCue { Name = "tbang", At = 0.3, Dist = dd } }, 0.8).Stems, 0, 99999)).ToArray();
                bool nonInc = peaks.Zip(peaks.Skip(1), (a, b) => b <= a).All(x => x);
                bool strict = peaks.Skip(2).Zip(peaks.Skip(3), (a, b) => b < a).All(x => x);
                T.Check("rendered peak is non-increasing with distance, strictly beyond ref_m (10 m)", nonInc && strict, string.Join(" ", dists.Zip(peaks, (dd, pk) => dd + "m:" + pk)));
                T.Check("inside ref_m the level is full (0 m = 5 m = 10 m)", peaks[0] == peaks[1] && peaks[1] == peaks[2], "");
                var far = Go("dist_151", new[] { new SoundCue { Name = "tbang", At = 0.3, Dist = 151 } }, 0.8);
                T.Check("beyond max_m (150 m) the voice is not started (inaudible)", far.Bank.Inaudible == 1 && MaxAbs(far.Stems, 0, 99999) == 0, far.R.Summary());
                var mine = Go("dist_player", new[] { new SoundCue { Name = "tbang", At = 0.3, Dist = 300, Player = true } }, 0.8);
                T.Check("the player's own sound at 300 m plays at full level", MaxAbs(mine.Stems, 0, 99999) == peaks[0], MaxAbs(mine.Stems, 0, 99999) + " vs " + peaks[0]);
                var flat = Go("dist_2d", new[] { new SoundCue { Name = "tbang", At = 0.3, Dist = -1 } }, 0.8);
                T.Check("a 2D sound (no position) plays at full level", MaxAbs(flat.Stems, 0, 99999) == peaks[0], "");
                var nop = Go("dist_nopresent", new[] { new SoundCue { Name = "tbang", At = 0.3, Dist = 20 } }, 0.8, present: false);
                T.Check("no player present: positional AI sounds are not played", nop.Bank.Inaudible == 1, nop.R.Summary());
                var lin = Go("dist_linear", new[] { new SoundCue { Name = "tbang", At = 0.3, Dist = 80 } }, 0.8, rig => ((JsonObject)rig.Output("stems")["distance"])["curve"] = "linear");
                T.Check("the curve comes from the rig (linear at 80 m: (150-80)/140 = 0.5 of full)", Math.Abs(MaxAbs(lin.Stems, 0, 99999) / (double)peaks[0] - 0.5) < 0.01, MaxAbs(lin.Stems, 0, 99999) + " / " + peaks[0]);
            }

            T.Section("Lfe.Stems: playback rate follows the event Hz for engine loops");
            {
                var idle = Go("rate_idle", new[] { new SoundCue { Name = "tengine", At = 0.2, Mode = 1, Hz = 8268.75, Player = true, Dist = 0 } }, 1.6);
                double fi = ZeroCrossHz(idle.Stems, 4800, 20800);
                T.Check("engine loop at 8268.75 Hz (idle, x0.75 of 11025): the 40 Hz stem plays at 30 Hz", Math.Abs(fi - 30) < 0.3, fi.ToString("0.00") + " Hz");
                var high = Go("rate_high", new[] { new SoundCue { Name = "tengine", At = 0.2, Mode = 1, Hz = 11025 * 1.65, Player = true, Dist = 0 } }, 1.6);
                double fh = ZeroCrossHz(high.Stems, 4800, 20800);
                T.Check("engine loop at 1.65 x 11025 Hz: 66 Hz", Math.Abs(fh - 66) < 0.5, fh.ToString("0.00") + " Hz");
                var wpn = Go("rate_weapon", new[] { new SoundCue { Name = "tbang", At = 0.2, Hz = 22050, Player = true, Dist = 0 } }, 0.8);
                T.Check("a weapon stem is not rate-scaled (not in rate_scale.categories)", wpn.Bank.StartLog.Count == 1 && wpn.Bank.StartLog[0].step == 1.0, "");
            }

            T.Section("Lfe.Stems: voice budget with priority player > nearby > far");
            {
                (string, int, double)[] snap = null;
                var cues = new List<SoundCue>();
                for (int i = 0; i < 3; i++) cues.Add(new SoundCue { Name = "tloop", At = 0.2, StopAt = 1.4, Mode = 1, Dist = 100 + i });
                for (int i = 0; i < 2; i++) cues.Add(new SoundCue { Name = "tloop", At = 0.2, StopAt = 1.4, Mode = 1, Dist = 20 + i });
                cues.Add(new SoundCue { Name = "tloop", At = 0.2, StopAt = 1.4, Mode = 1, Player = true, Dist = 0 });
                cues.Add(new SoundCue { Name = "tloop", At = 0.8, StopAt = 1.4, Mode = 1, Dist = 90 });     // a late far voice
                var r = Go("budget", cues, 1.6, rig => rig.Output("stems")["max_voices"] = 3, null,
                           p => p.OnStep = s => { if (Math.Abs(s.T - 0.6) < 1e-6) snap = p.Renderers.OfType<LfeStemsRenderer>().First().Bank.ActiveVoices; });
                T.Check("never more than max_voices (3) active voices, at any sample", r.Bank.MaxActive <= 3, "max active " + r.Bank.MaxActive);
                var cls = snap?.Select(v => v.Item2).OrderBy(x => x).ToArray();
                T.Check("kept: the player's voice and the two nearby ones (classes 2 2 3); the three far ones were stolen", cls != null && cls.SequenceEqual(new[] { 2, 2, 3 }) && r.Bank.Stolen == 3, cls == null ? "no snapshot" : string.Join(" ", cls) + "; " + r.R.Summary());
                T.Check("a later far voice does not steal a nearby or player voice (dropped 1)", r.Bank.Dropped == 1, r.R.Summary());
            }

            T.Section("Lfe.Stems: gain staging - no clipping with many loud voices");
            {
                var cues = Enumerable.Range(0, 8).Select(i => new SoundCue { Name = "tloud", At = 0.3, Player = true, Dist = 0, Voice = 0x8000 + 0x40 * i }).ToList();
                var r = Go("loud", cues, 1.0, rig => { rig.Output("stems")["gain"] = 3.0; rig.Output("stems")["max_voices"] = 8; });
                int ms = MaxAbs(r.Stems, 0, r.Stems.Length), ml = MaxAbs(r.Lfe, 0, r.Lfe.Length);
                T.Check("8 voices x 0.95 x gain 3 (raw 22.8): stems.wav stays under the 0.95 ceiling", ms <= (int)(0.95 * 32767) + 1 && r.Bank.PeakAbs > 10, string.Format("stems peak {0} (raw {1:0.0})", ms, r.Bank.PeakAbs));
                T.Check("the mixed lfe.wav never reaches full scale (Lfe.Synth's limiter x master)", ml < 32767 * 0.95, "lfe peak " + ml);
            }

            T.Section("Lfe.Stems: deterministic; missing stems fall back to Lfe.Synth only");
            {
                var cues = new[] {
                    new SoundCue { Name = "tbang", At = 0.3, Dist = 25 }, new SoundCue { Name = "tengine", At = 0.1, StopAt = 1.5, Mode = 1, Hz = 9000, Player = true, Dist = 0 },
                    new SoundCue { Name = "tloop", At = 0.7, StopAt = 1.1, Mode = 2, Dist = 60 } };
                var a = Go("det_a", cues, 1.8); var b = Go("det_b", cues, 1.8);
                bool same = File.ReadAllBytes(Path.Combine(a.Dir, "det_a.lfe.wav")).SequenceEqual(File.ReadAllBytes(Path.Combine(b.Dir, "det_b.lfe.wav"))) &&
                            File.ReadAllBytes(Path.Combine(a.Dir, "det_a.stems.wav")).SequenceEqual(File.ReadAllBytes(Path.Combine(b.Dir, "det_b.stems.wav")));
                T.Check("two renders of the same session write byte-identical lfe.wav and stems.wav", same, "");

                var synthOnly = Go("fb_ref", cues, 1.8, rig => SetSources(rig, 1, 0));
                var miss = Go("fb_missing", cues, 1.8, rig => rig.Output("stems")["manifest"] = Path.Combine(Fixture(), "no-such-manifest.json"));
                T.Check("no manifest on disk: renderer reports the fallback and stays silent", miss.R != null && miss.Bank == null && miss.R.Summary().Contains("Lfe.Synth only"), miss.R?.Summary());
                T.Check("no manifest on disk: lfe.wav is byte-identical to synth only", miss.Lfe.SequenceEqual(synthOnly.Lfe), "");
                var unk = Go("fb_unknown", new[] { new SoundCue { Name = "tnothere", At = 0.3, Player = true, Dist = 0 }, new SoundCue { Name = "tgone", At = 0.4, Player = true, Dist = 0 } }, 0.8);
                var none = Go("fb_none", new SoundCue[0], 0.8);
                T.Check("a sound with no stem (unknown name, or a stem missing on disk) is counted and leaves the output untouched",
                    unk.Bank.Missed == 2 && unk.Lfe.SequenceEqual(none.Lfe) && unk.R.Summary().Contains("tnothere"), unk.R.Summary());
                var alias = Go("alias", new[] { new SoundCue { Name = "TBANG.GPW", At = 0.3, Player = true, Dist = 0 } }, 0.8);
                T.Check("name lookup is case-insensitive and takes the .gpw alias", alias.Bank.Started == 1, alias.R.Summary());
                var solo = Go("standalone", new[] { new SoundCue { Name = "tbang", At = 0.5, Player = true, Dist = 0 } }, 1.0, null, new[] { "stems" });
                T.Check("standalone (sink 'stems', no lfe sink): stems.wav alone, same samples as the attached run",
                    solo.Lfe == null && solo.R != null && !solo.R.Attached && FirstNonZero(solo.Stems) == 8000 && solo.Stems.Skip(8000).Take(4000).SequenceEqual(Go("start_ref", new[] { new SoundCue { Name = "tbang", At = 0.5, Player = true, Dist = 0 } }, 1.0).Stems.Skip(8000).Take(4000)), solo.R?.Summary());
            }

            T.Section("Lfe.Stems: the real HD pack (tools/soundhd/out/pack-v1/lfe), when built");
            {
                var cfg = StemsConfig.From(EffectSet.Load().Rig.Output("stems"));
                var path = LfeStemsRenderer.ResolveManifest(cfg.Manifest);
                StemManifest m = null;
                if (File.Exists(path)) m = StemManifest.Load(path);
                if (m == null || m.Stems.Count == 0) T.Skipped("real pack stems", "not built (tools\\soundhd\\soundhd.py build): " + path);
                else
                {
                    T.Check("every listed stem is on disk, 16 kHz mono, non-empty (" + m.Stems.Count + ")", m.Missing.Count == 0 && m.Stems.Values.All(s => s.Rate == 16000 && s.Samples.Length > 0), "missing " + m.Missing.Count);
                    T.Check("engine loops are loops and carry the stock rate 11025 Hz for rate scaling", m.Stems.Values.Where(s => s.Category == "engine_loop").All(s => s.Loop && s.NominalHz == 11025), "");
                    var set = EffectSet.Load();
                    var dir = T.TempDir("stems");
                    var p = Session.Build(set, new[] { "lfe-wav" }, dir, "real_synthetic", false, 250, 60, null, TextWriter.Null);
                    var d = new Derive(); p.Core.Configure(d);
                    p.Run(Sources.FromDatagrams(Synthetic.Session(3), d, new TelCodec(null)));
                    foreach (var r in p.Renderers) r.Close();
                    var st = p.Renderers.OfType<LfeStemsRenderer>().First();
                    var pcm = ReadPcm(Path.Combine(dir, "real_synthetic.stems.wav"));
                    T.Check("synthetic session: whcan (AI cannon, 40 m) plays its stem at 14 s; tskid2 has no stem (tyres get none)",
                        st.Bank.Started == 1 && st.Bank.MissedNames.ContainsKey("tskid2") && MaxAbs(pcm, 14 * Rate, 15 * Rate) > 500 && MaxAbs(pcm, 0, 14 * Rate - 100) == 0, st.Summary());
                }
            }
        }
    }
}
