#!/usr/bin/env python3
# Build "Option 2 (Racing)" - NFS/GTA-convention Steam Deck config for Interstate 76.
import re
SRC="/private/tmp/claude-501/-Users-jamesvalentine-Documents-Repositories-mac-gaming-ports/934651c4-e77e-4320-9ab3-d662e6a50483/scratchpad/ref_neptune_wasd.vdf"
OUT="/private/tmp/claude-501/-Users-jamesvalentine-Documents-Repositories-mac-gaming-ports/934651c4-e77e-4320-9ab3-d662e6a50483/scratchpad/controller_neptune_i76_opt2.vdf"

tok=re.compile(r'"((?:[^"\\]|\\.)*)"|(\{)|(\})')
def parse(s):
    def rd(i):
        out=[]
        while i<len(s):
            m=tok.search(s,i)
            if not m: break
            i=m.end()
            if m.group(3)=='}': return out,i
            key=m.group(1)
            m2=tok.search(s,i); i=m2.end()
            if m2.group(2)=='{':
                val,i=rd(i); out.append([key,val])
            else:
                out.append([key,m2.group(1)])
        return out,i
    return rd(0)[0]
def ser(node,d=0):
    t="\t"*d; out=[]
    for k,v in node:
        if isinstance(v,list): out.append(f'{t}"{k}"\n{t}{{\n{ser(v,d+1)}{t}}}\n')
        else: out.append(f'{t}"{k}"\t\t"{v}"\n')
    return "".join(out)
def find(n,k):
    for kv in n:
        if kv[0]==k: return kv[1]
def findall(n,k): return [kv[1] for kv in n if kv[0]==k]

def kbs(*bindings):
    return [["activators",[["Full_Press",[["bindings",[["binding",b] for b in bindings]]]]]]]

txt=open(SRC,encoding="utf-8-sig").read()
root=parse(txt)
cm=find(root,"controller_mappings")
groups={find(g,"id"):g for g in findall(cm,"group")}
def set_mode(gid,mode):
    for kv in groups[gid]:
        if kv[0]=="mode": kv[1]=mode; return
def replace_inputs(gid,pairs):
    for kv in groups[gid]:
        if kv[0]=="inputs":
            kv[1]=[[inp,kbs(*bs)] for inp,bs in pairs]; return
def set_input(gid,inp,*bindings):
    inputs=find(groups[gid],"inputs")
    for kv in inputs:
        if kv[0]==inp: kv[1]=kbs(*bindings); return
    inputs.append([inp,kbs(*bindings)])

# LEFT STICK analog (steer; stick-Y feeds throttle axis too - triggers override in practice)
set_mode("3","joystick_move")
replace_inputs("3",[("click",["key_press G, Horn"])])
if not find(groups["3"],"settings"): groups["3"].append(["settings",[["deadzone_inner_radius","7199"]]])
# RIGHT STICK -> glance arrows; click = binoculars
set_mode("9","dpad")
replace_inputs("9",[("dpad_north",["key_press UP_ARROW, Glance up"]),
                    ("dpad_south",["key_press DOWN_ARROW, Glance down"]),
                    ("dpad_east",["key_press RIGHT_ARROW, Glance right"]),
                    ("dpad_west",["key_press LEFT_ARROW, Glance left"]),
                    ("click",["key_press B, Binoculars"])])
# ABXY: A=confirm+skip, B=reverse, X=fire-all, Y=view
set_input("0","button_a","key_press RETURN, Confirm / select","mouse_button LEFT, Click / skip")
set_input("0","button_b","key_press X, Reverse")
set_input("0","button_x","key_press F, Fire-all / link")
set_input("0","button_y","key_press V, Change view")
# TRIGGERS: R2 accelerate, L2 brake
replace_inputs("4",[("edge",["key_press S, Brake"])])
replace_inputs("5",[("edge",["key_press W, Accelerate"])])
# DPAD: engine/lights/target-nearest/next-target
replace_inputs("7",[("dpad_north",["key_press I, Start engine"]),
                    ("dpad_south",["key_press H, Headlights"]),
                    ("dpad_west",["key_press T, Target nearest"]),
                    ("dpad_east",["key_press Y, Next target"])])
# LEFT TRACKPAD radial: map/notepad/radar-range/radar-cam, click=untarget
replace_inputs("1",[("dpad_north",["key_press M, Map"]),
                    ("dpad_south",["key_press N, Notepad"]),
                    ("dpad_west",["key_press R, Radar range"]),
                    ("dpad_east",["key_press K, Radar camera"]),
                    ("click",["key_press U, Untarget"])])
# RIGHT TRACKPAD stays mouse; click = left-click
for kv in find(groups["2"],"inputs"):
    if kv[0]=="click": kv[1]=kbs("mouse_button LEFT, Click")
# SWITCHES: bumpers fire/cycle; Start=pause, Select=map; rear: targeting+handbrake+zoom
set_input("6","left_bumper","key_press TAB, Change weapon")
set_input("6","right_bumper","key_press SPACE, Fire weapon")
set_input("6","button_escape","key_press ESCAPE, Pause")   # Start
set_input("6","button_menu","key_press M, Map")            # Select
set_input("6","button_back_left","key_press Q, Front target")      # L4
set_input("6","button_back_right","key_press C, Handbrake")        # R4
set_input("6","button_back_left_upper","key_press PAGE_UP, Zoom out")   # L5
set_input("6","button_back_right_upper","key_press PAGE_DOWN, Zoom in") # R5
for kv in cm:
    if kv[0]=="title": kv[1]="Interstate 76 - Option 2 v1 (Racing: triggers drive)"
    if kv[0]=="game": kv[1]="Interstate 76"
out='"controller_mappings"\n{\n'+ser(cm,1)+'}\n'
open(OUT,"w",encoding="utf-8").write('﻿'+out)
print("braces:",out.count("{"),out.count("}"))
b=re.findall(r'"binding"\s+"([^"]+)"',out)
print(f"{len(b)} bindings"); [print("  ",x) for x in b]
