@echo off
REM PLAY-LOGGED.bat - play the LAB TWIN of the daily driver with the physics / memory logger running.
REM
REM One double-click: opens I76 Debug (browser dashboard, Trainer tab) with the logger armed, then starts the game exactly
REM like the twin's PLAY.bat (widescreen, preset best-wide) plus I76_TELEMETRY=1, which the logger reads.
REM   * Every mission is logged on its own: a new log starts when your car appears and stops 3 s after it is gone.
REM   * Scroll Lock          = MARK (drop a numbered marker into the log: "that jump felt wrong", "flipped here").
REM   * Shift + Scroll Lock  = stop / start the logger by hand. The Log / Mark buttons at the top of the dashboard do the same.
REM   * Logs: <lab>\captures\trainer-log\<date-time>-best-wide\s01, s02 ... (one per mission), with
REM     summary.md beside them (jumps, landings, turn-overs, wrecks, Arcade Phys. check, frame rate and physics steps).
REM Run at the physical console, not over Remote Desktop. Close the dashboard's console window when you are done.
REM
REM     PLAY-LOGGED.bat [preset] [game folder]    defaults: best-wide, the lab twin game-dd-20261003\Interstate 76
REM This file lives in i76-everywhere tools\debug; the twin's TEST-logged-play.bat calls it. Nothing here touches the
REM daily driver.
setlocal
set "PRESET=%~1"
if "%PRESET%"=="" set "PRESET=best-wide"
set "GAMEDIR=%~2"
if "%GAMEDIR%"=="" set "GAMEDIR=%USERPROFILE%\i76-uncap-lab\game-dd-20261003\Interstate 76"
set "DBG=%~dp0i76debug.py"
echo %GAMEDIR% | findstr /I /L /C:"Interstate76-" /C:"Downloads" >nul
if not errorlevel 1 (echo Refusing %GAMEDIR%: that is a playable install, not a lab copy. & pause & exit /b 1)
if not exist "%GAMEDIR%\i76.exe" (echo No i76.exe in %GAMEDIR% & pause & exit /b 1)
if not exist "%DBG%" (echo Missing %DBG% & pause & exit /b 1)
set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"

REM 1. the dashboard + logger (its own minimised console window; --any: the trainer may attach to this lab copy)
start "I76 Debug + logger" /min %PY% "%DBG%" --any --tab trainer --log-auto --hotkeys --log-label %PRESET%
timeout /t 2 /nobreak >nul

REM 2. the game, as the twin's PLAY.bat, with the telemetry export on (the game inherits this variable)
set "I76_TELEMETRY=1"
if exist "%GAMEDIR%\dgVoodoo.wide.conf" copy /y "%GAMEDIR%\dgVoodoo.wide.conf" "%GAMEDIR%\dgVoodoo.conf" >nul
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%GAMEDIR%\PLAY-i76.ps1" -GameDir "%GAMEDIR%" -Exe i76.exe -Preset %PRESET% -LosslessScaling none
endlocal
