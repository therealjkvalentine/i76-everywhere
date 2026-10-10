using System.Collections.Generic;

namespace Haptics.Core
{
    /// <summary>One effect the engine started this frame (Telemetry.ps1 FxFired entry).</summary>
    public struct FxFired
    {
        public int Slot, Id;
        public double Param, Mag;
        public FxFired(int slot, int id, double param, double mag) { Slot = slot; Id = id; Param = param; Mag = mag; }
    }

    /// <summary>
    /// The Tel-Sample shape the reference force model consumes (tools/ffb/Telemetry.ps1 Tel-Sample, only the
    /// fields Mix-Update reads). Nullable fields reproduce PowerShell's "property absent" semantics, which the
    /// model tests explicitly ($null -ne $Sample.Shift etc.).
    /// </summary>
    public sealed class Sample
    {
        public double T;
        public double Speed, Steer, Throttle, YawRate;
        public double LongG, LatG;
        public double? LongAccel, LatAccel, HeaveAccel, TravelPitch;
        public double Understeer, Oversteer, Jolt;
        public double Vy;
        public double Rpm;                 // 0 = unknown (Mix-Update falls back to speed)
        public bool Firing;
        public bool? FxEvent;
        public List<FxFired> FxFired;      // null = absent
        public int? Shift;                 // +1 / -1 / 0; null = absent
        public double? SinceTick;          // seconds since the sim last advanced; null = absent

        // carried for renderers (motion), not read by the force model
        public double AngVelX, AngVelZ;
        public double Vx, Vz;
        public double WorldAccelX, WorldAccelY, WorldAccelZ;
        public double HeadingApprox;

        public Sample Clone()
        {
            var s = (Sample)MemberwiseClone();
            if (FxFired != null) s.FxFired = new List<FxFired>(FxFired);
            return s;
        }
    }
}
