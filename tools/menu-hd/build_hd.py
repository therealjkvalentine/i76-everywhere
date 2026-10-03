#!/usr/bin/env python3
r"""build_hd.py - HD art pipeline for the Interstate '76 shell (DATABASE.MW2), offline.

Input : an mw2db extraction (i76-map\data\fmt\mw2tool.py extract -> data\out\mw2db\ with manifest.json).
Output: tools\menu-hd\out\ (git-ignored: upscaled game art is game data and stays on this machine).

    python tools\menu-hd\build_hd.py check                          what is installed, which upscalers are usable
    python tools\menu-hd\build_hd.py build  [--scales 3] [--upscaler classical] [--tag NAME] [--kinds bg,sprites,fonts]
    python tools\menu-hd\build_hd.py contact --variants 3x 3x-realesrgan-x4plus ...
    python tools\menu-hd\build_hd.py blite  [--source dedither|hd:<variant dir>] [--dither none|fs]

build writes  out\<scale>x[-tag]\bg\<id>.png            true-colour background (id = MW2 item id, two hex digits)
              out\<scale>x[-tag]\sprites\<id>\<frame>.png  RGBA frame, canvas-sized, straight alpha, colour bled under the edge
              out\<scale>x[-tag]\fonts\<id>.png + .json  coverage sheet (white, alpha = ink) + metrics (stock widths x scale)
              out\<scale>x[-tag]\manifest.json           keyed by MW2 item id, with the source md5 of every member and file
blite writes  out\blite\DATABASE.MW2 (same-size 8-bit backgrounds on their original palettes, repacked with mw2tool.py)

Upscalers are pluggable (class Upscaler, registry UPSCALERS):
    classical                         palette-aware dedither -> Lanczos in linear light (de-ringed) -> edge-directed
                                      anti-stairstep pass -> mild unsharp. numpy + OpenCV only.
    realesrgan:<model>                realesrgan-ncnn-vulkan.exe (found via --realesrgan-exe, %I76_REALESRGAN%, PATH or
                                      C:\Games\_tools\realesrgan). Models: whatever .param/.bin pairs sit in its models\.
Fonts and sprite alpha never go through an image model: they use the mask scaler (EPX then contour smoothing).
Nothing here runs the game, downloads anything, or writes into a game folder.
"""
import os, sys, json, time, glob, hashlib, argparse, shutil, subprocess, tempfile

import numpy as np
import cv2
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_MAP = os.path.join(os.path.dirname(REPO), "i76-map")
DEFAULT_OUT = os.path.join(HERE, "out")
TRANSPARENT = 255
VERSION = "menu-hd/1"
REALESRGAN_HINTS = [r"C:\Games\_tools\realesrgan\realesrgan-ncnn-vulkan.exe"]


# ---- small helpers ---------------------------------------------------------------------------------------------
def md5_file(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def is_game_folder(d):
    try:
        names = {n.lower() for n in os.listdir(d)}
    except OSError:
        return False
    return bool(names & {"i76.exe", "i76shell.dll", "nitro.exe"})


def refuse_game_folder(out):
    d = os.path.abspath(out)
    while True:
        if is_game_folder(d):
            sys.exit("refusing to write under a game folder: %s" % d)
        up = os.path.dirname(d)
        if up == d:
            return
        d = up


def s2l(x):
    x = np.asarray(x, np.float32)
    return np.where(x <= 0.04045, x / 12.92, ((np.maximum(x, 0) + 0.055) / 1.055) ** 2.4).astype(np.float32)


def l2s(x):
    x = np.clip(np.asarray(x, np.float32), 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055).astype(np.float32)


def to_u8(x):
    return (np.clip(x, 0, 1) * 255 + 0.5).astype(np.uint8)


def load_p(path):
    """-> (index array HxW uint8, palette 256x3 float 0..1). The extraction is palettised; anything else is an error."""
    im = Image.open(path)
    if im.mode != "P":
        raise SystemExit("%s is not palettised (mode %s): run on an untouched mw2tool extraction" % (path, im.mode))
    pal = bytes(im.getpalette() or b"")[:768]
    pal = np.frombuffer(pal + bytes(768 - len(pal)), np.uint8).reshape(256, 3).astype(np.float32) / 255
    return np.array(im), pal


def item_key(e):
    return "%02x" % e["index"]


# ---- palette-aware dedither ------------------------------------------------------------------------------------
def palette_nn_dist(pal):
    """Per index: distance (sRGB units, 0..1) to the nearest OTHER distinct palette colour. This is the size of the
    quantiser's step around that colour, so it bounds how far a dithered pixel can sit from the colour it stands for."""
    u = np.unique(pal, axis=0)
    d = np.linalg.norm(pal[:, None, :] - u[None, :, :], axis=2)
    d[d < 1e-6] = np.inf
    return d.min(1).astype(np.float32)


def dedither(idx, pal, mask=None, k=2.2, clamp=1.0, radius=2, sigma=1.3):
    """Edge-preserving average whose range is set per pixel from the palette: a neighbour takes part only if it is
    within k quantiser steps of the centre (so dither partners blend, real edges do not), and the result may move at
    most `clamp` steps away from the stored colour. Done in sRGB space, where the 1997 quantiser diffused its error.
    mask (bool, True = opaque) keeps transparent sprite pixels out of the average."""
    rgb = pal[idx]
    H, W = idx.shape
    dn = np.clip(palette_nn_dist(pal)[idx], 3 / 255, 20 / 255)
    m = np.ones((H, W), np.float32) if mask is None else mask.astype(np.float32)
    r = radius
    prgb = np.pad(rgb, ((r, r), (r, r), (0, 0)), mode="reflect")
    pm = np.pad(m, r, mode="reflect")
    acc = np.zeros_like(rgb)
    ws = np.zeros((H, W), np.float32)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            q = prgb[r + dy:r + dy + H, r + dx:r + dx + W]
            d = np.linalg.norm(q - rgb, axis=2)
            w = np.exp(-(dx * dx + dy * dy) / (2 * sigma * sigma)) * np.exp(-(d / (k * dn)) ** 4) * pm[r + dy:r + dy + H, r + dx:r + dx + W]
            if dx == 0 and dy == 0:
                w = np.ones((H, W), np.float32)
            acc += w[..., None] * q
            ws += w
    out = acc / ws[..., None]
    delta = out - rgb
    n = np.linalg.norm(delta, axis=2)
    lim = clamp * dn
    f = np.minimum(1.0, lim / np.maximum(n, 1e-9))
    return (rgb + delta * f[..., None]).astype(np.float32)


# ---- classical upscale -----------------------------------------------------------------------------------------
def lanczos_linear(rgb, scale):
    """Lanczos (8x8 taps) in linear light, then clamped to the local range of the source so it cannot ring."""
    lin = s2l(rgb)
    h, w = lin.shape[:2]
    size = (w * scale, h * scale)
    up = cv2.resize(lin, size, interpolation=cv2.INTER_LANCZOS4)
    k = np.ones((3, 3), np.uint8)
    lo = cv2.resize(cv2.erode(lin, k), size, interpolation=cv2.INTER_LINEAR)
    hi = cv2.resize(cv2.dilate(lin, k), size, interpolation=cv2.INTER_LINEAR)
    return l2s(np.clip(up, lo, hi))


def edge_directed(img, scale, iters=2, strength=1.0):
    """Edge-directed anti-stairstep pass: a short line-integral blur along the local edge tangent (structure tensor),
    weighted by coherence so only clean edges (lettering, rules, outlines) are touched and texture is left alone.
    This is what removes the staircase a separable Lanczos leaves on diagonals; it adds no detail."""
    h, w = img.shape[:2]
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    n = max(1, scale)
    ts = np.arange(-n, n + 1, dtype=np.float32)
    gw = np.exp(-ts * ts / (2 * (0.6 * scale) ** 2))
    gw /= gw.sum()
    for _ in range(iters):
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        s = 0.8 * scale
        j11 = cv2.GaussianBlur(gx * gx, (0, 0), s)
        j12 = cv2.GaussianBlur(gx * gy, (0, 0), s)
        j22 = cv2.GaussianBlur(gy * gy, (0, 0), s)
        tr = j11 + j22
        root = np.sqrt((j11 - j22) ** 2 + 4 * j12 * j12)
        coh = (root / (tr + 1e-6)) ** 2
        mag = np.clip(tr / 0.01, 0, 1)                 # ignore near-flat areas where orientation is noise
        th = 0.5 * np.arctan2(2 * j12, j11 - j22) + np.pi / 2
        tx, ty = np.cos(th).astype(np.float32), np.sin(th).astype(np.float32)
        acc = np.zeros_like(img)
        for t, wt in zip(ts, gw):
            acc += wt * cv2.remap(img, xs + t * tx, ys + t * ty, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        a = (np.clip(coh * mag, 0, 1) * strength)[..., None]
        img = img * (1 - a) + acc * a
    return img.astype(np.float32)


def unsharp(img, scale, amount=0.35):
    b = cv2.GaussianBlur(img, (0, 0), 0.5 * scale)
    return np.clip(img + amount * (img - b), 0, 1).astype(np.float32)


# ---- the pluggable upscaler interface --------------------------------------------------------------------------
class Upscaler:
    """An upscaler turns a list of opaque sRGB float images (HxWx3, 0..1, already dedithered, sprites already bled
    into their transparent area) into the same images at exactly `scale` times the size. That is the whole contract:
    alpha, fonts, palettes, file naming and the manifest are handled outside. To add a model, subclass this, give it
    a `name`, and register a factory in UPSCALERS."""
    name = "?"

    def upscale(self, imgs, scale):
        raise NotImplementedError

    def describe(self):
        return self.name


class Classical(Upscaler):
    name = "classical"

    def __init__(self, edge=True, sharpen=0.35):
        self.edge, self.sharpen = edge, sharpen

    def upscale(self, imgs, scale):
        out = []
        for im in imgs:
            up = lanczos_linear(im, scale)
            if self.edge:
                up = edge_directed(up, scale)
            if self.sharpen:
                up = unsharp(up, scale, self.sharpen)
            out.append(up)
        return out

    def describe(self):
        return "classical (Lanczos4 linear-light, de-ring%s%s)" % (", edge-directed" if self.edge else "", ", unsharp %.2f" % self.sharpen if self.sharpen else "")


def find_realesrgan(explicit=None):
    cands = [explicit, os.environ.get("I76_REALESRGAN"), shutil.which("realesrgan-ncnn-vulkan")] + REALESRGAN_HINTS
    for c in cands:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def realesrgan_models(exe):
    d = os.path.join(os.path.dirname(exe), "models")
    return sorted({os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(d, "*.param"))})


class RealEsrganNcnn(Upscaler):
    """realesrgan-ncnn-vulkan.exe as a batch filter. x4 models run at 4x and are brought down to the requested scale
    with an area filter in linear light; the animevideov3 family has native x2/x3/x4 weights. Small images are padded
    by edge replication (the network needs context) and cropped back."""
    MINSIDE = 64

    def __init__(self, model="realesrgan-x4plus", exe=None):
        self.exe = find_realesrgan(exe)
        if not self.exe:
            raise SystemExit("realesrgan-ncnn-vulkan.exe not found (use --realesrgan-exe or set I76_REALESRGAN)")
        have = realesrgan_models(self.exe)
        self.model = model
        self.family = model
        if model not in have and not any(m.startswith(model + "-x") for m in have):
            raise SystemExit("model %s not in %s (have: %s)" % (model, os.path.dirname(self.exe), ", ".join(have)))
        self.native_any = any(m.startswith(model + "-x") for m in have)
        self.name = "realesrgan-" + model.replace("realesrgan-", "").replace("realesr-", "")

    def upscale(self, imgs, scale):
        native = scale if (self.native_any and scale in (2, 3, 4)) else 4
        tin = tempfile.mkdtemp(prefix="menuhd_in_")
        tout = tempfile.mkdtemp(prefix="menuhd_out_")
        try:
            pads = []
            for i, im in enumerate(imgs):
                h, w = im.shape[:2]
                ph, pw = max(0, self.MINSIDE - h), max(0, self.MINSIDE - w)
                t, l = ph // 2, pw // 2
                a = cv2.copyMakeBorder(to_u8(im), t, ph - t, l, pw - l, cv2.BORDER_REPLICATE)
                pads.append((t, l, h, w))
                Image.fromarray(a).save(os.path.join(tin, "%05d.png" % i))
            cmd = [self.exe, "-i", tin, "-o", tout, "-n", self.model, "-s", str(native), "-f", "png"]
            r = subprocess.run(cmd, cwd=os.path.dirname(self.exe), capture_output=True, text=True)
            out = []
            for i, (t, l, h, w) in enumerate(pads):
                p = os.path.join(tout, "%05d.png" % i)
                if not os.path.isfile(p):
                    raise SystemExit("realesrgan produced no output for image %d\n%s" % (i, r.stderr[-2000:]))
                a = np.asarray(Image.open(p).convert("RGB"), np.float32) / 255
                a = a[t * native:(t + h) * native, l * native:(l + w) * native]
                if native != scale:
                    a = l2s(cv2.resize(s2l(a), (w * scale, h * scale), interpolation=cv2.INTER_AREA))
                out.append(np.ascontiguousarray(a))
            return out
        finally:
            shutil.rmtree(tin, ignore_errors=True)
            shutil.rmtree(tout, ignore_errors=True)

    def describe(self):
        return "Real-ESRGAN ncnn-vulkan, model %s (%s)" % (self.model, self.exe)


def make_upscaler(spec, args):
    kind, _, model = spec.partition(":")
    if kind not in UPSCALERS:
        raise SystemExit("unknown upscaler %r (have: %s)" % (kind, ", ".join(UPSCALERS)))
    return UPSCALERS[kind](model, args)


UPSCALERS = {
    "classical": lambda model, a: Classical(edge=not a.no_edge, sharpen=a.sharpen),
    "realesrgan": lambda model, a: RealEsrganNcnn(model or "realesrgan-x4plus", a.realesrgan_exe),
}


# ---- mask scaler (fonts, sprite alpha) -------------------------------------------------------------------------
def epx(m, s):
    """Scale2x / Scale3x (AdvMAME) on a boolean mask: the edge-directed step that joins diagonal pixel chains."""
    if s == 4:
        return epx(epx(m, 2), 2)
    if s not in (2, 3):
        return np.repeat(np.repeat(m, s, 0), s, 1)
    p = np.pad(m, 1, mode="constant")
    H, W = m.shape
    sl = lambda dy, dx: p[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
    A, B, C = sl(-1, -1), sl(-1, 0), sl(-1, 1)
    D, E, F = sl(0, -1), m, sl(0, 1)
    G, Hh, I = sl(1, -1), sl(1, 0), sl(1, 1)
    ok = (B != Hh) & (D != F)
    out = np.empty((H * s, W * s), bool)
    if s == 2:
        out[0::2, 0::2] = np.where(ok & (D == B), D, E)
        out[0::2, 1::2] = np.where(ok & (B == F), F, E)
        out[1::2, 0::2] = np.where(ok & (D == Hh), D, E)
        out[1::2, 1::2] = np.where(ok & (Hh == F), F, E)
        return out
    out[0::3, 0::3] = np.where(ok & (D == B), D, E)
    out[0::3, 1::3] = np.where(ok & (((D == B) & (E != C)) | ((B == F) & (E != A))), B, E)
    out[0::3, 2::3] = np.where(ok & (B == F), F, E)
    out[1::3, 0::3] = np.where(ok & (((D == B) & (E != G)) | ((D == Hh) & (E != A))), D, E)
    out[1::3, 1::3] = E
    out[1::3, 2::3] = np.where(ok & (((B == F) & (E != I)) | ((Hh == F) & (E != C))), F, E)
    out[2::3, 0::3] = np.where(ok & (D == Hh), D, E)
    out[2::3, 1::3] = np.where(ok & (((D == Hh) & (E != I)) | ((Hh == F) & (E != G))), Hh, E)
    out[2::3, 2::3] = np.where(ok & (Hh == F), F, E)
    return out


def upscale_mask(cov, scale, binary, ss=4, blur=0.33, gain=None):
    """Coverage (HxW float 0..1) -> coverage at `scale`. Works on a supersampled grid: binary masks get EPX, a small
    blur and a threshold (a smooth contour through the pixel staircase); anti-aliased masks get a cubic upsample and a
    soft threshold that tightens the edge without deleting faint strokes. The result is area-averaged back, so its
    edges are anti-aliased."""
    H, W = cov.shape
    if binary:
        e = epx(cov > 0.5, scale).astype(np.float32)
        big = np.repeat(np.repeat(e, ss, 0), ss, 1)
        big = cv2.GaussianBlur(big, (0, 0), blur * scale * ss)
        big = np.clip((big - 0.5) * (gain or 12.0) + 0.5, 0, 1)
    else:
        big = cv2.resize(cov.astype(np.float32), (W * scale * ss, H * scale * ss), interpolation=cv2.INTER_CUBIC)
        big = np.clip(big, 0, 1)
        g = gain or 2.0
        big = np.clip((big - 0.4) * g + 0.4, 0, 1)
    return cv2.resize(big, (W * scale, H * scale), interpolation=cv2.INTER_AREA)


# ---- kinds -----------------------------------------------------------------------------------------------------
def build_backgrounds(src, man, scale, up, outdir, only, log):
    items = [e for e in man["members"] if e["type"] == "background" and (not only or item_key(e) in only)]
    os.makedirs(os.path.join(outdir, "bg"), exist_ok=True)
    t0 = time.time()
    pre = []
    for e in items:
        idx, pal = load_p(os.path.join(src, e["file"]))
        pre.append(dedither(idx, pal))
    t1 = time.time()
    ups = up.upscale(pre, scale)
    t2 = time.time()
    res = {}
    for e, a in zip(items, ups):
        rel = "bg/%s.png" % item_key(e)
        Image.fromarray(to_u8(a)).save(os.path.join(outdir, rel))
        res[e["id"]] = {"type": "background", "used_by": e.get("used_by"), "file": rel, "size": [a.shape[1], a.shape[0]],
                        "stock_size": [e["width"], e["height"]], "palette": e["palette"], "upscaler": up.describe(),
                        "source_member_md5": e["md5"], "source_file": e["file"], "source_file_md5": md5_file(os.path.join(src, e["file"])),
                        "md5": md5_file(os.path.join(outdir, rel))}
    t3 = time.time()
    log["backgrounds"] = {"count": len(items), "dedither_s": round(t1 - t0, 2), "upscale_s": round(t2 - t1, 2), "write_s": round(t3 - t2, 2),
                          "total_s": round(t3 - t0, 2)}
    return res


def bleed(rgb, mask):
    """Fill transparent pixels with the nearest opaque colour so no filter can pull a matte colour into the edge."""
    if mask.all() or not mask.any():
        return rgb
    _, (iy, ix) = ndimage.distance_transform_edt(~mask, return_indices=True)
    return rgb[iy, ix]


def sprite_alpha(mask, box, scale):
    """-> (alpha at scale, how). A frame that is a full opaque rectangle keeps a hard rectangle (it has to butt against
    the background it replaces); any other shape gets the smooth-contour mask scaler."""
    H, W = mask.shape
    if mask.all():
        return np.ones((H * scale, W * scale), np.float32), "opaque"
    x0, y0, x1, y1 = box
    rect = np.zeros_like(mask)
    rect[max(0, y0):y1 + 1, max(0, x0):x1 + 1] = True
    if (mask == rect).all():
        return np.repeat(np.repeat(mask.astype(np.float32), scale, 0), scale, 1), "rect"
    return upscale_mask(mask.astype(np.float32), scale, True), "contour"


def build_sprites(src, man, scale, up, outdir, only, log):
    items = [e for e in man["members"] if e["type"] == "shapes" and (not only or item_key(e) in only)]
    t0 = time.time()
    pre, meta = [], []
    for e in items:
        os.makedirs(os.path.join(outdir, "sprites", item_key(e)), exist_ok=True)
        for k, f in enumerate(e["frames"]):
            idx, pal = load_p(os.path.join(src, f["file"]))
            mask = idx != TRANSPARENT
            rgb = dedither(idx, pal, mask) if mask.any() else pal[idx]
            pre.append(bleed(rgb, mask))
            meta.append((e, k, f, mask))
    t1 = time.time()
    ups = up.upscale(pre, scale)
    t2 = time.time()
    res = {}
    for (e, k, f, mask), a in zip(meta, ups):
        alpha, how = sprite_alpha(mask, f["box"], scale)
        rgba = np.dstack([to_u8(a), to_u8(alpha)])
        rel = "sprites/%s/%03d.png" % (item_key(e), k)
        Image.fromarray(rgba, "RGBA").save(os.path.join(outdir, rel))
        it = res.setdefault(e["id"], {"type": "shapes", "used_by": e.get("used_by"), "palette": e["palette"], "upscaler": up.describe(),
                                      "source_member_md5": e["md5"], "frames": []})
        x0, y0, x1, y1 = f["box"]
        it["frames"].append({"frame": k, "file": rel, "canvas": [mask.shape[1] * scale, mask.shape[0] * scale],
                             "stock_canvas": f["canvas"], "box": [x0 * scale, y0 * scale, (x1 + 1) * scale - 1, (y1 + 1) * scale - 1],
                             "stock_box": f["box"], "alpha": how, "source_file": f["file"],
                             "source_file_md5": md5_file(os.path.join(src, f["file"])), "md5": md5_file(os.path.join(outdir, rel))})
    t3 = time.time()
    log["sprites"] = {"tables": len(items), "frames": len(meta), "dedither_bleed_s": round(t1 - t0, 2), "upscale_s": round(t2 - t1, 2),
                      "alpha_write_s": round(t3 - t2, 2), "total_s": round(t3 - t0, 2)}
    return res


def font_coverage(e, idx, pal):
    """-> (coverage HxW float, binary?, {index: coverage}). 1-bpp: bit = ink. One ink index: binary. Four or more ink
    indices: an anti-aliased face on the grey ramp, coverage = darkness normalised to the darkest index used. Two or
    three ink indices: a layered face (e.g. letter + drop shadow): coverage is the union and build_fonts colours it."""
    if e["bpp"] == 1:
        return (idx > 0).astype(np.float32), True, {1: 1.0}
    used = [int(i) for i in np.unique(idx) if i != TRANSPARENT]
    if len(used) <= 1:
        return (idx != TRANSPARENT).astype(np.float32), True, {i: 1.0 for i in used}
    if len(used) < 4:
        return (idx != TRANSPARENT).astype(np.float32), True, {i: 1.0 for i in used}
    luma = pal @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    dark = 1.0 - luma
    top = max(dark[i] for i in used) or 1.0
    table = np.zeros(256, np.float32)
    for i in used:
        table[i] = dark[i] / top
    return table[idx], False, {i: round(float(table[i]), 4) for i in used}


def build_fonts(src, man, scale, outdir, only, log):
    items = [e for e in man["members"] if e["type"] == "font" and (not only or item_key(e) in only)]
    os.makedirs(os.path.join(outdir, "fonts"), exist_ok=True)
    res = {}
    t0 = time.time()
    for e in items:
        idx, pal = load_p(os.path.join(src, e["file"]))
        met = json.load(open(os.path.join(src, e["metrics"]), encoding="utf-8"))
        cols = e["sheet"]["cols"]
        cw, ch = e["sheet"]["cell"]
        widths = met["widths"]
        cov, binary, ink = font_coverage(e, idx, pal)
        rows = (len(widths) + cols - 1) // cols
        G = 1                                           # gutter, stock pixels, on every side of every cell
        pw, ph = cw + 2 * G, ch + 2 * G
        sheet = np.zeros((rows * ph * scale, cols * pw * scale), np.float32)
        layered = binary and len(ink) > 1
        layer_ids = sorted(ink) if layered else []
        lsheets = [np.zeros_like(sheet) for _ in layer_ids]
        for r in range(rows):                           # one glyph row at a time: the gutters isolate glyphs
            strip = np.zeros((ph, cols * pw), np.float32)
            for c in range(cols):
                g = r * cols + c
                if g < len(widths) and widths[g]:
                    w = min(widths[g], cw)
                    strip[G:G + ch, c * pw + G:c * pw + G + w] = cov[r * ch:(r + 1) * ch, c * cw:c * cw + w]
            if strip.any():
                sheet[r * ph * scale:(r + 1) * ph * scale] = upscale_mask(strip, scale, binary)
                for li, lid in enumerate(layer_ids):   # the same strip, one ink index at a time
                    ls = np.zeros_like(strip)
                    for c in range(cols):
                        g = r * cols + c
                        if g < len(widths) and widths[g]:
                            w = min(widths[g], cw)
                            ls[G:G + ch, c * pw + G:c * pw + G + w] = idx[r * ch:(r + 1) * ch, c * cw:c * cw + w] == lid
                    lsheets[li][r * ph * scale:(r + 1) * ph * scale] = upscale_mask(ls, scale, True)
        a = to_u8(sheet)
        if layered:                                     # colour = the layers' stock palette colours, mixed by coverage
            wsum = np.maximum(sum(lsheets), 1e-6)
            lin = sum(l[..., None] * s2l(pal[lid])[None, None, :] for l, lid in zip(lsheets, layer_ids)) / wsum[..., None]
            rgb = to_u8(l2s(lin))
            rgb[sum(lsheets) < 1e-3] = to_u8(pal[layer_ids[-1]])
            rgba = np.dstack([rgb, a])
        else:
            rgba = np.dstack([np.full_like(a, 255)] * 3 + [a])
        rel = "fonts/%s.png" % item_key(e)
        Image.fromarray(rgba, "RGBA").save(os.path.join(outdir, rel))
        glyphs = {}
        for g, w in enumerate(widths):
            if w:
                r, c = divmod(g, cols)
                glyphs[str(g)] = {"x": (c * pw + G) * scale, "y": (r * ph + G) * scale, "w": w * scale, "h": ch * scale,
                                  "advance": w * scale, "stock_width": w}
        mj = {"format": "i76-menu-hd-font/1", "id": e["id"], "scale": scale, "height": met["height"] * scale, "stock_height": met["height"],
              "sheet": rel, "sheet_size": [sheet.shape[1], sheet.shape[0]], "gutter": G * scale, "cell": [pw * scale, ph * scale], "cols": cols,
              "glyph_count": len(widths), "bpp": e["bpp"], "antialiased_source": not binary, "layered": layered,
              "layer_colours": {str(l): to_u8(pal[l]).tolist() for l in layer_ids}, "ink_indices": {str(k): v for k, v in ink.items()},
              "note": "Sheet is white with alpha = ink coverage (tint it as the shell's colour map would); a layered face carries its "
                      "stock palette colours instead. advance = stock glyph width x scale. The stock font member stores a width per glyph and nothing else; "
                      "any inter-glyph spacing is added by the shell's own text code, so an HD renderer multiplies that by scale too. "
                      "Glyph rects may be sampled with their gutter: ink never leaves the rect by more than the gutter.",
              "glyphs": glyphs}
        relj = "fonts/%s.json" % item_key(e)
        json.dump(mj, open(os.path.join(outdir, relj), "w", encoding="utf-8", newline="\n"))
        res[e["id"]] = {"type": "font", "used_by": e.get("used_by"), "file": rel, "metrics": relj, "glyphs": len(glyphs),
                        "stock_height": met["height"], "height": met["height"] * scale, "method": "mask scaler (%s)" % ("EPX + contour" if binary else "cubic + soft threshold"),
                        "source_member_md5": e["md5"], "source_file": e["file"], "source_file_md5": md5_file(os.path.join(src, e["file"])),
                        "md5": md5_file(os.path.join(outdir, rel))}
    log["fonts"] = {"count": len(items), "glyphs": sum(v["glyphs"] for v in res.values()), "total_s": round(time.time() - t0, 2)}
    return res


def load_manifest(a):
    src = os.path.abspath(a.src)
    p = os.path.join(src, "manifest.json")
    if not os.path.isfile(p):
        sys.exit("no manifest.json in %s: run  python %s extract <DATABASE.MW2> %s" % (src, os.path.join(a.i76_map, "data", "fmt", "mw2tool.py"), src))
    return src, json.load(open(p, encoding="utf-8")), md5_file(p)


def cmd_build(a):
    src, man, man_md5 = load_manifest(a)
    refuse_game_folder(a.out)
    kinds = set(a.kinds.split(","))
    only = set(x.lower().replace("0x", "").zfill(2) for x in a.only.split(",")) if a.only else None
    up = make_upscaler(a.upscaler, a)
    for scale in a.scales:
        name = "%dx" % scale + ("-" + a.tag if a.tag else "")
        outdir = os.path.join(a.out, name)
        os.makedirs(outdir, exist_ok=True)
        mp = os.path.join(outdir, "manifest.json")
        out = json.load(open(mp, encoding="utf-8")) if os.path.isfile(mp) else {}
        out.update({"format": "i76-menu-hd-manifest/1", "tool": VERSION, "scale": scale, "variant": name,
                    "source": {"extraction": src, "manifest_md5": man_md5, "database": man["source"]}})
        items = out.setdefault("items", {})
        log = out.setdefault("timings", {})
        t0 = time.time()
        if "bg" in kinds:
            items.update(build_backgrounds(src, man, scale, up, outdir, only, log))
        if "sprites" in kinds:
            items.update(build_sprites(src, man, scale, up, outdir, only, log))
        if "fonts" in kinds:
            items.update(build_fonts(src, man, scale, outdir, only, log))
        out["items"] = dict(sorted(items.items()))
        json.dump(out, open(mp, "w", encoding="utf-8", newline="\n"), indent=1)
        print("%s: %s  [%s]  %.1f s" % (name, ", ".join("%s %s" % (k, json.dumps(v)) for k, v in log.items() if k in
                                                         {"bg": "backgrounds", "sprites": "sprites", "fonts": "fonts"}.values()), up.describe(), time.time() - t0))
        print("  -> %s" % outdir)
    return 0


# ---- contact sheets --------------------------------------------------------------------------------------------
BG_CROPS = {"01": (372, 6), "04": (222, 48), "10": (26, 36), "0f": (150, 140), "06": (180, 20), "1a": (150, 70), "0e": (40, 140),
            "1b": (140, 300), "02": (372, 0), "12": (250, 0), "1d": (20, 20), "1c": (0, 20)}
BG_SHEETS = {"bg_forms": ["01", "04", "10", "0f"], "bg_art": ["06", "1a", "0e", "1b"]}
SPRITE_PICKS = [("3e", 0), ("3e", 4), ("24", 0), ("25", 0), ("29", 1), ("3d", 0), ("40", 0), ("3c", 0), ("31", 0), ("3b", 2), ("21", 0), ("35", 3)]
FONT_LINES = ["THE QUICK BROWN FOX 0123456789", "Jumps over the lazy dog (C) $1,250"]
CW, CH = 160, 120


def checker(h, w, s=12):
    y, x = np.mgrid[0:h, 0:w]
    c = (((x // s) + (y // s)) % 2).astype(np.float32)
    return np.dstack([0.55 + 0.15 * c] * 3)


def over(rgba, bg):
    a = rgba[..., 3:4].astype(np.float32) / 255
    return to_u8(l2s(s2l(rgba[..., :3].astype(np.float32) / 255) * a + s2l(bg) * (1 - a)))


def fit(img, w, h, fill=40):
    out = np.full((h, w, 3), fill, np.uint8)
    out[:min(h, img.shape[0]), :min(w, img.shape[1])] = img[:h, :w]
    return out


def sheet(path, title, cols, rows):
    """rows: [(label, [tile, ...])], every tile the same size."""
    th, tw = rows[0][1][0].shape[:2]
    pad, head = 6, 22
    W = pad + len(cols) * (tw + pad)
    H = head * 2 + len(rows) * (th + head + pad)
    im = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(im)
    d.text((pad, 4), title, fill=(255, 255, 255))
    for c, name in enumerate(cols):
        d.text((pad + c * (tw + pad), head + 4), name, fill=(255, 220, 120))
    y = head * 2
    for label, tiles in rows:
        d.text((pad, y + 4), label, fill=(200, 200, 200))
        for c, t in enumerate(tiles):
            im.paste(Image.fromarray(t), (pad + c * (tw + pad), y + head))
        y += th + head + pad
    im.save(path)
    print("contact sheet: %s (%dx%d)" % (path, W, H))


def cmd_contact(a):
    src, man, _ = load_manifest(a)
    by = {item_key(e): e for e in man["members"]}
    vdirs = [os.path.join(a.out, v) for v in a.variants]
    vman = [json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8")) for d in vdirs]
    scale = vman[0]["scale"]
    if any(m["scale"] != scale for m in vman):
        sys.exit("variants differ in scale")
    cdir = os.path.join(a.out, "contact")
    os.makedirs(cdir, exist_ok=True)
    nn = lambda x: np.repeat(np.repeat(x, scale, 0), scale, 1)
    cols = ["stock, nearest x%d" % scale] + list(a.variants)
    tw, th = CW * scale, CH * scale
    for name, ids in BG_SHEETS.items():
        rows = []
        for k in ids:
            e = by[k]
            x, y = BG_CROPS.get(k, (0, 0))
            st = np.asarray(Image.open(os.path.join(src, e["file"])).convert("RGB"))[y:y + CH, x:x + CW]
            tiles = [fit(nn(st), tw, th)]
            for d in vdirs:
                p = os.path.join(d, "bg", k + ".png")
                tiles.append(fit(np.asarray(Image.open(p).convert("RGB"))[y * scale:(y + CH) * scale, x * scale:(x + CW) * scale], tw, th)
                             if os.path.isfile(p) else np.zeros((th, tw, 3), np.uint8))
            rows.append(("0x%s  %s  (crop %d,%d %dx%d)" % (k, e.get("used_by") or "", x, y, CW, CH), tiles))
        sheet(os.path.join(cdir, "%s_%dx.png" % (name, scale)), "I'76 shell backgrounds, %dx: stock vs upscalers" % scale, cols, rows)
    rows = []
    for k, fr in SPRITE_PICKS:
        e = by.get(k)
        if not e or fr >= len(e["frames"]):
            continue
        f = e["frames"][fr]
        x0, y0 = max(0, f["box"][0]), max(0, f["box"][1])
        im = Image.open(os.path.join(src, f["file"]))
        idx = np.array(im)
        rgba = np.dstack([np.asarray(im.convert("RGB")), np.where(idx == TRANSPARENT, 0, 255).astype(np.uint8)])[y0:y0 + CH, x0:x0 + CW]
        bg = checker(th, tw)
        tiles = [fit(over(nn(rgba), bg[:rgba.shape[0] * scale, :rgba.shape[1] * scale]), tw, th)]
        for d in vdirs:
            p = os.path.join(d, "sprites", k, "%03d.png" % fr)
            if os.path.isfile(p):
                hd = np.asarray(Image.open(p).convert("RGBA"))[y0 * scale:(y0 + CH) * scale, x0 * scale:(x0 + CW) * scale]
                tiles.append(fit(over(hd, bg[:hd.shape[0], :hd.shape[1]]), tw, th))
            else:
                tiles.append(np.zeros((th, tw, 3), np.uint8))
        rows.append(("0x%s frame %d  %s" % (k, fr, e.get("used_by") or ""), tiles))
    for i in range(0, len(rows), 6):
        sheet(os.path.join(cdir, "sprites_%dx_%d.png" % (scale, i // 6 + 1)), "I'76 shell sprites on a checker, %dx: stock vs upscalers" % scale, cols, rows[i:i + 6])
    # fonts: typeset two lines with the stock sheet (nearest) and with the HD sheet + its metrics
    fdir = next((d for d in vdirs if os.path.isdir(os.path.join(d, "fonts"))), None)
    if fdir:
        rows = []
        FW = 300
        for e in [m for m in man["members"] if m["type"] == "font" and m["bpp"] == 8]:
            k = item_key(e)
            mj = json.load(open(os.path.join(fdir, "fonts", k + ".json"), encoding="utf-8"))
            hdim = np.asarray(Image.open(os.path.join(fdir, "fonts", k + ".png"))).astype(np.float32) / 255
            hd = hdim if mj.get("layered") else hdim[..., 3]
            idx, pal = load_p(os.path.join(src, e["file"]))
            cov, _, _ = font_coverage(e, idx, pal)
            if mj.get("layered"):
                cov = np.dstack([pal[idx], cov])
            cw, ch = e["sheet"]["cell"]
            widths = json.load(open(os.path.join(src, e["metrics"]), encoding="utf-8"))["widths"]
            lh = ch + 3
            a0 = np.zeros((lh * len(FONT_LINES) + 3, FW) + cov.shape[2:], np.float32)
            a1 = np.zeros((a0.shape[0] * scale, FW * scale) + cov.shape[2:], np.float32)
            for li, line in enumerate(FONT_LINES):
                x = 3
                for chh in line:
                    g = ord(chh)
                    w = widths[g] if g < len(widths) else 0
                    if not w:
                        g = 32
                        w = widths[32] or 4
                    if x + w >= FW:
                        break
                    r, c = divmod(g, e["sheet"]["cols"])
                    y = 3 + li * lh
                    if widths[g]:
                        a0[y:y + ch, x:x + w] = np.maximum(a0[y:y + ch, x:x + w], cov[r * ch:(r + 1) * ch, c * cw:c * cw + w])
                        gm = mj["glyphs"][str(g)]
                        blk = hd[gm["y"]:gm["y"] + gm["h"], gm["x"]:gm["x"] + gm["w"]]
                        a1[y * scale:y * scale + gm["h"], x * scale:x * scale + gm["w"]] = np.maximum(a1[y * scale:y * scale + gm["h"], x * scale:x * scale + gm["w"]], blk)
                    x += w
            paper, ink = np.array([0.93, 0.72, 0.33], np.float32), np.array([0.12, 0.07, 0.03], np.float32)
            comp = lambda al: (to_u8(l2s(s2l(paper) * (1 - al[..., 3:]) + s2l(al[..., :3]) * al[..., 3:])) if al.ndim == 3 else
                               to_u8(l2s(s2l(paper) * (1 - al[..., None]) + s2l(ink) * al[..., None])))
            rows.append(("0x%s  %s  (height %d -> %d, stock advance widths x%d)" % (k, e.get("used_by") or "", ch, ch * scale, scale), [comp(nn(a0)), comp(a1)]))
        sheet(os.path.join(cdir, "fonts_%dx.png" % scale), "I'76 shell fonts typeset from the sheets + metrics, %dx" % scale,
              ["stock glyphs, nearest x%d" % scale, "HD sheet (%s)" % os.path.basename(fdir)], rows)
    return 0


# ---- B-lite: same-size 8-bit backgrounds on their original palettes, repacked ------------------------------------
def quantise(rgb, pal, allowed, dither):
    """rgb HxWx3 float sRGB -> index image using only `allowed` palette indices. Nearest colour in CIE Lab."""
    allowed = np.array(sorted(allowed))
    lab = lambda x: cv2.cvtColor(np.ascontiguousarray(x, np.float32).reshape(-1, 1, 3), cv2.COLOR_RGB2Lab).reshape(-1, 3)
    if dither == "fs":
        pim = Image.new("P", (1, 1))
        sub = to_u8(pal[allowed])
        full = np.concatenate([sub, np.repeat(sub[:1], 256 - len(sub), 0)])
        pim.putpalette(full.tobytes())
        q = np.array(Image.fromarray(to_u8(rgb)).quantize(palette=pim, dither=Image.Dither.FLOYDSTEINBERG))
        q[q >= len(allowed)] = 0
        return allowed[q].astype(np.uint8)
    tree = cKDTree(lab(pal[allowed]))
    _, j = tree.query(lab(rgb.reshape(-1, 3)))
    return allowed[j].reshape(rgb.shape[:2]).astype(np.uint8)


def cmd_blite(a):
    src, man, _ = load_manifest(a)
    refuse_game_folder(a.out)
    tool = os.path.join(a.i76_map, "data", "fmt", "mw2tool.py")
    if not os.path.isfile(tool):
        sys.exit("mw2tool.py not found at %s (--i76-map)" % tool)
    bdir = os.path.join(a.out, "blite")
    work = os.path.join(bdir, "work")
    if os.path.isdir(work):
        shutil.rmtree(work)
    shutil.copytree(src, work, ignore=shutil.ignore_patterns("DATABASE.MW2", "*.tmp"))
    only = set(x.lower().replace("0x", "").zfill(2) for x in a.only.split(",")) if a.only else None
    t0 = time.time()
    report = {}
    written = {}
    for e in man["members"]:
        if e["type"] != "background" or (only and item_key(e) not in only):
            continue
        idx, pal = load_p(os.path.join(src, e["file"]))
        if a.source == "dedither":
            rgb = dedither(idx, pal)
        else:
            p = os.path.join(a.out, a.source.split(":", 1)[1], "bg", item_key(e) + ".png")
            hd = np.asarray(Image.open(p).convert("RGB"), np.float32) / 255
            rgb = l2s(cv2.resize(s2l(hd), (idx.shape[1], idx.shape[0]), interpolation=cv2.INTER_AREA))
        allowed = range(256) if a.all_indices else np.unique(idx).tolist()
        q = quantise(rgb, pal, allowed, a.dither)
        im = Image.fromarray(q, "P")
        im.putpalette(to_u8(pal).tobytes())
        im.save(os.path.join(work, e["file"]), optimize=False)
        written[e["index"]] = q
        flat = lambda x: float((x[:, 1:] != x[:, :-1]).mean())
        report[e["id"]] = {"pixels_changed": round(float((q != idx).mean()), 4), "indices_before": int(len(np.unique(idx))),
                           "indices_after": int(len(np.unique(q))), "h_neighbour_change_before": round(flat(idx), 4),
                           "h_neighbour_change_after": round(flat(q), 4)}
    out_db = os.path.join(bdir, "DATABASE.MW2")
    r = subprocess.run([sys.executable, tool, "repack", os.path.join(work, "manifest.json"), out_db], capture_output=True, text=True)
    print(r.stdout.strip()[-1500:])
    if not os.path.isfile(out_db):
        sys.exit("repack failed:\n" + r.stderr)
    # verify the write landed: parse the new database with the format library and compare every member
    sys.path.insert(0, os.path.dirname(tool))
    import mw2db
    data = open(out_db, "rb").read()
    _, blobs, _ = mw2db.split(data)
    bad = []
    for e, b in zip(man["members"], blobs):
        if e["index"] in written:
            m = mw2db.member_parse(b)
            got = np.frombuffer(b"".join(m.rows), np.uint8).reshape(m.height, m.width)
            if not (got == written[e["index"]]).all() or m.palette != to_u8(load_p(os.path.join(src, e["file"]))[1]).tobytes():
                bad.append(e["id"])
            report[e["id"]]["packed_size"] = [e["size"], len(b)]
        elif hashlib.md5(b).hexdigest() != e["md5"]:
            bad.append(e["id"])
    summary = {"format": "i76-menu-hd-blite/1", "database": out_db, "size": len(data), "md5": hashlib.md5(data).hexdigest(),
               "source_database": man["source"], "source": a.source, "dither": a.dither, "all_indices": bool(a.all_indices),
               "members": len(blobs), "backgrounds_rewritten": len(written), "verify": "FAIL: " + ",".join(bad) if bad else
               "ok: %d rewritten backgrounds decode to the written indices on their original palettes; %d other members byte-identical" % (len(written), len(blobs) - len(written)),
               "seconds": round(time.time() - t0, 2), "items": report}
    json.dump(summary, open(os.path.join(bdir, "blite.json"), "w", encoding="utf-8", newline="\n"), indent=1)
    print("B-lite: %s  %d bytes  md5 %s  (%.1f s)\nverify: %s" % (out_db, len(data), summary["md5"], summary["seconds"], summary["verify"]))
    return 1 if bad else 0


# ---- check -----------------------------------------------------------------------------------------------------
def cmd_check(a):
    import importlib
    print("python %s" % sys.version.split()[0])
    for m in ["PIL", "numpy", "cv2", "scipy", "skimage", "onnxruntime", "torch", "realesrgan", "basicsr", "ncnn"]:
        try:
            x = importlib.import_module(m)
            print("  %-12s %s" % (m, getattr(x, "__version__", "present")))
        except Exception:
            print("  %-12s missing" % m)
    exe = find_realesrgan(a.realesrgan_exe)
    print("realesrgan-ncnn-vulkan: %s" % (exe or "not found"))
    if exe:
        print("  models: %s" % ", ".join(realesrgan_models(exe)))
    print("upscalers usable now: classical" + ("".join(", realesrgan:" + m for m in sorted({m.split("-x")[0] if "animevideo" in m else m for m in realesrgan_models(exe)})) if exe else ""))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--i76-map", default=DEFAULT_MAP, help="the i76-map repo (for mw2tool.py and the default --src)")
    ap.add_argument("--src", default=None, help="mw2db extraction folder (default <i76-map>\\data\\out\\mw2db)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--realesrgan-exe", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("build"); p.set_defaults(fn=cmd_build)
    p.add_argument("--scales", type=int, nargs="+", default=[2, 3])
    p.add_argument("--upscaler", default="classical", help="classical | realesrgan:<model>")
    p.add_argument("--tag", default="", help="suffix of the output folder: out\\<scale>x-<tag>")
    p.add_argument("--kinds", default="bg,sprites,fonts")
    p.add_argument("--only", default="", help="comma list of item ids (hex) to limit the run")
    p.add_argument("--no-edge", action="store_true", help="classical: skip the edge-directed pass")
    p.add_argument("--sharpen", type=float, default=0.35, help="classical: unsharp amount (0 = off)")
    p = sub.add_parser("contact"); p.set_defaults(fn=cmd_contact)
    p.add_argument("--variants", nargs="+", required=True, help="output folders under --out to compare, e.g. 3x 3x-realesrgan-x4plus")
    p = sub.add_parser("blite"); p.set_defaults(fn=cmd_blite)
    p.add_argument("--source", default="dedither", help="dedither | hd:<variant folder under --out> (downsampled to stock size)")
    p.add_argument("--dither", default="none", choices=["none", "fs"])
    p.add_argument("--all-indices", action="store_true", help="allow every palette index (default: only those the stock background uses)")
    p.add_argument("--only", default="")
    a = ap.parse_args()
    a.i76_map = os.path.abspath(a.i76_map)
    a.src = a.src or os.path.join(a.i76_map, "data", "out", "mw2db")
    a.out = os.path.abspath(a.out)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
