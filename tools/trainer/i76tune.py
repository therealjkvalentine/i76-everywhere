r"""i76tune.py - live "spec tuner" for Interstate '76: change physics / weapon / AI constants in the running
game from a catalogue (tunables.json) derived from the reverse-engineering specs (i76-map\subsystems\*.md).
SANDBOX only by default, like i76trainer.py (which it imports for process access).

    python i76tune.py list [group]              id, name, live value vs default, unit ('*' = differs)
    python i76tune.py groups                    the catalogue groups and entry counts
    python i76tune.py get <id>                  one entry in full (meaning, spec, range, address)
    python i76tune.py set <id> <value> [--force] write, read back, print old -> new (derived fields too)
    python i76tune.py reset <id>|all            back to the pristine default (exe-scope entries)
    python i76tune.py preset save <file> [id..] JSON of id -> live value (default: every changed exe entry)
    python i76tune.py preset load <file>        apply a preset with read-back
    python i76tune.py watch <id>...             poll and print at 5 Hz until Ctrl-C
    python i76tune.py dump                      every entry's live value as JSON
    python i76tune.py --offline list [group]    no game: catalogue with the pristine-image defaults, plus the
                                                verification summary (every exe default checked against the image)
    options: --any (allow a non-sandbox game), --force (ignore min/max), --image <pristine exe path>

exe-scope entries live in the game image (.rdata / .data constants or .text instruction immediates) and change the
behaviour of EVERY car and AI at once; the pages are made writable with VirtualProtectEx for the write and restored.
entity / engine / brake / susp / wheel entries resolve through the player's vehicle on each command.
"""
import ctypes, ctypes.wintypes as wt, struct, sys, os, json, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import i76trainer                                           # find_game, Game (rd / wr / u32 / f32 / player), k32
from i76trainer import k32

CATALOGUE = os.path.join(HERE, "tunables.json")
FMT = {"f32": "<f", "f64": "<d", "i32": "<i", "u32": "<I", "u8": "<B"}
PAGE_READWRITE, PAGE_EXECUTE_READWRITE = 0x04, 0x40
COMPONENT_SLOT = {"engine": 0x3c4, "brake": 0x3cc, "susp": 0x3c8}      # entity+slot -> component object; +0x70 -> data

k32.VirtualProtectEx.argtypes = [wt.HANDLE, wt.LPVOID, ctypes.c_size_t, wt.DWORD, wt.PDWORD]
k32.VirtualProtectEx.restype = wt.BOOL


# ---------------------------------------------------------------- catalogue

def load_catalogue(path=CATALOGUE):
    with open(path, encoding="utf-8") as f:
        cat = json.load(f)
    ids = {}
    for e in cat["entries"]:
        if e["id"] in ids:
            sys.exit("catalogue: duplicate id %s" % e["id"])
        if e["type"] not in FMT:
            sys.exit("catalogue: %s has unknown type %s" % (e["id"], e["type"]))
        e["_addr"] = int(e["addr"], 16)
        for d in e.get("derived", []):
            d["_addr"] = int(d.get("addr") or d.get("off"), 16)
        ids[e["id"]] = e
    cat["_ids"] = ids
    return cat


def fmt_val(e, v):
    if v is None:
        return "n/a"
    if e["type"] in ("f32", "f64"):
        return "%.6g" % v
    return str(v)


def close(a, b, typ):
    if a is None or b is None:
        return False
    if typ in ("f32", "f64"):
        return abs(a - b) <= max(2e-4 * abs(b), 1e-7)
    return a == b


# ---------------------------------------------------------------- pristine image (no pefile dependency)

class Image:
    """Section-mapped reader of the pristine i76.exe (verification source and reset source)."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        self.md5 = hashlib.md5(self.data).hexdigest()
        pe = struct.unpack_from("<I", self.data, 0x3c)[0]
        if self.data[pe:pe + 4] != b"PE\0\0":
            sys.exit("%s is not a PE image" % path)
        nsec, opt = struct.unpack_from("<H", self.data, pe + 6)[0], struct.unpack_from("<H", self.data, pe + 20)[0]
        self.base = struct.unpack_from("<I", self.data, pe + 24 + 28)[0]
        self.sections = []
        for i in range(nsec):
            o = pe + 24 + opt + 40 * i
            name = self.data[o:o + 8].rstrip(b"\0").decode("latin1")
            vsize, va, rawsize, rawoff, chars = struct.unpack_from("<IIII", self.data, o + 8) + (struct.unpack_from("<I", self.data, o + 36)[0],)
            self.sections.append((name, self.base + va, max(vsize, rawsize), rawoff, rawsize, chars))

    def section(self, va):
        for name, start, size, rawoff, rawsize, chars in self.sections:
            if start <= va < start + size:
                return name
        return None

    def rd(self, va, n):
        for name, start, size, rawoff, rawsize, chars in self.sections:
            if start <= va < start + size:
                off = va - start
                if off + n > rawsize:
                    return None                                  # BSS: not file-backed
                return self.data[rawoff + off: rawoff + off + n]
        return None

    def value(self, va, typ):
        b = self.rd(va, struct.calcsize(FMT[typ]))
        return struct.unpack(FMT[typ], b)[0] if b else None


def open_image(cat, override=None):
    path = override or cat["image"]["path"]
    if not os.path.exists(path):
        return None
    img = Image(path)
    if img.md5 != cat["image"]["md5"]:
        print("warning: %s md5 %s is not the pristine %s; image defaults not trusted" % (path, img.md5, cat["image"]["md5"]))
        return None
    return img


def verify(cat, img, verbose=False):
    """Check every exe-scope default (and every derived address) against the pristine image. Returns (ok, bad, rows)."""
    ok, bad, rows = 0, [], []
    for e in cat["entries"]:
        if e["scope"] != "exe":
            continue
        sec = img.section(e["_addr"])
        iv = img.value(e["_addr"], e["type"])
        good = iv is not None and close(iv, e["default"], e["type"]) and sec == e.get("section")
        rows.append((e, iv, sec, good))
        if good:
            ok += 1
        else:
            bad.append((e["id"], e["default"], iv, sec, e.get("section")))
        for d in e.get("derived", []):
            dv = img.value(d["_addr"], d["type"])
            want = eval(d["formula"], {"__builtins__": {}}, {"x": e["default"], "max": max, "min": min, "abs": abs,
                                                            "rd": lambda off: None, "ri": lambda off: None})
            if dv is None or not close(dv, want, d["type"]):
                bad.append((e["id"] + " -> derived " + hex(d["_addr"]), want, dv, img.section(d["_addr"]), "?"))
    return ok, bad, rows


# ---------------------------------------------------------------- live game

class Tuner(i76trainer.Game):
    def __init__(self, pid, cat):
        super().__init__(pid)
        self.cat = cat

    def player_entity(self):
        root = self.u32(0x54a264)
        obj = self.u32(root) if root else None
        ent = self.u32(obj + 0x70) if obj else None
        return ent or None

    def base_of(self, e):
        """absolute address of an entry's value, or None when the scope cannot be resolved (no player car)"""
        if e["scope"] == "exe":
            return 0
        ent = self.player_entity()
        if not ent:
            return None
        if e["scope"] == "entity":
            return ent
        if e["scope"] in COMPONENT_SLOT:
            comp = self.u32(ent + COMPONENT_SLOT[e["scope"]])
        elif e["scope"] == "wheel":
            comp = self.u32(ent + 0x3a8 + 4 * int(e.get("slot", 0)))
        else:
            sys.exit("unknown scope %s" % e["scope"])
        data = self.u32(comp + 0x70) if comp else None
        return data or None

    def addr_of(self, e):
        b = self.base_of(e)
        return None if b is None else b + e["_addr"]

    def read_at(self, a, typ):
        b = self.rd(a, struct.calcsize(FMT[typ]))
        return struct.unpack(FMT[typ], b)[0] if b else None

    def read(self, e):
        a = self.addr_of(e)
        return None if a is None else self.read_at(a, e["type"])

    def write_at(self, a, typ, v, exe_scope):
        """VirtualProtectEx (exe scope), write, read back, restore. Returns the value read back."""
        data = struct.pack(FMT[typ], v)
        old = wt.DWORD(0)
        protected = False
        if exe_scope:
            want = PAGE_EXECUTE_READWRITE if self.cat_section(a) == ".text" else PAGE_READWRITE
            protected = bool(k32.VirtualProtectEx(self.h, ctypes.c_void_p(a), len(data), want, ctypes.byref(old)))
        try:
            ok = self.wr(a, data)
        finally:
            if protected:
                k32.VirtualProtectEx(self.h, ctypes.c_void_p(a), len(data), old.value, ctypes.byref(wt.DWORD(0)))
        back = self.read_at(a, typ)
        if not ok:
            print("  WRITE FAILED at 0x%08x (error %d)" % (a, ctypes.get_last_error()))
        return back

    def cat_section(self, a):
        for e in self.cat["entries"]:
            if e["scope"] == "exe" and e["_addr"] == a:
                return e.get("section")
            for d in e.get("derived", []):
                if e["scope"] == "exe" and d["_addr"] == a:
                    return e.get("section")
        return ".rdata"

    def apply(self, e, v, force=False, img=None):
        """set one entry (range check, write, read back, derived fields). Returns True when every write read back.
        With img (a reset), exe-scope derived words take their exact pristine bytes instead of the recomputed value."""
        if e["type"] in ("i32", "u32", "u8"):
            v = int(round(v))
        lo, hi = e.get("min"), e.get("max")
        if not force and ((lo is not None and v < lo) or (hi is not None and v > hi)):
            print("  %s: %s is outside the sane range [%s, %s]; use --force" % (e["id"], fmt_val(e, v), lo, hi))
            return False
        base = self.base_of(e)
        if base is None:
            print("  %s: no player vehicle (not in a mission?)" % e["id"])
            return False
        a = base + e["_addr"]
        old = self.read_at(a, e["type"])
        back = self.write_at(a, e["type"], v, e["scope"] == "exe")
        good = close(back, v, e["type"])
        print("  %-30s 0x%08x  %s -> %s%s" % (e["id"], a, fmt_val(e, old), fmt_val(e, back),
                                                "" if good else "   FAILED (wanted %s)" % fmt_val(e, v)))
        for d in e.get("derived", []):
            da = (0 if "addr" in d else base) + d["_addr"]
            env = {"x": v, "max": max, "min": min, "abs": abs,
                   "rd": lambda off, b=base: self.read_at(b + off, "f32"),
                   "ri": lambda off, b=base: self.read_at(b + off, "i32")}
            try:
                dv = eval(d["formula"], {"__builtins__": {}}, env)
            except Exception as ex:
                print("    derived %s: formula failed (%s)" % (d["note"], ex)); good = False; continue
            if img is not None and e["scope"] == "exe":
                pv = img.value(da, d["type"])
                if pv is not None and close(pv, dv, d["type"]):
                    dv = pv                                     # exact pristine bytes on a reset
            dold = self.read_at(da, d["type"])
            dback = self.write_at(da, d["type"], dv, e["scope"] == "exe")
            dg = close(dback, dv, d["type"])
            good = good and dg
            print("    derived: %s  0x%08x  %s -> %s%s" % (d["note"], da, "%.6g" % dold if dold is not None else "n/a",
                                                          "%.6g" % dback if dback is not None else "n/a", "" if dg else "   FAILED"))
        return good


# ---------------------------------------------------------------- commands

def entries_in(cat, group):
    return [e for e in cat["entries"] if not group or e["group"] == group]


def cmd_list(cat, g, img, group, offline):
    es = entries_in(cat, group)
    if not es:
        sys.exit("no entries in group %r (try: groups)" % group)
    col = "image" if offline else "live"
    print("%-30s %-44s %12s %12s  %s" % ("id", "name", col, "default", "unit"))
    changed = 0
    for e in es:
        if offline:
            v = img.value(e["_addr"], e["type"]) if (img and e["scope"] == "exe") else None
        else:
            v = g.read(e)
        dflt = e["default"]
        mark = ""
        if dflt is not None and v is not None and not close(v, dflt, e["type"]):
            mark = " *"; changed += 1
        tag = "" if e["scope"] == "exe" else "  [%s%s]" % (e["scope"], "" if "slot" not in e else " %d" % e["slot"])
        print("%-30s %-44s %12s %12s  %s%s%s" % (e["id"], e["name"][:44], fmt_val(e, v), fmt_val(e, dflt) if dflt is not None else "per car",
                                                 e.get("unit", ""), tag, mark))
    print("%d entries%s" % (len(es), ", %d differ from default (*)" % changed if changed else ""))
    if offline and img:
        ok, bad, rows = verify(cat, img)
        nexe = sum(1 for e in cat["entries"] if e["scope"] == "exe")
        print("\nverification against %s (md5 %s): %d of %d exe-scope defaults match the pristine image; "
              "%d entity/component entries are per car (not verifiable offline)"
              % (os.path.basename(img.path), img.md5, ok, nexe, len(cat["entries"]) - nexe))
        for iid, want, got, sec, wsec in bad:
            print("  MISMATCH %-40s catalogue %s, image %s (section %s, catalogue says %s)" % (iid, want, got, sec, wsec))
        by_sec = {}
        for e, iv, sec, good in rows:
            by_sec[sec] = by_sec.get(sec, 0) + 1
        print("  sections: " + ", ".join("%s %d" % kv for kv in sorted(by_sec.items(), key=lambda kv: str(kv[0]))))


def cmd_groups(cat):
    counts = {}
    for e in cat["entries"]:
        counts[e["group"]] = counts.get(e["group"], 0) + 1
    for k, n in counts.items():
        print("  %-12s %3d" % (k, n))


def cmd_get(cat, g, img, iid, offline):
    e = cat["_ids"].get(iid) or sys.exit("unknown id %s" % iid)
    v = (img.value(e["_addr"], e["type"]) if img and e["scope"] == "exe" else None) if offline else g.read(e)
    a = e["_addr"] if offline or e["scope"] == "exe" else g.addr_of(e)
    print("%s  (%s / %s)" % (e["id"], e["group"], e["name"]))
    print("  scope %s%s  address %s  type %s  section %s" % (e["scope"], " slot %d" % e["slot"] if "slot" in e else "",
                                                             "0x%08x" % a if a else e["addr"] + " (unresolved)", e["type"], e.get("section", "-")))
    print("  %s: %s   default: %s   unit: %s   sane range: [%s, %s]" % ("image" if offline else "live", fmt_val(e, v),
                                                                     fmt_val(e, e["default"]) if e["default"] is not None else "per car",
                                                                     e.get("unit", ""), e.get("min"), e.get("max")))
    print("  meaning: %s" % e["meaning"])
    print("  spec: %s" % e["spec"])
    for d in e.get("derived", []):
        print("  derived: %s   (%s)" % (d["note"], d["formula"]))


def parse_value(e, s):
    return float(s) if e["type"] in ("f32", "f64") else int(s, 0)


def cmd_set(cat, g, args, force):
    if len(args) < 2:
        sys.exit("set <id> <value>")
    e = cat["_ids"].get(args[0]) or sys.exit("unknown id %s" % args[0])
    g.apply(e, parse_value(e, args[1]), force)


def default_for(e, img):
    if e["default"] is None:
        return None
    if img and e["scope"] == "exe":
        iv = img.value(e["_addr"], e["type"])
        if iv is not None and close(iv, e["default"], e["type"]):
            return iv                                            # exact pristine bytes
    return e["default"]


def cmd_reset(cat, g, img, args):
    if not args:
        sys.exit("reset <id>|all")
    es = [e for e in cat["entries"] if e["scope"] == "exe"] if args[0] == "all" else [cat["_ids"].get(args[0]) or sys.exit("unknown id %s" % args[0])]
    n = 0
    for e in es:
        d = default_for(e, img)
        if d is None:
            print("  %s: per-car value, no fixed default (restore it with preset load)" % e["id"]); continue
        cur = g.read(e)
        if args[0] == "all" and close(cur, d, e["type"]):
            continue
        g.apply(e, d, force=True, img=img); n += 1
    if args[0] == "all":
        print("%d exe-scope entries reset%s" % (n, "" if n else " (nothing differed)"))


def cmd_preset(cat, g, img, args, force):
    if len(args) < 2 or args[0] not in ("save", "load"):
        sys.exit("preset save <file> [id ...] | preset load <file>")
    path = args[1]
    if args[0] == "save":
        ids = args[2:]
        out = {}
        for e in cat["entries"]:
            if ids and e["id"] not in ids:
                continue
            v = g.read(e)
            if v is None:
                continue
            if not ids and (e["scope"] != "exe" or close(v, e["default"], e["type"])):
                continue                                         # default: only changed exe entries
            out[e["id"]] = v
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
        print("saved %d values to %s" % (len(out), path))
    else:
        with open(path, encoding="utf-8") as f:
            pre = json.load(f)
        good = 0
        for iid, v in pre.items():
            e = cat["_ids"].get(iid)
            if not e:
                print("  %s: not in the catalogue, skipped" % iid); continue
            good += bool(g.apply(e, v, force))
        print("%d of %d preset values applied and read back" % (good, len(pre)))


def cmd_watch(cat, g, ids):
    es = [cat["_ids"].get(i) or sys.exit("unknown id %s" % i) for i in ids] or sys.exit("watch <id>...")
    print("  ".join("%s" % e["id"] for e in es) + "   (Ctrl-C stops)")
    try:
        while True:
            print("  ".join("%s=%s" % (e["id"], fmt_val(e, g.read(e))) for e in es), flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass


def cmd_dump(cat, g):
    out = {}
    for e in cat["entries"]:
        v = g.read(e)
        out[e["id"]] = {"live": v, "default": e["default"], "unit": e.get("unit", ""), "scope": e["scope"],
                        "changed": bool(e["default"] is not None and v is not None and not close(v, e["default"], e["type"]))}
    print(json.dumps(out, indent=1))


def main():
    argv = sys.argv[1:]
    offline, force, allow_any, image = "--offline" in argv, "--force" in argv, "--any" in argv, None
    if "--image" in argv:
        i = argv.index("--image"); image = argv[i + 1]; del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__); return
    cat = load_catalogue()
    img = open_image(cat, image)
    cmd, rest = args[0], args[1:]
    if cmd == "groups":
        cmd_groups(cat); return
    if offline:
        if img is None:
            sys.exit("--offline needs the pristine image (%s); pass --image <path>" % cat["image"]["path"])
        if cmd == "list":
            cmd_list(cat, None, img, rest[0] if rest else None, True)
        elif cmd == "get":
            cmd_get(cat, None, img, rest[0] if rest else sys.exit("get <id>"), True)
        else:
            sys.exit("--offline supports list, get and groups only")
        return
    pid, path = i76trainer.find_game(allow_any)
    print("attached to %s (pid %d)%s" % (path, pid, "" if img else "   [no pristine image: resets use catalogue defaults]"))
    g = Tuner(pid, cat)
    if cmd == "list":
        cmd_list(cat, g, img, rest[0] if rest else None, False)
    elif cmd == "get":
        cmd_get(cat, g, img, rest[0] if rest else sys.exit("get <id>"), False)
    elif cmd == "set":
        cmd_set(cat, g, rest, force)
    elif cmd == "reset":
        cmd_reset(cat, g, img, rest)
    elif cmd == "preset":
        cmd_preset(cat, g, img, rest, force)
    elif cmd == "watch":
        cmd_watch(cat, g, rest)
    elif cmd == "dump":
        cmd_dump(cat, g)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
