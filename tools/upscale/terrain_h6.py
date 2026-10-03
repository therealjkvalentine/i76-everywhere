#!/usr/bin/env python3
"""H6 (wrap padding removes terrain seams) and the far-level chain test, sprint 2026-10-03 agent U4.

Run with the sprint venv (torch + spandrel):
  python terrain_h6.py WORK [--models a.pth,b.pth] [--sets tp04,tp09,tp18,tp06] [--pad 64] [--check3x3]

WORK = i76-upscale-work. Reads WORK/src/terrain/<set>/<set>2??6.png (the 256 px L0 tile, see terrain.py extract),
writes WORK/runs/u4-h6/<model>/<set>.<mode>.{4x,256}.png, corner crops, scores.csv and contact sheets.

Modes
  none   the 256 tile alone (the model sees a hard border at all four edges)
  wrap   np.pad(mode='wrap') by --pad source pixels, upscale, crop the centre (the '3x3 tile then crop'
         recipe restricted to the context a conv net can actually use; --check3x3 runs the full 3x3 once and
         reports the max difference so the shortcut is measured, not assumed)
Seam score: terrain.seam_strength (wrap-step / median interior step; 1.0 = invisible) on the 4x output and on
its area-downscale back to 256 (the in-engine size).

Chain test (step 4): for the far levels L1 (64), L3 (32), L4 (16), compare at the level's own size
  A  area-downscale of the wrap-upscaled 1024 base
  B  model 4x of the original level, area-downscaled back to the level's size  (upscale each original)
  O  the original level
against O (RMSE, 0-255) and against the L0-derived colour (mean dE76 of the level mean), because a level whose
average colour departs from its neighbours shows as a band at the 50/100/200/400 m switch.
"""
from __future__ import annotations

import argparse, csv, glob, os, sys, time

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from terrain import seam_strength  # noqa: E402

DEFAULT_MODELS = "4xHDcube3_500k.pth,4xNomos8kSC.pth,4x_RRDB_PSNR.pth"


def load_model(path):
    import torch, spandrel
    m = spandrel.ModelLoader().load_from_file(path).eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    m = m.to(dev)
    half = False  # GTX 1080 Ti (Pascal): fp16 is ~1/64 rate, fp32 is faster
    if half:
        m = m.half()
    return m, dev, half


def run_model(model, x):
    """x float32 HxWx3 in [0,1] -> float32 (sH)x(sW)x3."""
    import torch
    m, dev, half = model
    t = torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1), dtype=np.float32))[None].to(dev)
    t = t.half() if half else t
    with torch.inference_mode():
        y = m(t)
    out = y[0].float().clamp(0, 1).cpu().numpy().transpose(1, 2, 0)
    del t, y
    if dev == "cuda":
        torch.cuda.empty_cache()
    return out


def area_down(a, n):
    h, w, c = a.shape
    return a.reshape(h // n, n, w // n, n, c).mean((1, 3))


def upscale(model, rgb, mode, pad):
    s = model[0].scale
    if mode == "none":
        return run_model(model, rgb)
    if mode == "wrap":
        p = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode="wrap")
        y = run_model(model, p)
        return y[pad * s:(pad + rgb.shape[0]) * s, pad * s:(pad + rgb.shape[1]) * s]
    if mode == "3x3":
        y = run_model(model, np.tile(rgb, (3, 3, 1)))
        h, w = rgb.shape[0] * s, rgb.shape[1] * s
        return y[h:2 * h, w:2 * w]
    raise ValueError(mode)


def to8(a):
    return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)


def ld(p):
    return np.asarray(Image.open(p).convert("RGB"), np.float32) / 255.0


def corner_crop(a, size):
    """size x size crop centred on the tile corner of a 2x2 wrap tiling (where all four seams meet)."""
    t = np.tile(a, (2, 2, 1))
    h, w = a.shape[:2]
    return t[h - size // 2:h + size // 2, w - size // 2:w + size // 2]


def lab_mean(a):
    from prepost import srgb_to_lab  # U3's library (same folder)
    return srgb_to_lab(a.reshape(-1, 1, 3)).reshape(-1, 3).mean(0)


def sheet(cells, cols, path, label_h=14):
    """cells: list of (label, uint8 HxWx3), same size."""
    h, w = cells[0][1].shape[:2]
    rows = (len(cells) + cols - 1) // cols
    o = Image.new("RGB", (cols * (w + 4), rows * (h + label_h + 4)), "white")
    d = ImageDraw.Draw(o)
    for i, (lab, im) in enumerate(cells):
        x, y = (i % cols) * (w + 4), (i // cols) * (h + label_h + 4)
        d.text((x + 2, y), lab, fill="black")
        o.paste(Image.fromarray(im), (x, y + label_h))
    o.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--models", default=DEFAULT_MODELS)
    ap.add_argument("--sets", default="tp04,tp09,tp18,tp06")
    ap.add_argument("--pad", type=int, default=64)
    ap.add_argument("--check3x3", action="store_true")
    a = ap.parse_args()
    out = os.path.join(a.work, "runs", "u4-h6")
    os.makedirs(out, exist_ok=True)
    rows, chain_rows = [], []
    base = {s: sorted(glob.glob(os.path.join(a.work, "src", "terrain", s, s + "2??6.png")))[0] for s in a.sets.split(",")}
    for s, p in base.items():  # originals, for reference
        r0 = ld(p)
        sc = seam_strength(r0 * 255)
        rows.append(dict(model="original", set=s, mode="-", size=256, **{k: round(v, 3) for k, v in sc.items()}, secs=0))
    crops = {s: [("original x4 nearest", np.repeat(np.repeat(to8(corner_crop(ld(p), 64)), 4, 0), 4, 1))] for s, p in base.items()}
    tiled = {s: [("original", to8(np.tile(ld(p), (4, 4, 1))))] for s, p in base.items()}
    for mpath in a.models.split(","):
        mname = os.path.splitext(os.path.basename(mpath))[0]
        model = load_model(os.path.join(a.work, "models", mpath))
        md = os.path.join(out, mname)
        os.makedirs(md, exist_ok=True)
        for s, p in base.items():
            rgb = ld(p)
            for mode in ("none", "wrap"):
                t0 = time.time()
                y = upscale(model, rgb, mode, a.pad)
                dt = time.time() - t0
                y256 = area_down(y, y.shape[0] // 256)
                Image.fromarray(to8(y)).save(os.path.join(md, f"{s}.{mode}.4x.png"))
                Image.fromarray(to8(y256)).save(os.path.join(md, f"{s}.{mode}.256.png"))
                for size, img in ((y.shape[0], y), (256, y256)):
                    sc = seam_strength(img * 255)
                    rows.append(dict(model=mname, set=s, mode=mode, size=size,
                                     **{k: round(v, 3) for k, v in sc.items()}, secs=round(dt, 2)))
                crops[s].append((f"{mname} {mode}", to8(corner_crop(y, 256))))
                tiled[s].append((f"{mname} {mode} ->256", to8(np.tile(y256, (4, 4, 1)))))
                if mode == "wrap":
                    ywrap = y
            if a.check3x3 and mpath == a.models.split(",")[0]:
                y3 = upscale(model, rgb, "3x3", a.pad)
                d = np.abs(y3 - ywrap)
                print(f"{s} {mname}: 3x3 vs wrap-pad{a.pad}: max {d.max()*255:.2f} mean {d.mean()*255:.4f} (0-255)")
            # chain test, step 4
            for lv, n in (("3", 64), ("5", 32), ("6", 16)):
                op = glob.glob(os.path.join(os.path.dirname(p), f"{s}{lv}??6.png"))[0]
                O = ld(op)
                A = area_down(ywrap, ywrap.shape[0] // n)
                yb = upscale(model, O, "wrap", min(a.pad, n))
                B = area_down(yb, yb.shape[0] // n)
                L0n = area_down(rgb, 256 // n)
                rm = lambda u, v: float(np.sqrt(((u - v) ** 2).mean()) * 255)
                dE = lambda u, v: float(np.linalg.norm(lab_mean(u) - lab_mean(v)))
                chain_rows.append(dict(model=mname, set=s, level=lv, size=n,
                                       rmse_A_vs_O=round(rm(A, O), 2), rmse_B_vs_O=round(rm(B, O), 2),
                                       rmse_boxL0_vs_O=round(rm(L0n, O), 2),
                                       dEmean_A_vs_L0=round(dE(A, rgb), 2), dEmean_B_vs_L0=round(dE(B, rgb), 2),
                                       dEmean_O_vs_L0=round(dE(O, rgb), 2),
                                       seam_A=round(seam_strength(A * 255)["seam"], 3),
                                       seam_B=round(seam_strength(B * 255)["seam"], 3)))
                # bigger far levels (in-engine option: L1/L2 at 256 instead of 64): A256 vs B256 detail
                if lv == "3":
                    Image.fromarray(to8(area_down(ywrap, ywrap.shape[0] // 256))).save(os.path.join(md, f"{s}.L1as256.A.png"))
                    Image.fromarray(to8(yb)).save(os.path.join(md, f"{s}.L1as256.B.png"))
        del model
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
    with open(os.path.join(out, "scores.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, list(rows[0].keys()))
        wr.writeheader(); wr.writerows(rows)
    with open(os.path.join(out, "chain.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, list(chain_rows[0].keys()))
        wr.writeheader(); wr.writerows(chain_rows)
    for s in base:
        sheet(crops[s], 3, os.path.join(out, f"{s}.corner-crops.png"))
        sheet([(l, im[:512, :512]) for l, im in tiled[s]], 3, os.path.join(out, f"{s}.tiled-256.png"))
    for r in rows:
        print(r)
    for r in chain_rows:
        print(r)


if __name__ == "__main__":
    main()
