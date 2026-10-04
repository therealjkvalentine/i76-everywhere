"""disp-cluster.py - find functions that touch a CLUSTER of struct offsets.

An entity field can't be xref'd by absolute address (the entity is in a register), but the CODE
that handles a multi-field sub-structure gives itself away: it emits several instructions with
displacements drawn from the same small set, close together. Armor is 8 current + 8 max values
at entity +0x138..+0x174, so the damage/repair/read code will show a dense run of
[reg+0x138..reg+0x174] memory operands.

    python disp-cluster.py 0x138 0x13c 0x148 0x14c 0x150 0x154 0x168 0x16c 0x170 0x174

Prints every window of .text where at least MIN_HITS distinct target displacements appear within
WINDOW instructions, with the enclosing addresses so you can disassemble it.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from xref import load_sections

WINDOW = 60          # instructions
MIN_HITS = 4         # distinct target displacements within the window


def main():
    targets = set(int(a, 0) for a in sys.argv[1:])
    if not targets:
        print(__doc__); return
    base, secs = load_sections(r"C:\Users\james\i76-uncap-lab\game\i76.exe")
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    for va, size, off, name, data in secs:
        if not (name.startswith('.text') or name in ('CODE', 'text')):
            continue
        insns = list(md.disasm(data, va))
        # displacement present on each instruction (from any memory operand)
        disp = [None] * len(insns)
        for i, ins in enumerate(insns):
            for op in ins.operands:
                if op.type == 3:  # X86_OP_MEM
                    d = op.mem.disp
                    if d in targets:
                        disp[i] = d
                        break
        # slide a window, report dense clusters
        reported = set()
        for i in range(len(insns)):
            seen = {}
            j = i
            while j < len(insns) and (insns[j].address - insns[i].address) < WINDOW * 6:
                if disp[j] is not None:
                    seen.setdefault(disp[j], insns[j].address)
                j += 1
            if len(seen) >= MIN_HITS:
                key = insns[i].address // 0x200
                if key in reported:
                    continue
                reported.add(key)
                lo = insns[i].address
                hi = insns[min(j, len(insns) - 1)].address
                print(f"cluster @ 0x{lo:08X}..0x{hi:08X}  "
                      f"disps: {sorted(hex(d) for d in seen)}")


if __name__ == '__main__':
    main()
