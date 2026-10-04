"""
armor-repair-live.py - refill the player's armor by copying MAX over CURRENT.

Layout, established by diffing a single-face damage event against a snapshot taken seconds
earlier (prefront -> frontgone):

    array of 20 records, stride 0x34, sitting a few KB before the player entity
        +0x00   CURRENT value   (integer tenths - drops with damage, 0 = destroyed)
        +0x04   MAX value       (integer tenths - the .vcf configured armor, never moves)

The +0x04 column is why an earlier scan looked wrong: searching for "a run of identical values"
locks onto the MAX column, which reads a pristine 400 (40.0) even on a wrecked car. The live
damage state is the +0x00 column four bytes earlier.

Repair = write max over current for every record.
"""
import ctypes, ctypes.wintypes as w, struct, sys, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
STRIDE, COUNT = 0x34, 20
CUR, MAX = 0x00, 0x04


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


def find_array(p, ent):
    """the MAX column is a run of identical plausible values; CURRENT is 4 bytes before it."""
    span = STRIDE * (COUNT - 1) + 4
    best = None
    for base, size in p.regions():
        if ent and (base + size < ent - 0x20000 or base > ent + 0x20000):
            continue
        data = p.read(base, size)
        for o in range(0, max(0, len(data) - span), 4):
            mx = [struct.unpack_from('<I', data, o + k * STRIDE)[0] for k in range(COUNT)]
            if len(set(mx)) != 1:
                continue
            v = mx[0]
            if not (50 <= v <= 2000):
                continue
            cur_base = base + o - 4
            cur = [p.u32(cur_base + k * STRIDE) for k in range(COUNT)]
            if all(0 <= c <= v for c in cur):
                best = (cur_base, v, cur)
                break
        if best:
            break
    return best


def main():
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    root = p.u32(0x54A264)
    s = p.u32(root)
    ent = p.u32(s + 0x70) if s else 0
    print(f"pid {pid}  entity 0x{ent:X}")

    found = find_array(p, ent)
    if not found:
        print("armor array not found"); return 1
    base, mx, cur = found
    print(f"\narmor array @0x{base:08X}  stride 0x{STRIDE:X}  max={mx} ({mx/10:.1f})")
    print("  idx        addr   current      max")
    for k in range(COUNT):
        a = base + k * STRIDE
        print(f"  {k:>3} 0x{a:08X} {p.u32(a):>9} {p.u32(a+4):>8}"
              + ("   <-- DESTROYED" if p.u32(a) == 0 else ""))

    if '--write' not in sys.argv:
        print("\n(dry run - pass --write to repair)")
        return 0
    ok = 0
    for k in range(COUNT):
        a = base + k * STRIDE
        if p.w32(a, p.u32(a + 4)):
            ok += 1
    print(f"\nrepaired {ok}/{COUNT} records (current := max)")
    print("  now: " + ' '.join(str(p.u32(base + k * STRIDE)) for k in range(COUNT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
