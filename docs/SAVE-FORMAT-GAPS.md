# Save format: what we READ vs what the GAME writes

*Reconciled 2026-10-02 against the shell's own writer (`i76shell.dll` `Cmp_Write` 0x10032980,
`dir_WriteAndSave` 0x10032f80 - `../i76-map/shell/SAVE.md`, `shell/work/cmp-layout.md`) and 46
game-written `.cmp`/`.spc` files + 5 `savegame.dir` files (byte-exact round trips in
`tests/test_save_editor.py`). The 2026-07 version of this page was built on an inventory frame
that started 32 bytes late and a directory frame that started 36 bytes late; everything it called
"open", "truncated" or "corrupt" was that offset. The retired statements are summarised at the
bottom so nobody re-derives them. Status words: **verified** = bytes vs the in-game screen or the
shell's code; **data** = holds on every game-written file on this machine, not yet shown on screen;
**open** = needs the game (probes in [EDITOR-FIELD-TESTS.md](EDITOR-FIELD-TESTS.md)).*

## 1. `saveNNN.cmp` (and `reconfig.spc`, `trip4.spc` - same writer)

```
0x000  GarageRec, 0x8c4 bytes (the shell's slot record, written verbatim)
0x8c4  u32 nA
0x8c8  nA x 0x74  section A - the inventory ring
       u32 nC
       nC x 0x74  section C - the repair queue (copies of the state-3 A records)
size == 0x8c4 + 8 + 0x74*(nA+nC), exactly.  No padding, no trailer, nothing truncated.
```

Each 0x74 record is a **PartNode (0x20) followed by a PartRec (0x54)**:

| offset | field | status |
|---|---|---|
| +0x00 u32[3] | runtime pointers (rec*, next, prev) - rewritten on load, garbage on disk | verified (code) |
| **+0x0c u32** | **condition** (hit points) | verified (code; `PartNode_DamageLevel` grades it against +0x6c in thirds) |
| **+0x10 u32** | **state**: 1 mounted on the car, 2 in the van (V), 3 queued for repair (R), 4 dropped = field salvage (S) | 1 and 3 verified (data: state-1 names == the equipped block in 21/21 game saves; section C == state-3 records in 21/21); 2 vs 4 **open** (data: state-2 counts never exceed the panel caps, state-4 counts run to 46; `trip4.spc` loading frees state 4) |
| +0x14 12 B | runtime leftovers, never read (often the slot type) | verified (code) |
| +0x20 char[30] | display name | verified |
| +0x3e u32 | type: 2 engine, 3 suspension, 4 brakes, 5 wheel, 7 gun, 8 dropper, 13 special | verified |
| +0x42 u32 | 0; 11 on game-rewritten turret-class guns | data, meaning unknown |
| +0x4e char[13] | class id (`eng01`, `slg02`, `whe01`; "" for specials) | verified |
| +0x5b char[13] | def file (`gmmedium.gdf`, `eng02`, `wauto_1b.wdf`, `spc05`) - what section C is matched on | verified (code) |
| +0x68 u32 | 0..3 | data, meaning unknown |
| +0x6c u32 | full condition = the def's maxHP (gdf offset 76) | verified |
| +0x70 f32 | weight = the def's weight | verified |

**Section C** is written from the shell's repair list: byte copies of ring records whose state is 3,
in bench order (not A order). On load each C record is resolved back to the first ring node with the
same condition, state 3 and def file; unmatched references are dropped silently. So an editor that
changes a part's state or condition must regenerate C (`Cmp.sync_repair_queue()` /
`withRepairQueue()`), and an unedited file must keep C's bytes - both tested.

### GarageRec (0x8c4 bytes)

| offset | content | status |
|---|---|---|
| +0x000 char[20] | car name ("Picard Piranha") | verified |
| +0x014 char[20] | variant ("Stock (Orange)") - LOAD-list text; the string exists nowhere else in the game data, so it is written-not-read | verified |
| +0x028 char[16] | id ("doarmel") | data |
| +0x03c u32, +0x040 | Mr. Damage registry: count, then 32-byte records `{u32 slot type, char[16] name, u32 x, u32 y, u32 0}`; x,y are the damage-panel coordinates (WHL FR 408,119 ...) | verified |
| +0x400 char[14][30] | **equipped by name**: engine, susp, brakes, tires FR/FL/RR/RL, weapons x4 (Piranha order: dropper, top1, top2, rear), specials x3; empty hardpoint = the literal `"Empty"`. Special 1/2/3 display order = registry order | verified |
| +0x7fc u32[8] | **armor in tenths**: armor F/R/L/Rear, chassis F/R/L/Rear (910,570,570,700 <-> 91/57/57/70) | verified |
| +0x820 / +0x82d char[13] | vdf `vppirnha.vdf`, vtf `piranha1.vtf` = the paint (2/3/4 = the other factory schemes) | vdf verified; repaint **open** (CAL PAINT BLUE) |
| +0x83a/+0x847/+0x854 | wheel wdf front/mid(null)/rear | verified |
| +0x864 13 x u32 | slot classes (2,4,1,2,5,2,1,1,3,1,1,...) | data |
| +0x898.. | two floats (1940.0-ish, 1320.0) and zeros | data; the 1320 is NOT the chassis weight |

**Weight (verified 2026-07-14, unaffected by the frame bug):** `total = 2910 + sum of mounted part
weights + 1.0 lb x armor points`, exact on two in-game builds (3986 / 3727 lbs).

**Panel caps (user-read 2026-07-14):** engines 3, suspensions 4, brakes 4, specials 9, weapons 11,
wheels 11 for car+van+bench together; salvage scrolls. Consistent with the state-2 counts in every
save (max seen: 2 engines, 3 suspensions, 4 brakes, 6 specials, 7 weapons, 6 wheels).

## 2. `savegame.dir`

```
u32 count
count x 60-byte records at 4 + 60k:
  +0  u32 scene      state 8 (saved in the garage): loads this scene
                     state 1 (saved after a mission): plays scene+1      [sandbox-verified 2026-10-01]
  +4  char[32] name  the typed bookmark name, buffer written verbatim (stale bytes after the NUL are normal)
  +36 char[16] file  "saveNNN" - the reader opens "%s.cmp" and silently DROPS a record whose file is missing
  +52 u32 state      1 or 8 (the exe game_state the shell was entered with)
  +56 u32 flags      0
size == 4 + 60*count, exactly.
```

Padding (the launchers' zero slack) is harmless: the reader stops at `count`. Shrinking is what to
avoid; the editors never do it. The `save-01.cmp` orphan is a shell bug reproduced from the code
(SAVE.md section 4: slot -1 after a second pass through the name field; Wine prints `-01`, Windows
`-001`); the stub's rescue copies the orphan onto the newest entry without a file.

## 3. Open - the probes in EDITOR-FIELD-TESTS.md answer these

1. colour thresholds (which third is which colour; is 100 % unmarked) - **CAL COLOR**
2. state 2 = van pane, state 4 = Field Salvage pane - **CAL V VS S**
3. bench cap - **CAL BENCH 15** (also the first in-game load of an editor-rebuilt section C)
4. four suspensions in the van - **CAL SUSP 4**
5. repaint via the vtf field - **CAL PAINT BLUE**
6. spc01 = Radar Jammer, any effect - **CAL JAMMER**
7. LOAD-board default label - **CAL LABEL 7 / 7+1**
8. meaning of PartRec +0x42 (11 on turrets), +0x68 (0..3), GarageRec +0x864 slot classes - no probe

## 4. Retired (2026-07 statements that were the frame offset)

- *"the game truncates the final inventory record at EOF"*, *"+84 inherited pointers"*, *"+96 cond /
  +100 loc"*, *"+104 mirrors the next record"*, *"corrupt NitrousOxide @9588 shifted 4 bytes"* - a
  name-first frame: the tail of record k was the head of record k+1 (or the section-C count).
- *"4 = FIELD SALVAGE, 2 = van-ish, 1 = car-ish; (C) rows are NOT loc-1 records"*, *"one (V) Stock
  suspension has no loc2 record"*, *"specials sit at loc 2/3/4 indiscriminately; their cond (15/41/
  100/300) means charges"* - every value was the next record's. Specials carry cond 0.
- *"first 116-byte train = van, later trains = repair"*, *"13/14 repair jobs, cap >= 14"* - section
  C is the queue; the trains were signature-scan artefacts.
- all **COLOR CAL / ALL PERFECT / TRUTH / TURRET** conclusions ("colours are render-time", "stored
  colour state not in the file", "salvage re-rolls") - each probe set cond on the record after the
  one it named. The five saves they produced (`saves/save008.cmp`, rescue `save004/006/007/008`)
  are the only files that fail the game invariants; they still round-trip and the editor's
  "Stow spares in van" re-sorts their states.
- `savegame.dir`: *"0x28 header, name at +0 / scene at +0x18 / name precedes its entry / 36 bytes
  short / last entry dropped unless padded / scene not recoverable / +16 = 1 or 8 unknown"* - the
  record starts at 4+60k; +52 is the entry state (1 post-mission, 8 garage); the "pad label vs dword"
  mismatch was the misread plus the state rule above.
- *"the game bumped save009's scene 6->7 without rewriting the cmp"* - a row click on the Save
  screen writes the current scene into that entry (SAVE.md section 4), not a bug.

## 5. Sample saves from the wild (research, 2026-07-14, unchanged)

- **"Lightfoot's I'76 Save Games"** - 14 campaign `.cmp` files (missions 2-15) from the defunct
  interstate76.com via the Wayback Machine (Nov 2007), in `game-data/downloads/lightfoot-saves/`;
  1.3-2.6 KB each, likely the pre-Gold format; no `savegame.dir`. Not yet parsed with the new frame.
- SavesForGames / TheTechGame sets skipped; GameFAQs, archive.org, VOGONS, GOG forums, ModDB hold
  none. No Nitro Riders / melee / non-Piranha saves exist publicly.
