#!/usr/bin/env python3
"""callers.py - linear E8 (call rel32) / E9 (jmp rel32) scan of .text for direct callers of one address. Read-only.

  python callers.py <exe> <target va hex> [...]
"""
import struct, sys
from exedis import PE

pe = PE(sys.argv[1])
for tgt in sys.argv[2:]:
    t = int(tgt, 16)
    va0, sz, rp, rs = pe.secs[0]
    code = pe.d[rp:rp + rs]
    base = pe.base + va0
    hits = []
    for i in range(len(code) - 5):
        if code[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", code, i + 1)[0]
            if base + i + 5 + rel == t:
                hits.append("%s 0x%08x" % ("call" if code[i] == 0xE8 else "jmp ", base + i))
    print("0x%08x: %d direct callers" % (t, len(hits)))
    for h in hits:
        print("   ", h)
