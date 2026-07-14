#!/usr/bin/env python3
"""Phase 3: rebuild every pak/loose-file from the manifest.

Per tile, the final native-resolution pixels are a BLEND of three layers (the
recipe James dialled in with the dashboard tuner, applied game-wide):
    BLEND_ORIG   * original           (faithful detail: radar rings, text, dither)
  + BLEND_ESRGAN * esrgan_downscaled  (Real-ESRGAN x4 -> Lanczos to native: cleanup)
  + BLEND_SHARP  * sharpened          (esrgan + luminance-only unsharp: crisp edges,
                                       no colour fringing)
The sharpen is a LUMINANCE box-blur unsharp mask - byte-for-byte the same math the
HTML tuner runs (build_tuner.py lumSharpen), so the game-wide bake == what James
approved in the tuner. Luminance-only => saturated edges (hazard stripes, red bars)
don't blue-fringe. All at native w/h - the engine's hard ceiling. If STAGING_DIR is
omitted the script falls back to pure-ESRGAN (the old behaviour).

VQM re-encode: quantizes to t01.act + a fresh PRIVATE codebook per pak.
M16 re-encode: fresh per-tile RGB565 palette (no quantization loss).
MAP re-encode: quantizes to t01.act, output is a plain .map.

Usage: python reencode_all.py MANIFEST.json ENHANCED_DIR ASSETS_DIR OUT_DIR [STAGING_DIR]
"""
import os, sys, json, struct, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i76img
from PIL import Image, ImageFilter
import numpy as np

manifest_path, enhanced_dir, assets, outdir = sys.argv[1:5]
staging_dir = sys.argv[5] if len(sys.argv) > 5 else None   # enables the blend
os.makedirs(outdir, exist_ok=True)
manifest = json.load(open(manifest_path))
pal = i76img.read_act(os.path.join(assets, "t01.act"))
t0 = time.time()

# --- the recipe (James, 2026-07-10, dialled in with build_tuner.py) ---
BLEND_ORIG, BLEND_ESRGAN, BLEND_SHARP = 0.47, 0.31, 0.22
SHARP_AMOUNT, SHARP_RADIUS = 116, 0.8   # tuner units: amount %, radius (rounds to box r)

def _load(dir_, staged, w, h, resize):
    path = os.path.join(dir_, staged)
    if not os.path.exists(path):
        path = os.path.join(dir_, staged.replace(".png", "_out.png"))
    im = Image.open(path)
    if resize and im.size != (w, h):
        im = im.resize((w, h), Image.LANCZOS)   # "HQ" downscale (tuner uses canvas-HQ)
    return im

def _box_blur(Y, r):
    """Separable box blur with edge-clamped sample count - matches the tuner's JS
    (averages only in-bounds samples in a (2r+1) window)."""
    H, W = Y.shape
    cs = np.concatenate([np.zeros((H, 1), np.float32), np.cumsum(Y, axis=1)], axis=1)
    x = np.arange(W); lo = np.clip(x - r, 0, W); hi = np.clip(x + r + 1, 0, W)
    Yh = (cs[:, hi] - cs[:, lo]) / (hi - lo).astype(np.float32)[None, :]
    cs2 = np.concatenate([np.zeros((1, W), np.float32), np.cumsum(Yh, axis=0)], axis=0)
    y = np.arange(H); lo2 = np.clip(y - r, 0, H); hi2 = np.clip(y + r + 1, 0, H)
    return (cs2[hi2, :] - cs2[lo2, :]) / (hi2 - lo2).astype(np.float32)[:, None]

def _tuner_sharpen(arr):
    """Luminance box-blur unsharp on an RGB float array - the tuner's exact lumSharpen:
    delta = (amount/100)*(Y - boxblur(Y)); add delta to every channel (hue-preserving)."""
    Y = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    r = max(1, round(SHARP_RADIUS))
    delta = (SHARP_AMOUNT / 100.0) * (Y - _box_blur(Y, r))
    return arr + delta[..., None]

_cache = {}
def enhanced_rgba(staged_name, w, h):
    """Final native RGBA for a tile: 47/31/22 blend if staging available, else pure ESRGAN."""
    key = (staged_name, w, h)
    out = _cache.get(key)
    if out is not None:
        return out
    esr = _load(enhanced_dir, staged_name, w, h, resize=True).convert("RGB")
    if staging_dir is None:
        out = esr.convert("RGBA")
    else:
        orig = _load(staging_dir, staged_name, w, h, resize=True)          # native, has alpha
        alpha = orig.getchannel("A") if orig.mode == "RGBA" else None
        a = np.asarray(orig.convert("RGB"), np.float32)
        b = np.asarray(esr, np.float32)
        c = _tuner_sharpen(b)                                              # sharpen the esrgan layer
        mix = (BLEND_ORIG * a + BLEND_ESRGAN * b + BLEND_SHARP * c).clip(0, 255).astype(np.uint8)
        out = Image.fromarray(mix, "RGB").convert("RGBA")
        if alpha is not None:
            out.putalpha(alpha)                                            # keep original transparency
    if len(_cache) > 96:
        _cache.pop(next(iter(_cache)))
    _cache[key] = out
    return out

n_done = n_err = 0
for rec in manifest:
    try:
        if rec["kind"] == "pak":
            codebook = ({}, [])
            parts, pix_lines, off = [], [], 0
            for e in rec["entries"]:
                enh = enhanced_rgba(e["staged"], e["w"], e["h"])
                if e["ext"] == ".m16":
                    v = i76img.encode_m16(enh.tobytes(), e["w"], e["h"], e["flags"] or 0)
                elif e["ext"] == ".map":
                    idx = i76img.quantize_to_palette(enh.tobytes(), e["w"], e["h"], pal)
                    v = i76img.encode_map(idx, e["w"], e["h"])
                else:  # .vqm
                    idx = i76img.quantize_to_palette(enh.tobytes(), e["w"], e["h"], pal)
                    cbk_name = os.path.splitext(rec["pak"])[0].upper()[:8] + ".CBK"
                    v = i76img.encode_vqm(idx, e["w"], e["h"], cbk_name, codebook)
                parts.append(v); pix_lines.append((e["name"], off, len(v))); off += len(v)
            base = os.path.join(outdir, os.path.splitext(rec["pak"])[0])
            open(base + ".pak", "wb").write(b"".join(parts))
            with open(base + ".pix", "w", newline="") as f:
                f.write(f"{len(pix_lines)}\r\n")
                for n, o, l in pix_lines:
                    f.write(f"{n.upper()} {o} {l}\r\n")
            if codebook[1]:
                cbk_name = os.path.splitext(rec['pak'])[0].upper()[:8] + ".CBK"
                open(os.path.join(outdir, cbk_name.lower()), "wb").write(
                    struct.pack("<I", len(codebook[1])) + b"".join(codebook[1]))
        elif rec["kind"] == "loose_map":
            e = rec["entries"][0]
            enh = enhanced_rgba(e["staged"], e["w"], e["h"])
            idx = i76img.quantize_to_palette(enh.tobytes(), e["w"], e["h"], pal)
            body = struct.pack("<2I", e["w"], e["h"]) + bytes(idx)
            open(os.path.join(outdir, rec["file"]), "wb").write(body)
        elif rec["kind"] == "loose_m16":
            e = rec["entries"][0]
            enh = enhanced_rgba(e["staged"], e["w"], e["h"])
            v = i76img.encode_m16(enh.tobytes(), e["w"], e["h"], e["flags"] or 0)
            open(os.path.join(outdir, rec["file"]), "wb").write(v)
        n_done += 1
    except Exception as ex:
        n_err += 1
        print(f"ERR {rec.get('pak') or rec.get('file')}: {ex}", file=sys.stderr)
    if n_done % 100 == 0 and n_done:
        print(f"  ...{n_done}/{len(manifest)} rebuilt ({time.time()-t0:.0f}s)", flush=True)

print(f"DONE: {n_done} rebuilt, {n_err} errors, -> {outdir}  ({time.time()-t0:.0f}s)")
