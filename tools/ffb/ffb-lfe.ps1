<#
  ffb-lfe.ps1 - render the bass-shaker channel of a captured drive to a WAV.

  The force bus carries an LFE block: parametric low-frequency content for a
  tactile transducer (engine fundamental, road bed, impact and weapon impulses).
  Parametric means nothing you can listen to - so this synthesises it into an
  ordinary WAV you can play, feel through a shaker, or open in an audio editor
  and look at the spectrum of.

      tools\ffb\ffb-lfe.ps1 -Csv drive2.csv
      tools\ffb\ffb-lfe.ps1 -Csv drive2.csv -Out shake.wav -Rate 8000

  ---------------------------------------------------------------------------
  WHY SYNTHESISE INSTEAD OF LOW-PASSING THE GAME AUDIO
  ---------------------------------------------------------------------------
  A 1997 title has no LFE channel. Its mix is full-range music and SFX, so a
  low-passed audio tap gives you sparse, uninformative rumble contaminated by the
  soundtrack. The commercial precedent is explicit: SimXperience's SimVibe is
  "physics based, rather than audio based", and SimHub's ShakeIt is the same idea -
  telemetry in, synthesised tones out. Telemetry knows things the audio does not:
  exactly when a wheel is scrubbing, exactly how hard an impact was.

  ---------------------------------------------------------------------------
  THE BAND, AND THE SAFETY FILTERS
  ---------------------------------------------------------------------------
  DEVICE: tuned for Aura AST-2B (20-80 Hz, Fs 40 Hz). See Mix-DefaultTune for
  why every band now centres on 40 Hz and how heave reaches below the floor.

  Shakers are 20-100 Hz devices (puck-style units like the Dayton BST-1 and Aura
  AST-2B are really 20-80 Hz with a resonance hump at 30-40 Hz; ButtKickers reach
  lower). Two filters are therefore not optional:

    * HIGH-PASS at 22 Hz. Infrasonic content produces large cone excursion for no
      perceptible benefit, and ButtKicker's own documentation warns it can damage
      the driver. Their BKA amplifier has a fixed 25 Hz low-cut for this reason.
    * LOW-PASS at 90 Hz. Above ~100 Hz a shaker stops delivering useful tactile
      output and starts making audible mechanical buzz. Dayton recommends 80 Hz or
      under; ButtKicker suggests 80-120 Hz.

  Both are 2-pole (12 dB/oct), cascaded one-pole sections. They are a safety net
  here rather than a shaping tool, because the content is authored in-band to
  begin with - but a fitted transducer should still have its own crossover.

  Frequency assignments and the reasoning for keeping concurrent effects apart
  live in FfbMixer.ps1's Lfe tunables.
#>
param(
    [string]$Csv = "",
    [string]$Out = "",
    # 8 kHz is ample: the content is entirely below 100 Hz, so Nyquist is met
    # eight times over, and the file stays small. Raise it if you want to inspect
    # the result in an editor that dislikes low rates.
    [int]$Rate = 8000,
    [double]$Master = 0.9,
    # Aura AST-2B: usable 20-80 Hz, Fs 40. The old 22/90 defaults spent
    # effort above where these transducers deliver any force.
    # 13 Hz is audible-by-touch on this desk, well below the driver's rated 20.
    # The high-pass exists to stop DC and sub-perceptual content, not to enforce
    # a spec sheet - so it sits just under what the rig can actually deliver.
    [double]$HpHz = 11.0,
    [double]$LpHz = 85.0,
    [switch]$NoCompensate
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')
. (Join-Path $here 'FfbMixer.ps1')

if (-not $Csv) { $Csv = Join-Path $here 'ffb-calib-samples.csv' }
if (-not (Test-Path $Csv)) { Write-Host "no capture at $Csv" -ForegroundColor Red; exit 1 }
if (-not $Out) { $Out = [System.IO.Path]::ChangeExtension($Csv, $null) + "lfe.wav" }

$raw = @(Import-Csv $Csv)
$cols = $raw[0].PSObject.Properties.Name
$has = { param($n) $cols -contains $n }
$hasFull = ($cols -contains 'longG') -and ($cols -contains 'jolt')
Write-Host ("replaying {0} ({1} samples)" -f (Split-Path -Leaf $Csv), $raw.Count) -ForegroundColor Cyan
if (-not $hasFull) { Write-Host "calibration capture - no jolt, so road/impulse will be silent" -ForegroundColor Yellow }

# ---- replay through the REAL mixer to get the LFE parameter track ---------
$mix = Mix-New
$n = $raw.Count
$tA=New-Object double[] $n; $efA=New-Object double[] $n; $eaA=New-Object double[] $n
$rfA=New-Object double[] $n; $raA=New-Object double[] $n
$iaA=New-Object double[] $n; $waA=New-Object double[] $n
$haA=New-Object double[] $n
$prevT=$null; $prevSpeed=0.0; $longG=0.0; $i=0
foreach ($r in $raw) {
    $t=[double]$r.t; $sp=[double]$r.speed; $st=[double]$r.steer; $yw=[double]$r.yaw
    if ($null -ne $prevT) { $dt=$t-$prevT; if ($dt -gt 0.005 -and $dt -lt 1.0) { $longG=(($sp-$prevSpeed)/$dt)/9.81 } }
    $prevT=$t; $prevSpeed=$sp
    $slip = Tel-Slip -Speed $sp -Steer $st -YawRate $yw
    $lg = if ($hasFull) { [double]$r.longG } else { $longG }
    $vy = if (& $has 'vy') { [double]$r.vy } else { 0.0 }
    $s = [pscustomobject]@{
        T=$t; Speed=$sp; SpeedMph=$sp*2.23694; Steer=$st
        Throttle=$(if (& $has 'throttle'){[double]$r.throttle}else{0.0}); YawRate=$yw
        AngVelX=$(if (& $has 'angVelX'){[double]$r.angVelX}else{0.0})
        AngVelZ=$(if (& $has 'angVelZ'){[double]$r.angVelZ}else{0.0})
        Vy=$vy; LongG=$lg; LongAccel=($lg*9.81); LatG=(($yw*$sp)/9.81); LatAccel=($yw*$sp)
        HeaveAccel=0.0; TravelPitch=0.0
        ExpectedYaw=$slip.ExpectedYaw; Understeer=$slip.Understeer; Oversteer=$slip.Oversteer
        Jolt=$(if (& $has 'jolt'){[double]$r.jolt}else{0.0}); Firing=$false
        Braking=($lg -lt -0.05); Airborne=([math]::Abs($vy) -gt 2.0)
        Ticks=0; Polls=0; Wheelbase=4.662
    }
    $o = Mix-Update $mix $s
    $L = $o.Bus.Lfe
    $tA[$i]=$t; $efA[$i]=$L.EngineFreq; $eaA[$i]=$L.EngineAmp
    $rfA[$i]=$(if ($null -ne $L.RoadFreq) { $L.RoadFreq } else { 60.0 }); $raA[$i]=$L.RoadAmp
    $iaA[$i]=$L.ImpulseAmp; $waA[$i]=$L.WeaponAmp
    $haA[$i]=$(if ($null -ne $L.HeaveAmp) { $L.HeaveAmp } else { 0.0 })
    $i++
}

# ---- synthesis ------------------------------------------------------------
# In C# rather than PowerShell: this is hundreds of thousands of samples with
# trig per sample, which a PS loop does in minutes and this does in a blink.
if (-not ('LfeSynth' -as [type])) {
Add-Type @"
using System;
public static class LfeSynth {
  // one-pole sections, cascaded in pairs for 12 dB/oct
  public static short[] Render(double[] t, double[] ef, double[] ea, double[] rf,
                               double[] ra, double[] ia, double[] wa, double[] ha,
                               int rate, double master, double jitter,
                               double impHz, double wpnHz, double carHz,
                               double hpHz, double lpHz,
                               double[] rHz, double[] rRel, double compMax)
  {
    int n = t.Length;
    // Per-source compensation. Because this synth is PARAMETRIC - every source
    // has a known instantaneous frequency - each one can be corrected at its own
    // frequency. That is strictly better than EQ-ing the summed output, which
    // could only correct the mixture and would smear correction across sources
    // that happen to overlap in the spectrum.
    Func<double,double> comp = hz => {
      if (rHz == null || rHz.Length < 2 || compMax <= 1.0) return 1.0;
      double rel;
      if (hz <= rHz[0]) rel = rRel[0];
      else if (hz >= rHz[rHz.Length-1]) rel = rRel[rHz.Length-1];
      else {
        int k = 0; while (k < rHz.Length-2 && rHz[k+1] < hz) k++;
        // interpolate in LOG frequency - hearing and touch are both ratio-based,
        // so 20->25 Hz is a bigger step than 60->65 and linear would misplace it
        double lo = Math.Log(rHz[k]), hi = Math.Log(rHz[k+1]);
        double u = (Math.Log(hz) - lo) / (hi - lo);
        rel = rRel[k] + (rRel[k+1] - rRel[k]) * u;
      }
      // A band the body cannot reach must NOT be boosted. Inverting a near-zero
      // response asks for enormous gain to chase output that will never arrive:
      // full power into a frequency that is felt as nothing, which buys silence
      // and pays for it in headroom and voice-coil heat. Below the floor the
      // gain therefore FALLS AWAY rather than running to the cap.
      const double floorRel = 0.08;
      if (rel <= 0.0) return 0.0;
      // Ramp toward the CAPPED gain, not the raw inverse. Scaling by 1/floorRel
      // instead would peak at 12.5x just below the floor - four times the cap,
      // and a step discontinuity at the boundary.
      if (rel < floorRel) return (rel / floorRel) * Math.Min(1.0 / floorRel, compMax);
      double g = 1.0 / rel;
      return g > compMax ? compMax : g;
    };
    double dur = t[n-1] - t[0];
    if (dur <= 0) return new short[0];
    int total = (int)(dur * rate);
    short[] outp = new short[total];
    double engPh = 0, roadPh = 0, impPh = 0, wpnPh = 0, jitPh = 0, carPh = 0;
    // envelope followers for the two one-shot channels: the parameter track is
    // already an envelope, so these only smooth the 60 Hz -> audio-rate steps
    double lpA = 0, lpB = 0, hpA = 0, hpB = 0, hpPrevIn = 0, hpPrevIn2 = 0;
    double kLp = 1.0 - Math.Exp(-2.0 * Math.PI * lpHz / rate);
    double rcHp = 1.0 / (2.0 * Math.PI * hpHz);
    double aHp = rcHp / (rcHp + 1.0 / rate);
    var rnd = new Random(1976);
    double noiseLp = 0;
    int idx = 0;
    for (int i = 0; i < total; i++) {
      double tt = t[0] + (double)i / rate;
      while (idx < n - 2 && t[idx+1] < tt) idx++;
      double span = t[idx+1] - t[idx];
      double f = span > 1e-9 ? (tt - t[idx]) / span : 0.0;
      if (f < 0) f = 0;
      if (f > 1) f = 1;
      // interpolation inlined: PowerShell 5.1's Add-Type compiles with an older
      // C# than local functions (C# 7) require.
      double engF  = ef[idx] + (ef[idx+1] - ef[idx]) * f;
      double engA  = ea[idx] + (ea[idx+1] - ea[idx]) * f;
      double roadF = rf[idx] + (rf[idx+1] - rf[idx]) * f;
      double roadA = ra[idx] + (ra[idx+1] - ra[idx]) * f;
      double impA  = ia[idx] + (ia[idx+1] - ia[idx]) * f;
      double wpnA  = wa[idx] + (wa[idx+1] - wa[idx]) * f;
      double hvA   = ha[idx] + (ha[idx+1] - ha[idx]) * f;

      // engine: sine with slow pitch wander. A perfectly steady tone numbs the
      // skin and masks everything else; ShakeIt randomises frequency for this.
      jitPh += 2 * Math.PI * 0.7 / rate;
      double engFj = engF * (1.0 + jitter * Math.Sin(jitPh));
      engPh += 2 * Math.PI * engFj / rate;
      double sig = engA * comp(engFj) * Math.Sin(engPh);
      // plus a quiet 2nd harmonic for body - compensated at ITS own frequency,
      // which on this rig can be a very different gain from the fundamental
      sig += engA * 0.18 * comp(engFj * 2) * Math.Sin(engPh * 2);

      // road: band-limited noise. White noise through a one-pole tracking the
      // road centre frequency - cheap, and a noise bed is what road texture is.
      double white = rnd.NextDouble() * 2.0 - 1.0;
      double kN = 1.0 - Math.Exp(-2.0 * Math.PI * roadF / rate);
      noiseLp += kN * (white - noiseLp);
      roadPh += 2 * Math.PI * roadF / rate;
      sig += roadA * comp(roadF) * (0.55 * noiseLp * 3.0 + 0.45 * Math.Sin(roadPh));

      // impulses: fixed frequency, amplitude already enveloped by the mixer
      impPh += 2 * Math.PI * impHz / rate;
      sig += impA * comp(impHz) * Math.Sin(impPh);
      wpnPh += 2 * Math.PI * wpnHz / rate;
      sig += wpnA * comp(wpnHz) * Math.Sin(wpnPh);

      // heave: carrier AT RESONANCE, amplitude-modulated by chassis heave. The
      // energy sits at carHz where the shaker is strongest; the felt rhythm is
      // the heave rate, which is mostly below the shaker's own floor.
      carPh += 2 * Math.PI * carHz / rate;
      sig += hvA * comp(carHz) * Math.Sin(carPh);

      // 2-pole high-pass at hpHz (excursion safety), then 2-pole low-pass at lpHz
      double h1 = aHp * (hpA + sig - hpPrevIn);       hpPrevIn = sig;  hpA = h1;
      double h2 = aHp * (hpB + h1 - hpPrevIn2);       hpPrevIn2 = h1;  hpB = h2;
      lpA += kLp * (h2 - lpA);
      lpB += kLp * (lpA - lpB);

      double v = lpB * master;
      if (v > 1.0) v = 1.0;
      if (v < -1.0) v = -1.0;
      outp[i] = (short)(v * 32767);
    }
    return outp;
  }
}
"@
}

$tune = Mix-DefaultTune
Write-Host "synthesising..." -ForegroundColor Cyan
$pcm = [LfeSynth]::Render($tA,$efA,$eaA,$rfA,$raA,$iaA,$waA,$haA,$Rate,$Master,
                          [double]$tune.LfeEngineJitter,[double]$tune.LfeImpactHz,
                          [double]$tune.LfeWeaponHz,[double]$tune.LfeCarrierHz,
                          $HpHz, $LpHz,
                          $(if ($NoCompensate) { $null } else { [double[]]$tune.LfeRespHz }),
                          [double[]]$tune.LfeRespRel, $(if ($NoCompensate) { 1.0 } else { [double]$tune.LfeCompMax }))

# ---- WAV ------------------------------------------------------------------
$fs = [System.IO.File]::Create($Out)
$bw = New-Object System.IO.BinaryWriter($fs)
$dataBytes = $pcm.Length * 2
$bw.Write([char[]]'RIFF'); $bw.Write([uint32](36 + $dataBytes)); $bw.Write([char[]]'WAVE')
$bw.Write([char[]]'fmt '); $bw.Write([uint32]16); $bw.Write([uint16]1); $bw.Write([uint16]1)
$bw.Write([uint32]$Rate); $bw.Write([uint32]($Rate * 2)); $bw.Write([uint16]2); $bw.Write([uint16]16)
$bw.Write([char[]]'data'); $bw.Write([uint32]$dataBytes)
foreach ($sm in $pcm) { $bw.Write([int16]$sm) }
$bw.Flush(); $bw.Close(); $fs.Close()

$peak = 0; foreach ($sm in $pcm) { $a=[math]::Abs([int]$sm); if ($a -gt $peak) { $peak=$a } }
Write-Host ""
Write-Host ("{0:0.0}s at {1} Hz mono   peak {2:0}% of full scale" -f `
    ($pcm.Length / [double]$Rate), $Rate, ($peak * 100.0 / 32767)) -ForegroundColor Green
Write-Host ("band: {0}-{1} Hz engine, {2}-{3} Hz road, {4} Hz impact, {5} Hz weapon" -f `
    $tune.LfeEngineIdleHz, $tune.LfeEngineMaxHz, $tune.LfeRoadLoHz, $tune.LfeRoadHiHz,
    $tune.LfeImpactHz, $tune.LfeWeaponHz) -ForegroundColor DarkGray
Write-Host ("heave: {0} Hz carrier, AM by chassis heave - carries sub-20 Hz motion" -f $tune.LfeCarrierHz) -ForegroundColor DarkGray
Write-Host ("filtered: {0} Hz high-pass, {1} Hz low-pass" -f $HpHz, $LpHz) -ForegroundColor DarkGray
if ($NoCompensate) {
    Write-Host "response compensation: OFF (-NoCompensate) - raw, uncorrected" -ForegroundColor Yellow
} else {
    Write-Host ("response compensation: ON, inverse of the measured rig curve, max {0:0.0}x" -f $tune.LfeCompMax) -ForegroundColor DarkGray
    Write-Host ("  measured peak {0} Hz; ends lifted, peak cut. Re-measure with ffb-lfe-sweep.ps1." -f $tune.LfeCarrierHz) -ForegroundColor DarkGray
}
Write-Host ("-> {0}" -f (Resolve-Path $Out)) -ForegroundColor Cyan
