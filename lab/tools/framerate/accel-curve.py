#!/usr/bin/env python3
"""accel-curve.py trace.csv [...] - acceleration vs speed, using LEVEL-GROUND samples only.

Every whole-run comparison (top speed, coast decay) is contaminated by terrain: a car that
wanders downhill gains speed. Instead of hunting for flat ground, filter for it - keep only
samples where the car is level and grounded (|vy| small AND height barely changing), then bin
by speed and report mean dv/dt in each bin.

That yields the engine's acceleration curve a(v), which is a property of the physics model and
is directly comparable across frame rates. If the curves coincide, the drivetrain/drag model is
frame-rate independent and any whole-run difference was terrain, not physics.
"""
import csv, sys, statistics

def load(p):
    with open(p) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]

BINS = [(5,10),(10,15),(15,20),(20,25),(25,30),(30,35)]

def curve(rows):
    out = {b: [] for b in BINS}
    for i in range(1, len(rows)):
        a, b = rows[i-1], rows[i]
        dt = (b['t_ms'] - a['t_ms']) / 1000.0
        if dt <= 0: continue
        dy = abs(b['y'] - a['y'])
        # level and grounded: not airborne, and height essentially unchanged
        if abs(b['vy']) > 0.6 or dy > 0.06: continue
        v = a['speed']
        dv = (b['speed'] - a['speed']) / dt
        if abs(dv) > 40: continue
        for lo, hi in BINS:
            if lo <= v < hi:
                out[(lo,hi)].append(dv); break
    return out

print("%-22s %6s | %s" % ("trace", "fps", "  ".join("%d-%d" % b for b in BINS)))
for path in sys.argv[1:]:
    rows = load(path)
    span = (rows[-1]['t_ms'] - rows[0]['t_ms']) / 1000.0
    fps = (rows[-1]['frame'] - rows[0]['frame']) / span if span else 0
    c = curve(rows)
    cells = []
    for b in BINS:
        v = c[b]
        cells.append("%6.2f" % statistics.median(v) if len(v) >= 3 else "   n/a")
    print("%-22s %6.1f | %s" % (path.split('\\')[-1], fps, "  ".join(cells)))
print("\nmedian dv/dt (m/s^2) per speed bin, level grounded samples only.")
print("Curves that coincide across frame rates => the acceleration model is frame-rate independent.")
