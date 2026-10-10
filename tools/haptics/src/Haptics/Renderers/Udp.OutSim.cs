using System;
using System.Text;
using Haptics.Core.Motion;

namespace Haptics.Renderers
{
    /// <summary>Little-endian fixed-size packet writer.</summary>
    public sealed class Packet
    {
        public readonly byte[] B;
        public Packet(int size) { B = new byte[size]; }
        public void F32(int o, double v) { var x = BitConverter.GetBytes((float)v); Array.Copy(x, 0, B, o, 4); }
        public void U32(int o, uint v) { var x = BitConverter.GetBytes(v); Array.Copy(x, 0, B, o, 4); }
        public void I32(int o, int v) { var x = BitConverter.GetBytes(v); Array.Copy(x, 0, B, o, 4); }
        public void U16(int o, ushort v) { var x = BitConverter.GetBytes(v); Array.Copy(x, 0, B, o, 2); }
        public void U8(int o, int v) { B[o] = (byte)Math.Max(0, Math.Min(255, v)); }
        public void S8(int o, int v) { B[o] = unchecked((byte)(sbyte)Math.Max(-127, Math.Min(127, v))); }
        public void Chars(int o, string s, int n) { var a = Encoding.ASCII.GetBytes(s ?? ""); Array.Copy(a, 0, B, o, Math.Min(n, a.Length)); }

        public static uint Ms(double t) => unchecked((uint)(long)Math.Round(t * 1000.0));
        /// <summary>LFS fixed point (1 m = 65536), wrapped into int32 like LFS's own counters.</summary>
        public static int Fixed(double m) => unchecked((int)(long)Math.Round(m * 65536.0));
    }

    /// <summary>
    /// Udp.OutSim: Live For Speed OutSim (classic 64 / 68 B, OutSimPack2 280 B at Opts 1ff) and OutGauge (92 / 96 B) from a
    /// MotionFrame (docs/MOTION-OUTPUT.md 3.1; layouts in schema/motion-wire.json, asserted by the motion tests).
    ///
    /// Axes: LFS X right, Y forward, Z up (right-handed). Body -> LFS: X = sway, Y = surge, Z = heave; angular velocity
    /// (X, Y, Z) = (pitch_rate, roll_rate, -yaw_rate) because LFS rotations are anticlockwise-positive (Z: a left turn).
    /// Heading = -i76motion heading (LFS: anticlockwise from above), Pitch = pitch (anticlockwise from the right = nose up),
    /// Roll = roll (anticlockwise from the front = right side down).
    /// frame "world" (default): Accel / Vel / AngVel rotated into LFS world axes (I'76 world (x, y up, z) -> (X = x, Y = z,
    /// Z = y)), which the LFS developer's forum answer says OutSim uses; "body": car-local. Owner test T2 settles it
    /// (braking must pitch the virtual rig nose-down whatever the heading).
    /// Accelerations on the wire = physics + cues (LFS has no cue channel). Honest accounting: what the engine does not
    /// have (tyre forces, temperatures, clutch, steer torque) is zero.
    /// </summary>
    public static class OutSimPacket
    {
        /// <summary>(X right, Y forward, Z up) body components -> the target's frame.</summary>
        static (double x, double y, double z) Frame(MotionFrame f, string frame, double bx, double by, double bz)
        {
            if (frame != "world") return (bx, by, bz);
            var r = f.S.Rot;
            // LFS-axis car vectors: right_L = (r0, r2, r1), fwd_L = (r6, r8, r7), up_L = (r3, r5, r4)
            return (bx * r[0] + by * r[6] + bz * r[3],
                    bx * r[2] + by * r[8] + bz * r[5],
                    bx * r[1] + by * r[7] + bz * r[4]);
        }

        static void Main(Packet p, int o, MotionFrame f, string frame)
        {
            var s = f.S;
            var av = Frame(f, frame, s.PitchRate, s.RollRate, -s.YawRate);
            var ac = Frame(f, frame, f.TotalSway, f.TotalSurge, f.TotalHeave);
            var ve = Frame(f, frame, s.VelRight, s.VelFwd, s.VelUp);
            p.F32(o + 0, av.x); p.F32(o + 4, av.y); p.F32(o + 8, av.z);
            p.F32(o + 12, -s.Heading); p.F32(o + 16, s.Pitch); p.F32(o + 20, s.Roll);
            p.F32(o + 24, ac.x); p.F32(o + 28, ac.y); p.F32(o + 32, ac.z);
            p.F32(o + 36, ve.x); p.F32(o + 40, ve.y); p.F32(o + 44, ve.z);
            p.I32(o + 48, Packet.Fixed(s.PosWorld[0])); p.I32(o + 52, Packet.Fixed(s.PosWorld[2])); p.I32(o + 56, Packet.Fixed(s.PosWorld[1]));
        }

        public static byte[] Classic(MotionFrame f, int id, string frame = "world")
        {
            var p = new Packet(id != 0 ? 68 : 64);
            p.U32(0, Packet.Ms(f.TSim));
            Main(p, 4, f, frame);
            if (id != 0) p.I32(64, id);
            return p.B;
        }

        /// <summary>LFS gear byte from the i76tel gear (0 R, 1 N, 2.. = 1st..): the same encoding.</summary>
        public static int Gear(int i76gear) => Math.Max(0, i76gear);

        // OutSimPack2 wheel order RL RR FL FR (assumed, docs/MOTION-OUTPUT.md 3.1); our arrays are FL FR RL RR
        static readonly int[] WheelMap = { 2, 3, 0, 1 };

        public static byte[] Pack2(MotionFrame f, int id, string frame, MotionParams prm)
        {
            var p = new Packet(280);
            var s = f.S;
            p.Chars(0, "LFST", 4); p.I32(4, id); p.U32(8, Packet.Ms(f.TSim));
            Main(p, 12, f, frame);
            p.F32(72, s.Throttle); p.F32(76, s.Brake); p.F32(80, s.Steer * (prm?.SteerLockRad ?? 0.76)); p.F32(84, 0); p.F32(88, s.Handbrake ? 1 : 0);
            p.U8(92, Gear(s.Gear));
            p.F32(96, s.Rpm * 2 * Math.PI / 60.0); p.F32(100, 0);
            p.F32(104, f.Distance); p.F32(108, 0);
            bool touching = !s.Airborne;
            for (int w = 0; w < 4; w++)
            {
                int o = 112 + 40 * w, k = WheelMap[w];
                p.F32(o + 0, -s.Susp[k]); p.F32(o + 4, 0); p.F32(o + 8, 0); p.F32(o + 12, 0);
                p.F32(o + 16, touching && s.Mass > 0 ? s.Mass * 9.8 / 4 * f.Gain : 0); p.F32(o + 20, 0); p.F32(o + 24, 0);
                p.U8(o + 28, 20); p.U8(o + 29, (int)Math.Round(255 * s.Skid[k])); p.U8(o + 30, touching ? 1 : 0); p.U8(o + 31, 0);
                p.F32(o + 32, 0); p.F32(o + 36, 0);
            }
            p.F32(272, 0); p.F32(276, 0);
            return p.B;
        }

        public const uint DL_SHIFT = 1u << 0, DL_HANDBRAKE = 1u << 2, DL_ENGINE = 1u << 11, DL_NEUTRAL = 1u << 17;

        public static byte[] OutGauge(MotionFrame f, int id)
        {
            var p = new Packet(id != 0 ? 96 : 92);
            var s = f.S;
            p.U32(0, Packet.Ms(f.TSim)); p.Chars(4, "I76 ", 4);
            p.U16(8, 0);                                         // OG_KM / OG_BAR unset: miles and psi (an American game)
            p.U8(10, Gear(s.Gear)); p.U8(11, 0);
            p.F32(12, s.Speed); p.F32(16, s.Rpm);
            for (int o = 20; o < 40; o += 4) p.F32(o, 0);         // turbo, eng temp, fuel, oil pressure, oil temp: not modelled
            uint avail = DL_SHIFT | DL_HANDBRAKE | DL_ENGINE | DL_NEUTRAL, on = 0;
            if (s.Rpm > 6000) on |= DL_SHIFT;
            if (s.Handbrake) on |= DL_HANDBRAKE;
            if (s.EngineHealth < 0.5) on |= DL_ENGINE;
            if (s.Gear == 1) on |= DL_NEUTRAL;
            p.U32(40, avail); p.U32(44, on);
            p.F32(48, s.Throttle); p.F32(52, s.Brake); p.F32(56, 0);
            p.Chars(60, s.WeaponName, 8);
            if (id != 0) p.I32(92, id);
            return p.B;
        }
    }
}
