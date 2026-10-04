r"""dispatch_check.py - validator for the `dispatch-case` evidence kind (PRIMARY, added 2026-09-26).

A named key selects an index, the index selects a case through a jump table, and the case calls the function the
evidence is attached to. Every link is decoded from the pristine file:
  literal   the bytes at literal_addr are the NUL-terminated literal
  matcher   inside the matcher function, `mov esi, literal_addr` is followed, before the next `mov esi, <imm>`, by
            `mov eax, index` (the unrolled compare-and-return shape of the fsm name lookup 0x410a10)
  table     dword at table + 4*index == case
  call      call_site decodes as `call <function>` and lies in [case, next jump-table target)
Called by merge.py for every row that carries the kind (any status) and by gates\gateG2_evidence.py.
"""
import struct
from capstone.x86 import X86_OP_IMM


class DispatchError(Exception):
    pass


def _u32(img, va):
    off = img.va2off(va)
    return struct.unpack("<I", img.data[off:off + 4])[0]


def check(img, md, fn_addr, e, matcher_size):
    p = lambda v: int(str(v), 16) if isinstance(v, str) else int(v)
    lit_va, idx, table, case, site, m_lo = p(e["literal_addr"]), int(e["index"]), p(e["table"]), p(e["case"]), p(e["call_site"]), p(e["matcher"])
    got = img.cstring(lit_va)
    if got is None or got.decode("latin1") != e["literal"]:
        raise DispatchError("literal at 0x%x is %r, claimed %r" % (lit_va, got, e["literal"]))
    off = img.va2off(m_lo)
    found = armed = False
    for ins in md.disasm(img.data[off:off + matcher_size], m_lo):
        if ins.mnemonic == "mov" and len(ins.operands) == 2 and ins.operands[1].type == X86_OP_IMM and ins.op_str.startswith("esi,"):
            armed = (ins.operands[1].imm & 0xffffffff) == lit_va
        elif armed and ins.mnemonic == "mov" and ins.op_str.startswith("eax, ") and len(ins.operands) == 2 and ins.operands[1].type == X86_OP_IMM:
            found = ins.operands[1].imm == idx
            break
    if not found:
        raise DispatchError("matcher 0x%x does not return index %d for literal 0x%x" % (m_lo, idx, lit_va))
    tgt = _u32(img, table + 4 * idx)
    if tgt != case:
        raise DispatchError("table 0x%x[%d] = 0x%x, claimed case 0x%x" % (table, idx, tgt, case))
    count = int(e.get("table_count") or 256)
    targets = sorted(set(_u32(img, table + 4 * k) for k in range(count)))
    nxt = min([t for t in targets if t > case] + [case + 0x400])
    if not (case <= site < nxt):
        raise DispatchError("call site 0x%x is outside case 0x%x..0x%x" % (site, case, nxt))
    off = img.va2off(site)
    ins = list(md.disasm(img.data[off:off + 16], site, count=1))
    if not ins or ins[0].mnemonic != "call" or not ins[0].operands or ins[0].operands[0].type != X86_OP_IMM \
            or (ins[0].operands[0].imm & 0xffffffff) != fn_addr:
        raise DispatchError("0x%x is not `call 0x%x`" % (site, fn_addr))
    return True
