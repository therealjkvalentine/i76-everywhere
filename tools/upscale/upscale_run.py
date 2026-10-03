#!/usr/bin/env python3
"""Manifest-driven upscaler for the I'76 benchmark set (spandrel; any arch spandrel/spandrel_extra_arches loads).

  python upscale_run.py --recipe RECIPE.yaml|json [--id RUN_ID] [--work DIR] [--manifest CSV]
                        [--classes vehicle_panel,terrain] [--names pp11ftl1,...] [--set key=value ...]

Writes WORK/runs/<id>/
  4x/<class>/<name>.png     model output at the overscale (RGB; RGBA if the tile has alpha), before any post step
  final/<class>/<name>.png  result at native * target_scale (RGBA if the tile has alpha, else RGB)
  mask/<class>/<name>.png   final mask (L), only for tiles with alpha
  run.json                  resolved recipe per class, models, timings, tiles

Recipe (YAML or JSON). `default` applies to every class; `classes.<class>` overrides keys for that class.
--set overrides `default` from the command line (value parsed as YAML: --set model=4x-FSMangaV2.pth --set passes=2).

  default:
    model: RealESRGAN_x4plus_anime_6B.pth  # file in WORK/models or an absolute path
    pre_model: null        # optional model run first at native size (e.g. a 1x dedither); chain = pre_model > model
    overscale: 4           # total upscale before the downscale: 4, or 8/16 = model run twice (4x, resize to 2x, 4x)
    target_scale: 2        # final size = native * target_scale (1 = back to native size)
    downscale: lanczos     # lanczos | area | bicubic | box | nearest  (overscale -> target)
    alpha: separate        # combined  : RGB as decoded (transparent px stay black), mask resized, soft
                           # separate  : RGB edge-bleed `bleed_px` into transparent px first, mask upscaled separately
                           # threshold : as separate, then mask binarised at alpha_threshold
    bleed_px: 8            # native px of edge dilation into transparent px (separate/threshold)
    alpha_model: null      # e.g. 4xHDcube-Alpha.pth to upscale the mask with a model; null = lanczos resize
    alpha_threshold: 0.5
    pad: auto              # auto = wrap if manifest tiles==wrap else reflect; wrap | reflect | none
    pad_px: 16             # native px of padding, cropped after the model (wrap = seamless tiling)
    color_match: false     # per-channel histogram match of the final RGB to the original's opaque pixels
    palette_lock: false    # snap final RGB to the original's own colours (M16: its <=255-entry tile palette)
    tile: 512              # inference tile size in input px (0 = whole image); overlap 32
  classes:
    terrain: {pad: wrap}

GPU etiquette: batch 1, fp32 (fp16 is slow on the GTX 1080 Ti), cache emptied between models.
"""
import argparse, copy, datetime, json, math, os, subprocess, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upscale_common as uc  # noqa: E402

DEFAULTS = {
    "model": "RealESRGAN_x4plus_anime_6B.pth", "pre_model": None, "overscale": 4, "target_scale": 2,
    "downscale": "lanczos", "alpha": "separate", "bleed_px": 8, "alpha_model": None, "alpha_threshold": 0.5,
    "pad": "auto", "pad_px": 16, "color_match": False, "palette_lock": False, "tile": 512,
}

_models = {}


def get_model(work, name):
    import torch, spandrel
    try:
        import spandrel_extra_arches
        spandrel_extra_arches.install()
    except Exception:
        pass
    path = name if os.path.isabs(name) else os.path.join(work, "models", name)
    if path not in _models:
        for k in list(_models):  # keep at most 2 models resident
            if len(_models) >= 2:
                del _models[k]
        torch.cuda.empty_cache()
        m = spandrel.ModelLoader().load_from_file(path)
        m.model.eval().to("cuda" if torch.cuda.is_available() else "cpu")
        _models[path] = m
    return _models[path]


def infer(m, rgb, tile=512, overlap=32):
    """rgb HxWx3 float [0,1] -> (H*s)x(W*s)x3, tiled with overlap (centre crop of each tile kept)."""
    import torch
    s = m.scale
    dev = next(m.model.parameters()).device
    H, W, _ = rgb.shape

    def run(a):
        t = torch.from_numpy(np.ascontiguousarray(a.transpose(2, 0, 1)))[None].to(dev)
        with torch.no_grad():
            o = m.model(t)
        return o[0].clamp(0, 1).permute(1, 2, 0).float().cpu().numpy()

    if not tile or (H <= tile and W <= tile):
        return run(rgb)
    out = np.zeros((H * s, W * s, 3), np.float32)
    step = tile - 2 * overlap
    for y0 in range(0, H, step):
        for x0 in range(0, W, step):
            ya, xa = max(0, y0 - overlap), max(0, x0 - overlap)
            yb, xb = min(H, y0 + step + overlap), min(W, x0 + step + overlap)
            o = run(rgb[ya:yb, xa:xb])
            y1, x1 = min(H, y0 + step), min(W, x0 + step)
            out[y0 * s:y1 * s, x0 * s:x1 * s] = o[(y0 - ya) * s:(y1 - ya) * s, (x0 - xa) * s:(x1 - xa) * s]
    return out


def resize(a, w, h, method):
    import cv2
    if a.shape[1] == w and a.shape[0] == h:
        return a
    if method == "area":
        return cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
    from PIL import Image
    f = {"lanczos": Image.LANCZOS, "bicubic": Image.BICUBIC, "box": Image.BOX, "nearest": Image.NEAREST,
         "bilinear": Image.BILINEAR}[method]
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((w, h), f), np.float32).clip(0, 1)
    return np.dstack([resize(a[..., c], w, h, method) for c in range(a.shape[2])])


def bleed(rgb, mask, px):
    """Dilate opaque colours into transparent pixels, px steps (each step = 3x3 mean of known neighbours)."""
    if mask is None or px <= 0:
        return rgb
    import cv2
    rgb, known = rgb.copy(), (mask >= 0.5).astype(np.float32)
    k = np.ones((3, 3), np.float32)
    for _ in range(int(px)):
        if known.min() >= 1:
            break
        num = cv2.filter2D(rgb * known[..., None], -1, k, borderType=cv2.BORDER_REPLICATE)
        den = cv2.filter2D(known, -1, k, borderType=cv2.BORDER_REPLICATE)
        new = (den > 0) & (known < 1)
        rgb[new] = num[new] / den[new][:, None]
        known = np.maximum(known, (den > 0).astype(np.float32))
    return rgb


def upscale_rgb(work, rgb, cfg, pad_mode):
    """Native RGB -> RGB at `overscale`, with padding and the optional pre-model / multi-pass chain."""
    p = int(cfg["pad_px"]) if pad_mode != "none" else 0
    if p:
        rgb = np.pad(rgb, ((p, p), (p, p), (0, 0)), mode="wrap" if pad_mode == "wrap" else "reflect")
    H, W = rgb.shape[:2]
    if cfg.get("pre_model"):
        pm = get_model(work, cfg["pre_model"])
        rgb = infer(pm, rgb, cfg["tile"])
        if pm.scale != 1:
            rgb = resize(rgb, W, H, "area")
    m = get_model(work, cfg["model"])
    over, ms = float(cfg["overscale"]), m.scale
    n = 1 if ms == 1 else max(1, math.ceil(round(math.log(over) / math.log(ms), 6)))
    cur = 1.0
    for k in range(1, n + 1):
        rgb = infer(m, rgb, cfg["tile"])
        cur *= ms
        want = over / (ms ** (n - k))
        if abs(cur - want) > 1e-6:
            rgb = resize(rgb, round(W * want), round(H * want), "lanczos" if want > cur else "area")
            cur = want
    if p:
        q = round(p * cur)
        rgb = rgb[q:rgb.shape[0] - q, q:rgb.shape[1] - q]
    return rgb, cur


def upscale_mask(work, mask, cfg, size, pad_mode):
    w, h = size
    if cfg.get("alpha_model"):
        a3, _ = upscale_rgb(work, np.dstack([mask] * 3), dict(cfg, model=cfg["alpha_model"], pre_model=None,
                                                                overscale=cfg["overscale"]), pad_mode)
        a = resize(a3.mean(axis=2), w, h, "area")
    else:
        a = resize(mask, w, h, "lanczos")
    return a.clip(0, 1)


def hist_match(src, ref, src_w=None, ref_w=None):
    out = src.copy()
    for c in range(3):
        s = src[..., c][src_w] if src_w is not None else src[..., c].ravel()
        r = ref[..., c][ref_w] if ref_w is not None else ref[..., c].ravel()
        sq, si = np.unique(np.sort(s), return_index=True)
        scdf = (si + 0.5) / len(s)
        rs = np.sort(r)
        rcdf = (np.arange(len(rs)) + 0.5) / len(rs)
        mapped = np.interp(np.interp(src[..., c], sq, scdf), rcdf, rs)
        out[..., c] = mapped
    return out


def palette_lock(rgb, orig, orig_w):
    pal = np.unique((orig[orig_w] * 255 + 0.5).astype(np.int32), axis=0).astype(np.float32) / 255
    flat = rgb.reshape(-1, 3)
    idx = np.empty(len(flat), np.int64)
    for i in range(0, len(flat), 65536):
        d = ((flat[i:i + 65536, None, :] - pal[None]) ** 2).sum(-1)
        idx[i:i + 65536] = d.argmin(1)
    return pal[idx].reshape(rgb.shape)


def process(work, row, cfg, out):
    t0 = time.time()
    rgb = uc.read_rgb(os.path.join(work, row["file"]))
    mask = uc.read_mask(os.path.join(work, row["mask"])) if row["has_alpha"] else None
    pad_mode = cfg["pad"] if cfg["pad"] != "auto" else ("wrap" if row.get("tiles") == "wrap" else "reflect")
    src = rgb if (mask is None or cfg["alpha"] == "combined") else bleed(rgb, mask, cfg["bleed_px"])
    big, over = upscale_rgb(work, src, cfg, pad_mode)
    nw, nh = row["native_w"], row["native_h"]
    tw, th = round(nw * cfg["target_scale"]), round(nh * cfg["target_scale"])
    sub = os.path.join(row["class"], row["name"] + ".png")
    big_a = upscale_mask(work, mask, dict(cfg, alpha="separate"), (big.shape[1], big.shape[0]), pad_mode) \
        if mask is not None else None
    uc.save_rgb(os.path.join(out, "4x", sub), big, big_a)
    fin = resize(big, tw, th, cfg["downscale"]).clip(0, 1)
    fa = None
    if mask is not None:
        fa = resize(big_a, tw, th, "area").clip(0, 1)
        if cfg["alpha"] == "threshold":
            fa = (fa >= float(cfg["alpha_threshold"])).astype(np.float32)
    if cfg["color_match"] or cfg["palette_lock"]:
        orig_w = mask >= 0.5 if mask is not None else np.ones(rgb.shape[:2], bool)
        fw = fa >= 0.5 if fa is not None else None
        if cfg["color_match"]:
            fin = hist_match(fin, rgb, fw, orig_w)
        if cfg["palette_lock"]:
            fin = palette_lock(fin, rgb, orig_w)
    uc.save_rgb(os.path.join(out, "final", sub), fin, fa)
    if fa is not None:
        os.makedirs(os.path.dirname(os.path.join(out, "mask", sub)), exist_ok=True)
        from PIL import Image
        Image.fromarray(uc.to_u8(fa), "L").save(os.path.join(out, "mask", sub))
    return {"name": row["name"], "class": row["class"], "native": f"{nw}x{nh}", "overscale": over,
            "final": f"{tw}x{th}", "pad": pad_mode, "seconds": round(time.time() - t0, 2)}


def parse_val(v):
    import yaml
    return yaml.safe_load(v)


def load_recipe(path, sets):
    with open(path) as f:
        text = f.read()
    if path.lower().endswith(".json"):
        rec = json.loads(text)
    else:
        import yaml
        rec = yaml.safe_load(text) or {}
    rec.setdefault("default", {})
    rec.setdefault("classes", {})
    for s in sets or []:
        k, v = s.split("=", 1)
        rec["default"][k] = parse_val(v)
    return rec


def resolve(rec, cls):
    cfg = dict(DEFAULTS)
    cfg.update(rec.get("default") or {})
    cfg.update((rec.get("classes") or {}).get(cls) or {})
    bad = set(cfg) - set(DEFAULTS)
    if bad:
        raise SystemExit(f"unknown recipe keys: {sorted(bad)}")
    if cfg["alpha"] not in ("combined", "separate", "threshold"):
        raise SystemExit(f"alpha must be combined|separate|threshold, got {cfg['alpha']}")
    return cfg


def git_head():
    try:
        return subprocess.check_output(["git", "-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse",
                                        "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--id", help="run id (default: recipe basename + timestamp)")
    ap.add_argument("--work", default=uc.DEFAULT_WORK)
    ap.add_argument("--manifest")
    ap.add_argument("--classes", help="comma list of manifest classes")
    ap.add_argument("--names", help="comma list of tile names")
    ap.add_argument("--set", action="append", metavar="KEY=VALUE", help="override a default recipe key")
    ap.add_argument("--force", action="store_true", help="allow writing into an existing run dir")
    a = ap.parse_args()
    rec = load_recipe(a.recipe, a.set)
    run_id = a.id or os.path.splitext(os.path.basename(a.recipe))[0] + "-" + datetime.datetime.now().strftime(
        "%Y%m%d-%H%M%S")
    out = uc.run_dir(a.work, run_id)
    if os.path.exists(os.path.join(out, "run.json")) and not a.force:
        raise SystemExit(f"{out} already has a run.json; pick another --id or pass --force")
    os.makedirs(out, exist_ok=True)
    rows = uc.filter_rows(uc.load_manifest(a.work, a.manifest), a.classes, a.names)
    if not rows:
        raise SystemExit("no tiles selected")
    t0, results, cfgs = time.time(), [], {}
    for row in rows:
        cfg = resolve(rec, row["class"])
        cfgs[row["class"]] = cfg
        r = process(a.work, row, cfg, out)
        results.append(r)
        print(f"{r['class']:14s} {r['name']:10s} {r['native']:>8s} -> x{r['overscale']:g} -> {r['final']:>9s} "
              f"pad={r['pad']} {r['seconds']}s", flush=True)
    import torch
    meta = {"id": run_id, "created": datetime.datetime.now().isoformat(timespec="seconds"),
            "recipe_file": os.path.abspath(a.recipe), "recipe": rec, "resolved": cfgs,
            "manifest": a.manifest or os.path.join(a.work, "src", "manifest.csv"), "git": git_head(),
            "torch": torch.__version__, "device": torch.cuda.get_device_name(0) if torch.cuda.is_available()
            else "cpu", "seconds": round(time.time() - t0, 1), "tiles": results}
    with open(os.path.join(out, "run.json"), "w") as f:
        json.dump(meta, f, indent=2)
    _models.clear()
    torch.cuda.empty_cache()
    print(f"run {run_id}: {len(results)} tiles in {meta['seconds']}s -> {out}")


if __name__ == "__main__":
    main()
