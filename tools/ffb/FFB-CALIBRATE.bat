@echo off
REM Interstate '76 custom force feedback - calibration.
REM
REM Run this ONCE per install, before using the panel. It measures two things the
REM force model would otherwise be guessing:
REM
REM   * which way the car's yaw rate is signed (get it wrong and the wheel helps
REM     you turn INTO the corner instead of resisting)
REM   * how many degrees of steering angle "full lock" means, which sets how
REM     readily slip is detected
REM
REM HOW TO DRIVE FOR IT: be in a mission, get above 20 mph, and make several
REM SUSTAINED smooth turns in BOTH directions. Sustained matters - a flick of the
REM wheel measures the car's transient response instead and fits a lock angle
REM that is too small.
REM
REM Writes ffb-calib.json next to this file. The panel picks it up automatically.

setlocal
cd /d "%~dp0"
echo.
echo Get into a mission and be ready to drive.
echo.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ffb-calibrate.ps1" %*
echo.
pause
endlocal
