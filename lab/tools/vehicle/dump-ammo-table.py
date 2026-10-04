"""
dump-ammo-table.py - enumerate the live weapon/ammo table and name every slot.

Established live (see docs/WEAPONS-MEMORY.md):
    array base   0x005AAB0C
    stride       0x4C
    ammo         +0x1C        <- writing this moves the HUD, verified
    +0x00/+0x04  pointers (this script resolves them to find the weapon identity)

Restores ammo to a given value with --set so a test run does not leave 7777 on the HUD.
"""
import ctypes, struct, sys, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
BASE, STRIDE, AMMO_OFF = 0x005AAB0C, 0x4C, 0x1C
DEF_TABLE, DEF_STRIDE, DEF_MAX = 0x5D8800, 0xD8, 64
NAME_AT_INSTANCE = 0x40


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
        self.h = k32.OpenProcess(0x0010 | 0x0020 | 0x0400 | 0x0008, False, pid)

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
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    setval = None
    if '--set' in sys.argv:
        setval = int(sys.argv[sys.argv.index('--set') + 1])
    count = 16

    print(f"pid {pid}   base 0x{BASE:X}  stride 0x{STRIDE:X}  ammo +0x{AMMO_OFF:X}\n")
    print(f"{'slot':>4} {'ammo addr':>12} {'ammo':>12}  {'p0':>10} {'p1':>10}  name")
    for i in range(count):
        rec = BASE + i * STRIDE
        aa = rec + AMMO_OFF
        ammo = p.u32(aa)
        p0, p1 = p.u32(rec), p.u32(rec + 4)
        # try to name it: follow either pointer and look for a string at the known offsets
        name = ''
        for ptr in (p0, p1):
            if 0x400000 < ptr < 0x40000000:
                for off in (0, NAME_AT_INSTANCE, 0x3C, 0x44):
                    s = cstr(p.read(ptr + off, 24))
                    if s and any(ch.isalpha() for ch in s) and len(s) >= 4:
                        name = f"{s} (@+0x{off:X})"
                        break
            if name:
                break
        shown = 'unlimited' if ammo == 0x0FFFFFFF else str(ammo)
        print(f"{i:4} 0x{aa:010X} {shown:>12}  0x{p0:08X} 0x{p1:08X}  {name}")
        if setval is not None and 0 < ammo != 0x0FFFFFFF:
            p.w32(aa, setval)
    if setval is not None:
        print(f"\nset all non-empty, non-unlimited slots to {setval}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
