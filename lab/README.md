# i76-uncap-lab — 60 Hz for Interstate '76

> **Snapshot, not the working copy.** This folder is a public-safe snapshot of `i76-uncap-lab@ebb3907`, taken
> 2026-10-03 (including two uncommitted edits to `autotest/saves/popup-repro.ps1` and `reminder-repro.ps1` as they
> stood that evening). No history was imported. The working copy, with its private data (the sandbox game clone
> `game/`, reference checkouts `refs/`, captures), lives outside this repo at its old path, `..\i76-uncap-lab`, and
> that is where the harness paths point. Three docs are held back until scrubbed (MOUSE-ESC-MENU-AND-SAVE-SCREEN,
> WIDESCREEN-2D, WIDESCREEN-FEASIBILITY, all under `docs/`); links to them read "held back: <path>".
>
> **Refresh:** from the repo root run `python tools\export_public.py export` (it must print `RESULT: PASS`), then copy
> the staged `lab\` tree over this folder. The allowlist is [`tools/export_public.toml`](../tools/export_public.toml).
>
> **Caveat:** the scripts still contain `C:\Users\james\...` paths and are Windows- and lab-specific; they will not run
> from here as-is. The next step is the path-convention migration (`I76_LAB_ROOT`, `I76_GAME_DIR`, `I76_MAP_ROOT`,
> resolved by [`autotest\lib\gamedir.ps1`](autotest/lib/gamedir.ps1)).

Isolated workspace for making I'76 render at **60 FPS with the physics untouched**.
Kept separate from the playable install and the `i76-everywhere` repo on purpose: nothing
here touches the game you actually play. The sandbox game clone (`game/`) and the reference
checkouts (`refs/`) are git-ignored — this repo carries only findings, tools, and (later) the
patch.

## Start here

| doc | what it is |
|---|---|
| **[docs/ENGINE-REFERENCE.md](docs/ENGINE-REFERENCE.md)** | **The engine reference.** Memory map with confidence levels, frame loop, physics findings, FFB/telemetry capture, handling model, and the traps that produce wrong data. Written for RE, the Time Vigilantes successor, trainers/mods, and motion-sim capture. |
| [autotest/README.md](autotest/README.md) | Cookbook for driving the game from a script: launch, menus, input, memory reads, regression tests. |
| **[docs/README.md](docs/README.md)** | **Documentation index** — every document, with the question each one answers. |
| **[docs/framerate/](docs/framerate/README.md)** | **Frame rate: how to run above 20 fps, what is proven safe, the known frame-coupled bugs, and how the community lore reconciles.** Split into the [story](docs/framerate/README.md), the [measurements](docs/framerate/MEASUREMENTS.md), and the [dead ends](docs/framerate/DEAD-ENDS.md). |
| [docs/PHYSICS-60HZ.md](docs/PHYSICS-60HZ.md) | The 20 Hz vs 60 Hz measurements and how the "residual" turned out to be terrain. |
| [docs/ENGINE-LOOP-MAP.md](docs/ENGINE-LOOP-MAP.md) | Static disassembly of the gameplay loop and the render/present seam. |
| [docs/TESTING-SETPIECES.md](docs/TESTING-SETPIECES.md) | Set pieces and weapons: what works, what failed (save-state), what still needs a human. |
| [docs/RESULTS.md](docs/RESULTS.md) | The interpolated-60 fps DLL result. |

## The approach in one line

Leave the simulation at its native ~20 Hz; **add 2 extrapolated render frames after each real
one** at the present hook (the D2DX / Diablo II model). Sim speed, physics, AI, scripted
stunts and audio timing are all byte-identical to unpatched — only the picture gets smoother.
Full rationale and the routes rejected: `../i76-everywhere/docs/records/FRAMERATE-UNCAP-RESEARCH.md`.

## Where things stand

**Done (static, this session):**
- Sandbox game clone at `game/` (Gold `i76.exe`, MD5 `60ABF7BC…`). Playable install untouched.
- Exe lineage pinned; the i76fix frame-loop hook `0x4039B8` **transfers to our Gold exe**.
- The Roanish `world_tick` contradiction settled: his fixed-step+interpolation is his
  **rewrite's** design, not the original — the original is sim==render, one step per frame,
  exactly the condition this plan assumes.
- **The gameplay loop mapped** end to end: frame counter, GetTickCount pacing, dt, the sim
  cluster, and the **render/present seam** (`render_scene 0x4621E0` bracketed by
  `[0x5DD2BC]`/`[0x5DD2C0]`). See `docs/ENGINE-LOOP-MAP.md`.
- Present hook + extra-frame design written: `docs/PATCH-DESIGN.md`.
- Read-only instrumentation built: `tools/framerate/probe-loop.ps1`.

**Blocked on one live measurement (needs the game running at the physical console):**
- The entity **world-position / orientation offset**. It's the only missing input for entity
  extrapolation, and it can't be read from a static binary — the renderer reaches it several
  matrix-builder calls deep. `tools/framerate/probe-loop.ps1 -FindPos` pins it in ~30 seconds of driving.

**Next, once that offset is known:**
- Milestone 2–3 (present-hook passthrough, then camera-only 3× — a real MVP that needs no new
  offsets) → milestone 4 (full entity extrapolation) → milestone 5 (discontinuity guards).
  Milestones and delivery vehicle are in `docs/PATCH-DESIGN.md`.

## The one thing I need from you (5 minutes at the console)

At the **physical monitor** (not RDP — the game's 3D won't init over RDP and every reading
would be invalid), launch the game, start any mission, then from this folder run:

```bash
powershell -ExecutionPolicy Bypass -File tools\framerate\probe-loop.ps1 -Fps
```

then, while **driving in a straight line at a steady speed**:

```bash
powershell -ExecutionPolicy Bypass -File tools\framerate\probe-loop.ps1 -FindPos
```

Paste me the output of both. `-Fps` confirms the frame counter and the current cap; `-FindPos`
prints the winning position offset. With that offset in hand the camera-only MVP and then full
60 Hz are unblocked.

## Layout

```
game/                 sandbox clone of the install (git-ignored, never edited by the lab)
refs/                 read-only reference checkouts (git-ignored):
  i76fix/             immi101 — the proven frame-loop hook (patch.s, delay.c)
  d2dx/               bolrog — the extrapolation model we're following
  roanish-i76/        the engine rewrite + REVERSING.md
captures/             run output: traces, dumps, screenshots (git-ignored)

docs/                 see docs/README.md for the index
  framerate/          the frame-rate work, split three ways:
    README.md           the story, how to enable it, why the lore says otherwise
    MEASUREMENTS.md     every measured result
    DEAD-ENDS.md        what was tried and failed — read before designing a test
  ENGINE-REFERENCE.md the address book
  ENGINE-LOOP-MAP.md  the static map of the gameplay loop (addresses + seam)

autotest/             AUTOMATED TESTING — everything for driving the game from a script
  enter-*.ps1         mission entry: melee, training, trip 1, mission 5
  lib/                focuslib, inputlib, maplib, memlib, simlib
                      ** the ONLY copies — tools/ must not carry its own **
  setup/              build a test car: equip weapons, author .VCF variants
  calibrate/          cursor mapping, menu sweeps, UI-control location
  diagnose/           is the sim running, who is which entity, captures

tools/                ENGINE INVESTIGATION — learning how the game works
  instruments/        subject-agnostic: disassembly, xref, memory dump, scan, poke
  framerate/          the frame-rate question: experiments + analysers
  vehicle/            weapons, ammo, hardpoints, .VCF memory layout
  wip/                investigations still open — filed apart from working tools
    armor/            SOLVED (entity +0x138, write-confirmed 2026-08-10); graduating soon

src/                  THE DELIVERABLE — present hook, watchpoint tool, injector
```

Scripts under `autotest/<sub>/` reach the libs via `..\lib\`; scripts under `tools/<cat>/` via
`..\..\autotest\lib\`; `tools/wip/armor/` via `..\..\..\autotest\lib\`. A script moved between
these directories needs that path adjusted.
