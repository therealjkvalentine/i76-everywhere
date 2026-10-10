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
                FrameIn cur = null; double coreT = double.NaN, lastSim = double.NaN, simAnchor = 0, stall = 0;
                double hostStart = double.NaN;
                foreach (var next in frames.Concat(new FrameIn[] { null }))
                {
                    if (ct.IsCancellationRequested) break;
                    if (cur == null) { cur = next; continue; }
                    Frames++;
                    // core time: the engine clock while it advances; host time while it is stalled (pause / menu)
                    bool advanced = double.IsNaN(lastSim) || cur.SimT > lastSim;
                    if (advanced) { simAnchor = cur.SimT; stall = 0; lastSim = cur.SimT; }
                    double span;
                    if (next == null) span = CoreHz > 0 ? 1.0 / CoreHz : 0.0;
                    else if (next.SimT > cur.SimT) span = next.SimT - cur.SimT;
                    else span = Math.Max(0.0, next.HostT - cur.HostT);
                    span = Math.Min(span, 0.25);
                    double t0 = advanced ? cur.SimT : (double.IsNaN(coreT) ? cur.SimT : coreT + (CoreHz > 0 ? 1.0 / CoreHz : 0.016));
                    if (!double.IsNaN(coreT) && t0 <= coreT) t0 = coreT + 1e-6;
                    int n = CoreHz > 0 ? Math.Max(1, (int)Math.Round(span * CoreHz)) : 1;
                    if (double.IsNaN(hostStart)) hostStart = cur.HostT;
                    for (int k = 0; k < n; k++)
                    {
                        double t = CoreHz > 0 ? t0 + k / (double)CoreHz : t0;
                        if (RealTime)
                        {
                            double due = (cur.HostT - hostStart) + (t - t0);
                            while (sw.Elapsed.TotalSeconds < due - 0.0015) Thread.Sleep(1);
                            while (sw.Elapsed.TotalSeconds < due) Thread.SpinWait(50);
                            LatenessMs.Add((sw.Elapsed.TotalSeconds - due) * 1000.0);
                        }
                        Derive.Result d = cur.D;
                        IList<HapticEvent> evs = cur.Events;
                        if (k > 0)
                        {
                            var s = d.Sample.Clone(); s.Shift = s.Shift.HasValue ? 0 : (int?)null; s.FxFired = null;
                            d = new Derive.Result { Sample = s, State = d.State, Vars = d.Vars };
                            evs = null;
                        }
                        if (!advanced || k > 0) { var s2 = d.Sample.Clone(); s2.SinceTick = stall + (t - t0); d = new Derive.Result { Sample = s2, State = d.State, Vars = d.Vars, Events = d.Events }; }
                        var step = Core.Step(d, evs ?? new List<HapticEvent>(), t);
                        step.NewFrame = k == 0;
                        Emit(step);
                        coreT = t;
                    }
                    if (!advanced) stall += span;
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
