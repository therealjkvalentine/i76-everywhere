@echo off
REM Interstate '76 Everywhere — double-click installer.
REM Finds your GOG offline backup (setup_interstate76_*.exe in Downloads),
REM installs the game, and applies all the controls/graphics improvements.
setlocal
echo.
echo   Interstate '76 Everywhere - installing from your GOG copy...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-From-GOG.ps1" %*
echo.
pause
