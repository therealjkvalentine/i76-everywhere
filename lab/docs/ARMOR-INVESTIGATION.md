# Live armor — SOLVED

**Status: CRACKED (2026-08-10).** Located offline by cross-instance offset intersection, then
**confirmed by the live write-test at the console** — `armor-authority-test.ps1` ran against a
live mission and the game followed the writes (user-confirmed same day). Armor lives **inside
the player entity**, reached by the stable pointer chain that survives the repair reallocation.

*Bookkeeping still owed: paste the test's phase output below, so this records which copy (A at
`+0x138`, B at `+0x178`, or both) drives the HUD, and whether the phase-3 repair healed the car.*

## THE FINDING (2026-08-10): armor is in the entity at +0x138..+0x174

Found **offline**, with no running game, by re-analysing the retained damage snapshots — which
is why it could be done over RDP where the earlier live hunt could not run at all.

**Method that cracked it — cross-instance offset intersection.** The car only reallocates on a
*repair*; a pure *damage* event keeps the same allocation, so within a damage pair every address
is comparable and the entity pointer is stable. Two independent damage pairs exist in the
retained snapshots:

```
full     -> hurt        entity 0xd740480   (one instance)
prefront -> frontgone   entity 0xd749a8c   (a different instance)
```

A real armor field drops in **both** pairs, but at different absolute addresses (different
instance). What it shares is its **offset from the entity base**. Expressing every dropped dword
as `addr - entity` and intersecting the two pairs collapses ~3000 vs ~4700 noisy drops to **three
offsets** — and two of them are the same value in lockstep. Tool: `tools/wip/armor/armor-offset-diff.py`.

**The structure** (integer tenths, `800` = 80.0; confirmed with `tools/wip/armor/armor-structure.py`).
The 8 components are exactly the **VCF armor block** documented in [CAR-CONFIG.md](CAR-CONFIG.md) —
4 external **ARMOR** faces followed by 4 **CHASSIS** faces — so the live store and the config
format are now linked:

| entity offset | meaning | full value |
|---|---|---|
| `+0x138 .. +0x154` | **current[8]** = ARMOR[FRONT,LEFT,RIGHT,REAR] then CHASSIS[FRONT,LEFT,RIGHT,REAR] | `[800,800,800,800, 720,720,720,720]` |
| `+0x158 .. +0x174` | **max[8]** — same layout, constant | `[800,800,800,800, 720,720,720,720]` |
| `+0x178 .. +0x198` | **copy B** — byte-identical lockstep copy | — |

| component | offset (copy A) | copy B | max |
|---|---|---|---|
| ARMOR&nbsp;&nbsp;FRONT | `+0x138` | `+0x178` | `+0x158` |
| ARMOR&nbsp;&nbsp;LEFT | `+0x13C` | `+0x17C` | `+0x15C` |
| ARMOR&nbsp;&nbsp;RIGHT | `+0x140` | `+0x180` | `+0x160` |
| ARMOR&nbsp;&nbsp;REAR | `+0x144` | `+0x184` | `+0x164` |
| CHASSIS FRONT | `+0x148` | `+0x18C` | `+0x168` |
| CHASSIS LEFT | `+0x14C` | `+0x190` | `+0x16C` |
| CHASSIS RIGHT | `+0x150` | `+0x194` | `+0x170` |
| CHASSIS REAR | `+0x154` | `+0x198` | `+0x174` |

**The two-system split is confirmed by the damage states, not guessed:**
- In `hurt` (gunfire) **all four ARMOR faces are 0 while CHASSIS is 578–720** — external armor
  absorbs gunfire first, then chassis, exactly the documented game model.
- In `frontonly` (created by ramming) **CHASSIS FRONT dropped (720→699) while ARMOR stayed full** —
  ramming/fire bypasses external armor and hits the chassis directly.
- In `frontgone` both ARMOR FRONT and CHASSIS FRONT reach 0 (front destroyed through both layers).

Memory order within each group is FRONT, LEFT, RIGHT, REAR — the RIGHT/LEFT swap versus the file
order that [CAR-CONFIG.md](CAR-CONFIG.md) records from its fingerprint test.

**Discarded:** `+0x510` also survived the intersection (1200→~1110) but reads as a *pointer* in
the `part`/`fixed` instances, so its `1200` was coincidence — it is not armor. The `+0x138..+0x174`
block, by contrast, holds armor-range integers in **all eight** snapshot states.

## The one thing left: which representation does the game READ?

There are now **three** known representations of the same armor: entity copy A (`+0x138`), entity
copy B (`+0x178`), and the external `20×0x34` mirror from the earlier session (below), which was
*proven downstream* — writes to it revert in ~300 ms. Copies A and B are byte-identical in every
at-rest snapshot, so snapshots alone cannot say which the damage model and HUD actually consume.
That needs a **live write-test at the physical console** (it cannot be done over RDP — the game's
3D will not init, so nothing can be launched or written; see the repo's RDP note).

**The staged test: `tools/wip/armor/armor-authority-test.ps1`.** In a mission it writes a
distinctive value to copy A's faces, holds it, and reports whether the write sticks and whether
the HUD damage panel follows; then repeats for copy B; then a full-repair test (set current=max).
The authority is the copy whose write **persists** (is not overwritten next frame) **and** drives
the display. Run it at the monitor and paste the output.

## What IS solved: ammo

Static array, survives everything including respawns:

```
0x005AAB0C   stride 0x4C   ammo at +0x1C   (0x0FFFFFFF = unlimited)
```

Proven by writing: `1234` → HUD read `30CAL MG 1234`; `7777`/`4242` → `30CAL MG 7777` /
`OIL SLICK 4242`; `3333` into slot 6 during a guided session matched the player's reported
1981. Tool: `tools/vehicle/ammo-lock.py` (`--set N --hold SECONDS`).

**Because it is static, it is the anchor for everything that moves.** The player's car is
identified by its loadout signature (`[~300, ~2000, 700, 25]` = 25mm / 50cal / Gas Launcher /
Landmines) rather than a fixed slot, because a respawn shifts which slots the player occupies —
observed slots 0–3 becoming 5–8.

## The thing that broke every armor search

**The regen repair spot heals by RESPAWNING the car, which reallocates the vehicle.**

```
across one heal:   entity 0xD740480 -> 0xD742CD0      logic 0x4D3AA0C -> 0x937BAC0
weapon objects:    0xD64BC2C..     -> 0xD662BE8..     (brand new allocations)
```

So armor can never satisfy *"the same address went full → 0 → full"*. Every filter built on
that premise was dead on arrival, which is why ~1.19 M churn-excluded candidates still left
nothing near the vehicle.

## What was found: a live damage MIRROR

20 records, stride `0x34`, a few KB before the player entity:

```
+0x00   CURRENT   integer tenths, drops with damage, 0 = destroyed
+0x04   MAX       integer tenths, the .vcf configured value, never moves
```

400 = 40.0, exactly the `.vcf` encoding ([CAR-CONFIG.md](CAR-CONFIG.md)). It tracks damage
faithfully: diffing two snapshots taken seconds apart around a single damage event showed
entries dropping to 0 precisely when damage was reported.

**But writing MAX over CURRENT for all 20 records repaired nothing visible.** It is downstream —
something else owns the value. Same shape as a stride-`0x2C` block found earlier in the sandbox
whose writes reverted within 300 ms.

## Dead ends, each with why it died

| approach | why it failed |
|---|---|
| search for the configured value (int 711, float 711.0, float 71.1) | live copy is not stored in that form; engine converts at load |
| "zero → large on heal" | only catches *destroyed* faces; a merely-damaged face never zeroes |
| intersect two heal cycles | respawn moves everything; survivors were terrain (`4270.00`, `49317.45` — world X/Z of a road strip) |
| HUD damage panel as oracle | changes on its own while AI cars shoot. Writing 30 moved 0.12 % of pixels and looked like a hit; writing **1**, far more extreme, moved **0 %**. Coincidence, not causation |
| "wait for AI fire" as stimulus | 35 s produced no armor change at all |
| wall grinding | negligible damage at low speed |
| own landmines | only 1 of 3 drops registered; inconclusive |
| iterative narrowing (17794 → 828 → 15) | survivors were smooth alternating floats with negatives — geometry, not armor |
| search "a run of identical values" | **locks onto the MAX column, not CURRENT** — max never moves, so it looks pristine on a wrecked car |
| entity − 0x410 | held for one car, coincidence; pointer garbage for the next |
| inside the vehicle-logic object | only 11 values moved across its whole `0x20000` span |
| "one array per vehicle" | wrong — exactly **one** such array exists process-wide |

## Two mistakes worth not repeating

1. **Reading four bytes off.** The array was reported "all 400, undamaged" on a wrecked car
   because the scan had locked onto MAX instead of CURRENT. Any signature built on *sameness*
   finds the immutable column by construction.
2. **Not connecting the mirror behaviour.** The stride-`0x2C` sandbox block that reverted writes
   in 300 ms was the same phenomenon, observed days earlier.

## Next step

**Run `tools/wip/armor/armor-authority-test.ps1` at the physical console** (see the section above).
It write-tests entity copy A vs copy B against the HUD and reports which is authoritative. That is
the whole remaining question; everything else is mapped.

If the write-test shows *neither* entity copy is authoritative (both revert, like the external
mirror did), the fallback is the original plan: a **hardware write breakpoint** on a face offset
via `src/find-reads.c` (Dr0–3), taking landmine self-damage (key `4`; see
`tools/vehicle/map-hardpoints.py`) on the sandbox — whatever writes the face each frame is reading
the true authority. But the entity copies are the strong favourites: they sit in the entity
struct itself, reached by the same stable chain that yields velocity/orientation, and they were
isolated by two independent damage events.

### How this was found without a running game (reusable)

The whole breakthrough was offline snapshot analysis, which matters because it works over RDP and
without risking the game:
- `tools/wip/armor/snaplib.py` — resolve any virtual address inside an `armor-watch` snapshot.
- `tools/wip/armor/armor-offset-diff.py` — cross-instance offset intersection (the method above).
- `tools/wip/armor/armor-structure.py` — variable-vs-constant map, lockstep copies, face assignment.
- `tools/wip/armor/entity-view.py` — print any entity-struct range across all damage states.

## Prior art

Community tooling for this problem is mature; we are re-deriving known technique.

| resource | relevance |
|---|---|
| [Cheat Engine pointer-scan tutorial](https://guidedhacking.com/threads/cheat-engine-pointer-scanning-tutorial-gh105.18280/) | the canonical answer to "the address changes every run": find the value, save a pointer map, restart, find it again, diff the maps |
| [Pointer scanning with pointermaps](https://guidedhacking.com/threads/cheat-engine-how-to-pointer-scan-with-pointermaps.9739/) | the two-session diff method, which is what our respawn problem needs |
| [Cheat Engine tutorial guide](https://wiki.cheatengine.org/index.php?title=Tutorials%3ACheat_Engine_Tutorial_Guide_x64) | "find out what accesses/writes this address" — the same Dr0–3 mechanism as `find-reads.c` |
| [Reverse engineering game memory with P/Invoke](https://medium.com/@AVTUNEY/reverse-engineering-game-memory-how-to-hack-any-game-using-cheat-engine-p-invoke-in-net-be70e2924506) | ReadProcessMemory/WriteProcessMemory patterns matching our tools |
| [game-hacking-1](https://github.com/ChaitanyaHaritash/game-hacking-1) | collected tutorials and tools for game RE |
| [OpenRakis/Spice86](https://github.com/OpenRakis/Spice86) | reverse-engineer and rewrite real-mode DOS programs; has a structured memory viewer |
| [neuviemeporte/mzretools](https://github.com/neuviemeporte/mzretools) | MZ executable inspection for DOS-era games |
| [retroreversing.com/dos](https://www.retroreversing.com/dos) | curated index of DOS game RE work |
| [Reverse Engineering DOS Games with Ghidra](https://gist.github.com/alexbevi/07560b7e82dd73527f4fc59ce1ed9972) | Ghidra workflow for era-appropriate binaries |

**The honest read:** Cheat Engine's pointer-scan workflow already solves "the address moves every
respawn" properly, and we have been hand-rolling a weaker version of it. Using it (or
implementing a real pointer map) is likely faster than more differential scanning.

## Data retained

`captures/armorwatch/` — snapshots `full`, `drove`, `hurt`, `fixed`, `part`, `fixed2`,
`frontonly`, `prefront`, `frontgone` (~90–100 MB each), plus `churn.json` (1.19 M addresses that
move while merely driving). All re-analysable offline; the tools take snapshot names.

Tools: `armor-watch`, `armor-rounds`, `armor-churn`, `armor-zeroed`, `armor-final`,
`armor-final2`, `armor-bigdrop`, `armor-array`, `armor-list-arrays`, `armor-set-live`,
`armor-repair-live`, `vehicle-diff`, `vehicle-track`, `vehicle-damage-diff`, `range-diff`,
`find-car-via-weapons`, `find-armor-array`, `ammo-lock`, `map-hardpoints`.
