#!/usr/bin/env python3
r"""test_debug.py - offline tests for I76 Debug (tools/debug). No game, no browser, no device, loopback only.

    python tools\debug\tests\test_debug.py            unit tests + the end-to-end run (about 25 s)
    python tools\debug\tests\test_debug.py --unit     unit tests only
    python tools\debug\tests\test_debug.py --rec X    end-to-end with another .i76rec (default: the overnight P2 t05 run,
                                                      else the host's scripted synthetic session)

End to end (the screenshot-free smoke test): the debug server (i76debug.py) on free ports with a real proxy log
fixture, the haptics host `live --source udp --port <tee> --debug-udp <port>` (file sinks only, no --live), and
`i76haptics play <rec> --port <tel>` standing in for the game. The server's telemetry socket tees every datagram to the
host. A Python client then reads /api/state and the /api/stream SSE feed and asserts that every panel has its data.
Ports are picked free at run time (never 7676: the owner's game may be sending there).
"""
import json, os, socket, struct, subprocess, sys, tempfile, threading, time, unittest, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEBUG = os.path.dirname(HERE)
TOOLS = os.path.dirname(DEBUG)
sys.path.insert(0, DEBUG)
sys.path.insert(0, os.path.join(TOOLS, "haptics", "design"))
import debug_core, i76rec
from debug_core import ProxyLog, Hub, ShmView

FIXTURE_LOG = os.path.join(HERE, "fixtures", "mciproxy-sample.log")
LAB_REC = r"C:\Users\james\i76-uncap-lab\autotest\runs\overnight-20261011-203304\P2\t05.i76rec"
HOST_EXE = os.path.join(TOOLS, "haptics", "src", "Host", "bin", "Release", "net8.0", "i76haptics.exe")
OUT = os.path.join(HERE, "out")
REC = LAB_REC
for i, a in enumerate(sys.argv):
    if a == "--rec" and i + 1 < len(sys.argv):
        REC = sys.argv[i + 1]


def free_udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def free_tcp():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class LogParser(unittest.TestCase):
    """ProxyLog on real lines (fixture = the overnight t05 start + one real example of each periodic line)."""

    @classmethod
    def setUpClass(cls):
        cls.L = ProxyLog(FIXTURE_LOG)
        cls.L.poll()
        cls.st = cls.L.state()

    def test_session_and_features(self):
        st = self.st
        self.assertGreater(st["lines"], 40)
        names = {f["name"] for f in st["features"]}
        for n in ("fixed-step", "telemetry", "render-interp", "far-clip", "trainer"):
            self.assertIn(n, names)
        self.assertIn("I76_FIXED_STEP", st["switches_from_log"])
        self.assertEqual(st["fixed_step"]["hz"], 24.0)
        self.assertTrue(any("not applied" in l for l in st["not_applied"]))
        ri = next(f for f in st["features"] if f["name"] == "render-interp")
        self.assertFalse(ri["applied"])                     # the last render-interp line in the fixture is 'needs ... not applied'

    def test_periodic_counters(self):
        st = self.st
        self.assertEqual(st["fps"]["fps"], 60.0)
        sf = st["coll"]["stepframe"]
        self.assertEqual((sf["pairs"], sf["widened"], sf["stock"], sf["fallback"]), (525, 104, 421, 0))
        self.assertEqual(len(st["coll"]["hist"]), 3)
        self.assertEqual(st["coll"]["v3"]["tests"], 2)
        self.assertEqual((st["bbox"]["parts"], st["bbox"]["boxes"]), (149, 10))
        self.assertTrue(st["bbox"]["status"].startswith("1/1"))
        self.assertEqual(st["lift_count"], 3)
        self.assertEqual(len(st["cockpit_under"]), 3)
        d = st["terrain_drops"][0]
        self.assertEqual((d["vertices"], d["prev"], d["cam_mode"]), (731, 6171, 0))
        self.assertAlmostEqual(d["eye_above"], 2.577)
        self.assertEqual(st["flash"]["scenes"], 600)
        self.assertEqual(st["flushes"][0]["n"], 1)
        self.assertEqual(st["tex"]["dl"], 86)
        self.assertEqual(st["road"]["pool_kb"], 2000)
        self.assertEqual(st["clutter"]["us_avg"], 266)
        self.assertEqual(len(st["start_pos"]), 3)

    def test_follow_appends_and_new_session_resets(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "mciproxy.log")
            with open(p, "w", encoding="latin1") as f:
                f.write("old junk\n  strlkup_orig: x\n  fixed-step: 24.00 steps/s (41.67 ms) on\n")
            L = ProxyLog(p)
            L.poll()
            self.assertEqual(L.fixed_step["hz"], 24.0)
            with open(p, "a", encoding="latin1") as f:
                f.write("  fps: 120.0 (600 frames / 5.0 s); work 2.00 ms avg, 3.00 ms max; cap wait 6.00 ms avg\npartial")
            new = L.poll()
            self.assertEqual(len(new), 1)                   # the unterminated 'partial' waits for its newline
            self.assertEqual(L.fps["fps"], 120.0)
            with open(p, "a", encoding="latin1") as f:
                f.write(" line\n  strlkup_orig: y\n")
            L.poll()
            self.assertIsNone(L.fps)                        # a new proxy start clears the per-process state
            self.assertIsNone(L.fixed_step)


class DrawProbeLines(unittest.TestCase):
    """I76_DRAW_PROBE (proxy 17baaab) has not run yet, so no real line exists: these are its three mlog formats
    (strlkproxy.c draw-probe) filled with made-up numbers, to pin the parser to the format strings."""

    def test_draw_probe(self):
        L = ProxyLog(None)
        for line in (
            "  draw-probe: TERRAIN-LOSS #1 at swap 900 (proxy frame 901, t 123 ms, cam mode 0): main terrain polygons emitted 410, clipped away 3, "
            "below the bucket floor 0 (floor 1.5, span 1800.0), past bucket 4096 0, > 32 vertices 0, queued 407, drawn 12 (previous swap 398); all polygons drawn 50 | "
            "other cameras: emitted 0 queued 0 drawn 0 | triangles 900 (previous 5000), LFB locks 0, state 5",
            "  draw-probe: TRIANGLE-LOSS #2 at swap 950 (proxy frame 951, t 130 ms, cam mode 0): triangles 800 (previous 5100) with main terrain polygons drawn 400 (previous 401), LFB locks 1",
            "  draw-probe: swaps 1200: last 600: main terrain polygons drawn min 12, triangles min 800, LFB locks 1, main terrain clipped away 30, below the floor 0, past 4096 0 | "
            "totals 1 terrain losses, 1 triangle losses | 14 terrain textures seen",
            "  draw-probe: on (3/3 sites: terrain clip 0x4925a8, insert 0x4925bc, hardware draw 0x48fb7e; ZGLIDE grDrawTriangle / grLfbLock counted when ZGLIDE loads)"):
            L.add(line)
        st = L.state()
        self.assertEqual([d["kind"] for d in st["draw_losses"]], ["TERRAIN-LOSS", "TRIANGLE-LOSS"])
        self.assertEqual((st["draw_losses"][0]["drawn"], st["draw_losses"][0]["prev"]), (12, 398))
        self.assertEqual(st["draw_losses"][1]["triangles"], 800)
        self.assertEqual((st["draw"]["drawn_min"], st["draw"]["terrain_losses"], st["draw"]["textures"]), (12, 1, 14))
        self.assertIn("I76_DRAW_PROBE", st["switches_from_log"])


class HubDecode(unittest.TestCase):
    def test_recording_through_the_hub(self):
        if not os.path.exists(REC):
            self.skipTest("no recording at %s" % REC)
        meta, recs = i76rec.read(REC)
        hub = Hub()
        for t, d in recs:
            hub.on_datagram(d, "test")
        self.assertEqual(hub.frames, len(recs))
        ev = hub.events_view()
        for k in ("SHOT", "EXPLOSION", "IMPACT", "SOUND_START", "SOUND_STOP", "DAMAGE_SIDE", "WEAPON_UI"):
            self.assertGreater(ev["count"].get(k, 0), 0, k)
        self.assertTrue(ev["shots"])
        self.assertTrue(any(x["hits"] for x in ev["damage_sides"].values()))
        self.assertTrue(ev["explosions"][0]["name"])
        self.assertGreater(len(hub.trail), 10)
        s = hub.samples[-1]
        for k in ("speed", "rpm", "ax", "pitch", "susp", "wg", "steps", "gg"):
            self.assertIn(k, s)
        json.dumps(hub.snapshot())                          # everything the API returns is JSON


class SharedMemory(unittest.TestCase):
    def test_open_existing_never_creates(self):
        name = "Local\\I76DebugTestNoSuch%d" % os.getpid()
        self.assertIsNone(ShmView.open(name))
        self.assertIsNone(ShmView.open(name))               # still absent: open() did not create it

    def test_reads_a_section_at_its_own_size(self):
        import mmap
        name = "I76DebugTest%d" % os.getpid()
        m = mmap.mmap(-1, 3000, tagname="Local\\" + name)  # a writer that made it 3000 bytes
        m[0:4] = b"abcd"
        v = ShmView.open("Local\\" + name)
        self.assertIsNotNone(v)
        self.assertGreaterEqual(v.size, 3000)
        self.assertEqual(v.read(0, 4), b"abcd")
        v.close(); m.close()

    def test_trainer_does_not_create_its_block(self):
        os.environ["I76TRAINER_SHM_SUFFIX"] = "DebugTest%d" % os.getpid()
        import importlib, debug_trainer
        importlib.reload(debug_trainer)
        t = debug_trainer.TrainerCore(Hub(), attach=False)
        t.tick()
        self.assertEqual(t.mode, "none")
        self.assertIsNone(ShmView.open(t.NAME))
        st = t.status()
        self.assertEqual(st["mode"], "none")
        self.assertTrue(any(p["key"] == "t05_hilltop" for p in st["presets"]))
        t.action({"action": "repair"})
        self.assertIn("repair: not attached", t.status()["log"][-1]["text"])
        t.action({"action": "preset", "key": "t05_hilltop"})
        self.assertTrue(any("teleport: not attached" in l["text"] for l in t.status()["log"]))
        t.close()


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


class EndToEnd(unittest.TestCase):
    """server + haptics host (live, --debug-udp, files only) + play (the recording as the game)"""

    @classmethod
    def setUpClass(cls):
        if "--unit" in sys.argv:
            raise unittest.SkipTest("--unit")
        if not os.path.exists(HOST_EXE):
            raise unittest.SkipTest("haptics host not built (tools\\haptics\\haptics.ps1 build)")
        os.makedirs(OUT, exist_ok=True)
        cls.rec = REC if os.path.exists(REC) else "synthetic"
        cls.tel, cls.tee, cls.hport, cls.http = free_udp(), free_udp(), free_udp(), free_tcp()
        env = dict(os.environ, I76TRAINER_SHM_SUFFIX="DebugE2E%d" % os.getpid())
        cls.procs = []
        cls.srv = subprocess.Popen([sys.executable, os.path.join(DEBUG, "i76debug.py"), "--http-port", str(cls.http), "--tel-port", str(cls.tel),
                                    "--tee", str(cls.tee), "--haptics-port", str(cls.hport), "--log", FIXTURE_LOG, "--no-attach", "--no-browser",
                                    "--seconds", "120"], stdout=open(os.path.join(OUT, "server.out"), "w"), stderr=subprocess.STDOUT, env=env)
        cls.procs.append(cls.srv)
        cls.host = subprocess.Popen([HOST_EXE, "live", "--source", "udp", "--port", str(cls.tee), "--sinks", "wheel-file,pad-file,lfe-wav,motion-file,motion-udp",
                                     "--out", os.path.join(OUT, "host"), "--seconds", "100", "--debug-udp", str(cls.hport)],
                                    stdout=open(os.path.join(OUT, "host.out"), "w"), stderr=subprocess.STDOUT)
        cls.procs.append(cls.host)
        for _ in range(50):
            try:
                get("http://127.0.0.1:%d/api/health" % cls.http, 1); break
            except OSError:
                time.sleep(0.2)
        time.sleep(1.5)                                     # the host JIT-warms before it listens
        cls.play = subprocess.Popen([HOST_EXE, "play", cls.rec, "--port", str(cls.tel)], stdout=open(os.path.join(OUT, "play.out"), "w"), stderr=subprocess.STDOUT)
        cls.procs.append(cls.play)
        # stream client in the background: count messages and remember which keys arrived
        cls.sse = {"messages": 0, "snapshot": False, "keys": set(), "samples": 0, "hsamples": 0, "events": 0}
        threading.Thread(target=cls.read_stream, daemon=True).start()
        # wait until every panel has its data (or 60 s)
        cls.state, t0 = None, time.time()
        while time.time() - t0 < 60:
            time.sleep(1.0)
            try:
                st = get("http://127.0.0.1:%d/api/state" % cls.http)
            except OSError:
                continue
            cls.state = st
            if cls.ready(st):
                break
        time.sleep(1.0)
        cls.state = get("http://127.0.0.1:%d/api/state" % cls.http)

    @staticmethod
    def ready(st):
        h = st.get("hap") or {}
        ev = st["ev"]["count"]
        return (st["overview"]["tel_frames"] > 300 and h.get("motion_out", {}).get("frames", 0) > 50 and ev.get("SHOT", 0) > 0
                and ev.get("EXPLOSION", 0) > 0 and ev.get("DAMAGE_SIDE", 0) > 0 and len(st["hsamples"]) > 50
                and any(abs(s.get("dev") or 0) > 0 for s in st["hsamples"]))

    @classmethod
    def read_stream(cls):
        try:
            r = urllib.request.urlopen("http://127.0.0.1:%d/api/stream?hz=10" % cls.http, timeout=10)
            ev = None
            for raw in r:
                line = raw.decode("utf-8").rstrip("\n")
                if line.startswith("event: snapshot"):
                    ev = "snapshot"
                elif line.startswith("data: "):
                    d = json.loads(line[6:])
                    cls.sse["messages"] += 1
                    if ev == "snapshot":
                        cls.sse["snapshot"] = True
                    cls.sse["keys"] |= set(d)
                    cls.sse["samples"] += len(d.get("samples", []))
                    cls.sse["hsamples"] += len(d.get("hsamples", []))
                    cls.sse["events"] += len(d.get("events", []))
                    ev = None
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        for p in getattr(cls, "procs", []):                 # only the processes this test started
            if p.poll() is None:
                p.terminate()
        for p in getattr(cls, "procs", []):
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()

    def test_overview(self):
        o = self.state["overview"]
        self.assertTrue(o["tel_frames"] > 300, o["tel_frames"])
        self.assertIn("udp 127.0.0.1:%d" % self.tel, o["tel_src"])
        self.assertIn("tee", o["tel_src"])
        self.assertEqual(o["tel_version"], 3)
        self.assertIn("speed", o["frame"])
        self.assertTrue(o["fps"] > 10, o["fps"])
        self.assertTrue(self.state["log"]["features"])
        self.assertEqual(o["game"]["log"], FIXTURE_LOG)

    def test_telemetry(self):
        s = self.state["samples"]
        self.assertGreater(len(s), 200)
        self.assertTrue(any(x["speed"] > 1 for x in s))
        self.assertTrue(any(abs(x["az"]) > 0 for x in s))
        self.assertGreater(len(self.state["trail"]), 5)

    def test_events(self):
        ev = self.state["ev"]
        for k in ("SHOT", "EXPLOSION", "SOUND_START", "DAMAGE_SIDE"):
            self.assertGreater(ev["count"].get(k, 0), 0, k)
        self.assertTrue(self.state["events"])
        self.assertTrue(ev["sounds"])
        self.assertTrue(self.state["hap_events"])           # host-derived events arrive through --debug-udp

    def test_force_feedback(self):
        h = self.state["hap"]
        self.assertEqual(h["kind"], "i76haptics")
        self.assertIn("center", h["wheel"]["channels"])
        self.assertTrue(any(abs(s["dev"] or 0) > 0 for s in self.state["hsamples"]))
        self.assertTrue(all("ch" in s for s in self.state["hsamples"]))

    def test_rumble(self):
        p = self.state["hap"]["pad"]
        self.assertTrue(p["open"])
        self.assertTrue(any((s["pl"] or 0) > 0 or (s["pr"] or 0) > 0 for s in self.state["hsamples"]))

    def test_lfe(self):
        l = self.state["hap"]["lfe"]
        self.assertTrue(l["open"])
        self.assertEqual(len(l["spectrum"]), len(l["spectrum_hz"]))
        self.assertEqual(l["spectrum_hz"][0], 10)
        self.assertEqual(l["spectrum_hz"][-1], 120)
        self.assertTrue(any((s["rms"] or 0) > 0 for s in self.state["hsamples"]))
        self.assertIn("stems", l)

    def test_motion(self):
        m = self.state["hap"]["motion_out"]
        self.assertTrue(m["open"])
        self.assertFalse(m["sending"])                       # files only: the host sent no motion UDP
        self.assertGreater(m["frames"], 50)
        self.assertTrue(m["targets"])
        self.assertIn("status", m)

    def test_collision_terrain_from_log(self):
        L = self.state["log"]
        self.assertEqual(L["coll"]["stepframe"]["pairs"], 525)
        self.assertEqual(L["bbox"]["boxes"], 10)
        self.assertEqual(len(L["terrain_drops"]), 3)
        self.assertEqual(L["lift_count"], 3)
        self.assertEqual(L["tex"]["dl"], 86)

    def test_trainer_panel(self):
        t = self.state["trainer"]
        self.assertEqual(t["mode"], "none")
        self.assertFalse(t["attach_enabled"])
        req = urllib.request.Request("http://127.0.0.1:%d/api/trainer" % self.http, data=json.dumps({"action": "repair"}).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read())
        self.assertTrue(j["ok"])
        self.assertIn("not attached", j["trainer"]["log"][-1]["text"])

    def test_log_endpoint_and_static(self):
        j = get("http://127.0.0.1:%d/api/log?q=TERRAIN-DROP" % self.http)
        self.assertEqual(len(j["lines"]), 3)
        for path in ("/", "/static/app.js", "/static/charts.js", "/static/app.css"):
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.http, path), timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertGreater(len(r.read()), 1000)

    def test_stream(self):
        self.assertTrue(self.sse["snapshot"])
        self.assertGreater(self.sse["messages"], 20)
        self.assertGreater(self.sse["samples"], 100)
        self.assertGreater(self.sse["hsamples"], 50)
        self.assertGreater(self.sse["events"], 0)
        for k in ("overview", "samples", "events", "hsamples", "hap", "log", "trainer"):
            self.assertIn(k, self.sse["keys"])


if __name__ == "__main__":
    argv = [a for a in sys.argv if a not in ("--unit",)]
    if "--rec" in argv:
        i = argv.index("--rec"); del argv[i:i + 2]
    unittest.main(argv=argv, verbosity=2)
