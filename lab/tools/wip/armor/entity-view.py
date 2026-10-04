"""entity-view.py - print a range of the player-entity struct across every damage snapshot.

Anchored on each snapshot's OWN entity base ([[[0x54A264]]+0x70]), so the columns line up by
struct offset even though the car is a different heap allocation in the post-repair snapshots.
Shows integer-tenths interpretation (the mirror's encoding: 400 = 40.0 armor). Only rows whose
value looks armor-plausible in at least one column are printed, so the armor block stands out
from pointers and flags.

    python entity-view.py            # default window 0x140..0x520, int tenths
    python entity-view.py 0 0x600 f  # floats, full struct
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from snaplib import Snap

ORDER = ['full', 'part', 'frontonly', 'prefront', 'frontgone', 'hurt', 'fixed', 'fixed2']


def main():
    lo = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x140
    hi = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x520
    kind = sys.argv[3] if len(sys.argv) > 3 else 'i'

    snaps = []
    for nm in ORDER:
        try:
            s = Snap(nm)
            s._ent = s.player_entity()
            snaps.append(s)
        except FileNotFoundError:
            pass

    print("offset   " + "  ".join(f"{s.name:>10}" for s in snaps))
    for off in range(lo, hi, 4):
        vals = []
        show = False
        for s in snaps:
            if kind == 'f':
                v = s.f32(s._ent + off)
                vals.append(None if v is None else round(v, 2))
                if v is not None and 1.0 <= v <= 6000.0:
                    show = True
            else:
                v = s.i32(s._ent + off)
                vals.append(v)
                if v is not None and 20 <= v <= 60000:
                    show = True
        if show:
            cells = "  ".join(("       ---" if v is None else f"{v:>10}") for v in vals)
            print(f"+0x{off:04X}  {cells}")


if __name__ == '__main__':
    main()
