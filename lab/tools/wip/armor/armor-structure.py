"""armor-structure.py - map the entity armor block precisely from the snapshots.

Three questions, answered purely offline from the damage-state snapshots:
  1. which offsets are VARIABLE (change with damage) vs CONSTANT (max/config)?
  2. which offsets are byte-identical in every state (the lockstep copies)?
  3. which face is which, assigned from the labelled states (frontonly / frontgone)?
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from snaplib import Snap

ORDER = ['full', 'part', 'frontonly', 'prefront', 'frontgone', 'hurt', 'fixed', 'fixed2']
LO, HI = 0x130, 0x200


def col(snaps, off):
    return [s.i32(s._ent + off) for s in snaps]


def main():
    snaps = []
    for nm in ORDER:
        s = Snap(nm)
        s._ent = s.player_entity()
        snaps.append(s)
    by = {s.name: s for s in snaps}

    # 1. variable vs constant, over the whole block
    offs = list(range(LO, HI, 4))
    variable = []
    for off in offs:
        vs = [c for c in col(snaps, off) if c is not None]
        if len(set(vs)) > 1:
            variable.append(off)

    # 2. group offsets whose full column-vector is identical (lockstep copies)
    sig = {}
    for off in offs:
        key = tuple(col(snaps, off))
        sig.setdefault(key, []).append(off)
    copies = [v for v in sig.values() if len(v) > 1 and any(o in variable for o in v)]

    # 3. face assignment: full vs frontonly isolates the FRONT face
    full, fonly, fgone = by['full'], by['frontonly'], by['frontgone']
    front_off = []
    for off in variable:
        a = full.i32(full._ent + off)
        b = fonly.i32(fonly._ent + off)
        g = fgone.i32(fgone._ent + off)
        if a is not None and b is not None and b < a and g == 0:
            front_off.append(off)

    print("VARIABLE offsets (change with damage):")
    print("  " + " ".join(f"+0x{o:03X}" for o in variable))
    print(f"\nLOCKSTEP COPIES (byte-identical in all {len(snaps)} states):")
    for grp in sorted(copies):
        print("  " + " <-> ".join(f"+0x{o:03X}" for o in grp))
    print("\nFRONT face (dropped in 'frontonly', zero in 'frontgone'):")
    for o in front_off:
        print(f"  +0x{o:03X}")

    # the 4-wide current array starting at the first front offset, with maxima guess
    if front_off:
        base = min(front_off)
        print(f"\nARMOR FACE ARRAY (assuming FRONT,LEFT,RIGHT,REAR from base +0x{base:03X}):")
        names = ['FRONT', 'LEFT', 'RIGHT', 'REAR']
        hdr = "face    off     " + "".join(f"{s.name:>10}" for s in snaps)
        print(hdr)
        for i, nm in enumerate(names):
            off = base + i * 4
            cells = "".join((f"{v:>10}" if v is not None else "       ---")
                            for v in col(snaps, off))
            print(f"{nm:<7} +0x{off:03X}  {cells}")


if __name__ == '__main__':
    main()
