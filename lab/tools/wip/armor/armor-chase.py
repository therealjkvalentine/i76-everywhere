"""
armor-chase.py - chase the live armor via the per-frame DERIVED copy.

The derived block (eight faces, stride 0x2C) is rewritten every frame, so it must be fed from
the true live armor. That makes it an informant: damage the car, read the derived block, and now
we know the CURRENT armor numbers even though we never knew the encoding. Then search memory
for those numbers - the live store holds them too, and unlike the derived copy a write to it
should stick.

This avoids the two things that kept failing:
  * searching for the CONFIGURED value (the live copy is not stored in that form at all)
  * using the HUD damage panel as an oracle (it moves on its own while AI cars shoot)

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
DERIVED_STRIDE = 0x2C


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


def find_sites(p, regs, values):
    """address -> index, for every 4-aligned occurrence of any value."""
    out = {}
    pats = [struct.pack('<I', v) for v in values]
    for base, size in regs:
        data = p.read(base, size)
        if not data:
            continue
        for i, pat in enumerate(pats):
            s = 0
            while True:
                j = data.find(pat, s)
                if j < 0:
                    break
                if j % 4 == 0:
                    out[base + j] = i
                s = j + 1
    return out


def drive(seconds):
    scW = u32.MapVirtualKeyW(0x57, 0)
    scD = u32.MapVirtualKeyW(0x44, 0)
    end = time.time() + seconds
    n = 0
    while time.time() < end:
        u32.keybd_event(0x57, scW, 0x8, 0); time.sleep(0.02)
        u32.keybd_event(0x57, scW, 0xA, 0)
        if (n // 30) % 2:
            u32.keybd_event(0x44, scD, 0x8, 0); time.sleep(0.02)
            u32.keybd_event(0x44, scD, 0xA, 0)
        n += 1
        time.sleep(0.03)


def main():
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    regs = p.regions()

    # 1. locate the derived block: 8 faces in order at stride 0x2C
    sites = find_sites(p, regs, FP)
    derived = None
    for a, i in sorted(sites.items()):
        if i != 0:
            continue
        seq = [a + k * DERIVED_STRIDE for k in range(8)]
        if all(sites.get(s) == k for k, s in enumerate(seq)):
            derived = a
            break
    if derived is None:
        print("derived block not found - is the fingerprint variant loaded?")
        return 1
    print(f"derived block @0x{derived:08X} (stride 0x{DERIVED_STRIDE:X})")
    before = [p.u32(derived + k * DERIVED_STRIDE) for k in range(8)]
    print(f"  before damage: {before}")

    # 2. damage the car
    print(f"\ndriving {secs}s to force collision damage...")
    drive(secs)
    time.sleep(0.5)
    after = [p.u32(derived + k * DERIVED_STRIDE) for k in range(8)]
    print(f"  after damage : {after}")

    moved = [(k, before[k], after[k]) for k in range(8) if before[k] != after[k]]
    if not moved:
        print("\nthe derived block did NOT change -> it does not track damage.")
        print("that itself is a finding: it is not an armor mirror. stop chasing it.")
        return 0
    print(f"\n{len(moved)} faces changed -> the derived block DOES track damage")

    # 3. the payoff: search for the CURRENT values, which we now know
    targets = [v for _, _, v in moved if v is not None and 0 < v < 100000]
    if not targets:
        print("current values implausible; block was probably reallocated")
        return 1
    print(f"searching memory for current values {targets}\n")
    regs = p.regions()
    hits = find_sites(p, regs, targets)
    # a live store should hold several of the current values close together
    byaddr = sorted(hits.items())
    print(f"{len(byaddr)} sites hold a current value")
    print("=== sites near each other holding >=3 different current values ===")
    n = len(byaddr)
    k = 0
    shown = 0
    while k < n:
        j = k
        seen = {}
        while j < n and byaddr[j][0] - byaddr[k][0] <= 0x400:
            seen.setdefault(byaddr[j][1], byaddr[j][0])
            j += 1
        if len(seen) >= 3:
            order = sorted(seen.items(), key=lambda kv: kv[1])
            gaps = [order[m + 1][1] - order[m][1] for m in range(len(order) - 1)]
            tag = '  <-- the derived block itself' if abs(order[0][1] - derived) < 0x200 else ''
            print(f"  0x{order[0][1]:08X}  {len(seen)} values, gaps {[hex(g) for g in gaps]}{tag}")
            shown += 1
            if shown > 20:
                print("  ... truncated"); break
        k = j if j > k else k + 1
    if shown == 0:
        print("  none")
    print("\nNEXT: poke-probe.ps1 each candidate - the LIVE store is the one where a write STICKS")
    print("and the derived block follows it on the next frame.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
