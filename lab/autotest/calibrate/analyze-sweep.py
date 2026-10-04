#!/usr/bin/env python3
# analyze-sweep.py <sweepdir> - find which cursor point highlights each menu item.
# Measures mean brightness of each item's text box across all grid screenshots; the
# brightest frame per item is the cursor position hovering it.
import csv, os, sys
from PIL import Image

d = sys.argv[1] if len(sys.argv) > 1 else '.'
# menu-item text boxes in 3440x1440 screen coords (from the menu screenshot)
ITEMS = {
    'OPTIONS': (670, 86, 990, 170),
    'EXIT':    (2560, 86, 2770, 170),
    'TRIP':    (1256, 900, 1500, 1010),
    'MELEE':   (2030, 900, 2360, 1010),
}
def brightness(img, box):
    c = img.crop(box).convert('L')
    px = list(c.getdata())
    return sum(px) / len(px)

rows = list(csv.DictReader(open(os.path.join(d, 'grid.csv'))))
data = {k: [] for k in ITEMS}
for r in rows:
    p = os.path.join(d, "g%03d.png" % int(r['idx']))
    if not os.path.exists(p):
        continue
    img = Image.open(p)
    for k, box in ITEMS.items():
        data[k].append((brightness(img, box), int(r['cx']), int(r['cy'])))

for k in ITEMS:
    vals = sorted(data[k], reverse=True)
    if not vals:
        continue
    base = sorted(v[0] for v in data[k])[len(data[k])//2]   # median = unhighlighted baseline
    top = vals[0]
    delta = top[0] - base
    flag = "  <== clear highlight" if delta > 8 else ("  (weak)" if delta > 3 else "  (no highlight found)")
    print("%-8s brightest=%.1f at cursor(%d,%d)  baseline=%.1f  delta=%.1f%s" % (k, top[0], top[1], top[2], base, delta, flag))
    # show top 3 for context
    for b, x, y in vals[:3]:
        print("         %.1f @ (%d,%d)" % (b, x, y))
