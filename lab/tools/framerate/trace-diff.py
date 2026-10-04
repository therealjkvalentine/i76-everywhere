#!/usr/bin/env python3
"""trace-diff.py ref.csv test.csv - compare two physics traces at matched elapsed time.

Physics are equivalent if, at the same WALL-CLOCK time, the car is in the same place moving at
the same speed - regardless of how many frames it took to get there. Reports per-checkpoint
error and a verdict. Fall speed (vy) is called out separately: it is the canonical I'76
frame-rate breakage.
"""
import csv, sys, math

def load(p):
    with open(p) as f:
        return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]

def at_time(rows, t):
    """linear interpolation of the trace at wall-clock t (ms)"""
    prev = None
    for r in rows:
        if r['t_ms'] >= t:
            if prev is None or r['t_ms'] == prev['t_ms']:
                return r
            f = (t - prev['t_ms']) / (r['t_ms'] - prev['t_ms'])
            return {k: prev[k] + (r[k] - prev[k]) * f for k in r}
        prev = r
    return prev

if len(sys.argv) < 3:
    print("usage: trace-diff.py ref.csv test.csv"); sys.exit(1)
ref, test = load(sys.argv[1]), load(sys.argv[2])
if not ref or not test:
    print("empty trace"); sys.exit(1)

end = min(ref[-1]['t_ms'], test[-1]['t_ms'])
checkpoints = [t for t in range(1000, int(end) + 1, 1000)]   # once a second
print("checkpoints every 1000 ms, up to %.0f ms" % end)
print("%6s %10s %10s %10s %10s %10s" % ("t(s)", "dist_err", "speed_err", "vy_ref", "vy_test", "vy_err"))

# Compare motion RELATIVE TO EACH RUN'S OWN START. Melee spawn points differ between runs,
# so absolute positions are not comparable - what must match is how far the car has travelled
# by a given wall-clock time.
r0, t0 = ref[0], test[0]
def rel(row, origin):
    return (row['x']-origin['x'], row['y']-origin['y'], row['z']-origin['z'])

worst_pos = worst_spd = worst_vy = 0.0
for t in checkpoints:
    a, b = at_time(ref, t), at_time(test, t)
    if not a or not b: continue
    ax, ay, az = rel(a, r0); bx, by, bz = rel(b, t0)
    d = math.sqrt((ax-bx)**2 + (ay-by)**2 + (az-bz)**2)
    s = abs(a['speed'] - b['speed'])
    vy = abs(a['vy'] - b['vy'])
    worst_pos = max(worst_pos, d); worst_spd = max(worst_spd, s); worst_vy = max(worst_vy, vy)
    print("%6.0f %10.3f %10.3f %10.3f %10.3f %10.3f" % (t/1000.0, d, s, a['vy'], b['vy'], vy))

# frame rates actually achieved
def fps(rows):
    dt = (rows[-1]['t_ms'] - rows[0]['t_ms']) / 1000.0
    df = rows[-1]['frame'] - rows[0]['frame']
    return df / dt if dt > 0 else 0
print("\nref  ~%.1f frames/s     test ~%.1f frames/s" % (fps(ref), fps(test)))
print("worst position error : %.3f m" % worst_pos)
print("worst speed error    : %.3f m/s" % worst_spd)
print("worst FALL-SPEED err : %.3f m/s   <-- the canonical I'76 breakage" % worst_vy)

# tolerances: same trajectory within a car length, speed within 1 m/s, fall speed within 0.5
ok = worst_pos < 5.0 and worst_spd < 1.0 and worst_vy < 0.5
print("\nVERDICT: %s" % ("PHYSICS EQUIVALENT" if ok else "DIVERGED - physics are NOT frame-rate independent"))
sys.exit(0 if ok else 2)
