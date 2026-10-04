<#
  enter-trip1.ps1 — cold launch into TRIP campaign mission 1 ("keep up with Taurus").

  Use this (rather than enter-melee.ps1) when the test needs OTHER MOVING VEHICLES: mission 1
  spawns ~6 entities including Taurus, who drives off and must be followed.

  Verified by memory (player entity non-zero), not by screenshot.
#>
param([switch]$NoLaunch, [string]$GameDir = "$PSScriptRoot\..\game")
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\focuslib.ps1"; . "$PSScriptRoot\lib\inputlib.ps1"; . "$PSScriptRoot\lib\maplib.ps1"; . "$PSScriptRoot\lib\memlib.ps1"

if (-not $NoLaunch) {
    Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
    Start-Sleep -Seconds 2
    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir
    Start-Sleep -Seconds 9
}
$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
Force-Foreground $proc.MainWindowHandle | Out-Null

# 1) intro crawl -> main menu
for ($i=0; $i -lt 6; $i++) { Force-Foreground $proc.MainWindowHandle|Out-Null; Send-Key $VK.ESC; Start-Sleep -Milliseconds 300; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 800 }

# 2) TRIP (OS 243,298) -> NEW TRIP (OS 212,346)
Force-Foreground $proc.MainWindowHandle | Out-Null
[Inp]::SetCursorPos(243,298); Start-Sleep -Milliseconds 250
[Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 60;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)
Start-Sleep -Milliseconds 800
[Inp]::SetCursorPos(243,298); Start-Sleep -Milliseconds 120
[Inp]::SetCursorPos(212,346); Start-Sleep -Milliseconds 300
[Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 60;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)

# 3) cutscene -> mission. Skip with ESC + click until the player entity appears.
$ctx = Mem-Open
$deadline = (Get-Date).AddSeconds(75)
while ((Get-Date) -lt $deadline) {
    if (Mem-InMission $ctx) { break }
    Force-Foreground $proc.MainWindowHandle | Out-Null
    Send-Key $VK.ESC; Start-Sleep -Milliseconds 250
    [Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 50;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)
    Start-Sleep -Milliseconds 900
}
$ok = Mem-InMission $ctx
if ($ok) {
    $ents = @(Mem-Entities $ctx)
    Write-Host ("IN TRIP MISSION 1 - {0} live entities" -f $ents.Count) -ForegroundColor Green
    $ents | ForEach-Object { Write-Host ("  idx {0}: ({1:N1},{2:N1},{3:N1}) r={4:N2}" -f $_.Index,$_.X,$_.Y,$_.Z,$_.Radius) }
} else { Write-Host "did not reach the mission" -ForegroundColor Red }
Mem-Close $ctx
exit ($(if ($ok) { 0 } else { 1 }))
