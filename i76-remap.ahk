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

; ---- XInput layer (2026-07-18): things winmm can NOT deliver.
; winmm merges both triggers into ONE shared axis (they cancel when pressed
; together), so trigger-as-two-buttons is impossible at the joystick layer.
; XInput exposes LT/RT as independent 0-255 values - and Wine/Proton implement
; xinput*.dll, so this works identically on Mac (Wine), Deck (Proton, Steam
; Input off) and native Windows. Polled here:
;   v3 layout (2026-07-18). Machine-readable: tools/pad-diagram.py renders
;   the @pad lines below plus input.map into docs/pad-diagram.html - keep
;   them in sync with the XIPoll code they describe.
; @pad RT: fire - current weapon / cockpit handgun (hold)
; @pad LT: hardpoint 2 (hold)
; @pad A(tap): OK in menus / single shot (click on release)
; @pad A(hold 400ms): NITROUS while held
; @pad B(tap): cycle weapon (C)
; @pad LB(tap): front target (Q)
; @pad LB+RT: hardpoint 1
; @pad LB+LT: hardpoint 5
; @pad LB+A: hardpoint 3 - rear gun only
; @pad LB+B: hardpoint 4 - dropper
; @pad LB+Select: untarget (U)
; @pad Select: pause menu / skip cutscene (Esc)
; @pad Dpad-Up: headlights (H)
; @pad Dpad-Down: ignition (I)
; @pad Dpad-Left: notepad (N)
; @pad Dpad-Right: map (M)
; @pad RStick: look / glance - cockpit, external cam, menus (arrow keys)
gXIDll := ""
Loop, Parse, % "xinput1_4.dll,xinput1_3.dll,xinput9_1_0.dll", `,
{
    if DllCall("LoadLibrary", "Str", A_LoopField, "Ptr") {
        gXIDll := A_LoopField
        break
    }
}
gXIPad := 0, gXIPrevBtns := 0, gRTHeld := false, gLTHeld := false
gLBPrev := false, gLBUsed := false, gLBt0 := 0
gAPrev := false, gAt0 := 0, gANitro := false, gBPrev := false, gSelPrev := false
if (gXIDll != "")
    SetTimer, XIPoll, 15

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
RSGSet("1", false), RSGSet("2", false), RSGSet("3", false), RSGSet("4", false), RSGSet("5", false), RSGSet("6", false)
RSGSet("h", false), RSGSet("i", false), RSGSet("n", false), RSGSet("m", false), RSGSet("LButton", false)
ExitApp

; ---- XInput poll (see init near the top). State struct: buttons WORD @4,
; LT BYTE @6, RT BYTE @7. A=0x1000, Back=0x0020. Trigger hysteresis 40/25.
XIPoll:
VarSetCapacity(xiState, 16, 0)
if (DllCall(gXIDll . "\XInputGetState", "UInt", gXIPad, "Ptr", &xiState, "UInt") != 0) {
    found := false
    Loop, 4 {
        idx := A_Index - 1
        if (DllCall(gXIDll . "\XInputGetState", "UInt", idx, "Ptr", &xiState, "UInt") = 0) {
            gXIPad := idx, found := true
            break
        }
    }
    if (!found) {
        RSGSet("1", false), RSGSet("2", false)
        gXIPrevBtns := 0
        return
    }
}
rt := NumGet(xiState, 7, "UChar")
lt := NumGet(xiState, 6, "UChar")
btns := NumGet(xiState, 4, "UShort")
if (rt > 40)
    gRTHeld := true
else if (rt < 25)
    gRTHeld := false
if (lt > 40)
    gLTHeld := true
else if (lt < 25)
    gLTHeld := false
aHeld := (btns & 0x1000) != 0
bHeld := (btns & 0x2000) != 0
lbHeld := (btns & 0x0100) != 0
selHeld := (btns & 0x0020) != 0

if (lbHeld && !gLBPrev)
    gLBUsed := false, gLBt0 := A_TickCount

; A: shifted = rear gun only. Base: tap = click on release; >=400ms = nitrous.
if (lbHeld) {
    RSGSet("6", false)
    gANitro := false, gAt0 := 0
    RSGSet("3", aHeld)
} else {
    RSGSet("3", false)
    if (aHeld && !gAPrev)
        gAt0 := A_TickCount, gANitro := false
    if (aHeld && !gANitro && gAt0 && A_TickCount - gAt0 >= 400) {
        gANitro := true
        RSGSet("6", true)
    }
    if (!aHeld && gAPrev) {
        if (gANitro)
            RSGSet("6", false)
        else if (gAt0)
            Click
        gANitro := false, gAt0 := 0
    }
}
gAPrev := aHeld

; fire + triggers, base vs layer
RSGSet("LButton", !lbHeld && gRTHeld)
RSGSet("1", lbHeld && gRTHeld)
RSGSet("2", !lbHeld && gLTHeld)
RSGSet("5", lbHeld && gLTHeld)

; B: base tap = cycle weapon (C); shifted = dropper (hardpoint 4)
RSGSet("4", lbHeld && bHeld)
if (!lbHeld && bHeld && !gBPrev)
    SendEvent, c
gBPrev := bHeld

; D-pad -> utility keys, held-mirrored like a physical keyboard (toggles
; fire once on key-down; works inside the map/notepad screens too)
RSGSet("h", (btns & 0x0001) != 0)
RSGSet("i", (btns & 0x0002) != 0)
RSGSet("n", (btns & 0x0004) != 0)
RSGSet("m", (btns & 0x0008) != 0)

if (lbHeld && (aHeld || bHeld || gRTHeld || gLTHeld || selHeld))
    gLBUsed := true
if (!lbHeld && gLBPrev && !gLBUsed && (A_TickCount - gLBt0 < 300))
    SendEvent, q
gLBPrev := lbHeld

; Select: base = Esc (pause/skip); shifted = untarget (U)
if (selHeld && !gSelPrev) {
    if (lbHeld)
        SendEvent, u
    else
        SendEvent, {Esc}
}
gSelPrev := selHeld
gXIPrevBtns := btns
return
