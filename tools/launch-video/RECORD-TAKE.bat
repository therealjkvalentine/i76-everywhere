@echo off
rem RECORD-TAKE.bat <tag> <seconds> [x,y,w,h] - records the running game window at 60 fps for the launch video (tools\launch-video\record-window.ps1)
rem cmd splits on commas, so x,y,w,h arrives as four arguments: they are joined again here.
if "%~3"=="" (powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0record-window.ps1" -Tag %1 -Seconds %2) else (powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0record-window.ps1" -Tag %1 -Seconds %2 -Rect "%3,%4,%5,%6")
pause
