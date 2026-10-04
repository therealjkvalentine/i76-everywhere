"""
vehicle-diff.py - dump what changed INSIDE the player's vehicle across full/hurt/fixed.

The filtered searches all failed at the last step: nothing that satisfied
"zeroed, returned to exactly full, never churned" lay anywhere near the vehicle
(entity 0xD742CD0, logic 0x937BAC0 - survivors were all at 0x0019xxxx).

So stop assuming. We know exactly where the vehicle lives; just print every word in it that
moved, with all three values side by side, and let the reported damage state pick the fields:

    all four armor faces black/zero
    front and rear chassis damaged
    left and right chassis UNTOUCHED
    weapons, equipment and wheels lightly damaged

The armor block should show up as four values that drop hard and recover, sitting near two that
drop a little and two that do not move at all.

Assumption being tested and possibly wrong: that armor reaches EXACTLY 0 when the panel goes
black. It may bottom out at a small non-zero, or the panel may black out below a threshold.
"""
import json, os, struct, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')


def load(n):
    m = json.load(open(os.path.join(D, n + '.json')))
    return m, open(os.path.join(D, n + '.bin'), 'rb')


def region_for(meta, addr):
    for base, ln, off in meta['index']:
        if base <= addr < base + ln:
            return base, ln, off
    return None


def read_span(meta, fh, addr, length):
    r = region_for(meta, addr)
    if not r:
        return None
    base, ln, off = r
    start = addr - base
    n = min(length, ln - start)
    fh.seek(off + start)
    return fh.read(n)


def main():
    if len(sys.argv) < 3:
        print("usage: vehicle-diff.py <hex addr> <length hex> [--all]")
        return 1
    addr = int(sys.argv[1], 16)
    length = int(sys.argv[2], 16)
    show_all = '--all' in sys.argv

    ma, fa = load('full')
    mh, fh = load('hurt')
    mx, fx = load('fixed')

    A = read_span(ma, fa, addr, length)
    H = read_span(mh, fh, addr, length)
    X = read_span(mx, fx, addr, length)
    if A is None or H is None or X is None:
        print("address not covered by one of the snapshots")
        return 1
    n = min(len(A), len(H), len(X))
    print(f"0x{addr:X} .. +0x{n:X}   full | hurt | fixed\n")
    print(f"{'off':>6}  {'full':>14} {'hurt':>14} {'fixed':>14}   note")

    shown = 0
    for o in range(0, n - 4, 4):
        wa, wh, wx = A[o:o+4], H[o:o+4], X[o:o+4]
        if not show_all and wa == wh == wx:
            continue
        ia, ih, ix = (struct.unpack('<I', w)[0] for w in (wa, wh, wx))
        fa_, fh_, fx_ = (struct.unpack('<f', w)[0] for w in (wa, wh, wx))

        def fmt(i, f):
            if f == f and 1e-4 < abs(f) < 1e6:
                return f"{f:.3f}"
            return str(i)
        note = ''
        if wa != wh and wh != wx:
            dropped = (ih < ia) or (fh_ < fa_ and fa_ == fa_)
            rose = (ix > ih) or (fx_ > fh_ and fx_ == fx_)
            if dropped and rose:
                note = '<< DOWN then UP'
                if wx == wa:
                    note += ', back to full'
        elif wa == wx and wa != wh:
            note = '<< changed then restored'
        print(f"+0x{o:04X}  {fmt(ia,fa_):>14} {fmt(ih,fh_):>14} {fmt(ix,fx_):>14}   {note}")
        shown += 1
        if shown > 400:
            print("  ... truncated")
            break
    if shown == 0:
        print("  (nothing changed in this span)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
