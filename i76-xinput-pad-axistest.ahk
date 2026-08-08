; Interstate '76 - gamepad AXIS diagnostic (definitive, dual-method).
; The decode harness saw buttons + D-pad but no analog axes. This settles WHY by
; reading the sticks TWO ways at once and tracking each one's live min/max:
;   (A) AHK's GetKeyState("JoyX")  - the wrapper the decode harness used
;   (B) raw DllCall joyGetPosEx()  - the EXACT winmm API the game itself uses
;       to read steering (so if the game steers, this MUST move)
; Swirl both sticks + squeeze both triggers for ~25 s. Whichever column shows a
; real RANGE is the method that works under Wine. Writes C:\AutoHotkey\axistest.txt.
;
; RUN STANDALONE, GAME QUIT (via `./setup-input-remapper.sh --axes`). Connect the
; pad BEFORE launching; keep swirling so it can't Bluetooth-sleep.
#NoEnv
#SingleInstance Force
#Persistent

global OUT := "C:\AutoHotkey\axistest.txt"
global DURATION := 25000
global JB
VarSetCapacity(JB, 52, 0)

; AHK-side joystick index (1-based); joyGetPosEx id is 0-based (JOYSTICKID1 = 0)
joy := 0
Loop, 16 {
    if (GetKeyState(A_Index . "JoyName") != "") {
        joy := A_Index
        break
    }
}
global joyN := joy ? joy : 1
global rawId := joyN - 1
; documented AHK quirk: query once before the loop so axis polling initializes
GetKeyState(joyN . "JoyX")

global aMin := 101, aMax := -1            ; AHK JoyX seen range (0-100)
global rMin := 999999, rMax := -1         ; raw dwXpos seen range (0-65535)
global aYmin := 101, aYmax := -1, rYmin := 999999, rYmax := -1
global startT := A_TickCount

Gui, +AlwaysOnTop
Gui, Color, 101010
Gui, Font, s13 cWhite Bold, Consolas
Gui, Add, Text, w600 vHdr, % "AXIS TEST - AHK joy" . joyN . " / joyGetPosEx id " . rawId
Gui, Font, s16 cAqua Bold, Consolas
Gui, Add, Text, w600 vBig, SWIRL BOTH STICKS + SQUEEZE BOTH TRIGGERS, fully
Gui, Font, s12 cSilver, Consolas
Gui, Add, Text, w600 vLive, (reading...)
Gui, Font, s13 cLime Bold, Consolas
Gui, Add, Text, w600 vVerdict, .
Gui, Font, s10 cGray, Consolas
Gui, Add, Text, w600 vTime, .
Gui, Show, , I76 Axis Test
SetTimer, Sample, 40
return

Sample:
    ; (A) AHK wrapper
    ax := GetKeyState(joyN . "JoyX")
    ay := GetKeyState(joyN . "JoyY")
    az := GetKeyState(joyN . "JoyZ")
    if (ax != "") {
        (ax < aMin) ? aMin := ax :
        (ax > aMax) ? aMax := ax :
        (ay < aYmin) ? aYmin := ay :
        (ay > aYmax) ? aYmax := ay :
    }
    ; (B) raw joyGetPosEx (JOY_RETURNALL = 0xFF), the game's own call
    NumPut(52, JB, 0, "UInt")
    NumPut(0xFF, JB, 4, "UInt")
    err := DllCall("winmm\joyGetPosEx", "UInt", rawId, "Ptr", &JB, "UInt")
    rx := NumGet(JB, 8, "UInt"), ry := NumGet(JB, 12, "UInt"), rz := NumGet(JB, 16, "UInt")
    rpov := NumGet(JB, 40, "UInt"), rbtn := NumGet(JB, 32, "UInt")
    if (err = 0) {
        (rx < rMin) ? rMin := rx :
        (rx > rMax) ? rMax := rx :
        (ry < rYmin) ? rYmin := ry :
        (ry > rYmax) ? rYmax := ry :
    }

    aRange := (aMax >= aMin) ? (aMax - aMin) : 0
    rRange := (rMax >= rMin) ? (rMax - rMin) : 0
    live := "AHK  : X=" Round(ax) " Y=" Round(ay) " Z=" Round(az) "     range(X)=" Round(aRange) "`n"
    live .= "RAW  : err=" err " X=" rx " Y=" ry " Z=" rz " POV=" rpov " btns=" rbtn "`n"
    live .= "RAW  : range(X)=" (rMax - rMin) "   (raw axes are 0-65535)"
    GuiControl,, Live, % live

    aOK := (aRange > 10) ? "YES" : "NO"
    rOK := ((rMax - rMin) > 3000) ? "YES" : "NO"
    GuiControl,, Verdict, % "AHK GetKeyState reads axes? " . aOK . "     raw joyGetPosEx reads axes? " . rOK

    elapsed := A_TickCount - startT
    GuiControl,, Time, % "time left: " . Round((DURATION - elapsed) / 1000) . "s   (close window to finish early)"
    if (elapsed >= DURATION) {
        SetTimer, Sample, Off
        Save()
        GuiControl,, Big, DONE - saved. Close this window.
    }
return

Save() {
    global
    FileDelete, %OUT%
    txt := "I76 axis test - AHK joy" . joyN . " / joyGetPosEx id " . rawId . "`n"
    txt .= "method            X-range   Y-range   reads-axes?`n"
    txt .= "AHK GetKeyState    " . Round(aMax - aMin) . " (of 100)   " . Round(aYmax - aYmin) . "     " . ((aMax - aMin) > 10 ? "YES" : "NO") . "`n"
    txt .= "raw joyGetPosEx    " . (rMax - rMin) . " (of 65535)  " . (rYmax - rYmin) . "   " . ((rMax - rMin) > 3000 ? "YES" : "NO") . "`n"
    FileAppend, %txt%, %OUT%
}

GuiClose:
    Save()
    FileAppend, `n(ended early)`n, %OUT%
    ExitApp
return
