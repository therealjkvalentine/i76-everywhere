#!/usr/bin/env python3
"""test_stems_view.py - tests for design/stems_view.py (HD sound pack LFE stems vs Lfe.Synth). Run directly, or through
test_design.py (haptics.ps1 test), which imports these classes. The end-to-end test needs the built pack and host."""
import json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np

import stems_view


class StemsViewUnits(unittest.TestCase):
    def test_effect_mapping(self):
        eff = stems_view.load_effects()
        # whmgun is listed by weapon.fire (player SHOT) and sound.ai_weapon (AI only): the player's effect wins
        self.assertEqual(stems_view.effect_for("whmgun", "weapon_fire", eff)[0], "weapon.fire")
        self.assertEqual(stems_view.effect_for("vexplode", "explosion_impact", eff)[0], "explosion.blast")
        self.assertEqual(stems_view.effect_for("eisv", "engine_loop", eff), ("engine.vibration", "category engine_loop"))
        eid, why = stems_view.effect_for("dblox", "dropper", eff)
        self.assertIsNone(eid)
        self.assertIn("no effect", why)

    def test_spectrum_reads_dbfs(self):
        rate = 16000
        t = np.arange(rate) / rate
        f, d = stems_view.spectrum_db(np.sin(2 * np.pi * 40 * t), rate)
        self.assertAlmostEqual(float(f[np.argmax(d)]), 40.0, delta=0.5)
        self.assertAlmostEqual(float(d.max()), 0.0, delta=0.5)          # full-scale sine = 0 dBFS
        f2, d2 = stems_view.spectrum_db(0.5 * np.sin(2 * np.pi * 40 * t), rate)
        self.assertAlmostEqual(float(d.max() - d2.max()), 6.02, delta=0.1)
        self.assertEqual(stems_view.peak_hz(np.zeros(4000), rate), None)


class StemsViewEndToEnd(unittest.TestCase):
    def test_view_two_stems(self):
        if not os.path.exists(stems_view.MANIFEST):
            self.skipTest("HD pack LFE stems not built (tools/soundhd/soundhd.py build)")
        man = json.load(open(stems_view.MANIFEST, encoding="utf-8"))
        if not all(os.path.exists(os.path.join(os.path.dirname(stems_view.MANIFEST), man["sounds"][s]["file"])) for s in ("whcan", "vexplode")):
            self.skipTest("stem WAVs not on disk")
        if not os.path.exists(stems_view.HOST):
            self.skipTest("host not built")
        saved = stems_view.VIEW
        stems_view.VIEW = os.path.join(stems_view.OUT, "stems-test")   # leave a full view in design/out/stems alone
        self.addCleanup(setattr, stems_view, "VIEW", saved)
        self.assertEqual(stems_view.main(["--only", "whcan,vexplode"]), 0)
        idx = {i["stem"]: i for i in json.load(open(os.path.join(stems_view.VIEW, "index.json"), encoding="utf-8"))}
        self.assertEqual(set(idx), {"whcan", "vexplode"})
        for s in idx.values():
            self.assertTrue(s["stem_rendered"] and s["synth_rendered"], s)
        page = open(os.path.join(stems_view.VIEW, "index.html"), encoding="utf-8").read()
        self.assertIn('<section id="vexplode">', page)
        self.assertIn("Lfe.Synth event: explosion.blast", page)
        # the stem through the host carries stem content, Lfe.Synth's render for the same event is a different signal
        _, st = stems_view.read_wav(os.path.join(stems_view.VIEW, "render", "stem", "vexplode.lfe.wav"))
        _, sy = stems_view.read_wav(os.path.join(stems_view.VIEW, "render", "synth", "explosion.blast.lfe.wav"))
        self.assertGreater(np.abs(stems_view.window(st, 16000)).max(), 0.1)
        self.assertEqual(np.abs(st[:int(0.5 * 16000)]).max(), 0.0)     # stems only: silent before the event
        self.assertGreater(np.abs(stems_view.window(sy, 16000)).max(), 0.1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
