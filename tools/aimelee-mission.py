#!/usr/bin/env python3
"""Build a network-melee arena with computer opponents (AI melee M1, docs/records/AI-MELEE-M1-2026-10-19.md).

    tools/aimelee-mission.py <stock arena .msn> <out .lvl> --count N --title "Hope Springs (4 AI)" [--zfs I76.ZFS]
    tools/aimelee-mission.py --install "<game folder>"      build every arena in ARENAS into ADDON (lower case)
    tools/aimelee-mission.py --remove  "<game folder>"      delete the ones --install made (marker files)

A stock melee arena (miss16\\Mnn.MSN, its spawn / regen points untouched) plus N AI cars:
  - ODEF OBJ records (100 B, class 1 = car, the record the campaign missions use for their AI cars), the label = the
    car's .vcf stem, e.g. 'vfcoupe2' -> vfcoupe2.vcf. Only multiplayer car variants stored in I76.ZFS are used
    (i76car.def stems x the numbered variants the ZFS holds: 67 in the GOG archive md5 6dd57b16, the same on every pack
    machine), never an ADDON .vcf (those differ between machines and the .lvl CRC does not cover them). The pick is the
    stock AUTO MELEE rule (a random car from the multiplayer list) with a fixed seed per file, so every build of a
    file is byte-identical;
  - team 7 (objFlags bits 16..18 = ODEF +0x62, "Men In Black"), so the AI are one team that is not the humans' default
    team 0; the proxy's tick (I76_AIMELEE) sends each one after the nearest human;
  - placed on the arena's roads (centre line of the RSEG edge pairs), at least 80 m from every spawn and regen point
    (a spawn point within the vehicle radius + 20 m of a car is skipped by 0x451030), 30 m from every scenery
    object, spread out by farthest-point sampling; the yaw follows the road. y is snapped by the loader;
  - distinct instance bits (bit 7 of the label bytes) when a stem repeats;
  - an I76P tag (tools/mp_pool.py) with a parking spot ~8 km away on an empty tile, for AI fill (the host's proxy
    parks one AI car per human beyond the first that the arena holds, I76_AIMELEE_FILL);
  - the WRLD mission title (body +0x13b, read with strcpy by the exe's title callback 0x4b4a10 into the shell's
    32-byte arena record) set; a title longer than 15 characters grows the WRLD body (the in-game loader 0x4b8a10
    reads fixed offsets below +0x13b, the walker skips by the chunk size).
Nothing else changes (no script: the arena's ADEF FSM stays empty).

The file names are lower case on purpose (the shells' ".lvl" test is case-sensitive; an upper-case name skips the
file and CRC check on the joiner, docs/records/COOP-LIST-ENTRIES-2026-10-18.md).
"""
import hashlib, math, os, random, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "re", "tools"))
from i76fmt import bwd2, zfs  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mp_pool  # noqa: E402

# (out file, source arena, AI count, title): the list entries, name first, the AI count in parentheses
ARENAS = [
    ("ai_hs2.lvl", "M07.MSN", 2, "Hope Springs (2 AI)"),
    ("ai_hs4.lvl", "M07.MSN", 4, "Hope Springs (4 AI)"),
    ("ai_hs6.lvl", "M07.MSN", 6, "Hope Springs (6 AI)"),
]
SRC_SUB = "miss16"
MARK = ".aimelee"
AI_TEAM = 7
MIN_SPAWN = 80.0       # metres from a spawn / regen point
MIN_SCENERY = 30.0     # metres from a scenery object
CAR_TAIL = bytes(36) + struct.pack("<II", 1, AI_TEAM << 16)   # body+56..100: 36 unused, class 1, flags (team 7)


def find(folder, name):
    if not os.path.isdir(folder):
        return None
    for f in os.listdir(folder):
        if f.lower() == name.lower():
            return os.path.join(folder, f)
    return None


def car_pool(game):
    """The multiplayer car list (i76car.def: u32 n, n x {u32 id, u32 variants, u32 ?, char stem[16]}) restricted to the
    variants stored in I76.ZFS."""
    raw = open(find(game, "i76car.def"), "rb").read()
    names = set(e.name.lower() for e in zfs.parse(open(find(game, "I76.ZFS"), "rb").read()).entries)
    pool = []
    for i in range(struct.unpack_from("<I", raw, 0)[0]):
        stem = raw[16 + 28 * i:32 + 28 * i].split(b"\0")[0].decode("ascii").lower()
        pool += [stem + str(k) for k in range(1, 10) if stem + str(k) + ".vcf" in names]
    if not pool:
        raise SystemExit("no multiplayer car variants found in I76.ZFS")
    return pool


def label_bytes(stem, inst):
    b = bytearray(stem.encode("ascii")[:8].ljust(8, b"\0"))
    for j in range(8):                                   # instance number in bit 7, lowest bit in the last byte
        if inst >> j & 1:
            b[7 - j] |= 0x80
    return bytes(b)


def positions(doc, n):
    objs = [bwd2.obj(c.body) for c in doc.find("ODEF")[0].children if c.tag_str == "OBJ"]
    starts = [o["pos"] for o in objs if o["class"] == 1 and bwd2.cstr(bytes(x & 0x7f for x in o["raw"][:8])) in ("spawn", "regen")]
    scenery = [o["pos"] for o in objs if o["class"] != 1]
    if not starts:
        raise SystemExit("no spawn points in the arena")
    cands = []
    for c in doc.find("RDEF")[0].children:
        if c.tag_str != "RSEG":
            continue
        pts = bwd2.rseg(c.body)["segments"]
        for k in range(1, len(pts) - 1, 3):
            lx, ly, lz, rx, ry, rz = pts[k]
            x, z = (lx + rx) / 2, (lz + rz) / 2
            nx = (pts[k + 1][0] + pts[k + 1][3]) / 2 - (pts[k - 1][0] + pts[k - 1][3]) / 2
            nz = (pts[k + 1][2] + pts[k + 1][5]) / 2 - (pts[k - 1][2] + pts[k - 1][5]) / 2
            if min(math.hypot(x - s[0], z - s[2]) for s in starts) < MIN_SPAWN:
                continue
            if scenery and min(math.hypot(x - s[0], z - s[2]) for s in scenery) < MIN_SCENERY:
                continue
            cands.append((x, z, math.atan2(nx, nz)))
    # keep to the area the spawn points span (+150 m), so the AI start where the humans play
    x0, x1 = min(s[0] for s in starts) - 150, max(s[0] for s in starts) + 150
    z0, z1 = min(s[2] for s in starts) - 150, max(s[2] for s in starts) + 150
    cands = [c for c in cands if x0 <= c[0] <= x1 and z0 <= c[1] <= z1]
    if len(cands) < n:
        raise SystemExit("only %d road points qualify, %d AI cars wanted" % (len(cands), n))
    cx = sum(s[0] for s in starts) / len(starts); cz = sum(s[2] for s in starts) / len(starts)
    pick = [min(cands, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cz) ** 2)]
    while len(pick) < n:                                 # farthest-point sampling: spread over the arena
        pick.append(max(cands, key=lambda c: min((c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2 for p in pick)))
    y = sum(s[1] for s in starts) / len(starts)
    return [(x, y, z, yaw) for x, z, yaw in pick]


def build(src, dst, count, title, game):
    raw = open(src, "rb").read()
    doc = bwd2.parse(raw)
    if bwd2.serialise(doc) != raw:
        raise SystemExit("%s does not round-trip through the BWD2 parser; refusing" % src)
    pool = car_pool(game)
    rng = random.Random(hashlib.md5(("%s|%d" % (os.path.basename(dst).lower(), count)).encode()).digest())
    cars = [rng.choice(pool) for _ in range(count)]
    odef = doc.find("ODEF")[0]
    seen = {}
    new = []
    where = positions(doc, count)
    parks, _ = mp_pool.park_spots(doc, count)
    for (stem, (x, y, z, yaw)), park in zip(zip(cars, where), parks):
        inst = seen.get(stem, 0); seen[stem] = inst + 1
        c, s = math.cos(yaw), math.sin(yaw)
        b = label_bytes(stem, inst) + struct.pack("<9f", c, 0, -s, 0, 1, 0, s, 0, c) + struct.pack("<3f", x, y, z) + mp_pool.tag(mp_pool.KIND_POOL, 0, b"", park) + CAR_TAIL[36:]
        assert len(b) == 100
        new.append(bwd2.Chunk(b"OBJ\0", b))
    last = max(k for k, c in enumerate(odef.children) if c.tag_str == "OBJ")
    odef.children[last + 1:last + 1] = new
    w = [c for c in doc.find("WDEF")[0].children if c.tag_str == "WRLD"][0]
    body = bytearray(w.body)
    if len(body) != 0x14b:
        raise SystemExit("WRLD body is %d bytes, expected 331" % len(body))
    t = title.encode("ascii")
    if len(t) > 31:
        raise SystemExit("title: at most 31 characters (the shell's arena record holds 32 with the NUL)")
    body[0x13b:] = t.ljust(16 if len(t) <= 15 else 32, b"\0")   # as coop-mission.py: a long title grows the body by 16
    w.body = bytes(body)
    out = bwd2.serialise(doc)
    open(dst, "wb").write(out)
    return cars, [(round(x, 1), round(z, 1)) for x, _, z, _ in where]


def install(game):
    src_dir = find(game, SRC_SUB)
    if not src_dir:
        raise SystemExit("no %s folder in %s" % (SRC_SUB, game))
    addon = find(game, "ADDON") or os.path.join(game, "ADDON")
    os.makedirs(addon, exist_ok=True)
    for name, src, n, title in ARENAS:
        old, mark = find(addon, name), find(addon, name + MARK)
        if old and not mark:
            raise SystemExit("%s exists and is not ours - refusing" % old)
        if old:                                          # ours: delete first, NTFS keeps an old name's case on overwrite
            os.remove(old); os.remove(mark)
        s = find(src_dir, src)
        if not s:
            raise SystemExit("missing %s\\%s" % (SRC_SUB, src))
        dst = os.path.join(addon, name)
        cars, pos = build(s, dst, n, title, game)
        open(dst + MARK, "w").write("installed by tools/aimelee-mission.py\n")
        print("ADDON\\%s \"%s\" %s: %s at %s" % (name, title, hashlib.md5(open(dst, "rb").read()).hexdigest()[:8],
                                                 ", ".join(cars), pos))


def remove(game):
    addon = find(game, "ADDON")
    n = 0
    for f in sorted(os.listdir(addon)) if addon else []:
        if f.endswith(MARK):
            t = os.path.join(addon, f[:-len(MARK)])
            if os.path.exists(t):
                os.remove(t)
            os.remove(os.path.join(addon, f)); n += 1
    print("ADDON: removed %d AI melee arenas" % n)


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "--install":
        return install(a[1])
    if a[0] == "--remove":
        return remove(a[1])
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--game", help="game folder holding i76car.def and I76.ZFS (default: two levels above src)")
    o = ap.parse_args(a)
    game = o.game or os.path.dirname(os.path.dirname(os.path.abspath(o.src)))
    cars, pos = build(o.src, o.dst, o.count, o.title, game)
    print("%s -> %s: %s at %s" % (o.src, o.dst, ", ".join(cars), pos))


if __name__ == "__main__":
    main()
