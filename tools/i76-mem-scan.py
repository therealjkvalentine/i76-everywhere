#!/usr/bin/env python3
"""Scan an i76 heap dump (from tools/i76-mem-dump.ahk) for values or diffs.

The AHK dumper walks the live game's committed private+RW regions via
VirtualQueryEx and writes dump.bin + dump.idx (VA/size/fileoffset per region).
This does the fast pattern logic Python-side.

Usage:
  i76-mem-scan.py dump.bin dump.idx find <int|f><value>   # locate a value
  i76-mem-scan.py A.bin A.idx diff B.bin B.idx <int|float> # changed addresses
The diff mode is the reliable way to pin LIVE values: dump, change the value
in-game (fire a weapon / take a hit), dump again, diff -> the address that
changed by the expected delta is the live field.
"""
import struct, sys

def load(binp, idxp):
    d = open(binp, "rb").read()
    idx = [(int(a,16),int(b,0),int(c,0)) for a,b,c in (l.split() for l in open(idxp))]
    return d, idx

def va_of(idx, fo):
    for b,s,f in idx:
        if f <= fo < f+s: return b+(fo-f)
    return None

def find(d, idx, spec):
    typ = "float" if spec[0]=="f" else "int"
    val = float(spec[1:]) if typ=="float" else int(spec)
    pat = struct.pack("<f", val) if typ=="float" else struct.pack("<i", val)
    hits, start = [], 0
    while True:
        i = d.find(pat, start)
        if i < 0: break
        start = i+1
        if i % 4 == 0: hits.append(va_of(idx, i))
    return typ, val, hits

def main():
    a = sys.argv
    if a[3] == "find":
        d, idx = load(a[1], a[2])
        typ, val, hits = find(d, idx, a[4])
        print(f"{typ} {val}: {len(hits)} hits")
        for h in hits[:60]:
            print(f"  0x{h:08x}")
    elif a[3] == "diff":
        dA, iA = load(a[1], a[2]); dB, iB = load(a[4], a[5])
        typ = a[6]
        # map VA->value in each, compare shared regions
        def table(d, idx):
            t = {}
            for b,s,f in idx:
                for o in range(0, s-4, 4):
                    v = struct.unpack_from("<f" if typ=="float" else "<i", d, f+o)[0]
                    t[b+o] = v
            return t
        tA, tB = table(dA, iA), table(dB, iB)
        changed = [(va, tA[va], tB[va]) for va in tA if va in tB and tA[va] != tB[va]]
        print(f"{len(changed)} addresses changed")
        for va, x, y in changed[:80]:
            print(f"  0x{va:08x}: {x} -> {y}")
    else:
        sys.exit(__doc__)

if __name__ == "__main__":
    main()
