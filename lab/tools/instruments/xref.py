#!/usr/bin/env python3
"""xref.py - find every instruction in i76.exe that touches a given address.

Hardware breakpoints (find-reads.exe) tell you WHICH code touched an address while the game
ran, but only for the moments you were watching, and they say nothing about what the code
does with it. This disassembles the exe's whole .text section once and reports every static
reference to an address, so a writer can be found even when it fires rarely.

    python tools/xref.py 0x5DDA74 0x5068FC

Prints the referencing instruction plus a few lines of context either side, which is usually
enough to see the constant being added and the shape of the update.
"""
import sys, struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"C:\Users\james\i76-uncap-lab\game\i76.exe"


def load_sections(path):
    """Return (image_base, [(va, size, file_off, name, data)]) for a PE32 file."""
    blob = open(path, "rb").read()
    pe = struct.unpack_from("<I", blob, 0x3C)[0]
    assert blob[pe:pe + 4] == b"PE\0\0", "not a PE"
    nsec = struct.unpack_from("<H", blob, pe + 6)[0]
    optsz = struct.unpack_from("<H", blob, pe + 20)[0]
    base = struct.unpack_from("<I", blob, pe + 24 + 28)[0]
    secs = []
    off = pe + 24 + optsz
    for i in range(nsec):
        h = blob[off + i * 40: off + (i + 1) * 40]
        name = h[:8].rstrip(b"\0").decode("latin1")
        vsize, va, rawsz, rawoff = struct.unpack_from("<IIII", h, 8)
        data = blob[rawoff:rawoff + rawsz]
        secs.append((base + va, max(vsize, rawsz), rawoff, name, data))
    return base, secs


def main():
    targets = [int(a, 16) for a in sys.argv[1:]]
    if not targets:
        print(__doc__)
        return
    base, secs = load_sections(EXE)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = False

    # BYTE SCAN, not a linear sweep. A linear disassembly of .text desyncs the first time it
    # hits inline data or a jump table (visible as garbage like `rcr cl, 0x5d`), and everything
    # after the desync is silently lost. That produced a false "0 references" for the frame
    # counter 0x5A7E1C - an address that appears 5 times in the file - because its refs sit
    # late in .text while the camera refs that DID show up sit early. Scanning for the
    # little-endian address bytes finds every candidate regardless of decode state; each hit is
    # then disassembled in a small window that re-syncs almost immediately.
    for va, size, off, name, data in secs:
        if not name.startswith(".text") and name not in ("CODE", "text"):
            continue
        for t in targets:
            pat = struct.pack("<I", t)
            i = 0
            while True:
                i = data.find(pat, i)
                if i < 0:
                    break
                site = va + i
                print("=" * 72)
                print("REF to 0x%X: operand bytes at 0x%08X" % (t, site))
                shown = None
                for back in (24, 18, 12, 8, 5, 3, 2, 1):
                    start = max(0, i - back)
                    insns = list(md.disasm(data[start:i + 14], va + start))
                    hit = [x for x in insns
                           if x.address <= site < x.address + x.size and x.size > 4]
                    if hit:
                        shown = (insns, hit[0].address)
                        break
                if shown:
                    for ins in shown[0]:
                        mark = ">>" if ins.address == shown[1] else "  "
                        print("  %s 0x%08X  %-18s %-8s %s" % (
                            mark, ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
                else:
                    print("   (no alignment decodes an instruction over these bytes - likely data)")
                i += 1


if __name__ == "__main__":
    main()
