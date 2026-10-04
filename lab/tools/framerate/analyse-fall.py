#!/usr/bin/env python3
"""analyse-fall.py fall20.csv fall60.csv - terrain-independent gravity from per-frame traces.

Uses the in-process recorder's per-FRAME samples. Selects only genuinely airborne stretches
(vy decreasing monotonically for several consecutive frames, with enough total change that it
cannot be suspension jitter), fits dvy/dt over each, and reports the distribution.

Terrain cannot bias this: once the car is off the ground only gravity acts, so the slope is
gravity regardless of where the car happens to be.
"""
import csv, sys, statistics

def load(p):
    with open(p) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]

def fall_segments(rows, min_frames=5, min_drop=2.0):
    segs, cur = [], []
    for i in range(1, len(rows)):
        if rows[i]['vy'] < rows[i-1]['vy'] - 1e-6:
            if not cur:
                cur = [rows[i-1]]
            cur.append(rows[i])
        else:
            if len(cur) >= min_frames and (cur[0]['vy'] - cur[-1]['vy']) >= min_drop:
                segs.append(cur)
            cur = []
    if len(cur) >= min_frames and (cur[0]['vy'] - cur[-1]['vy']) >= min_drop:
        segs.append(cur)
    return segs

for path in sys.argv[1:]:
    rows = load(path)
    if len(rows) < 2:
        print("%s: empty" % path); continue
    span = (rows[-1]['t_ms'] - rows[0]['t_ms']) / 1000.0
    fps = (rows[-1]['frame'] - rows[0]['frame']) / span if span else 0
    segs = fall_segments(rows)
    print("\n=== %s ===" % path.split('\\')[-1])
    print("  %d samples, %.1f s, %.1f frames/s" % (len(rows), span, fps))
    if not segs:
        print("  no qualifying free-fall segment (never left the ground long enough)")
        continue
    g_per_s, g_per_f = [], []
    for s in segs:
        dt = (s[-1]['t_ms'] - s[0]['t_ms']) / 1000.0
        df = s[-1]['frame'] - s[0]['frame']
        dv = s[-1]['vy'] - s[0]['vy']
        if dt > 0: g_per_s.append(dv / dt)
        if df > 0: g_per_f.append(dv / df)
    print("  %d free-fall segments (>=5 frames, >=2 m/s drop)" % len(segs))
    longest = max(segs, key=lambda s: s[-1]['t_ms'] - s[0]['t_ms'])
    print("  longest: %.2f s / %d frames, vy %.2f -> %.2f" % (
        (longest[-1]['t_ms']-longest[0]['t_ms'])/1000.0,
        longest[-1]['frame']-longest[0]['frame'], longest[0]['vy'], longest[-1]['vy']))
    if g_per_s:
        print("  gravity per SECOND: median %7.3f m/s^2   (min %.2f max %.2f)" % (
            statistics.median(g_per_s), min(g_per_s), max(g_per_s)))
    if g_per_f:
        print("  gravity per FRAME : median %7.4f m/s      (min %.4f max %.4f)" % (
            statistics.median(g_per_f), min(g_per_f), max(g_per_f)))
print("\nIf per-SECOND medians agree across frame rates, gravity is dt-correct.")
print("If per-FRAME medians agree instead, gravity is applied once per frame (the bug).")
