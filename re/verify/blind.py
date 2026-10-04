#!/usr/bin/env python3
"""Blind kit (VERIFICATION-PROGRAM.md section 2.6 / 4.5).

Produces the *stripped* decompilation of a function: every callee and global that the map has named is
replaced by its address form (FUN_<8hex> / DAT_<8hex>), string literals are kept (and resolved from the
export's strings table), the callers' stripped bodies are attached (first 40 lines each, at most 3), plus the
subsystem vocabulary table with addresses and example names redacted. Nothing in the output carries the
map's name for the function or for any `proposed`/`supported` neighbour.

Names whose status is `anchored` or `library` (the binary itself names them: import thunks, FID matches) are
kept; they are facts about the binary, not the map's reading.

Also hosts the small TSV loaders shared by make_units.py and worker.py (no extra module file).

CLI:
    python verify/blind.py 0x438fd0            # print the stripped C
    python verify/blind.py 0x438fd0 --json     # print the full blind-name inputs dict
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

VERIFY = Path(__file__).resolve().parent
ROOT = VERIFY.parent
FUNCTIONS_TSV = ROOT / "symbols" / "functions.tsv"
GLOBALS_TSV = ROOT / "symbols" / "globals.tsv"
EXPORT = ROOT / "ghidra" / "export"
DECOMP_DIR = EXPORT / "functions"
CALLGRAPH = EXPORT / "callgraph.json"
STRINGS_CSV = EXPORT / "strings_xrefs.csv"
VOCABULARY = ROOT / "subsystems" / "VOCABULARY.md"

KEEP_STATUSES = {"anchored", "library"}
CALLER_LINES = 40
MAX_CALLERS = 3


# ----------------------------------------------------------------------------- loaders

def addr8(addr) -> str:
    """'0x438fd0' / '438fd0' / '00438fd0' / int -> '00438fd0'."""
    if isinstance(addr, int):
        return f"{addr:08x}"
    a = str(addr).strip().lower()
    if a.startswith("0x"):
        a = a[2:]
    return a.zfill(8)


def addr0x(addr) -> str:
    return "0x" + addr8(addr).lstrip("0").rjust(1, "0")


def read_tsv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        header = None
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if header is None:
                header = parts
                continue
            parts += [""] * (len(header) - len(parts))
            rows.append(dict(zip(header, parts)))
    return rows


_FUNCS = None
_GLOBALS = None
_CALLGRAPH = None
_STRINGS = None


def load_functions() -> list[dict]:
    """functions.tsv rows (addr, size, name, status, ..., subsystem, evidence_ids); addr as '0x...'."""
    global _FUNCS
    if _FUNCS is None:
        _FUNCS = read_tsv(FUNCTIONS_TSV)
    return _FUNCS


def functions_by_addr() -> dict[str, dict]:
    return {addr8(r["addr"]): r for r in load_functions()}


def functions_by_name() -> dict[str, dict]:
    return {r["name"]: r for r in load_functions() if r["name"]}


def load_globals() -> list[dict]:
    global _GLOBALS
    if _GLOBALS is None:
        _GLOBALS = read_tsv(GLOBALS_TSV)
    return _GLOBALS


def load_callgraph() -> dict:
    """ghidra/export/callgraph.json: {addr8: {name, callers:[addr8], callees:[addr8], call_sites:[[site, target, name]]}}."""
    global _CALLGRAPH
    if _CALLGRAPH is None:
        with open(CALLGRAPH, encoding="utf-8") as fh:
            _CALLGRAPH = json.load(fh)
    return _CALLGRAPH


def load_strings() -> dict[str, str]:
    """strings_xrefs.csv -> {addr8: text}."""
    global _STRINGS
    if _STRINGS is None:
        _STRINGS = {}
        if STRINGS_CSV.exists():
            with open(STRINGS_CSV, encoding="utf-8", errors="replace", newline="") as fh:
                for row in csv.DictReader(fh):
                    _STRINGS[addr8(row["address"])] = row["string"]
    return _STRINGS


def read_decomp(addr) -> str | None:
    p = DECOMP_DIR / f"{addr8(addr)}.c"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------------- stripping

_NAME_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_@]*\b")


def _rename_tables() -> tuple[dict[str, str], dict[str, str]]:
    """name -> replacement for functions and globals that must be stripped."""
    fn = {}
    for r in load_functions():
        n = r["name"]
        if not n or n.startswith("FUN_") or r["status"] in KEEP_STATUSES:
            continue
        fn[n] = "FUN_" + addr8(r["addr"])
    gl = {}
    for r in load_globals():
        n = r["name"]
        if not n or n.startswith("DAT_") or r["status"] in KEEP_STATUSES:
            continue
        gl[n] = "DAT_" + addr8(r["addr"])
    return fn, gl


def strip_text(text: str) -> str:
    """Replace every map-named identifier in a decompilation with its FUN_/DAT_ form."""
    fn, gl = _rename_tables()
    table = {**gl, **fn}

    def sub(m):
        tok = m.group(0)
        return table.get(tok, tok)

    out = _NAME_RE.sub(sub, text)
    # The export's header comment is "// <addr8> <name> size=N thunk=..." - normalise the name slot too.
    out = re.sub(r"^// ([0-9a-f]{8}) \S+ ", lambda m: f"// {m.group(1)} FUN_{m.group(1)} ", out, flags=re.M)
    return out


def strip_decomp(addr) -> str | None:
    text = read_decomp(addr)
    return None if text is None else strip_text(text)


def strings_referenced(text: str) -> list[dict]:
    """String literals the body refers to, resolved via strings_xrefs.csv (kept: they are the binary's own)."""
    table = load_strings()
    seen = {}
    for m in re.finditer(r"\bs_[A-Za-z0-9_]*?_([0-9a-f]{8})\b|&?DAT_([0-9a-f]{8})\b", text):
        a = m.group(1) or m.group(2)
        if a in table and a not in seen:
            seen[a] = table[a]
    return [{"addr": f"0x{a.lstrip('0')}", "text": t} for a, t in seen.items()]


# ----------------------------------------------------------------------------- vocabulary

_HEX_RE = re.compile(r"0x[0-9a-fA-F]+")
_FNAME_RE = re.compile(r"\b[a-z][a-z0-9]*_[A-Za-z][A-Za-z0-9_]*\b")


def vocabulary_table() -> str:
    """The prefix table from subsystems/VOCABULARY.md as 'prefix | aliases | scope' rows, with every hex
    address and every example function/global name redacted (they would reveal map names)."""
    fn, gl = _rename_tables()
    map_names = set(fn) | set(gl)
    rows = []
    for line in VOCABULARY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].startswith("---") or cells[0].startswith("canonical"):
            continue
        scope = _HEX_RE.sub("", cells[2])
        scope = _FNAME_RE.sub("", scope)
        scope = _NAME_RE.sub(lambda m: "" if m.group(0) in map_names else m.group(0), scope)  # one-word names (rsqrt)
        scope = re.sub(r"\([^()A-Za-z]*\)", "", scope)         # parentheses left with no words inside
        scope = re.sub(r"\[[^\]A-Za-z0-9]*\]", "", scope)       # emptied brackets
        scope = re.sub(r"[+/]\s*(?=[,;)/\s]|$)", "", scope)     # dangling '+' / '/' operators
        scope = re.sub(r"\s+([,;.])", r"\1", scope)
        scope = re.sub(r"\s{2,}", " ", scope).strip(" ;,/-")
        rows.append(f"| {cells[0]} | {cells[1]} | {scope} |")
    return "| prefix | aliases | scope |\n|---|---|---|\n" + "\n".join(rows)


# ----------------------------------------------------------------------------- unit inputs

def blind_inputs(addr) -> dict | None:
    """The blind-name unit inputs for one function, or None when there is no decompilation."""
    a8 = addr8(addr)
    body = strip_decomp(a8)
    if body is None:
        return None
    cg = load_callgraph().get(a8, {})
    callers = list(cg.get("callers", []))
    callers_stripped = []
    for c in callers[:MAX_CALLERS]:
        ct = strip_decomp(c)
        if ct is None:
            continue
        lines = ct.splitlines()
        snippet = "\n".join(lines[:CALLER_LINES])
        if len(lines) > CALLER_LINES:
            snippet += f"\n/* ... {len(lines) - CALLER_LINES} more lines ... */"
        callers_stripped.append({"caller": f"FUN_{c}", "body": snippet})
    size = functions_by_addr().get(a8, {}).get("size", "")
    return {
        "function": f"FUN_{a8}",
        "size_bytes": int(size) if str(size).isdigit() else None,
        "stripped_c": body,
        "strings": strings_referenced(body),
        "caller_count": len(callers),
        "callee_count": len(cg.get("callees", [])),
        "callers_stripped": callers_stripped,
        "vocabulary": vocabulary_table(),
    }


def leaks(inputs: dict) -> list[str]:
    """Self-check: map names (non-anchored functions/globals) that still appear anywhere in the inputs."""
    blob = json.dumps(inputs)
    fn, gl = _rename_tables()
    found = [n for n in list(fn) + list(gl) if re.search(r"\b" + re.escape(n) + r"\b", blob)]
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("addr")
    ap.add_argument("--json", action="store_true", help="print the full blind-name inputs as JSON")
    args = ap.parse_args(argv)
    if args.json:
        inp = blind_inputs(args.addr)
        if inp is None:
            sys.exit(f"no decompilation for {args.addr}")
        print(json.dumps(inp, indent=1))
    else:
        text = strip_decomp(args.addr)
        if text is None:
            sys.exit(f"no decompilation for {args.addr}")
        print(text)


if __name__ == "__main__":
    main()
