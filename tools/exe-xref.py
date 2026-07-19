#!/usr/bin/env python3
"""String-anchor cross-reference mapper for the I'76 executables.

Finds where anchor strings live in the exe (VA), then finds every place the
binary embeds that VA as a 4-byte immediate/pointer — i.e. the code or data
that references the string. This is the "re-anchoring" step the Roanish
decompile prescribes (its addresses are Nitro; ours is Gold), done without
Ghidra: the xref VAs are direct entry points for a Ghidra/Cheat-Engine session,
and pointer-table detection maps whole string tables (e.g. the input-action
table) in one shot.

Usage: python3 tools/exe-xref.py <exe> [anchor ...]
With no anchors, uses the built-in target list (camera/save/input/FF).
"""
import struct, sys
from collections import defaultdict

DEFAULT_ANCHORS = [
    # camera / look (target 1)
    "track_yaw_delta", "track_pitch_delta", "pilot_glance_target", "pilot_glance_up",
    # save system (target 4)
    "savegame.dir", "save%03d",
    # input system (target 5)
    "input.map", "joystick1", "Joystick", "Rudder", "Throttle", "Left/Right",
    "Down/Up", "weapon_fire",
    # entity / vehicle anchors (targets 2-3)
    "cannot create entity",
    # force feedback (target 6)
    "FRC",
]

def load_pe(path):
    data = open(path, "rb").read()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    opt_sz = struct.unpack_from("<H", data, e_lfanew + 20)[0]
    image_base = struct.unpack_from("<I", data, e_lfanew + 24 + 28)[0]
    secs = []
    off = e_lfanew + 24 + opt_sz
    for i in range(nsec):
        s = data[off + 40 * i: off + 40 * (i + 1)]
        name = s[:8].rstrip(b"\0").decode(errors="replace")
        vsize, va, rsize, raw = struct.unpack_from("<IIII", s, 8)
        secs.append((name, va, rsize, raw))
    return data, image_base, secs

def raw_to_va(secs, base, raw_off):
    for name, va, rsize, raw in secs:
        if raw <= raw_off < raw + rsize:
            return base + va + (raw_off - raw), name
    return None, None

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    exe = sys.argv[1]
    anchors = sys.argv[2:] or DEFAULT_ANCHORS
    data, base, secs = load_pe(exe)
    print(f"{exe}: base=0x{base:08x}, {len(secs)} sections "
          f"({', '.join(s[0] for s in secs)})\n")

    # 1. locate each anchor string (null-terminated match preferred)
    str_vas = {}
    for a in anchors:
        needle = a.encode()
        hits = []
        start = 0
        while True:
            i = data.find(needle, start)
            if i < 0: break
            # prefer standalone strings: preceded by NUL and followed by NUL
            standalone = (i == 0 or data[i-1] == 0) and data[i+len(needle)] == 0
            hits.append((i, standalone))
            start = i + 1
        chosen = [h for h in hits if h[1]] or hits
        for i, _ in chosen[:2]:
            va, sec = raw_to_va(secs, base, i)
            if va:
                str_vas.setdefault(a, []).append(va)
                print(f"anchor {a!r}: raw 0x{i:x} -> VA 0x{va:08x} ({sec})")
        if a not in str_vas:
            print(f"anchor {a!r}: NOT FOUND")
    print()

    # 2. find embedded 4-byte references to each string VA
    all_refs = {}
    for a, vas in str_vas.items():
        refs = []
        for va in vas:
            pat = struct.pack("<I", va)
            start = 0
            while True:
                i = data.find(pat, start)
                if i < 0: break
                rva, rsec = raw_to_va(secs, base, i)
                if rva: refs.append((rva, rsec, va))
                start = i + 1
        all_refs[a] = refs
        if refs:
            lst = "  ".join(f"0x{rva:08x}({rsec})" for rva, rsec, _ in refs[:8])
            more = f"  +{len(refs)-8} more" if len(refs) > 8 else ""
            print(f"xrefs -> {a!r}: {lst}{more}")
        else:
            print(f"xrefs -> {a!r}: none (string may be reached via a table base + index)")
    print()

    # 3. pointer-table detection: xrefs to different anchors at a constant
    #    stride inside a data section = a string-pointer table (e.g. the
    #    input-action table). Report table candidates.
    data_refs = sorted((rva, a) for a, refs in all_refs.items()
                       for rva, rsec, _ in refs if rsec != ".text")
    runs = []
    for i in range(len(data_refs) - 1):
        d = data_refs[i+1][0] - data_refs[i][0]
        if 4 <= d <= 64:
            runs.append((data_refs[i], data_refs[i+1], d))
    if runs:
        print("possible string-pointer tables (data-section refs at small strides):")
        for (v1, a1), (v2, a2), d in runs:
            print(f"  0x{v1:08x} [{a1}]  ->  0x{v2:08x} [{a2}]   stride {d}")
        print("\nA constant stride across many action names = the input-action table;"
              "\nits per-entry payload dwords are the handler/state pointers to chase.")

if __name__ == "__main__":
    main()
