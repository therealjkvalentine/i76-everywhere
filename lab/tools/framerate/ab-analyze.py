#!/usr/bin/env python3
# ab-analyze.py — score the poke-ab.ps1 output.
# net = diff(B,C) - diff(A,B) : ambient motion cancels, the render-consumed copy stands out.
import glob, os, sys
from PIL import Image, ImageChops

d = sys.argv[1] if len(sys.argv) > 1 else '.'

def gray(p):
    return Image.open(p).convert('L')

def crop3d(img):
    # Absolute box: the center of the game 3D viewport (game window bbox was
    # (881,196)-(2558,1243)). Excludes radar (top-left), mirror (right), HUD (top),
    # dashboard (bottom) - so only genuine world geometry is compared.
    return img.crop((1150, 500, 2050, 1000))

def diff(pa, pb):
    a = crop3d(gray(pa)); b = crop3d(gray(pb))
    dd = ImageChops.difference(a, b)
    px = list(dd.getdata()); n = len(px)
    mean = sum(px)/n
    changed = 100.0*sum(1 for v in px if v > 12)/n
    return mean, changed

tags = sorted(set(os.path.basename(f).rsplit('_', 1)[0] for f in glob.glob(os.path.join(d, '*_A.png'))))
print("%-22s %10s %10s %10s   %s" % ("candidate", "ambient", "amb+eff", "NET", "verdict"))
rows = []
for t in tags:
    A = os.path.join(d, t+'_A.png'); B = os.path.join(d, t+'_B.png'); C = os.path.join(d, t+'_C.png')
    if not all(os.path.exists(x) for x in (A, B, C)):
        continue
    amb, _ = diff(A, B)
    tot, _ = diff(B, C)
    net = tot - amb
    rows.append((net, t, amb, tot))

rows.sort(reverse=True)
for net, t, amb, tot in rows:
    verdict = ""
    print("%-22s %10.3f %10.3f %10.3f" % (t, amb, tot, net))

if rows:
    best = rows[0]
    print("\nHighest NET: %s  (net=%.3f)" % (best[1], best[0]))
    if len(rows) > 1:
        ratio = best[0] / (rows[1][0] if abs(rows[1][0]) > 1e-6 else 1e-6)
        print("2nd place: %s (net=%.3f).  top/second = %.2fx" % (rows[1][1], rows[1][0], ratio))
    if best[0] < 1.0:
        print("WARNING: even the top NET is tiny - offset may be too small, or none is render-consumed in this view.")
