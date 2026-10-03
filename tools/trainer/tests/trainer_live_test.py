"""Live regression test for the proxy's trainer control block (Local\\I76Trainer, tools/trainer/i76trn.h).

Run while the SANDBOX game is in a mission with the i76-everywhere Strlkup proxy loaded and I76_TELEMETRY=1
(C:\\Users\\james\\i76-uncap-lab\\autotest\\proxy-run.ps1 -Run { python ...\\trainer_live_test.py } does all of that).
It reads state from Local\\I76Telemetry (tools/telemetry/i76tel.py's header parser) and drives the control block.

Checks, each printed PASS / FAIL:
  1. the proxy block is live: magic and a heartbeat that advances (a stale mapping survives the game while any
     process holds it, so magic alone proves nothing)
  2. holding GOD | AMMO forces options_play_flags bits 0x1c and releasing restores the previous value
  3. holding AMMO makes the selected weapon's ammo read 0x0fffffff; releasing leaves it there (held value, not a
     restore - the game refills from the .gdf each mission anyway)
  4. REPAIR one-shot is acknowledged
  5. drop test: a 40 m fall (TELEPORT one-shot, about 28 m/s at impact) costs armour + chassis with god off and
     nothing with god on
Verified 2026-10-02 on the sandbox (t01): 2/2 play flags, drop -156 off / 0 on.
"""
import mmap, struct, sys, time
sys.path.insert(0, __file__.rsplit("\\tools\\", 1)[0] + "\\tools\\telemetry")
import i76tel

TRN_MAGIC = 0x43363749
TRN_FMT = "<I H H I I I I I i i 3d 3f I I I I I I I I 64s"
TRN = ("magic version size flags play_set play_clear req_seq cmd slot_index ammo_value pos0 pos1 pos2 vel0 vel1 vel2 "
       "ack_seq heartbeat applied player_present play_flags_now play_flags_saved faults cmd_result msg").split()
# one offset per NAME: the format has "3d" / "3f" items covering three names each, so expand it per field first
_PER_FIELD = []
for _c in TRN_FMT[1:].split():
    _PER_FIELD += [_c[-1]] * int(_c[:-1]) if _c[:-1].isdigit() and _c[-1] != "s" else [_c]
TRN_OFF = {n: struct.calcsize("<" + "".join(_PER_FIELD[:i])) for i, n in enumerate(TRN)}
F_GOD, F_AMMO = 1, 2
CMD_REPAIR, CMD_TELEPORT = 1, 2
UNLIMITED = 0x0FFFFFFF

h = i76tel.Header()
shm_size = h.structs["i76tel_shm_t"][1]
frame_off = h.offset("i76tel_shm_t", "frame")
tel = mmap.mmap(-1, shm_size, tagname=h.consts["I76TEL_SHM_NAME"])
trn = mmap.mmap(-1, struct.calcsize(TRN_FMT), tagname="Local\\I76Trainer")
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print("  %s  %s" % ("PASS" if ok else "FAIL", what))


def frame():
    for _ in range(400):
        s0 = struct.unpack_from("<I", tel, 0)[0]
        buf = tel[:shm_size]
        s1 = struct.unpack_from("<I", tel, 0)[0]
        if s0 and s0 == s1 and not (s0 & 1):
            return i76tel.decode_frame(h, buf[frame_off:frame_off + h.frame_size])
        time.sleep(0.005)
    raise SystemExit("no telemetry frame (I76_TELEMETRY=1 and a running mission needed)")


def rd():
    d = dict(zip(TRN, struct.unpack_from(TRN_FMT, trn, 0)))
    d["msg"] = d["msg"].split(b"\0")[0].decode("latin1")
    return d


def flags(f):
    struct.pack_into("<I", trn, TRN_OFF["flags"], f)


def cmd(c, pos=None, vel=(0.0, 0.0, 0.0)):
    seq = rd()["req_seq"] + 1
    if pos:
        struct.pack_into("<3d", trn, TRN_OFF["pos0"], *pos)
    struct.pack_into("<3f", trn, TRN_OFF["vel0"], *vel)
    struct.pack_into("<I", trn, TRN_OFF["cmd"], c)
    struct.pack_into("<I", trn, TRN_OFF["req_seq"], seq)
    for _ in range(100):
        time.sleep(0.01)
        d = rd()
        if d["ack_seq"] == seq:
            return d
    return None


def hp(fr):
    comps = fr["engine_hp"] + fr["susp_hp"] + fr["brake_hp"] + sum(fr["wheel%d_hp" % i] for i in range(6) if fr["wheel%d_present" % i])
    return sum(fr["armour_%d" % i] + fr["chassis_%d" % i] for i in range(4)), comps


print("1. proxy block")
d = rd(); hb0 = d["heartbeat"]; time.sleep(1.0); d1 = rd()
check(d["magic"] == TRN_MAGIC, "magic 0x%08x" % d["magic"])
check(d1["heartbeat"] - hb0 > 10, "heartbeat +%d in 1 s" % (d1["heartbeat"] - hb0))
check(d1["player_present"] == 1, "player present")
if fails:
    sys.exit("no live proxy block - is the sandbox in a mission with the new Strlkup.dll?")

print("2. play-flag forcing and restore")
flags(0); time.sleep(0.2); before = rd()["play_flags_now"]
flags(F_GOD | F_AMMO); time.sleep(0.3); held = rd()
check(held["play_flags_now"] & 0x1c == 0x1c, "held: play flags 0x%02x (want bits 0x1c)" % held["play_flags_now"])
check(held["applied"] & (F_GOD | F_AMMO) == (F_GOD | F_AMMO), "applied 0x%02x" % held["applied"])
flags(0); time.sleep(0.3); after = rd()["play_flags_now"]
check(after == before, "released: play flags 0x%02x (were 0x%02x)" % (after, before))

print("3. ammo hold")
fr = frame(); a0 = fr["weapon_ammo"]
flags(F_AMMO); time.sleep(0.3); fr = frame()
check(fr["weapon_row"] >= 0, "a weapon is selected (row %d, %r)" % (fr["weapon_row"], fr["weapon_name"]))
check(fr["weapon_ammo"] == UNLIMITED, "selected weapon ammo 0x%08x while held (was %d)" % (fr["weapon_ammo"], a0))
flags(0)

print("4. repair one-shot")
d = cmd(CMD_REPAIR)
check(d is not None and d["cmd_result"] == 0, "ack %s msg %r" % (d and d["ack_seq"], d and d["msg"]))

print("5. drop test (god off, then on)")
loss = {}
for god in (0, 1):
    flags(F_GOD if god else 0); time.sleep(0.3); cmd(CMD_REPAIR); time.sleep(0.3)
    f0 = frame(); a0, c0 = hp(f0)
    d = cmd(CMD_TELEPORT, (f0["pos_0"], f0["pos_1"] + 40.0, f0["pos_2"]))
    minv = 0.0
    for _ in range(40):
        time.sleep(0.1); fr = frame(); minv = min(minv, fr["velocity_1"])
    a1, c1 = hp(fr)
    loss[god] = (a0 - a1) + (c0 - c1)
    print("     god=%d: fall %.1f m/s, armour+chassis %+d, components %+d" % (god, minv, a1 - a0, c1 - c0))
    check(minv < -15, "god=%d: the car fell (min vertical speed %.1f m/s)" % (god, minv))
flags(0)
check(loss[0] > 0, "god off: the fall cost %d hp" % loss[0])
check(loss[1] == 0, "god on: the fall cost %d hp" % loss[1])

print("%d failure(s)" % fails)
sys.exit(1 if fails else 0)
