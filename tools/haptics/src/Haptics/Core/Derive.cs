using System;
using System.Collections.Generic;

namespace Haptics.Core
{
    /// <summary>
    /// i76tel frames + raw events -> what the core consumes:
    ///  * a Tel-Sample-shaped <see cref="Sample"/> for the reference model, derived exactly as tools/ffb/Telemetry.ps1
    ///    derives it from memory (tick-differentiated long accel, heave, jolt, sideslip; Tel-Slip for under/oversteer),
    ///    with the gear from the engine's own field instead of the rpm-rate heuristic (FFB-DATA-AUDIT 2.1);
    ///  * the canonical <see cref="HapticEvent"/>s: proxy events (SHOT, EXPLOSION, IMPACT, v3 SOUND_START / SOUND_STOP /
    ///    DAMAGE_SIDE / WEAPON_UI) and host-derived edges (GEAR, LANDING, TAKEOFF, SURFACE, FLAT, GRIP_LIMIT, SKID,
    ///    OIL, ENGINE_START, NITROUS, DESTROYED) - HAPTICS-ARCHITECTURE 2.1;
    ///  * the <see cref="VehicleState"/> motion interface;
    ///  * the named frame variables effect expressions read.
    /// Time base: the engine's sim_time, never the host clock, so a replay equals a live run.
    /// </summary>
    public sealed class Derive
    {
        // Telemetry.ps1 handling-model constants (TEL_LAT_GAIN, TEL_STEER_LOCK, TEL_YAW_MAX, TEL_YAW_SIGN)
        public double LatGain = 31.0, SteerLock = 0.76, YawMax = 3.2, YawSign = 1.0, Wheelbase = 4.662;
        /// <summary>weapon.fire#/source/shot_mag: the magnitude a SHOT feeds the reference model (nominal 10, see the effect's note).</summary>
        public Effects.Expr ShotMag = new Effects.Expr("10");
        /// <summary>explosion.blast#/source/reach_m and mag_threshold: EXPLOSION distance -> blast magnitude.</summary>
        public double ExplosionReach = 100.0, ExplodeMag = 40.0;

        TelFrame _prev, _prevTick;
        bool _primed;
        double _longAccel, _vyRate, _wax, _way, _waz, _jolt, _slide, _lastHeading, _tickDt;
        double _airSince = -1;
        public int Ticks;

        public sealed class Result
        {
            public Sample Sample;
            public VehicleState State;
            public List<HapticEvent> Events = new List<HapticEvent>();
            public Dictionary<string, double> Vars = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        }

        public static (double expectedYaw, double under, double over) TelSlip(double speed, double steer, double yaw, double slide,
                                                                              double latGain = 31.0, double steerLock = 0.76, double yawMax = 3.2)
        {
            const double DEV_DEAD = 0.08, DEV_REF = 1.10;
            double expectedYaw = 0.0;
            if (speed > 0.5)
            {
                double aSteer = Math.Abs(steer);
                double kin = (speed / 4.662) * Math.Tan(aSteer * steerLock);
                double lat = latGain * aSteer / speed;
                double mag = Math.Min(kin, lat);
                if (mag > yawMax) mag = yawMax;
                if (steer < 0) mag = -mag;
                expectedYaw = mag;
            }
            double under = 0.0, over = 0.0;
            if (speed > 3.0)
            {
                double aY = Math.Abs(yaw), aE = Math.Abs(expectedYaw);
                if (aY > 0.15 && aE > 0.15 && Math.Sign(yaw) != Math.Sign(expectedYaw)) over = 1.0;
                else
                {
                    double span = DEV_REF - DEV_DEAD, shortf = aE - aY, excess = aY - aE;
                    if (shortf > DEV_DEAD) under = Math.Min(1.0, (shortf - DEV_DEAD) / span);
                    else if (excess > DEV_DEAD) over = Math.Min(1.0, (excess - DEV_DEAD) / span);
                }
            }
            if (slide > 0)
            {
                const double sDead = 0.12, sRef = 1.20;
                if (slide > sDead) { double n = Math.Min(1.0, (slide - sDead) / (sRef - sDead)); if (n > over) over = n; }
            }
            return (expectedYaw, under, over);
        }

        /// <summary>One frame (with the events that arrived with it). sinceTick: seconds since the sim last advanced, on the caller's clock.</summary>
        public Result Step(TelFrame f, IList<TelEvent> raw, double? sinceTick = null)
        {
            var r = new Result();
            double t = f.SimTime;
            bool present = f.PlayerPresent;
            var v = new Vec3(f.Vel(0), f.Vel(1), f.Vel(2));
            double speed = f.Speed;
            double yaw = f.YawRate * YawSign;
            bool ticked = _prevTick == null || f.SimFrame != _prevTick.SimFrame;

            if (ticked && present)
            {
                if (!_primed) _primed = true;
                else
                {
                    double dt = t - _prevTick.SimTime;
                    if (!(dt > 0.005 && dt < 1.0)) dt = f.SimDt > 0.005 ? f.SimDt : 0.05;
                    _tickDt = dt;
                    _longAccel = (speed - _prevTick.Speed) / dt;
                    _vyRate = (v.Y - _prevTick.Vel(1)) / dt;
                    _wax = (v.X - _prevTick.Vel(0)) / dt; _way = (v.Y - _prevTick.Vel(1)) / dt; _waz = (v.Z - _prevTick.Vel(2)) / dt;
                    if (speed > 2.0 && _lastHeading != 0.0)
                    {
                        double h = Math.Atan2(v.X, v.Z), dh = h - _lastHeading;
                        while (dh > Math.PI) dh -= 2 * Math.PI;
                        while (dh < -Math.PI) dh += 2 * Math.PI;
                        _slide = Math.Abs(yaw - dh / dt);
                        _lastHeading = h;
                    }
                    else if (speed > 2.0) { _lastHeading = Math.Atan2(v.X, v.Z); _slide = 0.0; }
                    else _slide = 0.0;
                    double dvx = v.X - _prevTick.Vel(0), dvy = v.Y - _prevTick.Vel(1), dvz = v.Z - _prevTick.Vel(2);
                    _jolt = Math.Sqrt(dvx * dvx + dvy * dvy + dvz * dvz) / dt;
                    Ticks++;
                }
            }
            if (!present) { _longAccel = _vyRate = _wax = _way = _waz = _jolt = _slide = 0; _primed = false; }

            double latAccel = yaw * speed;
            var slip = TelSlip(speed, f.Steer, yaw, _slide, LatGain, SteerLock, YawMax);

            var s = new Sample
            {
                T = t, Speed = speed, Steer = f.Steer, Throttle = f.Throttle, YawRate = yaw,
                LongAccel = _longAccel, LongG = _longAccel / 9.81, LatAccel = latAccel, LatG = latAccel / 9.81,
                HeaveAccel = _vyRate, Understeer = slip.under, Oversteer = slip.over, Jolt = _jolt, Vy = v.Y,
                Rpm = f.Rpm > 0 && f.Rpm < 20000 ? f.Rpm : 0, AngVelX = f.PitchRate, AngVelZ = f.RollRate,
                Vx = v.X, Vz = v.Z, WorldAccelX = _wax, WorldAccelY = _way, WorldAccelZ = _waz,
                HeadingApprox = speed > 1.0 ? Math.Atan2(v.X, v.Z) : 0.0,
                TravelPitch = speed > 2.0 ? Math.Asin(Math.Max(-1.0, Math.Min(1.0, v.Y / speed))) : 0.0,
                SinceTick = sinceTick, Shift = 0, FxEvent = false, FxFired = new List<FxFired>(),
            };

            // ---- host-derived edges ---------------------------------------------------------------------
            var p = _prev;
            void Ev(string type, Action<HapticEvent> fill = null)
            {
                var e = new HapticEvent { Type = type, T = t, Frame = f.ProxyFrame };
                fill?.Invoke(e); r.Events.Add(e);
            }
            if (p != null && present && p.PlayerPresent)
            {
                int g = f.Gear, pg = p.Gear;
                if (g != pg)
                {
                    int dir = (g >= 2 && pg >= 2) ? Math.Sign(g - pg) : 0;    // 0 reverse, 1 neutral: R/N changes are not shifts
                    Ev("GEAR", e => { e["gear"] = g; e["prev"] = pg; e["dir"] = dir; });
                    if (dir != 0) s.Shift = dir;
                }
                uint fl = f.Flags, pfl = p.Flags;
                bool Rise(uint bit) => (fl & bit) != 0 && (pfl & bit) == 0;
                bool Fall(uint bit) => (fl & bit) == 0 && (pfl & bit) != 0;
                if (Rise(TelFrame.FlagAirborne)) { _airSince = t; Ev("TAKEOFF", e => e["vy"] = v.Y); }
                if (Fall(TelFrame.FlagAirborne))
                {
                    double vyb = p.Vel(1), air = _airSince >= 0 ? t - _airSince : 0;
                    Ev("LANDING", e => { e["vy_before"] = vyb; e["airtime"] = air; });
                    _airSince = -1;
                }
                if (f.Surface != p.Surface) Ev("SURFACE", e => { e["surface"] = f.Surface; e["prev"] = p.Surface; });
                for (int w = 0; w < 6; w++) { int ww = w; if (f.WheelFlat(w) && !p.WheelFlat(w)) Ev("FLAT", e => e["wheel"] = ww); }
                if (Rise(TelFrame.FlagGripLimit)) Ev("GRIP_LIMIT");
                if (Rise(TelFrame.FlagSkid)) Ev("SKID");
                if (Rise(TelFrame.FlagOil)) Ev("OIL");
                if (Rise(TelFrame.FlagStarting)) Ev("ENGINE_START");
                if (Rise(TelFrame.FlagNitrous)) Ev("NITROUS");
                if (Rise(TelFrame.FlagDestroyed)) Ev("DESTROYED");
            }

            // ---- proxy events -> canonical events, and the reference model's FxFired --------------------------
            var me = new Vec3(f.Pos(0), f.Pos(1), f.Pos(2));
            if (raw != null)
                foreach (var e in raw)
                {
                    var h = new HapticEvent { T = t, Frame = e.Frame };
                    switch (e.Type)
                    {
                        case TelEvent.Shot:
                            h.Type = "SHOT"; h["row"] = e.F[0]; h["ammo_left"] = e.F[1]; h["dmg_per_hit"] = e.F[2]; h["dt_left"] = e.F[3];
                            h["weapdef"] = e.I[0]; h["rounds"] = e.I[1];
                            s.FxEvent = true;
                            s.Firing = true;
                            s.FxFired.Add(new FxFired(0, e.I[0], 0, ShotMag.Eval(k => h[k])));
                            break;
                        case TelEvent.Explosion:
                            h.Type = "EXPLOSION"; h.Name = e.Name8; h["x"] = e.F[0]; h["y"] = e.F[1]; h["z"] = e.F[2]; h["dist"] = e.F[3];
                            if (e.F[3] >= 0)
                            {
                                double lvl = Math.Max(0.0, Math.Min(1.0, 1.0 - e.F[3] / ExplosionReach));
                                if (lvl > 0) s.FxFired.Add(new FxFired(0, -2, 0, Math.Max(ExplodeMag, lvl * ExplodeMag * 1.5)));
                            }
                            break;
                        case TelEvent.Impact:
                            h.Type = "IMPACT"; h["impact_x"] = e.F[0]; h["impact_y"] = e.F[1]; h["impact_z"] = e.F[2]; h["hp_lost"] = e.F[3];
                            h["is_player"] = e.I[0]; h["source_class"] = e.I[1];
                            h["impact_mag"] = Math.Sqrt(e.F[0] * e.F[0] + e.F[1] * e.F[1] + e.F[2] * e.F[2]);
                            break;
                        case TelEvent.SoundStart:
                        {
                            h.Type = "SOUND_START"; h.Name = e.Name8;
                            int bits = e.I[2];
                            h["hz"] = e.F[0]; h["vol"] = e.F[1]; h["x"] = e.F[2]; h["y"] = e.F[3]; h["z"] = e.F[4]; h["pan"] = e.F[5];
                            h["mode"] = bits & 0xff; h["is_player"] = (bits & 0x100) != 0 ? 1 : 0; h["has_pos"] = (bits & 0x200) != 0 ? 1 : 0;
                            h["detached"] = (bits & 0x400) != 0 ? 1 : 0; h["prio"] = (bits >> 16) & 0xffff; h["obj"] = e.I[3];
                            h["voice"] = (uint)e.I[4];   // voice address: pairs a SOUND_START with its SOUND_STOP (Lfe.Stems)
                            h["dist"] = (bits & 0x200) != 0 && present ? (new Vec3(e.F[2], e.F[3], e.F[4]) - me).Length : 0.0;
                            break;
                        }
                        case TelEvent.SoundStop:
                            h.Type = "SOUND_STOP"; h.Name = e.Name8; h["seconds"] = e.F[0];
                            h["reason"] = e.I[2] & 0xffff; h["is_player"] = (e.I[2] & 0x10000) != 0 ? 1 : 0; h["obj"] = e.I[3]; h["voice"] = (uint)e.I[4];
                            break;
                        case TelEvent.DamageSide:
                            h.Type = "DAMAGE_SIDE"; h["amount"] = e.F[0]; h["hp_lost"] = e.F[1]; h["hit_x"] = e.F[2]; h["hit_y"] = e.F[3]; h["hit_z"] = e.F[4];
                            h["side"] = e.I[0]; h["zone"] = e.I[1];
                            h["is_player"] = (e.I[2] & 1) != 0 ? 1 : 0; h["by_player"] = (e.I[2] & 2) != 0 ? 1 : 0; h["killed"] = (e.I[2] & 4) != 0 ? 1 : 0;
                            h["type_mask"] = e.I[3]; h["source_class"] = e.I[4];
                            break;
                        case TelEvent.WeaponUi:
                            h.Type = "WEAPON_UI"; h["action"] = e.I[0];
                            break;
                        default:
                            h.Type = "TYPE_" + e.Type; break;
                    }
                    r.Events.Add(h);
                }
            if (s.FxFired.Count == 0) s.FxFired = null;
            if (!s.FxEvent.Value) s.FxEvent = false;

            // ---- the motion interface ------------------------------------------------------------------
            var st = new VehicleState
            {
                T = t, Dt = _tickDt, SimFrame = f.SimFrame, Present = present, Ticked = ticked, HasOrientation = f.Has("rot_0"),
                PosWorld = me, VelWorld = v, AccWorld = new Vec3(_wax, _way, _waz),
                AccEngineWorld = new Vec3(f.Accel(0), f.Accel(1), f.Accel(2)),
                AccBodyFfb = new Vec3(f["accel_body_0"], f["accel_body_1"], f["accel_body_2"]), FfbPresent = f["ffb_present"] != 0,
                PitchRate = f.PitchRate, YawRate = yaw, RollRate = f.RollRate, Speed = speed, Rpm = f.Rpm,
                Throttle = f.Throttle, Steer = f.Steer, Gear = f.Gear, Flags = f.Flags, Surface = f.Surface, Clearance = f["clearance"],
                GroundNormal = new Vec3(f["ground_normal_0"], f["ground_normal_1"], f["ground_normal_2"]),
            };
            if (st.HasOrientation && present)
            {
                bool nonzero = false;
                for (int i = 0; i < 9; i++) { st.Rot[i] = f.Rot(i); nonzero |= st.Rot[i] != 0; }
                if (!nonzero) { st.Rot = new double[] { 1, 0, 0, 0, 1, 0, 0, 0, 1 }; st.HasOrientation = false; }
                st.Pitch = Math.Asin(Clamp1(st.Rot[7])); st.Roll = Math.Asin(Clamp1(st.Rot[1])); st.Heading = Math.Atan2(st.Rot[6], st.Rot[8]);
            }
            st.VelBody = st.ToBody(v); st.AccBody = st.ToBody(st.AccWorld);
            for (int w = 0; w < 6; w++) { st.SuspOffset[w] = f.WheelSusp(w); st.WheelOnGround[w] = f.WheelPresent(w) && f["wheel" + w + "_unloaded"] == 0; }
            r.State = st;
            r.Sample = s;
            FillVars(r.Vars, f, s, st);
            if (ticked) _prevTick = f;
            _prev = f;
            return r;
        }

        static double Clamp1(double x) => Math.Max(-1.0, Math.Min(1.0, x));

        public static void FillVars(Dictionary<string, double> V, TelFrame f, Sample s, VehicleState st)
        {
            uint fl = f?.Flags ?? st.Flags;
            V["speed"] = s.Speed; V["steer"] = s.Steer; V["throttle"] = Math.Max(0, s.Throttle); V["brake"] = Math.Max(0, -s.Throttle);
            V["yaw_rate"] = s.YawRate; V["pitch_rate"] = st.PitchRate; V["roll_rate"] = st.RollRate; V["rpm"] = st.Rpm; V["gear"] = st.Gear;
            V["surface"] = st.Surface; V["clearance"] = st.Clearance; V["health_pct"] = f?["health_pct"] ?? 100;
            V["flags"] = fl;
            V["flag_engine_running"] = (fl & 0x1) != 0 ? 1 : 0; V["flag_skid"] = (fl & 0x2) != 0 ? 1 : 0; V["flag_airborne"] = (fl & 0x4) != 0 ? 1 : 0;
            V["flag_starting"] = (fl & 0x8) != 0 ? 1 : 0; V["flag_destroyed"] = (fl & 0x20) != 0 ? 1 : 0; V["flag_oil"] = (fl & 0x400) != 0 ? 1 : 0;
            V["flag_nitrous"] = (fl & 0x800) != 0 ? 1 : 0; V["flag_grip_limit"] = (fl & 0x2000) != 0 ? 1 : 0; V["flag_critical"] = (fl & 0x4000) != 0 ? 1 : 0;
            V["flag_wreck"] = (fl & 0x8000) != 0 ? 1 : 0;
            V["accel_x"] = st.AccBody.X; V["accel_y"] = st.AccBody.Y; V["accel_z"] = st.AccBody.Z;
            V["vel_x"] = st.VelBody.X; V["vel_y"] = st.VelBody.Y; V["vel_z"] = st.VelBody.Z;
            V["pitch"] = st.Pitch; V["roll"] = st.Roll; V["heading"] = st.Heading;
            V["jolt"] = s.Jolt; V["long_accel"] = s.LongAccel ?? 0; V["lat_accel"] = s.LatAccel ?? 0; V["heave_accel"] = s.HeaveAccel ?? 0;
            V["oversteer"] = s.Oversteer; V["understeer"] = s.Understeer; V["player_present"] = st.Present ? 1 : 0;
            int flats = 0; double smax = 0, smin = 0;
            for (int w = 0; w < 6; w++) { if (f != null && f.WheelFlat(w)) flats++; smax = Math.Max(smax, st.SuspOffset[w]); smin = Math.Min(smin, st.SuspOffset[w]); }
            V["wheels_flat"] = flats; V["susp_max"] = smax; V["susp_min"] = smin;
            V["drive_power"] = f?["drive_power"] ?? 0; V["mass"] = f?["mass"] ?? 0;
            // v3 frame fields (0 on a v2 frame)
            V["music_track"] = f?["music_track"] ?? 0; V["grip_cap"] = f?["grip_cap"] ?? 0; V["ground_g"] = f?["ground_g"] ?? 0;
            V["wheelbase"] = f?["wheelbase"] ?? 0; V["sound_voices"] = f?["sound_voices"] ?? 0;
        }

        /// <summary>For sources that are already Tel-Samples (legacy drive*.csv): a VehicleState without orientation.</summary>
        public static Result FromSample(Sample s)
        {
            var st = new VehicleState
            {
                T = s.T, Present = true, Ticked = true, HasOrientation = false, Speed = s.Speed, Steer = s.Steer, Throttle = s.Throttle,
                YawRate = s.YawRate, PitchRate = s.AngVelX, RollRate = s.AngVelZ, Rpm = s.Rpm,
                VelWorld = new Vec3(s.Vx, s.Vy, s.Vz), AccWorld = new Vec3(s.WorldAccelX, s.WorldAccelY, s.WorldAccelZ),
            };
            st.VelBody = st.VelWorld; st.AccBody = st.AccWorld;
            var r = new Result { Sample = s, State = st };
            FillVars(r.Vars, null, s, st);
            return r;
        }
    }
}
