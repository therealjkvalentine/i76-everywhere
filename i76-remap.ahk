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
; NO MODAL DIALOGS, EVER. AHK's rate-limit warning is a modal MsgBox: inside
; the Wine session it steals foreground focus from the game -- and under
; DxWnd's HideDesktop backdrop it's INVISIBLE, so the game just goes
; keyboard-dead (measured 2026-07-14: a 700-notch injected scroll flood
; tripped the old limit of 500 at exactly ~500 activations/2s and hard-blocked
; everything; a real trackpad momentum scroll can burst the same way). With
; only discrete button hotkeys bound, a runaway is impossible -- so set the
; threshold unreachably high instead of "high enough".
#MaxHotkeysPerInterval 200000
; Load-time errors print to stdout (remapper silently absent) instead of
; popping the same kind of focus-stealing dialog.
#ErrorStdOut

; ---- NO mouse-motion injection. A right-stick->mouse-X camera bridge lived
; here for a few hours on 2026-07-18 and was removed the same day: field
; verdict "unusable", and the user's standing policy is native-first - if the
; controller has a joystick, the game should see a joystick (input.map
; joystick1 bindings), not synthesized mouse motion. The engine's analog
; vocabulary reaches only one right-stick axis (winmm R = "Rudder"); the
; other half (winmm U) simply has no engine token - that gap does NOT get
; papered over with injection.

; ---- mouse button 4 ("back") --> 3 = hardpoint 3 (input.map binds Three ->
; hardpoint3_fire). Was 6/special1; changed 2026-07-18 - the user's nitrous
; lives on the OTHER side button (5/special2, field-confirmed 2026-07-14),
; so this one becomes the third weapon trigger.
XButton1::3

; ---- mouse button 5 ("forward") --> 7 = special 2 (nitrous on the user's car)
XButton2::7

; ---- mouse wheel: DO NOT REMAP. Removed 2026-07-14 after a field regression
; ("mouse activity kills WASD"). Two reasons, the first fatal:
;  1. Wheel "keys" have NO release event, and an AHK remap (WheelUp::=) holds
;     its destination key until the source releases -- which never comes. One
;     notch (incl. trackpad two-finger scroll / momentum scrolling) can leave
;     '=' logically STUCK DOWN, i.e. shift_up held forever -> transmission
;     pegged, throttle feels dead, "WASD broken" until the session restarts.
;  2. Even clean per-notch keystrokes spam the gear-shift actions, dropping
;     the transmission out of automatic mid-drive.
; If a wheel binding is ever wanted, use explicit hotkeys that send a full
; press+release of a HARMLESS key (never gears/steering/throttle):
;     WheelUp::SendEvent {F6}
; and field-test with trackpad momentum scrolling before shipping.
