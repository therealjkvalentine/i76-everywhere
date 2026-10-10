using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Haptics;
using Haptics.Core;
using Haptics.Effects;
using Haptics.Renderers;
using Haptics.Transport;

namespace Haptics.Tests
{
    static class RendererTests
    {
        static IEnumerable<FrameIn> GoldenFrames(string csv)
        {
            var g = CsvTable.Load(csv);
            for (int r = 0; r < g.Rows.Count; r++)
            {
                var s = GoldenTests.RowToSample(g, r);
                yield return new FrameIn { HostT = s.T, SimT = s.T, D = Derive.FromSample(s) };
            }
        }

        /// <summary>RMS in dB per band (FFT of the whole file), the B1 comparison measure.</summary>
        public static double[] BandDb(short[] pcm, int rate, double[][] bands)
        {
            int n = 1; while (n < pcm.Length) n <<= 1;
            var re = new double[n]; var im = new double[n];
            for (int i = 0; i < pcm.Length; i++) re[i] = pcm[i] / 32768.0;
            Fft(re, im);
            var o = new double[bands.Length];
            for (int b = 0; b < bands.Length; b++)
            {
                double e = 0;
                for (int k = 1; k < n / 2; k++) { double f = k * (double)rate / n; if (f >= bands[b][0] && f < bands[b][1]) e += re[k] * re[k] + im[k] * im[k]; }
                o[b] = 10 * Math.Log10(e + 1e-12);
            }
            return o;
        }
        static void Fft(double[] re, double[] im)
        {
            int n = re.Length;
            for (int i = 1, j = 0; i < n; i++) { int bit = n >> 1; for (; (j & bit) != 0; bit >>= 1) j ^= bit; j ^= bit; if (i < j) { (re[i], re[j]) = (re[j], re[i]); (im[i], im[j]) = (im[j], im[i]); } }
            for (int len = 2; len <= n; len <<= 1)
            {
                double ang = -2 * Math.PI / len; double wr = Math.Cos(ang), wi = Math.Sin(ang);
                for (int i = 0; i < n; i += len)
                {
                    double cr = 1, ci = 0;
                    for (int k = 0; k < len / 2; k++)
                    {
                        int a = i + k, b = i + k + len / 2;
                        double tr = re[b] * cr - im[b] * ci, ti = re[b] * ci + im[b] * cr;
                        re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti;
                        double nr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = nr;
                    }
                }
            }
        }

        public static void Run()
        {
            var golden = Path.Combine(T.HapticsRoot, "tests", "golden", "out");
            var probeDir = Path.Combine(T.HapticsRoot, "tests", "out", "probe");
            var bands = new[] { new[] { 20.0, 40 }, new[] { 40.0, 80 }, new[] { 80.0, 160 }, new[] { 160.0, 320 } };

            T.Section("B1 Lfe.Synth: probe scenarios re-rendered through the host vs ffb-lfe-probe.ps1's own WAVs");
            var names = new[] { "idle", "cruise", "accel", "brake", "bumps", "rev", "weapon", "collide", "slide" };
            if (!File.Exists(Path.Combine(probeDir, "idle.wav")))
                T.Skipped("probe comparison", "no " + probeDir + "\\*.wav - haptics.ps1 test renders them with tools/ffb/ffb-lfe-probe.ps1 -OutDir");
            else
                foreach (var nm in names)
                {
                    var csv = Path.Combine(golden, "probe_" + nm + ".csv");
                    if (!File.Exists(csv)) { T.Check("golden probe_" + nm + " present", false, csv); continue; }
                    var set = EffectSet.Load();
                    var p = Session.Build(set, new[] { "lfe-wav" }, null, "probe_" + nm, false, 0, 60);
                    p.Run(GoldenFrames(csv));
                    var mine = ((LfeSynthRenderer)p.Renderers[0]).Pcm;
                    var (rate, refS) = Wav.Read(Path.Combine(probeDir, nm + ".wav"));
                    var refPcm = refS.Select(x => (short)Math.Round(x * 32768.0)).ToArray();
                    int diff = 0; int maxd = 0;
                    for (int i = 0; i < Math.Min(mine.Length, refPcm.Length); i++) { int d = Math.Abs(mine[i] - refPcm[i]); if (d > 0) diff++; maxd = Math.Max(maxd, d); }
                    var a = BandDb(mine, 16000, bands); var b = BandDb(refPcm, 16000, bands);
                    double worst = a.Zip(b, (x, y) => Math.Abs(x - y)).Max();
                    T.Check("probe " + nm + ": same length, sample-identical, every band within 1 dB", mine.Length == refPcm.Length && diff == 0 && worst <= 1.0,
                        string.Format("len {0}/{1}, {2} samples differ (max {3}), worst band {4:0.000} dB", mine.Length, refPcm.Length, diff, maxd, worst));
                }

            T.Section("Pad.XInput");
            {
                var set = EffectSet.Load();
                var core = new HapticCore(set);
                var pad = new PadXInput();
                var cfg = (System.Text.Json.Nodes.JsonObject)set.Rig.Output("pad").DeepClone(); cfg["mode"] = "sum";
                pad.Open(new RendererContext { Config = cfg, Rig = set.Rig, Tune = core.Mixer.Tune, Effects = set, OutDir = null });
                var g = CsvTable.Load(Path.Combine(golden, "pad_impact.csv"));
                int bad = 0;
                for (int r = 0; r < g.Rows.Count; r++)
                {
                    var s = GoldenTests.RowToSample(g, r);
                    var st = core.Step(Derive.FromSample(s), new List<HapticEvent>(), s.T);
                    var (L, R) = pad.Mix(st);
                    if (Math.Abs(L - g.D(r, "pad_L")) > 1e-6 || Math.Abs(R - g.D(r, "pad_R")) > 1e-6) bad++;
                }
                T.Check("mode 'sum' reproduces Mix-RenderPad on a golden drive", bad == 0, bad + " frames differ");

                var maxPad = new PadXInput();
                maxPad.Open(new RendererContext { Config = set.Rig.Output("pad"), Rig = set.Rig, Tune = core.Mixer.Tune, Effects = set });
                var quiet = new CoreStep { T = 0, Mix = new ReferenceMixer(core.Mixer.Tune).Update(new Sample { T = 0 }), State = new VehicleState() };
                T.Check("mode 'max': a silent bus is silent (no dead-zone lift under nothing)", maxPad.Mix(quiet) == (0.0, 0.0), maxPad.Mix(quiet).ToString());
                var b = quiet.Bus; b.Voices.Add(new Voice { Id = "x", PadL = 0.5 });
                var (l1, _) = maxPad.Mix(new CoreStep { T = 1.0, Mix = quiet.Mix, State = quiet.State });
                T.Check("mode 'max': level 0.5 lifts to 0.30 + 0.5 x 0.70 = 0.65", Math.Abs(l1 - 0.65) < 1e-9, l1.ToString());
                b.Voices.Clear();
                var (l2, _) = maxPad.Mix(new CoreStep { T = 1.016, Mix = quiet.Mix, State = quiet.State });
                var (l3, _) = maxPad.Mix(new CoreStep { T = 1.045, Mix = quiet.Mix, State = quiet.State });
                T.Check("a one-frame spike is held >= 40 ms (ERM spin-up), then released", Math.Abs(l2 - 0.65) < 1e-9 && l3 == 0, l2 + " then " + l3);
                b.Voices.Add(new Voice { Id = "a", PadR = 0.3 }); b.Voices.Add(new Voice { Id = "b", PadR = 0.6 });
                var (_, r4) = maxPad.Mix(new CoreStep { T = 2.0, Mix = quiet.Mix, State = quiet.State });
                T.Check("per-motor MAX, not SUM (0.3 and 0.6 -> 0.6 before lift)", Math.Abs(r4 - (0.30 + 0.6 * 0.70)) < 1e-9, r4.ToString());
            }

            T.Section("Wheel.DirectInput (file sink)");
            {
                var set = EffectSet.Load(); var core = new HapticCore(set);
                var g = CsvTable.Load(Path.Combine(golden, "minforce_lift.csv"));
                int bad = 0;
                for (int r = 0; r < g.Rows.Count; r++)
                {
                    var s = GoldenTests.RowToSample(g, r);
                    var st = core.Step(Derive.FromSample(s), new List<HapticEvent>(), s.T);
                    if (WheelDirectInput.DeviceForce(st, 900, 150, 9500) != (int)g.D(r, "wheel")) bad++;
                }
                T.Check("no chain voices -> device force = Mix-RenderWheel exactly (golden 'wheel' column)", bad == 0, bad + " frames differ");
            }

            T.Section("Lfe.Loopback bed (offline: a WAV in place of the WASAPI capture)");
            {
                var dir = T.TempDir("loopback");
                var wav = Path.Combine(dir, "tone40_200_48k.wav");
                int sr = 48000; var tone = new short[sr * 2];
                for (int i = 0; i < tone.Length; i++) tone[i] = (short)(8000 * Math.Sin(2 * Math.PI * 40 * i / sr) + 8000 * Math.Sin(2 * Math.PI * 200 * i / sr));
                Wav.Write(wav, tone, sr);
                var bed = new LoopbackBed(16000, 1.0, 22, 90);
                var (r0, s0) = Wav.Read(wav); bed.SetSourceRate(r0); bed.MaxQueue = int.MaxValue / 8;
                bed.Push(s0.Select(x => (float)x).ToArray(), s0.Length);
                var outp = new short[16000]; for (int i = 0; i < outp.Length; i++) outp[i] = (short)(bed.Next() * 32767);
                var db = BandDb(outp.Skip(4000).ToArray(), 16000, new[] { new[] { 30.0, 50 }, new[] { 180.0, 220 } });
                T.Check("40 Hz passes, 200 Hz is >= 12 dB down after the bed's HP/LP (resampled 48k -> 16k)", db[0] - db[1] >= 12, string.Format("40 Hz {0:0.0} dB, 200 Hz {1:0.0} dB", db[0], db[1]));
                bed.SetGate(false); double tail = 0; for (int i = 0; i < 4000; i++) tail = Math.Abs(bed.Next());
                T.Check("gate closed (no player / music) -> the bed fades to silence", tail < 1e-3, tail.ToString());
                bed.SetGate(true); for (int i = 0; i < 4000; i++) bed.Next();
                double open = 0; for (int i = 0; i < 2000; i++) open = Math.Max(open, Math.Abs(bed.Next()));
                bed.SetDuck(0.25); for (int i = 0; i < 100; i++) bed.Next();
                double ducked = 0; for (int i = 0; i < 2000; i++) ducked = Math.Max(ducked, Math.Abs(bed.Next()));
                T.Check("duck 0.25 scales the bed to a quarter", Math.Abs(ducked / open - 0.25) < 0.05, (ducked / open).ToString("0.000"));
            }

            T.Section("preview: every effect renders alone to wheel + pad + lfe without error");
            {
                var set = EffectSet.Load();
                foreach (var e in set.Effects)
                {
                    if (e.Kind == "global" || e.Model == "legacy.unused") continue;
                    try
                    {
                        var s2 = EffectSet.Load(); var ee = s2.Get(e.Id); ee.Enabled = true;
                        var p = Session.Build(s2, new[] { "wheel-file", "pad-file", "lfe-wav" }, null, e.Id, false, 250);
                        p.Core.Solo.Add(e.Id); foreach (var c in Preview.Companions(e.Id)) p.Core.Solo.Add(c);
                        double wheel = 0, pad = 0, lfe = 0;
                        var w = (WheelDirectInput)p.Renderers[0]; var pd = (PadXInput)p.Renderers[1]; var lf = (LfeSynthRenderer)p.Renderers[2];
                        p.OnStep = st => { wheel = Math.Max(wheel, Math.Abs(w.LastDevice)); pad = Math.Max(pad, Math.Max(pd.Last.L, pd.Last.R)); };
                        p.Run(Preview.Stimulus(ee));
                        lfe = lf.Pcm.Select(x => Math.Abs((int)x)).DefaultIfEmpty(0).Max() / 32767.0;
                        bool wantWheel = ee.HasWheel || (ee.IsLegacy && ee.Json["routing"]?["wheel"] != null);
                        bool wantLfe = ee.Json["routing"]?["lfe"]?["amp"] != null;
                        bool wantPad = ee.Pad.Count > 0;
                        bool ok = (!wantWheel || wheel > 0) && (!wantLfe || lfe > 0.01) && (!wantPad || pad > 0);
                        T.Check("preview " + e.Id, ok, string.Format("wheel {0} pad {1:0.00} lfe {2:0.00} (wants wheel {3} pad {4} lfe {5})", wheel, pad, lfe, wantWheel, wantPad, wantLfe));
                    }
                    catch (Exception ex) { T.Check("preview " + e.Id, false, ex.GetType().Name + ": " + ex.Message); }
                }
            }

            T.Section("pipeline: deterministic replay; synthetic session through every sink");
            {
                string Run1(string tag)
                {
                    var dir = T.TempDir("determinism");
                    var p = Session.Build(EffectSet.Load(), new[] { "wheel-file", "pad-file", "lfe-wav", "motion-file" }, dir, tag, false, 250);
                    var d = new Derive(); p.Core.Configure(d);
                    p.Run(Sources.FromDatagrams(Synthetic.Session(3), d, new TelCodec(null)));
                    foreach (var r in p.Renderers) r.Close();
                    return dir;
                }
                var dirA = Run1("a"); Run1("b");
                bool same = new[] { ".wheel.csv", ".pad.csv", ".lfe.wav", ".motion.csv" }.All(x => File.ReadAllBytes(Path.Combine(dirA, "a" + x)).SequenceEqual(File.ReadAllBytes(Path.Combine(dirA, "b" + x))));
                T.Check("two replays of the same session write byte-identical files", same, "");
                var wheel = CsvTable.Load(Path.Combine(dirA, "a.wheel.csv"));
                int peak = Enumerable.Range(0, wheel.Rows.Count).Max(r => Math.Abs((int)wheel.D(r, "device_force")));
                T.Check("the wheel file stays inside the clamp", peak <= 9500, peak.ToString());
                var pad = CsvTable.Load(Path.Combine(dirA, "a.pad.csv"));
                double padPeak = Enumerable.Range(0, pad.Rows.Count).Max(r => pad.D(r, "L"));
                T.Check("the pad file reaches the heavy motor on the impact / landing", padPeak > 0.6, padPeak.ToString());
                var (_, lfe) = Wav.Read(Path.Combine(dirA, "a.lfe.wav"));
                T.Check("the LFE WAV is 20 s at 16 kHz and never clips", Math.Abs(lfe.Length - 20 * 16000) < 400 && lfe.Max(x => Math.Abs(x)) < 0.999, lfe.Length + " samples");
            }
        }
    }
}
