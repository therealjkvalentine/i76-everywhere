#!/usr/bin/env python3
"""manifest.py - md5 + size + relative path for every file under a root.

Usage
  python tools/manifest.py <root> [-o OUT]            write manifest (stdout if no -o)
  python tools/manifest.py <root> --check MANIFEST    recompute and diff against MANIFEST
  python tools/manifest.py <root> --large N [-o OUT] [--prefix P]
        emit a .gitignore block listing every file whose size is > N bytes. Rows are
        "/<prefix>/<relpath>"; prefix defaults to the root's own directory name, so
        `manifest.py recon-2026-09-04 --large N` gives rows usable from the repo top and
        `manifest.py . --large N --prefix ""` covers the whole repository.

Format (tab separated, sorted by path, POSIX separators, '#' header lines):
  <md5 hex>\t<size bytes>\t<relative path>

The manifest covers every file on disk under <root>, including files that .gitignore keeps
out of git (Ghidra projects, extracted ZFS, exe/dll copies); that is the point: git holds
the text, the manifest holds the identity of everything else. `.git` directories and the
output file itself are skipped. Nothing is inferred; a row is a hash of bytes read.
"""
import argparse
import hashlib
import os
import sys
import time

CHUNK = 1 << 20


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def walk(root, skip_abs):
    """Yield (relpath_posix, size, abspath) for every regular file under root."""
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            ap = os.path.join(dirpath, name)
            if os.path.abspath(ap) in skip_abs:
                continue
            if not os.path.isfile(ap):
                continue
            rel = os.path.relpath(ap, root).replace(os.sep, "/")
            yield rel, os.path.getsize(ap), ap


def build(root, skip_abs):
    rows = []
    for rel, size, ap in walk(root, skip_abs):
        rows.append((rel, size, md5_of(ap)))
    rows.sort(key=lambda r: r[0])
    return rows


def write_manifest(rows, root, out):
    total = sum(r[1] for r in rows)
    lines = [
        "# i76-map manifest: md5<TAB>size<TAB>path (paths relative to root, POSIX separators)",
        "# root: %s" % os.path.abspath(root).replace(os.sep, "/"),
        "# generated: %s by tools/manifest.py" % time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "# files: %d" % len(rows),
        "# bytes: %d" % total,
    ]
    lines += ["%s\t%d\t%s" % (md5, size, rel) for rel, size, md5 in rows]
    data = ("\n".join(lines) + "\n").encode("utf-8")
    if out:
        with open(out, "wb") as f:
            f.write(data)
    else:
        sys.stdout.buffer.write(data)
    return len(rows), total


def read_manifest(path):
    rows = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            md5, size, rel = line.split("\t", 2)
            rows[rel] = (int(size), md5)
    return rows


def check(root, manifest_path):
    skip = {os.path.abspath(manifest_path)}
    want = read_manifest(manifest_path)
    have = {rel: (size, md5) for rel, size, md5 in build(root, skip)}
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    changed = sorted(r for r in set(want) & set(have) if want[r] != have[r])
    for r in missing:
        print("MISSING\t%s" % r)
    for r in extra:
        print("EXTRA\t%s" % r)
    for r in changed:
        print("CHANGED\t%s\twant %s/%d\thave %s/%d" % (r, want[r][1], want[r][0], have[r][1], have[r][0]))
    print("# check: %d listed, %d on disk, %d missing, %d extra, %d changed"
          % (len(want), len(have), len(missing), len(extra), len(changed)))
    return 0 if not (missing or extra or changed) else 1


def large_block(root, threshold, out, prefix=None):
    """Emit a .gitignore block. gitignore has no trailing comments, so the size goes on its
    own '#' line above each path; the path line is the bare pattern."""
    root_abs = os.path.abspath(root)
    if prefix is None:
        prefix = os.path.basename(root_abs.rstrip("/\\"))
    pfx = ("/" + prefix) if prefix else ""
    big = [(rel, size) for rel, size, ap in walk(root_abs, set()) if size > threshold]
    big.sort()
    regen = "python tools/manifest.py %s --large %d%s" % (root, threshold, "" if prefix else ' --prefix ""')
    lines = [
        "# ---- BEGIN generated: files > %d bytes under %s/ ----" % (threshold, prefix or "."),
        "# %d files; regenerate: %s" % (len(big), regen),
    ]
    for rel, size in big:
        lines.append("# %d bytes" % size)
        lines.append("%s/%s" % (pfx, rel))
    lines.append("# ---- END generated ----")
    text = "\n".join(lines) + "\n"
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return len(big)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("-o", "--out", help="output file (default stdout)")
    ap.add_argument("--check", metavar="MANIFEST", help="verify root against an existing manifest")
    ap.add_argument("--large", type=int, metavar="BYTES", help="emit .gitignore block for files > BYTES")
    ap.add_argument("--prefix", default=None,
                    help="path prefix for --large rows (default: the root's own name; "
                         "pass an empty string when root is the repo top)")
    a = ap.parse_args()
    if not os.path.isdir(a.root):
        sys.exit("manifest.py: not a directory: %s" % a.root)
    if a.check:
        sys.exit(check(a.root, a.check))
    if a.large is not None:
        n = large_block(a.root, a.large, a.out, a.prefix)
        print("manifest.py: %d files > %d bytes" % (n, a.large), file=sys.stderr)
        return
    skip = {os.path.abspath(a.out)} if a.out else set()
    t0 = time.time()
    rows = build(a.root, skip)
    n, total = write_manifest(rows, a.root, a.out)
    print("manifest.py: %d files, %d bytes, %.1f s -> %s" % (n, total, time.time() - t0, a.out or "stdout"),
          file=sys.stderr)


if __name__ == "__main__":
    main()
