using System;
using Haptics.Core.Motion;

namespace Haptics.Renderers
{
    /// <summary>
    /// Udp.Forza: Forza "Data Out" Sled (232 B) and Dash (311 B, FM7) from a MotionFrame (docs/MOTION-OUTPUT.md 3.2; layout
    /// in schema/motion-wire.json). Car-local frame X right, Y up, Z forward = I'76's body rows, so Acceleration (X, Y, Z) =
    /// (sway, heave, surge) incl. cues, Velocity = body velocity, AngularVelocity (X, Y, Z) = (pitch, yaw, roll) rates and
    /// Yaw / Pitch / Roll = heading / pitch / roll, all with the i76motion signs: whether Forza's own signs match is
    /// unverified (official page unreachable; owner test T3 in SimHub). IsRaceOn = 0 while neutral / paused, so consumers park.
    /// Wheel order FL FR RL RR. No tyre model: slip fields are 0 / 1.5 from the skid flags.
    /// </summary>
    public static class ForzaPacket
    {
        public static byte[] Build(MotionFrame f, bool dash, MotionParams prm)
        {
            var p = new Packet(dash ? 311 : 232);
            var s = f.S;
            double r = prm?.WheelRadius ?? 0.35, travel = prm?.SuspTravel ?? 0.0875;
            p.I32(0, f.RaceOn ? 1 : 0); p.U32(4, Packet.Ms(f.TSim));
            p.F32(8, 7000); p.F32(12, 850); p.F32(16, s.Rpm);
            p.F32(20, f.TotalSway); p.F32(24, f.TotalHeave); p.F32(28, f.TotalSurge);
            p.F32(32, s.VelRight); p.F32(36, s.VelUp); p.F32(40, s.VelFwd);
            p.F32(44, s.PitchRate); p.F32(48, s.YawRate); p.F32(52, s.RollRate);
            p.F32(56, s.Heading); p.F32(60, s.Pitch); p.F32(64, s.Roll);
            for (int w = 0; w < 4; w++)
            {
                double slip = s.Skid[w] > 0.5 ? 1.5 : 0;
                p.F32(68 + 4 * w, Math.Max(0, Math.Min(1, 0.5 + s.Susp[w] / (2 * travel))));
                p.F32(84 + 4 * w, slip);
                p.F32(100 + 4 * w, s.Speed / r * (s.VelFwd < 0 ? -1 : 1));
                p.I32(116 + 4 * w, 0);
                p.F32(132 + 4 * w, 0);
                p.F32(148 + 4 * w, s.Texture);
                p.F32(164 + 4 * w, slip);
                p.F32(180 + 4 * w, slip);
                p.F32(196 + 4 * w, s.Susp[w]);
            }
            p.I32(212, 1976); p.I32(216, 3); p.I32(220, 500); p.I32(224, 1); p.I32(228, 8);
            if (!dash) return p.B;
            p.F32(232, s.PosWorld[0]); p.F32(236, s.PosWorld[1]); p.F32(240, s.PosWorld[2]);
            p.F32(244, s.Speed); p.F32(248, 0); p.F32(252, 0);
            for (int w = 0; w < 4; w++) p.F32(256 + 4 * w, 0);
            p.F32(272, (s.Flags & Core.TelFrame.FlagNitrous) != 0 ? 1 : 0); p.F32(276, 1); p.F32(280, f.Distance);
            p.F32(284, 0); p.F32(288, 0); p.F32(292, 0); p.F32(296, f.TSim);
            p.U16(300, 0); p.U8(302, 1);
            p.U8(303, (int)Math.Round(s.Throttle * 255)); p.U8(304, (int)Math.Round(s.Brake * 255)); p.U8(305, 0); p.U8(306, s.Handbrake ? 255 : 0);
            p.U8(307, Math.Max(0, s.Gear));
            p.S8(308, (int)Math.Round(s.Steer * 127)); p.S8(309, 0); p.S8(310, 0);
            return p.B;
        }
    }
}
