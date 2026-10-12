using System;
using System.Buffers;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using System.Threading;
using Haptics.Core;
using Haptics.Core.Motion;
using Haptics.Renderers;

namespace Haptics
{
    /// <summary>
    /// Single-writer ring of the most recent output samples (Lfe.Synth's final 16-bit PCM). The writer is the thread that
    /// renders samples (the tick thread in file mode, the waveOut thread live); a reader copies the newest N. A torn read
    /// costs one slightly wrong spectrum, never a stall: nothing here locks.
    /// </summary>
    public sealed class SampleTap
    {
        readonly short[] _ring;
        readonly int _mask;
        long _count;                         // samples ever written (Volatile)
        public int Rate;

        public SampleTap(int size = 8192, int rate = 16000)
        {
            int n = 1; while (n < size) n <<= 1;
            _ring = new short[n]; _mask = n - 1; Rate = rate;
        }

        public long Count => Volatile.Read(ref _count);

        public void Add(short s)
        {
            long c = _count;
            _ring[c & _mask] = s;
            Volatile.Write(ref _count, c + 1);
        }

        /// <summary>The newest n samples (fewer when fewer were written), oldest first, as -1..1.</summary>
        public double[] Last(int n)
        {
            long c = Count;
            n = (int)Math.Min(Math.Min(n, _ring.Length), c);
            var o = new double[n];
            for (int i = 0; i < n; i++) o[i] = _ring[(c - n + i) & _mask] / 32768.0;
            return o;
        }

        /// <summary>The samples written after <paramref name="since"/> (capped at the ring), as -1..1.</summary>
        public double[] Since(long since, out long now)
        {
            now = Count;
            long n = Math.Min(Math.Max(0, now - since), _ring.Length);
            var o = new double[n];
            for (long i = 0; i < n; i++) o[i] = _ring[(now - n + i) & _mask] / 32768.0;
            return o;
        }

        /// <summary>Hann-windowed Goertzel magnitude (0..~1 for a full-scale sine) at each frequency.</summary>
        public static double[] Spectrum(double[] x, int rate, double[] freqs)
        {
            var o = new double[freqs.Length];
            int n = x.Length;
            if (n < 16) return o;
            var w = new double[n];
            double wsum = 0;
            for (int i = 0; i < n; i++) { w[i] = 0.5 - 0.5 * Math.Cos(2 * Math.PI * i / (n - 1)); wsum += w[i]; }
            for (int b = 0; b < freqs.Length; b++)
            {
                double k = 2 * Math.Cos(2 * Math.PI * freqs[b] / rate), s1 = 0, s2 = 0;
                for (int i = 0; i < n; i++) { double s0 = x[i] * w[i] + k * s1 - s2; s2 = s1; s1 = s0; }
                double p = s1 * s1 + s2 * s2 - k * s1 * s2;
                o[b] = 2 * Math.Sqrt(Math.Max(0, p)) / wsum;
            }
            return o;
        }
    }

    /// <summary>
    /// The haptics host's debug publisher (--debug-udp [port | host:port], default 127.0.0.1:17680): one compact JSON
    /// datagram per published update, at most MaxHz per second of core time, for tools/debug (the I76 Debug dashboard).
    /// It carries what the dashboard cannot compute from telemetry alone: the bus, every effect contribution (the reference
    /// model's wheel channels and the chain voices), the wheel / pad / shaker / motion outputs, the shaker spectrum, the
    /// HD-pack stem voices. Loopback only. When the flag is absent nothing is created and the hot path costs one null test
    /// per update (Pipeline.Debug, LfeSynthRenderer.Tap). Schema: tools/debug/README.md "Haptics debug datagram".
    /// </summary>
    public sealed class DebugPublisher : IDisposable
    {
        public const int DefaultPort = 17680;
        public const int Schema = 1;
        public static readonly double[] SpectrumHz = Enumerable.Range(0, 23).Select(i => 10.0 + 5.0 * i).ToArray();   // 10..120 Hz

        readonly UdpClient _udp;
        readonly IPEndPoint _ep;
        readonly double _minDt;
        readonly ArrayBufferWriter<byte> _buf = new ArrayBufferWriter<byte>(8192);
        readonly Stopwatch _wall = Stopwatch.StartNew();
        double _lastT = double.NegativeInfinity;
        public string Source = "host";
        public long Published, Bytes, Errors, Steps;
        public int MaxEventsPerDatagram = 24;
        /// <summary>Tests: every datagram sent is also handed here.</summary>
        public Action<byte[]> OnDatagram;

        // what happened between two publishes
        readonly Dictionary<string, int> _evCount = new Dictionary<string, int>(StringComparer.Ordinal);
        readonly List<(double t, HapticEvent e)> _evRecent = new List<(double, HapticEvent)>();
        readonly Dictionary<string, long> _evTotal = new Dictionary<string, long>(StringComparer.Ordinal);
        double _peakDev, _peakL, _peakR;

        // renderers found in the pipeline
        Pipeline _p;
        WheelDirectInput _wheel; PadXInput _pad; LfeSynthRenderer _synth; LfeStemsRenderer _stems; MotionUdpRenderer _motion;
        public SampleTap Tap;
        long _tapMark; int _specEvery = 3, _pubSinceSpec = 99; double[] _spec = new double[SpectrumHz.Length];

        readonly object _mlk = new object();
        MotionFrame _lastMotion; long _motionFrames;
        readonly Dictionary<string, (long packets, double wall)> _tgtPrev = new Dictionary<string, (long, double)>();
        readonly Dictionary<string, double> _tgtRate = new Dictionary<string, double>();

        public DebugPublisher(string host = "127.0.0.1", int port = DefaultPort, double maxHz = 60)
        {
            var ip = IPAddress.Parse(host == "localhost" ? "127.0.0.1" : host);
            if (!IPAddress.IsLoopback(ip)) throw new ArgumentException("--debug-udp sends to loopback only (got " + host + ")");
            if (port <= 0 || port > 65535) throw new ArgumentException("--debug-udp port out of range: " + port);
            _ep = new IPEndPoint(ip, port);
            _udp = new UdpClient(AddressFamily.InterNetwork);
            _minDt = 1.0 / Math.Max(1.0, Math.Min(60.0, maxHz));
        }

        /// <summary>"17680", "127.0.0.1:17680", or null/"" for the default.</summary>
        public static DebugPublisher FromSpec(string spec, double maxHz = 60)
        {
            string host = "127.0.0.1"; int port = DefaultPort;
            if (!string.IsNullOrWhiteSpace(spec))
            {
                int c = spec.LastIndexOf(':');
                if (c > 0) { host = spec.Substring(0, c); port = int.Parse(spec.Substring(c + 1), CultureInfo.InvariantCulture); }
                else port = int.Parse(spec, CultureInfo.InvariantCulture);
            }
            return new DebugPublisher(host, port, maxHz);
        }

        public string Endpoint => _ep.ToString();

        /// <summary>Find the renderers, install the shaker tap and the motion frame hook. Call after the renderers are open.</summary>
        public void Attach(Pipeline p)
        {
            _p = p;
            p.Debug = this;
            foreach (var r in p.Renderers)
            {
                if (r is WheelDirectInput w) _wheel = w;
                else if (r is PadXInput pd) _pad = pd;
                else if (r is LfeSynthRenderer s) _synth = s;
                else if (r is LfeStemsRenderer st) _stems = st;
                else if (r is MotionUdpRenderer m) _motion = m;
            }
            if (_synth != null) { Tap = new SampleTap(8192, _synth.Rate); _synth.Tap = Tap; }
            if (_motion != null) _motion.OnFrame += OnMotionFrame;
        }

        void OnMotionFrame(MotionFrame f) { lock (_mlk) { _lastMotion = f; _motionFrames++; } }

        /// <summary>Called once per core update (Pipeline.Emit / the live loop), after the renderers.</summary>
        public void Observe(CoreStep s)
        {
            Steps++;
            if (s.Events != null)
                foreach (var e in s.Events)
                {
                    var k = e.Type ?? "?";
                    _evCount[k] = _evCount.TryGetValue(k, out var n) ? n + 1 : 1;
                    _evTotal[k] = _evTotal.TryGetValue(k, out var m) ? m + 1 : 1;
                    _evRecent.Add((s.T, e));
                    if (_evRecent.Count > MaxEventsPerDatagram) _evRecent.RemoveAt(0);
                }
            int dev = DeviceForce(s);
            _peakDev = Math.Max(_peakDev, Math.Abs(dev));
            if (_pad != null) { _peakL = Math.Max(_peakL, _pad.Last.L); _peakR = Math.Max(_peakR, _pad.Last.R); }
            if (s.T >= _lastT && s.T - _lastT < _minDt - 1e-9) return;
            _lastT = s.T;
            Publish(s, dev);
        }

        int DeviceForce(CoreStep s)
        {
            if (_wheel != null) return _wheel.LastDevice;
            var t = _p?.Core?.Mixer?.Tune;
            return t == null ? s.Mix.Force : WheelDirectInput.DeviceForce(s, t["MinForce"], t["MinForceGate"], t["Clamp"]);
        }

        void Publish(CoreStep s, int dev)
        {
            _buf.Clear();
            using (var w = new Utf8JsonWriter(_buf))
            {
                w.WriteStartObject();
                w.WriteNumber("schema", Schema);
                w.WriteString("kind", "i76haptics");
                w.WriteString("src", Source);
                w.WriteNumber("seq", Published + 1);
                N(w, "t", s.T);
                N(w, "wall", _wall.Elapsed.TotalSeconds);
                w.WriteNumber("steps", Steps);

                var st = s.State;
                w.WriteStartObject("state");
                w.WriteBoolean("present", st?.Present ?? false);
                N(w, "speed", st?.Speed ?? 0); N(w, "rpm", st?.Rpm ?? 0); w.WriteNumber("gear", st?.Gear ?? 0);
                w.WriteBoolean("airborne", st?.Airborne ?? false);
                w.WriteEndObject();

                // wheel: the reference model's force and its channel breakdown, the chain voices' share, the device value
                var mix = s.Mix;
                double voice = s.Bus.VoiceWheel * 10000.0 * mix.Ramp;
                w.WriteStartObject("wheel");
                w.WriteNumber("model", mix.Force); N(w, "voice", voice); N(w, "total", mix.Force + voice);
                w.WriteNumber("device", dev); N(w, "peak", _peakDev);
                w.WriteNumber("steady", mix.Steady); w.WriteNumber("osc", mix.Osc); N(w, "ramp", mix.Ramp); N(w, "duck", mix.Duck); N(w, "rough", mix.Rough);
                w.WriteStartObject("channels");
                if (mix.Channels != null) foreach (var k in mix.Channels.Keys) N(w, k, mix.Channels[k]);
                w.WriteEndObject();
                w.WriteStartArray("notes");
                if (mix.Notes != null) foreach (var n in mix.Notes) w.WriteStringValue(n);
                w.WriteEndArray();
                w.WriteEndObject();

                var b = s.Bus;
                w.WriteStartObject("bus");
                N(w, "steady", b.Steady); N(w, "osc", b.OscValue); N(w, "transient", b.Transient);
                N(w, "impact", b.TransientImpact); N(w, "weapon", b.TransientWeapon); N(w, "shift", b.TransientShift);
                w.WriteStartArray("tactile");
                foreach (var o in b.Tactile) { w.WriteStartObject(); w.WriteString("name", o.Name ?? ""); N(w, "hz", o.Freq); N(w, "amp", o.Amp); w.WriteEndObject(); }
                w.WriteEndArray();
                var L = b.Lfe;
                w.WriteStartObject("lfe");
                N(w, "engine_hz", L.EngineFreq); N(w, "engine", L.EngineAmp); N(w, "road_hz", L.RoadFreq); N(w, "road", L.RoadAmp);
                N(w, "impulse", L.ImpulseAmp); N(w, "impulse_hz", L.ImpulseFreq); N(w, "heave", L.HeaveAmp); N(w, "carrier_hz", L.CarrierFreq);
                N(w, "weapon", L.WeaponAmp); N(w, "weapon_hz", L.WeaponFreq); N(w, "scrub", L.ScrubAmp); N(w, "explode", L.ExplodeAmp);
                w.WriteEndObject();
                var M = b.Motion;
                w.WriteStartObject("motion");
                N(w, "surge", M.SurgeA); N(w, "sway", M.SwayA); N(w, "heave", M.HeaveA); N(w, "yaw_rate", M.YawRate); N(w, "pitch", M.Pitch);
                w.WriteEndObject();
                w.WriteEndObject();

                w.WriteStartArray("voices");
                foreach (var v in b.Voices)
                {
                    w.WriteStartObject();
                    w.WriteString("id", v.Id ?? ""); w.WriteString("group", v.Group ?? ""); w.WriteString("kind", v.Kind ?? "");
                    w.WriteNumber("prio", v.Priority); N(w, "level", v.Level); N(w, "wheel", v.Wheel); N(w, "lfe", v.LfeAmp); N(w, "lfe_hz", v.LfeHz);
                    N(w, "pad_l", v.PadL); N(w, "pad_r", v.PadR); w.WriteBoolean("transient", v.Transient); N(w, "age_ms", v.AgeMs);
                    w.WriteEndObject();
                }
                w.WriteEndArray();
                w.WriteStartObject("duck");
                if (s.Duck != null) foreach (var kv in s.Duck) N(w, kv.Key, kv.Value);
                w.WriteEndObject();

                // pad
                w.WriteStartObject("pad");
                w.WriteBoolean("open", _pad != null);
                if (_pad != null) { N(w, "l", _pad.Last.L); N(w, "r", _pad.Last.R); N(w, "peak_l", _peakL); N(w, "peak_r", _peakR); }
                else
                {
                    var leg = ReferenceMixer.RenderPadLegacy(b);         // what a pad would get (reference down-mix) when no pad sink is open
                    N(w, "l", leg.Left); N(w, "r", leg.Right);
                }
                w.WriteEndObject();

                // shaker output
                w.WriteStartObject("lfe");
                w.WriteBoolean("open", _synth != null);
                if (Tap != null)
                {
                    var x = Tap.Since(_tapMark, out var now); _tapMark = now;
                    double rms = 0, pk = 0; foreach (var v in x) { rms += v * v; pk = Math.Max(pk, Math.Abs(v)); }
                    N(w, "rms", x.Length > 0 ? Math.Sqrt(rms / x.Length) : 0); N(w, "peak", pk); w.WriteNumber("samples", now);
                    w.WriteNumber("rate", Tap.Rate);
                    if (++_pubSinceSpec >= _specEvery) { _pubSinceSpec = 0; _spec = SampleTap.Spectrum(Tap.Last(4096), Tap.Rate, SpectrumHz); }
                    w.WriteStartArray("spectrum_hz"); foreach (var f in SpectrumHz) w.WriteNumberValue(f); w.WriteEndArray();
                    w.WriteStartArray("spectrum"); foreach (var a in _spec) w.WriteNumberValue(R(a)); w.WriteEndArray();
                }
                if (_synth != null) { N(w, "synth_gain", _synth.SynthGain); }
                w.WriteStartObject("stems");
                var bank = _stems?.Bank;
                w.WriteBoolean("on", bank != null);
                if (bank != null)
                {
                    N(w, "mix_gain", bank.MixGain); w.WriteNumber("started", bank.Started); w.WriteNumber("missed", bank.Missed);
                    w.WriteNumber("dropped", bank.Dropped); w.WriteNumber("stolen", bank.Stolen); w.WriteNumber("stopped", bank.Stopped);
                    w.WriteStartArray("voices");
                    foreach (var (name, cls, gain) in bank.ActiveVoices) { w.WriteStartObject(); w.WriteString("name", name ?? ""); w.WriteNumber("cls", cls); N(w, "gain", gain); w.WriteEndObject(); }
                    w.WriteEndArray();
                }
                else w.WriteString("why", _stems?.Fallback ?? (_synth == null ? "no lfe sink" : "no stems output / manifest"));
                w.WriteEndObject();
                w.WriteEndObject();

                // motion
                w.WriteStartObject("motion_out");
                w.WriteBoolean("open", _motion != null);
                if (_motion != null)
                {
                    MotionFrame f; long mf;
                    lock (_mlk) { f = _lastMotion; mf = _motionFrames; }
                    w.WriteNumber("frames", mf);
                    w.WriteBoolean("sending", _motion.Send);
                    if (f != null)
                    {
                        w.WriteNumber("seq", f.Seq); w.WriteNumber("status", f.Status); N(w, "gain", f.Gain); N(w, "clock", f.Clock);
                        w.WriteBoolean("race_on", f.RaceOn);
                        var S = f.S;
                        N(w, "surge", S.Surge); N(w, "sway", S.Sway); N(w, "heave", S.Heave);
                        N(w, "cue_surge", f.CueSurge); N(w, "cue_sway", f.CueSway); N(w, "cue_heave", f.CueHeave);
                        N(w, "roll", S.Roll); N(w, "pitch", S.Pitch); N(w, "heading", S.Heading);
                        N(w, "roll_rate", S.RollRate); N(w, "pitch_rate", S.PitchRate); N(w, "yaw_rate", S.YawRate);
                    }
                    var core = _motion.Core;
                    if (core != null)
                    {
                        w.WriteNumber("ticks", core.Ticks); w.WriteNumber("neutral_ticks", core.NeutralTicks);
                        w.WriteStartObject("cues");
                        lock (_mlk) foreach (var kv in core.Cues.ByKind.ToArray()) w.WriteNumber(kv.Key, kv.Value);
                        w.WriteEndObject();
                    }
                    double wall = _wall.Elapsed.TotalSeconds;
                    w.WriteStartArray("targets");
                    foreach (var tr in _motion.Targets)
                    {
                        string name = tr.Def?.Name ?? "?";
                        long pk = Interlocked.Read(ref tr.Packets);
                        if (_tgtPrev.TryGetValue(name, out var prev) && wall - prev.wall >= 0.5)
                        { _tgtRate[name] = (pk - prev.packets) / (wall - prev.wall); _tgtPrev[name] = (pk, wall); }
                        else if (!_tgtPrev.ContainsKey(name)) _tgtPrev[name] = (pk, wall);
                        w.WriteStartObject();
                        w.WriteString("name", name); w.WriteNumber("packets", pk); w.WriteNumber("bytes", tr.Bytes); w.WriteNumber("errors", tr.SendErrors);
                        N(w, "rate", _tgtRate.TryGetValue(name, out var rr) ? rr : 0);
                        w.WriteString("streams", string.Join(",", tr.Streams.Select(x => x.kind + ":" + x.port)));
                        if (tr.LastError != null) w.WriteString("error", tr.LastError);
                        w.WriteEndObject();
                    }
                    w.WriteEndArray();
                }
                w.WriteEndObject();

                // events since the last datagram
                w.WriteStartObject("ev_count");
                foreach (var kv in _evCount) w.WriteNumber(kv.Key, kv.Value);
                w.WriteEndObject();
                w.WriteStartObject("ev_total");
                foreach (var kv in _evTotal) w.WriteNumber(kv.Key, kv.Value);
                w.WriteEndObject();
                w.WriteStartArray("events");
                foreach (var (t, e) in _evRecent)
                {
                    w.WriteStartObject();
                    N(w, "t", t); w.WriteString("type", e.Type ?? "?");
                    if (e.Name != null) w.WriteString("name", e.Name);
                    int k = 0;
                    w.WriteStartObject("f");
                    foreach (var kv in e.F) { if (++k > 12) break; N(w, kv.Key, kv.Value); }
                    w.WriteEndObject();
                    w.WriteEndObject();
                }
                w.WriteEndArray();
                w.WriteEndObject();
            }
            _evCount.Clear(); _evRecent.Clear(); _peakDev = 0; _peakL = _peakR = 0;
            var data = _buf.WrittenSpan.ToArray();
            try { _udp.Send(data, data.Length, _ep); Published++; Bytes += data.Length; }
            catch (SocketException) { Errors++; }       // nobody listening on loopback is not an error the host cares about
            OnDatagram?.Invoke(data);
        }

        static double R(double v) => double.IsFinite(v) ? Math.Round(v, 5) : 0.0;
        static void N(Utf8JsonWriter w, string k, double v) => w.WriteNumber(k, R(v));

        public string Summary() => string.Format(CultureInfo.InvariantCulture, "debug-udp -> {0}: {1} datagrams, {2} KB, {3} send errors, {4} core updates seen",
            _ep, Published, Bytes / 1024, Errors, Steps);

        public void Dispose()
        {
            if (_synth != null && _synth.Tap == Tap) _synth.Tap = null;
            if (_motion != null) _motion.OnFrame -= OnMotionFrame;
            _udp.Dispose();
        }
    }
}
