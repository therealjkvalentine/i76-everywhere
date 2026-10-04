"""LZO1X / LZO1Y decompressor (LZO 1.00 stream format), pure Python.

Port of recon-2026-09-04\\recon\\formats\\lzo.py (the minilzo state machine); that decoder decoded all 5,623
compressed I76.ZFS payloads to exactly flags>>8 bytes consuming exactly `size` input bytes (formats REPORT 2.3),
and the game's own decoders at 0x4babd8 (LZO1X, M2_MAX_OFFSET 0x800) / 0x4baa00 (LZO1Y, 0x400) were identified by
asm shape (zfs-lzo-refute section 2). No compressor: LZO 1.00's compressor is not reproducible with 2.x, so gate R
measures recompression identity only when a compressor is supplied (it is not); the archive gate is the
stored-mode repack (zfs.repack_stored).
"""


class LzoError(Exception):
    pass


def decompress(src, variant="1x", out_len=None):
    """Decode one LZO1X ('1x') or LZO1Y ('1y') stream. Returns (bytes, consumed_input_bytes).
    out_len, when given, is checked against the decoded length (LzoError on mismatch)."""
    if variant not in ("1x", "1y"):
        raise LzoError("variant must be '1x' or '1y'")
    ip = 0
    out = bytearray()
    m2_max_offset = 0x0800 if variant == "1x" else 0x0400

    def copy_match(mpos, cnt):
        for k in range(cnt):
            out.append(out[mpos + k])

    state = "next"
    t = src[ip]
    if t > 17:
        ip += 1
        t -= 17
        if t < 4:
            state = "match_next"
        else:
            out += src[ip:ip + t]
            ip += t
            state = "first_literal_run"
    while True:
        if state == "next":
            t = src[ip]; ip += 1
            if t >= 16:
                state = "match"; continue
            if t == 0:
                while src[ip] == 0:
                    t += 255; ip += 1
                t += 15 + src[ip]; ip += 1
            out += src[ip:ip + t + 3]; ip += t + 3
            state = "first_literal_run"; continue
        if state == "first_literal_run":
            t = src[ip]; ip += 1
            if t >= 16:
                state = "match"; continue
            mpos = len(out) - (1 + m2_max_offset) - (t >> 2) - (src[ip] << 2); ip += 1
            if mpos < 0:
                raise LzoError("lookbehind")
            copy_match(mpos, 3); state = "match_done"; continue
        if state == "match":
            if t >= 64:
                if variant == "1x":
                    mpos = len(out) - 1 - ((t >> 2) & 7) - (src[ip] << 3); ip += 1; t = (t >> 5) - 1
                else:
                    mpos = len(out) - 1 - ((t >> 2) & 3) - (src[ip] << 2); ip += 1; t = (t >> 4) - 3
            elif t >= 32:
                t &= 31
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 31 + src[ip]; ip += 1
                mpos = len(out) - 1 - ((src[ip] >> 2) + (src[ip + 1] << 6)); ip += 2
            elif t >= 16:
                mpos = len(out) - ((t & 8) << 11); t &= 7
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 7 + src[ip]; ip += 1
                mpos -= (src[ip] >> 2) + (src[ip + 1] << 6); ip += 2
                if mpos == len(out):
                    if out_len is not None and len(out) != out_len:
                        raise LzoError("decoded %d bytes, expected %d" % (len(out), out_len))
                    return bytes(out), ip  # EOF marker
                mpos -= 0x4000
            else:
                mpos = len(out) - 1 - (t >> 2) - (src[ip] << 2); ip += 1
                if mpos < 0:
                    raise LzoError("lookbehind")
                copy_match(mpos, 2); state = "match_done"; continue
            if mpos < 0:
                raise LzoError("lookbehind mpos=%d out=%d t=%d" % (mpos, len(out), t))
            copy_match(mpos, t + 2); state = "match_done"; continue
        if state == "match_done":
            t = src[ip - 2] & 3
            state = "next" if t == 0 else "match_next"; continue
        if state == "match_next":
            out += src[ip:ip + t]; ip += t
            t = src[ip]; ip += 1; state = "match"; continue


lzo_decompress = decompress  # name used by the recon script
