"""ZFSF v1 archive (I76.ZFS): directory parse, payload decode, byte-exact serialise, stored-mode repack.

Layout (formats REPORT 2.1-2.2, measured on I76.ZFS, 55,535,506 B):
  header 28 B: 'ZFSF', u32 version (1), u32 name_len (16), u32 per_block (100), u32 n_files, u32 xor_key (0),
               u32 dir0 (0x1C)
  directory block: u32 next_block_offset, then per_block entries of 36 B:
               char name[16], u32 offset, u32 id, u32 size (in-archive), u32 timestamp, u32 flags
               flags = (uncompressed_size << 8) | method; method 0 stored, 2 LZO1X, 4 LZO1Y
  payloads follow each block in directory order: [block][100 payloads][block][100 payloads]...
The loader (0x4b9bd0) treats (flags & 6) == 0 as stored and returns the raw bytes, and XORs the output
dword-wise with xor_key when it is non-zero (zfs-lzo-refute section 2); entries with flags & 1 are skipped by
the loader (0x4b9800). Both are honoured here. All offsets are class `file`.
"""
import struct
from . import lzo

MAGIC = b"ZFSF"
HDR = struct.Struct("<4sIIIIII")
ENT = struct.Struct("<16sIIIII")
ENTRY_SIZE = ENT.size  # 36


class ZfsError(Exception):
    pass


class Entry:
    __slots__ = ("name_raw", "offset", "id", "size", "timestamp", "flags", "block", "index")

    def __init__(self, name_raw, offset, id_, size, timestamp, flags, block, index):
        self.name_raw = name_raw; self.offset = offset; self.id = id_; self.size = size
        self.timestamp = timestamp; self.flags = flags; self.block = block; self.index = index

    @property
    def name(self):
        return self.name_raw.split(b"\0")[0].decode("latin1")

    @property
    def method(self):
        return self.flags & 0xFF

    @property
    def usize(self):
        return self.flags >> 8

    @property
    def empty(self):
        return self.name_raw[0:1] == b"\0"

    def __repr__(self):
        return "Entry(%r off=0x%x size=%d flags=0x%x)" % (self.name, self.offset, self.size, self.flags)


class Zfs:
    def __init__(self):
        self.version = 1; self.name_len = 16; self.per_block = 100; self.n_files = 0; self.xor_key = 0
        self.dir0 = HDR.size
        self.blocks = []        # list of (block_offset, next_offset, [Entry x per_block] including empty slots)
        self.data = b""         # the whole archive (payload bytes are sliced from it)
        self.trailing = b""     # bytes after the last payload (none in I76.ZFS)

    @property
    def entries(self):
        return [e for _, _, ents in self.blocks for e in ents if not e.empty]

    def payload_raw(self, e):
        return self.data[e.offset:e.offset + e.size]

    def read(self, e):
        """Decoded payload bytes, as the loader would return them."""
        raw = self.payload_raw(e)
        if len(raw) != e.size:
            raise ZfsError("%s: archive truncated (%d of %d bytes)" % (e.name, len(raw), e.size))
        m = e.method
        if (m & 6) == 0:
            out = raw
        else:
            dec, consumed = lzo.decompress(raw, "1x" if (m & 2) else "1y", out_len=e.usize)
            if consumed != len(raw):
                raise ZfsError("%s: %d trailing bytes after the LZO stream" % (e.name, len(raw) - consumed))
            out = dec
        if self.xor_key:
            out = _xor_dwords(out, self.xor_key)
        return out


def _xor_dwords(b, key):
    n = len(b) // 4
    words = struct.unpack_from("<%dI" % n, b, 0)
    out = bytearray(struct.pack("<%dI" % n, *[w ^ key for w in words]))
    out += b[n * 4:]
    return bytes(out)


def parse(data):
    if data[:4] != MAGIC:
        raise ZfsError("not a ZFSF archive")
    z = Zfs()
    magic, z.version, z.name_len, z.per_block, z.n_files, z.xor_key, z.dir0 = HDR.unpack_from(data, 0)
    if z.name_len != 16:
        raise ZfsError("name_len %d unsupported" % z.name_len)
    z.data = data
    off = z.dir0
    bi = 0
    last_end = HDR.size
    seen = set()
    while True:
        if off in seen or off + 4 + z.per_block * ENTRY_SIZE > len(data):
            raise ZfsError("bad directory chain at 0x%x" % off)
        seen.add(off)
        nxt = struct.unpack_from("<I", data, off)[0]
        ents = []
        p = off + 4
        for i in range(z.per_block):
            name_raw, eoff, eid, esize, ets, efl = ENT.unpack_from(data, p)
            e = Entry(name_raw, eoff, eid, esize, ets, efl, bi, i)
            ents.append(e)
            if not e.empty:
                last_end = max(last_end, eoff + esize)
            p += ENTRY_SIZE
        z.blocks.append((off, nxt, ents))
        last_end = max(last_end, p)
        bi += 1
        if nxt == 0:
            break
        off = nxt
    z.trailing = data[last_end:]
    return z


def serialise(z):
    """Byte-exact re-emission of the archive from its parsed directory and payload slices.
    Recomputes nothing: offsets, ids, flags, timestamps and empty-slot bytes are re-emitted as parsed, so a
    parse -> serialise -> parse loop proves the parser reads every byte it claims to (gate R). Bytes the parse
    did not model (gaps between spans) are copied from the source and counted by the caller."""
    out = bytearray(HDR.pack(MAGIC, z.version, z.name_len, z.per_block, z.n_files, z.xor_key, z.dir0))
    pieces = []
    for boff, nxt, ents in z.blocks:
        blk = bytearray(struct.pack("<I", nxt))
        for e in ents:
            blk += ENT.pack(e.name_raw, e.offset, e.id, e.size, e.timestamp, e.flags)
        pieces.append((boff, bytes(blk)))
        for e in ents:
            if not e.empty:
                pieces.append((e.offset, z.payload_raw(e)))
    pieces.sort(key=lambda t: t[0])
    gaps = 0
    for off, b in pieces:
        if off < len(out):
            if out[off:off + len(b)] != b:
                raise ZfsError("overlap at 0x%x" % off)
            continue
        if off > len(out):
            gaps += off - len(out)
            out += z.data[len(out):off]
        out += b
    out += z.trailing
    z.unmodelled_bytes = gaps
    return bytes(out)


def repack_stored(files, per_block=100, timestamp=0, xor_key=0):
    """Build a new ZFSF v1 archive with every payload stored (method 0, flags = len << 8).
    files: iterable of (name, bytes). Names are NUL-padded to 16 B. Directory order = the given order; the loader
    qsorts by name and bsearches (0x4b9800), so any order is legal; alphabetical mirrors the shipped archive."""
    files = list(files)
    n = len(files)
    blk_size = 4 + per_block * ENTRY_SIZE
    out = bytearray(HDR.size)
    dir0 = HDR.size
    i = 0
    first = True
    while first or i < n:
        first = False
        chunk = files[i:i + per_block]
        boff = len(out)
        payload_pos = boff + blk_size
        entries_bytes = bytearray()
        payloads = bytearray()
        for j, (name, data) in enumerate(chunk):
            nb = name.encode("latin1")
            if len(nb) > 15:
                raise ZfsError("name %r longer than 15 characters" % name)
            if len(data) >= (1 << 24):
                raise ZfsError("%s: %d bytes does not fit in flags >> 8" % (name, len(data)))
            entries_bytes += ENT.pack(nb.ljust(16, b"\0"), payload_pos + len(payloads), i + j, len(data), timestamp,
                                      (len(data) << 8) | 0)
            payloads += data
        entries_bytes += bytes(ENTRY_SIZE * (per_block - len(chunk)))
        i += len(chunk)
        nxt = 0 if i >= n else payload_pos + len(payloads)
        out += struct.pack("<I", nxt) + entries_bytes + payloads
    struct.pack_into(HDR.format, out, 0, MAGIC, 1, 16, per_block, n, xor_key, dir0)
    return bytes(out)
