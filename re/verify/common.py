r"""common.py - shared paths, the sandbox game's state readers and the functions.tsv loader for verify/*.

Everything here is read-only against the repository; the only files written are under verify\ and the two the
runner owns in the sandbox (game\.console-test.lock, game\STRLKUP.DLL + its .pretest backup).
"""
import bisect
import ctypes
import hashlib
import math
import os
import struct
import subprocess
import sys
import time

MAP = r"C:\Users\james\i76-map"
VERIFY = os.path.join(MAP, "verify")
TOOLS = os.path.join(MAP, "tools")
RUNS = os.path.join(VERIFY, "runs")
BATCHES = os.path.join(VERIFY, "batches")
SCENARIOS = os.path.join(VERIFY, "scenarios")
G = r"C:\Users\james\i76-uncap-lab\game"                     # the SANDBOX. Never the Downloads portable install.
EXE = "i76.exe"
NEWDLL = r"C:\Users\james\i76-everywhere\music-fix\Strlkup.dll"
TEL_DIR = r"C:\Users\james\i76-everywhere\tools\telemetry"
TRAINER_DIR = r"C:\Users\james\i76-everywhere\tools\trainer"       # i76trainer.py (Game.wr), i76tune.py (Tuner), tunables.json
FOCUS_PS1 = os.path.join(MAP, "captures", "014-framerate", "focus.ps1")   # dot-sources autotest\lib\focuslib.ps1
FUNCTIONS_TSV = os.path.join(MAP, "symbols", "functions.tsv")
REF_EXE = os.path.join(MAP, "ghidra", "i76_ref.exe")          # pristine image (md5 9a232dcc): functions.tsv addresses
LOCK = os.path.join(G, ".console-test.lock")

# class bss / data globals (subsystems/simclock.md, mission.md, camera.md)
FRAME_ADDR = 0x5a7e1c      # simclock_frame_count (u32)
TIME_ADDR = 0x5a7e74       # simclock_time (f32)
SIMDT_ADDR = 0x4fe420      # simclock_sim_dt, +8 simclock_dt
PLAY_MODE = 0x4fe534       # 1 driving, 2 paused, 4 map, 8 notepad, 0x10 menu, 0x20 cutscene / pre-start screen
CAM_CB = 0x4c2720          # camera controller callback; 0x48e190 while a mission script drives the camera
CAM_MODE = 0x4c2728        # camera_mode (globals.tsv; camera.md)
CAM_SCRIPT = 0x48e190
WORLD_PTR = 0x54a264       # [[0x54a264]] = player object, +0x70 its entity
TEXT_LO, TEXT_HI = 0x401000, 0x4bbe56

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32dll = ctypes.windll.user32


def md5_file(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


class Mem:
    """ReadProcessMemory wrapper over the game (PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)."""

    def __init__(self, pid):
        self.pid = pid
        self.h = k32.OpenProcess(0x0410, False, pid)
        if not self.h:
            raise OSError("OpenProcess(%d) failed: %d" % (pid, ctypes.get_last_error()))

    def rd(self, addr, n):
        b = ctypes.create_string_buffer(n)
        g = ctypes.c_size_t()
        ok = k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), b, n, ctypes.byref(g))
        return b.raw if ok and g.value == n else None

    def u32(self, a):
        b = self.rd(a, 4)
        return struct.unpack("<I", b)[0] if b else None

    def f32(self, a):
        b = self.rd(a, 4)
        return struct.unpack("<f", b)[0] if b else None

    def f64(self, a):
        b = self.rd(a, 8)
        return struct.unpack("<d", b)[0] if b else None

    def frame(self):
        return self.u32(FRAME_ADDR)

    def play_mode(self):
        return self.u32(PLAY_MODE)

    def player_object(self):
        p1 = self.u32(WORLD_PTR)
        return self.u32(p1) if p1 else None

    def entity(self):
        o = self.player_object()
        return self.u32(o + 0x70) if o else None

    def speed(self):
        e = self.entity()
        return self.f32(e + 0xac) if e else None

    def throttle(self):
        e = self.entity()
        return self.f32(e + 0xe4) if e else None

    def flags(self):
        e = self.entity()
        return self.u32(e + 0x454) if e else None

    def gear(self):
        """eng+0x08: 0 reverse, 1 neutral, 2/3/4 = 1st/2nd/3rd (eng = [[ent+0x3c4]+0x70])."""
        e = self.entity()
        if not e:
            return None
        o = self.u32(e + 0x3c4)
        eng = self.u32(o + 0x70) if o else None
        return self.u32(eng + 8) if eng else None

    def camera_scripted(self):
        return self.u32(CAM_CB) == CAM_SCRIPT

    def cam_mode(self):
        """camera_mode 0x4c2728 (camera.md: 0 cockpit, 1 chase/mounted, 2 binoculars, 3 overview, 4 target/enemy view,
        5 script, 6/7 orbit, 8 missile cam, 9 tunnel)."""
        return self.u32(CAM_MODE)

    def cam_cb(self):
        return self.u32(CAM_CB)

    def radar(self):
        """The player's radar block [[ent+0x434]+0x70] (entity_GetRadarTarget 0x4613f0 / entity_ToggleRadarRange 0x460db0;
        camera.md 'Radar data'): range index (+0: 0 = 100 m, 1 = 600 m), flags (+0xc: 1 on, 2 target view, 4 disabled,
        0x10 locked), locked contact (+0x54) and its object. None when the car has no radar."""
        e = self.entity()
        ro = self.u32(e + 0x434) if e else None
        rd = self.u32(ro + 0x70) if ro else None
        if not rd:
            return None
        fl = self.u32(rd + 0xc) or 0
        contact = self.u32(rd + 0x54) or 0
        return {"range": self.u32(rd), "flags": fl, "locked": bool(fl & 0x10), "target_view": bool(fl & 0x2),
                "contact": contact, "target": (self.u32(contact) or 0) if contact else 0}

    def airborne(self):
        f = self.flags()
        return None if f is None else bool(f & 0x4)

    def pos(self):
        """obj+0x40 world position (x, y up, z) as doubles, or None."""
        o = self.player_object()
        b = self.rd(o + 0x40, 24) if o else None
        return struct.unpack("<3d", b) if b else None

    def rot(self):
        """obj+0x18 rotation, 9 floats, rows right / up / forward (i76tel.h)."""
        o = self.player_object()
        b = self.rd(o + 0x18, 36) if o else None
        return struct.unpack("<9f", b) if b else None

    def heading(self):
        """atan2(forward.x, forward.z) in radians (i76tel.h's heading); bearing to a point is atan2(dx, dz) in the same frame."""
        r = self.rot()
        return math.atan2(r[6], r[8]) if r else None

    def engine(self):
        """eng = [[ent+0x3c4]+0x70] or None."""
        e = self.entity()
        o = self.u32(e + 0x3c4) if e else None
        return self.u32(o + 0x70) if o else None

    def wheel(self, slot):
        """wheel data = [[ent+0x3a8+4*slot]+0x70] or None (slots 0 1 2 3 4 5 = FL FR ML MR RL RR)."""
        e = self.entity()
        o = self.u32(e + 0x3a8 + 4 * slot) if e else None
        return self.u32(o + 0x70) if o else None

    def state(self):
        e = self.entity()
        return {"frame": self.frame(), "mode": self.play_mode(), "entity": ("0x%x" % e) if e else None,
                "speed": self.speed(), "gear": self.gear(), "flags": self.flags(), "cam_script": self.camera_scripted(),
                "sim_time": self.f32(TIME_ADDR)}

    def close(self):
        if self.h:
            k32.CloseHandle(self.h)
            self.h = None


def focus_game(pid, timeout=20):
    """Force the game window to the foreground (focuslib.ps1 via captures/014-framerate/focus.ps1). Returns the script's output."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", FOCUS_PS1, str(pid)],
                           capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()[-60:]
    except subprocess.TimeoutExpired:
        return "focus.ps1 timeout"


def wake_display():
    for dx in (5, -5):          # a sleeping monitor leaves Glide uninitialised (fr_probe, TEST-FRAMERATE)
        u32dll.mouse_event(0x0001, dx, 0, 0, 0)
        time.sleep(0.2)


# -------------------------------------------------------------------------------- keys (DirectInput scancodes)
# input.map is the only live binding file (i76-everywhere AGENTS.md): W throttle_up, S throttle_down (brake), A/D steer,
# X reverse_direction, Enter weapon_fire, 2..5 hardpoint2..5_fire (hardpoint1_fire has no key), I start_engine,
# Space e_brake, Tab weapon_cycle, F1..F10 preset views (gamekey.map).
KEYS = {
    "ESC": (0x1B, 0x01), "1": (0x31, 0x02), "2": (0x32, 0x03), "3": (0x33, 0x04), "4": (0x34, 0x05), "5": (0x35, 0x06),
    "6": (0x36, 0x07), "7": (0x37, 0x08), "8": (0x38, 0x09), "TAB": (0x09, 0x0F), "Q": (0x51, 0x10), "W": (0x57, 0x11),
    "E": (0x45, 0x12), "R": (0x52, 0x13), "T": (0x54, 0x14), "Y": (0x59, 0x15), "U": (0x55, 0x16), "I": (0x49, 0x17),
    "P": (0x50, 0x19), "ENTER": (0x0D, 0x1C), "A": (0x41, 0x1E), "S": (0x53, 0x1F), "D": (0x44, 0x20), "F": (0x46, 0x21),
    "G": (0x47, 0x22), "H": (0x48, 0x23), "K": (0x4B, 0x25), "LSHIFT": (0x10, 0x2A), "X": (0x58, 0x2D), "C": (0x43, 0x2E),
    "V": (0x56, 0x2F), "B": (0x42, 0x30), "N": (0x4E, 0x31), "M": (0x4D, 0x32), "SPACE": (0x20, 0x39),
    "F1": (0x70, 0x3B), "F2": (0x71, 0x3C), "F3": (0x72, 0x3D), "F4": (0x73, 0x3E), "F5": (0x74, 0x3F),
    "F6": (0x75, 0x40), "F7": (0x76, 0x41), "F8": (0x77, 0x42), "F9": (0x78, 0x43), "F10": (0x79, 0x44),
    "F11": (0x7A, 0x57), "F12": (0x7B, 0x58),
    # the "Grey" (extended, E0-prefixed) cluster: input.map binds pilot_glance_* to the bare GreyArrows, track_*/overview_* to
    # Shift+GreyArrow, zoom_factor/track_distance/overview_zoom to GreyPageUp/Down, zoom_factor_reset to GreyEnd
    "GREYUP": (0x26, 0x48, True), "GREYDOWN": (0x28, 0x50, True), "GREYLEFT": (0x25, 0x4B, True), "GREYRIGHT": (0x27, 0x4D, True),
    "GREYPGUP": (0x21, 0x49, True), "GREYPGDN": (0x22, 0x51, True), "GREYEND": (0x23, 0x4F, True), "GREYHOME": (0x24, 0x47, True),
}
KEYEVENTF_SCANCODE, KEYEVENTF_KEYUP, KEYEVENTF_EXTENDEDKEY = 0x0008, 0x0002, 0x0001


def _key(name):
    k = KEYS[name.upper()]
    vk, sc = k[0], k[1]
    return vk, sc, (KEYEVENTF_EXTENDEDKEY if len(k) > 2 and k[2] else 0)


def key_down(name):
    vk, sc, ext = _key(name)
    u32dll.keybd_event(vk, sc, KEYEVENTF_SCANCODE | ext, 0)


def key_up(name):
    vk, sc, ext = _key(name)
    u32dll.keybd_event(vk, sc, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP | ext, 0)


def key_tap(name, hold=0.08):
    key_down(name)
    time.sleep(hold)
    key_up(name)


# -------------------------------------------------------------------------------- functions.tsv
class Functions:
    """symbols\\functions.tsv rows with a containing-function lookup for return addresses."""

    def __init__(self, path=FUNCTIONS_TSV):
        self.rows = []
        self.path = path
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                p = line.rstrip("\n").split("\t")
                if p[0] == "addr":
                    self.header = p
                    continue
                self.rows.append({"addr": int(p[0], 16), "size": int(p[1]), "name": p[2], "status": p[3],
                                  "hookable": p[6] if len(p) > 6 else "", "subsystem": p[9] if len(p) > 9 else ""})
        self.rows.sort(key=lambda r: r["addr"])
        self.addrs = [r["addr"] for r in self.rows]
        self.by_addr = {r["addr"]: r for r in self.rows}
        self.md5 = md5_file(path)

    def containing(self, va):
        """The row whose [addr, addr+size) holds va, else None."""
        i = bisect.bisect_right(self.addrs, va) - 1
        if i < 0:
            return None
        r = self.rows[i]
        return r if r["addr"] <= va < r["addr"] + max(r["size"], 1) else None

    def name_for_ra(self, ra):
        r = self.containing(ra)
        if r:
            return "%s+0x%x" % (r["name"], ra - r["addr"])
        if TEXT_LO <= ra < TEXT_HI:
            return "unlisted_%08x" % ra
        return "other-module_%08x" % ra


def ensure_dirs():
    for d in (RUNS, BATCHES, SCENARIOS):
        os.makedirs(d, exist_ok=True)


def tools_path():
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    if TEL_DIR not in sys.path:
        sys.path.insert(0, TEL_DIR)


def trainer_path():
    """Make tools/trainer importable (i76trainer: Game with VM_WRITE; i76tune: Tuner + tunables.json)."""
    if TRAINER_DIR not in sys.path:
        sys.path.insert(0, TRAINER_DIR)
