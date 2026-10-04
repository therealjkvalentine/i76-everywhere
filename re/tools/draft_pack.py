r"""draft_pack.py - the bounded context of drafter step 2, in one read (added 2026-09-26 to cut drafter turns).

    python tools\draft_pack.py <key> --view c|pcode [--out <file>]

g2 measured ~1.5M cache-read tokens per drafter, mostly from re-reading context over the ~10 separate reads step 2
asks for. This prints the same items, bounded, in one output. View independence (G4) is kept:
  c      the function's .c, up to 5 callers' and 5 callees' .c (smallest first, capped), no pcode, no disassembly
  pcode  the function's .pcode and capstone disassembly, and for up to 5 callers only the disassembly around each
         call to this function (no .c of anything)
Both: callgraph entry, strings.tsv / imports.tsv / tables.tsv rows naming the function, functions.tsv status of
callers/callees, globals.tsv rows for absolute addresses the function references (xref index), functions\<key>.md
if merged, the names of the structs in types\i76.h, and capture manifests that mention the address. It never prints
another drafter's proposal or review.
"""
import argparse, csv, glob, hashlib, io, json, os, re, subprocess, sys

M = r"C:\Users\james\i76-map"
EXP = os.path.join(M, "ghidra", "export")
CAP_MAIN, CAP_CALLER, CAP_CALLEE, CTX_INSNS = 600, 120, 80, 12


def rows(name):
    p = os.path.join(M, "symbols", name)
    return list(csv.DictReader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t"))


def head(path, n):
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return None, 0
    return "\n".join(lines[:n]) + ("\n... (%d more lines)" % (len(lines) - n) if len(lines) > n else ""), len(lines)


def disasm(addr):
    p = subprocess.run([sys.executable, os.path.join(M, "tools", "disasm.py"), "0x%s" % addr], cwd=M, capture_output=True, text=True)
    return p.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--view", choices=["c", "pcode"], required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    key = a.key.lower().replace("0x", "").zfill(8)
    addr = int(key, 16)
    out = io.StringIO()
    w = lambda s="": out.write(s + "\n")
    cg = json.load(open(os.path.join(EXP, "callgraph.json"), encoding="utf-8"))
    ent = cg.get(key, {})
    fn = {("%08x" % int(r["addr"], 16)): r for r in rows("functions.tsv")}
    me = fn.get(key, {})
    w("# draft pack %s view %s (tools/draft_pack.py; bounded context of drafter step 2)" % (key, a.view))
    w("functions.tsv: %s" % "\t".join("%s=%s" % (k, me.get(k, "")) for k in ("name", "size", "status", "conv")))

    ext = ".c" if a.view == "c" else ".pcode"
    main_path = os.path.join(EXP, "functions", key + ext)
    body, n = head(main_path, CAP_MAIN)
    md5 = hashlib.md5(open(main_path, "rb").read()).hexdigest() if os.path.exists(main_path) else "(missing)"
    w("\n## 1. %s%s  (export_md5 %s, %d lines)" % (key, ext, md5, n))
    w(body or "(no export file)")
    if a.view == "pcode":
        w("\n## 1b. disassembly (tools/disasm.py)")
        w(disasm(key).rstrip())

    w("\n## 2. callgraph")
    callers = ent.get("callers", [])
    callees = [c for c in ent.get("callees", []) if int(c, 16) >= 0x401000]
    w("callers (%d): %s" % (len(callers), " ".join("%s %s [%s]" % (c, fn.get(c, {}).get("name", "?"), fn.get(c, {}).get("status", "?")) for c in callers)))
    w("callees (%d): %s" % (len(callees), " ".join("%s %s [%s]" % (c, fn.get(c, {}).get("name", "?"), fn.get(c, {}).get("status", "?")) for c in callees)))
    for s in ent.get("call_sites", []):
        w("  call_site %s -> %s %s" % (s[0], s[1], s[2]))

    size = lambda k: int(fn.get(k, {}).get("size") or 1 << 30)
    w("\n## 3. callers%s" % (" (.c, smallest 5)" if a.view == "c" else " (disassembly around each call to %s)" % key))
    for c in sorted(callers, key=size)[:5]:
        if a.view == "c":
            txt, n = head(os.path.join(EXP, "functions", c + ".c"), CAP_CALLER)
            w("\n### caller %s %s (%d lines)" % (c, fn.get(c, {}).get("name", "?"), n)); w(txt or "(no .c)")
        else:
            lines = disasm(c).splitlines()
            hits = [i for i, l in enumerate(lines) if re.search(r"\bcall\s+0x0*%x\b" % addr, l)]
            w("\n### caller %s %s: %d call(s)" % (c, fn.get(c, {}).get("name", "?"), len(hits)))
            for i in hits[:4]:
                w("\n".join(lines[max(1, i - CTX_INSNS):i + 4])); w("  ...")
    if a.view == "c":
        w("\n## 3b. callees (.c, smallest 5)")
        for c in sorted(callees, key=size)[:5]:
            txt, n = head(os.path.join(EXP, "functions", c + ".c"), CAP_CALLEE)
            w("\n### callee %s %s [%s] (%d lines)" % (c, fn.get(c, {}).get("name", "?"), fn.get(c, {}).get("status", "?"), n)); w(txt or "(no .c)")

    w("\n## 4. symbol rows")
    for r in rows("strings.tsv"):
        if key in (r.get("referencing_functions") or "") or key in (r.get("imm32_functions") or ""):
            w("string %s %r (refs %s)" % (r["addr"], r["string"][:160], r["referencing_functions"][:80]))
    for r in rows("imports.tsv"):
        if ("0x%x" % addr) in (r.get("functions") or "") or key in (r.get("ghidra_functions") or ""):
            w("import %s %s!%s" % (r["iat_slot"], r["dll"], r["name"]))
    for r in rows("tables.tsv"):
        if ("0x%x" % addr) in (r.get("targets") or ""):
            t = r["targets"].split(";")
            w("table %s %s kind=%s stride=%s index=%s" % (r["base"], r.get("name") or "", r["kind"], r["stride"], t.index("0x%x" % addr) if "0x%x" % addr in t else "?"))
    xp = os.path.join(M, "status", "xrefs-9a232dcc.json")
    if os.path.exists(xp):
        gl = {r["addr"]: r for r in rows("globals.tsv")}
        refs = json.load(open(xp))["refs"]
        seen = []
        for g, lst in refs.items():
            for s in lst:
                if len(s) > 5 and str(s[5]).replace("0x", "").zfill(8) == key:
                    seen.append((g, s))
        for g, s in sorted(seen)[:40]:
            row = gl.get(g)
            w("global %s at %s %s %s  %s" % (g, s[0], s[1], s[2], ("map: %s %s w%s %s" % (row["name"], row["type"], row["width"], row["status"])) if row else "(no globals.tsv row)"))

    w("\n## 5. merged record and types")
    mp = os.path.join(M, "functions", key + ".md")
    txt, n = head(mp, 80)
    w(txt if txt else "(no functions\\%s.md)" % key)
    hp = os.path.join(M, "types", "i76.h")
    names = re.findall(r"typedef (?:struct|enum) (\w+)", open(hp, encoding="utf-8").read())
    w("types\\i76.h defines: %s (read the header for a struct you use)" % ", ".join(names))
    for mf in glob.glob(os.path.join(M, "captures", "*", "manifest.json")):
        s = open(mf, encoding="utf-8", errors="replace").read()
        if ("0x%x" % addr) in s or key in s:
            w("capture mentions it: %s" % os.path.relpath(mf, M))
    text = out.getvalue()
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
        print("wrote %s (%d lines)" % (a.out, text.count("\n")))
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
