"""
find-live-armor2.py - find the armor fingerprint arranged at a CONSTANT STRIDE.

find-live-armor.py grouped hits by proximity within 0x100 and found only tightly packed copies:
  * 0x0310899C / 0x03184CA4 - stride 4, write STICKS but the HUD damage panel does not react
  * 0x072F9B1C / 0x07309B1C - stride 0x2C, write lands then the game RESTORES it within 300ms

Neither is the live value. The flaw was the window: the documented component record stride is
0x90, so eight faces span 0x480 and a 0x100 window can never see them. Search for a constant
stride directly instead of for proximity.

Requires a variant built with --armor-list 711,722,733,744,755,766,777,788.
"""
import ctypes, ctypes.wintypes as w, struct, sys, subprocess, collections

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

RW = (0x04, 0x40, 0x08, 0x80)
FP = [711, 722, 733, 744, 755, 766, 777, 788]
KNOWN = (0x0310899C, 0x03184CA4, 0x072F9B1C, 0x07309B1C, 0x072F7C70)


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
    print(f"pid {pid}, {len(regs)} regions; fingerprint {FP}\n")

    # address -> which face value lives there
    where = {}
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
                    where[base + j] = i
                s = j + 1
    print(f"total fingerprint sites: {len(where)}")
    addrs = sorted(where)

    print("\n=== 8 distinct faces at a CONSTANT stride ===")
    found = 0
    aset = set(addrs)
    for a in addrs:
        if where[a] != 0:          # anchor on face 0 (711) to avoid duplicate reports
            continue
        for stride in range(4, 0x201, 4):
            seq = [a + k * stride for k in range(8)]
            if not all(s in aset for s in seq):
                continue
            faces = [where[s] for s in seq]
            if sorted(faces) != list(range(8)):
                continue
            tag = '  <-- already rejected' if any(abs(a - k) < 0x10 for k in KNOWN) else ''
            print(f"  0x{a:08X}  stride 0x{stride:X}   order {[FP[f] for f in faces]}{tag}")
            found += 1
            break
        if found > 30:
            print("  ... truncated")
            break
    if found == 0:
        print("  none - the live copy may not keep all 8 faces in one array,")
        print("  or may store them scaled/as float")

    # also: any stride where >=6 faces line up (in case one face is stored elsewhere)
    print("\n=== relaxed: >=6 distinct faces at a constant stride ===")
    shown = 0
    for a in addrs:
        for stride in (0x2C, 0x38, 0x48, 0x4C, 0x54, 0x58, 0x60, 0x90, 0xA0, 0xC4, 0x150):
            seq = [a + k * stride for k in range(8)]
            got = [where[s] for s in seq if s in aset]
            if len(set(got)) >= 6:
                tag = '  <-- already rejected' if any(abs(a - k) < 0x10 for k in KNOWN) else ''
                print(f"  0x{a:08X}  stride 0x{stride:X}  {len(set(got))} faces {[FP[f] for f in got]}{tag}")
                shown += 1
                break
        if shown > 20:
            print("  ... truncated")
            break
    return 0


if __name__ == '__main__':
    sys.exit(main())
