#!/usr/bin/env python3
"""m16_scale_marker.py - build a loose ADDON override of an M16 texture pack (*6.pak + .pix) at 1x or 2x,
stamped with a marker that can only exist at the chosen resolution. The in-game test for "does the original
game (Glide -> ZGLIDE -> dgVoodoo) render a texture bigger than the file it replaces?".

Index-level and lossless apart from the marker: each M16 is parsed (i76img.parse_m16), its index plane is
scaled by pixel replication (so the art is unchanged, only denser), one palette slot becomes magenta, the
marker is drawn in that slot at the NEW resolution, and the tile is rebuilt with the same flags byte.

Marker at scale s (all in the new texel grid, transparent 0xFF texels left alone):
  - a 1-texel magenta border and a 1-texel diagonal X. At s=2 these lines are half an original texel wide,
    which no 1x texture can show: if they render thin and crisp, the 2x upload is live.
  - a 1-texel magenta/original checker over the top-left quarter. At s=2 it is finer than the original
    grid; a fallback to 1x art cannot produce it.
What each outcome means (chase view on the player's car):
  thin border + X + fine checker on every panel  -> 2x accepted, UVs normalised, the route works.
  only the top-left quarter of each panel, magnified -> UVs are in texels (not expected: ZGLIDE scales s,t
                                                      from normalised UVs, see docs).
  stock paint                                      -> the override did not load (wrong scheme / name).
  crash, white or wrong textures                   -> size rejected or TMU allocator failure.

Usage:
  python m16_scale_marker.py --game <game dir> --out <game dir>\\ADDON --pak pirana16 [--pak pirana26 ...]
                             [--scale 2] [--only PP11BKB1.M16 ...] [--no-marker]
Source: the pack is read from <game>\\ADDON if a loose copy exists there, else from <game>\\I76.ZFS through
i76-map's pure-Python ZFS reader (--i76fmt, default C:\\Users\\james\\i76-map\\tools). Writes <pak>.pak and
<pak>.pix to --out and a <pak>.scale-marker.json manifest (names, sizes, md5). Never writes into I76.ZFS.
Undo: delete the written .pak/.pix from ADDON.

Output is copyrighted game art (derived): never commit it.
"""
import argparse, hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))          # tools/i76img.py
import i76img

MAGENTA565 = 0xF81F


def read_pack(game, name, i76fmt_dir):
    """Return (pak bytes, pix text) for <name>.pak/.pix: loose ADDON copy first, then I76.ZFS."""
    addon = os.path.join(game, "ADDON")
    lp, lx = os.path.join(addon, name + ".pak"), os.path.join(addon, name + ".pix")
    if os.path.exists(lp) and os.path.exists(lx):
        return open(lp, "rb").read(), open(lx, "rb").read().decode("latin1"), "ADDON"
    sys.path.insert(0, i76fmt_dir)
    from i76fmt import zfs
    z = zfs.parse(open(os.path.join(game, "I76.ZFS"), "rb").read())
    ents = {e.name.lower(): e for e in z.entries}
    return z.read(ents[name + ".pak"]), z.read(ents[name + ".pix"]).decode("latin1"), "I76.ZFS"


def parse_pix(text):
    tok = text.split()
    n = int(tok[0])
    out = []
    for i in range(n):
        nm, off, ln = tok[1 + 3 * i], int(tok[2 + 3 * i]), int(tok[3 + 3 * i])
        out.append((nm, off, ln))
    return out


def magenta_slot(idx, pal):
    """A palette index to repaint magenta: a new slot if there is room, else the least-used one
    (its texels are remapped to the nearest other colour first)."""
    if len(pal) < 255:
        pal.append(MAGENTA565)
        return len(pal) - 1, idx
    counts = [0] * len(pal)
    for i in idx:
        if i < len(pal):
            counts[i] += 1
    victim = min(range(len(pal)), key=lambda i: counts[i])
    def d(a, b):
        return abs((a >> 11) - (b >> 11)) + abs((a >> 5 & 63) - (b >> 5 & 63)) + abs((a & 31) - (b & 31))
    near = min((i for i in range(len(pal)) if i != victim), key=lambda i: d(pal[i], pal[victim]))
    idx = bytes(near if i == victim else i for i in idx)
    pal[victim] = MAGENTA565
    return victim, idx


def scale_tile(data, s, marker):
    w, h, flags, idx, pal = i76img.parse_m16(data)
    W, H = w * s, h * s
    if max(W, H) > 256:
        raise ValueError(f"{w}x{h} x{s} = {W}x{H}: Glide 2 / ZGLIDE cap a side at 256")
    rows = [idx[y * w:(y + 1) * w] for y in range(h)]
    big = bytearray()
    for y in range(H):
        r = rows[y // s]
        big += bytes(r[x // s] for x in range(W))
    pal = list(pal)
    if marker:
        m, small = magenta_slot(bytes(big), pal)
        big = bytearray(small)
        def put(x, y):
            o = y * W + x
            if big[o] != 0xFF:
                big[o] = m
        for x in range(W):
            put(x, 0); put(x, H - 1)
        for y in range(H):
            put(0, y); put(W - 1, y)
        for i in range(W):                       # X across the (possibly non-square) tile
            y = i * H // W
            put(i, y); put(W - 1 - i, y)
        for y in range(H // 2):
            for x in range(W // 2):
                if (x + y) & 1:
                    put(x, y)
    return i76img.build_m16(W, H, flags, bytes(big), pal), (w, h, W, H)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", required=True, help="game folder holding I76.ZFS (read only)")
    ap.add_argument("--out", required=True, help="where to write <pak>.pak/.pix (normally <copy>\\ADDON)")
    ap.add_argument("--pak", action="append", required=True, help="pack base name, e.g. pirana16 (repeatable)")
    ap.add_argument("--scale", type=int, default=2, choices=(1, 2, 4))
    ap.add_argument("--only", action="append", default=[], help="entry names to touch (default: all)")
    ap.add_argument("--no-marker", action="store_true", help="scale only (memory-pressure runs)")
    ap.add_argument("--i76fmt", default=r"C:\Users\james\i76-map\tools")
    a = ap.parse_args()
    out_abs = os.path.abspath(a.out).lower()
    for bad in (r"\games\interstate76", "i76-everywhere-portable", r"\i76-uncap-lab\game\addon",
                r"\i76-uncap-lab\game-dd-20261003"):
        if bad in out_abs:
            sys.exit(f"refusing --out {a.out}: that is a playable install or the lab's protected sandbox")
    os.makedirs(a.out, exist_ok=True)
    only = {n.upper() for n in a.only}
    for name in a.pak:
        pak, pix, src = read_pack(a.game, name.lower(), a.i76fmt)
        parts, man, off, info = [], [], 0, []
        for nm, o, ln in parse_pix(pix):
            data = pak[o:o + ln]
            if nm.upper().endswith(".M16") and (not only or nm.upper() in only):
                new, (w, h, W, H) = scale_tile(data, a.scale, not a.no_marker)
                info.append({"name": nm, "from": f"{w}x{h}", "to": f"{W}x{H}"})
            else:
                new = data
            parts.append(new); man.append((nm, off, len(new))); off += len(new)
        base = os.path.join(a.out, name.lower())
        blob = b"".join(parts)
        open(base + ".pak", "wb").write(blob)
        with open(base + ".pix", "w", newline="") as f:
            f.write(f"{len(man)}\r\n")
            for nm, o, ln in man:
                f.write(f"{nm} {o} {ln}\r\n")
        rep = {"pak": name, "source": src, "scale": a.scale, "marker": not a.no_marker,
               "tiles_changed": info, "pak_bytes": len(blob), "pak_md5": hashlib.md5(blob).hexdigest()}
        json.dump(rep, open(base + ".scale-marker.json", "w"), indent=1)
        print(f"{name}: {len(info)} of {len(man)} tiles -> x{a.scale} ({src}); {len(blob)} bytes -> {base}.pak")


if __name__ == "__main__":
    main()
