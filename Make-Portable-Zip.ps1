<#
  Pack a fully-configured Interstate '76 install into ONE portable zip you can
  carry between your own PCs. Unzip anywhere on the new machine and double-click
  PLAY.bat - no reinstall, no GOG installer, no registry needed. dgVoodoo is
  drop-in and every config (dgVoodoo.conf, input.map, PLAY-i76.bat) is
  folder-relative, so the folder is location-independent.

  NOTE: the zip contains YOUR game files (copyrighted). It's for moving between
  computers you own - don't redistribute it. (The scripts in this repo are the
  only thing meant to be shared; those carry no game bytes.)

  Usage:
    ./Make-Portable-Zip.ps1                         # auto-detect the game, zip to Desktop
    ./Make-Portable-Zip.ps1 -GameDir "C:\Games\Interstate 76"
    ./Make-Portable-Zip.ps1 -OutDir "D:\" -IncludeSaves
#>
param(
    [string]$GameDir = "",
    [string]$OutDir  = "",
    [switch]$IncludeSaves,   # include your savegames in the portable zip
    [switch]$IncludeFrameGen,# bundle Lossless Scaling too (your licence, your PCs only)
    [switch]$IncludeHeadTrack,# bundle opentrack + the head-tracking scripts (opentrack is GPL)
    [switch]$Yes
)
$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
function Say($m,$c='Cyan'){ Write-Host $m -ForegroundColor $c }

Say "`n=== Make a portable Interstate '76 zip ===`n" 'Green'

# --- locate a configured install --------------------------------------------
if (-not $GameDir) {
    $cands = @()
    foreach ($k in 'HKLM:\SOFTWARE\WOW6432Node\GOG.com\Games','HKLM:\SOFTWARE\GOG.com\Games') {
        if (Test-Path $k) { Get-ChildItem $k | ForEach-Object {
            $g = Get-ItemProperty $_.PSPath
            if ($g.gameName -match 'Interstate') { $cands += $g.path }
        } }
    }
    $cands += 'C:\Games\Interstate 76','C:\GOG Games\Interstate 76',"$env:USERPROFILE\Interstate 76"
    $GameDir = $cands | Where-Object { Test-Path (Join-Path $_ 'i76.exe') } | Select-Object -First 1
}
if (-not $GameDir -or -not (Test-Path (Join-Path $GameDir 'i76.exe'))) {
    Say "No Interstate '76 install found. Point me at it: -GameDir `"C:\Games\Interstate 76`"" 'Red'; exit 1
}
if (-not (Test-Path (Join-Path $GameDir 'dgVoodoo.conf'))) {
    Say "That folder isn't configured yet (no dgVoodoo.conf)." 'Yellow'
    Say "Run Setup-From-GOG.ps1 (or install.ps1) first, then re-run this." 'Yellow'
    exit 1
}
if (-not $OutDir) { $OutDir = [Environment]::GetFolderPath('Desktop') }
Say "Source install : $GameDir" 'Green'

# --- stage a clean copy ------------------------------------------------------
$stamp = Get-Date -Format 'yyyyMMdd'
$bundleName = "Interstate76-i76-everywhere-portable-$stamp"
$staging = Join-Path $env:TEMP $bundleName
$gameOut = Join-Path $staging "Interstate 76"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Force $gameOut | Out-Null

# Exclude machine-noise: backups the tools leave, the retired OpenGLide DLLs,
# and (unless asked) your saves. Everything else - game + dgVoodoo + configs -
# travels as-is so the target just runs it.
$exclude = @('*.pre-*','*.stock-backup','*.gog-original','*.bak-*','*.pre-edit')
$excludeDirs = @('_openglide-backup')
if (-not $IncludeSaves) { $excludeDirs += @('savegame','SAVEGAME','saves') }

Say "Staging a clean copy (this can take a minute for a few hundred MB) ..."
robocopy $GameDir $gameOut /E /NFL /NDL /NJH /NJS /NP `
    /XF @exclude /XD @excludeDirs | Out-Null
if ($LASTEXITCODE -ge 8) { Say "robocopy failed ($LASTEXITCODE)." 'Red'; exit 1 }

# --- drop portable helpers into the bundle -----------------------------------
# PLAY.bat at the top so it's the obvious thing to double-click.
Set-Content (Join-Path $staging 'PLAY.bat') @'
@echo off
REM Portable Interstate '76 - just runs the game in place. No install needed.
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden ^
  -File "%~dp0Interstate 76\PLAY-i76.ps1" -GameDir "%~dp0Interstate 76" -Exe i76.exe
'@ -Encoding ascii

# One-time-per-machine niceties: desktop shortcut + (optional) force feedback.
Set-Content (Join-Path $staging 'Setup-This-PC.bat') @'
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-This-PC.ps1"
pause
'@ -Encoding ascii

Set-Content (Join-Path $staging 'Setup-This-PC.ps1') @'
# Make a Desktop shortcut pointing at THIS unzipped folder, and offer force feedback.
$here = $PSScriptRoot
$game = Join-Path $here 'Interstate 76'
$bat  = Join-Path $here 'PLAY.bat'
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) "Interstate '76.lnk"))
$lnk.TargetPath = $bat
$lnk.WorkingDirectory = $here
$lnk.IconLocation = "$(Join-Path $game 'i76.exe'),0"
$lnk.Save()
Write-Host "Desktop shortcut created -> $bat" -ForegroundColor Green
$ff = Join-Path $game 'enable-force-feedback.bat'
if (Test-Path $ff) {
    Write-Host "`nForce feedback (wheels/FFB sticks) needs a one-time registry write as Administrator."
    Write-Host "To enable it: right-click `"$ff`" -> Run as administrator."
}
Write-Host "`nDone. Double-click PLAY.bat (or the desktop shortcut) to play." -ForegroundColor Green
'@ -Encoding ascii

# carry the FFB enabler + the standalone browser save editor along for convenience
Copy-Item (Join-Path $repo 'enable-force-feedback.bat') $gameOut -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $repo 'i76-save-editor.html') $staging -Force -ErrorAction SilentlyContinue

# Refresh the launcher from the repo. The installed copy in the game folder can
# predate repo changes (it did on 2026-08-01 - the bundle shipped a PLAY-i76.ps1
# with no -LosslessScaling support), and the bundle should carry the current one.
Copy-Item (Join-Path $repo 'PLAY-i76.ps1') $gameOut -Force -ErrorAction SilentlyContinue

# --- optional: bundle Lossless Scaling (frame generation) --------------------
# It has NO Steam dependency (docs/WINDOWS-PLAYBOOK.md sec 2), so it runs from
# the unzipped folder on any of your PCs. It is a PAID app - your licence, your
# machines only. Installing it from Steam on the target is the cleaner route
# (you get updates); this switch exists for offline/one-carry moves.
if ($IncludeFrameGen) {
    $lsExe = $null
    $roots = @("${env:ProgramFiles(x86)}\Steam")
    $vdf = "${env:ProgramFiles(x86)}\Steam\steamapps\libraryfolders.vdf"
    if (Test-Path $vdf) {
        foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) {
            $roots += $m.Groups[1].Value -replace '\\\\', '\'
        }
    }
    foreach ($r in ($roots | Select-Object -Unique)) {
        $p = Join-Path $r 'steamapps\common\Lossless Scaling'
        if (Test-Path (Join-Path $p 'LosslessScaling.exe')) { $lsExe = $p; break }
    }
    if (-not $lsExe) {
        Say "-IncludeFrameGen: Lossless Scaling not found in any Steam library - skipping." 'Yellow'
    } else {
        Say "Staging Lossless Scaling from $lsExe ..."
        robocopy $lsExe (Join-Path $staging 'Lossless Scaling') /E /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { Say "robocopy of Lossless Scaling failed ($LASTEXITCODE)." 'Red'; exit 1 }
        Copy-Item (Join-Path $repo 'Setup-FrameGen.ps1') $staging -Force -ErrorAction SilentlyContinue
        Set-Content (Join-Path $staging 'PLAY-with-FrameGen.bat') @'
@echo off
REM Portable Interstate '76 + frame generation. Steam is NOT required - Lossless
REM Scaling is bundled beside this file and has no Steam dependency.
REM ONE-TIME PER PC: right-click Setup-FrameGen.ps1 -> Run with PowerShell, to add
REM the auto-scale profile. Without it, focus the game and press Ctrl+Alt+S.
REM The 20 FPS physics base is NEVER raised - these are interpolated DISPLAY
REM frames only. Raising FPSLimit breaks the Mission 5 canyon jump.
start "" "%~dp0Lossless Scaling\LosslessScaling.exe"
timeout /t 3 /nobreak >nul
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Interstate 76\PLAY-i76.ps1" -GameDir "%~dp0Interstate 76" -Exe i76.exe
'@ -Encoding ascii
        Say "Frame generation bundled (Lossless Scaling + Setup-FrameGen.ps1 + launcher)." 'Green'
    }
}

# --- optional: bundle opentrack (head tracking) ------------------------------
# opentrack is GPL and freely redistributable, so unlike Lossless Scaling this
# carries no licence caveat. What matters is the CONFIG: the script reads
# opentrack's freetrack shared memory, so the bundled profile must have
# protocol-dll=freetrack, not the vjoy default. We ship a profile that is already
# set that way, so a target PC needs only "Start".
if ($IncludeHeadTrack) {
    $otSrc = $null
    foreach ($p in "${env:ProgramFiles(x86)}\opentrack", "$env:ProgramFiles\opentrack") {
        if (Test-Path (Join-Path $p 'opentrack.exe')) { $otSrc = $p; break }
    }
    if (-not $otSrc) {
        Say "-IncludeHeadTrack: opentrack not installed - skipping." 'Yellow'
    } else {
        Say "Staging opentrack from $otSrc ..."
        robocopy $otSrc (Join-Path $staging 'opentrack') /E /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { Say "robocopy of opentrack failed ($LASTEXITCODE)." 'Red'; exit 1 }

        # carry the live profile, forced to the freetrack output the script needs
        $cfgDir = Join-Path $staging 'opentrack-profile'
        New-Item -ItemType Directory -Force $cfgDir | Out-Null
        $ini = Get-ChildItem "$env:USERPROFILE\Documents\opentrack-2.3" -Filter '*.ini' -ErrorAction SilentlyContinue |
               Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($ini) {
            (Get-Content $ini.FullName) -replace '^protocol-dll=.*', 'protocol-dll=freetrack' |
                Set-Content (Join-Path $cfgDir $ini.Name) -Encoding utf8
            Say "  profile $($ini.Name) staged (output forced to freetrack)."
        } else {
            Say "  no opentrack profile found - set Output = freetrack 2.0 Enhanced by hand on the target PC." 'Yellow'
        }

        Copy-Item (Join-Path $repo 'i76-headtrack.ahk')      (Join-Path $gameOut '_ahk') -Force -ErrorAction SilentlyContinue
        Copy-Item (Join-Path $repo 'i76-headtrack-test.ahk') (Join-Path $gameOut '_ahk') -Force -ErrorAction SilentlyContinue
        # Every AHK layer is enumerated BY NAME here, so one added to the repo and
        # not added to this list simply never ships. That is how _ahk\i76-remap.ahk
        # stayed three weeks stale while the repo copy grew an entire wheel layer
        # that consequently never ran. Add new layers here.
        Copy-Item (Join-Path $repo 'i76-fighterstick.ahk')   (Join-Path $gameOut '_ahk') -Force -ErrorAction SilentlyContinue

        Set-Content (Join-Path $staging 'HEADTRACK.bat') @'
@echo off
REM Interstate '76 head tracking (opentrack -> freetrack shared memory).
REM ONE-TIME PER PC: copy opentrack-profile\*.ini into
REM   %USERPROFILE%\Documents\opentrack-2.3\
REM so the Output is already "freetrack 2.0 Enhanced" - the script reads that,
REM NOT the vjoy output opentrack ships with by default.
REM Then: start opentrack, press Start, run this, focus the game.
REM   Ctrl+Alt+H  digital <-> analog       Ctrl+Alt+[ ]  yaw sensitivity
REM   Ctrl+Alt+- =  pitch sensitivity      Ctrl+Alt+L    log telemetry
start "" "%~dp0opentrack\opentrack.exe"
start "" "%~dp0Interstate 76\_ahk\AutoHotkeyU32.exe" "%~dp0Interstate 76\_ahk\i76-headtrack.ahk"
'@ -Encoding ascii
        Set-Content (Join-Path $staging 'HEADTRACK-TEST.bat') @'
@echo off
REM Live diagnostic window for the head-tracking chain - shows whether
REM FT_SharedMem is present, whether yaw is moving, whether the thresholds trip,
REM and whether the GAME WINDOW IS ACTIVE (the usual reason "nothing happens").
REM Sends no keys unless you tick the box.
start "" "%~dp0Interstate 76\_ahk\AutoHotkeyU32.exe" "%~dp0Interstate 76\_ahk\i76-headtrack-test.ahk"
'@ -Encoding ascii
        Say "Head tracking bundled (opentrack + profile + scripts + launchers)." 'Green'
    }
}

Set-Content (Join-Path $staging 'READ-ME-FIRST.txt') @"
Interstate '76 - portable (i76-everywhere)
==========================================

This is a COMPLETE, already-configured Interstate '76: unzip it anywhere on any
of your Windows PCs and play. No installer, no GOG, no registry required.

TO PLAY
  1. Unzip this folder somewhere (e.g. C:\Games\).
  2. Double-click  PLAY.bat
  (First boot shows ~60-75s of 'PLEASE STAND BY' - press ESC to skip the intro.)

OPTIONAL, per machine
  * Setup-This-PC.bat  - makes a Desktop shortcut for this copy.
  * Force feedback     - right-click 'Interstate 76\enable-force-feedback.bat'
                         -> Run as administrator (one-time HKLM write).
  * i76-save-editor.html - open in any browser to edit your saves (runs locally).

WHAT'S BAKED IN
  * dgVoodoo (20 FPS physics cap so scene 5's ramp jump works, sharp Voodoo look, MSAA)
  * Corrected input.map (mouse driving + gamepad: joystick1, glance hat, e-brake...)
  * The cutscene-music fix (if it was built) and the mouse-wheel targeting helper.

Connect your controller BEFORE launching - the 1997 engine enumerates joysticks
only at startup. These are YOUR game files; keep this zip to your own machines.
"@ -Encoding ascii

# --- zip it ------------------------------------------------------------------
$zipPath = Join-Path $OutDir "$bundleName.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Say "`nCompressing -> $zipPath ..."
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zipPath -CompressionLevel Optimal
$sizeMB = [math]::Round((Get-Item $zipPath).Length/1MB,1)
Remove-Item $staging -Recurse -Force

Say "`n=== DONE ===" 'Green'
Say "Portable zip: $zipPath  ($sizeMB MB)" 'Green'
Say "Copy it to another PC, unzip, double-click PLAY.bat. That's the whole move."
$global:LASTEXITCODE = 0
exit 0
