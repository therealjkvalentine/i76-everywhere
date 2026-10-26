#!/usr/bin/env python3
"""widgets.py - decode a static shell widget table (record stride 0x2c, terminator +0 == -1; per builder 0x10016600:
cmp [esi],-1 at 0x1001661e / add esi,0x2c at 0x100166c2). Raw dwords printed; fields named only where the builder
proves them: +0x1c create fn called with the record (0x1001667b) -> result stored at +0x18 (0x10016680); +0x8 and +0xc
default from result+0x24 / +0x20 when -1 (0x10016695 / 0x100166a3).
"""
import sys, struct
from sdis import Img, fname
img=Img()
def rec(a):
    return struct.unpack('<11i', img.read(a,0x2c))
def dump(t, maxn=60):
    print('== table 0x%x'%t)
    a=t
    for i in range(maxn):
        r=rec(a)
        if r[0]==-1: print('   end at 0x%x'%a); return
        cap=None
        for v in r:
            s=img.cstring(v & 0xffffffff) if img.klass(v & 0xffffffff) in ('data','rdata') else None
            if s: cap=s
        print('   %x id=%d  %s  %r'%(a, r[0], ' '.join('%x'%(v&0xffffffff) for v in r[1:]), cap))
        a+=0x2c
for x in sys.argv[1:]: dump(int(x,16))
