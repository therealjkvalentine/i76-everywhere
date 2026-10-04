"""
armor-rounds.py - narrow live armor by INTERSECTING repair cycles.

One damage->heal cycle cannot isolate armor: the regen spot RESPAWNS the car, so every position,
velocity and orientation value moves too. The first live cycle gave 21,981 "went up" addresses,
and even filtering to "was ~0, now large" left ~3,900 ints and ~8,000 floats.

But the respawn lands you somewhere DIFFERENT each time, while armor makes the SAME jump every
time. So intersect across cycles:

    cycle 1:  damaged -> healed  =>  set A
    cycle 2:  damaged -> healed  =>  set B
    armor is in A ∩ B, and position noise is not.

Usage:
  armor-rounds.py collect <damaged_snap> <healed_snap> <out.json>
  armor-rounds.py intersect <a.json> <b.json> [c.json ...]
"""
import struct, json, os, sys

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')


def load(name):
    meta = json.load(open(os.path.join(DIR, name + '.json')))
    return meta, open(os.path.join(DIR, name + '.bin'), 'rb')


def collect(a, b, out):
    ma, fa = load(a)
    mb, fb = load(b)
    if ma['pid'] != mb['pid']:
        print(f"pid mismatch {ma['pid']} vs {mb['pid']} - snapshots are from different runs")
        return 1
    bmap = {base: (off, ln) for base, ln, off in mb['index']}
    res = {}
    for base, ln, off in ma['index']:
        if base not in bmap:
            continue
        ob, lb = bmap[base]
        n = min(ln, lb)
        fa.seek(off); da = fa.read(n)
        fb.seek(ob);  db = fb.read(n)
        for o in range(0, n - 4, 4):
            wa, wb = da[o:o + 4], db[o:o + 4]
            if wa == wb:
                continue
            ia = struct.unpack_from('<I', wa)[0]
            ib = struct.unpack_from('<I', wb)[0]
            if ia <= 3 and 20 <= ib <= 100000:
                res[str(base + o)] = ['int', ia, ib]
                continue
            x = struct.unpack_from('<f', wa)[0]
            y = struct.unpack_from('<f', wb)[0]
            if x == x and y == y and 0 <= x < 0.05 and 1.0 < y < 100000.0:
                res[str(base + o)] = ['float', x, y]
    json.dump({'pid': ma['pid'], 'from': a, 'to': b, 'hits': res}, open(out, 'w'))
    print(f"{len(res)} zero->large jumps  ({a} -> {b})  -> {out}")
    return 0


def intersect(paths):
    sets = [json.load(open(p)) for p in paths]
    pids = {s['pid'] for s in sets}
    if len(pids) > 1:
        print(f"WARNING: mixed pids {pids}; addresses are not comparable across game restarts")
    common = set(sets[0]['hits'])
    for s in sets[1:]:
        common &= set(s['hits'])
    print(f"{' ∩ '.join(os.path.basename(p) for p in paths)}  =  {len(common)} addresses\n")
    rows = []
    for a in common:
        kinds = [s['hits'][a] for s in sets]
        rows.append((int(a), kinds))
    rows.sort()
    for addr, kinds in rows[:60]:
        vals = '  '.join(
            (f"{k[1]}->{k[2]}" if k[0] == 'int' else f"{k[1]:.2f}->{k[2]:.2f}") for k in kinds)
        print(f"  0x{addr:08X}  {kinds[0][0]:<5}  {vals}")
    if len(rows) > 60:
        print(f"  ... and {len(rows)-60} more")
    # clusters are what matter: 2-4 faces sitting together
    print("\n=== clusters within 0x200 (a face array) ===")
    addrs = [r[0] for r in rows]
    i, shown = 0, 0
    while i < len(addrs):
        j = i
        while j + 1 < len(addrs) and addrs[j + 1] - addrs[i] <= 0x200:
            j += 1
        if j - i + 1 >= 2:
            g = addrs[i:j + 1]
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
    if sys.argv[1] == 'collect':
        return collect(sys.argv[2], sys.argv[3], sys.argv[4])
    if sys.argv[1] == 'intersect':
        return intersect(sys.argv[2:])
    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main())
