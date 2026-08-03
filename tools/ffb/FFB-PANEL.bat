@echo off
REM Interstate '76 custom force feedback - live panel.
REM
REM Double-click this while the game is running. It waits for a mission to load
REM on its own, so it does not matter whether you start it before or after.
REM
REM Keys once running:  [space] mute   [+/-] master gain   [s] save tune   [q] quit
REM
REM FIRST TIME: run FFB-CALIBRATE.bat first. Until you do, the force model is
REM guessing the steering lock and the yaw-rate sign, and a wrong sign makes the
REM wheel help you turn INTO corners.
REM
REM Not sure / want to look before it touches the wheel:
REM     powershell -ExecutionPolicy Bypass -File ffb-interposer.ps1 -DryRun

setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ffb-interposer.ps1" %*
if errorlevel 1 (
  echo.
  echo ---------------------------------------------------------------
  echo It exited with an error. Common causes:
  echo   * the game is not running, or is not in a mission
  echo   * the Thrustmaster control panel is open - it takes the wheel
  echo     exclusively. Close it and try again.
  echo   * the wheel is not connected, or needs a power cycle
  echo ---------------------------------------------------------------
  pause
)
endlocal
