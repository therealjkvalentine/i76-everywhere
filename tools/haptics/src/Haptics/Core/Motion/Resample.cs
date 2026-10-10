using System;

namespace Haptics.Core.Motion
{
    /// <summary>
    /// Motion.Resample (docs/MOTION-OUTPUT.md 4.1): physics states (24 Hz under I76_FIXED_STEP, 21-32 Hz stock) -> any output
    /// tick time.
    ///  * interp: linear interpolation between the last two physics states, delayed by one physics step (the value at
    ///    t is the state line evaluated at t - D, D = the last step's length): a 24 Hz staircase becomes a ramp, +1 step latency.
    ///    Heading interpolates the short way round; discrete fields come from the nearer state.
    ///  * hold: zero-order hold of the newest state, then a first-order low-pass (hold_lp_hz) per output tick. No added
    ///    step of latency.
    /// Cues are not resampled (Motion.Cues evaluates its envelopes at the tick time).
    /// </summary>
    public sealed class Resampler
    {
        public string Mode = "interp";
        public double HoldLpHz = 8;
        PhysicsSample _a, _b;          // previous, newest
        double[] _lp; double _lpT = double.NaN;
        public bool LastWasInterpolated;

        public PhysicsSample Newest => _b;

        public void Push(PhysicsSample s) { _a = _b; _b = s; }
        public void Reset() { _a = _b = null; _lp = null; _lpT = double.NaN; }

        // continuous channels, packed so interpolation / filtering is one loop
        const int HeadingIdx = 8;
        static double[] Pack(PhysicsSample s) => new[]
        {
            s.Surge, s.Sway, s.Heave, s.RollRate, s.PitchRate, s.YawRate, s.Roll, s.Pitch, s.Heading,
            s.VelRight, s.VelUp, s.VelFwd, s.Speed, s.Rpm, s.Throttle, s.Brake, s.Steer,
            s.Susp[0], s.Susp[1], s.Susp[2], s.Susp[3], s.Skid[0], s.Skid[1], s.Skid[2], s.Skid[3], s.Texture,
            s.PosWorld[0], s.PosWorld[1], s.PosWorld[2], s.VelWorld[0], s.VelWorld[1], s.VelWorld[2], s.SimT,
        };
        static void Unpack(double[] v, PhysicsSample s)
        {
            int i = 0;
            s.Surge = v[i++]; s.Sway = v[i++]; s.Heave = v[i++]; s.RollRate = v[i++]; s.PitchRate = v[i++]; s.YawRate = v[i++];
            s.Roll = v[i++]; s.Pitch = v[i++]; s.Heading = Wrap(v[i++]);
            s.VelRight = v[i++]; s.VelUp = v[i++]; s.VelFwd = v[i++]; s.Speed = v[i++]; s.Rpm = v[i++]; s.Throttle = v[i++]; s.Brake = v[i++]; s.Steer = v[i++];
            for (int k = 0; k < 4; k++) s.Susp[k] = v[i++];
            for (int k = 0; k < 4; k++) s.Skid[k] = v[i++];
            s.Texture = v[i++];
            for (int k = 0; k < 3; k++) s.PosWorld[k] = v[i++];
            for (int k = 0; k < 3; k++) s.VelWorld[k] = v[i++];
            s.SimT = v[i++];
        }
        static double Wrap(double a) { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; }

        /// <summary>The channels at output time t (motion clock). Null before the first physics state.</summary>
        public PhysicsSample At(double t)
        {
            LastWasInterpolated = false;
            if (_b == null) return null;
            if (Mode == "hold")
            {
                var x = Pack(_b);
                if (_lp == null || double.IsNaN(_lpT)) { _lp = x; _lpT = t; }
                else
                {
                    double dt = Math.Max(0, t - _lpT); _lpT = t;
                    double a = 1 - Math.Exp(-2 * Math.PI * HoldLpHz * dt);
                    for (int i = 0; i < x.Length; i++)
                    {
                        double target = i == HeadingIdx ? _lp[i] + Wrap(x[i] - _lp[i]) : x[i];
                        _lp[i] += a * (target - _lp[i]);
                    }
                    _lp[HeadingIdx] = Wrap(_lp[HeadingIdx]);
                    x = (double[])_lp.Clone();
                }
                var h = _b.Clone(); Unpack(x, h); h.SimT = _b.SimT; return h;
            }
            if (_a == null) return _b.Clone();
            double D = _b.Clock - _a.Clock;
            if (!(D > 1e-6)) return _b.Clone();
            double al = Math.Max(0.0, Math.Min(1.0, (t - _b.Clock) / D));
            var va = Pack(_a); var vb = Pack(_b); var o = new double[va.Length];
            for (int i = 0; i < va.Length; i++)
            {
                double d = vb[i] - va[i];
                if (i == HeadingIdx) d = Wrap(d);
                o[i] = va[i] + al * d;
            }
            var r = (al < 0.5 ? _a : _b).Clone();
            Unpack(o, r);
            LastWasInterpolated = al > 0 && al < 1;
            return r;
        }
    }
}
