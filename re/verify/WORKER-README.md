# verify/ - model-facing half (sections 2.6, 2.7, 4.1, 4.2, 4.5 of status/VERIFICATION-PROGRAM.md)

The runner half (`run_scenario.py`, `census.py`, `coverage.py`, `README.md`) is documented separately. This file
covers the unit builder, the blind kit, the worker loop, the prompts and the schemas.

## Commands

```
# 4.1 one unit per `proposed` function whose contract/spec text makes a cadence claim (pre-filter, default on):
#     contract + spec paragraphs + callers (with known cadence) + subsystem; skipped rows -> queue/cadence-claim/SKIPPED.txt
python verify/make_units.py cadence-claim --prefix physics,entity --limit 20
python verify/make_units.py cadence-claim --dry-run                      # counts + SKIPPED.txt / PASSED.dryrun.txt only
python verify/make_units.py cadence-claim --no-only-with-cadence-text     # every proposed function (the old behaviour)

# 4.5 blind re-derivation inputs (stripped decompilation); random sample over the selected rows
python verify/make_units.py blind-name --sample 10 --seed 1 [--prefix physics]

# 4.5 judge units: pairs each blind-name result with the map's name+contract, random A/B per unit
python verify/make_units.py blind-judge --seed 1

# 4.2 pairs cadence-claim results with a census run (dir, census.classified.json, or scenario id = latest run)
python verify/make_units.py census-grade verify/fixtures/census.classified.sample.json
python verify/make_units.py census-grade drive fire-each

# the worker: pop units without results, call the CLI, validate, write results, journal
python verify/worker.py --kind cadence-claim --model haiku --max 200
python verify/worker.py --kind blind-name --model haiku --max 50 --dry-run      # render only -> verify/dryrun/
python verify/worker.py --kind cadence-claim --model sonnet --escalated         # re-run .escalate.json units
python verify/worker.py --kind cadence-claim --model sonnet --suffix sonnet     # parallel set: <addr>.sonnet.result.json
python verify/worker.py --kind blind-judge --parallel 4 --unit 0x405560,0x407500,blind-judge-0x40d8f0   # exact units, 4 at a time
python verify/worker.py --kind blind-judge --parallel 4 --unit @different.txt   # ids from a file, one per line (CRLF ok)

# the blind kit by hand
python verify/blind.py 0x438fd0          # stripped C
python verify/blind.py 0x438fd0 --json   # the full blind-name inputs
```

Worker flags: `--kind K` (template + schema + queue dir name), `--model haiku|sonnet`
(`claude-haiku-4-5-20251001` / `claude-sonnet-5`; any other value is passed to the CLI as a model id), `--max N`,
`--dry-run`, `--escalated`, `--timeout <s>` (per CLI call, default 300),
`--effort low|medium|high` (default low), `--max-thinking N` (MAX_THINKING_TOKENS for the CLI; default 1024,
0 = none, -1 = CLI default), `--suffix S` (write `<addr>.S.result.json` / `<addr>.S.escalate.json` and treat a unit
as pending when *that* file is missing; the canonical `<addr>.result.json` is the only one `make_units` and the
gate read, so a comparison set never reaches a downstream unit; journal lines carry `"suffix": "S"`).

`--unit` is an exact selection: a comma-separated list of addresses or unit ids (`0x405560`, `blind-judge-0x405560`;
`405560` is normalised too), or `@file` with one per line (CRLF, blank and `#` lines tolerated). Ids that match no
*pending* unit (no unit file, or a result already exists for the chosen suffix) are printed, so a stale list is a
visible message, not a silent no-op pass. The old substring/prefix match is gone: partition parallel runs with
`--parallel` or with explicit lists instead.

`--parallel N` runs N units at a time from one process (a thread pool; each unit is still its own `claude -p`
call, rate-limit sleeps happen inside the thread). Output is one whole line per unit as it finishes, so the order
is completion order. Several processes may also run at once: `journal.jsonl` is appended under
`journal.jsonl.lock` (msvcrt.locking on Windows, fcntl.flock elsewhere; open-write-fsync-close inside the lock),
tested with 6 processes x 250 lines and 8 threads x 100 lines without loss. Results are per-unit files so two
workers given the same unit would merely both write it; the pending check is not atomic, so do not hand two
workers overlapping selections (`--unit` lists or `--parallel` within one process keep them disjoint).

Measured on the first 20 physics cadence-claim units (2026-10-01, Haiku): effort high / uncapped thinking
1.9k in, 4.1k out, 42 s, $0.022 per unit; effort low / uncapped 2.0k in, 3.7k out, 36 s, $0.021; effort low /
cap 1024 2.0k in, 0.6-1.0k out, 7-14 s, $0.005-0.008; no thinking 2.5k in, 123 out, 4 s, $0.003 but it
over-claimed (per_event for a per-substep check) on the one unit tried. The 1024 cap kept the verdicts of the
uncapped run where they were right and fixed two wrong ones once the template gained the rules below.

Real run 2026-10-02 (journal `ts >= 2026-10-02T03`, effort low, cap 1024, CLI usage fields; Sonnet counts the same
prompt as ~1.25x more input tokens): 70 CLI calls, 70/70 valid on the first attempt, $0.70 total.

| kind | model | n | in / out tokens | s | $/unit | verdicts |
|---|---|---|---|---|---|---|
| cadence-claim | haiku (`--suffix haiku-r2`) | 20 | 2.1k / 0.7k | 9.8 | 0.0057 | 7 PASS, 13 INCONCLUSIVE |
| cadence-claim | sonnet (`--suffix sonnet`) | 20 | 2.7k / 0.15k | 5.6 | 0.0123 | 10 PASS, 10 INCONCLUSIVE |
| blind-name | haiku | 8 (+2 earlier) | 3.0k / 1.0k | 13.8 | 0.0088 | 6 PASS, 4 INCONCLUSIVE of 10 |
| blind-name | sonnet (`--suffix sonnet`) | 10 | 3.8k / 0.2k | 6.4 | 0.0173 | 3 PASS, 7 INCONCLUSIVE |
| blind-judge | haiku | 6 | 1.6k / 0.7k | 9.8 | 0.0051 | 2 compatible, 4 different |
| blind-judge | sonnet (`--suffix sonnet`) | 6 | 2.1k / 0.16k | 5.0 | 0.0100 | 1 same, 3 compatible, 2 different |

Cadence enums: Haiku-r2 vs Sonnet agree on 17/20; the 3 differences are all Haiku `unknown` where Sonnet gave an
enum (0x434670 per_event(impact), 0x436570 irregular, 0x436ff0 per_event(impact); the last is a per-substep
velocity *check* whose destroy is the event, the over-claim pattern noted above). Haiku vs its own earlier
canonical set agrees on 17/20 too; the 3 differences are canonical results from the pre-rules template. Blind:
Haiku's readings were right on 2/6 judged (D3D mode pick, simclock offset), wrong with *high* confidence on
object_ScriptDestroy ("object_LoadInstance") and inverted the comparator direction on weapon_CompareIntDesc;
Sonnet read both of those correctly and answered INCONCLUSIVE on 7/10. The two judges disagreed on 2/6:
Sonnet right on ai_AvlFind vs "entity_FindMatching" (compatible per the structure rule), Haiku right on the
comparator (the blind contract really does describe the opposite order). Working choice: Haiku for
cadence-claim and census-grade, Sonnet for blind-name, Haiku for blind-judge with every `different` re-judged
by Sonnet (`--suffix sonnet`) before it counts.

The CLI call is `claude -p --model <id> --output-format json --tools "" --no-session-persistence
--strict-mcp-config --effort <e> --system-prompt "<one line>"`, prompt on stdin. `--tools ""` removes every tool
(rule 0.1: the model never searches or edits), `--system-prompt` replaces the 6k-token Claude Code system prompt
(the prompt then costs ~1.5-2.5k input tokens). If `claude` is not on PATH, the worker prints the exact command
and exits 2; `--dry-run` writes the rendered prompts so they can be fed by hand. "Authentication required" also
exits 2 (`claude login` once, interactively). Rate limits / overloads: sleep 30, 60, 120 s, then the unit is
journaled as `error` and the loop continues.

## File layout

```
verify/
  make_units.py                 unit builders (one subcommand per kind)
  blind.py                      strip decompilation, vocabulary redaction, leak check; shared TSV loaders
  worker.py                     the loop: render -> claude -p -> validate -> result/escalate -> journal
  prompts/<kind>.md             fixed template, {{field}} / {{inputs.field}} placeholders
  schemas/<kind>.schema.json    draft-07, additionalProperties false, verdict + payload enums
  queue/<kind>/<addr>.json      unit  {"unit_id","kind","addr","name","inputs":{...}} (+ "hidden" for blind-judge)
  queue/<kind>/<addr>.result.json    validated reply + "meta" (model, effort, tokens, cost, ms, attempts)
  queue/<kind>/<addr>.escalate.json  two failed attempts (raw replies + validation errors); Sonnet input
  queue/cadence-claim/SKIPPED.txt    functions the cadence pre-filter left out (addr, name, reason)
  journal.jsonl                 one line per unit: unit_id, kind, model, verdict, input_tokens, output_tokens,
                                cost_usd, ms, attempts, outcome (result|escalate|error)
  journal.jsonl.lock            empty lock file for journal appends (safe to delete when no worker runs)
  dryrun/<kind>/<addr>.prompt.md     --dry-run output
  fixtures/census.classified.sample.json   synthetic 2.2 census for census-grade until a real run exists
```

Unit ids are `<kind>-<addr>` (`cadence-claim-0x438fd0`). Results are files beside the unit, so any run can be
killed and restarted (rule 0.4); `make_units` never rewrites a unit that has a result, and rewrites a unit file
only with `--force`.

Token numbers in `journal.jsonl` and `meta` come from the CLI envelope (`usage`, `total_cost_usd`):
`input_tokens` = uncached + cache_creation + cache_read, with the three parts kept separately; `output_tokens`
includes thinking tokens.

### What each unit carries

- **cadence-claim** inputs: `contract` (the first evidence claim that starts with "contract", else the first
  claim), `spec_paragraphs` (blank-line paragraphs of `subsystems/*.md` mentioning the name or its address,
  <= 1,500 chars, `spec_truncated` says if cut), `callers` (`[{name, cadence|null}]`, cadence read from an existing
  cadence-claim result), `subsystem`, `size_bytes`. Worker-side checks: `callers_expected` must be names in
  functions.tsv; `cadence: unknown` iff verdict INCONCLUSIVE; `event` is a string iff `cadence == per_event`.
  **Pre-filter** (`--only-with-cadence-text`, default on; section 10's decision): a unit is built only when the
  contract plus the spec paragraphs contain cadence vocabulary, whole-word, case-insensitive, hyphen or space
  between words (`make_units.CADENCE_VOCAB`, the one place the list lives: per/each/every frame, tick, substep,
  step, second, Hz, `every <n>`; once per/at/on/when, each/every/per call, per shot/hit/event/object/pair/mission;
  on/at load, init, startup, exit, shutdown, teardown, mission start/end, WinMain; when fired, on hit/impact/
  collision/damage/spawn/destroy/key; never, dead code, unreachable, debug only, network only; callback, timer,
  scheduled, polled, idle). The rest are listed in `queue/cadence-claim/SKIPPED.txt` as
  `addr<TAB>name<TAB>no cadence text: the census is the record`; their cadence is whatever the census measures,
  with no claim to grade. `--dry-run` writes SKIPPED.txt and `PASSED.dryrun.txt` (addr, name, the vocabulary
  that matched) and no unit files. Measured 2026-10-02 over the 1,882 `proposed` rows: **379 pass**, 1,444 skipped,
  59 have no contract claim at all. Top hits: per frame 131, callback 61, each frame 52, once per 49, never 47,
  every frame 37, per second 31, per call 28, timer 26, from WinMain 24. The list is deliberately permissive (a
  false positive costs one $0.006 unit that answers `unknown`; a false negative loses a claim), so `never`,
  `idle` and `callback` are in even though some of their hits are not cadence statements.
- **census-grade** inputs: the claim payload and its reason, one census view per scenario (classification,
  frames, calls, histogram, first/last frame, the classifier's statistics and note, callers as names), telemetry
  event counts per scenario (events.csv `type` codes 1/2/3 = shot/explosion/impact). `make_units` grades
  `claim == classification in every scenario` itself and writes the result (`meta.graded_by: script`); only
  mismatches and `irregular` go to the model (4.2). Units whose claim is `unknown` are skipped. The loader reads
  `census.py classify`'s census.classified.json (rows with `class`, callers `{ra: {n, name}}`, enriched with the
  histogram from census.jsonl), the section 2.2 object form, or a bare list; `fixtures/census.classified.sample.json`
  is a synthetic 2.2 file for testing. A fixture run writes into the live queue like any other: delete
  `queue/census-grade/` afterwards (or rebuild with `--force`) so synthetic grades never reach the gate.
- **blind-name** inputs: `stripped_c`, `strings` (resolved from `ghidra/export/strings_xrefs.csv`),
  `caller_count`, `callee_count`, `callers_stripped` (<= 3 callers, 40 lines each), `vocabulary` (the prefix table
  with every address and example name redacted). `name` is null in the unit. Stripping replaces every
  functions.tsv / globals.tsv name whose status is not `anchored`/`library` with `FUN_`/`DAT_<8hex>`; names the
  binary itself carries (import thunks, FID matches) stay. `blind.leaks()` re-scans the finished inputs and the
  unit is not written if any map name survives.
- **blind-judge** inputs: `A` and `B` = `{name, contract}`; `hidden` = which side is the map, the blind
  confidence and the seed. The renderer refuses `{{hidden...}}`, so no template can show it. Prompt rule
  (2026-10-02, after BLIND-SAMPLE-2.md): `different` requires a contradiction in *what the code does* (operation,
  offsets/constants, callees, argument or return rule, an asserted-versus-excluded side effect); two contracts
  that describe the same operations with different stated purposes or subsystems are `compatible`; a byte offset
  and the dword index of the same field are the same offset. The template carries one worked example of each
  (fictional functions, so no measured unit is mirrored). The schema is unchanged. Measured effect: see
  "Judge rule measurement" below.

### Judge rule measurement (2026-10-02, the 44 sample-2 `different` units, `--suffix v2|v3|v2-sonnet|v3-sonnet`)

The 44 are the seed-2 units whose Sonnet re-judge said `different` (BLIND-SAMPLE-2.md section 2; the two seed-1
units 0x460c80 / 0x46aa80 are not in it). Per-case labels in that section: **10 COMPAT** (judge over-calls:
0x407680 0x41ee40 0x41ef40 0x422230 0x42b020 0x445750 0x44b2d0 0x44c390 0x48f9b0 0x4b1a20), **31 MAP** (blind
purpose guess over right mechanics), 2 MAP-FIX (0x4907e0, 0x45d100), 1 GAP (0x448890). The summary line in that
report says 17 COMPAT / 24 MAP; the body labels do not support those two numbers, so the counts here use the labels.
`v2` = the rule plus examples that mirrored two real units (0x422230, 0x41ee40); `v3` = the same rule with
fictional examples (the shipped template). Each run: 44 CLI calls, 44 results, 44 journal lines; v3 Haiku and v3
Sonnet ran as two concurrent processes with `--parallel 4` each and lost no line.

| judge | prompt | COMPAT 10 -> compatible | MAP 31 -> compatible | MAP-FIX / GAP flipped | $/unit | $ total |
|---|---|---|---|---|---|---|
| Haiku | v1 (sample) | 0 | 0 | 0 | 0.0059 | |
| Haiku | v2 | 1 (0x48f9b0) | 1 (0x425e00) | 0x4907e0, 0x448890 | 0.0064 | 0.28 |
| Haiku | v3 | 1 (0x422230) | 1 (0x425e00) | none | 0.0068 | 0.30 |
| Sonnet | v1 (sample) | 0 | 0 | 0 | 0.0104 | |
| Sonnet | v2 | 4 (0x422230 0x44b2d0 0x44c390 0x48f9b0) | 7 | none | 0.0145 | 0.64 |
| Sonnet | v3 | 2 (0x44c390 0x48f9b0) | 9 (0x405560 0x407500 0x425e00 0x4466c0 0x44c8a0 0x462cc0 0x471980 0x48fac0 0x4abe60) | 0x45d100 | 0.0149 | 0.66 |

Reading: the rule barely moves Haiku (1 of 10 over-calls recovered, and a different one each run: Haiku's
`different` is noise at this level, it even called +0x54 versus dword [0x15] "different offsets" under v2). Sonnet
recovers 2-4 of the 10 over-calls but also turns 7-9 of the 31 purpose-guess cases into `compatible`, which is
correct by the rule's own letter (same mechanics, wrong purpose) and is what section 2 of the sample report says
those cases are; so under this rule `different` means "the mechanics clash", and the purpose-guess cases stop
counting as disagreement, which is the intent of section 10/11. The MAP-FIX flip (0x45d100) is the offset-detail
case, a reminder that `compatible` does not certify offsets. Rule kept regardless: **every Haiku `different` is
re-judged by Sonnet (`--suffix sonnet`) before it counts**; Haiku alone over-calls at any prompt tried.

## Adding a unit kind

1. Pick the kind name `K` (lower-case, hyphens). It is the queue dir, the template, the schema and the `--kind`.
2. `prompts/K.md`: one-paragraph role; the rules (JSON only; INCONCLUSIVE when the inputs do not settle it; never
   cite evidence not in the inputs; any kind-specific rule from section 4); the inputs as `{{inputs.x}}`; the
   output shape inline with `"unit_id": "{{unit_id}}"`; two short worked examples with fictional addresses.
   Keep it under 600 words: lists and dicts render as indented JSON, strings verbatim, missing fields as `(none)`.
3. `schemas/K.schema.json`: draft-07, top level `{unit_id, verdict, payload, reason}` + optional `meta`,
   `additionalProperties: false` everywhere, enums for every categorical field, `unit_id` pattern `^K-0x...$`.
4. `make_units.py`: a `make_K(args)` that builds `inputs` from repository files and calls
   `write_unit("K", addr, name, inputs, args.force)`; register the subparser in `main()`.
5. Cross-field rules the schema cannot express go in `worker.kind_checks()` (they are validation errors, so the
   model gets one retry with the message).
6. Dry-run ten units, read the rendered prompts, then run ten for real and read every result before scaling.
