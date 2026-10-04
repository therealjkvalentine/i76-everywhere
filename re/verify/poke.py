r"""poke.py - the poke runner (VERIFICATION-PROGRAM.md section 2.5; expectation mini-language section 4.4).

    python verify\poke.py [--expectations verify\expectations.json] [--only id,id ...] [--route melee|t01]
                          [--report verify\poke-report.md] [--profile stock20]

One sandbox session: boot, then for every expectation in expectations.json
    observe (A1), observe (A2)  - the A/A control: the same probe twice with nothing changed,
    set the tunable (tools/trainer/i76tune.py Tuner.apply: range check, write, read back, derived twins),
    observe (B),
    reset (pristine bytes from ghidra/i76_ref.exe for exe-scope entries; the saved live value for per-car entries),
    observe (A3),
and grade each `expect` entry PASS / FAIL / INCONCLUSIVE with the numbers (section 4.4 relations: formula, increase,
decrease, unchanged, event_count, flag_set, flag_clear; `inconclusive` = no telemetry field can see it, `needs` says which).

Probes (expectations.json "probe"): {"kind":"idle","s":N} brake to a stop, settle 1 s, observe N s standing;
{"kind":"accelerate","s":N} brake to a stop, turn to the session's heading (alternating 180 deg between probes so the
car shuttles over the same ground), stop, observe N s of full throttle (W); {"kind":"brake","s":N,"brake_s":M} as
accelerate for N s, then observe the S hold until the car stops (max M s); {"kind":"none"} no probe (inconclusive entries).
An observation is the telemetry frames (tellib keep=True) between the probe's start and end marks.

Route: `melee` (default) = Instant Melee on i76_pristine_fix.exe with 0 AI drivers (run_scenario --nomission --exe
i76_pristine_fix.exe --ai 0): no scripted mission end, which the ~10 minutes of probing need; t01 on i76.exe ends about
45-60 s after the hand-over (verify/README.md), so `--route t01` only fits one or two expectations and is there for a
spot check. Both are the sandbox copy (C:\Users\james\i76-uncap-lab\game); the exe-scope addresses are the same image
layout (tunables.json, md5 9a232dcc addresses; the pristine_fix build is that image plus i76fix's clusters, and every
write prints the old value, which is checked against the catalogue default before anything is graded).

Everything else is run_scenario.py's: lock, proxy install / restore, launch, melee navigation, focus, state-checked
keys, clean quit. Output: verify\runs\poke\<timestamp>\{telemetry.csv, events.csv, actions.csv, manifest.json, poke.json}
and the report (--report, default verify\poke-report.md).
"""
import argparse
import json
import math
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import EXE, LOCK, VERIFY, Functions, ensure_dirs, key_up, log, trainer_path  # noqa: E402
import run_scenario  # noqa: E402

trainer_path()
import i76tune  # noqa: E402

DEFAULT_EXPECTATIONS = os.path.join(VERIFY, "expectations.json")
DEFAULT_REPORT = os.path.join(VERIFY, "poke-report.md")
PASS_RATE = 0.98
RATIOS_IDS = {0: "gear_ratio_reverse", 2: "gear_ratio_1st", 3: "gear_ratio_2nd", 4: "gear_ratio_3rd"}
DECEL_CRASH_MS2 = 25.0        # a frame pair decelerating harder than this is a hit, not the brakes (2300/1951 x 8 = 9.4 stock)
STUCK_SPEED = 5.0             # an accelerate / brake probe whose top speed stays under this was blocked by scenery: redo it once
HOME_RADIUS = 15.0


# ---------------------------------------------------------------- evaluation of the mini-language

def row_namespace(row, x, cat):
    ns = dict(row)
    fl = int(row.get("flags", 0) or 0)
    ns.update({"skid": bool(fl & 0x2), "airborne": bool(fl & 0x4), "engine_on": bool(fl & 0x1), "flags": fl,
               "kmh": float(row.get("speed", 0.0)) * 3.6, "x": x,
               "floor": math.floor, "min": min, "max": max, "abs": abs, "sqrt": math.sqrt})
    g = int(row.get("gear", 1) or 1)
    rid = RATIOS_IDS.get(g)
    ns["gear_ratio"] = cat["_ids"][rid]["default"] if rid else 0.0
    # health helpers (damage.md): min side ratio over armour / chassis, and the core-component intact test
    r = 1.0
    for i in range(4):
        am, cm = float(row.get("armour_max_%d" % i, 0) or 0), float(row.get("chassis_max_%d" % i, 0) or 0)
        if am:
            r = min(r, float(row["armour_%d" % i]) / am)
        if cm:
            r = min(r, float(row["chassis_%d" % i]) / cm)
    ns["side_ratio"] = min(1.0, max(0.0, r))
    cores = []
    for a, b in (("engine_hp", "engine_hp_max"), ("susp_hp", "susp_hp_max"), ("brake_hp", "brake_hp_max")):
        mx = float(row.get(b, 0) or 0)
        cores.append(float(row.get(a, 0)) / mx if mx else 0.0)
    ns["cores_intact"] = all(c >= 0.9999 for c in cores)
    return ns


def _eval(expr, ns):
    return eval(expr, {"__builtins__": {}}, ns)


def frames_where(obs, when, x, cat):
    out = []
    for row in obs:
        if not row.get("player_present"):
            continue
        ns = row_namespace(row, x, cat)
        try:
            ok = bool(_eval(when, ns)) if when else True
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            out.append((row, ns))
    return out


def metric_of(exp, obs, x, cat):
    """A single number per observation for the increase / decrease / unchanged relations (None when undefined)."""
    m = exp.get("metric", "mean")
    when = exp.get("when")
    if m == "shift_speed_kmh":
        prev = None
        for row in obs:
            if not row.get("player_present"):
                continue
            g = int(row["gear"])
            if prev is not None and prev == int(exp["from"]) and g == int(exp["to"]):
                return float(row["speed"]) * 3.6
            prev = g
        return None
    sel = frames_where(obs, when, x, cat)
    if m == "decel":
        # median of -(dv/dt) over pairs of CONSECUTIVE frames (frame counter +1) that both satisfy `when`, sim_time as
        # the clock; pairs with |a| > DECEL_CRASH_MS2 are a collision or the rest snap, not the brakes (the first poke
        # session's mean read 46 m/s^2 from one arena hit), and are dropped
        ds = []
        rows = [r for r, _ in sel]
        for a, b in zip(rows[:-1], rows[1:]):
            dt = float(b["sim_time"]) - float(a["sim_time"])
            if int(b["frame"]) - int(a["frame"]) == 1 and 0 < dt < 0.5:
                acc = -(float(b["speed"]) - float(a["speed"])) / dt
                if abs(acc) < DECEL_CRASH_MS2:
                    ds.append(acc)
        return statistics.median(ds) if len(ds) >= 5 else None
    if m == "accel_y":
        # median of dvy/dt (telemetry velocity_1, the world-up component of ent+0xbc) over pairs of consecutive frames that
        # both satisfy `when`: the airborne path (phys_Integrate, physics.md) does not write the accel field ent+0xd4, which
        # reads 0 on every airborne frame of the jump runs (runs\jump61002-1359*), while dvy/dt reads -9.8 (median)
        ds = []
        rows = [r for r, _ in sel]
        for a, b in zip(rows[:-1], rows[1:]):
            dt = float(b["sim_time"]) - float(a["sim_time"])
            if int(b["frame"]) - int(a["frame"]) == 1 and 0 < dt < 0.5:
                ds.append((float(b["velocity_1"]) - float(a["velocity_1"])) / dt)
        return statistics.median(ds) if len(ds) >= 5 else None
    field = exp["field"]
    vals = [float(r[field]) for r, _ in sel]
    if not vals:
        return None
    return {"mean": statistics.mean, "max": max, "min": min, "count": len}[m](vals)


def grade_formula(exp, obs, x, cat):
    """Per-frame formula check -> dict(rate, considered, matched, max_err, ok, ...)."""
    tol = float(exp.get("tolerance", 0.0))
    minf = int(exp.get("min_frames", 10))
    if "metric" in exp:                                     # a metric compared with the formula (shift speed)
        v = metric_of(exp, obs, x, cat)
        if v is None:
            return {"ok": None, "considered": 0, "value": None, "expected": None, "note": "metric undefined"}
        e = float(_eval(exp["formula"], {"x": x, "floor": math.floor, "min": min, "max": max, "abs": abs}))
        return {"ok": abs(v - e) <= tol + 1e-9, "considered": 1, "value": round(v, 3), "expected": round(e, 3), "err": round(abs(v - e), 3)}
    sel = frames_where(obs, exp.get("when"), x, cat)
    if len(sel) < minf:
        return {"ok": None, "considered": len(sel), "note": "fewer than %d frames satisfy `when`" % minf}
    matched, errs = 0, []
    for row, ns in sel:
        try:
            e = float(_eval(exp["formula"], ns))
        except Exception as ex:  # noqa: BLE001
            return {"ok": None, "considered": len(sel), "note": "formula failed: %s" % ex}
        err = abs(float(row[exp["field"]]) - e)
        errs.append(err)
        if err <= tol + 1e-9:
            matched += 1
    rate = matched / len(sel)
    return {"ok": rate >= PASS_RATE, "considered": len(sel), "matched": matched, "rate": round(rate, 4),
            "max_err": round(max(errs), 4), "median_err": round(statistics.median(errs), 4)}


def grade_expect(exp, obs_a1, obs_a2, obs_b, obs_a3, x_default, x_set, cat, set_ok):
    rel = exp["relation"]
    out = {"relation": rel, "field": exp.get("field"), "metric": exp.get("metric"), "when": exp.get("when"), "formula": exp.get("formula")}
    if rel == "inconclusive":
        out.update({"grade": "INCONCLUSIVE", "why": "not observable: needs " + exp.get("needs", "?")})
        return out
    if not set_ok:
        out.update({"grade": "INCONCLUSIVE", "why": "the set did not read back (or the live value was not the catalogue default)"})
        return out
    if rel == "formula":
        a1, a2 = grade_formula(exp, obs_a1, x_default, cat), grade_formula(exp, obs_a2, x_default, cat)
        b = grade_formula(exp, obs_b, x_set, cat)
        a3 = grade_formula(exp, obs_a3, x_default, cat)
        out.update({"A1": a1, "A2": a2, "B": b, "A3": a3})
        if any(g["ok"] is None for g in (a1, a2, b)):
            out.update({"grade": "INCONCLUSIVE", "why": "; ".join("%s: %s" % (k, g.get("note")) for k, g in (("A1", a1), ("A2", a2), ("B", b)) if g["ok"] is None)})
        elif a1["ok"] != a2["ok"]:
            out.update({"grade": "INCONCLUSIVE", "why": "the A/A control disagrees (A1 %s, A2 %s): the observable is not stable under the probe" % (a1["ok"], a2["ok"])})
        elif not a1["ok"]:
            out.update({"grade": "FAIL", "why": "the unchanged game does not follow the spec formula at the default (A1 rate %s, A2 rate %s): a spec problem, not a poke result" % (a1.get("rate", a1.get("err")), a2.get("rate", a2.get("err")))})
        elif not b["ok"]:
            out.update({"grade": "FAIL", "why": "baseline follows the formula, the changed value does not (B rate %s, max err %s)" % (b.get("rate", b.get("err")), b.get("max_err", b.get("err")))})
        elif a3["ok"] is False:
            out.update({"grade": "FAIL", "why": "the reset did not bring the observable back (A3 rate %s)" % a3.get("rate", a3.get("err"))})
        else:
            out.update({"grade": "PASS", "why": "A/A, changed and restored observations all follow the formula with their own x"})
        return out
    if rel in ("increase", "decrease", "unchanged"):
        ms = [metric_of(exp, o, x_default, cat) for o in (obs_a1, obs_a2)] + [metric_of(exp, obs_b, x_set, cat), metric_of(exp, obs_a3, x_default, cat)]
        out.update({"A1": ms[0], "A2": ms[1], "B": ms[2], "A3": ms[3]})
        if any(m is None for m in ms[:3]):
            out.update({"grade": "INCONCLUSIVE", "why": "metric undefined on an observation (A1 %s, A2 %s, B %s)" % tuple(ms[:3])})
            return out
        abar = (ms[0] + ms[1]) / 2.0
        spread = abs(ms[0] - ms[1])
        noise = max(2.0 * spread, float(exp.get("min_delta", 0.0)))
        delta = ms[2] - abar
        out.update({"A_mean": round(abar, 4), "A_spread": round(spread, 4), "delta": round(delta, 4), "noise_band": round(noise, 4)})
        if rel == "unchanged":
            if abs(delta) <= noise:
                out.update({"grade": "PASS", "why": "B within the control band (|delta| %.3f <= %.3f)" % (abs(delta), noise)})
            else:
                out.update({"grade": "FAIL", "why": "B moved by %.3f, beyond the control band %.3f" % (delta, noise)})
            return out
        want = 1 if rel == "increase" else -1
        if delta * want > noise:
            out.update({"grade": "PASS", "why": "B moved %.3f (%s) beyond the control band %.3f" % (delta, rel, noise)})
        elif delta * want < -noise:
            out.update({"grade": "FAIL", "why": "B moved %.3f, the wrong way (expected %s) beyond the control band %.3f" % (delta, rel, noise)})
        else:
            out.update({"grade": "INCONCLUSIVE", "why": "B moved %.3f, within the control band %.3f (A1 %.3f, A2 %.3f)" % (delta, noise, ms[0], ms[1])})
        if ms[3] is not None and abs(ms[3] - abar) > noise and out["grade"] == "PASS":
            out.update({"grade": "INCONCLUSIVE", "why": out["why"] + "; but A3 after the reset (%.3f) did not return to the control band" % ms[3]})
        return out
    if rel in ("flag_set", "flag_clear"):
        mask = int(exp["mask"], 0) if isinstance(exp.get("mask"), str) else int(exp.get("mask", 0))

        def share(o):
            sel = frames_where(o, exp.get("when"), x_set, cat)
            return (sum(1 for r, _ in sel if int(r["flags"]) & mask) / len(sel)) if sel else None
        ss = [share(o) for o in (obs_a1, obs_a2, obs_b, obs_a3)]
        out.update({"A1": ss[0], "A2": ss[1], "B": ss[2], "A3": ss[3]})
        if any(s is None for s in ss[:3]):
            out.update({"grade": "INCONCLUSIVE", "why": "no frames satisfy `when`"})
            return out
        want_set = rel == "flag_set"
        ok_b = (ss[2] >= 0.5) == want_set
        ok_a = all((s >= 0.5) != want_set for s in ss[:2])
        out.update({"grade": "PASS" if (ok_b and ok_a) else "FAIL", "why": "flag share A1 %.2f A2 %.2f B %.2f" % tuple(ss[:3])})
        return out
    if rel == "event_count":
        out.update({"grade": "INCONCLUSIVE", "why": "event_count needs the per-observation event windows (events are kept but this relation is not used by any expectation yet)"})
        return out
    out.update({"grade": "INCONCLUSIVE", "why": "unknown relation %r" % rel})
    return out


# ---------------------------------------------------------------- the session

class PokeRunner(run_scenario.Runner):
    TEL_KEEP = True

    def mark(self):
        return len(self.tel.kept)

    def frames(self, i0, i1):
        return self.tel.kept[i0:i1]

    home = None               # (x, z) where the session started: even probes drive back here first (bounded drift)

    def probe(self, spec, heading_deg, go_home=False):
        """Run one probe; return (observation frames, info). Moving probes run from `home` (even) or from wherever the
        previous one ended (odd), facing heading_deg, so the car shuttles over the same ground; a probe blocked by
        scenery (top speed < STUCK_SPEED) is reported with info["stuck"] and the caller redoes it once."""
        kind = spec.get("kind", "idle")
        if kind == "none":
            return [], {"kind": kind}
        self.brake_to_stop(8)
        if kind == "idle":
            self.sleep_checked(1.0)
            i0 = self.mark(); self.act("obs-start", "idle %.0fs" % spec.get("s", 3))
            self.sleep_checked(float(spec.get("s", 3)))
            i1 = self.mark(); self.act("obs-end", "idle, %d frames" % (i1 - i0))
            return self.frames(i0, i1), {"kind": kind, "frames": i1 - i0}
        if go_home and self.home:
            self.drive_to({"x": self.home[0], "z": self.home[1], "radius": HOME_RADIUS, "max_s": 20})
            self.brake_to_stop(6)
        self.turn_to({"heading_deg": heading_deg, "max_s": 10, "tol_deg": 12})
        self.brake_to_stop(5)
        self.sleep_checked(0.5)
        if kind == "jump":
            # the jump scenario's launch op (run_scenario.Runner.jump_launch): roll for 2 s so speed > 5, lift 1.5 m and set vy, record s
            # seconds of flight and landing; "stuck" when fewer than 5 airborne frames came out (the write did not take)
            self.hold("W", float(spec.get("roll_s", 2.0)))
            i0 = self.mark(); self.act("obs-start", "jump vy %.0f, %.0fs" % (spec.get("vy", 12.0), spec.get("s", 4)))
            self.jump_launch({"vy": spec.get("vy", 12.0), "dy": spec.get("dy", 1.5)})
            self.sleep_checked(float(spec.get("s", 4)))
            i1 = self.mark()
            fr = self.frames(i0, i1)
            air = sum(1 for r in fr if int(r.get("flags", 0) or 0) & 0x4)
            self.act("obs-end", "jump, %d frames, %d airborne%s" % (i1 - i0, air, " STUCK" if air < 5 else ""))
            return fr, {"kind": kind, "frames": i1 - i0, "airborne_frames": air, "stuck": air < 5}
        i0 = self.mark(); self.act("obs-start", "%s W %.0fs heading %.0f" % (kind, spec.get("s", 8), heading_deg))
        self.hold("W", float(spec.get("s", 8)))
        if kind == "accelerate":
            i1 = self.mark()
            fr = self.frames(i0, i1)
            vmax = max([float(r["speed"]) for r in fr] or [0.0])
            self.act("obs-end", "accelerate, %d frames, top speed %.1f%s" % (i1 - i0, vmax, " STUCK" if vmax < STUCK_SPEED else ""))
            return fr, {"kind": kind, "frames": i1 - i0, "speed_end": self.mem.speed(), "top_speed": vmax, "stuck": vmax < STUCK_SPEED}
        v0 = self.mem.speed() or 0.0
        i0 = self.mark(); self.act("obs-start", "brake from %.1f m/s" % v0)
        self.brake_to_stop(float(spec.get("brake_s", 8)))
        i1 = self.mark(); self.act("obs-end", "brake, %d frames%s" % (i1 - i0, " STUCK" if v0 < STUCK_SPEED else ""))
        return self.frames(i0, i1), {"kind": kind, "frames": i1 - i0, "speed_start": v0, "stuck": v0 < STUCK_SPEED}

    def observe(self, spec, heading_deg, go_home):
        obs, info = self.probe(spec, heading_deg, go_home)
        if info.get("stuck"):
            self.act("probe-retry", "blocked by scenery (top speed under %.0f m/s): once more from home, other way" % STUCK_SPEED)
            obs, info = self.probe(spec, heading_deg + 180.0, True)
            info["retried"] = True
        return obs, info


def tunable_default(e, img):
    return i76tune.default_for(e, img)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--expectations", default=DEFAULT_EXPECTATIONS)
    ap.add_argument("--only", default="", help="comma-separated expectation ids")
    ap.add_argument("--route", default="melee", choices=["melee", "t01"])
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--profile", default="stock20", choices=sorted(run_scenario.PROFILES))
    ap.add_argument("--secs", type=float, default=1800.0, help="session cap from the hand-over (safety)")
    ap.add_argument("--heading", type=float, default=None, help="probe heading in degrees (atan2(fwd.x, fwd.z) frame); default: where the car points after the boot")
    ap.add_argument("--regrade", default=None, help="no game: regrade a recorded poke run directory (its actions.csv obs marks + telemetry.csv + poke.json) with the current expectations and grader; writes --report")
    a = ap.parse_args()
    ensure_dirs()
    spec = json.load(open(a.expectations, encoding="utf-8"))
    exps = spec["expectations"]
    if a.only:
        want = a.only.split(",")
        exps = sorted([e for e in exps if e["id"] in want], key=lambda e: want.index(e["id"]))   # --only order = run order
    cat = i76tune.load_catalogue()
    img = i76tune.open_image(cat)
    if a.regrade:
        return regrade(a.regrade, exps, cat, a.report)
    for e in exps:
        if e["tunable"] not in cat["_ids"]:
            raise SystemExit("expectation %s: unknown tunable %s" % (e["id"], e["tunable"]))
    # run_scenario's argument namespace (what Runner reads)
    ra = argparse.Namespace(id="poke", census=None, secs=a.secs, profile=a.profile, mission="t01.msn", snapshot_ms=1000, cap=32768,
                            hook_batch=50, attach_after_entity=False, attach_at_spawn=False,
                            exe="i76_pristine_fix.exe" if a.route == "melee" else EXE, nomission=(a.route == "melee"), ai=0)
    scenario = {"id": "poke", "description": "poke runner session (%s): %d expectations from %s" % (a.route, len(exps), a.expectations),
                "steps": [], "_file": a.expectations}
    functions = Functions()
    r = PokeRunner(ra, scenario)
    r.man["poke"] = {"route": a.route, "expectations_file": a.expectations, "ids": [e["id"] for e in exps],
                     "image": {"path": img.path, "md5": img.md5} if img else None}
    r.preflight()
    results = []
    code = 0
    tuner = None
    try:
        r.install_proxy()
        r.launch()
        r.wait_for_mission()
        r.check("player_present", r.mem.entity() is not None, "entity %s" % r.man.get("entity"))
        if not (r.mem.flags() or 0) & 1:                   # melee starts with the engine off
            r.run_step({"op": "start_engine", "after": 2.0})
        r.check("engine_on", bool((r.mem.flags() or 0) & 1), "flags 0x%x" % (r.mem.flags() or 0))
        tuner = i76tune.Tuner(r.p.pid, cat)
        h0 = a.heading if a.heading is not None else math.degrees(r.mem.heading() or 0.0)
        r.man["poke"]["heading0_deg"] = h0
        r.brake_to_stop(10)
        p0 = r.mem.pos()
        r.home = (p0[0], p0[2]) if p0 else None
        r.man["poke"]["home"] = r.home
        for k, exp in enumerate(exps):
            e = cat["_ids"][exp["tunable"]]
            hdg = h0 + (180.0 if k % 2 else 0.0)
            res = {"id": exp["id"], "tunable": exp["tunable"], "spec": exp.get("spec"), "note": exp.get("note"), "probe": exp.get("probe"),
                   "scope": e["scope"], "addr": e["addr"], "default": e["default"], "t_scn": round(time.perf_counter() - r.t0, 1)}
            log("=== expectation %d/%d %s (%s)" % (k + 1, len(exps), exp["id"], exp["tunable"]))
            r.act("expectation", "%s %s" % (exp["id"], exp["tunable"]))
            rels = [x["relation"] for x in exp["expect"]]
            if all(rel == "inconclusive" for rel in rels) or exp.get("probe", {}).get("kind") == "none":
                res["expect"] = [grade_expect(x, [], [], [], [], None, None, cat, True) for x in exp["expect"]]
                res["grade"] = "INCONCLUSIVE"
                results.append(res)
                continue
            live_before = tuner.read(e)
            x_default = e["default"] if e["default"] is not None else live_before
            x_set = float(exp["value"]) if "value" in exp else float(live_before) * float(exp["value_mult"])
            res.update({"live_before": live_before, "x_default": x_default, "x_set": x_set})
            default_ok = e["default"] is None or i76tune.close(live_before, e["default"], e["type"])
            if not default_ok:
                r.man["warnings"].append("%s: live value %s is not the catalogue default %s (a build patch?); graded INCONCLUSIVE" % (exp["tunable"], live_before, e["default"]))
            obs = {}
            obs["A1"], res["probe_A1"] = r.observe(exp["probe"], hdg, True)
            obs["A2"], res["probe_A2"] = r.observe(exp["probe"], hdg + 180.0, False)
            # set
            set_ok = default_ok and tuner.apply(e, x_set, force=False)
            res["set_read_back"] = tuner.read(e)
            res["set_ok"] = bool(set_ok)
            r.act("set", "%s -> %s (read back %s) %s" % (exp["tunable"], x_set, res["set_read_back"], "ok" if set_ok else "FAILED"))
            obs["B"], res["probe_B"] = r.observe(exp["probe"], hdg, True)
            # reset
            if e["scope"] == "exe":
                d = tunable_default(e, img)
                reset_ok = tuner.apply(e, d, force=True, img=img)
            else:
                reset_ok = tuner.apply(e, live_before, force=True)
            res["reset_read_back"] = tuner.read(e)
            res["reset_ok"] = bool(reset_ok) and i76tune.close(res["reset_read_back"], live_before, e["type"])
            r.act("reset", "%s -> %s (read back %s) %s" % (exp["tunable"], live_before, res["reset_read_back"], "ok" if res["reset_ok"] else "FAILED"))
            if not res["reset_ok"]:
                r.fail("reset of %s did not read back: %s" % (exp["tunable"], res["reset_read_back"]))
            obs["A3"], res["probe_A3"] = r.observe(exp["probe"], hdg + 180.0, False)
            res["expect"] = [grade_expect(x, obs["A1"], obs["A2"], obs["B"], obs["A3"], x_default, x_set, cat, set_ok) for x in exp["expect"]]
            grades = [x["grade"] for x in res["expect"]]
            res["grade"] = "FAIL" if "FAIL" in grades else ("INCONCLUSIVE" if "INCONCLUSIVE" in grades else "PASS")
            res["t_end_scn"] = round(time.perf_counter() - r.t0, 1)
            log("  -> %s: %s" % (res["grade"], "; ".join("%s (%s)" % (x["grade"], x["why"]) for x in res["expect"])))
            results.append(res)
            json.dump(results, open(os.path.join(r.out, "poke.json"), "w", encoding="utf-8"), indent=1, default=str)
        r.man["end_frame"] = r.mem.frame()
        r.man["end_state"] = r.mem.state()
        r.man["end_wall_ms"] = int(time.time() * 1000)
        r.act("scenario-end", "%d expectations" % len(results))
    except Exception as e:  # noqa: BLE001
        r.fail("%s: %s" % (type(e).__name__, e))
        code = 1
        if r.mem and r.t0 and "end_frame" not in r.man:
            r.man["end_frame"] = r.mem.frame()
    finally:
        try:
            if tuner is not None and r.p is not None and r.p.poll() is None:
                # leave no exe-scope entry changed if an exception interrupted a set
                changed = [e for e in cat["entries"] if e["scope"] == "exe" and e["default"] is not None
                           and tuner.read(e) is not None and not i76tune.close(tuner.read(e), e["default"], e["type"])]
                for e in changed:
                    tuner.apply(e, tunable_default(e, img), force=True, img=img)
                r.man["poke"]["exe_entries_reset_at_end"] = [e["id"] for e in changed]
        except Exception:  # noqa: BLE001
            pass
        try:
            for k in list(r.held):
                key_up(k)
            r.quit_game()
        finally:
            time.sleep(1.0)
            r.restore_proxy()
            if os.path.exists(LOCK):
                os.remove(LOCK)
            r.collect_logs()
            r.actions.close()
            r.man["poke"]["results"] = results
            r.write_manifest()
            json.dump(results, open(os.path.join(r.out, "poke.json"), "w", encoding="utf-8"), indent=1, default=str)
            write_report(results, r.man, a.report, exps)
    print("poke: %s  %d expectations  errors %s  report %s" % (r.out, len(results), r.man["errors"], a.report))
    return code


# ---------------------------------------------------------------- regrade a recorded run

def regrade(run_dir, exps, cat, report_path):
    """Rebuild each expectation's A1 / A2 / B / A3 observations from the recorded run (actions.csv obs-start / obs-end
    frames -> telemetry.csv rows) and grade them with the current expectations.json. The set / reset facts come from the
    run's poke.json. Nothing runs; the report says it was regraded."""
    import csv
    rows = []
    with open(os.path.join(run_dir, "telemetry.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append({k: _num(v) for k, v in r.items()})
    byf = {}
    for r in rows:
        byf.setdefault(int(r["frame"]), r)
    marks = {}
    cur_exp, start = None, None
    with open(os.path.join(run_dir, "actions.csv"), newline="") as fh:
        for a in csv.DictReader(fh):
            if a["action"] == "expectation":
                cur_exp = a["detail"].split(" ")[0]
            elif a["action"] == "obs-start":
                start = int(a["frame"])
            elif a["action"] == "obs-end" and start is not None and cur_exp:
                marks.setdefault(cur_exp, []).append((start, int(a["frame"])))
                start = None
            elif a["action"] == "probe-retry" and cur_exp and marks.get(cur_exp):
                marks[cur_exp].pop()                    # the stuck probe's window is replaced by the retry's
    old = {r["id"]: r for r in json.load(open(os.path.join(run_dir, "poke.json"), encoding="utf-8"))}
    man = json.load(open(os.path.join(run_dir, "manifest.json"), encoding="utf-8"))
    results = []
    for exp in exps:
        o = old.get(exp["id"])
        if o is None:
            continue
        res = {k: o.get(k) for k in ("id", "tunable", "spec", "probe", "scope", "addr", "default", "t_scn", "t_end_scn", "live_before",
                                     "x_default", "x_set", "set_read_back", "set_ok", "reset_read_back", "reset_ok",
                                     "probe_A1", "probe_A2", "probe_B", "probe_A3")}
        res["note"] = exp.get("note")
        res["regraded_from"] = run_dir
        if all(x["relation"] == "inconclusive" for x in exp["expect"]) or exp.get("probe", {}).get("kind") == "none":
            res["expect"] = [grade_expect(x, [], [], [], [], None, None, cat, True) for x in exp["expect"]]
            res["grade"] = "INCONCLUSIVE"
            results.append(res)
            continue
        wins = marks.get(exp["id"], [])
        # one window per probe: idle / accelerate mark obs-start .. obs-end; a brake probe marks obs-start (W), then a second
        # obs-start (S) which supersedes it, then obs-end, so its window is the S hold alone
        if len(wins) < 4:
            res["expect"] = [dict(relation=x["relation"], grade="INCONCLUSIVE", why="only %d observation windows recorded" % len(wins)) for x in exp["expect"]]
            res["grade"] = "INCONCLUSIVE"
            results.append(res)
            continue
        obs = [[byf[f] for f in range(w0, w1 + 1) if f in byf] for w0, w1 in wins[-4:]]
        res["expect"] = [grade_expect(x, obs[0], obs[1], obs[2], obs[3], res["x_default"], res["x_set"], cat, bool(res["set_ok"])) for x in exp["expect"]]
        grades = [x["grade"] for x in res["expect"]]
        res["grade"] = "FAIL" if "FAIL" in grades else ("INCONCLUSIVE" if "INCONCLUSIVE" in grades else "PASS")
        results.append(res)
        print("%-32s %s: %s" % (exp["id"], res["grade"], "; ".join("%s (%s)" % (x["grade"], x["why"]) for x in res["expect"])))
    man["regraded"] = time.strftime("%Y-%m-%d %H:%M")
    write_report(results, man, report_path, exps)
    json.dump(results, open(os.path.join(run_dir, "poke.regraded.json"), "w", encoding="utf-8"), indent=1, default=str)
    print("regraded %d expectations from %s -> %s" % (len(results), run_dir, report_path))
    return 0


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


# ---------------------------------------------------------------- report

def fmt(v):
    if isinstance(v, float):
        return "%.4g" % v
    return str(v)


def write_report(results, man, path, exps):
    L = []
    L.append("# Poke report (verify/poke.py, VERIFICATION-PROGRAM.md 2.5 / 4.4)")
    L.append("")
    if man.get("regraded"):
        L.append("**Regraded %s** from the recorded run (its observation windows, telemetry and set / reset read-backs) with the "
                 "current expectations.json and grader; the game was not run again for this table." % man["regraded"])
        L.append("")
    tel = man.get("telemetry") or {}
    L.append("Generated %s. Run: `%s` (route %s, exe %s md5 %s, profile %s, proxy %s). Telemetry frames %s, events %s. "
             "Sandbox restore: STRLKUP.DLL md5 %s after the run; quit: %s; errors: %s; warnings: %s." % (
                 time.strftime("%Y-%m-%d %H:%M"), man.get("out"), man.get("poke", {}).get("route"), os.path.basename((man.get("exe") or {}).get("path", "?")),
                 (man.get("exe") or {}).get("md5", "?")[:8], man.get("profile"), (man.get("proxy") or {}).get("md5", "?")[:8],
                 tel.get("frames"), tel.get("events"), man.get("proxy_restored", "?")[:8] if man.get("proxy_restored") else "NOT RESTORED",
                 man.get("quit"), man.get("errors"), man.get("warnings")))
    L.append("")
    L.append("Each expectation: observe (A1), observe (A2) with nothing changed (the A/A control), set the tunable with "
             "i76tune (read back), observe (B), reset (pristine bytes / saved live value, read back), observe (A3). `formula` "
             "grades PASS when >= 98% of the frames that satisfy `when` are within tolerance in A1, A2 (default x), B (set x) and "
             "A3 (default x); increase / decrease / unchanged compare B with the A mean beyond max(2 x |A1 - A2|, min_delta). "
             "INCONCLUSIVE when no field can observe the change, the probe produced too few frames, the A/A pair disagrees, or "
             "the write did not read back.")
    L.append("")
    L.append("## Results")
    L.append("")
    L.append("| # | expectation | tunable (scope, addr) | default -> set | relation | observable | A1 | A2 | B | A3 | grade | why |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, res in enumerate(results):
        for x in res.get("expect", []):
            obsv = x.get("field") or x.get("metric") or "-"
            if x.get("metric") and x.get("field"):
                obsv = "%s(%s)" % (x["metric"], x["field"])

            def cell(k):
                g = x.get(k)
                if g is None:
                    return "-"
                if isinstance(g, dict):
                    if g.get("ok") is None:
                        return "n/a (%s)" % g.get("note", g.get("considered"))
                    if "rate" in g:
                        return "%s %d/%d err<=%s" % ("ok" if g["ok"] else "FAIL", g["matched"], g["considered"], fmt(g["max_err"]))
                    return "%s %s vs %s" % ("ok" if g["ok"] else "FAIL", fmt(g.get("value")), fmt(g.get("expected")))
                return fmt(g)
            L.append("| %d | %s | %s (%s, %s) | %s -> %s | %s | %s | %s | %s | %s | %s | **%s** | %s |" % (
                i + 1, res["id"], res["tunable"], res.get("scope"), res.get("addr"), fmt(res.get("x_default")), fmt(res.get("x_set")),
                x["relation"], obsv, cell("A1"), cell("A2"), cell("B"), cell("A3"), x["grade"], x["why"].replace("|", "/")))
    L.append("")
    counts = {}
    for res in results:
        counts[res["grade"]] = counts.get(res["grade"], 0) + 1
    L.append("Per expectation: " + ", ".join("%s %d" % kv for kv in sorted(counts.items())) + " of %d." % len(results))
    L.append("")
    L.append("## Details")
    L.append("")
    for i, res in enumerate(results):
        L.append("### %d. %s" % (i + 1, res["id"]))
        L.append("")
        L.append("- tunable `%s` (%s scope, %s; spec %s); live before %s, set %s (read back %s, %s), reset read back %s (%s)." % (
            res["tunable"], res.get("scope"), res.get("addr"), res.get("spec"), fmt(res.get("live_before")), fmt(res.get("x_set")),
            fmt(res.get("set_read_back")), "ok" if res.get("set_ok") else "not applied", fmt(res.get("reset_read_back")), "ok" if res.get("reset_ok") else "FAILED"))
        if res.get("probe"):
            L.append("- probe %s; frames per observation: A1 %s, A2 %s, B %s, A3 %s; t = %s..%s s." % (
                json.dumps(res["probe"]), (res.get("probe_A1") or {}).get("frames"), (res.get("probe_A2") or {}).get("frames"),
                (res.get("probe_B") or {}).get("frames"), (res.get("probe_A3") or {}).get("frames"), res.get("t_scn"), res.get("t_end_scn")))
        if res.get("note"):
            L.append("- note: %s" % res["note"])
        for x in res.get("expect", []):
            L.append("- `%s` %s %s: **%s** - %s" % (x["relation"], x.get("field") or x.get("metric") or "", ("when `%s`" % x["when"]) if x.get("when") else "", x["grade"], x["why"]))
            for k in ("A1", "A2", "B", "A3"):
                if x.get(k) is not None:
                    L.append("  - %s: %s" % (k, json.dumps(x[k], default=str)))
        L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return path


if __name__ == "__main__":
    sys.exit(main())
