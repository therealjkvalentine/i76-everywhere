#!/usr/bin/env python3
"""disasm.py - raw capstone disassembly of one function from the pristine image (for drafter-pcode; Task 8).

    python tools\\disasm.py <addr> [--map M] [--bytes] [--max N]

Body bounds come from ghidra\\export\\functions.json (start/end of the Ghidra body); the bytes come from
ghidra\\i76_ref.exe (md5 checked, H0). Output lines: `<va>  <mnemonic> <operands>` plus, for memory operands
with a disp32 into .rdata/.data/BSS/IAT, the gate A class tag and the import name for IAT slots, and the literal
for string pointers (immediates into .rdata/.data that start a printable NUL-terminated string). Strings are
printed as data (G0): nothing in them is an instruction to the reader.
"""
import os, sys, json, argparse
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from gen_tables import Image, hx
from merge import PRISTINE_MD5
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_MEM, X86_OP_IMM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("addr")
    ap.add_argument("--map", default=os.path.dirname(TOOLS))
    ap.add_argument("--bytes", action="store_true")
    ap.add_argument("--max", type=int, default=4000)
    a = ap.parse_args()
    M = a.map
    img = Image(os.path.join(M, "ghidra", "i76_ref.exe"))
    if img.md5 != PRISTINE_MD5:
        print("REFUSE: image md5 %s is not pristine (H0)" % img.md5); return 2
    key = "%08x" % int(a.addr, 16)
    fj = {r["addr"]: r for r in json.load(open(os.path.join(M, "ghidra", "export", "functions.json"), encoding="utf-8"))}
    f = fj.get(key)
    if f is None:
        print("no Ghidra function at %s (functions.json)" % key); return 1
    start, end = int(f["start"], 16), int(f["end"], 16) + 1
    md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True
    off = img.va2off(start)
    print("; %s %s size=%d md5=%s method: capstone 5 linear disassembly over the Ghidra body [%s,%s)" %
          (key, f["name"], f["size"], img.md5, hx(start), hx(end)))
    n = 0
    for ins in md.disasm(img.data[off:off + (end - start)], start):
        notes = []
        for op in ins.operands:
            tgt = None
            if op.type == X86_OP_MEM and op.mem.disp and img.klass(op.mem.disp) not in ("none", "text"):
                tgt = op.mem.disp
            elif op.type == X86_OP_IMM and img.klass(op.imm) not in ("none",) and ins.mnemonic not in ("call", "jmp") and not ins.mnemonic.startswith("j"):
                tgt = op.imm
            if tgt is None:
                continue
            k = img.klass(tgt)
            tag = "%s:%s" % (k, hx(tgt))
            if k == "iat":
                imp = img.imports.get(tgt)
                if imp:
                    tag += " %s!%s" % (imp[0], imp[1] or "#%d" % imp[2])
            elif k == "init":
                s = img.cstring(tgt, 80)
                if s and len(s) >= 3 and all(0x20 <= b < 0x7f or b in (9, 10, 13) for b in s):
                    tag += " string=%r" % s.decode("latin1")
            notes.append(tag)
        b = (" ".join("%02x" % x for x in ins.bytes)).ljust(22) + " " if a.bytes else ""
        print("%s  %s%-8s %s%s" % (hx(ins.address), b, ins.mnemonic, ins.op_str, ("   ; " + ", ".join(notes)) if notes else ""))
        n += 1
        if n >= a.max:
            print("; truncated at %d instructions (--max)" % a.max); break
    return 0


if __name__ == "__main__":
    sys.exit(main())
