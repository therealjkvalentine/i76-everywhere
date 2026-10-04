"""Bitmap font .fnt ("1." fonts; also DATABASE.MW2 entries 64-70).

Measured layout (formats REPORT section 9; base6x7.fnt 'A' width 5 height 7 -> 39 B glyph; base6x74 'A' width 9
-> 130 B): "1." 00 00, u32 glyph_count, u32 height, u32 transparent_index, glyph_count x u32 absolute file
offset, then glyphs in offset order: u32 width, u8[width * height] (0xFF = transparent).
The 1-bpp MW2 font (entry 64, 8896 glyphs) is not a loose file and is not modelled; a font whose glyphs are not
laid out contiguously in offset order fails parse (FntError) so gate R reports it instead of guessing.
"""
import struct

MAGIC = b"1.\0\0"


class FntError(Exception):
    pass


class Glyph:
    __slots__ = ("width", "pixels")

    def __init__(self, width, pixels):
        self.width = width; self.pixels = pixels


class Fnt:
    def __init__(self, height, transparent, glyphs, trailing=b""):
        self.height = height; self.transparent = transparent; self.glyphs = glyphs; self.trailing = trailing

    @property
    def count(self):
        return len(self.glyphs)


def parse(data):
    if data[:4] != MAGIC:
        raise FntError("bad magic %r" % data[:4])
    n, h, tr = struct.unpack_from("<III", data, 4)
    table = 16
    if table + 4 * n > len(data):
        raise FntError("offset table exceeds file")
    offs = struct.unpack_from("<%dI" % n, data, table)
    p = table + 4 * n
    glyphs = []
    for i, o in enumerate(offs):
        if o != p:
            raise FntError("glyph %d at 0x%x, expected contiguous 0x%x" % (i, o, p))
        if p + 4 > len(data):
            raise FntError("glyph %d header past EOF" % i)
        w = struct.unpack_from("<I", data, p)[0]
        px = data[p + 4:p + 4 + w * h]
        if len(px) != w * h:
            raise FntError("glyph %d pixels short" % i)
        glyphs.append(Glyph(w, px))
        p += 4 + w * h
    return Fnt(h, tr, glyphs, data[p:])


def serialise(f):
    n = len(f.glyphs)
    out = bytearray(MAGIC + struct.pack("<III", n, f.height, f.transparent))
    p = 16 + 4 * n
    offs = []
    for g in f.glyphs:
        offs.append(p)
        p += 4 + g.width * f.height
    out += struct.pack("<%dI" % n, *offs)
    for g in f.glyphs:
        if len(g.pixels) != g.width * f.height:
            raise FntError("glyph pixel count %d != %d" % (len(g.pixels), g.width * f.height))
        out += struct.pack("<I", g.width) + bytes(g.pixels)
    out += f.trailing
    return bytes(out)
