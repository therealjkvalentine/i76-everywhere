"""
dump-weapon-instance.py - annotate a live weapon INSTANCE object.

The static definition table (0x5D8800) holds stats and is NOT live state: writing its ammo
field does not change the HUD and firing does not decrement it. The live per-weapon object is
what a trainer needs, and it is where ammo should live.

Instance layout landmark found so far: the weapon NAME string sits at instance+0x40.

Prints every dword as hex / signed int / float, resolves pointers into the definition table,
and flags any string. Pass the instance address in hex.
"""
import ctypes, struct, sys, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
TABLE_BASE, STRIDE, MAXREC = 0x5D8800, 0xD8, 64


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


def cstr(b, off=0, maxlen=28):
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
    base = int(sys.argv[1], 16)
    n = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x140

    defs = {}
    for i in range(MAXREC):
        va = TABLE_BASE + i * STRIDE
        nm = cstr(p.read(va, 32))
        if nm:
            defs[va] = nm

    data = p.read(base, n)
    print(f"instance 0x{base:X}  ({len(data)} bytes)\n")
    print(f"{'off':>6} {'hex':>10} {'int':>12} {'float':>14}  note")
    for o in range(0, len(data) - 3, 4):
        v = struct.unpack_from('<I', data, o)[0]
        s = struct.unpack_from('<i', data, o)[0]
        f = struct.unpack_from('<f', data, o)[0]
        note = ''
        if v in defs:
            note = f"-> DEF '{defs[v]}'"
        elif 0x400000 < v < 0x40000000:
            t = cstr(p.read(v, 28))
            note = f"-> ptr, str '{t}'" if t else "-> ptr"
        txt = cstr(data, o, 16)
        if txt and len(txt) >= 3:
            note = (note + '  ' if note else '') + f"str '{txt}'"
        fs = f"{f:.4g}" if 1e-8 < abs(f) < 1e9 else ''
        print(f"+0x{o:03X} {v:10X} {s:12d} {fs:>14}  {note}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
