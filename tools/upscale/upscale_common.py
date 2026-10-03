"""Shared helpers for the I'76 upscaling harness (upscale_run / score / contact_sheet / ab_viewer).

The work tree (images, weights, runs) lives OUTSIDE this public repo: default C:\\Users\\james\\i76-upscale-work,
override with --work or the I76_UPSCALE_WORK environment variable.
"""
import csv, os

import numpy as np
from PIL import Image

DEFAULT_WORK = os.environ.get("I76_UPSCALE_WORK", r"C:\Users\james\i76-upscale-work")


def load_manifest(work, path=None):
    path = path or os.path.join(work, "src", "manifest.csv")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["name"] = os.path.splitext(os.path.basename(r["file"]))[0]
        r["native_w"], r["native_h"] = int(r["native_w"]), int(r["native_h"])
        r["has_alpha"] = str(r.get("has_alpha", "0")) in ("1", "True", "true")
    return rows


def filter_rows(rows, classes=None, names=None):
    if classes:
        cs = set(classes.split(","))
        rows = [r for r in rows if r["class"] in cs]
    if names:
        ns = set(names.split(","))
        rows = [r for r in rows if r["name"] in ns]
    return rows


def read_rgb(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def read_mask(path):
    if path and os.path.exists(path):
        return np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
    return None


def to_u8(a):
    return (np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def save_rgb(path, rgb, alpha=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if alpha is None:
        Image.fromarray(to_u8(rgb), "RGB").save(path)
    else:
        Image.fromarray(np.dstack([to_u8(rgb), to_u8(alpha)]), "RGBA").save(path)


def run_dir(work, run_id):
    return os.path.join(work, "runs", run_id)


def final_path(work, run_id, row):
    return os.path.join(run_dir(work, run_id), "final", row["class"], row["name"] + ".png")
