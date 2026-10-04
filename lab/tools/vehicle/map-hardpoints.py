"""
map-hardpoints.py - which number key fires which weapon, read from the ammo table.

Far better than screenshotting the HUD: the live ammo array is already mapped
(0x005AAB0C, stride 0x4C, ammo at +0x1C - see docs/WEAPONS-MEMORY.md), so press a key and see
exactly which slot decremented, by name.

Also doubles as a self-damage tool: dropping landmines and reversing over them is the only
reliable way found so far to damage your own car on demand (AI fire is unreliable, and grinding
a wall at low speed does almost nothing).
"""
import ctypes, struct, sys, time, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
u32 = ctypes.WinDLL('user32', use_last_error=True)
BASE, STRIDE, AMMO = 0x005AAB0C, 0x4C, 0x1C
NSLOT = 12


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
        return struct.unpack('<I', b)[0] if len(b) == 4 else 0


def cstr(b, off=0, n=24):
    s = []
    for i in range(off, min(off + n, len(b))):
        c = b[i]
        if c == 0:
            break
        if c < 32 or c > 126:
            return ''
        s.append(chr(c))
    return ''.join(s)


def snapshot(p):
    return [p.u32(BASE + i * STRIDE + AMMO) for i in range(NSLOT)]


def names(p):
    out = []
    for i in range(NSLOT):
        ptr = p.u32(BASE + i * STRIDE)
        out.append(cstr(p.read(ptr, 24)) if 0x400000 < ptr < 0x40000000 else '')
    return out


def tap(vk, times=5, hold=0.06):
    sc = u32.MapVirtualKeyW(vk, 0)
    for _ in range(times):
        u32.keybd_event(vk, sc, 0x8, 0)
        time.sleep(hold)
        u32.keybd_event(vk, sc, 0x8 | 0x2, 0)
        time.sleep(0.22)


def main():
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    nm = names(p)
    print("slot names:", [f"{i}:{n}" for i, n in enumerate(nm) if n])
    print()
    for n in range(1, 6):
        before = snapshot(p)
        tap(0x30 + n, times=5)
        time.sleep(0.5)
        after = snapshot(p)
        moved = [(i, before[i], after[i]) for i in range(NSLOT)
                 if before[i] != after[i] and before[i] != 0x0FFFFFFF]
        if moved:
            for i, b, a in moved:
                print(f"  key '{n}'  -> slot {i} ({nm[i] or '?'})  {b} -> {a}   (-{b-a})")
        else:
            print(f"  key '{n}'  -> nothing fired")
    return 0


if __name__ == '__main__':
    sys.exit(main())
