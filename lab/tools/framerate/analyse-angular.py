#!/usr/bin/env python3
"""analyse-angular.py ang20.csv ang60.csv - is orientation integrated per frame or per second?

Compares the rotation the car ACTUALLY achieved (d heading/dt, from the render transform) with
the engine's own reported angular velocity (yaw rate, rad/s).

    ratio ~ 1 at both frame rates  -> orientation is dt-correct, rotation is not the bug
    ratio ~ 1 at 20 Hz, ~3 at 60   -> orientation is advanced ONCE PER FRAME  <-- the bug

Handles the +-pi wrap in heading.
"""
import csv, sys, math, statistics

def load(p):
    with open(p) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]

def unwrap(prev, cur):
    d = cur - prev
    while d > math.pi:  d -= 2*math.pi
    while d < -math.pi: d += 2*math.pi
    return d

for path in sys.argv[1:]:
    rows = load(path)
    if len(rows) < 5:
        print("%s: too few samples" % path); continue
    span = (rows[-1]['t_ms'] - rows[0]['t_ms']) / 1000.0
    fps = (rows[-1]['frame'] - rows[0]['frame']) / span if span else 0
    ratios, dh_per_s, yr, steer = [], [], [], []
    for i in range(1, len(rows)):
        dt = (rows[i]['t_ms'] - rows[i-1]['t_ms']) / 1000.0
        if dt <= 0: continue
        dh = unwrap(rows[i-1]['heading'], rows[i]['heading']) / dt      # rad/s actually turned
        y  = rows[i]['yawrate']                                        # rad/s the engine reports
        if rows[i]['speed'] < 3: continue        # only while genuinely driving
        if abs(y) < 0.05: continue               # only while genuinely turning
        dh_per_s.append(dh); yr.append(y); steer.append(rows[i].get('steer', float('nan')))
        ratios.append(dh / y)
    print("\n=== %s ===" % path.split('\\')[-1])
    print("  %.1f fps, %d usable samples" % (fps, len(ratios)))
    if len(ratios) < 3:
        print("  not enough turning samples"); continue
    print("  actual rotation   d(heading)/dt : median %+.3f rad/s" % statistics.median(dh_per_s))
    print("  engine yaw rate   (+0xCC)       : median %+.3f rad/s" % statistics.median(yr))
    print("  RATIO actual/reported           : %.2f" % statistics.median(ratios))
    st=[x for x in steer if x==x]
    if st:
        print("  applied steer (comparability)   : median %+.3f  <- must MATCH across rates" % statistics.median(st))
print("\nratio ~1 at both rates  -> orientation is dt-correct")
print("ratio ~1 at 20 and ~3 at 60 -> orientation advanced per FRAME (the rotation bug)")
