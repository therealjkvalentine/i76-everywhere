#!/usr/bin/env python3
"""ratio-scan.py - find globals whose VALUE scales with the frame rate.

Feed it two snap-static.ps1 dumps taken at different frame rates and it reports every dword
whose 20 Hz value divided by its 60 Hz value is close to 3 (or 1/3). That is the signature of
a frame delta-time: dt = 0.05 at 20 Hz, 0.0167 at 60 Hz. The reciprocal form (a stored frames-
per-second, 20 vs 60) shows up in the inverse list.

    python tools/ratio-scan.py captures/snap/at20.bin captures/snap/at60.bin [-base 0x400000]

Both float and integer interpretations are checked. Values are filtered to plausible ranges so
the output is a short list rather than every coincidence in 5 MB.
"""
import sys, struct, math

def load(p):
    return open(p, "rb").read()

def main():
    a_path, b_path = sys.argv[1], sys.argv[2]
    base = 0x400000
    if "-base" in sys.argv:
        base = int(sys.argv[sys.argv.index("-base") + 1], 16)
    A, B = load(a_path), load(b_path)
    n = min(len(A), len(B)) // 4
    print("scanning %d dwords from 0x%X" % (n, base))

    direct, inverse = [], []
    for i in range(n):
        o = i * 4
        if A[o:o + 4] == B[o:o + 4]:
            continue                      # identical -> not frame-rate dependent
        fa = struct.unpack_from("<f", A, o)[0]
        fb = struct.unpack_from("<f", B, o)[0]
        # dt-shaped: small positive float, 3x smaller in the faster run
        if (math.isfinite(fa) and math.isfinite(fb) and
                1e-4 < fb < 0.5 and 1e-4 < fa < 0.5 and fb != 0):
            r = fa / fb
            if 2.5 < r < 3.6:
                direct.append((base + o, fa, fb, r, "float"))
        # fps-shaped: a stored rate, 3x LARGER in the faster run (float or int)
        if (math.isfinite(fa) and math.isfinite(fb) and
                5 < fa < 400 and 5 < fb < 400 and fa != 0):
            r = fb / fa
            if 2.5 < r < 3.6:
                inverse.append((base + o, fa, fb, r, "float"))
        ia = struct.unpack_from("<i", A, o)[0]
        ib = struct.unpack_from("<i", B, o)[0]
        if 5 < ia < 400 and 5 < ib < 400:
            r = ib / ia
            if 2.5 < r < 3.6:
                inverse.append((base + o, ia, ib, r, "int"))

    def show(title, rows):
        print("\n%s  (%d hits)" % (title, len(rows)))
        print("%-12s %-16s %-16s %-7s %s" % ("addr", "slow-run", "fast-run", "ratio", "as"))
        for addr, x, y, r, kind in rows[:60]:
            print("0x%08X   %-16.6g %-16.6g %-7.3f %s" % (addr, x, y, r, kind))

    show("DT-SHAPED  (value 3x SMALLER at 60 Hz)", direct)
    show("RATE-SHAPED (value 3x LARGER at 60 Hz)", inverse)


if __name__ == "__main__":
    main()
