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

; ---- NO mouse-MOTION injection (a right-stick->mouse-X bridge lived here for
; a few hours on 2026-07-18: field verdict "unusable"). Discrete KEY emission
; is fine - it's this whole script's job, and it's exactly how Steam Input
; drives the same features on the Deck.

; ---- right stick --> arrow keys (glance/track camera/menus), 2026-07-18.
; The engine's analog vocabulary can't name the stick's horizontal axis
; (winmm U) and analog camera deltas felt bad anyway; the arrow keys are
; field-proven great in and out of the car. So: deflect right stick =
; hold the matching arrow key, exactly like the Deck config's right stick.
; Stuck-key safety (the wheel-disaster rules): held-state table so every
; down has a matching up, release-on-center every 15ms tick, release-all
; when the pad vanishes and on script exit.
gRSGHeld := {}
SetTimer, RStickGlance, 15
OnExit, RSGExit

; ---- mouse button 4 ("back") --> 6 = special 1: the user's NITROUS.
; Field-corrected 2026-07-18 (second pass): nitrous is in special slot 1,
; i.e. THIS button - the old "button 5 = nitrous" note (f04d668) was wrong
; for this loadout (special2 is empty; the forward button did nothing).
XButton1::6

; ---- mouse button 5 ("forward") --> 3 = weapon key 3 (input.map: Three ->
; hardpoint3_fire). NOTE 2026-07-18: on the user's car the hardpoint3_fire
; ACTION fires what the HUD numbers as weapon 4 - mount-slot vs HUD numbering
; differ. If the wrong gun fires, shift this key (2/3/4), one-line change.
XButton2::3

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

; ---- right-stick glance machinery (see SetTimer near the top).
; AHK v1 axes read 0-100, 50 = center. JoyR = right stick VERTICAL (up ~0),
; JoyU = right stick HORIZONTAL (right ~100) - decoded 2026-07-18. If a
; direction is backwards in the field, flip the +1/-1 in the RStickGlance
; calls. Hysteresis: press past 25-from-center, release inside 15-from-center.
RStickGlance:
u := GetKeyState("JoyU")
v := GetKeyState("JoyR")
if (u = "" || v = "") {
    RSGSet("Right", false), RSGSet("Left", false), RSGSet("Up", false), RSGSet("Down", false)
    return
}
RSGHys("Right", u, 1), RSGHys("Left", u, -1), RSGHys("Down", v, 1), RSGHys("Up", v, -1)
return

RSGHys(key, val, dir) {
    d := (val - 50) * dir
    if (d > 25)
        RSGSet(key, true)
    else if (d < 15)
        RSGSet(key, false)
}

RSGSet(key, want) {
    global gRSGHeld
    if (want && !gRSGHeld[key]) {
        gRSGHeld[key] := true
        SendEvent, {%key% down}
    } else if (!want && gRSGHeld[key]) {
        gRSGHeld[key] := false
        SendEvent, {%key% up}
    }
}

RSGExit:
RSGSet("Right", false), RSGSet("Left", false), RSGSet("Up", false), RSGSet("Down", false)
ExitApp
