#!/usr/bin/env python3
r"""i76mod.py - read, edit and rebuild Interstate '76 data files. Writes ONLY under data\out.

Sources: a path, or `zfs:<name>` for a file inside the pristine archive (sandbox-gog\main\app\I76.ZFS).

  i76mod.py show  <src> [chunk]                 list chunks, or every field of one chunk with its path and value
  i76mod.py get   <src> <chunk> <field>
  i76mod.py set   <src> <chunk> <field>=<value> [<chunk> <field>=<value> ...] [--out NAME] [--zfs]
  i76mod.py alias <src>                          named, documented shortcuts for this file type (see ALIASES)
  i76mod.py car   <src> <stat>=<value> ...       shortcut: vehicle stats by name (armour.front=900 ...)

<chunk> is TAG, PARENT/TAG, or either with #n for the n-th occurrence (0-based): VCFC, WEPN#2, ODEF/OBJ#17, ADEF/FSM.
<field> is a dotted path into the parsed body: armour, name, sections[3].left.x, consts[12], code[40].arg.
Values: integers, floats, or text (strings are NUL-padded to their field width; too long is an error).
--out NAME   output file name in data\out (default: the source name)
--zfs        also write data\out\I76.ZFS: the pristine archive with this file replaced (stored mode, all other
             entries byte-identical and still compressed); every entry is decoded back and compared.
Every write is read back and re-parsed; the edit is shown as old -> new.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
MAP = os.path.dirname(DATA)
sys.path.insert(0, os.path.join(DATA, "fmt"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(MAP, "tools"))
import bwd2x, schema, formats  # noqa: E402
from schema import FloatV, StrV  # noqa: E402
import zfspatch  # noqa: E402
from i76fmt import zfs  # noqa: E402

OUT = os.path.join(DATA, "out")
ZFS_PATH = os.path.join(MAP, "sandbox-gog", "main", "app", "I76.ZFS")
FORBIDDEN = [r"C:\Users\james\i76-uncap-lab\game", r"C:\Users\james\i76-bisect\game", os.path.join(MAP, "sandbox-gog"),
             os.path.expanduser(r"~\Downloads")]

try:
    from aliases import ALIASES  # noqa: E402
except ImportError:
    ALIASES = {}


def load(src):
    if src.startswith("zfs:"):
        name = src[4:].lower()
        z = zfs.parse(open(ZFS_PATH, "rb").read())
        for e in z.entries:
            if e.name.lower() == name:
                return name, z.read(e)
        raise SystemExit("%s not in %s" % (name, ZFS_PATH))
    return os.path.basename(src), open(src, "rb").read()


def safe_out(name):
    p = os.path.abspath(os.path.join(OUT, name))
    if not p.lower().startswith(os.path.abspath(OUT).lower()):
        raise SystemExit("REFUSE: output outside data\\out")
    for g in FORBIDDEN:
        if p.lower().startswith(os.path.abspath(g).lower()):
            raise SystemExit("REFUSE: game folder")
    return p


def find_chunk(doc, spec):
    idx = 0
    if "#" in spec:
        spec, i = spec.split("#"); idx = int(i)
    parent, tag = (spec.split("/") + [None])[:2] if "/" in spec else (None, spec)
    if tag is None:
        parent, tag = None, parent
    hits = bwd2x.chunks(doc, tag, parent)
    if idx >= len(hits):
        raise SystemExit("chunk %s#%d not found (%d present)" % (spec, idx, len(hits)))
    par, c, info = hits[idx]
    if info is None or info.layout is None:
        raise SystemExit("chunk %s has no layout (raw)" % spec)
    if info.error:
        raise SystemExit("chunk %s failed to parse: %s" % (spec, info.error))
    return c, info


def fmtv(v):
    if isinstance(v, FloatV) or isinstance(v, float):
        return repr(float(v))
    if isinstance(v, StrV) or isinstance(v, str):
        return repr(str(v))
    if isinstance(v, bytes):
        return v.hex() if len(v) <= 32 else "<%d bytes>" % len(v)
    return repr(v)


def flat(v, path=""):
    if isinstance(v, dict):
        for k, x in v.items():
            yield from flat(x, (path + "." if path else "") + k)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from flat(x, "%s[%d]" % (path, i))
    else:
        yield path, v


def coerce(old, text):
    if isinstance(old, (FloatV, float)):
        return float(text)
    if isinstance(old, (StrV, str)):
        return text
    if isinstance(old, bool):
        return text.lower() in ("1", "true", "yes")
    if isinstance(old, int):
        return int(text, 0)
    if isinstance(old, bytes):
        return bytes.fromhex(text)
    raise SystemExit("cannot set a field of type %s" % type(old).__name__)


def cmd_show(src, chunk=None):
    name, data = load(src)
    ext = os.path.splitext(name)[1]
    doc = bwd2x.decode(data, ext)
    if chunk is None:
        seen = {}
        for par, c, info in bwd2x.chunks(doc):
            k = (par + "/" if par else "") + c.tag_str
            n = seen.get(k, 0); seen[k] = n + 1
            st = "raw" if info is None or info.layout is None else ("ERR " + info.error if info.error else "ok")
            print("%-14s #%-3d %6d B  %s" % (k, n, len(c.body), st))
        return
    c, info = find_chunk(doc, chunk)
    for p, v in flat(info.value):
        print("%-40s %s" % (p, fmtv(v)))


def apply_edits(doc, edits):
    log = []
    for chunk, assign in edits:
        field, text = assign.split("=", 1)
        c, info = find_chunk(doc, chunk)
        old = schema.get(info.value, field)
        new = coerce(old, text)
        schema.put(info.value, field, new)
        log.append((chunk, field, old, new))
    return log


def cmd_set(src, pairs, out_name=None, want_zfs=False):
    name, data = load(src)
    ext = os.path.splitext(name)[1]
    doc = bwd2x.decode(data, ext)
    edits = [(pairs[i], pairs[i + 1]) for i in range(0, len(pairs), 2)]
    log = apply_edits(doc, edits)
    new = bwd2x.encode(doc)
    outp = safe_out(out_name or name)
    os.makedirs(OUT, exist_ok=True)
    open(outp, "wb").write(new)
    back = open(outp, "rb").read()
    assert back == new, "readback mismatch"
    doc2 = bwd2x.decode(back, ext)
    for chunk, field, old, nv in log:
        _, info = find_chunk(doc2, chunk)
        got = schema.get(info.value, field)
        ok = (float(got) == float(nv)) if isinstance(nv, float) else (str(got) == str(nv) if isinstance(nv, str) else got == nv)
        print("%s %s: %s -> %s  [read back %s %s]" % (chunk, field, fmtv(old), fmtv(nv), fmtv(got), "OK" if ok else "MISMATCH"))
        if not ok:
            raise SystemExit("read-back mismatch")
    nd = sum(1 for a, b in zip(data, new) if a != b) + abs(len(data) - len(new))
    print("wrote %s (%d bytes, %d bytes differ from source)" % (outp, len(new), nd))
    if want_zfs:
        raw = open(ZFS_PATH, "rb").read()
        arc = zfspatch.patch(raw, {name.lower(): new})
        bad, n = zfspatch.verify(arc, {name.lower(): new}, raw)
        if bad:
            raise SystemExit("archive verify failed: %s" % bad[:5])
        zp = safe_out("I76.ZFS")
        open(zp, "wb").write(arc)
        assert open(zp, "rb").read() == arc
        print("wrote %s (%d bytes; %d entries decoded and compared: all equal to the original except %s)" % (zp, len(arc), n, name.lower()))
    return outp


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    cmd = argv[1]
    want_zfs = "--zfs" in argv
    out_name = argv[argv.index("--out") + 1] if "--out" in argv else None
    args = [a for i, a in enumerate(argv[2:], 2) if a != "--zfs" and a != "--out" and argv[i - 1] != "--out"]
    if cmd == "show":
        cmd_show(args[0], args[1] if len(args) > 1 else None)
    elif cmd == "get":
        name, data = load(args[0])
        doc = bwd2x.decode(data, os.path.splitext(name)[1])
        c, info = find_chunk(doc, args[1])
        print(fmtv(schema.get(info.value, args[2])))
    elif cmd == "set":
        cmd_set(args[0], args[1:], out_name, want_zfs)
    elif cmd in ("alias", "car"):
        name, _ = load(args[0])
        fam = bwd2x.family(os.path.splitext(name)[1])
        table = ALIASES.get(fam, {})
        if cmd == "alias":
            for k, (chunk, field, doc) in table.items():
                print("%-24s %-10s %-24s %s" % (k, chunk, field, doc))
            return 0
        pairs = []
        for a in args[1:]:
            k, v = a.split("=", 1)
            if k not in table:
                raise SystemExit("unknown stat %r; `i76mod.py alias %s` lists them" % (k, args[0]))
            chunk, field, _ = table[k]
            pairs += [chunk, "%s=%s" % (field, v)]
        cmd_set(args[0], pairs, out_name, want_zfs)
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
