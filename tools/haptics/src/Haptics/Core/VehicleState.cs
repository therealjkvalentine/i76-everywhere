using System;

namespace Haptics.Core
{
    public struct Vec3
    {
        public double X, Y, Z;
        public Vec3(double x, double y, double z) { X = x; Y = y; Z = z; }
        public double Length => Math.Sqrt(X * X + Y * Y + Z * Z);
        public static Vec3 operator -(Vec3 a, Vec3 b) => new Vec3(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
        public static Vec3 operator *(Vec3 a, double k) => new Vec3(a.X * k, a.Y * k, a.Z * k);
        public override string ToString() => "(" + Fmt.G(X, "0.###") + ", " + Fmt.G(Y, "0.###") + ", " + Fmt.G(Z, "0.###") + ")";
    }

    /// <summary>
    /// THE MOTION INTERFACE. Everything a motion renderer (docs/MOTION-OUTPUT.md, separate workstream) needs about the
    /// player vehicle on one core step, in declared units and frames, unfiltered (cueing/washout is the motion
    /// renderer's job, HAPTICS-ARCHITECTURE 2.2 "Motion: no mixing; raw SI ... never pre-filtered").
    ///
    /// Frames and axes (I'76 world is Y-up):
    ///   world  x, y = up, z            (i76tel pos / velocity / accel)
    ///   body   x = right, y = up, z = forward; rows of Rot are those axes in world coordinates (world = local x R + T),
    ///          so v_body[i] = sum_j Rot[3i+j] * v_world[j]
    /// Angles: radians. pitch = asin(rot[7]), roll = asin(rot[1]), heading = atan2(rot[6], rot[8]) (i76tel.h).
    /// Body rates: the engine's own ent+0xc8/0xcc/0xd0, rad/s; NOTE the contact model snaps pitch/roll rate to 0 at
    /// rest (they are transients only, FFB-DATA-AUDIT).
    /// Accelerations, m/s^2, gravity EXCLUDED: AccWorld is d(velocity)/dt across sim ticks (Telemetry.ps1 semantics,
    /// a parked car reads 0); AccEngineWorld is the engine's ent+0xd4 as published (its gravity convention is not
    /// verified live); AccBody = Rot * AccWorld. AccBodyFfb is the exe's own body-frame copy (FFB block), valid only
    /// while FfbPresent.
    /// HasOrientation is false when the source cannot supply it (legacy drive*.csv replays): then Rot is identity and
    /// body = world.
    /// </summary>
    public sealed class VehicleState
    {
        public double T, Dt;               // engine sim time / the tick interval that produced the derivatives
        public uint SimFrame;
        public bool Present;               // player_present
        public bool Ticked;                // the sim advanced since the previous core step
        public bool HasOrientation;
        public Vec3 PosWorld, VelWorld, VelBody, AccWorld, AccBody, AccEngineWorld, AccBodyFfb;
        public bool FfbPresent;
        public double[] Rot = { 1, 0, 0, 0, 1, 0, 0, 0, 1 };
        public double Pitch, Roll, Heading;
        public double PitchRate, YawRate, RollRate;
        public double Speed, Rpm, Throttle, Steer, Clearance;
        public int Gear = 1;
        public uint Flags, Surface;
        public Vec3 GroundNormal;
        public double[] SuspOffset = new double[6];
        public bool[] WheelOnGround = new bool[6];
        // motion workstream additions (docs/MOTION-OUTPUT.md 4.1): physics-step detection and the dash / wheel fields
        public double SimDt;               // i76tel sim_dt (the rendered frame's dt)
        public int StepCount = -1;         // i76tel step_count: physics substeps this frame (0 = repeated pose under I76_FIXED_STEP; -1 unknown)
        public bool[] WheelSkid = new bool[6];
        public double[] WheelGroundSpeed = new double[6];
        public bool Handbrake;
        public double EngineHealth = 1.0;  // engine_hp / engine_hp_max (1 when unknown)
        public double Mass;
        public string WeaponName = "";

        public bool Airborne => (Flags & TelFrame.FlagAirborne) != 0;

        public Vec3 ToBody(Vec3 w) => new Vec3(
            Rot[0] * w.X + Rot[1] * w.Y + Rot[2] * w.Z,
            Rot[3] * w.X + Rot[4] * w.Y + Rot[5] * w.Z,
            Rot[6] * w.X + Rot[7] * w.Y + Rot[8] * w.Z);

        public VehicleState Clone()
        {
            var v = (VehicleState)MemberwiseClone();
            v.Rot = (double[])Rot.Clone(); v.SuspOffset = (double[])SuspOffset.Clone(); v.WheelOnGround = (bool[])WheelOnGround.Clone();
            v.WheelSkid = (bool[])WheelSkid.Clone(); v.WheelGroundSpeed = (double[])WheelGroundSpeed.Clone();
            return v;
        }
    }
}
