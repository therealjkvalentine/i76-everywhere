#!/usr/bin/env python3
"""U3 analysis for H2 (alpha/halo), H7 (colour match), H8 (palette lock), H11 (tiny tiles). Agent U3, 2026-10-03.

Reads model outputs the harness wrote (WORK/runs/u3-*/4x and /final), post-processes them with prepost.py, writes
derived runs (WORK/runs/u3-h7-*, u3-h8-* in the harness layout, so score.py / contact_sheet.py work on them),
CSV tables and contact sheets under WORK/u3/. Everything stays in WORK (copyrighted art, never in the repo).

  python u3_analyze.py h2 [--model hd|an]
  python u3_analyze.py h7 h8 [--base u3-h3-hd-none]
  python u3_analyze.py h11

H2 halo measure: final RGB composited with its mask over mid-grey, compared with a halo-free reference (the
original, edge-bled 8 px with nearest fill, Lanczos to 2x, composited with the nearest-2x original mask). In a
band of +-2 px around the reference mask edge, `band_dev` = mean |dL| (luminance, 0-1); `int_dev` = the same on
opaque pixels > 3 px inside; halo = band_dev - int_dev (how much worse the rim is than the model's ordinary
deviation); bias = signed mean dL in the band (< 0 dark fringe); iou = mask vs reference mask.
rim / rim_bias = prepost.halo_metrics on colour alone: |dL| vs the bled reference on the OUTPUT mask's own opaque
pixels within 2 px of its edge, minus the interior (independent of how the mask shape differs from the reference).
"""
import argparse, csv, json, os, shutil, sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prepost as pp  # noqa: E402
import upscale_common as uc  # noqa: E402

W = uc.DEFAULT_WORK
U3 = os.path.join(W, "u3")
GREY = (0.5, 0.5, 0.5)


def rows(alpha_only=False, names=None):
    rs = uc.load_manifest(W)
    if alpha_only:
        rs = [r for r in rs if r["has_alpha"]]
    if names:
        rs = [r for r in rs if r["name"] in names]
    return rs


def run_img(run, sub, row, rgba=False):
    p = os.path.join(W, "runs", run, sub, row["class"], row["name"] + ".png")
    return pp.load_rgba(p) if rgba else pp.load_rgb(p)


def write_csv(path, recs):
    keys = list(recs[0].keys())
    for r in recs:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(recs)


def halo(out_rgb, out_a, ref_rgb, ref_m, band=2):
    co = pp.composite(out_rgb, out_a, GREY)
    cr = pp.composite(ref_rgb, ref_m.astype(np.float32), GREY)
    dl = pp.luminance(co) - pp.luminance(cr)
    om = out_a >= 0.5
    din = ndi.distance_transform_edt(ref_m)
    dout = ndi.distance_transform_edt(~ref_m)
    bandm = (ref_m & (din <= band)) | (~ref_m & (dout <= band))
    inner = ref_m & (din > band + 1)
    u = (om | ref_m).sum()
    rim = pp.halo_metrics(out_rgb, om, ref_rgb, ref_m, band)
    return {"rim": rim["halo"], "rim_bias": rim["edge_bias"], "band_dev": float(np.abs(dl[bandm]).mean()), "int_dev": float(np.abs(dl[inner]).mean()) if inner.any()
            else float("nan"), "halo": float(np.abs(dl[bandm]).mean() - (np.abs(dl[inner]).mean() if inner.any()
                                                                         else 0)),
            "bias": float(dl[bandm].mean()), "iou": float((om & ref_m).sum() / u) if u else 1.0}


def edge_crop(m2, size=96):
    """(y0, x0) of a size x size window at 2x with the most mask-edge pixels."""
    e = m2 ^ ndi.binary_erosion(m2)
    h, w = m2.shape
    if h <= size and w <= size:
        return 0, 0, h, w
    s = ndi.uniform_filter(e.astype(np.float32), size, mode="constant")
    y, x = np.unravel_index(np.argmax(s), s.shape)
    y0 = int(np.clip(y - size // 2, 0, max(0, h - size)))
    x0 = int(np.clip(x - size // 2, 0, max(0, w - size)))
    return y0, x0, min(size, h), min(size, w)


# ------------------------------------------------------------------------------------------------------- H2

def h2(model):
    runs = {"raw": f"u3-h2-{model}-raw", "key": f"u3-h2-{model}-key", "b8": f"u3-h3-{model}-none"}
    if model == "hd":
        runs["b4"] = "u3-h2-hd-b4"
    recs, sheet_t, sheet_l = [], [], []
    for r in rows(alpha_only=True):
        orig = pp.load_rgb(os.path.join(W, r["file"]))
        m = pp.load_mask(os.path.join(W, r["mask"]))
        nh, nw = m.shape
        th, tw = nh * 2, nw * 2
        ref_rgb = pp.resize(pp.bleed(orig, m, 8, rest="nearest"), tw, th, "lanczos")
        ref_m = pp.resize(m.astype(np.float32), tw, th, "nearest") >= 0.5
        rgb2 = {k: pp.resize(run_img(v, "4x", r), tw, th, "lanczos") for k, v in runs.items()}
        masks = {"soft": pp.resize(m.astype(np.float32), tw, th, "lanczos")}
        for t in (0.2, 0.35, 0.5):
            masks[f"thr{t}"] = pp.upscale_alpha_threshold(m, tw, th, "bilinear", t).astype(np.float32)
        am = run_img("u3-h2-alphamodel", "4x", r).mean(2)
        masks["model"] = (pp.resize(am, tw, th, "area") >= 0.5).astype(np.float32)
        pal = pp.palette_from_image(orig, m)
        k4 = run_img(runs["key"], "4x", r)
        reg4 = pp.alpha_regenerate(k4, pal, key=pp.pick_key(pal), kuwahara_radius=1, grow=1)
        masks["regen"] = (pp.resize(reg4.astype(np.float32), tw, th, "area") >= 0.5).astype(np.float32)
        combos = [("raw", "soft", "combined RGBA (no bleed, soft alpha)")]
        combos += [(rk, mk, "") for rk in ("raw", "b4", "b8") if rk in rgb2
                   for mk in ("thr0.2", "thr0.35", "thr0.5", "model")]
        combos += [("key", "regen", "MrFlibble regenerate"), ("b8", "regen", "b8 colour + regen mask")]
        y0, x0, ch, cw = edge_crop(ref_m)
        crop = lambda a: a[y0:y0 + ch, x0:x0 + cw]
        tiles_row = [crop(pp.composite(ref_rgb, ref_m.astype(np.float32), GREY))]
        labs_row = ["reference"]
        for rk, mk, note in combos:
            hm = halo(rgb2[rk], masks[mk], ref_rgb, ref_m)
            recs.append(dict(model=model, tile=r["name"], rgb=rk, mask=mk, note=note,
                             **{k: round(v, 4) for k, v in hm.items()}))
            if (rk, mk) in (("raw", "soft"), ("raw", "thr0.5"), ("b4", "thr0.5"), ("b8", "thr0.5"),
                            ("b8", "thr0.2"), ("b8", "model"), ("key", "regen"), ("b8", "regen")):
                tiles_row.append(crop(pp.composite(rgb2[rk], masks[mk], GREY)))
                labs_row.append(f"{rk}/{mk} h{hm['halo']:.3f}")
        sheet_t += tiles_row
        sheet_l += labs_row
    write_csv(os.path.join(U3, f"h2_{model}.csv"), recs)
    pp.contact_sheet(sheet_t, sheet_l, 9, os.path.join(U3, f"h2_{model}_sheet.png"), 192, 192)
    # summary: mean over tiles per (rgb, mask)
    agg = {}
    for x in recs:
        agg.setdefault((x["rgb"], x["mask"]), []).append(x)
    print(f"H2 model={model}  n_tiles={len(set(x['tile'] for x in recs))}")
    print(f"{'rgb':5s} {'mask':8s} {'halo':>7s} {'band':>7s} {'int':>7s} {'bias':>7s} {'iou':>6s} {'rim':>7s} {'rimbias':>7s}  worst-tile-halo")
    summ = []
    for (rk, mk), xs in agg.items():
        f = lambda k: np.nanmean([x[k] for x in xs])
        worst = max(xs, key=lambda x: x["halo"])
        summ.append(dict(model=model, rgb=rk, mask=mk, halo=round(f("halo"), 4), rim=round(f("rim"), 4),
                         rim_bias=round(f("rim_bias"), 4), band_dev=round(f("band_dev"), 4),
                         int_dev=round(f("int_dev"), 4), bias=round(f("bias"), 4), iou=round(f("iou"), 4),
                         worst=f"{worst['tile']}:{worst['halo']:.3f}"))
        print(f"{rk:5s} {mk:8s} {f('halo'):7.4f} {f('band_dev'):7.4f} {f('int_dev'):7.4f} {f('bias'):7.4f} "
              f"{f('iou'):6.3f} {f('rim'):7.4f} {f('rim_bias'):7.4f}  {worst['tile']}:{worst['halo']:.3f}")
    write_csv(os.path.join(U3, f"h2_{model}_summary.csv"), summ)


# --------------------------------------------------------------------------------------------- derived runs

def derive_run(base, new_id, fn, note):
    """Copy run `base`'s finals through fn(final_rgb, final_alpha, orig, orig_mask, row) -> rgb into runs/new_id."""
    out = os.path.join(W, "runs", new_id)
    for r in rows():
        p = os.path.join(W, "runs", base, "final", r["class"], r["name"] + ".png")
        if not os.path.exists(p):
            continue
        rgb, a = pp.load_rgba(p)
        orig = pp.load_rgb(os.path.join(W, r["file"]))
        m = pp.load_mask(os.path.join(W, r["mask"])) if r["has_alpha"] else np.ones(orig.shape[:2], bool)
        new = fn(rgb, a, orig, m, r)
        dst = os.path.join(out, "final", r["class"], r["name"] + ".png")
        uc.save_rgb(dst, new, a if r["has_alpha"] else None)
        if r["has_alpha"]:
            mp = os.path.join(W, "runs", base, "mask", r["class"], r["name"] + ".png")
            os.makedirs(os.path.dirname(os.path.join(out, "mask", r["class"], r["name"] + ".png")), exist_ok=True)
            shutil.copy(mp, os.path.join(out, "mask", r["class"], r["name"] + ".png"))
    meta = json.load(open(os.path.join(W, "runs", base, "run.json")))
    meta.update(id=new_id, derived_from=base, post=note)
    json.dump(meta, open(os.path.join(out, "run.json"), "w"), indent=2)
    return new_id


def hist_gaps(rgb, mask):
    """Banding proxy: fraction of empty 8-bit levels between each channel's 1st and 99th percentile (opaque px)."""
    u = pp.to_u8(rgb)[mask]
    fr = []
    for c in range(3):
        v = u[:, c]
        lo, hi = np.percentile(v, 1), np.percentile(v, 99)
        if hi - lo < 4:
            continue
        levels = np.unique(v[(v >= lo) & (v <= hi)])
        fr.append(1 - len(levels) / (hi - lo + 1))
    return float(np.mean(fr)) if fr else 0.0


def colour_table(variants, tag):
    recs = []
    for r in rows():
        orig = pp.load_rgb(os.path.join(W, r["file"]))
        m = pp.load_mask(os.path.join(W, r["mask"])) if r["has_alpha"] else np.ones(orig.shape[:2], bool)
        rec = dict(tile=r["name"], cls=r["class"])
        for lab, run in variants:
            p = os.path.join(W, "runs", run, "final", r["class"], r["name"] + ".png")
            rgb, a = pp.load_rgba(p)
            th, tw = rgb.shape[:2]
            rec[f"dE_{lab}"] = round(pp.delta_e_native(rgb, orig, m, "box"), 3)
            m2 = (a >= 0.5) if r["has_alpha"] else np.ones((th, tw), bool)
            rec[f"gap_{lab}"] = round(hist_gaps(rgb, m2), 3)
            rec[f"ncol_{lab}"] = int(len(np.unique(pp.to_u8(rgb)[m2], axis=0)))
        rec["gap_orig2x"] = round(hist_gaps(pp.resize(orig, orig.shape[1] * 2, orig.shape[0] * 2, "lanczos"),
                                            pp.resize(m.astype(np.float32), orig.shape[1] * 2, orig.shape[0] * 2,
                                                      "nearest") >= .5), 3)
        rec["ncol_orig"] = int(len(pp.palette_from_image(orig, m)))
        recs.append(rec)
    write_csv(os.path.join(U3, f"{tag}.csv"), recs)
    keys = [k for k in recs[0] if k not in ("tile", "cls")]
    print(f"{tag}: n={len(recs)} tiles; means:")
    for k in keys:
        print(f"  {k:22s} {np.mean([x[k] for x in recs]):.3f}")
    return recs


def h7(base, short):
    hist = derive_run(base, f"u3-h7-{short}-hist",
                      lambda rgb, a, o, m, r: pp.histogram_match(rgb, o, (a >= .5) if r["has_alpha"] else None,
                                                                 m), "prepost.histogram_match")
    lut = derive_run(base, f"u3-h7-{short}-lut",
                     lambda rgb, a, o, m, r: pp.lut3d_match(rgb, o, m, n=9, smooth=1.0), "prepost.lut3d_match n9 s1")
    colour_table([("none", base), ("hist", hist), ("lut", lut)], f"h7_{short}")
    return hist, lut


def h8(base, short):
    ids = []
    for f in (1, 2, 4):
        def fn(rgb, a, o, m, r, f=f):
            pal = pp.palette_from_image(o, m)
            return pp.palette_lock(rgb, pp.widen_palette(pal, f) if f > 1 else pal)
        ids.append((f"pal{f}", derive_run(base, f"u3-h8-{short}-pal{f}", fn, f"palette_lock widen x{f}")))
    colour_table([("rgb", base)] + ids, f"h8_{short}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="+", choices=["h2", "h7", "h8"])
    ap.add_argument("--model", default="hd")
    ap.add_argument("--base", default="u3-h3-hd-none")
    ap.add_argument("--short", default="hd")
    a = ap.parse_args()
    os.makedirs(U3, exist_ok=True)
    for w in a.what:
        if w == "h2":
            h2(a.model)
        elif w == "h7":
            h7(a.base, a.short)
        elif w == "h8":
            h8(a.base, a.short)


if __name__ == "__main__":
    main()
