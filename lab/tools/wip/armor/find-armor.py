"""
find-armor.py - locate the vehicle armor block by its SHAPE, not by a guessed offset.

A stock ABX Leprechaun leaves the chassis form with all four faces at armor 20.0 and chassis
20.0 - eight equal values sitting close together. That shape is rare, and searching for it
avoids having to know the record layout in advance.

Tries both encodings, because the existing note ("armor and chassis are integer TENTHS") was
never verified against a live value and a scan of the logic object for int 200 found nothing:
  * int32 200        (20.0 in tenths)
  * float 20.0
  * int32 20

Reports any region holding >= 4 matches within a short window, with the gaps between them, so a
regular stride is visible.
"""
import ctypes, ctypes.wintypes as w, struct, sys, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

RW = (0x04, 0x40, 0x08, 0x80)


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
    p = Proc(pid)
    regs = p.regions()
    print(f"pid {pid}, {len(regs)} writable regions")

    patterns = {
        'int 200 (tenths)': struct.pack('<I', 200),
        'float 20.0':       struct.pack('<f', 20.0),
        'int 20':           struct.pack('<I', 20),
    }
    WINDOW, MINHITS = 0x120, 4

    for label, pat in patterns.items():
        print(f"\n=== {label} ===")
        clusters = 0
        for base, size in regs:
            data = p.read(base, size)
            if not data:
                continue
            offs = []
            start = 0
            while True:
                i = data.find(pat, start)
                if i < 0:
                    break
                if i % 4 == 0:
                    offs.append(i)
                start = i + 1
            # group into windows
            i = 0
            while i < len(offs):
                j = i
                while j + 1 < len(offs) and offs[j + 1] - offs[i] <= WINDOW:
                    j += 1
                n = j - i + 1
                if n >= MINHITS:
                    grp = offs[i:j + 1]
                    gaps = [grp[k + 1] - grp[k] for k in range(len(grp) - 1)]
                    print(f"  0x{base + grp[0]:08X}  {n} hits  gaps {[hex(g) for g in gaps][:10]}")
                    clusters += 1
                    if clusters > 40:
                        print("  ... (truncated)")
                        break
                i = j + 1
            if clusters > 40:
                break
        if clusters == 0:
            print("  none")
    return 0


if __name__ == '__main__':
    sys.exit(main())
