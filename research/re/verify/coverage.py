r"""coverage.py - which functions have never been seen to run (VERIFICATION-PROGRAM section 5).

    python verify\coverage.py [--all] [--json verify\coverage.json]

Walks verify\runs\<scenario>\<timestamp>\census.jsonl, sums calls per function over every run, and lists the hooked
functions with zero calls across all runs so far (name, batch, scenarios that hooked it, runs). Also reports
functions in batches\ that no run has hooked yet, hooks that were skipped (prologue differs / not hookable) and the
functions make-batches excluded (batches\excluded.json), so "never" is never confused with "never measured".
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BATCHES, RUNS, VERIFY  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="print every zero-call function, not the first 60")
    ap.add_argument("--json", default=os.path.join(VERIFY, "coverage.json"))
    a = ap.parse_args()
    seen = {}       # addr -> {name, calls, runs, scenarios, skipped:[reasons]}
    runs = sorted(glob.glob(os.path.join(RUNS, "*", "*", "census.jsonl")))
    for path in runs:
        scenario = os.path.basename(os.path.dirname(os.path.dirname(path)))
        ok = True
        mp = os.path.join(os.path.dirname(path), "manifest.json")
        if os.path.exists(mp):
            ok = json.load(open(mp, encoding="utf-8")).get("ok", True)
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            e = seen.setdefault(r["addr"], {"name": r["name"], "calls": 0, "runs": 0, "scenarios": set(), "skipped": set(), "runs_with_errors": 0})
            if r["hook"] != "attached":
                e["skipped"].add(r["hook"][:80])
                continue
            e["calls"] += r["calls"]
            e["runs"] += 1
            e["scenarios"].add(scenario)
            if not ok:
                e["runs_with_errors"] += 1
    batched = {}
    for bp in sorted(glob.glob(os.path.join(BATCHES, "batch-*.json"))):
        b = json.load(open(bp, encoding="utf-8"))
        for f in b["functions"]:
            batched[f["addr"]] = (b["batch"], f["name"])
    excluded = []
    xp = os.path.join(BATCHES, "excluded.json")
    if os.path.exists(xp):
        excluded = json.load(open(xp, encoding="utf-8"))["excluded"]
    zero = sorted([(addr, e) for addr, e in seen.items() if e["runs"] > 0 and e["calls"] == 0], key=lambda x: int(x[0], 16))
    skipped_only = sorted([(addr, e) for addr, e in seen.items() if e["runs"] == 0], key=lambda x: int(x[0], 16))
    unhooked = sorted([(addr, nm) for addr, (b, nm) in batched.items() if addr not in seen], key=lambda x: int(x[0], 16))
    print("census runs: %d   functions hooked at least once: %d   zero calls across all runs: %d   skipped in every run: %d   batched but never run: %d   excluded by make-batches: %d" % (
        len(runs), sum(1 for e in seen.values() if e["runs"] > 0), len(zero), len(skipped_only), len(unhooked), len(excluded)))
    print("\n%-10s %-40s %-10s %4s  %s" % ("addr", "name", "batch", "runs", "scenarios"))
    for addr, e in (zero if a.all else zero[:60]):
        print("%-10s %-40s %-10s %4d  %s" % (addr, e["name"], batched.get(addr, ("?", ""))[0], e["runs"], ",".join(sorted(e["scenarios"]))))
    if not a.all and len(zero) > 60:
        print("... %d more (--all)" % (len(zero) - 60))
    if skipped_only:
        print("\nskipped in every run (never hooked):")
        for addr, e in skipped_only:
            print("%-10s %-40s %s" % (addr, e["name"], "; ".join(sorted(e["skipped"]))))
    out = {"runs": runs, "zero_calls": [{"addr": addr, "name": e["name"], "batch": batched.get(addr, ("?",))[0], "runs": e["runs"],
                                        "scenarios": sorted(e["scenarios"]), "runs_with_errors": e["runs_with_errors"]} for addr, e in zero],
           "skipped_every_run": [{"addr": addr, "name": e["name"], "reasons": sorted(e["skipped"])} for addr, e in skipped_only],
           "batched_never_run": [{"addr": addr, "name": nm, "batch": batched[addr][0]} for addr, nm in unhooked],
           "excluded_by_make_batches": excluded,
           "hooked_summary": {addr: {"name": e["name"], "calls": e["calls"], "runs": e["runs"], "scenarios": sorted(e["scenarios"])} for addr, e in sorted(seen.items(), key=lambda x: int(x[0], 16))}}
    json.dump(out, open(a.json, "w", encoding="utf-8"), indent=1)
    print("\nwritten %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
