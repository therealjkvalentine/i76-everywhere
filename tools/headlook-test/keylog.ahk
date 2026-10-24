; Key logger window for the head-look headless test (tools\headlook-test\run-headless.ps1).
; A plain GUI window that the test makes the foreground "game"; it polls the OS's logical key state
; (GetAsyncKeyState - sees injected keys from every process, needs no hook) for the arrows, Enter, 1 and F every
; 2 ms and appends every transition to the log file given as the first argument:
;   <A_TickCount> <key> down|up
#NoEnv
#SingleInstance Off
#Persistent
SetBatchLines, -1
global LOG := A_Args[1]
global VKS := {Left: 0x25, Up: 0x26, Right: 0x27, Down: 0x28, Enter: 0x0D, One: 0x31, F: 0x46}
global prev := {}
Gui, +AlwaysOnTop
Gui, Font, s14
Gui, Add, Text, w420 h60, i76 head-look test - key logger window
Gui, Show, w460 h90, i76keylog
SetTimer, Poll, 2
return
Poll:
    for k, vk in VKS {
        d := (DllCall("GetAsyncKeyState", "Int", vk, "Short") & 0x8000) ? 1 : 0
        if (d != (prev.HasKey(k) ? prev[k] : 0)) {
            FileAppend, % A_TickCount . " " . k . " " . (d ? "down" : "up") . "`n", %LOG%
            prev[k] := d
        }
    }
return
GuiClose:
ExitApp
