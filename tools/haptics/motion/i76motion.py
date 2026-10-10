#!/usr/bin/env python3
"""i76motion.py - validator for the haptics host's motion output (docs/MOTION-OUTPUT.md 5.4). Offline, Python 3, stdlib only.

Decodes every wire format the host writes, auto-detected by size / magic: i76motion (144 B, 'I76M'), LFS OutSim classic
(64 / 68 B), OutSimPack2 (280 B, 'LFST'), OutGauge (92 / 96 B), Forza Sled (232 B) and Dash (311 B). Layouts come from
tools/haptics/schema/i76motion.json and schema/motion-wire.json, the same files the C# tests assert the encoders
against.

  python i76motion.py --decode LOG.i76rec [--limit 20]       print decoded packets (any format)
  python i76motion.py --check LOG.i76rec [...] [--expect synth-braking.expect.json] [--hz 100]
                                                             conformance + (optional) a scenario's expected values
  python i76motion.py --plot LOG.i76rec OUT.html             six-DOF / angles / dash / cue traces, static HTML
  python i76motion.py --preview LOG.i76rec OUT.html          motion_preview.html with this log embedded (3D car + rig)
  python i76motion.py --sniff [--port 7677 --port 4123 ...] [--seconds 30] [--log DIR] [--then-check]
                                                             listen on 127.0.0.1 (ONLY when no consumer holds the port),
                                                             decode, print rate / jitter / seq gaps / stale periods

LOG files are what `haptics.ps1 motion` writes (out\\motion\\<tag>.<target>.<format>.i76rec: the .i76rec container, one
motion datagram per record, timestamped on the motion clock) or what --sniff --log writes.
Exit status: 0 all checks passed, 1 a check failed, 2 usage.
"""
import argparse, json, math, os, socket, select, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
HAPTICS = os.path.dirname(HERE)
SCHEMA = os.path.join(HAPTICS, "schema")
sys.path.insert(0, os.path.join(HAPTICS, "design"))
import i76rec  # noqa: E402

TYPES = {"f32": ("f", 4), "i32": ("i", 4), "u32": ("I", 4), "u16": ("H", 2), "s16": ("h", 2), "u8": ("B", 1), "s8": ("b", 1),
         "char4": ("4s", 4), "char16": ("16s", 16)}


def load_formats():
    """{format name: {"size": n, "fields": [[off, type, name, unit, note], ...], ...}} for all six formats."""
    fm = {}
    with open(os.path.join(SCHEMA, "motion-wire.json"), encoding="utf-8") as f:
        fm.update(json.load(f)["formats"])
    with open(os.path.join(SCHEMA, "i76motion.json"), encoding="utf-8") as f:
        im = json.load(f)
    fm["i76motion"] = im
    return fm


FORMATS = load_formats()


def detect(data):
    n = len(data)
    if n >= 4 and data[:4] == b"I76M":
        return "i76motion"
    if n == 280 and data[:4] == b"LFST":
        return "lfs-pack2"
    if n in (64, 68):
        return "lfs-classic"
    if n in (92, 96):
        return "outgauge"
    if n == 232:
        return "forza-sled"
    if n == 311:
        return "forza-dash"
    if n in (324, 331):
        return "forza-dash"       # FH4/FH5 324, FM2023 331: decoded with the FM7 offsets (first 232 bytes match)
    return None


def decode(data, fmt=None):
    """(format, {field: value}) or (None, None). char fields come back as str."""
    fmt = fmt or detect(data)
    if fmt is None:
        return None, None
    out = {}
    for off, typ, name, unit, note in FORMATS[fmt]["fields"]:
        code, size = TYPES[typ]
        if off + size > len(data):
            continue
        v = struct.unpack_from("<" + code, data, off)[0]
        if isinstance(v, bytes):
            v = v.split(b"\0", 1)[0].decode("ascii", "replace")
        out[name] = v
    return fmt, out


def status_bits(st):
    names = {0: "live", 1: "air", 2: "skid", 3: "destroyed", 4: "paused", 5: "NEUTRAL", 6: "interp", 7: "cue", 31: "SHUTDOWN"}
    return ",".join(n for b, n in names.items() if st & (1 << b)) + " surf %d gear %d" % ((st >> 8) & 0xff, (st >> 16) & 0xff)


def load_log(path):
    meta, recs = i76rec.read(path)
    return meta, recs


def line(fmt, d):
    if fmt == "i76motion":
        return ("t %7.3f seq %5d | surge %+7.2f sway %+7.2f heave %+7.2f | roll %+6.2f pitch %+6.2f deg hdg %+7.1f | "
                "yaw %+5.2f | v %5.1f rpm %4.0f g %+.0f | cue %+6.1f %+6.1f %+6.1f | %s") % (
            d["t_sim"], d["seq"], d["surge"], d["sway"], d["heave"], math.degrees(d["roll"]), math.degrees(d["pitch"]),
            math.degrees(d["heading"]), d["yaw_rate"], d["speed"], d["rpm"], d["gear"], d["cue_surge"], d["cue_sway"], d["cue_heave"],
            status_bits(d["status"]))
    if fmt in ("lfs-classic", "lfs-pack2"):
        return ("t %8d ms | acc X %+7.2f Y %+7.2f Z %+7.2f | angvel %+5.2f %+5.2f %+5.2f | hdg %+6.3f pitch %+6.3f roll %+6.3f | "
                "vel %+6.2f %+6.2f %+6.2f%s") % (
            d["time"], d["accel_x"], d["accel_y"], d["accel_z"], d["angvel_x"], d["angvel_y"], d["angvel_z"], d["heading"], d["pitch"],
            d["roll"], d["vel_x"], d["vel_y"], d["vel_z"],
            " | id %d thr %.2f brk %.2f gear %d" % (d["id"], d["throttle"], d["brake"], d["gear"]) if fmt == "lfs-pack2" else "")
    if fmt == "outgauge":
        return "t %8d ms | %s gear %d speed %.2f rpm %.0f thr %.2f brk %.2f lights 0x%x/0x%x '%s'" % (
            d["time"], d["car"], d["gear"], d["speed"], d["rpm"], d["throttle"], d["brake"], d["dash_lights"], d["show_lights"], d["display1"])
    if fmt.startswith("forza"):
        return ("race %d t %8d ms | acc x %+7.2f y %+7.2f z %+7.2f | angvel %+5.2f %+5.2f %+5.2f | yaw %+6.3f pitch %+6.3f roll %+6.3f | rpm %.0f%s") % (
            d["is_race_on"], d["timestamp_ms"], d["accel_x"], d["accel_y"], d["accel_z"], d["angvel_x"], d["angvel_y"], d["angvel_z"],
            d["yaw"], d["pitch"], d["roll"], d["current_engine_rpm"],
            " | speed %.2f gear %d steer %d" % (d["speed"], d["gear"], d["steer"]) if fmt == "forza-dash" else "")
    return str(d)


# ---------------------------------------------------------------------------------------------------------------- check
class Result:
    def __init__(self):
        self.passed, self.failed = 0, 0
        self.lines = []

    def check(self, name, ok, detail=""):
        if ok:
            self.passed += 1
            self.lines.append("  PASS  " + name + ("  (" + detail + ")" if detail else ""))
        else:
            self.failed += 1
            self.lines.append("  FAIL  " + name + ("  (" + detail + ")" if detail else ""))
        return ok


def finite(d):
    return all(not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) for v in d.values())


def conformance(recs, meta, res, hz=None, label=""):
    """recs: [(t, bytes)]. Size / magic / monotonic time / NaN / ranges / status consistency / rate."""
    fmts = set()
    decoded = []
    bad_size = 0
    for t, b in recs:
        fmt, d = decode(b)
        if fmt is None:
            bad_size += 1
            continue
        fmts.add(fmt)
        decoded.append((t, fmt, d, len(b)))
    p = label + ": " if label else ""
    res.check(p + "every packet is a known format (size / magic)", bad_size == 0 and len(decoded) > 0, "%d packets, %d unknown" % (len(recs), bad_size))
    if not decoded:
        return []
    res.check(p + "one format per stream", len(fmts) == 1, ", ".join(sorted(fmts)))
    fmt = decoded[0][1]
    sizes = sorted(set(n for _, _, _, n in decoded))
    want = {FORMATS[fmt]["size"], FORMATS[fmt].get("size_with_id", FORMATS[fmt]["size"])}
    res.check(p + "%s sizes exact %s" % (fmt, sorted(want)), set(sizes) <= want, "seen %s" % sizes)
    res.check(p + "no NaN / inf", all(finite(d) for _, _, d, _ in decoded))
    if fmt == "i76motion":
        res.check(p + "magic I76M, version 1, size 144", all(d["magic"] == "I76M" and d["version"] == 1 and d["size"] == 144 for _, _, d, _ in decoded))
        ts = [d["t_sim"] for _, _, d, _ in decoded]
        res.check(p + "t_sim monotonic", all(b >= a for a, b in zip(ts, ts[1:])))
        seqs = [d["seq"] for _, _, d, _ in decoded]
        gaps = sum(1 for a, b in zip(seqs, seqs[1:]) if b != a + 1)
        res.check(p + "seq contiguous", gaps == 0, "%d gaps" % gaps)
        res.check(p + "angles within +-pi", all(abs(d[k]) <= math.pi + 1e-6 for _, _, d, _ in decoded for k in ("roll", "pitch", "heading")))
        res.check(p + "steady accelerations within +-40 m/s^2", all(abs(d[k]) <= 40 for _, _, d, _ in decoded for k in ("surge", "sway", "heave")),
                  "max %.1f" % max(abs(d[k]) for _, _, d, _ in decoded for k in ("surge", "sway", "heave")))
        res.check(p + "cues within +-200 m/s^2", all(abs(d[k]) <= 200 for _, _, d, _ in decoded for k in ("cue_surge", "cue_sway", "cue_heave")))
        air = [d for _, _, d, _ in decoded if d["status"] & 2 and not d["status"] & 64]
        res.check(p + "airborne -> physics channels 0 (airborne_zero_physics)", all(abs(d["surge"]) + abs(d["sway"]) + abs(d["heave"]) < 1e-4 for d in air),
                  "%d airborne ticks" % len(air))
        res.check(p + "gear in -1..3", all(-1 <= d["gear"] <= 3 for _, _, d, _ in decoded))
        res.check(p + "last packet is the shutdown tick (bit 31) with zero motion",
                  bool(decoded[-1][2]["status"] & (1 << 31)) and abs(decoded[-1][2]["surge"]) + abs(decoded[-1][2]["roll"]) == 0)
    elif fmt in ("lfs-classic", "lfs-pack2"):
        ts = [d["time"] for _, _, d, _ in decoded]
        res.check(p + "Time monotonic (ms)", all(b >= a for a, b in zip(ts, ts[1:])))
        res.check(p + "angles within +-pi", all(abs(d[k]) <= math.pi + 1e-6 for _, _, d, _ in decoded for k in ("heading", "pitch", "roll")))
        res.check(p + "accelerations (physics + cues) within +-200", all(abs(d[k]) <= 200 for _, _, d, _ in decoded for k in ("accel_x", "accel_y", "accel_z")))
        if fmt == "lfs-pack2":
            res.check(p + "LFST header", all(d["header"] == "LFST" for _, _, d, _ in decoded))
            res.check(p + "gear byte 0..5", all(0 <= d["gear"] <= 5 for _, _, d, _ in decoded))
    elif fmt == "outgauge":
        res.check(p + "Car tag 'I76'", all(d["car"].startswith("I76") for _, _, d, _ in decoded))
        res.check(p + "speed >= 0, rpm 0..8000", all(d["speed"] >= 0 and 0 <= d["rpm"] <= 8000 for _, _, d, _ in decoded))
    elif fmt.startswith("forza"):
        res.check(p + "IsRaceOn 0 / 1", all(d["is_race_on"] in (0, 1) for _, _, d, _ in decoded))
        res.check(p + "angles within +-pi", all(abs(d[k]) <= math.pi + 1e-6 for _, _, d, _ in decoded for k in ("yaw", "pitch", "roll")))
        res.check(p + "accelerations within +-200", all(abs(d[k]) <= 200 for _, _, d, _ in decoded for k in ("accel_x", "accel_y", "accel_z")))
    # rate on the log's own clock
    hz = hz or (meta or {}).get("output_hz")
    if hz and len(decoded) > 10:
        dts = sorted(b[0] - a[0] for a, b in zip(decoded, decoded[1:]) if b[0] > a[0])
        med = dts[len(dts) // 2] if dts else 0
        rate = 1.0 / med if med > 0 else 0
        res.check(p + "packet rate within 5%% of %g Hz" % hz, abs(rate - hz) <= 0.05 * hz, "median interval %.2f ms = %.1f Hz" % (med * 1000, rate))
    return decoded


def window(decoded, t0, t1):
    return [d for t, fmt, d, _ in decoded if t0 <= d.get("t_sim", t) <= t1]


def expectations(decoded, exp, res):
    for c in exp["checks"]:
        w = window(decoded, c["t0"], c["t1"])
        name = "%s: %s [%.2f-%.2f s]" % (exp["scenario"], c["name"], c["t0"], c["t1"])
        if not w:
            res.check(name, False, "no packets in the window")
            continue
        st = c["stat"]
        if st.startswith(("all_bit", "any_bit", "none_bit")):
            bit = int(st.split("bit")[1])
            hits = [bool(d["status"] & (1 << bit)) for d in w]
            ok = all(hits) if st.startswith("all") else any(hits) if st.startswith("any") else not any(hits)
            res.check(name, ok, "%d / %d ticks with bit %d" % (sum(hits), len(hits), bit))
            continue
        xs = [d[c["channel"]] for d in w]
        if st == "mean":
            v = sum(xs) / len(xs)
        elif st == "min":
            v = min(xs)
        elif st == "max":
            v = max(xs)
        elif st == "absmax":
            v = max(abs(x) for x in xs)
        elif st == "maxstep":
            v = max([abs(b - a) for a, b in zip(xs, xs[1:])] or [0])
        else:
            res.check(name, False, "unknown stat " + st)
            continue
        res.check(name, c["lo"] - 1e-9 <= v <= c["hi"] + 1e-9, "%s %s = %.5g, expected %.5g..%.5g (n %d)" % (st, c["channel"], v, c["lo"], c["hi"], len(xs)))


def cmd_check(paths, expect=None, hz=None, quiet=False):
    res = Result()
    exp = None
    if expect:
        with open(expect, encoding="utf-8") as f:
            exp = json.load(f)
    any_motion = False
    for p in paths:
        meta, recs = load_log(p)
        dec = conformance(recs, meta, res, hz, os.path.basename(p))
        if exp and dec and dec[0][1] == "i76motion":
            expectations(dec, exp, res)
            any_motion = True
    if exp and not any_motion:
        res.check("an i76motion log for the expectations", False, "expectations are evaluated on i76motion packets: pass the <tag>.native.i76motion.i76rec log")
    for ln in res.lines:
        if not quiet or ln.startswith("  FAIL"):
            print(ln)
    print("=== %d passed, %d failed ===" % (res.passed, res.failed))
    return 0 if res.failed == 0 else 1


# ---------------------------------------------------------------------------------------------------------------- plot
PLOT_PANELS = [
    ("Physics acceleration (m/s², + forward / right / up)", [("surge", 1), ("sway", 1), ("heave", 1)]),
    ("Cue spikes (m/s²)", [("cue_surge", 1), ("cue_sway", 1), ("cue_heave", 1)]),
    ("Body rates (rad/s, + roll right / nose up / turn right)", [("roll_rate", 1), ("pitch_rate", 1), ("yaw_rate", 1)]),
    ("Angles (deg, + right side down / nose up)", [("roll", 180 / math.pi), ("pitch", 180 / math.pi)]),
    ("Speed (m/s) and gear", [("speed", 1), ("gear", 1)]),
    ("Pedals and steer", [("throttle", 1), ("brake", 1), ("steer", 1)]),
]


def series_from_log(path):
    meta, recs = load_log(path)
    rows = []
    for t, b in recs:
        fmt, d = decode(b)
        if fmt != "i76motion":
            raise SystemExit("%s: --plot / --preview read i76motion logs (got %s); use the <tag>.native.i76motion.i76rec log" % (path, fmt))
        rows.append(d)
    return meta, rows


def cmd_plot(path, out):
    meta, rows = series_from_log(path)
    data = {"t": [round(r["t_sim"], 4) for r in rows], "status": [r["status"] for r in rows]}
    for _, chans in PLOT_PANELS:
        for ch, k in chans:
            data[ch] = [round(r[ch] * k, 5) for r in rows]
    with open(os.path.join(HERE, "plot.template.html"), encoding="utf-8") as f:
        html = f.read()
    payload = {"title": os.path.basename(path), "meta": meta, "panels": [[t, [c for c, _ in ch]] for t, ch in PLOT_PANELS], "data": data}
    html = html.replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("wrote %s (%d ticks)" % (out, len(rows)))
    return 0


def cmd_preview(path, out):
    meta, rows = series_from_log(path)
    keys = ["t_sim", "status", "surge", "sway", "heave", "roll", "pitch", "heading", "yaw_rate", "speed", "cue_surge", "cue_sway", "cue_heave"]
    data = {k: [round(r[k], 5) for r in rows] for k in keys}
    with open(os.path.join(HERE, "motion_preview.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*__EMBEDDED__*/null", json.dumps({"name": os.path.basename(path), "data": data}, separators=(",", ":")))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("wrote %s (%d ticks) - open it in a browser" % (out, len(rows)))
    return 0


# ---------------------------------------------------------------------------------------------------------------- sniff
DEFAULT_PORTS = [7677, 4123, 4124, 63393, 63392, 5300]


def cmd_sniff(ports, seconds, log_dir, do_check, quiet):
    socks = {}
    for p in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("127.0.0.1", p))
        except OSError as e:
            print("port %d: cannot bind (%s) - a consumer (FlyPT / SimHub / SimTools) probably holds it; close it to sniff here" % (p, e))
            s.close()
            continue
        s.setblocking(False)
        socks[s] = p
    if not socks:
        return 2
    print("sniffing 127.0.0.1 ports %s%s; Ctrl+C stops" % (", ".join(str(p) for p in socks.values()), " for %g s" % seconds if seconds else ""))
    st = {p: {"n": 0, "fmt": None, "t": [], "last": None, "seq": None, "gaps": 0, "stale": 0, "recs": []} for p in socks.values()}
    t0 = time.perf_counter(); next_print = t0 + 1.0
    try:
        while True:
            now = time.perf_counter()
            if seconds and now - t0 >= seconds:
                break
            r, _, _ = select.select(list(socks), [], [], 0.05)
            for s in r:
                try:
                    data, _ = s.recvfrom(2048)
                except OSError:
                    continue
                now = time.perf_counter()
                p = socks[s]; q = st[p]
                fmt, d = decode(data)
                q["n"] += 1; q["fmt"] = fmt or "unknown(%d B)" % len(data)
                if q["t"] and now - q["t"][-1] > 0.25:
                    q["stale"] += 1
                q["t"].append(now); q["last"] = (fmt, d)
                q["recs"].append((now - t0, data))
                if fmt == "i76motion":
                    if q["seq"] is not None and d["seq"] != q["seq"] + 1:
                        q["gaps"] += 1
                    q["seq"] = d["seq"]
            if now >= next_print:
                next_print += 1.0
                for p, q in st.items():
                    ts = q["t"][-200:]
                    if len(ts) < 2:
                        print("  :%-5d no packets" % p)
                        continue
                    dts = sorted(b - a for a, b in zip(ts, ts[1:]))
                    rate = (len(ts) - 1) / (ts[-1] - ts[0]) if ts[-1] > ts[0] else 0
                    print("  :%-5d %-11s %6d pkts %6.1f Hz  jitter p50 %.1f p95 %.1f ms  seq gaps %d  stale %d" % (
                        p, q["fmt"], q["n"], rate, dts[len(dts) // 2] * 1000, dts[int(len(dts) * 0.95)] * 1000, q["gaps"], q["stale"]))
                    if not quiet and q["last"][0]:
                        print("         " + line(*q["last"]))
    except KeyboardInterrupt:
        pass
    for s in socks:
        s.close()
    rc = 0
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        for p, q in st.items():
            if q["recs"]:
                path = os.path.join(log_dir, "sniff-%d.i76rec" % p)
                i76rec.write(path, q["recs"], {"source": "i76motion.py --sniff", "port": p, "payload": "motion"})
                print("  log :%d -> %s" % (p, path))
    if do_check:
        res = Result()
        for p, q in st.items():
            if q["recs"]:
                conformance(q["recs"], {}, res, None, ":%d" % p)
        for ln in res.lines:
            print(ln)
        print("=== %d passed, %d failed ===" % (res.passed, res.failed))
        rc = 0 if res.failed == 0 else 1
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(description="haptics motion output validator", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--decode", metavar="LOG")
    g.add_argument("--check", nargs="+", metavar="LOG")
    g.add_argument("--plot", nargs=2, metavar=("LOG", "OUT_HTML"))
    g.add_argument("--preview", nargs=2, metavar=("LOG", "OUT_HTML"))
    g.add_argument("--sniff", action="store_true")
    ap.add_argument("--expect")
    ap.add_argument("--hz", type=float)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--port", type=int, action="append")
    ap.add_argument("--seconds", type=float, default=0)
    ap.add_argument("--log")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--then-check", dest="then_check", action="store_true", help="with --sniff: run the conformance checks on what was captured")
    a = ap.parse_args(argv)
    if a.decode:
        meta, recs = load_log(a.decode)
        print("%s: %d packets, meta %s" % (a.decode, len(recs), json.dumps(meta)))
        for k, (t, b) in enumerate(recs):
            if a.limit and k >= a.limit:
                break
            fmt, d = decode(b)
            print("%9.3f %-11s %s" % (t, fmt, line(fmt, d) if fmt else "unknown %d B" % len(b)))
        return 0
    if a.check:
        return cmd_check(a.check, a.expect, a.hz, a.quiet)
    if a.plot:
        return cmd_plot(*a.plot)
    if a.preview:
        return cmd_preview(*a.preview)
    if a.sniff:
        return cmd_sniff(a.port or DEFAULT_PORTS, a.seconds, a.log, a.then_check, a.quiet)
    return 2


if __name__ == "__main__":
    sys.exit(main())
