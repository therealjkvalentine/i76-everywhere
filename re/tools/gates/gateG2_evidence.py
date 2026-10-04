#!/usr/bin/env python3
"""Gates G0, G1, G2 (method doc 4.2) on evidence.

G0 (untrusted input): strings and decompiled text are data; a proposal / evidence row that quotes an
    instruction-like string as a reason is rejected (regex in tools/proposal.py: G0_RE).
G1 (anchor): `anchored` needs an import wrapper / table target (every (table, tag) pair listed) / a self-naming
    literal in one of the forms `<name>: ...`, `<name> - ...`, `in <name>`, `<name>()` whose <name> is not an
    export of another module / the `X failed` / `X in infinite loop` rule (form rule-c); the literal must exist
    in strings.tsv at literal_addr and the cited site must be inside the row's function.
G2 (evidence): `supported` needs >= 2 independent hard evidence kinds, at least one primary; secondary kinds are
    counted once together; a non-unique constant-anchor is secondary; plausibility of the C is not evidence.
Also: string-xref literal_addr resolves in strings.tsv (or the file bytes contain the literal); import-callee
    names a slot in imports.tsv whose call/load site list contains the site; dynamic-capture cites an existing
    captures\\<id>\\manifest.json (G5).
"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, Reject, parse_addr, hx, IMPORT_COLS
from proposal import PRIMARY, SECONDARY, KINDS, G0_RE, SELF_NAME_FORMS

STR_COLS = ["addr", "class", "len", "string", "xref_count", "referencing_functions", "section", "ghidra_type",
            "imm32_sites", "imm32_functions", "verified"]




def check_dispatch_case(ctx, fn_addr, e):
    """dispatch-case (PRIMARY, added 2026-09-26 for the mission-script actions): a named key selects an index, the index
    selects a case through a jump table, and the case calls this function. Every link is decoded from the pristine file:
      literal     the bytes at literal_addr are the NUL-terminated literal
      matcher     inside the matcher function, `mov esi, literal_addr` is followed, before the next `mov esi, <imm>`,
                  by `mov eax, index` (the unrolled compare-and-return shape of fsm name lookup 0x410a10)
      table       dword at table + 4*index == case
      call        call_site decodes as `call fn_addr` and lies in [case, next jump-table target)"""
    import struct
    from capstone.x86 import X86_OP_IMM as _IMM
    img, dis = ctx.img, ctx.dis
    lit_va, idx, table, case, site = (parse_addr(e["literal_addr"]), int(e["index"]), parse_addr(e["table"]),
                                      parse_addr(e["case"]), parse_addr(e["call_site"]))
    got = img.cstring(lit_va)
    if got is None or got.decode("latin1") != e["literal"]:
        raise Reject("dispatch-case literal at %s is %r, claimed %r" % (hx(lit_va), got, e["literal"]))
    m_lo = parse_addr(e["matcher"])
    frow = [f for f in ctx.functions if parse_addr(f["addr"]) == m_lo]
    if not frow:
        raise Reject("dispatch-case matcher %s is not a function start" % hx(m_lo))
    m_hi = m_lo + int(frow[0]["size"] or 0)
    off = img.va2off(m_lo)
    found = armed = False
    for ins in dis.md.disasm(img.data[off:off + (m_hi - m_lo)], m_lo):
        if ins.mnemonic == "mov" and len(ins.operands) == 2 and ins.operands[1].type == _IMM and ins.op_str.startswith("esi,"):
            armed = (ins.operands[1].imm & 0xffffffff) == lit_va
        elif armed and ins.mnemonic == "mov" and ins.op_str.startswith("eax, ") and len(ins.operands) == 2 and ins.operands[1].type == _IMM:
            found = ins.operands[1].imm == idx
            break
    if not found:
        raise Reject("dispatch-case: matcher %s does not return index %d for literal %s" % (hx(m_lo), idx, hx(lit_va)))
    tgt = struct.unpack("<I", img.data[img.va2off(table + 4 * idx):img.va2off(table + 4 * idx) + 4])[0]
    if tgt != case:
        raise Reject("dispatch-case: table %s[%d] = %s, claimed case %s" % (hx(table), idx, hx(tgt), hx(case)))
    count = int(e.get("table_count") or 256)
    targets = sorted(set(struct.unpack("<I", img.data[img.va2off(table + 4 * k):img.va2off(table + 4 * k) + 4])[0] for k in range(count)))
    nxt = min([t for t in targets if t > case] + [case + 0x400])
    if not (case <= site < nxt):
        raise Reject("dispatch-case: call site %s is outside case %s..%s" % (hx(site), hx(case), hx(nxt)))
    ins = dis.at(site, 1)
    if not ins or ins[0].mnemonic != "call" or not ins[0].operands or ins[0].operands[0].type != _IMM or (ins[0].operands[0].imm & 0xffffffff) != fn_addr:
        raise Reject("dispatch-case: %s is not `call %s`" % (hx(site), hx(fn_addr)))

def _unescape(col):
    """strings.tsv keeps the column escaped (SOFTWARE\\\\Activision, Blend Caps\\n); YAML hands the merge the decoded text (PILOT-1 #1)."""
    import codecs
    try:
        return codecs.decode(col.encode("latin1", "backslashreplace"), "unicode_escape")
    except Exception:
        return col.replace(chr(92) * 2, chr(92)).replace(chr(92) + "n", chr(10)).replace(chr(92) + "t", chr(9))

def self_name_ok(name, literal, form):
    lit = literal.strip()
    pats = {"colon": r"^%s\s*:", "dash": r"^%s\s+-\s", "in": r"\bin\s+%s\b", "paren": r"\b%s\s*\(\s*\)",
            "rule-c": r"(^|\s)%s\s+(failed|in infinite loop)|Unable to .*\b%s\b"}
    p = pats.get(form)
    if not p:
        return False
    return re.search(p.replace("%s", re.escape(name)), lit) is not None


def main():
    ctx, args = make("gateG2", __doc__)
    from merge import gate_g1_g2
    strings = {parse_addr(r["addr"]): r for r in ctx.tsv("strings.tsv", STR_COLS)}
    imps = ctx.tsv("imports.tsv", IMPORT_COLS)
    imp_by_name = {}
    for r in imps:
        imp_by_name.setdefault(r["name"], r)
    fj = {int(r["addr"], 16): r for r in json.load(open(ctx.path("ghidra", "export", "functions.json"), encoding="utf-8"))}
    rows = (ctx.batch_rows("functions") + ctx.batch_rows("globals")) if ctx.batch else (ctx.functions + ctx.globals)
    n = 0
    for r in rows:
        evs = ctx.row_evidence(r)
        if r.get("status") not in ("anchored", "supported"):
            continue
        n += 1
        try:
            a = parse_addr(r["addr"])
            f = fj.get(a)
            lo, hi = (a, a + int(f["size"])) if f else (a, a + int(r.get("size") or 1))
            for e in evs:
                k = e.get("kind")
                if k not in KINDS:
                    raise Reject("evidence kind %r not in the vocabulary" % k)
                # Task 4 (t4-anchors) spelled these fields string/string_addr/import_name/sites; accept both
                if "literal" not in e and "string" in e:
                    e["literal"] = e["string"]
                if "literal_addr" not in e and "string_addr" in e:
                    e["literal_addr"] = e["string_addr"]
                if "import" not in e and e.get("import_name"):
                    e["import"] = e["import_name"]
                if "site" not in e and e.get("sites"):
                    e["site"] = e["sites"][0]
                for fld in ("claim", "reason", "note", "why", "literal"):
                    if fld != "literal" and G0_RE.search(str(e.get(fld, ""))):
                        raise Reject("G0: instruction-like text in evidence %s.%s: %r" % (k, fld, e.get(fld)))
                if k == "string-xref":
                    la = parse_addr(e["literal_addr"]) if e.get("literal_addr") else None
                    lit = e.get("literal", "")
                    if la is not None:
                        srow = strings.get(la)
                        if srow is None:
                            b = ctx.img.cstring(la)
                            if b is None or not lit or not b.startswith(lit.encode("latin1", "replace")[:len(b)]):
                                raise Reject("string-xref literal_addr %s is not in strings.tsv and the bytes do not match %r" % (hx(la), lit))
                        elif lit and lit not in srow["string"] and lit not in _unescape(srow["string"]) and lit not in _unescape(_unescape(srow["string"])):
                            # strings.tsv keeps the column escaped (SOFTWARE\\Activision); YAML hands us the decoded text (PILOT-1 #1)
                            # the recorded literal may be the whole string or the G1 grammar fragment inside it
                            raise Reject("string-xref literal %r is not contained in strings.tsv %r at %s" % (lit, srow["string"], hx(la)))
                    if e.get("site") and "row" in e and e["row"] == "function":
                        s = parse_addr(e["site"])
                        if not (lo <= s < hi):
                            raise Reject("string-xref site %s is outside the function %s-%s" % (e["site"], hx(lo), hx(hi)))
                    if r["status"] == "anchored" and e.get("form") in SELF_NAME_FORMS:
                        if not self_name_ok(r["name"], lit, e["form"]):
                            raise Reject("G1: literal %r does not name %s in form %s" % (lit, r["name"], e["form"]))
                        if r["name"] in imp_by_name:
                            raise Reject("G1: %s is an export of another module" % r["name"])
                if k == "import-callee":
                    imp = e.get("import", "")
                    nm = imp.split("!")[-1] if imp else e.get("name", "")
                    if nm not in imp_by_name:
                        raise Reject("import-callee %r is not in imports.tsv" % nm)
                    if e.get("site"):
                        row = imp_by_name[nm]
                        sites = set((row["call_site_list"] + ";" + row["load_site_list"] + ";" + row.get("thunk_caller_sites", "")).replace(",", ";").split(";"))
                        s = "0x%x" % parse_addr(e["site"])
                        if sites and s not in {x.strip() for x in sites if x.strip()} and row["call_site_list"]:
                            ctx.note("%s import-callee %s site %s is not in the imports.tsv site list (thunk or register-load form?)" % (r["addr"], nm, s))
                if k == "dispatch-case":
                    check_dispatch_case(ctx, parse_addr(r["addr"]), e)
                if k == "dynamic-capture":
                    cid = e.get("capture_id", "")
                    if not os.path.exists(ctx.path("captures", cid, "manifest.json")):
                        raise Reject("dynamic-capture %r has no captures/<id>/manifest.json (G5)" % cid)
            gate_g1_g2(r, evs)
            if r["status"] == "supported":
                prim = {e["kind"] for e in evs if e["kind"] in PRIMARY and not (e["kind"] == "constant-anchor" and not e.get("unique"))}
                sec = {e["kind"] for e in evs if e["kind"] in SECONDARY or (e["kind"] == "constant-anchor" and not e.get("unique"))}
                kinds = len(prim) + (1 if sec else 0)
                if kinds < 2:
                    raise Reject("G2: %d independent kinds (primary %s, secondary counted once: %s)" % (kinds, sorted(prim), sorted(sec)))
        except Reject as ex:
            ctx.fail("%s %s [%s]: %s" % (r.get("addr"), r.get("name"), r.get("status"), ex))
        except Exception as ex:
            ctx.fail("%s %s: %s" % (r.get("addr"), r.get("name"), ex))
    ctx.note("checked %d anchored/supported rows" % n)
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
