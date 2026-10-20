#!/usr/bin/env python3
r"""test_fullstate.py - offline tests for I76 Debug's full-state store / restore (i76trn.h i76trn_ext_t) and the haptics
starter (debug_haptics.py). No game, no device, no browser: a fake proxy block in this process stands in for the game.

    python tools\debug\tests\test_fullstate.py
"""
import json, mmap, os, shutil, struct, sys, tempfile, threading, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DEBUG = os.path.dirname(HERE)
TOOLS = os.path.dirname(DEBUG)
sys.path.insert(0, DEBUG)
SUFFIX = "FullStateTest%d" % os.getpid()
os.environ["I76TRAINER_SHM_SUFFIX"] = SUFFIX
import debug_core, debug_trainer, debug_haptics
import i76trainer_gui as gui
from debug_core import Hub

H = gui.CtlHeader(os.path.join(TOOLS, "trainer", "i76trn.h"))
C = H.consts


def fld(name):
    return next(f for f in H.structs["i76trn_ctl_t"][0] if f.name == name)


class FakeProxy:
    """Local\\I76Trainer<suffix> at 168 + sizeof(i76trn_ext_t), served by a thread like the proxy's frame hook: heartbeat,
    player present, STORE_STATE writes a known state, SET_STATE records the target it was given."""

    def __init__(self, ext=True):
        self.size = C["I76TRN_EXT_OFFSET"] + (H.structs["i76trn_ext_t"][1] if ext else 0)
        self.m = mmap.mmap(-1, self.size, tagname=C["I76TRN_SHM_NAME"] + SUFFIX)
        self.m[:] = b"\0" * self.size
        self.put("magic", C["I76TRN_MAGIC"]); self.put("version", C["I76TRN_VERSION"]); self.put("size", 168)
        self.put("player_present", 1)
        if ext:
            self.ext_put("ext_magic", C["I76TRN_EXT_MAGIC"])
        self.ext, self.applied, self.stop = ext, None, False
        self.state = {"valid": 1, "parts": C["I76TRN_ST_ALL"], "frame": 1234, "sim_frame": 77, "mass": 1800.0,
                      "rot": [1, 0, 0, 0, 0.9848, 0.1736, 0, -0.1736, 0.9848], "pos": [7950.5, 98.25, 44035.125],
                      "vel": [-20.0, -3.5, 0.25], "speed": 20.31, "inv_speed": 1 / 20.31, "rates": [0.1, 0.02, -0.01],
                      "accel": [0.5, -9.8, 0.0], "ent_flags": 4, "wheel_mask": 0x33,
                      "wheel": [{"present": 1, "susp_offset": 0.05 * k, "iir": [1, 2, 3, 4, 5]} for k in range(6)]}
        self.t = threading.Thread(target=self.run, daemon=True); self.t.start()

    def put(self, name, v):
        f = fld(name)
        struct.pack_into("<" + gui.SCALARS[f.type] * f.count, self.m, f.offset, *((v,) if f.count == 1 else v))

    def get(self, name):
        f = fld(name)
        v = struct.unpack_from("<" + gui.SCALARS[f.type] * f.count, self.m, f.offset)
        return v[0] if f.count == 1 else v

    def eoff(self, name):
        return C["I76TRN_EXT_OFFSET"] + H.offset("i76trn_ext_t", name)

    def ext_put(self, name, v):
        struct.pack_into("<I", self.m, self.eoff(name), v)

    def ext_get(self, name):
        return struct.unpack_from("<I", self.m, self.eoff(name))[0]

    def run(self):
        hb = 0
        while not self.stop:
            hb += 1
            self.put("heartbeat", hb)
            req = self.get("req_seq")
            if req != self.get("ack_seq"):
                cmd = self.get("cmd")
                self.put("cmd_result", 0)
                if self.ext and cmd == C["I76TRN_CMD_STORE_STATE"]:
                    raw = debug_trainer.dict_to_struct(H, "i76trn_state_t", self.state)
                    self.m[self.eoff("stored"):self.eoff("stored") + len(raw)] = raw
                    self.ext_put("store_seq", self.ext_get("store_seq") + 1)
                elif self.ext and cmd == C["I76TRN_CMD_SET_STATE"]:
                    n = H.structs["i76trn_state_t"][1]
                    self.applied = (debug_trainer.struct_to_dict(H, "i76trn_state_t", bytes(self.m[self.eoff("target"):self.eoff("target") + n])),
                                    self.ext_get("restore_parts"))
                    self.ext_put("restore_seq", self.ext_get("restore_seq") + 1)
                elif cmd == C["I76TRN_CMD_TELEPORT"]:
                    self.applied = ("teleport", self.get("pos"), self.get("vel"))
                elif cmd in (C["I76TRN_CMD_STORE_STATE"], C["I76TRN_CMD_SET_STATE"]):
                    self.put("cmd_result", 2)
                self.put("ack_seq", req)
            time.sleep(0.005)

    def close(self):
        self.stop = True; self.t.join(1); self.m.close()


class FakeGame:
    h = 0

    def u32(self, a):
        return 0


def core(wp_path):
    """a TrainerCore 'attached' to a fake game (no process opened) over the fake block"""
    debug_trainer.WAYPOINTS = wp_path
    gui.process_alive = lambda g: True
    gui.read_status_direct = lambda g: {"present": False}
    gui.weapon_slots = lambda g: []
    t = debug_trainer.TrainerCore(Hub(), attach=False)
    t.game, t.pid, t.path = FakeGame(), 1, r"C:\x\i76.exe"
    return t


def settle(t, cond, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        t.tick()
        if cond():
            return True
        time.sleep(0.05)
    return False


class Layout(unittest.TestCase):
    def test_sizes_and_v1_unchanged(self):
        self.assertEqual(H.structs["i76trn_ctl_t"][1], 168)                 # the version-1 block every old reader checks
        self.assertEqual(C["I76TRN_VERSION"], 1)
        self.assertEqual(C["I76TRN_EXT_OFFSET"], 168)
        self.assertEqual(H.structs["i76trn_state_t"][1], 632)
        self.assertEqual(H.structs["i76trn_ext_t"][1], 1304)

    def test_state_round_trip(self):
        st = {"valid": 1, "pos": [1.5, 2.25, -3.125], "rot": [0.5] * 9, "vel": [1, 2, 3], "ent_flags": 4,
              "wheel": [{"present": 1, "iir": [1.0, 2.0, 3.0, 4.0, 5.0], "local_y": 0.625}] * 6}
        raw = debug_trainer.dict_to_struct(H, "i76trn_state_t", st)
        self.assertEqual(len(raw), 632)
        back = debug_trainer.struct_to_dict(H, "i76trn_state_t", raw)
        self.assertEqual(back["pos"], [1.5, 2.25, -3.125])
        self.assertEqual(back["wheel"][5]["iir"], [1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(back["ent_flags"], 4)
        self.assertEqual(debug_trainer.dict_to_struct(H, "i76trn_state_t", back), raw)
        self.assertTrue(debug_trainer.state_summary(back)["airborne"])


class FullState(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.wp = os.path.join(self.dir, "waypoints.json")
        json.dump([{"x": 8231.4, "y": 20.8, "z": 44286.3, "saved": "2026-10-03 11:17"}, None, None], open(self.wp, "w"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_store_restore_waypoints(self):
        fp = FakeProxy()
        t = core(self.wp)
        try:
            self.assertTrue(settle(t, lambda: t.mode == "proxy"))
            st = t.status()
            self.assertEqual(st["full_state"], "proxy")
            self.assertFalse(st["waypoints"][0]["full"])                    # the old entry loads, position only
            self.assertTrue(settle(t, lambda: fp.ext_get("hotkeys") == 1))   # Ctrl+9 / Ctrl+0 enabled by default
            # old waypoint: position-only teleport
            t.action({"action": "wp_go", "i": 0}); settle(t, lambda: not t.pending)
            self.assertEqual(fp.applied[0], "teleport")
            self.assertAlmostEqual(fp.applied[1][0], 8231.4)
            # save full state into slot 2, go
            t.action({"action": "wp_save", "i": 1}); settle(t, lambda: not t.pending)
            w = json.load(open(self.wp))[1]
            self.assertEqual(w["how"], "proxy full state")
            self.assertEqual(w["state"]["vel"], [-20.0, -3.5, 0.25])
            self.assertAlmostEqual(w["x"], 7950.5)                         # x / y / z stay at the top for old readers
            self.assertTrue(w["summary"]["airborne"])
            t.action({"action": "wp_go", "i": 1}); settle(t, lambda: not t.pending)
            target, parts = fp.applied
            self.assertEqual(parts, 0)                                      # all parts
            self.assertEqual(target["pos"], [7950.5, 98.25, 44035.125])
            self.assertEqual(target["vel"], [-20.0, -3.5, 0.25])
            self.assertAlmostEqual(target["wheel"][2]["susp_offset"], 0.1, places=6)
            # go stopped: pose with zero motion
            t.action({"action": "wp_go", "i": 1, "still": True}); settle(t, lambda: not t.pending)
            target, parts = fp.applied
            self.assertEqual(target["vel"], [0.0, 0.0, 0.0])
            self.assertEqual(parts, C["I76TRN_ST_POSE"] | C["I76TRN_ST_MOTION"])
            # quick slot, as Ctrl+9 / Ctrl+0
            t.action({"action": "store"}); settle(t, lambda: not t.pending)
            self.assertEqual(t.status()["quick"]["kmh"], round(((20 ** 2 + 3.5 ** 2 + 0.25 ** 2) ** 0.5) * 3.6, 1))
            t.action({"action": "restore"}); settle(t, lambda: not t.pending)
            self.assertEqual(fp.applied[0]["pos"], [7950.5, 98.25, 44035.125])
            t.action({"action": "hotkeys", "on": False}); settle(t, lambda: fp.ext_get("hotkeys") == 0)
            self.assertEqual(fp.ext_get("hotkeys"), 0)
            t.action({"action": "hotkeys", "on": True}); settle(t, lambda: fp.ext_get("hotkeys") == 1)
        finally:
            t.close()
            self.assertEqual(fp.ext_get("hotkeys"), 0)                     # closing releases the keys it set
            fp.close()

    def test_old_proxy_keeps_position_teleport(self):
        fp = FakeProxy(ext=False)                                           # a version-1 proxy: 168 B, no ext magic
        t = core(self.wp)
        try:
            self.assertTrue(settle(t, lambda: t.mode == "proxy"))
            self.assertIn("predates", t.status()["full_state"])
            t.action({"action": "wp_save", "i": 2}); settle(t, lambda: not t.pending)
            # no telemetry and no direct reads in this fake: nothing to save, and nothing was sent as a state command
            self.assertIsNone(json.load(open(self.wp))[2])
            t.action({"action": "wp_go", "i": 0}); settle(t, lambda: not t.pending)
            self.assertEqual(fp.applied[0], "teleport")
        finally:
            t.close(); fp.close()


class Haptics(unittest.TestCase):
    class Tel:
        mode = "udp 127.0.0.1:7999"

        def __init__(self):
            self.tee = []

        def add_tee(self, p):
            self.tee.append(p)

    def test_no_device_refused_then_forced(self):
        debug_haptics.devices = lambda: []
        tel = self.Tel()
        hl = debug_haptics.HapticsLauncher(Hub(), tel, 17999, hint=sys.executable)   # python.exe stands in for the host exe
        ok, msg = hl.start()
        self.assertFalse(ok)
        self.assertIn("no wheel or gamepad found", msg)
        st = hl.status()
        self.assertEqual(st["devices"], [])
        self.assertFalse(st["running"])
        ok, msg = hl.start(force=True)                                      # the dry run anyway: started, fed by the tee
        self.assertTrue(ok, msg)
        self.assertIn("dry run", msg)
        self.assertEqual(tel.tee, [debug_haptics.TEE_PORT])
        self.assertIn("--debug-udp 127.0.0.1:17999", hl.cmd)
        self.assertNotIn("--live", hl.cmd.split())
        for _ in range(50):
            if not hl.running():
                break
            time.sleep(0.1)
        self.assertIsNotNone(hl.status().get("exited"))                     # python.exe 'live' exits: the page shows the exit + log tail
        self.assertFalse(hl.stop()[0])                                      # nothing of ours left running

    def test_live_needs_a_device_and_shm_mode_refuses(self):
        debug_haptics.devices = lambda: []
        hl = debug_haptics.HapticsLauncher(Hub(), self.Tel(), 17999, hint=sys.executable)
        self.assertIn("--live needs", hl.start(live=True, force=True)[1])
        tel = self.Tel(); tel.mode = "shm (existing only) - udp 127.0.0.1:7676 is taken"
        debug_haptics.devices = lambda: [("joystick", "Wheel (joystick 1)")]
        hl = debug_haptics.HapticsLauncher(Hub(), tel, 17999, hint=sys.executable)
        ok, msg = hl.start()
        self.assertFalse(ok)
        self.assertIn("could not bind the telemetry port", msg)
        self.assertEqual(hl.status()["devices"], ["Wheel (joystick 1)"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
