"""layouts.py - the registry: (family, parent group tag, chunk tag) -> body layout.

Families are file extensions (msn covers .msn/.lvl). parent is the enclosing xDEF group tag ('' at top level).
Each entry is a Layout: parse(body)->value, serialise(value)->bytes, coverage(value)->{class: bytes}.
Layouts live in the per-family modules (l_msn, l_vehicle, ...); this module only indexes them.
"""
import schema


class Layout:
    def __init__(self, typ=None, parse=None, serialise=None, cov=None, doc=""):
        self.typ = typ
        self._parse, self._ser, self._cov = parse, serialise, cov
        self.doc = doc

    def parse(self, body):
        if self._parse:
            return self._parse(body)
        return schema.parse_exact(self.typ, body)

    def serialise(self, v):
        if self._ser:
            return self._ser(v)
        return self.typ.emit(v, {})

    def coverage(self, v):
        if self._cov:
            return self._cov(v)
        return schema.coverage(self.typ, v)


REGISTRY = {}


def register(fams, parent, tag, layout):
    for f in fams.split():
        REGISTRY[(f, parent, tag)] = layout


def lookup(fam, parent, tag):
    return REGISTRY.get((fam, parent, tag)) or REGISTRY.get((fam, "*", tag)) or REGISTRY.get(("*", "*", tag))


def S(name, *fields):
    return schema.Struct(name, [schema.Field(*f) for f in fields])


def L(typ, doc=""):
    return Layout(typ=typ, doc=doc)


# REV-type chunks: body u32 revision, checked by bwd2_h_REV_* 0x4b4610 ("Bad BWD revision for file %s")
REV = S("REV", ("revision", schema.U32, "format revision, compared with the expected value", "bwd2_h_REV 0x4b4610"))
EMPTY = S("EMPTY")
for t in ("REV", "WREV", "TREV", "RREV", "OREV", "LREV", "AREV"):
    register("*", "*", t, L(REV))
register("*", "*", "EXIT", Layout(
    parse=lambda b: b, serialise=lambda v: v,
    cov=lambda v: {"cited": 0, "typed": 0, "unused": len(v), "unknown": 0},
    doc="group/file terminator, normally a 0-byte body. bwd2_h_EXIT 0x4b4290 compares only the tag and the walk stops "
        "at EXIT, so a body is never read. The game-written ADDON vehscn.vcf/.vsf carry an 8-byte body that is a second "
        "EXIT header ('EXIT', u32 16)."))

import l_msn  # noqa: E402,F401
try:
    import l_vehicle  # noqa: F401
except ImportError:
    pass
try:
    import l_defs  # noqa: F401
except ImportError:
    pass
