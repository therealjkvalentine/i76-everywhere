r"""foldin_coverage.py - which prior-work files mention >= 3 exe-range addresses and are NOT cited by any fold-in report.

    python tools\foldin_coverage.py            list the uncovered files (most addresses first)
    python tools\foldin_coverage.py --json F   also write the list as JSON (input for an extraction round)

Run it before trusting that "the old notes were folded in": round 1 read ~25 files and missed 57, docs\MISSION-LAUNCH.md
among them, which cost a re-derivation and a wrong correction (status\tasks\direct-mission-entry.md). A file counts as
covered when its basename is cited in foldin\FOLDIN-REPORT.md or foldin\round2\REPORT.md.
"""
import glob, json, os, re, sys

HOME = os.path.join("C:" + os.sep, "Users", "james")
REPORTS = [os.path.join(HOME, "i76-map", "foldin", "FOLDIN-REPORT.md"), os.path.join(HOME, "i76-map", "foldin", "round2", "REPORT.md")]
ROOTS = [os.path.join(HOME, "i76-everywhere"), os.path.join(HOME, "i76-uncap-lab")]
SKIP = ("node_modules", os.sep + ".git" + os.sep, "research-full", "recon-", os.sep + "game" + os.sep + "tools" + os.sep)
ADDR = re.compile(r"\b0x0*([4-6][0-9a-fA-F]{5})\b")


def covered_names():
    out = set()
    for rep in REPORTS:
        if os.path.exists(rep):
            for line in open(rep, encoding="utf-8", errors="replace"):
                for m in re.findall(r"([A-Za-z0-9_\-]+\.(?:md|ps1|py|c|h|ahk|txt))", line):
                    out.add(m.lower())
    return out


def main():
    covered = covered_names()
    rows, seen = [], set()
    for root in ROOTS:
        for ext in ("md", "ps1", "c", "py", "h", "ahk", "txt"):
            for f in glob.glob(os.path.join(root, "**", "*." + ext), recursive=True):
                fn = os.path.abspath(f)
                if fn in seen or any(x in fn for x in SKIP):
                    continue
                seen.add(fn)
                try:
                    t = open(f, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                a = set(m.lower() for m in ADDR.findall(t))
                if len(a) >= 3 and os.path.basename(f).lower() not in covered:
                    rows.append({"file": fn, "addrs": len(a), "kb": round(os.path.getsize(f) / 1024, 1)})
    rows.sort(key=lambda r: -r["addrs"])
    if "--json" in sys.argv:
        json.dump(rows, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
    print("%d uncovered files, %d address mentions" % (len(rows), sum(r["addrs"] for r in rows)))
    for r in rows:
        print("%4d %7.1fKB %s" % (r["addrs"], r["kb"], r["file"].replace(HOME + os.sep, "")))


if __name__ == "__main__":
    main()
