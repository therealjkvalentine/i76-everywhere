# Documentation index

Everything learned about the Interstate '76 engine while building the 60 fps patch, on the GOG
2019 Gold build (`i76.exe`, MD5 `60ABF7BC…`, image base `0x400000`, no ASLR).

**Two conventions run through all of it.** Findings carry the evidence that produced them, and
anything later disproved is *retracted in place* rather than deleted — knowing which approaches
failed has repeatedly been worth more than the ones that worked. Notes marked **GOTCHA** are the
ones that produce silently *wrong results* rather than errors.

## Start here

| if you want to… | read |
|---|---|
| run the game above 20 fps, and know what that costs | [framerate/README.md](framerate/README.md) |
| drive the game from a script (launch, menus, input, memory) | [../autotest/README.md](../autotest/README.md) |
| look up an address, structure, or engine constant | [ENGINE-REFERENCE.md](ENGINE-REFERENCE.md) |

## Frame rate

Split out of a single 500-line file; each part answers a different question.

| file | question it answers |
|---|---|
| [framerate/README.md](framerate/README.md) | What is the story? How do I turn 60 fps on, and why did the community say it breaks? |
| [framerate/MEASUREMENTS.md](framerate/MEASUREMENTS.md) | What has actually been measured, with numbers? |
| [framerate/DEAD-ENDS.md](framerate/DEAD-ENDS.md) | What was tried and did not work — read before designing an experiment |
| [PHYSICS-60HZ.md](PHYSICS-60HZ.md) | The full working behind the physics comparisons |
| [RESULTS.md](RESULTS.md) | Short summary of the patch effort |
| [PATCH-DESIGN.md](PATCH-DESIGN.md) | How the interpolating patch was designed |

## The engine

| file | contents |
|---|---|
| [ENGINE-REFERENCE.md](ENGINE-REFERENCE.md) | The address book: structures, globals, constants |
| [ENGINE-LOOP-MAP.md](ENGINE-LOOP-MAP.md) | The frame loop, the render seam, the position table |
| [RE-TECHNIQUES.md](RE-TECHNIQUES.md) | How this was reverse-engineered — watchpoints, scans, disassembly |

## Game data

| file | contents |
|---|---|
| [CAR-CONFIG.md](CAR-CONFIG.md) | `.VCF` vehicle config format |
| [WEAPONS-MEMORY.md](WEAPONS-MEMORY.md) | Weapon and ammo tables in memory |
| [ARMOR-INVESTIGATION.md](ARMOR-INVESTIGATION.md) | Armor — **SOLVED 2026-08-10**: entity `+0x138`, found offline by cross-instance offset diff, confirmed by console write-test |
| [RE-TECHNIQUES.md](RE-TECHNIQUES.md) | **"The rules, distilled"** — 14 investigation principles earned on the armor crack; read before any hunt |
| [CONFIG-OPTIONS.md](CONFIG-OPTIONS.md) | dgVoodoo and game options, and what each actually does |
| [dgVoodoo.conf.reference](dgVoodoo.conf.reference) | Annotated reference config |
| [TESTING-SETPIECES.md](TESTING-SETPIECES.md) | Set pieces worth testing (canyon jump, weapons) |

## Tooling layout

The split is by PURPOSE first: `autotest/` is for **testing the game**, `tools/` is for
**investigating the engine**, `src/` is the deliverable being built.

| directory | contents |
|---|---|
| `autotest/` | mission entry (`enter-*.ps1`) and `lib/` - focus, input, cursor mapping, memory |
| `autotest/setup/` | build a test car: equip weapons, author `.VCF` variants |
| `autotest/calibrate/` | cursor mapping, menu sweeps, locating UI controls |
| `autotest/diagnose/` | sim-running checks, entity identification, captures |
| `tools/instruments/` | subject-agnostic RE: disassembly, xref, memory dump, heap scan, poking |
| `tools/framerate/` | the frame-rate investigation: experiments and their analysers |
| `tools/vehicle/` | weapons, ammo, hardpoints, `.VCF` memory layout |
| `tools/wip/armor/` | armor is **solved** (entity `+0x138`, write-confirmed); dir stays in wip/ until the authoritative-copy detail is recorded and the keeper tools graduate |

**The libraries live in `autotest/lib/` only.** `tools/` once held its own older copies of
`focuslib`/`inputlib`/`maplib`; they were strict subsets (maplib was 1.3 KB against 9.7 KB and
lacked `Click-UI` entirely) and have been deleted. Likewise `tools/enter-melee.ps1`, which still
drove the menus with a retracted cursor calibration — use `autotest/enter-melee.ps1`.
