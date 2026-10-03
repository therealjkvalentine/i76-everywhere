#!/usr/bin/env python3
"""Derived benchmark sources for H2/H3 (agent U3, 2026-10-03). Writes WORK/u3/src_<variant>/<class>/<name>.png and
WORK/u3/manifest_<variant>.csv (same rows as src/manifest.csv, `file` repointed, masks still the originals), so the
harness CLI can run models on them: upscale_run.py --manifest WORK/u3/manifest_<variant>.csv ...
Score against the ORIGINAL manifest (score.py default), never the derived one.

  variants:
    prepass  MrFlibble de-dither (prepost.dedither_prepass: Scale4x -> Gaussian 0.5 px -> Lanczos down) applied to
             the bled RGB (alpha tiles: bleed 8 px, rest nearest); transparent pixels keep the bled colour
    blurctl  control for prepass: same chain with Scale4x replaced by a Lanczos 4x (isolates what the pattern
             scaler adds over plain resample + 0.5 px blur)
    key      alpha tiles only: transparent pixels painted with pp.pick_key(tile palette) (magenta unless the tile uses it; input for MrFlibble mask regeneration)
    mask     alpha tiles only: the mask as a grey RGB tile (to run an alpha model through the plain RGB path)
"""
import argparse, csv, os, sys

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prepost as pp  # noqa: E402
import upscale_common as uc  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variants", nargs="+", choices=["prepass", "blurctl", "key", "mask"])
    ap.add_argument("--work", default=uc.DEFAULT_WORK)
    ap.add_argument("--sigma", type=float, default=0.5)
    a = ap.parse_args()
    src_manifest = os.path.join(a.work, "src", "manifest.csv")
    with open(src_manifest, newline="") as f:
        raw = list(csv.DictReader(f))
    for v in a.variants:
        rows = []
        for r in raw:
            alpha = r["has_alpha"] in ("1", "True", "true")
            if v in ("key", "mask") and not alpha:
                continue
            rgb = pp.load_rgb(os.path.join(a.work, r["file"]))
            mask = pp.load_mask(os.path.join(a.work, r["mask"])) if alpha else None
            if v == "prepass":
                base = pp.bleed(rgb, mask, 8, rest="nearest") if alpha else rgb
                out = pp.dedither_prepass(base, sigma=a.sigma)
            elif v == "blurctl":
                base = pp.bleed(rgb, mask, 8, rest="nearest") if alpha else rgb
                h, w = base.shape[:2]
                up = pp.resize(base, 4 * w, 4 * h, "lanczos")
                up = np.dstack([ndi.gaussian_filter(up[..., c], a.sigma, mode="nearest") for c in range(3)])
                out = pp.resize(up, w, h, "lanczos")
            elif v == "key":
                out = pp.key_fill(rgb, mask, pp.pick_key(pp.palette_from_image(rgb, mask)))
            else:
                out = np.dstack([mask.astype(np.float32)] * 3)
            rel = f"u3/src_{v}/{r['class']}/{os.path.basename(r['file'])}"
            os.makedirs(os.path.dirname(os.path.join(a.work, rel)), exist_ok=True)
            pp.save_rgb(os.path.join(a.work, rel), out)
            r2 = dict(r, file=rel)
            if v == "mask":
                r2["has_alpha"] = "0"
            rows.append(r2)
        mpath = os.path.join(a.work, "u3", f"manifest_{v}.csv")
        with open(mpath, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(raw[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(v, len(rows), "tiles ->", mpath)


if __name__ == "__main__":
    main()
