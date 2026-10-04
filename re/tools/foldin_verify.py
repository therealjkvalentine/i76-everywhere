r"""foldin_verify.py - fold-in round 2: check every extracted prior-work claim against the pristine exe and the map.

    python tools\foldin_verify.py <claims.json> --out foldin\round2\ledger

<claims.json> is the extraction workflow's output: a list of {group, files_read, claims:[...]} (or a flat list of
claims). Nothing here trusts the source: every verdict is computed from the pristine file (md5 9a232dcc) and from
symbols\functions.tsv / globals.tsv.

Per claim:
  class        gen_tables.Image.klass: text / rdata / init / bss / iat / outside (field offsets: n/a)
  shifted      inside a .text patch cluster of any known patched build (binaries\diff-9a232dcc-vs-*.tsv): an
               instruction address there does not transfer 1:1 (gate P build-shifted); tagged with the builds
  bytes        when the source quoted original bytes: match / DIFFER against the pristine file
  map          the map's row at that address: exact function start, inside function X (+off), exact global, or none
  fn_start     for role=function: is the address a function start in the map
  verdict      one of
                 agrees      the map already names it and the names normalise to the same words
                 differs     the map names it differently (a naming or a semantic conflict: read both)
                 new-anchor  not in the map, class matches the role, not shifted, bytes match or not quoted
                 shifted     instruction address inside a patch cluster: needs a pristine-side re-anchor
                 bytes-mismatch  quoted bytes do not match pristine (other build, or wrong)
                 role-mismatch   e.g. a 'function' that is not a function start, a 'global' in .text
                 refuted-in-source  the source itself marks it refuted / a dead end (kept as a finding)
                 field       struct offset: not checkable against the exe here (listed for the struct owner)
Outputs: <out>.tsv (one row per claim), <out>.json, <out>-summary.md.
"""
import argparse, csv, glob, json, os, re, sys
M = r"C:\Users\james\i76-map"
sys.path.insert(0, os.path.join(M, "tools"))
from gen_tables import Image  # noqa: E402

PRISTINE = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"


def norm(n):
    return re.sub(r"[^a-z0-9]", "", str(n or "").lower())


def words(n):
    n = re.sub(r"^(FUN|DAT|thunk|sub)_", "", str(n or ""))
    n = re.sub(r"([a-z])([A-Z])", r"\1 \2", n)
    return set(w for w in re.split(r"[^a-z0-9]+", n.lower()) if len(w) > 2)


def load_clusters():
    out = []
    for p in glob.glob(os.path.join(M, "binaries", "diff-9a232dcc-vs-*.tsv")):
        tag = os.path.basename(p)[len("diff-9a232dcc-vs-"):-4]
        for line in open(p, encoding="utf-8"):
            if line.startswith("#") or line.startswith("section\t") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            if f[0] in (".text", ".text-tail"):
                out.append((int(f[2], 16), int(f[3], 16), tag))
    return out


def load_map():
    funcs, globs = [], {}
    for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        funcs.append((int(r["addr"], 16), int(r["size"] or 0), r["name"], r["status"]))
    funcs.sort()
    for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "globals.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        globs[int(r["addr"], 16)] = (r["name"], r["status"])
    return funcs, globs


def find_func(funcs, a):
    import bisect
    i = bisect.bisect_right([f[0] for f in funcs], a) - 1
    if i >= 0:
        s, size, name, st = funcs[i]
        if s <= a < s + max(size, 1):
            return s, name, st
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("claims")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = json.load(open(a.claims, encoding="utf-8"))
    claims = []
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "claims" in raw[0]:
        for g in raw:
            for c in g["claims"]:
                c = dict(c); c["group"] = g.get("group", ""); claims.append(c)
    else:
        claims = raw
    img = Image(PRISTINE)
    clusters = load_clusters()
    funcs, globs = load_map()
    rows = []
    for i, c in enumerate(claims):
        r = dict(c)
        r["ledger_id"] = "R2-%04d" % (i + 1)
        try:
            va = int(str(c.get("addr", "")).strip(), 16)
        except ValueError:
            va = None
        role = c.get("addr_role", "other")
        st = c.get("status_in_source", "unclear")
        r["class"] = r["shifted"] = r["bytes"] = r["map"] = r["map_name"] = r["map_status"] = ""
        if role == "field" or va is None or va < 0x400000:
            r["verdict"] = "field" if role == "field" else "unparsed"
            rows.append(r); continue
        klass = img.klass(va) if 0x400000 <= va < 0x66a000 else "outside"
        r["class"] = klass
        sh = sorted(set(t for lo, hi, t in clusters if lo <= va < hi))
        r["shifted"] = ",".join(sh)
        qb = re.sub(r"[^0-9a-fA-F]", "", str(c.get("quoted_bytes") or ""))
        if qb and len(qb) % 2 == 0:
            got = img.data[img.va2off(va):img.va2off(va) + len(qb) // 2].hex() if klass in ("text", "rdata", "init", "iat") else None
            r["bytes"] = "match" if got and got.lower() == qb.lower() else "DIFFER(%s)" % got
        g = globs.get(va)
        f = find_func(funcs, va)
        if g:
            r["map"], r["map_name"], r["map_status"] = "global", g[0], g[1]
        elif f and f[0] == va:
            r["map"], r["map_name"], r["map_status"] = "function-start", f[1], f[2]
        elif f:
            r["map"], r["map_name"], r["map_status"] = "inside %s+0x%x" % (f[1], va - f[0]), f[1], f[2]
        else:
            r["map"] = "none"
        # verdict
        mapped_name = r["map_name"] if r["map"] in ("global", "function-start") else ""
        auto = (not mapped_name) or mapped_name.startswith(("FUN_", "DAT_"))
        if st in ("refuted", "dead-end"):
            v = "refuted-in-source"
        elif r["bytes"].startswith("DIFFER"):
            v = "bytes-mismatch"
        elif sh and klass == "text" and role in ("code_site", "patch_site", "function"):
            v = "shifted"
        elif role == "function" and r["map"] != "function-start":
            v = "role-mismatch"
        elif role == "global" and klass == "text":
            v = "role-mismatch"
        elif not auto:
            cw, mw = words(c.get("name_claimed") or c.get("meaning", "")), words(mapped_name)
            v = "agrees" if (norm(c.get("name_claimed")) and norm(c.get("name_claimed")) == norm(mapped_name)) or (cw & mw) else "differs"
        else:
            v = "new-anchor"
        r["verdict"] = v
        rows.append(r)
    os.makedirs(os.path.dirname(os.path.join(M, a.out)), exist_ok=True)
    base = os.path.join(M, a.out)
    cols = ["ledger_id", "group", "file", "line", "addr", "addr_role", "class", "shifted", "bytes", "map", "map_name", "map_status",
            "verdict", "name_claimed", "meaning", "evidence_in_source", "status_in_source", "source_build", "quote"]
    with open(base + ".tsv", "w", encoding="utf-8", newline="") as fh:
        fh.write("# fold-in round 2 ledger - generated by tools/foldin_verify.py; verdicts computed from the pristine exe (md5 9a232dcc) and the map, never from the source\n")
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: str(r.get(k, "")).replace("\t", " ").replace("\n", " ") for k in cols})
    json.dump(rows, open(base + ".json", "w", encoding="utf-8"), indent=1)
    from collections import Counter
    cv = Counter(r["verdict"] for r in rows)
    ce = Counter(r.get("evidence_in_source", "") for r in rows)
    addrs = len(set(r.get("addr", "").lower() for r in rows))
    with open(base + "-summary.md", "w", encoding="utf-8") as fh:
        fh.write("# Fold-in round 2 - verification summary\n\n%d claims over %d distinct addresses.\n\n" % (len(rows), addrs))
        fh.write("| verdict | n |\n|---|---|\n" + "".join("| %s | %d |\n" % kv for kv in cv.most_common()) + "\n")
        fh.write("| evidence in source | n |\n|---|---|\n" + "".join("| %s | %d |\n" % kv for kv in ce.most_common()) + "\n")
    print("claims %d, addresses %d" % (len(rows), addrs))
    for k, n in cv.most_common():
        print("  %-18s %d" % (k, n))


if __name__ == "__main__":
    main()
