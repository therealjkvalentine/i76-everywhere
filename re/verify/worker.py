#!/usr/bin/env python3
"""Worker loop (VERIFICATION-PROGRAM.md section 2.7).

    python verify/worker.py --kind cadence-claim --model haiku --max 20 [--dry-run] [--escalated]

Pops units from verify/queue/<kind>/*.json that have neither a .result.json nor an .escalate.json, renders
verify/prompts/<kind>.md with the unit's fields, pipes the prompt to
    claude -p --model <id> --output-format json --tools "" --no-session-persistence --strict-mcp-config
validates the reply against verify/schemas/<kind>.schema.json (jsonschema when importable, else a minimal
draft-07 subset), retries once with the validation error appended, writes <unit>.result.json (reply + meta) or
<unit>.escalate.json (attempt history), and appends one line to verify/journal.jsonl. Token counts and cost are
the CLI's `usage` / `total_cost_usd` fields, never the model's estimate.

--dry-run renders the prompts to verify/dryrun/<kind>/ and calls nothing.
--escalated re-runs units that have an .escalate.json (and no result) with the failure history appended; meant
  for --model sonnet.
--unit 0x405560,0x407500 (or blind-judge-0x405560, or @list.txt with one id per line, CRLF tolerated) selects
  exactly those units; ids that match no pending unit are reported, never silently dropped.
--parallel N runs N units at a time (a thread pool; each unit is its own `claude -p` call). journal.jsonl is
  appended under a lock file (journal.jsonl.lock: msvcrt.locking on Windows, fcntl.flock elsewhere) so parallel
  workers, in one process or several, never lose a line.
Rate limits / overloads: sleep 30, 60, 120 s and retry (3x) before giving up on the unit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    import msvcrt  # Windows
except ImportError:  # pragma: no cover
    msvcrt = None
    import fcntl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blind  # noqa: E402

VERIFY = blind.VERIFY
QUEUE = VERIFY / "queue"
PROMPTS = VERIFY / "prompts"
SCHEMAS = VERIFY / "schemas"
DRYRUN = VERIFY / "dryrun"
JOURNAL = VERIFY / "journal.jsonl"

MODELS = {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-5"}
SYSTEM_PROMPT = ("You are a verification worker for a reverse-engineering map. You answer exactly one bounded "
                 "judgement per request from the inputs given and nothing else. Reply with a single JSON object: "
                 "no prose, no markdown, no code fences.")
RATE_SLEEPS = (30, 60, 120)
RATE_RE = re.compile(r"rate.?limit|429|overloaded|529|too many requests|capacity", re.I)
AUTH_RE = re.compile(r"authentication required|not logged in|sign in", re.I)

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover
    jsonschema = None


# ----------------------------------------------------------------------------- rendering

def render(template: str, unit: dict) -> str:
    """{{field}} / {{inputs.field}} -> the unit's value; strings verbatim, other values as JSON, missing '(none)'.
    `hidden` is never reachable from a template."""
    def lookup(path: str):
        cur = unit
        for part in path.split("."):
            if part == "hidden":
                return "(not available)"
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    def fmt(v):
        if v is None:
            return "(none)"
        if isinstance(v, str):
            return v
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list) and not v:
            return "(none)"
        return json.dumps(v, indent=1, ensure_ascii=False)

    return re.sub(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}", lambda m: fmt(lookup(m.group(1))), template)


def load_template(kind: str) -> str:
    p = PROMPTS / f"{kind}.md"
    if not p.exists():
        sys.exit(f"no prompt template for kind {kind}: {p}")
    return p.read_text(encoding="utf-8")


def load_schema(kind: str) -> dict:
    p = SCHEMAS / f"{kind}.schema.json"
    if not p.exists():
        sys.exit(f"no schema for kind {kind}: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- validation

def _minimal_validate(schema: dict, inst, path="$") -> None:
    """Draft-07 subset: type, enum, const, required, properties, additionalProperties, items, pattern,
    minLength/maxLength, minItems/maxItems, if/then/else."""
    def fail(msg):
        raise ValueError(f"{path}: {msg}")

    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        ok = any(
            (ty == "object" and isinstance(inst, dict)) or (ty == "array" and isinstance(inst, list)) or
            (ty == "string" and isinstance(inst, str)) or (ty == "null" and inst is None) or
            (ty == "boolean" and isinstance(inst, bool)) or
            (ty == "integer" and isinstance(inst, int) and not isinstance(inst, bool)) or
            (ty == "number" and isinstance(inst, (int, float)) and not isinstance(inst, bool))
            for ty in types)
        if not ok:
            fail(f"expected type {t}, got {type(inst).__name__}")
    if "enum" in schema and inst not in schema["enum"]:
        fail(f"{inst!r} is not one of {schema['enum']}")
    if "const" in schema and inst != schema["const"]:
        fail(f"{inst!r} != {schema['const']!r}")
    if isinstance(inst, str):
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            fail(f"{inst!r} does not match {schema['pattern']}")
        if "maxLength" in schema and len(inst) > schema["maxLength"]:
            fail(f"longer than {schema['maxLength']}")
        if "minLength" in schema and len(inst) < schema["minLength"]:
            fail(f"shorter than {schema['minLength']}")
    if isinstance(inst, dict):
        for k in schema.get("required", []):
            if k not in inst:
                fail(f"missing required property {k!r}")
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props:
                _minimal_validate(props[k], v, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                fail(f"additional property {k!r} not allowed")
    if isinstance(inst, list):
        if "maxItems" in schema and len(inst) > schema["maxItems"]:
            fail(f"more than {schema['maxItems']} items")
        if "minItems" in schema and len(inst) < schema["minItems"]:
            fail(f"fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, v in enumerate(inst):
                _minimal_validate(schema["items"], v, f"{path}[{i}]")
    if "if" in schema:
        try:
            _minimal_validate(schema["if"], inst, path)
            branch = schema.get("then")
        except ValueError:
            branch = schema.get("else")
        if branch:
            _minimal_validate(branch, inst, path)


def validate(schema: dict, inst) -> str | None:
    """None when valid, else the error text."""
    try:
        if jsonschema is not None:
            jsonschema.validate(inst, schema, cls=jsonschema.Draft7Validator)
        else:
            _minimal_validate(schema, inst)
    except Exception as e:  # noqa: BLE001
        msg = getattr(e, "message", None) or str(e)
        p = getattr(e, "json_path", None)
        return f"{p}: {msg}" if p else msg
    return None


def kind_checks(kind: str, unit: dict, reply: dict) -> str | None:
    """Cross-field rules the schema cannot express (section 4 validators)."""
    if reply.get("unit_id") != unit["unit_id"]:
        return f"unit_id must be {unit['unit_id']!r}"
    payload = reply.get("payload") or {}
    verdict = reply.get("verdict")
    if kind == "cadence-claim":
        allowed = {c["name"] for c in unit["inputs"].get("callers", [])} | set(blind.functions_by_name())
        bad = [c for c in payload.get("callers_expected", []) if c not in allowed]
        if bad:
            return f"callers_expected names not in functions.tsv: {bad}"
        if (payload.get("cadence") == "unknown") != (verdict == "INCONCLUSIVE"):
            return "cadence 'unknown' must pair with verdict INCONCLUSIVE and vice versa"
    elif kind == "census-grade":
        if payload.get("match") is True and verdict != "PASS":
            return "match true requires verdict PASS"
        if verdict == "PASS" and payload.get("match") is not True:
            return "verdict PASS requires match true"
    elif kind == "blind-judge":
        want = {"same": "PASS", "compatible": "PASS", "different": "FAIL"}.get(payload.get("agreement"))
        if want and verdict != want and verdict != "INCONCLUSIVE":
            return f"agreement {payload.get('agreement')} requires verdict {want}"
    elif kind == "blind-name":
        if verdict == "FAIL":
            return "blind-name never uses FAIL (PASS or INCONCLUSIVE)"
    return None


def extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(text[start:end + 1])


# ----------------------------------------------------------------------------- CLI call

class ClaudeUnavailable(RuntimeError):
    pass


EFFORT = "low"  # 'high' made Haiku spend 5-7k thinking tokens (45-75 s, $0.03-0.04) per unit
# MAX_THINKING_TOKENS cap passed to the CLI. Measured on cadence-claim: default (uncapped, effort low) ~3.7k output
# tokens, 36 s, $0.02 per unit; 0 (no thinking) 123 output tokens, 4 s, $0.003 but over-claimed on the sample read.
MAX_THINKING = 1024


def claude_cmd(model_id: str, effort: str = EFFORT, max_thinking: int | None = MAX_THINKING) -> list[str]:
    exe = shutil.which("claude")
    return [exe or "claude", "-p", "--model", model_id, "--output-format", "json", "--tools", "",
            "--no-session-persistence", "--strict-mcp-config", "--effort", effort,
            "--system-prompt", SYSTEM_PROMPT]


def call_claude(prompt: str, model_id: str, timeout: int, effort: str = EFFORT,
                max_thinking: int | None = MAX_THINKING) -> dict:
    """Runs the CLI once (with rate-limit retries). Returns the CLI's JSON envelope."""
    cmd = claude_cmd(model_id, effort)
    if shutil.which("claude") is None:
        raise ClaudeUnavailable("claude CLI not on PATH. Run this yourself (prompt on stdin):\n  " +
                                " ".join(_q(c) for c in cmd) + " < prompt.md")
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)  # allow running from inside another Claude Code session
    env["CLAUDE_EFFORT"] = effort  # an inherited CLAUDE_EFFORT=high would otherwise win
    if max_thinking is not None:
        env["MAX_THINKING_TOKENS"] = str(max_thinking)  # 0 disables thinking entirely
    for attempt in range(len(RATE_SLEEPS) + 1):
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"claude timed out after {timeout}s")
        out = proc.stdout.strip()
        try:
            env_json = json.loads(out) if out else {}
        except json.JSONDecodeError:
            env_json = {}
        text = str(env_json.get("result", "")) if env_json else (out or proc.stderr)
        if env_json and not env_json.get("is_error"):
            env_json["_ms"] = int((time.time() - t0) * 1000)
            return env_json
        if AUTH_RE.search(text or ""):
            raise ClaudeUnavailable("claude CLI is not authenticated here; run interactively once:\n  claude login")
        if RATE_RE.search((text or "") + proc.stderr) and attempt < len(RATE_SLEEPS):
            print(f"    rate limited; sleeping {RATE_SLEEPS[attempt]}s", flush=True)
            time.sleep(RATE_SLEEPS[attempt])
            continue
        raise RuntimeError(f"claude error (exit {proc.returncode}): {(text or proc.stderr)[:400]}")
    raise RuntimeError("rate limited 3x, giving up on this unit")


def _q(s: str) -> str:
    return f'"{s}"' if (" " in s or s == "") else s


def usage_of(env_json: dict) -> dict:
    u = env_json.get("usage") or {}
    inp = int(u.get("input_tokens") or 0)
    cc = int(u.get("cache_creation_input_tokens") or 0)
    cr = int(u.get("cache_read_input_tokens") or 0)
    return {"input_tokens": inp + cc + cr, "input_uncached": inp, "cache_creation": cc, "cache_read": cr,
            "output_tokens": int(u.get("output_tokens") or 0), "cost_usd": env_json.get("total_cost_usd"),
            "ms": env_json.get("_ms") or env_json.get("duration_ms")}


# ----------------------------------------------------------------------------- loop

def side_path(unit_path: Path, what: str, suffix: str = "") -> Path:
    """<addr>.result.json / <addr>.escalate.json, or <addr>.<suffix>.result.json for a parallel result set
    (e.g. --suffix sonnet keeps a second model's answers beside the canonical ones; make_units reads only the
    canonical file)."""
    mid = f".{suffix}" if suffix else ""
    return unit_path.with_name(f"{unit_path.stem}{mid}.{what}.json")


def pending_units(kind: str, escalated: bool, suffix: str = "") -> list[Path]:
    d = QUEUE / kind
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        if p.name.endswith(".result.json") or p.name.endswith(".escalate.json"):
            continue
        result = side_path(p, "result", suffix)
        esc = side_path(p, "escalate", suffix)
        if result.exists():
            continue
        if escalated != esc.exists():
            continue
        out.append(p)
    return out


JOURNAL_LOCK = JOURNAL.with_name(JOURNAL.name + ".lock")
_journal_thread_lock = threading.Lock()  # threads of one process; the lock file covers separate processes
LOCK_WAIT_S = 60


class _FileLock:
    """Exclusive lock on JOURNAL_LOCK. Windows: msvcrt.locking on the first byte (non-blocking, polled, so a
    dead holder's lock dies with its handle); elsewhere fcntl.flock. The lock file itself is never written."""

    def __init__(self, path: Path):
        self.path = path
        self.fh = None

    def __enter__(self):
        self.fh = open(self.path, "a+b")
        deadline = time.time() + LOCK_WAIT_S
        if msvcrt is not None:
            while True:
                try:
                    self.fh.seek(0)
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
                    return self
                except OSError:
                    if time.time() > deadline:
                        raise RuntimeError(f"could not lock {self.path} within {LOCK_WAIT_S}s")
                    time.sleep(0.02)
        else:
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX)
            return self

    def __exit__(self, *exc):
        try:
            if msvcrt is not None:
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        finally:
            self.fh.close()


def journal(entry: dict) -> None:
    """Append one line. Open-append-close happens entirely under the lock, so two writers never interleave or
    lose a line (one line of 575 went missing with four unlocked partitions, BLIND-SAMPLE-2.md section 3)."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _journal_thread_lock, _FileLock(JOURNAL_LOCK):
        with open(JOURNAL, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())


def run_unit(unit_path: Path, kind: str, model: str, template: str, schema: dict, timeout: int,
             escalated: bool, effort: str = EFFORT, max_thinking: int | None = MAX_THINKING,
             suffix: str = "") -> str:
    unit = json.loads(unit_path.read_text(encoding="utf-8"))
    prompt = render(template, unit)
    esc_path = side_path(unit_path, "escalate", suffix)
    model_id = MODELS.get(model, model)
    history = []
    if escalated and esc_path.exists():
        prev = json.loads(esc_path.read_text(encoding="utf-8"))
        history = prev.get("attempts", [])
        prompt += ("\n\n## Failure history (a smaller model's replies that failed validation)\n" +
                   json.dumps(history, indent=1)[:4000] + "\nReturn a corrected reply.")
    attempts = []
    totals = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "ms": 0}
    cur_prompt = prompt
    for attempt in range(2):
        env_json = call_claude(cur_prompt, model_id, timeout, effort, max_thinking)
        use = usage_of(env_json)
        for k in totals:
            totals[k] += (use.get(k) or 0)
        raw = str(env_json.get("result", ""))
        try:
            reply = extract_json(raw)
            err = validate(schema, reply) or kind_checks(kind, unit, reply)
        except (json.JSONDecodeError, ValueError) as e:
            reply, err = None, f"reply is not JSON: {e}"
        attempts.append({"attempt": attempt + 1, "error": err, "raw": raw[:4000], "usage": use})
        if err is None:
            reply["meta"] = {"model": model_id, "effort": effort, "max_thinking": max_thinking,
                             "attempts": attempt + 1, "escalated": escalated, "suffix": suffix or None,
                             "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **use,
                             **{k: v for k, v in totals.items()}}
            side_path(unit_path, "result", suffix).write_text(
                json.dumps(reply, indent=1, ensure_ascii=False), encoding="utf-8")
            journal({"unit_id": unit["unit_id"], "kind": kind, "model": model_id, "effort": effort,
                     "max_thinking": max_thinking, "suffix": suffix or None, "reader": unit.get("reader"),
                     "verdict": reply["verdict"], **totals,
                     "attempts": attempt + 1, "outcome": "result", "escalated": escalated})
            return reply["verdict"]
        cur_prompt = (prompt + "\n\n## Your previous reply failed validation\nError: " + err +
                      "\nPrevious reply:\n" + raw[:3000] + "\nReturn only the corrected JSON object.")
    esc = {"unit_id": unit["unit_id"], "kind": kind, "model": model_id, "attempts": history + attempts,
           "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    esc_path.write_text(json.dumps(esc, indent=1, ensure_ascii=False), encoding="utf-8")
    journal({"unit_id": unit["unit_id"], "kind": kind, "model": model_id, "suffix": suffix or None, "verdict": None,
             **totals, "attempts": len(attempts), "outcome": "escalate", "escalated": escalated})
    return "ESCALATE"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--model", default="haiku",
                    help="haiku | sonnet (aliases in MODELS) or a full model id passed through to the CLI")
    ap.add_argument("--suffix", default="",
                    help="write <addr>.<suffix>.result.json instead of <addr>.result.json (parallel result set "
                         "for a model comparison; pending = units without THAT file)")
    ap.add_argument("--max", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true", help="render prompts to verify/dryrun/<kind>/, call nothing")
    ap.add_argument("--escalated", action="store_true", help="re-run units with an .escalate.json")
    ap.add_argument("--timeout", type=int, default=300, help="seconds per CLI call")
    ap.add_argument("--unit", help="exact selection: comma-separated unit ids or addrs (0x405560 or "
                                   "blind-judge-0x405560), or @file with one per line; unmatched ids are reported")
    ap.add_argument("--parallel", type=int, default=1,
                    help="run N units at a time, each its own CLI call (default 1; the journal is locked)")
    ap.add_argument("--effort", choices=["low", "medium", "high"], default=EFFORT,
                    help="CLI thinking effort (default low; high costs 5-10x in output tokens)")
    ap.add_argument("--max-thinking", type=int, default=MAX_THINKING,
                    help="MAX_THINKING_TOKENS cap for the CLI (default %(default)s; 0 = no thinking, -1 = CLI default)")
    args = ap.parse_args(argv)

    max_thinking = None if args.max_thinking is not None and args.max_thinking < 0 else args.max_thinking
    if not re.fullmatch(r"[A-Za-z0-9_-]*", args.suffix):
        sys.exit("--suffix must be [A-Za-z0-9_-]")
    model_id = MODELS.get(args.model, args.model)
    template = load_template(args.kind)
    schema = load_schema(args.kind)
    if args.parallel < 1:
        sys.exit("--parallel must be >= 1")
    units = pending_units(args.kind, args.escalated, args.suffix)
    if args.unit:
        wanted = parse_unit_selection(args.unit, args.kind)
        by_stem = {u.stem: u for u in units}
        units = [by_stem[s] for s in wanted if s in by_stem]
        missing = [s for s in wanted if s not in by_stem]
        if missing:
            print(f"--unit: {len(missing)} id(s) match no pending {args.kind} unit (no unit file, or a result "
                  f"already exists for this suffix): {' '.join(missing[:20])}{' ...' if len(missing) > 20 else ''}")
    units = units[: args.max]
    if not units:
        print(f"no pending {args.kind} units in {QUEUE / args.kind}")
        return

    if args.dry_run:
        out = DRYRUN / args.kind
        out.mkdir(parents=True, exist_ok=True)
        sizes = []
        for u in units:
            unit = json.loads(u.read_text(encoding="utf-8"))
            prompt = render(template, unit)
            (out / (u.stem + ".prompt.md")).write_text(prompt, encoding="utf-8")
            sizes.append(len(prompt))
            print(f"  {unit['unit_id']}: {len(prompt)} chars, ~{len(prompt) // 4} tokens")
        print(f"dry-run: {len(units)} prompts in {out}; mean {sum(sizes) // len(sizes)} chars, max {max(sizes)}")
        print("would run:", " ".join(_q(c) for c in claude_cmd(model_id, args.effort)), "< prompt.md")
        return

    if shutil.which("claude") is None:
        print("claude CLI not on PATH. Install it, or run each prompt yourself with:")
        print("  " + " ".join(_q(c) for c in claude_cmd(model_id, args.effort)) + " < verify/dryrun/<kind>/<unit>.prompt.md")
        sys.exit(2)

    tally = {}
    t0 = time.time()

    def one(i: int, u: Path) -> str:
        """Runs one unit; returns its verdict, 'ERROR', or raises ClaudeUnavailable. Prints one whole line per
        unit so parallel output stays readable."""
        try:
            v = run_unit(u, args.kind, args.model, template, schema, args.timeout, args.escalated, args.effort,
                         max_thinking, args.suffix)
        except RuntimeError as e:
            print(f"[{i}/{len(units)}] {u.stem} -> ERROR {e}", flush=True)
            journal({"unit_id": u.stem, "kind": args.kind, "model": model_id, "suffix": args.suffix or None,
                     "verdict": None, "outcome": "error", "error": str(e)[:300]})
            return "ERROR"
        print(f"[{i}/{len(units)}] {u.stem} -> {v}", flush=True)
        return v

    try:
        if args.parallel == 1:
            for i, u in enumerate(units, 1):
                v = one(i, u)
                tally[v] = tally.get(v, 0) + 1
        else:
            with ThreadPoolExecutor(max_workers=args.parallel) as pool:
                futures = [pool.submit(one, i, u) for i, u in enumerate(units, 1)]
                for f in as_completed(futures):
                    v = f.result()
                    tally[v] = tally.get(v, 0) + 1
    except ClaudeUnavailable as e:
        print("\n" + str(e))
        sys.exit(2)
    print(f"done: {tally} in {int(time.time() - t0)}s (parallel {args.parallel}); journal {JOURNAL}")


def parse_unit_selection(spec: str, kind: str) -> list[str]:
    """'0x405560,blind-judge-0x407500' or '@list.txt' (one per line, CRLF/blank/# lines tolerated) -> unit file
    stems ('0x405560', ...), exact, in the order given, de-duplicated."""
    tokens: list[str] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("@"):
            text = Path(part[1:]).read_text(encoding="utf-8-sig")
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    tokens.append(line)
        else:
            tokens.append(part)
    out: list[str] = []
    for t in tokens:
        if t.startswith(kind + "-"):
            t = t[len(kind) + 1:]
        if re.fullmatch(r"(0x)?[0-9a-fA-F]{5,8}", t):
            t = blind.addr0x(t)
        if t not in out:
            out.append(t)
    return out


if __name__ == "__main__":
    main()
