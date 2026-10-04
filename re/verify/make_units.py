#!/usr/bin/env python3
"""Build work units for the model-facing half of the verification program (VERIFICATION-PROGRAM.md section 4).

    python verify/make_units.py cadence-claim [--prefix physics,entity] [--limit N] [--force]
                                              [--only-with-cadence-text | --no-only-with-cadence-text] [--dry-run]
    python verify/make_units.py blind-name    [--sample N --seed S] [--prefix ...] [--limit N] [--force]
    python verify/make_units.py blind-judge   [--seed S] [--force]
    python verify/make_units.py census-grade  <run> [<run> ...] [--force]

Units land in verify/queue/<kind>/<addr>.json as {"unit_id", "kind", "addr", "name", "inputs": {...}}
(plus a "hidden" object for blind-judge: the A/B mapping, never rendered into a prompt). A unit whose
.result.json or .escalate.json already exists is left alone; an existing unit file is only rewritten with --force.

<run> for census-grade is a run directory (verify/runs/<scenario>/<timestamp>), a census.classified.json file,
or a scenario id (latest timestamp wins). Format: see fixtures/census.classified.sample.json and section 2.2.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blind  # noqa: E402  (shared loaders live there)

VERIFY = blind.VERIFY
ROOT = blind.ROOT
QUEUE = VERIFY / "queue"
RUNS = VERIFY / "runs"
EVIDENCE = ROOT / "evidence"
SUBSYSTEMS = ROOT / "subsystems"

SPEC_MAX_CHARS = 1500
SPEC_SKIP = {"VOCABULARY.md", "README.md"}
CENSUS_ENUM = {"per_frame", "per_substep", "per_event", "init_only", "never", "menu_only", "irregular"}


# ----------------------------------------------------------------------------- helpers

def unit_id(kind: str, addr: str) -> str:
    return f"{kind}-{blind.addr0x(addr)}"


def unit_paths(kind: str, addr: str, reader: str = "") -> tuple[Path, Path, Path]:
    """<addr>.json / .result.json / .escalate.json; with `reader` = S the second-reader set <addr>.S.json /
    <addr>.S.result.json (the worker keys pending on the unit stem, so the two never collide; gate.py reads
    them as the second reader for the section 6 utility rule)."""
    d = QUEUE / kind
    base = d / (blind.addr0x(addr) + (f".{reader}" if reader else ""))
    return Path(str(base) + ".json"), Path(str(base) + ".result.json"), Path(str(base) + ".escalate.json")


def write_unit(kind: str, addr: str, name, inputs: dict, force: bool, hidden: dict | None = None,
               reader: str = "") -> str:
    """Returns 'written' | 'exists' | 'done'."""
    unit, result, escalate = unit_paths(kind, addr, reader)
    if result.exists() or escalate.exists():
        return "done"
    if unit.exists() and not force:
        return "exists"
    unit.parent.mkdir(parents=True, exist_ok=True)
    doc = {"unit_id": unit_id(kind, addr), "kind": kind, "addr": blind.addr0x(addr), "name": name, "inputs": inputs}
    if reader:
        doc["reader"] = reader
    if hidden is not None:
        doc["hidden"] = hidden
    unit.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return "written"


def load_result(kind: str, addr: str) -> dict | None:
    _, result, _ = unit_paths(kind, addr)
    if not result.exists():
        return None
    try:
        return json.loads(result.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def select_rows(status: str | None, prefixes: list[str] | None, limit: int | None) -> list[dict]:
    rows = blind.load_functions()
    if status:
        rows = [r for r in rows if r["status"] == status]
    if prefixes:
        pset = set(prefixes)
        rows = [r for r in rows if r["subsystem"] in pset or r["name"].split("_", 1)[0] in pset]
    rows.sort(key=lambda r: int(r["addr"], 16))
    if limit:
        rows = rows[:limit]
    return rows


def evidence_claims(row: dict) -> list[str]:
    claims = []
    for eid in filter(None, row.get("evidence_ids", "").split(";")):
        p = EVIDENCE / f"{eid}.json"
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        c = str(d.get("claim", "")).strip()
        if c:
            claims.append(c)
    return claims


_CONTRACT_PREFIX = re.compile(r"^contract\s*(\([^)]*\))?\s*:\s*", re.I)
# Claims that are metadata, not a reading of what the function does. 70 of 1,882 `proposed` rows have only
# these (2026-10-02); "conv __cdecl" reached a blind-judge unit as the map's "contract" before this filter.
_META_CLAIM = re.compile(r"^(conv|param|field|subsystem|name|ret|strings?|duplicate_of|size|status|hookable)\b", re.I)


def param_claims(row: dict) -> list[str]:
    """'param {"claim": "param", "index": 1, "value": "float time_offset"}' claims -> ['float time_offset', ...]."""
    out = []
    for c in evidence_claims(row):
        if not c.lower().startswith("param"):
            continue
        m = re.search(r"\{.*\}", c, re.S)
        try:
            d = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            d = {}
        v = str(d.get("value", "")).strip()
        if v:
            out.append((int(d.get("index", len(out) + 1)), v))
    return [v for _, v in sorted(out)]


def contract_for(row: dict, allow_params: bool = False) -> str | None:
    """The evidence claim that reads as the contract: one starting 'contract', else the first claim that is not
    metadata (conv/param/subsystem/name/...). None when the row has no such claim; with allow_params a
    params-only row yields '(no contract recorded) params: <types and names>' so a judge can still compare."""
    claims = evidence_claims(row)
    for c in claims:
        if c.lower().startswith("contract"):
            return _CONTRACT_PREFIX.sub("", c, count=1)
    for c in claims:
        if not _META_CLAIM.match(c):
            return c
    if allow_params:
        params = param_claims(row)
        if params:
            return "(no contract recorded) params: " + ", ".join(params)
    return None


_SPEC_CACHE: dict[str, list[str]] = {}


def spec_paragraphs_for(name: str, addr: str, max_chars: int = SPEC_MAX_CHARS) -> tuple[list[dict], bool]:
    """Paragraphs of subsystems/*.md that mention the name (as a word) or the address; capped at max_chars."""
    if not _SPEC_CACHE:
        for p in sorted(SUBSYSTEMS.glob("*.md")):
            if p.name in SPEC_SKIP:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            _SPEC_CACHE[p.stem] = [para.strip() for para in re.split(r"\n\s*\n", text) if para.strip()]
    a = blind.addr0x(addr)
    pats = [re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")] if name else []
    pats.append(re.compile(r"(?<![0-9a-fA-Fx])" + re.escape(a) + r"(?![0-9a-fA-F])"))
    out, used, truncated = [], 0, False
    for doc, paras in _SPEC_CACHE.items():
        for para in paras:
            if not any(p.search(para) for p in pats):
                continue
            room = max_chars - used
            if room <= 0:
                truncated = True
                break
            text = para if len(para) <= room else para[: max(0, room - 3)].rstrip() + "..."
            truncated = truncated or text != para
            out.append({"doc": doc, "text": text})
            used += len(text)
    return out, truncated


def callers_of(addr: str) -> list[str]:
    return list(blind.load_callgraph().get(blind.addr8(addr), {}).get("callers", []))


def name_of(addr8: str) -> str:
    r = blind.functions_by_addr().get(addr8)
    return r["name"] if r and r["name"] else f"FUN_{addr8}"


# ----------------------------------------------------------------------------- 4.1 cadence-claim

# Cadence vocabulary (VERIFICATION-PROGRAM.md section 10: most specs say nothing about when a function runs, so
# the census classification is the cadence record; the model step is kept only for functions whose contract or
# spec text makes a cadence claim). The single place this list lives. Matched case-insensitively as whole words
# over the contract plus the spec paragraphs; a hyphen or space between words is accepted ("per-frame", "per frame").
CADENCE_VOCAB = [
    # periodic
    "per frame", "each frame", "every frame", "once a frame", "frame loop", "main loop", "render loop",
    "per tick", "each tick", "every tick", "per substep", "each substep", "every substep", "per step",
    "per second", "per sim second", "hz", "every n", "every \\d+", "fixed rate", "fixed step",
    # once / bounded
    "once per", "once at", "once on", "once when", "only once", "exactly once", "each call", "every call",
    "per call", "per shot", "per hit", "per event", "per object", "per entity", "per vehicle", "per pair",
    "per mission", "per level", "per session",
    # lifecycle
    "on load", "at load", "mission load", "level load", "on init", "at init", "at startup", "on startup",
    "at boot", "from winmain", "at exit", "on exit", "at shutdown", "on shutdown", "teardown", "at mission start",
    "mission start", "mission end", "on save", "on restore",
    # event-triggered
    "when fired", "on fire", "when hit", "on hit", "on impact", "on collision", "on damage", "on spawn",
    "on destroy", "on death", "on keypress", "on key", "when pressed", "when triggered",
    # never / dead
    "never", "dead code", "unreachable", "debug only", "network only",
    # mechanism
    "callback", "timer", "scheduled", "polled", "idle",
]


def _vocab_regex(words: list[str]) -> re.Pattern:
    alts = []
    for w in words:
        parts = [p for p in w.split(" ") if p]
        alts.append(r"[\s-]+".join(parts))
    return re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(alts) + r")(?![A-Za-z0-9_])", re.I)


CADENCE_RE = _vocab_regex(CADENCE_VOCAB)
SKIP_REASON_NO_CADENCE = "no cadence text: the census is the record"


def cadence_text_hits(contract: str, paras: list[dict]) -> list[str]:
    """Distinct vocabulary matches (lower-cased) in the contract + spec paragraphs; empty = skip the unit."""
    text = contract + "\n" + "\n".join(p["text"] for p in paras)
    seen = []
    for m in CADENCE_RE.finditer(text):
        s = re.sub(r"[\s-]+", " ", m.group(0).lower())
        if s not in seen:
            seen.append(s)
    return seen


def make_cadence_claim(args) -> None:
    rows = select_rows("proposed", args.prefix, args.limit)
    counts = Counter()
    skipped: list[tuple[str, str, str]] = []
    passed: list[tuple[str, str, list[str]]] = []
    for r in rows:
        contract = contract_for(r)
        if contract is None:
            counts["no-contract"] += 1
            continue
        paras, truncated = spec_paragraphs_for(r["name"], r["addr"])
        if args.only_with_cadence_text:
            hits = cadence_text_hits(contract, paras)
            if not hits:
                counts["skipped-no-cadence-text"] += 1
                skipped.append((blind.addr0x(r["addr"]), r["name"], SKIP_REASON_NO_CADENCE))
                continue
            passed.append((blind.addr0x(r["addr"]), r["name"], hits))
        if args.dry_run:
            counts["would-write"] += 1
            continue
        callers = []
        for c in callers_of(r["addr"]):
            res = load_result("cadence-claim", c)
            cad = None
            if res and isinstance(res.get("payload"), dict):
                cad = res["payload"].get("cadence")
                if cad == "unknown":
                    cad = None
            callers.append({"name": name_of(c), "cadence": cad})
        inputs = {
            "name": r["name"],
            "subsystem": r["subsystem"] or r["name"].split("_", 1)[0],
            "contract": contract,
            "spec_paragraphs": paras,
            "spec_truncated": truncated,
            "callers": callers,
            "size_bytes": int(r["size"]) if r["size"].isdigit() else None,
        }
        counts[write_unit("cadence-claim", r["addr"], r["name"], inputs, args.force)] += 1
    if args.only_with_cadence_text:
        d = QUEUE / "cadence-claim"
        d.mkdir(parents=True, exist_ok=True)
        lines = [f"# cadence-claim units not built ({len(skipped)} of {len(rows)} selected `proposed` rows; "
                 f"{counts['no-contract']} more have no contract claim at all). Vocabulary: make_units.CADENCE_VOCAB.",
                 "# addr\tname\treason"]
        lines += [f"{a}\t{n}\t{why}" for a, n, why in skipped]
        (d / "SKIPPED.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if args.dry_run:
            (d / "PASSED.dryrun.txt").write_text(
                "# addr\tname\tcadence vocabulary matched (dry run, no units written)\n" +
                "".join(f"{a}\t{n}\t{'; '.join(h)}\n" for a, n, h in passed), encoding="utf-8")
        print(f"cadence pre-filter: {len(passed)} rows carry cadence text, {len(skipped)} skipped -> {d / 'SKIPPED.txt'}")
    print("cadence-claim:", dict(counts), "->", QUEUE / "cadence-claim")


# ----------------------------------------------------------------------------- 4.5 blind-name

def stratum_of(row: dict) -> str:
    return row["subsystem"] or row["name"].split("_", 1)[0]


def stratified_sample(rows: list[dict], n: int, rng: random.Random, floor: int = 5) -> list[dict]:
    """n rows sampled per subsystem prefix in proportion to the prefix's share of `rows`, with at least `floor`
    per prefix where the prefix has that many (all of them when it has fewer). Quotas: max(floor, n*share),
    then largest-remainder fill or largest-quota trim to land on exactly n."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(stratum_of(r), []).append(r)
    n = min(n, len(rows))
    # Strata whose proportional share falls below the floor are pinned at the floor (or their whole population);
    # the remaining budget is shared proportionally among the others. Repeat until no new stratum drops below.
    pinned: dict[str, int] = {}
    while True:
        free = [k for k in groups if k not in pinned]
        budget = n - sum(pinned.values())
        free_total = sum(len(groups[k]) for k in free)
        exact = {k: len(groups[k]) * budget / free_total for k in free}
        newly = {k: min(floor, len(groups[k])) for k in free if exact[k] < min(floor, len(groups[k]))}
        if not newly:
            break
        pinned.update(newly)
    quota = dict(pinned)
    for k in free:
        quota[k] = min(len(groups[k]), int(exact[k]))
    # largest-remainder fill to exactly n
    order = sorted(free, key=lambda k: exact[k] - int(exact[k]), reverse=True)
    i = 0
    while sum(quota.values()) < n and order:
        k = order[i % len(order)]
        if quota[k] < len(groups[k]):
            quota[k] += 1
        i += 1
    out = []
    for k in sorted(groups):
        out.extend(rng.sample(sorted(groups[k], key=lambda r: int(r["addr"], 16)), quota[k]))
    return out


def read_addr_list(spec: str) -> set[str]:
    """'0x405560,0x407500' or '@file' (one per line; CRLF, blank and # lines tolerated) -> set of addr8."""
    toks = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("@"):
            for line in Path(part[1:]).read_text(encoding="utf-8-sig").splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    toks.append(line.split()[0])
        else:
            toks.append(part)
    return {blind.addr8(t) for t in toks}


def make_blind_name(args) -> None:
    rows = select_rows("proposed", args.prefix, None)
    if getattr(args, "addrs", None):
        want = read_addr_list(args.addrs)
        rows = [r for r in rows if blind.addr8(r["addr"]) in want]
        missing = want - {blind.addr8(r["addr"]) for r in rows}
        if missing:
            print(f"--addrs: {len(missing)} address(es) are not proposed rows: {' '.join(sorted(missing)[:10])}")
    if args.exclude_existing:
        d = QUEUE / "blind-name"
        have = {p.name.split(".")[0] for p in d.glob("*.json")} if d.exists() else set()
        rows = [r for r in rows if blind.addr0x(r["addr"]) not in have]
    if args.sample:
        rng = random.Random(args.seed)
        if args.stratify:
            rows = stratified_sample(rows, args.sample, rng)
        else:
            rows = rng.sample(rows, min(args.sample, len(rows)))
        rows.sort(key=lambda r: int(r["addr"], 16))
        print("sample per prefix:", dict(sorted(Counter(stratum_of(r) for r in rows).items())))
    if args.limit:
        rows = rows[: args.limit]
    counts = Counter()
    for r in rows:
        inputs = blind.blind_inputs(r["addr"])
        if inputs is None:
            counts["no-decomp"] += 1
            continue
        leaked = blind.leaks(inputs)
        if leaked:
            counts["leak-blocked"] += 1
            print(f"  {r['addr']}: map names still visible after stripping, unit not written: {leaked[:5]}")
            continue
        # name is deliberately null: the unit must not carry the map's name.
        counts[write_unit("blind-name", r["addr"], None, inputs, args.force)] += 1
    print("blind-name:", dict(counts), "->", QUEUE / "blind-name")


# ----------------------------------------------------------------------------- 4.5 blind-judge

BLIND_FIXES_GLOB = "blind-fixes-*.json"


def blind_adopted_addrs() -> set[str]:
    """Addresses whose contract in the map was adopted from a blind reading: every function row of
    status/tasks/blind-fixes-*.json (merged or not). A judge unit for one of these would compare the reading with
    a contract derived from it, so make_blind_judge skips them (counter `blind-adopted-contract`)."""
    out: set[str] = set()
    for p in sorted((ROOT / "status" / "tasks").glob(BLIND_FIXES_GLOB)):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in doc.get("functions") or []:
            a = row.get("addr") or row.get("address")
            if a:
                out.add(blind.addr8(a))
    return out


def make_blind_judge(args) -> None:
    """One judge unit per canonical blind-name result. With --reader S: one per <addr>.S.result.json blind-name
    result (a second independent reader, worker.py --suffix S), written as queue/blind-judge/<addr>.S.json; the
    gate counts its verdict as the second reader of the section 6 utility rule."""
    by_addr = blind.functions_by_addr()
    counts = Counter()
    reader = getattr(args, "reader", "") or ""
    adopted = blind_adopted_addrs() if getattr(args, "exclude_blind_adopted", True) else set()
    for res_path in sorted((QUEUE / "blind-name").glob("*.result.json")):
        addr = res_path.name[: -len(".result.json")]
        if reader:
            if not addr.endswith("." + reader):
                continue
            addr = addr[: -len(reader) - 1]
        if "." in addr:  # <addr>.<suffix>.result.json / <addr>.v1.result.json: comparison sets, not the canonical reading
            continue
        if blind.addr8(addr) in adopted:
            # the map's contract for this row was written from a blind reading (status/tasks/blind-fixes-*.json);
            # judging it against that reading is circular (BLIND-PASS-4.md 0, BLIND-PASS-4-SLICE2.md 0)
            counts["blind-adopted-contract"] += 1
            continue
        try:
            res = json.loads(res_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            counts["bad-result"] += 1
            continue
        payload = res.get("payload") or {}
        if not payload.get("name") or res.get("verdict") == "INCONCLUSIVE":
            counts["blind-inconclusive"] += 1
            continue
        row = by_addr.get(blind.addr8(addr))
        if row is None:
            counts["not-in-tsv"] += 1
            continue
        contract = contract_for(row, allow_params=True)
        if contract is None:
            counts["no-contract"] += 1
            continue
        map_side = {"name": row["name"], "contract": contract}
        blind_side = {"name": payload["name"], "contract": payload.get("contract", "")}
        rng = random.Random(f"{args.seed}:{blind.addr0x(addr)}")
        map_is_a = rng.random() < 0.5
        a, b = (map_side, blind_side) if map_is_a else (blind_side, map_side)
        inputs = {"A": a, "B": b}
        hidden = {"A": "map" if map_is_a else "blind", "B": "blind" if map_is_a else "map",
                  "map_name": row["name"], "blind_name": payload["name"],
                  "blind_confidence": payload.get("confidence"), "seed": args.seed}
        if reader:
            hidden["reader"] = reader
            hidden["reader_model"] = (res.get("meta") or {}).get("model")
        counts[write_unit("blind-judge", addr, row["name"], inputs, args.force, hidden=hidden, reader=reader)] += 1
    print("blind-judge:", dict(counts), "->", QUEUE / "blind-judge")


# ----------------------------------------------------------------------------- 4.2 census-grade

def resolve_run(spec: str) -> Path:
    p = Path(spec)
    if p.is_file():
        return p
    if p.is_dir():
        f = p / "census.classified.json"
        if f.exists():
            return f
        raise SystemExit(f"{p} has no census.classified.json")
    cands = sorted(RUNS.glob(f"{spec}/*/census.classified.json"))
    if cands:
        return cands[-1]
    raise SystemExit(f"run not found: {spec} (no dir, file, or verify/runs/{spec}/*/census.classified.json)")


EVENT_CODES = {"1": "shot", "2": "explosion", "3": "impact"}  # events.csv `type` codes (census.py classify_run)
HIDE_FROM_MODEL = {"hook", "legacy_class", "name", "addr", "scenario", "class", "classification", "callers",
                   "calls_per_frame_hist", "substep_offset", "per_substep_mult", "per_frame_const"}


def load_census(path: Path) -> tuple[str, dict[str, dict], dict]:
    """-> (scenario, {addr8: row}, {event_type: count}).

    Accepts census.py's census.classified.json ({run, scenario, frames, frames_live, events:<int>, functions:[rows
    with `class`, callers {ra: {n, name}}, presence/mode/cv stats, note]}), the section 2.2 object form
    ({scenario, events:{type: n}, functions:[rows with `classification`, calls_per_frame_hist]}), or a bare list of
    rows (scenario from the run directory). Rows are enriched with calls_per_frame_hist / frames_with_calls from
    the run's census.jsonl when the classified rows lack them. Rows classed `not_hooked` are dropped."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        rows, scenario, events, frames = doc, path.parent.parent.name, {}, None
    else:
        rows = doc.get("functions") or doc.get("rows") or []
        if isinstance(rows, dict):
            rows = [dict(v, addr=k) for k, v in rows.items()]
        scenario = doc.get("scenario") or path.parent.parent.name
        events = doc.get("events") if isinstance(doc.get("events"), dict) else {}
        frames = doc.get("frames")
    if not events:
        events = events_from_csv(path.parent / "events.csv")
    hist = {}
    jl = path.parent / "census.jsonl"
    if jl.exists():
        for line in jl.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("addr"):
                hist[blind.addr8(r["addr"])] = r
    by_addr = {}
    for r in rows:
        if not r.get("addr"):
            continue
        r = dict(r)
        r["classification"] = r.get("classification") or r.get("class")
        if r["classification"] in (None, "not_hooked"):
            continue
        r.setdefault("scenario", scenario)
        if frames is not None:
            r.setdefault("frames", frames)
        a8 = blind.addr8(r["addr"])
        extra = hist.get(a8, {})
        for k in ("calls_per_frame_hist", "frames_with_calls", "frames"):
            if k not in r and k in extra:
                r[k] = extra[k]
        by_addr[a8] = r
    return scenario, by_addr, events


def events_from_csv(path: Path) -> dict:
    """Telemetry event counts from a run's events.csv (column event/type/kind/name; numeric codes mapped)."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        col = next((c for c in (reader.fieldnames or []) if c.lower() in ("event", "type", "kind", "name")), None)
        if col is None:
            return {}
        return dict(Counter(EVENT_CODES.get(str(row[col]), str(row[col])) for row in reader if row.get(col)))


def _caller_views(callers) -> list[dict]:
    """callers as {ra: n} | {ra: {n, name}} | [[ra, n], ...] -> [{name, calls}] by count, names resolved."""
    items = []
    if isinstance(callers, dict):
        for a, v in callers.items():
            n = v.get("n", 0) if isinstance(v, dict) else v
            nm = v.get("name") if isinstance(v, dict) else None
            if not nm or nm.startswith("FUN_") or nm.startswith("0x"):
                nm = name_of(blind.addr8(a)) if str(a).startswith("0x") else str(a)
            items.append((nm, int(n or 0)))
    elif isinstance(callers, list):
        for a, n in callers:
            items.append((name_of(blind.addr8(a)), int(n or 0)))
    items.sort(key=lambda x: -x[1])
    return [{"name": n, "calls": c} for n, c in items[:8]]


def census_view(row: dict) -> dict:
    """Trim a census row to what the model should see: the classifier's enum, counts, histogram, the classifier's
    statistics and note when present, callers as names (return sites)."""
    hist = row.get("calls_per_frame_hist")
    if isinstance(hist, dict):
        # buckets are "0", "1", ... plus an overflow bucket such as "64+" (the census_frames.js cap)
        def _bucket(kv):
            s = str(kv[0]).rstrip("+")
            return (int(s) if s.isdigit() else 1 << 30, str(kv[0]))
        hist = {str(k): v for k, v in sorted(hist.items(), key=_bucket)}
    view = {
        "scenario": row.get("scenario"),
        "classification": row.get("classification"),
        "frames": row.get("frames"),
        "calls": row.get("calls"),
        "frames_with_calls": row.get("frames_with_calls"),
        "calls_per_frame_hist": hist,
        "first_frame": row.get("first_frame"),
        "last_frame": row.get("last_frame"),
        "callers": _caller_views(row.get("callers") or {}),
    }
    for k, v in row.items():  # classifier statistics (presence, mode_share, cv, substep_match, note, ...)
        if k not in view and k not in HIDE_FROM_MODEL and isinstance(v, (int, float, str, type(None))):
            view[k] = v
    return view


def script_grade(claim: dict, views: list[dict]) -> str | None:
    """'match' when every scenario's classification equals the claim (or is `never` and the claim is a menu/init
    kind elsewhere); None when a model must grade it. `irregular` always goes to the model."""
    obs = {v["classification"] for v in views}
    if "irregular" in obs or not obs:
        return None
    if obs == {claim["cadence"]}:
        return "match"
    return None


def make_census_grade(args) -> None:
    by_addr = blind.functions_by_addr()
    per_addr: dict[str, list[dict]] = {}
    events: dict[str, dict] = {}
    for spec in args.run:
        path = resolve_run(spec)
        scenario, rows, ev = load_census(path)
        events[scenario] = ev
        for a8, row in rows.items():
            row = dict(row)
            row.setdefault("scenario", scenario)
            per_addr.setdefault(a8, []).append(row)
    counts = Counter()
    for a8, rows in sorted(per_addr.items()):
        res = load_result("cadence-claim", a8)
        if not res or not isinstance(res.get("payload"), dict):
            counts["no-claim"] += 1
            continue
        claim = res["payload"]
        if claim.get("cadence") in (None, "unknown"):
            counts["claim-unknown"] += 1
            continue
        fnrow = by_addr.get(a8, {})
        views = [census_view(r) for r in rows]
        inputs = {
            "name": fnrow.get("name") or f"FUN_{a8}",
            "subsystem": fnrow.get("subsystem", ""),
            "claim": claim,
            "claim_reason": res.get("reason", ""),
            "census": views,
            "events": {v["scenario"]: events.get(v["scenario"], {}) for v in views},
        }
        state = write_unit("census-grade", a8, inputs["name"], inputs, args.force)
        counts[state] += 1
        if state == "written" and script_grade(claim, views) == "match":
            observed = views[0]["classification"]
            result = {"unit_id": unit_id("census-grade", a8), "verdict": "PASS",
                      "payload": {"match": True, "observed": observed,
                                  "note": f"claim {claim['cadence']} == observed {observed} in every scenario"},
                      "reason": "Graded by script: census.classification equals claim.cadence in all scenarios.",
                      "meta": {"graded_by": "script", "scenarios": [v["scenario"] for v in views]}}
            unit_paths("census-grade", a8)[1].write_text(json.dumps(result, indent=1), encoding="utf-8")
            counts["script-pass"] += 1
    print("census-grade:", dict(counts), "->", QUEUE / "census-grade",
          "(script-pass units already carry a .result.json; the rest go to the worker)")


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="kind", required=True)

    def common(p):
        p.add_argument("--prefix", type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
                       help="comma-separated subsystem prefixes (functions.tsv subsystem column or name prefix)")
        p.add_argument("--limit", type=int)
        p.add_argument("--force", action="store_true", help="rewrite unit files that already exist (results untouched)")

    p = sub.add_parser("cadence-claim"); common(p)
    p.add_argument("--only-with-cadence-text", action=argparse.BooleanOptionalAction, default=True,
                   help="skip functions whose contract + spec paragraphs contain no cadence vocabulary "
                        "(CADENCE_VOCAB); skipped rows go to queue/cadence-claim/SKIPPED.txt (default on)")
    p.add_argument("--dry-run", action="store_true",
                   help="count and write SKIPPED.txt / PASSED.dryrun.txt, write no unit files")
    p.set_defaults(fn=make_cadence_claim)
    p = sub.add_parser("blind-name"); common(p)
    p.add_argument("--sample", type=int, help="random sample size over the selected rows")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--stratify", action="store_true",
                   help="sample proportionally per subsystem prefix (>= 5 per prefix where available)")
    p.add_argument("--exclude-existing", action="store_true",
                   help="skip functions that already have a blind-name unit in the queue (earlier samples)")
    p.add_argument("--addrs", help="restrict to these addresses: comma-separated, or @file with one per line")
    p.set_defaults(fn=make_blind_name)
    p = sub.add_parser("blind-judge")
    p.add_argument("--seed", type=int, default=1, help="A/B side assignment seed (per unit: seed + addr)")
    p.add_argument("--force", action="store_true")
    p.add_argument("--reader", default="",
                   help="build judge units for the second-reader blind-name set <addr>.<reader>.result.json "
                        "(worker.py --suffix <reader>), written as <addr>.<reader>.json")
    p.add_argument("--exclude-blind-adopted", action=argparse.BooleanOptionalAction, default=True,
                   help="skip rows whose contract was adopted from a blind reading (every function in "
                        "status/tasks/blind-fixes-*.json): judging those against the reading is circular (default on)")
    p.set_defaults(fn=make_blind_judge)
    p = sub.add_parser("census-grade")
    p.add_argument("run", nargs="+", help="run dir, census.classified.json, or scenario id (latest)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=make_census_grade)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
