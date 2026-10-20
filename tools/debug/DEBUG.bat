@echo off
title I76 Debug: debug / cheat tool
REM I76 Debug, the debug / cheat tool - a dashboard in your browser of everything going on while Interstate '76 runs: fps and physics steps,
REM live telemetry charts and a map, game events, force feedback, rumble, the bass shakers (LFE), motion output,
REM collision and terrain counters from the proxy log, the trainer, and the log itself. README.md explains each tab.
REM
REM Start the game (with I76_TELEMETRY on), then double-click this. It serves http://127.0.0.1:17690/ and opens it.
REM Needs Python 3 (python.org). No packages to install. Nothing here opens a device or plays sound (only a haptics
REM host started with "drive the devices" / --haptics-live does).
REM     DEBUG.bat --any               trainer may attach to a game that is not the lab sandbox copy
REM     DEBUG.bat --haptics           also start the haptics host (tools\haptics; dry run, only when a wheel or pad is
REM                                   found): the Force feedback / Rumble / LFE / Motion tabs fill in; --haptics-live drives the
REM                                   devices. The Haptics tabs have the same button.
REM     DEBUG.bat --tee 17676         forward telemetry to 17676 for a haptics host started by hand:
REM                                   tools\haptics\haptics.ps1 live --source udp --port 17676 --debug-udp
REM     DEBUG.bat --tab trainer       open on a tab (overview telemetry events ffb rumble lfe motion collision terrain trainer log)
REM     DEBUG.bat --no-attach         never open the game process (read-only panels only)
REM
REM Trainer: full car state - Store / Restore / waypoints put back position, heading, pitch, roll, speed, spin, suspension
REM and engine; in the game Ctrl+9 stores and Ctrl+0 restores. TRAINER.bat = DEBUG.bat --tab trainer.
REM CAMPAIGN: the Trainer tab has the same rules as the old trainer window - see its campaign line before ticking
REM God mode / Unlimited ammo or setting ammo/armour/chassis Play Options in a campaign.

setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0i76debug.py" %*
) else (
  python "%~dp0i76debug.py" %*
)
if errorlevel 1 (
  echo.
  echo ---------------------------------------------------------------
  echo I76 Debug exited with an error. Common causes:
  echo   * no Python 3 on the PATH - install it from python.org
  echo   * port 17690 already in use: another I76 Debug is running - use --http-port
  echo ---------------------------------------------------------------
  pause
)
endlocal
