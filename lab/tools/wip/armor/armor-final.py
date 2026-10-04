"""
armor-final.py - the four-point test for live armor.

Three snapshots plus a churn set, and armor must satisfy every condition simultaneously:

    full   -> drove   :  EXACTLY UNCHANGED   (not in the churn set - kills terrain, position,
                                              velocity, particles, animation: 1.19M addresses)
    full   -> hurt    :  drops to EXACTLY 0  (the reported state was all armor black)
    hurt   -> fixed   :  rises again
    fixed  vs full    :  EXACTLY EQUAL       (a repaired car is back at the same maximum)

The last condition is the one that does the heavy lifting and was missing from earlier passes.
Terrain repopulated after a respawn does not land on byte-identical values; a free-running
counter does not return to precisely where it started; and neither of those holds perfectly
still while you drive.
"""
import json, os, struct, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')


def load(n):
    m = json.load(open(os.path.join(D, n + '.json')))
    return m, open(os.path.join(D, n + '.bin'), 'rb')


def main():
    ma, fa = load('full')
    mh, fh = load('hurt')
    mx, fx = load('fixed')
    pids = {ma['pid'], mh['pid'], mx['pid']}
    if len(pids) > 1:
        print(f"pid mismatch {pids} - snapshots span a restart"); return 1

    churn = set()
    cp = os.path.join(D, 'churn.json')
    if os.path.exists(cp):
        churn = set(json.load(open(cp))['hits'])
    print(f"churn exclusion: {len(churn)}")

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
            if H[o:o + 4] != b'\x00\x00\x00\x00':      # must have zeroed
                continue
            if X[o:o + 4] != wa:                        # must return to EXACTLY the full value
                continue
            addr = base + o
            if str(addr) in churn:                      # must not move while merely driving
                continue
            i = struct.unpack('<I', wa)[0]
            f = struct.unpack('<f', wa)[0]
            hits.append((addr, i, f))

    print(f"\n=== survivors of all four conditions: {len(hits)} ===\n")
    hits.sort()
    for addr, i, f in hits[:80]:
        fs = f"{f:.3f}" if f == f and 1e-6 < abs(f) < 1e9 else ''
        print(f"  0x{addr:08X}   int={i:<12} float={fs}")
    if len(hits) > 80:
        print(f"  ... and {len(hits)-80} more")

    print("\n=== clusters within 0x200 (the face array) ===")
    addrs = [h[0] for h in hits]
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
