"""Force-feedback effect files .frc: RIFF form 'FORC' (Microsoft Force Editor .ffe layout under another name).

Measured (formats REPORT section 9, force\\*.FRC, 14 files 288-820 B): RIFF/FORC; LIST INFO (INAM ICMT ISFT
ICOP); trgt (16-byte GUID {04ACE095-1FA8-11D0-AA22-00A0C911F471}); LIST trak -> LIST efct x N: id u32, data
(0x68-byte DIEFFECT-like record beginning with the effect name), optional spln envelope.
This module is a generic RIFF walker (chunks padded to even length; LIST/RIFF carry a 4-byte form type and
nest); serialise recomputes sizes and pads. The efct records are exposed raw; DirectInput field semantics are
boundary typing for the FFB subsystem (dx5.h), not claimed here.
"""
import struct


class FrcError(Exception):
    pass


class RiffChunk:
    __slots__ = ("id", "form", "data", "children", "pad", "offset")

    def __init__(self, id_, form=None, data=b"", children=None, pad=b"", offset=None):
        self.id = id_; self.form = form; self.data = data; self.children = children; self.pad = pad
        self.offset = offset

    @property
    def is_list(self):
        return self.children is not None

    def size(self):
        if self.is_list:
            return 4 + sum(c.size() + 8 + len(c.pad) for c in self.children)
        return len(self.data)

    def find(self, id_, form=None):
        out = []
        for c in self.children or []:
            if c.id == id_ and (form is None or c.form == form):
                out.append(c)
        return out


def _walk(data, base, end):
    out = []
    p = base
    while p + 8 <= end:
        cid = data[p:p + 4]
        sz = struct.unpack_from("<I", data, p + 4)[0]
        body_end = p + 8 + sz
        if body_end > end:
            raise FrcError("chunk %r at 0x%x overruns (%d bytes)" % (cid, p, sz))
        pad = data[body_end:body_end + (sz & 1)] if (sz & 1) and body_end < end else b""
        if cid in (b"LIST", b"RIFF"):
            form = data[p + 8:p + 12]
            kids = _walk(data, p + 12, body_end)
            out.append(RiffChunk(cid, form, b"", kids, pad, p))
        else:
            out.append(RiffChunk(cid, None, data[p + 8:body_end], None, pad, p))
        p = body_end + len(pad)
    if p != end:
        raise FrcError("%d unparsed bytes before 0x%x" % (end - p, end))
    return out


class Frc:
    def __init__(self, root, trailing=b""):
        self.root = root          # RiffChunk id RIFF form FORC
        self.trailing = trailing  # bytes after the RIFF size span

    @property
    def effects(self):
        out = []
        for trak in self.root.find(b"LIST", b"trak"):
            for ef in trak.find(b"LIST", b"efct"):
                out.append(ef)
        return out


def parse(data):
    if data[:4] != b"RIFF":
        raise FrcError("not a RIFF file")
    sz = struct.unpack_from("<I", data, 4)[0]
    end = 8 + sz
    if end > len(data):
        raise FrcError("RIFF size %d exceeds file (%d)" % (sz, len(data)))
    if data[8:12] != b"FORC":
        raise FrcError("RIFF form %r, expected FORC" % data[8:12])
    roots = _walk(data, 0, end)
    if len(roots) != 1:
        raise FrcError("expected one RIFF root, found %d" % len(roots))
    return Frc(roots[0], data[end:])


def _emit(c, out):
    start = len(out)
    out += c.id + b"\0\0\0\0"
    if c.is_list:
        out += c.form
        for k in c.children:
            _emit(k, out)
    else:
        out += c.data
    sz = len(out) - start - 8
    struct.pack_into("<I", out, start + 4, sz)
    if sz & 1:
        out += c.pad if c.pad else b"\0"


def serialise(f):
    out = bytearray()
    _emit(f.root, out)
    out += f.trailing
    return bytes(out)
