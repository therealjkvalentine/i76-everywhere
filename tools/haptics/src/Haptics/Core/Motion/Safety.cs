using System;

namespace Haptics.Core.Motion
{
    /// <summary>
    /// Motion.Safety, the fail-to-neutral half (docs/MOTION-OUTPUT.md 6.3 / 6.6): a gain that RAMPS (never steps) to 0 when the
    /// telemetry is stale (no new physics state for stale_ms), the player is absent or destroyed, or during the startup
    /// hold (startup_neutral_s of neutral after the first data), and ramps back to 1 over the same neutral_ramp_ms.
    /// Always on, for every target: it is what a consumer sees as a parked car, not a filter.
    /// </summary>
    public sealed class NeutralRamp
    {
        public double RampS = 1.0;
        public double Gain;                       // starts parked
        double _t = double.NaN;
        public bool TargetNeutral = true;

        public double Update(double t, bool neutral)
        {
            TargetNeutral = neutral;
            if (double.IsNaN(_t)) { _t = t; return Gain; }
            double dt = Math.Max(0, t - _t); _t = t;
            double step = RampS > 0 ? dt / RampS : 1;
            Gain = neutral ? Math.Max(0, Gain - step) : Math.Min(1, Gain + step);
            return Gain;
        }
    }

    /// <summary>
    /// Motion.Safety, the per-target half (6.1 / 6.2): clamp and slew limits. OFF for software targets unless the target sets
    /// "clamp": true / "slew": true (or the rig sets safety.clamp_udp): the design library's rule is "don't clamp at the
    /// source; rig software crops". Meant for a future direct-actuator path (M6); here it only shapes values on the wire.
    /// </summary>
    public sealed class Limiter
    {
        readonly MotionParams P; readonly bool _clamp, _slew;
        double _t = double.NaN; double[] _prev;
        public int Clamped, Slewed;
        public Limiter(MotionParams p, bool clamp, bool slew) { P = p; _clamp = clamp; _slew = slew; }
        public bool Active => _clamp || _slew;

        static double C(double x, double lim, ref int n) { if (x > lim) { n++; return lim; } if (x < -lim) { n++; return -lim; } return x; }

        /// <summary>Returns a frame copy with clamped / slew-limited channels (the input is not modified).</summary>
        public MotionFrame Apply(MotionFrame f)
        {
            if (!Active) return f;
            var o = new MotionFrame { Seq = f.Seq, Status = f.Status, Clock = f.Clock, TSim = f.TSim, S = f.S.Clone(), CueSurge = f.CueSurge, CueSway = f.CueSway, CueHeave = f.CueHeave, Gain = f.Gain, RaceOn = f.RaceOn, Distance = f.Distance };
            var s = o.S;
            if (_slew)
            {
                double[] v = { s.Surge, s.Sway, s.Heave, s.RollRate, s.PitchRate, s.YawRate };
                if (_prev != null && !double.IsNaN(_t))
                {
                    double dt = Math.Max(1e-4, f.Clock - _t);
                    for (int i = 0; i < 6; i++)
                    {
                        double lim = (i < 3 ? P.MaxJerk : P.MaxRateChange) * dt, d = v[i] - _prev[i];
                        if (Math.Abs(d) > lim) { v[i] = _prev[i] + Math.Sign(d) * lim; Slewed++; }
                    }
                }
                s.Surge = v[0]; s.Sway = v[1]; s.Heave = v[2]; s.RollRate = v[3]; s.PitchRate = v[4]; s.YawRate = v[5];
                _prev = v; _t = f.Clock;
            }
            if (_clamp)
            {
                int n = 0;
                s.Surge = C(s.Surge, P.ClampAccel, ref n); s.Sway = C(s.Sway, P.ClampAccel, ref n); s.Heave = C(s.Heave, P.ClampAccel, ref n);
                o.CueSurge = C(o.CueSurge, P.ClampCue, ref n); o.CueSway = C(o.CueSway, P.ClampCue, ref n); o.CueHeave = C(o.CueHeave, P.ClampCue, ref n);
                s.RollRate = C(s.RollRate, P.ClampRate, ref n); s.PitchRate = C(s.PitchRate, P.ClampRate, ref n); s.YawRate = C(s.YawRate, P.ClampRate, ref n);
                s.Roll = C(s.Roll, P.ClampAngle, ref n); s.Pitch = C(s.Pitch, P.ClampAngle, ref n);
                Clamped += n;
            }
            return o;
        }
    }

    /// <summary>
    /// TODO(M6): Motion.Washout - classical washout (Reid &amp; Nahon) for a direct actuator path only (docs/MOTION-OUTPUT.md 4.3).
    /// Not implemented: every current target is third-party software that owns its own cueing, so the host sends raw
    /// body-frame data. A rig file with washout.enabled = true fails the config lint rather than silently doing nothing.
    /// </summary>
    public static class Washout
    {
        public const string Status = "not implemented (phase M6): UDP targets receive raw data";
    }
}
