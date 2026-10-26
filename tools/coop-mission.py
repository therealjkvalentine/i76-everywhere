#!/usr/bin/env python3
"""Turn a campaign mission into one a network game can load (the co-op spike, docs/research/COOP-SPIKE.md).

    tools/coop-mission.py T01.MSN COOP01.LVL [--spacing 30] [--count 2] [--keep-movies] [--title "Co-op Scene 1"]

Reads a mission (.msn, BWD2) and writes a copy with:
  - N 'spawn' objects (ODEF OBJ, class 1, the same record the melee arenas use) in a row beside the mission's player
    object, `spacing` metres apart along +x and 8 m up, so each network player gets a start point;
  - the WRLD intro and outro movie names blanked (body offsets 4 and 17, 13 bytes each), because an in-mission movie
    stops the network pump and the host drops a joiner that is still watching it.
  - with --title, the WRLD mission title (body +0x13b; 16 bytes, or 32 with the body grown by 16 for a title over 15
    characters; read only by the shell's arena list) set, so the file
    can sit in ADDON as its own multiplayer arena (the shell lists every ADDON\\*.lvl after the 15 stock arenas).
  - with --copies K (co-op scaling, docs/records/MP-OVERNIGHT-2026-10-20.md): K dormant copies of every enemy car
    (class 1, team neither 0 nor the player object's, not a trailer), each with the same record but the next free
    instance number, team 0 (so the script's allEnemyDead / isWithinEnemy, which walk teams 1..7, never see them) and
    an I76P tag (tools/mp_pool.py: copy number j, the original's label, its parking spot), placed on a remote parking
    tile. The host's proxy (I76_COOP_SCALE) brings copy j beside its original when the original first engages a human
    and j joiners are present; without joiners the copies stay parked and the mission plays as before.
tools/coop-install.py installs all 17 that way. Nothing else in the mission changes; the script and AI still run on
each machine.
"""
import argparse, os, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "re", "tools"))
from i76fmt import bwd2  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mp_pool  # noqa: E402

SPAWN_ROT = bytes.fromhex("f638f83e0000000014e75fbf000000000000803f0000000014e75f3f00000000f638f83e")   # 3x3 rotation of M01's first spawn record
SPAWN_TAIL = bytes.fromhex("00" * 36 + "01000000" + "00" * 4)   # body+56..100 of M01's spawn records (class 1 at +92)


def player_object(odef):
    for c in odef.children:
        if c.tag_str == "OBJ" and len(c.body) >= 100 and c.body[96] & 0x10:   # objFlags bit 0x10 = player
            return c
    raise SystemExit("no player object (objFlags bit 0x10) in ODEF")


def add_copies(odef, doc, pl, k):
    """k parked copies of every enemy car (module docstring)."""
    pteam = (struct.unpack_from("<I", pl.body, 96)[0] >> 16) & 7
    objs = [c for c in odef.children if c.tag_str == "OBJ"]
    used = {}
    for c in objs:
        stem, inst = mp_pool.label_inst(c.body)
        used.setdefault(stem, set()).add(inst)
    enemies = []
    for c in objs:
        b = c.body
        if len(b) < 100 or struct.unpack_from("<I", b, 92)[0] != 1:
            continue
        fl = struct.unpack_from("<I", b, 96)[0]
        stem, _ = mp_pool.label_inst(b)
        team = (fl >> 16) & 7
        if fl & 0x10 or team in (0, pteam) or stem in ("spawn", "regen") or "tlr" in stem:
            continue
        enemies.append(c)
    spots, dist = mp_pool.park_spots(doc, len(enemies) * k)
    new = []
    for j in range(1, k + 1):
        for e in enemies:
            stem, _ = mp_pool.label_inst(e.body)
            inst = max(used[stem]) + 1
            used[stem].add(inst)
            x, z = spots[len(new)]
            b = bytearray(e.body[:100])
            b[0:8] = mp_pool.label_bytes(stem, inst)
            struct.pack_into("<3f", b, 44, x, struct.unpack_from("<f", e.body, 48)[0], z)
            b[56:92] = mp_pool.tag(mp_pool.KIND_COPY, j, e.body[:8], (x, z))
            fl = struct.unpack_from("<I", b, 96)[0] & ~0x70000
            struct.pack_into("<I", b, 96, fl)
            new.append(bwd2.Chunk(b"OBJ\0", bytes(b)))
    last = max(i for i, c in enumerate(odef.children) if c.tag_str == "OBJ")
    odef.children[last + 1:last + 1] = new
    print("copies: %d enemy cars x %d = %d parked copies, %.0f m from the nearest object or road (%s)" %
          (len(enemies), k, len(new), dist, ", ".join(mp_pool.label_inst(e.body)[0] for e in enemies)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--spacing", type=float, default=30.0, help="metres between spawn points (default 30)")
    ap.add_argument("--count", type=int, default=2, help="spawn points to add (default 2)")
    ap.add_argument("--keep-movies", action="store_true", help="leave the intro/outro movies in")
    ap.add_argument("--copies", type=int, default=0, help="dormant copies per enemy car for co-op scaling (default 0)")
    ap.add_argument("--title", help="WRLD mission title for the multiplayer arena list (at most 31 characters)")
    a = ap.parse_args()
    raw = open(a.src, "rb").read()
    doc = bwd2.parse(raw)
    if bwd2.serialise(doc) != raw:
        raise SystemExit("this file does not round-trip through the BWD2 parser; refusing")
    odef = doc.find("ODEF")[0]
    pl = player_object(odef)
    px, py, pz = struct.unpack_from("<3f", pl.body, 44)
    new = []
    for i in range(a.count):
        b = bytearray(pl.body[:100])
        b[0:8] = b"spawn\0\0\0"
        b[8:44] = SPAWN_ROT
        struct.pack_into("<3f", b, 44, px + a.spacing * (i + 1), py + 8.0, pz)
        b[56:100] = SPAWN_TAIL
        new.append(bwd2.Chunk(b"OBJ\0", bytes(b)))
    last = max(k for k, c in enumerate(odef.children) if c.tag_str == "OBJ")
    odef.children[last + 1:last + 1] = new
    if a.copies > 0:
        add_copies(odef, doc, pl, a.copies)
    if not a.keep_movies:
        w = [c for c in doc.find("WDEF")[0].children if c.tag_str == "WRLD"][0]
        body = bytearray(w.body)
        print("movies removed: %r %r" % (bytes(body[4:17]).split(b"\0")[0], bytes(body[17:30]).split(b"\0")[0]))
        body[4:30] = bytes(26)
        w.body = bytes(body)
    if a.title is not None:
        t = a.title.encode("ascii")
        if len(t) > 31:
            raise SystemExit("--title: at most 31 characters (the shell's arena record holds title[32])")
        w = [c for c in doc.find("WDEF")[0].children if c.tag_str == "WRLD"][0]
        body = bytearray(w.body)
        if len(body) != 0x14b:
            raise SystemExit("WRLD body is %d bytes, expected 331; refusing to set a title" % len(body))
        # The stock field is the last 16 bytes of the body. The arena list reads it with strcpy from the chunk
        # (exe 0x4b4a10: chunk +0x143 = body +0x13b) and the shell keeps 31 characters (strncpy 0x20, 0x10027ea0),
        # so a longer title grows the body by 16 bytes; the mission loader reads WRLD by fixed offsets up to body
        # +0x137 (0x4b8a10) and never sees the tail (records/COOP-LIST-ENTRIES-2026-10-18.md section 8).
        if len(t) > 15:
            body = body[:0x13b] + t.ljust(32, b"\0")
        else:
            body[0x13b:0x14b] = t.ljust(16, b"\0")
        w.body = bytes(body)
    out = bwd2.serialise(doc)
    open(a.dst, "wb").write(out)
    print("%s -> %s: %d spawn points at x %s, y %.1f, z %.1f" % (a.src, a.dst, a.count,
          ", ".join("%.1f" % (px + a.spacing * (i + 1)) for i in range(a.count)), py + 8.0, pz))


if __name__ == "__main__":
    main()
