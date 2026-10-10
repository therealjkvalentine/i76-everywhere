using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using Haptics.Effects;
using Haptics.Renderers;
using Haptics.Transport;

namespace Haptics.Host
{
    /// <summary>
    /// `haptics stems ...`: the HD sound pack's LFE stems as a shaker source (Renderers/LfeStems.cs). Files only.
    ///   stems status                       manifest, stems on disk, categories, stock rates, the effective lfe.sources
    ///   stems render --name whcan [--dist 25 | --player] [--vol 100] [--hz 11025] [--mode 0|1|2] [--at 0.5] [--stop 1.5]
    ///                [--seconds 2.5] [--out DIR] [--tag NAME] [--sinks lfe-wav,stems] [--rig FILE] [--effects DIR]
    ///       one scripted SOUND_START (real v3 datagrams through Derive) -> &lt;tag&gt;.lfe.wav (the shaker as the rig mixes it)
    ///       and &lt;tag&gt;.stems.wav (the stems signal alone). I76_LFE_SOURCES=synth=0,stems=1 picks the sources for one run.
    /// </summary>
    static class StemsCommand
    {
        public const string HelpText =
@"  stems status                                    LFE stem manifest, stems on disk, lfe.sources (synth / stems gains)
  stems render --name NAME [--dist M | --player] [--vol %] [--hz HZ] [--mode 0|1|2] [--at S] [--stop S] [--seconds S]
               [--out DIR] [--tag NAME] [--sinks lfe-wav,stems]   one SOUND_START through the host -> <tag>.lfe.wav + .stems.wav
";

        sealed class A
        {
            readonly string[] _a;
            public A(string[] a) { _a = a; }
            public bool Has(string k) => _a.Contains(k);
            public string Get(string k, string d = null) { int i = Array.IndexOf(_a, k); return i >= 0 && i + 1 < _a.Length && !_a[i + 1].StartsWith("--") ? _a[i + 1] : d; }
            public double Num(string k, double d) => double.TryParse(Get(k), NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : d;
        }

        public static int Run(string[] argv)
        {
            string sub = argv.Length > 0 ? argv[0] : "status";
            var a = new A(argv.Skip(1).ToArray());
            var set = EffectSet.Load(a.Get("--effects"), a.Get("--rig"));
            switch (sub)
            {
                case "status": return Status(set);
                case "render": return Render(set, a);
                default: Console.Error.WriteLine("stems: unknown subcommand " + sub); Console.Write(HelpText); return 2;
            }
        }

        static int Status(EffectSet set)
        {
            var cfg = StemsConfig.From(set.Rig.Output("stems"));
            var path = LfeStemsRenderer.ResolveManifest(cfg.Manifest);
            var src = LfeSources.Read(set.Rig);
            Console.WriteLine("rig {0}: stems output {1}, enabled {2}; lfe.sources synth {3} stems {4} ({5})", set.Rig.Name,
                set.Rig.Output("stems") != null ? "present" : "ABSENT", set.Rig.OutputEnabled("stems"), src.synth, src.stems, src.from);
            Console.WriteLine("manifest: " + path);
            if (path == null || !File.Exists(path)) { Console.WriteLine("  not found: the shaker runs Lfe.Synth only. Build the pack: tools\\soundhd\\soundhd.py build"); return 0; }
            var m = StemManifest.Load(path, cfg.DefaultNominalHz);
            Console.WriteLine("  {0}: {1} stems on disk, {2} listed but missing, {3} aliases", m.Version, m.Stems.Count, m.Missing.Count, m.Alias.Count);
            foreach (var g in m.Stems.Values.GroupBy(s => s.Category).OrderBy(g => g.Key))
                Console.WriteLine("  {0,-18} {1,3}  loops {2,2}  rates {3}  stock Hz {4}", g.Key, g.Count(), g.Count(s => s.Loop),
                    string.Join("/", g.Select(s => s.Rate).Distinct()), string.Join("/", g.Select(s => s.NominalHz).Distinct()));
            Console.WriteLine("  rate scaling (event Hz / stock Hz) for: " + string.Join(", ", cfg.RateScale) + "; distance " + cfg.Curve +
                string.Format(CultureInfo.InvariantCulture, " ref {0} m max {1} m; budget {2} voices (player > near <= {3} m > far)", cfg.RefM, cfg.MaxM, cfg.MaxVoices, cfg.NearM));
            return 0;
        }

        static int Render(EffectSet set, A a)
        {
            var name = a.Get("--name") ?? throw new ArgumentException("stems render needs --name <sound>");
            var cue = new SoundCue
            {
                Name = name, At = a.Num("--at", 0.5), StopAt = a.Num("--stop", -1), Hz = a.Num("--hz", 11025), Vol = a.Num("--vol", 100),
                Mode = (int)a.Num("--mode", 0), Player = a.Has("--player"), Dist = a.Num("--dist", a.Has("--player") ? 0 : -1),
            };
            double secs = a.Num("--seconds", 2.5);
            var outDir = a.Get("--out") ?? Path.Combine(EffectSet.DefaultRoot(), "out", "stems");
            Directory.CreateDirectory(outDir);
            string tag = a.Get("--tag") ?? "stem_" + name;
            var sinks = (a.Get("--sinks") ?? "lfe-wav,stems").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var p = Session.Build(set, sinks, outDir, tag, false, 250, 50);
            var d = new Haptics.Core.Derive(); p.Core.Configure(d);
            p.Run(Sources.FromDatagrams(SyntheticSound.Session(new[] { cue }, secs), d, new TelCodec(null)));
            foreach (var r in p.Renderers) r.Close();
            Console.WriteLine("stems render {0}: {1} updates", name, p.Updates);
            foreach (var r in p.Renderers) Console.WriteLine("  " + r.Summary());
            return 0;
        }
    }
}
