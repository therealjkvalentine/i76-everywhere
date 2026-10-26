r"""run_scenario.py - replay one scripted scenario on the SANDBOX game and record telemetry (+ an optional call census).

    python verify\run_scenario.py drive [--census verify\batches\batch-001.json] [--secs 90] [--profile stock20|stock60|fixed]

VERIFICATION-PROGRAM section 2.1. Scenarios are verify\scenarios\<id>.json (steps below); the run writes
verify\runs\<id>\<timestamp>\{telemetry.csv, events.csv, actions.csv, mciproxy.log, manifest.json} and, with
--census, census.jsonl + census.series.bin/json + census\ (censuslib.py).

Launch (fr_probe.py / TEST-FRAMERATE.ps1): refuse when an i76* process runs or game\.console-test.lock exists;
create the lock; back up game\STRLKUP.DLL to .pretest and copy music-fix\Strlkup.dll over it; boot i76.exe -glide
straight into t01 (I76_MISSION=t01.msn, I76_SKIP_MOVIES=1, I76_TELEMETRY=1, I76MUSIC_LOG=1 + the profile's switches);
focus the window (focuslib.ps1) while it boots; Esc off the pre-start screen (play mode 0x20); wait for the player
entity [[0x54a264]]+0x70, for the frame counter 0x5a7e1c to move and for the mission script to hand the camera over
([0x4c2720] != 0x48e190; keys pressed before that are lost, capture 014). Every step is confirmed by state (speed,
gear, flags from the entity), never by pictures. At the end: WM_CLOSE, kill after 10 s, restore the DLL, remove the lock.

Census attach points (--census): default = frida.attach right after launch (1-2 s in; the mission has usually loaded by
2.4 s, so load-time code is partly missed); --attach-after-entity = hook once the player entity exists (phase 1, pass
`entity`: post-load state in every run); --attach-at-spawn = the game is started by frida.spawn (CreateProcess suspended;
the loader and every static DLL's DllMain, the proxy's patches included, run while Frida injects), the batch is hooked
before WinMain's first instruction and the process is then resumed (pass `early`: startup, loaders and init are counted).

Boot kinds (scenario JSON "boot"): "mission" (default: I76_MISSION direct boot into --mission) or "menu" (no mission:
the intro movies play (Esc taps skip them while the game state 0x4c2164 is not 6), the shell main menu comes up (state 6)
and sits; --secs counts from launch; no entity, no frame counter, nothing clicked).

Step ops (scenario JSON "steps"): {"op":"wait","s":N} | {"op":"tap","key":"X"} | {"op":"hold","key":"W","s":N}
(s = -1: until the duration ends; "keys":["W","A"] for a chord) | {"op":"brake_to_stop","max_s":N} (hold S until speed < 0.5) | {"op":"check",
"speed_gt":v | "speed_lt":v | "gear_in":[...] | "engine_on":true}. --secs N sets the recording duration from the
hand-over; the step list is cut off or padded with idle to fit.

Added for take-damage (2026-10-02):
  {"op":"drive_to","x":X,"z":Z,"radius":R,"max_s":N,"ram_s":M}  hold W and steer (A/D, closed loop on obj+0x18 heading
      vs the bearing to (X, Z), 10 Hz) until within R m or N s; then keep W for M more seconds (ram the target).
  {"op":"turn_to","heading_deg":H,"max_s":N,"tol_deg":T}       W + A/D until the heading is within T deg of H.
  {"op":"poke","what":"armour"|"chassis"|"engine_hp"|"susp_hp"|"brake_hp"|"wheel_hp","pct":P,"side":s|"slot":k}
      write the player's component / side value to P% of its max (i76trainer.Game.wr, read back; the armour / chassis
      HUD copies +0x178 / +0x18c follow). Recorded in manifest "pokes" and actions.csv. Values are not restored: the
      mission is quit at the end.

Added for jump / radar-lock / camera-cycle (2026-10-02):
  {"op":"launch","vy":V,"dy":D}   fr_probe --place's write path (trainer Game.wr, repeated 6 x 12 ms): the player object is
      lifted D m (obj+0x48) and its velocity ent+0xbc gets y = V m/s with x/z kept (Runner.jump_launch), i.e. the car leaves a ramp at its
      current heading and speed. Logged with the read-back and the frame the airborne flag 0x4 came up.
  {"op":"lift","m":M}             fr_probe --drop: the car is lifted M m and falls (vy = 0 at release).
  {"op":"check", ... "airborne":b, "airborne_frames_gt":N, "cam_mode_in":[..], "radar_locked":b, "radar_range_in":[..]}
  "watch": ["cam", "radar", "airborne"] (scenario key): a 20 Hz thread logs every change of camera_mode 0x4c2728 / the camera
      callback 0x4c2720, of the radar block [[ent+0x434]+0x70] (range index, flags, locked contact) and of the airborne flag
      to actions.csv ("watch" rows, with the frame) and to manifest "watch" / "airborne_spells".
"""
import argparse
import datetime
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (EXE, G, LOCK, MAP, NEWDLL, RUNS, SCENARIOS, TIME_ADDR, Functions, Mem, ensure_dirs, focus_game,  # noqa: E402
                    key_down, key_tap, key_up, log, md5_file, trainer_path, wake_display)
import tellib  # noqa: E402

# poke targets: (how to find the base, value offset, max offset). Component data = [[ent+slot]+0x70] (i76trainer COMP_HEALTH:
# engine type 21 / susp 23 -> hp +0, max +4; brakes type 22 and wheels type 30 -> hp +4, max +8). Sides: ent+0x138 armour
# (max +0x158, HUD copy +0x178), ent+0x148 chassis (max +0x168, HUD +0x18c) - the values object_HealthFraction reads.
POKE_TARGETS = {
    "engine_hp": ("engine", 0x0, 0x4), "susp_hp": ("susp", 0x0, 0x4), "brake_hp": ("brake", 0x4, 0x8), "wheel_hp": ("wheel", 0x4, 0x8),
    "armour": ("side", 0x138, 0x158), "chassis": ("side", 0x148, 0x168),
}
HUD_COPY = {"armour": 0x178, "chassis": 0x18c}
STEER_PERIOD = 0.1            # closed-loop steer update, s
STEER_DEADBAND_DEG = 4.0

PROFILES = {
    "stock20": {"I76_FPS_CAP": "20"},                  # the stock-era frame rate through the proxy's cap (steps 1-2 per frame)
    "stock60": {},                                     # the display's 60 Hz uncapped (1 step per frame)
    "fixed": {"I76_HIRES_CLOCK": "1", "I76_FIXED_STEP": "24", "I76_FRAMERATE_FIXES": "1", "I76_ENGINE_DT_FIX": "1", "I76_RENDER_INTERP": "1"},
}
STOP_SPEED = 0.5
GAME_STATE = 0x4c2164          # mission.md: 5 mission running (data init), 6 shell running
MENU_ESC_FROM_S = 8.0          # --boot menu: first Esc (skips the intro movies) this long after launch
MENU_ESC_EVERY_S = 3.0


class SpawnedProcess:
    """subprocess.Popen's poll/wait/kill/pid/returncode over a pid frida.spawn created (ctypes, no psutil dependency)."""
    STILL_ACTIVE = 259

    def __init__(self, pid):
        import ctypes
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.pid = pid
        self.returncode = None
        # PROCESS_TERMINATE | SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
        self.h = self.k32.OpenProcess(0x0001 | 0x00100000 | 0x1000, False, pid)
        if not self.h:
            raise OSError("OpenProcess(%d) failed: %d" % (pid, ctypes.get_last_error()))

    def poll(self):
        import ctypes
        if self.returncode is not None:
            return self.returncode
        code = ctypes.c_ulong()
        if self.k32.GetExitCodeProcess(self.h, ctypes.byref(code)) and code.value != self.STILL_ACTIVE:
            self.returncode = int(code.value)
        return self.returncode

    def wait(self, timeout=None):
        ms = 0xFFFFFFFF if timeout is None else int(timeout * 1000)
        self.k32.WaitForSingleObject(self.h, ms)
        return self.poll()

    def kill(self):
        if self.poll() is None:
            self.k32.TerminateProcess(self.h, 1)


class Runner:
    TEL_KEEP = False          # poke.py sets True: the recorder also keeps the decoded frames in memory (tellib keep=)

    def __init__(self, a, scenario):
        self.a, self.sc = a, scenario
        self.id = scenario["id"]
        self.ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.out = os.path.join(RUNS, self.id, self.ts)
        os.makedirs(self.out)
        self.man = {"scenario": self.id, "timestamp": self.ts, "out": self.out, "args": vars(a), "scenario_file": scenario.get("_file"),
                    "profile": a.profile, "env_switches": PROFILES[a.profile], "errors": [], "checks": [], "warnings": []}
        self.actions = open(os.path.join(self.out, "actions.csv"), "w", encoding="utf-8")
        self.actions.write("t_wall,t_scn,frame,sim_time,speed,gear,flags,mode,action,detail\n")
        self.p = None
        self.mem = None
        self.t0 = None
        self.census = None
        self.session = None
        self.tel = None
        self.held = set()
        self.act_lock = threading.Lock()
        self.watcher = None

    # ------------------------------------------------------------------ bookkeeping
    def act(self, action, detail=""):
        st = self.mem.state() if self.mem else {}
        row = [round(time.time(), 3), round(time.perf_counter() - self.t0, 3) if self.t0 else "", st.get("frame"), st.get("sim_time"),
               st.get("speed"), st.get("gear"), st.get("flags"), st.get("mode"), action, str(detail).replace(",", ";")]
        with self.act_lock:
            self.actions.write(",".join("" if v is None else (("%.3f" % v) if isinstance(v, float) else str(v)) for v in row) + "\n")
            self.actions.flush()
        log("%-14s %s | %s" % (action, detail, {k: st.get(k) for k in ("frame", "speed", "gear", "mode")}))

    # ------------------------------------------------------------------ state watcher (camera / radar / airborne transitions)
    WATCH_PERIOD = 0.05

    def start_watch(self):
        what = self.sc.get("watch") or []
        if not what:
            return
        self.man["watch"] = []
        self.man["airborne_spells"] = []
        self._watch_stop = threading.Event()
        self.watcher = threading.Thread(target=self._watch_loop, args=(what,), daemon=True)
        self.watcher.start()

    def stop_watch(self):
        if self.watcher:
            self._watch_stop.set()
            self.watcher.join(2.0)
            sp = self.man.get("airborne_spells") or []
            if sp and sp[-1].get("land_frame") is None:         # still in the air at the end
                sp[-1]["land_frame"] = self.mem.frame()
                sp[-1]["frames"] = (sp[-1]["land_frame"] or 0) - sp[-1]["takeoff_frame"]
                sp[-1]["open"] = True

    def _watch_sample(self, what):
        s = {}
        if "cam" in what:
            s["cam"] = (self.mem.cam_mode(), self.mem.cam_cb())
        if "radar" in what:
            r = self.mem.radar()
            s["radar"] = (r["range"], r["flags"], r["target"]) if r else None
        if "airborne" in what:
            s["airborne"] = self.mem.airborne()
        return s

    def _watch_loop(self, what):
        last = {}
        while not self._watch_stop.is_set():
            try:
                cur = self._watch_sample(what)
            except Exception:  # noqa: BLE001  (the game is quitting)
                break
            fr = self.mem.frame()
            for k, v in cur.items():
                if k in last and last[k] == v:
                    continue
                if k in last:
                    if k == "cam":
                        detail = "cam_mode %s -> %s (cb 0x%x -> 0x%x)" % (last[k][0], v[0], last[k][1] or 0, v[1] or 0)
                    elif k == "radar":
                        detail = "radar %s -> %s (range; flags; target)" % (
                            "none" if last[k] is None else "%d;0x%x;0x%x" % last[k], "none" if v is None else "%d;0x%x;0x%x" % v)
                    else:
                        detail = "airborne %s -> %s" % (last[k], v)
                        sp = self.man["airborne_spells"]
                        if v:
                            sp.append({"takeoff_frame": fr, "land_frame": None, "frames": None, "t_scn": round(time.perf_counter() - self.t0, 3) if self.t0 else None})
                        elif sp and sp[-1]["land_frame"] is None:
                            sp[-1]["land_frame"] = fr
                            sp[-1]["frames"] = (fr or 0) - (sp[-1]["takeoff_frame"] or 0)
                    self.man["watch"].append({"t_scn": round(time.perf_counter() - self.t0, 3) if self.t0 else None, "frame": fr, "what": k,
                                              "from": last[k], "to": v})
                    self.act("watch", detail)
                last[k] = v
            time.sleep(self.WATCH_PERIOD)

    def airborne_frames(self):
        """Frames spent with the airborne flag so far (watch 'airborne'), the open spell counted to the current frame."""
        tot = 0
        for sp in self.man.get("airborne_spells") or []:
            end = sp["land_frame"] if sp["land_frame"] is not None else self.mem.frame()
            tot += max((end or 0) - (sp["takeoff_frame"] or 0), 0)
        return tot

    def fail(self, msg):
        self.man["errors"].append(msg)
        log("ERROR: " + msg)

    def check(self, name, ok, detail):
        self.man["checks"].append({"check": name, "ok": bool(ok), "detail": detail, "t_scn": round(time.perf_counter() - self.t0, 2) if self.t0 else None})
        self.act("check", "%s %s %s" % (name, "PASS" if ok else "FAIL", detail))
        return ok

    # ------------------------------------------------------------------ preflight / launch
    def preflight(self):
        import psutil
        procs = [q.pid for q in psutil.process_iter(["name"]) if (q.info["name"] or "").lower().startswith("i76")]
        if procs:
            raise SystemExit("ABORT: an i76 process is already running: %s" % procs)
        if os.path.exists(LOCK):
            raise SystemExit("ABORT: %s exists: %s" % (LOCK, open(LOCK).read()))
        if not tellib.port_free(7676):
            raise SystemExit("ABORT: UDP 7676 is taken (another telemetry listener?)")
        for f in ("i76.exe", "STRLKUP.DLL", "input.map"):
            if not os.path.exists(os.path.join(G, f)):
                raise SystemExit("ABORT: %s missing in %s" % (f, G))
        open(LOCK, "w").write("verify/run_scenario.py %s pid %d %s" % (self.id, os.getpid(), time.ctime()))
        self.man["lock"] = LOCK

    def install_proxy(self):
        dll, bak = os.path.join(G, "STRLKUP.DLL"), os.path.join(G, "STRLKUP.DLL.pretest")
        if os.path.exists(bak):                       # a killed run left its backup: restore first (TEST-FRAMERATE Restore)
            shutil.copy2(bak, dll); os.remove(bak)
            self.man["warnings"].append("restored a leftover STRLKUP.DLL.pretest before installing")
        shutil.copy2(dll, bak)
        shutil.copy2(NEWDLL, dll)
        self.man["proxy"] = {"installed_from": NEWDLL, "md5": md5_file(NEWDLL), "backup": bak, "original_md5": md5_file(bak)}

    def restore_proxy(self):
        dll, bak = os.path.join(G, "STRLKUP.DLL"), os.path.join(G, "STRLKUP.DLL.pretest")
        if os.path.exists(bak):
            shutil.copy2(bak, dll); os.remove(bak)
            self.man["proxy_restored"] = md5_file(dll)

    @property
    def menu_boot(self):
        return self.sc.get("boot") == "menu"

    def launch(self):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("I76")}
        if self.a.nomission or self.menu_boot:    # plain boot: fr_probe --nomission (Melee route in wait_for_mission) or the shell menu
            env.update({"I76_TELEMETRY": "1", "I76MUSIC_LOG": "1"})   # I76_SKIP_MOVIES only acts with I76_MISSION (strlkproxy.c)
        else:
            env.update({"I76_MISSION": self.a.mission, "I76_SKIP_MOVIES": "1", "I76_TELEMETRY": "1", "I76MUSIC_LOG": "1"})
        env.update(PROFILES[self.a.profile])
        env.update(self.sc.get("env") or {})                       # scenario "env": {"I76_X": "v"} (proxy switches the run needs)
        for kv in (self.a.env or []):                              # --env I76_FAR_CLIP=1800 (repeatable; wins over the scenario)
            k, _, v = kv.partition("=")
            env[k] = v
        self.man["env"] = {k: v for k, v in env.items() if k.upper().startswith("I76")}
        self.man["boot"] = "menu" if self.menu_boot else ("nomission" if self.a.nomission else "mission")
        logp = os.path.join(G, "mciproxy.log")
        self.log_lines_before = sum(1 for _ in open(logp, errors="replace")) if os.path.exists(logp) else 0
        self.tel = tellib.TelemetryRecorder(os.path.join(self.out, "telemetry.csv"), keep=self.TEL_KEEP)
        self.tel.start()
        wake_display()
        exe = os.path.join(G, self.a.exe)
        self.man["exe"] = {"path": exe, "md5": md5_file(exe)}
        if self.a.census and self.a.attach_at_spawn:
            # frida.spawn: CreateProcess(CREATE_SUSPENDED); the loader runs (static DLLs incl. STRLKUP.DLL and its DllMain
            # patches) while Frida injects its agent; WinMain has not started. attach_census() hooks, then resume_spawned().
            import frida
            pid = frida.spawn(exe, argv=[exe, "-glide"], envp=env, cwd=G)
            self.p = SpawnedProcess(pid)
            self.spawned = True
            self.t_launch = time.perf_counter()
            self.man["launch"] = {"method": "frida.spawn (suspended)", "frida": frida.__version__}
        else:
            self.p = subprocess.Popen([exe, "-glide"], cwd=G, env=env)
            self.spawned = False
            self.t_launch = time.perf_counter()
            self.man["launch"] = {"method": "subprocess.Popen"}
        self.man["pid"] = self.p.pid
        self.man["launch_wall"] = time.time()
        log("launched %s pid %d (%s, %s)" % (exe, self.p.pid, self.a.profile, self.man["launch"]["method"]))
        for _ in range(40):
            time.sleep(0.1)
            try:
                self.mem = Mem(self.p.pid)
                break
            except OSError:
                pass
        if self.mem is None:
            raise RuntimeError("could not open the game process")

    def resume_spawned(self):
        """Let the frida-spawned (suspended) game run; records how long it sat and the frame counter / game state at resume."""
        import frida
        if not getattr(self, "spawned", False) or self.man.get("resumed"):
            return
        self.man["resumed"] = {"t_after_spawn": round(time.perf_counter() - self.t_launch, 2), "frame": self.mem.frame(),
                               "game_state": self.mem.u32(GAME_STATE), "entity_present": self.mem.entity() is not None}
        frida.resume(self.p.pid)
        self.t_launch = time.perf_counter()          # boot timings below count from the first instruction, as with Popen
        self.man["launch_wall"] = time.time()
        log("resumed pid %d after %.2f s suspended (frame %s, game state %s)" % (
            self.p.pid, self.man["resumed"]["t_after_spawn"], self.man["resumed"]["frame"], self.man["resumed"]["game_state"]))

    def attach_census(self):
        """Hook the batch as early as possible (right after launch, before the mission loads) so mission-load code is
        seen as init_only rather than never. Returns False when Frida could not attach or every hook failed."""
        import frida
        import censuslib
        batch = json.load(open(self.a.census, encoding="utf-8"))
        funcs = batch["functions"]
        last = None
        for _ in range(30):
            if self.p.poll() is not None:
                raise RuntimeError("game exited before Frida could attach (code %s)" % self.p.returncode)
            try:
                self.session = frida.attach(self.p.pid)
                break
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(0.5)
        if self.session is None:
            self.fail("frida.attach failed: %r" % (last,))
            return False
        mode = "spawn" if self.a.attach_at_spawn else ("entity" if self.a.attach_after_entity else "launch")
        self.man["census"] = {"batch": self.a.census, "batch_id": batch.get("batch"), "frida": frida.__version__,
                              "attach_mode": mode, "pass": {"spawn": "early", "entity": "entity", "launch": "launch"}[mode],
                              "attach_t_after_launch": round(time.perf_counter() - self.t_launch, 2),
                              "attach_after_entity": bool(self.a.attach_after_entity), "attach_at_spawn": bool(self.a.attach_at_spawn),
                              "attach_wall": time.strftime("%Y-%m-%dT%H:%M:%S"), "attach_game_state": self.mem.u32(GAME_STATE)}
        self.census = censuslib.FrameCensus(self.session, self.out, snapshot_ms=self.a.snapshot_ms, cap=self.a.cap)
        targets = [{"addr": int(f["addr"], 16), "name": f["name"], "hookable": f.get("hookable", "yes"), "source": "batch " + str(batch.get("batch"))} for f in funcs]
        self.census.check_prologues(targets, self.mem)
        skipped = [t for t in targets if t["hook"] != "ok"]
        for t in skipped:
            log("hook SKIPPED 0x%x %s: %s" % (t["addr"], t["name"], t["hook"]))
        self.census.setup(targets)
        n = self.census.attach(self.a.hook_batch)
        self.man["census"]["hooks_attached"] = n
        self.man["census"]["hooks_skipped"] = len(skipped)
        self.man["census"]["hooks_done_t_after_launch"] = round(time.perf_counter() - self.t_launch, 2)
        self.man["census"]["attach_frame"] = self.mem.frame()
        self.man["census"]["attach_entity_present"] = self.mem.entity() is not None
        self.census.start()
        self.man["census"]["start_wall_ms"] = int(time.time() * 1000)    # census\snapshots.csv t_ms is Date.now() (epoch ms)
        if n == 0:
            self.fail("no hook attached")
            return False
        return True

    def navigate_melee(self):
        """fr_probe.py --nomission: the capture 012 route through 002-nav\\ui.py (6 x Esc through the intro, MELEE, AUTO MELEE,
        INSTANT MELEE, [AI drivers to 0 when --ai 0], start). ui.py finds the window by the i76_pristine* process name."""
        UI = os.path.join(MAP, "captures", "002-nav", "ui.py")

        def ui(*xs):
            return subprocess.run([sys.executable, UI] + [str(x) for x in xs], capture_output=True, text=True).stdout
        for _ in range(6):
            ui("key", 27, "sleep", 2)
        seq = ["uclick", 445, 312, "sleep", 2, "uclick", 490, 350, "sleep", 2, "uclick", 530, 379, "sleep", 4]
        if self.a.ai == 0:
            seq += ["uclick", 187, 295, "sleep", 1]
        out = ui(*(seq + ["uclick", 298, 461, "sleep", 18]))
        self.man["navigated_melee"] = {"t_after_launch": round(time.perf_counter() - self.t_launch, 2), "ai": self.a.ai, "ui_out": out.strip()[-200:]}
        log("melee navigation done (ai=%d)" % self.a.ai)

    def wait_for_menu(self):
        """Boot kind "menu": no mission. The intro movies play first (Esc taps skip them, as the Melee route's 6 x Esc do);
        the shell main menu is up when the game state 0x4c2164 reads 6 (mission.md: shell_RunAndGetChoice sets it just
        before ShellMain). The scenario clock starts then; --secs counts from launch, so the menu sits for the rest."""
        t_wait = time.perf_counter()
        next_focus, next_esc = 0.0, MENU_ESC_FROM_S
        states = []
        state = None
        while time.perf_counter() - self.t_launch < max(self.a.secs - 5.0, 20.0):
            time.sleep(0.25)
            if self.p.poll() is not None:
                raise RuntimeError("game exited during the menu boot (code %s)" % self.p.returncode)
            if self.census and self.session is not None and self.session.is_detached:
                raise RuntimeError("Frida session detached during the menu boot (crash?)")
            t_el = time.perf_counter() - self.t_launch
            s = self.mem.u32(GAME_STATE)
            if s != state:
                state = s
                states.append({"t": round(t_el, 2), "game_state": s, "frame": self.mem.frame()})
            if s == 6:
                break
            if t_el >= next_focus:
                self.man.setdefault("focus", []).append(focus_game(self.p.pid))
                next_focus = t_el + 6.0
            if t_el >= next_esc:
                key_tap("ESC")
                self.man.setdefault("esc_sent", []).append(round(t_el, 2))
                next_esc = t_el + MENU_ESC_EVERY_S
        self.man["game_states"] = states
        self.man["menu_t"] = round(time.perf_counter() - self.t_launch, 2)
        self.man["menu_up"] = self.mem.u32(GAME_STATE) == 6
        if not self.man["menu_up"]:
            self.man["warnings"].append("game state never read 6 (shell) within %.0f s; last %s" % (time.perf_counter() - t_wait, state))
        time.sleep(1.0)
        self.man["focus_at_start"] = focus_game(self.p.pid)
        self.t0 = time.perf_counter()
        self.man["start_wall_ms"] = int(time.time() * 1000)
        self.a.secs = max(self.a.secs - (time.perf_counter() - self.t_launch), 5.0)     # the remainder of --secs from launch
        self.man["menu_sit_s"] = round(self.a.secs, 1)
        self.man["start_frame"] = self.mem.frame()
        self.man["start_state"] = self.mem.state()
        self.man["start_state"]["game_state"] = self.mem.u32(GAME_STATE)
        self.act("scenario-start", "menu up after %.1fs (game state %s), sitting %.0fs" % (self.man["menu_t"], self.man["start_state"]["game_state"], self.a.secs))

    def wait_for_mission(self):
        """fr_probe.py's boot wait: focus passes, Esc off the pre-start screen, player entity, frame counter moving."""
        ent = None
        for it in range(240):                     # 60 s
            time.sleep(0.25)
            if it % 8 == 4:
                self.man.setdefault("focus", []).append(focus_game(self.p.pid))
            if self.p.poll() is not None:
                raise RuntimeError("game exited during boot (code %s)" % self.p.returncode)
            if self.census and self.session is not None and self.session.is_detached:
                raise RuntimeError("Frida session detached during boot (crash?)")
            ent = self.mem.entity()
            if ent:
                break
            if self.a.nomission:
                # fr_probe navigates at its iteration 128; measured here, the route works when it starts ~55 s after launch
                # (the intro cutscene is up, Esc x6 drops to the main menu in fake-fullscreen 3440x1440 where ui.py clicks
                # 1:1; a run that clicked at 93 s found the shell windowed and the clicks missed). One retry after 45 s.
                nav = self.man.get("navigated_melee_attempts", 0)
                t_el = time.perf_counter() - self.t_launch
                if (nav == 0 and t_el >= 55) or (nav == 1 and t_el >= self.man["navigated_melee"]["t_after_launch"] + 45):
                    self.man["navigated_melee_attempts"] = nav + 1
                    self.navigate_melee()
                continue
            if self.mem.play_mode() == 0x20:
                focus_game(self.p.pid)
                key_tap("ESC")
                self.man.setdefault("esc_sent", []).append(round(time.perf_counter() - self.t_launch, 2))
        else:
            raise RuntimeError("no player entity after 60 s")
        self.man["entity"] = "0x%x" % ent
        self.man["entity_t"] = round(time.perf_counter() - self.t_launch, 2)
        if self.a.census and self.a.attach_after_entity:
            # hook only now: every run then sees the same post-load state (init_only vs never is consistent across runs)
            if not self.attach_census():
                raise RuntimeError("census could not be attached after the entity appeared (see manifest errors)")
            self.man["census"]["attach_entity_t"] = self.man["entity_t"]
        for _ in range(120):                      # frame counter moving
            f1 = self.mem.frame(); time.sleep(0.25); f2 = self.mem.frame()
            if f1 is not None and f2 is not None and f2 > f1:
                break
            if self.mem.play_mode() == 0x20:
                focus_game(self.p.pid)
                key_tap("ESC")
                self.man.setdefault("esc_sent", []).append(round(time.perf_counter() - self.t_launch, 2))
            if self.p.poll() is not None:
                raise RuntimeError("game exited before the loop started (code %s)" % self.p.returncode)
        else:
            raise RuntimeError("gameplay loop never started (frame counter frozen)")
        self.man["loop_t"] = round(time.perf_counter() - self.t_launch, 2)
        self.man["loop_frame"] = self.mem.frame()
        # the mission's scripted opening (camera callback 0x48e190) swallows key presses: wait for the hand-over
        tw = time.perf_counter()
        while self.mem.camera_scripted() and time.perf_counter() - tw < 60 and self.p.poll() is None:
            time.sleep(0.25)
        self.man["handover_wait_s"] = round(time.perf_counter() - tw, 2)
        self.man["camera_scripted_at_start"] = self.mem.camera_scripted()
        time.sleep(1.0)
        self.man["focus_at_start"] = focus_game(self.p.pid)
        self.t0 = time.perf_counter()
        self.man["start_wall_ms"] = int(time.time() * 1000)
        self.man["start_frame"] = self.mem.frame()
        self.man["start_state"] = self.mem.state()
        self.act("scenario-start", "handover wait %.1fs" % self.man["handover_wait_s"])

    # ------------------------------------------------------------------ steps
    def remaining(self):
        return self.a.secs - (time.perf_counter() - self.t0)

    def sleep_checked(self, s):
        end = time.perf_counter() + s
        while time.perf_counter() < end:
            time.sleep(min(0.25, max(0.0, end - time.perf_counter())))
            if self.p.poll() is not None:
                raise RuntimeError("game exited mid-scenario (code %s)" % self.p.returncode)
            if self.session is not None and self.session.is_detached:
                raise RuntimeError("Frida session detached mid-scenario (crash?)")

    def hold(self, keys, s):
        """Hold one key or a chord (list) for s seconds (-1 = until the duration ends)."""
        keys = [keys] if isinstance(keys, str) else list(keys)
        if s < 0:
            s = max(self.remaining(), 0)
        s = min(s, max(self.remaining(), 0))
        focus_game(self.p.pid)
        for k in keys:
            key_down(k); self.held.add(k)
        self.act("key-down", "+".join(keys))
        try:
            self.sleep_checked(s)
        finally:
            for k in keys:
                key_up(k); self.held.discard(k)
            self.act("key-up", "%s after %.1fs" % ("+".join(keys), s))

    def brake_to_stop(self, max_s):
        focus_game(self.p.pid)
        key_down("S"); self.held.add("S")
        self.act("key-down", "S (brake until speed < %.1f)" % STOP_SPEED)
        t = time.perf_counter()
        try:
            while time.perf_counter() - t < max_s and self.remaining() > 0:
                self.sleep_checked(0.25)
                v = self.mem.speed()
                if v is not None and abs(v) < STOP_SPEED:
                    break
        finally:
            key_up("S"); self.held.discard("S")
            self.act("key-up", "S after %.1fs, speed %s" % (time.perf_counter() - t, self.mem.speed()))

    # ------------------------------------------------------------------ take-damage ops: closed-loop steer, pokes
    @property
    def writer(self):
        """i76trainer.Game over the running sandbox game (PROCESS_VM_WRITE): the trainer's own write path, opened once."""
        if getattr(self, "_writer", None) is None:
            trainer_path()
            import i76trainer
            self._writer = i76trainer.Game(self.p.pid)
        return self._writer

    def poke(self, st):
        """Write one component / side value to pct% of its max through the trainer (read back; HUD copy follows)."""
        import struct as _struct
        what = st["what"]
        if what not in POKE_TARGETS:
            raise ValueError("poke: unknown target %r (one of %s)" % (what, sorted(POKE_TARGETS)))
        kind, off_val, off_max = POKE_TARGETS[what]
        ent = self.mem.entity()
        if kind == "side":
            side = int(st.get("side", 0))
            base = ent
            a_val, a_max = base + off_val + 4 * side, base + off_max + 4 * side
            hud = base + HUD_COPY[what] + 4 * side
        else:
            base = self.mem.wheel(int(st.get("slot", 0))) if kind == "wheel" else {
                "engine": self.mem.engine(), "susp": self.mem.u32(self.mem.u32(ent + 0x3c8) + 0x70) if self.mem.u32(ent + 0x3c8) else None,
                "brake": self.mem.u32(self.mem.u32(ent + 0x3cc) + 0x70) if self.mem.u32(ent + 0x3cc) else None}[kind]
            if not base:
                raise RuntimeError("poke %s: component not present" % what)
            a_val, a_max = base + off_val, base + off_max
            hud = None
        mx = _struct.unpack("<i", self.mem.rd(a_max, 4))[0]
        old = _struct.unpack("<i", self.mem.rd(a_val, 4))[0]
        new = int(round(mx * float(st["pct"]) / 100.0))
        g = self.writer
        ok = g.wr(a_val, _struct.pack("<i", new))
        if hud:
            ok = g.wr(hud, _struct.pack("<i", new)) and ok
        back = _struct.unpack("<i", self.mem.rd(a_val, 4))[0]
        rec = {"what": what, "side": st.get("side"), "slot": st.get("slot"), "pct": st["pct"], "addr": "0x%x" % a_val, "max": mx,
               "old": old, "new": new, "read_back": back, "ok": bool(ok and back == new), "frame": self.mem.frame(),
               "sim_time": self.mem.f32(TIME_ADDR), "t_scn": round(time.perf_counter() - self.t0, 3)}
        self.man.setdefault("pokes", []).append(rec)
        self.act("poke", "%s%s -> %d%% : %d/%d -> %d (read back %d) %s" % (
            what, (" side %s" % st["side"]) if "side" in st else ((" slot %s" % st["slot"]) if "slot" in st else ""),
            st["pct"], old, mx, new, back, "ok" if rec["ok"] else "FAILED"))
        if not rec["ok"]:
            self.fail("poke %s did not read back (%s)" % (what, rec))
        self.sleep_checked(st.get("after", 0.3))

    def _steer_loop(self, max_s, error_fn, done_fn, label):
        """Hold W; every STEER_PERIOD read the heading error (deg, + = target is anticlockwise in the atan2(x, z) frame),
        press A or D (sign learned on the fly: A is assumed to increase the heading, flipped once if the error grows for
        1 s) until done_fn() or max_s. Returns the loop's summary dict."""
        focus_game(self.p.pid)
        key_down("W"); self.held.add("W")
        self.act("key-down", "W (%s)" % label)
        t = time.perf_counter()
        # D increases the heading atan2(fwd.x, fwd.z): the melee runs' W+D holds read steer -0.94 and steer < 0 frames turned
        # the heading +0.083 rad/frame (x is to the right when facing +z). sign = +1 means exactly that; the flip below
        # is a safety net for a car that is sliding or pushed, not the expected path (the first take-damage run, with the
        # sign the other way round, flipped at 1 s and still arrived).
        sign = +1
        pressed = None
        hist = []
        try:
            while time.perf_counter() - t < max_s and self.remaining() > 0:
                self.sleep_checked(STEER_PERIOD)
                if done_fn():
                    break
                err = error_fn()
                if err is None:
                    continue
                v = self.mem.speed() or 0.0
                hist.append((time.perf_counter(), abs(err)))
                hist = [h for h in hist if h[0] > time.perf_counter() - 2.0]
                if len(hist) >= 16 and hist[-1][1] > hist[0][1] + 40 and pressed is not None and v > 5.0:
                    sign = -sign          # the error grew by 40 deg over two seconds of steering at speed: wrong side
                    hist = []
                    self.act("steer", "sign flipped (error grew to %.0f deg)" % err)
                want = None
                if abs(err) > STEER_DEADBAND_DEG:
                    want = "D" if (err > 0) == (sign > 0) else "A"
                if want != pressed:
                    if pressed:
                        key_up(pressed); self.held.discard(pressed)
                    if want:
                        key_down(want); self.held.add(want)
                    pressed = want
        finally:
            if pressed:
                key_up(pressed); self.held.discard(pressed)
        return {"elapsed": round(time.perf_counter() - t, 2), "sign": sign, "done": bool(done_fn())}

    def drive_to(self, st):
        tx, tz = float(st["x"]), float(st["z"])
        radius = float(st.get("radius", 8.0))

        def err():
            p, h = self.mem.pos(), self.mem.heading()
            if p is None or h is None:
                return None
            import math
            b = math.atan2(tx - p[0], tz - p[2])
            return math.degrees((b - h + math.pi) % (2 * math.pi) - math.pi)

        def dist():
            p = self.mem.pos()
            import math
            return math.hypot(tx - p[0], tz - p[2]) if p else None

        def done():
            d = dist()
            return d is not None and d < radius
        d0 = dist()
        self.act("drive_to", "(%.0f, %.0f) from %.0f m, bearing error %.0f deg" % (tx, tz, d0 or -1, err() or 0))
        res = self._steer_loop(float(st.get("max_s", 20)), err, done, "drive_to")
        res.update({"target": [tx, tz], "radius": radius, "dist_start": d0, "dist_end": dist(), "speed_end": self.mem.speed()})
        self.man.setdefault("drive_to", []).append(res)
        self.act("drive_to-end", "dist %.1f m after %.1fs (%s), speed %.1f" % (res["dist_end"] or -1, res["elapsed"], "arrived" if res["done"] else "timeout", res["speed_end"] or 0))
        ram = float(st.get("ram_s", 0))
        if ram > 0:
            try:
                self.sleep_checked(min(ram, max(self.remaining(), 0)))
            finally:
                key_up("W"); self.held.discard("W")
                self.act("key-up", "W after ramming %.1fs, speed %s" % (ram, self.mem.speed()))
        else:
            key_up("W"); self.held.discard("W")
            self.act("key-up", "W (drive_to)")

    def turn_to(self, st):
        import math
        target = math.radians(float(st["heading_deg"]))
        tol = float(st.get("tol_deg", 10.0))

        def err():
            h = self.mem.heading()
            return None if h is None else math.degrees((target - h + math.pi) % (2 * math.pi) - math.pi)

        def done():
            e = err()
            return e is not None and abs(e) < tol
        self.act("turn_to", "%.0f deg from %.0f" % (math.degrees(target), math.degrees(self.mem.heading() or 0)))
        res = self._steer_loop(float(st.get("max_s", 10)), err, done, "turn_to")
        key_up("W"); self.held.discard("W")
        res.update({"heading_end": math.degrees(self.mem.heading() or 0), "error_end": err()})
        self.man.setdefault("turn_to", []).append(res)
        self.act("turn_to-end", "heading %.0f (error %.0f) after %.1fs" % (res["heading_end"], res["error_end"] or 0, res["elapsed"]))

    # ------------------------------------------------------------------ jump ops: fr_probe --place / --drop write paths
    def jump_launch(self, st, lift_only=False):
        """Lift the player object dy m and set its velocity's y to vy (x/z kept): the car leaves a ramp at its current heading
        and speed (fr_probe --place writes +0xbc the same way; repeated 6 x 12 ms because a single write rarely sticks)."""
        vy = 0.0 if lift_only else float(st.get("vy", 12.0))
        dy = float(st.get("m", 20.0)) if lift_only else float(st.get("dy", 1.5))
        obj, ent = self.mem.player_object(), self.mem.entity()
        if not obj or not ent:
            raise RuntimeError("launch: no player object")
        pos = self.mem.pos()
        vel = struct.unpack("<3f", self.mem.rd(ent + 0xbc, 12))
        g = self.writer
        f0 = self.mem.frame()
        ok = True
        for _ in range(6):
            ok = g.wr(obj + 0x48, struct.pack("<d", pos[1] + dy)) and ok
            ok = g.wr(ent + 0xbc, struct.pack("<3f", vel[0], vy, vel[2])) and ok
            time.sleep(0.012)
        y_back = self.mem.f64(obj + 0x48)
        v_back = struct.unpack("<3f", self.mem.rd(ent + 0xbc, 12))
        t = time.perf_counter()
        air_frame = None
        while time.perf_counter() - t < 1.5:                 # the flag should come up within a step or two
            if self.mem.airborne():
                air_frame = self.mem.frame()
                break
            time.sleep(0.02)
        rec = {"op": "lift" if lift_only else "launch", "dy": dy, "vy": vy, "pos_before": list(pos), "vel_before": list(vel),
               "y_read_back": y_back, "vel_read_back": list(v_back), "write_ok": bool(ok), "frame": f0, "airborne_frame": air_frame,
               "sim_time": self.mem.f32(TIME_ADDR), "t_scn": round(time.perf_counter() - self.t0, 3)}
        self.man.setdefault("launches", []).append(rec)
        self.act(rec["op"], "y %.2f -> %.2f (read back %.2f), vel (%.1f, %.1f, %.1f) -> y %.1f (read back %.1f); airborne at frame %s" % (
            pos[1], pos[1] + dy, y_back or -1, vel[0], vel[1], vel[2], vy, v_back[1], air_frame))
        if air_frame is None:
            self.man["warnings"].append("%s at frame %s: airborne flag did not come up within 1.5 s" % (rec["op"], f0))
        self.sleep_checked(float(st.get("after", 0.0)))

    def run_step(self, st):
        op = st["op"]
        if op in ("poke", "drive_to", "turn_to"):
            {"poke": self.poke, "drive_to": self.drive_to, "turn_to": self.turn_to}[op](st)
        elif op == "launch":
            self.jump_launch(st)
        elif op == "lift":
            self.jump_launch(st, lift_only=True)
        elif op == "wait":
            self.act("wait", st["s"]); self.sleep_checked(min(st["s"], max(self.remaining(), 0)))
        elif op == "tap":
            focus_game(self.p.pid); key_tap(st["key"], st.get("hold", 0.08)); self.act("tap", st["key"])
            self.sleep_checked(st.get("after", 0.3))
        elif op == "hold":
            self.hold(st.get("keys", st.get("key")), st["s"])
        elif op == "brake_to_stop":
            self.brake_to_stop(st.get("max_s", 10))
        elif op == "start_engine":                 # tap I (start_engine) only when the engine flag (ent+0x454 bit 0) is off
            fl = self.mem.flags() or 0
            if not fl & 1:
                focus_game(self.p.pid); key_tap("I"); self.act("tap", "I (engine was off, flags 0x%x)" % fl)
                self.sleep_checked(st.get("after", 1.0))
            else:
                self.act("start_engine", "already on (flags 0x%x)" % fl)
        elif op == "check":
            s = self.mem.state()
            if "speed_gt" in st:
                self.check("speed_gt %s" % st["speed_gt"], (s["speed"] or 0) > st["speed_gt"], "speed %s" % s["speed"])
            if "speed_lt" in st:
                self.check("speed_lt %s" % st["speed_lt"], (s["speed"] or 0) < st["speed_lt"], "speed %s" % s["speed"])
            if "gear_in" in st:
                self.check("gear_in %s" % st["gear_in"], s["gear"] in st["gear_in"], "gear %s" % s["gear"])
            if st.get("engine_on"):
                self.check("engine_on", bool((s["flags"] or 0) & 1), "flags 0x%x" % (s["flags"] or 0))
            if st.get("player_present"):
                self.check("player_present", s["entity"] is not None, "entity %s" % s["entity"])
            if "airborne" in st:
                self.check("airborne %s" % st["airborne"], bool((s["flags"] or 0) & 4) == bool(st["airborne"]), "flags 0x%x" % (s["flags"] or 0))
            if "airborne_frames_gt" in st:
                n = self.airborne_frames()
                self.check("airborne_frames_gt %s" % st["airborne_frames_gt"], n > st["airborne_frames_gt"], "%d airborne frames so far, spells %s" % (
                    n, json.dumps(self.man.get("airborne_spells"))))
            if "cam_mode_in" in st:
                m = self.mem.cam_mode()
                self.check("cam_mode_in %s" % st["cam_mode_in"], m in st["cam_mode_in"], "camera_mode %s cb 0x%x" % (m, self.mem.cam_cb() or 0))
            if "radar_locked" in st or "radar_range_in" in st:
                r = self.mem.radar()
                if "radar_locked" in st:
                    self.check("radar_locked %s" % st["radar_locked"], bool(r and r["locked"]) == bool(st["radar_locked"]), "radar %s" % r)
                if "radar_range_in" in st:
                    self.check("radar_range_in %s" % st["radar_range_in"], bool(r) and r["range"] in st["radar_range_in"], "radar %s" % r)
        else:
            raise ValueError("unknown step op %r" % op)

    def run_steps(self):
        self.start_watch()
        for st in self.sc["steps"]:
            if self.remaining() <= 0:
                self.man["warnings"].append("duration reached before step %s" % json.dumps(st))
                break
            self.run_step(st)
        if self.remaining() > 0:
            self.act("idle", "%.1fs to the end" % self.remaining())
            self.sleep_checked(self.remaining())
        self.stop_watch()
        self.man["end_frame"] = self.mem.frame()
        self.man["end_state"] = self.mem.state()
        self.man["end_state"]["game_state"] = self.mem.u32(GAME_STATE)
        self.man["end_wall_ms"] = int(time.time() * 1000)
        self.act("scenario-end", "")

    # ------------------------------------------------------------------ teardown
    def finish_census(self, functions):
        if not self.census:
            return
        try:
            if self.session is not None and not self.session.is_detached:
                self.census.stop()
                self.census.dump()
                self.man["census"]["detach"] = self.census.detach()
            else:
                self.man["census"]["detached_early"] = True
            window = (self.man.get("start_frame"), self.man.get("end_frame"))
            self.man["census"]["attest"] = self.census.write(self.id, window, functions)
            self.census.unload()
            log("census: %d/%d hooks attached, fired_total %s, nonzero %d" % (
                self.man["census"]["attest"]["hooks_attached"], self.man["census"]["attest"]["hooks_requested"],
                (self.man["census"]["attest"].get("stop") or {}).get("fired_total"), self.man["census"]["attest"]["hooks_fired_nonzero"]))
        except Exception as e:  # noqa: BLE001
            self.fail("census finish: %r" % (e,))
        try:
            if self.session is not None and not self.session.is_detached:
                self.session.detach()
        except Exception:  # noqa: BLE001
            pass

    def quit_game(self):
        """WM_CLOSE to the main window (ui_i76.py quit_game), kill after 10 s."""
        import ctypes
        if self.p is None or self.p.poll() is not None:
            return
        for k in list(self.held):
            key_up(k)
        u = ctypes.windll.user32
        hwnds = []
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(h, _):
            pid = ctypes.c_uint()
            u.GetWindowThreadProcessId(ctypes.c_void_p(h), ctypes.byref(pid))
            if pid.value == self.p.pid and u.IsWindowVisible(ctypes.c_void_p(h)):
                hwnds.append(h)
            return True
        u.EnumWindows(EnumProc(cb), 0)
        for h in hwnds:
            u.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
        t = time.perf_counter()
        while self.p.poll() is None and time.perf_counter() - t < 10:
            time.sleep(0.25)
        if self.p.poll() is None:
            self.p.kill(); self.p.wait(10)
            self.man["quit"] = "WM_CLOSE ignored for 10 s, killed"
        else:
            self.man["quit"] = "clean exit %.1fs after WM_CLOSE (code %s)" % (time.perf_counter() - t, self.p.returncode)
        log("quit: " + self.man["quit"])

    def collect_logs(self):
        logp = os.path.join(G, "mciproxy.log")
        if os.path.exists(logp):
            lines = open(logp, errors="replace").read().splitlines()
            with open(os.path.join(self.out, "mciproxy.log"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines[self.log_lines_before:]) + "\n")
            self.man["proxy_log_switches"] = sorted(set(l.strip() for l in lines[self.log_lines_before:] if any(
                w in l for w in ("hires", "engine-dt", "mission-launch", "fixed-step", "framerate-fixes", "fps-cap", "telemetry", "UNEXPECTED"))))[:40]
        if self.tel:
            self.man["telemetry"] = self.tel.stop()
            ev = self.man["telemetry"].get("events_csv")
            if ev and os.path.exists(ev):
                os.replace(ev, os.path.join(self.out, "events.csv"))
                self.man["telemetry"]["events_csv"] = os.path.join(self.out, "events.csv")

    def write_manifest(self):
        self.man["time_end"] = datetime.datetime.now().isoformat(timespec="seconds")
        self.man["ok"] = not self.man["errors"]
        p = os.path.join(self.out, "manifest.json")
        tmp = p + ".tmp"
        json.dump(self.man, open(tmp, "w", encoding="utf-8"), indent=1, default=str)
        os.replace(tmp, p)
        json.load(open(p, encoding="utf-8"))      # read back
        log("manifest written: %s" % p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id", help="scenario id (verify\\scenarios\\<id>.json): mission-idle | drive | fire-each")
    ap.add_argument("--census", help="batch JSON from census.py make-batches; hooks it with Frida for the whole run")
    ap.add_argument("--secs", type=float, default=None, help="recording duration from the hand-over (default: the scenario's duration_s)")
    ap.add_argument("--profile", default="stock20", choices=sorted(PROFILES), help="proxy switches (default stock20: I76_FPS_CAP=20)")
    ap.add_argument("--mission", default="t01.msn")
    ap.add_argument("--snapshot-ms", type=int, default=1000)
    ap.add_argument("--cap", type=int, default=32768, help="per-function series length in frames")
    ap.add_argument("--hook-batch", type=int, default=50, help="hooks per Interceptor transaction")
    ap.add_argument("--attach-after-entity", action="store_true", help="hook the census only once the player entity exists (post-load state in every run; load-time code reads never)")
    ap.add_argument("--attach-at-spawn", action="store_true", help="start the game with frida.spawn (suspended), hook the census before WinMain's first instruction, then resume (pass `early`)")
    ap.add_argument("--exe", default=EXE, help="exe in the sandbox game dir (default i76.exe; i76_pristine_fix.exe for --nomission)")
    ap.add_argument("--nomission", action="store_true", help="no I76_MISSION redirect: plain boot and the Melee route (fr_probe --nomission); no scripted end")
    ap.add_argument("--ai", type=int, default=1, help="--nomission: 0 clicks the AI drivers to 0; 1 keeps the form's one AI car")
    ap.add_argument("--env", action="append", help="extra proxy switch KEY=VALUE for the game's environment (repeatable, e.g. --env I76_FAR_CLIP=1800)")
    a = ap.parse_args()
    if a.attach_after_entity and a.attach_at_spawn:
        raise SystemExit("--attach-after-entity and --attach-at-spawn exclude each other")
    ensure_dirs()
    scf = os.path.join(SCENARIOS, a.id + ".json")
    if not os.path.exists(scf):
        raise SystemExit("no scenario %s" % scf)
    sc = json.load(open(scf, encoding="utf-8"))
    sc["_file"] = scf
    if a.secs is None:
        a.secs = float(sc.get("duration_s", 90))
    if sc.get("boot") == "menu" and (a.attach_after_entity or a.nomission):
        raise SystemExit("a menu-boot scenario has no entity and no Melee route: drop --attach-after-entity / --nomission")
    functions = Functions()
    r = Runner(a, sc)
    r.preflight()
    code = 0
    try:
        r.install_proxy()
        r.launch()
        if a.census and not a.attach_after_entity:
            ok = r.attach_census()
            if not ok and a.attach_at_spawn:
                r.resume_spawned()                   # never leave a suspended game behind
            if not ok:
                raise RuntimeError("census could not be attached; stopping (see manifest errors)")
        r.resume_spawned()
        if r.menu_boot:
            r.wait_for_menu()
            r.check("menu_up", r.man.get("menu_up"), "game state %s after %ss" % (r.man["start_state"].get("game_state"), r.man.get("menu_t")))
        else:
            r.wait_for_mission()
            r.check("player_present", r.mem.entity() is not None, "entity %s" % r.man.get("entity"))
            r.check("frame_moving", (r.man.get("start_frame") or 0) > (r.man.get("loop_frame") or 0) - 1, "frame %s" % r.man.get("start_frame"))
        r.run_steps()
        if r.menu_boot:
            r.check("menu_still_up", r.man["end_state"].get("game_state") == 6, "game state %s at the end" % r.man["end_state"].get("game_state"))
    except Exception as e:  # noqa: BLE001
        r.fail("%s: %s" % (type(e).__name__, e))
        code = 1
        if r.mem and r.t0 and "end_frame" not in r.man:
            r.man["end_frame"] = r.mem.frame()
    finally:
        try:
            r.stop_watch()
        except Exception:  # noqa: BLE001
            pass
        try:
            r.resume_spawned()                       # a failure before resume must not leave a suspended process for quit_game
        except Exception:  # noqa: BLE001
            pass
        try:
            r.finish_census(functions)
        finally:
            try:
                r.quit_game()
            finally:
                time.sleep(1.0)
                r.restore_proxy()
                if os.path.exists(LOCK):
                    os.remove(LOCK)
                r.collect_logs()
                r.actions.close()
                r.write_manifest()
    print("%s: %s  frames %s..%s  telemetry %s  errors %s" % (
        r.id, r.out, r.man.get("start_frame"), r.man.get("end_frame"), (r.man.get("telemetry") or {}).get("frames"), r.man["errors"]))
    return code


if __name__ == "__main__":
    sys.exit(main())
