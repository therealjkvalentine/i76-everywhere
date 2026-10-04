#!/usr/bin/env python3
"""merge.py - the single writer for symbols\\functions.tsv, symbols\\globals.tsv and evidence\\E*.json.

Method doc (docs\\FRESH-START-METHOD.md) section 4: every row is validated against gates A, C, T, L, K, N, B
before it enters a TSV. Nothing else writes those files.

Usage:
    python tools\\merge.py batch.json [--map C:\\Users\\james\\i76-map] [--dry-run] [--log path] [--gates]
    python tools\\merge.py --proposal <addr> [--dry-run] [--single-view]        (Task 8: the agent-loop path)

Proposal path (method doc section 6, gates G0-G4; Task 8): reads functions\\<addr>.proposal.md (view c) and
functions\\<addr>.proposal.pcode.md (view pcode) plus functions\\<addr>.review.md (formats: tools\\proposal.py),
applies G0 (instruction-like strings are never reasons), G4 (only the intersection of the two views' claims), the
reviewer's per-claim verdicts, then runs every tools\\gates\\gate*.py on the derived batch and only then appends the
rows, writes functions\\<addr>.md, moves the proposals and review into functions\\history\\<addr>\\, appends
status\\merge-log.jsonl and releases the queue item (tools\\lease.py merge-result). --dry-run is what the reviewer
runs to obtain the gate lines; it writes nothing.

Batch format (JSON):
{
  "batch": "t4-anchors", "author": "...",
  "functions": [ {"addr": "0x4b4290", "name": "...", "status": "anchored", "conv": "__cdecl",
                  "conv_evidence": "auto:paramid" | "call-cleanup@0x4b9d40:add esp,0x14",
                  "subsystem": "bwd2", "size": 18 (only for rows that create a function),
                  "evidence": [ {evidence object}, ... ]}, ... ],
  "globals":   [ {"addr": "0x5a7e1c", "class": "bss", "width": 4, "type": "uint32", "name": "...",
                  "status": "supported", "readers": "...", "writers": "...", "bound_evidence": "",
                  "evidence": [ ... ]}, ... ]
}
Evidence object: {kind, addr, data, source, capture_id, instrument-checked, n, spread, p, method, md5, claim}
  kind (primary):   string-xref import-callee table-entry emulated-io dynamic-capture constant-anchor
                    import-thunk import-wrapper pe-entry callback-pointer
  kind (secondary): verified-callee struct-access census-class tu-neighbourhood global-write
  kind (gate L):    asm-shape fid  (library);  synthetic-shape (synthetic)
  kind (gate K):    call-cleanup {site, cleanup}
  kind (gate T):    width-from {site, width}
  kind (gate A):    ref-site {site} (bss globals);  create {method} (rows that create a function)
Every evidence row carries the md5 of the binary it was read from (H0); a count needs its method (gate C).
"""
import os, sys, json, csv, re, glob, io, time, argparse, hashlib, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_tables import Image, hx  # address classes per gate A (section 2.1), pefile-based
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_MEM, X86_OP_IMM

PRISTINE_MD5 = "9a232dcc2c164648cff20c414c1f9698"
STATUSES = ("auto", "proposed", "supported", "anchored", "library", "synthetic")
# gate P fast path (FOLDIN-REPORT section 3): `ported-static` = the quoted bytes of a ported static claim match the
# pristine file (verified here by bytes_at / capstone) and count as the GOG-side anchor for the ADDRESS; `ported` =
# the source's own row text, one H6 instance, never sufficient alone (secondary).
PRIMARY = {"string-xref", "import-callee", "table-entry", "emulated-io", "dynamic-capture", "constant-anchor",
           "import-thunk", "import-wrapper", "pe-entry", "callback-pointer", "export-ordinal", "dispatch-case", "ported-static",
           "census", "oracle"}
SECONDARY = {"verified-callee", "struct-access", "census-class", "tu-neighbourhood", "global-write", "ported",
             "blind"}                                  # verify/: an independent cold reading judged same/compatible
# G-BUILD-TAG: every ported row / evidence names the build its source observed (FOLDIN-REPORT build identity table;
# method doc section 8 item 1 adds the non-GOG identities: nitro, CD-era, unversioned).
BUILD_TAGS = {"pristine-9a232dcc", "pristine+p1-58d9dec0", "aio-60abf7bc", "sandbox-4fabc303", "portable-6319abf7",
              "nitro-28b8ae27", "cd-era", "unversioned"}
# Gate P `build-shifted`: instruction-level addresses inside these aio-60abf7bc .text patch clusters do not transfer
# 1:1 (FOLDIN-REPORT section 3); the generated binaries\diff-9a232dcc-vs-60abf7bc.tsv clusters are unioned in at run time.
PATCH_CLUSTERS = [(0x49c7f0, 0x49cbd6), (0x423b40, 0x424bb4), (0x4572d5, 0x457416), (0x499b16, 0x499cec), (0x4b2220, 0x4b234c),
                  (0x432950, 0x4329de), (0x495331, 0x4953dc), (0x470f7e, 0x4710d7), (0x49318f, 0x493728)]
PORTED_COLS = ["addr", "class", "kind", "name", "status", "source_instance", "source_status", "vt_session", "vt_correlator",
               "vt_similarity", "vt_confidence", "sig_route", "existing_name", "existing_status", "note"]
# G-ENC: the doubled-encoding signature of `Get-Content | Set-Content -Encoding utf8` mojibake (a UTF-8 multibyte
# sequence re-encoded as if it were cp1252/latin-1: U+00C3 / U+00E2 / U+00C2 followed by a latin-1 symbol)
MOJIBAKE_RE = re.compile("(Ã[-¿]|â[-¿][-¿]|Â[-¿])")
LIBRARY_KINDS = {"asm-shape", "fid", "emulated-io"}
ANCHOR_KINDS = {"import-thunk", "import-wrapper", "table-entry", "pe-entry", "callback-pointer", "export-ordinal"}
SELF_NAME_FORMS = {"colon", "dash", "in", "paren", "rule-c", "procaddr"}
FUNC_COLS = ["addr", "size", "name", "status", "conv", "conv_evidence", "hookable", "duplicate_of", "tu",
             "subsystem", "evidence_ids"]
GLOB_COLS = ["addr", "class", "width", "type", "name", "status", "readers", "writers", "bound_evidence",
             "evidence_ids"]
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_@$]*$")


class Reject(Exception):
    pass


# --------------------------------------------------------------------------------------------------
# TSV helpers (comments preserved; every write goes to .tmp, is renamed, then read back)
# --------------------------------------------------------------------------------------------------
def read_tsv(path, cols):
    comments, rows = [], []
    if not os.path.exists(path):
        return comments, rows
    with open(path, encoding="utf-8", newline="") as fh:
        for line in fh:
            if line.startswith("#"):
                comments.append(line.rstrip("\r\n")); continue
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split("\t")
            if parts[0] == cols[0]:
                continue  # header
            parts += [""] * (len(cols) - len(parts))
            rows.append(dict(zip(cols, parts[:len(cols)])))
    return comments, rows


def write_tsv(path, comments, cols, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        for c in comments:
            fh.write(c + "\n")
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")
    os.replace(tmp, path)
    _, back = read_tsv(path, cols)
    if len(back) != len(rows):
        raise RuntimeError("readback of %s: %d rows written, %d read" % (path, len(rows), len(back)))
    return len(back)


# --------------------------------------------------------------------------------------------------
# Disassembly helpers for the instruction-level gates (K, T, A-bss)
# --------------------------------------------------------------------------------------------------
class Disasm:
    def __init__(self, img):
        self.img = img
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        self.md.detail = True

    def at(self, va, n=2):
        """Decode up to n instructions starting at va (must be in .text)."""
        if not self.img.in_text(va):
            raise Reject("site %s is not in .text" % hx(va))
        off = self.img.va2off(va)
        return list(self.md.disasm(self.img.data[off:off + 16 * n], va, count=n))

    def refs_addr(self, ins, target):
        """True when an operand of ins is [disp32]/[base+idx*s+disp32] with disp32==target, or imm32==target."""
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.disp == target:
                return True
            if op.type == X86_OP_IMM and op.imm == target:
                return True
        return False

    def mem_width(self, ins, target):
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.disp == target:
                return op.size
        return None


# --------------------------------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------------------------------
def parse_addr(s):
    try:
        return int(s, 16)
    except Exception:
        raise Reject("address %r is not hex" % s)


def gate_evidence_common(ev, dynamic_ok=False):
    """Gate C (counts carry a method) + H0 (md5 stamp) + G-BUILD-TAG + G-ENC on one evidence object."""
    if "kind" not in ev:
        raise Reject("evidence without kind")
    for k in ("n", "count"):
        if k in ev and not ev.get("method"):
            raise Reject("evidence %s carries a count (%s=%s) without a method (gate C)" % (ev["kind"], k, ev[k]))
    if ev["kind"] in ("ported", "ported-static"):
        gate_build_tag(ev, "evidence %s" % ev["kind"])
        for fld in ("quote", "claim", "note"):
            gate_enc_text(ev.get(fld, ""), "evidence %s.%s" % (ev["kind"], fld))
        if ev["kind"] == "ported" and not (ev.get("source_instance") and ev.get("source") and ev.get("quote")):
            raise Reject("ported evidence needs source, source_instance and the source's own row text as `quote` (gate P, G0)")
    if ev["kind"] == "dynamic-capture":
        if not ev.get("capture_id"):
            raise Reject("dynamic-capture without capture_id (G5)")
        return
    md5 = ev.get("md5")
    if md5 != PRISTINE_MD5 and not ev.get("patched-build-only"):
        raise Reject("evidence %s carries md5 %s, not the pristine %s (H0)" % (ev["kind"], md5, PRISTINE_MD5))
    if "instrument-checked" not in ev:
        ev["instrument-checked"] = "n/a"


def gate_build_tag(obj, what="evidence"):
    """G-BUILD-TAG (FOLDIN-REPORT section 3, G-STALE/G-BUILD-TAG): every ported row and every ported evidence item
    carries `build_tag` from the build identity table."""
    bt = obj.get("build_tag")
    if bt not in BUILD_TAGS:
        raise Reject("%s carries build_tag %r, not one of %s (G-BUILD-TAG)" % (what, bt, sorted(BUILD_TAGS)))


def gate_enc_text(s, what):
    """G-ENC on a string already in memory: no mojibake signature, no BOM character."""
    if not isinstance(s, str):
        return
    if "﻿" in s:
        raise Reject("%s contains a BOM character (G-ENC)" % what)
    m = MOJIBAKE_RE.search(s)
    if m:
        raise Reject("%s carries the doubled-encoding signature %r (G-ENC)" % (what, m.group(0)))


def gate_enc_file(path):
    """G-ENC (FOLDIN-REPORT section 3): map and evidence files are UTF-8 without BOM or pure ASCII; the doubled-encoding
    signature (PowerShell `Get-Content | Set-Content -Encoding utf8` mojibake) is rejected. Returns (ok, reason)."""
    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        return False, "%s starts with a UTF-8 BOM (G-ENC)" % path
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError as ex:
        return False, "%s is not valid UTF-8: %s (G-ENC)" % (path, ex)
    m = MOJIBAKE_RE.search(txt)
    if m:
        line = txt.count("\n", 0, m.start()) + 1
        return False, "%s:%d carries the doubled-encoding signature %r (G-ENC)" % (path, line, m.group(0))
    return True, "utf-8 no BOM (%d bytes, %s)" % (len(raw), "ascii" if raw.isascii() else "non-ascii utf-8")


def load_patch_clusters(M):
    """PATCH_CLUSTERS (section 3 list) unioned with the .text clusters of binaries\\diff-9a232dcc-vs-60abf7bc.tsv."""
    cl = list(PATCH_CLUSTERS)
    p = os.path.join(M, "binaries", "diff-9a232dcc-vs-60abf7bc.tsv")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.startswith("#") or line.startswith("section\t") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            if f[0] == ".text":
                cl.append((int(f[2], 16), int(f[3], 16)))
    return sorted(set(cl))


def in_cluster(va, clusters):
    for lo, hi in clusters:
        if lo <= va < hi:
            return (lo, hi)
    return None


def gate_p_static(img, dis, ev, clusters, row_kind="function"):
    """Gate P `ported-static` fast path. The evidence quotes the bytes the source saw at `addr` (init/text classes) or at
    the referencing instruction `site` (bss globals); they must equal the pristine file's bytes. Inside an aio patch
    cluster the item is tagged build_shifted; for an instruction-level claim (row kind `site`) the fast path then does
    not apply. Returns a one-line detail. The semantics of the row stay proposed: only the address is anchored."""
    gate_build_tag(ev, "ported-static evidence")
    if not ev.get("bytes"):
        raise Reject("ported-static evidence without the quoted bytes (gate P fast path)")
    try:
        want = bytes.fromhex(ev["bytes"].replace(" ", ""))
    except ValueError:
        raise Reject("ported-static bytes %r are not hex" % ev["bytes"])
    if ev.get("site"):
        site = parse_addr(ev["site"])
        if not img.in_text(site):
            raise Reject("ported-static site %s is not in .text" % hx(site))
        got = img.bytes_at(site, len(want))
        if got != want:
            raise Reject("ported-static: bytes at site %s are %s, quoted %s (does not match pristine)" % (hx(site), got.hex() if got else None, want.hex()))
        # `target` = the address the quoted instruction must reference (a bss global, a table base, a callee); `addr` is
        # the row address the merge stamps on every evidence item and is not a reference claim
        target = parse_addr(ev["target"]) if ev.get("target") else None
        ins = dis.at(site, 1)
        if not ins:
            raise Reject("ported-static site %s does not decode" % hx(site))
        if target is not None and not dis.refs_addr(ins[0], target):
            raise Reject("ported-static site %s (%s %s) does not reference %s" % (hx(site), ins[0].mnemonic, ins[0].op_str, hx(target)))
        ev["insn"] = "%s %s" % (ins[0].mnemonic, ins[0].op_str)
        where = site
    else:
        if not ev.get("addr"):
            raise Reject("ported-static evidence needs addr (init/text) or site (bss) (gate P)")
        a = parse_addr(ev["addr"])
        if img.klass(a) not in ("init", "text"):
            raise Reject("ported-static addr %s is class %s: a bss claim must quote the referencing instruction as site" % (hx(a), img.klass(a)))
        got = img.bytes_at(a, len(want))
        if got != want:
            raise Reject("ported-static: bytes at %s are %s, quoted %s (does not match pristine)" % (hx(a), got.hex() if got else None, want.hex()))
        where = a
    ev.setdefault("method", "bytes_at over the pristine file (md5 %s); cluster test against PATCH_CLUSTERS + binaries/diff-9a232dcc-vs-60abf7bc.tsv" % PRISTINE_MD5)
    c = in_cluster(where, clusters)
    if c:
        ev["build_shifted"] = "0x%x-0x%x" % c
        if row_kind == "site":
            raise Reject("ported-static site %s lies inside the aio patch cluster 0x%x-0x%x: instruction-level address is build-shifted, fast path does not apply" % (hx(where), c[0], c[1]))
    else:
        ev["build_shifted"] = ""
    return "%d bytes at %s match pristine%s" % (len(want), hx(where), (" [build-shifted %s]" % ev["build_shifted"]) if c else "")



def _norm_cleanup(text):
    """gate K text compare: spaces removed and immediates compared numerically ('add esp,0x8' == 'add esp, 8')."""
    t = str(text).replace(" ", "").lower()
    m = re.match(r"^(addesp,|ret)(0x[0-9a-f]+|\d+)$", t)
    if m:
        return "%s%d" % (m.group(1), int(m.group(2), 16) if m.group(2).startswith("0x") else int(m.group(2)))
    return t

def gate_c_trap_after(dis, ev, ghidra_funcs):
    """Gate C method tag `hwbp-trap-after` (FOLDIN-REPORT section 3, C18): a hardware-watchpoint hit reports the
    resumed EIP (`trap_after`); the evidence must resolve it to the faulting instruction (`site` = preceding
    instruction) and the enclosing function start (`function`), verified by decoding the function from its start."""
    if ev.get("method") != "hwbp-trap-after" and not ev.get("trap_after"):
        return None
    for k in ("trap_after", "site", "function"):
        if not ev.get(k):
            raise Reject("hwbp-trap-after evidence needs trap_after (resumed EIP), site (faulting instruction) and function (gate C)")
    ta, site, fn = parse_addr(ev["trap_after"]), parse_addr(ev["site"]), parse_addr(ev["function"])
    f = ghidra_funcs.get(fn)
    if f is None:
        raise Reject("hwbp-trap-after: function %s is not a Ghidra function start (gate C)" % hx(fn))
    size = int(f["size"])
    if not (fn <= site < fn + size and fn < ta <= fn + size):
        raise Reject("hwbp-trap-after: site %s / trap_after %s are not inside %s (+%d) (gate C)" % (hx(site), hx(ta), hx(fn), size))
    off = dis.img.va2off(fn)
    prev = None
    for ins in dis.md.disasm(dis.img.data[off:off + size], fn):
        if ins.address == ta:
            if prev is None or prev.address != site:
                raise Reject("hwbp-trap-after: the instruction before %s is %s, not the claimed site %s (gate C)" % (hx(ta), hx(prev.address) if prev else None, hx(site)))
            ev["insn"] = "%s %s" % (prev.mnemonic, prev.op_str)
            ev["method"] = "hwbp-trap-after"
            return "trap_after %s resolves to %s (%s) in %s" % (hx(ta), hx(site), ev["insn"], hx(fn))
        prev = ins
    raise Reject("hwbp-trap-after: %s is not on an instruction boundary of %s (gate C)" % (hx(ta), hx(fn)))


def gate_k(dis, row, evs):
    """Convention claims need call-site cleanup evidence; otherwise conv stays auto."""
    ce = row.get("conv_evidence", "") or "auto:paramid"
    if ce.startswith("auto:"):
        return
    ks = [e for e in evs if e["kind"] == "call-cleanup"]
    if not ks:
        raise Reject("conv %s claimed without call-cleanup evidence (gate K)" % row.get("conv"))
    for e in ks:
        site = parse_addr(e["site"])
        ins = dis.at(site, 2)
        if len(ins) < 2 or ins[0].mnemonic != "call":
            raise Reject("call-cleanup site %s is not a call (gate K)" % hx(site))
        nxt = "%s %s" % (ins[1].mnemonic, ins[1].op_str)
        want = _norm_cleanup(e["cleanup"])
        if _norm_cleanup(nxt) != want:
            raise Reject("call-cleanup at %s: next instruction is %r, claimed %r (gate K)" % (hx(site), nxt, e["cleanup"]))
        # cleanup form -> convention
        if want.startswith("addesp,"):
            if row.get("conv") != "__cdecl":
                raise Reject("add esp after call implies __cdecl, row says %s (gate K)" % row.get("conv"))
        # the callee must be this row's function
        tgt = [op.imm for op in ins[0].operands if op.type == X86_OP_IMM]
        if tgt and tgt[0] != parse_addr(row["addr"]):
            raise Reject("call at %s targets %s, not this row (gate K)" % (hx(site), hx(tgt[0])))


def gate_l(row, evs):
    st = row["status"]
    kinds = {e["kind"] for e in evs}
    if st == "library":
        if not (kinds & LIBRARY_KINDS):
            raise Reject("library needs asm-shape / fid / emulated-io evidence (gate L)")
        for e in evs:
            if e["kind"] == "asm-shape" and not e.get("source"):
                raise Reject("asm-shape evidence needs a source (the reference file) (gate L)")
    if st == "synthetic" and "synthetic-shape" not in kinds:
        raise Reject("synthetic needs synthetic-shape evidence (gate L)")


def gate_g1_g2(row, evs):
    """G1 (anchored) and G2 (supported) evidence requirements."""
    st = row["status"]
    kinds = [e["kind"] for e in evs]
    if st == "anchored":
        ok = False
        for e in evs:
            if e["kind"] in ANCHOR_KINDS:
                ok = True
            if e["kind"] == "string-xref" and e.get("form") in SELF_NAME_FORMS:
                if not e.get("literal"):
                    raise Reject("self-naming string-xref needs the literal (G1)")
                ok = True
        if not ok:
            raise Reject("anchored needs an import-thunk/import-wrapper/table-entry/pe-entry/callback-pointer "
                         "row or a self-naming string-xref with form (G1)")
    if st == "supported":
        # a constant-anchor is primary only when unique (<= 3 .text sites); otherwise it counts as secondary
        prim = {e["kind"] for e in evs if e["kind"] in PRIMARY and not (e["kind"] == "constant-anchor" and not e.get("unique"))}
        allk = {k for k in kinds if k in PRIMARY or k in SECONDARY}
        # two independent blind readings (distinct 'reader' tags) judged same/compatible count as one primary kind:
        # the verification program's rule for utility functions the scenarios never run (VERIFICATION-PROGRAM.md s6)
        readers = {e.get("reader", "1") for e in evs if e["kind"] == "blind"}
        if len(readers) >= 2:
            prim.add("blind-x2"); allk.add("blind-x2")
        if not prim or len(allk) < 2:
            raise Reject("supported needs >= 2 independent evidence kinds with >= 1 primary; got %s (G2)" % sorted(set(kinds)))


def bwd2_pairs(tables_rows):
    """(table_base, tag) pairs per handler from tables.tsv bwd2-desc rows (gate N)."""
    pairs = {}
    for r in tables_rows:
        if r.get("kind") != "bwd2-desc":
            continue
        base = r["base"]
        for i, ent in enumerate(r["targets"].split(";")):
            if "=" not in ent:
                continue
            tag, rest = ent.split("=", 1)
            h = rest.split("/")[0]
            if int(h, 16) == 0:
                continue
            pairs.setdefault(int(h, 16), set()).add((base, i, tag.replace("\\0", "")))
    return pairs


def gate_n(row, evs, name_owner, pairs):
    name = row["name"]
    if not NAME_RE.match(name):
        raise Reject("name %r is not an identifier (gate N)" % name)
    a = parse_addr(row["addr"])
    if name in name_owner and name_owner[name] != a:
        raise Reject("name %r already belongs to %s (gate N)" % (name, hx(name_owner[name])))
    if name.startswith("bwd2_h_"):
        te = [e for e in evs if e["kind"] == "table-entry"]
        if not te:
            raise Reject("tag-derived name without table-entry evidence (gate N)")
        listed = set()
        for e in te:
            for p in e.get("pairs", []):
                listed.add((p["table"], int(p["index"]), p["tag"]))
        expect = pairs.get(a, set())
        if listed != expect:
            raise Reject("tag-derived name must list every (table,tag) pair: listed %s expected %s (gate N)"
                         % (sorted(listed), sorted(expect)))
        tags = []
        for t, i, tag in sorted(expect, key=lambda x: (x[0], x[1])):
            if tag not in tags:
                tags.append(tag)
        want = "bwd2_h_%s_%x" % ("_".join(tags), a)
        if name != want:
            raise Reject("tag-derived name must be %s (gate N)" % want)


def gate_b(row):
    t = row.get("type", "") or ""
    if "[" in t and not row.get("bound_evidence"):
        if row["status"] not in ("proposed", "auto"):
            raise Reject("array type %r without bound_evidence must stay proposed (gate B)" % t)


def gate_a_function(img, row, ghidra_funcs, evs):
    a = parse_addr(row["addr"])
    if img.klass(a) != "text":
        raise Reject("function address %s is class %s, not .text (gate A)" % (hx(a), img.klass(a)))
    if a not in ghidra_funcs:
        cr = [e for e in evs if e["kind"] == "create"]
        if not cr or not row.get("size"):
            raise Reject("no Ghidra function at %s: a row that creates one needs size and a 'create' evidence "
                         "with its method (gate A)" % hx(a))
        for e in cr:
            if not e.get("method"):
                raise Reject("create evidence without method (gate C)")


def gate_a_global(img, dis, row, evs):
    a = parse_addr(row["addr"])
    cls = row["class"]
    actual = img.klass(a)
    if cls == "iat":
        if actual != "iat":
            raise Reject("%s is class %s, not iat (gate A)" % (hx(a), actual))
        imp = img.imports.get(a)
        if not imp:
            raise Reject("slot %s not in the import descriptor (gate A)" % hx(a))
        return "slot %s = %s!%s" % (hx(a), imp[0], imp[1] or "#%d" % imp[2])
    if cls == "bss":
        if actual != "bss":
            raise Reject("%s is class %s, not bss (gate A)" % (hx(a), actual))
        rs = [e for e in evs if e["kind"] == "ref-site"]
        if not rs:
            raise Reject("bss global without a ref-site (a .text instruction whose disp32/imm32 decodes to it) (gate A)")
        for e in rs:
            site = parse_addr(e["site"])
            ins = dis.at(site, 1)
            if not ins or not dis.refs_addr(ins[0], a):
                raise Reject("ref-site %s does not decode to %s (gate A)" % (hx(site), hx(a)))
            e["insn"] = "%s %s" % (ins[0].mnemonic, ins[0].op_str)
        return "%d ref-site(s) verified by capstone" % len(rs)
    if cls == "init":
        if actual not in ("init",):
            raise Reject("%s is class %s, not init (gate A)" % (hx(a), actual))
        if img.u32(a) is None:
            raise Reject("%s has no file bytes (gate A)" % hx(a))
        return "file offset 0x%x" % img.va2off(a)
    raise Reject("class %r not accepted for a global (gate A)" % cls)


def gate_t(dis, row, evs):
    """Width claims cite the instruction that stores/loads at that width."""
    w = row.get("width", "")
    if w in ("", None):
        return
    w = int(w)
    a = parse_addr(row["addr"])
    wf = [e for e in evs if e["kind"] == "width-from"]
    if row["class"] == "iat":
        if w != 4:
            raise Reject("IAT slot width must be 4 (gate T)")
        return
    if not wf:
        raise Reject("width %d claimed without width-from evidence (gate T)" % w)
    # the width is the widest cited access: a narrower access (test byte ptr on the low byte of a dword flags word) is
    # consistent, a wider one is not, and at least one site must access the full claimed width (2026-09-26)
    full = False
    for e in wf:
        site = parse_addr(e["site"])
        ins = dis.at(site, 1)
        if not ins:
            raise Reject("width-from site %s does not decode (gate T)" % hx(site))
        mw = dis.mem_width(ins[0], a)
        if mw is None:
            # fld/fstp/inc forms: operand is memory with disp == a; capstone gives op.size
            raise Reject("width-from site %s has no memory operand at %s (gate T)" % (hx(site), hx(a)))
        if mw > w:
            raise Reject("width-from site %s accesses %d bytes, row claims %d (gate T)" % (hx(site), mw, w))
        full = full or mw == w
        e["insn"] = "%s %s" % (ins[0].mnemonic, ins[0].op_str)
    if not full:
        raise Reject("no width-from site accesses the claimed %d bytes, the widest cited is narrower (gate T)" % w)


# --------------------------------------------------------------------------------------------------
# Batch application (the original single-writer path), factored so the proposal path (Task 8) can reuse it
# --------------------------------------------------------------------------------------------------
def apply_batch(M, img, dis, batch, dry_run, emit):
    """Validate every row of `batch` against gates A, C, T, L, K, N, B, G1/G2, H0 and append the accepted rows.
    Returns {"accepted": {...}, "rejected": [...], "per_status": {...}, "evidence_ids": [...]}."""
    fpath = os.path.join(M, "symbols", "functions.tsv")
    gpath = os.path.join(M, "symbols", "globals.tsv")
    tpath = os.path.join(M, "symbols", "tables.tsv")
    fcom, frows = read_tsv(fpath, FUNC_COLS)
    gcom, grows = read_tsv(gpath, GLOB_COLS)
    if not gcom:
        gcom = ["# globals.tsv - written only by tools/merge.py. addr class per gate A (init|bss|iat); width cites a width-from "
                "instruction (gate T); readers/writers: method=capstone ref-sites listed in the evidence rows.",
                "# status: auto|proposed|supported|anchored|library|synthetic. evidence_ids -> evidence/E*.json"]
    _, trows = read_tsv(tpath, ["name", "base", "class", "end", "count", "stride", "ptr_off", "kind", "method",
                                 "source_sites", "targets", "note"])
    pairs = bwd2_pairs(trows)
    fj = json.load(open(os.path.join(M, "ghidra", "export", "functions.json"), encoding="utf-8"))
    ghidra_funcs = {int(r["addr"], 16): r for r in fj}
    fby = {parse_addr(r["addr"]): r for r in frows}
    gby = {parse_addr(r["addr"]): r for r in grows}

    # gate N owner map from what is already in the TSVs (default FUN_/DAT_ names are not claims)
    name_owner = {}
    for r in frows:
        if not r["name"].startswith("FUN_"):
            name_owner[r["name"]] = parse_addr(r["addr"])
    for r in grows:
        name_owner[r["name"]] = parse_addr(r["addr"])

    # evidence numbering: continue after the highest existing E<n>.json
    edir = os.path.join(M, "evidence")
    nums = [int(re.match(r"E(\d+)\.json", os.path.basename(p)).group(1))
            for p in glob.glob(os.path.join(edir, "E*.json")) if re.match(r"E(\d+)\.json", os.path.basename(p))]
    next_e = [max(nums) + 1 if nums else int(batch.get("evidence_base", 1))]
    pending_evidence = []

    def new_eid():
        n = next_e[0]; next_e[0] += 1
        return "E%05d" % n

    accepted = {"functions": [], "globals": [], "ported": []}
    rejected = []
    per_status = {}
    clusters = load_patch_clusters(M)

    def gate_p_c(row, evs, row_kind):
        """gate P fast path on every ported-static item; gate C hwbp-trap-after on every trap-derived item."""
        det = []
        for e in evs:
            if e.get("kind") == "ported-static":
                det.append(gate_p_static(img, dis, e, clusters, row_kind))
                e.setdefault("semantics", "proposed")
            d = gate_c_trap_after(dis, e, ghidra_funcs)
            if d:
                det.append(d)
        return det

    for row in batch.get("functions", []):
        evs = row.get("evidence", [])
        try:
            if row.get("status") not in STATUSES:
                raise Reject("status %r not in %s" % (row.get("status"), STATUSES))
            for e in evs:
                gate_evidence_common(e)
                if e.get("kind") == "dispatch-case":
                    # validated for every status, not only the supported rows gate G2 inspects (the first run of the
                    # fsm-actions batch accepted a wrong index on a proposed row: 2026-09-26)
                    import dispatch_check
                    msz = int((fby.get(parse_addr(e["matcher"])) or {}).get("size") or 0x2000)
                    try:
                        dispatch_check.check(img, dis.md, parse_addr(row["addr"]), e, msz)
                    except dispatch_check.DispatchError as ex:
                        raise Reject("dispatch-case: %s" % ex)
            gate_p_c(row, evs, "function")
            gate_a_function(img, row, ghidra_funcs, evs)
            gate_n(row, evs, name_owner, pairs)
            gate_l(row, evs)
            gate_g1_g2(row, evs)
            gate_k(dis, row, evs)
            gate_b(row)
        except Reject as ex:
            rejected.append((row.get("addr"), row.get("name"), str(ex)))
            emit("REJECT %s %s: %s" % (row.get("addr"), row.get("name"), ex)); continue
        a = parse_addr(row["addr"])
        name_owner[row["name"]] = a
        eids = []
        for e in evs:
            eid = new_eid(); e2 = dict(e); e2["id"] = eid; e2["addr"] = row["addr"]; e2["row"] = "function"
            e2.setdefault("batch", batch.get("batch")); e2.setdefault("time", time.strftime("%Y-%m-%dT%H:%M:%S"))
            pending_evidence.append((eid, e2)); eids.append(eid)
        old = fby.get(a)
        if old is None:
            old = {c: "" for c in FUNC_COLS}; old["addr"] = "0x%x" % a; old["size"] = str(row.get("size", ""))
            old["hookable"] = "tbd"; old["conv"] = row.get("conv", ""); frows.append(old); fby[a] = old
        old["name"] = row["name"]; old["status"] = row["status"]
        # a batch row that says conv "auto" (no convention claim) never downgrades a convention the map already holds
        # with evidence (2026-10-02: two verification batches reset eight rows, five with call-cleanup evidence)
        if row.get("conv") and not (row["conv"] == "auto" and old.get("conv") not in ("", "auto", None)):
            old["conv"] = row["conv"]
            old["conv_evidence"] = row.get("conv_evidence") or old.get("conv_evidence") or "auto:paramid"
        elif row.get("conv") == "auto":
            pass                                              # keep the existing conv and its evidence
        else:
            old["conv_evidence"] = row.get("conv_evidence") or old.get("conv_evidence") or "auto:paramid"
        if row.get("subsystem"): old["subsystem"] = row["subsystem"]
        if row.get("duplicate_of"): old["duplicate_of"] = row["duplicate_of"]
        prev = [x for x in (old.get("evidence_ids") or "").split(";") if x]
        old["evidence_ids"] = ";".join(prev + eids)
        accepted["functions"].append(old)
        per_status[row["status"]] = per_status.get(row["status"], 0) + 1
        emit("ACCEPT %s %s [%s] %s" % (row["addr"], row["name"], row["status"], ";".join(eids)))

    for row in batch.get("globals", []):
        evs = row.get("evidence", [])
        try:
            if row.get("status") not in STATUSES:
                raise Reject("status %r not in %s" % (row.get("status"), STATUSES))
            for e in evs:
                gate_evidence_common(e)
            gate_p_c(row, evs, "global")
            detail = gate_a_global(img, dis, row, evs)
            gate_n(row, evs, name_owner, pairs)
            gate_t(dis, row, evs)
            gate_g1_g2(row, evs)
            gate_b(row)
        except Reject as ex:
            rejected.append((row.get("addr"), row.get("name"), str(ex)))
            emit("REJECT %s %s: %s" % (row.get("addr"), row.get("name"), ex)); continue
        a = parse_addr(row["addr"])
        name_owner[row["name"]] = a
        eids = []
        for e in evs:
            eid = new_eid(); e2 = dict(e); e2["id"] = eid; e2["addr"] = row["addr"]; e2["row"] = "global"
            e2.setdefault("batch", batch.get("batch")); e2.setdefault("time", time.strftime("%Y-%m-%dT%H:%M:%S"))
            pending_evidence.append((eid, e2)); eids.append(eid)
        old = gby.get(a)
        if old is None:
            old = {c: "" for c in GLOB_COLS}; old["addr"] = "0x%x" % a; grows.append(old); gby[a] = old
        for c in ("class", "width", "type", "name", "status", "readers", "writers", "bound_evidence"):
            if row.get(c) not in (None, ""):
                old[c] = str(row[c])
        prev = [x for x in (old.get("evidence_ids") or "").split(";") if x]
        old["evidence_ids"] = ";".join(prev + eids)
        accepted["globals"].append(old)
        per_status["global:" + row["status"]] = per_status.get("global:" + row["status"], 0) + 1
        emit("ACCEPT global %s %s [%s] %s (%s)" % (row["addr"], row["name"], row["status"], ";".join(eids), detail))

    # ---- the `ported` section (gate P ledger rows): symbols\ported.tsv + evidence + status\findings.md -------------
    ppath = os.path.join(M, "symbols", "ported.tsv")
    pcom, prows = read_tsv(ppath, PORTED_COLS)
    findings = []
    if batch.get("ported"):
        res_p = apply_ported(M, img, dis, batch, batch.get("ported", []), clusters, ghidra_funcs, fby, gby, prows, new_eid,
                             pending_evidence, findings, emit)
        accepted["ported"] = res_p["accepted"]
        rejected += res_p["rejected"]
        for k, v in res_p["per_status"].items():
            per_status["ported:" + k] = per_status.get("ported:" + k, 0) + v

    emit("SUMMARY accepted functions=%d globals=%d ported=%d findings=%d rejected=%d per_status=%s evidence=%d"
         % (len(accepted["functions"]), len(accepted["globals"]), len(accepted["ported"]), len(findings), len(rejected),
            json.dumps(per_status, sort_keys=True), len(pending_evidence)))
    if dry_run:
        emit("DRY RUN: nothing written")
    else:
        frows.sort(key=lambda r: parse_addr(r["addr"]))
        grows.sort(key=lambda r: parse_addr(r["addr"]))
        nf = write_tsv(fpath, fcom, FUNC_COLS, frows)
        ng = write_tsv(gpath, gcom, GLOB_COLS, grows)
        os.makedirs(edir, exist_ok=True)
        for eid, e in pending_evidence:
            p = os.path.join(edir, eid + ".json")
            with open(p + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(e, fh, indent=1, sort_keys=True, ensure_ascii=False)
            os.replace(p + ".tmp", p)
            json.load(open(p, encoding="utf-8"))  # readback
            ok, why = gate_enc_file(p)
            if not ok:
                raise RuntimeError(why)
        npr = None
        if batch.get("ported"):
            prows.sort(key=lambda r: (parse_addr(r["addr"]) if (r.get("addr") or "").startswith("0x") else 0xffffffff, r.get("name", "")))
            npr = write_tsv(ppath, pcom, PORTED_COLS, prows)
        if findings:
            write_findings(M, batch, findings)
        for p in (fpath, gpath) + ((ppath,) if npr is not None else ()):
            ok, why = gate_enc_file(p)
            if not ok:
                raise RuntimeError(why)
        emit("WROTE %s (%d rows) %s (%d rows)%s evidence %d files%s (G-ENC read-back: utf-8, no BOM)"
             % (fpath, nf, gpath, ng, (" %s (%d rows)" % (ppath, npr)) if npr is not None else "", len(pending_evidence),
                (" findings %d -> status/findings.md" % len(findings)) if findings else ""))
    return {"accepted": accepted, "rejected": rejected, "per_status": per_status, "findings": findings,
            "evidence_ids": [eid for eid, _ in pending_evidence], "evidence": [e for _, e in pending_evidence]}


PORTED_KINDS = ("function", "site", "global", "table", "heap-offset", "format", "shell", "method", "request", "note", "constant")
PORTED_ENTRIES = ("ported-static", "proposed", "finding", "build-shifted", "request", "note")


def apply_ported(M, img, dis, batch, rows, clusters, ghidra_funcs, fby, gby, prows, new_eid, pending_evidence, findings, emit):
    """Gate P ledger rows (FOLDIN-REPORT section 5 format). Each row: {ledger_id, addr, class, kind, name, claim, source,
    source_instance, build_tag, quote (verbatim source row, G0), entry, prior_conf, evidence[...], heap{source,key,offset}}.
      entry ported-static -> status supported for the ADDRESS (a verified ported-static item is required; semantics proposed)
      entry proposed / build-shifted -> status proposed (build-shifted: instruction address inside an aio cluster)
      entry finding -> status\\findings.md only, never a row (contradicted prior claims); request / note -> ported.tsv rows
    Every accepted row is upserted into symbols\\ported.tsv keyed by ledger id (note `ledger=<id>`) with build= and
    semantics= tags in the note; its evidence items become evidence\\E*.json with row="ported"."""
    accepted, rejected, per_status = [], [], {}
    by_ledger = {}  # (ledger id, addr, name) -> row: one ledger line can yield several rows (a table and its globals, several heap offsets)
    for p in prows:
        m = re.search(r"ledger=(L\d+)", p.get("note") or "")
        if m:
            by_ledger[(m.group(1), p.get("addr") or "", p.get("name") or "")] = p
    for row in rows:
        lid = row.get("ledger_id", "?")
        evs = row.get("evidence", [])
        try:
            if not re.match(r"^L\d{3,4}[a-z]?$", lid):   # round 2 of the fold-in starts at L109; round 3 will pass L999
                raise Reject("ledger_id %r is not L<nnn>" % lid)
            gate_build_tag(row, "ported row %s" % lid)
            for fld in ("quote", "claim", "name", "note", "finding"):
                gate_enc_text(row.get(fld, ""), "%s.%s" % (lid, fld))
            if not row.get("quote"):
                raise Reject("ported row without the verbatim source row (`quote`, G0)")
            if not row.get("source") or not row.get("source_instance"):
                raise Reject("ported row without source / source_instance (gate P)")
            if row.get("kind") not in PORTED_KINDS:
                raise Reject("kind %r not in %s" % (row.get("kind"), PORTED_KINDS))
            if row.get("entry") not in PORTED_ENTRIES:
                raise Reject("entry %r not in %s" % (row.get("entry"), PORTED_ENTRIES))
            for e in evs:
                gate_evidence_common(e)
            # address class (gate A) for rows that carry an absolute address; heap offsets never do (H6)
            a = None
            cls = row.get("class", "")
            if row.get("kind") == "heap-offset":
                if row.get("addr"):
                    raise Reject("heap-offset row carries an absolute address %s (H6: (source, key, offset) only)" % row["addr"])
                h = row.get("heap") or {}
                if not (h.get("source") and h.get("key") and h.get("offset")):
                    raise Reject("heap-offset row needs heap {source, key, offset} (H6)")
                if cls != "heap-off":
                    raise Reject("heap-offset row must carry class heap-off, got %r" % cls)
            elif cls in ("shell", "nitro", "file"):
                pass  # second-partition / foreign classes: explicit tag, no i76.exe byte test (method doc 2.1)
            elif row.get("addr"):
                a = parse_addr(row["addr"])
                actual = img.klass(a)
                want = {"text": "text", "rdata": "init", "init": "init", "data-init": "init", "bss": "bss", "data-bss": "bss", "iat": "iat"}.get(cls)
                if want is None:
                    raise Reject("class %r is not a gate-A class tag" % cls)
                if actual != want and not (want == "init" and actual == "iat"):
                    raise Reject("%s is class %s, row says %s (gate A)" % (hx(a), actual, cls))
            elif row.get("entry") in ("ported-static", "build-shifted"):
                raise Reject("entry %s needs an address" % row["entry"])
            det = []
            static_ok = False
            for e in evs:
                if e.get("kind") == "ported-static":
                    det.append(gate_p_static(img, dis, e, clusters, row.get("kind", "function")))
                    e.setdefault("semantics", "proposed")
                    static_ok = True
                d = gate_c_trap_after(dis, e, ghidra_funcs)
                if d:
                    det.append(d)
            entry = row["entry"]
            if entry == "ported-static" and not static_ok:
                raise Reject("entry ported-static without a verified ported-static evidence item (gate P fast path)")
            if entry == "ported-static" and a is not None and row.get("kind") == "site" and in_cluster(a, clusters):
                raise Reject("site %s is inside an aio patch cluster: build-shifted, not ported-static" % hx(a))
            if entry == "finding":
                if not row.get("finding"):
                    raise Reject("entry finding without the finding sentence")
                findings.append(dict(row))
                per_status["finding"] = per_status.get("finding", 0) + 1
                emit("FINDING %s %s: %s" % (lid, row.get("addr") or row.get("name") or "", row["finding"][:140]))
                continue
            status = {"ported-static": "supported", "proposed": "proposed", "build-shifted": "proposed", "request": "request", "note": "note"}[entry]
        except Reject as ex:
            rejected.append((row.get("addr"), lid, str(ex)))
            emit("REJECT ported %s %s: %s" % (lid, row.get("addr") or row.get("name"), ex)); continue
        eids = []
        for e in evs:
            eid = new_eid(); e2 = dict(e); e2["id"] = eid; e2["addr"] = row.get("addr") or ""; e2["row"] = "ported"; e2["ledger_id"] = lid
            e2.setdefault("batch", batch.get("batch")); e2.setdefault("time", time.strftime("%Y-%m-%dT%H:%M:%S"))
            e2.setdefault("build_tag", row["build_tag"])
            pending_evidence.append((eid, e2)); eids.append(eid)
        ex_name = ex_status = ""
        if a is not None:
            fr = fby.get(a); gr = gby.get(a)
            if fr is not None:
                ex_name, ex_status = fr["name"], fr["status"]
            elif gr is not None:
                ex_name, ex_status = gr["name"], gr["status"]
        heap = row.get("heap") or {}
        note = "ledger=%s;build=%s;entry=%s;semantics=proposed;prior_conf=%s;E=%s" % (
            lid, row["build_tag"], entry, row.get("prior_conf", "-"), ",".join(eids))
        if heap:
            note += ";heap=(%s,%s,%s)" % (heap["source"], heap["key"], heap["offset"])
        if row.get("note"):
            note += ";" + row["note"].replace("\t", " ").replace("\n", " ")
        sig = "ported-static" if static_ok else ("build-shifted" if entry == "build-shifted" else "-")
        pkey = (lid, row.get("addr") or "", row.get("name", ""))
        prow = by_ledger.get(pkey)
        if prow is None:
            prow = {c: "" for c in PORTED_COLS}; prows.append(prow); by_ledger[pkey] = prow
        prow.update({"addr": row.get("addr") or "", "class": row.get("class", ""), "kind": row.get("kind", ""), "name": row.get("name", ""),
                     "status": status, "source_instance": row["source_instance"], "source_status": row.get("prior_conf", "-"),
                     "sig_route": sig, "existing_name": ex_name, "existing_status": ex_status, "note": note})
        accepted.append(prow)
        per_status[status] = per_status.get(status, 0) + 1
        emit("ACCEPT ported %s %s %s [%s] %s%s" % (lid, row.get("addr") or "", row.get("name", ""), status, ";".join(eids),
                                                  (" (" + "; ".join(det) + ")") if det else ""))
    return {"accepted": accepted, "rejected": rejected, "per_status": per_status}


def write_findings(M, batch, findings):
    """status\\findings.md: contradicted prior claims (gate P item 4, method doc section 8), appended, never rows."""
    p = os.path.join(M, "status", "findings.md")
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8", newline="\n") as fh:
        if new:
            fh.write("# findings\n\nContradicted prior claims and corrections, recorded by tools/merge.py (batch `ported` rows with entry=finding;\n"
                     "method doc section 8 item 4: contradictions are logged, never resolved by seniority and never entered as rows).\n"
                     "Each finding: the verbatim source row (data, G0), the source path + build tag, the contradiction as one falsifiable\n"
                     "sentence, and the pristine-side evidence. Address classes per gate A.\n")
        fh.write("\n## batch %s (%s)\n\n" % (batch.get("batch"), time.strftime("%Y-%m-%d")))
        for f in findings:
            fh.write("### %s %s\n\n" % (f.get("ledger_id"), f.get("name") or f.get("addr") or ""))
            fh.write("- source: `%s` (build %s; prior confidence %s)\n" % (f.get("source"), f.get("build_tag"), f.get("prior_conf", "-")))
            fh.write("- quote (verbatim, data): %s\n" % f.get("quote", "").replace("\n", " "))
            fh.write("- finding: %s\n" % f.get("finding"))
            if f.get("evidence_note"):
                fh.write("- evidence: %s\n" % f["evidence_note"])
            fh.write("\n")
    ok, why = gate_enc_file(p)
    if not ok:
        raise RuntimeError(why)
    return p


# --------------------------------------------------------------------------------------------------
# Gate executables (tools\gates\gate*.py, Task 8): every merge runs them on the batch before anything is written
# --------------------------------------------------------------------------------------------------
GATE_ORDER = ["gateA_address", "gateC_counts", "gateT_types", "gateL_library", "gateK_conv", "gateN_names", "gateB_arrays",
              "gateG2_evidence", "gateG3_consistency", "gateQ_budget", "gateS_static_first", "gateP_ported", "gateR_roundtrip"]


def run_gates(M, batch_path, emit, only=None):
    """Run each tools\\gates\\gate*.py with --batch; returns (all_pass, {gate: result dict})."""
    import subprocess
    gdir = os.path.join(M, "tools", "gates")
    results = {}
    ok = True
    for g in (only or GATE_ORDER):
        script = os.path.join(gdir, g + ".py")
        if not os.path.exists(script):
            results[g] = {"verdict": "MISSING", "fails": ["%s not found" % script]}; ok = False
            emit("GATE %s MISSING" % g); continue
        p = subprocess.run([sys.executable, script, "--map", M, "--batch", batch_path, "--json"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        try:
            r = json.loads(p.stdout)
        except ValueError:
            r = {"verdict": "ERROR", "fails": [(p.stdout[-1500:] + p.stderr[-1500:]).strip()], "notes": []}
        r["exit"] = p.returncode
        results[g] = r
        if r.get("verdict") != "PASS":
            ok = False
        emit("GATE %-20s %s%s" % (g, r.get("verdict"), "" if r.get("verdict") == "PASS" else " :: " + " | ".join(r.get("fails", [])[:3])))
    return ok, results


# --------------------------------------------------------------------------------------------------
# Proposal path (Task 8): functions\<addr>.proposal.md (+ .proposal.pcode.md) + <addr>.review.md -> merge
# --------------------------------------------------------------------------------------------------
STATUS_RANK = {"proposed": 0, "supported": 1, "anchored": 2, "library": 2, "synthetic": 2}


def compose_function_md(key, name, status, data, views, g4, gates, res, review, hist_dir):
    """functions\\<addr>.md: claim, evidence, prototype, contract, blockers, gate results (the merge is its only writer)."""
    L = ["# %s (0x%x)" % (name, int(key, 16)), "",
         "status: %s | conv: %s | conv_evidence: %s | subsystem: %s" % (status, data.get("conv", "auto"), data.get("conv_evidence", "auto:paramid"),
                                                                        data.get("subsystem") or "-"),
         "merged: %s | views: %s | G4: name_agree=%s claims_agreed=%s claims_disagreed=%s" %
         (time.strftime("%Y-%m-%dT%H:%M:%S"), ",".join(views), g4.get("name_agree"), g4.get("claims_agreed"), g4.get("claims_disagreed")),
         "", "## Claim", "", "name: %s" % name, "prototype: %s" % (data.get("prototype") or "-"), "", "## Evidence", ""]
    for e in res.get("evidence", []):
        site = e.get("site") or e.get("capture_id") or ""
        L.append("- %s %s %s %s" % (e["id"], e["kind"], site, (e.get("claim") or "")[:120]))
    L += ["", "## Contract", ""]
    body = (data.get("_contract") or "").strip()
    L.append(body if body else "(none stated; the drafter's free text is data, not a contract)")
    L += ["", "## Hypotheses", ""]
    for h in data.get("hypotheses") or []:
        L.append("- hypothesis: %s" % h)
    if not data.get("hypotheses"):
        L.append("- none")
    L += ["", "## Blockers", ""]
    b = data.get("blocker")
    L.append("- %s" % b if b and b != "~" else "- none")
    dr = data.get("dynamic_request")
    if dr and dr != "~":
        L += ["", "## Dynamic request (gate S checks it statically first)", "", "- %s" % json.dumps(dr)]
    L += ["", "## Gate results", ""]
    for g, r in gates.items():
        L.append("- %s %s%s" % (g, r.get("verdict"), "" if not r.get("fails") else " :: " + "; ".join(r["fails"][:2])))
    L.append("- merge.apply_batch: accepted %d function row(s), %d global row(s), rejected %d" %
             (len(res["accepted"]["functions"]), len(res["accepted"]["globals"]), len(res["rejected"])))
    for o in (review["data"].get("overrides") or []):
        L.append("override: %s reason: %s" % (o.get("gate"), o.get("reason")))
    L += ["", "## Review", "", "verdict: %s (reviewer %s) g0: %s" % (review["data"].get("verdict"), review["front"].get("reviewer"), review["data"].get("g0")),
          "history: %s" % hist_dir.replace("\\", "/"), ""]
    return "\n".join(L)


def merge_proposal(args, M, img, dis, emit):
    import shutil
    import proposal as P
    key = P.addr_key(args.proposal)
    fdir = os.path.join(M, "functions")
    paths = {"c": os.path.join(fdir, key + ".proposal.md"), "pcode": os.path.join(fdir, key + ".proposal.pcode.md")}
    rpath = os.path.join(fdir, key + ".review.md")
    props = {}
    for v, p in paths.items():
        if os.path.exists(p):
            try:
                props[v] = P.load_proposal(p)
            except P.ProposalError as ex:
                emit("REJECT %s view %s: proposal invalid: %s" % (key, v, ex)); return 1
    if not props:
        emit("REJECT %s: no proposal files (%s)" % (key, ", ".join(paths.values()))); return 1
    for v, p in props.items():
        if p["g0"]:
            emit("REJECT %s view %s: G0 hits %s" % (key, v, p["g0"])); return 1
    review = None
    if os.path.exists(rpath) and any(os.path.getmtime(p) > os.path.getmtime(rpath) for p in paths.values() if os.path.exists(p)):
        # a review older than a proposal it judged is stale (PILOT-1 re-merge: reviewers hit the previous round's file)
        emit("REVIEW %s: %s predates a proposal file; ignored (a fresh review is needed to merge)" % (key, os.path.basename(rpath)))
    elif os.path.exists(rpath):
        try:
            review = P.load_review(rpath)
        except P.ProposalError as ex:
            emit("REJECT %s: review invalid: %s" % (key, ex)); return 1
        if review["g0"]:
            emit("REJECT %s: G0 hits in review %s" % (key, review["g0"])); return 1
    no_review = review is None and not os.path.exists(rpath)
    # the no-review refusal comes AFTER G4 (below): a key that fails G4 needs a redraft, not a review, and the
    # merge worker must be able to requeue it before any review tokens are spent (PILOT-1-REMERGE change 7)
    # G4
    views = sorted(props)
    if len(props) == 2:
        agreed, dis_claims, g4 = P.intersect(props["c"], props["pcode"])
        st = min((props["c"]["data"].get("status", "proposed"), props["pcode"]["data"].get("status", "proposed")), key=lambda s: STATUS_RANK[s])
        if props["c"]["data"].get("status") != props["pcode"]["data"].get("status") and STATUS_RANK[st] >= 2:
            st = "proposed"
        if g4.get("name_mode") == "prefix":
            canon, how = _resolve_prefix(M, g4, agreed, review)
            if canon:
                g4["name_agree"] = True; g4["name_canonical"] = canon; g4["prefix_resolved_by"] = how
                emit("G4 %s: prefix reconciled (c=%s pcode=%s) -> %s by %s" % (key, g4["name_c"], g4["name_pcode"], canon, how))
            else:
                emit("G4 %s: prefix differs (c=%s pcode=%s), words agree: %s; requeue (reviewer may add reconcile: {name: <one of the two>})" % (key, g4["name_c"], g4["name_pcode"], how))
                if not args.dry_run:
                    _queue_result(M, key, "requeue", "G4 prefix c=%s pcode=%s (%s)" % (g4["name_c"], g4["name_pcode"], how), emit, tokens=args.review_tokens)
                return 5
        elif g4.get("name_mode") == "spelling":
            emit("G4 %s: spelling reconciled (c=%s pcode=%s) -> %s" % (key, g4["name_c"], g4["name_pcode"], g4["name_canonical"]))
        if not g4["name_agree"]:
            canon, how = _resolve_synonyms(M, g4, review)
            if canon:
                g4["name_agree"] = True; g4["name_canonical"] = canon; g4["name_mode"] = "synonym"; g4["words_resolved_by"] = how
                emit("G4 %s: words reconciled (c=%s pcode=%s) -> %s by %s" % (key, g4["name_c"], g4["name_pcode"], canon, how))
        if not g4["name_agree"]:
            emit("G4 %s: names differ (c=%s pcode=%s): requeue with both views (reviewer may add reconcile: {name: <one of the two>, synonyms: true} when both name the same behaviour)" % (key, g4["name_c"], g4["name_pcode"]))
            if not args.dry_run:
                _queue_result(M, key, "requeue", "G4 name disagreement c=%s pcode=%s" % (g4["name_c"], g4["name_pcode"]), emit, tokens=args.review_tokens)
            return 5
        if no_review and not args.dry_run:
            emit("REFUSE %s: no review file %s (the reviewer runs `merge.py --proposal %s --dry-run` and writes it)" % (key, rpath, key)); return 4
        data = dict(props["c"]["data"]); data["_contract"] = _first_paragraph(props["c"]["body"])
        if g4.get("name_mode") == "synonym":
            # intersect() put the two name claims in the disagreements; a reconciled pair is one agreed claim with the
            # union of both views' evidence (g4 reviewers found the reconcile otherwise merged NOTHING)
            for d in [d for d in dis_claims if d["key"] and d["key"][0] == "name"]:
                src = [c for v in ("c", "pcode") for c in (props[v]["data"].get("claims") or []) if c["claim"] == "name"]
                if len(src) == 2:
                    m = dict(src[0]); m["value"] = g4["name_canonical"]
                    seen, evs = set(), []
                    for e in list(src[0].get("evidence") or []) + list(src[1].get("evidence") or []):
                        k = json.dumps(e, sort_keys=True)
                        if k not in seen:
                            seen.add(k); evs.append(e)
                    m["evidence"] = evs
                    agreed.append(m); dis_claims.remove(d)
        if g4.get("name_canonical") and data.get("name") not in ("keep", None):
            data["name"] = g4["name_canonical"]
            for c in agreed:
                if c["claim"] == "name":
                    c["value"] = g4["name_canonical"]
            if g4.get("name_mode") == "prefix":
                # the subsystem claim follows the resolved prefix when one view claimed exactly it
                sub_dis = [d for d in dis_claims if d["key"] == ["subsystem"]]
                pref = g4["name_canonical"].split("_", 1)[0]
                for d in sub_dis:
                    side = "c" if d["c"] == pref else ("pcode" if d["pcode"] == pref else None)
                    if side:
                        src = [c for c in (props[side]["data"].get("claims") or []) if c["claim"] == "subsystem"]
                        if src:
                            agreed.append(dict(src[0])); dis_claims.remove(d)
                            emit("G4 %s: subsystem %s taken from the %s view (matches the resolved prefix)" % (key, pref, side))
        if props["pcode"]["data"].get("conv", "auto") != props["c"]["data"].get("conv", "auto"):
            data["conv"] = "auto"; data["conv_evidence"] = "auto:paramid"
    else:
        v = views[0]
        if not args.single_view:
            emit("WAIT %s: only the %s view is drafted; G4 needs both (or --single-view to record G4 as not applied)" % (key, v)); return 6
        if no_review and not args.dry_run:
            emit("REFUSE %s: no review file %s (the reviewer runs `merge.py --proposal %s --dry-run` and writes it)" % (key, rpath, key)); return 4
        agreed = props[v]["data"].get("claims") or []; dis_claims = []
        g4 = {"name_agree": None, "claims_agreed": len(agreed), "claims_disagreed": 0, "single_view": v}
        st = props[v]["data"].get("status", "proposed")
        data = dict(props[v]["data"]); data["_contract"] = _first_paragraph(props[v]["body"])
    for d in dis_claims:
        emit("G4 %s: disagreement %s (c=%s pcode=%s): dropped" % (key, d["key"], d["c"], d["pcode"]))
    # review verdicts per claim
    if review:
        stale = False
        if (review["data"]["verdict"] == "requeue" and g4.get("name_agree") and g4.get("name_mode") in ("spelling", "prefix")
                and G4_STALE_RE.search(str(review["data"].get("blocker") or ""))):
            stale = True
            emit("REVIEW %s: requeue verdict was the G4 name disagreement (%s / %s), superseded by the normalised G4 -> %s; per-claim verdicts applied, G4-spelling rejects ignored" %
                 (key, g4["name_c"], g4["name_pcode"], g4.get("name_canonical")))
        if review["data"]["verdict"] != "accept" and not stale:
            emit("REVIEW %s: verdict %s%s" % (key, review["data"]["verdict"], (": " + str(review["data"].get("blocker"))) if review["data"].get("blocker") else ""))
            if not args.dry_run:
                _queue_result(M, key, "requeue" if review["data"]["verdict"] == "requeue" else "rejected", review["data"].get("blocker") or "reviewer verdict", emit, tokens=args.review_tokens)
            return 7
        rej = {(c.get("claim"), str(c.get("value"))) for c in (review["data"].get("claims") or [])
               if c.get("verdict") == "reject" and not (stale and G4_STALE_RE.search(str(c.get("reason") or "")))}
        if rej:
            def _hit(c):
                if c["claim"] == "param":
                    return any(t == "param" and P.param_type(v) == P.param_type(c["value"]) for (t, v) in rej)
                if c["claim"] in ("name", "global"):
                    return any(t == c["claim"] and P.norm_name(v) == P.norm_name(c["value"]) for (t, v) in rej)
                return (c["claim"], str(c["value"])) in rej
            agreed = [c for c in agreed if not _hit(c)]
            emit("REVIEW %s: %d claim(s) rejected by the reviewer" % (key, len(rej)))
            if any(c[0] == "name" for c in rej):
                data["name"] = "keep"
    tokens = sum(int(p["front"].get("tokens_used", 0)) for p in props.values())
    batch_name = "proposal-%s-%s" % (key, time.strftime("%Y%m%dT%H%M%S"))
    batch, grows = P.to_batch(key, agreed, st, data, batch_name, views)
    if batch is None:
        batch = {"batch": batch_name, "author": "merge --proposal", "functions": [], "globals": grows}
    if not batch["functions"] and not batch["globals"]:
        emit("NOTHING %s: no accepted claim survives G4/review (name keep, no globals)" % key)
        if not args.dry_run:
            _queue_result(M, key, "requeue", "no claim survived G4/review", emit)
        return 8
    import tempfile
    bdir = tempfile.gettempdir() if args.dry_run else os.path.join(M, "status", "tasks")
    bpath = os.path.join(bdir, batch_name + ".batch.json")
    with open(bpath, "w", encoding="utf-8") as fh:
        json.dump(batch, fh, indent=1, default=str)
    emit("BATCH %s -> %s (%d function row(s), %d global row(s), status %s, views %s, tokens %d)" %
         (key, bpath, len(batch["functions"]), len(batch["globals"]), st, ",".join(views), tokens))
    ok, gates = run_gates(M, bpath, emit)
    if not ok:
        emit("REJECT %s: gate failure; nothing written" % key)
        if not args.dry_run:
            _queue_result(M, key, "requeue", "gates: " + "; ".join("%s: %s" % (g, r["fails"][0]) for g, r in gates.items() if r.get("fails")), emit)
        return 9
    res = apply_batch(M, img, dis, batch, args.dry_run, emit)
    if res["rejected"]:
        emit("REJECT %s: merge gates rejected %d row(s); nothing written" % (key, len(res["rejected"])))
        if not args.dry_run:
            _queue_result(M, key, "requeue", "merge: " + "; ".join(r[2] for r in res["rejected"]), emit)
        return 10
    if args.dry_run:
        emit("DRY RUN %s: proposal pipeline green (G0 ok, G4 %s, gates %s, %d row(s) would be written)" %
             (key, json.dumps(g4), "PASS", len(res["accepted"]["functions"]) + len(res["accepted"]["globals"])))
        return 0
    # write functions\<addr>.md, archive the proposals and review, log, release the queue item
    name = batch["functions"][0]["name"] if batch["functions"] else data.get("name", "keep")
    hist = os.path.join(fdir, "history", key)
    os.makedirs(hist, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    moved = []
    for p in list(paths.values()) + [rpath]:
        if os.path.exists(p):
            dst = os.path.join(hist, stamp + "-" + os.path.basename(p))
            shutil.move(p, dst); moved.append(dst)
    md = compose_function_md(key, name, st, data, views, g4, gates, res, review, hist)
    mpath = os.path.join(fdir, key + ".md")
    with open(mpath + ".tmp", "w", encoding="utf-8") as fh:
        fh.write(md)
    os.replace(mpath + ".tmp", mpath)
    if open(mpath, encoding="utf-8").read() != md:
        raise RuntimeError("readback of %s differs" % mpath)
    with open(os.path.join(M, "status", "merge-log.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "key": key, "name": name, "status": st, "views": views,
                             "accepted": len(res["accepted"]["functions"]) + len(res["accepted"]["globals"]), "tokens": tokens,
                             "evidence_ids": res["evidence_ids"], "batch": bpath, "md": mpath, "history": moved,
                             "review_tokens": args.review_tokens, "g4": g4}) + "\n")
    _queue_result(M, key, "accepted", None, emit, tokens=args.review_tokens)
    emit("MERGED %s %s [%s] -> %s (+%d evidence, history %s)" % (key, name, st, mpath, len(res["evidence_ids"]), hist))
    return 0


G4_STALE_RE = re.compile(r"\bG4\b|spelling|align on requeue|not in the intersection|no winner picked|differs from (the )?(c|pcode) view|name(s)? differ|intersection (contains|is) (no|empty)", re.I)


def _resolve_synonyms(M, g4, review):
    """G4 word disagreement (added 2026-09-26). Requeued synonym pairs did not converge: g3 redrafts came back with the
    two names swapped (Find/Scan, MciClose/CloseCdAudio). Both names are independent readings, so a reviewer may break
    the tie with reconcile: {name: X, synonyms: true} when X is exactly one of the two proposed names (never a third
    word), neither is `keep`, and the prefixes agree after vocabulary folding. Returns (name or None, how)."""
    import proposal as P
    if not (review and isinstance(review["data"].get("reconcile"), dict) and review["data"]["reconcile"].get("synonyms")):
        return None, "no synonym reconcile"
    x = str(review["data"]["reconcile"].get("name", ""))
    nc, npc = g4["name_c"], g4["name_pcode"]
    if "keep" in (nc, npc):
        return None, "one view kept the default name"
    if P.norm_name(x) not in (P.norm_name(nc), P.norm_name(npc)):
        return None, "reconcile name %r is neither proposed name" % x
    try:
        voc = json.load(open(os.path.join(M, "subsystems", "vocabulary.json"), encoding="utf-8"))
    except (OSError, ValueError):
        voc = {}
    fold = lambda p: voc.get(p.lower()) or voc.get(p) or p
    pc, pp = P.split_prefix(nc)[0], P.split_prefix(npc)[0]
    if fold(pc) != fold(pp):
        return None, "prefixes differ (%s / %s)" % (pc, pp)
    return (nc if P.norm_name(x) == P.norm_name(nc) else npc), "reviewer synonym reconcile"


def _resolve_prefix(M, g4, agreed, review):
    """G4 prefix mode: both views agree on the words after the prefix. The prefix comes from (1) the reviewer's
    reconcile: {name: X} when X is one of the two proposed spellings, (2) subsystems\\vocabulary.json when both
    prefixes fold into one canonical prefix, (3) an agreed subsystem claim equal to one view's prefix.
    Returns (canonical name or None, how)."""
    import proposal as P
    pc, pp = g4["prefix_c"], g4["prefix_pcode"]
    canonical_words = None
    for n in (g4["name_c"], g4["name_pcode"]):
        if P.NAME_STYLE_RE.match(n):
            canonical_words = P.split_prefix(n)[1]
    words = canonical_words or P.split_prefix(g4["name_c"])[1]
    if review and isinstance(review["data"].get("reconcile"), dict):
        x = str(review["data"]["reconcile"].get("name", ""))
        if P.norm_name(x) in (P.norm_name(g4["name_c"]), P.norm_name(g4["name_pcode"])):
            return "%s_%s" % (P.split_prefix(x)[0], words), "reviewer reconcile"
        return None, "reconcile name %r is neither proposed spelling" % x
    try:
        voc = json.load(open(os.path.join(M, "subsystems", "vocabulary.json"), encoding="utf-8"))
    except (OSError, ValueError):
        voc = {}
    a, b = voc.get(pc.lower()) or voc.get(pc), voc.get(pp.lower()) or voc.get(pp)
    if a and b and a == b:
        return "%s_%s" % (a, words), "vocabulary (%s, %s -> %s)" % (pc, pp, a)
    if (not pc) != (not pp) and (a or b):
        # one view gave no prefix (no opinion), the other's folds to a vocabulary prefix
        return "%s_%s" % (a or b, words), "vocabulary (%s / no prefix -> %s)" % (pc or pp, a or b)
    sub = [c for c in agreed if c["claim"] == "subsystem"]
    if sub and str(sub[0]["value"]) in (pc, pp):
        return "%s_%s" % (sub[0]["value"], words), "agreed subsystem claim"
    return None, "prefixes %s / %s do not fold to one vocabulary prefix (%s / %s) and no subsystem claim agrees" % (pc, pp, a, b)


def _first_paragraph(body):
    body = re.sub(r"```yaml.*?```", "", body, flags=re.S)
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip() and not p.strip().startswith("#")]
    return paras[0] if paras else ""


def _queue_result(M, key, result, reason, emit, tokens=0):
    try:
        import lease
        with lease.Queue(M) as Q:
            if key in Q.by_key:
                it = Q.merge_result(key, result, reason, tokens)
                emit("QUEUE %s -> %s" % (key, it["status"]))
            else:
                emit("QUEUE %s: not in queue.json (nothing to release)" % key)
    except Exception as ex:
        emit("QUEUE %s: update failed: %s" % (key, ex))


# --------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", nargs="?", default=None, help="batch JSON (tool batches); omit with --proposal")
    ap.add_argument("--map", default=r"C:\Users\james\i76-map")
    ap.add_argument("--exe", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--log", default=None)
    ap.add_argument("--gates", action="store_true", help="batch mode: run tools\\gates\\gate*.py on the batch before writing (always on for --proposal)")
    ap.add_argument("--proposal", default=None, metavar="ADDR",
                    help="merge functions\\<addr>.proposal.md (+ .proposal.pcode.md) with <addr>.review.md through G0/G4 + all gates")
    ap.add_argument("--single-view", action="store_true", help="with --proposal: allow a merge from one view (G4 recorded as not applied)")
    ap.add_argument("--review-tokens", type=int, default=0, help="with --proposal: the reviewer's token count, added to the queue item on release (drafts are counted at their own release)")
    ap.add_argument("--refresh-sizes", action="store_true",
                    help="after a DumpAll re-export: copy Ghidra's body size (functions.json) into functions.tsv for rows whose size differs "
                         "(rows created by ApplyMap carry a capstone estimate until then); the batch argument is ignored")
    args = ap.parse_args()
    M = args.map
    log = []

    def emit(s):
        log.append(s); print(s)

    if args.refresh_sizes:
        fpath = os.path.join(M, "symbols", "functions.tsv")
        fcom, frows = read_tsv(fpath, FUNC_COLS)
        fj = {"0x%x" % int(r["addr"], 16): r for r in json.load(open(os.path.join(M, "ghidra", "export", "functions.json"), encoding="utf-8"))}
        n = 0
        for r in frows:
            g = fj.get(r["addr"])
            if g is not None and str(g["size"]) != r["size"]:
                print("size %s %s: %s -> %d (Ghidra body, method: FunctionManager body.getNumAddresses)" % (r["addr"], r["name"], r["size"], g["size"]))
                r["size"] = str(g["size"]); n += 1
        if n:
            write_tsv(fpath, fcom, FUNC_COLS, frows)
        print("refreshed %d sizes" % n)
        return 0
    exe = args.exe or os.path.join(M, "ghidra", "i76_ref.exe")
    img = Image(exe)
    if img.md5 != PRISTINE_MD5:
        print("REFUSE: %s md5 %s is not the pristine %s (H0)" % (exe, img.md5, PRISTINE_MD5)); sys.exit(2)
    dis = Disasm(img)
    try:
        if args.proposal:
            return merge_proposal(args, M, img, dis, emit)
        if not args.batch:
            ap.error("a batch JSON or --proposal ADDR is required")
        ok, why = gate_enc_file(args.batch)
        if not ok:
            emit("REJECT batch %s: %s" % (args.batch, why)); return 3
        emit("G-ENC batch %s: %s" % (args.batch, why))
        batch = json.load(open(args.batch, encoding="utf-8"))
        if args.gates:
            ok, _ = run_gates(M, args.batch, emit)
            if not ok:
                emit("REJECT batch %s: gate failure; nothing written" % args.batch); return 9
        res = apply_batch(M, img, dis, batch, args.dry_run, emit)
        return 0 if not res["rejected"] else 1
    finally:
        if args.log:
            with open(args.log, "w", encoding="utf-8") as fh:
                fh.write("\n".join(log) + "\n")


if __name__ == "__main__":
    sys.exit(main())
