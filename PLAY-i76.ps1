# Interstate '76 / Nitro Pack launcher (Windows + dgVoodoo recipe).
#
# Presentation is owned by dgVoodoo (dgVoodoo.windows.conf): starts FULLSCREEN
# (aspect-correct stretched_ar), Alt+Enter toggles fullscreen/windowed, and
# dgVoodoo's emulated cursor keeps the mouse correct in both modes.
#
# This launcher just starts the game plus i76wheel.exe (mouse-wheel -> targeting
# keys: wheel up = Q frontal_target, wheel down = T target_nearest_enemy - the
# 1997 engine has no wheel tokens, see tools/i76wheel.c) and cleans it up when
# the game exits.
#
# Usage: PLAY-i76.ps1 [-GameDir "C:\Games\Interstate 76"] [-Exe i76.exe]
param(
    [string]$GameDir = "C:\Games\Interstate 76",
    [string]$Exe = "i76.exe",
    # Frame generation. Pass "" to skip it. Steam does NOT need to be running.
    [string]$LosslessScaling = "C:\Program Files (x86)\Steam\steamapps\common\Lossless Scaling\LosslessScaling.exe"
)
$ErrorActionPreference = 'SilentlyContinue'

$wheel = $null
if (Test-Path (Join-Path $GameDir 'i76wheel.exe')) {
    $wheel = Start-Process -FilePath (Join-Path $GameDir 'i76wheel.exe') -PassThru
}

# The XInput/shift-layer controller scheme (i76-remap.ahk): AutoHotkey inside the
# game folder emits the engine's stock keys for triggers, the LB shift layer,
# look-back fire, camera cycle and rumble. Started with the game and killed on
# exit (same lifetime model the Mac launcher and i76-with-remap.bat use), so its
# global hotkeys only live during a play session. Connect the pad BEFORE launch.
$ahk = $null
$ahkExe = Join-Path $GameDir '_ahk\AutoHotkeyU32.exe'
$ahkCfg = Join-Path $GameDir '_ahk\i76-remap.ahk'
if ((Test-Path $ahkExe) -and (Test-Path $ahkCfg)) {
    $ahk = Start-Process -FilePath $ahkExe -ArgumentList "`"$ahkCfg`"" -WorkingDirectory (Join-Path $GameDir '_ahk') -PassThru
}

# Frame generation (Lossless Scaling), optional. The engine's physics are locked
# at 20 FPS and break above ~25 (docs/STEAMDECK.md sec 5), so the ONLY way to a
# smoother picture is interpolating display frames on top - which is exactly what
# LSFG does. VERIFIED 2026-08-01: Lossless Scaling has NO Steam dependency -
# launched directly it loads zero steam_api/steamclient/overlay modules and
# nothing from outside its own folder, so Steam never has to be running.
# The "Interstate '76 Gold Edition" profile in
# %LOCALAPPDATA%\Lossless Scaling\Settings.xml has AutoScale=true + a 2x fixed
# multiplier, so it engages on its own when the game window appears - no hotkey.
# Set ForceVerticalSync=false in dgVoodoo.conf so LS owns presentation.
# We only stop it if WE started it (don't kill a session the user already had up).
$ls = $null
if ($LosslessScaling -and (Test-Path $LosslessScaling)) {
    if (-not (Get-Process -Name 'LosslessScaling' -ErrorAction SilentlyContinue)) {
        $ls = Start-Process -FilePath $LosslessScaling -PassThru
        Start-Sleep -Seconds 2   # let it register its window hook before the game appears
    }
}

$proc = Start-Process -FilePath (Join-Path $GameDir $Exe) -ArgumentList '-glide' -WorkingDirectory $GameDir -PassThru
$proc.WaitForExit()

if ($wheel -and -not $wheel.HasExited) { Stop-Process -Id $wheel.Id -Force }
if ($ahk   -and -not $ahk.HasExited)   { Stop-Process -Id $ahk.Id   -Force }
if ($ls    -and -not $ls.HasExited)    { Stop-Process -Id $ls.Id    -Force }
