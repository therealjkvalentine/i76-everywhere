#!/usr/bin/env python3
"""Build the 24-tile upscaling benchmark set (plan section 9) from an extracted I76.ZFS.

Writes, under WORK (default C:\\Users\\james\\i76-upscale-work, never inside the repo or a game folder):
  src/<class>/<name>.png       RGB original (transparent pixels left as decoded, i.e. black)
  src/<class>/<name>.mask.png  L mask, 255 = opaque, 0 = transparent (M16/VQM index 0xFF)
  src/manifest.csv             one row per tile (columns: see FIELDS)
  src/contact_originals.png    all 24 at 4x nearest-neighbour, magenta behind transparency

Usage:
  python build_bench.py [--work DIR] [--extract DIR] [--game DIR]

Sources: M16 (hardware sets, *6.pak, local RGB565 palette) wherever the asset has one; a VQM is decoded
with the ACT named like its codebook (zdash101 -> VPIT.CBK -> vpit.act; texture-lab used t01.act); PCX use their own palette.
Every decoded image is the game data as stored: billboards/signs are stored flipped (text reads mirrored /
upside down) and are NOT re-oriented, so encode-back stays trivial.
"""
import argparse, csv, os, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import i76img  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

# (class, pak or file, member, tiles_wrap, note)
BENCH = [
    ("vehicle_panel", "pirana16.pak", "pp11ftl1.m16", False, "Piranha front-left side, flat orange paint"),
    ("vehicle_panel", "sovern16.pak", "js11ftf1.m16", False, "Sovereign front: chrome grille + headlights (chrome panel)"),
    ("vehicle_panel", "pirana16.pak", "pp11ftt1.m16", False, "Piranha front top: windshield frame, glass is 0xFF transparent"),
    ("vehicle_top", "pirana16.pak", "pp11tp_1.m16", False, "Piranha roof, glass bands"),
    ("vehicle_top", "sovern16.pak", "js11tp_1.m16", False, "Sovereign roof, white paint + blue glass"),
    ("vehicle_top", "leprcn16.pak", "al11tp_1.m16", False, "Leprechaun roof"),
    ("vehicle_small", "pirana16.pak", "pp31mdt1.m16", False, "Piranha 64x32 mid-top bit, alpha"),
    ("vehicle_small", "pirana16.pak", "pp31mdb1.m16", False, "Piranha 32x16 mid-back bit"),
    ("vehicle_small", "sovern16.pak", "js31mdf1.m16", False, "Sovereign 32x16 mid-front bit (chrome)"),
    ("terrain", "tp01m6.pak", "tp012gr6.m16", True, "tp01 L0 (0-50 m) 256x256; tp*6 hold separate LOD tiles, not mip chains (see src/terrain/manifest.csv by U4)"),
    ("terrain", "tp05m6.pak", "tp052dr6.m16", True, "tp05 L0 256x256"),
    ("terrain", "tp18m6.pak", "tp182sw6.m16", True, "tp18 L0 256x256"),
    ("world_object", "bcxwhs56.pak", "cx_1bdf5.m16", False, "building facade 128x128 (small text)"),
    ("world_object", "bcgargc6.pak", "cg_1fn_1.m16", False, "fence 64x64, 62% transparent (thin alpha bars)"),
    ("world_object", "gtktank6.pak", "gtktl_.m16", False, "tank side 128x64"),
    ("dash", "zdash101.pak", "zdash101.vqm", False, "training car lower dash, VQM; codebook VPIT.CBK so decoded with vpit.act. 60% index 0xFF incl. speckle inside the gauges: in-game it overlays another layer, or 0xFF is not pure colourkey here (open question)"),
    ("dash", "zhr45101.m16", None, False, "cockpit hand-on-shifter overlay 256x256, alpha"),
    ("dash", "zswls101.m16", None, False, "cockpit steering wheel overlay 256x128, alpha"),
    ("shell_ui", "p01load.pcx", None, False, "mission load screen 640x480"),
    ("shell_ui", "b01load.pcx", None, False, "load screen 640x480"),
    ("shell_ui", "GAME:loadgame.pcx", None, False, "shell load-game screen 640x480 (game folder, not ZFS)"),
    ("decal", "aobilbb6.pak", "ao_1sg_b.m16", False, "billboard, dense text (stored flipped)"),
    ("decal", "aobilb86.pak", "ao_1sg_8.m16", False, "billboard Texas, text + map (stored flipped)"),
    ("decal", "bcxwhs56.pak", "cx_1sg15.m16", False, "sign 'WELCOME TO ...', thin text (stored flipped)"),
]

FIELDS = ["file", "mask", "class", "source_format", "palette_source", "native_size", "native_w", "native_h",
          "has_alpha", "tiles", "origin", "notes"]


def pak_member(extract, pak, member):
    pix = open(os.path.join(extract, pak[:-4] + ".pix")).read().split()
    data = open(os.path.join(extract, pak), "rb").read()
    it = iter(pix[1:])
    for n in it:
        off, ln = int(next(it)), int(next(it))
        if n.lower() == member:
            return data[off:off + ln]
    raise KeyError(f"{member} not in {pak}")


def decode(entry, extract, game):
    cls, src, member, wrap, note = entry
    if src.startswith("GAME:"):
        path = os.path.join(game, src[5:])
        im = Image.open(path).convert("RGBA")
        return im, "PCX", "PCX embedded 256-colour palette"
    if src.lower().endswith(".pcx"):
        im = Image.open(os.path.join(extract, src)).convert("RGBA")
        return im, "PCX", "PCX embedded 256-colour palette"
    raw = open(os.path.join(extract, src), "rb").read() if member is None else pak_member(extract, src, member)
    name = member or src
    if name.endswith(".m16"):
        w, h, _flags, rgba = i76img.decode_m16(raw)
        return Image.frombytes("RGBA", (w, h), rgba), "M16", "local RGB565 (in tile)"
    if name.endswith(".vqm"):
        cbk = raw[8:20].split(b"\0")[0].decode().lower()  # VPIT.CBK -> vpit.act
        act = os.path.splitext(cbk)[0] + ".act"
        if not os.path.exists(os.path.join(extract, act)):
            act = "t01.act"
        pal = i76img.read_act(os.path.join(extract, act))
        w, h, rgba = i76img.decode_vqm(raw, pal, extract)
        return Image.frombytes("RGBA", (w, h), rgba), "VQM", act + " (matches the codebook name)"
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=r"C:\Users\james\i76-upscale-work")
    ap.add_argument("--extract", default=None, help="extracted I76.ZFS (default WORK/extract)")
    ap.add_argument("--game", default=r"C:\Users\james\i76-uncap-lab\game", help="read-only, for loose PCX")
    a = ap.parse_args()
    extract = a.extract or os.path.join(a.work, "extract")
    rows, thumbs = [], []
    for e in BENCH:
        cls, src, member, wrap, note = e
        im, fmt, palsrc = decode(e, extract, a.game)
        name = os.path.splitext(member or src.split(":")[-1])[0].lower()
        d = os.path.join(a.work, "src", cls)
        os.makedirs(d, exist_ok=True)
        alpha = im.getchannel("A")
        has_alpha = alpha.getextrema()[0] < 255
        im.convert("RGB").save(os.path.join(d, name + ".png"))
        alpha.save(os.path.join(d, name + ".mask.png"))
        rows.append({"file": f"src/{cls}/{name}.png", "mask": f"src/{cls}/{name}.mask.png", "class": cls,
                     "source_format": fmt, "palette_source": palsrc, "native_size": f"{im.width}x{im.height}",
                     "native_w": im.width, "native_h": im.height, "has_alpha": int(has_alpha),
                     "tiles": "wrap" if wrap else "none",
                     "origin": f"{src}:{member}" if member else src, "notes": note})
        thumbs.append((f"{cls}/{name} {im.width}x{im.height}", im))
        print(f"{cls:14s} {name:10s} {im.width}x{im.height} {fmt} alpha={int(has_alpha)}")
    with open(os.path.join(a.work, "src", "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    contact(thumbs, os.path.join(a.work, "src", "contact_originals.png"))


def contact(thumbs, out, scale=4, maxw=1024):
    """Rows of tiles at `scale`x nearest-neighbour (PCX capped at maxw wide), magenta behind alpha."""
    placed, x, y, rowh, W = [], 0, 0, 0, 2600
    for label, im in thumbs:
        s = scale if im.width * scale <= maxw else max(1, maxw // im.width)
        tw, th = im.width * s, im.height * s + 14
        if x + tw > W:
            x, y, rowh = 0, y + rowh + 6, 0
        placed.append((label, im, s, x, y))
        x += tw + 6
        rowh = max(rowh, th)
    sheet = Image.new("RGB", (W, y + rowh), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    for label, im, s, x, y in placed:
        bg = Image.new("RGBA", im.size, (255, 0, 255, 255))
        bg.alpha_composite(im)
        sheet.paste(bg.convert("RGB").resize((im.width * s, im.height * s), Image.NEAREST), (x, y + 14))
        dr.text((x + 2, y + 1), f"{label} ({s}x)", fill=(255, 255, 255))
    sheet.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
