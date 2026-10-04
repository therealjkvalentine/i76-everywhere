#!/usr/bin/env python3
"""Gate L (library and synthetic; method doc 4.2). `library` needs a per-function evidence row (asm-shape match
against source with the source cited, FID match, or emulated-io identity); `synthetic` needs synthetic-shape;
ranges are never marked library.

Checks: every library/synthetic row (batch or map) carries the required kind; asm-shape carries `source`;
emulated-io used for library carries `oracle` (the reference implementation) or `capture_id`; regions.tsv
has no range row of kind library/synthetic (rows there are function-level only); synthetic rows are one of
the recognised shapes (Unwind@ funclet 11 B, EH stub `mov eax,FuncInfo; jmp __CxxFrameHandler`, thunk,
_ftol-style) by size/name heuristic, else a note.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, Reject, REGION_COLS


def main():
    ctx, args = make("gateL", __doc__)
    from merge import gate_l
    rows = ctx.batch_rows("functions") if ctx.batch else ctx.functions
    n = 0
    for r in rows:
        if r.get("status") not in ("library", "synthetic"):
            continue
        n += 1
        evs = ctx.row_evidence(r)
        try:
            gate_l(r, evs)
            for e in evs:
                if e.get("kind") == "emulated-io" and r["status"] == "library" and not (e.get("oracle") or e.get("capture_id")):
                    raise Reject("emulated-io for library needs oracle (reference implementation) or capture_id")
                if e.get("kind") == "fid" and not (e.get("source") or e.get("library")):
                    raise Reject("fid evidence needs the FID library name in source/library")
        except Reject as ex:
            ctx.fail("%s %s [%s]: %s" % (r.get("addr"), r.get("name"), r.get("status"), ex))
        if r["status"] == "synthetic":
            nm = r.get("name", "")
            ok = nm.startswith("Unwind@") or nm.startswith("eh_stub_") or "thunk" in nm.lower() or nm.startswith("_ftol") or nm.startswith("__")
            if not ok:
                ctx.note("synthetic row %s %s is not a recognised shape name (funclet/EH stub/thunk/_ftol)" % (r["addr"], nm))
    for reg in ctx.tsv("regions.tsv", REGION_COLS):
        if reg.get("kind") in ("library", "synthetic"):
            ctx.fail("regions.tsv %s-%s marked %s: ranges are never library/synthetic" % (reg["start"], reg["end"], reg["kind"]))
    ctx.note("checked %d library/synthetic rows" % n)
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
