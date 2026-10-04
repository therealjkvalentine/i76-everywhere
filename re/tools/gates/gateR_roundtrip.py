#!/usr/bin/env python3
"""Gate R (round trip; method doc 4.3). No parser output counts as evidence until parse -> serialise -> parse over
the full corpus reports 0 byte diffs.

Reads status\\roundtrip.json (written by tools\\i76fmt\\roundtrip.py; --run regenerates it first) and fails when:
any family has diff_files > 0 or parse errors; the corpus counts are below the method doc's floor (6,116 ZFS
payloads, 80 .msn, 81 .ter, 300 .vcf = 293 archived + 7 loose, loose .fnt/.frc); the stored-mode repack family is
missing or has diffs; the report is older than the parsers (any tools\\i76fmt\\*.py newer than the report) or than
I76.ZFS's md5 recorded in it; LZO recompression identity is not recorded (measured or explicitly not measured).
Batch rows carrying `parser` evidence (kind emulated-io with source i76fmt, or claim text citing i76fmt) are
accepted only when the report verdict is PASS.
"""
import os, sys, json, glob, subprocess, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make

FLOOR = {"zfs_payloads": 6116, "msn": 80, "ter": 81, "fnt": 3, "frc": 14}


def main():
    def extra(ap):
        ap.add_argument("--run", action="store_true", help="regenerate status/roundtrip.json first")
        ap.add_argument("--game", default=r"C:\Users\james\i76-uncap-lab\game")
    ctx, args = make("gateR", __doc__, extra)
    rp = ctx.path("status", "roundtrip.json")
    if args.run:
        rc = subprocess.call([sys.executable, ctx.path("tools", "i76fmt", "roundtrip.py"), "--game", args.game, "--out", rp])
        ctx.note("roundtrip.py exit %d" % rc)
    if not os.path.exists(rp):
        ctx.fail("status/roundtrip.json missing (run tools/i76fmt/roundtrip.py)"); return ctx.finish()
    d = json.load(open(rp, encoding="utf-8"))
    fams = {f["family"]: f for f in d.get("families", [])}
    for name, f in fams.items():
        if f.get("diff_files", 0):
            ctx.fail("family %s: %d files differ after round trip (first: %s)" % (name, f["diff_files"], (f.get("diffs") or [{}])[0]))
        if f.get("parse_errors"):
            ctx.fail("family %s: %d parse errors (first: %s)" % (name, len(f["parse_errors"]), f["parse_errors"][0]))
    for k, v in FLOOR.items():
        got = d.get("corpus", {}).get(k)
        if got is None or got < v:
            ctx.fail("corpus %s = %s, floor %d" % (k, got, v))
    vcf = fams.get("zfs-payloads", {}).get("by_ext", {}).get(".vcf", {}).get("n", 0) + d.get("corpus", {}).get("vcf-vsf-loose", 0)
    if vcf < 300:
        ctx.fail("vcf corpus %d < 300 (293 archived + 7 loose)" % vcf)
    if "zfs-repack-stored" not in fams:
        ctx.fail("stored-mode repack family missing (the archive gate)")
    if "lzo_recompression_identity" not in d:
        ctx.fail("LZO recompression identity not recorded (measured or 'not measured')")
    rt = os.path.getmtime(rp)
    stale = [p for p in glob.glob(ctx.path("tools", "i76fmt", "*.py")) if os.path.getmtime(p) > rt]
    if stale:
        ctx.fail("report older than parsers: %s (re-run roundtrip.py)" % ", ".join(os.path.basename(p) for p in stale))
    zp = os.path.join(args.game, "I76.ZFS")
    if os.path.exists(zp):
        md5 = hashlib.md5(open(zp, "rb").read()).hexdigest()
        if fams.get("zfs-archive", {}).get("md5") != md5:
            ctx.fail("I76.ZFS md5 %s differs from the report's %s" % (md5, fams.get("zfs-archive", {}).get("md5")))
    if d.get("verdict") != "PASS":
        ctx.fail("report verdict %s" % d.get("verdict"))
    if ctx.batch and d.get("verdict") != "PASS":
        for r in ctx.batch_rows("functions") + ctx.batch_rows("globals"):
            if any("i76fmt" in json.dumps(e) for e in ctx.row_evidence(r)):
                ctx.fail("%s cites parser output while gate R is not green" % r.get("addr"))
    ctx.note("report %s: %s, %s" % (d.get("time"), d.get("verdict"), json.dumps(d.get("totals"))))
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
