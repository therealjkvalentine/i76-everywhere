"""Pre/post-processing library for the I'76 texture-upscaling experiments (sprint 2026-10-03, agent U3).

Pure numpy/scipy/Pillow; no torch. Model inference lives in the harness (tools/upscale), this module only
prepares inputs for it and cleans up what comes back. Every function takes and returns numpy arrays:

    rgb   float32 HxWx3 in [0,1]      (load_rgb / save_rgb convert from/to 8-bit PNG)
    mask  bool HxW, True = opaque     (I'76 decodes colour index 0xFF as transparent, RGB 0,0,0)
    alpha float32 HxW in [0,1]        (a soft mask, e.g. a resized or model-upscaled one)

Contents
  bleed                 edge dilation of opaque colours into transparent pixels (halo prevention)
  resize, upscale_alpha_threshold, alpha_from_model, alpha_regenerate, key_fill
  dedither_prepass      MrFlibble's xBRZ 4x -> Gaussian 0.5 px -> sinc downscale; xBRZ is replaced by
                        Scale4x (EPX/AdvMAME, = Scale2x twice) because the only xBRZ package on PyPI
                        (xbrz.py) is sdist-only C++ and this machine has no compiler on PATH. Scale4x is
                        the same family (pattern-based, palette-exact, hard-edged); xBRZ additionally
                        anti-aliases its diagonals, which the 0.5 px blur partly stands in for.
  kuwahara              Kuwahara (4-quadrant, the Kuwahara-Nagao family) edge-preserving light denoise
  histogram_match, lut3d_fit / lut3d_apply / lut3d_match   colour match back to the original
  srgb_to_lab, delta_e2000, mean_delta_e
  palette_from_image, widen_palette, palette_lock
  halo_metrics, laplacian_variance
  contact_sheet         labelled grid for eyeballing (composited over a backdrop that shows halos)
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

# ----------------------------------------------------------------------------------------------- I/O

def load_rgb(path):
    im = Image.open(path)
    if im.mode == "RGBA":
        a = np.asarray(im, dtype=np.float32) / 255.0
        return a[..., :3].copy()
    return np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0


def load_rgba(path):
    """-> (rgb, alpha) from an RGBA png (alpha 1.0 if the file has none)."""
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im, dtype=np.float32) / 255.0
    return a[..., :3].copy(), a[..., 3].copy()


def load_mask(path, thr=0.5):
    """Mask PNG (white = opaque) -> bool. Accepts L, RGB or RGBA (uses the alpha if the image has a real one)."""
    im = Image.open(path)
    if im.mode in ("RGBA", "LA"):
        a = np.asarray(im.getchannel("A"), dtype=np.float32) / 255.0
        if a.min() < 1.0:
            return a >= thr
    return (np.asarray(im.convert("L"), dtype=np.float32) / 255.0) >= thr


def to_u8(x):
    return np.clip(np.rint(np.asarray(x, dtype=np.float32) * 255.0), 0, 255).astype(np.uint8)


def save_rgb(path, rgb):
    Image.fromarray(to_u8(rgb), "RGB").save(path)


def save_rgba(path, rgb, alpha):
    a = np.asarray(alpha, dtype=np.float32)
    Image.fromarray(np.dstack([to_u8(rgb), to_u8(a)]), "RGBA").save(path)


def save_mask(path, mask):
    Image.fromarray(to_u8(np.asarray(mask, dtype=np.float32)), "L").save(path)


# -------------------------------------------------------------------------------------------- resize

_FILTERS = {
    "nearest": Image.NEAREST, "bilinear": Image.BILINEAR, "bicubic": Image.BICUBIC,
    "lanczos": Image.LANCZOS, "sinc": Image.LANCZOS, "box": Image.BOX, "area": Image.BOX,
    "hamming": Image.HAMMING,
}


def resize(img, w, h, method="lanczos"):
    """Float-precision resize (per channel through PIL mode 'F'; no 8-bit rounding in between).
    Lanczos/bicubic can overshoot; the result is clipped to [0,1]."""
    f = _FILTERS[method]
    a = np.asarray(img, dtype=np.float32)
    if a.ndim == 2:
        out = np.asarray(Image.fromarray(a, "F").resize((w, h), f), dtype=np.float32)
    else:
        out = np.dstack([np.asarray(Image.fromarray(np.ascontiguousarray(a[..., c]), "F").resize((w, h), f),
                                    dtype=np.float32) for c in range(a.shape[2])])
    return np.clip(out, 0.0, 1.0)


def rescale(img, factor, method="lanczos"):
    h, w = img.shape[:2]
    return resize(img, max(1, int(round(w * factor))), max(1, int(round(h * factor))), method)


# --------------------------------------------------------------------------------------------- alpha

_N8 = np.ones((3, 3), bool)


def bleed(rgb, mask, px=4, rest="nearest"):
    """Dilate opaque colours into transparent pixels, `px` rings (8-connected), each ring pixel taking the
    mean of its already-filled neighbours (so colours blend at concave corners, like Photoshop's 'solidify').
    Pixels farther than `px` from any opaque pixel are filled per `rest`:
        'nearest'  colour of the nearest opaque pixel (whole background filled, no hard step anywhere)
        'mean'     the mean opaque colour
        'keep'     left as they were (the decoder's black)
    Opaque pixels are never changed. mask: bool, True = opaque."""
    rgb = np.asarray(rgb, dtype=np.float32).copy()
    filled = np.asarray(mask, bool).copy()
    if filled.all() or not filled.any():
        return rgb
    for _ in range(int(px)):
        ring = ndi.binary_dilation(filled, _N8) & ~filled
        if not ring.any():
            break
        w = filled.astype(np.float32)
        cnt = ndi.convolve(w, _N8.astype(np.float32), mode="nearest")
        for c in range(3):
            s = ndi.convolve(rgb[..., c] * w, _N8.astype(np.float32), mode="nearest")
            rgb[..., c][ring] = s[ring] / np.maximum(cnt[ring], 1e-6)
        filled |= ring
    if rest == "nearest" and not filled.all():
        _, (iy, ix) = ndi.distance_transform_edt(~filled, return_indices=True)
        rgb = rgb[iy, ix]
    elif rest == "mean" and not filled.all():
        rgb[~filled] = rgb[np.asarray(mask, bool)].mean(axis=0)
    return rgb


def key_fill(rgb, mask, key=(1.0, 0.0, 1.0)):
    """Paint transparent pixels with a key colour (magenta by default) - input for alpha_regenerate."""
    out = np.asarray(rgb, dtype=np.float32).copy()
    out[~np.asarray(mask, bool)] = key
    return out


def upscale_alpha_threshold(mask, w, h, method="bilinear", thr=0.5):
    """Separate-alpha path without a model: resize the binary mask with a smooth filter, then threshold."""
    return resize(np.asarray(mask, np.float32), w, h, method) >= thr


def alpha_from_model(model_out, thr=0.5):
    """Threshold a model-upscaled mask (RGB or L output of e.g. HDcube-Alpha run on the mask image)."""
    a = np.asarray(model_out, dtype=np.float32)
    if a.ndim == 3:
        a = a.mean(axis=2)
    return a >= thr


def palette_index(rgb, palette, space="lab", chunk=65536):
    """Index of the nearest palette colour for each pixel (no dither). palette: Kx3 float in [0,1]."""
    px = np.asarray(rgb, np.float32).reshape(-1, 3)
    pal = np.asarray(palette, np.float32).reshape(-1, 3)
    if space == "lab":
        px_s, pal_s = srgb_to_lab(px), srgb_to_lab(pal)
    else:
        px_s, pal_s = px, pal
    out = np.empty(len(px_s), np.int32)
    p2 = (pal_s ** 2).sum(1)
    for i in range(0, len(px_s), chunk):
        x = px_s[i:i + chunk]
        d = (x ** 2).sum(1)[:, None] - 2.0 * x @ pal_s.T + p2[None, :]
        out[i:i + chunk] = d.argmin(1)
    return out.reshape(np.asarray(rgb).shape[:2])


def alpha_regenerate(rgb_up_keyed, palette, key=(1.0, 0.0, 1.0), kuwahara_radius=1, grow=1):
    """MrFlibble's mask regeneration from an upscaled colour-keyed image:
    Kuwahara-Nagao blur -> palettize to (source palette + key) -> select pixels that map to the key ->
    grow that background selection by `grow` px (cuts the key-contaminated fringe) -> mask = not background.
    rgb_up_keyed: model output of key_fill(rgb, mask). Returns bool mask (True = opaque)."""
    x = kuwahara(rgb_up_keyed, kuwahara_radius) if kuwahara_radius > 0 else np.asarray(rgb_up_keyed, np.float32)
    pal = np.vstack([np.asarray(palette, np.float32).reshape(-1, 3), np.asarray(key, np.float32)[None]])
    bg = palette_index(x, pal, "rgb") == len(pal) - 1
    if grow > 0:
        bg = ndi.binary_dilation(bg, _N8, iterations=int(grow))
    return ~bg


# --------------------------------------------------------------------------------------------- dither

def _scale2x(img):
    """Scale2x / EPX / AdvMAME2x on an HxWxC array, exact colour equality (palette art)."""
    P = np.asarray(img)
    pad = np.pad(P, ((1, 1), (1, 1), (0, 0)), mode="edge")
    A = pad[:-2, 1:-1]   # up
    B = pad[1:-1, 2:]    # right
    C = pad[1:-1, :-2]   # left
    D = pad[2:, 1:-1]    # down
    eq = lambda u, v: np.all(u == v, axis=2)[..., None]
    CA, AB, DC, BD = eq(C, A), eq(A, B), eq(D, C), eq(B, D)
    CD, BA = ~eq(C, D), ~eq(A, B)
    AC, BDn = ~eq(A, C), ~eq(B, D)
    E0 = np.where(CA & CD & BA, A, P)
    E1 = np.where(AB & AC & BDn, B, P)
    E2 = np.where(DC & BDn & AC, C, P)
    E3 = np.where(BD & BA & CD, D, P)
    h, w, c = P.shape
    out = np.empty((2 * h, 2 * w, c), P.dtype)
    out[0::2, 0::2], out[0::2, 1::2], out[1::2, 0::2], out[1::2, 1::2] = E0, E1, E2, E3
    return out


def scale4x(rgb):
    """Scale4x = Scale2x applied twice (the AdvMAME4x definition). Works on uint8-exact colours."""
    u8 = to_u8(rgb)
    return _scale2x(_scale2x(u8)).astype(np.float32) / 255.0


def dedither_prepass(rgb, sigma=0.5, down="lanczos"):
    """MrFlibble's deterministic de-dither: pattern 4x (Scale4x standing in for xBRZ 4x) -> Gaussian blur of
    `sigma` px at 4x -> sinc (Lanczos) downscale back to the original size. Use on bled RGB (transparent
    pixels already filled) so the blur does not drag black into the edge."""
    h, w = rgb.shape[:2]
    up = scale4x(rgb)
    if sigma > 0:
        up = np.dstack([ndi.gaussian_filter(up[..., c], sigma, mode="nearest") for c in range(3)])
    return resize(up, w, h, down)


def kuwahara(rgb, radius=1):
    """Kuwahara filter (4 overlapping (r+1)x(r+1) quadrants; output = mean of the quadrant with the lowest
    luminance variance). Light, edge-preserving denoise; radius 1-2 px as in MrFlibble's chain."""
    x = np.asarray(rgb, np.float32)
    r = int(radius)
    if r <= 0:
        return x.copy()
    k = r + 1
    lum = x @ np.array([0.299, 0.587, 0.114], np.float32)
    m_l = ndi.uniform_filter(lum, k, mode="nearest")
    m_l2 = ndi.uniform_filter(lum * lum, k, mode="nearest")
    var = m_l2 - m_l * m_l
    m_c = np.dstack([ndi.uniform_filter(x[..., c], k, mode="nearest") for c in range(3)])
    # uniform_filter with even size k is centred at offset -(k//2)..; build the 4 quadrant means by shifting
    h, w = lum.shape
    best_v = np.full((h, w), np.inf, np.float32)
    out = np.zeros_like(x)
    # window covering rows [y+dy0, y+dy0+k) : the uniform_filter window for even/odd k starts at -(k//2)
    for oy in (-r, 0):
        for ox in (-r, 0):
            sy, sx = oy + k // 2, ox + k // 2   # shift so the window starts at y+oy
            v = _shift(var, sy, sx)
            c = np.dstack([_shift(m_c[..., i], sy, sx) for i in range(3)])
            better = v < best_v
            best_v = np.where(better, v, best_v)
            out[better] = c[better]
    return out


def _shift(a, dy, dx):
    """b[y,x] = a[y+dy, x+dx] with edge clamp."""
    h, w = a.shape
    yy = np.clip(np.arange(h) + dy, 0, h - 1)
    xx = np.clip(np.arange(w) + dx, 0, w - 1)
    return a[yy][:, xx]


# ---------------------------------------------------------------------------------------- colour space

def srgb_to_linear(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb_to_lab(rgb):
    """sRGB [0,1] (...x3) -> CIE L*a*b* (D65)."""
    lin = srgb_to_linear(rgb)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883])
    e, k = 216 / 24389, 24389 / 27
    f = np.where(xyz > e, np.cbrt(xyz), (k * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def delta_e2000(lab1, lab2):
    """CIEDE2000 (Sharma, Wu, Dalal 2005), vectorised over the leading axes."""
    L1, a1, b1 = np.moveaxis(np.asarray(lab1, np.float64), -1, 0)
    L2, a2, b2 = np.moveaxis(np.asarray(lab2, np.float64), -1, 0)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(C1p * C2p == 0, 0, dh)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh) / 2)
    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    hs = h1p + h2p
    hbp = np.where(np.abs(h1p - h2p) > 180, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2), hs / 2)
    hbp = np.where(C1p * C2p == 0, hs, hbp)
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def mean_delta_e(rgb_a, rgb_b, mask=None):
    """Mean CIEDE2000 between two same-size sRGB images (over opaque pixels if mask is given)."""
    d = delta_e2000(srgb_to_lab(rgb_a), srgb_to_lab(rgb_b))
    return float(d[np.asarray(mask, bool)].mean() if mask is not None else d.mean())


def delta_e_native(out_rgb, orig_rgb, mask=None, method="box"):
    """dE2000 of an upscaled output against the original after downscaling it back to native size."""
    h, w = orig_rgb.shape[:2]
    return mean_delta_e(resize(out_rgb, w, h, method), orig_rgb, mask)


# ---------------------------------------------------------------------------------------- colour match

def histogram_match(src, ref, src_mask=None, ref_mask=None):
    """Per-channel histogram (CDF) matching of src onto ref. Masks restrict which pixels define the CDFs;
    the mapping is applied to every src pixel."""
    src = np.asarray(src, np.float32)
    ref = np.asarray(ref, np.float32)
    out = np.empty_like(src)
    for c in range(3):
        s = src[..., c][src_mask] if src_mask is not None else src[..., c].ravel()
        r = ref[..., c][ref_mask] if ref_mask is not None else ref[..., c].ravel()
        sv, sc = np.unique(s, return_counts=True)
        rv, rc = np.unique(r, return_counts=True)
        s_cdf = (np.cumsum(sc) - 0.5 * sc) / s.size
        r_cdf = (np.cumsum(rc) - 0.5 * rc) / r.size
        mapped = np.interp(s_cdf, r_cdf, rv)
        out[..., c] = np.interp(src[..., c], sv, mapped)
    return np.clip(out, 0, 1)


def lut3d_fit(src, dst, mask=None, n=9, smooth=1.0):
    """Fit an n^3 RGB->RGB offset lattice from paired pixels (src[i] should become dst[i]).
    Trilinear splatting + normalised Gaussian convolution (`smooth` lattice cells) fills sparse cells;
    cells with no nearby data fall back to the global mean offset. Returns an n x n x n x 3 offset LUT."""
    s = np.asarray(src, np.float64).reshape(-1, 3)
    d = np.asarray(dst, np.float64).reshape(-1, 3)
    if mask is not None:
        m = np.asarray(mask, bool).ravel()
        s, d = s[m], d[m]
    off = d - s
    g = np.clip(s, 0, 1) * (n - 1)
    i0 = np.minimum(np.floor(g).astype(int), n - 2)
    f = g - i0
    S = np.zeros((n, n, n, 3))
    W = np.zeros((n, n, n))
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                w = (np.where(dr, f[:, 0], 1 - f[:, 0]) * np.where(dg, f[:, 1], 1 - f[:, 1])
                     * np.where(db, f[:, 2], 1 - f[:, 2]))
                idx = (i0[:, 0] + dr, i0[:, 1] + dg, i0[:, 2] + db)
                np.add.at(W, idx, w)
                for c in range(3):
                    np.add.at(S[..., c], idx, w * off[:, c])
    if smooth > 0:
        Wf = ndi.gaussian_filter(W, smooth, mode="nearest")
        Sf = np.stack([ndi.gaussian_filter(S[..., c], smooth, mode="nearest") for c in range(3)], -1)
    else:
        Wf, Sf = W, S
    glob = off.mean(0) if len(off) else np.zeros(3)
    lut = np.where(Wf[..., None] > 1e-3, Sf / np.maximum(Wf[..., None], 1e-12), glob)
    # blend weakly supported cells toward the global offset
    conf = np.clip(Wf / 0.05, 0, 1)[..., None]
    return conf * lut + (1 - conf) * glob


def lut3d_apply(rgb, lut):
    n = lut.shape[0]
    x = np.asarray(rgb, np.float64)
    shp = x.shape
    x = x.reshape(-1, 3)
    coords = (np.clip(x, 0, 1) * (n - 1)).T
    off = np.stack([ndi.map_coordinates(lut[..., c], coords, order=1, mode="nearest") for c in range(3)], -1)
    return np.clip(x + off, 0, 1).reshape(shp).astype(np.float32)


def lut3d_match(out_rgb, orig_rgb, mask=None, n=9, smooth=1.0, down="box"):
    """Fit a LUT from (output downscaled to native, original) pixel pairs and apply it to the full-size output."""
    h, w = orig_rgb.shape[:2]
    small = resize(out_rgb, w, h, down)
    lut = lut3d_fit(small, orig_rgb, mask, n, smooth)
    return lut3d_apply(out_rgb, lut)


# --------------------------------------------------------------------------------------------- palette

def palette_from_image(rgb, mask=None):
    """Unique colours of the opaque pixels. For a decoded M16 tile this IS the tile's palette (RGB565 decode
    is exact, so every used palette entry reappears verbatim). Returns Kx3 float32."""
    u = to_u8(rgb).reshape(-1, 3)
    if mask is not None:
        u = u[np.asarray(mask, bool).ravel()]
    return np.unique(u, axis=0).astype(np.float32) / 255.0


def widen_palette(palette, factor=2, k=4, steps=(0.25, 0.5, 0.75)):
    """Grow a palette to factor x its size without inventing hues: candidates are interpolations between each
    colour and its k nearest neighbours in Lab (i.e. along the ramps the artist already used); the original
    colours are always kept, then farthest-point sampling in Lab adds candidates until len = factor * K."""
    pal = np.asarray(palette, np.float32).reshape(-1, 3)
    K = len(pal)
    target = int(round(K * factor))
    if K < 2 or target <= K:
        return pal.copy()
    lab = srgb_to_lab(pal)
    d = ((lab[:, None] - lab[None]) ** 2).sum(-1)
    np.fill_diagonal(d, np.inf)
    nn = np.argsort(d, 1)[:, :min(k, K - 1)]
    cands = []
    for i in range(K):
        for j in nn[i]:
            if j < i and i in nn[j]:
                continue  # pair already added from the other side
            for t in steps:
                cands.append(pal[i] * (1 - t) + pal[j] * t)
    cands = np.unique(np.round(np.asarray(cands) * 255) / 255, axis=0).astype(np.float32)
    clab = srgb_to_lab(cands)
    mind = ((clab[:, None] - lab[None]) ** 2).sum(-1).min(1)
    chosen = []
    for _ in range(min(target - K, len(cands))):
        j = int(mind.argmax())
        if mind[j] <= 1e-9:
            break
        chosen.append(j)
        mind = np.minimum(mind, ((clab - clab[j]) ** 2).sum(-1))
    return np.vstack([pal, cands[chosen]]) if chosen else pal.copy()


def palette_lock(rgb, palette, space="lab"):
    """Quantize every pixel to its nearest palette colour (no dither)."""
    pal = np.asarray(palette, np.float32).reshape(-1, 3)
    return pal[palette_index(rgb, pal, space)]


# --------------------------------------------------------------------------------------------- metrics

def luminance(rgb):
    return np.asarray(rgb, np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def halo_metrics(out_rgb, out_mask, ref_rgb, ref_mask, band=2):
    """Objective halo measure at output resolution.
    out_rgb/out_mask : the final upscaled colour and its (binary) mask
    ref_rgb/ref_mask : a halo-free reference at the same size, e.g. lanczos(bleed(orig)) and the nearest-
                       neighbour-upscaled original mask.
    Returns dict:
      edge_dev   mean |L_out - L_ref| over opaque output pixels within `band` px of the output mask edge
      int_dev    the same over opaque pixels farther inside (the model's ordinary deviation)
      halo       edge_dev - int_dev (>0 = the rim deviates more than the interior: a halo)
      edge_bias  signed mean (L_out - L_ref) in the band (<0 dark halo, >0 light halo)
      mask_iou   IoU of out_mask vs ref_mask; fringe_px = opaque output pixels outside ref_mask."""
    om = np.asarray(out_mask, bool)
    rm = np.asarray(ref_mask, bool)
    dist = ndi.distance_transform_edt(om)
    edge = om & (dist <= band)
    inner = om & (dist > band + 1)
    dl = luminance(out_rgb) - luminance(ref_rgb)
    e = float(np.abs(dl[edge]).mean()) if edge.any() else float("nan")
    i = float(np.abs(dl[inner]).mean()) if inner.any() else float("nan")
    union = (om | rm).sum()
    return {
        "edge_dev": e, "int_dev": i, "halo": e - i if inner.any() and edge.any() else float("nan"),
        "edge_bias": float(dl[edge].mean()) if edge.any() else float("nan"),
        "mask_iou": float((om & rm).sum() / union) if union else 1.0,
        "fringe_px": int((om & ~rm).sum()), "missing_px": int((rm & ~om).sum()),
    }


def laplacian_variance(rgb, mask=None):
    lap = ndi.laplace(luminance(rgb).astype(np.float64))
    return float(lap[np.asarray(mask, bool)].var() if mask is not None else lap.var())


# ------------------------------------------------------------------------------------------ visualising

def composite(rgb, alpha, bg="checker", cell=8):
    """Composite over a backdrop; 'checker' (grey/white), 'magenta', 'black', 'white' or an RGB tuple."""
    rgb = np.asarray(rgb, np.float32)
    a = np.asarray(alpha, np.float32)[..., None]
    h, w = rgb.shape[:2]
    if bg == "checker":
        yy, xx = np.mgrid[:h, :w]
        c = (((yy // cell) + (xx // cell)) % 2).astype(np.float32)
        back = np.dstack([0.55 + 0.35 * c] * 3)
    else:
        col = {"magenta": (1, 0, 1), "black": (0, 0, 0), "white": (1, 1, 1)}.get(bg, bg)
        back = np.broadcast_to(np.asarray(col, np.float32), rgb.shape)
    return rgb * a + back * (1 - a)


def contact_sheet(tiles, labels, cols, path, cell_w=None, cell_h=None, row_labels=None, bg=(32, 32, 32)):
    """tiles: list of HxWx3 float arrays (None = blank). Each is nearest-scaled to (cell_w, cell_h) so pixels
    stay visible; labels drawn under each cell. Saves a PNG and returns its path."""
    valid = [t for t in tiles if t is not None]
    cw = cell_w or max(t.shape[1] for t in valid)
    ch = cell_h or max(t.shape[0] for t in valid)
    lab_h = 14
    rl_w = 0 if not row_labels else 110
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (rl_w + cols * (cw + 4) + 4, rows * (ch + lab_h + 4) + 4), bg)
    dr = ImageDraw.Draw(sheet)
    for k, (t, lab) in enumerate(zip(tiles, labels)):
        r, c = divmod(k, cols)
        x0, y0 = rl_w + 4 + c * (cw + 4), 4 + r * (ch + lab_h + 4)
        if t is not None:
            im = Image.fromarray(to_u8(t)).resize((cw, ch), Image.NEAREST)
            sheet.paste(im, (x0, y0))
        dr.text((x0, y0 + ch + 1), str(lab)[: max(4, cw // 6)], fill=(230, 230, 230))
    if row_labels:
        for r, lab in enumerate(row_labels):
            dr.text((4, 4 + r * (ch + lab_h + 4) + ch // 2), str(lab)[:18], fill=(230, 230, 120))
    sheet.save(path)
    return path
