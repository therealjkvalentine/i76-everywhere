#!/usr/bin/env python3
"""Plumbing-proof: rebuild pirana1m.pak with a magenta marker on every tile,
so one in-game glance confirms ADDON vehicle-texture override renders.
Usage: python make_marker.py ASSETS_DIR OUT_DIR"""
import os, sys, glob, struct, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i76img

assets, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
pal = i76img.read_act(os.path.join(assets, "t01.act"))

# nearest palette entry to magenta, computed once
def nearest(r, g, b):
    return min(range(255), key=lambda i: (pal[i][0]-r)**2 + (pal[i][1]-g)**2 + (pal[i][2]-b)**2)
MAGENTA = nearest(255, 0, 255)
print("magenta palette index:", MAGENTA, pal[MAGENTA])

# decode every tile of pirana1m.pak, stamp a magenta X + border, re-encode
pak_path = os.path.join(assets, "pirana1m.pak")
tiles = i76img.decode_pak(pak_path, pal, assets)
codebook = ({}, [])
parts, manifest = [], []
off = 0
mr, mg, mb = pal[MAGENTA]
for name, w, h, rgba in tiles:
    buf = bytearray(rgba)
    def put(x, y):
        o = (y * w + x) * 4
        if buf[o+3]:  # keep transparency
            buf[o:o+3] = bytes((mr, mg, mb))
    for x in range(w):        # thick border
        for t in range(2):
            put(x, t); put(x, h-1-t)
    for y in range(h):
        for t in range(2):
            put(t, y); put(w-1-t, y)
    for i in range(min(w, h)):  # X
        put(i, i); put(w-1-i, i)
    idx = i76img.quantize_to_palette(bytes(buf), w, h, pal)
    v = i76img.encode_vqm(idx, w, h, "HDCAR1.CBK", codebook)
    parts.append(v); manifest.append((name, off, len(v))); off += len(v)

base = os.path.join(outdir, "pirana1m")
open(base + ".pak", "wb").write(b"".join(parts))
with open(base + ".pix", "w", newline="") as f:
    f.write(f"{len(manifest)}\r\n")
    for name, o, l in manifest:
        f.write(f"{name.upper()} {o} {l}\r\n")
with open(os.path.join(outdir, "hdcar1.cbk"), "wb") as f:
    f.write(struct.pack("<I", len(codebook[1])) + b"".join(codebook[1]))
print(f"marker pak: {len(manifest)} tiles, {len(codebook[1])} codebook blocks")
