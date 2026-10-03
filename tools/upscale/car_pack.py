#!/usr/bin/env python3
"""car_pack.py - build real 2x upscaled ADDON overrides of a car's M16 texture packs (*6.pak + .pix).

The U1-U5 recipe (findings U2/U3/U5), applied to every M16 tile of each pack:
  1. decode the stock tile (index plane + RGB565 palette; index 0xFF = transparent),
  2. RGB with transparent texels bled 4 px (prepost.bleed), reflect-padded 16 px,
  3. 4x model (default: Manga109Attempt x RRDB_PSNR 0.5 interpolation), Lanczos down to 2x,
  4. separate alpha: the original mask resized (bilinear) to 2x and thresholded at 0.5,
  5. colour: prepost.lut3d_match(final, orig, mask, n=9, smooth=1.0); no de-dither,
  6. quantised to <= 255 RGB565 colours (opaque texels only; 0xFF stays transparent) and rebuilt with
     i76img.build_m16 using the tile's own flags byte.
Tiles whose 2x size would exceed 256 on a side are copied unchanged (Glide 2 cap). Non-M16 entries are copied.

Usage:
  python car_pack.py --game <game dir> --out <game dir>\\ADDON --pak pirana16 [--pak pirana26 ...]
                     [--model PATH.pth] [--tiles-dir DIR] [--sheet DIR]
The source pack is always read from <game>\\I76.ZFS (never from ADDON, which may hold earlier test packs).
--tiles-dir saves orig/final PNGs per tile; --sheet writes a per-pack contact sheet (original nearest 2x | final).
Output is copyrighted game art (derived): never commit it.
"""
import argparse, hashlib, json, os, sys, time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import i76img                      # noqa: E402
import prepost                     # noqa: E402
import upscale_run as ur           # noqa: E402
from m16_scale_marker import parse_pix   # noqa: E402

WORK = os.environ.get("I76_UPSCALE_WORK", r"C:\Users\james\i76-upscale-work")
DEFAULT_MODEL = os.path.join(WORK, "models", "interp", "4x_Manga109Attempt__4x_RRDB_PSNR__w50.pth")
REFUSE = (r"\games\interstate76", r"\games", "i76-everywhere-portable", r"\i76-uncap-lab\game\addon",
          r"\i76-uncap-lab\game-dd-20261003")


def read_zfs_pack(game, name, i76fmt_dir):
    sys.path.insert(0, i76fmt_dir)
    from i76fmt import zfs
    z = zfs.parse(open(os.path.join(game, "I76.ZFS"), "rb").read())
    ents = {e.name.lower(): e for e in z.entries}
    return z.read(ents[name + ".pak"]), z.read(ents[name + ".pix"]).decode("latin1")


def decode(idx, pal, w, h):
    lut = np.array([i76img.rgb565_to_rgb888(c) for c in pal] + [(0, 0, 0)] * (256 - len(pal)), np.float32) / 255
    a = np.frombuffer(idx, np.uint8).reshape(h, w)
    return lut[a], a != 0xFF


def quantise_565(rgb, mask, max_colors=255):
    """float RGB + bool mask -> (index bytes with 0xFF where transparent, RGB565 palette list)."""
    h, w = mask.shape
    u8 = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    # snap to the 565 grid first so the palette is exact
    r = ((u8[..., 0].astype(np.int32) * 31 + 127) // 255)
    g = ((u8[..., 1].astype(np.int32) * 63 + 127) // 255)
    b = ((u8[..., 2].astype(np.int32) * 31 + 127) // 255)
    c565 = (r << 11) | (g << 5) | b
    opaque = c565[mask]
    uniq = np.unique(opaque)
    out = np.full((h, w), 0xFF, np.uint8)
    if len(uniq) <= max_colors:
        pal = [int(c) for c in uniq]
        out[mask] = np.searchsorted(uniq, opaque).astype(np.uint8)
        return out.tobytes(), pal
    snapped = np.stack([(r * 255) // 31, (g * 255) // 63, (b * 255) // 31], -1).astype(np.uint8)
    pix = snapped[mask].reshape(1, -1, 3)
    q = Image.fromarray(pix, "RGB").quantize(colors=max_colors, method=Image.MEDIANCUT, dither=Image.NONE)
    qp = np.array(q.getpalette()[:3 * max_colors], np.int32).reshape(-1, 3)
    qi = np.asarray(q, np.uint8).ravel()
    used = np.unique(qi)
    remap = np.zeros(256, np.uint8)
    remap[used] = np.arange(len(used))
    pal = [i76img.rgb888_to_rgb565(*map(int, qp[u])) for u in used]
    out[mask] = remap[qi]
    return out.tobytes(), pal


def upscale_tile(data, model, cfg):
    w, h, flags, idx, pal = i76img.parse_m16(data)
    W, H = 2 * w, 2 * h
    if max(W, H) > 256:
        return None, (w, h)
    rgb, mask = decode(idx, pal, w, h)
    if not mask.any():
        big_idx = np.repeat(np.repeat(np.frombuffer(idx, np.uint8).reshape(h, w), 2, 0), 2, 1)
        return (i76img.build_m16(W, H, flags, big_idx.tobytes(), pal), rgb, mask, None, None), (w, h)
    src = prepost.bleed(rgb, mask, px=4) if not mask.all() else rgb
    big, _ = ur.upscale_rgb(WORK, src.astype(np.float32), dict(cfg, model=model), "reflect")
    fin = ur.resize(big, W, H, "lanczos").clip(0, 1)
    fmask = prepost.upscale_alpha_threshold(mask.astype(np.float32), W, H, thr=0.5)
    fin = prepost.lut3d_match(fin, rgb, mask, n=9, smooth=1.0)
    qidx, qpal = quantise_565(fin, fmask)
    return (i76img.build_m16(W, H, flags, qidx, qpal), rgb, mask, fin, fmask), (w, h)


def on_magenta(rgb, mask):
    out = np.array(rgb, np.float32).copy()
    out[~mask] = (1, 0, 1)
    return Image.fromarray((out.clip(0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


def sheet(rows, path, zoom=2):
    """rows: (name, orig PIL (native), final PIL (2x)). Original nearest-scaled to the final size; both x zoom."""
    from PIL import ImageDraw
    cells = []
    for nm, o, f in rows:
        o2 = o.resize(f.size, Image.NEAREST).resize((f.width * zoom, f.height * zoom), Image.NEAREST)
        f2 = f.resize((f.width * zoom, f.height * zoom), Image.NEAREST)
        cells.append((nm, o2, f2))
    pad, lab = 6, 14
    colw = max(c[1].width for c in cells)
    W = 2 * colw + 3 * pad
    H = sum(c[1].height + lab + pad for c in cells) + pad
    im = Image.new("RGB", (W, H), (32, 32, 32))
    d = ImageDraw.Draw(im)
    y = pad
    for nm, o, f in cells:
        d.text((pad, y), f"{nm}  original (nearest)  |  final 2x", fill=(230, 230, 230))
        y += lab
        im.paste(o, (pad, y)); im.paste(f, (2 * pad + colw, y))
        y += o.height + pad
    im.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pak", action="append", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--tile", type=int, default=512)
    ap.add_argument("--sheet", default=None, help="dir for <pak>-sheet.png contact sheets")
    ap.add_argument("--i76fmt", default=r"C:\Users\james\i76-map\tools")
    a = ap.parse_args()
    out_abs = os.path.abspath(a.out).lower()
    if any(b in out_abs for b in REFUSE):
        sys.exit(f"refusing --out {a.out}: a playable install or protected copy")
    os.makedirs(a.out, exist_ok=True)
    cfg = dict(ur.DEFAULTS, overscale=4, target_scale=2, pad_px=16, tile=a.tile)
    for name in a.pak:
        t0 = time.time()
        pak, pix = read_zfs_pack(a.game, name.lower(), a.i76fmt)
        parts, man, off, info, rows = [], [], 0, [], []
        for nm, o, ln in parse_pix(pix):
            data = pak[o:o + ln]
            new = data
            if nm.upper().endswith(".M16"):
                res, (w, h) = upscale_tile(data, a.model, cfg)
                if res is None:
                    info.append({"name": nm, "from": f"{w}x{h}", "to": "unchanged (>256 at 2x)"})
                else:
                    new, rgb, mask, fin, fmask = res
                    W2, H2, _, qi, qp = i76img.parse_m16(new)
                    info.append({"name": nm, "from": f"{w}x{h}", "to": f"{W2}x{H2}", "colors": len(qp)})
                    if a.sheet and fin is not None:
                        rows.append((nm, on_magenta(rgb, mask), on_magenta(decode(qi, qp, W2, H2)[0], fmask)))
            parts.append(new); man.append((nm, off, len(new))); off += len(new)
        base = os.path.join(a.out, name.lower())
        blob = b"".join(parts)
        open(base + ".pak", "wb").write(blob)
        with open(base + ".pix", "w", newline="") as f:
            f.write(f"{len(man)}\r\n")
            for nm, o, ln in man:
                f.write(f"{nm} {o} {ln}\r\n")
        # read back: every entry re-parses and the 2x tiles have the size we meant
        rb = open(base + ".pak", "rb").read()
        for nm, o, ln in man:
            if nm.upper().endswith(".M16"):
                i76img.parse_m16(rb[o:o + ln])
        rep = {"pak": name, "source": "I76.ZFS", "model": os.path.basename(a.model),
               "recipe": "bleed4 > 4x > lanczos 2x; mask bilinear thr0.5; lut3d n9 s1; 565 quantise <=255",
               "tiles": info, "pak_bytes": len(blob), "pak_md5": hashlib.md5(blob).hexdigest()}
        json.dump(rep, open(base + ".car-pack.json", "w"), indent=1)
        if a.sheet and rows:
            os.makedirs(a.sheet, exist_ok=True)
            sheet(rows, os.path.join(a.sheet, f"{name.lower()}-sheet.png"))
        print(f"{name}: {sum(1 for i in info if 'colors' in i)} of {len(man)} entries -> 2x; "
              f"{len(blob)} bytes; {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
