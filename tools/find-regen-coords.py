"""
find-regen-coords.py - locate REGEN (repair) spots inside an I'76 level and report their
placement, so you can drive straight to one.

Why: 33 of the 40 mirrored community maps contain a `regen` object (the "healing building"),
which is the only stimulus that raises armor on demand - and a repair event is what the live
armor hunt needs, because damage has been unreliable in every form tried.

Knowing a map HAS a regen is not enough; you have to reach it. I'76 level files are chunked
(the same BWD2-style tagging as .VCF: 4-char tag + u32 size), and vehicles/objects are placed
with coordinates near their class-name string. This dumps the bytes around each `regen`
occurrence and interprets nearby words as ints and floats, so the placement fields can be
identified by eye against known map dimensions.

Usage: find-regen-coords.py <level file> [context_bytes]
"""
import struct, sys, os, re


def chunks(data):
    """Walk 4-char-tag + u32-size chunks, the format .VCF uses."""
    out, o = [], 0
    while o + 8 <= len(data):
        tag = data[o:o + 4]
        if not all(c == 0 or 32 <= c < 127 for c in tag):
            break
        size = struct.unpack_from('<I', data, o + 4)[0]
        if size < 8 or o + size > len(data):
            break
        out.append((tag.decode('latin1').rstrip('\0'), o, size))
        o += size
    return out


def cstr(b, off, maxlen=32):
    s = []
    for i in range(off, min(off + maxlen, len(b))):
        c = b[i]
        if c == 0:
            break
        if c < 32 or c > 126:
            return ''
        s.append(chr(c))
    return ''.join(s)


def main():
    path = sys.argv[1]
    ctx = int(sys.argv[2]) if len(sys.argv) > 2 else 96
    data = open(path, 'rb').read()
    print(f"{os.path.basename(path)}  ({len(data):,} bytes)\n")

    ch = chunks(data)
    if ch:
        print("top-level chunks:")
        seen = {}
        for tag, off, size in ch[:40]:
            seen[tag] = seen.get(tag, 0) + 1
            print(f"  @0x{off:06X}  {tag:<6} size={size}")
        print()

    hits = [m.start() for m in re.finditer(rb'regen', data, re.I)]
    print(f"{len(hits)} 'regen' occurrences\n")
    for h in hits:
        lo = max(0, h - ctx)
        hi = min(len(data), h + ctx)
        print(f"=== regen @0x{h:06X} ('{cstr(data, h)}') ===")
        # nearby strings give the record's neighbours (other object class names)
        near = []
        for m in re.finditer(rb'[ -~]{4,20}', data[lo:hi]):
            s = m.group().decode('latin1')
            if s.strip():
                near.append((lo + m.start(), s))
        print("  nearby strings: " + ', '.join(f"0x{a:06X}:{s}" for a, s in near[:8]))
        # words around it, as int and float - placement is usually floats in world units
        print(f"  {'off':>8} {'hex':>10} {'int':>12} {'float':>14}")
        start = (h - ctx) & ~3
        for a in range(start, h + ctx, 4):
            if a < 0 or a + 4 > len(data):
                continue
            w = data[a:a + 4]
            i = struct.unpack('<i', w)[0]
            f = struct.unpack('<f', w)[0]
            fs = f"{f:.3f}" if 1e-6 < abs(f) < 1e7 else ''
            mark = '  <-- string' if a <= h < a + 4 else ''
            print(f"  {a - h:+8d} {struct.unpack('<I', w)[0]:10X} {i:12d} {fs:>14}{mark}")
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
