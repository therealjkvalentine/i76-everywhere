"""make-crops.py - cut the same rectangles out of every variant's screenshot and lay them side by side.

    python make-crops.py <shots dir> [crops.json]

<shots dir> holds one full-frame PNG per variant (capture-frame.ps1; all the same size). crops.json (default: the
one beside this script) lists rectangles in frame pixels: {"name": [x, y, w, h], ...}. Pick them ONCE on the 1x
shot and reuse them for every variant. Output, in <shots dir>\\crops:
    <crop>__<variant>.png   the raw crop (no rescale)
    <crop>__sheet.png       all variants of that crop in a row, enlarged 4x with nearest-neighbour (no smoothing
                            added by the comparison itself), labelled, in file-name order
It also prints, per crop and variant, the mean absolute luma step between horizontally adjacent pixels: a crude
edge-energy number (higher = sharper or more aliased; compare it with the eye, never instead of it).
"""
import json, os, sys
from PIL import Image, ImageDraw

shots = sys.argv[1]
crops = json.load(open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "crops.json")))
crops = {k: v for k, v in crops.items() if not k.startswith("_")}
files = sorted(f for f in os.listdir(shots) if f.lower().endswith(".png"))
if not files:
    sys.exit("no PNGs in " + shots)
out = os.path.join(shots, "crops"); os.makedirs(out, exist_ok=True)
sizes = {f: Image.open(os.path.join(shots, f)).size for f in files}
if len(set(sizes.values())) != 1:
    print("WARNING: the shots are not all the same size, so one rectangle is not the same place in each:", sizes)
Z = 4
for name, (x, y, w, h) in crops.items():
    sheet = Image.new("RGB", (len(files) * (w * Z + 8) + 8, h * Z + 28), (32, 32, 32))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        v = os.path.splitext(f)[0]
        c = Image.open(os.path.join(shots, f)).convert("RGB").crop((x, y, x + w, y + h))
        c.save(os.path.join(out, "%s__%s.png" % (name, v)))
        px = 8 + i * (w * Z + 8)
        sheet.paste(c.resize((w * Z, h * Z), Image.NEAREST), (px, 22))
        d.text((px, 5), v, fill=(255, 255, 255))
        g = c.convert("L"); p = g.load()
        e = sum(abs(p[i2 + 1, j] - p[i2, j]) for j in range(h) for i2 in range(w - 1)) / float(max(1, h * (w - 1)))
        print("%-16s %-22s edge energy %.2f" % (name, v, e))
    sheet.save(os.path.join(out, "%s__sheet.png" % name))
print("wrote", out)
