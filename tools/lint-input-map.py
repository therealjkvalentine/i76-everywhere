#!/usr/bin/env python3
"""Lint an Interstate '76 input.map against the engine's own string table.

Usage:  python3 tools/lint-input-map.py "<game dir>"        (dir with input.map + i76.exe/nitro.exe)
        python3 tools/lint-input-map.py <input.map> <exe>

Why this exists (2026-07-18): the engine silently ignores tokens it doesn't
know, and several of our regressions came from exactly that class of mistake —
`Up/Down` bound where the real Y-axis token is `Down/Up` (throttle silently
dead), and days of edits to KEYBOARD.MAP, which the engine never reads at all.
Every action name, key name, and axis token in input.map should exist verbatim
in the exe's string table; this proves it before a single launch is wasted.

Checks:
  1. every block's ACTION name exists in the exe strings (case-insensitive)
  2. every keyboard/mouse/joystick TOKEN exists in the exe strings
     (buttons: numeric suffix allowed on a known base, e.g. Button3)
  3. device tokens are known (keyboard / mouse / joystick / joystickN)
  4. chord warning: >1 `+` line in one block (all must be held together)
  5. analog trap: two analog sources in one block pin the axis dead-center
  6. dead-file tripwire: KEYBOARD.MAP/JOYSTICK.MAP newer than input.map means
     someone edited a file the engine does not read

Exit code: 0 clean, 1 findings.
"""
import os, re, string, sys

ANALOG = {"left/right", "down/up", "up/down", "throttle", "rudder"}
DEVICES = re.compile(r"^(keyboard|mouse|joystick[0-9]*)$", re.I)

def exe_strings(path, minlen=3):
    data = open(path, "rb").read()
    ok = set(string.printable) - set("\t\n\r\x0b\x0c")
    out, run = set(), []
    for b in data:
        c = chr(b)
        if c in ok:
            run.append(c)
        else:
            if len(run) >= minlen: out.add("".join(run).lower())
            run = []
    if len(run) >= minlen: out.add("".join(run).lower())
    return out

def parse_blocks(path):
    """Yield (lineno, action, [(sign, device, token), ...])."""
    blocks, cur, action, lineno0 = [], None, None, 0
    for n, raw in enumerate(open(path, errors="replace"), 1):
        line = raw.split("#", 1)[0].strip()
        if not line: continue
        m = re.match(r"^(\S+)\s*{", line)
        if m:
            action, cur, lineno0 = m.group(1), [], n
            continue
        if line.startswith("}"):
            if action is not None: blocks.append((lineno0, action, cur))
            action, cur = None, None
            continue
        m = re.match(r"^([+-])\s+(\S+)\s+(\S+)$", line)
        if m and cur is not None:
            cur.append((m.group(1), m.group(2), m.group(3)))
    return blocks

def main():
    if len(sys.argv) == 2 and os.path.isdir(sys.argv[1]):
        gd = sys.argv[1]
        imap = os.path.join(gd, "input.map")
        exe = next((os.path.join(gd, e) for e in ("i76.exe", "nitro.exe", "I76.EXE", "NITRO.EXE")
                    if os.path.exists(os.path.join(gd, e))), None)
    elif len(sys.argv) == 3:
        imap, exe = sys.argv[1], sys.argv[2]
        gd = os.path.dirname(os.path.abspath(imap))
    else:
        sys.exit(__doc__)
    if not exe or not os.path.exists(exe): sys.exit(f"no exe found for {imap}")

    known = exe_strings(exe)
    findings = []

    def tok_known(t):
        tl = t.lower()
        if len(tl) <= 2 and tl.isalnum(): return True  # single-letter/digit keys (below strings minlen)
        if re.match(r"^button[0-9]+$", tl): return True  # field-verified working despite absent base string
        if tl in known: return True
        m = re.match(r"^([a-z/]+?)([0-9]+)$", tl)      # NumpadN-style -> base
        return bool(m and m.group(1) in known)

    seen_actions = {}
    joy_devices = {}          # joystickN -> first line it appears on
    analog_joy_devices = set()

    for lineno, action, lines in parse_blocks(imap):
        seen_actions[action.lower()] = lineno
        if action.lower() not in known:
            findings.append(f"line {lineno}: action '{action}' not in exe strings — the engine will ignore this block")
        plus = [l for l in lines if l[0] == "+"]
        # Analog sinks are '-' lines (the sign is axis POLARITY, not a chord), so
        # this must look at every line - checking only '+' silently skipped the
        # real steer/throttle blocks and let a documented trap through (2026-08-02).
        analog = [l for l in lines if l[2].lower() in ANALOG]
        for _s, d, _t in analog:
            if re.match(r"^joystick[0-9]+$", d, re.I):
                analog_joy_devices.add(d.lower())
        for _s, d, _t in lines:
            if re.match(r"^joystick[0-9]+$", d, re.I):
                joy_devices.setdefault(d.lower(), lineno)
        nonmod = [l for l in plus if l[2].lower() not in ("shift", "control")]
        if len(plus) > 1 and len(nonmod) > 1 and not analog:  # modifier chords (Shift-click) are intended
            findings.append(f"line {lineno}: '{action}' has {len(plus)} '+' lines = CHORD (all keys at once). Alternatives need separate blocks")
        if len(analog) > 1:
            srcs = ", ".join(f"{d} {t}" for _s, d, t in analog)
            findings.append(f"line {lineno}: '{action}' has two analog sources ({srcs}) — axis pins dead-center (VERIFIED-FIXES; docs/WHEEL-T300.md: list joystick1 ONLY on steer/throttle)")
        for sign, dev, tok in lines:
            if re.fullmatch(r"joystick", dev, re.I):
                findings.append(f"line {lineno}: '{action}': DEAD device token '{dev}' — bare Joystick parses but binds NOTHING (field-settled 2026-07-18, twice). Use joystick1")
            elif not DEVICES.match(dev):
                findings.append(f"line {lineno}: '{action}': unknown device '{dev}'")
            if not tok_known(tok):
                hint = " (Y axis token is 'Down/Up')" if tok.lower() == "up/down" else ""
                findings.append(f"line {lineno}: '{action}': token '{tok}' not in exe strings — silently dead{hint}")

    # --- THE ANALOG SINKS MUST EXIST -----------------------------------------
    # Field case 2026-08-02: a wheel that steered and braked fine stopped doing
    # anything at all. Cause was not drivers, calibration or the registry - the
    # in-game Control Configuration menu had REWRITTEN input.map and dropped the
    # steer and throttle blocks entirely, leaving no analog sinks. With no sink
    # there is no wheel and no pedals, however healthy the device is.
    for need in ("steer", "throttle"):
        if need not in seen_actions:
            findings.append(
                f"NO '{need}' BLOCK — that axis cannot work at all. If both are missing this is the "
                f"signature of input.map having been rewritten by the IN-GAME Control Configuration "
                f"menu, which corrupts it (docs/VERIFIED-FIXES.md). Restore a known-good input.map; "
                f"never rebind in-game.")

    # The menu-corrupted file also re-pointed every button at whatever joystick
    # slot it felt like (a 3Dconnexion emulator on joystick8, with ZERO joystick1
    # references). If the buttons name a different stick than the analog sinks,
    # half the wheel will be inert.
    if analog_joy_devices:
        stray = {d: ln for d, ln in joy_devices.items() if d not in analog_joy_devices}
        if stray:
            a = ", ".join(sorted(analog_joy_devices))
            s = ", ".join(f"{d} (line {ln})" for d, ln in sorted(stray.items()))
            findings.append(
                f"MIXED JOYSTICK DEVICES: analog sinks use {a} but other bindings use {s}. "
                f"They must be the same physical stick - check which slot the wheel actually is "
                f"(joyGetDevCaps / tools/i76-joyprobe.py) before trusting any of these numbers.")
    elif joy_devices:
        findings.append(
            f"joystick bindings exist ({', '.join(sorted(joy_devices))}) but NO analog sink uses a "
            f"joystick — steering/pedals are unbound. Same corruption signature as above.")

    imap_mtime = os.path.getmtime(imap)
    for dead in ("KEYBOARD.MAP", "keyboard.map", "JOYSTICK.MAP", "joystick.map"):
        p = os.path.join(gd, dead)
        if os.path.exists(p) and os.path.getmtime(p) > imap_mtime:
            findings.append(f"{dead} is NEWER than input.map — the engine does not read it; did someone edit the wrong file?")
            break

    if findings:
        print(f"{len(findings)} finding(s) in {imap}:")
        for f in findings: print("  ⚠ " + f)
        sys.exit(1)
    print(f"OK: {imap} — all actions/tokens present in {os.path.basename(exe)}, no traps")

if __name__ == "__main__":
    main()
