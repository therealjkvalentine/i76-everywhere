"""bwd2x.py - BWD2 files with every chunk body decoded through a layout registry (layouts.py).

The container itself is i76fmt.bwd2 (imported, never modified). This module adds:
  decode(data, ext)  -> Doc: the i76fmt tree plus, per leaf chunk, `.value` = the parsed body (or None + reason)
  encode(doc)        -> bytes: bodies re-emitted from `.value` (so edits to values land), container via i76fmt
  coverage(doc)      -> {class: bytes}, container bytes (magic, header, chunk tag+size) counted as `cited`
                        (walker bwd2_Parse 0x4b3db0 reads tag and size of every chunk).
A chunk whose tag has no layout is kept as raw bytes and counted `unknown`.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from i76fmt import bwd2  # noqa: E402
import schema  # noqa: E402
import layouts  # noqa: E402

CONTAINER_CITE = "bwd2_Parse 0x4b3db0: magic/header, per chunk tag[4] + size (incl. 8-byte header)"


class Info:
    __slots__ = ("layout", "value", "error")

    def __init__(self, layout):
        self.layout, self.value, self.error = layout, None, None


class Doc:
    def __init__(self, raw, fam):
        self.raw, self.family, self.info = raw, fam, {}


def family(ext):
    ext = ext.lower().lstrip(".")
    return {"lvl": "msn", "cbt": "msn", "rac": "msn"}.get(ext, ext)


def _lookup(fam, parent, tag):
    return layouts.lookup(fam, parent, tag)


def decode(data, ext):
    fam = family(ext)
    doc = Doc(bwd2.parse(data), fam)

    def rec(chunks, parent):
        for c in chunks:
            if c.is_group:
                rec(c.children, c.tag_str)
                continue
            lay = _lookup(fam, parent, c.tag_str)
            info = doc.info[id(c)] = Info(lay)
            if lay is None:
                continue
            try:
                info.value = lay.parse(c.body)
            except Exception as ex:  # noqa: BLE001
                info.error = "%s: %s" % (type(ex).__name__, ex)
    rec(doc.raw.chunks, "")
    return doc


def encode(doc):
    def rec(chunks):
        for c in chunks:
            if c.is_group:
                rec(c.children)
            else:
                i = doc.info.get(id(c))
                if i is not None and i.layout is not None and i.error is None:
                    c.body = i.layout.serialise(i.value)
    rec(doc.raw.chunks)
    return bwd2.serialise(doc.raw)


def coverage(doc):
    cov = dict.fromkeys(schema.CLASSES, 0)
    cov["cited"] += 8 + len(doc.raw.header_extra)
    cov["unknown"] += len(doc.raw.trailing)
    per_tag = {}

    def add(tag, k, n):
        cov[k] += n
        d = per_tag.setdefault(tag, dict.fromkeys(schema.CLASSES, 0))
        d[k] += n

    def rec(chunks, parent):
        for c in chunks:
            add("(chunk headers)", "cited", 8)
            if c.is_group:
                rec(c.children, c.tag_str)
                continue
            key = (parent + "/" if parent else "") + c.tag_str
            i = doc.info.get(id(c))
            if i is None or i.layout is None or i.error is not None:
                add(key, "unknown", len(c.body))
                continue
            for k, n in i.layout.coverage(i.value).items():
                add(key, k, n)
    rec(doc.raw.chunks, "")
    return cov, per_tag


def errors(doc):
    out = []
    for c, _ in doc.raw.walk():
        i = doc.info.get(id(c))
        if i is not None and i.error:
            out.append((c.tag_str, i.error))
    return out


def chunks(doc, tag=None, parent=None):
    """(parent_tag, chunk, Info) for every leaf chunk, optionally filtered."""
    out = []

    def rec(cs, par):
        for c in cs:
            if c.is_group:
                rec(c.children, c.tag_str)
            elif (tag is None or c.tag_str == tag) and (parent is None or par == parent):
                out.append((par, c, doc.info.get(id(c))))
    rec(doc.raw.chunks, "")
    return out
