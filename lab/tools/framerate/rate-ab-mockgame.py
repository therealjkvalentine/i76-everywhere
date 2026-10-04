#!/usr/bin/env python3
"""rate-ab-mockgame.py - a stand-in for the game + proxy, so rate-ab-live.py's recorders can be run end to end with
no game: `python rate-ab-selftest.py --live` starts this and drives the recorders against it.

It is NOT a model of I'76 physics. It reproduces the INTERFACES the recorder talks to, laid out independently of
rate-ab-live.py (offsets parsed here from i76trn.h / i76tel.h, and the debug block from the g_idbg declaration in
strlkproxy.c):
  - memory at the game's addresses in this process: input block 0x5367CC (throttle) / 0x5367DB (weapon_fire) /
    0x5367DE.. (hardpoint keys), position table 0x54E11C, frame counter 0x5A7E1C, sim time 0x5A7E74, the player
    pointer chain [[0x54A264]], a player object (rot at +0x18), the weapon tables (record 0x5BE4D8, instances
    0x5AAB08, definitions 0x5D88D8, ordnance 0x655280) and a debug block with every g_idbg counter
  - Local\\I76Telemetry<suffix>: i76tel_shm_t with the seq lock and the event ring
  - Local\\I76Trainer<suffix>: TELEPORT / REPAIR one-shots with ack_seq, FREEZE_POS, heartbeat
and a toy world with a known answer: flat ground at y 25, 24 Hz fixed step under a --fps render loop (60: two frames
in five carry no step), the a01 saguaros (every ODD trunk crossing is a hit: IMPACT event class 3 and the speed cut to
10%; every EVEN one passes through), a ramp at z 42700 (take-off with pitch rate 0.4 rad/s, integrated with gain
--gain), and one AI car in slot 1 that accelerates as 25 (1 - exp(-t / --tau)) once the player is frozen.

For the PER-FRAME-AUDIT-2026-10-03 measures it also models, with the audit's own mechanisms:
  collisions   ODEF objects whose name starts with --solid are solid discs (--solid-r m). The contact test runs once
               per FRAME before the physics steps (physics_CollideAll): coll_events + 1; a contact that was also made
               on the previous frame while that frame ran no step is a repeat (coll_dups + 1). Each contact applies
               --coll-dmg hp and an IMPACT event (player, class 2), except a repeat under --coll-dedupe 1. The bounce
               happens on the next physics step. So at 24 steps/s the repeat share is 0 / 0.6 / 0.8 at 20 / 60 / 120 fps.
  weapons      the sandbox car's four rows (25mm, 50cal, Gas Launcher, Landmines) plus Fire-Dropper and Oil Slick
               definitions. A row fires while its hardpoint byte (or weapon_fire, for the primary row) is set. A dead
               row (condition 0) requests WMISS every frame (wmiss_req) and plays it on 20 Hz grid frames (wmiss_play).
               A row whose definition is a fire patch / oil slick drops a stationary patch 3 m behind the car (SHOT
               event, rounds = int(dt x rate)); a patch lives 20 s, ignores its shooter for 2 s, and on every step
               (--hazard-fix 1: grid frames only; 0: every frame) counts hazard_steps and, with the car within 1.2 m,
               hazard_impacts plus one ordnance IMPACT event per round.
  AI rolls     a skid-roll opportunity on every even frame and a horn opportunity on every fourth; --ai-hold 1 lets
               them roll on grid frames only.
The suffix keeps it off the real game's shared memory; it never sends input.
"""
import argparse, ctypes, importlib.util, math, mmap, os, re, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = r"C:\Users\james\i76-everywhere\tools"
PROXY_C = os.path.normpath(os.path.join(TOOLS, "..", "music-fix", "strlkproxy.c"))
GROUND = 25.0
C_TYPES = {"DWORD": 4, "int": 4, "float": 4, "double": 8, "WORD": 2, "BYTE": 1, "char": 1}


def struct_offsets(header, name):
    """{field: (offset, struct code, count)} of a packed struct in a C header, scalars only (i76trn.h contract)."""
    codes = {"uint32_t": "I", "int32_t": "i", "uint16_t": "H", "float": "f", "double": "d", "char": "s"}
    body = re.search(r"typedef struct %s \{(.*?)\} %s;" % (name, name), open(header, encoding="utf-8").read(), re.S).group(1)
    out, off = {}, 0
    for m in re.finditer(r"^\s*(\w+)\s+(\w+)(?:\[(\d+)\])?\s*;", body, re.M):
        c, n = codes[m.group(1)], int(m.group(3) or 1)
        out[m.group(2)] = (off, c, n)
        off += (n if c == "s" else struct.calcsize("<" + c) * n)
    return out, off


def c_layout(body):
    """Natural-alignment layout (what MSVC x86 and mingw -m32 both do for these types) of a C struct body with scalar
    members, arrays and nested anonymous structs: ([(name, offset)], size, alignment). Array members appear once
    (their first element); a nested struct array as name[i].field."""
    out, off, big, i = [], 0, 1, 0
    while True:
        while i < len(body) and body[i].isspace():
            i += 1
        if i >= len(body):
            break
        if body.startswith("struct", i):
            j = body.index("{", i)
            depth, k = 1, j + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(body[k], 0); k += 1
            inner, isize, ial = c_layout(body[j + 1:k - 1])
            end = body.index(";", k)
            for d in body[k:end].split(","):
                m = re.match(r"\s*(\w+)\s*(?:\[(\d+)\])?\s*$", d)
                off = (off + ial - 1) // ial * ial
                for n in range(int(m.group(2) or 1)):
                    out += [("%s[%d].%s" % (m.group(1), n, fn), off + fo) for fn, fo in inner]
                    off += isize
            big = max(big, ial)
        else:
            end = body.index(";", i)
            typ, decls = body[i:end].split(None, 1)
            size = C_TYPES[typ]
            for d in decls.split(","):
                m = re.match(r"\s*(\w+)\s*(?:\[(\d+)\])?\s*$", d)
                off = (off + size - 1) // size * size
                out.append((m.group(1), off))
                off += size * int(m.group(2) or 1)
            big = max(big, size)
        i = end + 1
    return out, (off + big - 1) // big * big, big


def gidbg_layout(path=PROXY_C):
    """({member: offset}, sizeof) of strlkproxy.c's g_idbg, computed from its declaration in the source."""
    text = open(path, encoding="utf-8", errors="replace").read()
    end = text.index("} g_idbg;")
    start = text.rindex("static struct {", 0, end)
    body = re.sub(r"/\*.*?\*/", " ", text[start + len("static struct {"):end], flags=re.S)
    fields, size, _al = c_layout(body)
    return dict(fields), size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", required=True)
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--gain", type=float, default=1.0)
    ap.add_argument("--tau", type=float, default=3.0)
    ap.add_argument("--fps", type=float, default=60.0)
    ap.add_argument("--solid", default="", help="ODEF name prefix of solid discs (the ram targets)")
    ap.add_argument("--solid-r", type=float, default=6.0)
    ap.add_argument("--coll-dedupe", type=int, default=1)
    ap.add_argument("--coll-dmg", type=int, default=25)
    ap.add_argument("--hazard-fix", type=int, default=1)
    ap.add_argument("--ai-hold", type=int, default=1)
    a = ap.parse_args()

    sys.path.insert(0, os.path.join(TOOLS, "telemetry"))
    import i76tel
    h = i76tel.Header()
    spec = importlib.util.spec_from_file_location("live", os.path.join(HERE, "rate-ab-live.py"))
    live = importlib.util.module_from_spec(spec); spec.loader.exec_module(live)
    _p, objs = live.load_objects("a01")
    cacti = [(x, z) for nm, x, _y, z in objs if nm.startswith("nsaguar") and not (a.solid and nm.startswith(a.solid))]
    solids = [(x, z) for nm, x, _y, z in objs if a.solid and nm.startswith(a.solid)]
    G, _gsize = gidbg_layout()

    k = ctypes.WinDLL("kernel32")
    k.VirtualAlloc.restype = ctypes.c_void_p
    k.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    base = k.VirtualAlloc(0x530000, 0x130000, 0x3000, 0x04)             # the exe's data range 0x530000..0x660000, same addresses
    aux = k.VirtualAlloc(0x00700000, 0x10000, 0x3000, 0x04)             # player object + debug block (< 4 GB: obj_addr is u32)
    if base != 0x530000 or not aux:
        print("MOCK-FAILED could not map the game's addresses in this process", flush=True); sys.exit(3)
    OBJ, PP, DBG = aux, aux + 0x3000, aux + 0x4000

    def poke(addr, fmt, *v):
        ctypes.memmove(addr, struct.pack(fmt, *v), struct.calcsize(fmt))

    def peek(addr, fmt):
        return struct.unpack(fmt, ctypes.string_at(addr, struct.calcsize(fmt)))

    # frame field offsets from the header's own flat format, one token per name
    foff, o = {}, 0
    for (cnt, code), name in zip(re.findall(r"(\d*)([a-zA-Z])", h.frame_fmt), h.frame_names):
        foff[name] = (o, cnt + code); o += struct.calcsize("<" + cnt + code)
    shm_size = h.structs["i76tel_shm_t"][1]
    frame_off, ring_off = h.offset("i76tel_shm_t", "frame"), h.offset("i76tel_shm_t", "ring")
    tel = mmap.mmap(-1, shm_size, tagname=h.consts["I76TEL_SHM_NAME"] + a.suffix)
    T, tsize = struct_offsets(os.path.join(TOOLS, "trainer", "i76trn.h"), "i76trn_ctl_t")
    trn = mmap.mmap(-1, tsize, tagname="Local\\I76Trainer" + a.suffix)

    def tget(f):
        off, c, n = T[f]
        v = struct.unpack_from("<%d%s" % (n, c), trn, off)
        return v if n > 1 and c != "s" else v[0]

    def tset(f, *v):
        off, c, n = T[f]
        struct.pack_into("<%d%s" % (n, c), trn, off, *v)

    tset("magic", 0x43363749); tset("version", 1); tset("size", tsize)

    # the player pointer chain and the weapon tables (i76-map types/i76_runtime.h)
    poke(0x54A264, "<I", PP); poke(PP, "<I", OBJ)
    DEFS = [("25mm Cannon", 2, 30, 200, 5.0, 6), ("50cal MG", 2, 8, 200, 10.0, 1), ("Gas Launcher", 5, 30, 200, 20.0, 0xA),
            ("Landmines", 6, 240, 200, 1.0, 0xF), ("Fire-Dropper", 6, 15, 200, 60.0, 0x11), ("Oil Slick", 6, 0, 200, 60.0, 0xC)]
    for i, (nm, klass, dmg, whp, rate, ordn) in enumerate(DEFS):
        d = 0x5D88D8 + i * 0xD8
        ctypes.memmove(d, nm.encode() + b"\0", len(nm) + 1)
        poke(d + 0x5C, "<3I", klass, dmg, whp); poke(d + 0x70, "<f", rate); poke(d + 0x80, "<I", ordn)
        poke(0x655280 + i * 0xD0, "<i", ordn)
    poke(0x5D88D4, "<i", len(DEFS)); poke(0x5A810C, "<i", len(DEFS))
    for i, ammo in enumerate((300, 2000, 700, 25)):                     # instance i = row i = definition i
        inst = 0x5AAB08 + i * 0x4C
        poke(inst, "<i", i); poke(inst + 0xC, "<3I", DEFS[i][3], DEFS[i][2], DEFS[i][3])
        poke(inst + 0x1C, "<2i", i, ammo); poke(inst + 0x30, "<i", i)
    poke(0x5DA750, "<i", 4)
    poke(0x5BE4D8, "<Ii", OBJ, 0)
    for row in range(5):
        poke(0x5BE4D8 + 0x58 + row * 0x58 + 0x50, "<i", row if row < 4 else -1)
    poke(0x5DA78C, "<i", 1)

    HP_MAX = 2000
    p, v, rates = [1362.5, GROUND, 49612.5], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    pitch, jumped, crossings, down = 0.0, False, 0, set()
    poke(OBJ + 0x18, "<9f", 1, 0, 0, 0, 1, 0, 0, 0, 1)
    seq = frame = ev_seq = 0
    acc, frozen_at, ai_x = 0.0, None, 0.0
    cn = dict.fromkeys(("far_steps", "tick20_n", "hazard_impacts", "hazard_steps", "wmiss_req", "wmiss_play", "skid_rolls",
                        "horn_rolls", "coll_events", "coll_dups"), 0)
    hp, grid, oil_t = HP_MAX, 0.0, 0.0
    fire_acc, was_trig = [0.0] * 4, [False] * 4
    patches = []                                                        # [x, z, born (sim s), rounds, ordnance, damage]
    last_contact, prev_steps, bounce = -10, 1, False
    truth = []
    print("MOCK-READY pid=%d dbg=0x%X" % (os.getpid(), DBG), flush=True)
    t0 = time.perf_counter()
    nxt = t0
    dt = 1.0 / a.fps
    while time.perf_counter() - t0 < a.seconds:
        frame += 1
        now = frame * dt
        events = []
        grid += dt
        tick20 = grid >= 0.05 - 1e-9
        if tick20:
            grid -= 0.05; cn["tick20_n"] += 1
        # trainer service, top of the frame
        tset("heartbeat", frame); tset("player_present", 1)
        frozen = bool(tget("flags") & 0x10)
        if frozen:
            p[:] = tget("pos"); v[:] = [0.0, 0.0, 0.0]; rates[:] = [0.0, 0.0, 0.0]
            frozen_at = frozen_at or frame
        else:
            frozen_at = None
        if tget("req_seq") != tget("ack_seq"):
            c = tget("cmd")
            if c == 1:
                hp = HP_MAX
            if c == 2:
                p[:] = tget("pos"); v[:] = tget("vel"); rates[:] = [0.0, 0.0, 0.0]
            tset("cmd_result", 0 if c in (1, 2) else 2)
            tset("ack_seq", tget("req_seq"))
        thr = 1.0 if peek(0x5367CC, "<i")[0] >= 100 else 0.0
        poke(0x5367CC, "<i", 0)                                         # the engine refills the block from the keyboard
        r = list(peek(OBJ + 0x18, "<9f"))
        n = math.hypot(r[6], r[8]) or 1.0
        hx, hz = r[6] / n, r[8] / n
        # weapons: triggers, the dead-weapon click, hazard drops
        fire = peek(0x5367DB, "<B")[0]
        primary = peek(0x5BE4D8 + 4, "<i")[0]
        for row in range(4):
            inst = 0x5AAB08 + row * 0x4C
            trig = bool(peek(0x5367DE + row, "<B")[0] or (fire and row == primary))
            poke(0x5367DE + row, "<B", 0)
            whp, wdmg = peek(inst + 0xC, "<2I")
            ammo, di = peek(inst + 0x20, "<i")[0], peek(inst + 0x30, "<i")[0]
            if trig and whp == 0:
                cn["wmiss_req"] += 1
                cn["wmiss_play"] += tick20
            elif trig and 0 <= di < len(DEFS) and DEFS[di][5] in (0x11, 0xC) and ammo > 0:
                if not was_trig[row]:
                    fire_acc[row] = 1.0
                fire_acc[row] += dt * DEFS[di][4]
                shots = min(int(fire_acc[row]), ammo)
                fire_acc[row] -= int(fire_acc[row])
                if shots:
                    poke(inst + 0x20, "<i", ammo - shots)
                    patches.append([p[0] - 3.0 * hx, p[2] - 3.0 * hz, now, shots, DEFS[di][5], wdmg])
                    events.append((1, (float(row), float(ammo - shots), float(wdmg), 0.0), (di, shots)))
            was_trig[row] = trig
        poke(0x5367DB, "<B", 0)
        # stationary hazards: every frame, or on the 20 Hz grid with the fix
        patches = [q for q in patches if now - q[2] < 20.0]
        oil_t = max(0.0, oil_t - dt)
        if tick20 or not a.hazard_fix:
            for q in patches:
                cn["hazard_steps"] += 1
                if now - q[2] >= 2.0 and math.hypot(p[0] - q[0], p[2] - q[1]) < 1.2:
                    cn["hazard_impacts"] += 1
                    if q[4] == 0xC:
                        oil_t = 2.0
                    for _ in range(q[3]):
                        lost = min(hp, q[5]); hp -= lost
                        events.append((3, (0.0, 0.0, 0.0, float(lost)), (1, 0x33)))
        # AI rolls
        if frame % 2 == 0 and (tick20 or not a.ai_hold):
            cn["skid_rolls"] += 1
        if frame % 4 == 0 and (tick20 or not a.ai_hold):
            cn["horn_rolls"] += 1
        # the contact test, once per frame, before the physics steps
        for cx, cz in solids:
            if math.hypot(cx - p[0], cz - p[2]) < a.solid_r and (cx - p[0]) * v[0] + (cz - p[2]) * v[2] > 0:
                cn["coll_events"] += 1
                dup = last_contact == frame - 1 and prev_steps == 0
                cn["coll_dups"] += dup
                if not (dup and a.coll_dedupe):
                    lost = min(hp, a.coll_dmg); hp -= lost
                    events.append((3, (v[0], 0.0, v[2], float(lost)), (1, 2)))
                last_contact, bounce = frame, True
        acc += dt
        steps = int(acc * 24.0 + 1e-9); acc -= steps / 24.0
        for _ in range(0 if frozen else steps):
            hs = 1.0 / 24.0
            r = list(peek(OBJ + 0x18, "<9f"))
            air = p[1] > GROUND + 1e-6 or v[1] > 0
            if bounce:                                                  # the response lands on the next physics step
                v[0], v[2], bounce = -0.3 * v[0], -0.3 * v[2], False
            if air:
                v[1] -= 9.8 * hs
                pitch += a.gain * rates[0] * hs
                c, s = math.cos(pitch), math.sin(pitch)
                poke(OBJ + 0x18, "<9f", 1, 0, 0, 0, c, s, 0, -s, c)
            else:
                n = math.hypot(r[6], r[8]) or 1.0
                fx, fz = r[6] / n, r[8] / n
                back = v[0] * fx + v[2] * fz < 0                        # rolling backwards after a bounce
                s = max(0.0, math.hypot(v[0], v[2]) + ((3.0 * thr - 0.3) if not back else -3.0) * hs)
                v[:] = [fx * s * (-1 if back else 1), 0.0, fz * s * (-1 if back else 1)]
                if 42700.0 <= p[2] <= 42705.0 and s > 10 and not jumped:
                    v[1], rates[0], jumped = 6.0, 0.4, True
            q = [p[0] + v[0] * hs, p[1] + v[1] * hs, p[2] + v[2] * hs]
            if q[1] <= GROUND:
                if air:
                    pitch = 0.0; rates[:] = [0.0, 0.0, 0.0]
                    poke(OBJ + 0x18, "<9f", 1, 0, 0, 0, 1, 0, 0, 0, 1)
                q[1], v[1] = GROUND, min(v[1], 0.0) * 0.0
                for i, (cx, cz) in enumerate(cacti):                    # trunk crossed in this step?
                    if i in down or abs(cx - p[0]) > 40 or abs(cz - p[2]) > 40:
                        continue
                    dx, dz = q[0] - p[0], q[2] - p[2]
                    L = dx * dx + dz * dz
                    if L == 0:
                        continue
                    u = ((cx - p[0]) * dx + (cz - p[2]) * dz) / L
                    if 0.0 <= u <= 1.0 and math.hypot(p[0] + u * dx - cx, p[2] + u * dz - cz) < 0.6:
                        crossings += 1
                        hit = crossings % 2 == 1
                        truth.append("HIT" if hit else "PASS-THROUGH")
                        if hit:
                            down.add(i)
                            q[0], q[2] = p[0] + u * dx, p[2] + u * dz
                            v[0] *= 0.1; v[2] *= 0.1
                            events.append((3, (9.0, 0.0, 1.0, 12.0), (1, 3)))
                            events.append((3, (1.0, 0.0, 0.0, 0.0), (0, 1)))     # someone else's impact
            p[:] = q
        prev_steps = 0 if frozen else steps
        air = p[1] > GROUND + 1e-6
        # publish: events into the ring, then the frame under the seq lock
        seq += 1
        struct.pack_into("<I", tel, 0, seq * 2 - 1)
        for typ, f, i in events:
            ev_seq += 1
            struct.pack_into(h.event_fmt, tel, ring_off + (ev_seq % 64) * h.event_size, ev_seq, frame, typ, *f, *i)
        buf = bytearray(h.frame_size)

        def put(name, val):
            struct.pack_into("<" + foff[name][1], buf, foff[name][0], val)

        r = peek(OBJ + 0x18, "<9f")
        for name, val in (("magic", h.consts["I76TEL_MAGIC"]), ("version", h.consts["I76TEL_VERSION"]), ("size", h.frame_size),
                          ("seq", seq), ("frame", frame), ("proxy_frame", frame), ("sim_time", frame * dt), ("sim_dt", dt), ("dt", dt),
                          ("step_count", steps), ("player_present", 1), ("obj_addr", OBJ), ("pos_0", p[0]), ("pos_1", p[1]), ("pos_2", p[2]),
                          ("velocity_0", v[0]), ("velocity_1", v[1]), ("velocity_2", v[2]), ("speed", math.sqrt(sum(x * x for x in v))),
                          ("pitch_rate", rates[0]), ("yaw_rate", rates[1]), ("roll_rate", rates[2]), ("throttle", thr),
                          ("flags", 1 | (4 if air else 0) | (0x400 if oil_t > 0 else 0)), ("clearance", p[1] - GROUND),
                          ("armour_0", hp), ("armour_max_0", HP_MAX), ("event_seq", ev_seq)):
            put(name, val)
        for i in range(9):
            put("rot_%d" % i, r[i])
        tel[frame_off:frame_off + h.frame_size] = bytes(buf)
        struct.pack_into("<I", tel, 4, shm_size)
        struct.pack_into("<I", tel, 0, seq * 2)
        # the exe's globals
        poke(0x5A7E1C, "<i", frame); poke(0x5A7E74, "<f", frame * dt)
        poke(0x54E11C, "<4f", p[0], p[1], p[2], 3.0)
        if frozen_at:
            tt = (frame - frozen_at) * dt - 2.0
            ai_x += (25.0 * (1 - math.exp(-tt / a.tau)) if tt > 0 else 0.0) * dt
            cn["far_steps"] += 1
        poke(0x54E11C + 0x20, "<4f", 3340.0 + ai_x, 3.3, 35880.0, 3.0)
        for name, val in cn.items():
            poke(DBG + G[name], "<I", val)
        nxt += dt
        time.sleep(max(0.0, nxt - time.perf_counter()))
    print("MOCK-TRUTH " + ",".join(truth), flush=True)


if __name__ == "__main__":
    main()
