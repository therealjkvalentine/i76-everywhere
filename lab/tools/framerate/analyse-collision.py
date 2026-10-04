#!/usr/bin/env python3
"""analyse-collision.py - is the collision HIT RATE frame-rate dependent?

    python tools/framerate/analyse-collision.py captures/collision/coll20.csv captures/collision/coll60.csv

The bug is probabilistic (~2/3 pass-through at 60 fps), so the statistic is a RATE over repeated
identical approaches, not a single outcome. For each pass, an impact is a sharp speed loss while
grounded; passes with no such event drove through whatever was in the way.

Reported per frame rate:
  * impacts per 100 m travelled  - the density-normalised figure, so a run that happened to
    cover more ground is not credited with more collisions
  * mean speed lost per impact   - if hits still register but bleed less speed, the solver is
    under-applying the impulse rather than missing the object entirely

Both matter: "misses the object" and "hits it too softly" are different bugs with different fixes.
"""
import sys, csv, math, statistics as st

WINDOW = 0.25      # seconds over which a speed drop counts as an impact
GROUND_VY = 2.0    # |vertical speed| above this means airborne - not a ground collision


def load(p):
    with open(p, newline="") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    for r in rows:
        for k in ("t", "speed", "vy", "px", "py", "pz", "frame", "pass"):
            r[k] = float(r[k])
    # one row per frame, per (pass, leg) - the sampler is faster than the game draws
    out, seen = [], None
    for r in rows:
        key = (r["pass"], r["leg"], r["frame"])
        if key != seen:
            out.append(r)
            seen = key
    return out


def legs(rows):
    """split into (pass, leg) runs."""
    groups, cur, key = [], [], None
    for r in rows:
        k = (r["pass"], r["leg"])
        if k != key:
            if cur:
                groups.append(cur)
            cur, key = [], k
        cur.append(r)
    if cur:
        groups.append(cur)
    return groups


def impacts(leg):
    """sharp grounded speed losses; returns list of speed-lost values."""
    hits = []
    i = 0
    while i < len(leg):
        j = i
        while j < len(leg) - 1 and (leg[j + 1]["t"] - leg[i]["t"]) <= WINDOW:
            j += 1
        drop = leg[i]["speed"] - leg[j]["speed"]
        grounded = abs(leg[i]["vy"]) < GROUND_VY and abs(leg[j]["vy"]) < GROUND_VY
        if drop >= 4.0 and grounded and leg[i]["speed"] > 6.0:
            hits.append(drop)
            i = j + 1          # don't double-count the same impact
        else:
            i += 1
    return hits


def dist(leg):
    return sum(math.dist((leg[i - 1]["px"], leg[i - 1]["pz"]), (leg[i]["px"], leg[i]["pz"]))
               for i in range(1, len(leg)))


def summarise(tag, rows):
    fps = (rows[-1]["frame"] - rows[0]["frame"]) / sum(
        g[-1]["t"] - g[0]["t"] for g in legs(rows))
    all_hits, total_d, n_legs, legs_with_hit = [], 0.0, 0, 0
    for g in legs(rows):
        h = impacts(g)
        d = dist(g)
        if d < 5:
            continue
        n_legs += 1
        total_d += d
        all_hits += h
        if h:
            legs_with_hit += 1
    per100 = 100.0 * len(all_hits) / total_d if total_d else float("nan")
    print("%s: %.1f fps, %d legs, %.0f m driven" % (tag, fps, n_legs, total_d))
    print("   impacts: %d   (%.2f per 100 m)" % (len(all_hits), per100))
    print("   legs with >=1 impact: %d/%d (%.0f%%)"
          % (legs_with_hit, n_legs, 100.0 * legs_with_hit / n_legs if n_legs else 0))
    if all_hits:
        print("   speed lost per impact: mean %.1f, median %.1f m/s"
              % (st.mean(all_hits), st.median(all_hits)))
    return fps, per100, (st.mean(all_hits) if all_hits else float("nan"))


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    fa, pa, ma = summarise("run A", a)
    print()
    fb, pb, mb = summarise("run B", b)
    print("\nframe-rate ratio B/A = %.2f" % (fb / fa))
    print("impacts per 100 m   A %.2f  B %.2f   -> B/A = %.2f" % (pa, pb, pb / pa if pa else 0))
    print("speed lost / impact A %.1f  B %.1f   -> B/A = %.2f" % (ma, mb, mb / ma if ma else 0))
    print("\nreading: impacts/100 m much LOWER at the higher rate => objects are being missed")
    print("         (pass-through). Similar rate but lower speed-lost => impulse under-applied.")
    print("NOTE: this needs the SAME route at both rates. Spawn/heading vary between launches,")
    print("      so treat a single pair as indicative and repeat before concluding.")


if __name__ == "__main__":
    main()
