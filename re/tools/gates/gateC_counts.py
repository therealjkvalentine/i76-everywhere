#!/usr/bin/env python3
"""Gate C (counting method; method doc 4.1). Every count carries its method.

Checks:
  evidence: any item with n / count / sites carries `method`; a `unique: true` constant-anchor carries method.
  imports.tsv: capstone call/load columns present for every slot; the four settled imports match
      GetTickCount 9 call + 1 load (Ghidra 21), HeapCreate 19 call + 7 load (Ghidra 62), timeGetTime 3 call
      (Ghidra 6), VirtualAlloc in 2 functions 0x498940/0x498a50 (Ghidra 5); the ratio ghidra_refs >= call+load
      holds for every slot (Ghidra counts flow refs too).
  tables.tsv: every row has a non-empty method.
  status\\roundtrip.json / evidence_supply.json (when present): every family carries `method`.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, IMPORT_COLS, TABLE_COLS, parse_addr

SETTLED = {"GetTickCount": (9, 1, 21), "HeapCreate": (19, 7, 62), "timeGetTime": (3, 0, 6)}


def main():
    ctx, args = make("gateC", __doc__)
    rows = ctx.batch_rows("functions") + ctx.batch_rows("globals") + ctx.batch_rows("ported") if ctx.batch else ctx.functions + ctx.globals
    n = 0
    ghidra_funcs = None

    def trap_after(e, who):
        """Gate C method tag `hwbp-trap-after` (FOLDIN-REPORT section 3, C18): watchpoint-derived addresses carry this
        tag and resolve the resumed EIP to the faulting instruction and its function start (merge.gate_c_trap_after)."""
        nonlocal ghidra_funcs
        if e.get("method") != "hwbp-trap-after" and not e.get("trap_after"):
            return
        if ghidra_funcs is None:
            ghidra_funcs = {int(x["addr"], 16): x for x in json.load(open(ctx.path("ghidra", "export", "functions.json"), encoding="utf-8"))}
        from merge import gate_c_trap_after, Reject
        try:
            gate_c_trap_after(ctx.dis, dict(e), ghidra_funcs)
        except Reject as ex:
            ctx.fail("%s: %s" % (who, ex))
    for r in rows:
        for e in ctx.row_evidence(r):
            n += 1
            for k in ("n", "count", "sites"):
                if k in e and not e.get("method"):
                    ctx.fail("%s %s evidence %s: %s=%r without method" % (r.get("addr"), r.get("name"), e.get("kind"), k, e[k]))
            if e.get("kind") == "constant-anchor" and e.get("unique") and not e.get("method"):
                ctx.fail("%s constant-anchor unique:true without the site-count method" % r.get("addr"))
            trap_after(e, "%s %s evidence %s" % (r.get("addr") or r.get("ledger_id"), r.get("name"), e.get("kind")))
    if not ctx.batch:
        for eid, e in ctx.evidence.items():
            for k in ("n", "count", "sites"):
                if k in e and not e.get("method"):
                    ctx.fail("evidence %s: %s=%r without method" % (eid, k, e[k]))
            trap_after(e, "evidence %s" % eid)
    imps = ctx.tsv("imports.tsv", IMPORT_COLS)
    byname = {}
    for r in imps:
        byname.setdefault(r["name"], r)
        for c in ("call_sites", "load_sites", "ghidra_refs"):
            if r.get(c, "") == "":
                ctx.fail("imports.tsv %s %s: %s column empty (capstone method missing)" % (r["iat_slot"], r["name"], c))
        try:
            if int(r["ghidra_refs"]) < int(r["call_sites"]) + int(r["load_sites"]) - int(r.get("jmp_sites") or 0):
                ctx.note("imports.tsv %s: ghidra_refs %s < call+load %s+%s (ratio outside the expected direction)"
                         % (r["name"], r["ghidra_refs"], r["call_sites"], r["load_sites"]))
        except ValueError:
            ctx.fail("imports.tsv %s: non-integer count" % r["name"])
    for name, (c, l, g) in SETTLED.items():
        r = byname.get(name)
        if r is None:
            ctx.fail("imports.tsv has no row for %s" % name); continue
        if (int(r["call_sites"]), int(r["load_sites"]), int(r["ghidra_refs"])) != (c, l, g):
            ctx.fail("imports.tsv %s: call/load/ghidra = %s/%s/%s, settled %d/%d/%d" %
                     (name, r["call_sites"], r["load_sites"], r["ghidra_refs"], c, l, g))
    va = byname.get("VirtualAlloc")
    if va is None:
        ctx.fail("imports.tsv has no row for VirtualAlloc")
    else:
        fns = {parse_addr(x) for x in (va["functions"] or "").split(";") if x}
        if fns != {0x498940, 0x498a50} or int(va["ghidra_refs"]) != 5:
            ctx.fail("imports.tsv VirtualAlloc: functions %s ghidra %s, settled {0x498940,0x498a50} / 5" % (sorted(map(hex, fns)), va["ghidra_refs"]))
    for t in ctx.tsv("tables.tsv", TABLE_COLS):
        if not t.get("method"):
            ctx.fail("tables.tsv %s %s: no method" % (t.get("base"), t.get("name")))
    for sf in ("roundtrip.json", "evidence_supply.json"):
        p = ctx.path("status", sf)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            fams = d.get("families") or d.get("histogram") or []
            for f in fams if isinstance(fams, list) else []:
                if isinstance(f, dict) and not f.get("method"):
                    ctx.fail("status/%s family %s: no method" % (sf, f.get("family")))
    ctx.note("checked %d evidence items on %d rows, %d import slots, 4 settled imports" % (n, len(rows), len(imps)))
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
