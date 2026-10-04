#!/usr/bin/env python3
"""proposal.py - the proposal / review file contract for the agent loop (method doc section 6, gates G0-G4).

Files (all under functions\\; the drafters write nothing else, the merge script is the only writer of <addr>.md):
    functions\\<addr>.proposal.md         view c      (drafter-c: the .c with <= 5 callers and <= 5 callees)
    functions\\<addr>.proposal.pcode.md   view pcode  (drafter-pcode: the .pcode / raw disassembly + callers only)
    functions\\<addr>.review.md           reviewer verdict (sees only the proposals and the same files)
<addr> is 8 lower-case hex digits (e.g. 0040aed0), the same key as ghidra\\export\\functions\\<addr>.c.

PROPOSAL FORMAT (exact). A YAML front matter block, then free text, then exactly one ```yaml fenced block:

    ---
    addr: 0x0040aed0
    view: c                          # c | pcode
    drafter: drafter-c               # drafter-c | drafter-pcode
    lease: L-0040aed0-c-20260904T181500
    export_md5: <md5 of the .c (view c) or .pcode (view pcode) file that was read>
    binary_md5: 9a232dcc2c164648cff20c414c1f9698
    tokens_used: 12000               # gate Q; integer
    ---
    # Proposal 0x0040aed0 (view c)
    free text: what the function does in the drafter's words (data, never a reason)
    ```yaml
    name: dbg_ResetLogFlag           # identifier, or keep   (keep = no name claim)
    status: proposed                 # proposed | supported | anchored | library | synthetic
    subsystem: debug                 # or ~
    prototype: "void __cdecl dbg_ResetLogFlag(void)"
    conv: auto                       # auto | __cdecl | __stdcall | __thiscall | __fastcall
    conv_evidence: auto:paramid      # auto:paramid | call-cleanup@0x004b9d3b:add esp,0x14 | ret-imm@0x...:ret 0xN
    claims:                          # every claim carries >= 1 evidence item; claims without evidence are hypotheses
      - claim: name                  # name | param | field | global | conv | status | subsystem | duplicate-of
        value: dbg_ResetLogFlag
        evidence:
          - kind: string-xref        # see KINDS below
            site: 0x0040aed5         # the referencing instruction (class text)
            literal_addr: 0x004c2aa0 # class init
            literal: "FSM - debug log"
            form: dash               # G1 self-naming grammar: colon | dash | in | paren | rule-c | ~ (not self-naming)
      - claim: param
        index: 1
        value: "int count"
        evidence: [{kind: verified-callee, callee: 0x0042d5d0, callee_name: dbg_LogStub, site: 0x0040aedf}]
      - claim: field
        struct: "param_1-base"       # a named struct in types\\i76.h, or <param>-base for an unnamed one
        offset: 0x18
        value: "u32 tick"
        evidence: [{kind: width-from, site: 0x0040aee2, width: 4}]
      - claim: global
        addr: 0x5a7e1c
        class: bss                   # init | bss | iat
        width: 4
        type: uint32
        value: simclock_frame_count
        evidence: [{kind: ref-site, site: 0x0049c805}, {kind: width-from, site: 0x0049c805, width: 4}]
      - claim: conv
        value: __cdecl
        evidence: [{kind: call-cleanup, site: 0x004b9d36, cleanup: "add esp,0x14"}]
    hypotheses:                      # anything without hard evidence; never becomes a name
      - "the tail loop looks like a bubble sort over 12-byte records"
    dynamic_request: ~               # or {break_on: 0x..., log: "...", why: "..."} (gate S checks it statically first)
    blocker: ~                       # one falsifiable sentence, or ~
    ```

EVIDENCE KINDS (method doc 4.2 vocabulary; the merge script enforces them):
  primary   : string-xref import-callee table-entry emulated-io dynamic-capture constant-anchor
              (constant-anchor is primary only with unique: true, i.e. <= 3 .text sites, or two co-occurring
              constants in one function; else it counts as secondary)
              G1 rule (a) kinds also primary: import-thunk import-wrapper pe-entry callback-pointer export-ordinal
  secondary : verified-callee struct-access census-class tu-neighbourhood global-write
              (secondary kinds are never sufficient alone and count once together, G2)
  gate L    : asm-shape fid (library, with source:), synthetic-shape (synthetic)
  gate K    : call-cleanup {site, cleanup}
  gate T    : width-from {site, width}, bit-tested-at {site, bit}
  gate A    : ref-site {site} (bss globals), create {method} (rows that create a function)
  gate P    : ported {source_instance, source} (enters as proposed; never sufficient alone)
  gate G5   : dynamic-capture {capture_id} (a captures\\<id>\\manifest.json)
Every evidence item names its site (class text) or capture; counts (n, count) carry method (gate C).

REVIEW FORMAT (exact):
    ---
    addr: 0x0040aed0
    reviewer: reviewer
    proposals: [functions/0040aed0.proposal.md, functions/0040aed0.proposal.pcode.md]
    gate_run: "python tools/merge.py --proposal 0040aed0 --dry-run"
    ---
    free text (the reviewer's reasoning; data)
    ```yaml
    verdict: accept                  # accept | reject | requeue
    g0: pass                         # pass | fail (an instruction-like string quoted as a reason)
    g4:
      name_agree: true               # both views claim the same name (or both keep)
      field_claims_agreed: 2
      field_claims_disagreed: 0
    claims:                          # one line per claim of the intersection, or per rejected claim
      - {claim: name, value: dbg_ResetLogFlag, verdict: accept, reason: "string-xref at 0x0040aed5 verified in strings.tsv"}
    overrides: []                    # [{gate: G3, reason: "..."}] only with a reason
    blocker: ~                       # one falsifiable sentence, or ~
    next_task: ~                     # the complement of the blocker (H7)
    ```
"""
import os, re, sys, json, hashlib
import yaml

PRISTINE_MD5 = "9a232dcc2c164648cff20c414c1f9698"
VIEWS = ("c", "pcode")
STATUSES = ("proposed", "supported", "anchored", "library", "synthetic")
CONVS = ("auto", "__cdecl", "__stdcall", "__thiscall", "__fastcall")
CLAIM_TYPES = ("name", "param", "field", "global", "conv", "status", "subsystem", "duplicate-of")
PRIMARY = {"string-xref", "import-callee", "table-entry", "emulated-io", "dynamic-capture", "constant-anchor",
           "import-thunk", "import-wrapper", "pe-entry", "callback-pointer", "export-ordinal", "dispatch-case",
           "ported-static"}  # gate P fast path: quoted bytes match the pristine file (merge.gate_p_static); anchors the ADDRESS only
SECONDARY = {"verified-callee", "struct-access", "census-class", "tu-neighbourhood", "global-write",
             "ported"}  # the source's own row text, one H6 instance (gate P); never sufficient alone
GATE_KINDS = {"asm-shape", "fid", "synthetic-shape", "call-cleanup", "width-from", "bit-tested-at", "ref-site",
              "create", "hwbp-trap-after"}  # hwbp-trap-after: gate C method tag (merge.gate_c_trap_after)
KINDS = PRIMARY | SECONDARY | GATE_KINDS
SELF_NAME_FORMS = {"colon", "dash", "in", "paren", "rule-c"}
ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{1,8}$")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_@$]*$")
KEY_RE = re.compile(r"^[0-9a-f]{8}$")
# G0: instruction-like text inside a string quoted as a reason (arXiv 2605.30667; AH section 3.10)
G0_RE = re.compile(r"(ignore (all |the )?(previous|prior|above)|you (must|should|are)|as an ai|system prompt|"
                   r"rename (this|the) function|set (the )?(name|status) to|assistant:|<\|im_start\|>|"
                   r"disregard|new instructions|override the gate)", re.I)


class ProposalError(Exception):
    pass


def addr_key(a):
    """'0x40aed0' / '0040aed0' / 4238032 -> '0040aed0'."""
    if isinstance(a, int):
        return "%08x" % a
    s = str(a).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if not re.match(r"^[0-9a-f]{1,8}$", s):
        raise ProposalError("bad address %r" % a)
    return "%08x" % int(s, 16)


def split_md(text):
    """-> (front_matter dict, body text, yaml block dict)."""
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, re.S)
    if not m:
        raise ProposalError("missing YAML front matter (--- ... ---)")
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as ex:
        raise ProposalError("front matter is not YAML: %s" % ex)
    body = m.group(2)
    blocks = re.findall(r"```yaml\r?\n(.*?)\r?\n```", body, re.S)
    if len(blocks) != 1:
        raise ProposalError("expected exactly one ```yaml block, found %d" % len(blocks))
    try:
        data = yaml.safe_load(blocks[0]) or {}
    except yaml.YAMLError as ex:
        raise ProposalError("yaml block does not parse: %s" % ex)
    if not isinstance(data, dict):
        raise ProposalError("yaml block must be a mapping")
    return fm, body, data


def _hex(v, what):
    if isinstance(v, int):
        return "0x%x" % v
    if not isinstance(v, str) or not ADDR_RE.match(v):
        raise ProposalError("%s: %r is not a hex address" % (what, v))
    return "0x%x" % int(v, 16)


def g0_scan(text, where):
    """Reject text that quotes instruction-like content as a reason (gate G0). Returns list of hits."""
    hits = []
    for m in G0_RE.finditer(text or ""):
        hits.append("%s: %r" % (where, m.group(0)))
    return hits


def validate_evidence(ev, where):
    if not isinstance(ev, dict) or "kind" not in ev:
        raise ProposalError("%s: evidence item without kind" % where)
    # aliases used by Task 4's batch rows (string / string_addr / import_name / sites) are normalised
    for old, new in (("string", "literal"), ("string_addr", "literal_addr"), ("import_name", "import")):
        if old in ev and new not in ev:
            ev[new] = ev[old]
    if "sites" in ev and "site" not in ev and ev["sites"]:
        ev["site"] = ev["sites"][0]
    k = ev["kind"]
    if k not in KINDS:
        raise ProposalError("%s: evidence kind %r not in the section 4.2 vocabulary" % (where, k))
    if k == "dynamic-capture":
        if not ev.get("capture_id"):
            raise ProposalError("%s: dynamic-capture without capture_id (G5)" % where)
    elif k == "ported":
        if not ev.get("source_instance"):
            raise ProposalError("%s: ported evidence without source_instance (gate P)" % where)
    elif k == "create":
        if not ev.get("method"):
            raise ProposalError("%s: create without method (gate C)" % where)
    elif k == "table-entry":
        if not ev.get("pairs") and not ev.get("table"):
            raise ProposalError("%s: table-entry needs pairs [{table,index,tag}] or table (gate N)" % where)
    else:
        if "site" not in ev:
            raise ProposalError("%s: %s evidence without site" % (where, k))
        ev["site"] = _hex(ev["site"], where + ".site")
    if k == "string-xref":
        if "literal" not in ev or "literal_addr" not in ev:
            raise ProposalError("%s: string-xref needs literal and literal_addr" % where)
        ev["literal_addr"] = _hex(ev["literal_addr"], where + ".literal_addr")
        f = ev.get("form")
        if f not in (None, "~") and f not in SELF_NAME_FORMS:
            raise ProposalError("%s: form %r not in %s" % (where, f, sorted(SELF_NAME_FORMS)))
    if k == "width-from" and not isinstance(ev.get("width"), int):
        raise ProposalError("%s: width-from needs an integer width" % where)
    if k == "call-cleanup" and not ev.get("cleanup"):
        raise ProposalError("%s: call-cleanup needs cleanup (e.g. 'add esp,0x14')" % where)
    if k == "constant-anchor":
        if "unique" not in ev:
            raise ProposalError("%s: constant-anchor needs unique: true|false (<= 3 .text sites, method)" % where)
        if ev.get("unique") and not ev.get("method"):
            raise ProposalError("%s: unique constant-anchor carries a count and needs method (gate C)" % where)
    for c in ("n", "count"):
        if c in ev and not ev.get("method"):
            raise ProposalError("%s: %s=%r without method (gate C)" % (where, c, ev[c]))
    for c in ("md5",):
        if c in ev and ev[c] != PRISTINE_MD5 and not ev.get("patched-build-only"):
            raise ProposalError("%s: md5 %s is not the pristine binary (H0)" % (where, ev[c]))
    ev.setdefault("md5", PRISTINE_MD5)
    return ev


def load_proposal(path):
    text = open(path, encoding="utf-8").read()
    fm, body, d = split_md(text)
    p = {"path": path, "front": fm, "body": body, "data": d, "g0": []}
    for k in ("addr", "view", "drafter", "lease", "export_md5", "binary_md5", "tokens_used"):
        if k not in fm:
            raise ProposalError("front matter missing %s" % k)
    if fm["view"] not in VIEWS:
        raise ProposalError("view %r not in %s" % (fm["view"], VIEWS))
    if fm["binary_md5"] != PRISTINE_MD5:
        raise ProposalError("binary_md5 %s is not the pristine binary (H0)" % fm["binary_md5"])
    if not isinstance(fm["tokens_used"], int) or fm["tokens_used"] < 0:
        raise ProposalError("tokens_used must be a non-negative integer (gate Q)")
    p["key"] = addr_key(fm["addr"])
    base = os.path.basename(path)
    want = p["key"] + (".proposal.md" if fm["view"] == "c" else ".proposal.pcode.md")
    if base != want:
        raise ProposalError("file name %s does not match view/addr (expected %s)" % (base, want))
    name = d.get("name", "keep")
    if name != "keep" and not NAME_RE.match(str(name)):
        raise ProposalError("name %r is not an identifier" % name)
    if d.get("status", "proposed") not in STATUSES:
        raise ProposalError("status %r not in %s" % (d.get("status"), STATUSES))
    if d.get("conv", "auto") not in CONVS:
        raise ProposalError("conv %r not in %s" % (d.get("conv"), CONVS))
    ce = d.get("conv_evidence", "auto:paramid") or "auto:paramid"
    if not (ce.startswith("auto:") or re.match(r"^(call-cleanup@0x[0-9a-fA-F]+:add esp,0x[0-9a-fA-F]+|ret-imm@0x[0-9a-fA-F]+:ret 0x[0-9a-fA-F]+)$", ce)):
        raise ProposalError("conv_evidence %r is not auto:... / call-cleanup@site:add esp,0xN / ret-imm@site:ret 0xN" % ce)
    if d.get("conv", "auto") != "auto" and ce.startswith("auto:"):
        raise ProposalError("conv %s claimed with auto conv_evidence (gate K)" % d["conv"])
    claims = d.get("claims") or []
    if not isinstance(claims, list):
        raise ProposalError("claims must be a list")
    for i, c in enumerate(claims):
        w = "claims[%d]" % i
        if not isinstance(c, dict) or c.get("claim") not in CLAIM_TYPES:
            raise ProposalError("%s: claim type must be one of %s" % (w, CLAIM_TYPES))
        if "value" not in c:
            raise ProposalError("%s: missing value" % w)
        evs = c.get("evidence") or []
        if not evs:
            raise ProposalError("%s (%s): a claim without evidence is a hypothesis; move it to hypotheses:" % (w, c["claim"]))
        c["evidence"] = [validate_evidence(e, "%s.evidence[%d]" % (w, j)) for j, e in enumerate(evs)]
        if c["claim"] == "global":
            for k in ("addr", "class", "width"):
                if k not in c:
                    raise ProposalError("%s: global claim needs %s" % (w, k))
            c["addr"] = _hex(c["addr"], w + ".addr")
            if c["class"] not in ("init", "bss", "iat"):
                raise ProposalError("%s: class %r not init|bss|iat (gate A)" % (w, c["class"]))
            if not NAME_RE.match(str(c["value"])):
                raise ProposalError("%s: global name %r is not an identifier" % (w, c["value"]))
        if c["claim"] == "field":
            if "offset" not in c:
                raise ProposalError("%s: field claim needs offset" % w)
            c["offset"] = int(c["offset"], 16) if isinstance(c["offset"], str) else int(c["offset"])
            if not any(e["kind"] in ("width-from", "bit-tested-at") for e in c["evidence"]):
                raise ProposalError("%s: field claim needs width-from or bit-tested-at evidence (gate T)" % w)
        if c["claim"] == "param" and not isinstance(c.get("index"), int):
            raise ProposalError("%s: param claim needs an integer index" % w)
        if c["claim"] == "name" and c["value"] != name:
            raise ProposalError("%s: name claim %r differs from top-level name %r" % (w, c["value"], name))
        if c["claim"] == "conv" and c["value"] != d.get("conv"):
            raise ProposalError("%s: conv claim %r differs from top-level conv %r" % (w, c["value"], d.get("conv")))
    if name != "keep" and not any(c["claim"] == "name" for c in claims):
        raise ProposalError("name %r without a name claim carrying evidence (write it as a hypothesis or add evidence)" % name)
    if d.get("hypotheses") is not None and not isinstance(d["hypotheses"], list):
        raise ProposalError("hypotheses must be a list of strings")
    # G0 over every free-text field
    p["g0"] += g0_scan(body, "body")
    for i, c in enumerate(claims):
        for j, e in enumerate(c["evidence"]):
            for fld in ("claim", "reason", "note", "why"):
                p["g0"] += g0_scan(str(e.get(fld, "")), "claims[%d].evidence[%d].%s" % (i, j, fld))
    for h in d.get("hypotheses") or []:
        p["g0"] += g0_scan(str(h), "hypotheses")
    if d.get("blocker") not in (None, "~", ""):
        b = str(d["blocker"])
        if len(b.split(". ")) > 2:
            raise ProposalError("blocker must be one falsifiable sentence (H7)")
    return p


def load_review(path):
    text = open(path, encoding="utf-8").read()
    fm, body, d = split_md(text)
    for k in ("addr", "reviewer", "proposals", "gate_run"):
        if k not in fm:
            raise ProposalError("review front matter missing %s" % k)
    if d.get("verdict") not in ("accept", "reject", "requeue"):
        raise ProposalError("review verdict must be accept|reject|requeue")
    if d.get("g0") not in ("pass", "fail"):
        raise ProposalError("review needs g0: pass|fail")
    for o in d.get("overrides") or []:
        if not o.get("gate") or not o.get("reason"):
            raise ProposalError("override without gate/reason")
    rc = d.get("reconcile")
    if rc is not None and (not isinstance(rc, dict) or not rc.get("name")):
        raise ProposalError("reconcile must be a mapping with a name (one of the two proposed spellings)")
    r = {"path": path, "front": fm, "body": body, "data": d, "key": addr_key(fm["addr"])}
    r["g0"] = g0_scan(body, "review body")
    return r


def _claim_key(c):
    t = c["claim"]
    if t == "name":
        return ("name",)
    if t == "param":
        return ("param", c["index"])
    if t == "field":
        return ("field", c.get("struct"), c["offset"])
    if t == "global":
        return ("global", c["addr"])
    return (t,)


NAME_STYLE_RE = re.compile(r"^[a-z0-9]+_[A-Z]")   # the map's canonical spelling: prefix_CamelCase


def norm_name(n):
    """G4 normalisation (PILOT-1 change 1): case and separators do not carry meaning."""
    return re.sub(r"[^a-z0-9]", "", str(n or "").lower())


def split_prefix(n):
    n = str(n or "")
    if "_" in n:
        a, b = n.split("_", 1)
        return a, b
    return "", n


def canonical_spelling(a, b):
    for n in (a, b):
        if NAME_STYLE_RE.match(n):
            return n
    return a


# a trailing one of these is part of the type, never the parameter's identifier ('unsigned int' is a type)
TYPE_WORDS = {"void", "char", "short", "int", "long", "float", "double", "signed", "unsigned",
              "const", "volatile", "struct", "union", "enum", "bool"}


def param_type(v):
    r"""The G4 key for a param claim is (index, type): the identifier spelling is free text
    (subsystems\VOCABULARY.md), so it is stripped here and the stars are normalised to '<base> <stars>'.

        'const char *path' -> 'const char *'   'FILE *fp' / 'FILE * fp' / 'FILE*fp' -> 'FILE *'
        'FILE *' -> 'FILE *'                   'char **argv' -> 'char **'
        'uint32_t miscCaps' -> 'uint32_t'      'int' -> 'int'      'unsigned int' -> 'unsigned int'
    """
    v = " ".join(str(v or "").split())
    if not v:
        return v
    m = re.match(r"^(.*?)\s*(\*+)\s*([A-Za-z_]\w*)?$", v)
    if m and m.group(1).strip():
        return "%s %s" % (m.group(1).strip(), m.group(2))
    parts = v.split()
    if len(parts) >= 2 and re.match(r"^[A-Za-z_]\w*$", parts[-1]) and parts[-1] not in TYPE_WORDS:
        return " ".join(parts[:-1])
    return v


def intersect(pc, pp):
    """G4: only claims present in both views with the same value are accepted; evidence is the union.
    Names agree when they are equal after normalisation (spelling) or when the part after the prefix agrees
    (prefix: the merge resolves the prefix through the subsystem vocabulary or the reviewer's reconcile).
    Param claims compare index + type; the identifier spelling is the c view's. Returns (agreed, disagreements, summary)."""
    a = {_claim_key(c): c for c in pc["data"].get("claims") or []}
    b = {_claim_key(c): c for c in pp["data"].get("claims") or []}
    agreed, dis = [], []
    for k in sorted(set(a) | set(b), key=str):
        ca, cb = a.get(k), b.get(k)
        if ca is None or cb is None:
            dis.append({"key": list(map(str, k)), "c": ca and ca["value"], "pcode": cb and cb["value"], "why": "only one view"})
            continue
        va, vb = str(ca["value"]).strip(), str(cb["value"]).strip()
        same = va == vb
        if not same and k[0] == "param":
            same = param_type(va) == param_type(vb)
        if not same and k[0] == "name":
            # spelling, or prefix mode (words after the prefix agree): the merge sets the canonical value
            same = norm_name(va) == norm_name(vb) or (bool(split_prefix(va)[1]) and norm_name(split_prefix(va)[1]) == norm_name(split_prefix(vb)[1]))
        if not same and k[0] == "global":
            same = norm_name(va) == norm_name(vb)
        if not same:
            dis.append({"key": list(map(str, k)), "c": ca["value"], "pcode": cb["value"], "why": "values differ"})
            continue
        m = dict(ca)
        if k[0] in ("name", "global") and va != vb:
            m["value"] = canonical_spelling(va, vb)
        seen = set(); evs = []
        for e in list(ca["evidence"]) + list(cb["evidence"]):
            sig = json.dumps(e, sort_keys=True)
            if sig not in seen:
                seen.add(sig); evs.append(dict(e))
        m["evidence"] = evs
        agreed.append(m)
    na, nb = pc["data"].get("name", "keep"), pp["data"].get("name", "keep")
    if na == nb:
        mode, canon = "exact", na
    elif norm_name(na) == norm_name(nb):
        mode, canon = "spelling", canonical_spelling(na, nb)
    elif norm_name(split_prefix(na)[1]) == norm_name(split_prefix(nb)[1]) and split_prefix(na)[1]:
        mode, canon = "prefix", None      # the merge resolves the prefix (vocabulary / reconcile) or requeues
    else:
        mode, canon = "differ", None
    summary = {"name_agree": mode in ("exact", "spelling"), "name_mode": mode, "name_canonical": canon,
               "name_c": na, "name_pcode": nb, "prefix_c": split_prefix(na)[0], "prefix_pcode": split_prefix(nb)[0],
               "status_c": pc["data"].get("status", "proposed"), "status_pcode": pp["data"].get("status", "proposed"),
               "claims_agreed": len(agreed), "claims_disagreed": len(dis)}
    return agreed, dis, summary


def to_batch(key, claims, status, data, batch_name, views):
    """Merge batch (tools\\merge.py format) from agreed claims."""
    addr = "0x%x" % int(key, 16)
    frow = {"addr": addr, "status": status, "evidence": []}
    name = None
    globals_rows = []
    for c in claims:
        t = c["claim"]
        if t == "name":
            name = c["value"]
            for e in c["evidence"]:
                e2 = dict(e); e2["claim"] = "name %s" % name; frow["evidence"].append(e2)
        elif t == "conv":
            frow["conv"] = c["value"]
            for e in c["evidence"]:
                e2 = dict(e); e2["claim"] = "conv %s" % c["value"]; frow["evidence"].append(e2)
        elif t == "subsystem":
            frow["subsystem"] = c["value"]
            for e in c["evidence"]:
                e2 = dict(e); e2["claim"] = "subsystem %s" % c["value"]; frow["evidence"].append(e2)
        elif t == "duplicate-of":
            frow["duplicate_of"] = c["value"]
        elif t in ("param", "field", "status"):
            for e in c["evidence"]:
                e2 = dict(e); e2["claim"] = "%s %s" % (t, json.dumps({k: v for k, v in c.items() if k != "evidence"}, default=str))
                frow["evidence"].append(e2)
        elif t == "global":
            g = {"addr": c["addr"], "class": c["class"], "width": c["width"], "type": c.get("type", ""), "name": c["value"],
                 "status": c.get("status", "proposed"), "readers": c.get("readers", ""), "writers": c.get("writers", ""),
                 "bound_evidence": c.get("bound_evidence", ""), "evidence": [dict(e, claim="global %s" % c["value"]) for e in c["evidence"]]}
            globals_rows.append(g)
    if name is None:
        # keep FUN_: a status/conv/subsystem-only row still needs the current name
        return None, globals_rows
    frow["name"] = name
    # the row's convention follows the agreed conv claim only (set at the `conv` claim above); a dropped or rejected
    # conv claim leaves auto, and the front-matter conv_evidence is copied only in that case (gate K)
    if frow.get("conv") and frow["conv"] != "auto":
        frow["conv_evidence"] = data.get("conv_evidence", "auto:paramid") or "auto:paramid"
    else:
        frow["conv"] = ""
        frow["conv_evidence"] = "auto:paramid"
    if data.get("subsystem") not in (None, "~", "") and "subsystem" not in frow:
        frow["subsystem"] = data["subsystem"]
    return {"batch": batch_name, "author": "merge --proposal (views: %s)" % ",".join(views),
            "functions": [frow], "globals": globals_rows}, globals_rows


def md5_file(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


if __name__ == "__main__":
    # `python tools\proposal.py <file>`: validate one proposal or review file and print the parsed structure
    for f in sys.argv[1:]:
        try:
            if f.endswith(".review.md"):
                r = load_review(f); print("OK review", r["key"], r["data"]["verdict"], "g0 hits:", r["g0"])
            else:
                p = load_proposal(f); print("OK proposal", p["key"], p["front"]["view"], p["data"].get("name"),
                                             "claims:", len(p["data"].get("claims") or []), "g0 hits:", p["g0"])
        except ProposalError as ex:
            print("INVALID", f, ":", ex); sys.exit(1)
