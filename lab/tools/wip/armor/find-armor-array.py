"""
find-armor-array.py - locate a vehicle's armor/chassis array by its SHAPE.

Established from the guided session: armor lives in a run of 20 int32 records, stride 0x34,
stored as integer TENTHS (400 = 40.0, the same encoding as the .vcf). On a fresh car every entry
reads the same value; damage drops individual entries.

Two things that are NOT true, both tested and discarded:
  * it is not at entity - 0x410. That held for one car and is coincidence; dumping there for a
    later car gives pointer garbage.
  * it is not inside the vehicle-logic object (only 11 values moved across its whole 0x20000).

It is a separate allocation, and the car is reallocated on every regen respawn, so it must be
found rather than remembered. The signature is unmistakable: 20 slots at 0x34 spacing, all
plausible tenths, the large majority identical.

  find-armor-array.py <snapshot> [more snapshots...]
"""
import json, os, struct, sys, collections

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures', 'armorwatch')
STRIDE, COUNT = 0x34, 20


def load(n):
    m = json.load(open(os.path.join(D, n + '.json')))
    return m, open(os.path.join(D, n + '.bin'), 'rb')


def scan(name):
    meta, fh = load(name)
    hits = []
    for base, ln, off in meta['index']:
        fh.seek(off)
        data = fh.read(ln)
        span = STRIDE * (COUNT - 1) + 4
        for o in range(0, len(data) - span, 4):
            vals = [struct.unpack_from('<I', data, o + k * STRIDE)[0] for k in range(COUNT)]
            if not all(1 <= v <= 2000 for v in vals):
                continue
            c = collections.Counter(vals)
            top, n = c.most_common(1)[0]
            if n < COUNT - 8:          # allow up to 8 damaged faces
                continue
            if top < 50:               # a full face is a real number, not 1 or 2
                continue
            hits.append((base + o, top, n, vals))
    return hits


def main():
    for name in (sys.argv[1:] or ['full']):
        print(f"=== {name} ===")
        hits = scan(name)
        if not hits:
            print("  no array found\n")
            continue
        for addr, top, n, vals in hits[:6]:
            print(f"  0x{addr:08X}   max={top} ({top/10:.1f})  {n}/{COUNT} at max")
            for i in range(COUNT):
                mark = '' if vals[i] == top else f"   <-- damaged, -{(1-vals[i]/top)*100:.0f}%"
                print(f"      {i:>2} 0x{addr + i*STRIDE:08X}  {vals[i]:>6}  ({vals[i]/10:.1f}){mark}")
            print()
        if len(hits) > 6:
            print(f"  ... and {len(hits)-6} more candidate arrays\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
