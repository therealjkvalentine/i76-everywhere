#!/usr/bin/env python3
r"""Gate R for the data track: decode -> encode over the full corpus, byte compare, and byte coverage per format.

    python data\\fmt\\roundtrip.py [--out data\\roundtrip.json]

Corpus (read-only):
  * the extracted archive  recon-2026-09-04\\recon\\formats\\zfs_out  (6,116 payloads, decoded by i76fmt.zfs/lzo)
  * the pristine sandbox   sandbox-gog\\main\\app  (loose .msn/.vcf/.def/.fnt/... ; ADDON\\ is recorded separately
    because it can carry user-modified copies)
Every file of a modelled family goes bytes -> typed values -> bytes. Coverage counts each byte once, as one of
cited / typed / unused / unknown (schema.py). Output shape follows status\\roundtrip.json (families[], totals,
verdict) plus a per-format coverage block.
"""
import os, sys, json, time, hashlib, argparse, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bwd2x  # noqa: E402
import formats  # noqa: E402

MAP = os.path.dirname(os.path.dirname(HERE))
ZOUT = os.path.join(MAP, "recon-2026-09-04", "recon", "formats", "zfs_out")
SANDBOX = os.path.join(MAP, "sandbox-gog", "main", "app")


def first_diff(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i, sum(1 for j in range(i, n) if a[j] != b[j]) + abs(len(a) - len(b))
    if len(a) == len(b):
        return None, 0
    return n, abs(len(a) - len(b))


SKIP_EXT = {".dll", ".exe", ".zfs", ".pdf", ".htm", ".ico", ".ttf", ".fot", ".hashdb", ".info", ".zip", ".doc",
            ".txt", ".ini", ".cur", ".ovl", ".mp3", ".bmp", ".log", ".bak", ".conf", ".ps1", ".bat"}
# .zfs: the archive container is gate R of tools\i76fmt (other session); its 6,116 payloads are covered via zfs_out.
# .dll/.exe/.ovl: code. .pdf/.htm/.doc/.txt/.ico/.ttf/.fot/.cur/.ini/.info/.hashdb/.zip: GOG packaging and docs.
# .mp3: GOG's replacement music (played by the modern audiere wrapper). .bmp: SP256\ launcher art (Splash.exe).


def corpus():
    out = []
    for n in sorted(os.listdir(ZOUT)):
        out.append(("zfs:" + n, os.path.join(ZOUT, n)))
    for root, _, fs in os.walk(SANDBOX):
        for f in sorted(fs):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, SANDBOX)
            if os.path.splitext(f)[1].lower() in SKIP_EXT:
                continue
            out.append(("sandbox:" + rel.replace("\\", "/"), p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(MAP, "data", "roundtrip.json"))
    ap.add_argument("--only", default=None, help="restrict to one extension, e.g. .msn")
    a = ap.parse_args()
    t0 = time.time()
    fams = {}
    for label, p in corpus():
        ext = os.path.splitext(p)[1].lower()
        if a.only and ext != a.only:
            continue
        handler = formats.handler_for(ext, p)
        if handler is None:
            continue
        fam = fams.setdefault(handler.name, {"family": handler.name, "files": 0, "bytes": 0, "parsed": 0,
                                             "parse_errors": [], "diff_files": 0, "diffs": [],
                                             "coverage": {"cited": 0, "typed": 0, "unused": 0, "unknown": 0},
                                             "per_chunk": {}, "method": handler.method})
        data = open(p, "rb").read()
        fam["files"] += 1; fam["bytes"] += len(data)
        try:
            v = handler.decode(data, ext)
            out = handler.encode(v)
            cov, per = handler.coverage(v)
        except Exception as ex:  # noqa: BLE001
            fam["parse_errors"].append({"path": label, "error": "%s: %s" % (type(ex).__name__, ex)})
            continue
        fam["parsed"] += 1
        for k, n in cov.items():
            fam["coverage"][k] += n
        for tag, d in (per or {}).items():
            pc = fam["per_chunk"].setdefault(tag, {"cited": 0, "typed": 0, "unused": 0, "unknown": 0})
            for k, n in d.items():
                pc[k] += n
        for e in handler.errors(v):
            if len(fam["parse_errors"]) < 50:
                fam["parse_errors"].append({"path": label, "error": "body %s: %s" % e})
        off, n = first_diff(data, out)
        if off is not None:
            fam["diff_files"] += 1
            if len(fam["diffs"]) < 50:
                fam["diffs"].append({"path": label, "first_diff": off, "diff_bytes": n, "len_in": len(data), "len_out": len(out)})
    families = sorted(fams.values(), key=lambda f: -f["bytes"])
    for f in families:
        tot = sum(f["coverage"].values()) or 1
        f["coverage_pct"] = {k: round(100.0 * n / tot, 2) for k, n in f["coverage"].items()}
        f["accounted_pct"] = round(100.0 * tot / (f["bytes"] or 1), 2)
    rep = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": "data/fmt/roundtrip.py",
           "corpus": {"zfs_out": ZOUT, "sandbox": SANDBOX}, "families": families}
    rep["totals"] = {"families": len(families), "files": sum(f["files"] for f in families),
                     "parsed": sum(f["parsed"] for f in families), "diff_files": sum(f["diff_files"] for f in families),
                     "parse_errors": sum(len(f["parse_errors"]) for f in families),
                     "bytes": sum(f["bytes"] for f in families),
                     "coverage": {k: sum(f["coverage"][k] for f in families) for k in ("cited", "typed", "unused", "unknown")},
                     "seconds": round(time.time() - t0, 1)}
    rep["verdict"] = "PASS" if rep["totals"]["diff_files"] == 0 and rep["totals"]["parse_errors"] == 0 else "FAIL"
    tmp = a.out + ".tmp"
    json.dump(rep, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, a.out)
    assert json.load(open(a.out, encoding="utf-8"))["verdict"] == rep["verdict"]
    print("%-10s %6s %11s %6s %5s %5s  %7s %7s %7s %7s" % ("family", "files", "bytes", "parsed", "diffs", "errs", "cited%", "typed%", "unused%", "unk%"))
    for f in families:
        c = f["coverage_pct"]
        print("%-10s %6d %11d %6d %5d %5d  %7.2f %7.2f %7.2f %7.2f" % (f["family"], f["files"], f["bytes"], f["parsed"], f["diff_files"],
                                                                      len(f["parse_errors"]), c["cited"], c["typed"], c["unused"], c["unknown"]))
    print("gate R (data track) %s: %s -> %s" % (rep["verdict"], json.dumps(rep["totals"]), a.out))
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
