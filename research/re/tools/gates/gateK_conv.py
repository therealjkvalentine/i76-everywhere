#!/usr/bin/env python3
"""Gate K (conventions; method doc 4.2). Every calling convention from Decompiler Parameter ID is `auto`; a
convention claim needs call-site cleanup evidence (`add esp,N` after the call, or `ret N` in the callee).

Checks (batch or map): rows whose conv_evidence is not `auto:*` carry call-cleanup evidence that capstone
confirms (call <this row>; next instruction == the claimed cleanup; add esp -> __cdecl); a `ret-imm@site:ret N`
form is checked by decoding `ret N` inside the function (-> __stdcall/__thiscall); N is consistent with the
argument count when a prototype with a fixed count is in types\\i76.h (4 bytes per stack argument).
Known correction asserted: 0x4b9fc0 is __cdecl with 5 stack args (add esp,0x14 at 0x4b9d3b).
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, Reject, parse_addr, hx


def main():
    ctx, args = make("gateK", __doc__)
    from merge import gate_k
    rows = ctx.batch_rows("functions") if ctx.batch else ctx.functions
    n = 0
    protos = {}
    hp = ctx.path("types", "i76.h")
    if os.path.exists(hp):
        for line in open(hp, encoding="utf-8"):
            m = re.match(r"^\s*[\w\s\*]+?\b(__cdecl|__stdcall|__thiscall|__fastcall)\s+(\w+)\s*\((.*)\)\s*;", line)
            if m:
                argl = m.group(3).strip()
                cnt = 0 if argl in ("", "void") else len([a for a in argl.split(",") if a.strip()])
                protos[m.group(2)] = (m.group(1), cnt)
    for r in rows:
        ce = r.get("conv_evidence") or "auto:paramid"
        if ce.startswith("auto:"):
            continue
        n += 1
        evs = ctx.row_evidence(r)
        try:
            m = re.match(r"^ret-imm@(0x[0-9a-fA-F]+):ret (0x[0-9a-fA-F]+)$", ce)
            if m:
                site = parse_addr(m.group(1)); ins = ctx.dis.at(site, 1)
                if not ins or ins[0].mnemonic != "ret" or ins[0].op_str.lower() != m.group(2).lower():
                    raise Reject("ret-imm site %s is not 'ret %s'" % (m.group(1), m.group(2)))
                if r.get("conv") not in ("__stdcall", "__thiscall", "__fastcall"):
                    raise Reject("ret N implies callee cleanup (__stdcall/__thiscall/__fastcall), row says %s" % r.get("conv"))
            else:
                gate_k(ctx.dis, r, evs)
            p = protos.get(r.get("name"))
            if p:
                conv, cnt = p
                if conv != r.get("conv"):
                    raise Reject("i76.h prototype says %s, row says %s" % (conv, r.get("conv")))
                for e in evs:
                    if e.get("kind") == "call-cleanup":
                        mm = re.match(r"add esp,\s*(0x[0-9a-fA-F]+|\d+)", e.get("cleanup", ""))
                        if mm:
                            nb = int(mm.group(1), 0)
                            if nb != 4 * cnt:
                                raise Reject("add esp,%d cleans %d args, prototype has %d" % (nb, nb // 4, cnt))
        except Reject as ex:
            ctx.fail("%s %s: %s" % (r.get("addr"), r.get("name"), ex))
        except Exception as ex:
            ctx.fail("%s %s: %s" % (r.get("addr"), r.get("name"), ex))
    if not ctx.batch:
        row = next((r for r in ctx.functions if parse_addr(r["addr"]) == 0x4b9fc0), None)
        if row is None or row.get("conv") != "__cdecl" or not (row.get("conv_evidence") or "").startswith("call-cleanup@0x4b9d3b"):
            ctx.fail("known correction: 0x4b9fc0 must be __cdecl with call-cleanup@0x4b9d3b (row: %s)" % (row and (row["conv"], row["conv_evidence"])))
    ctx.note("checked %d convention claims (%d prototypes in i76.h)" % (n, len(protos)))
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
