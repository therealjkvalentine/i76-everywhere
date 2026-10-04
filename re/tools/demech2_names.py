r"""demech2_names.py - addr -> name table from demech2's reccmp annotations (MW2.DLL / MW2SHELL.DLL, 1.1 patch).

    python tools\demech2_names.py [--module MW2|MW2SHELL] [--out external\demech2-MW2.tsv]

Reads external\demech2 (LGPL-3.0 reference clone). Kinds: FUNCTION (matching decomp), STUB (named, not yet
matched), GLOBAL, LIBRARY (MSVC runtime; the name is on the next comment line). The name of a FUNCTION/STUB is the
identifier before '(' on the first code line after the annotation; of a GLOBAL, the identifier before '=' / ';' / '['.
"""
import os, re, sys
M = r"C:\Users\james\i76-map"
mod = sys.argv[sys.argv.index("--module") + 1] if "--module" in sys.argv else "MW2"
out = os.path.join(M, sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else os.path.join(M, "external", "demech2-%s.tsv" % mod)
root = os.path.join(M, "external", "demech2", mod)
ann = re.compile(r"//\s*(FUNCTION|STUB|GLOBAL|LIBRARY):\s*%s\s+(0x[0-9a-fA-F]+)" % re.escape(mod))
rows = {}
for dp, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith((".c", ".h", ".cpp")):
            continue
        L = open(os.path.join(dp, f), encoding="utf-8", errors="replace").read().splitlines()
        for i, l in enumerate(L):
            m = ann.search(l)
            if not m:
                continue
            kind, addr = m.group(1), int(m.group(2), 16)
            name = None
            for j in range(i + 1, min(i + 8, len(L))):
                s = L[j].strip()
                if not s or ann.search(s):
                    continue
                if kind == "LIBRARY":
                    mm = re.match(r"//\s*([A-Za-z_?@$][\w?@$]*)", s)
                elif s.startswith("//"):
                    continue
                elif kind == "GLOBAL":
                    mm = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])*\s*(?:=|;)", s)
                else:
                    mm = re.search(r"([A-Za-z_]\w*)\s*\(", s)
                if mm:
                    name = mm.group(1)
                break
            if name:
                rows[addr] = (kind, name, os.path.relpath(os.path.join(dp, f), root))
with open(out, "w", encoding="utf-8") as fh:
    fh.write("# demech2 %s names (tools/demech2_names.py; github.com/anpage/demech2, LGPL-3.0; 1.1 patch binaries)\naddr\tkind\tname\tfile\n" % mod)
    for a in sorted(rows):
        fh.write("0x%x\t%s\t%s\t%s\n" % (a, *rows[a]))
from collections import Counter
print(out, len(rows), dict(Counter(k for k, _, _ in rows.values())))
