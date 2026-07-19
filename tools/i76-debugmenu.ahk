; Interstate '76 DEBUG MENU (AutoHotkey v1.1) — live-edit + freeze + field lab.
; Built on the verified chain (docs/MEMORY-MAP-INDEX.md):
;   entity = [[[0x54a264]]+0x70]          (relaunch-proof root)
;   inventory = entity-0x14C8, ~17 records x 0x38, header (7, 0x00750000),
;               CURRENT @+0x08 / MAX @+0x0c  (weapon ammo + part condition)
;   armor/chassis candidate grids (UNVERIFIED, int tenths) around entity-0x800
;               and entity+0x135c — widened windows shown in the GRIDS view.
;
; Views (F7): INVENTORY / GRIDS. ALL rows of BOTH views are monitored and
; logged every 200ms regardless of which view is displayed.
; Row interactions: double-click = edit; CHECKBOX = FREEZE (value at check
; time — or your edit — rewritten every 50ms; freezes are entity-RELATIVE, so
; they survive relocation). "*" in col 1 = value changed in the last ~3s.
; Logs (fetch with tools/debugmenu.sh --fetch):
;   C:\AutoHotkey\debugmenu.log — every unfrozen value change, timestamped
;   C:\AutoHotkey\debugmenu.out — full snapshot every ~2s
;
; F4 FACET SCAN — the armor-locker: give it the 8 DEFENSE numbers from the
; garage (tenths auto-applied) and it sweeps entity-0x8000..+0x8000 for runs
; matching (x,R,L,B) armor / (x,R,L,B) chassis (front wildcarded — it may
; already be damaged). Hits print + log as entity-relative offsets.
;
; Hotkeys: F4 facet scan  F5 refresh  F6 rearm all  F7 view  F8 hide  F9 unfreeze
; Launch:  tools/debugmenu.sh   (game in a mission)
; FIELD-RUN 2026-07-19: chain+GUI+logging verified live (rec13=7.62T ammo
; confirmed vs HUD; rec10 drains in sync with it — unidentified). This
; revision (colors/topmost/monitor-all/F4) not yet re-run.

#NoEnv
#Persistent
#SingleInstance Force
SetBatchLines, -1

global hProc := 0, gPid := 0, gView := "inv", gShow := true
global gAll := [], gLvIdx := [], gFrozen := {}, gEnt := 0, gTick := 0
global gPrev := {}, gMark := {}, gLogN := 0

Process, Exist, i76.exe
gPid := ErrorLevel
hProc := DllCall("OpenProcess","UInt",0x38,"Int",0,"UInt",gPid,"Ptr")

Gui, +AlwaysOnTop +ToolWindow
Gui, Color, 0d0d0d
Gui, Font, s10 cB8E6B8, Consolas
Gui, Add, Text, x8 y4 w480 vST, i76 debug menu — attaching...
Gui, Font, s10 c101010, Consolas
Gui, Add, ListView, x8 y24 w480 r20 Checked Grid vLV gLVevt AltSubmit, frz *|row|cur|max
LV_ModifyCol(1, 52), LV_ModifyCol(2, 210), LV_ModifyCol(3, 95), LV_ModifyCol(4, 95)
Gui, Font, s9 c9A9A9A, Consolas
Gui, Add, Text, x8 y+2 w480, F4 facet-scan  F5 refresh  F6 rearm  F7 view  F8 hide  F9 unfreeze | dblclick=edit  box=freeze
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
RelName(rel) {
    return rel < 0 ? "-0x" Format("{:x}", -rel) : "+0x" Format("{:x}", rel)
}
Entity() {
    w := RI(0x54a264)
    if (w = "ERR" || U(w) < 0x10000)
        return 0
    e := RI(U(RI(U(w))) + 0x70)
    return (e = "ERR" || U(e) < 0x10000) ? 0 : U(e)
}
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

; one flat model of every monitored offset; the view only filters the display
BuildAll() {
    global
    gAll := []
    if (!gEnt)
        return
    t := InvTable(gEnt)
    i := 0
    while (t && i < 30) {
        r := t + i*0x38
        if (!(RI(r) = 7 && U(RI(r+4)) = 0x750000))
            break
        gAll.Push({"rel": r+8-gEnt, "name": Format("rec {:02}", i), "hasmax": true, "view": "inv"})
        i++
    }
    Loop, 96
        gAll.Push({"rel": -0x880 + (A_Index-1)*4, "name": "armor? " RelName(-0x880 + (A_Index-1)*4), "hasmax": false, "view": "grid"})
    Loop, 96
        gAll.Push({"rel": 0x12e0 + (A_Index-1)*4, "name": "chassis? " RelName(0x12e0 + (A_Index-1)*4), "hasmax": false, "view": "grid"})
}

Rebuild() {
    global
    e := Entity()
    if (e)
        gEnt := e
    BuildAll()
    gPrev := {}, gMark := {}, gLvIdx := []
    LV_Delete()
    for i, row in gAll {
        cur := RI(gEnt + row.rel)
        gPrev[row.rel] := cur
        if (row.view != gView)
            continue
        gLvIdx.Push(i)
        LV_Add(gFrozen.HasKey(row.rel) ? "Check" : "", "", row.name, cur, row.hasmax ? RI(gEnt + row.rel + 4) : "")
    }
}

Tick:
    gTick++
    e := Entity()
    if (e)
        gEnt := e
    if (gEnt) {
        for rel, val in gFrozen
            WI(gEnt + rel, val)
    }
    if (Mod(gTick, 4))
        return
    ; sync checkboxes (visible rows only) -> the freeze map
    checked := {}
    r := 0
    while (r := LV_GetNext(r, "Checked"))
        checked[r] := true
    for lvrow, ai in gLvIdx {
        rel := gAll[ai].rel
        if (checked.HasKey(lvrow)) {
            if (!gFrozen.HasKey(rel) && gEnt) {
                v := RI(gEnt + rel)
                if (v != "ERR")
                    gFrozen[rel] := v
            }
        } else if (gFrozen.HasKey(rel))
            gFrozen.Delete(rel)
    }
    if (gEnt) {
        nf := 0
        for rel, val in gFrozen
            nf++
        snap := "", lvrow := 0, lvmap := {}
        for lvrow2, ai2 in gLvIdx
            lvmap[ai2] := lvrow2
        for i, row in gAll {
            cur := gFrozen.HasKey(row.rel) ? gFrozen[row.rel] : RI(gEnt + row.rel)
            if (!gFrozen.HasKey(row.rel) && gPrev.HasKey(row.rel) && cur != "ERR" && gPrev[row.rel] != "ERR" && cur != gPrev[row.rel]) {
                gMark[row.rel] := gTick
                if (gLogN < 8000) {
                    FileAppend, % A_Hour ":" A_Min ":" A_Sec " " row.name " " gPrev[row.rel] " -> " cur "`n", C:\AutoHotkey\debugmenu.log
                    gLogN++
                }
            }
            gPrev[row.rel] := cur
            if (gShow && lvmap.HasKey(i)) {
                mark := (gMark.HasKey(row.rel) && gTick - gMark[row.rel] < 60) ? "*" : ""
                LV_Modify(lvmap[i], "Col1", mark), LV_Modify(lvmap[i], "Col3", cur)
            }
            snap .= row.name "=" cur (row.hasmax ? "/" RI(gEnt + row.rel + 4) : "") "`n"
        }
        if (gShow)
            GuiControl,, ST, % "pid " gPid "  entity=0x" Format("{:08x}", gEnt) "  " (gView="inv" ? "INVENTORY" : "GRIDS(cand)") "  frozen=" nf "  music=" RI(0x524674)
        if (!Mod(gTick, 40)) {
            FileDelete, C:\AutoHotkey\debugmenu.out
            FileAppend, % "entity=0x" Format("{:08x}", gEnt) " view=" gView " frozen=" nf "`n" snap, C:\AutoHotkey\debugmenu.out
            WinSet, AlwaysOnTop, On, i76debugmenu   ; re-assert over the game window
        }
    } else if (gShow)
        GuiControl,, ST, % "pid " gPid "  NO ENTITY (in a mission?)"
return

LVevt:
    if (A_GuiEvent = "DoubleClick" && A_EventInfo >= 1 && A_EventInfo <= gLvIdx.Length()) {
        row := gAll[gLvIdx[A_EventInfo]]
        cur := RI(gEnt + row.rel)
        InputBox, v, % "Edit " row.name, % "current = " cur "   (entity" RelName(row.rel) ")`nnew int value:", , 360, 170
        if (ErrorLevel || v = "")
            return
        WI(gEnt + row.rel, v+0)
        if (gFrozen.HasKey(row.rel))
            gFrozen[row.rel] := v+0
        LV_Modify(A_EventInfo, "Col3", v+0)
    }
return

; ---- F4: scan entity-0x8000..+0x8000 for the DEFENSE facet runs ----
; matches (?,R,L,B) with FRONT wildcarded (it may be damaged); logs entity-
; relative offsets of every hit. Chunked RPM (4KB) so the sweep is instant.
F4::
    if (!gEnt) {
        GuiControl,, ST, no entity - facet scan needs a mission
        return
    }
    InputBox, spec, Facet scan, % "8 DEFENSE numbers as shown in the garage`n(armor F,R,L,B, chassis F,R,L,B):", , 420, 170, , , , , 100`,57`,57`,76`,70`,35`,35`,50
    if (ErrorLevel)
        return
    vals := []
    Loop, Parse, spec, `,, %A_Space%
        vals.Push(Round(A_LoopField * 10))
    if (vals.Length() != 8) {
        GuiControl,, ST, % "need exactly 8 numbers, got " vals.Length()
        return
    }
    out := "FACET SCAN garage(a " vals[1] "," vals[2] "," vals[3] "," vals[4] " c " vals[5] "," vals[6] "," vals[7] "," vals[8] ")`n"
    hits := 0
    ; single contiguous read of a ±0x10000 window (no chunk-boundary misses);
    ; VirtualQueryEx-free — the window sits inside the entity's committed heap.
    WIN := 0x20000, half := 0x10000
    VarSetCapacity(buf, WIN, 0)
    base := gEnt - half
    got := 0
    DllCall("ReadProcessMemory","Ptr",hProc,"Ptr",base,"Ptr",&buf,"UPtr",WIN,"Ptr*",got)
    if (got < 16) {
        ; heap page may not span the full window; retry the near side only
        WIN := 0x8000, base := gEnt - 0x4000
        DllCall("ReadProcessMemory","Ptr",hProc,"Ptr",base,"Ptr",&buf,"UPtr",WIN,"Ptr*",got)
    }
    off := 0
    while (off <= got - 16) {
        v1 := NumGet(buf, off, "Int"), v2 := NumGet(buf, off+4, "Int"), v3 := NumGet(buf, off+8, "Int"), v4 := NumGet(buf, off+12, "Int")
        if (v2 = vals[2] && v3 = vals[3] && v4 = vals[4] && v1 >= 0 && v1 <= vals[1]) {
            out .= "  ARMOR?   entity" RelName(base+off-gEnt) " = " v1 "," v2 "," v3 "," v4 "`n"
            hits++
        }
        if (v2 = vals[6] && v3 = vals[7] && v4 = vals[8] && v1 >= 0 && v1 <= vals[5]) {
            out .= "  CHASSIS? entity" RelName(base+off-gEnt) " = " v1 "," v2 "," v3 "," v4 "`n"
            hits++
        }
        off += 4
    }
    out .= "  scanned " got " bytes, " hits " hit(s)`n"
    FileAppend, %out%, C:\AutoHotkey\debugmenu.log
    MsgBox, 0, facet scan, %out%
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
