#!/usr/bin/env python3
"""
i76-joyprobe - read a wheel/pad through winmm, the API Interstate '76 itself uses.

I76 is winmm-joystick only (joyGetNumDevs / joyGetPosEx, no DirectInput input
path). So the ONLY measurement that settles an input.map question is one taken
through winmm - not DirectInput, not XInput, not the vendor's control panel.
This is that instrument. Windows only (it calls winmm directly).

    python i76-joyprobe.py                 enumerate devices + capabilities
    python i76-joyprobe.py --capture       wait for input, then record 40s
    python i76-joyprobe.py --capture -d 1  same, on winmm device index 1

WHY --capture WAITS instead of recording immediately: a fixed timer races the
human. It also races the DEVICE - joyGetPosEx returns 32767 defaults for a
second or two before a wheel settles, and a naive "detect movement" trigger
fires on that settling rather than on the user. So: warm up, THEN take the
baseline, THEN require 5 consecutive samples past threshold. Both mistakes were
made for real on 2026-08-01 before this shape was arrived at.

Axis -> input.map token mapping (see docs/input.map.reference):
    X = Left/Right      Y = Down/Up      Z = Throttle
    R/U = 5thAxis/6thAxis  (largely unusable natively - winmm's 6-axis ceiling)

The prefix on an analog block is axis POLARITY, and stock is `-`. `Up/Down` is
NOT a real token; the Y axis is named `Down/Up`. Both of those cost a field test
once already.
"""
import ctypes, ctypes.wintypes as w, time, json, sys

winmm = ctypes.WinDLL('winmm')
NAMES = ["X", "Y", "Z", "R", "U", "V"]
JOY_RETURNALL = 0x000000FF
CAPS = {0x0001: "HASZ", 0x0002: "HASR", 0x0004: "HASU", 0x0008: "HASV",
        0x0010: "HASPOV", 0x0020: "POV4DIR", 0x0040: "POVCTS"}


class JOYCAPSW(ctypes.Structure):
    _fields_ = [("wMid", w.WORD), ("wPid", w.WORD), ("szPname", w.WCHAR * 32),
        ("wXmin", w.UINT), ("wXmax", w.UINT), ("wYmin", w.UINT), ("wYmax", w.UINT),
        ("wZmin", w.UINT), ("wZmax", w.UINT), ("wNumButtons", w.UINT),
        ("wPeriodMin", w.UINT), ("wPeriodMax", w.UINT),
        ("wRmin", w.UINT), ("wRmax", w.UINT), ("wUmin", w.UINT), ("wUmax", w.UINT),
        ("wVmin", w.UINT), ("wVmax", w.UINT), ("wCaps", w.UINT),
        ("wMaxAxes", w.UINT), ("wNumAxes", w.UINT), ("wMaxButtons", w.UINT),
        ("szRegKey", w.WCHAR * 32), ("szOEMVxD", w.WCHAR * 260)]


class JOYINFOEX(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("dwFlags", w.DWORD),
        ("dwXpos", w.DWORD), ("dwYpos", w.DWORD), ("dwZpos", w.DWORD),
        ("dwRpos", w.DWORD), ("dwUpos", w.DWORD), ("dwVpos", w.DWORD),
        ("dwButtons", w.DWORD), ("dwButtonNumber", w.DWORD), ("dwPOV", w.DWORD),
        ("dwReserved1", w.DWORD), ("dwReserved2", w.DWORD)]


def read(dev):
    i = JOYINFOEX()
    i.dwSize = ctypes.sizeof(i)
    i.dwFlags = JOY_RETURNALL
    if winmm.joyGetPosEx(dev, ctypes.byref(i)) != 0:
        return None
    return (i.dwXpos, i.dwYpos, i.dwZpos, i.dwRpos, i.dwUpos, i.dwVpos,
            i.dwButtons, i.dwPOV)


def enumerate_devices():
    print("joyGetNumDevs (driver slots):", winmm.joyGetNumDevs(), "\n")
    found = 0
    for dev in range(16):
        c = JOYCAPSW()
        if winmm.joyGetDevCapsW(dev, ctypes.byref(c), ctypes.sizeof(c)) != 0:
            continue
        found += 1
        r = read(dev)
        print(f"=== winmm index {dev}   (input.map token 'joystick{dev + 1}') ===")
        print(f"  name     : {c.szPname}")
        print(f"  VID:PID  : {c.wMid:04X}:{c.wPid:04X}")
        print(f"  axes     : {c.wNumAxes} of max {c.wMaxAxes}    buttons: {c.wNumButtons}")
        print(f"  caps     : {', '.join(n for b, n in CAPS.items() if c.wCaps & b) or '(none)'}")
        print(f"  connected: {r is not None}")
        if r:
            print("  live     : " + "  ".join(f"{NAMES[k]}={r[k]}" for k in range(6))
                  + f"  POV={r[7]} buttons={r[6]:#b}")
        print("  NOTE: a snapshot taken immediately after start can read 32767")
        print("        defaults - the device has not settled. Use --capture.\n")
    if not found:
        print("No winmm joysticks. Connect the device BEFORE running (and before")
        print("launching the game - the 1997 engine enumerates only at startup).")


def capture(dev, warmup=4.0, wait=240.0, record=40.0, thresh=5000):
    t = time.time()
    while time.time() - t < warmup:
        read(dev); time.sleep(0.05)
    base = read(dev)
    if base is None:
        print(f"device {dev} not present"); return
    print("settled baseline:", dict(zip(NAMES + ["buttons", "POV"], base)), flush=True)

    t0, hits, trig = time.time(), 0, None
    while time.time() - t0 < wait:
        r = read(dev)
        if r:
            d = [abs(r[k] - base[k]) for k in range(6)]
            if max(d) > thresh or r[6] != base[6]:
                hits += 1
                if hits >= 5:
                    trig = NAMES[d.index(max(d))] if max(d) > thresh else f"button {r[6]}"
                    break
            else:
                hits = 0
        time.sleep(0.02)
    if not trig:
        print(f"NO INPUT DETECTED in {wait:.0f}s"); return
    print(f"triggered by {trig} -> recording {record:.0f}s", flush=True)

    s, t1 = [], time.time()
    while time.time() - t1 < record:
        r = read(dev)
        if r:
            s.append((round(time.time() - t1, 2),) + r)
        time.sleep(0.02)
    json.dump(s, open("joytrace.json", "w"))
    print(f"captured {len(s)} samples -> joytrace.json\n")
    report(s)


def report(s):
    print("=== per axis ===")
    live = []
    for k in range(6):
        v = [r[k + 1] for r in s]
        rest = max(set(v), key=v.count)
        span = max(v) - min(v)
        flag = "  <-- USED" if span > 3000 else ""
        print(f"  {NAMES[k]}: rest={rest:5d} min={min(v):5d} max={max(v):5d} span={span:5d}{flag}")
        if span > 3000:
            live.append((k, rest, min(v), max(v)))
    # The question that decides whether an axis can drive I76's `throttle`:
    # a single bidirectional sink NEEDS a centre-resting axis.
    print("\n=== centre-resting test (decides if it can drive `throttle`) ===")
    for k, rest, lo, hi in live:
        below, above = rest - lo, hi - rest
        ok = below > 3000 and above > 3000
        print(f"  {NAMES[k]}: -{below} / +{above}  -> "
              + ("BIDIRECTIONAL, centre-resting: usable for `throttle`" if ok
                 else "one-way, rests at an EXTREME: would pin throttle at full deflection"))
    mask = 0
    for r in s:
        mask |= r[7]
    if mask:
        print("\n  buttons seen:", [i + 1 for i in range(32) if mask >> i & 1])


if __name__ == "__main__":
    dev = 0
    if "-d" in sys.argv:
        dev = int(sys.argv[sys.argv.index("-d") + 1])
    if "--capture" in sys.argv:
        capture(dev)
    else:
        enumerate_devices()
