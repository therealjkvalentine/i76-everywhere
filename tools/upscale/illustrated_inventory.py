#!/usr/bin/env python3
r"""illustrated_inventory.py - inventory + decode of I'76's "illustrated" art classes (sprint 2026-10-03, agent U6).

Classes covered: cockpit/dash art (z*.pak/.pix, z*.map, z*.m16 from I76.ZFS), loading screens (*load.pcx),
shell art (DATABASE.MW2 via the existing mw2db extraction; nothing re-decoded), cutscene stills (Smacker .smk,
frames pulled with ffmpeg from imageio-ffmpeg).

    python illustrated_inventory.py [--zfs DIR] [--mw2db DIR] [--smk DIR] [--out DIR] [--frames]

Writes (all LOCAL, never commit; decoded game art is copyrighted):
    <out>\src\u6_cockpit\<pak>__<tile>.png + _mask.png
    <out>\src\u6_loadscreen\<name>.png
    <out>\src\u6_cutscene\<smk>_f<frame>.png          (with --frames)
    <out>\src\u6_manifest.csv                          one row per asset: class, file, source, fmt, w, h, opaque %, colours

Decoders: tools\i76img.py (VQM/MAP/M16; verified round-trip), Pillow (PCX). VQM/MAP use a world palette
(t01.act by default) because the shared cockpit codebook indexes the level palette; M16 tiles carry their own.
"""
import os, sys, csv, glob, json, argparse, subprocess

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import i76img  # noqa: E402

U = r"C:\Users\james"
DEF_ZFS = U + r"\i76-map\recon-2026-09-04\recon\formats\zfs_out"
DEF_MW2 = U + r"\i76-map\data\out\mw2db"
DEF_SMK = U + r"\i76-uncap-lab\game\smk"
DEF_OUT = U + r"\i76-upscale-work"


def save(rgba, w, h, path):
    a = np.frombuffer(rgba, np.uint8).reshape(h, w, 4)
    Image.fromarray(a[..., :3].copy()).save(path)
    m = a[..., 3]
    if (m < 255).any():
        Image.fromarray(m.copy()).save(path[:-4] + "_mask.png")
    rgb = a[..., :3][m > 0]
    ncol = len(np.unique(rgb.reshape(-1, 3), axis=0)) if len(rgb) else 0
    return round(100.0 * (m > 0).mean(), 1), ncol


def pix_entries(pix):
    toks = open(pix, "rb").read().decode("latin-1").split()
    n = int(toks[0])
    return [(toks[1 + 3 * i], int(toks[2 + 3 * i]), int(toks[3 + 3 * i])) for i in range(n)]


def cockpit(zfs, out, act, rows):
    d = os.path.join(out, "src", "u6_cockpit")
    os.makedirs(d, exist_ok=True)
    pal = i76img.read_act(os.path.join(zfs, act))
    for pak in sorted(glob.glob(os.path.join(zfs, "z*.pak"))):
        base = os.path.splitext(os.path.basename(pak))[0]
        data = open(pak, "rb").read()
        for name, off, ln in pix_entries(pak[:-4] + ".pix"):
            blob = data[off:off + ln]
            if name.lower().endswith(".m16"):
                w, h, _f, rgba = i76img.decode_m16(blob); fmt = "M16"
            else:
                w, h, rgba = i76img.decode_vqm(blob, pal, zfs); fmt = "VQM/" + act
            fn = "%s__%s.png" % (base, os.path.splitext(name)[0].lower())
            op, nc = save(rgba, w, h, os.path.join(d, fn))
            rows.append(dict(cls="cockpit", file="u6_cockpit/" + fn, source=base + ".pak:" + name, fmt=fmt, w=w, h=h,
                             opaque_pct=op, colours=nc))
    for f in sorted(glob.glob(os.path.join(zfs, "z*.map")) + glob.glob(os.path.join(zfs, "z*.m16"))):
        b = open(f, "rb").read()
        if f.endswith(".m16"):
            # loose M16s are also inside the z*.pak sets above; record size only
            w, h, _f, rgba = i76img.decode_m16(b); fmt = "M16(loose)"
        else:
            w, h, rgba = i76img.decode_map(b, pal); fmt = "MAP/" + act
        fn = "loose__" + os.path.basename(f).replace(".", "_") + ".png"
        op, nc = save(rgba, w, h, os.path.join(d, fn))
        rows.append(dict(cls="cockpit-hud", file="u6_cockpit/" + fn, source=os.path.basename(f), fmt=fmt, w=w, h=h,
                         opaque_pct=op, colours=nc))


def loadscreens(zfs, out, rows):
    d = os.path.join(out, "src", "u6_loadscreen")
    os.makedirs(d, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(zfs, "*.pcx"))):
        im = Image.open(f)
        n = os.path.splitext(os.path.basename(f))[0]
        im.convert("RGB").save(os.path.join(d, n + ".png"))
        rows.append(dict(cls="loadscreen", file="u6_loadscreen/%s.png" % n, source=os.path.basename(f),
                         fmt="PCX %s" % im.mode, w=im.width, h=im.height, opaque_pct=100.0,
                         colours=len(im.convert("RGB").getcolors(1 << 24))))


def shell(mw2, rows):
    man = json.load(open(os.path.join(mw2, "manifest.json")))
    for e in man["members"]:
        t = e.get("type", "?")
        rows.append(dict(cls="shell-" + t, file="(mw2db)/" + str(e.get("file", "")), source="DATABASE.MW2:" + e["id"],
                         fmt=e.get("info", t), w=e.get("width", ""), h=e.get("height", ""), opaque_pct="",
                         colours="", note=e.get("used_by", "")))


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def smacker(smk, out, rows, frames):
    ff = ffmpeg_exe()
    d = os.path.join(out, "src", "u6_cutscene")
    os.makedirs(d, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(smk, "*.SMK")) + glob.glob(os.path.join(smk, "*.smk"))):
        n = os.path.splitext(os.path.basename(f))[0].lower()
        if any(r["source"] == os.path.basename(f) for r in rows):
            continue
        p = subprocess.run([ff, "-hide_banner", "-i", f], capture_output=True, text=True)
        info = [l.strip() for l in p.stderr.splitlines() if "Video:" in l or "Duration" in l]
        size = ""
        for l in info:
            if "Video:" in l:
                for tok in l.replace(",", " ").split():
                    if tok.count("x") == 1 and all(s.isdigit() for s in tok.split("x")):
                        size = tok
                        break
        w, h = (size.split("x") + ["", ""])[:2]
        rows.append(dict(cls="cutscene", file="", source=os.path.basename(f), fmt="SMK " + " | ".join(info)[:160],
                         w=w, h=h, opaque_pct="", colours=""))
        if frames and n in frames:
            for t in frames[n]:
                o = os.path.join(d, "%s_t%s.png" % (n, str(t).replace(".", "p")))
                subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", f,
                                "-frames:v", "1", o])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zfs", default=DEF_ZFS)
    ap.add_argument("--mw2db", default=DEF_MW2)
    ap.add_argument("--smk", default=DEF_SMK)
    ap.add_argument("--out", default=DEF_OUT)
    ap.add_argument("--act", default="t01.act")
    ap.add_argument("--frames", default="", help="smk:t,t;smk:t  e.g. introf01:20,60;int01f01:10")
    a = ap.parse_args()
    if os.path.abspath(a.out).lower().startswith(os.path.abspath(U + r"\i76-everywhere").lower()):
        sys.exit("refusing to write decoded art inside the public repo")
    frames = {}
    for part in filter(None, a.frames.split(";")):
        k, v = part.split(":")
        frames[k.lower()] = [float(x) for x in v.split(",")]
    rows = []
    cockpit(a.zfs, a.out, a.act, rows)
    loadscreens(a.zfs, a.out, rows)
    shell(a.mw2db, rows)
    smacker(a.smk, a.out, rows, frames)
    keys = ["cls", "file", "source", "fmt", "w", "h", "opaque_pct", "colours", "note"]
    with open(os.path.join(a.out, "src", "u6_manifest.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, keys)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: r.get(k, "") for k in keys})
    from collections import Counter
    c = Counter((r["cls"], "%sx%s" % (r["w"], r["h"])) for r in rows)
    for (k, s), n in sorted(c.items()):
        print("%-22s %-10s %4d" % (k, s, n))


if __name__ == "__main__":
    main()
