#!/usr/bin/env python3
"""analyse-airspin.py airspin20.csv airspin60.csv - is orientation advanced per frame?

While AIRBORNE the only thing changing the car's orientation is its own angular velocity, so:

    rotation achieved per second  ==  |angular velocity|     if orientation is dt-correct
    rotation achieved per second  ==  3x                     if it is advanced once per FRAME

Rotation achieved is measured from the render transform's 3x3 matrix: the angle between the
matrix at consecutive samples (via the trace of R1*R0^T), which is orientation-representation
agnostic and needs no Euler conventions.
"""
import csv, sys, math, statistics

def load(p):
    with open(p) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]

def mat(r):
    return [[r['m0'],r['m1'],r['m2']],[r['m3'],r['m4'],r['m5']],[r['m6'],r['m7'],r['m8']]]

def rel_angle(A, B):
    """angle of the rotation taking A to B = arccos((trace(B*A^T)-1)/2)"""
    t = 0.0
    for i in range(3):
        for k in range(3):
            t += B[i][k]*A[i][k]     # trace(B * A^T)
    c = (t - 1.0) / 2.0
    c = max(-1.0, min(1.0, c))
    return math.acos(c)

for path in sys.argv[1:]:
    rows = load(path)
    if len(rows) < 5:
        print("%s: too few samples" % path); continue
    span = (rows[-1]['t_ms'] - rows[0]['t_ms'])/1000.0
    fps = (rows[-1]['frame'] - rows[0]['frame'])/span if span else 0
    ach, rep, ratios = [], [], []
    for i in range(1, len(rows)):
        a, b = rows[i-1], rows[i]
        dt = (b['t_ms'] - a['t_ms'])/1000.0
        if dt <= 0: continue
        if abs(b['vy']) < 2.0: continue            # airborne only
        w = math.sqrt(b['wx']**2 + b['wy']**2 + b['wz']**2)   # reported angular speed
        if w < 0.05: continue
        d = rel_angle(mat(a), mat(b)) / dt          # achieved angular speed rad/s
        if d > 50: continue                          # sampling alias guard
        ach.append(d); rep.append(w); ratios.append(d / w)
    print("\n=== %s ===" % path.split('\\')[-1])
    print("  %.1f fps, %d airborne rotating samples" % (fps, len(ratios)))
    if len(ratios) < 3:
        print("  not enough airborne rotation captured - needs more airtime"); continue
    print("  achieved rotation  : median %6.3f rad/s" % statistics.median(ach))
    print("  reported |omega|   : median %6.3f rad/s" % statistics.median(rep))
    print("  RATIO achieved/reported : %.2f" % statistics.median(ratios))
print("\n~1 at both rates -> dt-correct.  ~1 at 20 and ~3 at 60 -> orientation advanced PER FRAME.")
