#!/usr/bin/env python3
"""Render the CURRENT controller layout as an SVG diagram (generic Xbox-like
template, element names per Rewired's Controller Template guide) by reading
the live configs. Never hand-maintain the output.

Sources of truth, parsed fresh on every run:
  1. the live input.map in the game prefix  -> native joystick1/mouse bindings
  2. the @pad annotation lines in i76-remap.ahk -> the AHK/XInput layer

Usage: python3 tools/pad-diagram.py [output.html]
Writes ~/.cache/i76-pad-diagram.html by default and prints the path.
"""
import os, re, sys, html, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = os.path.expanduser(
    "~/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app/Contents/SharedSupport/prefix")
IMAP = PREFIX + "/drive_c/GOG Games/Interstate 76/input.map"
AHK = os.path.join(REPO, "i76-remap.ahk")

BTN_NAMES = {1: "A", 2: "B", 3: "X", 4: "Y", 5: "LB", 6: "RB", 7: "Select",
             8: "Start", 9: "L3", 10: "R3", 11: "Paddle 1", 12: "Paddle 2",
             13: "Paddle 3", 14: "Paddle 4"}
PRETTY = {"steer": "steer", "throttle": "throttle", "weapon_fire": "fire",
          "weapon_cycle": "cycle weapon", "e_brake": "handbrake",
          "special1": "special 1 (nitrous)", "special2": "special 2",
          "special3": "special 3", "NEXT_TARGET": "cycle targets",
          "frontal_target": "front target", "TARGET_NEAREST_ENEMY": "nearest enemy",
          "RESET_TARGET": "untarget", "pilot_glance_target": "look at target",
          "toggle_cmbt_view": "dash/combat view", "SHOW_MAP": "map",
          "SHOW_NOTEPAD": "notepad", "start_engine": "ignition",
          "toggle_lights": "headlights", "hardpoint1_fire": "hardpoint 1",
          "hardpoint2_fire": "hardpoint 2", "hardpoint3_fire": "hardpoint 3 (rear)",
          "hardpoint4_fire": "hardpoint 4 (dropper)", "hardpoint5_fire": "hardpoint 5"}

# inputs the AHK/XInput layer owns (shiftable with LB); keep in sync with XIPoll
AHK_OWNED = ["RT", "LT", "A", "B", "X", "Y", "Dpad-Up", "Dpad-Down",
             "Dpad-Left", "Dpad-Right", "Select", "Start", "RStick"]

def parse_input_map(path):
    native, mouse = {}, {}
    blocks = re.findall(r"^(\S+)\s*{\n(.*?)^}", open(path).read(), re.M | re.S)
    for action, body in blocks:
        pa = PRETTY.get(action, action.lower().replace("_", " "))
        for sign, dev, tok in re.findall(r"^\s*([+-])\s+(\S+)\s+(\S+)\s*$", body, re.M):
            if dev.lower().startswith("joystick"):
                m = re.match(r"Button(\d+)$", tok)
                if m:
                    native.setdefault(BTN_NAMES.get(int(m.group(1)), tok), []).append(pa)
                elif tok.startswith("Hat"):
                    native.setdefault("Dpad-" + tok[3:], []).append(pa)
                elif tok == "Left/Right":
                    native.setdefault("LStickX", []).append(pa)
                elif tok in ("Down/Up", "Up/Down"):
                    native.setdefault("LStickY", []).append(pa)
                else:
                    native.setdefault(tok, []).append(pa)
            elif dev.lower() == "mouse" and sign == "+":
                mouse.setdefault(tok, []).append(pa)
    return native, mouse

def parse_ahk(path):
    layer, extras = {}, []
    src = open(path).read()
    for m in re.finditer(r"^;\s*@pad\s+([^:]+):\s*(.+)$", src, re.M):
        layer[m.group(1).strip()] = m.group(2).strip()
    for m in re.finditer(r"^(XButton\d)::(\S+)", src, re.M):
        which = "Mouse 4 (back)" if m.group(1) == "XButton1" else "Mouse 5 (forward)"
        extras.append((which, "key " + m.group(2)))
    return layer, extras

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.cache/i76-pad-diagram.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    native, mouse = parse_input_map(IMAP)
    ahk, mextras = parse_ahk(AHK)

    def nat(key):
        return " + ".join(sorted(set(native[key]))) if key in native else None

    def base_of(pad_key, *ahk_keys):
        """binding text for an element: AHK @pad lines win, else native, else unbound"""
        parts = [ahk[k] for k in ahk_keys if k in ahk]
        if parts: return " · ".join(parts)
        n = nat(pad_key)
        return n if n else None

    UNBOUND = "— unbound —"
    # (template element name, binding, x,y of the element on the figure, side)
    elements = [
        ("Left Shoulder 2 (LT)",  base_of("LT", "LT"), 320, 62, "L"),
        ("Left Shoulder 1 (LB)",  base_of("LB", "LB(tap)"), 330, 92, "L"),
        ("Left Stick X",          nat("LStickX"), 322, 178, "L"),
        ("Left Stick Y",          nat("LStickY"), 322, 192, "L"),
        ("Left Stick Button (L3)", nat("L3"), 330, 206, "L"),
        ("D-Pad Up",              base_of("Dpad-Up", "Dpad-Up"), 395, 238, "L"),
        ("D-Pad Down",            base_of("Dpad-Down", "Dpad-Down"), 395, 282, "L"),
        ("D-Pad Left",            base_of("Dpad-Left", "Dpad-Left"), 373, 260, "L"),
        ("D-Pad Right",           base_of("Dpad-Right", "Dpad-Right"), 417, 260, "L"),
        ("Right Shoulder 2 (RT)", base_of("RT", "RT"), 580, 62, "R"),
        ("Right Shoulder 1 (RB)", base_of("RB", "RB"), 570, 92, "R"),
        ("Action Top Row 2 (Y)",  base_of("Y", "Y"), 565, 152, "R"),
        ("Action Top Row 1 (X)",  base_of("X", "X"), 537, 180, "R"),
        ("Action Bottom Row 2 (B)", base_of("B", "B(tap)"), 593, 180, "R"),
        ("Action Bottom Row 1 (A)", base_of("A", "A(tap)", "A(hold 400ms)"), 565, 208, "R"),
        ("Right Stick X/Y",       base_of("RStick", "RStick"), 505, 260, "R"),
        ("Right Stick Button (R3)", nat("R3"), 505, 275, "R"),
        ("Center 1 (Select)",     base_of("Select", "Select"), 425, 155, "C1"),
        ("Center 2 (Start)",      base_of("Start", "Start"), 475, 155, "C2"),
        ("Center 3 (Guide)",      None, 450, 190, "C3"),
    ]

    # --- SVG assembly
    left = [e for e in elements if e[4] == "L"]
    right = [e for e in elements if e[4] == "R"]
    center = [e for e in elements if e[4].startswith("C")]

    def label(x_text, y, name, binding, anchor):
        b = html.escape(binding) if binding else UNBOUND
        cls = "bound" if binding else "unbound"
        return (f'<text x="{x_text}" y="{y}" text-anchor="{anchor}" class="lname">{html.escape(name)}'
                f'<tspan x="{x_text}" dy="13" class="{cls}">{b}</tspan></text>')

    svg = []
    # body
    svg.append('<path d="M300,110 h300 a55,55 0 0 1 55,55 l18,110 a45,45 0 0 1 -80,32 l-30,-52 h-226 l-30,52 a45,45 0 0 1 -80,-32 l18,-110 a55,55 0 0 1 55,-55 z" class="body"/>')
    # shoulders
    svg.append('<rect x="295" y="86" width="80" height="12" rx="6" class="part"/><rect x="525" y="86" width="80" height="12" rx="6" class="part"/>')
    svg.append('<rect x="305" y="56" width="55" height="12" rx="6" class="part"/><rect x="540" y="56" width="55" height="12" rx="6" class="part"/>')
    # sticks
    svg.append('<circle cx="330" cy="192" r="26" class="part"/><circle cx="330" cy="192" r="14" class="stick"/>')
    svg.append('<circle cx="505" cy="260" r="26" class="part"/><circle cx="505" cy="260" r="14" class="stick"/>')
    # dpad
    svg.append('<path d="M387,238 h16 v14 h14 v16 h-14 v14 h-16 v-14 h-14 v-16 h14 z" class="part"/>')
    # face buttons
    for cx, cy, col, letter in [(565,152,"#4caf50","Y"),(537,180,"#42a5f5","X"),(593,180,"#ef5350","B"),(565,208,"#8bc34a","A")]:
        pass
    svg.append('<circle cx="565" cy="152" r="12" fill="#e6c229"/><text x="565" y="156" text-anchor="middle" class="bl">Y</text>')
    svg.append('<circle cx="537" cy="180" r="12" fill="#42a5f5"/><text x="537" y="184" text-anchor="middle" class="bl">X</text>')
    svg.append('<circle cx="593" cy="180" r="12" fill="#ef5350"/><text x="593" y="184" text-anchor="middle" class="bl">B</text>')
    svg.append('<circle cx="565" cy="208" r="12" fill="#66bb6a"/><text x="565" y="212" text-anchor="middle" class="bl">A</text>')
    # center buttons
    svg.append('<rect x="415" y="148" width="22" height="10" rx="5" class="part"/><rect x="465" y="148" width="22" height="10" rx="5" class="part"/><circle cx="450" cy="190" r="9" class="part"/>')

    # leader lines + labels
    y = 40
    for name, binding, ex, ey, _ in left:
        svg.append(f'<polyline points="215,{y+6} 245,{y+6} {ex},{ey}" class="lead"/>')
        svg.append(label(210, y, name, binding, "end"))
        y += 34
    y = 40
    for name, binding, ex, ey, _ in right:
        svg.append(f'<polyline points="685,{y+6} 655,{y+6} {ex},{ey}" class="lead"/>')
        svg.append(label(690, y, name, binding, "start"))
        y += 34
    cy0 = 395
    for i, (name, binding, ex, ey, _) in enumerate(center):
        cx = 320 + i * 130
        svg.append(f'<polyline points="{cx},{cy0-14} {ex},{ey}" class="lead"/>')
        svg.append(label(cx, cy0, name, binding, "middle"))

    # shift layer + free combos
    bound_shift = [(k, v) for k, v in ahk.items() if k.startswith("LB+")]
    used = {k[3:] for k, _ in bound_shift}
    free = [f"LB+{k}" for k in AHK_OWNED if k not in used and k != "LB"]
    shift_rows = "".join(f"<tr><td class='k'>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>"
                         for k, v in sorted(bound_shift))
    shift_rows += "".join(f"<tr><td class='k'>{html.escape(k)}</td><td class='unbound'>{UNBOUND}</td></tr>"
                          for k in free)
    mouse_rows = "".join(f"<tr><td class='k'>Mouse {html.escape(k)}</td><td>{html.escape(' + '.join(sorted(set(v))))}</td></tr>"
                         for k, v in sorted(mouse.items()))
    mouse_rows += "".join(f"<tr><td class='k'>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>" for k, v in mextras)
    paddle_rows = "".join(f"<tr><td class='k'>{html.escape(k)}</td><td>{html.escape(' + '.join(sorted(set(v))))}</td></tr>"
                          for k, v in sorted(native.items()) if k.startswith("Paddle"))

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>I'76 controller layout</title><style>
body{{font:14px/1.5 -apple-system,sans-serif;background:#1b1712;color:#e8ddc8;margin:1.5rem auto;max-width:62rem;padding:0 1rem}}
h1{{color:#e8a33d;font-size:1.3rem}} h2{{color:#e8a33d;font-size:1rem;margin-top:1.4rem}}
svg{{width:100%;height:auto;display:block}}
.body{{fill:#2a241b;stroke:#5a4d38;stroke-width:2}} .part{{fill:#3a3226;stroke:#5a4d38}}
.stick{{fill:#241f17;stroke:#6a5a40}} .lead{{fill:none;stroke:#6a5a40;stroke-width:1}}
.lname{{font:600 11px -apple-system,sans-serif;fill:#f3e9d2}}
.lname tspan{{font-weight:400;font-size:10.5px}} .bound{{fill:#c9b895}} .unbound{{fill:#6f6350;font-style:italic}}
.bl{{font:700 10px -apple-system,sans-serif;fill:#1b1712}}
table{{border-collapse:collapse;width:100%}} td{{padding:.25rem .6rem;border-bottom:1px solid #3a3226}}
td.k{{width:12rem;font-weight:600;color:#f3e9d2;white-space:nowrap}} td.unbound{{color:#6f6350;font-style:italic}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:0 2rem}} @media(max-width:700px){{.cols{{grid-template-columns:1fr}}}}
.note{{color:#a89878;font-size:.85rem}}
</style></head><body>
<h1>Interstate '76 — controller layout</h1>
<p class="note">Generated {stamp} from the live input.map + i76-remap.ahk annotations.
Element names per the generic gamepad template. Rerun <code>open-pad-diagram.command</code>
any time — never edit this file.</p>
<svg viewBox="0 0 900 420" xmlns="http://www.w3.org/2000/svg">{''.join(svg)}</svg>
<div class="cols">
<div><h2>Hold LB — shift layer</h2><table>{shift_rows}</table>
<h2>Back buttons / paddles (pads that have them)</h2><table>{paddle_rows}</table></div>
<div><h2>Mouse</h2><table>{mouse_rows}</table></div>
</div></body></html>"""
    open(out, "w").write(page)
    print(out)

if __name__ == "__main__":
    main()
