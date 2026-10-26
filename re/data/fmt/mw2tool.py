#!/usr/bin/env python3
r"""mw2tool.py - list, extract and repack DATABASE.MW2 (format: mw2db.py).

    python data\fmt\mw2tool.py list    <DATABASE.MW2>
    python data\fmt\mw2tool.py extract <DATABASE.MW2> <outdir>            (default outdir: data\out\mw2db)
    python data\fmt\mw2tool.py repack  <outdir\manifest.json> <new.MW2>   (default: <outdir>\DATABASE.MW2)

extract writes one entry per member plus manifest.json:
    NNN_0xHH_bg.png          background: 8-bit palettised PNG carrying the member's own 256-colour palette
    NNN_0xHH_shp\fNNN.png    one PNG per sprite frame, canvas-sized, palettised, index 255 = transparent
    NNN_0xHH_font.png/.json  glyph sheet (one cell per glyph) + metrics (widths)
    NNN_0xHH.wav / .txt      sound and credits text, raw bytes
    palettes\pal_0xHH.act    each distinct background palette (256 x RGB), named after its first user
repack rebuilds every member from those files (PNG -> PCX RLE -> LZSS, PNG -> shape run lists, sheet -> glyphs),
in manifest order, and reports whether the result is byte-identical to the file the manifest was extracted from.
Nothing is copied from the original, so an untouched extraction that repacks identically proves the encoders.

Editing: keep PNGs palettised to stay exact. An RGB/RGBA PNG is accepted and mapped to the nearest palette colour
(alpha < 128 = transparent for sprites and fonts); that path is lossy by nature. A sprite may grow beyond its
stored box (the box is widened to fit) but not beyond its PNG canvas unless "canvas" in the manifest is changed
too. Members can be reordered, added or dropped by editing manifest "members" (ids follow the order).
The tool never writes into a folder that holds i76.exe or i76shell.dll.
"""
import os, sys, json, hashlib, struct, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mw2db  # noqa: E402

MAP = os.path.dirname(os.path.dirname(HERE))
DEFAULT_OUT = os.path.join(MAP, "data", "out", "mw2db")
SPRITE_PALETTE = {0x40: 0x1b}      # sprite item -> background item whose palette it is drawn with (default: the common one)
TYPE = {"pcx": "background", "shp": "shapes", "fnt": "font", "wav": "wav", "text": "text", "raw": "raw"}
TRANSPARENT = 255


def md5(b):
    return hashlib.md5(b).hexdigest()


def _pil():
    from PIL import Image
    return Image


# ---- PNG helpers -----------------------------------------------------------------------------------------------
def save_p(path, w, h, pixels, palette, transparent=None):
    Image = _pil()
    im = Image.frombytes("P", (w, h), bytes(pixels))
    im.putpalette(palette)
    if transparent is None:
        im.save(path, optimize=False)
    else:
        im.save(path, optimize=False, transparency=transparent)


def load_indices(path, palette, sprite):
    """-> (w, h, bytes of palette indices, palette or None). Palettised PNGs are taken as they are."""
    Image = _pil()
    im = Image.open(path)
    w, h = im.size
    if im.mode == "P":
        pal = bytes(im.getpalette() or b"")[:768]
        return w, h, im.tobytes(), pal + bytes(768 - len(pal))
    rgba = im.convert("RGBA")
    palim = Image.new("P", (1, 1))
    pal = bytearray(palette)
    if sprite:
        pal[765:768] = pal[0:3]            # keep the quantiser off the transparent index
    palim.putpalette(bytes(pal))
    q = bytearray(rgba.convert("RGB").quantize(palette=palim, dither=Image.Dither.NONE).tobytes())
    if sprite:
        alpha = rgba.getchannel("A").tobytes()
        for i in range(len(q)):
            if alpha[i] < 128:
                q[i] = TRANSPARENT
            elif q[i] == TRANSPARENT:
                q[i] = 0
    return w, h, bytes(q), None


# ---- extract ---------------------------------------------------------------------------------------------------
def describe(m):
    if m.kind == "pcx":
        return "%dx%d 8-bit, %d dpi" % (m.width, m.height, m.dpi[0])
    if m.kind == "shp":
        sizes = sorted({(f.canvas_w1 + 1, f.canvas_h1 + 1) for f in m.frames})
        return "%d frames, canvas %s" % (len(m.frames), ", ".join("%dx%d" % s for s in sizes[:4]) + (" ..." if len(sizes) > 4 else ""))
    if m.kind == "fnt":
        return "%d glyphs, height %d, %d bpp, max width %d" % (len(m.glyphs), m.height, m.bpp, max(w for w, _ in m.glyphs))
    if m.kind == "wav":
        i = mw2db.wav_info(m.data)
        return "%s %d Hz %d-bit %d ch, %d data bytes" % (i.get("tag"), i.get("rate", 0), i.get("bits", 0), i.get("channels", 0), i.get("data_bytes", 0))
    if m.kind == "text":
        return "%d lines" % m.data.count(b"\n")
    return ""


def cmd_list(a):
    data = open(a.db, "rb").read()
    offs, blobs, _ = mw2db.split(data)
    print("%s: %d bytes, %d members, md5 %s" % (a.db, len(data), len(blobs), md5(data)))
    for i, (o, b) in enumerate(zip(offs, blobs), 1):
        m = mw2db.member_parse(b)
        use = mw2db.USES.get(i, ("", ""))[0]
        print("%3d 0x%02x  off 0x%07x  size %8d  %-10s %-44s %s" % (i, i, o, len(b), TYPE[m.kind], describe(m), use))
    return 0


def font_sheet(m):
    n = len(m.glyphs)
    cols = 16 if n <= 256 else 64
    cw = 8 * max(max(1, (w + 7) >> 3) for w, _ in m.glyphs) if m.bpp == 1 else max(1, max(w for w, _ in m.glyphs))
    ch = m.height
    rows = (n + cols - 1) // cols
    W, H = cols * cw, rows * ch
    buf = bytearray([0 if m.bpp == 1 else TRANSPARENT]) * (W * H)
    for g, (w, px) in enumerate(m.glyphs):
        gx, gy = (g % cols) * cw, (g // cols) * ch
        if m.bpp == 8:
            for y in range(ch if w else 0):
                buf[(gy + y) * W + gx:(gy + y) * W + gx + w] = px[y * w:(y + 1) * w]
        else:
            bpr = max(1, (w + 7) >> 3)
            for y in range(ch):
                for k in range(bpr):
                    v = px[y * bpr + k]
                    for bit in range(8):
                        if v & (0x80 >> bit):
                            buf[(gy + y) * W + gx + 8 * k + bit] = 1
    return cols, cw, ch, W, H, buf


def cmd_extract(a):
    out = os.path.abspath(a.out)
    data = open(a.db, "rb").read()
    offs, blobs, gap = mw2db.split(data)
    members = [mw2db.member_parse(b) for b in blobs]
    os.makedirs(os.path.join(out, "palettes"), exist_ok=True)
    pal_file = {}; pal_of = {}; count = {}
    for i, m in enumerate(members, 1):
        if m.kind == "pcx":
            if m.palette not in pal_file:
                pal_file[m.palette] = "palettes/pal_0x%02x.act" % i
                open(os.path.join(out, pal_file[m.palette]), "wb").write(m.palette)
            pal_of[i] = m.palette
            count[m.palette] = count.get(m.palette, 0) + 1
    common = max(count, key=count.get) if count else bytes(768)
    man = {"format": "i76-mw2db-manifest/1",
           "source": {"path": os.path.abspath(a.db), "size": len(data), "md5": md5(data)},
           "count": len(blobs), "head_gap_hex": gap.hex(), "members": []}
    for i, (o, b, m) in enumerate(zip(offs, blobs, members), 1):
        stem = "%03d_0x%02x" % (i, i)
        use, cite = mw2db.USES.get(i, ("", ""))
        e = {"index": i, "id": "0x%02x" % i, "offset": o, "size": len(b), "md5": md5(b), "type": TYPE[m.kind],
             "used_by": use or None, "citation": cite or None}
        if m.kind == "pcx":
            if m.bytes_per_line != m.width:
                raise mw2db.Mw2Error("item %d: PCX line padding is not representable as a PNG" % i)
            e.update(file=stem + "_bg.png", width=m.width, height=m.height, dpi=list(m.dpi), palette=pal_file[m.palette],
                     unpacked_size=struct.unpack_from("<I", b, 0)[0], pcx_header_hex=m.header.hex())
            save_p(os.path.join(out, e["file"]), m.width, m.height, b"".join(m.rows), m.palette)
        elif m.kind == "shp":
            pal = pal_of.get(SPRITE_PALETTE.get(i), common)
            d = stem + "_shp"
            os.makedirs(os.path.join(out, d), exist_ok=True)
            e.update(dir=d, palette=pal_file.get(pal), transparent_index=TRANSPARENT, frames=[])
            for k, f in enumerate(m.frames):
                x0, y0, x1, y1 = f.box
                W, H = max(f.canvas_w1, x1) + 1, max(f.canvas_h1, y1) + 1
                buf = bytearray([TRANSPARENT]) * (W * H)
                if x0 < 0 or y0 < 0:
                    raise mw2db.Mw2Error("item %d frame %d: negative box origin" % (i, k))
                for y, row in enumerate(f.rows):
                    base = (y0 + y) * W + x0
                    for x, c in enumerate(row):
                        if c is not None:
                            if c == TRANSPARENT or x0 + x >= W:
                                raise mw2db.Mw2Error("item %d frame %d: pixel not representable" % (i, k))
                            buf[base + x] = c
                fe = {"file": "%s/f%03d.png" % (d, k), "canvas": [f.canvas_w1 + 1, f.canvas_h1 + 1], "box": list(f.box)}
                if f.w4 or f.w6:
                    fe["words_4_6"] = [f.w4, f.w6]
                if m.table_aux[k]:
                    fe["table_aux"] = m.table_aux[k]
                e["frames"].append(fe)
                save_p(os.path.join(out, fe["file"]), W, H, buf, pal, TRANSPARENT)
            e["frame_count"] = len(m.frames)
        elif m.kind == "fnt":
            cols, cw, ch, W, H, buf = font_sheet(m)
            e.update(file=stem + "_font.png", metrics=stem + "_font.json", glyphs=len(m.glyphs), height=m.height, bpp=m.bpp,
                     flag=m.flag, sheet={"cols": cols, "cell": [cw, ch]}, max_width=max(w for w, _ in m.glyphs))
            if m.bpp == 8:
                e.update(palette=pal_file.get(common), transparent_index=TRANSPARENT)
                save_p(os.path.join(out, e["file"]), W, H, buf, common, TRANSPARENT)
            else:
                save_p(os.path.join(out, e["file"]), W, H, buf, bytes([0, 0, 0, 255, 255, 255]) + bytes(762))
            json.dump({"height": m.height, "widths": [w for w, _ in m.glyphs]},
                      open(os.path.join(out, e["metrics"]), "w", encoding="utf-8", newline="\n"))
        else:
            ext = {"wav": ".wav", "text": "_credits.txt", "raw": ".bin"}[m.kind]
            e.update(file=stem + ext)
            if m.kind == "wav":
                e.update(wav=mw2db.wav_info(m.data))
            open(os.path.join(out, e["file"]), "wb").write(m.data)
        e["info"] = describe(m)
        man["members"].append(e)
    p = os.path.join(out, "manifest.json")
    json.dump(man, open(p, "w", encoding="utf-8", newline="\n"), indent=1)
    kinds = {}
    for e in man["members"]:
        kinds[e["type"]] = kinds.get(e["type"], 0) + 1
    print("extracted %d members to %s: %s" % (len(blobs), out, ", ".join("%d %s" % (n, k) for k, n in kinds.items())))
    print("palettes: %d distinct; %d backgrounds share %s" % (len(pal_file), count.get(common, 0), pal_file.get(common)))
    return 0


# ---- repack ----------------------------------------------------------------------------------------------------
def build_member(root, e):
    t = e["type"]
    pal = open(os.path.join(root, e["palette"]), "rb").read() if e.get("palette") else bytes(768)
    if t == "background":
        w, h, px, png_pal = load_indices(os.path.join(root, e["file"]), pal, False)
        hdr = bytearray(bytes.fromhex(e["pcx_header_hex"]))
        x0, y0 = struct.unpack_from("<2H", hdr, 4)
        struct.pack_into("<2H", hdr, 8, x0 + w - 1, y0 + h - 1)
        struct.pack_into("<H", hdr, 66, w)
        return mw2db.member_emit(mw2db.Pcx(bytes(hdr), [px[y * w:(y + 1) * w] for y in range(h)], png_pal or pal))
    if t == "shapes":
        frames = []; aux = []
        for fe in e["frames"]:
            W, H, px, _ = load_indices(os.path.join(root, fe["file"]), pal, True)
            x0, y0, x1, y1 = fe["box"]
            xs = [x for y in range(H) for x in range(W) if px[y * W + x] != TRANSPARENT and not (x0 <= x <= x1 and y0 <= y <= y1)]
            if xs:      # art outside the stored box: widen the box to the canvas content
                ys = [y for y in range(H) if any(px[y * W + x] != TRANSPARENT for x in range(W))]
                cols = [x for x in range(W) if any(px[y * W + x] != TRANSPARENT for y in range(H))]
                x0, y0, x1, y1 = min(x0, cols[0]), min(y0, ys[0]), max(x1, cols[-1]), max(y1, ys[-1])
            if x1 >= W or y1 >= H:
                raise mw2db.Mw2Error("%s: box %s exceeds the %dx%d PNG" % (fe["file"], fe["box"], W, H))
            rows = [[None if c == TRANSPARENT else c for c in px[y * W + x0:y * W + x1 + 1]] for y in range(y0, y1 + 1)]
            for r in rows:
                while r and r[-1] is None:
                    r.pop()
            w4, w6 = fe.get("words_4_6", [0, 0])
            frames.append(mw2db.Frame(fe["canvas"][1] - 1, fe["canvas"][0] - 1, w4, w6, (x0, y0, x1, y1), rows))
            aux.append(fe.get("table_aux", 0))
        return mw2db.member_emit(mw2db.Shp(frames, aux))
    if t == "font":
        met = json.load(open(os.path.join(root, e["metrics"]), encoding="utf-8"))
        h = met["height"]; cols = e["sheet"]["cols"]; cw, ch = e["sheet"]["cell"]
        if e["bpp"] == 1:
            Image = _pil()
            im = Image.open(os.path.join(root, e["file"]))
            W, H = im.size
            px = im.tobytes() if im.mode == "P" else bytes(1 if c >= 128 else 0 for c in im.convert("L").tobytes())
        else:
            W, H, px, _ = load_indices(os.path.join(root, e["file"]), pal, True)
        glyphs = []
        for g, w in enumerate(met["widths"]):
            gx, gy = (g % cols) * cw, (g // cols) * ch
            if e["bpp"] == 8:
                if w > cw:
                    raise mw2db.Mw2Error("glyph %d width %d exceeds the sheet cell %d" % (g, w, cw))
                glyphs.append((w, b"".join(px[(gy + y) * W + gx:(gy + y) * W + gx + w] for y in range(h))))
            else:
                bpr = max(1, (w + 7) >> 3)
                o = bytearray()
                for y in range(h):
                    base = (gy + y) * W + gx
                    for k in range(bpr):
                        v = 0
                        for bit in range(8):
                            if px[base + 8 * k + bit]:
                                v |= 0x80 >> bit
                        o.append(v)
                glyphs.append((w, bytes(o)))
        return mw2db.member_emit(mw2db.Fnt(h, e["flag"], e["bpp"], glyphs))
    return open(os.path.join(root, e["file"]), "rb").read()


def is_game_folder(d):
    try:
        names = {n.lower() for n in os.listdir(d)}
    except OSError:
        return False
    return bool(names & {"i76.exe", "i76shell.dll", "nitro.exe"})


def cmd_repack(a):
    root = os.path.dirname(os.path.abspath(a.manifest))
    man = json.load(open(a.manifest, encoding="utf-8"))
    out = os.path.abspath(a.out or os.path.join(root, "DATABASE.MW2"))
    if is_game_folder(os.path.dirname(out)):
        print("refusing to write into a game folder: %s (write elsewhere and copy it yourself)" % os.path.dirname(out))
        return 2
    blobs = []; changed = []
    for k, e in enumerate(man["members"], 1):
        b = build_member(root, e)
        blobs.append(b)
        if md5(b) != e.get("md5"):
            changed.append("item %d (was %s, %s): %d -> %d bytes" % (k, e.get("id"), e["type"], e.get("size", 0), len(b)))
    data = mw2db.join(blobs, bytes.fromhex(man.get("head_gap_hex", "")))
    tmp = out + ".tmp"
    open(tmp, "wb").write(data)
    os.replace(tmp, out)
    back = open(out, "rb").read()
    assert back == data, "read-back differs"
    mw2db.split(back)
    same = md5(data) == man["source"]["md5"] and len(data) == man["source"]["size"]
    print("wrote %s: %d bytes, %d members, md5 %s" % (out, len(data), len(blobs), md5(data)))
    for c in changed:
        print("  changed: " + c)
    print("byte-identical to the extracted source (%s): %s" % (man["source"]["md5"], "YES" if same else "NO"))
    return 0 if same or changed else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("db"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("extract"); p.add_argument("db"); p.add_argument("out", nargs="?", default=DEFAULT_OUT); p.set_defaults(fn=cmd_extract)
    p = sub.add_parser("repack"); p.add_argument("manifest"); p.add_argument("out", nargs="?"); p.set_defaults(fn=cmd_repack)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
