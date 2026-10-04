@echo off
REM EXPERIMENT.bat - the LAB TWIN of the daily driver (same game, controls, wheel/stick/pad layers, head look),
REM with the newest proxy and the experimental switches. Saves here are a COPY: progress made here stays here.
REM Run at the physical console. Plug the wheel/pad in first.
echo.
echo  Detail distance:
echo    1 = off (same as the daily driver)
echo    2 = terrain shape x8          3 = terrain shape x16
echo    4 = terrain x8  + sharp ground textures + detailed objects 8x farther
echo    5 = terrain x16 + sharp ground textures + detailed objects 8x farther
choice /c 12345 /n /m " Detail? [1-5] "
if errorlevel 5 (set PRESET=exp-detail-16) else if errorlevel 4 (set PRESET=exp-detail-8) else if errorlevel 3 (set PRESET=exp-terrain-16) else if errorlevel 2 (set PRESET=exp-terrain-8) else (set PRESET=best-120)
echo.
echo  Picture shape (the game renders 4:3; wider = more stretched):
echo    1 = 16:10 (daily driver)   2 = 14:9   3 = 3:2   4 = 4:3 (unstretched)
echo    5 = WIDESCREEN 21:9 EXPERIMENT (wider view, not stretched; menus and HUD text look stretched)
set I76_ASPECT=
choice /c 12345 /n /m " Shape? [1-5] "
if errorlevel 5 (set ASPECT=wide& set I76_ASPECT=3440x1440) else if errorlevel 4 (set ASPECT=4x3) else if errorlevel 3 (set ASPECT=3x2) else if errorlevel 2 (set ASPECT=14x9) else (set ASPECT=16x10)
copy /y "%~dp0Interstate 76\dgVoodoo.aspect-%ASPECT%.conf" "%~dp0Interstate 76\dgVoodoo.conf" >nul
echo.
echo  Starting: preset %PRESET%, shape %ASPECT%
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Interstate 76\PLAY-i76.ps1" -GameDir "%~dp0Interstate 76" -Exe i76.exe -Preset %PRESET% -LosslessScaling none
