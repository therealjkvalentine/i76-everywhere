@echo off
rem RECORD-TAKE.bat <tag> <seconds> [x,y,w,h] - records the running game window at 60 fps for the launch video (tools\launch-video\record-window.ps1)
rem cmd splits "0,0,1920,1080" into four arguments, so the rectangle is put back together from %3..%6.
setlocal
set "RECT="
if not "%~6"=="" (set "RECT=%~3,%~4,%~5,%~6") else if not "%~3"=="" (set "RECT=%~3")
if "%RECT%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0record-window.ps1" -Tag %1 -Seconds %2
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0record-window.ps1" -Tag %1 -Seconds %2 -Rect "%RECT%"
)
pause
