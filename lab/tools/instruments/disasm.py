#!/usr/bin/env python3
"""disasm.py - disassemble i76.exe at a virtual address.

    python tools/disasm.py 0x417940 60          # 60 instructions from 0x417940
    python tools/disasm.py 0x417964 40 -back 24 # start 24 bytes earlier

Reads the on-disk exe (no ASLR, so file VAs match runtime addresses), which means this works
without the game running and without attaching a debugger to it.
"""
import sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from xref import load_sections


def main():
    va = int(sys.argv[1], 16)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    back = 0
    if "-back" in sys.argv:
        back = int(sys.argv[sys.argv.index("-back") + 1])
    va -= back
    base, secs = load_sections(r"C:\Users\james\i76-uncap-lab\game\i76.exe")
    for sva, size, off, name, data in secs:
        if sva <= va < sva + size:
            md = Cs(CS_ARCH_X86, CS_MODE_32)
            for i, ins in enumerate(md.disasm(data[va - sva:], va)):
                print("0x%08X  %-24s %-8s %s" % (
                    ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
                if i >= n:
                    break
            return
    print("address not in any section")


if __name__ == "__main__":
    main()
