"""
vehicle-track.py - diff the player's vehicle across snapshots, FOLLOWING THE POINTER.

THE BUG THIS FIXES: the regen spot respawns the car, and a respawn REALLOCATES the vehicle
object. So the player entity and vehicle-logic addresses differ between snapshots. Every
address-based search was therefore doomed - armor cannot satisfy "same address went full -> 0 ->
full" when the whole object moved in between. That is why nothing near the vehicle survived any
filter, and why the only survivors were unrelated fixed buffers at 0x0019xxxx.

Fix: 0x54A264 is static, so resolve the chain separately INSIDE EACH SNAPSHOT

    entity = [[0x54A264] + 0x70]
    logic  = [entity + 0x108]

and compare the object by OFFSET, not by absolute address.

Expected shape from the reported damage state (all armor black, front+rear chassis damaged,
left+right chassis untouched): four values that crash and recover, next to two that dip and two
that never move.
"""
import json, os, struct, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')
WORLD_ROOT, ENT_OFF, LOGIC_OFF = 0x54A264, 0x70, 0x108


class Snap:
    def __init__(self, name):
        self.meta = json.load(open(os.path.join(D, name + '.json')))
        self.f = open(os.path.join(D, name + '.bin'), 'rb')
        self.name = name
        self.regions = [(b, l, o) for b, l, o in self.meta['index']]

    def read(self, addr, n):
        for base, ln, off in self.regions:
            if base <= addr < base + ln:
                start = addr - base
                self.f.seek(off + start)
                return self.f.read(min(n, ln - start))
        return None

    def u32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack('<I', b)[0] if b and len(b) == 4 else 0

    def vehicle(self):
        root = self.u32(WORLD_ROOT)
        s = self.u32(root)
        ent = self.u32(s + ENT_OFF) if s else 0
        logic = self.u32(ent + LOGIC_OFF) if ent else 0
        return ent, logic


def fmt(w):
    i = struct.unpack('<I', w)[0]
    f = struct.unpack('<f', w)[0]
    if f == f and 1e-4 < abs(f) < 1e6:
        return f"{f:.3f}"
    return str(i)


def main():
    names = sys.argv[1:4] if len(sys.argv) >= 4 else ['full', 'hurt', 'fixed']
    span = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x800
    which = 'logic'
    if '--entity' in sys.argv:
        which = 'entity'

    snaps = [Snap(n) for n in names]
    print(f"{'snapshot':<10} {'entity':>12} {'logic':>12}")
    objs = []
    for s in snaps:
        e, l = s.vehicle()
        print(f"{s.name:<10} 0x{e:010X} 0x{l:010X}")
        objs.append((e, l))
    if any(o[0] == 0 for o in objs):
        print("\ncould not resolve the chain in one of the snapshots")
        return 1
    moved = len({o[1] for o in objs}) > 1
    print(f"\nvehicle object {'MOVED between snapshots (respawn reallocated it)' if moved else 'stayed put'}")

    base_idx = 1 if which == 'logic' else 0
    print(f"\ncomparing the {which} object by OFFSET, 0x{span:X} bytes\n")
    print(f"{'off':>7}  " + '  '.join(f"{n:>14}" for n in names) + "   note")

    datas = []
    for s, o in zip(snaps, objs):
        datas.append(s.read(o[base_idx], span))
    if any(d is None for d in datas):
        print("object not covered by a snapshot")
        return 1
    n = min(len(d) for d in datas)

    for off in range(0, n - 4, 4):
        ws = [d[off:off + 4] for d in datas]
        if len(set(ws)) == 1:
            continue
        vals = [struct.unpack('<f', w)[0] for w in ws]
        ivals = [struct.unpack('<I', w)[0] for w in ws]
        note = ''
        # full -> hurt -> fixed : down then up
        def num(k):
            return vals[k] if (vals[k] == vals[k] and abs(vals[k]) < 1e6 and abs(vals[k]) > 1e-6) else ivals[k]
        try:
            a, b, c = num(0), num(1), num(2)
            if b < a and c > b:
                note = '<< DOWN then UP'
                if abs(c - a) < 1e-3:
                    note += ', back to full'
            elif a == c and b != a:
                note = '<< dipped and restored'
        except Exception:
            pass
        print(f"+0x{off:04X}  " + '  '.join(f"{fmt(w):>14}" for w in ws) + f"   {note}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
