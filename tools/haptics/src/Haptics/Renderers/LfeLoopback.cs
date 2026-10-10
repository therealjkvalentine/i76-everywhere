using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using Haptics.Core;

namespace Haptics.Renderers
{
    /// <summary>
    /// The game-audio ambience bed for the shakers (HAPTICS-ARCHITECTURE section 5, option 2): mono-mix, resample to the
    /// synth rate, 2-pole HP + 4-pole LP (the mix carries music and speech up to 11 kHz, so it needs a steeper slope than the synth), gain (default 0.25), gate (silent with no player = menus / cut-scenes, and while
    /// a CD track plays when the v3 frame says so), duck under transients. Summed into Lfe.Synth BEFORE its filters and
    /// limiter, so bed and synth share one HP/LP/limiter chain. Feed: WASAPI loopback (live) or a WAV file (offline).
    /// </summary>
    public sealed class LoopbackBed : ILfeBed
    {
        readonly int _outRate; readonly double _gain;
        readonly object _lk = new object();
        readonly Queue<float> _q = new Queue<float>();
        int _srcRate = 48000; double _pos; float _a, _b; bool _have;
        double _hp1, _hp1in, _hp2, _hp2in, _lp1, _lp2, _lp3, _lp4; readonly double _aHp, _kLp;
        double _duck = 1, _gate = 1, _gateS = 1;
        public long Pushed, Pulled, Starved;
        public int MaxQueue;

        public LoopbackBed(int outRate, double gain, double hpHz, double lpHz)
        {
            _outRate = outRate; _gain = gain;
            double rc = 1.0 / (2 * Math.PI * hpHz); _aHp = rc / (rc + 1.0 / outRate);
            _kLp = 1.0 - Math.Exp(-2.0 * Math.PI * lpHz / outRate);
            MaxQueue = outRate;   // ~1 s at most; a bed that lags is worse than one that drops
        }
        public void SetSourceRate(int r) { lock (_lk) _srcRate = r; }
        public void SetDuck(double f) => _duck = f;
        public void SetGate(bool open) => _gate = open ? 1 : 0;

        public void Push(float[] mono, int n)
        {
            lock (_lk)
            {
                for (int i = 0; i < n; i++) _q.Enqueue(mono[i]);
                while (_q.Count > MaxQueue * 4) _q.Dequeue();
                Pushed += n;
            }
        }

        public double Next()
        {
            double x;
            lock (_lk)
            {
                double step = (double)_srcRate / _outRate;
                if (!_have) { if (_q.Count < 2) { Starved++; x = 0; goto filt; } _a = _q.Dequeue(); _b = _q.Dequeue(); _have = true; _pos = 0; }
                while (_pos >= 1.0) { if (_q.Count == 0) { Starved++; _have = false; x = 0; goto filt; } _a = _b; _b = _q.Dequeue(); _pos -= 1.0; }
                x = _a + (_b - _a) * _pos;
                _pos += step;
            }
        filt:
            Pulled++;
            double h1 = _aHp * (_hp1 + x - _hp1in); _hp1in = x; _hp1 = h1;
            double h2 = _aHp * (_hp2 + h1 - _hp2in); _hp2in = h1; _hp2 = h2;
            _lp1 += _kLp * (h2 - _lp1); _lp2 += _kLp * (_lp1 - _lp2); _lp3 += _kLp * (_lp2 - _lp3); _lp4 += _kLp * (_lp3 - _lp4);
            _gateS += 0.002 * (_gate - _gateS);            // ~30 ms at 16 kHz: no click when the gate moves
            return _lp4 * _gain * _duck * _gateS;
        }
    }

    public sealed class LfeLoopbackRenderer : IRenderer
    {
        public string Type => "Lfe.Loopback";
        public LoopbackBed Bed;
        RendererContext _ctx;
        WasapiLoopback _cap;
        string _mode = "off";
        public void Open(RendererContext ctx)
        {
            _ctx = ctx;
            int rate = (int)ctx.Rig.Num("lfe", "rate", 16000);
            Bed = new LoopbackBed(rate, ctx.Num("gain", 0.25), ctx.Num("hp_hz", 22), ctx.Num("lp_hz", 90));
            var wav = ctx.Str("input_wav");
            if (ctx.Live)
            {
                _cap = new WasapiLoopback();
                var err = _cap.Start(Bed);
                _mode = err == null ? "WASAPI loopback " + _cap.FormatText : "loopback failed: " + err;
                if (err != null) ctx.Log.WriteLine("Lfe.Loopback: " + err);
            }
            else if (!string.IsNullOrEmpty(wav))
            {
                var (r, s) = Wav.Read(wav);
                Bed.SetSourceRate(r); Bed.MaxQueue = int.MaxValue / 8;
                var f = new float[s.Length]; for (int i = 0; i < s.Length; i++) f[i] = (float)s[i];
                Bed.Push(f, f.Length);
                _mode = "offline from " + wav;
            }
        }
        public void Render(CoreStep step)
        {
            bool open = step.State.Present;
            string gate = _ctx.Str("gate") ?? "player_present";
            if (gate == "none") open = true;
            if (step.Vars != null && step.Vars.TryGetValue("music_track", out var mt) && mt > 0 && _ctx.Num("music_duck", 1) > 0) open = false;
            Bed.SetGate(open);
        }
        public void Close() { _cap?.Stop(); }
        public string Summary() => "Lfe.Loopback: " + _mode + string.Format(" (pushed {0}, pulled {1}, starved {2})", Bed?.Pushed, Bed?.Pulled, Bed?.Starved);
        public void Dispose() => Close();
    }

    /// <summary>
    /// WASAPI shared-mode loopback capture of the default render endpoint (raw COM, no NuGet). Capturing plays nothing.
    /// Started only from Lfe.Loopback live mode (--live) or `haptics loopback-probe` (format + level only, no samples kept).
    /// </summary>
    public sealed class WasapiLoopback
    {
        [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorCo { }
        [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IMMDeviceEnumerator
        {
            int EnumAudioEndpoints(int dataFlow, int stateMask, out IntPtr devices);
            int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice device);
        }
        [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IMMDevice
        {
            int Activate(ref Guid iid, int clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object iface);
            int OpenPropertyStore(int access, out IntPtr props);
            int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
            int GetState(out int state);
        }
        [ComImport, Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IAudioClient
        {
            int Initialize(int shareMode, int streamFlags, long bufferDuration, long periodicity, IntPtr format, IntPtr sessionGuid);
            int GetBufferSize(out uint frames);
            int GetStreamLatency(out long latency);
            int GetCurrentPadding(out uint padding);
            int IsFormatSupported(int shareMode, IntPtr format, out IntPtr closest);
            int GetMixFormat(out IntPtr format);
            int GetDevicePeriod(out long dflt, out long min);
            int Start();
            int Stop();
            int Reset();
            int SetEventHandle(IntPtr h);
            int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object iface);
        }
        [ComImport, Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IAudioCaptureClient
        {
            int GetBuffer(out IntPtr data, out uint frames, out uint flags, out ulong devPos, out ulong qpcPos);
            int ReleaseBuffer(uint frames);
            int GetNextPacketSize(out uint frames);
        }

        const int eRender = 0, eConsole = 0, CLSCTX_ALL = 23, AUDCLNT_SHAREMODE_SHARED = 0, AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000;
        const uint AUDCLNT_BUFFERFLAGS_SILENT = 0x2;

        IAudioClient _client; IAudioCaptureClient _capture; Thread _th; volatile bool _run;
        public int Rate, Channels, Bits; public bool Float;
        public long Packets, Frames, SilentPackets; public double Peak;
        public string FormatText => string.Format("{0} Hz x{1} {2}{3}", Rate, Channels, Bits, Float ? "f" : "i");
        LoopbackBed _bed;

        public string Start(LoopbackBed bed)
        {
            try
            {
                _bed = bed;
                var en = (IMMDeviceEnumerator)new MMDeviceEnumeratorCo();
                int hr = en.GetDefaultAudioEndpoint(eRender, eConsole, out var dev);
                if (hr != 0) return "GetDefaultAudioEndpoint 0x" + hr.ToString("X8");
                var iid = typeof(IAudioClient).GUID;
                hr = dev.Activate(ref iid, CLSCTX_ALL, IntPtr.Zero, out var o);
                if (hr != 0) return "Activate(IAudioClient) 0x" + hr.ToString("X8");
                _client = (IAudioClient)o;
                hr = _client.GetMixFormat(out var fmt);
                if (hr != 0) return "GetMixFormat 0x" + hr.ToString("X8");
                ushort tag = (ushort)Marshal.ReadInt16(fmt, 0);
                Channels = Marshal.ReadInt16(fmt, 2); Rate = Marshal.ReadInt32(fmt, 4); Bits = Marshal.ReadInt16(fmt, 14);
                Float = tag == 3 || (tag == 0xFFFE && Marshal.ReadInt32(fmt, 24) == 3);   // KSDATAFORMAT_SUBTYPE_IEEE_FLOAT Data1 = 3
                hr = _client.Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 200000 /* 20 ms */, 0, fmt, IntPtr.Zero);
                Marshal.FreeCoTaskMem(fmt);
                if (hr != 0) return "Initialize(loopback) 0x" + hr.ToString("X8");
                var ciid = typeof(IAudioCaptureClient).GUID;
                hr = _client.GetService(ref ciid, out var c);
                if (hr != 0) return "GetService(IAudioCaptureClient) 0x" + hr.ToString("X8");
                _capture = (IAudioCaptureClient)c;
                bed?.SetSourceRate(Rate);
                hr = _client.Start();
                if (hr != 0) return "Start 0x" + hr.ToString("X8");
                _run = true;
                _th = new Thread(Loop) { IsBackground = true, Priority = ThreadPriority.AboveNormal };
                _th.Start();
                return null;
            }
            catch (Exception ex) { return ex.GetType().Name + ": " + ex.Message; }
        }

        void Loop()
        {
            var mono = new float[8192];
            while (_run)
            {
                if (_capture.GetNextPacketSize(out uint n) != 0) break;
                if (n == 0) { Thread.Sleep(2); continue; }
                if (_capture.GetBuffer(out var data, out uint frames, out uint flags, out _, out _) != 0) break;
                Packets++; Frames += frames;
                if (mono.Length < frames) mono = new float[frames];
                bool silent = (flags & AUDCLNT_BUFFERFLAGS_SILENT) != 0;
                if (silent) SilentPackets++;
                int bps = Bits / 8;
                for (int i = 0; i < frames; i++)
                {
                    double acc = 0;
                    if (!silent)
                        for (int ch = 0; ch < Channels; ch++)
                        {
                            int off = (i * Channels + ch) * bps;
                            acc += Float ? BitConverter.Int32BitsToSingle(Marshal.ReadInt32(data, off)) : Marshal.ReadInt16(data, off) / 32768.0;
                        }
                    float m = (float)(acc / Math.Max(1, Channels));
                    mono[i] = m;
                    if (Math.Abs(m) > Peak) Peak = Math.Abs(m);
                }
                _capture.ReleaseBuffer(frames);
                _bed?.Push(mono, (int)frames);
            }
        }

        public void Stop()
        {
            _run = false; _th?.Join(500);
            try { _client?.Stop(); } catch { }
            if (_capture != null) Marshal.ReleaseComObject(_capture);
            if (_client != null) Marshal.ReleaseComObject(_client);
            _capture = null; _client = null;
        }
    }
}
