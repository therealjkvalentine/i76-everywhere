#!/usr/bin/env python3
"""Dashboard texture processing study: for each chosen instrument tile, produce
four native-resolution variants and a zoomed comparison strip, plus standalone
PNGs (native + ESRGAN 4x full-size) for manual experimentation.

Variants (all at the engine-native tile size - that's the hard ceiling):
  1. ORIGINAL      - decoded straight from the game
  2. ESRGAN        - what shipped: Real-ESRGAN x4plus-anime 4x, Lanczos back to native
  3. SHARPENED     - ESRGAN result + unsharp mask (recovers edge crispness)
  4. BLENDED       - 50/50 linear blend of ORIGINAL and ESRGAN (restores the
                     original's exact gradients + fine detail while keeping the cleanup)

Usage: python dash_variants.py ASSETS ESRGAN_EXE OUT_DIR
"""
import os, sys, subprocess, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i76img
from PIL import Image, ImageFilter, ImageChops, ImageDraw

assets, esrgan, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
pal = i76img.read_act(os.path.join(assets, "t01.act"))
tmp = tempfile.mkdtemp(prefix="i76dash")

# (label, pak, preferred tile substring) - pick the largest tile if substring not found
SUBJECTS = [
    ("radar",   "gsradar6", "GSRPL"),   # louvered hazard-stripe housing face
    ("weapons", "weapncm6", "GTUTF"),   # gatling weapon-pod barrel (gradient showcase)
    ("status",  "gsheatm6", "GSHPL"),   # systems/heat gauge housing face
]

def pick_tile(pak, want):
    tiles = i76img.decode_pak(os.path.join(assets, pak + ".pak"), pal, assets)
    for name, w, h, rgba in tiles:
        if want.lower() in name.lower():
            return name, w, h, rgba
    return max(tiles, key=lambda t: t[1] * t[2])  # largest by area

def esrgan_4x(im_rgb):
    fin, fout = os.path.join(tmp, "i.png"), os.path.join(tmp, "o.png")
    im_rgb.save(fin)
    subprocess.run([esrgan, "-i", fin, "-o", fout, "-n", "realesrgan-x4plus-anime"],
                   check=True, capture_output=True)
    return Image.open(fout).convert("RGB")

def variants(name, w, h, rgba):
    orig = Image.frombytes("RGBA", (w, h), bytes(rgba))
    alpha = orig.getchannel("A")
    orig_rgb = orig.convert("RGB")

    big = esrgan_4x(orig_rgb)                                  # 4x, full detail
    esrgan_native = big.resize((w, h), Image.LANCZOS)          # shipped variant

    # sharpen: unsharp mask on the ESRGAN native result
    sharp = esrgan_native.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=0))

    # blend: 50/50 linear mix of original and ESRGAN native
    blend = Image.blend(orig_rgb, esrgan_native, 0.5)

    def rgba_of(rgb):  # restore original alpha exactly
        return Image.merge("RGBA", (*rgb.split(), alpha))

    return {
        "1_original": orig,
        "2_esrgan":   rgba_of(esrgan_native),
        "3_sharpen":  rgba_of(sharp),
        "4_blend":    rgba_of(blend),
    }, big, orig  # also return 4x for standalone export

VLABELS = ["1_original", "2_esrgan", "3_sharpen", "4_blend"]
NICE = {"1_original": "ORIGINAL", "2_esrgan": "ESRGAN (shipped)",
        "3_sharpen": "SHARPENED", "4_blend": "BLEND 50/50"}
ZOOM = 7
rows = []
for label, pak, want in SUBJECTS:
    name, w, h, rgba = pick_tile(pak, want)
    vs, big, orig = variants(name, w, h, rgba)
    # standalone PNGs for manual experimentation
    orig.save(os.path.join(out, f"{label}_{name}_original_{w}x{h}.png"))
    big.save(os.path.join(out, f"{label}_{name}_esrgan4x_{big.width}x{big.height}.png"))
    for v in VLABELS:
        vs[v].save(os.path.join(out, f"{label}_{name}_{v}.png"))
    # comparison row: 4 variants zoomed, labeled
    cellw, cellh = w * ZOOM, h * ZOOM
    pad, labelh, rowlabelw = 10, 22, 130
    row = Image.new("RGBA", (rowlabelw + 4 * (cellw + pad) + pad, cellh + labelh + pad),
                    (20, 20, 24, 255))
    d = ImageDraw.Draw(row)
    d.text((8, cellh // 2), f"{label}\n{name}\n{w}x{h}", fill=(230, 210, 120, 255))
    x = rowlabelw
    for v in VLABELS:
        cell = vs[v].convert("RGB").resize((cellw, cellh), Image.NEAREST)
        row.paste(cell, (x, labelh))
        d.text((x + 2, 4), NICE[v], fill=(200, 200, 210, 255))
        x += cellw + pad
    rows.append(row)

W = max(r.width for r in rows)
H = sum(r.height + 4 for r in rows)
sheet = Image.new("RGBA", (W, H), (12, 12, 14, 255))
y = 0
for r in rows:
    sheet.alpha_composite(r, (0, y)); y += r.height + 4
sheet.convert("RGB").save(os.path.join(out, "COMPARISON_zoomed.png"))
print("wrote COMPARISON_zoomed.png + standalone PNGs to", out)
