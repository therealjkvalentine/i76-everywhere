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
; TRAY ICON KEPT, deliberately differing from i76-remap.ahk which sets #NoTrayIcon.
; That one runs inside the Wine prefix where there is no usable tray and its
; lifetime is the game session's. This one is launched by hand alongside a
; fullscreen game, and without an icon it runs with no window, no tray entry and
; no way to stop it short of Task Manager - while holding a key down. The icon is
; the visible proof it is running and the way to quit it.
#SingleInstance Force
#Persistent
; A runaway cannot happen here - this is a polled timer, not a hotkey - but the
; rate-limit warning is a modal MsgBox, and a modal is unacceptable (see above).
#MaxHotkeysPerInterval 200000
#ErrorStdOut
SetBatchLines, -1

; WHY THERE IS A WINDOW, AND WHY NOT A CONSOLE.
;
; AutoHotkey.exe is a GUI-subsystem binary: it gets no console of its own, so
; `FileAppend ... , *` writes into nothing when the script is launched
; interactively from a terminal. It DOES work when stdout is a pipe or a file -
; which is exactly how every automated test of this script ran. The tests passed
; while a human running the same command by hand saw dead silence.
;
; The obvious fix, DllCall("AttachConsole", -1), was tried and REVERTED. Attaching
; unconditionally breaks the redirected case - writes land on the console instead
; of the pipe, so `script -selftest > out.txt` yields an empty file. Gating it on
; GetFileType(GetStdHandle(-11)) to attach only when stdout is unused did not
; restore output either. Both were measured, not theorised.
;
; So stdout is left exactly as it was - correct whenever it is redirected or piped,
; which is every scripted use - and the interactive modes get a real window
; instead. A window is guaranteed visible regardless of how the script was
; launched, which the console never was.
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
KEY.B := "{SC030}", KEY.E := "{SC012}", KEY.F := "{SC021}", KEY.G := "{SC022}"
KEY.H := "{SC023}", KEY.I := "{SC017}", KEY.K := "{SC025}", KEY.M := "{SC032}"
KEY.N := "{SC031}", KEY.P := "{SC019}", KEY.Q := "{SC010}", KEY.R := "{SC013}"
KEY.T := "{SC014}", KEY.U := "{SC016}", KEY.V := "{SC02F}", KEY.X := "{SC02D}"
KEY.Y := "{SC015}"
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
; ---------------------------------------------------------------------------
; THE MAP. One entry per physical control, carrying three things:
;   ctl - what the control IS, by its official name (see the table below)
;   act - the I'76 action it performs, spelled as input.map spells it
;   key - the key input.map binds that action to
; Keep all three. `-map` prints them as a reference card, and the live display
; names the ACTION rather than the key, because "Button 9 -> T" tells you nothing
; while "castle UP -> TARGET_NEAREST_ENEMY" tells you everything.
;
; OFFICIAL HAT NAMES for the CH Fighterstick, so there is no ambiguity ever again
; (the earlier "upper-left / lower / side-right" wording caused exactly that):
;
;   cone hat             8-way POV, upper right of the top face  -> POV channel
;   convex serrated hat  leftmost on the top face                -> buttons 5-8
;   castle hat           lower right of the top face             -> buttons 9-12
;   trim hat             concave, halfway up the stick shaft     -> buttons 13-16
;
; Every hat's direction order is UP, RIGHT, DOWN, LEFT - measured 2026-08-08.
; Role assignment follows the A-10C convention by BUTTON NUMBER: 5-8 DMS,
; 9-12 TMS, 13-16 CMS.
global BTN := {}
BTN[1]  := {ctl: "trigger",              act: "weapon_fire",          key: "Enter"}
BTN[2]  := {ctl: "top red (pickle)",     act: "special1",             key: "Six"}
; Button 3 is the MODE SWITCH - it cycles the base LED through three positions,
; and on CH sticks the mode renumbers the buttons. Deliberately UNMAPPED: binding
; a game action to it means every mode change also fires that action.
BTN[4]  := {ctl: "pinky red",            act: "weapon_link",          key: "F"}
; --- convex serrated hat = DMS, display and sensor management ---
BTN[5]  := {ctl: "serrated UP",          act: "SHOW_MAP",             key: "M"}
BTN[6]  := {ctl: "serrated RIGHT",       act: "RADAR_RANGE_TOGGLE",   key: "R"}
BTN[7]  := {ctl: "serrated DOWN",        act: "SHOW_NOTEPAD",         key: "N"}
BTN[8]  := {ctl: "serrated LEFT",        act: "RADAR_CAMERA_TOGGLE",  key: "K"}
; --- castle hat = TMS, target management ---
BTN[9]  := {ctl: "castle UP",            act: "TARGET_NEAREST_ENEMY", key: "T"}
BTN[10] := {ctl: "castle RIGHT",         act: "NEXT_TARGET",          key: "Y"}
BTN[11] := {ctl: "castle DOWN",          act: "RESET_TARGET",         key: "U"}
BTN[12] := {ctl: "castle LEFT",          act: "frontal_target",       key: "Q"}
; --- trim hat = CMS, countermeasures and armament ---
BTN[13] := {ctl: "trim UP",              act: "special2",             key: "Seven"}
BTN[14] := {ctl: "trim RIGHT",           act: "special3",             key: "Eight"}
BTN[15] := {ctl: "trim DOWN",            act: "weapon_cycle",         key: "Tab"}
BTN[16] := {ctl: "trim LEFT",            act: "toggle_cmbt_view",     key: "V"}

; The CONE hat (8-way POV) is head-look, exactly as on a real grip - the control
; that transfers most directly of anything here. Index order is up/right/down/left
; to match the sector maths below.
global POV := []
POV.Push({ctl: "cone UP",    act: "pilot_glance_up",    key: "GreyUpArrow"})
POV.Push({ctl: "cone RIGHT", act: "pilot_glance_right", key: "GreyRightArrow"})
POV.Push({ctl: "cone DOWN",  act: "pilot_glance_down",  key: "GreyDownArrow"})
POV.Push({ctl: "cone LEFT",  act: "pilot_glance_left",  key: "GreyLeftArrow"})

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
AXIS.Push({ctl: "stick BACK",    axis: "Y", dir:  1, key: "Space",  mode: "level",     act: "e_brake",           name: "e_brake"})
AXIS.Push({ctl: "stick FORWARD", axis: "Y", dir: -1, key: "X",      mode: "momentary", act: "reverse_direction", name: "reverse_while_held"})
AXIS.Push({ctl: "stick LEFT",    axis: "X", dir: -1, key: "Comma",  mode: "edge",      act: "shift_down",        name: "shift_down"})
AXIS.Push({ctl: "stick RIGHT",   axis: "X", dir:  1, key: "Period", mode: "edge",      act: "shift_up",          name: "shift_up"})

; ---- args ------------------------------------------------------------------
mode := "run"
for i, a in A_Args {
    if (a = "-learn")
        mode := "learn"
    else if (a = "-selftest")
        mode := "selftest"
    else if (a = "-map")
        mode := "map"
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

global LOGLINES := []
global GUIREADY := false

Out(s) {
    global LOGLINES, GUIREADY
    FileAppend, %s%`n, *
    if (!GUIREADY)
        return
    ; Mirror into the window. Console output cannot be relied on - see AttachConsole
    ; above - and a bench tool you watch while pressing things needs somewhere to
    ; look that is guaranteed to exist.
    LOGLINES.Push(s)
    while (LOGLINES.Length() > 24)
        LOGLINES.RemoveAt(1)
    txt := ""
    for i, l in LOGLINES
        txt .= l "`n"
    GuiControl, Log:, LogBox, %txt%
}

; A plain window, NOT a MsgBox. The no-modal-dialogs rule inherited from
; i76-remap.ahk is about MODAL dialogs stealing foreground focus and going
; invisible behind DxWnd's backdrop; a normal window does neither. The precedent
; is i76-gamepad-axistest.ahk, which shows live joystick state the same way.
;
; +E0x08000000 is WS_EX_NOACTIVATE: the window can never take focus, so it cannot
; pull the game out of the foreground while you are watching it.
InitGui(title) {
    ; LogBox MUST be declared global. A GUI control's associated variable (vLogBox)
    ; has to be a global in AHK v1; created inside a function without this it binds
    ; to a local, and the window silently fails to appear at all - no error, no
    ; window, script runs on regardless. Verified: the identical Gui commands at the
    ; top level produce a window, and inside a function without this line they do not.
    global GUIREADY, LogBox
    Gui, Log:New, +AlwaysOnTop +E0x08000000 +Resize, %title%
    Gui, Log:Color, 0x101010
    Gui, Log:Font, s9 cC8C8C8, Consolas
    Gui, Log:Add, Edit, vLogBox w660 h380 ReadOnly -WantReturn
    Gui, Log:Show, NoActivate w680 h400, %title%
    GUIREADY := true
}
; NB: the LogGuiClose/LogGuiEscape labels for this window live at the BOTTOM of the
; script, with the other labels. They were briefly defined here, and that silently
; broke everything: in AHK v1 the auto-execute section ENDS at the first label, so
; execution stopped at this point in the file and never reached the mode dispatch
; below. Every mode exited 0 having printed nothing - which looks exactly like a
; broken redirect, and cost a round of chasing AttachConsole for a bug it never had.

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

; Game actions that have a keyboard binding in input.map but are NOT on the stick.
; Kept here so `-map` can show the whole picture: what a control does AND what is
; still available to move onto one. Audited against the live input.map 2026-08-08 -
; 54 actions carry a key, 24 of them are bound here.
; Explicit Push calls rather than one multi-line array literal: AHK v1.1 treats a
; leading comma as a line continuation and mis-parsed the literal, and a bare
; semicolon inside a string is a comment waiting to happen. Verbose, but it parses.
global UNMAPPED := []
UNMAPPED.Push(["toggle_lights",                  "H"])
UNMAPPED.Push(["TOGGLE_BINOCULARS",              "B"])
UNMAPPED.Push(["HONK_HORN",                      "G"])
UNMAPPED.Push(["start_engine",                   "I"])
UNMAPPED.Push(["pilot_glance_target",            "E"])
UNMAPPED.Push(["POETRY",                         "P"])
UNMAPPED.Push(["hardpoint2_fire .. hardpoint5_fire", "2 3 4 5"])
UNMAPPED.Push(["zoom_factor minus / plus / reset",   "PgUp PgDn End"])
UNMAPPED.Push(["show_player_scores / show_team_scores", "quote / semicolon"])
UNMAPPED.Push(["overview_ (map view pan and zoom)",  "arrows PgUp PgDn"])
UNMAPPED.Push(["track_ (external camera)",           "arrows PgUp PgDn"])

; ============================================================================
if (mode = "map") {
    Out("`nCH FIGHTERSTICK -> INTERSTATE '76")
    Out("`n  STICK (the ADC - analog deflection becomes a discrete action)")
    Out("  " Pad("control", 18) Pad("game action", 26) Pad("key", 7) "behaviour")
    Out("  " Pad("", 60, "-"))
    for i, a in AXIS
        Out("  " Pad(a.ctl, 18) Pad(a.act, 26) Pad(a.key, 7) a.mode)
    Out("`n  CONE HAT (8-way POV, upper right of the top face) - head-look")
    for i, p in POV
        Out("  " Pad(p.ctl, 18) Pad(p.act, 26) p.key)
    Out("`n  BUTTONS")
    Out("  " Pad("#", 5) Pad("control", 18) Pad("game action", 26) "key")
    Out("  " Pad("", 60, "-"))
    Loop, 32 {
        if (BTN.HasKey(A_Index))
            Out("  " Pad(A_Index, 5) Pad(BTN[A_Index].ctl, 18) Pad(BTN[A_Index].act, 26) BTN[A_Index].key)
        else if (A_Index = 3)
            Out("  " Pad(3, 5) Pad("back-side red", 18) "MODE SWITCH - deliberately unbound")
    }
    Out("`n  NOT ON THE STICK (bound to the keyboard, free to move here)")
    for i, u in UNMAPPED
        Out("  " Pad(u[1], 44) u[2])
    Out("")
    ExitApp, 0
}

Pad(s, n, ch := " ") {
    out := s
    while (StrLen(out) < n)
        out .= ch
    return out
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
; Everything from here on is an interactive mode - it watches the stick and keeps
; running - so give it a window. -map and -selftest print and exit above, and are
; fine on stdout alone.
InitGui("I76 Fighterstick" . (mode = "learn" ? " - LEARN" : (WHATIF ? " - BENCH TEST (no keys sent)" : "")))

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

; Name the tray entry so it is identifiable at a glance among other AHK scripts,
; and give it an Exit that runs ReleaseAll via OnExit rather than killing blind.
Menu, Tray, Tip, % "I76 Fighterstick" . (WHATIF ? " (-whatif, no keys)" : "")
Menu, Tray, NoStandard
Menu, Tray, Add, I76 Fighterstick - right-click to quit, TrayNoop
Menu, Tray, Disable, I76 Fighterstick - right-click to quit
Menu, Tray, Add
Menu, Tray, Add, Exit (releases held keys), TrayExit
Menu, Tray, Default, Exit (releases held keys)

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
            SendKey(BTN[b].key, down ? 1 : 0)
            if (down)
                Out("  " BTN[b].ctl "`t-> " BTN[b].act)
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
            SendKey(POV[prevPovIx + 1].key, 0)
        if (povIx >= 0) {
            SendKey(POV[povIx + 1].key, 1)
            Out("  " POV[povIx + 1].ctl "`t-> " POV[povIx + 1].act)
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
            Out("  " a.ctl "`t-> " a.act " ON")
        } else if (ev = "up") {
            SendKey(a.key, 0)
            heldKeys[a.key] := 0
            Out("  " a.ctl "`t-> " a.act " off")
        } else if (ev = "pulse") {
            SendKey(a.key)
            Out("  " a.ctl "`t-> " a.act)
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
            lbl := BTN.HasKey(b) ? (BTN[b].ctl " = " BTN[b].act) : "(UNMAPPED)"
            Out("  #" seq "`tButton " b "`t-> " lbl)
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
    global heldKeys, prevPovIx, POV
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
        SendKey(POV[prevPovIx + 1].key, 0)
}

LogGuiClose:
LogGuiEscape:
    ExitApp          ; OnExit fires -> ReleaseAll()
return

TrayNoop:
return

TrayExit:
    ExitApp          ; OnExit fires -> ReleaseAll(), so nothing is left held down
return

OnExitHandler:
    ReleaseAll()
ExitApp
