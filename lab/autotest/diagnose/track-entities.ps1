<#
  track-entities.ps1 — watch every vehicle's motion in memory (no screenshots).

  Identifies which slot is which by BEHAVIOUR: the player is slot 0, and the mission target
  (e.g. Taurus in Trip mission 1) is the AI car that actually drives off. Prints per-entity
  distance travelled so you can name the slots.

  Usage:
    tools\track-entities.ps1 -Seconds 10
    tools\track-entities.ps1 -Seconds 20 -Drive     # hold throttle so the mission starts
#>
param([int]$Seconds = 10, [int]$SampleMs = 250, [switch]$Drive)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\memlib.ps1"
. "$PSScriptRoot\..\lib\focuslib.ps1"
. "$PSScriptRoot\..\lib\inputlib.ps1"

$ctx = Mem-Open -Write
if (-not (Mem-InMission $ctx)) { throw "not in a mission" }
Force-Foreground $ctx.Proc.MainWindowHandle | Out-Null
Start-Sleep -Milliseconds 500

$prev = @{}
foreach ($e in Mem-Entities $ctx) { $prev[$e.Index] = $e }
$moved = @{}
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
    if ($Drive) { Mem-SetThrottle $ctx 127; Mem-SetSteer $ctx 60 }
    Start-Sleep -Milliseconds $SampleMs
    $now = @{}
    foreach ($e in Mem-Entities $ctx) { $now[$e.Index] = $e }
    foreach ($k in $now.Keys) {
        if ($prev.ContainsKey($k)) {
            $d = Mem-Distance $prev[$k] $now[$k]
            if (-not $moved.ContainsKey($k)) { $moved[$k] = 0.0 }
            $moved[$k] += $d
        }
    }
    $prev = $now
}
if ($Drive) { Mem-SetThrottle $ctx 0 }

Write-Host "`nper-entity distance travelled over $Seconds s:" -ForegroundColor Cyan
foreach ($k in ($moved.Keys | Sort-Object)) {
    $e = $prev[$k]
    $tag = if ($k -eq 0) { 'PLAYER' } elseif ($moved[$k] -gt 5) { 'MOVING (mission target?)' } else { 'static/parked' }
    Write-Host ("  idx {0}: moved {1,8:N1} m   now ({2,9:N1},{3,6:N1},{4,9:N1}) r={5:N2}  {6}" -f `
        $k, $moved[$k], $e.X, $e.Y, $e.Z, $e.Radius, $tag)
}
Mem-Close $ctx
