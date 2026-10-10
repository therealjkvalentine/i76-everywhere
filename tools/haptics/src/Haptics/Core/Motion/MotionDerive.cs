using System;

namespace Haptics.Core.Motion
{
    /// <summary>
    /// Motion.Derive (docs/MOTION-OUTPUT.md 4.1): VehicleState -> PhysicsSample, ONCE per new physics state.
    ///
    /// New-state rule: the core hands the same VehicleState to every 250 Hz sub-step of a frame, and at 60-120 fps under
    /// I76_FIXED_STEP=24 most rendered frames repeat the physics pose. A state is new when it is a different object, the
    /// sim frame advanced, and step_count &gt; 0 (or, when step_count is unknown (-1), the position / velocity / time changed).
    /// Never differentiates across a repeated pose (that would read 0 then 2x).
    ///
    /// Channels: accelerations from accel_source (integrator = the FFB block's accel_body while ffb_present, else ent+0xd4
    /// rotated into the body; differentiated = dv/dt across physics states; blend = integrator below blend_hz plus the
    /// high-passed, spike-clipped a_diff above it), zeroed while airborne (airborne_zero_physics); pitch / roll from rot,
    /// their rates DIFFERENTIATED from the angles (the engine's ent+0xc8 / +0xd0 are the contact model's lift targets,
    /// a square wave) and averaged over the last two steps; yaw rate is the engine's.
    /// </summary>
    public sealed class MotionDerive
    {
        public MotionParams P;
        public MotionDerive(MotionParams p) { P = p; }

        VehicleState _lastObj;
        PhysicsSample _prev;
        double _rawPitchRate, _rawRollRate;
        bool _haveRaw;
        double _lpS, _lpW, _lpH, _hpS, _hpW, _hpH, _hpInS, _hpInW, _hpInH; bool _blendInit;
        public int Derived, Repeats;

        public PhysicsSample Last => _prev;
        public bool FixedStepMode;
        int _stepsSince;

        /// <summary>Is this state a new physics state? (also records it as seen)</summary>
        public bool IsNew(VehicleState st)
        {
            if (ReferenceEquals(st, _lastObj)) return false;
            var prevObj = _lastObj; _lastObj = st;
            if (st.StepCount > 0) _stepsSince = st.StepCount;
            if (!st.Present) return false;
            if (prevObj == null || !prevObj.Present || _prev == null) return true;
            if (st.StepCount == 0) { Repeats++; FixedStepMode = true; return false; }
            bool moved = st.PosWorld.X != _prev.PosWorld[0] || st.PosWorld.Y != _prev.PosWorld[1] || st.PosWorld.Z != _prev.PosWorld[2]
                      || st.VelWorld.X != _prev.VelWorld[0] || st.VelWorld.Y != _prev.VelWorld[1] || st.VelWorld.Z != _prev.VelWorld[2];
            if (st.StepCount > 0) { if (st.SimFrame != prevObj.SimFrame || st.T != prevObj.T || moved) return true; Repeats++; return false; }
            // step_count unknown: a change of pose / velocity / sim time
            if (moved || st.T != _prev.SimT) return true;
            Repeats++; return false;
        }

        static double Wrap(double a) { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; }
        static double Clamp1(double x) => Math.Max(-1.0, Math.Min(1.0, x));

        public PhysicsSample Derive(VehicleState st, double clock)
        {
            var s = new PhysicsSample { Clock = clock, SimT = st.T, Present = st.Present, Flags = st.Flags, Surface = st.Surface };
            for (int i = 0; i < 9; i++) s.Rot[i] = st.Rot[i];
            s.PosWorld = new[] { st.PosWorld.X, st.PosWorld.Y, st.PosWorld.Z };
            s.VelWorld = new[] { st.VelWorld.X, st.VelWorld.Y, st.VelWorld.Z };
            // physics time since the previous state. Under I76_FIXED_STEP the proxy reports sim_time / sim_dt of the RENDERED
            // frame and steps physics in whole fixed steps (strlkproxy.c fixed-step accumulator), so the state advanced
            // step_count x the fixed step, not the sim_time difference (which jitters 33 / 50 ms at 60 fps). Fixed-step mode
            // is recognised by a step_count of 0, or one that differs from the stock stepper's floor(sim_dt x 20) + 1.
            if (st.StepCount == 0 || (st.StepCount > 0 && st.StepCount != Math.Min(20, (int)(st.SimDt * 20.0f) + 1) && st.SimDt > 0)) FixedStepMode = true;
            double dt;
            if (FixedStepMode && _prev != null && _stepsSince > 0) dt = _stepsSince / Math.Max(1.0, P.FixedStepHz);
            else dt = _prev != null ? st.T - _prev.SimT : 0;
            if (!(dt > 0.005 && dt < 1.0)) dt = _prev != null && _prev.Dt > 0 ? _prev.Dt : 1.0 / 24;
            s.Dt = dt;

            // angles (our sign convention: see PhysicsSample)
            if (st.HasOrientation)
            {
                s.Pitch = Math.Asin(Clamp1(st.Rot[7]));
                s.Roll = -Math.Asin(Clamp1(st.Rot[1]));
                s.Heading = Math.Atan2(st.Rot[6], st.Rot[8]);
            }
            else if (st.Speed > 1.0) s.Heading = Math.Atan2(st.VelWorld.X, st.VelWorld.Z);   // legacy source: travel direction

            var vb = s.ToBody(s.VelWorld[0], s.VelWorld[1], s.VelWorld[2]);
            s.VelRight = vb.r; s.VelUp = vb.u; s.VelFwd = vb.f;

            // accelerations
            double iS, iW, iH;
            if (st.FfbPresent) { iW = st.AccBodyFfb.X; iH = st.AccBodyFfb.Y; iS = st.AccBodyFfb.Z; }
            else { var a = s.ToBody(st.AccEngineWorld.X, st.AccEngineWorld.Y, st.AccEngineWorld.Z); iW = a.r; iH = a.u; iS = a.f; }
            if (_prev != null)
            {
                var d = s.ToBody((s.VelWorld[0] - _prev.VelWorld[0]) / dt, (s.VelWorld[1] - _prev.VelWorld[1]) / dt, (s.VelWorld[2] - _prev.VelWorld[2]) / dt);
                s.ADiffSway = d.r; s.ADiffHeave = d.u; s.ADiffSurge = d.f;
            }
            switch (P.AccelSource)
            {
                case "differentiated": s.Surge = s.ADiffSurge; s.Sway = s.ADiffSway; s.Heave = s.ADiffHeave; break;
                case "blend":
                {
                    double a = 1 - Math.Exp(-2 * Math.PI * P.BlendHz * dt);
                    double cS = Clip(s.ADiffSurge, iS, P.ImpulseThreshold), cW = Clip(s.ADiffSway, iW, P.ImpulseThreshold), cH = Clip(s.ADiffHeave, iH, P.ImpulseThreshold);
                    if (!_blendInit) { _lpS = iS; _lpW = iW; _lpH = iH; _hpInS = cS; _hpInW = cW; _hpInH = cH; _hpS = _hpW = _hpH = 0; _blendInit = true; }
                    _lpS += a * (iS - _lpS); _lpW += a * (iW - _lpW); _lpH += a * (iH - _lpH);
                    double k = 1 - a;   // first-order high-pass: y = k (y + x - x_prev)
                    _hpS = k * (_hpS + cS - _hpInS); _hpW = k * (_hpW + cW - _hpInW); _hpH = k * (_hpH + cH - _hpInH);
                    _hpInS = cS; _hpInW = cW; _hpInH = cH;
                    s.Surge = _lpS + _hpS; s.Sway = _lpW + _hpW; s.Heave = _lpH + _hpH;
                    break;
                }
                default: s.Surge = iS; s.Sway = iW; s.Heave = iH; break;
            }
            s.Airborne = (st.Flags & TelFrame.FlagAirborne) != 0;
            if (s.Airborne && P.AirborneZeroPhysics) { s.Surge = s.Sway = s.Heave = 0; }
            s.Destroyed = (st.Flags & (TelFrame.FlagDestroyed | TelFrame.FlagWreck)) != 0;

            // rates: differentiate the angles across physics steps, average the last two differences
            if (_prev != null && _prev.Present)
            {
                double rp = Wrap(s.Pitch - _prev.Pitch) / dt, rr = Wrap(s.Roll - _prev.Roll) / dt;
                s.PitchRate = _haveRaw ? 0.5 * (rp + _rawPitchRate) : rp;
                s.RollRate = _haveRaw ? 0.5 * (rr + _rawRollRate) : rr;
                _rawPitchRate = rp; _rawRollRate = rr; _haveRaw = true;
                s.LandingEdge = _prev.Airborne && !s.Airborne;
                s.TakeoffEdge = !_prev.Airborne && s.Airborne;
            }
            s.YawRate = st.YawRate;

            // dash / wheels
            s.Speed = st.Speed; s.Rpm = st.Rpm; s.Gear = st.Gear; s.Steer = st.Steer;
            s.Throttle = Math.Max(0, st.Throttle); s.Brake = Math.Max(0, -st.Throttle);
            s.Handbrake = st.Handbrake; s.EngineHealth = st.EngineHealth; s.Mass = st.Mass; s.WeaponName = st.WeaponName ?? "";
            int[] slot = { 0, 1, 4, 5 };
            bool flagSkid = (st.Flags & (TelFrame.FlagSkid | TelFrame.FlagGripLimit)) != 0, anyWheel = false;
            for (int i = 0; i < 4; i++) { s.Susp[i] = st.SuspOffset[slot[i]]; s.Skid[i] = st.WheelSkid[slot[i]] ? 1 : 0; anyWheel |= st.WheelSkid[slot[i]]; }
            if (flagSkid && !anyWheel) for (int i = 0; i < 4; i++) s.Skid[i] = 1;
            s.SkidAny = flagSkid || anyWheel;
            double amp = P.Surfaces.TryGetValue(st.Surface.ToString(System.Globalization.CultureInfo.InvariantCulture), out var sa) ? sa
                       : P.Surfaces.TryGetValue("default", out var sd) ? sd : 0;
            s.Texture = Math.Max(0, Math.Min(1, amp * st.Speed / Math.Max(1e-6, P.SpeedRef)));
            if (s.Airborne) s.Texture = 0;

            _prev = s; Derived++;
            return s;
        }

        static double Clip(double x, double c, double r) => Math.Max(c - r, Math.Min(c + r, x));

        /// <summary>The player left / came back: forget derivative history (no rate across a respawn).</summary>
        public void ResetHistory() { _prev = null; _haveRaw = false; _blendInit = false; }
    }
}
