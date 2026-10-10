using System.Collections.Generic;

namespace Haptics.Core
{
    /// <summary>
    /// The device-independent force bus. Field names and units are FfbMixer.ps1's (Mix-Update .Bus) so the two
    /// can be compared value for value: forces -1..1, amplitudes 0..1, frequencies Hz, motion SI.
    /// Voices is the one addition: effect-file ("chain") effects that the 1997-era reference model does not
    /// know about land there, so a renderer can tell the reference content from the added content.
    /// </summary>
    public sealed class Bus
    {
        public double Steady, OscValue;
        public TactileOsc[] Tactile = new TactileOsc[3];
        public double Transient, TransientImpact, TransientWeapon;
        /// <summary>Added (FfbMixer.ps1 folds shift into Lfe.ImpulseAmp only): the shift transient, for the pad tick.</summary>
        public double TransientShift;
        public MotionBlock Motion = new MotionBlock();
        public LfeBlock Lfe = new LfeBlock();
        public List<Voice> Voices = new List<Voice>();
        /// <summary>Signed wheel force contributed by chain voices (normalized, -1..1), already summed.</summary>
        public double VoiceWheel;
    }

    public struct TactileOsc
    {
        public string Name; public double Freq, Amp;
        public TactileOsc(string n, double f, double a) { Name = n; Freq = f; Amp = a; }
    }

    public sealed class MotionBlock
    {
        public double SurgeA, SwayA, HeaveA, YawRate, Pitch, Speed;
        // not in FfbMixer's bus (it had no orientation): filled by Derive from the i76tel frame when present
        public double PitchAngle, RollAngle, Heading, PitchRate, RollRate;
        public double PosX, PosY, PosZ, VelX, VelY, VelZ, AccX, AccY, AccZ;
        public double Rpm; public int Gear = 2; public double Throttle, Steer;
        public bool HasOrientation;
    }

    public sealed class LfeBlock
    {
        public double EngineFreq, EngineAmp, RoadAmp, RoadFreq, ImpulseAmp, HeaveAmp;
        public double CarrierFreq, ImpulseFreq, WeaponAmp, ScrubAmp, ExplodeAmp, WeaponFreq;
    }

    /// <summary>One sounding chain effect (an effects/*.json with model "chain").</summary>
    public sealed class Voice
    {
        public string Id, Group, Kind;
        public int Priority;
        public double Level;        // 0..1 after response + envelope + duck
        public double Wheel;        // signed normalized wheel contribution
        public double LfeAmp, LfeHz;
        public double PadL, PadR;
        public bool Transient;
        public double AgeMs;
        public override string ToString() => Id + " lvl=" + Level.ToString("0.###");
    }
}
