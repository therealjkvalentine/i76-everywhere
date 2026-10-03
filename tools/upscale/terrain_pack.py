#!/usr/bin/env python3
"""terrain_pack.py - build an upscaled terrain set (tp??m6.pak/.pix) for a loose ADDON override, U4's recipe
(findings\\U4.md "Recommended terrain recipe"), sprint 2026-10-03 task TERRAIN1.

  1. L0 (member '2', 256 px) decoded from the original pack.
  2. Native seam repair (terrain.repair_seam band 3, sigma 1.2) if its seam score > 1.3.
  3. 4x with wrap padding (64 src px) using the U2 terrain winner (Manga109Attempt x RRDB_PSNR 0.5 blend).
  4. 3D LUT colour match (prepost.lut3d_match, U3) of the 4x base to the (repaired) L0.
  5. Every level by area filter from that one base: L0 256, L1/L2 --far (128), L3 --far/2 (64), L4-6 --far/4 (32);
     each level's mean matched to the original level of the same member, quantised to <= 255 colours
     (snapped to RGB565 first), build_m16 with the original flags. Member '1' (never loaded) is copied unchanged;
     L1 = L2 byte-identical where the original set has them identical.
  6. Repack with the original member names and .pix order; decode back and report sizes + seam scores.

Usage (sprint venv: torch + spandrel):
  python terrain_pack.py --zfs <game>\\I76.ZFS --set tp04 --out OUTDIR [--far 128] [--model PTH] [--png-dir DIR]
Writes OUTDIR\\<set>m6.pak/.pix and <set>m6.terrain-pack.json. Output is derived game art: never commit it.
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import i76img  # noqa: E402
from terrain import open_zfs, seam_strength, repair_seam  # noqa: E402
from terrain_h6 import load_model, upscale, area_down, to8  # noqa: E402
from prepost import lut3d_match  # noqa: E402

DEFAULT_MODEL = r"C:\Users\james\i76-upscale-work\models\interp\4x_Manga109Attempt__4x_RRDB_PSNR__w50.pth"
PROTECTED = (r"\games\\", r"\games\interstate76", "i76-everywhere-portable", r"\i76-uncap-lab\game\addon",
             r"\i76-uncap-lab\game-dd-20261003")


def m16_rgb(d):
    w, h, flags, idx, pal = i76img.parse_m16(d)
    lut = np.array([i76img.rgb565_to_rgb888(c) for c in pal] + [(0, 0, 0)] * (256 - len(pal)), np.uint8)
    return lut[np.frombuffer(idx, np.uint8).reshape(h, w)], flags


def snap565(rgb8):
    """round-to-nearest (truncation biased every level ~-1.5 RGB; rgb565_to_rgb888 expands by *255//31)"""
    x = rgb8.astype(np.uint32)
    r, g, b = (x[..., 0] * 31 + 127) // 255, (x[..., 1] * 63 + 127) // 255, (x[..., 2] * 31 + 127) // 255
    return ((r << 11) | (g << 5) | b).astype(np.uint16)


def quantise_m16(rgb_f, flags, ncol=255):
    """float HxWx3 -> M16 bytes with <= ncol palette entries (RGB565). Median-cut without dither, then each
    palette entry is snapped to RGB565 and duplicate entries are merged."""
    h, w = rgb_f.shape[:2]
    rgb8 = to8(rgb_f)
    # exact path if the image already has few colours in RGB565
    c565 = snap565(rgb8)
    u, inv = np.unique(c565.ravel(), return_inverse=True)
    if len(u) <= ncol:
        return i76img.build_m16(w, h, flags, inv.astype(np.uint8).tobytes(), [int(c) for c in u]), len(u)
    # k-means in RGB (no dither): median cut stopped at ~100 colours and banded the L0 grain
    from scipy.cluster.vq import kmeans2
    px = rgb8.reshape(-1, 3).astype(np.float64)
    np.random.seed(0)
    cent, lab = kmeans2(px, ncol, minit="++", iter=20, seed=0)
    cent = np.array([px[lab == k].mean(0) if (lab == k).any() else cent[k] for k in range(len(cent))])
    pal = np.clip(cent + 0.5, 0, 255).astype(np.uint8)
    idx = lab.reshape(h, w).astype(np.uint8)
    used = np.unique(idx)
    p565 = snap565(pal[used])
    pu, pinv = np.unique(p565, return_inverse=True)
    remap = np.zeros(256, np.uint8)
    remap[used] = pinv.astype(np.uint8)
    return i76img.build_m16(w, h, flags, remap[idx].tobytes(), [int(c) for c in pu]), len(pu)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zfs", required=True, help="I76.ZFS to read the original set from (read only)")
    ap.add_argument("--set", default="tp04")
    ap.add_argument("--out", required=True)
    ap.add_argument("--far", type=int, default=128, help="L1/L2 size; L3 = far/2, L4-6 = far/4")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--pad", type=int, default=64)
    ap.add_argument("--seam-thr", type=float, default=1.3)
    ap.add_argument("--png-dir", help="also write the 4x base and each level as PNG here (work dir, local only)")
    a = ap.parse_args()
    oa = os.path.abspath(a.out).lower() + "\\"
    if any(b in oa for b in PROTECTED):
        sys.exit(f"refusing --out {a.out}: playable install or protected sandbox")
    os.makedirs(a.out, exist_ok=True)
    stem = a.set + "m6"
    ents, get = open_zfs(a.zfs)
    pix_text = get(stem + ".pix").decode("latin1")
    pak = get(stem + ".pak")
    toks = pix_text.split()
    members = [(toks[1 + 3 * i], int(toks[2 + 3 * i]), int(toks[3 + 3 * i])) for i in range(int(toks[0]))]
    orig = {nm.lower(): pak[o:o + ln] for nm, o, ln in members}
    lvl = {nm.lower()[4]: nm.lower() for nm, _, _ in members}

    l0_rgb, l0_flags = m16_rgb(orig[lvl["2"]])
    l0 = l0_rgb.astype(np.float32) / 255
    rep = {"set": a.set, "model": os.path.basename(a.model), "pad": a.pad, "far": a.far,
           "L0_seam_orig": seam_strength(l0)["seam"]}
    src = l0
    if rep["L0_seam_orig"] > a.seam_thr:
        src = repair_seam(l0, band=3, sigma=1.2).astype(np.float32)
        rep["seam_repair"] = "band 3 sigma 1.2"
    rep["L0_seam_repaired"] = seam_strength(src)["seam"]
    model = load_model(a.model)
    base = upscale(model, src, "wrap", a.pad)                 # 1024
    rep["base4x_seam_raw"] = seam_strength(base)["seam"]
    base = lut3d_match(base, src, down="box")
    rep["base4x_seam"] = seam_strength(base)["seam"]
    if a.png_dir:
        os.makedirs(a.png_dir, exist_ok=True)
        Image.fromarray(to8(base)).save(os.path.join(a.png_dir, f"{a.set}.base4x.png"))

    size_of = {"2": 256, "3": a.far, "4": a.far, "5": a.far // 2, "6": a.far // 4}
    new, levels = {}, []
    for ch in "123456":
        nm = lvl[ch]
        if ch == "1":
            new[nm] = orig[nm]
            continue
        if ch == "4" and orig[lvl["4"]] == orig[lvl["3"]]:
            new[nm] = new[lvl["3"]]
            levels.append({"member": nm, "note": "byte-identical to " + lvl["3"] + " (as in the original)"})
            continue
        s = size_of[ch]
        o_rgb, flags = m16_rgb(orig[nm])
        img = area_down(base, base.shape[0] // s)
        o_f = o_rgb.astype(np.float32) / 255
        img = np.clip(img + (o_f.reshape(-1, 3).mean(0) - img.reshape(-1, 3).mean(0)), 0, 1)
        data, npal = quantise_m16(img, flags)
        new[nm] = data
        dec, _ = m16_rgb(data)
        levels.append({"member": nm, "orig": f"{o_rgb.shape[1]}x{o_rgb.shape[0]}", "new": f"{s}x{s}",
                       "palette": npal, "bytes": len(data), "seam_orig": round(seam_strength(o_rgb)["seam"], 3),
                       "seam_new": round(seam_strength(dec)["seam"], 3),
                       "mean_drift_rgb": [round(float(x), 2) for x in
                                          (dec.reshape(-1, 3).mean(0) - o_rgb.reshape(-1, 3).mean(0))]})
        if a.png_dir:
            Image.fromarray(dec).save(os.path.join(a.png_dir, f"{nm[:-4]}.new{s}.png"))
            Image.fromarray(np.tile(dec, (4, 4, 1))).save(os.path.join(a.png_dir, f"{nm[:-4]}.new{s}.tiled4x4.png"))

    parts, man, off = [], [], 0
    for nm, _, _ in members:
        d = new[nm.lower()]
        parts.append(d); man.append((nm, off, len(d))); off += len(d)
    blob = b"".join(parts)
    pix = f"{len(man)}\r\n" + "".join(f"{nm} {o} {ln}\r\n" for nm, o, ln in man)
    base_out = os.path.join(a.out, stem)
    open(base_out + ".pak", "wb").write(blob)
    open(base_out + ".pix", "w", newline="").write(pix)

    # verify: decode the written pack back
    rb = open(base_out + ".pak", "rb").read()
    rt = open(base_out + ".pix", "rb").read().decode("latin1").split()
    check = []
    for i in range(int(rt[0])):
        nm, o, ln = rt[1 + 3 * i], int(rt[2 + 3 * i]), int(rt[3 + 3 * i])
        w, h, fl, idx, pal = i76img.parse_m16(rb[o:o + ln])
        assert 12 + w * h + 2 * len(pal) == ln and max(idx) < len(pal) and len(pal) <= 255, nm
        check.append(f"{nm} {w}x{h} pal={len(pal)} bytes={ln}")
    rep.update(levels=levels, decoded=check, member_order=[m[0] for m in members],
               pak_bytes=len(blob), pak_md5=hashlib.md5(blob).hexdigest(), orig_pix=pix_text)
    tmu = sum(int(c.split()[1].split("x")[0]) * int(c.split()[1].split("x")[1]) * 2 for c in check
              if c.split()[0].lower()[4] != "1")
    rep["tmu_bytes_16bit_levels_2to6"] = tmu
    json.dump(rep, open(base_out + ".terrain-pack.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "orig_pix"}, indent=1))


if __name__ == "__main__":
    main()
