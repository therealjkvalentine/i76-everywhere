#!/usr/bin/env python3
"""soundhd.py - Interstate '76 HD sound pack pipeline (design: docs/SOUND-HD-PACK.md).

    tools\\soundhd\\.venv\\Scripts\\python tools\\soundhd\\soundhd.py build          # extract..check, the whole v1 pack
    soundhd.py extract  [--zfs I76.ZFS] [--work DIR]      stock .wav/.gpw (+ loose music.wav) -> DIR\\stock, md5 manifest
    soundhd.py analyze  [--work DIR] [--compare CSV]      spectral survey -> DIR\\analysis (port of analyze_stock_sounds.py)
    soundhd.py recipe   [--work DIR] [--pack DIR]         per-sound recipe table -> PACK\\recipes\\recipes.json (+ overrides.toml)
    soundhd.py render   [--work DIR] [--pack DIR] [--small-speakers] [--only a,b]   speaker mix -> PACK\\addon\\*.gpw|*.wav
    soundhd.py lfe      [--work DIR] [--pack DIR]         LFE stems, 16 kHz mono -> PACK\\lfe\\*.wav + lfe-manifest.json
    soundhd.py manifest [--work DIR] [--pack DIR]         md5 of every original / replacement / LFE stem -> PACK\\manifest.json
    soundhd.py report   [--work DIR] [--pack DIR]         A/B spectrograms + band energies -> PACK\\report\\index.html
    soundhd.py check    [--work DIR] [--pack DIR]         offline gate -> PACK\\check-results.json (exit 1 on any FAIL)
    soundhd.py install   --game <lab game dir> [--pack DIR] [--apply]   gated ADDON drop-in (default: dry run)
    soundhd.py uninstall --game <lab game dir> [--apply]

Reads stock audio ONLY from the pristine read-only GOG copy (default C:\\Users\\james\\i76-map\\sandbox-gog\\main\\app)
through the repo's ZFS reader re/tools/i76fmt/zfs.py (identical to i76-map\\tools\\i76fmt\\zfs.py; byte-exact
round-trip gate in that package). Nothing but `install` writes outside the work/pack folders, and `install`
only into C:\\Users\\james\\i76-uncap-lab\\game* (sh_install.py).
"""
import argparse, csv, hashlib, io, json, math, os, re, shutil, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "re", "tools"))

import numpy as np  # noqa: E402

import sh_wav  # noqa: E402

PRISTINE = r"C:\Users\james\i76-map\sandbox-gog\main\app"
PRISTINE_ZFS_MD5 = "6dd57b1627d73e814247c0d9521f9778"
DEFAULT_WORK = os.path.join(HERE, "out", "work")
DEFAULT_PACK = os.path.join(HERE, "out", "pack-v1")
PACK_VERSION = "sound-hd v1 (2026-10-10)"
RESEARCH_CSV = r"C:\Users\james\i76-uncap-lab\captures\sound-hd-research\stock-sound-survey.csv"
LFE_RATE = 16000  # tools/ffb/ffb-lfe-live.ps1 streams at 16 kHz
# folders no soundhd stage except `install` may write into
GAME_ROOTS = [r"C:\Users\james\i76-map\sandbox-gog", r"C:\Users\james\i76-uncap-lab\game", r"C:\Users\james\Games"]


def md5b(b):
    return hashlib.md5(b).hexdigest()


def guard_out(path):
    """Refuse an output folder inside any game install, then create it (the stages write only to work/pack)."""
    guard_check(path)
    os.makedirs(path, exist_ok=True)
    return path


def guard_check(path):
    """SystemExit if `path` is inside a game install; creates nothing."""
    real = os.path.normcase(os.path.realpath(path))
    for g in GAME_ROOTS:
        gn = os.path.normcase(os.path.realpath(g))
        if real == gn or real.startswith(gn + os.sep) or (os.path.basename(gn) == "game" and
                                                          os.path.dirname(real) == os.path.dirname(gn) and
                                                          os.path.basename(real).startswith("game")):
            sys.exit("refused: output %s is inside a game folder (%s)" % (path, g))


def jdump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
        fh.write("\n")
    os.replace(tmp, path)


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ============================================================================================== extract
def cmd_extract(a):
    from i76fmt import zfs
    work = guard_out(a.work)
    stock = os.path.join(work, "stock")
    os.makedirs(stock, exist_ok=True)
    with open(a.zfs, "rb") as fh:
        data = fh.read()
    zmd5 = md5b(data)
    if zmd5 != PRISTINE_ZFS_MD5:
        print("WARNING: %s md5 %s is not the pristine archive %s" % (a.zfs, zmd5, PRISTINE_ZFS_MD5))
    z = zfs.parse(data)
    files = []
    for e in z.entries:
        if not e.name.lower().endswith((".wav", ".gpw")) or (e.flags & 1):
            continue
        blob = z.read(e)
        name = e.name.lower()
        with open(os.path.join(stock, name), "wb") as fo:
            fo.write(blob)
        files.append(dict(name=name, source="zfs", bytes=len(blob), md5=md5b(blob), zfs_method=e.method, zfs_id=e.id))
    loose = os.path.join(os.path.dirname(a.zfs), "music.wav")
    if os.path.exists(loose):
        blob = open(loose, "rb").read()
        with open(os.path.join(stock, "music.wav"), "wb") as fo:
            fo.write(blob)
        files.append(dict(name="music.wav", source="loose", bytes=len(blob), md5=md5b(blob)))
    files.sort(key=lambda f: f["name"])
    man = dict(created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), zfs=os.path.abspath(a.zfs), zfs_md5=zmd5,
               zfs_is_pristine=zmd5 == PRISTINE_ZFS_MD5, extractor="re/tools/i76fmt/zfs.py (= i76-map/tools/i76fmt/zfs.py)",
               count=len(files), files=files)
    jdump(man, os.path.join(work, "stock-manifest.json"))
    print("extracted %d sound files (%d from the archive, md5 %s) -> %s" % (
        len(files), sum(f["source"] == "zfs" for f in files), zmd5, stock))


def stock_index(work):
    man = jload(os.path.join(work, "stock-manifest.json"))
    return man, {f["name"]: f for f in man["files"]}


def read_stock(work, name, verify=None):
    blob = open(os.path.join(work, "stock", name), "rb").read()
    if verify and md5b(blob) != verify:
        raise SystemExit("stock file %s changed since extract (md5)" % name)
    return blob


# ============================================================================================== analyze
def categorize(stem):
    """Name -> category; verbatim port of analyze_stock_sounds.py categorize()."""
    s = stem.lower()
    if s == "music":
        return "music_loose"
    if re.match(r"^(\d\d[sa]|s\d[sa]|gds|tms|pos)[a-z0-9]{2,}\d\d$", s):
        return "cb_voice"
    if re.match(r"^g[a-z]{2,6}$", s):
        return "shell_ui"
    if s.startswith("ei") or s in ("aheli", "vballoon", "vufo"):
        return "engine_loop"
    if s.startswith("es"):
        return "engine_start"
    if s.startswith("vhorn") or s == "aps2":
        return "horn_siren"
    if s.startswith("x"):
        return "explosion_impact"
    if s.startswith("w"):
        return "weapon_fire"
    if s.startswith("h"):
        return "handgun"
    if s.startswith("t"):
        return "tyre_surface"
    if s.startswith("vcd") or s.startswith("vc"):
        return "surface_loop"
    if s.startswith("vv") or s.startswith("vn") or s.startswith("vt") or s in ("vland", "vlanding", "vexplode", "vskid", "vshif1a"):
        return "vehicle_collision"
    if s.startswith("c"):
        return "cockpit_ui"
    if s.startswith("m"):
        return "missile_lock"
    if s.startswith("d"):
        return "dropper"
    if s.startswith("f"):
        return "damage"
    if s.startswith("b"):
        return "nitro"
    if s.startswith("a"):
        return "ambient"
    return "other"


NEEDS_LOW_END = {"explosion_impact": 3, "vehicle_collision": 3, "engine_loop": 3, "weapon_fire": 2, "engine_start": 2,
                 "handgun": 2, "nitro": 2, "dropper": 1, "tyre_surface": 1, "surface_loop": 1, "horn_siren": 1,
                 "damage": 1, "ambient": 1, "missile_lock": 0, "cockpit_ui": 0, "shell_ui": 0, "cb_voice": 0,
                 "music_loose": 0, "other": 0}


def survey_metrics(x, rate):
    """Port of analyze_stock_sounds.py analyse(): same Welch parameters, same columns."""
    from scipy import signal
    n = len(x)
    if n < 16:
        return None
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x ** 2)))
    peak = float(np.max(np.abs(x)))
    nper = min(4096, n)
    f, p = signal.welch(x, fs=rate, nperseg=nper, noverlap=nper // 2, window="hann", detrend=False)
    tot = p.sum() + 1e-30
    fb = lambda hz: float(p[f < hz].sum() / tot)  # noqa: E731
    centroid = float((f * p).sum() / tot)
    pdb = 10 * np.log10(p + 1e-30)
    above = np.where(pdb >= pdb.max() - 20.0)[0]
    low_cut = float(f[above[0]]) if len(above) else float("nan")
    cum = np.cumsum(p) / tot
    roll95 = float(f[np.searchsorted(cum, 0.95)])
    win = max(1, int(rate * 0.005))
    env = np.sqrt(np.convolve(x ** 2, np.ones(win) / win, mode="valid"))
    crest = float(env.max() / (rms + 1e-9))
    return dict(rms_dbfs=20 * np.log10(rms + 1e-9), peak_dbfs=20 * np.log10(peak + 1e-9), crest_env=crest,
                centroid_hz=centroid, frac_below_80=fb(80), frac_below_120=fb(120), frac_below_200=fb(200),
                low_cut_m20db_hz=low_cut, rolloff95_hz=roll95)


def cmd_analyze(a):
    work = a.work
    out = guard_out(os.path.join(work, "analysis"))
    man, idx = stock_index(work)
    rows, errors = [], []
    for f in man["files"]:
        name = f["name"]
        stem, ext = os.path.splitext(name)
        blob = read_stock(work, name, f["md5"])
        try:
            d = sh_wav.decode(blob)
        except Exception as e:
            errors.append((name, str(e)))
            continue
        fmt, x, gas = d["fmt"], d["x"], d["gas"]
        m = survey_metrics(x, fmt["rate"])
        if m is None:
            errors.append((name, "too short"))
            continue
        cat = categorize(stem)
        g = gas or {}
        row = dict(name=name, stem=stem, ext=ext[1:], source=f["source"], category=cat, needs_low_end=NEEDS_LOW_END[cat],
                   bytes=len(blob), md5=f["md5"], fmt_tag=fmt["tag"], channels=fmt["channels"], rate_hz=fmt["rate"],
                   bits=fmt["bits"], fmt_chunk_size=fmt["fmt_size"], data_bytes=d["data_bytes"],
                   duration_s=round(len(x) / fmt["rate"], 4), dc_offset=round(float(np.mean(x)), 4),
                   # GAS0 + 6 x i32 (sh_wav docstring). The research CSV's gas_* columns are shifted by one.
                   gas_priority=g.get("priority", ""), gas_max_inst=g.get("max_instances", ""),
                   gas_mode=g.get("play_mode", ""), gas_volume=g.get("volume", ""),
                   gas_randpitch=g.get("random_pitch", ""), gas_freq=g.get("frequency", ""))
        row.update({k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()})
        rows.append(row)
    cols = list(rows[0].keys())
    with open(os.path.join(out, "stock-sound-survey.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    cats = {}
    for r in rows:
        c = cats.setdefault(r["category"], dict(n=0, seconds=0.0, bytes=0))
        c["n"] += 1
        c["seconds"] = round(c["seconds"] + r["duration_s"], 4)
        c["bytes"] += r["bytes"]
    count = lambda k: {str(v): sum(1 for r in rows if r[k] == v) for v in sorted(set(r[k] for r in rows), key=str)}  # noqa: E731
    summary = dict(files=len(rows), errors=errors, rates=count("rate_hz"), bits=count("bits"), channels=count("channels"),
                   gas_mode=count("gas_mode"), categories=cats, total_seconds=round(sum(r["duration_s"] for r in rows), 1))
    jdump(summary, os.path.join(out, "summary.json"))
    print("analyzed %d files, %d errors -> %s" % (len(rows), len(errors), out))
    print("rates", summary["rates"], "bits", summary["bits"], "GAS play_mode", summary["gas_mode"])
    if a.compare:
        compare_survey(os.path.join(out, "stock-sound-survey.csv"), a.compare)


def compare_survey(mine, theirs):
    """Every analysis column must equal the research survey; the GAS columns must equal it shifted by one."""
    load = lambda p: {r["name"]: r for r in csv.DictReader(open(p, encoding="utf-8"))}  # noqa: E731
    A, B = load(mine), load(theirs)
    shift = {"gas_priority": None, "gas_max_inst": "gas_priority", "gas_mode": "gas_max_inst", "gas_volume": "gas_mode",
             "gas_randpitch": "gas_volume", "gas_freq": "gas_randpitch"}
    bad = []
    if set(A) != set(B):
        bad.append("name sets differ: %s" % sorted(set(A) ^ set(B)))
    for n in sorted(set(A) & set(B)):
        a, b = A[n], B[n]
        for k in b:
            if k in shift or k == "source":
                continue
            if a.get(k) != b[k]:
                bad.append("%s %s: %s != %s" % (n, k, a.get(k), b[k]))
        for k, theirs_k in shift.items():
            if theirs_k and a[k] != b[theirs_k]:
                bad.append("%s %s=%s but research %s=%s" % (n, k, a[k], theirs_k, b[theirs_k]))
    print("compare vs %s: %d rows, %d differences" % (theirs, len(B), len(bad)))
    for x in bad[:20]:
        print("  " + x)
    return bad


# ============================================================================================== recipe
CATEGORY_RECIPES = {
    # rate None = keep the stock rate. sub: method none|transient|octave|transient+octave
    "engine_loop": dict(rate=11025, bits=16, clean=["dc", "denoise"], sub=dict(method="octave", level_db=-8.0, band=[30, 90], skip_if_e120=0.5),
                        harmonics_db=-10.0, lfe=True,
                        why="P5 constraint: engine pitch callback 0x424ca0 writes absolute Hz, so the loop stays 11,025 Hz; "
                            "octave-down sub period-matched to the loop"),
    "engine_start": dict(rate=22050, bits=16, clean=["dc", "declick", "denoise"],
                         sub=dict(method="transient+octave", level_db=-6.0, band=[35, 90], tau_s=0.25, sweep_s=0.25, skip_if_e120=0.5),
                         harmonics_db=-8.0, lfe=True, why="sub on the ignition hits + octave-down on the catch (voiced frames only)"),
    "vehicle_collision": dict(rate=22050, bits=16, clean=["declip", "dc", "denoise"],
                              sub=dict(method="transient", level_db=-5.0, band=[30, 90], tau_s=0.30, sweep_s=0.30, skip_if_e120=0.5),
                              harmonics_db=-8.0, lfe=True, why="transient-triggered 90->35 Hz sub drop"),
    "explosion_impact": dict(rate=22050, bits=16, clean=["declip", "dc", "denoise"],
                             sub=dict(method="transient", level_db=-5.0, band=[30, 90], tau_s=0.30, sweep_s=0.30, skip_if_e120=0.5),
                             harmonics_db=-8.0, lfe=True, why="transient-triggered sub drop; bass-heavy stems left alone"),
    "weapon_fire": dict(rate=22050, bits=16, clean=["dc", "declick"],
                        sub=dict(method="transient", level_db=-8.0, band=[40, 90], f_lo=40.0, tau_s=0.12, sweep_s=0.10, skip_if_e120=0.5),
                        harmonics_db=-8.0, lfe=True, why="sub thump per shot; loops processed circularly"),
    "handgun": dict(rate=22050, bits=16, clean=["dc", "declick"],
                    sub=dict(method="transient", level_db=-8.0, band=[40, 90], f_lo=40.0, tau_s=0.12, sweep_s=0.10, skip_if_e120=0.5),
                    harmonics_db=-10.0, lfe=True, why="sub thump per shot"),
    "nitro": dict(rate=22050, bits=16, clean=["dc", "declick"],
                  sub=dict(method="transient", level_db=-8.0, band=[40, 90], f_lo=40.0, tau_s=0.20, sweep_s=0.15, skip_if_e120=0.5),
                  harmonics_db=-10.0, lfe=True, why="sub on the burst onset"),
    "dropper": dict(rate=22050, bits=16, clean=["dc", "declick"],
                    sub=dict(method="transient", level_db=-8.0, band=[40, 90], f_lo=40.0, tau_s=0.12, sweep_s=0.10, skip_if_e120=0.5),
                    harmonics_db=-10.0, lfe=True, why="sub on the drop"),
    "damage": dict(rate=22050, bits=16, clean=["dc", "declick"],
                   sub=dict(method="transient", level_db=-8.0, band=[40, 90], f_lo=40.0, tau_s=0.12, sweep_s=0.10, skip_if_e120=0.5),
                   harmonics_db=-10.0, lfe=True, why="sub on the hit"),
    "tyre_surface": dict(rate=22050, bits=16, clean=["dc", "denoise"], sub=dict(method="none"), harmonics_db=None, lfe=False,
                         why="skids live at 150-400 Hz and the shaker already makes road texture from telemetry: no sub"),
    "surface_loop": dict(rate=22050, bits=16, clean=["dc", "denoise"], sub=dict(method="none"), harmonics_db=None, lfe=False,
                         why="as tyres: clean 16-bit only"),
    "horn_siren": dict(rate=22050, bits=16, clean=["dc"], sub=dict(method="octave", level_db=-12.0, band=[45, 90]),
                       harmonics_db=-10.0, lfe=False, why="light octave-down"),
    "ambient": dict(rate=22050, bits=16, clean=["dc", "denoise"], sub=dict(method="none"), harmonics_db=None, lfe=False,
                    why="not in the design table: clean 16-bit only"),
    "cockpit_ui": dict(rate=None, bits=16, clean=["dc", "declick"], sub=dict(method="none"), harmonics_db=None, lfe=False,
                       why="UI chirps: 16-bit at the stock rate, no bass"),
    "missile_lock": dict(rate=None, bits=16, clean=["dc", "declick"], sub=dict(method="none"), harmonics_db=None, lfe=False,
                         why="lock tones: 16-bit at the stock rate, no bass"),
}
UNTOUCHED = {"cb_voice": "CB/dialogue untouched in v1", "shell_ui": "shell/map UI untouched in v1",
             "music_loose": "loose music.wav untouched (the GOG mp3 soundtrack plays through the music proxy)",
             "other": "unclassified"}


def is_loop(row):
    return row["category"] == "engine_loop" or str(row["gas_mode"]) in ("1", "2")


def deep_merge(base, over):
    out = json.loads(json.dumps(base))
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def cmd_recipe(a):
    import tomllib
    pack = guard_out(a.pack)
    rdir = os.path.join(pack, "recipes")
    os.makedirs(rdir, exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(a.work, "analysis", "stock-sound-survey.csv"), encoding="utf-8")))
    ov_src = os.path.join(HERE, "overrides.toml")
    shutil.copy(ov_src, os.path.join(rdir, "overrides.toml"))
    overrides = tomllib.load(open(ov_src, "rb")).get("sound", {})
    stems = {}
    for r in rows:
        stems.setdefault(r["stem"], []).append(r)
    sounds, untouched = {}, {}
    for stem, rs in sorted(stems.items()):
        r = next((x for x in rs if x["ext"] == "gpw"), rs[0])  # loader prefers <name>.gpw
        shadowed = [x["name"] for x in rs if x is not r]
        cat = r["category"]
        if cat not in CATEGORY_RECIPES:
            untouched[r["name"]] = UNTOUCHED.get(cat, cat)
            continue
        rec = deep_merge(CATEGORY_RECIPES[cat], {})
        rec.update(category=cat, file=r["name"], ext=r["ext"], loop=is_loop(r), stock_rate=int(r["rate_hz"]),
                   gas_mode=r["gas_mode"], stock_e120=float(r["frac_below_120"]), shadowed_twins=shadowed)
        if rec["rate"] is None:
            rec["rate"] = int(r["rate_hz"])
        rec["rate"] = max(rec["rate"], int(r["rate_hz"])) if cat != "engine_loop" else 11025
        skip = rec["sub"].get("skip_if_e120")
        if skip is not None and rec["stock_e120"] >= skip:
            rec["sub"] = dict(method="none", skipped="stock E<120 %.2f >= %.2f (already bass-heavy)" % (rec["stock_e120"], skip))
            rec["harmonics_db"] = None
        if stem in overrides:
            rec = deep_merge(rec, overrides[stem])
            rec["override"] = overrides[stem]
            if rec.get("harmonics_db") is False:
                rec["harmonics_db"] = None
            if rec["sub"].get("method") == "none":
                rec["sub"] = {k: v for k, v in rec["sub"].items() if k in ("method", "skipped")}
        adds = rec["sub"]["method"] != "none"
        # check gate on E20-120 (fraction of energy 20-120 Hz, measured on stock and HD by `check`):
        # bass may not be lost (beyond 0.03) and, where a sub is added, may not be dumped (cap 0.75 or stock + 0.02)
        rec["e20_120_rule"] = dict(min_delta=-0.03, max_abs=0.75 if adds else None, max_delta=0.02 if adds else 0.05)
        rec["id"] = "%s/%s" % (cat, rec["sub"]["method"])
        sounds[stem] = rec
    out = dict(pack_version=PACK_VERSION, created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               global_=dict(loudness="BS.1770-4 integrated, matched to stock within +/-0.5 LU", true_peak_dbtp=-0.3,
                            lfe=dict(rate=LFE_RATE, bits=16, band=[25, 90]), dither="TPDF, seeded by sound name"),
               categories=CATEGORY_RECIPES, untouched=untouched, sounds=sounds)
    out["global"] = out.pop("global_")
    jdump(out, os.path.join(rdir, "recipes.json"))
    by = {}
    for s in sounds.values():
        by[s["id"]] = by.get(s["id"], 0) + 1
    print("recipes: %d sounds to render, %d untouched -> %s" % (len(sounds), len(untouched), rdir))
    for k in sorted(by):
        print("  %-36s %d" % (k, by[k]))


# ============================================================================================== render
def process(dec, rec, small_speakers=False, seed_name=""):
    """Stock decode -> (speaker mix float @ rec.rate, lfe source float @ rec.rate, info)."""
    import sh_dsp as D
    fs0 = dec["fmt"]["rate"]
    loop = bool(rec["loop"])
    x = dec["x"]
    info = dict(loop=loop)
    ref = x - np.mean(x)
    info["stock_lufs"] = D.loudness(ref, fs0)
    info["stock_tp_dbtp"] = D.true_peak_db(ref, loop)
    y = x.copy()
    clean = rec.get("clean", [])
    if "declip" in clean:
        y, info["declip_runs"] = D.declip(y, loop)
    if "dc" in clean:
        y = D.remove_dc(y, fs0, loop)
    if "declick" in clean:
        y, info["declick_samples"] = D.declick(y, loop)
    if "denoise" in clean and dec["fmt"]["bits"] == 8:
        y = D.denoise_quant(y, fs0, loop)
    fs = int(rec["rate"])
    y = D.resample(y, fs0, fs, loop)
    n = len(y)
    sub = np.zeros(n)
    s = rec["sub"]
    m = s.get("method", "none")
    band = tuple(s.get("band", [30, 90]))
    lvl = float(s.get("level_db", -8.0)) - (6.0 if small_speakers else 0.0)
    if "transient" in m:
        ons = D.onsets(y, fs, loop)
        info["onsets"] = len(ons)
        ts = D.transient_sub(n, fs, ons, loop, lvl, f_hi=float(s.get("f_hi", 90.0)), f_lo=float(s.get("f_lo", 35.0)),
                             sweep_s=float(s.get("sweep_s", 0.25)), tau_s=float(s.get("tau_s", 0.25)), band=band)
        ts, gmin = D.duck_sub(ts, y, fs, loop, lvl)
        info["sub_duck_min_db"] = round(D.db(gmin), 1)
        sub += ts
    if "octave" in m:
        so, oi = D.octave_sub(y, fs, loop, lvl, band=band, voiced_only=("transient" in m))
        info["octave"] = oi
        sub += so
    low = D.filt(D.sos_band(fs, 30.0, 90.0), y, loop, fs) + sub
    harm = np.zeros(n)
    hdb = rec.get("harmonics_db")
    if hdb is not None and D.rms(low) > 1e-6:
        harm = D.harmonics(low, fs, loop, float(hdb) + (4.0 if small_speakers else 0.0))
    mix = y + sub + harm
    info["sub_rms_dbfs"] = round(D.db(D.rms(sub)), 2) if m != "none" else None
    info["harm_rms_dbfs"] = round(D.db(D.rms(harm)), 2) if hdb is not None else None
    # loudness match (gain), then true-peak limit (sh_dsp.match_and_limit picks limiter or soft clip + limiter)
    out, g, li = D.match_and_limit(mix, fs, loop, info["stock_lufs"])
    info.update(li)
    info["gain_db"] = round(D.db(g), 2)
    if not np.all(np.isfinite(out)):
        raise ValueError("non-finite samples in the render")
    info["new_lufs"] = D.loudness(out, fs)
    info["new_tp_dbtp"] = D.true_peak_db(out, loop)
    lfe_src = D.filt(D.sos_band(fs, 25.0, 90.0), y + sub, loop, fs) * g
    return out, lfe_src, info


def cmd_render(a):
    pack = guard_out(a.pack)
    addon = os.path.join(pack, "addon")
    os.makedirs(addon, exist_ok=True)
    cache = os.path.join(a.work, "lfe-src")
    os.makedirs(cache, exist_ok=True)
    recipes = jload(os.path.join(pack, "recipes", "recipes.json"))
    _, idx = stock_index(a.work)
    only = set(a.only.split(",")) if a.only else None
    info_path = os.path.join(pack, "render-info.json")
    allinfo = jload(info_path) if (only and os.path.exists(info_path)) else {}
    t0 = time.time()
    for stem, rec in recipes["sounds"].items():
        if only and stem not in only:
            continue
        name = rec["file"]
        blob = read_stock(a.work, name, idx[name]["md5"])
        dec = sh_wav.decode(blob)
        out, lfe_src, info = process(dec, rec, small_speakers=a.small_speakers, seed_name=stem)
        seed = int(md5b(stem.encode())[:8], 16)
        riff = sh_wav.build_riff(sh_wav.to_pcm16(out, seed), int(rec["rate"]), 16, 1)
        payload = sh_wav.build_gpw(dec["gas_header"], riff) if rec["ext"] == "gpw" else riff
        with open(os.path.join(addon, name), "wb") as fo:
            fo.write(payload)
        np.save(os.path.join(cache, stem + ".npy"), lfe_src.astype(np.float32))
        info.update(file=name, rate=int(rec["rate"]), bytes=len(payload), stock_bytes=len(blob), small_speakers=bool(a.small_speakers))
        allinfo[stem] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in info.items()}
        print("%-10s %-18s %5d Hz  %6.2f -> %6.2f LUFS  TP %5.2f  gain %+5.1f dB" % (
            stem, rec["id"], rec["rate"], info["stock_lufs"], info["new_lufs"], info["new_tp_dbtp"], info["gain_db"]))
    if not only:
        keep = {r["file"] for r in recipes["sounds"].values()}
        for fn in os.listdir(addon):
            if fn not in keep:
                os.remove(os.path.join(addon, fn))  # stale render from an earlier recipe set
    jdump(allinfo, info_path)
    print("rendered %d sounds in %.0f s -> %s" % (len(allinfo), time.time() - t0, addon))


# ============================================================================================== lfe
def cmd_lfe(a):
    import sh_dsp as D
    pack = guard_out(a.pack)
    ldir = os.path.join(pack, "lfe")
    os.makedirs(ldir, exist_ok=True)
    recipes = jload(os.path.join(pack, "recipes", "recipes.json"))
    entries = {}
    for stem, rec in recipes["sounds"].items():
        if not rec.get("lfe"):
            continue
        p = os.path.join(a.work, "lfe-src", stem + ".npy")
        if not os.path.exists(p):
            sys.exit("no LFE source for %s: run render first" % stem)
        x = np.load(p).astype(np.float64)
        fs, loop = int(rec["rate"]), bool(rec["loop"])
        y = D.resample(x, fs, LFE_RATE, loop)
        # sample-peak ceiling -1 dBFS; levels stay comparable across sounds (no per-file normalisation)
        y = D.limit(y, LFE_RATE, loop, ceiling_db=-1.0)
        pcm = sh_wav.to_pcm16(y, int(md5b(("lfe" + stem).encode())[:8], 16))
        riff = sh_wav.build_riff(pcm, LFE_RATE, 16, 1)
        fn = stem + ".wav"
        with open(os.path.join(ldir, fn), "wb") as fo:
            fo.write(riff)
        entries[stem] = dict(file=fn, md5=md5b(riff), rate=LFE_RATE, bits=16, channels=1, samples=len(y),
                             duration_s=round(len(y) / LFE_RATE, 4), loop=loop, category=rec["category"],
                             peak_dbfs=round(D.db(np.max(np.abs(y)) if len(y) else 0), 2), rms_dbfs=round(D.db(D.rms(y)), 2),
                             aliases=[stem, rec["file"]] + rec.get("shadowed_twins", []), suggested_gain=1.0)
    for fn in os.listdir(ldir):
        if fn.endswith(".wav") and fn[:-4] not in entries:
            os.remove(os.path.join(ldir, fn))  # stale stem from an earlier recipe set
    man = dict(pack_version=PACK_VERSION, purpose="LFE stems for the haptics host: look up the sound name of a SOUND_START event "
               "(lowercase, with or without extension) in `aliases`, play `file` to the shaker bus; loop while the voice "
               "lives when `loop` is true. Band 25-90 Hz, 16 kHz mono 16-bit, levels comparable across sounds.",
               key="lowercase stem", rate=LFE_RATE, count=len(entries), sounds=entries)
    man["by_alias"] = {al.lower(): stem for stem, e in entries.items() for al in e["aliases"]}
    jdump(man, os.path.join(ldir, "lfe-manifest.json"))
    print("LFE stems: %d -> %s" % (len(entries), ldir))


# ============================================================================================== manifest
def md5_path(p):
    return md5b(open(p, "rb").read()) if os.path.exists(p) else None


def cmd_manifest(a):
    pack = a.pack
    smani, idx = stock_index(a.work)
    recipes = jload(os.path.join(pack, "recipes", "recipes.json"))
    rinfo = jload(os.path.join(pack, "render-info.json"))
    lman = jload(os.path.join(pack, "lfe", "lfe-manifest.json")) if os.path.exists(os.path.join(pack, "lfe", "lfe-manifest.json")) else {"sounds": {}}
    sounds = []
    for stem, rec in recipes["sounds"].items():
        name = rec["file"]
        st = idx[name]
        rp = os.path.join(pack, "addon", name)
        ri = rinfo.get(stem, {})
        le = lman["sounds"].get(stem)
        sounds.append(dict(
            name=stem, category=rec["category"], recipe_id=rec["id"], loop=rec["loop"],
            original=dict(file=name, md5=st["md5"], bytes=st["bytes"], rate=rec["stock_rate"], bits=8),
            replacement=dict(file=name, md5=md5_path(rp), bytes=os.path.getsize(rp) if os.path.exists(rp) else None,
                             rate=rec["rate"], bits=16) if os.path.exists(rp) else None,
            lfe=dict(file=le["file"], md5=md5_path(os.path.join(pack, "lfe", le["file"]))) if le else None,
            loudness=dict(stock_lufs=ri.get("stock_lufs"), new_lufs=ri.get("new_lufs"), new_tp_dbtp=ri.get("new_tp_dbtp"),
                          gain_db=ri.get("gain_db")),
            recipe=dict(clean=rec["clean"], sub=rec["sub"], harmonics_db=rec["harmonics_db"]),
            shadowed_twins=rec.get("shadowed_twins", []), rx_pass=False))
    untouched = [dict(file=n, md5=idx[n]["md5"], reason=why) for n, why in sorted(recipes["untouched"].items())]
    man = dict(pack_version=PACK_VERSION, created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               source=dict(zfs=smani["zfs"], zfs_md5=smani["zfs_md5"], pristine=smani["zfs_is_pristine"],
                           extractor=smani["extractor"]),
               engine_pitch_patch_p5=False, rx_pass=None,
               totals=dict(rendered=sum(1 for s in sounds if s["replacement"]), lfe=sum(1 for s in sounds if s["lfe"]),
                           untouched=len(untouched),
                           addon_bytes=sum(s["replacement"]["bytes"] for s in sounds if s["replacement"]),
                           stock_bytes_replaced=sum(s["original"]["bytes"] for s in sounds if s["replacement"])),
               sounds=sounds, untouched=untouched)
    jdump(man, os.path.join(pack, "manifest.json"))
    print("manifest: %d replacements (%d bytes vs %d stock), %d LFE stems, %d untouched" % (
        man["totals"]["rendered"], man["totals"]["addon_bytes"], man["totals"]["stock_bytes_replaced"], man["totals"]["lfe"],
        len(untouched)))


# ============================================================================================== check
def cmd_check(a):
    import sh_dsp as D
    pack = a.pack
    man = jload(os.path.join(pack, "manifest.json"))
    recipes = jload(os.path.join(pack, "recipes", "recipes.json"))
    smani, idx = stock_index(a.work)
    lman_p = os.path.join(pack, "lfe", "lfe-manifest.json")
    lman = jload(lman_p) if os.path.exists(lman_p) else {"sounds": {}}
    results, totals = [], {}
    fails = 0
    src_ok = smani["zfs_md5"] == PRISTINE_ZFS_MD5
    for s in man["sounds"]:
        stem = s["name"]
        rec = recipes["sounds"][stem]
        res = dict(name=stem, category=s["category"], checks={})
        c = res["checks"]

        def put(k, ok, detail=""):
            c[k] = dict(ok=bool(ok), detail=detail)
        name = s["original"]["file"]
        sblob = read_stock(a.work, name)
        put("original_md5", md5b(sblob) == s["original"]["md5"] == idx[name]["md5"] and src_ok,
            "stock payload md5 vs manifest and pristine archive %s" % smani["zfs_md5"])
        rp = os.path.join(pack, "addon", s["replacement"]["file"])
        blob = open(rp, "rb").read()
        put("replacement_md5", md5b(blob) == s["replacement"]["md5"])
        try:
            dec = sh_wav.decode(blob)
            put("decodable", True)
        except Exception as e:
            put("decodable", False, str(e))
            results.append(res)
            continue
        sdec = sh_wav.decode(sblob)
        fmt, ch = dec["fmt"], [k for k, _, _ in dec["chunks"]]
        put("riff_chunks_fmt_then_data", ch == ["fmt ", "data"], str(ch))
        put("fmt_ge_14_bytes", fmt["fmt_size"] >= 14 and fmt["fmt_size"] == 16 and fmt["tag"] == 1, "fmt %d bytes tag %d" % (fmt["fmt_size"], fmt["tag"]))
        put("mono", fmt["channels"] == 1)
        put("bits16", fmt["bits"] == 16)
        if s["category"] == "engine_loop" and not man.get("engine_pitch_patch_p5"):
            put("rate_rule", fmt["rate"] == 11025, "engine loop at %d (must be 11025 until P5)" % fmt["rate"])
        else:
            put("rate_rule", fmt["rate"] == rec["rate"] and fmt["rate"] in (11025, 22050, 44100), "%d Hz" % fmt["rate"])
        if rec["ext"] == "gpw":
            hdr_ok = dec["gas_header"] is not None and sdec["gas_header"] == dec["gas_header"]
            put("gpw_header_equals_stock", hdr_ok, json.dumps(dec["gas"]))
        else:
            put("plain_wav", dec["gas_header"] is None)
        x, fs = dec["x"], fmt["rate"]
        sx = sdec["x"] - np.mean(sdec["x"])
        loop = bool(rec["loop"])
        Ls, Ln = D.loudness(sx, sdec["fmt"]["rate"]), D.loudness(x, fs)
        dl = Ln - Ls if math.isfinite(Ls) and math.isfinite(Ln) else 0.0
        put("loudness_delta_le_0.5LU", abs(dl) <= 0.5, "stock %.2f new %.2f delta %+.2f LU" % (Ls, Ln, dl))
        tp = D.true_peak_db(x, loop)
        put("true_peak_le_-0.3dBTP", tp <= -0.3 + 0.05, "%.2f dBTP" % tp)  # 0.05 dB: 16-bit dither/rounding
        e_new, e_old = D.frac_band(x, fs, 20, 120), D.frac_band(sx, sdec["fmt"]["rate"], 20, 120)
        ru = rec["e20_120_rule"]
        lo = max(0.0, e_old + ru["min_delta"])
        hi = max(e_old + ru["max_delta"], ru["max_abs"]) if ru["max_abs"] is not None else e_old + ru["max_delta"]
        put("e20_120_in_target", lo <= e_new <= hi, "E20-120 %.3f -> %.3f (target %.3f..%.3f)" % (e_old, e_new, lo, hi))
        ratio = len(blob) / len(sblob)
        put("size_le_8x", ratio <= 8.0, "%d B = %.2fx stock" % (len(blob), ratio))
        if loop:
            sr_new, sr_old = D.seam_ratio(x), D.seam_ratio(sx)
            put("loop_seam", sr_new <= max(1.0, sr_old * 1.25 + 0.1),
                "seam jump %.2f x p99 step (stock %.2f)" % (sr_new, sr_old))
            oc = (jload(os.path.join(pack, "render-info.json")).get(stem, {}).get("octave") or {})
            if "octave" in rec["sub"].get("method", ""):
                put("sub_integer_cycles", isinstance(oc.get("sub_cycles"), int) and oc["sub_cycles"] >= 1,
                    "sub completes %s cycles over the loop" % oc.get("sub_cycles"))
        le = lman["sounds"].get(stem)
        if rec.get("lfe"):
            ok, det = False, "missing"
            if le:
                lb = open(os.path.join(pack, "lfe", le["file"]), "rb").read()
                try:
                    ld = sh_wav.decode(lb)
                    lf = ld["fmt"]
                    ok = (lf["rate"] == LFE_RATE and lf["channels"] == 1 and lf["bits"] == 16 and md5b(lb) == le["md5"]
                          == (s["lfe"] or {}).get("md5") and [k for k, _, _ in ld["chunks"]] == ["fmt ", "data"])
                    det = "%d Hz %d ch %d bit, peak %.1f dBFS" % (lf["rate"], lf["channels"], lf["bits"], D.db(np.max(np.abs(ld["x"])) + 1e-12))
                    if loop and ok:
                        lsr = D.seam_ratio(ld["x"])
                        ok = lsr <= 1.5
                        det += ", seam %.2f" % lsr
                except Exception as e:
                    det = str(e)
            put("lfe_stem", ok, det)
        res["ok"] = all(v["ok"] for v in c.values())
        fails += 0 if res["ok"] else 1
        for k, v in c.items():
            t = totals.setdefault(k, [0, 0])
            t[0 if v["ok"] else 1] += 1
        results.append(res)
    total_bytes = man["totals"]["addon_bytes"]
    summary = dict(pack_version=man["pack_version"], checked=len(results), passed=len(results) - fails, failed=fails,
                   per_check={k: dict(pass_=v[0], fail=v[1]) for k, v in sorted(totals.items())},
                   addon_bytes=total_bytes, budget_note="design 1.3: ~14 MB if every effect is 22,050/16",
                   untouched=len(man["untouched"]))
    jdump(dict(summary=summary, results=results), os.path.join(pack, "check-results.json"))
    print("check: %d sounds, %d pass, %d FAIL; addon %.2f MB" % (len(results), len(results) - fails, fails, total_bytes / 1e6))
    for k, v in sorted(totals.items()):
        print("  %-28s pass %3d  fail %3d" % (k, v[0], v[1]))
    for r in results:
        if not r.get("ok", False):
            bad = {k: v["detail"] for k, v in r["checks"].items() if not v["ok"]}
            print("  FAIL %-10s %s" % (r["name"], bad))
    return 1 if fails else 0


# ============================================================================================== report
def cmd_report(a):
    import sh_report
    sh_report.build(a.work, a.pack, stock_index, read_stock)


# ============================================================================================== install
def cmd_install(a):
    import sh_install
    try:
        sh_install.install(a.pack, a.game, apply=a.apply)
    except sh_install.InstallRefused as e:
        sys.exit(str(e))


def cmd_uninstall(a):
    import sh_install
    try:
        sh_install.uninstall(a.game, apply=a.apply)
    except sh_install.InstallRefused as e:
        sys.exit(str(e))


def cmd_build(a):
    if not os.path.exists(os.path.join(a.work, "stock-manifest.json")) or a.fresh:
        cmd_extract(a)
    a.compare = RESEARCH_CSV if os.path.exists(RESEARCH_CSV) else None
    cmd_analyze(a)
    cmd_recipe(a)
    a.only = None
    cmd_render(a)
    cmd_lfe(a)
    cmd_manifest(a)
    cmd_report(a)
    return cmd_check(a)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **kw):
        q = sp.add_parser(name)
        q.set_defaults(fn=fn)
        q.add_argument("--work", default=DEFAULT_WORK)
        q.add_argument("--pack", default=DEFAULT_PACK)
        q.add_argument("--zfs", default=os.path.join(PRISTINE, "I76.ZFS"))
        return q
    add("extract", cmd_extract)
    add("analyze", cmd_analyze).add_argument("--compare", help="research survey CSV to compare against")
    add("recipe", cmd_recipe)
    q = add("render", cmd_render)
    q.add_argument("--small-speakers", action="store_true", help="harmonics +4 dB, true sub -6 dB")
    q.add_argument("--only", help="comma-separated stems")
    add("lfe", cmd_lfe)
    add("manifest", cmd_manifest)
    add("report", cmd_report)
    add("check", cmd_check)
    for nm, fn in (("install", cmd_install), ("uninstall", cmd_uninstall)):
        q = add(nm, fn)
        q.add_argument("--game", required=True)
        q.add_argument("--apply", action="store_true", help="really write (default: dry run)")
    q = add("build", cmd_build)
    q.add_argument("--fresh", action="store_true", help="re-extract")
    q.add_argument("--small-speakers", action="store_true")
    a = p.parse_args(argv)
    rc = a.fn(a)
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
