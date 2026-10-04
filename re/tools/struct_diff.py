#!/usr/bin/env python3
"""struct_diff.py - G7 reproducibility check: diff the STRUCTURAL inventory of two Ghidra exports.

Compared (decompiler text is NOT compared; it is informational under G7):
  functions.json : function starts, sizes, body ranges, thunk flag/target, calling convention, param count,
                   prototype string, custom storage, stack purge, n_callers, n_callees, refs_to_entry, decomp_ok
  callgraph.json : caller/callee edge sets and call-site lists
  flows.csv      : the flow-reference rows (from,to,type)
  hot_globals.csv: address -> refs, reads, writes, funcs
  imports_xrefs.csv, strings_xrefs.csv (address -> xref counts), functions.csv (Ghidra-side prototype columns)
  summary.json   : function/thunk/decomp-failure/symbol counts
Optionally (--text) also counts .c files whose text differs, as an informational line.

Usage: python tools/struct_diff.py <exportA> <exportB> [--text]
Exit 0 when every structural comparison is empty ("reproducible"), 1 otherwise.
"""
import sys, os, json, csv, argparse, hashlib


def load_json(d, name):
    return json.load(open(os.path.join(d, name)))


def load_csv_index(d, name, keycols, valcols=None):
    out = {}
    with open(os.path.join(d, name), newline="", encoding="utf-8", errors="replace") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            k = tuple(row[c] for c in keycols)
            v = tuple(row[c] for c in (valcols or [c for c in rd.fieldnames if c not in keycols]))
            out.setdefault(k, []).append(v)
    return out


def dict_diff(name, A, B, limit=10):
    onlyA = sorted(set(A) - set(B)); onlyB = sorted(set(B) - set(A))
    changed = sorted(k for k in set(A) & set(B) if A[k] != B[k])
    print("  %-22s A=%d B=%d only-A=%d only-B=%d changed=%d" % (name, len(A), len(B), len(onlyA), len(onlyB), len(changed)))
    for k in onlyA[:limit]: print("     only-A %s" % (k,))
    for k in onlyB[:limit]: print("     only-B %s" % (k,))
    for k in changed[:limit]: print("     changed %s: %s -> %s" % (k, A[k], B[k]))
    return len(onlyA) + len(onlyB) + len(changed)


FKEYS = ["size", "start", "end", "ranges", "thunk", "thunk_target", "cc", "params", "prototype", "custom_storage",
         "stack_purge", "n_callers", "n_callees", "refs_to_entry", "decomp_ok", "name"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--text", action="store_true")
    o = ap.parse_args()
    total = 0
    print("struct_diff: A=%s B=%s" % (o.a, o.b))
    fa = {r["addr"]: tuple(r.get(k) for k in FKEYS) for r in load_json(o.a, "functions.json")}
    fb = {r["addr"]: tuple(r.get(k) for k in FKEYS) for r in load_json(o.b, "functions.json")}
    total += dict_diff("functions.json", fa, fb)
    ca = {k: (tuple(v["callers"]), tuple(v["callees"]), tuple(tuple(s) for s in v["call_sites"])) for k, v in load_json(o.a, "callgraph.json").items()}
    cb = {k: (tuple(v["callers"]), tuple(v["callees"]), tuple(tuple(s) for s in v["call_sites"])) for k, v in load_json(o.b, "callgraph.json").items()}
    total += dict_diff("callgraph.json", ca, cb)
    total += dict_diff("flows.csv", load_csv_index(o.a, "flows.csv", ["from", "to", "type"]), load_csv_index(o.b, "flows.csv", ["from", "to", "type"]))
    total += dict_diff("hot_globals.csv", load_csv_index(o.a, "hot_globals.csv", ["address"], ["refs", "reads", "writes", "funcs"]),
                       load_csv_index(o.b, "hot_globals.csv", ["address"], ["refs", "reads", "writes", "funcs"]))
    total += dict_diff("imports_xrefs.csv", load_csv_index(o.a, "imports_xrefs.csv", ["library", "name"]), load_csv_index(o.b, "imports_xrefs.csv", ["library", "name"]))
    total += dict_diff("strings_xrefs.csv", load_csv_index(o.a, "strings_xrefs.csv", ["address"], ["type", "length", "xref_count", "referencing_functions"]),
                       load_csv_index(o.b, "strings_xrefs.csv", ["address"], ["type", "length", "xref_count", "referencing_functions"]))
    total += dict_diff("functions.csv", load_csv_index(o.a, "functions.csv", ["address"], ["name", "size", "calling_convention", "param_count", "is_thunk", "string_refs", "vtable_calls", "x87_instrs"]),
                       load_csv_index(o.b, "functions.csv", ["address"], ["name", "size", "calling_convention", "param_count", "is_thunk", "string_refs", "vtable_calls", "x87_instrs"]))
    sa = load_json(o.a, "summary.json"); sb = load_json(o.b, "summary.json")
    for k in ("functions", "thunks", "decomp_failed", "symbols", "flow_refs_into_text", "exe_md5"):
        if sa.get(k) != sb.get(k):
            print("  summary.json %s: %s -> %s" % (k, sa.get(k), sb.get(k))); total += 1
    if o.text:
        da, db = os.path.join(o.a, "functions"), os.path.join(o.b, "functions")
        names = sorted(set(os.listdir(da)) | set(os.listdir(db)))
        nd = 0; miss = 0
        for n in names:
            pa, pb = os.path.join(da, n), os.path.join(db, n)
            if not (os.path.exists(pa) and os.path.exists(pb)): miss += 1; continue
            if hashlib.md5(open(pa, "rb").read()).digest() != hashlib.md5(open(pb, "rb").read()).digest(): nd += 1
        print("  informational: %d of %d .c/.pcode files differ in text, %d missing on one side" % (nd, len(names), miss))
    print("RESULT: %s (%d structural differences)" % ("reproducible" if total == 0 else "NOT reproducible", total))
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
