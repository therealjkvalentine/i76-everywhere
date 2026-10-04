#!/usr/bin/env python3
"""analyse-drag.py fall20.csv fall60.csv - terrain-free drag measurement.

The coast tests were confounded: a coasting car runs onto different terrain at each frame rate,
so slope contaminates the deceleration. AIRBORNE samples have no such problem - with no ground
contact the only thing acting on HORIZONTAL velocity is drag.

So: select airborne stretches (vy clearly negative and falling, i.e. genuinely off the ground),
and fit d|v_xz|/dt over them. That is air drag, terrain-free.

  per-SECOND equal across frame rates -> drag is dt-scaled (correct)
  per-FRAME  equal across frame rates -> drag applied once per frame (would explain the
                                          5-9% top-speed shortfall at 60 Hz)
"""
import csv, sys, math, statistics

def load(p):
    with open(p) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]

def hspeed(r):
    return math.sqrt(r['vx']*r['vx'] + r['vz']*r['vz'])

def airborne_runs(rows, min_frames=6):
    """contiguous stretches where the car is clearly off the ground and falling"""
    runs, cur = [], []
    for r in rows:
        if r['vy'] < -2.0:          # falling hard enough that it cannot be on the ground
            cur.append(r)
        else:
            if len(cur) >= min_frames: runs.append(cur)
            cur = []
    if len(cur) >= min_frames: runs.append(cur)
    return runs

for path in sys.argv[1:]:
    rows = load(path)
    span = (rows[-1]['t_ms'] - rows[0]['t_ms']) / 1000.0
    fps = (rows[-1]['frame'] - rows[0]['frame']) / span if span else 0
    runs = airborne_runs(rows)
    print("\n=== %s ===" % path.split('\\')[-1])
    print("  %.1f fps, %d airborne runs (>=6 frames, vy<-2)" % (fps, len(runs)))
    per_s, per_f, samples = [], [], 0
    for run in runs:
        for i in range(1, len(run)):
            dt = (run[i]['t_ms'] - run[i-1]['t_ms']) / 1000.0
            df = run[i]['frame'] - run[i-1]['frame']
            dh = hspeed(run[i]) - hspeed(run[i-1])
            if dt > 0 and df > 0 and abs(dh) < 20:   # ignore impact spikes
                per_s.append(dh / dt); per_f.append(dh / df); samples += 1
    if samples < 3:
        print("  not enough airborne samples"); continue
    print("  %d airborne sample pairs" % samples)
    print("  horizontal drag per SECOND: median %8.4f m/s^2  (mean %8.4f)" % (
        statistics.median(per_s), statistics.mean(per_s)))
    print("  horizontal drag per FRAME : median %8.5f m/s     (mean %8.5f)" % (
        statistics.median(per_f), statistics.mean(per_f)))
print("\nMatching per-SECOND medians => drag is dt-correct and the residual is trajectory")
print("divergence, not physics. Matching per-FRAME medians => drag is the frame-coupled term.")
