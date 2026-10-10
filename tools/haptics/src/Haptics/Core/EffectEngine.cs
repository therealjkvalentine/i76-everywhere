using System;
using System.Collections.Generic;
using System.Linq;
using Haptics.Effects;

namespace Haptics.Core
{
    /// <summary>
    /// Interprets "model": "chain" effect files (HAPTICS-ARCHITECTURE 2.2):
    ///   source (event filter + level expression, or a continuous channel expression)
    ///   -> response: input gain, threshold (dead-band), min-force floor, gamma
    ///   -> envelope: transient attack / hold / linear decay with a retrigger policy (restart | max | ignore);
    ///                continuous one-pole smoothing (smooth_ms)
    ///   -> carrier: base_hz .. high_hz by level
    ///   -> routing: wheel (signed, impulse or buzz, direction rule), pad taps, lfe (amp, hz)
    ///   -> mix: group, priority, duck (other groups x (1 - depth x level)).
    /// One voice per effect: a new trigger is resolved by the retrigger policy ("longest/strongest wins",
    /// SIM-RUMBLE-RESEARCH Part E rule 3) rather than stacking copies.
    /// </summary>
    public sealed class EffectEngine
    {
        sealed class Inst
        {
            public EffectDef E;
            public bool Active; public double Start, Level, Dir = 1, Smoothed;
            public double LastT = double.NaN;
        }
        readonly Dictionary<string, Inst> _st = new Dictionary<string, Inst>();
        public IReadOnlyList<EffectDef> Effects;
        public ISet<string> Solo, Mute;

        public EffectEngine(IEnumerable<EffectDef> chainEffects) { Reload(chainEffects); }

        /// <summary>Hot reload: keeps the state of effects whose id survives.</summary>
        public void Reload(IEnumerable<EffectDef> chainEffects)
        {
            Effects = chainEffects.Where(e => e.IsChain).ToList();
            var ids = new HashSet<string>(Effects.Select(e => e.Id));
            foreach (var k in _st.Keys.ToList()) if (!ids.Contains(k)) _st.Remove(k);
            foreach (var e in Effects) { if (_st.TryGetValue(e.Id, out var i)) i.E = e; else _st[e.Id] = new Inst { E = e }; }
        }

        public static double Response(EffectDef e, double x)
        {
            double y = x * e.InputGain;
            if (y <= e.Threshold || y <= 0) return 0.0;
            double u = e.Threshold >= 1 ? 1 : Math.Min(1.0, (y - e.Threshold) / (1.0 - e.Threshold));
            double g = Math.Pow(u, e.Gamma <= 0 ? 1 : e.Gamma);
            return Math.Min(1.0, e.MinForce + (1.0 - e.MinForce) * g);
        }

        /// <summary>Envelope value 0..1 at age (ms), or -1 once finished.</summary>
        public static double Envelope(EffectDef e, double ageMs)
        {
            if (ageMs < 0) return 0;
            if (ageMs < e.AttackMs) return ageMs / e.AttackMs;
            ageMs -= e.AttackMs;
            if (ageMs < e.HoldMs) return 1.0;
            ageMs -= e.HoldMs;
            if (e.DecayMs <= 0) return -1;
            if (ageMs < e.DecayMs) return 1.0 - ageMs / e.DecayMs;
            return -1;
        }

        public static bool Matches(EffectDef e, HapticEvent ev)
        {
            if (!string.Equals(e.SourceEvent, ev.Type, StringComparison.OrdinalIgnoreCase)) return false;
            foreach (var kv in e.Where)
            {
                if (kv.Key == "name_prefix")
                {
                    if (ev.Name == null) return false;
                    bool any = false;
                    if (kv.Value is System.Text.Json.Nodes.JsonArray arr) { foreach (var p in arr) if (ev.Name.StartsWith(p.GetValue<string>(), StringComparison.OrdinalIgnoreCase)) any = true; }
                    else any = ev.Name.StartsWith(kv.Value.GetValue<string>(), StringComparison.OrdinalIgnoreCase);
                    if (!any) return false;
                    continue;
                }
                if (kv.Key == "name")
                {
                    if (!string.Equals(ev.Name, kv.Value.GetValue<string>(), StringComparison.OrdinalIgnoreCase)) return false;
                    continue;
                }
                double have = ev[kv.Key];
                if (kv.Value is System.Text.Json.Nodes.JsonArray list)
                {
                    if (!list.Any(x => Math.Abs(x.GetValue<double>() - have) < 1e-9)) return false;
                }
                else if (Math.Abs(kv.Value.GetValue<double>() - have) > 1e-9) return false;
            }
            return true;
        }

        static double Direction(EffectDef e, HapticEvent ev, VehicleState st)
        {
            switch (e.WheelDirection)
            {
                case "-1": return -1;
                case "side": { int s = (int)ev["side"]; return s == 1 ? -1 : s == 2 ? 1 : 0; }
                case "wheel_side": return ((int)ev["wheel"] % 2 == 0) ? -1 : 1;
                case "impact_x":
                {
                    var b = st != null ? st.ToBody(new Vec3(ev["impact_x"], ev["impact_y"], ev["impact_z"])) : new Vec3(ev["impact_x"], 0, 0);
                    return b.X == 0 ? 1 : Math.Sign(b.X);
                }
                case "from_yaw": return st != null && Math.Abs(st.YawRate) > 0.05 ? Math.Sign(st.YawRate) : 1;
                default: return 1;
            }
        }

        bool On(EffectDef e) => e.Enabled && (Solo == null || Solo.Count == 0 || Solo.Contains(e.Id)) && (Mute == null || !Mute.Contains(e.Id));

        /// <summary>One core update: returns the sounding voices (before ducking; <see cref="ApplyDuck"/> does that).</summary>
        public List<Voice> Step(double t, IList<HapticEvent> events, Dictionary<string, double> vars, VehicleState st)
        {
            var voices = new List<Voice>();
            foreach (var e in Effects)
            {
                var I = _st[e.Id];
                if (!On(e)) { I.Active = false; I.Smoothed = 0; continue; }
                double dt = double.IsNaN(I.LastT) ? 0.016 : Math.Max(0, t - I.LastT);
                I.LastT = t;
                if (e.Kind == "continuous")
                {
                    double x = e.Channel?.Eval(k => vars.TryGetValue(k, out var d) ? d : 0.0) ?? 0;
                    double target = Response(e, x);
                    if (e.SmoothMs > 0) { double k = 1.0 - Math.Exp(-dt * 1000.0 / e.SmoothMs); I.Smoothed += k * (target - I.Smoothed); }
                    else I.Smoothed = target;
                    if (I.Smoothed < 1e-4) continue;
                    voices.Add(MakeVoice(e, I.Smoothed, 1.0, 0, t, st, false));
                    continue;
                }
                if (events != null)
                    foreach (var ev in events)
                    {
                        if (!Matches(e, ev)) continue;
                        double lvl = Response(e, e.Level?.Eval(k => ev.F.TryGetValue(k, out var d) ? d : (vars.TryGetValue(k, out var v2) ? v2 : 0.0)) ?? 1.0);
                        if (lvl <= 0) continue;
                        double curEnv = I.Active ? Math.Max(0, Envelope(e, (t - I.Start) * 1000.0)) * I.Level : 0;
                        bool fire = !I.Active || e.Retrigger == "restart" || (e.Retrigger == "max" && lvl > curEnv);
                        if (!fire) continue;
                        I.Active = true; I.Start = t; I.Level = lvl; I.Dir = Direction(e, ev, st);
                    }
                if (!I.Active) continue;
                double age = (t - I.Start) * 1000.0;
                double env = Envelope(e, age);
                if (env < 0) { I.Active = false; continue; }
                voices.Add(MakeVoice(e, I.Level, env, age, t, st, true, I.Dir));
            }
            return voices;
        }

        static Voice MakeVoice(EffectDef e, double level, double env, double ageMs, double t, VehicleState st, bool transient, double dir = 1)
        {
            double a = level * env;
            var v = new Voice { Id = e.Id, Group = e.Group, Kind = e.Kind, Priority = e.Priority, Level = a, Transient = transient, AgeMs = ageMs };
            if (e.HasWheel)
            {
                double w = e.WheelAmp * a * dir;
                if (e.WheelShape == "buzz") w *= Math.Sin(2 * Math.PI * e.WheelHz * (ageMs / 1000.0) + (transient ? 0 : 2 * Math.PI * e.WheelHz * t));
                v.Wheel = w;
            }
            if (e.HasLfe) { v.LfeAmp = e.LfeAmp * a; v.LfeHz = e.LfeHz > 0 ? e.LfeHz : e.BaseHz + (e.HighHz - e.BaseHz) * level; }
            foreach (var p in e.Pad)
            {
                if (p.From != "level") continue;
                if (p.Motor == 'L') v.PadL = Math.Max(v.PadL, p.Gain * a); else v.PadR = Math.Max(v.PadR, p.Gain * a);
            }
            return v;
        }

        /// <summary>
        /// Ducking: every voice whose effect names duck groups pulls those groups down by (1 - depth x its level);
        /// the deepest duck per group wins. Returns the per-group factor so the reference model's beds can follow.
        /// </summary>
        public Dictionary<string, double> ApplyDuck(List<Voice> voices)
        {
            var duck = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
            foreach (var v in voices)
            {
                var e = Effects.FirstOrDefault(x => x.Id == v.Id);
                if (e == null) continue;
                foreach (var g in e.DuckGroups)
                {
                    double f = 1.0 - e.DuckDepth * Math.Min(1.0, v.Level);
                    duck[g] = duck.TryGetValue(g, out var old) ? Math.Min(old, f) : f;
                }
            }
            foreach (var v in voices)
                if (v.Group != null && duck.TryGetValue(v.Group, out var f) && !(Effects.FirstOrDefault(x => x.Id == v.Id)?.DuckGroups.Contains(v.Group) ?? false))
                {
                    v.Level *= f; v.Wheel *= f; v.LfeAmp *= f; v.PadL *= f; v.PadR *= f;
                }
            return duck;
        }
    }
}
