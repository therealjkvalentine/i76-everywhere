#!/usr/bin/env python3
"""Gate N (names unique; method doc 4.2). The merge rejects two rows receiving the same name; a tag-derived
name lists every (table, tag) pair pointing at the function.

Checks (batch rows against the map, or the whole map): identifiers well-formed; no duplicate name across
functions.tsv + globals.tsv (+ batch); bwd2_h_* rows list every (table,index,tag) pair recomputed from
tables.tsv (0x4b4290 EXIT serves 31 pairs; 0x4b0d00 / 0x4b0e70 serve ENGN/BRAK/SUSP; VCFC maps to three
handlers); a name that is an export of another module (imports.tsv names, Z*.DLL exports listed in
symbols/modules.tsv when present) is not accepted as a G1 self-naming name unless the row is an import wrapper.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, Reject, parse_addr, TABLE_COLS, IMPORT_COLS


def main():
    ctx, args = make("gateN", __doc__)
    from merge import gate_n, bwd2_pairs, NAME_RE
    pairs = bwd2_pairs(ctx.tsv("tables.tsv", TABLE_COLS))
    owner = {}
    for r in ctx.functions:
        if not r["name"].startswith("FUN_"):
            if r["name"] in owner and owner[r["name"]] != parse_addr(r["addr"]):
                ctx.fail("functions.tsv: name %r at %s and %s" % (r["name"], hex(owner[r["name"]]), r["addr"]))
            owner.setdefault(r["name"], parse_addr(r["addr"]))
    for r in ctx.globals:
        if r["name"] in owner and owner[r["name"]] != parse_addr(r["addr"]):
            ctx.fail("globals.tsv: name %r at %s and %s" % (r["name"], hex(owner[r["name"]]), r["addr"]))
        owner.setdefault(r["name"], parse_addr(r["addr"]))
    imports = {r["name"] for r in ctx.tsv("imports.tsv", IMPORT_COLS)}
    rows = (ctx.batch_rows("functions") + ctx.batch_rows("globals")) if ctx.batch else (ctx.functions + ctx.globals)
    n = 0
    for r in rows:
        nm = r.get("name", "")
        if nm.startswith("FUN_") or nm.startswith("DAT_"):
            continue
        n += 1
        try:
            if not NAME_RE.match(nm):
                raise Reject("name %r is not an identifier" % nm)
            evs = ctx.row_evidence(r)
            gate_n(r, evs, owner if ctx.batch else {k: v for k, v in owner.items() if v != parse_addr(r["addr"])}, pairs)
            if nm in imports and r.get("status") == "anchored" and not any(e.get("kind") in ("import-thunk", "import-wrapper") for e in evs):
                raise Reject("name %r is an import of another module; only an import wrapper may carry it" % nm)
        except Reject as ex:
            ctx.fail("%s %s: %s" % (r.get("addr"), nm, ex))
        if ctx.batch:
            owner.setdefault(nm, parse_addr(r["addr"]))
    # bwd2 completeness on the map: every handler with pairs that carries a bwd2_h_ name lists them all (gate_n did it per row)
    ctx.note("checked %d named rows against %d existing names, %d BWD2 handlers with pairs" % (n, len(owner), len(pairs)))
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
