"""Indexed image sub-formats: .map (8-bit indexed), .vqm (vector-quantised 4x4 blocks) and .cbk (codebook).

Measured layouts (formats REPORT section 8, verified over the 154 + 321 .map, 101 + 6000 .vqm, 53 + 1 .cbk):
  .map  u32 w, u32 h, u8[w*h]        (153/154 archive files satisfy size = 8 + w*h; ADDON\\i2ayj_13.map is
                                      8,192 B with 128x64, i.e. 8 B short: the parser keeps whatever pixel
                                      bytes exist and serialise re-emits exactly them)
  .vqm  u32 w, u32 h, char cbk_name[12] (NUL-padded; 12-char names carry no NUL), u32 unk, u16[w*h/16] indices
  .cbk  u32 count, count x 16 B (4x4 8-bit tiles)
Any bytes beyond the modelled fields are kept as `trailing` so the round trip is exact and the excess is
reported, never silently dropped.
"""
import struct


class ImageError(Exception):
    pass


class MapImage:
    def __init__(self, w, h, pixels, trailing=b""):
        self.w = w; self.h = h; self.pixels = pixels; self.trailing = trailing

    @property
    def short_by(self):
        return self.w * self.h - len(self.pixels)


def parse_map(data):
    if len(data) < 8:
        raise ImageError("too short for a .map header")
    w, h = struct.unpack_from("<II", data, 0)
    n = w * h
    if n > (1 << 26):
        raise ImageError("implausible dimensions %dx%d" % (w, h))
    px = data[8:8 + n]
    return MapImage(w, h, px, data[8 + n:])


def serialise_map(m):
    return struct.pack("<II", m.w, m.h) + bytes(m.pixels) + m.trailing


class Vqm:
    def __init__(self, w, h, cbk_name, unk, indices, trailing=b""):
        self.w = w; self.h = h; self.cbk_name = cbk_name; self.unk = unk; self.indices = indices
        self.trailing = trailing

    @property
    def n_blocks(self):
        return (self.w * self.h) // 16


def parse_vqm(data):
    if len(data) < 8:
        raise ImageError("too short for a .vqm header")
    w, h = struct.unpack_from("<II", data, 0)
    # cbk name is a fixed 12-byte field (NUL-padded; a 12-character name such as ROADMAP2.CBK has no NUL):
    # measured by gate R on 2026-09-04, 51 of 101 archive .vqm are 8 + 12 + 4 + w*h/8 bytes with a 12-char name.
    # The recon REPORT's "NUL-terminated" reading was the 50 shorter-name files.
    name = data[8:20]
    p = 20
    if p + 4 > len(data):
        raise ImageError("missing u32 after codebook name")
    unk = struct.unpack_from("<I", data, p)[0]
    p += 4
    n = (w * h) // 16
    idx = data[p:p + 2 * n]
    if len(idx) != 2 * n:
        raise ImageError("index table short: %d of %d bytes" % (len(idx), 2 * n))
    return Vqm(w, h, name, unk, idx, data[p + 2 * n:])


def serialise_vqm(v):
    if len(v.cbk_name) != 12:
        raise ImageError("cbk_name must be exactly 12 bytes (NUL-padded)")
    return struct.pack("<II", v.w, v.h) + bytes(v.cbk_name) + struct.pack("<I", v.unk) + bytes(v.indices) + v.trailing


class Cbk:
    def __init__(self, tiles, trailing=b""):
        self.tiles = tiles  # bytes, 16 per tile
        self.trailing = trailing

    @property
    def count(self):
        return len(self.tiles) // 16


def parse_cbk(data):
    if len(data) < 4:
        raise ImageError("too short for a .cbk header")
    n = struct.unpack_from("<I", data, 0)[0]
    t = data[4:4 + 16 * n]
    if len(t) != 16 * n:
        raise ImageError("codebook short: %d of %d tiles" % (len(t) // 16, n))
    return Cbk(t, data[4 + 16 * n:])


def serialise_cbk(c):
    return struct.pack("<I", c.count) + bytes(c.tiles) + c.trailing


# generic entry points keyed by extension
PARSERS = {".map": (parse_map, serialise_map), ".vqm": (parse_vqm, serialise_vqm), ".cbk": (parse_cbk, serialise_cbk)}


def parse(data, ext):
    return PARSERS[ext.lower()][0](data)


def serialise(obj, ext):
    return PARSERS[ext.lower()][1](obj)
