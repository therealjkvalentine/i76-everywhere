#!/usr/bin/env python3
# Option 1 v4 - rebuilt from Valve's template PRESERVING its structure/settings
# (v3 dropped per-activator settings on the trackpad -> the "double-tap" bug).
import re
SRC="/private/tmp/claude-501/-Users-jamesvalentine-Documents-Repositories-mac-gaming-ports/934651c4-e77e-4320-9ab3-d662e6a50483/scratchpad/ref_neptune_wasd.vdf"
OUT="/private/tmp/claude-501/-Users-jamesvalentine-Documents-Repositories-mac-gaming-ports/934651c4-e77e-4320-9ab3-d662e6a50483/scratchpad/controller_neptune_i76_v4.vdf"

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
            else: out.append([key,m2.group(1)])
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
def get_input(g,name): return find(find(g,"inputs"),name)

# Valve-style input block: Full_Press + per-activator settings preserved
def vinput(binding, extra_activators=None, repeat=False):
    st=[["repeat_rate","99"],["haptic_intensity","1"]] if repeat else [["haptic_intensity","1"]]
    acts=[["Full_Press",[["bindings",[["binding",b] for b in (binding if isinstance(binding,list) else [binding])]],
                         ["settings",st]]]]
    if extra_activators: acts += extra_activators
    return [["activators",acts]]

txt=open(SRC,encoding="utf-8-sig").read()
root=parse(txt); cm=find(root,"controller_mappings")
groups={find(g,"id"):g for g in findall(cm,"group")}

def swap_binding(g,inp,new,label=""):
    node=get_input(groups[g],inp)
    for kv in find(find(node,"activators"),"Full_Press"):
        if kv[0]=="bindings": kv[1]=[["binding",f"{new}, {label}" if label else new]]

# g0 ABXY
node=get_input(groups["0"],"button_a")
for kv in find(find(node,"activators"),"Full_Press"):
    if kv[0]=="bindings": kv[1]=[["binding","key_press RETURN, Confirm / select"],["binding","mouse_button LEFT, Click / skip"]]
swap_binding("0","button_b","key_press TAB","Cycle weapon")
swap_binding("0","button_x","key_press X","Reverse")
# Y: F3 ext view single, F1 cockpit double
node=get_input(groups["0"],"button_y")
for kv in node:
    if kv[0]=="activators":
        kv[1]=[["Full_Press",[["bindings",[["binding","key_press F3, External view"]]],["settings",[["haptic_intensity","1"]]]]],
               ["Double_Press",[["bindings",[["binding","key_press F1, Cockpit view"]]],["settings",[["haptic_intensity","2"]]]]]]
# g1 left trackpad: keys only, Valve structure intact, NO click input
swap_binding("1","dpad_north","key_press M","Map")
swap_binding("1","dpad_south","key_press N","Notepad")
swap_binding("1","dpad_east","key_press K","Radar camera")
swap_binding("1","dpad_west","key_press R","Radar range")
# g2 right trackpad: unchanged (mouse + Soft_Press LMB)
# g3 left stick -> analog joystick; click = horn
for kv in groups["3"]:
    if kv[0]=="mode": kv[1]="joystick_move"
    if kv[0]=="inputs": kv[1]=[["click",vinput("key_press G, Horn")]]
    if kv[0]=="settings": kv[1]=[["deadzone_inner_radius","7199"]]
# g4 L2 -> hardpoint 2 (secondary), keep repeat (hold = keep firing)
swap_binding("4","edge","key_press 2","Fire secondary (hardpoint 2)")
# g5 R2 -> fire primary, keep repeat
swap_binding("5","edge","key_press SPACE","Fire weapon")
# g6 switches
swap_binding("6","button_escape","key_press ESCAPE","Pause")     # Start
swap_binding("6","button_menu","key_press M","Map")              # Select
swap_binding("6","left_bumper","key_press Y","Next target")      # LB
swap_binding("6","right_bumper","key_press C","Handbrake")       # RB
for name,b,l in [("button_back_left","key_press I","Start engine"),
                 ("button_back_right","key_press T","Target nearest"),
                 ("button_back_left_upper","key_press H","Headlights"),
                 ("button_back_right_upper","key_press B","Binoculars")]:
    node=get_input(groups["6"],name)
    for kv in find(find(node,"activators"),"Full_Press"):
        if kv[0]=="bindings": kv[1]=[["binding",f"{b}, {l}"]]
# g7 dpad: Valve's is ALREADY arrows with proper settings - keep verbatim!
# g9 right stick -> dpad arrows (glance) + click = look-at-target
for kv in groups["9"]:
    if kv[0]=="mode": kv[1]="dpad"
    if kv[0]=="inputs":
        kv[1]=[["dpad_north",vinput("key_press UP_ARROW, Glance up")],
               ["dpad_south",vinput("key_press DOWN_ARROW, Glance down")],
               ["dpad_east",vinput("key_press RIGHT_ARROW, Glance right")],
               ["dpad_west",vinput("key_press LEFT_ARROW, Glance left")],
               ["click",vinput("key_press E, Look at target")]]
    if kv[0]=="settings": kv[1]=[["requires_click","0"]]

for kv in cm:
    if kv[0]=="title": kv[1]="Interstate 76 - Option 1 v4 (Sim-Combat, analog)"
    if kv[0]=="game": kv[1]="Interstate 76"
out='"controller_mappings"\n{\n'+ser(cm,1)+'}\n'
open(OUT,"w",encoding="utf-8").write('﻿'+out)
print("braces:",out.count("{"),out.count("}"))
for x in re.findall(r'"binding"\s+"([^"]+)"',out): print("  ",x)
