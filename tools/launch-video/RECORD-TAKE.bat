@echo off
rem RECORD-TAKE.bat <tag> <seconds> [x,y,w,h] - records the running game window at 60 fps for the launch video (tools\launch-video\record-window.ps1)
if "%~3"=="" (powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0record-window.ps1" -Tag %1 -Seconds %2) else (powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0record-window.ps1" -Tag %1 -Seconds %2 -Rect %3)
pause
