#!/usr/bin/env python3
r"""fake_sim.py - throwaway target for tools\i76poke.py / tools\snapshot.py tests (no game launch, H10).

    python tools\tests\fake_sim.py --image <exe> [--patch 0x499b25:b8c8000000] [--tick-ms 20] [--start-after 0]
        [--pause-after S --pause-for S] [--clobber VA:hex] [--event VA:hex:N] [--pump] [--seconds 120]

Maps every section of <exe> at its preferred base inside this (64-bit) python.exe exactly as
tools\tests\fake_target.py does (VirtualAlloc at image_base, PAGE_READWRITE), then runs a fake sim clock:
  - every --tick-ms the dword at 0x5a7e1c (frame counter, class bss in the real image) is incremented and
    0x5a7e74 (game time, float) advances by tick_ms/1000; ticking starts after --start-after seconds
    (0x5a7e1c == 0 before that = the menu state) and freezes for --pause-for seconds at --pause-after
    (the PAUSE_GAME state: counter frozen and > 0 while the pump keeps running);
  - --clobber VA:hex rewrites those bytes every tick (i76poke expects `clobbered-per-frame` there);
  - --event VA:hex:N rewrites those bytes every N ticks (`clobbered-on-event`);
  - --pump calls user32!PeekMessageA once per tick so a pump hook on the fallback export counts.
Prints `READY pid=<pid> base=<hex>` and keeps ticking for --seconds. Everything is data of this process;
nothing here touches the game folder.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pe_ident  # noqa: E402

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.VirtualAlloc.restype = ctypes.c_void_p
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04
FRAME_COUNTER = 0x5A7E1C
GAME_TIME = 0x5A7E74


def poke(va, b):
    ctypes.memmove(ctypes.c_void_p(va), b, len(b))


def peek_u32(va):
    return struct.unpack("<I", ctypes.string_at(va, 4))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--patch", action="append", default=[])
    ap.add_argument("--tick-ms", type=float, default=20.0)
    ap.add_argument("--start-after", type=float, default=0.0)
    ap.add_argument("--pause-after", type=float, default=-1.0)
    ap.add_argument("--pause-for", type=float, default=0.0)
    ap.add_argument("--clobber", action="append", default=[], help="VA:hex rewritten every tick")
    ap.add_argument("--event", action="append", default=[], help="VA:hex:N rewritten every N ticks")
    ap.add_argument("--pump", action="store_true")
    ap.add_argument("--seconds", type=float, default=120)
    a = ap.parse_args()
    ident = pe_ident.identity(a.image)
    base = int(ident["image_base"], 16)
    size = ident["size_of_image"]
    p = k32.VirtualAlloc(ctypes.c_void_p(base), size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE)
    if not p or p != base:
        print("FAIL VirtualAlloc(%s) -> %s err %d" % (hex(base), hex(p or 0), ctypes.get_last_error()), flush=True)
        return 2
    with open(a.image, "rb") as f:
        raw = f.read()
    first_raw = min(int(s["raw_ptr"], 16) for s in ident["sections"])
    ctypes.memmove(ctypes.c_void_p(base), raw[:first_raw], first_raw)
    for s in ident["sections"]:
        va = int(s["va"], 16)
        rp = int(s["raw_ptr"], 16)
        n = min(s["raw_size"], size - (va - base))
        ctypes.memmove(ctypes.c_void_p(va), raw[rp:rp + n], n)
    for spec in a.patch:
        va_s, hx = spec.split(":")
        poke(int(va_s, 16), bytes.fromhex(hx))
    clob = [(int(v, 16), bytes.fromhex(h)) for v, h in (s.split(":") for s in a.clobber)]
    evs = [(int(v, 16), bytes.fromhex(h), int(n)) for v, h, n in (s.split(":") for s in a.event)]
    u32 = ctypes.WinDLL("user32", use_last_error=True) if a.pump else None
    msg = ctypes.create_string_buffer(64)
    print("READY pid=%d base=%s image=%s md5=%s patches=%d tick_ms=%s clobber=%d event=%d pump=%s" % (
        os.getpid(), hex(base), a.image, ident["md5"], len(a.patch), a.tick_ms, len(clob), len(evs), a.pump), flush=True)
    stop = time.time() + a.seconds
    t_start = time.time() + a.start_after
    t_pause = (time.time() + a.pause_after) if a.pause_after >= 0 else None
    ticks = 0

    def loop():
        nonlocal ticks
        while time.time() < stop:
            now = time.time()
            if u32 is not None:
                u32.PeekMessageA(msg, None, 0, 0, 0)
            paused = t_pause is not None and t_pause <= now < t_pause + a.pause_for
            if now >= t_start and not paused:
                ticks += 1
                poke(FRAME_COUNTER, struct.pack("<I", ticks))
                poke(GAME_TIME, struct.pack("<f", ticks * a.tick_ms / 1000.0))
                for va, b in clob:
                    poke(va, b)
                for va, b, n in evs:
                    if ticks % n == 0:
                        poke(va, b)
            time.sleep(a.tick_ms / 1000.0)

    th = threading.Thread(target=loop, daemon=True)
    th.start()
    th.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
