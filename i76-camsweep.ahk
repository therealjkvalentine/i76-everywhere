; Interstate '76 - camera address sweeper (AutoHotkey v1.1).
;
; Finds which memory address actually drives the in-game view, instead of
; trusting the map. Sweeps ONE candidate at a time with a slow sine wave while
; you drive: when the view starts swinging by itself, that address is the one.
;
; WHY THIS EXISTS: docs/GHIDRA-MEMORY-MAP.md lists cam_yaw @ 0x4c2964 as the
; head-tracking target, but writing it produced no visible movement. That
; reading was taken with the game sitting on the pause menu, so it proved
; nothing either way - this settles it under real gameplay.
;
; USE:
;   1. Get INTO a mission and be driving (not paused, not in a menu).
;   2. Ctrl+Alt+1 .. Ctrl+Alt+6 picks which address to sweep.
;      Ctrl+Alt+0 stops sweeping (restores the value it found).
;   3. Watch the view. When it swings on its own, that address wins - tell me
;      the number and it becomes the analog head-tracking target.
;
; Each slot beeps a distinct number of times when selected, because a tooltip
; can be hidden behind the game's output window.

#NoEnv
#SingleInstance Force
#Persistent
#MaxHotkeysPerInterval 200000
#ErrorStdOut

global GAME_EXE := "i76.exe"
global ADDRS := [0x4c2964, 0x4c2968, 0x4c296c, 0x4c2970, 0x4c2974, 0x4c2980]
global gSlot := 0          ; 0 = off, else index into ADDRS
global gPhase := 0
global gOrig := 0
global hProc := 0, gPid := 0

OpenGame() {
    global hProc, gPid, GAME_EXE
    Process, Exist, %GAME_EXE%
    pid := ErrorLevel
    if (!pid) {
        if (hProc)
            DllCall("CloseHandle", "Ptr", hProc)
        hProc := 0, gPid := 0
        return false
    }
    if (pid != gPid) {
        if (hProc)
            DllCall("CloseHandle", "Ptr", hProc)
        hProc := DllCall("OpenProcess", "UInt", 0x38, "Int", 0, "UInt", pid, "Ptr")
        gPid := pid
    }
    return (hProc != 0)
}
ReadF(addr) {
    global hProc
    VarSetCapacity(b, 4, 0)
    return DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &b, "UPtr", 4, "Ptr", 0)
         ? NumGet(b, 0, "Float") : 0
}
WriteF(addr, val) {
    global hProc
    VarSetCapacity(b, 4, 0)
    NumPut(val, b, 0, "Float")
    return DllCall("WriteProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &b, "UPtr", 4, "Ptr", 0)
}

Pick(n) {
    global gSlot, gOrig, gPhase, ADDRS
    if (!OpenGame())
        return
    ; put back whatever we were overwriting before moving on
    if (gSlot)
        WriteF(ADDRS[gSlot], gOrig)
    gSlot := n
    gPhase := 0
    if (n) {
        gOrig := ReadF(ADDRS[n])
        Loop, %n%
        {
            SoundBeep, 900, 90
            Sleep, 60
        }
        ToolTip, % "sweeping slot " . n . "  addr 0x" . Format("{:X}", ADDRS[n]) . "  (was " . Round(gOrig,4) . ")"
    } else {
        SoundBeep, 400, 250
        ToolTip, sweep OFF
    }
    SetTimer, ClearTip, -1500
}

^!1::Pick(1)
^!2::Pick(2)
^!3::Pick(3)
^!4::Pick(4)
^!5::Pick(5)
^!6::Pick(6)
^!0::Pick(0)

ClearTip:
    ToolTip
return

SetTimer, Sweep, 16
OnExit, Bail
return

Sweep:
    if (!gSlot)
        return
    if (!OpenGame())
        return
    ; slow, obvious sine: +/-0.9 rad (~50 deg) over about 3 seconds
    gPhase += 0.033
    WriteF(ADDRS[gSlot], 0.9 * Sin(gPhase))
return

Bail:
    if (gSlot && hProc)
        WriteF(ADDRS[gSlot], gOrig)
    if (hProc)
        DllCall("CloseHandle", "Ptr", hProc)
ExitApp
