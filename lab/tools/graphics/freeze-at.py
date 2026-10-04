"""freeze-at.py on|off - park the player's car at one fixed spot of t01 through the proxy's trainer control block
(Local\\I76Trainer, i76-everywhere tools/trainer/i76trn.h), so every graphics capture shows the same view.
'on': teleport to SPOT, then hold FREEZE_POS (zero velocity). 'off': release."""
import mmap, struct, sys, time
SPOT = (3634.8, 2.6, 36398.1)          # t01 start area, on the road (trainer drop test, 2026-10-02)
m = mmap.mmap(-1, 168, tagname="Local\\I76Trainer")
if struct.unpack_from("<I", m, 0)[0] != 0x43363749:
    sys.exit("trainer block missing")
if sys.argv[1] == "on":
    struct.pack_into("<3d", m, 36, *SPOT); struct.pack_into("<3f", m, 60, 0.0, 0.0, 0.0)
    struct.pack_into("<I", m, 24, 2)                               # cmd TELEPORT
    struct.pack_into("<I", m, 20, struct.unpack_from("<I", m, 20)[0] + 1)
    time.sleep(0.3)
    struct.pack_into("<I", m, 8, 0x10)                             # flags FREEZE_POS
    print("frozen at", SPOT)
else:
    struct.pack_into("<I", m, 8, 0)
    print("released")
