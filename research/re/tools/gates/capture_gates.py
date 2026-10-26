#!/usr/bin/env python3
"""capture_gates.py - manifest validators for the capture-time gates of FOLDIN-REPORT section 3 (p5-foldin-merge).

Used by the capture tools (tools\\snapshot.py, tools\\frida_gettick.py, the Task 10 scripts) before a capture is
accepted, and runnable standalone:

    python tools\\gates\\capture_gates.py captures\\<id>\\manifest.json [--json]
    python tools\\gates\\capture_gates.py --all [--map M] [--json]        every captures\\*\\manifest.json
    python tools\\gates\\capture_gates.py --selftest                       the built-in positive/negative manifests

Each gate returns PASS / FAIL / N/A with one message per failing item; a capture is voided (H4) when any applicable
gate FAILs. The gates read manifest fields only; they never launch anything and never write (H10).

Manifest contract (schema 2; the legacy schema-1 manifests 001-003 pre-date these fields and report N/A):
  tick_rate_hz          number      G-UNITS: the sim tick rate every threshold/duration is expressed against
  stimuli               [ {name, kind, fired_canary: {kind, before, after|value}, stimulus_fired: bool} ]   G-STIM
  predicates            [ {name, threshold, unit: s|ticks|value, duration, duration_unit: s|ticks} ]         G-UNITS
  reads                 [ {name, method: bulk|ring|external|paused, sim_advancing: bool, torn_possible: bool,
                           coherence_claim: bool} ]                                                            G-TORN
  funnel                {rows: [{name, candidates, survivors}], positive_control: {name, passed: bool}}       G-POS
  hooks                 [ {name, kind: hook|proxy|patch, fired_counter: int, source: which_build|self-report} ] G-ATTEST
  dgvoodoo              {sections: {General: {...}, Glide: {...}, DirectX: {...}}, misplaced: [...]}           G-CONF
  restore_attempted     bool (must be absent or false)                                                         G-NORESTORE
"""
import os, sys, json, glob, argparse

# dgVoodoo.conf key ownership (G-CONF; tools\which_build.py holds the same table, read from dgVoodooCpl's template)
CONF_OWNER = {"ScalingMode": "General", "EnableInactiveAppState": "Glide", "FPSLimit": "Glide", "Resolution": ("Glide", "DirectX")}
LEGACY_KEYS = ("stimuli", "predicates", "reads", "funnel", "hooks", "dgvoodoo", "tick_rate_hz")


def _res(gate, verdict, fails, notes=None):
    return {"gate": gate, "verdict": verdict, "fails": fails, "notes": notes or []}


def g_stim(m):
    """G-STIM: every scripted stimulus records an independent observable proving it fired (`stimulus_fired`
    with its canary); a dead stimulus voids the capture. Root cause of C2 (fire bound to Space while the block bound Enter)."""
    st = m.get("stimuli")
    if st is None:
        return _res("G-STIM", "N/A", [], ["no stimuli in manifest"])
    fails = []
    for s in st:
        nm = s.get("name", "?")
        c = s.get("fired_canary")
        if not isinstance(c, dict) or not c.get("kind"):
            fails.append("stimulus %s: no fired_canary {kind, before, after|value} (an independent observable)" % nm); continue
        if c["kind"] not in ("ammo-delta", "GetAsyncKeyState", "entity-velocity", "input-state-byte", "hud-screenshot", "frame-counter", "other"):
            fails.append("stimulus %s: canary kind %r not in the vocabulary" % (nm, c["kind"]))
        if "stimulus_fired" not in s:
            fails.append("stimulus %s: stimulus_fired missing" % nm); continue
        if s["stimulus_fired"] is not True:
            fails.append("stimulus %s: stimulus_fired=%r -> dead stimulus voids the capture" % (nm, s["stimulus_fired"]))
        if "before" in c and "after" in c and c["before"] == c["after"] and s["stimulus_fired"] is True:
            fails.append("stimulus %s: canary before == after (%r) but stimulus_fired claims true" % (nm, c["before"]))
    return _res("G-STIM", "FAIL" if fails else "PASS", fails, ["%d stimuli" % len(st)])


def g_units(m):
    """G-UNITS: capture predicates state thresholds and durations in seconds or ticks with the tick rate in the
    manifest; frame counts are never a predicate."""
    pr = m.get("predicates")
    if pr is None:
        return _res("G-UNITS", "N/A", [], ["no predicates in manifest"])
    fails = []
    tr = m.get("tick_rate_hz")
    if not isinstance(tr, (int, float)) or tr <= 0:
        fails.append("tick_rate_hz missing or not positive (%r); every threshold/duration is expressed against it" % (tr,))
    for p in pr:
        nm = p.get("name", "?")
        u = p.get("unit"); du = p.get("duration_unit")
        if u in ("frames", "frame") or du in ("frames", "frame"):
            fails.append("predicate %s: frame counts are never a predicate (unit=%r duration_unit=%r)" % (nm, u, du))
        if "threshold" in p and u not in ("s", "ticks", "value"):
            fails.append("predicate %s: threshold unit %r not in s|ticks|value" % (nm, u))
        if "duration" in p and du not in ("s", "ticks"):
            fails.append("predicate %s: duration_unit %r not in s|ticks" % (nm, du))
    return _res("G-UNITS", "FAIL" if fails else "PASS", fails, ["%d predicates, tick_rate_hz=%r" % (len(pr), tr)])


def g_torn(m):
    """G-TORN: an external ReadProcessMemory taken while the sim advances is tagged torn-possible; coherence claims
    (matrices, float3) need the in-process ring, PAUSE_GAME, or one bulk read."""
    rd = m.get("reads")
    if rd is None:
        return _res("G-TORN", "N/A", [], ["no reads in manifest"])
    fails = []
    for r in rd:
        nm = r.get("name", "?")
        meth = r.get("method")
        if meth not in ("bulk", "ring", "external", "paused"):
            fails.append("read %s: method %r not in bulk|ring|external|paused" % (nm, meth)); continue
        adv = r.get("sim_advancing", True)
        if meth == "external" and adv and r.get("torn_possible") is not True:
            fails.append("read %s: external read while the sim advances must be tagged torn_possible: true" % nm)
        if r.get("coherence_claim") and (meth == "external" and adv):
            fails.append("read %s: coherence claim on a torn-possible external read (needs ring, paused, or one bulk read)" % nm)
    return _res("G-TORN", "FAIL" if fails else "PASS", fails, ["%d reads" % len(rd)])


def g_norestore(m):
    """G-NORESTORE: the snapshot ring and all captures are read-only instruments; process-state restore is out of scope."""
    if m.get("restore_attempted"):
        return _res("G-NORESTORE", "FAIL", ["restore_attempted=%r: process-state restore is out of scope (three attempts killed the game)" % m["restore_attempted"]])
    return _res("G-NORESTORE", "PASS", [], ["no restore attempted"])


def g_attest(m):
    """G-ATTEST: every hook, proxy and byte patch exports a fired-counter that which_build.py reads into the manifest;
    count 0 during a capture voids it; 'verified' means the user's workflow ran, not a synthetic probe."""
    hk = m.get("hooks")
    if hk is None:
        return _res("G-ATTEST", "N/A", [], ["no hooks in manifest"])
    fails = []
    for h in hk:
        nm = h.get("name", "?")
        fc = h.get("fired_counter")
        if not isinstance(fc, int):
            fails.append("hook %s: fired_counter missing or not an integer (%r)" % (nm, fc)); continue
        if fc == 0:
            fails.append("hook %s: fired_counter 0 during the capture -> voided" % nm)
        if h.get("source") not in ("which_build", "self-report"):
            fails.append("hook %s: counter source %r not in which_build|self-report" % (nm, h.get("source")))
        if h.get("verified") is True and h.get("verified_by") != "user-workflow":
            fails.append("hook %s: 'verified' requires verified_by: user-workflow (a synthetic probe is not verification)" % nm)
    return _res("G-ATTEST", "FAIL" if fails else "PASS", fails, ["%d hooks/proxies/patches" % len(hk)])


def g_conf(m):
    """G-CONF: which_build.py parses dgVoodoo.conf section-aware and records the effective
    EnableInactiveAppState/FPSLimit/Resolution/ScalingMode per section; a key outside its owning section is a warning."""
    dv = m.get("dgvoodoo")
    if dv is None:
        return _res("G-CONF", "N/A", [], ["no dgvoodoo block in manifest"])
    fails, notes = [], []
    secs = dv.get("sections")
    if not isinstance(secs, dict):
        fails.append("dgvoodoo.sections missing: the conf must be recorded per section, not flat")
        return _res("G-CONF", "FAIL", fails)
    for key, owner in CONF_OWNER.items():
        owners = owner if isinstance(owner, tuple) else (owner,)
        for sec, kv in secs.items():
            if isinstance(kv, dict) and key in kv and sec not in owners:
                notes.append("warning: %s found in [%s], owning section(s) %s (the weeks-long [Glide] misplacement)" % (key, sec, "/".join(owners)))
    for mp in dv.get("misplaced", []) or []:
        notes.append("warning (recorded by which_build): %s" % mp)
    for key in ("FPSLimit", "EnableInactiveAppState"):
        if not any(isinstance(kv, dict) and key in kv for kv in secs.values()):
            notes.append("%s not present in any section (effective value = dgVoodoo default)" % key)
    return _res("G-CONF", "PASS", fails, notes)


def g_pos(m):
    """G-POS: every scan funnel carries one row known to pass (e.g. the ammo write 1234 -> HUD) so an empty result
    is distinguishable from a broken instrument."""
    fn = m.get("funnel")
    if fn is None:
        return _res("G-POS", "N/A", [], ["no funnel in manifest"])
    fails = []
    pc = fn.get("positive_control")
    if not isinstance(pc, dict) or not pc.get("name"):
        fails.append("funnel without positive_control {name, passed}")
    elif pc.get("passed") is not True:
        fails.append("positive control %s did not pass: the instrument is broken, the funnel's null says nothing" % pc.get("name"))
    rows = fn.get("rows") or []
    for r in rows:
        for k in ("candidates", "survivors"):
            if not isinstance(r.get(k), int):
                fails.append("funnel row %s: %s missing (H4: every scan emits candidates -> survivors)" % (r.get("name", "?"), k))
    return _res("G-POS", "FAIL" if fails else "PASS", fails, ["%d funnel rows" % len(rows)])


GATES = [g_stim, g_units, g_torn, g_norestore, g_attest, g_conf, g_pos]


def validate_manifest(m):
    """Run every capture gate on a manifest dict. Returns (voided: bool, results: [ {gate, verdict, fails, notes} ])."""
    if not isinstance(m, dict):
        return True, [_res("manifest", "FAIL", ["manifest is not a JSON object"])]
    res = [g(m) for g in GATES]
    legacy = not any(k in m for k in LEGACY_KEYS)
    if legacy:
        res.append(_res("schema", "N/A", [], ["legacy schema-1 manifest (pre-dates the section-3 gates): capture-time gates report N/A; re-mine under H8 with a reconstructed manifest"]))
    return any(r["verdict"] == "FAIL" for r in res), res


def validate_file(path):
    try:
        m = json.load(open(path, encoding="utf-8"))
    except Exception as ex:
        return True, [_res("manifest", "FAIL", ["%s does not parse: %s" % (path, ex)])]
    return validate_manifest(m)


SELFTEST = {
    "positive": {"tick_rate_hz": 20, "stimuli": [{"name": "fire", "kind": "key-hold", "fired_canary": {"kind": "ammo-delta", "before": 100, "after": 97}, "stimulus_fired": True}],
                 "predicates": [{"name": "idle", "threshold": 0.5, "unit": "s", "duration": 30, "duration_unit": "s"}],
                 "reads": [{"name": "snap", "method": "paused", "sim_advancing": False, "coherence_claim": True}],
                 "funnel": {"rows": [{"name": "armor", "candidates": 1000, "survivors": 0}], "positive_control": {"name": "ammo 1234 -> HUD", "passed": True}},
                 "hooks": [{"name": "u32x", "kind": "proxy", "fired_counter": 12, "source": "which_build"}],
                 "dgvoodoo": {"sections": {"General": {"ScalingMode": "stretched_ar"}, "Glide": {"FPSLimit": 21, "EnableInactiveAppState": True}}, "misplaced": []}},
    "negative": {"tick_rate_hz": 0, "stimuli": [{"name": "fire", "fired_canary": {"kind": "ammo-delta", "before": 100, "after": 100}, "stimulus_fired": True}],
                 "predicates": [{"name": "idle", "threshold": 600, "unit": "frames"}],
                 "reads": [{"name": "ext", "method": "external", "sim_advancing": True, "coherence_claim": True}],
                 "funnel": {"rows": [{"name": "armor", "candidates": 1000}]},
                 "hooks": [{"name": "u32x", "kind": "proxy", "fired_counter": 0, "source": "which_build"}],
                 "dgvoodoo": {"sections": {"General": {"FPSLimit": 21}}}, "restore_attempted": True},
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--map", default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    out = []
    if args.selftest:
        vp, rp = validate_manifest(SELFTEST["positive"])
        vn, rn = validate_manifest(SELFTEST["negative"])
        expect_fail = {"G-STIM", "G-UNITS", "G-TORN", "G-NORESTORE", "G-ATTEST", "G-POS"}
        got_fail = {r["gate"] for r in rn if r["verdict"] == "FAIL"}
        ok = (not vp) and vn and got_fail == expect_fail and any("warning" in n for r in rn if r["gate"] == "G-CONF" for n in r["notes"])
        out.append({"manifest": "selftest", "voided": not ok, "results": [{"gate": "selftest", "verdict": "PASS" if ok else "FAIL",
                    "fails": [] if ok else ["positive voided=%s; negative failing gates %s expected %s" % (vp, sorted(got_fail), sorted(expect_fail))],
                    "notes": ["positive: %s" % [r["verdict"] for r in rp], "negative: %s" % sorted(got_fail)]}]})
    else:
        paths = glob.glob(os.path.join(args.map, "captures", "*", "manifest.json")) if args.all else ([args.manifest] if args.manifest else [])
        if not paths:
            ap.error("give a manifest path, --all, or --selftest")
        for p in sorted(paths):
            voided, res = validate_file(p)
            out.append({"manifest": p, "voided": voided, "results": res})
    rc = 0
    if args.json:
        print(json.dumps(out, indent=1))
    for o in out:
        for r in o["results"]:
            for f in r["fails"]:
                if not args.json: print("FAIL %s %s: %s" % (r["gate"], os.path.basename(os.path.dirname(o["manifest"])) if o["manifest"] != "selftest" else "selftest", f))
            for n_ in r["notes"]:
                if not args.json: print("note %s %s: %s" % (r["gate"], os.path.basename(os.path.dirname(o["manifest"])) if o["manifest"] != "selftest" else "selftest", n_))
        if not args.json:
            print("%s %s (%s)" % (o["manifest"], "VOIDED" if o["voided"] else "ACCEPTED", ", ".join("%s=%s" % (r["gate"], r["verdict"]) for r in o["results"])))
        rc |= 1 if o["voided"] else 0
    return rc


if __name__ == "__main__":
    sys.exit(main())
