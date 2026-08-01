; Interstate '76 - head tracking TEST HARNESS (AutoHotkey v1.1).
;
; A visible window that shows, live, every stage of the head-tracking chain, so
; you can see exactly where it breaks instead of guessing:
;   1. is opentrack's FT_SharedMem there at all?
;   2. is yaw actually moving?
;   3. does it cross the thresholds?
;   4. is the GAME window active? (the real script only acts when it is - this
;      is the usual reason "nothing happens")
;   5. what key WOULD be held right now
;
; Sends NOTHING by default. Tick "actually send keys" to arm it, so you can
; safely watch the numbers in any window (Notepad is a good target once armed).
;
; Run:  _ahk\AutoHotkeyU32.exe i76-headtrack-test.ahk     (or HEADTRACK-TEST.bat)
; Docs: docs/HEAD-TRACKING.md

#NoEnv
#SingleInstance Force
#Persistent
#MaxHotkeysPerInterval 200000
#ErrorStdOut

global YAW_ON  := 0.18
global YAW_OFF := 0.12
global GAME_EXE := "i76.exe"
global hMap := 0, pView := 0, gHeld := {}, gSend := 0, gMinY := 0, gMaxY := 0

Gui, Font, s10, Consolas
Gui, Add, Text, w560 vS1, 1. FT_SharedMem      : (checking...)
Gui, Add, Text, w560 vS2, 2. yaw / pitch / roll: -
Gui, Add, Text, w560 vS3, 3. yaw range seen    : -
Gui, Add, Text, w560 vS4, 4. threshold         : -
Gui, Add, Text, w560 vS5, 5. game window active: -
Gui, Add, Text, w560 vS6, 6. key that would be held: (none)
Gui, Add, Text, w560 vS7, active window right now: -
Gui, Font, s9, Segoe UI
Gui, Add, Checkbox, vSendKeys gToggleSend, actually send the arrow keys (leave OFF to just watch)
Gui, Add, Text, w560, Turn your head left and right. Thresholds: on %YAW_ON% rad / off %YAW_OFF% rad.
Gui, Add, Button, gResetRange, Reset range
Gui, Show, w580, I76 head-tracking test
SetTimer, Tick, 30
OnExit, Bail
return

ToggleSend:
    GuiControlGet, gSend,, SendKeys
    if (!gSend)
        ReleaseAll()
return

ResetRange:
    gMinY := 0, gMaxY := 0
return

OpenFT() {
    global hMap, pView
    if (pView)
        return true
    hMap := DllCall("OpenFileMapping", "UInt", 0x0004, "Int", 0, "Str", "FT_SharedMem", "Ptr")
    if (!hMap)
        return false
    pView := DllCall("MapViewOfFile", "Ptr", hMap, "UInt", 0x0004, "UInt", 0, "UInt", 0, "UPtr", 0, "Ptr")
    return (pView != 0)
}

KeySet(key, want) {
    global gHeld, gSend
    if (want && !gHeld[key]) {
        gHeld[key] := true
        if (gSend)
            SendEvent, {%key% down}
    } else if (!want && gHeld[key]) {
        gHeld[key] := false
        if (gSend)
            SendEvent, {%key% up}
    }
}
ReleaseAll() {
    KeySet("Left", false), KeySet("Right", false)
}

Tick:
    if (!OpenFT()) {
        GuiControl,, S1, % "1. FT_SharedMem      : *** NOT FOUND *** -> in opentrack set Output = freetrack 2.0 Enhanced, then press Start"
        GuiControl,, S2, % "2. yaw / pitch / roll: -"
        ReleaseAll()
        return
    }
    GuiControl,, S1, % "1. FT_SharedMem      : OK (opentrack is publishing)"

    y := NumGet(pView+0, 12, "Float")
    p := NumGet(pView+0, 16, "Float")
    r := NumGet(pView+0, 20, "Float")
    if (y < gMinY)
        gMinY := y
    if (y > gMaxY)
        gMaxY := y
    GuiControl,, S2, % "2. yaw / pitch / roll: " . Round(y,3) . "  /  " . Round(p,3) . "  /  " . Round(r,3)
    GuiControl,, S3, % "3. yaw range seen    : " . Round(gMinY,3) . " .. " . Round(gMaxY,3)
                     . (Abs(gMaxY - gMinY) < 0.05 ? "   <-- not moving! is tracking STARTED in opentrack?" : "")

    ; thresholds (hysteresis, same as the real script)
    if (y > YAW_ON)
        KeySet("Right", true)
    else if (y < YAW_OFF)
        KeySet("Right", false)
    if (y < -YAW_ON)
        KeySet("Left", true)
    else if (y > -YAW_OFF)
        KeySet("Left", false)

    st := (y > YAW_ON) ? "PAST +on (look right)" : (y < -YAW_ON) ? "PAST -on (look left)" : "inside deadzone"
    GuiControl,, S4, % "4. threshold         : " . st

    act := WinActive("ahk_exe " . GAME_EXE) ? "YES - the real script would be driving the game"
         : "NO  - the real script does nothing unless " . GAME_EXE . " is focused"
    GuiControl,, S5, % "5. game window active: " . act

    held := ""
    for k, v in gHeld
        if (v)
            held .= (held ? "+" : "") . k
    GuiControl,, S6, % "6. key that would be held: " . (held ? held : "(none)") . (gSend ? "   [SENDING]" : "   [watch only]")

    WinGetTitle, t, A
    WinGet, e, ProcessName, A
    GuiControl,, S7, % "active window right now: " . e . "  -  " . SubStr(t, 1, 48)
return

GuiClose:
Bail:
    ReleaseAll()
    if (pView)
        DllCall("UnmapViewOfFile", "Ptr", pView)
    if (hMap)
        DllCall("CloseHandle", "Ptr", hMap)
ExitApp
