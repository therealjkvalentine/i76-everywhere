#!/usr/bin/env python3
"""bspatch.py OLD NEW PATCH - apply a BSDIFF40 patch (Colin Percival's format, as bsdiff4 / tools/mac-kit/make-patches.py
write it) with the Python standard library only: SteamOS has python3 but no bspatch. I'76 Deck Kit (i76-everywhere deck/kit)."""
import bz2, sys


def offtin(b):
    y = int.from_bytes(b[:7] + bytes([b[7] & 0x7f]), 'little')
    return -y if b[7] & 0x80 else y


def bspatch(old, patch):
    if patch[:8] != b'BSDIFF40':
        raise ValueError('not a BSDIFF40 patch')
    lc, ld, newsize = offtin(patch[8:16]), offtin(patch[16:24]), offtin(patch[24:32])
    if lc < 0 or ld < 0 or newsize < 0:
        raise ValueError('corrupt header')
    ctrl = bz2.decompress(patch[32:32 + lc])
    diff = bz2.decompress(patch[32 + lc:32 + lc + ld])
    extra = bz2.decompress(patch[32 + lc + ld:])
    new = bytearray(newsize)
    op = np = ci = di = ei = 0
    while np < newsize:
        x, y, z = offtin(ctrl[ci:ci + 8]), offtin(ctrl[ci + 8:ci + 16]), offtin(ctrl[ci + 16:ci + 24])
        ci += 24
        if np + x > newsize:
            raise ValueError('corrupt patch (diff block)')
        for i in range(x):
            o = old[op + i] if 0 <= op + i < len(old) else 0
            new[np + i] = (diff[di + i] + o) & 0xff
        di += x; np += x; op += x
        if np + y > newsize:
            raise ValueError('corrupt patch (extra block)')
        new[np:np + y] = extra[ei:ei + y]
        ei += y; np += y; op += z
    return bytes(new)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    old = open(sys.argv[1], 'rb').read()
    out = bspatch(old, open(sys.argv[3], 'rb').read())
    open(sys.argv[2], 'wb').write(out)
