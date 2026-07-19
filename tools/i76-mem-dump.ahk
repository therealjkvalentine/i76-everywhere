#NoEnv
#SingleInstance Force
SetBatchLines, -1
Process, Exist, i76.exe
pid := ErrorLevel
h := DllCall("OpenProcess","UInt",0x38,"Int",0,"UInt",pid,"Ptr")
idx := FileOpen("C:\AutoHotkey\dump.idx","w")
dmp := FileOpen("C:\AutoHotkey\dump.bin","w")
addr := 0, total := 0, CAP := 402653184  ; 384MB cap
VarSetCapacity(mbi,28,0)
CH := 0x100000
VarSetCapacity(buf, CH, 0)
Loop {
    r := DllCall("VirtualQueryEx","Ptr",h,"Ptr",addr,"Ptr",&mbi,"UPtr",28)
    if (!r)
        break
    base := NumGet(mbi,0,"UInt"), rsize := NumGet(mbi,12,"UInt")
    state := NumGet(mbi,16,"UInt"), prot := NumGet(mbi,20,"UInt"), type := NumGet(mbi,24,"UInt")
    if (rsize=0)
        break
    ; private OR mapped, committed, writable -> game data lives here
    rw := (prot=0x04 || prot=0x40)
    if (state=0x1000 && rw && type=0x20000 && base<0x7FFF0000 && total<CAP) {
        pos := 0
        while (pos < rsize && total < CAP) {
            want := (rsize-pos<CH)?rsize-pos:CH
            n := DllCall("ReadProcessMemory","Ptr",h,"Ptr",base+pos,"Ptr",&buf,"UPtr",want,"Ptr",0)
            if (n) {
                dmp.RawWrite(&buf, want)
                idx.WriteLine(Format("{:08x} {} {}", base+pos, want, total))
                total += want
            }
            pos += want
        }
    }
    addr := base+rsize
    if (addr<base)
        break
}
idx.Close(), dmp.Close()
FileDelete, C:\AutoHotkey\dump.done
FileAppend, % "dumped " total " bytes", C:\AutoHotkey\dump.done
ExitApp
