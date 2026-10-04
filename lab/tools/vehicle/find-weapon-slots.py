"""
find-weapon-slots.py - locate the player's equipped-weapon slot array in I'76 memory.

Why this shape: guessing offsets inside the player entity / vehicle-logic object did not work
(scans of both for pointers into the static definition table returned zero hits, and an older
guess of "weapon arrays at logic +0xa71c" does not resolve on this build). So instead of
guessing where slots live, find the things slots must POINT AT, then find the pointers.

  1. read the static definition table (0x5D8800, stride 0xD8) for the names loaded this mission
  2. sweep every committed writable region for those name strings -> live weapon INSTANCES
  3. sweep every region again for dwords pointing at (or just inside) those instances
  4. report runs of such pointers at a regular stride - that shape IS a slot array

Traps this deliberately avoids:
  * VirtualQueryEx needs PROCESS_QUERY_INFORMATION (0x400) or it enumerates zero regions and
    you silently scan nothing.
  * Partial ReadProcessMemory at a region tail must be tolerated, not treated as failure -
    the PowerShell version returned "unreadable" for the whole entity because of this.
"""
import ctypes, ctypes.wintypes as w, struct, sys, collections

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
WRITABLE = (0x04, 0x40, 0x08, 0x80, 0x02, 0x20)   # incl. read-only, the def table is rdata-ish

TABLE_BASE, STRIDE, MAXREC = 0x5D8800, 0xD8, 64


def find_pid(name='i76.exe'):
    import subprocess
    out = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'],
                                  text=True, errors='ignore')
    for line in out.splitlines()[1:]:
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == name:
            return int(parts[1])
    return None


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not self.h:
            raise OSError(f"OpenProcess failed: {ctypes.get_last_error()}")

    def read(self, addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
        return buf.raw[:got.value]          # tolerate short reads

    def regions(self):
        addr, out = 0, []
        mbi = MBI()
        while addr < 0x7FFF0000:
            if not k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                      ctypes.sizeof(mbi)):
                break
            size = mbi.RegionSize or 0x1000
            if mbi.State == MEM_COMMIT and mbi.Protect in WRITABLE:
                out.append((mbi.BaseAddress or 0, size))
            addr = (mbi.BaseAddress or 0) + size
        return out


def cstr(b, off, maxlen=24):
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
        print("i76.exe not running"); return 1
    p = Proc(pid)
    print(f"pid {pid}")

    # 1. definitions loaded this mission
    defs = {}
    for i in range(MAXREC):
        va = TABLE_BASE + i * STRIDE
        b = p.read(va, 32)
        n = cstr(b, 0)
        if n:
            ammo = struct.unpack_from('<I', p.read(va + 0x7C, 4))[0] if len(p.read(va + 0x7C, 4)) == 4 else 0
            defs[va] = (n, ammo)
    print(f"definitions: {len(defs)}")
    for va, (n, a) in defs.items():
        print(f"   0x{va:X}  {n:<16} ammo={a}")
    names = sorted({n for n, _ in defs.values()}, key=len, reverse=True)
    if not names:
        print("no definitions - are you in a mission?"); return 1

    regs = p.regions()
    print(f"writable regions: {len(regs)}")

    # 2. every occurrence of a weapon name anywhere -> candidate instances
    occ = collections.defaultdict(list)      # name -> [addr,...]
    blobs = {}
    for base, size in regs:
        if size > 64 * 1024 * 1024:
            continue
        data = p.read(base, size)
        if not data:
            continue
        blobs[base] = data
        for nm in names:
            pat = nm.encode() + b'\x00'
            start = 0
            while True:
                i = data.find(pat, start)
                if i < 0:
                    break
                occ[nm].append(base + i)
                start = i + 1
    total = sum(len(v) for v in occ.values())
    print(f"\nname occurrences: {total}")
    for nm in names:
        if occ[nm]:
            sample = ', '.join(f"0x{a:X}" for a in occ[nm][:6])
            print(f"   {nm:<16} x{len(occ[nm]):<4} {sample}")

    # ignore the static table's own copies; we want heap instances
    heap_targets = set()
    for nm, addrs in occ.items():
        for a in addrs:
            if not (TABLE_BASE <= a < TABLE_BASE + MAXREC * STRIDE):
                heap_targets.add(a)
    print(f"\nheap-side name sites: {len(heap_targets)}")

    # 3. who points at those sites (or just before them - name is usually at +0)
    print("\n=== pointers into heap weapon objects ===")
    found = collections.defaultdict(list)
    windows = {}
    for t in heap_targets:
        for back in range(0, 0x81, 4):       # slot may point at object base, name at +0..0x80
            windows[t - back] = t
    for base, data in blobs.items():
        n = len(data) - 4
        for o in range(0, n, 4):
            v = struct.unpack_from('<I', data, o)[0]
            if v in windows:
                found[windows[v]].append((base + o, v))
    if not found:
        print("  none")
    for tgt, refs in sorted(found.items(), key=lambda kv: -len(kv[1]))[:12]:
        nm = ''
        for k, v in occ.items():
            if tgt in v:
                nm = k
        print(f"\n  target 0x{tgt:X} ({nm})  <- {len(refs)} refs")
        for a, v in refs[:10]:
            print(f"      from 0x{a:X}  (value 0x{v:X})")

    # 4. runs of nearby referrers = an array of slots
    print("\n=== referrer clusters (candidate SLOT ARRAYS) ===")
    allrefs = sorted(a for refs in found.values() for a, _ in refs)
    run = []
    for a in allrefs:
        if run and a - run[-1] <= 0x40:
            run.append(a)
        else:
            if len(run) >= 2:
                print(f"  0x{run[0]:X} .. 0x{run[-1]:X}   {len(run)} entries, "
                      f"stride ~{(run[-1]-run[0])//max(1,len(run)-1):#x}")
            run = [a]
    if len(run) >= 2:
        print(f"  0x{run[0]:X} .. 0x{run[-1]:X}   {len(run)} entries, "
              f"stride ~{(run[-1]-run[0])//max(1,len(run)-1):#x}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
