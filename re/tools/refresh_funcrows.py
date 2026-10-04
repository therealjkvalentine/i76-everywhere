#!/usr/bin/env python3
"""refresh_funcrows.py - refresh the Ghidra-derived columns of symbols/functions.tsv for a chosen set of rows.

After a Ghidra round that created functions or ran Decompiler Parameter ID on a subset (p4-ghidra-fixes:
ParamIdTargeted.py), the rows those functions own carry stale `size`, `conv` (Parameter ID, gate K `auto`) and
`hookable` values (`tbd` for rows ApplyMap created under -noanalysis). This tool copies exactly those columns
from a fresh hookability run (tools/hookability.py --out <scratch tsv>, never written over the map's own
functions.tsv because that run resets every status to auto) into the map's rows, and inserts a new `auto` row for
every function in the export that has no row yet (status auto, conv from Parameter ID, conv_evidence
auto:paramid, no evidence). Names, status, evidence, tu, subsystem, duplicate_of are never touched for existing
rows. Writes through merge.write_tsv (.tmp, rename, read back). Every address is class init (.text VA).

    python tools\\refresh_funcrows.py --auto-tsv <scratch>\\functions-auto.tsv [--addrs touched.txt] [--dry-run]
Without --addrs the refreshed set is: rows with hookable == tbd + functions absent from functions.tsv.
"""
import os, sys, json, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from merge import read_tsv, write_tsv, FUNC_COLS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=ROOT)
    ap.add_argument("--auto-tsv", required=True, help="functions.tsv written by hookability.py from the NEW export (scratch path)")
    ap.add_argument("--addrs", default=None, help="hex addresses to refresh (one per line); default = hookable==tbd rows + new functions")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    M = a.map
    fpath = os.path.join(M, "symbols", "functions.tsv")
    fcom, frows = read_tsv(fpath, FUNC_COLS)
    _, arows = read_tsv(a.auto_tsv, FUNC_COLS)
    auto = {int(r["addr"], 16): r for r in arows}
    have = {int(r["addr"], 16): r for r in frows}
    fj = {int(r["addr"], 16): r for r in json.load(open(os.path.join(M, "ghidra", "export", "functions.json"), encoding="utf-8"))}
    if a.addrs:
        sel = {int(l.strip(), 16) for l in open(a.addrs, encoding="utf-8") if l.strip() and not l.startswith("#")}
    else:
        sel = {ad for ad, r in have.items() if r.get("hookable") == "tbd"} | (set(auto) - set(have))
    updated, inserted, unchanged, missing = [], [], 0, []
    for ad in sorted(sel):
        src = auto.get(ad)
        if src is None:
            missing.append("0x%06x" % ad); continue
        g = fj.get(ad, {})
        if ad in have:
            r = have[ad]
            new = {"size": src["size"], "conv": src["conv"], "hookable": src["hookable"]}
            old = {k: r[k] for k in new}
            if old != new:
                for k, v in new.items():
                    r[k] = v
                if not r.get("conv_evidence"):
                    r["conv_evidence"] = "auto:paramid"
                updated.append((ad, r["name"], old, new, g.get("params")))
            else:
                unchanged += 1
        else:
            row = {c: "" for c in FUNC_COLS}
            row.update({"addr": "0x%06x" % ad, "size": src["size"], "name": src["name"], "status": "auto", "conv": src["conv"],
                        "conv_evidence": "auto:paramid", "hookable": src["hookable"], "duplicate_of": src.get("duplicate_of", "")})
            frows.append(row); have[ad] = row
            inserted.append((ad, row["name"], src["size"], src["conv"], src["hookable"], g.get("params")))
    frows.sort(key=lambda r: int(r["addr"], 16))
    for ad, name, old, new, p in updated:
        print("update 0x%06x %-22s %s -> %s params=%s" % (ad, name, old, new, p))
    for ad, name, sz, cc, hk, p in inserted:
        print("insert 0x%06x %-22s size=%s conv=%s hookable=%s params=%s status=auto" % (ad, name, sz, cc, hk, p))
    print("refresh_funcrows: selected %d; updated %d, inserted %d, unchanged %d, missing-from-auto %s; rows %d -> %d" %
          (len(sel), len(updated), len(inserted), unchanged, missing or 0, len(have) - len(inserted), len(frows)))
    if a.dry_run:
        print("dry run: nothing written"); return 0
    n = write_tsv(fpath, fcom, FUNC_COLS, frows)
    print("wrote %s: %d rows (read back)" % (fpath, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
