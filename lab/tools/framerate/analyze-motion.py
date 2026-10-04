"""analyze-motion.py - body-motion metrics per (rate, surface) from body-motion.ps1 CSVs.

Per-second physical rates so sampling divides out; deltas only across samples where the game
frame advanced. Reports: mean speed, mean |roll rate|, mean |pitch rate| (deg/s), height
jitter (m/s RMS), and roll zero-crossing frequency (Hz) - the felt 'busyness' of the body.
"""
import csv, glob, math, os, re, sys
from collections import defaultdict

def wrap(d):
    while d > 180: d -= 360
    while d < -180: d += 360
    return d

def main(d):
    groups = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(d, '*.csv'))):
        with open(f) as fh:
            for r in csv.DictReader(fh):
                m = re.match(r'(\d+)fps', r['tag'])
                if m:
                    groups[(int(m.group(1)), r['phase'])].append(r)
    print(f'{"rate":>5} {"surface":>8} {"n":>6} {"v_mean":>7} {"|droll|/s":>10} {"|dpitch|/s":>11} {"dy_rms":>8} {"roll_xing_hz":>13}')
    for (rate, phase), rs in sorted(groups.items()):
        rolls, pitches, dys, ts = [], [], [], []
        speeds = []
        prev = None
        for r in rs:
            t = float(r['t_ms'])/1000.0; fr = int(r['frame'])
            roll, pitch, y, v = float(r['roll']), float(r['pitch']), float(r['eyey']), float(r['speed'])
            speeds.append(v)
            if prev is not None and fr > prev[1] and 0 < (t - prev[0]) < 0.5:
                dt = t - prev[0]
                rolls.append(abs(wrap(roll - prev[2]))/dt)
                pitches.append(abs(wrap(pitch - prev[3]))/dt)
                dys.append(((y - prev[4])/dt)**2)
                ts.append((t, wrap(roll - prev[2])))
            prev = (t, fr, roll, pitch, y)
        if not rolls: continue
        # roll direction changes per second = oscillation busyness
        xings = sum(1 for i in range(1, len(ts)) if ts[i][1]*ts[i-1][1] < 0)
        dur = ts[-1][0] - ts[0][0] if len(ts) > 1 else 1
        print(f'{rate:>5} {phase:>8} {len(rs):>6} {sum(speeds)/len(speeds):>7.1f} '
              f'{sum(rolls)/len(rolls):>10.2f} {sum(pitches)/len(pitches):>11.2f} '
              f'{math.sqrt(sum(dys)/len(dys)):>8.2f} {xings/dur:>13.1f}')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
