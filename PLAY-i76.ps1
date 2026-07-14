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
    [string]$Exe = "i76.exe"
)
$ErrorActionPreference = 'SilentlyContinue'

$wheel = $null
if (Test-Path (Join-Path $GameDir 'i76wheel.exe')) {
    $wheel = Start-Process -FilePath (Join-Path $GameDir 'i76wheel.exe') -PassThru
}

$proc = Start-Process -FilePath (Join-Path $GameDir $Exe) -ArgumentList '-glide' -WorkingDirectory $GameDir -PassThru
$proc.WaitForExit()

if ($wheel -and -not $wheel.HasExited) { Stop-Process -Id $wheel.Id -Force }
