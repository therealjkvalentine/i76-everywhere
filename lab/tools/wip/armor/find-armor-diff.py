"""
find-armor-diff.py - find armor by letting the car TAKE damage and diffing.

Searching for "eight equal 20.0 faces" failed: by the time you are in a melee the AI has
already shot you, so the faces are no longer equal (the HUD damage panel showed the left side
red before anything was written). Worse, a cluster that merely *looks* like armor proved not to
be - writing 20 into 0x030F7234's four 200s did not change the damage panel at all.

So do it the way ammo was cracked: apply the stimulus, diff, and demand a shape that noise
cannot fake.

    snapshot -> take fire for N seconds -> snapshot

Armor must DECREASE, sit in a plausible magnitude, and - the part that kills coincidences -
have siblings at a REGULAR STRIDE, because the four faces are an array. Anything reported here
still has to be confirmed by writing and watching the HUD damage panel; several candidates will
be the AI cars' armor rather than the player's.
"""
import ctypes, ctypes.wintypes as w, struct, sys, time, subprocess, collections

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

RW = (0x04, 0x40, 0x08, 0x80)
LO, HI = 1, 400            # armor magnitude: 20.0 stock -> 200 tenths


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
        return struct.unpack('<I', b)[0] if len(b) == 4 else None

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
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    regs = p.regions()
    print(f"pid {pid}, {len(regs)} regions")
    print(f"snapshot A, then TAKE FIRE for {wait}s (leave the game alone; AI will shoot)")
    A = {b: p.read(b, s) for b, s in regs}
    time.sleep(wait)
    B = {b: p.read(b, s) for b, s in regs}

    dec = []
    for base, size in regs:
        a, b = A.get(base), B.get(base)
        if not a or not b:
            continue
        n = min(len(a), len(b)) - 4
        for o in range(0, n, 4):
            va = struct.unpack_from('<I', a, o)[0]
            vb = struct.unpack_from('<I', b, o)[0]
            if LO <= vb < va <= HI:
                dec.append((base + o, va, vb))
    print(f"\ndecreased and in [{LO},{HI}]: {len(dec)}")

    # the discriminator: siblings at a regular stride (4 faces = an array)
    addrs = {a for a, _, _ in dec}
    print("\n=== decreasing values that sit in a regular-stride array ===")
    shown = 0
    byaddr = {a: (va, vb) for a, va, vb in dec}
    for a, va, vb in sorted(dec):
        for stride in (0x38, 0x40, 0x4C, 0x54, 0x58, 0x60, 0x90):
            sibs = [a + k * stride for k in range(1, 4)]
            # siblings need not have decreased, but must be plausible armor values
            vals = [p.u32(s) for s in sibs]
            if all(v is not None and LO <= v <= HI for v in vals):
                print(f"  0x{a:08X}  {va}->{vb}   stride 0x{stride:X}  siblings {vals}")
                shown += 1
                break
        if shown > 25:
            print("  ... truncated")
            break
    if shown == 0:
        print("  none - widen LO/HI or take more damage")
    print("\nCONFIRM by writing and watching the HUD damage panel:")
    print("  tools/test-armor-candidate.ps1 -Addr 0x... -Stride 0x... -Count 4")
    return 0


if __name__ == '__main__':
    sys.exit(main())
