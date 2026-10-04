<#
  enter-mission5.ps1 — load the bookmarked save at TRIP mission 5 (the canyon-jump mission).

  Mission 5 is the canonical "high FPS breaks the game" test case: the scripted canyon jump is
  said to become impossible above 20 fps. Reaching it needs a save, so this drives the
  LOAD BOOKMARK path rather than NEW TRIP.

  Requires save002 (mission 5) in the game folder - check with:
      python ..\..\i76-everywhere\i76-save-editor.py --dir <gamedir> --list

  Flow (all coordinates calibrated, see lib/maplib.ps1):
    intro skip -> TRIP -> LOAD BOOKMARK -> SCENE 5 -> LOAD
    -> Car/Van Inventory (ACCEPT SALVAGE) -> Build and Repair (DONE)
    -> intro cutscene skip -> gameplay (verified by entities appearing)
#>
# -SceneY picks which bookmark row to load (SCENE 5 = 782; each row is ~50 px apart,
# SCENE 6 = 833). -StopAtGarage leaves you on the Build and Repair form so weapons can be
# equipped before entering the mission.
param([switch]$NoLaunch, [string]$GameDir = "$PSScriptRoot\..\game",
      [int]$SceneY = 782, [switch]$StopAtGarage)
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

# 1) intro -> main menu
for ($i=0; $i -lt 6; $i++) { Force-Foreground $proc.MainWindowHandle|Out-Null; Send-Key $VK.ESC; Start-Sleep -Milliseconds 300; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 800 }

# 2) TRIP -> LOAD BOOKMARK
[Inp]::SetCursorPos(243,298); Start-Sleep -Milliseconds 250
[Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 60;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)
Start-Sleep -Milliseconds 800
[Inp]::SetCursorPos(243,298); Start-Sleep -Milliseconds 120
[Inp]::SetCursorPos(298,346); Start-Sleep -Milliseconds 300
[Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 60;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)
Start-Sleep -Seconds 3

# 3) pick SCENE 5, LOAD
Click-Screen 1370 $SceneY 400          # scene row (SCENE 5 default)
Start-Sleep -Milliseconds 600
Click-Screen 1817 1284 500         # LOAD
Start-Sleep -Seconds 7

# 4) garage screens
Click-Screen 1995 1379 500         # ACCEPT SALVAGE  (Car/Van Inventory)
Start-Sleep -Seconds 4
if ($StopAtGarage) {
    Write-Host "Stopped on the BUILD AND REPAIR form - equip weapons, then click DONE." -ForegroundColor Yellow
    exit 0
}
Click-Screen 2007 1379 500         # DONE            (Build and Repair)
Start-Sleep -Seconds 5

# 5) skip the mission cutscene; gameplay is confirmed by the entity table filling
$ctx = Mem-Open
$ok = $false
for ($i=0; $i -lt 25; $i++) {
    if ((Mem-InMission $ctx) -and (@(Mem-Entities $ctx).Count -gt 0)) { $ok = $true; break }
    Force-Foreground $proc.MainWindowHandle | Out-Null
    Send-Key $VK.ESC; Start-Sleep -Milliseconds 250
    [Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 50;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)
    Start-Sleep -Milliseconds 1000
}
if ($ok) {
    $e = @(Mem-Entities $ctx)
    Write-Host ("IN MISSION 5 - {0} entities, sim running: {1}" -f $e.Count, (Ensure-SimRunning $ctx)) -ForegroundColor Green
} else { Write-Host "did not reach mission 5 gameplay" -ForegroundColor Red }
Mem-Close $ctx
exit ($(if ($ok) { 0 } else { 1 }))
