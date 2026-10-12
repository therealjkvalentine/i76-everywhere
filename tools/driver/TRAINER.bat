@echo off
REM Interstate '76 trainer for THIS folder's game (repair, ammo, play-option cheats, teleport, waypoints): since
REM 2026-10-12 it is the Trainer tab of I76 Debug (DEBUG.bat), opened on that tab. TRAINER.bat --classic = the old window.
REM Start the game with PLAY.bat first, then double-click this; it attaches on its own, re-trying every 2 s.
REM Changes are made in the running game's memory only - nothing on disk, saves untouched.
REM Code: _tools\debug and _tools\trainer (from i76-everywhere tools\; README.md / README-GUI.md there explain every control).
REM Needs Python 3 (python.org). No packages to install.
setlocal
set "DBG=%~dp0_tools\debug\i76debug.py"
set "TR=%~dp0_tools\trainer\i76trainer_gui.py"
set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
set "CLASSIC="
for %%A in (%*) do if /I "%%~A"=="--classic" set "CLASSIC=1"
if defined CLASSIC goto classic
if not exist "%DBG%" (echo Missing %DBG% & pause & exit /b 1)
%PY% "%DBG%" --any --tab trainer %*
goto done
:classic
if not exist "%TR%" (echo Missing %TR% & pause & exit /b 1)
%PY% "%TR%" --any
:done
if errorlevel 1 (
  echo.
  echo The trainer exited with an error - is Python 3 ^(with tcl/tk for --classic^) installed and on the PATH?
  echo Is I76 Debug already open ^(port 17690^)? Then use its Trainer tab.
  pause
)
endlocal
