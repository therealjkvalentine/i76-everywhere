#!/usr/bin/env python3
r"""test_proposal_g4.py - offline tests for the G4 comparison helpers of tools\proposal.py (param_type,
norm_name, split_prefix, canonical_spelling) and for intersect()'s param rule.

    python tools\tests\test_proposal_g4.py

Nothing is written under functions\, symbols\, evidence\ or status\: the real-data case copies an archived
proposal pair out of functions\history\ into a scratch directory (load_proposal validates the file name) and
only reads it. Every check prints its measured value; exit 0 only if all pass.

Why param_type exists: subsystems\VOCABULARY.md makes the G4 key for a param claim (index, type) and leaves the
identifier free text, so 'FILE *log' (view c) and 'FILE *fp' (view pcode) must intersect. The first version's
regex required whitespace before the identifier and so returned 'FILE *fp' unchanged for the map's own
canonical pointer spelling, and every pointer param was dropped as a disagreement.
"""
import glob
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, ".."))
MAP = os.path.abspath(os.path.join(TOOLS, ".."))
sys.path.insert(0, TOOLS)
import proposal as P  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


def view(name, claims, status="supported"):
    """the shape intersect() reads: {"data": {name, status, claims:[{claim, value, index?, evidence}]}}"""
    for c in claims:
        c.setdefault("evidence", [])
    return {"data": {"name": name, "status": status, "claims": claims}}


def main():
    # 1. param_type: pointer spellings reduce to the type with the stars kept and normalised
    for value, want in [("FILE *fp", "FILE *"), ("FILE * fp", "FILE *"), ("FILE*fp", "FILE *"),
                        ("const char *path", "const char *"), ("unsigned char *palette768", "unsigned char *"),
                        ("char **argv", "char **"), ("I76_WorldCtx *obj", "I76_WorldCtx *")]:
        got = P.param_type(value)
        check("param_type(%r) == %r" % (value, want), got == want, "got %r" % got)

    # 2. param_type: the cases that must not change (bare types, no pointer, an array suffix it cannot parse)
    for value, want in [("int", "int"), ("uint32_t miscCaps", "uint32_t"), ("float amount", "float"),
                        ("FILE *", "FILE *"), ("int *", "int *"), ("unsigned int", "unsigned int"),
                        ("uint32_t audio_rate[7]", "uint32_t audio_rate[7]"), ("", "")]:
        got = P.param_type(value)
        check("param_type(%r) == %r" % (value, want), got == want, "got %r" % got)

    # 3. intersect(): two views whose param claims differ only in the identifier agree; a real type difference does not
    a = view("renderer_PrintMiscCaps", [{"claim": "param", "index": 1, "value": "FILE *log"},
                                        {"claim": "param", "index": 2, "value": "uint32_t miscCaps"},
                                        {"claim": "param", "index": 3, "value": "int flags"}])
    b = view("renderer_PrintMiscCaps", [{"claim": "param", "index": 1, "value": "FILE *fp"},
                                        {"claim": "param", "index": 2, "value": "uint32_t misc_caps"},
                                        {"claim": "param", "index": 3, "value": "float flags"}])
    agreed, dis, g4 = P.intersect(a, b)
    idx = sorted(c["index"] for c in agreed if c["claim"] == "param")
    check("intersect: params 1 and 2 agree on type alone", idx == [1, 2], "agreed param indexes %s" % idx)
    check("intersect: param 3 (int vs float) stays a disagreement",
          any(d["key"] == ["param", "3"] for d in dis), "disagreements %s" % [d["key"] for d in dis])
    check("intersect: the agreed param keeps the c view's spelling",
          [c["value"] for c in agreed if c["claim"] == "param" and c["index"] == 1] == ["FILE *log"],
          "%s" % [c["value"] for c in agreed if c["claim"] == "param"])

    # 4. the name helpers G4 leans on (unchanged by this fix, checked so the amendment stays covered)
    check("norm_name: spelling only", P.norm_name("pcx_ReadPalette") == P.norm_name("pcx_read_palette"))
    check("canonical_spelling prefers prefix_CamelCase",
          P.canonical_spelling("pcx_read_palette", "pcx_ReadPalette") == "pcx_ReadPalette")
    check("split_prefix splits at the first underscore", P.split_prefix("videolog_print_shade_caps") == ("videolog", "print_shade_caps"))

    # 5. real data: the archived 00432690 pair (the batch this fix came from), read-only through a scratch copy
    hist = sorted(glob.glob(os.path.join(MAP, "functions", "history", "00432690", "*-00432690.proposal.md")))
    if hist:
        tmp = tempfile.mkdtemp(prefix="test-proposal-g4-")
        try:
            shutil.copy(hist[-1], os.path.join(tmp, "00432690.proposal.md"))
            shutil.copy(hist[-1].replace(".proposal.md", ".proposal.pcode.md"), os.path.join(tmp, "00432690.proposal.pcode.md"))
            pc = P.load_proposal(os.path.join(tmp, "00432690.proposal.md"))
            pp = P.load_proposal(os.path.join(tmp, "00432690.proposal.pcode.md"))
            agreed, dis, g4 = P.intersect(pc, pp)
            params = sorted(c["index"] for c in agreed if c["claim"] == "param")
            check("00432690 (archived): both param claims intersect (was: both dropped)", params == [1, 2],
                  "c=%s pcode=%s -> agreed %s, disagreements %s"
                  % ([c["value"] for c in pc["data"]["claims"] if c["claim"] == "param"],
                     [c["value"] for c in pp["data"]["claims"] if c["claim"] == "param"],
                     params, [d["key"] for d in dis]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("SKIP 00432690 archived pair not present (functions\\history\\00432690)")

    failed = [n for n, ok in results if not ok]
    print("\n%d checks, %d failed%s" % (len(results), len(failed), (": " + ", ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
