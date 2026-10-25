@echo off
rem Interstate '76 internet relay: starts pyrelay.py (Python 3) in this console window and leaves it running.
rem Prints the port (relay.ini, default UDP 19900), this PC's home-network address (where the router's port forward points)
rem and the public address players type: PLAY.bat --relay <public address>:19900. Close the window or Ctrl+C stops it.
rem Once per PC first: RELAY-FIREWALL.bat (Windows Firewall) and, in your router's admin page, port forwarding of UDP 19900
rem to this PC. README.md beside this file explains it.
setlocal
title Interstate '76 relay
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0relay-tool.ps1" -Run
echo.
echo The relay has stopped.
pause
