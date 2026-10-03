#!/usr/bin/env python3
"""Score upscale runs against the originals (plan section 9, method b + c).

  python score.py RUN_ID [RUN_ID ...] [--metrics lpips,dists,lapvar,de] [--classes ..] [--names ..] [--cpu]

Per tile (manifest row with a final in runs/<id>/final/<class>/<name>.png):
  lpips, dists   final area-downscaled to native vs original (pyiqa; lower = more faithful). Transparent pixels
                 are filled from the original in both images, so only opaque content counts. Tiles under 64 px
                 are nearest-upsampled to >= 64 px on both sides before the nets.
  de2000         mean CIEDE2000 over opaque pixels at native size (lower = closer colour)
  lapvar         Laplacian variance of the final's luminance (x1000; higher = sharper)
  lapvar_ref     same for the original bicubic-resized to the final's size (the "no model" baseline)
Appends WORK/runs/scores.csv and writes WORK/runs/<id>/scores.csv.
"""
import argparse, csv, datetime, json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upscale_common as uc  # noqa: E402

FIELDS = ["time", "run", "class", "name", "native", "final", "lpips", "dists", "de2000", "lapvar", "lapvar_ref",
          "model", "recipe"]


def ciede2000(lab1, lab2):
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(C1p * C2p == 0, 0, dh)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    hs = h1p + h2p
    hbp = np.where(np.abs(h1p - h2p) > 180, np.where(hs < 360, hs / 2 + 180, hs / 2 - 180), hs / 2)
    hbp = np.where(C1p * C2p == 0, hs, hbp)
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def to_lab(rgb):
    import cv2
    return cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2LAB)  # float input: L 0-100, a/b unscaled


def lapvar(rgb):
    import cv2
    y = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float32)
    return float(cv2.Laplacian(y, cv2.CV_32F).var() * 1000)


def to_tensor(a, dev):
    import torch
    return torch.from_numpy(np.ascontiguousarray(a.transpose(2, 0, 1)))[None].float().to(dev)


def min64(a):
    h, w = a.shape[:2]
    k = max(1, -(-64 // min(h, w)))
    return np.repeat(np.repeat(a, k, 0), k, 1) if k > 1 else a


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--work", default=uc.DEFAULT_WORK)
    ap.add_argument("--manifest")
    ap.add_argument("--metrics", default="lpips,dists,lapvar,de")
    ap.add_argument("--classes")
    ap.add_argument("--names")
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args()
    import torch
    from upscale_run import resize
    dev = "cpu" if a.cpu or not torch.cuda.is_available() else "cuda"
    mets = set(a.metrics.split(","))
    nets = {}
    if mets & {"lpips", "dists"}:
        import pyiqa
        for n in ("lpips", "dists"):
            if n in mets:
                nets[n] = pyiqa.create_metric(n, device=dev, as_loss=False)
    rows = uc.filter_rows(uc.load_manifest(a.work, a.manifest), a.classes, a.names)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    allp = os.path.join(a.work, "runs", "scores.csv")
    for run in a.runs:
        rd = uc.run_dir(a.work, run)
        meta = {}
        if os.path.exists(os.path.join(rd, "run.json")):
            meta = json.load(open(os.path.join(rd, "run.json")))
        out = []
        for r in rows:
            fp = uc.final_path(a.work, run, r)
            if not os.path.exists(fp):
                continue
            from PIL import Image
            fin = np.asarray(Image.open(fp).convert("RGB"), np.float32) / 255
            orig = uc.read_rgb(os.path.join(a.work, r["file"]))
            mask = uc.read_mask(os.path.join(a.work, r["mask"])) if r["has_alpha"] else None
            nw, nh = r["native_w"], r["native_h"]
            back = resize(fin, nw, nh, "area").clip(0, 1)
            opaque = mask >= 0.5 if mask is not None else np.ones((nh, nw), bool)
            back_f = np.where(opaque[..., None], back, orig)
            res = {"time": now, "run": run, "class": r["class"], "name": r["name"], "native": f"{nw}x{nh}",
                   "final": f"{fin.shape[1]}x{fin.shape[0]}"}
            cfg = (meta.get("resolved") or {}).get(r["class"]) or {}
            res["model"] = cfg.get("model", "")
            res["recipe"] = os.path.basename(meta.get("recipe_file", ""))
            with torch.no_grad():
                for n, net in nets.items():
                    res[n] = round(float(net(to_tensor(min64(back_f), dev), to_tensor(min64(orig), dev))), 5)
            if "de" in mets:
                res["de2000"] = round(float(ciede2000(to_lab(back), to_lab(orig))[opaque].mean()), 4)
            if "lapvar" in mets:
                res["lapvar"] = round(lapvar(fin), 3)
                res["lapvar_ref"] = round(lapvar(resize(orig, fin.shape[1], fin.shape[0], "bicubic")), 3)
            out.append(res)
            print(f"{run:28s} {r['class']:14s} {r['name']:10s} " + " ".join(
                f"{k}={res[k]}" for k in ("lpips", "dists", "de2000", "lapvar", "lapvar_ref") if k in res))
        if not out:
            print(f"{run}: no finals found under {rd}\\final")
            continue
        for path, mode in ((os.path.join(rd, "scores.csv"), "w"), (allp, "a")):
            new = mode == "w" or not os.path.exists(path)
            with open(path, mode, newline="") as f:
                w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
                if new:
                    w.writeheader()
                w.writerows(out)
        means = {k: np.mean([o[k] for o in out if k in o]) for k in ("lpips", "dists", "de2000", "lapvar")
                 if any(k in o for o in out)}
        print(f"== {run} mean over {len(out)} tiles: " + " ".join(f"{k}={v:.4f}" for k, v in means.items()))


if __name__ == "__main__":
    main()
