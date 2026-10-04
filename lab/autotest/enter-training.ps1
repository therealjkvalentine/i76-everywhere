<#
  enter-training.ps1 — launch into the TRIP training mission and bring the car to a stop.

  The training mission is the best stage for animation/per-frame work: it starts you on open
  flat desert with a large clear sky, and (unlike melee) there is no combat to end the run.
  The car starts rolling at ~15 m/s, so this brakes it to a halt - a stationary car means the
  view is not moving and pixel/animation measurements are not swamped by camera motion.

  TRAINING lives at UI (113,351) under TRIP (243,298) - read off a Capture-UI screenshot.
#>
param([switch]$NoLaunch, [switch]$NoStop, [string]$GameDir = "$PSScriptRoot\..\game")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\focuslib.ps1"; . "$PSScriptRoot\lib\inputlib.ps1"
. "$PSScriptRoot\lib\maplib.ps1";   . "$PSScriptRoot\lib\memlib.ps1"
. "$PSScriptRoot\lib\simlib.ps1"

if (-not $NoLaunch) {
    Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
    Start-Sleep -Seconds 2
    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir
    Start-Sleep -Seconds 9
}
$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null
for ($i=0; $i -lt 6; $i++) { Force-Foreground $proc.MainWindowHandle|Out-Null; Send-Key $VK.ESC; Start-Sleep -Milliseconds 300; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 800 }

[Inp]::SetCursorPos(243,298); Start-Sleep -Milliseconds 250          # TRIP
[Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 60;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)
Start-Sleep -Milliseconds 900
[Inp]::SetCursorPos(243,298); Start-Sleep -Milliseconds 150
Click-UI 113 351 400                                                  # TRAINING
Start-Sleep -Seconds 4

$ctx = Mem-Open
$ok = $false
for ($i=0; $i -lt 30; $i++) {
    if ((Mem-InMission $ctx) -and (@(Mem-Entities $ctx).Count -gt 0)) { $ok = $true; break }
    Force-Foreground $proc.MainWindowHandle | Out-Null
    Send-Key $VK.ESC; Start-Sleep -Milliseconds 250
    [Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 50;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)
    Start-Sleep -Milliseconds 900
}
if ($ok -and -not $NoStop) {
    # the mission starts you rolling at ~15 m/s; brake and handbrake to a standstill
    for ($i=0; $i -lt 25; $i++) { Send-Key $VK.S 50; Start-Sleep -Milliseconds 70 }
    Send-Key ([byte]0x43) 100
    Start-Sleep -Seconds 3
}
if ($ok) {
    $p = Mem-Player $ctx
    Write-Host ("IN TRAINING - speed {0:N2} m/s, {1} entities, sim {2}" -f $p.Speed, (@(Mem-Entities $ctx).Count), (Ensure-SimRunning $ctx)) -ForegroundColor Green
} else { Write-Host "did not reach training gameplay" -ForegroundColor Red }
Mem-Close $ctx
exit ($(if ($ok) { 0 } else { 1 }))
