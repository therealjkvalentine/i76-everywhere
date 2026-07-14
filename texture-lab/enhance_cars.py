#!/usr/bin/env python3
"""Enhanced same-res car texture pipeline (the engine ceiling is original dimensions):
decode pak -> Real-ESRGAN 4x (anime model, best for flat game art) -> Lanczos back to
original size -> original alpha mask re-applied -> quantize to level palette -> new pak
with a private codebook -> ready for ADDON/.

Usage: python enhance_cars.py ASSETS_DIR ESRGAN_EXE PAKNAME CBKNAME OUT_DIR
e.g.:  python enhance_cars.py C:\\Games\\_tools\\i76-assets ^
         C:\\Games\\_tools\\realesrgan\\realesrgan-ncnn-vulkan.exe pirana1m HDCAR1.CBK build\\final
"""
import os, sys, struct, subprocess, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i76img
from PIL import Image

assets, esrgan, pakname, cbkname, outdir = sys.argv[1:6]
os.makedirs(outdir, exist_ok=True)
pal = i76img.read_act(os.path.join(assets, "t01.act"))

tiles = i76img.decode_pak(os.path.join(assets, pakname + ".pak"), pal, assets)
tmp = tempfile.mkdtemp(prefix="i76esr")

codebook = ({}, [])
parts, manifest = [], []
off = 0
for name, w, h, rgba in tiles:
    im = Image.frombytes("RGBA", (w, h), bytes(rgba))
    alpha = im.getchannel("A")
    src = os.path.join(tmp, "in.png")
    dst = os.path.join(tmp, "out.png")
    im.convert("RGB").save(src)
    subprocess.run([esrgan, "-i", src, "-o", dst, "-n", "realesrgan-x4plus-anime"],
                   check=True, capture_output=True)
    big = Image.open(dst).convert("RGB")
    small = big.resize((w, h), Image.LANCZOS)
    out = Image.merge("RGBA", (*small.split(), alpha))  # original alpha, exactly
    idx = i76img.quantize_to_palette(out.tobytes(), w, h, pal)
    v = i76img.encode_vqm(idx, w, h, cbkname, codebook)
    parts.append(v); manifest.append((name, off, len(v))); off += len(v)
    print(f"  {name} {w}x{h} ok")

base = os.path.join(outdir, pakname)
open(base + ".pak", "wb").write(b"".join(parts))
with open(base + ".pix", "w", newline="") as f:
    f.write(f"{len(manifest)}\r\n")
    for name, o, l in manifest:
        f.write(f"{name.upper()} {o} {l}\r\n")
with open(os.path.join(outdir, cbkname.lower()), "wb") as f:
    f.write(struct.pack("<I", len(codebook[1])) + b"".join(codebook[1]))
print(f"{pakname}: {len(manifest)} tiles enhanced, {len(codebook[1])} codebook blocks -> {outdir}")
