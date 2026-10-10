using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json.Nodes;
using Haptics;
using Haptics.Core;
using Haptics.Effects;
using Haptics.Renderers;

namespace Haptics.Tests
{
    static class CoreTests
    {
        public static void Run()
        {
            T.Section("A3 effect files: the tune read back from effects/ + rigs/ equals Mix-DefaultTune");
            var set = EffectSet.Load();
            T.Check("all effect files parse", set.LoadErrors.Count == 0, string.Join("; ", set.LoadErrors));
            Tune ft = null;
            try { ft = set.BuildTune(); } catch (Exception ex) { T.Check("BuildTune resolves every tunemap pointer", false, ex.Message); }
            if (ft != null)
            {
                var oracle = Tune.Defaults();
                int diff = 0; string first = null;
                foreach (var k in oracle.ScalarKeys) if (!ft.Has(k) || ft[k] != oracle[k]) { diff++; first = first ?? k + ": file " + (ft.Has(k) ? ft.Describe(k) : "absent") + " vs " + oracle.Describe(k); }
                foreach (var k in oracle.ArrayKeys) if (!ft.Has(k) || !ft.Array(k).SequenceEqual(oracle.Array(k))) { diff++; first = first ?? k; }
                T.Check("66 keys, every value equal (per key)", ft.Count == 66 && oracle.Count == 66 && diff == 0, "file keys " + ft.Count + ", diffs " + diff + " " + first);
                T.Check("every tunemap key maps to a distinct pointer", set.TuneMap.Values.Distinct().Count() == set.TuneMap.Count, "");
            }

            T.Section("lints (HAPTICS-ARCHITECTURE 2.2)");
            var lint = set.Lint();
            T.Check("no lint ERRORS (warnings are listed, several are deliberate in the shipped tune)", !lint.Any(i => i.Error),
                string.Join(" | ", lint.Where(i => i.Error).Select(i => i.ToString())));
            Console.WriteLine("    known warnings: " + string.Join("; ", lint.Where(i => !i.Error).Select(i => i.Rule + (i.Effect != null ? "[" + i.Effect + "]" : ""))));
            var broken = EffectDef.Parse(JsonNode.Parse("{\"id\":\"x\",\"kind\":\"transient\",\"model\":\"chain\",\"source\":{\"event\":\"IMPACT\",\"level\":\"bogus_var * 2\"}}") as JsonObject, "x.json");
            var set2 = EffectSet.Load(); set2.Effects.Add(broken);
            T.Check("the linter catches an unknown expression variable", set2.Lint().Any(i => i.Error && i.Rule == "expr"), "");

            T.Section("expressions");
            var e1 = new Expr("clamp(hp_lost / 60, 0, 1)");
            T.Check("clamp(hp_lost/60,0,1) at 30 = 0.5", Math.Abs(e1.Eval(k => k == "hp_lost" ? 30 : 0) - 0.5) < 1e-12, "");
            T.Check("... and saturates at 1", e1.Eval(k => 600) == 1.0, "");
            T.Check("precedence and unary minus: -2 + 3 * 4 = 10", new Expr("-2 + 3 * 4").Eval(k => 0) == 10, "");
            T.Check("division by zero gives 0, not Inf", new Expr("1 / x").Eval(k => 0) == 0, "");
            bool threw = false; try { new Expr("foo(1)"); } catch (FormatException) { threw = true; }
            T.Check("unknown function rejected at load", threw, "");

            T.Section("A2 golden again, tune read from the effect files (the migration is behaviour-preserving)");
            GoldenTests.Run(() => EffectSet.Load().BuildTune(), "tune from effects/*.json + rigs/*.json");

            T.Section("effect engine: response chain, envelopes, retrigger, duck");
            var eng = MakeEngine(out var eff);
            T.Check("response: below threshold is 0", EffectEngine.Response(eff, 0.01) == 0, "");
            T.Check("response: just above threshold lands on the min-force floor", Math.Abs(EffectEngine.Response(eff, 0.0201) - eff.MinForce) < 0.01, EffectEngine.Response(eff, 0.0201).ToString());
            T.Check("response: full input = 1", Math.Abs(EffectEngine.Response(eff, 1.0) - 1.0) < 1e-9, "");
            var ev = new HapticEvent { Type = "IMPACT" }; ev["is_player"] = 1; ev["hp_lost"] = 60;
            var vars = new Dictionary<string, double>();
            var v0 = eng.Step(1.0, new[] { ev }, vars, new VehicleState());
            T.Check("an IMPACT event starts a voice", v0.Count == 1 && v0[0].Id == eff.Id, "voices " + v0.Count);
            var v1 = eng.Step(1.03, null, vars, new VehicleState());
            T.Check("held through hold_ms (40 ms)", v1.Count == 1 && Math.Abs(v1[0].Level - 1.0) < 1e-9, v1.Count > 0 ? v1[0].Level.ToString() : "none");
            var v2 = eng.Step(1.2, null, vars, new VehicleState());
            T.Check("decaying after the hold", v2.Count == 1 && v2[0].Level < 1.0 && v2[0].Level > 0, v2.Count > 0 ? v2[0].Level.ToString() : "none");
            var v3 = eng.Step(1.5, null, vars, new VehicleState());
            T.Check("silent after attack+hold+decay", v3.Count == 0, "");
            var other = new HapticEvent { Type = "IMPACT" }; other["is_player"] = 0; other["hp_lost"] = 60;
            T.Check("'where' filter: a hit on someone else does nothing", eng.Step(2.0, new[] { other }, vars, null).Count == 0, "");
            // retrigger "max": a weaker hit during a strong one is ignored, a stronger one restarts
            eng.Step(3.0, new[] { ev }, vars, null);
            var weak = new HapticEvent { Type = "IMPACT" }; weak["is_player"] = 1; weak["hp_lost"] = 6;
            var vw = eng.Step(3.01, new[] { weak }, vars, null);
            T.Check("retrigger max: a weaker hit does not cut a strong one short", vw.Count == 1 && vw[0].Level > 0.9, vw.Count > 0 ? vw[0].Level.ToString() : "");
            // duck and its release
            var voices = eng.Step(4.0, new[] { ev }, vars, null);
            var bed = new Voice { Id = "x", Group = "engine", Level = 1, LfeAmp = 0.4 };
            voices.Add(bed);
            var duck = eng.ApplyDuck(voices);
            T.Check("a ducking voice pulls its target group down", duck.ContainsKey("engine") && bed.LfeAmp < 0.4 - 1e-6, "lfe " + bed.LfeAmp);
            var later = eng.Step(5.0, null, vars, null);
            T.Check("duck released once the ducking voice ends", eng.ApplyDuck(later).Count == 0, "");

            T.Section("no NaN / no exception under zeroed and degenerate frames");
            var core = new HapticCore(EffectSet.Load());
            bool bad = false; string why = "";
            try
            {
                foreach (var sp in new[] { 0.0, 1e-9, 3, 200 })
                    foreach (var yw in new[] { 0.0, 1e-9, -1e-9, 5 })
                    {
                        var s = new Sample { T = 1 + sp + yw, Speed = sp, YawRate = yw, Steer = 0.5, LatG = 2, Understeer = 0.5, Oversteer = 0.5, HeaveAccel = 0, LongAccel = 0, LatAccel = 0 };
                        var r = Derive.FromSample(s);
                        var st = core.Step(r, new List<HapticEvent>(), s.T);
                        if (double.IsNaN(st.Mix.Force) || double.IsNaN(st.Bus.VoiceWheel) || st.Bus.Voices.Any(v => double.IsNaN(v.Level))) { bad = true; why = "NaN at speed " + sp; }
                    }
                var zero = Derive.FromSample(new Sample());
                core.Step(zero, new List<HapticEvent>(), 9.0);
            }
            catch (Exception ex) { bad = true; why = ex.Message; }
            T.Check("all-zero and degenerate samples: no NaN, no throw", !bad, why);

            T.Section("disabling an effect file gates its reference-model channel");
            var setOff = EffectSet.Load(); setOff.Get("steer.center").Enabled = false;
            var c1 = new HapticCore(EffectSet.Load()); var c2 = new HapticCore(setOff);
            CoreStep a = null, b = null;
            for (double t = 0; t < 2; t += 1 / 60.0)
            {
                var s = new Sample { T = t, Speed = 15, Steer = 0.6, LongAccel = 0, LatAccel = 0, HeaveAccel = 0 };
                a = c1.Step(Derive.FromSample(s), new List<HapticEvent>(), t); b = c2.Step(Derive.FromSample(s.Clone()), new List<HapticEvent>(), t);
            }
            T.Check("steer.center on: centring force present", Math.Abs(a.Mix.Force) > 500, a.Mix.Force.ToString());
            T.Check("steer.center \"enabled\": false -> no centring force", Math.Abs(b.Mix.Force) < 400, b.Mix.Force.ToString());
        }

        static EffectEngine MakeEngine(out EffectDef e)
        {
            var j = JsonNode.Parse(@"{""id"":""t.impact"",""kind"":""transient"",""model"":""chain"",
              ""source"":{""event"":""IMPACT"",""where"":{""is_player"":1},""level"":""clamp(hp_lost / 60, 0, 1)""},
              ""response"":{""input_gain"":1,""threshold"":0.02,""min_force"":0.25,""gamma"":1},
              ""envelope"":{""attack_ms"":0,""hold_ms"":40,""decay_ms"":220,""retrigger"":""max""},
              ""routing"":{""wheel"":{""amp"":0.8,""shape"":""impulse"",""direction"":""+1""},""pad"":[{""motor"":""L"",""gain"":1}],""lfe"":{""amp"":0.6,""hz"":30}},
              ""mix"":{""group"":""impact"",""priority"":90,""duck"":{""groups"":[""engine""],""depth"":0.5}}}") as JsonObject;
            e = EffectDef.Parse(j, "t.impact.json");
            return new EffectEngine(new[] { e });
        }
    }
}
