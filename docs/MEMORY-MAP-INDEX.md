# Interstate '76 memory map — consolidated index (current truth)

*Read this FIRST. This is the reconciled result of the 2026-07-18 multi-thread
reverse-engineering push (static disassembly + live process reads, several
parallel sessions). The raw session logs live in
[GHIDRA-MEMORY-MAP.md](GHIDRA-MEMORY-MAP.md) (PARTs 1–13b) and
[STATIC-RE-FABLE.md](STATIC-RE-FABLE.md) (§1–12) — they contain intermediate
claims that were later corrected; where this file and a PART/§ disagree, THIS
file wins. Machine-readable map: `tools/i76-addresses.json`.*

*All addresses are GOG Gold `i76.exe`, loaded at 0x400000 (1997 PE, no ASLR
under Wine, so static VAs are live process addresses). Nitro-Pack deltas in
addresses.json. Verification labels: **✓ live** = read/written against the
running game and matched the HUD/behavior; **disasm** = read from the
disassembly, not yet exercised live; **candidate** = plausible, unconfirmed.*

## The engine in one paragraph (why some things were hard)

I'76 is a **modified MechWarrior 2 engine**. Four architectural facts shaped
this whole effort: (1) it runs a **mission SCRIPT VM** — many "functions"
(`ammoLesser`, `isCBEmpty`, `playScene`, `setUserRadar`) are bytecode opcode
names matched in strcmp tables, so string-anchored disassembly often lands in a
dispatch table, not real code. (2) It keeps a **2029-bucket hash of
heap-allocated entity structs** (Roanish) — gameplay objects RELOCATE per
mission/load, which is why every flat value-scan and cross-dump diff for
ammo/armor failed; only pointer chains from static roots survive. (3) It splits
a vehicle into a **transform-entity** (position/rotation/controls) and separate
**logic/inventory sub-objects** (weapons/components) reached by accessors —
different objects, different roots. (4) The sim runs a **fixed ~20 fps tick**;
combat ints mutate on tick boundaries, so correlate actions to deltas by ticks.

## Tier 1 — STATIC globals (permanent, no pointer chain)

| VA | type | meaning | status |
|---|---|---|---|
| 0x536770 / 78 / 80 | int | pilot yaw / pitch / roll look input | ✓ live |
| 0x5367cc / d4 / db | int | throttle / steer / weapon_fire input | ✓ live (fire is read-only in practice — see dead end #9) |
| 0x536770..0x536818 | block | EVERY action's live value (action table col 2) | ✓ live |
| 0x4c2964 / 6c / 70 / 74 | float | live camera Euler angles | ✓ live (F7 sweep turns the view) |
| 0x4c2728 | int | camera view mode (F1..F11) | ✓ live |
| 0x54a264 | ptr | **world-context root** (accessor 0x457530 returns it) | ✓ live |
| 0x51f5d0 | int[8] | entity-table group counts | ✓ live |
| 0x507da0 | ptr[8][64] | entity-table group arrays (stride 0x100) | ✓ live |
| 0x524674 | int | **music-active flag** (nonzero = playing) | disasm |
| 0x4ed890 / 894 | handle | MCI device / aux-volume device | disasm |
| 0x52bbd0 | int | FFB present flag (1 only if i7_SFRCE.DLL init succeeded at boot) | ✓ live (0 on Mac without the shim) |
| 0x52bbcc | handle | private Win32 heap for FFB impact-event nodes (HeapCreate(0,0,0) — the old "FFB object ptr" label was wrong) | disasm |
| 0x52bbdc / e0 / e4 | ptr | I7FF_InitSystem / ExitSystem / SIM_Effect fn ptrs from the DLL | disasm |
| 0x4f2328 | 364 B | FFB force-state block, filled EVERY sim tick by ffb_tick 0x445ba0 whenever the flag is 1 — full field map in [FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md) | disasm (deep-dived 2026-07-19) |
| 0x541070 | table | DirectPlay MP player table (16×0x48, veh ptr @+0x28) | ✓ live-zero in SP — MP only |

## Tier 2 — the PLAYER entity chain (permanent root)

```
entity = [ [ [0x54a264] ] + 0x70 ]     ; ✓ live-verified repeatedly,
                                       ;   including across a mission reload
                                       ;   (entity relocated, chain re-resolved)
```

Known entity fields (base relocates; offsets are stable):

| offset | content | status |
|---|---|---|
| +0x04..0x30 | world transform, 3×4 float matrix (rotation confirmed) | ✓ live |
| +0x94 | float ~51.5 — best SPEED candidate | candidate |
| +0xe0 / +0xe4 | steer / throttle applied (float) | ✓ disasm+live |
| +0x108 | ptr → vehicle-LOGIC object (ammoLesser accessor 0x466e20; AI-aggression path) | ✓ live-walked |
| +0x10c | ptr → logic/sub-object used for the component-record dissection | ✓ live-walked |
| +0x1a0..0x1d4 | 14-entry int part-slot list, −1 terminated | med |

**Open reconciliation:** +0x108 and +0x10c were each called "the vehicle-logic
object" by different threads. +0x108 is the one the engine's own accessors use
(weapon count 4 read at logic+0xa718; aggression written at logic+0xa818);
+0x10c is where the 16 × 0x90-stride component records were dissected and what
`i76-chaindiff.ahk` walks. They may be two views of one graph or two adjacent
sub-objects — nobody has diffed the two pointers' targets yet.

## Tier 3 — ammo & part condition: **SOLVED** (the inventory table)

The single most useful result of the whole effort. Live-verified twice,
including across a relocation (mission reload):

```
entity   = [ [ [0x54a264] ] + 0x70 ]
table    = entity - 0x14C8          ; 17 records × 0x38 bytes
record w = table + w*0x38
  +0x00  int 7           ; header tag  — VALIDATE before trusting the table
  +0x04  ptr 0x00750000  ; shared class ptr — second half of the signature
  +0x08  int CURRENT     ; live ammo (weapons) / condition (parts)  ← write target
  +0x0c  int MAX         ; capacity / full condition
```

- The 17 records = every weapon's ammo AND every part's durability/condition
  (matches the save editor's per-part dur/cond columns).
- Robust resolve: compute `entity-0x14C8`, check the (7, 0x00750000) signature;
  on miss, sweep `entity-0x1500..entity-0x1000` for it. Implemented and
  field-tested in `tools/i76-rearm.ahk` (F5 view, F6 cur=max repair+rearm).
- Secondary confirmation: HUD ammo-gauge structs (stride 0xC0, session-heap)
  each hold a pointer to a record's +0x08.
- Encoding facts (per Open76 + save editor + MW2 ancestry, confirmed live):
  ammo is a plain int32 countdown; part/armor values are integer TENTHS
  (91.0 shown = 910 stored). No floats, no fixed-point, in any combat scalar.

## Tier 3b — armor/chassis: candidates, not locked

The DEFENSE-panel facets are NOT in the inventory table and NOT at flat entity
offsets. Live int-scans (tenths) found two large contiguous grids:

| where | seen | reading |
|---|---|---|
| entity + 0x135c | runs of 400 with damaged 376/352 (= 40.0/37.6/35.2) | **chassis grid** candidate |
| entity − 0x800 | runs of 575/800/1000 (= 57.5/80.0/100.0) | **armor grid** candidate |

These are big per-panel damage GRIDS — the 4-facet DEFENSE numbers are likely a
rollup. **To lock:** note the on-screen DEFENSE values (garage), take one hit,
re-read the grids; "full armor" trainer write = grid to max. Also unpinned: the
component-record field meanings inside the 16 × 0x90 records off entity+0x10c
(+0x40 int dur 100, +0xac float 100.0, +0xc4 = 50 observed).

## Tier 4 — the WORLD entity table (all vehicles)

✓ live-verified (14 entities, 3 active groups); tool: `tools/i76-worldscan.ahk`.

```
for g in 0..7:                                  # faction/team groups
  n = read_u32(0x51f5d0 + g*4)
  for s in 0..n-1:
    wrapper = read_u32(0x507da0 + g*0x100 + s*4)
    logic   = [[wrapper] + 0x70] + 0x108 deref  # wrapper -> [.] -> +0x70 -> +0x108
    aggression = read_u32(logic + 0xa818)       # int 0..4, writable
```

Basis for radar/minimap, targeting, threat display, and mission-clear detection
(`allEnemyDead` watches group counts → 0). The table entries are WRAPPERS, not
the transform-entities. **OPEN:** the world-position float offset (transform
translation columns read origin-small constants across all cars) and the speed
offset — need drive-correlation ("which 3 floats move together").

## Applying it — feature by feature

- **Trainer / accessibility** — SHIPPED: `tools/i76-rearm.ahk` (repair+rearm
  via the Tier 3 chain, field-tested). Next: full-armor once a 3b grid locks.
- **Head tracking / analog look** — a MEMORY-WRITE feature: write the int
  inputs 0x536770/78 or the camera floats 0x4c2964/70. The input.map route is
  dead (dead end #8). Production plan: opentrack/webcam → UDP → writer at
  frame rate; the trainer's F7 sweep is the proof-of-life.
- **Rumble that reads the game** — SOLVED at the architecture level
  (2026-07-19, [FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md)): the FFB plugin DLL
  `i7_SFRCE.DLL` receives a fully-mapped 364-byte force-state block every sim
  tick (engine/speed/terrain/skid/weapon-fire/steering-kick/impact events
  with direction+damage). `../ffb-shim/` is a drop-in replacement that
  activates FFB with NO DirectInput device (works on Mac/Wine), drives XInput
  rumble from the stream, and logs telemetry for tuning. Builds clean; NOT
  yet field-run. Fallback signals (if ever needed): speed candidate
  entity+0x94, camera-float jumps, inventory condition drops.
- **Smarter music** — read 0x524674 to know exactly when the engine thinks
  music plays (replaces launcher inference). Volume: the engine feeds
  `auxSetVolume` (0x424ba2) from the Music Level setting to device
  [0x4ed894] — set volume live instead of re-encoding mp3s (level global
  still to pin). The cutscene stop stays in the SMACKW32 proxy — right layer.
- **Radar / minimap / mission awareness** — Tier 4 enumeration works now;
  blips blocked only on the position offset.
- **AI tweaks** — write aggression (0..4) per car at logic+0xa818.
- **Save integrity** — the save writer (and the savegame.dir truncation bug)
  lives in i76shell.dll, not i76.exe; future Ghidra session on the DLL.

## Dead ends — named, so nobody re-chases them

1. **`0x25b0728` as "ammo capacity"** — it was the 50cal CURRENT ammo caught at
   full (2000); it decrements. The whole "capacity table" reading of PART 7 was
   wrong; PART 12/13 supersede it (it's record 12 of the inventory table).
2. **Single-hit value scans** (3739/3721 etc.) — landed in a resource cache on
   sequential entry IDs bracketed by filenames. A single match is a coincidence
   generator; require the full confirmation protocol (PART 8).
3. **Cross-dump differentials minutes apart** — structs relocate between dumps;
   no VA carries the transition. Diff OFFSETS through the chain
   (`i76-chaindiff.ahk`) or scan close-in-session (`i76-diffscan.ahk`).
4. **Flat car offsets on the entity** (+0x3c/+0x40 components, +0xa718/+0xa71c
   weapons) — read garbage on the transform-entity; those offsets belong to the
   logic-object side, reached via +0x108/+0x10c.
5. **"0x144-stride component sub-structs"** (STATIC-RE §9) — a hex/decimal
   units mixup; the live dissection shows records at stride **0x90** (=144
   decimal).
6. **MP player table 0x541070 for the SP car** — it's the DirectPlay table,
   all zeros in single-player. (Keep it: it IS the map for future MP work.)
7. **winedbg** — attach-to-running: macOS denies (error 5) and wow64 reads
   fault. Launch-under-winedbg: accepts breakpoints, but the game crashes on
   `cont` outside its DxWnd launch context. Parked; the chain differential
   made find-what-writes unnecessary for field mapping.
8. **Binding `pilot_yaw_delta`/`pilot_pitch` in input.map** — parses but the
   analog pilot_* actions aren't wired to the file parser; zero effect in-game.
   Head-look is memory-write only.
9. **Writing in_weapon_fire (0x5367db) to inject fire** — overwritten by the
   game's per-frame input poll. Direct value writes are the path.
10. **Armor as floats / literal-value scans for 910** — nothing; armor lives in
    int-tenths GRIDS at the 3b candidates, not an 8-int block where expected.
11. **Control files** (different subsystem, same spirit — see CLAUDE.md):
    KEYBOARD.MAP/JOYSTICK.MAP are inert; bare `Joystick` device token is dead
    (`joystick1` works); in-game Control Config menu corrupts input.map.
12. **Mac-native game FFB via DirectInput** — Wine-on-Mac has no FFB backend,
    so the REAL i7_SFRCE.DLL can never open a device here. OVERTURNED as a
    dead end 2026-07-19: the plugin architecture means a fake i7_SFRCE.DLL
    (`../ffb-shim/`) gets the game's own force stream with no DirectInput at
    all. Also corrected: there is NO "FRC registry key" gate in the Gold exe
    (the old 0x446025 "FRC" xref was a string-copy artifact of
    "I7_SFRCE.DLL"), and 0x52bbcc is a heap handle, not an FFB object.

## Open items (ranked by payoff)

1. **Lock the armor/chassis grids** (3b) — needs current DEFENSE values + one
   hit. Unlocks the full-armor trainer write.
2. **World-position offset** in the entity — unlocks radar/minimap blips.
3. **Speed confirm** (entity+0x94) — unlocks physics-driven rumble + HUD tools.
4. **+0x108 vs +0x10c reconciliation** — cheap: read both, diff the targets.
5. **Music Level global** — unlocks live volume set.
6. **Gauge-table static root** — a second, independent chain to ammo.
7. **FFB leftovers** ([FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md) §6): surface-id →
   I7_* terrain-name order; hardpoint gain/freq scales; what [veh+0xe4]
   really is (steer input vs lateral slip) — all answerable from the shim's
   telemetry in one field run.

## Tooling (repo)

| tool | purpose | status |
|---|---|---|
| `tools/i76-debugmenu.ahk` + `debugmenu.sh` | **the debug menu**: live table of every inventory record (cur/max) + the armor-candidate grids; double-click = edit, checkbox = FREEZE (entity-relative, relocation-proof); `*` marks rows that just changed and every change auto-logs in the prefix (`debugmenu.sh --fetch`); F6 rearm-all. Field-test sheet: [DEBUG-MENU-FIELD-TEST.md](DEBUG-MENU-FIELD-TEST.md) | built 2026-07-19, NOT yet field-run |
| `../ffb-shim/` | fake i7_SFRCE.DLL: activates the game's FFB path with no DI device, receives the per-tick force stream, drives XInput rumble + telemetry files ([FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md)) | builds clean, NOT yet field-run |
| `tools/gpw-envelopes.py` | sound→rumble table generator: decodes every .gpw effect (GAS0+WAVE), emits windowed-RMS envelopes (0-100) for the AHK rumble layer; output gitignored | run end-to-end (123 envelopes), integration pending |
| `tools/i76-rearm.ahk` | repair+rearm via the Tier 3 chain (F5 view / F6 write) | field-tested |
| `tools/i76-worldscan.ahk` | enumerate all vehicles via the Tier 4 table | field-tested |
| `tools/i76-trainer.ahk` | live overlay (camera/input/FFB/music/chain) + scanner + write | field-tested core |
| `tools/i76-chaindiff.ahk` + `chaindiff.sh` | relocation-proof offset differential through the chain | verified |
| `tools/i76-diffscan.ahk` | CE-style in-process live differential scanner | working |
| `tools/i76-mem-dump.ahk` + `i76-mem-scan.py` | heap dump + offline differential | superseded for dynamic values (dead end #3) — fine for statics |
| `tools/i76-findwrites.sh` | launch-under-winedbg driver | parked (dead end #7) |
| `tools/exe-xref.py` / `exe-disasm.py` | static string-xref / capstone disasm on the PE | working |
| `tools/i76-addresses.json` | machine-readable map (Gold + Nitro) | current |

Method references: [RE-METHODOLOGY.md](RE-METHODOLOGY.md) (scan/watchpoint
discipline), [RE-FIELD-GUIDE.md](RE-FIELD-GUIDE.md) +
[RE-RESOURCES.md](RE-RESOURCES.md) (cited canon),
[MW2-I76-STRUCTS.md](MW2-I76-STRUCTS.md) (file-format/struct shapes),
[SAVE-FORMAT-GAPS.md](SAVE-FORMAT-GAPS.md) (save ↔ screen reconciliation),
[SCOPE-AND-LEGITIMACY.md](SCOPE-AND-LEGITIMACY.md) (why this is fine).
