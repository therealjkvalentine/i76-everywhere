#!/usr/bin/env python3
r"""illustrated_bakeoff.py - mini model bake-off for the illustrated classes (dash, shell bg, sprite, text, font).
Sprint 2026-10-03, agent U6. Runs in the shared venv (C:\Users\james\i76-upscale-work\.venv): torch + spandrel.

    python illustrated_bakeoff.py run     --src DIR --models a.pth b.pth ... --out RUN_DIR [--assets dash_a,bg_a]
    python illustrated_bakeoff.py sheets  --src DIR --out RUN_DIR [--crop-scale 2]

run: for every <asset>.png in --src (optional <asset>_mask.png = opaque mask) and every model:
     colour bled under transparent pixels (prepost.bleed) -> model at its native scale, repeated until >= 4x
     (a 2x model runs twice) -> exact 4x (area) -> 4x.png ; 4x -> 2x by area in linear light -> 2x.png.
     Alpha never goes through the model: bilinear-resize + threshold of the stock mask (prepost).
     Tiled (192 px input tiles, 16 px overlap), batch 1, fp32 (Pascal has no fast fp16), cache freed per model.
     scores.csv: model, asset, seconds, LPIPS and DISTS of (2x -> native, area) vs the original, Laplacian
     variance at 2x (sharpness proxy), mean dE2000 at native.
sheets: per asset, a 2x crop grid: nearest | lanczos | each model's 2x, plus a 4x crop grid (detail at full res).
All images stay in RUN_DIR (local; decoded/upscaled game art is copyrighted, never commit).
"""
import os, sys, csv, time, glob, argparse

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prepost as pp  # noqa: E402


def lin(x):
    return pp.srgb_to_linear(x) if hasattr(pp, "srgb_to_linear") else x ** 2.2


def delin(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055).astype(np.float32)


def area(rgb, w, h):
    """Area downscale in linear light."""
    return delin(pp.resize(lin(rgb), w, h, "box"))


def load_assets(src, only):
    out = []
    for f in sorted(glob.glob(os.path.join(src, "*.png"))):
        n = os.path.basename(f)[:-4]
        if n.endswith("_mask") or (only and n not in only):
            continue
        rgb = pp.load_rgb(f)
        mp = os.path.join(src, n + "_mask.png")
        mask = pp.load_mask(mp) if os.path.exists(mp) else None
        out.append((n, rgb, mask))
    return out


def run_model(model, rgb, dev, tile=192, ov=16):
    import torch
    s = model.scale
    h, w = rgb.shape[:2]
    out = np.zeros((h * s, w * s, 3), np.float32)
    wt = np.zeros((h * s, w * s, 1), np.float32)
    ys = list(range(0, max(h - ov, 1), tile - 2 * ov)) or [0]
    xs = list(range(0, max(w - ov, 1), tile - 2 * ov)) or [0]
    for y0 in ys:
        for x0 in xs:
            y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
            ya, xa = max(0, y1 - tile), max(0, x1 - tile)
            t = torch.from_numpy(np.ascontiguousarray(rgb[ya:y1, xa:x1].transpose(2, 0, 1)))[None].to(dev)
            with torch.no_grad():
                r = model(t).clamp(0, 1)[0].permute(1, 2, 0).float().cpu().numpy()
            # feather: weight falls off over the overlap so seams average
            th, tw = r.shape[:2]
            wy = np.minimum(np.arange(th) + 1, np.arange(th)[::-1] + 1).astype(np.float32)
            wx = np.minimum(np.arange(tw) + 1, np.arange(tw)[::-1] + 1).astype(np.float32)
            m = np.minimum(np.minimum.outer(wy, wx), ov * s)[..., None]
            out[ya * s:y1 * s, xa * s:x1 * s] += r * m
            wt[ya * s:y1 * s, xa * s:x1 * s] += m
    return out / np.maximum(wt, 1e-6)


def cmd_run(a):
    import torch
    import spandrel
    try:
        import spandrel_extra_arches
        spandrel_extra_arches.install()
    except Exception:
        pass
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    assets = load_assets(a.src, set(filter(None, a.assets.split(","))))
    os.makedirs(a.out, exist_ok=True)
    rows = []
    try:
        import pyiqa
        lp = pyiqa.create_metric("lpips", device=dev)
        ds = pyiqa.create_metric("dists", device=dev)
    except Exception as e:
        print("pyiqa unavailable:", e)
        lp = ds = None

    def iqa(metric, x, y):
        t = lambda z: torch.from_numpy(np.ascontiguousarray(z.transpose(2, 0, 1)))[None].to(dev)
        with torch.no_grad():
            return float(metric(t(x), t(y)))

    for mp in a.models:
        mname = os.path.splitext(os.path.basename(mp))[0]
        model = spandrel.ModelLoader().load_from_file(mp).to(dev).eval()
        print("model", mname, model.architecture.name, "x%d" % model.scale, flush=True)
        md = os.path.join(a.out, mname)
        os.makedirs(md, exist_ok=True)
        for n, rgb, mask in assets:
            h, w = rgb.shape[:2]
            inp = pp.bleed(rgb, mask, px=8) if mask is not None else rgb
            t0 = time.time()
            x, sc = inp, 1
            while sc < 4:
                x = run_model(model, x, dev)
                sc *= model.scale
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            secs = time.time() - t0
            x4 = x if sc == 4 else area(x, w * 4, h * 4)
            x2 = area(x4, w * 2, h * 2)
            pp.save_rgb(os.path.join(md, n + "_4x.png"), x4)
            pp.save_rgb(os.path.join(md, n + "_2x.png"), x2)
            if mask is not None:
                pp.save_mask(os.path.join(md, n + "_2x_mask.png"), pp.upscale_alpha_threshold(mask, w * 2, h * 2))
            nat = area(x2, w, h)
            rgb = inp  # score against the bled source: transparent pixels hold bled colour, not decoder black
            r = dict(model=mname, arch=model.architecture.name, scale=model.scale, asset=n, seconds=round(secs, 2),
                     lap_var_2x=round(pp.laplacian_variance(x2), 5),
                     dE_native=round(pp.mean_delta_e(nat, rgb, mask), 3))
            if lp is not None:
                r["lpips_native"] = round(iqa(lp, nat, rgb), 4)
                r["dists_native"] = round(iqa(ds, nat, rgb), 4)
            rows.append(r)
            print("  ", r, flush=True)
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    sp = os.path.join(a.out, "scores.csv")
    new = not os.path.exists(sp)
    keys = ["model", "arch", "scale", "asset", "seconds", "lpips_native", "dists_native", "dE_native", "lap_var_2x"]
    with open(sp, "a", newline="") as fh:
        wr = csv.DictWriter(fh, keys)
        if new:
            wr.writeheader()
        for r in rows:
            wr.writerow({k: r.get(k, "") for k in keys})


CROPS = {  # (x, y, w, h) in native pixels: the detail each sheet should show
    "dash_a": (0, 0, 256, 128), "dash_b": (0, 0, 256, 128), "bg_a": (0, 0, 320, 200),
    "bg_b": (0, 150, 320, 200), "text_a": (0, 50, 320, 150), "sprite_a": (0, 0, 190, 98), "font_a": (0, 0, 224, 120),
}
CROPS4 = {  # (x, y) of the half-size crop used on the 4x sheets
    "bg_a": (180, 20), "bg_b": (170, 320), "dash_a": (0, 0), "dash_b": (0, 0), "text_a": (180, 55), "sprite_a": (0, 0),
    "font_a": (0, 0),
}


def cmd_sheets(a):
    assets = load_assets(a.src, set(filter(None, a.assets.split(","))))
    models = sorted(d for d in os.listdir(a.out) if os.path.isdir(os.path.join(a.out, d)) and d != "sheets")
    sd = os.path.join(a.out, "sheets")
    os.makedirs(sd, exist_ok=True)
    for n, rgb, mask in assets:
        h, w = rgb.shape[:2]
        x, y, cw, ch = CROPS.get(n, (0, 0, min(w, 256), min(h, 192)))
        for sc in (2, 4):
            x, y = CROPS.get(n, (0, 0))[:2]
            if sc == 4:  # 4x sheets: half the crop so the cell stays readable
                cw4, ch4 = cw // 2, ch // 2
                x, y = CROPS4.get(n, (x, y))
            else:
                cw4, ch4 = cw, ch
            tiles, labels = [], []
            crop = rgb[y:y + ch4, x:x + cw4]
            tiles.append(pp.resize(crop, cw4 * sc, ch4 * sc, "nearest")); labels.append("stock nearest")
            tiles.append(pp.resize(crop, cw4 * sc, ch4 * sc, "lanczos")); labels.append("lanczos")
            for m in models:
                p = os.path.join(a.out, m, "%s_%dx.png" % (n, sc))
                if not os.path.exists(p):
                    continue
                img = pp.load_rgb(p)
                c = img[y * sc:(y + ch4) * sc, x * sc:(x + cw4) * sc]
                if mask is not None and sc == 2:
                    mk = pp.load_mask(os.path.join(a.out, m, n + "_2x_mask.png"))[y * sc:(y + ch4) * sc, x * sc:(x + cw4) * sc]
                    # dash masks are speckled near-black keys: judge colour on black, the mask on its own sheet
                    c = pp.composite(c, mk, "black" if n.startswith("dash") else "checker")
                tiles.append(c); labels.append(m)
            cols = 3 if cw4 * sc > 500 else 4
            pp.contact_sheet(tiles, labels, cols, os.path.join(sd, "%s_%dx.png" % (n, sc)))
            print(os.path.join(sd, "%s_%dx.png" % (n, sc)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--assets", default="")
    p = sub.add_parser("sheets")
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--assets", default="")
    a = ap.parse_args()
    if os.path.abspath(a.out).lower().startswith(os.path.dirname(os.path.dirname(HERE)).lower()):
        sys.exit("refusing to write images inside the public repo")
    {"run": cmd_run, "sheets": cmd_sheets}[a.cmd](a)


if __name__ == "__main__":
    main()
