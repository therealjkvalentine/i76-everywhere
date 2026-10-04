#!/usr/bin/env python3
"""export_public.py - stage the public-safe subset of the sibling repos (i76-uncap-lab, i76-map) for review.

Why: the lab and the RE map have no remote. Parts of them (our own harness code, format parsers, prose RE docs)
belong in this public repo; other parts (Ghidra decompiler exports, game screenshots, extracted game data,
third-party media) must never leave the machine (THIRD-PARTY.md: decompiler output "is Activision's code in
another form"). This tool is the gate between the two, built allowlist-first (backlog P3-23):

  inventory  --repo DIR [--depth N]     classify a repo's TRACKED files by directory: counts, bytes, binary/image
                                        files, decompiler residue, disassembly runs, personal identifiers.
  export     [--config F] [--out DIR]   copy the allowlisted TRACKED files of each source into a staging folder
                                        OUTSIDE every repo, then scan the staged copy (not the source list) and
                                        exit 1 if anything in the hard classes matches.

It never writes into a repository, never commits, never pushes. Only `git ls-files` output is considered, so a
gitignored file can never be staged. The owner reads the report and decides what, if anything, moves.

Config: tools/export_public.toml (globs are fnmatch over the repo-relative posix path; `*` crosses `/`).
Roots resolve relative to this repo's parent, overridable with I76_LAB_ROOT / I76_MAP_ROOT / I76_PUBLIC_STAGING,
so no personal path is committed.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_CONFIG = HERE / "export_public.toml"
STAGING_MARKER = ".export_public_staging"

# ---- residue classes -------------------------------------------------------------------------------------------
# HARD: any match in a staged file fails the export.
#   ghidra_body   - tokens only a decompiler body produces (typed temporaries, undefinedN types, register spill names,
#                   Ghidra's own warning comments). One hit means a pasted decompile.
#   ghidra_name   - FUN_/DAT_/LAB_/PTR_/local_ auto-names. In prose these are references, not code, but the public
#                   house style is a bare address (0x4956e0) or a proposed name; a mechanical rename clears them.
#   disasm_run    - more than DISASM_RUN_MAX consecutive "address  mnemonic" lines (a listing, not a quote).
#   binary        - a NUL byte in the first 8 KB, or a denied extension (images, audio, executables, archives,
#                   Ghidra databases, game containers).
#   email         - any e-mail address not in [identity].allowed_emails.
#   hostname      - Windows/macOS default machine names.
# WARN: reported, not failing.
#   user_path     - absolute paths into a personal home directory (already present in the public repo's docs;
#                   scripts need a variable instead, see the plan).
HARD_PATTERNS = {
    "ghidra_body": re.compile(
        r"\b(?:[a-z]{0,3}Var\d+|undefined[1-8]|unaff_\w+|extraout_\w+|in_stack_[0-9a-f]+|in_(?:EAX|ECX|EDX|EBX|ESI|EDI|FS_OFFSET)\b)"
        r"|/\* WARNING: |\bCONCAT\d\d\(|\bSUB\d\d\(|\bZEXT\d\d\(|\bSEXT\d\d\("
    ),
    "ghidra_name": re.compile(r"\b(?:FUN|DAT|LAB|PTR|thunk_FUN|switchD|caseD)_[0-9a-fA-F]{6,8}\b|\blocal_[0-9a-f]{1,4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"),
    "hostname": re.compile(r"\bDESKTOP-[A-Z0-9]{7}\b|\b\w+s-(?:MacBook|iMac|Mac-mini|Mac-Studio)[\w-]*\b"),
}
WARN_PATTERNS = {
    "user_path": re.compile(r"(?i)\b[A-Z]:[\\/]{1,2}Users[\\/]{1,2}[^\\/\s'\"]+|/c/Users/[^/\s'\"]+|/Users/[a-z][^/\s'\"]*|/home/[a-z][^/\s'\"]*"),
}
DISASM_LINE = re.compile(
    r"^\s*(?:[-+|>*`]\s*)?(?:0x)?[0-9a-fA-F]{6,8}h?:?\s+(?:[0-9a-fA-F]{2}\s+)*"
    r"(?:mov|movsx|movzx|push|pop|call|jmp|j[a-z]{1,3}|cmp|test|add|sub|lea|xor|and|or|not|neg|inc|dec|imul|idiv|mul|div"
    r"|shl|shr|sar|rol|ror|ret|retn|nop|int3|leave|f[a-z]{1,6}|cdq|sete|setne|rep\w*|stos\w*|movs\w*)\b",
    re.I,
)
DISASM_RUN_MAX = 20
NOT_TLD = {"fx", "fxh", "ini", "conf", "ps1", "py", "dll", "exe", "md", "txt", "json", "c", "h"}
DENY_EXT = {
    ".exe", ".dll", ".sys", ".drv", ".obj", ".lib", ".exp", ".pdb", ".ilk", ".o", ".a", ".so", ".dylib",
    ".bmp", ".png", ".jpg", ".jpeg", ".gif", ".tga", ".pcx", ".ico", ".webp", ".tif", ".tiff", ".dds",
    ".wav", ".mp3", ".ogg", ".flac", ".smk", ".avi", ".mp4", ".mkv",
    ".zfs", ".mw2", ".vqm", ".cbk", ".fsm", ".gpw", ".cmp", ".pcode", ".gbf", ".gpr", ".rep", ".db",
    ".zip", ".7z", ".cab", ".rar", ".gz", ".tar", ".iso", ".bin", ".raw", ".dmp", ".mvb", ".ivt", ".pyc",
}


def git_ls_files(repo: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        return b""


def scan_text(data: bytes, allowed_email_hashes: set[str], owner_hashes: set[str]) -> dict[str, int]:
    """Counts per class for one file's bytes (binary files report only 'binary')."""
    hits: dict[str, int] = defaultdict(int)
    if b"\0" in data[:8192]:
        hits["binary"] += 1
        return hits
    text = data.decode("utf-8", "replace")
    for name, rx in HARD_PATTERNS.items():
        for m in rx.finditer(text):
            if name == "email":
                if m.group(0).rsplit(".", 1)[-1].lower() in NOT_TLD:
                    continue  # SMAA@SMAA.fx (ReShade technique@file), not an address
                h = sha(m.group(0))
                if h in allowed_email_hashes:
                    continue
                if h in owner_hashes:
                    hits["owner_email"] += 1
            hits[name] += 1
    for name, rx in WARN_PATTERNS.items():
        n = len(rx.findall(text))
        if n:
            hits[name] += n
    run = best = 0
    for line in text.splitlines():
        if DISASM_LINE.match(line):
            run += 1
            best = max(best, run)
        elif line.strip() in ("", "...", "```"):
            continue  # blank lines and elisions do not break a listing
        else:
            run = 0
    if best:
        hits["disasm_max_run"] = best
    if best > DISASM_RUN_MAX:
        hits["disasm_run"] += 1
    return hits


def sha(s: str) -> str:
    return hashlib.sha256(s.strip().lower().encode()).hexdigest()


def load_config(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def identity_sets(cfg: dict) -> tuple[set[str], set[str]]:
    ident = cfg.get("identity", {})
    allowed = {sha(e) for e in ident.get("allowed_emails", [])}
    owner = set(ident.get("owner_email_sha256", []))
    return allowed, owner


def matches(path: str, globs: list[str]) -> str | None:
    for g in globs:
        if fnmatch.fnmatchcase(path, g):
            return g
    return None


# ---- inventory -------------------------------------------------------------------------------------------------
def group_key(path: str, depth: int, overrides: dict[str, int]) -> str:
    parts = path.split("/")
    top = parts[0]
    d = overrides.get(top, depth)
    if len(parts) == 1:
        return "(root files)"
    return "/".join(parts[: min(d, len(parts) - 1)]) + "/"


def cmd_inventory(args, cfg) -> int:
    repo = Path(args.repo).resolve()
    allowed, owner = identity_sets(cfg)
    overrides = {}
    for spec in args.split or []:
        k, _, v = spec.partition("=")
        overrides[k] = int(v)
    groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for rel in git_ls_files(repo):
        p = repo / rel
        data = read_bytes(p)
        g = groups[group_key(rel, args.depth, overrides)]
        g["files"] += 1
        g["bytes"] += len(data)
        ext = Path(rel).suffix.lower()
        if ext in DENY_EXT:
            g["deny_ext"] += 1
        hits = scan_text(data, allowed, owner)
        for k in ("binary", "ghidra_body", "ghidra_name", "disasm_run", "email", "owner_email", "hostname", "user_path"):
            if hits.get(k):
                g["f_" + k] += 1
        if hits.get("ghidra_body", 0) >= 5:
            g["f_body5"] += 1
        if rel.endswith(".md") and (hits.get("ghidra_body") or hits.get("disasm_run")):
            g["md_scrub"] += 1
    cols = ["files", "bytes", "deny_ext", "f_binary", "f_ghidra_body", "f_body5", "f_ghidra_name", "f_disasm_run",
            "md_scrub", "f_email", "f_owner_email", "f_hostname", "f_user_path"]
    print("group\t" + "\t".join(cols))
    for k in sorted(groups):
        print(k + "\t" + "\t".join(str(groups[k].get(c, 0)) for c in cols))
    return 0


# ---- export ----------------------------------------------------------------------------------------------------
def resolve_root(spec: str, env: str | None) -> Path:
    if env and os.environ.get(env):
        return Path(os.environ[env]).resolve()
    p = Path(spec)
    return (p if p.is_absolute() else (REPO_ROOT / p)).resolve()


def safe_clear(out: Path) -> None:
    if out.exists():
        if not (out / STAGING_MARKER).exists():
            sys.exit(f"refusing to clear {out}: no {STAGING_MARKER} marker (not a staging folder made by this tool)")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / STAGING_MARKER).write_text("created by i76-everywhere/tools/export_public.py; safe to delete\n")


def inside_any_repo(out: Path, roots: list[Path]) -> bool:
    for r in roots:
        try:
            out.relative_to(r)
            return True
        except ValueError:
            pass
    return False


def cmd_export(args, cfg) -> int:
    allowed, owner = identity_sets(cfg)
    stg = cfg.get("staging", {})
    out = Path(args.out).resolve() if args.out else resolve_root(stg.get("out", "../i76-public-staging"), "I76_PUBLIC_STAGING")
    sources = cfg["source"]
    roots = [REPO_ROOT] + [resolve_root(s["repo"], s.get("env")) for s in sources]
    if inside_any_repo(out, roots):
        sys.exit(f"refusing: staging folder {out} is inside a repository")
    safe_clear(out)

    report: list[str] = []
    totals = {"staged": 0, "bytes": 0}
    for s, root in zip(sources, roots[1:]):
        tracked = git_ls_files(root)
        include, exclude = s.get("include", []), s.get("exclude", [])
        scrub = s.get("needs_scrub", [])
        never = cfg.get("never", {}).get("globs", [])
        reasons: dict[str, int] = defaultdict(int)
        staged = 0
        for rel in tracked:
            if not matches(rel, include):
                reasons["not allowlisted"] += 1
                continue
            if matches(rel, never):
                reasons["never-public glob"] += 1
                continue
            if matches(rel, exclude):
                reasons["source exclude"] += 1
                continue
            if matches(rel, scrub):
                reasons["needs_scrub (held back)"] += 1
                continue
            if Path(rel).suffix.lower() in DENY_EXT:
                reasons["denied extension"] += 1
                continue
            dst = out / s["dest"] / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, dst)
            staged += 1
            totals["bytes"] += dst.stat().st_size
        totals["staged"] += staged
        report.append(f"[{s['name']}] {root.name}: tracked {len(tracked)}, staged {staged} -> {s['dest']}/")
        for k, v in sorted(reasons.items()):
            report.append(f"    skipped {v:6d}  {k}")

    # gate: scan what actually landed in the staging folder
    fail: dict[str, list[str]] = defaultdict(list)
    warn: dict[str, list[str]] = defaultdict(list)
    for p in sorted(out.rglob("*")):
        if not p.is_file() or p.name == STAGING_MARKER:
            continue
        rel = p.relative_to(out).as_posix()
        if p.suffix.lower() in DENY_EXT:
            fail["denied_extension"].append(rel)
        hits = scan_text(read_bytes(p), allowed, owner)
        for k in ("binary", "ghidra_body", "ghidra_name", "disasm_run", "email", "hostname"):
            if hits.get(k):
                fail[k].append(f"{rel} ({hits[k]})")
        for k in ("user_path",):
            if hits.get(k):
                warn[k].append(f"{rel} ({hits[k]})")
    report.append(f"staged total: {totals['staged']} files, {totals['bytes']:,} bytes in {out}")
    for k, v in sorted(fail.items()):
        report.append(f"FAIL {k}: {len(v)} files")
        report += ["    " + x for x in v[: args.show]]
    for k, v in sorted(warn.items()):
        report.append(f"WARN {k}: {len(v)} files")
        report += ["    " + x for x in v[: args.show]]
    report.append("RESULT: " + ("FAIL (residue in staged copy)" if fail else "PASS (no hard residue in staged copy)"))
    text = "\n".join(report)
    print(text)
    (out / "EXPORT-REPORT.txt").write_text(text + "\n", encoding="utf-8")
    return 1 if fail else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("inventory")
    a.add_argument("--repo", required=True)
    a.add_argument("--depth", type=int, default=1)
    a.add_argument("--split", nargs="*", help="TOP=DEPTH overrides, e.g. ghidra=2 verify=2")
    b = sub.add_parser("export")
    b.add_argument("--out")
    b.add_argument("--show", type=int, default=40, help="list at most this many files per class")
    args = ap.parse_args()
    cfg = load_config(Path(args.config))
    return cmd_inventory(args, cfg) if args.cmd == "inventory" else cmd_export(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
