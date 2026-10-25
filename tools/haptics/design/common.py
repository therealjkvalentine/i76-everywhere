"""common.py - shared helpers for the haptics design facility (tools/haptics/design).

Paths, reading the game's sounds out of the PRISTINE read-only install (never a game folder that is played or
tested), .gpw decoding, and a dependency-free PNG writer + raster plots (matplotlib is not installed on this box;
numpy is).
"""
import io, json, os, struct, sys, wave, zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                # tools/haptics
REPO = os.path.dirname(os.path.dirname(ROOT))
OUT = os.path.join(HERE, "out")                             # gitignored: derived from the owner's own game files
PRISTINE = (__import__("os").path.expanduser("~") + r"\i76-map\sandbox-gog\main\app")   # AGENTS.md: "pristine control - read-only reference"
LZO_CANDIDATES = [os.environ.get("LZO2_DLL", ""), (__import__("os").path.expanduser("~") + r"\anaconda3\Library\bin\lzo2.dll")]

sys.path.insert(0, os.path.join(REPO, "tools"))


def game_dir():
    d = os.environ.get("I76_PRISTINE", PRISTINE)
    for bad in ("Interstate76-2026-10-03", "golden", "uncap-lab", "Downloads"):
        if bad.lower() in d.lower():
            raise SystemExit("refusing %s: the design facility reads only the pristine read-only copy" % d)
    return d


def _lzo_env():
    if os.environ.get("LZO2_DLL") and os.path.exists(os.environ["LZO2_DLL"]):
        return
    for c in LZO_CANDIDATES:
        if c and os.path.exists(c):
            os.environ["LZO2_DLL"] = c
            return


def zfs_sounds(kinds=(".gpw", ".wav")):
    """{name: payload bytes} for every .gpw / .wav in the pristine I76.ZFS (read-only; decompressed in memory)."""
    _lzo_env()
    import zfs_extract
    path = os.path.join(game_dir(), "I76.ZFS")
    data = open(path, "rb").read()
    out = {}
    for name, off, length, comp, dlen in zfs_extract.parse(data):
        if not name.endswith(kinds):
            continue
        out[name] = zfs_extract.decompress(data[off:off + length], comp, dlen)
    return out


GAS_FIELDS = ("priority", "max_instances", "mode", "volume_pct", "random_pitch", "frequency")


def decode_sound(name, payload):
    """(meta, rate, samples float64 -1..1). .gpw = 'GAS0' + 6 int32 (data/FORMATS.md 8) + RIFF WAVE."""
    meta = {"name": name.rsplit(".", 1)[0], "container": name.rsplit(".", 1)[-1]}
    riff = payload.find(b"RIFF")
    if payload[:4] == b"GAS0":
        vals = struct.unpack_from("<6i", payload, 4)
        meta["gas"] = dict(zip(GAS_FIELDS, vals))
    if riff < 0:
        raise ValueError("no RIFF in " + name)
    w = wave.open(io.BytesIO(payload[riff:]))
    n, width, rate, ch = w.getnframes(), w.getsampwidth(), w.getframerate(), w.getnchannels()
    raw = w.readframes(n)
    if width == 1:
        s = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        s = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    else:
        raise ValueError("sample width %d in %s" % (width, name))
    if ch > 1:
        s = s.reshape(-1, ch).mean(axis=1)
    meta.update({"rate": rate, "bits": width * 8, "channels": ch, "frames": len(s)})
    return meta, rate, s


def read_wav(path):
    w = wave.open(path)
    raw = w.readframes(w.getnframes())
    s = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0 if w.getsampwidth() == 2 else (np.frombuffer(raw, np.uint8) - 128.0) / 128.0
    if w.getnchannels() > 1:
        s = s.reshape(-1, w.getnchannels()).mean(axis=1)
    return w.getframerate(), s


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")


# ---------------------------------------------------------------------------------------------------------------
# PNG + raster plots
# ---------------------------------------------------------------------------------------------------------------
def write_png(path, rgb):
    """rgb: uint8 array (h, w, 3)."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


_CMAP = np.array([[13, 8, 135], [84, 2, 163], [139, 10, 165], [185, 50, 137], [219, 92, 104], [244, 136, 73], [254, 188, 43], [240, 249, 33]], float)


def colormap(v):
    """v in 0..1 -> rgb (plasma-like, 8 stops)."""
    v = np.clip(v, 0, 1) * (len(_CMAP) - 1)
    i = np.minimum(np.floor(v).astype(int), len(_CMAP) - 2)
    f = (v - i)[..., None]
    return (_CMAP[i] * (1 - f) + _CMAP[i + 1] * f).astype(np.uint8)


def spectrogram_png(path, samples, rate, fmax=400.0, width=480, height=160, win=1024, db_range=60.0):
    """Log-magnitude STFT up to fmax, time left to right; returns the (times, freqs, S_db) it drew."""
    x = np.asarray(samples, float)
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))
    hop = max(1, (len(x) - win) // max(1, width - 1))
    frames = 1 + (len(x) - win) // hop
    w = np.hanning(win)
    S = np.array([np.abs(np.fft.rfft(x[i * hop:i * hop + win] * w)) for i in range(frames)]).T
    freqs = np.fft.rfftfreq(win, 1.0 / rate)
    keep = freqs <= fmax
    S, freqs = S[keep], freqs[keep]
    Sdb = 20 * np.log10(S + 1e-9)
    top = Sdb.max()
    img = (Sdb - (top - db_range)) / db_range
    # resample to the canvas
    yi = np.linspace(0, img.shape[0] - 1, height).astype(int)[::-1]
    xi = np.linspace(0, img.shape[1] - 1, width).astype(int)
    rgb = colormap(img[np.ix_(yi, xi)])
    # 20/40/80/160/320 Hz guide lines
    for f in (20, 40, 80, 160, 320):
        if f < fmax:
            y = height - 1 - int(f / fmax * (height - 1))
            rgb[y, ::4] = [255, 255, 255]
    write_png(path, rgb)
    return frames, freqs, Sdb


def _canvas(w, h, bg=(250, 250, 250)):
    c = np.zeros((h, w, 3), np.uint8)
    c[:] = bg
    return c


def line_plot_png(path, series, width=480, height=140, ylim=None, colors=None, zero_line=True):
    """series: list of (x array, y array). Min/max per pixel column so fast signals (a 30 Hz buzz) stay visible."""
    colors = colors or [(31, 119, 180), (214, 39, 40), (44, 160, 44), (148, 103, 189)]
    c = _canvas(width, height)
    xs = np.concatenate([np.asarray(s[0], float) for s in series]) if series else np.array([0, 1])
    ys = np.concatenate([np.asarray(s[1], float) for s in series]) if series else np.array([0, 1])
    x0, x1 = float(xs.min()), float(xs.max()) if len(xs) else 1.0
    if x1 <= x0:
        x1 = x0 + 1
    lo, hi = ylim if ylim else (float(min(ys.min(), 0)), float(max(ys.max(), 1e-9)))
    if hi <= lo:
        hi = lo + 1
    def Y(v):
        return np.clip((height - 1) - ((np.asarray(v) - lo) / (hi - lo) * (height - 1)), 0, height - 1).astype(int)
    if zero_line and lo < 0 < hi:
        c[Y(0), :] = [200, 200, 200]
    for k, (x, y) in enumerate(series):
        x = np.asarray(x, float); y = np.asarray(y, float)
        if len(x) == 0:
            continue
        col = np.clip(((x - x0) / (x1 - x0) * (width - 1)).astype(int), 0, width - 1)
        rgb = colors[k % len(colors)]
        ymin = np.full(width, np.inf); ymax = np.full(width, -np.inf)
        np.minimum.at(ymin, col, y); np.maximum.at(ymax, col, y)
        prev = None
        for px in range(width):
            if not np.isfinite(ymin[px]):
                continue
            a, b = Y(ymax[px]), Y(ymin[px])
            if prev is not None:
                a, b = min(a, prev), max(b, prev)
            c[a:b + 1, px] = rgb
            prev = Y((ymin[px] + ymax[px]) / 2)
    write_png(path, c)


def bar_png(path, labels_values, width=480, height=120, color=(44, 160, 44)):
    c = _canvas(width, height)
    n = len(labels_values)
    vals = np.array([v for _, v in labels_values], float)
    top = vals.max() if vals.size and vals.max() > 0 else 1.0
    bw = width // max(1, n)
    for i, v in enumerate(vals):
        h = int(v / top * (height - 4))
        c[height - h:height, i * bw + 2:(i + 1) * bw - 2] = color
    write_png(path, c)
