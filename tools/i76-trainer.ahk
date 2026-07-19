; Interstate '76 memory trainer / live-state inspector (AutoHotkey v1.1).
; Runs INSIDE the Wine prefix, same session as i76.exe, so kernel32
; ReadProcessMemory/WriteProcessMemory reach the game across the Wine boundary.
; It is a TEST INSTRUMENT for the static memory map (docs/GHIDRA-MEMORY-MAP.md):
;   - live readout of the CONFIRMED addresses (camera, input, view mode, FFB)
;   - a camera-angle WRITE test that proves the head-tracking write path
;   - an exact-value + next-scan SCANNER to pin the runtime unknowns
;     (armor / gear / speed / current target) while you play
;
; The 1997 i76.exe has no ASLR and loads at its preferred base 0x400000 under
; Wine, so the static VAs from the disassembly are valid process addresses.
;
; Launch:  wine AutoHotkeyU32.exe i76-trainer.ahk   (with the game running)
; Hotkeys: F8 toggle overlay  |  F7 head-look write test  |  see SCANNER below.
;
; NOTHING here writes game files or the input map; it only touches live process
; memory of i76.exe. Safe to close any time; it holds no locks.

#NoEnv
#SingleInstance Force
#Persistent
SetBatchLines, -1

; ---- confirmed addresses (docs/GHIDRA-MEMORY-MAP.md PART 2/4/5) --------------
; two address sets (docs/GHIDRA-MEMORY-MAP.md / tools/i76-addresses.json);
; AttachGame picks by which exe is running.
global ADDR_I76 := { "cam_yaw":0x4c2964, "cam_pitch":0x4c296c, "cam_roll":0x4c2970
               , "view_mode":0x4c2728, "in_throttle":0x5367cc, "in_steer":0x5367d4
               , "in_pilot_yaw":0x536770, "in_pilot_pitch":0x536778
               , "ffb_flag":0x52bbd0, "ffb_params":0x4f2328 }
global ADDR_NITRO := { "cam_yaw":0x4f38fc, "cam_pitch":0x4f3908, "cam_roll":0x4f38fc
               , "view_mode":0x4f38c0, "in_throttle":0x5348fc, "in_steer":0x534904
               , "in_pilot_yaw":0x5348a0, "in_pilot_pitch":0x5348a8
               , "ffb_flag":0x52bbd0, "ffb_params":0x4f2328 }
global ADDR := ADDR_I76

global PROC_VM_READ := 0x10, PROC_VM_WRITE := 0x20, PROC_VM_OP := 0x8
global hProc := 0, gPid := 0, gShow := true
global gHeadTest := false, gHeadT := 0

; ---- attach to i76.exe (or nitro.exe) ---------------------------------------
AttachGame() {
    global
    for idx, exe in ["i76.exe", "nitro.exe"] {   ; v1: single-var for gets the KEY - must use idx,exe
        pid := 0
        Process, Exist, %exe%
        pid := ErrorLevel
        if (pid) {
            gPid := pid
            ADDR := (exe = "nitro.exe") ? ADDR_NITRO : ADDR_I76
            hProc := DllCall("OpenProcess", "UInt", PROC_VM_READ|PROC_VM_WRITE|PROC_VM_OP
                           , "Int", 0, "UInt", pid, "Ptr")
            return hProc != 0
        }
    }
    return false
}

RInt(addr) {
    global hProc
    VarSetCapacity(buf, 4, 0)
    if !DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &buf, "UPtr", 4, "Ptr", 0)
        return "?"
    return NumGet(buf, 0, "Int")
}
RFloat(addr) {
    global hProc
    VarSetCapacity(buf, 4, 0)
    if !DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &buf, "UPtr", 4, "Ptr", 0)
        return "?"
    return Round(NumGet(buf, 0, "Float"), 4)
}
WInt(addr, val) {
    global hProc
    VarSetCapacity(buf, 4, 0), NumPut(val, buf, 0, "Int")
    return DllCall("WriteProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &buf, "UPtr", 4, "Ptr", 0)
}
WFloat(addr, val) {
    global hProc
    VarSetCapacity(buf, 4, 0), NumPut(val, buf, 0, "Float")
    return DllCall("WriteProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &buf, "UPtr", 4, "Ptr", 0)
}

; ---- overlay GUI ------------------------------------------------------------
Gui, +AlwaysOnTop +ToolWindow -Caption +E0x20
Gui, Color, 111111
Gui, Font, s10 cCCFFCC, Consolas
Gui, Add, Text, x8 y6 w360 vTX, attaching...
Gui, Show, x8 y8 NoActivate, i76trainer

if !AttachGame() {
    GuiControl,, TX, i76.exe/nitro.exe not found - start the game, then reload.
}
SetTimer, Refresh, 100

Refresh:
    if (!hProc) {
        if AttachGame()
            GuiControl,, TX, attached pid %gPid%
        return
    }
    if (!gShow) {
        GuiControl,, TX, [F8] overlay hidden`nscanner: type /scan
        return
    }
    ; head-look write test: sweep yaw so you SEE the view turn -> proves write path
    if (gHeadTest) {
        gHeadT += 0.04
        WFloat(ADDR["cam_yaw"], 0.5 * Sin(gHeadT))
    }
    s := "I'76 TRAINER  pid " gPid "   [F8]hide [F7]head-test`n"
    s .= "----------------------------------------`n"
    s .= "view mode : " RInt(ADDR["view_mode"]) "`n"
    s .= "cam yaw   : " RFloat(ADDR["cam_yaw"]) "   pitch: " RFloat(ADDR["cam_pitch"]) "`n"
    s .= "cam roll  : " RFloat(ADDR["cam_roll"]) "`n"
    s .= "in throttle: " RInt(ADDR["in_throttle"]) "  steer: " RInt(ADDR["in_steer"]) "`n"
    s .= "pilot yaw : " RInt(ADDR["in_pilot_yaw"]) "  pitch: " RInt(ADDR["in_pilot_pitch"]) "`n"
    s .= "FFB flag  : " RInt(ADDR["ffb_flag"]) "   (0 = no DI-FFB device, expected on Mac)`n"
    s .= "head-test : " (gHeadTest ? "ON (view should sweep)" : "off") "`n"
    s .= scanStatus
    GuiControl,, TX, %s%
    ; headless log: append a JSON state line so the tool is verifiable/feedable
    j := "{""t"":" A_TickCount ",""view"":" RInt(ADDR["view_mode"]) ",""yaw"":" RFloat(ADDR["cam_yaw"]) ",""pitch"":" RFloat(ADDR["cam_pitch"]) ",""throttle"":" RInt(ADDR["in_throttle"]) ",""steer"":" RInt(ADDR["in_steer"]) ",""ffb"":" RInt(ADDR["ffb_flag"]) "}"
    FileDelete, C:\AutoHotkey\trainer-state.json
    FileAppend, %j%, C:\AutoHotkey\trainer-state.json
return

F8::gShow := !gShow
; --- EDIT demo: F6 writes a value to any address (freeze/set). Read+Write are
;     both proven live (ammo set to 9999 held; camera write turns the view).
;     For heap values (ammo/armor) use the F9/F10 scanner to get the address
;     first (they move per game launch), then freeze here.
F6::
    InputBox, spec, Write memory, addr,value (hex addr) e.g. 25b0728,9999 or f0x4c2964,0.3:, , 380, 130
    if (ErrorLevel)
        return
    parts := StrSplit(spec, ",")
    isF := (SubStr(parts[1],1,1)="f")
    astr := isF ? SubStr(parts[1],2) : parts[1]
    addr := "0x" . astr
    if (isF)
        WFloat(addr+0, parts[2]+0.0)
    else
        WInt(addr+0, parts[2]+0)
return
F7::
    gHeadTest := !gHeadTest
    if (!gHeadTest)
        WFloat(ADDR["cam_yaw"], 0)   ; recenter on release
return

; ---- SCANNER (pin runtime unknowns: armor / gear / speed / target) ----------
; Usage while playing:
;   1. note a value on screen (e.g. armor 100). Press F9, type 100, Enter.
;   2. let the value change in-game (take a hit -> armor 80). Press F10, type 80.
;   3. repeat F10 until 1-3 candidates remain -> those are the address(es).
; Scans a broad range of the game's writable image+heap for int OR float matches.
global gCands := [], scanStatus := "scanner: F9 first-scan  F10 next-scan  F11 show", gScanType := "int"
global SCAN_LO := 0x00500000, SCAN_HI := 0x02000000, SCAN_STEP := 4

FirstScan(val) {
    global
    gCands := []
    addr := SCAN_LO
    VarSetCapacity(buf, 0x10000, 0)
    while (addr < SCAN_HI) {
        n := DllCall("ReadProcessMemory", "Ptr", hProc, "Ptr", addr, "Ptr", &buf, "UPtr", 0x10000, "Ptr", 0)
        if (n) {
            off := 0
            while (off < 0x10000 - 4) {
                v := (gScanType = "float") ? NumGet(buf, off, "Float") : NumGet(buf, off, "Int")
                if ((gScanType = "float") ? (Abs(v - val) < 0.01) : (v = val))
                    gCands.Push(addr + off)
                off += SCAN_STEP
            }
        }
        addr += 0x10000
        if (gCands.Length() > 200000)
            break
    }
    scanStatus := "scanner: " gCands.Length() " candidates (" gScanType " " val ")"
}
NextScan(val) {
    global
    keep := []
    for i, a in gCands {
        v := (gScanType = "float") ? RFloat(a) : RInt(a)
        if ((gScanType = "float") ? (Abs(v - val) < 0.01) : (v = val))
            keep.Push(a)
    }
    gCands := keep
    scanStatus := "scanner: " gCands.Length() " candidates (=" val ")"
    if (gCands.Length() <= 8) {
        t := "scanner HITS:`n"
        for i, a in gCands
            t .= format("  0x{:08x}", a) "`n"
        scanStatus := t
    }
}
F9::
    InputBox, v, First scan, value to find (prefix f for float, e.g. f0.5):, , 320, 130
    if (ErrorLevel)
        return
    gScanType := (SubStr(v,1,1)="f") ? "float" : "int"
    val := (gScanType="float") ? SubStr(v,2)+0 : v+0
    scanStatus := "scanning..."
    FirstScan(val)
return
F10::
    InputBox, v, Next scan, new value:, , 320, 130
    if (ErrorLevel)
        return
    val := (gScanType="float") ? (SubStr(v,1,1)="f" ? SubStr(v,2) : v)+0 : v+0
    NextScan(val)
return
F11::
    t := gCands.Length() " candidates`n"
    Loop, % Min(gCands.Length(), 20)
        t .= format("  0x{:08x} = ", gCands[A_Index]) ((gScanType="float") ? RFloat(gCands[A_Index]) : RInt(gCands[A_Index])) "`n"
    MsgBox, % t
return

GuiClose:
ExitApp
