@echo off
REM Interstate '76 trainer window for THIS folder's game (repair, ammo, play-option cheats, teleport, waypoints).
REM Start the game with PLAY.bat first, then double-click this; it attaches on its own, re-trying every 2 s.
REM Changes are made in the running game's memory only - nothing on disk, saves untouched.
REM Code: _tools\trainer (from i76-everywhere tools\trainer; README-GUI.md there explains every control).
REM Needs Python 3 with tkinter (python.org build, 'tcl/tk' ticked). No packages to install.
setlocal
set "TR=%~dp0_tools\trainer\i76trainer_gui.py"
if not exist "%TR%" (echo Missing %TR% & pause & exit /b 1)
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%TR%" --any %*
) else (
  python "%TR%" --any %*
)
if errorlevel 1 (
  echo.
  echo The trainer exited with an error - is Python 3 with tcl/tk installed and on the PATH?
  pause
)
endlocal
