<#
  coast-test.ps1 — isolate DRAG from thrust by coasting.

  Accelerate to a target speed, release the throttle, then record the speed decay. Drag is the
  only force left, so the decay rate is a direct measurement of it.

    per-second decay equal across frame rates  -> drag is dt-scaled (correct)
    per-FRAME  decay equal across frame rates  -> drag is applied once per frame (the bug),
                                                  which lowers top speed at high FPS

  This is the cleanest available discriminator: it needs no terrain, no jump, and no AI.
#>
param([double]$TargetSpeed = 25, [int]$CoastSeconds = 8, [string]$Label = 'coast',
      [int]$SampleMs = 50, [string]$OutDir = "$PSScriptRoot\..\..\captures\traces")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\autotest\lib\memlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\focuslib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\inputlib.ps1"
. "$PSScriptRoot\..\..\autotest\lib\simlib.ps1"
New-Item -ItemType Directory -Force $OutDir | Out-Null

$ctx = Mem-Open
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
if (-not (Ensure-SimRunning $ctx)) { throw "sim not advancing" }
$inv = [Globalization.CultureInfo]::InvariantCulture

# --- accelerate to the target -------------------------------------------------
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 25) {
    Send-Key $VK.W 25
    $p = Mem-Player $ctx
    if ($p.Speed -ge $TargetSpeed) { break }
    Start-Sleep -Milliseconds 30
}
$p = Mem-Player $ctx
$startSpeed = $p.Speed
$startFrame = $p.Frame
Write-Host ("coasting from {0:N2} m/s" -f $startSpeed) -ForegroundColor Cyan

# --- release everything and record the decay ----------------------------------
$rows = @('t_ms,frame,speed,vx,vy,vz')
$sw2 = [Diagnostics.Stopwatch]::StartNew()
$next = 0
while ($sw2.Elapsed.TotalSeconds -lt $CoastSeconds) {
    $t = $sw2.Elapsed.TotalMilliseconds
    if ($t -ge $next) {
        $q = Mem-Player $ctx
        $rows += (([int]$t).ToString($inv) + ',' + ($q.Frame - $startFrame).ToString($inv) + ',' +
                  $q.Speed.ToString('R',$inv) + ',' + $q.VX.ToString('R',$inv) + ',' +
                  $q.VY.ToString('R',$inv) + ',' + $q.VZ.ToString('R',$inv))
        $next += $SampleMs
    }
    Start-Sleep -Milliseconds 5
}
$rows | Set-Content (Join-Path $OutDir "$Label.csv")
$end = Mem-Player $ctx
$dt = $sw2.Elapsed.TotalSeconds
$dfr = $end.Frame - $startFrame
Mem-Close $ctx
Write-Host ("{0}: {1:N2} -> {2:N2} m/s over {3:N2}s / {4} frames" -f $Label, $startSpeed, $end.Speed, $dt, $dfr) -ForegroundColor Green
if ($dt -gt 0)  { Write-Host ("  decay per SECOND : {0:N4} m/s^2" -f (($end.Speed - $startSpeed) / $dt)) }
if ($dfr -gt 0) { Write-Host ("  decay per FRAME  : {0:N5} m/s"   -f (($end.Speed - $startSpeed) / $dfr)) }
