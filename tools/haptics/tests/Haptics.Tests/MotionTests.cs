using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Haptics;
using Haptics.Core;
using Haptics.Core.Motion;
using Haptics.Effects;
using Haptics.Renderers;
using Haptics.Transport;

namespace Haptics.Tests
{
    /// <summary>
    /// Motion output (docs/MOTION-OUTPUT.md): wire layouts against the schema files and hand-computed fixtures, the 21 layout
    /// assertions of tools/ffb/ffb-telemetry-udp.ps1 -SelfTest ported, the golden tests of section 5.4 (axis maps, rotation,
    /// gravity exclusion, dedupe, resampler, fail-to-neutral timing, status bits), cues, lints, the renderer end to end and a
    /// loopback UDP send.
    /// </summary>
    static class MotionTests
    {
        const double Tol = 1e-4;
        static bool Near(double a, double b, double tol = Tol) => Math.Abs(a - b) <= tol * Math.Max(1.0, Math.Abs(b));

        static MotionParams Params(Action<MotionParams> tweak = null)
        {
            var p = new MotionParams { StartupNeutralS = 0, OutputHz = 100 };
            tweak?.Invoke(p);
            return p;
        }

        /// <summary>The hand fixture: distinctive values on every channel, identity orientation.</summary>
        static MotionFrame Fixture()
        {
            var s = new PhysicsSample
            {
                Surge = -4.0, Sway = 1.5, Heave = 0.2, RollRate = 0.2, PitchRate = 0.1, YawRate = 0.42, Roll = -0.03, Pitch = 0.05, Heading = 0.15,
                VelRight = 3.0, VelUp = 0.1, VelFwd = 19.7, Speed = 20.0, Rpm = 4321, Gear = 3, Throttle = 0.8, Brake = 0, Steer = 0.5,
                Texture = 0.25, Mass = 1800, WeaponName = "gmg30cal", Flags = 0x801, Surface = 5,
            };
            s.Susp = new[] { 0.01, 0.02, 0.03, 0.04 }; s.Skid = new[] { 0.0, 1.0, 0.0, 1.0 };
            s.PosWorld = new[] { 10.5, 2.25, -7.75 };
            return new MotionFrame { Seq = 77, Status = 0x00030501, TSim = 1.234, Clock = 1.234, S = s, CueSurge = 0.5, CueSway = -0.25, CueHeave = 1.0, Gain = 1, RaceOn = true, Distance = 123.5 };
        }

        static JsonObject Schema(string file) => JsonNode.Parse(File.ReadAllText(Path.Combine(T.HapticsRoot, "schema", file))) as JsonObject;

        static object Read(byte[] b, int off, string type)
        {
            switch (type)
            {
                case "f32": return (double)BitConverter.ToSingle(b, off);
                case "i32": return (double)BitConverter.ToInt32(b, off);
                case "u32": return (double)BitConverter.ToUInt32(b, off);
                case "u16": return (double)BitConverter.ToUInt16(b, off);
                case "u8": return (double)b[off];
                case "s8": return (double)(sbyte)b[off];
                case "char4": return Encoding.ASCII.GetString(b, off, 4).TrimEnd('\0');
                case "char16": return Encoding.ASCII.GetString(b, off, 16).TrimEnd('\0');
            }
            throw new ArgumentException(type);
        }

        /// <summary>Every schema field of the format decoded from the packet and compared with the expected table; every field must be in the table.</summary>
        static void AgainstSchema(string label, byte[] pkt, JsonArray fields, Dictionary<string, object> expect)
        {
            var bad = new List<string>(); int n = 0;
            foreach (var f in fields.OfType<JsonArray>())
            {
                int off = (int)f[0]; string type = (string)f[1], name = (string)f[2];
                if (name == "id" && off >= pkt.Length) continue;          // optional trailing ID
                n++;
                if (!expect.TryGetValue(name, out var want)) { bad.Add(name + ": not in the fixture table"); continue; }
                var got = Read(pkt, off, type);
                bool ok = want is string ws ? (string)got == ws : Near((double)got, Convert.ToDouble(want));
                if (!ok) bad.Add(name + "@" + off + " = " + got + " (want " + want + ")");
            }
            T.Check(label + ": all " + n + " schema fields at their offsets hold the hand-computed values", bad.Count == 0, string.Join("; ", bad.Take(6)));
        }

        static Dictionary<string, object> D(params object[] kv) { var d = new Dictionary<string, object>(); for (int i = 0; i < kv.Length; i += 2) d[(string)kv[i]] = kv[i + 1]; return d; }

        public static void Run()
        {
            Layouts();
            Ported();
            Golden();
            CuesAndSafety();
            Lints();
            RendererEndToEnd();
            RealTimeOutput();
        }

        // ------------------------------------------------------------------------------------------------ real time
        static void RealTimeOutput()
        {
            T.Section("Real-time loop (B4): Motion.Udp on its own output thread, LoopStats, ChunkedDoubles (2 s of wall clock)");
            var cd = new ChunkedDoubles();
            for (int i = 0; i < 200000; i++) cd.Add(i * 0.5);
            T.Check("ChunkedDoubles: 200,000 values across chunks read back in order", cd.Count == 200000 && cd[0] == 0 && cd[65535] == 65535 * 0.5 && cd[65536] == 65536 * 0.5 && cd[199999] == 199999 * 0.5, "");
            var h = LoopStats.Histogram(new[] { 0.1, 0.2, 9.0, 0.3 });
            T.Check("LoopStats.Histogram counts the misses over 8 ms", h.StartsWith("4 updates") && h.EndsWith("missed (>8 ms): 1"), h);

            var dir = T.TempDir("motion-rt");
            var set = EffectSet.Load();
            var p = Session.Build(set, new string[0], dir, "rt", false, 250);
            var mr = Open(dir, "rt", new JsonObject { ["select"] = "native" });
            p.Renderers.Add(mr);
            p.RealTime = true;
            var d = new Derive(); p.Core.Configure(d);
            p.Run(Sources.FromDatagrams(Synthetic.Session(3).Take(120), d, TelCodec.Default()));   // 2 s at 60 fps, paced
            mr.Close();
            var nat = RecordingReader.Load(mr.Logs.First(l => l.kind == "i76motion").path).Records;
            var seq = nat.Select(x => BitConverter.ToUInt32(x.data, 8)).ToList();
            T.Check("about 100 ticks per second of wall clock, seq contiguous, shutdown packet last",
                nat.Count >= 180 && nat.Count <= 215 && seq.Zip(seq.Skip(1), (x, y) => y == x + 1).All(b => b) && (BitConverter.ToUInt32(nat.Last().data, 12) & 0x80000000u) != 0,
                nat.Count + " packets");
            var g = mr.SendGapsMs; Array.Sort(g);
            double med = g.Length > 0 ? g[g.Length / 2] : 0;
            T.Check("ticks are sent from the output thread on a 10 ms schedule (median gap 10 +- 1 ms; the core grid gave 8 / 12)",
                g.Length > 150 && Math.Abs(med - 10.0) < 1.0 && mr.Summary().Contains("own output thread"), "median " + med.ToString("0.00") + " ms over " + g.Length + " gaps");
            T.Check("the pipeline logged a lateness sample per core update", p.Stats != null && p.Stats.Count == p.Updates && p.Stats.Report().Contains("stage ms per update"), p.Stats?.Histogram() ?? "no stats");
        }

        // ------------------------------------------------------------------------------------------------ layouts
        static void Layouts()
        {
            T.Section("motion wire layouts vs schema/*.json and hand-computed fixtures");
            var f = Fixture();
            var wire = Schema("motion-wire.json")["formats"] as JsonObject;
            var im = Schema("i76motion.json");
            T.Check("schema i76motion: magic I76M, version 1, size 144, port 7677",
                (string)im["magic"] == "I76M" && (int)im["version"] == 1 && (int)im["size"] == 144 && (int)im["default_port"] == 7677, "");

            var i76 = I76MotionPacket.Build(f);
            var p2 = OutSimPacket.Pack2(f, 1, "body", new MotionParams());
            var c64 = OutSimPacket.Classic(f, 0, "body"); var c68 = OutSimPacket.Classic(f, 7, "body");
            var og = OutSimPacket.OutGauge(f, 0); var og96 = OutSimPacket.OutGauge(f, 3);
            var sled = ForzaPacket.Build(f, false, new MotionParams()); var dash = ForzaPacket.Build(f, true, new MotionParams());
            T.Check("sizes: i76motion 144, OutSim 64 / 68 with ID, OutSimPack2 280, OutGauge 92 / 96, Forza Sled 232 / Dash 311",
                i76.Length == 144 && c64.Length == 64 && c68.Length == 68 && p2.Length == 280 && og.Length == 92 && og96.Length == 96 && sled.Length == 232 && dash.Length == 311,
                string.Join(" ", new[] { i76, c64, c68, p2, og, og96, sled, dash }.Select(x => x.Length)));
            foreach (var (name, pkt) in new[] { ("lfs-classic", c64), ("lfs-pack2", p2), ("outgauge", og), ("forza-sled", sled), ("forza-dash", dash) })
            {
                var sch = wire[name] as JsonObject;
                T.Check("schema " + name + " size " + (int)sch["size"] + " = encoder", (int)sch["size"] == pkt.Length, pkt.Length.ToString());
            }

            AgainstSchema("i76motion", i76, im["fields"] as JsonArray, D(
                "magic", "I76M", "version", 1, "size", 144, "seq", 77, "status", 0x00030501, "t_sim", 1.234,
                "surge", -4.0, "sway", 1.5, "heave", 0.2, "roll_rate", 0.2, "pitch_rate", 0.1, "yaw_rate", 0.42, "roll", -0.03, "pitch", 0.05, "heading", 0.15,
                "speed", 20.0, "rpm", 4321, "gear", 2.0, "throttle", 0.8, "brake", 0.0, "steer", 0.5,
                "susp_fl", 0.01, "susp_fr", 0.02, "susp_rl", 0.03, "susp_rr", 0.04, "skid_fl", 0, "skid_fr", 1, "skid_rl", 0, "skid_rr", 1,
                "texture", 0.25, "cue_surge", 0.5, "cue_sway", -0.25, "cue_heave", 1.0, "vel_right", 3.0, "vel_up", 0.1, "vel_fwd", 19.7, "reserved", 0));

            // LFS, frame "body": X right = sway + cue, Y forward = surge + cue, Z up = heave + cue; AngVel (pitch, roll, -yaw); Heading = -heading
            var main = D("angvel_x", 0.1, "angvel_y", 0.2, "angvel_z", -0.42, "heading", -0.15, "pitch", 0.05, "roll", -0.03,
                         "accel_x", 1.25, "accel_y", -3.5, "accel_z", 1.2, "vel_x", 3.0, "vel_y", 19.7, "vel_z", 0.1,
                         "pos_x", 10.5 * 65536, "pos_y", -7.75 * 65536, "pos_z", 2.25 * 65536);
            var classic = new Dictionary<string, object>(main) { ["time"] = 1234 };
            AgainstSchema("lfs-classic (frame body)", c64, wire["lfs-classic"]["fields"] as JsonArray, classic);
            var pk = new Dictionary<string, object>(main)
            {
                ["header"] = "LFST", ["id"] = 1, ["time"] = 1234, ["throttle"] = 0.8, ["brake"] = 0.0, ["input_steer"] = 0.38, ["clutch"] = 0, ["handbrake"] = 0,
                ["gear"] = 3, ["sp1"] = 0, ["sp2"] = 0, ["sp3"] = 0, ["engine_ang_vel"] = 4321 * 2 * Math.PI / 60, ["max_torque_at_vel"] = 0,
                ["current_lap_dist"] = 123.5, ["indexed_distance"] = 0, ["steer_torque"] = 0, ["spare"] = 0,
            };
            // wheels RL RR FL FR <- our FL FR RL RR: susp_deflect = -susp_offset, load = m g / 4, slip_fraction 255 x skid
            double[] defl = { -0.03, -0.04, -0.01, -0.02 }; int[] slip = { 0, 255, 0, 255 };
            for (int w = 0; w < 4; w++)
            {
                string p = "w" + w + "_";
                pk[p + "susp_deflect"] = defl[w]; pk[p + "steer"] = 0; pk[p + "x_force"] = 0; pk[p + "y_force"] = 0; pk[p + "vertical_load"] = 1800 * 9.8 / 4;
                pk[p + "ang_vel"] = 0; pk[p + "lean_rel_to_road"] = 0; pk[p + "air_temp"] = 20; pk[p + "slip_fraction"] = slip[w]; pk[p + "touching"] = 1;
                pk[p + "spare"] = 0; pk[p + "slip_ratio"] = 0; pk[p + "tan_slip_angle"] = 0;
            }
            AgainstSchema("lfs-pack2 (frame body)", p2, wire["lfs-pack2"]["fields"] as JsonArray, pk);
            AgainstSchema("outgauge", og, wire["outgauge"]["fields"] as JsonArray, D(
                "time", 1234, "car", "I76 ", "flags", 0, "gear", 3, "plid", 0, "speed", 20.0, "rpm", 4321, "turbo", 0, "eng_temp", 0, "fuel", 0,
                "oil_pressure", 0, "oil_temp", 0, "dash_lights", 1 | 4 | 2048 | 131072, "show_lights", 0, "throttle", 0.8, "brake", 0.0, "clutch", 0,
                "display1", "gmg30cal", "display2", ""));
            var fz = D("is_race_on", 1, "timestamp_ms", 1234, "engine_max_rpm", 7000, "engine_idle_rpm", 850, "current_engine_rpm", 4321,
                "accel_x", 1.25, "accel_y", 1.2, "accel_z", -3.5, "vel_x", 3.0, "vel_y", 0.1, "vel_z", 19.7, "angvel_x", 0.1, "angvel_y", 0.42, "angvel_z", 0.2,
                "yaw", 0.15, "pitch", 0.05, "roll", -0.03, "car_ordinal", 1976, "car_class", 3, "car_pi", 500, "drivetrain", 1, "num_cylinders", 8);
            string[] W4 = { "fl", "fr", "rl", "rr" };
            for (int w = 0; w < 4; w++)
            {
                double su = new[] { 0.01, 0.02, 0.03, 0.04 }[w], sl = w % 2 == 1 ? 1.5 : 0;
                fz["norm_susp_travel_" + W4[w]] = 0.5 + su / (2 * 0.0875); fz["tire_slip_ratio_" + W4[w]] = sl; fz["wheel_rot_speed_" + W4[w]] = 20.0 / 0.35;
                fz["wheel_on_rumble_" + W4[w]] = 0; fz["wheel_in_puddle_" + W4[w]] = 0; fz["surface_rumble_" + W4[w]] = 0.25; fz["tire_slip_angle_" + W4[w]] = sl;
                fz["tire_combined_slip_" + W4[w]] = sl; fz["susp_travel_m_" + W4[w]] = su;
            }
            AgainstSchema("forza-sled", sled, wire["forza-sled"]["fields"] as JsonArray, fz);
            var fd = new Dictionary<string, object>(fz)
            {
                ["pos_x"] = 10.5, ["pos_y"] = 2.25, ["pos_z"] = -7.75, ["speed"] = 20.0, ["power"] = 0, ["torque"] = 0, ["boost"] = 1, ["fuel"] = 1, ["distance"] = 123.5,
                ["best_lap"] = 0, ["last_lap"] = 0, ["current_lap"] = 0, ["race_time"] = 1.234, ["lap"] = 0, ["race_pos"] = 1, ["accel"] = 204, ["brake"] = 0, ["clutch"] = 0,
                ["handbrake"] = 0, ["gear"] = 3, ["steer"] = 64, ["driving_line"] = 0, ["ai_brake_diff"] = 0,
            };
            foreach (var w in W4) fd["tire_temp_" + w] = 0;
            AgainstSchema("forza-dash", dash, wire["forza-dash"]["fields"] as JsonArray, fd);

            // world frame: identity orientation = body; heading 90 deg moves body forward onto world +x = LFS X
            var cw = OutSimPacket.Classic(f, 0, "world");
            T.Check("lfs world frame with identity rot equals body frame", cw.Skip(4).SequenceEqual(c64.Skip(4)), "");
            var f90 = Fixture(); f90.S.Rot = new double[] { 0, 0, -1, 0, 1, 0, 1, 0, 0 };    // heading 90: right = -z, forward = +x
            var w90 = OutSimPacket.Classic(f90, 0, "world");
            T.Check("lfs world frame, heading 90: forward accel (-3.5) lands on LFS X, right accel (1.25) on -Y",
                Near(BitConverter.ToSingle(w90, 28), -3.5) && Near(BitConverter.ToSingle(w90, 32), -1.25) && Near(BitConverter.ToSingle(w90, 36), 1.2),
                BitConverter.ToSingle(w90, 28) + " " + BitConverter.ToSingle(w90, 32) + " " + BitConverter.ToSingle(w90, 36));
            T.Check("lfs world frame, heading 90: yaw rate stays on Z (-0.42), pitch rate (about right) moves to -Y",
                Near(BitConverter.ToSingle(w90, 12), -0.42) && Near(BitConverter.ToSingle(w90, 8), -0.1) && Near(BitConverter.ToSingle(w90, 4), 0.2),
                BitConverter.ToSingle(w90, 4) + " " + BitConverter.ToSingle(w90, 8) + " " + BitConverter.ToSingle(w90, 12));
        }

        // ------------------------------------------------------------------------------------------------ ported 21
        static void Ported()
        {
            T.Section("ported: tools/ffb/ffb-telemetry-udp.ps1 -SelfTest (21 assertions, signs per docs/MOTION-OUTPUT.md 3.1)");
            // the script's fake sample: speed 20, steer 0.5, throttle 0.8, yaw 0.42, v (3.0, 0.1, 19.7), world accel (1.5, 0.2, -4.0), heading 0.15
            var f = Fixture(); f.CueSurge = f.CueSway = f.CueHeave = 0; f.S.Pitch = 0; f.S.Roll = 0;
            var c64 = OutSimPacket.Classic(f, 0, "world"); var p2 = OutSimPacket.Pack2(f, 1, "world", new MotionParams());
            var og = OutSimPacket.OutGauge(f, 0); var ogid = OutSimPacket.OutGauge(f, 7);
            T.Check("classic OutSim is exactly 64 bytes", c64.Length == 64, c64.Length.ToString());
            T.Check("OutSimPack2 (Opts 1ff) is exactly 280 bytes", p2.Length == 280, "");
            T.Check("OutSimPack2 starts with the LFST magic", Encoding.ASCII.GetString(p2, 0, 4) == "LFST", "");
            T.Check("OutSimPack2 carries the configured ID", BitConverter.ToInt32(p2, 4) == 1, "");
            T.Check("OutGauge is exactly 92 bytes", og.Length == 92, "");
            T.Check("OutGauge with an ID is 96 bytes", ogid.Length == 96, "");
            T.Check("classic Time at +0", BitConverter.ToUInt32(c64, 0) == 1234, "");
            T.Check("classic yaw rate at +12 (AngVel Z, LFS anticlockwise = -0.42 for a right turn; the script sent +)", Near(BitConverter.ToSingle(c64, 12), -0.42), BitConverter.ToSingle(c64, 12).ToString());
            T.Check("classic Heading at +16 (LFS anticlockwise = -heading; the script sent +)", Near(BitConverter.ToSingle(c64, 16), -0.15), "");
            T.Check("classic Pitch / Roll at +20 / +24 (now filled from rot; zero on a level car)", BitConverter.ToSingle(c64, 20) == 0 && BitConverter.ToSingle(c64, 24) == 0, "");
            T.Check("Accel X at +28 is world X", Near(BitConverter.ToSingle(c64, 28), 1.5), "");
            T.Check("Accel Y at +32 is I76 z (forward)", Near(BitConverter.ToSingle(c64, 32), -4.0), "");
            T.Check("Accel Z at +36 is I76 y (up)", Near(BitConverter.ToSingle(c64, 36), 0.2), "");
            T.Check("Vel Y at +44 is I76 z (forward)", Near(BitConverter.ToSingle(c64, 44), 19.7), "");
            T.Check("pack2 Throttle at +72", Near(BitConverter.ToSingle(p2, 72), 0.8), "");
            T.Check("pack2 Brake at +76 is zero on positive throttle", BitConverter.ToSingle(p2, 76) == 0, "");
            T.Check("pack2 SteerTorque at +272 (zero: no steer torque in the motion state; the script sent its synthesised wheel force)", BitConverter.ToSingle(p2, 272) == 0, "");
            T.Check("OutGauge Car tag at +4", Encoding.ASCII.GetString(og, 4, 4) == "I76 ", "");
            T.Check("OutGauge Speed at +12 in m/s", Near(BitConverter.ToSingle(og, 12), 20.0), "");
            T.Check("OutGauge Throttle at +48", Near(BitConverter.ToSingle(og, 48), 0.8), "");
            // braking: the signed axis splits in Derive (throttle < 0 -> brake)
            var md = new MotionDerive(new MotionParams());
            var vs = State(throttle: -0.6);
            var s = md.Derive(vs, 0);
            var fb = Fixture(); fb.S = s;
            var ob = OutSimPacket.OutGauge(fb, 0);
            T.Check("negative throttle becomes Brake, not Throttle", BitConverter.ToSingle(ob, 48) == 0 && Near(BitConverter.ToSingle(ob, 52), 0.6), BitConverter.ToSingle(ob, 48) + " / " + BitConverter.ToSingle(ob, 52));
        }

        // ------------------------------------------------------------------------------------------------ golden 5.4
        static VehicleState State(double t = 0, uint frame = 1, double throttle = 0, double[] rot = null, Vec3? accWorld = null, Vec3? vel = null,
                                  uint flags = 1, int stepCount = 1, double yaw = 0, Vec3? pos = null)
        {
            var st = new VehicleState
            {
                T = t, SimFrame = frame, Present = true, HasOrientation = true, Throttle = throttle, Flags = flags, StepCount = stepCount, SimDt = 1.0 / 24,
                AccEngineWorld = accWorld ?? new Vec3(0, 0, 0), VelWorld = vel ?? new Vec3(0, 0, 0), YawRate = yaw, Gear = 2, PosWorld = pos ?? new Vec3(0, 0, 0),
            };
            if (rot != null) st.Rot = (double[])rot.Clone();
            st.Speed = st.VelWorld.Length;
            return st;
        }

        static double[] RotFor(double h, double p, double r)
        {
            // same construction as motion/make_synthetic.py rot_rows
            double[] f0 = { Math.Sin(h), 0, Math.Cos(h) }, r0 = { Math.Cos(h), 0, -Math.Sin(h) }, u0 = { 0, 1, 0 };
            var f1 = new double[3]; var u1 = new double[3]; var r2 = new double[3]; var u2 = new double[3];
            for (int i = 0; i < 3; i++) { f1[i] = f0[i] * Math.Cos(p) + u0[i] * Math.Sin(p); u1[i] = u0[i] * Math.Cos(p) - f0[i] * Math.Sin(p); }
            for (int i = 0; i < 3; i++) { r2[i] = r0[i] * Math.Cos(r) - u1[i] * Math.Sin(r); u2[i] = u1[i] * Math.Cos(r) + r0[i] * Math.Sin(r); }
            return r2.Concat(u2).Concat(f1).ToArray();
        }

        static void Golden()
        {
            T.Section("motion golden tests (MOTION-OUTPUT 5.4)");
            // axis map: world acceleration (1.5, 0.2, -4.0), identity rot
            var md = new MotionDerive(new MotionParams());
            var s = md.Derive(State(accWorld: new Vec3(1.5, 0.2, -4.0)), 0);
            T.Check("axis map: world accel (1.5, 0.2, -4.0), identity rot -> sway 1.5, heave 0.2, surge -4.0", Near(s.Sway, 1.5) && Near(s.Heave, 0.2) && Near(s.Surge, -4.0), s.Sway + " " + s.Heave + " " + s.Surge);
            var fr = new MotionFrame { S = s, TSim = 0 };
            var c = OutSimPacket.Classic(fr, 0, "world"); var fz = ForzaPacket.Build(fr, false, null);
            T.Check("axis map: OutSim X / Y / Z = 1.5 / -4.0 / 0.2", Near(BitConverter.ToSingle(c, 28), 1.5) && Near(BitConverter.ToSingle(c, 32), -4.0) && Near(BitConverter.ToSingle(c, 36), 0.2), "");
            T.Check("axis map: Forza Acceleration X / Y / Z (sway / heave / surge) = 1.5 / 0.2 / -4.0", Near(BitConverter.ToSingle(fz, 20), 1.5) && Near(BitConverter.ToSingle(fz, 24), 0.2) && Near(BitConverter.ToSingle(fz, 28), -4.0), "");
            T.Check("FFB accel_body (right, up, forward) is used directly while ffb_present", new Func<bool>(() =>
            {
                var st = State(accWorld: new Vec3(9, 9, 9)); st.FfbPresent = true; st.AccBodyFfb = new Vec3(0.5, -0.25, -9.5);
                var x = new MotionDerive(new MotionParams()).Derive(st, 0);
                return Near(x.Sway, 0.5) && Near(x.Heave, -0.25) && Near(x.Surge, -9.5);
            })(), "");

            // rotation: heading 90 deg - world +x is body forward
            var r90 = RotFor(Math.PI / 2, 0, 0);
            var s90 = new MotionDerive(new MotionParams()).Derive(State(rot: r90, accWorld: new Vec3(2.0, 0, 0)), 0);
            T.Check("rotation: heading 90 deg, world +x accel 2.0 -> surge 2.0, sway 0", Near(s90.Surge, 2.0) && Math.Abs(s90.Sway) < 1e-9, s90.Surge + " / " + s90.Sway);
            T.Check("rotation: heading = atan2(rot6, rot8) = +90 deg (clockwise from above)", Near(s90.Heading, Math.PI / 2), s90.Heading.ToString());
            var rb = RotFor(0.3, -0.05, 0.04);
            var sb = new MotionDerive(new MotionParams()).Derive(State(rot: rb), 0);
            T.Check("angles: pitch = asin(rot7) (+ nose up), roll = -asin(rot1) (+ right side down) recover the construction", Near(sb.Pitch, -0.05) && Near(sb.Roll, 0.04, 1e-3) && Near(sb.Heading, 0.3), sb.Pitch + " " + sb.Roll + " " + sb.Heading);

            // gravity exclusion: parked on a 10 deg slope, nose up
            var slope = new MotionDerive(new MotionParams()).Derive(State(rot: RotFor(0.7, 10 * Math.PI / 180, 0)), 0);
            T.Check("gravity excluded: parked on a 10 deg slope -> surge / sway / heave 0, pitch 0.1745", slope.Surge == 0 && slope.Sway == 0 && slope.Heave == 0 && Near(slope.Pitch, 0.174533), slope.Pitch.ToString());
            var airD = new MotionDerive(new MotionParams());
            var air = airD.Derive(State(accWorld: new Vec3(0, -9.8, 0), flags: 1 | TelFrame.FlagAirborne), 0);
            T.Check("airborne_zero_physics: free fall (accel y -9.8, flags & 4) -> physics channels 0", air.Surge == 0 && air.Sway == 0 && air.Heave == 0, air.Heave.ToString());

            // dedupe: one state, then 4 repeats with step_count 0 (60-120 fps under I76_FIXED_STEP), then a new one
            var core = new MotionCore(Params());
            var first = State(t: 1.0, frame: 10, accWorld: new Vec3(0, 0, -5));
            core.Feed(first, null, 1.0);
            VehicleState rep = null;
            for (int k = 1; k <= 4; k++) { rep = State(t: 1.0 + k / 120.0, frame: (uint)(10 + k), accWorld: new Vec3(0, 0, -5), stepCount: 0); core.Feed(rep, null, 1.0 + k / 120.0); core.Feed(rep, null, 1.0 + k / 120.0 + 0.004); }   // + the 250 Hz sub-step re-feed
            T.Check("dedupe: 5 frames of one physics pose (step_count 0 on 4) -> one derive", core.Derive.Derived == 1 && core.Derive.Repeats == 4, core.Derive.Derived + " derived, " + core.Derive.Repeats + " repeats");
            core.Feed(State(t: 1.0 + 5 / 120.0, frame: 15, accWorld: new Vec3(0, 0, -5), stepCount: 1, vel: new Vec3(0, 0, 1)), null, 1.0 + 5 / 120.0);
            T.Check("dedupe: the next stepped frame is a new state; fixed-step mode recognised (dt = 1/24, not the 41.7 ms render gap by luck)",
                core.Derive.Derived == 2 && core.Derive.FixedStepMode && Near(core.Derive.Last.Dt, 1.0 / 24), core.Derive.Last.Dt.ToString());

            // resampler: linear ramp sampled at 24 Hz, output 100 Hz, interp mode = the ramp delayed by one step
            var rs = new Resampler { Mode = "interp" };
            double maxErr = 0; int nOut = 0;
            Func<double, double> ramp = t => 3.0 * t - 1.0;
            double step = 1.0 / 24;
            for (int k = 0; k < 48; k++)
            {
                double tk = k * step;
                rs.Push(new PhysicsSample { Clock = tk, SimT = tk, Surge = ramp(tk), Pitch = 0.01 * ramp(tk) });
                if (k < 2) continue;
                for (double t = Math.Ceiling(tk * 100 - 1e-9) / 100; t < tk + step - 1e-9; t += 0.01)
                {
                    var o = rs.At(t);
                    maxErr = Math.Max(maxErr, Math.Abs(o.Surge - ramp(t - step)));
                    maxErr = Math.Max(maxErr, Math.Abs(o.Pitch - 0.01 * ramp(t - step)));
                    nOut++;
                }
            }
            T.Check("resampler: 24 -> 100 Hz linear interpolation of a ramp, error < 1e-6 (one step of latency)", maxErr < 1e-6 && nOut > 150, "max err " + maxErr.ToString("E2") + " over " + nOut + " ticks");
            var hz = new Resampler { Mode = "interp" };
            hz.Push(new PhysicsSample { Clock = 0, Heading = 3.10 }); hz.Push(new PhysicsSample { Clock = 0.04, Heading = -3.10 });
            var mid = hz.At(0.06);
            T.Check("resampler: heading interpolates the short way round across +-pi", Math.Abs(Math.Abs(mid.Heading) - Math.PI) < 0.01, mid.Heading.ToString());
            var hold = new Resampler { Mode = "hold", HoldLpHz = 8 };
            hold.Push(new PhysicsSample { Clock = 0, Surge = 0 }); hold.At(0);
            hold.Push(new PhysicsSample { Clock = 0.001, Surge = 1 });
            double tau = 1 / (2 * Math.PI * 8), y = 0;
            for (double t = 0.001; t <= tau + 1e-9; t += 0.001) y = hold.At(t).Surge;
            T.Check("hold: zero-order hold + 8 Hz first-order LP reaches 63% after one time constant", Math.Abs(y - (1 - Math.Exp(-1))) < 0.03, y.ToString("0.000"));

            // fail-to-neutral timing
            NeutralTiming();

            // status bits
            var sc = new MotionCore(Params());
            var stA = State(t: 0, frame: 1, flags: 1 | TelFrame.FlagAirborne | TelFrame.FlagSkid); stA.Surface = 7; stA.Gear = 3;
            sc.Feed(stA, null, 0);
            var tk0 = sc.Pump(0.0).Last();
            T.Check("status: live, airborne, skid, surface 7 in bits 8-15, gear 3 in bits 16-23",
                (tk0.Status & MotionStatus.Live) != 0 && (tk0.Status & MotionStatus.Airborne) != 0 && (tk0.Status & MotionStatus.Skid) != 0 &&
                ((tk0.Status >> 8) & 0xff) == 7 && ((tk0.Status >> 16) & 0xff) == 3, "0x" + tk0.Status.ToString("x8"));
            var dsc = new MotionCore(Params());
            dsc.Feed(State(t: 0, flags: 1 | TelFrame.FlagDestroyed), null, 0);
            var dt0 = dsc.Pump(0.0).Last();
            T.Check("status: destroyed -> bit 3 and neutral (bit 5), not live", (dt0.Status & MotionStatus.Destroyed) != 0 && (dt0.Status & MotionStatus.Neutral) != 0 && (dt0.Status & MotionStatus.Live) == 0, "0x" + dt0.Status.ToString("x8"));
            var sd = sc.ShutdownFrame(1.0);
            T.Check("status: the shutdown tick has bit 31 and zero motion", (sd.Status & MotionStatus.ShuttingDown) != 0 && sd.S.Surge == 0 && sd.S.Roll == 0, "");
        }

        static void NeutralTiming()
        {
            var p = Params(x => { x.StartupNeutralS = 0; x.StaleMs = 250; x.NeutralRampMs = 1000; });
            var core = new MotionCore(p);
            var frames = new List<MotionFrame>();
            // 2 s of a steady turn at 24 Hz (sway 6), then silence until t = 5, then 2 s more
            uint fno = 0;
            for (double t = 0; t < 2.0; t += 1.0 / 24)
            {
                var st = State(t: t, frame: ++fno, accWorld: new Vec3(6, 0, 0), vel: new Vec3(0, 0, 20), pos: new Vec3(0, 0, 20 * t));
                core.Feed(st, null, t); frames.AddRange(core.Pump(t));
            }
            frames.AddRange(core.Pump(5.0));
            for (double t = 5.0; t < 7.5; t += 1.0 / 24)
            {
                var st = State(t: t, frame: ++fno, accWorld: new Vec3(6, 0, 0), vel: new Vec3(0, 0, 20), pos: new Vec3(0, 0, 20 * t));
                frames.AddRange(core.Pump(t - 1e-7)); core.Feed(st, null, t); frames.AddRange(core.Pump(t));
            }
            double lastState = frames.Where(f => f.Clock < 2.0).Max(f => f.Clock);
            var at = new Func<double, MotionFrame>(t => frames.OrderBy(f => Math.Abs(f.Clock - t)).First());
            double lastPhys = Math.Floor(2.0 * 24 - 1e-9) / 24;     // the last state's clock
            T.Check("neutral: full output until stale_ms (250 ms) after the last physics state", Near(at(lastPhys + 0.2).S.Sway, 6.0, 1e-6) && (at(lastPhys + 0.2).Status & MotionStatus.Neutral) == 0, at(lastPhys + 0.2).S.Sway.ToString());
            var half = at(lastPhys + 0.25 + 0.5);
            T.Check("neutral: half way down 0.5 s into the 1 s ramp (sway ~3), bit 5 set", Math.Abs(half.S.Sway - 3.0) < 0.15 && (half.Status & MotionStatus.Neutral) != 0, half.S.Sway.ToString("0.000"));
            var zero = at(lastPhys + 0.25 + 1.05);
            T.Check("neutral: reaches 0 after the 1 s ramp, stays", Math.Abs(zero.S.Sway) < 1e-9 && frames.Where(f => f.Clock > lastPhys + 1.3 && f.Clock < 4.99).All(f => f.S.Sway == 0 && f.Gain == 0), zero.S.Sway.ToString());
            double maxStep = 0;
            for (int k = 1; k < frames.Count; k++) maxStep = Math.Max(maxStep, Math.Abs(frames[k].S.Sway - frames[k - 1].S.Sway));
            T.Check("neutral: never a step (largest change per 10 ms tick <= 6 x 0.01 / 1 s + rounding)", maxStep <= 6 * 0.01 + 1e-6, maxStep.ToString("0.0000"));
            var back = at(5.0 + 1.1);
            T.Check("neutral: recovers with the same ramp (full again ~1 s after data returns), bit 5 clear", Near(back.S.Sway, 6.0, 1e-3) && (back.Status & MotionStatus.Neutral) == 0, back.S.Sway.ToString());
            T.Check("neutral: the gap is reported as paused (bit 4)", (at(3.0).Status & MotionStatus.Paused) != 0, "");
            T.Check("neutral: no impulse cue on resume (no derivative across the gap)", core.Cues.Raised == 0, core.Cues.Raised + " cues");

            var sp = Params(x => { x.StartupNeutralS = 2.0; });
            var c2 = new MotionCore(sp); var f2 = new List<MotionFrame>(); fno = 0;
            for (double t = 0; t < 4.0; t += 1.0 / 24) { c2.Feed(State(t: t, frame: ++fno, accWorld: new Vec3(0, 0, 4), vel: new Vec3(0, 0, t), pos: new Vec3(0, 0, t * t)), null, t); f2.AddRange(c2.Pump(t)); }
            T.Check("startup: neutral for startup_neutral_s (2 s), then a 1 s ramp to full", f2.Where(f => f.Clock < 2.0).All(f => f.S.Surge == 0) && Near(f2.First(f => f.Clock >= 2.5).S.Surge, 2.0, 0.05) && Near(f2.Last().S.Surge, 4.0, 1e-6), "");
        }

        // ------------------------------------------------------------------------------------------------ cues / limiter
        static void CuesAndSafety()
        {
            T.Section("motion cues and limiter");
            var p = Params();
            var cues = new Cues(p);
            var s = new PhysicsSample { Rot = RotFor(Math.PI / 6, 0, 0) };
            var fwd = new[] { Math.Sin(Math.PI / 6), 0, Math.Cos(Math.PI / 6) };
            var hit = new HapticEvent { Type = "IMPACT" }; hit["impact_x"] = -15 * fwd[0]; hit["impact_z"] = -15 * fwd[2]; hit["hp_lost"] = 60; hit["is_player"] = 1;
            cues.OnEvents(new List<HapticEvent> { hit }, 1.0, s);
            var c0 = cues.At(1.0);
            T.Check("IMPACT against travel (60 hp) -> cue_surge -impact_peak (-30), no sway", Near(c0.s, -30) && Math.Abs(c0.w) < 1e-9, c0.s + " / " + c0.w);
            T.Check("IMPACT cue decays with tau 60 ms", Near(cues.At(1.06).s, -30 * Math.Exp(-1), 1e-6), cues.At(1.06).s.ToString());
            cues.OnEvents(new List<HapticEvent> { hit }, 1.1, s);
            T.Check("min_gap_ms 150: a second impact 100 ms later is dropped", cues.Dropped == 1, cues.Dropped.ToString());
            var ai = new HapticEvent { Type = "IMPACT" }; ai["impact_x"] = 1; ai["hp_lost"] = 60; ai["is_player"] = 0;
            cues.OnEvents(new List<HapticEvent> { ai }, 2.0, s);
            T.Check("IMPACT on another car (is_player 0) raises nothing", cues.Raised == 1, cues.Raised.ToString());
            var near = new HapticEvent { Type = "EXPLOSION" }; near["dist"] = 0.5; near["x"] = 1; near["z"] = 0;
            var c2 = new Cues(p); c2.OnEvents(new List<HapticEvent> { near }, 0, new PhysicsSample());
            T.Check("EXPLOSION at 0.5 m: 1/d^2 floored at 3 m -> heave 40 / 9 = 4.44, pushed away from the blast (left)", Near(c2.At(0).h, 40.0 / 9) && c2.At(0).w < 0, c2.At(0).h + " / " + c2.At(0).w);
            var c3 = new Cues(Params(x => x.ExplosionGain = 10000));
            c3.OnEvents(new List<HapticEvent> { near }, 0, new PhysicsSample());
            T.Check("cue_max caps a huge blast at 60", Math.Sqrt(Math.Pow(c3.At(0).h, 2) + Math.Pow(c3.At(0).w, 2)) <= 60 + 1e-9, c3.At(0).h.ToString());
            var c4 = new Cues(p);
            var a = new HapticEvent { Type = "EXPLOSION" }; a["dist"] = 3; a["x"] = 0; a["z"] = -1;
            var b = new HapticEvent { Type = "EXPLOSION" }; b["dist"] = 3; b["x"] = 0; b["z"] = -1;
            c4.OnEvents(new List<HapticEvent> { a, b }, 0, new PhysicsSample());
            T.Check("overlapping cues combine as max, not sum", Near(c4.At(0).h, 40.0 / 9), c4.At(0).h.ToString());
            var c5 = new Cues(p);
            c5.LandingVy = -6; c5.OnPhysics(new PhysicsSample { LandingEdge = true }, 0, "integrator");
            T.Check("LANDING: heave + landing_k x |v_y| = 6 m/s^2", Near(c5.At(0).h, 6.0), c5.At(0).h.ToString());
            var c6 = new Cues(p);
            c6.OnPhysics(new PhysicsSample { ADiffSurge = -360, Surge = 0 }, 0, "integrator");
            T.Check("a_diff residual (wall: -360 m/s^2 in one step) -> impulse cue, x impulse_gain, capped at cue_max (-60)", Near(c6.At(0).s, -60), c6.At(0).s.ToString());
            var c7 = new Cues(p); c7.OnPhysics(new PhysicsSample { ADiffHeave = 140, TakeoffEdge = true }, 0, "integrator");
            T.Check("no impulse cue on a takeoff step", c7.Raised == 0, "");
            var shot = new HapticEvent { Type = "SHOT" }; shot["rounds"] = 1;
            var c8 = new Cues(p); c8.OnEvents(new List<HapticEvent> { shot }, 0, new PhysicsSample());
            T.Check("SHOT recoil is off by default (shot_recoil 0)", c8.Raised == 0, "");

            var lim = new Limiter(Params(), true, true);
            var big = Fixture(); big.S.Surge = 100; big.S.Roll = 1.0; big.CueHeave = 200; big.S.YawRate = 5;
            var o = lim.Apply(big);
            T.Check("limiter clamp: surge 3 g, cue 6 g, rate 2 rad/s, angle 0.35 rad", Near(o.S.Surge, 3 * 9.81) && Near(o.CueHeave, 6 * 9.81) && Near(o.S.YawRate, 2) && Near(o.S.Roll, 0.35), "");
            var f1 = Fixture(); f1.Clock = 1.0; f1.S.Surge = 0; lim = new Limiter(Params(), false, true); lim.Apply(f1);
            var f2 = Fixture(); f2.Clock = 1.01; f2.S.Surge = 50; var o2 = lim.Apply(f2);
            T.Check("limiter slew: max_jerk 400 m/s^3 -> at most 4 m/s^2 per 10 ms tick", Near(o2.S.Surge, 4.0), o2.S.Surge.ToString());
            T.Check("limiter off (software default) passes the frame through untouched", ReferenceEquals(new Limiter(Params(), false, false).Apply(big), big), "");
        }

        // ------------------------------------------------------------------------------------------------ lints
        static void Lints()
        {
            T.Section("motion config lints and files");
            var p = MotionParams.Load(EffectSet.Load().Rig.Json["motion"] as JsonObject);
            T.Check("motion/targets.json loads: flypt, simtools (off), simhub, simhub-forza (off), native", string.Join(",", p.Targets.Select(t => t.Name)) == "flypt,simtools,simhub,simhub-forza,native" &&
                !p.Targets.First(t => t.Name == "simtools").Enabled, string.Join(",", p.Targets.Select(t => t.Name)));
            T.Check("shipped config lints clean (no errors)", !p.Lint().Any(l => l.Error), string.Join("; ", p.Lint()));
            T.Check("defaults: 100 Hz interp, integrator, stale 250 ms, ramp 1 s, clamp_udp off, washout off",
                p.OutputHz == 100 && p.Resample == "interp" && p.AccelSource == "integrator" && p.StaleMs == 250 && p.NeutralRampMs == 1000 && !p.ClampUdp && !p.WashoutEnabled, "");
            var all = p.Targets.ToList();
            T.Check("lint: 4123 shared by flypt (pack2) and simtools (classic) warns", p.Lint(all).Any(l => !l.Error && l.Message.Contains("4123")), "");
            var wide = Params(x => x.ClampAccel = 5 * 9.81);
            T.Check("lint: a rig that widens a clamp is an error", wide.Lint(new MotionTarget[0]).Any(l => l.Error && l.Message.Contains("widen")), "");
            var remote = MotionTarget.From(new JsonObject { ["name"] = "far", ["format"] = "i76motion", ["host"] = "192.168.1.50", ["port"] = 7677 });
            T.Check("lint: a non-loopback host without allow_remote is an error", Params().Lint(new[] { remote }).Any(l => l.Error && l.Message.Contains("loopback")), "");
            var badFrame = MotionTarget.From(new JsonObject { ["name"] = "x", ["format"] = "lfs-classic", ["frame"] = "car" });
            T.Check("lint: unknown frame is an error", Params().Lint(new[] { badFrame }).Any(l => l.Error && l.Message.Contains("frame")), "");
            T.Check("lint: washout enabled (M6, not built) is an error", Params(x => x.WashoutEnabled = true).Lint(new MotionTarget[0]).Any(l => l.Error && l.Message.Contains("M6")), "");
            T.Check("lint: interp below 2 x 24 Hz is an error", Params(x => x.OutputHz = 40).Lint(new MotionTarget[0]).Any(l => l.Error), "");
        }

        // ------------------------------------------------------------------------------------------------ renderer
        static MotionUdpRenderer Open(string dir, string tag, JsonObject cfg)
        {
            var set = EffectSet.Load();
            var r = new MotionUdpRenderer { CaptureFrames = true };
            r.Open(new RendererContext { OutputName = "motion_udp", Config = cfg, Rig = set.Rig, Effects = set, OutDir = dir, Tag = tag, Log = TextWriter.Null });
            return r;
        }

        static void RendererEndToEnd()
        {
            T.Section("Motion.Udp renderer end to end (synthetic session, file sink; loopback UDP)");
            var dir = T.TempDir("motion");
            string[] tags = { "a", "b" };
            foreach (var tag in tags)
            {
                var set = EffectSet.Load();
                var p = Session.Build(set, new string[0], dir, tag, false, 250);
                var mr = Open(dir, tag, new JsonObject { ["select"] = "flypt,simtools,simhub-forza,native" });
                p.Renderers.Add(mr);
                var d = new Derive(); p.Core.Configure(d);
                p.Run(Sources.FromDatagrams(Synthetic.Session(3), d, TelCodec.Default()));
                mr.Close();
                if (tag == "a")
                {
                    var logs = mr.Logs.ToList();
                    T.Check("logs: flypt pack2 + OutGauge, simtools classic + OutGauge, forza dash, native i76motion (6 streams)", logs.Count == 6, string.Join(", ", logs.Select(l => l.target + ":" + l.kind)));
                    var sizes = logs.ToDictionary(l => l.kind + "@" + l.target, l => RecordingReader.Load(l.path).Records.Select(x => x.data.Length).Distinct().ToList());
                    T.Check("logged packet sizes: 280 / 92 / 64 / 92 / 311 / 144",
                        sizes["lfs-pack2@flypt"].SequenceEqual(new[] { 280 }) && sizes["outgauge@flypt"].SequenceEqual(new[] { 92 }) && sizes["lfs-classic@simtools"].SequenceEqual(new[] { 64 }) &&
                        sizes["forza-dash@simhub-forza"].SequenceEqual(new[] { 311 }) && sizes["i76motion@native"].SequenceEqual(new[] { 144 }), string.Join(" ", sizes.Select(kv => kv.Key + "=" + string.Join("/", kv.Value))));
                    var fr = mr.Captured;
                    double dur = fr.Last().Clock - fr.First().Clock;
                    T.Check("100 Hz ticks over the 20 s session (one per 10 ms on the engine clock)", Math.Abs(fr.Count - (dur * 100 + 1)) <= 2 && fr.Zip(fr.Skip(1), (x, y) => y.Clock - x.Clock).Take(fr.Count - 2).All(g => Math.Abs(g - 0.01) < 1e-6), fr.Count + " ticks over " + dur.ToString("0.00") + " s");
                    var nat = RecordingReader.Load(logs.First(l => l.kind == "i76motion").path).Records;
                    var lastPkt = nat.Last().data;
                    T.Check("the last native packet is the shutdown tick (bit 31)", (BitConverter.ToUInt32(lastPkt, 12) & 0x80000000u) != 0, "");
                    T.Check("i76motion seq contiguous in the log", nat.Select(x => BitConverter.ToUInt32(x.data, 8)).Zip(nat.Skip(1).Select(x => BitConverter.ToUInt32(x.data, 8)), (x, y) => y == x + 1).All(b => b), "");
                    T.Check("cues raised on the synthetic session: impulse (9.5 s jolt), landing (11.6 s), explosion (12.5 s)",
                        mr.Core == null && mr.Summary().Contains("landing:1") && mr.Summary().Contains("explosion:1") && mr.Summary().Contains("impulse:1"), mr.Summary().Split('\n')[0]);
                }
            }
            bool same = Directory.GetFiles(dir, "a.*.i76rec").All(fa => File.ReadAllBytes(fa).SequenceEqual(File.ReadAllBytes(Path.Combine(dir, "b" + Path.GetFileName(fa).Substring(1)))));
            T.Check("deterministic: two replays give byte-identical packet logs (engine clock, no wall clock)", same, "");

            // loopback UDP: bind an ephemeral port on 127.0.0.1, point a target file at it, send, receive
            using (var rx = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0)))
            {
                int port = ((IPEndPoint)rx.Client.LocalEndPoint).Port;
                var tf = Path.Combine(dir, "loopback-targets.json");
                File.WriteAllText(tf, "{\"output_hz\": 100, \"targets\": [{\"name\": \"test\", \"format\": \"i76motion\", \"host\": \"127.0.0.1\", \"port\": " + port + "}]}");
                var set = EffectSet.Load();
                var p = Session.Build(set, new string[0], null, "udp", false, 250);
                var mr = Open(null, "udp", new JsonObject { ["targets_file"] = tf, ["send"] = true });
                p.Renderers.Add(mr);
                var d = new Derive(); p.Core.Configure(d);
                int got = 0; bool magicOk = true;
                rx.Client.ReceiveTimeout = 2000;
                var recv = new System.Threading.Thread(() =>
                {
                    var ep = new IPEndPoint(IPAddress.Any, 0);
                    try { while (true) { var b = rx.Receive(ref ep); got++; magicOk &= b.Length == 144 && Encoding.ASCII.GetString(b, 0, 4) == "I76M"; if ((BitConverter.ToUInt32(b, 12) & 0x80000000u) != 0) break; } }
                    catch (SocketException) { }
                });
                recv.Start();
                p.Run(Sources.FromDatagrams(Synthetic.Session(3).Take(240), d, TelCodec.Default()));   // 4 s, max speed
                mr.Close();
                recv.Join(3000);
                T.Check("UDP to 127.0.0.1: every i76motion tick arrives (144 B, I76M), ending with the shutdown packet", got > 300 && magicOk && got == mr.Captured.Count, got + " received, " + mr.Captured.Count + " sent");
            }
        }
    }
}
