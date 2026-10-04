"""
dump-weapon-slots.py - resolve a vehicle's weapon SLOT ARRAY and walk back to its owner.

find-weapon-slots.py located the shape: a run of adjacent dwords, each pointing at a live
weapon INSTANCE object whose name string sits at instance+0x40. Two adjacent slots holding
Oil Slick + 30cal MG match the player's loadout on the driver entry form.

This script dumps the array around a given address, names every slot, then searches memory for
whoever points at the array so the chain back to the vehicle can be established.
"""
import ctypes, ctypes.wintypes as w, struct, sys, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

WRITABLE = (0x04, 0x40, 0x08, 0x80, 0x02, 0x20)
TABLE_BASE, STRIDE, MAXREC = 0x5D8800, 0xD8, 64
NAME_OFF = 0x40          # instance base -> name string


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

    def read(self, addr, n):
        buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
        return buf.raw[:got.value]

    def u32(self, a):
        b = self.read(a, 4)
        return struct.unpack('<I', b)[0] if len(b) == 4 else 0

    def regions(self):
        addr, out, mbi = 0, [], MBI()
        while addr < 0x7FFF0000:
            if not k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                      ctypes.sizeof(mbi)):
                break
            size = mbi.RegionSize or 0x1000
            if mbi.State == 0x1000 and mbi.Protect in WRITABLE:
                out.append((mbi.BaseAddress or 0, size))
            addr = (mbi.BaseAddress or 0) + size
        return out


def cstr(b, off=0, maxlen=24):
    s = []
    for i in range(off, min(off + maxlen, len(b))):
        c = b[i]
        if c == 0:
            break
        if c < 32 or c > 126:
            return ''
        s.append(chr(c))
    return ''.join(s)


def main():
    pid = find_pid()
    p = Proc(pid)
    center = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0xC57C364
    span = 0x60

    print(f"pid {pid}   slot array around 0x{center:X}\n")
    lo = center - span
    print(f"{'addr':>10}  {'value':>10}  weapon")
    for a in range(lo, center + span, 4):
        v = p.u32(a)
        nm = ''
        if 0x400000 < v < 0x40000000:
            nm = cstr(p.read(v + NAME_OFF, 24))
        mark = ' <<<' if a == center else ''
        if nm:
            print(f"0x{a:08X}  0x{v:08X}  {nm}{mark}")
        else:
            print(f"0x{a:08X}  0x{v:08X}{mark}")

    # who points at this array?
    print("\n=== referrers to the slot array ===")
    targets = {center - k * 4: k for k in range(0, 9)}
    regs = p.regions()
    hits = []
    for base, size in regs:
        if size > 64 * 1024 * 1024:
            continue
        data = p.read(base, size)
        for o in range(0, max(0, len(data) - 4), 4):
            v = struct.unpack_from('<I', data, o)[0]
            if v in targets:
                hits.append((base + o, v, targets[v]))
    for a, v, k in hits[:25]:
        print(f"  0x{a:08X} -> 0x{v:08X}  (array base - {k} slots)")
    if not hits:
        print("  none")

    # cross-check against the player entity
    root = p.u32(p.u32(0x54A264))
    player = p.u32(root + 0x70)
    logic = p.u32(player + 0x108)
    print(f"\nplayer entity = 0x{player:X}   vehicle logic = 0x{logic:X}")
    for a, v, k in hits:
        if player <= a < player + 0x2000:
            print(f"  *** referrer 0x{a:X} is INSIDE the player entity at +0x{a-player:X}")
        if logic and logic <= a < logic + 0x20000:
            print(f"  *** referrer 0x{a:X} is INSIDE the vehicle logic at +0x{a-logic:X}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
