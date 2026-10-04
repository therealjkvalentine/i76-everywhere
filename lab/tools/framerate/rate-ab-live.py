#!/usr/bin/env python3
"""rate-ab-live.py - the in-mission half of rate-ab.ps1's telemetry measurements (cactus2, airborne2, farengine, and the
PER-FRAME-AUDIT-2026-10-03 acceptance measures colldedupe / hazard / wmiss / airolls).

Run by rate-ab.ps1 inside proxy-run's -Run block: the sandbox game is in a mission with the i76-everywhere Strlkup
proxy loaded. It only RECORDS (raw frames, events, samples -> CSV); rate-ab-analyse.py judges afterwards, so a
capture can be re-analysed with a different classifier (memory rule: retain and re-mine raw captures).

    python rate-ab-live.py cactus    --pid P --mission a01 --out DIR\\TAG [--speed 15 --dist 30 --approaches 6]
    python rate-ab-live.py airborne  --pid P --out DIR\\TAG --seconds 20 [--place X Y Z SPEED] [--fixed-step 24]
    python rate-ab-live.py farengine --pid P --out DIR\\TAG --seconds 30 [--lift 800] [--dbg 0xADDR]
    python rate-ab-live.py ram       --pid P --mission t01 --out DIR\\TAG --dbg 0xADDR [--prefix b --dist 60 --approaches 6]
    python rate-ab-live.py hazard    --pid P --out DIR\\TAG --seconds 10 [--dbg 0xADDR] [--hazard auto|fire|oil]
    python rate-ab-live.py wmiss     --pid P --out DIR\\TAG --seconds 5 --dbg 0xADDR
    python rate-ab-live.py counters  --pid P --out DIR\\TAG --seconds 30 --dbg 0xADDR [--mission t01 --near --god]
    python rate-ab-live.py <any> --dry-run ...     # no game: parse the headers, load the ODEF, print the plan

What each one talks to
  Local\\I76Telemetry  (I76_TELEMETRY=1; i76-everywhere tools\\telemetry\\i76tel.h, parsed at run time): one
                      i76tel_frame_t per rendered frame - pose, rot[9], body rates, flags (0x4 airborne), step_count,
                      throttle - plus the event ring (I76TEL_EV_IMPACT).           cactus, airborne
  Local\\I76Trainer    (always on; tools\\trainer\\i76trn.h): TELEPORT one-shot = position + velocity written on the
                      game thread (an external poke can be undone by the render-interp restore), REPAIR one-shot,
                      FREEZE_POS hold.                                             cactus, airborne, farengine
  process memory      input block 0x5367CC (throttle; the engine refills it from the keyboard each frame, so the W key
                      is held as well), obj+0x18 rotation (airborne placement), the world position table 0x54E11C
                      (every vehicle, stride 0x20), the proxy debug block counter far_steps.

cactus     No steering and no steer calibration. The saguaro positions come from the mission's ODEF (level-objects.py).
           Per approach: take the car's own heading f, pick an unused saguaro C whose corridor along f is clear of
           every other ODEF object, TELEPORT to C - dist x f at rest, wait for the car to settle, re-place if the
           settled heading moved the line off the trunk, then TELEPORT in place with velocity speed x f and hold the
           throttle whenever the car is below the set speed, until 25 m past the trunk. A cactus is used once per
           mission load (a hit knocks it down).
airborne   Optional placement (rotation identity + TELEPORT with velocity +z, read back), then every telemetry frame
           for --seconds with W held. phys_dt = step_count / fixed-step rate under I76_FIXED_STEP, else sim_dt.
farengine  Lifts the player --lift m straight up with FREEZE_POS, so every AI car is beyond the camera far radius
           + 25 m and takes physics_StepVehicleFar from its first metre; samples the position table (+ far_steps)
           at ~50 Hz for --seconds; puts the player back.
ram        (colldedupe, audit F3) The cactus planner pointed at DURABLE objects. A saguaro is a class 4 breakable: the
           first contact knocks it off and unregisters it (i76-map physics.md), so it cannot show a repeated contact.
           Default targets are the mission's buildings (ODEF names b*, class 2 structures, hp 400), least-used first.
           Per ram: REPAIR, TELEPORT --dist m before the target centre along the car's own heading, settle, REPAIR,
           TELEPORT in place with velocity, governor to --speed until the first contact (a collision-class IMPACT
           event on the player, or g_idbg.coll_events advancing when the settle window showed no background
           contacts), then throttle off and --post s more. Every frame carries coll_events / coll_dups / tick20_n and
           the armour + chassis sum; the background rates of both counters (a pair resting in contact somewhere else
           in the level counts every frame) are measured over half a second at rest before each launch.
hazard     (audit F1) Finds a weapon definition whose ordnance is a fire patch (0x11) or an oil slick (0xc) in the
           mission's definition table (0x5d88d8; a01 loads Fire-Dropper with the vgoon1 cars, t01 Oil Slick with
           t01al01), checks that ordnance is registered (0x655280: an unregistered id reads slot -1), and points the
           player's dropper instance at it (instance +0x30 def index, +0x10 damage, +0x20 ammo; all read back, all
           restored). Car at rest: fire for --tap s (the row's hardpoint key, or weapon_fire with the row made
           primary), wait out the 2 s shooter immunity, look for contact in place and then in 0.5 m steps behind the
           drop pose, FREEZE_POS there and record --seconds (cut to the patch's 20 s life). REPAIR is posted every
           frame during the window so the car survives; damage is read from the IMPACT events' f3, not from hp.
wmiss      (audit F4) Sets the condition of one of the player's weapons (a row with a hardpoint key) to 0, holds that
           key --seconds, samples g_idbg.wmiss_req / wmiss_play / tick20_n, puts the condition back.
counters   (airolls, audit F5) Samples skid_rolls / horn_rolls / tick20_n for --seconds. --near moves the player
           beside the mission's own cars (ODEF names starting with the mission stem, away from the start) so the AI
           has a vehicle target off-road; --god holds the trainer god flag for the window.
Prints progress lines and, last, one JSON line {"status": ...} for rate-ab.ps1.
"""
import argparse, ctypes, importlib.util, json, math, mmap, os, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
DEF_TOOLS = r"C:\Users\james\i76-everywhere\tools"
DEF_GAME = os.path.normpath(os.path.join(HERE, "..", "..", "game"))

TRN_MAGIC = 0x43363749
TRN_FMT = "<I H H I I I I I i i 3d 3f I I I I I I I I 64s"      # i76trn_ctl_t, 168 bytes (trainer_live_test.py)
TRN = ("magic version size flags play_set play_clear req_seq cmd slot_index ammo_value pos0 pos1 pos2 vel0 vel1 vel2 "
       "ack_seq heartbeat applied player_present play_flags_now play_flags_saved faults cmd_result msg").split()
# one format code per NAME (3d / 3f expand to three), so an offset is the size of the codes before it. The table in
# trainer_live_test.py indexes the unexpanded tokens and is only right up to pos0 (its vel0 lands on heartbeat).
_CODES = [c for tok in TRN_FMT[1:].split() for c in ([tok[1:]] * int(tok[0]) if tok[0].isdigit() and tok[-1] != "s" else [tok])]
TRN_OFF = {n: struct.calcsize("<" + "".join(_CODES[:i])) for i, n in enumerate(TRN)}
TRN_SIZE = struct.calcsize(TRN_FMT)
assert len(_CODES) == len(TRN) and TRN_OFF["pos0"] == 36 and TRN_OFF["vel0"] == 60 and TRN_OFF["ack_seq"] == 72 and TRN_SIZE == 168
F_GOD, F_FREEZE_POS = 0x01, 0x10
CMD_REPAIR, CMD_TELEPORT = 1, 2
EV_SHOT, EV_EXPLOSION, EV_IMPACT = 1, 2, 3
CLS_ORDNANCE, CLS_EXPLOSION = 0x33, 0x34
FLAG_OIL = 0x400
FLAG_AIRBORNE = 0x4

IN_THROTTLE = 0x5367CC          # memlib.ps1 InThrottle (int, -128..127)
POS_TABLE, POS_STRIDE, POS_SLOTS = 0x54E11C, 0x20, 16
SIM_TIME, FRAME_COUNTER = 0x5A7E74, 0x5A7E1C
# strlkproxy.c g_idbg: 120-byte header, 16 x 112-byte ring, then DWORD counters in declaration order. This table is
# checked against the struct in the source by rate-ab-selftest.py (layout recomputed from the declaration).
DBG_NAMES = ("ping_req ping_play ping_frames flame_hits flame_dmg aifire_calls aifire_yes tick20_n dodge_calls dodge_yes "
             "mirror_draws far_steps hazard_impacts hazard_steps radar_turns wmiss_req wmiss_play skid_rolls horn_rolls "
             "coll_events coll_dups").split()
DBG_BASE = 1912
DBG = {n: DBG_BASE + 4 * i for i, n in enumerate(DBG_NAMES)}
DBG_END = DBG_BASE + 4 * len(DBG_NAMES)
DBG_FAR_STEPS = DBG["far_steps"]            # 1956
VK_W, VK_ENTER, VK_1 = 0x57, 0x0D, 0x31
# weapons (i76-map types/i76_runtime.h, subsystems/weapons.md)
P_PLAYER = 0x54A264                         # [[0x54a264]] = the local player's object
WREC, WREC_STRIDE, WREC_COUNT = 0x5BE4D8, 0x2C8, 0x5DA78C      # vehicle weapon records: +0 vehicle, +4 primary row, slots +0x58 + k x 0x58 (+0x50 instance index)
WINST, WINST_STRIDE, WINST_COUNT = 0x5AAB08, 0x4C, 0x5DA750    # instances: +0xc hp, +0x10 damage, +0x14 hp max, +0x20 ammo, +0x30 def index
WDEF, WDEF_STRIDE, WDEF_COUNT = 0x5D88D8, 0xD8, 0x5D88D4       # definitions: +0 name, +0x5c class, +0x60 damage, +0x64 hp, +0x70 rate, +0x80 ordnance id
ORD, ORD_STRIDE, ORD_COUNT, ORD_SLOTS = 0x655280, 0xD0, 0x5A810C, 20   # registered ordnance, +0 id
IN_FIRE, IN_HARDPOINT1 = 0x5367DB, 0x5367DE                    # held-key bytes: weapon_fire, hardpoint1..5_fire
ORD_FIRE, ORD_OIL = 0x11, 0x0C
HAZARD_LIFE, HAZARD_IMMUNITY = 20.0, 2.0    # gfirdrop / goilslck GDFC lifetime; the shooter's immunity to its own droppers


def say(*a):
    print(*a, flush=True)


def finish(obj):
    print(json.dumps(obj), flush=True)
    sys.exit(0)


# ---- pure helpers (unit-run by rate-ab-selftest.py) ----------------------------------------------------------------
def load_objects(mission, game=DEF_GAME, tools=DEF_TOOLS):
    """Every ODEF object of <mission>.msn as (name, x, y, z), via i76-everywhere tools\\level-objects.py."""
    spec = importlib.util.spec_from_file_location("level_objects", os.path.join(tools, "level-objects.py"))
    lo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lo)
    stem = os.path.splitext(mission)[0]
    for sub in ("ADDON", "miss16", "miss8", ""):
        p = os.path.join(game, sub, stem + ".msn")
        if os.path.exists(p):
            top, objs = lo.objects(p)
            if top is None:
                raise SystemExit("no ODEF in %s" % p)
            return p, [(nm.lower(), x, y, z) for nm, x, y, z, _o, _h in objs]
    raise SystemExit("mission file %s.msn not found under %s (ADDON, miss16, miss8)" % (stem, game))


def heading(fr):
    """Horizontal unit forward (fx, fz) from rot rows right/up/forward, or None when the car is not upright."""
    fx, fz, up_y = fr["rot_6"], fr["rot_8"], fr["rot_4"]
    n = math.hypot(fx, fz)
    if n < 0.5 or up_y < 0.8:
        return None
    return fx / n, fz / n


def corridor_clear(objs, ci, f, dist, overrun=25.0, cactus_clear=5.0, other_clear=20.0, prefix="nsaguar", small=(), ignore=()):
    """True when no other ODEF object sits beside the line from C - dist x f to C + overrun x f. Names starting with
    `prefix` or one of `small` need cactus_clear m, the rest other_clear m; names starting with one of `ignore` are
    not obstacles (flat road pieces)."""
    cx, cz = objs[ci][1], objs[ci][3]
    sx, sz = cx - dist * f[0], cz - dist * f[1]
    small = (prefix,) + tuple(small)
    for k, (nm, x, _y, z) in enumerate(objs):
        if k == ci or (ignore and nm.startswith(tuple(ignore))):
            continue
        along = (x - sx) * f[0] + (z - sz) * f[1]
        lat = abs((x - sx) * f[1] - (z - sz) * f[0])
        if -6.0 <= along <= dist + overrun and lat < (cactus_clear if nm.startswith(small) else other_clear):
            return False
    return True


def plan_approach(objs, used, pos, f, dist, prefix="nsaguar", **kw):
    """Nearest unused cactus (index) whose corridor along heading f is clear, and the start point; None when none."""
    cand = [k for k, o in enumerate(objs) if o[0].startswith(prefix) and k not in used]
    cand.sort(key=lambda k: (objs[k][1] - pos[0]) ** 2 + (objs[k][3] - pos[1]) ** 2)
    for k in cand:
        if corridor_clear(objs, k, f, dist, prefix=prefix, **kw):
            return k, (objs[k][1] - dist * f[0], objs[k][3] - dist * f[1])
    return None


RAM_SMALL = ("nsaguar", "s")      # saguaros and road signs (s*): thin, 5 m beside the line is enough
RAM_IGNORE = ("i",)               # i*: intersection / road pieces, flat


def is_target(name, prefixes, exclude=()):
    return name.startswith(tuple(prefixes)) and not (exclude and name.startswith(tuple(exclude)))


def plan_ram(objs, uses, pos, f, dist, prefixes, exclude=(), once=False, other_clear=15.0):
    """The least-used (then nearest) target whose corridor along heading f is clear up to the target itself, and the
    start point; None when none. once=True never reuses a target (breakables)."""
    cand = [k for k, o in enumerate(objs) if is_target(o[0], prefixes, exclude) and not (once and uses.get(k))]
    cand.sort(key=lambda k: (uses.get(k, 0), (objs[k][1] - pos[0]) ** 2 + (objs[k][3] - pos[1]) ** 2))
    for k in cand:
        if corridor_clear(objs, k, f, dist, overrun=0.0, other_clear=other_clear, small=RAM_SMALL, ignore=RAM_IGNORE):
            return k, (objs[k][1] - dist * f[0], objs[k][3] - dist * f[1])
    return None


def hp_sum(fr):
    """Armour + chassis over the four sides (telemetry frame)."""
    return sum(fr["armour_%d" % i] + fr["chassis_%d" % i] for i in range(4))


def pick_hazard_def(defs, ords, want):
    """The first definition whose ordnance id is wanted (in `want` order) and registered; None when none."""
    for o in want:
        for d in defs:
            if d["ordnance"] == o and o in ords:
                return d
    return None


def pick_dropper_row(rows, defs, target):
    """The player's row to fire: one that already carries the target definition, else a dropper (class 6), else the
    last row. Returns (row dict, reason) or (None, reason)."""
    by = {d["index"]: d for d in defs}
    for r in rows:
        if r["def_index"] == target["index"]:
            return r, "already mounted"
    for r in rows:
        if by.get(r["def_index"], {}).get("klass") == 6:
            return r, "dropper %r" % by[r["def_index"]]["name"]
    if rows:
        r = rows[-1]
        return r, "no dropper on the car: last row (%r)" % by.get(r["def_index"], {}).get("name", "?")
    return None, "no weapon rows"


def pick_wmiss_row(rows, primary):
    """A row with a hardpoint key bound in the sandbox input.map (rows 1..4 = keys 2..5), not the primary if possible."""
    cand = [r for r in rows if 1 <= r["row"] <= 4]
    cand.sort(key=lambda r: (r["row"] == primary, r["row"]))
    return cand[0] if cand else None


# ---- live plumbing --------------------------------------------------------------------------------------------------
class Tel:
    def __init__(self, tools):
        sys.path.insert(0, os.path.join(tools, "telemetry"))
        import i76tel
        self.h = h = i76tel.Header()
        self.decode = i76tel.decode_frame
        self.size = h.structs["i76tel_shm_t"][1]
        self.frame_off, self.ring_off = h.offset("i76tel_shm_t", "frame"), h.offset("i76tel_shm_t", "ring")
        self.ring = h.consts["I76TEL_RING"]
        self.m = None
        self.last_seq = self.last_ev = None
        self.lost = 0                                       # events that left the 64-entry ring between two reads

    def open(self, suffix=""):
        self.m = mmap.mmap(-1, self.size, tagname=self.h.consts["I76TEL_SHM_NAME"] + suffix)

    def next(self, timeout=1.0):
        """The next newly published frame and the events recorded since the previous call: (frame, [events]) or None."""
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            s0 = struct.unpack_from("<I", self.m, 0)[0]
            if s0 == 0 or s0 & 1 or s0 == self.last_seq:
                time.sleep(0.001)
                continue
            buf = self.m[:self.size]
            if struct.unpack_from("<I", self.m, 0)[0] != s0:
                continue
            self.last_seq = s0
            fr = self.decode(self.h, buf[self.frame_off:self.frame_off + self.h.frame_size])
            evs, ev_seq = [], fr["event_seq"]
            if self.last_ev is None:
                self.last_ev = ev_seq                       # history before the first read is not ours
            self.lost += max(0, ev_seq - self.ring - self.last_ev)
            for s in range(max(self.last_ev + 1, ev_seq - self.ring + 1), ev_seq + 1):
                o = self.ring_off + (s % self.ring) * self.h.event_size
                ev = dict(zip(self.h.event_names, struct.unpack_from(self.h.event_fmt, buf, o)))
                if ev["seq"] == s:
                    evs.append(ev)
            self.last_ev = ev_seq
            return fr, evs
        return None

    def frame(self, timeout=1.0):
        r = self.next(timeout)
        return r[0] if r else None


class Trn:
    def __init__(self, suffix=""):
        self.m = mmap.mmap(-1, TRN_SIZE, tagname="Local\\I76Trainer" + suffix)

    def rd(self):
        return dict(zip(TRN, struct.unpack_from(TRN_FMT, self.m, 0)))

    def live(self):
        """Magic plus a heartbeat that advances (a stale mapping outlives the game: stale-shared-memory trap)."""
        d = self.rd(); time.sleep(0.4)
        return d["magic"] == TRN_MAGIC and self.rd()["heartbeat"] != d["heartbeat"]

    def flags(self, f):
        struct.pack_into("<I", self.m, TRN_OFF["flags"], f)

    def set_pos(self, pos):
        struct.pack_into("<3d", self.m, TRN_OFF["pos0"], *pos)

    def cmd(self, c, pos=None, vel=(0.0, 0.0, 0.0)):
        seq = self.rd()["req_seq"] + 1
        if pos:
            self.set_pos(pos)
        struct.pack_into("<3f", self.m, TRN_OFF["vel0"], *vel)
        struct.pack_into("<I", self.m, TRN_OFF["cmd"], c)
        struct.pack_into("<I", self.m, TRN_OFF["req_seq"], seq)
        for _ in range(200):
            time.sleep(0.005)
            d = self.rd()
            if d["ack_seq"] == seq:
                return d["cmd_result"] == 0
        return False

    def post(self, c):
        """A one-shot without waiting for the acknowledgement (skipped while the previous one is still pending)."""
        d = self.rd()
        if d["ack_seq"] != d["req_seq"]:
            return False
        struct.pack_into("<I", self.m, TRN_OFF["cmd"], c)
        struct.pack_into("<I", self.m, TRN_OFF["req_seq"], d["req_seq"] + 1)
        return True


class Mem:
    def __init__(self, pid):
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = ctypes.c_void_p
        k.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        for fn in (k.ReadProcessMemory, k.WriteProcessMemory):
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
            fn.restype = ctypes.c_int
        self.k = k
        self.h = k.OpenProcess(0x38, 0, pid)                 # VM_OPERATION | VM_READ | VM_WRITE
        if not self.h:
            raise SystemExit("OpenProcess(%d) failed" % pid)

    def read(self, addr, n):
        buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t(0)
        if self.k.ReadProcessMemory(self.h, addr, buf, n, ctypes.byref(got)) and got.value == n:
            return buf.raw
        return None

    def write(self, addr, data):
        got = ctypes.c_size_t(0)
        return bool(self.k.WriteProcessMemory(self.h, addr, data, len(data), ctypes.byref(got))) and got.value == len(data)


class Throttle:
    """Full throttle: the input block (clobbered from the keyboard each frame, autotest README) AND the W key."""

    def __init__(self, mem, keys=True):
        self.mem, self.u, self.t, self.down, self.keys = mem, ctypes.windll.user32, 0.0, False, keys

    def hold(self):
        self.mem.write(IN_THROTTLE, struct.pack("<i", 127))
        now = time.perf_counter()
        if self.keys and now - self.t > 0.05:
            self.u.keybd_event(VK_W, self.u.MapVirtualKeyW(VK_W, 0), 0x8, 0)
            self.t, self.down = now, True

    def release(self):
        if self.down:
            self.u.keybd_event(VK_W, self.u.MapVirtualKeyW(VK_W, 0), 0x8 | 0x2, 0)
            self.down = False
        self.mem.write(IN_THROTTLE, struct.pack("<i", 0))


class Key:
    """A held key: the engine's held-key byte (refilled from the keyboard each frame) AND the real key."""

    def __init__(self, mem, vk, addr, keys=True):
        self.mem, self.vk, self.addr, self.keys = mem, vk, addr, keys
        self.u, self.t, self.down = ctypes.windll.user32, 0.0, False

    def hold(self):
        if self.addr:
            self.mem.write(self.addr, b"\x01")
        now = time.perf_counter()
        if self.keys and now - self.t > 0.05:
            self.u.keybd_event(self.vk, self.u.MapVirtualKeyW(self.vk, 0), 0x8, 0)
            self.t, self.down = now, True

    def release(self):
        if self.down:
            self.u.keybd_event(self.vk, self.u.MapVirtualKeyW(self.vk, 0), 0x8 | 0x2, 0)
            self.down = False
        if self.addr:
            self.mem.write(self.addr, b"\x00")


def rd_i32(mem, addr, default=0):
    b = mem.read(addr, 4)
    return struct.unpack("<i", b)[0] if b else default


def rd_u32(mem, addr, default=0):
    b = mem.read(addr, 4)
    return struct.unpack("<I", b)[0] if b else default


def wr_i32(mem, addr, v):
    """Write and read back (memory rule: verify the write landed)."""
    return mem.write(addr, struct.pack("<i", v)) and rd_i32(mem, addr, None) == v


def read_counters(mem, dbg):
    """Every g_idbg counter as {name: value}, or None when there is no debug block (stock set) or it cannot be read."""
    if not dbg:
        return None
    b = mem.read(dbg + DBG_BASE, DBG_END - DBG_BASE)
    return dict(zip(DBG_NAMES, struct.unpack("<%dI" % len(DBG_NAMES), b))) if b else None


def player_obj(mem):
    p = rd_u32(mem, P_PLAYER)
    return rd_u32(mem, p) if p else 0


def weapon_defs(mem):
    """The mission's weapon definitions. The count is read from 0x5d88d4; when that is not a plausible count the first
    32 slots are scanned instead. Only slots with a printable name and a weapon class 1..7 are returned."""
    n = rd_i32(mem, WDEF_COUNT)
    if not 1 <= n <= 64:
        n = 32
    out = []
    for i in range(n):
        b = mem.read(WDEF + i * WDEF_STRIDE, 0x88)
        if not b:
            break
        raw = b[:32].split(b"\0")[0]
        klass, damage, hp = struct.unpack_from("<3I", b, 0x5C)
        if not raw or any(c < 0x20 or c > 0x7E for c in raw) or not 1 <= klass <= 7:
            continue
        name = raw.decode("latin1")
        out.append({"index": i, "name": name, "klass": klass, "damage": damage, "hp": hp,
                    "rate": struct.unpack_from("<f", b, 0x70)[0], "ordnance": struct.unpack_from("<I", b, 0x80)[0]})
    return out


def ordnance_ids(mem):
    n = max(0, min(rd_i32(mem, ORD_COUNT), ORD_SLOTS))
    return [rd_i32(mem, ORD + i * ORD_STRIDE, -1) for i in range(n)]


def player_weapons(mem, obj):
    """(record address, primary row, [{row, index, inst, hp, damage, hp_max, ammo, def_index}]) of the player's car."""
    n = max(0, min(rd_i32(mem, WREC_COUNT), 150))
    ninst = max(0, min(rd_i32(mem, WINST_COUNT), 150))
    for i in range(n):
        rec = WREC + i * WREC_STRIDE
        if not obj or rd_u32(mem, rec) != obj:
            continue
        rows = []
        for row in range(5):
            idx = rd_i32(mem, rec + 0x58 + row * 0x58 + 0x50, -1)
            if not 0 <= idx < ninst:
                continue
            inst = WINST + idx * WINST_STRIDE
            b = mem.read(inst, WINST_STRIDE)
            if not b:
                continue
            hp, damage, hp_max = struct.unpack_from("<3I", b, 0x0C)
            rows.append({"row": row, "index": idx, "inst": inst, "hp": hp, "damage": damage, "hp_max": hp_max,
                         "ammo": struct.unpack_from("<i", b, 0x20)[0], "def_index": struct.unpack_from("<i", b, 0x30)[0]})
        return rec, rd_i32(mem, rec + 4, -1), rows
    return 0, -1, []


def fire_key(mem, rec, row, keys=True):
    """The key that fires `row`: its hardpoint key (rows 1..4 = keys 2..5 in the sandbox input.map), else weapon_fire
    (Enter) with the row made the record's primary. Returns (Key, description) or (None, why not)."""
    if 1 <= row <= 4:
        return Key(mem, VK_1 + row, IN_HARDPOINT1 + row, keys), "hardpoint%d_fire (key %d)" % (row + 1, row + 1)
    if not wr_i32(mem, rec + 4, row):
        return None, "could not make row %d the primary" % row
    return Key(mem, VK_ENTER, IN_FIRE, keys), "weapon_fire (Enter), row %d made primary" % row


def wait_live(tel, seconds=10.0):
    """A telemetry frame with a player and a publish counter that advances."""
    end = time.perf_counter() + seconds
    first = None
    while time.perf_counter() < end:
        fr = tel.frame(0.5)
        if fr and fr["magic"] == tel.h.consts["I76TEL_MAGIC"] and fr["player_present"]:
            if first is None:
                first = fr["seq"]
            elif fr["seq"] != first:
                return fr
    return None


def settle(tel, quiet=0.4, timeout=6.0):
    """Wait until the car has been on the ground and slower than 0.7 m/s for `quiet` s. Returns (frame, settled)."""
    end = time.perf_counter() + timeout
    since, fr = None, None
    while time.perf_counter() < end:
        got = tel.frame(1.0)
        if got is None:
            break
        fr = got
        if not (fr["flags"] & FLAG_AIRBORNE) and fr["speed"] < 0.7:
            since = since or time.perf_counter()
            if time.perf_counter() - since >= quiet:
                return fr, True
        else:
            since = None
    return fr, False


def writer(path, cols):
    f = open(path, "w", encoding="utf-8", newline="\n")
    f.write(",".join(cols) + "\n")
    return f


def cell(v):
    return ("%.6g" % v) if isinstance(v, float) else str(v)


# ---- cactus -----------------------------------------------------------------------------------------------------------
CACTUS_COLS = ("approach t seq frame proxy_frame step_count sim_dt x y z speed vx vy vz flags throttle "
               "tx tz fx fz v_set target").split()
EVENT_COLS = "approach t seq frame type f0 f1 f2 f3 i0 i1".split()


def acquire(tel, thr, seconds=20.0):
    """Tap W until a held W shows as applied throttle > 0.5 (a01's scripted start hold yields to taps, not to a hold)."""
    u = ctypes.windll.user32
    sc = u.MapVirtualKeyW(VK_W, 0)
    end = time.perf_counter() + seconds
    taps = 0
    while time.perf_counter() < end:
        t1 = time.perf_counter() + 0.4
        best = -9.0
        while time.perf_counter() < t1:
            thr.hold()
            fr = tel.frame(0.2)
            if fr:
                best = max(best, fr["throttle"])
        thr.release()
        if best > 0.5:
            return True, taps
        for _ in range(8 if thr.keys else 0):
            u.keybd_event(VK_W, sc, 0x8, 0); time.sleep(0.07)
            u.keybd_event(VK_W, sc, 0x8 | 0x2, 0); time.sleep(0.09)
            taps += 1
    return False, taps


def run_cactus(a):
    path, objs = load_objects(a.mission, a.game, a.tools)
    ncact = sum(1 for o in objs if o[0].startswith(a.prefix))
    say("  %s: %d objects, %d %s*" % (path, len(objs), ncact, a.prefix))
    if a.dry_run:
        f = (1.0, 0.0)
        used, pos, n = set(), (objs[0][1], objs[0][3]), 0
        for _ in range(a.approaches):
            p = plan_approach(objs, used, pos, f, a.dist, prefix=a.prefix)
            if not p:
                break
            k, s = p; used.add(k); n += 1
            pos = (objs[k][1] + 25 * f[0], objs[k][3] + 25 * f[1])
            say("  [dry-run] approach %d: cactus #%d at (%.1f, %.1f), start (%.1f, %.1f), heading +x, %.0f m at %.0f m/s"
                % (n, k, objs[k][1], objs[k][3], s[0], s[1], a.dist, a.speed))
        Tel(a.tools)
        finish({"status": "dry-run", "cacti": ncact, "planned": n, "trainer_block_bytes": TRN_SIZE})
    if not ncact:
        finish({"status": "no %s objects in %s" % (a.prefix, a.mission)})
    tel = Tel(a.tools); tel.open(a.shm_suffix)
    trn, mem = Trn(a.shm_suffix), Mem(a.pid)
    if not wait_live(tel):
        finish({"status": "no live telemetry (I76_TELEMETRY=1 and a mission needed)"})
    if not trn.live():
        finish({"status": "trainer block not live (magic / heartbeat)"})
    thr = Throttle(mem, not a.no_keys)
    ff = writer(a.out + ".frames.csv", CACTUS_COLS)
    ef = writer(a.out + ".events.csv", EVENT_COLS)
    t0 = time.perf_counter()
    used, done, notes, acquired = set(), 0, [], False
    try:
        acquired, taps = acquire(tel, thr, a.acquire)
        say("  control %s after %d taps" % ("acquired" if acquired else "NOT acquired (the velocity write still launches the car)", taps))
        for n in range(1, a.approaches + 1):
            trn.cmd(CMD_REPAIR)
            fr, _ok = settle(tel, timeout=4.0)
            f = heading(fr) if fr else None
            if not f:
                notes.append("approach %d: car not upright" % n); break
            placed = None
            for attempt in range(4):
                p = plan_approach(objs, used, (fr["pos_0"], fr["pos_2"]), f, a.dist, prefix=a.prefix)
                if not p:
                    break
                k, s = p
                c = objs[k]
                near = math.hypot(fr["pos_0"] - s[0], fr["pos_2"] - s[1]) < 400.0
                y = (max(c[2], fr["pos_1"]) if near else c[2]) + a.lift
                if not trn.cmd(CMD_TELEPORT, (s[0], y, s[1])):
                    notes.append("approach %d: teleport not acknowledged" % n); break
                fr, settled = settle(tel)
                if not fr:
                    break
                f2 = heading(fr)
                if not f2:
                    notes.append("approach %d: not upright after placement" % n); break
                rx, rz = c[1] - fr["pos_0"], c[3] - fr["pos_2"]
                along, lat = rx * f2[0] + rz * f2[1], rx * f2[1] - rz * f2[0]
                if abs(lat) <= 0.25 and along > 0.6 * a.dist and corridor_clear(objs, k, f2, a.dist, prefix=a.prefix):
                    placed = (k, c, f2, settled, along, lat)
                    break
                f = f2                                       # the settled heading moved the line: plan again along it
            if not placed:
                notes.append("approach %d: no placement (no clear cactus, or the line would not hold)" % n)
                break
            k, c, f, settled, along, lat = placed
            used.add(k)
            say("  approach %d: cactus #%d (%.1f, %.1f) from %.1f m, lateral %.2f m, settled=%s" % (n, k, c[1], c[3], along, lat, settled))
            if not trn.cmd(CMD_TELEPORT, (fr["pos_0"], fr["pos_1"] + 0.02, fr["pos_2"]), (a.speed * f[0], 0.0, a.speed * f[1])):
                notes.append("approach %d: launch not acknowledged" % n); break
            ta = time.perf_counter()
            slow_since, boosted, rows, spd = None, False, 0, a.speed
            while time.perf_counter() - ta < a.timeout:
                # governor, as cactus-gauntlet.ps1: throttle only below the set speed. The pass-through rate depends on
                # speed (MEASUREMENTS.md: 67% hits at 15 m/s, 20% at 21), so the arrival speed must not drift with the condition
                if spd < a.speed:
                    thr.hold()
                else:
                    thr.release()
                got = tel.next(1.0)
                if got is None:
                    notes.append("approach %d: telemetry stalled" % n); break
                fr, evs = got
                spd = fr["speed"]
                t = time.perf_counter() - t0
                ff.write(",".join(cell(v) for v in (
                    n, t, fr["seq"], fr["frame"], fr["proxy_frame"], fr["step_count"], fr["sim_dt"], fr["pos_0"], fr["pos_1"],
                    fr["pos_2"], fr["speed"], fr["velocity_0"], fr["velocity_1"], fr["velocity_2"], fr["flags"], fr["throttle"],
                    c[1], c[3], f[0], f[1], a.speed, k)) + "\n")
                rows += 1
                for ev in evs:
                    ef.write(",".join(cell(v) for v in (n, t, ev["seq"], ev["frame"], ev["type"], ev["f_0"], ev["f_1"],
                                                         ev["f_2"], ev["f_3"], ev["i_0"], ev["i_1"])) + "\n")
                al = (fr["pos_0"] - c[1]) * f[0] + (fr["pos_2"] - c[3]) * f[1]
                if a.relaunch_at > 0 and not boosted and al >= -a.relaunch_at:
                    boosted = True                           # optional: restore the set speed just before the trunk
                    trn.cmd(CMD_TELEPORT, (fr["pos_0"], fr["pos_1"], fr["pos_2"]), (a.speed * f[0], fr["velocity_1"], a.speed * f[1]))
                if al > a.overrun:
                    break
                if al > -5.0 and fr["speed"] < 1.0:          # stopped at the trunk: a hit, no need to wait out the timeout
                    slow_since = slow_since or time.perf_counter()
                    if time.perf_counter() - slow_since > 1.0:
                        break
                else:
                    slow_since = None
            thr.release()
            done += 1
            say("    %d frames recorded" % rows)
    finally:
        thr.release(); ff.close(); ef.close()
    finish({"status": "ok" if done else "no-approaches (%s)" % "; ".join(notes or ["none planned"]), "approaches": done,
            "acquired": acquired, "notes": notes, "cacti": ncact})


# ---- airborne ---------------------------------------------------------------------------------------------------------
AIR_COLS = ("t seq frame proxy_frame step_count sim_time sim_dt dt phys_dt flags x y z r0 r1 r2 r3 r4 r5 r6 r7 r8 "
            "pitch_rate yaw_rate roll_rate vx vy vz speed throttle clearance").split()


def run_airborne(a):
    if a.dry_run:
        Tel(a.tools)
        say("  [dry-run] place %s, record %d s of telemetry frames (phys_dt = step_count / %s)" %
            (a.place or "nothing", a.seconds, a.fixed_step or "- (stock: sim_dt)"))
        finish({"status": "dry-run", "columns": len(AIR_COLS)})
    tel = Tel(a.tools); tel.open(a.shm_suffix)
    trn, mem = Trn(a.shm_suffix), Mem(a.pid)
    fr = wait_live(tel)
    if not fr:
        finish({"status": "no live telemetry (I76_TELEMETRY=1 and a mission needed)"})
    placed_dz, placed_ok = None, None
    if a.place:
        if not trn.live():
            finish({"status": "trainer block not live (magic / heartbeat)"})
        x, y, z, v = a.place
        ident = struct.pack("<9f", 1, 0, 0, 0, 1, 0, 0, 0, 1)   # right +x, up +y, forward +z (ramp A)
        for attempt in range(3):
            for _ in range(6):                                # a write inside the render window is undone by the interp restore
                mem.write(fr["obj_addr"] + 0x18, ident); time.sleep(0.012)
            ack = trn.cmd(CMD_TELEPORT, (x, y, z), (0.0, 0.0, v))
            for _ in range(3):
                fr = tel.frame(1.0) or fr
            placed_dz = round(fr["pos_2"] - z, 2)
            placed_ok = bool(ack and fr["rot_8"] > 0.99 and abs(fr["pos_0"] - x) < 3.0 and -1.0 < placed_dz < v * 0.5 + 5.0)
            if placed_ok:
                break
        say("  placed at (%.0f, %.0f, %.0f) %.0f m/s: read-back dz=%.2f m, forward.z=%.3f, ok=%s" % (x, y, z, v, placed_dz, fr["rot_8"], placed_ok))
    thr = Throttle(mem, not a.no_keys)
    out = writer(a.out + ".csv", AIR_COLS)
    rate = float(a.fixed_step) if a.fixed_step else 0.0
    n = air = 0
    t0 = time.perf_counter()
    try:
        while time.perf_counter() - t0 < a.seconds:
            thr.hold()
            got = tel.next(1.0)
            if got is None:
                break
            fr = got[0]
            if not fr["player_present"]:
                continue
            sc = fr["step_count"]
            phys = (sc / rate if sc >= 0 else float("nan")) if rate else fr["sim_dt"]
            out.write(",".join(cell(v) for v in (
                time.perf_counter() - t0, fr["seq"], fr["frame"], fr["proxy_frame"], sc, fr["sim_time"], fr["sim_dt"], fr["dt"], float(phys),
                fr["flags"], fr["pos_0"], fr["pos_1"], fr["pos_2"], *[fr["rot_%d" % i] for i in range(9)],
                fr["pitch_rate"], fr["yaw_rate"], fr["roll_rate"], fr["velocity_0"], fr["velocity_1"], fr["velocity_2"],
                fr["speed"], fr["throttle"], fr["clearance"])) + "\n")
            n += 1
            air += bool(fr["flags"] & FLAG_AIRBORNE)
    finally:
        thr.release(); out.close()
    finish({"status": "ok" if n else "no-frames", "frames": n, "airborne_frames": air, "placed_dz": placed_dz, "placed_ok": placed_ok})


# ---- farengine --------------------------------------------------------------------------------------------------------
FAR_COLS = "t frame sim_time far_steps slot x y z".split()


def read_slots(mem):
    b = mem.read(POS_TABLE, POS_STRIDE * POS_SLOTS)
    out = []
    if not b:
        return out
    for i in range(POS_SLOTS):
        x, y, z = struct.unpack_from("<3f", b, i * POS_STRIDE)
        if x == x and z == z and (abs(x) > 0.01 or abs(z) > 0.01):
            out.append((i, x, y, z))
    return out


def run_farengine(a):
    if a.dry_run:
        say("  [dry-run] FREEZE_POS %d m above the start, sample 0x%X (%d slots) for %d s, far_steps at debug block + %d"
            % (a.lift, POS_TABLE, POS_SLOTS, a.seconds, DBG_FAR_STEPS))
        finish({"status": "dry-run", "trainer_block_bytes": TRN_SIZE})
    mem = Mem(a.pid)
    dbg = int(a.dbg, 0) if a.dbg else 0
    slots = read_slots(mem)
    me = next((s for s in slots if s[0] == 0), None)
    if not me:
        finish({"status": "no player in the position table"})
    trn, lifted = None, None
    if a.lift > 0:
        trn = Trn(a.shm_suffix)
        if not trn.live():
            finish({"status": "trainer block not live (magic / heartbeat)"})
        trn.set_pos((me[1], me[2] + a.lift, me[3]))
        trn.flags(F_FREEZE_POS)
        time.sleep(0.5)
        now = next((s for s in read_slots(mem) if s[0] == 0), me)
        lifted = round(now[2] - me[2], 1)                    # read back: did the hold land?
        say("  player held %.1f m above (%.0f, %.0f, %.0f); %d other live slots" % (lifted, me[1], me[2], me[3], len(slots) - 1))
    out = writer(a.out + ".csv", FAR_COLS)
    n = 0
    t0 = time.perf_counter()
    try:
        while time.perf_counter() - t0 < a.seconds:
            t = time.perf_counter() - t0
            hdr = mem.read(FRAME_COUNTER, 4), mem.read(SIM_TIME, 4), (mem.read(dbg + DBG_FAR_STEPS, 4) if dbg else None)
            frame = struct.unpack("<i", hdr[0])[0] if hdr[0] else -1
            st = struct.unpack("<f", hdr[1])[0] if hdr[1] else float("nan")
            fs = struct.unpack("<I", hdr[2])[0] if hdr[2] else ""
            for i, x, y, z in read_slots(mem):
                out.write("%.4f,%d,%.4f,%s,%d,%.3f,%.3f,%.3f\n" % (t, frame, st, fs, i, x, y, z))
            n += 1
            time.sleep(0.02)
    finally:
        out.close()
        if trn:
            trn.flags(0)
            trn.cmd(CMD_TELEPORT, (me[1], me[2] + 1.0, me[3]))
    finish({"status": "ok" if n else "no-samples", "samples": n, "lifted_m": lifted, "live_slots": len(slots)})


# ---- ram (colldedupe) -------------------------------------------------------------------------------------------------
RAM_COLS = ("ram t seq frame proxy_frame step_count sim_dt x y z speed flags throttle hp coll_events coll_dups tick20_n "
            "tx tz fx fz v_set dist bg_s bg_dups_s target name").split()
HEADINGS8 = [(math.sin(math.radians(d)), math.cos(math.radians(d))) for d in range(0, 360, 45)]


def cnt(c, name):
    return c[name] if c else ""


def upright(mem, trn, tel, fr):
    """A car on its side or roof back on its wheels: identity rotation (as the airborne placement) and a 1 m drop."""
    ident = struct.pack("<9f", 1, 0, 0, 0, 1, 0, 0, 0, 1)
    for _ in range(6):
        mem.write(fr["obj_addr"] + 0x18, ident); time.sleep(0.012)
    trn.cmd(CMD_TELEPORT, (fr["pos_0"], fr["pos_1"] + 1.0, fr["pos_2"]))
    return settle(tel)[0]


def run_ram(a):
    prefixes = tuple(x for x in a.prefix.lower().split(",") if x)
    exclude = tuple(x for x in a.exclude.lower().split(",") if x)
    path, objs = load_objects(a.mission, a.game, a.tools)
    targets = [o for o in objs if is_target(o[0], prefixes, exclude)]
    say("  %s: %d objects, %d targets (%s)" % (path, len(objs), len(targets), ", ".join(sorted({o[0] for o in targets})) or "none"))
    if a.dry_run:
        start = next((o for o in objs if o[0].startswith("vp")), objs[0])
        ok = 0
        for f in HEADINGS8:
            uses, pos, names = {}, (start[1], start[3]), []
            for _ in range(a.approaches):
                p = plan_ram(objs, uses, pos, f, a.dist, prefixes, exclude, a.once, a.clear)
                if not p:
                    break
                uses[p[0]] = uses.get(p[0], 0) + 1
                names.append(objs[p[0]][0]); pos = (objs[p[0]][1], objs[p[0]][3])
            ok += bool(names)
            say("  [dry-run] heading (%+.2f, %+.2f): %d of %d rams planned from %.0f m at %.0f m/s: %s"
                % (f[0], f[1], len(names), a.approaches, a.dist, a.speed, " ".join(names) or "-"))
        Tel(a.tools)
        finish({"status": "dry-run", "targets": len(targets), "headings_ok": ok, "trainer_block_bytes": TRN_SIZE})
    if not targets:
        finish({"status": "no %s objects in %s" % (a.prefix, a.mission)})
    tel = Tel(a.tools); tel.open(a.shm_suffix)
    trn, mem = Trn(a.shm_suffix), Mem(a.pid)
    if not wait_live(tel):
        finish({"status": "no live telemetry (I76_TELEMETRY=1 and a mission needed)"})
    if not trn.live():
        finish({"status": "trainer block not live (magic / heartbeat)"})
    dbg = int(a.dbg, 0) if a.dbg else 0
    if dbg and read_counters(mem, dbg) is None:
        finish({"status": "debug block unreadable at %s" % a.dbg})
    thr = Throttle(mem, not a.no_keys)
    ff = writer(a.out + ".frames.csv", RAM_COLS)
    ef = writer(a.out + ".events.csv", EVENT_COLS)
    t0 = time.perf_counter()
    uses, done, contacts, notes, acquired = {}, 0, 0, [], False
    try:
        acquired, taps = acquire(tel, thr, a.acquire)
        say("  control %s after %d taps" % ("acquired" if acquired else "NOT acquired (the velocity write still launches the car)", taps))
        for n in range(1, a.approaches + 1):
            trn.cmd(CMD_REPAIR)
            fr, _ok = settle(tel, timeout=4.0)
            f = heading(fr) if fr else None
            if fr and not f:
                fr = upright(mem, trn, tel, fr)
                f = heading(fr) if fr else None
            if not f:
                notes.append("ram %d: car not upright" % n); break
            placed = None
            for attempt in range(4):
                p = plan_ram(objs, uses, (fr["pos_0"], fr["pos_2"]), f, a.dist, prefixes, exclude, a.once, a.clear)
                if not p:
                    break
                k, s = p
                c = objs[k]
                near = math.hypot(fr["pos_0"] - s[0], fr["pos_2"] - s[1]) < 400.0
                y = (max(c[2], fr["pos_1"]) if near else c[2]) + a.lift
                if not trn.cmd(CMD_TELEPORT, (s[0], y, s[1])):
                    notes.append("ram %d: teleport not acknowledged" % n); break
                fr, settled = settle(tel)
                if not fr:
                    break
                f2 = heading(fr)
                if not f2:
                    fr = upright(mem, trn, tel, fr)
                    f2 = heading(fr) if fr else None
                    if not f2:
                        notes.append("ram %d: not upright after placement" % n); break
                rx, rz = c[1] - fr["pos_0"], c[3] - fr["pos_2"]
                along, lat = rx * f2[0] + rz * f2[1], rx * f2[1] - rz * f2[0]
                if abs(lat) <= a.lat_tol and along > 0.6 * a.dist and corridor_clear(
                        objs, k, f2, a.dist, overrun=0.0, other_clear=a.clear, small=RAM_SMALL, ignore=RAM_IGNORE):
                    placed = (k, c, f2, settled, along, lat)
                    break
                f = f2                                       # the settled heading moved the line: plan again along it
            if not placed:
                notes.append("ram %d: no placement (no target with a clear corridor, or the line would not hold)" % n)
                break
            k, c, f, settled, along, lat = placed
            uses[k] = uses.get(k, 0) + 1
            trn.cmd(CMD_REPAIR)
            # background contacts: the counter over a quiet half second at rest (another car scraping something
            # elsewhere counts too: physics_CollideAll is global). Only a silent background lets the counter end a ram.
            c1, tq = read_counters(mem, dbg), time.perf_counter()
            while time.perf_counter() - tq < 0.5:
                fr = tel.frame(0.5) or fr
            c2 = read_counters(mem, dbg)
            bg = (c2["coll_events"] - c1["coll_events"]) / (time.perf_counter() - tq) if c1 and c2 else None
            bgd = (c2["coll_dups"] - c1["coll_dups"]) / (time.perf_counter() - tq) if c1 and c2 else None
            say("  ram %d: %s #%d (%.1f, %.1f) from %.1f m, lateral %.2f m, settled=%s, background %s contacts/s"
                % (n, c[0], k, c[1], c[3], along, lat, settled, "-" if bg is None else "%.1f" % bg))
            tel.next(0.5)                                    # events up to here are not this ram's
            if not trn.cmd(CMD_TELEPORT, (fr["pos_0"], fr["pos_1"] + 0.02, fr["pos_2"]), (a.speed * f[0], 0.0, a.speed * f[1])):
                notes.append("ram %d: launch not acknowledged" % n); break
            ta = time.perf_counter()
            contact_t, ce0, rows, spd, slow_since = None, None, 0, a.speed, None
            while time.perf_counter() - ta < a.timeout:
                if contact_t is None and spd < a.speed:      # governor until the contact, then hands off
                    thr.hold()
                else:
                    thr.release()
                got = tel.next(1.0)
                if got is None:
                    notes.append("ram %d: telemetry stalled" % n); break
                fr, evs = got
                spd = fr["speed"]
                t = time.perf_counter() - t0
                cc = read_counters(mem, dbg)
                if ce0 is None and cc:
                    ce0 = cc["coll_events"]
                ff.write(",".join(cell(v) for v in (
                    n, t, fr["seq"], fr["frame"], fr["proxy_frame"], fr["step_count"], fr["sim_dt"], fr["pos_0"], fr["pos_1"],
                    fr["pos_2"], fr["speed"], fr["flags"], fr["throttle"], hp_sum(fr), cnt(cc, "coll_events"), cnt(cc, "coll_dups"),
                    cnt(cc, "tick20_n"), c[1], c[3], f[0], f[1], a.speed, a.dist, "" if bg is None else bg, "" if bgd is None else bgd, k, c[0])) + "\n")
                rows += 1
                for ev in evs:
                    ef.write(",".join(cell(v) for v in (n, t, ev["seq"], ev["frame"], ev["type"], ev["f_0"], ev["f_1"],
                                                         ev["f_2"], ev["f_3"], ev["i_0"], ev["i_1"])) + "\n")
                if contact_t is None:
                    hit = any(ev["type"] == EV_IMPACT and ev["i_0"] and ev["i_1"] not in (0, CLS_ORDNANCE, CLS_EXPLOSION) for ev in evs)
                    if not hit and cc and bg == 0 and cc["coll_events"] > ce0:
                        hit = True
                    if hit:
                        contact_t = time.perf_counter(); contacts += 1
                        thr.release()
                        continue
                    al = (fr["pos_0"] - c[1]) * f[0] + (fr["pos_2"] - c[3]) * f[1]
                    if al > a.overrun:                       # through the target's centre without a contact
                        break
                    if fr["speed"] < 1.0 and time.perf_counter() - ta > 2.0:
                        slow_since = slow_since or time.perf_counter()
                        if time.perf_counter() - slow_since > 1.5:
                            break                            # stopped without a contact signal: the analyser will say so
                    else:
                        slow_since = None
                elif time.perf_counter() - contact_t >= a.post:
                    break
            thr.release()
            done += 1
            say("    %d frames recorded, contact %s" % (rows, "seen" if contact_t else "NOT seen"))
    finally:
        thr.release(); ff.close(); ef.close()
    finish({"status": "ok" if done else "no-rams (%s)" % "; ".join(notes or ["none planned"]), "rams": done, "contacts": contacts,
            "acquired": acquired, "notes": notes, "targets": len(targets), "events_lost": tel.lost})


# ---- hazard -------------------------------------------------------------------------------------------------------------
HAZ_COLS = ("phase t seq frame proxy_frame step_count sim_dt x y z speed flags hp ammo hazard_impacts hazard_steps "
            "tick20_n offset").split()
HAZ_EVENT_COLS = "phase t seq frame type f0 f1 f2 f3 i0 i1".split()


def run_hazard(a):
    want = {"fire": (ORD_FIRE,), "oil": (ORD_OIL,), "auto": (ORD_FIRE, ORD_OIL)}[a.hazard]
    if a.dry_run:
        Tel(a.tools)
        say("  [dry-run] look for a weapon definition with ordnance %s in 0x%X (stride 0x%X) and that id in 0x%X; point the "
            "player's dropper row at it (instance +0x30 / +0x10 / +0x20, read back)" % ("/".join("0x%x" % o for o in want), WDEF, WDEF_STRIDE, ORD))
        say("  [dry-run] fire %.2f s at rest, wait %.1f s (shooter immunity), search 0..%.1f m behind in 0.5 m steps (%.2f s each), "
            "FREEZE_POS, record %d s (patch life %.0f s)" % (a.tap, HAZARD_IMMUNITY, a.search, a.dwell, a.seconds, HAZARD_LIFE))
        finish({"status": "dry-run", "columns": len(HAZ_COLS), "trainer_block_bytes": TRN_SIZE})
    tel = Tel(a.tools); tel.open(a.shm_suffix)
    trn, mem = Trn(a.shm_suffix), Mem(a.pid)
    fr = wait_live(tel)
    if not fr:
        finish({"status": "no live telemetry (I76_TELEMETRY=1 and a mission needed)"})
    if not trn.live():
        finish({"status": "trainer block not live (magic / heartbeat)"})
    dbg = int(a.dbg, 0) if a.dbg else 0
    obj = player_obj(mem) or fr["obj_addr"]
    defs, ords = weapon_defs(mem), ordnance_ids(mem)
    say("  definitions: " + " | ".join("%d %r class %d ord 0x%x" % (d["index"], d["name"], d["klass"], d["ordnance"]) for d in defs))
    say("  ordnance registered: " + " ".join("0x%x" % o for o in ords))
    rec, primary, rows = player_weapons(mem, obj)
    target = pick_hazard_def(defs, ords, want)
    if not target:
        finish({"status": "no fire patch / oil slick definition loaded in this mission (wanted ordnance %s; %d definitions, see the log)"
                % ("/".join("0x%x" % o for o in want), len(defs))})
    row, why = pick_dropper_row(rows, defs, target)
    if not row:
        finish({"status": "no weapon row on the player's car (%s)" % why})
    inst = row["inst"]
    key, kdesc = fire_key(mem, rec, row["row"], not a.no_keys)
    if not key:
        finish({"status": kdesc})
    ammo0 = row["ammo"] if row["ammo"] >= 500 else 500
    # the Fire-Dropper's 15 hp x difficulty per round per step would wreck the car between two REPAIRs once a few rounds
    # lie under it; a smaller per-hit damage keeps it alive and the per-round rates are the same
    dmg = min(target["damage"], a.hazard_damage) if a.hazard_damage > 0 else target["damage"]
    swapped = row["def_index"] != target["index"]

    def restore():
        ok = wr_i32(mem, inst + 0x30, row["def_index"]) and wr_i32(mem, inst + 0x10, row["damage"]) and wr_i32(mem, inst + 0x20, row["ammo"])
        if rd_i32(mem, rec + 4, -1) != primary:
            ok = wr_i32(mem, rec + 4, primary) and ok
        return bool(ok)

    if not (wr_i32(mem, inst + 0x30, target["index"]) and wr_i32(mem, inst + 0x10, dmg) and wr_i32(mem, inst + 0x20, ammo0)):
        restore()
        finish({"status": "weapon instance write did not read back (instance 0x%X)" % inst})
    say("  row %d (%s): definition %d -> %d %r (ordnance 0x%x, damage %d of the definition's %d, %.0f shots/s), ammo %d; fire = %s"
        % (row["row"], why, row["def_index"], target["index"], target["name"], target["ordnance"], dmg, target["damage"], target["rate"], ammo0, kdesc))
    ff = writer(a.out + ".frames.csv", HAZ_COLS)
    ef = writer(a.out + ".events.csv", HAZ_EVENT_COLS)
    t0 = time.perf_counter()
    st = {"off": 0.0, "shots": 0, "rounds": 0}

    def rec_frame(phase):
        got = tel.next(1.0)
        if got is None:
            return None, []
        fr, evs = got
        c = read_counters(mem, dbg)
        t = time.perf_counter() - t0
        ff.write(",".join(cell(v) for v in (
            phase, t, fr["seq"], fr["frame"], fr["proxy_frame"], fr["step_count"], fr["sim_dt"], fr["pos_0"], fr["pos_1"], fr["pos_2"],
            fr["speed"], fr["flags"], hp_sum(fr), rd_i32(mem, inst + 0x20, -1), cnt(c, "hazard_impacts"), cnt(c, "hazard_steps"),
            cnt(c, "tick20_n"), st["off"])) + "\n")
        for ev in evs:
            ef.write(",".join(cell(v) for v in (phase, t, ev["seq"], ev["frame"], ev["type"], ev["f_0"], ev["f_1"], ev["f_2"],
                                                 ev["f_3"], ev["i_0"], ev["i_1"])) + "\n")
            if ev["type"] == EV_SHOT and ev["i_0"] == target["index"]:
                st["shots"] += 1; st["rounds"] += ev["i_1"]
        return fr, evs

    def signals(fr, evs):
        return sum(1 for ev in evs if ev["type"] == EV_IMPACT and ev["i_0"] and ev["i_1"] == CLS_ORDNANCE) + bool(fr["flags"] & FLAG_OIL)

    status, found, window, restored = "ok", None, 0.0, False
    try:
        trn.cmd(CMD_REPAIR)
        fr, settled = settle(tel, timeout=8.0)
        f = heading(fr) if fr else None
        if not f:
            status = "car not upright before the drop"
        else:
            p0 = (fr["pos_0"], fr["pos_1"], fr["pos_2"])
            tel.next(0.5)                                    # events up to here are not ours
            td = time.perf_counter()
            while time.perf_counter() - td < a.tap:
                key.hold()
                rec_frame("drop")
            key.release()
            while time.perf_counter() - td < HAZARD_IMMUNITY + 0.2:
                rec_frame("wait")
            used = ammo0 - rd_i32(mem, inst + 0x20, ammo0)
            say("  dropped: %d SHOT events, %d rounds, ammo -%d, car %s" % (st["shots"], st["rounds"], used, "at rest" if settled else "NOT settled"))
            if not st["shots"] and not used:
                status = "nothing dropped (%s not seen by the game: focus?)" % kdesc
            else:
                hold = p0
                for d in [0.5 * i for i in range(int(a.search / 0.5) + 1)]:
                    if d > 0:
                        hold = (p0[0] - d * f[0], p0[1] + 0.05, p0[2] - d * f[1])
                        trn.cmd(CMD_TELEPORT, hold)
                    st["off"] = d
                    ca, ts, sig = read_counters(mem, dbg), time.perf_counter(), 0
                    while time.perf_counter() - ts < a.dwell:
                        fr2, evs = rec_frame("search")
                        if fr2 is None:
                            break
                        sig += signals(fr2, evs)
                        hold = (fr2["pos_0"], fr2["pos_1"], fr2["pos_2"])
                        if not a.no_repair:
                            trn.post(CMD_REPAIR)
                    cb = read_counters(mem, dbg)
                    if ca and cb:
                        sig += cb["hazard_impacts"] - ca["hazard_impacts"]
                    if sig >= 2:
                        found = d
                        break
                if found is None:
                    status = "no-contact (searched 0..%.1f m behind the drop pose, %d rounds dropped)" % (a.search, st["rounds"] or used)
                else:
                    if not a.no_freeze:
                        trn.set_pos(hold); trn.flags(F_FREEZE_POS)
                    window = min(float(a.seconds), HAZARD_LIFE - (time.perf_counter() - td) - 0.7)
                    say("  contact %.1f m behind the drop pose; recording %.1f s" % (found, window))
                    tm = time.perf_counter()
                    while time.perf_counter() - tm < window:
                        if rec_frame("measure")[0] is None:
                            status = "telemetry stalled in the window"; break
                        if not a.no_repair:
                            trn.post(CMD_REPAIR)
    finally:
        key.release(); trn.flags(0); ff.close(); ef.close()
        restored = restore()
    finish({"status": status, "hazard": target["name"], "ordnance": target["ordnance"], "damage": dmg, "swapped": swapped,
            "row": row["row"], "shots": st["shots"], "rounds": st["rounds"], "offset_m": found, "window_s": round(window, 2),
            "events_lost": tel.lost, "restored": restored})


# ---- wmiss + counters (airolls) -------------------------------------------------------------------------------------------
CNT_COLS = ["t", "frame", "sim_time"] + DBG_NAMES + ["hp", "near_m"]


def cnt_row(mem, c, t, hp="", near=""):
    return ",".join(cell(v) for v in [t, rd_i32(mem, FRAME_COUNTER, -1), struct.unpack("<f", mem.read(SIM_TIME, 4) or b"\0\0\0\0")[0]]
                    + [c[n] for n in DBG_NAMES] + [hp, near]) + "\n"


def run_wmiss(a):
    if a.dry_run:
        say("  [dry-run] player record via [[0x%X]] in 0x%X; a row 1..4 instance +0xc (condition) = 0, read back; hold its "
            "hardpoint key %d s; sample wmiss_req +%d / wmiss_play +%d / tick20_n +%d; restore" % (
                P_PLAYER, WREC, a.seconds, DBG["wmiss_req"], DBG["wmiss_play"], DBG["tick20_n"]))
        finish({"status": "dry-run", "columns": len(CNT_COLS)})
    mem = Mem(a.pid)
    dbg = int(a.dbg, 0) if a.dbg else 0
    if read_counters(mem, dbg) is None:
        finish({"status": "no debug block (the fixed set with I76_RENDER_INTERP is needed)"})
    rec, primary, rows = player_weapons(mem, player_obj(mem))
    row = pick_wmiss_row(rows, primary)
    if not row:
        finish({"status": "no weapon row with a hardpoint key on the player's car (rows %s)" % [r["row"] for r in rows]})
    inst, hp0 = row["inst"], row["hp"]
    if not wr_i32(mem, inst + 0xC, 0):
        finish({"status": "condition write did not read back (instance 0x%X)" % inst})
    key = Key(mem, VK_1 + row["row"], IN_HARDPOINT1 + row["row"], not a.no_keys)
    say("  row %d (instance %d): condition %d -> 0, holding key %d" % (row["row"], row["index"], hp0, row["row"] + 1))
    out = writer(a.out + ".csv", CNT_COLS)
    n = rewrites = 0
    restored = False
    try:
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < a.seconds:
            key.hold()
            hp = rd_i32(mem, inst + 0xC, -1)
            if hp != 0:                                      # something repaired it: the window is no longer clean
                wr_i32(mem, inst + 0xC, 0); rewrites += 1
            c = read_counters(mem, dbg)
            if c:
                out.write(cnt_row(mem, c, time.perf_counter() - t0, hp)); n += 1
            time.sleep(0.004)
    finally:
        key.release(); out.close()
        restored = bool(wr_i32(mem, inst + 0xC, hp0))
    finish({"status": "ok" if n else "no-samples", "samples": n, "row": row["row"], "hp_was": hp0, "rewrites": rewrites, "restored": restored})


def near_spot(objs, mission, dist=40.0, clear=20.0, lift=3.0):
    """A clear spot `dist` m from the centroid of the mission's own cars (ODEF names starting with the mission stem)
    that are not parked at the player's start: (x, y, z), [names]; None when the mission has none."""
    stem = os.path.splitext(mission)[0].lower()
    start = next((o for o in objs if o[0].startswith("vp")), None)
    cars = [o for o in objs if o[0].startswith(stem) and not (start and math.hypot(o[1] - start[1], o[3] - start[3]) < 150.0)]
    if not cars:
        return None
    cx, cz = sum(o[1] for o in cars) / len(cars), sum(o[3] for o in cars) / len(cars)
    y = max(o[2] for o in cars) + lift
    for r in (dist, 1.5 * dist, 2.0 * dist):
        for fx, fz in HEADINGS8:
            x, z = cx + r * fx, cz + r * fz
            if all(o[0].startswith(RAM_IGNORE) or math.hypot(o[1] - x, o[3] - z) >= clear for o in objs):
                return (x, y, z), [o[0] for o in cars]
    return None


def run_counters(a):
    spot = None
    if a.near:
        _path, objs = load_objects(a.mission, a.game, a.tools)
        spot = near_spot(objs, a.mission, lift=a.lift)
    if a.dry_run:
        say("  [dry-run] sample skid_rolls +%d / horn_rolls +%d / tick20_n +%d at ~50 Hz for %d s%s%s" % (
            DBG["skid_rolls"], DBG["horn_rolls"], DBG["tick20_n"], a.seconds, ", god flag held" if a.god else "",
            (", player moved to (%.0f, %.0f, %.0f) beside %s" % (*spot[0], " ".join(spot[1]))) if spot else
            (", --near: no mission cars in the ODEF" if a.near else "")))
        finish({"status": "dry-run", "columns": len(CNT_COLS), "near": bool(spot)})
    mem = Mem(a.pid)
    dbg = int(a.dbg, 0) if a.dbg else 0
    if read_counters(mem, dbg) is None:
        finish({"status": "no debug block (the fixed set with I76_RENDER_INTERP is needed)"})
    trn, placed = None, None
    if spot or a.god:
        trn = Trn(a.shm_suffix)
        if not trn.live():
            finish({"status": "trainer block not live (magic / heartbeat)"})
    if a.god:
        trn.flags(F_GOD)
    if spot:
        ack = trn.cmd(CMD_TELEPORT, spot[0])
        time.sleep(1.5)
        me = next((s for s in read_slots(mem) if s[0] == 0), None)
        placed = bool(ack and me and math.hypot(me[1] - spot[0][0], me[3] - spot[0][2]) < 30.0)   # read back
        say("  player moved beside %s: %s" % (" ".join(spot[1]), "ok" if placed else "NOT confirmed"))
    out = writer(a.out + ".csv", CNT_COLS)
    n, t0 = 0, time.perf_counter()
    try:
        while time.perf_counter() - t0 < a.seconds:
            c = read_counters(mem, dbg)
            slots = read_slots(mem)
            me = next((s for s in slots if s[0] == 0), None)
            near = min((math.dist(me[1:], s[1:]) for s in slots if s[0] != 0), default="") if me else ""
            if c:
                out.write(cnt_row(mem, c, time.perf_counter() - t0, "", near)); n += 1
            time.sleep(0.02)
    finally:
        out.close()
        if trn:
            trn.flags(0)
    finish({"status": "ok" if n else "no-samples", "samples": n, "placed": placed, "god": bool(a.god)})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("measure", choices=("cactus", "airborne", "farengine", "ram", "hazard", "wmiss", "counters"))
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--out", default="", help="output path stem: <dir>\\<tag>")
    ap.add_argument("--tools", default=DEF_TOOLS, help="i76-everywhere tools dir (telemetry\\i76tel.py, level-objects.py)")
    ap.add_argument("--game", default=DEF_GAME)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--mission", default="a01")
    ap.add_argument("--prefix", default=None, help="cactus: ODEF name prefix (nsaguar); ram: comma-separated target prefixes (b = buildings)")
    ap.add_argument("--exclude", default="bebridg", help="ram: comma-separated name prefixes that are never targets")
    ap.add_argument("--once", action="store_true", help="ram: never reuse a target (breakables)")
    ap.add_argument("--clear", type=float, default=15.0, help="ram: clearance beside the approach line for anything that is not a sign or a cactus, m")
    ap.add_argument("--lat-tol", type=float, default=3.0, help="ram: accepted lateral offset of the line from the target centre, m")
    ap.add_argument("--post", type=float, default=1.5, help="ram: seconds recorded after the first contact")
    ap.add_argument("--hazard", choices=("auto", "fire", "oil"), default="auto")
    ap.add_argument("--tap", type=float, default=0.06, help="hazard: seconds the dropper is fired (60 rounds/s)")
    ap.add_argument("--hazard-damage", type=int, default=5, help="hazard: per-hit damage written to the instance (0 = the definition's own)")
    ap.add_argument("--search", type=float, default=8.0, help="hazard: how far behind the drop pose to look for contact, m")
    ap.add_argument("--dwell", type=float, default=0.35, help="hazard: seconds per search position")
    ap.add_argument("--no-freeze", action="store_true", help="hazard: do not FREEZE_POS during the window")
    ap.add_argument("--no-repair", action="store_true", help="hazard: do not post REPAIR every frame")
    ap.add_argument("--near", action="store_true", help="counters: move the player beside the mission's own cars")
    ap.add_argument("--god", action="store_true", help="counters: hold the trainer god flag for the window")
    ap.add_argument("--speed", type=float, default=15.0)
    ap.add_argument("--dist", type=float, default=None, help="start distance before the target: cactus 30, ram 60")
    ap.add_argument("--approaches", type=int, default=6)
    ap.add_argument("--lift", type=float, default=None, help="cactus: drop height above the ODEF y (2); ram 4; counters --near 3; farengine: hold height (800)")
    ap.add_argument("--overrun", type=float, default=25.0)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--acquire", type=float, default=20.0)
    ap.add_argument("--relaunch-at", type=float, default=0.0, help="cactus: re-assert the set speed this many metres before the trunk (0 = off)")
    ap.add_argument("--place", type=float, nargs=4, metavar=("X", "Y", "Z", "SPEED"))
    ap.add_argument("--fixed-step", type=float, default=0.0, help="I76_FIXED_STEP rate (24) when the fixed set is on, else 0")
    ap.add_argument("--dbg", default="", help="farengine: proxy debug block address")
    ap.add_argument("--shm-suffix", default="", help="test only: suffix on both shared-memory names (rate-ab-mockgame.py)")
    ap.add_argument("--no-keys", action="store_true", help="test only: never send the W key (input block write only)")
    a = ap.parse_args()
    if a.lift is None:
        a.lift = {"farengine": 800.0, "ram": 4.0, "counters": 3.0}.get(a.measure, 2.0)
    if a.prefix is None:
        a.prefix = "b" if a.measure == "ram" else "nsaguar"
    if a.dist is None:
        a.dist = 60.0 if a.measure == "ram" else 30.0
    if not a.dry_run and (not a.pid or not a.out):
        ap.error("--pid and --out are required for a live run")
    {"cactus": run_cactus, "airborne": run_airborne, "farengine": run_farengine, "ram": run_ram, "hazard": run_hazard,
     "wmiss": run_wmiss, "counters": run_counters}[a.measure](a)


if __name__ == "__main__":
    main()
