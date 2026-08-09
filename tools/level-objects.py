"""
level-objects.py - list every object in an I'76 level, with world coordinates.

Decoded from b01dojo.cbt. Levels are chunked exactly like .VCF (4-char tag + u32 size, size
INCLUDES the 8-byte header):

    BWD2  REV  WDEF(world)  TDEF(terrain)  RDEF(roads)  ODEF(objects)  LDEF  ADEF  EXIT

Inside ODEF, each object is an `OBJ` chunk of 0x6C bytes:

    +0x00  char[8]   class name          "REGEN", "AARAMP1", "BHBARN1" ...
    +0x08  float[9]  3x3 rotation matrix
    +0x2C  float     X  \
    +0x30  float     Y   >  world position (Y is height)
    +0x34  float     Z  /

Verified against the live game's coordinate scale: dojo's first REGEN sits at
(1782.5, 24.0, 50263.5) and in-mission player positions read ~ (4688, 120, 49082).

WHY THIS MATTERS: `regen` is the repair spot - the "healing building". 33 of the 40 mirrored
community maps contain one, and a repair is the only stimulus that raises armor ON DEMAND,
which is what the live-armor hunt needs. Knowing a map has one is useless without knowing where
it is; this prints the coordinates to drive to.

Usage:
  level-objects.py <level file>              list every object
  level-objects.py <level file> --only regen only matching class names
  level-objects.py <dir> --scan regen        scan a directory of levels
"""
import struct, sys, os, glob

OBJ_SIZE = 0x6C
NAME_LEN = 8
POS_OFF = 0x2C


def chunks(data, start=0, end=None):
    out, o = [], start
    end = len(data) if end is None else end
    while o + 8 <= end:
        tag = data[o:o + 4]
        if not all(c == 0 or 32 <= c < 127 for c in tag):
            break
        size = struct.unpack_from('<I', data, o + 4)[0]
        if size < 8 or o + size > end:
            break
        out.append((tag.decode('latin1').rstrip('\0'), o, size))
        o += size
    return out


def name_at(b, off):
    """Class name, 8 bytes.

    BIT 7 OF A NAME CHARACTER IS A FLAG, NOT PART OF THE NAME. Left raw you get phantom
    classes - 'BCSTRAK2' and 'BCSTRAK6' alongside 'BCSTRÃK6' (0xC1 vs 0x41) and 'AKWRECÃ‹2',
    which look like file corruption but are the same objects with a bit set. Mask to 7 bits and
    report the flag separately.
    """
    raw = b[off:off + NAME_LEN]
    flags = any(c & 0x80 for c in raw if c)
    s = bytes(c & 0x7F for c in raw).split(b'\0')[0]
    try:
        return s.decode('ascii'), flags
    except Exception:
        return '', flags


def objects(path):
    data = open(path, 'rb').read()
    top = chunks(data)
    odef = next(((o, s) for t, o, s in top if t == 'ODEF'), None)
    if not odef:
        return None, []
    off, size = odef
    out = []
    for tag, o, s in chunks(data, off + 8, off + size):
        if tag != 'OBJ' or s < POS_OFF + 12:
            continue
        p = o + 8
        nm, hib = name_at(data, p)
        if not nm:
            continue
        try:
            x, y, z = struct.unpack_from('<3f', data, p + POS_OFF)
        except struct.error:
            continue
        out.append((nm, x, y, z, o, hib))
    return top, out


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    target = sys.argv[1]
    only = None
    if '--only' in sys.argv:
        only = sys.argv[sys.argv.index('--only') + 1].lower()
    if '--scan' in sys.argv:
        want = sys.argv[sys.argv.index('--scan') + 1].lower()
        pats = ('*.lvl', '*.LVL', '*.cbt', '*.CBT', '*.rac', '*.RAC')
        files = [f for p in pats for f in glob.glob(os.path.join(target, '**', p), recursive=True)]
        seen = set()
        for f in sorted(files):
            if os.path.realpath(f) in seen:
                continue
            seen.add(os.path.realpath(f))
            try:
                _, objs = objects(f)
            except Exception:
                continue
            hit = [o for o in objs if want in o[0].lower()]
            if hit:
                print(f"\n{os.path.relpath(f, target)}   ({len(objs)} objects)")
                for nm, x, y, z, _o, _h in hit:
                    print(f"    {nm:<10}  X={x:10.1f}  Y={y:8.1f}  Z={z:10.1f}")
        return 0

    top, objs = objects(target)
    if top is None:
        print("no ODEF chunk - is this a level file?"); return 1
    print(f"{os.path.basename(target)}")
    print("chunks: " + ', '.join(f"{t}({s})" for t, _o, s in top))
    print(f"\n{len(objs)} objects\n")
    counts = {}
    for nm, x, y, z, o, hib in objs:
        counts[nm] = counts.get(nm, 0) + 1
        if only and only not in nm.lower():
            continue
        print(f"  @0x{o:06X}  {nm:<10}  X={x:10.1f}  Y={y:8.1f}  Z={z:10.1f}")
    if not only:
        print("\nby class:")
        for nm, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {n:4}  {nm}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
