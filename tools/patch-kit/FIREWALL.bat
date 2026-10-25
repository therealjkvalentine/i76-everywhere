@echo off
rem Interstate '76 Patch Kit: let the game receive LAN packets (IPX over UDP) on private networks.
rem Adds one inbound Windows Firewall allow rule for the game exe in THIS folder (i76.exe or nitro.exe). Needs admin: it asks once.
rem Undo: netsh advfirewall firewall delete rule name="Interstate 76 (i76-everywhere)"
setlocal
set "HERE=%~dp0"
set "EXE="
if exist "%HERE%i76.exe" set "EXE=%HERE%i76.exe"
if exist "%HERE%nitro.exe" set "EXE=%HERE%nitro.exe"
if "%EXE%"=="" ( echo No i76.exe or nitro.exe next to this file. Put FIREWALL.bat in the game folder. & pause & exit /b 1 )
net session >nul 2>&1
if errorlevel 1 (
  echo Asking for administrator rights to add the firewall rule for:
  echo   %EXE%
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)
netsh advfirewall firewall delete rule name="Interstate 76 (i76-everywhere)" program="%EXE%" >nul 2>&1
netsh advfirewall firewall add rule name="Interstate 76 (i76-everywhere)" dir=in action=allow program="%EXE%" enable=yes profile=private description="i76-everywhere: LAN play (IPX over UDP). Private networks only."
if errorlevel 1 ( echo Failed to add the rule. & pause & exit /b 1 )
echo Done: inbound allowed for %EXE% on private networks. Hosting and joining LAN games will not prompt again.
pause
