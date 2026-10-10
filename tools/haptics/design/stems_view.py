#!/usr/bin/env python3
"""stems_view.py - design facility view: each HD sound pack LFE stem next to what Lfe.Synth makes for the same event.

For every stem in tools/soundhd/out/pack-v1/lfe/lfe-manifest.json, one row:
  1. the STEM file itself (16 kHz mono, 25-90 Hz): spectrum, waveform;
  2. the stem THROUGH THE HOST as the shaker gets it with stems only (`i76haptics stems render --name <stem> --player`,
     I76_LFE_SOURCES=synth=0,stems=1: Lfe.Stems -> Lfe.Synth's HP/LP, drive, limiter, master);
  3. LFE.SYNTH for the same event with synth only (`i76haptics preview --effect <id>`, I76_LFE_SOURCES=synth=1,stems=0),
     where <id> is the effect whose reference.sounds lists the stem, else the effect for the stem's category
     (engine_loop -> engine.vibration, vehicle_collision -> impact.event, weapon_fire -> weapon.fire, ...). Stems with no
     matching effect say so: Lfe.Synth is silent for that event, the stem is the only shaker content it will ever have.
  One overlay plot per stem: spectrum in dB over 10-160 Hz (log axis), blue = stem through the host, red = Lfe.Synth,
  plus band energies (20-40 / 40-80 / 80-160 Hz) and the spectral peak of each.

  python design/stems_view.py                    # all stems (about 90 host runs, files only, nothing is played)
  python design/stems_view.py --only whcan,eisv,vexplode
Output: design/out/stems/index.html (+ PNGs, WAVs), gitignored: derived from the owner's game files via the pack.
"""
import argparse, html, json, os, subprocess, sys

import numpy as np

from common import OUT, ROOT, line_plot_png, read_wav, spectrogram_png

VIEW = os.path.join(OUT, "stems")
HOST = os.path.join(ROOT, "src", "Host", "bin", "Release", "net8.0", "i76haptics.exe")
MANIFEST = os.path.normpath(os.path.join(ROOT, "..", "soundhd", "out", "pack-v1", "lfe", "lfe-manifest.json"))
BANDS = [(20, 40), (40, 80), (80, 160)]
F_LO, F_HI = 10.0, 160.0
EVENT_AT = 0.5          # both host renders put their event at 0.5 s
WINDOW_S = 2.0          # spectrum over [event, event + 2 s)
CATEGORY_EFFECT = {
    "engine_loop": "engine.vibration", "engine_start": "engine.start", "vehicle_collision": "impact.event",
    "explosion_impact": "explosion.blast", "weapon_fire": "weapon.fire", "handgun": "weapon.fire", "damage": "damage.side",
}


def host_exe():
    if not os.path.exists(HOST):
        subprocess.run(["dotnet", "build", os.path.join(ROOT, "src", "Host", "Host.csproj"), "-c", "Release", "--nologo", "-v", "q"], check=True)
    return HOST


def load_effects():
    eff = {}
    for fn in sorted(os.listdir(os.path.join(ROOT, "effects"))):
        if fn.endswith(".json"):
            eff[fn[:-5]] = json.load(open(os.path.join(ROOT, "effects", fn), encoding="utf-8"))
    return eff


def effect_for(stem, category, effects):
    """(effect id, why) for the event that plays this sound, or (None, why)."""
    named = [eid for eid, e in effects.items() if stem in ((e.get("reference") or {}).get("sounds") or []) and e.get("enabled", True)]
    if named:
        # the stem is rendered as the player's own sound, so an effect gated to AI sounds (where.is_player 0) comes last;
        # then an effect with its own preview stimulus (it is the event itself), then legacy channels
        def ai_only(eid):
            return ((effects[eid].get("source") or {}).get("where") or {}).get("is_player") == 0
        named.sort(key=lambda eid: (1 if ai_only(eid) else 0, 0 if effects[eid].get("preview") else 1, eid))
        return named[0], "reference.sounds of " + named[0]
    eid = CATEGORY_EFFECT.get(category)
    if eid and eid in effects:
        return eid, "category " + category
    return None, "no effect plays on this sound's event (category %s)" % (category or "?")


def spectrum_db(x, rate, lo=F_LO, hi=F_HI):
    """Amplitude spectrum (Hann, zero-padded) in dBFS - a steady full-scale sine reads 0 dB - over lo..hi Hz."""
    x = np.asarray(x, float)
    if len(x) < 16:
        x = np.pad(x, (0, 16 - len(x)))
    w = np.hanning(len(x))
    n = 1 << int(np.ceil(np.log2(max(len(x), 1 << 15))))
    a = 2 * np.abs(np.fft.rfft(x * w, n)) / max(w.sum(), 1e-9)
    f = np.fft.rfftfreq(n, 1.0 / rate)
    keep = (f >= lo) & (f <= hi)
    return f[keep], 20 * np.log10(a[keep] + 1e-9)


def band_db(x, rate):
    x = np.asarray(x, float)
    n = 1 << int(np.ceil(np.log2(max(len(x), 2))))
    s = np.abs(np.fft.rfft(x, n)) ** 2 / max(1, len(x))
    f = np.fft.rfftfreq(n, 1.0 / rate)
    return [10 * np.log10(s[(f >= a) & (f < b)].sum() + 1e-12) for a, b in BANDS]


def peak_hz(x, rate):
    f, d = spectrum_db(x, rate, 15.0, 150.0)
    return float(f[int(np.argmax(d))]) if len(d) and np.max(d) > -100 else None


def window(x, rate):
    a = int(EVENT_AT * rate)
    return np.asarray(x[a:a + int(WINDOW_S * rate)], float)


def run_host(args, env_sources, cwd_out):
    env = dict(os.environ)
    env["I76_LFE_SOURCES"] = env_sources
    os.makedirs(cwd_out, exist_ok=True)
    r = subprocess.run([host_exe()] + args, capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def render_stem(name, loop, out):
    args = ["stems", "render", "--name", name, "--player", "--out", out, "--tag", name, "--sinks", "lfe-wav", "--seconds", "3.0"]
    if loop:
        args += ["--mode", "1", "--stop", str(EVENT_AT + WINDOW_S)]
    code, log = run_host(args, "synth=0,stems=1", out)
    p = os.path.join(out, name + ".lfe.wav")
    return (p if code == 0 and os.path.exists(p) else None), log


_synth_cache = {}


def render_synth(eid, out):
    if eid in _synth_cache:
        return _synth_cache[eid]
    code, log = run_host(["preview", "--effect", eid, "--out", out, "--sinks", "lfe-wav"], "synth=1,stems=0", out)
    p = os.path.join(out, eid + ".lfe.wav")
    _synth_cache[eid] = ((p if code == 0 and os.path.exists(p) else None), log)
    return _synth_cache[eid]


def esc(x):
    return html.escape(str(x))


def fmt_db(v):
    return " / ".join("%.0f" % b for b in v)


def row(name, meta, effects, rel):
    out = ['<section id="%s"><h2>%s <small>%s, %s, %.2f s, peak %.1f dBFS</small></h2>' % (
        esc(name), esc(name), esc(meta.get("category")), "loop" if meta.get("loop") else "one-shot", meta.get("duration_s", 0), meta.get("peak_dbfs", 0))]
    stem_path = os.path.join(os.path.dirname(MANIFEST), meta["file"])
    rate, stem = read_wav(stem_path)
    eid, why = effect_for(name, meta.get("category"), effects)
    sp, slog = render_stem(name, bool(meta.get("loop")), os.path.join(VIEW, "render", "stem"))
    yp, ylog = render_synth(eid, os.path.join(VIEW, "render", "synth")) if eid else (None, why)
    img = os.path.join(VIEW, "img", name)
    series, rows = [], []
    sw = yw = None
    if sp:
        _, s_all = read_wav(sp); sw = window(s_all, 16000)
        f, d = spectrum_db(sw, 16000); series.append((np.log2(f), d))
    if yp:
        _, y_all = read_wav(yp); yw = window(y_all, 16000)
        f, d = spectrum_db(yw, 16000); series.append((np.log2(f), d))
    if series:
        line_plot_png(img + ".spec.png", series, width=520, height=160, ylim=(-80, 0), zero_line=False,
                      colors=[(31, 119, 180), (214, 39, 40)])
    spectrogram_png(img + ".stem.spec.png", stem, rate, fmax=F_HI, width=260, height=90, win=2048)
    t = np.arange(len(stem)) / rate
    line_plot_png(img + ".stem.wave.png", [(t, stem)], width=260, height=90, ylim=(-1, 1))
    for label, x, r in (("stem file", stem, rate), ("stem through the host (stems only)", sw, 16000), ("Lfe.Synth, same event (synth only)", yw, 16000)):
        if x is None:
            rows.append("<tr><th>%s</th><td colspan=3 class=dim>%s</td></tr>" % (esc(label), "not rendered" if label.startswith("stem") else esc(why)))
            continue
        pk = peak_hz(x, r)
        rows.append("<tr><th>%s</th><td>%s</td><td>%s</td><td>%.2f</td></tr>" % (
            esc(label), fmt_db(band_db(x, r)), "%.0f Hz" % pk if pk else "-", float(np.abs(x).max()) if len(x) else 0.0))
    out.append('<div class="grid"><div class="box"><h3>Spectrum 10-160 Hz <small>(log axis; blue = stem via host, red = Lfe.Synth)</small></h3>')
    out.append('<img src="img/%s.spec.png" title="x: log2 Hz 10..160, y: -80..0 dBFS">' % esc(name) if series else "<p class=dim>nothing rendered</p>")
    out.append("<table><tr><th></th><th>20-40 / 40-80 / 80-160 Hz dB</th><th>peak</th><th>max |x|</th></tr>%s</table>" % "".join(rows))
    out.append("<p class=dim>Lfe.Synth event: %s%s</p></div>" % (esc(eid or "none"), " (" + esc(why) + ")" if eid else ""))
    out.append('<div class="box"><h3>Stem file</h3><img src="img/%s.stem.wave.png" title="waveform -1..1"> <img src="img/%s.stem.spec.png" title="spectrogram 0-160 Hz">' % (esc(name), esc(name)))
    out.append("<details><summary>host logs</summary><pre>%s\n\n%s</pre></details></div></div></section>" % (esc(slog), esc(ylog)))
    return "\n".join(out), {"stem": name, "effect": eid, "why": why, "stem_rendered": sp is not None, "synth_rendered": yp is not None}


def main(argv=None):
    global MANIFEST
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="")
    ap.add_argument("--manifest", default=MANIFEST)
    a = ap.parse_args(argv)
    MANIFEST = a.manifest
    if not os.path.exists(MANIFEST):
        print("no LFE stem manifest at %s - build the pack first: tools\\soundhd\\soundhd.py build" % MANIFEST)
        return 2
    man = json.load(open(MANIFEST, encoding="utf-8"))
    effects = load_effects()
    names = sorted(man["sounds"])
    if a.only:
        want = [s.strip().lower() for s in a.only.split(",") if s.strip()]
        names = [n for n in names if n in want]
    os.makedirs(os.path.join(VIEW, "img"), exist_ok=True)
    rel = lambda p: os.path.relpath(p, VIEW).replace("\\", "/")
    body, index = [], []
    for n in names:
        h, info = row(n, man["sounds"][n], effects, rel)
        body.append(h); index.append(info)
    no_synth = [i["stem"] for i in index if not i["effect"]]
    toc = " &middot; ".join('<a href="#%s">%s</a>' % (esc(n), esc(n)) for n in names)
    page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stems vs synth</title><style>
:root{--bg:#fafafa;--fg:#222;--dim:#777;--box:#fff;--line:#ddd}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#16181c;--fg:#e6e6e6;--dim:#999;--box:#1f2228;--line:#333}}
:root[data-theme="dark"]{--bg:#16181c;--fg:#e6e6e6;--dim:#999;--box:#1f2228;--line:#333}
body{background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;margin:0 16px 40px}
h1{margin:16px 0 4px} section{border-top:2px solid var(--line);margin-top:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%%,420px),1fr));gap:12px}
.box{background:var(--box);border:1px solid var(--line);border-radius:6px;padding:8px 12px;overflow-x:auto}
img{max-width:100%%;image-rendering:pixelated;border:1px solid var(--line)} table{border-collapse:collapse} th,td{text-align:left;padding:2px 8px 2px 0;vertical-align:top}
.dim,small{color:var(--dim)} pre{white-space:pre-wrap;font-size:12px}
</style></head><body><h1>HD sound pack LFE stems vs Lfe.Synth</h1>
<p class=dim>Generated by tools/haptics/design/stems_view.py from %s (%s) and the host (files only). Each row: the stem, the stem as
the shaker gets it with <code>lfe.sources</code> stems only, and what Lfe.Synth makes for the same event with synth only. %d stems; %d have no
Lfe.Synth effect on their event (%s).</p><p>%s</p>%s</body></html>""" % (
        esc(MANIFEST), esc(man.get("pack_version")), len(names), len(no_synth), esc(", ".join(no_synth)) or "none", toc, "\n".join(body))
    with open(os.path.join(VIEW, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(VIEW, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, indent=1)
    print("wrote", os.path.join(VIEW, "index.html"), "(%d stems, %d without a synth effect)" % (len(names), len(no_synth)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
