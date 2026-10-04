#!/usr/bin/env python3
"""truthset_select.py - Task 7: select and seal status\\truthset.json (gate G6) against ghidra\\export-frozen.

    python tools\\truthset_select.py [--map C:\\Users\\james\\i76-map] [--emu-trials 6] [--seed 7] [--dry-run]

Two sealed halves, both chosen deterministically (size-quantile spread inside each stratum, no RNG in the choice;
the emulator's inputs are seeded):

  anchored (30): rows whose functions.tsv status is `anchored` (G1 names), minus import thunks (6-byte jmp stubs
    carry nothing to name), `entry` (CRT boilerplate), rows absent from the frozen export and bodies < 16 B. Strata: the 7 self-naming-literal rows + WinMain (all),
    12 BWD2 handlers, 6 shell callbacks, 4 heap creators, each spread over the stratum's size range.
  string-less (30): functions.csv string_refs == 0, status `auto`, not thunk, size >= 20, decompiles, no CALLIND.
    Strata: 10 pure leaves (no callees, no (ram,..) varnode in .pcode, Unicorn confirms no data-section touch),
    8 leaves that touch globals, 12 non-leaves (60-1500 B). Each carries a sealed fact tuple:
      callee set (export-frozen callgraph.json call_sites: internal targets + import names),
      globals written / read (capstone 5 over the body [start,end]: memory operands whose disp32 is in
        .rdata/.data/BSS; each with gate A class, site and instruction),
      rate class placeholder (census, Task 10 item 004), ledger key placeholder (Task 10 item 005),
      emulated input->output table for pure leaves (tools\\emulate_leaf.py, gate E; oracle matches listed, a
        table without an oracle is data).

Outputs (all under status\\): truthset.json (SEALED: names and tuples; drafters must never read it),
truthset-blind.json (addresses, half, size only: the drafter-facing list), truthset-exclude.txt (the 60 plus every
direct caller, one hex address per line; ApplyMap.py skips these rows, G6). Every address is class `text`.
"""
import os, sys, json, csv, re, argparse, hashlib, subprocess, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_tables import Image, hx
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_MEM

PRISTINE_MD5 = "9a232dcc2c164648cff20c414c1f9698"
FUNC_COLS = ["addr", "size", "name", "status", "conv", "conv_evidence", "hookable", "duplicate_of", "tu", "subsystem", "evidence_ids"]


def read_tsv(path, cols):
    rows = []
    for line in open(path, encoding="utf-8"):
        if line.startswith("#"):
            continue
        line = line.rstrip("\r\n")
        if not line:
            continue
        p = line.split("\t")
        if p[0] == cols[0]:
            continue
        p += [""] * (len(cols) - len(p))
        rows.append(dict(zip(cols, p[:len(cols)])))
    return rows


def quantile_pick(items, k):
    """k items spread over the size-sorted list (first, last and evenly spaced ranks between); deterministic."""
    items = sorted(items, key=lambda x: (x["size"], x["addr"]))
    n = len(items)
    if k >= n:
        return items
    if k == 1:
        return [items[n // 2]]
    idx = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    # collisions (tiny strata) fill from the neighbours
    j = 0
    while len(idx) < k and j < n:
        if j not in idx:
            idx.append(j)
        j += 1
    return [items[i] for i in sorted(idx)]


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def name_tokens(name):
    """Scoring tokens for an anchored name (blind_eval.py uses the same function)."""
    parts = re.split(r"[_\W]+", name)
    toks = set()
    for p in parts:
        if re.fullmatch(r"[0-9a-f]{5,8}", p) or p.isdigit():
            continue   # an address suffix or a plain number carries no meaning
        # camelCase split, digits stay attached to the preceding letters (bwd2, cb10, vec3)
        for q in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+[0-9]*|[A-Z]+[0-9]*|[0-9]+", p):
            if not q.isdigit():
                toks.add(q.lower())
    return sorted(toks)


class Ctx:
    def __init__(self, M):
        self.M = M
        self.img = Image(os.path.join(M, "ghidra", "i76_ref.exe"))
        assert self.img.md5 == PRISTINE_MD5, self.img.md5
        F = os.path.join(M, "ghidra", "export-frozen")
        self.F = F
        self.fj = {int(r["addr"], 16): r for r in json.load(open(os.path.join(F, "functions.json"), encoding="utf-8"))}
        self.cg = json.load(open(os.path.join(F, "callgraph.json"), encoding="utf-8"))
        self.fc = {int(r["address"], 16): r for r in csv.DictReader(open(os.path.join(F, "functions.csv"), newline="", encoding="utf-8"))}
        self.ft = {int(r["addr"], 16): r for r in read_tsv(os.path.join(M, "symbols", "functions.tsv"), FUNC_COLS)}
        self.md = Cs(CS_ARCH_X86, CS_MODE_32); self.md.detail = True
        self.manifest_md5 = hashlib.md5(open(os.path.join(F, "MANIFEST.md5"), "rb").read()).hexdigest()

    def pcode(self, a):
        return open(os.path.join(self.F, "functions", "%08x.pcode" % a), encoding="utf-8", errors="replace").read()

    def callees(self, a):
        e = self.cg["%08x" % a]
        internal = sorted({hx(int(t, 16)) for _, t, _ in e["call_sites"] if not t.startswith("EXTERNAL")})
        imports = sorted({n for _, t, n in e["call_sites"] if t.startswith("EXTERNAL")})
        return {"internal": internal, "imports": imports, "n_sites": len(e["call_sites"]),
                "method": "export-frozen callgraph.json call_sites (Ghidra flow refs; thunk targets as the thunk)"}

    def callers(self, a):
        return sorted(hx(int(c, 16)) for c in self.cg["%08x" % a]["callers"])

    def globals_rw(self, a):
        """disp32 memory operands into .rdata/.data/BSS over the body; split by capstone access flags."""
        info = self.fj[a]
        start, end = int(info["start"], 16), int(info["end"], 16)
        off = self.img.va2off(start)
        code = self.img.data[off:off + (end - start + 1)]
        written, read = [], []
        for ins in self.md.disasm(code, start):
            for op in ins.operands:
                if op.type != X86_OP_MEM:
                    continue
                d = op.mem.disp & 0xffffffff
                k = self.img.klass(d)
                if k not in ("init", "bss", "iat"):
                    continue
                rec = {"addr": hx(d), "class": k, "site": hx(ins.address), "insn": "%s %s" % (ins.mnemonic, ins.op_str),
                       "width": op.size, "indexed": bool(op.mem.base or op.mem.index)}
                acc = op.access
                # capstone: CS_AC_READ=1, CS_AC_WRITE=2
                if acc & 2:
                    written.append(rec)
                if acc & 1:
                    read.append(rec)
        return {"written": written, "read": read,
                "method": "capstone 5.0.7 linear disassembly over [start,end] of the Ghidra body (ranges=%d), memory operands with "
                          "disp32 in .rdata/.data/BSS/IAT, access from capstone operand flags" % info["ranges"]}


def build(M, emu_trials, seed, dry):
    C = Ctx(M)
    funnel = []
    # ---------------- anchored half ----------------
    anch = [r for a, r in C.ft.items() if r["status"] == "anchored"]
    funnel.append(("anchored rows in functions.tsv", len(anch)))
    pool = [r for r in anch if not r["name"].startswith("thunk_") and r["name"] != "entry"]
    funnel.append(("minus import thunks and entry", len(pool)))
    pool = [r for r in pool if int(r["addr"], 16) in C.fj]
    funnel.append(("minus rows absent from export-frozen (functions ApplyMap created after the freeze)", len(pool)))
    pool = [r for r in pool if int(r["size"]) >= 16]
    funnel.append(("minus bodies < 16 B (a ret / jmp stub carries nothing to name)", len(pool)))
    items = []
    for r in pool:
        a = int(r["addr"], 16)
        items.append({"addr": a, "size": int(r["size"]), "name": r["name"], "subsystem": r["subsystem"],
                      "evidence_ids": r["evidence_ids"]})
    strata = collections.OrderedDict()
    strata["self-named+WinMain"] = [x for x in items if x["subsystem"] not in ("bwd2", "shell", "heap")]
    strata["bwd2"] = [x for x in items if x["subsystem"] == "bwd2"]
    strata["shell"] = [x for x in items if x["subsystem"] == "shell"]
    strata["heap"] = [x for x in items if x["subsystem"] == "heap"]
    want = {"self-named+WinMain": 8, "bwd2": 12, "shell": 6, "heap": 4}
    anchored = []
    for k, lst in strata.items():
        pick = quantile_pick(lst, want[k])
        funnel.append(("stratum %s: %d available -> %d picked (size quantiles)" % (k, len(lst), len(pick)), len(pick)))
        for x in pick:
            x["stratum"] = k
        anchored += pick
    assert len(anchored) == 30, len(anchored)
    for x in anchored:
        a = x["addr"]
        x["addr"] = hx(a); x["class"] = "text"; x["half"] = "anchored"; x["status"] = "anchored"
        x["callers"] = C.callers(a); x["callees"] = C.callees(a)
        x["tokens"] = name_tokens(x["name"])
        x["prototype_auto"] = C.fj[a]["prototype"]
        x["sha256"] = sha({k: v for k, v in x.items() if k != "sha256"})
    # ---------------- string-less half ----------------
    cand = []
    n0 = 0
    for a, r in C.fc.items():
        n0 += 1
        if int(r["string_refs"]) > 0 or r["is_thunk"] == "true":
            continue
        row = C.ft.get(a)
        if row is None or row["status"] != "auto":
            continue
        sz = int(r["size"])
        if sz < 20 or not C.fj[a]["decomp_ok"]:
            continue
        pc = C.pcode(a)
        if "CALLIND" in pc:
            continue
        e = C.cg["%08x" % a]
        cand.append({"addr": a, "size": sz, "n_callees": len(e["callees"]), "ram": pc.count("(ram, "),
                     "x87": int(r["x87_instrs"])})
    funnel.append(("functions in export-frozen", n0))
    funnel.append(("string-less, auto, not thunk, size>=20, decompiles, no CALLIND", len(cand)))
    pure_static = [c for c in cand if c["n_callees"] == 0 and c["ram"] == 0]
    leaf_glob = [c for c in cand if c["n_callees"] == 0 and c["ram"] > 0 and 40 <= c["size"] <= 800]
    nonleaf = [c for c in cand if c["n_callees"] > 0 and 60 <= c["size"] <= 1500]
    funnel.append(("pure-leaf candidates (no callees, no ram varnode)", len(pure_static)))
    funnel.append(("leaf-with-globals candidates (40-800 B)", len(leaf_glob)))
    funnel.append(("non-leaf candidates (60-1500 B)", len(nonleaf)))
    # emulate every static pure leaf; keep those the emulator confirms pure with >= 1 ok trial in some mode
    from emulate_leaf import Emu, emulate_function
    emu = Emu(C.img)
    emu_results = {}
    t0 = time.time()
    for c in pure_static:
        emu_results[c["addr"]] = emulate_function(emu, C.img, C.fj, c["addr"], emu_trials, seed)
    funnel.append(("pure leaves emulated (%.1fs)" % (time.time() - t0), len(emu_results)))
    pure_ok = [c for c in pure_static if emu_results[c["addr"]]["pure"] and any(m["ok"] > 0 for m in emu_results[c["addr"]]["modes"].values())]
    funnel.append(("emulator-confirmed pure with >= 1 ok trial", len(pure_ok)))
    picks = []
    for label, lst, k in (("pure-leaf", pure_ok, 10), ("leaf-globals", leaf_glob, 8), ("nonleaf", nonleaf, 12)):
        p = quantile_pick(lst, k)
        funnel.append(("stratum %s: %d available -> %d picked (size quantiles)" % (label, len(lst), len(p)), len(p)))
        for x in p:
            x["stratum"] = label
        picks += p
    assert len(picks) == 30, len(picks)
    stringless = []
    for c in picks:
        a = c["addr"]
        t = {"addr": hx(a), "class": "text", "half": "stringless", "stratum": c["stratum"], "size": c["size"],
             "size_method": "Ghidra FunctionManager body.getNumAddresses (export-frozen functions.json)",
             "prototype_auto": C.fj[a]["prototype"], "cc_auto": C.fj[a]["cc"], "x87_instrs": c["x87"],
             "pcode_ram_varnodes": c["ram"], "callers": C.callers(a), "callees": C.callees(a),
             "globals": C.globals_rw(a),
             "rate_class": {"class": None, "n": None, "placeholder": "census rate class with n (Task 10 item 004, captures\\004-*)"},
             "ledger_key": {"value": None, "placeholder": "(source,key,size,retaddr) from ledger.js (Task 10 item 005)"},
             "emulated_io": emu_results.get(a)}
        t["facts_method"] = "callees: export-frozen callgraph.json; globals: capstone disp32 operands (class per gate A); io: tools/emulate_leaf.py"
        t["sha256"] = sha({k: v for k, v in t.items() if k != "sha256"})
        stringless.append(t)
    # ---------------- exclusion list ----------------
    truth_addrs = [int(x["addr"], 16) for x in anchored + stringless]
    callers = set()
    for x in anchored + stringless:
        callers.update(int(c, 16) for c in x["callers"])
    exclude = sorted(set(truth_addrs) | callers)
    funnel.append(("truth-set functions", len(truth_addrs)))
    funnel.append(("distinct direct callers", len(callers - set(truth_addrs))))
    funnel.append(("exclusion list (functions + callers)", len(exclude)))
    out = {"sealed": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": "t7-truth-set", "exe_md5": C.img.md5,
           "export": "ghidra/export-frozen", "export_manifest_md5": C.manifest_md5,
           "selection": "deterministic size-quantile spread per stratum; emulator seed %d, %d trials/mode" % (seed, emu_trials),
           "funnel": [{"step": s, "n": n} for s, n in funnel],
           "scoring": {"anchored": "blind_eval.py: exact = normalised name equal; semantic = shared scoring token (len>=4, not a stopword) "
                                   "or exact; subsystem = proposal subsystem equals the row's; floor (G6) 80%% Phase 1 / 90%% Phase 4 on semantic",
                       "stringless": "contradictions against the tuple: claimed callee not in set, claimed written global not in set, "
                                     "leaf/pure claims against callees/purity, io_expr against the emulated table (>4 ulp); halt when > 1 per 4 tuples"},
           "anchored": anchored, "stringless": stringless,
           "exclude": [hx(a) for a in exclude]}
    out["sha256_entries"] = sha([x["sha256"] for x in anchored + stringless])
    if dry:
        for s, n in funnel:
            print("%-75s %d" % (s, n))
        return out
    S = os.path.join(M, "status")
    p = os.path.join(S, "truthset.json")
    with open(p + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    os.replace(p + ".tmp", p)
    back = json.load(open(p, encoding="utf-8"))
    assert len(back["anchored"]) == 30 and len(back["stringless"]) == 30 and back["sha256_entries"] == out["sha256_entries"]
    # blind list (no names, no tuples)
    blind = {"note": "drafter-facing list; names and fact tuples are sealed in truthset.json (never read it while drafting)",
             "export": "ghidra/export-frozen", "functions": [{"addr": x["addr"], "half": x["half"], "size": x["size"],
                                                              "task": "name" if x["half"] == "anchored" else "facts"}
                                                             for x in anchored + stringless]}
    pb = os.path.join(S, "truthset-blind.json")
    with open(pb + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(blind, fh, indent=1)
    os.replace(pb + ".tmp", pb)
    assert len(json.load(open(pb, encoding="utf-8"))["functions"]) == 60
    # exclusion list: one hex address per line (ApplyMap.py int(line,16)); comments on their own lines only
    px = os.path.join(S, "truthset-exclude.txt")
    with open(px + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# truthset-exclude.txt - G6: the 60 truth-set functions and their direct callers. ApplyMap.py never applies\n")
        fh.write("# a functions.tsv row at these addresses (names must not enter the Ghidra project or the regenerated corpus).\n")
        fh.write("# Written by tools/truthset_select.py (t7-truth-set); one hex .text address per line; %d entries.\n" % len(exclude))
        for a in exclude:
            fh.write("0x%x\n" % a)
    os.replace(px + ".tmp", px)
    back_x = [int(l.strip(), 16) for l in open(px, encoding="utf-8") if l.strip() and not l.startswith("#")]
    assert back_x == exclude, (len(back_x), len(exclude))
    for s, n in funnel:
        print("%-75s %d" % (s, n))
    print("wrote %s (sha256 of file %s)" % (p, hashlib.sha256(open(p, "rb").read()).hexdigest()))
    print("wrote %s (60 rows) and %s (%d addresses, read back equal)" % (pb, px, len(back_x)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=r"C:\Users\james\i76-map")
    ap.add_argument("--emu-trials", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    build(a.map, a.emu_trials, a.seed, a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
