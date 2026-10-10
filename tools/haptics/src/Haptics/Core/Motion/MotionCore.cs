using System;
using System.Collections.Generic;

namespace Haptics.Core.Motion
{
    /// <summary>
    /// The motion pipeline, pure (no sockets, no clock of its own): Feed() it the core's VehicleState + events with a motion
    /// clock, Pump() it to that clock and it returns one MotionFrame per output tick (output_hz on the same clock).
    ///
    ///   VehicleState --Motion.Derive (once per physics state)--> PhysicsSample --Motion.Resample--> channels at tick t
    ///   events + edges --Motion.Cues--> cue vector at tick t
    ///   Motion.Safety: fail-to-neutral gain (stale / absent / destroyed / startup), status word
    ///
    /// Clock: in replay the core time (engine sim time + stalled intervals), so a replay gives the same packets every run;
    /// live, the host's stopwatch, so a dead game still ramps to neutral (docs/MOTION-OUTPUT.md 2 / 6).
    /// </summary>
    public sealed class MotionCore
    {
        public readonly MotionParams P;
        public readonly MotionDerive Derive;
        public readonly Resampler Resample;
        public readonly Cues Cues;
        public readonly NeutralRamp Neutral;
        uint _seq;
        double _nextTick = double.NaN, _lastPhysicsClock = double.NaN, _lastFeedClock = double.NaN, _firstData = double.NaN, _lastTick = double.NaN;
        bool _present, _destroyed;
        double _distance;
        public long Ticks, NeutralTicks, PhysicsStates;

        public MotionCore(MotionParams p)
        {
            P = p;
            Derive = new MotionDerive(p);
            Resample = new Resampler { Mode = p.Resample, HoldLpHz = p.HoldLpHz };
            Cues = new Cues(p);
            Neutral = new NeutralRamp { RampS = p.NeutralRampMs / 1000.0 };
        }

        public double Period => 1.0 / Math.Max(1.0, P.OutputHz);

        /// <summary>One core step's input. Cheap when nothing changed (the same VehicleState is handed over at 250 Hz).</summary>
        public void Feed(VehicleState st, IList<HapticEvent> events, double clock)
        {
            if (st == null) return;
            bool firstSight = !ReferenceEquals(st, _lastState);
            _lastState = st;
            if (firstSight) { _lastFeedClock = clock; _present = st.Present; _destroyed = (st.Flags & (TelFrame.FlagDestroyed | TelFrame.FlagWreck)) != 0; }
            if (!st.Present && firstSight) { Derive.ResetHistory(); }
            // back after a dropout (stale): no derivative across the gap, no interpolation from the pre-gap state
            if (firstSight && st.Present && !double.IsNaN(_lastPhysicsClock) && clock - _lastPhysicsClock > P.StaleMs / 1000.0)
            { Derive.ResetHistory(); Resample.Reset(); _lastStamp = double.NaN; }
            if (Derive.IsNew(st))
            {
                var prev = Derive.Last;
                double vyPrev = prev != null ? prev.VelWorld[1] : 0;
                var s = Derive.Derive(st, clock);
                // fixed-step streams: put the state on the physics timeline (previous stamp + step dt) so the interpolator
                // does not inherit the 33 / 50 ms render-frame jitter; re-anchor to the arrival clock if it drifts > 2 steps
                if (Derive.FixedStepMode && prev != null && !double.IsNaN(_lastStamp) && Math.Abs(_lastStamp + s.Dt - clock) < 2 * s.Dt)
                    s.Clock = _lastStamp + s.Dt;
                _lastStamp = s.Clock;
                Resample.Push(s);
                PhysicsStates++;
                _lastPhysicsClock = clock;
                if (double.IsNaN(_firstData)) _firstData = clock;
                Cues.LandingVy = vyPrev;
                Cues.OnPhysics(s, clock, P.AccelSource);
            }
            if (events != null && events.Count > 0) Cues.OnEvents(events, clock, Derive.Last);
        }
        VehicleState _lastState;
        double _lastStamp = double.NaN;

        /// <summary>All output ticks up to and including clock.</summary>
        public List<MotionFrame> Pump(double clock)
        {
            var o = new List<MotionFrame>();
            if (double.IsNaN(_firstData)) return o;               // nothing to say before the first physics state
            if (double.IsNaN(_nextTick)) _nextTick = Math.Ceiling(_firstData / Period - 1e-9) * Period;
            if (clock - _nextTick > 10.0) _nextTick = Math.Ceiling(clock / Period - 1e-9) * Period - Period;   // more than 10 s behind (suspend / long pause): resync, the gap is neutral anyway
            int guard = 0;
            while (_nextTick <= clock + 1e-9 && guard++ < 2000)
            {
                o.Add(Tick(_nextTick));
                _seq++;
                _nextTick = Math.Round((_nextTick + Period) / Period) * Period;
            }
            return o;
        }

        /// <summary>Is the stream stale at t (no new physics state for stale_ms, or no frames at all)?</summary>
        public bool StaleAt(double t) => double.IsNaN(_lastPhysicsClock) || t - _lastPhysicsClock > P.StaleMs / 1000.0;
        public bool PausedAt(double t) => double.IsNaN(_lastFeedClock) || t - _lastFeedClock > P.StaleMs / 1000.0;

        public MotionFrame Tick(double t)
        {
            bool stale = StaleAt(t), paused = PausedAt(t);
            bool startup = !double.IsNaN(_firstData) && t < _firstData + P.StartupNeutralS;
            bool neutral = stale || !_present || _destroyed || startup;
            double g = Neutral.Update(t, neutral);
            var s = Resample.At(t) ?? new PhysicsSample();
            s = s.Clone();
            var cue = Cues.At(t);
            double dt = double.IsNaN(_lastTick) ? 0 : Math.Max(0, t - _lastTick); _lastTick = t;
            _distance += s.Speed * dt;

            // the ramp scales every kinematic channel; dash values (speed, rpm, gear, pedals) pass through
            s.Surge *= g; s.Sway *= g; s.Heave *= g; s.RollRate *= g; s.PitchRate *= g; s.YawRate *= g;
            s.Roll *= g; s.Pitch *= g; s.VelRight *= g; s.VelUp *= g; s.VelFwd *= g; s.Texture *= g;
            for (int i = 0; i < 4; i++) { s.Susp[i] *= g; s.Skid[i] *= g; }
            var f = new MotionFrame
            {
                Seq = _seq, Clock = t, TSim = t, S = s, Gain = g, Distance = _distance,
                CueSurge = cue.s * g, CueSway = cue.w * g, CueHeave = cue.h * g,
            };
            uint st = 0;
            bool live = _present && !stale && !_destroyed;
            if (live) st |= MotionStatus.Live;
            if (s.Airborne) st |= MotionStatus.Airborne;
            if (s.SkidAny) st |= MotionStatus.Skid;
            if (_destroyed) st |= MotionStatus.Destroyed;
            if (paused) st |= MotionStatus.Paused;
            if (neutral || g < 1) st |= MotionStatus.Neutral;
            if (Resample.LastWasInterpolated) st |= MotionStatus.Interpolated;
            if (cue.any) st |= MotionStatus.Cues;
            st |= (s.Surface & 0xff) << MotionStatus.SurfaceShift;
            st |= ((uint)Math.Max(0, Math.Min(255, s.Gear)) & 0xff) << MotionStatus.GearShift;
            f.Status = st;
            f.RaceOn = live && !neutral;
            Ticks++; if ((st & MotionStatus.Neutral) != 0) NeutralTicks++;
            return f;
        }

        /// <summary>The explicit last tick on exit (bit 31): every kinematic channel zero.</summary>
        public MotionFrame ShutdownFrame(double t)
        {
            var s = (Resample.Newest ?? new PhysicsSample()).Clone();
            s.Surge = s.Sway = s.Heave = s.RollRate = s.PitchRate = s.YawRate = s.Roll = s.Pitch = 0;
            s.VelRight = s.VelUp = s.VelFwd = s.Texture = 0;
            for (int i = 0; i < 4; i++) { s.Susp[i] = 0; s.Skid[i] = 0; }
            var f = new MotionFrame { Seq = _seq++, Clock = t, TSim = t, S = s, Gain = 0, Distance = _distance };
            f.Status = MotionStatus.ShuttingDown | MotionStatus.Neutral | ((uint)Math.Max(0, Math.Min(255, s.Gear)) << MotionStatus.GearShift);
            return f;
        }
    }
}
