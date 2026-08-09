"""
find-regen-maps.py - find community maps that contain a REGEN (repair) spot.

The Asset Bible documents `regen = Regen/Repair spot for damaged car` as a placeable vehicle-class
code. A map containing one gives a REPAIR EVENT ON DEMAND, which is the stimulus needed to locate
live armor in memory: damage has been unreliable in every form tried, and a repair is the only
thing that moves armor UPWARD on cue.

Scans the zips in place (no extraction) for the class code, plus `spawn` and `check1` as a sanity
check that the scanner is actually reading level data and not just failing to match anything.
"""
import zipfile, os, sys, re, collections

CODES = [b'regen', b'REGEN', b'Regen']
SANITY = [b'spawn', b'SPAWN', b'check1', b'CHECK1']


def scan_bytes(data):
    hits = collections.Counter()
    for c in CODES:
        n = data.count(c)
        if n:
            hits[c.decode()] += n
    return hits


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else 'refs/route380/maps'
    found = []
    sanity_total = collections.Counter()
    scanned = 0
    for fn in sorted(os.listdir(root)):
        if not fn.lower().endswith('.zip'):
            continue
        path = os.path.join(root, fn)
        try:
            z = zipfile.ZipFile(path)
        except Exception as e:
            print(f"  !! {fn}: {e}")
            continue
        per_map = collections.Counter()
        where = []
        for info in z.infolist():
            if info.is_dir() or info.file_size > 8 * 1024 * 1024:
                continue
            try:
                data = z.read(info)
            except Exception:
                continue
            scanned += 1
            h = scan_bytes(data)
            if h:
                per_map.update(h)
                where.append(info.filename)
            for s in SANITY:
                sanity_total[s.decode()] += data.count(s)
        if per_map:
            found.append((fn, sum(per_map.values()), where[:6]))
        z.close()

    print(f"scanned {scanned} files inside {len(os.listdir(root))} archives\n")
    print("=== maps containing a REGEN / repair spot ===")
    if not found:
        print("  none")
    for fn, n, where in sorted(found, key=lambda t: -t[1]):
        print(f"  {fn:<26} {n:3} hits   {', '.join(where)}")
    print("\nsanity (proves the scanner reads real level data):")
    for k, v in sanity_total.most_common():
        print(f"  {k:<8} {v}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
