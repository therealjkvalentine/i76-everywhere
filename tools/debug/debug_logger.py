r"""debug_logger.py - the physics / memory logger of I76 Debug: start / stop / mark from the dashboard (Trainer tab and
the header pill), from two global hotkeys, or automatically per mission (--log-auto).

What it writes. The same files as the emulator logger I76MEM after lab emu\tools\memtrace\mem2csv.py, in the same
folder layout as an owner play session (owner_log.py collect), so every analysis tool reads both without a change:

    <log-dir>\<YYYYMMDD-HHMMSS>-<label>\           one folder per dashboard run
        s01\mem.phys.csv     one row per frame with the player present: mem2csv.py's LAB + EXTRA columns in the same order
                             (phase t sim_time sim_dt dt step_count x y z vx vy vz speed pitch_rate yaw_rate roll_rate rot1 rot4
                             rot6 rot7 rot8 flags throttle steer clearance rpm gear handbrake | frame tick verify phase_ms oflags
                             health health_max speedo step_ms surface gny ai_alive ai_total n_dist n_x n_z n_speed n_health
                             n_eflags cd_track cd_playing game_state rep), then three columns of our own (health_pct
                             tel_music_track mark). Every column but phase is numeric (owner_log.py drops a row with text).
        s01\mem.frames.csv   one row per telemetry frame (frame tick wall_ms sim_dt_ms dt_ms step_ms step_count skipped verify
                             phase_ms game_state), as mem2csv.py
        s01\mem.music.csv    every change of the music intent (frame tick phase cd_track cd_playing cd_loop cd_paused cd_ok
                             game_state), as mem2csv.py
        s01\marks.csv        one row per mark: n, label, frame, tick, sim_time, x, y, z, speed, flags, source
        s01\meta.json        what was logged: sources, exe md5, frame / row counts, frames missed, the reader check
        s02\ ...             the next start (a new mission under --log-auto)
        summary.md / .json   owner_log.py summary over the sNN folders, run after every stop when the lab tools are there

Where the numbers come from.
  * Per frame: the proxy's telemetry (tools\telemetry\i76tel.h, I76_TELEMETRY=1), one frame per datagram, taken by the
    proxy on the game thread at the top of the next frame (strlkproxy.c tel_frame): the END state of the frame whose
    simclock_frame_count it carries, with that frame's own sim_dt / dt - the same labelling as I76MEM 2026-10-15b, but
    read in-process and frame-consistent, so verify is 1 on every row. The entity flags (ent+0x454) carry 0x10000
    (Arcade Phys.), 0x200 (just landed), 0x8000 (wreck), 0x4 (airborne) exactly as I76MEM's eflags column.
  * At about 8 Hz (I76MEM reads its slow fields every 8 frames): a read-only ReadProcessMemory reader for the fields the
    telemetry does not carry - game state 0x4c2164, the player object's flags (obj+0x10), the AI team lists (alive /
    total, the nearest car's distance, x, z, speed, armour + chassis, entity flags) and the CD music intent (0x4ed800,
    0x52456c.., 0x524674), at I76MEM's addresses (lab emu\probe\i76addr.h, the Gold / AiO link). The reader's player
    object is compared with the telemetry's obj_addr on every read (meta.json 'reader_check'): a mismatch means the
    addresses do not fit the exe, and those columns are then left at their defaults.
  * tick = the host's millisecond clock when the datagram arrived (I76MEM: the guest's GetTickCount at the frame's start).
    wall_ms = its difference. Use the proxy's I76_FRAME_LOG for exact frame periods; this one includes the UDP hop.
  * step_ms = sim_dt / step_count (mem2csv.py's frames rule); under I76_FIXED_STEP that is the accumulator's mean step.
  * skipped = frames missing between two datagrams by the frame counter (UDP drops, or shared-memory polling).
  * phase = 'play' from the start, 'markNN' after mark NN (the I76DRV 'log MARK' rule: analysis tools split on it).

Nothing here writes to the game. The reader opens the process with PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION.
"""
import collections, ctypes, ctypes.wintypes as wt, datetime, hashlib, json, math, os, struct, subprocess, sys, threading, time

LAB = r"C:\Users\james\i76-uncap-lab"
MEMTRACE = os.path.join(LAB, "emu", "tools", "memtrace")
DEFAULT_ROOT = os.path.join(LAB, "captures", "trainer-log") if os.path.isdir(LAB) else \
    os.path.join(os.path.expanduser("~"), "Documents", "I76-logs")

# mem2csv.py LAB + EXTRA (lab emu\tools\memtrace\mem2csv.py) - same names, same order; ours appended after
LAB_COLS = ("phase t sim_time sim_dt dt step_count x y z vx vy vz speed pitch_rate yaw_rate roll_rate "
            "rot1 rot4 rot6 rot7 rot8 flags throttle steer clearance rpm gear handbrake").split()
EXTRA_COLS = ("frame tick verify phase_ms oflags health health_max speedo step_ms surface gny ai_alive ai_total n_dist n_x "
              "n_z n_speed n_health n_eflags cd_track cd_playing game_state rep").split()
OUR_COLS = "health_pct tel_music_track mark".split()
PHYS_COLS = LAB_COLS + EXTRA_COLS + OUR_COLS
FRAME_COLS = "frame tick wall_ms sim_dt_ms dt_ms step_ms step_count skipped verify phase_ms game_state".split()
MUSIC_COLS = "frame tick phase cd_track cd_playing cd_loop cd_paused cd_ok game_state".split()
MARK_COLS = "n label frame tick sim_time x y z speed flags source".split()

# I76MEM's addresses (lab emu\probe\i76addr.h; the Gold CD / GOG 2017 / AiO / our exe link)
A_GAME_STATE, A_PAUSE_BITS, A_PLAYER_ROOT = 0x004C2164, 0x004FE534, 0x0054A264
A_TEAM_LISTS, A_TEAM_COUNTS = 0x00507DA0, 0x0051F5D0
A_CD_TRACK, A_CD_PAUSED, A_CD_OK = 0x004ED800, 0x0052456C, 0x00524674       # paused +0, playing +4, loop +8
ENT_SPEED, ENT_ARMOUR, ENT_FLAGS = 0xAC, 0x138, 0x454
STEP_MAX = 20


def stepcount(sim_dt):
    return min(int(sim_dt * 20.0) + 1, STEP_MAX)      # simclock_StepperBegin 0x49cc20: floor(dt x 20) + 1, at most 20


def now_ms():
    return int(time.monotonic() * 1000.0)


# ---------------------------------------------------------------- read-only process reader (the slow fields)

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
k32.ReadProcessMemory.argtypes = (wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
k32.CloseHandle.argtypes = (wt.HANDLE,)
k32.GetExitCodeProcess.argtypes = (wt.HANDLE, ctypes.POINTER(wt.DWORD))
k32.QueryFullProcessImageNameW.argtypes = (wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD))
PROCESS_VM_READ, PROCESS_QUERY_LIMITED = 0x0010, 0x1000


def list_games():
    """[(pid, path)] of running i76*.exe (not the helpers i76wheel / i76haptics)"""
    arr = (wt.DWORD * 4096)(); got = wt.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    out = []
    for pid in arr[:got.value // 4]:
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(1024); n = wt.DWORD(1024)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        k32.CloseHandle(h)
        b = os.path.basename(buf.value).lower()
        if ok and b.startswith("i76") and b.endswith(".exe") and "wheel" not in b and "haptics" not in b:
            out.append((int(pid), buf.value))
    return out


class ProcReader:
    """read-only handle on one game process"""

    def __init__(self, pid, path=""):
        self.pid, self.path = pid, path
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED, False, pid)
        if not self.h:
            raise OSError("OpenProcess(%d) failed: %d" % (pid, ctypes.get_last_error()))

    def alive(self):
        c = wt.DWORD()
        return bool(k32.GetExitCodeProcess(self.h, ctypes.byref(c))) and c.value == 259

    def rd(self, addr, n):
        if not addr:
            return None
        buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)) or got.value != n:
            return None
        return buf.raw

    def u32(self, addr):
        b = self.rd(addr, 4)
        return struct.unpack("<I", b)[0] if b else 0

    def close(self):
        if self.h:
            k32.CloseHandle(self.h)
            self.h = None


SLOW_DEFAULT = {"game_state": "", "pause_bits": 0, "oflags": 0, "ai_alive": 0, "ai_total": 0, "n_dist": 0.0, "n_x": 0.0,
                "n_z": 0.0, "n_speed": 0.0, "n_health": 0, "n_eflags": 0, "cd_track": 0, "cd_playing": 0, "cd_loop": 0,
                "cd_paused": 0, "cd_ok": 0, "player_obj": 0}


def read_slow(r, px=None, pz=None):
    """one pass over I76MEM's slow fields (i76mem.c do_read: game state, cd, player oflags, AI scan + nearest).
    px / pz: the player's position (telemetry) for the nearest-car search; None = read it from the object."""
    s = dict(SLOW_DEFAULT)
    s["game_state"] = r.u32(A_GAME_STATE)
    s["pause_bits"] = r.u32(A_PAUSE_BITS)
    s["cd_track"] = struct.unpack("<i", struct.pack("<I", r.u32(A_CD_TRACK)))[0]
    cd = r.rd(A_CD_PAUSED, 12)
    if cd:
        s["cd_paused"], s["cd_playing"], s["cd_loop"] = int(cd[0] != 0), int(cd[4] != 0), int(cd[8] != 0)
    s["cd_ok"] = int(r.u32(A_CD_OK) != 0)
    rec = r.u32(A_PLAYER_ROOT)
    obj = r.u32(rec) if rec else 0
    ob = r.rd(obj + 0x10, 0x48) if obj else None
    if not ob or not (struct.unpack_from("<I", ob, 0)[0] & 0x10):
        return s
    s["player_obj"] = obj
    s["oflags"] = struct.unpack_from("<I", ob, 0)[0]
    if px is None:
        px, pz = struct.unpack_from("<d", ob, 0x30)[0], struct.unpack_from("<d", ob, 0x40)[0]
    cnt = r.rd(A_TEAM_COUNTS, 32)
    if not cnt:
        return s
    best, bd = None, 1e30
    for grp, n in enumerate(struct.unpack("<8i", cnt)):
        if n <= 0 or n > 64:
            continue
        lst = r.rd(A_TEAM_LISTS + 0x100 * grp, 4 * n)
        if not lst:
            continue
        for w in struct.unpack("<%dI" % n, lst):
            o = r.u32(w) if w else 0
            if not o or o == obj:
                continue
            ab = r.rd(o + 0x10, 0x64)
            if not ab:
                continue
            s["ai_total"] += 1
            if struct.unpack_from("<I", ab, 0)[0] & 0x20:
                continue
            s["ai_alive"] += 1
            x, z = struct.unpack_from("<d", ab, 0x30)[0], struct.unpack_from("<d", ab, 0x40)[0]
            d = (x - px) ** 2 + (z - pz) ** 2
            if d < bd:
                bd, best = d, (ab, x, z)
    if best:
        ab, x, z = best
        s["n_dist"], s["n_x"], s["n_z"] = math.sqrt(bd), x, z
        e = struct.unpack_from("<I", ab, 0x60)[0]                 # obj+0x70
        if e:
            sp = r.rd(e + ENT_SPEED, 4)
            h = r.rd(e + ENT_ARMOUR, 32)
            s["n_speed"] = struct.unpack("<f", sp)[0] if sp else 0.0
            s["n_health"] = sum(struct.unpack("<8i", h)) if h else 0
            s["n_eflags"] = r.u32(e + ENT_FLAGS)
    return s


class SlowReader(threading.Thread):
    """~8 Hz read-only pass over the slow fields, on its own thread so the telemetry thread never waits on it"""

    def __init__(self, logger, hz=8.0, pid=None, pid_hint=None):
        super().__init__(daemon=True, name="logger-reader")
        self.logger, self.period, self.pid, self.pid_hint = logger, 1.0 / hz, pid, pid_hint
        self.stop_ev = threading.Event()
        self.r = None
        self.state, self.note, self.reads, self.read_s = dict(SLOW_DEFAULT), "not attached", 0, 0.0
        self.next_attach = 0.0

    def choose(self):
        if self.pid:
            return [(p, path) for p, path in list_games() if p == self.pid][:1]
        games = list_games()
        hint = self.pid_hint() if self.pid_hint else None
        if hint:
            m = [x for x in games if x[0] == hint]
            if m:
                return m
        lab = [x for x in games if os.path.normcase(x[1]).startswith(os.path.normcase(LAB))]
        return lab[:1] if lab else games[:1]

    def run(self):
        while not self.stop_ev.is_set():
            t0 = time.perf_counter()
            if self.r is not None and not self.r.alive():
                self.r.close(); self.r = None; self.note = "game exited"
            if self.r is None and time.time() >= self.next_attach:
                self.next_attach = time.time() + 2.0
                c = self.choose()
                if c:
                    try:
                        self.r = ProcReader(*c[0])
                        self.note = "pid %d %s (read-only)" % c[0]
                    except OSError as e:
                        self.note = str(e)
            if self.r is not None and self.logger.wants_reader():
                fr = self.logger.last_frame
                px, pz = (fr["pos_0"], fr["pos_2"]) if fr and fr["player_present"] else (None, None)
                try:
                    s = read_slow(self.r, px, pz)
                except Exception as e:                       # a torn list between missions: keep the last values
                    self.note = "read error %r" % e
                else:
                    self.state = s
                    self.reads += 1
                    self.read_s += time.perf_counter() - t0
                    self.logger.on_slow(s)
            self.stop_ev.wait(max(0.0, self.period - (time.perf_counter() - t0)))
        if self.r:
            self.r.close()


# ---------------------------------------------------------------- global hotkeys

MODS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
VKS = {"scroll": 0x91, "scrolllock": 0x91, "pause": 0x13, "insert": 0x2D, "home": 0x24, "end": 0x23,
       **{"f%d" % i: 0x6F + i for i in range(1, 25)}, **{chr(c).lower(): c for c in range(0x41, 0x5B)}}


def parse_hotkey(text):
    """'shift+scroll' -> (mods, vk); ValueError on an unknown name"""
    mods, vk = 0x4000, None                                 # MOD_NOREPEAT
    for p in text.lower().replace(" ", "").split("+"):
        if p in MODS:
            mods |= MODS[p]
        elif p in VKS:
            vk = VKS[p]
        else:
            raise ValueError("unknown key %r in hotkey %r" % (p, text))
    if vk is None:
        raise ValueError("no key in hotkey %r" % text)
    return mods, vk


class Hotkeys(threading.Thread):
    """RegisterHotKey on its own thread with a message loop. keys: {name: (text, callback)}"""

    def __init__(self, keys):
        super().__init__(daemon=True, name="hotkeys")
        self.keys, self.tid, self.registered, self.errors = keys, None, {}, {}
        self.ready = threading.Event()

    def run(self):
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        u32.RegisterHotKey.argtypes = (wt.HWND, ctypes.c_int, wt.UINT, wt.UINT)
        self.tid = k32.GetCurrentThreadId()
        ids = {}
        for i, (name, (text, cb)) in enumerate(self.keys.items(), 1):
            try:
                mods, vk = parse_hotkey(text)
            except ValueError as e:
                self.errors[name] = str(e); continue
            if u32.RegisterHotKey(None, 0xB000 + i, mods, vk):
                ids[0xB000 + i] = cb; self.registered[name] = text
            else:
                self.errors[name] = "%s: RegisterHotKey failed (%d) - another program owns it" % (text, ctypes.get_last_error())
        self.ready.set()
        msg = wt.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312 and msg.wParam in ids:  # WM_HOTKEY
                try:
                    ids[msg.wParam]()
                except Exception as e:
                    print("hotkey:", e)
        for i in ids:
            u32.UnregisterHotKey(None, i)

    def stop(self):
        if self.tid:
            ctypes.windll.user32.PostThreadMessageW(self.tid, 0x0012, 0, 0)   # WM_QUIT


# ---------------------------------------------------------------- the logger

def file_md5(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None


class PhysLogger:
    """Fed every telemetry frame by Hub.on_datagram (outside the hub lock); start / stop / mark from any thread."""

    ABSENT_STOP_S = 3.0           # --log-auto: stop when the player has been gone this long (mission over, quit to menu)

    def __init__(self, root=DEFAULT_ROOT, auto=False, label="", summary=True, reader=True, reader_pid=None, pid_hint=None):
        self.root, self.auto, self.label, self.summary = root, auto, label, summary
        self.lock = threading.RLock()
        self.rundir, self.sess, self.sdir = None, 0, None
        self.files = {}
        self.recording, self.started_by = False, ""
        self.last_frame, self.last_frame_wall, self.present_at = None, 0.0, 0.0
        self.slow, self.slow_fresh = dict(SLOW_DEFAULT), False
        self.history = collections.deque(maxlen=20)                 # finished sessions (status)
        self.marks_total, self.note = 0, ""
        self.summary_state = ""
        self.reader = SlowReader(self, pid=reader_pid, pid_hint=pid_hint) if reader else None
        self.cost_s, self.cost_n = 0.0, 0
        self.exe_md5_cache = {}

    def start_threads(self):
        if self.reader:
            self.reader.start()

    def close(self):
        self.stop("dashboard closing")
        if self.reader:
            self.reader.stop_ev.set()

    # ---- control
    def start(self, label="", by="button"):
        with self.lock:
            if self.recording:
                return False, "already recording %s" % self.sdir
            if self.rundir is None:
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in (self.label or ""))[:40]
                self.rundir = os.path.join(self.root, stamp + ("-" + safe if safe else ""))
            self.sess += 1
            self.sdir = os.path.join(self.rundir, "s%02d" % self.sess)
            os.makedirs(self.sdir, exist_ok=True)
            op = lambda n: open(os.path.join(self.sdir, n), "w", newline="", buffering=1 << 16)  # noqa: E731
            self.files = {"phys": op("mem.phys.csv"), "frames": op("mem.frames.csv"), "music": op("mem.music.csv"),
                          "marks": op("marks.csv")}
            self.files["phys"].write(",".join(PHYS_COLS) + "\n")
            self.files["frames"].write(",".join(FRAME_COLS) + "\n")
            self.files["music"].write(",".join(MUSIC_COLS) + "\n")
            self.files["marks"].write(",".join(MARK_COLS) + "\n")
            self.recording, self.started_by = True, by
            self.phase, self.mark_n = "play", 0
            self.prev_frame = self.prev_tick = self.music_key = None
            self.c = collections.Counter()
            self.sim_dt_ms, self.steps = [], collections.Counter()
            self.t_start, self.t_start_wall = now_ms(), time.time()
            self.reader_check = collections.Counter()
            self.meta = {"session": "s%02d" % self.sess, "label": label or self.label, "started": datetime.datetime.now().isoformat(timespec="seconds"),
                         "started_by": by, "source": "I76 Debug telemetry logger (tools\\debug\\debug_logger.py)",
                         "columns": "mem2csv.py LAB + EXTRA, then " + " ".join(OUR_COLS)}
            self.last_flush = time.time()
            self.note = "recording %s" % self.sdir
            return True, self.note

    def stop(self, why="button"):
        with self.lock:
            if not self.recording:
                return False, "not recording"
            self.recording = False
            for f in self.files.values():
                f.close()
            self.files = {}
            m = self.meta
            sd = sorted(self.sim_dt_ms)
            q = lambda p: round(sd[min(len(sd) - 1, int(p * len(sd)))], 3) if sd else None  # noqa: E731
            dur = (now_ms() - self.t_start) / 1000.0
            m.update(stopped=datetime.datetime.now().isoformat(timespec="seconds"), stopped_by=why, seconds=round(dur, 1),
                     frames=self.c["frames"], phys_rows=self.c["rows"], frames_missed=self.c["skipped"],
                     counter_resets=self.c["resets"], marks=self.mark_n, fps_received=round(self.c["frames"] / dur, 2) if dur > 0 else None,
                     sim_dt_ms_p5_p50_p95=[q(0.05), q(0.5), q(0.95)], step_count=dict(sorted(self.steps.items())),
                     arcade_frames=self.c["arcade"], wreck_frames=self.c["wreck"], airborne_frames=self.c["air"],
                     reader_check=dict(self.reader_check), reader=self.reader.note if self.reader else "off",
                     reader_reads=self.reader.reads if self.reader else 0,
                     reader_ms_per_read=round(1000 * self.reader.read_s / self.reader.reads, 3) if self.reader and self.reader.reads else None,
                     logger_us_per_frame=round(1e6 * self.cost_s / self.cost_n, 2) if self.cost_n else None,
                     game_state_source="reader (0x4c2164)" if self.reader_check.get("match") else "inferred: 5 with the player present, else 6",
                     exe=self.exe_info())
            with open(os.path.join(self.sdir, "meta.json"), "w") as f:
                json.dump(m, f, indent=1)
            # owner_log.py session_summary reads raw\Sxx.LOG for the exe / logger lines (I76MEM writes them there)
            os.makedirs(os.path.join(self.rundir, "raw"), exist_ok=True)
            ex = m["exe"] or {}
            with open(os.path.join(self.rundir, "raw", "S%02d.LOG" % self.sess), "w") as f:
                f.write("signature: %s %s\n" % (ex.get("md5") or "exe not read", ex.get("path") or ""))
                f.write("I76MEM-compatible CSV from the I76 Debug telemetry logger (tools\\debug\\debug_logger.py), %d frames, "
                        "%d missed\n" % (m["frames"], m["frames_missed"]))
                f.write("local time: %s\n" % m["started"])
            self.history.append({"dir": self.sdir, "seconds": m["seconds"], "frames": m["frames"], "rows": m["phys_rows"],
                                 "missed": m["frames_missed"], "marks": m["marks"]})
            self.note = "stopped (%s): %s, %d frames, %d rows, %d missed" % (why, self.sdir, m["frames"], m["phys_rows"], m["frames_missed"])
            if self.summary:
                threading.Thread(target=self.run_summary, args=(self.rundir,), daemon=True).start()
            return True, self.note

    def toggle(self, by="hotkey"):
        with self.lock:
            return self.stop(by) if self.recording else self.start(by=by)

    def mark(self, label="", source="button"):
        with self.lock:
            if not self.recording:
                return False, "not recording - start the logger first"
            self.mark_n += 1
            self.phase = "mark%02d" % self.mark_n
            fr = self.last_frame
            row = [self.mark_n, (label or "").replace(",", ";").replace("\n", " ")]
            if fr:
                row += [fr["frame"], self.prev_tick or now_ms(), "%.4f" % fr["sim_time"], "%.3f" % fr["pos_0"], "%.3f" % fr["pos_1"],
                        "%.3f" % fr["pos_2"], "%.3f" % fr["speed"], fr["flags"]]
            else:
                row += ["", now_ms(), "", "", "", "", "", ""]
            row.append(source)
            self.files["marks"].write(",".join(str(x) for x in row) + "\n")
            self.files["marks"].flush()
            self.marks_total += 1
            return True, "mark %d%s" % (self.mark_n, (" '" + label + "'") if label else "")

    def set_auto(self, on):
        with self.lock:
            self.auto = bool(on)
            return True, "auto %s" % ("on" if self.auto else "off")

    # ---- feeds
    def wants_reader(self):
        return self.recording or (self.last_frame is not None and time.time() - self.last_frame_wall < 2.0)

    def on_slow(self, s):
        with self.lock:
            self.slow, self.slow_fresh = s, True

    def exe_info(self):
        r = self.reader.r if self.reader else None
        if not r:
            return None
        if r.path not in self.exe_md5_cache:
            self.exe_md5_cache[r.path] = file_md5(r.path)
        return {"path": r.path, "md5": self.exe_md5_cache[r.path]}

    def tick(self):
        """from the server's slow loop (4 Hz): --log-auto stop, periodic flush"""
        with self.lock:
            now = time.time()
            if self.recording:
                if self.auto and self.started_by == "auto" and now - self.present_at > self.ABSENT_STOP_S:
                    self.stop("auto: player gone %.0f s" % self.ABSENT_STOP_S)
                elif now - self.last_flush > 1.0:
                    for f in self.files.values():
                        f.flush()
                    self.last_flush = now

    def on_frame(self, fr):
        t0 = time.perf_counter()
        with self.lock:
            now = time.time()
            self.last_frame, self.last_frame_wall = fr, now
            present = bool(fr["player_present"])
            if present:
                self.present_at = now
            if not self.recording:
                if self.auto and present:
                    self.start(by="auto")
                else:
                    return
            self.write_frame(fr, present)
        self.cost_s += time.perf_counter() - t0
        self.cost_n += 1

    def write_frame(self, fr, present):
        c, s = self.c, self.slow
        tick = now_ms()
        frame = fr["frame"]
        if frame == self.prev_frame:                      # the same frame twice (shm re-read): keep one
            return
        skipped = 0
        if self.prev_frame is not None:
            gap = frame - self.prev_frame - 1
            if gap < 0 or gap > 100000:
                c["resets"] += 1
            else:
                skipped = gap
        # the reader's player object against the telemetry's (the address check), once per fresh slow read
        if self.slow_fresh:
            self.slow_fresh = False
            if present and s.get("player_obj"):
                self.reader_check["match" if s["player_obj"] == fr["obj_addr"] else "mismatch"] += 1
            elif present:
                self.reader_check["no_player_read"] += 1
        reader_ok = self.reader_check.get("match", 0) > 0 and not self.reader_check.get("mismatch", 0)
        gs = s["game_state"] if reader_ok and s["game_state"] != "" else (5 if present else 6)
        sim_dt, dt = fr["sim_dt"], fr["dt"]
        cnt = fr["step_count"] if fr["step_count"] > 0 else stepcount(sim_dt)
        step_ms = sim_dt * 1000.0 / cnt if cnt else 0.0
        c["frames"] += 1
        c["skipped"] += skipped
        if gs == 5 and 0 < sim_dt < 1.0:
            self.sim_dt_ms.append(round(sim_dt * 1000.0, 3)); self.steps[cnt] += 1
        wall = "" if self.prev_tick is None else tick - self.prev_tick
        self.files["frames"].write("%d,%d,%s,%.3f,%.3f,%.3f,%d,%d,1,0,%s\n" % (frame, tick, wall, sim_dt * 1000.0, dt * 1000.0,
                                                                                step_ms, cnt, skipped, gs))
        self.prev_frame, self.prev_tick = frame, tick
        mk = (s["cd_track"], s["cd_playing"], s["cd_loop"], s["cd_paused"], s["cd_ok"], gs) if reader_ok else None
        if mk is not None and mk != self.music_key:
            self.music_key = mk
            self.files["music"].write("%d,%d,%s,%d,%d,%d,%d,%d,%s\n" % ((frame, tick, self.phase) + mk))
        if not present:
            return
        fl = fr["flags"]
        c["rows"] += 1
        c["arcade"] += bool(fl & 0x10000); c["wreck"] += bool(fl & 0x8000); c["air"] += bool(fl & 0x4)
        health = sum(fr["armour_%d" % k] + fr["chassis_%d" % k] for k in range(4))
        health_max = sum(fr["armour_max_%d" % k] + fr["chassis_max_%d" % k] for k in range(4))
        ai = s if reader_ok else SLOW_DEFAULT
        self.files["phys"].write(",".join((
            self.phase, "%.3f" % ((tick - self.t_start) / 1000.0), "%.4f" % fr["sim_time"], "%.6f" % sim_dt, "%.6f" % dt, str(cnt),
            "%.4f" % fr["pos_0"], "%.4f" % fr["pos_1"], "%.4f" % fr["pos_2"],
            "%.5f" % fr["velocity_0"], "%.5f" % fr["velocity_1"], "%.5f" % fr["velocity_2"], "%.5f" % fr["speed"],
            "%.6g" % fr["pitch_rate"], "%.6g" % fr["yaw_rate"], "%.6g" % fr["roll_rate"],
            "%.6g" % fr["rot_1"], "%.6g" % fr["rot_4"], "%.6g" % fr["rot_6"], "%.6g" % fr["rot_7"], "%.6g" % fr["rot_8"],
            str(fl), "%.4g" % fr["throttle"], "%.4g" % fr["steer"], "%.5g" % fr["clearance"], "%.1f" % fr["rpm"], str(fr["gear"]),
            str(fr["handbrake"]),
            str(frame), str(tick), "1", "0", str(ai["oflags"]), str(health), str(health_max), "%.2f" % fr["speedo"],
            "%.3f" % step_ms, str(fr["surface"]), "%.4f" % fr["ground_normal_1"], str(ai["ai_alive"]), str(ai["ai_total"]),
            "%.2f" % ai["n_dist"], "%.2f" % ai["n_x"], "%.2f" % ai["n_z"], "%.3f" % ai["n_speed"], str(ai["n_health"]),
            str(ai["n_eflags"]), str(ai["cd_track"]), str(ai["cd_playing"]), str(gs), "0",
            "%.1f" % fr["health_pct"], str(fr.get("music_track", 0) or 0), str(self.mark_n))) + "\n")

    # ---- summary (lab tools)
    def run_summary(self, rundir):
        tool = os.path.join(MEMTRACE, "owner_log.py")
        if not os.path.exists(tool):
            self.summary_state = "no summary: %s not found" % tool
            return
        self.summary_state = "summary running"
        try:
            p = subprocess.run([sys.executable, "-I", tool, "summary", rundir], capture_output=True, text=True, timeout=300,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.summary_state = ("summary written: %s" % os.path.join(rundir, "summary.md")) if p.returncode == 0 else \
                ("summary failed (%d): %s" % (p.returncode, (p.stderr or "").strip().splitlines()[-1:] or ""))
        except Exception as e:
            self.summary_state = "summary failed: %r" % e

    # ---- view
    def status(self):
        with self.lock:
            st = {"recording": self.recording, "auto": self.auto, "root": self.root, "rundir": self.rundir, "dir": self.sdir,
                  "note": self.note, "summary": self.summary_state, "history": list(self.history),
                  "reader": self.reader.note if self.reader else "off", "hotkeys": getattr(self, "hotkeys_view", {})}
            if self.recording:
                st.update(seconds=round((now_ms() - self.t_start) / 1000.0, 1), frames=self.c["frames"], rows=self.c["rows"],
                          missed=self.c["skipped"], marks=self.mark_n, phase=self.phase, started_by=self.started_by,
                          arcade=self.c["arcade"], reader_check=dict(self.reader_check))
            return st
