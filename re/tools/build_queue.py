#!/usr/bin/env python3
"""build_queue.py - write status\\queue.json for the agent loop (method doc section 6; Task 8).

Order rule (leases are handed out in `rank` order):
  tier 1  leaves first: functions with no intra-module callee (all callees EXTERNAL), ordered by static
          evidence supply (strings referenced + imports called, desc) then size (asc);
  tier 2  callers of accepted rows: direct callers of anchored/supported/library rows, ordered by the number of
          accepted callees (desc) then size;
  tier 3  everything else by size (asc);
  tier 4  functions whose decompilation exceeds 300 lines (c_lines in functions.json), always last.
Excluded (never leased): rows already anchored/supported/library/synthetic; the truth set and its direct
callers (status\\truthset.json {"anchored": [...], "stringless": [...]} and/or status\\truthset-exclude.txt, Task 7),
recorded under `excluded` with the reason. Functions whose decompile failed carry views_available: [pcode].

    python tools\\build_queue.py [--map M] [--out status\\queue.json] [--force]
Refuses to overwrite a queue that holds live leases unless --force (leases would be lost); otherwise carries
tokens_used / attempts / status of existing items forward by address.
"""
import os, sys, json, time, hashlib, argparse, re

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from merge import read_tsv, FUNC_COLS  # noqa: E402

ACCEPTED = ("anchored", "supported", "library", "synthetic")
BIG_LINES = 300
STR_COLS = ["addr", "class", "len", "string", "xref_count", "referencing_functions", "section", "ghidra_type",
            "imm32_sites", "imm32_functions", "verified"]


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def load_truthset(M):
    """-> (truth-set function addresses, extra excluded addresses already listed by Task 7, sources).
    truthset.json holds the 60 sealed functions (anchored + stringless halves); truthset-exclude.txt is Task 7's own
    callers-inclusive exclusion list (186 = 60 + direct callers), used by ApplyMap.py."""
    truth = set(); extra = set(); src = []
    tp = os.path.join(M, "status", "truthset.json")
    if os.path.exists(tp):
        t = json.load(open(tp, encoding="utf-8"))
        for k in ("anchored", "stringless"):
            for a in t.get(k, []):
                truth.add(int(str(a.get("addr", a) if isinstance(a, dict) else a), 16))
        for a in t.get("exclude", []):
            extra.add(int(str(a), 16))
        src.append("status/truthset.json")
    xp = os.path.join(M, "status", "truthset-exclude.txt")
    if os.path.exists(xp):
        for line in open(xp, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                extra.add(int(line, 16))
        src.append("status/truthset-exclude.txt")
    return truth, extra, src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=os.path.dirname(TOOLS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--ttl", type=int, default=3600, help="default lease TTL in seconds")
    a = ap.parse_args()
    M = a.map
    out = a.out or os.path.join(M, "status", "queue.json")
    cgp = os.path.join(M, "ghidra", "export", "callgraph.json")
    fjp = os.path.join(M, "ghidra", "export", "functions.json")
    ftp = os.path.join(M, "symbols", "functions.tsv")
    cg = json.load(open(cgp, encoding="utf-8"))
    fj = {r["addr"]: r for r in json.load(open(fjp, encoding="utf-8"))}
    rows = {"%08x" % int(r["addr"], 16): r for r in read_tsv(ftp, FUNC_COLS)[1]}
    strings = read_tsv(os.path.join(M, "symbols", "strings.tsv"), STR_COLS)[1]
    str_by_fn = {}
    for s in strings:
        for f in (s.get("referencing_functions") or "").split(";"):
            f = f.strip().lower()
            if f:
                str_by_fn[f] = str_by_fn.get(f, 0) + 1

    old = {}
    if os.path.exists(out):
        try:
            oq = json.load(open(out, encoding="utf-8"))
            old = {it["key"]: it for it in oq.get("items", [])}
            live = [it for it in old.values() for v in it["views"].values() if v.get("lease")]
            if live and not a.force:
                print("REFUSE: %s holds %d live leases; use --force to rebuild (leases are lost)" % (out, len(live)))
                return 2
        except Exception as ex:
            print("warning: could not read existing queue (%s); rebuilding" % ex)

    truth, extra, truth_src = load_truthset(M)
    truth_keys = {"%08x" % t for t in truth}
    truth_callers = set()
    for k in truth_keys:
        for c in cg.get(k, {}).get("callers", []):
            truth_callers.add(c)
    truth_callers |= {"%08x" % t for t in extra} - truth_keys  # Task 7's own list (callers-inclusive), never leased
    accepted_keys = {k for k, r in rows.items() if r["status"] in ACCEPTED}

    items, excluded = [], []
    for k, g in cg.items():
        r = rows.get(k)
        f = fj.get(k)
        name = g.get("name") or (r and r["name"]) or ("FUN_" + k)
        if r and r["status"] in ACCEPTED:
            excluded.append({"key": k, "name": name, "why": "status %s" % r["status"]}); continue
        if k in truth_keys:
            excluded.append({"key": k, "name": name, "why": "truth set (G6)"}); continue
        if k in truth_callers:
            excluded.append({"key": k, "name": name, "why": "direct caller of a truth-set function (G6)"}); continue
        internal = [c for c in g.get("callees", []) if not c.startswith("000000")]
        externals = [c for c in g.get("callees", []) if c.startswith("000000")]
        leaf = len(internal) == 0
        acc_callees = [c for c in internal if c in accepted_keys]
        size = int(f["size"]) if f else int(r["size"]) if r and r["size"] else 0
        c_lines = f.get("c_lines") if f else None
        decomp_ok = f.get("decomp_ok", True) if f else True
        supply = {"strings": str_by_fn.get(k, 0), "imports": len(set(externals)), "method": "strings.tsv referencing_functions; callgraph.json EXTERNAL callees"}
        if c_lines is not None and c_lines > BIG_LINES:
            tier = 4
        elif leaf:
            tier = 1
        elif acc_callees:
            tier = 2
        else:
            tier = 3
        prev = old.get(k, {})
        it = {"addr": "0x%x" % int(k, 16), "key": k, "name": name, "size": size, "c_lines": c_lines, "tier": tier,
              "leaf": leaf, "n_callers": len(g.get("callers", [])), "n_callees_internal": len(internal),
              "accepted_callees": ["0x%x" % int(c, 16) for c in acc_callees], "evidence_supply": supply,
              "decomp_ok": decomp_ok, "views_available": ["c", "pcode"] if decomp_ok else ["pcode"],
              "status": prev.get("status", "open") if prev.get("status") not in ("leased",) else "open",
              "tokens_used": prev.get("tokens_used", 0), "attempts": prev.get("attempts", 0),
              "blocker": prev.get("blocker"), "requeue": prev.get("requeue"),
              "views": {v: {"state": "open", "lease": None, "attempts": prev.get("views", {}).get(v, {}).get("attempts", 0),
                            "tokens": prev.get("views", {}).get(v, {}).get("tokens", 0),
                            "proposal": prev.get("views", {}).get(v, {}).get("proposal")}
                        for v in ("c", "pcode")},
              "history": prev.get("history", [])}
        if prev.get("status") in ("done", "budget-exhausted", "rejected"):
            it["status"] = prev["status"]
        items.append(it)

    def sort_key(it):
        if it["tier"] == 1:
            return (1, -(it["evidence_supply"]["strings"] + it["evidence_supply"]["imports"]), it["size"], it["key"])
        if it["tier"] == 2:
            return (2, -len(it["accepted_callees"]), it["size"], it["key"])
        return (it["tier"], it["size"], it["key"])
    items.sort(key=sort_key)
    for i, it in enumerate(items, 1):
        it["rank"] = i
    tiers = {}
    for it in items:
        tiers[it["tier"]] = tiers.get(it["tier"], 0) + 1
    q = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": "tools/build_queue.py",
         "order_rule": "tier 1 leaves (no intra-module callee) by evidence supply desc then size; tier 2 direct callers of anchored/supported/library rows by accepted-callee count; tier 3 rest by size; tier 4 c_lines > 300 last; truth set and its direct callers never leased",
         "sources": {"callgraph.json": md5(cgp), "functions.json": md5(fjp), "functions.tsv": md5(ftp), "truthset": truth_src or None,
                     "truthset_functions": len(truth_keys), "truthset_callers": len(truth_callers - truth_keys)},
         "lease_ttl_seconds": a.ttl, "per_function_token_budget": 150000,
         "counts": {"items": len(items), "excluded": len(excluded), "by_tier": {str(k): v for k, v in sorted(tiers.items())},
                    "method": "callgraph.json keys minus accepted/truth-set rows; tiers as in order_rule"},
         "items": items, "excluded": excluded}
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(q, fh, indent=1)
    os.replace(tmp, out)
    back = json.load(open(out, encoding="utf-8"))
    assert len(back["items"]) == len(items), "readback mismatch"
    print("queue: %d items (%s), %d excluded, truth set %d (+%d callers) from %s -> %s" %
          (len(items), json.dumps(q["counts"]["by_tier"]), len(excluded), len(truth_keys), len(truth_callers - truth_keys), truth_src or "none yet", out))
    for it in items[:5]:
        print("  rank %d tier %d %s %s size %d supply %s" % (it["rank"], it["tier"], it["addr"], it["name"], it["size"], it["evidence_supply"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
