; Interstate '76 DEBUG MENU (AutoHotkey v1.1) — live-edit + freeze + field lab.
; Built on the verified chain (docs/MEMORY-MAP-INDEX.md):
;   entity = [[[0x54a264]]+0x70]                (relaunch-proof root)
;   AMMO table = entity-0x1228  (= 0x25b0720 the session PART 12 live-matched to
;     the HUD; row0 = 50cal, row1 = 7.62T). Records: header int7 @+0x00,
;     0x00750000 @+0x04, CURRENT @+0x08, MAX @+0x0c. Stride 0x38.
;   VAN table  = entity-0x14C8  (same structure, 12 records BEFORE the ammo
;     table — owned-but-unmounted / repair-queue weapons).
;
; Views (F7 cycles): AMMO (car weapons, row0=50cal) / VAN (preceding table) /
;   GRIDS (armor candidate offsets). Every offset in every view is monitored
;   and logged each 200ms regardless of the displayed view.
; Row interactions: double-click = edit value; CHECKBOX = FREEZE (value at
;   check time — or your edit — rewritten every 50ms; entity-RELATIVE so it
;   survives relocation). "*" in col 1 = value changed in the last ~3s.
;   F3 = rename the selected row (label persists for the session).
; Logs (tools/debugmenu.sh --fetch):
;   C:\AutoHotkey\debugmenu.log — every unfrozen value change, timestamped
;   C:\AutoHotkey\debugmenu.out — full snapshot every ~2s
;
; F4 FACET SCAN — the armor-locker: enter the 8 DEFENSE numbers from the
;   garage; it sweeps the entity's committed heap region for a (front,R,L,B)
;   armor run and (front,R,L,B) chassis run, trying tenths (x10) AND raw, and
;   logs every hit as an entity-relative offset. Front is wildcarded (may be
;   damaged). Uses VirtualQueryEx to clamp to mapped memory (an over-wide raw
;   read returns 0 bytes under Wine — that was the "scanned 0 bytes" bug).
;
; Hotkeys: F3 rename  F4 facet scan  F5 refresh  F6 rearm car  F7 view
;          F8 hide  F9 unfreeze
; Launch:  tools/debugmenu.sh   (game in a mission)
; FIELD-RUN 2026-07-19: chain+GUI+logging verified; base corrected -0x14C8 ->
; -0x1228 so records align with the HUD. This revision not yet re-run.

#NoEnv
#Persistent
#SingleInstance Force
SetBatchLines, -1

global hProc := 0, gPid := 0, gView := "ammo", gShow := true
global gAll := [], gLvIdx := [], gFrozen := {}, gEnt := 0, gTick := 0
global gPrev := {}, gMark := {}, gLogN := 0, gLabels := {}
; confident names by record MAX capacity (PART 12 live-verified the first two)
global gNameByMax := {2000: "50cal MG", 4000: "7.62 Turret"}

Process, Exist, i76.exe
gPid := ErrorLevel
hProc := DllCall("OpenProcess","UInt",0x38,"Int",0,"UInt",gPid,"Ptr")

Gui, +AlwaysOnTop +ToolWindow
Gui, Color, 0d0d0d
Gui, Font, s10 cB8E6B8, Consolas
Gui, Add, Text, x8 y4 w600 vST, i76 debug menu - attaching...
Gui, Font, s10 c101010, Consolas
Gui, Add, ListView, x8 y24 w600 r18 Checked Grid vLV gLVevt AltSubmit, frz *|#|name (guess)|cur|max|addr
LV_ModifyCol(1, 44), LV_ModifyCol(2, 34), LV_ModifyCol(3, 190), LV_ModifyCol(4, 95), LV_ModifyCol(5, 95), LV_ModifyCol(6, 110)
Gui, Font, s9 c9A9A9A, Consolas
Gui, Add, Text, x8 y+3 w600, F3 rename  F4 facet-scan  F5 refresh  F6 rearm  F7 view  F8 hide  F9 unfreeze | dblclick=edit  box=freeze
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
; validate the (7, 0x00750000) header at a candidate base
HdrOK(a) {
    return (RI(a) = 7 && U(RI(a+4)) = 0x750000)
}
; ammo table: PART 12/13 base entity-0x1228 (verified) first, then the -0x14C8
; superset, then a sweep. Returns the base that starts the CAR weapons.
AmmoTable(e) {
    if (HdrOK(e - 0x1228))
        return e - 0x1228
    if (HdrOK(e - 0x14C8))
        return e - 0x14C8
    a := e - 0x1500
    while (a < e - 0x0F00) {
        if (HdrOK(a))
            return a
        a += 4
    }
    return 0
}

BuildAll() {
    global
    gAll := []
    if (!gEnt)
        return
    if (gView = "ammo" || gView = "van") {
        t := (gView = "ammo") ? AmmoTable(gEnt) : gEnt - 0x14C8
        if (!t)
            return
        i := 0
        while (i < 24) {
            r := t + i*0x38
            if (!HdrOK(r))
                break
            gAll.Push({"rel": r+8-gEnt, "abs": r+8, "name": Format("{:02}", i), "hasmax": true, "view": gView, "idx": i})
            i++
        }
    } else {  ; grid: armor/chassis candidate windows (tenths ints)
        Loop, 96
            gAll.Push({"rel": -0x880 + (A_Index-1)*4, "abs": 0, "name": "armor? " RelName(-0x880 + (A_Index-1)*4), "hasmax": false, "view": "grid", "idx": -1})
        Loop, 96
            gAll.Push({"rel": 0x12e0 + (A_Index-1)*4, "abs": 0, "name": "chassis? " RelName(0x12e0 + (A_Index-1)*4), "hasmax": false, "view": "grid", "idx": -1})
    }
}

; the display name: manual label > confident by-max name > "?"
GuessName(row) {
    global gLabels, gNameByMax
    if (gLabels.HasKey(row.rel))
        return gLabels[row.rel]
    if (row.view = "grid")
        return row.name
    mx := RI(gEnt + row.rel + 4)
    if (gNameByMax.HasKey(mx))
        return gNameByMax[mx]
    return "? (cap " mx ")"
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
        LV_Add(gFrozen.HasKey(row.rel) ? "Check" : "", "", row.name, (row.view="grid" ? "" : GuessName(row)), cur, row.hasmax ? RI(gEnt + row.rel + 4) : "", row.abs ? Format("0x{:08x}", row.abs) : "")
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
        snap := "", lvmap := {}
        for lvrow2, ai2 in gLvIdx
            lvmap[ai2] := lvrow2
        for i, row in gAll {
            cur := gFrozen.HasKey(row.rel) ? gFrozen[row.rel] : RI(gEnt + row.rel)
            if (!gFrozen.HasKey(row.rel) && gPrev.HasKey(row.rel) && cur != "ERR" && gPrev[row.rel] != "ERR" && cur != gPrev[row.rel]) {
                gMark[row.rel] := gTick
                if (gLogN < 8000) {
                    lbl := (row.view = "grid") ? row.name : (row.view "#" row.name " " GuessName(row))
                    FileAppend, % A_Hour ":" A_Min ":" A_Sec " " lbl " " gPrev[row.rel] " -> " cur "`n", C:\AutoHotkey\debugmenu.log
                    gLogN++
                }
            }
            gPrev[row.rel] := cur
            if (gShow && lvmap.HasKey(i)) {
                mark := (gMark.HasKey(row.rel) && gTick - gMark[row.rel] < 60) ? "*" : ""
                LV_Modify(lvmap[i], "Col1", mark), LV_Modify(lvmap[i], "Col4", cur)
            }
            snap .= row.view "#" row.name "=" cur (row.hasmax ? "/" RI(gEnt + row.rel + 4) : "") "`n"
        }
        if (gShow)
            GuiControl,, ST, % "pid " gPid "  entity=0x" Format("{:08x}", gEnt) "  view=" gView "  frozen=" nf "  music=" RI(0x524674)
        if (!Mod(gTick, 40)) {
            FileDelete, C:\AutoHotkey\debugmenu.out
            FileAppend, % "entity=0x" Format("{:08x}", gEnt) " view=" gView " frozen=" nf "`n" snap, C:\AutoHotkey\debugmenu.out
            WinSet, AlwaysOnTop, On, i76debugmenu
        }
    } else if (gShow)
        GuiControl,, ST, % "pid " gPid "  NO ENTITY (in a mission?)"
return

LVevt:
    if (A_GuiEvent = "DoubleClick" && A_EventInfo >= 1 && A_EventInfo <= gLvIdx.Length()) {
        row := gAll[gLvIdx[A_EventInfo]]
        cur := RI(gEnt + row.rel)
        InputBox, v, % "Edit " GuessName(row), % "current = " cur "   (entity" RelName(row.rel) (row.abs ? ", 0x" Format("{:08x}",row.abs) : "") ")`nnew int value:", , 380, 170
        if (ErrorLevel || v = "")
            return
        WI(gEnt + row.rel, v+0)
        if (gFrozen.HasKey(row.rel))
            gFrozen[row.rel] := v+0
        LV_Modify(A_EventInfo, "Col4", v+0)
    }
return

; F3: rename the selected row (label persists for the session)
F3::
    sel := LV_GetNext(0)
    if (!sel || sel > gLvIdx.Length())
        return
    row := gAll[gLvIdx[sel]]
    InputBox, nm, Rename row, % "label for entity" RelName(row.rel) ":", , 360, 150, , , , , % GuessName(row)
    if (ErrorLevel)
        return
    gLabels[row.rel] := nm
    LV_Modify(sel, "Col3", nm)
return

; F4: facet scan — clamp to the entity's committed region, scan for the tuple
F4::
    if (!gEnt) {
        GuiControl,, ST, no entity - facet scan needs a mission
        return
    }
    InputBox, spec, Facet scan, % "8 DEFENSE numbers from the garage`n(armor F,R,L,B then chassis F,R,L,B):", , 440, 170, , , , , 100`,57`,57`,76`,70`,35`,35`,50
    if (ErrorLevel)
        return
    raw := []
    Loop, Parse, spec, `,, %A_Space%
        raw.Push(A_LoopField + 0)
    if (raw.Length() != 8) {
        GuiControl,, ST, % "need 8 numbers, got " raw.Length()
        return
    }
    ; committed region containing the entity (RPM of unmapped pages returns 0)
    VarSetCapacity(mbi, 28, 0)
    if (!DllCall("VirtualQueryEx","Ptr",hProc,"Ptr",gEnt,"Ptr",&mbi,"UPtr",28)) {
        MsgBox, VirtualQueryEx failed
        return
    }
    rBase := NumGet(mbi,0,"UPtr"), rSize := NumGet(mbi,12,"UPtr")
    lo := gEnt - 0x8000, hi := gEnt + 0x8000
    if (lo < rBase)
        lo := rBase
    if (hi > rBase + rSize)
        hi := rBase + rSize
    span := hi - lo
    if (span < 16 || span > 0x100000) {
        MsgBox, % "region odd: base 0x" Format("{:08x}",rBase) " size 0x" Format("{:x}",rSize)
        return
    }
    VarSetCapacity(buf, span, 0)
    got := 0
    DllCall("ReadProcessMemory","Ptr",hProc,"Ptr",lo,"Ptr",&buf,"UPtr",span,"Ptr*",got)
    out := "FACET SCAN garage(a " raw[1] "," raw[2] "," raw[3] "," raw[4] " c " raw[5] "," raw[6] "," raw[7] "," raw[8] ") region 0x" Format("{:08x}",lo) "+0x" Format("{:x}",got) "`n"
    hits := 0
    ; try both encodings: tenths (x10) and raw
    for si, scale in [10, 1] {
        aF := raw[1]*scale, aR := raw[2]*scale, aL := raw[3]*scale, aB := raw[4]*scale
        cF := raw[5]*scale, cR := raw[6]*scale, cL := raw[7]*scale, cB := raw[8]*scale
        off := 0
        while (off <= got - 16) {
            v1 := NumGet(buf,off,"Int"), v2 := NumGet(buf,off+4,"Int"), v3 := NumGet(buf,off+8,"Int"), v4 := NumGet(buf,off+12,"Int")
            if (v2 = aR && v3 = aL && v4 = aB && v1 >= 0 && v1 <= aF) {
                out .= "  ARMOR   x" scale " entity" RelName(lo+off-gEnt) " = " v1 "," v2 "," v3 "," v4 "`n"
                hits++
            }
            if (v2 = cR && v3 = cL && v4 = cB && v1 >= 0 && v1 <= cF) {
                out .= "  CHASSIS x" scale " entity" RelName(lo+off-gEnt) " = " v1 "," v2 "," v3 "," v4 "`n"
                hits++
            }
            off += 4
        }
    }
    out .= "  " hits " hit(s)`n"
    FileAppend, %out%, C:\AutoHotkey\debugmenu.log
    MsgBox, 0, facet scan, %out%
return

F5::Rebuild()
F6::
    if (!gEnt)
        return
    t := AmmoTable(gEnt)
    n := 0, i := 0
    while (t && i < 24) {
        r := t + i*0x38
        if (!HdrOK(r))
            break
        WI(r+8, RI(r+0xc))
        n++, i++
    }
    GuiControl,, ST, % "REARMED+REPAIRED " n " records (cur=max)"
return
F7::
    gView := (gView = "ammo") ? "van" : (gView = "van") ? "grid" : "ammo"
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
