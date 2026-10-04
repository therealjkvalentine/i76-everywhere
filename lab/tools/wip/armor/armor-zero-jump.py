"""
armor-zero-jump.py - find armor by the ZERO -> FULL jump across a repair.

A plain "went up" diff across a regen is useless: the repair spot RESPAWNS the car elsewhere, so
every position, velocity and orientation value moves too (21,981 candidates in the live run).

The reported state before healing was: front destroyed, rear destroyed, sides lightly damaged.
That is a much stronger fingerprint than "increased":

    two faces  ~0  ->  large      (front, rear)
    two faces  mid ->  same large (sides, small rise)

Very little else in memory goes from exactly zero to a large value on cue, and the two-tier
shape (two big jumps + two small, all landing on the SAME full value) is close to unforgeable.

Reads the snapshots taken by armor-watch.py.
"""
import struct, json, os, sys, collections

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')


def load(name):
    meta = json.load(open(os.path.join(DIR, name + '.json')))
    f = open(os.path.join(DIR, name + '.bin'), 'rb')
    return meta, f


def main():
    a = sys.argv[1] if len(sys.argv) > 1 else 'base'
    b = sys.argv[2] if len(sys.argv) > 2 else 'healed'
    ma, fa = load(a)
    mb, fb = load(b)
    if ma['pid'] != mb['pid']:
        print(f"pid mismatch {ma['pid']} vs {mb['pid']}"); return 1
    bmap = {base: (off, ln) for base, ln, off in mb['index']}

    ints, floats = [], []
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
            # int: 0 (or all but dead) -> a real value
            if ia <= 3 and 20 <= ib <= 100000:
                ints.append((base + o, ia, ib))
            else:
                x = struct.unpack_from('<f', wa)[0]
                y = struct.unpack_from('<f', wb)[0]
                if x == x and y == y and 0 <= x < 0.05 and 1.0 < y < 100000.0:
                    floats.append((base + o, x, y))

    print(f"int   0->large : {len(ints)}")
    print(f"float 0->large : {len(floats)}\n")

    # armor faces sit together; a lone jump is noise, a cluster of 2-4 is a face array
    for label, rows, fmt in (('INT', ints, '{:d}'), ('FLOAT', floats, '{:.3f}')):
        if not rows:
            continue
        rows.sort()
        print(f"=== {label}: clusters within 0x200 ===")
        i, shown = 0, 0
        while i < len(rows):
            j = i
            while j + 1 < len(rows) and rows[j + 1][0] - rows[i][0] <= 0x200:
                j += 1
            grp = rows[i:j + 1]
            if len(grp) >= 2:
                span = grp[-1][0] - grp[0][0]
                gaps = [grp[k + 1][0] - grp[k][0] for k in range(len(grp) - 1)]
                vals = ', '.join(fmt.format(v[2]) for v in grp[:8])
                print(f"  0x{grp[0][0]:08X}  n={len(grp)}  span 0x{span:X}  "
                      f"gaps {[hex(g) for g in gaps][:6]}  now: {vals}")
                shown += 1
                if shown > 25:
                    print("  ... truncated"); break
            i = j + 1
        if shown == 0:
            print("  no clusters; singletons:")
            for addr, x, y in rows[:15]:
                print(f"  0x{addr:08X}  {x} -> {fmt.format(y)}")
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
