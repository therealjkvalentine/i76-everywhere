# Reverse-engineering I'76 live memory — resources & method

Curated reading for finding/confirming dynamic game values (ammo, armor, gear,
speed, target) the right way, plus how each applies to OUR setup (i76.exe under
Wine on macOS). Gathered 2026-07-18.

## The core reading list

| Resource | Teaches | Our use |
|---|---|---|
| [CE: Find what writes/accesses this address](https://wiki.cheatengine.org/index.php?title=Help_File%3AFind_out_what_writes%2Faccesses_this_address) | Data breakpoint → the instruction that writes a value; register/base at write time | The airtight display-vs-internal test; gives the struct base register |
| [CE health tutorial](https://wiki.cheatengine.org/index.php?title=Tutorials%3ACreate_cheat_table_full%3Ahealth) | Unknown-initial-value + decreased/increased/unchanged successive scans; freeze-one-at-a-time | Find live ammo/armor with NO encoding assumption |
| [CE: Dissect data/structures](https://wiki.cheatengine.org/index.php?title=Help_File:Dissect_data/structures) | Map a struct from a base; compare two entities (player vs enemy) to label fields | We already have the offsets statically — this confirms them live |
| [GuidedHacking: pointer scanning / multilevel pointers](https://guidedhacking.com/threads/cheat-engine-how-to-pointer-scan-with-pointermaps.9739/) | Green=static; base+offset chain that survives relaunch | Turn a live vehicle address into a relaunch-proof static→offset map |
| [Lonami: Writing our own Cheat Engine (series)](https://lonami.dev/blog/woce-1/) | Implementing scan/first-scan/next-scan/pointer-scan yourself | Basis for our own tools/i76-mem-scan.py + trainer scanner |
| [winedbg man page](https://linux.die.net/man/1/winedbg) + [CodeWeavers: debugging Wine with x86 debug registers](https://www.codeweavers.com/blog/aeikum/2022/6/3/debugging-wine-with-x86-hardware-debug-registers) | `watch` (on write/read) at an address; hardware debug registers under Wine | **find-what-writes IS possible on our Mac Wine** — the technique I'd wrongly ruled out |

## The two realizations that change our approach

### 1. find-what-writes works on Mac Wine (winedbg `watch`)
winedbg supports `watch` on write at an address (4 bytes). Our slim Wine bundle
has no `winedbg` binary, but a full Wine (or building winedbg) gives us the
single most reliable technique — set a write-watch on a live value, and the
instruction that fires names the field and hands us the struct base register.
This is how you conclusively separate the authoritative value from its HUD copy.

### 2. HYBRID beats blind scanning — we already own the struct map
Our static disassembly already reversed the vehicle layout:
- component list: `vehicle+0x3c` count, `vehicle+0x40` array (stride 0x20, type@+0)
- weapons: `vehicle+0xa71c` ptrs, `vehicle+0xa738` records (stride 0x20)
So we don't need to blind-scan for each value — we need ONE thing: the live
**vehicle base pointer**, then base+offset gives everything, relocation-proof.

The player→vehicle lookup (`0x4547c0`) revealed a player table at `0x541070`
(stride 0x48, id@+0, **vehicle ptr @+0x28**, array base 0x541098). That table is
the DirectPlay/multiplayer one — empty in single-player (all 16 slots 0 live).
The single-player local-vehicle global is a different static — found the same
way: locate a fn that reads the player car (HUD ammo draw, or the callers of
weapon_info_in_car 0x409e40), read the global it loads.

## The recommended workflow to finish the live map
1. **Get the base once.** Either (a) winedbg `watch` on a known live value
   (e.g. camera 0x4c2964) or the capacity table (0x25b0728) → the writing/
   reading instruction reveals the vehicle base register + the static global it
   came from; or (b) static: disassemble the HUD-ammo draw / weapon_info callers
   to find the single-player local-vehicle global.
2. **Deref + dissect.** base = [global]; then walk base+0x40 (components) and
   base+0xa738 (weapons) using CE's dissect view (or our reader) and match the
   fields to the HUD — armor facets, per-weapon ammo, condition.
3. **Confirm each** via freeze (changes gameplay, not just the dial) and, where
   it matters, winedbg find-what-writes.
4. **Record** the static global + offsets into tools/i76-addresses.json — that
   map survives relaunch (unlike raw heap addresses).

## Why our headless dump-diff stalled (for the record)
Dynamic values live in a struct that RE-ALLOCATES between our minutes-apart
dumps, so cross-dump VA matching fails for every encoding (int/float/double/
scaled/counter — all ruled out for 7.62T 3739→3721). CE avoids this with rapid
successive scans in one attached session; the pointer-chain approach avoids it
entirely by anchoring to a static global. Both beat re-dumping.
