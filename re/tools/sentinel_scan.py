#!/usr/bin/env python3
r"""sentinel_scan.py - count sentinel byte patterns in a capture's raw snapshot files (Task 10 item 006; H4 funnel).

    python tools\sentinel_scan.py --capture 006-null                                  # null scan: expects 0 aligned u32 hits
    python tools\sentinel_scan.py --capture 006-variant-a --label variant_scan        # variant run: hits + resolved chain
    python tools\sentinel_scan.py --dir <scratch>\x --values 695,697 --no-manifest    # offline / test

Reads every raw\*.bin written by tools\snapshot.py (snapshot.bin / snapshot-2.bin / frame0.bin = .data 0x4c2000-
0x669ef8, class init+bss; heap-0x<base>.bin = a heap or pool region read with --heaps --read-heaps, class
heap-offset from that base) and counts, per file and per value: u32 LE at any byte offset (`u32_any`, bytes.count),
u32 LE at 4-aligned offsets (`u32_aligned`, numpy; the hits that can be a field), u16 LE (`u16_any`, expected noise),
f32 of the value and of value/10 (`f32`, `f32_tenths`: armour is stored as integer tenths in the file, a float copy is
the alternative hypothesis). Aligned hits are listed with their address (VA for the .data files, base+offset for
heap files) up to --max-hits per value.

Chain: with the .data file present the tool follows [[[0x54a264]]+0x70] (world_root bss -> world ctx -> player
entity; fold-in L040/L041) through the stored heap regions and, when every hop lands in a stored file, prints the
24 dwords at entity +0x138/+0x158/+0x178 (the predicted current[8]/max[8]/copy-B blocks, class heap-offset,
proposed) so a variant run can compare them with the file's armour list directly; a hop outside every stored
region is reported as such (read the null: the region was not read, nothing more).

Funnel (printed and stored): files -> bytes scanned -> hits per pattern per file. Result merged into
captures\<id>\manifest.json under --label (default `null_scan`) and read back (H3); --no-manifest skips that.
A null run is "usable" when every value has 0 aligned u32 hits in every file (u16 noise is recorded, not judged).
Exit 0 always once the files were read (the verdict is data); 2 when no raw file exists.
"""
import argparse
import glob
import hashlib
import json
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE, END = 0x4c2000, 0x669ef8
WORLD_ROOT = 0x54a264           # bss; world_root (globals.tsv, supported)
PLAYER_OFF = 0x70               # world ctx + 0x70 = player entity (heap-offset, proposed until a second instance)
ARMOUR_OFFS = (0x138, 0x158, 0x178)
DEFAULT_VALUES = "695,697,699,701,703,705,707,709"


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def region_of(fname):
    b = os.path.basename(fname).lower()
    if b.startswith("heap-0x"):
        return "heap", int(b[5:-4], 16)
    return "data", BASE


def scan_file(path, vals, max_hits):
    blob = open(path, "rb").read()
    kind, base = region_of(path)
    arr = np.frombuffer(blob[: len(blob) // 4 * 4], dtype=np.uint32)
    out = {"file": os.path.relpath(path, ROOT), "class": "init+bss" if kind == "data" else "heap-offset", "base": hex(base),
           "bytes": len(blob), "md5": md5f(path), "hits": {}}
    for v in vals:
        h = {"u32_any": blob.count(struct.pack("<I", v)), "u16_any": blob.count(struct.pack("<H", v)) if v < 65536 else None,
             "f32": blob.count(struct.pack("<f", float(v))), "f32_tenths": blob.count(struct.pack("<f", v / 10.0))}
        idx = np.nonzero(arr == v)[0]
        h["u32_aligned"] = int(len(idx))
        h["aligned_addrs"] = [hex(base + 4 * int(i)) for i in idx[:max_hits]]
        out["hits"][str(v)] = h
    return out, blob, kind, base


def follow_chain(regions):
    """regions: list of (kind, base, blob). Returns the chain record."""
    def read_u32(addr):
        for kind, base, blob in regions:
            if base <= addr and addr + 4 <= base + len(blob):
                return struct.unpack_from("<I", blob, addr - base)[0], kind, base
        return None, None, None
    rec = {"root": hex(WORLD_ROOT), "hops": []}
    v, k, b = read_u32(WORLD_ROOT)
    rec["hops"].append({"read": hex(WORLD_ROOT), "value": hex(v) if v is not None else None, "in": (k, hex(b)) if k else None})
    if not v:
        rec["result"] = "world_root null or .data file absent"; return rec
    ctx, k2, b2 = read_u32(v)
    rec["hops"].append({"read": hex(v), "value": hex(ctx) if ctx is not None else None, "in": (k2, hex(b2)) if k2 else None})
    if ctx is None:
        rec["result"] = "hop 1 (world ctx pointer) outside every stored region: read the null - that heap was not stored"; return rec
    if not ctx:
        rec["result"] = "world ctx pointer is null (no mission loaded)"; return rec
    ent, k3, b3 = read_u32(ctx + PLAYER_OFF)
    rec["hops"].append({"read": hex(ctx + PLAYER_OFF), "value": hex(ent) if ent is not None else None, "in": (k3, hex(b3)) if k3 else None})
    if ent is None:
        rec["result"] = "hop 2 (ctx+0x70) outside every stored region"; return rec
    if not ent:
        rec["result"] = "player entity null"; return rec
    blocks = {}
    for off in ARMOUR_OFFS:
        vals = []
        for i in range(8):
            x, _, _ = read_u32(ent + off + 4 * i)
            vals.append(x)
        blocks["+0x%x" % off] = vals
    rec["entity"] = hex(ent); rec["armour_blocks"] = blocks
    rec["result"] = "resolved" if all(x is not None for b in blocks.values() for x in b) else "entity outside every stored region"
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--capture"); g.add_argument("--dir")
    ap.add_argument("--values", default=DEFAULT_VALUES)
    ap.add_argument("--label", default="null_scan")
    ap.add_argument("--max-hits", type=int, default=64)
    ap.add_argument("--no-manifest", action="store_true")
    ap.add_argument("--map-root", default=ROOT)
    a = ap.parse_args()
    d = a.dir or os.path.join(a.map_root, "captures", a.capture)
    vals = [int(x, 0) for x in a.values.split(",")]
    files = sorted(f for f in glob.glob(os.path.join(d, "raw", "*.bin")))
    if not files:
        print("no raw\\*.bin under %s (nothing scanned; snapshot.py writes them)" % d); return 2
    results, regions = [], []
    for f in files:
        r, blob, kind, base = scan_file(f, vals, a.max_hits)
        results.append(r); regions.append((kind, base, blob))
    chain = follow_chain(regions)
    usable = all(r["hits"][str(v)]["u32_aligned"] == 0 for r in results for v in vals)
    total = sum(r["bytes"] for r in results)
    print("funnel: %d files -> %d bytes -> aligned u32 hits per value:" % (len(files), total))
    for v in vals:
        agg = {k: sum((r["hits"][str(v)][k] or 0) for r in results) for k in ("u32_any", "u32_aligned", "u16_any", "f32", "f32_tenths")}
        print("  %5d  u32_aligned %d  u32_any %d  u16_any %d  f32 %d  f32_tenths %d" % (v, agg["u32_aligned"], agg["u32_any"], agg["u16_any"], agg["f32"], agg["f32_tenths"]))
        for r in results:
            if r["hits"][str(v)]["aligned_addrs"]:
                print("         %s: %s" % (r["file"], " ".join(r["hits"][str(v)]["aligned_addrs"][:12])))
    print("chain [[[0x54a264]]+0x70]: %s%s" % (chain["result"], (" entity %s blocks %s" % (chain.get("entity"), chain.get("armour_blocks"))) if "entity" in chain else ""))
    print("verdict: %s" % ("usable null frame (0 aligned u32 hits for every value)" if usable else "aligned hits present (see above)"))
    block = {"tool": "tools/sentinel_scan.py 0.1", "values": vals, "files": results, "chain": chain, "usable_null": usable,
             "method": "bytes.count for *_any/f32 (any offset); numpy uint32 == value for u32_aligned (4-aligned); chain by dword reads in stored regions"}
    if not a.no_manifest:
        mp = os.path.join(d, "manifest.json")
        m = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
        m[a.label] = block
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(m, fh, indent=1)
        rb = json.load(open(mp, encoding="utf-8"))
        assert rb[a.label]["usable_null"] == usable, "manifest read-back mismatch"
        print("manifest %s: '%s' written and read back" % (mp, a.label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
