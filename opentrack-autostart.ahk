; Start opentrack tracking without touching the mouse.
;
; opentrack has no command-line "start tracking" switch (checked: the exe exposes
; only the Qt btnStartTracker widget), and no auto-start key in the profile. So
; the launcher starts opentrack and this presses Start for it.
;
; Idempotent: if FT_SharedMem already exists, tracking is running and this exits
; without clicking anything - so it is safe to run on every launch, and safe if
; you started opentrack by hand first.
;
; Run:  AutoHotkeyU32.exe opentrack-autostart.ahk
; Docs: docs/HEAD-TRACKING.md

#NoEnv
#NoTrayIcon
#SingleInstance Force

; already publishing? then tracking is live - nothing to do
hMap := DllCall("OpenFileMapping", "UInt", 0x0004, "Int", 0, "Str", "FT_SharedMem", "Ptr")
if (hMap) {
    DllCall("CloseHandle", "Ptr", hMap)
    ExitApp
}

; wait for the opentrack window (it can take a few seconds to build its UI)
SetTitleMatchMode, 2
WinWait, opentrack,, 25
if (ErrorLevel)
    ExitApp

; The Start button is a Qt widget; AHK sees Qt controls as QWidgetN, so match on
; the button TEXT rather than a class index, which shifts between builds.
Loop, 20 {
    ControlGet, hBtn, Hwnd,, Start, opentrack
    if (hBtn) {
        ControlClick, Start, opentrack,,,, NA
        break
    }
    Sleep, 500
}

; confirm it actually started publishing rather than assuming the click landed
Loop, 20 {
    Sleep, 500
    h := DllCall("OpenFileMapping", "UInt", 0x0004, "Int", 0, "Str", "FT_SharedMem", "Ptr")
    if (h) {
        DllCall("CloseHandle", "Ptr", h)
        break
    }
}
ExitApp
