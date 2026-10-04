# re/ — Interstate '76 reverse-engineering map (public snapshot)

> **Snapshot, not the working copy.** This folder is a public-safe snapshot of `i76-map@ee48d0f4`, taken 2026-10-03.
> No history was imported. The working copy, with its private data (Ghidra decompiler exports, evidence and
> verification runs, captures, the pristine game sandbox, extracted game data), lives outside this repo at its old
> path, `..\i76-map`, and that is where the harness paths point. 68 files are held back until scrubbed of decompiler
> names and tokens (among them the original `README.md`, `symbols/functions.tsv`, `shell/SCREENS.md`, `SAVE.md`,
> `FIXES.md`); links to them read "held back: <path>".
>
> **Refresh:** from the repo root run `python tools\export_public.py export` (it must print `RESULT: PASS`), then copy
> the staged `re\` tree over this folder (keep this README). The allowlist is
> [`tools/export_public.toml`](../tools/export_public.toml).
>
> **Caveat:** the scripts still contain `C:\Users\james\...` paths and are Windows- and lab-specific; they will not run
> from here as-is. The next step is the path-convention migration (`I76_LAB_ROOT`, `I76_GAME_DIR`, `I76_MAP_ROOT`,
> resolved by the lab's [`autotest\lib\gamedir.ps1`](../lab/autotest/lib/gamedir.ps1)).

## What is here

| path | what it answers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | the engine as a labelled binary: module map, frame sequence, object model, physics, damage, weapons, AI, renderer |
| [REIMPLEMENTATION.md](REIMPLEMENTATION.md) | what a source port needs, subsystem by subsystem |
| [OPEN76-GAPS.md](OPEN76-GAPS.md) | where the Open76 reimplementation diverges from the exe |
| [subsystems/](subsystems/) | per-subsystem specs (physics is held back) |
| [functions/](functions/) | per-function notes, keyed by address |
| [data/](data/README.md) | byte-exact file-format specs and parsers (`data/FORMATS.md` first), FSM notes, the mod CLI, round-trip tests |
| [shell/](shell/README.md) | i76shell.dll: screens, callbacks, input-map corruption |
| [symbols/](symbols/), [types/](types/) | the public parts of the symbol and type tables |
| [tools/](tools/), [ghidra/scripts/](ghidra/scripts/), [verify/](verify/README.md) | the tooling that produced and checks the map |
