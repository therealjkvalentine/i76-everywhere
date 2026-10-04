#!/usr/bin/env python3
"""Gate A (address space; method doc 4.1). Every address carries a class tag and passes the class test.

Checks (batch rows, or the whole map without --batch):
  functions: addr in .text; a row with no Ghidra function needs size + `create` evidence with a method.
  globals:   class init -> file bytes exist at the section-delta offset; bss -> a capstone-verified ref-site
             (a .text instruction whose disp32/imm32 decodes to the address); iat -> slot in the import descriptor.
  evidence:  every `site` field is in .text; every `literal_addr` is init.
Negative test set (run every time): 0x4c1a8c is not a table base in tables.tsv (the FSM prototype table is
0x4c2e8c); 0x4f26f0 is not the gamekey table (0x4f3af0 is); 0x4edd58 renderer names count 18 not 19; 0x5a7e1c
passes as bss and fails as init; 0x4bc100 passes as iat; 0x608bb8 is accepted only as a slot of an enclosing table.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, parse_addr, hx, Reject, TABLE_COLS


def main():
    ctx, args = make("gateA", __doc__)
    img = ctx.img
    from merge import gate_a_function, gate_a_global
    fj = {int(r["addr"], 16) for r in json.load(open(ctx.path("ghidra", "export", "functions.json"), encoding="utf-8"))}

    # --- negative test set ---------------------------------------------------------------------------------
    tables = ctx.tsv("tables.tsv", TABLE_COLS)

    def base_of(t):
        b = t.get("base") or ""
        return parse_addr(b) if b.startswith("0x") else None  # 'stack:0x4022e0:esp+20' rows carry an explicit non-VA tag

    bases = {base_of(t) for t in tables} - {None}
    for t in tables:
        t["base"] = "0x%x" % base_of(t) if base_of(t) is not None else ""
    if 0x4c1a8c in bases:
        ctx.fail("negative set: 0x4c1a8c (a file offset) appears as a table base")
    if 0x4c2e8c not in bases:
        ctx.fail("negative set: the FSM prototype table 0x4c2e8c is missing from tables.tsv")
    if 0x4f3af0 not in bases:
        ctx.fail("negative set: the gamekey table 0x4f3af0 is missing from tables.tsv")
    for t in tables:
        if t.get("base") and parse_addr(t["base"]) == 0x4f26f0 and "gamekey" in (t.get("name") or "").lower():
            ctx.fail("negative set: 0x4f26f0 named as the gamekey table")
        if t.get("base") and parse_addr(t["base"]) == 0x4edd58 and t.get("count") not in ("", "18"):
            ctx.fail("negative set: renderer name table 0x4edd58 count %s, expected 18" % t.get("count"))
    if img.klass(0x5a7e1c) != "bss":
        ctx.fail("negative set: 0x5a7e1c must be bss, got %s" % img.klass(0x5a7e1c))
    if img.klass(0x4bc100) != "iat":
        ctx.fail("negative set: 0x4bc100 must be iat, got %s" % img.klass(0x4bc100))
    # --- FOLDIN-REPORT section 3 additions (p5-foldin-merge) ---------------------------------------------------
    import struct as _st
    f32 = lambda va: _st.unpack("<f", img.bytes_at(va, 4))[0]
    # +0xc00 slips: the prior docs quoted 0x4bc71c = 0.05 and 0x4bc59c = 9.8; those values sit exactly 0xc00 higher
    if not (abs(f32(0x4bd31c) - 0.05) < 1e-6 and abs(f32(0x4bd19c) - 9.8) < 1e-5):
        ctx.fail("negative set: 0x4bd31c/0x4bd19c must hold 0.05f/9.8f, got %r/%r" % (f32(0x4bd31c), f32(0x4bd19c)))
    if abs(f32(0x4bc71c) - 0.05) < 1e-6 or abs(f32(0x4bc59c) - 9.8) < 1e-5:
        ctx.fail("negative set: 0x4bc71c/0x4bc59c must NOT hold 0.05f/9.8f (file-offset-as-VA slip of 0xc00)")
    # mid-function label and operand-address 'functions': not Ghidra function starts; 0x4b6860 not an instruction boundary
    for va, why in ((0x43b090, "mid-function label in 0x43a5d0"), (0x4b6860, "operand address inside 0x4b6850"), (0x40a280, "operand address inside 0x40a270")):
        if va in fj:
            ctx.fail("negative set: %s is a Ghidra function start but is a %s" % (hx(va), why))
    for name, row in (("functions.tsv", ctx.functions),):
        for r in row:
            if parse_addr(r["addr"]) in (0x43b090, 0x4b6860, 0x40a280):
                ctx.fail("negative set: %s carries a row for %s (%s)" % (name, r["addr"], r["name"]))

    def insn_boundaries(fn, size):
        off = img.va2off(fn)
        return {i.address for i in ctx.dis.md.disasm(img.data[off:off + size], fn)}
    if 0x4b6860 in insn_boundaries(0x4b6850, 0x40):
        ctx.fail("negative set: 0x4b6860 decodes as an instruction boundary of 0x4b6850 (expected mid-instruction)")
    if 0x40a280 not in insn_boundaries(0x40a270, 0x40):
        ctx.fail("negative set: 0x40a280 should be an instruction boundary inside 0x40a270 (mov eax,[esp+0x1c])")
    # bss quoted without a static base, and the wrong input-table base: no .text operand decodes to them
    for va in (0x501858, 0x501918, 0x4f2840):
        for g in ctx.globals:
            if parse_addr(g["addr"]) == va:
                ctx.fail("negative set: %s carries a globals.tsv row (%s); it has no static base / is the wrong table base" % (hx(va), g["name"]))
    if img.u32(0x4f2840) != 0 or img.u32(0x4f2844) != 0:
        ctx.fail("negative set: 0x4f2840/0x4f2844 must be zero (the input-action table base is 0x4f2860)")
    if 0x4f2860 not in bases:
        ctx.fail("negative set: the input-action table base 0x4f2860 is missing from tables.tsv")
    for g in ctx.globals:
        if parse_addr(g["addr"]) == 0x608bb8 and g["status"] not in ("auto", "proposed"):
            ev = ctx.row_evidence(g)
            if not any(e.get("kind") in ("table-entry", "ref-site") for e in ev):
                ctx.fail("negative set: 0x608bb8 accepted without table-entry/ref-site evidence")
        if parse_addr(g["addr"]) == 0x5a7e1c and g["class"] != "bss":
            ctx.fail("negative set: 0x5a7e1c carries class %s" % g["class"])

    # --- rows --------------------------------------------------------------------------------------------------
    frows = ctx.batch_rows("functions") if ctx.batch else ctx.functions
    grows = ctx.batch_rows("globals") if ctx.batch else ctx.globals
    for r in frows:
        try:
            evs = ctx.row_evidence(r)
            gate_a_function(img, r, fj, evs)
            for e in evs:
                for k in ("site",):
                    if e.get(k) and not img.in_text(parse_addr(e[k])):
                        raise Reject("evidence %s site %s is not in .text" % (e.get("kind"), e[k]))
                if e.get("literal_addr") and img.klass(parse_addr(e["literal_addr"])) not in ("init", "text"):
                    raise Reject("literal_addr %s is class %s" % (e["literal_addr"], img.klass(parse_addr(e["literal_addr"]))))
        except Reject as ex:
            ctx.fail("function %s %s: %s" % (r.get("addr"), r.get("name"), ex))
        except Exception as ex:
            ctx.fail("function %s: %s" % (r.get("addr"), ex))
    for r in grows:
        try:
            evs = ctx.row_evidence(r)
            if r["class"] not in ("init", "bss", "iat"):
                raise Reject("class %r is not init|bss|iat" % r["class"])
            gate_a_global(img, ctx.dis, r, evs)
        except Reject as ex:
            ctx.fail("global %s %s: %s" % (r.get("addr"), r.get("name"), ex))
        except Exception as ex:
            ctx.fail("global %s: %s" % (r.get("addr"), ex))
    ctx.note("checked %d function rows, %d global rows, negative set of 6 + 7 FOLDIN additions "
             "(0x4bc71c/0x4bd31c, 0x4bc59c/0x4bd19c, 0x43b090, 0x4b6860, 0x40a280, 0x501858/0x501918, 0x4f2840)" % (len(frows), len(grows)))
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
