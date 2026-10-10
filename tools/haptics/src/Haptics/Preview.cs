using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.Json.Nodes;
using Haptics.Core;
using Haptics.Effects;

namespace Haptics
{
    /// <summary>
    /// The stimulus that makes one effect sound on its own (design facility "preview", HAPTICS-ARCHITECTURE 2.2 item 4;
    /// the generalisation of ffb-lfe-demo.ps1). Chain effects declare theirs in "preview" (an event to inject or frame
    /// values to hold); legacy effects get the scripted telemetry that drives their reference-model channel, the same
    /// kind of inputs ffb-mixer-test.ps1 / ffb-lfe-probe.ps1 use. Run it soloed through the normal pipeline.
    /// </summary>
    public static class Preview
    {
        public const double Seconds = 2.5, Hz = 60.0, At = 0.5;

        public static IEnumerable<FrameIn> Stimulus(EffectDef e)
        {
            var rnd = new Random(1976);
            int n = (int)(Seconds * Hz);
            var pv = e.Json["preview"] as JsonObject;
            for (int i = 0; i < n; i++)
            {
                double t = i / Hz;
                bool at = Math.Abs(t - At) < 0.5 / Hz;
                var s = new Sample { T = t, Speed = 15, Throttle = 0.3, FxEvent = false };
                var events = new List<HapticEvent>();
                uint flags = 0x1;
                switch (e.Model)
                {
                    case "legacy.center": s.Speed = 15; s.Steer = 0.6 * Math.Sin(2 * Math.PI * 0.5 * t); break;
                    case "legacy.corner": s.Speed = 18; s.Steer = 0.5; s.YawRate = 0.5; s.LatG = 1.5; break;
                    case "legacy.grip": s.Speed = 18; s.Steer = 0.5; s.YawRate = 0.5; s.LatG = 1.5; if (t > 1.0 && t < 1.8) s.Oversteer = 0.7; break;
                    case "legacy.oversteer":
                    case "legacy.scrub": s.Speed = 18; s.Steer = 0.5; s.YawRate = 1.6; s.LatG = 2.6; s.Oversteer = t > At ? 0.9 : 0; break;
                    case "legacy.texture":
                    case "legacy.heave":
                        s.Speed = 17.9; s.Throttle = 0.35;
                        if (i % 11 == 0) { s.Jolt = 8.0 + 6.0 * rnd.NextDouble(); s.Vy = 0.35 * (rnd.NextDouble() - 0.5); }
                        s.HeaveAccel = s.Vy * 20.0; break;
                    case "legacy.brake": s.Speed = 16; s.Steer = 0.3; s.Throttle = -0.9; s.LongG = t > At ? -0.8 : 0; break;
                    case "legacy.judder": s.Speed = 16; s.Steer = 0.2; s.Throttle = -1; s.LongG = t > At ? -0.9 : 0; break;
                    case "legacy.impact": s.Speed = 15; s.YawRate = 0.2; s.Jolt = (t >= At && t < At + 0.1) ? 120 : 0; break;
                    case "legacy.shift": s.Speed = 20; s.Shift = at ? 1 : 0; break;
                    case "legacy.weapon": s.Speed = 15; if (at) { s.FxEvent = true; s.FxFired = new List<FxFired> { new FxFired(0, 8, 0.8, 10) }; } break;
                    case "legacy.engine": s.Speed = 10; s.Throttle = t > At ? 1.0 : 0.1; s.Rpm = 1050 + 4950 * Math.Min(1, Math.Max(0, t - At) / 1.2); break;
                    case "legacy.blast": s.Speed = 15; s.Throttle = 0.5; if (at) s.FxFired = new List<FxFired> { new FxFired(0, -2, 0, 60) }; break;
                    default:
                        if (pv?["frames"] is JsonObject fr)
                        {
                            s.Speed = EffectDef.Num(fr, "speed", 15);
                            flags = (uint)EffectDef.Num(fr, "flags", 1);
                            if (t < At) flags = 0x1;
                        }
                        if (at && pv?["event"] is JsonObject ev)
                        {
                            var h = new HapticEvent { Type = EffectDef.Str(ev, "type"), T = t, Name = EffectDef.Str(ev, "name") };
                            foreach (var kv in ev) if (kv.Key != "type" && kv.Key != "name" && kv.Value is JsonValue v && v.TryGetValue<double>(out var d)) h[kv.Key] = d;
                            events.Add(h);
                        }
                        break;
                }
                s.LongAccel = s.LongG * 9.81; s.LatAccel = s.LatG * 9.81;
                if (!s.HeaveAccel.HasValue) s.HeaveAccel = 0; s.TravelPitch = 0;
                var r = Derive.FromSample(s);
                r.State.Flags = flags; r.Vars["flags"] = flags; r.Vars["flag_grip_limit"] = (flags & 0x2000) != 0 ? 1 : 0;
                r.Events.AddRange(events);
                yield return new FrameIn { HostT = t, SimT = t, D = r };
            }
        }
    }
}
