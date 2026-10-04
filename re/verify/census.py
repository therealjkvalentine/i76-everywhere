r"""census.py - census batches and the per-function cadence classifier (VERIFICATION-PROGRAM section 2.2).

    python verify\census.py make-batches [--size 150] [--prefix physics,entity,...] [--include-unhookable]
                                      [--from-summary runs\phase1-all-summary.json --name never]   (only that summary's `never` functions)
    python verify\census.py classify <run dir>            -> <run>\census.classified.json (+ census\classes.csv via tools\census_classify.py)
    python verify\census.py summary <run dir>             print the class histogram of a classified run

make-batches: symbols\functions.tsv rows with status not synthetic/library, size > 0, name not thunk_*, hookable=yes
(the Frida prologue rule; the others are listed in batches\excluded.json so coverage.py can tell "not hookable"
from "never called"). Ordered by the --prefix list (then address), chunked into batches\batch-NNN.json.

classify: the enum per function from the per-frame series (census.series.bin), the run's telemetry (step_count per
frame, player_present) and events; tools\census_classify.py's thresholds (PRESENCE_MIN 0.9, TICK 0.95..1.05,
TICK_CV 0.2, FRAME_CV 0.5) are imported and its classes.csv is produced on the same run as the legacy cross-check.
  never        0 calls in the run (section 2.2 reads 'in every scenario': that is coverage.py)
  init_only    calls only before scenario start + 5 s (mission load, first frames)
  menu_only    calls only on frames without a live player (menu-* scenarios; otherwise 'irregular'); in a menu-boot run
               (manifest boot == "menu": no entity, no frame counter) the census\counts.csv snapshots split the run at the
               moment the shell came up (start_wall_ms): calls after it = menu_only, calls only before it = init_only
  (live frames = window frames with player_present and without the destroyed/wreck flags 0x8020; the wrecked tail
   is excluded from the shares and reported as frames_wrecked_excluded / first_wreck_frame)
  per_substep  on >= 95% of live frames calls == a + b x step_count (b >= 1 integer: calls per substep summed over the
               vehicles stepped, a >= 0 a per-frame constant; best of frame offset -1/0/+1); needs >= 2 step_count values
               in the run (stock20 gives 1 and 2; stock60 gives only 1, where per_substep cannot be told from per_frame)
  per_frame    on >= 95% of window frames calls == k (k >= 1; k reported), or steady (presence >= 0.9, cv < 0.5)
  per_event    present on < 50% of window frames; event_corr = share of call frames within +-2 frames of a telemetry
               event or a key action
  irregular    everything else with calls > 0
"""
import argparse
import csv
import json
import os
import statistics
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BATCHES, FUNCTIONS_TSV, TOOLS, Functions, ensure_dirs, tools_path  # noqa: E402

tools_path()
import census_classify  # noqa: E402  (tools/census_classify.py: thresholds)

PRESENCE_MIN, FRAME_CV = census_classify.PRESENCE_MIN, census_classify.FRAME_CV
MATCH_MIN = 0.95
EVENT_PRESENCE_MAX = 0.5
INIT_WINDOW_S = 5.0
CLASSES = ("per_frame", "per_substep", "per_event", "init_only", "never", "menu_only", "irregular")


# ------------------------------------------------------------------------------------------------ make-batches
def make_batches(a):
    ensure_dirs()
    fn = Functions()
    prefixes = [p.strip() for p in a.prefix.split(",") if p.strip()] if a.prefix else []
    only = None
    if a.from_summary:          # phase1_summary.py output: keep the functions it classed `never` (0 calls in every run)
        summ = json.load(open(a.from_summary, encoding="utf-8"))
        only = {int(addr, 16) for addr, f in summ["functions"].items() if f.get("overall") == "never"}
    rows, excluded = [], []
    for r in fn.rows:
        why = None
        if only is not None and r["addr"] not in only:
            continue
        if r["status"] in ("synthetic", "library"):
            why = "status " + r["status"]
        elif r["size"] <= 0:
            why = "size 0"
        elif r["name"].startswith("thunk_") or r["subsystem"] == "thunk":
            why = "thunk"
        elif r["hookable"] != "yes" and not a.include_unhookable:
            why = "hookable=" + (r["hookable"] or "?")
        if prefixes and not any(r["name"].startswith(p + "_") or r["name"] == p for p in prefixes):
            continue
        (excluded if why else rows).append(dict(r, reason=why) if why else r)

    def order(r):
        for i, p in enumerate(prefixes):
            if r["name"].startswith(p + "_"):
                return (i, r["addr"])
        return (len(prefixes), r["addr"])
    rows.sort(key=order)
    written = []
    for i in range(0, len(rows), a.size):
        part = rows[i:i + a.size]
        bid = "%s-%03d" % (a.name, i // a.size + 1)
        out = os.path.join(BATCHES, bid + ".json")
        json.dump({"batch": bid, "size": len(part), "filter": {"prefix": prefixes, "size": a.size, "hookable": "yes" if not a.include_unhookable else "any",
                                                              "from_summary": a.from_summary},
                   "functions_tsv_md5": fn.md5, "functions": [{"addr": "0x%x" % r["addr"], "name": r["name"], "size": r["size"], "status": r["status"],
                                                               "hookable": r["hookable"], "subsystem": r["subsystem"]} for r in part]},
                  open(out, "w", encoding="utf-8"), indent=1)
        written.append((bid, len(part), part[0]["name"], part[-1]["name"]))
    json.dump({"functions_tsv_md5": fn.md5, "filter": {"prefix": prefixes}, "excluded": [
        {"addr": "0x%x" % r["addr"], "name": r["name"], "size": r["size"], "status": r["status"], "hookable": r["hookable"], "reason": r["reason"]} for r in excluded]},
              open(os.path.join(BATCHES, ("excluded.json" if a.name == "batch" else a.name + "-excluded.json")), "w", encoding="utf-8"), indent=1)
    for bid, n, first, last in written:
        print("%s  %3d functions  %s .. %s" % (bid, n, first, last))
    print("%d functions in %d batches; %d excluded (batches\\excluded.json); functions.tsv md5 %s" % (len(rows), len(written), len(excluded), fn.md5))
    return 0


# ------------------------------------------------------------------------------------------------ classify
def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_run(run):
    man = json.load(open(os.path.join(run, "manifest.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(run, "census.series.json"), encoding="utf-8"))
    n, cap = len(meta["addrs"]), meta["cap"]
    raw = open(os.path.join(run, "census.series.bin"), "rb").read()
    series = [struct.unpack_from("<%dH" % cap, raw, 2 * cap * j) for j in range(n)]
    jl = [json.loads(l) for l in open(os.path.join(run, "census.jsonl"), encoding="utf-8") if l.strip()]
    tel = read_csv(os.path.join(run, "telemetry.csv"))
    evs = read_csv(os.path.join(run, "events.csv")) if os.path.exists(os.path.join(run, "events.csv")) else []
    acts = read_csv(os.path.join(run, "actions.csv")) if os.path.exists(os.path.join(run, "actions.csv")) else []
    return man, meta, series, jl, tel, evs, acts


def classify_menu_run(run, man, jl):
    """Boot kind "menu" (scenarios\\menu-idle.json): no entity, no frame counter, so the per-frame series is useless;
    the census\\counts.csv snapshots (cumulative calls per function every snapshot_ms, t_ms = epoch ms) split the run at
    the manifest's start_wall_ms (the moment the game state read 6 = shell up): calls only before it = init_only
    (startup, loaders, intro movies), calls after it = menu_only (the shell main menu sitting)."""
    snaps = read_csv(os.path.join(run, "census", "snapshots.csv"))
    with open(os.path.join(run, "census", "counts.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    addrs = rows[0][1:]
    counts = {int(r[0]): [int(x) for x in r[1:]] for r in rows[1:] if r}
    start_ms, end_ms = man.get("start_wall_ms"), man.get("end_wall_ms")
    if start_ms is None or not snaps:
        raise SystemExit("menu run has no start_wall_ms / snapshots: %s" % run)
    snap_start = next((int(s["snap"]) for s in snaps if int(s["t_ms"]) >= start_ms), None)
    snap_end = max(counts)
    if end_ms:
        snap_end = max((int(s["snap"]) for s in snaps if int(s["t_ms"]) <= end_ms), default=snap_end)
    if snap_start is None or snap_start not in counts:
        snap_start = snap_end
    c0, c1 = counts[snap_start], counts[snap_end]
    sit_s = (int(next(s["t_ms"] for s in snaps if int(s["snap"]) == snap_end)) - int(next(s["t_ms"] for s in snaps if int(s["snap"]) == snap_start))) / 1000.0
    out_fns = []
    counts_by_class = {c: 0 for c in CLASSES}
    for j, rec in enumerate(jl):
        res = {"addr": rec["addr"], "name": rec["name"], "hook": rec["hook"], "calls": rec["calls"], "callers": rec["callers"],
               "first_frame": rec["first_frame"], "last_frame": rec["last_frame"]}
        if rec["hook"] != "attached":
            res.update({"class": "not_hooked", "note": rec["hook"]})
            out_fns.append(res)
            continue
        if rec["calls"] == 0:
            res.update({"class": "never", "note": "0 calls in this run (coverage.py for 'every scenario')"})
            counts_by_class["never"] += 1
            out_fns.append(res)
            continue
        if addrs[j].lower() != rec["addr"].lower():
            raise SystemExit("counts.csv column %d is %s, census.jsonl row is %s" % (j, addrs[j], rec["addr"]))
        boot_calls, menu_calls = c0[j], c1[j] - c0[j]
        res.update({"calls_boot": boot_calls, "calls_menu": menu_calls, "menu_sit_s": round(sit_s, 1),
                    "menu_rate_per_s": round(menu_calls / sit_s, 3) if sit_s > 0 else None})
        if menu_calls == 0:
            cls, note = "init_only", "%d calls before the shell menu was up (boot, loaders, intro; game state 6 at %.1f s), none while it sat %.0f s" % (boot_calls, man.get("menu_t") or -1, sit_s)
        else:
            cls, note = "menu_only", "%d calls while the main menu sat %.0f s (%.1f/s), %d before it (boot + intro)" % (menu_calls, sit_s, menu_calls / sit_s if sit_s > 0 else 0, boot_calls)
        res.update({"class": cls, "note": note, "legacy_class": None})
        counts_by_class[cls] += 1
        out_fns.append(res)
    f0 = man.get("start_frame")
    out = {"run": run, "scenario": man["scenario"], "profile": man.get("profile"), "boot": "menu", "window": [f0, man.get("end_frame")], "frames": 0, "frames_live": 0,
           "init_end_frame": None, "frames_player_present": 0, "frames_wrecked_excluded": 0, "first_wreck_frame": None, "step_count_hist": {}, "steps_all_one": False,
           "telemetry_frames": 0, "events": 0, "classes": counts_by_class,
           "menu": {"snap_start": snap_start, "snap_end": snap_end, "sit_s": round(sit_s, 1), "menu_t_after_launch": man.get("menu_t"), "menu_up": man.get("menu_up"), "esc_sent": man.get("esc_sent")},
           "thresholds": {"rule": "init_only: no call after the game state read 6; menu_only: calls while the menu sat"},
           "legacy": {"tool": None, "summary": "menu boot: no frame series, census_classify.py not run"}, "functions": out_fns}
    p = os.path.join(run, "census.classified.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print(json.dumps({"run": run, "classes": counts_by_class, "menu": out["menu"]}))
    return out


def classify_run(run):
    man, meta, series, jl, tel, evs, acts = load_run(run)
    if man.get("boot") == "menu":
        return classify_menu_run(run, man, jl)
    base, cap = meta["base_frame"], meta["cap"]
    f0, f1 = man.get("start_frame"), man.get("end_frame")
    if f0 is None or f1 is None or f1 < f0:
        raise SystemExit("run has no scenario window (start_frame/end_frame): %s" % run)
    # telemetry per sim frame: the last row published for that frame counter value
    tel_by_frame = {}
    for row in tel:
        try:
            fr = int(row["frame"])
        except (KeyError, ValueError):
            continue
        tel_by_frame[fr] = row
    proxy_to_frame = {int(r["proxy_frame"]): int(r["frame"]) for r in tel if r.get("proxy_frame")}
    window = list(range(f0, f1 + 1))
    WRECK_FLAGS = 0x8020                 # ent+0x454: 0x20 destroyed, 0x8000 wreck (i76tel.h)
    present = [f for f in window if tel_by_frame.get(f, {}).get("player_present") == "1"]
    wrecked = [f for f in present if int(tel_by_frame[f].get("flags") or 0) & WRECK_FLAGS]
    live = [f for f in present if f not in set(wrecked)]      # cadence is graded on the live, driveable car only
    first_wreck_frame = wrecked[0] if wrecked else None
    live_set = set(live)
    steps = {f: int(tel_by_frame[f]["step_count"]) for f in live if tel_by_frame[f].get("step_count") not in (None, "", "-1")}
    step_hist = {}
    for s in steps.values():
        step_hist[s] = step_hist.get(s, 0) + 1
    steps_all_one = bool(steps) and set(steps.values()) == {1}
    # init window: start + 5 s of sim time
    t_start = float(tel_by_frame[f0]["sim_time"]) if f0 in tel_by_frame and tel_by_frame[f0].get("sim_time") else None
    init_end = f0
    if t_start is not None:
        for f in window:
            row = tel_by_frame.get(f)
            if row and float(row["sim_time"]) <= t_start + INIT_WINDOW_S:
                init_end = f
    else:
        init_end = f0 + int(INIT_WINDOW_S * 20)
    # event frames (telemetry events are stamped with proxy_frame) and key actions (sim frame)
    event_frames = {}
    for e in evs:
        try:
            fr = proxy_to_frame.get(int(e["frame"]))
        except (KeyError, ValueError):
            fr = None
        if fr is not None:
            event_frames.setdefault(fr, set()).add({"1": "shot", "2": "explosion", "3": "impact"}.get(e.get("type"), e.get("type")))
    for ac in acts:
        if ac.get("action") in ("key-down", "key-up", "tap") and ac.get("frame"):
            try:
                event_frames.setdefault(int(ac["frame"]), set()).add("key")
            except ValueError:
                pass
    near_event = set()
    for fr in event_frames:
        for d in range(-2, 3):
            near_event.add(fr + d)

    out_fns = []
    counts_by_class = {c: 0 for c in CLASSES}
    for j, rec in enumerate(jl):
        s = series[j]
        calls_total = rec["calls"]
        res = {"addr": rec["addr"], "name": rec["name"], "hook": rec["hook"], "calls": calls_total, "callers": rec["callers"],
               "first_frame": rec["first_frame"], "last_frame": rec["last_frame"]}
        if rec["hook"] != "attached":
            res.update({"class": "not_hooked", "note": rec["hook"]})
            out_fns.append(res)
            continue
        if calls_total == 0:
            res.update({"class": "never", "note": "0 calls in this run (coverage.py for 'every scenario')"})
            counts_by_class["never"] += 1
            out_fns.append(res)
            continue

        def cnt(f):
            d = f - base
            return s[d] if 0 <= d < cap else 0
        win_counts = [cnt(f) for f in window]
        win_calls = sum(win_counts)
        live_counts = [cnt(f) for f in live]
        live_calls = sum(live_counts)
        calls_after_init = sum(cnt(f) for f in window if f > init_end)
        res["calls_in_window"] = win_calls
        res["calls_live_frames"] = live_calls
        res["frames_live"] = len(live)
        if calls_after_init == 0:
            # everything happened at or before init_end (pre-base calls and frames before the window included)
            res.update({"class": "init_only", "note": "no call after scenario start + %.0f s (frame %d); %d calls before/at it, %d before the hook's base frame" % (
                INIT_WINDOW_S, init_end, calls_total - calls_after_init, rec["pre_base_calls"])})
            counts_by_class["init_only"] += 1
            out_fns.append(res)
            continue
        if live and live_calls == 0 and win_calls > 0:
            cls = "menu_only" if man["scenario"].startswith("menu") else "irregular"
            res.update({"class": cls, "note": "calls only on frames without a live player (%d in window)" % win_calls})
            counts_by_class[cls] += 1
            out_fns.append(res)
            continue
        n_live = len(live) or 1
        fwc = sum(1 for c in live_counts if c > 0)
        presence = fwc / n_live
        nz = [c for c in live_counts if c > 0]
        mode = max(set(nz), key=nz.count) if nz else 0
        mode_share = sum(1 for c in live_counts if c == mode) / n_live
        mean = statistics.fmean(live_counts) if live_counts else 0.0
        cv = (statistics.pstdev(live_counts) / mean) if (len(live_counts) > 1 and mean > 0) else float("nan")
        # substep fit: count = a + b x step_count (b = calls per substep summed over the vehicles stepped, a = a per-frame
        # constant, e.g. the far vehicles' lite step), tried at frame offsets -1, 0, +1 (the hook stamps the counter at
        # call time; the telemetry row is the completed frame). The live run showed offset 0 fits exactly.
        best_off, best_match, best_ab = 0, 0.0, (0, 0)
        if steps and len(set(steps.values())) >= 2:
            svals = sorted(set(steps.values()))
            for off in (-1, 0, 1):
                modes = {}
                for sv in svals:
                    cs = [cnt(f + off) for f in live if steps.get(f) == sv]
                    modes[sv] = max(set(cs), key=cs.count) if cs else 0
                s1, s2 = svals[0], svals[-1]
                b = (modes[s2] - modes[s1]) / float(s2 - s1)
                a = modes[s1] - b * s1
                if b != int(b) or b < 1 or a < 0:
                    continue
                a, b = int(a), int(b)
                m = sum(1 for f in live if f in steps and cnt(f + off) == a + b * steps[f])
                share = m / len(steps)
                if share > best_match:
                    best_off, best_match, best_ab = off, share, (a, b)
        call_frames = [f for f, c in zip(live, live_counts) if c > 0]
        event_corr = (sum(1 for f in call_frames if f in near_event) / len(call_frames)) if call_frames else 0.0
        res.update({"presence": round(presence, 4), "mode_count": mode, "mode_share": round(mode_share, 4), "mean_per_frame": round(mean, 4),
                    "cv": round(cv, 4) if cv == cv else None, "substep_match": round(best_match, 4), "substep_offset": best_off,
                    "per_substep_mult": best_ab[1], "per_frame_const": best_ab[0], "event_corr": round(event_corr, 3)})
        if steps and best_match >= MATCH_MIN and not steps_all_one:
            cls, note = "per_substep", "calls = %d + %d x step_count on %.1f%% of live frames (offset %d; %d per substep summed over the vehicles stepped, %d per frame); step_count hist %s" % (
                best_ab[0], best_ab[1], 100 * best_match, best_off, best_ab[1], best_ab[0], step_hist)
        elif mode_share >= MATCH_MIN and mode >= 1:
            cls = "per_frame"
            note = "%d call(s) on %.1f%% of live frames (k = calls per frame, summed over objects)" % (mode, 100 * mode_share)
            if steps_all_one:
                note += "; step_count was 1 on every frame: per_substep indistinguishable in this run"
            elif steps:
                note += "; not step-dependent (best substep fit %.1f%%)" % (100 * best_match)
        elif presence >= PRESENCE_MIN and cv == cv and cv < FRAME_CV:
            cls, note = "per_frame", "steady: present on %.1f%% of live frames, mean %.2f/frame, cv %.2f (legacy per-frame rule)" % (100 * presence, mean, cv)
        elif presence < EVENT_PRESENCE_MAX:
            cls, note = "per_event", "bursty: present on %.1f%% of live frames, %.0f%% of call frames within 2 frames of a telemetry event or key" % (100 * presence, 100 * event_corr)
        else:
            cls, note = "irregular", "present on %.1f%% of live frames, mode %d (%.1f%%), cv %s" % (100 * presence, mode, 100 * mode_share, res["cv"])
        res.update({"class": cls, "note": note})
        counts_by_class[cls] += 1
        out_fns.append(res)

    # legacy cross-check: tools/census_classify.py on the same run (census\snapshots.csv, counts.csv, targets.csv)
    legacy = {}
    try:
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "census_classify.py"), "--dir", run], capture_output=True, text=True)
        cpath = os.path.join(run, "census", "classes.csv")
        if os.path.exists(cpath):
            for row in read_csv(cpath):
                legacy[row["addr"]] = row["class"]
        legacy_note = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
    except Exception as e:  # noqa: BLE001
        legacy_note = ["census_classify.py failed: %r" % (e,)]
    for f in out_fns:
        f["legacy_class"] = legacy.get(f["addr"])
    out = {"run": run, "scenario": man["scenario"], "profile": man.get("profile"), "window": [f0, f1], "frames": len(window), "frames_live": len(live),
           "init_end_frame": init_end, "frames_player_present": len(present), "frames_wrecked_excluded": len(wrecked), "first_wreck_frame": first_wreck_frame, "step_count_hist": {str(k): v for k, v in sorted(step_hist.items())}, "steps_all_one": steps_all_one,
           "telemetry_frames": len(tel), "events": len(evs), "classes": counts_by_class, "thresholds": {
               "match_min": MATCH_MIN, "presence_min": PRESENCE_MIN, "frame_cv": FRAME_CV, "event_presence_max": EVENT_PRESENCE_MAX, "init_window_s": INIT_WINDOW_S},
           "legacy": {"tool": "tools/census_classify.py", "summary": legacy_note[0] if legacy_note else ""},
           "functions": out_fns}
    p = os.path.join(run, "census.classified.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print(json.dumps({"run": run, "classes": counts_by_class, "frames": len(window), "frames_live": len(live), "step_count_hist": out["step_count_hist"]}))
    return out


def summary(run):
    c = json.load(open(os.path.join(run, "census.classified.json"), encoding="utf-8"))
    print("%s  %s  window %s frames %d live %d  steps %s" % (c["scenario"], c.get("profile"), c["window"], c["frames"], c["frames_live"], c["step_count_hist"]))
    for cls in CLASSES:
        fs = [f for f in c["functions"] if f["class"] == cls]
        print("%-12s %3d  %s" % (cls, len(fs), ", ".join(f["name"] for f in fs[:8]) + (" ..." if len(fs) > 8 else "")))
    nh = [f for f in c["functions"] if f["class"] == "not_hooked"]
    if nh:
        print("%-12s %3d  %s" % ("not_hooked", len(nh), "; ".join("%s (%s)" % (f["name"], f["note"][:60]) for f in nh)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    mb = sub.add_parser("make-batches")
    mb.add_argument("--size", type=int, default=150)
    mb.add_argument("--prefix", default="", help="comma-separated name prefixes (physics,entity,...); empty = every function")
    mb.add_argument("--include-unhookable", action="store_true")
    mb.add_argument("--from-summary", default=None, help="a phase1_summary.py JSON: batch only the functions it classed `never`")
    mb.add_argument("--name", default="batch", help="batch file stem (batch-NNN.json); another name keeps the phase-1 batches and excluded.json untouched")
    cl = sub.add_parser("classify")
    cl.add_argument("run")
    sm = sub.add_parser("summary")
    sm.add_argument("run")
    a = ap.parse_args()
    if a.cmd == "make-batches":
        return make_batches(a)
    if a.cmd == "classify":
        classify_run(a.run)
        return 0
    if a.cmd == "summary":
        return summary(a.run)


if __name__ == "__main__":
    sys.exit(main())
