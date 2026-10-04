#!/usr/bin/env python3
r"""census_classify.py - rate classes per function from a census capture (runbook item 004).

    python tools\census_classify.py --capture 004-census            -> captures\004-census\census\classes.csv
    python tools\census_classify.py --dir <dir with census\>         (test runs outside captures\)

Input (written by tools\frida_run.py --census): census\snapshots.csv (snap,t_ms,frame,gtime,final),
census\counts.csv (cumulative per-hook counters per snapshot; columns = target addresses) and census\targets.csv.

Method. Interval i = snapshot i-1 -> i: dt_ms, dframe = frame delta of the sim frame counter 0x5a7e1c (bss),
dcalls = counter delta. A "moving" interval has dframe > 0 (the sim advanced; menus and PAUSE keep 0x5a7e1c
frozen, so a capture with no moving interval classifies nothing: the null is reported, H4). Per function over
the moving intervals: ratio_i = dcalls_i / dframe_i, presence = share of moving intervals with dcalls > 0,
median ratio, coefficient of variation of ratio_i. Classes:
  never      calls_total == 0 over the whole capture
  init       calls > 0 only in or before the first moving interval, none afterwards (load-time work; the
             census attaches to a running game, so true startup code is 'never' here - stated in the column)
  per-tick   presence >= 0.9 and median ratio in [0.95, 1.05] and cv < 0.2  (once per sim frame)
  per-frame  presence >= 0.9 and cv < 0.5, not per-tick (steady k != 1 calls per sim frame)
  event      anything else with calls > 0 (bursty)
  unclassified-sim-stalled   calls > 0 but no moving interval
Counter reads and the frame read are not one atomic snapshot: a ratio can be off by ~1/dframe per interval,
which the cv threshold absorbs at snapshot_ms >= 1000 (>= 20 frames per interval at 21 fps).
"""
import argparse
import csv
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "0.1"
PRESENCE_MIN, TICK_LO, TICK_HI, TICK_CV, FRAME_CV = 0.9, 0.95, 1.05, 0.2, 0.5


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--capture")
    g.add_argument("--dir")
    ap.add_argument("--out", help="output CSV (default <dir>\\census\\classes.csv)")
    a = ap.parse_args()
    base = a.dir or os.path.join(ROOT, "captures", a.capture)
    cdir = os.path.join(base, "census")
    snaps = read_csv(os.path.join(cdir, "snapshots.csv"))[1:]
    counts = read_csv(os.path.join(cdir, "counts.csv"))
    addrs = counts[0][1:]
    rows = [[int(x) for x in r[1:]] for r in counts[1:]]
    targets = {}
    tpath = os.path.join(cdir, "targets.csv")
    if os.path.exists(tpath):
        for r in read_csv(tpath)[1:]:
            targets[r[1]] = {"name": r[2], "source": r[3], "attached": r[4] == "1", "error": r[5], "fired": int(r[6])}
    man = {}
    mpath = os.path.join(base, "manifest.json")
    if os.path.exists(mpath):
        man = json.load(open(mpath, encoding="utf-8"))
    snapshot_ms = man.get("frida", {}).get("args", {}).get("snapshot_ms", "")
    capture = man.get("capture") or a.capture or os.path.basename(base)
    n = min(len(snaps), len(rows))
    if n < 2:
        print("null: %d snapshots (need >= 2); nothing to classify" % n)
        return 1
    t = [int(s[1]) for s in snaps[:n]]
    frames = [int(s[2]) if s[2] not in ("", "None") else None for s in snaps[:n]]
    intervals = []
    for i in range(1, n):
        df = (frames[i] - frames[i - 1]) if (frames[i] is not None and frames[i - 1] is not None) else None
        intervals.append({"i": i, "dt_ms": t[i] - t[i - 1], "dframe": df, "moving": bool(df and df > 0)})
    moving = [iv for iv in intervals if iv["moving"]]
    first_moving = moving[0]["i"] if moving else None
    sec_moving = sum(iv["dt_ms"] for iv in moving) / 1000.0
    frames_moving = sum(iv["dframe"] for iv in moving)
    funnel = {"snapshots": n, "intervals": len(intervals), "moving_intervals": len(moving),
              "seconds_moving": round(sec_moving, 3), "frames_moving": frames_moving,
              "frame_first": frames[0], "frame_last": frames[n - 1]}
    if not moving:
        print("null: no interval with a frame-counter advance (0x5a7e1c frozen: menu, pause, or wrong target); "
              "classes are never/unclassified-sim-stalled only")
    out = a.out or os.path.join(cdir, "classes.csv")
    classes = {}
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["addr", "addr_class", "name", "attached", "calls_total", "calls_moving", "seconds_moving", "frames_moving",
                    "calls_per_s", "calls_per_frame", "median_ratio", "cv_ratio", "presence", "class",
                    "n_intervals", "n_moving_intervals", "snapshot_ms", "capture", "method_rate", "method_class"])
        method_rate = ("counter deltas between consecutive snapshots; calls_per_s = calls in moving intervals / wall seconds of "
                       "moving intervals; calls_per_frame = same / frame delta of 0x5a7e1c (bss); moving = dframe > 0")
        method_class = ("never: total 0; init: no calls after the first moving interval; per-tick: presence>=%.2f, median ratio "
                        "in [%.2f,%.2f], cv<%.2f; per-frame: presence>=%.2f, cv<%.2f; else event; attach-time census, so "
                        "startup code reads never" % (PRESENCE_MIN, TICK_LO, TICK_HI, TICK_CV, PRESENCE_MIN, FRAME_CV))
        for j, addr in enumerate(addrs):
            tg = targets.get(addr, {})
            total = rows[n - 1][j]
            d = [rows[iv["i"]][j] - rows[iv["i"] - 1][j] for iv in intervals]
            dm = [rows[iv["i"]][j] - rows[iv["i"] - 1][j] for iv in moving]
            calls_moving = sum(dm)
            ratios = [dm[k] / moving[k]["dframe"] for k in range(len(moving))]
            presence = (sum(1 for x in dm if x > 0) / len(dm)) if dm else 0.0
            med = statistics.median(ratios) if ratios else 0.0
            mean = statistics.fmean(ratios) if ratios else 0.0
            cv = (statistics.pstdev(ratios) / mean) if (len(ratios) > 1 and mean > 0) else (0.0 if ratios else float("nan"))
            after_first = sum(d[k] for k, iv in enumerate(intervals) if first_moving is not None and iv["i"] > first_moving)
            if not tg.get("attached", True):
                cls = "not-attached"
            elif total == 0:
                cls = "never"
            elif not moving:
                cls = "unclassified-sim-stalled"
            elif after_first == 0:
                cls = "init"
            elif presence >= PRESENCE_MIN and TICK_LO <= med <= TICK_HI and cv < TICK_CV:
                cls = "per-tick"
            elif presence >= PRESENCE_MIN and cv < FRAME_CV:
                cls = "per-frame"
            else:
                cls = "event"
            classes[cls] = classes.get(cls, 0) + 1
            va = int(addr, 16)
            acls = "init" if 0x401000 <= va < 0x4bbe56 else "other-module"
            w.writerow([addr, acls, tg.get("name", ""), int(tg.get("attached", True)), total, calls_moving, round(sec_moving, 3), frames_moving,
                        round(calls_moving / sec_moving, 3) if sec_moving else "", round(calls_moving / frames_moving, 4) if frames_moving else "",
                        round(med, 4), round(cv, 4) if cv == cv else "", round(presence, 3), cls,
                        len(intervals), len(moving), snapshot_ms, capture, method_rate, method_class])
    back = read_csv(out)
    assert len(back) == len(addrs) + 1, "read-back row count mismatch"
    summary = {"tool": "tools/census_classify.py " + VERSION, "out": out, "functions": len(addrs), "classes": classes, "funnel": funnel}
    print(json.dumps(summary))
    # merge a short block into the manifest (append-only key)
    if man:
        man.setdefault("derived", {})["census_classes"] = summary
        tmp = mpath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(man, f, indent=1, default=str)
        os.replace(tmp, mpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
