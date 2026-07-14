#!/usr/bin/env python3
"""Blend-ratio ladder + luminance-only sharpen, to pick the right dashboard recipe.
Columns: ORIGINAL | blend 75% orig | blend 50/50 | blend 25% orig | full ESRGAN |
         ESRGAN+lumsharp (color-fringe-free sharpen).
Also renders each at DASHBOARD DISPLAY SIZE (bilinear-stretched ~4x) since that's
how the eye sees them in the cockpit, not at 1:1.
"""
import os, sys, subprocess, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i76img
from PIL import Image, ImageFilter, ImageDraw

assets, esrgan, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
pal = i76img.read_act(os.path.join(assets, "t01.act"))
tmp = tempfile.mkdtemp(prefix="i76ladder")

SUBJECTS = [("radar", "gsradar6", "GSRPL"), ("weapons", "weapncm6", "GTUTF"),
            ("status", "gsheatm6", "GSHPL")]

def pick(pak, want):
    tiles = i76img.decode_pak(os.path.join(assets, pak + ".pak"), pal, assets)
    for t in tiles:
        if want.lower() in t[0].lower():
            return t
    return max(tiles, key=lambda t: t[1] * t[2])

def esrgan_native(rgb, w, h):
    fin, fout = os.path.join(tmp, "i.png"), os.path.join(tmp, "o.png")
    rgb.save(fin)
    subprocess.run([esrgan, "-i", fin, "-o", fout, "-n", "realesrgan-x4plus-anime"],
                   check=True, capture_output=True)
    return Image.open(fout).convert("RGB").resize((w, h), Image.LANCZOS)

def lum_sharpen(rgb):
    # sharpen only the luminance channel -> no color fringing on saturated edges
    ycbcr = rgb.convert("YCbCr")
    y, cb, cr = ycbcr.split()
    y = y.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=1))
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")

DISP = 5  # display-size stretch factor (bilinear, like the cockpit)
cols = ["ORIGINAL", "75% orig", "50/50", "25% orig", "ESRGAN", "ESRGAN+lumSharp"]
rows = []
for label, pak, want in SUBJECTS:
    name, w, h, rgba = pick(pak, want)
    orig = Image.frombytes("RGBA", (w, h), bytes(rgba)).convert("RGB")
    esr = esrgan_native(orig, w, h)
    variants = [
        orig,
        Image.blend(orig, esr, 0.25),
        Image.blend(orig, esr, 0.50),
        Image.blend(orig, esr, 0.75),
        esr,
        lum_sharpen(esr),
    ]
    cellw, cellh = w * DISP, h * DISP
    pad, labelh, rlw = 8, 20, 90
    row = Image.new("RGB", (rlw + len(variants) * (cellw + pad) + pad, cellh + labelh + pad),
                    (20, 20, 24))
    d = ImageDraw.Draw(row)
    d.text((6, cellh // 2), f"{label}\n{w}x{h}", fill=(230, 210, 120))
    x = rlw
    for v, cname in zip(variants, cols):
        row.paste(v.resize((cellw, cellh), Image.BILINEAR), (x, labelh))
        d.text((x + 2, 4), cname, fill=(200, 200, 210))
        x += cellw + pad
    rows.append(row)

W = max(r.width for r in rows); H = sum(r.height + 4 for r in rows)
sheet = Image.new("RGB", (W, H), (12, 12, 14))
y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height + 4
sheet.save(os.path.join(out, "LADDER_displaysize.png"))
print("wrote LADDER_displaysize.png")
