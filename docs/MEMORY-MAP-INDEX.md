# Interstate '76 memory map — consolidated index & architecture

*One readable place for everything the GHIDRA-MEMORY-MAP PART 1-10 sections and
the static-RE work established. Read this first; drop into the PART docs for the
raw disassembly. All addresses are GOG Gold `i76.exe`, loaded at 0x400000 (no
ASLR under Wine, so static VAs are live process addresses). Nitro deltas in
tools/i76-addresses.json.*

## The engine in one paragraph (why some things were hard)

I'76 is a **modified MechWarrior 2 engine**. Three architectural facts shaped
this whole effort: (1) it runs a **mission SCRIPT VM** — many "functions"
(`ammoLesser`, `isCBEmpty`, `playScene`, `setUserRadar`) are bytecode opcode
names matched in strcmp tables, so string-anchored disassembly often lands in a
dispatch table, not real code. (2) It keeps a **2029-bucket hash of
heap-allocated entity structs** (Roanish) — gameplay objects relocate per
mission/load, which is why flat value-scans for ammo/armor kept missing. (3) It
splits a vehicle into a **transform-entity** (position/rotation/controls) and a
separate **vehicle-LOGIC object** (weapons/components) reached by accessors —
they are different objects with different roots.

## Tier 1 — STATIC globals (permanent, no pointer chain)

| VA | type | meaning | verified |
|---|---|---|---|
| 0x536770 / 78 / 80 | int | pilot yaw / pitch / roll look input | ✓ live |
| 0x5367cc / d4 / **d0** | int | throttle / steer / **weapon fire** input | ✓ live |
| 0x5367de | byte | second fire flag (0/1) | ✓ live |

| 0x4c2964 / 6c / 70 / 74 | float | live camera Euler angles | ✓ live (head-track target) |
| 0x4c2728 | int | camera view mode (F1..F11) | ✓ |
| 0x54a264 | ptr | **world-context root** (0x457530 returns it) | ✓ live |
| 0x524674 | int | **music-active flag** (nonzero = playing) | disasm |
| 0x4ed890 / 894 | handle | MCI device / aux-volume device | disasm |
| 0x52bbd0 / cc | int/ptr | FFB present flag / object ptr | ✓ (0 on Mac) |
| 0x4f2328 | 364 B | FFB effect param block (rumble-mirror src on Win) | disasm |

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

## Tier 3 — CLOSED (weapons / components / armor / ammo)

**The link (live thread PART 11, corroborated by the static entity map §10):**
```
logic = [player_entity + 0x108]      ; vehicle-LOGIC object (weapons/components)
  logic -> 16 COMPONENT records @ stride 0x90   (engine/susp/brakes/4 tires/armor...)
  logic -> weapon container -> weapon-pointer array -> weapon -> +ammo (int32 countdown)
```
- `+0x108` is exactly the accessor `0x466e20` (`return [arg+0x108]`) that
  ammoLesser used; the static entity dump independently flagged `+0x10c` as a
  live pointer into the same graph. Both threads converged on the same link.
- Components: **16 records at stride 0x90** (supersedes the earlier 0x20/0x144
  guesses — those were intermediate mis-reads). Armor/chassis are **integer
  TENTHS** (91.0 = 910) per the save editor + Open76.
- Ammo: plain **int32 current-rounds countdown** inside each weapon object.

So the FULL permanent chain from the static root:
`[0x54a264] -> world -> [.+0x70] = entity -> [.+0x108] = logic -> components/weapons`.
Every relocating gameplay value is now a fixed base+offset walk. Exact per-field
offsets inside the 0x90 component record and the weapon object (health, ammo)
are the last few bytes the live thread is confirming with a winedbg watchpoint.

## Tier 4 — the WORLD (entity table, all vehicles)

From `setAllAggresion` (0x40a280), live-verified (14 entities this mission):
```
8 faction/team groups:
  counts     @ 0x51f5d0  (8 ints)
  ptr arrays @ 0x507da0  (stride 0x100 = 64 slots/group)
  entity(g,s) = [0x507da0 + g*0x100 + s*4]     # a WRAPPER handle
  wrapper -> [.] -> +0x70 -> +0x108 = logic object (health/weapons/aggression)
  AI aggression = logic + 0xa818 (int 0..4)
```
Enumerate all 8 groups to see every car (player, allies, police, enemies) —
the basis for a radar/minimap, targeting, threat display, and mission-clear
detection (`allEnemyDead` watches group counts -> 0). OPEN: the world-position
float offset inside the entity (transform translation reads origin-small;
needs drive-correlation or a render watchpoint) and the speed offset (best
candidate entity+0x94 ~51.5). AI/radar/targeting logic is script-VM-dispatched
(0x410xxx region) — traced live, not statically.

## How each finding powers a real feature

- **Head tracking / analog look** — write `0x4c2964`/`0x4c2970` (camera yaw/pitch)
  or the int look inputs `0x536770/78`. opentrack/webcam -> UDP -> a writer at
  frame rate = the original goal, now address-in-hand. (input.map analog binding
  is inert; it's a memory-write feature.)
- **Rumble that reads the game** — the FFB param block `0x4f2328` on Win/Deck is
  the real physics force to mirror into XInput rumble; on Mac the entity
  transform (`+0x08`, delta per frame) + control inputs drive synthetic rumble.
- **Minimap / "where am I"** — entity position/heading from the transform block.
- **Smarter music** — read `0x524674` to know exactly when music should play
  (no more inferring in the launcher); set volume via the aux device instead of
  re-encoding the mp3s.
- **Trainer / accessibility** — armor/ammo edits once the logic-object base is
  pinned (encodings already known: int tenths, int32 countdown).
- **Save integrity** — the save system lives in i76shell.dll (PART 2), which is
  also where the savegame.dir truncation bug is, for a future source-level fix.

## Tooling (repo)
- `tools/exe-xref.py` — string-VA -> pointer xref + table detection
- `tools/exe-disasm.py` — capstone x86 disasm with .data/.rdata string annotation
- `tools/i76-addresses.json` — machine-readable map (both exes)
- `tools/i76-trainer.ahk` — live overlay + scanner + write (in-prefix ReadProcessMemory)
- `tools/i76-mem-dump.ahk` + `i76-mem-scan.py` — heap dump + differential scanner
- Method: `docs/RE-METHODOLOGY.md` (run Cheat Engine INSIDE the wineprefix for
  watchpoints); shapes: `docs/MW2-I76-STRUCTS.md`; legitimacy: `docs/SCOPE-AND-LEGITIMACY.md`.

## The FFB effect block — the engine's own event feed

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

### The effect-slot array — measured live

Inside the block, base `+0x030`, **stride `0x1C`**, at least 6 slots:

| field | meaning | observed |
|---|---|---|
| `+0x00` | active flag | 0 / 1 |
| `+0x0C` | effect / weapon id | 8, 13, 17 |
| `+0x10` | float parameter, reads as a direction | 0.8104, 180.8 |
| `+0x14` | magnitude or duration | 5, 10, 60 |
| `+0x18` | flag | 0 / 1 |

A slot going `0 → 1` **is** the event. Timing identifies the kind: one slot fired
six times at even 0.75 s intervals (a weapon on a reload cycle) while others fired
in 0.1 s bursts (rapid fire). The field shape matches the DLL's own logging format,
`Hardpoint:%d WpnId:%d Freq:%d Gain:%d Direction:%d`.

Slot 6 would begin at `+0x0D8`, but that region updates continuously at the sim
tick rate with hundreds of distinct values — a different structure, not another
on/off slot. `+0x160` is the sim delta-time (0.047–0.063 ≈ 1/20 s).

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
