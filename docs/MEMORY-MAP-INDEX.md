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
| 0x5367cc / d4 / **d0** | int | throttle / steer / **weapon fire** input | ✓ live |
| 0x5367de | byte | second fire flag (0/1) | ✓ live |

| 0x4c2964 / 6c / 70 / 74 | float | live camera Euler angles | ✓ live (head-track target) |
| 0x4c2728 | int | camera view mode (F1..F11) | ✓ |
| 0x54a264 | ptr | **world-context root** (0x457530 returns it) | ✓ live |
| 0x524674 | int | **music-active flag** (nonzero = playing) | disasm |
| 0x4ed890 / 894 | handle | MCI device / aux-volume device | disasm |
| 0x52bbd0 | int | FFB present flag (1 only if i7_SFRCE.DLL init succeeded at boot) | ✓ live (0 on Mac without the shim) |
| 0x52bbcc | handle | private Win32 heap for FFB impact-event nodes (HeapCreate(0,0,0) — the old "FFB object ptr" label was wrong) | disasm |
| 0x52bbdc / e0 / e4 | ptr | I7FF_InitSystem / ExitSystem / SIM_Effect fn ptrs from the DLL | disasm |
| 0x4f2328 | 364 B | FFB force-state block, filled EVERY sim tick by ffb_tick 0x445ba0 whenever the flag is 1 — full field map in [FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md) | disasm (deep-dived 2026-07-19) |
| 0x541070 | table | DirectPlay MP player table (16×0x48, veh ptr @+0x28) | ✓ live-zero in SP — MP only |

**CORRECTION 2026-08-04 — weapon fire is `0x5367d0`, not `0x5367db`.** Measured
with `tools/ffb/ffb-find-fire.ps1`, which diffs an idle baseline against a firing
phase with the steering held still (holding still is what isolates fire from the
throttle and steer entries sharing this block). Firing moved exactly two bytes,
each taking only `{0, 1}`: **`0x5367d0`** and **`0x5367de`**. `0x5367db` did **not**
move.

`0x5367d0` also sits exactly between throttle (`0x5367cc`) and steer (`0x5367d4`)
in what is plainly a 4-byte-strided input array, so `db` reads as a transcription
slip for `d0`. `0x5367de` is unaligned and is more likely a derived or per-weapon
flag — I'76 has two distinct fire actions (`weapon_fire` and `hardpoint1_fire`),
which has caused trouble in this repo before when a binding landed on the wrong
one. Which of the two is which is **not** established.

**SUPERSEDED for weapon detection.** These input bytes were used to drive the FFB
weapon channel and produced no response across two field sessions — a button
moving is not the same thing as a weapon firing. Use the engine's own effect table
instead (see "The FFB effect block" at the end of this document); the input flag
remains only as a fallback.

## Tier 2 — the PLAYER pointer chain (permanent root, live-verified)

```
world  = [0x54a264]
sub    = [world]
entity = [sub + 0x70]          ; = [[[0x54a264]] + 0x70]   the player vehicle entity
  entity+0x04..0x30 : FOUR float3 = wheel contact points, LOCAL space  ✓ verified
  entity+0xac : speed = |velocity|  (float)                            ✓ verified
  entity+0xbc : velocity x,y,z      (float3, world space)              ✓ verified
  entity+0xc8 : angular velocity x,y,z — YAW RATE at +0xcc (float3)    strong
  entity+0xd4 : acceleration / accumulated force (float3)              likely
  entity+0xe0 : steer applied (float, -1..1)                            disasm + live
  entity+0xe4 : throttle applied (float, -1..1, negative = brake)       disasm + live
  entity+0x80..0x8c : LOOP TEMPORARY — looks like telemetry, is not
```
This is the durable base for heading/controls/dynamics — survives relaunch.

**CORRECTION 2026-08-02 — `+0x08` is not a transform.** This table previously read
`entity+0x08 : world transform (rotation matrix; position adjacent) ✓ verified`.
It is not a rotation matrix. `+0x04..0x30` is **four float3 wheel contact points
in local space** — parked they read `(-0.99, 0.654, -2.37) (0.99, 0.654, -2.37)
(0.99, 0.654, 2.29) (-0.99, 0.654, 2.29)`: x and z flip sign, y is constant. That
is a rectangle in the xz plane at one ride height. An orthonormality scan over the
whole first `0x200` bytes finds **no** rotation matrix anywhere in this struct.

The likely origin of the error is that `0.654` sits in a 0..1 range and reads like
a matrix element, when it is a y coordinate. It mattered: the "position adjacent"
note sent the position hunt looking next to a matrix that does not exist, which is
why position stayed unfound while velocity was sitting 0xA0 bytes further on.

**Units are metres.** The wheel corners give a wheelbase of 4.662 m and a track of
1.976 m — a large American car, which is what I'76 drives — so speed is m/s and
the observed 21.2 m/s top speed is 47 mph.

**`+0xac`/`+0xbc` supersede the "velocity: nothing anywhere" note** in
GHIDRA-MEMORY-MAP.md §149. Confirmed by an exact identity rather than by
plausible values: on a car left barely rolling, `velocity = (0.5676, 0, 1.3592)`
has magnitude `1.47296` and `+0xac` reads `1.473`. Note the method — a *stationary*
car cannot show this (0 == 0) and a fast one is hard to sample coherently across
two reads; a slowly-rolling one proves it in a single frame. The y term at `+0xc0`
stays ~0 on flat ground, which is why a range-based probe sees velocity as two
moving floats with a dead one between them rather than as a vector.

Consumed by `tools/ffb/Telemetry.ps1`; the two values that remain assumptions
(yaw sign, steering lock) are measured by `tools/ffb/ffb-calibrate.ps1`.

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

## Tier 3 — the inventory table: CAPACITY, not live ammo (**claim retracted**)

> **RETRACTION (field run 2026-07-19).** This tier was previously headed "ammo
> SOLVED". It is not. With the HUD showing 50cal=**1995** and 7.62T=**3986**,
> the table records read **2000/2000** and **4000/4000** — and *freezing* them
> changed nothing on the HUD. These records are **static capacity / durability**,
> not the live round count. The earlier "live-verified" reading (PART 12 catching
> 2000→1856) most likely compared a capacity value against a HUD glance rather
> than tracking it. **The live per-weapon ammo count is still UNLOCATED.**
>
> An exact-value scan of 158 MB for 1995/3986 returned 22 hits — three mirrored
> regions plus two in the known `0x04b1xxxx` resource-cache area — and a peek at
> the best candidate showed no capacity neighbour and no record structure, i.e.
> cache indices the value merely passes through (PART 8's coincidence trap).
> Headless scanning has now failed on this target repeatedly; the next move is a
> live debugger's **find-what-writes** (see the Cheat-Engine plan in
> [RE-METHODOLOGY.md](RE-METHODOLOGY.md) §6).
>
> What *does* still hold: the table is real, chain-addressable, and writing
> cur=max across it **does** refill ammo in the garage/repair sense
> (`i76-rearm.ahk` was field-tested) — it is the capacity/condition store.

The structure below is accurate; only the "this is the live count" reading was
wrong. Live-verified twice for *location*, including across a relocation:

```
entity   = [ [ [0x54a264] ] + 0x70 ]
table    = entity - 0x1228          ; the CAR-WEAPON ammo table; record 0 = 50cal
record w = table + w*0x38
  +0x00  int 7           ; header tag  — VALIDATE before trusting the table
  +0x04  ptr 0x00750000  ; shared class ptr — second half of the signature
  +0x08  int CURRENT     ; live ammo (weapons) / condition (parts)  ← write target
  +0x0c  int MAX         ; capacity / full condition
```

- **Base correction (field run 2026-07-19).** The ammo table is at **`entity −
  0x1228`** — this is the base PART 12 live-verified against the HUD (record 0 =
  50cal @ 2000, record 1 = 7.62 turret @ 4000; in that run the absolute base
  landed at `0x25b0720`, matching `entity − 0x1228` exactly). The earlier
  `entity − 0x14C8` (PART 13b) is **12 records too early** — it starts a
  contiguous PRECEDING table (owned-but-unmounted / repair-queue weapons: the
  "van"), so the car weapons show up at its records 12–16. Both bases carry the
  (7, 0x00750000) header, which is why the sweep locked onto the wrong one.
  `−0x14C8` is a valid *superset* base (rearming across it refills car + van
  harmlessly, which is why `i76-rearm.ahk` worked), but for a HUD-aligned view
  use `−0x1228`. The debug menu now tries `−0x1228` first, `−0x14C8` second.
- Records = each owned weapon's ammo (and parts' durability/condition, matching
  the save editor's dur/cond columns). NOTE: the small-count HUD items
  (cluster-bomb 30, landmines 25, nitrous 3, specials) do NOT appear as records
  with those values — droppers/specials are a separate subsystem; only the
  gun-ammo weapons are in this table. Identify each record by the fire
  differential (fire one weapon, see which record's CURRENT drops).
- Robust resolve: `entity-0x1228` → check (7, 0x00750000); else `entity-0x14C8`;
  else sweep `entity-0x1500..entity-0x1000`.
- Secondary confirmation: HUD ammo-gauge structs (stride 0xC0, session-heap)
  each hold a pointer to a record's +0x08.
- Encoding: ammo is a plain int32 countdown (**1:1 with the HUD** — PART 12
  caught 50cal at 2000 then 1856 after a burst, not doubled); part/armor values
  are integer TENTHS (91.0 shown = 910 stored). No floats/fixed-point.
- **OPEN — the "linked counter":** firing the 7.62T dropped its ammo record AND
  a van-table record by the *exact same amount*. Whether that second record is a
  backing pool, a mirror, or coincidence is unresolved (low priority).

## Tier 3b — armor/chassis: candidates RETIRED, active hunt via F4

The DEFENSE-panel facets are NOT in the inventory table and NOT at flat entity
offsets. The earlier candidate grids are now **retired** — a field run
(2026-07-19, Picard Piranha, garage armor 100/57/57/76 chassis 70/35/35/50)
read them live and they did NOT match:

| where | read live this run | verdict |
|---|---|---|
| entity − 0x800 | 80.0/100.0 runs (800, 1000), no 570 anywhere | ✗ not this car's armor |
| entity + 0x135c | uniform 40.0 grid (all 400) | ✗ not this car's chassis |

So armor is either elsewhere, or not a simple ×10 tuple near the entity. **Active
approach:** `i76-debugmenu.ahk` **F4 facet-scan** sweeps a 128 KB window around
the entity for a contiguous `(front, 57, 57, 76)` armor run and `(front, 35, 35,
50)` chassis run (front wildcarded — may be damaged; R=L on this car so facet
order is moot). Awaiting that scan. Fallback if it whiffs: armor is the
per-panel damage GRID (not a 4-facet rollup) and needs a take-a-hit differential.

Also unpinned: the component-record field meanings inside the 16 × 0x90 records
off entity+0x10c (+0x40 int dur 100, +0xac float 100.0, +0xc4 = 50 observed).

### Inventory record identities (field run 2026-07-19)
Confirmed live: **rec 12 = 50cal MG** (2000), **rec 13 = 7.62 turret** (4000,
drained on fire, matched HUD). **rec 10** (5000) drains by the *exact same
amount* as rec 13 when firing — an unidentified linked counter (backing pool /
mirror?), flagged for a later look. Records 00–09 are the other weapons/parts.

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
- **Motion sim / wheel FFB (6DOF)** — the shim also emits the stream as UDP for
  the standard home-rig receivers (SimTools/SimHub), whose axis-testers are the
  visualizer. The force vector gives surge+sway today; true heave/roll/pitch/yaw
  want a memory reader for the entity transform (Tier 2). Full plan, honest
  gaps, and the wheel-torque reality (Windows-only): [MOTION-SIM.md](MOTION-SIM.md).
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
| `../ffb-shim/` | fake i7_SFRCE.DLL: activates the game's FFB path with no DI device, receives the per-tick force stream, drives XInput rumble + telemetry files + UDP ([FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md)) | field-run and tuned on the Mac 2026-07-19/20; never run on Windows |
| `tools/i76-ffb-monitor.ahk` | in-prefix overlay of the FFB stream (motor bars, force channels, flags, impacts) — the "watch it while driving" viewer | built 2026-07-19, NOT yet field-run |
| `tools/ffb-udp-listen.py` | UDP telemetry listener: live dashboard / `--raw` / `--csv`; proves the wire, stands in for SimHub ([MOTION-SIM.md](MOTION-SIM.md)) | wire-verified loopback |
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

## The FFB effect block — the engine's own event feed

*Two stacks consume this block by different routes and disagree in one place; [FFB-STACKS.md](FFB-STACKS.md) maps both and lists where they fight.*

`I7_SFRCE.DLL` exports exactly three symbols, and every force-feedback event the
engine plays goes through one of them:

| VA | meaning |
|---|---|
| `0x52bbdc` | resolved `I7FF_InitSystem` pointer |
| `0x52bbe0` | resolved `I7FF_ExitSystem` pointer |
| `0x52bbe4` | resolved **`I7FF_SIM_Effect`** pointer — the single event funnel |
| `0x4f2328` | **364-byte effect parameter block** (`0x16c`), the function's only argument |

Dispatcher at `0x446110`:

```
mov  eax, [0x52bbe4]
test eax, eax
je   0x446155                     ; the engine ALREADY tolerates a null pointer
push 0x4f2328
mov  dword ptr [0x4f2328], 0x16c  ; sizeof(struct)
call eax
```

Reached from `0x445B58` / `0x445B76` / `0x445B98` (enable/disable toggles) and
from `0x445E83`, a call out of the parameter builder — the function that reads the
player entity at `+0x70`, so that is the per-event path.

### The effect-slot array — measured live, and named from the DLL

Inside the block, base `+0x030`, **stride `0x1C`**, six slots. Two independent
routes reached this structure and agree on its shape: measured live from outside
by `tools/ffb/ffb-watch-effects.ps1` (Windows), and disassembled out of
`i7_sfrce.dll` itself to build the shim ([FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md),
Mac). They are one record per **hardpoint**, not per generic effect.

| field | live observation | name from the DLL disasm |
|---|---|---|
| `+0x00` | active flag, 0 / 1 | firing count/flag — nonzero while the trigger is held |
| `+0x04` | — | event flag -> misfire ("Misfire: Triggered") |
| `+0x08` | — | second misfire-ish flag (jammed/dry — a guess) |
| `+0x0C` | effect / weapon id: 8, 13, 17 | **WpnId**, indexes DLL table `0x1000f148` (stride 16); ids `0x0d..0x10` are missiles |
| `+0x10` | float: 0.8104, 180.8 — read as a **direction** | f32 firing **frequency** (scaled by DLL const `0x1000d4f8`) |
| `+0x14` | magnitude or duration: 5, 10, 60 | int **gain** |
| `+0x18` | flag, 0 / 1 | DLL prev/active marker |

**`+0x10` is the one open disagreement**, and it is worth settling because both
halves key weapons off this record. The DLL's own log line is
`Hardpoint:%d WpnId:%d Freq:%d Gain:%d Direction:%d` — it carries both a Freq and
a Direction, so the format alone cannot decide it, and 180.8 does look like
degrees. The disassembly says the record holds freq and gain, and that direction
lives on the *impact* nodes instead (node `+0x00`, degrees as a float). One drive
settles it: fire the same weapon pointed different ways and watch whether `+0x10`
moves.

The two routes confirm each other everywhere else. Six slots ending at `+0xd3`
matches the live finding that `+0x0D8` is a different structure — it updates
continuously at tick rate with hundreds of distinct values, not an on/off slot —
and `+0x160` reads as the sim delta-time on both sides (0.047–0.063 ≈ 1/20 s; the
DLL decays effect magnitude with it).

A slot going `0 -> 1` **is** the event. Timing identifies the kind: one slot fired
six times at even 0.75 s intervals (a weapon on a reload cycle) while others fired
in 0.1 s bursts (rapid fire).

**Mind the field widths on the impact list.** Its nodes store direction and
magnitude as **floats**, not ints — a shim that read them as ints turned a
50-damage hit into ~1e9 and pinned the motor (live-confirmed 2026-07-20). Full
node layout in [FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md).

**Why this beats the input flag at `0x5367d0`:** it is what the engine *decided*,
after input handling, weapon logic, ammo and damage rules have run. An input byte
says a button moved; this says a weapon actually fired. Watching the input flag
produced no weapon response in the field; this does.

**Consequence for patching:** zero `0x52bbe4` rather than `0x52bbd0` to stop the
crash at `I7_SFRCE.DLL+0x2505`. Zeroing the *flag* makes the gated callers bail
before the block is ever filled, so the engine's events become invisible; zeroing
the *pointer* lets every effect be built and merely skips the call into the DLL.
The null check is the engine's own. Read by `tools/ffb/Telemetry.ps1`; watch it
live with `tools/ffb/ffb-watch-effects.ps1`.