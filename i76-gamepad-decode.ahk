; Interstate '76 - gamepad DECODE HARNESS (AutoHotkey v1.1, runs in the prefix).
; Guided: it names each Xbox control, you actuate it, and it auto-detects which
; winmm Joy button / axis fired - writing an exact mapping to C:\AutoHotkey\
; joymap.txt that we read back to build the final input.map + AHK layer. No
; eyeballing raw numbers, no transcription. A live raw panel shows underneath as
; a fallback if auto-detect ever misfires.
;
; RUN STANDALONE, GAME QUIT: launch via `./setup-input-remapper.sh --decode`.
; The game's DxWnd HideDesktop backdrop would hide this window (same trap that
; hid the rate-limit dialog), so the game must NOT be running. Connect the pad
; BEFORE launching (winmm enumerates joysticks once, at startup).
;
; Controls while it runs:  [S]=skip this step   [R]=restart   [Esc]=quit+save
#NoEnv
#SingleInstance Force
#Persistent
#InstallKeybdHook

OUT := "C:\AutoHotkey\joymap.txt"
THRESH := 30            ; axis counts as "deflected" at >30 from its own rest (0-100 scale)
CENTER := 12            ; and "re-centered" within 12 of rest

; --- find the joystick (first index that reports a name) ---
joy := 0
Loop, 16 {
    if (GetKeyState(A_Index . "JoyName") != "") {
        joy := A_Index
        break
    }
}
if (!joy) {
    MsgBox, 48, I76 Gamepad Decode, No joystick detected.`n`nConnect the Xbox pad BEFORE launching this, then re-run.
    ExitApp
}
jName := GetKeyState(joy . "JoyName")
jBtns := GetKeyState(joy . "JoyButtons")
jAxes := GetKeyState(joy . "JoyAxes")

; --- capture the resting baseline of every axis (sticks ~50, triggers ~50, V~0) ---
global AX := ["X","Y","Z","R","U","V"]
global rest := {}
for i, a in AX
    rest[a] := GetKeyState(joy . "Joy" . a)

; --- the guided sequence: label, result-key, type ("button" | "axis") ---
global steps := []
steps.Push({t:"button", k:"A",     l:"A  (bottom face button)"})
steps.Push({t:"button", k:"B",     l:"B  (right face button)"})
steps.Push({t:"button", k:"X",     l:"X  (left face button)"})
steps.Push({t:"button", k:"Y",     l:"Y  (top face button)"})
steps.Push({t:"button", k:"LB",    l:"LB (left bumper)"})
steps.Push({t:"button", k:"RB",    l:"RB (right bumper)"})
steps.Push({t:"button", k:"BACK",  l:"BACK / VIEW  (the two-squares button)"})
steps.Push({t:"button", k:"START", l:"START / MENU (the hamburger button)"})
steps.Push({t:"button", k:"L3",    l:"L3 (press the LEFT stick straight in)"})
steps.Push({t:"button", k:"R3",    l:"R3 (press the RIGHT stick straight in)"})
steps.Push({t:"axis",   k:"LS_right", l:"LEFT stick -> push fully RIGHT"})
steps.Push({t:"axis",   k:"LS_down",  l:"LEFT stick -> push fully DOWN"})
steps.Push({t:"axis",   k:"RS_right", l:"RIGHT stick -> push fully RIGHT"})
steps.Push({t:"axis",   k:"RS_down",  l:"RIGHT stick -> push fully DOWN"})
steps.Push({t:"trig",   k:"RT",    l:"RIGHT TRIGGER (RT) -> squeeze fully"})
steps.Push({t:"trig",   k:"LT",    l:"LEFT TRIGGER (LT) -> squeeze fully"})
steps.Push({t:"pov",    k:"DP_up",    l:"D-PAD -> press UP"})
steps.Push({t:"pov",    k:"DP_right", l:"D-PAD -> press RIGHT"})

global idx := 1
global phase := "await"      ; await -> (capture) -> release/center -> next
global results := {}
global logLines := ""

Gui, +AlwaysOnTop +ToolWindow
Gui, Color, 101010
Gui, Font, s14 cWhite, Consolas
Gui, Add, Text, w620 vHdr, % "I76 GAMEPAD DECODE - " . jName . "  (" . jBtns . " buttons, " . jAxes . " axes)"
Gui, Font, s20 cAqua Bold, Consolas
Gui, Add, Text, w620 vPrompt, (starting...)
Gui, Font, s12 cSilver Bold, Consolas
Gui, Add, Text, w620 vStatus, .
Gui, Font, s10 cGray, Consolas
Gui, Add, Text, w620 h150 vLog, .
Gui, Add, Text, w620 vRaw, .
Gui, Font, s9 c808080, Consolas
Gui, Add, Text, w620, [S] skip step   [R] restart   [Esc] quit + save
Gui, Show, , I76 Gamepad Decode
ShowStep()
SetTimer, Poll, 30
return

ShowStep() {
    global
    if (idx > steps.MaxIndex()) {
        GuiControl,, Prompt, ALL DONE - saved. You can close this window.
        GuiControl,, Status, % "Wrote " . OUT
        return
    }
    st := steps[idx]
    GuiControl,, Prompt, % "Press:  " . st.l
    GuiControl,, Status, % "step " . idx . " / " . steps.MaxIndex() . "   (phase: " . phase . ")"
}

; return the first pressed button number (1..jBtns), or 0
FirstButton() {
    global joy, jBtns
    Loop, % jBtns {
        if GetKeyState(joy . "Joy" . A_Index)
            return A_Index
    }
    return 0
}
AnyButton() {
    return FirstButton() > 0
}
; largest-deviation axis vs rest -> returns "AXIS+"/"AXIS-" and magnitude via ByRef
BiggestAxis(ByRef mag) {
    global joy, AX, rest
    best := "", mag := 0
    for i, a in AX {
        v := GetKeyState(joy . "Joy" . a)
        d := v - rest[a]
        ad := abs(d)
        if (ad > mag) {
            mag := ad
            best := a . (d >= 0 ? "+" : "-")
        }
    }
    return best
}
AxesCentered() {
    global joy, AX, rest, CENTER
    for i, a in AX {
        if (abs(GetKeyState(joy . "Joy" . a) - rest[a]) > CENTER)
            return false
    }
    return true
}
Record(key, val) {
    global results, logLines, OUT
    results[key] := val
    logLines .= key . " = " . val . "`n"
    GuiControl,, Log, % logLines
    ; persist incrementally so a mid-run quit still yields partial data
    FileDelete, %OUT%
    header := "I76 gamepad decode`njoystick=" . GetKeyState(1 . "JoyName") . "`n---`n"
    FileAppend, % header . logLines, %OUT%
}

Poll:
    ; --- live raw panel (always) ---
    raw := "raw:  "
    for i, a in AX
        raw .= a "=" Round(GetKeyState(joy . "Joy" . a)) "  "
    pov := GetKeyState(joy . "JoyPOV")
    raw .= "POV=" pov "  btns:"
    Loop, % jBtns
        raw .= GetKeyState(joy . "Joy" . A_Index) ? " " A_Index : ""
    GuiControl,, Raw, % raw

    if (idx > steps.MaxIndex())
        return
    st := steps[idx]

    if (phase = "await") {
        if (st.t = "button") {
            b := FirstButton()
            if (b) {
                Record(st.k, "Joy" . b)
                phase := "release"
            }
        } else if (st.t = "axis" || st.t = "trig") {
            mag := 0
            ax := BiggestAxis(mag)
            if (mag > THRESH) {
                Record(st.k, "Joy" . ax . "  (rest " . Round(rest[SubStr(ax,1,1)]) . " -> " . Round(GetKeyState(joy . "Joy" . SubStr(ax,1,1))) . ")")
                phase := "center"
            }
        } else if (st.t = "pov") {
            if (pov >= 0) {
                Record(st.k, "POV=" . pov)
                phase := "center"
            }
        }
    } else if (phase = "release") {
        if (!AnyButton()) {
            idx += 1, phase := "await"
            ShowStep()
        }
    } else if (phase = "center") {
        centered := (st.t = "pov") ? (GetKeyState(joy . "JoyPOV") < 0) : AxesCentered()
        if (centered) {
            idx += 1, phase := "await"
            ShowStep()
        }
    }
return

; --- hotkeys: S skip, R restart, Esc quit+save ---
*s::
    if (idx <= steps.MaxIndex()) {
        Record(steps[idx].k, "(skipped)")
        idx += 1, phase := "await"
        ShowStep()
    }
return
*r::
    idx := 1, phase := "await", results := {}, logLines := ""
    GuiControl,, Log,
    ShowStep()
return
*Esc::
GuiClose:
    FileAppend, `n(session ended at step %idx%)`n, %OUT%
    ExitApp
return
