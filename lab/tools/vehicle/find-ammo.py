"""
find-ammo.py - locate LIVE ammo by gating on firing.

An earlier hunt used "starts at 2000 and decreases" and produced 0x005AAC58 / 0x005AACA4, which
were NOT ammo: with the HUD reading 1885 they read 1640/1648, and writing 9999 did not move the
HUD. They were free-running counters that happened to start at 2000.

The fix is a discriminator that a free-running counter cannot pass:

    idle -> FIRE -> idle -> FIRE

Real ammo DROPS across each fire window and stays EXACTLY CONSTANT across each idle window.
Anything that ticks on its own fails the idle test. Requiring two fire windows with similar
decrements removes most of the rest.

Two passes so it runs in reasonable time: a coarse A/B sweep over all writable memory to build
a candidate set, then the remaining phases sampled only at those addresses.

Verification is still required after this: WRITE a distinctive value and confirm the HUD follows.
"Decreases when expected" alone is what caused the last wrong answer.
"""
import ctypes, ctypes.wintypes as w, struct, sys, time, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
u32dll = ctypes.WinDLL('user32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

RW = (0x04, 0x40, 0x08, 0x80)          # writable only - ammo must be writable
# FIRE IS ENTER, NOT SPACE. input.map's comment header says "Space fire" and it is WRONG - the
# actual weapon_fire block binds keyboard Enter (and mouse LeftBtn). Firing Space changes
# nothing, every candidate is noise, and the HUD still reads 2000. Check the binding block, not
# the comment.
VK_FIRE, KEYEVENTF_SCANCODE, KEYEVENTF_KEYUP = 0x0D, 0x8, 0x2
AMMO_MIN, AMMO_MAX = 2, 30000


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
        if not self.h:
            raise OSError(ctypes.get_last_error())

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


def hold_fire(seconds):
    sc = u32dll.MapVirtualKeyW(VK_FIRE, 0)
    end = time.time() + seconds
    while time.time() < end:
        u32dll.keybd_event(VK_FIRE, sc, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.015)
    u32dll.keybd_event(VK_FIRE, sc, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)


def snap(p, regs):
    return {b: p.read(b, s) for b, s in regs}


def main():
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    regs = p.regions()
    print(f"pid {pid}, {len(regs)} writable regions")

    print("phase 1: idle 2s")
    time.sleep(2.0)
    A = snap(p, regs)
    print("phase 2: FIRING 3s")
    hold_fire(3.0)
    time.sleep(0.4)
    B = snap(p, regs)

    cand = []
    for base, size in regs:
        a, b = A.get(base), B.get(base)
        if not a or not b:
            continue
        n = min(len(a), len(b)) - 4
        for o in range(0, n, 4):
            va = struct.unpack_from('<I', a, o)[0]
            vb = struct.unpack_from('<I', b, o)[0]
            if va != vb and AMMO_MIN <= vb < va <= AMMO_MAX and (va - vb) <= 2000:
                cand.append((base + o, va, vb))
    print(f"after fire#1: {len(cand)} candidates decreased")
    if not cand:
        print("none - is a weapon firing? check you are in a mission and Space fires.")
        return 1

    print("phase 3: idle 3s  (real ammo must NOT move)")
    time.sleep(3.0)
    keep = []
    for addr, va, vb in cand:
        vc = p.u32(addr)
        if vc == vb:
            keep.append((addr, va, vb))
    print(f"survived idle: {len(keep)}")

    print("phase 4: FIRING 3s")
    hold_fire(3.0)
    time.sleep(0.4)
    final = []
    for addr, va, vb in keep:
        vd = p.u32(addr)
        if vd is not None and vd < vb:
            final.append((addr, va, vb, vd, (va - vb), (vb - vd)))
    print(f"decreased again: {len(final)}\n")

    final.sort(key=lambda r: abs(r[4] - r[5]))    # similar decrement both bursts = best
    print(f"{'addr':>12} {'idle1':>8} {'afterF1':>8} {'afterF2':>8} {'d1':>6} {'d2':>6}")
    for addr, va, vb, vd, d1, d2 in final[:25]:
        print(f"0x{addr:010X} {va:8d} {vb:8d} {vd:8d} {d1:6d} {d2:6d}")
    if final:
        print("\nNEXT: verify by WRITING a distinctive value (e.g. 1234) and confirming the HUD")
        print("shows it. 'Decreases when firing' alone is what produced the last wrong answer.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
