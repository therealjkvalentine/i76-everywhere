@echo off
REM Interstate '76 daily driver, EXTRA option: widescreen 21:9, 120 fps, detail trimmed where it costs and shows least
REM (preset best-wide-balanced, see "Interstate 76\presets"). PLAY.bat (best-wide) stays the default.
REM Run at the physical console, never over Remote Desktop. Plug the wheel/pad in first.
REM --legacy-multiplayer (also --legacy_multiplayer): multiplayer the old way for this launch, the stock MODEM / IPX / INTERNET /
REM NULLMODEM row under MULTI MELEE > HOST / JOIN (PLAY-i76.ps1 -LegacyMultiplayer = proxy I76_MP_MENU=0).
setlocal
set "HERE=%~dp0"
set "LEGACY="
:args
if "%~1"=="" goto :argsdone
if /i "%~1"=="--legacy-multiplayer" (set "LEGACY= -LegacyMultiplayer" & shift & goto :args)
if /i "%~1"=="--legacy_multiplayer" (set "LEGACY= -LegacyMultiplayer" & shift & goto :args)
if /i "%~1"=="-LegacyMultiplayer" (set "LEGACY= -LegacyMultiplayer" & shift & goto :args)
shift
goto :args
:argsdone
copy /y "%HERE%Interstate 76\dgVoodoo.wide.conf" "%HERE%Interstate 76\dgVoodoo.conf" >nul
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%HERE%Interstate 76\PLAY-i76.ps1" -GameDir "%HERE%Interstate 76" -Exe i76.exe -Preset best-wide-balanced -LosslessScaling none%LEGACY%
