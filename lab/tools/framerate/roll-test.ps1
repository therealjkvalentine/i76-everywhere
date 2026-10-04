<#
  roll-test.ps1 — measure chassis ROLL response to a step steer input.

  "Chassis roll is too fast at high frame rate" was unmeasurable while orientation was unknown.
  It is measurable now: the render-consumed eye transform at 0x5FCDC4 is
      [0..2] position   [3..5] right   [6..8] forward   [9..11] up   [12..14] scale
  and its UP vector is tilted away from vertical exactly by the chassis roll.

  Method - a step response, not a free drive:
    * HOLD the throttle key down (writing the engine's input block does nothing: it is refilled
      from the keyboard every frame. Discrete key taps are worse than useless here - they once
      faked a 15x difference that was pure sampling artefact. A held key is identical at any
      frame rate.)
    * let the car reach steady speed going straight
    * hold steer to full lock and log roll angle against WALL-CLOCK time
  If roll is frame-coupled, the same roll angle is reached ~3x sooner in seconds at 60 Hz.

  Run on FLAT ground (AirBase or SlickTrack) with AI cars set to zero, or terrain and traffic
  swamp the signal.

    tools\roll-test.ps1 -Label roll20
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [double]$SettleSeconds = 4,
    [double]$LogSeconds = 4,
    [ValidateSet('Left','Right')][string]$Turn = 'Left',
    [string]$OutDir
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
# $PSScriptRoot is not reliably expanded in a param default under `powershell -File`, which
# silently dropped an earlier run's CSVs at the drive root. Resolve it in the body instead.
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot '..\captures\roll' }

$EYE = 0x5FCDC4
function Get-Roll($ctx) {
    $v = Mem-Floats $ctx $EYE 12
    if (-not $v) { return $null }
    $fx,$fy,$fz = $v[6],$v[7],$v[8]
    $ux,$uy,$uz = $v[9],$v[10],$v[11]
    $fl = [math]::Sqrt($fx*$fx+$fy*$fy+$fz*$fz)
    if ($fl -lt 0.5) { return $null }
    $fx/=$fl; $fy/=$fl; $fz/=$fl
    # up with the roll removed: world up projected perpendicular to forward
    $d = $fy
    $px = -$fx*$d; $py = 1 - $fy*$d; $pz = -$fz*$d
    $pl = [math]::Sqrt($px*$px+$py*$py+$pz*$pz)
    if ($pl -lt 1e-6) { return $null }
    $px/=$pl; $py/=$pl; $pz/=$pl
    $c = $ux*$px + $uy*$py + $uz*$pz
    $c = [math]::Max(-1.0, [math]::Min(1.0, $c))
    # sign of the roll: which side of the no-roll up the actual up leans, about forward
    $sx = $py*$fz - $pz*$fy; $sy = $pz*$fx - $px*$fz; $sz = $px*$fy - $py*$fx
    $sign = if (($ux*$sx + $uy*$sy + $uz*$sz) -lt 0) { -1 } else { 1 }
    return $sign * [math]::Acos($c) * 180.0 / [math]::PI
}

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$out = Join-Path $OutDir "$Label.csv"
if (Test-Path $out) { Remove-Item $out -Force }   # never let a stale trace pass as a fresh run

$VK_W = [byte]0x57
$VK_TURN = if ($Turn -eq 'Left') { [byte]0x41 } else { [byte]0x44 }   # A / D
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null

# settle: straight and flat at full throttle
Key-Down $VK_W
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $SettleSeconds) { Key-Down $VK_W; Start-Sleep -Milliseconds 20 }
$p0 = Mem-Player $ctx
$roll0 = Get-Roll $ctx

# step
$rows = New-Object System.Collections.Generic.List[object]
Key-Down $VK_TURN
$sw.Restart()
while ($sw.Elapsed.TotalSeconds -lt $LogSeconds) {
    Key-Down $VK_W; Key-Down $VK_TURN          # re-assert so autorepeat gaps cannot drop it
    $r = Get-Roll $ctx
    $p = Mem-Player $ctx
    if ($null -ne $r) {
        $rows.Add([pscustomobject]@{
            t     = [math]::Round($sw.Elapsed.TotalSeconds, 4)
            frame = $p.Frame
            roll  = [math]::Round($r, 4)
            drift = [math]::Round($r - $roll0, 4)
            speed = [math]::Round($p.Speed, 3)
            yaw   = [math]::Round($p.YawRate, 5)
        })
    }
    Start-Sleep -Milliseconds 10
}
Key-Up $VK_TURN; Key-Up $VK_W

$f0 = $rows[0].frame; $f1 = $rows[$rows.Count-1].frame
$fps = ($f1 - $f0) / $rows[$rows.Count-1].t
$rows | Export-Csv -NoTypeInformation $out
Mem-Close $ctx
Write-Host ("{0}: {1:N1} fps, {2} samples, entry speed {3:N2} m/s, roll0 {4:N2} deg -> {5}" -f `
    $Label, $fps, $rows.Count, $p0.Speed, $roll0, $out) -ForegroundColor Green
