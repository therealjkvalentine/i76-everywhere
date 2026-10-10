using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json.Nodes;
using Haptics.Core;
using Haptics.Effects;

namespace Haptics.Renderers
{
    /// <summary>What a renderer is given when it is opened.</summary>
    public sealed class RendererContext
    {
        public string OutputName;          // the key in rigs/*.json "outputs" ("wheel", "pad", "lfe", "motion", ...)
        public JsonObject Config;          // that output's JSON object
        public RigDef Rig;
        public Tune Tune;
        public EffectSet Effects;
        public bool Live;                  // false = file sink (dry run); true = open the real device. Only --live sets it.
        public string OutDir;              // where file sinks write
        public string Tag = "session";     // file name stem
        public int CoreHz = 250;           // core updates per second (sub-frame updates in replay)
        public TextWriter Log = Console.Out;
        public double Num(string k, double d) => EffectDef.Num(Config, k, d);
        public string Str(string k) => EffectDef.Str(Config, k);
    }

    /// <summary>
    /// THE OUTPUT PLUG-IN POINT. A renderer turns CoreSteps into one device's signal. It must work in two modes:
    /// file sink (default: writes what it would send, so it can be verified against files with no device and no
    /// game) and live (only when ctx.Live, i.e. the user passed --live). Register new types with
    /// <see cref="RendererRegistry.Register"/>; a rig selects them by "renderer" name per output.
    /// The motion workstream (docs/MOTION-OUTPUT.md) plugs in here: implement IRenderer, read
    /// CoreStep.State (the VehicleState motion interface) and CoreStep.Events, register "Motion.&lt;name&gt;".
    /// </summary>
    public interface IRenderer : IDisposable
    {
        string Type { get; }
        void Open(RendererContext ctx);
        void Render(CoreStep step);
        /// <summary>Flush and close files / release devices. Must leave a device at rest (zero force, motors off).</summary>
        void Close();
        /// <summary>One line for the run summary (what was written, peak values, errors).</summary>
        string Summary();
    }

    public static class RendererRegistry
    {
        static readonly Dictionary<string, Func<IRenderer>> _f = new Dictionary<string, Func<IRenderer>>(StringComparer.OrdinalIgnoreCase)
        {
            ["Wheel.DirectInput"] = () => new WheelDirectInput(),
            ["Pad.XInput"] = () => new PadXInput(),
            ["Lfe.Synth"] = () => new LfeSynthRenderer(),
            ["Lfe.Loopback"] = () => new LfeLoopbackRenderer(),
            ["Motion.FileSink"] = () => new MotionFileSink(),
            // Kept as a name so older rig files resolve; the OutSim/OutGauge packet work moved to docs/MOTION-OUTPUT.md.
            ["Udp.OutSim"] = () => new MotionFileSink(),
        };
        public static void Register(string type, Func<IRenderer> factory) => _f[type] = factory;
        public static IEnumerable<string> Types => _f.Keys;
        public static IRenderer Create(string type)
        {
            if (type != null && _f.TryGetValue(type, out var f)) return f();
            throw new KeyNotFoundException("no renderer type '" + type + "' (known: " + string.Join(", ", _f.Keys) + ")");
        }
    }

    /// <summary>16-bit PCM WAV writer (mono or stereo).</summary>
    public static class Wav
    {
        public static void Write(string path, short[] pcm, int rate, int channels = 1)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)));
            using (var bw = new BinaryWriter(File.Create(path)))
            {
                int bytes = pcm.Length * 2;
                bw.Write(new[] { 'R', 'I', 'F', 'F' }); bw.Write(36 + bytes); bw.Write(new[] { 'W', 'A', 'V', 'E' });
                bw.Write(new[] { 'f', 'm', 't', ' ' }); bw.Write(16); bw.Write((short)1); bw.Write((short)channels);
                bw.Write(rate); bw.Write(rate * 2 * channels); bw.Write((short)(2 * channels)); bw.Write((short)16);
                bw.Write(new[] { 'd', 'a', 't', 'a' }); bw.Write(bytes);
                foreach (var s in pcm) bw.Write(s);
            }
        }

        /// <summary>Reads 8/16-bit PCM (any channel count, mixed to mono) as doubles in -1..1.</summary>
        public static (int rate, double[] samples) Read(string path)
        {
            var b = File.ReadAllBytes(path);
            int p = 12, rate = 0, ch = 1, bits = 16; int dataOff = -1, dataLen = 0;
            while (p + 8 <= b.Length)
            {
                string id = System.Text.Encoding.ASCII.GetString(b, p, 4); int len = BitConverter.ToInt32(b, p + 4);
                if (id == "fmt ") { ch = BitConverter.ToInt16(b, p + 10); rate = BitConverter.ToInt32(b, p + 12); bits = BitConverter.ToInt16(b, p + 22); }
                else if (id == "data") { dataOff = p + 8; dataLen = Math.Min(len, b.Length - dataOff); break; }
                p += 8 + len + (len & 1);
            }
            if (dataOff < 0) throw new InvalidDataException("no data chunk in " + path);
            int bps = bits / 8, n = dataLen / (bps * ch);
            var o = new double[n];
            for (int i = 0; i < n; i++)
            {
                double acc = 0;
                for (int c = 0; c < ch; c++)
                {
                    int q = dataOff + (i * ch + c) * bps;
                    acc += bits == 8 ? (b[q] - 128) / 128.0 : BitConverter.ToInt16(b, q) / 32768.0;
                }
                o[i] = acc / ch;
            }
            return (rate, o);
        }
    }
}
