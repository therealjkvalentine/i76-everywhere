#!/usr/bin/env python3
r"""test_logger.py - offline tests for the I76 Debug physics / memory logger (tools/debug/debug_logger.py). No game, no
browser; loopback only, free ports (never 7676), the read-only reader off (--no-attach).

    python tools\debug\tests\test_logger.py            unit + end to end (about 20 s)
    python tools\debug\tests\test_logger.py --unit     unit tests only

Unit: a real telemetry recording (the overnight P2 t05 .i76rec, else skipped) through Hub -> PhysLogger; the columns are
mem2csv.py's (imported from the lab when it is there, else the copy in debug_logger); every phys cell but phase parses as
a number (owner_log.py drops a row that does not); frame gaps count as missed; marks set the phase; auto start / stop;
hotkey names parse. When the lab memtrace tools exist, owner_log.py summary and fingerprint.py metrics are run on the
output and must read it.
End to end: i76debug.py --no-attach --no-browser on free ports, the recording replayed to its telemetry port at 4x,
/api/logger start / mark / stop over HTTP, files checked.
"""
import csv, json, os, shutil, socket, subprocess, sys, tempfile, threading, time, unittest, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEBUG = os.path.dirname(HERE)
TOOLS = os.path.dirname(DEBUG)
sys.path.insert(0, DEBUG)
sys.path.insert(0, os.path.join(TOOLS, "haptics", "design"))
import debug_core, debug_logger, i76rec

REC = r"C:\Users\james\i76-uncap-lab\autotest\runs\overnight-20261011-203304\P2\t05.i76rec"
MEMTRACE = debug_logger.MEMTRACE


def free_udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def free_tcp():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def run_recording(lg, recs, drop=()):
    hub = debug_core.Hub()
    hub.logger = lg
    for i, (t, d) in enumerate(recs):
        if i not in drop:
            hub.on_datagram(d, "test")
    return hub


class Columns(unittest.TestCase):
    def test_same_columns_as_mem2csv(self):
        p = os.path.join(MEMTRACE, "mem2csv.py")
        if not os.path.exists(p):
            self.skipTest("no lab mem2csv.py")
        sys.path.insert(0, MEMTRACE)
        import mem2csv
        self.assertEqual(debug_logger.LAB_COLS + debug_logger.EXTRA_COLS, mem2csv.LAB + mem2csv.EXTRA)
        self.assertEqual(debug_logger.PHYS_COLS[:len(mem2csv.LAB + mem2csv.EXTRA)], mem2csv.LAB + mem2csv.EXTRA)

    def test_hotkey_names(self):
        self.assertEqual(debug_logger.parse_hotkey("scroll"), (0x4000, 0x91))
        self.assertEqual(debug_logger.parse_hotkey("Shift+Scroll"), (0x4004, 0x91))
        self.assertEqual(debug_logger.parse_hotkey("ctrl+alt+f11"), (0x4003, 0x7A))
        with self.assertRaises(ValueError):
            debug_logger.parse_hotkey("ctrl+banana")


class Recording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(REC):
            raise unittest.SkipTest("no recording at %s" % REC)
        cls.meta, cls.recs = i76rec.read(REC)
        cls.tmp = tempfile.mkdtemp(prefix="trnlog-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_files_rows_marks_gaps(self):
        lg = debug_logger.PhysLogger(root=self.tmp, reader=False, summary=False, label="unit")
        self.assertFalse(lg.mark("x")[0])                    # not recording
        self.assertTrue(lg.start(by="test")[0])
        drop = set(range(100, 105))
        hub = debug_core.Hub(); hub.logger = lg
        for i, (t, d) in enumerate(self.recs):
            if i in drop:
                continue
            hub.on_datagram(d, "test")
            if i == 1000:
                self.assertTrue(lg.mark("landing, hard")[0])
        ok, msg = lg.stop("test")
        self.assertTrue(ok, msg)
        d = lg.history[-1]["dir"]
        frames = list(csv.DictReader(open(os.path.join(d, "mem.frames.csv"))))
        phys = list(csv.DictReader(open(os.path.join(d, "mem.phys.csv"))))
        self.assertEqual(len(frames), len(self.recs) - len(drop))
        self.assertEqual(sum(int(r["skipped"]) for r in frames), len(drop))
        self.assertEqual(list(phys[0].keys()), debug_logger.PHYS_COLS)
        for r in phys:                                       # owner_log.py: every cell but phase must be a number
            for k, v in r.items():
                if k != "phase":
                    float(v)
        self.assertEqual(phys[0]["phase"], "play")
        self.assertEqual(phys[-1]["phase"], "mark01")
        self.assertEqual(phys[-1]["mark"], "1")
        mk = list(csv.DictReader(open(os.path.join(d, "marks.csv"))))
        self.assertEqual(len(mk), 1)
        self.assertEqual(mk[0]["label"], "landing; hard")
        meta = json.load(open(os.path.join(d, "meta.json")))
        self.assertEqual(meta["frames_missed"], len(drop))
        self.assertEqual(meta["phys_rows"], len(phys))
        self.assertTrue(os.path.exists(os.path.join(lg.rundir, "raw", "S01.LOG")))
        # the frame values are the telemetry's, bit for bit at the CSV precision
        fr, _ = debug_core.i76tel.decode_datagram(hub.tel_h, self.recs[-1][1])
        self.assertEqual(int(phys[-1]["frame"]), fr["frame"])
        self.assertAlmostEqual(float(phys[-1]["yaw_rate"]), fr["yaw_rate"], places=5)
        self.assertEqual(int(phys[-1]["flags"]), fr["flags"])
        self.__class__.done_dir = lg.rundir

    def test_auto_start_and_stop(self):
        lg = debug_logger.PhysLogger(root=self.tmp, reader=False, summary=False, auto=True)
        hub = run_recording(lg, self.recs[:200])
        self.assertTrue(lg.recording)
        self.assertEqual(lg.started_by, "auto")
        lg.present_at -= 10                                  # the player gone for 10 s
        lg.tick()
        self.assertFalse(lg.recording)
        self.assertEqual(lg.history[-1]["frames"], 200)
        # a stop by hand under --log-auto holds until the player has gone (no immediate restart)
        run_recording(lg, self.recs[200:210])
        self.assertTrue(lg.recording)
        lg.stop("button")
        run_recording(lg, self.recs[210:220])
        self.assertFalse(lg.recording)

    def test_lab_tools_read_it(self):
        if not os.path.exists(os.path.join(MEMTRACE, "owner_log.py")):
            self.skipTest("no lab memtrace tools")
        lg = debug_logger.PhysLogger(root=self.tmp, reader=False, summary=False, label="labtools")
        lg.start(by="test")
        run_recording(lg, self.recs)
        lg.stop("test")
        p = subprocess.run([sys.executable, "-I", os.path.join(MEMTRACE, "owner_log.py"), "summary", lg.rundir],
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr)
        sm = json.load(open(os.path.join(lg.rundir, "summary.json")))
        s1 = sm["sessions"][0]
        self.assertEqual(len(s1["missions"]), 1)
        self.assertEqual(s1["missions"][0]["frames_n"], len(self.recs))
        self.assertGreaterEqual(len(s1["jumps"]), 1)
        fp = os.path.join(self.tmp, "t05-trnlog-unit")                 # a t05 context name for fingerprint.py
        shutil.copytree(lg.history[-1]["dir"], fp)
        p = subprocess.run([sys.executable, "-I", os.path.join(MEMTRACE, "fingerprint.py"), "metrics", fp],
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("frames.sim_dt_p50@t05", p.stdout)
        self.assertIn("mode.arcade_share@t05", p.stdout)


def get(url, data=None, timeout=5):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class EndToEnd(unittest.TestCase):
    def test_server_start_mark_stop(self):
        if not os.path.exists(REC):
            self.skipTest("no recording")
        meta, recs = i76rec.read(REC)
        tmp = tempfile.mkdtemp(prefix="trnlog-e2e-")
        tel, http = free_udp(), free_tcp()
        srv = subprocess.Popen([sys.executable, os.path.join(DEBUG, "i76debug.py"), "--no-browser", "--no-attach", "--no-trainer",
                                "--tel-port", str(tel), "--haptics-port", "0", "--http-port", str(http), "--log-dir", tmp,
                                "--log-label", "e2e", "--no-summary", "--game-dir", tmp, "--seconds", "40"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            base = "http://127.0.0.1:%d" % http
            for _ in range(50):
                try:
                    get(base + "/api/health"); break
                except OSError:
                    time.sleep(0.2)
            st = get(base + "/api/logger")
            self.assertFalse(st["recording"])
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            r = get(base + "/api/logger", {"op": "start", "label": "e2e"})
            self.assertTrue(r["ok"], r)
            t0, w0 = recs[0][0], time.perf_counter()
            for i, (t, d) in enumerate(recs[:1200]):           # 4x real time
                lag = (t - t0) / 4.0 - (time.perf_counter() - w0)
                if lag > 0:
                    time.sleep(lag)
                s.sendto(d, ("127.0.0.1", tel))
                if i == 600:
                    self.assertTrue(get(base + "/api/logger", {"op": "mark", "label": "half"})["ok"])
            time.sleep(0.5)
            st = get(base + "/api/state?history=1")["logger"]
            self.assertTrue(st["recording"])
            r = get(base + "/api/logger", {"op": "stop"})
            self.assertTrue(r["ok"], r)
            h = r["logger"]["history"][-1]
            self.assertEqual(h["marks"], 1)
            self.assertGreaterEqual(h["frames"], 1190)            # loopback UDP: allow a handful of drops, they are counted
            self.assertEqual(h["frames"] + h["missed"], 1200)
            rows = list(csv.DictReader(open(os.path.join(h["dir"], "mem.phys.csv"))))
            self.assertEqual(len(rows), h["rows"])
            self.assertIn("mark01", {x["phase"] for x in rows})
        finally:
            srv.terminate()
            try:
                srv.wait(10)
            except subprocess.TimeoutExpired:
                srv.kill()
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unit = "--unit" in sys.argv
    argv = [a for a in sys.argv if a != "--unit"]
    if unit:
        suite = unittest.TestSuite()
        for c in (Columns, Recording):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(c))
        sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
    unittest.main(argv=argv, verbosity=2)
