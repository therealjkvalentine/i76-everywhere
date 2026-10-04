r"""list_auto_range.py - still-unnamed (status auto) functions whose start lies in [lo, hi), with size.

    python tools\list_auto_range.py 0x418000 0x420000 [--min-size 0]
"""
import csv, os, sys, argparse

M = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lo")
    ap.add_argument("hi")
    ap.add_argument("--min-size", type=int, default=0)
    a = ap.parse_args()
    lo, hi = int(a.lo, 16), int(a.hi, 16)
    n = b = 0
    for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8")
                             if not l.startswith("#")), delimiter="\t"):
        f = int(r["addr"], 16)
        if lo <= f < hi and r["status"] == "auto" and int(r["size"] or 0) >= a.min_size:
            print("%s size %5s %s" % (hex(f), r["size"], r["name"]))
            n += 1; b += int(r["size"] or 0)
    print("%d auto functions, %d bytes" % (n, b), file=sys.stderr)


if __name__ == "__main__":
    main()
