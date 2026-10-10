#!/usr/bin/env python3
"""gpw_spectra.py - per-sound analysis of Interstate '76's stock sounds, for designing haptics from them.

Reads every .gpw (and, with --wav, every .wav) out of the PRISTINE read-only install's I76.ZFS (decompressed in
memory, nothing written into any game folder) and writes, per sound, design/out/analysis/<name>.json:

  RMS envelope (10 ms), onset and emphasis points, duration, band energies (0-20, 20-40, 40-80, 80-160, 160-320,
  320-1000, >1000 Hz; fractions of the total), the strongest frequency in the shaker band (22-90 Hz), the spectral
  centroid over time, the .gpw header (priority, mode one-shot/loop, volume, random-pitch), and a SUGGESTED haptic
  mapping (shaker carrier + envelope, pad motor + envelope, wheel transient amplitude) - never applied automatically.
  Plus a spectrogram PNG (0-400 Hz) and design/out/analysis/index.json.

CAVEAT (written into every file): the stock effects are 8-bit, 11,025 Hz mono, so content under ~40 Hz is the 1997
designers' INTENT seen through a lossy medium, not a measured truth; the engine re-pitches one-shots x0.80..1.16 at
random and the engine loop continuously with rpm (SOUND-INTERPOSER-REVIEW 3.2), so carriers are suggestions.

  python design/gpw_spectra.py                # the 123 .gpw
  python design/gpw_spectra.py --wav          # + the .wav set (mostly CB speech; slower)
  python design/gpw_spectra.py --only vvch    # name filter
"""
import argparse, os, sys

import numpy as np

from common import OUT, decode_sound, spectrogram_png, write_json, zfs_sounds

BANDS = [(0, 20), (20, 40), (40, 80), (80, 160), (160, 320), (320, 1000), (1000, 1e9)]
SHAKER = (22.0, 90.0)
RIG_PEAK_HZ = 35.0          # rigs/desk-t300-evo4.json resp curve peak (ffb-lfe-sweep.ps1)
CAVEAT = ("8-bit 11,025 Hz mono source: energy under ~40 Hz is design intent through a lossy medium, not a measurement; "
          "one-shots are re-pitched x0.80..1.16 at random and engine loops track rpm, so frequencies are suggestions.")


def band_name(lo, hi):
    return "%d-%d" % (lo, hi) if hi < 1e8 else ">%d" % lo


def analyse(meta, rate, x):
    x = np.asarray(x, float)
    x = x - x.mean() if len(x) else x
    n = len(x)
    win = max(1, int(round(rate * 0.010)))
    nw = max(1, n // win)
    rms = np.sqrt(np.mean(x[:nw * win].reshape(nw, win) ** 2, axis=1)) if n >= win else np.array([np.sqrt(np.mean(x ** 2))])
    peak = float(rms.max()) if rms.size else 0.0
    env = (rms / peak).round(4) if peak > 0 else rms
    on = int(np.argmax(env > 0.10)) * 10 if peak > 0 else 0
    pk = int(np.argmax(env)) * 10
    above = np.where(env >= 0.7)[0]
    hold = (above[-1] - above[0] + 1) * 10 if above.size else 0
    tail = np.where(env[int(above[-1]) if above.size else 0:] < 0.10)[0]
    decay = int(tail[0]) * 10 if tail.size else (len(env) - (int(above[-1]) if above.size else 0)) * 10
    db = 20 * np.log10(rms + 1e-9)
    emphasis = [int(i * 10) for i in range(3, len(db)) if db[i] - db[i - 3] > 6.0 and env[i] > 0.3]
    # spectrum: zero-padded FFT of the whole sound (resolution <= 1.35 Hz)
    nfft = 1 << max(13, int(np.ceil(np.log2(max(n, 2)))))
    spec = np.abs(np.fft.rfft(x * np.hanning(n) if n > 1 else x, nfft)) ** 2
    f = np.fft.rfftfreq(nfft, 1.0 / rate)
    total = float(spec[1:].sum()) or 1e-30
    bands = {band_name(lo, hi): round(float(spec[(f >= lo) & (f < hi)].sum()) / total, 6) for lo, hi in BANDS}
    m = (f >= SHAKER[0]) & (f <= SHAKER[1])
    peak_hz = float(f[m][np.argmax(spec[m])]) if m.any() and spec[m].max() > 0 else None
    shaker_frac = float(spec[m].sum()) / total
    # centroid over time (93 ms frames, 20 ms hop)
    fw, hop = 1024, max(1, int(rate * 0.020))
    cent = []
    for i in range(0, max(1, n - fw + 1), hop):
        seg = x[i:i + fw]
        if len(seg) < fw:
            seg = np.pad(seg, (0, fw - len(seg)))
        s = np.abs(np.fft.rfft(seg * np.hanning(fw)))
        ff = np.fft.rfftfreq(fw, 1.0 / rate)
        cent.append(round(float((s * ff).sum() / s.sum()), 1) if s.sum() > 0 else 0.0)
    cmean = float(np.mean(cent)) if cent else 0.0
    loop = meta.get("gas", {}).get("mode", 0) in (1, 2)
    low_frac = float(spec[(f > 0) & (f < 160)].sum()) / total
    # suggestions (HAPTICS-ARCHITECTURE 2.2 item 2): carrier near the dominant in-band energy, else the rig peak;
    # envelope from the RMS curve; pad motor by how much of the energy is low (weight -> left ERM, texture -> right;
    # the design says "by centroid", but these 8-bit sounds all have bright centroids, so the low fraction separates
    # them better); wheel transient by onset energy.
    lfe_hz = round(peak_hz, 1) if peak_hz and shaker_frac > 0.01 else RIG_PEAK_HZ
    sugg = {
        "kind": "continuous" if loop else "transient",
        "lfe": {"hz": max(25.0, min(80.0, lfe_hz)), "hz_source": "in-band peak" if lfe_hz != RIG_PEAK_HZ else "rig peak (little in-band energy)",
                "amp": round(min(0.9, 0.35 + 3.0 * shaker_frac), 2), "env": [float(v) for v in env[:150:2]]},
        "pad": {"motor": "L" if low_frac > 0.30 else "R", "why": "%.0f%% of the energy under 160 Hz (L = heavy motor above 30%%); centroid %.0f Hz" % (100 * low_frac, cmean),
                "attack_ms": max(0, pk - on), "hold_ms": int(hold), "decay_ms": int(min(decay, 600)), "min_pulse_ms_ok": bool(hold + decay >= 40)},
        "wheel": {"transient_amp": round(float(min(1.0, peak * 2.5)), 2), "shape": "jolt" if low_frac > 0.30 else "buzz"},
        "status": "suggested - never applied automatically",
    }
    return {
        **meta, "duration_s": round(n / rate, 4), "rms_10ms": [float(v) for v in env], "peak_rms": round(peak, 4),
        "onset_ms": on, "peak_ms": pk, "emphasis_ms": [int(v) for v in emphasis[:20]], "bands": bands, "shaker_band_fraction": round(shaker_frac, 6),
        "peak_hz_in_band": round(peak_hz, 2) if peak_hz else None, "centroid_hz": cent[:200], "centroid_mean_hz": round(cmean, 1),
        "suggested": sugg, "caveats": CAVEAT,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wav", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=os.path.join(OUT, "analysis"))
    a = ap.parse_args()
    kinds = (".gpw", ".wav") if a.wav else (".gpw",)
    sounds = zfs_sounds(kinds)
    index = {}
    for name in sorted(sounds):
        if a.only and a.only not in name:
            continue
        try:
            meta, rate, x = decode_sound(name, sounds[name])
            r = analyse(meta, rate, x)
        except Exception as ex:
            print("  skip %s: %s" % (name, ex))
            continue
        stem = r["name"] + ("" if name.endswith(".gpw") else ".wav")
        write_json(os.path.join(a.out, stem + ".json"), r)
        spectrogram_png(os.path.join(a.out, stem + ".png"), x, rate)
        index[stem] = {k: r[k] for k in ("duration_s", "rate", "bits", "peak_hz_in_band", "shaker_band_fraction", "centroid_mean_hz", "onset_ms")}
        index[stem]["mode"] = r.get("gas", {}).get("mode")
        index[stem]["suggested_lfe_hz"] = r["suggested"]["lfe"]["hz"]
        index[stem]["suggested_pad_motor"] = r["suggested"]["pad"]["motor"]
    write_json(os.path.join(a.out, "index.json"), {"caveats": CAVEAT, "sounds": index})
    print("analysed %d sounds -> %s" % (len(index), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
