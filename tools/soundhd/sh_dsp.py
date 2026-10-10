"""DSP for the I'76 HD sound pack: clean-up, sub synthesis, harmonics, loudness match, true-peak limiting.

Every stage takes `loop`: a loop (engine idle, mode 1/2 GAS loops) is processed circularly -- tiled, processed,
middle period kept, or resampled by FFT (exactly periodic) -- so the seam the stock file had is the seam the
replacement has. One-shots are processed linearly at their stock length.

Design: docs/SOUND-HD-PACK.md 2 (methods ranked) and 3.2 (synthesis details). Deviations are commented inline.
"""
import math

import numpy as np
from scipy import signal
from scipy.interpolate import CubicSpline
from scipy.ndimage import minimum_filter1d, uniform_filter1d

EPS = 1e-12


def db(x):
    return 20.0 * math.log10(max(float(x), EPS))


def undb(d):
    return 10.0 ** (d / 20.0)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


# ---------------------------------------------------------------------------------------------- circular helpers
def tiles_for(n, pad):
    """Odd number of tiles so that `pad` samples of context exist on both sides of the middle period."""
    k = int(math.ceil(pad / max(n, 1)))
    return 2 * k + 1


def circ(fn, x, pad):
    """Apply fn to a periodic signal: tile, process, keep the middle period."""
    n = len(x)
    k = tiles_for(n, pad)
    y = fn(np.tile(x, k))
    m = k // 2
    return np.asarray(y[m * n:(m + 1) * n])


def sos_band(fs, lo, hi, order=2):
    """Butterworth band-pass (order per edge; order=2 -> 4th-order band-pass)."""
    nyq = fs / 2.0
    hi = min(hi, 0.95 * nyq)
    return signal.butter(order, [lo / nyq, hi / nyq], btype="bandpass", output="sos")


def sos_hp(fs, f, order=2):
    return signal.butter(order, f / (fs / 2.0), btype="highpass", output="sos")


def sos_lp(fs, f, order=2):
    return signal.butter(order, min(f / (fs / 2.0), 0.95), btype="lowpass", output="sos")


def filt(sos, x, loop, fs, zero_phase=False):
    """Filter; loops circularly (1 s of context), one-shots causally or zero-phase."""
    if loop:
        f = (lambda t: signal.sosfiltfilt(sos, t)) if zero_phase else (lambda t: signal.sosfilt(sos, t))
        return circ(f, x, int(fs * 1.0))
    if zero_phase:
        return signal.sosfiltfilt(sos, x)
    return signal.sosfilt(sos, x)


# ---------------------------------------------------------------------------------------------- clean-up
def remove_dc(x, fs, loop):
    """Subtract the mean; one-shots also get a zero-phase 10 Hz high-pass (drifting 8-bit offsets)."""
    y = x - np.mean(x)
    if not loop and len(y) > 64:
        y = signal.sosfiltfilt(sos_hp(fs, 10.0, 1), y)
    return y


def declick(x, loop):
    """Replace isolated 1-2 sample spikes. A spike = a second difference that stands > 8x above the LOCAL median
    second difference (65-sample window) and above 0.15 FS. Using the local scale keeps legitimate near-Nyquist
    content (every sample "spiky") untouched; only outliers against their own neighbourhood are repaired, by linear
    interpolation across them. Returns (y, n_fixed)."""
    from scipy.ndimage import median_filter

    def run(t):
        e = np.zeros_like(t)
        e[1:-1] = t[1:-1] - 0.5 * (t[:-2] + t[2:])
        a = np.abs(e)
        loc = median_filter(a, 65, mode="nearest")
        # a 1-sample spike of height h gives second differences (-h/2, h, -h/2): keep only the local maxima
        bad = (a > 8.0 * loc + EPS) & (a > 0.15)
        lmax = np.zeros_like(bad)
        lmax[1:-1] = (a[1:-1] >= a[:-2]) & (a[1:-1] >= a[2:])
        bad &= lmax
        lab = np.diff(np.concatenate(([0], bad.astype(np.int8), [0])))
        starts, ends = np.where(lab == 1)[0], np.where(lab == -1)[0]
        y = t.copy()
        nfix = 0
        for s, e_ in zip(starts, ends):
            if e_ - s > 2 or s < 1 or e_ >= len(t):
                continue
            y[s:e_] = np.interp(np.arange(s, e_), [s - 1, e_], [t[s - 1], t[e_]])
            nfix += e_ - s
        return y, nfix
    if loop:
        n = len(x)
        y3, nb = run(np.tile(x, 3))
        return y3[n:2 * n], nb // 3
    return run(x)


def declip(x, loop, thr=126.5 / 128.0, max_run=48, max_gain=1.2):
    """Gentle de-clip: runs of >= 2 samples at the 8-bit rails are re-drawn with a cubic spline through
    4 good neighbours each side, kept on the rail's side and capped at max_gain x the rail. Returns (y, n_runs)."""
    def run(t):
        y = t.copy()
        hot = (t >= thr) | (t <= -thr - 1.0 / 128.0 + 1e-9)  # +127/128 and -128/128 rails
        lab = np.diff(np.concatenate(([0], hot.astype(np.int8), [0])))
        starts, ends = np.where(lab == 1)[0], np.where(lab == -1)[0]
        nfix = 0
        for s, e in zip(starts, ends):
            if e - s < 2 or e - s > max_run or s < 4 or e + 4 > len(t):
                continue
            idx = np.r_[s - 4:s, e:e + 4]
            if hot[idx].any():
                continue
            cs = CubicSpline(idx, t[idx])
            seg = cs(np.arange(s, e))
            sign = np.sign(t[s])
            seg = sign * np.clip(np.abs(seg), np.abs(t[s:e]), max_gain)
            y[s:e] = seg
            nfix += 1
        return y, nfix
    if loop:
        n = len(x)
        y3, nf = run(np.tile(x, 3))
        return y3[n:2 * n], nf // 3
    return run(x)


_NOISE_REF = {}


def _noise_psd(fs, nper, nover, sigma):
    key = (fs, nper, nover)
    if key not in _NOISE_REF:
        rng = np.random.default_rng(76)
        w = rng.standard_normal(fs * 4)
        _, _, z = signal.stft(w, fs, window="hann", nperseg=nper, noverlap=nover)
        _NOISE_REF[key] = np.mean(np.abs(z) ** 2, axis=1)
    return _NOISE_REF[key] * sigma ** 2


def denoise_quant(x, fs, loop, bits=8, oversub=2.0, floor_db=-12.0):
    """Spectral gate against the KNOWN 8-bit quantisation floor (white, sigma = q/sqrt(12), q = 2/2^bits):
    bins within a few dB of that floor are attenuated (at most `floor_db`), louder bins pass. Using the
    theoretical floor rather than a percentile estimate keeps steady loop content (an engine drone) intact.
    Deviation from RX Spectral De-noise: no learned profile; deliberately mild."""
    sigma = (2.0 / 2 ** bits) / math.sqrt(12.0)
    nper = 256 if fs <= 12000 else 512
    nover = nper * 3 // 4
    pn = _noise_psd(fs, nper, nover, sigma)
    gmin = undb(floor_db)

    def run(t):
        _, _, z = signal.stft(t, fs, window="hann", nperseg=nper, noverlap=nover)
        p = np.abs(z) ** 2 + EPS
        g = np.clip(1.0 - oversub * pn[:, None] / p, gmin, 1.0)
        g = signal.medfilt2d(g, (1, 3))  # tame musical noise
        _, y = signal.istft(z * g, fs, window="hann", nperseg=nper, noverlap=nover)
        y = y[:len(t)]
        if len(y) < len(t):
            y = np.pad(y, (0, len(t) - len(y)))
        return y
    if loop:
        return circ(run, x, nper * 4)
    return run(x)


# ---------------------------------------------------------------------------------------------- resampling
def resample(x, fs_in, fs_out, loop):
    if fs_in == fs_out:
        return x.copy()
    if loop:
        n_out = int(round(len(x) * fs_out / fs_in))
        return signal.resample(x, n_out)  # FFT method: exactly periodic, the seam survives
    g = math.gcd(int(fs_in), int(fs_out))
    return signal.resample_poly(x, fs_out // g, fs_in // g)


# ---------------------------------------------------------------------------------------------- envelopes / onsets
def env_rms(x, fs, win_s, loop):
    w = max(1, int(fs * win_s))
    if loop:
        return circ(lambda t: np.sqrt(np.maximum(uniform_filter1d(t ** 2, w, mode="nearest"), 0.0)), x, w * 2)
    return np.sqrt(np.maximum(uniform_filter1d(x ** 2, w, mode="nearest"), 0.0))


def onsets(x, fs, loop, rise_db_per_ms=2.0, refractory_s=0.06, floor_rel_db=-30.0):
    """5 ms RMS envelope sampled every 1 ms; an onset = a rise >= rise_db_per_ms within 1 ms (design 3.2), with
    the envelope above (max - 30 dB) and a 60 ms refractory. Returns [(sample_index, env_peak_rms)]."""
    n = len(x)
    if loop:
        t = np.tile(x, 3)
    else:
        t = x
    env = np.sqrt(np.maximum(uniform_filter1d(t ** 2, max(1, int(fs * 0.005)), mode="nearest"), 0.0))
    hop = max(1, int(fs * 0.001))
    e = env[::hop]
    edb = 20 * np.log10(e + 1e-9)
    floor = edb.max() + floor_rel_db
    rise = np.diff(edb, prepend=edb[0])
    # also require 6 dB over the preceding 5 ms so slow swells on noise don't count
    look = 5
    rise5 = edb - np.concatenate((np.full(look, edb[0]), edb[:-look]))
    cand = np.where((rise >= rise_db_per_ms) & (rise5 >= 6.0) & (edb >= floor))[0]
    out, last = [], -10 ** 9
    ref = int(refractory_s / 0.001)
    for c in cand:
        if c - last < ref:
            continue
        last = c
        s = c * hop
        pk = float(env[s:s + int(fs * 0.03)].max()) if s < len(env) else float(env[-1])
        if loop:
            if n <= s < 2 * n:
                out.append((s - n, pk))
        else:
            out.append((s, pk))
    if loop and len(out) < max(1, int(n / fs / 0.25)):
        # dense weapon loops (whmgun: shots every ~45 ms, envelope dips only ~4 dB, never a 2 dB/ms rise from a
        # gap): take envelope peaks with >= 2.5 dB prominence instead, onset placed 5 ms before each peak
        pk, _ = signal.find_peaks(edb, prominence=2.5, distance=max(1, int(0.03 / 0.001)))
        out = []
        for c in pk:
            s = max(0, c - 5) * hop
            if n <= s < 2 * n:
                out.append((s - n, float(env[c * hop])))
    if not loop and not out and len(x):
        # a one-shot that starts at full level has no rise from silence: the file start is the onset
        out.append((0, float(env[: int(fs * 0.03)].max())))
    return out


# ---------------------------------------------------------------------------------------------- sub synthesis
def transient_sub(n, fs, ons, loop, level_db, f_hi=90.0, f_lo=35.0, sweep_s=0.25, tau_s=0.25, band=(30.0, 90.0)):
    """Each onset spawns A*sin(phi(t))*exp(-t/tau), f(t) gliding f_hi -> f_lo over sweep_s, A from the onset's
    envelope peak; then a 4th-order band-pass. Loops add bursts circularly (indices mod n)."""
    y = np.zeros(n)
    blen = int(fs * tau_s * 5)
    t = np.arange(blen) / fs
    f = f_hi * (f_lo / f_hi) ** np.minimum(t / sweep_s, 1.0)
    ph = 2 * np.pi * np.concatenate(([0.0], np.cumsum(f[:-1]) / fs))
    att = np.minimum(1.0, t / 0.003)
    burst = np.sin(ph) * np.exp(-t / tau_s) * att
    for pos, pk in ons:
        a = pk * math.sqrt(2.0) * undb(level_db)
        idx = pos + np.arange(blen)
        if loop:
            np.add.at(y, idx % n, a * burst)
        else:
            m = idx < n
            y[idx[m]] += a * burst[m]
    y = filt(sos_band(fs, band[0], band[1]), y, loop, fs)
    if not loop and n > int(fs * 0.03):
        fo = int(fs * 0.03)
        y[-fo:] *= np.linspace(1.0, 0.0, fo)  # one-shots keep their stock length; fade the truncated tail
    return y


def duck_sub(sub, src, fs, loop, level_db, headroom_db=3.0):
    """Keep the summed sub under the source's own 50 ms envelope (+ level + headroom): overlapping bursts of a
    fast weapon loop would otherwise pile up into a drone that eats the file's headroom."""
    cap = env_rms(src, fs, 0.05, loop) * math.sqrt(2.0) * undb(level_db + headroom_db)
    se = env_rms(sub, fs, 0.02, loop) * math.sqrt(2.0)
    g = np.minimum(1.0, cap / (se + EPS))
    w = max(1, int(fs * 0.03))
    g = circ(lambda t: uniform_filter1d(t, w, mode="nearest"), g, 2 * w) if loop else uniform_filter1d(g, w, mode="nearest")
    return sub * g, float(np.min(g))


def track_f0(x, fs, loop, fmin=40.0, fmax=400.0, hop_s=0.046, win_s=0.093, clarity_min=0.35):
    """Autocorrelation f0 tracker (design 3.2: 40-400 Hz, 46 ms hop). Clarity 0.35 (not
    0.45): the 8-bit engine loops einp1/eitank sit at a median 0.37-0.41. Returns (centres, f0[], clarity[])."""
    pre = filt(sos_lp(fs, 1000.0, 4), x, loop, fs)
    n = len(pre)
    win = int(fs * win_s)
    hop = int(fs * hop_s)
    lmin, lmax = int(fs / fmax), int(math.ceil(fs / fmin))
    src = np.tile(pre, 3) if loop else np.pad(pre, (win // 2, win // 2))
    off = n if loop else 0
    w = np.hanning(win)
    centres = np.arange(0, n, hop)
    f0 = np.zeros(len(centres))
    cl = np.zeros(len(centres))
    floor = undb(-45.0)
    for i, c in enumerate(centres):
        a = off + c - (win // 2 if loop else 0)
        seg = src[a:a + win]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        if rms(seg) < floor:
            continue
        s = seg * w
        spec = np.fft.rfft(s, 2 * win)
        r = np.fft.irfft(np.abs(spec) ** 2)[:win]
        r = r / (r[0] + EPS)
        r = r / np.maximum(1.0 - np.arange(win) / win, 0.25)  # unbias the lag taper
        if lmax >= win:
            continue
        seg_r = r[lmin:lmax + 1]
        best = int(np.argmax(seg_r)) + lmin
        # octave-error guard: a strong peak at half the lag is the real period
        while best // 2 >= lmin and r[best // 2] >= 0.85 * r[best]:
            best //= 2
        cl[i] = r[best]
        f0[i] = fs / best
    voiced = cl >= clarity_min
    return centres, np.where(voiced, f0, 0.0), cl


def octave_sub(x, fs, loop, level_db, band=(30.0, 90.0), voiced_only=False):
    """Pitch-tracked octave-down sub: sine at f0/2^k (k chosen so the median lands in the band), driven by the
    source's 50 ms RMS envelope, band-passed. Loops: frequency scaled so the phase completes an INTEGER number of
    cycles over the loop length (period-matched). Returns (y, info)."""
    n = len(x)
    centres, f0, cl = track_f0(x, fs, loop)
    v = f0 > 0
    info = dict(frames=int(len(f0)), voiced_frames=int(v.sum()))
    if v.sum() >= max(2, 0.2 * len(f0)):
        med = float(np.median(f0[v]))
        k = 1
        while med / 2 ** k > band[1]:
            k += 1
        if med / 2 ** k < band[0]:
            k = max(0, k - 1)
        fv = f0[v] / 2 ** k
        cv = centres[v]
        if loop:
            # circular interpolation across the seam
            xs = np.concatenate((cv - n, cv, cv + n))
            ys = np.tile(fv, 3)
        else:
            xs, ys = cv, fv
        fs_t = np.interp(np.arange(n), xs, ys)
        info.update(tracker="autocorr", f0_median_hz=round(med, 2), octave_div=2 ** k, sub_median_hz=round(med / 2 ** k, 2))
    else:
        fs_t = np.full(n, 45.0)
        info.update(tracker="fallback-45Hz", f0_median_hz=None, octave_div=None, sub_median_hz=45.0)
    if loop:
        cyc = float(np.sum(fs_t) / fs)
        N = max(1, int(round(cyc)))
        fs_t = fs_t * (N / cyc)
        info["sub_cycles"] = N
    ph = 2 * np.pi * np.concatenate(([0.0], np.cumsum(fs_t[:-1]) / fs))
    env = env_rms(x, fs, 0.05, loop)
    amp = env * math.sqrt(2.0) * undb(level_db)
    if voiced_only:
        vm = np.interp(np.arange(n), centres, v.astype(float))
        vm = uniform_filter1d(vm, max(1, int(fs * 0.05)), mode="nearest")
        amp = amp * vm
    y = np.sin(ph) * amp
    y = filt(sos_band(fs, band[0], band[1]), y, loop, fs)
    if not loop and n > int(fs * 0.03):
        fo = int(fs * 0.03)
        y[-fo:] *= np.linspace(1.0, 0.0, fo)
    return y, info


def harmonics(low, fs, loop, level_db, lo=90.0, hi=250.0):
    """Psychoacoustic bass (MaxxBass-style): waveshape the 30-90 Hz band (tanh + a little x^2 for even
    harmonics), keep 90-250 Hz, scale to `level_db` relative to the low band's RMS."""
    pk = float(np.max(np.abs(low))) + EPS
    u = low / pk
    h = np.tanh(3.0 * u) + 0.3 * u * u
    h = filt(sos_hp(fs, lo, 4), h, loop, fs)
    h = filt(sos_lp(fs, hi, 4), h, loop, fs)
    r = rms(h)
    if r < EPS:
        return np.zeros_like(low)
    return h * (rms(low) * undb(level_db) / r)


# ---------------------------------------------------------------------------------------------- loudness / peak
def loudness(x, fs):
    """ITU-R BS.1770-4 integrated loudness (pyloudnorm). Files shorter than the 400 ms gating block are measured
    as one block of their own length (ungated K-weighted loudness); the stock/new comparison is like-for-like."""
    import pyloudnorm as pyln
    n = len(x)
    if n < 16:
        return float("-inf")
    bs = min(0.4, (n - 1) / fs)
    m = pyln.Meter(int(fs), block_size=bs)
    try:
        return float(m.integrated_loudness(np.asarray(x, dtype=np.float64)))
    except Exception:
        return float("-inf")


def true_peak_db(x, loop=False):
    """4x oversampled peak (BS.1770 Annex 2 style), dBTP."""
    if len(x) == 0:
        return float("-inf")
    if loop:
        n = len(x)
        os_ = signal.resample_poly(np.tile(x, 3), 4, 1)[4 * n:8 * n]
    else:
        os_ = signal.resample_poly(x, 4, 1)
    return db(np.max(np.abs(os_)))


def limit(x, fs, loop, ceiling_db=-0.3, margin_db=0.25, release_s=0.06, look_s=0.0015, passes=6):
    """Look-ahead true-peak limiter. The gain at each sample never exceeds what the 4x-oversampled peak needs
    (minimum filter over +/- look, then a moving average over half of that, then a release-only smoother)."""
    target = undb(ceiling_db - margin_db)
    y = np.asarray(x, dtype=np.float64).copy()
    for _ in range(passes):
        if true_peak_db(y, loop) <= ceiling_db:
            break
        def run(t):
            os_ = np.abs(signal.resample_poly(t, 4, 1))[: 4 * len(t)]
            if len(os_) < 4 * len(t):
                os_ = np.pad(os_, (0, 4 * len(t) - len(os_)))
            pk = os_.reshape(-1, 4).max(axis=1)
            need = np.minimum(1.0, target / (pk + EPS))
            la = max(1, int(fs * look_s))
            g = minimum_filter1d(need, 2 * la + 1, mode="nearest")
            g = uniform_filter1d(g, la, mode="nearest")
            g = np.minimum(g, need)
            r = math.exp(-1.0 / (fs * release_s))
            out = np.empty_like(g)
            prev = 1.0
            for i in range(len(g)):
                cur = r * prev + (1.0 - r) * g[i]
                if cur > g[i]:
                    cur = g[i]
                out[i] = cur
                prev = cur
            return t * out
        if loop:
            y = circ(run, y, int(fs * 0.5))
        else:
            y = run(y)
    return y


def soft_clip(x, ceiling_db=-0.6, knee=0.7):
    """Linear below knee*ceiling, tanh into the ceiling above it. Used only for dense near-square stock material
    (whmgun & co.) whose 8-bit samples sit at the rails: band-limiting that material adds ~2 dB of inter-sample
    overshoot, and a limiter alone can only meet -0.3 dBTP by squashing the whole loop."""
    c = undb(ceiling_db)
    k = knee * c
    a = np.abs(x)
    o = np.where(a <= k, a, k + (c - k) * np.tanh((a - k) / (c - k)))
    return np.sign(x) * o


def match_and_limit(mix, fs, loop, target_lufs, ceiling_db=-0.3, tol=0.15, max_gr_db=4.0):
    """Gain to the stock loudness, then the true-peak limiter; iterate (the limiter eats a little loudness).
    Strategy 1: limiter only (60 ms release). If that misses by > 0.3 LU or needs > max_gr_db of reduction,
    strategy 2: soft clip + limiter (20 ms release). Returns (out, gain, info)."""
    def attempt(stage):
        g = 1.0
        out = None
        for _ in range(8):
            z = mix * g
            if stage == "softclip+limiter":
                z = soft_clip(z)
                out = limit(z, fs, loop, ceiling_db, release_s=0.02)
            else:
                out = limit(z, fs, loop, ceiling_db, release_s=0.06)
            if not math.isfinite(target_lufs):
                break
            L = loudness(out, fs)
            if not math.isfinite(L):
                break
            d = target_lufs - L
            if abs(d) <= tol:
                break
            g *= undb(d)
        pre = np.abs(mix * g)
        m = pre > 1e-3
        gr = float(np.max(20 * np.log10(pre[m] / np.maximum(np.abs(out[m]), 1e-9)))) if m.any() else 0.0
        L = loudness(out, fs)
        miss = abs(target_lufs - L) if math.isfinite(target_lufs) and math.isfinite(L) else 0.0
        return out, g, dict(peak_stage=stage, limiter_max_gr_db=round(gr, 2), loudness_miss_lu=round(miss, 3))
    r1 = attempt("limiter")
    if r1[2]["loudness_miss_lu"] <= 0.3 and r1[2]["limiter_max_gr_db"] <= max_gr_db:
        return r1
    r2 = attempt("softclip+limiter")
    return r2 if r2[2]["loudness_miss_lu"] < r1[2]["loudness_miss_lu"] or r1[2]["loudness_miss_lu"] <= 0.3 and         r2[2]["loudness_miss_lu"] <= 0.3 else r1


def frac_below(x, fs, hz):
    """Fraction of Welch PSD energy below hz (the survey's E<hz metric, same parameters)."""
    x = x - np.mean(x)
    n = len(x)
    if n < 16:
        return 0.0
    nper = min(4096, n)
    f, p = signal.welch(x, fs=fs, nperseg=nper, noverlap=nper // 2, window="hann", detrend=False)
    return float(p[f < hz].sum() / (p.sum() + 1e-30))


def frac_band(x, fs, lo, hi):
    """Fraction of Welch PSD energy in [lo, hi) Hz -- the check's E20-120 metric. The survey's E<120 counts
    0-20 Hz too, which on drifting 8-bit files (dfire: E<120 0.25 stock, almost all of it below 20 Hz) is the DC
    wander that remove_dc() takes out, not audible bass."""
    x = x - np.mean(x)
    n = len(x)
    if n < 16:
        return 0.0
    nper = min(int(round(fs * 4096 / 11025)), n)  # same frequency resolution at every rate (2.7 Hz bins)
    f, p = signal.welch(x, fs=fs, nperseg=nper, noverlap=nper // 2, window="hann", detrend=False)
    return float(p[(f >= lo) & (f < hi)].sum() / (p.sum() + 1e-30))


BANDS = [(20, 40), (40, 80), (80, 160), (160, 320), (320, 640), (640, 1280), (1280, 2560), (2560, 5512), (5512, 11025)]


def band_energies_db(x, fs):
    """Energy per octave band (dB re full-scale sine power), for the report."""
    x = x - np.mean(x)
    if len(x) < 16:
        return [None] * len(BANDS)
    nper = min(4096, len(x))
    f, p = signal.welch(x, fs=fs, nperseg=nper, noverlap=nper // 2, window="hann", detrend=False, scaling="spectrum")
    out = []
    for lo, hi in BANDS:
        m = (f >= lo) & (f < hi)
        out.append(round(10 * math.log10(p[m].sum() + 1e-20) + 3.01, 1) if m.any() and lo < fs / 2 else None)
    return out


def seam_ratio(x):
    """Wrap-around continuity of a loop: |x[0] - x[-1]| relative to the 99th percentile of |diff(x)|.
    <= 1 means the jump across the seam is no bigger than an ordinary sample step."""
    d = np.abs(np.diff(x))
    p99 = float(np.percentile(d, 99)) + EPS
    return float(abs(x[0] - x[-1]) / p99)

