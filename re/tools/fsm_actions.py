r"""fsm_actions.py - join the mission-script (FSM) action names to their handlers, statically.

    python tools\fsm_actions.py [--out foldin\fsm-actions.tsv]

1. The name matcher 0x410a10 is an unrolled string compare: each block loads a name literal (`mov esi, <str>`) and, on
   a match, returns a fixed index (`mov eax, <imm>` ... `ret`). Parsing the blocks in order gives name -> index.
2. fsm_ActionDispatch 0x412ce0 switches on the index through the jump table at 0x4144e4 (96 dword targets): index ->
   case address. (Verified here by reading the `jmp dword ptr [reg*4 + table]` in the dispatcher.)
3. In each case block, the first direct `call` before the block's closing `jmp`/`ret` is taken as the handler, and the
   case's own code range is recorded, so an inline action (no call) is visible as such.
Method: capstone over the pristine file (md5 9a232dcc); every row carries the instruction addresses it came from.
"""
import argparse, csv, os, re, struct, sys
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

M = r"C:\Users\james\i76-map"
EXE = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"
MATCHER, DISPATCH = 0x410a10, 0x412ce0
# shared helpers every case calls before its real handler: the argument/object resolver, the sim clock, _ftol
HELPERS = {0x45f0f0, 0x49c7e0, 0x4ba090}

pe = pefile.PE(EXE)
BASE = pe.OPTIONAL_HEADER.ImageBase
md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True


def rd(va, n):
    off = pe.get_offset_from_rva(va - BASE)
    return pe.__data__[off:off + n]


def cstr(va):
    return rd(va, 64).split(b"\0")[0].decode("latin1")


def disasm(lo, hi):
    return list(md.disasm(rd(lo, hi - lo), lo))


def fsize(addr):
    for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if int(r["addr"], 16) == addr:
            return int(r["size"])
    raise SystemExit("no function row at 0x%x" % addr)


def names():
    names_map = {}
    for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        names_map[int(r["addr"], 16)] = (r["name"], r["status"])
    return names_map


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"foldin\fsm-actions.tsv")
    a = ap.parse_args()
    ins = disasm(MATCHER, MATCHER + fsize(MATCHER))
    # 1. name -> index
    pairs, cur, cur_site = [], None, None
    for i in ins:
        if i.mnemonic == "mov" and len(i.operands) == 2 and i.operands[1].type == X86_OP_IMM and i.op_str.startswith("esi,"):
            v = i.operands[1].imm & 0xffffffff
            if 0x4bc000 <= v < 0x501800:
                cur, cur_site = cstr(v), (i.address, v)
        elif i.mnemonic == "mov" and i.op_str.startswith("eax, ") and len(i.operands) == 2 and i.operands[1].type == X86_OP_IMM and cur is not None:
            pairs.append((cur, i.operands[1].imm, cur_site[1], cur_site[0], i.address))
            cur = None
    # the first name is compared before any `mov esi` in some compilers: report what was found
    # 2. jump table in the dispatcher
    dins = disasm(DISPATCH, DISPATCH + fsize(DISPATCH))
    table = None
    for i in dins:
        if i.mnemonic == "jmp" and i.operands and i.operands[0].type == X86_OP_MEM and i.operands[0].mem.scale == 4 and i.operands[0].mem.disp:
            table = (i.address, i.operands[0].mem.disp & 0xffffffff, i.operands[0].mem.index)
            break
    if not table:
        raise SystemExit("no jump table found in the dispatcher")
    # the index register may be biased (sub eax, K before the jmp): find the nearest cmp bound and any sub before the jmp
    bias, bound = 0, None
    for i in dins:
        if i.address >= table[0]:
            break
        if i.mnemonic in ("sub", "add", "dec") and len(i.operands) == 2 and i.operands[1].type == X86_OP_IMM:
            bias = (i.operands[1].imm if i.mnemonic == "sub" else -i.operands[1].imm)
        if i.mnemonic == "cmp" and len(i.operands) == 2 and i.operands[1].type == X86_OP_IMM:
            bound = i.operands[1].imm
    count = (bound + 1) if bound is not None else 96
    targets = [struct.unpack("<I", rd(table[1] + 4 * k, 4))[0] for k in range(count)]
    # 3. handler per case: first direct call inside the case block (block ends at the next case start / jmp / ret)
    starts = sorted(set(targets))
    nm = names()
    rows = []
    for name, idx, str_va, str_site, idx_site in pairs:
        k = idx - bias
        if not (0 <= k < len(targets)):
            rows.append({"name": name, "index": idx, "case": "", "handler": "", "handler_name": "", "note": "index outside the table (bias %d, count %d)" % (bias, len(targets)),
                         "string": "0x%x" % str_va, "string_site": "0x%x" % str_site, "index_site": "0x%x" % idx_site})
            continue
        case = targets[k]
        nxt = min([s for s in starts if s > case] + [DISPATCH + fsize(DISPATCH)])
        handler, calls, note, sites = "", [], "", {}
        for i in disasm(case, nxt):
            if i.mnemonic == "call" and i.operands and i.operands[0].type == X86_OP_IMM:
                calls.append(i.operands[0].imm & 0xffffffff)
                sites[i.operands[0].imm & 0xffffffff] = i.address
            if i.mnemonic in ("jmp", "ret") and i.address > case:
                break
        real = [c for c in calls if c not in HELPERS]
        if real:
            handler = real[-1] if len(set(real)) == 1 else real[0]
            note = "calls: " + ",".join("0x%x" % c for c in calls)
        elif calls:
            note = "helpers only: " + ",".join("0x%x" % c for c in calls)
        else:
            note = "inline case (no direct call) 0x%x-0x%x" % (case, nxt)
        hn = nm.get(handler, ("", ""))
        rows.append({"name": name, "index": idx, "case": "0x%x" % case, "handler": ("0x%x" % handler) if handler else "",
                     "handler_name": "%s [%s]" % hn if handler else "", "note": note, "call_site": ("0x%x" % sites[handler]) if handler else "",
                     "string": "0x%x" % str_va, "string_site": "0x%x" % str_site, "index_site": "0x%x" % idx_site})
    out = os.path.join(M, a.out)
    cols = ["name", "index", "case", "handler", "handler_name", "call_site", "note", "string", "string_site", "index_site"]
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write("# fsm-actions.tsv - mission-script action name -> index (matcher 0x410a10) -> case (jump table 0x%x in 0x412ce0, bias %d, %d entries) -> handler; tools/fsm_actions.py, capstone over md5 9a232dcc\n" % (table[1], bias, len(targets)))
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t"); w.writeheader()
        for r in rows:
            w.writerow(r)
    distinct = len(set(r["handler"] for r in rows if r["handler"]))
    print("names %d, jump table 0x%x (%d entries, bias %d), handlers %d distinct, inline %d" % (
        len(rows), table[1], len(targets), bias, distinct, sum(1 for r in rows if "inline" in r["note"])))


if __name__ == "__main__":
    main()
