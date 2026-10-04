"""
find-live-armor.py - locate the LIVE (real-time, damageable) armor values in memory.

Earlier attempts failed because they searched for the stock value 200, which appears everywhere;
two clusters that looked perfect (0x030F7234, 0x04C1B570) were rejected by writing to them and
seeing the HUD damage panel not react.

New leverage: the car config is a file we can edit (docs/CAR-CONFIG.md). So plant a FINGERPRINT
- eight distinct improbable numbers, one per face - and look for that exact pattern. This pins
the block immediately and also reveals the field ORDER in memory, which need not match the file.

Also searches float and tenths-scaled forms, since the file stores tenths but the live copy may
be a float in real units (711 -> 71.1).

Run after entering a mission with a variant built by:
  make-test-variant.py src dst --armor-list 711,722,733,744,755,766,777,788
"""
import ctypes, ctypes.wintypes as w, struct, sys, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

RW = (0x04, 0x40, 0x08, 0x80)
FINGERPRINT = [711, 722, 733, 744, 755, 766, 777, 788]


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
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    regs = p.regions()
    print(f"pid {pid}, {len(regs)} writable regions")
    print(f"fingerprint {FINGERPRINT}\n")

    # every encoding the live copy might use
    forms = {
        'int tenths': [struct.pack('<I', v) for v in FINGERPRINT],
        'float tenths': [struct.pack('<f', float(v)) for v in FINGERPRINT],
        'float real': [struct.pack('<f', v / 10.0) for v in FINGERPRINT],
    }

    for label, pats in forms.items():
        print(f"=== {label} ===")
        hits = {i: [] for i in range(8)}
        for base, size in regs:
            data = p.read(base, size)
            if not data:
                continue
            for i, pat in enumerate(pats):
                start = 0
                while True:
                    j = data.find(pat, start)
                    if j < 0:
                        break
                    if j % 4 == 0:
                        hits[i].append(base + j)
                    start = j + 1
        total = sum(len(v) for v in hits.values())
        if total == 0:
            print("  no matches\n")
            continue
        for i in range(8):
            n = len(hits[i])
            s = ', '.join(f"0x{a:08X}" for a in hits[i][:6])
            print(f"  face {i} ({FINGERPRINT[i]}): {n:3} {s}")

        # the payoff: addresses of different faces that sit near each other = the live block
        print("  --- groups where >=4 different faces cluster within 0x100 ---")
        allhits = sorted((a, i) for i in range(8) for a in hits[i])
        n = len(allhits)
        k = 0
        shown = 0
        while k < n:
            j = k
            faces = {}
            while j < n and allhits[j][0] - allhits[k][0] <= 0x100:
                faces.setdefault(allhits[j][1], allhits[j][0])
                j += 1
            if len(faces) >= 4:
                order = sorted(faces.items(), key=lambda kv: kv[1])
                span = order[-1][1] - order[0][1]
                gaps = [order[m + 1][1] - order[m][1] for m in range(len(order) - 1)]
                print(f"    0x{order[0][1]:08X}  {len(faces)} faces, span 0x{span:X}, "
                      f"gaps {[hex(g) for g in gaps]}")
                print(f"      order in memory: {[FINGERPRINT[f] for f, _ in order]}")
                shown += 1
                if shown > 12:
                    print("    ... truncated")
                    break
            k = j if j > k else k + 1
        print()
    print("CONFIRM by writing one face low and watching the HUD damage panel:")
    print("  tools/test-armor-candidate.ps1 -Addr 0x... -Stride 0x4 -Count 8 -Value 50")
    return 0


if __name__ == '__main__':
    sys.exit(main())
