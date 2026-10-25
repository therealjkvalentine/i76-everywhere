# Mac graphics tune 2026-10-24: how much of the PC graphics advantage fits in 60 fps on each Mac

Question (owner): "get as much of the graphic advantage as we can and still keep 60 fps" on EACH Mac. Test lane, scripted, n 1 per row.
Follows MAC-GRAPHICS-2026-10-24.md. Raw data (per run: mciproxy.log + per-frame CSV) and scripts: lab
`captures\mac-graphics-tune-20261024\` (macbook-m5pro, andrew-m2, michael-m4max-contaminated; gfx1.sh = runner, tab.py = table, ph*.sh = row lists).

## Method

- Per Mac a silent clone "I76 GFX LAB.app" (tools/mac-test-clone.sh, null audio, movies skipped) of that Mac's own app, proxy **53944fb2**. Shipped apps untouched.
  The boys' clones live in a NEW folder `~/i76-gfx-lab/` on each (clone + scripts + out/); no sudo; nothing else touched. Both were idle (HID idle > 5 min, no
  i76/wine) at every launch. `caffeinate -d` (mine) held the display awake during runs; stopped afterwards.
- Each row: `open -n --env I76_MISSION=t05 --env I76_SKIP_MOVIES=1 --env I76_FRAME_LOG=C:\frames.csv --env <keys>`, stationary at the t05 start, per-frame CSV from the proxy,
  first 5 s dropped, next 60 s used. median = median of 1-second bins; 1 % low = 1000 / (99th percentile frame period). Every row booted t05, 0 CRASH, coop-ai 27/27
  (SKY_MIRROR=0 left out of every row, for the 25/27 reason in the previous record; M16_SKY=0 kept).
- "free set" (base) = the pack keys in each prefix + morph / smooth-shade (S), mirror (M), sparse-bush (C) keys. Stock = far clip 600 m (mission value), road 450 m,
  bushes 120 m, terrain LOD 1, detail 1. Distance rows move FAR_CLIP, ROAD_DIST, CLUTTER_DIST together unless named "only".
- Pass (brief) = median >= 57 AND 1 % low >= 45. **The base itself cannot meet the 1 % low half**: on the MacBook it reads 40.0-45.2 in three runs, because
  I76_FIXED_STEP 24 makes every other frame run a physics step (max frame period 33 ms in nearly all rows). So the 1 % low is read RELATIVE to the base (about 40 on the
  MacBook, 32-38 on the M2); the deciding number is the median plus "1 % low not worse than base".
- Spread: base repeated on the MacBook (68.9 / 60.0 / 64.0 median, lows 45.2 / 40.5 / 40.0); on the M2 (49.6 / 49.3 free set, 52.6 / 52.0 pack only). Median 60.0 is the
  display lock; the mean shows excursions above it. Differences under about 5 fps in the median are noise at n 1-3.
- Not measured: driving (all rows stand still), fog / fog alpha by eye, pictures. **screencapture still fails** over SSH on the MacBook ("could not create image from display";
  the grant did not reach the SSH parent). I did not retry osascript (a hung prompt would sit on the owner's screen).

## MacBook Pro (Mac17,8, Apple M5 Pro, 64 GB; viewport 1512x977, MSAA 4)

| row | keys added to the free base | median | mean | 1 % low | verdict |
|---|---|---|---|---|---|
| free base (3 runs) | - | 68.9 / 60.0 / 64.0 | 71.0 / 61.8 / 66.6 | 45.2 / 40.5 / 40.0 | reference |
| road 900 / 1500 / 1800 | ROAD_DIST | 60.0 / 60.2 / 62.0 | 61.4 / 68.2 / 66.8 | 40.0 / 41.0 / 45.7 | free |
| far clip only 900 / 1000 / 1200 | FAR_CLIP | 60.0 / 60.0 / 53.9 | 61.4 / 60.3 / 55.6 | 40.4 / 39.8 / 35.3 | free to 1000, 1200 costs |
| far+road+clutter 600 / 900 / 1200 / 1500 / 1800 | all three | 59.9 / 46.3 / 35.8 / 30.5 / 27.2 | 59.2 / 46.6 / 36.8 / 30.4 / 27.5 | 38.9 / 32.8 / 27.2 / 24.0 / 21.3 | **1800 = 27 fps, fails**; 2000-2200 not run (previous record: 2300 -> 21) |
| clutter dist 600 / 1200 only | CLUTTER_DIST | 59.3 / 57.2 | 58.5 / 56.5 | 36.0 / 35.1 | small cost, lows drop |
| detail x2 (TERRAIN_TEX, OBJECT_LOD, SHADOW_DIST, ROAD_TEX = 2) | | 70.0 | 70.4 | 45.6 | free |
| detail x4 | | 64.2 | 65.2 | 38.9 | free |
| detail x8 (TEX 8, OBJ 8, SHADOW 4, ROAD_TEX 8) | | 68.6 | 67.4 | 44.5 | **free** (the old "x8 -> 37 fps" was TERRAIN_LOD 24, not the detail keys) |
| terrain LOD 2 / 4 / 8 / 16 / 24 (FAR_CLIP 600) | TERRAIN_LOD | 60.0 / 59.9 / 46.5 / 41.3 / 37.5 | 63.4 / 60.9 / 49.2 / 45.7 / 40.3 | 39.5 / 40.6 / 34.3 / 31.7 / 29.4 | free to 4; **24 = 37 fps** |
| x8 + road 1800 (pA) | | 60.0 | 63.9 | 41.2 | **pick** (n 1; the repeat was cut when the coordinator asked for the MacBook back) |
| x8 + far 1000 (pB) | | 60.0 | 58.7 | 35.3 | ok, lows worse |
| road 1800 + far 1000 (pC) | | 51.4 | 52.4 | 32.5 | fails: the pieces add up |
| x8 + road 1800 + far 1000 (cD) | | 53.1 | 52.4 | 31.6 | fails |
| x8 + road 1800 + far 800 + LOD 4 (cF) | | 51.6 | 53.0 | 36.0 | fails |
| x8 + road 1800 + far 1000 + LOD 4 (cB) | | 45.5 | 45.7 | 32.9 | fails |
| cB + clutter 600 (cC) | | 38.8 | 38.8 | 29.9 | fails |
| x8 + road 1500 + clutter 600 + far 900 (comboA) | | 48.0 | 48.2 | 34.9 | fails |
| x8 + road 1800 + far 600 + LOD 4 (pD) | | 49.5 | 51.7 | 32.5 | fails |

Reading: detail x8, road 1800, far clip 1000 and LOD 4 are each about free alone; together they are not (two or three distance / geometry keys already drop the median to 50-53).
The MacBook has roughly one such step of headroom. **Recommended local.psd1 for this MacBook:** detail x8 + ROAD_DIST 1800, the rest stock:

    I76_FAR_CLIP='' I76_CLUTTER_DIST='' I76_TERRAIN_LOD=''   (removed = stock)
    I76_ROAD_DIST='1800'
    I76_TERRAIN_TEX='8' I76_OBJECT_LOD='8' I76_SHADOW_DIST='4' I76_ROAD_TEX='8'
    fog keys '' ; morph / smooth / mirror / bush-density keys as in presets\graphics-mac.psd1 minus SKY_MIRROR=0

Alternative if the owner prefers far terrain to far roads: FAR_CLIP=1000 instead of ROAD_DIST (pB: same median, worse lows). Untried middle: x8 + road 1500 + far 900.

## MacBook Pro (Mac16,6, Apple M4 Max, 36 GB; viewport 1512x977) (Michael): NOT MEASURED, data discarded

Idle at the start with no i76/wine, but **Minecraft (java, 4 GB, 5 h uptime) is open on his Mac** and macOS `mediaanalysisd` ran at ~120 % CPU during my runs (seen only after 5 rows).
The rows are visibly disturbed: fps falling steadily 48 -> 25 within a run, a 7.4 s stall, two boots that never reached the mission (f600, f1500 NODATA). Partial rows are kept in
`michael-m4max-contaminated`, NOT used (900 m all three 35.8 with a 7 s stall; 1200 m 26.4). I stopped my runs, killed only my own processes (my clone, my caffeinate), left Minecraft alone.
His disk is 99 % full (14 GB free; the clone is an APFS clone, a few hundred MB written).
**Needs a quiet moment (Minecraft closed, about 25 min); the clone and scripts are in place in `~/i76-gfx-lab/` on his Mac.** Provisional, NOT measured: use the safe baseline below.

## MacBook Pro (Mac14,7, Apple M2, 8 GB; viewport 1440x900, MSAA 4) (Andrew)

| row | keys | median | mean | 1 % low | verdict |
|---|---|---|---|---|---|
| pack keys only (2 runs) | - | 52.6 / 52.0 | 54.2 / 54.5 | 37.8 / 37.5 | **below 57 with nothing added** |
| + morph + smooth (S) | | 52.8 | 55.3 | 37.3 | free |
| S + mirror (SM) | | 49.8 | 52.7 | 32.2 | mirror costs ~3 |
| free set S+M+C (2 runs) | | 49.6 / 49.3 | 51.6 / 51.4 | 32.1 / 32.8 | base for the rows below |
| detail x2 / x4 / x8 | | 48.8 / 49.4 / 48.4 | 49.1 / 48.8 / 49.1 | 29.8 / 29.4 / 29.7 | ~free (-1) |
| S + x4 (no mirror) | | 51.3 | 50.6 | 35.0 | |
| S + x4 + road 900 | | 49.7 | 50.3 | 35.2 | |
| road 900 / 1800 | | 48.3 / 48.0 | 50.7 / 50.8 | 30.9 / 31.0 | ~free (-1.5) |
| far clip only 900 / 1200 | | 45.2 / 36.5 | 46.7 / 39.1 | 30.1 / 26.3 | costs |
| far+road+clutter 600 / 900 / 1200 / 1800 | | 37.9 / 30.2 / 22.9 / 17.4 | 38.5 / 30.7 / 23.6 / 17.4 | 25.9 / 21.6 / 17.2 / 13.5 | fails |
| clutter dist 600 only | | 39.5 | 40.2 | 25.5 | **costs ~10** |
| terrain LOD 8 / 16 / 24 (FAR_CLIP 600) | | 33.7 / 27.4 / 23.8 | 36.2 / 30.1 / 26.4 | 26.1 / 21.9 / 19.4 | fails |

No setting reaches the pass line on this M2, including the bare pack (about 52). Boot flake: 3 of about 16 attempts on the boys' Macs never reached the mission (rerun fine).
**Recommended local.psd1 for the M2:** stock distances; `I76_TERRAIN_MORPH*` + `I76_SHADE_SMOOTH`, detail x2; no mirror set, no bush distance, no LOD, no far clip.

## Baseline "graphics-mac" (safe on the slowest = the M2)

- **presets\graphics-mac.psd1 as committed must change**: its 1800 m distances + LOD 24 measured 27 fps (M5 Pro) and 17 fps (M2) for the distances alone, LOD 24 another -22 / -26.
- Distances stock: remove `I76_FAR_CLIP`, `I76_ROAD_DIST`, `I76_CLUTTER_DIST`, `I76_TERRAIN_LOD` (set '' in the preset).
- Keep: `I76_TERRAIN_MORPH=0.25`, `_STATELESS=1`, `_SHADE=3`, `_NEAR=100`, `I76_SHADE_SMOOTH=1`; detail `I76_TERRAIN_TEX / OBJECT_LOD / ROAD_TEX / SHADOW_DIST = 2` (about free on both).
- Drop from the Mac tier: the mirror set (-3 on the M2, free on the M5 Pro), bush keys (bush distance -10 on the M2), fog keys, `I76_SKY_MIRROR=0` (costs two coop-ai sites).
- Per-machine on top: MacBook M5 Pro = x8 + road 1800 (+ mirror set); M2 = baseline as is; M4 Max pending.

## Caveats

- n 1 per row (n 2-3 for base rows); noise about +-5 fps in the median; play the pick once by eye. No pictures.
- Stationary at the t05 start; driving through dense terrain or the binoculars costs more, so the far-clip rows are optimistic.
- Cleanup: the MacBook clone `~/Applications/Sikarugir/I76 GFX LAB.app` and `~/i76-gfx-lab/` remain (nothing of mine running there); the boys' clones are in their own `~/i76-gfx-lab/`.
