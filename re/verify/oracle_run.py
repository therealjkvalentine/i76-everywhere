r"""oracle_run.py - run a spec oracle against a recorded telemetry run (VERIFICATION-PROGRAM.md section 2.4).

    python verify/oracle_run.py <oracle> <run-dir> [--tolerances verify/tolerances.json] [--json out.json]
    python verify/oracle_run.py --all [--runs "verify/runs/*/*"] [--report verify/oracles/REPORT.md]

An oracle is `verify/oracles/<name>.py`. Its contract:

    INPUTS   list of telemetry columns the oracle reads. A column name with the suffix "@prev" is read from the
             previous frame (frame N-1) instead of frame N; frame 0 is then skipped ("no previous frame").
    OUTPUTS  list of output names. Each is a telemetry column unless the module defines `observed(row) -> dict`,
             which derives the live value from the row (e.g. a flag bit).
    LAG      0 = the outputs are compared with frame N (same frame as the inputs); 1 = with frame N+1.
    step(inputs: dict) -> dict        the spec equation; returns the predicted OUTPUTS.
    skip(inputs: dict, row: dict) -> str | None   (optional) a reason to leave the frame out (airborne, engine off ...);
             the runner counts frames per reason and reports them.
    configure(manifest: dict)        (optional) read the run's manifest (profile, env_switches, env) before stepping;
             the runner adds manifest["_run_dir"] so an oracle can read the run's events.csv (hit frames).
    REQUIRED_COLUMNS (optional) telemetry columns read outside INPUTS (in configure / summary). A run whose CSV lacks
             any INPUTS / OUTPUTS / REQUIRED_COLUMNS column (an older i76tel.h version) is graded INCONCLUSIVE with
             the missing names, never FAIL.
    reset()                          (optional) clear per-run state (an accumulator) before stepping.
    fit(rows: list[dict]) -> dict    (optional) fit the constants the telemetry does not expose and set them on the
             module; the result is reported as a FINDING, never as a PASS (KIND = "finding").
    summary(rows: list[dict]) -> dict (optional) per-run figures worth recording beside the match (e.g. the range of a
             predicted value that is only observable through a threshold); printed and put in the report, no grading.
    KIND     "pass" (PASS at >= 98% of considered frames within tolerance, else FAIL) or "finding" (the module needed
             a fitted constant; the harness reports the fit and the match rate but never says PASS).
    CONSTANTS  dict name -> "value (spec citation)"; every constant step() uses must be listed here and must be one
             the spec names. A constant the spec does not name is a spec gap: put it in GAPS, not in CONSTANTS.
    GAPS     list of strings: what the spec does not say and what the module assumed instead.
    CAVEAT   one paragraph on what a PASS here does and does not prove.
    CLAIMS   list of (name_or_field, "what the match supports") pairs for the report's claims table.
    VARIANTS (optional) list of (label, {module_attr: value}) alternative readings; --all runs each and reports its
             match rate beside the default's, so a reading the spec leaves open is settled by the data, not by us.

Tolerance per output comes from tolerances.json: {"<output>": {"abs": a, "rel": r}}; a frame's output is within
tolerance when |got - expected| <= a + r x |expected| (+1e-9 for float noise). Outputs missing from the file use
{"abs": 0, "rel": 0} (exact). A frame matches when every output is within tolerance.

The telemetry CSV is one row per rendered frame, written by tools/telemetry/i76tel.py (fields: i76tel.h). Frames
with player_present == 0 are skipped for every oracle. Nothing here runs the game or writes outside verify\oracles\
(and the optional --json path).
"""
import argparse
import csv
import glob
import importlib.util
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ORACLES = os.path.join(HERE, "oracles")
DEFAULT_TOL = os.path.join(HERE, "tolerances.json")
DEFAULT_REPORT = os.path.join(ORACLES, "REPORT.md")
# section 2.4's first oracles are engine / brake / step oracles (the drive scenario) plus the damage oracles (take-damage);
# several globs separated by ';' are allowed; --runs "verify/runs/*/*" for everything
DEFAULT_RUNS = os.path.join(HERE, "runs", "drive", "*") + ";" + os.path.join(HERE, "runs", "take-damage", "*")
PASS_RATE = 0.98
WORST_N = 5

# the oracles section 2.4 asks for, in report order
FIRST_ORACLES = ["engine_rpm", "engine_gear", "drive_power", "brake_effective", "health_fraction", "damage_smoke", "step_count"]


def _num(s):
    if s is None:
        return None
    t = s.strip()
    if t == "":
        return None
    try:
        if t.lstrip("-").isdigit():
            return int(t)
        return float(t)
    except ValueError:
        return t


def load_rows(run_dir):
    p = os.path.join(run_dir, "telemetry.csv")
    with open(p, newline="") as fh:
        rd = csv.DictReader(fh)
        rows = []
        for r in rd:
            rows.append({k: _num(v) for k, v in r.items()})
    return rows


def load_manifest(run_dir):
    p = os.path.join(run_dir, "manifest.json")
    if os.path.exists(p):
        with open(p) as fh:
            return json.load(fh)
    return {}


def load_oracle(name):
    p = os.path.join(ORACLES, name + ".py")
    if not os.path.exists(p):
        sys.exit("no such oracle: %s" % p)
    spec = importlib.util.spec_from_file_location("oracle_" + name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ("INPUTS", "OUTPUTS", "LAG", "step"):
        if not hasattr(mod, attr):
            sys.exit("oracle %s lacks %s" % (name, attr))
    return mod


def load_tolerances(path):
    if path and os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return {}


def within(got, exp, tol):
    if isinstance(exp, bool) or isinstance(got, bool):
        return float(bool(got) != bool(exp)), bool(got) == bool(exp)
    if got is None or exp is None:
        return math.inf, False
    err = abs(float(got) - float(exp))
    a = float(tol.get("abs", 0.0))
    r = float(tol.get("rel", 0.0))
    return err, err <= a + r * abs(float(exp)) + 1e-9


def observed_of(mod, row):
    if hasattr(mod, "observed"):
        return mod.observed(row)
    return {o: row.get(o) for o in mod.OUTPUTS}


def run_oracle(mod, name, run_dir, tolerances, variant=None):
    rows = load_rows(run_dir)
    manifest = load_manifest(run_dir)
    manifest["_run_dir"] = run_dir
    # an older telemetry layout (i76tel.h v1 has no engine_power / mass / health_pct) cannot feed this oracle: say so
    cols = set(rows[0].keys()) if rows else set()
    need = [f[:-5] if f.endswith("@prev") else f for f in mod.INPUTS] + list(getattr(mod, "REQUIRED_COLUMNS", []))
    if not hasattr(mod, "observed"):
        need += list(mod.OUTPUTS)
    missing = sorted(set(f for f in need if f not in cols))
    if missing:
        reason = "columns missing (telemetry v%s): %s" % (rows[0].get("version") if rows else "?", ", ".join(missing))
        return {
            "oracle": name, "run": run_dir, "variant": variant or {}, "frames": len(rows), "considered": 0,
            "skipped": {reason: len(rows)}, "matched": 0, "rate": 0.0, "max_abs_err": {o: 0.0 for o in mod.OUTPUTS},
            "positives": {}, "worst": [], "verdict": "INCONCLUSIVE", "kind": getattr(mod, "KIND", "pass"), "fitted": None,
            "summary": None, "lag": int(mod.LAG), "profile": manifest.get("profile"), "env_switches": manifest.get("env_switches", {}),
            "tolerances": {o: tolerances.get(o, {}) for o in mod.OUTPUTS},
        }
    if hasattr(mod, "configure"):
        mod.configure(manifest)
    if variant:                                   # after configure: a variant overrides what the manifest set (health_fraction FIX_X100)
        for k, v in variant.items():
            setattr(mod, k, v)
    if hasattr(mod, "reset"):
        mod.reset()
    fitted = mod.fit(rows) if hasattr(mod, "fit") else None
    summary = mod.summary(rows) if hasattr(mod, "summary") else None
    lag = int(mod.LAG)
    tol = {o: tolerances.get(o, {}) for o in mod.OUTPUTS}
    considered = matched = 0
    skipped = {}
    max_err = {o: 0.0 for o in mod.OUTPUTS}
    worst = []        # (score, frame_idx, inputs, expected, got, errs)
    positives = {o: [0, 0] for o in mod.OUTPUTS}   # [expected true, predicted true] for boolean outputs
    n = len(rows)
    for i in range(n):
        j = i + lag
        if j >= n:
            break
        row_in, row_out = rows[i], rows[j]
        if not row_in.get("player_present") or not row_out.get("player_present"):
            skipped["player absent"] = skipped.get("player absent", 0) + 1
            continue
        inputs = {}
        bad = None
        for f in mod.INPUTS:
            if f.endswith("@prev"):
                if i == 0:
                    bad = "no previous frame"
                    break
                inputs[f] = rows[i - 1][f[:-5]]
            else:
                inputs[f] = row_in[f]
        if bad:
            skipped[bad] = skipped.get(bad, 0) + 1
            continue
        if hasattr(mod, "skip"):
            reason = mod.skip(inputs, row_in)
            if reason:
                skipped[reason] = skipped.get(reason, 0) + 1
                continue
        got = mod.step(inputs)
        exp = observed_of(mod, row_out)
        considered += 1
        ok_all = True
        score = 0.0
        errs = {}
        for o in mod.OUTPUTS:
            err, ok = within(got.get(o), exp.get(o), tol[o])
            errs[o] = err
            if isinstance(exp.get(o), bool):
                positives[o][0] += int(bool(exp.get(o)))
                positives[o][1] += int(bool(got.get(o)))
            if err > max_err[o]:
                max_err[o] = err
            denom = float(tol[o].get("abs", 0.0)) + float(tol[o].get("rel", 0.0)) * abs(float(exp.get(o) or 0.0))
            score = max(score, err / denom if denom > 0 else err)
            ok_all = ok_all and ok
        if ok_all:
            matched += 1
        else:
            worst.append((score, i, dict(inputs), exp, got, errs, row_out.get("frame"), row_out.get("sim_time"), row_out.get("flags")))
    worst.sort(key=lambda w: -w[0])
    rate = matched / considered if considered else 0.0
    kind = getattr(mod, "KIND", "pass")
    if considered == 0:
        verdict = "INCONCLUSIVE"
    elif kind == "finding":
        verdict = "FINDING"
    else:
        verdict = "PASS" if rate >= PASS_RATE else "FAIL"
        # a boolean observable that was never true (neither observed nor predicted) cannot discriminate the spec from
        # "it never happens": label it so the gate does not read it as a full pass
        bools = getattr(mod, "BOOL_OUTPUTS", ())
        if verdict == "PASS" and bools and all(positives[o] == [0, 0] for o in bools):
            verdict = "PASS (one-sided)"
    return {
        "oracle": name, "run": run_dir, "variant": variant or {}, "frames": n, "considered": considered,
        "skipped": skipped, "matched": matched, "rate": rate, "max_abs_err": max_err,
        "positives": {o: {"expected_true": p[0], "predicted_true": p[1]} for o, p in positives.items() if p != [0, 0] or _is_bool_output(mod, o)},
        "worst": [{"idx": w[1], "frame": w[6], "sim_time": w[7], "flags": w[8], "inputs": w[2], "expected": w[3], "got": w[4], "err": w[5]} for w in worst[:WORST_N]],
        "verdict": verdict, "kind": kind, "fitted": fitted, "summary": summary, "lag": lag,
        "profile": manifest.get("profile"), "env_switches": manifest.get("env_switches", {}),
        "tolerances": tol,
    }


def _is_bool_output(mod, o):
    return o in getattr(mod, "BOOL_OUTPUTS", ())


def fmt_val(v):
    if isinstance(v, bool):
        return "T" if v else "F"
    if isinstance(v, float):
        return "%.6g" % v
    if isinstance(v, int) and v > 0xffff:
        return "0x%x" % v
    return str(v)


def print_result(res):
    print("oracle %s on %s (profile %s, lag %d)" % (res["oracle"], res["run"], res["profile"], res["lag"]))
    if res["variant"]:
        print("  variant: %s" % res["variant"])
    print("  frames %d, considered %d, matched %d, match rate %.4f -> %s" % (res["frames"], res["considered"], res["matched"], res["rate"], res["verdict"]))
    if res["skipped"]:
        print("  skipped: " + ", ".join("%s %d" % (k, v) for k, v in sorted(res["skipped"].items(), key=lambda kv: -kv[1])))
    for o, e in res["max_abs_err"].items():
        print("  max_abs_err %s = %s (tolerance %s)" % (o, fmt_val(e), res["tolerances"][o] or "exact"))
    for o, p in res["positives"].items():
        print("  %s: expected true on %d frames, predicted true on %d" % (o, p["expected_true"], p["predicted_true"]))
    if res["fitted"]:
        print("  fitted: %s" % json.dumps(res["fitted"]))
    if res.get("summary"):
        print("  summary: %s" % json.dumps(res["summary"]))
    if res["worst"]:
        print("  worst %d frames:" % len(res["worst"]))
        for w in res["worst"]:
            print("    frame %s t=%s flags=%s inputs=%s expected=%s got=%s" % (
                w["frame"], fmt_val(w["sim_time"]), fmt_val(w["flags"]),
                "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["inputs"].items()) + "}",
                "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["expected"].items()) + "}",
                "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["got"].items()) + "}"))


def list_runs(pattern):
    """Run directories under the glob that hold a telemetry.csv with at least one frame AND a manifest.json
    (run_scenario.py writes the manifest last, so a directory without one is still being recorded by the sandbox and
    its CSV grows under the reader). The empty / in-progress ones are returned separately so the report lists them
    instead of grading a partial file."""
    out, skipped = [], []
    dirs = []
    for pat in pattern.split(";"):
        if pat.strip():
            dirs += glob.glob(pat.strip())
    for d in sorted(set(dirs)):
        p = os.path.join(d, "telemetry.csv")
        if not (os.path.isdir(d) and os.path.exists(p)):
            continue
        if not os.path.exists(os.path.join(d, "manifest.json")):
            skipped.append((d, "no manifest.json yet: run in progress"))
            continue
        with open(p, newline="") as fh:
            n = sum(1 for _ in fh) - 1
        if n > 0:
            out.append(d)
        else:
            skipped.append((d, "telemetry.csv has no frames"))
    return out, skipped


def run_label(run_dir):
    parts = os.path.normpath(run_dir).split(os.sep)
    return "/".join(parts[-2:])


def write_report(results, empty_runs, oracle_mods, runs, path):
    L = []
    L.append("# Oracle report (verify/oracle_run.py --all)")
    L.append("")
    L.append("Generated %s. Runs: %s. PASS = >= %d%% of considered frames within tolerance (verify/tolerances.json). "
             "KIND `finding` oracles fit a constant the telemetry does not carry and are never graded PASS." % (
                 time.strftime("%Y-%m-%d %H:%M"), ", ".join("%s (%s)" % (run_label(r), load_manifest(r).get("profile")) for r in runs), int(PASS_RATE * 100)))
    if empty_runs:
        L.append("")
        L.append("Run directories matched but not graded: %s." % "; ".join("%s (%s)" % (run_label(d), why) for d, why in empty_runs))
    L.append("")
    L.append("Nothing here ran the game: every number comes from the recorded `telemetry.csv` of each run (one row per "
             "rendered frame, fields per `tools/telemetry/i76tel.h`) and its `manifest.json`.")
    L.append("")
    L.append("## Pass/fail table")
    L.append("")
    L.append("| oracle | run (profile) | lag | frames | considered | skipped | matched | rate | max_abs_err | verdict |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for res in results:
        if res["variant"]:
            continue
        sk = sum(res["skipped"].values())
        mae = ", ".join("%s %s" % (o, fmt_val(e)) for o, e in res["max_abs_err"].items())
        L.append("| %s | %s (%s) | %d | %d | %d | %d | %d | %.4f | %s | **%s** |" % (
            res["oracle"], run_label(res["run"]), res["profile"], res["lag"], res["frames"], res["considered"], sk,
            res["matched"], res["rate"], mae, res["verdict"]))
    L.append("")
    # per oracle sections
    for name in [n for n in FIRST_ORACLES if n in oracle_mods] + [n for n in oracle_mods if n not in FIRST_ORACLES]:
        mod = oracle_mods[name]
        L.append("## %s" % name)
        L.append("")
        doc = (mod.__doc__ or "").strip().splitlines()
        if doc:
            L.append(doc[0].strip())
            L.append("")
        L.append("- INPUTS: `%s`; OUTPUTS: `%s`; LAG %d; KIND %s" % (", ".join(mod.INPUTS), ", ".join(mod.OUTPUTS), mod.LAG, getattr(mod, "KIND", "pass")))
        consts = getattr(mod, "CONSTANTS", {})
        if consts:
            L.append("- Spec constants used: " + "; ".join("`%s` = %s" % (k, v) for k, v in consts.items()))
        mine = [r for r in results if r["oracle"] == name and not r["variant"]]
        for res in mine:
            sk = ", ".join("%s %d" % (k, v) for k, v in sorted(res["skipped"].items(), key=lambda kv: -kv[1])) or "none"
            L.append("- %s: considered %d of %d frames (skipped: %s); matched %d (%.4f); %s." % (
                run_label(res["run"]), res["considered"], res["frames"], sk, res["matched"], res["rate"], res["verdict"]))
            for o, p in res["positives"].items():
                L.append("  - `%s` observed true on %d frames, predicted true on %d" % (o, p["expected_true"], p["predicted_true"]))
            if res["fitted"]:
                L.append("  - fitted: " + ", ".join("%s = %s" % (k, fmt_val(v) if isinstance(v, (int, float)) else v) for k, v in res["fitted"].items()))
            if res.get("summary"):
                L.append("  - summary: " + ", ".join("%s = %s" % (k, fmt_val(v) if isinstance(v, (int, float)) else v) for k, v in res["summary"].items()))
            if res["worst"] and res["verdict"] != "PASS":
                L.append("  - worst frames (frame, sim_time, flags, inputs -> expected / got):")
                for w in res["worst"]:
                    L.append("    - %s t=%s flags=%s %s -> expected %s / got %s" % (
                        w["frame"], fmt_val(w["sim_time"]), fmt_val(w["flags"]),
                        "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["inputs"].items()) + "}",
                        "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["expected"].items()) + "}",
                        "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["got"].items()) + "}"))
            elif res["worst"]:
                w = res["worst"][0]
                L.append("  - worst frame: %s t=%s flags=%s %s -> expected %s / got %s" % (
                    w["frame"], fmt_val(w["sim_time"]), fmt_val(w["flags"]),
                    "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["inputs"].items()) + "}",
                    "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["expected"].items()) + "}",
                    "{" + ", ".join("%s=%s" % (k, fmt_val(v)) for k, v in w["got"].items()) + "}"))
        vres = [r for r in results if r["oracle"] == name and r["variant"]]
        if vres:
            L.append("- Variant readings (match rate per run, default first):")
            labels = [lbl for lbl, _ in getattr(mod, "VARIANTS", [])]
            for run in runs:
                base = [r for r in mine if r["run"] == run]
                vs = [r for r in vres if r["run"] == run]
                if not base:
                    continue
                parts = ["default %.4f" % base[0]["rate"]]
                for lbl, r in zip(labels, vs):
                    parts.append("%s %.4f" % (lbl, r["rate"]))
                L.append("  - %s: %s" % (run_label(run), "; ".join(parts)))
        cav = getattr(mod, "CAVEAT", "")
        if cav:
            L.append("- What this does and does not prove: " + " ".join(cav.split()))
        L.append("")
    # spec gaps
    L.append("## Spec gaps")
    L.append("")
    L.append("Constants or branches the oracles needed that the cited spec does not name, and branches the recorded runs never exercise.")
    L.append("")
    any_gap = False
    for name, mod in oracle_mods.items():
        for g in getattr(mod, "GAPS", []):
            L.append("- **%s**: %s" % (name, " ".join(g.split())))
            any_gap = True
    if not any_gap:
        L.append("- none")
    L.append("")
    # claims
    L.append("## Claims these oracles now support")
    L.append("")
    L.append("Names and fields whose equation claim the matching oracle exercises on these runs. A `finding` oracle supports the "
             "*shape* of the equation only; the fitted constant is reported, not proved from the spec.")
    L.append("")
    L.append("| oracle | verdicts | name / field | what the match supports |")
    L.append("|---|---|---|---|")
    for name, mod in oracle_mods.items():
        vs = sorted(set(r["verdict"] for r in results if r["oracle"] == name and not r["variant"]))
        for claim, what in getattr(mod, "CLAIMS", []):
            L.append("| %s | %s | %s | %s |" % (name, ", ".join(vs), claim, what))
    L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("oracle", nargs="?", help="oracle module name under verify/oracles/")
    ap.add_argument("run", nargs="?", help="run directory holding telemetry.csv and manifest.json")
    ap.add_argument("--tolerances", default=DEFAULT_TOL)
    ap.add_argument("--json", help="write the result dict here")
    ap.add_argument("--all", action="store_true", help="every oracle on every run; writes the report")
    ap.add_argument("--runs", default=DEFAULT_RUNS, help="glob(s) of run directories for --all, ';'-separated (default: drive/* and take-damage/*)")
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--variant", action="append", default=[], help="attr=value to set on the module (python literal)")
    args = ap.parse_args()
    tolerances = load_tolerances(args.tolerances)

    if args.all:
        runs, empty = list_runs(args.runs)
        if not runs:
            sys.exit("no runs with frames match %s" % args.runs)
        for d, why in empty:
            print("skipping %s: %s" % (d, why))
        names = [n for n in FIRST_ORACLES if os.path.exists(os.path.join(ORACLES, n + ".py"))]
        names += sorted(os.path.splitext(f)[0] for f in os.listdir(ORACLES)
                        if f.endswith(".py") and not f.startswith("_") and os.path.splitext(f)[0] not in names)
        mods = {n: load_oracle(n) for n in names}
        results = []
        for n in names:
            for r in runs:
                mod = load_oracle(n)                       # fresh module per run: no state leaks between runs
                res = run_oracle(mod, n, r, tolerances)
                results.append(res)
                print_result(res)
                for lbl, var in getattr(mod, "VARIANTS", []):
                    vmod = load_oracle(n)
                    vres = run_oracle(vmod, n, r, tolerances, variant=var)
                    results.append(vres)
                    print("  variant %-28s match rate %.4f (%d/%d)" % (lbl, vres["rate"], vres["matched"], vres["considered"]))
        p = write_report(results, empty, mods, runs, args.report)
        print("report: %s" % p)
        if args.json:
            with open(args.json, "w") as fh:
                json.dump(results, fh, indent=1, default=str)
        return

    if not args.oracle or not args.run:
        ap.error("oracle and run are required unless --all")
    variant = {}
    for v in args.variant:
        k, _, val = v.partition("=")
        import ast
        variant[k.strip()] = ast.literal_eval(val.strip())
    mod = load_oracle(args.oracle)
    res = run_oracle(mod, args.oracle, args.run, tolerances, variant=variant or None)
    print_result(res)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(res, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
