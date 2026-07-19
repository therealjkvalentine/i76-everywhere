#!/usr/bin/env python3
"""Disassemble a VA range of a PE (x86-32) and annotate memory operands that
land in .data/.rdata with the string they point to when one is there. Pairs
with exe-xref.py: xref finds the function, this reads what it touches.

Usage: python3 tools/exe-disasm.py <exe> <hexVA> [count]
"""
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

def load(path):
    data = open(path, "rb").read()
    e = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, e + 6)[0]
    opt = struct.unpack_from("<H", data, e + 20)[0]
    base = struct.unpack_from("<I", data, e + 24 + 28)[0]
    secs = []
    off = e + 24 + opt
    for i in range(nsec):
        s = data[off+40*i: off+40*(i+1)]
        nm = s[:8].rstrip(b"\0").decode(errors="replace")
        vsz, va, rsz, raw = struct.unpack_from("<IIII", s, 8)
        secs.append((nm, va, vsz, rsz, raw))
    return data, base, secs

def va2raw(secs, base, va):
    for nm, sva, vsz, rsz, raw in secs:
        if sva <= va - base < sva + max(vsz, rsz):
            off = va - base - sva
            return (raw + off, nm) if off < rsz else (None, nm)
    return None, None

def cstr(data, secs, base, va):
    r, _ = va2raw(secs, base, va)
    if r is None: return None
    end = data.find(b"\0", r, r + 48)
    if end < 0: return None
    s = data[r:end]
    if 2 < len(s) < 48 and all(32 <= c < 127 for c in s):
        return s.decode()
    return None

def main():
    exe, va = sys.argv[1], int(sys.argv[2], 16)
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    data, base, secs = load(exe)
    raw, sec = va2raw(secs, base, va)
    if raw is None: sys.exit(f"VA {va:#x} not in a raw section")
    code = data[raw: raw + count * 8]
    md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True
    n = 0
    for insn in md.disasm(code, va):
        note = ""
        for m in list(insn.operands):
            if m.type == 3 and m.mem.base == 0 and m.mem.index == 0:  # [disp] absolute
                d = m.mem.disp & 0xffffffff
                s = cstr(data, secs, base, d)
                _, msec = va2raw(secs, base, d)
                if 0x400000 <= d < 0x600000:
                    note = f"   ; [{d:#08x}{'/'+msec if msec else ''}]" + (f' = {s!r}' if s else '')
            if m.type == 1:  # imm
                d = m.imm & 0xffffffff
                s = cstr(data, secs, base, d)
                if s: note = f"   ; {d:#08x} = {s!r}"
        print(f"0x{insn.address:08x}  {insn.mnemonic:7}{insn.op_str}{note}")
        n += 1
        if n >= count: break

if __name__ == "__main__":
    main()
