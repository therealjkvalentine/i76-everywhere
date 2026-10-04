<#
  cactus-gauntlet.ps1 - measure the collision pass-through rate (fix-list bug #5).

  THE BUG (reported from play): at 60 fps the car drives clean through a cactus ~2/3 of the
  time; at 20 fps it collides correctly. Intermittency like that is the signature of a
  per-frame collision test. This harness turns the anecdote into a number.

  DESIGN
  * Training mission A01: the road east of spawn (1575, 49602) runs through a field of 89
    nsaguar1 saguaros whose exact world coordinates come from level-objects.py.
  * One RUN drives a gentle weave through a SEQUENCE of cacti. Fresh targets matter: a hit
    knocks the saguaro down, so a cactus is only a valid obstacle once per mission load.
  * Drive by HOLDING SCANCODE KEYS (Key-Down/Key-Up). The input-block poke does NOT work for
    throttle - physics-trace.ps1 line 39 verified it reads back 0 - so bang-bang key control
    is the established method.
  * Steering: pure pursuit via yaw from Mem-EyeAngles (cockpit forward = car heading), with
    the steer-key left/right sign CALIBRATED at run start rather than assumed.
  * Classification is post-hoc from a CSV of raw approach metrics - the script judges nothing
    on the fly. Per approach: min horizontal distance to the cactus, speed before, min speed
    near it, yaw kick. A 20 fps calibration pass validates the classifier (all clean passes
    over the trunk should read as hits there, per the reported behaviour).

  Usage: game running IN the training mission, car may be moving or stopped.
    tools\framerate\cactus-gauntlet.ps1 -Tag 60fps-run1
#>
param(
    [string]$Tag = 'run',
    [string]$OutDir = "$PSScriptRoot\..\..\captures\cactus",
    [double]$CruiseSpeed = 15.0,
    [double]$HitWindow = 12.0     # metres of x around the target counted as "at the cactus"
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"

# eastbound cactus line, gentle lateral steps (from level-objects.py on A01.MSN)
$TARGETS = @(
    @{ x = 1650.0; z = 49640.0 },
    @{ x = 1715.0; z = 49650.0 },
    @{ x = 1800.0; z = 49630.0 },
    @{ x = 1875.0; z = 49630.0 },
    @{ x = 1935.0; z = 49620.0 }
)

$proc = Get-GamePid
if (-not $proc) { throw "sandbox game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 500
$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }

New-Item -ItemType Directory -Force $OutDir | Out-Null
$csv  = Join-Path $OutDir "$Tag.csv"
$rows = @('tag,target_x,target_z,min_dist,cross_lat,v_before,v_min,yaw_in,yaw_out,frames_in_window,fps')

function W-Down { Key-Down $VK.W }  ; function W-Up { Key-Up $VK.W }
function L-Tap([int]$ms) { Key-Down $script:LeftKey;  Start-Sleep -Milliseconds $ms; Key-Up $script:LeftKey }
function R-Tap([int]$ms) { Key-Down $script:RightKey; Start-Sleep -Milliseconds $ms; Key-Up $script:RightKey }

function Yaw { $e = Mem-EyeAngles $ctx; if ($e) { $e.Yaw } else { $null } }
function WrapDeg([double]$d) { while ($d -gt 180) { $d -= 360 }; while ($d -lt -180) { $d += 360 }; $d }

# ---- ACQUIRE CONTROL: tap W until the car responds ------------------------------------
# The training mission opens with a scripted autopilot: it drives the intro fly-through, then
# HOLDS the car at the start line with throttle = -1.00 (full brake). Held W cannot override
# that hold - but TAPPING W breaks through and releases control (verified live: ~10 taps took
# v from 0 to 8 m/s, after which held W wound up 8 -> 27 m/s normally, so there is NO 60 fps
# throttle bug - the earlier "creep at 1 m/s" was held W losing to the autopilot). Frame-
# scripted, so the hold lasts ~3x longer in wall-clock at 60 fps; tap until it gives. Never
# brake to a standstill (S at 0 shifts the automatic into REVERSE, inverting the steer sign).
$script:LeftKey = $VK.A; $script:RightKey = $VK.D
$acquired = $false
$acqDeadline = (Get-Date).AddSeconds(120)
$taps = 0
while (-not $acquired -and (Get-Date) -lt $acqDeadline) {
    Key-Down $VK.W; Start-Sleep -Milliseconds 70; Key-Up $VK.W; Start-Sleep -Milliseconds 90
    $taps++
    if ($taps % 8 -eq 0) {
        $v = (Mem-Player $ctx).Speed
        if ($v -gt 5) { $acquired = $true; Write-Host ("control acquired after {0} taps (v={1:N1} m/s)" -f $taps, $v) }
    }
}
if (-not $acquired) { Write-Host "never acquired control (autopilot never released) - aborting run" -ForegroundColor Red; Mem-Close $ctx; exit 1 }
# car is now rolling FORWARD under our control (taps only ever add forward throttle)
# calibration must OBSERVE a yaw change - a 0.00 reading twice in a row means it measured
# nothing (eye transform not yet live), and an uncalibrated sign wrecks the whole pursuit
$calOk = $false
for ($attempt = 0; $attempt -lt 4 -and -not $calOk; $attempt++) {
    $y0 = Yaw
    Key-Down $VK.A; Start-Sleep -Milliseconds 450; Key-Up $VK.A
    Start-Sleep -Milliseconds 300
    $y1 = Yaw
    if ($null -ne $y0 -and $null -ne $y1) {
        $d = WrapDeg ($y1 - $y0)
        if ([math]::Abs($d) -gt 0.5) {
            if ($d -gt 0) { $script:LeftKey = $VK.D; $script:RightKey = $VK.A }
            Write-Host ("steer calibration: A moved yaw {0:N2} deg -> LeftKey={1}" -f $d, $(if ($script:LeftKey -eq $VK.A) { 'A' } else { 'D' }))
            $calOk = $true
        }
    }
    if (-not $calOk) { W-Down; Start-Sleep -Milliseconds 600 }
}
if (-not $calOk) { Write-Host "steer calibration NEVER observed a yaw change - aborting run (do not trust pursuit)" -ForegroundColor Red; W-Up; Mem-Close $ctx; exit 1 }

$f0 = Mem-I32 $ctx 0x5A7E1C; $t0 = Get-Date

foreach ($tg in $TARGETS) {
    $tx = $tg.x; $tz = $tg.z
    $minDist = 1e9; $vMin = 1e9; $vBefore = @(); $yawIn = $null; $yawOut = $null
    $framesIn0 = 0; $framesIn1 = 0
    $stuck = 0
    $deadline = (Get-Date).AddSeconds(90)     # a target must resolve in 90s or the run is over
    while ((Get-Date) -lt $deadline) {
        $p = Mem-Player $ctx
        if (-not $p) { break }
        $x = $p.X; $z = $p.Z; $v = $p.Speed
        if ($x -gt ($tx + $HitWindow)) { break }                      # past this cactus
        # speed governor
        if ($v -lt $CruiseSpeed) { W-Down } else { W-Up }
        # pure pursuit
        $yaw = Yaw
        if ($null -ne $yaw) {
            $des = [math]::Atan2($tx - $x, $tz - $z) * 180.0 / [math]::PI
            $err = WrapDeg ($des - $yaw)
            if     ($err -gt  2.5) { R-Tap ([int][math]::Min(90, 15 + [math]::Abs($err)*3)) }
            elseif ($err -lt -2.5) { L-Tap ([int][math]::Min(90, 15 + [math]::Abs($err)*3)) }
        }
        # metrics
        $dx = $x - $tx; $dz = $z - $tz
        $dist = [math]::Sqrt($dx*$dx + $dz*$dz)
        if ($dist -lt $minDist) { $minDist = $dist }
        if ([math]::Abs($dx) -le $HitWindow) {
            if ($framesIn0 -eq 0) { $framesIn0 = $p.Frame; $yawIn = $yaw }
            $framesIn1 = $p.Frame; $yawOut = $yaw
            if ($v -lt $vMin) { $vMin = $v }
        } else {
            $vBefore += $v
            if ($vBefore.Count -gt 40) { $vBefore = $vBefore[-40..-1] }
        }
        if ($v -lt 2.5 -and [math]::Abs($x - $tx) -gt $HitWindow) { $stuck++ } else { $stuck = 0 }
        if ($stuck -gt 120) { Write-Host "  wedged - abandoning run" -ForegroundColor Yellow; break }
        Start-Sleep -Milliseconds 12
    }
    W-Up
    $timedOut = ((Get-Date) -ge $deadline)
    $vb = if ($vBefore.Count) { ($vBefore | Select-Object -Last 25 | Measure-Object -Average).Average } else { 0 }
    $fps = ((Mem-I32 $ctx 0x5A7E1C) - $f0) / ((Get-Date) - $t0).TotalSeconds
    $lat = [math]::Abs((Mem-Player $ctx).Z - $tz)
    $rows += ('{0},{1},{2},{3:N2},{4:N2},{5:N2},{6:N2},{7:N2},{8:N2},{9},{10:N1}' -f `
        $Tag,$tx,$tz,$minDist,$lat,$vb,$(if($vMin -lt 1e8){$vMin}else{-1}),$yawIn,$yawOut,($framesIn1-$framesIn0),$fps)
    Write-Host ("  cactus ({0},{1}): minDist={2:N2}m  v_before={3:N1}  v_min={4:N1}" -f $tx,$tz,$minDist,$vb,$(if($vMin -lt 1e8){$vMin}else{-1}))
    if ($stuck -gt 120 -or $timedOut) { if ($timedOut) { Write-Host "  target timed out - ending run" -ForegroundColor Yellow }; break }
}
W-Up
$rows | Set-Content $csv
Write-Host ("wrote {0}" -f $csv) -ForegroundColor Green
Mem-Close $ctx
