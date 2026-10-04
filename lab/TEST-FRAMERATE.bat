@echo off
rem TEST-FRAMERATE.bat - try things in the SANDBOX game (C:\Users\james\i76-uncap-lab\game), never the daily driver.
rem The sandbox has the daily driver's controls and its own saves. Runs 1-3 start like the daily driver's PLAY.bat
rem (pad/wheel/stick layers; no head tracking here). The launcher prints every I76_* switch before the game starts.
echo.
echo   1 = WIDESCREEN + DETAIL     21:9, 120 fps, terrain/textures/objects/bushes/shadows/roads farther out
echo   2 = WIDESCREEN + MAX DETAIL 1 with terrain shape x16 and bushes to 400 m
echo   3 = DAILY DRIVER TODAY      best-120 at 16:10 (what PLAY.bat runs now)
echo   4 = STOCK 20 FPS            the reference feel, no fixes
echo   5 = MORE...                 frame-rate A/B runs and picture shapes
choice /c 12345 /n /m " Which? [1-5] "
if errorlevel 5 goto more
if errorlevel 4 (set ARGS=-Mode stock20 -Shape 16x10& goto run)
if errorlevel 3 (set ARGS=-Preset best-120 -Shape 16x10& goto run)
if errorlevel 2 (set ARGS=-Preset exp-detail-16 -Shape wide& goto run)
set ARGS=-Preset exp-detail-8 -Shape wide
goto run

:more
echo.
echo   1 = 60 fps, all fixes          (hires clock, fixed 24 Hz physics, frame-rate fixes, engine fix, interpolation)
echo   2 = 60 fps, fixes but NO interpolation  (shows the 24 Hz judder interpolation removes)
echo   3 = 60 fps stock               (the control)
echo   4 = 120 fps, all fixes + bug fixes + far clip 1800 m + telemetry  (keyboard only)
echo   5 = terrain shape x8 only      (exp-terrain-8)
echo   6 = terrain shape x16 only     (exp-terrain-16)
choice /c 123456 /n /m " Which run? [1-6] "
set MODE=fixed
set EXTRA=
if errorlevel 6 (set EXTRA=-Preset exp-terrain-16& goto shape)
if errorlevel 5 (set EXTRA=-Preset exp-terrain-8& goto shape)
if errorlevel 4 (set MODE=all120& goto shape)
if errorlevel 3 (set MODE=stock60& goto shape)
if errorlevel 2 (set MODE=nointerp& goto shape)
:shape
echo.
echo   Picture: 1 = 16:10   2 = 14:9   3 = 3:2   4 = 4:3   5 = widescreen 21:9
choice /c 12345 /n /m " Shape? [1-5] "
set SHAPE=16x10
if errorlevel 5 (set SHAPE=wide& goto shaped)
if errorlevel 4 (set SHAPE=4x3& goto shaped)
if errorlevel 3 (set SHAPE=3x2& goto shaped)
if errorlevel 2 (set SHAPE=14x9& goto shaped)
:shaped
set ARGS=-Mode %MODE% -Shape %SHAPE% %EXTRA%

:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0TEST-FRAMERATE.ps1" %ARGS%
pause
