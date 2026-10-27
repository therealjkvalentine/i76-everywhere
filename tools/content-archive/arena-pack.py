r"""arena-pack.py - stage a community arena for Gold's ADDON\ (or Nitro's miss8/miss16 + addon) with a readable title.

    python -I tools/content-archive/arena-pack.py show  <map>...                      # layout + what the title peek reads
    python -I tools/content-archive/arena-pack.py gold  <map.lvl|.cbt> <lab game dir> --name rageco [--title ..] [--raw]
    python -I tools/content-archive/arena-pack.py nitro <miss16 map> <lab game dir> --miss8 <8-bit map> --name gumball

Why: 409 community mission files (every LSM i76comb* arena, the 1997 Activision bonus maps) are I76EDIT-1997 files,
WREV 8. Measured 2026-10-24 (docs/research/CONTENT-FEASIBILITY-2026-10-25.md s.2): their WRLD is 318 bytes and lacks ONE field,
the 13-byte horizon .hzd name at body +0x86 (Gold/Nitro WREV 9 = 331 bytes); the author's title is there, 13 bytes
early (+0x12e). Every 1997 exe (demo, 1.05, 1.06, 1.081, 1.083) expects WREV 8; Gold and Nitro expect WREV 9 (REV table
0x500438: VERW 9) and read WRLD at fixed offsets (0x4b8a10: hour body +0x93, surfaces +0x97, far clip +0x137; title
peek 0x4b4a10: strcpy from body +0x13b). So in Gold a raw WREV 8 map reads every field after the 8th name 13 bytes
off: the horizon name is the hour's bytes, the hour and the 8 surface-physics records are shifted, the far clip is
read from the title text, and the arena list shows an empty name (or the title's last characters).
This tool:
  - refuses a file that does not round-trip byte-exact through the BWD2 container parser (re/tools/i76fmt);
  - WRLD 318 B (WREV 8) -> inserts a horizon name at body +0x86 (--hzd, default: the horizon of the stock miss8
    mission with the same palette, else empty as stock M15) and sets WREV 9; every other byte keeps its value, so
    the author's own title lands at +0x13b; --title replaces it (16 bytes, grown to 32 for 16-31 characters, as
    tools/coop-mission.py --title; the loader never reads past +0x13b);
  - WRLD 331 / 347 B (WREV 9) -> only --title, if given;
  - writes the mission under a lower-case name (the join CRC check only runs for a lower-case ".lvl",
    records/COOP-LIST-ENTRIES-2026-10-18.md s.1), copies every terrain the ZONE chunks name from beside the source;
  - re-parses the output and prints what the shell will read.
Nothing else in the file changes. Lab copies only (guarded): never the daily driver / golden / LAN / release candidate.
"""
import argparse, os, shutil, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "re", "tools"))
from i76fmt import bwd2  # noqa: E402

FORBIDDEN = ("daily-driver", "golden", "\\lan", "/lan", "release-candidate", "interstate76-2026-10-03", "interstate76-lan")
# palette -> horizon of the stock Gold miss8 mission with that palette (sandbox-gog main miss8, read 2026-10-24)
STOCK_HZD = {"t17": "p01.HZD", "t09": "p01.HZD", "t06": "p04.HZD", "t02": "p01.HZD", "t01": "p01.HZD", "t08": "p04.HZD",
             "t03": "p01.HZD", "t11": "p01.HZD", "t12": "p04.HZD", "t15": "p02.HZD", "m05": "n02.HZD", "m15": "",
             "t04": "t01.hzd", "t05": "t05.HZD", "t07": "t07.HZD", "t10": "t10.HZD", "t13": "t13.HZD", "t14": "t14.HZD",
             "t16": "p02.hzd"}


def load(path):
    raw = open(path, "rb").read()
    doc = bwd2.parse(raw)
    if bwd2.serialise(doc) != raw:
        raise SystemExit("%s does not round-trip through the BWD2 parser; refusing" % path)
    return raw, doc


def wdef_parts(doc):
    wdef = doc.find("WDEF")[0]
    wrev = [c for c in wdef.children if c.tag_str == "WREV"][0]
    wrld = [c for c in wdef.children if c.tag_str == "WRLD"][0]
    return wdef, wrev, wrld


def shell_title(raw, doc):
    """What Gold's title peek gets: strcpy from WRLD body +0x13b, bytes up to the first NUL wherever they are (max 31)."""
    _, _, wrld = wdef_parts(doc)
    p = wrld.offset + 8 + 0x13b
    end = raw.find(b"\0", p)
    return raw[p:end if end >= 0 else len(raw)][:31]


def gold_reads(body):
    """The fields Gold's WRLD loader takes at its fixed offsets, from this body (for the show mode)."""
    hz = body[0x86:0x93].split(b"\0")[0]
    hour = struct.unpack_from("<I", body, 0x93)[0] if len(body) >= 0x97 else None
    far = struct.unpack_from("<i", body, 0x137)[0] if len(body) >= 0x13b else None
    grip0 = struct.unpack_from("<f", body, 0x97)[0] if len(body) >= 0x9b else None
    return hz, hour, far, grip0


def zones(doc):
    out = []
    for c, _ in doc.walk():
        if c.tag_str == "ZONE":
            out.append(c.body[1:].split(b"\0")[0].decode("latin1"))
    return out


def convert(doc, title, hzd=None):
    _, wrev, wrld = wdef_parts(doc)
    body = bytes(wrld.body)
    before = (len(body), struct.unpack_from("<I", wrev.body, 0)[0])
    if len(body) == 318 and before[1] == 8:   # I76EDIT 1997 / retail 1.0x layout: no horizon name
        if hzd is None:
            pal = body[0x1e:0x2b].split(b"\0")[0].decode("latin1").lower()
            hzd = STOCK_HZD.get(os.path.splitext(pal)[0], "")
        h = hzd.encode("ascii")
        if len(h) > 12:
            raise SystemExit("--hzd: at most 12 characters")
        body = body[:0x86] + h.ljust(13, b"\0") + body[0x86:]
        wrev.body = struct.pack("<I", 9) + wrev.body[4:]
    elif len(body) not in (0x14b, 0x15b):
        raise SystemExit("WRLD body is %d bytes, WREV %d (expected 318/8 or 331/9); refusing" % (len(body), before[1]))
    if title:
        t = title.encode("ascii")
        if not 0 < len(t) <= 31:
            raise SystemExit("--title: 1..31 ASCII characters (the shell's arena record holds title[32])")
        body = body[:0x13b] + t.ljust(32 if len(t) > 15 else 16, b"\0")
    wrld.body = body
    return before, (len(body), struct.unpack_from("<I", wrev.body, 0)[0]), hzd


def find_beside(src_dir, name):
    for f in os.listdir(src_dir):
        if f.lower() == name.lower():
            return os.path.join(src_dir, f)
    return None


def guard(game_dir):
    g = os.path.abspath(game_dir).lower()
    if "i76-uncap-lab" not in g or any(x in g for x in FORBIDDEN):
        raise SystemExit("refusing: %s is not a lab copy (i76-uncap-lab\\exp-*)" % game_dir)


def stage(src, dst_path, title, hzd=None, raw_copy=False):
    raw, doc = load(src)
    old = shell_title(raw, doc)
    if raw_copy:                           # the control: the file as published, only renamed
        open(dst_path, "wb").write(raw)
        print("  %s -> %s: copied unchanged (control); shell title %r" % (os.path.basename(src), dst_path, old))
        return doc
    before, after, hz = convert(doc, title, hzd)
    out = bwd2.serialise(doc)
    open(dst_path, "wb").write(out)
    raw2, doc2 = load(dst_path)          # read back
    new = shell_title(raw2, doc2)
    print("  %s -> %s: WRLD %d B WREV %d -> WRLD %d B WREV %d (horizon %r); shell title %r -> %r; %d -> %d bytes"
          % (os.path.basename(src), dst_path, before[0], before[1], after[0], after[1], hz, old, new, len(raw), len(out)))
    return doc2


def copy_terrain(doc, src_dir, dst_dir):
    for z in zones(doc):
        f = find_beside(src_dir, z)
        if not f:
            print("  WARNING: terrain %s not beside the source (stock terrain, or missing)" % z)
            continue
        d = os.path.join(dst_dir, os.path.basename(f).lower())
        shutil.copyfile(f, d)
        print("  terrain %s -> %s" % (f, d))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=("show", "gold", "nitro"))
    ap.add_argument("src", nargs="+")
    ap.add_argument("--name", help="lower-case stem for the staged file")
    ap.add_argument("--title", help="mission title for the arena list (1..31 characters; default: the author's)")
    ap.add_argument("--hzd", help="horizon .hzd name to insert into a WREV 8 file (default: by palette, see STOCK_HZD)")
    ap.add_argument("--raw", action="store_true", help="copy the map unchanged (the control), only renamed")
    ap.add_argument("--miss8", help="nitro: the 8-bit copy of the map (default: the miss16 file in both folders)")
    a = ap.parse_args()
    if a.mode == "show":
        for s in a.src:
            raw, doc = load(s)
            _, wrev, wrld = wdef_parts(doc)
            hz, hour, far, grip0 = gold_reads(wrld.body)
            print("%s: WREV %d, WRLD %d B, zones %s; Gold reads: title %r, horizon %r, hour %s, far clip %s, grip[0] %.3g"
                  % (s, struct.unpack_from("<I", wrev.body, 0)[0], len(wrld.body), zones(doc), shell_title(raw, doc),
                     hz, hour, far, grip0))
        return
    if len(a.src) != 2 or not a.name:
        raise SystemExit("gold / nitro: <map> <game dir> --name <stem>")
    src, game = a.src
    guard(game)
    name = a.name.lower()
    if a.mode == "gold":
        addon = os.path.join(game, "ADDON")
        doc = stage(src, os.path.join(addon, name + ".lvl"), a.title, a.hzd, a.raw)
        copy_terrain(doc, os.path.dirname(src), addon)
    else:
        ext = os.path.splitext(src)[1].lower()
        doc = stage(src, os.path.join(game, "miss16", name + ext), a.title, a.hzd, a.raw)
        stage(a.miss8 or src, os.path.join(game, "miss8", name + ext), a.title, a.hzd, a.raw)
        copy_terrain(doc, os.path.dirname(src), os.path.join(game, "addon"))
        if a.miss8:
            copy_terrain(doc, os.path.dirname(a.miss8), os.path.join(game, "addon"))


if __name__ == "__main__":
    main()
