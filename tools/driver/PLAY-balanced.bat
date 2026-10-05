@echo off
REM Interstate '76 daily driver, EXTRA option: widescreen 21:9, 120 fps, detail trimmed where it costs and shows least
REM (preset best-wide-balanced, see "Interstate 76\presets"). PLAY.bat (best-wide) stays the default.
REM Run at the physical console, never over Remote Desktop. Plug the wheel/pad in first.
copy /y "%~dp0Interstate 76\dgVoodoo.wide.conf" "%~dp0Interstate 76\dgVoodoo.conf" >nul
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Interstate 76\PLAY-i76.ps1" -GameDir "%~dp0Interstate 76" -Exe i76.exe -Preset best-wide-balanced -LosslessScaling none
