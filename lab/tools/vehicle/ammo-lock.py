"""
ammo-lock.py - set and hold a weapon's ammo. The one thing that is fully proven.

The live ammo array is STATIC, which is why it survives the respawns that defeat every
address-based armor search:

    0x005AAB0C, stride 0x4C, ammo at +0x1C   (0x0FFFFFFF = unlimited)

Verified by writing: 1234 -> HUD read "30CAL MG 1234"; 7777/4242 -> "30CAL MG 7777" /
"OIL SLICK 4242".

The player's car is identified by its LOADOUT signature rather than a fixed slot index, because
a respawn shifts which slots the player occupies (observed: slots 0-3 became 5-8). For the
Piranha loadout that signature is roughly [300, ~2000, 700, 25] in consecutive slots =
25mm Cannon, 50cal MG, Gas Launcher, Landmines.

  ammo-lock.py                       show the array
  ammo-lock.py --set 3333            set the 50cal slot once
  ammo-lock.py --set 3333 --hold 120 hold it there for 120 s (defeats firing)
"""
import ctypes, struct, sys, time, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
BASE, STRIDE, AMMO, NSLOT = 0x005AAB0C, 0x4C, 0x1C, 16
UNLIMITED = 0x0FFFFFFF


def find_pid():
    for n in ('i76.exe', 'nitro.exe'):
        out = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {n}', '/FO', 'CSV'],
                                      text=True, errors='ignore')
        for line in out.splitlines()[1:]:
            p = [x.strip('"') for x in line.split('","')]
            if len(p) > 1 and p[0].lower() == n:
                return int(p[1])
    return None


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(0x0010 | 0x0020 | 0x0008 | 0x0400, False, pid)
        if not self.h:
            raise OSError(ctypes.get_last_error())

    def u32(self, a):
        b = ctypes.create_string_buffer(4); g = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), b, 4, ctypes.byref(g))
        return struct.unpack('<I', b.raw)[0] if g.value == 4 else 0

    def w32(self, a, v):
        b = struct.pack('<I', v); g = ctypes.c_size_t(0)
        return bool(k32.WriteProcessMemory(self.h, ctypes.c_void_p(a), b, 4, ctypes.byref(g)))


def slots(p):
    return [(i, p.u32(BASE + i * STRIDE + AMMO)) for i in range(NSLOT)]


def find_50cal(p):
    """the player's group looks like [~300, ~2000, ~700, ~25]; the 50cal is the 2nd."""
    s = [v for _i, v in slots(p)]
    for i in range(len(s) - 3):
        a, b, c, d = s[i], s[i + 1], s[i + 2], s[i + 3]
        if 200 <= a <= 320 and 300 <= b <= 4000 and 500 <= c <= 760 and 1 <= d <= 30:
            return i + 1
    # fall back: the slot closest to a machine-gun magazine
    best, bi = 1e9, None
    for i, v in slots(p):
        if v != UNLIMITED and 500 <= v <= 4000 and abs(v - 2000) < best:
            best, bi = abs(v - 2000), i
    return bi


def main():
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    print(f"pid {pid}\n  slot   ammo")
    for i, v in slots(p):
        if v == 0:
            continue
        print(f"  {i:>4}  {'unlimited' if v == UNLIMITED else v}")

    idx = find_50cal(p)
    if idx is None:
        print("\ncould not identify the 50cal slot"); return 1
    addr = BASE + idx * STRIDE + AMMO
    print(f"\n50cal MG -> slot {idx}, ammo at 0x{addr:08X}, currently {p.u32(addr)}")

    if '--set' not in sys.argv:
        print("(pass --set N to write)")
        return 0
    val = int(sys.argv[sys.argv.index('--set') + 1])
    p.w32(addr, val)
    print(f"wrote {val}; reads back {p.u32(addr)}")

    if '--hold' in sys.argv:
        secs = int(sys.argv[sys.argv.index('--hold') + 1])
        print(f"holding at {val} for {secs}s - fire away, it should not drop")
        end = time.time() + secs
        writes = 0
        while time.time() < end:
            if p.u32(addr) != val:
                p.w32(addr, val)
                writes += 1
            time.sleep(0.05)
        print(f"done; re-asserted {writes} times (each one is a shot you fired)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
