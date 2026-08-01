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
; Separate gains: side-to-side wants far more travel than up/down, and a big
; pitch gain is also what makes a sideways glance drift vertically.
global ANALOG_GAIN   := 9.0  ; yaw:   head radians -> camera radians
global ANALOG_GAIN_P := 3.5  ; pitch: deliberately lower
; Deadzone, applied BEFORE the gain and subtracted (not zeroed) so there is no
; step as you leave it. Kills rest jitter and stops a sideways look from
; dragging the view up/down. Pitch gets a wider one for that reason.
global ANALOG_DZ     := 0.05
global ANALOG_DZ_P   := 0.03   ; up/down wants a SMALL deadzone (field request)
; The clamp was the real reason side-to-side kept feeling short: at gain 4.0 a
; 0.43 rad head turn asks for 1.72 rad, and a 1.2 clamp threw away a third of it.
; Raised so the gain is what limits travel, not this.
global ANALOG_MAX    := 2.4  ; rad (~137deg)
; Analog needs the OPPOSITE vertical sign to digital: digital's arrow-key glance
; is field-correct with INVERT_PITCH=1, but writing the camera float that way
; came out upside down. Separate sign so tuning one never breaks the other.
global ANALOG_PITCH_SIGN := -1
; The "bounce" is NOT a race with the engine after all: a live dump showed the
; whole camera angle block sits perfectly static unless WE write it, and feeding
; the int look inputs (0x536770/78) changes nothing - the engine does not
; recompute. So the only writer is us, and the shake is our own input jitter,
; amplified by the gain. That makes SMOOTH the real fix, not write frequency.
; 0 = none, 0.9 = heavy. Note the sim only renders ~19 FPS, so a continuously
; varying angle is sampled 19 times a second no matter how often we write it -
; some of the "jitter" is that, and heavy smoothing is the only lever we have.
global SMOOTH        := 0.93
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
global ADDR_CAM_YAW   := 0x4c2970   ; map calls this cam_pitch - FIELD-CONFIRMED horizontal
global ADDR_VIEW_MODE := 0x4c2728   ; camera FSM: which F1..F11 view is live
; The vertical axis is NOT 0x4c2964 (the map's "cam_yaw") - writing it moves
; nothing. The apply fn stores to 0x4c2964/6c/70/74, and 70 is horizontal, so the
; vertical is one of the others. Ctrl+Alt+P cycles these live (beeps the slot
; number) so it can be found in play instead of guessed.
; FIELD-CONFIRMED 2026-08-01: 0x4c2968 IS the vertical axis (it moved the view,
; just inverted). The memory map documents neither this nor 0x4c2970-as-yaw, so
; the real layout of this block is: 0x4c2968 = pitch, 0x4c2970 = yaw.
global PITCH_CANDIDATES := [0x4c2968, 0x4c2964, 0x4c296c, 0x4c2974, 0x4c2980]
global gPitchSlot := 1
global ADDR_CAM_PITCH := 0x4c2968

global gMode := "DIGITAL"
global gHeld := {}
global gView := 0
global gSmY := 0, gSmP := 0
global gFreeze := 0

; ---- THE FIX FOR THE SHAKE ---------------------------------------------------
; The engine stamps its own value over both camera angles every frame, from the
; cockpit-look apply fn (0x406b00). Found by disassembly, bytes verified:
;   0x406c4b  89 15 70 29 4C 00   mov [0x4c2970], edx   <- our YAW
;   0x406cb9  89 15 68 29 4C 00   mov [0x4c2968], edx   <- our PITCH
; Writing the same floats from outside is therefore a race we only sometimes
; win, and the visible shake is the two values alternating - which is exactly
; why it got worse the further you looked (bigger gap between the two).
; While ANALOG is on we NOP both instructions (6 x 0x90) so nothing but us
; writes the camera. Restored on mode switch, on exit, and it is memory-only:
; relaunching the game undoes it regardless.
; There are THREE of these handlers, not one - the camera-mode jump table at
; 0x4c2990 dispatches a different one per view, and each stamps BOTH angles.
; Patching only mode A left the other two stamping, which is why the shake
; survived the first attempt. Byte-verified, and note mode B's yaw store is a
; 5-byte A3 (mov [disp32],eax) while the rest are 6-byte 89 15 (…,edx):
;   mode A  0x406c4b yaw 6   0x406cb9 pitch 6
;   mode B  0x4073a3 yaw 5   0x40741c pitch 6
;   mode C  0x4077e1 yaw 6   0x40784f pitch 6
global PATCH_SITES := [[0x406c4b,6], [0x406cb9,6], [0x4073a3,5], [0x40741c,6], [0x4077e1,6], [0x40784f,6]]
global gPatched := 0
global gOrig := {}
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

; Code pages are read+execute, so flip to RWX for the write and put the old
; protection straight back.
WriteCode(addr, ByRef buf, len) {
    global hProc
    old := 0
    if (!DllCall("VirtualProtectEx", "Ptr", hProc, "Ptr", addr, "UPtr", len, "UInt", 0x40, "UInt*", old))
        return false
    ok := DllCall("WriteProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &buf, "UPtr", len, "Ptr", 0)
    DllCall("VirtualProtectEx", "Ptr", hProc, "Ptr", addr, "UPtr", len, "UInt", old, "UInt*", old)
    return ok
}

; on=true  -> replace both engine writes with NOPs (we become the only writer)
; on=false -> put the original instructions back
SetPatch(on) {
    global PATCH_SITES, gPatched, gOrig, hProc
    if (!hProc || gPatched = on)
        return
    for i, site in PATCH_SITES {
        addr := site[1], len := site[2]
        if (on) {
            ; stash the real bytes the first time we ever touch this site
            if (!gOrig.HasKey(addr)) {
                VarSetCapacity(cur, len, 0)
                if (!DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &cur, "UPtr", len, "Ptr", 0))
                    continue
                s := ""
                Loop, % len
                    s .= Format("{:02X}", NumGet(cur, A_Index - 1, "UChar"))
                ; only ever patch the two store encodings we verified:
                ; 6-byte 8915 (mov [disp32],edx) and 5-byte A3 (mov [disp32],eax)
                ok := (len = 6 && SubStr(s,1,4) = "8915") || (len = 5 && SubStr(s,1,2) = "A3")
                if (!ok)
                    continue
                gOrig[addr] := s
            }
            VarSetCapacity(nop, len, 0x90)
            WriteCode(addr, nop, len)
        } else {
            if (!gOrig.HasKey(addr))
                continue
            s := gOrig[addr]
            VarSetCapacity(orig, len, 0)
            Loop, % len
                NumPut("0x" . SubStr(s, A_Index * 2 - 1, 2), orig, A_Index - 1, "UChar")
            WriteCode(addr, orig, len)
        }
    }
    gPatched := on
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
    SetPatch(true)   ; stop the engine overwriting us (see PATCH_SITES)
    ; NO view-mode gate. The first cut only wrote when cam_view_mode was 2 or 5
    ; (the FSM switch values the disassembly showed), and that silently blocked
    ; analog entirely: read live in cockpit view on the Gold exe it is 0. Read it
    ; for the on-screen readout, but never let it stop the write.
    gView := ReadInt(ADDR_VIEW_MODE)
    ; low-pass, then write twice per tick: the engine is writing these same
    ; floats every frame and the last writer before the render wins.
    ; FREEZE TEST (Ctrl+Alt+F): hold a fixed angle, ignoring the head entirely.
    ; If the view still shakes with a constant value going in, the shake is the
    ; engine/renderer, not our signal - that tells us where to look next.
    if (gFreeze) {
        WriteFloat(ADDR_CAM_YAW,   0.6)
        WriteFloat(ADDR_CAM_PITCH, 0)
        return
    }
    gSmY := gSmY * SMOOTH + Clamp(Dead(yaw,   ANALOG_DZ)   * ANALOG_GAIN)   * (1 - SMOOTH)
    gSmP := gSmP * SMOOTH + Clamp(Dead(pitch, ANALOG_DZ_P) * ANALOG_GAIN_P * ANALOG_PITCH_SIGN) * (1 - SMOOTH)
    WriteFloat(ADDR_CAM_YAW,   gSmY)
    WriteFloat(ADDR_CAM_PITCH, gSmP)
return

; subtract the deadzone rather than zeroing inside it - no step on the way out
Dead(v, dz) {
    if (v > dz)
        return v - dz
    if (v < -dz)
        return v + dz
    return 0
}

Clamp(v) {
    global ANALOG_MAX
    if (v > ANALOG_MAX)
        return ANALOG_MAX
    if (v < -ANALOG_MAX)
        return -ANALOG_MAX
    return v
}

; Ctrl+Alt+F - freeze the output at a fixed angle (diagnostic, see the Tick code)
^!f::
    gFreeze := !gFreeze
    SoundBeep, % (gFreeze ? 1400 : 500), 150
    ToolTip, % gFreeze ? "FROZEN at yaw 0.6 - if the view still shakes, it is NOT our signal" : "freeze off"
    SetTimer, ClearTip, -2000
return

; Ctrl+Alt+P - cycle which address the vertical axis writes to. Beeps the slot
; number. Nod up and down after each press; when the view finally moves
; vertically, that slot is the real pitch and it goes in as the default.
^!p::
    gPitchSlot := Mod(gPitchSlot, PITCH_CANDIDATES.MaxIndex()) + 1
    ADDR_CAM_PITCH := PITCH_CANDIDATES[gPitchSlot]
    Loop, % gPitchSlot
    {
        SoundBeep, 1100, 80
        Sleep, 60
    }
    ToolTip, % "pitch slot " . gPitchSlot . " -> 0x" . Format("{:X}", ADDR_CAM_PITCH)
    SetTimer, ClearTip, -1500
return

; Ctrl+Alt+H - swap modes (release everything first so nothing sticks)
^!h::
    ReleaseAll()
    gMode := (gMode = "DIGITAL") ? "ANALOG" : "DIGITAL"
    if (gMode = "DIGITAL")
        SetPatch(false)   ; hand the camera back to the engine
    ToolTip, % "I76 head tracking: " . gMode
    SetTimer, ClearTip, -1200
return
ClearTip:
    ToolTip
return

Bail:
    ReleaseAll()
    SetPatch(false)   ; NEVER leave the engine's camera writes NOPed
    if (pView)
        DllCall("UnmapViewOfFile", "Ptr", pView)
    if (hMap)
        DllCall("CloseHandle", "Ptr", hMap)
    if (hProc)
        DllCall("CloseHandle", "Ptr", hProc)
ExitApp
