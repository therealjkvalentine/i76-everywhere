#!/usr/bin/env python3
"""Render the CURRENT controller layout as HTML by reading the live configs.

Sources of truth (parsed fresh on every run — never hand-maintain the output):
  1. the live input.map in the game prefix  -> native joystick1/mouse bindings
  2. the @pad annotation lines in i76-remap.ahk -> the AHK/XInput layer
     (kept adjacent to the code they describe; the one drift risk, by design)

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
                    native.setdefault("D-pad " + tok[3:], []).append(pa)
                elif tok == "Left/Right":
                    native.setdefault("Left stick X", []).append(pa)
                elif tok in ("Down/Up", "Up/Down"):
                    native.setdefault("Left stick Y", []).append(pa)
                else:
                    native.setdefault(tok, []).append(pa)
            elif dev.lower() == "mouse" and sign == "+":
                mouse.setdefault(tok, []).append(pa)
    return native, mouse

def parse_ahk(path):
    layer, extras = {}, []
    for m in re.finditer(r"^;\s*@pad\s+([^:]+):\s*(.+)$", open(path).read(), re.M):
        layer[m.group(1).strip()] = m.group(2).strip()
    for m in re.finditer(r"^(XButton\d)::(\S+)", open(path).read(), re.M):
        which = "Mouse 4 (back)" if m.group(1) == "XButton1" else "Mouse 5 (forward)"
        extras.append((which, "key " + m.group(2)))
    return layer, extras

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.cache/i76-pad-diagram.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    native, mouse = parse_input_map(IMAP)
    ahk, mextras = parse_ahk(AHK)

    def row(k, v, cls=""):
        return f'<tr class="{cls}"><td class="k">{html.escape(k)}</td><td>{html.escape(v)}</td></tr>'

    base_rows, shift_rows = [], []
    order = ["RStick", "RT", "LT", "A(tap)", "A(hold 400ms)", "B(tap)", "LB(tap)",
             "Select", "Dpad-Up", "Dpad-Down", "Dpad-Left", "Dpad-Right"]
    for k in order:
        if k in ahk: base_rows.append(row(k.replace("Dpad-", "D-pad "), ahk[k], "ahk"))
    for k, v in ahk.items():
        if k.startswith("LB+"): shift_rows.append(row(k, v, "ahk"))
    nat_rows = [row(k, " + ".join(sorted(set(v))), "nat") for k, v in sorted(native.items())]
    mouse_rows = [row("Mouse " + k, " + ".join(sorted(set(v))), "nat") for k, v in sorted(mouse.items())]
    mouse_rows += [row(k, v, "ahk") for k, v in mextras]

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>I'76 controller layout</title><style>
body{{font:14px/1.5 -apple-system,sans-serif;background:#1b1712;color:#e8ddc8;margin:2rem auto;max-width:60rem;padding:0 1rem}}
h1{{color:#e8a33d;font-size:1.4rem}} h2{{color:#e8a33d;font-size:1.05rem;margin-top:1.6rem}}
table{{border-collapse:collapse;width:100%}} td{{padding:.3rem .6rem;border-bottom:1px solid #3a3226}}
td.k{{width:11rem;font-weight:600;color:#f3e9d2;white-space:nowrap}}
tr.ahk td.k::after{{content:" ⚙";opacity:.5}} .cols{{display:grid;grid-template-columns:1fr 1fr;gap:0 2rem}}
@media(max-width:700px){{.cols{{grid-template-columns:1fr}}}}
.note{{color:#a89878;font-size:.85rem}} .shift{{background:#252017;border:1px solid #4a3d24;border-radius:8px;padding:.4rem .8rem}}
</style></head><body>
<h1>Interstate '76 — controller layout</h1>
<p class="note">Generated {stamp} from the live input.map + i76-remap.ahk annotations.
⚙ = via the AHK/XInput layer; others are native engine bindings. Rerun
<code>open-pad-diagram.command</code> any time — never edit this file.</p>
<div class="cols">
<div><h2>Pad — base</h2><table>{''.join(base_rows + nat_rows)}</table></div>
<div><div class="shift"><h2 style="margin-top:.2rem">Hold LB — weapons layer</h2>
<table>{''.join(shift_rows)}</table></div>
<h2>Mouse</h2><table>{''.join(mouse_rows)}</table></div>
</div></body></html>"""
    open(out, "w").write(page)
    print(out)

if __name__ == "__main__":
    main()
