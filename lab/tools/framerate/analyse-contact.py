#!/usr/bin/env python3
"""analyse-contact.py - is the frame-rate speed gap made on the ground, or at landings?

    python tools/analyse-contact.py captures/air/traj20*.csv --vs captures/air/traj60*.csv

Over rough terrain the car covers ~9% less ground at 60 Hz than at 20 Hz. Two very different
causes would produce that, and they are separable in data already captured:

  * if driving itself is slower, mean speed while the wheels are DOWN differs too;
  * if the contact solver is the problem, on-ground driving matches and the difference is
    concentrated in what each landing costs.

The second is the standing hypothesis: the solver runs 3x as often at 60 Hz, so a contact
impulse applied per frame rather than per second lands three times as hard.

Landing cost is measured as speed just before leaving the ground minus speed shortly after
touching down again, so it is a per-event figure and does not depend on how many jumps a
particular run happened to take.
"""
import sys, csv, math, statistics as st

GROUND_VY = 0.5      # |vertical speed| below this counts as running on the ground
AIR_VY = -3.0        # clearly falling
SETTLE = 0.4         # seconds after touchdown before re-reading speed


def load(p):
    with open(p, newline="") as f:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    out = []
    for r in rows:
        if not out or r["frame"] != out[-1]["frame"]:
            out.append(r)
    return out


def ground_speed(rows):
    v = [r["speed"] for r in rows if abs(r["vy"]) < GROUND_VY]
    return (st.mean(v), len(v) / len(rows)) if v else (float("nan"), 0.0)


def landings(rows):
    """Speed lost across each airborne excursion."""
    out, i, n = [], 0, len(rows)
    while i < n:
        if rows[i]["vy"] < AIR_VY:
            start = i
            while start > 0 and abs(rows[start - 1]["vy"]) > GROUND_VY:
                start -= 1
            j = i
            while j < n - 1 and abs(rows[j]["vy"]) > GROUND_VY:
                j += 1
            # speed once the car has settled after touchdown
            t_end = rows[j]["t"] + SETTLE
            k = j
            while k < n - 1 and rows[k]["t"] < t_end:
                k += 1
            before, after = rows[start]["speed"], rows[k]["speed"]
            air_t = rows[j]["t"] - rows[start]["t"]
            if air_t > 0.15 and before > 5:
                out.append({"before": before, "after": after,
                            "loss": before - after, "frac": (before - after) / before,
                            "air": air_t})
            i = k + 1
        else:
            i += 1
    return out


def summarise(tag, paths):
    gs, gf, alll = [], [], []
    for p in paths:
        rows = load(p)
        m, f = ground_speed(rows)
        if not math.isnan(m):
            gs.append(m)
            gf.append(f)
        alll += landings(rows)
    print("%s  (%d runs, %d landings)" % (tag, len(paths), len(alll)))
    print("   mean speed while ON THE GROUND : %.2f m/s (sd %.2f), %.0f%% of frames on ground"
          % (st.mean(gs), st.pstdev(gs), 100 * st.mean(gf)))
    if alll:
        print("   speed lost per landing         : %.2f m/s (sd %.2f)  =  %.1f%% of entry speed"
              % (st.mean([x["loss"] for x in alll]), st.pstdev([x["loss"] for x in alll]),
                 100 * st.mean([x["frac"] for x in alll])))
        print("   mean airtime per landing       : %.2f s" % st.mean([x["air"] for x in alll]))
    return (st.mean(gs), st.mean([x["frac"] for x in alll]) if alll else float("nan"))


def main():
    i = sys.argv.index("--vs")
    A, B = sys.argv[1:i], sys.argv[i + 1:]
    ga, la = summarise("run set A", A)
    gb, lb = summarise("run set B", B)
    print("\non-ground speed   B/A = %.3f" % (gb / ga))
    print("landing loss frac B/A = %.3f" % (lb / la))
    print("\nreading: on-ground ~1.0 with landing loss clearly >1.0 => the contact solver,")
    print("         not driving, is where the frame-rate difference is made.")


if __name__ == "__main__":
    main()
