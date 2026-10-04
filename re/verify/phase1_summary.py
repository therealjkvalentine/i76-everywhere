r"""phase1_summary.py - roll the phase-1 census runs up per function (VERIFICATION-PROGRAM section 2.2 / 5).

    python verify\phase1_summary.py [--json verify\runs\phase1-summary.json] [--pass entity|early|all] [--all-runs] [--compare other-summary.json]

Reads every runs\<scenario>\<ts>\census.classified.json whose manifest census pass matches --pass (`entity` = the
first pass, attach after the player entity, the default; `early` = attach at spawn, run_phase1.py --pass early; `all`
= both; --all-runs takes every classified run whatever its pass) and gives, per function, the class in every scenario
plus one overall class: the strongest cadence seen in any scenario (per_substep > per_frame > per_event > irregular >
menu_only > init_only > never; not_hooked when no run hooked it). Prints the histogram over all functions, the
per-scenario histograms, and the zero-calls list grouped by name prefix. --compare <summary.json> (an earlier pass's
output) lists, by prefix, the functions that were `never` there and fire in this set, with the class they got.
"""
import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BATCHES, RUNS  # noqa: E402

RANK = {"per_substep": 6, "per_frame": 5, "per_event": 4, "irregular": 3, "menu_only": 2, "init_only": 1, "never": 0}


def prefix(name):
    return name.split("_")[0] if "_" in name else name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=os.path.join(RUNS, "phase1-summary.json"))
    ap.add_argument("--pass", dest="pass_", default="entity", choices=("entity", "early", "all"))
    ap.add_argument("--all-runs", action="store_true")
    ap.add_argument("--compare", default=None, help="an earlier summary JSON: report its `never` functions that fire here")
    a = ap.parse_args()
    per = {}            # addr -> {name, batch, scen: {scenario: [class, ...]}, calls}
    runs_used = []
    for cp in sorted(glob.glob(os.path.join(RUNS, "*", "*", "census.classified.json"))):
        d = os.path.dirname(cp)
        man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
        cen = man.get("census") or {}
        run_pass = cen.get("pass") or ("entity" if cen.get("attach_after_entity") else "launch")
        if not a.all_runs and a.pass_ != "all" and run_pass != a.pass_:
            continue
        if not a.all_runs and a.pass_ == "all" and run_pass not in ("entity", "early"):
            continue
        cl = json.load(open(cp, encoding="utf-8"))
        runs_used.append({"run": d, "scenario": cl["scenario"], "pass": run_pass, "batch": cen.get("batch_id"), "frames_live": cl["frames_live"],
                          "classes": cl["classes"], "ok": man.get("ok"), "attach_t": cen.get("attach_t_after_launch"), "hooks_done_t": cen.get("hooks_done_t_after_launch")})
        for f in cl["functions"]:
            e = per.setdefault(f["addr"], {"name": f["name"], "scen": {}, "calls": 0, "hooked_runs": 0, "not_hooked": set()})
            if f["class"] == "not_hooked":
                e["not_hooked"].add(f.get("note", "")[:60])
                continue
            e["hooked_runs"] += 1
            e["calls"] += f.get("calls", 0)
            e["scen"].setdefault(cl["scenario"], []).append(f["class"])
    batched = {}
    for bp in sorted(glob.glob(os.path.join(BATCHES, "batch-*.json"))):
        b = json.load(open(bp, encoding="utf-8"))
        for f in b["functions"]:
            batched[f["addr"]] = b["batch"]
    overall = collections.Counter()
    per_scn = collections.defaultdict(collections.Counter)
    zero = []
    out_fns = {}
    for addr, e in sorted(per.items(), key=lambda x: int(x[0], 16)):
        if e["hooked_runs"] == 0:
            cls = "not_hooked"
        else:
            best = max((c for cs in e["scen"].values() for c in cs), key=lambda c: RANK.get(c, -1))
            cls = best
        overall[cls] += 1
        for s, cs in e["scen"].items():
            per_scn[s][max(cs, key=lambda c: RANK.get(c, -1))] += 1
        out_fns[addr] = {"name": e["name"], "batch": batched.get(addr), "overall": cls, "calls": e["calls"], "hooked_runs": e["hooked_runs"],
                         "by_scenario": {s: cs for s, cs in e["scen"].items()}, "not_hooked": sorted(e["not_hooked"])}
        if cls == "never":
            zero.append((addr, e["name"]))
    print("phase-1 runs used: %d   functions seen: %d   hooked at least once: %d" % (len(runs_used), len(per), sum(1 for e in per.values() if e["hooked_runs"])))
    print("overall (strongest class in any scenario): %s" % dict(overall.most_common()))
    for s, c in sorted(per_scn.items()):
        print("  %-10s %s" % (s, dict(c.most_common())))
    byp = collections.defaultdict(list)
    for addr, nm in zero:
        byp[prefix(nm)].append(nm)
    tot = collections.Counter(prefix(e["name"]) for e in per.values() if e["hooked_runs"])
    print("\nzero calls in every scenario: %d functions" % len(zero))
    for p, names in sorted(byp.items(), key=lambda x: -len(x[1])):
        print("  %-14s %3d / %3d  %s%s" % (p, len(names), tot[p], ", ".join(n for n in names[:6]), " ..." if len(names) > 6 else ""))
    compare = None
    if a.compare:
        prev = json.load(open(a.compare, encoding="utf-8"))
        prev_never = {addr: f["name"] for addr, f in prev["functions"].items() if f["overall"] == "never"}
        now_fire = {addr: out_fns[addr] for addr in prev_never if addr in out_fns and out_fns[addr]["overall"] not in ("never", "not_hooked")}
        unseen = [addr for addr in prev_never if addr not in out_fns or out_fns[addr]["overall"] == "not_hooked"]
        byp2 = collections.defaultdict(list)
        for addr, f in now_fire.items():
            byp2[prefix(f["name"])].append({"addr": addr, "name": f["name"], "overall": f["overall"], "calls": f["calls"], "by_scenario": f["by_scenario"]})
        tot2 = collections.Counter(prefix(n) for n in prev_never.values())
        cls2 = collections.Counter(f["overall"] for f in now_fire.values())
        print("\ncompare with %s: %d `never` there; %d fire here (%s); %d not hooked here" % (
            os.path.basename(a.compare), len(prev_never), len(now_fire), dict(cls2.most_common()), len(unseen)))
        for p, fs in sorted(byp2.items(), key=lambda x: -len(x[1])):
            print("  %-14s %3d / %3d  %s%s" % (p, len(fs), tot2[p], ", ".join("%s(%s)" % (f["name"], f["overall"]) for f in fs[:5]), " ..." if len(fs) > 5 else ""))
        compare = {"against": a.compare, "never_there": len(prev_never), "fire_here": len(now_fire), "fire_here_classes": dict(cls2),
                   "not_hooked_here": len(unseen), "by_prefix": {p: fs for p, fs in byp2.items()},
                   "still_never_by_prefix": {p: n for p, n in collections.Counter(prefix(nm) for addr, nm in prev_never.items() if addr not in now_fire).items()}}
    json.dump({"pass": a.pass_, "runs": runs_used, "overall": dict(overall), "per_scenario": {s: dict(c) for s, c in per_scn.items()},
               "zero_calls_by_prefix": {p: names for p, names in byp.items()}, "compare": compare, "functions": out_fns},
              open(a.json, "w", encoding="utf-8"), indent=1)
    print("\nwritten %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
