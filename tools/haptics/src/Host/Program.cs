using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using Haptics.Core;
using Haptics.Effects;
using Haptics.Renderers;
using Haptics.Transport;

namespace Haptics.Host
{
    /// <summary>
    /// The haptics host CLI. Everything is offline unless --live is passed: no device is opened, nothing is played,
    /// no game is touched. See tools/haptics/README.md.
    /// </summary>
    static class Program
    {
        const string Help = @"haptics <command> [options]

  replay <input> [--sinks wheel-file,pad-file,lfe-wav,motion-file,loopback-wav] [--out DIR] [--tag NAME]
         [--core-hz 250 | --core-hz frame --frame-hz 60] [--realtime] [--solo id,..] [--mute id,..]
         [--loopback-wav FILE] [--effects DIR] [--rig FILE] [--live]
         <input> = a .i76rec recording | a tools/ffb drive*.csv | synthetic | synthetic:v2 | synthetic:v3
  preview --effect ID [--out DIR] [--sinks ...]   render one effect alone (its stimulus, soloed) to all sinks
  synth --out FILE.i76rec [--version 2|3] [--repeats N]     write a scripted session as real datagrams
  record --udp [PORT] | --shm   --out FILE.i76rec [--seconds N]   capture telemetry (no device involved)
  live --source udp|shm [--port 7676] [--sinks ...] [--out DIR] [--seconds N] [--live]
         250 Hz loop against the running game; WITHOUT --live every output is a file sink (dry run)
  decode <FILE.i76rec> [--events]                 summary of a recording: versions, frames, events
  lint                                            effect/rig lints (HAPTICS-ARCHITECTURE 2.2)
  tune                                            the reference model's tune as read from effects/ + rigs/
  devices                                         audio output names (enumeration only, nothing is opened)
  loopback-probe --live [--seconds 1]             open the WASAPI loopback briefly: format, packets, peak (no samples kept)
";

        static int Main(string[] argv)
        {
            if (argv.Length == 0 || argv[0] == "help" || argv[0] == "--help") { Console.Write(Help); return 0; }
            var a = new Args(argv.Skip(1).ToArray());
            try
            {
                switch (argv[0])
                {
                    case "replay": return Replay(argv.Length > 1 ? argv[1] : null, a);
                    case "preview": return PreviewCmd(a);
                    case "synth": return Synth(a);
                    case "record": return Record(a);
                    case "live": return Live(a);
                    case "decode": return Decode(argv.Length > 1 ? argv[1] : null, a);
                    case "lint": return Lint(a);
                    case "tune": return TuneCmd(a);
                    case "devices": foreach (var (d, i) in LfeLiveOut.Devices().Select((d, i) => (d, i))) Console.WriteLine("{0,3}  {1}", i, d); return 0;
                    case "loopback-probe": return LoopbackProbe(a);
                    default: Console.Error.WriteLine("unknown command " + argv[0]); Console.Write(Help); return 2;
                }
            }
            catch (Exception ex) { Console.Error.WriteLine("error: " + ex.Message); return 1; }
        }

        sealed class Args
        {
            readonly string[] _a;
            public Args(string[] a) { _a = a; }
            public bool Has(string k) => _a.Contains(k);
            public string Get(string k, string d = null) { int i = Array.IndexOf(_a, k); return i >= 0 && i + 1 < _a.Length && !_a[i + 1].StartsWith("--") ? _a[i + 1] : d; }
            public double Num(string k, double d) => double.TryParse(Get(k), NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : d;
            public string[] List(string k, string d = "") => (Get(k, d) ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
        }

        static EffectSet LoadSet(Args a) => EffectSet.Load(a.Get("--effects"), a.Get("--rig"));

        static string OutDir(Args a, string dflt)
        {
            var d = a.Get("--out") ?? Path.Combine(EffectSet.DefaultRoot(), "out", dflt);
            Directory.CreateDirectory(d); return d;
        }

        static IEnumerable<FrameIn> Input(string input, Derive derive, Action<string> warn)
        {
            if (input == null) throw new ArgumentException("replay needs an input (a .i76rec, a drive*.csv, or synthetic[:v2|v3])");
            if (input.StartsWith("synthetic", StringComparison.OrdinalIgnoreCase))
            {
                int v = input.EndsWith(":v2") ? 2 : 3;
                return Sources.FromDatagrams(Synthetic.Session(v), derive, TelCodec.Default(), warn);
            }
            if (input.EndsWith(".csv", StringComparison.OrdinalIgnoreCase)) return Sources.FromDriveCsv(input);
            var rec = RecordingReader.Load(input);
            return Sources.FromDatagrams(rec.Records, derive, TelCodec.Default(), warn);
        }

        static void Guard(Args a)
        {
            if (a.Has("--live")) Console.WriteLine("--live: real devices WILL be opened (wheel force, pad motors, shaker audio).");
        }

        static int Replay(string input, Args a)
        {
            Guard(a);
            var set = LoadSet(a);
            string coreHzS = a.Get("--core-hz", "250");
            int coreHz = coreHzS == "frame" ? 0 : int.Parse(coreHzS, CultureInfo.InvariantCulture);
            int frameHz = (int)a.Num("--frame-hz", 60);
            string tag = a.Get("--tag") ?? (input == null ? "replay" : Path.GetFileNameWithoutExtension(input.Replace(':', '_')));
            var outDir = OutDir(a, "replay");
            var sinks = a.List("--sinks", "wheel-file,pad-file,lfe-wav,motion-file");
            var p = Session.Build(set, sinks, outDir, tag, a.Has("--live"), coreHz, frameHz, a.Get("--loopback-wav"));
            foreach (var s in a.List("--solo")) p.Core.Solo.Add(s);
            foreach (var s in a.List("--mute")) p.Core.Mute.Add(s);
            p.RealTime = a.Has("--realtime");
            var derive = new Derive(); p.Core.Configure(derive);
            var evLog = new StreamWriter(Path.Combine(outDir, tag + ".events.log"));
            int nev = 0;
            p.OnStep = s => { foreach (var e in s.Events) { nev++; evLog.WriteLine(Fmt.G(s.T, "0.000") + "  " + e); } };
            var cts = new CancellationTokenSource(); Console.CancelKeyPress += (o, e) => { e.Cancel = true; cts.Cancel(); };
            var t0 = DateTime.UtcNow;
            p.Run(Input(input, derive, w => Console.WriteLine("  decoder: " + w)), cts.Token);
            foreach (var r in p.Renderers) r.Close();
            evLog.Dispose();
            Console.WriteLine("replayed {0}: {1} frames, {2} core updates ({3}), {4} events, {5:0.0} s wall",
                input, p.Frames, p.Updates, coreHz > 0 ? coreHz + " Hz" : "one per frame", nev, (DateTime.UtcNow - t0).TotalSeconds);
            foreach (var r in p.Renderers) Console.WriteLine("  " + r.Summary());
            Console.WriteLine("  events -> " + Path.Combine(outDir, tag + ".events.log"));
            if (p.RealTime)
            {
                var h = p.LatenessHistogram();
                Console.WriteLine("  deadline: " + h);
                File.WriteAllText(Path.Combine(outDir, tag + ".deadlines.txt"), h + Environment.NewLine);
            }
            return 0;
        }

        static int PreviewCmd(Args a)
        {
            Guard(a);
            var set = LoadSet(a);
            var id = a.Get("--effect") ?? throw new ArgumentException("preview needs --effect <id>");
            var e = set.Get(id) ?? throw new ArgumentException("no effect '" + id + "' in " + set.EffectsDir);
            var outDir = OutDir(a, "preview");
            var p = Session.Build(set, a.List("--sinks", "wheel-file,pad-file,lfe-wav"), outDir, id, a.Has("--live"), (int)a.Num("--core-hz", 250));
            p.Core.Solo.Add(id);
            foreach (var c in Preview.Companions(id)) p.Core.Solo.Add(c);
            if (!e.Enabled) Console.WriteLine("note: " + id + " is disabled in its file; previewing it anyway");
            if (!e.Enabled) { e.Enabled = true; p.Core.Load(set); }
            p.Run(Preview.Stimulus(e));
            foreach (var r in p.Renderers) r.Close();
            Console.WriteLine("preview {0}: {1} updates", id, p.Updates);
            foreach (var r in p.Renderers) Console.WriteLine("  " + r.Summary());
            return 0;
        }

        static int Synth(Args a)
        {
            var path = a.Get("--out") ?? Path.Combine(EffectSet.DefaultRoot(), "replays", "synthetic-v3.i76rec");
            int v = (int)a.Num("--version", 3), rep = (int)a.Num("--repeats", 1);
            using (var w = new RecordingWriter(path, "{\"source\":\"haptics synth\",\"version\":" + v + ",\"repeats\":" + rep + ",\"script\":\"Transport/Synthetic.cs\"}"))
                foreach (var (t, d) in Synthetic.Session(v, 60, rep)) w.Add(t, d);
            Console.WriteLine("wrote " + path + " (" + new FileInfo(path).Length + " bytes)");
            return 0;
        }

        static int Record(Args a)
        {
            var path = a.Get("--out") ?? throw new ArgumentException("record needs --out FILE.i76rec");
            double secs = a.Num("--seconds", 0);
            var sw = System.Diagnostics.Stopwatch.StartNew();
            int n = 0;
            var cts = new CancellationTokenSource(); Console.CancelKeyPress += (o, e) => { e.Cancel = true; cts.Cancel(); };
            using (var w = new RecordingWriter(path, "{\"source\":\"" + (a.Has("--shm") ? "shm" : "udp") + "\",\"created\":\"" + DateTime.UtcNow.ToString("o") + "\"}"))
            {
                if (a.Has("--shm"))
                {
                    using (var shm = new ShmReader())
                        while (!cts.IsCancellationRequested && (secs <= 0 || sw.Elapsed.TotalSeconds < secs))
                        { var d = shm.Poll(); if (d != null) { w.Add(sw.Elapsed.TotalSeconds, d); n++; } else Thread.Sleep(1); }
                }
                else
                {
                    using (var u = new UdpListener((int)a.Num("--udp", 7676)))
                        while (!cts.IsCancellationRequested && (secs <= 0 || sw.Elapsed.TotalSeconds < secs))
                        { var d = u.Receive(100); if (d != null) { w.Add(sw.Elapsed.TotalSeconds, d); n++; } }
                }
            }
            Console.WriteLine("recorded {0} datagrams in {1:0.0} s -> {2}", n, sw.Elapsed.TotalSeconds, path);
            return 0;
        }

        /// <summary>The live 250 Hz loop: newest frame from UDP or shm, core updates on the host clock between frames.</summary>
        static int Live(Args a)
        {
            Guard(a);
            var set = LoadSet(a);
            var outDir = OutDir(a, "live");
            var p = Session.Build(set, a.List("--sinks", "wheel-file,pad-file,lfe-wav,motion-file"), outDir, "live", a.Has("--live"), 250);
            var derive = new Derive(); p.Core.Configure(derive);
            var codec = TelCodec.Default();
            bool shm = a.Get("--source", "udp") == "shm";
            double secs = a.Num("--seconds", 0);
            using var udp = shm ? null : new UdpListener((int)a.Num("--port", 7676));
            using var sh = shm ? new ShmReader() : null;
            using var rec = a.Get("--record") != null ? new RecordingWriter(a.Get("--record")) : null;
            var cts = new CancellationTokenSource(); Console.CancelKeyPress += (o, e) => { e.Cancel = true; cts.Cancel(); };
            var sw = System.Diagnostics.Stopwatch.StartNew();
            Derive.Result last = null; double lastSim = 0, lastArrive = 0; var pending = new List<HapticEvent>();
            var effectsDir = set.EffectsDir; DateTime stamp = Directory.GetFiles(effectsDir, "*.json").Max(f => File.GetLastWriteTimeUtc(f));
            var late = new List<double>(); double next = 0, lastReloadCheck = 0; int frames = 0;
            Console.WriteLine("live: waiting for telemetry on " + (shm ? "shm" : "udp :" + udp.Port) + (a.Has("--live") ? " (devices LIVE)" : " (file sinks only - add --live for devices)"));
            while (!cts.IsCancellationRequested && (secs <= 0 || sw.Elapsed.TotalSeconds < secs))
            {
                // drain the source: keep the newest frame, accumulate events
                while (true)
                {
                    byte[] d = shm ? sh.Poll() : udp.Receive(0);
                    if (d == null) break;
                    rec?.Add(sw.Elapsed.TotalSeconds, d);
                    var dg = codec.Decode(d);
                    if (dg?.Frame == null) continue;
                    last = derive.Step(dg.Frame, dg.Events, 0.0); pending.AddRange(last.Events);
                    lastSim = dg.Frame.SimTime; lastArrive = sw.Elapsed.TotalSeconds; frames++;
                }
                if (last != null)
                {
                    double t = lastSim + Math.Min(0.25, sw.Elapsed.TotalSeconds - lastArrive);
                    var s = last.Sample.Clone(); s.SinceTick = sw.Elapsed.TotalSeconds - lastArrive;
                    if (pending.Count == 0) { s.Shift = 0; s.FxFired = null; }
                    var step = p.Core.Step(new Derive.Result { Sample = s, State = last.State, Vars = last.Vars }, pending, t);
                    foreach (var r in p.Renderers) r.Render(step);
                    pending = new List<HapticEvent>();
                    if (s.Shift != 0 || last.Sample.FxFired != null) { last.Sample.Shift = 0; last.Sample.FxFired = null; }
                }
                // hot reload of effects/*.json
                if (sw.Elapsed.TotalSeconds - lastReloadCheck >= 1.0)
                {
                    lastReloadCheck = sw.Elapsed.TotalSeconds;
                    var st = Directory.GetFiles(effectsDir, "*.json").Max(f => File.GetLastWriteTimeUtc(f));
                    if (st != stamp) { stamp = st; try { var ns = EffectSet.Load(a.Get("--effects"), a.Get("--rig")); p.Core.Load(ns); Console.WriteLine("reloaded effects"); } catch (Exception ex) { Console.WriteLine("reload failed: " + ex.Message); } }
                }
                next += 0.004;
                double now = sw.Elapsed.TotalSeconds;
                if (next > now) { while (sw.Elapsed.TotalSeconds < next - 0.0015) Thread.Sleep(1); while (sw.Elapsed.TotalSeconds < next) Thread.SpinWait(50); }
                else if (now - next > 0.1) next = now;
                late.Add((sw.Elapsed.TotalSeconds - next) * 1000);
            }
            foreach (var r in p.Renderers) r.Close();
            var lp = new Pipeline(); lp.LatenessMs.AddRange(late);
            Console.WriteLine("live: {0} frames; loop deadline {1}", frames, lp.LatenessHistogram());
            foreach (var r in p.Renderers) Console.WriteLine("  " + r.Summary());
            return 0;
        }

        static int Decode(string path, Args a)
        {
            var rec = RecordingReader.Load(path);
            var codec = TelCodec.Default();
            var versions = new Dictionary<int, int>(); var evTypes = new Dictionary<uint, int>(); int bad = 0;
            foreach (var (t, d) in rec.Records)
            {
                var dg = codec.Decode(d);
                if (dg?.Frame == null) { bad++; continue; }
                versions[dg.Frame.Version] = versions.GetValueOrDefault(dg.Frame.Version) + 1;
                foreach (var e in dg.Events)
                {
                    evTypes[e.Type] = evTypes.GetValueOrDefault(e.Type) + 1;
                    if (a.Has("--events")) Console.WriteLine("{0,8:0.000}  type {1} seq {2} f=[{3}] i=[{4}] name '{5}'", t, e.Type, e.Seq,
                        string.Join(", ", e.F.Select(x => x.ToString("0.###", CultureInfo.InvariantCulture))), string.Join(", ", e.I), e.Name8);
                }
            }
            Console.WriteLine("{0}: meta {1}", path, rec.Meta);
            Console.WriteLine("  {0} datagrams, {1} undecodable; versions {2}; events by type {3}", rec.Records.Count, bad,
                string.Join(" ", versions.Select(kv => "v" + kv.Key + ":" + kv.Value)), string.Join(" ", evTypes.Select(kv => kv.Key + ":" + kv.Value)));
            return bad == 0 ? 0 : 1;
        }

        static int Lint(Args a)
        {
            var set = LoadSet(a);
            var t = set.BuildTune();
            var core = new LfeCore(16000, t["LfeEngineJitter"], t["LfeImpactHz"], t["LfeWeaponHz"], t["LfeCarrierHz"], 11, 85,
                                   t.Array("LfeRespHz"), t.Array("LfeRespRel"), t["LfeCompMax"], t["LfeScrubHz"], t["LfeExplodeHz"]);
            var issues = set.Lint(core.Comp);
            Console.WriteLine("{0} effects ({1} legacy, {2} chain, {3} enabled), rig {4}", set.Effects.Count, set.Effects.Count(e => e.IsLegacy),
                set.Effects.Count(e => e.IsChain), set.Effects.Count(e => e.Enabled), set.Rig.Name);
            foreach (var i in issues) Console.WriteLine("  " + i);
            int err = issues.Count(i => i.Error);
            Console.WriteLine("{0} errors, {1} warnings", err, issues.Count - err);
            return err == 0 ? 0 : 1;
        }

        static int TuneCmd(Args a)
        {
            var set = LoadSet(a);
            var t = set.BuildTune();
            foreach (var k in t.ScalarKeys.Concat(t.ArrayKeys).OrderBy(x => x)) Console.WriteLine("{0,-16} {1,-50} {2}", k, set.TuneMap[k], t.Describe(k));
            return 0;
        }

        static int LoopbackProbe(Args a)
        {
            if (!a.Has("--live")) { Console.WriteLine("loopback-probe opens the default render endpoint for capture; pass --live to allow it."); return 2; }
            var cap = new WasapiLoopback();
            var err = cap.Start(null);
            if (err != null) { Console.WriteLine("loopback: " + err); return 1; }
            Thread.Sleep((int)(a.Num("--seconds", 1) * 1000));
            cap.Stop();
            Console.WriteLine("loopback OK: {0}; {1} packets, {2} frames ({3} flagged silent), peak {4:0.0000} (samples discarded)",
                cap.FormatText, cap.Packets, cap.Frames, cap.SilentPackets, cap.Peak);
            return 0;
        }
    }
}
