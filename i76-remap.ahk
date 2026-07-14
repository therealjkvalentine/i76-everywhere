; Interstate '76 - universal in-container input remapper (AutoHotkey v1.1).
; Runs INSIDE the Wine/Proton prefix on Mac/Deck - and unchanged on native
; Windows. Installed by setup-input-remapper.sh; auto-started by the Mac
; launcher stub when present. Docs: docs/INPUT-REMAPPER.md.
;
; WHY: the I76 engine knows exactly three mouse buttons (LeftBtn/RightBtn/
; MiddleBtn - verified in the exe). Buttons 4/5 DO exist at the Windows layer
; (winemac.drv maps physical button N>=4 to XBUTTON1/XBUTTON2), so we turn
; them into KEYS here and let input.map bind those keys as usual. The game
; never binds buttons 4/5 itself, so this remap is purely additive - no
; double-trigger even if hook suppression ever fails under Wine.
;
; EDITING RULES (human + agent):
;  - Keep SendMode at its DEFAULT (Event). Do not add "SendMode Input":
;    AHK uninstalls its own hooks during SendInput playback, and in this
;    prefix only SendEvent-injected events reach the hooks (verified
;    2026-07-14 with the setup script's --test harness).
;  - "A::B" remap syntax holds B down while A is held - what specials want.
;  - Deliberately NO #IfWinActive scoping: under Wine this script only lives
;    while the game session lives, and its hooks only see input while a Wine
;    window has focus. If you run it globally on native Windows, wrap the
;    remaps in:  #IfWinActive ahk_exe i76.exe
;
; The key names on the RIGHT are what input.map binds (docs/input.map.reference):
;   6 / 7 / 8  =  special1 / special2 / special3  (nitrous, bumpers... fire
;                 from whichever special slot the part is mounted in)
;   = / -      =  shift_up / shift_down (gear shift)

#NoEnv
#NoTrayIcon
#SingleInstance Force
#Persistent
#InstallMouseHook
#MaxHotkeysPerInterval 500  ; fast wheel scrolling must never pop the warning dialog

; ---- mouse button 4 ("back") --> 6 = special 1 (the default nitrous slot)
XButton1::6

; ---- mouse button 5 ("forward") --> 7 = special 2
XButton2::7

; ---- mouse wheel --> gear shift ('=' = shift_up, '-' = shift_down)
; Note: on a text screen (pilot-name entry) a wheel notch types '='/'-' like
; any keypress would. Comment these two lines out if that ever bothers you.
WheelUp::=
WheelDown::-
