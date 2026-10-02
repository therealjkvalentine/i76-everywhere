@echo off
REM Interstate '76 trainer window (tools\trainer\i76trainer_gui.py).
REM
REM Start the game first (the SANDBOX copy, C:\Users\james\i76-uncap-lab\game - the daily driver is refused
REM unless you tick 'allow non-sandbox game' in the window), then double-click this. It attaches on its own,
REM re-trying every 2 s, and uses the Strlkup proxy's control block when the game runs with the proxy,
REM direct memory pokes otherwise. README-GUI.md explains every control.
REM
REM Needs Python 3 with tkinter (the stock python.org / Store build has it). No packages to install.
REM     TRAINER.bat --selftest    parse the headers and round-trip a request, no game needed
REM     TRAINER.bat --any         start with the non-sandbox box ticked

setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0i76trainer_gui.py" %*
) else (
  python "%~dp0i76trainer_gui.py" %*
)
if errorlevel 1 (
  echo.
  echo ---------------------------------------------------------------
  echo The trainer exited with an error. Common causes:
  echo   * no Python 3 on the PATH (install from python.org, tick 'tcl/tk')
  echo   * tools\telemetry\i76tel.h or tools\trainer\i76trn.h is missing
  echo ---------------------------------------------------------------
  pause
)
endlocal
