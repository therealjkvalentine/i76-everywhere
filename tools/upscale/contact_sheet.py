#!/usr/bin/env python3
"""Contact sheet: rows = tiles, columns = original + each run's final (labelled), magenta behind alpha.

  python contact_sheet.py RUN_ID [RUN_ID ...] [--out PNG] [--classes ..] [--names ..] [--zoom 2]
                          [--no-original] [--max-width 640] [--scores]

Every cell is shown at the run's final size x zoom (nearest), the original nearest-resized to the same size.
Tiles wider than --max-width (after zoom) are shrunk to fit. --scores prints lpips/dists from
runs/<id>/scores.csv under each cell. Default out: WORK/runs/<first id>/contact_<ids>.png
"""
import argparse, csv, os, sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upscale_common as uc  # noqa: E402

BG, MAG = (32, 32, 32), (255, 0, 255, 255)


def flat(im):
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, MAG)
    bg.alpha_composite(im)
    return bg.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--work", default=uc.DEFAULT_WORK)
    ap.add_argument("--manifest")
    ap.add_argument("--out")
    ap.add_argument("--classes")
    ap.add_argument("--names")
    ap.add_argument("--zoom", type=float, default=2)
    ap.add_argument("--max-width", type=int, default=640)
    ap.add_argument("--no-original", action="store_true")
    ap.add_argument("--scores", action="store_true")
    a = ap.parse_args()
    rows = uc.filter_rows(uc.load_manifest(a.work, a.manifest), a.classes, a.names)
    scores = {}
    if a.scores:
        for run in a.runs:
            p = os.path.join(uc.run_dir(a.work, run), "scores.csv")
            if os.path.exists(p):
                for s in csv.DictReader(open(p, newline="")):
                    scores[(run, s["name"])] = s
    cols = ([] if a.no_original else ["original"]) + a.runs
    grid = []
    for r in rows:
        cells, size = [], None
        for run in a.runs:
            fp = uc.final_path(a.work, run, r)
            if os.path.exists(fp):
                size = size or Image.open(fp).size
        if size is None:
            continue
        w, h = round(size[0] * a.zoom), round(size[1] * a.zoom)
        if w > a.max_width:
            w, h = a.max_width, round(h * a.max_width / w)
        for c in cols:
            if c == "original":
                im = Image.open(os.path.join(a.work, r["file"])).convert("RGB")
                if r["has_alpha"]:
                    im.putalpha(Image.open(os.path.join(a.work, r["mask"])).convert("L"))
            else:
                fp = uc.final_path(a.work, c, r)
                im = Image.open(fp) if os.path.exists(fp) else None
            if im is None:
                cells.append(None)
                continue
            rs = Image.NEAREST if (c == "original" or a.zoom >= 1) else Image.LANCZOS
            cells.append(flat(im).resize((w, h), rs))
        grid.append((r, (w, h), cells))
    if not grid:
        raise SystemExit("nothing to draw (no finals for the selected tiles)")
    colw = [max(g[1][0] for g in grid) for _ in cols]
    lab, foot = 16, (14 if a.scores else 0)
    W = sum(colw) + 8 * (len(cols) + 1)
    H = 22 + sum(g[1][1] + lab + foot + 8 for g in grid)
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    x = 8
    for c, cw in zip(cols, colw):
        d.text((x, 4), c, fill=(255, 255, 0))
        x += cw + 8
    y = 22
    for r, (w, h), cells in grid:
        x = 8
        for c, cw, im in zip(cols, colw, cells):
            d.text((x, y), f"{r['class']}/{r['name']} {r['native_size']}" if c == "original" or a.no_original
                   else r["name"], fill=(230, 230, 230))
            if im is not None:
                sheet.paste(im, (x, y + lab))
            s = scores.get((c, r["name"]))
            if s:
                d.text((x, y + lab + h + 1), f"lpips {float(s['lpips']):.3f}  dists {float(s['dists']):.3f}  "
                       f"dE {float(s['de2000']):.2f}", fill=(160, 220, 160))
            x += cw + 8
        y += h + lab + foot + 8
    out = a.out or os.path.join(uc.run_dir(a.work, a.runs[0]), "contact_" + "+".join(a.runs)[:120] + ".png")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print("wrote", out, sheet.size)


if __name__ == "__main__":
    main()
