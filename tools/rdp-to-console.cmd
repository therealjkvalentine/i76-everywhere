@echo off
rem Hand this RDP session to the physical console and drop the RDP link.
rem The desktop stays logged in and unlocked at the machine, so harness runs
rem that need an active console session (docs\records\FRESH-START-METHOD.md, H10) work.
rem Reconnecting over RDP later takes the session back.

rem tscon needs admin: relaunch elevated if we aren't already.
net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

rem Our session ID is the 3rd column of the line marked '>' in "query user".
set "SID="
for /f "tokens=1-3" %%a in ('query user %USERNAME% 2^>nul') do (
    if /i "%%a"==">%USERNAME%" set "SID=%%c"
)
if not defined SID (
    echo Could not find this session's ID. "query user" says:
    query user
    pause
    exit /b 1
)

echo Moving session %SID% to the console...
tscon %SID% /dest:console
if errorlevel 1 (
    echo tscon failed with error %errorlevel%.
    pause
    exit /b 1
)
