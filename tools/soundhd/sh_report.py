"""A/B report for the HD sound pack: per sound, stock vs replacement spectrograms (20-2000 Hz, log axis, one shared
dB scale) and octave-band energies; an index.html with the loudness / true-peak / E<120 table.

PNG figures are written next to index.html (gitignored with the audio); index.html itself is committed.
"""
import html, json, math, os

import numpy as np

import sh_dsp as D
import sh_wav

STOCK_C, HD_C = "#2a78d6", "#eb6834"  # categorical slots 1/2 of the dataviz reference palette


def _spec(ax, x, fs, vmax, title, plt):
    from scipy import signal
    nper = 1024 if fs <= 12000 else 2048
    nper = min(nper, max(64, len(x)))
    f, t, s = signal.spectrogram(x, fs, window="hann", nperseg=nper, noverlap=nper * 7 // 8, scaling="spectrum")
    sdb = 10 * np.log10(s + 1e-14)
    m = (f >= 15) & (f <= 2200)
    im = ax.pcolormesh(t, f[m], sdb[m], shading="auto", cmap="Blues", vmin=vmax - 70, vmax=vmax)
    ax.set_yscale("log")
    ax.set_ylim(20, 2000)
    ax.set_yticks([20, 40, 80, 160, 320, 640, 1280])
    ax.set_yticklabels(["20", "40", "80", "160", "320", "640", "1.3k"])
    ax.set_title(title, fontsize=9, loc="left")
    ax.set_ylabel("Hz", fontsize=8)
    ax.tick_params(labelsize=7)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    return im


def _peak_db(x, fs):
    from scipy import signal
    nper = 1024 if fs <= 12000 else 2048
    nper = min(nper, max(64, len(x)))
    _, _, s = signal.spectrogram(x, fs, window="hann", nperseg=nper, noverlap=nper * 7 // 8, scaling="spectrum")
    return float(10 * np.log10(s.max() + 1e-14))


def figure(path, name, sx, sfs, nx, nfs, sb, nb):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(9.0, 5.2), dpi=80)
    gs = fig.add_gridspec(2, 2, width_ratios=[2.2, 1.0], hspace=0.45, wspace=0.45)
    vmax = max(_peak_db(sx, sfs), _peak_db(nx, nfs))
    a1 = fig.add_subplot(gs[0, 0])
    _spec(a1, sx, sfs, vmax, "%s  stock (8-bit, %d Hz)" % (name, sfs), plt)
    a2 = fig.add_subplot(gs[1, 0], sharex=a1)
    im = _spec(a2, nx, nfs, vmax, "%s  HD (16-bit, %d Hz)" % (name, nfs), plt)
    a2.set_xlabel("s", fontsize=8)
    cb = fig.colorbar(im, ax=[a1, a2], fraction=0.025, pad=0.01)
    cb.set_label("dB (shared scale)", fontsize=7)
    cb.ax.tick_params(labelsize=7)
    a3 = fig.add_subplot(gs[:, 1])
    labels = ["%d" % lo if lo < 1000 else "%.1fk" % (lo / 1000) for lo, _ in D.BANDS]
    y = np.arange(len(labels))
    floor = -90.0
    sv = [v if v is not None else floor for v in sb]
    nv = [v if v is not None else floor for v in nb]
    h = 0.38
    a3.barh(y - h / 2 - 0.02, [v - floor for v in sv], h, left=floor, color=STOCK_C, label="stock")
    a3.barh(y + h / 2 + 0.02, [v - floor for v in nv], h, left=floor, color=HD_C, label="HD")
    a3.set_yticks(y)
    a3.set_yticklabels([l + " Hz" for l in labels], fontsize=7)
    a3.invert_yaxis()
    a3.set_xlim(floor, 0)
    a3.set_xlabel("octave-band energy, dBFS", fontsize=8)
    a3.tick_params(labelsize=7)
    a3.grid(axis="x", color="#dddddd", linewidth=0.6)
    a3.set_axisbelow(True)
    for sp in ("top", "right"):
        a3.spines[sp].set_visible(False)
    a3.legend(fontsize=7, frameon=False, loc="lower right")
    a3.set_title("band energies", fontsize=9, loc="left")
    fig.savefig(path, facecolor="white")
    plt.close(fig)


CSS = """
:root{--bg:#ffffff;--fg:#1f1f1e;--muted:#5f5e58;--line:#e2e1da;--bad:#b3261e;--good:#1b7f3b;--card:#f7f6f2}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1a1a19;--fg:#f2f1ea;--muted:#c3c2b7;--line:#3a3a37;--bad:#ff8a80;--good:#7ed69a;--card:#232321}}
:root[data-theme="dark"]{--bg:#1a1a19;--fg:#f2f1ea;--muted:#c3c2b7;--line:#3a3a37;--bad:#ff8a80;--good:#7ed69a;--card:#232321}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;padding:16px;max-width:1200px}
h1{font-size:20px;margin:0 0 4px} h2{font-size:16px;margin:24px 0 8px} p{margin:4px 0 8px;color:var(--muted)}
.wrap{overflow-x:auto} table{border-collapse:collapse;font-size:12px;width:100%}
th,td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:right;white-space:nowrap}
th{position:sticky;top:0;background:var(--bg);text-align:right} td.l,th.l{text-align:left}
.bad{color:var(--bad);font-weight:600} .good{color:var(--good)}
details{background:var(--card);border-radius:6px;padding:6px 10px;margin:6px 0} img{max-width:100%;height:auto;background:#fff}
"""


def build(work, pack, stock_index, read_stock):
    rdir = os.path.join(pack, "report")
    os.makedirs(rdir, exist_ok=True)
    recipes = json.load(open(os.path.join(pack, "recipes", "recipes.json"), encoding="utf-8"))
    rinfo = json.load(open(os.path.join(pack, "render-info.json"), encoding="utf-8"))
    _, idx = stock_index(work)
    rows = []
    for stem, rec in recipes["sounds"].items():
        name = rec["file"]
        sd = sh_wav.decode(read_stock(work, name))
        nd = sh_wav.decode(open(os.path.join(pack, "addon", name), "rb").read())
        sx = sd["x"] - np.mean(sd["x"])
        sfs, nfs = sd["fmt"]["rate"], nd["fmt"]["rate"]
        nx = nd["x"]
        sb, nb = D.band_energies_db(sx, sfs), D.band_energies_db(nx, nfs)
        png = stem + ".png"
        figure(os.path.join(rdir, png), name, sx, sfs, nx, nfs, sb, nb)
        ri = rinfo.get(stem, {})
        rows.append(dict(stem=stem, file=name, cat=rec["category"], rid=rec["id"], loop=rec["loop"], sfs=sfs, nfs=nfs,
                         Ls=D.loudness(sx, sfs), Ln=D.loudness(nx, nfs), tp=D.true_peak_db(nx, rec["loop"]),
                         e_s=D.frac_band(sx, sfs, 20, 120), e_n=D.frac_band(nx, nfs, 20, 120), sb=sb, nb=nb, png=png,
                         stage=ri.get("peak_stage"), gr=ri.get("limiter_max_gr_db"), oct=ri.get("octave"),
                         ons=ri.get("onsets"), why=rec.get("why", ""), skipped=rec["sub"].get("skipped")))
        print("report %-10s" % stem)
    write_index(rdir, rows, recipes)
    print("report: %d sounds -> %s" % (len(rows), os.path.join(rdir, "index.html")))


def _f(v, fmt="%.2f"):
    return "" if v is None or (isinstance(v, float) and not math.isfinite(v)) else fmt % v


def write_index(rdir, rows, recipes):
    e = html.escape
    out = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
           "<title>Sound HD report</title><style>%s</style></head><body>" % CSS,
           "<h1>I'76 HD sound pack: A/B report</h1>",
           "<p>%s. %d replacements; %d stock files untouched (CB/dialogue, shell UI, loose music). Stock = the pristine "
           "I76.ZFS payload (8-bit); HD = the rendered ADDON file (16-bit). Loudness = BS.1770-4 integrated (files under "
           "400 ms: one block of their own length). E20-120 = fraction of energy between 20 and 120 Hz. Band columns = HD minus "
           "stock octave-band energy in dB. Figures (stock/HD spectrograms on one dB scale + band energies) open per row.</p>"
           % (e(recipes["pack_version"]), len(rows), len(recipes["untouched"])),
           "<div class=wrap><table><thead><tr><th class=l>sound</th><th class=l>recipe</th><th>loop</th><th>Hz</th>"
           "<th>stock LUFS</th><th>HD LUFS</th><th>&Delta; LU</th><th>HD dBTP</th><th>E20-120 stock</th><th>E20-120 HD</th>"]
    for lo, _ in D.BANDS:
        out.append("<th>&Delta;%s</th>" % (("%d" % lo) if lo < 1000 else "%.1fk" % (lo / 1000)))
    out.append("<th class=l>peak stage</th></tr></thead><tbody>")
    for r in rows:
        dl = r["Ln"] - r["Ls"] if math.isfinite(r["Ln"]) and math.isfinite(r["Ls"]) else None
        cls = "bad" if dl is not None and abs(dl) > 0.5 else ""
        tcls = "bad" if r["tp"] > -0.25 else ""
        out.append("<tr><td class=l><a href='#%s'>%s</a></td><td class=l>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td>"
                   "<td class='%s'>%s</td><td class='%s'>%s</td><td>%s</td><td>%s</td>" % (
                       e(r["stem"]), e(r["file"]), e(r["rid"]), "yes" if r["loop"] else "", r["nfs"], _f(r["Ls"]), _f(r["Ln"]),
                       cls, _f(dl, "%+.2f"), tcls, _f(r["tp"]), _f(r["e_s"], "%.3f"), _f(r["e_n"], "%.3f")))
        for a, b in zip(r["sb"], r["nb"]):
            out.append("<td>%s</td>" % (_f(b - a, "%+.1f") if a is not None and b is not None else ""))
        out.append("<td class=l>%s%s</td></tr>" % (e(r["stage"] or ""), (" (GR %.1f dB)" % r["gr"]) if r["gr"] else ""))
    out.append("</tbody></table></div><h2>Per sound</h2>")
    for r in rows:
        extra = []
        if r["oct"]:
            o = r["oct"]
            extra.append("f0 tracker: %s, f0 median %s Hz, divisor %s, sub %s Hz%s" % (
                o.get("tracker"), o.get("f0_median_hz"), o.get("octave_div"), o.get("sub_median_hz"),
                (", %s whole cycles per loop" % o["sub_cycles"]) if o.get("sub_cycles") else ""))
        if r["ons"] is not None:
            extra.append("%d onsets" % r["ons"])
        if r["skipped"]:
            extra.append("sub skipped: " + r["skipped"])
        out.append("<details id='%s'><summary>%s (%s)</summary><p>%s</p><p>%s</p><img loading=lazy src='%s' alt='%s spectrograms'></details>" % (
            e(r["stem"]), e(r["file"]), e(r["rid"]), e(r["why"]), e("; ".join(extra)), e(r["png"]), e(r["file"])))
    out.append("</body></html>")
    with open(os.path.join(rdir, "index.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))
