using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Runtime;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace Haptics
{
    /// <summary>
    /// How a real-time loop waits for its next deadline and what it does to its thread. Chosen per run:
    /// <c>--rt hires</c> (default) or <c>--rt legacy</c> (the original Thread.Sleep(1) + spin, kept for A/B measurement),
    /// or I76_RT=legacy|hires. See README "B4 real-time loop".
    /// </summary>
    public sealed class RtOptions
    {
        /// <summary>true: high-resolution waitable timer to ~SpinMs before the deadline, then spin. false: Thread.Sleep(1) loop.</summary>
        public bool HiResTimer = true;
        /// <summary>Thread priority Highest + MMCSS "Games" on the timing thread.</summary>
        public bool Boost = true;
        /// <summary>GCSettings.LatencyMode = SustainedLowLatency for the run (no blocking gen2 compaction while it lasts).</summary>
        public bool LowLatencyGc = true;
        /// <summary>The last stretch before a deadline that is spun rather than slept (ms).</summary>
        public double SpinMs = 0.6;
        /// <summary>JIT the host's methods before the clock starts (RtWarmup).</summary>
        public bool Prejit = true;
        /// <summary>Renderers with their own schedule (IRealTimeRenderer: Motion.Udp at output_hz) get their own output thread.
        /// false = the old behaviour, ticks sent from whichever core update crosses them.</summary>
        public bool OwnOutputThreads = true;

        public static RtOptions Legacy() => new RtOptions { HiResTimer = false, Boost = false, LowLatencyGc = false, Prejit = false, OwnOutputThreads = false, SpinMs = 1.5 };

        /// <summary>"legacy" | "hires" (default), from the argument or I76_RT.</summary>
        public static RtOptions Parse(string s)
        {
            s = s ?? Environment.GetEnvironmentVariable("I76_RT") ?? "hires";
            switch (s.Trim().ToLowerInvariant())
            {
                case "legacy": return Legacy();
                case "hires": case "": return new RtOptions();
                default: throw new ArgumentException("--rt must be legacy or hires, not '" + s + "'");
            }
        }

        public override string ToString() => HiResTimer || Boost || LowLatencyGc
            ? string.Format(CultureInfo.InvariantCulture, "hires (waitable timer{0}, spin {1} ms{2}{3})", HiResTimer ? "" : " OFF", SpinMs,
                Boost ? ", priority Highest + MMCSS Games" : "", LowLatencyGc ? ", GC SustainedLowLatency" : "") + (OwnOutputThreads ? ", motion on its own output thread" : "")
            : "legacy (Thread.Sleep(1) + spin 1.5 ms)";
    }

    /// <summary>
    /// The deadline waiter for one timing thread: timeBeginPeriod(1), a CREATE_WAITABLE_TIMER_HIGH_RESOLUTION timer
    /// (Windows 10 1803+; falls back to Sleep(1) without it) to SpinMs before the deadline, then a spin on the stopwatch.
    /// Create, use and dispose it on the same thread (Enter boosts that thread, Dispose restores it).
    /// </summary>
    public sealed class RtWaiter : IDisposable
    {
        [DllImport("winmm.dll")] static extern uint timeBeginPeriod(uint p);
        [DllImport("winmm.dll")] static extern uint timeEndPeriod(uint p);
        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] static extern IntPtr CreateWaitableTimerExW(IntPtr attr, string name, uint flags, uint access);
        [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetWaitableTimer(IntPtr h, ref long due, int period, IntPtr cb, IntPtr arg, bool resume);
        [DllImport("kernel32.dll", SetLastError = true)] static extern uint WaitForSingleObject(IntPtr h, uint ms);
        [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr h);
        [DllImport("avrt.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr AvSetMmThreadCharacteristicsW(string task, ref uint index);
        [DllImport("avrt.dll", SetLastError = true)] static extern bool AvRevertMmThreadCharacteristics(IntPtr h);
        const uint CREATE_WAITABLE_TIMER_HIGH_RESOLUTION = 0x2, TIMER_ALL_ACCESS = 0x1F0003;

        public readonly RtOptions Opt;
        public readonly Stopwatch Sw;
        IntPtr _timer, _mmcss;
        ThreadPriority _oldPrio;
        GCLatencyMode _oldGc;
        public string Notes = "";

        public RtWaiter(RtOptions opt, Stopwatch sw = null)
        {
            Opt = opt ?? new RtOptions();
            Sw = sw ?? Stopwatch.StartNew();
            timeBeginPeriod(1);
            var notes = new List<string>();
            if (Opt.HiResTimer)
            {
                _timer = CreateWaitableTimerExW(IntPtr.Zero, null, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
                if (_timer == IntPtr.Zero) notes.Add("high-resolution waitable timer unavailable (error " + Marshal.GetLastWin32Error() + "), Sleep(1) instead");
            }
            _oldPrio = Thread.CurrentThread.Priority;
            if (Opt.Boost)
            {
                Thread.CurrentThread.Priority = ThreadPriority.Highest;
                try { uint idx = 0; _mmcss = AvSetMmThreadCharacteristicsW("Games", ref idx); if (_mmcss == IntPtr.Zero) notes.Add("MMCSS refused (error " + Marshal.GetLastWin32Error() + ")"); }
                catch (DllNotFoundException) { notes.Add("no avrt.dll"); }
            }
            _oldGc = GCSettings.LatencyMode;
            if (Opt.LowLatencyGc) GCSettings.LatencyMode = GCLatencyMode.SustainedLowLatency;
            Notes = string.Join("; ", notes);
        }

        public double Now => Sw.Elapsed.TotalSeconds;

        /// <summary>Blocks until the stopwatch reaches <paramref name="due"/> (seconds). Returns at once when it already has.</summary>
        public void WaitUntil(double due)
        {
            if (Opt.HiResTimer && _timer != IntPtr.Zero)
            {
                double sleepS = due - Sw.Elapsed.TotalSeconds - Opt.SpinMs / 1000.0;
                if (sleepS > 0.0002)
                {
                    long rel = -(long)(sleepS * 1e7);                 // relative, 100 ns units
                    if (SetWaitableTimer(_timer, ref rel, 0, IntPtr.Zero, IntPtr.Zero, false)) WaitForSingleObject(_timer, 1000);
                }
            }
            else
            {
                double margin = Opt.SpinMs / 1000.0;
                while (Sw.Elapsed.TotalSeconds < due - margin) Thread.Sleep(1);
            }
            while (Sw.Elapsed.TotalSeconds < due) Thread.SpinWait(20);
        }

        public void Dispose()
        {
            if (_timer != IntPtr.Zero) { CloseHandle(_timer); _timer = IntPtr.Zero; }
            if (_mmcss != IntPtr.Zero) { AvRevertMmThreadCharacteristics(_mmcss); _mmcss = IntPtr.Zero; }
            if (Opt.Boost) Thread.CurrentThread.Priority = _oldPrio;
            if (Opt.LowLatencyGc) GCSettings.LatencyMode = _oldGc;
            timeEndPeriod(1);
        }
    }

    /// <summary>
    /// JIT every method of the host's assemblies before a real-time clock starts: the first core update otherwise compiles
    /// the whole hot path on the spot (measured 6-8 ms on update #1, the only update over 4 ms late in a 120 s replay).
    /// </summary>
    public static class RtWarmup
    {
        static bool _done;
        public static string Prejit(params System.Reflection.Assembly[] extra)
        {
            if (_done) return "";
            _done = true;
            var sw = Stopwatch.StartNew(); int n = 0, failed = 0;
            var asms = new List<System.Reflection.Assembly> { typeof(RtWarmup).Assembly };
            foreach (var a in extra) if (a != null && !asms.Contains(a)) asms.Add(a);
            const System.Reflection.BindingFlags all = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic |
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.DeclaredOnly;
            foreach (var asm in asms)
            {
                Type[] types;
                try { types = asm.GetTypes(); } catch (System.Reflection.ReflectionTypeLoadException e) { types = e.Types.Where(t => t != null).ToArray(); }
                foreach (var t in types)
                {
                    if (t.ContainsGenericParameters) continue;
                    foreach (var m in t.GetMethods(all).Cast<System.Reflection.MethodBase>().Concat(t.GetConstructors(all)))
                    {
                        if (m.IsAbstract || m.ContainsGenericParameters || (m.MethodImplementationFlags & System.Reflection.MethodImplAttributes.InternalCall) != 0) continue;
                        if ((m.Attributes & System.Reflection.MethodAttributes.PinvokeImpl) != 0) continue;
                        try { System.Runtime.CompilerServices.RuntimeHelpers.PrepareMethod(m.MethodHandle); n++; } catch { failed++; }
                    }
                }
            }
            return string.Format(CultureInfo.InvariantCulture, "pre-JIT {0} methods in {1:0} ms{2}", n, sw.Elapsed.TotalMilliseconds, failed > 0 ? " (" + failed + " skipped)" : "");
        }
    }

    /// <summary>A growable list of doubles in fixed 64 K chunks: Add never copies, so it never stalls a real-time loop.</summary>
    public sealed class ChunkedDoubles
    {
        const int Chunk = 1 << 16;
        readonly List<double[]> _c = new List<double[]>();
        public int Count { get; private set; }
        public ChunkedDoubles() { _c.Add(new double[Chunk]); }
        public void Add(double v)
        {
            int i = Count & (Chunk - 1);
            if (i == 0 && Count > 0) _c.Add(new double[Chunk]);
            _c[_c.Count - 1][i] = v; Count++;
        }
        public double this[int i] => _c[i >> 16][i & (Chunk - 1)];
        public double[] ToArray() { var a = new double[Count]; for (int i = 0; i < Count; i++) a[i] = this[i]; return a; }
    }

    /// <summary>
    /// Per-update timing of a real-time loop (B4 instrumentation). Each update records its lateness (wake time - deadline),
    /// its slack (deadline - time the wait began: negative = the work before it overran), the time spent in each named stage
    /// since the previous wake, and whether a garbage collection ran since the previous update. No allocation per update.
    /// </summary>
    public sealed class LoopStats
    {
        public readonly string[] Stages;
        readonly ChunkedDoubles _late = new ChunkedDoubles(), _slack = new ChunkedDoubles(), _gc = new ChunkedDoubles();
        readonly ChunkedDoubles[] _stage;
        readonly double[] _cur;
        long _mark; int _gc0, _gc1, _gc2, _gcStart0, _gcStart1, _gcStart2; TimeSpan _pause0;
        static readonly double TickMs = 1000.0 / Stopwatch.Frequency;
        public string Mode = "";
        GCLatencyMode _mode = GCSettings.LatencyMode;

        public LoopStats(params string[] stages)
        {
            Stages = stages;
            _stage = stages.Select(_ => new ChunkedDoubles()).ToArray();
            _cur = new double[stages.Length];
            _gcStart0 = _gc0 = GC.CollectionCount(0); _gcStart1 = _gc1 = GC.CollectionCount(1); _gcStart2 = _gc2 = GC.CollectionCount(2);
            _pause0 = GC.GetTotalPauseDuration();
            _mark = Stopwatch.GetTimestamp();
        }

        public int Count => _late.Count;
        public double LatenessAt(int i) => _late[i];

        /// <summary>Close the current stage: the time since the last mark is charged to stage <paramref name="i"/>.</summary>
        public void Mark(int i) { long now = Stopwatch.GetTimestamp(); _cur[i] += (now - _mark) * TickMs; _mark = now; }

        /// <summary>Record one update: <paramref name="slackMs"/> measured before the wait, <paramref name="lateMs"/> after it.
        /// The wait itself is charged to no stage.</summary>
        public void Update(double slackMs, double lateMs)
        {
            _late.Add(lateMs); _slack.Add(slackMs);
            for (int i = 0; i < _cur.Length; i++) { _stage[i].Add(_cur[i]); _cur[i] = 0; }
            int g0 = GC.CollectionCount(0), g1 = GC.CollectionCount(1), g2 = GC.CollectionCount(2);
            _gc.Add(g2 != _gc2 ? 2 : g1 != _gc1 ? 1 : g0 != _gc0 ? 0 : -1);
            if (_late.Count == 1) _mode = GCSettings.LatencyMode;
            _gc0 = g0; _gc1 = g1; _gc2 = g2;
            _mark = Stopwatch.GetTimestamp();
        }

        static double P(double[] sorted, double p) => sorted.Length == 0 ? 0 : sorted[Math.Min(sorted.Length - 1, (int)(sorted.Length * p))];

        /// <summary>The B4 histogram line (same shape as Pipeline.LatenessHistogram).</summary>
        public static string Histogram(double[] lateMs)
        {
            if (lateMs.Length == 0) return "(no real-time samples)";
            var a = (double[])lateMs.Clone(); Array.Sort(a);
            var sb = new StringBuilder();
            sb.AppendFormat(CultureInfo.InvariantCulture, "{0} updates: p50 {1:0.00} ms, p99 {2:0.00} ms, p99.9 {3:0.00} ms, max {4:0.00} ms; ", a.Length, P(a, 0.5), P(a, 0.99), P(a, 0.999), a[a.Length - 1]);
            var bins = new[] { 1.0, 2, 4, 8, 16, double.MaxValue };
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

        public string Histogram() => Histogram(_late.ToArray());

        /// <summary>The histogram plus: cause of every update later than 1 ms, stage times, GC counts, the worst updates.</summary>
        public string Report(int worst = 10)
        {
            var sb = new StringBuilder();
            var late = _late.ToArray();
            sb.AppendLine("deadline: " + Histogram(late));
            if (Mode != "") sb.AppendLine("  wait mode: " + Mode);
            int n = late.Length;
            int lateN = 0, overran = 0, wake = 0, withGc = 0, withGc2 = 0;
            for (int i = 0; i < n; i++)
            {
                if (late[i] <= 1.0) continue;
                lateN++;
                if (_slack[i] < 0) overran++; else wake++;
                if (_gc[i] >= 0) withGc++;
                if (_gc[i] >= 1) withGc2++;
            }
            sb.AppendFormat(CultureInfo.InvariantCulture, "  late > 1 ms: {0}; of them the work before the wait overran the deadline: {1}, woke late from the wait: {2}; a GC ran since the previous update: {3} (gen1/2: {4})",
                lateN, overran, wake, withGc, withGc2).AppendLine();
            sb.AppendFormat(CultureInfo.InvariantCulture, "  GC during the run: gen0 {0}, gen1 {1}, gen2 {2}; total pause {3:0.0} ms; latency mode {4}",
                GC.CollectionCount(0) - _gcStart0, GC.CollectionCount(1) - _gcStart1, GC.CollectionCount(2) - _gcStart2,
                (GC.GetTotalPauseDuration() - _pause0).TotalMilliseconds, _mode).AppendLine();
            sb.Append("  stage ms per update (p50 / p99 / p99.9 / max):");
            for (int s = 0; s < Stages.Length; s++)
            {
                var a = _stage[s].ToArray(); Array.Sort(a);
                sb.AppendFormat(CultureInfo.InvariantCulture, "  {0} {1:0.000}/{2:0.000}/{3:0.000}/{4:0.00}", Stages[s], P(a, 0.5), P(a, 0.99), P(a, 0.999), a.Length > 0 ? a[a.Length - 1] : 0);
            }
            sb.AppendLine();
            var idx = Enumerable.Range(0, n).OrderByDescending(i => late[i]).Take(worst).ToList();
            sb.AppendLine("  worst updates: #index late ms | slack ms | GC since previous | stage ms");
            foreach (var i in idx)
            {
                sb.AppendFormat(CultureInfo.InvariantCulture, "    #{0} {1:0.00} | {2:0.00} | {3} |", i, late[i], _slack[i], _gc[i] < 0 ? "-" : "gen" + _gc[i]);
                for (int s = 0; s < Stages.Length; s++) sb.AppendFormat(CultureInfo.InvariantCulture, " {0} {1:0.00}", Stages[s], _stage[s][i]);
                sb.AppendLine();
            }
            return sb.ToString();
        }
    }
}
