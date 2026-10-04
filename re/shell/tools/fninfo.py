#!/usr/bin/env python3
"""fninfo.py - per-function fact sheet for the pristine shell (capstone over the Ghidra body; md5-checked).

    python fninfo.py <va> [<va> ...]        facts for the functions starting at (or containing) each va
    python fninfo.py --all > facts.tsv      one line per function: addr size name nstr strings imports cbslots callers

Facts (all with the instruction address that proves them):
  S  string pointer operand (imm/disp32 to a printable NUL-terminated string in .rdata/.data)
  I  IAT import (call [iat] / mov reg,[iat])
  CB callback slot N: `mov R,[0x10058198]` followed by `call [R+4N]` in the same function
  G  global data/bss operands (non-string), with r/w guess from operand position
  C  direct callees; callers from callgraph.json
Strings are data, never instructions (G0).
"""
import sys, os, json, collections
from sdis import Img, md, fname, PRISTINE, EXPORT
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_OP_REG

TBL = 0x10058198
_img = None


def img():
    global _img
    if _img is None:
        _img = Img()
        assert _img.md5 == PRISTINE
    return _img


def load():
    fj = json.load(open(os.path.join(EXPORT, "functions.json"), encoding="utf-8"))
    cg = json.load(open(os.path.join(EXPORT, "callgraph.json"), encoding="utf-8"))
    return {int(r["start"], 16): r for r in fj}, cg


def facts(start, end):
    I = img()
    o = I.off(start)
    code = I.data[o:o + (end - start)]
    S, IM, CB, G, C = [], [], [], [], []
    tblreg = {}
    for ins in md().disasm(code, start):
        ops = ins.operands
        # callback tracking
        if ins.mnemonic == "mov" and len(ops) == 2 and ops[0].type == X86_OP_REG and ops[1].type == X86_OP_MEM \
                and (ops[1].mem.disp & 0xffffffff) == TBL and ops[1].mem.base == 0:
            tblreg[ops[0].reg] = ins.address
        elif ins.mnemonic == "call" and ops and ops[0].type == X86_OP_MEM and ops[0].mem.base in tblreg and ops[0].mem.index == 0:
            CB.append((ops[0].mem.disp // 4, ins.address))
        elif ops and ops[0].type == X86_OP_REG and ops[0].reg in tblreg and ins.mnemonic in ("mov", "lea", "xor", "pop"):
            tblreg.pop(ops[0].reg, None)
        if ins.mnemonic == "call" and ops and ops[0].type == X86_OP_IMM:
            C.append((ops[0].imm & 0xffffffff, ins.address))
        for k, op in enumerate(ops):
            t = None
            if op.type == X86_OP_MEM and op.mem.disp:
                t = op.mem.disp & 0xffffffff
            elif op.type == X86_OP_IMM and not ins.mnemonic.startswith("j") and ins.mnemonic != "call":
                t = op.imm & 0xffffffff
            if t is None:
                continue
            kl = I.klass(t)
            if kl == "iat":
                IM.append(("!".join(I.imports[t]), ins.address))
            elif kl in ("rdata", "data", "bss"):
                s = I.cstring(t) if kl != "bss" else None
                if s and op.type == X86_OP_IMM:
                    S.append((s, t, ins.address))
                elif t != TBL:
                    rw = "w" if (k == 0 and op.type == X86_OP_MEM and ins.mnemonic in ("mov", "inc", "dec", "add", "sub", "or", "and", "xor")) else "r"
                    G.append((t, rw, ins.address, op.type == X86_OP_IMM))
    return S, IM, CB, G, C


def sheet(va):
    F, cg = load()
    I = img()
    r = F.get(va)
    if r is None:
        cands = [s for s in F if s <= va <= int(F[s]["end"], 16)]
        if not cands:
            print("no function at 0x%x" % va); return
        r = F[max(cands)]
    s, e = int(r["start"], 16), int(r["end"], 16) + 1
    S, IM, CB, G, C = facts(s, e)
    g = cg.get(r["start"], {})
    print("== 0x%x %s size=%d params=%s cc=%s  callers=%s" % (s, fname(s) or r["name"], r["size"], r["params"], r["cc"],
          ",".join(g.get("callers", []))))
    for x in S:
        print("  S  %08x  0x%x %r" % (x[2], x[1], x[0][:90]))
    for x in IM:
        print("  I  %08x  %s" % (x[1], x[0]))
    for x in CB:
        print("  CB %08x  slot %02d" % (x[1], x[0]))
    gg = collections.OrderedDict()
    for t, rw, a, isimm in G:
        gg.setdefault(t, []).append(("&" if isimm else rw) + "@%x" % a)
    for t, v in gg.items():
        print("  G  0x%x %s  %s" % (t, I.klass(t), " ".join(v[:8]) + (" ..+%d" % (len(v) - 8) if len(v) > 8 else "")))
    cc = collections.OrderedDict()
    for t, a in C:
        cc.setdefault(t, []).append(a)
    print("  C  " + " ".join("%x%s" % (t, ("(" + fname(t) + ")") if fname(t) and not fname(t).startswith("FUN_") else "") for t in cc))


def main(argv):
    if argv[1] == "--all":
        F, cg = load()
        for s in sorted(F):
            r = F[s]
            if r.get("external"):
                continue
            S, IM, CB, G, C = facts(s, int(r["end"], 16) + 1)
            print("%x\t%d\t%s\t%d\t%s\t%s\t%s\t%s" % (s, r["size"], fname(s) or r["name"], len(S),
                  " | ".join(sorted(set(x[0][:40] for x in S)))[:300],
                  ",".join(sorted(set(x[0].split("!")[1] for x in IM))),
                  ",".join("%02d" % k for k in sorted(set(x[0] for x in CB))),
                  ",".join(cg.get(r["start"], {}).get("callers", []))))
        return
    for a in argv[1:]:
        sheet(int(a, 16))


if __name__ == "__main__":
    main(sys.argv)
