using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using Haptics.Core;

namespace Haptics.Tests
{
    /// <summary>
    /// A2 exit criterion: the C# Core reproduces FfbMixer.ps1's outputs (force, channels, notes, every bus field,
    /// the pad down-mix and the wheel renderer) on every golden drive written by tests/golden/make-golden.ps1.
    /// </summary>
    static class GoldenTests
    {
        public const double Tol = 1e-6;

        public static Sample RowToSample(CsvTable g, int r)
        {
            var s = new Sample
            {
                T = g.D(r, "T"), Speed = g.D(r, "Speed"), Steer = g.D(r, "Steer"), Throttle = g.D(r, "Throttle"),
                YawRate = g.D(r, "YawRate"), LongG = g.D(r, "LongG"), LatG = g.D(r, "LatG"),
                LongAccel = g.N(r, "LongAccel"), LatAccel = g.N(r, "LatAccel"), HeaveAccel = g.N(r, "HeaveAccel"),
                TravelPitch = g.N(r, "TravelPitch"),
                Understeer = g.D(r, "Understeer"), Oversteer = g.D(r, "Oversteer"), Jolt = g.D(r, "Jolt"), Vy = g.D(r, "Vy"),
                Rpm = g.D(r, "Rpm"), Firing = g.S(r, "Firing") == "1",
            };
            var fe = g.S(r, "FxEvent"); if (fe.Length > 0) s.FxEvent = fe == "1";
            var mags = g.S(r, "FxMags");
            if (mags.Length > 0)
            {
                s.FxFired = new List<FxFired>();
                if (mags != "-")
                    foreach (var m in mags.Split(';')) s.FxFired.Add(new FxFired(0, 8, 0.8, double.Parse(m, CultureInfo.InvariantCulture)));
            }
            var sh = g.S(r, "Shift"); if (sh.Length > 0) s.Shift = int.Parse(sh, CultureInfo.InvariantCulture);
            s.SinceTick = g.N(r, "SinceTick");
            return s;
        }

        public static Dictionary<string, bool> RowActive(CsvTable g, int r)
        {
            var a = g.S(r, "Active");
            if (a.Length == 0) return null;
            var d = new Dictionary<string, bool>();
            if (a != "-") foreach (var k in a.Split(';')) d[k] = true;
            return d;
        }

        /// <summary>Replays one golden drive through a fresh ReferenceMixer; returns (fields compared, mismatches, first message).</summary>
        public static (int compared, int bad, string first) CompareDrive(string path, Tune tune)
        {
            var g = CsvTable.Load(path);
            var mix = new ReferenceMixer(tune);
            int compared = 0, bad = 0; string first = null;
            void Cmp(int r, string col, double got)
            {
                compared++;
                double want = g.D(r, col);
                if (!(Math.Abs(got - want) <= Tol))
                {
                    bad++;
                    if (first == null) first = string.Format(CultureInfo.InvariantCulture, "frame {0} {1}: C# {2} vs ps1 {3}", r, col, Fmt.R(got), Fmt.R(want));
                }
            }
            for (int r = 0; r < g.Rows.Count; r++)
            {
                var s = RowToSample(g, r);
                mix.Enabled = g.S(r, "Enabled") != "0";
                var o = mix.Update(s, RowActive(g, r));
                Cmp(r, "Force", o.Force); Cmp(r, "Steady", o.Steady); Cmp(r, "Osc", o.Osc); Cmp(r, "Ramp", o.Ramp);
                foreach (var c in new[] { "grip%", "center", "corner", "oversteer", "brake", "texture", "scrub", "judder", "impact", "weapon", "shift" })
                    Cmp(r, "ch_" + c, o.Channels[c]);
                compared++;
                if (string.Join("|", o.Notes) != g.S(r, "Notes")) { bad++; if (first == null) first = "frame " + r + " notes: '" + string.Join("|", o.Notes) + "' vs '" + g.S(r, "Notes") + "'"; }
                var b = o.Bus;
                Cmp(r, "b_Steady", b.Steady); Cmp(r, "b_OscValue", b.OscValue);
                Cmp(r, "b_TexAmp", b.Tactile[0].Amp); Cmp(r, "b_ScrubAmp", b.Tactile[1].Amp); Cmp(r, "b_JudderAmp", b.Tactile[2].Amp);
                Cmp(r, "b_Transient", b.Transient); Cmp(r, "b_TransientImpact", b.TransientImpact); Cmp(r, "b_TransientWeapon", b.TransientWeapon);
                Cmp(r, "m_SurgeA", b.Motion.SurgeA); Cmp(r, "m_SwayA", b.Motion.SwayA); Cmp(r, "m_HeaveA", b.Motion.HeaveA);
                Cmp(r, "m_YawRate", b.Motion.YawRate); Cmp(r, "m_Pitch", b.Motion.Pitch); Cmp(r, "m_Speed", b.Motion.Speed);
                var L = b.Lfe;
                Cmp(r, "l_EngineFreq", L.EngineFreq); Cmp(r, "l_EngineAmp", L.EngineAmp); Cmp(r, "l_RoadAmp", L.RoadAmp);
                Cmp(r, "l_RoadFreq", L.RoadFreq); Cmp(r, "l_ImpulseAmp", L.ImpulseAmp); Cmp(r, "l_HeaveAmp", L.HeaveAmp);
                Cmp(r, "l_WeaponAmp", L.WeaponAmp); Cmp(r, "l_ScrubAmp", L.ScrubAmp); Cmp(r, "l_ExplodeAmp", L.ExplodeAmp);
                var pad = ReferenceMixer.RenderPadLegacy(b);
                Cmp(r, "pad_L", pad.Left); Cmp(r, "pad_R", pad.Right);
                Cmp(r, "wheel", ReferenceMixer.RenderWheelLegacy(o.Force, tune["MinForce"], tune["MinForceGate"], tune["Clamp"]));
                Cmp(r, "peak", mix.PeakForce); Cmp(r, "blastEnv", mix.BlastEnv);
            }
            return (compared, bad, first);
        }

        public static void Run(Func<Tune> tuneSource, string label)
        {
            T.Section("A2 golden: C# Core vs FfbMixer.ps1 (" + label + ")");
            var dir = Path.Combine(T.HapticsRoot, "tests", "golden", "out");
            var files = Directory.Exists(dir) ? Directory.GetFiles(dir, "*.csv").OrderBy(f => f).ToArray() : new string[0];
            if (files.Length == 0)
            {
                T.Check("golden drives present (run tests/golden/make-golden.ps1, or haptics.ps1 test)", false, dir);
                return;
            }
            int totalCmp = 0, totalBad = 0, drives = 0, synth = 0;
            foreach (var f in files)
            {
                var name = Path.GetFileNameWithoutExtension(f);
                var (c, b, first) = CompareDrive(f, tuneSource());
                totalCmp += c; totalBad += b; drives++;
                if (!name.StartsWith("real_")) synth++;
                T.Check("drive " + name + " matches within " + Tol, b == 0, b == 0 ? c + " values" : b + "/" + c + " differ; first: " + first);
            }
            Console.WriteLine("  {0} drives ({1} synthetic, {2} real captures), {3} values compared, {4} mismatches", drives, synth, drives - synth, totalCmp, totalBad);
        }
    }
}
