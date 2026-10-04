"""
find-live-armor3.py - identify the LIVE armor copy by which fingerprint site CHANGES on damage.

Why not the HUD: the damage panel is a terrible oracle while AI cars are shooting, because it
changes on its own between the "before" and "after" captures. That produced a false positive -
writing 30 to 0x0CCC6480 moved 0.12% of panel pixels and looked like a hit, but writing 1 (a far
more extreme value) moved 0%. Incidental damage, not causation.

The fingerprint is a much better oracle. Every face has a unique improbable value
(711...788) planted through the .vcf, so:

    a site still holding its fingerprint value = a config/template copy
    a site whose value MOVED                   = the live, damageable armor

Just watch every site across a damage window. No screenshots, no ambiguity.

Requires a variant built with --armor-list 711,722,733,744,755,766,777,788.
"""
import ctypes, ctypes.wintypes as w, struct, sys, time, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

RW = (0x04, 0x40, 0x08, 0x80)
FP = [711, 722, 733, 744, 755, 766, 777, 788]
FACE = ['FRONT', 'RIGHT', 'LEFT', 'REAR', 'chassis FRONT', 'chassis RIGHT',
        'chassis LEFT', 'chassis REAR']


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


def main():
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 30
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
    # Waiting for the AI to shoot is not a reliable stimulus - a 35 s window produced no armor
    # change at all. Drive instead: full throttle into scenery guarantees collision damage.
    print(f"now TAKING DAMAGE for {wait}s - driving at full throttle to force collisions\n")
    u = ctypes.WinDLL('user32', use_last_error=True)
    scW = u.MapVirtualKeyW(0x57, 0)      # W = throttle (notched: repeated taps add notches)
    scD = u.MapVirtualKeyW(0x44, 0)      # D = steer, to keep hitting new things
    end = time.time() + wait
    n = 0
    while time.time() < end:
        u.keybd_event(0x57, scW, 0x8, 0)
        time.sleep(0.02)
        u.keybd_event(0x57, scW, 0x8 | 0x2, 0)
        if (n // 40) % 2:                # alternate straight / turning
            u.keybd_event(0x44, scD, 0x8, 0)
            time.sleep(0.02)
            u.keybd_event(0x44, scD, 0x8 | 0x2, 0)
        n += 1
        time.sleep(0.03)

    changed = []
    for a, i in sorted(sites.items()):
        v = p.u32(a)
        if v is not None and v != FP[i]:
            changed.append((a, i, FP[i], v))

    print(f"=== sites whose value MOVED (live armor) : {len(changed)} ===")
    if not changed:
        print("  none - the car took no damage. Drive into things, or wait longer,")
        print("  and make sure AI drivers > 0 on the driver entry form.")
        return 0
    for a, i, was, now in changed:
        print(f"  0x{a:08X}  face {i} {FACE[i]:<14} {was} -> {now}")

    # a live block should show several faces at one stride
    print("\n=== stride between changed sites ===")
    addrs = [a for a, _, _, _ in changed]
    for k in range(len(addrs) - 1):
        print(f"  0x{addrs[k]:08X} -> 0x{addrs[k+1]:08X}   +0x{addrs[k+1]-addrs[k]:X}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
