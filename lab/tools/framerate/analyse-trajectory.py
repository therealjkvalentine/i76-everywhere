#!/usr/bin/env python3
"""analyse-trajectory.py - do two runs from the same spawn, with the same held input, follow
the same path?

    python tools/analyse-trajectory.py captures/air/traj20.csv captures/air/traj60.csv

This is the strongest whole-system test available without a save state. Both runs start from an
identical melee spawn and hold the throttle key, nothing else. If the simulation is genuinely
frame-rate independent, the two cars trace the same route over the same terrain and the
distance between them stays near zero. Where they part company is where a frame-coupled system
lives, and WHEN they part says which one - a split at the first jump implicates contact and
suspension, a slow drift implicates steering or drag.

Divergence is reported against WALL-CLOCK time, since that is the thing the two runs share.
"""
import sys, csv, math


def load(p):
    with open(p, newline="") as f:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    out = []
    for r in rows:
        if not out or r["frame"] != out[-1]["frame"]:
            out.append(r)
    return out


def at_time(rows, t):
    """Linear interpolation of the sample nearest wall-clock time t."""
    if t <= rows[0]["t"]:
        return rows[0]
    for i in range(1, len(rows)):
        if rows[i]["t"] >= t:
            a, b = rows[i - 1], rows[i]
            span = b["t"] - a["t"]
            f = 0.0 if span <= 0 else (t - a["t"]) / span
            return {k: a[k] + (b[k] - a[k]) * f for k in a}
    return rows[-1]


def main():
    A, B = load(sys.argv[1]), load(sys.argv[2])
    fa = (A[-1]["frame"] - A[0]["frame"]) / A[-1]["t"]
    fb = (B[-1]["frame"] - B[0]["frame"]) / B[-1]["t"]
    print("run A: %.1f fps, %d frames logged" % (fa, len(A)))
    print("run B: %.1f fps, %d frames logged" % (fb, len(B)))
    print("spawn A (%.1f, %.1f, %.1f)   spawn B (%.1f, %.1f, %.1f)\n"
          % (A[0]["px"], A[0]["py"], A[0]["pz"], B[0]["px"], B[0]["py"], B[0]["pz"]))

    end = min(A[-1]["t"], B[-1]["t"])
    print("%-7s %-24s %-24s %-9s %-8s %s"
          % ("t", "A (x, y, z)", "B (x, y, z)", "sep", "dspeed", "dpitch"))
    t = 0.0
    first_big = None
    while t <= end:
        a, b = at_time(A, t), at_time(B, t)
        sep = math.sqrt((a["px"] - b["px"]) ** 2 + (a["py"] - b["py"]) ** 2 + (a["pz"] - b["pz"]) ** 2)
        if first_big is None and sep > 5.0:
            first_big = t
        print("%-7.1f (%8.1f,%6.1f,%9.1f) (%8.1f,%6.1f,%9.1f) %-9.2f %-8.2f %.2f"
              % (t, a["px"], a["py"], a["pz"], b["px"], b["py"], b["pz"],
                 sep, a["speed"] - b["speed"], a["pitch"] - b["pitch"]))
        t += 1.0

    print("\ndistance travelled: A %.1f m, B %.1f m"
          % (math.dist((A[0]["px"], A[0]["pz"]), (A[-1]["px"], A[-1]["pz"])),
             math.dist((B[0]["px"], B[0]["pz"]), (B[-1]["px"], B[-1]["pz"]))))
    if first_big is None:
        print("paths stayed within 5 m for the whole run - simulation matches across frame rates")
    else:
        print("paths first separated by more than 5 m at t = %.1f s" % first_big)


if __name__ == "__main__":
    main()
