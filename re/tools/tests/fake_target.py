#!/usr/bin/env python3
r"""fake_target.py - a throwaway process that maps an i76 image at its preferred base so
which_build.py's ReadProcessMemory path can be exercised without launching the game.

    python tools\tests\fake_target.py --image <exe> [--patch 0x499b25:b8c8000000 ...] [--seconds 60]

Copies every section of <exe> to VA image_base + rva inside this (64-bit) process with
VirtualAlloc(image_base, SizeOfImage, MEM_RESERVE|MEM_COMMIT, PAGE_READWRITE) - the address is
free in a 64-bit python.exe - applies the optional patches, prints 'READY pid=<pid> base=<hex>'
and sleeps. The PE headers are mapped too, so the import-descriptor walk works.
"""
import argparse
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pe_ident  # noqa: E402

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.VirtualAlloc.restype = ctypes.c_void_p
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--patch", action="append", default=[], help="VA:hexbytes, applied after mapping")
    ap.add_argument("--seconds", type=float, default=60)
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
        b = bytes.fromhex(hx)
        ctypes.memmove(ctypes.c_void_p(int(va_s, 16)), b, len(b))
    print("READY pid=%d base=%s image=%s md5=%s patches=%d" % (os.getpid(), hex(base), a.image, ident["md5"], len(a.patch)), flush=True)
    time.sleep(a.seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
