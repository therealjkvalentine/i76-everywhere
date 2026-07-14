#!/usr/bin/env python3
"""Enhanced same-res M16 (hardware/-glide) car textures:
decode M16 -> Real-ESRGAN 4x (anime model) -> Lanczos back to original size ->
original alpha (0xFF) preserved -> re-encode M16 with fresh per-tile RGB565 palette.
Per-tile palettes mean NO level-palette quantization - full color freedom.

Usage: python enhance_cars_m16.py ASSETS_DIR ESRGAN_EXE PAKNAME OUT_DIR
"""
import os, sys, struct, subprocess, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i76img
from PIL import Image

assets, esrgan, pakname, outdir = sys.argv[1:5]
os.makedirs(outdir, exist_ok=True)

src = open(os.path.join(assets, pakname + ".pak"), "rb").read()
lines = open(os.path.join(assets, pakname + ".pix")).read().split()
tmp = tempfile.mkdtemp(prefix="i76m16")

it = iter(lines[1:])
parts, manifest, off = [], [], 0
for name in it:
    o, ln = int(next(it)), int(next(it))
    w, h, flags, rgba = i76img.decode_m16(src[o:o + ln])
    im = Image.frombytes("RGBA", (w, h), bytes(rgba))
    alpha = im.getchannel("A")
    fin, fout = os.path.join(tmp, "in.png"), os.path.join(tmp, "out.png")
    im.convert("RGB").save(fin)
    subprocess.run([esrgan, "-i", fin, "-o", fout, "-n", "realesrgan-x4plus-anime"],
                   check=True, capture_output=True)
    small = Image.open(fout).convert("RGB").resize((w, h), Image.LANCZOS)
    out = Image.merge("RGBA", (*small.split(), alpha))
    v = i76img.encode_m16(out.tobytes(), w, h, flags)
    parts.append(v); manifest.append((name, off, len(v))); off += len(v)
    print(f"  {name} {w}x{h} ok")

base = os.path.join(outdir, pakname)
open(base + ".pak", "wb").write(b"".join(parts))
with open(base + ".pix", "w", newline="") as f:
    f.write(f"{len(manifest)}\r\n")
    for n, o, l in manifest:
        f.write(f"{n.upper()} {o} {l}\r\n")
print(f"{pakname}: {len(manifest)} M16 tiles enhanced -> {outdir}")
