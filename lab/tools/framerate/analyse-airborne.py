#!/usr/bin/env python3
"""analyse-airborne.py - is mid-air rotation integrated with the frame delta-time?

    python tools/analyse-airborne.py captures/air/air20.csv captures/air/air60.csv

Finds free-fall segments and, within each, compares the attitude change actually observed
against the attitude change the stored angular velocity asks for. The ratio between them is
dimensionless, so jumps of different sizes on different terrain are directly comparable:

    gain = (degrees of pitch actually turned) / (angular velocity in deg/s * seconds elapsed)

  gain ~= 1 at both frame rates  -> rotation is dt-correct
  gain ~= 3x larger at 60 Hz     -> FRAME-COUPLED: the car over-rotates in the air

Free-fall detection reuses the criterion that fixed an earlier false result: a segment must run
at least 5 frames AND lose at least 2 m/s of vertical speed. Without both, suspension jitter on
the ground fits as "free fall" and produces a confident, wrong answer.
"""
import sys, csv, math

# A minimum expressed in FRAMES is not the same test at two frame rates: 5 frames is 0.25 s of
# airtime at 20 Hz but 0.083 s at 60 Hz, so the faster run qualifies on hops the slower run
# never sees. Require the same physical airtime at both rates.
MIN_SECONDS = 0.25
MIN_FRAMES = 3
MIN_DROP = 2.0
GRAVITY_TOL = 3.0      # how far the segment's vertical acceleration may sit from -9.8 m/s^2


def load(p):
    with open(p, newline="") as f:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    # One row per FRAME. The sampler polls faster than the game draws, so at 20 Hz several rows
    # share a frame and carry identical vy. A strictly-decreasing test then breaks on every
    # duplicate and reports "no airborne segments" for a run full of jumps.
    out = []
    for r in rows:
        if not out or r["frame"] != out[-1]["frame"]:
            out.append(r)
    return out


def segments(rows):
    """Contiguous runs where vertical speed only falls - i.e. gravity is the only vertical force."""
    out, i, n = [], 0, len(rows)
    while i < n - 1:
        if rows[i + 1]["vy"] < rows[i]["vy"]:
            j = i
            while j < n - 1 and rows[j + 1]["vy"] < rows[j]["vy"]:
                j += 1
            seg = rows[i:j + 1]
            drop = seg[0]["vy"] - seg[-1]["vy"]
            frames = seg[-1]["frame"] - seg[0]["frame"]
            span = seg[-1]["t"] - seg[0]["t"]
            # Falling is not the same as flying. A car settling on its springs also loses
            # vertical speed, and those frames carry suspension torques that are not free
            # flight - including them produced angular-velocity "decay" of +7.6/s, i.e. spin
            # appearing out of nowhere. Only true ballistic flight accelerates at gravity, so
            # require the segment's vertical acceleration to match g.
            accel = (seg[-1]["vy"] - seg[0]["vy"]) / span if span > 0 else 0
            if frames >= MIN_FRAMES and span >= MIN_SECONDS and drop >= MIN_DROP:
                seg[0]["accel"] = accel
                seg[0]["ballistic"] = abs(accel + 9.8) < GRAVITY_TOL
                out.append(seg)
            i = j + 1
        else:
            i += 1
    return out


def unwrap(a, b):
    d = b - a
    while d > 180:
        d -= 360
    while d < -180:
        d += 360
    return d


def gains(rows):
    """Per-segment (observed degrees turned) / (commanded degrees) for each attitude axis."""
    res = []
    for seg in segments(rows):
        dt = seg[-1]["t"] - seg[0]["t"]
        if dt <= 0:
            continue
        obs_p = abs(unwrap(seg[0]["pitch"], seg[-1]["pitch"]))
        obs_r = abs(unwrap(seg[0]["roll"], seg[-1]["roll"]))
        obs_y = abs(unwrap(seg[0]["yaw"], seg[-1]["yaw"]))
        # mean magnitude of each angular-velocity component over the segment, rad/s -> deg/s
        n = len(seg)
        cx = sum(abs(r["avx"]) for r in seg) / n * 180 / math.pi
        cy = sum(abs(r["avy"]) for r in seg) / n * 180 / math.pi
        cz = sum(abs(r["avz"]) for r in seg) / n * 180 / math.pi
        mag = lambda r: math.sqrt(r["avx"] ** 2 + r["avy"] ** 2 + r["avz"] ** 2)
        res.append({
            "dt": dt, "frames": seg[-1]["frame"] - seg[0]["frame"],
            "drop": seg[0]["vy"] - seg[-1]["vy"],
            "obs_p": obs_p, "obs_r": obs_r, "obs_y": obs_y,
            "cmd_x": cx * dt, "cmd_y": cy * dt, "cmd_z": cz * dt,
            "w0": mag(seg[0]), "w1": mag(seg[-1]),
            "accel": seg[0].get("accel", 0), "ballistic": seg[0].get("ballistic", False),
        })
    return res


def summarise(tag, rows):
    fps = (rows[-1]["frame"] - rows[0]["frame"]) / rows[-1]["t"]
    g = gains(rows)
    print("%s: %.1f fps, %d samples, %d free-fall segment(s)" % (tag, fps, len(rows), len(g)))
    if not g:
        print("   no airborne segments - drive somewhere with jumps (Dunes/Crater)")
        return fps, None
    print("   %-7s %-7s %-7s %-8s %-4s | %-9s %-9s | %-9s %-9s" %
          ("dt", "frames", "drop", "accel", "ball", "pitch obs", "pitch cmd", "roll obs", "roll cmd"))
    for s in g:
        print("   %-7.2f %-7.0f %-7.1f %-8.2f %-4s | %-9.2f %-9.2f | %-9.2f %-9.2f" %
              (s["dt"], s["frames"], s["drop"], s["accel"], "yes" if s["ballistic"] else "-",
               s["obs_p"], s["cmd_x"], s["obs_r"], s["cmd_z"]))
    # Angular-velocity decay in free flight. A rigid body with no contact keeps its angular
    # velocity; whatever decay is seen is the engine's own damping. If that damping is applied
    # once per frame without the delta-time, it acts 3x faster per SECOND at 60 Hz - which shows
    # up here as a per-second rate that scales with frame rate and a per-frame rate that does not.
    print("   angular-velocity decay in free flight (rigid body would be 0):")
    print("      %-7s %-10s %-10s %-11s %s" % ("dt", "|w| start", "|w| end", "decay /s", "decay /frame"))
    ds, df, nseg = [], [], 0
    for s in g:
        if s["w0"] <= 1e-4 or s["w1"] <= 1e-4:
            continue
        lr = math.log(s["w1"] / s["w0"])
        ds.append(lr / s["dt"])
        df.append(lr / s["frames"] if s["frames"] else 0)
        nseg += 1
        print("      %-7.2f %-10.4f %-10.4f %-11.3f %.4f"
              % (s["dt"], s["w0"], s["w1"], lr / s["dt"], lr / s["frames"] if s["frames"] else 0))
    if nseg:
        print("      mean decay: %.3f /s, %.4f /frame" % (sum(ds) / nseg, sum(df) / nseg))

    tot_obs = sum(s["obs_p"] + s["obs_r"] for s in g)
    tot_cmd = sum(s["cmd_x"] + s["cmd_z"] for s in g)
    gain = tot_obs / tot_cmd if tot_cmd else float("nan")
    tot_t = sum(s["dt"] for s in g)
    tot_f = sum(s["frames"] for s in g)
    print("   airborne total: %.2fs / %d frames;  observed %.1f deg, commanded %.1f deg"
          % (tot_t, tot_f, tot_obs, tot_cmd))
    print("   GAIN = %.3f   (deg/s airborne: %.1f, deg/frame: %.3f)\n"
          % (gain, tot_obs / tot_t if tot_t else 0, tot_obs / tot_f if tot_f else 0))
    return fps, (gain, tot_obs / tot_t if tot_t else 0, tot_obs / tot_f if tot_f else 0)


def main():
    A, B = load(sys.argv[1]), load(sys.argv[2])
    fa, ra = summarise("run A", A)
    fb, rb = summarise("run B", B)
    if not ra or not rb:
        return
    print("frame-rate ratio B/A = %.2f" % (fb / fa))
    print("gain  A %.3f  B %.3f   ->  B/A = %.2f" % (ra[0], rb[0], rb[0] / ra[0]))
    print("deg/s A %.1f  B %.1f   ->  B/A = %.2f" % (ra[1], rb[1], rb[1] / ra[1]))
    print("deg/f A %.3f B %.3f   ->  B/A = %.2f" % (ra[2], rb[2], rb[2] / ra[2]))
    print("\nreading: gain B/A near 1.0 => dt-correct. gain B/A near 3.0 => FRAME-COUPLED.")


if __name__ == "__main__":
    main()
