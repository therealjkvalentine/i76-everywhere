r"""callgraph_report.py - the numbers behind ARCHITECTURE.md (module map, fan-in/fan-out, frame-loop reach).

    python tools\callgraph_report.py [--top 25] [--mermaid-edges 18] [--out ARCHITECTURE-callgraph.md]

Inputs (read-only):
  ghidra\export\callgraph.json   {caller_addr: {call_sites: [[site, callee, name], ...], callees, callers, name}}
  symbols\functions.tsv          addr size name ... subsystem (column 10 = the prefix that owns the function)

What it computes:
  1. prefix x prefix call matrix. One unit = one call site (a `call` instruction) whose caller and callee are both
     named functions. Self-edges (same prefix) are counted but reported separately from cross-prefix edges.
  2. top fan-in (distinct callers) and fan-out (distinct callees) functions.
  3. the set of functions reachable from WinMain's gameplay loop body (0x4039a0..0x403f20, one iteration = one
     rendered frame), through direct calls only, plus the indirect roots the specs name (class-table tick/post-tick
     slots and the default camera callback), grouped by prefix. Indirect calls (class table 0x4f76e0, FSM action
     table, camera controller [0x4c2720], BWD2 chunk tables) are not in callgraph.json, so this is a lower bound.

Prefix: the functions.tsv `subsystem` column; when it is empty the name's prefix (text before the first '_') is
used. Thunks, EH funclets and synthetic rows are dropped from the matrix (they have no behaviour of their own).
"""
import argparse
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CALLGRAPH = os.path.join(ROOT, "ghidra", "export", "callgraph.json")
FUNCTIONS = os.path.join(ROOT, "symbols", "functions.tsv")

WINMAIN = 0x402B30
LOOP_LO, LOOP_HI = 0x4039A0, 0x403F20
# Functions the frame loop reaches only through pointer tables (not visible to the static callgraph).
# Each group names the table; the addresses come from the subsystem specs (physics.md, ai.md, renderer.md, camera.md).
INDIRECT_ROOT_GROUPS = {
    "class table 0x4f76e0 (+0xc tick, +0x10 post-tick)": [
        0x463800,  # entity_TickVehicle, type 1
        0x463950,  # entity_VehiclePostTick, player
        0x45FAF0,  # entity_UpdateRadarContacts, type 34 post-tick
        0x46BD10,  # physics_StepAircraft, type 9
    ],
    "camera controller [0x4c2720] (per-mode callbacks)": [
        0x406AB0, 0x4071A0, 0x4061B0, 0x407AD0, 0x407680, 0x409540, 0x408240, 0x408A10, 0x408C60, 0x409140, 0x405B90,
    ],
    "AI behaviour table 0x4c3e00 (34 records x 0x1354; enter / update / exit / interrupt / leave)": [
        # enter
        0x416B80, 0x416BE0, 0x416E50, 0x41C210, 0x41C830, 0x41C300, 0x41F750, 0x41C900, 0x41C5C0, 0x416F20, 0x41E740,
        0x41E8B0, 0x41ED00, 0x41C9D0, 0x41CB00, 0x41CE50, 0x41DB10, 0x41CF30, 0x41D620, 0x41E160, 0x420A20, 0x420AA0,
        0x41E2B0, 0x41EEF0, 0x40AF80,
        # update
        0x416BC0, 0x416CB0, 0x416EB0, 0x41C2A0, 0x41C8E0, 0x41C430, 0x41F7F0, 0x41C9B0, 0x41C680, 0x4171A0, 0x41E890,
        0x41E970, 0x41CAE0, 0x41CBB0, 0x41CEC0, 0x41DD80, 0x41CFF0, 0x41D6D0, 0x420D30, 0x420ED0, 0x420FC0, 0x420B30,
        0x41E450, 0x41EF40, 0x40AF00,
        # exits / terminators
        0x41C2C0, 0x41CC00, 0x416CD0, 0x416ED0, 0x41F860, 0x41CC40, 0x417490, 0x41EC20, 0x41CE30, 0x41D170, 0x41E230,
        0x420E70, 0x420E50, 0x420F80, 0x41E640, 0x41E720,
        # interrupts, transitions, leaves, selector
        0x41CD90, 0x41D770, 0x41D820, 0x41D8B0, 0x41D240, 0x41E080, 0x41E600, 0x41E680, 0x41D330, 0x41D450, 0x41F590,
        0x41EE10, 0x41ECC0, 0x41E030, 0x41D390, 0x41D6F0, 0x41E660, 0x40AFA0, 0x420520, 0x412680,
    ],
    "renderer draw-record dispatch 0x4faca8 and polygon drawers": [
        0x48F550, 0x48F500, 0x48F4C0, 0x48F570, 0x490640, 0x4260D0, 0x471FD0,
    ],
    "FSM action table (fsm_ActionDispatch 0x412ce0 is direct; its 96 actions are reached through it)": [
        0x4149F0,
    ],
}
INDIRECT_ROOTS = {a: g for g, lst in INDIRECT_ROOT_GROUPS.items() for a in lst}
DROP_PREFIXES = {"import-thunk", "synthetic", "thunk", "eh", "Unwind@004bbe40", "crt"}


def load_functions():
    rows = {}
    with open(FUNCTIONS, encoding="utf-8") as f:
        reader = csv.reader((l for l in f if not l.startswith("#")), delimiter="\t")
        header = next(reader)
        idx = {h: i for i, h in enumerate(header)}
        for p in reader:
            if len(p) < len(header):
                continue
            addr = int(p[idx["addr"]], 16)
            name = p[idx["name"]]
            sub = p[idx["subsystem"]].strip()
            if not sub:
                sub = name.split("_", 1)[0] if "_" in name else name
            rows[addr] = {"name": name, "prefix": sub, "size": int(p[idx["size"]] or 0)}
    return rows


def load_callgraph():
    with open(CALLGRAPH, encoding="utf-8") as f:
        return json.load(f)


def parse_addr(s):
    try:
        return int(s, 16)
    except ValueError:
        return None


def build_edges(cg, fn):
    """Return (site_edges Counter[(caller, callee)], callers_of dict, callees_of dict)."""
    site_edges = collections.Counter()
    callees_of = collections.defaultdict(set)
    callers_of = collections.defaultdict(set)
    for caller_s, rec in cg.items():
        caller = parse_addr(caller_s)
        if caller is None or caller not in fn:
            continue
        for site, callee_s, _nm in rec.get("call_sites", []):
            if callee_s.startswith("EXTERNAL"):
                continue
            callee = parse_addr(callee_s)
            if callee is None or callee not in fn:
                continue
            site_edges[(caller, callee)] += 1
            callees_of[caller].add(callee)
            callers_of[callee].add(caller)
    return site_edges, callers_of, callees_of


def prefix_matrix(site_edges, fn):
    matrix = collections.Counter()
    for (a, b), n in site_edges.items():
        pa, pb = fn[a]["prefix"], fn[b]["prefix"]
        if pa in DROP_PREFIXES or pb in DROP_PREFIXES:
            continue
        matrix[(pa, pb)] += n
    return matrix


def reach(roots, callees_of):
    seen = set()
    stack = list(roots)
    while stack:
        a = stack.pop()
        if a in seen:
            continue
        seen.add(a)
        stack.extend(callees_of.get(a, ()))
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25, help="rows in the top-edge and fan tables")
    ap.add_argument("--mermaid-edges", type=int, default=18, help="cross-prefix edges drawn in the Mermaid module map")
    ap.add_argument("--out", help="write the report here instead of stdout")
    args = ap.parse_args()

    fn = load_functions()
    cg = load_callgraph()
    site_edges, callers_of, callees_of = build_edges(cg, fn)
    matrix = prefix_matrix(site_edges, fn)

    out = []
    w = out.append
    n_funcs = sum(1 for a in fn if fn[a]["prefix"] not in DROP_PREFIXES)
    w(f"<!-- generated by tools/callgraph_report.py from ghidra/export/callgraph.json + symbols/functions.tsv -->")
    w(f"Functions in the matrix: {n_funcs}; call sites between named functions: {sum(site_edges.values())}; "
      f"distinct caller->callee pairs: {len(site_edges)}.")
    w("")

    # --- per-prefix totals
    per_prefix = collections.defaultdict(lambda: {"funcs": 0, "bytes": 0, "out": 0, "in": 0, "self": 0})
    for a, r in fn.items():
        if r["prefix"] in DROP_PREFIXES:
            continue
        per_prefix[r["prefix"]]["funcs"] += 1
        per_prefix[r["prefix"]]["bytes"] += r["size"]
    for (pa, pb), n in matrix.items():
        if pa == pb:
            per_prefix[pa]["self"] += n
        else:
            per_prefix[pa]["out"] += n
            per_prefix[pb]["in"] += n
    w("## Subsystems (prefix column of functions.tsv)")
    w("")
    w("| prefix | functions | bytes | calls out (cross) | calls in (cross) | internal calls |")
    w("|---|---:|---:|---:|---:|---:|")
    for p, d in sorted(per_prefix.items(), key=lambda kv: -kv[1]["funcs"]):
        if d["funcs"] < 3:
            continue
        w(f"| {p} | {d['funcs']} | {d['bytes']} | {d['out']} | {d['in']} | {d['self']} |")
    w("")

    # --- top cross-prefix edges
    cross = [((pa, pb), n) for (pa, pb), n in matrix.items() if pa != pb]
    cross.sort(key=lambda kv: -kv[1])
    w(f"## Top {args.top} cross-prefix edges (call sites)")
    w("")
    w("| caller prefix | callee prefix | call sites |")
    w("|---|---|---:|")
    for (pa, pb), n in cross[: args.top]:
        w(f"| {pa} | {pb} | {n} |")
    w("")

    # --- mermaid module map
    w("## Mermaid module map")
    w("")
    w("```mermaid")
    w("flowchart LR")
    nodes = set()
    for (pa, pb), n in cross[: args.mermaid_edges]:
        nodes.add(pa)
        nodes.add(pb)
    for p in sorted(nodes):
        d = per_prefix[p]
        w(f'  {p}["{p}<br/>{d["funcs"]} fn"]')
    for (pa, pb), n in cross[: args.mermaid_edges]:
        w(f"  {pa} -- {n} --> {pb}")
    w("```")
    w("")

    # --- fan-in / fan-out
    def fan_table(title, mapping, key):
        w(f"## Top {args.top} {title}")
        w("")
        w(f"| addr | name | prefix | {key} |")
        w("|---|---|---|---:|")
        items = sorted(((len(v), a) for a, v in mapping.items() if fn[a]["prefix"] not in DROP_PREFIXES), reverse=True)
        for n, a in items[: args.top]:
            w(f"| 0x{a:06x} | {fn[a]['name']} | {fn[a]['prefix']} | {n} |")
        w("")

    fan_table("fan-in (distinct callers)", callers_of, "callers")
    fan_table("fan-out (distinct callees)", callees_of, "callees")

    # --- frame loop reach
    wm = cg.get(f"{WINMAIN:08x}", {})
    loop_roots = []
    for site, callee_s, _nm in wm.get("call_sites", []):
        s = parse_addr(site)
        c = parse_addr(callee_s)
        if s is None or c is None or not (LOOP_LO <= s <= LOOP_HI) or c not in fn:
            continue
        if c not in loop_roots:
            loop_roots.append(c)
    direct = reach(loop_roots, callees_of)
    unknown_roots = [a for a in INDIRECT_ROOTS if a not in fn]
    indirect = [a for a in INDIRECT_ROOTS if a in fn]
    full = reach(loop_roots + indirect, callees_of)
    w("## Frame-loop reach")
    w("")
    w(f"WinMain 0x{WINMAIN:06x} loop body 0x{LOOP_LO:06x}..0x{LOOP_HI:06x}: {len(loop_roots)} distinct direct callees "
      f"(in call order below). Reachable through direct calls: {len(direct)} functions; with the "
      f"{len(indirect)} pointer-table roots added: {len(full)} of {n_funcs}.")
    w("")
    w("Direct callees in loop order: " + ", ".join(f"{fn[c]['name']} 0x{c:06x}" for c in loop_roots))
    w("")
    w("Pointer-table roots added (from the subsystem specs):")
    w("")
    for g, lst in INDIRECT_ROOT_GROUPS.items():
        w(f"- {g}: " + ", ".join(f"{fn[a]['name']} 0x{a:06x}" for a in lst if a in fn))
    if unknown_roots:
        w("")
        w("WARNING: not in functions.tsv: " + ", ".join(f"0x{a:06x}" for a in unknown_roots))
    w("")
    by_prefix = collections.Counter(fn[a]["prefix"] for a in full if fn[a]["prefix"] not in DROP_PREFIXES)
    w("| prefix | reachable from the frame loop | of |")
    w("|---|---:|---:|")
    for p, n in by_prefix.most_common():
        w(f"| {p} | {n} | {per_prefix[p]['funcs']} |")
    w("")
    not_reached = sorted(p for p in per_prefix if p not in by_prefix and per_prefix[p]["funcs"] >= 3)
    w("Prefixes with nothing reachable from the loop (load-time, shell, or pointer-table only): " + ", ".join(not_reached))
    w("")

    text = "\n".join(out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()
