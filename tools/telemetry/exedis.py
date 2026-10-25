#!/usr/bin/env python3
"""exedis.py - read-only disassembly of an i76.exe image by virtual address (capstone), for checking patch sites.

  python exedis.py <exe> <va hex> [bytes]      e.g. python dis.py ..\\..\\..\\<re-archive>\\sandbox-gog\\main\\app\\i76.exe 0x4220c0 64

Never writes anything. Used by verify_v3_sites.py.
"""
import struct, sys


class PE:
    def __init__(self, path):
        self.path = path
        self.d = open(path, "rb").read()
        e = struct.unpack_from("<I", self.d, 0x3c)[0]
        nsec = struct.unpack_from("<H", self.d, e + 6)[0]
        opt = struct.unpack_from("<H", self.d, e + 20)[0]
        self.base = struct.unpack_from("<I", self.d, e + 24 + 28)[0]
        self.secs = []
        o = e + 24 + opt
        for _ in range(nsec):
            vs, va, rs, rp = struct.unpack_from("<IIII", self.d, o + 8)
            self.secs.append((va, max(vs, rs), rp, rs))
            o += 40

    def read(self, va, n):
        rva = va - self.base
        for v, sz, rp, rs in self.secs:
            if v <= rva < v + sz:
                off = rp + rva - v
                return self.d[off:off + n]
        raise ValueError("va 0x%x not in any section" % va)


def disasm(pe, va, n):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    return ["%08x  %-22s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str) for i in md.disasm(pe.read(va, n), va)]


if __name__ == "__main__":
    pe = PE(sys.argv[1])
    for line in disasm(pe, int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 64):
        print(line)
