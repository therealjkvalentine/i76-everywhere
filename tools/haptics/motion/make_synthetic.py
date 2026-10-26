#!/usr/bin/env python3
"""make_synthetic.py - scripted i76tel sessions for the motion pipeline, each with an expected-values table.

Writes tools/haptics/replays/synth-<scenario>.i76rec (raw i76tel v3 datagrams in the .i76rec container, the same input a
real `haptics.ps1 record` capture gives) and synth-<scenario>.expect.json (windows of the i76motion output with the range
each channel must fall in). `i76motion.py --check <log> --expect <json>` compares; motion/test_motion.py runs all of them
through the host.

  python make_synthetic.py                    # every scenario, 60 fps rendering of 24 Hz fixed-step physics
  python make_synthetic.py braking turn       # some
  python make_synthetic.py --fps 120 --list

The frames imitate the proxy under I76_FIXED_STEP=24 (docs/engine/MOTION-OUTPUT.md 4.1): sim_time / sim_dt are the rendered
frame's, physics advances in whole 1/24 s steps (step_count 0 on frames without a step, the pose repeated), so every
scenario also exercises the host's repeated-pose dedupe and its 24 Hz -> output-rate resampler.

Physics model (simple and exact, so the expected values are arithmetic, not a fit):
  integrator acceleration (i76tel accel[3], world frame; ffb_present 0 so the host rotates it): surge = a_long,
  sway = v x yaw_rate (centripetal, + right), heave 0; zero while airborne.
  pitch eases (tau 0.12 s) to asin(2 x 0.008 x a_long / 2.72)  (the engine's dive rule, physics.md: 1 g = 3.3 deg),
  roll to -asin(2 x 0.008 x sway / 1.6) (body rolls outward: right side UP in a right turn = roll < 0 in i76motion);
  airborne: pitch eases to -pi/20 (tau 0.5 s), gravity on v_y.
  Signs follow the i76motion contract (schema/i76motion.json): surge + forward, sway + right, heave + up; roll + right
  side down, pitch + nose up, yaw + right turn; i76tel yaw_rate + = right turn, heading clockwise from above.
The host's startup hold (2 s of neutral after the first data, then a 1 s ramp) means checks start at t >= 3.5 s.
"""
import argparse, json, math, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HAPTICS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HAPTICS, "..", "telemetry"))
sys.path.insert(0, os.path.join(HAPTICS, "design"))
import i76tel   # noqa: E402  (the layout comes from tools/telemetry/i76tel.h)
import i76rec   # noqa: E402

PHYS_HZ = 24.0
G = 9.8
WHEELBASE = 2.72      # dive rule: sin p = 2 x 0.008 x a_long / L  (1 g = 3.3 deg nose-down)
TRACK = 1.6
DIVE = 0.008          # m of weight-transfer offset per m/s^2
DEG = math.pi / 180


def pitch_for(a_long):
    return math.asin(max(-1.0, min(1.0, 2 * DIVE * a_long / WHEELBASE)))


def roll_for(sway):
    return -math.asin(max(-1.0, min(1.0, 2 * DIVE * sway / TRACK)))


def rot_rows(h, p, r):
    """I'76 rot (rows right / up / forward in world (x, y up, z)) for heading h (clockwise from above), pitch p (+ nose up),
    roll r (+ right side down). pitch = asin(rot[7]), roll = -asin(rot[1]), heading = atan2(rot[6], rot[8])."""
    f0 = (math.sin(h), 0.0, math.cos(h)); r0 = (math.cos(h), 0.0, -math.sin(h)); u0 = (0.0, 1.0, 0.0)
    f1 = tuple(f0[i] * math.cos(p) + u0[i] * math.sin(p) for i in range(3))
    u1 = tuple(u0[i] * math.cos(p) - f0[i] * math.sin(p) for i in range(3))
    r2 = tuple(r0[i] * math.cos(r) - u1[i] * math.sin(r) for i in range(3))
    u2 = tuple(u1[i] * math.cos(r) + r0[i] * math.sin(r) for i in range(3))
    return list(r2) + list(u2) + list(f1)


def body_to_world(rot, right, up, fwd):
    return tuple(right * rot[i] + up * rot[3 + i] + fwd * rot[6 + i] for i in range(3))


class Car:
    def __init__(self, heading_deg=30.0, speed=0.0):
        self.x = self.y = self.z = 0.0
        self.h = heading_deg * DEG
        self.v = speed
        self.vy = 0.0
        self.p = self.r = 0.0
        self.air = False
        self.a_long = self.sway = 0.0
        self.yaw = 0.0
        self.throttle = 0.0
        self.steer = 0.0


# ---- scenarios: script(car, t) sets the inputs for the physics step starting at t; events(t, car) -> [event dict]
def scen_braking():
    def script(c, t):
        c.yaw = 0.0
        if t < 5.0:
            c.a_long, c.throttle = 0.0, 0.3
        elif c.v > 0:
            c.a_long, c.throttle = -9.5, -1.0
        else:
            c.a_long, c.throttle = 0.0, 0.0
    p = pitch_for(-9.5)
    checks = [
        ("cruise: no surge", 3.5, 4.8, "surge", "mean", -0.2, 0.2),
        ("cruise: level", 3.5, 4.8, "pitch", "mean", -0.2 * DEG, 0.2 * DEG),
        ("braking: surge -9.5 m/s^2", 5.6, 7.3, "surge", "mean", -9.8, -9.2),
        ("braking: pitch nose-down ~%.2f deg" % (p / DEG), 5.6, 7.3, "pitch", "mean", p - 0.3 * DEG, p + 0.3 * DEG),
        ("braking: no sway", 5.6, 7.3, "sway", "absmax", 0, 0.2),
        ("braking: no heave", 5.6, 7.3, "heave", "absmax", 0, 0.2),
        ("braking: brake pedal 1", 5.6, 7.3, "brake", "mean", 0.99, 1.01),
        ("braking: speed falls", 5.6, 7.3, "speed", "min", 1.0, 20.0),
        ("braking: live, not neutral", 5.6, 7.3, "status", "all_bit0", 1, 1),
        ("stopped: surge back to 0", 8.3, 9.5, "surge", "absmax", 0, 0.2),
        ("stopped: pitch recovers", 8.6, 9.5, "pitch", "absmax", 0, 0.3 * DEG),
    ]
    return dict(name="braking", length=10.0, heading=30.0, speed=25.0, script=script, checks=checks,
                description="cruise 25 m/s at heading 30 deg, full brake (-9.5 m/s^2) from 5 s to a stop: surge -9.5, pitch %.2f deg nose-down, independent of heading" % (p / DEG))


def scen_accelerating():
    def script(c, t):
        c.yaw = 0.0
        if 4.0 <= t < 9.0:
            c.a_long, c.throttle = 4.0, 1.0
        else:
            c.a_long, c.throttle = 0.0, 0.0
    p = pitch_for(4.0)
    checks = [
        ("parked: zero", 3.5, 3.9, "surge", "absmax", 0, 0.1),
        ("launch: surge +4", 4.6, 8.8, "surge", "mean", 3.8, 4.2),
        ("launch: nose up ~%.2f deg" % (p / DEG), 4.6, 8.8, "pitch", "mean", p - 0.2 * DEG, p + 0.2 * DEG),
        ("launch: throttle 1", 4.6, 8.8, "throttle", "mean", 0.99, 1.01),
        ("launch: speed reaches ~20", 9.0, 9.4, "speed", "max", 19.0, 20.5),
        ("cruise after: surge 0", 9.6, 10.5, "surge", "absmax", 0, 0.2),
    ]
    return dict(name="accelerating", length=11.0, heading=-60.0, speed=0.0, script=script, checks=checks,
                description="parked, then +4 m/s^2 for 5 s (0 -> 20 m/s): surge +4, squat nose-up %.2f deg" % (p / DEG))


def scen_turn():
    def script(c, t):
        c.a_long, c.throttle = 0.0, 0.4
        if 4.5 <= t < 7.0:
            c.yaw, c.steer = 0.4, 0.5
        elif 7.5 <= t < 10.0:
            c.yaw, c.steer = -0.4, -0.5
        else:
            c.yaw, c.steer = 0.0, 0.0
    sway = 20.0 * 0.4
    r = roll_for(sway)
    checks = [
        ("straight: no sway", 3.5, 4.4, "sway", "absmax", 0, 0.1),
        ("right turn: sway +%.1f (toward the centre, right)" % sway, 5.1, 6.9, "sway", "mean", sway - 0.3, sway + 0.3),
        ("right turn: yaw rate +0.4", 5.1, 6.9, "yaw_rate", "mean", 0.39, 0.41),
        ("right turn: body rolls out, roll ~%.2f deg (right side up)" % (r / DEG), 5.1, 6.9, "roll", "mean", r - 0.3 * DEG, r + 0.3 * DEG),
        ("right turn: no surge", 5.1, 6.9, "surge", "absmax", 0, 0.2),
        ("right turn: steer +0.5", 5.1, 6.9, "steer", "mean", 0.49, 0.51),
        ("left turn: sway -%.1f" % sway, 8.1, 9.9, "sway", "mean", -sway - 0.3, -sway + 0.3),
        ("left turn: yaw rate -0.4", 8.1, 9.9, "yaw_rate", "mean", -0.41, -0.39),
        ("left turn: roll ~+%.2f deg" % (-r / DEG), 8.1, 9.9, "roll", "mean", -r - 0.3 * DEG, -r + 0.3 * DEG),
    ]
    return dict(name="turn", length=11.0, heading=0.0, speed=20.0, script=script, checks=checks,
                description="20 m/s: right turn at 0.4 rad/s (4.5-7 s), then left at -0.4 (7.5-10 s): sway +-8, roll %.2f deg outward" % (-r / DEG))


def scen_crest():
    def script(c, t):
        c.a_long, c.yaw, c.throttle = 0.0, 0.0, 0.4
    def takeoff(c, t):
        return 2.0 if abs(t - 5.0) < 0.5 / PHYS_HZ else None
    checks = [
        ("before: no heave cue", 3.5, 4.9, "cue_heave", "absmax", 0, 0.05),
        ("over the crest: physics heave gated to 0", 5.08, 5.4, "heave", "absmax", 0, 0.05),
        ("over the crest: airborne bit", 5.08, 5.4, "status", "all_bit1", 1, 1),
        ("touchdown: heave cue ~1.6 m/s^2 (landing_k x |v_y| of the last airborne state)", 5.35, 5.8, "cue_heave", "max", 1.0, 2.3),
        ("cue decays (tau 80 ms)", 6.2, 6.8, "cue_heave", "absmax", 0, 0.05),
    ]
    return dict(name="crest", length=7.0, heading=10.0, speed=20.0, script=script, takeoff=takeoff, checks=checks,
                description="20 m/s over a crest: about 0.4 s light airborne (v_y +2 -> about -2 m/s), a small landing cue")


def scen_jump():
    vy0 = 0.5 * G * 1.2 - 0.0    # 5.88 m/s: lands 1.2 s later at -5.88 m/s
    def script(c, t):
        c.a_long, c.yaw, c.throttle = 0.0, 0.0, 0.5
    def takeoff(c, t):
        return vy0 if abs(t - 5.0) < 0.5 / PHYS_HZ else None
    checks = [
        ("in flight: physics surge / sway / heave 0", 5.2, 6.1, "heave", "absmax", 0, 0.05),
        ("in flight: no surge", 5.2, 6.1, "surge", "absmax", 0, 0.05),
        ("in flight: no cue (free flight is flat)", 5.2, 6.1, "cue_heave", "absmax", 0, 0.05),
        ("in flight: airborne bit", 5.2, 6.1, "status", "all_bit1", 1, 1),
        ("in flight: nose drops (pitch eases to -pi/20)", 5.9, 6.15, "pitch", "min", -0.17, -0.06),
        ("landing: heave cue ~%.1f m/s^2" % vy0, 6.15, 6.5, "cue_heave", "max", vy0 - 1.0, vy0 + 0.8),
        ("landing: cue is heave, not surge", 6.15, 6.5, "cue_surge", "absmax", 0, 0.5),
    ]
    return dict(name="jump", length=8.0, heading=-20.0, speed=25.0, script=script, takeoff=takeoff, checks=checks,
                description="25 m/s ramp jump: 1.2 s airborne (v_y +%.2f -> -%.2f m/s); physics flat in flight, landing heave cue only" % (vy0, vy0))


def scen_impact():
    def script(c, t):
        c.yaw = 0.0
        c.a_long, c.throttle = 0.0, (0.4 if t < 5.0 else 0.0)
    def wall(c, t):
        return abs(t - 5.0) < 0.5 / PHYS_HZ

    def events(c, t):
        ev = []
        if wall(c, t):
            fw = body_to_world(rot_rows(c.h, c.p, c.r), 0, 0, 1)
            ev.append(dict(type=3, f=[-15 * fw[0], -15 * fw[1], -15 * fw[2], 40.0, 0, 0], i=[1, 0, 0, 0, 0]))
        if abs(t - 7.5) < 0.5 / PHYS_HZ:
            rt = body_to_world(rot_rows(c.h, c.p, c.r), 1, 0, 0)
            name = struct.unpack("<ii", b"xcar\0\0\0\0")
            ev.append(dict(type=2, f=[c.x + 6 * rt[0], c.y, c.z + 6 * rt[2], 6.0, 0, 0], i=[name[0], name[1], 0, 0, 0]))
        return ev
    checks = [
        ("before: no cues", 3.5, 4.9, "cue_surge", "absmax", 0, 0.05),
        ("wall: surge cue against travel (<= -40 m/s^2)", 5.0, 5.2, "cue_surge", "min", -60.5, -40.0),
        ("wall: no sideways cue", 5.0, 5.2, "cue_sway", "absmax", 0, 3.0),
        ("wall: physics surge channel stays steady (integrator omits impulses)", 5.0, 5.3, "surge", "absmax", 0, 0.5),
        ("wall: impact cue decays (tau 60 ms)", 5.6, 6.0, "cue_surge", "absmax", 0, 0.5),
        ("explosion 6 m right: heave cue ~1.1", 7.5, 7.7, "cue_heave", "max", 0.8, 1.2),
        ("explosion: pushed away (left, sway < 0)", 7.5, 7.7, "cue_sway", "min", -0.4, -0.15),
        ("stopped: speed 0", 5.5, 7.0, "speed", "absmax", 0, 0.01),
    ]
    return dict(name="impact", length=9.0, heading=30.0, speed=15.0, script=script, wall=wall, events=events, checks=checks,
                description="15 m/s into a wall at 5 s (stop in one physics step, IMPACT 40 hp against travel), explosion 6 m to the right at 7.5 s")


def scen_dropout():
    def script(c, t):
        c.a_long, c.throttle = 0.0, 0.4
        c.yaw, c.steer = 0.3, 0.4
    gap = (5.0, 7.0)
    sway = 20 * 0.3
    checks = [
        ("before the gap: steady sway %.1f" % sway, 4.0, 4.9, "sway", "mean", sway - 0.2, sway + 0.2),
        ("gap +0.2 s: still live (stale_ms 250)", 5.0, 5.19, "status", "none_bit5", 1, 1),
        ("gap: neutral bit set", 5.35, 6.9, "status", "all_bit5", 1, 1),
        ("gap +0.75 s: ramp half way (sway ~%.1f)" % (sway / 2), 5.74, 5.76, "sway", "mean", sway * 0.35, sway * 0.65),
        ("gap +1.3 s: neutral reached (ramp 1 s, not a step)", 6.35, 6.9, "sway", "absmax", 0, 0.01),
        ("gap: ramp never steps (max change per tick)", 5.2, 6.4, "sway", "maxstep", 0, sway * 0.02),
        ("after: ramps back", 8.3, 8.9, "sway", "mean", sway - 0.2, sway + 0.2),
    ]
    return dict(name="dropout", length=9.0, heading=45.0, speed=20.0, script=script, gap=gap, checks=checks,
                description="steady right turn, telemetry stops for 2 s at 5 s (game paused / crashed): neutral after 250 ms, 1 s ramp down, ramp back up after")


SCENARIOS = [scen_braking, scen_accelerating, scen_turn, scen_crest, scen_jump, scen_impact, scen_dropout]


def frame_bytes(h, v, events):
    lay = h
    vals = []
    for n in lay.frame_names:
        x = v.get(n, 0)
        if n == "weapon_name":
            x = v.get(n, b"")
            if isinstance(x, str):
                x = x.encode("ascii")
        vals.append(x)
    data = bytearray(struct.pack(lay.frame_fmt, *vals))
    for e in events:
        data += struct.pack(lay.event_fmt, *[e.get(n, 0) for n in lay.event_names])
    return bytes(data)


def generate(sc, fps=60.0):
    """-> (records [(t, datagram)], meta)"""
    h = i76tel.Header()
    c = Car(sc["heading"], sc["speed"])
    n_frames = int(round(sc["length"] * fps))
    recs = []
    acc = 0.0; phys_t = 0.0; steps_total = 0
    seq = 0; ev_seq = 0; frame_no = 0
    pending_events = []
    pend_tk = None
    for i in range(n_frames):
        t = i / fps
        acc += 1.0 / fps if i > 0 else 0.0
        steps = 0
        while acc >= 1.0 / PHYS_HZ - 1e-9:
            acc -= 1.0 / PHYS_HZ
            steps += 1
            dt = 1.0 / PHYS_HZ
            # ---- one physics step at phys_t ----
            sc["script"](c, phys_t)
            tk = sc.get("takeoff", lambda *_: None)(c, phys_t)
            if "events" in sc:
                for e in sc["events"](c, phys_t):
                    pending_events.append(e)
            if tk is not None and not c.air:
                c.air = True; c.vy = tk
            if c.air:
                c.vy -= G * dt
                c.y += c.vy * dt
                if c.y <= 0.0:
                    c.y = 0.0; c.air = False; c.vy = 0.0
            if "wall" in sc and sc["wall"](c, phys_t):
                c.v = 0.0; c.a_long = 0.0
            if not c.air:
                c.v = max(0.0, c.v + c.a_long * dt) if c.a_long < 0 else c.v + c.a_long * dt
                c.sway = c.v * c.yaw
                c.h += c.yaw * dt
                pt, rt = pitch_for(c.a_long if c.v > 0 or c.a_long > 0 else 0.0), roll_for(c.sway)
                k = 1 - math.exp(-dt / 0.12)
                c.p += k * (pt - c.p); c.r += k * (rt - c.r)
            else:
                c.sway = 0.0
                k = 1 - math.exp(-dt / 0.5)
                c.p += k * (-math.pi / 20 - c.p)
            fw = (math.sin(c.h), 0.0, math.cos(c.h))
            c.x += fw[0] * c.v * dt; c.z += fw[2] * c.v * dt
            phys_t += dt; steps_total += 1
        gap = sc.get("gap")
        if gap and gap[0] <= t < gap[1]:
            continue                                   # telemetry silent: no datagram at all
        frame_no += 1
        rot = rot_rows(c.h, c.p, c.r)
        a_body = (0.0, 0.0, 0.0) if c.air else (c.sway, 0.0, c.a_long if (c.v > 0 or c.a_long > 0) else 0.0)
        aw = body_to_world(rot, *a_body)
        fwd = (math.sin(c.h), 0.0, math.cos(c.h))
        vel = (fwd[0] * c.v, c.vy, fwd[2] * c.v)
        flags = 0x1 | (0x4 if c.air else 0)
        v = {
            "magic": h.consts["I76TEL_MAGIC"], "version": h.consts["I76TEL_VERSION"], "size": h.frame_size,
            "seq": seq + 1, "frame": frame_no, "proxy_frame": i, "sim_time": t, "sim_dt": 1.0 / fps, "dt": 1.0 / fps,
            "step_count": steps, "player_present": 1, "obj_addr": 0x1000, "ent_addr": 0x2000,
            "pos_0": c.x, "pos_1": c.y, "pos_2": c.z,
            "velocity_0": vel[0], "velocity_1": vel[1], "velocity_2": vel[2], "speed": math.sqrt(sum(x * x for x in vel)),
            "yaw_rate": 0.0 if c.air else c.yaw, "pitch_rate": 0.0, "roll_rate": 0.0,
            "accel_0": aw[0], "accel_1": aw[1], "accel_2": aw[2],
            "steer": c.steer, "throttle": c.throttle, "gear_dir": 1, "gear_lever": 3,
            "gear": 2 if c.v > 0.5 else 1, "rpm": 850 + min(6000, c.v * 200), "flags": flags, "surface": 5,
            "ground_normal_1": 1.0, "clearance": 0.3 + c.y, "mass": 1800.0, "inv_mass": 1 / 1800.0, "health_pct": 100,
            "engine_hp": 100, "engine_hp_max": 100, "weapon_name": b"gmg30cal", "weapon_def": 3, "weapon_row": 0,
            "wheelbase": WHEELBASE, "front_track": TRACK, "ground_g": 9.8, "event_hooks": 0x7f,
        }
        for k in range(9):
            v["rot_%d" % k] = rot[k]
        for w in range(6):
            present = w not in (2, 3)
            v["wheel%d_present" % w] = 1 if present else 0
            v["wheel%d_hp" % w] = 100; v["wheel%d_hp_max" % w] = 100; v["wheel%d_grip" % w] = 1.0
            v["wheel%d_ground_speed" % w] = c.v
            front = w in (0, 1)
            v["wheel%d_susp_offset" % w] = (-1 if front else 1) * 0.004 * a_body[2] if present else 0.0
            v["wheel%d_unloaded" % w] = 1 if c.air else 0
        evs = []
        for e in pending_events:
            ev_seq += 1
            d = {"seq": ev_seq, "frame": i, "type": e["type"]}
            for k in range(6):
                d["f_%d" % k] = e["f"][k]
            for k in range(5):
                d["i_%d" % k] = e["i"][k]
            evs.append(d)
        pending_events = []
        v["event_seq"] = ev_seq; v["event_count"] = len(evs)
        seq += 1
        recs.append((t, frame_bytes(h, v, evs)))
    return recs


def write_scenario(sc, out_dir, fps=60.0):
    recs = generate(sc, fps)
    base = os.path.join(out_dir, "synth-%s" % sc["name"])
    meta = {"source": "tools/haptics/motion/make_synthetic.py", "scenario": sc["name"], "fps": fps, "physics_hz": PHYS_HZ,
            "description": sc["description"]}
    i76rec.write(base + ".i76rec", recs, meta)
    exp = {"scenario": sc["name"], "description": sc["description"], "fps": fps, "physics_hz": PHYS_HZ,
           "note": "windows are on the i76motion t_sim clock; values are i76motion fields (SI, radians); stat = mean | min | max | absmax | maxstep over the window, or all_bitN / any_bitN / none_bitN on status",
           "checks": [dict(name=n, t0=a, t1=b, channel=ch, stat=st, lo=lo, hi=hi) for (n, a, b, ch, st, lo, hi) in sc["checks"]]}
    with open(base + ".expect.json", "w", newline="\n") as f:
        json.dump(exp, f, indent=1)
    return base + ".i76rec", base + ".expect.json", len(recs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help="scenarios (default: all)")
    ap.add_argument("--fps", type=float, default=60.0, help="rendered frame rate (physics stays 24 Hz)")
    ap.add_argument("--out", default=os.path.join(HAPTICS, "replays"))
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    scs = [f() for f in SCENARIOS]
    if a.list:
        for s in scs:
            print("%-13s %s" % (s["name"], s["description"]))
        return 0
    want = set(a.names)
    if "all" in want:
        want = set()
    unknown = want - {s["name"] for s in scs}
    if unknown:
        print("unknown scenario(s): %s (known: %s)" % (", ".join(sorted(unknown)), ", ".join(s["name"] for s in scs)))
        return 2
    os.makedirs(a.out, exist_ok=True)
    for s in scs:
        if want and s["name"] not in want:
            continue
        rec, exp, n = write_scenario(s, a.out, a.fps)
        print("%-13s %5d frames -> %s (+ %s)" % (s["name"], n, rec, os.path.basename(exp)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
