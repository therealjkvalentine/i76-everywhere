"""
armor-watch.py - snapshot/compare live memory across NARRATED events.

Built for a guided session: the player takes damage, then drives onto the healing building. The
decisive signature is a value that goes DOWN on damage and back UP on heal. Almost nothing else
in memory does both, which is far stronger than any constraint available unattended.

Why this shape rather than another auto-scanner:
  * the live armor encoding is unknown - searches for the configured number as int32, float
    711.0 and float 71.1 all found nothing that behaves like armor, so the engine converts at
    load. Everything here is tested as BOTH int32 and float32.
  * every self-service damage stimulus tried was unreliable (AI fire: 35 s with no change at
    all; wall grinding: nothing; own landmines: inconclusive). A narrated event removes that.

Attaches to whichever i76.exe / nitro.exe is running, from ANY install path - the harness's
usual Get-GamePid filters to the sandbox copy and would silently match nothing.

  armor-watch.py snap  A                  save a snapshot
  armor-watch.py cmp   A B down           addresses that DECREASED  -> cand.json
  armor-watch.py cmp   A B up             addresses that INCREASED
  armor-watch.py keep  B up               of the saved candidates, those that rose since B
  armor-watch.py show                     print current values of the saved candidates
"""
import ctypes, ctypes.wintypes as w, struct, sys, os, json, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')
CAND = os.path.join(DIR, 'cand.json')

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]

RW = (0x04, 0x40, 0x08, 0x80)


def find_proc():
    """any i76/nitro, regardless of install path."""
    for name in ('i76.exe', 'nitro.exe'):
        out = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'],
                                      text=True, errors='ignore')
        for line in out.splitlines()[1:]:
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) > 1 and parts[0].lower() == name:
                return name, int(parts[1])
    return None, None


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not self.h:
            raise OSError(f"OpenProcess failed ({ctypes.get_last_error()}) - "
                          "run this shell as the same user as the game")

    def read(self, a, n):
        b = ctypes.create_string_buffer(n); g = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), b, n, ctypes.byref(g))
        return b.raw[:g.value]

    def word(self, a):
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


def nums(b):
    return struct.unpack('<I', b)[0], struct.unpack('<f', b)[0]


def ok_int(v):
    return 1 <= v <= 200000


def ok_float(v):
    return 0.01 < v < 200000.0 and v == v


def snap(name):
    exe, pid = find_proc()
    if not pid:
        print("no i76.exe / nitro.exe running"); return 1
    p = Proc(pid)
    os.makedirs(DIR, exist_ok=True)
    regs = p.regions()
    path = os.path.join(DIR, name + '.bin')
    idx = []
    with open(path, 'wb') as f:
        for base, size in regs:
            d = p.read(base, size)
            if not d:
                continue
            idx.append([base, len(d), f.tell()])
            f.write(d)
    json.dump({'pid': pid, 'exe': exe, 'index': idx},
              open(os.path.join(DIR, name + '.json'), 'w'))
    print(f"{exe} pid {pid}: snapshot '{name}' - {len(idx)} regions, "
          f"{os.path.getsize(path)/1e6:.1f} MB")
    return 0


def load(name):
    meta = json.load(open(os.path.join(DIR, name + '.json')))
    f = open(os.path.join(DIR, name + '.bin'), 'rb')
    return meta, f


def cmp_snaps(a, b, direction):
    ma, fa = load(a)
    mb, fb = load(b)
    if ma['pid'] != mb['pid']:
        print(f"WARNING: different pids ({ma['pid']} vs {mb['pid']}) - addresses will not match")
    bmap = {base: (off, ln) for base, ln, off in mb['index']}
    out = []
    for base, ln, off in ma['index']:
        if base not in bmap:
            continue
        offb, lnb = bmap[base]
        n = min(ln, lnb)
        fa.seek(off); da = fa.read(n)
        fb.seek(offb); db = fb.read(n)
        for o in range(0, n - 4, 4):
            wa, wb = da[o:o+4], db[o:o+4]
            if wa == wb:
                continue
            ia, fva = nums(wa)
            ib, fvb = nums(wb)
            if ok_int(ia) and ok_int(ib) and ((ib < ia) if direction == 'down' else (ib > ia)):
                out.append([base + o, 'int', ib])
            elif ok_float(fva) and ok_float(fvb) and ((fvb < fva) if direction == 'down' else (fvb > fva)):
                out.append([base + o, 'float', fvb])
    os.makedirs(DIR, exist_ok=True)
    json.dump({'pid': mb['pid'], 'cands': out}, open(CAND, 'w'))
    print(f"{len(out)} addresses went {direction.upper()} between '{a}' and '{b}'  -> cand.json")
    for a_, k, v in out[:25]:
        print(f"  0x{a_:08X}  {k:<5} {v}")
    return 0


def keep(base_snap, direction):
    """of the saved candidates, keep those that moved `direction` since snapshot base_snap."""
    c = json.load(open(CAND))
    exe, pid = find_proc()
    p = Proc(pid)
    meta, f = load(base_snap)
    bmap = {b: (o, l) for b, l, o in meta['index']}
    kept = []
    for addr, kind, _ in c['cands']:
        # value at base_snap
        old = None
        for b, (o, l) in bmap.items():
            if b <= addr < b + l - 4:
                f.seek(o + (addr - b)); old = f.read(4); break
        cur = p.word(addr)
        if old is None or cur is None:
            continue
        oi, of_ = nums(old); ci, cf = nums(cur)
        if kind == 'int' and ok_int(ci) and ((ci > oi) if direction == 'up' else (ci < oi)):
            kept.append([addr, kind, ci])
        elif kind == 'float' and ok_float(cf) and ((cf > of_) if direction == 'up' else (cf < of_)):
            kept.append([addr, kind, cf])
    json.dump({'pid': pid, 'cands': kept}, open(CAND, 'w'))
    print(f"{len(kept)} of {len(c['cands'])} candidates went {direction.upper()} since '{base_snap}'")
    for a_, k, v in kept[:40]:
        print(f"  0x{a_:08X}  {k:<5} {v}")
    return 0


def show():
    c = json.load(open(CAND))
    exe, pid = find_proc()
    p = Proc(pid)
    for addr, kind, _ in c['cands'][:60]:
        b = p.word(addr)
        if b is None:
            continue
        i, fv = nums(b)
        print(f"  0x{addr:08X}  {kind:<5} int={i} float={fv:.4f}")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    cmd = sys.argv[1]
    if cmd == 'snap':
        return snap(sys.argv[2])
    if cmd == 'cmp':
        return cmp_snaps(sys.argv[2], sys.argv[3], sys.argv[4])
    if cmd == 'keep':
        return keep(sys.argv[2], sys.argv[3])
    if cmd == 'show':
        return show()
    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main())
