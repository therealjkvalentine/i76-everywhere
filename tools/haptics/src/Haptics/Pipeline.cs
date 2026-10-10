using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using Haptics.Core;
using Haptics.Renderers;
using Haptics.Transport;

namespace Haptics
{
    /// <summary>One input frame for the pipeline, whatever the source.</summary>
    public sealed class FrameIn
    {
        public double HostT;            // seconds, source clock (recording timestamp / synthetic schedule / arrival)
        public double SimT;             // engine sim_time
        public Derive.Result D;
        public List<HapticEvent> Events => D.Events;
    }

    /// <summary>Sources -> FrameIn.</summary>
    public static class Sources
    {
        /// <summary>Datagrams (recording / synthetic / UDP / shm) through the decoder and Derive.</summary>
        public static IEnumerable<FrameIn> FromDatagrams(IEnumerable<(double t, byte[] data)> dgs, Derive derive, TelCodec codec, Action<string> warn = null)
        {
            string lastWarn = null;
            foreach (var (t, data) in dgs)
            {
                var dg = codec.Decode(data);
                if (dg == null || dg.Frame == null) { if (dg?.Warning != null && dg.Warning != lastWarn) warn?.Invoke(lastWarn = dg.Warning); continue; }
                if (dg.Warning != null && dg.Warning != lastWarn) warn?.Invoke(lastWarn = dg.Warning);
                var r = derive.Step(dg.Frame, dg.Events, 0.0);
                yield return new FrameIn { HostT = t, SimT = dg.Frame.SimTime, D = r };
            }
        }

        /// <summary>
        /// A legacy capture (tools/ffb drive*.csv: t, speed, steer, throttle, longG, yaw, jolt, vy ...) rebuilt as
        /// ffb-replay.ps1's Build-Samples does (full capture), slip from Tel-Slip.
        /// </summary>
        public static IEnumerable<FrameIn> FromDriveCsv(string path)
        {
            var g = CsvTable.Load(path);
            bool full = g.Has("longG") && g.Has("jolt");
            double prevT = double.NaN, prevSp = 0, longG = 0;
            for (int r = 0; r < g.Rows.Count; r++)
            {
                double t = g.D(r, "t"), sp = g.D(r, "speed"), st = g.D(r, "steer"), yw = g.D(r, "yaw");
                if (!double.IsNaN(prevT)) { double dt = t - prevT; if (dt > 0.005 && dt < 1.0) longG = ((sp - prevSp) / dt) / 9.81; }
                prevT = t; prevSp = sp;
                double slide = g.Has("slide") ? g.D(r, "slide") : 0;
                var slip = Derive.TelSlip(sp, st, yw, slide);
                var s = new Sample
                {
                    T = t, Speed = sp, Steer = st, Throttle = full ? g.D(r, "throttle") : 0, YawRate = yw,
                    Vy = g.Has("vy") ? g.D(r, "vy") : 0, LongG = full ? g.D(r, "longG") : longG, LatG = (yw * sp) / 9.81,
                    Understeer = slip.under, Oversteer = slip.over, Jolt = full ? g.D(r, "jolt") : 0,
                    AngVelX = g.Has("angVelX") ? g.D(r, "angVelX") : 0, AngVelZ = g.Has("angVelZ") ? g.D(r, "angVelZ") : 0,
                };
                yield return new FrameIn { HostT = t, SimT = t, D = Derive.FromSample(s) };
            }
        }
    }

    /// <summary>
    /// The host loop. Replay: each input frame is followed by core updates at CoreHz until the next frame's time
    /// (deterministic: a replay at max speed produces the same files as a real-time one). Events and the one-shot
    /// sample fields (Shift, FxFired) go to the first update of their frame only. Real time: the same schedule paced
    /// by a 1 ms timer, with every update's lateness logged (B4 histogram).
    /// </summary>
    public sealed class Pipeline
    {
        public HapticCore Core;
        public readonly List<IRenderer> Renderers = new List<IRenderer>();
        public int CoreHz = 250;            // 0 = one update per input frame
        public bool RealTime;
        public long Updates, Frames;
        public readonly List<double> LatenessMs = new List<double>();
        public Action<CoreStep> OnStep;

        [DllImport("winmm.dll")] static extern uint timeBeginPeriod(uint p);
        [DllImport("winmm.dll")] static extern uint timeEndPeriod(uint p);

        void Emit(CoreStep s) { Updates++; foreach (var r in Renderers) r.Render(s); OnStep?.Invoke(s); }

        public void Run(IEnumerable<FrameIn> frames, CancellationToken ct = default)
        {
            var sw = Stopwatch.StartNew();
            if (RealTime) timeBeginPeriod(1);
            try
            {
                // Core time = engine sim time + every stalled (paused / menu) interval measured on the source clock,
                // so it is monotonic and equals sim time in normal play. Grid mode: updates at k / CoreHz on that axis;
                // a frame shorter than one grid step hands its events / one-shots to the next update (never lost).
                FrameIn cur = null; double lastSim = double.NaN, offset = 0, lastEnd = double.NaN, lastAdvStart = 0;
                double grid0 = double.NaN; long k = 0; double rt0 = double.NaN;
                var pendEv = new List<HapticEvent>(); int? pendShift = null; List<FxFired> pendFx = null;
                foreach (var next in frames.Concat(new FrameIn[] { null }))
                {
                    if (ct.IsCancellationRequested) break;
                    if (cur == null) { cur = next; continue; }
                    Frames++;
                    bool advanced = double.IsNaN(lastSim) || cur.SimT > lastSim;
                    double span;
                    if (next == null) span = CoreHz > 0 ? 1.0 / CoreHz : 0.0;
                    else if (next.SimT > cur.SimT) span = next.SimT - cur.SimT;
                    else span = Math.Max(0.0, next.HostT - cur.HostT);
                    span = Math.Min(span, 0.25);
                    double start = advanced || double.IsNaN(lastEnd) ? cur.SimT + offset : lastEnd;
                    if (!double.IsNaN(lastEnd) && start < lastEnd) start = lastEnd;
                    double end = start + span;
                    if (advanced) { lastSim = cur.SimT; lastAdvStart = start; } else offset += span;
                    lastEnd = end;

                    pendEv.AddRange(cur.Events);
                    if (cur.D.Sample.Shift.HasValue && cur.D.Sample.Shift.Value != 0) pendShift = cur.D.Sample.Shift;
                    if (cur.D.Sample.FxFired != null) (pendFx ?? (pendFx = new List<FxFired>())).AddRange(cur.D.Sample.FxFired);

                    var times = new List<double>();
                    if (CoreHz <= 0) times.Add(start);
                    else
                    {
                        if (double.IsNaN(grid0)) grid0 = start;
                        // a gap in the input (telemetry silent for longer than the 0.25 s span cap): resume the grid at the
                        // new frame's time instead of back-filling the gap with the new frame's state (the motion renderer
                        // must see the gap to ramp to neutral). Contiguous input never takes this branch.
                        long kmin = (long)Math.Ceiling((start - grid0) * CoreHz - 1e-6);
                        if (kmin > k) k = kmin;
                        while (true) { double t = grid0 + k / (double)CoreHz; if (t >= end - 1e-9 && !(next == null && times.Count == 0)) break; times.Add(t); k++; if (next == null) break; }
                    }
                    for (int j = 0; j < times.Count; j++)
                    {
                        double t = times[j];
                        if (RealTime)
                        {
                            if (double.IsNaN(rt0)) rt0 = t;
                            double due = t - rt0;
                            while (sw.Elapsed.TotalSeconds < due - 0.0015) Thread.Sleep(1);
                            while (sw.Elapsed.TotalSeconds < due) Thread.SpinWait(50);
                            LatenessMs.Add((sw.Elapsed.TotalSeconds - due) * 1000.0);
                        }
                        var s = cur.D.Sample;
                        if (CoreHz > 0 || !advanced)
                        {
                            s = s.Clone();
                            s.Shift = pendShift ?? (s.Shift.HasValue ? 0 : (int?)null);
                            s.FxFired = pendFx;
                            s.SinceTick = Math.Max(0, t - lastAdvStart);
                        }
                        var d = new Derive.Result { Sample = s, State = cur.D.State, Vars = cur.D.Vars };
                        var evs = pendEv; pendEv = new List<HapticEvent>(); pendShift = null; pendFx = null;
                        var step = Core.Step(d, evs, t);
                        step.NewFrame = j == 0;
                        Emit(step);
                    }
                    cur = next;
                }
            }
            finally { if (RealTime) timeEndPeriod(1); }
        }

        public string LatenessHistogram()
        {
            if (LatenessMs.Count == 0) return "(no real-time samples)";
            var a = LatenessMs.OrderBy(x => x).ToArray();
            double P(double p) => a[Math.Min(a.Length - 1, (int)(a.Length * p))];
            var bins = new[] { 1.0, 2, 4, 8, 16, double.MaxValue };
            var sb = new System.Text.StringBuilder();
            sb.AppendFormat(CultureInfo.InvariantCulture, "{0} updates: p50 {1:0.00} ms, p99 {2:0.00} ms, p99.9 {3:0.00} ms, max {4:0.00} ms; ", a.Length, P(0.5), P(0.99), P(0.999), a[a.Length - 1]);
            double lo = double.MinValue;
            foreach (var b in bins)
            {
                int c = a.Count(x => x > lo && x <= b);
                sb.AppendFormat(CultureInfo.InvariantCulture, "{0}{1}: {2}  ", lo == double.MinValue ? "<=" : ">" + lo + "..", b == double.MaxValue ? "inf" : b.ToString(CultureInfo.InvariantCulture), c);
                lo = b;
            }
            sb.AppendFormat("missed (>8 ms): {0}", a.Count(x => x > 8));
            return sb.ToString();
        }
    }
}
