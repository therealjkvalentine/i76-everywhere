; Interstate '76 repair + rearm tool (AutoHotkey v1.1) — chain-based, relaunch-proof.
; Walks the static pointer chain to the live vehicle inventory table and, on
; demand, sets every record's CURRENT = MAX (full ammo + full part condition).
; Read-only until you press the hotkey; nothing is written on load.
;
; Chain (docs/GHIDRA-MEMORY-MAP.md PART 13/13b, live-verified across a mission
; reload, GOG Gold i76.exe, no ASLR -> base 0x400000 under Wine):
;   entity = [ [ [0x54a264] ] + 0x70 ]
;   table  = entity - 0x14C8          ; 17 records x 0x38
;   record = table + i*0x38 : header int7 @+0x00, 0x00750000 @+0x04,
;            CURRENT @+0x08, MAX @+0x0c   (ammo for weapons, condition for parts)
;
; Launch:  wine AutoHotkeyU32.exe i76-rearm.ahk   (game running)
; Hotkeys: F5 = show table (read-only)   F6 = REARM+REPAIR (write cur=max)
; Only touches i76.exe process memory; writes no files.

#NoEnv
#Persistent
#SingleInstance Force
global hProc := 0

Process, Exist, i76.exe
hProc := DllCall("OpenProcess","UInt",0x38,"Int",0,"UInt",ErrorLevel,"Ptr")
Gui, +AlwaysOnTop +ToolWindow -Caption
Gui, Color, 101010
Gui, Font, s10 cAACCFF, Consolas
Gui, Add, Text, x8 y6 w520 vTX, i76 rearm - F5 show / F6 rearm+repair
Gui, Show, x8 y8 NoActivate, i76rearm
return

RI(a) {
    global hProc
    VarSetCapacity(b,4,0)
    return DllCall("ReadProcessMemory","Ptr",hProc,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0) ? NumGet(b,0,"Int") : "ERR"
}
WI(a,v) {
    global hProc
    VarSetCapacity(b,4,0), NumPut(v,b,0,"Int")
    return DllCall("WriteProcessMemory","Ptr",hProc,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0)
}
U(x) {
    return x<0 ? x+4294967296 : x
}
; resolve the inventory table base via the chain; verify header; return 0 on fail
Table() {
    w := U(RI(0x54a264))
    if (w = "ERR" || w < 0x10000)
        return 0
    w := U(RI(w))
    ent := U(RI(w+0x70))
    if (ent < 0x10000)
        return 0
    t := ent - 0x14C8
    if (RI(t) = 7 && U(RI(t+4)) = 0x750000)
        return t
    ; fallback: sweep entity-0x1500..entity-0x1000 for the header signature
    a := ent-0x1500
    while (a < ent-0x0F00) {
        if (RI(a) = 7 && U(RI(a+4)) = 0x750000)
            return a
        a += 4
    }
    return 0
}

F5::
    t := Table()
    if (!t) {
        GuiControl,, TX, table not found (game running? in a mission?)
        return
    }
    s := "inventory @0x" Format("{:08x}",t) " (cur/max):`n"
    i := 0
    while (i < 30) {
        r := t + i*0x38
        if (!(RI(r) = 7 && U(RI(r+4)) = 0x750000))
            break
        s .= Format("#{:02} {}/{}`n", i, RI(r+8), RI(r+0xc))
        i++
    }
    GuiControl,, TX, %s%
return

F6::
    t := Table()
    if (!t) {
        GuiControl,, TX, table not found - not rearming
        return
    }
    n := 0, i := 0
    while (i < 30) {
        r := t + i*0x38
        if (!(RI(r) = 7 && U(RI(r+4)) = 0x750000))
            break
        WI(r+8, RI(r+0xc))   ; current = max
        n++, i++
    }
    GuiControl,, TX, % "REARMED + REPAIRED " n " records (cur=max)"
return

GuiClose:
ExitApp
