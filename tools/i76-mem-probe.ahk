#NoEnv
#SingleInstance Force
Process, Exist, i76.exe
pid := ErrorLevel
if (!pid) { Process, Exist, nitro.exe
    pid := ErrorLevel }
h := DllCall("OpenProcess", "UInt", 0x38, "Int", 0, "UInt", pid, "Ptr")
RF(h,a){
 VarSetCapacity(b,4,0)
 DllCall("ReadProcessMemory","Ptr",h,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0)
 return NumGet(b,0,"Float")
}
RI(h,a){
 VarSetCapacity(b,4,0)
 DllCall("ReadProcessMemory","Ptr",h,"Ptr",a,"Ptr",&b,"UPtr",4,"Ptr",0)
 return NumGet(b,0,"Int")
}
out := "pid=" pid " hProc=" h "`n"
out .= "view_mode(0x4c2728)=" RI(h,0x4c2728) "`n"
out .= "cam_yaw(0x4c2964)=" RF(h,0x4c2964) "`n"
out .= "cam_pitch(0x4c296c)=" RF(h,0x4c296c) "`n"
out .= "cam_roll(0x4c2970)=" RF(h,0x4c2970) "`n"
out .= "in_throttle(0x5367cc)=" RI(h,0x5367cc) "`n"
out .= "in_steer(0x5367d4)=" RI(h,0x5367d4) "`n"
out .= "ffb_flag(0x52bbd0)=" RI(h,0x52bbd0) "`n"
out .= "ffb_params0(0x4f2328)=" RI(h,0x4f2328) "`n"
FileDelete, C:\AutoHotkey\probe.out
FileAppend, %out%, C:\AutoHotkey\probe.out
ExitApp
