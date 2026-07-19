# Static RE findings (fable-static-re branch, 2026-07-18)

Complementary to the live-scanning main thread: these come from DISASSEMBLING
i76.exe on disk (tools/exe-xref.py + exe-disasm.py), not from value scanning.
They explain WHY the live scan for ammo kept failing and answer the music
question by reading the code instead of inferring.

## 1. Ammo lives in per-weapon SUB-OBJECTS, not the flat car struct

The real `ammoLesser` C function (0x40be60) walks the vehicle's weapon list:
```
mov  eax, [ebx + 0xa718]      ; weapon COUNT
lea  edi, [ebx + 0xa71c]      ; weapon-pointer ARRAY (dword ptrs, stride 4)
mov  ecx, [edi]               ; ecx = pointer to weapon OBJECT i
... iterate esi=0..count ...
```
So `car+0xa718` = weapon count, `car+0xa71c` = an array of POINTERS to
heap-allocated weapon objects. **The ammo count is a field INSIDE each pointed-to
weapon object** — it is NOT contiguous in the car struct.

**This is exactly why the main thread's value-scan for ammo failed at stable
addresses**: the HUD number (3721) is read through car -> ptr[i] -> weapon.ammo,
and the weapon objects are separate allocations. A flat scan can still find the
weapon-object field, but the robust path is a POINTER walk (car base ->
+0xa71c -> [i] -> +ammo_off) or a "find what accesses this address" watchpoint.
The weapon-object ammo-field offset is the one value left to pin (main thread /
the struct agent's Open76 cross-check will give it).

The engine is heavily SCRIPT-DRIVEN: `ammoLesser`, `isCBEmpty`, `playScene`,
`setUserRadar`, `SET_SPEED_*` are mission-script VM opcodes (matched in strcmp
tables, dispatched by bytecode). Many "functions" are opcode names, not C
symbols — a trap when xref-ing by string.

## 2. MUSIC state — answers "know exactly when music plays" (no inferring)

Music is MCI (`mciSendCommandA`, 2 call sites: 0x423f8d play/open, 0x424aea).
The stop path (0x423f8d) does:
```
call mciSendCommandA          ; MCI_CLOSE (0x804)
mov  [0x4ed890], 0xffffffff   ; MCI device handle = none
mov  [0x524674], 0            ; <-- MUSIC-ACTIVE FLAG cleared
```
and the play/update path (0x423fb0) gates on it:
```
mov  eax, [0x524674]          ; if zero, skip -> no music playing
test eax, eax
je   ...
mov  ecx, [0x4ed890]          ; MCI device handle
... mciSendCommandA MCI_STATUS/MCI_PLAY (0x814) ...
```
**Read `0x524674` live: nonzero = music is playing, 0 = stopped.** That is the
exact "is music supposed to be playing" signal, straight from the engine — no
more inferring from the launcher. Companion globals: `0x4ed890` = MCI device
handle (0xffffffff when closed), `0x4ed894` = aux/volume device id.

### Music VOLUME can be set from memory (instead of re-encoding the mp3s)
`auxSetVolume` (0x424ba2) is fed a 0-0xffff level computed from the in-game
"Music Level" setting, sent to device `[0x4ed894]`. So the earlier "turn music
down 10%" could be done live by writing the music-level global + re-invoking the
volume set, rather than re-encoding every track. (The exact level global is the
Audio-Control menu's backing var — a follow-up trace; the mechanism is proven.)

## 3. FFB param block (rumble-mirror groundwork, Win/Deck)
The FFB init (0x445a60) zeroes the 0x16c-byte effect param block at 0x4f2328
and sets flags (0x52bbd4=1 init-done, 0x52bbd0=0 present). The per-frame force
fill (physics -> magnitude) is a separate tick writer (0x4460e2/0x446120 region,
inside the I7FF_SIM_Effect send path) — the value to mirror into XInput rumble
on Windows/Deck. Not filled on Mac (no DI-FFB device), consistent with our
synthetic-rumble decision.

## 4. Methodology to crack the ammo encoding (see docs/RE-METHODOLOGY.md)
The winning approach, ranked (RE-methodology research):
1. **Unknown-value scan driven by firing** — no encoding assumptions; catches an
   up-counter / down-counter / fixed-point alike. Scriptable in AHK RPM today
   (snapshot all -> fire -> keep addresses that changed -> repeat).
2. **"Find what writes this address" watchpoint** — reads the encoding straight
   off the disassembly AND yields the base-register+offset for the pointer path.
   Needs a debugger — and the key enabler below.
3. Multi-width exact scans: test 3721 as int16 and float32, and 3721*65536 as
   int32 (1997 titles love int16 and 16.16 fixed-point).
4. Struct dissection once a base pointer is known.

### THE practical unlock for this setup
Native Cheat-Engine-to-Wine attach is flaky, BUT running **cheatengine.exe (or
x32dbg) INSIDE the same wineprefix** as the game (our Sikarugir wrapper) works —
both are then Windows processes in one prefix, so attach + watchpoints + pointer
scanner all function. That gives us technique #2 (the conclusive one), which
pure AHK RPM cannot do. Install CE into drive_c of the prefix and launch it via
wine, same as our AHK tools.

## 5. CONCLUSION — the ammo/armor encoding, cracked (disasm + Open76 source)

Combining this branch's disassembly with the Open76/renscreations reimplementation
source (docs/MW2-I76-STRUCTS.md) resolves the main thread's stuck scan:

**Ammo = plain signed int32, a CURRENT-ROUNDS COUNTDOWN**, one per weapon
instance (`--weapon.Ammo` per shot in Open76's WeaponsController; GDF `AmmoCount`
int32 at offset 94). NOT fixed-point, NOT a fired-up-counter. It lives inside the
per-weapon heap sub-object that this branch located via `car+0xa71c[i]`
(disasm §1). Why the main thread's scan missed it: (a) the far-apart dumps
diffed a Δ18 across too much noise; (b) the weapon sub-object is a separate
heap allocation. **Fix: fire exactly ONE shot and diff for a −1 int delta**
between two CLOSE snapshots (the countdown is unambiguous), or pointer-walk
`car -> +0xa71c -> [weapon_idx] -> +ammo_off`.

**Armor = 8 contiguous per-facet INTEGERS (4 armor + 4 chassis), in TENTHS.**
This matches BOTH the save editor's "game shows tenths" note AND Open76's
integer-subtraction damage model: stored = HUD ×10 (front 91.0 -> 910). The
earlier live scan for 910/570/700 found nothing not because the encoding is
wrong but because of dump timing / struct-not-yet-populated. **Fix: take a hit,
then tight-loop scan for 910 → new value; the 8 facets are contiguous so one
hit locates the whole block.**

**Sim runs at a fixed ~20 fps tick** (Peelar + Roanish `world_tick`): combat
ints mutate on tick boundaries — step by ticks when correlating a shot to a
delta, don't sample mid-frame.

**The conclusive tool (from RE-METHODOLOGY.md):** install `cheatengine.exe`
into the prefix's drive_c and launch it via wine (same as our AHK tools) so it's
a Windows process in the same prefix → "find what writes this address" on a
found ammo/armor byte reads the offset + base register straight off the
disassembly, giving the permanent pointer path (`[[static]+o1]+o2`) that
survives relaunch. Pure AHK RPM can't set watchpoints; CE-in-prefix can.

## 6. KEYSTONE — the static player-car pointer chain (survives relaunch)

The input-apply function (0x44f1c6, reads throttle 0x5367cc / steer 0x5367d4 and
writes them into the player car) reaches the player car like this:
```
mov eax, [0x54a264]     ; 0x457530(): world/context root  (STATIC .data global)
mov esi, eax
mov eax, [esi]          ; -> sub-object A = [[0x54a264]]
mov edi, [eax + 0x70]   ; player_car = [[[0x54a264]] + 0x70]
```
**`player_car = [[[0x54a264]] + 0x70]`** — a 3-hop pointer chain rooted at the
STATIC global **0x54a264** (loads at a fixed address, no ASLR). This is the
permanent root the whole vehicle map hangs off; unlike raw heap addresses it
survives every relaunch. `0x457530` is the world-context accessor (`return
[0x54a264]`), called all over (camera init 0x405ac1, input apply, etc.).

### Player-car field offsets confirmed so far (from disasm)
| offset | field | source |
|---|---|---|
| car + 0xe0  | steer input applied (float) | 0x44f2a2 |
| car + 0xe4  | throttle input applied (float) | 0x44f290 |
| car + 0x3c  | component COUNT (int) | component-finder 0x4b6900 |
| car + 0x40  | component ARRAY (stride 0x20, type-tag @+0) — armor/engine/tire/brake, int TENTHS | 0x4b6900 |
| car + 0xa718 | weapon COUNT (int) | ammoLesser 0x40be a5 |
| car + 0xa71c | weapon-pointer ARRAY (stride 4) -> weapon obj -> +ammo (int32 countdown) | ammoLesser |

### The permanent reader (for the trainer / any tool)
```
world   = read_u32(0x54a264)
subobj  = read_u32(world)
car     = read_u32(subobj + 0x70)
throttle_out = read_f32(car + 0xe4)      # applied control
wcount  = read_u32(car + 0xa718)
warray  = read_u32(car + 0xa71c)         # then warray[i] -> weapon -> +ammo
ccount  = read_u32(car + 0x3c)
carray  = car + 0x40                     # component[i] = carray + i*0x20
```
This turns every heap-relocating value (ammo, armor, speed, gear) into a stable
`base+offset` read. The remaining unknowns (exact ammo offset in the weapon obj,
health offset in the 0x20 component record) are a few bytes to pin with the
component/weapon record dumped via this chain — or a CE watchpoint.

## 7. KEYSTONE — LIVE-VERIFIED (2026-07-18) + honest correction

Walked the chain live: `[0x54a264]=0x542c68 -> [.]=0x2597378 -> [.+0x70]=
0x25b1948`. All three hops resolve to valid pointers, and the final object at
0x25b1948 has a **normalized rotation matrix at +0x08** (floats 0.654, 0.986,
-0.990, ...), i.e. the entity's world transform — **confirming the chain reaches
the real player-vehicle entity.** It sits in the same heap region as the ammo
capacity table (0x25b0728), consistent with a vehicle allocation.

**CONFIRMED**
- Static root `0x54a264` -> player entity `[[[0x54a264]]+0x70]` (permanent, no ASLR).
- Player entity `+0x08..0x2c` = 3x3/3x4 world transform (rotation; position nearby).
- Control inputs applied at entity `+0xe0` (steer) / `+0xe4` (throttle) — from the
  input-apply disasm (0x44f290/0x44f2a2); read 0 at idle, consistent.

**CORRECTION (was over-claimed):** the weapon container (+0xa718 count / +0xa71c
ptr array) and the component list (+0x3c/+0x40) are NOT flat offsets on this
entity base — reading them here returns garbage. They are SUB-OBJECTS reached
via accessor calls (ammoLesser used `call 0x466e20(vehicle)` to get the weapon
container; the component-finder took a different base). So the real map is:
```
entity = [[[0x54a264]]+0x70]
  +0x08 : world transform (rotation matrix; position adjacent)
  +0xe0 : steer applied   +0xe4 : throttle applied
  +????  : pointer to weapon-container sub-object  (find the offset that
           0x466e20 returns; then +0xa718 count / +0xa71c ptr array hold)
  +????  : pointer to component-list sub-object     (armor/engine/tire tenths)
```
Remaining work (small): disassemble `0x466e20` to learn which entity offset holds
the weapon-container pointer, and the component-list accessor likewise. Then the
whole map is a permanent chain. The ENTITY root + transform + controls are
proven and usable now (e.g. live position/heading for a minimap or motion-based
rumble).

## 8. Weapon sub-chain — NEGATIVE result (record so nobody re-chases it)

Tried `weapon_container = [[entity+0x70]+0x108]` (from ammoLesser's accessors
0x467440 = `[arg+0x70]`, 0x466e20 = `[arg+0x108]`). Live: it resolves to a
pointer, but `wc+0xa718` (expected weapon count) reads 0, and `[entity+0x70]`
CHANGED between two reads (0xE6E0B8 -> 0xE6E438). Conclusion: the "vehicle"
object ammoLesser operates on is NOT the same object as the transform-entity my
input chain reaches — the engine has distinct entity vs vehicle-logic
representations, and 0x467440/0x466e20 take the logic object, not the transform
entity. So the weapon/component containers are reached from a DIFFERENT root than
`[[[0x54a264]]+0x70]`.

**What's still solid:** the transform-entity chain (root 0x54a264 -> +0x70 ->
transform +0x08, controls +0xe0/+0xe4) is live-verified. **What's open:** the
vehicle-LOGIC object's own static root (the one ammoLesser's arg comes from) — find
it by disassembling ammoLesser's caller (what supplies esp+0x68), or set a CE
watchpoint on a known-live ammo byte and read the base register. That single step
connects weapons/components/armor to a permanent root; the entity side is done.

## 9. Component/weapon offset CORRECTION — indexed 0x144-stride sub-structs

Re-read the component-finder prologue (0x4b6860): the offsets I quoted as
`car+0x3c`/`+0x40`/`+0xa718` are NOT relative to the object base. The function
computes `ebp = N * 0x144` (324 bytes/entry: `N*5<<4 + N, <<2`) and addresses
`[ebx + ebp + 0x3c]`, `[ebx + ebp + 0x40]`, `[ebx + ebp + 0x820]`. So the
vehicle-logic object contains an **indexed array of 0x144-byte sub-structures**,
and:
- component count is at `base + N*0x144 + 0x3c`
- component array at `base + N*0x144 + 0x40` (stride 0x20 within)
- (the 0xa718 weapon offset similarly sits at some base+index, not a flat car
  offset)

**This is why both the value-scan AND the entity-pointer structural search
found nothing at those flat offsets** — the true address is
`base + index*0x144 + field`, and neither `base` nor `index` for the player is
known from static analysis alone (they arrive as function args / this-pointers).

### Honest division of labor (static has hit its floor here)
Static disassembly has fully mapped the SHAPES: entity chain
`[[[0x54a264]]+0x70]` (verified), the 0x144-stride component sub-struct, the
weapon-pointer-array pattern, int-tenths armor, int32-countdown ammo. What it
CANNOT cheaply yield is the absolute base of the vehicle-logic object for the
player. The conclusive tool is the **winedbg / Cheat-Engine "find what accesses
this address" watchpoint** on a live ammo or armor byte: it reads the exact
`base register + displacement` off the CPU at the moment the game touches the
value, giving both the base and the true offset in one shot. That's the live
thread's job and it closes Tier 3. Static + live meet exactly here.

## 10. Player-entity field map (live-read + gauge-code labels)

Read the verified entity (`[[[0x54a264]]+0x70]`, base 0x25b1948 this session) and
cross-referenced with the gauge code. Field layout of the transform-entity:

| offset | content | confidence |
|---|---|---|
| +0x04..0x30 | **world transform** — 3x4 float matrix (rotation cols in [-1,1]; +0x0c/+0x18/+0x24/+0x30 are the translation/position column) | high (matches Roanish 48-byte transform) |
| +0x34 | float ~1.358 (scale? bounding?) | low |
| +0x50 | float 1.000 | low |
| +0x70..0x90 | second float block (0.17, -0.14, -2.05, 0.84, 1.02...) — likely velocity/orientation deltas | med |
| +0x94 | float ~51.5 — candidate SPEED (mph-range) | med |
| +0xa4 | float 2000.0 | low (matches a weapon max-ammo constant; may be coincidence) |
| +0xc0..0xc8 | floats (-0.59, -29.5, 0.17) — candidate position or angular vel | low |
| +0xe0 | **steer applied** (float) | high (disasm 0x44f2a2) |
| +0xe4 | **throttle applied** (float) | high (disasm 0x44f290) |
| +0x104 | int 1 — a flag/count | low |
| +0x10c | **pointer** to an entity-graph sub-object (its +0x5c points back to the `sub` = [[0x54a264]]) | high (ptr), role med |
| +0x1a0..0x1d4 | **14-entry int array + -1 terminator**: `8 7 7 7 6 9 6 0 1 7 8 9 11 12 -1` — a component/mount/part-slot list (car has ~14 parts per the save editor) | med |

Notes: (1) armor tenths (910/570/700) are NOT in the entity — confirms armor lives
in the vehicle-LOGIC object (the live thread's target, already walked to
weapon_count=4). (2) The gauge code reads the player via the SAME root
(speedometer at 0x45a102 calls 0x457530 = `[0x54a264]`), so speed/RPM/gear are
reached from this entity graph — the speed float feeds a float->int (ftol
0x4ba090) then a 0-9 needle level. (3) `+0x94` (~51.5) and `+0x70` block are the
best SPEED/velocity candidates to confirm live (drive, watch which moves).

This maps the ENTITY side thoroughly; the weapon/component/armor values are the
LOGIC-object side the live thread is pinning. Together = the full vehicle.

## 11. THE ENTITY TABLE — enumerate every vehicle (radar/targeting/AI)

From `setAllAggresion` (0x40a280), which iterates ALL entities:
```
entity groups: 8 FACTION/TEAM groups
  counts       @ 0x51f5d0  (8 ints, one per group)
  ptr arrays   @ 0x507da0  (stride 0x100 = 64 slots per group)
  group g's entities: [0x507da0 + g*0x100 + slot*4]  for slot in 0..count[g]-1
```
Live-verified (this mission): group0=3, group1=2, group2=9, groups3-7=0 =>
**14 total entities** (player + allies + police + enemies — matches the mission).
Groups are teams/factions; iterate all 8 to see every car in the world.

**AI aggression** is written to `logic_object + 0xa818` (int; setAllAggresion
clamps its arg to 1-5 then stores arg-1 = 0..4). The write path
`entity -> [entity] -> +0x70 -> +0x108 = logic -> +0xa818` re-confirms the
entity+0x108 = logic-object link (both threads).

### What this unlocks
- **Radar / minimap of ALL cars** — walk the 8 groups, read each entity's
  transform (position at the transform block) -> plot blips by faction colour.
- **Targeting / threat** — enumerate hostile groups, compute range from the
  player position, find nearest enemy (what `nearestEnemy`/`target_nearest_enemy`
  do internally).
- **Mission awareness** — count alive per group (`allEnemyDead` reads these
  counts hitting 0); detect when objectives clear.
- **AI tweaks** — write aggression per entity at `logic+0xa818`, or globally via
  the same loop.

### Enumeration recipe
```
for g in 0..7:
  n = read_u32(0x51f5d0 + g*4)
  for s in 0..n-1:
    slot = read_u32(0x507da0 + g*0x100 + s*4)   # table entry
    entity = read_u32(slot)                      # actual entity (deref)
    # entity+transform = world pos/heading; entity->+0x108 = logic (health/weapons)
```
Related: `0x457530` = get world/user-entity context (`[0x54a264]`); `0x457570
(ctx, idx)` = indexed context accessor. Spawn system at 0x456ade
("Cannot find a valid spawn location"). AI is an FSM + A* pathfinder (strings
`FSM: behave`, `astar`).

## 12. Entity-table refinements + honest limits (position/faction)

Live follow-up on §11:
- **The table entries are WRAPPER objects, not transform-entities.** From
  setAllAggresion the chain is `slot -> esi(wrapper) -> [esi] -> +0x70 -> +0x108
  = logic`. Read live, the 14 table entities sit at 0x0054xxxx (a compact
  region) and do NOT equal the player's transform-entity from
  `[[[0x54a264]]+0x70]` (0x2401948 this session) — so there's a wrapper layer
  between the table and the transform-entity. Both are valid handles to the same
  car; the table is the enumeration index, the chain is the player fast-path.
- **Position offset NOT yet pinned.** The transform translation columns
  (+0x0c/0x18/0x24/0x30) read as small constants (0.0, 30.0) across all cars —
  so world position is stored elsewhere in the entity, OR the mission coords are
  origin-centered. Pinning it needs correlation (drive, watch which 3 floats
  move together) or a winedbg watchpoint on the render/transform code — the
  live thread's tools. The 0x94 (~51.5) field remains the best speed candidate.
- **Faction/team = the group index itself** (0..7 in the table); "enemy" is
  determined by group relationship, computed in the targeting code (the
  nearestEnemy/isWithinEnemy logic, which lives in the script-VM region 0x410xxx
  and is opcode-dispatched — hard to trace statically).

### Net for the entity system
CONFIRMED & usable now: the 8-group entity TABLE (counts 0x51f5d0, ptr arrays
0x507da0/0x100), live 14-entity enumeration, aggression at logic+0xa818, the
wrapper->entity->logic graph. OPEN (needs live correlation): the exact
world-position and speed offsets inside the entity — the last pieces for a live
radar/minimap, and exactly the kind of "watch it change" pin the live thread
does best. Static mapped the STRUCTURE of the world; live pins the moving floats.
