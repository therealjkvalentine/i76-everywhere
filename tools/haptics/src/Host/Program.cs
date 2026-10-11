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
  motion <input> [--targets flypt,native] [--send] [--fast] [--repeat N] [--hz 100] [--resample interp|hold]
         [--targets-file FILE] [--startup-neutral S] [--core-hz 1000] [--out DIR] [--tag NAME] [--rig FILE]
         replay -> the motion renderer (docs/MOTION-OUTPUT.md): packet logs per target in --out; with --send also UDP
         to the targets' loopback ports, paced in real time (--fast: as fast as possible). Default targets: the
         enabled ones in motion/targets.json. <input> as for replay.
  preview --effect ID [--out DIR] [--sinks ...]   render one effect alone (its stimulus, soloed) to all sinks
  synth --out FILE.i76rec [--version 2|3] [--repeats N]     write a scripted session as real datagrams
  record --udp [PORT] | --shm   --out FILE.i76rec [--seconds N]   capture telemetry (no device involved)
  live --source udp|shm [--port 7676] [--sinks ...] [--out DIR] [--seconds N] [--live]
         250 Hz loop against the running game; WITHOUT --live every output is a file sink (dry run)
  play <FILE.i76rec | synthetic> [--port 7676] [--repeats N]   send a recording's datagrams to 127.0.0.1:PORT at their
         recorded times (stands in for the game when testing `live`; loopback only, prints the sender's own pacing)
  decode <FILE.i76rec> [--events]                 summary of a recording: versions, frames, events
  lint                                            effect/rig lints (HAPTICS-ARCHITECTURE 2.2)
  tune                                            the reference model's tune as read from effects/ + rigs/
  devices                                         audio output names (enumeration only, nothing is opened)
  loopback-probe --live [--seconds 1]             open the WASAPI loopback briefly: format, packets, peak (no samples kept)
";

        static int Main(string[] argv)
        {
            if (argv.Length == 0 || argv[0] == "help" || argv[0] == "--help") { Console.Write(Help); Console.Write(StemsCommand.HelpText); return 0; }
            var a = new Args(argv.Skip(1).ToArray());
            try
            {
                switch (argv[0])
                {
                    case "replay": return Replay(argv.Length > 1 ? argv[1] : null, a);
                    case "preview": return PreviewCmd(a);
                    case "motion": return MotionCmd(argv.Length > 1 ? argv[1] : null, a);
                    case "synth": return Synth(a);
                    case "record": return Record(a);
                    case "live": return Live(a);
                    case "play": return Play(argv.Length > 1 ? argv[1] : null, a);
                    case "decode": return Decode(argv.Length > 1 ? argv[1] : null, a);
                    case "lint": return Lint(a);
                    case "tune": return TuneCmd(a);
                    case "devices": foreach (var (d, i) in LfeLiveOut.Devices().Select((d, i) => (d, i))) Console.WriteLine("{0,3}  {1}", i, d); return 0;
                    case "loopback-probe": return LoopbackProbe(a);
                    case "stems": return StemsCommand.Run(argv.Skip(1).ToArray());   // HD sound pack LFE stems (StemsCommand.cs)
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
            p.Rt = RtOptions.Parse(a.Get("--rt"));
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
                var h = p.Stats.Report();
                Console.Write("  " + h.Replace(Environment.NewLine, Environment.NewLine + "  ").TrimEnd() + Environment.NewLine);
                File.WriteAllText(Path.Combine(outDir, tag + ".deadlines.txt"), h);
            }
            return 0;
        }

        /// <summary>
        /// haptics motion: a recording / synthetic session through the core into Motion.Udp only. Files always; UDP only with
        /// --send (loopback targets only: the config lint refuses anything else without allow_remote).
        /// </summary>
        static int MotionCmd(string input, Args a)
        {
            var set = LoadSet(a);
            string tag = a.Get("--tag") ?? (input == null ? "motion" : Path.GetFileNameWithoutExtension(input.Replace(':', '_')));
            var outDir = OutDir(a, "motion");
            bool send = a.Has("--send");
            var cfg = (set.Rig.Output("motion_udp")?.DeepClone() as System.Text.Json.Nodes.JsonObject) ?? new System.Text.Json.Nodes.JsonObject { ["renderer"] = "Motion.Udp" };
            if (a.Get("--targets") != null) cfg["select"] = a.Get("--targets");
            if (a.Get("--targets-file") != null) cfg["targets_file"] = Path.GetFullPath(a.Get("--targets-file"));
            if (a.Get("--hz") != null) cfg["output_hz"] = a.Num("--hz", 100);
            if (a.Get("--resample") != null) cfg["resample"] = a.Get("--resample");
            if (a.Get("--startup-neutral") != null) cfg["startup_neutral_s"] = a.Num("--startup-neutral", 2.0);
            cfg["send"] = send;
            // 1 kHz core grid: output ticks (100 Hz) are emitted when a core step crosses them, so the grid sets the send
            // jitter (250 Hz would send at 8 / 12 ms alternately in real time); packet contents do not depend on it
            int coreHz = (int)a.Num("--core-hz", 1000);
            var p = Session.Build(set, new string[0], outDir, tag, false, coreHz);
            var mr = new MotionUdpRenderer();
            mr.Open(new RendererContext { OutputName = "motion_udp", Config = cfg, Rig = set.Rig, Effects = set, Tune = p.Core.Mixer.Tune, OutDir = outDir, Tag = tag, CoreHz = coreHz });
            p.Renderers.Add(mr);
            p.RealTime = (send && !a.Has("--fast")) || a.Has("--realtime");
            p.Rt = RtOptions.Parse(a.Get("--rt"));
            var derive = new Derive(); p.Core.Configure(derive);
            int repeat = Math.Max(1, (int)a.Num("--repeat", 1));
            var cts = new CancellationTokenSource(); Console.CancelKeyPress += (o, e) => { e.Cancel = true; cts.Cancel(); };
            if (p.RealTime) Console.WriteLine("motion: real-time playback" + (repeat > 1 ? ", " + repeat + " passes" : "") + "; Ctrl+C stops (the targets then get the shutdown packet)");
            var t0 = DateTime.UtcNow;
            p.Run(MotionInput(input, derive, repeat, w => Console.WriteLine("  decoder: " + w)), cts.Token);
            foreach (var r in p.Renderers) r.Close();
            Console.WriteLine("motion {0}: {1} frames, {2:0.0} s wall", input, p.Frames, (DateTime.UtcNow - t0).TotalSeconds);
            Console.WriteLine("  " + mr.Summary());
            foreach (var (tg, kind, path) in mr.Logs) Console.WriteLine("  log {0} {1} -> {2}", tg, kind, path);
            return 0;
        }

        /// <summary>Datagrams of a recording / synthetic session, optionally looped: each pass shifts sim_time / frame / seq so time keeps running forward.</summary>
        static IEnumerable<FrameIn> MotionInput(string input, Derive derive, int repeat, Action<string> warn)
        {
            if (input == null) throw new ArgumentException("motion needs an input (a .i76rec, a drive*.csv, or synthetic[:v2|v3])");
            if (input.EndsWith(".csv", StringComparison.OrdinalIgnoreCase)) return Sources.FromDriveCsv(input);
            List<(double t, byte[] data)> recs = input.StartsWith("synthetic", StringComparison.OrdinalIgnoreCase)
                ? Synthetic.Session(input.EndsWith(":v2") ? 2 : 3).ToList()
                : RecordingReader.Load(input).Records;
            return Sources.FromDatagrams(Loop(recs, repeat), derive, TelCodec.Default(), warn);
        }

        static IEnumerable<(double t, byte[] data)> Loop(List<(double t, byte[] data)> recs, int repeat)
        {
            foreach (var r in recs) yield return r;
            if (repeat <= 1 || recs.Count < 2) yield break;
            var codec = TelCodec.Default();
            var first = codec.Decode(recs[0].data); var last = codec.Decode(recs[recs.Count - 1].data);
            if (first?.Frame == null || last?.Frame == null) yield break;
            // passes are separated by 1.5 s of silence: the end of a pass and the start of the next are different places and
            // speeds, so the host must see a dropout (no derivative across the seam, a smooth ramp to neutral and back)
            // rather than a teleport (which would read as a huge impulse)
            const double Seam = 1.5;
            double hostSpan = recs[recs.Count - 1].t - recs[0].t + (recs[1].t - recs[0].t) + Seam;
            double simSpan = last.Frame.SimTime - first.Frame.SimTime + Math.Max(0.001, last.Frame.SimDt) + Seam;
            double frameSpan = last.Frame.SimFrame - first.Frame.SimFrame + 1, seqSpan = last.Frame.Seq - first.Frame.Seq + 1;
            double pfSpan = last.Frame.ProxyFrame - first.Frame.ProxyFrame + 1, evSpan = last.Frame.EventSeq;
            for (int k = 1; k < repeat; k++)
                foreach (var (t, d) in recs)
                {
                    var dg = codec.Decode(d);
                    if (dg?.Frame == null) continue;
                    var f = dg.Frame;
                    f["sim_time"] = f.SimTime + k * simSpan; f["frame"] = f.SimFrame + k * frameSpan; f["seq"] = f.Seq + k * seqSpan;
                    f["proxy_frame"] = f.ProxyFrame + k * pfSpan; f["event_seq"] = f.EventSeq + k * evSpan;
                    foreach (var e in dg.Events) { e.Seq += (uint)(k * evSpan); e.Frame += (uint)(k * pfSpan); }
                    yield return (t + k * hostSpan, TelCodec.Encode(f, dg.Events, dg.Layout, f.Size));
                }
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

        /// <summary>One decoded telemetry frame handed from the source thread to the tick thread.</summary>
        sealed class LiveFrame { public Derive.Result D; public double Sim, Arrive; }

        /// <summary>
        /// The live 250 Hz loop. Three threads so no I/O sits on the tick: a SOURCE thread (blocking UDP receive, or a 1 ms shm
        /// poll) that also records, decodes and derives, and hands frames over a queue; a RELOAD thread that checks effects/*.json
        /// once a second and loads a changed set; and the TICK thread (this one: RtWaiter, high-resolution timer + spin,
        /// priority Highest + MMCSS) that runs the core and the renderers on an absolute 4 ms schedule. Motion.Udp sends from
        /// its own output thread at output_hz (IRealTimeRenderer). --rt legacy restores the old wait for A/B.
        /// </summary>
        static int Live(Args a)
        {
            Guard(a);
            var set = LoadSet(a);
            var outDir = OutDir(a, "live");
            var p = Session.Build(set, a.List("--sinks", "wheel-file,pad-file,lfe-wav,motion-file"), outDir, "live", a.Has("--live"), 250, hostClock: true);
            var derive = new Derive(); p.Core.Configure(derive);
            var codec = TelCodec.Default();
            bool shm = a.Get("--source", "udp") == "shm";
            double secs = a.Num("--seconds", 0);
            var rtOpt = RtOptions.Parse(a.Get("--rt"));
            using var udp = shm ? null : new UdpListener((int)a.Num("--port", 7676));
            using var sh = shm ? new ShmReader() : null;
            using var rec = a.Get("--record") != null ? new RecordingWriter(a.Get("--record")) : null;
            var cts = new CancellationTokenSource(); Console.CancelKeyPress += (o, e) => { e.Cancel = true; cts.Cancel(); };
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var queue = new System.Collections.Concurrent.ConcurrentQueue<LiveFrame>();
            int frames = 0;

            // source thread: receive (blocking), record, decode, derive -> queue
            var source = new Thread(() =>
            {
                while (!cts.IsCancellationRequested)
                {
                    byte[] d = shm ? sh.Poll() : udp.Receive(50);
                    if (d == null) { if (shm) Thread.Sleep(1); continue; }
                    double arrive = sw.Elapsed.TotalSeconds;
                    rec?.Add(arrive, d);
                    var dg = codec.Decode(d);
                    if (dg?.Frame == null) continue;
                    queue.Enqueue(new LiveFrame { D = derive.Step(dg.Frame, dg.Events, 0.0), Sim = dg.Frame.SimTime, Arrive = arrive });
                }
            }) { IsBackground = true, Name = "live source", Priority = ThreadPriority.AboveNormal };

            // reload thread: hot reload of effects/*.json, applied by the tick thread between updates
            var effectsDir = set.EffectsDir; EffectSet reloaded = null;
            var reloader = new Thread(() =>
            {
                DateTime stamp = Directory.GetFiles(effectsDir, "*.json").Max(f => File.GetLastWriteTimeUtc(f));
                while (!cts.Token.WaitHandle.WaitOne(1000))
                {
                    try
                    {
                        var st = Directory.GetFiles(effectsDir, "*.json").Max(f => File.GetLastWriteTimeUtc(f));
                        if (st == stamp) continue;
                        stamp = st;
                        Volatile.Write(ref reloaded, EffectSet.Load(a.Get("--effects"), a.Get("--rig")));
                    }
                    catch (Exception ex) { Console.WriteLine("reload failed: " + ex.Message); }
                }
            }) { IsBackground = true, Name = "live reload" };

            Console.WriteLine("live: waiting for telemetry on " + (shm ? "shm" : "udp :" + udp.Port) + (a.Has("--live") ? " (devices LIVE)" : " (file sinks only - add --live for devices)"));
            var stages = new[] { "drain", "core" }.Concat(p.Renderers.Select(r => r.Type)).Concat(new[] { "reload" }).ToArray();
            LoopStats stats;
            Derive.Result last = null; double lastSim = 0, lastArrive = 0; var pending = new List<HapticEvent>();
            source.Start(); reloader.Start();
            string jit = rtOpt.Prejit ? RtWarmup.Prejit(typeof(Program).Assembly) : "";
            using (var rt = new RtWaiter(rtOpt, sw))
            {
                stats = new LoopStats(stages) { Mode = rtOpt + (rt.Notes != "" ? "; " + rt.Notes : "") + (jit != "" ? "; " + jit : "") };
                if (rtOpt.OwnOutputThreads) foreach (var r in p.Renderers) (r as IRealTimeRenderer)?.StartRealTime();
                const double Period = 0.004;
                double t0 = rt.Now; long k = 0;
                while (!cts.IsCancellationRequested && (secs <= 0 || rt.Now < secs))
                {
                    // deadline k on an absolute schedule (no drift); more than 100 ms behind (suspend, debugger): resync
                    double due = t0 + k * Period;
                    if (rt.Now - due > 0.1) { k = (long)Math.Ceiling((rt.Now - t0) / Period); due = t0 + k * Period; }
                    k++;
                    double slack = (due - rt.Now) * 1000.0;
                    rt.WaitUntil(due);
                    stats.Update(slack, (rt.Now - due) * 1000.0);

                    // drain: keep the newest frame, accumulate events
                    while (queue.TryDequeue(out var lf))
                    {
                        last = lf.D; pending.AddRange(lf.D.Events); lastSim = lf.Sim; lastArrive = lf.Arrive; frames++;
                    }
                    stats.Mark(0);
                    if (last != null)
                    {
                        double now = sw.Elapsed.TotalSeconds;
                        double t = lastSim + Math.Min(0.25, now - lastArrive);
                        var s = last.Sample.Clone(); s.SinceTick = now - lastArrive;
                        if (pending.Count == 0) { s.Shift = 0; s.FxFired = null; }
                        var step = p.Core.Step(new Derive.Result { Sample = s, State = last.State, Vars = last.Vars }, pending, t);
                        stats.Mark(1);
                        for (int i = 0; i < p.Renderers.Count; i++) { p.Renderers[i].Render(step); stats.Mark(2 + i); }
                        pending = new List<HapticEvent>();
                        if (s.Shift != 0 || last.Sample.FxFired != null) { last.Sample.Shift = 0; last.Sample.FxFired = null; }
                    }
                    var ns = Interlocked.Exchange(ref reloaded, null);
                    if (ns != null) { p.Core.Load(ns); Console.WriteLine("reloaded effects"); }
                    stats.Mark(2 + p.Renderers.Count);
                }
                foreach (var r in p.Renderers) (r as IRealTimeRenderer)?.StopRealTime();
            }
            cts.Cancel();
            source.Join(500); reloader.Join(1500);
            foreach (var r in p.Renderers) r.Close();
            var report = stats.Report();
            Console.WriteLine("live: {0} frames; loop {1}", frames, report.Replace(Environment.NewLine, Environment.NewLine + "  ").TrimEnd());
            File.WriteAllText(Path.Combine(outDir, "live.deadlines.txt"), report);
            foreach (var r in p.Renderers) Console.WriteLine("  " + r.Summary());
            return 0;
        }

        /// <summary>
        /// haptics play: a recording (or the scripted session) as UDP datagrams to 127.0.0.1, each at its recorded time on the
        /// same high-resolution waiter the loops use, so a `live` test sees the real telemetry rate. Loopback only.
        /// </summary>
        static int Play(string input, Args a)
        {
            if (input == null) throw new ArgumentException("play needs a .i76rec or synthetic");
            int port = (int)a.Num("--port", 7676), reps = Math.Max(1, (int)a.Num("--repeats", 1));
            var recs = input.StartsWith("synthetic", StringComparison.OrdinalIgnoreCase)
                ? Synthetic.Session(input.EndsWith(":v2") ? 2 : 3, 60, reps).ToList()
                : RecordingReader.Load(input).Records;
            if (recs.Count == 0) { Console.WriteLine("play: nothing to send"); return 1; }
            var cts = new CancellationTokenSource(); Console.CancelKeyPress += (o, e) => { e.Cancel = true; cts.Cancel(); };
            var ep = new System.Net.IPEndPoint(System.Net.IPAddress.Loopback, port);
            var late = new ChunkedDoubles(); int sent = 0;
            using (var u = new System.Net.Sockets.UdpClient(System.Net.Sockets.AddressFamily.InterNetwork))
            using (var rt = new RtWaiter(new RtOptions()))
            {
                double t0 = recs[0].t;
                foreach (var (t, d) in recs)
                {
                    if (cts.IsCancellationRequested) break;
                    double due = t - t0;
                    rt.WaitUntil(due);
                    late.Add((rt.Now - due) * 1000.0);
                    u.Send(d, d.Length, ep); sent++;
                }
            }
            Console.WriteLine("play: {0} datagrams to 127.0.0.1:{1} over {2:0.0} s ({3:0.0} /s); sender pacing {4}", sent, port,
                recs[Math.Min(sent, recs.Count) - 1].t - recs[0].t, sent / Math.Max(1e-9, recs[Math.Min(sent, recs.Count) - 1].t - recs[0].t), LoopStats.Histogram(late.ToArray()));
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
