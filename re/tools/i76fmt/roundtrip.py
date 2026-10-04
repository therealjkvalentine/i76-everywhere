#!/usr/bin/env python3
"""Gate R: parse -> serialise -> parse over the full game-data corpus; 0 byte diffs expected.

    python tools\\i76fmt\\roundtrip.py [--game C:\\Users\\james\\i76-uncap-lab\\game] [--out status\\roundtrip.json]
                                     [--repack-out <path>] [--quick]

Corpus (method doc gate R): I76.ZFS (6,116 payloads: archive-level byte identity + every decoded payload of a
modelled family re-serialised + stored-mode repack of all payloads read back), 80 .msn (+1 .lvl), 81 .ter,
loose .vcf/.vsf (7 + 1; 293 more .vcf inside the archive), 3 .fnt, 14 .frc, loose .cbk/.map.
Every family reports files, bytes, parse errors and byte diffs (first offset, differing byte count); the game
folder is opened read-only and nothing is written there. The LZO recompression identity is recorded as
"not measured" (no LZO 1.00 compressor; gate R makes it a measurement, not a requirement).
Exit 0 when every family has 0 diffs and 0 parse errors, 1 otherwise.
"""
import os, sys, json, time, hashlib, argparse, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from i76fmt import zfs as zfsmod, bwd2, ter, images, fnt, frc  # noqa: E402

BWD2_EXT = {".msn", ".lvl", ".vcf", ".vsf", ".sdf", ".vdf", ".wdf", ".gdf", ".xdf", ".vtf", ".cdf"}


def first_diff(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            break
    else:
        i = n
        if len(a) == len(b):
            return None, 0
    ndiff = sum(1 for j in range(n) if a[j] != b[j]) + abs(len(a) - len(b))
    return i, ndiff


def rt_bytes(data, ext):
    """Return (ok, detail) for parse -> serialise -> parse on one blob of family ext."""
    ext = ext.lower()
    if ext in BWD2_EXT:
        d = bwd2.parse(data); s = bwd2.serialise(d); bwd2.parse(s)
    elif ext == ".ter":
        d = ter.parse(data); s = ter.serialise(d); ter.parse(s)
    elif ext in images.PARSERS:
        d = images.parse(data, ext); s = images.serialise(d, ext); images.parse(s, ext)
    elif ext == ".fnt":
        d = fnt.parse(data); s = fnt.serialise(d); fnt.parse(s)
    elif ext == ".frc":
        d = frc.parse(data); s = frc.serialise(d); frc.parse(s)
    else:
        return None, "unmodelled"
    off, n = first_diff(data, s)
    return (off is None), {"first_diff": off, "diff_bytes": n, "len_in": len(data), "len_out": len(s)}


def family(name):
    return {"family": name, "files": 0, "bytes": 0, "parsed": 0, "parse_errors": [], "diff_files": 0, "diffs": [],
            "method": "parse -> serialise -> parse; byte compare of the serialised blob against the input"}


def run_files(fam, paths, ext_of=None):
    for p in paths:
        data = open(p, "rb").read()
        fam["files"] += 1; fam["bytes"] += len(data)
        ext = ext_of or os.path.splitext(p)[1].lower()
        try:
            ok, det = rt_bytes(data, ext)
        except Exception as ex:
            fam["parse_errors"].append({"path": p, "error": "%s: %s" % (type(ex).__name__, ex)}); continue
        fam["parsed"] += 1
        if ok is False:
            fam["diff_files"] += 1; det["path"] = p; fam["diffs"].append(det)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=r"C:\Users\james\i76-uncap-lab\game")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(HERE)), "status", "roundtrip.json"))
    ap.add_argument("--repack-out", default=None, help="also write the stored-mode repack to this path (never inside --game)")
    ap.add_argument("--quick", action="store_true", help="skip the archive payload loop (directory + loose files only)")
    a = ap.parse_args()
    G = a.game
    if a.repack_out and os.path.abspath(a.repack_out).lower().startswith(os.path.abspath(G).lower()):
        print("REFUSE: --repack-out inside the game folder"); return 2
    t0 = time.time()
    report = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "game": G, "families": [], "corpus": {},
              "lzo_recompression_identity": "not measured: no LZO 1.00 compressor available (gate R records it, never requires it)",
              "tool": "tools/i76fmt/roundtrip.py", "i76fmt_version": "0.1.0"}

    # ---- I76.ZFS archive level ------------------------------------------------------------------------------
    zp = os.path.join(G, "I76.ZFS")
    raw = open(zp, "rb").read()
    fam = family("zfs-archive"); fam["files"] = 1; fam["bytes"] = len(raw)
    fam["md5"] = hashlib.md5(raw).hexdigest()
    fam["method"] = "zfs.parse -> zfs.serialise (offsets/ids/flags re-emitted as parsed, gaps copied and counted) -> byte compare -> zfs.parse again -> directory compare"
    z = zfsmod.parse(raw)
    s = zfsmod.serialise(z)
    off, n = first_diff(raw, s)
    fam["parsed"] = 1
    if off is not None:
        fam["diff_files"] = 1; fam["diffs"].append({"path": zp, "first_diff": off, "diff_bytes": n, "len_in": len(raw), "len_out": len(s)})
    z2 = zfsmod.parse(s)
    same_dir = [(e.name_raw, e.offset, e.id, e.size, e.timestamp, e.flags) for e in z.entries] == \
               [(e.name_raw, e.offset, e.id, e.size, e.timestamp, e.flags) for e in z2.entries]
    fam["directory"] = {"blocks": len(z.blocks), "per_block": z.per_block, "n_files_header": z.n_files,
                        "entries": len(z.entries), "xor_key": z.xor_key, "unmodelled_gap_bytes": getattr(z, "unmodelled_bytes", 0),
                        "trailing_bytes": len(z.trailing), "reparse_directory_equal": same_dir,
                        "method": "directory chain walk from header dir0; count = non-empty name slots"}
    report["families"].append(fam)
    report["corpus"]["zfs_payloads"] = len(z.entries)

    # ---- payloads ---------------------------------------------------------------------------------------------
    if not a.quick:
        pf = family("zfs-payloads"); pf["method"] = "zfs.read (stored / LZO1X / LZO1Y per flags) then family round trip for modelled extensions"
        by_method = {}
        by_ext = {}
        decoded = []
        for e in z.entries:
            m = e.method
            by_method[m] = by_method.get(m, 0) + 1
            pf["files"] += 1; pf["bytes"] += e.size
            try:
                d = z.read(e)
            except Exception as ex:
                pf["parse_errors"].append({"path": "I76.ZFS:" + e.name, "error": "%s: %s" % (type(ex).__name__, ex)}); continue
            decoded.append((e.name, d))
            ext = os.path.splitext(e.name)[1].lower()
            st = by_ext.setdefault(ext, {"n": 0, "modelled": 0, "diffs": 0, "errors": 0})
            st["n"] += 1
            try:
                ok, det = rt_bytes(d, ext)
            except Exception as ex:
                st["errors"] += 1
                pf["parse_errors"].append({"path": "I76.ZFS:" + e.name, "error": "%s: %s" % (type(ex).__name__, ex)}); continue
            if ok is None:
                continue
            st["modelled"] += 1
            pf["parsed"] += 1
            if not ok:
                st["diffs"] += 1; pf["diff_files"] += 1; det["path"] = "I76.ZFS:" + e.name; pf["diffs"].append(det)
        pf["decoded"] = len(decoded)
        pf["by_method"] = {{0: "stored", 2: "lzo1x", 4: "lzo1y"}.get(k, str(k)): v for k, v in sorted(by_method.items())}
        pf["by_ext"] = by_ext
        report["families"].append(pf)

        # stored-mode repack (the archive gate): every payload method 0, read back, byte compare
        rf = family("zfs-repack-stored"); rf["method"] = "zfs.repack_stored(all decoded payloads, method 0) -> zfs.parse -> zfs.read each -> compare with the decoded original"
        packed = zfsmod.repack_stored(decoded)
        rf["files"] = 1; rf["bytes"] = len(packed)
        zr = zfsmod.parse(packed)
        rf["parsed"] = 1
        ents = zr.entries
        rf["entries"] = len(ents)
        bad = 0
        for (name, d), e in zip(decoded, ents):
            if e.name != name or e.method != 0 or zr.read(e) != d:
                bad += 1
                if len(rf["diffs"]) < 20:
                    rf["diffs"].append({"path": "repack:" + name, "first_diff": first_diff(d, zr.read(e))[0]})
        rf["diff_files"] = bad
        rf["header"] = {"n_files": zr.n_files, "blocks": len(zr.blocks), "size_vs_original": len(packed) - len(raw)}
        if a.repack_out:
            with open(a.repack_out, "wb") as fh:
                fh.write(packed)
            rf["written"] = {"path": a.repack_out, "md5": hashlib.md5(packed).hexdigest(),
                             "readback_equal": open(a.repack_out, "rb").read() == packed}
        report["families"].append(rf)

    # ---- loose files ------------------------------------------------------------------------------------------
    def files(patterns):
        out = set()
        for pat in patterns:
            for p in glob.glob(os.path.join(G, pat), recursive=True):
                out.add(os.path.normpath(p))
        return sorted(out, key=str.lower)

    msn = [p for p in files(["**/*.msn", "**/*.MSN"]) if p.lower().endswith(".msn")]
    lvl = [p for p in files(["**/*.lvl"]) if p.lower().endswith(".lvl")]
    terf = [p for p in files(["**/*.ter", "**/*.TER"]) if p.lower().endswith(".ter")]
    vcf = [p for p in files(["**/*.vcf", "**/*.vsf"]) if p.lower().endswith((".vcf", ".vsf"))]
    fnts = [p for p in files(["*.fnt", "*.FNT"]) if p.lower().endswith(".fnt")]
    frcs = [p for p in files(["force/*.frc", "force/*.FRC"]) if p.lower().endswith(".frc")]
    cbk = [p for p in files(["**/*.cbk"]) if p.lower().endswith(".cbk")]
    # only the ADDON binary .map is an image; root *.map files are the text input-binding grammar
    maps = [p for p in files(["ADDON/*.map"]) if p.lower().endswith(".map")]
    for name, paths in (("msn", msn), ("lvl", lvl), ("ter", terf), ("vcf-vsf-loose", vcf), ("fnt", fnts), ("frc", frcs),
                        ("cbk-loose", cbk), ("map-loose", maps)):
        fm = family(name)
        run_files(fm, paths)
        report["families"].append(fm)
        report["corpus"][name] = len(paths)

    tot_diff = sum(f["diff_files"] for f in report["families"])
    tot_err = sum(len(f["parse_errors"]) for f in report["families"])
    report["totals"] = {"families": len(report["families"]), "files": sum(f["files"] for f in report["families"]),
                        "parsed": sum(f["parsed"] for f in report["families"]), "diff_files": tot_diff, "parse_errors": tot_err,
                        "seconds": round(time.time() - t0, 1)}
    report["verdict"] = "PASS" if tot_diff == 0 and tot_err == 0 else "FAIL"
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    os.replace(tmp, a.out)
    back = json.load(open(a.out, encoding="utf-8"))
    assert back["verdict"] == report["verdict"], "readback mismatch"
    for f in report["families"]:
        print("%-18s files=%-5d parsed=%-5d diffs=%-3d errors=%d" % (f["family"], f["files"], f["parsed"], f["diff_files"], len(f["parse_errors"])))
    print("gate R %s: %s (%.1fs) -> %s" % (report["verdict"], json.dumps(report["totals"]), report["totals"]["seconds"], a.out))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
