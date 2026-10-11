"""texture-lab/cockpit_split.py: .geo layout, quadrant clipper, quarter tiles, pak writer, end-to-end on synthetic
fixtures built here (no game data in git). The live half (every LOD-4 .geo in the archive parses to exact length and
re-writes byte-identically) runs only when the pristine sandbox archive is present: set I76_ZFS_DIR (default
C:\\Users\\james\\i76-map\\sandbox-gog\\main\\app)."""
import os, random, re, struct, sys, tempfile, unittest, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "texture-lab"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import cockpit_split as cs  # noqa: E402
import i76img  # noqa: E402

GAME = os.environ.get("I76_ZFS_DIR", r"C:\Users\james\i76-map\sandbox-gog\main\app")
HAVE_DATATRACK = os.path.exists(os.path.join(cs.I76MAP, "data", "fmt", "other_formats.py"))


def make_geo(faces, verts, name=b"XX51DASH"):
    """faces: [(texture, [(vid, u, v), ...])] on the plane z = -0.08 (normal +z)."""
    g = cs.Geo()
    g.w4, g.name, g.w20, g.tail = 107, name.ljust(16, b"\0"), 0, b""
    g.verts = [tuple(cs.f32(c) for c in v) for v in verts]
    g.normals = [(0.0, 0.0, 1.0) for _ in verts]
    g.faces = []
    for k, (tex, refs) in enumerate(faces):
        g.faces.append({"index": k, "rgb": b"\x38\x38\x38", "plane": (0.0, 0.0, 1.0, cs.f32(0.08)), "zero": 0,
                        "surface": b"\x04\x01\x00", "texture": tex.encode().ljust(13, b"\0"), "parent": 0xFFFFFFFF,
                        "side": 1, "vrefs": [(vid, vid, cs.f32(u), cs.f32(v)) for vid, u, v in refs]})
    return g


def dash_like():
    """A Piranha-shaped dash: a full quad on ZDASH102, a 5-corner face with a cut corner on ZDASH101 and the
    corner's filler quad on ZDASH101 (same layout as PP51DASH, simplified coordinates)."""
    z = -0.08
    verts = [(0.75, 0.16, z), (-0.18, 0.16, z), (-0.18, -0.16, z), (0.75, -0.16, z),          # 0-3 quad
             (-0.79, -0.16, z), (-0.18, -0.16, z), (-0.18, 0.16, z), (-0.736, 0.16, z), (-0.789, 0.097, z),  # 4-8
             (-0.79, 0.114, z), (-0.749, 0.158, z)]                                            # 9-10
    U = lambda x: (x + 0.79) / 0.61
    V = lambda y: (y + 0.16) / 0.32
    faces = [("ZDASH102.MAP", [(0, 0.96, 1.0), (1, 0.0, 1.0), (2, 0.0, 0.0), (3, 0.96, 0.0)]),
             ("ZDASH101.MAP", [(k, U(verts[k][0]), V(verts[k][1])) for k in (4, 5, 6, 7, 8)]),
             ("ZDASH101.MAP", [(k, U(verts[k][0]), V(verts[k][1])) for k in (7, 10, 9, 8)])]
    return make_geo(faces, verts)


class GeoLayout(unittest.TestCase):
    def test_roundtrip(self):
        g = dash_like()
        b = cs.write_geo(g)
        self.assertEqual(b[:4], b"OEG.")
        # header 36 + 11 verts * 24 + per face 55 (8 + rgb 3 + plane 16 + 4 + surface 3 + tex 13 + 8) + 16/corner
        self.assertEqual(len(b), 36 + 11 * 24 + 3 * 55 + 16 * (4 + 5 + 4))
        self.assertEqual(cs.write_geo(cs.parse_geo(b)), b)

    @unittest.skipUnless(HAVE_DATATRACK, "i76-map data track not present")
    def test_data_track_parser_agrees(self):
        sys.path.insert(0, os.path.join(cs.I76MAP, "data", "fmt"))
        sys.path.insert(0, os.path.join(cs.I76MAP, "tools"))
        import other_formats
        h = other_formats.handler_for(".geo")
        b = cs.write_geo(dash_like())
        v = h.decode(b, ".geo")
        self.assertEqual(h.encode(v), b)
        self.assertEqual(len(v["faces"][1]["rgb"]), 3)


class Axis(unittest.TestCase):
    def test_split_and_inverse(self):
        for seam in ("overlap", "clamp"):
            for L in (256, 128):
                ax = cs.Axis(L, seam)
                self.assertAlmostEqual(ax.split, 256 / 510)
                for u in (0, 0.1, ax.split, 0.7, 1):
                    for i in (0, 1):
                        self.assertAlmostEqual(ax.unmap(ax.remap(u, i), i), u, places=12)

    def test_overlap_bounds(self):
        ax = cs.Axis(256, "overlap")
        self.assertAlmostEqual(ax.remap(0, 0) * ax.K, 1.0)         # outer edge: texel coord 1, inside the border
        self.assertAlmostEqual(ax.remap(ax.split, 0), 1.0)         # seam, left quarter: s = 255
        self.assertAlmostEqual(ax.remap(ax.split, 1) * ax.K, 1.0)  # seam, right quarter: s = 1
        self.assertLess(ax.remap(1, 1), 1.0)

    def test_clamp_is_texel_exact(self):
        ax = cs.Axis(256, "clamp")
        self.assertAlmostEqual(ax.remap(ax.split, 0) * ax.K, 256.0)
        self.assertAlmostEqual(ax.remap(ax.split, 1) * ax.K, 0.0)


class Clipper(unittest.TestCase):
    def setUp(self):
        self.g = dash_like()
        self.au, self.av = cs.Axis(256, "overlap"), cs.Axis(128, "overlap")
        self.ng, self.rep = cs.resplit_geo(self.g, {"ZDASH101", "ZDASH102"}, self.au, self.av)

    def pieces_of(self, fi):
        return [(f, o) for f, o in zip(self.ng.faces, self.ng.origin) if o and o[0] == fi]

    def test_areas_sum_and_quadrants(self):
        for fi, f in enumerate(self.g.faces):
            uva = abs(cs.poly_area2([(r[2], r[3]) for r in f["vrefs"]]))
            a3 = cs.area3([self.g.verts[r[0]] for r in f["vrefs"]])
            s_uv = s_3 = 0
            for pf, (_, i, j) in self.pieces_of(fi):
                guv = [(self.au.unmap(r[2], i), self.av.unmap(r[3], j)) for r in pf["vrefs"]]
                s_uv += abs(cs.poly_area2(guv))
                s_3 += cs.area3([self.ng.verts[r[0]] for r in pf["vrefs"]])
                for u, v in guv:
                    self.assertTrue((u <= self.au.split + 1e-6) if i == 0 else (u >= self.au.split - 1e-6))
                    self.assertTrue((v <= self.av.split + 1e-6) if j == 0 else (v >= self.av.split - 1e-6))
                for r in pf["vrefs"]:
                    self.assertTrue(0 <= r[2] <= 1 and 0 <= r[3] <= 1)
            self.assertAlmostEqual(s_uv, uva, places=6)
            self.assertAlmostEqual(s_3, a3, places=6)

    def test_piece_counts_and_five_corner_face(self):
        counts = [len(self.pieces_of(fi)) for fi in range(3)]
        self.assertEqual(counts, [4, 4, 1])          # filler quad sits in one quadrant (u < .09, v > .8)
        five = [len(pf["vrefs"]) for pf, _ in self.pieces_of(1)]
        self.assertEqual(sorted(five), [4, 4, 4, 5])  # the cut corner stays in the Q01 piece

    def test_winding_and_attributes_preserved(self):
        for fi, f in enumerate(self.g.faces):
            sign = cs.poly_area2([(self.g.verts[r[0]][0], self.g.verts[r[0]][1]) for r in f["vrefs"]]) > 0
            for pf, (_, i, j) in self.pieces_of(fi):
                self.assertEqual(cs.poly_area2([(self.ng.verts[r[0]][0], self.ng.verts[r[0]][1]) for r in pf["vrefs"]]) > 0, sign)
                for k in ("rgb", "plane", "surface", "zero", "parent", "side"):
                    self.assertEqual(pf[k], f[k])
                self.assertEqual(pf["texture"], f"ZD10{cs.tex_stem(f)[-1]}Q{i}{j}.MAP".encode().ljust(13, b"\0"))
                for r in pf["vrefs"]:
                    self.assertEqual(r[0], r[1])
                    self.assertAlmostEqual(self.ng.verts[r[0]][2], -0.08, places=6)

    def test_original_corners_keep_their_vertex(self):
        for fi, f in enumerate(self.g.faces):
            used = {r[0] for pf, _ in self.pieces_of(fi) for r in pf["vrefs"]}
            self.assertTrue({r[0] for r in f["vrefs"]} <= used)
        self.assertEqual(self.ng.verts[:len(self.g.verts)], self.g.verts)

    def test_split_vertices_shared(self):
        # the full quad: 4 edge points + 1 centre, shared by its four pieces (no duplicates)
        quad = {r[0] for pf, _ in self.pieces_of(0) for r in pf["vrefs"]} - set(range(len(self.g.verts)))
        self.assertEqual(len(quad), 5)
        keys = [struct.pack("<3f", *v) for v in self.ng.verts[len(self.g.verts):]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_affine_residual_zero_for_planar_affine(self):
        for f in self.g.faces:
            self.assertLess(cs.affine_residual(self.g, f), 1e-6)

    def test_tjunction_fix(self):
        # two quads sharing an edge; only the left one is split -> the right one gets the split points of the edge
        z = 0.0
        verts = [(0, 0, z), (1, 0, z), (1, 1, z), (0, 1, z), (2, 0, z), (2, 1, z)]
        g = make_geo([("ZDASH101.MAP", [(0, 0, 0), (1, 1, 0), (2, 1, 1), (3, 0, 1)]),
                      ("FLAT.MAP", [(1, 0, 0), (4, 1, 0), (5, 1, 1), (2, 0, 1)])], verts)
        ng, rep = cs.resplit_geo(g, {"ZDASH101"}, cs.Axis(256, "clamp"), cs.Axis(128, "clamp"))
        right = [f for f, o in zip(ng.faces, ng.origin) if o is None][0]
        self.assertEqual(len(right["vrefs"]), 5)
        self.assertEqual(rep["tjunction_corners_added"], 1)
        ng2, rep2 = cs.resplit_geo(g, {"ZDASH101"}, cs.Axis(256, "clamp"), cs.Axis(128, "clamp"), tjunction=False)
        self.assertEqual(rep2["tjunction_corners_added"], 0)


def synth_tile(seed, key_frac=0.05):
    rnd = random.Random(seed)
    pal = [rnd.randrange(65536) for _ in range(255)]
    idx = bytes(0xFF if rnd.random() < key_frac else rnd.randrange(255) for _ in range(256 * 128))
    return i76img.build_m16(256, 128, 0x80, idx, pal)


class Quarters(unittest.TestCase):
    def test_clamp_replicate_is_exact_block(self):
        d = synth_tile(1)
        au, av = cs.Axis(256, "clamp"), cs.Axis(128, "clamp")
        q = cs.build_quarters_index(d, au, av, False, "ZDASH101")
        w, h, f, idx, pal = i76img.parse_m16(d)
        for (i, j), b in q.items():
            W, H, F, qi, qp = i76img.parse_m16(b)
            self.assertEqual((W, H, F, qp), (256, 128, 0x80, pal))
            for y in (0, 37, 127):
                for x in (0, 101, 255):
                    self.assertEqual(qi[y * 256 + x], idx[((128 * j + y) // 2) * 256 + (256 * i + x) // 2])

    def test_overlap_borders_match_neighbours(self):
        d = synth_tile(2)
        au, av = cs.Axis(256, "overlap"), cs.Axis(128, "overlap")
        q = {k: i76img.parse_m16(b)[3] for k, b in cs.build_quarters_index(d, au, av, False, "ZDASH101").items()}
        px = lambda k, x, y: q[k][y * 256 + x]
        for y in range(128):
            self.assertEqual(px((0, 0), 255, y), px((1, 0), 1, y))
            self.assertEqual(px((1, 0), 0, y), px((0, 0), 254, y))
            self.assertEqual(px((0, 0), 0, y), px((0, 0), 1, y))       # outer edge replicated
        for x in range(256):
            self.assertEqual(px((0, 0), x, 127), px((0, 1), x, 1))
            self.assertEqual(px((0, 1), x, 0), px((0, 0), x, 126))

    def test_marker_palette_and_colours(self):
        d = synth_tile(3)
        au, av = cs.Axis(256, "overlap"), cs.Axis(128, "overlap")
        q = cs.build_quarters_index(d, au, av, True, "ZDASH101")
        for (i, j), b in q.items():
            W, H, F, qi, qp = i76img.parse_m16(b)
            self.assertLessEqual(len(qp), 255)
            self.assertTrue(max(v for v in qi if v != 0xFF) < len(qp))
            want = i76img.rgb888_to_rgb565(*cs.QCOL[(i, j)])
            self.assertIn(want, qp)
            self.assertGreater(qi.count(qp.index(want)), 500)          # frame + label actually drawn
            self.assertIn(i76img.rgb888_to_rgb565(*cs.MAGENTA), qp)

    def test_free_slots_merges_least_used(self):
        idx = bytes([k for k in range(255) for _ in range(3) if k not in (1, 7)] + [1] + [7, 7])
        pal = [k * 200 for k in range(255)]
        idx2, p2, slots = cs.free_slots(idx, pal, 2)
        self.assertEqual(len(p2), 255)
        self.assertEqual(sorted(slots), [1, 7])
        self.assertNotIn(1, idx2)
        self.assertNotIn(7, idx2)


class PakAndPipeline(unittest.TestCase):
    def test_pak_roundtrip(self):
        mem = [("A.GEO", b"abc"), ("B.M16", b"defgh")]
        pak, pix = cs.build_pak(mem)
        self.assertEqual(pix, b"2\r\nA.GEO 0 3\r\nB.M16 3 5\r\n")
        self.assertEqual(cs.pak_members(pak, pix), mem)

    def test_refuses_game_folder(self):
        with tempfile.TemporaryDirectory() as t:
            open(os.path.join(t, "i76.exe"), "wb").close()
            with self.assertRaises(SystemExit):
                cs.refuse_out(t)

    @unittest.skipUnless(HAVE_DATATRACK, "i76-map data track not present (self-checks use its parsers)")
    def test_end_to_end_synthetic(self):
        with tempfile.TemporaryDirectory() as t:
            ext = os.path.join(t, "extract"); os.makedirs(ext)
            g = dash_like()
            other = make_geo([("V1 BO DY.MAP", [(0, 0, 0), (1, 1, 0), (2, 1, 1)])], [(0, 0, 0), (1, 0, 0), (1, 1, 0)], b"XX11BDYM")
            pak, pix = cs.build_pak([("XX11BDYM.GEO", cs.write_geo(other)), ("XX51DASH.GEO", cs.write_geo(g))])
            open(os.path.join(ext, "vxfakeg.pak"), "wb").write(pak); open(os.path.join(ext, "vxfakeg.pix"), "wb").write(pix)
            pak, pix = cs.build_pak([("ZDASH101.M16", synth_tile(4)), ("ZDASH102.M16", synth_tile(5))])
            open(os.path.join(ext, "zdash106.pak"), "wb").write(pak); open(os.path.join(ext, "zdash106.pix"), "wb").write(pix)
            for mode in (["--marker"], ["--replicate"], ["--replicate", "--seam", "clamp"]):
                out = os.path.join(t, "out-" + "-".join(m.strip("-") for m in mode))
                rc = cs.main(["--extract", ext, "--out", out, "--car-pak", "vxfakeg"] + mode)
                m = json.load(open(os.path.join(out, "cockpit-split.json")))
                self.assertEqual(rc, 0, m["selfcheck_failures"])
                self.assertEqual(m["selfcheck"]["car_pak_members"]["changed"], ["XX51DASH.GEO"])
                self.assertEqual(len(m["selfcheck"]["tex_pak_members"]["added"]), 8)
                if "--replicate" in mode:
                    re_ = m["selfcheck"]["render_equivalence"]
                    self.assertTrue(re_["coverage_equal"])
                    self.assertLess(re_["mean_abs_8bit"], 1.0)
                    if "clamp" not in mode:
                        for st in ("ZDASH101", "ZDASH102"):
                            self.assertEqual(m["selfcheck"]["seams"][st]["max_border_mismatch_8bit"], 0.0)


@unittest.skipUnless(os.path.exists(os.path.join(GAME, "I76.ZFS")), "pristine archive not present")
class LiveArchive(unittest.TestCase):
    def test_every_lod4_geo_parses_exactly(self):
        src = cs.Source(GAME, no_addon=True)
        paks = sorted(n[:-4] for n in src.ents if re.match(r"^v.*g\.pak$", n))
        n = 0
        for p in paks:
            if p + ".pix" not in src.ents:
                continue
            for nm, d in cs.pak_members(src.read(p + ".pak"), src.read(p + ".pix")):
                if nm.upper().endswith(".GEO") and len(nm) > 3 and nm[2] == "5":
                    g = cs.parse_geo(d)
                    self.assertEqual(g.tail, b"", nm)
                    self.assertEqual(cs.write_geo(g), d, nm)
                    n += 1
        print(f"\n  {n} LOD-4 .geo members in {len(paks)} v*g.pak parsed to exact length and re-written identically")
        self.assertGreater(n, 1000)


if __name__ == "__main__":
    unittest.main()
