using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Haptics.Core;
using Haptics.Effects;
using Haptics.Renderers;

namespace Haptics
{
    /// <summary>Builds a Pipeline from an effect set, the rig's outputs and the requested sinks.</summary>
    public static class Session
    {
        static readonly Dictionary<string, string> SinkOutput = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["wheel-file"] = "wheel", ["wheel"] = "wheel", ["pad-file"] = "pad", ["pad"] = "pad", ["lfe-wav"] = "lfe", ["lfe"] = "lfe",
            ["loopback"] = "loopback", ["loopback-wav"] = "loopback", ["motion-file"] = "motion", ["motion"] = "motion",
            ["motion-udp"] = "motion_udp",
        };

        public static Pipeline Build(EffectSet set, IEnumerable<string> sinks, string outDir, string tag, bool live,
                                     int coreHz, int frameHz = 60, string loopbackWav = null, TextWriter log = null, bool hostClock = false)
        {
            var core = new HapticCore(set);
            var p = new Pipeline { Core = core, CoreHz = coreHz };
            var tune = core.Mixer.Tune;
            LfeSynthRenderer synth = null; LfeLoopbackRenderer loop = null;
            foreach (var sink in sinks.Where(x => !string.IsNullOrWhiteSpace(x)))
            {
                if (!SinkOutput.TryGetValue(sink.Trim(), out var output)) throw new ArgumentException("unknown sink '" + sink + "' (known: " + string.Join(", ", SinkOutput.Keys) + ")");
                var cfg = set.Rig.Output(output);
                if (cfg == null) throw new ArgumentException("rig " + set.Rig.Name + " has no '" + output + "' output");
                if (output == "loopback" && loopbackWav != null) cfg = (System.Text.Json.Nodes.JsonObject)cfg.DeepClone();
                if (output == "loopback" && loopbackWav != null) cfg["input_wav"] = loopbackWav;
                var r = RendererRegistry.Create(EffectDef.Str(cfg, "renderer"));
                r.Open(new RendererContext
                {
                    OutputName = output, Config = cfg, Rig = set.Rig, Tune = tune, Effects = set, Live = live, OutDir = outDir, Tag = tag,
                    CoreHz = coreHz > 0 ? coreHz : frameHz, Log = log ?? Console.Out, HostClock = hostClock,
                });
                p.Renderers.Add(r);
                if (r is LfeSynthRenderer s) synth = s;
                if (r is LfeLoopbackRenderer l) loop = l;
            }
            if (synth != null && loop != null) synth.Bed = loop.Bed;
            return p;
        }
    }
}
