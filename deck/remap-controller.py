#!/usr/bin/env python3
# Rewrite the neptune WASD template into a full Interstate '76 layout.
# Handles: replacing existing bindings (key_press / mouse_wheel / mouse_button)
# AND inserting bindings into empty back-button blocks. Structure preserved.
import re

SRC = "/private/tmp/claude-501/-Users-jamesvalentine-Documents-Repositories-mac-gaming-ports/b50977da-e002-449c-b723-ede354c6d910/scratchpad/ref_neptune_wasd.vdf"
OUT = "/private/tmp/claude-501/-Users-jamesvalentine-Documents-Repositories-mac-gaming-ports/b50977da-e002-449c-b723-ede354c6d910/scratchpad/i76-deck-bundle/config/controller_neptune_i76.vdf"

# (group_id, input_name) -> (key_token, label)
MAP = {
 ("0","button_a"): ("C","Handbrake"),
 ("0","button_b"): ("X","Reverse"),
 ("0","button_x"): ("F","Link weapons"),
 ("0","button_y"): ("V","Change view"),
 ("3","dpad_north"): ("W","Accelerate"),
 ("3","dpad_south"): ("S","Brake"),
 ("3","dpad_east"):  ("D","Steer right"),
 ("3","dpad_west"):  ("A","Steer left"),
 ("4","edge"): ("S","Brake"),
 ("5","edge"): ("W","Accelerate"),
 ("7","dpad_north"): ("UP_ARROW","Glance up"),
 ("7","dpad_south"): ("DOWN_ARROW","Glance down"),
 ("7","dpad_east"):  ("RIGHT_ARROW","Glance right"),
 ("7","dpad_west"):  ("LEFT_ARROW","Glance left"),
 ("1","dpad_north"): ("M","Map"),
 ("1","dpad_south"): ("N","Notepad"),
 ("1","dpad_east"):  ("K","Radar camera"),
 ("1","dpad_west"):  ("H","Lights"),
 ("1","click"):      ("I","Start engine"),
 ("6","button_escape"): ("ESCAPE","Pause / back"),
 ("6","button_menu"):   ("RETURN","Confirm / select"),
 ("6","left_bumper"):   ("TAB","Cycle weapon"),
 ("6","right_bumper"):  ("SPACE","Fire weapon"),
 ("6","button_back_left"):        ("Q","Target front"),
 ("6","button_back_right"):       ("T","Target nearest"),
 ("6","button_back_left_upper"):  ("Y","Target next"),
 ("6","button_back_right_upper"): ("R","Radar range"),
}
INPUT_NAMES = {k[1] for k in MAP} | {"edge","click"}

lines = open(SRC, encoding="utf-8-sig").read().split("\n")
out = []
cur_group=None; pending_gid=False; cur_input=None
in_bindings=False; bindings_indent=""; target=None; inserted=False

for ln in lines:
    s = ln.strip()
    if s == '"group"': pending_gid=True
    m = re.match(r'"id"\s+"(\d+)"', s)
    if m and pending_gid: cur_group=m.group(1); pending_gid=False
    mi = re.match(r'"([a-z_]+)"$', s)
    if mi and mi.group(1) in INPUT_NAMES: cur_input=mi.group(1)

    # entering a bindings block
    if s == '"bindings"':
        in_bindings=True; target=MAP.get((cur_group,cur_input)); inserted=False
        bindings_indent = ln[:len(ln)-len(ln.lstrip())]
        out.append(ln); continue

    if in_bindings:
        # replace an existing binding line for a target input
        if s.startswith('"binding"') and target:
            key,label=target
            out.append(f'{bindings_indent}\t"binding"\t\t"key_press {key}, {label}"')
            inserted=True; continue
        # close of an (empty) bindings block -> insert if target & nothing inserted
        if s == '}':
            if target and not inserted:
                key,label=target
                out.append(f'{bindings_indent}\t"binding"\t\t"key_press {key}, {label}"')
            in_bindings=False; target=None
            out.append(ln); continue
    out.append(ln)

txt="\n".join(out)
txt=re.sub(r'"game"\s+"[^"]*"', '"game" "Interstate 76"', txt, count=1)
txt=re.sub(r'"title"\s+"Keyboard \(WASD\) and Mouse"', '"title" "Interstate 76 (full driving+combat)"', txt)
open(OUT,"w",encoding="utf-8").write(txt)

bound=re.findall(r'key_press ([A-Z0-9_]+), ([^"]+)"', txt)
print(f"wrote {OUT}  ({len(bound)} key bindings)")
for k,l in bound: print(f"  {k:12} {l}")
print("braces:", txt.count("{"), txt.count("}"), "balanced" if txt.count("{")==txt.count("}") else "MISMATCH")
