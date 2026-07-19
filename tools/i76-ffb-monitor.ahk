; Interstate '76 FFB MONITOR (AutoHotkey v1.1) — live overlay of the force stream.
; Reads the ffb-shim's telemetry files (../ffb-shim/) and draws the game's own
; force-feedback stream + the rumble it produces, so you can watch it while
; driving and tune the mapping:
;   C:\AutoHotkey\ffb-state.txt   one key=value status line, rewritten each tick
;   C:\AutoHotkey\ffb-events.txt  appended impact log (dir + damage)
;
; This is the "display it to me" tool. It needs NO motion rig and NO winsock —
; just the shim installed and the game in a mission. (The shim ALSO sends the
; same data over UDP for SimTools/SimHub; tools/ffb-udp-listen.py + docs/
; MOTION-SIM.md cover the rig path.) If every value reads 0/blank, the shim
; isn't receiving — that's the first thing this tool tells you.
;
; Launch: wine AutoHotkeyU32.exe i76-ffb-monitor.ahk
; STATUS: built 2026-07-19 from the shim's output format; NOT yet field-run.

#NoEnv
#Persistent
#SingleInstance Force
SetBatchLines, -1
global STATEF := "C:\AutoHotkey\ffb-state.txt", EVENTF := "C:\AutoHotkey\ffb-events.txt"
global gLastTick := -1, gStale := 0

Gui, +AlwaysOnTop +ToolWindow -Caption
Gui, Color, 0a0a0a
Gui, Font, s10 cCFE8CF, Consolas
Gui, Add, Text, x10 y8 w420 vTX, i76 FFB monitor — waiting for the shim...
Gui, Show, x8 y8 NoActivate, i76ffb
SetTimer, Tick, 100
return

; pull an integer token "key=NNN" out of the status line
Val(s, key) {
    if (RegExMatch(s, key "=(-?\d+)", m))
        return m1 + 0
    return 0
}
Bar(v01, w := 22) {
    if (v01 < 0)
        v01 := 0
    if (v01 > 1)
        v01 := 1
    f := Round(v01 * w)
    out := ""
    Loop, %f%
        out .= Chr(0x2588)
    Loop, % w - f
        out .= Chr(0x2500)
    return out
}
Surface(id) {   ; id order is a GUESS (docs/FFB-DEEP-DIVE.md) — trailing ? flags that
    static names := {0:"stopped",1:"dirt-x?",2:"parking?",3:"rocky?",4:"wash?",5:"dirt-rd?",6:"paved?",7:"veg?",8:"packed?",9:"in-air?"}
    return names.HasKey(id) ? names[id] : "id" id
}

Tick:
    FileRead, s, %STATEF%
    if (ErrorLevel || s = "") {
        GuiControl,, TX, % "FFB monitor: no telemetry file yet.`n(install the shim: ../ffb-shim/install.sh, then drive)"
        return
    }
    if (InStr(s, "init ok") || InStr(s, "exit")) {
        GuiControl,, TX, % "shim loaded (" Trim(s, " `r`n") ") — waiting for the sim tick"
        return
    }
    tick := Val(s, "tick"), on := Val(s, "on")
    ; stall detection: same tick across polls = game paused or stream dead
    if (tick = gLastTick)
        gStale += 1
    else
        gStale := 0, gLastTick := tick

    spd := Val(s, "spd10") / 10.0
    low := Val(s, "low100"), high := Val(s, "high100")
    fx := Val(s, "fx1000") / 1000.0, fy := Val(s, "fy1000") / 1000.0
    surf := Surface(Val(s, "surf"))
    flags := ""
    if (Val(s, "air"))
        flags .= "AIR "
    if (Val(s, "skid"))
        flags .= "SKID "
    if (Val(s, "slide"))
        flags .= "SLIDE "
    if (Val(s, "oil"))
        flags .= "OIL "
    if (flags = "")
        flags := "-"
    RegExMatch(s, "tires=([\d,]+)", tm)
    RegExMatch(s, "fire=(\d+)", fm)

    ; last impact event (tail of the append log)
    ev := ""
    FileRead, evs, %EVENTF%
    if (!ErrorLevel && evs != "") {
        a := StrSplit(Trim(evs, " `r`n"), "`n", "`r")
        ev := a[a.MaxIndex()]
    }

    t := "I'76 FFB MONITOR   tick=" tick "   forces=" (on ? "ON" : "off")
    t .= (gStale > 8 ? "  [STALLED]" : "") "`n`n"
    t .= "L impact/engine [" Bar(low/100) "] " low "`n"
    t .= "R weapons       [" Bar(high/100) "] " high "`n`n"
    t .= "speed  " Format("{:5.1f}", spd) " mph [" Bar(spd/165 > 1 ? 1 : spd/165, 16) "]`n"
    t .= "surge fx " Format("{:+.2f}", fx) "   sway fy " Format("{:+.2f}", fy) "   steer " Val(s,"steer") "`n"
    t .= "engine " (Val(s,"run") ? "run" : "off") " pitch " Val(s,"pitch") "   surface " surf "`n"
    t .= "flags  " flags "`n"
    t .= "tires  " tm1 "   firing " fm1 " gain " Val(s,"gain") "`n"
    t .= "impact " (ev != "" ? ev : "-")
    GuiControl,, TX, %t%
return

GuiClose:
ExitApp
