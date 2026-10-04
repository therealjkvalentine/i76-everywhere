#!/usr/bin/env python3
"""Gate T (types and enums; method doc 4.2). Every struct field width and enum bit cites the instruction that
tests or stores it.

Checks:
  globals (batch or map): a non-empty width needs width-from evidence whose capstone memory operand at the
      cited site has exactly that width (IAT slots are 4 by definition).
  batch function evidence: every `field` claim evidence of kind width-from / bit-tested-at decodes at the site
      (width-from: an operand of that size; bit-tested-at: a test/and/or/bt/cmp instruction with an immediate
      whose bit set contains the claimed bit).
  types\\i76.h: every struct member line carries `width-from` or `bit-tested-at` in its comment, or is
      `undefined` with the source noted; every enum member line carries `bit-tested-at`; the BWD2 descriptor
      enum, when present, must not contain bit 0x4 (no citation exists).
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, parse_addr, hx, Reject
from capstone.x86 import X86_OP_IMM, X86_OP_REG


def check_bit_tested(ctx, site, bit, cmp_value=None):
    ins = ctx.dis.at(site, 1)
    if not ins:
        raise Reject("bit-tested-at %s does not decode" % hx(site))
    i = ins[0]
    if i.mnemonic not in ("test", "and", "or", "xor", "bt", "bts", "btr", "cmp"):
        raise Reject("bit-tested-at %s is %s, not a bit test" % (hx(site), i.mnemonic))
    imms = [op.imm for op in i.operands if op.type == X86_OP_IMM]
    if not imms:
        raise Reject("bit-tested-at %s has no immediate" % hx(site))
    imm = imms[0]
    # a high byte register (ah/bh/ch/dh) addresses bits 8-15 of the dword: test bh,1 is bit 0x100 (PILOT-1 re-merge)
    regs = [i.reg_name(op.reg) for op in i.operands if op.type == X86_OP_REG]
    if any(r in ("ah", "bh", "ch", "dh") for r in regs):
        imm = imm << 8
    if i.mnemonic.startswith("bt"):
        if bit != (1 << imms[0]):
            raise Reject("bt at %s tests bit %d, claim 0x%x" % (hx(site), imms[0], bit))
    elif i.mnemonic == "cmp" and cmp_value is not None:
        if (imms[0] & 0xffffffff) != (cmp_value & 0xffffffff):
            raise Reject("cmp at %s compares against 0x%x, claim value 0x%x" % (hx(site), imms[0] & 0xffffffff, cmp_value))
    elif not (imm & bit):
        raise Reject("immediate 0x%x at %s does not contain bit 0x%x" % (imm, hx(site), bit))


def main():
    ctx, args = make("gateT", __doc__)
    from merge import gate_t
    grows = ctx.batch_rows("globals") if ctx.batch else ctx.globals
    for r in grows:
        try:
            gate_t(ctx.dis, r, ctx.row_evidence(r))
        except Reject as ex:
            ctx.fail("global %s %s: %s" % (r.get("addr"), r.get("name"), ex))
        except Exception as ex:
            ctx.fail("global %s: %s" % (r.get("addr"), ex))
    for r in ctx.batch_rows("functions"):
        for e in ctx.row_evidence(r):
            try:
                if e.get("kind") == "width-from":
                    site = parse_addr(e["site"]); ins = ctx.dis.at(site, 1)
                    if not ins:
                        raise Reject("width-from %s does not decode" % e["site"])
                    sizes = [op.size for op in ins[0].operands]
                    if int(e.get("width", 0)) not in sizes:
                        raise Reject("width-from %s: operand sizes %s, claim %s (%s %s)" % (e["site"], sizes, e.get("width"), ins[0].mnemonic, ins[0].op_str))
                    e["insn"] = "%s %s" % (ins[0].mnemonic, ins[0].op_str)
                if e.get("kind") == "bit-tested-at":
                    b = e.get("bit")
                    v = e.get("value")
                    if b is None and v is None:
                        raise Reject("bit-tested-at %s carries neither bit nor value" % e.get("site"))
                    if b is None:
                        # a compare immediate (cmp al, 0xa): the claim is the value compared, not a bit
                        v = int(v, 16) if isinstance(v, str) else int(v)
                        check_bit_tested(ctx, parse_addr(e["site"]), v, cmp_value=v)
                    else:
                        b = int(b, 16) if isinstance(b, str) else int(b)
                        check_bit_tested(ctx, parse_addr(e["site"]), b)
            except Reject as ex:
                ctx.fail("function %s %s: %s" % (r.get("addr"), r.get("name"), ex))
            except Exception as ex:
                ctx.fail("function %s: %s" % (r.get("addr"), ex))
    # header
    hp = ctx.path("types", "i76.h")
    if os.path.exists(hp):
        in_struct = in_enum = in_comment = False; n = 0
        for ln, line in enumerate(open(hp, encoding="utf-8"), 1):
            s = line.strip()
            # a citation often runs over several lines; a continuation inside /* ... */ is never a member
            if in_comment:
                if "*/" in s:
                    in_comment = False
                continue
            opens_comment = s.count("/*") > s.count("*/")
            if re.match(r"^(typedef\s+)?struct\b.*\{", s):
                in_struct = True; continue
            if re.match(r"^(typedef\s+)?enum\b.*\{", s):
                in_enum = True; continue
            if s.startswith("}"):
                in_struct = in_enum = False; continue
            if in_struct and s and not s.startswith("/*") and not s.startswith("//") and ";" in s:
                n += 1
                if "width-from" not in s and "bit-tested-at" not in s and "undefined" not in s:
                    ctx.fail("i76.h:%d struct member without width-from / bit-tested-at citation: %s" % (ln, s))
            if in_enum and s and not s.startswith("/*") and not s.startswith("//") and "=" in s:
                n += 1
                if "bit-tested-at" not in s:
                    ctx.fail("i76.h:%d enum member without bit-tested-at citation: %s" % (ln, s))
                if re.search(r"=\s*0x0*4\b", s) and "BWD2" in open(hp, encoding="utf-8").read():
                    ctx.fail("i76.h:%d BWD2 descriptor bit 0x4 has no citation and is not an enum member" % ln)
            if opens_comment:
                in_comment = True
        ctx.note("i76.h: %d struct/enum member lines checked" % n)
    ctx.note("checked %d global rows" % len(grows))
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
