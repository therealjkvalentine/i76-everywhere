; Interstate '76 - head tracking (opentrack -> in-game look), AutoHotkey v1.1.
;
; TRANSPORT: opentrack's "freetrack 2.0 Enhanced" output -> the FT_SharedMem
; shared-memory block. Chosen over opentrack's vjoy output on purpose: this
; machine enumerates NO winmm device at index 0 (the devices sit at ids 4 and 8,
; which is why input.map here binds joystick5), so adding another virtual stick
; risks shifting what the engine binds. Shared memory touches no joystick at all.
; Verified live 2026-08-01: yaw arrives in RADIANS, ~+/-0.65 (about +/-37 deg).
;
; TWO MODES (Ctrl+Alt+H toggles; starts in DIGITAL):
;
;  1. DIGITAL - head yaw past a threshold holds the glance arrow key, exactly the
;     mechanism the right stick already uses in i76-remap.ahk. Works in every
;     view, needs nothing but the game running.
;
;  2. ANALOG - writes the live camera yaw float directly into the game
;     (cam_yaw @ 0x4c2964, confirmed in docs/GHIDRA-MEMORY-MAP.md "CAMERA").
;     The engine's cockpit_look_apply (0x406b00) recomputes those floats every
;     frame from the int inputs at 0x536770/78, so this deliberately re-writes
;     at ~66 Hz against a 20 FPS sim to win the race. Cockpit view only.
;
; SAFETY (the wheel-disaster rules from docs/INPUT-REMAPPER.md):
;  - every key-down has a matching key-up; a held-state table, release-on-center,
;    release-all when tracking drops out, on mode switch, and on exit.
;  - only acts while the game window is active, so head movement can never type
;    into the desktop.
;  - NO modal dialogs (they hide behind the game and kill input).
;
; Run it alongside i76-remap.ahk (they don't overlap: that one owns the pad,
; this one owns the head). Docs: docs/GHIDRA-MEMORY-MAP.md, docs/HEAD-TRACKING.md

#NoEnv
#NoTrayIcon
#SingleInstance Force
#Persistent
#MaxHotkeysPerInterval 200000
#ErrorStdOut

; ---- tunables ---------------------------------------------------------------
; Field-tuned 2026-08-01: yaw thresholds confirmed good; yaw needed inverting.
global YAW_ON      := 0.18   ; rad, ~10deg: past this the glance key goes down
global YAW_OFF     := 0.12   ; rad, ~7deg:  inside this it comes back up
; Pitch gets a smaller gate than yaw on purpose - people nod through a much
; narrower arc than they turn (measured: yaw reached ~0.43 rad, pitch ~0.17).
global PITCH_ON    := 0.12
global PITCH_OFF   := 0.08
; Analog feel. Gain 2.5 because a comfortable head turn only reaches ~0.43 rad -
; at the old 1.6 the view ran out of travel well before you ran out of neck.
global ANALOG_GAIN   := 2.5  ; head radians -> camera radians
global ANALOG_MAX    := 1.2  ; clamp, rad (~69deg) so you can't spin the view
; The engine rewrites these floats every frame, so analog is a race we win by
; writing more often. SMOOTH also damps the residual chatter (0 = none, 0.9 =
; heavy); the visible "bounce" is our write and the engine's alternating.
global SMOOTH        := 0.55
; Both axes needed inverting on this rig (field-confirmed 2026-08-01): opentrack's
; freetrack yaw/pitch signs run opposite to the engine's glance direction.
global INVERT       := 1     ; yaw:   looking left glances left
global INVERT_PITCH := 1     ; pitch: looking up glances up
global GAME_EXE    := "i76.exe"

; Camera angle block, i76.exe Gold. NOTE the map's labels are SWAPPED against
; what the engine actually does: docs/GHIDRA-MEMORY-MAP.md calls 0x4c2964
; "cam_yaw" and 0x4c2970 "cam_pitch", but in play, writing 0x4c2970 swings the
; view HORIZONTALLY and 0x4c2964 vertically (field-confirmed 2026-08-01 - head
; up/down was moving the view left/right). So they are bound the other way here.
global ADDR_CAM_YAW   := 0x4c2970   ; map calls this cam_pitch
global ADDR_CAM_PITCH := 0x4c2964   ; map calls this cam_yaw
global ADDR_VIEW_MODE := 0x4c2728   ; camera FSM: which F1..F11 view is live

global gMode := "DIGITAL"
global gHeld := {}
global gView := 0
global gSmY := 0, gSmP := 0
global hMap := 0, pView := 0, hProc := 0, gPid := 0

; ---- freetrack shared memory ------------------------------------------------
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

; FreeTrackData: DataID@0, CamWidth@4, CamHeight@8, then Yaw@12 Pitch@16 Roll@20 (float, radians)
FTYaw() {
    global pView
    return pView ? NumGet(pView+0, 12, "Float") : 0
}
FTPitch() {
    global pView
    return pView ? NumGet(pView+0, 16, "Float") : 0
}

; ---- held-key table: every down gets an up ----------------------------------
KeySet(key, want) {
    global gHeld
    if (want && !gHeld[key]) {
        gHeld[key] := true
        SendEvent, {%key% down}
    } else if (!want && gHeld[key]) {
        gHeld[key] := false
        SendEvent, {%key% up}
    }
}
ReleaseAll() {
    KeySet("Left", false), KeySet("Right", false)
    KeySet("Up", false), KeySet("Down", false)
}

; ---- game process (analog mode only) ----------------------------------------
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
        ; PROCESS_VM_OPERATION|VM_READ|VM_WRITE = 0x38 (same as tools/i76-trainer.ahk)
        hProc := DllCall("OpenProcess", "UInt", 0x38, "Int", 0, "UInt", pid, "Ptr")
        gPid := pid
    }
    return (hProc != 0)
}
ReadInt(addr) {
    global hProc
    VarSetCapacity(b, 4, 0)
    return DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &b, "UPtr", 4, "Ptr", 0)
         ? NumGet(b, 0, "Int") : 0
}
WriteFloat(addr, val) {
    global hProc
    VarSetCapacity(b, 4, 0)
    NumPut(val, b, 0, "Float")
    return DllCall("WriteProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &b, "UPtr", 4, "Ptr", 0)
}

; ---- main loop --------------------------------------------------------------
SetTimer, Tick, 8
OnExit, Bail
return

Tick:
    if (!OpenFT()) {
        ReleaseAll()
        return
    }
    ; only ever act on the live game window - never type at the desktop
    if (!WinActive("ahk_exe " . GAME_EXE)) {
        ReleaseAll()
        return
    }
    yaw := FTYaw()
    if (INVERT)
        yaw := -yaw
    pitch := FTPitch()
    if (INVERT_PITCH)
        pitch := -pitch

    if (gMode = "DIGITAL") {
        ; hysteresis: press past *_ON, release inside *_OFF, so a head hovering
        ; on the boundary can't chatter the key down/up every tick.
        if (yaw > YAW_ON)
            KeySet("Right", true)
        else if (yaw < YAW_OFF)
            KeySet("Right", false)
        if (yaw < -YAW_ON)
            KeySet("Left", true)
        else if (yaw > -YAW_OFF)
            KeySet("Left", false)

        if (pitch > PITCH_ON)
            KeySet("Up", true)
        else if (pitch < PITCH_OFF)
            KeySet("Up", false)
        if (pitch < -PITCH_ON)
            KeySet("Down", true)
        else if (pitch > -PITCH_OFF)
            KeySet("Down", false)
        return
    }

    ; ---- ANALOG: poke the camera yaw float straight into the engine ----------
    ReleaseAll()
    if (!OpenGame())
        return
    ; NO view-mode gate. The first cut only wrote when cam_view_mode was 2 or 5
    ; (the FSM switch values the disassembly showed), and that silently blocked
    ; analog entirely: read live in cockpit view on the Gold exe it is 0. Read it
    ; for the on-screen readout, but never let it stop the write.
    gView := ReadInt(ADDR_VIEW_MODE)
    ; low-pass, then write twice per tick: the engine is writing these same
    ; floats every frame and the last writer before the render wins.
    gSmY := gSmY * SMOOTH + Clamp(yaw   * ANALOG_GAIN) * (1 - SMOOTH)
    gSmP := gSmP * SMOOTH + Clamp(pitch * ANALOG_GAIN) * (1 - SMOOTH)
    WriteFloat(ADDR_CAM_YAW,   gSmY)
    WriteFloat(ADDR_CAM_PITCH, gSmP)
    WriteFloat(ADDR_CAM_YAW,   gSmY)
    WriteFloat(ADDR_CAM_PITCH, gSmP)
return

Clamp(v) {
    global ANALOG_MAX
    if (v > ANALOG_MAX)
        return ANALOG_MAX
    if (v < -ANALOG_MAX)
        return -ANALOG_MAX
    return v
}

; Ctrl+Alt+H - swap modes (release everything first so nothing sticks)
^!h::
    ReleaseAll()
    gMode := (gMode = "DIGITAL") ? "ANALOG" : "DIGITAL"
    ToolTip, % "I76 head tracking: " . gMode
    SetTimer, ClearTip, -1200
return
ClearTip:
    ToolTip
return

Bail:
    ReleaseAll()
    if (pView)
        DllCall("UnmapViewOfFile", "Ptr", pView)
    if (hMap)
        DllCall("CloseHandle", "Ptr", hMap)
    if (hProc)
        DllCall("CloseHandle", "Ptr", hProc)
ExitApp
