"""analyze-cactus.py - classify cactus-gauntlet approaches and compare hit rates by fps.

Reads every CSV in the given directory (written by cactus-gauntlet.ps1, tagged e.g.
"20fps-run1"). Classification is deliberately done HERE, offline, so the criteria can be
revised against the raw numbers without re-driving anything:

    valid approach : min_dist <= VALID_M   (the car actually got onto the trunk line;
                     wider misses say nothing about collision and are excluded)
    hit            : the speed collapsed near the cactus - v_min < HIT_FRACTION * v_before
    pass-through   : valid approach where speed carried straight through

The 20 fps runs are the calibration: reported behaviour is "collides correctly at 20", so
valid approaches there should classify ~100% hit. If they do not, distrust the classifier,
not the game (suspect-the-instrument).
"""
import csv, glob, os, re, sys
from collections import defaultdict

VALID_M = 1.8        # how close counts as "on the cactus" - saguaro trunk is ~1m wide
HIT_FRACTION = 0.6   # v_min below 60% of approach speed = a real deceleration event

def main(d):
    rows = []
    for f in sorted(glob.glob(os.path.join(d, '*.csv'))):
        with open(f) as fh:
            rows += list(csv.DictReader(fh))
    if not rows:
        print('no CSVs in', d); return
    by_rate = defaultdict(list)
    for r in rows:
        m = re.match(r'(\d+)fps', r['tag'])
        if m:
            by_rate[int(m.group(1))].append(r)
    print(f'{"rate":>6} {"approaches":>10} {"valid":>6} {"hits":>5} {"pass":>5} {"hit rate":>9}   (valid = min_dist <= {VALID_M} m)')
    for rate in sorted(by_rate):
        rs = by_rate[rate]
        valid = hits = 0
        for r in rs:
            md, vb, vm = float(r['min_dist']), float(r['v_before']), float(r['v_min'])
            if md > VALID_M or vb < 5 or vm < 0:
                continue
            valid += 1
            if vm < HIT_FRACTION * vb:
                hits += 1
        rate_s = f'{hits/valid:.0%}' if valid else '-'
        print(f'{rate:>6} {len(rs):>10} {valid:>6} {hits:>5} {valid-hits:>5} {rate_s:>9}')
    print()
    print('raw approaches (near-misses included for context):')
    print(f'{"tag":<14} {"target":<16} {"min_dist":>8} {"v_before":>8} {"v_min":>7} {"fps":>6}  verdict')
    for r in rows:
        md, vb, vm = float(r['min_dist']), float(r['v_before']), float(r['v_min'])
        if md > VALID_M:                verdict = 'MISS (excluded)'
        elif vb < 5 or vm < 0:          verdict = 'no-data'
        elif vm < HIT_FRACTION * vb:    verdict = 'HIT'
        else:                           verdict = 'PASS-THROUGH'
        print(f'{r["tag"]:<14} ({r["target_x"]},{r["target_z"]}) {md:>8.2f} {vb:>8.1f} {vm:>7.1f} {float(r["fps"]):>6.1f}  {verdict}')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
