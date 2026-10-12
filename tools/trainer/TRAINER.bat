@echo off
REM Interstate '76 trainer - now part of I76 Debug (tools\debug): this opens the debug dashboard on its Trainer tab, with
REM every control of the old window (repair, ammo, Play Options, teleport incl. the T05 hill top, waypoints, freeze).
REM
REM Start the game first (the SANDBOX copy, C:\Users\james\i76-uncap-lab\game - the daily driver is refused unless you
REM tick 'allow non-sandbox game' on the Trainer tab, or pass --any). It attaches on its own, re-trying every 2 s, and
REM uses the Strlkup proxy's control block when the game runs with the proxy, direct memory pokes otherwise.
REM tools\debug\README.md and README-GUI.md (this folder) explain every control.
REM
REM Needs Python 3. No packages to install.
REM     TRAINER.bat --any         start with the non-sandbox box ticked
REM     TRAINER.bat --classic     the old tkinter window (i76trainer_gui.py) instead
REM     TRAINER.bat --selftest    the old window's self-test (parse the headers, round-trip a request, no game needed)
REM
REM CAMPAIGN: Play Options ammo/armour/chassis (and, on a proxy without the 'cheat-marker guard 4/4' log line,
REM God mode / Unlimited ammo left ticked through an Esc-menu close or a mission end) make the game mark itself
REM as cheated: won missions then do NOT advance. Repair / refill / teleport / freeze are safe. Fix: the
REM 'Turn off cheater options' button, or the game's own 'Turn off Cheater Options', then win the mission again.
REM NOTE: the classic window maps the telemetry shared memory at the old v2 size; while it is open a v3 proxy cannot
REM use its shared memory (UDP still works). The debug dashboard never creates that mapping.

setlocal
cd /d "%~dp0"
set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
set "CLASSIC="
for %%A in (%*) do (
  if /I "%%~A"=="--classic" set "CLASSIC=1"
  if /I "%%~A"=="--selftest" set "CLASSIC=1"
)
if defined CLASSIC goto classic
%PY% "%~dp0..\debug\i76debug.py" --tab trainer %*
goto done
:classic
set "ARGS=%*"
set "ARGS=%ARGS:--classic=%"
%PY% "%~dp0i76trainer_gui.py" %ARGS%
:done
if errorlevel 1 (
  echo.
  echo ---------------------------------------------------------------
  echo The trainer exited with an error. Common causes:
  echo   * no Python 3 on the PATH - install it from python.org
  echo   * tools\telemetry\i76tel.h or tools\trainer\i76trn.h is missing
  echo   * port 17690 in use: I76 Debug is already running - use its Trainer tab
  echo ---------------------------------------------------------------
  pause
)
endlocal
