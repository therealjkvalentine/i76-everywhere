@echo off
rem Interstate '76 + in-container input remapper - Deck (Proton) / native Windows.
rem Put this next to i76.exe, install C:\AutoHotkey per docs/INPUT-REMAPPER.md,
rem then launch THIS instead of i76.exe (Heroic: "select alternative exe").
rem The Mac wrapper does NOT use this file - its launcher stub starts AHK itself.
cd /d "%~dp0"
if exist C:\AutoHotkey\AutoHotkeyU32.exe if exist C:\AutoHotkey\i76-remap.ahk start "" C:\AutoHotkey\AutoHotkeyU32.exe C:\AutoHotkey\i76-remap.ahk
start "" /wait i76.exe %*
taskkill /im AutoHotkeyU32.exe /f >nul 2>&1
