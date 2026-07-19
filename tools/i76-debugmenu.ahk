; Interstate '76 DEBUG MENU (AutoHotkey v1.1) — live-edit + freeze table.
; The "trainer/debug menu" built on the verified chain (docs/MEMORY-MAP-INDEX.md):
;   entity = [[[0x54a264]]+0x70]          (relaunch-proof root)
;   inventory = entity-0x14C8, 17ish records x 0x38, header (7, 0x00750000),
;               CURRENT @+0x08 / MAX @+0x0c  (weapon ammo + part condition)
;   armor candidate grids (UNVERIFIED, int tenths): entity-0x800 (armor?),
;               entity+0x135c (chassis?) — shown in the GRIDS view, edit at
;               your own risk until docs/MEMORY-MAP-INDEX.md Tier 3b locks.
;
; Views: INVENTORY (cur/max records) and GRIDS (armor/chassis candidates).
; Every row: double-click = edit the value; CHECKBOX = FREEZE (the value at
; check time — or your edit — is rewritten every 50ms, relocation-proof
; because freezes are stored as entity-RELATIVE offsets and the chain is
; re-resolved each tick).
;
; Hotkeys: F5 refresh view   F6 rearm+repair all (cur=max)   F7 switch view
;          F8 hide/show      F9 unfreeze all
; Launch:  wine AutoHotkeyU32.exe i76-debugmenu.ahk   (game in a mission)
; Only touches i76.exe process memory; writes no files.
; STATUS: NOT yet field-run (2026-07-19) — built from the verified map;
; the chain + rearm write path itself is field-tested via i76-rearm.ahk.

#NoEnv
#Persistent
#SingleInstance Force
SetBatchLines, -1

global hProc := 0, gPid := 0, gView := "inv", gShow := true
global gRows := [], gFrozen := {}, gEnt := 0, gTick := 0

Process, Exist, i76.exe
gPid := ErrorLevel
hProc := DllCall("OpenProcess","UInt",0x38,"Int",0,"UInt",gPid,"Ptr")

Gui, +AlwaysOnTop +ToolWindow
Gui, Color, 0d0d0d
Gui, Font, s9 cB8E6B8, Consolas
Gui, Add, Text, x8 y4 w430 vST, i76 debug menu — attaching...
Gui, Add, ListView, x8 y22 w430 r18 Checked Grid vLV gLVevt AltSubmit, frz#|row|cur|max
LV_ModifyCol(1, 50), LV_ModifyCol(2, 170), LV_ModifyCol(3, 90), LV_ModifyCol(4, 90)
Gui, Add, Text, x8 y+2 w430 cGray, F5 refresh  F6 rearm all  F7 view  F8 hide  F9 unfreeze | dbl-click=edit  checkbox=freeze
Gui, Show, x8 y8 NoActivate, i76debugmenu
Rebuild()
SetTimer, Tick, 50
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
Entity() {
    w := RI(0x54a264)
    if (w = "ERR" || U(w) < 0x10000)
        return 0
    e := RI(U(RI(U(w))) + 0x70)
    return (e = "ERR" || U(e) < 0x10000) ? 0 : U(e)
}
; inventory table base for entity e: fixed offset first, then signature sweep
InvTable(e) {
    t := e - 0x14C8
    if (RI(t) = 7 && U(RI(t+4)) = 0x750000)
        return t
    a := e - 0x1500
    while (a < e - 0x0F00) {
        if (RI(a) = 7 && U(RI(a+4)) = 0x750000)
            return a
        a += 4
    }
    return 0
}

Rebuild() {
    global
    gEnt := Entity()
    gRows := []
    LV_Delete()
    if (!gEnt)
        return
    if (gView = "inv") {
        t := InvTable(gEnt)
        i := 0
        while (t && i < 30) {
            r := t + i*0x38
            if (!(RI(r) = 7 && U(RI(r+4)) = 0x750000))
                break
            gRows.Push({"rel": r+8-gEnt, "name": Format("rec {:02}", i), "hasmax": true})
            i++
        }
    } else {
        Loop, 16
            gRows.Push({"rel": -0x800 + (A_Index-1)*4, "name": Format("armor? -0x800+{:02x}", (A_Index-1)*4), "hasmax": false})
        Loop, 16
            gRows.Push({"rel": 0x135c + (A_Index-1)*4, "name": Format("chassis? +0x135c+{:02x}", (A_Index-1)*4), "hasmax": false})
    }
    for i, row in gRows {
        cur := RI(gEnt + row.rel)
        mx := row.hasmax ? RI(gEnt + row.rel + 4) : ""
        LV_Add(gFrozen.HasKey(row.rel) ? "Check" : "", "", row.name, cur, mx)
    }
}

Tick:
    gTick++
    e := Entity()
    if (e)
        gEnt := e
    ; 1) enforce freezes every 50ms (entity-relative -> relocation-proof)
    if (gEnt) {
        for rel, val in gFrozen
            WI(gEnt + rel, val)
    }
    ; 2) every 4th tick: sync checkbox state + refresh visible values
    if (Mod(gTick, 4))
        return
    checked := {}
    r := 0
    while (r := LV_GetNext(r, "Checked"))
        checked[r] := true
    for i, row in gRows {
        if (checked.HasKey(i)) {
            if (!gFrozen.HasKey(row.rel) && gEnt) {
                v := RI(gEnt + row.rel)                  ; capture at check time
                if (v != "ERR")
                    gFrozen[row.rel] := v
            }
        } else if (gFrozen.HasKey(row.rel))
            gFrozen.Delete(row.rel)
    }
    if (gShow && gEnt) {
        nf := 0
        for rel, val in gFrozen
            nf++
        for i, row in gRows {
            cur := gFrozen.HasKey(row.rel) ? gFrozen[row.rel] : RI(gEnt + row.rel)
            LV_Modify(i, "Col3", cur)
        }
        GuiControl,, ST, % "pid " gPid "  entity=0x" Format("{:08x}", gEnt) "  view=" (gView="inv" ? "INVENTORY" : "GRIDS (candidates!)") "  frozen=" nf "  music=" RI(0x524674)
    } else if (gShow)
        GuiControl,, ST, % "pid " gPid "  NO ENTITY (in a mission?)"
return

LVevt:
    if (A_GuiEvent = "DoubleClick" && A_EventInfo >= 1 && A_EventInfo <= gRows.Length()) {
        row := gRows[A_EventInfo]
        cur := RI(gEnt + row.rel)
        InputBox, v, % "Edit " row.name, % "current = " cur "   (entity" (row.rel<0 ? "-0x" Format("{:x}", -row.rel) : "+0x" Format("{:x}", row.rel)) ")`nnew int value:", , 360, 170
        if (ErrorLevel || v = "")
            return
        WI(gEnt + row.rel, v+0)
        if (gFrozen.HasKey(row.rel))
            gFrozen[row.rel] := v+0     ; frozen rows hold the edited value
        LV_Modify(A_EventInfo, "Col3", v+0)
    }
return

F5::Rebuild()
F6::
    if (!gEnt)
        return
    t := InvTable(gEnt)
    n := 0, i := 0
    while (t && i < 30) {
        r := t + i*0x38
        if (!(RI(r) = 7 && U(RI(r+4)) = 0x750000))
            break
        WI(r+8, RI(r+0xc))
        n++, i++
    }
    GuiControl,, ST, % "REARMED+REPAIRED " n " records (cur=max)"
return
F7::
    gView := (gView = "inv") ? "grid" : "inv"
    Rebuild()
return
F8::
    gShow := !gShow
    if (gShow)
        Gui, Show, NoActivate
    else
        Gui, Hide
return
F9::
    gFrozen := {}
    Rebuild()
return

GuiClose:
ExitApp
