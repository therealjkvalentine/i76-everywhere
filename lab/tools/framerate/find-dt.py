#!/usr/bin/env python3
"""find-dt.py - locate the engine's frame delta-time global.

Weaker tests failed here, so this uses the strongest available signature. A delta-time does not
merely scale with frame rate (any per-frame delta does that, and out of 1.3M dwords a handful
will scale by 3x purely by chance). A delta-time SITS AT 1/rate on every single frame. So:

  * take several snapshots during a 20 Hz run, keep dwords whose float value is within a few
    percent of 0.05 in EVERY snapshot;
  * do the same for a 60 Hz run against 0.0167;
  * the answer is in the intersection of the two address sets.

A value that is merely noisy, or constant-but-arbitrary, cannot survive both bands.

    python tools/find-dt.py --fps20 captures/snap/dt20_*.bin --fps60 captures/snap/dt60_*.bin
"""
import sys, struct, glob

BASE = 0x400000
TOL = 0.12          # +/-12%: enough slack for a frame-time that jitters, far too tight for noise


def surviving(paths, target, tol=TOL):
    """Addresses whose float value is within tol of target in every snapshot."""
    lo, hi = target * (1 - tol), target * (1 + tol)
    keep = None
    for p in paths:
        blob = open(p, "rb").read()
        here = set()
        for o in range(0, len(blob) - 3, 4):
            v = struct.unpack_from("<f", blob, o)[0]
            if lo < v < hi:
                here.add(o)
        keep = here if keep is None else (keep & here)
        print("  %-28s %7d in band, %7d surviving" % (p.split("\\")[-1], len(here), len(keep)))
    return keep or set()


def main():
    a = sys.argv
    p20 = [x for x in a[a.index("--fps20") + 1: a.index("--fps60")]]
    p60 = [x for x in a[a.index("--fps60") + 1:]]
    p20 = sorted(sum([glob.glob(x) for x in p20], []))
    p60 = sorted(sum([glob.glob(x) for x in p60], []))
    print("20 Hz run (looking for ~0.0500):")
    s20 = surviving(p20, 1.0 / 20.0)
    print("60 Hz run (looking for ~0.0167):")
    s60 = surviving(p60, 1.0 / 60.0)
    both = sorted(s20 & s60)
    print("\n%d address(es) hold 1/rate at BOTH frame rates:" % len(both))
    for o in both:
        v20 = struct.unpack_from("<f", open(p20[0], "rb").read(), o)[0]
        v60 = struct.unpack_from("<f", open(p60[0], "rb").read(), o)[0]
        print("  0x%08X   20Hz=%.6f   60Hz=%.6f   ratio=%.3f" % (BASE + o, v20, v60, v20 / v60))
    if not both:
        print("  (none - the frame delta-time is not a static global; it is computed and passed)")


if __name__ == "__main__":
    main()
