#!/usr/bin/env python3
"""test_design.py - tests for the haptics design facility (run: python design/test_design.py, or haptics.ps1 test).

Offline. Reads the pristine install only where a test says so (skipped when it is absent).
"""
import importlib.util, json, os, struct, subprocess, sys, tempfile, unittest, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np

import common, gpw_spectra, i76rec, migrate_tune, stock_reference


def burst(hz=30.0, rate=11025, dur=0.30, attack=0.02, tau=0.08, bits8=True):
    t = np.arange(int(rate * dur)) / rate
    env = np.where(t < attack, t / attack, np.exp(-(t - attack) / tau))
    x = 0.8 * env * np.sin(2 * np.pi * hz * t)
    if bits8:                                       # through the game's own medium: 8-bit unsigned
        x = (np.round(x * 127) + 128).astype(np.uint8)
        x = (x.astype(float) - 128) / 128.0
    return rate, np.concatenate([np.zeros(int(rate * 0.05)), x, np.zeros(int(rate * 0.2))])


class Spectra(unittest.TestCase):
    def test_30hz_burst_recovered(self):
        rate, x = burst(30.0)
        r = gpw_spectra.analyse({"name": "synthetic30"}, rate, x)
        self.assertAlmostEqual(r["peak_hz_in_band"], 30.0, delta=1.0)
        self.assertAlmostEqual(r["suggested"]["lfe"]["hz"], 30.0, delta=1.0)
        self.assertEqual(r["suggested"]["kind"], "transient")
        self.assertEqual(r["suggested"]["pad"]["motor"], "L")          # all of the energy is low
        self.assertTrue(40 <= r["onset_ms"] <= 70, r["onset_ms"])       # 50 ms of silence first
        self.assertTrue(60 <= r["peak_ms"] <= 90, r["peak_ms"])         # peak at the end of the 20 ms attack
        self.assertGreater(r["bands"]["20-40"], 0.8)
        env = np.array(r["rms_10ms"])
        self.assertAlmostEqual(env.max(), 1.0, places=6)
        self.assertLess(env[-5:].max(), 0.05)                           # decays to silence
        self.assertIn("8-bit", r["caveats"])

    def test_65hz_vs_200hz(self):
        rate, a = burst(65.0)
        self.assertAlmostEqual(gpw_spectra.analyse({"name": "a"}, rate, a)["peak_hz_in_band"], 65.0, delta=1.0)
        rate, b = burst(200.0)
        r = gpw_spectra.analyse({"name": "b"}, rate, b)
        self.assertLess(r["shaker_band_fraction"], 0.05)
        self.assertEqual(r["suggested"]["lfe"]["hz_source"], "rig peak (little in-band energy)")

    def test_gpw_header_decoded(self):
        rate, x = burst(30.0)
        pcm = (np.round(x * 127) + 128).astype(np.uint8).tobytes()
        import io, wave
        bio = io.BytesIO()
        w = wave.open(bio, "wb"); w.setnchannels(1); w.setsampwidth(1); w.setframerate(rate); w.writeframes(pcm); w.close()
        payload = b"GAS0" + struct.pack("<6i", 50, 2, 1, 80, 1, -1) + bio.getvalue()
        meta, r2, y = common.decode_sound("test.gpw", payload)
        self.assertEqual(meta["gas"]["mode"], 1); self.assertEqual(meta["gas"]["volume_pct"], 80); self.assertEqual(r2, rate)
        self.assertEqual(len(y), len(x))


class Migration(unittest.TestCase):
    def test_every_key_in_exactly_one_place(self):
        tune = migrate_tune.parse_default_tune()
        self.assertEqual(len(tune), 66)
        self.assertEqual(migrate_tune.diff(tune, migrate_tune.load_tunemap()), 0)

    def test_parse_matches_known_values(self):
        t = migrate_tune.parse_default_tune()
        self.assertEqual(t["LfeExplodeHz"], 25.0)          # the 560dcd2 values
        self.assertEqual(t["LfeExplodeDuck"], 0.75)
        self.assertEqual(len(t["LfeRespHz"]), 21)


class Stock(unittest.TestCase):
    def test_reference_has_the_events(self):
        ref = json.load(open(os.path.join(common.ROOT, "stock", "stock-ffb-reference.json"), encoding="utf-8"))
        for k in ("impact.collision", "impact.ordnance", "impact.concussion", "engine.vibration", "tyre.flat", "weapon.hardpoint", "terrain.rumble"):
            self.assertIn(k, ref["events"])
        self.assertIn("55.0 + 0.5625", ref["events"]["impact.collision"]["formula"])
        for e in ref["events"].values():
            self.assertTrue(e["evidence"])

    def test_frc_compositions_from_the_pristine_copy(self):
        force = os.path.join(common.PRISTINE, "force")
        if not os.path.isdir(force):
            self.skipTest("pristine install not present")
        comps = stock_reference.frc_compositions(force)
        self.assertEqual(len(comps), 14)
        self.assertEqual(comps["EXPLOSN.FRC"]["types"], ["SawtoothDown1"])
        self.assertIn("Superimpose3", comps["TIREBLWL.FRC"]["types"])

    def test_effect_references_resolve(self):
        ref = json.load(open(os.path.join(common.ROOT, "stock", "stock-ffb-reference.json"), encoding="utf-8"))
        for fn in os.listdir(os.path.join(common.ROOT, "effects")):
            e = json.load(open(os.path.join(common.ROOT, "effects", fn), encoding="utf-8"))
            s = (e.get("reference") or {}).get("stock")
            if s:
                self.assertIn(s.split("#")[1], ref["events"], fn)


class Recording(unittest.TestCase):
    def test_round_trip(self):
        p = os.path.join(tempfile.mkdtemp(), "x.i76rec")
        recs = [(0.0, b"\x01\x02"), (0.016, bytes(range(200)))]
        i76rec.write(p, recs, {"a": 1})
        meta, back = i76rec.read(p)
        self.assertEqual(meta, {"a": 1}); self.assertEqual(back, recs)

    def test_host_recording_decodes_with_i76tel_py(self):
        """Cross-check: a host-written synthetic session decodes in the telemetry tool's own decoder (needs the v3 i76tel.py)."""
        tel = os.path.join(common.REPO, "tools", "telemetry", "i76tel.py")
        alt = os.path.join(common.ROOT, "tests", "out", "xcheck", "i76tel.py")
        src = tel if "def decode_datagram" in open(tel, encoding="utf-8").read() else (alt if os.path.exists(alt) else None)
        exe = os.path.join(common.ROOT, "src", "Host", "bin", "Release", "net8.0", "i76haptics.exe")
        if src is None or not os.path.exists(exe):
            self.skipTest("v3 i76tel.py (decode_datagram) or the built host not available")
        spec = importlib.util.spec_from_file_location("i76tel_x", src)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        h = m.Header(os.path.join(os.path.dirname(src), "i76tel.h"))
        for v in (2, 3):
            p = os.path.join(tempfile.mkdtemp(), "s.i76rec")
            subprocess.run([exe, "synth", "--out", p, "--version", str(v)], check=True, capture_output=True)
            meta, recs = i76rec.read(p)
            types = {}
            for t, b in recs:
                fr, evs = m.decode_datagram(h, b)
                self.assertIsNotNone(fr)
                self.assertAlmostEqual(fr["sim_time"], t, places=4)
                self.assertEqual(fr["version"], v)
                for e in evs:
                    types[e["type"]] = types.get(e["type"], 0) + 1
            want = {1: 10, 2: 1, 3: 1} if v == 2 else {1: 10, 2: 1, 3: 1, 4: 2, 5: 1, 6: 1, 7: 1}
            self.assertEqual(types, want)


class Png(unittest.TestCase):
    def test_png_valid(self):
        p = os.path.join(tempfile.mkdtemp(), "a.png")
        common.line_plot_png(p, [(np.arange(100), np.sin(np.arange(100) / 5))], width=64, height=32)
        b = open(p, "rb").read()
        self.assertEqual(b[:8], b"\x89PNG\r\n\x1a\n")
        w, h = struct.unpack(">II", b[16:24])
        self.assertEqual((w, h), (64, 32))
        idat = b[b.index(b"IDAT") + 4:b.index(b"IEND") - 8]
        self.assertEqual(len(zlib.decompress(idat)), 32 * (1 + 64 * 3))


class Report(unittest.TestCase):
    def test_report_for_the_four_named_events(self):
        if not os.path.exists(os.path.join(common.PRISTINE, "I76.ZFS")):
            self.skipTest("pristine install not present")
        exe = os.path.join(common.ROOT, "src", "Host", "bin", "Release", "net8.0", "i76haptics.exe")
        if not os.path.exists(exe):
            self.skipTest("host not built")
        r = subprocess.run([sys.executable, os.path.join(HERE, "report.py"), "--only", "impact.collision,weapon.fire,engine.vibration,slip.scrub"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = open(os.path.join(common.OUT, "report", "index.html"), encoding="utf-8").read()
        for eid in ("impact.collision", "weapon.fire", "engine.vibration", "slip.scrub"):
            self.assertIn('<section id="%s">' % eid, page)
        self.assertIn("1. Stock FFB", page); self.assertIn("2. Stock sound", page); self.assertIn("4. Current effect rendered", page)
        self.assertNotIn("<pre>error", page)


from test_stems_view import StemsViewEndToEnd, StemsViewUnits  # noqa: E402,F401  (HD sound pack LFE stems view)


if __name__ == "__main__":
    unittest.main(verbosity=2)
