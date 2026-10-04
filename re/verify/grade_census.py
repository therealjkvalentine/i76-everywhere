#!/usr/bin/env python3
r"""grade_census.py - section 4.2 (census-grade), the script half (VERIFICATION-PROGRAM.md 4.2, 6).

    python verify\grade_census.py [--dry-run] [--only 0x46a320,...]

For every function with a canonical cadence-claim result (verify\queue\cadence-claim\<addr>.result.json; the
.sonnet. / .r2. / .v1. variants are ignored) whose enum is not `unknown`, compare the claim to the phase-1 census
(every runs\<scenario>\<ts>\census.classified.json whose manifest says census.attach_after_entity; the strongest
class per scenario, phase1_summary.RANK). The equivalences:

  claim == strongest class in every scenario                         -> PASS (script)
  per_substep claimed, per_frame observed on runs with 1 step/frame   -> PASS (script); runs with 2-step frames -> model
  per_event claimed, per_event/irregular bursts in >= 1 scenario and
      never elsewhere                                                 -> PASS (script)
  per_event claimed, 0 calls everywhere, event not in any scenario
      (save/load/spawn/key)                                           -> INCONCLUSIVE (no scenario)
  init_only claimed, 0 calls everywhere (hooks attach after the
      player entity exists, so mission init is never seen)            -> INCONCLUSIVE (early-attach census)
  per_frame claimed, 0 calls in every scenario                        -> FAIL (script)
  never claimed, calls seen                                           -> FAIL (script)
  menu_only claimed (no menu scenario yet)                            -> INCONCLUSIVE (no scenario)
  anything else                                                       -> census-grade unit for the model

Script verdicts are written as verify\queue\census-grade\<addr>.result.json with meta.graded_by = "script" and
meta.rule; model cases get a unit verify\queue\census-grade\<addr>.json (make_units.write_unit shape, one census
view per run plus the run's step histogram) for `worker.py --kind census-grade`. An existing result whose
meta.inputs_md5 differs from the inputs built here is rotated to <addr>.v<N>.result.json first (same convention
as the earlier calibration units) so the worker re-runs it on the phase-1 data. Nothing outside verify\queue\
census-grade\ is written; the game is not run.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blind  # noqa: E402
import make_units  # noqa: E402
from phase1_summary import RANK  # noqa: E402

VERIFY = blind.VERIFY
RUNS = VERIFY / "runs"
QUEUE = VERIFY / "queue"
KIND = "census-grade"

# events no phase-1 scenario produces (drive / fire-each / melee have shot, explosion, impact, damage)
EVENTS_NOT_IN_PHASE1 = {"save", "load", "spawn", "key"}
BURST = {"per_event", "irregular"}


# ----------------------------------------------------------------------------- inputs

def phase1_runs() -> list[dict]:
    """Every classified run whose manifest says attach_after_entity: {run_id, scenario, path, rows, events, steps}."""
    out = []
    for cp in sorted(glob.glob(str(RUNS / "*" / "*" / "census.classified.json"))):
        d = os.path.dirname(cp)
        mp = os.path.join(d, "manifest.json")
        if not os.path.exists(mp):
            continue
        man = json.load(open(mp, encoding="utf-8"))
        cs = man.get("census") or {}
        if not cs.get("attach_after_entity"):
            continue
        doc = json.load(open(cp, encoding="utf-8"))
        scenario, rows, events = make_units.load_census(Path(cp))
        out.append({"run_id": f"{scenario}/{os.path.basename(d)}", "scenario": scenario, "batch": cs.get("batch_id"),
                    "rows": rows, "events": events,
                    "steps": {"step_count_hist": doc.get("step_count_hist"), "steps_all_one": doc.get("steps_all_one"),
                              "frames_live": doc.get("frames_live"), "profile": doc.get("profile")}})
    return out


def canonical_claims() -> dict[str, dict]:
    """addr8 -> cadence-claim result (canonical file only), enum != unknown."""
    out = {}
    for p in sorted((QUEUE / "cadence-claim").glob("0x*.result.json")):
        if p.name.count(".") != 2:  # 0x401c90.result.json only
            continue
        try:
            res = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        pay = res.get("payload") or {}
        if pay.get("cadence") in (None, "unknown"):
            continue
        out[blind.addr8(p.name.split(".")[0])] = res
    return out


def strongest(classes: list[str]) -> str:
    return max(classes, key=lambda c: RANK.get(c, -1))


# ----------------------------------------------------------------------------- the rule

def grade_rule(claim: dict, per_scenario: dict[str, str], runs: list[dict]) -> tuple[str, str] | None:
    """(verdict, rule) for the script-gradable cases, None when a model must judge.

    per_scenario: scenario -> strongest class. runs: the per-run records for this function (each with 'class' and
    'steps'), used for the per_substep / 1-step equivalence."""
    c = claim["cadence"]
    obs = set(per_scenario.values())
    if not obs:
        return None
    if obs == {c}:
        return "PASS", "claim == observed in every scenario"
    all_never = obs == {"never"}
    if c == "per_substep":
        if obs <= {"per_substep", "per_frame"}:
            pf_runs = [r for r in runs if r["class"] == "per_frame"]
            if pf_runs and all(r["steps"].get("steps_all_one") for r in pf_runs):
                return "PASS", "per_substep claimed; per_frame observed only on runs with 1 step per frame"
        return None
    if c == "per_event":
        if (obs & BURST) and obs <= (BURST | {"never"}):
            return "PASS", "per_event claimed; bursts in >= 1 scenario, 0 calls where the event is absent"
        if all_never and claim.get("event") in EVENTS_NOT_IN_PHASE1:
            return "INCONCLUSIVE", f"per_event({claim.get('event')}) claimed; no phase-1 scenario produces that event"
        return None
    if c == "init_only":
        if all_never:
            return "INCONCLUSIVE", "init_only claimed, 0 calls: hooks attach after the player entity exists (early-attach census needed)"
        return None
    if c == "per_frame":
        if all_never:
            return "FAIL", "per_frame claimed, 0 calls in every mission scenario"
        return None
    if c == "never":
        return "FAIL", "never claimed, calls observed"
    if c == "menu_only":
        return "INCONCLUSIVE", "menu_only claimed; no menu scenario in phase 1"
    return None  # irregular and everything else: the model


# ----------------------------------------------------------------------------- outputs

def inputs_md5(inputs: dict) -> str:
    return hashlib.md5(json.dumps(inputs, sort_keys=True).encode("utf-8")).hexdigest()


def rotate_result(result: Path) -> str | None:
    """<addr>.result.json -> <addr>.v<N>.result.json (lowest free N); returns the new name.

    Suffixed results beside it (<addr>.sonnet.result.json, the Sonnet re-grade gate.py prefers over the canonical
    file) were graded on the same old inputs, so they rotate too (<addr>.sonnet.v<N>.result.json); otherwise a stale
    Sonnet verdict would outrank the fresh grade in gate.py."""
    if not result.exists():
        return None
    base = result.name[: -len(".result.json")]
    for sib in result.parent.glob(f"{base}.*.result.json"):
        suffix = sib.name[len(base) + 1: -len(".result.json")]
        if "." in suffix or re.fullmatch(r"v\d+", suffix) or re.fullmatch(r"v-old", suffix):
            continue  # already a rotated file
        m = 1
        while True:
            cand = sib.with_name(f"{base}.{suffix}.v{m}.result.json")
            if not cand.exists():
                sib.rename(cand)
                break
            m += 1
    n = 1
    while True:
        cand = result.with_name(f"{base}.v{n}.result.json")
        if not cand.exists():
            result.rename(cand)
            return cand.name
        n += 1


def result_inputs_md5(result_p: Path, unit_p: Path) -> str | None:
    """The inputs hash a result was graded on: meta.inputs_md5 (script grades), else the stamp on the unit file the
    worker answered (worker results carry no inputs_md5 in meta)."""
    try:
        oldres = json.loads(result_p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        oldres = {}
    md5 = (oldres.get("meta") or {}).get("inputs_md5")
    if md5 is None and unit_p.exists():
        try:
            md5 = json.loads(unit_p.read_text(encoding="utf-8")).get("inputs_md5")
        except (json.JSONDecodeError, OSError):
            md5 = None
    return md5


def build_inputs(a8: str, fnrow: dict, claim_res: dict, recs: list[dict], events_by_run: dict) -> dict:
    views = []
    for r in recs:
        v = make_units.census_view(r["row"])
        v["scenario"] = r["scenario"]
        v["run"] = r["run_id"]
        v["step_count_hist"] = r["steps"].get("step_count_hist")
        views.append(v)
    return {
        "name": fnrow.get("name") or f"FUN_{a8}",
        "subsystem": fnrow.get("subsystem", ""),
        "claim": claim_res["payload"],
        "claim_reason": claim_res.get("reason", ""),
        "census": views,
        "events": {r["run_id"]: events_by_run.get(r["run_id"], {}) for r in recs},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the grading, write nothing")
    ap.add_argument("--only", help="comma-separated addresses")
    ap.add_argument("--summary-json", help="also write the per-function grading table here (outside the repo)")
    args = ap.parse_args(argv)

    runs = phase1_runs()
    by_addr_fn = blind.functions_by_addr()
    claims = canonical_claims()
    only = {blind.addr8(a) for a in args.only.split(",")} if args.only else None

    # per function: the runs that hooked it
    recs_by_addr: dict[str, list[dict]] = {}
    events_by_run = {}
    for run in runs:
        events_by_run[run["run_id"]] = run["events"]
        for a8, row in run["rows"].items():
            recs_by_addr.setdefault(a8, []).append(
                {"run_id": run["run_id"], "scenario": run["scenario"], "batch": run["batch"], "row": row,
                 "class": row["classification"], "steps": run["steps"]})

    counts = Counter()
    table = []
    for a8, res in sorted(claims.items()):
        if only and a8 not in only:
            continue
        claim = res["payload"]
        fnrow = by_addr_fn.get(a8, {})
        recs = recs_by_addr.get(a8, [])
        name = fnrow.get("name") or f"FUN_{a8}"
        if not recs:
            counts["not-measured"] += 1
            table.append({"addr": blind.addr0x(a8), "name": name, "claim": claim["cadence"], "event": claim.get("event"),
                          "observed": {}, "outcome": "not-measured", "rule": "not hooked in phase 1 (hookable=%s)" % fnrow.get("hookable")})
            continue
        per_scn: dict[str, list[str]] = {}
        for r in recs:
            per_scn.setdefault(r["scenario"], []).append(r["class"])
        per_scenario = {s: strongest(cs) for s, cs in per_scn.items()}
        inputs = build_inputs(a8, fnrow, res, recs, events_by_run)
        md5 = inputs_md5(inputs)
        unit_p, result_p, esc_p = make_units.unit_paths(KIND, a8)
        graded = grade_rule(claim, per_scenario, recs)
        entry = {"addr": blind.addr0x(a8), "name": name, "claim": claim["cadence"], "event": claim.get("event"),
                 "observed": per_scenario, "calls": sum(int(r["row"].get("calls") or 0) for r in recs),
                 "runs": [r["run_id"] for r in recs]}
        if graded:
            verdict, rule = graded
            entry.update(outcome=verdict, rule=rule)
            counts[f"script-{verdict}"] += 1
            if not args.dry_run:
                old = None
                if result_p.exists() and result_inputs_md5(result_p, unit_p) != md5:
                    old = rotate_result(result_p)
                if not result_p.exists():
                    observed = strongest(list(per_scenario.values()))
                    result = {"unit_id": make_units.unit_id(KIND, a8), "verdict": verdict,
                              "payload": {"match": verdict == "PASS", "observed": observed,
                                          "note": f"claim {claim['cadence']}; observed {json.dumps(per_scenario, sort_keys=True)}"},
                              "reason": f"Graded by script (grade_census.py): {rule}.",
                              "meta": {"graded_by": "script", "rule": rule, "inputs_md5": md5,
                                       "scenarios": sorted(per_scenario), "runs": [r["run_id"] for r in recs],
                                       "rotated": old}}
                    unit_p.parent.mkdir(parents=True, exist_ok=True)
                    unit_p.write_text(json.dumps({"unit_id": result["unit_id"], "kind": KIND, "addr": blind.addr0x(a8),
                                                  "name": name, "inputs": inputs}, indent=1, ensure_ascii=False),
                                      encoding="utf-8")
                    result_p.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        else:
            entry.update(outcome="model", rule="needs a judgement")
            counts["model-unit"] += 1
            if not args.dry_run:
                if result_p.exists():
                    if result_inputs_md5(result_p, unit_p) == md5:
                        counts["model-unit-already-graded"] += 1
                    else:
                        rotate_result(result_p)
                if esc_p.exists():
                    esc_p.rename(esc_p.with_name(esc_p.name.replace(".escalate.json", ".v-old.escalate.json")))
                if not result_p.exists():
                    inputs_with_tag = dict(inputs)
                    state = make_units.write_unit(KIND, a8, name, inputs_with_tag, force=True)
                    # stamp the inputs hash on the unit so the worker's result can be matched to its inputs later
                    doc = json.loads(unit_p.read_text(encoding="utf-8"))
                    doc["inputs_md5"] = md5
                    unit_p.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
                    counts[f"unit-{state}"] += 1
        table.append(entry)

    print("grade_census:", dict(sorted(counts.items())))
    for e in table:
        if e["outcome"] in ("FAIL", "model", "not-measured"):
            print("  %-10s %-9s %-14s %-40s %s" % (e["outcome"], e["claim"], e.get("event") or "", e["name"],
                                                  json.dumps(e["observed"], sort_keys=True)))
    if args.summary_json:
        Path(args.summary_json).write_text(json.dumps({"counts": dict(counts), "table": table}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
