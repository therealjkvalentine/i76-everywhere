#!/usr/bin/env python3
r"""proposals.py - harvest the proposed exe names from data\notes\*.md into data\exe-proposals.tsv.

Columns: the symbols\functions.tsv columns (addr size name status conv conv_evidence hookable duplicate_of tu
subsystem evidence_ids) + current_name + evidence + source_note. status is always `proposed`; the main session
merges through its gates. Rows whose current name is already non-FUN_ and differs are kept and marked in
current_name so the merger sees the conflict. Multi-address cells ("0x40aff0 / 0x40b0f0") are split and paired
with the matching "/"-separated name.
"""
import os, re, csv, glob
DATA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.dirname(DATA)


def funcs():
    out = {}
    for r in csv.DictReader((l for l in open(os.path.join(MAP, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        out[int(r["addr"], 16)] = r
    return out


def rows_from(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|") and "propos" in ln.lower() and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            hdr = [c.strip().lower() for c in ln.strip("|").split("|")]
            ia = next((k for k, h in enumerate(hdr) if h.startswith("addr")), 0)
            iname = next((k for k, h in enumerate(hdr) if "propos" in h), 1)
            iev = next((k for k, h in enumerate(hdr) if "evidence" in h), None)
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if len(cells) > max(ia, iname):
                    addrs = re.findall(r"0x[0-9a-fA-F]{6}", cells[ia])
                    names = [n.strip(" `*") for n in re.split(r"\s*/\s*", cells[iname])]
                    ev = cells[iev] if iev is not None and iev < len(cells) else ""
                    if len(addrs) == len(names):
                        pairs = zip(addrs, names)
                    elif len(names) == 1:
                        pairs = [(a, names[0]) for a in addrs[:1]]
                    else:
                        pairs = []
                    for a, n in pairs:
                        n = re.sub(r"\(.*?\)", "", n).strip().split()[0] if n else n
                        if n and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", n) and not n.lower().startswith(("already", "keep")):
                            out.append((int(a, 16), n, ev, os.path.basename(path)))
                i += 1
            continue
        i += 1
    return out


def main():
    fs = funcs()
    rows = []
    for p in sorted(glob.glob(os.path.join(DATA, "notes", "*.md"))):
        rows += rows_from(p)
    seen = {}
    for a, n, ev, src in rows:
        seen.setdefault(a, []).append((n, ev, src))
    cols = ["addr", "size", "name", "status", "conv", "conv_evidence", "hookable", "duplicate_of", "tu", "subsystem", "evidence_ids",
            "current_name", "evidence", "source_note"]
    out = [cols]
    nconf = 0
    nagree = 0
    for a in sorted(seen):
        n, ev, src = seen[a][0]
        alts = sorted({x[0] for x in seen[a]} - {n})
        f = fs.get(a)
        cur = f["name"] if f else "(no function at this address in functions.tsv)"
        norm = lambda x: x.lower().replace("_", "")
        if f and not cur.startswith("FUN_") and norm(cur) == norm(n):
            nagree += 1
            continue  # the map already has this name (case/separator only)
        if f and not cur.startswith("FUN_") and cur != n:
            nconf += 1
        sub = n.split("_")[0] if "_" in n else ""
        evs = " ; ".join(sorted({"%s: %s" % (x[2], x[1]) for x in seen[a] if x[1]}))
        if alts:
            evs += " ; alternative names: " + ", ".join(alts)
        out.append(["0x%x" % a, f["size"] if f else "", n, "proposed", "auto", "auto:paramid", f["hookable"] if f else "", "", "", sub, "",
                    cur, evs.replace("\t", " ").replace("\n", " "), ",".join(sorted({x[2] for x in seen[a]}))])
    dst = os.path.join(DATA, "exe-proposals.tsv")
    with open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write("# data-track proposed exe names (data/fmt/proposals.py from data/notes/*.md). status=proposed; merge only through the main session's gates.\n")
        fh.write("# current_name = the name in symbols/functions.tsv at harvest time; a non-FUN_ value that differs is a naming conflict for the merger to resolve.\n")
        csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(out)
    print("wrote %s: %d proposals (%d on FUN_ rows, %d differ from an existing name); %d already named identically, skipped" % (dst, len(out) - 1, len(out) - 1 - nconf, nconf, nagree))


if __name__ == "__main__":
    main()
