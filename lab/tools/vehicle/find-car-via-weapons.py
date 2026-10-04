"""
find-car-via-weapons.py - locate the car object through its WEAPONS, across a respawn.

James's idea, and it beats every address-based approach so far: the regen heals by RESPAWNING
the car, which reallocates the vehicle object. So nothing can be tracked by address across a
heal. But the weapons are known and identifiable - 50cal MG, 25mm Cannon, Gas Launcher,
Landmines - and the live ammo array is STATIC:

    0x005AAB0C, stride 0x4C, ammo at +0x1C, slot pointer at +0x00
    [[slot+0x00]+0x00] is the GDF asset name  (gmmedium, gcmedium, gfmedium, glandmin)

Static means it survives the respawn. So resolve the weapons in EACH snapshot, see which
objects moved, and use them as an anchor to find the car - the armor should live near whatever
the vehicle's weapon set hangs off.

Also reports the vehicle pointer chain per snapshot so a reallocation is visible.
"""
import json, os, struct, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')
AMMO_BASE, AMMO_STRIDE, AMMO_OFF, NSLOT = 0x005AAB0C, 0x4C, 0x1C, 16
WORLD_ROOT, ENT_OFF, LOGIC_OFF = 0x54A264, 0x70, 0x108


class Snap:
    def __init__(self, name):
        self.name = name
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

    def cstr(self, a, n=24):
        b = self.read(a, n)
        if not b:
            return ''
        out = []
        for c in b:
            if c == 0:
                break
            if c < 32 or c > 126:
                return ''
            out.append(chr(c))
        return ''.join(out)

    def vehicle(self):
        root = self.u32(WORLD_ROOT)
        s = self.u32(root)
        ent = self.u32(s + ENT_OFF) if s else 0
        return ent, (self.u32(ent + LOGIC_OFF) if ent else 0)

    def slots(self):
        out = []
        for i in range(NSLOT):
            rec = AMMO_BASE + i * AMMO_STRIDE
            p0 = self.u32(rec)
            ammo = self.u32(rec + AMMO_OFF)
            nm = self.cstr(p0) if 0x400000 < p0 < 0x40000000 else ''
            out.append((i, p0, ammo, nm))
        return out


def main():
    names = sys.argv[1:] or ['full', 'hurt', 'fixed']
    snaps = [Snap(n) for n in names]

    print(f"{'snapshot':<8} {'entity':>12} {'logic':>12}")
    for s in snaps:
        e, l = s.vehicle()
        print(f"{s.name:<8} 0x{e:010X} 0x{l:010X}")

    print("\n=== static ammo array per snapshot ===")
    for s in snaps:
        print(f"\n-- {s.name} --")
        print(f"  {'slot':>4} {'ptr':>12} {'ammo':>10}  gdf")
        for i, p0, ammo, nm in s.slots():
            if p0 == 0 and ammo == 0:
                continue
            shown = 'unlimited' if ammo == 0x0FFFFFFF else str(ammo)
            print(f"  {i:>4} 0x{p0:010X} {shown:>10}  {nm}")

    # which weapon objects moved across the respawn?
    print("\n=== weapon object pointers across snapshots ===")
    tab = {s.name: {i: p for i, p, _a, _n in s.slots()} for s in snaps}
    names_by_slot = {}
    for s in snaps:
        for i, p, a, nm in s.slots():
            if nm:
                names_by_slot.setdefault(i, nm)
    print(f"  {'slot':>4} {'gdf':<12} " + '  '.join(f"{n:>12}" for n in names))
    for i in range(NSLOT):
        row = [tab[n].get(i, 0) for n in names]
        if not any(row):
            continue
        moved = '   <-- MOVED' if len(set(row)) > 1 else ''
        print(f"  {i:>4} {names_by_slot.get(i,''):<12} " +
              '  '.join(f"0x{v:010X}" for v in row) + moved)
    return 0


if __name__ == '__main__':
    sys.exit(main())
