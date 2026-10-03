"""Unit tests for prepost.py on synthetic images. Run: python tools/upscale/test_prepost.py (or pytest)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prepost as pp  # noqa: E402


def _disc(h=32, w=32, r=9):
    yy, xx = np.mgrid[:h, :w]
    return (yy - h / 2 + 0.5) ** 2 + (xx - w / 2 + 0.5) ** 2 <= r * r


def test_bleed_rings_and_rest():
    m = _disc()
    rgb = np.zeros((32, 32, 3), np.float32)
    rgb[m] = (0.8, 0.2, 0.1)
    out = pp.bleed(rgb, m, px=3, rest="keep")
    assert np.array_equal(out[m], rgb[m]), "opaque pixels must not change"
    import scipy.ndimage as ndi
    d = ndi.distance_transform_cdt(~m, metric="chessboard")
    ring = (d >= 1) & (d <= 3)
    assert np.allclose(out[ring], (0.8, 0.2, 0.1), atol=1e-5)
    assert np.allclose(out[d > 3], 0)
    full = pp.bleed(rgb, m, px=3, rest="nearest")
    assert np.allclose(full, (0.8, 0.2, 0.1), atol=1e-5)


def test_bleed_mixes_two_colours():
    m = np.zeros((8, 8), bool)
    m[:, :3] = True
    m[:, 5:] = True
    rgb = np.zeros((8, 8, 3), np.float32)
    rgb[:, :3] = (1, 0, 0)
    rgb[:, 5:] = (0, 0, 1)
    out = pp.bleed(rgb, m, px=1, rest="keep")
    assert np.allclose(out[:, 3], (1, 0, 0)) and np.allclose(out[:, 4], (0, 0, 1))


def test_resize_float_and_threshold():
    m = _disc(16, 16, 5)
    up = pp.upscale_alpha_threshold(m, 64, 64, "bilinear", 0.5)
    assert up.shape == (64, 64)
    ref = _disc(64, 64, 20)
    iou = (up & ref).sum() / (up | ref).sum()
    assert iou > 0.9, iou
    # lower threshold -> grows the mask
    assert pp.upscale_alpha_threshold(m, 64, 64, "bilinear", 0.2).sum() > up.sum()


def test_scale2x_exact_and_diagonal():
    a = np.zeros((4, 4, 3), np.uint8)
    for i in range(4):
        a[i, : i + 1] = 255        # staircase
    s = pp._scale2x(a)
    assert s.shape == (8, 8, 3)
    # flat image stays flat; colours are never invented
    flat = np.full((3, 5, 3), 7, np.uint8)
    assert np.array_equal(pp._scale2x(flat), np.full((6, 10, 3), 7, np.uint8))
    assert set(map(tuple, s.reshape(-1, 3))) <= {(0, 0, 0), (255, 255, 255)}
    # the staircase gets smoothed: more white than a nearest-neighbour 2x
    nn = a.repeat(2, 0).repeat(2, 1)
    assert s.sum() != nn.sum()
    assert pp.scale4x(a / 255.0).shape == (16, 16, 3)


def test_dedither_flattens_checkerboard():
    yy, xx = np.mgrid[:32, :32]
    cb = ((yy + xx) % 2).astype(np.float32)
    rgb = np.dstack([cb * 0.6 + 0.2] * 3)
    out = pp.dedither_prepass(rgb, sigma=0.5)
    assert out.shape == rgb.shape
    assert out.std() < 0.5 * rgb.std(), (out.std(), rgb.std())
    assert abs(out.mean() - rgb.mean()) < 0.05


def test_kuwahara_preserves_edge_and_denoises():
    rng = np.random.default_rng(0)
    img = np.zeros((32, 32, 3), np.float32)
    img[:, 16:] = 1.0
    noisy = np.clip(img + rng.normal(0, 0.05, img.shape).astype(np.float32), 0, 1)
    out = pp.kuwahara(noisy, 2)
    assert np.abs(out[:, :14] - 0).mean() < np.abs(noisy[:, :14] - 0).mean()
    # edge stays sharp: column 15 dark, column 16 bright
    assert out[:, 15].mean() < 0.2 and out[:, 16].mean() > 0.8


def test_delta_e2000_sharma():
    pairs = [((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
             ((50, 2.5, 0), (73, 25, -18), 27.1492),
             ((50, 2.5, 0), (50, 3.2972, 0), 1.0000),
             ((50, 2.5, 0), (58, 24, 15), 19.4535),
             ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
             ((50, -1, 2), (50, 0, 0), 2.3669),
             ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441)]
    a = np.array([p[0] for p in pairs]); b = np.array([p[1] for p in pairs])
    d = pp.delta_e2000(a, b)
    assert np.allclose(d, [p[2] for p in pairs], atol=1e-4), d
    assert np.allclose(pp.delta_e2000(b, a), d, atol=1e-6)


def test_lab_white_black():
    lab = pp.srgb_to_lab(np.array([[1, 1, 1], [0, 0, 0]], np.float32))
    assert np.allclose(lab[0], (100, 0, 0), atol=0.05) and np.allclose(lab[1], 0, atol=1e-6)


def test_histogram_match_undoes_contrast_drift():
    rng = np.random.default_rng(1)
    orig = rng.uniform(0.2, 0.8, (32, 32, 3)).astype(np.float32)
    drift = np.clip((orig - 0.5) * 1.4 + 0.5, 0, 1)   # brights brighter, darks darker
    fixed = pp.histogram_match(drift, orig)
    assert pp.mean_delta_e(fixed, orig) < 0.25 * pp.mean_delta_e(drift, orig)


def test_lut3d_learns_channel_swap_tint():
    rng = np.random.default_rng(2)
    orig = rng.uniform(0, 1, (48, 48, 3)).astype(np.float32)
    tinted = np.clip(orig * np.array([0.9, 1.0, 1.1]) + np.array([0.03, -0.02, 0.0]), 0, 1).astype(np.float32)
    lut = pp.lut3d_fit(tinted, orig, n=9, smooth=0.7)
    fixed = pp.lut3d_apply(tinted, lut)
    assert pp.mean_delta_e(fixed, orig) < 0.3 * pp.mean_delta_e(tinted, orig)
    # identity when nothing to correct
    lut0 = pp.lut3d_fit(orig, orig)
    assert np.allclose(pp.lut3d_apply(orig, lut0), orig, atol=1e-5)
    # lut3d_match at 4x: output that is a tinted 4x of the original
    up = pp.resize(tinted, 192, 192, "nearest")
    m = pp.lut3d_match(up, orig)
    assert pp.delta_e_native(m, orig) < 0.3 * pp.delta_e_native(up, orig)


def test_palette_from_image_and_lock():
    pal = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], np.float32)
    idx = np.random.default_rng(3).integers(0, 4, (16, 16))
    img = pal[idx]
    got = pp.palette_from_image(img)
    assert len(got) == 4
    noisy = np.clip(img + 0.05, 0, 1)
    locked = pp.palette_lock(noisy, pal)
    assert np.array_equal(locked, img)


def test_widen_palette_keeps_originals_and_stays_on_ramps():
    ramp = np.linspace(0, 1, 8)[:, None] * np.array([[1.0, 0.5, 0.2]], np.float32)
    w2 = pp.widen_palette(ramp, 2)
    assert len(w2) == 16
    assert np.allclose(w2[:8], ramp)
    # every added colour lies on the ramp line (no new hues)
    d = w2[8:] - (w2[8:, :1]) * np.array([1.0, 0.5, 0.2])
    assert np.abs(d).max() < 0.01
    w4 = pp.widen_palette(ramp, 4)
    assert 16 < len(w4) <= 32


def test_alpha_regenerate_recovers_mask():
    m = _disc(32, 32, 10)
    rgb = np.zeros((32, 32, 3), np.float32)
    rgb[m] = (0.2, 0.6, 0.3)
    rgb[m & (np.arange(32)[None, :] > 16)] = (0.7, 0.7, 0.2)
    keyed = pp.key_fill(rgb, m)
    up = pp.resize(keyed, 128, 128, "bicubic")   # a stand-in for the model (blurs key into edge)
    pal = pp.palette_from_image(rgb, m)
    got = pp.alpha_regenerate(up, pal, grow=1)
    ref = _disc(128, 128, 40)
    iou = (got & ref).sum() / (got | ref).sum()
    assert iou > 0.9, iou
    # grow=1 removes the magenta-contaminated rim: no strongly magenta pixel left inside
    lab_key = pp.srgb_to_lab(np.array([1, 0, 1], np.float32))
    de = pp.delta_e2000(pp.srgb_to_lab(up[got]), lab_key)
    assert de.min() > 20


def test_halo_metrics_detect_dark_rim():
    m = _disc(64, 64, 20)
    ref = np.full((64, 64, 3), 0.7, np.float32)
    out = ref.copy()
    import scipy.ndimage as ndi
    rim = m & (ndi.distance_transform_edt(m) <= 2)
    out[rim] *= 0.5
    h = pp.halo_metrics(out, m, ref, m)
    assert h["halo"] > 0.2 and h["edge_bias"] < -0.2 and h["mask_iou"] == 1.0
    clean = pp.halo_metrics(ref, m, ref, m)
    assert abs(clean["halo"]) < 1e-6


def test_laplacian_and_contact_sheet(tmp=None):
    import tempfile
    rng = np.random.default_rng(4)
    a = rng.uniform(0, 1, (16, 16, 3)).astype(np.float32)
    assert pp.laplacian_variance(a) > pp.laplacian_variance(np.full_like(a, 0.5))
    d = tempfile.mkdtemp()
    p = pp.contact_sheet([a, None, pp.composite(a, _disc(16, 16, 5))], ["a", "b", "c"], 2,
                         os.path.join(d, "s.png"), 64, 64, row_labels=["r0", "r1"])
    assert os.path.getsize(p) > 0


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(e))
    sys.exit(1 if fails else 0)
