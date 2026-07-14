#!/usr/bin/env python3
# evdev-tap: the LINUX-side half of the I76 input science. Lists every input
# device and streams events from Steam Input's virtual devices (what Wine sees
# as its input source). No dependencies - raw struct reads on /dev/input.
# Usage: python3 evdev-tap.py            (list devices)
#        python3 evdev-tap.py N [secs]   (stream /dev/input/eventN)
import struct, sys, os, glob, time, select

def name_of(ev):
    try:
        return open(f"/sys/class/input/{os.path.basename(ev)}/device/name").read().strip()
    except Exception:
        return "?"

if len(sys.argv) < 2:
    for ev in sorted(glob.glob("/dev/input/event*"), key=lambda p: int(p[16:])):
        print(f"{ev}: {name_of(ev)}")
    print("\nStream one: python3 evdev-tap.py <N> [seconds]")
    sys.exit(0)

n, secs = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30
path = f"/dev/input/event{n}"
print(f"streaming {path} ({name_of(path)}) for {secs}s...")
EV = {0x00:"SYN",0x01:"KEY",0x02:"REL",0x03:"ABS",0x04:"MSC"}
ABS = {0:"X",1:"Y",2:"Z",3:"RX",4:"RY",5:"RZ",16:"HAT0X",17:"HAT0Y"}
fmt = "llHHi"; sz = struct.calcsize(fmt)
with open(path, "rb", buffering=0) as f:
    end = time.time() + secs
    while time.time() < end:
        r, _, _ = select.select([f], [], [], 0.5)
        if not r: continue
        data = f.read(sz)
        if not data or len(data) < sz: continue
        _, _, etype, code, val = struct.unpack(fmt, data)
        if etype == 0: continue  # SYN
        t = EV.get(etype, hex(etype))
        c = ABS.get(code, code) if etype == 3 else code
        print(f"{t} code={c} val={val}", flush=True)
print("done")
