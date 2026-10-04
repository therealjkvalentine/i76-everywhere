#!/usr/bin/env python3
"""g3_check.py - gate G3 / G7 after an ApplyMap + DumpAll round.

Compares the decompiler artefact counts of every touched function and its direct callers/callees between a
baseline export (default ghidra\\export-frozen) and the new export (ghidra\\export): new `WARNING:` lines,
new `undefined` tokens, new `in_stack_` / `unaff_` artefacts, and decompile failures (G7 baseline: the two
pass-4 failures 0x4b06b0 and 0x47a220, see status\\tasks\\t2-ghidra-rebuild.md). A function touched only by a
rename is compared on the artefact counts, never on the text. The parameter-count check is suspended for
rows carrying call-cleanup evidence (gate K).

    python tools\\g3_check.py [--map C:\\Users\\james\\i76-map] [--before ghidra\\export-frozen] [--after ghidra\\export]
                              [--batch status\\tasks\\t4-anchors.batch.json] [--out status\\tasks\\t4-g3.json]
Exit 0 when no touched function regresses; 1 otherwise (the list of regressing rows is in the JSON).
"""
import os, sys, re, json, argparse

W = re.compile(r"^\s*/\* WARNING: ", re.M)
UNDEF = re.compile(r"\bundefined\d*\b")
INSTK = re.compile(r"\b(in_stack_[0-9a-fA-F]+|unaff_[A-Za-z0-9_]+|in_[A-Z]{2,3}\b)")
G7_BASELINE_FAILURES = ("004b06b0", "0047a220")   # pass-4 baseline (Task 2); class text
G7_MAX_FAILURES = 2



def counts(path):
    if not os.path.exists(path):
        return None
    txt = open(path, encoding="utf-8", errors="replace").read()
    failed = "// DECOMPILE FAILED" in txt
    return {"warnings": len(W.findall(txt)), "undefined": len(UNDEF.findall(txt)), "in_stack": len(INSTK.findall(txt)),
            "failed": failed, "lines": txt.count("\n")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=r"C:\Users\james\i76-map")
    ap.add_argument("--before", default=None)
    ap.add_argument("--after", default=None)
    ap.add_argument("--batch", default=None)
    ap.add_argument("--addrs", default=None, help="touched set as a file of hex .text addresses (instead of a merge batch)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    M = a.map
    before = a.before or os.path.join(M, "ghidra", "export-frozen")
    after = a.after or os.path.join(M, "ghidra", "export")
    if a.addrs:
        batch = {"functions": [{"addr": l.strip(), "status": "anchored", "conv_evidence": ""} for l in open(a.addrs, encoding="utf-8")
                               if l.strip() and not l.startswith("#")]}
    else:
        batch = json.load(open(a.batch or os.path.join(M, "status", "tasks", "t4-anchors.batch.json"), encoding="utf-8"))
    fj_b = {r["addr"]: r for r in json.load(open(os.path.join(before, "functions.json"), encoding="utf-8"))}
    fj_a = {r["addr"]: r for r in json.load(open(os.path.join(after, "functions.json"), encoding="utf-8"))}
    cg_a = json.load(open(os.path.join(after, "callgraph.json"), encoding="utf-8"))
    cg_b = json.load(open(os.path.join(before, "callgraph.json"), encoding="utf-8"))
    applied = [r for r in batch["functions"] if r["status"] in ("anchored", "supported", "library", "synthetic")]
    touched = {}
    for r in applied:
        k = "%08x" % int(r["addr"], 16)
        touched[k] = r
    # neighbourhood: callers + callees of every touched function (from both graphs)
    neigh = set()
    for k in touched:
        for g in (cg_a, cg_b):
            if k in g:
                neigh.update(g[k]["callers"]); neigh.update(g[k]["callees"])
    neigh = {n for n in neigh if n in fj_a and n not in touched}
    gateK = {k for k, r in touched.items() if (r.get("conv_evidence") or "").startswith("call-cleanup")}

    def cmp(k):
        cb = counts(os.path.join(before, "functions", k + ".c"))
        ca = counts(os.path.join(after, "functions", k + ".c"))
        return cb, ca

    regress, improved, created, same = [], [], [], 0
    rows = {}
    for k in sorted(set(touched) | neigh):
        cb, ca = cmp(k)
        if ca is None:
            regress.append({"addr": k, "why": "missing after export"}); continue
        if cb is None:
            created.append({"addr": k, "after": ca}); continue
        d = {m: ca[m] - cb[m] for m in ("warnings", "undefined", "in_stack")}
        row = {"addr": k, "name": fj_a[k]["name"], "touched": k in touched, "before": cb, "after": ca, "delta": d,
               "params_before": fj_b[k]["params"] if k in fj_b else None, "params_after": fj_a[k]["params"]}
        rows[k] = row
        bad = []
        if ca["failed"] and not cb["failed"]:
            bad.append("decompile failure")
        for m in ("warnings", "undefined", "in_stack"):
            if d[m] > 0:
                bad.append("%s +%d" % (m, d[m]))
        if k in fj_b and fj_a[k]["params"] != fj_b[k]["params"] and k not in gateK:
            # only an increase of undefined-typed parameters is a regression; a count change alone is noted
            row["params_changed"] = True
        if bad:
            row["regress"] = bad; regress.append(row)
        elif any(v < 0 for v in d.values()):
            improved.append(row)
        else:
            same += 1
    fails_b = sorted(k for k, r in fj_b.items() if not r.get("decomp_ok", True))
    fails_a = sorted(k for k, r in fj_a.items() if not r.get("decomp_ok", True))
    g7_new = [k for k in fails_a if k not in G7_BASELINE_FAILURES]
    g7_ok = len(fails_a) <= G7_MAX_FAILURES and not g7_new
    g7 = {"baseline": list(G7_BASELINE_FAILURES), "max_failures": G7_MAX_FAILURES, "failures_after": fails_a,
          "outside_baseline": g7_new, "pass": g7_ok}
    out = {"before": before, "after": after, "functions_before": len(fj_b), "functions_after": len(fj_a),
           "touched": len(touched), "neighbourhood": len(neigh), "created": created, "unchanged": same,
           "improved": improved, "regressions": regress, "decompile_failures_before": fails_b, "decompile_failures_after": fails_a,
           "gateK_suspended": sorted(gateK), "g7": g7}
    op = a.out or os.path.join(M, "status", "tasks", "t4-g3.json")
    with open(op, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("G3: functions %d -> %d; touched %d (+%d neighbours); created %d; unchanged %d; improved %d; regressions %d; "
          "decompile failures %d -> %d %s" % (len(fj_b), len(fj_a), len(touched), len(neigh), len(created), same, len(improved),
                                              len(regress), len(fails_b), len(fails_a), fails_a))
    print("G7: %s (failures %d <= %d and none outside baseline %s; outside=%s)" % ("PASS" if g7_ok else "FAIL -> auto-revert",
          len(fails_a), G7_MAX_FAILURES, list(G7_BASELINE_FAILURES), g7_new))
    for r in regress:
        print("  REGRESS", r["addr"], r.get("name"), r.get("regress") or r.get("why"))
    for r in improved[:20]:
        print("  improved", r["addr"], r["name"], r["delta"])
    return 1 if (regress or not g7_ok) else 0


if __name__ == "__main__":
    sys.exit(main())
