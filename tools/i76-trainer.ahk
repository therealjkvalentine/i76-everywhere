; Interstate '76 memory trainer / live-state inspector (AutoHotkey v1.1).
; Runs INSIDE the Wine prefix, same session as i76.exe, so kernel32
; ReadProcessMemory/WriteProcessMemory reach the game across the Wine boundary
; (validated 2026-07-18: reads match the HUD, writes hold).
;
;   - live overlay of the CONFIRMED addresses (camera, input, view mode, FFB)
;   - continuous headless log to C:\AutoHotkey\trainer-state.json (self-test/feed)
;   - F7 head-look WRITE test (sweeps cam yaw -> the view turns = proof)
;   - F6 write any addr,value; F9/F10/F11 value + next-scan scanner
;
; 1997 i76.exe has no ASLR -> loads at 0x400000 under Wine, so the static VAs
; are valid live addresses. Heap addresses (ammo/armor) move per launch -> scan.
; Built on the minimal structure that survives Wine's AutoHotkeyU32 (object
; literals single-line; inline attach in auto-exec). Only touches process memory.

#NoEnv
#Persistent
#SingleInstance Force

global hProc := 0, gPid := 0, gShow := true, gHeadTest := false, gHeadT := 0
global gScanType := "int", gCands := [], scanStatus := "scan: F9 first / F10 next / F11 show"
global A_I76 := {"cam_yaw":0x4c2964, "cam_pitch":0x4c2970, "view_mode":0x4c2728, "in_throttle":0x5367cc, "in_steer":0x5367d4, "ffb_flag":0x52bbd0}
global A_NIT := {"cam_yaw":0x4f38fc, "cam_pitch":0x4f3908, "view_mode":0x4f38c0, "in_throttle":0x5348fc, "in_steer":0x534904, "ffb_flag":0x52bbd0}
global ADDR := A_I76

Process, Exist, i76.exe
gPid := ErrorLevel
if (!gPid) {
    Process, Exist, nitro.exe
    gPid := ErrorLevel
    ADDR := A_NIT
}
hProc := DllCall("OpenProcess", "UInt", 0x38, "Int", 0, "UInt", gPid, "Ptr")

Gui, +AlwaysOnTop +ToolWindow -Caption
Gui, Color, 111111
Gui, Font, s10 cCCFFCC, Consolas
Gui, Add, Text, x8 y6 w400 vTX, i76 trainer starting...
Gui, Show, x8 y8 NoActivate, i76trainer
SetTimer, Tick, 100
return

Tick:
    if (gHeadTest) {
        gHeadT += 0.04
        WFloat(ADDR["cam_yaw"], 0.5 * Sin(gHeadT))
    }
    vm := RInt(ADDR["view_mode"]), yaw := RFloat(ADDR["cam_yaw"]), pit := RFloat(ADDR["cam_pitch"])
    thr := RInt(ADDR["in_throttle"]), st := RInt(ADDR["in_steer"]), ffb := RInt(ADDR["ffb_flag"])
    if (gShow) {
        s := "I'76 TRAINER pid " gPid "  [F8]hide [F7]head [F6]write`n"
        s .= "view=" vm "  yaw=" yaw "  pitch=" pit "`n"
        s .= "throttle=" thr "  steer=" st "  FFB=" ffb "`n"
        s .= "head-test: " (gHeadTest ? "ON (view sweeps)" : "off") "`n" scanStatus
        GuiControl,, TX, %s%
    }
    j := "{""pid"":" gPid ",""view"":" vm ",""yaw"":" yaw ",""pitch"":" pit ",""throttle"":" thr ",""steer"":" st ",""ffb"":" ffb ",""head"":" (gHeadTest?1:0) "}"
    FileDelete, C:\AutoHotkey\trainer-state.json
    FileAppend, %j%, C:\AutoHotkey\trainer-state.json
return

F8::gShow := !gShow
F7::
    gHeadTest := !gHeadTest
    if (!gHeadTest)
        WFloat(ADDR["cam_yaw"], 0)
return
F6::
    InputBox, spec, Write memory, addr`,value  e.g. 25b0728`,9999  or  f4c2964`,0.3, , 400, 130
    if (ErrorLevel)
        return
    c := InStr(spec, ",")
    a := SubStr(spec, 1, c-1), val := SubStr(spec, c+1)
    if (SubStr(a,1,1) = "f")
        WFloat(("0x" SubStr(a,2))+0, val+0.0)
    else
        WInt(("0x" a)+0, val+0)
return
F9::
    InputBox, v, First scan, value (f-prefix = float):, , 320, 130
    if (ErrorLevel)
        return
    gScanType := (SubStr(v,1,1)="f") ? "float" : "int"
    FirstScan((gScanType="float") ? SubStr(v,2)+0.0 : v+0)
return
F10::
    InputBox, v, Next scan, new value:, , 320, 130
    if (ErrorLevel)
        return
    NextScan((gScanType="float") ? ((SubStr(v,1,1)="f")?SubStr(v,2):v)+0.0 : v+0)
return
F11::
    t := gCands.Length() " candidates`n"
    Loop, % (gCands.Length()<25 ? gCands.Length() : 25)
        t .= Format("  0x{:08x} = ", gCands[A_Index]) ((gScanType="float") ? RFloat(gCands[A_Index]) : RInt(gCands[A_Index])) "`n"
    MsgBox, % t
return

RInt(a) {
    global hProc
    VarSetCapacity(b,4,0)
    return DllCall("ReadProcessMemory","Ptr",hProc,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0) ? NumGet(b,0,"Int") : "?"
}
RFloat(a) {
    global hProc
    VarSetCapacity(b,4,0)
    return DllCall("ReadProcessMemory","Ptr",hProc,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0) ? Round(NumGet(b,0,"Float"),4) : "?"
}
WInt(a,v) {
    global hProc
    VarSetCapacity(b,4,0), NumPut(v,b,0,"Int")
    return DllCall("WriteProcessMemory","Ptr",hProc,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0)
}
WFloat(a,v) {
    global hProc
    VarSetCapacity(b,4,0), NumPut(v,b,0,"Float")
    return DllCall("WriteProcessMemory","Ptr",hProc,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0)
}
FirstScan(val) {
    global
    gCands := []
    VarSetCapacity(mbi,28,0), VarSetCapacity(buf,0x100000,0)
    addr := 0
    Loop {
        if (!DllCall("VirtualQueryEx","Ptr",hProc,"Ptr",addr,"Ptr",&mbi,"UPtr",28))
            break
        base := NumGet(mbi,0,"UInt"), rs := NumGet(mbi,12,"UInt")
        stt := NumGet(mbi,16,"UInt"), pr := NumGet(mbi,20,"UInt"), ty := NumGet(mbi,24,"UInt")
        if (rs = 0)
            break
        if (stt=0x1000 && (pr=0x04||pr=0x40) && ty=0x20000 && base<0x7FFF0000) {
            pos := 0
            while (pos < rs) {
                want := (rs-pos<0x100000) ? rs-pos : 0x100000
                if (DllCall("ReadProcessMemory","Ptr",hProc,"Ptr",base+pos,"Ptr",&buf,"UPtr",want,"Ptr",0)) {
                    off := 0
                    while (off < want-4) {
                        x := (gScanType="float") ? NumGet(buf,off,"Float") : NumGet(buf,off,"Int")
                        if ((gScanType="float") ? (Abs(x-val)<0.01) : (x=val))
                            gCands.Push(base+pos+off)
                        off += 4
                    }
                }
                pos += want
            }
        }
        addr := base+rs
        if (addr < base)
            break
    }
    scanStatus := "scan: " gCands.Length() " candidates (" gScanType " " val ")"
}
NextScan(val) {
    global
    keep := []
    for i,a in gCands {
        x := (gScanType="float") ? RFloat(a) : RInt(a)
        if ((gScanType="float") ? (Abs(x-val)<0.01) : (x=val))
            keep.Push(a)
    }
    gCands := keep
    scanStatus := "scan: " gCands.Length() " left (=" val ")"
    if (gCands.Length() <= 6) {
        t := "HITS: "
        for i,a in gCands
            t .= Format("0x{:08x} ", a)
        scanStatus := t
    }
}
GuiClose:
ExitApp
