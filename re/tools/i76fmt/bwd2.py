"""BWD2 tagged-chunk container (.msn .lvl .vcf .vsf .sdf .vdf .wdf .gdf .xdf .vtf .cdf).

Layout (formats REPORT section 5, measured over every BWD2 file in the corpus):
  file header: 'BWD2', u32 header_size (8)
  chunk: char tag[4], u32 size (including the 8-byte chunk header), body[size - 8]
  first chunk 'REV\\0' (size 12, u32 revision); 'EXIT' chunks (size 8) close groups and may appear more than once
  at the top level (vmxmarx3.vcf: VCFC EXIT WEPNx5 EXIT), so EXIT is never treated as end-of-file.
  Nested groups: a chunk whose tag ends in 'DEF' (WDEF TDEF RDEF ODEF LDEF ADEF) holds its own chunk sequence
  starting with an xREV chunk and ending with EXIT; the parser nests only when the body walks exactly to its
  end and begins with a *REV tag, and serialise re-emits nested groups by recomputing sizes bottom-up.
The engine's walker (0x4b3db0, handler table records {tag, unk, handler @+8, flags @+0xC}) is the reference;
the exe string "Bad BWD revision for file %s" names the format. All offsets are class `file`.
"""
import struct

MAGIC = b"BWD2"


class Bwd2Error(Exception):
    pass


class Chunk:
    __slots__ = ("tag", "body", "children", "offset")

    def __init__(self, tag, body=b"", children=None, offset=None):
        self.tag = tag            # bytes[4]
        self.body = body          # bytes (leaf) - for a group this is the raw body kept for reference only
        self.children = children  # list[Chunk] or None for a leaf
        self.offset = offset      # file offset of the chunk header (class file)

    @property
    def tag_str(self):
        return self.tag.rstrip(b"\0").decode("latin1")

    @property
    def is_group(self):
        return self.children is not None

    def size(self):
        return 8 + (len(self.body) if not self.is_group else sum(c.size() for c in self.children))

    def find(self, tag):
        t = tag.encode("latin1").ljust(4, b"\0") if isinstance(tag, str) else tag
        return [c for c in (self.children or []) if c.tag == t]

    def __repr__(self):
        return "Chunk(%s, %d)" % (self.tag_str, self.size())


class Bwd2:
    def __init__(self, header_size=8, header_extra=b"", chunks=None, trailing=b""):
        self.header_size = header_size
        self.header_extra = header_extra  # bytes between offset 8 and header_size (none in the corpus)
        self.chunks = chunks or []
        self.trailing = trailing

    @property
    def revision(self):
        for c in self.chunks:
            if c.tag == b"REV\0" and len(c.body) >= 4:
                return struct.unpack_from("<I", c.body, 0)[0]
        return None

    def find(self, tag):
        t = tag.encode("latin1").ljust(4, b"\0") if isinstance(tag, str) else tag
        return [c for c in self.chunks if c.tag == t]

    def walk(self):
        """Depth-first (chunk, depth) generator."""
        def rec(cs, d):
            for c in cs:
                yield c, d
                if c.is_group:
                    for x in rec(c.children, d + 1):
                        yield x
        return rec(self.chunks, 0)


def _walk_flat(data, base, strict):
    """Split data into (tag, body, offset) triples. Returns (list, consumed)."""
    out = []
    p = 0
    n = len(data)
    while p + 8 <= n:
        tag = data[p:p + 4]
        size = struct.unpack_from("<I", data, p + 4)[0]
        if size < 8 or p + size > n:
            if strict:
                raise Bwd2Error("bad chunk size %d at file offset 0x%x (tag %r)" % (size, base + p, tag))
            break
        out.append((tag, data[p + 8:p + size], base + p))
        p += size
    return out, p


def _nest(tag, body, base):
    """Decide whether body is a chunk group: tag ends in DEF, body walks exactly, first tag ends in REV."""
    if not tag.endswith(b"DEF") or len(body) < 8:
        return None
    try:
        items, consumed = _walk_flat(body, base + 8, strict=True)
    except Bwd2Error:
        return None
    if consumed != len(body) or not items or not items[0][0].endswith(b"REV"):
        return None
    return [_make(t, b, o) for t, b, o in items]


def _make(tag, body, off):
    kids = _nest(tag, body, off)
    return Chunk(tag, body, kids, off)


def parse(data, strict=True):
    if data[:4] != MAGIC:
        raise Bwd2Error("not a BWD2 file")
    hs = struct.unpack_from("<I", data, 4)[0]
    if hs < 8 or hs > len(data):
        raise Bwd2Error("bad header size %d" % hs)
    items, consumed = _walk_flat(data[hs:], hs, strict)
    doc = Bwd2(hs, data[8:hs], [_make(t, b, o) for t, b, o in items], data[hs + consumed:])
    return doc


def _emit(c, out):
    if c.is_group:
        start = len(out)
        out += c.tag + b"\0\0\0\0"
        for k in c.children:
            _emit(k, out)
        struct.pack_into("<I", out, start + 4, len(out) - start)
    else:
        out += c.tag + struct.pack("<I", 8 + len(c.body)) + c.body


def serialise(doc):
    out = bytearray(MAGIC + struct.pack("<I", doc.header_size) + doc.header_extra)
    for c in doc.chunks:
        _emit(c, out)
    out += doc.trailing
    return bytes(out)


# ---- convenience record views (best effort; the round trip never depends on these) ----------------------
def cstr(b):
    return b.split(b"\0")[0].decode("latin1")


VCFC_ARMOUR_OFF = 93   # body offset of the 8 x u32 armour block (file 0x79 in a rev-3 .vcf: 8 hdr + 12 REV + 8 VCFC hdr + 93)


def vcfc(body):
    """VCFC body (129 B in rev 3 .vcf): name[16], vdf[13], vtf[13], 3 u32, 3 x wheel[13] (front wdf, 'null', rear
    wdf), 8 u32 armour (integer tenths) at body+93 = file 0x79, u32 tail.

    p6-finalize: the earlier view read 4 wheel fields and armour at body+106 (fold-in L063: the fresh 4-wdf reading
    was wrong). Checked on vppt01.vcf (zfs_out; armour 8 x 600), and on the user's ADDON\\valepre4.orig / .vcf pair,
    whose only differing bytes are file offsets 121..152 (8 dwords, stride 4) = body+93. The round trip (gate R)
    never depends on this view."""
    d = {"name": cstr(body[0:16]), "vdf": cstr(body[16:29]), "vtf": cstr(body[29:42])}
    d["u32_3"] = list(struct.unpack_from("<III", body, 42))
    d["wheels"] = [cstr(body[54 + 13 * i:67 + 13 * i]) for i in range(3)]
    d["armour"] = list(struct.unpack_from("<8I", body, VCFC_ARMOUR_OFF)) if len(body) >= VCFC_ARMOUR_OFF + 32 else None
    d["tail"] = body[VCFC_ARMOUR_OFF + 32:]
    d["raw"] = body
    return d


def wepn(body):
    """WEPN body (17 B): u32 mount_index, gdf_name[13]."""
    return {"mount": struct.unpack_from("<I", body, 0)[0], "gdf": cstr(body[4:17]), "raw": body}


def obj(body):
    """ODEF/LDEF OBJ body (100 B): name[8], 9 floats rotation, 3 floats position, 44 B tail (u32 class @+92)."""
    return {"name": cstr(body[0:8]), "rot": list(struct.unpack_from("<9f", body, 8)),
            "pos": list(struct.unpack_from("<3f", body, 44)), "tail": body[56:100],
            "class": struct.unpack_from("<I", body, 92)[0] if len(body) >= 96 else None, "raw": body}


def rseg(body):
    """RSEG body: u32 type, u32 n, n x (left vec3, right vec3)."""
    t, n = struct.unpack_from("<II", body, 0)
    pts = [struct.unpack_from("<6f", body, 8 + 24 * i) for i in range(n)]
    return {"type": t, "n": n, "segments": pts, "raw": body}


def zmap(body):
    """ZMAP body: u8 tile_count then 80x80 u8 grid of tile indices (0xFF = void)."""
    return {"tile_count": body[0], "grid": body[1:6401], "raw": body}


def zone(body):
    """ZONE body: u8 0xFF, then the terrain file name."""
    return {"flag": body[0], "ter": cstr(body[1:]), "raw": body}
