@echo off
title I76 Debug: debug / cheat tool
REM I76 Debug - the debug / cheat tool for THIS folder's game: a dashboard in your browser (http://127.0.0.1:17690/) - fps and
REM physics steps, telemetry charts and a map, game events, force feedback, collision / terrain counters from the proxy log,
REM the log itself, and the TRAINER: repair, ammo, Play Options, teleport incl. the T05 hill top, freeze, and the FULL CAR
REM STATE: Store / Restore (and three waypoints) put the car back with its position, heading, pitch, roll, speed, spin,
REM suspension and engine, so a jump run-up replays from the same state. In the game: Ctrl+9 stores, Ctrl+0 restores.
REM Start the game with PLAY.bat first, then double-click this; it attaches on its own, re-trying every 2 s.
REM Changes are made in the running game's memory only - nothing on disk, saves untouched.
REM Code: _tools\debug (from i76-everywhere tools\debug; its README.md explains every tab). TRAINER.bat = this, on the Trainer tab.
REM Needs Python 3 (python.org). No packages to install.
REM     DEBUG.bat --tab trainer   open on a tab (overview telemetry events ffb rumble lfe motion collision terrain trainer log)
REM     DEBUG.bat --haptics       also start the haptics host (the Force feedback / Rumble / LFE / Motion tabs' data; dry run,
REM                               only when a wheel or pad is found); --haptics-live lets it drive the devices
REM     DEBUG.bat --no-attach     never open the game process (read-only panels only)
REM The telemetry charts need the game started with I76_TELEMETRY=1; the trainer, collision, terrain and log tabs do not.
REM CAMPAIGN: God mode / Unlimited ammo and the ammo/armour/chassis Play Options can mark a campaign as cheated -
REM see the campaign line on the Trainer tab ('Turn off cheater options' undoes it). Repair / refill / teleport / restore are safe.
setlocal
set "DBG=%~dp0_tools\debug\i76debug.py"
if not exist "%DBG%" (echo Missing %DBG% & pause & exit /b 1)
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%DBG%" --any %*
) else (
  python "%DBG%" --any %*
)
if errorlevel 1 (
  echo.
  echo I76 Debug exited with an error - is Python 3 installed and on the PATH? Is another I76 Debug already open
  echo ^(port 17690^)? Then use that one.
  pause
)
endlocal
