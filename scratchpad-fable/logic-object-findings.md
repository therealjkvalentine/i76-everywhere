# Vehicle-logic object dissection (read-only, live, 2026-07-18)

Walked the parallel session's chain live: player_entity = [[[0x54a264]]+0x70] = 0x025b1948 (this run).
NEW: player_entity **+0x10c holds a pointer to the VEHICLE-LOGIC object** = 0x020e24d0 (this run;
heap, re-resolve each run). This is the "different root" the addresses.json note wanted pinned.

## Logic-object structure (0x020e24d0)
- **Component records: array of 16 at STRIDE 0x90 (=144 decimal), starting ~+0x40.**
  The note's "N*0x144" looks like a units mixup — the real stride is 0x90 (144 dec), not 0x144 (324).
  Each 0x90 record carries a durability=100 field (at +0x40, +0xd0, +0x160, ... every 0x90) and a
  "50"/"1" pair (condition / grade), matching the save editor's dur/cond/grade columns.
- **Ammo / fired candidates** (need the CURRENT HUD values to lock): +0x2b0=3173, +0x580=4273,
  +0x2a0.. ; and **fired-counters = 18** at +0x588, +0x6b8, +0x748, +0x858, +0x868 (these are the
  same "0->18" counters seen during the fire differential — model is max minus fired).

## Precise finish (two options)
1. TARGETED micro-differential (no debugger, uses the captures): snapshot these logic-object
   offsets, fire a KNOWN burst, re-read — the field that moves by the fired amount is ammo/fired.
   Fast + exact because it's ~16 offsets, not the whole heap.
2. winedbg watch (tools/i76-findwrites.sh) on e.g. logic+0x588 while firing -> the writing
   instruction names the field and gives the base register/offset. Needs a mission-loaded debug
   instance (display contention with the live game) -> coordinate a paused moment or a cloned prefix.
