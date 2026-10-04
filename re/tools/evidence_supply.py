#!/usr/bin/env python3
r"""evidence_supply.py (Task 5, Phase 0) - per-function inventory of the statically available
evidence kinds and the bytes-weighted evidence-supply histogram (status\evidence_supply.json).

Kinds (gate G2 vocabulary; every count carries its method):
  primary   string-xref        distinct literals referenced (capstone imm32 sites, symbols\strings.tsv; Ghidra count kept beside)
            import-callee      distinct IAT slots called/loaded (capstone, symbols\imports.tsv; callgraph EXTERNAL count beside)
            table-entry        membership in a named table (symbols\tables.tsv: bwd2-desc, dispatch, stack-slot-table)
                               and, separately, in generic code-pointer runs (>= 2 consecutive code pointers in .data/.rdata)
            unique-constant    capstone immediates >= 0x100 outside the image occurring at <= 3 .text sites (the G2 rule);
                               the pcode-const view is computed beside it as a cross-check, never as the count
            emulated-io        availability only: pure leaf = no callees (callgraph.json) and no data-section varnode in .pcode
  secondary eh-frame           owner of a C++ EH frame (tools\eh_decode.py)
            tu-neighbourhood   symbols\modules.tsv neighbourhood with >= 1 other function carrying a primary kind
            struct-access      >= 1 [reg+disp] operand with 4 <= disp, disp not an image address (capstone)
  (verified-callee and census are process/dynamic kinds; not statically available on day 4 and not counted.)

Histogram variants: strict (named tables only; unique constants only from the curated oracle list) and loose (generic runs
and any unique constant count).  supported-eligible = >= 2 primary kinds, or 1 primary + >= 1 secondary (G2).
The provisional Phase 1 exit value is derived from the strict variant (rule stated in the JSON).

Usage: python tools\evidence_supply.py [--exe PATH] [--export DIR] [--out status\evidence_supply.json]
"""
import argparse
import csv
import glob
import json
import os
import re
import struct
import sys
from collections import OrderedDict, defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_tables import Image  # noqa: E402
from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # noqa: E402
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_ESP, X86_REG_EBP, X86_REG_INVALID  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_EXE = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"
EXPECTED_MD5 = "9a232dcc2c164648cff20c414c1f9698"
TEXT_BYTES = 765525
UNIQUE_MAX_SITES = 3
TU_MAX_FUNCS = 100  # a neighbourhood larger than this carries no placement information (the first cut had one of 1,699)
# curated constant-anchor oracle (method doc Task 5); 0x6cd is listed to be reported, never assigned
CURATED = OrderedDict([
    (0xbfc, "rsqrt magic (0x495000)"), (0x1a5e0, "108000"), (54000, "54000"), (0xe14, "0xe14"), (0x10c, "VFS source stride"),
    (0x2e47454f, "'OEG.'"), (0x32445742, "'BWD2'"), (2029, "hash buckets 2029"), (109, "hash buckets 109 (< 0x100: fails the imm rule)"),
    (0xaab, "0xaab"), (0x6cd, "0x6cd: 7 sites, must not be assigned")])


def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        hdr = None
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = parts
                continue
            rows.append(dict(zip(hdr, parts)))
    return rows


def enclosing(fs_sorted, va):
    lo, hi = 0, len(fs_sorted) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        a, s = fs_sorted[mid]
        if va < a:
            hi = mid - 1
        elif va >= a + s:
            lo = mid + 1
        else:
            return a
    return None


def scan_bodies(img, funcs):
    """One capstone pass over every function body: immediates, struct-access displacements."""
    cs = Cs(CS_ARCH_X86, CS_MODE_32)
    cs.detail = True
    cs.skipdata = True
    imm_sites = defaultdict(list)   # value -> [(site, func)]
    disp_sites = defaultdict(list)  # value -> [(site, func)] for [reg+disp] with disp not an image address
    struct_access = Counter()       # func -> count of [reg+disp] operands (reg != esp/ebp), 4 <= disp < image
    lo_img, hi_img = img.base, img.data_hi
    for a, s in funcs:
        off = img.va2off(a)
        if off is None:
            continue
        for ins in cs.disasm(img.data[off:off + s], a):
            if ins.id == 0:
                continue
            for op in ins.operands:
                if op.type == X86_OP_IMM:
                    v = op.imm & 0xffffffff
                    if v >= 0x100 and not (lo_img <= v < hi_img):
                        imm_sites[v].append((ins.address, a))
                elif op.type == X86_OP_MEM:
                    d = op.mem.disp & 0xffffffff
                    base = op.mem.base
                    if base not in (X86_REG_INVALID, X86_REG_ESP, X86_REG_EBP) and 4 <= d and not (lo_img <= d < hi_img):
                        struct_access[a] += 1
                    if d >= 0x100 and not (lo_img <= d < hi_img) and base != X86_REG_INVALID:
                        disp_sites[d].append((ins.address, a))
    return imm_sites, disp_sites, struct_access


PCODE_CONST = re.compile(r"\(const, 0x([0-9a-f]+), (\d+)\)")
PCODE_RAM = re.compile(r"\(ram, 0x([0-9a-f]+), (\d+)\)")


def scan_pcode(export, img):
    """pcode view: per function the set of consts >= 0x100 (non-image), and whether any data-section varnode appears."""
    consts = {}
    data_ref = {}
    for fn in glob.glob(os.path.join(export, "functions", "*.pcode")):
        a = int(os.path.basename(fn)[:8], 16)
        cset = set()
        dref = False
        with open(fn, errors="replace") as fh:
            for line in fh:
                m = re.search(r"\)\s+([A-Z_]+)\s", line) or re.search(r"---\s+([A-Z_]+)\s", line)
                op = m.group(1) if m else "?"
                if op in ("INDIRECT", "CALLOTHER"):
                    continue
                body = line.split(op, 1)[1] if m else line
                if op in ("LOAD", "STORE"):
                    body = re.sub(r"^\s*\(const, 0x[0-9a-f]+, \d+\)\s*,?", "", body, count=1)
                for v, sz in PCODE_CONST.findall(body):
                    v = int(v, 16)
                    if img.rdata_lo <= v < img.data_hi:
                        dref = True
                    elif v >= 0x100 and not (img.base <= v < img.data_hi):
                        cset.add(v)
                for v, sz in PCODE_RAM.findall(line):
                    v = int(v, 16)
                    if img.rdata_lo <= v < img.data_hi:
                        dref = True
        consts[a] = cset
        data_ref[a] = dref
    return consts, data_ref


def data_encodings(img, value):
    """Where an integer/float/double encoding of `value` sits in initialised .rdata/.data (method: byte scan, 4-aligned)."""
    hits = []
    pats = [("u32", struct.pack("<I", value & 0xffffffff))]
    try:
        pats.append(("f32", struct.pack("<f", float(value))))
        pats.append(("f64", struct.pack("<d", float(value))))
    except (OverflowError, struct.error):
        pass
    for sec in (img.rdata, img.sdata):
        lo = sec["va"]
        n = min(sec["vsize"], sec["rawsize"])
        blob = img.data[sec["raw"]:sec["raw"] + n]
        for kind, pat in pats:
            i = 0
            while True:
                i = blob.find(pat, i)
                if i < 0:
                    break
                if i % 4 == 0:
                    hits.append((kind, lo + i))
                i += 1
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--export", default=os.path.join(REPO, "ghidra", "export"))
    ap.add_argument("--out", default=os.path.join(REPO, "status", "evidence_supply.json"))
    ap.add_argument("--per-function", default=os.path.join(REPO, "status", "tasks", "t5-evidence-supply.per-function.tsv"))
    ap.add_argument("--eh-json", default=os.path.join(REPO, "status", "tasks", "t5-evidence-supply.eh.json"))
    ap.add_argument("--modules", default=os.path.join(REPO, "symbols", "modules.tsv"))
    a = ap.parse_args()
    img = Image(a.exe)
    if img.md5 != EXPECTED_MD5:
        sys.exit("refusing: md5 %s != %s (H0)" % (img.md5, EXPECTED_MD5))
    funnel = OrderedDict()
    # ---- functions -------------------------------------------------------------------
    F = OrderedDict()
    with open(os.path.join(a.export, "functions.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            addr = int(r["address"], 16)
            F[addr] = OrderedDict(addr=addr, size=int(r["size"]), name=r["name"], x87=int(r["x87_instrs"]) > 0,
                                  ghidra_string_refs=int(r["string_refs"]))
    with open(os.path.join(a.export, "functions.json")) as fh:
        for rec in json.load(fh):
            addr = int(rec["addr"], 16)
            if addr in F:
                F[addr]["n_callees"] = rec["n_callees"]
                F[addr]["n_callers"] = rec["n_callers"]
    with open(os.path.join(a.export, "callgraph.json")) as fh:
        cg = json.load(fh)
    for k, v in cg.items():
        addr = int(k, 16)
        if addr in F:
            ext = set(t[2] for t in v.get("call_sites", []) if t[1].startswith("EXTERNAL"))
            F[addr]["ghidra_ext_callees"] = len(ext)
    for r in read_tsv(os.path.join(REPO, "symbols", "functions.tsv")):
        addr = int(r["addr"], 16)
        if addr in F:
            F[addr]["status"] = r["status"]
            F[addr]["name"] = r["name"]
            F[addr]["hookable"] = r["hookable"]
    for f in F.values():
        f.setdefault("status", "auto")
        f.setdefault("n_callees", 0)
        f.setdefault("ghidra_ext_callees", 0)
    funcs = sorted((f["addr"], f["size"]) for f in F.values())
    funnel["functions (ghidra/export/functions.csv)"] = len(F)
    funnel["function bytes (sum of Ghidra body sizes)"] = sum(f["size"] for f in F.values())
    funnel[".text bytes (denominator)"] = TEXT_BYTES
    # ---- strings ---------------------------------------------------------------------
    s_cap = defaultdict(set)
    s_gh = defaultdict(set)
    for r in read_tsv(os.path.join(REPO, "symbols", "strings.tsv")):
        for fn in r["imm32_functions"].split(";"):
            if fn:
                s_cap[int(fn, 16)].add(r["addr"])
        for fn in r["referencing_functions"].split(";"):
            if fn:
                s_gh[int(fn, 16)].add(r["addr"])
    # ---- imports ---------------------------------------------------------------------
    i_cap = defaultdict(set)
    for r in read_tsv(os.path.join(REPO, "symbols", "imports.tsv")):
        for col in ("functions", "thunk_caller_functions"):
            for fn in r.get(col, "").split(";"):
                if fn:
                    i_cap[int(fn, 16)].add(r["iat_slot"])
    # ---- tables ----------------------------------------------------------------------
    t_named = defaultdict(set)
    t_generic = defaultdict(set)
    for r in read_tsv(os.path.join(REPO, "symbols", "tables.tsv")):
        kind = r["kind"]
        if kind == "jumptable":
            continue
        targets = []
        if kind == "bwd2-desc":
            for item in r["targets"].split(";"):
                if "=" in item:
                    tag, rest = item.split("=", 1)
                    targets.append(int(rest.split("/")[0], 16))
        else:
            for item in r["targets"].split(";"):
                item = item.strip()
                if item.startswith("0x"):
                    try:
                        targets.append(int(item, 16))
                    except ValueError:
                        pass
        for t in targets:
            if t in F:
                if r["name"]:
                    t_named[t].add(r["name"])
                elif kind == "code-ptr-run":
                    t_generic[t].add(r["base"])
    # ---- capstone body scan --------------------------------------------------------------
    imm_sites, disp_sites, struct_access = scan_bodies(img, funcs)
    funnel["capstone imm >= 0x100 non-image: distinct values"] = len(imm_sites)
    uniq_vals = {v for v, sites in imm_sites.items() if len(sites) <= UNIQUE_MAX_SITES}
    funnel["  values at <= %d .text sites (unique-constant candidates)" % UNIQUE_MAX_SITES] = len(uniq_vals)
    u_any = defaultdict(list)
    for v in uniq_vals:
        for site, fn in imm_sites[v]:
            u_any[fn].append(v)
    # ---- pcode cross-check + purity ---------------------------------------------------------
    p_consts, p_dref = scan_pcode(a.export, img)
    p_owner = defaultdict(set)
    for fn, cset in p_consts.items():
        for v in cset:
            p_owner[v].add(fn)
    funnel["pcode consts >= 0x100 non-image: distinct values"] = len(p_owner)
    funnel["  values in <= 3 functions (pcode view)"] = sum(1 for v, s in p_owner.items() if len(s) <= 3)
    # ---- EH frames ----------------------------------------------------------------------
    eh_owner = {}
    if os.path.exists(a.eh_json):
        with open(a.eh_json) as fh:
            for fr in json.load(fh)["frames"]:
                for ps in fr["push_sites"]:
                    if ps["owner"] is not None:
                        eh_owner[ps["owner"]] = fr["funcinfo"]
    funnel["EH frame owners (eh_decode.py)"] = len(eh_owner)
    # ---- modules ----------------------------------------------------------------------
    mod_of = {}
    mod_members = defaultdict(list)
    mod_level = {}
    for r in read_tsv(a.modules):
        for fn in r["functions"].split(";"):
            if fn:
                mod_of[int(fn, 16)] = int(r["module"])
                mod_members[int(r["module"])].append(int(fn, 16))
                mod_level[int(r["module"])] = r["level"]
    funnel["modules (symbols/modules.tsv)"] = len(mod_members)
    # ---- per-function kinds ---------------------------------------------------------------
    for addr, f in F.items():
        f["strings_capstone"] = len(s_cap.get(addr, ()))
        f["strings_ghidra"] = len(s_gh.get(addr, ()))
        f["imports_capstone"] = len(i_cap.get(addr, ()))
        f["tables_named"] = sorted(t_named.get(addr, ()))
        f["tables_generic"] = len(t_generic.get(addr, ()))
        f["uconst_any"] = sorted(set(u_any.get(addr, ())))
        f["uconst_curated"] = sorted(v for v in set(u_any.get(addr, ())) if v in CURATED and v != 0x6cd)
        f["pcode_uconst"] = sorted(v for v in p_consts.get(addr, ()) if len(p_owner[v]) <= 3)
        f["eh_frame"] = addr in eh_owner
        f["struct_access"] = struct_access.get(addr, 0)
        f["leaf"] = f["n_callees"] == 0 and f["status"] != "synthetic"
        f["pure_leaf"] = f["leaf"] and not p_dref.get(addr, True)
        f["module"] = mod_of.get(addr)
    # tu-neighbourhood: another function in the module carries a primary kind (strict)
    def prim_strict(f):
        return [k for k, ok in (("string-xref", f["strings_capstone"] > 0), ("import-callee", f["imports_capstone"] > 0),
                                ("table-entry", bool(f["tables_named"])), ("unique-constant", bool(f["uconst_curated"])),
                                ("emulated-io", f["pure_leaf"])) if ok]

    def prim_loose(f):
        return [k for k, ok in (("string-xref", f["strings_capstone"] > 0), ("import-callee", f["imports_capstone"] > 0),
                                ("table-entry", bool(f["tables_named"]) or f["tables_generic"] > 0),
                                ("unique-constant", bool(f["uconst_any"])), ("emulated-io", f["pure_leaf"])) if ok]
    mod_prim = defaultdict(int)
    for f in F.values():
        if prim_strict(f):
            mod_prim[f["module"]] += 1
    funnel["tu-neighbourhood cap (functions per module for the kind to count)"] = TU_MAX_FUNCS
    funnel["functions in modules over the cap"] = sum(1 for f in F.values() if f["module"] is not None and len(mod_members[f["module"]]) > TU_MAX_FUNCS)
    for addr, f in F.items():
        others = mod_prim[f["module"]] - (1 if prim_strict(f) else 0)
        f["tu_informative"] = (f["module"] is not None and others >= 1
                               and 2 <= len(mod_members[f["module"]]) <= TU_MAX_FUNCS)
        f["primary_strict"] = prim_strict(f)
        f["primary_loose"] = prim_loose(f)
        f["secondary"] = [k for k, ok in (("eh-frame", f["eh_frame"]), ("tu-neighbourhood", f["tu_informative"]),
                                          ("struct-access", f["struct_access"] > 0)) if ok]
        for var in ("strict", "loose"):
            npri = len(f["primary_" + var])
            f["n_primary_" + var] = npri
            f["eligible_" + var] = npri >= 2 or (npri == 1 and len(f["secondary"]) >= 1)
    # ---- histograms -------------------------------------------------------------------
    def hist(var, subset):
        h = OrderedDict()
        for n in range(6):
            fl = [f for f in subset if f["n_primary_" + var] == n]
            h[str(n)] = OrderedDict(functions=len(fl), bytes=sum(f["size"] for f in fl),
                                    pct_text="%.1f" % (100.0 * sum(f["size"] for f in fl) / TEXT_BYTES))
        return h

    def summary(var, subset):
        el = [f for f in subset if f["eligible_" + var]]
        b = sum(f["size"] for f in el)
        return OrderedDict(functions=len(el), bytes=b, pct_text="%.1f" % (100.0 * b / TEXT_BYTES))
    allf = list(F.values())
    autof = [f for f in allf if f["status"] in ("auto", "proposed")]
    done = [f for f in allf if f["status"] in ("anchored", "library", "synthetic", "supported", "verified")]
    done_bytes = sum(f["size"] for f in done)
    kinds_count = OrderedDict()
    for k in ("string-xref", "import-callee", "table-entry", "unique-constant", "emulated-io"):
        fl = [f for f in allf if k in f["primary_strict"]]
        fl2 = [f for f in allf if k in f["primary_loose"]]
        kinds_count[k] = OrderedDict(strict_functions=len(fl), strict_bytes=sum(f["size"] for f in fl),
                                     loose_functions=len(fl2), loose_bytes=sum(f["size"] for f in fl2))
    for k in ("eh-frame", "tu-neighbourhood", "struct-access"):
        fl = [f for f in allf if k in f["secondary"]]
        kinds_count[k] = OrderedDict(functions=len(fl), bytes=sum(f["size"] for f in fl))
    leaves = [f for f in allf if f["leaf"]]
    pure = [f for f in allf if f["pure_leaf"]]
    funnel["leaves (n_callees == 0, not synthetic; callgraph.json)"] = "%d functions, %d B" % (len(leaves), sum(f["size"] for f in leaves))
    funnel["pure leaves (no data-section varnode in .pcode)"] = "%d functions, %d B (x87: %d)" % (
        len(pure), sum(f["size"] for f in pure), sum(1 for f in pure if f["x87"]))
    # ---- Phase 1 exit ------------------------------------------------------------------
    el_auto_strict = sum(f["size"] for f in autof if f["eligible_strict"])
    el_auto_loose = sum(f["size"] for f in autof if f["eligible_loose"])
    ceiling_strict = done_bytes + el_auto_strict
    ceiling_loose = done_bytes + el_auto_loose
    acc = 0.8  # G6 Phase-1 anchored-half accuracy floor
    exit_bytes = done_bytes + acc * el_auto_strict
    exit_pct = 100.0 * exit_bytes / TEXT_BYTES
    exit_value = int(exit_pct // 5 * 5)
    phase1 = OrderedDict(
        rule="exit = bytes already anchored/library/synthetic/supported + 0.8 x bytes of auto/proposed functions that are supported-eligible "
             "under the strict kinds (>= 2 primary, or 1 primary + 1 secondary), as a share of the 765,525 .text bytes, rounded down to 5 points; "
             "0.8 is gate G6's Phase-1 accuracy floor",
        done_bytes=done_bytes, done_pct="%.1f" % (100.0 * done_bytes / TEXT_BYTES),
        eligible_auto_bytes_strict=el_auto_strict, eligible_auto_bytes_loose=el_auto_loose,
        ceiling_strict_pct="%.1f" % (100.0 * ceiling_strict / TEXT_BYTES), ceiling_loose_pct="%.1f" % (100.0 * ceiling_loose / TEXT_BYTES),
        exit_pct_raw="%.1f" % exit_pct, provisional_phase1_exit_pct=exit_value,
        method_doc_placeholder_pct=30)
    # ---- candidate constants ---------------------------------------------------------------
    cands = OrderedDict()
    for v, label in CURATED.items():
        imm = imm_sites.get(v, [])
        dsp = disp_sites.get(v, [])
        pf = sorted(p_owner.get(v, ()))
        enc = data_encodings(img, v)
        enc_refs = []
        for kind, va in enc:
            # who references this data address (capstone disp32/imm32 sites over bodies): reuse the scan via a second pass on demand
            enc_refs.append(OrderedDict(kind=kind, addr="0x%x" % va, klass=img.klass(va)))
        by_fn = sorted(set(fn for _, fn in imm))
        verdict = ("not assignable: %s" % label if v == 0x6cd else
                   "fails imm >= 0x100 rule" if v < 0x100 else
                   "unique (%d site(s) in %d function(s))" % (len(imm), len(by_fn)) if 0 < len(imm) <= UNIQUE_MAX_SITES else
                   "not unique (%d sites)" % len(imm) if imm else "no .text immediate site")
        cands["0x%x" % v] = OrderedDict(
            label=label, value=v, imm_sites=[OrderedDict(site="0x%x" % s, function="0x%x" % fn, name=F[fn]["name"]) for s, fn in imm],
            imm_site_method="capstone imm operand == value over Ghidra function bodies",
            disp_sites=[OrderedDict(site="0x%x" % s, function="0x%x" % fn) for s, fn in dsp][:12], disp_site_count=len(dsp),
            pcode_functions=["0x%x" % x for x in pf], pcode_method="(const, v, n) operands in high pcode (decompiler recombines lea/shl multiplies, so counts differ from imm sites)",
            data_encodings=enc_refs[:12], data_encoding_count=len(enc), verdict=verdict)
    # ---- write --------------------------------------------------------------------------
    out = OrderedDict(
        exe=a.exe, md5=img.md5, tool="tools/evidence_supply.py 1.0", funnel=funnel,
        definitions=OrderedDict(
            primary_strict="string-xref (capstone imm32), import-callee (capstone), table-entry (named tables), unique-constant (curated list, <= 3 sites), emulated-io (pure leaf)",
            primary_loose="as strict, plus generic code-ptr-run membership and any imm >= 0x100 at <= 3 .text sites",
            secondary="eh-frame, tu-neighbourhood (module has another function with a strict primary kind), struct-access; counted once together (G2)",
            eligible="supported-eligible: >= 2 primary kinds, or 1 primary + >= 1 secondary",
            bytes="Ghidra function body sizes; pct_text = share of the 765,525 .text bytes"),
        kinds=kinds_count,
        histogram_strict_all=hist("strict", allf), histogram_loose_all=hist("loose", allf),
        histogram_strict_auto=hist("strict", autof), histogram_loose_auto=hist("loose", autof),
        eligible=OrderedDict(strict_all=summary("strict", allf), loose_all=summary("loose", allf),
                             strict_auto=summary("strict", autof), loose_auto=summary("loose", autof)),
        status_bytes=OrderedDict((st, OrderedDict(functions=sum(1 for f in allf if f["status"] == st),
                                                  bytes=sum(f["size"] for f in allf if f["status"] == st)))
                                 for st in sorted(set(f["status"] for f in allf))),
        phase1_exit=phase1, candidate_constants=cands)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    os.replace(tmp, a.out)
    with open(a.out, encoding="utf-8") as fh:
        back = json.load(fh)
    assert back["phase1_exit"]["provisional_phase1_exit_pct"] == exit_value
    # per-function table
    hdr = ["addr", "size", "name", "status", "strings_capstone", "strings_ghidra", "imports_capstone", "ghidra_ext_callees", "tables_named",
           "tables_generic", "uconst_curated", "uconst_any", "pcode_uconst", "eh_frame", "module", "tu_informative", "struct_access",
           "leaf", "pure_leaf", "x87", "primary_strict", "primary_loose", "secondary", "n_primary_strict", "n_primary_loose",
           "eligible_strict", "eligible_loose"]
    lines = ["# t5-evidence-supply.per-function.tsv - tools/evidence_supply.py; addr class text; methods in status/evidence_supply.json", "\t".join(hdr)]
    for f in allf:
        lines.append("\t".join(str(x) for x in [
            "0x%x" % f["addr"], f["size"], f["name"], f["status"], f["strings_capstone"], f["strings_ghidra"], f["imports_capstone"],
            f["ghidra_ext_callees"], ";".join(f["tables_named"]), f["tables_generic"], ";".join("0x%x" % v for v in f["uconst_curated"]),
            ";".join("0x%x" % v for v in f["uconst_any"][:8]) + (";..." if len(f["uconst_any"]) > 8 else ""),
            ";".join("0x%x" % v for v in f["pcode_uconst"][:8]) + (";..." if len(f["pcode_uconst"]) > 8 else ""),
            int(f["eh_frame"]), f["module"], int(f["tu_informative"]), f["struct_access"], int(f["leaf"]), int(f["pure_leaf"]), int(f["x87"]),
            ";".join(f["primary_strict"]), ";".join(f["primary_loose"]), ";".join(f["secondary"]), f["n_primary_strict"], f["n_primary_loose"],
            int(f["eligible_strict"]), int(f["eligible_loose"])]))
    txt = "\n".join(lines) + "\n"
    with open(a.per_function, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    with open(a.per_function, encoding="utf-8") as fh:
        assert fh.read() == txt
    print("launched %s md5 %s evidence_supply.py 1.0" % (a.exe, img.md5))
    for k, v in funnel.items():
        print("  %s: %s" % (k, v))
    print("kinds:", json.dumps(kinds_count))
    print("histogram strict (all):", json.dumps(out["histogram_strict_all"]))
    print("histogram loose (all):", json.dumps(out["histogram_loose_all"]))
    print("eligible:", json.dumps(out["eligible"]))
    print("phase1:", json.dumps(phase1))
    for k, c in cands.items():
        print("cand %s %s -> %s; pcode fns %s; data encodings %d" % (k, c["label"], c["verdict"], c["pcode_functions"][:6], c["data_encoding_count"]))
    print("-> %s ; %s" % (a.out, a.per_function))


if __name__ == "__main__":
    main()
