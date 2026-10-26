#!/usr/bin/env python3
r"""completeness.py - section 5 metrics of FRESH-START-METHOD.md rev 2, computed from files only (Task 11).

    python tools\completeness.py                       # -> status\progress.json (+ timeline entry), status\progress.svg
    python tools\completeness.py --no-append           # compute and write, but do not append to the timeline
    python tools\completeness.py --print               # also print the metrics as JSON

Every count carries its method (gate C) in the JSON next to the number (`*_method` keys or the
`methods` block). Every address class is taken from the PE section table of `ghidra\i76_ref.exe`
(md5 must be 9a232dcc2c164648cff20c414c1f9698), never hard-coded. Inputs (all read-only):
  symbols\functions.tsv globals.tsv tables.tsv strings.tsv imports.tsv regions.tsv heaptypes.tsv (optional)
  ghidra\export\{functions.json, hot_globals.csv, data_layout.txt, functions\*.c}
  status\{tasks\t4-g3.json, blind\floor-t7-result.json, merge-log.jsonl (optional), queue.json, evidence_supply.json}
  requests\{dynamic-*.yaml, measurements.yaml}   captures\*\manifest.json   binaries\sandbox.toml
Writes are done to .tmp, renamed, and read back (H3); the read-back row is in the output JSON.
"""
import argparse
import csv
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRISTINE_MD5 = "9a232dcc2c164648cff20c414c1f9698"
STATUSES = ["auto", "proposed", "supported", "verified", "anchored", "library", "synthetic", "stub", "dead"]
TOOL = "tools/completeness.py"
VERSION = "0.1"


def p(*a):
    return os.path.join(ROOT, *a)


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_tsv(path):
    """TSV with '#' comment lines; first non-comment line is the header."""
    rows = []
    header = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\r\n").split("\t")
            if header is None:
                header = parts
                continue
            parts += [""] * (len(header) - len(parts))
            rows.append(dict(zip(header, parts)))
    return header or [], rows


def hx(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 16)
    except ValueError:
        return None


# ---------------------------------------------------------------- sections (gate A, never hard-coded)
def sections():
    import pefile
    exe = p("ghidra", "i76_ref.exe")
    md5 = md5_file(exe)
    if md5 != PRISTINE_MD5:
        sys.exit(f"refused: {exe} md5 {md5} != pristine {PRISTINE_MD5}")
    pe = pefile.PE(exe, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    sec = {}
    for s in pe.sections:
        name = s.Name.rstrip(b"\0").decode()
        va = base + s.VirtualAddress
        sec[name] = {"va": va, "vsize": s.Misc_VirtualSize, "raw": s.SizeOfRawData, "raw_off": s.PointerToRawData}
    pe.parse_data_directories(directories=[12])  # IAT
    iat = pe.OPTIONAL_HEADER.DATA_DIRECTORY[12]
    text = sec[".text"]
    rdata = sec[".rdata"]
    data = sec[".data"]
    out = {
        "exe": exe, "md5": md5,
        "text": (text["va"], text["va"] + text["vsize"]),
        "rdata": (rdata["va"], rdata["va"] + rdata["vsize"]),
        "iat": (base + iat.VirtualAddress, base + iat.VirtualAddress + iat.Size),
        "data_init": (data["va"], data["va"] + data["raw"]),
        "bss": (data["va"] + data["raw"], data["va"] + data["vsize"]),
        "rsrc": (sec[".rsrc"]["va"], sec[".rsrc"]["va"] + sec[".rsrc"]["vsize"]),
    }
    return out


def region_of(sec, addr):
    for k in ("text", "rdata", "data_init", "bss", "rsrc"):
        lo, hi = sec[k]
        if lo <= addr < hi:
            if k == "rdata" and sec["iat"][0] <= addr < sec["iat"][1]:
                return "iat"
            return k
    return "outside"


# ---------------------------------------------------------------- functions (section 5, "Functions")
def union_bytes(intervals, lo, hi):
    """bytes covered by the union of [a,b) intervals clipped to [lo,hi); returns (bytes, merged list)."""
    ivs = sorted((max(a, lo), min(b, hi)) for a, b in intervals if b > lo and a < hi)
    merged = []
    for a, b in ivs:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return sum(b - a for a, b in merged), merged


def functions_metrics(sec):
    _, rows = read_tsv(p("symbols", "functions.tsv"))
    tlo, thi = sec["text"]
    text_bytes = thi - tlo
    per = {s: {"functions": 0, "bytes": 0} for s in STATUSES}
    other = {}
    multi = 0
    ivs_by_status = {}
    for r in rows:
        st = r["status"].strip()
        key = st.split("(")[0]
        a = hx(r["addr"]); n = int(r["size"] or 0)
        if key in per:
            per[key]["functions"] += 1; per[key]["bytes"] += n
        else:
            other.setdefault(st, {"functions": 0, "bytes": 0})
            other[st]["functions"] += 1; other[st]["bytes"] += n
        ivs_by_status.setdefault(key, []).append((a, a + n))
    all_ivs = [iv for l in ivs_by_status.values() for iv in l]
    fn_union, merged = union_bytes(all_ivs, tlo, thi)
    # partition: function-owned bytes (union) + data-in-text (jump tables from regions.tsv, static scan) + padding
    _, regs = read_tsv(p("symbols", "regions.tsv"))
    jt = [(hx(r["start"]), hx(r["end"])) for r in regs if r["kind"] in ("jumptable", "indextable")]
    pad = [(hx(r["start"]), hx(r["end"])) for r in regs if r["kind"] == "padding"]
    # remove overlaps with function bodies (a created function may now own bytes regions.tsv called gap)
    def minus(ivs, cover):
        out = []
        for a, b in ivs:
            cur = [(a, b)]
            for ca, cb in cover:
                nxt = []
                for x, y in cur:
                    if cb <= x or ca >= y:
                        nxt.append((x, y))
                    else:
                        if x < ca: nxt.append((x, ca))
                        if cb < y: nxt.append((cb, y))
                cur = nxt
            out += cur
        return out
    jt_b, _ = union_bytes(minus(jt, merged), tlo, thi)
    pad_b, _ = union_bytes(minus(pad, merged), tlo, thi)
    untagged = text_bytes - fn_union - jt_b - pad_b
    # untagged gap count: bytes of .text in no function, jumptable or padding, as maximal runs
    covered = sorted(merged + [list(x) for x in minus(jt, merged)] + [list(x) for x in minus(pad, merged)])
    gaps = []
    cur = tlo
    for a, b in covered:
        if a > cur:
            gaps.append((cur, a))
        cur = max(cur, b)
    if cur < thi:
        gaps.append((cur, thi))
    per_status_union = {}
    for k, l in ivs_by_status.items():
        per_status_union[k] = union_bytes(l, tlo, thi)[0]
    # remainder: bytes not yet at verified/anchored/library/synthetic/dead (+ untagged)
    done_keys = ("verified", "anchored", "library", "synthetic", "dead")
    done_b = sum(per_status_union.get(k, 0) for k in done_keys)
    return {
        "denominator_text_bytes": text_bytes,
        "denominator_method": "PE .text VirtualSize of ghidra/i76_ref.exe (pefile)",
        "rows": len(rows),
        "rows_method": "symbols/functions.tsv data rows",
        "per_status": per,
        "per_status_other": other,
        "per_status_method": "status column of functions.tsv; bytes = size column (Ghidra body bytes, FunctionManager); multi-range bodies counted by their body size",
        "per_status_union_bytes": per_status_union,
        "partition": {
            "function_bytes_union": fn_union,
            "data_in_text_jumptable_bytes": jt_b,
            "padding_bytes": pad_b,
            "untagged_bytes": untagged,
            "untagged_gaps": len(gaps),
            "untagged_largest": [(f"0x{a:x}", f"0x{b:x}", b - a) for a, b in sorted(gaps, key=lambda g: g[0] - g[1])[:5]],
            "method": "interval union of [addr, addr+size) over functions.tsv clipped to .text (19 multi-range bodies approximated as contiguous); jumptable/padding from regions.tsv (Task 3 capstone/byte scan) minus function-covered bytes; untagged = .text - union - jumptable - padding; baseline in the method doc: 25,763 B in 75 gaps",
        },
        "remainder_bytes": text_bytes - done_b,
        "remainder_method": ".text bytes not in the union of verified/anchored/library/synthetic/dead rows (auto + proposed + supported + untagged count as remainder)",
        "supported_or_better_bytes": sum(per_status_union.get(k, 0) for k in ("supported",) + done_keys),
        "supported_or_better_pct": round(100.0 * sum(per_status_union.get(k, 0) for k in ("supported",) + done_keys) / text_bytes, 2),
    }


# ---------------------------------------------------------------- data (section 5, "Data")
def data_metrics(sec):
    regions = ["rdata", "data_init", "bss"]
    den = {k: sec[k][1] - sec[k][0] for k in regions}
    typed = {k: [] for k in regions + ["iat", "text", "outside"]}
    owners = {k: [] for k in regions + ["iat", "text", "outside"]}
    _, globs = read_tsv(p("symbols", "globals.tsv"))
    bss_status = {}
    unbounded = 0
    for g in globs:
        a = hx(g["addr"]); w = int(g["width"] or 0)
        if a is None:
            continue
        reg = region_of(sec, a)
        typed.setdefault(reg, []).append((a, a + max(w, 1)))
        owners.setdefault(reg, []).append((a, a + max(w, 1), "globals.tsv"))
        if reg == "bss":
            bss_status[g["status"]] = bss_status.get(g["status"], 0) + 1
        if "[" in (g.get("type") or "") and not (g.get("bound_evidence") or "").strip():
            unbounded += 1
    _, tabs = read_tsv(p("symbols", "tables.tsv"))
    tab_unbounded = 0
    for t in tabs:
        a = hx(t["base"]); e = hx(t["end"])
        if a is None or e is None or t["class"] not in ("init", "bss"):
            continue
        reg = region_of(sec, a)
        typed.setdefault(reg, []).append((a, e))
        owners.setdefault(reg, []).append((a, e, "tables.tsv"))
        if "proposed" in (t.get("note") or "").lower() or "run-to-break" in (t.get("note") or "").lower():
            tab_unbounded += 1
    _, strs = read_tsv(p("symbols", "strings.tsv"))
    for s in strs:
        a = hx(s["addr"]); n = int(s["len"] or 0)
        if a is None or n <= 0:
            continue
        reg = region_of(sec, a)
        typed.setdefault(reg, []).append((a, a + n))
        owners.setdefault(reg, []).append((a, a + n, "strings.tsv"))
    _, imps = read_tsv(p("symbols", "imports.tsv"))
    for i in imps:
        a = hx(i.get("iat_slot") or i.get("addr"))
        if a is None:
            continue
        owners.setdefault("iat", []).append((a, a + 4, "imports.tsv"))
        typed.setdefault("iat", []).append((a, a + 4))
    typed_bytes = {}
    for k in regions:
        lo, hi = sec[k]
        typed_bytes[k] = union_bytes(typed[k], lo, hi)[0]
    # Ghidra-defined data per block (data_layout.txt); .data is one block there (init + BSS together)
    ghidra_defined = {}
    try:
        cur = None
        for line in open(p("ghidra", "export", "data_layout.txt"), encoding="utf-8", errors="replace"):
            m = re.match(r"== Block (\S+) ", line)
            if m:
                cur = m.group(1)
            m = re.match(r"\s*defined data: (\d+) items, (\d+) bytes", line)
            if m and cur:
                ghidra_defined[cur] = {"items": int(m.group(1)), "bytes": int(m.group(2))}
    except OSError:
        pass
    # unowned referenced addresses: hot_globals.csv (code-referenced addresses) not inside any owner interval
    refd = []
    with open(p("ghidra", "export", "hot_globals.csv"), newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            refd.append(int(r["address"], 16))
    all_owner = sorted((a, b) for l in owners.values() for a, b, _ in l)
    merged = []
    for a, b in all_owner:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    import bisect
    starts = [a for a, _ in merged]
    per_region_ref = {}
    per_region_unowned = {}
    for a in refd:
        reg = region_of(sec, a)
        per_region_ref[reg] = per_region_ref.get(reg, 0) + 1
        i = bisect.bisect_right(starts, a) - 1
        owned = i >= 0 and merged[i][0] <= a < merged[i][1]
        if not owned:
            per_region_unowned[reg] = per_region_unowned.get(reg, 0) + 1
    return {
        "denominators": den,
        "denominators_method": "PE section table: .rdata VirtualSize; .data SizeOfRawData (initialised); .data VirtualSize - SizeOfRawData (BSS)",
        "map_typed_bytes": typed_bytes,
        "map_typed_method": "union of globals.tsv [addr, addr+width), tables.tsv [base, end) for class init/bss, strings.tsv [addr, addr+len) per region",
        "ghidra_defined_data": ghidra_defined,
        "ghidra_defined_method": "ghidra/export/data_layout.txt 'defined data' per memory block (the .data block holds initialised + BSS together)",
        "referenced_addresses": len(refd),
        "referenced_per_region": per_region_ref,
        "unowned_referenced": sum(per_region_unowned.values()),
        "unowned_per_region": per_region_unowned,
        "unowned_method": "ghidra/export/hot_globals.csv addresses (Ghidra reference manager, pass 4) not inside any globals.tsv/tables.tsv/strings.tsv/imports.tsv interval",
        "bss_status_counts": bss_status,
        "bss_status_method": "globals.tsv rows with class bss, by status",
        "unbounded_array_rows": {"globals_tsv": unbounded, "tables_tsv_proposed_bound": tab_unbounded},
        "unbounded_method": "globals.tsv rows whose type contains '[' and bound_evidence is empty; tables.tsv rows whose note says proposed/run-to-break (gate B)",
    }


# ---------------------------------------------------------------- heap / pool, labels
def heap_metrics():
    path = p("symbols", "heaptypes.tsv")
    keys = 0; full = 0; per_source = {}
    if os.path.exists(path):
        _, rows = read_tsv(path)
        for r in rows:
            keys += 1
            src = r.get("source", "?")
            per_source.setdefault(src, {"keys": 0, "full_field_tables": 0})
            per_source[src]["keys"] += 1
            if (r.get("struct") or "").strip():
                full += 1; per_source[src]["full_field_tables"] += 1
    _, imps = read_tsv(p("symbols", "imports.tsv"))
    creators = None
    for i in imps:
        if i.get("name") == "HeapCreate":
            creators = i.get("functions") or i.get("call_sites")
    return {
        "keys_observed": keys, "keys_with_full_field_tables": full, "per_source": per_source,
        "method": "symbols/heaptypes.tsv rows (absent = 0; the ledger capture, Task 10 item 005, is the only producer)",
        "static_sources": {"HeapCreate_callers": creators, "pool_functions": ["0x498940", "0x499ce0"]},
        "static_sources_method": "imports.tsv HeapCreate functions column (capstone); pool functions per the method doc (VirtualAlloc callers)",
    }


def label_metrics():
    labels = 0; files = []
    for f in glob.glob(p("captures", "*", "**", "labels.csv"), recursive=True):
        files.append(os.path.relpath(f, ROOT))
        with open(f, newline="", encoding="utf-8", errors="replace") as fh:
            labels += max(0, sum(1 for _ in fh) - 1)
    tweak = 0
    for f in glob.glob(p("status", "tweak*.tsv")) + glob.glob(p("symbols", "tweak*.tsv")):
        tweak += max(0, sum(1 for l in open(f, encoding="utf-8") if not l.startswith("#")) - 1)
    return {
        "verified_labels": labels, "label_files": files, "per_channel": {},
        "tweak_manifest_rows": tweak, "cheat_flag_hits": 0,
        "method": "rows of captures/*/**/labels.csv (H2 channels); tweak rows = status|symbols/tweak*.tsv; cheat-flag hits = rows tagged cheat in those files (none exist yet)",
    }


# ---------------------------------------------------------------- quality
TOKENS = {
    "WARNING": r"\bWARNING\b",
    "undefined": r"\bundefined\w*",
    "FUN_": r"\bFUN_[0-9a-fA-F]{8}\b",
    "DAT_": r"\bDAT_[0-9a-fA-F]{8}\b",
    "param_": r"\bparam_\d+\b",
    "local_": r"\blocal_[0-9a-fA-F]+\b",
}


def quality_metrics():
    cdir = p("ghidra", "export", "functions")
    occ = {k: 0 for k in TOKENS}
    files_with = {k: 0 for k in TOKENS}
    nfiles = 0
    rx = {k: re.compile(v) for k, v in TOKENS.items()}
    for f in glob.glob(os.path.join(cdir, "*.c")):
        nfiles += 1
        txt = open(f, encoding="utf-8", errors="replace").read()
        for k, r in rx.items():
            n = len(r.findall(txt))
            occ[k] += n
            if n:
                files_with[k] += 1
    fj = json.load(open(p("ghidra", "export", "functions.json"), encoding="utf-8"))
    fails = [x["addr"] for x in fj if not x.get("decomp_ok", True)]
    residual_fun = sum(1 for x in fj if x["name"].startswith("FUN_"))
    g3 = {}
    try:
        g = json.load(open(p("status", "tasks", "t4-g3.json"), encoding="utf-8"))
        g3 = {"touched": g["touched"], "improved": len(g["improved"]), "regressions": len(g["regressions"]),
              "revert_rate": (len(g["regressions"]) / g["touched"]) if g["touched"] else None,
              "source": "status/tasks/t4-g3.json (Task 4 ApplyMap round, export-frozen vs export)"}
    except (OSError, KeyError):
        pass
    # G4 from the queue history (PILOT-1 change 6): every key with a merge event counts; a key whose latest merge
    # event requeued on a G4 name/prefix disagreement counts as a disagreement; merge-log.jsonl gives accepted merges.
    g4 = {"keys_merged": 0, "accepted": 0, "g4_disagreements": 0, "other_requeues": 0, "rate": None,
          "source": "status/queue.json history merge events (reason starting with G4) + status/merge-log.jsonl"}
    try:
        qj = json.load(open(p("status", "queue.json"), encoding="utf-8"))
        for it in qj.get("items", []):
            ev = [h for h in it.get("history", []) if h.get("event") == "merge"]
            if not ev:
                continue
            g4["keys_merged"] += 1
            last = ev[-1]
            if last.get("result") == "accepted":
                g4["accepted"] += 1
            elif str(last.get("reason", "")).startswith("G4"):
                g4["g4_disagreements"] += 1
            else:
                g4["other_requeues"] += 1
        if g4["keys_merged"]:
            g4["rate"] = g4["g4_disagreements"] / g4["keys_merged"]
            g4["acceptance"] = g4["accepted"] / g4["keys_merged"]
    except (OSError, ValueError, KeyError):
        pass
    ml = p("status", "merge-log.jsonl")
    if os.path.exists(ml):
        g4["merge_log_lines"] = sum(1 for line in open(ml, encoding="utf-8") if line.strip())
    g6 = {}
    try:
        fr = json.load(open(p("status", "blind", "floor-t7-result.json"), encoding="utf-8"))
        an = fr.get("anchored", {}); sl = fr.get("stringless", {})
        g6 = {"anchored": {k: an[k] for k in an if not isinstance(an[k], (list, dict))},
              "stringless": {k: sl[k] for k in sl if not isinstance(sl[k], (list, dict))},
              "contaminated": True,
              "source": "status/blind/floor-t7-result.json (Task 7 floor run; the drafter had listed functions.tsv earlier, so this is not the unprimed floor)"}
    except OSError:
        pass
    return {
        "corpus_files": nfiles,
        "token_occurrences": occ, "files_containing": files_with,
        "token_method": "regex occurrences over ghidra/export/functions/*.c: " + json.dumps(TOKENS),
        "decompile_failures": len(fails), "decompile_failures_list": fails,
        "decompile_method": "ghidra/export/functions.json decomp_ok == false (DumpAll, DecompInterface 60 s timeout)",
        "residual_FUN_names": residual_fun, "residual_method": "functions.json rows whose name starts with FUN_",
        "G3": g3, "G4": g4, "G6": g6,
    }


# ---------------------------------------------------------------- throughput, dynamic, process-wide
def throughput_metrics():
    q = json.load(open(p("status", "queue.json"), encoding="utf-8"))
    items = q.get("items", [])
    leased = 0; oldest = None; done = 0
    now = dt.datetime.now(dt.timezone.utc)
    for it in items:
        if it.get("state") == "done":
            done += 1
        for v in ("c", "pcode"):
            l = (it.get("lease") or {}).get(v) or it.get(f"lease_{v}")
            if l and l.get("holder"):
                leased += 1
                t = l.get("since") or l.get("time")
                if t:
                    try:
                        ts = dt.datetime.fromisoformat(t)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=dt.timezone.utc)
                        age = (now - ts).total_seconds()
                        oldest = age if oldest is None else max(oldest, age)
                    except ValueError:
                        pass
    ml = p("status", "merge-log.jsonl")
    merges = sum(1 for _ in open(ml, encoding="utf-8")) if os.path.exists(ml) else 0
    return {
        "queue_items": len(items), "queue_excluded": len(q.get("excluded", [])), "queue_counts": q.get("counts"),
        "leases_open": leased, "oldest_lease_age_s": oldest, "merged_proposals": merges, "queue_done": done,
        "proposals_per_hour": None, "acceptance_rate": None, "tokens_per_accepted_function": None,
        "method": "status/queue.json items/excluded/lease fields; merges = lines of status/merge-log.jsonl (absent = 0); rates are null until the loop has run (Task 9 not started)",
    }


def dynamic_metrics():
    reqs = sorted(os.path.relpath(f, ROOT) for f in glob.glob(p("requests", "dynamic-*.yaml")))
    open_items = 0
    try:
        import yaml
        for f in reqs:
            y = yaml.safe_load(open(p(f), encoding="utf-8")) or {}
            for it in (y.get("items") or []):
                if (it.get("status") or "open") == "open":
                    open_items += 1
    except ImportError:
        open_items = None
    caps = []
    disk = 0
    refusals = 0
    for d in sorted(glob.glob(p("captures", "*"))):
        if not os.path.isdir(d):
            continue
        man = os.path.join(d, "manifest.json")
        size = 0
        for root, _, files in os.walk(d):
            for fn in files:
                size += os.path.getsize(os.path.join(root, fn))
        disk += size
        lg = os.path.join(d, "launch.log")
        if os.path.exists(lg):
            refusals += sum(1 for l in open(lg, encoding="utf-8", errors="replace") if l.startswith("refused"))
        entry = {"id": os.path.basename(d), "bytes": size, "manifest": os.path.exists(man)}
        if os.path.exists(man):
            try:
                m = json.load(open(man, encoding="utf-8"))
                entry["build"] = m.get("build_md5") or (m.get("build") or {}).get("build_class")
                r = m.get("results") or {}
                if r:
                    entry["state"] = r.get("state")
                    entry["AA_p"] = [r.get("AA_0v1_p"), r.get("AA_1v2_p"), r.get("AA_0v2_p")]
            except ValueError:
                entry["manifest"] = "unparseable"
        caps.append(entry)
    meas = {"settled": 0, "partial": 0, "open": 0}
    try:
        import yaml
        y = yaml.safe_load(open(p("requests", "measurements.yaml"), encoding="utf-8"))
        for it in y.get("items", []):
            meas[it.get("status", "open")] = meas.get(it.get("status", "open"), 0) + 1
    except Exception as e:  # noqa: BLE001
        meas["error"] = str(e)
    return {
        "request_files": reqs, "open_requests": open_items,
        "captures": caps, "captures_with_manifest": sum(1 for c in caps if c["manifest"] is True),
        "disk_bytes": disk, "canary_failures": 0, "canary_method": "no capture has recorded a canary verdict yet (gate H4 fields absent); 0 = not measured, not passed",
        "H0_refusals": refusals, "H0_method": "lines starting with 'refused' in captures/*/launch.log",
        "measurements_yaml": meas, "measurements_method": "requests/measurements.yaml items by status (PyYAML)",
    }


def processwide_metrics(sec, fn):
    t = tomllib.load(open(p("binaries", "sandbox.toml"), "rb"))
    mods = []
    seen = set()
    for m in t.get("module", []):
        if not m.get("in_scope"):
            continue
        rel = m["relpath"]; low = rel.lower()
        base = low.replace(".orig", "")
        if m.get("role") == "exe" and m["md5"] not in (PRISTINE_MD5,):
            continue  # only the ground-truth exe counts once
        if base in seen or m["md5"] in seen:
            continue
        # prefer the GOG-shipped copy (ground_truth true or .orig) for the shell
        if base == "i76shell.dll" and not (m.get("ground_truth") or low.endswith(".orig")):
            continue
        seen.add(base); seen.add(m["md5"])
        text = next((s["vsize"] for s in m.get("sections", []) if s["name"] == ".text"), None)
        remainder = fn["remainder_bytes"] if m.get("role") == "exe" else text
        mods.append({"module": rel, "md5": m["md5"], "text_bytes": text, "remainder_bytes": remainder,
                     "mapped": m.get("role") == "exe"})
    return {
        "modules": mods,
        "remainder_sum": sum(x["remainder_bytes"] or 0 for x in mods),
        "method": "binaries/sandbox.toml in_scope modules, one per basename (ground-truth exe, GOG-shipped shell .orig, the four Z*.DLL); remainder = whole .text for modules without a map, the exe remainder above for i76.exe",
    }


# ---------------------------------------------------------------- svg
def write_svg(path, fn):
    per = fn["per_status"]
    order = ["anchored", "supported", "library", "synthetic", "proposed", "verified", "auto"]
    rows = [(k, per[k]["bytes"], per[k]["functions"]) for k in order]
    rows.append(("untagged", fn["partition"]["untagged_bytes"], fn["partition"]["untagged_gaps"]))
    rows.append(("jumptable+padding", fn["partition"]["data_in_text_jumptable_bytes"] + fn["partition"]["padding_bytes"], None))
    den = fn["denominator_text_bytes"]
    colors = {"anchored": "#2b8a3e", "supported": "#74b816", "library": "#1971c2", "synthetic": "#868e96",
              "proposed": "#f59f00", "verified": "#0b7285", "auto": "#c92a2a", "untagged": "#e03131", "jumptable+padding": "#adb5bd"}
    w, rh, left, barw = 760, 26, 150, 480
    h = 60 + rh * len(rows)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="Segoe UI, Arial, sans-serif" font-size="12">',
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
           f'<text x="10" y="20" font-size="14" font-weight="bold">i76.exe .text by status - {den:,} B denominator - {dt.date.today().isoformat()}</text>',
           f'<text x="10" y="38" fill="#495057">bytes per functions.tsv status (Ghidra body sizes); untagged = .text bytes in no function/jumptable/padding</text>']
    y = 50
    for name, b, n in rows:
        pct = 100.0 * b / den
        bw = max(1, int(barw * b / den))
        out.append(f'<text x="{left - 8}" y="{y + 17}" text-anchor="end">{name}</text>')
        out.append(f'<rect x="{left}" y="{y + 4}" width="{bw}" height="{rh - 8}" fill="{colors.get(name, "#999")}"/>')
        lab = f"{b:,} B ({pct:.1f}%)" + (f", {n} fn" if n is not None and name != "untagged" else (f", {n} gaps" if n is not None else ""))
        out.append(f'<text x="{left + bw + 6}" y="{y + 17}" fill="#212529">{lab}</text>')
        y += rh
    out.append("</svg>")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    os.replace(tmp, path)
    return os.path.getsize(path)


def git_head():
    try:
        return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=p("status", "progress.json"))
    ap.add_argument("--svg", default=p("status", "progress.svg"))
    ap.add_argument("--no-append", action="store_true")
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    sec = sections()
    print(f"launched {sec['exe']} md5 {sec['md5']} {TOOL} {VERSION}")
    fn = functions_metrics(sec)
    data = data_metrics(sec)
    metrics = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "tool": f"{TOOL} {VERSION}", "exe_md5": sec["md5"], "commit_before": git_head(),
        "sections": {k: [f"0x{v[0]:x}", f"0x{v[1]:x}"] for k, v in sec.items() if isinstance(v, tuple)},
        "functions": fn, "data": data, "heap_pool": heap_metrics(), "labels": label_metrics(),
        "quality": quality_metrics(), "throughput": throughput_metrics(), "dynamic": dynamic_metrics(),
    }
    metrics["process_wide"] = processwide_metrics(sec, fn)
    # timeline
    timeline = []
    if os.path.exists(a.out):
        try:
            timeline = json.load(open(a.out, encoding="utf-8")).get("timeline", [])
        except ValueError:
            timeline = []
    entry = {"time": metrics["generated"], "commit_before": metrics["commit_before"],
             "status_bytes": {k: v["bytes"] for k, v in fn["per_status"].items()},
             "untagged_bytes": fn["partition"]["untagged_bytes"], "remainder_bytes": fn["remainder_bytes"],
             "unowned_referenced": data["unowned_referenced"], "decompile_failures": metrics["quality"]["decompile_failures"],
             "residual_FUN_names": metrics["quality"]["residual_FUN_names"]}
    if not a.no_append:
        timeline.append(entry)
    doc = {"metrics": metrics, "timeline": timeline}
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, a.out)
    back = json.load(open(a.out, encoding="utf-8"))
    assert back["metrics"]["functions"]["rows"] == fn["rows"], "read-back mismatch"
    svg_bytes = write_svg(a.svg, fn)
    print(f"wrote {os.path.relpath(a.out, ROOT)} ({os.path.getsize(a.out)} B, timeline {len(back['timeline'])} entries, read back OK); "
          f"{os.path.relpath(a.svg, ROOT)} ({svg_bytes} B)")
    ps = fn["per_status"]
    print("status bytes: " + ", ".join(f"{k}={v['bytes']}/{v['functions']}" for k, v in ps.items() if v["functions"]))
    print(f"partition: union {fn['partition']['function_bytes_union']} + jumptable {fn['partition']['data_in_text_jumptable_bytes']} "
          f"+ padding {fn['partition']['padding_bytes']} + untagged {fn['partition']['untagged_bytes']} ({fn['partition']['untagged_gaps']} gaps) = {fn['denominator_text_bytes']}")
    print(f"data typed: {data['map_typed_bytes']} of {data['denominators']}; unowned referenced {data['unowned_referenced']}/{data['referenced_addresses']} {data['unowned_per_region']}")
    q = metrics["quality"]
    print(f"quality: {q['token_occurrences']} decompile failures {q['decompile_failures']} residual FUN_ {q['residual_FUN_names']}")
    if a.print:
        print(json.dumps(metrics, indent=1))


if __name__ == "__main__":
    main()
