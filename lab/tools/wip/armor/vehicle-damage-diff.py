"""
vehicle-damage-diff.py - what changed in the vehicle when it took damage.

The cleanest comparison available: between the 'full' and 'hurt' snapshots the vehicle object
did NOT move (logic 0x4D3AA0C in both) - only the heal reallocated it. So full vs hurt is a
same-address, same-object diff with a known cause: damage.

Reported state at 'hurt': all four armor faces black/zero, front and rear chassis damaged,
left and right chassis untouched, weapons/equipment/wheels lightly damaged.

So look for a run of values that DECREASED, four of them hard.

Prints every decrease in the object, and separately any group of >= 3 decreases close together,
which is what a face array looks like.
"""
import json, os, struct, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')
WORLD_ROOT, ENT_OFF, LOGIC_OFF = 0x54A264, 0x70, 0x108


class Snap:
    def __init__(self, name):
        self.meta = json.load(open(os.path.join(D, name + '.json')))
        self.f = open(os.path.join(D, name + '.bin'), 'rb')

    def read(self, addr, n):
        for base, ln, off in self.meta['index']:
            if base <= addr < base + ln:
                s = addr - base
                self.f.seek(off + s)
                return self.f.read(min(n, ln - s))
        return None

    def u32(self, a):
        b = self.read(a, 4)
        return struct.unpack('<I', b)[0] if b and len(b) == 4 else 0

    def vehicle(self):
        root = self.u32(WORLD_ROOT)
        s = self.u32(root)
        ent = self.u32(s + ENT_OFF) if s else 0
        return ent, (self.u32(ent + LOGIC_OFF) if ent else 0)


def main():
    a_name = sys.argv[1] if len(sys.argv) > 1 else 'full'
    b_name = sys.argv[2] if len(sys.argv) > 2 else 'hurt'
    span = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x20000
    target = 'entity' if '--entity' in sys.argv else 'logic'

    A, B = Snap(a_name), Snap(b_name)
    ea, la = A.vehicle()
    eb, lb = B.vehicle()
    print(f"{a_name}: entity 0x{ea:X} logic 0x{la:X}")
    print(f"{b_name}: entity 0x{eb:X} logic 0x{lb:X}")
    base_a = la if target == 'logic' else ea
    base_b = lb if target == 'logic' else eb
    if base_a != base_b:
        print(f"\nWARNING: the {target} object moved between these two snapshots; "
              f"offsets are still comparable but a reallocation may reshuffle contents")
    da = A.read(base_a, span)
    db = B.read(base_b, span)
    if da is None or db is None:
        print("object not covered"); return 1
    n = min(len(da), len(db))
    print(f"\n{target} object, 0x{n:X} bytes, showing DECREASES ({a_name} -> {b_name})\n")

    drops = []
    for o in range(0, n - 4, 4):
        wa, wb = da[o:o + 4], db[o:o + 4]
        if wa == wb:
            continue
        ia, ib = struct.unpack('<I', wa)[0], struct.unpack('<I', wb)[0]
        fa_, fb_ = struct.unpack('<f', wa)[0], struct.unpack('<f', wb)[0]
        is_f = (fa_ == fa_ and fb_ == fb_ and 1e-3 < abs(fa_) < 1e6)
        if is_f and fb_ < fa_:
            drops.append((o, fa_, fb_, 'f'))
        elif (not is_f) and 0 < ib < ia <= 200000:
            drops.append((o, ia, ib, 'i'))

    print(f"{len(drops)} values decreased\n")
    for o, a, b, k in drops[:80]:
        av = f"{a:.3f}" if k == 'f' else str(a)
        bv = f"{b:.3f}" if k == 'f' else str(b)
        pct = (1 - (b / a)) * 100 if a else 0
        print(f"  +0x{o:05X}  {av:>12} -> {bv:>12}   -{pct:5.1f}%")
    if len(drops) > 80:
        print(f"  ... and {len(drops)-80} more")

    print("\n=== groups of >=3 decreases within 0x80 (a face array) ===")
    offs = [d[0] for d in drops]
    i, shown = 0, 0
    while i < len(offs):
        j = i
        while j + 1 < len(offs) and offs[j + 1] - offs[i] <= 0x80:
            j += 1
        if j - i + 1 >= 3:
            g = drops[i:j + 1]
            gaps = [g[k + 1][0] - g[k][0] for k in range(len(g) - 1)]
            print(f"\n  +0x{g[0][0]:05X}  n={len(g)}  gaps {[hex(x) for x in gaps][:8]}")
            for o, a, b, k in g[:10]:
                av = f"{a:.3f}" if k == 'f' else str(a)
                bv = f"{b:.3f}" if k == 'f' else str(b)
                print(f"      +0x{o:05X}  {av:>12} -> {bv:>12}")
            shown += 1
        i = j + 1
    if not shown:
        print("  none")
    return 0


if __name__ == '__main__':
    sys.exit(main())
