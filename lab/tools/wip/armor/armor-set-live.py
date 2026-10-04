"""
armor-set-live.py - find the armor array in the LIVE game and (optionally) refill it.

The claim being tested: armor is a run of 20 int32 at stride 0x34, stored as integer TENTHS
(400 = 40.0), in a heap allocation that is re-created every time the regen respawns the car.

This is the only honest test of that claim - write the values and look at the damage panel.

Note the scan allows ZERO entries, unlike the snapshot version: with front armor and chassis
destroyed the array contains 0s, and a filter demanding 1..2000 would skip the very array we
want.

  armor-set-live.py                 list candidate arrays
  armor-set-live.py --write         set every entry of the best candidate to its max
  armor-set-live.py --write --all   set every entry of EVERY candidate
  armor-set-live.py --value 400     use an explicit value instead of the observed max
"""
import ctypes, ctypes.wintypes as w, struct, sys, subprocess, collections

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
STRIDE, COUNT = 0x34, 20


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]


RW = (0x04, 0x40, 0x08, 0x80)


def find_pid():
    for name in ('i76.exe', 'nitro.exe'):
        out = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'],
                                      text=True, errors='ignore')
        for line in out.splitlines()[1:]:
            p = [x.strip('"') for x in line.split('","')]
            if len(p) > 1 and p[0].lower() == name:
                return int(p[1])
    return None


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(0x0010 | 0x0020 | 0x0008 | 0x0400, False, pid)
        if not self.h:
            raise OSError(f"OpenProcess failed: {ctypes.get_last_error()}")

    def read(self, a, n):
        b = ctypes.create_string_buffer(n); g = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), b, n, ctypes.byref(g))
        return b.raw[:g.value]

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
    force = None
    if '--value' in sys.argv:
        force = int(sys.argv[sys.argv.index('--value') + 1])

    # Anchor near the player entity. A whole-process scan of this shape returns ~21,000
    # candidates (texture and audio blobs match a run of small ints trivially), so restrict to
    # the vehicle's neighbourhood - in the captured sessions the array sat within a few KB of
    # the entity.
    root = struct.unpack('<I', p.read(0x54A264, 4))[0]
    s = struct.unpack('<I', p.read(root, 4))[0] if root else 0
    ent = struct.unpack('<I', p.read(s + 0x70, 4))[0] if s else 0
    print(f"player entity 0x{ent:X}")
    WIN = 0x20000
    lo, hi = (ent - WIN, ent + WIN) if ent else (0, 0)

    span = STRIDE * (COUNT - 1) + 4
    cands = []
    for base, size in p.regions():
        if ent and (base + size < lo or base > hi):
            continue
        data = p.read(base, size)
        if len(data) < span:
            continue
        for o in range(0, len(data) - span, 4):
            vals = [struct.unpack_from('<I', data, o + k * STRIDE)[0] for k in range(COUNT)]
            if not all(0 <= v <= 2000 for v in vals):
                continue
            nz = [v for v in vals if v]
            if len(nz) < 8:
                continue
            c = collections.Counter(nz)
            top, n = c.most_common(1)[0]
            if top < 50 or n < 8:
                continue
            cands.append((base + o, top, n, vals))

    print(f"pid {pid}: {len(cands)} candidate arrays\n")
    for addr, top, n, vals in cands[:8]:
        dmg = sum(1 for v in vals if v != top)
        print(f"  0x{addr:08X}  max={top} ({top/10:.1f})  {n}/{COUNT} at max, {dmg} differ")
        print("      " + ' '.join(f"{v:>4}" for v in vals))
    if not cands:
        print("  none found - the shape assumption may be wrong")
        return 1

    if '--write' not in sys.argv:
        print("\n(dry run - pass --write to refill)")
        return 0

    targets = cands if '--all' in sys.argv else cands[:1]
    for addr, top, n, vals in targets:
        val = force if force else top
        ok = 0
        for k in range(COUNT):
            if p.w32(addr + k * STRIDE, val):
                ok += 1
        after = [struct.unpack('<I', p.read(addr + k * STRIDE, 4))[0] for k in range(COUNT)]
        print(f"\nwrote {val} ({val/10:.1f}) to {ok}/{COUNT} slots at 0x{addr:08X}")
        print("      " + ' '.join(f"{v:>4}" for v in after))
    return 0


if __name__ == '__main__':
    sys.exit(main())
