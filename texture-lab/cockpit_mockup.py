#!/usr/bin/env python3
"""cockpit_mockup.py - stage 0 of docs/research/COCKPIT-HIRES-FEASIBILITY.md: a picture the owner can judge before any
console time. Decodes the dash tiles (ZDASHn01/n02.M16 from zdashn06.pak), upscales them 2x and 4x, rebuilds the
dash from the cockpit .geo, and writes an HTML page with 1x / 2x / 4x side by side, plus crops:

  1. In situ: the stock start-line cockpit capture (3440x1440, best-wide) with the visible dash strip re-rendered.
     The dash plane's screen mapping is fitted to the capture itself (x = a + sx*X, y = b - sy*Y, least squares on
     the strip, 1x render vs capture), so the 1x panel is a reproduction check of the fit.
  2. Look-down: the whole dash panel front-on at the same horizontal magnification as in game (what a head-look
     down shows, minus perspective). The needles (separate sub-objects) and painted faces are not drawn.
  3. What does not change: crops of the painted gauge faces from the same capture (radar, weapons, damage).

Upscaler (redistributable as a recipe, docs/research/COCKPIT-HIRES-FEASIBILITY.md section 5): U2's dash-class winner,
4x-Manga109Attempt (CC-BY-4.0) x 4x_RRDB_PSNR (Apache-2.0) interpolated 50/50, run at 4x; the 2x is a Lanczos
downscale of that 4x (U2's "o4 -> 2x"). Weights are read from <work>/models/interp (never in the repo). If they are
missing it falls back to a classical Lanczos + luminance unsharp and says so on the page.

Inputs are read only: the archive (I76.ZFS in --game; ADDON copies ignored) and the capture. Output goes to
--out (default texture-lab/out/cockpit-mockup, gitignored): derived game art, never commit.
Also writes tiles/<TILE>.png (the 2x, stored orientation) for `cockpit_split.py --png-dir`.

Run with the upscale venv (torch + spandrel):
  <upscale-work>\\.venv\\Scripts\\python.exe texture-lab\\cockpit_mockup.py --game <dir>
"""
import argparse, datetime, html, json, os, sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "upscale"))
import cockpit_split as cs  # noqa: E402

MODEL = "interp/4x_Manga109Attempt__4x_RRDB_PSNR__w50.pth"
CAPTURE = (__import__("os").path.expanduser("~") + r"\i76-uncap-lab\captures\graphics\look\hudsq2-on-a-target.png")


def upscale_model(work, rgb):
    import upscale_run as ur
    cfg = dict(ur.DEFAULTS, model=MODEL, overscale=4, pad="reflect", pad_px=16, tile=512)
    big, over = ur.upscale_rgb(work, rgb, cfg, "reflect")
    assert abs(over - 4) < 1e-6
    big = big.clip(0, 1)
    h, w = rgb.shape[:2]
    two = ur.resize(big, 2 * w, 2 * h, "lanczos").clip(0, 1)
    return two, big


def upscale_classical(rgb, s):
    """Lanczos s-x + luminance-only unsharp (texture-lab's 2026-07 sharpen: box-blur unsharp, amount 1.16, r 0.8)."""
    h, w = rgb.shape[:2]
    im = Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).resize((w * s, h * s), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255
    import cv2
    y = a @ np.array([0.299, 0.587, 0.114], np.float32)
    r = max(1, int(round(0.8 * s)))
    blur = cv2.blur(y, (2 * r + 1, 2 * r + 1))
    return (a + 1.16 * (y - blur)[..., None]).clip(0, 1)


def save(path, a):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def fit_strip(geo, tex1x, cap, region):
    """Fit the dash plane -> screen mapping so the 1x render matches the capture in region (x0,y0,x1,y1):
    first affine (x = a + sx*X, y = b - sy*Y), then a full plane homography from there (the camera looks down
    onto the panel, so its vertical edges converge). Loss = residual after a linear grey-level fit."""
    from scipy.optimize import minimize
    x0, y0, x1, y1 = region
    target = cap[y0:y1, x0:x1]
    shift = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], float)

    def loss_m(M):
        img, cov = cs.render_faces(geo, tex1x, (x1 - x0, y1 - y0), shift @ M, ss=1)
        if cov.sum() < 500:
            return 1e3
        A = img[cov].mean(1); B = target[cov].mean(1)
        g = np.polyfit(A, B, 1)
        return float(((np.polyval(g, A) - B) ** 2).mean()) + 0.05 * (1 - cov.mean())

    best = None
    for sy0 in (0.5, 0.8, 1.1):
        p0 = [2552.0, 2041.0, 1351 + 2041 * sy0 * 0.163, 2041 * sy0]
        r = minimize(lambda p: loss_m(cs.xform_matrix(tuple(p))), p0, method="Nelder-Mead",
                     options={"xatol": 0.05, "fatol": 1e-7, "maxiter": 1500})
        if best is None or r.fun < best.fun:
            best = r
    M0 = cs.xform_matrix(tuple(best.x))
    scale = np.array([M0[0, 0], 1000, 100, 1000, M0[1, 1], 100, 1, 1])     # normalise the 8 free entries

    def mat(q):
        e = q * scale
        return np.array([[e[0], e[1] / 1000, e[2]], [e[3] / 1000, e[4], e[5]], [e[6] / 1000, e[7] / 1000, 1]])
    q0 = np.array([1, 0, M0[0, 2] / 100, 0, 1, M0[1, 2] / 100, 0, 0], float)
    r2 = minimize(lambda q: loss_m(mat(q)), q0, method="Nelder-Mead",
                  options={"xatol": 1e-5, "fatol": 1e-8, "maxiter": 6000, "adaptive": True})
    return (mat(r2.x), r2.fun, best.fun) if r2.fun < best.fun else (M0, best.fun, best.fun)


def colour_fit(img, cap, cov):
    """Per-channel linear map render -> capture over covered pixels (dgVoodoo gamma, 1555 conversion)."""
    g = []
    for c in range(3):
        g.append(np.polyfit(img[cov][:, c], cap[cov][:, c], 1))
    return lambda a: np.dstack([np.polyval(g[c], a[..., c]) for c in range(3)]).clip(0, 1), g


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", default=(__import__("os").path.expanduser("~") + r"\i76-map\sandbox-gog\main\app"))
    ap.add_argument("--car-pak", default="vppirnag")
    ap.add_argument("--capture", default=CAPTURE)
    ap.add_argument("--work", default=os.environ.get("I76_UPSCALE_WORK", (__import__("os").path.expanduser("~") + r"\i76-upscale-work")))
    ap.add_argument("--out", default=os.path.join(HERE, "out", "cockpit-mockup"))
    ap.add_argument("--classical", action="store_true", help="force the classical upscale")
    ap.add_argument("--marker-dir", default=os.path.join(HERE, "out", "cockpit-split", "marker2x"),
                    help="a cockpit_split.py --marker output to preview in situ (skipped if absent)")
    ap.add_argument("--redo", action="store_true", help="re-run the model even if tiles/*.png exist")
    a = ap.parse_args()
    cs.refuse_out(a.out)
    os.makedirs(a.out, exist_ok=True)
    src = cs.Source(a.game, no_addon=True)
    car = dict((k.upper(), v) for k, v in cs.pak_members(src.read(a.car_pak + ".pak"), src.read(a.car_pak + ".pix")))
    gname = cs.find_dash_geo(list(car.items()))
    geo = cs.parse_geo(car[gname])
    stems = sorted({cs.tex_stem(f) for f in geo.faces if cs.TILE_RE.match(cs.tex_stem(f))})
    tpak = f"zdash{cs.TILE_RE.match(stems[0]).group(1)}06"
    tex = dict((k.upper(), v) for k, v in cs.pak_members(src.read(tpak + ".pak"), src.read(tpak + ".pix")))

    have_model = os.path.exists(os.path.join(a.work, "models", MODEL)) and not a.classical
    T = {"1x": {}, "2x": {}, "4x": {}, "2x-classical": {}}
    for st in stems:
        rgb = cs.m16_to_array(tex[st + ".M16"])            # 0xFF texels as black (how they render: 1555 0x0000)
        T["1x"][st] = rgb
        cached = [os.path.join(a.out, "tiles", st + n) for n in (".png", "_4x.png")]
        if have_model and not a.redo and all(os.path.exists(c) for c in cached) and                 json.load(open(os.path.join(a.out, "mockup.json"))).get("model") == MODEL:
            T["2x"][st], T["4x"][st] = [np.asarray(Image.open(c).convert("RGB"), np.float32) / 255 for c in cached]
        elif have_model:
            T["2x"][st], T["4x"][st] = upscale_model(a.work, rgb)
        else:
            T["2x"][st], T["4x"][st] = upscale_classical(rgb, 2), upscale_classical(rgb, 4)
        T["2x-classical"][st] = upscale_classical(rgb, 2)
        save(os.path.join(a.out, "tiles", st + ".png"), T["2x"][st])
        save(os.path.join(a.out, "tiles", st + "_4x.png"), T["4x"][st])
        save(os.path.join(a.out, "tiles", st + "_1x.png"), rgb)
        # as seen (rows flipped: v = 0 is the bottom of the panel)
        for k in ("1x", "2x", "4x"):
            save(os.path.join(a.out, "tiles-as-seen", f"{st}_{k}.png"), T[k][st][::-1])

    cap = np.asarray(Image.open(a.capture).convert("RGB"), np.float32) / 255
    H, W = cap.shape[:2]
    region = (2000, 1330, W, H)                        # right of the PRND / N overlays, the visible dash strip
    M, fun, fun_affine = fit_strip(geo, T["1x"], cap, region)
    p = M
    # horizontal magnification at the dash's visible top edge (model y = 0.163) and the strip's top row
    xt = np.array([[-0.5, 0.163, 1], [0.5, 0.163, 1]]) @ M.T
    xt = xt[:, :2] / xt[:, 2:]
    sx = float(xt[1, 0] - xt[0, 0]); strip_top = float(xt[:, 1].mean())
    full1, cov = cs.render_faces(geo, T["1x"], (W, H), p)
    cmap, gains = colour_fit(full1, cap, cov & (np.arange(W)[None, :] >= 2000))
    resid = np.abs(cmap(full1) - cap).mean(2)
    occl = cov & (resid > 0.12)                          # PRND / N plates etc. drawn in front of the dash
    keep = cov & ~occl
    insitu = {}
    for k in ("1x", "2x", "4x"):
        img, _ = cs.render_faces(geo, T[k], (W, H), p)
        comp = cap.copy(); comp[keep] = cmap(img)[keep]
        insitu[k] = comp
        save(os.path.join(a.out, f"insitu_{k}.png"), comp)
        save(os.path.join(a.out, f"insitu_strip_{k}.png"), comp[1300:H, 1500:W])
        save(os.path.join(a.out, f"insitu_strip_crop_{k}.png"), comp[1320:H, 2200:3000])
    save(os.path.join(a.out, "insitu_strip_capture.png"), cap[1300:H, 1500:W])
    # what the stage-2 marker boot should show: cockpit_split.py --marker output rendered the same way
    marker_ok = False
    if a.marker_dir and os.path.exists(os.path.join(a.marker_dir, "zdash106.pak")):
        rd = lambda n: open(os.path.join(a.marker_dir, n), "rb").read()
        mg = cs.parse_geo(dict((k.upper(), v) for k, v in cs.pak_members(rd(a.car_pak + ".pak"), rd(a.car_pak + ".pix")))[gname])
        mt = {k.split(".")[0].upper(): cs.m16_to_array(v) for k, v in cs.pak_members(rd(tpak + ".pak"), rd(tpak + ".pix")) if "Q" in k.upper()}
        img, mcov = cs.render_faces(mg, mt, (W, H), p)
        comp = cap.copy(); mk = mcov & ~occl; comp[mk] = cmap(img)[mk]
        save(os.path.join(a.out, "insitu_strip_marker.png"), comp[1300:H, 1500:W])
        marker_ok = True
    save(os.path.join(a.out, "insitu_strip_crop_capture.png"), cap[1320:H, 2200:3000])
    resid_fit = float(np.abs(insitu["1x"] - cap)[keep].mean() * 255)

    # look-down panel, front-on, horizontal scale as fitted, square pixels
    xs = [v[0] for v in geo.verts]; ys = [v[1] for v in geo.verts]
    pw = int((max(xs) - min(xs)) * sx) + 40
    ph = int((max(ys) - min(ys)) * sx) + 40
    xf = (20 - min(xs) * sx, sx, 20 + max(ys) * sx, sx)
    panels = {}
    for k in ("1x", "2x", "4x", "2x-classical"):
        img, pc = cs.render_faces(geo, T[k], (pw, ph), xf)
        img = cmap(img); img[~pc] = 0.12
        panels[k] = img
        save(os.path.join(a.out, f"panel_{k}.png"), img)
    # crops (panel pixel boxes chosen from the geometry: speedo/tach on ZDASH101, radio and small gauges on 102)
    def box_uv(stem, u0, v0, u1, v1):
        f = [f for f in geo.faces if cs.tex_stem(f) == stem]
        f = max(f, key=lambda f: len(f["vrefs"]) + (f["vrefs"][0][3] < 0.5))
        P = np.array([(xf[0] + sx * geo.verts[r[0]][0], xf[2] - sx * geo.verts[r[0]][1]) for r in f["vrefs"]])
        UV = np.array([(r[2], r[3]) for r in f["vrefs"]])
        X = np.c_[UV, np.ones(len(UV))]
        c, *_ = np.linalg.lstsq(X, P, rcond=None)
        q = np.array([[u0, v0, 1], [u1, v1, 1]]) @ c
        return int(q[:, 0].min()), int(q[:, 1].min()), int(q[:, 0].max()), int(q[:, 1].max())
    crops = {"speedo": box_uv("ZDASH101", 0.33, 1.0, 0.66, 0.15), "warning lamps + dial": box_uv("ZDASH101", 0.07, 0.97, 0.33, 0.35),
             "radio": box_uv("ZDASH102", 0.2, 0.97, 0.53, 0.7), "small gauges": box_uv("ZDASH102", 0.13, 0.42, 0.52, 0.05)}
    for name, (x0, y0, x1, y1) in crops.items():
        for k, img in panels.items():
            save(os.path.join(a.out, "crops", f"{name.replace(' ', '_').replace('+', '')}_{k}.png"), img[y0:y1, x0:x1])
    # untouched painted faces from the capture
    fixed = {"radar (painted, stays 256 px)": (640, 0, 1300, 330), "weapons panel (painted)": (1340, 0, 1910, 390),
             "damage diagram (painted)": (1950, 0, 2640, 390)}
    for name, (x0, y0, x1, y1) in fixed.items():
        save(os.path.join(a.out, "crops", "fixed_" + name.split(" ")[0] + ".png"), cap[y0:y1, x0:x1])

    meta = {"date": datetime.date.today().isoformat(), "upscaler": "model" if have_model else "classical",
            "model": MODEL if have_model else None, "geo": gname, "tex_pak": tpak, "tiles": stems,
            "fit": {"homography": M.tolist(), "sx_px_per_unit_at_top_edge": sx, "strip_top_row": strip_top,
                    "loss": fun, "loss_affine_only": fun_affine,
                    "colour_gains": [list(map(float, g)) for g in gains], "mean_abs_err_1x_vs_capture_8bit": resid_fit,
                    "dash_pixels_replaced": int(keep.sum()), "occluder_pixels_kept": int(occl.sum())},
            "magnification_texels": {"ZDASH101_px_per_texel_1x": sx * 0.611 / 255, "ZDASH102_px_per_texel_1x": sx * 0.9324 / (0.9605 * 255)},
            "capture": a.capture}
    json.dump(meta, open(os.path.join(a.out, "mockup.json"), "w"), indent=1)
    meta["marker_preview"] = marker_ok
    write_html(a.out, meta, crops, fixed)
    print(json.dumps(meta, indent=1))


def write_html(out, meta, crops, fixed):
    up = ("U2 dash recipe: 4x-Manga109Attempt (CC-BY-4.0) x 4x_RRDB_PSNR (Apache-2.0), 50/50 weight interpolation, "
          "run at 4x; 2x = Lanczos downscale of the 4x") if meta["upscaler"] == "model" else \
        "classical Lanczos + luminance unsharp (model weights not found locally)"
    f = meta["fit"]
    m = meta["magnification_texels"]

    def row(label, items):
        cells = "".join(f'<figure><img src="{html.escape(src)}" loading="lazy"><figcaption>{html.escape(cap)}</figcaption></figure>'
                        for cap, src in items)
        return f'<section><h3>{html.escape(label)}</h3><div class="row">{cells}</div></section>'

    crop_rows = "".join(row(n, [(k, f"crops/{n.replace(' ', '_').replace('+', '')}_{k}.png") for k in ("1x", "2x", "4x", "2x-classical")])
                        for n in crops)
    fixed_row = row("Not changed by the tile split: painted gauge faces (from the same capture, 1:1)",
                    [(n, "crops/fixed_" + n.split(" ")[0] + ".png") for n in fixed])
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cockpit dash mock-up</title>
<style>
:root{{--bg:#f6f5f2;--fg:#1d1d1b;--muted:#5d5d58;--card:#fff;--line:#dcdad3}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#151514;--fg:#ecebe6;--muted:#a3a29b;--card:#1f1f1d;--line:#34332f}}}}
:root[data-theme="dark"]{{--bg:#151514;--fg:#ecebe6;--muted:#a3a29b;--card:#1f1f1d;--line:#34332f}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:16px;max-width:1800px}}
h1{{font-size:1.5rem;margin:.2em 0}} h2{{font-size:1.15rem;margin-top:2em;border-top:1px solid var(--line);padding-top:1em}}
h3{{font-size:1rem;margin:1.2em 0 .4em}} p,li{{max-width:75ch}} .muted{{color:var(--muted)}}
.row{{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);padding:6px;max-width:100%}}
figure img{{display:block;max-width:100%;image-rendering:auto}} figcaption{{font-size:.85rem;color:var(--muted);padding-top:4px}}
.stack figure{{width:100%}} .stack img{{width:100%}}
code{{font-size:.9em}}
</style></head><body>
<h1>Cockpit dash at 2x / 4x: what the tile split would buy</h1>
<p class="muted">Stage 0 of docs/research/COCKPIT-HIRES-FEASIBILITY.md, {meta['date']}. Piranha dash ({meta['geo']}, tiles {', '.join(meta['tiles'])} from {meta['tex_pak']}.pak).
Offline render, nothing run in game. Upscaler: {html.escape(up)}. Derived game art: local only, never commit.</p>
<ul>
<li><b>2x is what the Glide route can deliver</b> (four 256x128 quarter tiles per dash tile, no exe change). 4x is shown for reference: it would need 16 tiles per dash tile, the same geo trick twice.</li>
<li>In the stock F1 view only the top strip of the dash is on screen (about {1440 - f['strip_top_row']:.0f} of 1440 rows). The panel itself shows when you look down (head-look), section 2.</li>
<li>Magnification at 1x: about {m['ZDASH101_px_per_texel_1x']:.1f} screen pixels per texel on the speedo tile and {m['ZDASH102_px_per_texel_1x']:.1f} on the radio tile at 3440 wide. 2x halves that.</li>
<li>Not drawn: the speedo/tach needles (separate sub-objects, flat polygons - already sharp). Not changed by any Glide route: radar, weapons, damage, compass, gear, mirror (painted 8-bit faces), section 3.</li>
</ul>

<h2>1. In situ: the start-line cockpit (3440x1440, best-wide)</h2>
<p>The dash strip is re-rendered over the stock capture. The mapping was fitted to the capture (mean error of the 1x reproduction {f['mean_abs_err_1x_vs_capture_8bit']:.1f}/255 over {f['dash_pixels_replaced']:,} dash pixels; pixels the fit cannot explain, such as the PRND and gear plates in front of the dash, keep the capture).</p>
{row("Visible strip (1:1, right of the PRND plate)", [("stock capture", "insitu_strip_crop_capture.png"), ("1x re-render (fit check)", "insitu_strip_crop_1x.png"), ("2x", "insitu_strip_crop_2x.png"), ("4x", "insitu_strip_crop_4x.png")])}
<div class="stack">{row("Whole strip", [("stock capture", "insitu_strip_capture.png"), ("2x", "insitu_strip_2x.png")])}</div>
<div class="stack">{row("Full frame with the 2x strip", [("2x", "insitu_2x.png")])}</div>
{('<div class="stack">' + row("What the stage-2 marker boot (owner test 29) should show: the cockpit_split.py --marker build rendered the same way", [("marker2x-split, expected", "insitu_strip_marker.png")]) + '</div>') if meta.get("marker_preview") else ""}

<h2>2. Look-down: the dash panel front-on, at the in-game magnification</h2>
<p>Same horizontal scale as the fitted F1 view ({f['sx_px_per_unit_at_top_edge']:.0f} px per model unit at the visible top edge), square pixels, no perspective. Colours mapped to the capture with the same per-channel fit. Grey = no dash face.</p>
<div class="stack">{row("Whole panel", [("1x (stock texels)", "panel_1x.png"), ("2x", "panel_2x.png"), ("4x", "panel_4x.png")])}</div>
{crop_rows}

<h2>3. What stays soft</h2>
{fixed_row}

<h2>How this was made</h2>
<ul>
<li>Tiles decoded index-exact from the M16 pack (texel 0xFF drawn black: ZGLIDE converts it to ARGB1555 0x0000 and these faces have no colour key bit). Stored rows are bottom-up (v = 0 is the bottom of the panel), flipped here for viewing.</li>
<li>Faces drawn from the .geo with bilinear sampling and clamp, Glide's s = u x 255 convention, 2x2 supersampling (dgVoodoo renders 5160x2160 and scales to 3440x1440).</li>
<li>Fit: a plane homography from the dash panel to the screen, Nelder-Mead on the strip right of x = 2000 (affine start, loss {f['loss_affine_only']:.5f} -> {f['loss']:.5f} with perspective). Only the top ~12 % of the panel is visible, so the fit says nothing reliable about the lower panel's on-screen size; section 2 uses the top edge's horizontal scale. Known misfit: the right-hand knob tab leans in the capture and stands upright in the re-render (the perspective is not fully recovered), so compare texture sharpness, not exact edge positions.</li>
<li>Tool: <code>texture-lab/cockpit_mockup.py</code>; the 2x tiles it writes (tiles/*.png) feed <code>texture-lab/cockpit_split.py --png-dir</code>.</li>
</ul>
</body></html>"""
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page)


if __name__ == "__main__":
    main()
