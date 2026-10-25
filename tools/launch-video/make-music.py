#!/usr/bin/env python3
"""make-music.py - the royalty-free soundtrack for the launch video: a 1970s-funk groove synthesised from scratch (numpy only,
no samples, no third-party audio). Written for this project; released CC0 1.0 (public domain dedication) like any output of
this script. The cut that carries the game's own theme is the separate '-theme' render (docs/LAUNCH-VIDEO-2026-10-25.md s.3).

  python make-music.py --out groove.wav --seconds 95 [--bpm 104] [--seed 76]

Structure (bars of 4/4): intro (drums + bass) 4, groove A 8, break 2, groove B (stabs + lead) 8, then A/B again to the length,
last 2 s faded. Key E minor (E dorian riffs)."""
import argparse, wave
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--seconds", type=float, default=95)
ap.add_argument("--bpm", type=float, default=104)
ap.add_argument("--seed", type=int, default=76)
a = ap.parse_args()
SR = 48000
rng = np.random.default_rng(a.seed)
N = int(a.seconds * SR)
L = np.zeros(N); R = np.zeros(N)
beat = 60.0 / a.bpm
s16 = beat / 4


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12.0)


def env(n, att=0.002, dec=0.2, sus=0.0, rel=0.05, hold=None):
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(att, 1e-4))
    d = np.exp(-np.maximum(0, t - att) / max(dec, 1e-4)) * (1 - sus) + sus
    e = e * d
    if hold is not None:
        r = np.clip(1 - (t - hold) / rel, 0, 1)
        e = e * np.where(t > hold, r, 1)
    return e


def add(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    R[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def lp(x, cut):  # one-pole low pass, cut Hz (array or scalar)
    y = np.zeros_like(x); k = 1 - np.exp(-2 * np.pi * np.broadcast_to(cut, x.shape) / SR); z = 0.0
    for i in range(len(x)):
        z += k[i] * (x[i] - z); y[i] = z
    return y


def kick():
    n = int(0.35 * SR); t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t / 0.03)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.18) * 0.9


def snare():
    n = int(0.25 * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 190 * t) * env(n, 0.001, 0.05) * 0.4
    nz = rng.standard_normal(n); nz = nz - lp(nz, 1500)
    return body + nz * env(n, 0.001, 0.09) * 0.35


def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    nz = rng.standard_normal(n); nz = nz - lp(nz, 7000)
    return nz * env(n, 0.0005, 0.12 if open_ else 0.02) * 0.18


def bass(note, dur):
    n = int(dur * SR); t = np.arange(n) / SR; f = midi(note)
    saw = 2 * ((t * f) % 1) - 1
    sq = np.sign(np.sin(2 * np.pi * f * t))
    x = 0.6 * saw + 0.4 * sq
    cut = 300 + 1400 * np.exp(-t / 0.06)
    return lp(x, cut) * env(n, 0.003, 0.25, 0.5, 0.03, hold=dur * 0.85) * 0.55


def stab(notes, dur, wah):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for m in notes:
        f = midi(m)
        for det in (-0.004, 0.004):
            x += 2 * ((t * f * (1 + det)) % 1) - 1
    x /= 2 * len(notes)
    cut = 600 + 2600 * wah * np.exp(-t / 0.08)
    return lp(x, cut) * env(n, 0.002, 0.15, 0.2, 0.03, hold=dur * 0.8) * 0.5


def lead(note, dur):
    n = int(dur * SR); t = np.arange(n) / SR; f = midi(note)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.15, 0, 1)
    ph = np.cumsum(f * vib) / SR
    x = 0.5 * (2 * (ph % 1) - 1) + 0.5 * (2 * ((ph * 1.003) % 1) - 1)
    return lp(x, 2400) * env(n, 0.02, 0.4, 0.6, 0.06, hold=dur * 0.9) * 0.28


K, S = kick(), snare()
# E dorian riffs, 16 steps per bar: (step, midi, length in 16ths)
riffA = [(0, 40, 2), (3, 40, 1), (4, 43, 2), (6, 45, 1), (8, 40, 2), (10, 47, 1), (11, 45, 1), (12, 43, 2), (14, 38, 2)]
riffB = [(0, 45, 2), (3, 45, 1), (4, 48, 2), (6, 50, 1), (8, 45, 2), (10, 52, 1), (11, 50, 1), (12, 47, 2), (14, 43, 2)]
chordsA = [64, 67, 71, 74]   # Em9-ish
chordsB = [69, 72, 76, 79]   # Am9-ish
melody = [(0, 76, 3), (4, 79, 2), (6, 81, 2), (8, 79, 4), (14, 76, 2), (16, 74, 2), (18, 76, 2), (20, 71, 6), (28, 74, 4)]

bar = 16 * s16
nbars = int(a.seconds / bar) + 1
plan = []
for b in range(nbars):
    if b < 4:
        plan.append("intro")
    elif b < 12:
        plan.append("A")
    elif b < 14:
        plan.append("break")
    else:
        plan.append("B" if ((b - 14) // 8) % 2 == 0 else "A")
for b, part in enumerate(plan):
    t0 = b * bar
    swing = lambda st: t0 + st * s16 + (0.018 if st % 2 else 0.0)
    if part != "break":
        for st in (0, 8, 10):
            add(K, swing(st), 0, 1.0 if st != 10 else 0.6)
        for st in (4, 12):
            add(S, swing(st), 0.05)
        for st in range(0, 16, 2):
            add(hat(st == 14), swing(st), 0.3, 0.9 if st % 4 == 0 else 0.6)
        add(hat(), swing(15), 0.3, 0.4)
    else:
        add(S, swing(12), 0.05); add(S, swing(14), 0.05); add(S, swing(15), 0.05, 0.7)
    riff = riffB if (part == "B" and b % 2 == 1) else riffA
    if part in ("intro", "A", "B"):
        for st, m, ln in riff:
            add(bass(m, ln * s16), swing(st), -0.05)
    if part in ("A", "B"):
        ch = chordsB if b % 4 == 3 else chordsA
        for st in (2, 6, 11):
            add(stab(ch, 1.5 * s16, 0.7 + 0.3 * rng.random()), swing(st), -0.35, 0.9)
    if part == "B" and b % 2 == 0:
        for st, m, ln in melody:
            add(lead(m, ln * s16), swing(st), 0.25)

mix = np.stack([L, R], 1)
# gentle room: two short taps
for d, g in ((0.031, 0.18), (0.047, 0.12)):
    k = int(d * SR); mix[k:, 0] += mix[:-k, 1] * g; mix[k:, 1] += mix[:-k, 0] * g
fade = int(2.0 * SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix = np.tanh(mix * 1.4) / np.tanh(1.4)
mix *= 0.89 / max(1e-9, np.abs(mix).max())
with wave.open(a.out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("make-music: %s %.1f s, %d bpm, CC0" % (a.out, a.seconds, a.bpm))
