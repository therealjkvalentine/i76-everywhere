#!/usr/bin/env python3
"""map-cursor.py <calibdir> - fit the OS-cursor -> drawn-game-cursor mapping.

Consumes what capture-cursor-probes.ps1 photographed. For each probe frame, diff against the
reference frame: the changed pixels form TWO blobs - the reference cursor (same place in every
probe) and this probe's cursor. The reference blob is identified as the one whose position
recurs across probes; the other blob's top-left is the drawn cursor for that probe.

Then least-squares fit screen = a*OS + b per axis, and report residuals so you can see whether
a single affine map is actually good enough.
"""
import csv, os, sys
from PIL import Image, ImageChops

d = sys.argv[1] if len(sys.argv) > 1 else '.'
ref = Image.open(os.path.join(d, 'ref.png')).convert('L')
probes = list(csv.DictReader(open(os.path.join(d, 'probes.csv'))))

def blobs_of(img, step=2, gap=90, minpts=4):
    """coarse changed-pixel blobs vs ref: [(minx,miny,count,cx,cy)]"""
    diff = ImageChops.difference(ref, img)
    w, h = diff.size
    px = diff.load()
    found = []
    for y in range(0, h, step):
        for x in range(0, w, step):
            if px[x, y] > 40:
                placed = False
                for b in found:
                    if abs(x - b['cx']) <= gap and abs(y - b['cy']) <= gap:
                        b['n'] += 1
                        b['minx'] = min(b['minx'], x); b['miny'] = min(b['miny'], y)
                        b['cx'] = (b['cx'] * (b['n'] - 1) + x) // b['n']
                        b['cy'] = (b['cy'] * (b['n'] - 1) + y) // b['n']
                        placed = True
                        break
                if not placed:
                    found.append({'minx': x, 'miny': y, 'cx': x, 'cy': y, 'n': 1})
    return [b for b in found if b['n'] >= minpts]

# pass 1: collect blobs per probe, find the recurring (reference) blob
per = []
for r in probes:
    p = os.path.join(d, "p%03d.png" % int(r['idx']))
    if not os.path.exists(p):
        continue
    bs = blobs_of(Image.open(p).convert('L'))
    per.append((int(r['osx']), int(r['osy']), bs))

counts = {}
for _, _, bs in per:
    for b in bs:
        key = (b['cx'] // 60, b['cy'] // 60)
        counts[key] = counts.get(key, 0) + 1
refkey = max(counts, key=counts.get) if counts else None
print("frames: %d ; reference blob cell %s seen in %d of them" % (len(per), refkey, counts.get(refkey, 0)))

pairs = []
for osx, osy, bs in per:
    cand = [b for b in bs if (b['cx'] // 60, b['cy'] // 60) != refkey]
    if not cand:
        continue
    c = max(cand, key=lambda b: b['n'])
    pairs.append((osx, osy, c['minx'], c['miny']))
    print("  OS(%4d,%4d) -> screen(%5d,%5d)" % (osx, osy, c['minx'], c['miny']))

if len(pairs) < 3:
    print("only %d usable pairs" % len(pairs)); sys.exit(1)

def fit(xs, ys):
    n = len(xs); sx = sum(xs); sy = sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    a = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    return a, (sy - a * sx) / n

ax, bx = fit([p[0] for p in pairs], [p[2] for p in pairs])
ay, by = fit([p[1] for p in pairs], [p[3] for p in pairs])
rx = max(abs(ax * p[0] + bx - p[2]) for p in pairs)
ry = max(abs(ay * p[1] + by - p[3]) for p in pairs)
print("\nfitted %d points" % len(pairs))
print("  screen_x = %.4f * OS_x + %.1f   (max residual %.1f px)" % (ax, bx, rx))
print("  screen_y = %.4f * OS_y + %.1f   (max residual %.1f px)" % (ay, by, ry))
print("\npaste into autotest/lib/maplib.ps1:")
print("  $script:MAP_AX = %.4f; $script:MAP_BX = %.1f" % (ax, bx))
print("  $script:MAP_AY = %.4f; $script:MAP_BY = %.1f" % (ay, by))
