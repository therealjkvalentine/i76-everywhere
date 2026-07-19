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

## Update: relocation confirmed + chain differential working (2026-07-18)
- **The structs RELOCATE**: player_entity moved 0x025b1948 -> 0x02401948, logic
  0x020e24d0 -> 0x020e1348 between reads. The chain [[[0x54a264]]+0x70]+0x10c
  re-resolves correctly every time. THIS is why all cross-dump/absolute-address
  differentials failed and why the chain approach wins. Diff OFFSETS, not addrs.
- **tools/i76-chaindiff.ahk / chaindiff.sh**: snap (640 logic offsets) then diff,
  both through the chain -> relocation-proof field finder. VERIFIED it catches
  live changes.
- Uncontrolled 2-min diff showed real movement: +0x108 98->32 (-66, ammo/damage
  candidate); per-record field at record+0x48 (786450->18, looks 16-bit); plus
  many physics floats (noise). Precise attribution needs a CONTROLLED action.
- **Component record layout (stride 0x90 from logic+0x40)**: +0x40 int dur(100),
  +0xac float dur(100.0), +0x48 a counter/id, +0xc4 =50 (cond?). 16 records.

## Debugger status (final)
- attach-to-running = macOS error 5 (denied).
- launch-under-winedbg = sets breakpoints + reads 32-bit regs, but the game
  CRASHES on cont (c0000005) when run outside its DxWnd launch context. Full
  find-what-writes would need winedbg to follow the dxwnd->i76 child chain, or a
  cloned prefix launched debugger-first. Deferred; the chain differential makes
  it unnecessary for field-mapping.

## THE FINISH (one controlled action)
snap -> fire EXACTLY N rounds of ONE weapon -> diff. The offset that moved by
-N (or a counter +N) is that weapon's ammo. Repeat for armor (take a hit) and
speed (accelerate). tools/chaindiff.sh drives it.
