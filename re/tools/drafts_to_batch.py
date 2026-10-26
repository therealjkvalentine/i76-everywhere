r"""drafts_to_batch.py - turn subagent cluster drafts (JSON: {"cluster", "functions": [{addr, name, contract, evidence:
[{site, claim}], confidence}], ...}) into a merge.py batch.

    python tools\drafts_to_batch.py --batch physics-map-1 --author "..." draft1.json [draft2.json ...] > batch.json

Rules (2026-09-27):
  * a function that already has a non-auto name keeps it; a different draft name is listed in "conflicts";
  * low-confidence drafts are held back ("held");
  * duplicates across drafts: the higher confidence wins, then the first file;
  * prefixes outside subsystems/VOCABULARY.md are folded (terrain_/surface_ -> world_) or held;
  * every evidence item becomes a struct-access evidence row with the pristine md5; the contract goes in as the
    first claim.
"""
import csv, json, os, re, sys, argparse

M = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD5 = "9a232dcc2c164648cff20c414c1f9698"
FOLD = {"terrain": "world", "surface": "world", "obj": "object", "geom": "math", "calc": "math"}
RANK = {"high": 3, "medium-high": 2.5, "medium": 2, "low-medium": 1.5, "low": 1}


def vocab():
    pre = set()
    for line in open(os.path.join(M, "subsystems", "VOCABULARY.md"), encoding="utf-8"):
        m = re.match(r"\|\s*([a-z0-9]+)\s*\|", line)
        if m and m.group(1) not in ("canonical",):
            pre.add(m.group(1))
    return pre


def conf_rank(c):
    c = (c or "").lower()
    for k in sorted(RANK, key=len, reverse=True):
        if c.startswith(k):
            return RANK[k]
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("drafts", nargs="+")
    a = ap.parse_args()
    fn = {int(r["addr"], 16): r for r in csv.DictReader(
        (l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t")}
    owners = {r["name"]: int(r["addr"], 16) for r in fn.values()}
    V = vocab()
    best, conflicts, held = {}, [], []
    for path in a.drafts:
        d = json.load(open(path, encoding="utf-8"))
        for f in d.get("functions", []):
            addr = int(str(f["addr"]), 16)
            name = f["name"]
            pre, _, rest = name.partition("_")
            pre = FOLD.get(pre, pre)
            name = pre + "_" + rest
            rank = conf_rank(f.get("confidence"))
            row = fn.get(addr)
            if row is None:
                held.append({"addr": hex(addr), "name": name, "why": "no function row at this address"}); continue
            if row["status"] != "auto":
                if row["name"] != name:
                    conflicts.append({"addr": hex(addr), "existing": row["name"], "draft": name, "cluster": d.get("cluster")})
                continue
            if rank < 2:
                held.append({"addr": hex(addr), "name": name, "why": "confidence %s" % f.get("confidence")}); continue
            if pre not in V:
                held.append({"addr": hex(addr), "name": name, "why": "prefix %s not in VOCABULARY.md" % pre}); continue
            cur = best.get(addr)
            if cur and cur[0] >= rank:
                if cur[1]["name"] != name:
                    conflicts.append({"addr": hex(addr), "existing": cur[1]["name"], "draft": name, "cluster": d.get("cluster")})
                continue
            best[addr] = (rank, dict(f, name=name, cluster=d.get("cluster")))
    rows, used = [], {}
    for addr, (rank, f) in sorted(best.items()):
        name = f["name"]
        if (name in owners and owners[name] != addr) or name in used:
            held.append({"addr": hex(addr), "name": name, "why": "name already used by %s" % hex(owners.get(name, used.get(name, 0)))}); continue
        used[name] = addr
        ev = [{"kind": "struct-access", "md5": MD5, "site": hex(addr), "claim": "contract (cluster %s): %s" % (f["cluster"], f.get("contract", ""))}]
        for e in f.get("evidence", []):
            site = str(e.get("site", "")).split()[0].split("..")[0].split("/")[0].rstrip(",;")
            ev.append({"kind": "struct-access", "md5": MD5, "site": site if site.startswith("0x") else hex(addr), "claim": e.get("claim", "")})
        rows.append({"addr": hex(addr), "name": name, "status": "proposed", "conv": "auto", "conv_evidence": "auto:paramid",
                     "subsystem": name.split("_")[0], "evidence": ev})
    json.dump({"batch": a.batch, "author": a.author, "functions": rows, "conflicts": conflicts, "held": held},
              sys.stdout, indent=1)
    print("rows %d, conflicts %d, held %d" % (len(rows), len(conflicts), len(held)), file=sys.stderr)


if __name__ == "__main__":
    main()
