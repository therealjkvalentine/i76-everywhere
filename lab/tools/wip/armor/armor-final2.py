"""
armor-final2.py - the four-point test, plus plausibility and structural filters.

armor-final.py left 1,035 survivors, all packed into one low region (0x0009xxxx-0x0019xxxx)
holding pointer-shaped garbage (1993879792, 1688172, ...). That is a buffer being zeroed and
rebuilt with identical content, which passes "full -> 0 -> back to full" trivially.

Two more filters, both cheap and both things armor must satisfy:

  * PLAUSIBLE MAGNITUDE - an armor face is a modest number. The .vcf stores integer tenths
    (200 = 20.0, 900 = 90.0); live it is int or float but not 1.9 billion and not a pointer.
  * STRUCTURAL - armor belongs to the vehicle. Read the live player entity and vehicle-logic
    pointers and keep only candidates lying inside a plausible span of them. This is the filter
    that separates real vehicle state from unrelated buffers that happen to fit the pattern.

Reads the live process for the pointers, so run it while the game is still up.
"""
import json, os, struct, sys, ctypes, subprocess

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
WORLD_ROOT, ENT_OFF, LOGIC_OFF = 0x54A264, 0x70, 0x108


def find_pid():
    for name in ('i76.exe', 'nitro.exe'):
        out = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'],
                                      text=True, errors='ignore')
        for line in out.splitlines()[1:]:
            p = [x.strip('"') for x in line.split('","')]
            if len(p) > 1 and p[0].lower() == name:
                return int(p[1])
    return None


def live_pointers():
    pid = find_pid()
    if not pid:
        return None
    h = k32.OpenProcess(0x0010 | 0x0400, False, pid)
    if not h:
        return None

    def u32(a):
        b = ctypes.create_string_buffer(4); g = ctypes.c_size_t(0)
        k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, 4, ctypes.byref(g))
        return struct.unpack('<I', b.raw)[0] if g.value == 4 else 0
    root = u32(u32(WORLD_ROOT))
    ent = u32(root + ENT_OFF) if root else 0
    logic = u32(ent + LOGIC_OFF) if ent else 0
    return pid, ent, logic


def load(n):
    m = json.load(open(os.path.join(D, n + '.json')))
    return m, open(os.path.join(D, n + '.bin'), 'rb')


def plausible(i, f):
    if 1 <= i <= 20000:
        return True
    return f == f and 0.5 <= f <= 20000.0


def main():
    lp = live_pointers()
    if lp:
        pid, ent, logic = lp
        print(f"live pid {pid}  player entity 0x{ent:X}  vehicle logic 0x{logic:X}")
    else:
        ent = logic = 0
        print("game not running - structural filter disabled")

    ma, fa = load('full')
    mh, fh = load('hurt')
    mx, fx = load('fixed')
    churn = set()
    cp = os.path.join(D, 'churn.json')
    if os.path.exists(cp):
        churn = set(json.load(open(cp))['hits'])

    hmap = {b: (o, l) for b, l, o in mh['index']}
    xmap = {b: (o, l) for b, l, o in mx['index']}
    hits = []
    for base, ln, off in ma['index']:
        if base not in hmap or base not in xmap:
            continue
        oh, lh = hmap[base]
        ox, lx = xmap[base]
        n = min(ln, lh, lx)
        fa.seek(off); A = fa.read(n)
        fh.seek(oh);  H = fh.read(n)
        fx.seek(ox);  X = fx.read(n)
        for o in range(0, n - 4, 4):
            wa = A[o:o + 4]
            if wa == b'\x00\x00\x00\x00':
                continue
            if H[o:o + 4] != b'\x00\x00\x00\x00' or X[o:o + 4] != wa:
                continue
            addr = base + o
            if str(addr) in churn:
                continue
            i = struct.unpack('<I', wa)[0]
            f = struct.unpack('<f', wa)[0]
            if not plausible(i, f):
                continue
            hits.append((addr, i, f))

    print(f"\nafter plausibility: {len(hits)}")
    near = [h for h in hits
            if (ent and ent - 0x2000 <= h[0] <= ent + 0x8000)
            or (logic and logic - 0x2000 <= h[0] <= logic + 0x30000)]
    print(f"of those, inside the entity/logic span: {len(near)}\n")

    show = near if near else hits
    label = 'STRUCTURAL HITS' if near else 'all plausible (none near the vehicle)'
    print(f"=== {label} ===")
    for addr, i, f in show[:60]:
        fs = f"{f:.3f}" if f == f and 1e-6 < abs(f) < 1e9 else ''
        rel = ''
        if ent and ent - 0x2000 <= addr <= ent + 0x8000:
            rel = f"  entity+0x{addr-ent:X}"
        elif logic and logic - 0x2000 <= addr <= logic + 0x30000:
            rel = f"  logic+0x{addr-logic:X}"
        print(f"  0x{addr:08X}  int={i:<8} float={fs:<10}{rel}")
    if len(show) > 60:
        print(f"  ... and {len(show)-60} more")

    print("\n=== clusters within 0x200 ===")
    addrs = [h[0] for h in show]
    i0, shown = 0, 0
    while i0 < len(addrs):
        j = i0
        while j + 1 < len(addrs) and addrs[j + 1] - addrs[i0] <= 0x200:
            j += 1
        if j - i0 + 1 >= 2:
            g = addrs[i0:j + 1]
            gaps = [g[k + 1] - g[k] for k in range(len(g) - 1)]
            print(f"  0x{g[0]:08X}  n={len(g)}  gaps {[hex(x) for x in gaps][:10]}")
            shown += 1
        i0 = j + 1
    if not shown:
        print("  none")
    return 0


if __name__ == '__main__':
    sys.exit(main())
