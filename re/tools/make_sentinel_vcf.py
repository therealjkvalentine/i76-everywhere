#!/usr/bin/env python3
r"""make_sentinel_vcf.py - Task 10 item 006: a loose ADDON .vcf whose armour block carries sentinel values.

    python tools\make_sentinel_vcf.py --out captures\006-sentinel\vppt01.vcf
    python tools\make_sentinel_vcf.py --src <stock.vcf> --out <dst.vcf> --armour-list 695,697,699,701,703,705,707,709 [--name SENTINEL]

Built on tools\i76fmt\bwd2 (parse -> edit one chunk body -> serialise; gate R parser, never a byte poke at a
guessed offset). The VCFC body layout it relies on: name[16] vdf[13] vtf[13] 3 x u32 wheel[13] 'null'[13]
wheel[13] then 8 x u32 armour in integer tenths at body+93 = file 0x79 (fold-in L063; verified on the stock
vppt01.vcf and on the user's ADDON\valepre4.orig/.vcf pair whose only differing bytes are file 121..152).
The tool refuses a source whose middle wheel field is not 'null' (the 3-wheel layout is the precondition, H5).

Survey before building: C:\Users\james\i76-uncap-lab\autotest\setup\make-test-variant.py --armor-list and
tools\vehicle\vcf.py set-armor do the same edit by searching the last '.wdf' string; this port uses the
parsed chunk and adds the read-back (H3): the output is re-parsed, the armour list must read back exactly,
the byte diff against the source must lie entirely inside the 32-byte armour block, and a JSON sidecar
(<out>.json) records src/out md5, the values, their little-endian byte patterns (for tools\sentinel_scan.py)
and the diff offsets, so the capture manifest can cite the file it loaded.

Default values: 8 distinct odd numbers starting at 695/697 (the method doc's "armour = 695 (and 697 adjacent)"),
one per slot, so a memory hit also tells which slot (file order FRONT,LEFT,RIGHT,REAR x current/max per the
fold-in's ARMOR-INVESTIGATION reading; the memory order is what item 006 measures, never assumed).
Nothing here writes into the game folder: the user copies the file to ADDON\ at the console (H10).
Exit 0 = written and read back; 1 = read-back mismatch or diff outside the armour block; 2 = bad input.
"""
import argparse
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from i76fmt import bwd2  # noqa: E402

ROOT = os.path.dirname(HERE)
DEFAULT_SRC = os.path.join(ROOT, "recon-2026-09-04", "recon", "formats", "zfs_out", "vppt01.vcf")
DEFAULT_VALUES = "695,697,699,701,703,705,707,709"


def md5(b):
    return hashlib.md5(b).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=DEFAULT_SRC, help="stock .vcf (default: the ZFS-extracted vppt01.vcf in the archive)")
    ap.add_argument("--out", required=True, help="destination .vcf (write under captures\\006-sentinel\\; the user copies it to ADDON\\)")
    ap.add_argument("--armour-list", default=DEFAULT_VALUES, help="8 integers (tenths), file order")
    ap.add_argument("--name", default=None, help="optional variant name (char[16]); default keeps the stock name")
    a = ap.parse_args()

    vals = [int(x, 0) for x in a.armour_list.split(",")]
    if len(vals) != 8 or any(not (0 <= v < 2 ** 32) for v in vals):
        print("need exactly 8 unsigned 32-bit values"); return 2
    src = open(a.src, "rb").read()
    doc = bwd2.parse(src)
    if bwd2.serialise(doc) != src:
        print("source does not round-trip through i76fmt.bwd2 (gate R); refusing"); return 2
    vc = [c for c in doc.chunks if c.tag_str == "VCFC"]
    if len(vc) != 1:
        print("expected exactly one top-level VCFC chunk, found %d" % len(vc)); return 2
    c = vc[0]
    view = bwd2.vcfc(c.body)
    if view["wheels"][1].lower() != "null" or view["armour"] is None:
        print("VCFC layout precondition failed: wheels=%r armour=%r (3-wheel layout with 'null' in the middle expected; H5)"
              % (view["wheels"], view["armour"])); return 2
    before = list(view["armour"])
    body = bytearray(c.body)
    struct.pack_into("<8I", body, bwd2.VCFC_ARMOUR_OFF, *vals)
    if a.name is not None:
        nm = a.name.encode("latin1")[:15].ljust(16, b"\0")
        body[0:16] = nm
    c.body = bytes(body)
    out = bwd2.serialise(doc)

    # byte diff against the source: every differing offset must lie inside the armour block (or the name field)
    armour_file_off = c.offset + 8 + bwd2.VCFC_ARMOUR_OFF
    allowed = set(range(armour_file_off, armour_file_off + 32))
    if a.name is not None:
        allowed |= set(range(c.offset + 8, c.offset + 8 + 16))
    diff = [i for i in range(max(len(src), len(out))) if (src[i:i + 1] != out[i:i + 1])]
    outside = [i for i in diff if i not in allowed]

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "wb") as fh:
        fh.write(out)
    rb = open(a.out, "rb").read()
    rdoc = bwd2.parse(rb)
    rview = bwd2.vcfc([x for x in rdoc.chunks if x.tag_str == "VCFC"][0].body)
    ok = (rb == out) and (rview["armour"] == vals) and not outside and len(src) == len(out)

    side = {
        "tool": "tools/make_sentinel_vcf.py 0.1", "src": os.path.abspath(a.src), "src_md5": md5(src), "src_bytes": len(src),
        "out": os.path.abspath(a.out), "out_md5": md5(rb), "out_bytes": len(rb),
        "vcfc_name": rview["name"], "vdf": rview["vdf"], "vtf": rview["vtf"], "wheels": rview["wheels"],
        "armour_before_tenths": before, "armour_after_tenths": vals, "armour_readback": rview["armour"],
        "armour_file_offset": armour_file_off, "diff_offsets": diff, "diff_outside_armour": outside,
        "patterns": {str(v): {"u32_le": struct.pack("<I", v).hex(), "u16_le": struct.pack("<H", v).hex() if v < 65536 else None,
                              "f32_le": struct.pack("<f", float(v)).hex(), "f32_tenths_le": struct.pack("<f", v / 10.0).hex()} for v in vals},
        "readback_ok": ok,
    }
    sp = a.out + ".json"
    with open(sp, "w", encoding="utf-8") as fh:
        json.dump(side, fh, indent=1)
    json.load(open(sp, encoding="utf-8"))
    print("src %s md5 %s (%d B) armour %s" % (a.src, side["src_md5"], len(src), before))
    print("out %s md5 %s (%d B) armour %s" % (a.out, side["out_md5"], len(rb), rview["armour"]))
    print("armour block at file offset %d (0x%x); diff offsets %d (%s); outside the block: %d" % (
        armour_file_off, armour_file_off, len(diff), "%d..%d" % (diff[0], diff[-1]) if diff else "-", len(outside)))
    print("read-back %s; sidecar %s" % ("OK" if ok else "MISMATCH", sp))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
