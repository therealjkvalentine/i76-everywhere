#!/usr/bin/env python3
"""report.py - the design facility's three-way view, one static HTML page (HAPTICS-ARCHITECTURE 2.2 / 4.3).

For every effect file it shows, side by side:
  1. the STOCK FFB behaviour for that event (stock/stock-ffb-reference.json: what i7_sfrce.dll did, .frc composition);
  2. the SOUND the engine plays for it (design/out/analysis/<sound>.json + spectrogram, from gpw_spectra.py);
  3. the SUGGESTED mapping from that sound vs the CURRENT effect file, with the deltas called out;
  4. the CURRENT effect rendered through the real host for all three devices (i76haptics preview: wheel force,
     pad L/R, shaker WAV - files only, nothing is played).

  python design/report.py                    # runs gpw_spectra / stock_reference first if their output is missing
  python design/report.py --only impact.collision,weapon.fire
Output: design/out/report/index.html (+ PNGs, render/), gitignored: it is derived from the owner's game files.
"""
import argparse, html, json, os, shutil, subprocess, sys

import numpy as np

from common import OUT, ROOT, bar_png, line_plot_png, read_wav, spectrogram_png, write_json

REPORT = os.path.join(OUT, "report")
ANALYSIS = os.path.join(OUT, "analysis")
HOST = os.path.join(ROOT, "src", "Host", "bin", "Release", "net8.0", "i76haptics.exe")
BANDS = [(20, 40), (40, 80), (80, 160), (160, 320)]


def host_exe():
    if not os.path.exists(HOST):
        subprocess.run(["dotnet", "build", os.path.join(ROOT, "src", "Host", "Host.csproj"), "-c", "Release", "--nologo", "-v", "q"], check=True)
    return HOST


def ensure_inputs():
    if not os.path.exists(os.path.join(ANALYSIS, "index.json")):
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "gpw_spectra.py")], check=True)
    if not os.path.exists(os.path.join(ROOT, "stock", "stock-ffb-reference.json")):
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "stock_reference.py")], check=True)


def load_effects():
    eff = {}
    for fn in sorted(os.listdir(os.path.join(ROOT, "effects"))):
        if fn.endswith(".json"):
            eff[fn[:-5]] = json.load(open(os.path.join(ROOT, "effects", fn), encoding="utf-8"))
    return eff


def band_db(x, rate):
    n = 1 << int(np.ceil(np.log2(max(len(x), 2))))
    s = np.abs(np.fft.rfft(x, n)) ** 2
    f = np.fft.rfftfreq(n, 1.0 / rate)
    return [10 * np.log10(s[(f >= lo) & (f < hi)].sum() + 1e-12) for lo, hi in BANDS]


def render(eid, outdir):
    """Run the host's preview for one effect; returns paths of the three files (or an error string)."""
    os.makedirs(outdir, exist_ok=True)
    r = subprocess.run([host_exe(), "preview", "--effect", eid, "--out", outdir, "--sinks", "wheel-file,pad-file,lfe-wav"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stdout + r.stderr).strip()
    return {k: os.path.join(outdir, eid + ext) for k, ext in (("wheel", ".wheel.csv"), ("pad", ".pad.csv"), ("lfe", ".lfe.wav"))}, r.stdout.strip()


def csv_cols(path):
    lines = open(path).read().strip().splitlines()
    head = lines[0].split(",")
    rows = [l.split(",") for l in lines[1:]]
    return {h: np.array([float(r[i]) if r[i] not in ("", "max", "sum") else 0.0 for r in rows]) for i, h in enumerate(head) if h != "mode"}


def current_lfe_hz(e):
    lf = (e.get("routing") or {}).get("lfe") or {}
    if "hz" in lf:
        return lf["hz"]
    if "hz_lo" in lf:
        return "%s-%s" % (lf["hz_lo"], lf["hz_hi"])
    c = e.get("carrier") or {}
    return c.get("base_hz")


def current_pad_motors(e):
    taps = (e.get("routing") or {}).get("pad") or []
    return "".join(sorted(set(t.get("motor", "?") for t in taps if t.get("gain", 0) > 0))) or "-"


def esc(x):
    return html.escape(str(x))


def section(eid, e, stock, analyses, rel):
    out = ['<section id="%s"><h2>%s <small>%s / %s%s</small></h2>' % (esc(eid), esc(eid), esc(e.get("kind")), esc(e.get("model")),
                                                                         "" if e.get("enabled", True) else " / DISABLED")]
    ref = e.get("reference") or {}
    out.append('<div class="grid">')
    # 1 stock
    sid = (ref.get("stock") or "").split("#")[-1] if ref.get("stock") else None
    st = stock.get("events", {}).get(sid) if sid else None
    out.append('<div class="box"><h3>1. Stock FFB (i7_sfrce.dll)</h3>')
    if st:
        out.append('<table>' + "".join("<tr><th>%s</th><td>%s</td></tr>" % (esc(k), esc(v)) for k, v in st.items() if k != "frc") + "</table>")
    else:
        out.append("<p class=dim>no stock effect for this event%s</p>" % (" (" + esc(sid) + " not in the reference)" if sid else ""))
    out.append("</div>")
    # 2 sounds
    out.append('<div class="box"><h3>2. Stock sound(s)</h3>')
    sounds = ref.get("sounds") or []
    shown = 0
    for snd in sounds:
        a = analyses.get(snd)
        if not a or shown >= 3:
            continue
        shown += 1
        bars = os.path.join(REPORT, "img", snd + ".bands.png")
        bar_png(bars, [(k, v) for k, v in a["bands"].items()])
        out.append("<h4>%s <small>%.2f s, %d-bit %d Hz, %s</small></h4>" % (esc(snd), a["duration_s"], a["bits"], a["rate"],
                   {0: "one-shot", 1: "loop", 2: "sustained loop"}.get(a.get("gas", {}).get("mode"), "mode default")))
        out.append('<img src="%s" title="spectrogram 0-400 Hz, guides at 20/40/80/160/320"> <img src="img/%s.bands.png" title="band energy: %s">' %
                   (esc(rel(os.path.join(ANALYSIS, snd + ".png"))), esc(snd), esc(", ".join(a["bands"].keys()))))
        out.append("<p>in-band peak <b>%s Hz</b>, shaker-band energy %.1f%%, centroid %.0f Hz, onset %d ms, emphasis %s</p>" % (
            a["peak_hz_in_band"], 100 * a["shaker_band_fraction"], a["centroid_mean_hz"], a["onset_ms"], esc(a["emphasis_ms"][:6])))
    if shown == 0:
        out.append("<p class=dim>no sound referenced%s</p>" % (" (" + esc(", ".join(sounds)) + " not analysed)" if sounds else ""))
    out.append("</div>")
    # 3 suggestion vs current
    out.append('<div class="box"><h3>3. Suggested (from the sound) vs current effect</h3>')
    a0 = next((analyses[s] for s in sounds if s in analyses), None)
    if a0:
        sg = a0["suggested"]
        rows = [("shaker carrier Hz", sg["lfe"]["hz"], current_lfe_hz(e)), ("shaker amp", sg["lfe"]["amp"], ((e.get("routing") or {}).get("lfe") or {}).get("amp")),
                ("pad motor", sg["pad"]["motor"] + " (" + sg["pad"]["why"] + ")", current_pad_motors(e)),
                ("envelope a/h/d ms", "%d / %d / %d" % (sg["pad"]["attack_ms"], sg["pad"]["hold_ms"], sg["pad"]["decay_ms"]),
                 "%s / %s / %s" % tuple((e.get("envelope") or {}).get(k, "-") for k in ("attack_ms", "hold_ms", "decay_ms"))),
                ("kind", sg["kind"], e.get("kind")), ("wheel", "%s %.2f" % (sg["wheel"]["shape"], sg["wheel"]["transient_amp"]),
                 ((e.get("routing") or {}).get("wheel") or {}).get("shape", "-"))]
        out.append("<table><tr><th></th><th>suggested</th><th>current</th></tr>" + "".join(
            "<tr><th>%s</th><td>%s</td><td>%s</td></tr>" % (esc(n), esc(s), esc(c)) for n, s, c in rows) + "</table>")
        out.append("<p class=dim>%s</p>" % esc(a0["caveats"]))
    else:
        out.append("<p class=dim>no analysed sound: nothing to suggest from</p>")
    out.append("<details><summary>current effect file</summary><pre>%s</pre></details></div>" % esc(json.dumps(e, indent=1)))
    # 4 rendered
    out.append('<div class="box"><h3>4. Current effect rendered alone (host preview)</h3>')
    if e.get("kind") in ("global",) or e.get("model") == "legacy.unused":
        out.append("<p class=dim>nothing to render</p>")
    else:
        files, log = render(eid, os.path.join(REPORT, "render", eid))
        if not files:
            out.append("<pre>%s</pre>" % esc(log))
        else:
            w = csv_cols(files["wheel"]); p = csv_cols(files["pad"]); rate, lfe = read_wav(files["lfe"])
            img = os.path.join(REPORT, "img", eid)
            line_plot_png(img + ".wheel.png", [(w["t"], w["device_force"])], ylim=(-10000, 10000))
            line_plot_png(img + ".pad.png", [(p["t"], p["L"]), (p["t"], p["R"])], ylim=(0, 1))
            t = np.arange(len(lfe)) / rate
            line_plot_png(img + ".lfe.png", [(t, lfe)], ylim=(-1, 1))
            spectrogram_png(img + ".lfe.spec.png", lfe, rate, fmax=160, height=100, win=2048)
            bd = band_db(lfe, rate)
            out.append("<p><b>wheel</b> device force (+-10000), peak %d</p><img src='img/%s.wheel.png'>" % (int(np.abs(w["device_force"]).max()), esc(eid)))
            out.append("<p><b>pad</b> L (blue) / R (red), 0..1 after the dead-zone lift, peak L %.2f R %.2f</p><img src='img/%s.pad.png'>" % (p["L"].max(), p["R"].max(), esc(eid)))
            out.append("<p><b>shaker</b> WAV 16 kHz, peak %.2f; bands 20-40/40-80/80-160/160-320 Hz: %s dB</p><img src='img/%s.lfe.png'> <img src='img/%s.lfe.spec.png' title='0-160 Hz'>" % (
                np.abs(lfe).max(), " / ".join("%.0f" % v for v in bd), esc(eid), esc(eid)))
    out.append("</div></div></section>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    ensure_inputs()
    effects = load_effects()
    stock = json.load(open(os.path.join(ROOT, "stock", "stock-ffb-reference.json"), encoding="utf-8"))
    analyses = {}
    for fn in os.listdir(ANALYSIS):
        if fn.endswith(".json") and fn != "index.json" and not fn.endswith(".wav.json"):
            analyses[fn[:-5]] = json.load(open(os.path.join(ANALYSIS, fn), encoding="utf-8"))
    os.makedirs(os.path.join(REPORT, "img"), exist_ok=True)
    rel = lambda p: os.path.relpath(p, REPORT).replace("\\", "/")
    order = ["impact.collision", "weapon.fire", "engine.vibration", "slip.scrub"]
    ids = [i for i in order if i in effects] + [i for i in effects if i not in order]
    if a.only:
        ids = [i for i in ids if i in a.only.split(",")]
    body = [section(i, effects[i], stock, analyses, rel) for i in ids]
    toc = " &middot; ".join('<a href="#%s">%s</a>' % (esc(i), esc(i)) for i in ids)
    page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Haptics design report</title><style>
:root{--bg:#fafafa;--fg:#222;--dim:#777;--box:#fff;--line:#ddd}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#16181c;--fg:#e6e6e6;--dim:#999;--box:#1f2228;--line:#333}}
body{background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;margin:0 16px 40px}
h1{margin:16px 0 4px} section{border-top:2px solid var(--line);margin-top:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}
.box{background:var(--box);border:1px solid var(--line);border-radius:6px;padding:8px 12px;overflow-x:auto}
img{max-width:100%%;image-rendering:pixelated;border:1px solid var(--line)} table{border-collapse:collapse} th,td{text-align:left;padding:2px 8px 2px 0;vertical-align:top}
.dim,small{color:var(--dim)} pre{white-space:pre-wrap;font-size:12px}
</style></head><body><h1>Haptics design report</h1>
<p class=dim>Generated by tools/haptics/design/report.py from the pristine install's sounds and .frc files, stock/stock-ffb-reference.json,
effects/*.json and the host's preview renders. Suggestions are never applied automatically. %d effects, %d analysed sounds.</p>
<p>%s</p>%s</body></html>""" % (len(ids), len(analyses), toc, "\n".join(body))
    path = os.path.join(REPORT, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
