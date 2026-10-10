"""RIFF WAVE and GPW (GAS0) reading/writing for the I'76 HD sound pack.

GPW layout, verified 2026-10-10 against three sources before any writer was written:
  * i76-map\\data\\fmt\\other_formats.py `GPW` struct: 'GAS0' magic + 6 x i32
    (priority, max_instances, play_mode, volume, random_pitch, frequency) + RIFF WAVE;
  * docs/SOUND-HD-PACK.md 1.3 item 3: the loader starts the RIFF at +0x1c and copies 7 dwords to voice
    +0x30..+0x48 -- that is the magic plus the 6 fields (frequency lands at +0x48, which 0x425753 overwrites);
  * every stock .gpw in I76.ZFS: bytes 0x1c..0x20 are 'RIFF' (checked by `split_gpw`).
So the header is 28 bytes = magic + SIX ints. ("7 x i32" in the design doc counts the magic; the research survey
unpacked 7 ints after the magic and its gas_* columns are shifted by one, its gas_freq column is 'RIFF' as an int.)

The engine's RIFF walk (0x425573..0x42563d) needs RIFF/WAVE, a `fmt ` chunk of >= 14 bytes and a `data` chunk,
honouring odd-size padding. Every file written here is: RIFF, WAVE, `fmt ` (16 bytes, PCM tag 1), `data`, nothing else.
"""
import struct

import numpy as np

GAS_MAGIC = b"GAS0"
GAS_HEADER_SIZE = 0x1C
GAS_FIELDS = ("priority", "max_instances", "play_mode", "volume", "random_pitch", "frequency")


class WavError(ValueError):
    pass


def split_gpw(blob):
    """Return (header28 bytes or None, gas dict or None, riff bytes)."""
    if blob[:4] == GAS_MAGIC:
        if len(blob) < GAS_HEADER_SIZE + 12 or blob[GAS_HEADER_SIZE:GAS_HEADER_SIZE + 4] != b"RIFF":
            raise WavError("GAS0 header not followed by RIFF at +0x1c")
        vals = struct.unpack_from("<6i", blob, 4)
        return blob[:GAS_HEADER_SIZE], dict(zip(GAS_FIELDS, vals)), blob[GAS_HEADER_SIZE:]
    return None, None, blob


def walk_riff(riff):
    """Chunk walk like the loader: returns (chunks list [(id, offset, size)], fmt dict, data bytes)."""
    if riff[:4] != b"RIFF" or riff[8:12] != b"WAVE":
        raise WavError("not RIFF/WAVE")
    end = min(len(riff), 8 + struct.unpack_from("<I", riff, 4)[0])
    pos = 12
    chunks, fmt, data = [], None, None
    while pos + 8 <= end:
        cid = riff[pos:pos + 4]
        csz = struct.unpack_from("<I", riff, pos + 4)[0]
        body = riff[pos + 8:pos + 8 + csz]
        chunks.append((cid.decode("latin1"), pos, csz))
        if cid == b"fmt " and fmt is None:
            if csz < 14:
                raise WavError("fmt chunk %d bytes (< 14)" % csz)
            tag, ch, rate, bps, align = struct.unpack_from("<HHIIH", body, 0)
            bits = struct.unpack_from("<H", body, 14)[0] if csz >= 16 else 8
            fmt = dict(tag=tag, channels=ch, rate=rate, byte_rate=bps, block_align=align, bits=bits, fmt_size=csz)
        elif cid == b"data" and data is None:
            data = body
        pos += 8 + csz + (csz & 1)
    if fmt is None or data is None:
        raise WavError("fmt/data missing")
    return chunks, fmt, data


def decode(blob):
    """blob (.wav or .gpw bytes) -> dict(gas_header, gas, fmt, chunks, x float64 mono in [-1,1), data_bytes)."""
    hdr, gas, riff = split_gpw(blob)
    chunks, fmt, data = walk_riff(riff)
    if fmt["tag"] != 1:
        raise WavError("fmt tag %d (not PCM)" % fmt["tag"])
    if fmt["bits"] == 8:
        x = (np.frombuffer(data, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif fmt["bits"] == 16:
        x = np.frombuffer(data[: len(data) // 2 * 2], dtype="<i2").astype(np.float64) / 32768.0
    else:
        raise WavError("bits %d unsupported" % fmt["bits"])
    if fmt["channels"] > 1:
        x = x[: len(x) // fmt["channels"] * fmt["channels"]].reshape(-1, fmt["channels"]).mean(axis=1)
    return dict(gas_header=hdr, gas=gas, fmt=fmt, chunks=chunks, x=x, data_bytes=len(data))


def to_pcm16(x, seed=None):
    """float [-1,1) -> little-endian int16 bytes, TPDF dither (seeded -> deterministic output)."""
    x = np.asarray(x, dtype=np.float64)
    if seed is not None:
        rng = np.random.default_rng(seed)
        d = (rng.random(len(x)) - rng.random(len(x)))  # TPDF, +/- 1 LSB
    else:
        d = 0.0
    q = np.round(x * 32767.0 + d)
    return np.clip(q, -32768, 32767).astype("<i2").tobytes()


def build_riff(pcm_bytes, rate, bits=16, channels=1):
    """RIFF/WAVE with exactly `fmt ` (16 bytes) then `data`."""
    align = channels * bits // 8
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * align, align, bits)
    data = pcm_bytes
    pad = b"\0" if len(data) & 1 else b""
    body = b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data + pad
    return b"RIFF" + struct.pack("<I", len(body)) + body


def build_gpw(stock_header, riff):
    """Stock 28-byte GAS0 header kept verbatim (priority/instances/mode/volume/random-pitch/frequency) + new RIFF."""
    if stock_header is None or len(stock_header) != GAS_HEADER_SIZE or stock_header[:4] != GAS_MAGIC:
        raise WavError("need the stock 28-byte GAS0 header")
    return bytes(stock_header) + riff
