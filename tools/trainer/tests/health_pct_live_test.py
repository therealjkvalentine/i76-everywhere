"""Live check of object_HealthFraction (0x40b450) under the I76_FIX_HEALTH_PCT variants, on the PLAYER's car.

The target bracket's colour and length are pure functions of this value (docs/HEALTH-BAR-COLOUR.md), so a numeric
check of the value settles the bar. Reads health_pct from Local\\I76Telemetry (the proxy calls the function on the
game thread each frame), pokes the player's armour sides and engine hp directly (tools/trainer/i76trainer.py's Game),
then repairs through the trainer block.

    expected health_pct          stock     =2 (x100 only)   =1 (min(28+72r, 100c))
    armour 30%, core intact      49.6      49.6             49.6
    + engine 99%                 0.99      99.0             49.6
    + engine 20%                 0.20      20.0             20.0

Run inside proxy-run.ps1 -Env @{ I76_FIX_HEALTH_PCT = "1" } (or "2", or "0" for stock, which unsets it).
Usage: health_pct_live_test.py <variant: stock|1|2>
"""
import mmap, struct, sys, time, os
root = __file__.rsplit("\\tools\\", 1)[0]
sys.path.insert(0, root + "\\tools\\telemetry"); sys.path.insert(0, root + "\\tools\\trainer")
import i76tel, i76trainer

variant = sys.argv[1] if len(sys.argv) > 1 else "1"
EXPECT = {"stock": (49.6, 0.99, 0.20), "2": (49.6, 99.0, 20.0), "1": (49.6, 49.6, 20.0)}[variant]
h = i76tel.Header()
shm_size = h.structs["i76tel_shm_t"][1]; frame_off = h.offset("i76tel_shm_t", "frame")
tel = mmap.mmap(-1, shm_size, tagname=h.consts["I76TEL_SHM_NAME"])
trn = mmap.mmap(-1, 168, tagname="Local\\I76Trainer")
fails = 0


def frame():
    last = struct.unpack_from("<I", tel, 0)[0]
    for _ in range(400):
        s0 = struct.unpack_from("<I", tel, 0)[0]
        buf = tel[:shm_size]
        s1 = struct.unpack_from("<I", tel, 0)[0]
        if s0 and s0 == s1 and not (s0 & 1) and s0 != last:      # a frame published after the poke
            return i76tel.decode_frame(h, buf[frame_off:frame_off + h.frame_size])
        time.sleep(0.005)
    raise SystemExit("no telemetry frame")


def health():
    time.sleep(0.1); frame()
    return frame()["health_pct"]


def check(got, want, what):
    global fails
    ok = abs(got - want) < 0.05 * max(1.0, abs(want))
    fails += not ok
    print("  %s  %-34s health_pct %.3f (want %.2f)" % ("PASS" if ok else "FAIL", what, got, want))


def repair():
    seq = struct.unpack_from("<I", trn, 20)[0] + 1
    struct.pack_into("<I", trn, 24, 1); struct.pack_into("<I", trn, 20, seq)
    for _ in range(100):
        time.sleep(0.01)
        if struct.unpack_from("<I", trn, 72)[0] == seq: return True
    return False


pid, path = i76trainer.find_game(False)
g = i76trainer.Game(pid)
obj, ent = g.player()
eng = g.u32(g.u32(ent + 0x3c4) + 0x70) if g.u32(ent + 0x3c4) else 0
if not eng or g.u32(g.u32(ent + 0x3c4) + 0x6c) != 21:
    sys.exit("no engine component (type 21) in slot 7")
print("variant %s: player obj 0x%08x ent 0x%08x engine 0x%08x  baseline health_pct %.3f" % (variant, obj, ent, eng, health()))
repair(); time.sleep(0.2)
# armour 30% on all four sides (absorption copy and HUD copy), chassis full
for s in range(4):
    am = g.i32(ent + 0x158 + 4 * s)
    g.wr(ent + 0x138 + 4 * s, struct.pack("<i", int(am * 0.3))); g.wr(ent + 0x178 + 4 * s, struct.pack("<i", int(am * 0.3)))
check(health(), EXPECT[0], "armour 30%, core intact")
emax = g.i32(eng + 4)
g.wr(eng, struct.pack("<i", int(emax * 0.99)))
check(health(), EXPECT[1], "+ engine 99%% (%d/%d)" % (int(emax * 0.99), emax))
g.wr(eng, struct.pack("<i", int(emax * 0.20)))
check(health(), EXPECT[2], "+ engine 20%")
print("  repair:", "ok" if repair() else "NO ACK", " health_pct after %.2f" % health())
print("%d failure(s)" % fails)
sys.exit(1 if fails else 0)
