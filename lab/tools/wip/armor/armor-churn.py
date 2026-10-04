"""
armor-churn.py - subtract everything that moves on its own, then keep what rises on a heal.

Two flaws in the first pass, both mine:

1. Filtering to "was ~0, now large" only catches DESTROYED faces. Round 2's front was merely
   damaged (yellow, not zero), so that filter would have EXCLUDED the real armor. Use
   "increased" instead.

2. Intersecting two heals still left 1,449 addresses, and the survivors were obviously terrain:
   ascending floats like 4270.00, 4275.00 ... paired with 49317.45 - world X/Z of a road strip
   being repopulated after the regen respawns the car.

The fix is the discriminator that cracked live ammo: armor is EXACTLY CONSTANT when nothing is
happening to it. Terrain, position, velocity, particles and animation all churn continuously
while you merely drive. So:

    churn  = anything that changes while driving normally (no damage, no heal)
    armor ⊆ (rose across heal #1) ∩ (rose across heal #2) − churn

Usage:
  armor-churn.py rose  <damaged> <healed> <out.json>     addresses that INCREASED
  armor-churn.py churn <a> <b> <out.json>                addresses that CHANGED at all
  armor-churn.py solve <rose1.json> <rose2.json> --minus <churn.json> [...]
"""
import struct, json, os, sys

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')


def load(name):
    meta = json.load(open(os.path.join(DIR, name + '.json')))
    return meta, open(os.path.join(DIR, name + '.bin'), 'rb')


def walk(a, b):
    ma, fa = load(a)
    mb, fb = load(b)
    if ma['pid'] != mb['pid']:
        print(f"pid mismatch {ma['pid']} vs {mb['pid']}")
        return None, None
    bmap = {base: (off, ln) for base, ln, off in mb['index']}
    for base, ln, off in ma['index']:
        if base not in bmap:
            continue
        ob, lb = bmap[base]
        n = min(ln, lb)
        fa.seek(off); da = fa.read(n)
        fb.seek(ob);  db = fb.read(n)
        yield base, da, db, n


def collect(a, b, out, mode):
    res = {}
    for base, da, db, n in walk(a, b):
        for o in range(0, n - 4, 4):
            wa, wb = da[o:o + 4], db[o:o + 4]
            if wa == wb:
                continue
            if mode == 'churn':
                res[str(base + o)] = 1
                continue
            ia = struct.unpack_from('<I', wa)[0]
            ib = struct.unpack_from('<I', wb)[0]
            if 0 <= ia < ib <= 100000:
                res[str(base + o)] = ['int', ia, ib]
                continue
            x = struct.unpack_from('<f', wa)[0]
            y = struct.unpack_from('<f', wb)[0]
            if x == x and y == y and 0 <= x < y < 100000.0:
                res[str(base + o)] = ['float', round(x, 3), round(y, 3)]
    meta, _ = load(a)
    json.dump({'pid': meta['pid'], 'mode': mode, 'hits': res}, open(out, 'w'))
    print(f"{len(res)} {'changed' if mode=='churn' else 'increased'}  ({a} -> {b})  -> {out}")
    return 0


def solve(rose_paths, churn_paths):
    sets = [json.load(open(p)) for p in rose_paths]
    keep = set(sets[0]['hits'])
    for s in sets[1:]:
        keep &= set(s['hits'])
    print(f"rose in all {len(sets)} heals: {len(keep)}")
    for p in churn_paths:
        c = set(json.load(open(p))['hits'])
        before = len(keep)
        keep -= c
        print(f"  minus churn {os.path.basename(p)} ({len(c)}): {before} -> {len(keep)}")
    rows = sorted(int(a) for a in keep)
    print(f"\n=== {len(rows)} survivors ===")
    for addr in rows[:60]:
        k = sets[0]['hits'][str(addr)]
        vals = '   '.join(
            (f"{s['hits'][str(addr)][1]}->{s['hits'][str(addr)][2]}") for s in sets)
        print(f"  0x{addr:08X}  {k[0]:<5}  {vals}")
    if len(rows) > 60:
        print(f"  ... and {len(rows)-60} more")
    print("\n=== clusters within 0x200 (a face array) ===")
    i, shown = 0, 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1] - rows[i] <= 0x200:
            j += 1
        if j - i + 1 >= 2:
            g = rows[i:j + 1]
            gaps = [g[k + 1] - g[k] for k in range(len(g) - 1)]
            print(f"  0x{g[0]:08X}  n={len(g)}  gaps {[hex(x) for x in gaps][:8]}")
            shown += 1
        i = j + 1
    if not shown:
        print("  none")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    c = sys.argv[1]
    if c == 'rose':
        return collect(sys.argv[2], sys.argv[3], sys.argv[4], 'rose')
    if c == 'churn':
        return collect(sys.argv[2], sys.argv[3], sys.argv[4], 'churn')
    if c == 'solve':
        args = sys.argv[2:]
        i = args.index('--minus') if '--minus' in args else len(args)
        return solve(args[:i], args[i + 1:])
    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main())
