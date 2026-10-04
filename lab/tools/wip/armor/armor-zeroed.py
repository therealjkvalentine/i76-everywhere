"""
armor-zeroed.py - find the armor array using an ALL-ARMOR-GONE damage state.

The reported state: every armor face black/zero, front and rear chassis damaged, left and right
chassis UNTOUCHED, weapons/wheels lightly damaged.

That is an unusually strong signature, because it contains its own control:

    4 values  ->  EXACTLY 0        (the armor faces)
    2 values  ->  reduced          (front, rear chassis)
    2 values  ->  perfectly still  (left, right chassis)   <- the control

A coincidental cluster is very unlikely to have two members holding perfectly still while four
of its neighbours zero out.

Combined with the churn set (everything that moved while merely driving - 1.19M addresses),
which armor cannot be in, since armor does not move when nothing is hitting you.
"""
import json, os, struct, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')


def load(n):
    m = json.load(open(os.path.join(D, n + '.json')))
    return m, open(os.path.join(D, n + '.bin'), 'rb')


def main():
    a_name = sys.argv[1] if len(sys.argv) > 1 else 'full'
    b_name = sys.argv[2] if len(sys.argv) > 2 else 'hurt'
    use_churn = '--no-churn' not in sys.argv

    ma, fa = load(a_name)
    mb, fb = load(b_name)
    if ma['pid'] != mb['pid']:
        print(f"pid mismatch {ma['pid']} vs {mb['pid']}"); return 1

    churn = set()
    cp = os.path.join(D, 'churn.json')
    if use_churn and os.path.exists(cp):
        churn = set(json.load(open(cp))['hits'])
        print(f"churn exclusion set: {len(churn)}")

    bmap = {b: (o, l) for b, l, o in mb['index']}
    zeroed = []
    for base, ln, off in ma['index']:
        if base not in bmap:
            continue
        ob, lb = bmap[base]
        n = min(ln, lb)
        fa.seek(off); da = fa.read(n)
        fb.seek(ob);  db = fb.read(n)
        for o in range(0, n - 4, 4):
            wa = da[o:o + 4]
            if db[o:o + 4] != b'\x00\x00\x00\x00' or wa == b'\x00\x00\x00\x00':
                continue
            addr = base + o
            if str(addr) in churn:
                continue
            i = struct.unpack('<I', wa)[0]
            f = struct.unpack('<f', wa)[0]
            if (1 <= i <= 100000) or (f == f and 0.5 < f < 100000.0):
                zeroed.append((addr, i, f))

    print(f"\nwent to EXACTLY 0, and did NOT move while driving: {len(zeroed)}\n")
    zeroed.sort()
    if not zeroed:
        return 0

    # cluster: the armor faces live together
    runs, cur = [], [zeroed[0]]
    for r in zeroed[1:]:
        if r[0] - cur[-1][0] <= 0x200:
            cur.append(r)
        else:
            if len(cur) >= 3:
                runs.append(cur)
            cur = [r]
    if len(cur) >= 3:
        runs.append(cur)

    print(f"clusters of >=3 within 0x200: {len(runs)}")
    for c in runs[:25]:
        gaps = [c[k + 1][0] - c[k][0] for k in range(len(c) - 1)]
        print(f"\n  0x{c[0][0]:08X}  n={len(c)}  gaps {[hex(g) for g in gaps][:10]}")
        for addr, i, f in c[:10]:
            print(f"      0x{addr:08X}  was int={i:<8} float={f:.3f}")
    if not runs:
        print("no clusters; singletons:")
        for addr, i, f in zeroed[:40]:
            print(f"  0x{addr:08X}  was int={i:<8} float={f:.3f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
