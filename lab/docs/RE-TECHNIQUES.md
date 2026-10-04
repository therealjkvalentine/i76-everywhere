# Finding things in memory — technique, and when to stop hand-rolling it

**Read this before starting a new memory hunt.** Most of what follows was learned the expensive
way on this repo, and the last section is the part that would have saved the most time.

## The rules, distilled — written the day armor finally cracked (2026-08-10)

Three days of scanning failed; the winning analysis was ~100 lines of Python that ran in
seconds, on data already sitting on disk, from a machine that couldn't even launch the game.
That asymmetry is the lesson. Each rule below is earned by a specific event in this repo.

### Before you search

1. **Classify the target's allocation lifetime before the first scan** — static, heap-stable,
   or reallocated — *and for "reallocated", establish exactly which events reallocate.* Armor
   moves on **repair** but not on **damage**; every "same address went full→0→full" search was
   dead before it ran, through 1.19 M candidates, because nobody had split those two events.
2. **The obstacle, stated precisely, is the method.** "It reallocates on every heal" felt like
   the wall. Stated precisely it reads: *"it is stable between heals"* — which is not a wall,
   it is the experimental design (compare within damage-only windows). When something breaks
   your approach, measure exactly when it fires; the complement is your laboratory.
3. **Work in coordinates where the target is stationary.** Absolute addresses were the wrong
   frame; entity-relative offsets were the right one, and in that frame the "moving" target had
   never moved at all. Every *"it keeps moving"* complaint is a missing-anchor problem — and
   the anchor (the `0x54A264` entity chain) had existed in this repo for days, built by a
   different investigation.

### Designing the search

4. **Intersect independent instances; never filter one instance harder.** One damage diff:
   ~3000 plausible drops. Two independent diffs, intersected in offset space: **3 survivors,
   all real.** Tightening thresholds on a single observation just selects prettier noise — the
   17794→828→15 narrowing ended in terrain geometry.
5. **Search for behaviour, not values.** The configured `711` existed in memory in *no* form —
   not int, not float, not scaled. Representations get converted at load; behaviour (drops on
   damage, twin lockstep copies, current bounded by max) survives any encoding.
6. **Make the stimulus produce *labelled* states.** One narrated snapshot — "only the front
   was damaged" — assigned the face layout instantly. A single labelled bit beat a million
   unlabelled diffs. And gate the stimulus twice: prove it *fired* (a whole scan once ran with
   fire bound to the wrong key) and prove *quiescence* (the idle-gate is what cracked ammo).
7. **Distrust signatures that find invariance.** "A run of identical values" locked onto the
   MAX column — which is pristine on a wrecked car, *by construction*. Any sameness-based
   signature returns the thing that never changes.

### Believing a result

8. **A real find over-explains.** The armor block was selected only on "dropped in both
   pairs" — and then, unasked, it explained armor-absorbs-gunfire-first, ramming-bypasses-armor,
   the VCF 8-slot layout, and the LEFT/RIGHT memory swap. Demand that a candidate explain
   evidence it was not selected on; a false positive fits exactly the test that found it and
   nothing else.
9. **Link memory to files.** The loader put the data there, and file layout tends to survive
   into RAM (the VCF armor block appears in the entity verbatim, scaled to tenths). If you know
   the file format, you already know the *shape* to hunt for.
10. **Only a write closes the case.** Located-and-mapped was still not "solved" until the
    console write-test moved the game's own display. Watching is correlation; writing is
    causation. (Two claims in this repo were once withdrawn for skipping this.)

### Running the investigation

11. **Retain raw captures — data outlives methods.** The winning snapshots were taken for a
    *failed* approach; the method that cracked them was invented a day later and ran on the
    same bytes. Store raw + index (pid, exe, region table), not just conclusions.
12. **When blocked from collecting, re-mine what you hold.** RDP made live work impossible —
    and that constraint forced the offline re-analysis that won. "Can't run the experiment"
    does not mean "can't make progress"; inventory existing data before waiting for access.
13. **Record dead ends *with their reasons* — they are the map.** The re-attack took hours,
    not days, because every failed route carried its cause. A dead end without its reason gets
    retried; with its reason it becomes a *constraint* ("the live value is not stored in the
    configured form") that narrows the answer.
14. **Wins are assembled from parts built for other purposes.** The entity chain came from the
    frame-rate work, the snapshots from the armor sessions, the layout from the VCF work, the
    write-verification doctrine from ammo. The expensive part of investigation is building the
    *position* from which cheap experiments win — which is why everything gets documented and
    indexed even when its investigation "failed".

## The decision that matters first: is the address stable?

| kind | example here | how to find it |
|---|---|---|
| **static** | ammo `0x005AAB0C`, weapon defs `0x5D8800`, frame counter `0x5A7E1C` | plain value scan; the address is the answer |
| **heap, stable within a session** | vehicle logic, entity | pointer chain from a static root (`0x54A264`) |
| **heap, reallocated during play** | **armor** — the regen respawn rebuilds the car | ⚠️ value scanning cannot work; anchor on a stable pointer instead — see below |

Getting this wrong costs days. Armor is reallocated on every repair, so *every* search of the
form "the same address went full → 0 → full" was dead before it ran — which is exactly what
happened, through roughly 1.19 M candidates.

**How armor was finally located (2026-08-10):** not by scanning at all, but by **cross-instance
offset intersection** on retained snapshots. A *damage* event (unlike a repair) does not
reallocate, so within a damage pair the entity pointer is stable; expressing every dropped dword
as an offset from the entity and intersecting two independent damage pairs collapses thousands of
drops to the armor block, at `entity+0x138`. The reallocation that defeated absolute-address
scanning is irrelevant once you anchor on the entity pointer and compare *offsets*, not
addresses. This also runs entirely offline — no game process — which is what made it possible
over RDP. See [ARMOR-INVESTIGATION.md](ARMOR-INVESTIGATION.md) and `tools/wip/armor/armor-offset-diff.py`.

## Techniques that worked here

**Gate the stimulus.** A value that merely "goes down when expected" is not enough — a
free-running counter does that too. Demand a pattern noise cannot fake:

```
idle -> FIRE -> idle -> FIRE      real ammo is EXACTLY CONSTANT across the idle windows
```

That collapsed ~3800 candidates to 35 and found live ammo. The earlier attempt without the idle
gate produced a confident wrong answer.

**Verify by WRITING, never by watching.** Write a distinctive value and confirm the thing the
game *displays* follows. `1234` → HUD read `30CAL MG 1234`. Two separate claims in this repo
were withdrawn because they were only ever verified by observation.

**Plant a fingerprint if you control the input.** Since the car config is an editable file
([CAR-CONFIG.md](CAR-CONFIG.md)), setting each armor face to a distinct improbable value
(711, 722, 733…) pins every copy at once — and revealed that memory order is FRONT, LEFT,
RIGHT, REAR while the file order is FRONT, RIGHT, LEFT, REAR.

**Anchor on something static.** When the target moves, find it *through* something that does
not. The static ammo array identifies the player's car by loadout signature
(`[~300, ~2000, 700, 25]`) even though the player's slot indices shift on respawn.

**Identify by shape, not by address.** `find-armor-array.py` locates a 20×`0x34` record array by
its structure, because the address is different every time.

## Traps, each of which produced a wrong answer here

- **Searching for "a run of identical values" finds the immutable column.** A record with
  `CURRENT` at +0x00 and `MAX` at +0x04 will match on MAX, which never moves — so a wrecked car
  reads pristine. Cost: a confident wrong "armor is undamaged" report, four bytes off.
- **A visual oracle that changes on its own.** The HUD damage panel moves while AI cars shoot.
  Writing 30 shifted 0.12 % of pixels and looked like a hit; writing **1**, far more extreme,
  shifted **0 %**. Always run a null capture pair to measure baseline noise.
- **Unverified stimulus.** Fire was bound to `Enter`, not `Space` — a whole scan ran with
  nothing being fired, producing 471 pure-noise candidates while the HUD still read 2000.
  Confirm the stimulus did something before trusting the diff.
- **NaN defeats range filters.** `x < lo or x > hi` never skips NaN. Use `abs(x - target) <= tol`.
- **`VirtualQueryEx` needs `PROCESS_QUERY_INFORMATION`** or it enumerates zero regions and
  silently dumps nothing.
- **A suspiciously round constant is usually your own pipeline.** A 5/6 slope in the cursor
  mapping was an aspect-ratio bug in the measurement, not a property of the game.

## When to stop hand-rolling: use the community's tools

**This is the lesson worth the most.** The "address moves every run" problem is solved, and
solved better, by [Cheat Engine's pointer scan](https://guidedhacking.com/threads/cheat-engine-pointer-scanning-tutorial-gh105.18280/):

1. find the value's current address (any method)
2. save a **pointer map**
3. restart the game / trigger the reallocation
4. find the value again, save a second pointer map
5. **diff the maps** → a pointer chain that resolves the value every time

That is precisely the armor situation, and days of differential scanning were a weaker
re-derivation of it. [Pointer scanning with pointermaps](https://guidedhacking.com/threads/cheat-engine-how-to-pointer-scan-with-pointermaps.9739/)
covers the two-session diff directly.

Cheat Engine's **"find out what writes to this address"** is the same Dr0–3 hardware-watchpoint
mechanism as our `src/find-reads.c` — see the
[CE tutorial guide](https://wiki.cheatengine.org/index.php?title=Tutorials%3ACheat_Engine_Tutorial_Guide_x64).
Its **Dissector** does structure mapping of the kind we did by hand for the `.VCF` and level
formats.

| tool | use it for |
|---|---|
| [Cheat Engine](https://wiki.cheatengine.org/) | pointer scans, "what writes here", structure dissect. **Reach for this first when an address moves** |
| [ReClass-style dissectors](https://medium.com/@AVTUNEY/reverse-engineering-game-memory-how-to-hack-any-game-using-cheat-engine-p-invoke-in-net-be70e2924506) | naming fields in a struct once you have its base |
| [game-hacking-1](https://github.com/ChaitanyaHaritash/game-hacking-1) | collected game-RE tutorials and tooling |
| [OpenRakis/Spice86](https://github.com/OpenRakis/Spice86) | real-mode DOS RE with a structured memory viewer |
| [neuviemeporte/mzretools](https://github.com/neuviemeporte/mzretools) | MZ executable inspection, DOS-era binaries |
| [RetroReversing — DOS](https://www.retroreversing.com/dos) | curated index of era-appropriate RE work |
| [DOS games with Ghidra](https://gist.github.com/alexbevi/07560b7e82dd73527f4fc59ce1ed9972) | static analysis workflow |

**Rule of thumb:** hand-rolled scanning is fine for a static address. The moment the target is
reallocated between observations, stop and pointer-scan.

**Postscript (2026-08-10):** armor was ultimately cracked by neither CE nor more scanning, but
by the *principle* CE's pointer scan implements — express the target in a frame where it is
stationary (offsets from an anchor pointer) instead of absolute addresses — applied **offline**
to retained snapshots, intersected across two independent damage events. CE remains the right
tool when you need to *discover* the anchor chain live; here the chain was already documented,
so a 100-line offline analysis beat both CE and three days of scanning. The rule generalizes:
the tool matters less than getting the coordinate frame right. See "The rules, distilled" at
the top of this file.

## Our own tooling

`tools/` — `ammo-lock.py` (set/hold ammo, finds the weapon by loadout signature),
`armor-watch.py` (snapshot/compare), `find-armor-array.py` (locate by shape),
`find-car-via-weapons.py` (anchor on the static ammo array), `range-diff.py`,
`vehicle-track.py` (follows the pointer chain per snapshot rather than assuming a fixed
address), `src/find-reads.c` (hardware watchpoints — **has crashed the game on detach**).

See also [ARMOR-INVESTIGATION.md](ARMOR-INVESTIGATION.md) for the full dead-end log.
