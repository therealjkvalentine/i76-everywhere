; Start opentrack tracking without a click - now a thin wrapper around i76-opentrack-autostart.ps1.
;
; 2026-10-24: this script used to look for opentrack's Start button with ControlGet/ControlClick. That
; never worked on opentrack 2026.1: it is a Qt 6 app and Qt widgets are not native windows, so there is
; no "Start" control to find (owner: "head look does not automatically start opentrack but it works fine
; after you click it"; reproduced - it waited 20 s and exited with tracking off). The PowerShell helper
; presses Start through UI Automation and verifies that FT_SharedMem's DataID advances. PLAY-i76.ps1
; -HeadTrack runs the .ps1 directly (and switches on opentrack's own game detection); this wrapper is
; for anything that still starts the .ahk.
;
; Run:  AutoHotkeyU32.exe i76-opentrack-autostart.ahk
; Docs: docs/HEAD-TRACKING.md

#NoEnv
#NoTrayIcon
#SingleInstance Force

ps := A_ScriptDir . "\i76-opentrack-autostart.ps1"
if (!FileExist(ps))
    ExitApp, 1
RunWait, % "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ . ps . """ -Log """ . A_ScriptDir . "\opentrack-autostart.log""",, Hide
ExitApp, %ErrorLevel%
