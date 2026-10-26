"""zfspatch.py - rebuild I76.ZFS with some entries replaced, keeping every other payload byte-for-byte compressed.

Replaced entries are written stored (method 0, flags = usize << 8): the loader 0x4b9bd0 returns raw bytes when
(flags & 6) == 0 (i76fmt.zfs docstring; zfs-lzo-refute section 2). There is no LZO 1.00 compressor, so this is the
only legal way to put an edited file into the archive. Directory layout, ids, timestamps and order are preserved:
[header][block: next, 100 x 36-byte entries][their payloads][block]... exactly as the original is laid out.
"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from i76fmt import zfs  # noqa: E402

HDR = struct.Struct("<4sIIIIII")
ENT = struct.Struct("<16sIIIII")


def patch(raw, replace):
    """raw: original archive bytes; replace: {lower-case name: new decoded bytes}. Returns new archive bytes."""
    z = zfs.parse(raw)
    magic, ver, nlen, per_block, n_files, xor_key, dir0 = HDR.unpack_from(raw, 0)
    if xor_key != 0:
        raise ValueError("xor_key != 0 not supported")
    ents = list(z.entries)
    missing = set(replace) - {e.name.lower() for e in ents}
    if missing:
        raise KeyError("not in archive: %s" % sorted(missing))
    out = bytearray(HDR.pack(magic, ver, nlen, per_block, n_files, xor_key, HDR.size))
    for b0 in range(0, len(ents), per_block):
        blk = ents[b0:b0 + per_block]
        bstart = len(out)
        out += b"\0" * (4 + per_block * ENT.size)
        p = len(out)
        recs = []
        for e in blk:
            name = e.name.lower()
            if name in replace:
                payload = replace[name]
                flags = (len(payload) << 8) | 0
            else:
                payload = z.payload_raw(e)
                flags = e.flags
            recs.append(ENT.pack(e.name_raw, p, e.id, len(payload), e.timestamp, flags))
            out += payload
            p += len(payload)
        for i, r in enumerate(recs):
            o = bstart + 4 + i * ENT.size
            out[o:o + ENT.size] = r
        nxt = len(out) if b0 + per_block < len(ents) else 0
        struct.pack_into("<I", out, bstart, nxt)
    return bytes(out)


def verify(new, replace, raw):
    """Every entry of the new archive decodes to the original bytes, except the replaced ones, which decode to theirs."""
    z0, z1 = zfs.parse(raw), zfs.parse(new)
    e0 = {e.name.lower(): e for e in z0.entries}
    bad = []
    for e in z1.entries:
        n = e.name.lower()
        want = replace[n] if n in replace else z0.read(e0[n])
        if z1.read(e) != want:
            bad.append(n)
    return bad, len(z1.entries)
