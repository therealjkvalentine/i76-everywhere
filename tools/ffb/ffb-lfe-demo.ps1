<#
  ffb-lfe-demo.ps1 - hear every shaker channel on its own, then in combination,
  without launching the game.

  WHY: every channel so far has been judged either from a number in a readout or
  from a drive with five sources playing at once. Neither tells you whether an
  impact feels like an impact. This plays each source alone, at exactly the
  amplitude it ships with, says what it is and what to notice, and only then puts
  them together.

  Nothing here is a special demo signal. Part 1 drives the real DSP with one
  source enabled; part 2 drives the real MIXER with scripted telemetry. If it
  feels right here it will feel right in the game - and if it does not, the fault
  is reproducible without a play session.

      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-demo.ps1 -ListDevices
      powershell -NoProfile -ExecutionPolicy Bypass -File tools\ffb\ffb-lfe-demo.ps1 -Device 0
      ... -Device 0 -Pause           wait for Enter between items
      ... -Device 0 -Only IMPACT     just one
#>
param(
    [switch]$ListDevices,
    [int]$Device = -1,
    [string]$Only = "",
    [switch]$Pause,
    [int]$Rate = 16000,
    [int]$FrameHz = 60,
    [double]$Drive = 1.5,
    [double]$Master = 0.9
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'FfbMixer.ps1')
. (Join-Path $here 'LfeSynth.ps1')

if ($ListDevices) {
    Write-Host ""
    Write-Host "output devices (pass the number as -Device):" -ForegroundColor Cyan
    Write-Host ("  {0,3}  {1}" -f '-1', 'system default (WAVE_MAPPER)')
    $d = [LfeOut]::Devices()
    for ($k = 0; $k -lt $d.Count; $k++) { Write-Host ("  {0,3}  {1}" -f $k, $d[$k]) }
    Write-Host ""
    Write-Host "Pick the one your SHAKERS are on." -ForegroundColor Yellow
    exit 0
}

$tune = Mix-DefaultTune
[LfeCore]::ScrubHzCfg   = [double]$tune.LfeScrubHz
[LfeCore]::ExplodeHzCfg = [double]$tune.LfeExplodeHz
[LfeCore]::RenderTap = 2
[LfeCore]::RenderBypassLimit = $false

$devs = [LfeOut]::Devices()
$devName = if ($Device -lt 0 -or $Device -ge $devs.Count) { 'system default' } else { $devs[$Device] }

function Blank { param([int]$Count) return ,(New-Object double[] $Count) }

function Play-Tracks {
    param($Ef, $Ea, $Rf, $Ra, $Ia, $Wa, $Ha, $Sa, $Xa)
    $pcm = [LfeCore]::RenderLive($Ef,$Ea,$Rf,$Ra,$Ia,$Wa,$Ha,$Sa,$Xa,
        $Rate, $FrameHz, $Master, $Drive,
        [double]$tune.LfeEngineJitter, [double]$tune.LfeImpactHz, [double]$tune.LfeWeaponHz,
        [double]$tune.LfeCarrierHz, 11.0, 85.0,
        [double[]]$tune.LfeRespHz, [double[]]$tune.LfeRespRel, [double]$tune.LfeCompMax)
    $b = New-Object byte[] ($pcm.Length * 2)
    [Buffer]::BlockCopy($pcm, 0, $b, 0, $b.Length)
    $meter = [LfeCore]::LastRender
    $err = [LfeOut]::Play($b, $Rate, $Device)
    if ($err) { Write-Host "  PLAYBACK FAILED: $err" -ForegroundColor Red; exit 1 }
    return $meter
}

function Report {
    param($Meter)
    Write-Host ("                    peak {0:0.00}   {1:0.0}% limited" -f `
        $Meter.PeakAbs, (100.0 * $Meter.Limited / [math]::Max(1, $Meter.Samples))) -ForegroundColor DarkGray
    if ($Pause) {
        Write-Host "                    Enter for next..." -ForegroundColor DarkGray
        [void](Read-Host)
    }
}

# ---- part 1: one source at a time ----------------------------------------
# Steady sources play flat. EVENTS are spiked for a single frame and repeated,
# because that is exactly how the game delivers them - the peak-hold on the audio
# thread is what turns a one-frame spike into a thump, so this tests that too.
$SOLO = @(
 @{ N='engine idle';    Hz=$tune.LfeEngineIdleHz; Sec=3.0; Kind='steady'; Ch='e'
    Amp=($tune.LfeEngineAmp * 0.35)
    Note='low steady bed - present, never intrusive' }
 @{ N='engine revving'; Hz=$tune.LfeEngineMaxHz;  Sec=3.5; Kind='sweep';  Ch='e'
    Amp=$tune.LfeEngineAmp
    Note='pitch climbs with speed, toward your rig peak at 35 Hz' }
 @{ N='road bed';       Hz=$tune.LfeRoadLoHz;     Sec=3.0; Kind='steady'; Ch='r'
    Amp=$tune.LfeRoadAmp
    Note='noise, not a tone - texture. Only fires on bumps you did not cause' }
 @{ N='IMPACT';         Hz=$tune.LfeImpactHz;     Sec=4.5; Kind='event';  Ch='i'
    Amp=0.602
    Note='30 Hz, deep and heavy. Four hits. This is a collision' }
 @{ N='weapon';         Hz=$tune.LfeWeaponHz;     Sec=4.5; Kind='event';  Ch='w'
    Amp=0.513
    Note='38 Hz, shorter and snappier than an impact. Four shots' }
 @{ N='EXPLOSION';      Hz=$tune.LfeExplodeHz;    Sec=5.0; Kind='event';  Ch='x'
    Amp=$tune.LfeExplodeAmp
    Note='22 Hz with a long tail - deepest and biggest thing in the mix' }
 @{ N='slide / scrub';  Hz=$tune.LfeScrubHz;      Sec=3.0; Kind='steady'; Ch='s'
    Amp=$tune.LfeScrubAmp
    Note='70 Hz with a ROUGH amplitude - should feel gritty, not like a tone' }
 @{ N='heave';          Hz=$tune.LfeCarrierHz;    Sec=3.5; Kind='wobble'; Ch='h'
    Amp=($tune.LfeHeaveAmp * 0.8)
    Note='35 Hz carrier swelling a few times a second - body motion, felt as rhythm' }
)

Write-Host ""
Write-Host "SHAKER AUDITION" -ForegroundColor Cyan
Write-Host ("output: {0}    drive {1}    master {2}" -f $devName, $Drive, $Master) -ForegroundColor DarkGray
Write-Host "Set the amp where you would actually drive, then leave it alone." -ForegroundColor Yellow
Write-Host ""
Write-Host "--- PART 1: each channel alone, at its shipped level ---" -ForegroundColor Cyan
Write-Host ""

foreach ($it in $SOLO) {
    if ($Only -and $it.N -notlike "*$Only*") { continue }
    $count = [int]($it.Sec * $FrameHz)
    $ef = Blank $count; $ea = Blank $count; $rf = Blank $count; $ra = Blank $count
    $ia = Blank $count; $wa = Blank $count; $ha = Blank $count
    $sa = Blank $count; $xa = Blank $count
    for ($i = 0; $i -lt $count; $i++) {
        $ef[$i] = [double]$tune.LfeEngineIdleHz
        $rf[$i] = [double]$tune.LfeRoadLoHz
    }

    # A hashtable lookup, NOT a switch. `$x = switch (..) { 'i' { $ia } }` unrolls
    # the array into the pipeline and rebuilds it, so $tgt would be a COPY and
    # every write below would land nowhere - the channel plays silence. Same trap
    # the `,` in Blank guards against.
    $byCh = @{ e = $ea; r = $ra; i = $ia; w = $wa; h = $ha; s = $sa; x = $xa }
    $tgt = $byCh[$it.Ch]
    $lo = [double]$tune.LfeEngineIdleHz
    $hi = [double]$tune.LfeEngineMaxHz
    for ($i = 0; $i -lt $count; $i++) {
        if ($it.Kind -eq 'steady') {
            $tgt[$i] = [double]$it.Amp
        } elseif ($it.Kind -eq 'sweep') {
            $tgt[$i] = [double]$it.Amp
            $ef[$i]  = $lo + ($hi - $lo) * ($i / [double]$count)
        } elseif ($it.Kind -eq 'wobble') {
            $tgt[$i] = [double]$it.Amp * (0.15 + 0.85 * [math]::Max(0.0, [math]::Sin(2*[math]::PI*2.5*$i/$FrameHz)))
        }
    }
    if ($it.Kind -eq 'event') {
        for ($k = 1; $k -le 4; $k++) {
            $idx = [int]($k * $FrameHz * 1.0)
            if ($idx -lt $count) { $tgt[$idx] = [double]$it.Amp }
        }
    }

    Write-Host ("  {0,-16} {1,5:0.#} Hz   {2}" -f $it.N, $it.Hz, $it.Note) -ForegroundColor Green
    Report (Play-Tracks $ef $ea $rf $ra $ia $wa $ha $sa $xa)
}

# ---- part 2: through the real mixer --------------------------------------
Write-Host ""
Write-Host "--- PART 2: scripted driving, through the real mixer ---" -ForegroundColor Cyan
Write-Host ""

$SCEN = @(
 @{ N='pulling away';   Sec=5.0; Note='engine rising - nothing else should fire' }
 @{ N='hitting a wall'; Sec=5.0; Note='cruise, then one heavy collision' }
 @{ N='firing';         Sec=5.0; Note='cruising and shooting' }
 @{ N='a car blows up'; Sec=5.0; Note='cruising, then a mag-60 blast' }
 @{ N='drifting';       Sec=5.0; Note='sustained slide - grit at 70 Hz under the engine' }
)

foreach ($sc in $SCEN) {
    if ($Only -and $sc.N -notlike "*$Only*") { continue }
    $count = [int]($sc.Sec * $FrameHz)
    $ef = Blank $count; $ea = Blank $count; $rf = Blank $count; $ra = Blank $count
    $ia = Blank $count; $wa = Blank $count; $ha = Blank $count
    $sa = Blank $count; $xa = Blank $count
    $mix = Mix-New $tune

    for ($i = 0; $i -lt $count; $i++) {
        $t = $i / [double]$FrameHz
        $sp = 17.9; $thr = 0.4; $jolt = 2.0; $over = 0.0
        $fx = @()
        if ($sc.N -eq 'pulling away') {
            $sp = [math]::Min(30.0, 5.0*$t); $thr = 1.0; $jolt = 4.9
        } elseif ($sc.N -eq 'hitting a wall') {
            if ($t -ge 2.5 -and $t -lt 2.6) { $jolt = 180.0 }
            if ($t -ge 2.6) { $sp = 0.0; $thr = 0.0 }
        } elseif ($sc.N -eq 'firing') {
            if (([int]($t*2)) -ne ([int](($t-0.02)*2))) {
                $fx = @([pscustomobject]@{ Slot=0; Id=8; Param=0.8; Mag=10.0 })
            }
        } elseif ($sc.N -eq 'a car blows up') {
            if ($t -ge 2.0 -and $t -lt 2.03) {
                $fx = @([pscustomobject]@{ Slot=0; Id=17; Param=0.9; Mag=60.0 })
            }
        } elseif ($sc.N -eq 'drifting') {
            $over = 0.8
        }
        $fire = ($fx.Count -gt 0)
        $steer = 0.0; $yaw = 0.0
        if ($over -gt 0) { $steer = 0.4; $yaw = 1.4 }
        $s = [pscustomobject]@{
            T=$t; Speed=$sp; SpeedMph=($sp*2.23694); Steer=$steer; Throttle=$thr
            YawRate=$yaw; AngVelX=0.0; AngVelZ=0.0; Vy=0.0
            LongG=0.0; LongAccel=0.0; LatG=0.0; LatAccel=0.0
            HeaveAccel=0.0; TravelPitch=0.0
            ExpectedYaw=0.0; Understeer=0.0; Oversteer=$over; Jolt=$jolt
            Firing=$fire; FxEvent=$fire; FxFired=$fx
            Braking=$false; Airborne=$false
            Ticks=$i; Polls=$i; Wheelbase=4.662
        }
        $L = (Mix-Update $mix $s).Bus.Lfe
        $ef[$i] = [double]$L.EngineFreq
        $ea[$i] = [double]$L.EngineAmp
        $rf[$i] = [double]$(if ($null -ne $L.RoadFreq) { $L.RoadFreq } else { 60.0 })
        $ra[$i] = [double]$L.RoadAmp
        $ia[$i] = [double]$L.ImpulseAmp
        $wa[$i] = [double]$L.WeaponAmp
        $ha[$i] = [double]$(if ($null -ne $L.HeaveAmp) { $L.HeaveAmp } else { 0.0 })
        $sa[$i] = [double]$(if ($null -ne $L.ScrubAmp) { $L.ScrubAmp } else { 0.0 })
        $xa[$i] = [double]$(if ($null -ne $L.ExplodeAmp) { $L.ExplodeAmp } else { 0.0 })
    }

    Write-Host ("  {0,-16} {1}" -f $sc.N, $sc.Note) -ForegroundColor Green
    Report (Play-Tracks $ef $ea $rf $ra $ia $wa $ha $sa $xa)
}

Write-Host ""
Write-Host "Done. Anything that felt wrong is reproducible with -Only <name>." -ForegroundColor Cyan
