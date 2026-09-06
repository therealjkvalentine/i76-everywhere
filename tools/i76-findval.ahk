; Interstate '76 exact-value finder — scans the live process for one or more
; int32 values and reports each hit as an ABSOLUTE address plus an
; ENTITY-RELATIVE offset (the only kind that survives relocation).
;
; Purpose: when a value you can SEE on the HUD (e.g. ammo 1995) isn't where the
; map says it should be, this locates it in one pass. Feed it two values from
; different weapons and it also reports hits that sit close together — the
; signature of a per-weapon record array.
;
; Driven by a command file so a shell script can run it headless:
;   C:\AutoHotkey\fv.cmd  = space-separated ints, e.g. "1995 3986"
;   C:\AutoHotkey\fv.out  = results
; Launch: tools/findval.sh 1995 3986      (game running, in a mission)
; Read-only: never writes game memory.

#NoEnv
#SingleInstance Force
SetBatchLines, -1

Process, Exist, i76.exe
pid := ErrorLevel
h := DllCall("OpenProcess","UInt",0x38,"Int",0,"UInt",pid,"Ptr")

RI(a) {
    global h
    VarSetCapacity(b,4,0)
    return DllCall("ReadProcessMemory","Ptr",h,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0) ? NumGet(b,0,"Int") : "ERR"
}
U(x) {
    return x<0 ? x+4294967296 : x
}
Rel(off) {
    return off < 0 ? "-0x" Format("{:x}", -off) : "+0x" Format("{:x}", off)
}

; player entity (for relative offsets)
ent := 0
w := RI(0x54a264)
if (w != "ERR" && U(w) > 0x10000) {
    e := RI(U(RI(U(w))) + 0x70)
    if (e != "ERR" && U(e) > 0x10000)
        ent := U(e)
}

FileRead, cmd, C:\AutoHotkey\fv.cmd
cmd := Trim(cmd)

; PEEK mode: "peek 0xADDR [count]" - dump dwords around an address
if (SubStr(cmd, 1, 4) = "peek") {
    parts := StrSplit(SubStr(cmd, 6), " ")
    a := parts[1], n := parts[2] ? parts[2]+0 : 24
    a := (SubStr(a,1,2) = "0x") ? "0x" SubStr(a,3) : a
    a := a + 0
    o := "PEEK 0x" Format("{:08x}", a) " entity=0x" Format("{:08x}", ent) "`n"
    i := -n
    while (i <= n) {
        v := RI(a + i*4)
        o .= "  " (i<0?"-":"+") "0x" Format("{:x}", Abs(i*4)) "  @0x" Format("{:08x}", a+i*4) " = " v "`n"
        i++
    }
    FileDelete, C:\AutoHotkey\fv.out
    FileAppend, %o%, C:\AutoHotkey\fv.out
    ExitApp
}

wants := [], names := []
Loop, Parse, % Trim(cmd), %A_Space%, %A_Space%%A_Tab%%A_CR%%A_LF%
{
    if (A_LoopField != "")
        wants.Push(A_LoopField + 0)
}

out := "FINDVAL pid=" pid " entity=0x" Format("{:08x}", ent) "  looking for:"
for i, v in wants
    out .= " " v
out .= "`n"

hits := []          ; [{val, addr}]
VarSetCapacity(mbi, 28, 0)
VarSetCapacity(buf, 0x100000, 0)
addr := 0, scanned := 0
Loop {
    if (!DllCall("VirtualQueryEx","Ptr",h,"Ptr",addr,"Ptr",&mbi,"UPtr",28))
        break
    base := NumGet(mbi,0,"UPtr"), rs := NumGet(mbi,12,"UPtr")
    stt := NumGet(mbi,16,"UInt"), pr := NumGet(mbi,20,"UInt")
    if (rs = 0)
        break
    ; committed + readable (rw / ro / wc), skip guard/noaccess
    readable := (pr = 0x04 || pr = 0x02 || pr = 0x20 || pr = 0x40 || pr = 0x08 || pr = 0x80)
    if (stt = 0x1000 && readable && base < 0x7FFF0000) {
        pos := 0
        while (pos < rs) {
            want := (rs - pos < 0x100000) ? rs - pos : 0x100000
            got := 0
            if (DllCall("ReadProcessMemory","Ptr",h,"Ptr",base+pos,"Ptr",&buf,"UPtr",want,"Ptr*",got) && got >= 4) {
                scanned += got
                off := 0
                while (off <= got - 4) {
                    x := NumGet(buf, off, "Int")
                    for i, v in wants {
                        if (x = v)
                            hits.Push({"val": v, "addr": base+pos+off})
                    }
                    off += 4
                }
            }
            pos += want
        }
    }
    addr := base + rs
    if (addr < base)
        break
}

out .= "scanned " Round(scanned/1048576,1) "MB, " hits.Length() " hit(s)`n"
; group by value, and flag hits near the entity or near each other
for i, hit in hits {
    line := "  " hit.val "  @0x" Format("{:08x}", hit.addr)
    if (ent) {
        d := hit.addr - ent
        if (d > -0x200000 && d < 0x200000)
            line .= "   entity" Rel(d)
    }
    ; note other wanted values within 0x200 bytes (per-weapon record neighbours)
    near := ""
    for j, other in hits {
        if (j = i || other.val = hit.val)
            continue
        gap := other.addr - hit.addr
        if (gap > -0x200 && gap < 0x200)
            near .= " " other.val "@" (gap<0 ? "-" : "+") "0x" Format("{:x}", Abs(gap))
    }
    if (near != "")
        line .= "   NEAR:" near
    out .= line "`n"
}
if (hits.Length() = 0)
    out .= "  (nothing - is the value still on screen? try again without firing)`n"

FileDelete, C:\AutoHotkey\fv.out
FileAppend, %out%, C:\AutoHotkey\fv.out
ExitApp
