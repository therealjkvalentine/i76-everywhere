using System;
using System.Collections.Generic;
using System.Globalization;

namespace Haptics.Core
{
    /// <summary>
    /// A line-for-line port of tools/ffb/FfbMixer.ps1 (Mix-New / Mix-Trigger / Mix-Update / Mix-RenderPad /
    /// Mix-RenderWheel) as of commit 560dcd2, including the blast-decay / duck fix of that commit.
    ///
    /// FfbMixer.ps1 stays the REFERENCE: tests/golden/make-golden.ps1 runs it over the synthetic drives and
    /// tests/Haptics.Tests compares every output of this port against it. Expression order is kept identical to
    /// the PowerShell so the doubles agree bit for bit; PowerShell's [int] cast (round half to even) and
    /// [math]::Round are reproduced with <see cref="PsInt"/> and Math.Round.
    ///
    /// The design rationale for every channel lives in FfbMixer.ps1's comments and is not repeated here.
    /// </summary>
    public sealed class ReferenceMixer
    {
        public static readonly string[] GateChannels =
            { "center", "corner", "oversteer", "brake", "texture", "scrub", "judder", "impact", "weapon", "shift" };

        sealed class Transient { public string Shape; public double Amp; public int Ms; public double Hz; public double Start; public string Kind; }

        public Tune Tune;
        public double Phase, ScrubPhase, JudderPhase;
        readonly List<Transient> _transients = new List<Transient>();
        public double LastForce, LastT, StartT = -1.0;
        public bool Enabled = true;
        public double PeakForce, LastJolt, BlastEnv;
        public bool LastFiring;
        public double LastFireT = -10.0, StillSince = -1.0;

        public ReferenceMixer(Tune tune) { Tune = tune ?? throw new ArgumentNullException(nameof(tune)); }

        public int TransientCount => _transients.Count;

        public static int PsInt(double x)
        {
            if (double.IsNaN(x) || double.IsInfinity(x)) throw new OverflowException("PowerShell [int] of " + x);
            return (int)Math.Round(x, MidpointRounding.ToEven);
        }

        void Trigger(string shape, double amp, int ms, double hz = 30.0, string kind = "impact")
        {
            _transients.Add(new Transient { Shape = shape, Amp = amp, Ms = ms, Hz = hz, Start = LastT, Kind = kind });
        }

        /// <summary>Mix-Update. <paramref name="active"/> null = every channel on; otherwise a missing key is OFF (PowerShell [bool]$null).</summary>
        public MixOut Update(Sample s, IDictionary<string, bool> active = null)
        {
            var gate = new Dictionary<string, bool>();
            foreach (var k in GateChannels)
                gate[k] = active == null ? true : (active.TryGetValue(k, out var on) && on);

            var Tn = Tune;
            double t = s.T;
            double dt = LastT > 0 ? t - LastT : 0.016;
            if (dt <= 0 || dt > 0.5) dt = 0.016;
            LastT = t;
            if (StartT < 0) StartT = t;

            var ch = new Channels();
            var notes = new List<string>();

            double outOfShape = Math.Max(s.Understeer, s.Oversteer);
            double gripScale = 1.0 - (outOfShape * Tn["UndersteerDrop"]);
            ch["grip%"] = Math.Round(gripScale * 100);

            double spdN = Math.Min(1.0, s.Speed / Tn["SatRef"]);
            double satAuthority = Tn["SatFloor"] + (1.0 - Tn["SatFloor"]) * spdN;
            double sat = -s.Steer * Tn["SatGain"] * satAuthority * gripScale;
            ch["center"] = PsInt(sat);

            double latN = Math.Min(1.0, Math.Abs(s.LatG) / Tn["CornerRef"]);
            double corner = 0.0;
            if (Math.Abs(s.YawRate) > 0.001)
                corner = -Math.Sign(s.YawRate) * latN * Tn["CornerGain"] * gripScale;
            ch["corner"] = PsInt(corner);

            double over = 0.0;
            if (s.Oversteer > 0.01)
            {
                over = Math.Sign(s.YawRate) * s.Oversteer * Tn["OversteerGain"];
                if (s.Oversteer > 0.35) notes.Add("OVERSTEER");
            }
            ch["oversteer"] = PsInt(over);

            double brake = 0.0;
            if (s.LongG < -0.05)
            {
                double brakeN = Math.Min(1.0, (-s.LongG) / Tn["BrakeRef"]);
                brake = -Math.Sign(s.Steer) * brakeN * Tn["BrakeGain"];
                if (brakeN > 0.7) notes.Add("HARD BRAKE");
            }
            ch["brake"] = PsInt(brake);

            if (!gate["center"]) sat = 0.0;
            if (!gate["corner"]) corner = 0.0;
            if (!gate["oversteer"]) over = 0.0;
            if (!gate["brake"]) brake = 0.0;
            double steady = (sat + corner + over + brake);

            double jl = s.Jolt;
            double laC = Math.Abs(s.LongAccel ?? 0.0);
            double ltC = Math.Abs(s.LatAccel ?? 0.0);
            double resid2 = (jl * jl) - (laC * laC) - (ltC * ltC);
            if (resid2 < 0.0) resid2 = 0.0;
            double rough = Math.Min(1.0, Math.Sqrt(resid2) / Tn["RoughRef"]);
            double heave = Math.Min(1.0, Math.Abs(s.Vy) / 0.8);
            double texN = Math.Min(1.0, s.Speed / Tn["TexRef"]);
            double texAmp = (Tn["TextureGain"] * texN * (Tn["TextureFloor"] + (1.0 - Tn["TextureFloor"]) * rough)) + (Tn["BumpGain"] * heave * texN);
            Phase += 2 * Math.PI * Tn["TextureHz"] * dt;
            if (Phase > (2 * Math.PI)) Phase -= 2 * Math.PI;
            double texture = texAmp * Math.Sin(Phase);
            ch["texture"] = PsInt(texture);

            double scrub = 0.0, scrubAmp = 0.0;
            if (outOfShape > 0.15)
            {
                scrubAmp = Tn["ScrubGain"] * outOfShape;
                ScrubPhase += 2 * Math.PI * Tn["ScrubHz"] * dt;
                if (ScrubPhase > (2 * Math.PI)) ScrubPhase -= 2 * Math.PI;
                scrub = Tn["ScrubGain"] * outOfShape * Math.Sin(ScrubPhase);
                if (s.Oversteer > 0.4) notes.Add("SPIN");
                else if (s.Understeer > 0.4) notes.Add("PLOUGHING");
            }
            ch["scrub"] = PsInt(scrub);

            double judder = 0.0, judderAmp = 0.0;
            if (s.LongG < -0.45 && s.Speed > 4)
            {
                JudderPhase += 2 * Math.PI * Tn["JudderHz"] * dt;
                if (JudderPhase > (2 * Math.PI)) JudderPhase -= 2 * Math.PI;
                double jN = Math.Min(1.0, ((-s.LongG) - 0.45) / 0.5);
                judderAmp = Tn["JudderGain"] * jN;
                judder = judderAmp * Math.Sin(JudderPhase);
            }
            ch["judder"] = PsInt(judder);

            double impThresh = Tn["ImpactRef"] * 0.08;
            if (s.Jolt > impThresh && LastJolt <= impThresh)
            {
                double mag = Math.Min(1.0, s.Jolt / Tn["ImpactRef"]);
                int dir = Math.Abs(s.YawRate) > 0.05 ? Math.Sign(s.YawRate) : 1;
                Trigger("jolt", dir * mag * Tn["ImpactGain"], PsInt(Tn["ImpactMs"]));
                notes.Add(string.Format(CultureInfo.InvariantCulture, "IMPACT {0:0}%", mag * 100));
            }
            LastJolt = s.Jolt;

            bool firing = s.FxEvent.HasValue ? s.FxEvent.Value : s.Firing;
            double wScale = 1.0;
            double blast = 0.0;
            if (s.FxFired != null && s.FxFired.Count > 0)
            {
                foreach (var fx in s.FxFired)
                {
                    if (fx.Mag >= Tn["LfeExplodeMag"])
                    {
                        double b = Math.Min(1.0, fx.Mag / (Tn["LfeExplodeMag"] * 1.5));
                        if (b > blast) blast = b;
                    }
                }
                double mx = 0;
                foreach (var fx in s.FxFired) if (fx.Mag > mx) mx = fx.Mag;
                if (mx > 0)
                {
                    wScale = Math.Sqrt(mx / Tn["WeaponMagRef"]);
                    if (wScale > Tn["WeaponMagMax"]) wScale = Tn["WeaponMagMax"];
                    if (wScale < 0.35) wScale = 0.35;
                }
            }
            if (blast > BlastEnv) BlastEnv = blast; else BlastEnv *= 0.90;
            if (BlastEnv < 0.001) BlastEnv = 0.0;
            double duck = 1.0 - (Tn["LfeExplodeDuck"] * BlastEnv);

            if (firing && !LastFiring)
            {
                if (((t - LastFireT) * 1000.0) >= Tn["WeaponBlankMs"])
                {
                    Trigger("buzz", Tn["WeaponGain"] * wScale, PsInt(Tn["WeaponMs"]), Tn["WeaponHz"], "weapon");
                    LastFireT = t;
                    notes.Add("FIRE");
                }
            }

            if (s.Shift.HasValue && s.Shift.Value != 0)
            {
                double shiftAmp = s.Shift.Value > 0 ? Tn["ShiftGain"] : Tn["ShiftGain"] * Tn["ShiftDownScale"];
                Trigger("jolt", shiftAmp, PsInt(Tn["ShiftMs"]), 30.0, "shift");
                notes.Add(s.Shift.Value > 0 ? "UPSHIFT" : "DOWNSHIFT");
            }
            LastFiring = firing;

            double transImpact = 0.0, transShift = 0.0, transWeapon = 0.0;
            var dead = new List<Transient>();
            foreach (var tr in _transients)
            {
                double age = (t - tr.Start) * 1000.0;
                if (age >= tr.Ms) { dead.Add(tr); continue; }
                double u = age / tr.Ms;
                double v;
                if (tr.Shape == "buzz")
                    v = tr.Amp * Math.Exp(-3.0 * u) * Math.Sin(2 * Math.PI * tr.Hz * (age / 1000.0));
                else
                {
                    double env = u < 0.12 ? u / 0.12 : Math.Exp(-3.5 * (u - 0.12));
                    v = tr.Amp * env;
                }
                if (tr.Kind == "weapon") transWeapon += v;
                else if (tr.Kind == "shift") transShift += v;
                else transImpact += v;
            }
            foreach (var d in dead) _transients.Remove(d);
            ch["impact"] = PsInt(transImpact);
            ch["weapon"] = PsInt(transWeapon);
            ch["shift"] = PsInt(transShift);

            if (!gate["texture"]) texture = 0.0;
            if (!gate["scrub"]) scrub = 0.0;
            if (!gate["judder"]) judder = 0.0;
            if (!gate["impact"]) transImpact = 0.0;
            if (!gate["shift"]) transShift = 0.0;
            if (!gate["weapon"]) transWeapon = 0.0;
            double trans = transImpact + transWeapon + transShift;
            double osc = texture + scrub + judder;

            double maxStep = Tn["SlewMax"] * dt;
            double dd = steady - LastForce;
            if (dd > maxStep) steady = LastForce + maxStep;
            else if (dd < -maxStep) steady = LastForce - maxStep;
            LastForce = steady;

            double force = (steady + osc + trans) * Tn["Master"];

            double ramp = Math.Min(1.0, ((t - StartT) * 1000.0) / Math.Max(1, Tn["RampMs"]));
            if (s.SinceTick.HasValue && s.SinceTick.Value > 0.5) ramp = 0.0;

            if (s.Speed > 0.5) StillSince = -1.0;
            else if (StillSince < 0) StillSince = t;
            if (StillSince >= 0)
            {
                double still = t - StillSince;
                if (still > Tn["IdleFadeAfter"])
                {
                    double fade = 1.0 - ((still - Tn["IdleFadeAfter"]) / Math.Max(0.1, Tn["IdleFadeOver"]));
                    if (fade < 0) fade = 0;
                    if (fade < ramp) ramp = fade;
                }
            }
            force *= ramp;
            if (!Enabled) force = 0;

            if (force > Tn["Clamp"]) force = Tn["Clamp"];
            if (force < -Tn["Clamp"]) force = -Tn["Clamp"];
            if (Math.Abs(force) > PeakForce) PeakForce = Math.Abs(force);

            const double N = 10000.0;
            double mScale = Tn["Master"] * ramp;
            if (!Enabled) mScale = 0.0;
            var bus = new Bus();
            bus.Steady = Math.Round((steady * mScale) / N, 4);
            bus.OscValue = Math.Round((osc * mScale) / N, 4);
            bus.Tactile[0] = new TactileOsc("texture", Tn["TextureHz"], Math.Round(Math.Abs(texAmp * mScale) / N, 4));
            bus.Tactile[1] = new TactileOsc("scrub", Tn["ScrubHz"], Math.Round((scrubAmp * mScale) / N, 4));
            bus.Tactile[2] = new TactileOsc("judder", Tn["JudderHz"], Math.Round((judderAmp * mScale) / N, 4));
            bus.Transient = Math.Round(((transImpact + transWeapon) * mScale) / N, 4);
            bus.TransientImpact = Math.Round((transImpact * mScale) / N, 4);
            bus.TransientWeapon = Math.Round((transWeapon * mScale) / N, 4);

            var m = bus.Motion;
            m.SurgeA = Math.Round(s.LongAccel ?? 0.0, 3);
            m.SwayA = Math.Round(s.LatAccel ?? 0.0, 3);
            m.HeaveA = Math.Round(s.HeaveAccel ?? 0.0, 3);
            m.YawRate = Math.Round(s.YawRate, 4);
            m.Pitch = Math.Round(s.TravelPitch ?? 0.0, 4);
            m.Speed = Math.Round(s.Speed, 3);

            var L = bus.Lfe;
            double engN = s.Rpm > 0
                ? Math.Max(0.0, Math.Min(1.0, (s.Rpm - Tn["LfeRpmIdle"]) / (Tn["LfeRpmMax"] - Tn["LfeRpmIdle"])))
                : Math.Min(1.0, s.Speed / Tn["LfeEngineRefSpd"]);
            L.EngineFreq = Math.Round(Tn["LfeEngineIdleHz"] + (Tn["LfeEngineMaxHz"] - Tn["LfeEngineIdleHz"]) * engN, 1);
            L.EngineAmp = Math.Round(duck * Tn["LfeEngineAmp"] * (0.35 + 0.65 * Math.Abs(s.Throttle)) *
                                     ((s.Speed > 0.5 || Math.Abs(s.Throttle) > 0.05) ? 1.0 : 0.0), 3);
            L.RoadAmp = Math.Round(Math.Min(1.0, duck * Tn["LfeRoadAmp"] * rough * Math.Min(1.0, s.Speed / Tn["TexRef"])), 3);
            L.RoadFreq = Math.Round(Tn["LfeRoadLoHz"] + (Tn["LfeRoadHiHz"] - Tn["LfeRoadLoHz"]) * rough, 1);
            L.ImpulseAmp = Math.Round(Math.Min(1.0, Math.Abs(transImpact + transShift) / N * (Tn["LfeImpactAmp"] * N / Math.Max(1, Tn["ImpactGain"]))), 3);
            L.HeaveAmp = Math.Round(Math.Min(1.0, Tn["LfeHeaveAmp"] * Math.Abs(s.HeaveAccel ?? 0.0) / Tn["LfeHeaveRef"]), 3);
            L.CarrierFreq = Tn["LfeCarrierHz"];
            L.ImpulseFreq = Tn["LfeImpactHz"];
            L.WeaponAmp = Math.Round(Math.Min(1.0, (1.0 - BlastEnv) * Tn["LfeWeaponAmp"] * Math.Abs(transWeapon) / Math.Max(1, Tn["WeaponGain"])), 3);
            L.ScrubAmp = Math.Round(Math.Min(1.0, duck * Tn["LfeScrubAmp"] * scrubAmp / Math.Max(1, Tn["ScrubGain"])), 3);
            L.ExplodeAmp = Math.Round(Math.Min(1.0, Tn["LfeExplodeAmp"] * BlastEnv), 3);
            L.WeaponFreq = Tn["LfeWeaponHz"];

            return new MixOut
            {
                Force = PsInt(force),
                Steady = PsInt(steady),
                Osc = PsInt(osc),
                Ramp = ramp,
                Channels = ch,
                Notes = notes,
                Bus = bus,
                Duck = duck,
                Rough = rough,
            };
        }

        /// <summary>Mix-RenderPad: the legacy SUM down-mix (left = heavy, right = buzz), 0..1.</summary>
        public static (double Left, double Right) RenderPadLegacy(Bus b)
        {
            double left = 0.0, right = 0.0;
            left += b.Lfe.EngineAmp * 0.5;
            left += b.Lfe.RoadAmp * 0.6;
            left += Math.Abs(b.TransientImpact);
            left += Math.Abs(b.Steady) * 0.25;
            foreach (var tt in b.Tactile)
            {
                if (tt.Name == "texture") right += tt.Amp * 0.5; else right += tt.Amp;
            }
            right += Math.Abs(b.TransientWeapon);
            if (left > 1.0) left = 1.0;
            if (right > 1.0) right = 1.0;
            return (Math.Round(left, 4), Math.Round(right, 4));
        }

        /// <summary>Mix-RenderWheel: belt-drive stiction lift (device stage), clamp, [int].</summary>
        public static int RenderWheelLegacy(int modelForce, double minForce, double minForceGate, double clamp)
        {
            double f = modelForce;
            if (minForce > 0 && Math.Abs(f) >= minForceGate)
            {
                double mag = Math.Abs(f);
                double lifted = minForce + mag * (1.0 - (minForce / clamp));
                if (lifted > mag) f = lifted * Math.Sign(f);
            }
            if (f > clamp) f = clamp;
            if (f < -clamp) f = -clamp;
            return PsInt(f);
        }
    }

    /// <summary>Ordered channel breakdown (Mix-Update .Channels).</summary>
    public sealed class Channels
    {
        readonly List<string> _order = new List<string>();
        readonly Dictionary<string, double> _v = new Dictionary<string, double>();
        public double this[string k]
        {
            get => _v.TryGetValue(k, out var v) ? v : 0.0;
            set { if (!_v.ContainsKey(k)) _order.Add(k); _v[k] = value; }
        }
        public IReadOnlyList<string> Keys => _order;
        public bool Contains(string k) => _v.ContainsKey(k);
    }

    public sealed class MixOut
    {
        public int Force, Steady, Osc;
        public double Ramp;
        public Channels Channels;
        public List<string> Notes;
        public Bus Bus;
        public double Duck, Rough;
    }
}
