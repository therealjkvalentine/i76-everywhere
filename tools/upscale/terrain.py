#!/usr/bin/env python3
"""Terrain texture tools for the I'76 upscaling sprint (2026-10-03, agent U4). Code only; images stay in
i76-upscale-work (never commit decoded art).

Format facts this relies on (findings\\U4.md; renderer: i76-uncap-lab\\docs\\TEXTURE-AND-OBJECT-LOD.md):
  * A mission names ONE terrain texture in WRLD (e.g. tp041db6.map). The engine replaces character 4 with
    '2'..'6' and loads five textures: level 0 = '2' (256 px, used to 50 m), 1 = '3' (64), 2 = '4' (64),
    3 = '5' (32), 4..6 = '6' (16). The '1' member is never loaded. Under Glide the .m16 of each pair is used;
    the members live in tp??m6.pak (+ .pix). Same M16 layout as vehicles, flags byte 0x80, no mip chain
    inside a file, no palette offset.
  * The texture tiles once per 40 m over the whole map, for every surface type: it only has to wrap with
    itself (no transition tiles; surface types only drive physics/sound/AI).

Subcommands
  extract ZFS OUTDIR [--sets tp04,tp09] [--manifest CSV] [--missions-dir DIR]
        RGB PNG + mask PNG + raw .m16 per member, manifest rows (appended) with mission usage.
  roundtrip ZFS [--sets ...]          parse_m16 -> build_m16 byte-identity on every member (exit 1 on diff)
  preview PNG OUT.png [--n 4]         n x n tiled view
  seam PNG [PNG ...]                  wrap-seam strength (see seam_strength)
"""
from __future__ import annotations

import csv, glob, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import i76img  # noqa: E402

LEVEL_OF = {"1": "unused", "2": "L0", "3": "L1", "4": "L2", "5": "L3", "6": "L4-6"}
RANGE_OF = {"1": "never loaded", "2": "0-50 m", "3": "50-100 m", "4": "100-200 m", "5": "200-400 m",
            "6": ">400 m"}


# ------------------------------------------------------------------------------------------- archive

def open_zfs(zfs_path):
    import zfs_extract
    data = open(zfs_path, "rb").read()
    ents = {e[0]: e for e in zfs_extract.parse(data)}

    def get(name):
        n, off, ln, comp, dlen = ents[name.lower()]
        return zfs_extract.decompress(data[off:off + ln], comp, dlen)
    return ents, get


def pak_members(get, stem):
    """stem like 'tp04m6' -> list of (name, bytes) in .pix order."""
    toks = get(stem + ".pix").decode("ascii").split()
    pak = get(stem + ".pak")
    out, it = [], iter(toks[1:])
    for name in it:
        off, ln = int(next(it)), int(next(it))
        out.append((name.lower(), pak[off:off + ln]))
    return out


def terrain_sets(ents):
    return sorted(n[:-4] for n in ents if re.fullmatch(r"tp\d\dm6\.pak", n))


def mission_terrain(missions_dir):
    """{set stem 'tp04': [(mission, hour, act), ...]} from miss16\\*.MSN WRLD headers."""
    use = {}
    for f in sorted({os.path.normcase(p) for p in glob.glob(os.path.join(missions_dir, "*.[mM][sS][nN]"))}):
        d = open(f, "rb").read()
        i = d.find(b"WRLD")
        if i < 0:
            continue
        base = i + 8
        names = [n.decode() for n in re.findall(rb"[A-Za-z0-9_]{2,8}\.[A-Za-z0-9]{3}", d[base:base + 0x93])]
        tex = [n for n in names if n.lower()[:2] in ("tp", "tt", "tm")]
        act = [n for n in names if n.lower().endswith(".act")]
        if tex:
            use.setdefault(tex[0].lower()[:4], []).append(
                (os.path.splitext(os.path.basename(f))[0].upper(), d[base + 0x93], act[0] if act else ""))
    return use


# ------------------------------------------------------------------------------------------- images

def m16_to_rgb(d):
    import numpy as np
    w, h, flags, idx, pal = i76img.parse_m16(d)
    lut = np.array([i76img.rgb565_to_rgb888(c) for c in pal] + [(0, 0, 0)] * (256 - len(pal)), np.uint8)
    a = np.frombuffer(idx, np.uint8).reshape(h, w)
    rgb = lut[a]
    mask = a != 0xFF
    return rgb, mask, (w, h, flags, len(pal), len(set(idx)))


def tile_preview(rgb, n=4):
    import numpy as np
    return np.tile(rgb, (n, n, 1))


def seam_strength(img):
    """Wrap-seam strength of a tiling texture (HxWx3 uint8/float). Luma L; column step g[x] = mean_y |L[y,x]-L[y,x-1]|
    with x=0 taken across the wrap (L[:,0]-L[:,W-1]). seam_h = g[0] / median(g[1:]); same for rows -> seam_v.
    1.0 = the wrap edge is as smooth as a typical interior column; >1.5 is a visible line.
    Also returns z: (g[0]-mean)/std over interior columns, which says how unusual the seam column is."""
    import numpy as np
    L = np.asarray(img, np.float64)[..., :3] @ np.array([0.299, 0.587, 0.114])
    out = {}
    for axis, key in ((1, "h"), (0, "v")):
        g = np.abs(L - np.roll(L, 1, axis=axis)).mean(axis=1 - axis)  # g[k]: step between k-1 and k (wrap at 0)
        inner = g[1:]
        out["seam_" + key] = float(g[0] / np.median(inner))
        out["z_" + key] = float((g[0] - inner.mean()) / (inner.std() + 1e-9))
    out["seam"] = max(out["seam_h"], out["seam_v"])
    return out


def repair_seam(img, band=3, sigma=1.2):
    """Soften a native wrap seam (tp04/tp09/tp18 carry one in the 1997 art) before upscaling: roll the seam to the
    centre, blend a 1-D Gaussian-blurred copy across +-band px with a tent weight, roll back; rows then columns.
    Touches 2*band columns and rows only. float HxWx3 in, float out."""
    import numpy as np
    from scipy.ndimage import gaussian_filter1d
    a = np.asarray(img, np.float64).copy()
    for axis in (1, 0):
        n = a.shape[axis]
        r = np.roll(a, n // 2, axis=axis)  # wrap edge now between n//2-1 and n//2
        bl = gaussian_filter1d(r, sigma, axis=axis, mode="wrap")
        k = np.arange(n) - (n // 2 - 0.5)
        wgt = np.clip(1 - np.abs(k) / band, 0, 1)
        shape = [1, 1, 1]; shape[axis] = n
        wgt = wgt.reshape(shape)
        a = np.roll(r * (1 - wgt) + bl * wgt, -(n // 2), axis=axis)
    return a


def save_png(path, arr):
    from PIL import Image
    Image.fromarray(arr).save(path)


# ------------------------------------------------------------------------------------------- commands

MANIFEST_COLS = ["file", "mask", "raw", "class", "source_format", "palette_source", "set", "member", "level",
                 "use_range", "native_w", "native_h", "colors", "palette_count", "flags", "missions", "notes"]


def cmd_extract(a):
    ents, get = open_zfs(a.zfs)
    sets = a.sets.split(",") if a.sets else [s[:4] for s in terrain_sets(ents)]
    use = mission_terrain(a.missions_dir) if a.missions_dir else {}
    os.makedirs(a.out, exist_ok=True)
    rows = []
    for s in sets:
        sd = os.path.join(a.out, s)
        os.makedirs(sd, exist_ok=True)
        miss = " ".join(f"{m}@{h:02d}h/{act}" for m, h, act in use.get(s, []))
        for name, d in pak_members(get, s + "m6"):
            stem = os.path.splitext(name)[0]
            rgb, mask, (w, h, flags, npal, ncol) = m16_to_rgb(d)
            p_rgb, p_mask, p_raw = (os.path.join(sd, stem + ".png"), os.path.join(sd, stem + ".mask.png"),
                                    os.path.join(sd, name))
            save_png(p_rgb, rgb)
            save_png(p_mask, (mask * 255).astype("uint8"))
            open(p_raw, "wb").write(d)
            if stem[4] == "2":
                save_png(os.path.join(sd, stem + ".tiled4x4.png"), tile_preview(rgb, 4))
            dup = [o for o, od in pak_members(get, s + "m6") if od == d and o != name]
            rows.append({
                "file": os.path.relpath(p_rgb, a.rel).replace("\\", "/"),
                "mask": os.path.relpath(p_mask, a.rel).replace("\\", "/"),
                "raw": os.path.relpath(p_raw, a.rel).replace("\\", "/"),
                "class": "terrain", "source_format": "M16", "palette_source": "local RGB565",
                "set": s, "member": name, "level": LEVEL_OF[stem[4]], "use_range": RANGE_OF[stem[4]],
                "native_w": w, "native_h": h, "colors": ncol, "palette_count": npal, "flags": hex(flags),
                "missions": miss, "notes": ("identical to " + "+".join(dup)) if dup else ""})
            print(f"{s} {name} {w}x{h} pal={npal} used={ncol} {LEVEL_OF[stem[4]]}")
    if a.manifest:
        new = not os.path.exists(a.manifest)
        with open(a.manifest, "a", newline="") as f:
            wr = csv.DictWriter(f, MANIFEST_COLS)
            if new:
                wr.writeheader()
            wr.writerows(rows)
        print(f"appended {len(rows)} rows to {a.manifest}")


def cmd_roundtrip(a):
    ents, get = open_zfs(a.zfs)
    sets = a.sets.split(",") if a.sets else [s[:4] for s in terrain_sets(ents)]
    n = bad = 0
    for s in sets:
        for name, d in pak_members(get, s + "m6"):
            w, h, fl, idx, pal = i76img.parse_m16(d)
            # through RGB and back too: the PNG we hand to the upscalers must re-encode to the same colours
            rgb, _, _ = m16_to_rgb(d)
            pal2 = [i76img.rgb888_to_rgb565(*rgb_c) for rgb_c in
                    (tuple(int(v) for v in i76img.rgb565_to_rgb888(c)) for c in pal)]
            ok = i76img.build_m16(w, h, fl, idx, pal) == d and pal2 == pal
            n += 1
            bad += not ok
            if not ok:
                print("DIFF", s, name)
    print(f"roundtrip: {n} members, {bad} differ")
    return 1 if bad else 0


def cmd_preview(a):
    import numpy as np
    from PIL import Image
    rgb = np.asarray(Image.open(a.png).convert("RGB"))
    save_png(a.out, tile_preview(rgb, a.n))


def cmd_seam(a):
    import numpy as np
    from PIL import Image
    for p in a.pngs:
        s = seam_strength(np.asarray(Image.open(p).convert("RGB")))
        print(f"{p}\tseam_h={s['seam_h']:.3f}\tseam_v={s['seam_v']:.3f}\tz_h={s['z_h']:.2f}\tz_v={s['z_v']:.2f}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract"); e.add_argument("zfs"); e.add_argument("out")
    e.add_argument("--sets"); e.add_argument("--manifest"); e.add_argument("--missions-dir")
    e.add_argument("--rel", default=".", help="manifest paths are relative to this dir")
    r = sub.add_parser("roundtrip"); r.add_argument("zfs"); r.add_argument("--sets")
    p = sub.add_parser("preview"); p.add_argument("png"); p.add_argument("out"); p.add_argument("--n", type=int, default=4)
    s = sub.add_parser("seam"); s.add_argument("pngs", nargs="+")
    a = ap.parse_args(argv)
    return {"extract": cmd_extract, "roundtrip": cmd_roundtrip, "preview": cmd_preview, "seam": cmd_seam}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
