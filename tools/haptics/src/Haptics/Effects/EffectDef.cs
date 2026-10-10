using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.Json.Nodes;

namespace Haptics.Effects
{
    public sealed class PadTap
    {
        public char Motor;        // 'L' heavy/low, 'R' buzz/high
        public double Gain;
        public string From;       // "level" (the effect's own level) or a bus signal, see Core/PadMixer
    }

    /// <summary>
    /// One effects/*.json. Shape: HAPTICS-ARCHITECTURE section 4.2 (ShakeIt response chain + AHAP-style
    /// transient/continuous envelope + per-output routing). Legacy effects ("model": "legacy.*") carry the
    /// reference model's tune at the pointers in schema/legacy-tunemap.json; chain effects ("model": "chain")
    /// are interpreted by Core/EffectEngine.
    /// </summary>
    public sealed class EffectDef
    {
        public string Id, Kind, Model, File;
        public bool Enabled = true;
        public JsonObject Json;

        // chain-effect fields (also parsed for legacy ones where present)
        public string SourceEvent;
        public Dictionary<string, JsonNode> Where = new Dictionary<string, JsonNode>(StringComparer.OrdinalIgnoreCase);
        public Expr Level, Channel;
        public double InputGain = 1, Threshold = 0, MinForce = 0, Gamma = 1;
        public double AttackMs, HoldMs, DecayMs, SmoothMs;
        public string Retrigger = "max";
        public double BaseHz, HighHz;
        public double WheelAmp, WheelHz; public string WheelShape = "impulse", WheelDirection = "+1";
        public bool HasWheel, HasLfe;
        public double LfeAmp, LfeHz;
        public List<PadTap> Pad = new List<PadTap>();
        public string Group = "default";
        public int Priority = 50;
        public List<string> DuckGroups = new List<string>();
        public double DuckDepth;

        public bool IsLegacy => Model != null && Model.StartsWith("legacy.", StringComparison.Ordinal);
        public bool IsChain => Model == "chain";

        public static EffectDef Parse(JsonObject j, string file)
        {
            var e = new EffectDef { Json = j, File = file };
            e.Id = Str(j, "id") ?? System.IO.Path.GetFileNameWithoutExtension(file);
            e.Kind = Str(j, "kind") ?? "transient";
            e.Model = Str(j, "model") ?? "chain";
            if (j["enabled"] is JsonValue ev && ev.TryGetValue<bool>(out var en)) e.Enabled = en;

            if (j["source"] is JsonObject src)
            {
                e.SourceEvent = Str(src, "event");
                if (src["where"] is JsonObject w) foreach (var kv in w) e.Where[kv.Key] = kv.Value;
                if (e.IsChain)
                {
                    var lvl = Str(src, "level"); if (lvl != null) e.Level = new Expr(lvl);
                    var chn = Str(src, "channel"); if (chn != null) e.Channel = new Expr(chn);
                }
            }
            if (j["response"] is JsonObject r)
            {
                e.InputGain = Num(r, "input_gain", 1); e.Threshold = Num(r, "threshold", 0);
                e.MinForce = Num(r, "min_force", 0); e.Gamma = Num(r, "gamma", 1);
            }
            if (j["envelope"] is JsonObject env)
            {
                e.AttackMs = Num(env, "attack_ms", 0); e.HoldMs = Num(env, "hold_ms", 0); e.DecayMs = Num(env, "decay_ms", 0);
                e.SmoothMs = Num(env, "smooth_ms", 0); e.Retrigger = Str(env, "retrigger") ?? "max";
            }
            if (j["carrier"] is JsonObject c) { e.BaseHz = Num(c, "base_hz", 0); e.HighHz = Num(c, "high_hz", e.BaseHz); }
            if (j["routing"] is JsonObject rt)
            {
                if (rt["wheel"] is JsonObject wh)
                {
                    e.HasWheel = true;
                    e.WheelAmp = Num(wh, "amp", 0); e.WheelHz = Num(wh, "hz", 13);
                    e.WheelShape = Str(wh, "shape") ?? "impulse"; e.WheelDirection = Str(wh, "direction") ?? "+1";
                }
                if (rt["lfe"] is JsonObject lf && lf["amp"] != null)
                {
                    e.HasLfe = true; e.LfeAmp = Num(lf, "amp", 0); e.LfeHz = Num(lf, "hz", e.BaseHz);
                }
                if (rt["pad"] is JsonArray pa)
                    foreach (var p in pa)
                        if (p is JsonObject po)
                            e.Pad.Add(new PadTap { Motor = (Str(po, "motor") ?? "L")[0], Gain = Num(po, "gain", 0), From = Str(po, "from") ?? "level" });
            }
            if (j["mix"] is JsonObject m)
            {
                e.Group = Str(m, "group") ?? "default";
                e.Priority = (int)Num(m, "priority", 50);
                if (m["duck"] is JsonObject d)
                {
                    if (d["groups"] is JsonArray ga) foreach (var g in ga) e.DuckGroups.Add(g.GetValue<string>());
                    e.DuckDepth = Num(d, "depth", 0);
                }
            }
            return e;
        }

        public static string Str(JsonObject o, string k) =>
            o != null && o[k] is JsonValue v && v.TryGetValue<string>(out var s) ? s : null;

        public static double Num(JsonObject o, string k, double dflt)
        {
            if (o == null || !(o[k] is JsonValue v)) return dflt;
            if (v.TryGetValue<double>(out var d)) return d;
            if (v.TryGetValue<int>(out var i)) return i;
            if (v.TryGetValue<long>(out var l)) return l;
            if (v.TryGetValue<string>(out var s) && double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out var p)) return p;
            return dflt;
        }

        public override string ToString() => Id + " (" + Model + ")";
    }
}
