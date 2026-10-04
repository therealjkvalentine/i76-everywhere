#!/usr/bin/env python3
r"""ledger_types.py - allocation types from a ledger capture (runbook item 005; M07 input).

    python tools\ledger_types.py --capture 005-ledger [--markers captures\005-ledger\ledger\markers.json] [--window-s 5]
    python tools\ledger_types.py --dir <dir with ledger\>          (test runs outside captures\)
    -> <dir>\ledger\types.csv

Input (tools\frida_run.py --ledger): ledger\records.csv (seq,drain,src,src_name,kind,key,size,extra,result,ra,frame,tid),
ledger\drains.csv (drain,t_ms,frame,...), ledger\sources.csv. Optional markers.json written by the operator
(tools\ledger_mark.py, right after cheatlib Send-SelfDestruct): {"markers": [{"t_ms": <epoch ms>, "label": ...}]}.

Method (funnel printed: records -> after nested-pair collapse -> alloc-like -> types).
1. Nested pairs: two consecutive seq numbers on one thread that report the same result pointer (or, for
   frees, the same freed pointer) are one allocation seen at two hook levels (e.g. heap_5a7cc0_alloc 0x499ce0
   and the HeapAlloc it calls; msvcrt free and operator delete). The inner record (lower seq: its on_leave
   ran first) is dropped and counted as nested.
2. Type key = (source, key, size, retaddr): key = heap handle for HeapAlloc/HeapReAlloc/HeapFree/wrapper
   (the value of the wrapper's handle global at call time), 0 for msvcrt malloc/new and the pools; retaddr =
   the direct return address of the hooked call, class init when inside .text 0x401000-0x4bbe55 (H6: heap
   claims are (source, key, offset), never absolute addresses; the pointer values here are per-run and only
   used to match frees).
3. Lifetime: a free-like record (HeapFree, free, delete, realloc's old pointer, pool_Free) pops the live entry
   with the same (pointer space, pointer): space = ('heap', handle) for HeapAlloc/HeapFree/wrapper, ('crt', 0)
   for malloc/realloc/new/free/delete, ('pool', 0) for pool_Reserve/pool_Free. Lifetime in sim frames comes
   from the frame field (0x5a7e1c bss, read at on_leave); in ms from the delivering drain's host time
   (resolution = drain_ms, so a lifetime shorter than one drain reads 0 ms).
4. Respawn join: an allocation whose drain time lies in [marker, marker + window_s] counts as in-window;
   a type with n_markers > 0 and in-window share > 0.5 is flagged respawn-burst (the candidate vehicle /
   entity types for M07, to be confirmed by H6 across two markers).
"""
import argparse
import csv
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "0.1"
ALLOC_KINDS = {"heap-alloc", "heap-realloc", "malloc", "realloc", "new", "pool-reserve", "wrapper-alloc", "heap-create"}
FREE_KINDS = {"heap-free", "free", "delete", "pool-free", "heap-destroy"}


def space_of(kind, key):
    if kind in ("heap-alloc", "heap-realloc", "heap-free", "wrapper-alloc"):
        return ("heap", key)
    if kind in ("malloc", "realloc", "new", "free", "delete"):
        return ("crt", 0)
    if kind in ("pool-reserve", "pool-free"):
        return ("pool", 0)
    return ("other", 0)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--capture")
    g.add_argument("--dir")
    ap.add_argument("--markers", help="markers.json (default <dir>\\ledger\\markers.json if present)")
    ap.add_argument("--window-s", type=float, default=5.0)
    ap.add_argument("--out")
    a = ap.parse_args()
    base = a.dir or os.path.join(ROOT, "captures", a.capture)
    ldir = os.path.join(base, "ledger")
    recs = read_csv(os.path.join(ldir, "records.csv"))
    drains = {int(r["drain"]): r for r in read_csv(os.path.join(ldir, "drains.csv"))}
    for r in recs:
        r["seq"] = int(r["seq"]); r["tid"] = int(r["tid"]); r["frame"] = int(r["frame"]); r["size"] = int(r["size"])
        r["key_i"] = int(r["key"], 16); r["result_i"] = int(r["result"], 16); r["extra_i"] = int(r["extra"], 16)
        d = drains.get(int(r["drain"]))
        r["t_ms"] = int(d["t_ms"]) if d else None
    recs.sort(key=lambda r: r["seq"])
    funnel = {"records": len(recs)}
    # 1. nested-pair collapse
    nested = 0
    keep = []
    for i, r in enumerate(recs):
        nxt = recs[i + 1] if i + 1 < len(recs) else None
        if nxt and nxt["tid"] == r["tid"] and nxt["seq"] == r["seq"] + 1:
            same_alloc = r["kind"] in ALLOC_KINDS and nxt["kind"] in ALLOC_KINDS and r["result_i"] and r["result_i"] == nxt["result_i"]
            same_free = r["kind"] in FREE_KINDS and nxt["kind"] in FREE_KINDS and r["extra_i"] and r["extra_i"] == nxt["extra_i"]
            if same_alloc or same_free:
                nested += 1
                continue
        keep.append(r)
    funnel["after_nested_collapse"] = len(keep)
    funnel["nested_dropped"] = nested
    # markers
    mpath = a.markers or os.path.join(ldir, "markers.json")
    markers = []
    if os.path.exists(mpath):
        markers = [m["t_ms"] for m in json.load(open(mpath, encoding="utf-8")).get("markers", [])]
    win = int(a.window_s * 1000)

    def in_window(t):
        return t is not None and any(m <= t <= m + win for m in markers)

    # 2/3. types and lifetimes
    types = {}
    live = {}
    unmatched_free = 0
    alloc_like = 0

    def tkey(r):
        return (r["src_name"], r["key_i"], r["size"], r["ra"])

    def get_type(r):
        k = tkey(r)
        if k not in types:
            va = int(r["ra"], 16)
            types[k] = {"source": r["src_name"], "kind": r["kind"], "key": r["key"], "size": r["size"], "retaddr": r["ra"],
                        "retaddr_class": "init" if 0x401000 <= va < 0x4bbe56 else "other-module",
                        "n_alloc": 0, "n_freed": 0, "n_in_window": 0, "first_frame": r["frame"], "last_frame": r["frame"],
                        "frames": set(), "life_frames": [], "life_ms": [], "first_seq": r["seq"]}
        return types[k]

    for r in keep:
        if r["kind"] in ALLOC_KINDS:
            alloc_like += 1
            if r["kind"] == "realloc" or r["kind"] == "heap-realloc":
                old = live.pop((space_of(r["kind"], r["key_i"]), r["extra_i"]), None)
                if old is not None:
                    _close(old, r)
            ty = get_type(r)
            ty["n_alloc"] += 1
            ty["first_frame"] = min(ty["first_frame"], r["frame"]); ty["last_frame"] = max(ty["last_frame"], r["frame"])
            ty["frames"].add(r["frame"])
            if in_window(r["t_ms"]):
                ty["n_in_window"] += 1
            if r["result_i"]:
                live[(space_of(r["kind"], r["key_i"]), r["result_i"])] = (ty, r)
        elif r["kind"] in FREE_KINDS and r["kind"] != "heap-destroy":
            ent = live.pop((space_of(r["kind"], r["key_i"]), r["extra_i"]), None)
            if ent is None:
                unmatched_free += 1
            else:
                _close(ent, r)
    funnel["alloc_like"] = alloc_like
    funnel["unmatched_frees"] = unmatched_free
    funnel["alive_at_end"] = len(live)
    funnel["types"] = len(types)
    funnel["markers"] = len(markers)
    out = a.out or os.path.join(ldir, "types.csv")
    rows = sorted(types.values(), key=lambda t: (-t["n_alloc"], t["first_seq"]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["type_id", "source", "kind", "key", "size", "retaddr", "retaddr_class", "n_alloc", "n_freed", "n_alive_end",
                    "n_frames_seen", "first_frame", "last_frame", "allocs_per_frame_span", "life_frames_median", "life_frames_min",
                    "life_frames_max", "life_ms_median", "n_markers", "n_in_window", "in_window_share", "flag",
                    "method_key", "method_lifetime", "method_marker"])
        mk = "(source,key,size,retaddr); key = heap handle (HeapAlloc/HeapReAlloc/HeapFree/wrapper handle global), 0 for msvcrt and pools; retaddr = direct return address of the hooked call; nested pairs collapsed to the outer record"
        ml = "free matched by (pointer space, pointer): heap=(handle), crt, pool; frames from 0x5a7e1c (bss) at on_leave; ms from drain host time (resolution drain_ms)"
        mm = "markers.json t_ms (epoch ms) from ledger_mark.py after Send-SelfDestruct; in-window = alloc drain time within [marker, marker+%.1f s]; flag respawn-burst when share > 0.5" % a.window_s
        for i, t in enumerate(rows):
            span = t["last_frame"] - t["first_frame"] + 1
            share = (t["n_in_window"] / t["n_alloc"]) if t["n_alloc"] else 0.0
            flag = "respawn-burst" if (markers and share > 0.5) else ""
            lf, lm = t["life_frames"], t["life_ms"]
            w.writerow([i, t["source"], t["kind"], t["key"], t["size"], t["retaddr"], t["retaddr_class"], t["n_alloc"], t["n_freed"],
                        t["n_alloc"] - t["n_freed"], len(t["frames"]), t["first_frame"], t["last_frame"],
                        round(t["n_alloc"] / span, 4) if span > 0 else "",
                        statistics.median(lf) if lf else "", min(lf) if lf else "", max(lf) if lf else "",
                        statistics.median(lm) if lm else "", len(markers), t["n_in_window"], round(share, 3), flag, mk, ml, mm])
    back = read_csv(out)
    assert len(back) == len(rows), "read-back row count mismatch"
    summary = {"tool": "tools/ledger_types.py " + VERSION, "out": out, "funnel": funnel,
               "top_types": [{"source": t["source"], "size": t["size"], "retaddr": t["retaddr"], "n_alloc": t["n_alloc"]} for t in rows[:5]]}
    print(json.dumps(summary))
    mpath2 = os.path.join(base, "manifest.json")
    if os.path.exists(mpath2):
        man = json.load(open(mpath2, encoding="utf-8"))
        man.setdefault("derived", {})["ledger_types"] = summary
        tmp = mpath2 + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(man, f, indent=1, default=str)
        os.replace(tmp, mpath2)
    return 0


def _close(ent, free_rec):
    ty, alloc_rec = ent
    ty["n_freed"] += 1
    ty["life_frames"].append(free_rec["frame"] - alloc_rec["frame"])
    if free_rec["t_ms"] is not None and alloc_rec["t_ms"] is not None:
        ty["life_ms"].append(free_rec["t_ms"] - alloc_rec["t_ms"])


if __name__ == "__main__":
    sys.exit(main())
