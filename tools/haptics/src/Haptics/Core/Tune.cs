using System;
using System.Collections.Generic;
using System.Globalization;

namespace Haptics.Core
{
    /// <summary>
    /// The force model's tunables, keyed exactly as tools/ffb/FfbMixer.ps1 Mix-DefaultTune names them.
    /// The values are NOT hard-coded here: they come from effects/*.json + rigs/*.json through
    /// schema/legacy-tunemap.json (Effects.EffectSet.BuildTune). <see cref="Defaults"/> exists only as the
    /// test oracle for that migration and is itself checked against FfbMixer.ps1 by design/migrate_tune.py.
    /// </summary>
    public sealed class Tune
    {
        readonly Dictionary<string, double> _v = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        readonly Dictionary<string, double[]> _a = new Dictionary<string, double[]>(StringComparer.OrdinalIgnoreCase);

        public double this[string k]
        {
            get
            {
                if (_v.TryGetValue(k, out var d)) return d;
                throw new KeyNotFoundException("tune key '" + k + "' is not defined (check effects/ and schema/legacy-tunemap.json)");
            }
            set { _v[k] = value; }
        }
        public double[] Array(string k)
        {
            if (_a.TryGetValue(k, out var a)) return a;
            throw new KeyNotFoundException("tune array '" + k + "' is not defined");
        }
        public void SetArray(string k, double[] a) { _a[k] = a; }
        public bool Has(string k) => _v.ContainsKey(k) || _a.ContainsKey(k);
        public IEnumerable<string> ScalarKeys => _v.Keys;
        public IEnumerable<string> ArrayKeys => _a.Keys;
        public int Count => _v.Count + _a.Count;

        public Tune Clone()
        {
            var t = new Tune();
            foreach (var kv in _v) t._v[kv.Key] = kv.Value;
            foreach (var kv in _a) t._a[kv.Key] = (double[])kv.Value.Clone();
            return t;
        }

        public string Describe(string k)
        {
            if (_v.TryGetValue(k, out var d)) return d.ToString("R", CultureInfo.InvariantCulture);
            if (_a.TryGetValue(k, out var a)) return "[" + string.Join(", ", System.Array.ConvertAll(a, x => x.ToString("R", CultureInfo.InvariantCulture))) + "]";
            return "<absent>";
        }

        /// <summary>Mix-DefaultTune as of commit 560dcd2. Test oracle only - see the class comment.</summary>
        public static Tune Defaults()
        {
            var t = new Tune();
            void S(string k, double v) => t._v[k] = v;
            S("Master", 1.00);
            S("SatGain", 5200); S("SatRef", 9.0); S("SatFloor", 0.28);
            S("CornerGain", 3400); S("CornerRef", 2.80);
            S("UndersteerDrop", 0.75); S("ScrubGain", 900); S("ScrubHz", 14.0); S("OversteerGain", 3600);
            S("TextureGain", 1500); S("TexRef", 16.0); S("TextureHz", 11.0); S("RoughRef", 6.0); S("TextureFloor", 0.06); S("BumpGain", 1400);
            S("BrakeGain", 2200); S("BrakeRef", 0.60); S("JudderGain", 1300); S("JudderHz", 12.0);
            S("ImpactGain", 9000); S("ImpactRef", 70.0); S("ImpactMs", 260); S("KerbGain", 2500);
            S("ShiftGain", 2600); S("ShiftMs", 90); S("ShiftDownScale", 0.55);
            S("WeaponGain", 3400); S("WeaponMs", 140); S("WeaponHz", 13.0); S("WeaponMagRef", 10.0); S("WeaponMagMax", 2.6); S("WeaponBlankMs", 70);
            S("LfeEngineIdleHz", 26.0); S("LfeEngineMaxHz", 38.0); S("LfeEngineRefSpd", 40.0); S("LfeRpmIdle", 1050.0); S("LfeRpmMax", 6000.0);
            S("LfeEngineAmp", 0.45); S("LfeEngineJitter", 0.06);
            S("LfeRoadLoHz", 55.0); S("LfeRoadHiHz", 72.0); S("LfeRoadAmp", 0.34);
            S("LfeImpactAmp", 0.62); S("LfeWeaponAmp", 0.75); S("LfeImpactHz", 30.0);
            S("LfeScrubHz", 70.0); S("LfeScrubAmp", 0.34); S("LfeWeaponHz", 38.0);
            t._a["LfeRespHz"] = new double[] { 8.0, 10.0, 12.0, 13.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 31.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 70.0, 80.0, 90.0, 100.0 };
            t._a["LfeRespRel"] = new double[] { 0.00, 0.00, 0.11, 0.11, 0.22, 0.33, 0.44, 0.56, 0.67, 0.78, 0.89, 1.00, 0.89, 0.78, 0.67, 0.67, 0.67, 0.67, 0.67, 0.56, 0.44 };
            S("LfeCompMax", 1.6);
            S("LfeExplodeHz", 25.0); S("LfeExplodeAmp", 0.58); S("LfeExplodeDuck", 0.75); S("LfeExplodeMag", 40.0);
            S("LfeCarrierHz", 35.0); S("LfeHeaveAmp", 0.44); S("LfeHeaveRef", 10.0);
            S("MinForce", 900); S("MinForceGate", 150); S("Clamp", 9500);
            S("IdleFadeAfter", 20.0); S("IdleFadeOver", 2.0); S("RampMs", 700); S("SlewMax", 2600);
            return t;
        }
    }
}
