#!/usr/bin/env python3
"""Decode Interstate '76 image formats to PNG (and back - see encode_map).

Formats (verified against game data; layouts match Open76's parsers):
  .ACT  256*3 RGB bytes - palette.
  .MAP  u32 w | u32 h | w*h palette indices. Index 0xFF = transparent.
  .CBK  u32 count? | count * 16-byte blocks (4x4 palette indices) - VQM codebook.
  .VQM  u32 w | u32 h | char[12] cbk-name | u32 unk | u16[] block stream:
        MSB clear -> 16 indices from codebook block (index*16), MSB set -> low byte
        is a solid palette index for the whole 4x4 block. Blocks tile left-to-right,
        top-to-bottom in 4px steps.
  .PIX  text manifest: count, then "NAME.vqm offset length" lines into the matching .PAK.
  .PAK  concatenation of the VQMs the .PIX lists.
  .M16  hardware-renderer texture (the *6.pak sets, e.g. pirana16.pak; -glide mode):
        u32 w | u32 h|flags<<24 | u8[w*h] indices (row-major; 0xFF = transparent) |
        u32 paletteCount | u16[paletteCount] LOCAL palette in RGB565 LE.
        Cracked 2026-07-09 by cross-checking leprcn16 vs leprcn1m (avg diff 7.75 =
        565 quantization); count is 255 max because 0xFF is the transparency index.

Usage:
  i76img.py decode FILE[.map|.vqm|.pak] PALETTE.act OUT.png [--cbk-dir DIR]
  i76img.py palette PALETTE.act OUT.png            # visualize a palette
"""
import struct, sys, os

def read_act(path):
    d = open(path, "rb").read()
    assert len(d) >= 768, f"{path}: not an ACT palette"
    return [tuple(d[i*3:i*3+3]) for i in range(256)]

def encode_map(indices, w, h):
    """Inverse of decode_map: raw u32 w, u32 h, then w*h palette-index bytes - no
    VQM tiling/codebook. `indices` from quantize_to_palette (0xFF = transparent)."""
    return struct.pack("<2I", w, h) + bytes(indices)

def decode_map(d, pal):
    w, h = struct.unpack_from("<2I", d, 0)
    px = d[8:8 + w*h]
    rgba = bytearray()
    for i in px:
        r, g, b = pal[i]
        rgba += bytes((r, g, b, 0 if i == 0xFF else 255))
    return w, h, bytes(rgba)

def decode_vqm(d, pal, cbk_dir):
    w, h, = struct.unpack_from("<2I", d, 0)
    cbk_name = d[8:20].split(b"\0")[0].decode().lower()
    cbk = open(os.path.join(cbk_dir, cbk_name), "rb").read()
    stream = d[24:]
    out = bytearray(w * h)  # palette indices
    bw = (w + 3) // 4
    n_blocks = bw * ((h + 3) // 4)
    for bi in range(min(n_blocks, len(stream) // 2)):
        (idx,) = struct.unpack_from("<H", stream, bi * 2)
        bx, by = (bi % bw) * 4, (bi // bw) * 4
        if idx & 0x8000:
            block = bytes([idx & 0xFF]) * 16
        else:
            off = 4 + idx * 16
            block = cbk[off:off + 16]
        for r in range(4):
            for c in range(4):
                x, y = bx + c, by + r
                if x < w and y < h:
                    out[y * w + x] = block[r * 4 + c]
    rgba = bytearray()
    for i in out:
        r, g, b = pal[i]
        rgba += bytes((r, g, b, 0 if i == 0xFF else 255))
    return w, h, bytes(rgba)

def decode_m16(d):
    """M16 -> (w, h, flags, rgba). Colors from the tile's embedded RGB565 palette."""
    w, h_raw = struct.unpack_from("<2I", d, 0)
    h, flags = h_raw & 0xFFFFFF, h_raw >> 24
    px = d[8:8 + w*h]
    count = struct.unpack_from("<I", d, 8 + w*h)[0]
    p16 = struct.unpack_from(f"<{count}H", d, 12 + w*h)
    rgba = bytearray()
    for i in px:
        if i == 0xFF and i >= count:
            rgba += b"\0\0\0\0"
        else:
            c = p16[i] if i < count else 0
            rgba += bytes(((c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63,
                           (c & 31) * 255 // 31, 255))
    return w, h, flags, bytes(rgba)

def encode_m16(rgba, w, h, flags=0):
    """RGBA -> M16 bytes with a per-tile RGB565 palette (max 255 colors + 0xFF alpha).
    Colors are median-cut quantized to 255 if needed (PIL)."""
    from PIL import Image
    im = Image.frombytes("RGBA", (w, h), bytes(rgba))
    alpha = im.getchannel("A")
    rgb = im.convert("RGB")
    # collect unique colors; quantize only if over budget
    colors = rgb.getcolors(maxcolors=1 << 24)
    if len(colors) > 255:
        rgb = rgb.quantize(colors=255, method=Image.MEDIANCUT).convert("RGB")
    pal565, lut = [], {}
    out = bytearray(w * h)
    data = rgb.tobytes()
    amask = alpha.tobytes()
    for p in range(w * h):
        if amask[p] < 128:
            out[p] = 0xFF
            continue
        r, g, b = data[p*3:p*3+3]
        # round-to-nearest so decode(encode(x)) == x for 565-born colors
        c = (((r * 31 + 127) // 255) << 11) | (((g * 63 + 127) // 255) << 5) | ((b * 31 + 127) // 255)
        i = lut.get(c)
        if i is None:
            if len(pal565) >= 255:
                i = min(range(len(pal565)), key=lambda j: abs((pal565[j] >> 11) - (c >> 11)) +
                        abs((pal565[j] >> 5 & 63) - (c >> 5 & 63)) + abs((pal565[j] & 31) - (c & 31)))
            else:
                i = len(pal565); pal565.append(c)
            lut[c] = i
        out[p] = i
    return (struct.pack("<2I", w, h | (flags << 24)) + bytes(out)
            + struct.pack("<I", len(pal565)) + struct.pack(f"<{len(pal565)}H", *pal565))

def decode_pak(pak_path, pal, cbk_dir):
    """Decode all VQM tiles in a PAK using its .PIX manifest; returns list of (name,w,h,rgba)."""
    pix_path = os.path.splitext(pak_path)[0] + ".pix"
    lines = open(pix_path).read().split()
    # format: count, then triples NAME offset length
    tiles = []
    d = open(pak_path, "rb").read()
    it = iter(lines[1:])
    for name in it:
        off, ln = int(next(it)), int(next(it))
        if name.lower().endswith(".m16"):
            w, h, _flags, rgba = decode_m16(d[off:off + ln])
        else:
            w, h, rgba = decode_vqm(d[off:off + ln], pal, cbk_dir)
        tiles.append((name, w, h, rgba))
    return tiles

def write_png(path, w, h, rgba):
    try:
        from PIL import Image
        Image.frombytes("RGBA", (w, h), bytes(rgba)).save(path)
    except ImportError:
        import zlib
        raw = b"".join(b"\0" + rgba[y*w*4:(y+1)*w*4] for y in range(h))
        def chunk(t, data):
            c = t + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">2I5B", w, h, 8, 6, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(raw))
               + chunk(b"IEND", b""))
        open(path, "wb").write(png)

def quantize_to_palette(img_rgba, w, h, pal):
    """RGBA bytes -> palette indices (exact match fast path, else nearest by RGB distance).
    Fully transparent pixels -> 0xFF."""
    lut = {}
    for i, (r, g, b) in enumerate(pal[:255]):  # 0xFF reserved for transparency
        lut.setdefault((r, g, b), i)
    out = bytearray(w * h)
    for p in range(w * h):
        r, g, b, a = img_rgba[p*4:p*4+4]
        if a < 128:
            out[p] = 0xFF; continue
        hit = lut.get((r, g, b))
        if hit is None:
            hit = min(range(255), key=lambda i: (pal[i][0]-r)**2 + (pal[i][1]-g)**2 + (pal[i][2]-b)**2)
            lut[(r, g, b)] = hit
        out[p] = hit
    return bytes(out)

def encode_vqm(indices, w, h, cbk_name, codebook):
    """indices -> VQM bytes; appends new 4x4 blocks to `codebook` (a dict block->id + list)."""
    blocks, order = codebook
    stream = bytearray()
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            blk = bytes(indices[min(by+r, h-1)*w + min(bx+c, w-1)] for r in range(4) for c in range(4))
            if len(set(blk)) == 1:
                stream += struct.pack("<H", 0x8000 | blk[0])
            else:
                bid = blocks.get(blk)
                if bid is None:
                    bid = len(order)
                    if bid >= 0x8000:
                        raise ValueError("codebook overflow (>32767 blocks)")
                    blocks[blk] = bid; order.append(blk)
                stream += struct.pack("<H", bid)
    hdr = struct.pack("<2I", w, h) + cbk_name.upper().encode().ljust(12, b"\0") + struct.pack("<I", 256)
    return hdr + bytes(stream)

def cmd_makepak(argv):
    """makepak OUTBASE PALETTE.act CBKNAME.cbk TILE1.png NAME1.vqm [TILE2.png NAME2.vqm ...]
    Writes OUTBASE.pak, OUTBASE.pix and CBKNAME.cbk (in OUTBASE's directory)."""
    outbase, act, cbk_name = argv[0], argv[1], argv[2]
    from PIL import Image
    pal = read_act(act)
    codebook = ({}, [])
    parts, manifest = [], []
    pairs = list(zip(argv[3::2], argv[4::2]))
    off = 0
    for png, vqm_name in pairs:
        im = Image.open(png).convert("RGBA")
        w, h = im.size
        idx = quantize_to_palette(im.tobytes(), w, h, pal)
        v = encode_vqm(idx, w, h, cbk_name, codebook)
        parts.append(v); manifest.append((vqm_name, off, len(v))); off += len(v)
    open(outbase + ".pak", "wb").write(b"".join(parts))
    with open(outbase + ".pix", "w", newline="") as f:
        f.write(f"{len(manifest)}\r\n")
        for name, o, l in manifest:
            f.write(f"{name.upper()} {o} {l}\r\n")
    blocks_blob = b"".join(codebook[1])
    cbk_path = os.path.join(os.path.dirname(outbase) or ".", cbk_name.lower())
    with open(cbk_path, "wb") as f:
        f.write(struct.pack("<I", len(codebook[1])) + blocks_blob)
    print(f"wrote {outbase}.pak/.pix + {cbk_path} ({len(codebook[1])} codebook blocks)")

def main():
    cmd = sys.argv[1]
    if cmd == "makepak":
        cmd_makepak(sys.argv[2:]); return
    if cmd == "palette":
        pal = read_act(sys.argv[2])
        rgba = bytearray()
        for y in range(16):
            for _ in range(16):  # 16px tall rows of 16 swatches, 16px wide each
                pass
        w = h = 16 * 16
        buf = bytearray(w * h * 4)
        for i, (r, g, b) in enumerate(pal):
            sx, sy = (i % 16) * 16, (i // 16) * 16
            for y in range(16):
                for x in range(16):
                    o = ((sy + y) * w + sx + x) * 4
                    buf[o:o+4] = bytes((r, g, b, 255))
        write_png(sys.argv[3], w, h, bytes(buf))
        return
    if cmd == "decode":
        src, act, out = sys.argv[2], sys.argv[3], sys.argv[4]
        cbk_dir = sys.argv[6] if "--cbk-dir" in sys.argv else os.path.dirname(src)
        pal = read_act(act)
        ext = os.path.splitext(src)[1].lower()
        if ext == ".map":
            w, h, rgba = decode_map(open(src, "rb").read(), pal)
            write_png(out, w, h, rgba); print(f"{out}: {w}x{h}")
        elif ext == ".vqm":
            w, h, rgba = decode_vqm(open(src, "rb").read(), pal, cbk_dir)
            write_png(out, w, h, rgba); print(f"{out}: {w}x{h}")
        elif ext == ".pak":
            for name, w, h, rgba in decode_pak(src, pal, cbk_dir):
                p = out.replace(".png", f".{name.lower().replace('.vqm','')}.png")
                write_png(p, w, h, rgba); print(f"{p}: {w}x{h}")
        else:
            sys.exit(f"unsupported: {ext}")

if __name__ == "__main__":
    main()
