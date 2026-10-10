using System;
using System.Collections.Generic;
using Haptics.Core;

namespace Haptics.Transport
{
    /// <summary>
    /// Scripted i76tel sessions, encoded as real datagrams (v2 or v3 layout), so the whole chain - decoder, Derive,
    /// core, renderers - runs without the game. No captured .i76rec exists yet (the console was not available), so
    /// this is the stand-in input until owner test C1 records one. The script (20 s, repeatable):
    ///   0.5 s engine start | 1-6 s accelerate, upshifts at 2.5 / 4.5 s | 6-8 s corner, grip-limit 7.0-7.5 s
    ///   8-9 s machine-gun SHOTs every 0.1 s | 9.5 s IMPACT (40 hp, sideways jolt) | 11.0-11.6 s airborne -> LANDING
    ///   12.5 s EXPLOSION 30 m away | 13.5 s flat front-right tyre | 14 s (v3) AI cannon SOUND_START 40 m away,
    ///   DAMAGE_SIDE right 30, WEAPON_UI cycle, skid SOUND_START/STOP | 15-17 s hard braking to a stop | parked.
    /// </summary>
    public static class Synthetic
    {
        public const double Length = 20.0;

        public static IEnumerable<(double t, byte[] data)> Session(int version = 3, double fps = 60.0, int repeats = 1)
        {
            var L = version == 2 ? I76TelLayout.V2 : I76TelLayout.V3;
            uint seq = 0, evSeq = 0, simFrame = 0;
            double heading = 0, x = 0, y = 0, z = 0, vy = 0, airY = 0;
            int gear = 1;
            double total = Length * repeats, dt = 1.0 / fps;
            int n = (int)Math.Round(total * fps);
            for (int i = 0; i < n; i++)
            {
                double T = i * dt, t = T % Length;
                bool lapStart = i > 0 && Math.Abs(t) < 1e-9;
                var f = new TelFrame();
                var evs = new List<TelEvent>();
                void Ev(uint type, Action<TelEvent> fill) { var e = new TelEvent { Seq = ++evSeq, Frame = (uint)i, Type = type }; fill(e); evs.Add(e); }

                // ---- driving script ----
                double speed, steer = 0, throttle = 0; uint flags = 0;
                if (t < 0.5) { speed = 0; }
                else if (t < 1.0) { speed = 0; flags |= TelFrame.FlagStarting; }
                else if (t < 6.0) { speed = Math.Min(25.0, 5.0 * (t - 1.0)); throttle = 1.0; }
                else if (t < 15.0) { speed = 25.0; throttle = 0.4; }
                else if (t < 17.0) { speed = Math.Max(0.0, 25.0 - 12.5 * (t - 15.0)); throttle = -1.0; }
                else speed = 0;
                if (t >= 1.0) flags |= TelFrame.FlagEngineRunning;
                if (t >= 6.0 && t < 8.0) steer = 0.5;
                if (t >= 7.0 && t < 7.5) flags |= TelFrame.FlagGripLimit;
                if (t >= 7.2 && t < 7.4) flags |= TelFrame.FlagSkid;
                int g = t < 1.0 ? 1 : t < 2.5 ? 2 : t < 4.5 ? 3 : 4;
                if (t >= 17.0) g = 1;
                gear = g;
                double rpm = t < 1.0 ? (t < 0.5 ? 0 : 850) : g <= 1 ? 1050 : 1050 + 4950 * Math.Min(1.0, ((t - (g == 2 ? 1.0 : g == 3 ? 2.5 : 4.5)) / (g == 4 ? 4.0 : 1.5)));
                double yaw = speed > 0.5 ? (steer != 0 ? 31.0 * steer / Math.Max(speed, 12.0) : 0) : 0;
                heading += yaw * dt;
                // airborne hop
                if (t >= 11.0 && t < 11.6) { flags |= TelFrame.FlagAirborne; double u = t - 11.0; vy = 3.0 - 15.0 * u; airY = 3.0 * u - 7.5 * u * u; }
                else { vy = 0; airY = 0; }
                double vx = speed * Math.Sin(heading), vz = speed * Math.Cos(heading);
                // sideways jolt on the impact frame
                if (Math.Abs(t - 9.5) < dt / 2) { vx += 6.0 * Math.Cos(heading); vz -= 6.0 * Math.Sin(heading); }
                x += vx * dt; z += vz * dt; y = airY;
                bool flatFR = t >= 13.5 && t < 17.5;

                simFrame++;
                f["seq"] = ++seq; f["frame"] = simFrame; f["proxy_frame"] = i; f["sim_time"] = T; f["sim_dt"] = dt; f["dt"] = dt;
                f["step_count"] = 1; f["player_present"] = 1; f["obj_addr"] = 0x1000; f["ent_addr"] = 0x2000;
                f["pos_0"] = x; f["pos_1"] = y; f["pos_2"] = z;
                double ch = Math.Cos(heading), sh = Math.Sin(heading);
                // rows right / up / forward for a car yawed by heading (pitch = roll = 0): heading = atan2(rot[6], rot[8])
                double[] rot = { ch, 0, -sh, 0, 1, 0, sh, 0, ch };
                for (int k = 0; k < 9; k++) f["rot_" + k] = rot[k];
                f["velocity_0"] = vx; f["velocity_1"] = vy; f["velocity_2"] = vz; f["speed"] = Math.Sqrt(vx * vx + vy * vy + vz * vz);
                f["yaw_rate"] = yaw; f["pitch_rate"] = 0; f["roll_rate"] = 0;
                f["steer"] = steer; f["throttle"] = throttle; f["gear_dir"] = 1; f["gear_lever"] = 3; f["gear"] = g; f["rpm"] = rpm;
                f["flags"] = flags; f["surface"] = t > 10 && t < 12 ? 3 : 5; f["ground_normal_1"] = 1; f["clearance"] = 0.3 + airY;
                for (int k = 0; k < 4; k++) { f["armour_" + k] = 100; f["armour_max_" + k] = 100; f["chassis_" + k] = 100; f["chassis_max_" + k] = 100; }
                for (int w = 0; w < 6; w++)
                {
                    bool present = w != 2 && w != 3;
                    f["wheel" + w + "_present"] = present ? 1 : 0; f["wheel" + w + "_hp"] = 100; f["wheel" + w + "_hp_max"] = 100;
                    f["wheel" + w + "_grip"] = 1.0; f["wheel" + w + "_unloaded"] = (flags & TelFrame.FlagAirborne) != 0 ? 1 : 0;
                    f["wheel" + w + "_flat"] = (w == 1 && flatFR) ? 1 : 0;
                }
                f["weapon_row"] = 0; f["weapon_def"] = 3; f["weapon_ammo"] = 200; f["mass"] = 1800; f["inv_mass"] = 1 / 1800.0; f["health_pct"] = 100;
                f.WeaponName = System.Text.Encoding.ASCII.GetBytes("gmg30cal");
                if (version >= 3) { f["wheelbase"] = 2.9; f["front_track"] = 1.6; f["steer_gain"] = 1 / 5.8; f["grip_sum"] = 4; f["grip_cap"] = 31.36; f["ground_g"] = 9.8; f["event_hooks"] = 0x7f; }

                // ---- events ----
                double Near(double at) => Math.Abs(t - at) < dt / 2 ? 1 : 0;
                if (t >= 8.0 && t < 9.0 && ((int)Math.Round((t - 8.0) * fps) % 6) == 0)
                    Ev(TelEvent.Shot, e => { e.F[0] = 0; e.F[1] = 200; e.F[2] = 4; e.F[3] = 0; e.I[0] = 3; e.I[1] = 1; });
                if (Near(9.5) > 0) Ev(TelEvent.Impact, e => { e.F[0] = (float)(6 * ch); e.F[1] = 0; e.F[2] = (float)(-6 * sh); e.F[3] = 40; e.I[0] = 1; e.I[1] = 1; });
                if (Near(12.5) > 0) Ev(TelEvent.Explosion, e => { e.F[0] = (float)x + 30; e.F[1] = 0; e.F[2] = (float)z; e.F[3] = 30; var nm = TelEvent.PackName("xcar"); e.I[0] = nm.lo; e.I[1] = nm.hi; });
                if (version >= 3)
                {
                    if (Near(14.0) > 0)
                    {
                        Ev(TelEvent.SoundStart, e => { e.F[0] = 11025; e.F[1] = 100; e.F[2] = (float)x + 40; e.F[3] = 0; e.F[4] = (float)z; e.F[5] = 0; var nm = TelEvent.PackName("whcan"); e.I[0] = nm.lo; e.I[1] = nm.hi; e.I[2] = 0 | 0x200 | (60 << 16); e.I[3] = 0x3000; e.I[4] = 0x4000; });
                        Ev(TelEvent.DamageSide, e => { e.F[0] = 30; e.F[1] = 12; e.F[2] = 1; e.F[3] = 0.5f; e.F[4] = 0; e.I[0] = 2; e.I[1] = 1; e.I[2] = 1; e.I[3] = 1; e.I[4] = 1; });
                        Ev(TelEvent.WeaponUi, e => { e.I[0] = 0; });
                    }
                    if (Near(7.2) > 0) Ev(TelEvent.SoundStart, e => { e.F[0] = 11025; e.F[1] = 50; var nm = TelEvent.PackName("tskid2"); e.I[0] = nm.lo; e.I[1] = nm.hi; e.I[2] = 2 | 0x100 | 0x200 | (70 << 16); e.I[3] = 0x1000; e.I[4] = 0x5000; });
                    if (Near(7.4) > 0) Ev(TelEvent.SoundStop, e => { e.F[0] = 0.2f; var nm = TelEvent.PackName("tskid2"); e.I[0] = nm.lo; e.I[1] = nm.hi; e.I[2] = 2 | 0x10000; e.I[3] = 0x1000; e.I[4] = 0x5000; });
                }
                f["event_seq"] = evSeq;
                yield return (T, TelCodec.Encode(f, evs, L));
            }
        }
    }
}
