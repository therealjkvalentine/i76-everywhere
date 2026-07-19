; Interstate '76 world scanner — enumerate every vehicle in the mission.
; Runs INSIDE the Wine prefix (same session as i76.exe). Read-only.
;
; Uses the live-verified ENTITY TABLE (docs/STATIC-RE-FABLE.md section 11/12):
;   8 faction/team groups; counts @ 0x51f5d0, pointer arrays @ 0x507da0
;   (stride 0x100, 64 slots/group). entity(g,s) = [0x507da0 + g*0x100 + s*4].
;   From an entity wrapper: [.] -> +0x70 -> +0x108 = vehicle-LOGIC object;
;   AI aggression = logic + 0xa818.
;   Player fast-path (Tier 2): [[[0x54a264]] + 0x70].
;
; Output: C:\AutoHotkey\worldscan.out — one line per car (group, handle, logic,
; aggression, + player marker). This is the data layer for a radar/minimap or a
; threat display; add the position offset once it's pinned by correlation.
;
; Launch: wine AutoHotkeyU32.exe i76-worldscan.ahk   (game must be in a mission)

#NoEnv
#SingleInstance Force

Process, Exist, i76.exe
pid := ErrorLevel
if (!pid) {
    Process, Exist, nitro.exe
    pid := ErrorLevel
}
h := DllCall("OpenProcess", "UInt", 0x38, "Int", 0, "UInt", pid, "Ptr")

RU(a) {
    global h
    VarSetCapacity(b, 4, 0)
    return DllCall("ReadProcessMemory","Ptr",h,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0) ? NumGet(b,0,"UInt") : 0
}

player := RU(RU(RU(0x54a264)) + 0x70)
out := "I'76 world scan  pid=" pid "  player_entity=0x" Format("{:08x}", player) "`n"
out .= "grp slot  wrapper     logic       aggr  note`n"
total := 0
Loop, 8 {
    g := A_Index - 1
    cnt := RU(0x51f5d0 + g*4)
    if (cnt <= 0 || cnt > 64)
        continue
    Loop, % cnt {
        s := A_Index - 1
        ent := RU(0x507da0 + g*0x100 + s*4)
        if (!ent)
            continue
        total += 1
        inner := RU(ent)                 ; [wrapper]
        sub   := RU(inner + 0x70)
        logic := RU(sub + 0x108)
        aggr  := logic ? RU(logic + 0xa818) : "?"
        mark  := ""
        if (ent = player || inner = player || sub = player)
            mark := "<-- PLAYER"
        out .= Format(" {}   {}    0x{:08x}  0x{:08x}  {}   {}`n", g, s, ent, (logic ? logic : 0), aggr, mark)
    }
}
out .= "total vehicles: " total "`n"
FileDelete, C:\AutoHotkey\worldscan.out
FileAppend, %out%, C:\AutoHotkey\worldscan.out
ExitApp
