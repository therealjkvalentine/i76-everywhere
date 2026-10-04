#!/usr/bin/env python3
"""measure-gravity.py trace.csv [...] - extract effective gravity from free-fall segments.

Finds the longest run of samples where the car is airborne and falling (vy decreasing
monotonically), then fits dvy/dt. That number is the engine's gravity in m/s^2 AS THE PLAYER
EXPERIENCES IT. If gravity is applied per FRAME rather than per second, this value scales with
the frame rate - which is exactly the I'76 falling bug.
"""
import csv, sys

def load(p):
    with open(p) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]

def segments(rows, min_len=4):
    """runs where vy is strictly decreasing (accelerating downward = free fall)"""
    out, cur = [], []
    for i in range(1, len(rows)):
        if rows[i]['vy'] < rows[i-1]['vy'] - 1e-6:
            if not cur: cur = [rows[i-1]]
            cur.append(rows[i])
        else:
            if len(cur) >= min_len: out.append(cur)
            cur = []
    if len(cur) >= min_len: out.append(cur)
    return out

for path in sys.argv[1:]:
    rows = load(path)
    dt_total = (rows[-1]['t_ms'] - rows[0]['t_ms']) / 1000.0
    dframes = rows[-1]['frame'] - rows[0]['frame']
    fps = dframes / dt_total if dt_total else 0
    segs = segments(rows)
    print("\n=== %s ===" % path)
    print("  %.1f frames/s over %.1f s" % (fps, dt_total))
    if not segs:
        print("  no free-fall segment found (car never left the ground)")
        continue
    best = max(segs, key=lambda s: s[-1]['t_ms'] - s[0]['t_ms'])
    dt = (best[-1]['t_ms'] - best[0]['t_ms']) / 1000.0
    dvy = best[-1]['vy'] - best[0]['vy']
    dfr = best[-1]['frame'] - best[0]['frame']
    print("  longest fall: %.2f s, %d frames, vy %.2f -> %.2f" % (dt, dfr, best[0]['vy'], best[-1]['vy']))
    if dt > 0:
        print("  gravity per SECOND : %7.3f m/s^2" % (dvy / dt))
    if dfr > 0:
        print("  gravity per FRAME  : %7.4f m/s per frame" % (dvy / dfr))
    print("  (per-second value should be ~equal across frame rates if physics are correct;")
    print("   per-frame value equal instead means gravity is applied once per frame = the bug)")
