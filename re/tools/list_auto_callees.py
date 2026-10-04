r"""list_auto_callees.py - still-unnamed (status auto) functions reachable from roots, with depth and size.

    python tools\list_auto_callees.py 0x4a4130 0x4a0410 [--depth 3] [--exclude-tree 0x438fd0,0x465370]

Uses the static call graph (ghidra\export\callgraph.json via tools\perframe.py). --exclude-tree drops functions
reachable from those roots (e.g. an already-mapped subsystem) so work lists do not overlap.
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv, _argv = [sys.argv[0]], sys.argv
import perframe as P
sys.argv = _argv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--exclude-tree", default="")
    a = ap.parse_args()
    excl = set()
    if a.exclude_tree:
        excl = P.reach([int(x, 16) for x in a.exclude_tree.split(",")])
    seen = {}
    frontier = [(int(r, 16), 0) for r in a.roots]
    while frontier:
        f, d = frontier.pop(0)
        if f in seen or d > a.depth:
            continue
        seen[f] = d
        for c in P.callees(f):
            if c in P.FN:
                frontier.append((c, d + 1))
    rows = [(d, f) for f, d in seen.items() if f in P.FN and P.FN[f]["status"] == "auto" and f not in excl]
    for d, f in sorted(rows):
        print("%s depth %d size %5s %s" % (hex(f), d, P.FN[f].get("size"), P.FN[f]["name"]))
    print("%d auto functions" % len(rows), file=sys.stderr)


if __name__ == "__main__":
    main()
