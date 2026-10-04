<#
  body-motion.ps1 - quantify "the car's body motion is too fast at 60 fps" (user-reported,
  firsthand: it breaks the experience). Also localizes the 5-9% speed loss.

  What was and was not known: a steering-step on smooth ground rolls the SAME at both rates
  (measured earlier), but airborne roll rate is 1.24x at 60 fps and roll over ROUGH ground was
  never tested. This drives the same line at 20 and 60 fps over two surfaces (paved road /
  open desert) and records the body attitude every ~15 ms:
      t, frame, x, z, speed, roll, pitch, eyeY
  Analysis is offline (analyze-motion.py): mean |roll rate| and |pitch rate| in deg/s,
  height-jitter, oscillation frequency - per surface per rate. Per-SECOND metrics, so sampling
  and frame rates divide out; only samples where the frame counter advanced count.

  Usage (game IN training mission): body-motion.ps1 -Tag 60fps-r1
#>
param(
    [string]$Tag = 'run',
    [string]$OutDir = "$PSScriptRoot\..\..\captures\motion",
    [double]$Cruise = 18.0,
    [int]$PhaseSeconds = 22
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"

$proc = Get-GamePid
if (-not $proc) { throw "sandbox game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 400
$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
New-Item -ItemType Directory -Force $OutDir | Out-Null

function Yaw { $e = Mem-EyeAngles $ctx; if ($e) { $e.Yaw } else { $null } }
function WrapDeg([double]$d) { while ($d -gt 180) { $d -= 360 }; while ($d -lt -180) { $d += 360 }; $d }
function L-Tap([int]$ms) { Key-Down $VK.A; Start-Sleep -Milliseconds $ms; Key-Up $VK.A }
function R-Tap([int]$ms) { Key-Down $VK.D; Start-Sleep -Milliseconds $ms; Key-Up $VK.D }

# acquire control (tap through the intro autopilot's throttle hold - see cactus-gauntlet)
$acquired = $false
$deadline = (Get-Date).AddSeconds(120)
$taps = 0
while (-not $acquired -and (Get-Date) -lt $deadline) {
    Key-Down $VK.W; Start-Sleep -Milliseconds 70; Key-Up $VK.W; Start-Sleep -Milliseconds 90
    $taps++
    if ($taps % 8 -eq 0 -and ((Mem-Player $ctx).Speed) -gt 5) { $acquired = $true }
}
if (-not $acquired) { throw "never acquired control" }
Write-Host ("control acquired ({0} taps)" -f $taps)

$rows = @('tag,phase,t_ms,frame,x,z,speed,roll,pitch,eyey')
$sw = [Diagnostics.Stopwatch]::StartNew()

function Drive-Phase([string]$phase, [double]$lineZ) {
    $end = (Get-Date).AddSeconds($PhaseSeconds)
    while ((Get-Date) -lt $end) {
        $pl = Mem-Player $ctx
        $e  = Mem-EyeAngles $ctx
        if ($pl.Speed -lt $Cruise) { Key-Down $VK.W } else { Key-Up $VK.W }
        if ($null -ne $e) {
            # pursue a far point on the line (x always ahead)
            $des = [math]::Atan2(($pl.X + 120) - $pl.X, $lineZ - $pl.Z) * 180.0 / [math]::PI
            $err = WrapDeg ($des - $e.Yaw)
            if     ($err -gt  3) { R-Tap ([int][math]::Min(70, 12 + [math]::Abs($err)*2)) }
            elseif ($err -lt -3) { L-Tap ([int][math]::Min(70, 12 + [math]::Abs($err)*2)) }
            $script:rows += ('{0},{1},{2},{3},{4:0.00},{5:0.00},{6:0.00},{7:0.000},{8:0.000},{9:0.000}' -f `
                $Tag,$phase,$sw.ElapsedMilliseconds,$pl.Frame,$pl.X,$pl.Z,$pl.Speed,$e.Roll,$e.Pitch,$e.PY)
        }
        Start-Sleep -Milliseconds 10
    }
    Key-Up $VK.W
}

Write-Host "phase 1: paved road (z=49602)..."
Drive-Phase 'road' 49602.0
Write-Host "phase 2: open desert (z=49430)..."
Drive-Phase 'desert' 49430.0
$csv = Join-Path $OutDir "$Tag.csv"
$rows | Set-Content $csv
$fps = 0
$first = ($rows[1] -split ','); $last = ($rows[-1] -split ',')
if ($rows.Count -gt 2) { $fps = ([double]$last[3] - [double]$first[3]) / (([double]$last[2] - [double]$first[2]) / 1000.0) }
Write-Host ("wrote {0}  ({1} samples, fps~{2:N1})" -f $csv, ($rows.Count-1), $fps) -ForegroundColor Green
Mem-Close $ctx
