"""
armor-list-arrays.py - list EVERY armor array in the process, with its damage pattern.

The bug this fixes: the previous finder returned the first array within a window of the player
entity, and that is not necessarily the PLAYER's. Every vehicle in the mission has one. After a
respawn the entity moved (0xD749A8C -> 0xD74CC60) while the finder kept returning the same
0x0D740070 - a different (or stale) car. That is why writing max over current repaired nothing
visible: it was repairing somebody else.

Layout (verified): 20 records, stride 0x34, CURRENT at +0x00, MAX at +0x04, integer tenths.

Identify the player's by its DAMAGE PATTERN. Ask the player what is hurt, then pick the array
whose damaged-record count matches - e.g. "only back armor" means exactly one record with
current < max.
"""
import ctypes, ctypes.wintypes as w, struct, sys, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
STRIDE, COUNT = 0x34, 20


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]


RW = (0x04, 0x40, 0x08, 0x80)


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

    def read(self, a, n):
        b = ctypes.create_string_buffer(n); g = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), b, n, ctypes.byref(g))
        return b.raw[:g.value]

    def u32(self, a):
        b = self.read(a, 4)
        return struct.unpack('<I', b)[0] if len(b) == 4 else 0

    def w32(self, a, v):
        b = struct.pack('<I', v); g = ctypes.c_size_t(0)
        return bool(k32.WriteProcessMemory(self.h, ctypes.c_void_p(a), b, 4, ctypes.byref(g)))

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
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    want = None
    if '--damaged' in sys.argv:
        want = int(sys.argv[sys.argv.index('--damaged') + 1])
    repair = '--repair' in sys.argv
    only = None
    if '--at' in sys.argv:
        only = int(sys.argv[sys.argv.index('--at') + 1], 16)

    span = STRIDE * (COUNT - 1) + 4 + 4
    found = []
    for base, size in p.regions():
        data = p.read(base, size)
        if len(data) < span:
            continue
        for o in range(4, len(data) - span, 4):
            mx = [struct.unpack_from('<I', data, o + k * STRIDE)[0] for k in range(COUNT)]
            if len(set(mx)) != 1:
                continue
            v = mx[0]
            if not (50 <= v <= 5000):
                continue
            cur = [struct.unpack_from('<I', data, o - 4 + k * STRIDE)[0] for k in range(COUNT)]
            if not all(0 <= c <= v for c in cur):
                continue
            dmg = sum(1 for c in cur if c != v)
            found.append((base + o - 4, v, dmg, cur))

    print(f"pid {pid}: {len(found)} armor arrays (one per vehicle)\n")
    for addr, v, dmg, cur in found:
        if only is not None and addr != only:
            continue
        if want is not None and dmg != want:
            continue
        print(f"  0x{addr:08X}  max={v} ({v/10:.1f})  {dmg} damaged")
        print("      " + ' '.join(f"{c:>4}" for c in cur))
        for i, c in enumerate(cur):
            if c != v:
                print(f"        idx {i:>2} @0x{addr + i*STRIDE:08X}  {c} / {v}"
                      f"   (-{(1-c/v)*100:.0f}%)")
        if repair:
            n = sum(1 for k in range(COUNT) if p.w32(addr + k * STRIDE, v))
            print(f"      repaired {n}/{COUNT}")
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
