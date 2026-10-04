"""armor-offset-diff.py - find the authoritative armor field by cross-instance offset intersection.

The prior hunt was stuck because armor is reallocated on repair, so absolute addresses never
survive a heal. This sidesteps that entirely using two SAME-ALLOCATION damage events:

    full      -> hurt        (entity 0xd740480, one instance)
    prefront  -> frontgone   (entity 0xd749a8c, a different instance)

In each pair the car did not respawn, so every address is comparable within the pair and the
player-entity pointer is stable. A value that dropped because of damage will appear in BOTH
diffs, but at DIFFERENT absolute addresses (different instance). What it shares across the two
instances is its OFFSET from a stable anchor - the entity base, the level-2 logic pointer, or
the damage mirror. Express every dropped address as an offset from each anchor, intersect the
two pairs, and the armor field survives while unrelated churn (at random relative positions)
cancels out.

Tests both int (tenths, like the mirror's 400=40.0) and float encodings, kept separate.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from snaplib import Snap

PAIRS = [('full', 'hurt'), ('prefront', 'frontgone')]


def dropped(a, b, kind):
    """addresses whose value fell from snapshot a to b, within an armor-plausible range.
    Returns {addr: (old, new)}. Walks only the regions common to both, dword-aligned."""
    amap = {base: (off, ln) for base, ln, off in a.index}
    out = {}
    for base, ln, off in b.index:
        if base not in amap:
            continue
        offa, lna = amap[base]
        n = min(ln, lna) & ~3
        da = a.blob[offa:offa + n]
        db = b.blob[off:off + n]
        if da == db:
            continue
        for o in range(0, n, 4):
            wa = da[o:o + 4]
            wb = db[o:o + 4]
            if wa == wb:
                continue
            if kind == 'int':
                va = struct.unpack('<i', wa)[0]
                vb = struct.unpack('<i', wb)[0]
                if 5 <= vb < va <= 60000 and (va - vb) >= 5:
                    out[base + o] = (va, vb)
            else:
                va = struct.unpack('<f', wa)[0]
                vb = struct.unpack('<f', wb)[0]
                if (va == va and vb == vb and 0.5 <= vb < va <= 6000.0
                        and (va - vb) >= 0.5):
                    out[base + o] = (va, vb)
    return out


def anchors(snap):
    """named stable reference points to measure offsets from."""
    ent = snap.player_entity()
    root = snap.u32(0x54A264)
    lvl2 = snap.u32(root) if root else None
    return {'entity': ent, 'logic': lvl2}


def main():
    kinds = ['int', 'float']
    for kind in kinds:
        print(f"\n================  {kind.upper()}  ================")
        drops = []
        ancs = []
        for a_name, b_name in PAIRS:
            a, b = Snap(a_name), Snap(b_name)
            d = dropped(a, b, kind)
            drops.append(d)
            ancs.append(anchors(a))
            print(f"{a_name}->{b_name}: {len(d)} dropped {kind} values "
                  f"(entity={hex(ancs[-1]['entity'])}, logic={hex(ancs[-1]['logic'])})")

        for anchor in ('entity', 'logic'):
            # offset from this anchor, in each pair, keeping the value pair for display
            def by_off(drop, anc):
                base = anc[anchor]
                m = {}
                for addr, (old, new) in drop.items():
                    off = addr - base
                    if -0x8000 <= off <= 0x400000:   # within a struct/arena, not wild
                        m.setdefault(off, []).append((addr, old, new))
                return m
            m0 = by_off(drops[0], ancs[0])
            m1 = by_off(drops[1], ancs[1])
            common = sorted(set(m0) & set(m1))
            print(f"\n  anchor={anchor}: {len(m0)} vs {len(m1)} offsets, {len(common)} shared")
            for off in common[:40]:
                s = 'x'.join(hex(x) for x in (off & 0xffffffff,))
                v0 = m0[off][0]
                v1 = m1[off][0]
                print(f"    +0x{off & 0xffffffff:06X}  pair1 {v0[1]}->{v0[2]} @{hex(v0[0])}   "
                      f"pair2 {v1[1]}->{v1[2]} @{hex(v1[0])}")


if __name__ == '__main__':
    main()
