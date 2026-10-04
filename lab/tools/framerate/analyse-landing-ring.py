#!/usr/bin/env python3
"""analyse-landing-ring.py - measure the suspension ring after each landing.

The naive "idle/drive bob" test was confounded (a parked car just creeps down the slope; a
driving car is forced by terrain at a speed-dependent rate). The clean signal is an IMPULSE
response: when the car lands from a jump the suspension compresses and RINGS as it settles, and
that ring frequency is a property of the spring/damper - unless it is integrated per-frame, in
which case it rings faster at higher fps.

A landing is where vertical speed goes from clearly falling (vy < -3) back to ~0. After each,
the pitch decays in an oscillation; the ring frequency comes from the spacing of its extrema in
the ~0.8 s window following touchdown. Frequencies are pooled across all landings in the run.

    python tools/framerate/analyse-landing-ring.py captures/bounce/bounce20.csv captures/bounce/bounce60.csv
"""
import sys, csv, statistics as st


def load(p):
    with open(p, newline="") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    for r in rows:
        for k in ("t", "frame", "pitch", "vy"):
            r[k] = float(r[k])
    # bounce-test files have a 'drive' phase; airborne-test files have no phase column
    if rows and "phase" in rows[0]:
        rows = [r for r in rows if r["phase"] == "drive"]
    out, seen = [], None
    for r in rows:
        if r["frame"] != seen:
            out.append(r)
            seen = r["frame"]
    return out


def landings(rows):
    """indices where vy recovers from < -3 to > -0.5 (touchdown)."""
    idx = []
    for i in range(1, len(rows)):
        if rows[i-1]["vy"] < -3.0 and rows[i]["vy"] > -0.5:
            idx.append(i)
    return idx


def ring_freq(rows, i0):
    """dominant frequency of pitch in the ~0.8 s after touchdown, from extrema spacing."""
    t0 = rows[i0]["t"]
    seg = [r for r in rows if t0 <= r["t"] <= t0 + 0.8]
    if len(seg) < 6:
        return None
    p = [r["pitch"] for r in seg]
    t = [r["t"] for r in seg]
    # local extrema
    ex = []
    for k in range(1, len(p) - 1):
        if (p[k] - p[k-1]) * (p[k+1] - p[k]) < 0:
            ex.append(t[k])
    if len(ex) < 3:
        return None
    halfperiods = [ex[k] - ex[k-1] for k in range(1, len(ex))]
    mean_hp = st.mean(halfperiods)
    if mean_hp <= 0:
        return None
    return 0.5 / mean_hp        # extrema are half a period apart


def summarise(tag, rows):
    fps = (rows[-1]["frame"] - rows[0]["frame"]) / (rows[-1]["t"] - rows[0]["t"])
    ls = landings(rows)
    freqs = [f for f in (ring_freq(rows, i) for i in ls) if f]
    print("%s: %.1f fps, %d landings, %d with a measurable ring"
          % (tag, fps, len(ls), len(freqs)))
    if freqs:
        print("   ring frequency: median %.2f Hz, mean %.2f Hz (%s)"
              % (st.median(freqs), st.mean(freqs),
                 ", ".join("%.1f" % f for f in sorted(freqs))))
    return fps, (st.median(freqs) if freqs else None)


def summarise_pool(tag, paths):
    """pool landings across several independent runs (each file keeps its own clock/frames)."""
    freqs, nland, fps_list = [], 0, []
    for p in paths:
        rows = load(p)
        if len(rows) < 8:
            continue
        fps_list.append((rows[-1]["frame"] - rows[0]["frame"]) / (rows[-1]["t"] - rows[0]["t"]))
        ls = landings(rows)
        nland += len(ls)
        freqs += [f for f in (ring_freq(rows, i) for i in ls) if f]
    fps = st.mean(fps_list) if fps_list else 0
    print("%s: %.1f fps, %d files, %d landings, %d rings" % (tag, fps, len(paths), nland, len(freqs)))
    if freqs:
        print("   ring frequency: median %.2f Hz, mean %.2f Hz over %d rings"
              % (st.median(freqs), st.mean(freqs), len(freqs)))
    return fps, (st.median(freqs) if freqs else None)


def main():
    # accept comma-separated file lists per side to pool landings
    pa = sys.argv[1].split(",")
    pb = sys.argv[2].split(",")
    if len(pa) > 1 or len(pb) > 1:
        fa, ma = summarise_pool("run A", pa)
        fb, mb = summarise_pool("run B", pb)
    else:
        fa, ma = summarise("run A", load(pa[0]))
        fb, mb = summarise("run B", load(pb[0]))
    if ma and mb:
        print("\nframe-rate ratio B/A = %.2f" % (fb / fa))
        print("ring Hz  A %.2f  B %.2f  -> B/A = %.2f  =>  %s"
              % (ma, mb, mb / ma,
                 "FRAME-COUPLED" if mb / ma > 2 else
                 "dt-correct" if 0.6 < mb / ma < 1.5 else "unclear"))
    else:
        print("\nnot enough clean landings - capture a run with more airtime (Dunes/Crater, hold W).")


if __name__ == "__main__":
    main()
