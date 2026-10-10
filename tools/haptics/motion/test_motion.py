#!/usr/bin/env python3
"""test_motion.py - tests for the motion validator and the synthetic scenarios (run: python motion/test_motion.py, or haptics.ps1 test).

Offline. The end-to-end class runs the host binary (built by haptics.ps1 test) over every scenario with file sinks only:
nothing is sent over UDP, no game, no device. It is skipped when the binary is missing.
"""
import io, json, math, os, struct, subprocess, sys, tempfile, unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
HAPTICS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HAPTICS, "design"))
sys.path.insert(0, os.path.join(HAPTICS, "..", "telemetry"))
import i76motion, make_synthetic, i76rec, i76tel  # noqa: E402

EXE = os.path.join(HAPTICS, "src", "Host", "bin", "Release", "net8.0", "i76haptics.exe")


def i76m_packet(seq=5, status=0x00020501, t=2.5, surge=-9.5, sway=1.0, heave=0.25, cue_heave=6.0, roll=0.01, pitch=-0.056, heading=0.52):
    """A hand-packed i76motion v1 datagram (offsets typed in from docs/MOTION-OUTPUT.md 3.3, not from the schema)."""
    b = bytearray(144)
    b[0:4] = b"I76M"
    struct.pack_into("<HHII", b, 4, 1, 144, seq, status)
    struct.pack_into("<f", b, 16, t)
    struct.pack_into("<fff", b, 20, surge, sway, heave)
    struct.pack_into("<fff", b, 32, 0.0, -0.1, 0.4)
    struct.pack_into("<fff", b, 44, roll, pitch, heading)
    struct.pack_into("<fff", b, 56, 11.0, 3000.0, 1.0)
    struct.pack_into("<fff", b, 68, 0.0, 1.0, -0.25)
    struct.pack_into("<f", b, 112, 0.3)
    struct.pack_into("<fff", b, 116, 0.0, 0.0, cue_heave)
    struct.pack_into("<fff", b, 128, 0.5, 0.0, 11.0)
    return bytes(b)


class Decoder(unittest.TestCase):
    def test_i76motion_hand_packet(self):
        fmt, d = i76motion.decode(i76m_packet())
        self.assertEqual(fmt, "i76motion")
        self.assertEqual((d["magic"], d["version"], d["size"], d["seq"]), ("I76M", 1, 144, 5))
        self.assertAlmostEqual(d["surge"], -9.5, places=5)
        self.assertAlmostEqual(d["heave"], 0.25, places=5)
        self.assertAlmostEqual(d["pitch_rate"], -0.1, places=5)
        self.assertAlmostEqual(d["yaw_rate"], 0.4, places=5)
        self.assertAlmostEqual(d["pitch"], -0.056, places=5)
        self.assertAlmostEqual(d["gear"], 1.0)
        self.assertAlmostEqual(d["brake"], 1.0)
        self.assertAlmostEqual(d["steer"], -0.25)
        self.assertAlmostEqual(d["texture"], 0.3, places=5)
        self.assertAlmostEqual(d["cue_heave"], 6.0)
        self.assertAlmostEqual(d["vel_fwd"], 11.0)
        self.assertEqual((d["status"] >> 16) & 0xff, 2)

    def test_lfs_and_forza_hand_packets(self):
        c = bytearray(64)
        struct.pack_into("<I15f", c, 0, 1234, 0.1, 0.2, -0.42, -0.15, 0.05, -0.03, 1.25, -3.5, 1.2, 3.0, 19.7, 0.1, 0, 0, 0)
        struct.pack_into("<iii", c, 52, int(10.5 * 65536), int(-7.75 * 65536), int(2.25 * 65536))
        fmt, d = i76motion.decode(bytes(c))
        self.assertEqual(fmt, "lfs-classic")
        self.assertEqual(d["time"], 1234)
        self.assertAlmostEqual(d["angvel_z"], -0.42, places=5)
        self.assertAlmostEqual(d["accel_y"], -3.5, places=5)
        self.assertEqual(d["pos_y"], int(-7.75 * 65536))
        p2 = bytearray(280); p2[0:4] = b"LFST"; struct.pack_into("<iI", p2, 4, 1, 99); struct.pack_into("<ff", p2, 72, 0.8, 0.0); p2[92] = 3
        fmt, d = i76motion.decode(bytes(p2))
        self.assertEqual((fmt, d["id"], d["time"], d["gear"]), ("lfs-pack2", 1, 99, 3))
        self.assertAlmostEqual(d["throttle"], 0.8, places=5)
        og = bytearray(92); og[4:8] = b"I76 "; og[10] = 3; struct.pack_into("<ff", og, 12, 20.0, 4321.0); og[60:68] = b"gmg30cal"
        fmt, d = i76motion.decode(bytes(og))
        self.assertEqual((fmt, d["car"], d["gear"], d["display1"]), ("outgauge", "I76 ", 3, "gmg30cal"))
        fz = bytearray(311); struct.pack_into("<iI", fz, 0, 1, 1234); struct.pack_into("<fff", fz, 20, 1.25, 1.2, -3.5); fz[307] = 3; struct.pack_into("<b", fz, 308, 64)
        fmt, d = i76motion.decode(bytes(fz))
        self.assertEqual((fmt, d["is_race_on"], d["gear"], d["steer"]), ("forza-dash", 1, 3, 64))
        self.assertAlmostEqual(d["accel_z"], -3.5, places=5)
        self.assertEqual(i76motion.detect(bytes(232)), "forza-sled")
        self.assertEqual(i76motion.detect(bytes(68)), "lfs-classic")
        self.assertEqual(i76motion.detect(bytes(96)), "outgauge")
        self.assertIsNone(i76motion.detect(bytes(100)))

    def test_schema_sizes_and_contiguity(self):
        sz = {"f32": 4, "i32": 4, "u32": 4, "u16": 2, "s16": 2, "u8": 1, "s8": 1, "char4": 4, "char16": 16}
        for name, f in i76motion.FORMATS.items():
            fields = [x for x in f["fields"] if x[2] != "id" or x[0] < f["size"]]
            off = 0
            for o, t, n, *_ in fields:
                self.assertEqual(o, off, "%s.%s at %d, expected %d" % (name, n, o, off))
                off += sz[t]
            self.assertEqual(off, f["size"], name)


class Checks(unittest.TestCase):
    def run_check(self, recs, meta=None, hz=None, exp=None):
        res = i76motion.Result()
        dec = i76motion.conformance(recs, meta or {}, res, hz)
        if exp:
            i76motion.expectations(dec, exp, res)
        return res

    def test_conformance_pass_and_fail(self):
        recs = [(k * 0.01, i76m_packet(seq=k, t=k * 0.01, status=1)) for k in range(50)]
        recs.append((0.5, i76m_packet(seq=50, t=0.5, status=0x80000020, surge=0, sway=0, heave=0, roll=0, pitch=0, heading=0, cue_heave=0)))
        res = self.run_check(recs, {"output_hz": 100})
        self.assertEqual(res.failed, 0, "\n".join(res.lines))
        bad = list(recs); bad[10] = (0.10, i76m_packet(seq=99, t=0.10))
        self.assertGreater(self.run_check(bad).failed, 0)                       # seq gap
        slow = [(k * 0.02, p) for k, (_, p) in enumerate(recs)]
        self.assertGreater(self.run_check(slow, {"output_hz": 100}).failed, 0)  # 50 Hz where 100 was configured
        air = [(k * 0.01, i76m_packet(seq=k, t=k * 0.01, status=1 | 2, surge=-3)) for k in range(5)]
        self.assertGreater(self.run_check(air).failed, 0)                       # airborne with a physics channel

    def test_expectations(self):
        recs = [(k * 0.01, i76m_packet(seq=k, t=k * 0.01, surge=-9.5 if k > 20 else 0.0)) for k in range(60)]
        exp = {"scenario": "t", "checks": [dict(name="a", t0=0.3, t1=0.5, channel="surge", stat="mean", lo=-9.6, hi=-9.4),
                                           dict(name="b", t0=0.0, t1=0.1, channel="surge", stat="absmax", lo=0, hi=0.01),
                                           dict(name="c", t0=0.0, t1=0.5, channel="status", stat="all_bit0", lo=1, hi=1)]}
        res = self.run_check(recs, exp=exp)
        self.assertEqual([ln for ln in res.lines if "FAIL" in ln and ln.split(":")[0].strip().startswith("FAIL  t")], [], "\n".join(res.lines))
        exp["checks"][0]["lo"], exp["checks"][0]["hi"] = -5, -4
        self.assertTrue(any("FAIL  t: a" in ln for ln in self.run_check(recs, exp=exp).lines))


class Synthetic(unittest.TestCase):
    def test_scenarios_decode_as_i76tel_v3(self):
        h = i76tel.Header()
        for f in make_synthetic.SCENARIOS:
            sc = f()
            recs = make_synthetic.generate(sc, 60.0)
            self.assertGreater(len(recs), 300, sc["name"])
            steps, prev_pose, new_states = [], None, 0
            for t, b in recs:
                fr, evs = i76tel.decode_datagram(h, b)
                self.assertIsNotNone(fr)
                self.assertEqual((fr["magic"], fr["version"], fr["size"]), (h.consts["I76TEL_MAGIC"], 3, 664))
                steps.append(fr["step_count"])
                pose = (fr["pos_0"], fr["pos_2"], fr["velocity_0"], fr["velocity_2"])
                if fr["step_count"] == 0 and prev_pose is not None and sc.get("name") != "dropout":
                    self.assertEqual(pose, prev_pose, "%s: a frame without a physics step must repeat the pose" % sc["name"])
                prev_pose = pose
                r = [fr["rot_%d" % k] for k in range(9)]
                for i in range(3):
                    self.assertAlmostEqual(sum(r[3 * i + k] ** 2 for k in range(3)), 1.0, places=5)
            self.assertIn(0, steps, "%s: 60 fps of 24 Hz physics has frames without a step" % sc["name"])
            dur = recs[-1][0] - recs[0][0]
            if "gap" not in sc:                                                # the dropout's silent frames carry their steps away
                self.assertAlmostEqual(sum(steps) / dur, 24.0, delta=0.5, msg=sc["name"])

    def test_rot_conventions(self):
        r = make_synthetic.rot_rows(0.3, -0.05, 0.04)
        self.assertAlmostEqual(math.asin(r[7]), -0.05, places=9)              # pitch + nose up
        self.assertAlmostEqual(-math.asin(r[1]), 0.04, places=3)              # roll + right side down
        self.assertAlmostEqual(math.atan2(r[6], r[8]), 0.3, places=9)         # heading clockwise from above
        self.assertAlmostEqual(make_synthetic.pitch_for(9.81) / make_synthetic.DEG, 3.31, places=2)   # 1 g = 3.3 deg

    def test_writes_files(self):
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(make_synthetic.main(["braking", "--out", d]), 0)
            meta, recs = i76rec.read(os.path.join(d, "synth-braking.i76rec"))
            self.assertEqual(meta["scenario"], "braking")
            exp = json.load(open(os.path.join(d, "synth-braking.expect.json")))
            self.assertTrue(any("surge -9.5" in c["name"] for c in exp["checks"]))


@unittest.skipUnless(os.path.exists(EXE), "host binary not built (haptics.ps1 build)")
class EndToEnd(unittest.TestCase):
    """make_synthetic -> i76haptics motion (files only) -> i76motion.py --check against each scenario's table."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="motion-e2e-")
        with redirect_stdout(io.StringIO()):
            make_synthetic.main(["--out", cls.tmp])

    def scenario(self, name, targets="flypt,simtools,simhub,simhub-forza,native"):
        out = os.path.join(self.tmp, "out")
        rec = os.path.join(self.tmp, "synth-%s.i76rec" % name)
        r = subprocess.run([EXE, "motion", rec, "--targets", targets, "--out", out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("not sent (files only)", r.stdout)
        logs = [os.path.join(out, f) for f in os.listdir(out) if f.startswith("synth-%s." % name) and f.endswith(".i76rec")]
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = i76motion.cmd_check(sorted(logs), os.path.join(self.tmp, "synth-%s.expect.json" % name), quiet=True)
        self.assertEqual(rc, 0, buf.getvalue())
        return logs

    def test_braking(self):
        logs = self.scenario("braking")
        self.assertEqual(len(logs), 8)      # flypt / simtools / simhub: OutSim + OutGauge each; simhub-forza dash; native

    def test_accelerating(self):
        self.scenario("accelerating", "native")

    def test_turn(self):
        self.scenario("turn", "native,simhub-forza")

    def test_crest(self):
        self.scenario("crest", "native")

    def test_jump(self):
        self.scenario("jump", "native,flypt")

    def test_impact(self):
        self.scenario("impact", "native")

    def test_dropout(self):
        self.scenario("dropout", "native")


if __name__ == "__main__":
    unittest.main(verbosity=2)
