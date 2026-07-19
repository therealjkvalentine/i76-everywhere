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
; @pad RT(looking back): fires the REAR gun (hp3) while right stick is held back
; @pad LT: hardpoint 2 (hold)
; @pad LB+X: radar zoom toggle (R)
; @pad A(tap): OK/select in menus - click+Enter; in-sim a single shot
; @pad A(hold 400ms): NITROUS while held
; @pad B(tap): cycle weapon (C)
; @pad X: cycle targets (Y)
; @pad Y: toggle chase cam <-> cockpit (F3/F1)
; @pad LB(tap): front target (Q)
; @pad Select: pause menu / skip cutscene (Esc)
; @pad Start: map (M)
; @pad Dpad-Up: headlights (H)
; @pad Dpad-Down: ignition (I)
; @pad Dpad-Left: notepad (N)
; @pad Dpad-Right: map (M)
; @pad RStick: look / glance - cockpit, external cam, menus (arrow keys)
; @pad R3: look at target (E)
; @pad R3(looking back): drop mines (hardpoint 4)
; @pad LB+RT: hardpoint 1
; @pad LB+LT: hardpoint 5 + hardpoint 2 (backup - few cars have a 5th)
; @pad LB+A: hardpoint 3 - rear gun only
; @pad LB+B: hardpoint 4 - dropper
; @pad LB+Y: cycle camera views (F1 F2 F3 F7 F8 F9 F10 F1 - both dash modes)
; @pad L3: nitrous / special 1 (hold); with LEFT stick pulled back = toggle reverse
; @pad LB+Dpad-Up: binoculars (B)
; @pad LB+Dpad-Down: horn (G)
; @pad LB+Dpad-Left: gear down (-)
; @pad LB+Dpad-Right: gear up (=)
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
gYPrev := false, gCamIdx := 0, gYExt := false
gTL := 0, gTR := 0, gTTicks := 0, gGrowl := 0
gNitroPrev := false, gRBPrev := false, gGearUPrev := false, gGearDPrev := false, gMinePrev := false, gLookBack := false, gL3Nitro := false, gL3Prev := false, gXIVibLast := -1
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
    if (d > 12)
        RSGSet(key, true)
    else if (d < 8)
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
VarSetCapacity(xiVib0, 4, 0)
if (gXIDll != "")
    DllCall(gXIDll . "\XInputSetState", "UInt", gXIPad, "Ptr", &xiVib0)
RSGSet("Right", false), RSGSet("Left", false), RSGSet("Up", false), RSGSet("Down", false)
RSGSet("1", false), RSGSet("2", false), RSGSet("3", false), RSGSet("4", false), RSGSet("5", false), RSGSet("6", false)
RSGSet("h", false), RSGSet("i", false), RSGSet("n", false), RSGSet("m", false), RSGSet("LButton", false)
RSGSet("y", false), RSGSet("u", false), RSGSet("v", false), RSGSet("x", false), RSGSet("-", false), RSGSet("=", false), RSGSet("b", false), RSGSet("g", false), RSGSet("e", false), RSGSet("r", false)
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
xHeld := (btns & 0x4000) != 0
yHeld := (btns & 0x8000) != 0
lbHeld := (btns & 0x0100) != 0
selHeld := (btns & 0x0020) != 0
stHeld := (btns & 0x0010) != 0
dU := (btns & 0x0001) != 0
dD := (btns & 0x0002) != 0
dL := (btns & 0x0004) != 0
dR := (btns & 0x0008) != 0

if (lbHeld && !gLBPrev)
    gLBUsed := false, gLBt0 := A_TickCount

; A: shifted = rear gun only. Base: tap = click+Enter on release (menu
; OK/select; in-sim just a single shot); held >=400ms = nitrous.
if (lbHeld) {
    gANitro := false, gAt0 := 0
    RSGSet("3", (lbHeld && aHeld) || (gLookBack && gRTHeld))
} else {
    RSGSet("3", gLookBack && gRTHeld)
    if (aHeld && !gAPrev)
        gAt0 := A_TickCount, gANitro := false
    if (aHeld && !gANitro && gAt0 && A_TickCount - gAt0 >= 400)
        gANitro := true
    if (!aHeld && gAPrev) {
        if (!gANitro && gAt0) {
            Click
            SendEvent, {Enter}
        }
        gANitro := false, gAt0 := 0
    }
}
gAPrev := aHeld

; L3: nitrous while held - unless the LEFT stick is pulled back at the
; press, then it's a reverse toggle instead (low-speed 3-point-turn helper)
l3Held := (btns & 0x0040) != 0
if (l3Held && !gL3Prev) {
    ly := NumGet(xiState, 10, "Short")
    if (ly < -16384) {
        SendEvent, x
        RumblePulse(25000, 0, 2)  ; tactile confirm: reverse toggled
    } else
        gL3Nitro := true
}
if (!l3Held)
    gL3Nitro := false
gL3Prev := l3Held
RSGSet("6", gANitro || gL3Nitro)

; look-back fire: while the right stick is held back (rear view), RT
; routes to the rear gun instead of the front guns
ry := NumGet(xiState, 14, "Short")
if (ry < -16384)
    gLookBack := true
else if (ry > -13000)
    gLookBack := false

; fire + triggers, base vs layer vs look-back
RSGSet("LButton", !lbHeld && !gLookBack && gRTHeld)
RSGSet("1", lbHeld && gRTHeld)
RSGSet("2", gLTHeld)              ; hp2 always - shifted too (hp5 backup rule)
RSGSet("5", lbHeld && gLTHeld)

; R3: look at target; while looking back, drop mines (hardpoint 4).
; "4" has ONE writer: OR of LB+B (dropper) and lookback-R3 (mines).
r3Held := (btns & 0x0080) != 0
RSGSet("e", r3Held && !gLookBack)

; B: base tap = cycle weapon (C); shifted = dropper (hardpoint 4)
RSGSet("4", (lbHeld && bHeld) || (r3Held && gLookBack))
if (!lbHeld && bHeld && !gBPrev)
    SendEvent, c
gBPrev := bHeld

; X: cycle targets (Y key); shifted = radar zoom toggle (R)
RSGSet("y", !lbHeld && xHeld)
RSGSet("r", lbHeld && xHeld)

; Y: base = chase <-> cockpit toggle (F3/F1); shifted = cycle camera views
if (!lbHeld && yHeld && !gYPrev) {
    gYExt := !gYExt
    yKey := gYExt ? "F3" : "F1"
    SendEvent, {%yKey%}
    gCamIdx := gYExt ? 2 : 0     ; keep the LB+Y cycle in step
}
if (lbHeld && yHeld && !gYPrev) {
    gCamIdx := Mod(gCamIdx + 1, 8)
    camKey := StrSplit("F1,F2,F3,F7,F8,F9,F10,F1", ",")[gCamIdx + 1]
    SendEvent, {%camKey%}
}
gYPrev := yHeld

; D-pad: base = utilities (held-mirrored keys, work inside map/notepad
; screens too); shifted = driving (reverse / gear down / gear up)
RSGSet("h", !lbHeld && dU)
RSGSet("i", !lbHeld && dD)
RSGSet("n", !lbHeld && dL)
RSGSet("m", stHeld || (!lbHeld && dR))   ; Start also = map
RSGSet("b", lbHeld && dU)     ; binoculars
RSGSet("g", lbHeld && dD)     ; horn (hold to honk)
RSGSet("-", lbHeld && dL)
RSGSet("=", lbHeld && dR)

if (lbHeld && (aHeld || bHeld || xHeld || yHeld || gRTHeld || gLTHeld || dU || dD || dL || dR))
    gLBUsed := true
if (!lbHeld && gLBPrev && !gLBUsed && (A_TickCount - gLBt0 < 300)) {
    SendEvent, q
    RumblePulse(0, 20000, 1)     ; tactile confirm: front-target snap
}
gLBPrev := lbHeld

; Select: Esc (pause / skip cutscene)
if (selHeld && !gSelPrev)
    SendEvent, {Esc}
gSelPrev := selHeld

; ---- rumble mixer (2026-07-18, field-proven path). Design per the game-feel
; canon: hierarchy + restraint (continuous states LOW so transients read on
; top), distinct signature per event, left motor = heavy/low-freq, right =
; light/high-freq buzz. Two layers: continuous (nitrous/weapons/engine growl)
; + transient pulses (RumblePulse, last-event-wins). SetState only on change.
lyR := NumGet(xiState, 10, "Short")
nact := (gANitro || gL3Nitro)
if (nact && !gNitroPrev)
    RumblePulse(65000, 30000, 2)          ; nitrous ENGAGE kick
gNitroPrev := nact
rbHeld := (btns & 0x0200) != 0
if (rbHeld && !gRBPrev)
    RumblePulse(30000, 0, 2)              ; handbrake thud
gRBPrev := rbHeld
gearU := lbHeld && dR, gearD := lbHeld && dL
if ((gearU && !gGearUPrev) || (gearD && !gGearDPrev))
    RumblePulse(0, 32000, 1)              ; gear-shift click
gGearUPrev := gearU, gGearDPrev := gearD
mn := (lbHeld && bHeld) || (r3Held && gLookBack)
if (mn && !gMinePrev)
    RumblePulse(40000, 0, 3)              ; mine/dropper thud
gMinePrev := mn
cl := 0, cr := 0
if (nact)
    cl := 45000, cr := 20000
if (gRSGHeld["LButton"] || gRSGHeld["1"] || gRSGHeld["2"] || gRSGHeld["3"] || gRSGHeld["5"])
    cr := cr > 18000 ? cr : 18000         ; weapons-fire buzz (light motor)
if (!nact && lyR > 28000) {
    gGrowl := Mod(gGrowl + 1, 12)
    gv := 9000 + (gGrowl >= 6 ? 4000 : 0) ; full-throttle engine growl (textured)
    cl := cl > gv ? cl : gv
}
if (gTTicks > 0) {
    gTTicks -= 1
    cl := cl > gTL ? cl : gTL
    cr := cr > gTR ? cr : gTR
}
cl := cl > 65535 ? 65535 : cl
cr := cr > 65535 ? 65535 : cr
vibPair := (cl << 16) | cr
if (vibPair != gXIVibLast) {
    VarSetCapacity(xiVib, 4, 0)
    NumPut(cl, xiVib, 0, "UShort"), NumPut(cr, xiVib, 2, "UShort")
    DllCall(gXIDll . "\XInputSetState", "UInt", gXIPad, "Ptr", &xiVib)
    gXIVibLast := vibPair
}
gXIPrevBtns := btns
return

RumblePulse(l, r, ticks) {
    global gTL, gTR, gTTicks
    gTL := l, gTR := r, gTTicks := ticks
}
