#!/usr/bin/env python3
"""
Parse Interstate '76's force\\*.frc effect files.

WHY: the engine ships 14 pre-authored force effects. They are the vocabulary the
original authors chose for THIS car on a 1997 force-feedback wheel - what a cannon
should feel like, how long an explosion rings, how hard a tyre blowout kicks. For
synthesising weapon and engine feel that is better guidance than taste.

This is a DESIGN REFERENCE, not a runtime dependency. Nothing in the interposer
needs it, and since our layer coexists with the game (tools/ffb/README.md) the
engine still plays these itself.

FORMAT: RIFF, form type "FORC" - Immersion's Force Resource layout.

    RIFF <size> FORC
      LIST <size> INFO        INAM / ICMT / ISFT / ICOP   (all empty here)
      trgt <16>               DirectInput target GUID
      LIST <size> trak
        LIST <size> efct
          id   <4>            effect id
          data <size>         the effect itself

  data payload:
    +0   int32     104 in every file - the size of the header+envelope region
    +4   char[16]  effect type name, e.g. "SawtoothDown1", "UserDefined1"
    +20  int32[12] SIX (time, magnitude) keyframe pairs - the envelope
    +68  int32[]   parameter block; semantics NOT identified, printed raw

  Magnitudes read as percent: 100 (0x64) recurs throughout, and the envelope
  values sit in +/-126.

  What is legible: the type name and the envelope. What is NOT: most of the
  parameter block. It is reported raw rather than guessed at.

Usage:
    python tools/ffb/parse-frc.py "C:/path/to/Interstate 76/force"
    python tools/ffb/parse-frc.py                 # auto-find from the running game
"""
import struct
import sys
import os
import glob

TARGET_GUID_BYTES = bytes.fromhex("95e0ac04a81fd011aa2200a0c911f471")


def guid_str(b):
    """Format 16 raw bytes as a Windows GUID (first three fields little-endian)."""
    d1, d2, d3 = struct.unpack_from("<IHH", b, 0)
    rest = b[8:]
    return "{%08X-%04X-%04X-%s-%s}" % (
        d1, d2, d3, rest[:2].hex().upper(), rest[2:].hex().upper())


def walk_chunks(buf, start, end):
    """Yield (fourcc, payload_start, payload_size) for chunks in [start, end)."""
    p = start
    while p + 8 <= end:
        cc = buf[p:p + 4].decode("latin-1")
        size = struct.unpack_from("<I", buf, p + 4)[0]
        yield cc, p + 8, size
        p += 8 + size + (size & 1)      # RIFF chunks are word-aligned


def find_data_chunks(buf):
    """Locate every 'data' chunk, descending through the LIST nesting."""
    out = []

    def descend(lo, hi):
        for cc, off, size in walk_chunks(buf, lo, hi):
            if size < 0 or off + size > len(buf):
                return
            if cc == "LIST":
                # a LIST payload begins with its own 4CC form type
                descend(off + 4, off + size)
            elif cc == "data":
                out.append((off, size))
            elif cc == "trgt":
                out.append(("trgt", off, size))
    descend(12, len(buf))               # skip "RIFF"<size>"FORC"
    return out


def parse_effect(buf, off, size):
    """
    Returns (hdr_size, type_name, strings, mid_kind, params).

    NOTE ON WHAT IS NOT DECODED. An earlier version of this read six (time,
    magnitude) int32 pairs at payload+20 and called it an envelope. That was
    wrong. The region between the type name and payload+68 is:

      * a VARIABLE-length null-terminated type name (7 chars for "Cosine1",
        13 for "SawtoothDown1"), so nothing after it sits at a fixed offset; and
      * in several files, 0xCD fill - the MSVC debug heap's uninitialised-memory
        pattern, written straight to disk. It is not data at all.

    Reading it as int32 pairs produced magnitudes like 842150451, which is
    0x32323233, which is the ASCII text "3222". A number that large in a field
    whose neighbours are all <= 126 was the tell.

    So this reports the region's KIND rather than inventing values for it. The
    type name and the payload+68 parameter block are at consistent positions and
    are reported as read.
    """
    hdr_size = struct.unpack_from("<i", buf, off)[0]

    mid = buf[off + 4:off + 68]
    # every printable null-terminated string in the region, in order
    strings = [s.decode("latin-1", "replace")
               for s in mid.split(b"\0")
               if s and all(32 <= c < 127 for c in s)]
    type_name = strings[0] if strings else "?"

    body = mid[len(type_name) + 1:]
    if body.count(b"\xcd") > len(body) // 2:
        mid_kind = "0xCD fill (uninitialised)"
    elif body.strip(b"\0") == b"":
        mid_kind = "zero"
    else:
        mid_kind = "table/unknown"

    params = []
    p = off + 68
    while p + 4 <= off + size:
        params.append(struct.unpack_from("<i", buf, p)[0])
        p += 4
    return hdr_size, type_name, strings[1:], mid_kind, params


def main():
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = None
        # try the running game, then the usual install spots
        for cand in (
            r"C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801\Interstate 76\force",
            r"C:\Games\Interstate 76\force",
            r"C:\GOG Games\Interstate 76\force",
        ):
            if os.path.isdir(cand):
                folder = cand
                break
        if not folder:
            print("Pass the path to the game's force\\ folder.")
            return 1

    # De-duplicated by real path. Globbing "*.FRC" and "*.frc" and concatenating
    # doubles every file on Windows, where glob is CASE-INSENSITIVE - each pattern
    # matches all 14. That silently listed every effect twice.
    seen = set()
    files = []
    for pat in ("*.FRC", "*.frc"):
        for p in glob.glob(os.path.join(folder, pat)):
            key = os.path.normcase(os.path.realpath(p))
            if key not in seen:
                seen.add(key)
                files.append(p)
    files.sort()
    if not files:
        print("No .frc files in " + folder)
        return 1

    print("force effects in %s\n" % folder)
    rows = []
    for path in files:
        with open(path, "rb") as f:
            buf = f.read()
        if buf[:4] != b"RIFF" or buf[8:12] != b"FORC":
            print("%-14s NOT a RIFF/FORC file" % os.path.basename(path))
            continue

        chunks = find_data_chunks(buf)
        target = None
        effects = []
        for c in chunks:
            if c[0] == "trgt":
                target = buf[c[1]:c[1] + c[2]]
            else:
                effects.append(parse_effect(buf, c[0], c[1]))

        name = os.path.basename(path)
        rows.append((name, [e[1] for e in effects]))

        tgt_ok = (target == TARGET_GUID_BYTES) if target else False
        print("=" * 78)
        print("%-14s  %d bytes  %d effect(s)   target %s" % (
            name, len(buf), len(effects),
            "standard" if tgt_ok else (guid_str(target) if target else "none")))
        for (hdr, ename, extra, mid_kind, params) in effects:
            print("   type %-16s  mid-region: %s%s" % (
                ename, mid_kind, ("   also: %r" % extra) if extra else ""))
            # Printed raw. Guessing at unidentified fields and writing the guess
            # down as if it were known is exactly how the "+0x08 is a rotation
            # matrix" error in the memory map happened - so these stay raw.
            print("   params (semantics unidentified): %s" % params)
        print()

    # --- what this is actually for --------------------------------------------
    print("=" * 78)
    print("SUMMARY - the authored vocabulary")
    print("=" * 78)
    for (fname, types) in rows:
        comp = " + ".join(types)
        print("%-14s %s" % (fname, comp))
    print()
    allt = sorted(set(t for _, ts in rows for t in ts))
    print("distinct effect types used: %s" % ", ".join(allt))
    print()
    print("THE FINDING THAT MATTERS, and it is certain because it is just the type")
    print("names: these effects are COMPOSED, not single primitives. A tyre blowout")
    print("is ConstantForce + Sine superimposed. Missiles are a Cosine and a")
    print("ConstantForce driven by a Sequence. The 1997 authors built feel by")
    print("LAYERING a steady force with an oscillation - which is precisely the")
    print("additive model FfbMixer.ps1 uses (steady + texture*osc + transients).")
    print("That is independent corroboration of the mixer's shape from the people")
    print("who tuned this game for this wheel.")
    print()
    print("What is NOT decoded: the parameter block. Peak magnitude and duration")
    print("are presumably in there - 100 (0x64) and +/-126 recur, suggesting")
    print("percent - but the fields are not pinned, so no numbers are claimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
