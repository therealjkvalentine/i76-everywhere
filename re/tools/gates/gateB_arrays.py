#!/usr/bin/env python3
"""Gate B (bounded arrays; method doc 4.2). An array claim needs stride evidence (imul/lea scale in a
referencing function) and a bound from {compare immediate in the loop, HeapCreate/VirtualAlloc/pool size,
observed max index in a capture}. Rows without a bound stay `proposed` and their bytes count as remainder.
"Absorb unreferenced bytes" is not a rule.

Checks (batch or map): every global whose type contains `[` and whose status is above proposed carries
bound_evidence of the form `cmp-imm@0x<site>:<N>` | `heap-size@0x<site>:<N>` | `pool-size@0x<site>:<N>` |
`observed-max@<capture_id>:<N>` and a `stride` evidence item {site, scale} whose instruction capstone
decodes with that scale (imul imm, lea [..*s], or shl); the declared element count equals N (or N+1 for
observed-max); a cmp-imm site decodes to `cmp ..., N`.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, Reject, parse_addr, hx
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

BOUND_RE = re.compile(r"^(cmp-imm|heap-size|pool-size)@(0x[0-9a-fA-F]+):(\d+)$|^observed-max@([\w\-]+):(\d+)$")


def check_stride(ctx, site, scale):
    ins = ctx.dis.at(site, 1)
    if not ins:
        raise Reject("stride site %s does not decode" % hx(site))
    i = ins[0]
    if i.mnemonic == "imul":
        imms = [op.imm for op in i.operands if op.type == X86_OP_IMM]
        if scale in imms:
            return
    if i.mnemonic in ("lea", "mov", "add", "cmp", "movzx", "fld", "fstp"):
        for op in i.operands:
            if op.type == X86_OP_MEM and op.mem.scale == scale:
                return
    if i.mnemonic in ("shl", "sal"):
        imms = [op.imm for op in i.operands if op.type == X86_OP_IMM]
        if imms and (1 << imms[0]) == scale:
            return
    raise Reject("stride site %s (%s %s) does not show scale %d" % (hx(site), i.mnemonic, i.op_str, scale))


def main():
    ctx, args = make("gateB", __doc__)
    rows = ctx.batch_rows("globals") if ctx.batch else ctx.globals
    n = 0
    for r in rows:
        t = r.get("type", "") or ""
        if "[" not in t:
            continue
        n += 1
        try:
            m = re.search(r"\[(\d+)\]", t)
            count = int(m.group(1)) if m else None
            be = r.get("bound_evidence", "") or ""
            if r.get("status") in ("proposed", "auto", ""):
                if be:
                    ctx.note("%s %s: proposed with bound_evidence %s (may be promoted)" % (r["addr"], r["name"], be))
                continue
            mm = BOUND_RE.match(be)
            if not mm:
                raise Reject("array type %r above proposed without a recognised bound_evidence (%r)" % (t, be))
            bound = int(mm.group(3) or mm.group(5))
            kind = mm.group(1) or "observed-max"
            if count is not None and not (count == bound or (kind == "observed-max" and count == bound + 1)):
                raise Reject("declared count %d != bound %d from %s" % (count, bound, be))
            if kind == "cmp-imm":
                site = parse_addr(mm.group(2)); ins = ctx.dis.at(site, 1)
                if not ins or ins[0].mnemonic != "cmp" or bound not in [op.imm for op in ins[0].operands if op.type == X86_OP_IMM]:
                    raise Reject("cmp-imm site %s is not 'cmp ..., %d'" % (mm.group(2), bound))
            evs = ctx.row_evidence(r)
            st = [e for e in evs if e.get("kind") == "stride" or e.get("stride")]
            if not st:
                raise Reject("no stride evidence item {site, scale}")
            for e in st:
                check_stride(ctx, parse_addr(e["site"]), int(e.get("scale") or e.get("stride")))
        except Reject as ex:
            ctx.fail("global %s %s: %s" % (r.get("addr"), r.get("name"), ex))
        except Exception as ex:
            ctx.fail("global %s: %s" % (r.get("addr"), ex))
    ctx.note("checked %d array rows" % n)
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
