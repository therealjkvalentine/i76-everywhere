"""
armor-narrow.py - find live armor by ITERATIVE NARROWING, assuming nothing about the encoding.

Every previous attempt assumed the live value looked like the configured one. It does not:
searches for int 711, float 711.0 and float 71.1 all fail to find anything that behaves like
live armor, so the engine converts at load. The fingerprint trick therefore only ever finds
config/template copies.

So drop the assumption. Classic narrowing:

    round 1: snapshot, take damage, snapshot -> keep everything that DECREASED
    round N: take damage again              -> keep only what decreased AGAIN

Coincidences do not survive three or four consecutive rounds. Values are tested as BOTH int32
and float32, because the encoding is exactly what we do not know.

Damage source: AI cars. Unreliable per-second, but it is the only stimulus verified to actually
damage the player (the HUD panel went red on the left). Sit still and let them work - driving
adds position/velocity churn that inflates the candidate set for no benefit.

Usage: armor-narrow.py [seconds_per_round] [rounds]
"""
import ctypes, ctypes.wintypes as w, struct, sys, time, subprocess

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

    def raw(self, a):
        b = self.read(a, 4)
        return b if len(b) == 4 else None

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


def as_num(b):
    """(int_value, float_value) for a 4-byte word."""
    i = struct.unpack('<I', b)[0]
    f = struct.unpack('<f', b)[0]
    return i, f


def plausible_int(v):
    return 1 <= v <= 100000


def plausible_float(v):
    return 0.05 < v < 100000.0 and v == v      # NaN fails the equality, as it should


def main():
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    regs = p.regions()
    print(f"pid {pid}, {len(regs)} writable regions")

    print(f"\nround 1: baseline, then {secs}s of taking fire (sit still)")
    A = {b: p.read(b, s) for b, s in regs}
    time.sleep(secs)
    B = {b: p.read(b, s) for b, s in regs}

    cand = {}          # addr -> (last_int, last_float, kind)
    for base, size in regs:
        a, b = A.get(base), B.get(base)
        if not a or not b:
            continue
        n = min(len(a), len(b)) - 4
        for o in range(0, n, 4):
            wa, wb = a[o:o + 4], b[o:o + 4]
            if wa == wb:
                continue
            ia, fa = as_num(wa)
            ib, fb = as_num(wb)
            if plausible_int(ia) and plausible_int(ib) and ib < ia:
                cand[base + o] = (ib, fb, 'int')
            elif plausible_float(fa) and plausible_float(fb) and fb < fa:
                cand[base + o] = (ib, fb, 'float')
    print(f"  survivors: {len(cand)}")
    if not cand:
        print("  nothing decreased - the car took no damage. Check AI drivers > 0.")
        return 1

    for r in range(2, rounds + 1):
        print(f"round {r}: {secs}s more fire")
        time.sleep(secs)
        nxt = {}
        for addr, (li, lf, kind) in cand.items():
            raw = p.raw(addr)
            if raw is None:
                continue
            i, f = as_num(raw)
            if kind == 'int' and plausible_int(i) and i < li:
                nxt[addr] = (i, f, kind)
            elif kind == 'float' and plausible_float(f) and f < lf:
                nxt[addr] = (i, f, kind)
        cand = nxt
        print(f"  survivors: {len(cand)}")
        if not cand:
            print("  all eliminated - the car may have stopped taking damage")
            return 1
        if len(cand) <= 40:
            break

    print(f"\n=== {len(cand)} survivors after consecutive decreases ===")
    for addr, (i, f, kind) in sorted(cand.items())[:40]:
        shown = f"{i}" if kind == 'int' else f"{f:.3f}"
        print(f"  0x{addr:08X}  {kind:<5} now {shown}")
    print("\nNEXT: poke-probe.ps1 each - live armor is writable and the write STICKS.")
    print("Then raise it and confirm the HUD damage panel turns green.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
