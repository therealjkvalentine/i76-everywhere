@echo off
title I76 FFB panel
REM The FFB / LFE tuning page in your browser: http://127.0.0.1:17691/
REM
REM Live telemetry, every force-feedback channel as a meter with solo / mute, the gains as sliders (they write
REM ffb-tune-owner.json here and the running interposer picks the change up within half a second), the event log
REM (shots, hits, landings, ignition, gear, surface), the "things we want noticeable" checklist (each verdict is saved
REM to notes\ffb-notes-<time>.csv), and the bass-shaker (LFE) bus with the game's music / voice levels read-only.
REM
REM Start the game with the wheel first (PLAY.bat starts the interposer when a wheel is attached; PLAY.bat --panel
REM also opens this page). This window only serves the page: closing it does not touch the wheel. The interposer's
REM own console panel stays the fallback.
REM Needs Python 3 (python.org), no packages. Run at the physical console. Options: --no-browser  --http-port N
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0ffb-panel.py" %*
) else (
  python "%~dp0ffb-panel.py" %*
)
if errorlevel 1 (
  echo.
  echo ---------------------------------------------------------------
  echo The FFB panel exited with an error. Common causes:
  echo   * no Python 3 on the PATH - install it from python.org
  echo   * UDP port 17682 is taken by another program
  echo ---------------------------------------------------------------
  pause
)
endlocal
