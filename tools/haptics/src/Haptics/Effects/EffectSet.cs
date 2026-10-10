using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using Haptics.Core;

namespace Haptics.Effects
{
    /// <summary>rigs/*.json: which outputs exist, which renderer serves each, gains and limits.</summary>
    public sealed class RigDef
    {
        public string Name, File;
        public JsonObject Json;
        public readonly Dictionary<string, JsonObject> Outputs = new Dictionary<string, JsonObject>(StringComparer.OrdinalIgnoreCase);

        public static RigDef Load(string path)
        {
            var j = JsonNode.Parse(System.IO.File.ReadAllText(path), null, new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip }) as JsonObject;
            var r = new RigDef { Json = j, File = path, Name = EffectDef.Str(j, "name") ?? Path.GetFileNameWithoutExtension(path) };
            if (j["outputs"] is JsonObject o) foreach (var kv in o) if (kv.Value is JsonObject oo) r.Outputs[kv.Key] = oo;
            return r;
        }
        public JsonObject Output(string name) => Outputs.TryGetValue(name, out var o) ? o : null;
        public double Num(string output, string key, double dflt) => EffectDef.Num(Output(output), key, dflt);
        public string Renderer(string output) => EffectDef.Str(Output(output), "renderer");
        public bool OutputEnabled(string output)
        {
            var o = Output(output);
            if (o == null) return false;
            return !(o["enabled"] is JsonValue v && v.TryGetValue<bool>(out var b) && !b);
        }
    }

    public sealed class LintIssue
    {
        public string Rule, Effect, Message; public bool Error;
        public override string ToString() => (Error ? "ERROR " : "warn  ") + Rule + (Effect != null ? " [" + Effect + "]" : "") + ": " + Message;
    }

    /// <summary>
    /// All effect files + the active rig. Builds the reference model's Tune from them via schema/legacy-tunemap.json
    /// (the only place the legacy numbers live now) and lints the set against HAPTICS-ARCHITECTURE 2.2.
    /// </summary>
    public sealed class EffectSet
    {
        public readonly List<EffectDef> Effects = new List<EffectDef>();
        public RigDef Rig;
        public Dictionary<string, string> TuneMap = new Dictionary<string, string>();
        public string EffectsDir, TuneMapPath;
        public readonly List<string> LoadErrors = new List<string>();

        public static string DefaultRoot()
        {
            var d = new DirectoryInfo(AppContext.BaseDirectory);
            while (d != null && !System.IO.File.Exists(Path.Combine(d.FullName, "haptics.ps1"))) d = d.Parent;
            return d?.FullName ?? Directory.GetCurrentDirectory();
        }

        public static EffectSet Load(string effectsDir = null, string rigPath = null, string tunemapPath = null)
        {
            string root = DefaultRoot();
            var set = new EffectSet
            {
                EffectsDir = effectsDir ?? Path.Combine(root, "effects"),
                TuneMapPath = tunemapPath ?? Path.Combine(root, "schema", "legacy-tunemap.json"),
            };
            rigPath = rigPath ?? Path.Combine(root, "rigs", "desk-t300-evo4.json");
            set.Rig = RigDef.Load(rigPath);
            var opts = new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true };
            foreach (var f in Directory.GetFiles(set.EffectsDir, "*.json").OrderBy(x => x, StringComparer.Ordinal))
            {
                try
                {
                    var j = JsonNode.Parse(System.IO.File.ReadAllText(f), null, opts) as JsonObject;
                    set.Effects.Add(EffectDef.Parse(j, f));
                }
                catch (Exception ex) { set.LoadErrors.Add(Path.GetFileName(f) + ": " + ex.Message); }
            }
            if (System.IO.File.Exists(set.TuneMapPath))
            {
                var tm = JsonNode.Parse(System.IO.File.ReadAllText(set.TuneMapPath), null, opts) as JsonObject;
                foreach (var kv in (JsonObject)tm["keys"]) set.TuneMap[kv.Key] = kv.Value.GetValue<string>();
            }
            return set;
        }

        public EffectDef Get(string id) => Effects.FirstOrDefault(e => e.Id == id);

        public static JsonNode Pointer(JsonNode doc, string ptr)
        {
            JsonNode cur = doc;
            foreach (var part in ptr.Trim('/').Split('/'))
            {
                if (cur is JsonObject o && o.TryGetPropertyValue(part, out var nx)) cur = nx;
                else return null;
            }
            return cur;
        }

        /// <summary>The reference model's tune, read from the effect and rig files. Throws listing every key it could not resolve.</summary>
        public Tune BuildTune()
        {
            var t = new Tune();
            var missing = new List<string>();
            foreach (var kv in TuneMap)
            {
                var parts = kv.Value.Split('#');
                JsonNode doc = parts[0] == "rig" ? (JsonNode)Rig.Json : Get(parts[0])?.Json;
                var node = doc == null ? null : Pointer(doc, parts[1]);
                if (node is JsonArray arr) t.SetArray(kv.Key, arr.Select(x => x.GetValue<double>()).ToArray());
                else if (node is JsonValue v && v.TryGetValue<double>(out var d)) t[kv.Key] = d;
                else missing.Add(kv.Key + " -> " + kv.Value);
            }
            if (missing.Count > 0) throw new InvalidDataException("tune keys not found in effect/rig files: " + string.Join("; ", missing));
            return t;
        }

        static readonly Dictionary<string, string> LegacyGate = new Dictionary<string, string>
        {
            ["legacy.center"] = "center", ["legacy.corner"] = "corner", ["legacy.oversteer"] = "oversteer", ["legacy.brake"] = "brake",
            ["legacy.texture"] = "texture", ["legacy.scrub"] = "scrub", ["legacy.judder"] = "judder", ["legacy.impact"] = "impact",
            ["legacy.weapon"] = "weapon", ["legacy.shift"] = "shift",
        };

        /// <summary>Channel gating for the reference model from the legacy effects' "enabled" flags (+ solo/mute by id). null = all on.</summary>
        public Dictionary<string, bool> LegacyActive(ISet<string> solo = null, ISet<string> mute = null)
        {
            var d = new Dictionary<string, bool>();
            bool any = false;
            foreach (var ch in ReferenceMixer.GateChannels) d[ch] = true;
            foreach (var e in Effects)
            {
                if (!LegacyGate.TryGetValue(e.Model ?? "", out var ch)) continue;
                bool on = e.Enabled && (solo == null || solo.Count == 0 || solo.Contains(e.Id)) && (mute == null || !mute.Contains(e.Id));
                if (!on) { d[ch] = false; any = true; }
            }
            return any ? d : null;
        }

        // ------------------------------------------------------------------------------------------------
        // Lints (HAPTICS-ARCHITECTURE 2.2). Rule violations are reported, not fixed: several are deliberate in
        // the shipped tune and the owner decides (the report says which).
        // ------------------------------------------------------------------------------------------------
        public static readonly HashSet<string> FrameVariables = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "speed","steer","throttle","brake","yaw_rate","pitch_rate","roll_rate","rpm","gear","surface","clearance","health_pct",
            "flags","flag_engine_running","flag_skid","flag_airborne","flag_starting","flag_destroyed","flag_oil","flag_nitrous",
            "flag_grip_limit","flag_critical","flag_wreck","accel_x","accel_y","accel_z","vel_x","vel_y","vel_z","pitch","roll",
            "heading","jolt","long_accel","lat_accel","heave_accel","oversteer","understeer","player_present","wheels_flat",
            "susp_max","susp_min","drive_power","mass","music_track","grip_cap","ground_g","wheelbase","sound_voices",
        };
        public static readonly Dictionary<string, string[]> EventFields = new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase)
        {
            ["SHOT"] = new[] { "row", "ammo_left", "dmg_per_hit", "dt_left", "weapdef", "rounds" },
            ["EXPLOSION"] = new[] { "x", "y", "z", "dist" },
            ["IMPACT"] = new[] { "impact_x", "impact_y", "impact_z", "hp_lost", "is_player", "source_class", "impact_mag" },
            ["SOUND_START"] = new[] { "hz", "vol", "x", "y", "z", "pan", "mode", "prio", "is_player", "has_pos", "detached", "obj", "dist" },
            ["SOUND_STOP"] = new[] { "seconds", "reason", "is_player", "obj" },
            ["DAMAGE_SIDE"] = new[] { "amount", "hp_lost", "hit_x", "hit_y", "hit_z", "side", "zone", "is_player", "by_player", "killed", "type_mask", "source_class" },
            ["WEAPON_UI"] = new[] { "action" },
            ["GEAR"] = new[] { "gear", "prev", "dir" },
            ["LANDING"] = new[] { "vy_before", "airtime" },
            ["TAKEOFF"] = new[] { "vy" },
            ["SURFACE"] = new[] { "surface", "prev" },
            ["FLAT"] = new[] { "wheel" },
            ["GRIP_LIMIT"] = new string[0], ["SKID"] = new string[0], ["OIL"] = new string[0],
            ["ENGINE_START"] = new string[0], ["NITROUS"] = new string[0], ["DESTROYED"] = new string[0],
        };

        public List<LintIssue> Lint(Func<double, double> rigComp = null)
        {
            var L = new List<LintIssue>();
            void Add(string rule, string eff, string msg, bool err = false) => L.Add(new LintIssue { Rule = rule, Effect = eff, Message = msg, Error = err });
            foreach (var le in LoadErrors) Add("parse", null, le, true);
            try { BuildTune(); } catch (Exception ex) { Add("tunemap", null, ex.Message, true); }

            double deadzone = Rig.Num("pad", "deadzone", 0.30);
            string padMode = EffectDef.Str(Get("global.mixer")?.Json?["mix"] as JsonObject, "pad_mode") ?? "max";
            var on = Effects.Where(e => e.Enabled).ToList();

            foreach (var e in Effects)
            {
                if (Path.GetFileNameWithoutExtension(e.File) != e.Id) Add("id", e.Id, "id does not match its file name " + Path.GetFileName(e.File), true);
                if (e.IsChain)
                {
                    if (e.Kind == "transient" && e.SourceEvent == null) Add("source", e.Id, "transient chain effect without source.event", true);
                    if (e.Kind == "continuous" && e.Channel == null) Add("source", e.Id, "continuous chain effect without source.channel", true);
                    if (e.SourceEvent != null && !EventFields.ContainsKey(e.SourceEvent)) Add("source", e.Id, "unknown event type " + e.SourceEvent, true);
                    var known = new HashSet<string>(FrameVariables, StringComparer.OrdinalIgnoreCase);
                    if (e.SourceEvent != null && EventFields.TryGetValue(e.SourceEvent, out var ef)) foreach (var f in ef) known.Add(f);
                    foreach (var x in new[] { e.Level, e.Channel })
                        if (x != null) foreach (var v in x.Variables) if (!known.Contains(v)) Add("expr", e.Id, "unknown variable '" + v + "' in '" + x.Text + "'", true);
                }
                else if (!e.IsLegacy) Add("model", e.Id, "unknown model '" + e.Model + "'", true);
            }

            // pad: envelopes shorter than the ERM can render; amplitudes under the dead-zone when nothing lifts them
            foreach (var e in on.Where(x => x.IsChain && x.Kind == "transient" && x.Pad.Count > 0))
                if (e.AttackMs + e.HoldMs + e.DecayMs < 40) Add("pad-envelope", e.Id, string.Format(CultureInfo.InvariantCulture, "pad pulse {0} ms < 40 ms (ERM spin-up 20-30 ms)", e.AttackMs + e.HoldMs + e.DecayMs));
            if (padMode == "sum")
                foreach (var e in on) foreach (var p in e.Pad) if (p.Gain > 0 && p.Gain < deadzone) Add("pad-deadzone", e.Id, "pad tap gain " + p.Gain + " cannot clear the " + deadzone + " dead-zone in 'sum' mode (no lift)");

            // shaker: carriers in band, continuous count, separation, headroom
            var lfeSources = new List<(string id, string kind, double lo, double hi, double amp)>();
            foreach (var e in on)
            {
                var r = e.Json["routing"] as JsonObject; var lf = r?["lfe"] as JsonObject;
                if (lf == null || lf["amp"] == null) continue;
                double amp = EffectDef.Num(lf, "amp", 0);
                double lo, hi;
                if (lf["hz_lo"] != null) { lo = EffectDef.Num(lf, "hz_lo", 0); hi = EffectDef.Num(lf, "hz_hi", lo); }
                else if (lf["hz"] != null) { lo = hi = EffectDef.Num(lf, "hz", 0); }
                else { var c = e.Json["carrier"] as JsonObject; lo = EffectDef.Num(c, "base_hz", 0); hi = EffectDef.Num(c, "high_hz", lo); }
                lfeSources.Add((e.Id, e.Kind, lo, hi, amp));
                if (lo < 22 || hi > 90) Add("lfe-band", e.Id, string.Format(CultureInfo.InvariantCulture, "shaker carrier {0}-{1} Hz outside 22-90 Hz", lo, hi));
            }
            var cont = lfeSources.Where(s => s.kind == "continuous").ToList();
            if (cont.Count > 3) Add("lfe-continuous-count", null, cont.Count + " continuous shaker sources (" + string.Join(", ", cont.Select(c => c.id)) + ") > 3 (SimHub/design-library rule)");
            for (int i = 0; i < cont.Count; i++)
                for (int k = i + 1; k < cont.Count; k++)
                {
                    double gap = Math.Max(0, Math.Max(cont[i].lo, cont[k].lo) - Math.Min(cont[i].hi, cont[k].hi));
                    if (gap < 8) Add("lfe-separation", cont[i].id + "+" + cont[k].id, string.Format(CultureInfo.InvariantCulture,
                        "continuous sources {0}-{1} Hz and {2}-{3} Hz are within 8 Hz", cont[i].lo, cont[i].hi, cont[k].lo, cont[k].hi));
                }
            Func<double, double> comp = rigComp ?? (hz => 1.0);
            double beds = cont.Sum(c => c.amp * comp(c.lo));
            foreach (var tr in lfeSources.Where(s => s.kind == "transient"))
            {
                var e = Get(tr.id);
                double duck = e.DuckGroups.Count > 0 ? 1.0 - e.DuckDepth : 1.0;
                double head = beds * duck + tr.amp * comp(tr.lo);
                if (head > 0.95) Add("lfe-headroom", tr.id, string.Format(CultureInfo.InvariantCulture,
                    "every continuous bed at full + this transient = {0:0.00} of full scale (pre-drive) > 0.95", head));
            }

            // wheel: continuous budget
            var tune = SafeTune();
            if (tune != null)
            {
                double steadyMax = tune["SatGain"] + tune["CornerGain"];
                double frac = steadyMax / tune["Clamp"];
                if (frac > 0.70) Add("wheel-budget", "steer.center+steer.corner", string.Format(CultureInfo.InvariantCulture,
                    "continuous wheel channels reach {0:0}% of the clamp at full lock and speed (rule: 40-70%)", frac * 100));
            }
            return L;
        }

        Tune SafeTune() { try { return BuildTune(); } catch { return null; } }
    }
}
