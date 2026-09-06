; i76-cursor-overlay.ahk - draw a pointer the game cannot hide.
;
; WHY: the OS pointer is invisible over the game's client area and visible over every other
; window, even while the game is in the background. Measured and NOT the cause: dgVoodoo (with
; FreeMouse=true it does not touch the mouse and the pointer is still gone), the ShowCursor
; reference count (ends positive), the window class cursor (a normal IDC_ARROW), the two .cur
; files (both have real ink), exclusive fullscreen (it is a borderless window), and answering
; WM_SETCURSOR ourselves (tried, changed nothing).
;
; So stop trying to make the game show a cursor and put one on top of it instead. This is a
; separate always-on-top, click-through window that follows the real pointer - the same
; pointer whose CLICKS were always landing correctly. It cannot be hidden by the game because
; the game does not own it.
;
; It is click-through (WS_EX_TRANSPARENT), never takes focus (NoActivate), and re-asserts its
; z-order on a timer because the game re-asserts its own.
;
;   "%GameDir%\_ahk\AutoHotkeyU32.exe" i76-cursor-overlay.ahk
;
; Exit from the tray icon, or press Ctrl+Alt+C to toggle it off and on.

#NoEnv
#SingleInstance Force
#Persistent
SetBatchLines, -1
CoordMode, Mouse, Screen

; ---- appearance ---------------------------------------------------------------------------
; A crosshair rather than an arrow: the game hit-tests the pointer's exact pixel, so a shape
; centred on the hotspot shows precisely where the click will land. Green reads against both
; the dark menus and the desert.
global SIZE   := 21          ; overall box, odd so there is a true centre pixel
global THICK  := 3
global COLOR  := "22DD22"
global GAP    := 3           ; hole in the middle so the thing under the pointer stays visible

global Visible := true
global Shown   := true

half := (SIZE - THICK) // 2
arm  := (SIZE - GAP) // 2 - 1
far  := SIZE - arm
; NOTE: every Gui option below uses plain %var% substitution. Mixing an expression into the
; option string (x% SIZE-arm) makes AHK read "SIZE-arm y" as one variable name and refuse to
; start - "the following variable name contains an illegal character".

Gui, +AlwaysOnTop +ToolWindow -Caption +E0x20 +LastFound +HwndOverlayHwnd
; E0x20 = WS_EX_TRANSPARENT: clicks pass straight through to the game underneath.
Gui, Color, 000000
Gui, Margin, 0, 0
; four arms, leaving a gap at the centre
Gui, Add, Progress, x0     y%half% w%arm%  h%THICK% Background%COLOR%
Gui, Add, Progress, x%far% y%half% w%arm%  h%THICK% Background%COLOR%
Gui, Add, Progress, x%half% y0     w%THICK% h%arm%  Background%COLOR%
Gui, Add, Progress, x%half% y%far% w%THICK% h%arm%  Background%COLOR%
Gui, Show, NoActivate x0 y0 w%SIZE% h%SIZE%, i76cursor
WinSet, TransColor, 000000, ahk_id %OverlayHwnd%

SetTimer, Track, 15
SetTimer, CheckGame, 2000
return

Track:
    if (!Visible) {
        if (Shown) {
            Gui, Hide
            Shown := false
        }
        return
    }
    ; Only draw over the game. Otherwise this thing follows the pointer around the desktop and
    ; sits on top of every other window, which is worse than the problem it solves.
    if (!WinActive("ahk_exe i76.exe")) {
        if (Shown) {
            Gui, Hide
            Shown := false
        }
        return
    }
    if (!Shown) {
        Gui, Show, NoActivate
        Shown := true
    }
    MouseGetPos, mx, my
    ; SWP_NOACTIVATE|SWP_NOSIZE, HWND_TOPMOST (-1): move and re-assert topmost in one call, so
    ; the overlay stays above the game even though the game keeps re-asserting its own z-order.
    DllCall("SetWindowPos", "Ptr", OverlayHwnd, "Ptr", -1
        , "Int", mx - (SIZE // 2), "Int", my - (SIZE // 2), "Int", 0, "Int", 0
        , "UInt", 0x0011)      ; SWP_NOSIZE (0x1) | SWP_NOACTIVATE (0x10)
return

^!c::
    Visible := !Visible
return

; Leave with the game, so a stray overlay never outlives the session it belongs to.
CheckGame:
    Process, Exist, i76.exe
    if (!ErrorLevel)
        ExitApp
return

GuiClose:
ExitApp
