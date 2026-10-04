#!/usr/bin/env python3
"""rate-ab-analyse.py - JSON analysis front end for rate-ab.ps1.

    python rate-ab-analyse.py cactus    <condition dir>     -> {"runs": {tag: {approaches, valid, hits, pass, hit_rate, fps}}, "table": ...}
    python rate-ab-analyse.py airborne  <run csv>           -> {"fps", "gain", "deg_s", "deg_frame", "segments", "text"}
    python rate-ab-analyse.py cactus2   <tag>.frames.csv    -> {approaches, valid, hits, pass, hit_rate, hits_impact, hits_speed, ...}
    python rate-ab-analyse.py airborne2 <tag>.csv           -> {fps, gain, deg_s, deg_step, segments, air_s, ...}
    python rate-ab-analyse.py farengine <tag>.csv [slot]    -> {t_cruise_s, cruise_ms, far_steps_s, min_dist_m, cars, ...}
    python rate-ab-analyse.py colldedupe <tag>.frames.csv   -> {rams, valid, dup_ratio, events_ram, dups_ram, impacts_ram, dmg_ram, hp_ram, ...}
    python rate-ab-analyse.py hazard    <tag>.frames.csv    -> {impacts_round_s, steps_proj_s, hz_impacts_s, hp_round_s, rounds, shots, ...}
    python rate-ab-analyse.py wmiss     <tag>.csv           -> {wmiss_play_s, wmiss_req_s, req_per_frame, play_per_tick, ticks_s, fps}
    python rate-ab-analyse.py airolls   <tag>.csv           -> {skid_rolls_s, horn_rolls_s, skid_per_tick, horn_per_tick, ticks_s, fps, near_m}

The first two wrap the EXISTING analysers (no analysis of their own); the last three analyse the raw telemetry
captures of rate-ab-live.py and are unit-run on synthetic telemetry by rate-ab-selftest.py.

cactus:   runs analyze-cactus.main(dir) and parses its per-approach verdict lines (HIT / PASS-THROUGH / MISS (excluded) /
          no-data), so the classifier (VALID_M, HIT_FRACTION) stays in one place. Grouped by tag = one gauntlet run.
airborne: calls analyse-airborne.summarise(), which returns (fps, (gain, deg/s airborne, deg/frame)) or (fps, None).

cactus2:  per approach (frames = one telemetry frame each, with the target trunk and the approach direction):
            line_off   lateral offset of the car from the trunk line at the last frame 8..2.5 m before the trunk
            min_dist   closest pass to the trunk, interpolated between frames (reported; a hit stops short of it)
            v_before   mean speed 12..4 m before the trunk;  v_min  minimum speed from 3 m before to 15 m after
            impacts    I76TEL_EV_IMPACT events on the player from 5 m before to 10 m after, by source object class
          MISS (excluded) line_off > VALID2_M;  SLOW (excluded) v_before < SLOW_FRACTION x set speed;
          HIT = a scenery-class impact event (class not 0 terrain / 1 car / 0x33 ordnance / 0x34 explosion) OR
          v_min < HIT_FRACTION x v_before (the old classifier);  else PASS-THROUGH.  hit_rate = hits / valid.
          hits_impact / hits_speed are reported separately so a live run shows whether the two signals agree.
airborne2: frames without a physics step are dropped (step_count 0: render-interpolated repeats). An airborne segment
          is a run of consecutive step frames with flags bit 0x4. Per pair of consecutive frames in a segment:
            observed  = rotation angle between the two rot[9] matrices (2 asin(|R1 - R0|_F / 2 sqrt 2))
            commanded = mean |body rate| of the two frames x phys_dt (steps x fixed step, or sim_dt at stock)
          gain = sum observed / sum commanded over segments of at least MIN_AIR_S and MIN_CMD_DEG. 1.0 = dt-correct.
farengine: per vehicle slot of the 0x54E11C table (slot 0 = the player): speed = displacement over a SPEED_WIN window;
          cruise = 90th percentile speed; t_cruise = time from the last moment at <= 10% cruise (or the window start)
          to the first moment at >= 90% cruise. The reported car is the one that travelled furthest (or [slot]).
          min_dist_m = closest that car came to the player (far path needs > far radius + 25 m);
          far_steps_s = g_idbg.far_steps per second (counted only under I76_FAR_ENGINE_DT).

The PER-FRAME-AUDIT-2026-10-03 acceptance measures (i76-everywhere docs; captures of rate-ab-live.py ram / hazard /
wmiss / counters):
colldedupe: per ram (frames from the launch to RAM post-contact seconds; counters read with every frame):
            contact    the first collision-class IMPACT event on the player (source class not 0 / 0x33 / 0x34), else the
                       first frame g_idbg.coll_events moved (only when the ram's background rate bg_s was 0)
            events / dups   coll_events / coll_dups over the ram;  burst = coll_events in the first BURST_S after contact
            impacts / dmg   IMPACT events on the player from the contact on (any source class but ordnance / explosion)
                       and the sum of their f3 (armour + chassis + component hp lost in the call);  hp = armour +
                       chassis sum at launch minus at the end.  events / dups have the ram's background rates
                       (bg_s, bg_dups_s: counted at rest before the launch) taken out
            verdict    RAM, or NO-CONTACT, EARLY (contact in the first quarter of the approach: not the target), SLOW
                       (speed before contact < SLOW_FRACTION x set speed) - only RAM rows are averaged.
          dup_ratio = sum dups / sum events over RAM rows. Audit: 0 at capped 20, ~0.6 at 60, ~0.8 at 120 (24 steps/s);
          with I76_COLL_DEDUPE=0 impacts ~ events, with the dedupe impacts ~ events - dups.
hazard:   the 'measure' phase (car held on the patch). rounds = sum of the SHOT events' round counts for the swapped
          definition (else the ammo used), shots = SHOT events = projectiles (live patches).
            impacts_round_s = ordnance-class (0x33) IMPACT events on the player per second per round   (audit: 20, any fps)
            steps_proj_s    = g_idbg.hazard_steps per second per projectile                             (audit: 20)
            hz_impacts_s    = g_idbg.hazard_impacts per second (contact effects), hp_round_s = sum f3 per second per round
            oil_frac        = frames with flags 0x400 (traction loss) / frames;  explosions_s = EXPLOSION events within 15 m / s
wmiss:    counter deltas over the window / seconds; req_per_frame = wmiss_req / frames (1.0 while the dead weapon's key is
          held), play_per_tick = wmiss_play / tick20_n (1.0: one click per 20 Hz grid frame).
airolls:  skid_rolls / horn_rolls per second and per tick20_n (with the hold a roll can only happen on a grid frame, so
          per-tick <= AI cars in the state; without it the per-tick figure scales with fps / 20). near_m = closest any
          other vehicle came to the player.
"""
import contextlib, csv, importlib.util, io, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERDICT = re.compile(r'^(\S+)\s+\(([^)]*)\)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(HIT|PASS-THROUGH|MISS \(excluded\)|no-data)$')


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), os.path.join(HERE, name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cactus(d):
    m = load('analyze-cactus')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        m.main(d)
    runs = {}
    for line in buf.getvalue().splitlines():
        mm = VERDICT.match(line.strip())
        if not mm:
            continue
        tag, verdict = mm.group(1), mm.group(7)
        r = runs.setdefault(tag, {'approaches': 0, 'valid': 0, 'hits': 0, 'pass': 0, 'fps': []})
        r['approaches'] += 1
        try:
            r['fps'].append(float(mm.group(6)))
        except ValueError:
            pass
        if verdict == 'HIT':
            r['valid'] += 1; r['hits'] += 1
        elif verdict == 'PASS-THROUGH':
            r['valid'] += 1; r['pass'] += 1
    for r in runs.values():
        r['hit_rate'] = r['hits'] / r['valid'] if r['valid'] else None
        r['fps'] = sum(r['fps']) / len(r['fps']) if r['fps'] else None
    return {'runs': runs, 'table': buf.getvalue()}


def airborne(p):
    m = load('analyse-airborne')
    rows = m.load(p)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fps, r = m.summarise(os.path.basename(p), rows)
    text = buf.getvalue()
    seg = re.search(r'(\d+) free-fall segment', text)
    return {'fps': fps, 'gain': r[0] if r else None, 'deg_s': r[1] if r else None, 'deg_frame': r[2] if r else None,
            'segments': int(seg.group(1)) if seg else 0, 'samples': len(rows), 'text': text}


# ---- telemetry analyses (rate-ab-live.py captures) ------------------------------------------------------------------
VALID2_M = 1.0          # the trunk line: car centre within 1 m of the trunk centre (trunk ~0.45 m, car half width ~0.9 m)
HIT_FRACTION = 0.6      # as analyze-cactus.py
SLOW_FRACTION = 0.7     # an approach that arrived below 70% of the set speed is not the condition under test
NON_SCENERY = (0, 1, 0x33, 0x34)   # i76tel.h I76TEL_EV_IMPACT source classes: terrain / none, car, ordnance, explosion
EV_IMPACT = 3
MIN_AIR_S = 0.25        # as analyse-airborne.py MIN_SECONDS
MIN_CMD_DEG = 1.0       # a segment that was asked to turn less than this carries no gain information
SPEED_WIN = 0.5         # s, farengine finite-difference window
TELEPORT_MS = 150.0     # a "speed" above this is a placement, not driving


def rows_of(p):
    out = []
    with open(p, newline="") as f:
        for r in csv.DictReader(f):
            d = {}
            for k, v in r.items():
                try:
                    d[k] = float(v)
                except (TypeError, ValueError):
                    d[k] = float("nan") if v in ("", None) else v
            out.append(d)
    return out


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def fmt(x, d=2):
    return "-" if x is None else "%.*f" % (d, x)


def seg_dist(ax, az, bx, bz):
    """Distance from the origin to the segment a-b (positions relative to the trunk)."""
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    u = 0.0 if L == 0 else max(0.0, min(1.0, -(ax * dx + az * dz) / L))
    return math.hypot(ax + u * dx, az + u * dz)


def cactus2(p):
    frames = rows_of(p)
    evp = p[:-len(".frames.csv")] + ".events.csv" if p.endswith(".frames.csv") else ""
    events = rows_of(evp) if evp and os.path.exists(evp) else []
    res = []
    lines = ["%-3s %-18s %8s %8s %8s %7s %6s %7s %-12s %s" % ("#", "target", "line_off", "min_dist", "v_before", "v_min", "steps", "impacts", "classes", "verdict")]
    for a in sorted({r["approach"] for r in frames}):
        rs = [r for r in frames if r["approach"] == a]
        tx, tz, fx, fz, vset = (rs[0][k] for k in ("tx", "tz", "fx", "fz", "v_set"))
        rel = [(r["x"] - tx, r["z"] - tz) for r in rs]
        along = [x * fx + z * fz for x, z in rel]
        md = min([math.hypot(*rel[0])] + [seg_dist(*rel[i - 1], *rel[i]) for i in range(1, len(rel))])
        # a car that HITS stops with its centre a bumper's length short of the trunk, so min_dist cannot say whether
        # it was on the trunk line; the lateral offset of the line just before contact can
        pre = [abs(x * fz - z * fx) for (x, z), al in zip(rel, along) if -8.0 <= al <= -2.5]
        off = pre[-1] if pre else None
        vb = mean(r["speed"] for r, al in zip(rs, along) if -12.0 <= al <= -4.0)
        near = [r for r, al in zip(rs, along) if -3.0 <= al <= 15.0]
        vm = min((r["speed"] for r in near), default=None)
        steps = mean(r["step_count"] for r in near if r["step_count"] >= 0)
        by_frame = {r["proxy_frame"]: al for r, al in zip(rs, along)}
        cls = []
        for e in events:
            if e["approach"] != a or e["type"] != EV_IMPACT or not e["i0"]:
                continue
            al = by_frame.get(e["frame"])
            if al is None:                                   # the frame that carried it was missed by the sampler: nearest
                al = min(zip(rs, along), key=lambda ra: abs(ra[0]["proxy_frame"] - e["frame"]))[1]
            if -5.0 <= al <= 10.0:
                cls.append(int(e["i1"]))
        hit_i = any(c not in NON_SCENERY for c in cls)
        hit_s = vb is not None and vm is not None and vm < HIT_FRACTION * vb
        if vb is None or vm is None or off is None:
            verdict = "no-data"                              # never reached the trunk (or was placed inside the window)
        elif off > VALID2_M:
            verdict = "MISS (excluded)"
        elif vb < SLOW_FRACTION * vset:
            verdict = "SLOW (excluded)"
        elif hit_i or hit_s:
            verdict = "HIT"
        else:
            verdict = "PASS-THROUGH"
        res.append({"approach": int(a), "min_dist": md, "line_off": off, "v_before": vb, "v_min": vm, "steps": steps, "classes": cls,
                    "hit_impact": hit_i, "hit_speed": hit_s, "verdict": verdict})
        lines.append("%-3d (%7.1f,%8.1f) %8s %8.2f %8s %7s %6s %7d %-12s %s" % (
            a, tx, tz, fmt(off), md, fmt(vb, 1), fmt(vm, 1), fmt(steps), len(cls), ",".join("0x%x" % c for c in sorted(set(cls))) or "-", verdict))
    valid = [r for r in res if r["verdict"] in ("HIT", "PASS-THROUGH")]
    hits = [r for r in valid if r["verdict"] == "HIT"]
    return {"approaches": len(res), "valid": len(valid), "hits": len(hits), "pass": len(valid) - len(hits),
            "hit_rate": len(hits) / len(valid) if valid else None,
            "hits_impact": sum(r["hit_impact"] for r in valid), "hits_speed": sum(r["hit_speed"] for r in valid),
            "both": sum(r["hit_impact"] and r["hit_speed"] for r in valid),
            "miss": sum(r["verdict"].startswith("MISS") for r in res), "slow": sum(r["verdict"].startswith("SLOW") for r in res),
            "v_before": mean(r["v_before"] for r in valid), "steps_frame": mean(r["steps"] for r in valid if r["steps"] is not None),
            "frames": len(frames), "rows": res, "table": "\n".join(lines)}


def rot_angle(a, b):
    """Angle (rad) of the rotation taking matrix a to b, from the Frobenius norm of the difference (stable near 0)."""
    d = math.sqrt(sum((y - x) ** 2 for x, y in zip(a, b)))
    return 2.0 * math.asin(min(1.0, d / (2.0 * math.sqrt(2.0))))


def airborne2(p):
    allrows = rows_of(p)
    rows = [r for r in allrows if r["step_count"] != 0]     # 0 = no physics step this frame; -1 (unknown) is kept
    segs, cur = [], []
    for r in rows:
        if int(r["flags"]) & 0x4:
            cur.append(r)
        else:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
    if len(cur) > 1:
        segs.append(cur)
    D = 180.0 / math.pi
    out, lines = [], ["%-8s %-6s %-7s %-9s %-9s %-7s %s" % ("t", "steps", "air s", "obs deg", "cmd deg", "gain", "used")]
    for s in segs:
        obs = cmd = dur = 0.0
        nsteps = 0
        for a, b in zip(s, s[1:]):
            dt = b["phys_dt"]
            if not dt == dt or dt <= 0:
                continue
            obs += rot_angle([a["r%d" % i] for i in range(9)], [b["r%d" % i] for i in range(9)])
            w = [math.sqrt(x["pitch_rate"] ** 2 + x["yaw_rate"] ** 2 + x["roll_rate"] ** 2) for x in (a, b)]
            cmd += 0.5 * (w[0] + w[1]) * dt
            dur += dt
            nsteps += max(1, int(b["step_count"]))
        used = dur >= MIN_AIR_S and cmd * D >= MIN_CMD_DEG
        out.append({"t": s[0]["t"], "steps": nsteps, "air_s": dur, "obs_deg": obs * D, "cmd_deg": cmd * D, "used": used})
        lines.append("%-8.2f %-6d %-7.2f %-9.2f %-9.2f %-7s %s" % (s[0]["t"], nsteps, dur, obs * D, cmd * D,
                                                                 "%.3f" % (obs / cmd) if cmd > 0 else "-", "yes" if used else "-"))
    u = [o for o in out if o["used"]]
    obs, cmd, dur, st = (sum(o[k] for o in u) for k in ("obs_deg", "cmd_deg", "air_s", "steps"))
    span = allrows[-1]["t"] - allrows[0]["t"] if len(allrows) > 1 else 0
    return {"fps": (allrows[-1]["frame"] - allrows[0]["frame"]) / span if span > 0 else None,
            "gain": obs / cmd if cmd > 0 else None, "deg_s": obs / dur if dur > 0 else None, "deg_step": obs / st if st else None,
            "segments": len(u), "segments_seen": len(out), "air_s": dur, "samples": len(allrows), "step_frames": len(rows),
            "airborne_frames": sum(1 for r in rows if int(r["flags"]) & 0x4), "text": "\n".join(lines)}


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def farengine(p, slot=None):
    rows = rows_of(p)
    by = {}
    for r in rows:
        by.setdefault(int(r["slot"]), []).append(r)
    me = {r["frame"]: r for r in by.get(0, [])}
    cars = []
    for s, rs in sorted(by.items()):
        if s == 0:
            continue
        pts = []
        for r in rs:                                         # one sample per game frame: the sampler polls faster at 20 fps
            if not pts or r["frame"] != pts[-1]["frame"]:
                pts.append(r)
        v, j = [], 0
        for i in range(len(pts)):
            while j < len(pts) and pts[j]["t"] < pts[i]["t"] + SPEED_WIN:
                j += 1
            if j >= len(pts):
                break
            sp = math.dist((pts[i]["x"], pts[i]["y"], pts[i]["z"]), (pts[j]["x"], pts[j]["y"], pts[j]["z"])) / (pts[j]["t"] - pts[i]["t"])
            if sp < TELEPORT_MS:
                v.append((0.5 * (pts[i]["t"] + pts[j]["t"]), sp))
        if not v:
            continue
        cruise = pct([sp for _t, sp in v], 0.9)
        c = {"slot": s, "cruise_ms": cruise, "path_m": mean(sp for _t, sp in v) * (v[-1][0] - v[0][0]),
             "t_cruise_s": None, "moving_at_start": None, "min_dist_m": None}
        if cruise >= 3.0:
            i90 = next(i for i, (_t, sp) in enumerate(v) if sp >= 0.9 * cruise)
            i10 = max((i for i in range(i90) if v[i][1] <= 0.1 * cruise), default=None)
            c["moving_at_start"] = i10 is None
            c["t_cruise_s"] = v[i90][0] - (v[i10][0] if i10 is not None else pts[0]["t"])
        ds = [math.dist((r["x"], r["y"], r["z"]), (me[r["frame"]]["x"], me[r["frame"]]["y"], me[r["frame"]]["z"])) for r in pts if r["frame"] in me]
        c["min_dist_m"] = min(ds) if ds else None
        cars.append(c)
    fs = [(r["t"], r["far_steps"]) for r in rows if r["far_steps"] == r["far_steps"]]
    far_s = (fs[-1][1] - fs[0][1]) / (fs[-1][0] - fs[0][0]) if len(fs) > 1 and fs[-1][0] > fs[0][0] else None
    span = rows[-1]["t"] - rows[0]["t"] if len(rows) > 1 else 0
    moving = [c for c in cars if c["t_cruise_s"] is not None]
    if slot is not None:
        pick = next((c for c in cars if c["slot"] == slot), None)
    else:
        pick = max(moving, key=lambda c: c["path_m"]) if moving else None
    lines = ["%-4s %-9s %-9s %-10s %-9s %s" % ("slot", "cruise", "path m", "t_cruise", "min dist", "moving at start")]
    for c in cars:
        lines.append("%-4d %-9s %-9s %-10s %-9s %s" % (c["slot"], fmt(c["cruise_ms"]), fmt(c["path_m"], 0), fmt(c["t_cruise_s"]),
                                                      fmt(c["min_dist_m"], 0), c["moving_at_start"]))
    out = {"fps": (rows[-1]["frame"] - rows[0]["frame"]) / span if span > 0 else None, "cars": len(cars), "moving": len(moving),
           "far_steps_s": far_s, "window_s": span, "text": "\n".join(lines), "slot": None, "t_cruise_s": None, "cruise_ms": None,
           "min_dist_m": None, "moving_at_start": None}
    if pick:
        out.update({k: pick[k] for k in ("slot", "t_cruise_s", "cruise_ms", "min_dist_m", "moving_at_start")})
    return out


# ---- PER-FRAME-AUDIT-2026-10-03 acceptance measures -------------------------------------------------------------------
EV_SHOT, EV_EXPLOSION = 1, 2
CLS_ORDNANCE, CLS_EXPLOSION = 0x33, 0x34
BURST_S = 0.25          # one impact's worth of frames at any of the three rates (5 frames at 20 fps, 30 at 120)
EARLY_FRACTION = 0.75   # a contact further than this x the start distance from the target centre is not the target


def num(x):
    """A CSV cell that may be blank (counters under the stock set): float or None."""
    return x if isinstance(x, float) and x == x else None


def delta(rows, col):
    a, b = (num(rows[0][col]), num(rows[-1][col])) if rows else (None, None)
    return b - a if a is not None and b is not None else None


def events_of(p):
    evp = p[:-len(".frames.csv")] + ".events.csv" if p.endswith(".frames.csv") else ""
    return rows_of(evp) if evp and os.path.exists(evp) else []


def colldedupe(p):
    frames, events = rows_of(p), events_of(p)
    res = []
    lines = ["%-3s %-10s %7s %7s %6s %5s %5s %6s %7s %7s %6s %s" % (
        "#", "target", "v_cont", "at m", "events", "dups", "burst", "impact", "dmg", "hp", "bg/s", "verdict")]
    for a in sorted({r["ram"] for r in frames}):
        rs = [r for r in frames if r["ram"] == a]
        pev = [e for e in events if e["approach"] == a and e["type"] == EV_IMPACT and e["i0"] and e["i1"] not in (CLS_ORDNANCE, CLS_EXPLOSION)]
        tx, tz, vset, dist = (rs[0][k] for k in ("tx", "tz", "v_set", "dist"))
        bg, bgd = num(rs[0]["bg_s"]), num(rs[0].get("bg_dups_s", float("nan")))
        ce0 = num(rs[0]["coll_events"])
        tc = min((e["t"] for e in pev if e["i1"] != 0), default=None)      # class 0 (terrain / none) alone is a bump, not a ram
        if ce0 is not None and bg == 0:
            tcc = next((r["t"] for r in rs if r["coll_events"] > ce0), None)
            tc = tcc if tc is None else (tc if tcc is None else min(tc, tcc))
        evs = [e for e in pev if tc is not None and e["t"] >= tc - 0.05]
        ce, cd = delta(rs, "coll_events"), delta(rs, "coll_dups")
        if ce is not None and bg:                            # a resting pair elsewhere counts every frame: take it out
            span = rs[-1]["t"] - rs[0]["t"]
            ce, cd = max(0.0, ce - bg * span), max(0.0, cd - (bgd or 0.0) * span)
        hp = rs[0]["hp"] - rs[-1]["hp"]
        vc = at = burst = None
        if tc is not None:
            before = [r for r in rs if tc - 0.3 <= r["t"] < tc] or [r for r in rs if r["t"] <= tc][-1:]
            vc = mean(r["speed"] for r in before)
            rc = min(rs, key=lambda r: abs(r["t"] - tc))
            at = math.hypot(rc["x"] - tx, rc["z"] - tz)
            if ce0 is not None:
                pre = [r for r in rs if r["t"] < tc]
                win = [r for r in rs if r["t"] <= tc + BURST_S]
                burst = win[-1]["coll_events"] - (pre[-1]["coll_events"] if pre else ce0)
        if tc is None:
            verdict = "NO-CONTACT"
        elif at > EARLY_FRACTION * dist:
            verdict = "EARLY (excluded)"
        elif vc is None or vc < SLOW_FRACTION * vset:
            verdict = "SLOW (excluded)"
        else:
            verdict = "RAM"
        res.append({"ram": int(a), "name": rs[0].get("name"), "v_contact": vc, "at_m": at, "events": ce, "dups": cd, "burst": burst,
                    "impacts": len(evs), "dmg": sum(e["f3"] for e in evs), "hp": hp, "bg_s": bg, "verdict": verdict,
                    "classes": sorted({int(e["i1"]) for e in evs})})
        lines.append("%-3d %-10s %7s %7s %6s %5s %5s %6d %7.0f %7.0f %6s %s" % (
            a, rs[0].get("name"), fmt(vc, 1), fmt(at, 1), fmt(ce, 0), fmt(cd, 0), fmt(burst, 0), len(evs), res[-1]["dmg"], hp,
            fmt(bg, 1), verdict))
    v = [r for r in res if r["verdict"] == "RAM"]
    vc = [r for r in v if r["events"] is not None]
    ev, du = sum(r["events"] for r in vc), sum(r["dups"] for r in vc)
    steps = [r["step_count"] for r in frames if r["step_count"] >= 0]
    span = frames[-1]["t"] - frames[0]["t"] if len(frames) > 1 else 0
    return {"rams": len(res), "valid": len(v), "no_contact": sum(r["verdict"] == "NO-CONTACT" for r in res),
            "dup_ratio": du / ev if ev else None, "events_ram": mean(r["events"] for r in vc), "dups_ram": mean(r["dups"] for r in vc),
            "burst_ram": mean(r["burst"] for r in vc if r["burst"] is not None), "impacts_ram": mean(r["impacts"] for r in v),
            "dmg_ram": mean(r["dmg"] for r in v), "hp_ram": mean(r["hp"] for r in v), "v_contact": mean(r["v_contact"] for r in v),
            "steps_frame": mean(steps), "zero_step_frac": (sum(1 for x in steps if x == 0) / len(steps)) if steps else None,
            "frames": len(frames), "rows": res, "table": "\n".join(lines)}


def hazard(p):
    frames, events = rows_of(p), events_of(p)
    m = [r for r in frames if r["phase"] == "measure"]
    pre = [r for r in frames if r["phase"] in ("drop", "wait")]
    shots = [e for e in events if e["type"] == EV_SHOT and e["phase"] in ("drop", "wait")]
    rounds = sum(e["i1"] for e in shots)
    ammo_used = (pre[0]["ammo"] - pre[-1]["ammo"]) if pre else None
    if not rounds and ammo_used:
        rounds = ammo_used
    out = {"rounds": rounds or None, "shots": len(shots) or None, "ammo_used": ammo_used, "frames": len(m), "window_s": None, "fps": None,
           "impacts_round_s": None, "impacts_s": None, "hp_round_s": None, "hp_s": None, "steps_proj_s": None, "steps_s": None,
           "hz_impacts_s": None, "ticks_s": None, "oil_frac": None, "explosions_s": None,
           "offset_m": m[0]["offset"] if m else None}
    if len(m) < 2:
        out["text"] = "no 'measure' phase in the capture (%d frames in all)" % len(frames)
        return out
    T = m[-1]["t"] - m[0]["t"]
    me = [e for e in events if e["phase"] == "measure"]
    imp = [e for e in me if e["type"] == EV_IMPACT and e["i0"] and e["i1"] == CLS_ORDNANCE]
    expl = [e for e in me if e["type"] == EV_EXPLOSION and 0 <= e["f3"] <= 15.0]
    per = lambda x, d: (x / T / d) if x is not None and d else None
    st, hi, tk = delta(m, "hazard_steps"), delta(m, "hazard_impacts"), delta(m, "tick20_n")
    out.update({"window_s": T, "fps": (m[-1]["frame"] - m[0]["frame"]) / T, "impacts_s": len(imp) / T, "impacts_round_s": per(len(imp), rounds),
                "hp_s": sum(e["f3"] for e in imp) / T, "hp_round_s": per(sum(e["f3"] for e in imp), rounds),
                "steps_s": per(st, 1), "steps_proj_s": per(st, len(shots)), "hz_impacts_s": per(hi, 1), "ticks_s": per(tk, 1),
                "oil_frac": sum(1 for r in m if int(r["flags"]) & 0x400) / len(m), "explosions_s": len(expl) / T})
    out["text"] = ("%.1f s on the patch %.1f m behind the drop pose, %.1f fps; %s rounds in %s projectiles\n"
                   "IMPACT (ordnance, player) %.1f /s = %s per round   hp %.0f /s = %s per round\n"
                   "hazard_steps %s /s = %s per projectile   hazard_impacts %s /s   tick20 %s /s   oil flag %.0f%% of frames   EXPLOSION %.1f /s" % (
                       T, out["offset_m"], out["fps"], rounds, len(shots), out["impacts_s"], fmt(out["impacts_round_s"], 1), out["hp_s"],
                       fmt(out["hp_round_s"], 1), fmt(out["steps_s"], 1), fmt(out["steps_proj_s"], 1), fmt(out["hz_impacts_s"], 1),
                       fmt(out["ticks_s"], 1), 100 * out["oil_frac"], out["explosions_s"]))
    return out


def counter_rates(p, names):
    rows = rows_of(p)
    out = {"samples": len(rows), "window_s": None, "fps": None, "ticks_s": None}
    out.update({n + "_s": None for n in names})
    if len(rows) < 2 or rows[-1]["t"] <= rows[0]["t"]:
        return rows, out, None, None
    T, frames = rows[-1]["t"] - rows[0]["t"], rows[-1]["frame"] - rows[0]["frame"]
    out.update({"window_s": T, "fps": frames / T, "ticks_s": delta(rows, "tick20_n") / T})
    out.update({n + "_s": delta(rows, n) / T for n in names})
    return rows, out, frames, delta(rows, "tick20_n")


def wmiss(p):
    rows, out, frames, ticks = counter_rates(p, ("wmiss_req", "wmiss_play"))
    out.update({"req_per_frame": None, "play_per_tick": None, "text": "no samples"})
    if frames is None:
        return out
    out["req_per_frame"] = delta(rows, "wmiss_req") / frames if frames else None
    out["play_per_tick"] = delta(rows, "wmiss_play") / ticks if ticks else None
    out["text"] = "%.1f s at %.1f fps: wmiss_req %.1f /s (%s per frame), wmiss_play %.1f /s (%s per 20 Hz tick, %.1f ticks/s)" % (
        out["window_s"], out["fps"], out["wmiss_req_s"], fmt(out["req_per_frame"]), out["wmiss_play_s"], fmt(out["play_per_tick"]), out["ticks_s"])
    return out


def airolls(p):
    rows, out, frames, ticks = counter_rates(p, ("skid_rolls", "horn_rolls"))
    out.update({"skid_per_tick": None, "horn_per_tick": None, "near_m": None, "text": "no samples"})
    if frames is None:
        return out
    near = [r["near_m"] for r in rows if num(r["near_m"]) is not None]
    out["near_m"] = min(near) if near else None
    if ticks:
        out["skid_per_tick"], out["horn_per_tick"] = delta(rows, "skid_rolls") / ticks, delta(rows, "horn_rolls") / ticks
    out["text"] = "%.1f s at %.1f fps: skid rolls %.2f /s (%s per tick), horn rolls %.2f /s (%s per tick), %.1f ticks/s, nearest other vehicle %s m" % (
        out["window_s"], out["fps"], out["skid_rolls_s"], fmt(out["skid_per_tick"], 3), out["horn_rolls_s"], fmt(out["horn_per_tick"], 3),
        out["ticks_s"], fmt(out["near_m"], 0))
    return out


def main():
    cmds = {"cactus": cactus, "airborne": airborne, "cactus2": cactus2, "airborne2": airborne2, "farengine": farengine,
            "colldedupe": colldedupe, "hazard": hazard, "wmiss": wmiss, "airolls": airolls}
    if len(sys.argv) < 3 or sys.argv[1] not in cmds or len(sys.argv) > (4 if sys.argv[1] == "farengine" else 3):
        print(__doc__); sys.exit(2)
    extra = [int(sys.argv[3])] if len(sys.argv) == 4 else []
    print(json.dumps(clean(cmds[sys.argv[1]](sys.argv[2], *extra))))


def clean(o):
    """NaN / inf are not JSON (ConvertFrom-Json rejects them): null instead."""
    if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))):
        return None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o


if __name__ == '__main__':
    main()
