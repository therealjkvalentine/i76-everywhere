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
    # PRE-LIMITER GAIN. The rendered signal has a crest factor of 21 dB - RMS
    # only 8.8% of peak - so almost all the headroom is held for rare transients
    # while the continuous content you actually feel sits far below it. Driving
    # into a soft knee raises what is felt without shattering the peaks.
    [double]$Drive = 2.0,

    # Aura AST-2B: usable 20-80 Hz, Fs 40. The old 22/90 defaults spent
    # effort above where these transducers deliver any force.
    # 13 Hz is audible-by-touch on this desk, well below the driver's rated 20.
    # The high-pass exists to stop DC and sub-perceptual content, not to enforce
    # a spec sheet - so it sits just under what the rig can actually deliver.
    [double]$HpHz = 11.0,
    [double]$LpHz = 85.0,
    [switch]$NoCompensate,
    [switch]$Play,              # play it through the shaker, don't just write a file
    [switch]$ListDevices,
    [int]$Device = -1           # -1 = system default; use -ListDevices to find yours
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'Telemetry.ps1')
. (Join-Path $here 'FfbMixer.ps1')

if (-not $Csv) { $Csv = Join-Path $here 'ffb-calib-samples.csv' }
if (-not (Test-Path $Csv)) { Write-Host "no capture at $Csv" -ForegroundColor Red; exit 1 }
if (-not $Out) { $Out = [System.IO.Path]::ChangeExtension($Csv, $null) + "lfe.wav" }

. (Join-Path $here 'LfeSynth.ps1')
if ($ListDevices) {
    Write-Host ""
    Write-Host "output devices (pass the number as -Device):" -ForegroundColor Cyan
    Write-Host ("  {0,3}  {1}" -f '-1', 'system default (WAVE_MAPPER)')
    $d = [LfeOut]::Devices()
    for ($k = 0; $k -lt $d.Count; $k++) { Write-Host ("  {0,3}  {1}" -f $k, $d[$k]) }
    exit 0
}

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
# The DSP now lives in LfeSynth.ps1, shared with ffb-lfe-live.ps1 so that what
# you hear from a replay and what you feel while driving cannot drift apart.
. (Join-Path $here 'LfeSynth.ps1')

$tune = Mix-DefaultTune
Write-Host "synthesising..." -ForegroundColor Cyan
$pcm = [LfeCore]::Render($tA,$efA,$eaA,$rfA,$raA,$iaA,$waA,$haA,$Rate,$Master,$Drive,
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

if ($Play) {
    # Same reason the sweep plays its own tones: writing a file and leaving the
    # playing to the operator is where a feedback loop goes to die.
    $bytes = New-Object byte[] ($pcm.Length * 2)
    [Buffer]::BlockCopy($pcm, 0, $bytes, 0, $bytes.Length)
    $devs = [LfeOut]::Devices()
    $dn = if ($Device -lt 0 -or $Device -ge $devs.Count) { 'system default' } else { $devs[$Device] }
    Write-Host ("playing through {0} - {1:0.0}s" -f $dn, ($pcm.Length / $Rate)) -ForegroundColor Green
    $err = [LfeOut]::Play($bytes, $Rate, $Device)
    if ($err) { Write-Host "PLAYBACK FAILED: $err" -ForegroundColor Red }
}

$peak = 0; foreach ($sm in $pcm) { $a=[math]::Abs([int]$sm); if ($a -gt $peak) { $peak=$a } }
Write-Host ""
$m = [LfeCore]::LastRender
Write-Host ("drive {0:0.0}x   peak {1:0.00} before limiting   {2:0.00}% of samples limited" -f `
    $Drive, $m.PeakAbs, (100.0 * $m.Limited / [math]::Max(1, $m.Samples))) -ForegroundColor DarkGray
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
