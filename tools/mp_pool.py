"""Pre-spawned car pools for network games (docs/records/MP-OVERNIGHT-2026-10-20.md).

Shared by tools/aimelee-mission.py (AI fill: the arena's AI cars carry a parking spot) and tools/coop-mission.py
--copies (co-op scaling: k dormant copies of every enemy car, parked far from play). No car is ever created after
the mission loads: every car a joiner will see is an ODEF object of the file, so the stock load and the proxy's 'AT'
sync (label table index) carry it. The host's proxy (music-fix/mpfill.c) reads the tags below from the .lvl it
loaded and moves cars between their parking spot and the game.

Tag, in the 36 unused bytes of an ODEF OBJ body (body+56..92; FORMATS.md: never read by the loader):
    +56  b"I76P"
    +60  u8 kind (1 = AI-fill pool car, 2 = co-op copy)
    +61  u8 copy number j (kind 2: 1..k; the copy is used once j joiners are present)
    +62  u16 0
    +64  original label[8] (kind 2: the raw 8 label bytes of the car it copies; kind 1: zero)
    +72  f32 park x, f32 park z (where the host parks the car while it is not in the game)
    +80  12 zero bytes

Parking: an EMPTY tile (ZMAP: tile = (int(x // 640), int(z // 640)), grid index tz * 80 + tx, 0xff = no terrain;
fitted on coop01 / coop13 / ai_hs4, every object inside) with no terrain within 2 tiles, as far as possible from every
ODEF object and road point of the mission (park_spots); cars in a 25 m grid around the tile's centre.
"""
import math, struct

TAG = b"I76P"
KIND_POOL, KIND_COPY = 1, 2
TILE = 640.0
PARK_DIST, PARK_MIN = 8000.0, 6000.0    # metres from the nearest object / road: beyond every far clip (600 .. 1800)


def tag(kind, j=0, orig=b"", park=(0.0, 0.0)):
    b = TAG + struct.pack("<BBH", kind, j, 0) + bytes(orig[:8]).ljust(8, b"\0") + struct.pack("<2f", *park) + bytes(12)
    assert len(b) == 36
    return b


def read_tag(body):
    if len(body) < 92 or body[56:60] != TAG:
        return None
    kind, j, _ = struct.unpack_from("<BBH", body, 60)
    px, pz = struct.unpack_from("<2f", body, 72)
    return {"kind": kind, "j": j, "orig": bytes(body[64:72]), "park": (px, pz)}


def _grid(doc):
    from i76fmt import bwd2
    return bwd2.zmap(doc.find("TDEF")[0].find("ZMAP")[0].body)["grid"]


def landmarks(doc):
    from i76fmt import bwd2
    pts = [(o["pos"][0], o["pos"][2]) for o in
           (bwd2.obj(c.body) for c in doc.find("ODEF")[0].children if c.tag_str == "OBJ")]
    for c in doc.find("RDEF")[0].children:
        if c.tag_str == "RSEG":
            for s in bwd2.rseg(c.body)["segments"][::4]:
                pts.append(((s[0] + s[3]) / 2, (s[2] + s[5]) / 2))
    return pts


def park_spots(doc, n, spacing=25.0):
    """n parking positions (x, z) on one remote tile with NO terrain, and its distance to the nearest landmark (m).

    Every one of the world's 128 x 128 tile slots that the mission's ZMAP leaves empty points at one shared tile
    (0x493080 fills the table 0x644380 with 0x59c588 before the 80 x 80 ZMAP is placed at slot (24, 24)), so a void
    tile is flat ground at height 0 (the samplers 0x493160 / 0x493550 read it like any other; outside the 80 x 80
    grid they return 0). The missions use 12-48 of the 6400 tiles, so a void tile 5+ km from everything always
    exists (the spot nearest PARK_DIST, never under PARK_MIN): beyond every draw distance, the radar (600 m) and every AI's reach."""
    g = _grid(doc)
    lm = landmarks(doc)
    best = None
    for tz in range(4, 76):
        for tx in range(4, 76):
            if any(g[(tz + b) * 80 + tx + a] != 0xff for a in (-2, -1, 0, 1, 2) for b in (-2, -1, 0, 1, 2)):
                continue
            cx, cz = (tx + 0.5) * TILE, (tz + 0.5) * TILE
            d = min(math.hypot(cx - x, cz - z) for x, z in lm)
            key = abs(d - PARK_DIST) if d >= PARK_MIN else 1e9 - d   # nearest to PARK_DIST, never under PARK_MIN
            if best is None or key < best[0]:
                best = (key, d, cx, cz)
    if best is None or best[1] < 3000:
        raise SystemExit("no empty tile 3 km from the mission to park cars on")
    best = best[1:]
    d, cx, cz = best
    side = max(1, math.ceil(math.sqrt(n)))
    if side * spacing > TILE - 2 * spacing:
        raise SystemExit("%d cars do not fit on one tile at %.0f m" % (n, spacing))
    out = []
    for i in range(n):
        r, c = divmod(i, side)
        out.append((cx + (c - (side - 1) / 2) * spacing, cz + (r - (side - 1) / 2) * spacing))
    return out, d


def label_inst(raw):
    """(stem, instance number) of 8 raw label bytes (bit 7 of each byte, lowest bit in the last byte)."""
    stem = bytes(x & 0x7f for x in raw[:8]).split(b"\0")[0].decode("latin1")
    return stem, sum(((raw[7 - j] >> 7) & 1) << j for j in range(8))


def label_bytes(stem, inst):
    b = bytearray(stem.encode("ascii")[:8].ljust(8, b"\0"))
    for j in range(8):
        if inst >> j & 1:
            b[7 - j] |= 0x80
    return bytes(b)
