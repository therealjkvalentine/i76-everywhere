r"""foldin_batch.py - turn the fold-in round-2 ledger (tools\foldin_verify.py output) into a merge batch of `ported`
rows, in the format of the first fold-in (status\tasks\p5-foldin-merge.batch.json).

    python tools\foldin_batch.py foldin\round2\ledger.json --out status\tasks\foldin-r2.batch.json

Gate P: every row enters ported.tsv only (never functions.tsv / globals.tsv). Entry types:
  proposed       verdict new-anchor: a claim the map does not have yet
  ported-static  new-anchor whose source quoted the original bytes and they match the pristine file
  note           verdict agrees: a second instance of something the map already holds
  build-shifted  verdict shifted: an instruction address inside a patch cluster of a patched build
  finding        verdict refuted-in-source / differs / role-mismatch: the sentence says what disagrees with what
Field (struct offset) claims are not rows here: they go to foldin\round2\fields.tsv for the struct owner.
"""
import argparse, json, os, re

M = r"C:\Users\james\i76-map"
MD5 = "9a232dcc2c164648cff20c414c1f9698"
CONF = {"measured-live": "high", "patched-and-observed": "high", "static-disasm": "medium", "hypothesis": "low", "unclear": "low"}
KIND = {"function": "function", "global": "global", "constant": "global", "string": "global", "iat": "global",
        "code_site": "site", "patch_site": "site", "other": "note"}
CLASS_OK = {"text", "rdata", "init", "bss", "iat"}


def build_tag(s):
    s = (s or "").lower()
    if "60abf7bc" in s or "aio" in s or "camorig" in s:
        return "aio-60abf7bc"
    if "4fabc303" in s or "sandbox" in s or "uncap" in s:
        return "sandbox-4fabc303"
    if "6319abf7" in s or "portable" in s:
        return "portable-6319abf7"
    if "58d9dec0" in s:
        return "pristine+p1-58d9dec0"
    if "9a232dcc" in s or "pristine" in s or "gog" in s or "gold" in s:
        return "pristine-9a232dcc"
    if "nitro" in s or "28b8ae27" in s:
        return "nitro-28b8ae27"
    return "unversioned"


def ident(n):
    n = re.sub(r"[^A-Za-z0-9_]+", "_", str(n or "")).strip("_")
    return n[:48]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = json.load(open(os.path.join(M, a.ledger), encoding="utf-8"))
    ported, fields = [], []
    seq = 108                      # round 1 used L001..L108
    for r in rows:
        v = r["verdict"]
        if v in ("field", "unparsed"):
            fields.append(r)
            continue
        seq += 1
        lid = "L%03d" % seq
        tag = build_tag(r.get("source_build"))
        src = r.get("file", "")
        base = os.path.basename(src)
        quote = str(r.get("quote", ""))[:300]
        claim = str(r.get("meaning", ""))[:300]
        ev = {"kind": "ported", "source": src, "source_instance": "%s:%s" % (base, tag), "build_tag": tag, "quote": quote,
              "claim": claim, "ledger_id": lid, "round2_id": r["ledger_id"], "prior_conf": CONF.get(r.get("evidence_in_source"), "low"),
              "md5": MD5, "foldin": "round2/ledger.tsv", "method": "verbatim quote extracted by the round-2 readers; verdict by tools/foldin_verify.py"}
        cls = r.get("class") if r.get("class") in CLASS_OK else ""
        row = {"ledger_id": lid, "round2_id": r["ledger_id"], "source": src, "source_instance": ev["source_instance"], "build_tag": tag,
               "kind": KIND.get(r.get("addr_role"), "note"), "class": cls, "name": ident(r.get("name_claimed")),
               "claim": claim, "prior_conf": ev["prior_conf"], "quote": quote, "addr": r["addr"].lower() if cls else "",
               "note": "round-2 row %s; map: %s %s; role %s; evidence in source: %s; status in source: %s" % (r["ledger_id"], r.get("map", ""), r.get("map_name", ""), r.get("addr_role"), r.get("evidence_in_source"), r.get("status_in_source")),
               "evidence": [ev]}
        if v == "new-anchor":
            row["entry"] = "proposed"
            if str(r.get("bytes", "")) == "match" and cls in ("text", "rdata", "init"):
                row["entry"] = "ported-static"
                row["evidence"].append({"kind": "ported-static", "addr": row["addr"], "bytes": re.sub(r"[^0-9a-fA-F]", "", r.get("quoted_bytes", "")).lower(),
                                        "build_tag": tag, "md5": MD5, "claim": "original bytes quoted by the source match the pristine file"})
        elif v == "agrees":
            row["entry"] = "note"
        elif v == "shifted":
            row["entry"] = "build-shifted"
            row["note"] += "; inside a .text patch cluster of " + r.get("shifted", "")
        else:
            row["entry"] = "finding"
            if v == "refuted-in-source":
                row["finding"] = "the source itself records this as %s: %s" % (r.get("status_in_source"), claim)
            elif v == "differs":
                row["finding"] = "names or meaning differ: the map has %s (%s), the source says %r (%s)" % (r.get("map_name"), r.get("map_status"), r.get("name_claimed") or claim, r.get("evidence_in_source"))
            elif v == "bytes-mismatch":
                row["finding"] = "quoted bytes do not match the pristine file (%s): another build, or a transcription error" % r.get("bytes")
            else:
                row["finding"] = "role mismatch: the source calls %s a %s but the map has it %s" % (r["addr"], r.get("addr_role"), r.get("map"))
        if not row["addr"] and row["entry"] in ("ported-static", "build-shifted"):
            row["entry"] = "finding"; row["finding"] = "no gate-A class for %s" % r["addr"]
        ported.append(row)
    batch = {"batch": "foldin-r2", "author": "main session (fold-in round 2, 2026-09-26)", "functions": [], "globals": [], "ported": ported}
    json.dump(batch, open(os.path.join(M, a.out), "w", encoding="utf-8"), indent=1)
    with open(os.path.join(M, "foldin", "round2", "fields.tsv"), "w", encoding="utf-8") as fh:
        fh.write("ledger_id\tfile\tline\tfield_base\taddr\tname_claimed\tmeaning\tevidence_in_source\tstatus_in_source\tquote\n")
        for r in fields:
            fh.write("\t".join(str(r.get(k, "")).replace("\t", " ").replace("\n", " ") for k in
                               ("ledger_id", "file", "line", "field_base", "addr", "name_claimed", "meaning", "evidence_in_source", "status_in_source", "quote")) + "\n")
    from collections import Counter
    print("ported rows %d; fields %d" % (len(ported), len(fields)), dict(Counter(p["entry"] for p in ported)))


if __name__ == "__main__":
    main()
