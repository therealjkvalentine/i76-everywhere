; Chain-based offset differential: reads the vehicle-logic object THROUGH the
; relocation-proof pointer chain [[[0x54a264]]+0x70]+0x10c, so it diffs OFFSETS
; (stable) not absolute addresses (which relocate). Driven by C:\AutoHotkey\cd.cmd:
;   snap   -> record all logic-object offsets 0..0xA00
;   diff   -> re-read; report offsets that changed (int delta) since snap
#NoEnv
#SingleInstance Force
SetBatchLines,-1
Process, Exist, i76.exe
h := DllCall("OpenProcess","UInt",0x38,"Int",0,"UInt",ErrorLevel,"Ptr")
RU(a){
 global h
 VarSetCapacity(b,4,0)
 return DllCall("ReadProcessMemory","Ptr",h,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0) ? NumGet(b,0,"UInt") : 0
}
logic(){
 a1:=RU(0x54a264), a2:=RU(a1), pe:=RU(a2+0x70)
 return RU(pe+0x10c)
}
FileRead, cmd, C:\AutoHotkey\cd.cmd
cmd := Trim(cmd)
LO := logic()
N := 0xA00
if (cmd = "snap") {
 f := FileOpen("C:\AutoHotkey\cd.snap","w")
 off := 0
 while (off < N) {
  f.WriteLine(Format("{:x}={}", off, RU(LO+off)))
  off += 4
 }
 f.Close()
 FileDelete, C:\AutoHotkey\cd.out
 FileAppend, % "snapped logic=0x" Format("{:08x}",LO) " " (N//4) " offsets", C:\AutoHotkey\cd.out
} else if (cmd = "diff") {
 FileRead, snapraw, C:\AutoHotkey\cd.snap
 prev := {}
 for i,ln in StrSplit(snapraw,"`n","`r") {
  pp := StrSplit(ln,"=")
  if (pp[1] != "")
   prev[pp[1]] := pp[2]
 }
 o := "changed offsets (logic=0x" Format("{:08x}",LO) "):`n"
 off := 0
 while (off < N) {
  key := Format("{:x}",off)
  cur := RU(LO+off)
  if (prev.HasKey(key) && prev[key]+0 != cur) {
   p := prev[key]+0
   pi := (p&0x80000000)?p-0x100000000:p
   ci := (cur&0x80000000)?cur-0x100000000:cur
   if (Abs(pi)<1000000 && Abs(ci)<1000000)
    o .= Format("  +0x{:x}: {} -> {}  (d{})`n", off, pi, ci, ci-pi)
   else
    o .= Format("  +0x{:x}: float/ptr changed`n", off)
  }
  off += 4
 }
 FileDelete, C:\AutoHotkey\cd.out
 FileAppend, %o%, C:\AutoHotkey\cd.out
}
ExitApp
