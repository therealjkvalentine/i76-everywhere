r"""debug_core.py - the data side of I76 Debug (tools/debug/i76debug.py): telemetry and haptics sources, the proxy log
parser, and the Hub that keeps the recent history every dashboard panel draws from.

Nothing here creates a shared-memory section, opens a device, or sends anywhere but 127.0.0.1:

* Telemetry: the proxy's UDP stream (i76tel.h, default 127.0.0.1:7676), optionally forwarded datagram-for-datagram to
  other loopback ports (the tee: the haptics host and this tool both listen, only one socket can own the port). When the
  port is taken (the haptics host bound it first) it falls back to Local\I76Telemetry opened EXISTING-only at whatever
  size the proxy made it - never mapped at a fixed size, so it can never block a v3 proxy the way the old trainer window
  did (it created the section at the v2 size).
* Haptics: the host's --debug-udp JSON datagrams (DebugPublisher.cs, default 127.0.0.1:17680).
* The proxy log (mciproxy.log beside the game): tailed from the last proxy start, parsed into the per-panel state.
"""
import collections, ctypes, ctypes.wintypes as wt, hashlib, json, math, os, re, socket, struct, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(TOOLS, "telemetry"))
import i76tel                                                   # Header, decode_datagram, sound_fields, ev_name, ...

LAB_GAME = r"C:\Users\james\i76-uncap-lab\game"

# ---------------------------------------------------------------- shared memory, open-existing only

FILE_MAP_WRITE, FILE_MAP_READ = 0x0002, 0x0004
_k32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wt.DWORD),
                ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_size_t), ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


if _k32:
    _k32.OpenFileMappingW.restype = wt.HANDLE
    _k32.OpenFileMappingW.argtypes = (wt.DWORD, wt.BOOL, wt.LPCWSTR)
    _k32.MapViewOfFile.restype = ctypes.c_void_p
    _k32.MapViewOfFile.argtypes = (wt.HANDLE, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_size_t)
    _k32.UnmapViewOfFile.argtypes = (ctypes.c_void_p,)
    _k32.VirtualQuery.restype = ctypes.c_size_t
    _k32.VirtualQuery.argtypes = (ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t)
    _k32.CloseHandle.argtypes = (wt.HANDLE,)


class ShmView:
    """A view of an EXISTING named section (OpenFileMappingW): None from open() when nobody created it. The section's real
    size comes from VirtualQuery (page-rounded), so the reader adapts to whatever size the writer chose."""

    def __init__(self, handle, addr, size, writable):
        self.h, self.addr, self.size, self.writable = handle, addr, size, writable

    @classmethod
    def open(cls, name, writable=False):
        if not _k32:
            return None
        access = FILE_MAP_READ | (FILE_MAP_WRITE if writable else 0)
        h = _k32.OpenFileMappingW(access, False, name)
        if not h:
            return None
        addr = _k32.MapViewOfFile(h, access, 0, 0, 0)
        if not addr:
            _k32.CloseHandle(h)
            return None
        mbi = MEMORY_BASIC_INFORMATION()
        _k32.VirtualQuery(addr, ctypes.byref(mbi), ctypes.sizeof(mbi))
        return cls(h, addr, int(mbi.RegionSize), writable)

    def read(self, off, n):
        n = max(0, min(n, self.size - off))
        return ctypes.string_at(self.addr + off, n)

    def u32(self, off):
        return struct.unpack("<I", self.read(off, 4))[0]

    def write(self, off, data):
        if not self.writable or off + len(data) > self.size:
            raise ValueError("view is read-only or too small")
        ctypes.memmove(self.addr + off, data, len(data))

    def close(self):
        if self.addr:
            _k32.UnmapViewOfFile(self.addr)
            self.addr = None
        if self.h:
            _k32.CloseHandle(self.h)
            self.h = None


# ---------------------------------------------------------------- small helpers

def jsonable(v):
    if isinstance(v, bytes):
        return v.split(b"\0")[0].decode("latin1", "replace")
    if isinstance(v, float):
        return round(v, 5) if math.isfinite(v) else 0.0
    return v


def file_md5(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None


def angles(fr):
    """pitch, roll, heading (rad) from the frame's rot rows (i76tel.h: pitch = asin(rot[7]), roll = asin(rot[1]),
    heading = atan2(rot[6], rot[8]))"""
    def cl(x):
        return max(-1.0, min(1.0, x))
    return math.asin(cl(fr["rot_7"])), math.asin(cl(fr["rot_1"])), math.atan2(fr["rot_6"], fr["rot_8"])


# ---------------------------------------------------------------- telemetry

class TelemetrySource(threading.Thread):
    """UDP on 127.0.0.1:port (+ tee) or, when the port is taken, the existing shared memory. Hands raw datagrams to
    hub.on_datagram. port 0 = shared memory only; port None = off."""

    def __init__(self, hub, port=7676, tee=(), shm_fallback=True, shm_suffix=""):
        super().__init__(daemon=True, name="telemetry")
        self.hub, self.port, self.tee, self.shm_fallback, self.suffix = hub, port, list(tee), shm_fallback, shm_suffix
        self.mode, self.note = "off", ""
        self.forwarded = self.received = 0
        self.stop_ev = threading.Event()
        self.sock = None

    def bind(self):
        if not self.port:
            return False
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # never SO_REUSEADDR: on Windows it would let this socket share (steal) a port the haptics host already owns
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            s.bind(("127.0.0.1", self.port))
        except OSError as e:
            s.close()
            self.note = "udp 127.0.0.1:%d is taken (%s)" % (self.port, e.strerror or e)
            return False
        s.settimeout(0.25)
        self.sock = s
        return True

    def run(self):
        if self.bind():
            self.mode = "udp 127.0.0.1:%d%s" % (self.port, (" -> tee " + ",".join(str(p) for p in self.tee)) if self.tee else "")
            out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if self.tee else None
            while not self.stop_ev.is_set():
                try:
                    data, _ = self.sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    continue
                self.received += 1
                for p in self.tee:
                    try:
                        out.sendto(data, ("127.0.0.1", p)); self.forwarded += 1
                    except OSError:
                        pass
                self.hub.on_datagram(data, "udp")
            self.sock.close()
            return
        if self.port is not None and self.shm_fallback:
            self.mode = "shm (existing only)" + ((" - " + self.note) if self.note else "")
            self.run_shm()

    def run_shm(self):
        h = self.hub.tel_h
        name = h.consts["I76TEL_SHM_NAME"] + self.suffix
        view, last_seq, last_ev = None, None, None
        ring = h.consts["I76TEL_RING"]
        while not self.stop_ev.is_set():
            if view is None:
                view = ShmView.open(name)
                if view is None:
                    self.mode = "shm: %s not present (no proxy running, or telemetry off)%s" % (name, (" - " + self.note) if self.note else "")
                    self.stop_ev.wait(1.0)
                    continue
                self.mode = "shm %s (%d B section, opened existing)%s" % (name, view.size, (" - " + self.note) if self.note else "")
            seq0 = view.u32(0)
            if seq0 == 0 or seq0 & 1 or seq0 == last_seq:
                self.stop_ev.wait(0.002)
                continue
            buf = view.read(0, view.size)
            if view.u32(0) != seq0:
                continue
            last_seq = seq0
            lay = i76tel.shm_layout(h, buf)
            if lay.structs["i76tel_shm_t"][1] > len(buf):
                self.mode = "shm %s: the section (%d B) is smaller than the writer's v%d layout - use UDP" % (name, view.size, lay.consts["I76TEL_VERSION"])
                self.stop_ev.wait(1.0)
                continue
            fo, ro = lay.offset("i76tel_shm_t", "frame"), lay.offset("i76tel_shm_t", "ring")
            frame = bytearray(buf[fo:fo + lay.frame_size])
            es = struct.unpack_from("<I", frame, lay.offset("i76tel_frame_t", "event_seq"))[0]
            if last_ev is None:
                last_ev = es
            n = min(es - last_ev, ring) if es >= last_ev else 0
            evs = b"".join(buf[ro + (s % ring) * lay.event_size: ro + (s % ring + 1) * lay.event_size] for s in range(es - n + 1, es + 1))
            last_ev = es
            struct.pack_into("<I", frame, lay.offset("i76tel_frame_t", "event_count"), n)
            self.received += 1
            self.hub.on_datagram(bytes(frame) + evs, "shm")
        if view:
            view.close()


class HapticsSource(threading.Thread):
    """The haptics host's --debug-udp datagrams (JSON) on 127.0.0.1:port."""

    def __init__(self, hub, port=17680):
        super().__init__(daemon=True, name="haptics")
        self.hub, self.port = hub, port
        self.mode, self.received = "off", 0
        self.stop_ev = threading.Event()

    def run(self):
        if not self.port:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            s.bind(("127.0.0.1", self.port))
        except OSError as e:
            self.mode = "udp 127.0.0.1:%d taken (%s): another I76 Debug running?" % (self.port, e.strerror or e)
            return
        self.mode = "udp 127.0.0.1:%d" % self.port
        s.settimeout(0.25)
        while not self.stop_ev.is_set():
            try:
                data, _ = s.recvfrom(65535)
            except (socket.timeout, OSError):
                continue
            try:
                j = json.loads(data)
            except ValueError:
                continue
            self.received += 1
            self.hub.on_haptics(j)
        s.close()


# ---------------------------------------------------------------- the proxy log

KNOWN_SWITCHES = set("""I76_SOUND_EVENTS I76_ROAD_DIST I76_MISSION I76_FAR_CLIP I76_DAMAGE_EVENTS I76_COLL_WINDOW I76_BREAKABLE_BOX
I76_ZGLIDE_TMUFIX I76_TRAINER I76_TEX_CENSUS I76_TERRAIN_TEX I76_TERRAIN_LOD I76_TELEMETRY I76_SW_RES I76_START_POS
I76_SKIP_MOVIES I76_SHADOW_DIST I76_ROAD_TEX I76_ROAD_POOL I76_RENDER_INTERP I76_PHYS_RATE I76_OBJECT_LOD I76_NO_MINIMIZE
I76_MUSIC_GUARD I76_MIRROR_RATE I76_MIRROR_FAR I76_JOY_SYNTH I76_JOY_MAP I76_INTERP_SMOOTH I76_INPUT_LATCH I76_HUD_SQUEEZE
I76_HIRES_CLOCK I76_GLIDE_REFRESH I76_GLIDE_GAMMA I76_FRAME_SPIKES I76_FRAMERATE_FIXES I76_FPS_PROF I76_FPS_LOG I76_FPS_CAP
I76_FLASH_PROBE I76_FIX_LABEL_TABLE I76_FIX_HEALTH_PCT I76_FIXED_STEP I76_FAR_ENGINE_DT I76_ENGINE_DT_FIX I76_CWD_FIX
I76_CRASH_LOG I76_COOP_AI I76_COOP_CHAIN I76_COOP_HEAPWATCH I76_COLL_WINDOW_WHEN I76_COLL_WINDOW_SCALE I76_COLL_DEDUPE
I76_CLUTTER_DIST I76_CAM_GROUND_FIX I76_ASPECT I76_AI_FIXES I76_AI_BACKAWAY_GRID I76_HAZARD_CONTACT I76_PERFRAME_FIXES I76_DRAW_PROBE""".split())
# log prefix -> switch, where the generic rule (I76_ + prefix upper-cased, '-' -> '_') does not give a known name
PREFIX_SWITCH = {"fix-health-pct": "I76_FIX_HEALTH_PCT", "fix-label-table": "I76_FIX_LABEL_TABLE", "sound-events": "I76_SOUND_EVENTS",
                 "damage-events": "I76_DAMAGE_EVENTS", "coll-window": "I76_COLL_WINDOW", "breakable-box": "I76_BREAKABLE_BOX",
                 "zglide-tmufix": "I76_ZGLIDE_TMUFIX", "mission-launch": "I76_MISSION", "start-pos": "I76_START_POS",
                 "fps-cap": "I76_FPS_CAP", "fps-log": "I76_FPS_LOG", "clutter-dist": "I76_CLUTTER_DIST", "flash-probe": "I76_FLASH_PROBE",
                 "cam-ground-fix": "I76_CAM_GROUND_FIX", "glide-refresh": "I76_GLIDE_REFRESH", "glide-gamma": "I76_GLIDE_GAMMA",
                 "music-guard": "I76_MUSIC_GUARD", "trainer": "I76_TRAINER", "tex-census": "I76_TEX_CENSUS", "aspect": "I76_ASPECT",
                 "draw-probe": "I76_DRAW_PROBE", "breakable-speed": "I76_BREAKABLE_BOX"}
PERIODIC = ("fps", "clutter", "road-pool", "coop-ai", "coop-heap", "coop-chain", "coop-dmg", "hud-squeeze", "str ok", "PLAY", "run")
FEATURE_WORDS = (" on", "repointed", "patched", "installed", "not applied", " off", "hooked", "armed", "enabled", ": x", " -> ")

RX = {
    "fps": re.compile(r"fps: ([\d.]+) \((\d+) frames / ([\d.]+) s\); work ([\d.]+) ms avg, ([\d.]+) ms max; cap wait ([\d.]+) ms avg"),
    "fixed": re.compile(r"fixed-step: ([\d.]+) steps/s \(([\d.]+) ms\) (\w+)"),
    "cw_sf": re.compile(r"coll-window when=stepframe: pair tests (\d+), widened \(a body steps this frame\) (\d+), stock window (\d+), no pair window \(=2 used\) (\d+)"),
    "cw_v3": re.compile(r"coll-window v3: sphere->slab tests (\d+), widened \(class [^)]*\) (\d+); part classes seen:(.*) other (\d+)"),
    "bbox": re.compile(r"breakable-box: (\d+) class-4 default parts seen, (\d+) made boxes"),
    "lift": re.compile(r"cam-ground-fix: lift #(\d+) \(camera (\w+), (\w+)(?:, mode (-?\d+))?\): eye ([\d.]+) m under the terrain height (-?[\d.]+); setup (.*)"),
    "ckunder": re.compile(r"cam-ground-fix: COCKPIT-UNDER #(\d+): eye ([\d.]+) m under the terrain height (-?[\d.]+)"),
    "tdrop": re.compile(r"TERRAIN-DROP #(\d+) at swap (\d+) \(proxy frame (\d+), t (\d+) ms, state (\d+), cam mode (\d+)\): terrain vertices (\d+) "
                        r"\(previous scene (\d+)\) \| camera \((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\), (-?[\d.]+) m above the terrain height (-?[\d.]+), "
                        r"moved ([\d.]+) m since the previous scene \| player \((-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)"),
    "flash": re.compile(r"flash-probe: swaps (\d+): last 600: (\d+) main scenes, terrain vertices min (\d+), (\d+) zero-terrain scenes, (\d+) drops < 30 %, "
                        r"(\d+) pixel flashes \| totals (\d+) terrain events \((\d+) zero\), (\d+) pixel flashes \| cam-ground lifts (\d+) \((\d+) refused\)"),
    "flush": re.compile(r"tex-census: FLUSH #(\d+) at swap (\d+) \(proxy frame (\d+), t (\d+) ms\): (\d+) downloads / (\d+) KB since start, resident before (\d+) KB, no-slot flag (\d+)"),
    "tswaps": re.compile(r"tex-census: swaps (\d+) \(proxy frame (\d+)\): last 600: (\d+) downloads (\d+) KB, (\d+) flushes, (\d+) no-slot; resident (\d+) KB \(peak (\d+) KB\), TMU (\d+); "
                         r"totals (\d+) dl, (\d+) flushes, (\d+) no-slot"),
    "road": re.compile(r"road-pool: (\d+) frames: refused (\d+) polygons \((\d+) past the pool, (\d+) past bucket \d+\), (\d+) bucket links dropped; node high water (\d+) KB of (\d+) KB; refusals since start (\d+)"),
    "clutter": re.compile(r"clutter: (\d+) frames: (\d+) us avg, (\d+) us max; cells ([\d.]+) avg, (\d+) max; instances tested (\d+)/frame; refused \(pool\) (\d+); record pool high water (\d+) KB"),
    # I76_DRAW_PROBE (2026-10-12): per-swap terrain draw census, loss events and a 600-swap summary
    "tloss": re.compile(r"draw-probe: TERRAIN-LOSS #(\d+) at swap (\d+) \(proxy frame (\d+), t (\d+) ms, cam mode (\d+)\): main terrain polygons emitted (\d+), "
                        r"clipped away (\d+), below the bucket floor (\d+) \(floor (-?[\d.]+), span (-?[\d.]+)\), past bucket 4096 (\d+), > 32 vertices (\d+), "
                        r"queued (\d+), drawn (\d+) \(previous swap (\d+)\)"),
    "triloss": re.compile(r"draw-probe: TRIANGLE-LOSS #(\d+) at swap (\d+) \(proxy frame (\d+), t (\d+) ms, cam mode (\d+)\): triangles (\d+) \(previous (\d+)\) "
                          r"with main terrain polygons drawn (\d+) \(previous (\d+)\), LFB locks (\d+)"),
    "dsum": re.compile(r"draw-probe: swaps (\d+): last 600: main terrain polygons drawn min (\d+), triangles min (\d+), LFB locks (\d+), main terrain clipped away (\d+), "
                       r"below the floor (\d+), past 4096 (\d+) \| totals (\d+) terrain losses, (\d+) triangle losses \| (\d+) terrain textures seen"),
    "prefix": re.compile(r"^  ([A-Za-z][\w-]*(?: [\w=.-]+)?): (.*)$"),
}


class ProxyLog:
    """mciproxy.log from the last proxy start on, followed as it grows. parse(line) keeps the per-panel state."""

    SESSION_MARK = "  strlkup_orig:"

    def __init__(self, path=None):
        self.path, self.pos, self.ino = path, 0, None
        self.lines = collections.deque(maxlen=4000)            # (id, text)
        self.next_id = 1
        self.reset()

    def reset(self):
        self.features = collections.OrderedDict()              # prefix -> {text, applied, switch}
        self.fps = None
        self.fps_hist = collections.deque(maxlen=240)
        self.fixed_step = None
        self.coll = {"stepframe": None, "v3": None, "status": [], "hist": collections.deque(maxlen=240)}
        self.bbox = {"status": None, "report": None, "parts": 0, "boxes": 0}
        self.lifts, self.cockpit_under = collections.deque(maxlen=200), collections.deque(maxlen=200)
        self.lift_count = self.cockpit_count = 0
        self.terrain_drops = collections.deque(maxlen=200)
        self.flash = None
        self.flushes = collections.deque(maxlen=200)
        self.tex = None
        self.tex_noslot = collections.deque(maxlen=100)
        self.road = self.clutter = None
        self.draw_losses = collections.deque(maxlen=200)
        self.draw = None
        self.start_pos = collections.deque(maxlen=20)
        self.render_interp = None
        self.not_applied = collections.deque(maxlen=100)
        self.crashes = collections.deque(maxlen=20)
        self.session_lines = 0

    def set_path(self, path):
        if path != self.path:
            self.path, self.pos, self.ino = path, 0, None
            self.reset()

    def poll(self):
        """read what was appended since the last call (the first call starts at the last proxy start in the newest 4 MB)"""
        if not self.path:
            return []
        try:
            st = os.stat(self.path)
        except OSError:
            return []
        if st.st_size < self.pos:                              # truncated / replaced: start over
            self.pos = 0
            self.reset()
        new = []
        try:
            with open(self.path, "rb") as f:
                if self.pos == 0:
                    start = max(0, st.st_size - 4 * 1024 * 1024)
                    f.seek(start)
                    text = f.read().decode("latin1", "replace").lstrip("\ufeff").replace("\xef\xbb\xbf", "")
                    k = text.rfind(self.SESSION_MARK)
                    if k < 0 and start:
                        k = text.find("\n") + 1
                    text = text[max(0, k):]
                    self.pos = st.st_size
                else:
                    f.seek(self.pos)
                    raw = f.read(st.st_size - self.pos)
                    nl = raw.rfind(b"\n")
                    if nl < 0:
                        return []
                    raw = raw[:nl + 1]
                    self.pos += len(raw)
                    text = raw.decode("latin1", "replace").replace("\xef\xbb\xbf", "")
        except OSError:
            return []
        for line in text.splitlines():
            if not line.strip():
                continue
            if line.startswith(self.SESSION_MARK):
                self.reset()                                   # a new proxy start: the state is per process
            new.append(self.add(line))
        return new

    def add(self, line):
        lid = self.next_id
        self.next_id += 1
        self.lines.append((lid, line))
        self.session_lines += 1
        self.parse(line)
        return (lid, line)

    def parse(self, line):
        m = RX["fps"].search(line)
        if m:
            self.fps = {"fps": float(m.group(1)), "frames": int(m.group(2)), "secs": float(m.group(3)), "work_avg": float(m.group(4)),
                        "work_max": float(m.group(5)), "cap_wait": float(m.group(6)), "at": time.time()}
            self.fps_hist.append(self.fps["fps"])
            return
        m = RX["cw_sf"].search(line)
        if m:
            d = dict(zip(("pairs", "widened", "stock", "fallback"), map(int, m.groups())))
            d["at"] = time.time()
            self.coll["stepframe"] = d
            self.coll["hist"].append(d)
            return
        m = RX["cw_v3"].search(line)
        if m:
            self.coll["v3"] = {"tests": int(m.group(1)), "widened": int(m.group(2)), "classes": m.group(3).strip(), "other": int(m.group(4)), "at": time.time()}
            return
        m = RX["lift"].search(line)
        if m:
            self.lift_count = int(m.group(1))
            self.lifts.append({"n": int(m.group(1)), "camera": m.group(2), "which": m.group(3), "mode": int(m.group(4)) if m.group(4) else None,
                               "depth": float(m.group(5)), "terrain": float(m.group(6)), "setup": m.group(7)})
            return
        m = RX["ckunder"].search(line)
        if m:
            self.cockpit_count = int(m.group(1))
            self.cockpit_under.append({"n": int(m.group(1)), "depth": float(m.group(2)), "terrain": float(m.group(3))})
            return
        m = RX["tdrop"].search(line)
        if m:
            g = m.groups()
            self.terrain_drops.append({"n": int(g[0]), "swap": int(g[1]), "frame": int(g[2]), "state": int(g[4]), "cam_mode": int(g[5]),
                                       "vertices": int(g[6]), "prev": int(g[7]), "camera": [float(g[8]), float(g[9]), float(g[10])],
                                       "eye_above": float(g[11]), "terrain": float(g[12]), "moved": float(g[13]),
                                       "player": [float(g[14]), float(g[15]), float(g[16])]})
            return
        m = RX["flash"].search(line)
        if m:
            k = ("swaps", "scenes", "vmin", "zero", "drops", "pix", "events", "events_zero", "pix_total", "lifts", "refused")
            self.flash = dict(zip(k, map(int, m.groups())))
            return
        m = RX["tloss"].search(line)
        if m:
            g = list(map(float, m.groups()))
            self.draw_losses.append({"kind": "TERRAIN-LOSS", "n": int(g[0]), "swap": int(g[1]), "frame": int(g[2]), "cam_mode": int(g[4]),
                                     "emitted": int(g[5]), "clipped": int(g[6]), "below_floor": int(g[7]), "floor": g[8], "span": g[9],
                                     "past_4096": int(g[10]), "big": int(g[11]), "queued": int(g[12]), "drawn": int(g[13]), "prev": int(g[14])})
            return
        m = RX["triloss"].search(line)
        if m:
            g = list(map(int, m.groups()))
            self.draw_losses.append({"kind": "TRIANGLE-LOSS", "n": g[0], "swap": g[1], "frame": g[2], "cam_mode": g[4], "triangles": g[5],
                                     "prev_triangles": g[6], "drawn": g[7], "prev": g[8], "lfb": g[9]})
            return
        m = RX["dsum"].search(line)
        if m:
            k = ("swaps", "drawn_min", "tris_min", "lfb", "clipped", "below_floor", "past_4096", "terrain_losses", "triangle_losses", "textures")
            self.draw = dict(zip(k, map(int, m.groups())))
            return
        m = RX["flush"].search(line)
        if m:
            k = ("n", "swap", "frame", "t_ms", "downloads", "kb", "resident_kb", "noslot")
            self.flushes.append(dict(zip(k, map(int, m.groups()))))
            return
        m = RX["tswaps"].search(line)
        if m:
            k = ("swaps", "frame", "dl", "dl_kb", "flushes", "noslot", "resident_kb", "peak_kb", "tmu", "total_dl", "total_flushes", "total_noslot")
            self.tex = dict(zip(k, map(int, m.groups())))
            return
        if "tex-census: NO-SLOT" in line:
            self.tex_noslot.append(line.strip())
            return
        m = RX["road"].search(line)
        if m:
            k = ("frames", "refused", "past_pool", "past_bucket", "links_dropped", "high_kb", "pool_kb", "refusals_total")
            self.road = dict(zip(k, map(int, m.groups())))
            return
        m = RX["clutter"].search(line)
        if m:
            g = m.groups()
            self.clutter = {"frames": int(g[0]), "us_avg": int(g[1]), "us_max": int(g[2]), "cells_avg": float(g[3]), "cells_max": int(g[4]),
                            "tested": int(g[5]), "refused": int(g[6]), "pool_kb": int(g[7])}
            return
        m = RX["bbox"].search(line)
        if m:
            self.bbox.update(parts=int(m.group(1)), boxes=int(m.group(2)), report=line.strip())
            return
        if "start-pos:" in line:
            self.start_pos.append(line.strip())
        if "CRASH" in line:
            self.crashes.append(line.strip())
        m = RX["prefix"].match(line)
        if not m:
            return
        prefix, text = m.group(1), m.group(2)
        base = prefix.split(" ")[0]
        if base in PERIODIC or base.startswith("coop"):
            return
        if "not applied" in text:
            self.not_applied.append(line.strip())
        if base == "fixed-step":
            fm = RX["fixed"].search(line)
            if fm:
                self.fixed_step = {"hz": float(fm.group(1)), "ms": float(fm.group(2)), "state": fm.group(3)}
        if base == "render-interp":
            self.render_interp = text
        if base == "breakable-box" and "class-4 default parts" not in text:
            self.bbox["status"] = text
        if base == "coll-window" and len(self.coll["status"]) < 12:
            self.coll["status"].append(line.strip())
        if base == "cam-ground-fix" and not text.startswith(("lift", "COCKPIT")):
            self.features["cam-ground-fix"] = self.feature(base, text)
            return
        if any(w in text for w in FEATURE_WORDS) or text.startswith(("on", "off")):
            self.features[base] = self.feature(base, text)

    @staticmethod
    def feature(base, text):
        sw = PREFIX_SWITCH.get(base) or ("I76_" + base.upper().replace("-", "_"))
        applied = "not applied" not in text and not text.startswith("off") and "needs " not in text[:6]
        if applied and ("FAILED" in text or "refused" in text):
            applied = None                                       # on, but part of it failed (e.g. telemetry with its shm view refused)
        return {"text": text[:240], "applied": applied, "switch": sw if sw in KNOWN_SWITCHES else None}

    def state(self):
        return {
            "path": self.path, "lines": self.session_lines,
            "features": [{"name": k, **v} for k, v in self.features.items()],
            "switches_from_log": sorted({v["switch"] for v in self.features.values() if v["switch"] and v["applied"] is not False}),
            "not_applied": list(self.not_applied), "fps": self.fps, "fps_hist": list(self.fps_hist), "fixed_step": self.fixed_step,
            "render_interp": self.render_interp,
            "coll": {"stepframe": self.coll["stepframe"], "v3": self.coll["v3"], "status": self.coll["status"], "hist": list(self.coll["hist"])[-60:]},
            "bbox": self.bbox, "lift_count": self.lift_count, "lifts": list(self.lifts)[-40:], "cockpit_count": self.cockpit_count,
            "cockpit_under": list(self.cockpit_under)[-40:], "terrain_drops": list(self.terrain_drops)[-40:], "flash": self.flash,
            "flushes": list(self.flushes)[-40:], "tex": self.tex, "tex_noslot": list(self.tex_noslot)[-20:], "road": self.road,
            "clutter": self.clutter, "draw": self.draw, "draw_losses": list(self.draw_losses)[-40:], "start_pos": list(self.start_pos), "crashes": list(self.crashes),
        }

    def tail(self, n=500, q=None, after=0):
        out = []
        ql = q.lower() if q else None
        for lid, text in reversed(self.lines):
            if lid <= after:
                break
            if ql and ql not in text.lower():
                continue
            out.append({"id": lid, "text": text})
            if len(out) >= n:
                break
        return list(reversed(out))


# ---------------------------------------------------------------- the hub

EV_NAMES = {1: "SHOT", 2: "EXPLOSION", 3: "IMPACT", 4: "SOUND_START", 5: "SOUND_STOP", 6: "DAMAGE_SIDE", 7: "WEAPON_UI"}
SRC_CLASS = {0: "terrain/none", 1: "car", 0x33: "ordnance", 0x34: "explosion"}


class Hub:
    """Everything the panels show, with a short history. Fed by the source threads; read by the HTTP handlers."""

    SAMPLE_HZ = 60.0

    def __init__(self):
        self.lock = threading.RLock()
        self.tel_h = i76tel.Header()
        self.t0 = time.time()
        # telemetry
        self.frame, self.frame_at, self.frames, self.tel_src, self.tel_version = None, 0.0, 0, None, None
        self.samples = collections.deque(maxlen=7200)          # compact per-frame samples (decimated to SAMPLE_HZ)
        self.sample_id = 0
        self.last_sample_wall = 0.0
        self.fps_win = collections.deque(maxlen=240)          # (wall, frame counter) for the arrival rate
        self.dt_hist = collections.deque(maxlen=600)
        self.trail = collections.deque(maxlen=1500)           # player x, z for the minimap
        self.short_dgrams = 0
        # events
        self.events = collections.deque(maxlen=1000)
        self.event_id = 0
        self.ev_count = collections.Counter()
        self.impacts = {"player": 0, "other": 0, "by_source": collections.Counter(), "player_hp": 0.0}
        self.damage_sides = {k: {"hits": 0, "hp": 0.0} for k in ("front", "left", "right", "back", "top", "?")}
        self.damage_zones = collections.Counter()
        self.damage_other = {"hits": 0, "hp": 0.0, "kills": 0, "by_player": 0}
        self.shots = collections.Counter()
        self.explosions = collections.deque(maxlen=50)
        self.explosion_names = collections.Counter()
        self.sounds = collections.Counter()
        self.sounds_active = {}                               # voice address -> {name, hz, vol, player, mode, t}
        self.weapon_ui = collections.Counter()
        self.markers = collections.deque(maxlen=200)          # world positions of recent events (minimap)
        # haptics
        self.hap, self.hap_at, self.hap_count = None, 0.0, 0
        self.hsamples = collections.deque(maxlen=7200)
        self.hsample_id = 0
        self.hap_events = collections.deque(maxlen=300)
        self.hap_event_id = 0
        # sources (set by the server)
        self.tel_source = self.hap_source = None
        self.log = ProxyLog()
        self.trainer = None
        self.logger = None                                    # debug_logger.PhysLogger (fed every frame, outside the lock)
        self.game_info = {}

    # ---- telemetry
    def on_datagram(self, data, src):
        h = self.tel_h
        fr, evs = i76tel.decode_datagram(h, data)
        now = time.time()
        with self.lock:
            if fr is None:
                self.short_dgrams += 1
                return
            if fr["magic"] != h.consts["I76TEL_MAGIC"]:
                self.short_dgrams += 1
                return
            self.frames += 1
            self.frame, self.frame_at, self.tel_src, self.tel_version = fr, now, src, fr["version"]
            self.fps_win.append((now, fr["proxy_frame"]))
            self.dt_hist.append(fr["dt"] * 1000.0)
            if fr["player_present"]:
                if not self.trail or (fr["pos_0"] - self.trail[-1][0]) ** 2 + (fr["pos_2"] - self.trail[-1][1]) ** 2 > 0.25:
                    self.trail.append((round(fr["pos_0"], 2), round(fr["pos_2"], 2)))
            if now - self.last_sample_wall >= 1.0 / self.SAMPLE_HZ - 1e-4:
                self.last_sample_wall = now
                self.sample_id += 1
                self.samples.append(self.compact(fr, now))
            for ev in evs:
                self.add_event(ev, fr, now)
        lg = self.logger
        if lg is not None:
            lg.on_frame(fr)

    def compact(self, fr, now):
        p, r, hd = angles(fr)
        # accel_body is the exe's FFB-block copy, valid only while ffb_present (0 otherwise, as in the overnight t05 run):
        # else rotate the world acceleration (ent+0xd4) into the body frame, v_body[i] = sum_j rot[3i+j] * v_world[j]
        if fr["ffb_present"] and (fr["accel_body_0"] or fr["accel_body_1"] or fr["accel_body_2"]):
            ab, ab_src = (fr["accel_body_0"], fr["accel_body_1"], fr["accel_body_2"]), "ffb"
        else:
            a = (fr["accel_0"], fr["accel_1"], fr["accel_2"])
            ab = tuple(sum(fr["rot_%d" % (3 * i + j)] * a[j] for j in range(3)) for i in range(3))
            ab_src = "rot*accel"
        s = {"id": self.sample_id, "w": round(now - self.t0, 3), "t": round(fr["sim_time"], 3), "dt": round(fr["dt"] * 1000.0, 2),
             "sdt": round(fr["sim_dt"] * 1000.0, 2), "steps": fr["step_count"], "pp": fr["player_present"],
             "speed": round(fr["speed"], 3), "rpm": round(fr["rpm"], 1), "gear": fr["gear"], "thr": round(fr["throttle"], 3),
             "str": round(fr["steer"], 3), "ax": round(ab[0], 3), "ay": round(ab[1], 3), "az": round(ab[2], 3), "abs": ab_src,
             "pitch": round(p, 4), "roll": round(r, 4), "hdg": round(hd, 4), "pr": round(fr["pitch_rate"], 4), "yr": round(fr["yaw_rate"], 4),
             "rr": round(fr["roll_rate"], 4), "x": round(fr["pos_0"], 2), "y": round(fr["pos_1"], 2), "z": round(fr["pos_2"], 2),
             "clr": round(fr["clearance"], 3), "gg": round(fr["ground_g"], 3), "grip": round(fr["grip_sum"], 3), "gcap": round(fr["grip_cap"], 3),
             "pwr": round(fr["drive_power"], 3), "fl": fr["flags"], "surf": fr["surface"], "hp": round(fr["health_pct"], 1),
             "susp": [round(fr["wheel%d_susp_offset" % k], 4) for k in range(6)], "wg": [round(fr["wheel%d_grip" % k], 3) for k in range(6)],
             "skid": [fr["wheel%d_skid_active" % k] for k in range(6)]}
        return s

    def add_event(self, ev, fr, now):
        h = self.tel_h
        c = h.consts
        t = ev["type"]
        name = EV_NAMES.get(t, "type%d" % t)
        self.ev_count[name] += 1
        d = {"type": name, "seq": ev["seq"], "frame": ev["frame"], "w": round(now - self.t0, 3), "text": i76tel.event_line(h, ev).strip()}
        f = [ev.get("f_%d" % k, 0.0) for k in range(6)]
        i = [ev.get("i_%d" % k, 0) for k in range(5)]
        if t == c["I76TEL_EV_SHOT"]:
            row = int(f[0])
            wname = fr["weapon_name"].split(b"\0")[0].decode("ascii", "replace") if fr["weapon_row"] == row else ""
            key = "row %d%s" % (row, (" " + wname) if wname else "")
            self.shots[key] += max(1, i[1])
            d.update(row=row, weapon=wname, ammo=int(f[1]), dmg=int(f[2]), rounds=i[1])
        elif t == c["I76TEL_EV_EXPLOSION"]:
            nm = i76tel.ev_name(ev)
            self.explosion_names[nm] += 1
            e = {"name": nm, "pos": [round(f[0], 1), round(f[1], 1), round(f[2], 1)], "dist": round(f[3], 1), "w": d["w"]}
            self.explosions.append(e)
            self.markers.append({"kind": "explosion", "x": f[0], "z": f[2], "w": d["w"], "label": nm})
            d.update(name=nm, pos=e["pos"], dist=e["dist"])
        elif t == c["I76TEL_EV_IMPACT"]:
            mag = math.sqrt(f[0] ** 2 + f[1] ** 2 + f[2] ** 2)
            who = "player" if i[0] else "other"
            self.impacts[who] += 1
            self.impacts["by_source"][SRC_CLASS.get(i[1], "class %d" % i[1])] += 1
            if i[0]:
                self.impacts["player_hp"] += f[3]
            d.update(player=bool(i[0]), source=SRC_CLASS.get(i[1], "class %d" % i[1]), mag=round(mag, 2), hp=round(f[3], 1))
        elif t == c.get("I76TEL_EV_SOUND_START"):
            s = i76tel.sound_fields(h, ev)
            nm = i76tel.ev_name(ev)
            self.sounds[nm] += 1
            self.sounds_active[i[4] & 0xffffffff] = {"name": nm, "hz": round(f[0], 1), "vol": round(f[1], 1), "player": s["is_player"],
                                                      "mode": i76tel.SND_MODE.get(s["mode"], str(s["mode"])), "w": d["w"]}
            if len(self.sounds_active) > 256:
                self.sounds_active.pop(next(iter(self.sounds_active)))
            if s["has_pos"]:
                self.markers.append({"kind": "sound", "x": f[2], "z": f[4], "w": d["w"], "label": nm})
            d.update(name=nm, hz=round(f[0], 1), vol=round(f[1], 1), pan=round(f[5], 1), player=s["is_player"], mode=i76tel.SND_MODE.get(s["mode"], s["mode"]))
        elif t == c.get("I76TEL_EV_SOUND_STOP"):
            s = i76tel.sound_fields(h, ev)
            nm = i76tel.ev_name(ev)
            self.sounds_active.pop(i[4] & 0xffffffff, None)
            d.update(name=nm, after=round(f[0], 2), reason=i76tel.STOP_REASON.get(s["reason"], hex(s["reason"])), player=s["is_player"])
        elif t == c.get("I76TEL_EV_DAMAGE_SIDE"):
            side = i76tel.SIDES.get(i[0], "?")
            pl = bool(i[2] & c["I76TEL_DMG_PLAYER"])
            if pl:
                ds = self.damage_sides.setdefault(side, {"hits": 0, "hp": 0.0})
                ds["hits"] += 1
                ds["hp"] += f[1]
                self.damage_zones[i[1]] += 1
            else:
                self.damage_other["hits"] += 1
                self.damage_other["hp"] += f[1]
                self.damage_other["kills"] += bool(i[2] & c["I76TEL_DMG_KILLED"])
                self.damage_other["by_player"] += bool(i[2] & c["I76TEL_DMG_BY_PLAYER"])
            d.update(player=pl, side=side, zone=i[1], incoming=round(f[0], 1), lost=round(f[1], 1),
                     killed=bool(i[2] & c["I76TEL_DMG_KILLED"]), by_player=bool(i[2] & c["I76TEL_DMG_BY_PLAYER"]))
        elif t == c.get("I76TEL_EV_WEAPON_UI"):
            k = i76tel.WEAPON_UI.get(i[0], str(i[0]))
            self.weapon_ui[k] += 1
            d.update(action=k)
        self.event_id += 1
        d["id"] = self.event_id
        self.events.append(d)

    # ---- haptics
    def on_haptics(self, j):
        now = time.time()
        with self.lock:
            self.hap, self.hap_at = j, now
            self.hap_count += 1
            w, pad, lfe, mo, bus = j.get("wheel", {}), j.get("pad", {}), j.get("lfe", {}), j.get("motion_out", {}), j.get("bus", {})
            self.hsample_id += 1
            self.hsamples.append({
                "id": self.hsample_id, "w": round(now - self.t0, 3), "t": j.get("t"),
                "model": w.get("model"), "voice": w.get("voice"), "dev": w.get("device"), "peak": w.get("peak"),
                "ch": w.get("channels", {}), "vw": {v["id"]: v.get("wheel", 0) for v in j.get("voices", []) if v.get("wheel")},
                "pl": pad.get("l"), "pr": pad.get("r"), "ppl": pad.get("peak_l", pad.get("l")), "ppr": pad.get("peak_r", pad.get("r")),
                "rms": lfe.get("rms"), "lpk": lfe.get("peak"),
                "lfe_src": {k: bus.get("lfe", {}).get(k, 0) for k in ("engine", "road", "impulse", "heave", "weapon", "scrub", "explode")},
                "ms": [mo.get(k) for k in ("surge", "sway", "heave", "roll_rate", "pitch_rate", "yaw_rate")],
                "mc": [mo.get(k) for k in ("cue_surge", "cue_sway", "cue_heave")], "mg": mo.get("gain"), "mst": mo.get("status"),
            })
            for e in j.get("events", []):
                self.hap_event_id += 1
                self.hap_events.append({"id": self.hap_event_id, "w": round(now - self.t0, 3), **e})

    # ---- views
    def tel_fps(self):
        w = list(self.fps_win)
        if len(w) < 2 or w[-1][0] - w[0][0] <= 0:
            return 0.0
        return (w[-1][1] - w[0][1]) / (w[-1][0] - w[0][0]) if w[-1][1] >= w[0][1] else 0.0

    def overview(self):
        fr, now = self.frame, time.time()
        o = {"now": round(now - self.t0, 3), "tel_live": bool(fr and now - self.frame_at < 0.5), "tel_frames": self.frames,
             "tel_src": self.tel_source.mode if self.tel_source else "off", "tel_version": self.tel_version, "short_dgrams": self.short_dgrams,
             "hap_live": bool(self.hap and now - self.hap_at < 0.5), "hap_count": self.hap_count,
             "hap_src": self.hap_source.mode if self.hap_source else "off", "game": self.game_info}
        if fr:
            dts = sorted(self.dt_hist)
            p, r, hd = angles(fr)
            o.update(frame={k: jsonable(fr[k]) for k in ("frame", "proxy_frame", "sim_time", "sim_dt", "dt", "step_count", "player_present", "speed",
                                                          "rpm", "gear", "gear_lever", "throttle", "steer", "handbrake", "health_pct", "engine_hp",
                                                          "engine_hp_max", "susp_hp", "susp_hp_max", "brake_hp", "brake_hp_max", "flags", "surface",
                                                          "state_timer", "weapon_row", "weapon_ammo", "weapon_name", "music_track", "event_hooks",
                                                          "sound_voices", "mass", "wheelbase", "front_track", "steer_gain", "ground_g", "clearance",
                                                          "drive_power", "engine_power", "ffb_present", "pos_0", "pos_1", "pos_2", "velocity_0",
                                                          "velocity_1", "velocity_2")},
                     armour=[fr["armour_%d" % k] for k in range(4)], armour_max=[fr["armour_max_%d" % k] for k in range(4)],
                     chassis=[fr["chassis_%d" % k] for k in range(4)], chassis_max=[fr["chassis_max_%d" % k] for k in range(4)],
                     wheels=[{k: jsonable(fr["wheel%d_%s" % (w, k)]) for k in ("present", "hp", "hp_max", "grip", "ground_speed", "susp_offset", "unloaded", "flat", "skid_active")} for w in range(6)],
                     angles=[round(p, 4), round(r, 4), round(hd, 4)], fps=round(self.tel_fps(), 1),
                     dt_p50=round(dts[len(dts) // 2], 2) if dts else None, dt_p99=round(dts[int(len(dts) * 0.99)], 2) if dts else None,
                     flags_str=i76tel.flags_str(fr["flags"]), gear_str=i76tel.GEARS.get(fr["gear"], str(fr["gear"])))
        return o

    def events_view(self):
        return {"count": dict(self.ev_count), "impacts": {"player": self.impacts["player"], "other": self.impacts["other"],
                                                          "by_source": dict(self.impacts["by_source"]), "player_hp": round(self.impacts["player_hp"], 1)},
                "damage_sides": self.damage_sides, "damage_zones": {str(k): v for k, v in self.damage_zones.items()}, "damage_other": self.damage_other,
                "shots": dict(self.shots), "explosions": list(self.explosions)[-20:], "explosion_names": dict(self.explosion_names),
                "sounds": dict(self.sounds.most_common(40)), "sounds_active": list(self.sounds_active.values())[-40:],
                "weapon_ui": dict(self.weapon_ui)}

    def snapshot(self, history=600):
        with self.lock:
            return {"overview": self.overview(), "samples": list(self.samples)[-history:], "events": list(self.events)[-300:],
                    "ev": self.events_view(), "trail": list(self.trail)[-800:], "markers": list(self.markers)[-100:],
                    "hap": self.hap, "hsamples": list(self.hsamples)[-history:], "hap_events": list(self.hap_events)[-200:],
                    "log": self.log.state(), "log_tail": self.log.tail(400),
                    "trainer": self.trainer.status() if self.trainer else None,
                    "logger": self.logger.status() if self.logger else None}

    def delta(self, cur):
        """what a stream client has not seen yet (cur = its cursors dict, updated in place)"""
        with self.lock:
            out = {"overview": self.overview()}
            out["samples"] = [s for s in self.samples if s["id"] > cur.get("s", 0)][-240:]
            out["events"] = [e for e in self.events if e["id"] > cur.get("e", 0)][-200:]
            out["hsamples"] = [s for s in self.hsamples if s["id"] > cur.get("h", 0)][-240:]
            out["hap_events"] = [e for e in self.hap_events if e["id"] > cur.get("he", 0)][-100:]
            out["log_tail"] = self.log.tail(200, after=cur.get("l", 0))
            cur["s"], cur["e"], cur["h"] = self.sample_id, self.event_id, self.hsample_id
            cur["he"] = self.hap_event_id
            if out["log_tail"]:
                cur["l"] = out["log_tail"][-1]["id"]
            if out["events"] or cur.get("ev_due", 0) <= time.time():
                out["ev"] = self.events_view()
                out["markers"] = list(self.markers)[-100:]
                cur["ev_due"] = time.time() + 1.0
            if self.hap is not None and self.hap_count != cur.get("hc"):
                out["hap"] = self.hap
                cur["hc"] = self.hap_count
            if cur.get("slow_due", 0) <= time.time():
                out["log"] = self.log.state()
                out["trail"] = list(self.trail)[-800:]
                cur["slow_due"] = time.time() + 1.0
            if self.trainer:
                out["trainer"] = self.trainer.status()
            if self.logger:
                out["logger"] = self.logger.status()
            return out
