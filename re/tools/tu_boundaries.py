#!/usr/bin/env python3
r"""tu_boundaries.py (Task 5, Phase 0) - cluster .text functions into translation-unit
neighbourhoods and write symbols\modules.tsv.

Two levels of evidence, both measured on this binary (funnel printed and stored in the
file header; numbers in status\tasks\t5-evidence-supply.md):

  Level 1, packaging (evidence class `int3-fill`): 2,150 of 2,207 function starts are
  16-aligned.  The compiler pads between the functions of one object with `nop` runs
  (1,790 gaps) and pads the object's .text to 16 as well, so an object boundary inside
  the game's own code leaves no fill at all.  `int3` (0xCC) fill is the linker's, and it
  appears only between COMDAT-packaged functions (/Gy objects: 0x41c1ca-0x41f8e0, the
  CRT/library tail).  An int3 run therefore separates *packaging units*, not TUs of the
  game core (the first version of this tool assumed otherwise and produced one
  1,745-function block plus 63 one-function blocks: the null that refuted it).

  Level 2, literal neighbourhood (evidence class `literal-gap`): string literals are
  emitted into the object's .data contribution in first-use order and contributions sit in
  link order, so the literal addresses referenced by successive functions rise with the
  function address (382 functions reference .data literals; 43 back-jumps, all shared
  literals).  Identical literals ARE pooled by the linker (17 literals are referenced by
  functions more than 64 KB apart, e.g. "Interstate '76 Gold Edition" over 718 KB), so a
  shared literal is not per-object evidence; those are excluded.  Each function owns the
  interval of its remaining literals; walking in address order, a function whose interval
  starts more than GAP_THRESHOLD bytes of .data past the neighbourhood's highest literal
  opens a new neighbourhood (evidence: the two addresses and the distance).  A first
  version keyed on literal *runs* with back-reference merging collapsed into one
  1,699-function block (runs straddle objects; pooled literals merge everything): the null
  that led to this form.  Functions without literals stay with the neighbourhood they sit
  in (`unlinked`).  Level-2 boundaries are `proposed`: an object's own initialised globals
  also separate its literal blocks, so this over-segments; the threshold sensitivity
  (64..4096 B) is printed and stored in the file header.

Every boundary carries its evidence (`int3-run@va len N` with the bytes re-read from the
pristine file; `literal-run-skip ...`; `section-start`), every count its method.  Writes
symbols\modules.tsv and a JSON side file and reads both back.

Usage: python tools\tu_boundaries.py [--exe PATH] [--export DIR] [--out symbols\modules.tsv]
"""
import argparse
import csv
import json
import os
import sys
from collections import OrderedDict, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_tables import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_EXE = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"
EXPECTED_MD5 = "9a232dcc2c164648cff20c414c1f9698"
RUN_GAP = 4  # bytes: literals closer than this (alignment padding) belong to one run (report only)
POOL_SPAN = 65536  # a literal whose referencing functions span more .text than this is linker-pooled, not per-object
GAP_THRESHOLD = 256  # bytes of .data between two functions' literal intervals that opens a new neighbourhood (sensitivity in funnel)


def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        hdr = None
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = parts
                continue
            rows.append(dict(zip(hdr, parts)))
    return rows


def load_functions(export):
    fs = []
    with open(os.path.join(export, "functions.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            fs.append(OrderedDict(addr=int(r["address"], 16), size=int(r["size"]), name=r["name"]))
    fs.sort(key=lambda f: f["addr"])
    return fs


def pad_kind(img, start, end):
    """Classify the bytes [start,end) from the pristine file: int3 | nop | zero | mixed."""
    off = img.va2off(start)
    b = img.data[off:off + (end - start)]
    if not b:
        return "empty"
    if all(x == 0xCC for x in b):
        return "int3"
    if all(x == 0x00 for x in b):
        return "zero"
    # multi-byte nops: 90, 8D 40 00, 8D 49 00, 8D 64 24 00, 8D 9B 00 00 00 00, 8D A4 24 00 00 00 00 ...
    if all(x in (0x90, 0x8D, 0x40, 0x49, 0x64, 0x24, 0x00, 0x9B, 0xA4, 0x76, 0x74, 0xB6, 0xBF) for x in b):
        return "nop"
    return "mixed"


def literal_runs(img, strings_rows):
    """Runs of consecutive literals per section (method: strings.tsv addr/len, gap <= RUN_GAP)."""
    lits = sorted((int(r["addr"], 16), int(r["len"]), r["section"], r) for r in strings_rows
                  if r["section"] in (".data", ".rdata"))
    runs = []
    cur = None
    for a, l, sec, r in lits:
        end = a + l + 1
        if cur and sec == cur["sec"] and a - cur["end"] <= RUN_GAP:
            cur["end"] = end
            cur["items"].append(r)
        else:
            cur = OrderedDict(start=a, end=end, sec=sec, items=[r])
            runs.append(cur)
    for i, r in enumerate(runs):
        r["idx"] = i
    frun = defaultdict(set)  # function -> run indices (capstone imm32 method)
    for r in runs:
        for it in r["items"]:
            for fn in it["imm32_functions"].split(";"):
                if fn:
                    frun[int(fn, 16)].add(r["idx"])
    return runs, frun


def level1(img, fs):
    """Packaging spans: split at int3 fill. Returns list of spans (lists of functions) with evidence + gap notes."""
    spans = []
    cur = None
    kinds = defaultdict(int)
    prev_end = img.text_lo
    for f in fs:
        a = f["addr"]
        gap = (prev_end, a) if a > prev_end else None
        ev = None
        note = None
        if cur is None:
            ev = "section-start@0x%x" % img.text_lo
        elif gap:
            k = pad_kind(img, gap[0], gap[1])
            kinds[k] += 1
            if k == "int3":
                ev = "int3-run@0x%x len %d (bytes re-read: all 0xCC)" % (gap[0], gap[1] - gap[0])
            elif k in ("mixed", "zero") and (gap[1] - gap[0]) >= 16:
                note = "%s-gap@0x%x len %d" % (k, gap[0], gap[1] - gap[0])
        if ev:
            cur = OrderedDict(evidence=ev, functions=[], notes=[])
            spans.append(cur)
        if note:
            cur["notes"].append(note)
        cur["functions"].append(f)
        prev_end = max(prev_end, a + f["size"])
    return spans, dict(kinds)


def level2(span, runs, frun, img, flit, pooled, gap_threshold):
    """Split one packaging span into literal neighbourhoods by .data distance between literal intervals.

    Each function owns the interval [min, max] of the .data literals it references (pooled literals
    excluded).  Walking in address order, a function whose interval starts more than `gap_threshold`
    bytes past the neighbourhood's highest literal opens a new neighbourhood (evidence: the .data
    distance).  Literal-less functions stay with the neighbourhood they sit in (`unlinked`).
    Run indices are kept for the report only."""
    clusters = []
    cur = None
    links = {}
    for f in span["functions"]:
        a = f["addr"]
        L = sorted(x for x in flit.get(a, ()) if x not in pooled)
        R = sorted(r for r in frun.get(a, ()) if runs[r]["sec"] == ".data")
        if cur is None:
            cur = OrderedDict(functions=[f], runs=set(R), lit_lo=(L[0] if L else None), lit_hi=(L[-1] if L else None),
                              evidence=span["evidence"], level="packaging", merges=[])
            clusters.append(cur)
            links[a] = "first" if L else "unlinked"
            continue
        if not L:
            cur["functions"].append(f)
            links[a] = "unlinked"
            continue
        if cur["lit_hi"] is None:
            cur["functions"].append(f)
            cur["runs"].update(R)
            cur["lit_lo"], cur["lit_hi"] = L[0], L[-1]
            links[a] = "first-literal 0x%x" % L[0]
            continue
        if L[0] <= cur["lit_hi"] + gap_threshold:
            links[a] = ("within-interval 0x%x" % L[0]) if L[0] <= cur["lit_hi"] else "adjacent-literal 0x%x (+%d B)" % (L[0], L[0] - cur["lit_hi"])
            cur["functions"].append(f)
            cur["runs"].update(R)
            cur["lit_hi"] = max(cur["lit_hi"], L[-1])
            continue
        dist = L[0] - cur["lit_hi"]
        ev = "literal-gap: previous neighbourhood's last literal 0x%x -> this function's first literal 0x%x, %d B of .data between (> %d B threshold)" % (
            cur["lit_hi"], L[0], dist, gap_threshold)
        cur = OrderedDict(functions=[f], runs=set(R), lit_lo=L[0], lit_hi=L[-1], evidence=ev, level="literal-gap", merges=[])
        clusters.append(cur)
        links[a] = "opens 0x%x" % L[0]
    for c in clusters:
        c["notes"] = list(span["notes"]) if c is clusters[0] else []
    return clusters, links


def build(img, fs, strings_rows, names):
    funnel = OrderedDict()
    runs, frun = literal_runs(img, strings_rows)
    funnel["literals (.data+.rdata, strings.tsv)"] = sum(len(r["items"]) for r in runs)
    funnel["literal runs (gap <= %d B)" % RUN_GAP] = len(runs)
    funnel["  .data runs"] = sum(1 for r in runs if r["sec"] == ".data")
    funnel["functions with .data literal refs (capstone imm32)"] = sum(
        1 for a, s in frun.items() if any(runs[r]["sec"] == ".data" for r in s))
    # per-function .data literal addresses and the pooled set (identical literals merged by the linker, /GF)
    flit = defaultdict(set)
    lit_fns = defaultdict(set)
    for r in strings_rows:
        if r["section"] != ".data":
            continue
        va = int(r["addr"], 16)
        for fn in r["imm32_functions"].split(";"):
            if fn:
                flit[int(fn, 16)].add(va)
                lit_fns[va].add(int(fn, 16))
    pooled = {va for va, s in lit_fns.items() if max(s) - min(s) > POOL_SPAN}
    funnel["literals referenced by > 1 function"] = sum(1 for s in lit_fns.values() if len(s) > 1)
    funnel["  pooled (referencing functions span > %d B of .text; excluded from linking)" % POOL_SPAN] = len(pooled)
    spans, kinds = level1(img, fs)
    funnel["inter-function gap kinds (pristine bytes)"] = kinds
    funnel["level-1 packaging spans (int3 fill)"] = len(spans)
    sens = OrderedDict()
    for g in (64, 128, 256, 512, 1024, 4096):
        n = 0
        for sp in spans:
            n += len(level2(sp, runs, frun, img, flit, pooled, g)[0])
        sens[str(g)] = n
    funnel["neighbourhood count vs .data gap threshold (B)"] = sens
    funnel["gap threshold used (B)"] = GAP_THRESHOLD
    modules = []
    links = {}
    for sp in spans:
        cl, lk = level2(sp, runs, frun, img, flit, pooled, GAP_THRESHOLD)
        modules.extend(cl)
        links.update(lk)
    funnel["level-2 neighbourhoods"] = len(modules)
    funnel["  opened by literal-gap"] = sum(1 for m in modules if m["level"] == "literal-gap")
    lk = defaultdict(int)
    for v in links.values():
        lk[v.split(" ")[0]] += 1
    funnel["function link kinds"] = dict(lk)
    for m in modules:
        m["start"] = m["functions"][0]["addr"]
        m["end"] = max(f["addr"] + f["size"] for f in m["functions"])
        lits = sorted(set(x for r in m["runs"] for x in (runs[r]["start"],)))
        m["strings_lo"] = runs[min(m["runs"])]["start"] if m["runs"] else None
        m["strings_hi"] = runs[max(m["runs"])]["end"] if m["runs"] else None
        m["n_runs"] = len(m["runs"])
        m["n_literals"] = sum(len(runs[r]["items"]) for r in m["runs"])
        m["n_unlinked"] = sum(1 for f in m["functions"] if links[f["addr"]] == "unlinked")
    # ordering check across consecutive neighbourhoods with literals
    ordered = overl = checked = 0
    for a, b in zip(modules, modules[1:]):
        if a["runs"] and b["runs"]:
            checked += 1
            if max(a["runs"]) < min(b["runs"]):
                ordered += 1
                b["string_check"] = "ordered"
            else:
                overl += 1
                b["string_check"] = "overlap"
        else:
            b["string_check"] = "n/a"
    modules[0]["string_check"] = "first"
    funnel["consecutive neighbourhoods both with literals"] = checked
    funnel["  ordered"] = ordered
    funnel["  overlapping run indices (a run can straddle two neighbourhoods; report only)"] = overl
    sizes = sorted(len(m["functions"]) for m in modules)
    funnel["functions per neighbourhood min/median/max"] = [sizes[0], sizes[len(sizes) // 2], sizes[-1]]
    funnel["neighbourhoods with >= 2 functions"] = sum(1 for s in sizes if s >= 2)
    return modules, links, runs, funnel


def hint_for(m, names):
    named = [names[f["addr"]][0] for f in m["functions"] if f["addr"] in names and not names[f["addr"]][0].startswith("FUN_")]
    return ";".join(named[:6]) + (";..." if len(named) > 6 else "")


def write(modules, links, funnel, img, names, out, out_json):
    hdr = ["module", "start", "end", "size", "class", "level", "status", "n_functions", "function_bytes", "n_unlinked",
           "boundary_evidence", "string_check", "strings_lo", "strings_hi", "n_runs", "n_literals", "named_functions", "notes", "functions"]
    lines = ["# modules.tsv - translation-unit neighbourhoods of .text (tools/tu_boundaries.py, Task 5). class text (.text VA); md5 %s" % img.md5,
             "# level: packaging = opened by int3 linker fill (bytes re-read from the pristine file) or the section start; literal-gap = opened by a .data distance > %d B between literal intervals (proposed; over-segments objects; pooled literals excluded)" % GAP_THRESHOLD,
             "# string_check vs the previous row: ordered = this row's .data literal runs all lie after the previous row's; n/a = a side has no literal",
             "# n_functions: ghidra/export/functions.csv; function_bytes = sum of Ghidra body sizes; n_unlinked = functions with no .data literal, placed by address adjacency only",
             "# strings_lo/hi: first/last byte of the .data literal runs this neighbourhood references (method: capstone imm32 sites from strings.tsv, runs with gap <= %d B)" % RUN_GAP,
             "# funnel: " + json.dumps(funnel),
             "\t".join(hdr)]
    for i, m in enumerate(modules, 1):
        fb = sum(f["size"] for f in m["functions"])
        notes = list(m["notes"]) + m["merges"]
        row = [str(i), "0x%x" % m["start"], "0x%x" % m["end"], str(m["end"] - m["start"]), "text", m["level"],
               "supported" if m["level"] == "packaging" else "proposed",
               str(len(m["functions"])), str(fb), str(m["n_unlinked"]), m["evidence"], m.get("string_check", ""),
               ("0x%x" % m["strings_lo"]) if m["strings_lo"] else "", ("0x%x" % m["strings_hi"]) if m["strings_hi"] else "",
               str(m["n_runs"]), str(m["n_literals"]), hint_for(m, names), ";".join(notes),
               ";".join("0x%x" % f["addr"] for f in m["functions"])]
        lines.append("\t".join(row))
    txt = "\n".join(lines) + "\n"
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    os.replace(tmp, out)
    with open(out, encoding="utf-8") as fh:
        back = fh.read()
    assert back == txt, "read-back mismatch " + out
    n_rows = sum(1 for l in back.splitlines() if l and not l.startswith("#") and not l.startswith("module\t"))
    assert n_rows == len(modules), "row count mismatch"
    js = OrderedDict(md5=img.md5, funnel=funnel, modules=[OrderedDict(
        module=i, start=m["start"], end=m["end"], level=m["level"], evidence=m["evidence"], string_check=m.get("string_check", ""),
        n_unlinked=m["n_unlinked"], runs=sorted(m["runs"]),
        functions=[OrderedDict(addr=f["addr"], link=links[f["addr"]]) for f in m["functions"]],
        notes=m["notes"] + m["merges"]) for i, m in enumerate(modules, 1)])
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(js, fh, indent=1)
    with open(out_json, encoding="utf-8") as fh:
        assert len(json.load(fh)["modules"]) == len(modules)
    return n_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--export", default=os.path.join(REPO, "ghidra", "export"))
    ap.add_argument("--out", default=os.path.join(REPO, "symbols", "modules.tsv"))
    ap.add_argument("--json", default=os.path.join(REPO, "status", "tasks", "t5-evidence-supply.modules.json"))
    a = ap.parse_args()
    img = Image(a.exe)
    if img.md5 != EXPECTED_MD5:
        sys.exit("refusing: md5 %s != %s (H0)" % (img.md5, EXPECTED_MD5))
    fs = load_functions(a.export)
    names = {}
    for r in read_tsv(os.path.join(REPO, "symbols", "functions.tsv")):
        names[int(r["addr"], 16)] = (r["name"], r["status"])
    strings_rows = read_tsv(os.path.join(REPO, "symbols", "strings.tsv"))
    modules, links, runs, funnel = build(img, fs, strings_rows, names)
    n = write(modules, links, funnel, img, names, a.out, a.json)
    print("launched %s md5 %s tu_boundaries.py 2.0" % (a.exe, img.md5))
    for k, v in funnel.items():
        print("  %s: %s" % (k, v))
    print("modules=%d rows-read-back=%d -> %s" % (len(modules), n, a.out))


if __name__ == "__main__":
    main()
