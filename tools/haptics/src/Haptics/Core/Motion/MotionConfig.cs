using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Haptics.Core.Motion
{
    /// <summary>
    /// The motion pipeline's parameters: the rig's "motion" section (cueing, safety) plus motion/targets.json (output rate,
    /// resampler, where each wire format goes). docs/MOTION-OUTPUT.md section 7. Every default below is the design's.
    /// </summary>
    public sealed class MotionParams
    {
        // ---- output / resampling (targets.json) ----
        public double OutputHz = 100;              // 60..100 recommended; lint below 2 x the physics step rate in interp mode
        public string Resample = "interp";         // "interp" (linear, +1 physics step latency) | "hold" (zero-order hold + 1st-order LP)
        public double HoldLpHz = 8;

        // ---- derivation (rig motion section) ----
        public string AccelSource = "integrator";  // "integrator" (ent+0xd4 / FFB accel_body) | "differentiated" (dv/dt across physics steps) | "blend"
        public double BlendHz = 2.0;               // blend: integrator below, high-passed a_diff above
        public bool AirborneZeroPhysics = true;    // gate the physics accelerations while flags & 4 (gravity convention of the airborne branch unknown)
        public double SpeedRef = 30.0;             // texture = surface amplitude x speed / SpeedRef, clamped 0..1
        public Dictionary<string, double> Surfaces = new Dictionary<string, double> { ["0"] = 0.0, ["2"] = 0.1, ["default"] = 0.3 };
        public double FixedStepHz = 24;            // I76_FIXED_STEP rate: physics dt = step_count / this, when the stream is in fixed-step mode
        public double SteerLockRad = 0.76;         // OutSimPack2 InputSteer = steer x lock (ffb-calib value until ent+0x118 lock is exported)
        public double WheelRadius = 0.35;          // Forza wheel rotation speed / normalised travel until the radius is exported (M5)
        public double SuspTravel = 0.0875;         // +-0.25 x r: Forza NormalizedSuspensionTravel = 0.5 + offset / (2 x travel)

        // ---- cues ----
        public double ImpactGain = 1.0, ImpactPeak = 30.0, ImpactTauMs = 60;     // peak m/s^2 at 60 hp lost, x gain
        public double ExplosionGain = 40.0, ExplosionTauMs = 120, ExplosionMinDist = 3.0, ExplosionPush = 0.25;
        public double LandingK = 1.0, LandingTauMs = 80;                          // m/s^2 per m/s of vertical speed before touchdown
        public double ShotRecoil = 0.0, ShotTauMs = 40;                           // off by default (weapons already drive wheel / pad)
        public double ImpulseThreshold = 25.0, ImpulseGain = 0.5;                 // a_diff - integrator residual above this becomes a cue
        public double CueMax = 60.0, MinGapMs = 150;
        public string CueBudget = "max";                                          // overlapping cues: max per axis, never the sum

        // ---- safety (section 6) ----
        public double StaleMs = 250, NeutralRampMs = 1000, StartupNeutralS = 2.0;
        public bool ClampUdp = false;                                             // software targets: off (rig software crops)
        public double ClampAccel = 3 * 9.81, ClampCue = 6 * 9.81, ClampRate = 2.0, ClampAngle = 0.35;
        public double MaxJerk = 400, MaxRateChange = 20;                          // slew limits (m/s^3, rad/s^2) when a target enables slew

        // ---- washout (M6, stub) ----
        public bool WashoutEnabled = false;

        public readonly List<MotionTarget> Targets = new List<MotionTarget>();
        public string TargetsFile;
        public readonly List<string> Warnings = new List<string>();

        public static string DefaultTargetsPath() => Path.Combine(Effects.EffectSet.DefaultRoot(), "motion", "targets.json");

        static JsonObject Parse(string path) =>
            JsonNode.Parse(File.ReadAllText(path), null, new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true }) as JsonObject;

        static double N(JsonObject o, string k, double d) => Effects.EffectDef.Num(o, k, d);
        static string S(JsonObject o, string k, string d) => Effects.EffectDef.Str(o, k) ?? d;
        static bool B(JsonObject o, string k, bool d) => o != null && o[k] is JsonValue v && v.TryGetValue<bool>(out var b) ? b : d;

        /// <summary>rigMotion = the rig file's top-level "motion" object (may be null); targetsPath null = motion/targets.json.</summary>
        public static MotionParams Load(JsonObject rigMotion, string targetsPath = null)
        {
            var p = new MotionParams();
            var m = rigMotion;
            if (m != null)
            {
                p.AccelSource = S(m, "accel_source", p.AccelSource);
                p.BlendHz = N(m, "blend_hz", p.BlendHz);
                p.AirborneZeroPhysics = B(m, "airborne_zero_physics", p.AirborneZeroPhysics);
                p.HoldLpHz = N(m, "hold_lp_hz", p.HoldLpHz);
                p.SpeedRef = N(m, "speed_ref", p.SpeedRef);
                p.FixedStepHz = N(m, "fixed_step_hz", p.FixedStepHz);
                p.SteerLockRad = N(m, "steer_lock_rad", p.SteerLockRad);
                p.WheelRadius = N(m, "wheel_radius", p.WheelRadius);
                p.SuspTravel = N(m, "susp_travel", p.SuspTravel);
                if (m["surfaces"] is JsonObject so) { p.Surfaces.Clear(); foreach (var kv in so) p.Surfaces[kv.Key] = (double)kv.Value; }
                if (m["cues"] is JsonObject c)
                {
                    p.ImpactGain = N(c, "impact_gain", p.ImpactGain); p.ImpactPeak = N(c, "impact_peak", p.ImpactPeak); p.ImpactTauMs = N(c, "impact_tau_ms", p.ImpactTauMs);
                    p.ExplosionGain = N(c, "explosion_gain", p.ExplosionGain); p.ExplosionTauMs = N(c, "explosion_tau_ms", p.ExplosionTauMs);
                    p.ExplosionMinDist = N(c, "explosion_min_dist", p.ExplosionMinDist); p.ExplosionPush = N(c, "explosion_push", p.ExplosionPush);
                    p.LandingK = N(c, "landing_k", p.LandingK); p.LandingTauMs = N(c, "landing_tau_ms", p.LandingTauMs);
                    p.ShotRecoil = N(c, "shot_recoil", p.ShotRecoil); p.ShotTauMs = N(c, "shot_tau_ms", p.ShotTauMs);
                    p.ImpulseThreshold = N(c, "impulse_threshold", p.ImpulseThreshold); p.ImpulseGain = N(c, "impulse_gain", p.ImpulseGain);
                    p.CueMax = N(c, "cue_max", p.CueMax); p.MinGapMs = N(c, "min_gap_ms", p.MinGapMs); p.CueBudget = S(c, "cue_budget", p.CueBudget);
                }
                if (m["safety"] is JsonObject s)
                {
                    p.ClampUdp = B(s, "clamp_udp", p.ClampUdp); p.StaleMs = N(s, "stale_ms", p.StaleMs); p.NeutralRampMs = N(s, "neutral_ramp_ms", p.NeutralRampMs);
                    p.StartupNeutralS = N(s, "startup_neutral_s", p.StartupNeutralS); p.MaxJerk = N(s, "max_jerk", p.MaxJerk); p.MaxRateChange = N(s, "max_rate_change", p.MaxRateChange);
                    p.ClampAccel = N(s, "clamp_accel", p.ClampAccel); p.ClampCue = N(s, "clamp_cue", p.ClampCue); p.ClampRate = N(s, "clamp_rate", p.ClampRate); p.ClampAngle = N(s, "clamp_angle", p.ClampAngle);
                    if (s["cue_budget"] != null) p.CueBudget = S(s, "cue_budget", p.CueBudget);
                }
                if (m["washout"] is JsonObject w) p.WashoutEnabled = B(w, "enabled", false);
            }
            p.TargetsFile = targetsPath ?? DefaultTargetsPath();
            if (File.Exists(p.TargetsFile))
            {
                var t = Parse(p.TargetsFile);
                p.OutputHz = N(t, "output_hz", p.OutputHz);
                p.Resample = S(t, "resample", p.Resample);
                if (t["hold_lp_hz"] != null) p.HoldLpHz = N(t, "hold_lp_hz", p.HoldLpHz);
                if (t["targets"] is JsonArray arr)
                    foreach (var n in arr.OfType<JsonObject>()) p.Targets.Add(MotionTarget.From(n));
            }
            else if (targetsPath != null) throw new FileNotFoundException("motion targets file not found", targetsPath);
            return p;
        }

        /// <summary>Config lints (section 6 item 8). Errors stop a run; warnings are printed.</summary>
        public List<LintMsg> Lint(IEnumerable<MotionTarget> active = null)
        {
            var o = new List<LintMsg>();
            void E(string m) => o.Add(new LintMsg { Error = true, Message = m });
            void W(string m) => o.Add(new LintMsg { Error = false, Message = m });
            if (OutputHz < 60) W("output_hz " + OutputHz + " is below the 60 Hz minimum the design library asks for");
            if (OutputHz > 1000) E("output_hz " + OutputHz + " is not sensible");
            if (Resample != "interp" && Resample != "hold") E("resample must be interp or hold, not '" + Resample + "'");
            if (Resample == "interp" && OutputHz < 2 * 24) E("interp needs output_hz >= 2 x the 24 Hz physics step rate");
            if (AccelSource != "integrator" && AccelSource != "differentiated" && AccelSource != "blend") E("accel_source '" + AccelSource + "' unknown");
            if (ClampAccel > 3 * 9.81 + 1e-9 || ClampCue > 6 * 9.81 + 1e-9 || ClampRate > 2.0 + 1e-9 || ClampAngle > 0.35 + 1e-9)
                E("a rig may tighten the safety clamps, never widen them (max +-3 g steady, +-6 g cues, +-2 rad/s, +-0.35 rad)");
            if (StaleMs <= 0 || StaleMs > 1000) E("stale_ms " + StaleMs + " outside 1..1000");
            if (NeutralRampMs < 100) W("neutral_ramp_ms " + NeutralRampMs + " is close to a step (a jolt on a rig)");
            if (WashoutEnabled) E("washout.enabled: Motion.Washout is phase M6 and not implemented (UDP targets get raw data; the rig software owns cueing)");
            var list = (active ?? Targets.Where(t => t.Enabled)).ToList();
            foreach (var t in list)
            {
                if (!MotionTarget.Formats.Contains(t.Format)) E("target " + t.Name + ": format '" + t.Format + "' unknown (" + string.Join(", ", MotionTarget.Formats) + ")");
                if (t.Frame != "world" && t.Frame != "body") E("target " + t.Name + ": frame must be world or body, not '" + t.Frame + "'");
                if (!t.IsLoopback && !t.AllowRemote) E("target " + t.Name + ": host " + t.Host + " is not loopback; set \"allow_remote\": true to send off this machine");
                if (t.Port <= 0 || t.Port > 65535) E("target " + t.Name + ": port " + t.Port);
            }
            foreach (var g in list.SelectMany(t => t.Streams().Select(s => (t, s))).GroupBy(x => (x.t.Host, x.s.port)).Where(g => g.Select(x => x.s.kind).Distinct().Count() > 1))
                W("port " + g.Key.port + " receives different formats (" + string.Join(", ", g.Select(x => x.t.Name + ":" + x.s.kind)) + "): only one consumer can listen there, sending both is harmless");
            return o;
        }
    }

    public sealed class LintMsg { public bool Error; public string Message; public override string ToString() => (Error ? "ERROR " : "warn  ") + Message; }

    /// <summary>One consumer: a wire format, a UDP destination and the per-format options.</summary>
    public sealed class MotionTarget
    {
        public static readonly string[] Formats = { "lfs-classic", "lfs-pack2", "outgauge", "forza-sled", "forza-dash", "i76motion" };
        public string Name, Format, Host = "127.0.0.1", Frame = "world", Note;
        public int Port, Id, GaugePort, GaugeId;
        public bool Enabled = true, AllowRemote, Clamp, Slew;
        public JsonObject Json;

        public bool IsLoopback => Host == "127.0.0.1" || Host == "localhost" || Host == "::1" || Host.StartsWith("127.");

        public static MotionTarget From(JsonObject n)
        {
            var t = new MotionTarget
            {
                Json = n,
                Name = Effects.EffectDef.Str(n, "name") ?? "target",
                Format = Effects.EffectDef.Str(n, "format") ?? "i76motion",
                Host = Effects.EffectDef.Str(n, "host") ?? "127.0.0.1",
                Frame = Effects.EffectDef.Str(n, "frame") ?? "world",
                Note = Effects.EffectDef.Str(n, "note"),
                Port = (int)Effects.EffectDef.Num(n, "port", 0),
                Id = (int)Effects.EffectDef.Num(n, "id", 0),
                GaugePort = (int)Effects.EffectDef.Num(n, "gauge_port", 0),
                GaugeId = (int)Effects.EffectDef.Num(n, "gauge_id", 0),
            };
            bool B(string k, bool d) => n[k] is JsonValue v && v.TryGetValue<bool>(out var b) ? b : d;
            t.Enabled = B("enabled", true); t.AllowRemote = B("allow_remote", false); t.Clamp = B("clamp", false); t.Slew = B("slew", false);
            if (t.Port == 0) t.Port = t.Format == "i76motion" ? 7677 : t.Format.StartsWith("forza") ? 5300 : t.Format == "outgauge" ? 4124 : 4123;
            return t;
        }

        /// <summary>(kind, port) of every datagram stream this target sends: the main format plus OutGauge for LFS targets with a gauge_port.</summary>
        public IEnumerable<(string kind, int port)> Streams()
        {
            yield return (Format, Port);
            if ((Format == "lfs-classic" || Format == "lfs-pack2") && GaugePort > 0) yield return ("outgauge", GaugePort);
        }

        public override string ToString() => string.Format(CultureInfo.InvariantCulture, "{0} ({1} -> {2}:{3}{4}{5})", Name, Format, Host, Port,
            GaugePort > 0 ? ", OutGauge :" + GaugePort : "", Format.StartsWith("lfs") ? ", id " + Id + ", frame " + Frame : "");
    }
}
