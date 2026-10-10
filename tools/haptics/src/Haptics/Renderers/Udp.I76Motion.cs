using Haptics.Core.Motion;

namespace Haptics.Renderers
{
    /// <summary>
    /// Udp.I76Motion: the host's own 144-byte motion datagram, i76motion v1 (docs/MOTION-OUTPUT.md 3.3). The layout is
    /// schema/i76motion.json; motion/i76motion.py decodes it from that file and the C# tests assert every offset below
    /// against it. Physics channels and cue channels are separate; the status word carries live / neutral / paused.
    /// </summary>
    public static class I76MotionPacket
    {
        public const int Size = 144, Version = 1, DefaultPort = 7677;

        public static byte[] Build(MotionFrame f)
        {
            var p = new Packet(Size);
            var s = f.S;
            p.Chars(0, "I76M", 4); p.U16(4, Version); p.U16(6, Size);
            p.U32(8, f.Seq); p.U32(12, f.Status); p.F32(16, f.TSim);
            p.F32(20, s.Surge); p.F32(24, s.Sway); p.F32(28, s.Heave);
            p.F32(32, s.RollRate); p.F32(36, s.PitchRate); p.F32(40, s.YawRate);
            p.F32(44, s.Roll); p.F32(48, s.Pitch); p.F32(52, s.Heading);
            p.F32(56, s.Speed); p.F32(60, s.Rpm); p.F32(64, f.GearFloat);
            p.F32(68, s.Throttle); p.F32(72, s.Brake); p.F32(76, s.Steer);
            for (int w = 0; w < 4; w++) { p.F32(80 + 4 * w, s.Susp[w]); p.F32(96 + 4 * w, s.Skid[w]); }
            p.F32(112, s.Texture);
            p.F32(116, f.CueSurge); p.F32(120, f.CueSway); p.F32(124, f.CueHeave);
            p.F32(128, s.VelRight); p.F32(132, s.VelUp); p.F32(136, s.VelFwd);
            p.U32(140, 0);
            return p.B;
        }
    }
}
