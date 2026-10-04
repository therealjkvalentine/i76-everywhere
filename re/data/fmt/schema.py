"""schema.py - a small declarative struct engine for byte-exact parse / serialise / byte-coverage accounting.

Every chunk body layout in data\\fmt is written as a Struct of Fields. parse() returns plain python values
(dict / list / int / float / str / bytes) and serialise() turns them back into bytes. Byte exactness:
  * F32 values are FloatV (a float that remembers its 4 raw bytes) so NaN payloads and -0.0 survive;
    an edited float (plain float) is packed normally.
  * Str(n) values are StrV (a str that remembers its n raw bytes, including anything after the NUL);
    an edited string is re-encoded latin1 and NUL-padded to n.
Coverage: every leaf field has a class, counted in bytes:
  cited    meaning backed by a consuming instruction in i76.exe (Field.cite = "0x4ad9a3 ...")
  typed    named and typed, meaning from corpus statistics or prior art (Open76, That Tony), no exe citation yet
  unused   the loader provably never reads these bytes (cite the loader that skips them)
  unknown  explicit unknown run (name starts with "unk")
"""
import struct

CLASSES = ("cited", "typed", "unused", "unknown")


class FloatV(float):
    __slots__ = ("raw",)

    def __new__(cls, raw):
        v = float.__new__(cls, struct.unpack("<f", raw)[0])
        v.raw = raw
        return v


class StrV(str):
    __slots__ = ("raw",)

    def __new__(cls, raw):
        v = str.__new__(cls, raw.split(b"\0")[0].decode("latin1"))
        v.raw = raw
        return v


class T:
    size = None  # fixed size or None

    def parse(self, b, o, ctx):
        raise NotImplementedError

    def emit(self, v, ctx):
        raise NotImplementedError

    def leaves(self, v, field, path, out):
        out.append((path, len(self.emit(v, {})), field.klass))


class Prim(T):
    def __init__(self, fmt, name):
        self.fmt = "<" + fmt
        self.size = struct.calcsize(self.fmt)
        self.name = name

    def parse(self, b, o, ctx):
        if o + self.size > len(b):
            raise ValueError("short read %s at %d" % (self.name, o))
        return struct.unpack_from(self.fmt, b, o)[0], o + self.size

    def emit(self, v, ctx):
        return struct.pack(self.fmt, v)

    def leaves(self, v, field, path, out):
        out.append((path, self.size, field.klass))


class F32T(T):
    size = 4
    name = "f32"

    def parse(self, b, o, ctx):
        if o + 4 > len(b):
            raise ValueError("short read f32 at %d" % o)
        return FloatV(bytes(b[o:o + 4])), o + 4

    def emit(self, v, ctx):
        if isinstance(v, FloatV):
            return v.raw
        return struct.pack("<f", v)

    def leaves(self, v, field, path, out):
        out.append((path, 4, field.klass))


U8, I8, U16, I16, U32, I32 = Prim("B", "u8"), Prim("b", "i8"), Prim("H", "u16"), Prim("h", "i16"), Prim("I", "u32"), Prim("i", "i32")
F32 = F32T()


class Str(T):
    def __init__(self, n):
        self.size = n
        self.name = "char[%d]" % n

    def parse(self, b, o, ctx):
        if o + self.size > len(b):
            raise ValueError("short read str at %d" % o)
        return StrV(bytes(b[o:o + self.size])), o + self.size

    def emit(self, v, ctx):
        if isinstance(v, StrV):
            return v.raw
        e = v.encode("latin1")
        if len(e) >= self.size + 1:
            raise ValueError("string %r too long for char[%d]" % (v, self.size))
        return e.ljust(self.size, b"\0")

    def leaves(self, v, field, path, out):
        out.append((path, self.size, field.klass))


class Raw(T):
    """n bytes (n=None: to the end of the buffer)."""

    def __init__(self, n=None):
        self.size = n
        self.name = "u8[%s]" % ("rest" if n is None else n)

    def parse(self, b, o, ctx):
        n = len(b) - o if self.size is None else self.size
        if o + n > len(b):
            raise ValueError("short read raw[%d] at %d" % (n, o))
        return bytes(b[o:o + n]), o + n

    def emit(self, v, ctx):
        return bytes(v)

    def leaves(self, v, field, path, out):
        out.append((path, len(v), field.klass))


class Field:
    def __init__(self, name, typ, meaning="", cite="", unused=False):
        self.name, self.typ, self.meaning, self.cite, self.unused = name, typ, meaning, cite, unused

    @property
    def klass(self):
        if self.name.startswith("unk"):
            return "unknown"
        if self.unused:
            return "unused"
        return "cited" if self.cite else "typed"


class Struct(T):
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields
        ss = [f.typ.size for f in fields]
        self.size = sum(ss) if all(s is not None for s in ss) else None

    def parse(self, b, o, ctx):
        d = {}
        for f in self.fields:
            ctx2 = dict(ctx); ctx2.update(d); ctx2["_end"] = ctx.get("_end", len(b))
            d[f.name], o = f.typ.parse(b, o, ctx2)
        return d, o

    def emit(self, v, ctx):
        out = bytearray()
        for f in self.fields:
            ctx2 = dict(ctx); ctx2.update(v)
            out += f.typ.emit(v[f.name], ctx2)
        return bytes(out)

    def leaves(self, v, field, path, out):
        for f in self.fields:
            start = len(out)
            f.typ.leaves(v[f.name], f, path + "." + f.name if path else f.name, out)
            k = f.klass
            if k in ("cited", "unused") and isinstance(f.typ, (Struct, Arr)):
                # leaves of a cited/unused aggregate inherit its class unless they carry their own
                for i in range(start, len(out)):
                    if out[i][2] == "typed":
                        out[i] = (out[i][0], out[i][1], k)


class Arr(T):
    """count: int, name of an earlier sibling field, a callable(ctx) -> int, or None (repeat to end of buffer)."""

    def __init__(self, typ, count):
        self.typ, self.count = typ, count
        self.size = typ.size * count if isinstance(count, int) and typ.size is not None else None
        self.name = "%s[%s]" % (typ.name, count if not callable(count) else "f()")

    def _n(self, ctx):
        c = self.count
        if isinstance(c, int):
            return c
        if isinstance(c, str):
            return ctx[c]
        return c(ctx)

    def parse(self, b, o, ctx):
        out = []
        if self.count is None:
            end = ctx.get("_end", len(b))
            while o < end:
                v, o = self.typ.parse(b, o, ctx)
                out.append(v)
            return out, o
        n = self._n(ctx)
        if n < 0 or n > 10_000_000:
            raise ValueError("bad array count %r" % n)
        for _ in range(n):
            v, o = self.typ.parse(b, o, ctx)
            out.append(v)
        return out, o

    def emit(self, v, ctx):
        return b"".join(self.typ.emit(x, ctx) for x in v)

    def leaves(self, v, field, path, out):
        for i, x in enumerate(v):
            self.typ.leaves(x, Field(field.name, self.typ, field.meaning, field.cite, field.unused) if not isinstance(self.typ, Struct) else field, "%s[%d]" % (path, i), out)


class Cond(T):
    """typ if pred(ctx) else nothing (value None)."""

    def __init__(self, pred, typ):
        self.pred, self.typ = pred, typ
        self.size = None
        self.name = "cond(%s)" % typ.name

    def parse(self, b, o, ctx):
        if self.pred(ctx):
            return self.typ.parse(b, o, ctx)
        return None, o

    def emit(self, v, ctx):
        return b"" if v is None else self.typ.emit(v, ctx)

    def leaves(self, v, field, path, out):
        if v is not None:
            self.typ.leaves(v, field, path, out)


def parse_exact(typ, body):
    """Parse body with typ; the whole body must be consumed. Returns value."""
    v, o = typ.parse(body, 0, {"_end": len(body)})
    if o != len(body):
        raise ValueError("%s consumed %d of %d bytes" % (typ.name, o, len(body)))
    return v


def coverage(typ, v):
    """{class: bytes} over the leaves of v."""
    out = []
    typ.leaves(v, Field("root", typ), "", out)
    cov = dict.fromkeys(CLASSES, 0)
    for _, n, k in out:
        cov[k] += n
    return cov


def layout_rows(typ, prefix="", base=0):
    """Static layout table rows (offset, type, name, class, meaning, cite) for docs; variable parts reported once."""
    rows = []
    off = base
    for f in getattr(typ, "fields", []):
        t = f.typ
        o = off if off is not None else None
        if isinstance(t, Struct):
            rows.append((o, "struct %s" % t.name, prefix + f.name, f.klass, f.meaning, f.cite))
            rows += layout_rows(t, prefix + f.name + ".", o)
        elif isinstance(t, Arr) and isinstance(t.typ, Struct):
            rows.append((o, "%s[%s]" % (t.typ.name, t.count if not callable(t.count) else "f()"), prefix + f.name, f.klass, f.meaning, f.cite))
            rows += layout_rows(t.typ, prefix + f.name + "[i].", 0)
        else:
            rows.append((o, t.name, prefix + f.name, f.klass, f.meaning, f.cite))
        off = off + t.size if (off is not None and t.size is not None) else None
    return rows


def get(v, path):
    """Resolve a dotted/indexed path like 'segments[3].left.x' in a parsed value."""
    import re
    cur = v
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            cur = cur[int(part[1:-1])]
        else:
            cur = cur[part]
    return cur


def put(v, path, new):
    import re
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    cur = v
    for part in parts[:-1]:
        cur = cur[int(part[1:-1])] if part.startswith("[") else cur[part]
    last = parts[-1]
    if last.startswith("["):
        cur[int(last[1:-1])] = new
    else:
        if last not in cur:
            raise KeyError(path)
        cur[last] = new
