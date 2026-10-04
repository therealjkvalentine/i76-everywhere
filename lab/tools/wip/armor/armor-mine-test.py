"""
armor-mine-test.py - damage your own car ON DEMAND with landmines, and see what moves.

Getting a reliable damage stimulus was most of this problem:
  * waiting for AI fire      - 35 s produced no armor change at all
  * grinding a wall at speed 1 - almost no damage
  * full-throttle driving    - hits scenery but stops the car dead against it

Landmines are deterministic. Key '4' drops one (measured against the live ammo table: slot 3,
23 -> 21), it lands behind the car, and reversing over it detonates it on your own vehicle.

Procedure per round: drop mines, reverse onto them, then compare every fingerprint site.
Sites still holding their planted value are config/template copies; sites that MOVED are live.

Requires a variant built with --armor-list 711,722,733,744,755,766,777,788.
"""
import ctypes, ctypes.wintypes as w, struct, sys, time, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
u32 = ctypes.WinDLL('user32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

RW = (0x04, 0x40, 0x08, 0x80)
FP = [711, 722, 733, 744, 755, 766, 777, 788]
FACE = ['FRONT', 'RIGHT', 'LEFT', 'REAR', 'ch-FRONT', 'ch-RIGHT', 'ch-LEFT', 'ch-REAR']
AMMO_BASE, AMMO_STRIDE, AMMO_OFF = 0x005AAB0C, 0x4C, 0x1C


def find_pid(name='i76.exe'):
    out = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'],
                                  text=True, errors='ignore')
    for line in out.splitlines()[1:]:
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == name:
            return int(parts[1])
    return None


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(0x0010 | 0x0400, False, pid)

    def read(self, a, n):
        b = ctypes.create_string_buffer(n); g = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), b, n, ctypes.byref(g))
        return b.raw[:g.value]

    def u32(self, a):
        b = self.read(a, 4)
        return struct.unpack('<I', b)[0] if len(b) == 4 else None

    def regions(self):
        addr, out, mbi = 0, [], MBI()
        while addr < 0x7FFF0000:
            if not k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                      ctypes.sizeof(mbi)):
                break
            size = mbi.RegionSize or 0x1000
            if mbi.State == 0x1000 and mbi.Protect in RW and size <= 32 * 1024 * 1024:
                out.append((mbi.BaseAddress or 0, size))
            addr = (mbi.BaseAddress or 0) + size
        return out


def key(vk, hold=0.06):
    sc = u32.MapVirtualKeyW(vk, 0)
    u32.keybd_event(vk, sc, 0x8, 0)
    time.sleep(hold)
    u32.keybd_event(vk, sc, 0x8 | 0x2, 0)


def hold(vk, secs):
    sc = u32.MapVirtualKeyW(vk, 0)
    end = time.time() + secs
    while time.time() < end:
        u32.keybd_event(vk, sc, 0x8, 0)
        time.sleep(0.015)
    u32.keybd_event(vk, sc, 0x8 | 0x2, 0)


def mine_round(p):
    """drop mines, then reverse onto them. returns landmine ammo used."""
    slot3 = AMMO_BASE + 3 * AMMO_STRIDE + AMMO_OFF
    a0 = p.u32(slot3)
    hold(0x57, 1.2)                 # W - roll forward a little
    for _ in range(3):
        key(0x34); time.sleep(0.35)  # '4' - drop landmine
    time.sleep(0.4)
    hold(0x58, 2.2)                 # X - reverse over them
    time.sleep(1.2)
    a1 = p.u32(slot3)
    return (a0 or 0) - (a1 or 0)


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    regs = p.regions()

    sites = {}
    for base, size in regs:
        data = p.read(base, size)
        if not data:
            continue
        for i, v in enumerate(FP):
            pat = struct.pack('<I', v)
            s = 0
            while True:
                j = data.find(pat, s)
                if j < 0:
                    break
                if j % 4 == 0:
                    sites[base + j] = i
                s = j + 1
    print(f"pid {pid}: {len(sites)} fingerprint sites")

    for r in range(rounds):
        used = mine_round(p)
        moved = [(a, i) for a, i in sites.items()
                 if (p.u32(a) is not None and p.u32(a) != FP[i])]
        print(f"  round {r+1}: {used} mines used, {len(moved)} sites moved")
        if len(moved) and len(moved) < 60:
            break

    print("\n=== sites that MOVED (candidate live armor) ===")
    out = []
    for a, i in sorted(sites.items()):
        v = p.u32(a)
        if v is not None and v != FP[i]:
            out.append((a, i, FP[i], v))
    if not out:
        print("  none - the car took no damage from its own mines either.")
        return 0
    # a live armor value should DROP, and stay in a sane range
    plausible = [t for t in out if 0 < t[3] < t[2]]
    print(f"  {len(out)} moved, {len(plausible)} of them DECREASED (armor should decrease)\n")
    for a, i, was, now in plausible[:40]:
        print(f"  0x{a:08X}  {FACE[i]:<9} {was} -> {now}")
    if not plausible:
        print("  none decreased; the movers are:")
        for a, i, was, now in out[:20]:
            print(f"  0x{a:08X}  {FACE[i]:<9} {was} -> {now}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
