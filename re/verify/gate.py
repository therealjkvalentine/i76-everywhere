#!/usr/bin/env python3
r"""gate.py - the promotion gate (VERIFICATION-PROGRAM.md 2.8 / section 6), as a standalone script.

    python verify\gate.py [--date 2026-10-02] [--legacy-kinds] [--check] [--dry-run]

Reads every verification result and WRITES
  status\tasks\verify-<date>.json   the promotion batch (proposed -> supported, verification evidence rows);
                                    tools\merge.py applies it, this script never touches symbols\*.tsv
  verify\report.md                  counts by status before/after, per-prefix table, census FAILs, disputes, holds
  verify\disputes.tsv               rows a FAIL marks `disputed` for review (nothing is demoted by a script)

Evidence sources
  census   verify\queue\census-grade\<addr>.result.json (grade_census.py script grades + worker results) for the
           functions with a cadence claim; for functions without a claim the phase-1 census class itself is the
           cadence record (verify\runs\phase1-summary.json, strongest class over scenarios) when it is definite
           (per_frame / per_substep / per_event / init_only).
  oracle   verify\oracles\REPORT.md, "Claims these oracles now support": rows whose verdict is exactly PASS.
  blind    verify\queue\blind-judge\<addr>.result.json with <addr>.sonnet.result.json taking precedence (the
           Sonnet re-judge is final, BLIND-SAMPLE-2.md); same / compatible = PASS. A second independent reader
           (make_units.py blind-judge --reader reader2 over worker.py --suffix reader2 blind-name results) is
           <addr>.reader2.json / <addr>.reader2.result.json; it is the second reader of the section 6 utility
           rule (two blind PASS -> supported; two `different` -> disputes.tsv).

Section 6 rules applied: function -> supported when census PASS and (oracle PASS or blind PASS), or when two independent
blind readers (reader "1": <addr>.result.json, reader "2": <addr>.reader2.result.json) were both judged same/compatible
(the section 6 utility rule, applied to any prefix since blind pass 4: functions the scenarios never run have no census);
utility functions (math_, heap_, vfs_, crt_) with one reader PASS are held; blind `different` from both readers ->
disputes.tsv (any prefix, review only). A field -> supported on oracle PASS (only rows that exist in symbols\globals.tsv
can be promoted). census FAIL -> disputes.tsv. Batch rows carry conv auto / auto:paramid (merge.py gate K) and each
blind evidence row carries `reader` "1" / "2" (merge.py gate_g1_g2 two-reader rule).

Evidence kinds: by default the rows carry the section 2.8 kinds `census` / `oracle` / `blind` with claims starting
"verification (<kind>): ...". tools\merge.py gate_evidence_common accepts any kind (it checks only `kind` + the
pristine md5, and `method` beside a count), but gate_g1_g2 counts only its PRIMARY / SECONDARY vocabulary for
`supported`, so these rows are rejected there until merge.py learns the kinds. --legacy-kinds instead emits
`dynamic-capture` (census, oracle: primary, capture_id = the run ids) and `struct-access` (blind: secondary) with the
same claim text, which gate_g1_g2 accepts today. --check imports tools\merge.py and runs its pure gates
(gate_evidence_common, gate_g1_g2) over the batch rows in memory to predict the verdict; no map file is read or
written by that.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blind  # noqa: E402
from phase1_summary import RANK  # noqa: E402

VERIFY = blind.VERIFY
ROOT = blind.ROOT
QUEUE = VERIFY / "queue"
RUNS = VERIFY / "runs"
PRISTINE_MD5 = "9a232dcc2c164648cff20c414c1f9698"
DEFINITE = {"per_frame", "per_substep", "per_event", "init_only"}
UTILITY_PREFIXES = {"math", "heap", "vfs", "crt"}  # section 6 "utility (math_, heap_, vfs_, string)"; strings are crt_ here
ORACLE_REPORT = VERIFY / "oracles" / "REPORT.md"
# oracle rows the report itself qualifies; held, not promoted (reason quoted from REPORT.md)
ORACLE_HOLDS = {
    "0x4fe420": "step_count PASS used it but 'indistinguishable from 0x4fe428 here' (sim_dt and dt are equal on every frame): the oracle cannot tell the two names apart",
}
# functions named in REPORT.md outside the support table, with the report's own words (no PASS to credit)
ORACLE_MENTIONS = {
    "0x46a0c0": "physics_ShiftCurveTest: engine_gear 'treats every throttle >= 0.0625 as the full set (the interpolated ShiftCurveTest never passes)'; the oracle never exercised it, so no oracle PASS",
}
CENSUS_METHOD = ("Frida hook census (verify/census_frames.js): per-frame call counts and return sites over scripted "
                 "scenarios, class by verify/census.py classify; graded by verify/grade_census.py")


# ----------------------------------------------------------------------------- loaders

def canonical_results(kind: str) -> dict[str, dict]:
    out = {}
    for p in sorted((QUEUE / kind).glob("0x*.result.json")):
        if p.name.count(".") != 2:
            continue
        try:
            out[blind.addr8(p.name.split(".")[0])] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return out


def blind_final(reader: str = "") -> dict[str, dict]:
    """addr8 -> {agreement, judge_model, file, blind_name, blind_contract, confidence}; sonnet overrides haiku.
    With `reader` = S: the second-reader set (<addr>.S.json judge units over <addr>.S.result.json readings)."""
    out = {}
    d = QUEUE / "blind-judge"
    names = {}
    for p in sorted((QUEUE / "blind-name").glob(f"0x*.{reader}.result.json" if reader else "0x*.result.json")):
        if p.name.count(".") != (3 if reader else 2):
            continue
        try:
            names[blind.addr8(p.name.split(".")[0])] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    for unit_p in sorted(d.glob(f"0x*.{reader}.json" if reader else "0x*.json")):
        if unit_p.name.count(".") != (2 if reader else 1):
            continue
        a8 = blind.addr8(unit_p.name.split(".")[0])
        son = unit_p.with_name(unit_p.stem + ".sonnet.result.json")
        hai = unit_p.with_name(unit_p.stem + ".result.json")
        src = son if son.exists() else hai if hai.exists() else None
        if src is None:
            continue
        res = json.loads(src.read_text(encoding="utf-8"))
        unit = json.loads(unit_p.read_text(encoding="utf-8"))
        hidden = unit.get("hidden") or {}
        bn = names.get(a8) or {}
        out[a8] = {"agreement": (res.get("payload") or {}).get("agreement"),
                   "judge_model": (res.get("meta") or {}).get("model", "?"),
                   "file": src.relative_to(ROOT).as_posix(),
                   "blind_name": hidden.get("blind_name") or (bn.get("payload") or {}).get("name"),
                   "blind_contract": (bn.get("payload") or {}).get("contract", ""),
                   "reader_model": (bn.get("meta") or {}).get("model", "?"),
                   "reader_effort": (bn.get("meta") or {}).get("effort"),
                   "reader": reader or None,
                   "confidence": hidden.get("blind_confidence")}
    return out


def oracle_support() -> dict[str, list[dict]]:
    """addr -> [{oracle, verdict, text, supports}] parsed from the report's 'Claims these oracles now support' table."""
    out: dict[str, list[dict]] = defaultdict(list)
    if not ORACLE_REPORT.exists():
        return out
    txt = ORACLE_REPORT.read_text(encoding="utf-8")
    sec = txt.split("## Claims these oracles now support", 1)
    if len(sec) < 2:
        return out
    for line in sec[1].splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| oracle"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        oracle, verdict, what, supports = cells[:4]
        for a in re.findall(r"0x[0-9a-fA-F]{5,8}", what):
            out[blind.addr8(a)].append({"oracle": oracle, "verdict": verdict, "text": what, "supports": supports})
    return out


def oracle_runs() -> list[str]:
    txt = ORACLE_REPORT.read_text(encoding="utf-8") if ORACLE_REPORT.exists() else ""
    m = re.search(r"Runs: (.+?)\. PASS", txt)
    return [r.strip().split(" ")[0] for r in m.group(1).split(",")] if m else []


def prefix_of(row: dict) -> str:
    """functions.tsv `subsystem`, else the name prefix; rows with neither a subsystem nor a prefix_ name are '(other)'."""
    if row.get("subsystem"):
        return row["subsystem"]
    return row["name"].split("_")[0] if "_" in row["name"] else "(other)"


# ----------------------------------------------------------------------------- evidence rows

def ev_census(addr0x: str, legacy: bool, observed: str, runs: list[str], scenarios: dict, calls: int, graded_by: str,
              claim_cadence: str | None, result_file: str) -> dict:
    scen = ", ".join(f"{s}={c}" for s, c in sorted(scenarios.items()))
    if claim_cadence:
        head = f"verification (census): cadence claim {claim_cadence} graded PASS by {graded_by}; observed {observed} ({scen})"
    else:
        head = f"verification (census): no cadence claim in the contract; the census is the cadence record: {observed} ({scen})"
    ev = {"kind": "dynamic-capture" if legacy else "census", "md5": PRISTINE_MD5, "site": addr0x,
          "claim": f"{head}; {calls} calls over {len(runs)} phase-1 runs ({'; '.join(runs)}); {result_file}",
          "method": CENSUS_METHOD, "n": calls, "runs": runs, "instrument-checked": "verify/runs/PROGRESS.md (per-run checks)"}
    if legacy:
        ev["capture_id"] = ";".join(runs)
    return ev


def ev_blind(addr0x: str, legacy: bool, b: dict) -> dict:
    who = f"{b['reader_model']}" + (f", second reader, effort {b.get('reader_effort')}" if b.get("reader") else "")
    # `reader` "1" / "2": tools/merge.py gate_g1_g2 counts two blind rows with distinct reader tags as one primary kind
    return {"kind": "struct-access" if legacy else "blind", "md5": PRISTINE_MD5, "site": addr0x,
            "claim": (f"verification (blind): cold reading of the stripped decompilation ({who}) named it "
                      f"'{b['blind_name']}' ({b.get('confidence')}): {b['blind_contract'][:300]}; judged '{b['agreement']}' "
                      f"by {b['judge_model']} ({b['file']}; verify/BLIND-SAMPLE-2.md, verify/BLIND-PASS-3.md, verify/BLIND-PASS-4.md)"),
            "reader": "2" if b.get("reader") else "1"}


def ev_oracle(addr0x: str, legacy: bool, rows: list[dict], runs: list[str]) -> dict:
    parts = "; ".join(f"{r['oracle']}: {r['supports']}" for r in rows)
    ev = {"kind": "dynamic-capture" if legacy else "oracle", "md5": PRISTINE_MD5, "site": addr0x,
          "claim": f"verification (oracle): {parts} (verify/oracles/REPORT.md, PASS on {len(runs)} recorded drive runs: {', '.join(runs)})",
          "method": "verify/oracle_run.py --all: spec equation re-implemented in Python, compared frame by frame to the recorded telemetry.csv within verify/tolerances.json",
          "runs": runs}
    if legacy:
        ev["capture_id"] = ";".join(runs)
    return ev


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default="2026-10-02")
    ap.add_argument("--legacy-kinds", action="store_true", help="dynamic-capture / struct-access instead of census / oracle / blind")
    ap.add_argument("--check", action="store_true", help="predict tools/merge.py gate_evidence_common + gate_g1_g2 on the rows")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary", default=str(RUNS / "phase1-summary.json"),
                    help="phase1_summary.py output to read the census record from (default runs/phase1-summary.json; "
                         "runs/phase1-all-summary.json is the combined entity + early + never-pass view)")
    args = ap.parse_args(argv)

    funcs = blind.load_functions()
    by_addr = {blind.addr8(r["addr"]): r for r in funcs}
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    sfn = summary["functions"]
    # the never-pass batches (verify/batches/never-*.json) re-hooked functions whose first batch never ran them; the
    # summary's `batch` is the first batch, so the never batch is looked up here for the census evidence run list
    never_batch_of = {}
    for bp in sorted(glob.glob(str(VERIFY / "batches" / "never-*.json"))):
        if "excluded" in os.path.basename(bp):
            continue
        b = json.loads(Path(bp).read_text(encoding="utf-8"))
        for f in b.get("functions", []):
            never_batch_of[blind.addr8(f["addr"])] = b["batch"]
    cg = canonical_results("census-grade")
    # a Haiku census-grade FAIL re-graded by Sonnet (`worker.py --model sonnet --suffix sonnet`) takes Sonnet's verdict,
    # the same rule the blind step uses (section 10: a small model's negative verdict is not evidence by itself)
    regraded = 0
    for p in sorted((QUEUE / "census-grade").glob("0x*.sonnet.result.json")):
        a8 = blind.addr8(p.name.split(".")[0])
        try:
            son = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        hai = cg.get(a8)
        if hai is not None:
            son.setdefault("meta", {})["haiku_verdict"] = hai.get("verdict")
            son["meta"]["runs"] = (hai.get("meta") or {}).get("runs")
        cg[a8] = son
        regraded += 1
    cc = canonical_results("cadence-claim")
    runs_of_batch = defaultdict(list)
    for r in summary.get("runs", []):
        runs_of_batch[r.get("batch")].append(f"{r['scenario']}/{os.path.basename(r['run'])}")
    summary_rel = Path(args.summary).resolve().relative_to(ROOT).as_posix() if Path(args.summary).resolve().is_relative_to(ROOT) else args.summary

    def census_runs(a8: str, s: dict | None) -> list[str]:
        """Run ids behind a no-claim census record: the function's first batch plus its never-pass batch, limited to the
        scenarios the summary saw it hooked in."""
        s = s or {}
        scen = set(s.get("by_scenario") or {})
        out = []
        for b in (s.get("batch"), never_batch_of.get(a8)):
            for rid in runs_of_batch.get(b, []) if b else []:
                if (not scen or rid.split("/")[0] in scen) and rid not in out:
                    out.append(rid)
        return out
    bl = blind_final()
    bl2 = blind_final("reader2")
    orc = oracle_support()
    orc_runs = oracle_runs()
    globals_rows = {blind.addr8(r["addr"]): r for r in blind.load_globals()}

    before = Counter(r["status"] for r in funcs)
    per_prefix = defaultdict(Counter)
    promoted, disputes, holds, info = [], [], [], defaultdict(list)
    census_pass = {}

    for a8, row in sorted(by_addr.items()):
        pfx = prefix_of(row)
        st = row["status"]
        per_prefix[pfx]["rows"] += 1
        per_prefix[pfx][st] += 1
        s = sfn.get(blind.addr0x(a8))
        claim = (cc.get(a8) or {}).get("payload") or {}
        claim_cad = claim.get("cadence") if claim.get("cadence") not in (None, "unknown") else None
        grade = cg.get(a8)
        # ---- census
        cpass = None
        if grade:
            meta = grade.get("meta") or {}
            gb = "script" if meta.get("graded_by") == "script" else meta.get("model", "model")
            if grade["verdict"] == "PASS":
                cpass = {"observed": grade["payload"]["observed"], "graded_by": gb, "claim": claim_cad,
                         "file": f"verify/queue/census-grade/{blind.addr0x(a8)}.result.json"}
            elif grade["verdict"] == "FAIL":
                per_prefix[pfx]["census_FAIL"] += 1
                disputes.append({"addr": blind.addr0x(a8), "name": row["name"], "status": st, "kind": "census",
                                 "claim": f"{claim_cad}" + (f"({claim.get('event')})" if claim.get("event") else ""),
                                 "observed": grade["payload"]["observed"], "graded_by": gb,
                                 "evidence": f"verify/queue/census-grade/{blind.addr0x(a8)}.result.json; runs {'; '.join(meta.get('runs') or [])}",
                                 "note": (grade.get("reason") or "")[:300],
                                 "claim_reason": ((cc.get(a8) or {}).get("reason") or "")[:300]})
            else:
                rule = (grade.get("meta") or {}).get("rule", "")
                key = "inconclusive_early_attach" if "early-attach" in rule else "inconclusive_other"
                per_prefix[pfx][key] += 1
                info[key].append((blind.addr0x(a8), row["name"], claim_cad, (grade.get("reason") or "")[:160]))
        elif s and s.get("overall") in DEFINITE and not claim_cad:
            cpass = {"observed": s["overall"], "graded_by": "census record (no claim)", "claim": None,
                     "file": summary_rel}
        elif s and s.get("overall") in DEFINITE and claim_cad:
            info["claim_not_graded"].append((blind.addr0x(a8), row["name"], claim_cad, s["overall"]))
        if s and s.get("overall") == "irregular" and not grade:
            per_prefix[pfx]["irregular_no_claim"] += 1
        if s and s.get("overall") == "never":
            per_prefix[pfx]["never"] += 1
        if cpass:
            per_prefix[pfx]["census_PASS"] += 1
            census_pass[a8] = cpass
        # ---- blind
        b = bl.get(a8)
        bpass = b if b and b["agreement"] in ("same", "compatible") else None
        if b:
            per_prefix[pfx]["blind_judged"] += 1
            if bpass:
                per_prefix[pfx]["blind_PASS"] += 1
            else:
                per_prefix[pfx]["blind_different"] += 1
                info["blind_different"].append((blind.addr0x(a8), row["name"], b["blind_name"], b["judge_model"]))
        b2 = bl2.get(a8)
        bpass2 = b2 if b2 and b2["agreement"] in ("same", "compatible") else None
        if b2:
            per_prefix[pfx]["blind2_judged"] += 1
            if not bpass2:
                info["blind2_different"].append((blind.addr0x(a8), row["name"], b2["blind_name"], b2["judge_model"]))
        # ---- oracle
        orows = [r for r in orc.get(a8, []) if r["verdict"] == "PASS"]
        oother = [r for r in orc.get(a8, []) if r["verdict"] != "PASS"]
        if blind.addr0x(a8) in ORACLE_HOLDS and orows:
            holds.append((blind.addr0x(a8), row["name"], "oracle", ORACLE_HOLDS[blind.addr0x(a8)]))
            orows = []
        if blind.addr0x(a8) in ORACLE_MENTIONS:
            holds.append((blind.addr0x(a8), row["name"], "oracle", ORACLE_MENTIONS[blind.addr0x(a8)]))
        if orows:
            per_prefix[pfx]["oracle_PASS"] += 1
        for r in oother:
            holds.append((blind.addr0x(a8), row["name"], "oracle", f"{r['oracle']} verdict {r['verdict']}: {r['supports'][:140]} (not a PASS)"))
        # ---- rule
        if st != "proposed":
            continue
        # Batch rows carry conv "auto" / "auto:paramid": a verification row makes no convention claim, and a row that
        # repeats the TSV's `__cdecl` without a call-cleanup evidence row trips merge.py gate K (verify-2026-10-02b).
        base_row = {"addr": blind.addr0x(a8), "name": row["name"], "status": "supported",
                    "conv": "auto", "conv_evidence": "auto:paramid", "subsystem": row.get("subsystem") or pfx, "_prefix": pfx}
        if row.get("conv") and row.get("conv") != "auto":
            info["conv_reset"].append((blind.addr0x(a8), row["name"], row.get("conv"), row.get("conv_evidence")))
        if bpass and bpass2:
            # two independent readers, both judged same/compatible: one primary kind in merge.py gate_g1_g2 (distinct
            # `reader` tags). Section 6 wrote this rule for utility functions; it applies to any prefix since pass 4
            # (functions the scenarios never run have no census to pair a single reading with).
            evs = [ev_blind(blind.addr0x(a8), args.legacy_kinds, bpass), ev_blind(blind.addr0x(a8), args.legacy_kinds, bpass2)]
            route = ["blind", "blind2"]
            if cpass:
                runs_ = ((grade or {}).get("meta") or {}).get("runs") or census_runs(a8, s)
                per_scn = {k: max(v, key=lambda c: RANK.get(c, -1)) for k, v in (s or {}).get("by_scenario", {}).items()}
                evs.insert(0, ev_census(blind.addr0x(a8), args.legacy_kinds, cpass["observed"], runs_, per_scn,
                                        int((s or {}).get("calls") or 0), cpass["graded_by"], cpass["claim"], cpass["file"]))
                route.insert(0, "census")
            if orows:
                evs.append(ev_oracle(blind.addr0x(a8), args.legacy_kinds, orows, orc_runs)); route.append("oracle")
            promoted.append({**base_row, "evidence": evs, "_route": "+".join(route)})
            per_prefix[pfx]["promoted"] += 1
            per_prefix[pfx]["two_readers"] += 1
            continue
        if b and b2 and not bpass and not bpass2:
            # the negative of the two-reader rule (section 6 "blind `different` from both"): listed for review, never demoted
            disputes.append({"addr": blind.addr0x(a8), "name": row["name"], "status": st, "kind": "blind",
                             "claim": row["name"], "observed": f"{b['blind_name']} / {b2['blind_name']}", "graded_by": b["judge_model"],
                             "evidence": f"{b['file']}; {b2['file']}",
                             "note": "two-reader rule (section 6): blind `different` from both readers" + ("" if pfx in UTILITY_PREFIXES else f" ({pfx}, non-utility; read in verify/BLIND-PASS-4.md)"),
                             "claim_reason": ""})
            per_prefix[pfx]["two_readers_different"] += 1
            if not (cpass and orows):  # census + oracle would still qualify below
                if cpass:
                    per_prefix[pfx]["census_only"] += 1
                continue
        if pfx in UTILITY_PREFIXES:
            if bpass or bpass2:
                one = bpass or bpass2
                holds.append((blind.addr0x(a8), row["name"], "utility", f"blind PASS from one reader ({one['judge_model']} judged {one['agreement']}"
                              + (f"; the other reader judged {(b2 if one is bpass else b)['agreement']}" if (b and b2) else "") + "); section 6 needs two readers"))
                per_prefix[pfx]["utility_one_reader"] += 1
            continue
        if cpass and (orows or bpass or bpass2):
            # run ids for the census evidence: a grade result carries them; otherwise the batch's phase-1 runs
            runs_ = ((grade or {}).get("meta") or {}).get("runs") or census_runs(a8, s)
            per_scn = {k: max(v, key=lambda c: RANK.get(c, -1)) for k, v in (s or {}).get("by_scenario", {}).items()}
            evs = [ev_census(blind.addr0x(a8), args.legacy_kinds, cpass["observed"], runs_, per_scn,
                             int((s or {}).get("calls") or 0), cpass["graded_by"], cpass["claim"], cpass["file"])]
            route = []
            if orows:
                evs.append(ev_oracle(blind.addr0x(a8), args.legacy_kinds, orows, orc_runs)); route.append("oracle")
            if bpass:
                evs.append(ev_blind(blind.addr0x(a8), args.legacy_kinds, bpass)); route.append("blind")
            if bpass2:
                evs.append(ev_blind(blind.addr0x(a8), args.legacy_kinds, bpass2)); route.append("blind2")
            promoted.append({**base_row, "evidence": evs, "_route": "census+" + "+".join(route)})
            per_prefix[pfx]["promoted"] += 1
        elif cpass:
            per_prefix[pfx]["census_only"] += 1
        elif orows or bpass or bpass2:
            per_prefix[pfx]["name_evidence_no_census"] += 1
            if (bpass or bpass2) and (b and b2):
                per_prefix[pfx]["one_reader_of_two"] += 1

    # ---- globals from the oracle table
    promoted_globals = []
    for a8, rows in orc.items():
        g = globals_rows.get(a8)
        if not g:
            if a8 not in by_addr:
                holds.append((blind.addr0x(a8), "(no row)", "oracle-field", f"{rows[0]['oracle']} {rows[0]['verdict']}: {rows[0]['text'][:80]} has no row in symbols/globals.tsv or tables.tsv; nothing to promote"))
            continue
        prows = [r for r in rows if r["verdict"] == "PASS"]
        if blind.addr0x(a8) in ORACLE_HOLDS:
            holds.append((blind.addr0x(a8), g["name"], "oracle-field", ORACLE_HOLDS[blind.addr0x(a8)]))
            continue
        if prows and g["status"] == "proposed":
            promoted_globals.append({"addr": blind.addr0x(a8), "class": g["class"], "name": g["name"], "status": "supported",
                                     "evidence": [ev_oracle(blind.addr0x(a8), args.legacy_kinds, prows, orc_runs)]})

    # ---- batch
    batch = {
        "batch": f"verify-{args.date}",
        "author": (f"verify/gate.py {args.date}: VERIFICATION-PROGRAM.md section 6 over verify/queue/census-grade (grade_census.py + "
                   f"worker haiku), verify/oracles/REPORT.md, verify/queue/blind-judge (Sonnet-final); evidence kinds "
                   f"{'dynamic-capture/struct-access (legacy vocabulary)' if args.legacy_kinds else 'census/oracle/blind (section 2.8)'}; nothing demoted"),
        "functions": [{k: v for k, v in r.items() if not k.startswith("_")} for r in promoted],
        "globals": promoted_globals,
    }
    # conv_reset was collected for every proposed row; the report line is about the rows this batch promotes
    promoted_addrs = {r["addr"] for r in promoted}
    info["conv_reset"] = [t for t in info["conv_reset"] if t[0] in promoted_addrs]
    after = Counter(before)
    after["proposed"] -= len(promoted)
    after["supported"] += len(promoted)

    # ---- --check: merge.py's pure gates in memory
    check_lines = []
    if args.check:
        sys.path.insert(0, str(ROOT / "tools"))
        try:
            import merge  # noqa: E402
            for r in batch["functions"] + batch["globals"]:
                try:
                    evs = [dict(e) for e in r["evidence"]]
                    for e in evs:
                        merge.gate_evidence_common(e)
                    merge.gate_g1_g2(r, evs)
                    check_lines.append(f"ACCEPT(G2) {r['addr']} {r['name']}")
                except merge.Reject as ex:
                    check_lines.append(f"REJECT {r['addr']} {r['name']}: {ex}")
        except Exception as ex:  # capstone / gen_tables missing
            check_lines.append(f"(could not import tools/merge.py: {ex})")

    # ---- cost (journal)
    cost = Counter(); calls = Counter()
    jp = VERIFY / "journal.jsonl"
    if jp.exists():
        for line in jp.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            k = d.get("kind")
            cost[k] += float(d.get("cost_usd") or 0); calls[k] += 1
            if k == "census-grade" and str(d.get("ts", "")).startswith(args.date):
                cost["census-grade (today)"] += float(d.get("cost_usd") or 0); calls["census-grade (today)"] += 1

    # ---- report
    L = []
    L.append(f"# Verification gate report ({args.date})\n")
    L.append("Written by `verify/gate.py` (VERIFICATION-PROGRAM.md 2.8 / section 6). The game was not run; every number comes from "
             "result files under `verify/`. Nothing is demoted; FAILs are listed in `verify/disputes.tsv` for review. The batch "
             f"`status/tasks/verify-{args.date}.json` is written here and applied by `tools/merge.py` (not by this script).\n")
    L.append("## Inputs\n")
    L.append(f"- phase-1 census: {len(summary['runs'])} runs, {len(sfn)} functions seen (`{summary_rel}`); "
             f"cadence claims: {sum(1 for v in cc.values() if (v.get('payload') or {}).get('cadence') not in (None, 'unknown'))} with an enum "
             f"of {len(cc)} canonical results; census-grade results: {len(cg)} "
             f"({sum(1 for g in cg.values() if (g.get('meta') or {}).get('graded_by') == 'script')} script, "
             f"{sum(1 for g in cg.values() if (g.get('meta') or {}).get('graded_by') != 'script')} model)")
    L.append(f"- oracle: `verify/oracles/REPORT.md`, {len(orc_runs)} recorded drive runs; rows with verdict PASS in 'Claims these oracles now support'")
    L.append(f"- blind: {len(bl)} judged functions (final = Sonnet re-judge where present): "
             f"{Counter(b['agreement'] for b in bl.values()).most_common()}; second reader (`reader2`): {len(bl2)} judged: "
             f"{Counter(b['agreement'] for b in bl2.values()).most_common()}\n")
    L.append("## Functions by status\n")
    L.append("| status | before | after |\n|---|---|---|")
    for stt in ("anchored", "supported", "proposed", "synthetic", "library", "auto"):
        if before.get(stt) or after.get(stt):
            L.append(f"| {stt} | {before.get(stt, 0)} | {after.get(stt, 0)} |")
    L.append(f"\n**{len(promoted)} functions qualify for `supported`** (census PASS and oracle or blind PASS; or two independent blind PASS, "
             f"any prefix, since pass 4): {Counter(r['_route'] for r in promoted).most_common()}; {len(promoted_globals)} globals (oracle PASS).\n")
    if info["conv_reset"]:
        L.append(f"Batch rows carry conv `auto` / `auto:paramid` (gate K); {len(info['conv_reset'])} promoted rows had another conv in functions.tsv, "
                 "which the merge will reset: " + ", ".join(f"{n} {a} ({c}; {ce})" for a, n, c, ce in info["conv_reset"]) + "\n")
    L.append("## Census outcomes (functions with a cadence claim)\n")
    gv = Counter()
    for g in cg.values():
        gb = "script" if (g.get("meta") or {}).get("graded_by") == "script" else "model"
        gv[(g["verdict"], gb)] += 1
    L.append("| verdict | script | model |\n|---|---|---|")
    for v in ("PASS", "FAIL", "INCONCLUSIVE"):
        L.append(f"| {v} | {gv.get((v, 'script'), 0)} | {gv.get((v, 'model'), 0)} |")
    if regraded:
        flips = Counter((g["meta"].get("haiku_verdict"), g["verdict"]) for g in cg.values() if (g.get("meta") or {}).get("haiku_verdict"))
        L.append(f"\nModel column: Haiku first; its {regraded} FAILs were re-graded by Sonnet (`--suffix sonnet`), whose verdict is final "
                 f"(Haiku -> Sonnet: {sorted(flips.items())}).")
    L.append(f"\nFunctions without a claim (no cadence vocabulary, or claim `unknown`) take the census class as their cadence record; "
             f"{sum(1 for c in census_pass.values() if c['claim'] is None)} of them have a definite class.\n")
    L.append("## Per prefix\n")
    cols = ["rows", "proposed", "supported", "anchored", "census_PASS", "census_FAIL", "inconclusive_early_attach", "never",
            "blind_judged", "blind_PASS", "blind_different", "blind2_judged", "oracle_PASS", "promoted", "census_only",
            "two_readers", "two_readers_different", "one_reader_of_two", "utility_one_reader"]
    L.append("| prefix | " + " | ".join(cols) + " |")
    L.append("|---|" + "---|" * len(cols))
    tot = Counter()
    for pfx in sorted(per_prefix, key=lambda p: -per_prefix[p]["rows"]):
        c = per_prefix[pfx]
        tot.update(c)
        L.append(f"| {pfx} | " + " | ".join(str(c.get(k, 0)) for k in cols) + " |")
    L.append("| **all** | " + " | ".join(f"**{tot.get(k, 0)}**" for k in cols) + " |")
    L.append("\n`census_only` = census PASS but no oracle/blind evidence yet (the blind sample covered 300 of 1,882 proposed rows); "
             "`never` = 0 calls in every phase-1 scenario; `inconclusive_early_attach` = init_only claimed, 0 calls because the hooks "
             "attach after the player entity exists (early-attach census pending).\n")
    L.append(f"## Census FAIL ({sum(1 for d in disputes if d['kind'] == 'census')}) and blind `different` from both readers "
             f"({sum(1 for d in disputes if d['kind'] == 'blind')}) -> `verify/disputes.tsv`\n")
    L.append("Script rule: per_frame claimed and 0 calls in every mission scenario (or never claimed and calls seen). Model rule "
             "(census-grade prompt): the observation contradicts the claim. The reviewer notes at the end of this file read each one.\n")
    L.append("| addr | name | claim | observed | graded by | observation | claim reason |\n|---|---|---|---|---|---|---|")
    for d in disputes:
        L.append(f"| {d['addr']} | {d['name']} | {d['claim']} | {d['observed']} | {d['graded_by']} | {d['note'][:220]} | {d['claim_reason'][:160]} |")
    L.append(f"\n## INCONCLUSIVE awaiting the early-attach census ({len(info['inconclusive_early_attach'])})\n")
    L.append(", ".join(f"{n} {a}" for a, n, _, _ in info["inconclusive_early_attach"]) or "(none)")
    L.append(f"\n## Other INCONCLUSIVE ({len(info['inconclusive_other'])})\n")
    for a, n, c, r in info["inconclusive_other"]:
        L.append(f"- {a} {n}: claim {c}; {r}")
    L.append(f"\n## Blind `different` ({len(info['blind_different'])}; not disputes under section 6 for non-utility rows, each read in BLIND-SAMPLE-2.md / BLIND-PASS-3.md)\n")
    L.append(", ".join(f"{n} (blind: {bn})" for a, n, bn, _ in info["blind_different"]) or "(none)")
    L.append(f"\n## Second reader (`reader2`) `different` ({len(info['blind2_different'])})\n")
    L.append(", ".join(f"{n} (blind: {bn})" for a, n, bn, _ in info["blind2_different"]) or "(none)")
    L.append(f"\n## Holds ({len(holds)})\n")
    for a, n, k, why in holds:
        L.append(f"- {a} {n} [{k}]: {why}")
    L.append("\n## Evidence kinds and merge.py\n")
    L.append("`tools/merge.py gate_evidence_common` accepts any `kind` (it checks the pristine md5 and that a count carries a method), "
             "but `gate_g1_g2` promotes to `supported` only with >= 2 kinds from its PRIMARY/SECONDARY vocabulary and >= 1 primary. "
             + ("This batch uses the legacy vocabulary (`dynamic-capture` for census/oracle with capture_id = run ids, `struct-access` for blind), "
                "claim text prefixed `verification (<kind>):`, so G2 accepts the census+blind rows today; a census+oracle-only row collapses "
                "to one kind and is still rejected." if args.legacy_kinds else
                "This batch uses the section 2.8 kinds `census` / `oracle` / `blind`; G2 rejects every row until `census`, `oracle` join "
                "PRIMARY and `blind` joins SECONDARY in merge.py (one-line edit), or regenerate with `gate.py --legacy-kinds`."))
    if check_lines:
        L.append("\n### --check (merge.py pure gates, in memory)\n")
        cc_ = Counter(l.split(" ")[0] for l in check_lines)
        L.append(f"{dict(cc_)}; every REJECT, then the first accepts:\n")
        L.extend(f"    {l}" for l in [x for x in check_lines if x.startswith("REJECT")] + [x for x in check_lines if not x.startswith("REJECT")][:4])
    L.append("\n## Cost (verify/journal.jsonl)\n")
    L.append("| kind | calls | USD |\n|---|---|---|")
    for k in sorted(cost):
        L.append(f"| {k} | {calls[k]} | {cost[k]:.3f} |")
    L.append(f"| **all** | {sum(v for k, v in calls.items() if '(today)' not in k)} | {sum(v for k, v in cost.items() if '(today)' not in k):.3f} |")
    # hand-written review notes after the marker survive a re-run
    marker = "<!-- reviewer notes: everything below this line is hand-written and kept by gate.py -->"
    notes = ""
    rp = VERIFY / "report.md"
    if rp.exists() and marker in rp.read_text(encoding="utf-8"):
        notes = rp.read_text(encoding="utf-8").split(marker, 1)[1]
    report = "\n".join(L) + "\n\n" + marker + notes + ("\n" if not notes.endswith("\n") else "")

    # ---- disputes.tsv
    dcols = ["addr", "name", "status", "kind", "claim", "observed", "graded_by", "evidence", "note", "claim_reason"]
    dl = ["# verify/disputes.tsv - rows a verification FAIL marks `disputed` (VERIFICATION-PROGRAM.md 2.8 / 6); written by verify/gate.py, nothing demoted",
          "\t".join(dcols)]
    for d in disputes:
        dl.append("\t".join(str(d.get(c, "")).replace("\t", " ").replace("\n", " ") for c in dcols))
    disputes_tsv = "\n".join(dl) + "\n"

    if args.dry_run:
        print(report)
        print(f"(dry run) batch rows: {len(batch['functions'])} functions, {len(batch['globals'])} globals")
        return
    out_batch = ROOT / "status" / "tasks" / f"verify-{args.date}.json"
    out_batch.write_text(json.dumps(batch, indent=1, ensure_ascii=False), encoding="utf-8")
    (VERIFY / "report.md").write_text(report, encoding="utf-8")
    (VERIFY / "disputes.tsv").write_text(disputes_tsv, encoding="utf-8")
    print(f"wrote {out_batch} ({len(batch['functions'])} functions, {len(batch['globals'])} globals), verify/report.md, verify/disputes.tsv ({len(disputes)} rows)")
    for l in check_lines[:10]:
        print(" ", l)


if __name__ == "__main__":
    main()
