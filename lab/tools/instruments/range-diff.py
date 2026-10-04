"""
range-diff.py - diff an address range between two snapshots.

Used to search the CAR'S NEIGHBOURHOOD. The static ammo array (0x005AAB0C) gives the player's
weapon-object pointers in every snapshot, which survives the respawn even though the vehicle
object does not. In 'full' and 'hurt' the player's weapons sit at 0xD64BC2C..0xD64CF28, so the
car's allocations cluster around there - and the armor should be in that cluster.

    range-diff.py <from> <to> <lo hex> <hi hex> [--drops]

--drops shows only values that decreased, which is the damage signature.
"""
import json, os, struct, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')


def load(n):
    m = json.load(open(os.path.join(D, n + '.json')))
    return m, open(os.path.join(D, n + '.bin'), 'rb')


def read(meta, fh, addr, n):
    for base, ln, off in meta['index']:
        if base <= addr < base + ln:
            s = addr - base
            fh.seek(off + s)
            return fh.read(min(n, ln - s))
    return None


def main():
    a, b = sys.argv[1], sys.argv[2]
    lo, hi = int(sys.argv[3], 16), int(sys.argv[4], 16)
    only_drops = '--drops' in sys.argv
    ma, fa = load(a)
    mb, fb = load(b)

    rows = []
    addr = lo
    while addr < hi:
        A = read(ma, fa, addr, 0x1000)
        B = read(mb, fb, addr, 0x1000)
        if A is None or B is None:
            addr += 0x1000
            continue
        n = min(len(A), len(B))
        for o in range(0, n - 4, 4):
            wa, wb = A[o:o + 4], B[o:o + 4]
            if wa == wb:
                continue
            ia, ib = struct.unpack('<I', wa)[0], struct.unpack('<I', wb)[0]
            fa_, fb_ = struct.unpack('<f', wa)[0], struct.unpack('<f', wb)[0]
            isf = fa_ == fa_ and fb_ == fb_ and 1e-3 < abs(fa_) < 1e6
            if only_drops:
                if isf and not (0 <= fb_ < fa_):
                    continue
                if (not isf) and not (0 <= ib < ia <= 200000):
                    continue
            rows.append((addr + o, ia, ib, fa_, fb_, isf))
        addr += n if n else 0x1000

    print(f"{len(rows)} {'decreases' if only_drops else 'changes'} in "
          f"0x{lo:X}..0x{hi:X}  ({a} -> {b})\n")
    print(f"{'addr':>12}  {'from':>14} {'to':>14}   drop")
    for ad, ia, ib, fa_, fb_, isf in rows[:120]:
        if isf:
            av, bv = f"{fa_:.3f}", f"{fb_:.3f}"
            pct = (1 - fb_ / fa_) * 100 if fa_ else 0
        else:
            av, bv = str(ia), str(ib)
            pct = (1 - ib / ia) * 100 if ia else 0
        print(f"  0x{ad:08X}  {av:>14} {bv:>14}   {pct:5.1f}%")
    if len(rows) > 120:
        print(f"  ... and {len(rows)-120} more")
    return 0


if __name__ == '__main__':
    sys.exit(main())
