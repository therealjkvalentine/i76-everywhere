"""
armor-bigdrop.py - global search for a cluster of values that CRASHED when the car was wrecked.

Established so far:
  * between 'full' and 'hurt' the vehicle object did NOT move (logic 0x4D3AA0C in both), so
    armor is at the same address in both snapshots - a plain diff is valid.
  * armor is NOT inside the logic object: only 11 values decreased in its whole 0x20000 span.
    So it lives in a separate allocation, presumably reached by a pointer.

Dropping two assumptions that may have been wrong:
  * that armor lands on EXACTLY zero when the panel reads black (it may bottom out low, or the
    panel may black out below a threshold)
  * that armor never changes while driving (the churn set may be over-broad; it was collected
    over a long drive and holds 1.19M addresses)

So: find every value that fell by a large fraction, then keep only tight clusters - four faces
crashing together is the shape, a lone value is noise.
"""
import json, os, struct, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')


def load(n):
    m = json.load(open(os.path.join(D, n + '.json')))
    return m, open(os.path.join(D, n + '.bin'), 'rb')


def main():
    a_name = sys.argv[1] if len(sys.argv) > 1 else 'full'
    b_name = sys.argv[2] if len(sys.argv) > 2 else 'hurt'
    min_drop = float(sys.argv[3]) if len(sys.argv) > 3 else 0.80
    use_churn = '--churn' in sys.argv
    need = 4

    ma, fa = load(a_name)
    mb, fb = load(b_name)
    churn = set()
    if use_churn:
        cp = os.path.join(D, 'churn.json')
        if os.path.exists(cp):
            churn = set(json.load(open(cp))['hits'])
            print(f"churn exclusion: {len(churn)}")

    bmap = {b: (o, l) for b, l, o in mb['index']}
    drops = []
    for base, ln, off in ma['index']:
        if base not in bmap:
            continue
        ob, lb = bmap[base]
        n = min(ln, lb)
        fa.seek(off); A = fa.read(n)
        fb.seek(ob);  B = fb.read(n)
        for o in range(0, n - 4, 4):
            wa, wb = A[o:o + 4], B[o:o + 4]
            if wa == wb:
                continue
            addr = base + o
            if churn and str(addr) in churn:
                continue
            ia, ib = struct.unpack('<I', wa)[0], struct.unpack('<I', wb)[0]
            fa_, fb_ = struct.unpack('<f', wa)[0], struct.unpack('<f', wb)[0]
            if fa_ == fa_ and fb_ == fb_ and 0.5 < fa_ < 1e5 and 0 <= fb_ < fa_:
                if (1 - fb_ / fa_) >= min_drop:
                    drops.append((addr, fa_, fb_, 'f'))
            elif 2 <= ia <= 200000 and 0 <= ib < ia:
                if (1 - ib / ia) >= min_drop:
                    drops.append((addr, ia, ib, 'i'))

    print(f"{len(drops)} values fell by >= {min_drop*100:.0f}%\n")
    drops.sort()
    print(f"=== clusters of >= {need} within 0x100 ===")
    offs = [d[0] for d in drops]
    i, shown = 0, 0
    while i < len(offs):
        j = i
        while j + 1 < len(offs) and offs[j + 1] - offs[i] <= 0x100:
            j += 1
        if j - i + 1 >= need:
            g = drops[i:j + 1]
            gaps = [g[k + 1][0] - g[k][0] for k in range(len(g) - 1)]
            print(f"\n  0x{g[0][0]:08X}  n={len(g)}  gaps {[hex(x) for x in gaps][:10]}")
            for addr, a, b, k in g[:12]:
                av = f"{a:.3f}" if k == 'f' else str(a)
                bv = f"{b:.3f}" if k == 'f' else str(b)
                print(f"      0x{addr:08X}  {av:>12} -> {bv:>12}")
            shown += 1
            if shown > 15:
                print("  ... truncated"); break
        i = j + 1
    if not shown:
        print("  none - try a lower threshold, e.g. 0.5")
    return 0


if __name__ == '__main__':
    sys.exit(main())
