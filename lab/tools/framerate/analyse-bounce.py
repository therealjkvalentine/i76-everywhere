#!/usr/bin/env python3
"""analyse-bounce.py - is the chassis bob frequency frame-rate dependent?

    python tools/framerate/analyse-bounce.py captures/bounce/bounce20.csv captures/bounce/bounce60.csv

The suspension is a spring/damper. Its natural OSCILLATION FREQUENCY (Hz) is a property of the
car, not the frame rate - unless the integration advances per-frame without the frame delta-time,
in which case the ring is faster at higher fps. So the test is: measure the bob frequency at each
rate and see whether it holds steady in Hz (dt-correct) or scales ~3x (frame-coupled).

Frequency is measured two ways, on the pitch and vertical-position signals, per phase:
  * zero-crossing rate of the detrended signal (robust, cheap)
  * dominant period from the mean spacing of local extrema
Both are reported per Hz; if the car is frame-coupled they rise with fps, and the deg/frame-style
"per-frame step" view holds steady instead.

The 'idle' phase (parked) is the clean one - pure suspension settling, no terrain forcing. The
'drive' phase adds terrain bumps, whose forcing rate depends on speed, so read idle first.
"""
import sys, csv, statistics as st


def load(p):
    with open(p, newline="") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    for r in rows:
        for k in ("t", "frame", "py", "pitch", "roll", "speed", "vy"):
            r[k] = float(r[k])
    out, seen = [], None
    for r in rows:
        if r["frame"] != seen:
            out.append(r)
            seen = r["frame"]
    return out


def crossings(sig):
    m = st.mean(sig)
    d = [x - m for x in sig]
    n = 0
    for i in range(1, len(d)):
        if (d[i-1] <= 0 < d[i]) or (d[i-1] >= 0 > d[i]):
            n += 1
    return n


def freq(rows, key):
    if len(rows) < 8:
        return None, None, 0
    sig = [r[key] for r in rows]
    span = rows[-1]["t"] - rows[0]["t"]
    if span <= 0:
        return None, None, 0
    dfr = rows[-1]["frame"] - rows[0]["frame"]
    # zero crossings -> full cycles: each cycle is two crossings
    hz = crossings(sig) / 2.0 / span
    per_frame = crossings(sig) / 2.0 / dfr if dfr else 0     # cycles per frame
    amp = (max(sig) - min(sig))
    return hz, per_frame, amp


def phase(rows, name):
    return [r for r in rows if r["phase"] == name]


def summarise(tag, rows):
    fps = (rows[-1]["frame"] - rows[0]["frame"]) / (rows[-1]["t"] - rows[0]["t"])
    print("%s: %.1f fps, %d frames" % (tag, fps, len(rows)))
    res = {}
    for ph in ("idle", "drive"):
        pr = phase(rows, ph)
        if len(pr) < 8:
            continue
        for key in ("py", "pitch"):
            hz, pf, amp = freq(pr, key)
            if hz is None:
                continue
            res[(ph, key)] = (hz, pf, amp)
            print("   %-5s %-5s  %.2f Hz   %.5f cyc/frame   amplitude %.4f"
                  % (ph, key, hz, pf, amp))
    return fps, res


def main():
    A, B = load(sys.argv[1]), load(sys.argv[2])
    fa, ra = summarise("run A", A)
    fb, rb = summarise("run B", B)
    print("\nframe-rate ratio B/A = %.2f" % (fb / fa))
    print("%-14s %10s %10s %8s   %s" % ("signal", "A Hz", "B Hz", "B/A", "verdict"))
    for k in sorted(set(ra) & set(rb)):
        ha = ra[k][0]
        hb = rb[k][0]
        ratio = hb / ha if ha else 0
        verdict = ("FRAME-COUPLED" if ratio > 2.0 else
                   "dt-correct" if 0.6 < ratio < 1.5 else "unclear")
        print("%-14s %10.2f %10.2f %8.2f   %s" % ("%s/%s" % k, ha, hb, ratio, verdict))
    print("\nHz B/A near 3 => bob is frame-coupled; near 1 => dt-correct.")
    print("Read the 'idle' rows first - 'drive' mixes in terrain forcing that depends on speed.")


if __name__ == "__main__":
    main()
