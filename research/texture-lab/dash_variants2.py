#!/usr/bin/env python3
"""Dashboard variant study v2 - the REAL cockpit HUD panels:
  radar   = zradf000 (VQM pak, frame ZRADF000)  - green CRT + housing
  weapons = zwpe     (loose .map)                - ammo readout bars
  status  = zsy_     (loose .map)                - Mr Damage vehicle-status panel

Variants (native res = engine ceiling):
  1 ORIGINAL
  2 ESRGAN                 - x4plus-anime 4x -> Lanczos to native (shipped)
  3 SHARPEN 40%            - ESRGAN + LUMINANCE-only unsharp at ~40% intensity
                            (luminance-only => no blue/color fringing)
  4 BLEND 33/33/33         - equal mix of ORIGINAL + ESRGAN + SHARPEN

Panels render MIRRORED in the archive (engine flips them); shown as-stored.
Usage: python dash_variants2.py ASSETS ESRGAN_EXE OUT_DIR [sharpen_percent]
"""
import os, sys, subprocess, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i76img
from PIL import Image, ImageFilter, ImageChops, ImageDraw

assets, esrgan, out = sys.argv[1:4]
SHARP_PCT = int(sys.argv[4]) if len(sys.argv) > 4 else 55   # ~40% of the old 140%
os.makedirs(out, exist_ok=True)
pal = i76img.read_act(os.path.join(assets, "t01.act"))
tmp = tempfile.mkdtemp(prefix="i76dv2")

def load_panel(name):
    base = os.path.join(assets, name)
    if os.path.exists(base + ".map"):
        w, h, rgba = i76img.decode_map(open(base + ".map", "rb").read(), pal)
    elif os.path.exists(base + ".pix"):
        n, w, h, rgba = i76img.decode_pak(base + ".pak", pal, assets)[0]
    else:
        raise SystemExit("missing " + name)
    return w, h, Image.frombytes("RGBA", (w, h), bytes(rgba))

SUBJECTS = [("radar", "zradf000"), ("weapons", "zwpe"), ("status", "zsy_")]

def esrgan_4x(rgb):
    fin, fout = os.path.join(tmp, "i.png"), os.path.join(tmp, "o.png")
    rgb.save(fin)
    subprocess.run([esrgan, "-i", fin, "-o", fout, "-n", "realesrgan-x4plus-anime"],
                   check=True, capture_output=True)
    return Image.open(fout).convert("RGB")

def lum_unsharp(rgb, percent):
    y, cb, cr = rgb.convert("YCbCr").split()
    y = y.filter(ImageFilter.UnsharpMask(radius=1.0, percent=percent, threshold=1))
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")

def blend3(a, b, c):  # equal 1/3 each
    ab = Image.blend(a, b, 0.5)          # (a+b)/2
    return Image.blend(ab, c, 1.0 / 3)   # (2*(a+b)/2 + c)/3 = (a+b+c)/3

VLAB = ["1_original", "2_esrgan", f"3_sharpen{SHARP_PCT}", "4_blend333"]
NICE = {VLAB[0]: "ORIGINAL", VLAB[1]: "ESRGAN (shipped)",
        VLAB[2]: f"SHARPEN {SHARP_PCT}% (lum)", VLAB[3]: "BLEND 33/33/33"}
ZOOM = 3
rows = []
for label, tex in SUBJECTS:
    w, h, orig = load_panel(tex)
    alpha = orig.getchannel("A"); orig_rgb = orig.convert("RGB")
    big = esrgan_4x(orig_rgb)
    esr = big.resize((w, h), Image.LANCZOS)
    sharp = lum_unsharp(esr, SHARP_PCT)
    blend = blend3(orig_rgb, esr, sharp)
    def rgba(x): return Image.merge("RGBA", (*x.split(), alpha))
    vs = {VLAB[0]: orig, VLAB[1]: rgba(esr), VLAB[2]: rgba(sharp), VLAB[3]: rgba(blend)}
    # standalone exports
    orig.save(os.path.join(out, f"{label}_{tex}_original_{w}x{h}.png"))
    big.save(os.path.join(out, f"{label}_{tex}_esrgan4x_{big.width}x{big.height}.png"))
    for v in VLAB:
        vs[v].save(os.path.join(out, f"{label}_{tex}_{v}.png"))
    cw, ch = w * ZOOM, h * ZOOM
    pad, lh, rlw = 8, 20, 110
    row = Image.new("RGBA", (rlw + 4 * (cw + pad) + pad, ch + lh + pad), (20, 20, 24, 255))
    d = ImageDraw.Draw(row)
    d.text((6, ch // 2), f"{label}\n{tex}\n{w}x{h}", fill=(235, 210, 110, 255))
    x = rlw
    for v in VLAB:
        row.paste(vs[v].convert("RGB").resize((cw, ch), Image.NEAREST), (x, lh))
        d.text((x + 2, 4), NICE[v], fill=(205, 205, 215, 255)); x += cw + pad
    rows.append(row)

W = max(r.width for r in rows); H = sum(r.height + 4 for r in rows)
sheet = Image.new("RGBA", (W, H), (12, 12, 14, 255))
y = 0
for r in rows:
    sheet.alpha_composite(r, (0, y)); y += r.height + 4
sheet.convert("RGB").save(os.path.join(out, "COMPARISON2.png"))
print(f"wrote COMPARISON2.png (sharpen {SHARP_PCT}%) + standalone PNGs")
