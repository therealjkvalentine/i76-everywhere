r"""xref_scan.py - capstone data-reference index over the pristine .text (one linear pass, cached).

    python tools\xref_scan.py 0x5fcdc0 [0x5fcdc4 ...]      references to these addresses (or ranges lo-hi)
    python tools\xref_scan.py --rebuild

Every instruction whose memory displacement or immediate falls in .rdata/.data/.bss (0x4bc000-0x669ef8) is
recorded as (site, mnemonic, operand text, access r|w|imm, size, function start). Cache: status\xrefs-9a232dcc.json.
Method: capstone 5 linear sweep of the Ghidra function bodies (functions.tsv addr/size), md5-stamped.
"""
import sys, os, json, csv
M = r"C:\Users\james\i76-map"
CACHE = os.path.join(M, "status", "xrefs-9a232dcc.json")
EXE = r"C:\Users\james\i76-uncap-lab\game\i76_pristine.exe"


def build():
    import pefile
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    from capstone.x86 import X86_OP_MEM, X86_OP_IMM
    pe = pefile.PE(EXE); base = pe.OPTIONAL_HEADER.ImageBase
    txt = [s for s in pe.sections if s.Name.startswith(b".text")][0]; code = txt.get_data(); va = base + txt.VirtualAddress
    funcs = []
    for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        funcs.append((int(r["addr"], 16), int(r["size"])))
    funcs.sort()
    md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True
    refs = {}
    for fa, fs in funcs:
        off = fa - va
        end = off + fs
        while off < end:
            try:
                ins = next(md.disasm(code[off:off + 16], va + off, count=1))
            except StopIteration:
                off += 1; continue
            for op in ins.operands:
                if op.type == X86_OP_MEM:
                    v = op.mem.disp & 0xffffffff; acc = "w" if (op.access & 2) else "r"; size = op.size
                elif op.type == X86_OP_IMM:
                    v = op.imm & 0xffffffff; acc = "imm"; size = 0
                else:
                    continue
                if 0x4bc000 <= v < 0x669ef8:
                    refs.setdefault("0x%x" % v, []).append(["0x%x" % ins.address, ins.mnemonic, ins.op_str, acc, size, "0x%x" % fa])
            off += ins.size
    json.dump({"md5": "9a232dcc2c164648cff20c414c1f9698", "refs": refs}, open(CACHE, "w"))
    return refs


DISP_CACHE = os.path.join(M, "status", "disprefs-9a232dcc.json")


def build_disp():
    """Register-relative displacement index: every memory operand [reg (+ idx*s) + disp] with 0x10 <= disp < 0x10000
    and no absolute base, keyed by disp -> (site, mnemonic, operands, r|w, size, function). For struct-field hunts
    (which functions touch +0x138 of *something*); the base register's identity is not resolved here."""
    import pefile
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    from capstone.x86 import X86_OP_MEM
    pe = pefile.PE(EXE); base = pe.OPTIONAL_HEADER.ImageBase
    txt = [s for s in pe.sections if s.Name.startswith(b".text")][0]; code = txt.get_data(); va = base + txt.VirtualAddress
    funcs = []
    for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="	"):
        funcs.append((int(r["addr"], 16), int(r["size"])))
    funcs.sort()
    md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True
    refs = {}
    for fa, fs in funcs:
        off = fa - va; end = off + fs
        while off < end:
            try:
                ins = next(md.disasm(code[off:off + 16], va + off, count=1))
            except StopIteration:
                off += 1; continue
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base != 0 and ins.reg_name(op.mem.base) not in ("esp", "ebp") or (op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index != 0):
                    d = op.mem.disp
                    if 0x10 <= d < 0x10000:
                        acc = "w" if (op.access & 2) else "r"
                        refs.setdefault("0x%x" % d, []).append(["0x%x" % ins.address, ins.mnemonic, ins.op_str, acc, op.size, "0x%x" % fa])
            off += ins.size
    json.dump({"md5": "9a232dcc2c164648cff20c414c1f9698", "refs": refs}, open(DISP_CACHE, "w"))
    return refs


def load():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))["refs"]
    return build()


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--rebuild":
        refs = build(); print("built", len(refs), "referenced addresses ->", CACHE); return
    if args[0] == "--disp":
        args = args[1:]
        refs = json.load(open(DISP_CACHE))["refs"] if os.path.exists(DISP_CACHE) else build_disp()
        if not args:
            print("disp index:", len(refs), "displacements"); return
    else:
        refs = load()
    for a in args:
        if "-" in a:
            lo, hi = (int(x, 16) for x in a.split("-"))
        else:
            lo = hi = int(a, 16)
        for v in range(lo, hi + 1):
            for r in refs.get("0x%x" % v, []):
                print("0x%x  %s  %-6s %-40s %s size=%s fn=%s" % (v, r[0], r[1], r[2], r[3], r[4], r[5]))


if __name__ == "__main__":
    main()
