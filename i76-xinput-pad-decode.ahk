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
THRESH := 25            ; axis counts as "deflected" at >25 from its own rest (0-100 scale)
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

; documented AHK+Wine quirk: joystick axes read a STALE ~50 until the device is
; queried once to kick off polling. Without this the decode harness (2026-07-14)
; saw every axis frozen at center - the "analog didn't register" bug. Warm it up,
; settle, then baseline. Axes ARE readable via GetKeyState (proven by the axis
; test: X/Y span the full 0-100 when the stick moves).
GetKeyState(joy . "JoyX")
Sleep, 300

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
    ; re-baseline the axes at the moment an analog step begins (the prior step's
    ; "center" phase guarantees the sticks are back at rest), so detection is
    ; immune to warmup/drift.
    if (st.t = "axis" || st.t = "trig") {
        for i, a in AX
            rest[a] := GetKeyState(joy . "Joy" . a)
    }
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
            ; INLINE detection (mirrors the working raw panel). The old BiggestAxis()
            ; function path never advanced the step even though the raw axes moved -
            ; a function-scope / ByRef failure under this AHK+Wine build (2026-07-14).
            bestAx := "", bestMag := 0, bestBase := 0, bestCur := 0
            for i, a in AX {
                cur := GetKeyState(joy . "Joy" . a)
                d := cur - rest[a]
                ad := (d < 0) ? -d : d
                if (ad > bestMag) {
                    bestMag := ad
                    bestAx := a . ((d >= 0) ? "+" : "-")
                    bestBase := rest[a], bestCur := cur
                }
            }
            if (bestMag > THRESH) {
                Record(st.k, "Joy" . bestAx . "  (rest " . Round(bestBase) . " -> " . Round(bestCur) . ")")
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
        ; INLINE re-center check (same reason as detection - no function/ByRef).
        centered := true
        if (st.t = "pov") {
            centered := (GetKeyState(joy . "JoyPOV") < 0)
        } else {
            for i, a in AX {
                dd := GetKeyState(joy . "Joy" . a) - rest[a]
                if (((dd < 0) ? -dd : dd) > CENTER)
                    centered := false
            }
        }
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
