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
; Nodding through a small arc, so these are deliberately tight (field: "I have to
; nod too far" at 0.12/0.08).
; Field-bracketed over three sessions, so the history is the argument:
;   0.12 / 0.08  -> "I have to nod too far"
;   0.05         -> "a hair too early"
;   0.075        -> "looking down just a smidge too easily"  (2026-08-08)
; The answer is between 0.075 and 0.12, nearer the bottom - a smidge, not a lot.
; Only the DOWN direction is live (PITCH_UP_KEY = 0 below, because Up is LOOK BACK
; in this engine, not glance-up), so this value IS the look-down threshold.
global PITCH_ON    := 0.09
global PITCH_OFF   := 0.06    ; same ~0.03 hysteresis band as before
; The Up arrow is NOT glance-up in this engine - it is LOOK BACK, so nodding up
; was throwing the view to the rear. Disabled. Set to 1 only if a future binding
; makes Up mean glance-up.
global PITCH_UP_KEY := 0
; Analog feel. Gain 2.5 because a comfortable head turn only reaches ~0.43 rad -
; at the old 1.6 the view ran out of travel well before you ran out of neck.
; Separate gains: side-to-side wants far more travel than up/down, and a big
; pitch gain is also what makes a sideways glance drift vertically.
global ANALOG_GAIN   := 9.0  ; yaw:   head radians -> camera radians
global ANALOG_GAIN_P := 3.5  ; pitch: deliberately lower
; Deadzone, applied BEFORE the gain and subtracted (not zeroed) so there is no
; step as you leave it. Kills rest jitter and stops a sideways look from
; dragging the view up/down. Pitch gets a wider one for that reason.
global ANALOG_DZ     := 0.03
global ANALOG_DZ_P   := 0.012  ; up/down wants a SMALL deadzone (field request x3)
; EXPO is the better answer than a fat deadzone for a sketchy centre: it squashes
; small movements (where the tracker is noisiest, relative to the signal) while
; keeping FULL travel at a big turn. 1.0 = linear, 2.0 = very soft centre.
; Pitch gets more of it because webcam pitch is the noisier estimate - nodding is
; harder to track than turning.
global EXPO          := 1.7
global EXPO_P        := 2.2
; Per-axis reference: the head's OWN full deflection on each axis. These are not
; the same and using one value for both was the bug that made up/down look dead -
; measured at 100Hz, yaw reaches ~0.43 rad but pitch only ~0.17, so normalising
; pitch against 0.45 asked for (0.17/0.45)^2.2 = 12% of its range and no more.
global EXPO_REF      := 0.45   ; rad, yaw:   full comfortable head turn
global EXPO_REF_P    := 0.17   ; rad, pitch: people nod through a much smaller arc
; Pitch also gets its own, heavier filter for the same reason.
global SMOOTH_P      := 0.8
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
; With the engine's writes NOPed the value we write is now provably stable, so
; heavy smoothing is no longer buying anything - it only adds lag. Dropped back.
; SNAP kills the last of the exponential tail: below it we jump exactly onto the
; target instead of creeping toward it forever in the low decimals.
global SMOOTH        := 0.6
global SNAP          := 0.002
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

; ---- THE INPUT PATH (what analog actually drives) ----------------------------
; The engine's own glance input. All three camera handlers read these with
; `fild` (0x406B14 / 0x40728C / 0x4076AA for yaw), then build the ENTIRE camera
; state from them - which is why driving these looks right and poking the output
; floats did not: the transform stays self-consistent, so no missing terrain.
;
; They are a RATE, not an angle. The engine integrates while a value is held and
; springs back to centre when it is zero. Measured on the Gold exe:
;   yaw   saturates at +/-133.3, pitch at +/-104.7
;   release decay: 54 -> 15 -> 0.6 in 300ms (fast, proportional)
; So holding a fixed angle needs a closed loop: push a delta proportional to the
; error and the camera settles where the push balances the spring. KP is that
; gain; the residual steady-state offset is why it is deliberately large.
global ADDR_IN_YAW    := 0x536770
global ADDR_IN_PITCH  := 0x536778
; How far the view travels at a full head turn, in engine units (ceilings 133 /
; 104). Tune these LIVE with Ctrl+Alt+[ and Ctrl+Alt+] rather than by editing -
; 115 and 70 both came back "way too sensitive", so the useful value is clearly
; well below half the available range.
; Field result: yaw feels right at 4 - only 3% of the 133 ceiling - so the engine
; units are far finer than the saturation figure suggests, and the useful tuning
; band is down near 1..10, not 40..115. Steps are 1.15x and the floor is 0.2.
; RADIANS. Measured off the engine's OWN arrow-key glance: the camera floats only
; travel about +/-0.2 rad and the int delta only ranges -13..+6. Earlier values
; here (115, 70, 40, even 4) were all in the wrong unit by 1-2 orders of
; magnitude - "4" meant 4 RADIANS, i.e. 229 degrees - which is why yaw was
; oversensitive at the minimum and pitch, clamped, did nothing at all.
; The "saturation at 133" I calibrated against came from injecting values far
; outside the engine's design range; it is not a usable scale.
; YAW: 4.0 is FIELD-CONFIRMED good. I briefly "corrected" this to 0.30 on the
; theory that these were radians (the engine's own glance moves the camera floats
; only ~0.2 and its int delta only -13..+6) - and that made yaw barely move. The
; measured engine scale simply does not transfer to injected writes, so the
; field value wins over my inference.
global YAW_RANGE      := 4.0
; PITCH is NOT used for the int path any more - see PITCH_VIA_KEYS below.
global PITCH_RANGE    := 4.0
global KP             := 90.0    ; error -> delta
global KP_P           := 90.0
global DELTA_MAX      := 12000   ; back to the value that worked with YAW_RANGE 4.0
; PITCH VIA KEYS. Writing 0x536778 is a dead end on this build: the delta is
; computed correctly and reads back EXACTLY as written (so nothing clobbers it),
; yet the camera never responds - at any magnitude, tiny or enormous. The engine
; evidently gates pitch on something its input poll sets alongside the value.
; But the arrow-key glance pitches perfectly, so analog now drives yaw through
; the int delta and pitch through the SAME held Up/Down keys digital uses. Yaw
; stays smooth and continuous; pitch is stepped but actually works.
global PITCH_VIA_KEYS := 1

; The engine's input poll rewrites these ints every frame (from the keyboard /
; joystick glance), so a write every 8ms only sometimes survives to be read -
; which is exactly "left/right does nothing, up/down glitches at the extremes".
; The original calibration only worked because it wrote in a tight loop thousands
; of times a second and won the race by brute force.
; So while ANALOG is on we NOP the poll's writes to these two ints. This is far
; safer than the earlier camera-float patch: these are INPUTS, not part of the
; view transform, so nothing can end up mutually inconsistent (no missing
; terrain). The only side effect is that keyboard/joystick glance is inert while
; analog is on - which is the point, head tracking replaces it. Restored on mode
; switch and exit. All seven are 5-byte `mov [disp32],eax`, byte-verified.
global INPUT_SITES := [[0x44efbc,5,"A370675300"], [0x44f0c1,5,"A370675300"], [0x44fc5d,5,"A370675300"]
    , [0x44fd7d,5,"A370675300"], [0x44fd98,5,"A370675300"]
    , [0x44f053,5,"A378675300"], [0x44fd0b,5,"A378675300"]]
global gInPatched := 0
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
global gLog := 0

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
; ALL FIFTEEN per-frame writers: three camera-mode handlers x five angle floats.
; Patching only the two we write was not enough - with them pinned, the engine
; kept decaying the OTHER three each frame and the renderer mixed the two states.
; Each entry is [address, length, original bytes], generated from the binary, so
; the patcher can verify a site before touching it and restore it byte-exactly.
; (The four one-time init writes at 0x405Axx are deliberately NOT here - those
; run once at camera setup, not per frame.)
; OFF BY DEFAULT - it BREAKS RENDERING. Field result: with all 15 NOPed the
; ground textures vanish and the terrain draws as sky, returning the moment you
; switch back to digital. So these five floats are NOT five independent Euler
; angles; they are components of the view transform, and freezing three while
; injecting into two leaves an inconsistent basis, so terrain gets culled.
; It also did not help the shake. Set to 1 only to experiment further.
global PATCH_ENABLED := 0
global PATCH_SITES := [[0x406b7c,6,"D91D64294C00"], [0x4072bc,6,"D91D64294C00"], [0x407712,6,"D91D64294C00"]
    , [0x406cb9,6,"891568294C00"], [0x40741c,6,"891568294C00"], [0x40784f,6,"891568294C00"]
    , [0x406b3a,6,"D9156C294C00"], [0x4072aa,6,"D91D6C294C00"], [0x4076d0,6,"D9156C294C00"]
    , [0x406c4b,6,"891570294C00"], [0x4073a3,5,"A370294C00"],   [0x4077e1,6,"891570294C00"]
    , [0x406b88,6,"D91D74294C00"], [0x4072d5,6,"D91D74294C00"], [0x40771e,6,"D91D74294C00"]]
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
ReadFloat(addr) {
    global hProc
    VarSetCapacity(b, 4, 0)
    return DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &b, "UPtr", 4, "Ptr", 0)
         ? NumGet(b, 0, "Float") : 0
}
WriteInt(addr, val) {
    global hProc
    VarSetCapacity(b, 4, 0)
    NumPut(val, b, 0, "Int")
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

; write a hex string ("891568294C00") back over an instruction
WriteBytes(addr, hex, len) {
    VarSetCapacity(b, len, 0)
    Loop, % len
        NumPut("0x" . SubStr(hex, A_Index * 2 - 1, 2), b, A_Index - 1, "UChar")
    return WriteCode(addr, b, len)
}

; Self-heal: if a previous run was force-killed its OnExit never ran, leaving the
; game's camera code NOPed and the view frozen. Anything sitting as all-0x90 at a
; known site gets its real instruction back at startup. (Hit this for real - a
; Stop-Process left all six patched.)
RestoreLeftovers() {
    global PATCH_SITES, INPUT_SITES, hProc
    if (!hProc)
        return
    all := []
    for i, s in PATCH_SITES
        all.Push(s)
    for i, s in INPUT_SITES
        all.Push(s)
    for i, site in all {
        addr := site[1], len := site[2], want := site[3]
        VarSetCapacity(cur, len, 0)
        if (!DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &cur, "UPtr", len, "Ptr", 0))
            continue
        allNop := true
        Loop, % len
            if (NumGet(cur, A_Index - 1, "UChar") != 0x90)
                allNop := false
        if (allNop)
            WriteBytes(addr, want, len)
    }
}

; on=true  -> replace ALL the engine's camera writes with NOPs (we become the
;             only writer, and nothing decays behind our back)
; on=false -> put the original instructions back
SetPatch(on) {
    global PATCH_SITES, gPatched, gOrig, hProc
    if (!hProc || gPatched = on)
        return
    for i, site in PATCH_SITES {
        addr := site[1], len := site[2], want := site[3]
        if (on) {
            ; only patch a site that still holds the exact expected instruction
            VarSetCapacity(cur, len, 0)
            if (!DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &cur, "UPtr", len, "Ptr", 0))
                continue
            s := ""
            Loop, % len
                s .= Format("{:02X}", NumGet(cur, A_Index - 1, "UChar"))
            if (s != want)
                continue
            VarSetCapacity(nop, len, 0x90)
            WriteCode(addr, nop, len)
        } else {
            WriteBytes(addr, want, len)
        }
    }
    gPatched := on
}

; ---- main loop --------------------------------------------------------------
if (OpenGame())
    RestoreLeftovers()
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

        if (PITCH_UP_KEY) {
            if (pitch > PITCH_ON)
                KeySet("Up", true)
            else if (pitch < PITCH_OFF)
                KeySet("Up", false)
        }
        if (pitch < -PITCH_ON)
            KeySet("Down", true)
        else if (pitch > -PITCH_OFF)
            KeySet("Down", false)
        return
    }

    ; ---- ANALOG: drive the engine's OWN glance input, closed loop -------------
    ; Do NOT write the camera floats. Those are outputs the engine rebuilds each
    ; frame along with the rest of the view transform; poking them fought the
    ; auto-centring spring (shake) and left the transform inconsistent (terrain
    ; drawn as sky). Feeding the input instead means the engine derives every
    ; camera value itself, so it always agrees with itself.
    ; Yaw is analog (int delta); pitch rides the working arrow-key path, so we
    ; only release the two horizontal keys here - Up/Down are driven below.
    KeySet("Left", false), KeySet("Right", false)
    if (!OpenGame())
        return
    SetInputPatch(true)   ; stop the poll clobbering the delta we push
    gView := ReadInt(ADDR_VIEW_MODE)
    ; FREEZE TEST (Ctrl+Alt+F): hold a fixed angle, ignoring the head entirely.
    if (gFreeze) {
        WriteInt(ADDR_IN_YAW, Round(ClampD(KP * (60.0 - ReadFloat(ADDR_CAM_YAW)))))
        return
    }
    ; head angle -> a fraction of full deflection (-1..1), expo'd about centre
    ; Expo now returns a normalised -1..1 fraction of that axis's own full travel
    nY := Expo(Dead(yaw,   ANALOG_DZ),   EXPO,   EXPO_REF)
    nP := Expo(Dead(pitch, ANALOG_DZ_P), EXPO_P, EXPO_REF_P)
    nY := (nY > 1) ? 1 : (nY < -1) ? -1 : nY
    nP := (nP > 1) ? 1 : (nP < -1) ? -1 : nP
    gSmY := gSmY * SMOOTH   + nY * (1 - SMOOTH)
    gSmP := gSmP * SMOOTH_P + nP * (1 - SMOOTH_P)

    ; closed loop: push the engine's own delta toward the angle we want
    tgtY := gSmY * YAW_RANGE
    tgtP := gSmP * PITCH_RANGE * ANALOG_PITCH_SIGN
    dY := KP   * (tgtY - ReadFloat(ADDR_CAM_YAW))
    dP := KP_P * (tgtP - ReadFloat(ADDR_CAM_PITCH))
    WriteInt(ADDR_IN_YAW, Round(ClampD(dY)))
    if (PITCH_VIA_KEYS) {
        ; same hysteresis the digital glance uses - press past *_ON, release
        ; inside *_OFF, so a head hovering on the edge cannot chatter the key
        if (PITCH_UP_KEY) {
            if (pitch > PITCH_ON)
                KeySet("Up", true)
            else if (pitch < PITCH_OFF)
                KeySet("Up", false)
        }
        if (pitch < -PITCH_ON)
            KeySet("Down", true)
        else if (pitch > -PITCH_OFF)
            KeySet("Down", false)
    } else {
        WriteInt(ADDR_IN_PITCH, Round(ClampD(dP)))
    }

    ; diagnostic sample (Ctrl+Alt+L): does the pitch delta we push survive the
    ; frame, and does the camera actually respond to it?
    if (gLog && A_TickCount < gLog) {
        FileAppend, % "hP=" . Round(pitch,3)
            . "  nP=" . Round(nP,3)
            . "  tgtP=" . Round(tgtP,2)
            . "  dP=" . Round(dP,0)
            . "  inP(readback)=" . ReadInt(ADDR_IN_PITCH)
            . "  camP=" . Round(ReadFloat(ADDR_CAM_PITCH),2)
            . "  cam2964=" . Round(ReadFloat(0x4c2964),2)
            . "  camY=" . Round(ReadFloat(ADDR_CAM_YAW),2) . "`n"
            , % A_ScriptDir . "\headtrack-log.txt"
    }
return

ClampD(v) {
    global DELTA_MAX
    return (v > DELTA_MAX) ? DELTA_MAX : (v < -DELTA_MAX) ? -DELTA_MAX : v
}

; NOP (or restore) the input poll's writes to the two look inputs, so the value
; we push actually survives until the camera code reads it.
SetInputPatch(on) {
    global INPUT_SITES, gInPatched, hProc
    if (!hProc || gInPatched = on)
        return
    for i, site in INPUT_SITES {
        addr := site[1], len := site[2], want := site[3]
        if (on) {
            VarSetCapacity(cur, len, 0)
            if (!DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &cur, "UPtr", len, "Ptr", 0))
                continue
            s := ""
            Loop, % len
                s .= Format("{:02X}", NumGet(cur, A_Index - 1, "UChar"))
            if (s != want)          ; only ever patch the exact expected instruction
                continue
            VarSetCapacity(nop, len, 0x90)
            WriteCode(addr, nop, len)
        } else {
            WriteBytes(addr, want, len)
        }
    }
    gInPatched := on
}


; Power curve about centre, normalised so a full turn still reaches full travel:
; only the small stuff gets attenuated, the ends are untouched.
Expo(v, k, ref) {
    n := v / ref
    s := (n < 0) ? -1 : 1
    a := Abs(n)
    if (a > 1)
        a := 1 + (a - 1)        ; past the reference, stay linear - don't blow up
    else
        a := a ** k
    return s * a
}

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

; Ctrl+Alt+[ / Ctrl+Alt+] - sensitivity DOWN / UP, live, while you play.
; Both axes scale together so the feel stays consistent. Low beep = less.
; [ / ] = YAW finer/coarser.  - / = = PITCH finer/coarser.  Separate, because they
; do not want the same number: yaw settled at 4 while pitch showed nothing there.
^![::
    Sens(0.87, 1)
return
^!]::
    Sens(1.15, 1)
return
^!-::
    Sens(0.87, 0)
return
^!=::
    Sens(1.15, 0)
return
Sens(mul, isYaw) {
    global YAW_RANGE, PITCH_RANGE
    ; radians now - the engine's own glance lives around 0.2, so the useful band
    ; is roughly 0.05 .. 0.8 and the old 133/104 ceilings are meaningless here.
    if (isYaw) {
        YAW_RANGE := Round(YAW_RANGE * mul, 3)
        if (YAW_RANGE < 0.02)
            YAW_RANGE := 0.02
        if (YAW_RANGE > 1.5)
            YAW_RANGE := 1.5
    } else {
        PITCH_RANGE := Round(PITCH_RANGE * mul, 3)
        if (PITCH_RANGE < 0.02)
            PITCH_RANGE := 0.02
        if (PITCH_RANGE > 1.5)
            PITCH_RANGE := 1.5
    }
    SoundBeep, % (mul < 1 ? 500 : 1200), 60
    ToolTip, % "yaw " . YAW_RANGE . "    pitch " . PITCH_RANGE
    SetTimer, ClearTip, -1400
}

; Ctrl+Alt+L - log 6s of the pitch chain to headtrack-log.txt beside the script.
; Telemetry read from outside always looks frozen because the script only drives
; the game while the game has FOCUS - so it has to be logged from in here.
^!l::
    gLog := A_TickCount + 6000
    SoundBeep, 1500, 120
    ToolTip, logging 6s - nod up and down NOW
    SetTimer, ClearTip, -2500
return

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
    if (gMode = "DIGITAL") {
        SetPatch(false)        ; hand the camera back to the engine
        SetInputPatch(false)   ; and give keyboard/joystick glance back
    }
    ToolTip, % "I76 head tracking: " . gMode
    SetTimer, ClearTip, -1200
return
ClearTip:
    ToolTip
return

Bail:
    ReleaseAll()
    SetPatch(false)        ; NEVER leave the engine's camera writes NOPed
    SetInputPatch(false)   ; nor the input poll's - that would kill glance entirely
    if (pView)
        DllCall("UnmapViewOfFile", "Ptr", pView)
    if (hMap)
        DllCall("CloseHandle", "Ptr", hMap)
    if (hProc)
        DllCall("CloseHandle", "Ptr", hProc)
ExitApp
