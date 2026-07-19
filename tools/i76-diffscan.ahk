; Interstate '76 differential memory scanner (AutoHotkey v1.1), Cheat-Engine style.
; Runs in the Wine prefix; reads i76.exe live. Driven by a one-line command file
; C:\AutoHotkey\diff.cmd; writes C:\AutoHotkey\diff.out (human summary) and
; C:\AutoHotkey\diff.cands ("type" header then "VA=value" lines). Each "next"
; scan re-reads the live value at each candidate VA and compares to the STORED
; value, so relocation between scans doesn't matter while the struct is stable.
;
; Commands (write to diff.cmd, then run this script):
;   first int   <N>     first scan: all 4-byte ints == N
;   first float <F>     first scan: all floats ~= F
;   next  dec           keep candidates whose value DECREASED since last scan
;   next  inc           keep candidates whose value INCREASED
;   next  same          keep candidates UNCHANGED
;   next  exact <N|F>   keep candidates == N (int) / ~= F (float)

#NoEnv
#SingleInstance Force
SetBatchLines, -1
Process, Exist, i76.exe
pid := ErrorLevel
if (!pid) {
    Process, Exist, nitro.exe
    pid := ErrorLevel
}
h := DllCall("OpenProcess","UInt",0x38,"Int",0,"UInt",pid,"Ptr")

R(a, isF) {
    global h
    VarSetCapacity(b,4,0)
    if !DllCall("ReadProcessMemory","Ptr",h,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0)
        return ""
    return isF ? Round(NumGet(b,0,"Float"),3) : NumGet(b,0,"Int")
}

FileRead, cmd, C:\AutoHotkey\diff.cmd
cmd := Trim(cmd)
p := StrSplit(cmd, " ")
op := p[1]

if (op = "first") {
    isF := (p[2] = "float")
    val := isF ? p[3]+0.0 : p[3]+0
    f := FileOpen("C:\AutoHotkey\diff.cands","w")
    f.WriteLine(isF ? "float" : "int")
    cnt := 0
    VarSetCapacity(mbi,28,0), VarSetCapacity(buf,0x100000,0)
    addr := 0
    Loop {
        if (!DllCall("VirtualQueryEx","Ptr",h,"Ptr",addr,"Ptr",&mbi,"UPtr",28))
            break
        base := NumGet(mbi,0,"UInt"), rs := NumGet(mbi,12,"UInt")
        st := NumGet(mbi,16,"UInt"), pr := NumGet(mbi,20,"UInt"), tp := NumGet(mbi,24,"UInt")
        if (rs = 0)
            break
        if (st=0x1000 && (pr=0x04||pr=0x40) && tp=0x20000 && base<0x7FFF0000) {
            pos := 0
            while (pos < rs) {
                want := (rs-pos<0x100000) ? rs-pos : 0x100000
                if (DllCall("ReadProcessMemory","Ptr",h,"Ptr",base+pos,"Ptr",&buf,"UPtr",want,"Ptr",0)) {
                    off := 0
                    while (off < want-4) {
                        v := isF ? NumGet(buf,off,"Float") : NumGet(buf,off,"Int")
                        if (isF ? (Abs(v-val)<0.01) : (v=val)) {
                            f.WriteLine(Format("{:x}", base+pos+off) "=" (isF ? Round(v,3) : v))
                            cnt += 1
                        }
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
    f.Close()
    FileDelete, C:\AutoHotkey\diff.out
    FileAppend, % "first " p[2] " " p[3] " -> " cnt " candidates", C:\AutoHotkey\diff.out
} else if (op = "next") {
    sub := p[2]
    FileRead, candsraw, C:\AutoHotkey\diff.cands
lines := StrSplit(candsraw, "`n", "`r")
    isF := (lines[1] = "float")
    tgt := (p[3] != "") ? (isF ? p[3]+0.0 : p[3]+0) : ""
    f := FileOpen("C:\AutoHotkey\diff.cands","w")
    f.WriteLine(isF ? "float" : "int")
    cnt := 0, shown := ""
    i := 2
    while (i <= lines.MaxIndex()) {
        ln := Trim(lines[i]), i += 1
        if (ln = "")
            continue
        rec := StrSplit(ln, "=")
        va := ("0x" rec[1]) + 0
        prev := rec[2]+0
        cur := R(va, isF)
        if (cur = "")
            continue
        good := false
        if (sub = "dec")
            good := (cur < prev)
        else if (sub = "inc")
            good := (cur > prev)
        else if (sub = "same")
            good := (cur = prev)
        else if (sub = "exact")
            good := isF ? (Abs(cur-tgt)<0.01) : (cur = tgt)
        if (good) {
            f.WriteLine(rec[1] "=" cur)
            cnt += 1
            if (cnt <= 10)
                shown .= "0x" rec[1] "=" cur "  "
        }
    }
    f.Close()
    FileDelete, C:\AutoHotkey\diff.out
    FileAppend, % "next " sub " -> " cnt " candidates`n" shown, C:\AutoHotkey\diff.out
}
ExitApp
