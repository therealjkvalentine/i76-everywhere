@echo off
rem Interstate '76 internet relay: let players from the internet reach the relay through Windows Firewall. Run it once per PC
rem (and again after the relay's Python is updated or replaced). Needs admin: it asks once.
rem What it does, for the Python that RUN-RELAY.bat uses (relay.ini "python =", else py -3, else python):
rem   1. removes every inbound BLOCK rule on that Python's program file (Windows adds them when its "allow access?" prompt
rem      is closed or answered for one network type only);
rem   2. adds ONE inbound ALLOW rule "Interstate 76 relay (i76-everywhere)": UDP, the relay's port only (relay.ini, 19900),
rem      for that program only, on PRIVATE and PUBLIC networks. Public too because players from the internet arrive on
rem      whatever profile Windows gave the network the router forwards them through; a home network marked Public would
rem      otherwise drop them.
rem RELAY-FIREWALL.bat --check   lists what it would change and changes nothing (no admin needed).
rem Undo: netsh advfirewall firewall delete rule name="Interstate 76 relay (i76-everywhere)"
rem (the removed BLOCK rules are not put back by that; Windows asks again the next time Python listens).
setlocal
if /i "%~1"=="--check" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0relay-tool.ps1" -Firewall -Check
  pause
  exit /b 0
)
net session >nul 2>&1
if errorlevel 1 (
  echo Asking for administrator rights to change the firewall rules for the relay ^(UDP, relay.ini's port^).
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0relay-tool.ps1" -Firewall
if errorlevel 1 ( echo Failed - nothing more was changed. & pause & exit /b 1 )
echo Done. Start RUN-RELAY.bat; players reach it once the router forwards the port to this PC.
pause
