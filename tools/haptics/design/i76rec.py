#!/usr/bin/env python3
"""i76rec.py - read / write .i76rec telemetry recordings (the format of tools/haptics/src/Haptics/Transport/Recording.cs).

  "I76REC01"  u32 meta_len  meta (UTF-8 JSON)
  records:    f64 host_time_s  u32 len  len bytes = one i76tel datagram (frame + its events, any version)

  python design/i76rec.py <file.i76rec>                 summary (record count, duration, datagram sizes)
  python design/i76rec.py <file.i76rec> --decode        also decode with tools/telemetry/i76tel.py (needs decode_datagram, v3 tools)

Library use: read(path) -> (meta_dict, [(t, bytes), ...]); write(path, records, meta=None).
"""
import json, os, struct, sys

MAGIC = b"I76REC01"


def read(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != MAGIC:
        raise ValueError("%s is not an .i76rec (magic %r)" % (path, data[:8]))
    ml = struct.unpack_from("<I", data, 8)[0]
    meta = json.loads(data[12:12 + ml].decode("utf-8") or "{}")
    p, recs = 12 + ml, []
    while p + 12 <= len(data):
        t, n = struct.unpack_from("<dI", data, p)
        p += 12
        if p + n > len(data):
            break                                   # truncated tail: keep what is whole
        recs.append((t, data[p:p + n]))
        p += n
    return meta, recs


def write(path, records, meta=None):
    m = json.dumps(meta or {}).encode("utf-8")
    with open(path, "wb") as f:
        f.write(MAGIC + struct.pack("<I", len(m)) + m)
        for t, b in records:
            f.write(struct.pack("<dI", float(t), len(b)) + bytes(b))


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    meta, recs = read(sys.argv[1])
    sizes = sorted(set(len(b) for _, b in recs))
    dur = recs[-1][0] - recs[0][0] if recs else 0
    print("%s: %d records, %.2f s, meta %s, datagram sizes %s%s" % (sys.argv[1], len(recs), dur, meta, sizes[:6], "..." if len(sizes) > 6 else ""))
    if "--decode" in sys.argv:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "telemetry"))
        import i76tel
        h = i76tel.Header()
        n_ev = 0
        for t, b in recs:
            fr, evs = i76tel.decode_datagram(h, b)
            n_ev += len(evs)
        print("decoded with i76tel.py: %d frames, %d events" % (len(recs), n_ev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
