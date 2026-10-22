# Graphics rebaseline for promotion 19 (2026-10-21, rebaseline lane)

Owner, 2026-10-21: "what are the defaults for all the graphics stuff like the draw distances and splits and stuff like that and how far
have we drifted? seems like maybe we could have gotten confused about what does what and have some changes that don't help? maybe we need
to rebaseline?" and "guide me through what you need from me now to finish the gold graphics settings and tuning".

The answer is a ladder. It starts from stock graphics and adds one change per rung, on the promotion-19 candidate's tick (41.667 ms) with
every non-graphics fix on. Each rung is measured and driven by the owner, who keeps or drops it. What he keeps becomes the final preset,
with the reason written next to every line.

**Status (2026-10-21 evening):** measured (s.4), driven by the owner (s.4), traced (s.6). Interim final values staged (s.5): R07's terrain at 1800 m, i.e. promotion 18's graphics; 2000 m after a soak.

## 1. Stock vs promotion 18 vs candidate vs final

| switch | what it does | stock | P18 PLAY.bat (best-wide) | P18 PLAY-balanced | RC as gated 2026-10-20 (tick19g) | candidate (exp-p19, tick19-42) | final |
|---|---|---|---|---|---|---|---|
| `I76_FAR_CLIP` | draw distance (the missions set 600) | 600 m | 1800 | 1200 | 1200 | 1800 | open |
| `I76_ROAD_DIST` | roads drawn | 450 m | 1800 | 1200 | 1200 | 1800 | open |
| `I76_CLUTTER_DIST` / `_FADE` | bushes | 120 m / - | 1800 / 300 | 1200 / 300 | 1200 / 300 | 1800 / 300 | open |
| `I76_TERRAIN_LOD` | sets A and B together (default for both) | x1 | 24 | 24 | 24 | 24 | open |
| `I76_TERRAIN_LOD_A` | terrain split distance (x) | x1 | (24) | (24) | **96** | (24) | open |
| `I76_TERRAIN_LOD_B` | terrain height-error threshold (/) | /1 | (/24) | (/24) | (/24) | **/4** | open |
| `I76_TERRAIN_HYST` | split / merge hysteresis | off | off | off | off | 20 % | open |
| `I76_TERRAIN_FREEZE` | far terrain keeps its first shape | off | off | off | off | 300,40 | open |
| `I76_TERRAIN_TEX` | terrain texture distance | x1 (256 px tile to 50 m) | 8 | 8 | 8 | 8 | open |
| `I76_OBJECT_LOD` | detailed object meshes kept farther | x1 | 8 | 8 | 8 | 8 | open |
| `I76_SHADOW_DIST` | shadows | x1 (50 m) | 4 | 4 | 4 | 4 | open |
| `I76_ROAD_TEX` | sharper road texture | x1 (60 m) | 8 | 8 | 8 | 8 | open |
| `I76_MIRROR_FAR` | rear mirror far clip | 100 m | 300 | 300 | 300 | 300 | open |

(Values in brackets come from `I76_TERRAIN_LOD`; the proxy uses LOD for A and B unless `_A` / `_B` is set.)

Where each value came from (the daily driver's PROMOTIONS.md):
- Promotion 2 (2026-10-03) made best-wide PLAY.bat with the detail set: far clip 1800, terrain x8, texture x8, objects x8, shadows x4, road
  texture x8, mirror 300. The texture, object, shadow, road-texture and mirror values have never been judged by eye (backlog G-04). COST.md
  (2026-10-05, t04) found no measurable cost for any of them in the cockpit.
- Promotion 13 added best-wide-balanced = far 1200.
- Promotion 16 set roads to 1800 / 1200 (owner-verified 2026-10-12).
- Promotion 17 set the bushes to the road distance (dense, fade 300) and terrain 8 -> 24.
- The release candidate's tick presets were generated from *balanced*, which is why its far clip is 1200 (RC-DRAW-FPS s.1). The LOD_A 96
  came from the lod-sweep lane.

**Drift found while building the ladder.** The candidate's terrain is **A x24 / B /4**, not "x24":
- `I76_TERRAIN_LOD 24` stays in the preset, and its comment still describes x24.
- `I76_TERRAIN_LOD_B 4` then overrides the height-error half of it.

So the candidate splits terrain as far out as promotion 18 does, but with a height-error threshold 6x larger. The brief's rung 4 adds
"threshold / 4 (LOD_B 4)" on top of the stock split distance (A x1). The ladder's R11 is therefore the candidate minus the split distance
x24. **R12 - R11 = `I76_TERRAIN_LOD 24` (split distance x24) and nothing else**: the env of every preset was diffed key by key (s.2). The
sanity rung became a measurement of the one switch the ladder does not otherwise isolate.

## 2. The ladder (lab copy `i76-uncap-lab\exp-rebase`)

`exp-rebase` is a copy of `exp-p19` (the candidate as applied; 94 / 94 files of its MD5SUMS verified after the copy). Proxy: the
candidate's 8f8da929. Base preset: the candidate's `tick19-42.psd1` (f7e589ef) with the 13 graphics keys removed (= stock). Every rung
otherwise runs the candidate's tick 41.667 and keeps every non-graphics fix on, including:
- cam-ground and hull fixes
- ZGLIDE TMU fix, Glide refresh 120, Hor+ 3440x1440
- cursor map
- breakable box, sign sound, fade
- LAN switches

Written by `i76-uncap-lab\tools\rebaseline\rungs.py`. Each `PLAY-Rnn.bat` opens a console window titled "I'76 ladder Rnn - <what it
adds>". The window stays open while the game runs and closes when it exits. Each `presets\rebase-rNN.psd1` carries the reason in a comment
on every graphics line.

| rung | launcher | adds (cumulative unless stated) | env diff to the rung before (checked) |
|---|---|---|---|
| R00 | PLAY-R00.bat | stock graphics: far clip 600, roads 450, bushes 120, terrain x1 / threshold /1, no hysteresis / freeze, textures / objects / shadows / road textures x1, mirror 100 | candidate minus 13 keys |
| R01 | PLAY-R01.bat | + far clip 1800 | FAR_CLIP 1800 |
| R02 | PLAY-R02.bat | + roads 1800 | ROAD_DIST 1800 |
| R03 | PLAY-R03.bat | + bushes 1800, fade 300 | CLUTTER_DIST 1800, CLUTTER_FADE 300 |
| R04 | PLAY-R04.bat | + terrain height-error threshold /4 | TERRAIN_LOD_B 4 |
| R05 | PLAY-R05.bat | + hysteresis 20 | TERRAIN_HYST 20 |
| R06 | PLAY-R06.bat | + freeze 300,40 | TERRAIN_FREEZE 300,40 |
| R07 | PLAY-R07.bat | R03 + the old x24 split (promotion 18's terrain) INSTEAD of R04-R06 | (vs R03) TERRAIN_LOD 24 |
| R08 | PLAY-R08.bat | R06 + terrain texture distance x8 | TERRAIN_TEX 8 |
| R09 | PLAY-R09.bat | + object detail x8 | OBJECT_LOD 8 |
| R10 | PLAY-R10.bat | + shadows x4, road texture x8 | SHADOW_DIST 4, ROAD_TEX 8 |
| R11 | PLAY-R11.bat | + mirror 300 | MIRROR_FAR 300 |
| R12 | PLAY-R12.bat | the candidate's own tick19-42, as is | (vs R11) TERRAIN_LOD 24, the split distance x24 (s.1) |

`PLAY-i76.ps1 -DryRun` exits 0 for all 13 presets.

## 3. How each rung is measured (`i76-uncap-lab\tools\rebaseline\rb-queue.ps1`, results under `captures\rebase-20261021\`)

Nothing boots before `.gate-done`. Every step does the following:
- It takes `.console-owner` and `.fps-lock` (exclusive create) and releases both after the step.
- It waits until no other game runs.
- A watchdog voids the step if another i76 / nitro runs beside it. If a game outside the lab starts, the watchdog stops the lane's own
  game at once, because route keys go to the foreground window.
- The step is void if an rdp-tcp session is Active before or after it. Up to 3 tries.
- Each boot sets `I76_MUTE=1`, starts a per-pid mute watcher and sets `I76_SHM_SUFFIX=exp-rebase`. The persisted mutes of
  `exp-rebase\Interstate 76\i76.exe` are cleared at the end.

The measurements:
- **fps, n 3, console:** `autotest\t05-route-fps.ps1` (gate row 9) through `PLAY-Rnn.bat`, with the folder's own 8f8da929. Rounds: R00 -> R12,
  then R12 -> R00, then R00 -> R12, so time drift falls on every rung. Columns: the hill leg's median, mean, 1 % low and lowest 1 s, the
  terrain vertex peak, and the ridge leg.
- **trip row, n 1, console:** `gate-folder.ps1 -Only 3 -TripRuns 1` through `PLAY-Rnn.bat`.
- **hill-top view, n 1, console:** `rb-hill.ps1`, which uses the same pose every rung: I76_START_POS 7972, 101.8, 44035, yaw -90, the car held
  by the trainer freeze, cockpit. It takes one 3440x1440 desktop capture 4 s after the hold and records the vertices and the far clip read back.
  The barn is 1747 m away.
- **churn census, n 3, headless (private desktop):** `rb-census.ps1`, the rc-draw lane's census on its lab twin `Strlkup-rcd2-lab` a944eb21.
  The twin is tick19g plus the same terrain switches, a drive block and the census. Its graphics code is identical to 8f8da929's: `git diff
  64d9361 5a7f83b -- music-fix` changes no far-clip / clutter / detail / terrain path except dc008e2 + 74fb9f4, which the twin carries. So
  the twin's churn numbers apply to the candidate, but its frame rate is not used.

## 4. The owner's drive (2026-10-21 ~18:00-18:45, at the console; verdicts relayed by main, his words condensed)

**How the columns were measured**
- Console, T05 route, hill leg (2.6 km over the hill top).
- Tool: autotest-p19 `t05-route-fps.ps1` (the p19 gate's key sender), through the rung's own launcher and 8f8da929.
- n 3, in three rounds: R00 -> R12, R12 -> R00, R00 -> R12. Each cell is the mean [min..max].
- Main's console anchors for the installed candidate: PLAY-TICK 120 / 91, ALT-TERRAIN 120 / 83, P18 control 120 / 98.
- The median is 120 on every rung (the 120 fps cap), so the 1 % low is the column that moves.
- Churn census: R00 only (n 1: 16.9 splits + merges per s, 12.8 % of frames, on-screen change 4,088 px/s within 300 m, 36 beyond). Main dropped the rest of the census in favour of the trace (s.6).
- Hill-top shots: `i76-uncap-lab\captures\rebase-20261021\hill\Rnn-hill-s1.png` (3440x1440, same pose).

| rung | launcher | what it adds | hill median / 1 % low fps | lowest 1 s | terrain verts peak | barn from the hill top | verdict | his note |
|---|---|---|---|---|---|---|---|---|
| R00 | PLAY-R00.bat | stock graphics | 120.0 / 97.4 [96.7..98.5] | 118 | 621 | no (far 600) | (baseline) | "slope redraws aggressively, near terrain too, less on flatter slopes" |
| R01 | PLAY-R01.bat | + far clip 1800 | 120.0 / 95.5 [94.7..96.5] | 119 | 4,556 | yes | (not driven separately) | |
| R02 | PLAY-R02.bat | + roads 1800 | 120.0 / 101.8 [101.2..102.4] | 119 | 4,556 | yes | | |
| R03 | PLAY-R03.bat | + bushes 1800 (fade 300) | 120.0 / 106.3 [106.0..106.7] | 118 | 4,557 | yes | keep (view) | "further, bushes visible, same slope redraws, almost exactly the same; terrain 1800 but objects / roads still closer" |
| R04 | PLAY-R04.bat | + terrain threshold /4 (LOD_B 4) | 120.0 / 105.8 [104.9..106.6] | 119 | 4,595 | yes | drop | "terrain changes exactly the same" |
| R05 | PLAY-R05.bat | + hysteresis 20 | 120.0 / 106.3 [106.0..106.8] | 118 | 4,506 | yes | (not reported) | |
| R06 | PLAY-R06.bat | + freeze 300,40 | 120.0 / 105.5 [105.3..105.9] | 119 | 4,506 | yes | drop | "no improvement in redraw stability at all" |
| R07 | PLAY-R07.bat | R03 + old x24 terrain (instead of R04-R06) | 120.1 / **86.3** [85.2..88.2] | 111 | **7,473** | yes | **keep** | "first one with any improvement; much improved, still minor shade changes in flat tiles, the bad canyon ones about the same" |
| R08 | PLAY-R08.bat | R06 + terrain textures x8 | 120.0 / 105.7 [105.7..105.7] | 118 | 4,506 | yes | (not reported) | |
| R09 | PLAY-R09.bat | + object detail x8 | 120.0 / 105.1 [104.7..105.8] | 118 | 4,506 | yes | (not reported) | |
| R10 | PLAY-R10.bat | + shadows x4 / road texture x8 | 120.0 / 104.3 [103.7..105.1] | 118 | 4,506 | yes | (not reported) | |
| R11 | PLAY-R11.bat | + mirror 300 | 120.0 / 103.4 [102.6..104.3] | 118 | 4,506 | yes | (not reported) | |
| R12 | PLAY-R12.bat | the candidate as is (= R11 + split distance x24) | 120.0 / **87.1** [76.1..92.7] | 100 [69..118] | **6,018** | yes | drop (terrain) | the RC: "maybe slightly better" than stock |
| R13 | PLAY-R13.bat | R03 + split distance x24 only (LOD_A 24) | 120.0 / 91.0 (n 1) | 111 | 5760 | yes | (added after the drive; one round, main) | |
| R14 | PLAY-R14.bat | R03 + threshold /24 only (LOD_B 24) | (queued) |  |  |  | (added after the drive; one round, main) | |

Main's extra rungs in exp-rebase (`PLAY-X1..X4.bat`, presets rebase-x1..x4, made by main, log-verified):

| rung | what | his note |
|---|---|---|
| X1 | R07 + LOD 48 | "further / better, the bad one still really bad". Console with the trace twin: 101 / 65, n 2. The trace itself costs about 3 fps on the median and about 12 on the 1 % low (traced R07: 117-118 / 72-76, untraced: 120 / 86) |
| X2 | R07 + HYST 20 + FREEZE 300,40 | "no improvement at all" |
| X3 | R07 + LOD_A 96 (split A x96, B x24) | "same behaviour, same fps at the hill top" |
| X4 | R07 + far / roads / bushes 2400 | "no stability issues, objects not further" |

What the table shows:
- **The terrain is the only expensive switch.** Every rung with split distance x24 costs about 20 on the 1 % low: R07 86, R12 87, R13 91,
  against 103-106 for the rest. The view switches (far 1800, roads, bushes) and the detail set (textures, objects, shadows, road
  textures, mirror) all land within ~3 of each other.
- **One unexplained step:** R00 -> R01 -> R03 rises from 97 to 106 while the vertex peak falls from 6.6k to 4.6k. Possible causes are the
  stock 600 m view hitting different hitches, or run order. Treat 95-106 as one band.
- **LOD_B 4, HYST and FREEZE are invisible to the owner** (R04, R06, X2). The trace (s.6) shows why: on this route no node flips back
  and forth, so these switches have nothing to damp.
- **Trip row 3**, run as the p19 gate ran it (autotest-p19 gate-folder + LAB_CURSOR_FREE): R00 FAIL 0, R01 FAIL 0, R02 FAIL 0, R03 FAIL 0, R04 FAIL 0, R05 FAIL 0, R06 FAIL 0, R07 FAIL 0, R08 FAIL 0, R09 FAIL 0, R10 FAIL 0, R11 FAIL 0, R12 FAIL 0, R13 PASS 120 (the last run per rung; fps from the trainer heartbeat). The first round's trip rows
  used the plain autotest gate-folder without LAB_CURSOR_FREE. The clicks missed and the game sat on the main menu, so engine up was 0 of 1
  on every rung. That was a harness fault, not a game fault. Saves were verified byte-identical after each run.

## 5. Final values (interim ship, main's ruling 2026-10-21 evening)

**R07's terrain at far clip 1800**, i.e. the candidate minus `I76_TERRAIN_LOD_B`, `I76_TERRAIN_HYST` and `I76_TERRAIN_FREEZE`. That is
promotion 18's PLAY.bat graphics (best-wide), now on the tick.
- **Far clip:** 1800 now, **2000 after a soak**. The owner ruled 2400 "fine but not needed"; main ships 2000 once it is soaked.
- **Staged, not installed:** `i76-uncap-lab\builds\rebaseline-20261021\stage\`. It holds the seven `tick19-NN.psd1` with the reason on
  every graphics line, plus `DIFF.txt` and `MD5SUMS.txt`.
- **Proxy:** stays 8f8da929.
- **ALT terrain:** `tick19alt-42` / `PLAY-TICK-ALT-TERRAIN.bat` (LOD 24 + FREEZE) are untouched. They are now nearly the same as the
  default; drop them from the installed set.

| key | final | reason |
|---|---|---|
| I76_FAR_CLIP | 1800 (2000 after a soak) | R01 draws the barn (1747 m) and the map edge from the hill top; owner: "further"; X4 at 2400 showed no stability issue |
| I76_ROAD_DIST | 1800 | roads drawn to the far clip (R03 note: at stock, "roads still closer") |
| I76_CLUTTER_DIST / _FADE | 1800 / 300 | owner: "bushes visible" (R03); promotion 17's dense variant |
| I76_TERRAIN_LOD | 24 (A x24, B /24) | R07, the only rung the owner called an improvement. Costs ~20 on the 1 % low (86 vs 106). LOD 48 and A 96 move the pops but do not remove them (s.6) |
| I76_TERRAIN_LOD_B | removed | R04: "exactly the same"; the RC with it was only "maybe slightly better" than stock |
| I76_TERRAIN_HYST | removed | R05 / X2: no improvement; nothing flips back and forth (s.6) |
| I76_TERRAIN_FREEZE | removed | R06 / X2: no improvement |
| I76_TERRAIN_TEX / OBJECT_LOD | 8 / 8 | in since promotion 2; R08 / R09 within noise; not judged in this drive |
| I76_SHADOW_DIST / ROAD_TEX | 4 / 8 | in since promotion 2; R10 within noise; not judged in this drive |
| I76_MIRROR_FAR | 300 | in since promotion 2; R11 within noise; not judged in this drive |

The owner drove R07 without the detail set (R07 = R03 + LOD 24). The staged set is R07 plus the detail set. That exact combination was
not driven as a rung, but each detail switch measured within noise (R08-R11).

Staged MD5SUMS (`builds\rebaseline-20261021\stage\MD5SUMS.txt`):

```
df370e446e731f228f76f5821ff93e89  DIFF.txt
70ae169bca0831ad99c18c2507e48997  Interstate 76\presets\tick19-33.psd1
a2416eea47bcaf32dd7a373f3a782f28  Interstate 76\presets\tick19-36.psd1
97ad230e3a22fe7e87c810896262ef8a  Interstate 76\presets\tick19-39.psd1
29cef1b3ceb7aa86f9919724878fbd78  Interstate 76\presets\tick19-42.psd1
739a1470efe0a3a88d0a4a4ec4ef1ab6  Interstate 76\presets\tick19-44.psd1
170cd8e47e7de04e52a54f59d4534d3c  Interstate 76\presets\tick19-47.psd1
85e7cf2cbd61b6d319d51d491afa3332  Interstate 76\presets\tick19-66.psd1
```

**Stock vs promotion 18 vs candidate vs final (graphics only):**

| key | stock | P18 PLAY.bat | P18 balanced | candidate | final |
|---|---|---|---|---|---|
| far clip / roads / bushes | 600 / 450 / 120 | 1800 / 1800 / 1800 | 1200 / 1200 / 1200 | 1800 / 1800 / 1800 | 1800 / 1800 / 1800 (2000 after a soak) |
| bush fade | - | 300 | 300 | 300 | 300 |
| terrain split A / threshold B | x1 / /1 | x24 / /24 | x24 / /24 | x24 / **/4** | x24 / /24 |
| hysteresis / freeze | off / off | off / off | off / off | **20 / 300,40** | off / off |
| textures / objects / shadows / road tex / mirror | 1 / 1 / 1 / 1 / 100 | 8 / 8 / 4 / 8 / 300 | same | same | same |

The graphics drift since promotion 18 was three switches: LOD_B 4, HYST and FREEZE. Measured and driven, none of them gave anything
visible, so the final set returns to promotion 18's graphics.

## 6. What the snap is: a per-node trace (main's direction after the drive)

### The instrument

**Build.** The lab twin is `builds\rebaseline-20261021\trace\trace\Strlkup.dll` (dfa47d12).
- `tools\rebaseline\trace\build-trace.sh` builds it from a `git archive 5a7f83b` of music-fix plus `insert-trace.py`.
- The same script's plain build reproduces 8f8da929 byte for byte.
- Source diff: `tools\rebaseline\trace\results\trace-v2.patch`.

**Hook.** `I76_TERRAIN_TRACE=<file>` hooks the node test at 0x4912f6 through the hysteresis code's stub. With the trace alone, the stock
tests run unchanged.

**What it computes.** For every visited node of half size 1..16 samples (10..160 m tiles), the trace computes the stock decision itself,
at this pass's eye (disassembly in `tools\rebaseline\trace\qt-4911e0.asm`):
- **F** (leaf): d2 > (2h)^2 A
- **N** (forced split): 2 d2 < (2h)^2 A
- **E** (in between): the midpoint height error x 2h is compared with T = floor_pow2(d2) x B, using raw heights from 0x493160. The
  stock's last tile-flag check (0x49155a) is not replicated.

**What it logs.** After each main-camera pass: every node whose decision changed, with the previous and current band, the exponent of
d2, and the guard's refusals in that pass.

**v1 vs v2.** The first version (v1) inferred "split" from a visited child, so children entering or leaving the frustum read as flips
(63 % of its flips). v2 computes the decision directly and does not depend on the frustum.

**Runs.** Console, T05 route, n 2 each, in the lab copy `exp-rebase-trace`: presets rebase-t07 (= R07) and rebase-tx1 (= X1).
- Decision logs: `tools\rebaseline\trace\results\*.v2.csv.gz`.
- Classification: `results\kinds.txt`, from `trace_kinds.py` and `trace_view.py`.

### Result (R07, n 2; the two runs agree within 0.3 %)

| why the node's decision changed | share | distance by tile size 10 / 20 / 40 / 80 / 160 m |
|---|---|---|
| ring F -> E: the split-distance ring. Steep ground splits as soon as it is eligible, because its error is already over the threshold | 30.7 % | 183 / 366 / 732 / 1464 / 2928 m (= 18.3 x size = (2h) sqrt(A)) |
| ring E -> N: the forced-split ring. Every tile, flat ones too | 58.7 % | 129 / 259 / 518 / 1035 / 2070 m (= 12.9 x size = (2h) sqrt(A/2)) |
| err-step: same E band, d2 crossed a power of two, so T halved | 7.1 % | 160 / 320 / 640 / 1280 / 2560 m |
| merges (E->F, N->E, err-step M): the eye moving away or turning | 4.1 % | |
| vertex guard refusals | **0** | vertex peak 7,458 / 7,452 (limit 28,000) |

- **No flip-flop.** In the view centre on the hill leg (±15°) there were 615 flips over 615 different nodes: every node changed once,
  none twice. Hysteresis and freeze therefore have nothing to act on.
- **X1 (LOD 48, n 2): every ring moves by x1.41.** 183 -> 259 m, 129 -> 183 m, err-steps 160 -> 226 m. The mix of reasons stays the
  same (9,162 / 9,153 flips; guard 0; vertex peak 9,609).

### What the owner sees

- **Each pop is one quadtree level replacing a tile by four.** The stock renderer does not blend, so the shape jumps in one frame, and so
  does the Gouraud shading on the new vertices.
- **There is always a pop somewhere.** The rings are 2x apart in distance, one per tile size, so at any distance some tile size is
  crossing its ring.
- **Why LOD 48 and A 96 did not fix it.** Scaling A changes which tile size pops at a given distance, and makes each pop smaller on
  screen. It cannot remove the pops. That matches his X1 note: "further / better, the bad one still really bad".
- **Steep canyon faces** carry large height errors even at 10 m tiles, so their pops are big at any ring.
- **Flat tiles** pop only at the forced ring (12.9 x size), with a small shading change. That is his "minor shade changes in flat tiles".

### Inference and open points

- **LOD_B 4 (inference; the candidate was not traced).** A 6x larger threshold leaves more steep tiles coarse past the F -> E ring,
  until the closer forced ring. Larger tiles then pop nearer, which fits the owner calling the candidate barely better than stock.
- **Not identified: the exact patch in his screenshots** (`Downloads\Screenshot 2026-10-21 1758*.png`). He drove off the road and the
  screenshots carry no pose. A trainer pose snapshot at the spot would let the trace isolate that node.
- **Remedy: geomorphing**, i.e. blending new vertices across the ring (RC-DRAW s.7). It applies to both rings. Main briefed a geomorph
  lane (exp-morph) that reads these files.

## 7. Status and files

- **Lab copies** (both retired with this record):
  - `exp-rebase`: the ladder, proxy 8f8da929; PLAY-R00..R14, and PLAY-X1..X4 by main.
  - `exp-rebase-trace`: the trace twin dfa47d12; PLAY-T07 / PLAY-TX1.
- **Scripts:** `i76-uncap-lab\tools\rebaseline\` (rungs.py, rb-queue.ps1, rb-hill.ps1, rb-census.ps1, rb_tab.py, stage.py, trace\).
- **Raw data:** `i76-uncap-lab\captures\rebase-20261021\` (fps\Rnn, hill, trace, census\R00, queue.log). Voided runs are under `*\void`.
- **Harness lessons:**
  - The committed `autotest\t05-route-fps.ps1` key sender drove only 103 m at the console. The lane uses autotest-p19's copy, and any
    hill leg under 2,000 m voids the run.
  - Stopping the queue mid-step once left the global dgVoodoo.conf hidden by gate-folder. It was restored, and the saves were verified.
