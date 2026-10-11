using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text.Json.Nodes;
using System.Threading;
using Haptics.Core;
using Haptics.Core.Motion;
using Haptics.Transport;

namespace Haptics.Renderers
{
    /// <summary>
    /// Motion.Udp: the motion renderer (docs/MOTION-OUTPUT.md). Runs MotionCore on CoreStep.State / Events and writes every
    /// output tick in each enabled target's wire format (motion/targets.json): LFS OutSim classic / OutSimPack2 (+ OutGauge),
    /// Forza Sled / Dash, i76motion.
    ///
    /// File sink (default): one packet log per stream, &lt;tag&gt;.&lt;target&gt;.&lt;format&gt;.i76rec (the .i76rec container with the
    /// motion datagrams as records, timestamped on the motion clock), plus &lt;tag&gt;.motionout.csv. Nothing is sent.
    /// UDP: only when the run allows it (--live, or the motion command's --send) and only to loopback unless a target sets
    /// allow_remote. Sending is to third-party SOFTWARE; no actuator is driven from this host (Actuator.Direct is M6, not built).
    ///
    /// Output config keys (rig "outputs": {"motion_udp": {...}}; the motion command overrides them):
    ///   targets_file (default motion/targets.json), select ("flypt,native"; default = the file's enabled targets),
    ///   send (bool), output_hz, resample, log (bool, default true), csv (bool, default true).
    /// </summary>
    public sealed class MotionUdpRenderer : IRenderer, IRealTimeRenderer
    {
        public string Type => "Motion.Udp";
        public MotionCore Core;
        public MotionParams Params;
        public readonly List<TargetRt> Targets = new List<TargetRt>();
        public bool Send, HostClock;
        public readonly List<MotionFrame> Captured = new List<MotionFrame>();   // tests: keep every frame when CaptureFrames
        public bool CaptureFrames;
        public Action<MotionFrame> OnFrame;
        Stopwatch _sw; double _clock0 = double.NaN;
        StreamWriter _csv; string _csvPath;
        TextWriter _log;
        double _lastClock;

        public sealed class TargetRt
        {
            public MotionTarget Def;
            public Limiter Lim;
            public readonly List<(string kind, int port, RecordingWriter log, string path)> Streams = new List<(string, int, RecordingWriter, string)>();
            public UdpClient Udp;
            public long Packets, Bytes, SendErrors;
            public string LastError;
        }

        public void Open(RendererContext ctx)
        {
            _log = ctx.Log ?? Console.Out;
            var cfg = ctx.Config ?? new JsonObject();
            string root = Effects.EffectSet.DefaultRoot();
            string tf = Effects.EffectDef.Str(cfg, "targets_file");
            if (tf != null && !Path.IsPathRooted(tf)) tf = Path.Combine(root, tf);
            Params = MotionParams.Load(ctx.Rig?.Json?["motion"] as JsonObject, tf);
            if (cfg["output_hz"] != null) Params.OutputHz = Effects.EffectDef.Num(cfg, "output_hz", Params.OutputHz);
            if (cfg["resample"] != null) Params.Resample = Effects.EffectDef.Str(cfg, "resample");
            if (cfg["startup_neutral_s"] != null) Params.StartupNeutralS = Effects.EffectDef.Num(cfg, "startup_neutral_s", Params.StartupNeutralS);
            bool B(string k, bool d) => cfg[k] is JsonValue v && v.TryGetValue<bool>(out var b) ? b : d;
            Send = ctx.Live || B("send", false);
            HostClock = ctx.HostClock;
            var sel = (Effects.EffectDef.Str(cfg, "select") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries).Select(x => x.Trim()).ToList();
            IEnumerable<MotionTarget> chosen;
            if (sel.Count > 0)
            {
                var missing = sel.Where(n => !Params.Targets.Any(t => string.Equals(t.Name, n, StringComparison.OrdinalIgnoreCase))).ToList();
                if (missing.Count > 0) throw new ArgumentException("no motion target named " + string.Join(", ", missing) + " in " + Params.TargetsFile + " (known: " + string.Join(", ", Params.Targets.Select(t => t.Name)) + ")");
                chosen = Params.Targets.Where(t => sel.Contains(t.Name, StringComparer.OrdinalIgnoreCase));
            }
            else chosen = Params.Targets.Where(t => t.Enabled);
            var active = chosen.ToList();
            var lint = Params.Lint(active);
            foreach (var l in lint) _log.WriteLine("  motion lint: " + l);
            if (lint.Any(l => l.Error)) throw new InvalidOperationException("motion config has errors (see 'motion lint' above)");
            Core = new MotionCore(Params);

            bool log = B("log", true) && ctx.OutDir != null;
            if (log) Directory.CreateDirectory(ctx.OutDir);
            foreach (var t in active)
            {
                var rt = new TargetRt { Def = t, Lim = new Limiter(Params, t.Clamp || Params.ClampUdp, t.Slew) };
                foreach (var (kind, port) in t.Streams())
                {
                    RecordingWriter w = null; string path = null;
                    if (log)
                    {
                        path = Path.Combine(ctx.OutDir, ctx.Tag + "." + t.Name + "." + kind + ".i76rec");
                        var meta = new JsonObject
                        {
                            ["source"] = "haptics Motion.Udp", ["payload"] = "motion", ["target"] = t.Name, ["format"] = kind, ["host"] = t.Host, ["port"] = port,
                            ["id"] = kind == "outgauge" ? t.GaugeId : t.Id, ["frame"] = t.Frame, ["output_hz"] = Params.OutputHz, ["resample"] = Params.Resample,
                            ["accel_source"] = Params.AccelSource, ["clock"] = HostClock ? "host" : "core (engine sim time)",
                        };
                        w = new RecordingWriter(path, meta.ToJsonString());
                    }
                    rt.Streams.Add((kind, port, w, path));
                    if (path != null) _logs.Add((t.Name, kind, path));
                }
                if (Send) rt.Udp = new UdpClient(AddressFamily.InterNetwork);
                Targets.Add(rt);
            }
            if (B("csv", true) && ctx.OutDir != null)
            {
                _csvPath = Path.Combine(ctx.OutDir, ctx.Tag + ".motionout.csv");
                _csv = new StreamWriter(_csvPath);
                _csv.WriteLine("t,seq,status,gain,surge,sway,heave,roll_rate,pitch_rate,yaw_rate,roll,pitch,heading,speed,rpm,gear,throttle,brake,steer,cue_surge,cue_sway,cue_heave,vel_right,vel_up,vel_fwd,texture");
            }
            _log.WriteLine("  Motion.Udp: {0} target(s) [{1}], {2} Hz {3}, accel {4}, {5}", Targets.Count, string.Join("; ", Targets.Select(x => x.Def.ToString())),
                Params.OutputHz, Params.Resample, Params.AccelSource, Send ? "SENDING UDP" : "files only (no UDP)");
        }

        // the wall clock behind the motion clock (live, or a real-time run): started at the first Render, motion clock =
        // _clock0 + elapsed. Offline replays never start it.
        bool WallMapped => HostClock || _rtThread != null;
        double WallClock() => _sw == null ? double.NaN : _clock0 + _sw.Elapsed.TotalSeconds;

        double Clock(CoreStep step)
        {
            if (_sw == null && WallMapped) { _sw = Stopwatch.StartNew(); _clock0 = step.T; }
            if (!HostClock) return step.T;
            return _clock0 + _sw.Elapsed.TotalSeconds;
        }

        public void Render(CoreStep step)
        {
            if (Core == null) return;
            if (_rtThread != null)
            {
                // real time: the core update only feeds; the output thread sends each tick at its own time (OutputLoop)
                lock (_lk) { double cc = Clock(step); _lastClock = Math.Max(_lastClock, cc); Core.Feed(step.State, step.Events, cc); }
                return;
            }
            double c = Clock(step); _lastClock = c;
            // ticks before this step's time belong to the previous state (after a telemetry gap the replay clock jumps:
            // those ticks must see the stale stream and ramp to neutral, not the new frame)
            foreach (var f in Core.Pump(c - 1e-7)) { Timing(f); Emit(f); }
            Core.Feed(step.State, step.Events, c);
            foreach (var f in Core.Pump(c)) { Timing(f); Emit(f); }
        }

        // ---- real-time output schedule (IRealTimeRenderer): one boosted thread, a tick every 1 / output_hz on the wall clock,
        // independent of the core grid (which sent at 8 / 12 ms spacing when 100 Hz ticks rode on 250 Hz updates) ----
        readonly object _lk = new object();
        Thread _rtThread; volatile bool _rtRun; bool _everRt;
        public RtOptions Rt = new RtOptions();
        readonly ChunkedDoubles _sendGap = new ChunkedDoubles(), _sendLate = new ChunkedDoubles();
        long _lastSendTs;

        public void StartRealTime()
        {
            if (Core == null || _rtThread != null) return;
            _rtRun = true; _everRt = true;
            _rtThread = new Thread(OutputLoop) { IsBackground = true, Name = "Motion.Udp output" };
            _rtThread.Start();
        }

        public void StopRealTime()
        {
            var th = _rtThread; if (th == null) return;
            _rtRun = false; th.Join(2000);
            _rtThread = null;
        }

        void OutputLoop()
        {
            // the GC latency mode is process-wide: the loop that owns the run sets and restores it, not this thread
            using (var w = new RtWaiter(new RtOptions { HiResTimer = Rt.HiResTimer, Boost = Rt.Boost, SpinMs = Rt.SpinMs, LowLatencyGc = false }))
            {
                var buf = new List<MotionFrame>();
                while (_rtRun)
                {
                    double next = double.NaN, now = 0;
                    lock (_lk) if (_sw != null) { next = Core.NextTick - _clock0; now = _sw.Elapsed.TotalSeconds; }   // next tick on the wall clock
                    if (double.IsNaN(next)) { w.WaitUntil(w.Now + 0.001); continue; }
                    if (next > now + 0.25) next = now + 0.001;                   // no tick due soon (before the first state): poll
                    w.WaitUntil(w.Now + (next - now));                           // the waiter's stopwatch and _sw differ by a constant
                    buf.Clear();
                    lock (_lk) { double c = WallClock(); _lastClock = Math.Max(_lastClock, c); buf.AddRange(Core.Pump(c)); }
                    foreach (var f in buf) { Timing(f); Emit(f); }
                }
            }
        }

        void Timing(MotionFrame f)
        {
            if (!WallMapped || _sw == null) return;
            long ts = Stopwatch.GetTimestamp();
            if (_lastSendTs != 0) _sendGap.Add((ts - _lastSendTs) * 1000.0 / Stopwatch.Frequency);
            _lastSendTs = ts;
            _sendLate.Add((_sw.Elapsed.TotalSeconds - (f.Clock - _clock0)) * 1000.0);
        }

        /// <summary>Wall-clock gaps between consecutive output ticks (ms), live / real-time runs only.</summary>
        public double[] SendGapsMs => _sendGap.ToArray();

        /// <summary>Wall-clock send timing of the output ticks (live / real-time runs): gaps between consecutive ticks, each tick's lateness.</summary>
        public string SendTiming()
        {
            if (_sendGap.Count == 0) return null;
            var g = _sendGap.ToArray(); Array.Sort(g);
            double per = 1000.0 / Math.Max(1.0, Params.OutputHz);
            double P(double[] a, double p) => a[Math.Min(a.Length - 1, (int)(a.Length * p))];
            int off = g.Count(x => Math.Abs(x - per) > 1.0);
            return string.Format(CultureInfo.InvariantCulture, "send timing ({0}): {1} gaps p1 {2:0.00} / p50 {3:0.00} / p99 {4:0.00} / max {5:0.00} ms, {6} more than 1 ms off the {7:0.##} ms period; tick lateness {8}",
                _everRt ? "own output thread" : "sent from the core update", g.Length, P(g, 0.01), P(g, 0.5), P(g, 0.99), g[g.Length - 1], off, per, LoopStats.Histogram(_sendLate.ToArray()));
        }

        void Emit(MotionFrame f)
        {
            if (CaptureFrames) Captured.Add(f);
            OnFrame?.Invoke(f);
            foreach (var rt in Targets)
            {
                var g = rt.Lim.Apply(f);
                foreach (var (kind, port, log, _) in rt.Streams)
                {
                    var pkt = Encode(kind, g, rt.Def, Params);
                    if (rt.Udp != null)
                    {
                        try { rt.Udp.Send(pkt, pkt.Length, rt.Def.Host, port); }
                        catch (Exception ex) { rt.SendErrors++; rt.LastError = ex.Message; }
                    }
                    log?.Add(f.Clock, pkt);
                    rt.Packets++; rt.Bytes += pkt.Length;
                }
            }
            if (_csv != null)
            {
                var s = f.S;
                _csv.WriteLine(string.Format(CultureInfo.InvariantCulture,
                    "{0:0.0000},{1},{2},{3:0.###},{4:0.####},{5:0.####},{6:0.####},{7:0.#####},{8:0.#####},{9:0.#####},{10:0.######},{11:0.######},{12:0.######},{13:0.###},{14:0},{15},{16:0.###},{17:0.###},{18:0.###},{19:0.####},{20:0.####},{21:0.####},{22:0.###},{23:0.###},{24:0.###},{25:0.###}",
                    f.Clock, f.Seq, f.Status, f.Gain, s.Surge, s.Sway, s.Heave, s.RollRate, s.PitchRate, s.YawRate, s.Roll, s.Pitch, s.Heading, s.Speed, s.Rpm, s.Gear - 1,
                    s.Throttle, s.Brake, s.Steer, f.CueSurge, f.CueSway, f.CueHeave, s.VelRight, s.VelUp, s.VelFwd, s.Texture));
            }
        }

        public static byte[] Encode(string kind, MotionFrame f, MotionTarget t, MotionParams p)
        {
            switch (kind)
            {
                case "lfs-classic": return OutSimPacket.Classic(f, t?.Id ?? 0, t?.Frame ?? "world");
                case "lfs-pack2": return OutSimPacket.Pack2(f, t?.Id ?? 0, t?.Frame ?? "world", p);
                case "outgauge": return OutSimPacket.OutGauge(f, t == null ? 0 : (t.Format == "outgauge" ? t.Id : t.GaugeId));
                case "forza-sled": return ForzaPacket.Build(f, false, p);
                case "forza-dash": return ForzaPacket.Build(f, true, p);
                case "i76motion": return I76MotionPacket.Build(f);
            }
            throw new ArgumentException("unknown motion format " + kind);
        }

        public void Close()
        {
            if (Core == null) return;
            StopRealTime();
            if (Core.PhysicsStates > 0) Emit(Core.ShutdownFrame(_lastClock + Core.Period));
            foreach (var rt in Targets)
            {
                foreach (var s in rt.Streams) s.log?.Dispose();
                rt.Streams.Clear();
                rt.Udp?.Dispose(); rt.Udp = null;
            }
            _csv?.Dispose(); _csv = null;
            _summary = BuildSummary();
            Core = null;
        }
        string _summary;

        string BuildSummary()
        {
            var c = Core;
            var sb = new System.Text.StringBuilder();
            sb.AppendFormat(CultureInfo.InvariantCulture, "Motion.Udp: {0} ticks at {1} Hz ({2} neutral), {3} physics states ({4} repeated poses skipped), cues {5}{6}; {7}",
                c.Ticks, Params.OutputHz, c.NeutralTicks, c.PhysicsStates, c.Derive.Repeats,
                c.Cues.ByKind.Count == 0 ? "none" : string.Join(" ", c.Cues.ByKind.Select(kv => kv.Key + ":" + kv.Value)),
                c.Cues.Dropped > 0 ? " (" + c.Cues.Dropped + " dropped by min_gap)" : "", Send ? "sent over UDP" : "not sent (files only)");
            foreach (var rt in Targets)
                sb.AppendFormat(CultureInfo.InvariantCulture, "{0}    {1}: {2} packets, {3} B{4}{5}", Environment.NewLine, rt.Def, rt.Packets, rt.Bytes,
                    rt.Lim.Active ? ", limiter clamped " + rt.Lim.Clamped + " / slewed " + rt.Lim.Slewed : "",
                    rt.SendErrors > 0 ? ", " + rt.SendErrors + " send errors (" + rt.LastError + ")" : "");
            var st = SendTiming(); if (st != null) sb.Append(Environment.NewLine + "    " + st);
            if (_csvPath != null) sb.Append(Environment.NewLine + "    csv -> " + _csvPath);
            return sb.ToString();
        }

        /// <summary>The packet logs written (target, format, path).</summary>
        public IEnumerable<(string target, string kind, string path)> Logs => _logs;
        readonly List<(string, string, string)> _logs = new List<(string, string, string)>();

        public string Summary() => _summary ?? (Core != null ? BuildSummary() : "Motion.Udp: not opened");
        public void Dispose() => Close();
    }
}
