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
    [switch]$WithHDTextures, # build the HD pack once now, so the zip is HD on every target PC
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

# --- optional: bake the HD texture pack in (build ONCE here, ships to every PC) ---
# The pack lands in <game>\ADDON and robocopy carries it into the zip, so target
# machines get HD textures with no Python/GPU/40-min build. Run in a child process
# so install.ps1's prereq checks can't abort this packager.
if ($WithHDTextures) {
    Say "`nBuilding the HD texture pack into the source install (once, ~40 min, uses your GPU) ..." 'Cyan'
    $p = Start-Process powershell -Wait -PassThru -NoNewWindow -ArgumentList @(
        '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'install.ps1'),
        '-GameDir',"`"$GameDir`"",'-WithHDTextures','-Yes')
    if ($p.ExitCode -ne 0) {
        Say "HD build didn't complete (exit $($p.ExitCode)) - see messages above. Zipping WITHOUT HD." 'Yellow'
        Say "(Needs Python 3 + a GPU on THIS machine; the pack is built from your own I76.ZFS.)" 'Yellow'
    } else {
        Say "HD pack built into $GameDir\ADDON - baking it into the zip." 'Green'
    }
}

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
