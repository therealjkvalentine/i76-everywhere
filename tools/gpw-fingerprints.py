#!/usr/bin/env python3
"""Generate a fingerprint table so the sound-rumble dsound proxy can identify
which .gpw effect is playing from the PCM the game writes into a DirectSound
buffer.

The game decodes a .gpw and copies its 8-bit PCM into a secondary sound buffer,
then Play()s it. The proxy captures that PCM on Unlock and must map it back to a
sound NAME (to pick the rumble envelope). A fingerprint = (byte length, a cheap
rolling hash of the PCM) — small, and computed identically here and in the DLL.

Output line: name=length,hash   (both decimal). Consumed by sound-rumble/ and
matched against tools/rumble-envelopes.ini by name. Generated locally from the
user's own game audio; gitignored, not committed.

Usage: gpw-fingerprints.py <I76.ZFS | game-dir> [--out rumble-fingerprints.ini]
                            [--check]   # report collisions and exit
"""
import argparse, io, os, struct, sys, wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zfs_extract


def pcm_of(payload: bytes):
    riff = payload.find(b"RIFF")
    if riff < 0:
        return None
    w = wave.open(io.BytesIO(payload[riff:]))
    return w.readframes(w.getnframes())


def fingerprint(pcm: bytes):
    """(length, hash). Same 32-bit FNV-1a over EVERY byte that the DLL computes
    (once per buffer Unlock, not per frame — cheap enough). Remaining collisions
    are byte-identical files, which rumble the same anyway."""
    h = 2166136261
    for b in pcm:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return len(pcm), h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", default="rumble-fingerprints.ini")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    src = args.source
    if os.path.isdir(src):
        src = os.path.join(src, "I76.ZFS")
    data = open(src, "rb").read()

    entries = [e for e in zfs_extract.parse(data) if e[0].endswith(".gpw")]
    fps, seen, collisions = [], {}, []
    for name, off, length, comp, dlen in sorted(entries):
        pcm = pcm_of(zfs_extract.decompress(data[off:off + length], comp, dlen))
        if pcm is None:
            continue
        n, h = fingerprint(pcm)
        key = (n, h)
        if key in seen:
            collisions.append((name, seen[key]))
        seen[key] = name
        fps.append((name[:-4], n, h))

    if collisions:
        print(f"COLLISIONS ({len(collisions)}): fingerprint can't distinguish these:")
        for a, b in collisions:
            print(f"  {a} == {b}")
    else:
        print(f"OK: all {len(fps)} .gpw fingerprints unique")
    if args.check:
        sys.exit(1 if collisions else 0)

    with open(args.out, "w") as f:
        f.write("; gpw fingerprints (name=length,hash) — tools/gpw-fingerprints.py\n")
        for name, n, h in fps:
            f.write(f"{name}={n},{h}\n")
    print(f"wrote {args.out}: {len(fps)} fingerprints")


if __name__ == "__main__":
    main()
