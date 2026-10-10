using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json.Nodes;
using System.Threading;
using Haptics.Core;
using Haptics.Effects;

namespace Haptics.Renderers
{
    /// <summary>A source of extra shaker samples mixed under the synth (the loopback ambience bed).</summary>
    public interface ILfeBed
    {
        /// <summary>The bed's next sample at the synth's rate, already gained, gated and ducked, -1..1.</summary>
        double Next();
        void SetDuck(double factor);
    }

    /// <summary>
    /// Lfe.Synth: bass-transducer signal synthesised from the bus (HAPTICS-ARCHITECTURE section 5: "synthesise, don't
    /// tap"). Exactly LfeSynth.ps1's live path (LfeSmoother advanced per sample, LfeCore.Step, drive into the soft
    /// knee, master) plus the chain voices and the optional loopback bed summed in before the filters.
    /// File sink: a mono 16-bit WAV. Live (--live only): waveOut to the device whose name matches the rig.
    /// </summary>
    public sealed class LfeSynthRenderer : IRenderer
    {
        public string Type => "Lfe.Synth";
        RendererContext _ctx;
        LfeCore _core; LfeSmoother _sm; LfeVoiceBank _bank;
        int _rate, _perUpdate; double _drive, _master;
        readonly List<short> _pcm = new List<short>();
        public ILfeBed Bed;
        public double SynthGain = 1.0;      // rig lfe.sources.synth (Renderers/LfeStems.cs LfeSources): 0 = stems / bed only
        LfeLiveOut _live;
        public string WavPath;
        public LfeCore Core => _core;

        public static LfeCore MakeCore(RendererContext ctx, Tune t)
        {
            int rate = (int)ctx.Num("rate", 16000);
            double[] rHz = Arr(ctx.Config, "resp_hz") ?? t.Array("LfeRespHz");
            double[] rRel = Arr(ctx.Config, "resp_rel") ?? t.Array("LfeRespRel");
            return new LfeCore(rate, t["LfeEngineJitter"], t["LfeImpactHz"], t["LfeWeaponHz"], t["LfeCarrierHz"],
                               ctx.Num("hp_hz", 11.0), ctx.Num("lp_hz", 85.0), rHz, rRel, ctx.Num("comp_max", t["LfeCompMax"]),
                               t["LfeScrubHz"], t["LfeExplodeHz"]);
        }
        static double[] Arr(JsonObject o, string k) => o?[k] is JsonArray a ? a.Select(x => x.GetValue<double>()).ToArray() : null;

        public void Open(RendererContext ctx)
        {
            _ctx = ctx;
            _rate = (int)ctx.Num("rate", 16000);
            _drive = ctx.Num("drive", 1.5); _master = ctx.Num("master", 0.9);
            SynthGain = LfeSources.Read(ctx.Rig).synth;
            _perUpdate = _rate / Math.Max(1, ctx.CoreHz);
            _core = MakeCore(ctx, ctx.Tune);
            _sm = new LfeSmoother(_rate);
            _bank = new LfeVoiceBank(_rate);
            WavPath = System.IO.Path.Combine(ctx.OutDir ?? ".", ctx.Tag + ".lfe.wav");
            if (ctx.Live)
            {
                _live = new LfeLiveOut();
                string err = _live.Start(ctx.Str("device_name_match"), _rate, (int)ctx.Num("buffer_samples", 256), (int)ctx.Num("buffers", 4), this);
                if (err != null) { ctx.Log.WriteLine("Lfe.Synth live: " + err + " - falling back to the WAV sink"); _live = null; }
            }
        }

        // parameters the audio thread reads in live mode (plain doubles: a torn read costs one stale buffer at worst)
        internal double pEF = 25, pEA, pRF = 60, pRA, pIA, pWA, pHA, pSA, pXA;
        internal volatile Voice[] pVoices = new Voice[0];

        public void Render(CoreStep step)
        {
            var L = step.Bus.Lfe;
            pEF = L.EngineFreq; pEA = L.EngineAmp; pRF = L.RoadFreq; pRA = L.RoadAmp; pIA = L.ImpulseAmp; pWA = L.WeaponAmp;
            pHA = L.HeaveAmp; pSA = L.ScrubAmp; pXA = L.ExplodeAmp;
            pVoices = step.Bus.Voices.Where(v => v.LfeAmp > 0).ToArray();
            if (Bed != null)
            {
                double tr = Math.Max(Math.Max(L.ImpulseAmp, L.ExplodeAmp), L.WeaponAmp);
                foreach (var v in step.Bus.Voices) if (v.Transient) tr = Math.Max(tr, v.LfeAmp);
                Bed.SetDuck(Math.Max(0, 1.0 - _ctx.Rig.Num("loopback", "duck_on_transient", 0.6) * Math.Min(1, tr)));
            }
            (Bed as ILfeStepBed)?.OnStep(step);              // Lfe.Stems: this step's SOUND_START / STOP before its samples
            if (_live != null) return;                       // the audio thread renders
            _bank.SetTargets(pVoices);
            for (int k = 0; k < _perUpdate; k++) _pcm.Add(NextSample());
        }

        internal short NextSample()
        {
            _sm.Advance(pEF, pEA, pRF, pRA, pIA, pWA, pHA, pSA, pXA);
            double g = SynthGain;                           // x 1.0 is exact: the default leaves the output sample-identical
            double extra = (_bank.Count > 0 ? _bank.Sample(_core) : 0.0) * g;
            if (Bed != null) extra += Bed.Next();
            double v = _core.Step(_sm.sEngF, _sm.sEngA * g, _sm.sRoadF, _sm.sRoadA * g, _sm.sImpA * g, _sm.sWpnA * g, _sm.sHvA * g, _sm.sScrA * g, _sm.sExpA * g, extra);
            v = _core.Limit(v * _drive) * _master;
            return (short)(v * 32767);
        }
        internal void LiveRefreshVoices() => _bank.SetTargets(pVoices);

        public short[] Pcm => _pcm.ToArray();

        public void Close()
        {
            if (_live != null) { _live.Stop(); _live = null; return; }
            if (_ctx?.OutDir != null) Wav.Write(WavPath, _pcm.ToArray(), _rate);
        }
        public string Summary() => string.Format(System.Globalization.CultureInfo.InvariantCulture,
            "Lfe.Synth: {0} samples @ {1} Hz, peak {2:0.00}, limited {3:0.00}% -> {4}",
            _pcm.Count, _rate, _core?.PeakAbs ?? 0, 100.0 * (_core?.Limited ?? 0) / Math.Max(1, _core?.Samples ?? 1), _live != null ? "live device" : WavPath);
        public void Dispose() { }
    }

    /// <summary>waveOut streaming (LfeSynth.ps1 LfeOut + LfeLive). Opened only from Lfe.Synth live mode (--live).</summary>
    public sealed class LfeLiveOut
    {
        [StructLayout(LayoutKind.Sequential)] public struct WAVEFORMATEX { public ushort wFormatTag, nChannels; public uint nSamplesPerSec, nAvgBytesPerSec; public ushort nBlockAlign, wBitsPerSample, cbSize; }
        [StructLayout(LayoutKind.Sequential)] public struct WAVEHDR { public IntPtr lpData; public uint dwBufferLength, dwBytesRecorded; public IntPtr dwUser; public uint dwFlags, dwLoops; public IntPtr lpNext, reserved; }
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        public struct WAVEOUTCAPS { public ushort wMid, wPid; public uint vDriverVersion; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szPname; public uint dwFormats; public ushort wChannels, wReserved1; public uint dwSupport; }
        [DllImport("winmm.dll")] static extern uint waveOutGetNumDevs();
        [DllImport("winmm.dll", CharSet = CharSet.Unicode)] static extern uint waveOutGetDevCapsW(IntPtr id, ref WAVEOUTCAPS c, uint sz);
        [DllImport("winmm.dll")] static extern uint waveOutOpen(out IntPtr h, int devId, ref WAVEFORMATEX fmt, IntPtr cb, IntPtr inst, uint flags);
        [DllImport("winmm.dll", EntryPoint = "waveOutPrepareHeader")] static extern uint waveOutPrepareHeaderP(IntPtr h, IntPtr hdr, uint sz);
        [DllImport("winmm.dll", EntryPoint = "waveOutWrite")] static extern uint waveOutWriteP(IntPtr h, IntPtr hdr, uint sz);
        [DllImport("winmm.dll", EntryPoint = "waveOutUnprepareHeader")] static extern uint waveOutUnprepareHeaderP(IntPtr h, IntPtr hdr, uint sz);
        [DllImport("winmm.dll")] static extern uint waveOutReset(IntPtr h);
        [DllImport("winmm.dll")] static extern uint waveOutClose(IntPtr h);

        /// <summary>Output device names (index = waveOut id). Enumerating opens nothing.</summary>
        public static string[] Devices()
        {
            uint n = waveOutGetNumDevs(); var o = new string[n];
            for (uint i = 0; i < n; i++) { var c = new WAVEOUTCAPS(); waveOutGetDevCapsW((IntPtr)i, ref c, (uint)Marshal.SizeOf(typeof(WAVEOUTCAPS))); o[i] = c.szPname; }
            return o;
        }

        IntPtr _h; Thread _th; volatile bool _run; byte[][] _bufs; GCHandle[] _pins; IntPtr[] _hdr; int _flagsOff, _hdrSize, _n, _bs;
        LfeSynthRenderer _src;
        public long Underruns, WriteErrors;

        public string Start(string nameMatch, int rate, int bufSamples, int nBuf, LfeSynthRenderer src)
        {
            int dev = -1;
            var devs = Devices();
            if (!string.IsNullOrEmpty(nameMatch))
            {
                dev = Array.FindIndex(devs, d => d.Replace(" ", "").IndexOf(nameMatch.Replace(" ", ""), StringComparison.OrdinalIgnoreCase) >= 0);
                if (dev < 0) return "no output device matching '" + nameMatch + "' (have: " + string.Join(", ", devs) + ")";
            }
            _src = src; _n = nBuf; _bs = bufSamples;
            var f = new WAVEFORMATEX { wFormatTag = 1, nChannels = 1, nSamplesPerSec = (uint)rate, wBitsPerSample = 16, nBlockAlign = 2, nAvgBytesPerSec = (uint)(rate * 2) };
            uint r = waveOutOpen(out _h, dev, ref f, IntPtr.Zero, IntPtr.Zero, 0);
            if (r != 0) { _h = IntPtr.Zero; return "waveOutOpen failed, code " + r; }
            _bufs = new byte[nBuf][]; _pins = new GCHandle[nBuf]; _hdr = new IntPtr[nBuf];
            _hdrSize = Marshal.SizeOf(typeof(WAVEHDR)); _flagsOff = (int)Marshal.OffsetOf(typeof(WAVEHDR), "dwFlags");
            for (int i = 0; i < nBuf; i++)
            {
                _bufs[i] = new byte[bufSamples * 2]; _pins[i] = GCHandle.Alloc(_bufs[i], GCHandleType.Pinned);
                var hd = new WAVEHDR { lpData = _pins[i].AddrOfPinnedObject(), dwBufferLength = (uint)(bufSamples * 2) };
                _hdr[i] = Marshal.AllocHGlobal(_hdrSize); Marshal.StructureToPtr(hd, _hdr[i], false);
                waveOutPrepareHeaderP(_h, _hdr[i], (uint)_hdrSize);
                Marshal.WriteInt32(_hdr[i], _flagsOff, Marshal.ReadInt32(_hdr[i], _flagsOff) | 1);
            }
            _run = true; _th = new Thread(Loop) { IsBackground = true, Priority = ThreadPriority.AboveNormal }; _th.Start();
            return null;
        }

        void Loop()
        {
            while (_run)
            {
                bool filled = false; int inflight = 0;
                for (int i = 0; i < _n && _run; i++)
                {
                    int fl = Marshal.ReadInt32(_hdr[i], _flagsOff);
                    if ((fl & 0x10) != 0) { inflight++; continue; }
                    _src.LiveRefreshVoices();
                    for (int k = 0; k < _bs; k++) { short s = _src.NextSample(); _bufs[i][k * 2] = (byte)(s & 0xff); _bufs[i][k * 2 + 1] = (byte)((s >> 8) & 0xff); }
                    Marshal.WriteInt32(_hdr[i], _flagsOff, fl & ~1);
                    if (waveOutWriteP(_h, _hdr[i], (uint)_hdrSize) != 0) WriteErrors++;
                    filled = true;
                }
                if (inflight == 0 && filled) Underruns++;
                Thread.Sleep(filled ? 0 : 1);
            }
        }

        public void Stop()
        {
            _run = false; _th?.Join(500);
            if (_h == IntPtr.Zero) return;
            waveOutReset(_h);
            for (int i = 0; i < _n; i++) { waveOutUnprepareHeaderP(_h, _hdr[i], (uint)_hdrSize); Marshal.FreeHGlobal(_hdr[i]); if (_pins[i].IsAllocated) _pins[i].Free(); }
            waveOutClose(_h); _h = IntPtr.Zero;
        }
    }
}
