"""M16 index-level round trip (tools/i76img.py parse_m16/build_m16) on synthetic data and, when the game
archive and liblzo2 are available, on every terrain M16 of the missions T01 (tp04, desert day), T06
(tp09, night) and M14 (tp18, snow) - plus every other tp??m6.pak set while we are there.

Game data is read-only and never committed: set I76_ZFS (default: ../i76-uncap-lab/game/I76.ZFS) and
LZO2_DLL (e.g. anaconda3/Library/bin/lzo2.dll) to run the live half.
"""
import os, struct, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "upscale"))
import i76img  # noqa: E402

ZFS = os.environ.get("I76_ZFS", os.path.join(ROOT, "..", "i76-uncap-lab", "game", "I76.ZFS"))
MISSION_SETS = {"T01": "tp04", "T06": "tp09", "M14": "tp18"}


class SyntheticM16(unittest.TestCase):
    def test_roundtrip_with_unused_palette_entries(self):
        w = h = 8
        idx = bytes((x * 3 + y) % 7 for y in range(h) for x in range(w))
        pal = [0xF800, 0x07E0, 0x001F, 0xFFFF, 0, 0x1234, 0x1234, 0xBEEF, 0xBEEF, 0xBEEF]  # dups + unused
        d = i76img.build_m16(w, h, 0x80, idx, pal)
        self.assertEqual(len(d), 12 + w * h + 2 * len(pal))
        self.assertEqual(i76img.parse_m16(d), (w, h, 0x80, idx, pal))
        self.assertEqual(i76img.build_m16(*i76img.parse_m16(d)), d)

    def test_size_check(self):
        d = i76img.build_m16(4, 4, 0x80, bytes(16), [1, 2])
        with self.assertRaises(ValueError):
            i76img.parse_m16(d + b"\0\0")

    def test_rgb565_lossless(self):
        for c in range(0, 65536, 7):
            self.assertEqual(i76img.rgb888_to_rgb565(*i76img.rgb565_to_rgb888(c)), c)


@unittest.skipUnless(os.path.exists(ZFS), "I76.ZFS not present")
class LiveTerrainM16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import terrain
            cls.ents, get = terrain.open_zfs(ZFS)
            cls.get = staticmethod(get)
            cls.get("tp04m6.pix")
            cls.terrain = terrain
        except SystemExit as e:  # zfs_extract exits when liblzo2 is missing
            raise unittest.SkipTest(str(e))

    def check_set(self, stem):
        members = self.terrain.pak_members(self.get, stem + "m6")
        self.assertEqual(len(members), 6)
        for k, (name, d) in enumerate(members):
            self.assertEqual(name[4], "123456"[k], name)  # .pix order is '1'..'6'
            w, h, fl, idx, pal = i76img.parse_m16(d)
            self.assertEqual(fl, 0x80, name)
            self.assertLess(max(idx), len(pal), name)       # no palette offset, no 0xFF in terrain
            self.assertEqual(i76img.build_m16(w, h, fl, idx, pal), d, name)
            # the RGB PNG handed to the upscalers maps back to the same 565 palette
            self.assertEqual([i76img.rgb888_to_rgb565(*i76img.rgb565_to_rgb888(c)) for c in pal], pal)
        sizes = [i76img.parse_m16(d)[0] for _, d in members[1:]]
        self.assertEqual(sizes, [256, 64, 64, 32, 16], stem)

    def test_mission_sets(self):
        for mission, stem in MISSION_SETS.items():
            with self.subTest(mission=mission):
                self.check_set(stem)

    def test_all_terrain_sets(self):
        sets = self.terrain.terrain_sets(self.ents)
        self.assertGreaterEqual(len(sets), 11)
        for s in sets:
            with self.subTest(set=s):
                self.check_set(s[:4])


if __name__ == "__main__":
    unittest.main()
