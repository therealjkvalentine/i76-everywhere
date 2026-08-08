<#
  LfeSynth.ps1 - the shaker DSP, the audio device, and live streaming.

  ONE DSP, TWO CONSUMERS. ffb-lfe.ps1 renders a captured drive to a WAV;
  ffb-lfe-live.ps1 streams while you play. Both call LfeCore.Step, so what you
  hear offline is what you feel live, by construction rather than by discipline.
  The same reasoning put Tel-Slip in one place: two copies of a model drift, and
  the drift is silent.

  WHY winmm: System.Media.SoundPlayer can only reach the DEFAULT output device.
  Shakers hang off a second interface - here an Audient EVO 4 - so choosing the
  destination is the one thing this cannot do without. waveOut takes a device
  index. It is also the interop the rest of the repo already uses.

  Dot-source this; it defines nothing at load beyond the type.
#>

if (-not ("LfeCore" -as [type])) {
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Threading;

// ===================== DSP =====================
public class LfeCore {
  public static LfeCore LastRender;   // so callers can read the meters
  double engPh, roadPh, impPh, wpnPh, jitPh, carPh, noiseLp, noiseLp2;
  double lpA, lpB, hpA, hpB, hpPrevIn, hpPrevIn2;
  double kLp, aHp;
  Random rnd = new Random(1976);
  int rate;
  double jitter, impHz, wpnHz, carHz, compMax;
  double[] rHz, rRel;

  public LfeCore(int rate, double jitter, double impHz, double wpnHz, double carHz,
                 double hpHz, double lpHz, double[] rHz, double[] rRel, double compMax) {
    this.rate = rate; this.jitter = jitter;
    this.impHz = impHz; this.wpnHz = wpnHz; this.carHz = carHz;
    this.rHz = rHz; this.rRel = rRel; this.compMax = compMax;
    kLp = 1.0 - Math.Exp(-2.0 * Math.PI * lpHz / rate);
    double rcHp = 1.0 / (2.0 * Math.PI * hpHz);
    aHp = rcHp / (rcHp + 1.0 / rate);
  }

  // Per-source compensation against the MEASURED rig curve. Because this synth
  // is parametric - every source has a known instantaneous frequency - each is
  // corrected at its own frequency. Strictly better than EQ-ing the summed
  // output, which could only correct the mixture.
  public double Comp(double hz) {
    if (rHz == null || rHz.Length < 2 || compMax <= 1.0) return 1.0;
    double rel;
    if (hz <= rHz[0]) rel = rRel[0];
    else if (hz >= rHz[rHz.Length-1]) rel = rRel[rHz.Length-1];
    else {
      int k = 0; while (k < rHz.Length-2 && rHz[k+1] < hz) k++;
      // interpolate in LOG frequency - touch is ratio-based, so 20->25 Hz is a
      // bigger step than 60->65 and linear would misplace the correction
      double lo = Math.Log(rHz[k]), hi = Math.Log(rHz[k+1]);
      double u = (Math.Log(hz) - lo) / (hi - lo);
      rel = rRel[k] + (rRel[k+1] - rRel[k]) * u;
    }
    // A band the body cannot reach must NOT be boosted. Inverting a near-zero
    // response asks enormous gain to chase output that never arrives: full power
    // into a frequency felt as nothing, paid for in headroom and coil heat.
    const double floorRel = 0.08;
    if (rel <= 0.0) return 0.0;
    // Ramp toward the CAPPED gain. Scaling by 1/floorRel instead would peak at
    // 12.5x just under the floor - four times the cap - and step discontinuously.
    if (rel < floorRel) return (rel / floorRel) * Math.Min(1.0 / floorRel, compMax);
    double g = 1.0 / rel;
    return g > compMax ? compMax : g;
  }

  // Metering. Tactile content is judged by RMS - what you feel continuously -
  // but headroom is spent on peaks, so the two must be tracked separately.
  public double PeakAbs = 0; public long Limited = 0, Samples = 0;

  // Soft knee instead of a hard ceiling. A hard clip turns a peak into a burst
  // of harmonics - broadband, buzzy, and audible far outside the shaker's band.
  // This is linear up to 0.6 and bends smoothly to an asymptote at 1.0, so only
  // the rare peaks are touched and they are compressed rather than shattered.
  // Continuous in value AND slope at the knee: 0.4 * tanh'(0) = 1 exactly.
  public double Limit(double v) {
    Samples++;
    double a = Math.Abs(v);
    if (a > PeakAbs) PeakAbs = a;
    if (a <= 0.6) return v;
    Limited++;
    return (v < 0 ? -1.0 : 1.0) * (0.6 + 0.4 * Math.Tanh((a - 0.6) / 0.4));
  }

  public double Step(double engF, double engA, double roadF, double roadA,
                     double impA, double wpnA, double hvA) {
    // engine: sine with slow pitch wander. A perfectly steady tone numbs the
    // skin and masks everything else.
    jitPh += 2 * Math.PI * 0.7 / rate;
    double engFj = engF * (1.0 + jitter * Math.Sin(jitPh));
    engPh += 2 * Math.PI * engFj / rate;
    double sig = engA * Comp(engFj) * Math.Sin(engPh);
    // 2nd harmonic corrected at ITS frequency - on this rig that can be a very
    // different gain from the fundamental
    sig += engA * 0.18 * Comp(engFj * 2) * Math.Sin(engPh * 2);

    // road: band-limited noise. A noise bed is what road texture is.
    double white = rnd.NextDouble() * 2.0 - 1.0;
    double kN = 1.0 - Math.Exp(-2.0 * Math.PI * roadF / rate);
    // Two poles, not one. A single 6 dB/oct pole leaves white noise with
    // substantial energy an octave above the corner - out of the shaker's useful
    // band and into where it can only rattle.
    noiseLp += kN * (white - noiseLp);
    noiseLp2 += kN * (noiseLp - noiseLp2);
    roadPh += 2 * Math.PI * roadF / rate;
    sig += roadA * Comp(roadF) * (0.55 * noiseLp2 * 5.0 + 0.45 * Math.Sin(roadPh));

    impPh += 2 * Math.PI * impHz / rate;
    sig += impA * Comp(impHz) * Math.Sin(impPh);
    wpnPh += 2 * Math.PI * wpnHz / rate;
    sig += wpnA * Comp(wpnHz) * Math.Sin(wpnPh);

    // heave: carrier at the measured peak, amplitude-modulated by chassis heave.
    // Energy sits where the rig is strongest; the felt rhythm is the heave rate,
    // which is below the rig's own floor.
    carPh += 2 * Math.PI * carHz / rate;
    sig += hvA * Comp(carHz) * Math.Sin(carPh);

    double h1 = aHp * (hpA + sig - hpPrevIn);   hpPrevIn = sig;  hpA = h1;
    double h2 = aHp * (hpB + h1 - hpPrevIn2);   hpPrevIn2 = h1;  hpB = h2;
    lpA += kLp * (h2 - lpA);
    lpB += kLp * (lpA - lpB);
    return lpB;
  }

  // Offline: interpolate a 60 Hz parameter track up to audio rate.
  public static short[] Render(double[] t, double[] ef, double[] ea, double[] rf,
                               double[] ra, double[] ia, double[] wa, double[] ha,
                               int rate, double master, double drive, double jitter,
                               double impHz, double wpnHz, double carHz,
                               double hpHz, double lpHz,
                               double[] rHz, double[] rRel, double compMax) {
    int n = t.Length;
    double dur = t[n-1] - t[0];
    if (dur <= 0) return new short[0];
    int total = (int)(dur * rate);
    short[] outp = new short[total];
    var core = new LfeCore(rate, jitter, impHz, wpnHz, carHz, hpHz, lpHz, rHz, rRel, compMax);
    LastRender = core;
    int idx = 0;
    for (int i = 0; i < total; i++) {
      double tt = t[0] + (double)i / rate;
      while (idx < n - 2 && t[idx+1] < tt) idx++;
      double span = t[idx+1] - t[idx];
      double f = span > 1e-9 ? (tt - t[idx]) / span : 0.0;
      if (f < 0) f = 0; if (f > 1) f = 1;
      double v = core.Step(
        ef[idx] + (ef[idx+1] - ef[idx]) * f, ea[idx] + (ea[idx+1] - ea[idx]) * f,
        rf[idx] + (rf[idx+1] - rf[idx]) * f, ra[idx] + (ra[idx+1] - ra[idx]) * f,
        ia[idx] + (ia[idx+1] - ia[idx]) * f, wa[idx] + (wa[idx+1] - wa[idx]) * f,
        ha[idx] + (ha[idx+1] - ha[idx]) * f) * drive;
      v = core.Limit(v) * master;
      outp[i] = (short)(v * 32767);
    }
    return outp;
  }
}

// ===================== device + blocking play =====================
public class LfeOut {
  // DWORD_PTR fields are IntPtr so the struct is right in 32- and 64-bit.
  [StructLayout(LayoutKind.Sequential)]
  public struct WAVEFORMATEX {
    public ushort wFormatTag, nChannels;
    public uint nSamplesPerSec, nAvgBytesPerSec;
    public ushort nBlockAlign, wBitsPerSample, cbSize;
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct WAVEHDR {
    public IntPtr lpData; public uint dwBufferLength, dwBytesRecorded;
    public IntPtr dwUser; public uint dwFlags, dwLoops;
    public IntPtr lpNext, reserved;
  }
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct WAVEOUTCAPS {
    public ushort wMid, wPid; public uint vDriverVersion;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szPname;
    public uint dwFormats; public ushort wChannels, wReserved1; public uint dwSupport;
  }

  [DllImport("winmm.dll")] public static extern uint waveOutGetNumDevs();
  [DllImport("winmm.dll", CharSet = CharSet.Unicode)]
  public static extern uint waveOutGetDevCapsW(IntPtr id, ref WAVEOUTCAPS c, uint sz);
  [DllImport("winmm.dll")] public static extern uint waveOutOpen(
    out IntPtr h, int devId, ref WAVEFORMATEX fmt, IntPtr cb, IntPtr inst, uint flags);
  [DllImport("winmm.dll")] public static extern uint waveOutPrepareHeader(IntPtr h, ref WAVEHDR hdr, uint sz);
  [DllImport("winmm.dll")] public static extern uint waveOutWrite(IntPtr h, ref WAVEHDR hdr, uint sz);
  [DllImport("winmm.dll")] public static extern uint waveOutUnprepareHeader(IntPtr h, ref WAVEHDR hdr, uint sz);
  [DllImport("winmm.dll")] public static extern uint waveOutReset(IntPtr h);
  [DllImport("winmm.dll")] public static extern uint waveOutClose(IntPtr h);

  public static string[] Devices() {
    uint n = waveOutGetNumDevs();
    string[] outp = new string[n];
    for (uint i = 0; i < n; i++) {
      WAVEOUTCAPS c = new WAVEOUTCAPS();
      waveOutGetDevCapsW((IntPtr)i, ref c, (uint)Marshal.SizeOf(typeof(WAVEOUTCAPS)));
      outp[i] = c.szPname;
    }
    return outp;
  }

  public static WAVEFORMATEX Fmt(int rate) {
    WAVEFORMATEX f = new WAVEFORMATEX();
    f.wFormatTag = 1; f.nChannels = 1; f.nSamplesPerSec = (uint)rate;
    f.wBitsPerSample = 16; f.nBlockAlign = 2;
    f.nAvgBytesPerSec = (uint)(rate * 2); f.cbSize = 0;
    return f;
  }

  // Blocking. waveOutWrite is asynchronous, so spin on WHDR_DONE rather than
  // returning while the buffer is still on its way to the speaker.
  public static string Play(byte[] pcm, int rate, int devId) {
    WAVEFORMATEX f = Fmt(rate);
    IntPtr h;
    uint r = waveOutOpen(out h, devId, ref f, IntPtr.Zero, IntPtr.Zero, 0);
    if (r != 0) return "waveOutOpen failed, code " + r;
    GCHandle pin = GCHandle.Alloc(pcm, GCHandleType.Pinned);
    WAVEHDR hdr = new WAVEHDR();
    hdr.lpData = pin.AddrOfPinnedObject();
    hdr.dwBufferLength = (uint)pcm.Length;
    int sz = Marshal.SizeOf(typeof(WAVEHDR));
    try {
      r = waveOutPrepareHeader(h, ref hdr, (uint)sz);
      if (r != 0) return "prepareHeader failed, code " + r;
      r = waveOutWrite(h, ref hdr, (uint)sz);
      if (r != 0) return "waveOutWrite failed, code " + r;
      while ((hdr.dwFlags & 0x00000001) == 0) Thread.Sleep(10);
      waveOutUnprepareHeader(h, ref hdr, (uint)sz);
    } finally { pin.Free(); waveOutReset(h); waveOutClose(h); }
    return null;
  }
}

// ===================== live streaming =====================
public class LfeLive {
  // Parameters written by the game loop, read by the audio thread. Plain
  // doubles: aligned 64-bit reads do not tear on x64, and the worst case is one
  // buffer using a value 16 ms stale - inaudible for a rumble bed, and far
  // cheaper than locking the audio thread against a PowerShell caller.
  public double EngineFreq = 25, EngineAmp = 0, RoadFreq = 60, RoadAmp = 0;
  public double ImpulseAmp = 0, WeaponAmp = 0, HeaveAmp = 0, Master = 0.9, Drive = 1.0;
  public long Underruns = 0;

  // Smoothed copies, advanced ONE SAMPLE AT A TIME toward the targets above.
  // Without this the live path applies a 60 Hz staircase to every amplitude,
  // while the offline renderer interpolates between frames - so the two sounded
  // different, and the live one buzzed. Stepping a gain 60 times a second puts
  // sidebands +/-60 Hz around every source: classic zipper noise, and squarely in
  // the band this rig reproduces best.
  double sEngF = 25, sEngA, sRoadF = 60, sRoadA, sImpA, sWpnA, sHvA;

  IntPtr h = IntPtr.Zero;
  double kAmp, kFrq;
  public LfeCore core;
  Thread th;
  volatile bool running;
  int rate, bufSamples, nBuf;
  byte[][] bufs; GCHandle[] pins; LfeOut.WAVEHDR[] hdrs;

  public string Start(int devId, int rate, double jitter, double impHz, double wpnHz,
                      double carHz, double hpHz, double lpHz,
                      double[] rHz, double[] rRel, double compMax,
                      int bufSamples, int nBuf) {
    this.rate = rate; this.bufSamples = bufSamples; this.nBuf = nBuf;
    core = new LfeCore(rate, jitter, impHz, wpnHz, carHz, hpHz, lpHz, rHz, rRel, compMax);
    // 6 ms on amplitudes, 25 ms on frequencies - fast enough that an impact still
    // arrives as an impact, slow enough that the 16 ms parameter staircase is gone.
    kAmp = 1.0 - Math.Exp(-1.0 / (0.006 * rate));
    kFrq = 1.0 - Math.Exp(-1.0 / (0.025 * rate));
    LfeOut.WAVEFORMATEX f = LfeOut.Fmt(rate);
    uint r = LfeOut.waveOutOpen(out h, devId, ref f, IntPtr.Zero, IntPtr.Zero, 0);
    if (r != 0) { h = IntPtr.Zero; return "waveOutOpen failed, code " + r; }

    bufs = new byte[nBuf][]; pins = new GCHandle[nBuf]; hdrs = new LfeOut.WAVEHDR[nBuf];
    int sz = Marshal.SizeOf(typeof(LfeOut.WAVEHDR));
    for (int i = 0; i < nBuf; i++) {
      bufs[i] = new byte[bufSamples * 2];
      pins[i] = GCHandle.Alloc(bufs[i], GCHandleType.Pinned);
      hdrs[i] = new LfeOut.WAVEHDR();
      hdrs[i].lpData = pins[i].AddrOfPinnedObject();
      hdrs[i].dwBufferLength = (uint)(bufSamples * 2);
      uint pr = LfeOut.waveOutPrepareHeader(h, ref hdrs[i], (uint)sz);
      if (pr != 0) return "prepareHeader failed, code " + pr;
      hdrs[i].dwFlags |= 0x00000001;   // WHDR_DONE: free, so the thread fills it
    }
    running = true;
    th = new Thread(Loop); th.IsBackground = true;
    th.Priority = ThreadPriority.AboveNormal;   // starving this makes it crackle
    th.Start();
    return null;
  }

  void Loop() {
    int sz = Marshal.SizeOf(typeof(LfeOut.WAVEHDR));
    while (running) {
      bool filled = false;
      for (int i = 0; i < nBuf && running; i++) {
        // WHDR_INQUEUE (0x10) still playing; WHDR_DONE (0x01) free to refill
        if ((hdrs[i].dwFlags & 0x00000010) != 0) continue;
        for (int k = 0; k < bufSamples; k++) {
          // amplitudes track quickly (transients must stay sharp), frequencies
          // slowly (a swept tone should glide, not stair-step)
          sEngA += kAmp * (EngineAmp - sEngA);   sRoadA += kAmp * (RoadAmp - sRoadA);
          sImpA += kAmp * (ImpulseAmp - sImpA);  sWpnA  += kAmp * (WeaponAmp - sWpnA);
          sHvA  += kAmp * (HeaveAmp - sHvA);
          sEngF += kFrq * (EngineFreq - sEngF);  sRoadF += kFrq * (RoadFreq - sRoadF);
          double v = core.Step(sEngF, sEngA, sRoadF, sRoadA, sImpA, sWpnA, sHvA) * Drive;
          v = core.Limit(v) * Master;
          short s = (short)(v * 32767);
          bufs[i][k*2] = (byte)(s & 0xFF); bufs[i][k*2+1] = (byte)((s >> 8) & 0xFF);
        }
        hdrs[i].dwFlags &= ~0x00000001u;   // clear DONE before re-queueing
        LfeOut.waveOutWrite(h, ref hdrs[i], (uint)sz);
        filled = true;
      }
      // Every buffer still in flight: sleep briefly. If NOTHING was in flight we
      // had already run dry, which is the underrun worth counting.
      if (!filled) Thread.Sleep(1); else Thread.Sleep(0);
    }
  }

  public void Stop() {
    running = false;
    if (th != null) th.Join(500);
    if (h != IntPtr.Zero) {
      LfeOut.waveOutReset(h);
      int sz = Marshal.SizeOf(typeof(LfeOut.WAVEHDR));
      for (int i = 0; i < nBuf; i++) {
        LfeOut.waveOutUnprepareHeader(h, ref hdrs[i], (uint)sz);
        if (pins[i].IsAllocated) pins[i].Free();
      }
      LfeOut.waveOutClose(h); h = IntPtr.Zero;
    }
  }
}
"@
}
