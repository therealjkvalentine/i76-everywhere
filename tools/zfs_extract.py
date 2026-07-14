#!/usr/bin/env python3
"""Extract Interstate '76 ZFS archives (I76.ZFS, "ZFSF" v1).

Format (verified against the GOG I76.ZFS byte-by-byte; matches Open76 & That Tony):
  header (0x1C bytes):
    char[4]  magic "ZFSF"
    u32      version (=1)
    u32      unk (0x10)
    u32      filesPerDirBlock (100)
    u32      numFilesTotal
    u32      unk2
    u32      unk3
  directory blocks, first at 0x1C:
    u32      nextBlockOffset (file offset of the next block, 0/garbage after last)
    then filesPerDirBlock entries of 36 bytes:
      char[16] name (NUL-padded, effectively lowercase)
      u32      dataOffset      (absolute file offset of raw payload)
      u32      id              (running index)
      u32      length          (stored/compressed size)
      u32      timestamp
      u8       compression     (0 = stored, 2 = LZO1X, 4 = LZO1Y)
      u24      decompressedLength
  file payloads sit between/after blocks at their dataOffset.

Usage:
  zfs_extract.py I76.ZFS --list [substr]
  zfs_extract.py I76.ZFS OUTDIR [substr]
"""
import struct, sys, os

ENTRY = struct.Struct("<16s4I")   # + 1 byte comp + 3 bytes dlen = 36 total
HEADER = struct.Struct("<4s6I")

def parse(data):
    magic, version, _u1, per_dir, total, _u2, _u3 = HEADER.unpack_from(data, 0)
    if magic != b"ZFSF" or version != 1:
        sys.exit(f"not a ZFSF v1 archive (magic={magic!r} v{version})")
    entries, block = [], HEADER.size
    while len(entries) < total:
        next_block = struct.unpack_from("<I", data, block)[0]
        pos = block + 4
        for _ in range(min(per_dir, total - len(entries))):
            raw_name, off, fid, length, _ts = ENTRY.unpack_from(data, pos)
            comp = data[pos + 32]
            dlen = int.from_bytes(data[pos + 33:pos + 36], "little")
            name = raw_name.split(b"\0")[0].decode("ascii", "replace").lower()
            entries.append((name, off, length, comp, dlen))
            pos += 36
        block = next_block
    return entries

_lzo = None
def decompress(payload, comp, dlen):
    """comp 2 = LZO1X, 4 = LZO1Y - decompressed with liblzo2 via ctypes, the same
    library Open76 P/Invokes. macOS: brew install lzo. Windows: point LZO2_DLL at
    an lzo2.dll (e.g. from the conda-forge `lzo` package, Library/bin/lzo2.dll)."""
    if comp == 0:
        return payload
    global _lzo
    import ctypes, ctypes.util
    if _lzo is None:
        candidates = ([os.environ["LZO2_DLL"]] if os.environ.get("LZO2_DLL") else []) + [
            ctypes.util.find_library("lzo2"),
            "/opt/homebrew/lib/liblzo2.dylib",
            "lzo2.dll", "liblzo2-2.dll",
        ]
        for path in candidates:
            if not path:
                continue
            try:
                _lzo = ctypes.CDLL(path)
                break
            except OSError:
                continue
        if _lzo is None:
            sys.exit("liblzo2 not found - set LZO2_DLL or install lzo")
    fn = _lzo.lzo1x_decompress_safe if comp == 2 else _lzo.lzo1y_decompress_safe
    dst = ctypes.create_string_buffer(dlen)
    out_len = ctypes.c_size_t(dlen)
    rc = fn(payload, ctypes.c_size_t(len(payload)), dst, ctypes.byref(out_len), None)
    if rc != 0:
        raise ValueError(f"lzo rc={rc}")
    return dst.raw[:out_len.value]

def main():
    argv = sys.argv[1:]
    do_list = "--list" in argv
    argv = [a for a in argv if a != "--list"]
    data = open(argv[0], "rb").read()
    entries = parse(data)
    pat = ""
    if do_list:
        pat = argv[1].lower() if len(argv) > 1 else ""
        for n, o, l, c, d in entries:
            if pat in n:
                print(f"{n:16s} {l:9d} comp={c} -> {d}")
        return
    out = argv[1]; pat = argv[2].lower() if len(argv) > 2 else ""
    os.makedirs(out, exist_ok=True)
    n_ok = n_fail = 0
    for name, off, length, comp, dlen in entries:
        if pat and pat not in name:
            continue
        try:
            body = decompress(data[off:off + length], comp, dlen)
            open(os.path.join(out, name), "wb").write(body)
            n_ok += 1
        except Exception as e:
            print(f"FAIL {name}: {e}", file=sys.stderr); n_fail += 1
    print(f"extracted {n_ok} files to {out}" + (f" ({n_fail} failed)" if n_fail else ""))

if __name__ == "__main__":
    main()
