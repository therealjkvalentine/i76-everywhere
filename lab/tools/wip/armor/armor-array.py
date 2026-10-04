"""
armor-array.py - dump the vehicle armor/chassis array side by side across snapshots.

FOUND: near the player entity, a run of values of 400 - i.e. 40.0 in the integer TENTHS the
.vcf uses for armor - that drop by varying amounts when the car is damaged, at a stride of 0x34.

The gaps are the proof. Diffing full vs partially-damaged showed decreases spaced 0x34 apart
with occasional jumps of 0x9C (= 3 x 0x34): exactly where a face was reported UNDAMAGED and so
never appeared in a decreases-only list. James's report for that snapshot was "all armor and
front/right chassis damaged; left and rear chassis untouched".

This prints EVERY entry, changed or not, so the undamaged controls are visible too.
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
    names = sys.argv[1].split(',') if len(sys.argv) > 1 else ['fixed', 'part']
    start = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x0D740070
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    stride = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x34

    snaps = [(n,) + load(n) for n in names]
    print(f"armor/chassis array @0x{start:X}  stride 0x{stride:X}  x{count}\n")
    print(f"{'#':>3} {'addr':>12}  " + '  '.join(f"{n:>10}" for n in names) + "   note")
    for i in range(count):
        a = start + i * stride
        vals = []
        for _n, meta, fh in snaps:
            b = read(meta, fh, a, 4)
            vals.append(struct.unpack('<I', b)[0] if b and len(b) == 4 else None)
        if all(v is None for v in vals):
            continue
        note = ''
        if len(vals) >= 2 and vals[0] and vals[1] is not None:
            if vals[1] < vals[0]:
                note = f"-{(1-vals[1]/vals[0])*100:.0f}%"
            elif vals[1] == vals[0]:
                note = 'unchanged'
        shown = '  '.join(('----' if v is None else f"{v:>10}") for v in vals)
        tenths = f"   ({vals[0]/10:.1f})" if vals[0] and vals[0] < 20000 else ''
        print(f"{i:>3} 0x{a:08X}  {shown}   {note}{tenths}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
