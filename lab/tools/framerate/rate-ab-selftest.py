#!/usr/bin/env python3
"""rate-ab-selftest.py - unit-run of rate-ab-analyse.py's telemetry analyses on SYNTHETIC captures, and of
rate-ab-live.py's offline parts (struct offsets, ODEF load, approach planning). No game. rate-ab.ps1 -DryRun runs it.

    python rate-ab-selftest.py            # every check, PASS / FAIL per line, exit 1 on any failure

The synthetic captures are written in the exact column layout rate-ab-live.py records, so a layout drift between the
recorder and the analyser fails here. What this cannot show: that the live game produces such telemetry.
"""
import importlib.util, math, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


an, live, mockmod = load("rate-ab-analyse"), load("rate-ab-live"), load("rate-ab-mockgame")
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print("  %s  %s" % ("PASS" if ok else "FAIL", what))


def write(path, cols, rows):
    with open(path, "w", newline="\n") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(live.cell(v) for v in r) + "\n")


# ---- cactus2 ----------------------------------------------------------------------------------------------------------
def cactus_capture(d, fps):
    """Five approaches along +x at 15 m/s: impact+stop, pass-through, 2.5 m wide, speed-only stop, slow arrival."""
    frames, events, t, pf = [], [], 0.0, 1000
    cases = [("hit", 0.1, 15.0), ("pass", 0.1, 15.0), ("miss", 2.5, 15.0), ("speedhit", 0.2, 15.0), ("slow", 0.1, 6.0)]
    for n, (kind, lat, v0) in enumerate(cases, 1):
        tx, tz, x, v = 2000.0 + 100 * n, 49600.0, -30.0, v0
        while x < 25.0 and not (v < 0.2 and x > -5):
            if kind in ("hit", "speedhit") and x >= -2.0:
                if v == v0 and kind == "hit":
                    events.append((n, t, 500 + n, pf, 3, 9.0, 0.0, 1.0, 12.0, 1, 3))      # player, scenery class 3
                    events.append((n, t, 600 + n, pf, 3, 0.0, 2.0, 0.0, 0.0, 1, 0))        # player, terrain: not a hit
                    events.append((n, t, 700 + n, pf, 3, 1.0, 0.0, 0.0, 0.0, 0, 3))        # another car's impact: ignored
                v = max(0.0, v - 60.0 / fps)
            frames.append((n, t, pf, pf, pf, 1, 1.0 / fps, tx + x, 25.0, tz + lat, v, v, 0.0, 0.0, 1, 1.0, tx, tz, 1.0, 0.0, 15.0, n))
            x += v / fps; t += 1.0 / fps; pf += 1
            if v == 0.0:
                break
    p = os.path.join(d, "cactus-%d.frames.csv" % fps)
    write(p, live.CACTUS_COLS, frames)
    write(p.replace(".frames.csv", ".events.csv"), live.EVENT_COLS, events)
    return p


# ---- airborne2 --------------------------------------------------------------------------------------------------------
def rot_x(th):                                               # rows right / up / forward, pitched by th
    c, s = math.cos(th), math.sin(th)
    return [1, 0, 0, 0, c, s, 0, -s, c]


def airborne_capture(d, name, fps, fixed, gain=1.0, w=0.5):
    """3 s at `fps`: ground, 1.2 s airborne at body pitch rate w (the pose turning gain x w), ground. With `fixed`
    the physics steps at 24 Hz and the frames in between repeat the pose with step_count 0; else one step per frame."""
    rows, th, acc, t, frame = [], 0.0, 0.0, 0.0, 100
    for _ in range(int(3.0 * fps)):
        dt = 1.0 / fps
        t += dt; frame += 1
        if fixed:
            acc += dt
            steps = int(acc * 24.0 + 1e-9); acc -= steps / 24.0
            phys = steps / 24.0
        else:
            steps, phys = 1, dt
        air = 1.0 <= t < 2.2
        if air:
            th += gain * w * phys
        rows.append((t, frame, frame, frame, steps, t, dt, dt, phys, 5 if air else 1, 0.0, 30.0, t * 20.0, *rot_x(th),
                     w if air else 0.0, 0.0, 0.0, 0.0, 0.0, 20.0, 20.0, 1.0, 2.0 if air else 0.3))
    p = os.path.join(d, name + ".csv")
    write(p, live.AIR_COLS, rows)
    return p


# ---- farengine --------------------------------------------------------------------------------------------------------
def far_capture(d, name, tau, fps=60, far_rate=60):
    """30 s: the player frozen 800 m up, slot 1 accelerating as vc (1 - exp(-t / tau)) from a 2 s standstill, slot 2 parked."""
    rows, vc, x = [], 30.0, 0.0
    for i in range(1500):
        t = i * 0.02
        frame = int(t * fps)
        v = vc * (1 - math.exp(-(t - 2.0) / tau)) if t > 2.0 else 0.0
        x += v * 0.02
        fs = int(t * far_rate)
        rows += [(t, frame, t, fs, 0, 3337.5, 803.3, 35872.5), (t, frame, t, fs, 1, 3340.0 + x, 3.3, 35880.0),
                 (t, frame, t, fs, 2, 3400.0, 3.3, 35900.0)]
    p = os.path.join(d, name + ".csv")
    write(p, live.FAR_COLS, rows)
    return p


# ---- PER-FRAME-AUDIT-2026-10-03 measures ------------------------------------------------------------------------------
def ram_capture(d, fps, dedupe):
    """Four rams at 15 m/s from 60 m at a target whose face is 8 m from its centre: a ram, an approach that never
    touches, one that arrives slow, one that touches something 50 m out. Per impact the contact is found on k frames
    (k = frames per 24 Hz step: 1 / 3 / 5 at 20 / 60 / 120 fps); the damage call runs on all k without the dedupe."""
    k = {20: 1, 60: 3, 120: 5}[fps]
    frames, events, t, pf, ce, cd = [], [], 0.0, 1000, 40, 7
    for n, (kind, v0) in enumerate((("ram", 15.0), ("none", 15.0), ("slow", 6.0), ("early", 15.0)), 1):
        tx, tz, x, v, hp, left, tc = 3000.0 + 200 * n, 37000.0, -60.0, v0, 1800.0, 0, None
        face = -50.0 if kind == "early" else -8.0
        while t < 1e9:
            if kind != "none" and tc is None and x >= face:
                tc, left = t, k
            if left:
                ce += 1; cd += left < k
                if left == k or not dedupe:
                    events.append((n, t, 5000 + len(events), pf, 3, v, 0.0, 0.0, 25.0, 1, 2)); hp -= 25
                    events.append((n, t, 5000 + len(events), pf, 3, v, 0.0, 0.0, 0.0, 0, 1))     # the building's own damage call
                left -= 1
                if not left:
                    v = 0.0
            frames.append((n, t, pf, pf, pf, 1 if fps == 20 else int(pf % (fps // 24 + 1) == 0), 1.0 / fps, tx + x, 25.0, tz, v, 1, 1.0, hp, ce, cd,
                           int(t * 20), tx, tz, 1.0, 0.0, 15.0, 60.0, 0.0, 0.0, n, "bctest%d" % n))
            x += v / fps; t += 1.0 / fps; pf += 1
            if (tc is not None and t - tc > 1.5) or x > 25.0:
                break
    p = os.path.join(d, "ram-%d-%d.frames.csv" % (fps, dedupe))
    write(p, live.RAM_COLS, frames)
    write(p.replace(".frames.csv", ".events.csv"), live.EVENT_COLS, events)
    return p


def hazard_capture(d, fps, step_hz, counters=True):
    """Drop 3 rounds in 2 projectiles, wait, two search positions, then 8 s on the patch: every projectile steps at
    step_hz, every step in contact gives one ordnance IMPACT per round (15 hp each)."""
    frames, events, t, pf, hs, hi = [], [], 0.0, 500, 0, 0
    acc = 0.0
    for phase, dur in (("drop", 0.12), ("wait", 2.1), ("search", 0.7), ("measure", 8.0)):
        t1 = t + dur
        first = True
        while t < t1:
            if phase == "drop" and first:
                events.append((phase, t, 900, pf, 1, 3.0, 498.0, 15.0, 0.0, 4, 2))
                events.append((phase, t, 901, pf, 1, 3.0, 497.0, 15.0, 0.0, 4, 1))
                events.append((phase, t, 902, pf, 2, 0.0, 0.0, 0.0, 3.0, 0, 0))
            first = False
            acc += step_hz / fps
            n = int(acc + 1e-9); acc -= n
            hs += 2 * n
            if phase == "measure" or (phase == "search" and t > t1 - 0.35):
                hi += n
                for _ in range(3 * n):
                    events.append((phase, t, 1000 + len(events), pf, 3, 0.0, 0.0, 0.0, 15.0, 1, 0x33))
            ammo = 500 if phase == "drop" and t == 0.0 else 497
            frames.append((phase, t, pf, pf, pf, 1, 1.0 / fps, 100.0, 25.0, 200.0, 0.0, 0x401 if phase == "measure" else 1, 1900.0, ammo,
                           hi if counters else "", hs if counters else "", int(t * 20) if counters else "", 2.0 if phase == "measure" else 0.0))
            t += 1.0 / fps; pf += 1
    p = os.path.join(d, "hazard-%d-%d-%d.frames.csv" % (fps, step_hz, counters))
    write(p, live.HAZ_COLS, frames)
    write(p.replace(".frames.csv", ".events.csv"), live.HAZ_EVENT_COLS, events)
    return p


def counter_capture(d, name, fps, seconds, **rates):
    """Counter samples at 50 Hz: every g_idbg counter 0 except the given per-second rates; tick20_n at 20/s."""
    rows = []
    for i in range(int(seconds * 50) + 1):
        t = i * 0.02
        c = {n: 0 for n in live.DBG_NAMES}
        c["tick20_n"] = int(t * 20)
        for n, r in rates.items():
            if n in c:
                c[n] = 77 + int(t * r)
        rows.append([t, 1000 + int(t * fps), t] + [c[n] for n in live.DBG_NAMES] + [0, rates.get("near", "")])
    p = os.path.join(d, name + ".csv")
    write(p, live.CNT_COLS, rows)
    return p


def audit_checks(d):
    print("7. g_idbg layout, computed from the declaration in strlkproxy.c (not from the audit's numbers)")
    try:
        G, size = mockmod.gidbg_layout()
        bad = [n for n in live.DBG_NAMES if G.get(n) != live.DBG[n]]
        check(not bad and size >= live.DBG_END, "all %d counters of rate-ab-live.py match the source (tick20_n +%d ... coll_events +%d, coll_dups +%d; sizeof %d)%s" % (
            len(live.DBG_NAMES), G["tick20_n"], G["coll_events"], G["coll_dups"], size, "; MISMATCH " + ",".join(bad) if bad else ""))
        check(G["ring[0].frame"] == 120 and G["ring[1].frame"] - G["ring[0].frame"] == 112 and G["ping_req"] == 1912,
              "120-byte header, 16 x 112-byte ring, counters from +1912")
        ps1 = open(os.path.join(HERE, "rate-ab.ps1"), encoding="utf-8").read()
        tab = re.search(r"\$RA_DBG = @\{(.*?)\}", ps1, re.S).group(1)
        pairs = {m.group(1): int(m.group(2)) for m in re.finditer(r"(\w+)\s*=\s*(\d+)", tab)}
        size_ps = pairs.pop("Size")
        bad = [n for n, o in pairs.items() if G.get(n) != o]
        check(not bad and {"coll_events", "coll_dups", "wmiss_play", "skid_rolls", "hazard_steps"} <= set(pairs) and max(pairs.values()) + 4 <= size_ps <= size,
              "rate-ab.ps1 $RA_DBG: %d counters match the source, read size %d%s" % (len(pairs), size_ps, "; MISMATCH " + ",".join(bad) if bad else ""))
    except Exception as e:
        check(False, "g_idbg layout from %s: %r" % (mockmod.PROXY_C, e))

    print("8. colldedupe on synthetic rams (1 / 3 / 5 contact frames per impact at 20 / 60 / 120 fps)")
    for fps, want in ((20, 0.0), (60, 2 / 3), (120, 0.8)):
        off, on = an.colldedupe(ram_capture(d, fps, 0)), an.colldedupe(ram_capture(d, fps, 1))
        v = [x["verdict"] for x in off["rows"]]
        check(v == ["RAM", "NO-CONTACT", "SLOW (excluded)", "EARLY (excluded)"], "%d fps verdicts %s" % (fps, v))
        k = round(1 / (1 - want))
        check(abs(off["dup_ratio"] - want) < 1e-9 and off["dup_ratio"] == on["dup_ratio"] and off["events_ram"] == k and off["burst_ram"] == k,
              "%d fps: dup ratio %.3f with and without the dedupe (the counters do not depend on it), %d contact frames per ram" % (fps, off["dup_ratio"], k))
        check((off["impacts_ram"], off["dmg_ram"], off["hp_ram"]) == (k, 25.0 * k, 25.0 * k) and (on["impacts_ram"], on["dmg_ram"], on["hp_ram"]) == (1, 25.0, 25.0),
              "%d fps: damage per ram %.0f hp passed through, %.0f with the dedupe (the building's own damage call is not counted)" % (fps, off["dmg_ram"], on["dmg_ram"]))
    check(abs(off["v_contact"] - 15.0) < 0.01 and abs(off["rows"][0]["at_m"] - 8.0) < 0.3, "contact at %.1f m/s, %.1f m from the target centre" % (off["v_contact"], off["rows"][0]["at_m"]))

    print("9. hazard on synthetic captures (3 rounds in 2 projectiles)")
    for fps, hz in ((20, 20), (60, 20), (120, 20), (120, 120)):
        r = an.hazard(hazard_capture(d, fps, hz))
        check(r["rounds"] == 3 and r["shots"] == 2 and abs(r["impacts_round_s"] - hz) < 0.6 and abs(r["steps_proj_s"] - hz) < 0.6
              and abs(r["hp_round_s"] - 15 * hz) < 9 and abs(r["hz_impacts_s"] - hz) < 0.6,
              "%d fps, hazards stepping at %d Hz: %.1f impacts and %.0f hp per second per round, %.1f steps per second per projectile" % (
                  fps, hz, r["impacts_round_s"], r["hp_round_s"], r["steps_proj_s"]))
    r = an.hazard(hazard_capture(d, 60, 60, counters=False))
    check(r["steps_proj_s"] is None and r["hz_impacts_s"] is None and abs(r["impacts_round_s"] - 60) < 0.6 and r["oil_frac"] == 1.0 and r["offset_m"] == 2.0,
          "stock set (no debug block): counters null, telemetry still gives %.1f impacts per second per round" % r["impacts_round_s"])
    import json
    check("NaN" not in json.dumps(an.clean(r)), "blank counters report nulls, not NaN")

    print("10. wmiss + airolls on synthetic counter samples")
    for fps in (20, 60, 120):
        r = an.wmiss(counter_capture(d, "wmiss-%d" % fps, fps, 5, wmiss_req=fps, wmiss_play=20))
        check(abs(r["wmiss_req_s"] - fps) < 0.5 and abs(r["wmiss_play_s"] - 20) < 0.5 and abs(r["req_per_frame"] - 1) < 0.02 and abs(r["play_per_tick"] - 1) < 0.02,
              "%d fps: wmiss_req %.1f /s (%.2f per frame), wmiss_play %.1f /s (%.2f per tick)" % (fps, r["wmiss_req_s"], r["req_per_frame"], r["wmiss_play_s"], r["play_per_tick"]))
    a, b = an.airolls(counter_capture(d, "roll-hold", 120, 30, skid_rolls=8, horn_rolls=2, near=42.0)), an.airolls(counter_capture(d, "roll-free", 120, 30, skid_rolls=48, horn_rolls=12))
    check(abs(a["skid_rolls_s"] - 8) < 0.2 and abs(b["skid_rolls_s"] - 48) < 0.2 and abs(b["skid_per_tick"] / a["skid_per_tick"] - 6) < 0.1 and a["near_m"] == 42.0 and b["near_m"] is None,
          "skid rolls %.1f /s held, %.1f /s per frame at 120 fps (x%.1f per tick); horn %.1f vs %.1f" % (a["skid_rolls_s"], b["skid_rolls_s"], b["skid_per_tick"] / a["skid_per_tick"], a["horn_rolls_s"], b["horn_rolls_s"]))

    print("11. offline pickers")
    defs = [{"index": 0, "name": "25mm", "klass": 2, "ordnance": 6}, {"index": 1, "name": "Landmines", "klass": 6, "ordnance": 15},
            {"index": 2, "name": "Oil Slick", "klass": 6, "ordnance": 12}, {"index": 3, "name": "Fire-Dropper", "klass": 6, "ordnance": 17}]
    rows = [{"row": 0, "def_index": 0}, {"row": 1, "def_index": 1}]
    check(live.pick_hazard_def(defs, [6, 15, 12, 17], (17, 12))["index"] == 3 and live.pick_hazard_def(defs, [6, 15, 12], (17, 12))["index"] == 2
          and live.pick_hazard_def(defs, [6, 15], (17, 12)) is None, "hazard definition: fire first, oil when fire is not registered, none when neither is")
    check(live.pick_dropper_row(rows, defs, defs[3])[0]["row"] == 1 and live.pick_dropper_row(rows[:1], defs, defs[3])[0]["row"] == 0
          and live.pick_dropper_row([], defs, defs[3])[0] is None, "dropper row: the class 6 row, else the last row, else none")
    check(live.pick_wmiss_row([{"row": 0}, {"row": 1}, {"row": 2}], 1)["row"] == 2 and live.pick_wmiss_row([{"row": 0}], 0) is None,
          "wmiss row: a hardpoint-key row that is not the primary; row 0 alone gives none")
    try:
        _p, objs = live.load_objects("t01")
        uses, got = {}, []
        for _ in range(6):
            k, st = live.plan_ram(objs, uses, (3337.5, 35872.5), (0.0, 1.0), 60.0, ("b",), ("bebridg",))
            uses[k] = uses.get(k, 0) + 1; got.append(objs[k][0])
            ok = all(j == k or o[0].startswith("i") or not (-6 <= (o[3] - st[1]) <= 60 and abs(o[1] - st[0]) < 5.0) for j, o in enumerate(objs))
            if not ok:
                got.append("BLOCKED")
        check(len(set(got)) == 6 and "BLOCKED" not in got, "t01: 6 different buildings with a clear 60 m corridor along +z: %s" % " ".join(got))
        spot = live.near_spot(objs, "t01")
        check(spot is not None and set(spot[1]) == {"t01fc01", "t01fy01", "t01al01"} and all(o[0].startswith("i") or math.hypot(o[1] - spot[0][0], o[3] - spot[0][2]) >= 20 for o in objs),
              "t01 --near: beside %s at (%.0f, %.0f), 20 m clear of every object (Taurus at the start is left out)" % (" ".join(spot[1]), spot[0][0], spot[0][2]))
    except SystemExit as e:
        check(False, "mission ODEF: %s" % e)


def start_mock(*args):
    import subprocess
    suffix = ".selftest%d-%d" % (os.getpid(), start_mock.n)
    start_mock.n += 1
    mock = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "rate-ab-mockgame.py"), "--suffix", suffix, "--seconds", "300", *args],
                            stdout=subprocess.PIPE, text=True)
    line = mock.stdout.readline().strip()
    if not line.startswith("MOCK-READY"):
        mock.kill()
        return None, None, "mock game did not start: %r" % line
    pid, dbg = line.split("pid=")[1].split()[0], line.split("dbg=")[1]

    def run(*argv):
        import json
        out = subprocess.run([sys.executable, "-u", os.path.join(HERE, "rate-ab-live.py"), *argv, "--pid", pid, "--shm-suffix", suffix,
                              "--no-keys", "--dbg", dbg], capture_output=True, text=True)
        js = [l for l in out.stdout.splitlines() if l.startswith("{")]
        return json.loads(js[-1]) if js else {"status": "no JSON: " + (out.stdout + out.stderr)[-400:]}
    return mock, run, None


start_mock.n = 0


def audit_live_leg(d):
    """The four new recorders against mock games at 20 / 60 / 120 fps, in parallel (one mock per condition)."""
    from concurrent.futures import ThreadPoolExecutor
    print("12. the audit recorders end to end against mock games (about a minute, in parallel)")

    def ram(fps, dedupe):
        mock, run, err = start_mock("--fps", str(fps), "--solid", "bcrhopr", "--coll-dedupe", str(dedupe))
        if err:
            return {"status": err}, None
        try:
            out = os.path.join(d, "live-ram-%d-%d" % (fps, dedupe))
            st = run("ram", "--mission", "a01", "--out", out, "--approaches", "3", "--acquire", "3")
            return st, (an.colldedupe(out + ".frames.csv") if st["status"] == "ok" else None)
        finally:
            mock.kill()

    def hazard(fix, kind, extra):
        mock, run, err = start_mock("--hazard-fix", str(fix))
        if err:
            return {"status": err}, None, None
        try:
            out = os.path.join(d, "live-hazard-%d-%s" % (fix, kind))
            st = run("hazard", "--out", out, "--seconds", "5", "--hazard", kind)
            r = an.hazard(out + ".frames.csv") if st["status"] == "ok" else None
            return st, r, extra(run) if extra else None
        finally:
            mock.kill()

    def counters(hold):
        mock, run, err = start_mock("--ai-hold", str(hold))
        if err:
            return {"status": err}, None
        try:
            out = os.path.join(d, "live-rolls-%d" % hold)
            st = run("counters", "--out", out, "--seconds", "4", "--mission", "t01", "--near", "--god")
            return st, (an.airolls(out + ".csv") if st["status"] == "ok" else None)
        finally:
            mock.kill()

    def wmiss_run(run):
        out = os.path.join(d, "live-wmiss")
        st = run("wmiss", "--out", out, "--seconds", "3")
        return st, (an.wmiss(out + ".csv") if st["status"] == "ok" else None)

    with ThreadPoolExecutor(9) as ex:
        rams = {key: ex.submit(ram, *key) for key in ((20, 0), (60, 0), (120, 0), (120, 1))}
        hz = {key: ex.submit(hazard, *key) for key in ((1, "auto", wmiss_run), (0, "fire", None), (1, "oil", None))}
        rl = {hold: ex.submit(counters, hold) for hold in (1, 0)}
        rams, hz, rl = ({k2: f.result() for k2, f in x.items()} for x in (rams, hz, rl))

    for (fps, dedupe), lo, hi in (((20, 0), 0.0, 0.0), ((60, 0), 0.45, 0.70), ((120, 0), 0.72, 0.85), ((120, 1), 0.72, 0.85)):
        st, r = rams[(fps, dedupe)]
        if not r:
            check(False, "ram recorder %d fps dedupe %d: %s" % (fps, dedupe, st)); continue
        print(r["table"])
        check(st["rams"] == 3 and st["contacts"] == 3 and r["valid"] == 3 and lo <= r["dup_ratio"] <= hi,
              "ram %d fps, dedupe %d: 3 rams with contact, dup ratio %.2f (mock mechanism: %.2f..%.2f), %.1f contact frames per ram" % (
                  fps, dedupe, r["dup_ratio"], lo, hi, r["events_ram"]))
        want = 1.0 if dedupe else r["events_ram"]
        check(abs(r["impacts_ram"] - want) < 0.01 and abs(r["dmg_ram"] - 25 * want) < 0.5 and abs(r["hp_ram"] - r["dmg_ram"]) < 0.5 and 12 < r["v_contact"] < 16.5,
              "    %.1f player impacts and %.0f hp per ram (armour + chassis lost %.0f), contact at %.1f m/s" % (r["impacts_ram"], r["dmg_ram"], r["hp_ram"], r["v_contact"]))
    for (fix, kind, _x), hzw in (((1, "auto", wmiss_run), 20.0), ((0, "fire", None), 60.0), ((1, "oil", None), 20.0)):
        st, r, extra = hz[(fix, kind, _x)]
        if not r:
            check(False, "hazard recorder fix %d %s: %s" % (fix, kind, st)); continue
        print("  " + r["text"].replace("\n", "\n  "))
        name = "Oil Slick" if kind == "oil" else "Fire-Dropper"
        check(st["hazard"] == name and st["swapped"] and st["restored"] and st["row"] == 3 and st["offset_m"] == 2.0 and st["rounds"] == r["rounds"] > 0,
              "hazard (%s, fix %d): row 3 pointed at %s and restored, %d rounds in %d projectiles, contact found 2.0 m behind" % (kind, fix, st["hazard"], st["rounds"], st["shots"]))
        tol = 0.12 * hzw
        check(abs(r["impacts_round_s"] - hzw) < tol and abs(r["steps_proj_s"] - hzw) < tol and (r["oil_frac"] > 0.95) == (kind == "oil")
              and (kind == "oil") == (r["hp_s"] == 0),
              "    %.1f impacts per second per round and %.1f steps per second per projectile (mock steps at %.0f Hz), oil flag %.0f%%, %.0f hp/s" % (
                  r["impacts_round_s"], r["steps_proj_s"], hzw, 100 * r["oil_frac"], r["hp_s"]))
        if extra:
            st, r = extra
            check(bool(r) and st["restored"] and st["row"] == 1 and st["hp_was"] == 200 and abs(r["play_per_tick"] - 1) < 0.05 and r["req_per_frame"] > 0.9
                  and 2.5 < r["wmiss_req_s"] / r["wmiss_play_s"] < 3.5,
                  "wmiss recorder: row 1 condition 200 -> 0 -> restored; %s" % (r["text"] if r else st))
    (s1, r1), (s0, r0) = rl[1], rl[0]
    if not (r1 and r0):
        check(False, "counters recorder: %s / %s" % (s1, s0))
    else:
        check(s1["placed"] and s1["god"] and abs(r1["skid_per_tick"] - 0.5) < 0.06 and abs(r0["skid_per_tick"] - 1.5) < 0.12 and abs(r0["horn_per_tick"] - 0.75) < 0.08,
              "counters recorder (--near placed, god held): skid rolls per tick %.2f held vs %.2f every frame at 60 fps; horn %.2f vs %.2f" % (
                  r1["skid_per_tick"], r0["skid_per_tick"], r1["horn_per_tick"], r0["horn_per_tick"]))


def live_leg(d):
    """rate-ab-live.py's three recorders, for real, against rate-ab-mockgame.py (suffixed shared memory, no key input)."""
    import json, subprocess
    print("6. the recorders end to end against the mock game (about a minute)")
    suffix = ".selftest%d" % os.getpid()
    mock = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "rate-ab-mockgame.py"), "--suffix", suffix, "--seconds", "240"],
                            stdout=subprocess.PIPE, text=True)
    try:
        line = mock.stdout.readline().strip()
        if not line.startswith("MOCK-READY"):
            check(False, "mock game did not start: %r" % line)
            return
        pid = line.split("pid=")[1].split()[0]
        dbg = line.split("dbg=")[1]

        def run(*argv):
            out = subprocess.run([sys.executable, "-u", os.path.join(HERE, "rate-ab-live.py"), *argv, "--pid", pid, "--shm-suffix", suffix,
                                  "--no-keys"], capture_output=True, text=True)
            js = [l for l in out.stdout.splitlines() if l.startswith("{")]
            if not js:
                print(out.stdout + out.stderr)
                return {"status": "no JSON"}
            return json.loads(js[-1])

        st = run("cactus", "--out", os.path.join(d, "live-cactus"), "--approaches", "4")
        check(st["status"] == "ok" and st["approaches"] == 4 and st["acquired"], "cactus recorder: %s" % {k: st.get(k) for k in ("status", "approaches", "acquired", "notes")})
        if st["status"] == "ok":
            r = an.cactus2(os.path.join(d, "live-cactus.frames.csv"))
            print(r["table"])
            v = [x["verdict"] for x in r["rows"]]
            check(v == ["HIT", "PASS-THROUGH", "HIT", "PASS-THROUGH"], "verdicts match the mock's ground truth (odd crossings hit): %s" % v)
            check(r["hits_impact"] == 2 and r["hits_speed"] == 2 and all(x["line_off"] < 0.3 for x in r["rows"]),
                  "both hit signals on both hits; every approach within 0.3 m of the trunk line (max %.2f m)" % max(x["line_off"] for x in r["rows"]))
            check(abs(r["v_before"] - 15.0) < 1.0 and 0.3 < r["steps_frame"] < 0.5, "arrival speed %.1f m/s, %.2f steps per frame (24 Hz under 60 fps)" % (r["v_before"], r["steps_frame"]))
        st = run("airborne", "--out", os.path.join(d, "live-air"), "--seconds", "8", "--fixed-step", "24", "--place", "7930", "24", "42580", "28")
        check(st["status"] == "ok" and st["placed_ok"] and st["airborne_frames"] > 20, "airborne recorder: %s" % st)
        if st["status"] == "ok":
            r = an.airborne2(os.path.join(d, "live-air.csv"))
            print(r["text"])
            check(r["segments"] == 1 and abs(r["gain"] - 1.0) < 0.05, "one jump, gain %.3f (the mock integrates with gain 1), %.2f s airborne" % (r["gain"] or 0, r["air_s"]))
        st = run("farengine", "--out", os.path.join(d, "live-far"), "--seconds", "14", "--dbg", dbg)
        check(st["status"] == "ok" and abs(st["lifted_m"] - 800) < 2, "farengine recorder: %s" % st)
        if st["status"] == "ok":
            r = an.farengine(os.path.join(d, "live-far.csv"))
            print(r["text"])
            check(r["slot"] == 1 and abs(r["cruise_ms"] - 25) < 3 and 4.0 < r["t_cruise_s"] < 9.0 and r["min_dist_m"] > 625 and 50 < r["far_steps_s"] < 70,
                  "slot 1: cruise %.1f m/s, t_cruise %.2f s (tau 3 s), min distance %.0f m, far_steps %.1f / s" % (
                      r["cruise_ms"], r["t_cruise_s"], r["min_dist_m"], r["far_steps_s"]))
    finally:
        mock.kill()


def main():
    d = tempfile.mkdtemp(prefix="rate-ab-selftest-")
    print("1. recorder layout")
    check(live.TRN_SIZE == 168 and live.TRN_OFF["vel0"] == 60 and live.TRN_OFF["flags"] == 8 and live.TRN_OFF["req_seq"] == 20,
          "trainer block: %d bytes, flags +8, req_seq +20, pos +36, vel +60 (i76trn.h)" % live.TRN_SIZE)
    try:
        tel = live.Tel(live.DEF_TOOLS)
        need = {"seq", "frame", "proxy_frame", "step_count", "sim_dt", "pos_0", "rot_8", "pitch_rate", "yaw_rate", "roll_rate",
                "flags", "throttle", "velocity_2", "speed", "obj_addr", "event_seq", "clearance", "sim_time", "dt"}
        check(need <= set(tel.h.frame_names), "i76tel.h has every frame field the recorder reads (frame %d B)" % tel.h.frame_size)
        check({"seq", "frame", "type", "f_3", "i_0", "i_1"} <= set(tel.h.event_names) and tel.h.consts["I76TEL_EV_IMPACT"] == an.EV_IMPACT,
              "i76tel.h event fields; I76TEL_EV_IMPACT = %d" % an.EV_IMPACT)
    except Exception as e:                                   # the header lives in the other repo
        check(False, "i76tel.h not loadable from %s: %s" % (live.DEF_TOOLS, e))

    print("2. ODEF + approach planning")
    try:
        for msn, want in (("a01", 89), ("t01", 9)):
            path, objs = live.load_objects(msn)
            n = sum(1 for o in objs if o[0].startswith("nsaguar"))
            check(n == want, "%s: %d nsaguar* in the ODEF (want %d) - %s" % (msn, n, want, os.path.basename(os.path.dirname(path))))
        path, objs = live.load_objects("a01")
        for f in ((1.0, 0.0), (0.0, 1.0), (-0.6, 0.8)):
            used, pos, got = set(), (1362.5, 49612.5), 0
            for _ in range(6):
                p = live.plan_approach(objs, used, pos, f, 30.0)
                if not p:
                    break
                k, s = p
                used.add(k); got += 1
                ok = all(not (-6 <= (o[1] - s[0]) * f[0] + (o[3] - s[1]) * f[1] <= 55 and
                              abs((o[1] - s[0]) * f[1] - (o[3] - s[1]) * f[0]) < 5.0) for j, o in enumerate(objs) if j != k)
                if not ok:
                    got = -99
                pos = (objs[k][1] + 25 * f[0], objs[k][3] + 25 * f[1])
            check(got == 6, "a01 heading (%.1f, %.1f): 6 distinct cacti with a clear 55 m corridor" % f)
    except SystemExit as e:
        check(False, "mission ODEF: %s" % e)
    toy = [("nsaguar1", 100.0, 0.0, 0.0), ("nsaguar1", 85.0, 0.0, 1.0), ("nsaguar1", 100.0, 0.0, 50.0), ("bcbank1", 300.0, 0.0, 0.0)]
    p = live.plan_approach(toy, set(), (60.0, 0.0), (1.0, 0.0), 30.0)
    check(p is not None and p[0] == 2 and p[1] == (70.0, 50.0), "blocked corridors are skipped (toy field picks cactus #2, start (70, 50))")
    check(live.heading({"rot_6": 0.6, "rot_8": 0.8, "rot_4": 0.99}) == (0.6, 0.8) and live.heading({"rot_6": 0.6, "rot_8": 0.8, "rot_4": 0.2}) is None,
          "heading from rot rows; a car on its side gives none")

    print("3. cactus2 on synthetic telemetry (hit + impact, pass-through, wide miss, speed-only hit, slow arrival)")
    for fps in (20, 60, 120):
        r = an.cactus2(cactus_capture(d, fps))
        v = [x["verdict"] for x in r["rows"]]
        check(v == ["HIT", "PASS-THROUGH", "MISS (excluded)", "HIT", "SLOW (excluded)"], "%d fps verdicts %s" % (fps, v))
        check((r["approaches"], r["valid"], r["hits"], r["hits_impact"], r["hits_speed"]) == (5, 3, 2, 1, 2) and abs(r["hit_rate"] - 2 / 3) < 1e-9,
              "%d fps: 5 approaches, 3 valid, 2 hits (1 by impact event, 2 by speed), hit rate %.3f" % (fps, r["hit_rate"]))
        check(r["rows"][0]["classes"] == [3, 0], "%d fps: the other car's impact is ignored, terrain is not a hit (classes %s)" % (fps, r["rows"][0]["classes"]))

    print("4. airborne2 on synthetic telemetry (0.5 rad/s for 1.2 s)")
    for name, fps, fixed, gain in (("stock20", 20, False, 1.0), ("stock60", 60, False, 1.0), ("stock60-under", 60, False, 0.39),
                                   ("fixed60", 60, True, 1.0), ("fixed120", 120, True, 1.0), ("fixed120-over", 120, True, 3.0)):
        r = an.airborne2(airborne_capture(d, name, fps, fixed, gain))
        check(r["segments"] == 1 and r["gain"] is not None and abs(r["gain"] - gain) < 0.02 * gain,
              "%s: gain %.3f (want %.2f), %d segment, %.2f s airborne, %d of %d frames carry a step" % (
                  name, r["gain"] or 0, gain, r["segments"], r["air_s"], r["step_frames"], r["samples"]))
    r = an.airborne2(airborne_capture(d, "norot", 60, True, 1.0, w=0.0))
    check(r["segments"] == 0 and r["segments_seen"] == 1 and r["gain"] is None, "no commanded rotation: segment seen, not used, gain null")

    print("5. farengine on synthetic samples (cruise 30 m/s; time constant 2 s vs 6 s)")
    a, b = an.farengine(far_capture(d, "tau2", 2.0)), an.farengine(far_capture(d, "tau6", 6.0, far_rate=0))
    check(a["slot"] == 1 and a["cars"] == 2 and a["moving"] == 1, "slot 1 is the moving car (slot 2 parked, slot 0 the player)")
    check(abs(a["cruise_ms"] - 30) < 1.5 and 2.5 < a["t_cruise_s"] < 5.5, "tau 2 s: cruise %.1f m/s, t_cruise %.2f s" % (a["cruise_ms"], a["t_cruise_s"]))
    check(b["t_cruise_s"] > 2.0 * a["t_cruise_s"], "tau 6 s: t_cruise %.2f s (%.1fx the tau 2 run)" % (b["t_cruise_s"], b["t_cruise_s"] / a["t_cruise_s"]))
    check(abs(a["far_steps_s"] - 60) < 1 and b["far_steps_s"] == 0, "far_steps %.1f / s counted, %.1f when the counter stands still" % (a["far_steps_s"], b["far_steps_s"]))
    check(a["min_dist_m"] > 625, "min distance to the lifted player %.0f m" % a["min_dist_m"])
    import json
    check("NaN" not in json.dumps(an.clean(an.farengine(far_capture(d, "one", 2.0), 2))), "a parked car reports nulls, not NaN")

    audit_checks(d)

    if "--live" in sys.argv:
        live_leg(d)
        audit_live_leg(d)

    if fails or "--keep" in sys.argv:
        print("%d failure(s); synthetic captures kept in %s" % (fails, d))
    else:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
        print("0 failure(s)  (--keep leaves the synthetic captures on disk)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
