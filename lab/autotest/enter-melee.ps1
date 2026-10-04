<#
  enter-melee.ps1 — launch I'76 (sandbox) and drive the menus into an INSTANT MELEE,
  fully unattended. Returns once the player entity is live (in a mission).

  This is the recovery path for the whole effort: the game crashes easily during RE, and
  the menus need a DirectInput cursor mapped into the screen's upper-left (see maplib.ps1).
  Encodes the calibrated path discovered 2026-08-08:
    intro -> ESC/ENTER skips -> main menu
    MELEE (OS 450,300) -> AUTO MELEE (490,360) -> INSTANT MELEE (535,375)
    Driver Entry Form -> ENTER AREA (screen 1648,1385 via calibrated map)
  In-mission is detected from memory: player entity [[[0x54a264]]+0x70] != 0.

  Usage:
    powershell -ExecutionPolicy Bypass -File tools\enter-melee.ps1            # launch + enter
    powershell -ExecutionPolicy Bypass -File tools\enter-melee.ps1 -NoLaunch  # already running
#>
<#
  -Area selects the ARENA on the Driver Entry Form. Terrain slope contaminates any speed or
  drag measurement (a car that wanders downhill gains speed), so physics tests should use a
  FLAT arena - 'SlickTrack' or 'AirBase' - not the default hilly Tombstone.
#>
param([switch]$NoLaunch, [switch]$KeepAI, [string]$GameDir = "$PSScriptRoot\..\game",
      [ValidateSet('','Crater','Dunes','AirBase','Suburbia','SlickTrack','Tombstone')][string]$Area = '',
      # stop early so a human can take over from a known point (used by record-session.ps1)
      [switch]$StopAtMainMenu, [switch]$StopAtForm,
      [switch]$DryRun)     # print the resolved game folder and exit
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\gamedir.ps1"
$GameDir = Resolve-LabGameDir $GameDir     # inside the lab only (default: the sandbox); the playable installs are refused
$I76GameDirInUse = $GameDir                # focuslib / maplib: this folder's process and its dgVoodoo.conf
if ($DryRun) { "enter-melee DRY RUN (nothing started): $(Join-Path $GameDir 'i76.exe') -glide, cwd $GameDir, conf $(Join-Path $GameDir 'dgVoodoo.conf')"; exit 0 }
. "$PSScriptRoot\lib\focuslib.ps1"; . "$PSScriptRoot\lib\inputlib.ps1"; . "$PSScriptRoot\lib\maplib.ps1"
Add-Type @"
using System;using System.Runtime.InteropServices;
public class EM{ [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a,bool i,int p);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);}
"@
function Player-Entity([int]$procId) {
    $h = [EM]::OpenProcess(0x10, $false, $procId); if ($h -eq [IntPtr]::Zero) { return 0 }
    function rd32([int64]$a){$b=New-Object byte[] 4;$n=0;if([EM]::ReadProcessMemory($h,[IntPtr]$a,$b,4,[ref]$n)){[BitConverter]::ToInt32($b,0)}else{0}}
    $w = rd32 0x54a264; if (-not $w) { return 0 }
    $s = rd32 $w; if (-not $s) { return 0 }
    return (rd32 ($s + 0x70))
}

if (-not $NoLaunch) {
    Get-Process i76 -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
    Start-Sleep -Seconds 1
    Start-Process -FilePath (Join-Path $GameDir 'i76.exe') -ArgumentList '-glide' -WorkingDirectory $GameDir
    Start-Sleep -Seconds 8
}
$proc = Get-GamePid; if (-not $proc) { throw "game not running" }
if ($PSBoundParameters.ContainsKey('GameDir') -and -not (Test-ProcInDir $proc $GameDir)) { throw "the running game is $($proc.Path), not in -GameDir $GameDir" }
Force-Foreground $proc.MainWindowHandle | Out-Null

# 1) skip intro crawl -> main menu (tap a few times)
for ($i=0; $i -lt 6; $i++) { Force-Foreground $proc.MainWindowHandle|Out-Null; Send-Key $VK.ESC; Start-Sleep -Milliseconds 300; Send-Key $VK.ENTER; Start-Sleep -Milliseconds 800 }

if ($StopAtMainMenu) { Write-Host "Stopped at the MAIN MENU." -ForegroundColor Yellow; exit 0 }

# 2) MELEE -> AUTO MELEE -> INSTANT MELEE (OS-space path, keeps chain open)
Force-Foreground $proc.MainWindowHandle | Out-Null
[Inp]::SetCursorPos(450,300); Start-Sleep -Milliseconds 250
[Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 60;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)   # click MELEE
Start-Sleep -Milliseconds 600
[Inp]::SetCursorPos(450,300); Start-Sleep -Milliseconds 120
[Inp]::SetCursorPos(490,360); Start-Sleep -Milliseconds 250
[Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 60;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)   # click AUTO MELEE
Start-Sleep -Milliseconds 600
[Inp]::SetCursorPos(450,300); Start-Sleep -Milliseconds 100
[Inp]::SetCursorPos(490,360); Start-Sleep -Milliseconds 100
[Inp]::SetCursorPos(535,375); Start-Sleep -Milliseconds 250
[Inp]::mouse_event(0x2,0,0,0,[IntPtr]::Zero);Start-Sleep -Milliseconds 60;[Inp]::mouse_event(0x4,0,0,0,[IntPtr]::Zero)   # click INSTANT MELEE
Start-Sleep -Milliseconds 2500

if ($StopAtForm) { Write-Host "Stopped on the DRIVER ENTRY FORM." -ForegroundColor Yellow; exit 0 }

# 3) Driver Entry Form: pick the arena, set A.I. DRIVERS to 0, then ENTER AREA
Force-Foreground $proc.MainWindowHandle | Out-Null
if ($Area) {
    # AREA OF PLAY rows in UI (640x480) coordinates, read straight off a Capture-UI screenshot.
    # Terrain matters for physics tests: AirBase and SlickTrack are flat (no airtime at all),
    # Dunes/Crater/Tombstone have hills - use those for anything involving jumps or rotation.
    $areaY = @{ Crater = 157; Dunes = 174; AirBase = 191; Suburbia = 208; SlickTrack = 226; Tombstone = 242 }
    Click-UI 80 $areaY[$Area] 400
    Start-Sleep -Milliseconds 500
}
# A.I. DRIVERS [-] is UI (159,295) per lib/maplib.ps1. The old screen-space coordinate here was
# from a superseded (wrong) calibration and silently did nothing, so "empty" arenas still had an
# AI car in them - which collides with the player and corrupts any rotation/spin measurement.
if (-not $KeepAI) { Click-UI 159 295 400; Start-Sleep -Milliseconds 300 }
Click-Screen 1648 1385 500
Start-Sleep -Seconds 2

# 4) wait for in-mission
$deadline = (Get-Date).AddSeconds(20); $ent = 0
while ((Get-Date) -lt $deadline) {
    $ent = Player-Entity $proc.Id
    if ($ent -ne 0) { break }
    Start-Sleep -Milliseconds 500
}
if ($ent -ne 0) { Write-Host ("IN MISSION - player entity 0x{0:X}" -f $ent) -ForegroundColor Green; exit 0 }
else { Write-Host "Did not reach mission (menu nav may have drifted)." -ForegroundColor Red; exit 1 }
