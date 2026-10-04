"""Terrain .ter: N tiles of 128x128 little-endian u16, row-major; value = height (low 12 bits) | flags (high 4 bits).

Measured (formats REPORT section 7): every .ter is N x 32,768 B; N equals the mission's ZMAP tile count; the
neighbour-smoothness test picks width 128. Third-party corroboration only for the bit split (0x0FFF height,
0x4000 tarmac / 0x6000 dirt), which is recorded as `proposed` semantics, not evidence.
"""
import array
import sys

TILE_W = 128
TILE_H = 128
TILE_BYTES = TILE_W * TILE_H * 2  # 32768


class TerError(Exception):
    pass


class Ter:
    def __init__(self, tiles, trailing=b""):
        self.tiles = tiles          # list of array('H') with 16384 values each
        self.trailing = trailing    # bytes after the last whole tile (none in the corpus)

    @property
    def n_tiles(self):
        return len(self.tiles)

    def height(self, tile, x, y):
        return self.tiles[tile][y * TILE_W + x] & 0x0FFF

    def flags(self, tile, x, y):
        return self.tiles[tile][y * TILE_W + x] >> 12


def parse(data, strict=True):
    n, rem = divmod(len(data), TILE_BYTES)
    if strict and rem:
        raise TerError("size %d is not a multiple of %d" % (len(data), TILE_BYTES))
    tiles = []
    for i in range(n):
        a = array.array("H")
        a.frombytes(data[i * TILE_BYTES:(i + 1) * TILE_BYTES])
        if sys.byteorder != "little":
            a.byteswap()
        tiles.append(a)
    return Ter(tiles, data[n * TILE_BYTES:])


def serialise(t):
    out = bytearray()
    for a in t.tiles:
        if len(a) != TILE_W * TILE_H:
            raise TerError("tile has %d values, expected %d" % (len(a), TILE_W * TILE_H))
        b = a
        if sys.byteorder != "little":
            b = array.array("H", a); b.byteswap()
        out += b.tobytes()
    out += t.trailing
    return bytes(out)
