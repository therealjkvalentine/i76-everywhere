using System;

namespace Haptics.Core.Motion
{
    /// <summary>
    /// One physics state in motion terms (Motion.Derive output), SI units, the car's body frame.
    ///
    /// SIGN CONVENTIONS (the i76motion contract, schema/i76motion.json; every wire format is mapped from these):
    ///   surge + forward, sway + right, heave + up                         (m/s^2, gravity EXCLUDED: a parked car reads 0)
    ///   rotations follow the aerospace body convention (right-hand rule about forward / right / down):
    ///   roll  + = right side down          roll  = -asin(rot[1])        (I'76's rot[1] is the right axis' up component)
    ///   pitch + = nose up                  pitch =  asin(rot[7])
    ///   yaw   + = nose turning right       yaw_rate = engine ent+0xcc (assumed + = right turn, the synthetic session's
    ///                                      convention; owner test T1 checks it against the steering)
    ///   heading = atan2(rot[6], rot[8]): 0 facing world +z, increasing clockwise seen from above (I'76's world is
    ///   left-handed, x right of z), wrapped to -pi..pi.
    /// vel_body: (right, up, forward), m/s.  Wheel arrays: FL FR RL RR = i76tel component slots 0 1 4 5.
    /// </summary>
    public sealed class PhysicsSample
    {
        public double Clock;                       // the motion clock when this state was first seen (core time in replay, host time live)
        public double SimT, Dt;                    // engine sim time; sim time since the previous physics state
        public double Surge, Sway, Heave;          // physics acceleration (steady channel), body frame
        public double RollRate, PitchRate, YawRate;
        public double Roll, Pitch, Heading;
        public double VelRight, VelUp, VelFwd;
        public double Speed, Rpm, Throttle, Brake, Steer;
        public int Gear = 1;                       // i76tel: 0 R, 1 N, 2..4 = 1st..3rd
        public double[] Susp = new double[4];      // susp_offset, m
        public double[] Skid = new double[4];      // 0 / 1
        public double Texture;                     // 0..1
        public double ADiffSurge, ADiffSway, ADiffHeave;   // dv/dt across physics steps, body frame (impulses included)
        public double[] PosWorld = new double[3], VelWorld = new double[3];
        public double[] Rot = { 1, 0, 0, 0, 1, 0, 0, 0, 1 };
        public uint Flags, Surface;
        public bool Present, Airborne, Destroyed, Handbrake, SkidAny;
        public bool LandingEdge, TakeoffEdge;
        public double EngineHealth = 1, Mass;
        public string WeaponName = "";

        public PhysicsSample Clone()
        {
            var s = (PhysicsSample)MemberwiseClone();
            s.Susp = (double[])Susp.Clone(); s.Skid = (double[])Skid.Clone(); s.PosWorld = (double[])PosWorld.Clone();
            s.VelWorld = (double[])VelWorld.Clone(); s.Rot = (double[])Rot.Clone();
            return s;
        }

        /// <summary>world (x, y up, z) -> body (right, up, forward)</summary>
        public (double r, double u, double f) ToBody(double x, double y, double z) =>
            (Rot[0] * x + Rot[1] * y + Rot[2] * z, Rot[3] * x + Rot[4] * y + Rot[5] * z, Rot[6] * x + Rot[7] * y + Rot[8] * z);
        /// <summary>body (right, up, forward) -> world (x, y up, z): v_world = v_body x R</summary>
        public (double x, double y, double z) ToWorld(double r, double u, double f) =>
            (r * Rot[0] + u * Rot[3] + f * Rot[6], r * Rot[1] + u * Rot[4] + f * Rot[7], r * Rot[2] + u * Rot[5] + f * Rot[8]);
    }

    /// <summary>i76motion status word bits (schema/i76motion.json "status_bits").</summary>
    public static class MotionStatus
    {
        public const uint Live = 1u << 0, Airborne = 1u << 1, Skid = 1u << 2, Destroyed = 1u << 3, Paused = 1u << 4,
                          Neutral = 1u << 5, Interpolated = 1u << 6, Cues = 1u << 7, ShuttingDown = 1u << 31;
        public const int SurfaceShift = 8, GearShift = 16;
    }

    /// <summary>One output tick: what every wire encoder reads. Physics channels are already resampled and scaled by the neutral gain.</summary>
    public sealed class MotionFrame
    {
        public uint Seq, Status;
        public double Clock, TSim;
        public PhysicsSample S;                    // resampled channels (a private copy)
        public double CueSurge, CueSway, CueHeave;
        public double Gain = 1;                    // the fail-to-neutral / startup ramp factor already applied
        public bool RaceOn;                        // live && !neutral-target: Forza IsRaceOn
        public double Distance;                    // integrated speed x dt (Forza DistanceTraveled)

        public double TotalSurge => S.Surge + CueSurge;
        public double TotalSway => S.Sway + CueSway;
        public double TotalHeave => S.Heave + CueHeave;

        /// <summary>Gear as a float for scripts: -1 R, 0 N, 1..3.</summary>
        public double GearFloat => S.Gear - 1;
    }
}
