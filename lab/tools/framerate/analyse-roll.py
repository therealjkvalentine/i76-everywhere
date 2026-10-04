#!/usr/bin/env python3
"""analyse-roll.py - compare chassis roll step responses taken at two frame rates.

    python tools/analyse-roll.py captures/roll/roll20.csv captures/roll/roll60.csv

The question is whether roll is integrated with the frame delta-time or with a fixed per-frame
constant. Two readings decide it:

  * TIME to reach a given roll angle. dt-correct -> equal in seconds at both rates.
    Frame-coupled -> ~3x sooner at 60 Hz.
  * FRAMES to reach it. Frame-coupled -> equal frame counts at both rates.

Reporting both matters because either one alone can be explained away; together they point one
way. Speed is printed too, since roll follows lateral acceleration and a speed mismatch between
runs would produce a roll difference that has nothing to do with frame rate.
"""
import sys, csv


def load(p):
    with open(p, newline="") as f:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    f0 = rows[0]["frame"]
    for r in rows:
        r["df"] = r["frame"] - f0
    return rows


def fps(rows):
    return (rows[-1]["frame"] - rows[0]["frame"]) / rows[-1]["t"]


def first_reaching(rows, target):
    """(seconds, frames) at which |drift| first reaches target degrees."""
    for r in rows:
        if abs(r["drift"]) >= target:
            return r["t"], r["df"]
    return None, None


def main():
    A, B = load(sys.argv[1]), load(sys.argv[2])
    fa, fb = fps(A), fps(B)
    print("run A: %.1f fps, %d samples, speed %.1f->%.1f m/s"
          % (fa, len(A), A[0]["speed"], A[-1]["speed"]))
    print("run B: %.1f fps, %d samples, speed %.1f->%.1f m/s"
          % (fb, len(B), B[0]["speed"], B[-1]["speed"]))
    print("frame-rate ratio B/A = %.2f\n" % (fb / fa))

    print("%-8s %-22s %-22s %-10s %s" % ("roll", "run A (s / frames)", "run B (s / frames)",
                                         "time A/B", "frames B/A"))
    for target in (1, 2, 3, 5, 8, 12):
        ta, na = first_reaching(A, target)
        tb, nb = first_reaching(B, target)
        if ta is None or tb is None:
            print("%-8s %-22s %-22s" % ("%d deg" % target,
                                        "not reached" if ta is None else "%.3f / %d" % (ta, na),
                                        "not reached" if tb is None else "%.3f / %d" % (tb, nb)))
            continue
        print("%-8s %-22s %-22s %-10.2f %.2f"
              % ("%d deg" % target, "%.3f / %d" % (ta, na), "%.3f / %d" % (tb, nb),
                 ta / tb if tb else 0, nb / na if na else 0))

    print("\npeak roll: A %.2f deg, B %.2f deg" % (max(abs(r["drift"]) for r in A),
                                                   max(abs(r["drift"]) for r in B)))
    print("\nreading: 'time A/B' near 1.0 and 'frames B/A' near 3.0 => dt-correct (roll is fine).")
    print("         'time A/B' near 3.0 and 'frames B/A' near 1.0 => FRAME-COUPLED (the bug).")


if __name__ == "__main__":
    main()
