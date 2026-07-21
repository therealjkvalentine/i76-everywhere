@echo off
REM Pack your configured Interstate '76 into a portable zip for another PC.
setlocal
echo.
echo   Building a portable Interstate '76 zip...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Make-Portable-Zip.ps1" %*
echo.
pause
