#!/usr/bin/env python3
"""cbsites.py - every DLL call through the exe callback table (ShellMain arg 9, stored at 0x10058198 by the
instruction at 0x1001e2e3). Method: capstone linear sweep of .text; for each `mov R, [0x10058198]`, follow the
next 12 instructions while R is not overwritten and record every `call [R+disp]` / `call [R]` (slot = disp/4)
and every `mov R2,[R+disp]` (indirect slot load). Also reports direct `call [0x10058198+disp]`-style sites
(none expected). Output: tsv slot, site, containing function, form.
"""
import sys, collections
from sdis import Img, sweep, containing, PRISTINE
from capstone.x86 import X86_OP_MEM, X86_OP_REG, X86_REG_EAX, X86_REG_ECX, X86_REG_EDX

TBL = 0x10058198


def main():
    img = Img()
    assert img.md5 == PRISTINE
    ins_list = list(sweep(img))
    rows = []
    paired = set()
    loads = []
    for i, ins in enumerate(ins_list):
        if ins.mnemonic != "mov" or len(ins.operands) != 2:
            continue
        d, s = ins.operands
        if not (d.type == X86_OP_REG and s.type == X86_OP_MEM and (s.mem.disp & 0xffffffff) == TBL and s.mem.base == 0 and s.mem.index == 0):
            continue
        R = d.reg
        loads.append(ins.address)
        for j in range(i + 1, min(i + 40, len(ins_list))):
            nx = ins_list[j]
            used = False
            for op in nx.operands:
                if op.type == X86_OP_MEM and op.mem.base == R:
                    slot = op.mem.disp // 4
                    form = "call" if nx.mnemonic == "call" else nx.mnemonic
                    rows.append((slot, nx.address, form, ins.address))
                    paired.add(ins.address)
                    used = True
            # stop when R is overwritten (dest register == R and not a mem use)
            if nx.operands and nx.operands[0].type == X86_OP_REG and nx.operands[0].reg == R and nx.mnemonic in ("mov", "lea", "xor", "pop") and not used:
                break
            if nx.mnemonic in ("ret", "jmp"):
                break
            if nx.mnemonic == "call" and R in (X86_REG_EAX, X86_REG_ECX, X86_REG_EDX):
                break
    by = collections.defaultdict(list)
    for slot, site, form, ld in rows:
        c = containing(site)
        by[slot].append((site, form, ld, c[2]["start"] if c else "?"))
    print("# slot\tn_sites\tsites(site:form:fn)  method=capstone linear sweep, table ptr load at 0x%x then [R+4*slot]" % TBL)
    for slot in sorted(by):
        v = by[slot]
        fns = sorted(set(x[3] for x in v))
        print("%02d\t%d\t%s" % (slot, len(v), " ".join("%x:%s:%s" % (s, f, fn) for s, f, l, fn in v)))
    print("# table loads with no paired use:", " ".join("%x" % a for a in loads if a not in paired))
    missing = [k for k in range(27) if k not in by]
    print("# slots with no site found:", missing)


if __name__ == "__main__":
    main()
