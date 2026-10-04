#!/usr/bin/env python3
"""blind_eval.py - gate G6: render the truth set blind for a drafter, and score a proposal against the sealed set.

    python tools\\blind_eval.py render  [--export ghidra\\export-frozen] [--out status\\blind] [--context 5]
    python tools\\blind_eval.py score   proposal.json [--out result.json] [--second proposal2.json]
    python tools\\blind_eval.py reveal  0xADDR --reviewer          (prints the sealed row; reviewers only)

render: for every truth-set function (status\\truthset-blind.json: addresses only) writes
  <out>\\<addr>\\self.c              the function's .c with every truth-set name and every direct caller's name
                                    restored to FUN_<addr> (and the ApplyMap plate comment removed)
  <out>\\<addr>\\callers\\<a>.c      up to --context direct callers, same restoration
  <out>\\<addr>\\callees\\<a>.c      up to --context direct callees, same restoration
  <out>\\<addr>\\BRIEF.md            what to produce (a name for the anchored half, facts for the string-less half)
  <out>\\INDEX.json                 the list; no names, no tuples
The hidden-name map is built from symbols\\functions.tsv for the truth-set rows and their direct callers, so the
view is blind whichever export it is rendered from (export-frozen already carries FUN_ names; the live export
carries applied names, which is why the restoration exists). Callees keep their map names: a drafter in the loop
sees callee names too, and the truth set measures naming, not the callee context.

score: proposal JSON
  {"drafter": "...", "view": "...", "proposals": {"0x40a270": {"name": "...", "subsystem": "...",
     "callees": ["0x..."], "globals_written": ["0x..."], "leaf": true, "pure": true, "io_expr": "lambda a: ..."}}}
Anchored half (per function, all three reported; the G6 floor is on `semantic`):
  exact     normalised proposal name == normalised truth name (lowercase, non-alphanumerics dropped)
  semantic  exact, or a shared scoring token of length >= 4 that is not a stopword (tokens: split on _ and camelCase;
            hex/decimal tokens dropped) - the same tokenizer sealed the truth tokens
  subsystem proposal `subsystem` == truth subsystem (only rows with a subsystem count in the denominator)
String-less half: contradictions against the sealed tuple - claimed callee not in the callee set; claimed written
global not among globals written (init/bss/iat disp32 targets); `leaf: true` with callees present; `pure: true`
with globals or callees present or the emulator saw a data-section touch; `io_expr` disagreeing with any ok row of
the emulated proto-mode table by > 4 ulp (st0) or any bits (eax). Reported as contradictions per 4 tuples
against the halt threshold (> 1 per 4). Unproposed functions count as unscored (n reports both).
--second: a second proposal (the other G4 view) gives agreement and agreement-when-both-wrong on the anchored half.
"""
import os, sys, re, json, argparse, hashlib, math, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from truthset_select import name_tokens, read_tsv, FUNC_COLS

STOP = {"fun", "func", "function", "sub", "proc", "handler", "callback", "routine", "helper", "impl", "internal",
        "init", "load", "read", "write", "update", "process", "handle", "main", "data", "table", "entry"}
PLATE = re.compile(r"^\s*/\*\s*i76-map .*?\*/\s*$", re.M)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def hx(a):
    return "0x%x" % a


def load_truth(M):
    p = os.path.join(M, "status", "truthset.json")
    t = json.load(open(p, encoding="utf-8"))
    t["_file_sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return t


# ---------------------------------------------------------------------------------------------------------------
def render(M, export, out, context):
    blind = json.load(open(os.path.join(M, "status", "truthset-blind.json"), encoding="utf-8"))
    cg = json.load(open(os.path.join(M, "ghidra", export, "callgraph.json"), encoding="utf-8"))
    ft = {int(r["addr"], 16): r for r in read_tsv(os.path.join(M, "symbols", "functions.tsv"), FUNC_COLS)}
    truth_addrs = [int(f["addr"], 16) for f in blind["functions"]]
    hidden = set(truth_addrs)
    for a in truth_addrs:
        e = cg.get("%08x" % a)
        if e:
            hidden.update(int(c, 16) for c in e["callers"])
    # name -> FUN_ map for every hidden address whose map row carries a non-default name
    restore = {}
    for a in hidden:
        r = ft.get(a)
        if r and not r["name"].startswith("FUN_"):
            restore[r["name"]] = "FUN_%08x" % a
    pat = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(restore, key=len, reverse=True)) + r")\b") if restore else None

    def sanitize(text):
        text = PLATE.sub("", text)
        if pat:
            text = pat.sub(lambda m: restore[m.group(1)], text)
        # header line "// 004aeb60 bwd2_h_... size=" -> default
        text = re.sub(r"^// ([0-9a-f]{8}) (\S+) size=", lambda m: "// %s FUN_%s size=" % (m.group(1), m.group(1)), text, count=1, flags=re.M)
        return text

    def cfile(a):
        p = os.path.join(M, "ghidra", export, "functions", "%08x.c" % a)
        if not os.path.exists(p):
            return None
        return sanitize(open(p, encoding="utf-8", errors="replace", newline="").read().replace("\r", ""))

    os.makedirs(out, exist_ok=True)
    index = []
    n_files = 0
    for f in blind["functions"]:
        a = int(f["addr"], 16)
        d = os.path.join(out, "%08x" % a)
        os.makedirs(os.path.join(d, "callers"), exist_ok=True)
        os.makedirs(os.path.join(d, "callees"), exist_ok=True)
        c = cfile(a)
        if c is None:
            print("no .c for %s in %s" % (f["addr"], export)); continue
        open(os.path.join(d, "self.c"), "w", encoding="utf-8", newline="\n").write(c); n_files += 1
        e = cg.get("%08x" % a, {"callers": [], "callees": []})
        callers = sorted(int(x, 16) for x in e["callers"])[:context]
        callees = sorted(int(x, 16) for x in e["callees"] if not x.startswith("EXTERNAL"))[:context]
        for lst, sub in ((callers, "callers"), (callees, "callees")):
            for b in lst:
                cb = cfile(b)
                if cb is not None:
                    open(os.path.join(d, sub, "%08x.c" % b), "w", encoding="utf-8", newline="\n").write(cb); n_files += 1
        task = ("Propose ONE name for FUN_%08x and a subsystem, from the C below and its callers/callees only. "
                "Do not open symbols\\, status\\truthset.json, evidence\\ or ghidra\\export for this address." % a
                if f["half"] == "anchored" else
                "Propose facts for FUN_%08x: callee set (addresses), globals written (addresses), leaf?, pure? and, "
                "for a pure leaf, an io_expr (python lambda over the typed args) predicting eax or st0. Same reading rule." % a)
        open(os.path.join(d, "BRIEF.md"), "w", encoding="utf-8").write(
            "# FUN_%08x (blind view, %s half, size %d)\n\n%s\n\nFiles: self.c, callers\\*.c (%d), callees\\*.c (%d).\n"
            % (a, f["half"], f["size"], task, len(callers), len(callees)))
        index.append({"addr": f["addr"], "half": f["half"], "size": f["size"], "dir": "%08x" % a,
                      "n_callers": len(e["callers"]), "n_callees": len(callees)})
    json.dump({"export": export, "hidden_names": len(restore), "hidden_addresses": len(hidden), "functions": index},
              open(os.path.join(out, "INDEX.json"), "w", encoding="utf-8"), indent=1)
    print("rendered %d functions, %d files, %d names restored to FUN_ over %d hidden addresses -> %s"
          % (len(index), n_files, len(restore), len(hidden), out))
    return 0


# ---------------------------------------------------------------------------------------------------------------
def score_anchored(truth_rows, props):
    rows = []
    for t in truth_rows:
        p = props.get(t["addr"]) or props.get(t["addr"].lower()) or props.get(t["addr"].upper())
        if not p:
            rows.append({"addr": t["addr"], "scored": False}); continue
        pname = p.get("name", "") or ""
        exact = norm(pname) == norm(t["name"])
        ptoks = {x for x in name_tokens(pname) if len(x) >= 4 and x not in STOP}
        ttoks = {x for x in t["tokens"] if len(x) >= 4 and x not in STOP}
        shared = sorted(ptoks & ttoks)
        semantic = exact or bool(shared)
        subs = None
        if t.get("subsystem"):
            subs = norm(p.get("subsystem", "")) == norm(t["subsystem"])
        rows.append({"addr": t["addr"], "scored": True, "stratum": t.get("stratum"), "proposed": pname, "truth": t["name"], "exact": exact,
                     "semantic": semantic, "shared_tokens": shared, "subsystem": subs,
                     "truth_subsystem": t.get("subsystem", ""), "proposed_subsystem": p.get("subsystem", "")})
    sc = [r for r in rows if r["scored"]]
    n = len(sc)
    ex = sum(1 for r in sc if r["exact"]); se = sum(1 for r in sc if r["semantic"])
    by_stratum = {}
    for r in sc:
        st = r["stratum"]; b = by_stratum.setdefault(st, {"n": 0, "exact": 0, "semantic": 0, "subsystem": 0, "subsystem_n": 0})
        b["n"] += 1; b["exact"] += r["exact"]; b["semantic"] += r["semantic"]
        if r["subsystem"] is not None:
            b["subsystem_n"] += 1; b["subsystem"] += r["subsystem"]
    sub_rows = [r for r in sc if r["subsystem"] is not None]
    su = sum(1 for r in sub_rows if r["subsystem"])
    return {"n_truth": len(truth_rows), "n_scored": n, "exact": ex, "semantic": se, "subsystem": su,
            "subsystem_n": len(sub_rows), "by_stratum": by_stratum,
            "exact_rate": ex / n if n else None, "semantic_rate": se / n if n else None,
            "subsystem_rate": su / len(sub_rows) if sub_rows else None,
            "floor_phase1_semantic": 0.8, "below_floor": (se / n < 0.8) if n else None,
            "method": "blind_eval.py score_anchored: exact=normalised equality; semantic=exact or shared token len>=4 not in STOP; "
                      "subsystem=normalised equality over rows with a truth subsystem", "rows": rows}


def eval_io(expr, emu):
    """Run a proposal's io_expr against the proto-mode ok rows. Returns (n_checked, n_mismatch, note)."""
    try:
        fn = eval(expr, {"__builtins__": {}, "math": math, "abs": abs, "min": min, "max": max, "int": int, "float": float})
    except Exception as e:
        return 0, 0, "io_expr does not evaluate: %s" % e
    rows = [r for r in emu["modes"].get("proto", {}).get("rows", []) if r["status"] == "ok" and r.get("args_typed")]
    if not rows:
        rows = [r for r in emu["modes"].get("int", {}).get("rows", []) if r["status"] == "ok"]
        typed = lambda r: [int(a, 16) for a in r["args"]]
    else:
        typed = lambda r: r["args_typed"]
    n = mism = 0
    for r in rows:
        try:
            pred = fn(*typed(r))
        except Exception:
            continue
        n += 1
        if isinstance(pred, float) and r.get("st0") is not None:
            a, b = pred, r["st0"]
            if a != b:
                fa = struct.unpack("<i", struct.pack("<f", a))[0] if abs(a) < 3e38 else None
                fb = struct.unpack("<i", struct.pack("<f", b))[0] if abs(b) < 3e38 else None
                if fa is None or fb is None or abs(fa - fb) > 4:
                    mism += 1
        else:
            try:
                if (int(pred) & 0xffffffff) != r["eax"]:
                    mism += 1
            except Exception:
                mism += 1
    return n, mism, "checked against %d emulated rows" % n


def score_stringless(truth_rows, props):
    rows = []
    for t in truth_rows:
        p = props.get(t["addr"])
        if not p:
            rows.append({"addr": t["addr"], "scored": False}); continue
        contra = []
        cal = set(t["callees"]["internal"])
        for c in p.get("callees", []) or []:
            if isinstance(c, str) and c.lower() not in cal and c not in t["callees"]["imports"]:
                contra.append("callee %s not in sealed set" % c)
        gw = {g["addr"] for g in t["globals"]["written"]}
        for g in p.get("globals_written", []) or []:
            if isinstance(g, str) and g.lower() not in gw:
                contra.append("global %s not written by this function (sealed disp32 set)" % g)
        has_callees = bool(t["callees"]["internal"] or t["callees"]["imports"])
        if p.get("leaf") is True and has_callees:
            contra.append("claimed leaf; sealed callees %d" % (len(t["callees"]["internal"]) + len(t["callees"]["imports"])))
        if p.get("leaf") is False and not has_callees:
            contra.append("claimed non-leaf; sealed callee set empty")
        sealed_pure = (t["emulated_io"] or {}).get("pure") if t.get("emulated_io") else False
        impure_static = bool(t["globals"]["written"] or t["globals"]["read"] or has_callees)
        if p.get("pure") is True and (impure_static or not sealed_pure):
            contra.append("claimed pure; sealed: globals r/w=%d/%d, callees=%s, emulator pure=%s"
                          % (len(t["globals"]["read"]), len(t["globals"]["written"]), has_callees, sealed_pure))
        io_note = None
        if p.get("io_expr") and t.get("emulated_io"):
            n, m, io_note = eval_io(p["io_expr"], t["emulated_io"])
            if m:
                contra.append("io_expr mismatches %d of %d emulated rows" % (m, n))
        rows.append({"addr": t["addr"], "scored": True, "contradictions": contra, "n_contradictions": len(contra),
                     "io_note": io_note, "stratum": t["stratum"]})
    sc = [r for r in rows if r["scored"]]
    n = len(sc); c = sum(r["n_contradictions"] for r in sc)
    return {"n_truth": len(truth_rows), "n_scored": n, "contradictions": c,
            "per_4_tuples": (4.0 * c / n) if n else None, "halt_threshold_per_4": 1.0,
            "halt": ((4.0 * c / n) > 1.0) if n else None,
            "method": "blind_eval.py score_stringless: contradiction count against the sealed tuple (see module doc)",
            "rows": rows}


def agreement(truth_rows, p1, p2):
    both = n = agree = both_wrong = agree_both_wrong = 0
    for t in truth_rows:
        a = (p1.get(t["addr"]) or {}).get("name"); b = (p2.get(t["addr"]) or {}).get("name")
        if not a or not b:
            continue
        n += 1
        ag = norm(a) == norm(b)
        wa = norm(a) != norm(t["name"]); wb = norm(b) != norm(t["name"])
        agree += ag
        if wa and wb:
            both_wrong += 1
            agree_both_wrong += ag
    return {"n_both_proposed": n, "agree": agree, "both_wrong": both_wrong, "agree_when_both_wrong": agree_both_wrong,
            "method": "normalised name equality between the two G4 views (exact level)"}


def score(M, proposal_path, out, second):
    t = load_truth(M)
    prop = json.load(open(proposal_path, encoding="utf-8"))
    props = {k.lower(): v for k, v in prop.get("proposals", {}).items()}
    res = {"proposal": proposal_path, "drafter": prop.get("drafter"), "view": prop.get("view"),
           "truthset_sha256": t["_file_sha256"], "truthset_sealed": t["sealed"],
           "anchored": score_anchored(t["anchored"], props), "stringless": score_stringless(t["stringless"], props)}
    if second:
        p2 = {k.lower(): v for k, v in json.load(open(second, encoding="utf-8")).get("proposals", {}).items()}
        res["g4_agreement"] = agreement(t["anchored"], props, p2)
    A, S = res["anchored"], res["stringless"]
    print("anchored: scored %d/%d  exact %d (%s)  semantic %d (%s)  subsystem %d/%d  below Phase-1 floor: %s"
          % (A["n_scored"], A["n_truth"], A["exact"], fmt(A["exact_rate"]), A["semantic"], fmt(A["semantic_rate"]),
             A["subsystem"], A["subsystem_n"], A["below_floor"]))
    for st, b in A["by_stratum"].items():
        print("  stratum %-20s n=%d exact=%d semantic=%d subsystem=%d/%d" % (st, b["n"], b["exact"], b["semantic"], b["subsystem"], b["subsystem_n"]))
    for r in A["rows"]:
        if r["scored"]:
            print("  %s %-34s truth %-40s exact=%s semantic=%s shared=%s subsystem=%s"
                  % (r["addr"], r["proposed"], r["truth"], int(r["exact"]), int(r["semantic"]), r["shared_tokens"], r["subsystem"]))
    print("stringless: scored %d/%d  contradictions %d  per-4-tuples %s  halt: %s"
          % (S["n_scored"], S["n_truth"], S["contradictions"], fmt(S["per_4_tuples"], 2), S["halt"]))
    for r in S["rows"]:
        if r["scored"] and r["n_contradictions"]:
            print("  %s: %s" % (r["addr"], "; ".join(r["contradictions"])))
    if "g4_agreement" in res:
        print("G4 agreement:", res["g4_agreement"])
    if out:
        with open(out + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, sort_keys=True)
        os.replace(out + ".tmp", out)
        json.load(open(out, encoding="utf-8"))
        print("wrote", out)
    return 0


def fmt(x, d=3):
    return "n/a" if x is None else ("%%.%df" % d) % x


def reveal(M, addr, reviewer):
    if not reviewer:
        print("reveal prints sealed truth; pass --reviewer (drafters must never run this)"); return 2
    t = load_truth(M)
    a = addr.lower()
    for half in ("anchored", "stringless"):
        for r in t[half]:
            if r["addr"] == a:
                print(json.dumps({k: v for k, v in r.items() if k != "emulated_io"}, indent=1, sort_keys=True))
                if r.get("emulated_io"):
                    e = r["emulated_io"]
                    print("emulated_io: pure=%s oracles=%s ok=%s" % (e["pure"], [o["oracle"] for o in e["oracle_matches"]],
                                                                    {m: v["ok"] for m, v in e["modes"].items()}))
                return 0
    print("not in the truth set"); return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["render", "score", "reveal"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--map", default=r"C:\Users\james\i76-map")
    ap.add_argument("--export", default="export-frozen")
    ap.add_argument("--out", default=None)
    ap.add_argument("--context", type=int, default=5)
    ap.add_argument("--second", default=None)
    ap.add_argument("--reviewer", action="store_true")
    a = ap.parse_args()
    if a.cmd == "render":
        return render(a.map, a.export, a.out or os.path.join(a.map, "status", "blind"), a.context)
    if a.cmd == "score":
        if not a.arg:
            print("score needs a proposal file"); return 2
        return score(a.map, a.arg, a.out, a.second)
    if a.cmd == "reveal":
        return reveal(a.map, a.arg or "", a.reviewer)


if __name__ == "__main__":
    sys.exit(main())
