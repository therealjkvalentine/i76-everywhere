#!/usr/bin/env python3
"""cockpit_split.py - double the static cockpit dash under Glide 2 by splitting each 256x128 dash tile into
four 256x128 quarter tiles of a 512x256 version, and re-authoring the dash .geo so each face is cut along the
quadrant lines and every piece samples its own quarter (docs/research/COCKPIT-HIRES-FEASIBILITY.md, option B, stage 1).

Generator only: it reads the owner's own archive (I76.ZFS, an ADDON copy, or an extraction folder) and writes an
ADDON-ready override pair into a folder the owner chooses:
    <out>/<car>g.pak + .pix     every member byte-identical except the dash .geo (e.g. PP51DASH.GEO)
    <out>/zdashN06.pak + .pix   the original ZDASHN01/N02.M16 kept byte-identical (other cars use them) plus
                                eight quarter tiles ZDn01Qij.M16 / ZDn02Qij.M16 (i = u half, j = v half; j = 0 is the
                                panel's lower half as seen)
    <out>/cockpit-split.json    manifest: md5s, sizes, per-face split, every self-check result
Everything written is derived from Activision's data: never commit it (texture-lab/.gitignore keeps out/).

Tile content modes (exactly one):
    --marker         pixel-replicated 2x art with a visible label per quarter ('101-00' = ZDASH101 quarter i=0 j=0;
                     colours red 00, green 10, blue 01, yellow 11; text drawn row-flipped so it reads upright in
                     game, see ORIENTATION), a 2-texel frame in the quarter colour and a 1-texel magenta checker patch only a 2x tile can show.
                     The first boot test.
    --replicate      pixel-replicated 2x, no marker (memory/plumbing control; renders identical to stock).
    --png-dir DIR    real 512x256 upscales named <TILE>.png, e.g. ZDASH101.png, in the STORED orientation
                     (row 0 = v 0, the same orientation i76img decodes; texture-lab/cockpit_mockup.py writes them).

Seams (--seam; the clamp/wrap mode ZGLIDE uses for these faces is not verified, so both are offered):
    overlap (default) - the 512x256 is resampled to 508x252 unique texels; each quarter holds 254x126 of them plus a
                     1-texel border copied from its neighbour (edge-replicated at the outer edges). Remapped UVs keep
                     every bilinear sample inside the tile's own texels, so the result is seam-free under clamp AND
                     wrap. Costs a 0.8 % resample.
    clamp            straight cut of the 512x256; exact when the engine clamps, a 1-texel bleed line under wrap.

UV convention (static read, lab docs/TEXTURE-DELIVERY.md 1): ZGLIDE computes s = u * 255 * (1 or 1/2 ...) in Glide
coordinates that span 256 on the long side, so on a 256x128 tile u 0..1 covers texel coordinates 0..255 and
v 0..1 covers 0..127.5 (K = L * 255/256). The split line is therefore at u = v = 256/510 (= 0.50196), the texel
boundary, not at 0.5, and remapped UVs are u' = (G - N*i + b) / K with G the global texel coordinate in the 2x
(unique) grid, N the unique texels per tile, b the border (0 or 1). --uv-k 256 switches to the ideal mapping.

ORIENTATION: texel row = v * K_t, row 0 is v = 0. On the Piranha dash v = 0 is the bottom edge of the panel
(PP51DASH vertices: y = -0.163 has v = 0), so the stored art is upside down as seen; the stock start-line capture
agrees (the ZDASH102 knob tabs, stored in its last rows, show on the top edge of the dash).

Usage:
  python cockpit_split.py --game <dir with I76.ZFS> --out <folder> --marker
  python cockpit_split.py --game <dir> --out <folder> --png-dir <folder with ZDASH101.png ZDASH102.png>
  [--car-pak vppirnag] [--geo PP51DASH.GEO] [--seam overlap|clamp] [--no-addon] [--extract <loose files dir>]
Refuses an --out that holds i76.exe or I76.ZFS, and the owner's playable installs.
"""
import argparse, hashlib, json, math, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import i76img  # noqa: E402

I76MAP = os.environ.get("I76MAP", (__import__("os").path.expanduser("~") + r"\i76-map"))
TILE_RE = re.compile(r"^ZDASH(\d)0([12])$")
QCOL = {(0, 0): (255, 40, 40), (1, 0): (40, 220, 40), (0, 1): (60, 110, 255), (1, 1): (255, 230, 0)}
MAGENTA = (255, 0, 255)
PROTECTED = (r"\games\interstate76", "i76-everywhere-portable", r"\i76-uncap-lab\game\addon",
             r"\i76-uncap-lab\game-dd-20261003", r"\i76-uncap-lab\golden", r"\sandbox-gog\main\app")


# ---------------------------------------------------------------------------------------------- archive access
class Source:
    """Read members by file name: <game>/ADDON loose copy first (unless no_addon), then <game>/I76.ZFS via
    <re-archive>'s pure-Python reader; or a loose extraction folder."""

    def __init__(self, game=None, extract=None, no_addon=False):
        self.game, self.extract, self.no_addon, self.z, self.used = game, extract, no_addon, None, {}
        if extract:
            self.loose = {n.lower(): os.path.join(extract, n) for n in os.listdir(extract)}
        if game and not extract:
            sys.path.insert(0, os.path.join(I76MAP, "tools"))
            from i76fmt import zfs
            self.z = zfs.parse(open(os.path.join(game, "I76.ZFS"), "rb").read())
            self.ents = {e.name.lower(): e for e in self.z.entries}

    def read(self, name):
        n = name.lower()
        if self.extract:
            self.used[n] = "extract"
            return open(self.loose[n], "rb").read()
        lp = os.path.join(self.game, "ADDON", n)
        if not self.no_addon and os.path.exists(lp):
            self.used[n] = "ADDON"
            return open(lp, "rb").read()
        self.used[n] = "I76.ZFS"
        return self.z.read(self.ents[n])


def parse_pix(data):
    tok = data.decode("latin1").split()
    return [(tok[1 + 3 * i], int(tok[2 + 3 * i]), int(tok[3 + 3 * i])) for i in range(int(tok[0]))]


def pak_members(pak, pix):
    return [(nm, pak[o:o + ln]) for nm, o, ln in parse_pix(pix)]


def build_pak(members):
    """[(NAME, bytes)] -> (pak bytes, pix bytes) in the game's own layout (CRLF, count line, NAME off size)."""
    blob, lines, off = [], [b"%d" % len(members)], 0
    for nm, d in members:
        blob.append(d); lines.append(b"%s %d %d" % (nm.encode("latin1"), off, len(d))); off += len(d)
    return b"".join(blob), b"\r\n".join(lines) + b"\r\n"


# ---------------------------------------------------------------------------------------------- .geo
# Layout (geo_Parse 0x446c90; <re-archive> data/fmt/other_formats.py GEO; flat colour is 3 bytes):
#   'OEG.' u32 w4, name[16], u32 nVerts, u32 nFaces, u32 0; nVerts x f32[3] pos; nVerts x f32[3] normal;
#   per face: u32 index, u32 nCorners, u8[3] rgb, f32[4] plane, u32 0, u8[3] surface, char[13] texture,
#   u32 parent, u32 side, nCorners x {u32 vertex, u32 normal, f32 u, f32 v}
class Geo:
    pass


def parse_geo(d):
    g = Geo()
    if d[:4] != b"OEG.":
        raise ValueError("not a .geo")
    g.w4, = struct.unpack_from("<I", d, 4)
    g.name = d[8:24]
    nv, nf, g.w20 = struct.unpack_from("<3I", d, 24)
    o = 36
    g.verts = [struct.unpack_from("<3f", d, o + 12 * i) for i in range(nv)]; o += 12 * nv
    g.normals = [struct.unpack_from("<3f", d, o + 12 * i) for i in range(nv)]; o += 12 * nv
    g.faces = []
    for _ in range(nf):
        f = {}
        f["index"], n = struct.unpack_from("<2I", d, o); o += 8
        f["rgb"] = d[o:o + 3]; o += 3
        f["plane"] = struct.unpack_from("<4f", d, o); o += 16
        f["zero"], = struct.unpack_from("<I", d, o); o += 4
        f["surface"] = d[o:o + 3]; o += 3
        f["texture"] = d[o:o + 13]; o += 13
        f["parent"], f["side"] = struct.unpack_from("<2I", d, o); o += 8
        f["vrefs"] = [struct.unpack_from("<2I2f", d, o + 16 * k) for k in range(n)]; o += 16 * n
        g.faces.append(f)
    g.tail = d[o:]
    return g


def write_geo(g):
    out = [b"OEG.", struct.pack("<I", g.w4), g.name, struct.pack("<3I", len(g.verts), len(g.faces), g.w20)]
    out += [struct.pack("<3f", *p) for p in g.verts] + [struct.pack("<3f", *n) for n in g.normals]
    for f in g.faces:
        out.append(struct.pack("<2I", f["index"], len(f["vrefs"])) + f["rgb"] + struct.pack("<4f", *f["plane"])
                   + struct.pack("<I", f["zero"]) + f["surface"] + f["texture"] + struct.pack("<2I", f["parent"], f["side"]))
        out += [struct.pack("<2I2f", *r) for r in f["vrefs"]]
    return b"".join(out) + g.tail


def tex_stem(f):
    return f["texture"].split(b"\0")[0].decode("latin1").split(".")[0].upper()


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


# ---------------------------------------------------------------------------------------------- UV mapping
class Axis:
    """One texture axis of the split: L texels per tile (256 or 128), K = engine scale (u -> texel coord on the
    ORIGINAL tile), N unique texels per quarter, b border texels."""

    def __init__(self, L, seam, k_ratio=255 / 256):
        self.L, self.K = L, L * k_ratio
        self.b = 1 if seam == "overlap" else 0
        self.N = L - 2 * self.b
        self.split = self.N / (self.K * 2 * self.N / L)       # = L / (2K): the u where G == N

    def G(self, u):                    # global coordinate in the unique 2N grid
        return u * self.K * 2 * self.N / self.L

    def remap(self, u, i):             # u on the original tile -> u' on quarter i
        return (self.G(u) - self.N * i + self.b) / self.K

    def unmap(self, up, i):            # inverse of remap
        return (up * self.K - self.b + self.N * i) * self.L / (self.K * 2 * self.N)


# ---------------------------------------------------------------------------------------------- clipping
def poly_area2(pts):
    a = 0.0
    for k in range(len(pts)):
        x0, y0 = pts[k]; x1, y1 = pts[(k + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2


def area3(ps):
    sx = sy = sz = 0.0
    for k in range(len(ps)):
        a, b = ps[k], ps[(k + 1) % len(ps)]
        sx += a[1] * b[2] - a[2] * b[1]; sy += a[2] * b[0] - a[0] * b[2]; sz += a[0] * b[1] - a[1] * b[0]
    return 0.5 * math.sqrt(sx * sx + sy * sy + sz * sz)


def affine_residual(g, f):
    """Max |u,v - affine(pos)| over a face's corners (least squares in the face plane). ~0 = UV is affine,
    so linear interpolation of positions along clipped edges is exact."""
    import numpy as np
    P = np.array([g.verts[r[0]] for r in f["vrefs"]], float)
    UV = np.array([(r[2], r[3]) for r in f["vrefs"]], float)
    if len(P) <= 3:
        return 0.0
    c = P.mean(0); Q = P - c
    _, _, vt = np.linalg.svd(Q)
    X = np.c_[Q @ vt[0], Q @ vt[1], np.ones(len(P))]
    coef, *_ = np.linalg.lstsq(X, UV, rcond=None)
    return float(np.abs(X @ coef - UV).max())


class Corner:
    __slots__ = ("pos", "nrm", "u", "v", "vid")

    def __init__(self, pos, nrm, u, v, vid=None):
        self.pos, self.nrm, self.u, self.v, self.vid = pos, nrm, u, v, vid

    def key(self):
        return struct.pack("<3f3f", *self.pos, *self.nrm) if self.vid is None else ("v", self.vid)


def _lerp_corner(a, b, axis, value):
    """Point on edge a-b where the axis coordinate ('u' or 'v') equals value; computed in a canonical endpoint
    order so both polygons sharing the edge get the identical float32 vertex."""
    ka, kb = repr(a.key()), repr(b.key())
    if ka > kb:
        a, b = b, a
    ca, cb = getattr(a, axis), getattr(b, axis)
    t = (value - ca) / (cb - ca)
    pos = tuple(f32(a.pos[k] + t * (b.pos[k] - a.pos[k])) for k in range(3))
    nrm = tuple(f32(a.nrm[k] + t * (b.nrm[k] - a.nrm[k])) for k in range(3))
    u = value if axis == "u" else a.u + t * (b.u - a.u)
    v = value if axis == "v" else a.v + t * (b.v - a.v)
    return Corner(pos, nrm, u, v)


def clip(poly, axis, value, keep_below):
    """Sutherland-Hodgman against axis < value (keep_below) or >= value. Keeps corner order (winding)."""
    out = []
    n = len(poly)
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        ia = (getattr(a, axis) <= value) if keep_below else (getattr(a, axis) >= value)
        ib = (getattr(b, axis) <= value) if keep_below else (getattr(b, axis) >= value)
        if ia:
            out.append(a)
        if ia != ib:
            ca, cb = getattr(a, axis), getattr(b, axis)
            if ca != value and cb != value:
                out.append(_lerp_corner(a, b, axis, value))
    # drop consecutive duplicates (corner exactly on the line)
    ded = []
    for c in out:
        if not ded or repr(ded[-1].key()) != repr(c.key()):
            ded.append(c)
    if len(ded) > 1 and repr(ded[0].key()) == repr(ded[-1].key()):
        ded.pop()
    return ded


def split_face(g, f, au, av):
    """-> [(i, j, [Corner...])] pieces of face f in each UV quadrant (u split at au.split, v at av.split)."""
    poly = [Corner(g.verts[r[0]], g.normals[r[1]], r[2], r[3], r[0]) for r in f["vrefs"]]
    for r in f["vrefs"]:
        if r[0] != r[1]:
            raise ValueError("vertex/normal index differ in a split face: not handled")
    pieces = []
    for i in (0, 1):
        pu = clip(poly, "u", au.split, i == 0)
        if len(pu) < 3:
            continue
        for j in (0, 1):
            pv = clip(pu, "v", av.split, j == 0)
            if len(pv) >= 3 and abs(poly_area2([(c.u, c.v) for c in pv])) > 1e-12:
                pieces.append((i, j, pv))
    return pieces


def quarter_name(stem, i, j):
    m = TILE_RE.match(stem)
    return f"ZD{m.group(1)}0{m.group(2)}Q{i}{j}"            # ZDASH101 -> ZD101Q00 (8 chars)


def resplit_geo(g, split_stems, au, av, tjunction=True):
    """New Geo with every face whose texture stem is in split_stems cut into quadrant pieces.
    Returns (geo, report)."""
    ng = Geo()
    ng.w4, ng.name, ng.w20, ng.tail = g.w4, g.name, g.w20, g.tail
    ng.verts, ng.normals = list(g.verts), list(g.normals)
    newv = {}
    faces, rep = [], []
    for fi, f in enumerate(g.faces):
        stem = tex_stem(f)
        if stem not in split_stems:
            faces.append((dict(f), None)); continue
        pieces = split_face(g, f, au, av)
        frep = {"face": fi, "texture": stem, "corners": len(f["vrefs"]), "affine_residual": affine_residual(g, f),
                "pieces": []}
        for i, j, poly in pieces:
            vrefs = []
            for c in poly:
                if c.vid is None:
                    k = c.key()
                    if k not in newv:
                        newv[k] = len(ng.verts)
                        ng.verts.append(c.pos); ng.normals.append(c.nrm)
                    c.vid = newv[k]
                vrefs.append((c.vid, c.vid, f32(au.remap(c.u, i)), f32(av.remap(c.v, j))))
            nf = dict(f)
            nm = quarter_name(stem, i, j)
            ext = f["texture"].split(b"\0")[0].split(b".")[1] if b"." in f["texture"] else b"MAP"
            nf["texture"] = (nm.encode() + b"." + ext).ljust(13, b"\0")
            nf["vrefs"] = vrefs
            faces.append((nf, (fi, i, j)))
            frep["pieces"].append({"quarter": f"{i}{j}", "tile": nm, "corners": len(vrefs)})
        rep.append(frep)
    added = 0
    if tjunction:
        added = fix_tjunctions(ng, faces, set(newv.values()), au, av)
    ng.faces, ng.origin = [], [o for _, o in faces]
    for k, (f, _) in enumerate(faces):
        f["index"] = k                      # BSP node id: never read (engine rebuilds its tree, 0x45cbe0)
        ng.faces.append(f)
    return ng, {"faces": rep, "new_vertices": len(newv), "tjunction_corners_added": added,
                "n_verts": [len(g.verts), len(ng.verts)], "n_faces": [len(g.faces), len(ng.faces)]}


def fix_tjunctions(g, faces, new_ids, au, av, tol=1e-6):
    """Insert every new vertex that lies strictly inside an edge of another face as an extra (collinear) corner,
    so no polygon edge passes through a vertex of its neighbour (T-junctions crack at high resolution)."""
    added = 0
    for f, _ in faces:
        vr = f["vrefs"]
        out = []
        have = {r[0] for r in vr}
        for k in range(len(vr)):
            a, b = vr[k], vr[(k + 1) % len(vr)]
            out.append(a)
            pa, pb = g.verts[a[0]], g.verts[b[0]]
            d = [pb[c] - pa[c] for c in range(3)]
            L2 = sum(x * x for x in d)
            if L2 == 0:
                continue
            ins = []
            for vid in new_ids:
                if vid in have:
                    continue
                p = g.verts[vid]
                t = sum((p[c] - pa[c]) * d[c] for c in range(3)) / L2
                if not (1e-9 < t < 1 - 1e-9):
                    continue
                dist2 = sum((pa[c] + t * d[c] - p[c]) ** 2 for c in range(3))
                if dist2 < (tol * tol) * max(L2, 1e-12):
                    ins.append((t, vid))
            for t, vid in sorted(ins):
                out.append((vid, vid, f32(a[2] + t * (b[2] - a[2])), f32(a[3] + t * (b[3] - a[3]))))
                added += 1
        f["vrefs"] = out
    return added


# ---------------------------------------------------------------------------------------------- tiles
def m16_rgb_index(data):
    """-> (w, h, flags, idx bytes, pal565 list, rgb list per index incl. 0xFF as black)."""
    w, h, flags, idx, pal = i76img.parse_m16(data)
    rgb = [i76img.rgb565_to_rgb888(c) for c in pal]
    return w, h, flags, idx, pal, rgb


def free_slots(idx, pal, k):
    """Make k palette slots free (merge least-used colours into their nearest neighbour). -> (idx, pal, slots)."""
    pal = list(pal)
    idx = bytearray(idx)
    slots = []
    while len(pal) < 255 and len(slots) < k:
        pal.append(0); slots.append(len(pal) - 1)
    if len(slots) < k:
        counts = [0] * len(pal)
        for i in idx:
            if i < len(pal):
                counts[i] += 1

        def dist(a, b):
            return abs((a >> 11) - (b >> 11)) + abs((a >> 5 & 63) - (b >> 5 & 63)) + abs((a & 31) - (b & 31))
        order = sorted(range(len(pal)), key=lambda i: counts[i])
        for victim in order:
            if len(slots) >= k:
                break
            near = min((i for i in range(len(pal)) if i != victim and i not in slots), key=lambda i: dist(pal[i], pal[victim]))
            for p in range(len(idx)):
                if idx[p] == victim:
                    idx[p] = near
            slots.append(victim)
    return bytes(idx), pal, slots


FONT = {  # 3x5 glyphs, rows top->bottom, bit 2 = left column
    "-": [0, 0, 7, 0, 0], "0": [7, 5, 5, 5, 7], "1": [2, 6, 2, 2, 7], "2": [7, 1, 7, 4, 7], "3": [7, 1, 7, 1, 7],
    "4": [5, 5, 7, 1, 1], "5": [7, 4, 7, 1, 7], "6": [7, 4, 7, 5, 7], "Z": [7, 1, 2, 4, 7], "D": [6, 5, 5, 5, 6],
}


def draw_text(put, x0, y0, text, scale, flip_rows, H):
    for n, ch in enumerate(text):
        g = FONT[ch]
        for r in range(5):
            for c in range(3):
                if g[r] >> (2 - c) & 1:
                    for dy in range(scale):
                        for dx in range(scale):
                            y = y0 + r * scale + dy
                            put(x0 + (n * 4 + c) * scale + dx, (H - 1 - y) if flip_rows else y)


def quarter_layout(big_idx_or_rgb, W2, H2, au, av, resample):
    """Cut a 2x image (list of rows) into 4 quarters per the seam mode. resample(img, w, h) -> rows.
    Returns {(i,j): rows (L_v rows of L_u values)}."""
    if au.b:
        img = resample(big_idx_or_rgb, 2 * au.N, 2 * av.N)
    else:
        img = big_idx_or_rgb
    Wu, Hu = 2 * au.N, 2 * av.N
    out = {}
    for i in (0, 1):
        for j in (0, 1):
            rows = []
            for ty in range(av.L):
                gy = min(max(ty - av.b + av.N * j, 0), Hu - 1)
                row = img[gy]
                rows.append([row[min(max(tx - au.b + au.N * i, 0), Wu - 1)] for tx in range(au.L)])
            out[(i, j)] = rows
    return out


def nearest_rows(rows, w, h):
    H, W = len(rows), len(rows[0])
    return [[rows[y * H // h][x * W // w] for x in range(w)] for y in range(h)]


def build_quarters_index(data, au, av, marker, stem):
    """Pixel-replicated 2x quarters at index level (shared palette => exact art). -> {(i,j): m16 bytes}."""
    w, h, flags, idx, pal = i76img.parse_m16(data)
    rows = [list(idx[y * w:(y + 1) * w]) for y in range(h)]
    big = [[rows[y // 2][x // 2] for x in range(2 * w)] for y in range(2 * h)]
    qs = quarter_layout(big, 2 * w, 2 * h, au, av, nearest_rows)
    out = {}
    for (i, j), q in qs.items():
        flat = bytes(v for r in q for v in r)
        qpal = list(pal)
        if marker:
            flat, qpal, slots = free_slots(flat, qpal, 3)
            cq, cm, ck = slots
            qpal[cq] = i76img.rgb888_to_rgb565(*QCOL[(i, j)])
            qpal[cm] = i76img.rgb888_to_rgb565(*MAGENTA)
            qpal[ck] = 0
            flat = bytearray(flat)
            Lu, Lv = au.L, av.L

            def put(x, y, c):
                if 0 <= x < Lu and 0 <= y < Lv:
                    flat[y * Lu + x] = c
            x0, x1, y0, y1 = au.b, Lu - 1 - au.b, av.b, Lv - 1 - av.b      # unique region
            for t in range(2):                                              # 2-texel frame, quarter colour
                for x in range(x0, x1 + 1):
                    put(x, y0 + t, cq); put(x, y1 - t, cq)
                for y in range(y0, y1 + 1):
                    put(x0 + t, y, cq); put(x1 - t, y, cq)
            # label box: black, then text in quarter colour; rows flipped so it reads upright in game
            lab = f"{stem[-3:]}-{i}{j}"
            sc = 3      # small and near the top edge: the stock F1 view shows only the top ~12 % of the panel
            bw, bh = (len(lab) * 4 + 1) * sc, 7 * sc
            bx, by = 24, 4
            for y in range(by, by + bh):
                for x in range(bx, bx + bw):
                    put(x, Lv - 1 - y, ck)
            draw_text(lambda x, y: put(x, y, cq), bx + sc, by + sc, lab, sc, True, Lv)
            for y in range(by, by + bh):                                    # 1-texel checker: 2x-only detail
                for x in range(bx + bw + 8, bx + bw + 8 + 48):
                    if (x + y) & 1:
                        put(x, Lv - 1 - y, cm)
            flat = bytes(flat)
        out[(i, j)] = i76img.build_m16(au.L, av.L, flags, flat, qpal)
    return out


def quantize255(rgb_rows, key_rows, flags, L_u, L_v):
    """Rows of (r,g,b) -> M16 with the best of PIL's 255-colour quantisers (median cut / max coverage / octree,
    each with k-means refinement), judged by RGB565 mean squared error. key texels -> 0xFF. -> (m16, stats)."""
    import numpy as np
    from PIL import Image
    a = np.array(rgb_rows, np.uint8).reshape(L_v, L_u, 3)
    key = np.array(key_rows, bool).reshape(L_v, L_u)
    im = Image.fromarray(a, "RGB")
    best = None
    if len(np.unique(a.reshape(-1, 3), axis=0)) <= 255:
        cands = [("exact", None)]
    else:
        cands = [(n, m) for n, m in (("mediancut", Image.Quantize.MEDIANCUT), ("maxcoverage", Image.Quantize.MAXCOVERAGE),
                                     ("octree", Image.Quantize.FASTOCTREE))]
    for name, meth in cands:
        if meth is None:
            cols, inv = np.unique(a.reshape(-1, 3), axis=0, return_inverse=True)
            pal = cols; idx = inv.reshape(L_v, L_u)
        else:
            q = im.quantize(colors=255, method=meth, kmeans=4, dither=Image.Dither.NONE)
            pal = np.array(q.getpalette()[:3 * 255], np.uint8).reshape(-1, 3)
            idx = np.asarray(q, np.uint8)
        p565 = [i76img.rgb888_to_rgb565(*map(int, c)) for c in pal]
        back = np.array([i76img.rgb565_to_rgb888(c) for c in p565], np.float32)
        err = ((back[idx] - a.astype(np.float32)) ** 2)[~key].mean() if (~key).any() else 0.0
        if best is None or err < best[0]:
            best = (err, name, p565, idx)
    err, name, p565, idx = best
    used = sorted(set(np.unique(idx[~key]).tolist()))
    remap = {o: n for n, o in enumerate(used)}
    lut = np.full(256, 0xFF, np.uint8)
    for o, n in remap.items():
        lut[o] = n
    out = lut[idx]; out[key] = 0xFF
    pal = [p565[o] for o in used]
    return i76img.build_m16(L_u, L_v, flags, out.tobytes(), pal), {"quantiser": name, "colours": len(pal),
                                                                    "rmse_8bit": round(float(err) ** 0.5, 2)}


def build_quarters_png(data, png_path, au, av, keep_key=False):
    """Real upscale (512x256 RGB PNG, stored orientation) -> quarters, each quantised to its own <=255-colour RGB565
    palette. keep_key: texels that are 0xFF in the original (nearest 2x) stay 0xFF; default off, because these dash
    faces have no colour-key bit and their 0xFF texels render black (ZGLIDE 1555 0x0000), which the upscale already
    shows - a nearest-2x key mask would put the 1x blockiness back. -> ({(i,j): m16 bytes}, {(i,j): stats})."""
    from PIL import Image
    w, h, flags, idx, pal = i76img.parse_m16(data)
    im = Image.open(png_path).convert("RGB")
    if im.size != (2 * w, 2 * h):
        raise ValueError(f"{png_path}: {im.size}, expected {(2 * w, 2 * h)}")
    key = [[keep_key and idx[(y // 2) * w + x // 2] == 0xFF for x in range(2 * w)] for y in range(2 * h)]
    if au.b:
        im = im.resize((2 * au.N, 2 * av.N), Image.LANCZOS)
        key = nearest_rows(key, 2 * au.N, 2 * av.N)
    px = im.load()
    rows = [[px[x, y] for x in range(im.size[0])] for y in range(im.size[1])]
    lay_rgb, lay_key = _cut_prepared(rows, au, av), _cut_prepared(key, au, av)
    out, stats = {}, {}
    for q in lay_rgb:
        out[q], stats[q] = quantize255(lay_rgb[q], lay_key[q], flags, au.L, av.L)
    return out, stats


def _cut_prepared(img, au, av):
    """Cut an image already at the unique resolution (2N x 2N_v) into bordered quarters."""
    Wu, Hu = 2 * au.N, 2 * av.N
    out = {}
    for i in (0, 1):
        for j in (0, 1):
            out[(i, j)] = [[img[min(max(ty - av.b + av.N * j, 0), Hu - 1)][min(max(tx - au.b + au.N * i, 0), Wu - 1)]
                            for tx in range(au.L)] for ty in range(av.L)]
    return out


# ---------------------------------------------------------------------------------------------- render (checks)
def xform_matrix(xform):
    """(a, sx, b, sy) -> 3x3 homography from the model's (x, y) plane to screen (X = a + sx*x, Y = b - sy*y);
    a 3x3 array passes through (perspective views of a planar panel)."""
    import numpy as np
    if len(xform) == 4 and not hasattr(xform[0], "__len__"):
        a, sx, b, sy = xform
        return np.array([[sx, 0, a], [0, -sy, b], [0, 0, 1]], float)
    return np.asarray(xform, float)


def render_faces(g, textures, size, xform, k_ratio=255 / 256, ss=2):
    """Software render of geo faces through a plane homography of (x, y) (front view: x right, y up), bilinear
    with clamp like Glide, UV interpolated perspective-correctly (affine in the model plane).
    textures: stem -> float array HxWx3 (stored orientation). xform: (a, sx, b, sy) or a 3x3 homography.
    Returns float HxWx3 and a coverage mask. Faces without a texture in `textures` are skipped."""
    import numpy as np
    W, H = size
    M = xform_matrix(xform)
    M = np.diag([ss, ss, 1.0]) @ M
    Mi = np.linalg.inv(M)
    img = np.zeros((H * ss, W * ss, 3), np.float32)
    cov = np.zeros((H * ss, W * ss), bool)
    for f in g.faces:
        st = tex_stem(f)
        if st not in textures:
            continue
        T = textures[st]
        th, tw = T.shape[:2]
        Q = np.array([(g.verts[r[0]][0], g.verts[r[0]][1], 1.0) for r in f["vrefs"]])
        Ph = Q @ M.T
        if (Ph[:, 2] <= 0).any():
            continue
        P = Ph[:, :2] / Ph[:, 2:]
        UV = np.array([(r[2], r[3]) for r in f["vrefs"]], float)
        coef, *_ = np.linalg.lstsq(Q, UV, rcond=None)
        x0, y0 = np.floor(P.min(0)).astype(int); x1, y1 = np.ceil(P.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W * ss), min(y1, H * ss)
        if x1 <= x0 or y1 <= y0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float64) + 0.5
        inside = np.zeros(xx.shape, bool)
        n = len(P)
        for k in range(n):                               # even-odd rule
            (xa, ya), (xb, yb) = P[k], P[(k + 1) % n]
            cond = (ya > yy) != (yb > yy)
            with np.errstate(divide="ignore", invalid="ignore"):
                xi = xa + (yy - ya) * (xb - xa) / (yb - ya)
            inside ^= cond & (xx < xi)
        wx = Mi[0, 0] * xx + Mi[0, 1] * yy + Mi[0, 2]
        wy = Mi[1, 0] * xx + Mi[1, 1] * yy + Mi[1, 2]
        ww = Mi[2, 0] * xx + Mi[2, 1] * yy + Mi[2, 2]
        mx, my = wx / ww, wy / ww
        u = coef[0, 0] * mx + coef[1, 0] * my + coef[2, 0]
        v = coef[0, 1] * mx + coef[1, 1] * my + coef[2, 1]
        s = u * tw * k_ratio - 0.5
        t = v * th * k_ratio - 0.5
        s0 = np.floor(s); t0 = np.floor(t); fs = (s - s0)[..., None]; ft = (t - t0)[..., None]
        s0 = s0.astype(int); t0 = t0.astype(int)
        c = lambda q, m: np.clip(q, 0, m - 1)
        p00 = T[c(t0, th), c(s0, tw)]; p10 = T[c(t0, th), c(s0 + 1, tw)]
        p01 = T[c(t0 + 1, th), c(s0, tw)]; p11 = T[c(t0 + 1, th), c(s0 + 1, tw)]
        col = (p00 * (1 - fs) + p10 * fs) * (1 - ft) + (p01 * (1 - fs) + p11 * fs) * ft
        sub = img[y0:y1, x0:x1]; sub[inside] = col[inside]
        cov[y0:y1, x0:x1] |= inside
    img = img.reshape(H, ss, W, ss, 3).mean((1, 3))
    cov = cov.reshape(H, ss, W, ss).mean((1, 3)) > 0.999
    return img, cov


def m16_to_array(data, key_black=True):
    import numpy as np
    w, h, flags, idx, pal = i76img.parse_m16(data)
    lut = np.zeros((256, 3), np.float32)
    for i, c in enumerate(pal):
        lut[i] = i76img.rgb565_to_rgb888(c)
    return lut[np.frombuffer(idx, np.uint8).reshape(h, w)] / 255.0


# ---------------------------------------------------------------------------------------------- self-checks
def selfcheck(src_geo, new_geo, new_geo_bytes, orig_members, new_members, orig_tex_members, new_tex_members, tiles, au, av,
              split_stems, out_dir, car_pak, tex_pak, mode, ref2x=None):
    import numpy as np
    res = {}
    sys.path.insert(0, os.path.join(I76MAP, "data", "fmt"))
    sys.path.insert(0, os.path.join(I76MAP, "tools"))
    import other_formats  # noqa: F401  (registers the data-track handlers)
    hg = other_formats.handler_for(".geo")
    # 1. written files decode with the existing parsers and re-encode byte-identically
    rt = {}
    for base in (car_pak, tex_pak):
        pp = os.path.join(out_dir, base + ".pak")
        h = other_formats.handler_for(".pak", pp)
        data = open(pp, "rb").read()
        v = h.decode(data, ".pak")
        kinds = sorted({m[0] for _, m in v["members"]})
        rt[base + ".pak"] = {"members": len(v["members"]), "reencode_identical": h.encode(v) == data,
                             "member_kinds": kinds, "tail_bytes": len(v["tail"])}
        px = open(os.path.join(out_dir, base + ".pix"), "rb").read()
        hp = other_formats.handler_for(".pix")
        pv = hp.decode(px, ".pix")
        rt[base + ".pix"] = {"entries": pv["n"], "reencode_identical": hp.encode(pv) == px,
                             "contiguous": all(pv["entries"][k][1] + pv["entries"][k][2] == (pv["entries"][k + 1][1] if k + 1 < pv["n"] else len(data))
                                               for k in range(pv["n"])),
                             "names_unique": len({e[0].lower() for e in pv["entries"]}) == pv["n"]}
    gv = hg.decode(new_geo_bytes, ".geo")
    rt["geo"] = {"data_track_exact": hg.encode(gv) == new_geo_bytes, "own_parser_identity": write_geo(parse_geo(new_geo_bytes)) == new_geo_bytes,
                 "n_verts": gv["n_verts"], "n_faces": gv["n_faces"], "tail_bytes": len(gv["unk_tail"])}
    res["roundtrip"] = rt
    # 2. untouched members byte-identical
    om, nm = dict(orig_members), dict(new_members)
    changed = [k for k in om if om[k] != nm.get(k)]
    res["car_pak_members"] = {"original": len(om), "written": len(nm), "changed": changed,
                              "missing": [k for k in om if k not in nm], "order_preserved": [k for k, _ in orig_members] == [k for k, _ in new_members]}
    ot, nt = dict(orig_tex_members), dict(new_tex_members)
    res["tex_pak_members"] = {"original_kept_identical": all(nt.get(k) == ot[k] for k in ot),
                              "added": [k for k in nt if k not in ot]}
    # 3. M16 encoding of every new member
    m16 = {}
    for k in res["tex_pak_members"]["added"]:
        d = nt[k]
        w, h, flags, idx, pal = i76img.parse_m16(d)
        mx = max((i for i in idx if i != 0xFF), default=0)
        hm = other_formats.handler_for(".m16")
        m16[k] = {"size": f"{w}x{h}", "flags": hex(flags), "palette": len(pal), "bytes": len(d),
                  "bytes_expected": 12 + w * h + 2 * len(pal), "max_index": mx, "key_texels": idx.count(0xFF),
                  "ok": (w, h) == (au.L, av.L) and len(pal) <= 255 and mx < len(pal) and i76img.build_m16(w, h, flags, idx, pal) == d
                  and hm.encode(hm.decode(d, ".m16")) == d}
    res["m16"] = m16
    # 4. names (ng re-parsed from the written bytes; origin bookkeeping from the in-memory geo)
    ng = parse_geo(new_geo_bytes)
    referenced = sorted({tex_stem(f) for f in ng.faces})
    nlow = {k.upper() for k in nt}
    res["names"] = {"referenced": referenced,
                    "all_split_names_in_pak": all((s + ".M16") in nlow for s in referenced if s not in split_stems and s.startswith("ZD")),
                    "max_stem_len": max(len(k.split(".")[0]) for k in nt), "texture_field_ok": all(f["texture"][-1:] == b"\0" for f in ng.faces),
                    "no_split_texture_left": not any(s in split_stems for s in referenced)}
    # 5. UV coverage and geometry: per original face, the pieces (mapped back to the original UV space) must sum
    #    to the face's UV area and 3D area, lie in their own quadrant, and stay on the face plane.
    cov = []
    og = src_geo
    origin = getattr(new_geo, "origin", None) or [None] * len(ng.faces)
    split_faces = [f for f, o in zip(ng.faces, origin) if o is not None]
    for fi, f in enumerate(og.faces):
        if tex_stem(f) not in split_stems:
            continue
        uva = abs(poly_area2([(r[2], r[3]) for r in f["vrefs"]]))
        a3 = area3([og.verts[r[0]] for r in f["vrefs"]])
        sum_uv = sum_3 = on_plane = 0.0
        inside, n_pieces, eps = True, 0, 1e-5
        for pf, o in zip(ng.faces, origin):
            if o is None or o[0] != fi:
                continue
            _, i, j = o
            n_pieces += 1
            guv = [(au.unmap(r[2], i), av.unmap(r[3], j)) for r in pf["vrefs"]]
            sum_uv += abs(poly_area2(guv)); sum_3 += area3([ng.verts[r[0]] for r in pf["vrefs"]])
            lo_u, hi_u = (0 - eps, au.split + eps) if i == 0 else (au.split - eps, 1 + eps)
            lo_v, hi_v = (0 - eps, av.split + eps) if j == 0 else (av.split - eps, 1 + eps)
            inside &= all(lo_u <= u <= hi_u and lo_v <= v <= hi_v for u, v in guv)
            pl = f["plane"]
            for r in pf["vrefs"]:
                p = ng.verts[r[0]]
                on_plane = max(on_plane, abs(pl[0] * p[0] + pl[1] * p[1] + pl[2] * p[2] + pl[3]))
        cov.append({"face": fi, "texture": tex_stem(f), "corners": len(f["vrefs"]), "pieces": n_pieces,
                    "uv_area": round(uva, 7), "uv_rel_err": abs(sum_uv - uva) / max(uva, 1e-12),
                    "area3_rel_err": abs(sum_3 - a3) / max(a3, 1e-12),
                    "pieces_inside_quadrants": inside, "max_plane_distance": on_plane})
    res["uv_coverage"] = cov
    uvs = [(r[2], r[3]) for f in split_faces for r in f["vrefs"]]
    res["uv_bounds"] = {"u": [min(u for u, _ in uvs), max(u for u, _ in uvs)], "v": [min(v for _, v in uvs), max(v for _, v in uvs)],
                        "texel_s": [min(u for u, _ in uvs) * au.K, max(u for u, _ in uvs) * au.K],
                        "texel_t": [min(v for _, v in uvs) * av.K, max(v for _, v in uvs) * av.K]}
    # 6. seams: border texels equal the neighbour's edge texels (overlap mode)
    seams = {}
    if au.b:
        for st in split_stems:
            arr = {q: m16_to_array(nt[quarter_name(st, *q) + ".M16"]) for q in [(0, 0), (1, 0), (0, 1), (1, 1)]}
            d = []
            for j in (0, 1):   # vertical seam between i=0 and i=1
                d.append(np.abs(arr[(0, j)][:, -1] - arr[(1, j)][:, 1]).max()); d.append(np.abs(arr[(1, j)][:, 0] - arr[(0, j)][:, -2]).max())
            for i in (0, 1):
                d.append(np.abs(arr[(i, 0)][-1, :] - arr[(i, 1)][1, :]).max()); d.append(np.abs(arr[(i, 1)][0, :] - arr[(i, 0)][-2, :]).max())
            seams[st] = {"max_border_mismatch_8bit": round(float(max(d)) * 255, 2)}
        if mode == "marker":
            seams["note"] = "marker frames are drawn inside the unique region, so borders match except where label pixels sit"
    res["seams"] = seams or {"mode": "clamp: straight cut, no border texels"}
    # 7. render equivalence: split geo + quarters vs original geo + the whole 2x(unique) texture
    if ref2x is not None:
        texq = {quarter_name(st, i, j): m16_to_array(nt[quarter_name(st, i, j) + ".M16"]) for st in split_stems for i in (0, 1) for j in (0, 1)}
        xs = [p[0] for p in og.verts]; ys = [p[1] for p in og.verts]
        Wpx = 2400
        sx = (Wpx - 40) / (max(xs) - min(xs)); sy = sx
        Hpx = int((max(ys) - min(ys)) * sy) + 40
        xf = (20 - min(xs) * sx, sx, 20 + max(ys) * sy, sy)
        A, ca = render_faces(og, ref2x, (Wpx, Hpx), xf)
        B, cb = render_faces(ng, texq, (Wpx, Hpx), xf)
        both = ca & cb
        diff = np.abs(A - B).max(2)[both] * 255
        res["render_equivalence"] = {"pixels": int(both.sum()), "coverage_equal": bool((ca == cb).mean() > 0.999),
                                     "coverage_mismatch_px": int((ca != cb).sum()),
                                     "mean_abs_8bit": round(float(diff.mean()), 3), "p99_8bit": round(float(np.percentile(diff, 99)), 2),
                                     "max_8bit": round(float(diff.max()), 2)}
    return res


def verdict(res):
    bad = []
    for k, v in res["roundtrip"].items():
        if not v.get("reencode_identical", True) or not v.get("data_track_exact", True) or not v.get("own_parser_identity", True) \
                or not v.get("contiguous", True) or not v.get("names_unique", True):
            bad.append("roundtrip " + k)
    cp = res["car_pak_members"]
    if len(cp["changed"]) != 1 or cp["missing"] or not cp["order_preserved"]:
        bad.append("car pak members")
    if not res["tex_pak_members"]["original_kept_identical"]:
        bad.append("tex pak originals")
    bad += ["m16 " + k for k, v in res["m16"].items() if not v["ok"]]
    n = res["names"]
    if not (n["all_split_names_in_pak"] and n["max_stem_len"] <= 8 and n["texture_field_ok"] and n["no_split_texture_left"]):
        bad.append("names")
    for c in res["uv_coverage"]:
        if c["uv_rel_err"] > 1e-5 or c["area3_rel_err"] > 1e-4 or not c["pieces_inside_quadrants"] or c["max_plane_distance"] > 1e-5:
            bad.append(f"uv coverage face {c['face']}")
    return bad


# ---------------------------------------------------------------------------------------------- main
def refuse_out(out):
    o = os.path.abspath(out)
    low = o.lower()
    for bad in PROTECTED:
        if bad in low:
            sys.exit(f"refusing --out {out}: a playable install or a pristine/protected copy")
    if os.path.isdir(o):
        names = {n.lower() for n in os.listdir(o)}
        if "i76.exe" in names or "i76.zfs" in names:
            sys.exit(f"refusing --out {out}: it holds the game (i76.exe / I76.ZFS); write to ADDON or elsewhere")


def find_dash_geo(members):
    c = [nm for nm, _ in members if re.match(r"^..51DASH\.GEO$", nm.upper())]
    if len(c) != 1:
        raise SystemExit(f"cannot pick the dash .geo automatically: {c}; pass --geo")
    return c[0]


def run(a):
    refuse_out(a.out)
    os.makedirs(a.out, exist_ok=True)
    src = Source(a.game, a.extract, a.no_addon)
    car = a.car_pak.lower()
    car_members = pak_members(src.read(car + ".pak"), src.read(car + ".pix"))
    geo_name = a.geo or find_dash_geo(car_members)
    gbytes = dict((k.upper(), v) for k, v in car_members)[geo_name.upper()]
    g = parse_geo(gbytes)
    assert write_geo(g) == gbytes, "own .geo writer is not identity on the source"
    stems = sorted({tex_stem(f) for f in g.faces if TILE_RE.match(tex_stem(f))})
    if not stems:
        raise SystemExit(f"{geo_name} has no ZDASHn0[12] faces")
    sets = {TILE_RE.match(s).group(1) for s in stems}
    if len(sets) != 1:
        raise SystemExit(f"mixed dash sets {sets}")
    tex_pak = f"zdash{sets.pop()}06"
    tex_members = pak_members(src.read(tex_pak + ".pak"), src.read(tex_pak + ".pix"))
    tdict = {k.upper(): v for k, v in tex_members}
    w, h, *_ = i76img.parse_m16(tdict[stems[0] + ".M16"])
    k_ratio = (a.uv_k / 256.0)
    au, av = Axis(w, a.seam, k_ratio), Axis(h, a.seam, k_ratio)
    ng, grep = resplit_geo(g, set(stems), au, av, tjunction=not a.no_tjunction_fix)
    ngb = write_geo(ng)
    mode = "marker" if a.marker else ("replicate" if a.replicate else "png")
    tiles, quant = {}, {}
    import numpy as np
    ref2x = {}
    for st in stems:
        d = tdict[st + ".M16"]
        if mode == "png":
            q, qst = build_quarters_png(d, os.path.join(a.png_dir, st + ".png"), au, av, a.keep_key)
            quant[st] = {f"Q{i}{j}": v for (i, j), v in qst.items()}
        else:
            q = build_quarters_index(d, au, av, mode == "marker", st)
        for (i, j), b in q.items():
            tiles[quarter_name(st, i, j) + ".M16"] = b
        # reference for the render-equivalence check: the whole 2x (unique-grid) texture before cutting
        base = m16_to_array(d)
        if mode == "png":
            from PIL import Image
            im = Image.open(os.path.join(a.png_dir, st + ".png")).convert("RGB")
            if au.b:
                im = im.resize((2 * au.N, 2 * av.N), Image.LANCZOS)
            ref = np.asarray(im, np.float32) / 255
        else:
            ref = base.repeat(2, 0).repeat(2, 1)
            if au.b:
                H2, W2 = 2 * av.N, 2 * au.N
                ys = (np.arange(H2) * ref.shape[0]) // H2; xs = (np.arange(W2) * ref.shape[1]) // W2
                ref = ref[ys][:, xs]
        ref2x[st] = ref
    new_car = [(nm, ngb if nm.upper() == geo_name.upper() else d) for nm, d in car_members]
    new_tex = list(tex_members) + sorted(tiles.items())
    for base, mem in ((car, new_car), (tex_pak, new_tex)):
        pk, px = build_pak(mem)
        open(os.path.join(a.out, base + ".pak"), "wb").write(pk)
        open(os.path.join(a.out, base + ".pix"), "wb").write(px)
    res = selfcheck(g, ng, ngb, car_members, new_car, tex_members, new_tex, tiles, au, av, set(stems), a.out, car, tex_pak,
                    mode, ref2x if mode != "marker" else None)
    bad = verdict(res)
    # preview: the re-authored dash with the written quarter tiles, front-on and upright (as seen from the seat)
    try:
        from PIL import Image
        nt = dict(new_tex)
        texq = {quarter_name(st, i, j): m16_to_array(nt[quarter_name(st, i, j) + ".M16"]) for st in stems for i in (0, 1) for j in (0, 1)}
        xs = [p[0] for p in g.verts]; ys = [p[1] for p in g.verts]
        sx = 2360 / (max(xs) - min(xs))
        img, cv = render_faces(ng, texq, (2400, int((max(ys) - min(ys)) * sx) + 40), (20 - min(xs) * sx, sx, 20 + max(ys) * sx, sx))
        img[~cv] = 0.15
        Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(a.out, "preview-as-seen.png"))
    except Exception as e:  # noqa: BLE001  (preview is a convenience, never a gate)
        print("  preview skipped:", e)
    man = {"tool": "texture-lab/cockpit_split.py", "mode": mode, "seam": a.seam, "uv_k": a.uv_k,
           "split_u": au.split, "split_v": av.split, "sources": src.used, "car_pak": car, "geo": geo_name,
           "tex_pak": tex_pak, "tiles_split": stems, "geo_report": grep, "quantisation": quant, "keep_key": a.keep_key,
           "files": {f: {"bytes": os.path.getsize(os.path.join(a.out, f)),
                         "md5": hashlib.md5(open(os.path.join(a.out, f), "rb").read()).hexdigest()}
                     for f in (car + ".pak", car + ".pix", tex_pak + ".pak", tex_pak + ".pix")},
           "selfcheck": res, "selfcheck_failures": bad, "derived_game_data": "never commit"}
    open(os.path.join(a.out, "cockpit-split.json"), "w").write(json.dumps(man, indent=1))
    print(f"{geo_name}: faces {grep['n_faces'][0]} -> {grep['n_faces'][1]}, verts {grep['n_verts'][0]} -> {grep['n_verts'][1]}"
          f", T-junction corners +{grep['tjunction_corners_added']}; {tex_pak}: +{len(tiles)} quarter tiles ({mode}, seam {a.seam})")
    for fr in grep["faces"]:
        print(f"  face {fr['face']} {fr['texture']} {fr['corners']} corners, affine residual {fr['affine_residual']:.2e}: "
              + ", ".join(f"Q{p['quarter']}({p['corners']})" for p in fr["pieces"]))
    if "render_equivalence" in res:
        print("  render equivalence vs whole 2x texture:", res["render_equivalence"])
    print("  self-check:", "PASS" if not bad else "FAIL " + "; ".join(bad))
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", help="game folder holding I76.ZFS (read only)")
    ap.add_argument("--extract", help="folder of loose extracted archive files instead of --game")
    ap.add_argument("--no-addon", action="store_true", help="ignore <game>/ADDON copies (read I76.ZFS only)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--car-pak", default="vppirnag", help="car geometry pack (default vppirnag = Piranha)")
    ap.add_argument("--geo", help="dash .geo member (default: the pack's only ??51DASH.GEO)")
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument("--marker", action="store_true")
    m.add_argument("--replicate", action="store_true")
    m.add_argument("--png-dir")
    ap.add_argument("--seam", choices=("overlap", "clamp"), default="overlap")
    ap.add_argument("--uv-k", type=float, default=255.0, help="ZGLIDE texel scale per unit UV on a 256 axis (255 static read; 256 ideal)")
    ap.add_argument("--no-tjunction-fix", action="store_true")
    ap.add_argument("--keep-key", action="store_true", help="--png-dir: keep the original's 0xFF texels (nearest 2x) as 0xFF")
    a = ap.parse_args(argv)
    if not (a.game or a.extract):
        ap.error("--game or --extract is required")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
