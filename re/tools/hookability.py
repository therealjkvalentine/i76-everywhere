#!/usr/bin/env python3
"""hookability.py - per-function hookability (Task 2) and symbols/functions.tsv (status auto for all rows).

Inputs (all under the map repository):
  ghidra/export/functions.json   Ghidra structural inventory (DumpAll.py)
  ghidra/export/flows.csv        every Ghidra flow reference whose destination is in .text (DumpAll.py)
  ghidra/i76_ref.exe             the pristine image (md5 9a232dcc2c164648cff20c414c1f9698), bytes via pefile

Rule (method doc section 7, Task 2). A function is hookable when ALL of:
  1. size >= 8 bytes (Ghidra body size)
  2. no branch target (from ANY function, Ghidra flow refs UNION capstone direct-branch targets) lands strictly
     inside its first 5 bytes, i.e. in [entry+1, entry+4]
  3. it is not a thunk (Ghidra isThunk), not an EH funclet (name Unwind@* or an 11-byte body in
     0x4bba40-0x4bbe40), not an EH stub (`B8 imm32 ; E9 rel32` = mov eax,FuncInfo; jmp __CxxFrameHandler, 10 B)
  4. the instructions covering the first 5 bytes decode cleanly, stay inside the body, and are relocatable:
     no rel8/rel32 branch (jmp/jcc/call/loop/jecxz/jcxz) and no RIP-relative operand (none exist on x86-32,
     checked anyway)
Every address in the outputs is class `init` (.text, VA; file offset = VA - 0x400c00).  Counts carry their
method in the header lines of the TSVs and in the printed funnel (H4).

Outputs: symbols/functions.tsv, symbols/hookability.tsv, and a funnel printed to stdout.
"""
import argparse, csv, json, os, sys, collections
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_GRP_JUMP, CS_GRP_CALL, CS_GRP_BRANCH_RELATIVE
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_LO, TEXT_HI = 0x401000, 0x4bbe56          # .text VA range (end exclusive)
IMG_LO, IMG_HI = 0x400000, 0x66b000
FUNCLET_LO, FUNCLET_HI = 0x4bba40, 0x4bbe40 + 11
DUP_PAIRS = [(0x48a870, 0x48c320), (0x487480, 0x488e40), (0x489be0, 0x48b690), (0x486860, 0x488220)]


def load_image(exe):
    pe = pefile.PE(exe)
    data = open(exe, "rb").read()
    secs = []
    for s in pe.sections:
        va = pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress
        secs.append((va, va + max(s.Misc_VirtualSize, s.SizeOfRawData), s.PointerToRawData, s.SizeOfRawData))

    def read(va, n):
        for lo, hi, raw, rawsz in secs:
            if lo <= va < hi:
                off = raw + (va - lo)
                b = data[off:off + n]
                if va - lo + n > rawsz:  # beyond raw: zero fill
                    b = b + b"\0" * (n - len(b))
                return b
        return b""
    return read


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default=os.path.join(ROOT, "ghidra", "export"))
    ap.add_argument("--exe", default=os.path.join(ROOT, "ghidra", "i76_ref.exe"))
    ap.add_argument("--out", default=os.path.join(ROOT, "symbols", "functions.tsv"))
    ap.add_argument("--detail", default=os.path.join(ROOT, "symbols", "hookability.tsv"))
    a = ap.parse_args()

    funcs = json.load(open(os.path.join(a.export, "functions.json")))
    funcs.sort(key=lambda r: int(r["addr"], 16))
    read = load_image(a.exe)
    md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True
    md_skip = Cs(CS_ARCH_X86, CS_MODE_32); md_skip.detail = True; md_skip.skipdata = True

    # --- branch targets, method 1: Ghidra flow references (flows.csv) ---
    ghidra_targets = collections.defaultdict(set)
    n_flows = 0
    with open(os.path.join(a.export, "flows.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            n_flows += 1
            ghidra_targets[int(row["to"], 16)].add(int(row["from"], 16))
    # --- branch targets, method 2: capstone linear sweep over every function body (direct imm targets) ---
    cap_targets = collections.defaultdict(set)
    n_cap_insn = 0
    for r in funcs:
        if r.get("external"):
            continue
        lo, hi = int(r["start"], 16), int(r["end"], 16) + 1
        code = read(lo, hi - lo)
        for ins in md_skip.disasm(code, lo):
            n_cap_insn += 1
            if ins.id == 0:
                continue
            grp = set(ins.groups)
            if (CS_GRP_JUMP in grp or CS_GRP_CALL in grp) and ins.operands and ins.operands[0].type == X86_OP_IMM:
                t = ins.operands[0].imm & 0xffffffff
                if TEXT_LO <= t < TEXT_HI:
                    cap_targets[t].add(ins.address)
    all_targets = set(ghidra_targets) | set(cap_targets)
    only_g = len(set(ghidra_targets) - set(cap_targets)); only_c = len(set(cap_targets) - set(ghidra_targets))

    funnel = collections.OrderedDict()
    funnel["functions"] = len(funcs)
    rows = []; detail = []
    reasons = collections.Counter()
    for r in funcs:
        ea = int(r["addr"], 16); size = int(r["size"])
        why = []
        first5 = read(ea, 8)
        if r.get("external"):
            why.append("external")
        if size < 8:
            why.append("size<8")
        if r.get("thunk"):
            why.append("thunk")
        if r["name"].startswith("Unwind@") or (size == 11 and FUNCLET_LO <= ea < FUNCLET_HI):
            why.append("eh-funclet")
        if size == 10 and first5[0:1] == b"\xb8" and first5[5:6] == b"\xe9":
            why.append("eh-stub")
        hits = sorted(t for t in all_targets if ea < t < ea + 5)
        if hits:
            why.append("branch-target-in-prologue:" + "/".join("%x" % t for t in hits))
        # relocatability of the instructions covering the first 5 bytes
        insns = []; covered = 0; ok = True; note = ""
        code = read(ea, min(size, 32)) if size > 0 else b""
        for ins in md.disasm(code, ea):
            insns.append("%s %s" % (ins.mnemonic, ins.op_str))
            grp = set(ins.groups)
            if CS_GRP_BRANCH_RELATIVE in grp or ((CS_GRP_JUMP in grp or CS_GRP_CALL in grp) and ins.operands and ins.operands[0].type == X86_OP_IMM):
                ok = False; note = "rel-branch@%x" % ins.address
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    ok = False; note = "rip-relative@%x" % ins.address
            covered += ins.size
            if covered >= 5:
                break
        if covered < 5:
            ok = False; note = "undecodable-prologue(covered=%d)" % covered
        elif covered > size:
            ok = False; note = "prologue-exceeds-body(%d>%d)" % (covered, size)
        if not ok:
            why.append("not-relocatable:" + note)
        for w in why:
            reasons[w.split(":")[0]] += 1
        hookable = not why
        detail.append((ea, size, r["name"], "yes" if hookable else "no", ";".join(why), covered, " | ".join(insns[:3])))
        rows.append((ea, size, r["name"], r.get("cc") or "unknown", hookable))
    funnel["after size>=8"] = sum(1 for r in funcs if int(r["size"]) >= 8)
    funnel["after not thunk/funclet/eh-stub"] = sum(1 for d in detail if not any(k in d[4] for k in ("thunk", "eh-funclet", "eh-stub", "external")) and d[1] >= 8)
    funnel["after no branch target in first 5 B"] = sum(1 for d in detail if d[1] >= 8 and not any(k in d[4] for k in ("thunk", "eh-funclet", "eh-stub", "external", "branch-target")))
    funnel["after relocatable prologue (hookable)"] = sum(1 for d in detail if d[3] == "yes")

    # --- duplicate pairs: identical instruction streams modulo image-absolute operands and branch displacements ---
    by_addr = {int(r["addr"], 16): r for r in funcs}
    dup = {}
    dup_report = []

    def norm(ea, size):
        out = []
        for ins in md.disasm(read(ea, size), ea):
            ops = []
            grp = set(ins.groups)
            for op in ins.operands:
                if op.type == X86_OP_IMM:
                    v = op.imm & 0xffffffff
                    if (CS_GRP_JUMP in grp or CS_GRP_CALL in grp):
                        ops.append("REL%+d" % (v - ea) if ea <= v < ea + size else "IMG")
                    elif IMG_LO <= v < IMG_HI:
                        ops.append("IMG")
                    else:
                        ops.append("imm%x" % v)
                elif op.type == X86_OP_MEM:
                    d = op.mem.disp & 0xffffffff
                    ops.append("mem(b=%d,i=%d,s=%d,d=%s)" % (op.mem.base, op.mem.index, op.mem.scale,
                               "IMG" if IMG_LO <= d < IMG_HI else "%x" % d))
                else:
                    ops.append("reg%d" % op.reg)
            out.append((ins.mnemonic, tuple(ops), ins.size))
        return out
    dup_rows = []
    for lo, hi in DUP_PAIRS:
        ra, rb = by_addr.get(lo), by_addr.get(hi)
        if ra is None or rb is None:
            dup_report.append("%x/%x: missing function (%s/%s)" % (lo, hi, ra is not None, rb is not None)); continue
        sa, sb = int(ra["size"]), int(rb["size"])
        na, nb = norm(lo, sa), norm(hi, sb)
        same_raw = read(lo, sa) == read(hi, sb)
        diffs = []
        ia, ib = list(md.disasm(read(lo, sa), lo)), list(md.disasm(read(hi, sb), hi))
        for (x, y, p, q) in zip(na, nb, ia, ib):
            if x != y:
                diffs.append("%x:%s %s<>%x:%s %s" % (p.address, p.mnemonic, p.op_str, q.address, q.mnemonic, q.op_str))
        ndiff = len(diffs) + abs(len(na) - len(nb))
        verdict = "identical-modulo-relocations" if (sa == sb and ndiff == 0) else "near-duplicate(%d insn diffs)" % ndiff
        dup_report.append("%x(size %d)/%x(size %d): raw-identical=%s insns=%d/%d %s %s" % (lo, sa, hi, sb, same_raw, len(na), len(nb), verdict, "; ".join(diffs)))
        dup_rows.append((lo, hi, sa, sb, len(na), len(nb), verdict, "; ".join(diffs)))
        if sa == sb and ndiff == 0:
            dup[lo] = hi; dup[hi] = lo
    dpath = os.path.join(os.path.dirname(a.out), "duplicates.tsv")
    with open(dpath, "w", newline="\n") as fh:
        fh.write("# duplicates.tsv - the four H6 pairs compared by capstone instruction stream (tools/hookability.py). addr class: init.\n")
        fh.write("# 'identical-modulo-relocations' = same size and every instruction equal after replacing image-absolute imm/disp (0x400000-0x66b000) and branch displacements; only such pairs get duplicate_of in functions.tsv.\n")
        fh.write("a\tb\tsize_a\tsize_b\tinsns_a\tinsns_b\tverdict\tinstruction_diffs\n")
        for r in dup_rows:
            fh.write("0x%06x\t0x%06x\t%d\t%d\t%d\t%d\t%s\t%s\n" % r)

    # --- write symbols/functions.tsv ---
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="\n") as fh:
        fh.write("# functions.tsv - generated by tools/hookability.py from ghidra/export (Task 2). addr class: init (.text VA; file = VA - 0x400c00).\n")
        fh.write("# size: Ghidra function body bytes (method: FunctionManager body.getNumAddresses). status auto for every row; conv from Decompiler Parameter ID (gate K: auto, no claim).\n")
        fh.write("# hookable: yes/no per the Task 2 rule (size>=8, no branch target in [entry+1,entry+4] from Ghidra flows UNION capstone, not thunk/funclet/EH stub, relocatable first 5 B); reasons in hookability.tsv.\n")
        fh.write("# duplicate_of: symmetric, only for pairs whose instruction streams are identical modulo image-absolute operands and branch displacements (see hookability.py, DUP_PAIRS).\n")
        fh.write("addr\tsize\tname\tstatus\tconv\tconv_evidence\thookable\tduplicate_of\ttu\tsubsystem\tevidence_ids\n")
        for ea, size, name, cc, hookable in rows:
            fh.write("0x%06x\t%d\t%s\tauto\t%s\tauto:paramid\t%s\t%s\t\t\t\n" % (ea, size, name, cc, "yes" if hookable else "no", ("0x%06x" % dup[ea]) if ea in dup else ""))
    with open(a.detail, "w", newline="\n") as fh:
        fh.write("# hookability.tsv - reasons per function (tools/hookability.py). addr class: init. prologue_covered = bytes of the decoded instructions covering the first 5 B.\n")
        fh.write("addr\tsize\tname\thookable\treasons\tprologue_covered\tfirst_insns\n")
        for d in detail:
            fh.write("0x%06x\t%d\t%s\t%s\t%s\t%d\t%s\n" % d)
    # read back
    n_rows = sum(1 for l in open(a.out) if not l.startswith("#")) - 1
    n_hook = sum(1 for l in open(a.out) if not l.startswith("#") and l.split("\t")[6] == "yes")

    print("hookability funnel (method: functions.json + flows.csv + capstone over i76_ref.exe):")
    for k, v in funnel.items():
        print("  %-42s %d" % (k, v))
    print("  reasons (a function may carry several):", dict(reasons))
    print("  branch-target sets: ghidra flow refs=%d rows -> %d distinct targets; capstone %d insns -> %d targets; only-ghidra=%d only-capstone=%d"
          % (n_flows, len(ghidra_targets), n_cap_insn, len(cap_targets), only_g, only_c))
    # H4 control for the prologue predicate: the same test over a wider window must be non-empty if the target set is sound
    ctrl5 = sum(1 for r in funcs if any(int(r["addr"], 16) < t < int(r["addr"], 16) + 5 for t in all_targets))
    ctrl16 = sum(1 for r in funcs if any(int(r["addr"], 16) + 5 <= t < int(r["addr"], 16) + 16 for t in all_targets))
    print("  prologue-target control: functions with a target in [entry+1,entry+4]=%d; in [entry+5,entry+15]=%d (non-zero proves the target set covers intra-function jumps)" % (ctrl5, ctrl16))
    # EH stubs by byte pattern (mov eax,imm32; jmp rel32 -> __CxxFrameHandler thunk 0x4ba304), and whether any is a function entry
    stubs = []
    for va in range(TEXT_LO, TEXT_HI - 10):
        b = read(va, 10)
        if b and b[0] == 0xb8 and b[5] == 0xe9 and ((va + 10 + int.from_bytes(b[6:10], "little", signed=True)) & 0xffffffff) == 0x4ba304:
            stubs.append(va)
    print("  EH stubs by byte scan (B8 imm32 E9 rel32 -> 0x4ba304): %d sites, %d are function entries, range %x-%x"
          % (len(stubs), sum(1 for s in stubs if s in by_addr), min(stubs) if stubs else 0, max(stubs) if stubs else 0))
    print("  duplicate pairs:")
    for l in dup_report:
        print("    " + l)
    print("  wrote %s: %d rows, %d hookable (read back); %s" % (a.out, n_rows, n_hook, a.detail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
