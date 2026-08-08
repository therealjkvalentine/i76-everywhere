; Interstate '76 - CH Products Fighterstick HOTAS layer (AutoHotkey v1.1).
;
; The grip's buttons follow F-16 convention; the stick's own DEFLECTION becomes
; the gearbox and the handbrake:
;
;     pull back    -> HANDBRAKE     (held for as long as the stick is back)
;     push forward -> REVERSE       (momentary: in reverse only while held)
;     left / right -> shift down / shift up
;
; Chosen at the wheel rather than from first principles. The handbrake is the
; gesture you make hardest and most often, so it takes the strongest, most natural
; pull; reverse reads as a held state rather than a latch; and the shifts sit out
; of the way of both on the lateral axis.
;
; WHY AHK AND NOT input.map: the engine's binding file maps an analog axis only to
; an ANALOG sink - `steer` and `throttle`. There is no syntax for "when this axis
; passes 60%, press a button", so an axis can never drive shift_up. The conversion
; has to happen outside the engine, and this is it: read the stick, send the key
; input.map already binds. input.map is not touched, so this cannot break the wheel.
;
; WHY AHK AND NOT POWERSHELL (this started life as a .ps1): AHK runs INSIDE the
; Wine/Proton prefix on Mac and Deck, exactly as i76-remap.ahk does, so the same
; script serves all three platforms. A PowerShell tool is Windows-only, which is a
; poor fit for a repo named i76-everywhere. It is also simply the right tool -
; joystick reading and key synthesis are what AHK is for - and it inherits the
; hard-won doctrine below instead of rediscovering it.
;
; EDITING RULES (human + agent), inherited from i76-remap.ahk:
;  - Keep SendMode at its DEFAULT (Event). Do NOT add "SendMode Input": AHK
;    uninstalls its own hooks during SendInput playback, and inside the Wine prefix
;    only SendEvent-injected events reach the hooks (verified 2026-07-14).
;  - NO MODAL DIALOGS, EVER. Under DxWnd's backdrop a MsgBox is invisible and steals
;    focus, so the game just goes input-dead. Output goes to stdout.
;
; Usage:
;     AutoHotkey.exe i76-fighterstick.ahk              run it
;     AutoHotkey.exe i76-fighterstick.ahk -learn       press controls, see numbers
;     AutoHotkey.exe i76-fighterstick.ahk -selftest    test the ADC, no hardware
;     AutoHotkey.exe i76-fighterstick.ahk -whatif      show actions, send no keys
;     AutoHotkey.exe i76-fighterstick.ahk -device 3    if the stick is not joystick2
;
; Docs: docs/FIGHTERSTICK.md.  Device: CH Fighterstick USB, VID 068E PID 00F3.

#NoEnv
#NoTrayIcon
#SingleInstance Force
#Persistent
; A runaway cannot happen here - this is a polled timer, not a hotkey - but the
; rate-limit warning is a modal MsgBox, and a modal is unacceptable (see above).
#MaxHotkeysPerInterval 200000
#ErrorStdOut
SetBatchLines, -1
; Registered here, not merely defined below: an OnExitHandler label that is never
; handed to OnExit is dead code, and the thing it guards against - a held Space
; leaving the player with a handbrake they cannot release - outlives the script.
OnExit, OnExitHandler

global DEV     := 2       ; AHK joystick index; the T300 wheel is 1
global THRESH  := 0.35    ; deflection to trigger, 0..1 from centre
global RELEASE := 0.20    ; deflection to release/re-arm - the gap is hysteresis
global POLL    := 15      ; ms, ~66 Hz, matching i76-remap.ahk's timers
global WHATIF  := false

; ---- keys ------------------------------------------------------------------
; SCAN CODES rather than characters. Verified on Windows that scancode 0x14
; resolves to VK_T and extended 0xE0,0x48 to VK_UP, so both a scan-code reader and
; a virtual-key reader see these. The game's joystick path is winmm
; (joyGetNumDevs/joyGetPosEx, no DirectInput - docs/GAMEPAD-PC-MAC.md); its
; keyboard path is not documented, so send the form that satisfies either.
;
; The arrow keys the game calls GreyUpArrow are the dedicated cluster, NOT the
; numpad. AHK's {Up}/{Down}/{Left}/{Right} are already that cluster.
global KEY := {}
KEY.Enter := "{SC01C}", KEY.Tab := "{SC00F}", KEY.Space := "{SC039}"
KEY.Period := "{SC034}", KEY.Comma := "{SC033}"
KEY.B := "{SC030}", KEY.E := "{SC012}", KEY.G := "{SC022}", KEY.I := "{SC017}"
KEY.M := "{SC032}", KEY.Q := "{SC010}", KEY.R := "{SC013}", KEY.T := "{SC014}"
KEY.U := "{SC016}", KEY.V := "{SC02F}", KEY.X := "{SC02D}", KEY.Y := "{SC015}"
KEY.Six := "{SC007}", KEY.Seven := "{SC008}", KEY.Eight := "{SC009}"
KEY.GreyUpArrow := "{Up}", KEY.GreyDownArrow := "{Down}"
KEY.GreyLeftArrow := "{Left}", KEY.GreyRightArrow := "{Right}"

; ---- the mapping -----------------------------------------------------------
; F-16 grip convention on the left, what I'76 calls it on the right. The key is
; whatever input.map already binds that action to.
;
;   trigger        gun                 -> weapon_fire      Enter
;   pickle (thumb) weapon release      -> special1         6
;   thumb          -                   -> weapon_cycle     Tab
;   pinky/paddle   NWS / AR disconnect -> HONK_HORN        G
;   castle hat     view / head-look    -> pilot_glance_*   grey arrows
;   TMS  4-way     target management   -> target actions   T Y U Q
;   DMS  4-way     display management  -> map/radar/optics M R V B
;
; CH's DOCUMENTED default numbering - 1 trigger, 2-4 thumb, then the 4-way hats in
; blocks of four - NOT measured on this unit, and the 3-position mode switch
; renumbers everything. Run -learn and correct this table.
global BTN := {}
BTN[1]  := "Enter"    ; trigger   -> weapon_fire
BTN[2]  := "Six"      ; pickle    -> special1
BTN[3]  := "Tab"      ; thumb     -> weapon_cycle
BTN[4]  := "G"        ; pinky     -> HONK_HORN
; Upper-left hat = DMS on a real A-10C grip (display/sensor management), so it
; gets I'76's display actions. Order within each hat is up/right/down/left and is
; NOT yet measured - see docs/FIGHTERSTICK.md.
BTN[5]  := "M"        ; DMS up    -> SHOW_MAP
BTN[6]  := "R"        ; DMS right -> RADAR_RANGE_TOGGLE
BTN[7]  := "V"        ; DMS down  -> toggle_cmbt_view
BTN[8]  := "B"        ; DMS left  -> TOGGLE_BINOCULARS
; SIDE/RIGHT hat = CMS (countermeasures). NOTE the numbering: CH's documentation
; puts the lower hat on 9-12 and the right hat on 13-16. MEASURED on this unit
; (2026-08-08, -learn) it is the OTHER WAY ROUND - the right hat reports 9-12 and
; the lower hat reports 13-16. Trust the measurement, not the sheet.
BTN[9]  := "Seven"    ; CMS up    -> special2
BTN[10] := "Eight"    ; CMS right -> special3
BTN[11] := "E"        ; CMS down  -> pilot_glance_target
BTN[12] := "I"        ; CMS left  -> start_engine
; LOWER/CENTRE hat = TMS (target management). Closest I'76 analogue by far.
BTN[13] := "T"        ; TMS up    -> TARGET_NEAREST_ENEMY
BTN[14] := "Y"        ; TMS right -> NEXT_TARGET
BTN[15] := "U"        ; TMS down  -> RESET_TARGET
BTN[16] := "Q"        ; TMS left  -> frontal_target

; The 8-way castle hat is head-look, exactly as on a real grip.
global POVKEY := ["GreyUpArrow", "GreyRightArrow", "GreyDownArrow", "GreyLeftArrow"]

; ---- the ADC ---------------------------------------------------------------
; EDGE vs LEVEL is the whole design:
;   shift_up/down are EDGE - one gearchange per movement. The stick must return
;   through RELEASE before it fires again, which is how a sequential gate behaves;
;   you cannot hold it forward and climb through the gears.
;   e_brake is LEVEL - held for as long as the stick is over. A handbrake you had
;   to tap would be useless.
; Layout chosen at the wheel, 2026-08-08, and it is better than the first guess:
; the handbrake is the gesture you make most violently, so it gets the strongest,
; most natural pull; reverse is a held state rather than a latched one; and the
; shifts move to left/right where they are out of the way of both.
global AXIS := []
AXIS.Push({axis: "Y", dir:  1, key: "Space",  mode: "level",     name: "e_brake"})
AXIS.Push({axis: "Y", dir: -1, key: "X",      mode: "momentary", name: "reverse_while_held"})
AXIS.Push({axis: "X", dir: -1, key: "Comma",  mode: "edge",      name: "shift_down"})
AXIS.Push({axis: "X", dir:  1, key: "Period", mode: "edge",      name: "shift_up"})

; ---- args ------------------------------------------------------------------
mode := "run"
for i, a in A_Args {
    if (a = "-learn")
        mode := "learn"
    else if (a = "-selftest")
        mode := "selftest"
    else if (a = "-whatif")
        WHATIF := true
    else if (a = "-device")
        DEV := A_Args[i + 1]
}

; ============================================================================
; The axis state machine: a PURE function of (deflection, state), so -selftest can
; exercise it with no hardware. This is the part that is easy to get subtly wrong
; and impossible to debug halfway through a mission.
; Returns "down" | "up" | "pulse" | "".
; ============================================================================
StepAxis(defl, state, mode, on, off) {
    isOn  := (defl >= on)
    isOff := (defl < off)
    if (mode = "level") {
        if (isOn && !state.held) {
            state.held := true
            return "down"
        }
        if (isOff && state.held) {
            state.held := false
            return "up"
        }
        return ""
    }
    ; MOMENTARY: pulse on the way IN and again on the way OUT.
    ;
    ; This exists for reverse. I'76's reverse_direction is a TOGGLE - tapping X
    ; flips between forward and reverse - so holding the key down does NOT hold
    ; reverse, and "level" would leave the car stuck in reverse after the stick
    ; recentred. Two taps against a toggle give the momentary behaviour the toggle
    ; itself cannot: in reverse while deflected, back to forward on release.
    if (mode = "momentary") {
        if (isOn && !state.held) {
            state.held := true
            return "pulse"
        }
        if (isOff && state.held) {
            state.held := false
            return "pulse"
        }
        return ""
    }
    if (isOn && state.armed) {
        state.armed := false
        return "pulse"
    }
    if (isOff)
        state.armed := true
    return ""
}

; AHK reports axes 0..100 with centre at 50; the design works in -1..+1.
Norm(v) {
    n := (v - 50.0) / 50.0
    return (n > 1) ? 1 : (n < -1) ? -1 : n
}

Out(s) {
    FileAppend, %s%`n, *
}

SendKey(name, down := "") {
    global KEY, WHATIF
    if (!KEY.HasKey(name)) {
        Out("  no key mapping for '" name "'")
        return
    }
    if (WHATIF)
        return
    k := KEY[name]
    if (down = "")
        Send, %k%                              ; tap
    else if (down) {
        k := SubStr(k, 1, -1) . " down}"
        Send, %k%
    } else {
        k := SubStr(k, 1, -1) . " up}"
        Send, %k%
    }
}

; ============================================================================
if (mode = "selftest") {
    fails := 0
    Out("`nADC state machine")
    ; EDGE - a sequential gate. One shift per movement, no repeats while held.
    s := {held: false, armed: true}
    fails += Check("edge: centred does nothing",              StepAxis(0.00, s, "edge", 0.55, 0.35), "")
    fails += Check("edge: crossing threshold shifts",         StepAxis(0.60, s, "edge", 0.55, 0.35), "pulse")
    fails += Check("edge: HELD forward does NOT shift again", StepAxis(0.90, s, "edge", 0.55, 0.35), "")
    fails += Check("edge: still held, still nothing",         StepAxis(0.70, s, "edge", 0.55, 0.35), "")
    fails += Check("edge: inside hysteresis does not re-arm", StepAxis(0.45, s, "edge", 0.55, 0.35), "")
    fails += Check("edge: back past release re-arms",         StepAxis(0.10, s, "edge", 0.55, 0.35), "")
    fails += Check("edge: now it shifts again",               StepAxis(0.60, s, "edge", 0.55, 0.35), "pulse")
    ; LEVEL - a handbrake. Held down for as long as the stick is over.
    s := {held: false, armed: true}
    fails += Check("level: centred does nothing",             StepAxis(0.00, s, "level", 0.55, 0.35), "")
    fails += Check("level: crossing pulls the key down",      StepAxis(0.60, s, "level", 0.55, 0.35), "down")
    fails += Check("level: staying over holds it",            StepAxis(0.95, s, "level", 0.55, 0.35), "")
    fails += Check("level: inside hysteresis stays held",     StepAxis(0.45, s, "level", 0.55, 0.35), "")
    fails += Check("level: recentring releases",              StepAxis(0.10, s, "level", 0.55, 0.35), "up")
    fails += Check("level: staying centred does nothing",     StepAxis(0.00, s, "level", 0.55, 0.35), "")
    ; MOMENTARY - reverse. Pulses IN and OUT, because reverse_direction is a toggle:
    ; one tap enters reverse, the second returns to forward. A missing exit pulse
    ; leaves the car stuck in reverse with the stick centred, which is the exact
    ; failure this mode exists to prevent.
    s := {held: false, armed: true}
    fails += Check("momentary: centred does nothing",         StepAxis(0.00, s, "momentary", 0.55, 0.35), "")
    fails += Check("momentary: pushing in taps into reverse", StepAxis(0.60, s, "momentary", 0.55, 0.35), "pulse")
    fails += Check("momentary: HELD does not re-tap",         StepAxis(0.90, s, "momentary", 0.55, 0.35), "")
    fails += Check("momentary: hysteresis band holds it",     StepAxis(0.45, s, "momentary", 0.55, 0.35), "")
    fails += Check("momentary: releasing taps back OUT",      StepAxis(0.10, s, "momentary", 0.55, 0.35), "pulse")
    fails += Check("momentary: centred again does nothing",   StepAxis(0.00, s, "momentary", 0.55, 0.35), "")
    fails += Check("momentary: second push re-enters",        StepAxis(0.60, s, "momentary", 0.55, 0.35), "pulse")

    Out("`nAxis normalisation (AHK reports 0-100, centre 50)")
    fails += Check("centre reads 0",       Round(Norm(50), 2),  0)
    fails += Check("full left  = -1",      Round(Norm(0), 2),  -1)
    fails += Check("full right = +1",      Round(Norm(100), 2), 1)
    fails += Check("out-of-range clamps",  Round(Norm(140), 2), 1)
    fails += Check("resting 50.4 is inside the deadzone", (Abs(Norm(50.4)) < 0.35) ? 1 : 0, 1)

    Out("")
    if (fails) {
        Out(fails " FAILED")
        ExitApp, 1
    }
    Out("all passed")
    ExitApp, 0
}

Check(what, got, want) {
    ok := (got = want)
    pad := SubStr(what . "                                                        ", 1, 52)
    Out("  " (ok ? "ok  " : "FAIL") " " pad " got '" got "' want '" want "'")
    return ok ? 0 : 1
}

; ============================================================================
; Documented AHK quirk (i76-gamepad-axistest.ahk): query an axis once before the
; polling loop or axis reads do not initialise.
GetKeyState(DEV . "JoyX")
name := GetKeyState(DEV . "JoyName")
if (name = "") {
    Out("joystick" DEV " is not present. Devices AHK can see:")
    Loop, 16 {
        n := GetKeyState(A_Index . "JoyName")
        if (n != "")
            Out("    joystick" A_Index "  " n "  (" GetKeyState(A_Index . "JoyButtons") " buttons)")
    }
    ExitApp, 1
}
Out("joystick" DEV ": " name " - " GetKeyState(DEV . "JoyButtons") " buttons, " GetKeyState(DEV . "JoyAxes") " axes")

if (mode = "learn") {
    Out("`nPress each control one at a time, in the checklist order. Ctrl+C to stop.`n")
    ; prevBtn is created here as well as on the run path: LearnPoll calls
    ; prevBtn.HasKey(), and -learn never reaches the run path's initialisation.
    global prevPov := -1, seq := 0, prevBtn := {}
    SetTimer, LearnPoll, %POLL%
    return
}

Out("")
Out("  pull back = HANDBRAKE (held)    push forward = REVERSE (while held)")
Out("  left = shift down               right = shift up")
Out("  threshold " Round(THRESH * 100) "% on, " Round(RELEASE * 100) "% off")
if (WHATIF)
    Out("  -whatif: showing actions, sending NO keys")
Out("  Ctrl+C to stop.`n")

global state := {}
for i, a in AXIS
    state[a.name] := {held: false, armed: true}
global heldKeys := {}
global prevBtn  := {}
global prevPovIx := -1

SetTimer, Poll, %POLL%
return

; ---------------------------------------------------------------------------
Poll:
    ; buttons: straight through, held for as long as they are held
    Loop, 32 {
        b := A_Index
        if (!BTN.HasKey(b))
            continue
        down := GetKeyState(DEV . "Joy" . b)
        was  := prevBtn.HasKey(b) ? prevBtn[b] : 0
        if (down != was) {
            SendKey(BTN[b], down ? 1 : 0)
            if (down)
                Out("  Button" b " -> " BTN[b])
            prevBtn[b] := down
        }
    }

    ; castle hat: head-look, held while deflected. AHK gives -1 when centred and
    ; 0..35900 centidegrees otherwise. Folded into 4 sectors so the 8-way diagonals
    ; fall through to the nearer cardinal rather than doing nothing.
    pov := GetKeyState(DEV . "JoyPOV")
    povIx := -1
    if (pov >= 0)
        povIx := Mod(Round(pov / 9000), 4)
    if (povIx != prevPovIx) {
        if (prevPovIx >= 0)
            SendKey(POVKEY[prevPovIx + 1], 0)
        if (povIx >= 0) {
            SendKey(POVKEY[povIx + 1], 1)
            Out("  hat " POVKEY[povIx + 1] " -> glance")
        }
        prevPovIx := povIx
    }

    ; the ADC
    nx := Norm(GetKeyState(DEV . "JoyX"))
    ny := Norm(GetKeyState(DEV . "JoyY"))
    for i, a in AXIS {
        v := (a.axis = "X") ? nx : ny
        ev := StepAxis(v * a.dir, state[a.name], a.mode, THRESH, RELEASE)
        if (ev = "down") {
            SendKey(a.key, 1)
            heldKeys[a.key] := 1
            Out("  " a.name " ON")
        } else if (ev = "up") {
            SendKey(a.key, 0)
            heldKeys[a.key] := 0
            Out("  " a.name " off")
        } else if (ev = "pulse") {
            SendKey(a.key)
            Out("  " a.name)
        }
    }
return

LearnPoll:
    ; Numbered, because the press order is what identifies each control. With 19
    ; buttons and a fixed checklist, an unnumbered list of hits cannot be matched
    ; back to what was actually pressed.
    Loop, 32 {
        b := A_Index
        down := GetKeyState(DEV . "Joy" . b)
        was  := prevBtn.HasKey(b) ? prevBtn[b] : 0
        if (down && !was) {
            seq += 1
            Out("  #" seq "`tButton " b "`t-> currently sends '" (BTN.HasKey(b) ? BTN[b] : "(UNMAPPED)") "'")
        }
        prevBtn[b] := down
    }
    ; The POV is reported on its own channel, NOT as buttons - worth showing
    ; distinctly, because CH's own docs suggest it may appear as button IDs up to
    ; 24 "depending on configuration", and which of those is true here decides
    ; whether the castle hat needs button handling or POV handling.
    pov := GetKeyState(DEV . "JoyPOV")
    if (pov != prevPov) {
        if (pov >= 0) {
            seq += 1
            dirs := ["UP", "up-right", "RIGHT", "down-right", "DOWN", "down-left", "LEFT", "up-left"]
            Out("  #" seq "`tPOV hat`t-> " Round(pov / 100) " deg  (" dirs[Mod(Round(pov / 4500), 8) + 1] ")")
        }
        prevPov := pov
    }
return

; Never leave a key stuck down: a held Space is a handbrake the player cannot
; release, and it would survive this script exiting.
ReleaseAll() {
    global heldKeys, prevPovIx, POVKEY
    ; Guarded because OnExit fires on EVERY exit path, including -selftest, which
    ; returns before heldKeys/prevPovIx are ever created. Iterating an unset
    ; variable as an object throws, and an exit handler that throws is a bad way
    ; to discover this.
    if (IsObject(heldKeys)) {
        for k, v in heldKeys {
            if (v)
                SendKey(k, 0)
        }
    }
    if (prevPovIx != "" && prevPovIx >= 0)
        SendKey(POVKEY[prevPovIx + 1], 0)
}

OnExitHandler:
    ReleaseAll()
ExitApp
