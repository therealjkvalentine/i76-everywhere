"""formats.py - extension -> format handler (decode / encode / coverage / errors) for the data-track round trip.

Every corpus file gets a handler: a modelled format, or `raw` (whole file counted unknown, identity round trip)
so byte coverage is always measured over the whole corpus, never over the modelled part only.
"""
import os
import bwd2x

BWD2_EXT = {".msn", ".lvl", ".vcf", ".vsf", ".sdf", ".vdf", ".wdf", ".gdf", ".xdf", ".vtf", ".cdf"}


class Handler:
    def __init__(self, name, decode, encode, coverage, errors=lambda v: [], method=""):
        self.name, self.decode, self.encode, self.coverage, self.errors, self.method = name, decode, encode, coverage, errors, method


def _raw(name):
    return Handler(name, lambda d, e: d, lambda v: v,
                   lambda v: ({"cited": 0, "typed": 0, "unused": 0, "unknown": len(v)}, {}),
                   method="unmodelled: identity, whole file counted unknown")


def _bwd2(ext):
    fam = bwd2x.family(ext)
    return Handler("bwd2" + ext if fam == ext.lstrip(".") else "bwd2." + fam, bwd2x.decode, bwd2x.encode, bwd2x.coverage, bwd2x.errors,
                   method="i76fmt.bwd2 container + data/fmt layouts per chunk body; decode -> encode -> byte compare")


EXTRA = {}  # ext -> Handler, filled by the other format modules


def register(ext, handler):
    EXTRA[ext] = handler


def handler_for(ext, path=None):
    if ext in BWD2_EXT:
        with open(path, "rb") as fh:
            if fh.read(4) == b"BWD2":
                h = _bwd2(ext)
                h.name = "bwd2:" + bwd2x.family(ext)
                return h
    if ext in EXTRA:
        return EXTRA[ext]
    return _raw("raw:" + (ext or "(none)"))


try:
    import other_formats  # noqa: F401  registers non-BWD2 handlers
except ImportError:
    pass
