#!/usr/bin/env python3
"""mw2db.py - DATABASE.MW2 container reader, per TMPackDataBaseObj ctor 0x10007fd0 / GetDBItem 0x10008240:
u32 count; u32 offset[count]; item id k (1-based, GetDBItem does `dec ecx` at 0x10008258) = bytes [offset[k-1], offset[k]) (last: to EOF, 0x10008111 ftell).
    python mw2db.py <DATABASE.MW2> list | dump <id> [n] | extract <outdir>
"""
import sys, struct, os
def load(p):
    d=open(p,'rb').read(); n=struct.unpack_from('<I',d,0)[0]
    offs=list(struct.unpack_from('<%dI'%n,d,4)); ends=offs[1:]+[len(d)]
    return d,[(offs[i],ends[i]-offs[i]) for i in range(n)]
def main(a):
    d,items=load(a[1])
    if a[2]=='list':
        for i,(o,s) in enumerate(items,1):
            b=d[o:o+min(s,24)]
            print('%3d 0x%02x off=0x%07x size=%7d  %s  %r'%(i,i,o,s,b[:16].hex(' '),bytes(c if 32<=c<127 else 46 for c in b)))
    elif a[2]=='dump':
        k=int(a[3],0); o,s=items[k-1]; n=int(a[4],0) if len(a)>4 else 256
        b=d[o:o+min(s,n)]
        for i in range(0,len(b),16):
            r=b[i:i+16]; print('%06x  %-48s %s'%(i,r.hex(' '),''.join(chr(c) if 32<=c<127 else '.' for c in r)))
    elif a[2]=='extract':
        os.makedirs(a[3],exist_ok=True)
        for i,(o,s) in enumerate(items,1): open(os.path.join(a[3],'item%03d.bin'%i),'wb').write(d[o:o+s])
main(sys.argv)

def unlzss(b):
    """DB item decompressor, per TMPackDataBaseObj 0x10008320: u32 outlen; LZSS, 4 KB ring at 0x10052178 zeroed
    (rep stosd 0x400 dwords at 0x10008412), write pos starts at ring[0]; flag byte LSB-first (shr at 0x1000842c,
    or ah,1 sentinel at 0x10008449); bit 1 = literal; bit 0 = u16 LE, pos = v & 0xfff (0x100084b6),
    len = ((v >> 12) & 0xf) + 3 (0x100084b0..0x100084bb)."""
    import struct as _s
    n = _s.unpack_from('<I', b, 0)[0]; i = 4; ring = bytearray(0x1000); w = 0; out = bytearray(); flags = 0
    while len(out) < n and i < len(b):
        flags >>= 1
        if not (flags & 0x100):
            flags = b[i] | 0xff00; i += 1
        if flags & 1:
            c = b[i]; i += 1; out.append(c); ring[w] = c; w = (w + 1) & 0xfff
        else:
            v = b[i] | (b[i + 1] << 8); i += 2
            p = v & 0xfff; L = ((v >> 12) & 0xf) + 3
            for _ in range(L):
                c = ring[p]; out.append(c); ring[w] = c; w = (w + 1) & 0xfff; p = (p + 1) & 0xfff
    return bytes(out[:n])
