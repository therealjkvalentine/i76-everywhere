# Whole-sim tick, finished and tested against promotion 18 (2026-10-18, overnight)

The owner's question (2026-10-17): "where did we leave our two tick engine fix attempt? ... get me a finished version
tested of that overnight as well and say if it's better or worse."

Earlier records: [WHOLE-SIM-TICK-2026-10-17.md](WHOLE-SIM-TICK-2026-10-17.md) (the tick),
[TICK-LATENCY-AND-AI-FIRE-2026-10-17.md](TICK-LATENCY-AND-AI-FIRE-2026-10-17.md) (the early tick on input; completed
today: s.1.5 physics rows, s.2 AI fire), [SAME-CAR-FINGERPRINT-2026-10-17.md](SAME-CAR-FINGERPRINT-2026-10-17.md). Lab
only. The daily driver, the golden copy and the Downloads portable were only read (the promotion-18 presets and md5s).
Nothing was promoted.

## Verdict

**Update 2026-10-21 (s.20): the T05 jump per tick, against retail 1.0 at the same frame time and promotion 18. 41.667 ms jumps as 1997 did at ~42 ms (crest descents, the emulator car: take-off 49.9 vs retail 50.0 m/s, apex 10.0 vs 10.0 m, 10 of 10 vs 6 of 6 clear); 33.3 ms jumps 2.5 m/s slower and clears 4 of 7. The cause is one per-substep term, the slope-follow speed loss (the ground projection in 0x43a5d0); scaled to the 41.667 ms rate under the tick (I76_SIM_TICK_SLOPE, new default, exactly 1 = not installed at 41.667) 33.3 ms jumps as 41.667 (50.5 m/s, 6 of 6). 44 "made it" because a longer step loses less on the ramp face; at 41.667 there is nothing for it to compensate. Candidate staged, not installed: lab builds\jump-fix-20261020 (ed772c2).**

**Update 2026-10-20 (s.19): the tick range. 1997 ran its car step at the PC's frame time, 35.5-48 ms on the period machines we measured, and never one step at 50 ms or more; launchers PLAY-TICK-36 / -39 / -42 / -44 / -47 (+ the outliers -33 / -66) in game-tick on the new STRLKUP-tick19g adc4fd49 (main 64d9361: + the rate-aware flame factor, so tick19-42 drops its interim 3.5 line). Measured per tick (n 24 jumps, bounce, flame n 2, keys n 40): the bounce tempo is 7 car steps at every tick (0.252 / 0.273 / 0.292 / 0.308 / 0.328 s), the jump rises slightly with the tick (paired take-off -0.56 .. +0.46 m/s across 36-47, inside retail's spread), flame ~85 / s and key response ~5 ms at every tick; 41.667 is the value that matches 1997 everywhere. User override, not in the menus: `PLAY-TICK.bat <ms>` / `tick-ms.txt` / `PLAY-TICK-CHOOSE.bat` (16.7-66.7 ms, else refused), tested headless by the proxy's own tick line. No console gate on tick19g yet.**

**Update 2026-10-19 evening (s.17): new candidate STRLKUP-tick19f-av 2eb345d1 (main d664f91: tick19e + the instant-melee fix + the owner's tick19e playtest fixes + the driver's wide menu ('aw') + terrain A 96 / B 24), GATED: PLAY-TICK all rows pass (row 4 after a gate-harness fix: its clicks assumed the 4:3 picture), PLAY-TICK-42 8 / 0, PLAY-TICK-66 8 / 0, control 6 / 0, instant-melee rows 3 / 3. Under the tick, each with its own switch: sign posts knocked off by the sweep play their hit sound (0 -> 33 of 33), no camera stutter when a key is pressed in an outside cutscene (19 of 44 -> 0 of 24 stutter frames at an early tick), the death camera and the sky at the 1997 rate (240 -> 192 deg / s and 0.030 -> 0.024 / s, 1997 192 / 0.024; the driver 160 / 0.020). Music: no dropped cue (12 boots; the silences are the data-track missions and the retail run-end gap). Tracers: no double drawing; the tick's every-frame streak is a look difference. Installed in game-tick with PLAY-TICK-33 / -42 / -66; the LAN AI arena under the wide menu was not tested. s.18 (ed5c305) is not in this build.**

**Update 2026-10-19 (s.14): new candidate STRLKUP-tick19e a08577c4, GATED 21 / 0 / 2, 8 / 0, 6 / 0 (this covers tick19d too). Under the tick, four per-pass systems now run at the 1997 rate per second, each with its own switch (I76_SIM_TICK_{HAZARD,SCRAPE,WRECK,RADAR}_FACTOR). Measured, n 3 per arm: dropper / oil contact per round 120.5 /s at 1997 against tick33 150.5 -> 120.4 and tick66 75.5 -> 120.9; the wreck blast roll 24.1 /s against 30.1 -> 23.1 / 23.9. The sustained-scrape scaling is verified per application but its rate was not resolved. The radar-missile turn is from the code only. The flame outliers are stock: the flame kill roll on a destroyed component, plus a health-lost measure that books the wreck. T06 strip 54 / 54 unchanged.**

**Update 2026-10-19 (s.12): new candidate STRLKUP-tick19d 88970903, NOT gated yet (the owner was at the PC; headless only). Flame damage under the tick is x 2.8 by default (I76_SIM_TICK_FLAME_DMG): a T05 car burns to death 10.9 s after first contact under tick33 and tick66, 1997 20 fps 11.2 s (s.11's "~25 / ~40 s" were mission times; n 6 / 6). The T05 bars burn again with I76_BREAKABLE_BOX=4 (I76_BREAKABLE_BOX_FLAME, default on: the flame sees the bars' stock sphere; 94 % of tests, rams 19 / 30 vs 20 / 30, signs unchanged): the flat box missed because the flame tests it with a pad of 0 and the streams pass 1-2.7 m above it, not because of an inside-start rejection. On a bar the tick now deals ~2 x the 1997 rate (the car-calibrated factor does not fit the bar). T06 strip 54 / 54 unchanged. Promotion 18 (the driver) has neither fix.**

**Update 2026-10-18 evening (s.11): the flame finding of s.10 was wrong. The tick does not stop flame hits. The T05 bar is a flat box under `I76_BREAKABLE_BOX=4` (both the tick presets and promotion 18), and the flame never hits it, even in the stock loop. With the bar's stock shape the tick hits it on 94 % of the tests. A T05 car is burned and killed under the tick: ~40 s, against ~25 s for the 1997 20 fps coupling; promotion 18 does not kill it in 38 s. No tick fix, so tick19c 6846c2d4 stays the candidate.**

**Update 2026-10-18 afternoon (s.10): the owner's first playtest found four real problems. Fixed and measured: tracers (drawn for 1 frame, now every frame), sound loops restarted every tick (15.4 starts / sim s, now 0.86 like promotion 18), the lab copy not being the driver (keys, music switch, menu pointer). NOT fixed: flame hits never register under the tick (nor under promotion 18). New candidate STRLKUP-tick19c 6846c2d4, gate 21 PASS 0 FAIL 2 INFO.**

**Update 2026-10-18 morning (s.9): the four unmeasured items were measured; three needed a patch (wheel / pad early tick, sign timing, new rounds frozen for a tick) and the flamer a fourth (stream ~2.5 segments under the tick); new candidate STRLKUP-tick19b 7e2caf32, gate 21 PASS 0 FAIL 2 INFO. Flame hits on a target remain unmeasured.**

**Better than promotion 18 on what was measured, with two gaps that are not measured.** Recommended: the **33.3 ms
tick** (`tick19-33`, launcher `PLAY-TICK.bat`).

| metric (n) | tick 33.3 ms | tick 66.7 ms | promotion 18 (PLAY-balanced) | tick33 vs p18 |
|---|---|---|---|---|
| tick correctness: ticks / wall s, gates per tick, leaks, hooks read back live (s.2) | 29.98 /s, 1.000, 0 leaks / 430 k checks, 30/30 sites, 24 boots | 15.005 /s, 1.000, 0 / 180 k, 30/30, 21 boots | (no tick) 18/18 sites, 23 boots | works |
| keyboard: key -> first changed drawn frame, median / p90 / max ms (3 boots x 40 presses each) | **4.4 / 7.8 / 8.7** | 4.3 / 8.0 / 9.1 | 10.0 / 28.0 / 33.5 | **better** |
| wheel / pad -> drawn frame | not measured (expected about 0..33 ms, the early tick watches the keyboard only) | not measured (0..67 ms) | not measured | **unknown, probably worse** |
| T13 AI fire, hostile shots per sim min, 20..53 s window, god (5 boots) | 151 +- 16 | 98 +- 63 | 87 +- 10 | **closer to stock** (stock 30 fps loop: 171 +- 64) |
| T13 the same, 20 s to end (5 boots) | 305 +- 111, player alive 5/5 | 184 +- 43, alive 5/5 | 87 +- 10, **god-held player killed at 53.6 s in 5/5** | **better** (stock 30 fps: 286 +- 149, alive 5/5) |
| T13 40 s window (5 boots + 2 A/A) | 36 +- 4 | 32 +- 8 | 31 +- 4 | same (all arms, stock 32 +- 6) |
| flamer damage per sim second | not measured (s.5) | not measured | not measured | **unknown** |
| T06 strip vs retail P166 (3 boots, same car) | 11 / 13 gate rows PASS | **12 / 13** | 9 / 13 | better |
| T05 placed 56 m/s jumps vs retail P166 (9 jumps, same car) | take-off / vy / apex PASS, distance 235 ok, 0 turned over | same as tick33 | take-off / vy / apex PASS, **distance 178 m OUT, pitch rate 0.62 vs 1.61 OUT** | better |
| drawn-pose stalls: player / AI cars / projectiles (20-21 boots) | 0.16 % / 0.36 % / 3.1 % | 0.35 % / 0.39 % / 4.3 % | 0.16 % / 0.36 % / 0.0 % | same / same / **worse** |
| owner's route, real renderer (game-tick, dgVoodoo): gate-folder | **21 PASS 0 FAIL 2 INFO**, trip 2/2 at 119.7 / 120 fps, 10/10 boots tick ON | rows 2, 3, 5, 6: 8 PASS 0 FAIL, 120.3 / 120.7 fps, 7/7 tick ON | promotion 18 passed the same gate (PROMOTIONS row 17); control on this proxy rows 3, 6: 6 PASS | same |

**tick33 vs tick66.** Both are the same build; only `I76_SIM_TICK_MS` differs. tick66 (the 1997 design: 15 ticks / s,
the car in 2 x 33.3 ms) passes one more retail row (left-key yaw) and the T06 ramp apex, but its AI decides at 15 Hz:
its fire sits below the stock 30 fps reference (98 vs 171 per min in the common window, 184 vs 286 full), and the
player and projectiles stall about twice as often between ticks. tick33 is the owner's 33.3 ms baseline, matches the
stock loop's AI fire and keeps the drawn player as smooth as promotion 18. Recommendation: **tick33 as PLAY-TICK**,
tick66 kept as PLAY-TICK-66 for the feel comparison.

**What would make it worse in play, unmeasured:** (1) the wheel or pad: the early tick only watches keyboard keys, so
analog input waits for the next tick (uniform 0..33 ms at tick33), where promotion 18 waits for its next 41.7 ms step
from a per-frame input path (not measured either); (2) flamers (s.5). Both need the owner's hands or a new probe.

## 1. The build

| | md5 | source |
|---|---|---|
| **candidate proxy `STRLKUP-tick19.dll`** | **`3dab950b9250ab11bb80572e2b9697e5`** | i76-everywhere `music-fix` as committed at `dd8d3e3` (= HEAD `e46704d` for music-fix: no music-fix commit between), MSVC 2019 x86 `cl /LD /MT /O2 /W3` (lab `builds\tick-finish-20261018\build.cmd`, the recipe that reproduces 33211f11, CURSOR-FIX-ON-18 s.1). No warnings. |
| second build of the same tree (`run2\`) | `dd96dda7...` | `pecmp.py`: `.text .rdata .data .fptable .reloc` SAME, 0 bytes differ with the timestamps masked: deterministic |
| lab twin for the headless harness `Strlkup-tf2-lab.dll` | `c4a505f48e830c0a480b9ad92d70db20` | the same tree + the lab drive block (drive keys, latency probe, `lat_peek` for the early tick, fire bits) + `I76_STEP_SEQ` / `I76_HEADLESS_ACTIVE` (`make.ps1 -LabTag tf2`) |

- **What is in it beyond promotion 18's 33211f11** (source `eed2c1b`): `simtick.c` (`I76_SIM_TICK_MS`,
  `I76_SIM_TICK_INPUT` form 2), `replay.c`, the retail-handling and music-retail switches, the cursor `ar` map, the
  start-pos patch 2. All are off unless set. One default-path change: the music proxy reads an MCI status "paused" as
  not ended (music retail work, e025739). The control gate (promotion 18's PLAY-balanced preset on this proxy, rows 3
  and 6) passed 6/6 at 120 fps.
- **No proxy selftest exists** (none in music-fix or tools); the checks are the live read-backs: every boot's probe
  decodes the 12 sim gates, 4 display hooks and the frame hook from the running process (30 call sites land in the
  proxy for every tick boot, 18 for every promotion-18 boot), and the proxy log's `sim-tick: ON ... 12/12 sim gates,
  4/4 display hooks, 14/14 draw-side holds, 7/7 cosmetic sites; early tick on input ON` line in every tick boot (0
  `NOT applied`, 0 CRASH lines in 89 private-desktop boots and 20 gate boots).

## 2. The presets (lab; generator `tools\tick-finish\make-presets.ps1`, driver files read only)

`tick19-33.psd1` (`9588701b`) and `tick19-66.psd1` (`1e1e2756`) = the daily driver's promotion-18
**best-wide-balanced** (`0bca8b31`, checked by md5 before use) minus 10 keys, plus 2:

- **Removed (per-frame timing):** `I76_FIXED_STEP`, `I76_FRAMERATE_FIXES`, `I76_ENGINE_DT_FIX`, `I76_RENDER_INTERP`
  (the proxy refuses the tick with any of these on), `I76_INPUT_LATCH`, `I76_AI_BACKAWAY_GRID`, `I76_COLL_DEDUPE`,
  `I76_COLL_WINDOW`, `I76_COLL_WINDOW_WHEN`, `I76_AI_ROLL_HOLD` (='0', off either way).
- **Added:** `I76_SIM_TICK_MS` 33.3333 / 66.6667, `I76_SIM_TICK_INPUT=1`.
- **Kept, all 24 others** (terrain hull fix, breakable box 4, clutter 1200 + fade 300, road / far clip 1200, terrain
  LOD 24, cursor map keys, health %, label table, ZGLIDE TMU fix, Glide refresh 120, aspect, mirror ...). Also written:
  `tick19w-33/66` from best-wide (PLAY.bat), and `p18-best-wide*.psd1` = verbatim copies (the twin's own best-wide
  presets are still the pre-18 files).

**Do any kept switches assume the per-frame path?** (read in `strlkproxy.c` / `simtick.c`)
- `I76_COLL_WINDOW` needs `I76_FIXED_STEP` (logs "not applied" without it); `I76_COLL_DEDUPE` only acts with a fixed
  step; `I76_INPUT_LATCH` changes nothing without one. Removed for that reason: the tick sweeps a whole step's contacts
  once per tick and runs input once per tick.
- `I76_HIRES_CLOCK`: inert under the tick (`if (g_hires_on && !g_simtick)`); the tick has its own QPC accumulator.
- `I76_BREAKABLE_BOX=4` (sign-post sweep + knock-off when the DRAWN car reaches the post): the sweep runs every display
  frame from the frame hook and sees the physics pose move only on tick frames (one tick's motion per sweep); its drawn
  pose comes from `simtick.c`'s render wrapper (written for it). Designed to work, **not measured under the tick**: no
  sign or barricade ram boots ran tonight.
- `I76_CAM_GROUND_FIX`, `I76_TERRAIN_HULL_FIX`: render side, read the camera every display frame; fine by construction.

## 3. Harness and A/A

Lab copies: `game-wst` (headless twin, i76.exe 6319abf7, null renderers, 120 fps cap; Jade's car), `game-samecar`
(the emulator save's car read back in every boot: armour+chassis 9600, mass 1846, engine 104440, 18/18 boots),
`game-tick` (dgVoodoo, the owner's route). Every headless boot on a private desktop (`deskrun.py`), keys through the
proxy's drive block (no key ever reaches the owner's desktop), audio muted and read back per hold, console lock held at
most 38 min per hold (6 holds, 00:47-04:05, interleaved with the controls-promotion, LAN-test and the stopped lane's
queues). The gate needs the screen and ran on the physical console (03:36-03:50).

Arms: **tf33 / tf66** = `tick19-33 / tick19-66`; **p18** = promotion 18's PLAY-balanced preset verbatim + the judder
census; **e30k** = the stock frame loop at 30 fps (I76_TICK_MS 1 + FPS cap 30, no timing patches): AI-DAMAGE-BALANCE
s.0 item 4 found this loop indistinguishable from retail 1.0 on the emulated P166 in T13 (n 8 vs 10), so it is the
retail stand-in on this harness. **tf33aa / tf66aa / p18aa** = independent second boot sets (A/A). Captures: lab
`captures\tick-finish-20261018` (gitignored); tables: lab `emu\results\tick-finish-20261018\tf-tables.md`
(`tools\tick-finish\tf_analyse.py --fp`). Spreads are 95 % t intervals over boots (boot = cluster).

**A/A.** Latency boot medians: tf33 5.3 / 4.8 vs tf33aa 3.4 ms; tf66 4.3 / 4.8 vs 4.1; p18 9.2 / 8.3 vs 11.3. T13
40 s window: tf33 36 +- 4 vs tf33aa 38 (n 2); p18 31 +- 4 vs p18aa 33 (n 2). Every A/A pair lies inside its arm's
spread. Physics boots are near-deterministic (sd 0.000 on most rows), so their spread comes from the retail references.

## 4. Measurements

### 4.1 Correctness (every boot, live counters + proxy log)

| arm | boots | ticks / wall s | gate calls / tick (10 offline sites) | player / AI substeps per tick | leaks / checks | proxy sites read back | log: tick ON / NOT applied / CRASH |
|---|---|---|---|---|---|---|---|
| tf33 + tf33aa | 24 | 29.98 (29.944..30.000) | 0.999..1.000 | 1.000 / 1.000 | 0 / 429 657 | 30 x 24 | 24 / 0 / 0 |
| tf66 + tf66aa | 21 | 15.005 (14.991..15.021) | 0.999..1.000 | 2.000 / 2.000 | 0 / 180 161 | 30 x 21 | 21 / 0 / 0 |
| tf33g / tf66g (game-tick, dgVoodoo, private desktop; flamer boots) | 4 / 4 | 30.000 / 15.010 | 1.000 | 1 / 2 | 0 / 194 558 | 30 x 8 | 8 / 0 / 0 |
| p18 + p18aa (+ p18g) | 23 (+3) | - | - | - | - | 18 x 24 | - / - / 0 |
| e30k | 10 | - | - | - | - | 2 x 13 | - / - / 0 |

Outside writes (a pose changed between ticks by something other than the sim) are the harness's own placements and
the flamer turret's hand-turned car (0 in the latency and combat boots). Early ticks: 29-36 of 40 presses per latency
boot (the rest landed on a regular tick or waited for an outstanding borrowed tick, at most 5).

### 4.2 Input latency (T06, 40 steer-key toggles per boot at random phases; the proxy's latency probe)

| arm | boots | presses | key -> first sim step ms (median, p90, max) | key -> first changed drawn frame ms (median, p90, max) |
|---|---|---|---|---|
| tf33 (+aa) | 2 + 1 | 120 | 4.3, 7.7, 8.5 | **4.4, 7.8, 8.7** |
| tf66 (+aa) | 2 + 1 | 120 | 4.2, 7.8, 8.9 | 4.3, 8.0, 9.1 |
| p18 (+aa) | 2 + 1 | 120 | 9.9, 27.9, 33.4 | 10.0, 28.0, 33.5 |

The early tick turns "wait for the tick" into "wait for the next display frame" (max 9 ms at 120 fps). Promotion 18
waits for its next 41.7 ms physics step when the key lands between steps (p90 28 ms). The probe measures the first
sim step and the first changed drawn pose, not photons. Keyboard only: wheel / pad input is not watched by the early
tick and was not probed.

### 4.3 AI fire (T13, player idle, trainer god flag held)

Three windows, because the per-frame scheme changes how the mission plays out (TICK-LATENCY s.2):

| arm | 40 s boots: hostile shots / min (n) | 90 s boots, 20..53 s: shots / min | hits / min | 90 s boots, 20 s..end: shots / min | player killed despite god (90 s boots) |
|---|---|---|---|---|---|
| tf33 | 36 +- 4 (5) | **151 +- 16** (5) | 37 +- 12 | **305 +- 111** | 0 / 5 |
| tf66 | 32 +- 8 (5) | 98 +- 63 (5) | 44 +- 46 | 184 +- 43 | 0 / 5 |
| p18 | 31 +- 4 (5) | 87 +- 10 (5) | 22 +- 4 | 87 +- 10 (to 52 s) | **5 / 5, all at 53.6 s sim** |
| e30k (stock loop, 30 fps) | 32 +- 6 (5) | 171 +- 64 (5) | 40 +- 10 | 286 +- 149 | 0 / 5 |

- In the first 40 s (mostly the approach: no fire before about 19 s) every arm is the same.
- Once the fight starts, **tf33 tracks the stock 30 fps loop** (151 vs 171, 305 vs 286 /min; hits 37 vs 40). tf66
  fires less (its AI rolls 15 times a second, the passed share is the same). **Promotion 18 fires about half as much
  and its god-held player is killed at 53.6 s in 5 of 5 boots**, a deterministic event the stock loop and both ticks
  never show (0 of 15). The 3.5 x ratio first reported (WHOLE-SIM-TICK s.3.1, n 1) was this divergence measured over
  unequal windows. Promotion 18 under-firing matches AI-DAMAGE-BALANCE s.0 item 6 (best-wide 50 vs retail 118 rounds
  /min, other harness). Which switch kills the player under god was bisected but not narrowed (TICK-LATENCY s.2).
- **Against retail's 107 /min (AI-DAMAGE-BALANCE s.5):** that figure is the parked, non-god emulator harness (the
  player dies about 56 s in), not comparable number for number with these god boots; e30k on this harness is the
  stand-in, and tf33 matches it.
- By weapon (90 s F boots of the stopped lane, same pattern): the difference is the turret 30cal (the truck
  `vfratlr1`) and 50cal; missiles (DrRadar 5-10 /min) are the same in every arm.

### 4.4 Physics vs retail 1.0 (game-samecar = the emulator's car; T06 strip 3 boots, T05 placed 56 m/s 3 boots x 3 jumps)

Against retail P166 low (the gold standard; fingerprint.py pass bands):

| metric | P166 | tf33 | tf66 | p18 |
|---|---|---|---|---|
| 0-20 m/s s | 4.18 | 4.20 PASS | 4.13 PASS | 4.17 PASS |
| brake decel 25 -> 5 m/s2 | 11.88 | 11.77 PASS | 11.76 PASS | **11.60 FAIL** |
| steady yaw R / L / pooled rad/s | 1.107 / 1.128 / 1.117 | 1.104 PASS / **1.112 FAIL** / 1.108 PASS | 1.116 / 1.126 / 1.121 **all PASS** | 1.093 PASS / **1.099 FAIL** / **1.096 FAIL** |
| T06 ramp A 30: foot m/s, air s, apex m | 35.28, 2.27, 28.52 | PASS, **1.667 FAIL**, **28.00 FAIL** | PASS, **1.911 FAIL**, 28.29 PASS | **35.95 FAIL**, **1.850 FAIL**, PASS |
| T05 take-off m/s, vy, apex dy | 51.62, 14.45, 10.66 | 50.57, 14.16, 10.23 PASS | the same PASS | 51.87, 14.52, 10.76 PASS |
| T05 distance m, pitch rate rad/s (watch) | 228, 1.61 | 235 ok, 1.57 ok | 235 ok, 1.57 ok | **178 OUT, 0.62 OUT** |
| turned over / destroyed | 0/7, 0/7 | 0/9, 0/9 | 0/9, 0/9 | 0/9, 0/9 |

- Gate rows passed of 13 (accel 3, brake 1, yaw 3, ramp 3, T05 3): **tf66 12, tf33 11, p18 9**. The T06 ramp air
  time fails in every arm (known, SAME-CAR s.4.4: not the step). Against P133 the ticks fail the T05 take-off rows and
  every arm fails P133's 6/10 wreck rate, as before.
- The early tick does not change physics (TICK-LATENCY s.1.5): tf33 / tf66 reproduce last night's tick33 / tick66
  same-car rows to the printed digit (0-10 m/s 1.167 / 1.133, take-off 50.57).
- p18's 41.7 ms step (I76_FIXED_STEP 24) jumps 50 m shorter with a third of the pitch rate. Not traced.

### 4.5 Drawn smoothness (stall census: a display frame whose drawn pose equals the last one while the object moved)

| arm | boots | player | AI vehicles | projectiles | camera |
|---|---|---|---|---|---|
| tf33 | 21 | 0.16 % | 0.36 % | 3.08 % | 0.45 % |
| tf66 | 20 | 0.35 % | 0.39 % | 4.31 % | 0.65 % |
| p18 | 20 | 0.16 % | 0.36 % | 0.00 % (stepped every frame) | 0.55 % |

(n 53 000-520 000 frame-object samples per cell; flamer boots excluded. The A/A sets, latency and combat boots only, read lower in every arm: tf33aa 0.02 / 0.43 / 0.79 %, p18aa 0.04 / 0.23 / 0.0 %.) Promotion 18 interpolates only the player and
the camera and steps projectiles every frame; the tick interpolates everything but a projectile spawned or removed
between ticks stalls for a frame. Not judged by eye.

### 4.6 The owner's route on the real renderer (game-tick, dgVoodoo, `gate-folder.ps1`, physical console)

| run | launcher / preset | result | proxy log slice |
|---|---|---|---|
| gate 20261018-033625 | `PLAY-TICK.bat` / tick19-33, all rows | **21 PASS 0 FAIL 2 INFO**: conf accepted (3440x1440), bookmark route 3/3 through B1.10, trip 2/2 at 119.7 / 120 fps, save screen NO / YES (modal arrow, scratch only, savegame.dir exact), Esc-menu Exit hit where drawn (pointer read back 2326,1338), melee at 120.5 fps, input.map lint, saves byte-identical, no drift; INFO: watermark by eye, no wheel plugged | sim-tick ON 33.333 ms x 10 boots, early tick ON x 10, breakable-box 4 x 10, NOT applied 0, CRASH 0 |
| gate 20261018-034349 | `PLAY-TICK-66.bat` / tick19-66, rows 2, 3, 5, 6 | **8 PASS 0 FAIL**: route 3/3, trip 2/2 at 120.3 / 120.7 fps, Esc-menu Exit HIT, melee 121 fps | ON 66.667 ms x 7, NOT applied 0, CRASH 0 |
| gate 20261018-034838 | control: `PLAY-P18-BALANCED.bat` (promotion 18 preset) on the candidate proxy, rows 3, 6 | **6 PASS 0 FAIL**: trip 2/2 at 120 fps, melee | no tick (as intended), CRASH 0 |

Rows other than 3 boot without the launcher; they took the preset through `LAB_GAME_ENV` with the four refused timing
keys blanked, and the proxy log confirms the tick on in every boot. `game-tick`'s STRLKUP.DLL read back
`3dab950b` before and after.

## 5. Flamers: not measured (three attempts)

- **Player Gas Launcher at T13's AI cars** (turret mode, the frozen player re-placed 18 m from the nearest car): the
  hardpoint key was held 66-81 s per boot through the drive block, headless (6 boots) and on the real renderer (3);
  0 flame hits in every arm, and the launcher's ammo read **700 -> 700**: the key never fired the weapon. Why the drive
  block's hardpoint byte does not fire (throttle and steer bytes work the same way) is not traced.
- **T05's AI flamer cars** (t05cc02 Gas Launcher, t05cc03 FlameThrower), idle + god 120 s, real renderer (5 boots):
  only t05fp03 engaged (20mm, Aim-Nein); the flamer cars never fired. Dropped.
- **What the code predicts** (i76-map `subsystems/weapons.md`: one application per flamer update of max(1, int(D x f x
  dt))): the tick applies flamer damage once per tick from the main pass with dt = T, promotion 18 once per 20 Hz grid
  frame with dt 50 ms. For the Gas Launcher (D 30) in an AI's hands (f 1): tick33 30 x 1 = 30, tick66 15 x 2 = 30,
  promotion 18 20 x 1 = 20, stock 20 fps 20 x 1 = 20, stock ~30 fps (P166) 30 x 1 = 30 damage per second. A
  prediction only. The owner test below covers it.

## 6. Staging (no promotion)

- Lab twin `game-dd-20261003\PLAY-TICK.bat` (tick19-33) and `PLAY-TICK-66.bat` (tick19-66): run the lab copy
  game-tick (the twin keeps the promotion-18 proxy, which has no tick).
- `game-tick\PLAY-TICK.bat`, `PLAY-TICK-66.bat` (own folder) and `PLAY-P18-BALANCED.bat` (the control). game-tick's
  STRLKUP.DLL is now the candidate `3dab950b` (backup `STRLKUP.DLL.c4a505f4-pre-tickfinish`); its older TEST-tick-*
  launchers keep working (their presets need only the tick).
- **`i76-uncap-lab\builds\tick-finish-20261018\promotion-19-candidate\`**: every file a promotion copies, md5s and the
  PROMOTIONS row text + rollback in its README.

## 7. Owner tests (what the lab cannot measure)

1. Wheel feel: PLAY-TICK with the wheel vs PLAY-balanced. If steering feels late, try PLAY-TICK-66 to see the size
   of the effect (twice the wait) before deciding.
2. A mission with flamers on either side (or a melee with a Gas Launcher car): do they burn as they did?
3. T05 signs and barricades on PLAY-TICK (breakable box 4 under the tick is unmeasured).
4. Projectile smoothness at 120 fps (tracers, missiles): the census shows 3.1 % stalled frames at tick33.

## 8. Not run, and why

- Wheel / pad latency: no probe for DirectInput / winmm joystick input exists in the headless harness.
- Flamer damage: s.5.
- Sign / barricade rams under the tick with breakable box 4: no console time left after the gate; listed as owner
  test 3.
- Melee contexts on the same-car fingerprint (as SAME-CAR s.5).
- `tf66aa` T13 boots (A/A for tf66 is the latency boot only).

## 9. The four gaps, measured and patched (2026-10-18 morning, tick-gaps lane)

The owner: "What is the status and next steps of the tick fix? Playtesting? Everything else measured? Surely one or two
things still need a patch here and there?" Three of the four unmeasured items needed a patch, and the fourth (flamers)
needed one too once it could be measured; flame HITS are still not measured. Lab only; the daily driver, the golden copy
and the Downloads portable were not touched.

**New candidate proxy `STRLKUP-tick19b.dll` md5 `7e2caf329346828de8507d080e3e3924`** (i76-everywhere `a3befe1`
music-fix, lab `builds\tick-gaps-20261018\make.ps1`, the MSVC recipe of s.1; a second build is section-identical, pecmp
SAME). Staged in `builds\tick-finish-20261018\promotion-19-candidate\` (README row text and MD5SUMS rewritten) and in
`game-tick` (read back). The presets `tick19-33` / `tick19-66` are unchanged (the new behaviour is the default under the
tick); the PLAY-TICK / PLAY-TICK-66 launcher comments name the new md5 (candidate folder, game-tick, lab twin).

Harness: lab copy `game-wst` (headless, private desktop, audio muted), lab twin builds `Strlkup-tg1..tg6-lab.dll` (the
same source + the drive block; tg6 = `a3befe1`), tools `tools\tick-gaps\` (tables: `tg_analyse.py` ->
`emu\results\tick-gaps-20261018\tg-tables.md`), captures `captures\tick-gaps-20261018` (gitignored). Every tick boot's
probe read the 30 hook sites back live (30 / 30), 0 interpolation leaks, 0 CRASH, 0 NOT applied. Arms: **tg33** =
tick19-33 on the patched build; **tg33nj / tg33p0 / tg33fa0** = the same with one patch switched off (= last night's
behaviour); **p18** = promotion 18's PLAY-balanced preset; **e30k** = the stock loop at 30 fps (retail stand-in);
*aa = A/A twins.

### 9.1 Wheel / pad latency - PATCHED

- **Path (static).** The engine reads a wheel or pad through winmm `joyGetPosEx` (input_JoystickPoll 0x450870, IAT
  0x4bc384, only while GetFocus() is the game window) inside input_UpdateControls. DirectInput is only the force
  feedback. Last night's early tick watched only the keyboard's down bits.
- **Patch (simtick.c + the joy routing in strlkproxy.c).** With I76_SIM_TICK_INPUT=1 the proxy hooks joyGetPosEx /
  joyGetDevCapsA (the existing routing hooks, ids unrouted), records what the tick's input_UpdateControls read per
  joystick id, and on every non-tick display frame calls the same hooked joyGetPosEx for the ids the engine polled (no
  game code). A button, the POV or an axis move of more than 1 % of its caps range (I76_SIM_TICK_JOY_DB permille,
  default 10) runs the early tick, borrowed as for keys (one outstanding at most). I76_SIM_TICK_JOY=0 turns it off.
- **Probe.** No wheel is plugged in and vJoy has no device configured, so a synthetic pad at the proxy's winmm hook
  (I76_JOY_SYNTH, winmm id 0 = joystick1 = the map's steer axis): the harness sets its X (centre <-> +20000) with a QPC
  stamp, the proxy's probe times device change -> first sim step -> first drawn frame; 40 events per boot, T06.

| arm (side build) | boots | events | -> first drawn frame ms: median, p90, max | boot medians | early ticks from the pad per boot |
|---|---|---|---|---|---|
| **tg33** (tg1 x 2, tg6 x 1) | 3 | 120 | **4.2, 7.7, 8.8** | 5.5, 3.6, 3.5 | 33, 32, 28 |
| tg33aa (A/A) | 1 | 40 | 5.1, 8.5, 8.6 | 5.1 | 33 |
| tg33nj (keyboard-only early tick = last night) | 2 | 80 | 13.3, 30.8, 34.0 | 15.8, 11.1 | 0 |
| p18 / p18aa | 2 / 1 | 80 / 40 | 11.2, 28.3, 33.0 / 7.0, 20.2, 24.0 | 11.6, 10.3 / 7.0 | - |

- The pad now answers like the keyboard (max 8.8 ms, one display frame at 120 fps). Without the watch it waited for the
  tick (0..33 ms); promotion 18 waits for its 41.7 ms step (its boot medians spread 7-12 ms A/A).
- **No false early ticks:** pad centred with +-300 counts of noise on every read (0.46 % of the range), no input, 60 s:
  0 early ticks in 3 boots (about 2 500 watcher calls each); no pad at all: 0 watcher calls.
- **Keyboard unchanged:** tg33 key -> drawn frame 4.7 / 7.9 / 9.1 ms (2 boots) and 3.8 / 7.7 / 8.5 (1 boot, final
  source); last night 4.4 / 7.8 / 8.7.
- Not measured: a real device's joyGetPosEx cost per display frame (the synthetic pad costs ~0 us) and its axis noise
  (the 1 % dead band is chosen on the safe side).

### 9.2 Flamers - PATCHED (stream length); hits not measured

- **Why last night's Gas Launcher never fired:** in T13 the AI drives the player car for the whole boot
  (ai_WasPlayerAutopiloted 0x5244c4 = 1 in 185 of 190 samples, `tools\tick-gaps\flame_diag.py`), and weapon_Update
  0x4a4130 skips weapon_ReadPlayerTrigger 0x4a5870 while it is set; the drive block's fire byte was fine. T05 hands the
  car over at ~10 s; there the key fires (ammo 700 -> 0 in 40 s in every boot). That car's Gas Launcher (hardpoint 3)
  fires backwards (stream forward row . nose = -0.996).
- **Found: under the tick the flame stayed ~2.5 segments long.** weapon_AgeFlamerStreams retracts a stream by 2
  segments on each call that saw no shot; 20 shots a second against 30 ageing calls nets nothing (the stock 30 fps loop
  has the same frame-rate bug). Promotion 18 holds ageing to its 20 Hz grid: 18.5 segments.
- **Patch (simtick.c, I76_SIM_TICK_FLAME_AGE=<hz>, default 20, 0 = every tick):** under the tick a stream is aged only
  once a whole 50 ms of sim time has passed since the last ageing (every 2nd tick at 33.3 ms, every tick at 66.7 ms), so
  each call covers a full shot interval. (A first form aged on 50 ms grid lines, 33 / 67 ms windows: 18.7 segments in 3
  boots and 2.5 in a 4th, depending on the weapon timer's phase; replaced by a3befe1.)
- **Measured** (T05, player Gas Launcher held 40 s, barricade 8 / 14 m behind the car; proxy I76_FLAME_CENSUS):

| arm | boots | stream segments, mean while firing | damage-capable flamer updates per sim s (stream live) |
|---|---|---|---|
| **tg33, final source** | 4 | **18.6** (all 4) | **30** (main pass, tick frames) |
| tg33fa0 (ageing every tick = last night) | 4 | 2.5 | 20 (the stream is empty 1 tick in 3) |
| p18 | 4 | 18.5 | 20 (20 Hz grid) |
| e30k (stock 30 fps) | 4 | 2.5 | 20 main pass + 20 rear-mirror pass |

  Every application is max(1, int(D x f x dt)) = 1 in all arms (raw amount 1 read in the stock boots), so per hitting
  segment the tick deals 30 a second (the 15 fps design value D x f of the Gas Launcher, as s.5 predicted),
  promotion 18 20, the stock 30 fps loop 20 plus the mirror's.
- **Not measured: hits.** Only the stock loop landed flame on the barricade (2 of 4 boots with the muzzle on it, 20.1
  damage per sim s); the tick (0 of 13 boots) and promotion 18 (0 of 5, with an 18.5-segment stream) registered no hit
  there, and the T05 cars within reach of the hand-over are dormant (0 hits). Whether the grid / tick flamer paths miss
  targets in play or only this low static bar is open: owner check 2. AI flamer cars against the player: T05's never
  engaged (as last night).

### 9.3 Signs and barricades (I76_BREAKABLE_BOX=4) - PATCHED (sign timing)

T05 Texas 13 / US 380 posts, 11 rams per boot at 20 m/s, +-4 deg / +-0.6 m jitter (signs3-measure's rams); barricades
10 rams per boot (rate-ab-live ram --direct).

| arm | boots | posts knocked off | drawn gap at the knock-off m: median (min..max) | gap when queued, median |
|---|---|---|---|---|
| p18 | 2 | 22 / 22 | -0.11 (-0.34..0.00) | +0.50 |
| tg33 before the patch (tg1, tg2) | 3 | 33 / 33 | -0.31 (-0.42..-0.02) | -0.13 |
| **tg33 patched (tg5 x 2, tg6 x 1)** | 3 | **33 / 33** | **-0.09 (-0.16..-0.01)** | -0.02 |

- Cause: the sweep ran in the frame hook and saw a tick's motion one display frame after the tick, while the drawn car
  starts down that tick's segment in the tick's own frame; the entry point within the step predicted the gap (gap =
  0.67 x entry - 0.24 m, 0.67 m = one tick at 20 m/s). **Patch (strlkproxy.c sign_sweep_tick / sign_pend_frame, called
  from simtick.c):** under the tick the sweep runs once per tick at the end of the sim block, before that frame is drawn,
  and a queued knock-off is tried at once and on every display frame after. Every post still falls (100 %), 0 timeouts,
  now within 0.16 m of the drawn bumper, as under promotion 18.
- Barricades: 13 / 20 knocked off in both arms (n 2 boots each): unchanged by the tick.

### 9.4 Projectile stalls - PATCHED

- **Cause** (census split by spawn tick): 99-100 % of the stalls were rounds spawned inside the tick. They have no
  tick-start pose, so they sat at their end-of-tick pose for the whole next window (a one-tick freeze at the muzzle) and
  then moved on one tick late.
- **Patch (simtick.c, I76_SIM_TICK_PROJ, default 1):** a round spawned in a tick is drawn moving from its end pose E along
  its velocity (projectile data +0x14, in its own frame) to E + 0.5 v T during its first window, and the next tick's
  segment starts from that drawn pose; drawing only, the sim pose is never touched. The velocity reading matched the next
  tick's motion within 10 % in 100 % of 1 466 checks (mean error 6-7 %).
- **Measured** (T13 idle + god 60 s, I76_SIM_TICK_PROJLOG: every round's drawn position per frame at 120 fps):

| arm | boots | census stall % | drawn tracks | zero-length frame steps | steps > 3 x the track median | reversed steps |
|---|---|---|---|---|---|---|
| tg33p0 (last night) / aa | 3 / 1 | 1.8 +- 0.8 / 2.2 | 512 / 146 | **3.4 % / 3.7 %** (all in a track's first 4 frames) | 0 / 0.08 % | 0 |
| **tg33 patched / aa / final** | 3 / 1 / 1 | 0.24 +- 0.66 / 0 / 0 | 448 / 184 / 163 | **0** | 0 / 0 / 0.04 % | 0 |

  Tracers and missiles now leave the muzzle on their first drawn frame and never step backwards.

### 9.5 Gate and physics rows (final candidate)

- **Gate on game-tick (dgVoodoo, physical console, 09:26-09:41, `tools\tick-gaps\run-gate.ps1`), proxy 7e2caf32 read
  back:** PLAY-TICK.bat all rows **21 PASS 0 FAIL 2 INFO** (route 3/3, trip 2/2 at 120 fps, save screen, Esc-menu Exit
  HIT, melee; INFO = watermark by eye, no wheel); PLAY-TICK-66 rows 2, 3, 5, 6 **8 PASS 0 FAIL**; PLAY-balanced's preset
  on the new proxy rows 3, 6 **6 PASS 0 FAIL**. Proxy log: tick ON in 10 + 7 boots with joystick watch ON, new rounds
  drawn moving ON and flamer ageing 20 Hz in every one; 0 CRASH, 0 NOT applied. Runs `autotest\runs\gate\20261018-092638`,
  `-093403`, `-093847`.
- **T06 strip on game-samecar (n 3, patched source tg5):** all 54 fingerprint rows against retail P166 keep last night's
  tf33 verdict (19 PASS, 13 FAIL, 1 OUT, 9 ok, 12 INFO; the 13-row gate as s.4.4); values equal to the printed digit
  except the 33 m/s ramp rows, which differ inside their boot sd (air 2.100 vs 2.133 s, sd 0.03 / 0.06). The patches
  change no physics row.

### 9.6 Patch list (i76-everywhere music-fix)

| commit | change |
|---|---|
| 91c959f | joystick watch for the early tick; projectile spawn census and drawing switch; PROJLOG; FLAME_CENSUS; shm v3 |
| 5f7f3f0 | flamer stream ageing on a 20 Hz sim-time grid under the tick; sign-sweep log detail |
| 6c71b6b | new rounds drawn moving by default; the sign sweep once per tick at the sim block's end |
| 1d3577b, 0d6c3dc | flame census logs stream lengths and the update cadence (lab instrument, off by default) |
| a3befe1 | flamer ageing after a whole 50 ms (phase-independent) - the candidate source |

### 9.7 Owner checks (revised)

1. **Wheel and pad feel**: PLAY-TICK vs PLAY-balanced. The early tick now watches them (lab: synthetic pad, 4.2 ms
   median). If steering feels twitchy or the game stutters with the wheel in, say so (a real device's read cost and
   noise are not measured).
2. **Flamers, on PLAY-TICK and on PLAY-balanced**: does a Gas Launcher or FlameThrower burn an enemy car, and is the flame
   long? The lab could not land flame on a target under either.
3. **T05 signs**: do they fall as the bumper touches them?
4. **Tracers and missiles at 120 fps**: smooth from the muzzle?

### 9.8 Still not measured, and why

- Flame hits and damage on a target under the tick and under promotion 18 (9.2: the harness's targets took 0 hits).
- AI flamer cars against the player (T05's never engaged; no other mission tried).
- A real wheel or pad (none plugged in; vJoy has no device configured, and enabling one needs admin and adds a
  system-wide device).
- tick66 arms beyond the gate rows (the patches apply to it), and the same-car T05 jumps (no physics code changed).

## 10. The owner's first playtest of PLAY-TICK, and what changed (2026-10-18 afternoon, tick-fix lane)

The owner played PLAY-TICK / PLAY-TICK-66 (game-tick, proxy 7e2caf32) and wrote seven notes. Lab only: the daily driver,
the golden copy and the Downloads portable were only read. Captures: lab `captures\tick-fix-20261018` (gitignored); side
builds `builds\tick-fix-20261018` (tx1..tx8, `make.ps1`); queues `queue-tickfix\q1..q8`; tools `tools\tick-fix`.

**New candidate `STRLKUP-tick19c.dll` md5 `6846c2d42dcd9ad7ed2503956c19d522`** (i76-everywhere `3e7e0c5` music-fix, the
MSVC recipe of s.1; a second build `run2\` is section-identical, pecmp SAME). Installed in game-tick (read back) and staged
in `builds\tick-finish-20261018\promotion-19-candidate\` (tick19b's set kept in `_superseded-tick19b\`). `3e7e0c5` also
carries the co-op commits made on music-fix since `a3befe1` (d444c9b, f2598f0: network games only).

| owner note | cause | fix | evidence (n) |
|---|---|---|---|
| cursor still not aligned | the driver itself has the 242 px offset; the fix (CURSOR-FIX-ON-18) was gated, never promoted | game-tick tick presets `I76_CURSOR_MAP_DGV='ar'` + `dgVoodoo.tick.conf` aa6414e4 | pointer minus drawn pencil max 8 px vs 242 px with the driver's settings (n 2 + 1) |
| music not like the best | `I76_MUSIC_RETAIL` / `_RESUME` are not in the driver | both in the tick presets | proxy log: retail set ON in 11 / 11 tick boots of the gate (not listened to) |
| keys | old game-tick had the pre-18 input.map 90122d37 | game-tick rebased on the driver (input.map a66a37f7) | md5, 449 / 449 files |
| signs | - | - | owner: correct |
| sounds restarted fast | sustained loops stopped every display frame between ticks | keep-alive held between ticks | 15.4 -> 0.86 starts / sim s (n 3 + 3) |
| tracers only the first moment (33 and 66) | the renderer resets a tracer not stepped since its last draw | records kept alive, drawn segment between ticks | 1 drawn frame -> every frame of 0.72 s (n 2 + 5) |
| flamer impact / damage | under the tick (and promotion 18) a stream never registers a hit | NOT FIXED (3 hypotheses ruled out) | 0 hits in 116 000 near calls vs 94 % in stock (n 4 + 3) |

### 10.1 The lab copy was not the daily driver ("the lab isn't up to date with the best stuff in the daily driver")

| file | daily driver (promotion 18 + controls 18) | old game-tick | lab twin game-dd-20261003 |
|---|---|---|---|
| input.map | a66a37f7 | **90122d37 (pre-18)** | **12a6357e** (18 without the orbit blocks) |
| _ahk\i76-remap.ahk | 62ba0883 | **14367db9 (pre-18)** | 62ba0883 |
| presets best-wide / -balanced / best-120 | 3922146a / 0bca8b31 / 9b53c141 | **e1a9bd26 / 75881df4 / df936278 (pre-17)** | the same pre-17 files |
| I76PLYR.DEF, NSCR.DAT, NVCL\nvcl0.vcf, multicar.def, user.mel | the driver's | differ | differ (also ADDON\vehscn.vcf, i76car.def, saves) |
| i76.exe, u32x, i76shell, dgVoodoo confs, PLAY-i76.ps1, music\*.mp3, music.wav | 6319abf7, 06467bd2, a300db63, dccd379a, ... | same | same |

So game-tick played the pre-promotion-18 keys (no J K L ; hardpoints, K radar). The tick presets themselves were made from
the driver's 0bca8b31 and were right. The twin does not mirror the driver either (input.map, presets, saves); it was not
changed here (other lanes stage into it).

**Rebase.** The old game-tick is kept as `game-tick-old` (a copy: the folder could not be renamed, a handle was open in it).
game-tick\Interstate 76 was mirrored from the DRIVER (robocopy /MIR, the driver only read): md5 manifests of the two (449
files) identical. Then only these were added; an md5 diff against the driver shows nothing else:
`STRLKUP.DLL` 33211f11 -> **6846c2d4**; `presets\tick19-33.psd1` **b8bb9b1b**, `tick19-66.psd1` **8715387b**, `tick19w-33 / -66`
(b2d30f14 / f5a2e2a8), `p18-best-wide(-balanced).psd1` (verbatim copies of the driver's); `dgVoodoo.tick.conf` **aa6414e4**
(new file). Outside the game folder: `PLAY-TICK.bat`, `PLAY-TICK-66.bat`, `PLAY-P18-BALANCED.bat`.

**Presets** (`tools\tick-finish\make-presets.ps1 -OwnerBest`, from the driver's best-wide-balanced 0bca8b31): promotion 18's
switch set minus the 10 per-frame timing keys of s.2, plus the tick keys, plus the two finished items the owner approved that
are NOT in the driver yet:
- **music**: `I76_MUSIC_RETAIL=1` + `I76_MUSIC_RESUME=1` (OWNER-TEST-LIST item 49, owner test 05 "perfect in each way"). The
  music files were identical everywhere; what differed was the switch (the driver plays today's non-retail rules).
- **menu pointer**: `I76_CURSOR_MAP_DGV='ar'` + `dgVoodoo.tick.conf` = the CURSOR-FIX-ON-18 conf aa6414e4 ([DirectX] Resolution
  1920x1440), copied in by PLAY-TICK / PLAY-TICK-66 (PLAY-P18-BALANCED keeps the driver's wide conf). The driver still has DGV
  '1' and conf dccd379a, the 242 px offset CURSOR-FIX-ON-18 s.3a measured; the fix was gated on the twin but never promoted,
  so "still not aligned" was the driver's own state carried into game-tick. The candidate proxy has the 'ar' code (s.1).

### 10.2 Tracers ("don't go out from the car, just the first moment is visible"; 66: "only the second part, not the travel")

- **Cause (static, i76-map disassembly).** A tracer is not drawn from its round's pose. The engine keeps a ring of tracer
  records (0x64 B, `[0x52ba48]`): +4 the round, +8 "updated since the last draw", +0xc / +0x10 the older / newer slot of a
  2-slot ring (next table 0x52ba38), +0x1c the slots' world points. weapon_StepBullet 0x4abe60 -> 0x441ef0 writes the round's
  position into the next slot and sets +8; renderer_QueueTracers 0x442480 draws older -> newer and clears +8, and a record
  whose +8 is already 0 when drawn is **reset and loses its round** (+4 = 0). Stock stepped before every draw. Under the tick
  the second drawn frame after a tick reset every record and 0x441ef0 never found it again: each tracer was drawn for one
  frame. At 66.7 ms the one drawn segment is the round's second step ("only the second part").
- **Fix (simtick.c, I76_SIM_TICK_TRACER, default 1).** Records updated in a tick are kept marked around each render; the drawn
  segment ends at lerp(older, newer, alpha) (where the round is drawn) and is one tick long, starting at the muzzle during the
  round's first tick; after the render the record and +8 = 0 are put back, so a dead round's record is still reset by the
  first render after its last tick, as in stock. Lab log I76_SIM_TICK_TRCLOG (`tools\tick-fix\trc_analyse.py`).
- **Measured** (T13 idle + god 60 s, the AI firing at the player, headless, every tracer record the renderer drew per frame
  at 120 fps):

| arm | boots | tracers | drawn frames per tracer (median) | shown / alive | life median | segment | head step per drawn frame |
|---|---|---|---|---|---|---|---|
| tick33, tracer fix off (= 7e2caf32) | 1 | 91 | **1** | - | 1 frame | 1.9 m | - |
| tick66, fix off | 1 | 91 | **1** | - | 1 frame | 6.7 m (the 2nd step) | - |
| **tick33** (+ A/A) | 3 | 141 / 151 / 176 | **88** | **1.00** (p10 1.00) | 0.72 s | grows from the muzzle over the first tick, then 6.67 m (one tick at 200 m/s) | 1.67 m every frame; 0 zero, 0 reversed in 38 372 steps |
| **tick66** | 2 | 87 / 86 | 80 / 176 | **1.00** | 0.66 / 1.46 s | 13.3 m (one 66.7 ms tick) | 0 zero, 0 reversed in 23 205 steps |

  The stock game at 30 fps draws the same streak (one frame of travel). Not judged by eye (s.10.6).

### 10.3 Sound effects ("being restarted fast")

- **Cause.** Sustained loops (voice mode 2: road dirt / sand, wind, tyre skid / turn, tflat, damage, missile-lock tones) live
  while requested: each request adds 1 to the voice's keep-alive byte +0x74, and the per-frame sound update shell_cb_10
  0x421400 (call 0x403e27, every DISPLAY frame) stops a mode-2 voice whose keep-alive is 0. Under the tick the sim requests once
  per tick, so the next display frame stopped the loop and the next tick started it again.
- **Fix (simtick.c, I76_SIM_TICK_SOUND, default 1).** The tick frame lists the mode-2 voices the tick requested; on the display
  frames until the next tick those voices get keep-alive 1 before the update. A loop the next tick does not request stops on
  that tick frame, as in stock. Count instrument I76_SOUND_CENSUS=1 (the sound_StartVoice call sites 0x4214e0 / 0x422422:
  every start that played, by sample; `tools\tick-fix\snd_analyse.py`).
- **Measured** (T06 strip: accel, steer, jumps; headless; voice starts per sim second over ~86 sim s per boot):

| arm | boots | starts / sim s | sustained-loop starts / sim s | top restarts |
|---|---|---|---|---|
| tick33, keep-alive fix off (= 7e2caf32) | 3 | **15.42, 15.42, 15.48** | 14.90, 14.88, 14.87 | vcddirt 8.0 /s, vcdsand 2.9, ADWIND 2.3, tskid3 0.75, tturn3 0.46, tskid2 0.44 |
| **tick33** (+ A/A) | 3 | **0.85, 0.90, 0.82** | 0.30, 0.28, 0.22 | none (keep-alives held 3 428-3 950 per boot) |
| promotion 18 (PLAY-balanced preset) | 3 | 0.79, 0.91, 0.80 | 0.28, 0.31, 0.31 | - |
| stock loop at 30 fps | 2 | 0.89, 0.91 | 0.32, 0.28 | - |

### 10.4 Flamers ("go out the right distance, but the impact animation is a hall of mirrors; doesn't seem to damage") - NOT FIXED

- **Found: under the tick a flame stream never registers a hit.** Probe I76_FLAME_PROBE_AT (strlkproxy.c, lab: every
  weapon_FlameHitTest call from the flamer update at 0x44449b, the closest tested segment to a point, the clock at the call)
  with the player's Gas Launcher held 40 s at the T05 barricade 8 m behind the car (`flamep`):

| arm | boots | hit-test calls | calls with the tested segment within 2 m of the barricade | hits | mean tested segment |
|---|---|---|---|---|---|
| stock loop 30 fps, headless / real renderer (25 fps) | 3 / 1 | 2 100 / 30 294 | 0 / 0 (closest 3.9 / 2.2 m) | **700 / 28 464** (33 % / 94 % of the calls) | 1.3 m (2.5 segments) / 2.8 m (17.5 segments) |
| tick33, headless / real renderer | 3 / 1 | 150 700 / 37 674 | 116 648 / 29 162 | **0 / 0** | **9.8 m** (18.6 segments) |
| tick66 | 1 | 150 624 | 116 592 | **0** | 10.2 m |
| promotion 18, headless / real renderer | 2 / 1 | 162 742 | 125 678 | **0** | 6.1 m |

  So no flame damage and no hit explosion on that target under the tick AND under promotion 18 (both hold the flamer update
  the same way, s.9.2); the stock loop hits. The 0-hit census of s.9.2 was this, not the harness. With no hit there is no hit
  explosion, so the lab could not reproduce the "hall of mirrors" on this target; the owner's impressions (impacts, no clear
  damage) need his eyes again once hits work.
- **Ruled out** (each 1-3 boots; still 0 hits, tested segment unchanged): the flamer update's per-call record state (it stores
  the muzzle transform and animation counters in the stream record on every call, 0x444810 / 0x444846; saved and restored
  around every non-tick and mirror call: I76_SIM_TICK_FLAME_STATE=1, 3 boots); the clock at the call (the tick's clock on every
  display frame: I76_SIM_TICK_FLAME_CLK=1); the flamer dt floor (0.001 s and 0.1 s instead of the tick: I76_SIM_TICK_FLAME_DT).
  All three stay as lab switches, off. The lead is the tested segment (9.8 m here against 2.8 m in the hitting stock run):
  what sets it in weapon_UpdateFlamerStreams 0x443fc0 is not traced.
- Also measured: the stock loop spawns one hit explosion per hitting segment per update (28 464 in 36 s, ~780 a second with a
  17-segment stream on the barricade), i.e. the stock game itself stacks many impact sprites.
- The headless T05 ally-van target (`flamepn`, 10 boots) was a dud: the nearest car was 518 m away and dormant in every boot.

### 10.5 Gate, pointer, physics rows (physical console, lock held, audio muted; the owner away)

- **Gate on game-tick (proxy 6846c2d4 read back; `tools\tick-gaps\run-gate.ps1`, 16:09-16:24):** PLAY-TICK.bat all rows **21 PASS
  0 FAIL 2 INFO** (conf accepted, bookmark route 3/3, trip 2/2 at 120.1 / 119.5 fps, save screen NO / YES, Esc-menu Exit hit
  where drawn, melee 121 fps, input.map a66a37f7 lint OK and unchanged, saves byte-identical; INFO = watermark by eye, no
  wheel); PLAY-TICK-66 rows 2, 3, 5, 6 **8 PASS 0 FAIL**; PLAY-P18-BALANCED (promotion 18's preset, the driver's conf) rows 3, 6
  **6 PASS 0 FAIL**. Proxy log: tick ON 33.333 ms x 10 and 66.667 ms x 7, early tick ON in each, NOT applied 0, CRASH 0; the
  tick boots logged `I76_CURSOR_MAP_DGV=ar` and `music: retail set ON` (11 boots), the control `=1` / `retail set off`. Runs
  lab `autotest\runs\gate\20261018-160859`, `-161627`, `-162113`.
- **Menu pointer on game-tick** (`tools\tick-fix\cursor-tick.ps1` -> `tools\cursor-offset\measure-cursor.ps1`, main menu, 7
  points, screen px on 3440x1440): PLAY-TICK's set (tick19-33 + dgVoodoo.tick.conf): pointer minus drawn pencil **max 8 px**
  in both runs (identical to the pixel: centre (-4,-7), corners (-3..-4, -6..-8)), the click lands within 1 px of the pencil;
  the same copy with the driver's settings (p18 preset + wide conf): **242 px** at the sides (-242 / +241), as CURSOR-FIX-ON-18
  s.3a. Lab `tools\cursor-offset\runs\cursor-tick19c-a / -b / -p18ctl.json`.
- **T06 strip on game-samecar, candidate source** (n 3, lab twin tx8 = `3e7e0c5` + drive block): **54 / 54 fingerprint rows keep
  tg33's verdict** (19 PASS, 13 FAIL, 1 OUT, 9 ok, 12 INFO); values within boot noise (accel t20 4.20 s, brake v0 29.51 m/s).
  No physics row moved (lab `emu\results\tick-fix-20261018\tx-t06-vs-p166.md`).

- **Wide menu + pointer (2026-10-19, cursor-wide lane, CURSOR-FIX-ON-18 s.6):** the driver's conf dccd379a draws the menu 16:10 (568..2871); the tick conf's 4:3 [DirectX] mode is what made u32x's 4:3 shell map and DGV `ar` right. New proxy switch `I76_CURSOR_MAP_DGV='aw'` (i76-everywhere 1ca6ba0, music-fix/cursoraw.c) with dccd379a: pointer minus pencil **max 4 px**, shell hit within 4 px (n 2), vs 242 px for the driver set and 8 px for PLAY-TICK (n 2 each, identical to the pixel); mission-start HUD / 3D unchanged (n 1). Not installed: fold `aw` + a 1ca6ba0+ proxy + PLAY-TICK copying dgVoodoo.wide.conf into the next candidate; OK-popup arrow, save screen, Esc menu and the gate not yet run with it.

### 10.6 Still needs the owner's eyes (and ears)

1. **Tracers** on PLAY-TICK and PLAY-TICK-66: do rounds now leave the car and streak all the way? (Lab: drawn every frame, one
   tick long; not seen by eye, see below.)
2. **Sound**: tyre / road / wind loops steady, no stutter.
3. **Music**: the menu track loops on its own, mission music continues after Replay / Esc (test 05's retail + resume set).
4. **Keys**: promotion 18's map (J K L ; hardpoints, O radar camera): game-tick now has the driver's input.map.
5. **Menu pointer** on PLAY-TICK: the arrow on the pencil (lab: within 8 px).
6. **Flamers: still broken under the tick and, by the same measurement, under promotion 18**: no hit registers on the T05
   barricade. Please say whether a flamer burns a car on PLAY-balanced (the driver): that tells whether cars behave like the
   barricade.

Not run, and why:
- The screenshot bursts of visible 3D runs (`wst-run.ps1 -Visible -Shots`, `tools\tick-fix\shots.py`, PIL ImageGrab; also a
  PrintWindow test) came back entirely black for the dgVoodoo window (on lab copy game-tickvis), while the gate's own captures
  (Capture-UI) of game-tick show the picture. Not resolved, so there is no frame sequence of tracers or flames.
- Flame damage on a car: the headless T05 ally-van target (`flamepn`, 10 boots) picked a dormant car 518 m away every time, and
  the barricade takes no hit under the tick anyway (10.4).
- The twin game-dd-20261003 is still not the driver (10.1); not changed here.

## 11. Flame hits: the cause was the barricade's shape, not the tick (2026-10-18 evening, tick-fix2 lane)

**Correction to 10.4.** The tick does not stop flame hits. The T05 bar took 0 hits under the tick and under promotion 18
because both presets set `I76_BREAKABLE_BOX=4`, which turns that bar into a flat box. The flame never hits the flat bar,
not even in the stock loop. With the bar's stock shape the tick hits it on 94 % of the hit tests. A car is hit and killed
under the tick (lab n 6, real renderer n 1). Nothing in the tick needed a fix, so there is **no tick19d**.
`STRLKUP-tick19c` 6846c2d4 stays the candidate, and game-tick was read back as 6846c2d4.

Lab only. The daily driver, the golden copy and the Downloads portable were not touched. Lab twin
`builds\tick-fix2-20261018\Strlkup-fx1-lab.dll` 435cc5be (i76-everywhere `2743ceb` + drive block). Captures: lab
`captures\tick-fix2-20261018` (gitignored). Queues: `queue-fix2\b1`, `b2`. Table tool: `tools\tick-fix2\flame_tab.py`.
Every boot is headless T05 with the player's Gas Launcher held 40 s, unless a row says otherwise. Headless boots repeat to the digit
(e.g. e30ks n 3: 700 / 700 / 700 hits), so the same-condition spread is 0 on the barricade and small on the car.

### 11.1 What a hit needs (static, i76-map disassembly of 0x443fc0 / 0x4354c0 / 0x43d770 / 0x43d9e0 / 0x434f00 / 0x43df10)

- weapon_UpdateFlamerStreams 0x443fc0 walks the stream's points P1..Pn, which it rebuilds on every call. For each point
  after the first it calls weapon_FlameHitTest 0x4354c0 (site 0x44449b) with these arguments:
  - A = the point Pi;
  - a radius of 1.0;
  - B = P1, the first point (stored at i == 1, 0x444732);
  - the damage record (owner [stream+8], kind 4, amount max(1, int(D x f x dt)));
  - an out-pointer for the object that was hit.
- The hit test casts a moving point: A with velocity (A - B) x sim_rate [0x4fe424]. It walks every world record, movers
  0x52b930 then statics 0x52b934, and skips the shooter's own. A record goes on to the narrow test 0x43d770 (site 0x435691)
  only when A lies inside its bound sphere + 1.0.
- The narrow test sweeps over sim_dt [0x4fe420] (0x49c7a0). So the tested segment is A -> A + (A - B), whatever the clock.
  The clock cancels out, which is why FLAME_CLK and FLAME_DT changed nothing (10.4).
  - A part with a sphere (0x4000 / 0x5000) uses the swept sphere test 0x434f00: within radius + 1 at any point of the
    segment, the start included.
  - A box part (0x2000) uses the slab test 0x43df10, padded by the radius. It **rejects a segment that starts inside the
    padded box** (entry t < 0).
- After the first hitting point, every later point of the same update spawns a hit explosion. The stream is shortened to
  1/8 steps from there, which is why a hitting stream's mean |A - B| is short (2.9 m against 9.8 m). The short segment
  in 10.4 was a consequence of hitting, not the cause.
- **Inputs the tick changes:** the stream length (ageing, s.9.2) and which frames may apply damage. The clock it changes
  cancels out. The record lists, the radius and the sweep are the same. The tick does not touch the input that decided
  this test, the bar's part shape.

### 11.2 Bisect and the differing input (T05 bar, player's car 8 m off along x; narrow-test probe on every boot)

| arm | boots | hit tests that hit | damage applications / sim s | hit explosions / sim s | stream segments | narrow tests on the bar / hits |
|---|---|---|---|---|---|---|
| tick33 preset (bar = box) | 2 | 0 % | 0 | 0 | 18.65 | 73 000 / 0 |
| tick33, flamer update left stock every display frame (`I76_SIM_TICK_FLAME_STOCK=1`) | 2 | 0 % | 0 | 0 | 18.65 | 81 080 / 0 |
| tick33, flamer and ageing stock (`=2`) | 2 | 0 % | 0 | 0 | 2.0 | 1 360 / 0 |
| stock loop 30 fps, bar = stock sphere (e30ks) | 3 | 33 % | 20 | 20 | 2.5 | 2 038 / 680 |
| **stock loop 30 fps, bar = box (`I76_BREAKABLE_BOX=4`, e30kb)** | 2 | **0 %** | 0 | 0 | 2.5 | 2 038 / 0 |
| **tick33, bar = stock sphere (preset minus `I76_BREAKABLE_BOX`, fx33nb)** | 3 | **94 %** | **500** | **500** (124 000 held back on non-tick frames) | 18.65 | 145 000 / 136 900 |

- **The differing input is the bar's part shape.** The tick33 preset, promotion 18's PLAY-balanced preset and the stock
  arm with the box all miss. Every arm with the stock sphere hits. The bisect (rows 2 and 3) had already shown the
  tick's flamer hold was not the cause.
- **Why the bar misses.** The probe puts the 18.6-segment stream 1.7 m above the bar (A y 21.7 against the bar's 20.0).
  The 3.03 m stock sphere catches that; the flat box (8.04 x 0.64 x 0 m) does not. Aimed into the bar it still misses:
  - the car pitched 10 / 20 deg nose up (rear muzzle down), n 1 each, tick and stock + box: 0;
  - approached across the bar along z, the stream through two bars within 0.6 / 0.8 m of their centres, n 1 each:
    tick33, promotion 18 and stock + box all 0, stock without the box 680 hits.

  The likely reason is the slab test's inside-start rejection: the points are about 1 m apart, so a point always lands
  inside the 2 m padded slab. That reason is not instrumented further.
- **Consequence (daily driver included):** under `I76_BREAKABLE_BOX=4` the flame **cannot burn the long thin low bars of
  class-4 breakables** (the T05 road-closed barricade bars). This holds in promotion 18 (the driver), in PLAY-TICK and in
  any loop. Rams, signs and posts are unaffected (posts keep their spheres). Cars are not class 4 and are unaffected.
  Owner decision, not changed here: accept it, or patch the flame's box test (e.g. hit when the segment starts inside the
  padded box).

### 11.3 Flame on a car, and the rate against 1997

Target: the nearest T05 car (t05cm03, a parked AI car, class 1, box record). The player's car is frozen 4 m from it with
the Gas Launcher held 40 s. Unpitched, the rear stream rises about 5 deg and passes over the car's roof: 0 hits in every
arm, stock included (n 1 x 3). Pitched 20 deg it goes under: 0 in both arms. So the car runs hold the player's car
**10 deg nose up** (`flamepn4p10`). The damage log is I76_DAMAGE_EVENTS (entity_DamageAndKill 0x463a80); "lost" is the
target's health lost.

| arm | boots | damage applications / sim s | hit explosions / sim s | target car | target health lost |
|---|---|---|---|---|---|
| stock loop 20 fps (e20ks, the 1997 coupling: 18.7 segments, mirror pass) | 3 | 142-147 | 481-501 | **killed at 23.8 / 25.8 / 24.4 s** | 900-954 |
| stock loop 30 fps (e30ks: the 2.5-segment ageing bug, s.9.2) | 3 | 20 | 20 | alive after 35 s | 427-436 |
| **tick33** (fx33 = tick19-33 preset) | 3 | 30-51 | 444-499 | **killed at 38.3 / 41.8 / 39.1 s** | 854-919 |
| **tick66** (fx66) | 3 | 17-30 (amount 2 each) | 226-250 | **killed at 43.7 / 33.5 / 43.6 s** | 848-931 |
| promotion 18 (p18s, the driver's preset) | 3 | 27-38 | 288-311 | alive after 38 s | 417-462 |
| **tick33 on game-tick, real dgVoodoo renderer, visible on the console** (PLAY-TICK's preset, lab twin; game-tick's DLL restored to 6846c2d4 after and read back) | 1 | 117 | 307 | **killed at 17.6 s** | 723 |

The barricade with the stock sphere (n 3 each) gives the cleanest rate, in damage per sim s per target:

| arm | damage / sim s |
|---|---|
| 1997 coupling (stock 20 fps) | **668** |
| tick33 | **500** |
| tick66 | **500** (250 applications x 2) |
| promotion 18 | **328** |
| stock 30 fps | 20 |

- **Flamers damage and kill cars under the tick.** On the car the tick deals about 60 % of the 1997 rate (killed at
  ~40 s against ~25 s). On the bar it deals 75 %. The gap is by design (s.9.2): damage is applied once per tick (30 a
  second), while 1997 at 20 fps applied it 20 times a second in the main pass plus 20 in the rear-mirror pass.
- **Promotion 18 (the driver) burns cars too, but at about half the tick's rate** (car not dead after 38 s, ~440 health
  lost; 328 against 500 on the bar). Its 20 Hz grid applies damage 20 times a second with no mirror pass. **So the game
  the owner plays does not have broken flamers against cars.** They are weaker than 1997 (about 1/3 of the 1997 car
  rate), and the T05-type bars cannot be burned at all (11.2).

### 11.4 "Hall of mirrors" (impact sprites)

- **Rates.** Under the tick the hit explosion (entity_SpawnExplosion 0x49ead0, the xflht1 sprite) is spawned once per
  hitting point per tick update. The non-tick frames' spawns are held back (flame_expl_wrap: 124 000 held back per boot
  on the bar). Spawns per sim s with a full stream:

  | arm | bar | car |
  |---|---|---|
  | tick33 | 500 | 444-499 |
  | tick66 | 250 | 226-250 |
  | promotion 18 | 328 | 288-311 |
  | stock 20 fps (1997) | **668** | **481-501** |

  The tick spawns no more impact sprites per second than the 1997 coupling, so the stacked sprites the owner saw are
  the stock game's own look with a full-length stream (stock 30 fps hides it only because its stream is 2.5 segments
  long).
- **Ageing (static, not instrumented).** The sprite object is pooled per template. 0x49ead0 stamps it with simclock time
  (0x49c8c0) and starts its texture animation (0x44b240, 0.1 s per frame). Texture animations advance in
  image_UpdateTexAnims 0x44af80, one of the 12 sim gates (tick frames only, the tick clock). The object's class tick runs
  in entity_TickAll (gated). So under the tick the sprites are spawned and aged per tick, which is consistent. No fix
  needed. Not done: a per-frame count of live sprite objects.

### 11.5 Build, gate, staging

- **No new candidate.** The two proxy commits are lab instruments, off by default:
  - 2743ceb: the narrow-test probe inside I76_FLAME_PROBE_AT, and `I76_SIM_TICK_FLAME_STOCK` (1 = flamer update / dt /
    damage / hit explosion / mirror left stock under the tick, 2 = the ageing too).

  No default-path code changed, so tick19c 6846c2d4 stays in game-tick and in
  `promotion-19-candidate`. The gate (s.10.5) and the T06 strip were not re-run, because the shipped DLL and the physics
  path did not change. The visible run installed the lab twin in game-tick for one boot; the script put 6846c2d4 back and
  read it back.
- `promotion-19-candidate\README.md`: the flame text in the row ("KNOWN OPEN") and owner check 6 were rewritten to these results. MD5SUMS is unchanged.
- The 10.4 conclusion ("flame hits never register under the tick or promotion 18") and its owner check 6 in s.10.6 are
  superseded by 11.2-11.3.

### 11.6 Still needs the owner's eyes

1. **Flamers on a car, PLAY-TICK vs PLAY-balanced:** the lab kills the T05 car in ~40 s under the tick. The driver deals
   about half that, and the 1997 coupling kills in ~25 s. Does the flame feel strong enough? A per-tick damage multiplier
   to restore the 1997 (main + mirror) rate is possible; it is not done, because it is an owner choice.
2. **The impact sprites:** the tick spawns them at or below the 1997 rate. If they still look wrong, say whether it is
   the number (the stock game's own stacking) or how they move.
3. **Barricade bars and `I76_BREAKABLE_BOX=4`:** on the driver and PLAY-TICK the flame cannot burn the T05 road-closed
   bars (11.2). Keep it, or patch it?

## 13. "Suburbia does not load correctly on tick 66, just a big flat expanse": not reproduced (2026-10-19, tick66-terrain lane)

**Owner note (PLAY-TICK-66, game-tick, proxy tick19c 6846c2d4, preset tick19-66):** "suburbia map does not load correctly
on tick 66 copy, just a big flat expanse." **Result: not reproduced.** Suburbia loaded with its terrain, its houses and its roads
under the 66.7 ms tick on every boot here, by every route the lab can drive. That was 10 boots at 66.7 ms: 2 by the owner's
menus on the real renderer, 3 direct boots on the real renderer and 5 headless. All 15 stock arenas also load their terrain at 33.3 and 66.7 ms. No
call or value differed between the two tick lengths, so **there is no cause to fix and no simtick.c change**. tick19c / the
coming tick19d are unaffected by this lane. Section 12 (the flame lane) is not touched.

Lab only. The daily driver, the golden copy and the Downloads portable were not touched, and game-tick was only read (its STRLKUP.DLL
is still 6846c2d4). Lane copies: `game-t66x` is headless (a copy of game-wst, null renderers, with the owner's user.mel,
I76PLYR.DEF and multicar.def), and `game-t66v` is visible (a copy of game-tick, dgVoodoo.tick.conf). Lab twin
`builds\tick66-terrain-20261019\Strlkup-t1-lab.dll` a0fdbfcb is i76-everywhere a4f3d1e + the drive block + a lab-only
`I76_MELEE_BOOT` block. Tools are in lab `tools\tick66-terrain`, and the captures are in lab `captures\tick66-terrain-20261019`
(gitignored). The visible boots ran with the console lock taken and released per run (owner away, coordinator's go-ahead,
mute watcher on). No input reached the owner's desktop.

### 13.1 What was measured

The terrain is loaded once, at mission load: TDEF -> ZMAP 80x80 tile grid -> ZONE .ter -> the tile table `0x644380`. Suburbia
(m04.msn) has 4 tiles, x 3840..5120 and z 48640..49920, so a camera outside that square would see flat zero-height ground. The
probe (`t66_probe.py`, read-only, every 0.25 s) re-does the engine's own height lookup 0x493550 under the car and under the
camera. It also reads:

- the tile pointer;
- the terrain vertices queued per scene `[0x6442ec]`;
- the car pose and the camera pose;
- the sim-tick shm counters.

The visible boots also took screenshots (shots.py).

| route (renderer) | arm | boots | terrain under car / camera | terrain vertices per scene (median) | houses on screen |
|---|---|---|---|---|---|
| shell menus MELEE > AUTO MELEE > INSTANT MELEE > Suburbia (dgVoodoo, owner's files, AI as the form had them) | tick66 | 2 (1 with throttle held) | 119.9 m tile present, every sample | 2400; 2308-1883 driving | yes: drove through the town (`menu-d1-tick19-66` b02) |
| same | tick33 | 2 (1 with throttle held) | 119.9 m tile present, every sample | 2456; 2276-1978 driving | yes (`menu-d1-tick19-33` b02) |
| same, Hope Springs (control) | tick66 | 1 (throttle) | 24.0-27.9 m, car within 0.0-1.3 m of it | 2760-3556 | n/a (terrain present) |
| direct boot (I76_MELEE_BOOT, dgVoodoo); in the sp1 pair the same pose for both (I76_START_POS 4172.5, 49552.5) | 66 / 33 | 3 / 3 | 119.9 m present | 2400 / 2400 at the same pose | the direct boot's first camera looks up (boot artifact, equal in both arms); the 66 and 33 frames at the same pose differ only in the radar sweep and the HUD lamps |
| headless direct boot, wst files and the owner's files, throttle from 4-8 s | 66 / 33 | 4 / 4 | 119.9 m present, car-terrain -0.05..+0.11 m | 1992-2069 / 1982-2035 | n/a |
| headless sweep, all 15 stock arenas, throttle held | 66 / 33 | 15 / 15 | present on every sample of every boot (0 samples without a tile) | 1193-3004 / 1197-2713 (m08: 0 in both arms, spawn stuck, the same at 33) | n/a |

The sim-tick counters were normal in every tick boot: 15.0 / 30.0 ticks a second, 2 / 1 car substeps, 12/12 gates, 0 leaks.
No early ticks fired (no input device was connected; joyGetDevCaps rc 165 on all 16 ids, in the owner's log too).

### 13.2 The owner's own log (game-tick mciproxy.log, read only)

- **Two Suburbia visits at 66 ms.** Session A: a CD track 6 run (= m04's WRLD track) at t 1889360609, back in the shell 11.7 s
  later, then Dunes (track 8). Session B: track 6 at 1889575671, the in-game menu after ~9 s, then the shell and exit. Both
  are short visits, which fits "it looks wrong, leave".
- **One Suburbia visit at 33 ms earlier the same morning, several minutes long.** Its mirror-pass hull events put the eye at
  world (4812, 49427), next to the east spawns (4732-4862, 49317-49542).
- No CRASH line, no terrain or far-clip complaint, and no proxy event of any kind during either 66 ms Suburbia visit. The one CRASH
  in session A is AcGenral.DLL at exit (state 10), after Dunes.
- **The log cannot tell what was on screen.** The proxy does not log terrain heights or spawn points, and the hull-fix lines
  (mirror pass) depend on the car moving, so their absence says nothing. The lab's Suburbia boots show none either, at
  33 or 66.

### 13.3 What "a big flat expanse" probably was (not proven)

Suburbia is a flat plateau at 119.9 m: every terrain sample the probe read in the town was 119.9. The night arena has 18
houses, a school and 2 bunkers, between x 4305 and 4690. The melee spawn is picked at random among 12 points in two groups,
x 4172-4272 (west) and x 4732-4862 (east). The two groups face each other across the town. **From a west spawn at night, the
first view is a flat grey plain with the houses as a row of small lit windows on the horizon.** This was seen at 66 ms
(`menu-m1-tick19-66` b00/b02); the town is 130-500 m away and dark. The houses appear only after driving toward them. An east
spawn at 33 ms, which is what the owner's 33 ms visit had, shows the same plain looking west. The spawn draw is random per
boot, not per tick length. The lab got a west spawn at 66 ms in 3 of 4 menu / direct boots and at 33 ms in 2 of 4. So the
owner may simply have drawn a west spawn on both 66 ms visits. That is unproven: no screenshot of his screen exists.

### 13.4 Answers to the two questions

- **Does the same happen on PLAY-TICK (33.3 ms) with any arena?** Not here. All 15 stock arenas had terrain at 33.3 ms, the
  same as at 66.7 ms (headless n 1 per arena per arm). Suburbia at 33.3 ms rendered its town on the real renderer (n 2 menu
  boots + 3 direct).
- **Night or size?** Neither shows a tick dependence. Suburbia (hour 0) and Night Driver m12 (hour 0) load their terrain at
  both tick lengths. Suburbia is the smallest stock arena (4 tiles, 1.3 x 1.3 km; the others have 5-27 tiles, Hope Springs 12, Night Driver 27). The
  terrain is loaded whole at mission load, before the first tick, so tile count cannot interact with the tick.

### 13.5 Owner check (needs his eyes)

1. **PLAY-TICK-66, Instant Melee, Suburbia, 3 starts.** If it looks like an empty plain, drive forward 10 s. If houses
   appear, it was the spawn view (13.3). If it is still an empty plain with no houses after driving, take a screenshot
   (Win+Shift+S) and quit with Esc > Abort Mission, not by closing the window. The proxy log then has the timing, and the lab
   can probe that spawn.

### 13.6 Not done, and why

- **No fix, no commit to simtick.c.** There was no differing call or value to fix (rule: instrument, do not guess). The
  candidates in the brief were ruled out:
  - a per-frame call the streamer needs: the terrain is not streamed, it is all loaded at mission load;
  - a load-time timeout: the tile table was complete at the first sample of every boot;
  - the tick starting before the load finished: the first gameplay frame comes after the load (0x403598 onward).
- The multiplayer route (MULTI MELEE > HOST) could not be driven on this copy. The IPX error box "Unable to create an IPX
  connection" appears, because game-tick has no IPX wrapper. If the owner's "MULTIPLAYER" means a network game, that route is
  untested here.
- One of the A/B pairs is a direct boot, not the owner's route. `I76_MELEE_BOOT` sets match_IsMultiMelee [0x501818] and the car
  name 0x5dd370, which the shell's play mode 3 sets at 0x40257b. Its first camera is odd in both arms. The menu boots are the
  owner's route.

## 12. Flame damage at the 1997 rate, and the flame against the boxed bars (2026-10-19, flame-fix lane)

The owner's two decisions on s.11 (verbatim): "yes the flamer damage should map 1997 it's hard to make contact with it so it
should be quite punishing. i think we should patch the breakable-box switch, sure."

**New candidate `STRLKUP-tick19d.dll` md5 `889709031cd60d7cc71aa15fbd71c57f`** (i76-everywhere `ee0bda6`, lab
`builds\flame-fix-20261019\make.ps1`, the MSVC recipe of s.1; a second build `run2\` is section-identical, pecmp SAME). Installed
in game-tick (read back; tick19c kept beside it as `STRLKUP.DLL.6846c2d4-pre-flamefix`) and staged in
`builds\tick-finish-20261018\promotion-19-candidate\` (tick19c's set in `_superseded-tick19c\`). **The gate was not run** (12.6).

Lab only: the daily driver, the golden copy and the Downloads portable were not touched. Every boot headless (private desktop;
the real-renderer rows on the lab copy game-tickvis, also on a private desktop). Lab twins `Strlkup-ff1-lab.dll` e1a9f2d3
(`a4f3d1e`: switches, factor default 1) and `Strlkup-ff2-lab.dll` 0a62a992 (`ee0bda6` = the candidate source) + the drive block.
Captures `captures\flame-fix-20261019` (gitignored); queues `queue-flamefix\q0..q3`; tools `tools\flame-box\` (`ff_tab.py` tables,
`fbdis.py` disassembly, `ff-queue.ps1` / `ff-lock.ps1` = tg-queue / with-lock without the host mute, 12.7).

### 12.1 Correction to s.11: the kill times were mission times

s.11.3 printed the combat log's `t_dead` as "killed at". That clock is mission time (it ends at ~53.7 s, the same base as the
flame census, whose first application is at 13.1-13.4 s). Measured from the first flame contact, the T05 car dies after
**~11 s at the 1997 timing** (s.11 boots: 10.5 / 12.4 / 11.0 s), and after **~27 s under the tick** (tick33 25.2 / 28.7 / 26.0,
tick66 30.7 / 20.4 / 30.3). The car gap was 2.5 x, not 1.6 x, and the brief's "time to kill ~25 s" target is ~11 s.
`tools\flame-box\ff_tab.py` measures from the first contact.

### 12.2 Why the boxed bar rejects the flame (instrumented)

- **The pad is 0, not the flame's radius (static).** weapon_FlameHitTest calls the narrow test 0x43d770 at 0x435691 with arg 10 =
  0 (`push 0` at 0x435674). The tree test 0x43d9e0 passes that value both to the part's sphere prefilter (radius + it) and as the
  pad of the box test 0x43df10 (`push ecx` at 0x43dccc). s.11.1's "padded by the radius" was wrong: the flame tests the boxed bar
  as its bare mesh AABB, 8.04 x 0.64 x 0 m. 0x43df10 is a slab test in the order x, z, y (|d| < 1e-4 = parallel); it then rejects
  tnear > tfar, tfar < 0, tnear > sim_dt and tnear < 0.
- **Probe I76_FLAME_BOX_PROBE=1** (lab, strlkproxy.c `flame_box_probe` at 0x43dd3e; counted only inside a flame narrow test,
  with I76_BREAKABLE_BOX_FLAME=0): it replays the slab test in C and files each call under the first comparison that rejects it.
  The replay agreed with the real return value on **188 024 of 188 024 calls**.

| boot (bar = box, fix off; n 1 each) | box tests | first failing comparison | entry < 0 ("starts inside") | closest the rejected segment came to the bar: < 1 m / 1-2 m / >= 2 m |
|---|---|---|---|---|
| tick33, the s.11 geometry (stream over the bar) | 64 992 | y slab behind 40 708, z slab behind 24 284 | **0** | 0 / 32 535 / 32 457 |
| tick33, bar approached across (flamepx) | 120 994 | z parallel outside 120 980, z slab behind 14 | **0** | 2 / 72 992 / 48 000 |
| stock loop 30 fps | 2 038 | y slab behind 2 036, slabs disjoint 2 | **0** | 0 / 0 / 2 038 |

- **Cause:** the flame segments never pass through the bar's rectangle. In the s.11 geometry they cross the bar's plane 1-2.7 m
  above its 0.64 m height and move away; in the across geometry they run along the bar, parallel to its zero-thickness plane,
  0.44 m off it (a degenerate slab: a parallel segment can only hit at z = 0 exactly). None started inside the box, so s.11's
  suspected reason (an inside-start rejection) was wrong. The stock 0.75 r sphere (3.03 m) catches the same streams on 94 % of
  the tests. A thicker box or a pad of 1 m would still miss this geometry (the closest approach is >= 1 m in 188 022 of 188 024).
- **Fix (strlkproxy.c, `I76_BREAKABLE_BOX_FLAME`, default 1 whenever I76_BREAKABLE_BOX is applied; 0 = as before):** the flame's
  narrow-test call 0x435691 goes through a wrapper that marks "inside a flame narrow test"; the tree test's part-kind read at
  0x43da33 (`mov ebp, [ebx+0x10]; and ebp, 0xf000`, 9 bytes) goes to a thunk that, only while that mark is set, returns the stock
  class-4 default 0x5000 (the 0.75 r sphere) for a part bbox_pick made a box (its node pointers are kept in a ring of 128). So the
  flame sees the stock bar; the car-vs-bar collision (0x43ff80, never inside the flame mark) keeps the box. It applies in every
  loop: stock, the 20 Hz grid and the tick.

### 12.3 The bar with the switch on: flame hits restored (T05 bar, player's Gas Launcher held 40 s, 8 m; headless)

| arm | boots | hit tests that hit | damage / sim s | before (s.11, same arm with the box) |
|---|---|---|---|---|
| 1997 coupling (stock 20 fps) + box + fix | 2 | 94 % | **669.2** (both) | - (stock sphere 669.2, n 3) |
| stock 30 fps + box + fix | 1 | 33 % | 20.1 | 0 (e30kb, n 2) |
| tick33 preset (box on) + fix, factor 1 | 3 | 94 % | 500.6 (all 3) | **0** (n 2) |
| tick66 preset + fix, factor 1 | 3 | 94 % | 500.8 (all 3) | - |
| tick33 preset, fix off (= tick19c) | 1 | 0 % | 0 | 0 |

Equal to the bar's stock sphere in every arm (s.11: 669 / 20 / 500 / 500). Stream 18.6-18.7 segments in every tick boot.

**Not changed by the fix (n 3 each, tick33 preset):**
- T05 barricade rams at 20 m/s (10 per boot): **19 / 30 knocked off with the fix, 20 / 30 without** (per boot 7, 6, 6 against 6, 7, 7;
  s.9.3: 13 / 20). The fix-on count joins one ff1 boot (r1) and two ff2 boots (R2, R3); one ff2 boot was lost to lock contention.
- T05 sign posts (11 + 11 rams per boot): 33 / 33 knocked off, drawn gap at the knock-off median -0.10 m (mean -0.09, -0.17..0.00),
  0 timeouts (s.9.3: -0.09 m, 33 / 33).
- The car (not class 4): the fix only touches class-4 box parts; the car tables below (fix on in every tick arm) match s.11's
  factor-1 boots.

### 12.4 Flame damage factor (I76_SIM_TICK_FLAME_DMG, simtick.c / strlkproxy.c `flame_damage_wrap`)

- **What it does.** Under the tick only (g_simtick), each flame damage application's amount (record d[4] = max(1, int(D x f x
  dt)): 1 at 33.3 ms, 2 at 66.7 ms) is multiplied by the factor, the fraction carried per target. So the factor scales damage per
  unit of damage, i.e. per sim second in both tick arms. The 20 Hz grid (promotion 18) and the stock loop are not touched.
- **AI flamers get it automatically:** every stream in the ring 0x52bb90 (the player's and every AI car's) applies its damage
  through the same site, 0x4357c3 in weapon_FlameHitTest -> `flame_damage_wrap`. Static; no AI flamer fired at the player in the lab
  (T05's never engage, s.9.2).
- **Calibrated on the T05 car** (the nearest parked car, 4 m, the player's car held 10 deg nose up; health lost per second from
  the first contact to the kill). Per boot:

| arm | boots | health lost / s while burning, per boot | kill after first contact s | mean (steady boots) |
|---|---|---|---|---|
| 1997 coupling (stock 20 fps, mirror on): s.11 + this lane | 6 | 86.1, 76.9, 84.1, 90.6, 70.2, 84.4 | 10.5, 12.4, 11.0, 9.8, 12.8, 10.8 | **82.0 / s, 11.2 s** |
| tick33, factor 1: s.11 + this lane | 6 | 36.4, 29.7, 34.4, 29.3, 31.1, *99.4* | 25.2, 28.7, 26.0, 33.3, 28.0, *8.2* | 32.2 / s (n 5), 28.2 s |
| tick66, factor 1 | 6 | 30.4, 41.6, 30.4, 36.1, 32.4, *226* | 30.7, 20.4, 30.3, 25.6, 26.9, *3.7* | 34.2 / s (n 5), 26.8 s |
| tick33, factor 1, flamer dt floor 50 ms (the 1997 stream shape, diagnostic) | 2 | 40.0, 28.9 | 24.6, 33.1 | 34.5 |
| tick33, factor 1, stream record saved / restored around non-tick calls (I76_SIM_TICK_FLAME_STATE, diagnostic) | 2 | 35.4, 29.5 | 25.9, 29.6 | 32.5 |
| tick33 / tick66, factor 2.5 | 3 + 3 | 60.4, 84.4, *369* / 65.8, 75.5, 77.5 | 16.1, 11.2, *2.0* / 14.3, 11.5, 11.9 | 72.7 (n 5), 13.0 s |
| **tick33, factor 2.8 (tick19d source, default)** | 3 | 77.1, 83.1, 91.7 | 11.7, 11.3, 9.7 | **84.0 / s, 10.9 s** |
| **tick66, factor 2.8 (default)** | 3 | 76.8, 94.5, 74.0 | 11.3, 8.8, 12.6 | **81.8 / s, 10.9 s** |
| promotion 18 (s.11, unchanged) | 3 | 11.5, 12.0, 10.9 | alive after 38 s | 11.5 |

  *Italic*: a second regime, 3 of 18 tick boots at factor 1 / 2.5 and 0 of 6 at 2.8, 0 of 6 at 1997: the car dies in 2-8 s from
  only 58-247 hits (lost per hit 3-12 instead of ~1); not explained, left out of the means. Ratio 1997 / tick at factor 1 =
  82.0 / 33.2 = 2.47; 2.5 measured 72.7 (-11 %), 2.8 measured **82.9 (+1 %, n 6) and a kill in 10.9 s against 11.2 s (-3 %)**:
  **default 2.8**. Both inside the brief's ~10 %.
- **The bar does not fit the same factor.** On the bar (stock sphere, or the box with the fix) tick33 and tick66 at 2.8 deal
  **1401.5 / 1402.3 per sim s against 1997's 669.2 (+110 %)**; at factor 1 they deal 500.6 / 500.8, i.e. 1997 / tick = 1.337 there,
  exactly the missing mirror pass (40 updates a second against 30). On the bar every update's contact equals 1997's (16.7 hitting
  points per update in both); on the car the tick's updates land about half the hits per update of 1997's (1997 ~79 car hits / s =
  2.0 per update of 40; tick ~30 / s = 1.0 per update of 30 or 15). The flamer dt (the stream shape) and the stream record state
  were ruled out (diagnostic rows, n 2 each); the cause is not found. Calibrating on the car, as decided, therefore makes the tick
  **about twice as strong as 1997 on a bar** (it burns down faster).
- **Real renderer** (lab copy game-tickvis, dgVoodoo, private desktop; factor 1, n 2 each): 1997 timing 86.5 / 78.4 per s, killed
  10.9 / 10.9 s; tick33 16.7 (alive at the end) / 33.2 (27.8 s); tick66 33.6 (27.5 s) / 47.5 (20.1 s). The same 1997 / tick gap as
  headless (~2.5 x), so the headless calibration carries over. (s.11's one visible boot, killed in 4.7 s, was the second regime.)
- Stream length unchanged: 18.64-18.66 segments in every tick boot (1997 18.68).

### 12.5 Physics strip and build

- **T06 strip on game-samecar, candidate source (ff2 twin, n 3):** **54 / 54 fingerprint rows keep tick19c's verdict** (19 PASS,
  13 FAIL, 1 OUT, 9 ok, 12 INFO); accel t20 4.20 s, brake v0 29.51 m/s, brake dist 37.90 m, equal to the printed digit (lab
  `emu\results\tick-fix-20261018\tick19d-t06-vs-p166.md`). Run because the box fix patches the tree narrow test, which the car's
  collisions also use (the thunk changes nothing outside the flame mark).
- **What else is in tick19d.** It is built from main at `ee0bda6`, which since tick19c (3e7e0c5) also carries three multiplayer
  commits from other lanes: efa108d (MULTI MELEE HOST / JOIN go straight to IPX, `I76_MP_MENU=1` by default; AREA OF PLAY title fit),
  e1f35f0 (AI melee, acts only in ADDON ai_*.lvl) and fdb1b06 (arena title font). This lane did not test them; the single-player
  rows above ran on the same source.

### 12.6 Not done, and why

- **The owner-route gate (run-gate.ps1) was not run on tick19d.** The owner sat down at the PC during the run, and from then on
  every run had to stay headless; the gate drives the real menus on the console. Run it before promoting: PLAY-TICK all rows,
  PLAY-TICK-66 rows 2 3 5 6, PLAY-P18-BALANCED rows 3 6 (expected 21/0, 8/0, 6/0 as tick19c). Note that `run-gate.ps1` takes the
  lock through `with-lock.ps1`, which mutes the host (12.7).
- One ram boot (ff33 R1) and one 1997 + box bar boot (e20kbf b1) were lost to lock contention with other lanes; n is as printed.
- The car's per-update contact gap (12.4) and the second regime are not explained.
- AI flamers against the player: static evidence only.

### 12.7 Audio during this lane

The owner heard music from the first headless boots. The lab lock wrapper `with-lock.ps1` mutes the host per hold and every hold
read back `muted = True` (and a read-only sampler showed the endpoint still muted while a boot ran), yet the coordinator found the
host unmuted at that time; for one hold this lane also ran `tools\mute.ps1` before each launch. Then the owner asked for the host
to stay unmuted: since then this lane's runs went through `tools\flame-box\ff-lock.ps1` / `ff-queue.ps1` (with-lock and tg-queue
without the host mute) and refuse to launch unless the per-process watcher `tools\mute-proc.ps1 -Watch` (pid in
`tools\mute-proc.watch.pid`) is running; `wst-run.ps1` / `sc-run.ps1` check the same. One hold that started before the change
(08:26) ran with-lock's host mute once more. The host was not unmuted by this lane.

### 12.8 Still needs the owner's eyes

1. **Flamers on PLAY-TICK:** a T05 car now burns to death in ~11 s of contact, like 1997 at 20 fps (PLAY-balanced, the driver,
   does not kill it in 35 s). Strong enough, too strong?
2. **T05 road-closed bars** now burn under PLAY-TICK (and would under the driver's switch set with this proxy). Under the tick a bar
   takes ~2 x the 1997 flame damage (12.4).
3. **Promotion 18 (the daily driver) has neither fix:** its proxy 33211f11 has no flame factor (its 20 Hz grid applies 328 per s
   on the bar, ~11.5 health / s on a car) and its I76_BREAKABLE_BOX=4 still makes the T05 bars flame-proof.
4. The gate (12.6).

## 14. The frame-bound factors, the flame outliers, tick19e (2026-10-19, tick-factors lane)

The brief was to implement the four "too fast at 33" factors recommended in FRAME-BOUND-SYSTEMS-2026-10-19.md, under the tick only, each with
its own switch. Then: look for the cause of the flame outliers (s.12.4, the italic rows), build and gate a new candidate, and run the T06 strip.

**New candidate `STRLKUP-tick19e.dll` md5 `a08577c4d512926933b83395b5a2ba48`**
- Source: i76-everywhere `6efb646`, built with lab `builds\tick-factors-20261019\make.ps1` (the MSVC recipe of s.1).
- A second build, `run2\`, is section-identical (pecmp SAME), so the build is deterministic.
- **Gated** on game-tick: 21 / 0 / 2, 8 / 0, 6 / 0 (14.6). This gate also covers tick19d, which was never gated.
- Installed in game-tick and read back. tick19d is kept beside it as `STRLKUP.DLL.88970903-pre-factors`.
- Staged in `promotion-19-candidate`. tick19d's set moved to `_superseded-tick19d\`.

Lab only. The daily driver, the golden copy, the Downloads portable and the PC LAN copy were not touched.
- Every measurement boot was headless: lab copy `game-tfx` (a copy of game-fbs: i76.exe 6319abf7, null renderers), private desktop.
- Lab twin `Strlkup-tf1-lab.dll` c656976c = `6efb646` + the drive block.
- Locks were taken through `tools\flame-box\ff-lock.ps1`: no host mute; the i76 audio sessions were muted by the `mute-proc.ps1` watcher.
- Tools: lab `tools\tick-factors\` (`tf-run.ps1`, `tf-queue.ps1`, `tf_live.py`, `tf_tab.py`, `radar_turn_sim.py`, `outlier\`).
- Tables: lab `emu\results\tick-factors-20261019\tf-tables.md`. Captures: lab `captures\tick-factors-20261019` (gitignored).

### 14.1 What the factors do (simtick.c `st_factors_install`, strlkproxy.c hooks)

The reference rate is `I76_SIM_TICK_REF_HZ`, default 24 per second (1997 as played, the census's reference). Each factor has its own
switch: unset or `auto` = the default below, `0` / `1` / `off` = off, any other value from 0.05 to 10 = that factor.

| system | switch | sites | what is scaled | 33.3 ms | 66.7 ms |
|---|---|---|---|---|---|
| Fire-Dropper patch, oil slick, wheel hazard, landed canister: contact damage | `I76_SIM_TICK_HAZARD_FACTOR` | steps 0x4a08ec / 0x4a0914 / 0x4a0900 / 0x4a0856; damage at the class-damage call 0x4a81d3 in physics_ApplyCollisionDamage | each application's amounts (record d[2..5]) x ref / tick rate, the fraction carried per target and field | 0.8 | 1.6 |
| sustained scrape / pinned contact | `I76_SIM_TICK_SCRAPE_FACTOR` | 0x4644bc (vehicles) / 0x46f8d4 (objects) through `coll_damage_wrap`, then the same class-damage call | applications of a victim / source pair that already had contact on the previous collision pass x ref / tick rate. The first impact stays whole. Projectile sources (class 0x33 / 0x34) and class-4 breakables are left as stock, so the sign / bar knock-off is unchanged | 0.8 | 1.6 |
| wreck debris / secondary-blast roll | `I76_SIM_TICK_WRECK_FACTOR` | 0x4664eb (`call ebx; and eax, 0xf` -> `call st_wreck_roll`; `cmp eax, 7` kept) | a roll is passed with probability ref x substep; otherwise it reads 15 (no action). rand() is consumed as stock | 0.8 | 0.8 (2 substeps a tick) |
| radar-missile turn per step | `I76_SIM_TICK_RADAR_FACTOR` | 0x4aaca0 / 0x4ab400 | a clamped turn x k; a proportional turn x (1 - 0.25^k) / 0.75; k = ref / tick rate | 0.8 | 1.6 |

- `I76_FACTOR_CENSUS=1` (lab) installs the same wrappers in any frame loop, counting only. It logs a `tick-factors:` line every 2 s.
  That line is the measurement below (the 1997 arm uses it in the stock loop).
- Co-op's stub on 0x4a81d3 (`I76_COOP_AI`) chains behind the tick-factors wrapper instead of failing its patch.
- Proxy log line, read in every tick boot of the gate:
  `tick-factors: under the tick; ref 24.0 / s; hazard x 0.800 (4/4 steps, class-damage call 1/1), scrape repeats x 0.800 (2/2 collision calls), wreck roll pass 0.800 (1/1), radar turn x 0.800 / proportional x 0.893 (2/2)`.

### 14.2 Measured (headless T05, n 3 boots per arm; 95 % t intervals, boot = unit)

The arms:
- **1997** = e24: the stock loop at 24 fps, as in the census.
- **before** = tick33off / tick66off: the tick with all four factors off, i.e. tick19d.
- **after** = tick33 / tick66 at the defaults.

**Hazard contact.** The T05 player's Landmines row was swapped to the Oil Slick definition (rate-ab-live's hazard staging). The slick was
dropped for 0.06 s, wait out the 2 s shooter immunity, then the car was frozen in the slicks for 10 s with REPAIR every frame. T05 loads no
Fire-Dropper patch. The slick has damage mask 0, so for the test it was given channel 0 and 5 damage per hit. This is the same sweep ->
0x4a7c80 path the fire patch takes.

| arm | rounds dropped | applications / sim s per round in contact | damage per application (in -> out) | damage / sim s per round in contact |
|---|---|---|---|---|
| 1997 | 4 | **24.1** | 5 -> 5 | **120.5** |
| tick33 before | 4 | 30.1 | 5 -> 5 | 150.5 (x 1.25) |
| tick33 after | 4 | 30.1 | 5 -> **4.00** | **120.4** |
| tick66 before | 8 | 15.1 | 5 -> 5 | 75.5 (x 0.63) |
| tick66 after | 8 | 15.1 | 5 -> **8.00** | **120.9** |

How the per-round numbers were derived:
- The rounds in contact per step are read off the integer counts per boot. In 5 of 15 boots one round lay outside the car (3 of 4, or 7 of 8),
  so the raw applications per second differ between boots: 1997 96.4 / 72.3 / 72.3.
- Per round in contact, every boot repeats to 0.1: 24.1, 30.1, 15.1 per s.
- At 66.7 ms the 0.06 s tap spans two ticks, so 8 rounds are dropped instead of 4. The rate per round is still 15.1 per s: one projectile
  step per tick, as the census said.

**Wreck debris / secondary-blast roll.** The T05 car was killed with the 50cal (fb_live's guns staging). The wreck's rolls were then counted
for its 10 s (span 10.0 s in every boot).

| arm | rolls / sim s | passed / sim s | acting rolls (values 0..7) / sim s |
|---|---|---|---|
| 1997 | 24.1 +- 0 | **24.1** | **12.2 +- 0.7** |
| tick33 before / after | 30.1 / 30.1 | 30.1 -> **23.1 +- 0.9** | 15.1 +- 1.9 -> **11.5 +- 2.9** |
| tick66 before / after | 30.1 / 30.1 | 30.1 -> **23.9 +- 0.4** | 15.4 +- 1.5 -> **11.4 +- 0.4** |

The 66.7 ms tick runs the roll 30 times a second (2 substeps x 15), as the census said.

**Sustained scrape.** The setup was the T05 car placed 6 m in front of the parked target car, 3 m/s toward it, full throttle for 8 s.

| arm | repeated-contact applications per boot | their amount in -> out | first-contact applications | collision damage on the player per boot (in -> out) |
|---|---|---|---|---|
| 1997 | 24, 24, 24 | 33 / 33 / 34 (unscaled) | 16, 32, 16 | 35, 68, 38 |
| tick33 before | 18, 36, 18 | 25 / 52 / 25 | 52, 44, 50 | 45, 100, 49 |
| tick33 after | 18, 0, 0 | 25 -> **19** | 46, 20, 32 | 48 -> 44, 21, 29 |
| tick66 before | 2, 2, 0 | 3 / 3 / 0 | 32, 32, 30 | 43, 43, 46 |
| tick66 after | 22, 0, 22 | 26 -> **41** | 46, 30, 46 | 61 -> 70, 46, 61 -> 70 |

- **The mechanism is verified.** Repeats are scaled 0.76 / 1.58 (0.8 / 1.6 with the integer carry). First contacts are untouched.
  1997's repeat rate while in contact was 44.4 per s for both directions of the pair (n 3).
- **The effect on damage per second is not resolved.** The push did not hold contact: the target slides away and the car re-contacts, so
  most records are "first" contacts. Repeats appeared in 3 of 3 1997 boots but only 1-2 of 3 boots in four of the tick arms.
- The between-boot spread (player damage 21-100 per boot) is larger than any arm difference.
- A pinned contact against a fixed wall was not staged. T05 has no wall the harness can place the car against without a planner.

**Radar-missile turn: not measured in game, from the code only.**
- T05's two DrRadar turrets (t05ug01, about 2.3 km from the hand-over) did not fire at the player. The player was held on a 150 m circle
  round one of them for 30 s, n 1, and the census line logged 0 turns.
- The player's own DrRadar (the Landmines row swapped to the DrRadar Trt definition) fired 4 missiles, but with no radar lock they never
  turned: 0 turns. The missile's target (pd+0x10) is a referenced object, and writing it from outside is not safe.
- `radar_turn_sim.py` replays the turn law (0x4aa9f0) in 2D: 200 m/s, a target crossing at 30 m/s at 200 m, launched 20 / 60 / 120 deg off.

| arm | limit per s, 15..150 m flown (deg/s) | > 150 m | time to align, 60 deg off (s) |
|---|---|---|---|
| 1997 | 356 | 470 | 0.29 |
| tick33 before / after | 445 / **356** | 588 / **470** | 0.23 / **0.30** |
| tick66 before / after | 222 / **356** | 294 / **470** | 0.47 / **0.33** |

  After the factor, the turn per second is 1997's at both ticks. At 66.7 ms the missile still moves 13.3 m per step against 8.3 m in 1997.
  In the model it then overshoots on its first pass and comes round again: hit at 2.9-3.2 s against 1.1-1.3 s in 1997. That is the step
  length, which no turn factor can fix. Not seen in game.

### 14.3 The flame outliers (s.12.4's second regime): stock mechanisms, no proxy bug

Method: log analysis of the flame lane's and tick-fix2's captures (combat logs, proxy logs) plus a static reading of the exe. The game was
not run for this part (`tools\tick-factors\outlier\ratio.py`, `clstab.py`).

| boot | hits | damage asked | health "lost" | kill after first contact |
|---|---|---|---|---|
| ff33f1-c2 (tick33, factor 1) | 247 | 247 | 812 | 8.2 s |
| ff66f1-c1 (tick66, factor 1) | 58 | 116 | 843 | 3.8 s |
| ff33x250-c3 (tick33, 2.5) | 63 | 157 | 749 | 2.1 s |
| fx33g-v1 (s.11's visible "4.7 s") | 144 | 144 | 723 | 4.8 s |

- **Ruled out:** a second damage source. Every damage event on the target in these 4 boots came from the player at the flame amount: 1 or 2
  per hit, or the factor-2.5 amounts. There was no collision, blast or other shooter.
- **Also ruled out:** the target moving off. Its drift was 0.1-3.4 m, the same as in normal boots.
- **Ruled out:** a stale or doubled record. "Asked" equals hits x the amount in every outlier.
- **"Lost per hit" is not damage dealt.** The killing call runs the stock wreck code inside the hooked entity_DamageAndKill (0x463a80 ->
  0x466180). That code removes 50-100 % of every component's remaining health (0x46646a / 0x466471, then 0x462040 at 0x46648f), and the
  hook books all of it on that one call. A car killed early therefore shows ~800 "lost" over a few hits.
  Cars still alive lose 0.56-0.66 per unit asked (n 7).
- **Why it dies early.** A flame record (kind mask bit 2) never reaches armour or chassis: in 0x465620 armour needs mask & 3 and chassis
  mask & 8. It damages only components (0x465af0), and it kills only through that function's instant-kill roll (0x465cc3..0x465d7f). The
  roll fires when the random pick lands on a component that is already destroyed, and kills if (current / max component health) x
  (rand % 100) < amount x 2.5 (x 0.1 for the player).
  - So every flame kill is that roll; an early kill is an early lucky roll after a small component in the hit zone died.
  - The tick does not raise the odds per unit of damage. At full health it is about 3 % per unit at 1 per hit (1997 and tick33), 2.5 % at
    2 per hit (tick66) and about 2.7 % at 3 per hit.
- **"Never at 1997" is not evidence of a tick effect.** Early kills were 4 of 34 tick boots against 0 of 8 at 1997. P(0 of 8 | the same rate)
  is about 0.41.
- No fix: it is stock behaviour.
- Instrument change for later (not made): in the combat log, book the kill call's loss as `lost_wreck` and report damage asked per second, not
  lost per second.

**The census's "god-held player dies in T13" (e24, 4 of 5): a different mechanism, only partly traced.**
- In 2 of the 4 deaths (a3 at 43.45 s, a5 at 43.53 s) no damage event reached the player after the 42.91 s snapshot.
- Collision damage goes through the same hooked dispatch and would have been counted. So those two deaths did not come through damage.
- They came through object_Destroy 0x4652b0, which sets the dead flag directly, and the trainer's god flag never clears it.
- 0x4652b0's callers are: upside-down at rest 0x436ff0, a fall of more than 35 m 0x438fd0, a script destroy, self-destruct, and the network.
  T13's script destroys only enemy8/9 and the bridge span.
- In the other two deaths (a2, a4) the player was hit in the window, so their cause is open.
- A side gap in god mode: 0x465620's play-flag zeroing sits inside `if (side != 4)`, so roof hits still reach the components and the kill
  roll (x 0.1 for the player).
- It is not the flame mechanism. A flip or a fall is the guess (step-coupled, which fits 41.7 ms arms only), but it is not proven: the boots
  recorded no pose.
- Next step: hook 0x4652b0's entry and log the caller's return address. One e24 boot should name the path.

### 14.4 T06 strip (game-samecar, tick33 preset, lab twin tf1 of the tick19e source, n 3)

- **54 / 54 fingerprint rows keep tick19d's verdict:** 19 PASS, 13 FAIL, 1 OUT, 9 ok, 12 INFO.
- accel t20 4.20 s, brake v0 29.52 m/s (tick19d 29.51), brake dist 37.90 m.
- Table: lab `emu\results\tick-fix-20261018\tick19e-t06-vs-p166.md`.
- Run because the scrape factor touches the collision pass. The strip's car never meets a second body, so no repeat is scaled there.

### 14.5 Build and staging

- `promotion-19-candidate`: README (row, gate evidence, owner check 7), MD5SUMS.txt (6 files), and launcher text "tick19e (md5 a08577c4)".
  The two launchers were copied to game-tick as well: PLAY-TICK 11c7d9d6, PLAY-TICK-66 5400a386. Presets and conf are unchanged.
- tick19d's set is kept in `_superseded-tick19d\`.
- `tools\tick-gaps\run-gate.ps1 -NoHostMute` takes the console lock through ff-lock.ps1 (no host mute; the audio watcher is required).

### 14.6 Gate (lab game-tick, dgVoodoo, physical console, owner away, 2026-10-19 13:25-13:40, `run-gate.ps1 -NoHostMute`)

| launcher | rows | result | run |
|---|---|---|---|
| PLAY-TICK.bat (tick19-33) | all | **21 PASS 0 FAIL 2 INFO** | `autotest\runs\gate\20261019-132526` |
| PLAY-TICK-66.bat (tick19-66) | 2 3 5 6 | **8 PASS 0 FAIL** | `-133258` |
| PLAY-P18-BALANCED.bat (control) | 3 6 | **6 PASS 0 FAIL** | `-133748` |

- Proxy log: tick ON in 17 / 17 tick boots, all at 120 fps.
- The tick-factors line was in every tick boot, with all sites applied. 0 NOT applied.
- **1 CRASH line set: an AcGenral.DLL access fault (AcGenral.DLL+0x98AD3) after the MCI close at exit, in one tick66 boot.**
  - It is the compat shim's exit fault, seen in the owner's own log before (s.13.2).
  - Its row passed. It is not in proxy code.

### 14.7 Not done, and why

- **The radar-missile turn is not measured in game (14.2).** The factor is implemented from the code and checked in the model only.
- **Sustained-scrape damage per second is not resolved (14.2).** The per-application scaling is verified; the push did not hold contact.
- **Fire-Dropper patch itself:** not loaded in T05. It was stood in for by the oil slick with a forced mask and damage, on the same code path.
- No AI-dropper or wheel-hazard boots. The landed canister has no stock weapon.
- The two open T13 deaths (14.3) are not traced.

### 14.8 Still needs the owner's eyes

1. On PLAY-TICK and PLAY-TICK-66, these should now cost what they did in 1997:
   - standing in a Fire-Dropper patch or an oil slick;
   - being pinned against a car;
   - sitting next to a burning wreck (its debris / blasts);
   - dodging a radar missile.

   Say if the radar missiles feel too lazy or too sharp. That one is from the code only.
2. Any one factor can be switched off in the preset (`I76_SIM_TICK_<HAZARD|SCRAPE|WRECK|RADAR>_FACTOR=0`).

## 15. LAN merged into the candidate presets; I76_MUTE for the harness (2026-10-19 afternoon, lan-merge / mute-switch lane)

Owner: *"would like to see network funcitonalities merged into the lab version"* and, on muting, *"why should we have a watcher
process for muting instead of muting it in the kickoff script?"*

### 15.1 LAN in game-tick and the candidate

- `make-presets.ps1 -OwnerBest` (lab) now also writes the PLAY-LAN.bat keys `I76_COOP_AI='1'`, `I76_COOP_CHAIN='1'`, `I76_MP_MENU='1'`
  (after the music keys). Before the edit the generator reproduced the installed presets byte for byte (4 of 4). Regenerated:
  tick19-33 b8bb9b1b -> 1f01e781, tick19-66 8715387b -> 64d3b6f5 (tick19w-33/-66 b2d30f14 / f5a2e2a8 -> a2dccfb8 / 9ef60fe1; in
  game-tick and the twin game-dd-20261003). The diff is exactly three added lines in each:

      >         I76_COOP_AI         = '1'   # LAN (as PLAY-LAN.bat): the host runs the mission cars and mirrors them to joiners; AI melee arenas ai_*.lvl
      >         I76_COOP_CHAIN      = '1'   # LAN: co-op scene won -> the next scene for everybody; joiners respawn; a lost scenario reloads
      >         I76_MP_MENU         = '1'   # LAN: MULTI MELEE HOST / JOIN go straight to IPX (IPXWrapper DLLs beside i76.exe)

- Files added to `game-tick\Interstate 76` (what mp-pack.py adds to a plain install; the PC LAN copy vs the driver by md5 shows
  nothing else network-related): `ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll` (IPXWrapper 0.7.2) and the 27 ADDON arenas of
  `tools/coop-install.py` at a05a6e4 (ai_hs2/4/6, auto01..07, coop01..17 + 27 markers). Candidate folder: same presets and files,
  README (LAN note, file rows, PROMOTIONS row text, rollback with `coop-install.py --remove`), MD5SUMS.txt 63 files; the pre-merge
  set in `_superseded-tick19e-prelan\`. tick19e (a08577c4) unchanged.
- Tests, PC, console lock 13:56-14:06 then the gate (joiner: lab copy `game-lanmerge-b` = game-mpmenu-b + coop-install.py, ADDON
  byte-identical to game-tick's, proxy 24bf53c5 = a547572 lab build, I76_MUTE=1; game-tick started by PLAY-TICK.bat with only
  I76_MULTI_INSTANCE=1 I76_NO_MINIMIZE=1 added; driver `i76-uncap-lab\tools\lan-merge\lmnav.sh`, i76probe):

| check | result | n |
|---|---|---|
| game-tick (tick 33.3 ms ON in the log) hosts Hope Springs (2 AI) (index 15, `ai_hs2.lvl`), the other copy joins | joined (me 6, host 3); 4 cars at the same coordinates on both; the 2 AI cars move and the joiner's copies follow the host's within 0.5 m (aimelee log lines, host and joiner) | 2 |
| reverse: game-lanmerge-b hosts Hope Springs (2 AI), game-tick (PLAY-TICK.bat) joins | joined, 4 = 4 cars at the same places | 1 |
| game-tick hosts Scene 1 (Co-op) (index 25, `coop01.lvl`), the other copy joins | joined; host drives the mission's player object; 7 = 7 cars at the same places | 1 |
| single player on PLAY-TICK: gate rows 2-3 (run-gate.ps1 -NoHostMute -Which 33 -Only 2,3; `autotest\runs\gate\20261019-140652`) | 6 PASS 0 FAIL: bookmark route 3 of 3, trip through PLAY-TICK.bat 2 of 2 at 119.7 fps, saves byte-identical; tick ON 5 of 5 boots, CRASH 0 | 1 gate (3 + 2 runs) |

  Seen in the host's log, not a failure: under the tick `coop-ai: ai_FrameTick at 0x00403DDF has UNEXPECTED bytes - not patching`
  (the tick owns that call); the mission cars still reached the joiner in both arenas (positions above). Not run: PLAY-TICK-66
  in a network game, scenarios, 3+ players, the family machines (they carry the 2026-10-18 pack: stock arenas only with this set
  until they get the next pack, from the CRC rule, not tested).

### 15.2 I76_MUTE

- Proxy commit a547572 (`music-fix/mutesess.c`, off by default): a thread started in DllMain mutes the process's default audio
  session through Core Audio (CoInitializeEx MTA, default render endpoint for eConsole and eMultimedia, IAudioSessionManager,
  GetSimpleAudioVolume(NULL, 0), SetMute, GetMute) and re-checks at 3 / 15 / 60 s. **It works at attach**: the session exists from
  that call on (seen 0.15-0.16 s after launch, state inactive, already muted) before the game opens any sound; no later hook needed.
  Lab-only build `i76-uncap-lab\builds\mute-switch-20261019\STRLKUP-mute-a547572.dll` (24bf53c5; the worktree compile 83c736a5 has
  the same .text); game-tick and the candidate keep tick19e.
- Test (lab copy game-lanmerge-b, watcher stopped with tools\mute-proc.stop, `tools\lan-merge\mute-check.ps1` polling the sessions
  every 100 ms + `mute-proc.ps1 -List`): with I76_MUTE=1 the session was muted when first seen and in every sample, -List muted
  True, log "mute: session muted = 1 (at attach ...)" 2/2 roles, n 2 (a fresh folder, and one after clearing the stored state)
  plus one more after a muted run; without the key: first seen unmuted and playing at t+0.98 s, no mute line, n 1.
- **Windows remembers a session mute per exe path** (HKCU `...\Audio\PolicyConfig\PropertyStore`, value 5, per output device)
  and applies it to that exe's next session. The first control boot came up muted only because the previous run had muted it
  (the null read as "the switch leaks"; the store said otherwise). Consequence: every watcher-muted lab copy stays muted for the
  next launch, whoever starts it: **game-tick, the owner's PLAY-TICK copy, was stored muted on both output devices** (from the
  gate runs under the watcher). Cleared with the new lab `tools\unmute-persisted.ps1` (game closed; read back "not muted" 2/2);
  tg-gate.ps1 now runs it for game-tick at its end. Not re-checked by a boot of game-tick (the mechanism was checked on
  game-lanmerge-b, n 1).
- Harness: I76_MUTE=1 in autotest\proxy-run.ps1, tools\tick-gaps\tg-gate.ps1 (LAB_GAME_ENV and the launcher rows' environment),
  tools\tick-fix\cursor-tick.ps1, tools\frame-bound\fb-run.ps1; not in any owner preset or PLAY-*.bat. tick19e and older proxies
  ignore it, so the watcher stays as the fallback (lab CONSOLE-LOCK.md).

## 16. Owner regressions on tick19e: the instant-melee crash, "no AI cars", two helicopters in T05; tick19f (2026-10-19 evening, sp-fix lane)

Owner (verbatim): *"crashes every time i try it enter instant melee. multi-melee opens but no ai cars are populated."* and *"not sure why
two heilocopters spawn in t05 (on both play-tick and daily but not on stock game), that seems to be an error too."*

**Results in short.**
- **Instant melee crash: a tick bug, not a LAN-key bug. Fixed in tick19f `d805e4be995bdd1bc4ee49ae6d2d2ada` (i76-everywhere
  `47a2b3a`, deterministic). Its gate ran but is void (16.5), so tick19f is NOT installed and NOT staged; game-tick keeps tick19e.**
  The tick's object walks called the engine's release-if-dead function as if it were a lookup. Each walk stole a reference from every
  dead object, so objects were freed while the texture-animation list still held them.
- **"No AI cars" in multi melee: the owner's games never loaded Hope Springs.** His sessions on game-tick and on game-aimelee ran other
  arenas. Hope Springs (4 AI), hosted alone, had 4 AI cars, all sent at the host (n 3). The suspected cause is the pointer on the wide
  menu picture: the list click did not change the selection. That is not measured (16.3).
- **Two helicopters in T05: the 1997 mission has two.** They are not doubled by any switch. The count was 2 under the stock loop,
  promotion 18 and tick19-33 (n 2 each). There is no fix, and the daily driver is not affected by any switch.

The daily driver, the golden copy, the Downloads portable and the PC LAN copy were only read (T05.MSN md5s). The owner was at the PC
for the first part of the session, so every run before the gate was headless, on a private desktop, with the game muted per pid.

### 16.1 Headless shell driving (new lab tool)

The instant-melee route goes through the shell's menus. SendInput and SetCursorPos cannot reach a game on a private desktop, so the
lab twin got a block that drives the shell from inside the game:
- `builds\sp-fix-20261019\shellclick-block.c`, switch `I76_LAB_SHELLCLICK=1`, lab builds only.
- The shell's MouseUpdate (0x1001fbf0) reads the pointer through three i76shell.dll imports: GetCursorPos, ScreenToClient and
  GetAsyncKeyState(1/2/4). The block repoints those three slots.
- It is fed by a command file, `<game>\labclick.cmd`, with `click x y [ms]`, `move x y` and `key VK` commands.

The tools around it, in lab `tools\sp-fix\`:
- `sp-run.ps1` starts one boot of a lab copy with a preset, on desktop I76Lab-sp. It sets I76_MUTE=1 and starts start-mute-watch on
  the pid, and keeps a per-folder lock.
- `spnav.py` reads state from memory. It drives these routes:
  - MELEE > AUTO MELEE > INSTANT MELEE, with the form's A.I. DRIVERS -/+ (form buttons 8 / 9 at x 150..166 / 198..213, y 288..303);
  - MELEE > MULTI MELEE > HOST / JOIN;
  - an I76_MISSION boot.
- `spnav.py` also takes a census of the live-object list (0x54b204), unique objects by class and name.

The lab copies are `game-sp` (a robocopy of game-tick) and `game-sp-b`.

**Where the crash came from in the owner's log.** game-tick's mciproxy.log has 3 crashes at about 15:21:
- AcGenral.DLL+0x99892 once, and exe+0x5F103 (read 0x13657F08) twice;
- all three at `frame 1 state 5`, right after the shell played track 2;
- in each of those boots the arena list's first measured title was **'Scene 1 (Co-op)'**.

The arena index of INSTANT MELEE and MULTI MELEE is shared (DAT_100d4474) and is saved in `user.mel` (its first dword). The lan-merge
lane had hosted Scene 1 (Co-op), index 25 (`coop01.lvl`), from game-tick. The owner's instant melee therefore opened on that arena. At
15:37 a MULTI MELEE host saved index 5 (Tombstone).

### 16.2 Instant melee: reproduction, bisect, cause, fix

Setup: game-sp, the tick19-33 preset (with the LAN keys), user.mel index 25, and the lab twin of tick19e plus the shell-click block.
"Held" means the boot was still alive in the mission after 30 s.

| condition (instant melee, Scene 1 (Co-op)) | result | n |
|---|---|---|
| tick19-33 as the owner runs it | **crash exe+0x5F103, read [esi+8], frame 1, 1.5-3 s after ENTER AREA** | 1 |
| without I76_COOP_AI / without I76_COOP_CHAIN / without I76_MP_MENU / I76_AIMELEE=0 / all three LAN keys off | crash, same address | 1 each (5) |
| tick 66.7 ms / I76_BREAKABLE_BOX off / tick drawing switches off (PROJ, TRACER, SOUND, COSMETIC) / the four tick factors off / I76_SIM_TICK_INPUT off | crash, same address | 1 each (5) |
| with the texture-animation diagnostic (I76_LAB_TEXDIAG) | crash, same address | 2 |
| **tick off** (I76_SIM_TICK_MS removed) | held | 4 |
| promotion 18's preset / the stock preset | held / held (the stock run ended the mission by itself within 15 s) | 1 / 1 |
| tick19-33 on other arenas: Tombstone, Crater, Hope Springs (4 AI), Oil Well Well (Scenario), Scene 2 (Co-op) | held | 1 each (+1 Tombstone) |

In total the tick crashed this case 13 of 13 boots; with the tick off 0 of 4 crashed. Not bisected: tick19d against tick19e. The code
that crashes has been in every tick build since `68d3ba2` (2026-10-17), so tick19d has it as well.

**Cause** (I76_LAB_TEXDIAG logs every texture-animation add and walk, and every HeapFree / VirtualFree that frees a held handle):
- **What image_UpdateTexAnims does.** It runs at 0x44af80, gated with the sim. It walks the list [0x535f64] and calls
  `0x45f0f0(handle, "texanm")` on each node.
- **What 0x45f0f0 is.** It is not a lookup but the engine's release-if-dead:
  - for a live object (word +8 != 1) it returns the object;
  - for a dead one it drops one reference (+0xc, and the children's through 0x45f0c0), frees the object at the last reference, and
    returns 0.
- **Who calls it.** Every holder calls it once per pass to give up its own reference: entity_TickAll with "clasfn", the
  texture-animation walk with "texanm", and others.
- **The proxy's calls.** The proxy called it as a lookup in two places:
  - `wst_walk` (simtick.c), several walks per tick, every tick;
  - `mark_live` (strlkproxy.c, I76_RENDER_INTERP), every rendered frame.
- **What the stolen references did.** In the coop01 instant melee, four placeholder objects ('NULL', 176 bytes, texture-animated) die at
  load.
  - Stock order: entity_TickAll releases the live list's reference, then the texture-animation walk releases the last one and frees
    them. The walk's own stack (0x44afa7) does the frees.
  - Under the tick, with the walks' stolen references: entity_TickAll's release (stack 0x461ca1 / 0x403d8b) already freed two of them.
    The heap decommitted the page (MEM_RESERVE at 0x..7000). The walk then read [handle+8] of handle 0x..7F00, which is the crash.
- **With the fix** the frees come from 0x44afa7 again, as in the stock loop.

**Fix (i76-everywhere `47a2b3a`):**
- `obj_live_noref(h)` makes the same alive test (null handle, word +8 == 1) and changes nothing.
- It is used in `wst_walk` and in `mark_live`.
- No switch: the old call was wrong in every case.

**Promotion 18 (the daily driver) has the same call in `mark_live`.** It steals one reference per rendered frame from each dead object
until entity_TickAll unlinks it. Nothing was seen to crash from it on the driver: it has no ADDON arenas, and its preset held coop01
instant melee n 1 here. It is a latent memory-safety bug there, not a measured one. The fix reaches the driver only with a proxy
promotion.

**Verified on the lab twin of the fix** (sp2 = 1ca6ba0 + the fix; sp3 = `47a2b3a` + the lab blocks):

| check | result | n |
|---|---|---|
| instant melee, Scene 1 (Co-op), tick19-33, held 30 s | held; 6 other cars alive; 0 CRASH lines | 9 (3 + 5 + gate pre-run) |
| instant melee, Tombstone, A.I. DRIVERS + twice (form drivers 4 = 3 AI), held 45 s | held; 3 AI present and alive. AI hit the player in 1 run (hp 6400 -> 5793 by 30 s); in the others the nearest AI closed from 406 -> 203 m and 176 -> 16 m | 3 |
| T01 mission boot (I76_MISSION=t01.msn), held 30 s | held; 5 mission cars | 1 |
| MULTI MELEE host, stock arena (Tombstone), alone | in session (net 1), held 100 s / 200 s | 2 |
| join of that host from game-sp-b, headless | **not reached**: after JOIN the shell stayed in screen 0xc026 with no form function for 90 s while the host was up (with no host up, the join form opened in 0.3 s). Not explained; the console check with lmnav is still to run (16.5) | 2 |

### 16.3 "Multi-melee opens but no AI cars are populated": the owner's games never loaded Hope Springs

**What the logs show.** Neither of the owner's attempts loaded an AI arena:
- A host writes an `aimelee: t ...` status line every 5 s while it is in an `ai_*.lvl` arena. The lab runs below logged them (n 3), as
  did the AI lane's.
- **game-tick, about 15:37** (tick19e): none of the owner's boots after line 44000 of its mciproxy.log has one. user.mel was saved with
  index 5, Tombstone, session name 'Unnamed'. That is a stock arena, and stock arenas have no AI cars by design.
- **game-aimelee, about 17:51-17:56** (PLAY-LAN.bat, no tick; the coordinator reports the owner hosted "Hope Springs (4 AI)" there):
  - no aimelee status line;
  - two network missions, about 5 s and 25 s long;
  - the shell's mission music was disc track 2 and then disc track 1.
- Hope Springs (4 AI) plays track 8 (3 of 3 lab hosts). Track 2 is Scene 1 (Co-op), coop01, which was the arena preselected in that
  copy: its list's first measured title was 'Co-op Scene 1'. user.mel there now holds index 5 (Tombstone).

So the "no AI" is not the tick, not the LAN merge and not the AI sync: **the selection never became Hope Springs.** The host form keeps
the arena it opened with until a click lands inside the list's hit area. That area is form button 11, UI x 31..216, y 150..270, and the
row is (y - 151) / row height + scroll.

**Likely cause, not measured here:** the menu pointer on the wide pictures (the cursor-wide lane's subject, 1ca6ba0 `I76_CURSOR_MAP_DGV=aw`):
- under dgVoodoo.wide.conf dccd379a the 640x480 shell is drawn 16:10 (screen x 568..2871 on 3440);
- u32x hit-tests it over the 4:3 fit (x 760..2680);
- a click on the drawn arena titles (UI x 34 and up, screen x about 690) then falls left of the list's hit area and is ignored.

The owner can check this without a fix: before BROADCAST, the selected arena's title is shown at the top of the form, above the list.
It must read "Hope Springs (4 AI)".

**Hope Springs (4 AI) hosted alone** (game-sp, tick19-33, lab twin of the fix; MELEE > MULTI MELEE > HOST > arena index 16 preselected
in user.mel > BROADCAST; no joiner, no lab AI switches):

| run | AI cars present / alive | AI targets | closest approach in 40 s | host hit within 30 s |
|---|---|---|---|---|
| 1 | 4 / 4 | all -> slot 0 (host) from the 2nd status line on | 43 m | yes (100 % -> 74 %) |
| 2 | 4 / 4 | all -> host | 153 m | no |
| 3 | 4 / 4 | all -> host | 6 m | no |

**Not done:** the re-check with a joiner. The headless join did not complete (16.2), and the console was not free for lmnav
(`tools\sp-fix\lan-console.sh` is written for it: 3 lone hosts, then 2 host + join runs through PLAY-TICK.bat).

### 16.4 Two helicopters in T05

- The helicopters are `t05ug01`: two ODEF instances (the second has the instance bit), entities enemy14 / enemy15.
- Each has its own script machine (m32 and m33: setSkill, setAgg, setHeliHeight 25 / 40 m). Both are switched on by the same flag
  (g62 == 1).
- This is the 1997 data. T05.MSN (miss8 91f0ac08, miss16 6df2e45c) is byte-identical in the pristine GOG install, the golden copy, the
  daily driver and game-tick.

Census of the live-object list 15 s into a T05 boot (I76_MISSION):

| preset | t05ug01 objects (class 9) | n |
|---|---|---|
| stock | 2, at (5892, 135, 45178) and (6108, 135, 45268) | 2 (+1) |
| p18-best-wide-balanced (promotion 18) | 2, same places | 2 |
| tick19-33 | 2, same places | 2 (+1) |

So no switch doubles them, and there is nothing to fix under the tick or under I76_FIXED_STEP. The daily driver shows two because the
mission has two.

Not measured: why the owner saw one on the "stock game". The flight after g62 == 1 was not staged, and the retail emulator was not run.
- Untested guess: the stock far clip (600 m) and object LOD hide the second helicopter at some distances.
- The promotion presets draw objects to 1200 m and keep the detailed mesh x 8 farther.

### 16.5 tick19f: build, gate (void), state of game-tick

**Build.** `STRLKUP-tick19f.dll` `d805e4be995bdd1bc4ee49ae6d2d2ada`:
- i76-everywhere `47a2b3a` (= 1ca6ba0 + the fix; cursoraw.c is in it and off unless set);
- lab `builds\sp-fix-20261019\make.ps1 -Rev 47a2b3a -Cand tick19f`, the MSVC recipe of s.1;
- a second build from the same source directory (`run2\`, 1491b1a6) is section-identical (pecmp SAME, timestamps masked).

Lab twin `Strlkup-sp3-lab.dll` = the same commit + drive block + I76_STEP_SEQ + shell-click / texdiag block. The tick-av lane had built
no tick19f yet, so the name is tick19f. Their build must be on `47a2b3a` or later.

**Gate (2026-10-19 17:47-19:12, `tg-gate.ps1 ... -TwinDll`): void, not a verdict on the build.**
- Run with game-tick's launchers as they stood: PLAY-TICK.bat copies dgVoodoo.tick.conf `aa6414e4`, and the presets tick19-33 / -66
  (1f01e781 / 64d3b6f5) set `I76_CURSOR_MAP_DGV='ar'`.
- PLAY-TICK all rows: 8 PASS 6 FAIL 2 INFO.
- **Every FAIL is the harness refusing to run with another i76.exe up** ("an i76* process is running", "the running game is
  ...game-aimelee\i76.exe"). Behind those processes:
  - the owner played game-aimelee during rows 3-5;
  - other lanes' headless games ran throughout (game-av, game-tc, game-t42).
- Row 6 (menu melee) hung for 30 min with the game in the arena behind other windows; I stopped it.
- PLAY-TICK-66: rows 2 and 3 failed the same way; row 5 hung for 30 min.
- I stopped the gate (only my own processes: the gate's scripts and game-tick's i76.exe). I then:
  - put the global `%APPDATA%\dgVoodoo\dgVoodoo.conf` back (the gate's row 1 had left it as `.hidden-by-gate`);
  - removed the stale `game-tick\Interstate 76\.console-test.lock`;
  - cleared game-tick's stored mute (`unmute-persisted.ps1`: "not muted").
- Rows that ran to the end: 1 (conf accepted, put back), 4 (savegame.dir put back), 7 (lint), S (player state byte-identical), D.
- The proxy log slice of the 33 part: tick ON 5 / 5, NOT applied 0, CRASH 0.
- The new rows M1a / M1b / M2 (`tools\sp-fix\sp-gate-rows.ps1`, headless on game-sp, twin sp3) passed 3 / 3 in a run before the gate.
  In the gate itself they were never reached.

**game-tick is back on tick19e** (a08577c4, read back). The gate had installed tick19f. tick19e is also kept as
`STRLKUP.DLL.a08577c4-tick19e`. `promotion-19-candidate` is unchanged: tick19f is not staged, because it is not gated.

**To finish:**
1. Run the gate when no i76.exe runs anywhere on the PC, headless lanes included (gate-folder.ps1 refuses any i76 process by name):
   `run-gate.ps1 -Dll builds\sp-fix-20261019\STRLKUP-tick19f.dll -Md5 d805e4be995bdd1bc4ee49ae6d2d2ada -NoHostMute -TwinDll builds\sp-fix-20261019\Strlkup-sp3-lab.dll`.
2. Run the console LAN check: `tools\sp-fix\lan-console.sh` under with-lock.
3. Install and stage: keep tick19e beside the install and move its set to `_superseded-tick19e`.

If the tick-av lane's presets and launchers (`aw`, dgVoodoo.wide.conf) are in game-tick by then, the gate runs with those. Note which
pointer mode it ran with.

### 16.6 Still needs the owner

1. Instant melee on PLAY-TICK once tick19f is installed, including the arena it remembers (Scene 1 (Co-op) crashed every time on
   tick19e).
2. MULTI MELEE > HOST: before BROADCAST, check that the title at the top of the form reads "Hope Springs (4 AI)". If clicking the list
   row does not change it, the problem is the pointer, not the AI.
3. T05: whether two helicopters are wrong. The 1997 mission places two; say if retail shows only one at the same place in the mission.

## 17. The owner's playtest of tick19e (PLAY-TICK 33): sign sound, music, cutscene camera, death camera, sky, tracers; tick19f-av (2026-10-19 evening, tick-av lane)

The owner (verbatim): "about half the time it seems that the sign running over sound does not play when it gets hit (they do always get
hit and fall though)" / "when the camera is outside the car on cutscenes and you press w to accelerate it makes the video stutter a bit,
not inside, not sure why" / "music doesn't seem to play consistently" / "feels like maybe the death camera is rotating too fast or no?" /
"the sky speed is wrong on tick" / "the tracers seem wider/thicker/denser than they were before maybe 2x somehow".

| owner note | cause | fix (switch, default on, under the tick only) | measured (headless T05 unless stated) |
|---|---|---|---|
| sign sound missing | the post-hit sound is the ENGINE's contact sound (physics_CollideBodyPair: other body class 4 -> `vnvco3.wav` on the car, 0x434e5c..0x434ebc), played before the contact's damage; a post knocked off by `I76_BREAKABLE_BOX`'s sweep had no engine contact, so it fell silently | `I76_SIM_TICK_SIGN_SOUND`: the sweep's knock-off plays that sound on the car (sound_PlayOnObject 0x4231f0) | sweep knock-offs / sounds: old tick33 33 / **0**; fixed tick33 33 / **33** (n 3 + 3); 1997 every knock-off had its sound (2 / 2) |
| music | no tick effect: every cue requested was started in every arm; the silences come from the rules | none (proxy unchanged) | T01 / T05, stock 24 + retail rules, tick33, driver preset, n 2 each: 1 cue per boot, started in 31-172 ms; the owner's own game-tick log: 1 mission with run 1..14 = the data track, silent by design |
| cutscene camera stutter on W | an early tick (key press) restarts the SCRIPT camera's blend from the older tick view while the objects restart from the pose about to be drawn: the camera jumps ahead, then crawls | `I76_SIM_TICK_EARLY_CAM`: the script camera's early segment starts from the view about to be drawn | stutter frames within 3 frames of an early tick: tick33 old **19 of 44**, fixed **0 of 24**; tick66 19 of 29 -> 1 of 20 (n 3-4) |
| death camera too fast | the orbit step (8 x 1 deg per call) was scaled to the TICK's rate (30 / s at 33.3 ms, 15 at 66.7) | `I76_SIM_TICK_ORBIT_REF`: scaled to `I76_SIM_TICK_REF_HZ` (24 / s) | deg / s: 1997 192.0, tick33 old **240.0** -> **192.0**, tick66 old 120.0 -> 192.0, driver 160.0 (n 3 / 3 / 3 / 1 / 3 / 1) |
| sky speed | the cloud scroll step was scaled to the tick's rate as well | `I76_SIM_TICK_SKY_REF`: 24 / s | cloud u / s (cutscene, cockpit): 1997 0.0240 / 0.0480, tick33 old **0.0300 / 0.0599** -> **0.0240 / 0.0480**, tick66 old 0.0150 / 0.0300 -> 0.0240 / 0.0480, driver 0.0200 / 0.0400 (n 3 / 3 / 3 / 1 / 3 / 1) |
| tracers denser | a LOOK difference, not a bug: each tracer is drawn once per frame (no double draw), the same constant-width line, but at 120 fps every frame redraws a streak 1 tick long, so each stretch of the path is lit ~4 frames running; 1997 and the driver draw short dashes with gaps | none | main-pass calls per frame 1 / 1 in every boot; records drawn per frame 1.0-1.5; segment 50cal 1997 4.2 m, tick33 3.3 m, tick66 10.4 m, driver 1.2 m (n 3 / 3 / 1 / 1) |

**New candidate `STRLKUP-tick19f-av.dll` md5 `2eb345d15c10430e1435c4e7cb596937`**
- Source: i76-everywhere `d664f91` (main), built with lab `builds\tick-av-20261019\make.ps1 -Rev d664f91 -Cand tick19f-av` (the MSVC recipe of s.1).
  It carries the crash lane's tick19f fix (47a2b3a, s.16), `I76_SHM_SUFFIX` (4c1b146), `I76_CURSOR_MAP_DGV=aw` (1ca6ba0),
  `I76_TERRAIN_LOD_A` / `_B` (d664f91) and this section's commits e9d8079, 7f3060d, aa86ec3. (A first build from 3f36d2d, 309bc2b7,
  was superseded before staging.) Not in it: the flame-factor / lip-clip lane (s.18, ed5c305), which reached main after the build.
- A second build, `run2\`, is section-identical (pecmp SAME): deterministic.
- Gate, install and staging: 17.9.

Lab only. The daily driver, the golden copy, the Downloads portable and the PC LAN copy were only read (the driver's presets, by
make-presets.ps1's md5 check). The owner was at the PC for part of the lane (his daily driver ran): every measurement boot was headless.

### 17.1 Harness

- Lab copies of this lane: `game-av` (a copy of game-tfx = game-wst: i76.exe 6319abf7, null renderers), `game-samecar-av` (a copy of
  game-samecar, the T06 strip), `game-tick-av` (a copy of game-tick; not used for results: dgVoodoo drew no frame on the private desktop).
- `tools\tick-av\av-run.ps1` one headless boot on the private desktop **`I76Lab-av`** (other lanes use I76Lab-wst), per-pid mute;
  `av-queue.ps1` runs a list; `av_live.py` stages (idle, real key messages, self-destruct); `av_tab.py` makes the tables.
- Lab twins `Strlkup-av1/av2/av3-lab.dll` (the source + the drive block; av3 = 3f36d2d). Their `Local\` blocks carry the tag `AV`
  (`builds\tick-av-20261019\av-names.py`, lab twin only) and the drivers run through `tools\tick-av\av_shim.py`, which maps the names.
  **Why:** four other lanes were booting headless games at the same time on the same block names and desktop. While they did,
  ~15 % of this lane's boots lost their game a few seconds in with no fault event and no proxy CRASH line (cause not found); after the
  isolation the loss stopped in the sign / guns / camera arms, and the queue retries a lost boot (`_lost\` keeps every one of them).
- Instrument `I76_AV_LOG=<path>` (simtick.c, lab, off by default; e9d8079 / 7f3060d): one line per drawn frame (camera eye and drawn
  forward row, orbit yaw 0x4c291c, camera callback, cloud u / v 0x507cd8 / 0x507c50, tracer records per pass with segment and
  cross-section, class-4 knock-offs via the class-table slot 0x4f7770, the engine's collision sounds at 0x434ebc, the sweep's sign
  sounds, early-tick and pending-key counters, the player's drawn position, the T05 autopilot flag) and music cue events at the exe's
  own entries (PlayCdTrack 0x423330, StopCdMusic 0x4233d0, pause 0x4234a0, unpause 0x4234e0). `I76_AV_VIEW=<sim s>:<view>` sets a
  camera view.
- Arms: **1997** = `e24`, the stock loop at 24 fps on a 1 ms tick (FRAME-BOUND-SYSTEMS' reference); `e24r` = e24 + the tick presets'
  music keys; **tick33 / tick66** = game-tick's `tick19-33` / `tick19-66` on the lab twin (every s.17 switch at its default);
  **old** = the same with the s.17 switches off (= tick19e); **driver** = game-tick's `p18-best-wide-balanced` (promotion 18).
- Captures: lab `captures\tick-av-20261019` (gitignored). Boots: 88 kept, 23 set aside in `_lost\` (lost games, the pre-isolation
  runs with a short log, the real-renderer copy, the first T06 tries without telemetry).

### 17.2 Sign sound ("about half the time ... does not play")

- **Where the sound comes from (static).** No sign sound is played by the knock-off itself (slot 9 0x46f9a0 calls no sound). It is
  the contact sound of physics_CollideBodyPair 0x434bb0: when the other body is not a vehicle and its class is 4 (breakables), it plays
  `vnvco3.wav` (0x4f1578) on the car through sound_PlayOnObject 0x4231f0 (0x434e5c..0x434ebc), before 0x461f70 applies the contact.
  So a post makes its sound only when the engine finds a contact with it.
- `I76_BREAKABLE_BOX=4` (tick presets and promotion 18) knocks off every post the car's box sweeps through, also when the engine
  found no contact. Promotion 18 gets most posts through engine contacts with `I76_COLL_WINDOW`, which needs a fixed step, so the tick
  presets cannot carry it (s.2). Under the tick the sweep did the knocking, silently.
- **Measured** (T05 Texas 13 / US 380 posts, 11 rams per boot at 20 m/s, wst-run's `signs` rams; knock-offs counted at the class-4
  slot, sounds at 0x434ebc and at the new call, voice starts by the sound census):

| arm | boots | knock-offs | by engine contact / by the sweep | engine contact sounds (vnvco3) | sweep sounds | vnvco3 voice starts logged |
|---|---|---|---|---|---|---|
| 1997 (e24, no breakable box) | 3 | 1, 1, 0 | engine 2 / 0 | 2 | - | 2 |
| tick33 old | 3 | 11, 11, 11 | 0 / 33 | 0 | 0 | **0** |
| **tick33** | 3 | 11, 11, 12 | 0 / 33 | 0 | **33** | 30 |
| tick66 | 1 | 11 | 1 / 10 | 1 | 10 | 10 |
| driver (p18) | 1 | 11 | 0 / 11 | 0 | (switch is tick-only) | 0 |

  - The census writes its line at most every 5 s; in each tick33 boot the last post fell 1.6 s before the end, after the last line,
    so 30 of 33 is the logging lag (every logged start matched a knock-off).
  - The stock loop at 24 fps knocks over almost no post at 20 m/s (the sign bug the box switch fixed); the posts it does knock over
    come with the sound, which is the 1997 behaviour the switch restores.
  - In this harness the driver's posts all fell by the sweep, silent too (n 1). The owner's "half the time" on the tick against the
    driver probably reflects his real driving (engine contacts with COLL_WINDOW in the driver); not measured. The switch acts under
    the tick only, as briefed; the same call would cover promotion 18's sweep if wanted.
- **Fix:** `I76_SIM_TICK_SIGN_SOUND` (simtick.c `st_sign_sound`, called from strlkproxy.c `sign_pend_run` for a sweep entry and
  `sign_sweep`'s immediate score): the sweep's knock-off plays `vnvco3.wav` on the car, as the engine would at a contact. 0 = silent.

### 17.3 Music ("doesn't seem to play consistently")

- **Cue sources (static):** in a mission the exe asks for music only at the mission start (PlayCdTrack(-1, 0) at 0x4037e1), on
  Replay (0x40454f), in the Options screen (0x49514b / 0x49529a) and from its watchdog (0x423400, called from the per-display-frame
  sound update 0x421407). No mission-script music action exists in this exe. Pause / unpause come from the Esc menu, movies and
  activation. None of these is in the gated sim block.
- **Measured** (`idle` boots, 150 s wall from launch, I76MUSIC_LOG + the instrument's cue events; same sim window per mission):

| mission | arm | boots | cues (exe entries) | track starts | started after the cue |
|---|---|---|---|---|---|
| T01 (run 2..14) | 1997 + retail rules (e24r) | 2 | 1, 1 (mission start) | track 2 | 31 / 47 ms |
| T01 | tick33 (retail + resume) | 2 | 1, 1 | track 2 | 47 / 125 ms |
| T01 | driver (non-retail rules) | 2 | 1, 1 | track 2 | 31 / 94 ms |
| T05 (run 6..14) | e24r | 2 | 1, 1 | 6, then 7 at +145.5 / +146.0 s (gapless) | 172 / 62 ms |
| T05 | tick33 | 2 | 1, 1 | 6, then 7 at +145.5 s | 31 / 47 ms |
| T05 | driver | 2 | 1, 1 | 6 (7 not reached in the window: no gapless, the next song waits for the exe's 60 s poll) | 31 / 32 ms |

  0 cues requested and not started in 12 boots (79-152 s of sim each).
- **The owner's own sessions** (game-tick `mciproxy.log`, read only; the 6 sessions after the s.14 install that are not gate / LAN
  runs): every cue was started, except one mission whose run starts at **track 1, the data track**: the proxy plays it as silence
  ("track 1 is the DATA track - silence, as the original disc gave"). Missions with WRLD 1: M06, S02, S06, and S01 in miss16
  (MUSIC-TRACK-MAP.md). That is the same under the driver.
- **So the silences are rules, not drops:** the data-track missions above; under the retail rules the end of a mission's run is
  followed by 0-60 s of silence until the exe's 60 s poll starts run 2..14 (MUSIC-RETAIL-INTENT s.1), where the driver's rules have
  that gap between every song instead. No fix: the tick does not change music.

### 17.4 Outside camera stutter when W is pressed in a cutscene

- **Cause (simtick.c st_render_wrap, read):** a script (FSM) camera is set inside the sim, so the tick draws it blended between its
  last two tick views. A key press runs an early tick (`I76_SIM_TICK_INPUT`). On that frame the objects' new segment starts from the
  pose they were about to be drawn at (st_early_from), but the camera's blend restarted at 0 from the OLDER view: the camera jumped
  ahead by the rest of the old tick and then crawled over the longer early segment while the car moved smoothly. The cockpit and
  chase views are camera modes computed every display frame from the drawn poses, which is why "not inside".
- **Measured:** T05's opening is a script-camera cutscene (the AI drives the player's car for ~8 s, 980+ blended frames per boot).
  W key messages through the game's own window procedure (PostMessage WM_KEYDOWN / WM_KEYUP, scan code 0x11, 0.45 s down / 0.55 s
  up from 3 s; the early tick sees the keyboard's own bits). A "stutter frame" = the eye's speed off the centred 9-frame median by
  more than 35 %.

| arm | boots | early ticks in the cutscene | stutter frames / s | stutter frames within 3 frames of an early tick |
|---|---|---|---|---|
| 1997 (e24, 24 fps) | 3 | - | 0.36, 0.95, 0.59 | - |
| tick33 old | 3 | 9, 6, 8 | 1.76, 1.66, 1.77 | **19 of 44** |
| **tick33** | 4 | 5, 6, 6, 8 | 0.47, 0.70, 0.70, 0.93 | **0 of 24** |
| tick66 old | 3 | 6, 5, 10 | 0.84, 1.07, 1.56 | 19 of 29 |
| **tick66** | 3 | 10, 9, 6 | 0.71, 0.60, 1.07 | 1 of 20 |

- **Chase view** (`I76_AV_VIEW` PRESET_VIEW_3 after the hand-over, the same W taps; ~2 000 chase frames per boot): stutter frames
  within 3 frames of an early tick 1 of 30, 1 of 18, 0 of 25 (tick33, n 3) and 1 of 16 (old, n 1): the chase camera already follows
  the drawn car. 1997 chase 0.04 / s (n 3). **Inside (cockpit) view:** the fix does not act there (no blended script camera in any cockpit
  frame); stutter frames within 3 frames of an early tick 5 of 56 (tick33, n 4) vs 0 of 42 (old, n 3), overall 0.72-2.01 vs
  0.91-2.28 per s: the cockpit eye carries the head sway, and this difference is inside the boots' spread.
- **Fix:** `I76_SIM_TICK_EARLY_CAM` (simtick.c `st_early_cam_from`): on the early frame the camera this frame would have drawn is kept,
  and the early segment blends from it to the new tick's view, as the objects do. 0 = the old blend.
- **Pending key releases:** a second suspect (a pending release that the tick's input pass never clears would borrow an early tick on
  every frame) was not seen: 0 frames with a pending release in 16 boots (~40 000 frames). Its guard `I76_SIM_TICK_PEND_ONCE` stays as
  a switch, **default off** (aa86ec3).

### 17.5 Death camera rotation

- **Cause:** the player's death (entity_Wreck 0x466180 -> 0x46638e..0x4663ab) sets view 0xfefe, orbit A 0x405b90, with
  track_yaw_delta 8: yaw += 8 x [0x4bc528] (-1 deg) per call (0x405c1c). The tick's cosmetic patch scaled that constant by
  display dt / T, i.e. to the TICK's per-second rate: 8 x 30 = 240 deg / s at 33.3 ms, 8 x 15 = 120 at 66.7 ms. 1997 at 24 fps: 192.
- **Measured** (T05, self-destruct 2 s after the hand-over: input_self_destruct 0x5367f9 = 1, read back; the orbit yaw 0x4c291c per
  drawn frame over the ~6 s orbit, all of it in gameplay frames):

| arm | boots | deg / s (orbit yaw) | deg / s (drawn forward row) |
|---|---|---|---|
| 1997 (e24) | 3 | **192.0, 192.0, 192.0** | 212.1, 184.1, 164.2 |
| tick33 old | 3 | **240.0, 240.0, 240.0** | 216.4, 234.0, 254.8 |
| **tick33** | 3 | **192.0, 192.0, 192.0** | 186.3, 189.4, 208.6 |
| tick66 old | 1 | 120.0 | 143.6 |
| **tick66** | 3 | 192.0, 192.0, 192.0 | 188.1, 179.6, 185.7 |
| driver (p18) | 1 | 160.0 (its 20 Hz grid) | 125.0 |

  The forward-row figure moves with the wreck's own motion; the orbit variable is the camera's angle itself.
- **Fix:** `I76_SIM_TICK_ORBIT_REF`: orbit A's two sites (0x405bd0 pitch, 0x405c1c yaw) get their own constant, display dt x
  `I76_SIM_TICK_REF_HZ` (24 / s), also on frames outside gameplay. The free-look keys (orbit B 0x4061e7 / 0x406233) and the map zoom
  keep the tick's rate (not reported). Against the driver the death orbit is now 1.2 x (192 vs 160): the driver's 20 Hz reference.

### 17.6 Sky speed

- **Cause:** the cloud scroll (u -= 1 / (1001 - s), v alike, per call of renderer_DrawClouds 0x405200) is the same kind of per-call
  constant; the cosmetic patch scaled it to the tick's rate. In the cockpit the rear mirror draws the dome a second time per frame
  (0x4459a1), so the cockpit rate is twice the cutscene rate in every arm.
- **Measured** (cloud u per wall second during gameplay, by camera; n 3 per arm unless stated):

| arm | cutscene (script camera) | cockpit (main + mirror) | death orbit |
|---|---|---|---|
| 1997 (e24) | **0.02400** | **0.04797** | - |
| tick33 old | 0.03001 (x 1.25) | 0.05995 | - |
| **tick33** | **0.02400** | **0.04795** | - |
| tick66 old (n 1) | 0.01501 (x 0.63) | 0.02998 | - |
| **tick66** | 0.0240 | 0.0480 | 0.0240 |
| driver (p18, n 1) | 0.0200 | 0.0400 | 0.0200 |

- **Fix:** `I76_SIM_TICK_SKY_REF`: the two cloud sites scaled by display dt x 24. The sky now moves at the 1997 rate; it is 1.2 x the
  driver's (the driver uses a 20 / s reference). `I76_SIM_TICK_REF_HZ=20` would match the driver, but it also moves the four s.14
  factors.

### 17.7 Tracers ("wider / thicker / denser ... maybe 2x")

- **No double drawing, no width change (measured).** In every boot of every arm the main pass (renderer_QueueTracers 0x442480) runs
  exactly once per drawn frame, and each live round's record is drawn once by it (1.0-1.5 records per frame). The mirror pass draws
  only into the mirror (0.6 calls per frame = the cockpit share). The 50cal's tracer is type 2: a line from the older point drawn 35 %
  of the way to the newer one (0x4425b8..), so it has no cross-section and the same line every frame; the quad types take their
  cross-section from constant offsets x a per-type size (0x441f48), not from the frame rate.
- **Segment (older -> newer point), 50cal, T05 guns at a parked car 12 m away:** 1997 4.23 / 4.26 / 8.45 m (n 3), tick33 3.23 / 3.27 /
  3.27 m (n 3), tick66 10.37 m (n 1), driver 1.23 m (n 1). The drawn line is 35 % of that: 1.5 m in 1997, 1.1 m at tick33, 3.6 m at
  tick66, 0.4 m under the driver. (FRAME-BOUND-SYSTEMS row 22 quotes 8.3 / 6.7 m for a 200 m/s round; this 50cal flies ~100 m/s.)
- **"Denser" is a look difference, not a bug.** 1997 (24 fps) and the driver (one 120 fps step per frame) draw a short dash that
  moves its own length or more each frame, leaving gaps (the line covers ~35 % of the path per frame). The tick draws, on every one of
  its 4 display frames per tick, a line 35 % of one TICK of travel long (1.1 m), whose head moves a quarter of a tick per frame
  (0.8 m): each stretch of the path is lit on ~1.4 frames running, against ~0.35 in 1997 (a 1.5 m dash every 4.2 m) and under the
  driver (0.4 m every 1.2 m) - about 4 x the coverage at tick33, ~4.4 frames running at tick66. That reads as a denser,
  brighter, thicker streak. The tracer fix of s.10.2 chose the tick-long segment (the stock streak at the tick's rate). A display-frame
  segment would give the driver's look; not built (owner's call).

### 17.8 T06 strip (game-samecar-av, tick33 preset, lab twin av3 = 3f36d2d, n 3)

- The 54 rows tick19e's strip had keep their verdict (0 changes). This run also produced the 8 rows of the 34 m/s ramp jump, which
  tick19e's strip did not have: gate PASS 25, FAIL 13; watch ok 11, OUT 1; INFO 12. Lab `emu\results\tick-fix-20261018\tick19f-av-t06-vs-p166.md`.
- Run because the camera blend changed; nothing in the sim block changed.

### 17.9 Build, install, staging, gate

- **Installed in game-tick** (read back 2eb345d1). tick19e is kept beside it as `STRLKUP.DLL.a08577c4-pre-19f` (the folder held tick19e: the crash
  lane's tick19f had been taken out again after its voided gate). Presets regenerated by `make-presets.ps1 -OwnerBest` in game-tick and the twin
  game-dd-20261003: tick19-33 57d13cd5, tick19-42 231f1534, tick19-66 bd9e6673 (the generator now writes `I76_CURSOR_MAP_DGV='aw'`,
  `I76_TERRAIN_LOD_A='96'`, `I76_TERRAIN_LOD_B='24'`; a diff against the previous files is exactly those three lines; the previous presets are in
  `presets\_pre-tick19f-av\`). tick19-33-lod32 and PLAY-TICK-LOD32.bat moved to `_superseded-lod32\` in game-tick and the twin. Launchers
  PLAY-TICK.bat = PLAY-TICK-33.bat (b4ce0baf), PLAY-TICK-42.bat (ab2416a6), PLAY-TICK-66.bat (4ecc09aa) copy `dgVoodoo.wide.conf` (dccd379a);
  the old ones are kept as `*.bat.pre-tick19f-av`. game-tick's dgVoodoo.conf = dccd379a.
- **Gate** (lab game-tick, physical console, owner away, coordinator's GATE GO; `run-gate.ps1 -Which 33,42,66,18 -NoHostMute -TwinDll` (the
  sp-fix rows' lab twin built from d664f91, 696ebff8); I76_SHM_SUFFIX=game-tick; per-pid mute; 60 s with no foreign i76 before each start):

| launcher | rows | result | run |
|---|---|---|---|
| PLAY-TICK.bat (tick19-33) | all | 19 PASS, **2 FAIL (row 4)**, 2 INFO; row 4 re-run after the harness fix below: **12 PASS 0 FAIL** | `autotest\runs\gate\20261019-203325`, `-213305` |
| PLAY-TICK-42.bat (tick19-42) | 2 3 5 6 | **8 PASS 0 FAIL** | `-210715` |
| PLAY-TICK-66.bat (tick19-66) | 2 3 5 6 | **8 PASS 0 FAIL** | `-211553` |
| PLAY-P18-BALANCED.bat (control) | 3 6 | **6 PASS 0 FAIL** | `-212438` |
| sp-fix rows (headless, game-sp) | M1a instant melee Scene 1 (Co-op) 30 s, M1b Tombstone 30 s, M2 Tombstone 3 AI 45 s | **3 PASS** | `queue-tickgaps\gate-20261019-203324.log` |

  - Proxy log, every tick boot (10 + 7 + 7): tick ON, `terrain-lod: split A x96.00, height-error B x24.00`, the aw cursor map, the s.17 line;
    0 NOT applied, 0 CRASH (tg-gate.ps1 now prints this check).
  - **Row 4 (save screen) under aw - found and fixed in the HARNESS, not the game.** The first run's YES wrote save003.cmp (slot 3) instead of
    the scratch bookmark (slot 18), and "the shell mouse follows the hand" read (304,301) for (300,300). gate-folder.ps1's Place-Ui knew only the
    4:3 picture (hand = 760 + 3 x UI x on 3440 x 1440), but aw with the wide conf maps the shell over the 16:10 picture (568 + 3.6 x UI x), so
    the gate's hand was up to ~19 UI px off and its row click picked row 3. The gate's own state restore put save003.cmp back (row S
    byte-identical, 36 files). Fix: Place-Ui tries a 4th candidate, the 16:10 picture, read back by the shell's own mouse like the others (used
    only when the first three fail). Re-run: every click read back within 1 px, SAVE x2 -> slot = owSlot = 18, NO writes nothing, YES writes
    save018.cmp and savegame.dir only, the modal arrow over the prompt, savegame.dir exact, S byte-identical. A player is not affected: under
    aw the pencil is drawn where the shell reads.
  - **Second harness bug, found in row 4:** gate-folder.ps1 `Run-Child` waits for `cmd /c`'s output pipe, and the per-pid mute watcher a child
    starts (start-mute-watch.ps1 -> Start-Process) inherits that handle and lives until the game exits, so the gate hung in the garage (21 min).
    For this gate `tools\tick-av\gate-watch-reaper.ps1` ended such orphaned watchers of game-tick games (16 times over the gate, the row-4 re-run and the pointer / LAN runs); the game stays muted by its
    own I76_MUTE=1 and tg-gate clears game-tick's stored mute at its end. Not fixed in start-mute-watch.ps1 (other lanes' infrastructure).
  - **'aw' pointer rows:** main menu (measure-cursor.ps1 -Aspect 16:10 on game-tick through PLAY-i76.ps1, presets tick19-33 and tick19-42, n 1
    each): where the shell lands minus the drawn pencil within 4 px at the 7 picture points (the two runs identical to the pixel; outside the
    picture the pointer clamps to its edge, as in CURSOR-FIX-ON-18 s.6); save screen and its modal prompt: row 4 above; Esc menu: row 5 HIT
    where drawn on 33, 42 and 66 (conf frame (2326,1338), read back). The garage was reached by the gate's bookmark route (row 2, 3 of 3) and
    row 4 (2 of 2); a separate garage reminder popup was not met by any row.
- **LAN console check** (tools\sp-fix\lan-console.sh under with-lock, game-tick through PLAY-TICK.bat + lab copy game-lanmerge-b, I76_MUTE):
  host + joiner n 2 (both games list both players at the same places), 3 lone hosts, 0 CRASH. Every run hosted **arena index 0** (a stock
  arena): the probe's clicks also assume the 4:3 picture, so the list never scrolled to Hope Springs (4 AI) or Tombstone. **The AI arena
  under aw was not tested** (owner check).
- **Candidate folder** re-staged: tick19e's set to `_superseded-tick19e\`; STRLKUP.DLL 2eb345d1, the three presets, PLAY-TICK / -33 / -42 / -66
  .bat; dgVoodoo.tick.conf, PLAY-TICK-LOD32.bat and tick19-33-lod32 removed; README (files, gate, row text, rollback, owner checks), MD5SUMS
  65 files.

### 17.10 Not done, and why

- **Music** was not listened to. The arms ran on game-av (music level 6; the owner's copy has 7, both above the retail gate 2); the
  real-renderer copy drew no frame on the private desktop (its 3 boots are in `_lost\real`).
- **Signs:** the stock loop knocks over almost no post at 20 m/s, so the 1997 row has 2 knock-offs; the driver's engine contacts in
  real driving (COLL_WINDOW) were not reproduced (its 11 harness knock-offs were all by the sweep). The switch is tick-only.
- **Lost boots:** ~15 % of the boots before the isolation lost their game a few seconds in with no fault and no proxy CRASH line; the
  cause was not found (the other lanes' tools stop only their own pids). None were used.
- The camera stutter metric is a proxy for what the eye sees; not judged by eye. The tracer look was not seen either.
- The flame-factor / lip-clip lane (s.18, ed5c305) landed in main after this build: not in tick19f-av (pending for the next build).
- **LAN AI arena under aw** (Hope Springs (4 AI)): the LAN probe's arena pick assumes the 4:3 picture; only arena index 0 was hosted.
- A garage reminder popup was not met by any gate row (the garage itself, the save screen and its modal prompt, and the Esc menu were).
- The T06 strip ran on the lab twin of 3f36d2d; d664f91 adds only the terrain A / B switches (render detail), so it was not repeated.
- The two harness bugs (Place-Ui's 4:3-only candidates in the LAN probe, the mute watcher's inherited pipe in start-mute-watch.ps1) are fixed
  only where this lane needed it (gate-folder.ps1 Place-Ui) or worked around (the reaper, this gate only).

### 17.11 Still needs the owner's eyes and ears

1. Sign posts on PLAY-TICK: the hit sound every time.
2. A cutscene (T05's opening): press and release W: no stutter. Inside and chase views as before.
3. Death camera: should turn at the 1997 rate (192 deg / s; the driver turns at 160).
4. Sky: 1997's speed (the driver's sky is 0.8 x that).
5. Tracers: if the tick's streak still reads as too dense, say so: a one-display-frame streak (the driver's look) is a small change.
6. Music: the silent missions (M06, S02, S06, S01) are the original disc's data track; after a run ends, retail waits up to 60 s.
7. The driver's wide menu on PLAY-TICK ('aw'): pointer on the pencil in the menus, the garage, the save screen (save over a bookmark you do not
   need first) and the Esc menu; and a LAN AI arena (Hope Springs (4 AI)) hosted from PLAY-TICK, which the lab could not reach (17.9).
8. Which tick PLAY-TICK should be: 33, 42 or 66 (PLAY-TICK-33 / -42 / -66.bat).

## 18. tick42 before promotion: the lip clips, the flame factor at 41.667 ms (2026-10-19 evening, tick42 lane)

The brief, from TWO-CLOCKS-2026-10-19 s.6: before the 41.667 ms tick is promoted, trace the "lip clips" (5 of 58 lab jumps at a
41.7 ms step against 0 of 70 retail; tick42 3 of 3 on the 56 m/s centre line), and run the flame calibration at 41.667 ms.

**Results in short.**
- **The lip clips were the harness placement, not the tick and not the engine at 41.7 ms.**
  - The two-clocks placement wrote the car's rotation, then sent the trainer's TELEPORT (which zeroes the body rates). When a physics
    step ran in between, it turned the car by the rates left from the previous jump's crash. Those are clamped at pi rad/s, so the
    error was up to pi x step: 7.5 deg at 41.7 ms (measured 7.50 deg in 9 placements, each after a crash with a yaw rate of 3.14).
  - The velocity still pointed down the run, so the car slid 2.6-6.0 m/s sideways onto the ramp face, got 0-12 m/s of lift
    instead of 15.4-15.7, and ran 1.9-3.9 m under the face. **12 of the 13 placements more than 2 deg off clipped; 0 of 249 within
    2 deg did** (179 lab, 70 retail).
  - With the placement verified (18.2), **tick42 clips 0 of 60 jumps and the stock loop at 24 fps (41 / 42 ms frames) 0 of 60**,
    plus 0 of 6 each on the 56 m/s centre line. Take-off 52.67 +- 0.88 against 52.68 +- 0.87 m/s, apex 11.10 +- 0.37 m in both,
    distance 222 +- 35 against 225 +- 34 m (n 60 each, 10 boots).
  - Control: the same jumps placed 7.5 deg yawed clip in both arms (stock 24 fps 5 of 5, tick42 3 of 3; a fatal clip ends the boot).
    An oblique, sliding car goes into the T05 ramp face in the stock loop too.
  - **No proxy change for the lip.** The fix is in the lab harness (`tools\tick42\t42_suite.py` `place_verified`). Other lanes'
    copies of phys-suite (two-clocks `tc_suite.py`, `box-spec\phys-suite.py`) still place the old way.
- **Flame at 41.667 ms.** The fixed factor 2.8 under-delivers there. The engine's amount per application is max(1, int(R x T)) = 1
  at both 33.3 and 41.7 ms (Gas Launcher, R 30), so the tick applies 24 units a second instead of 30. On the T05 car it asks
  **67.7 per second of burning against 84-85 at 33.3 / 66.7 ms**.
  - **The factor is now rate-aware by default** (i76-everywhere `ed5c305`). Every tick length asks the same flame damage per second:
    **84.8 / 84.7 / 85.3 per s at 33.3 / 41.667 / 66.7 ms (n 3 each)**. The factor is 2.8 at 33.3 and 66.7 ms (s.12's calibration,
    unchanged) and 3.5 at 41.667 ms.
  - The T05 car dies 8.2-11.5 s after the first contact at every tick (one early kill per arm in two of the arms, s.14.3's roll),
    against 10.4 / 11.8 s for the 1997 coupling (s.12: 11.2 s, n 6).
- The four s.14 factors are exactly 1 at 41.667 ms. Since `ed5c305` their wrappers are not installed there at all (log line in 18.4).
- The early tick, tracers, sustained sounds and sign knock-off behave at 42 as at 33 (18.4, n 1 each).
- **For the candidate (18.5):** tick42 needs no preset key beyond tick19-42's, but it needs a proxy built from `ed5c305` or later
  for the flame default. tick19f-av (2eb345d1, from d664f91) does not have it and runs tick42 at the fixed 2.8.

Lab only. The daily driver, the golden copy, the Downloads portable, the PC LAN copy and game-tick were only read.
- Every boot was headless, on a private desktop `I76Lab-t42`, with I76_MUTE=1 plus the per-pid mute watcher.
- Lab copies: `game-t42` (= game-tc: the emulator save's car, for the jumps and the harness rows) and `game-t42f` (= game-wst: the
  T05 car with the Gas Launcher, s.12's copy; game-t42's car has no flamer).
- The owner's game (game-tick) ran during the session. The lab twin `builds\tick42-20261019\Strlkup-t42-lab.dll` (6652a4f3) names
  its blocks `Local\I76TrainerT42`, `I76TelemetryT42`, `I76SimTickT42` and `I76RhDriveT42`.
  - `t42-run.ps1` refuses a DLL without the T42 trainer name.
  - `t42_drive.py` appends the suffix to any `Local\I76...` mapping a tool in its process opens without one. flame_live.py and
    combat-live.py open the default names: run from wst-run they would reach the owner's trainer block.
- Twin source: i76-everywhere `aa86ec3` + this lane's change (the code of `ed5c305`) + the two-clocks lab hunks (drive block,
  headless-active).
- Paused 20:27-22:03 for the candidate lane's console gate.
- Tools: lab `tools\tick42\` (`t42-run.ps1`, `t42-queue.ps1`, `t42_suite.py`, `t42_drive.py`, `lip_scan.py`, `t42_tab.py`,
  `flame_rate.py`).
- Queue: `queue-tick42\q1.txt`. Captures: lab `captures\tick42-20261019` (gitignored; `v1-placement\` = the first placement
  version, `v1-nogas\` = flame boots on the car without a flamer, not used). Tables: lab `emu\results\tick42-20261019\`.

### 18.1 The clips in the two-clocks captures (re-read, lab `tools\tick42\lip_scan.py`)

Clip = the car more than 1 m under the ramp face (surface y = 20.0 + 0.28 (6900 - x), from clean jumps) between x 6876 and 6898.
`yaw0` = the heading at the first recorded state after the placement.

| two-clocks set | arm | clips | heading off at placement | side slip before the foot m/s | under the face m | ramp lift vy m/s |
|---|---|---|---|---|---|---|
| t05sw (centre line) jump 3 | tick42 | 3 / 3 boots | +7.50 | -4.36 | 3.50 | 9.94 |
| t05sw jump 3 | e30 | 3 / 3 | +4.43, +5.94, -6.12 | 4.4-4.9 | 3.3-3.5 | 10.3-11.0 |
| t05sw jumps 2, 6 | p18 | 2 | +-7.50 | 4.4-6.0 | 3.5-3.9 | 0 |
| t05j (jittered) | tick42 | 2 / 10 | -2.68, -7.50 | 2.6, 4.3 | 1.9, 3.7 | 11.9, 10.0 |
| t05j | p18 | 2 / 12 | +-7.50 | 4.1-4.3 | 3.6-3.7 | 0, 10.0 |

- **The heading error is the previous jump's yaw rate x one step.** In every case the yaw rate at the end of the previous phase times
  the step equals the error: 3.1415 x 41.7 ms = 7.50 deg; -1.121 x 41.7 ms = -2.68; e30 2.343 x 33 ms = 4.43. The step falls
  between the rotation write and the TELEPORT.
- **Why tick42 was 3 of 3 on the centre line and e24 0 of 6.** tick42's jump 2 (50 m/s) ended spinning at +pi rad/s and e24's did
  not, and the boots repeat to the digit. Jump 3 at 56 m/s was therefore always placed 7.5 deg off under tick42.
- **The two-clocks counts, read again.** Its "5 of 58" lip clips at 41.7 ms were:
  - 4 mis-headed placements (tick42 2, p18 2);
  - 1 e24 record that ends 0.2 s after a normal take-off at 51.9 / 14.5 m/s (`tc_analyse.py` read the truncated flight as a clip).
- Pitch and suspension state entering the ramp do not separate clips from clean jumps. Clipped cars entered with pitch sd 0.001-1.5
  deg; clean ones with up to 0.4 deg and the lip's 0.52 rad/s pitch kick.
- **What a clip is.** The yawed, sliding car's first face step rises 0.35-0.43 m instead of 0.57-0.66 m, and the side speed jumps
  (-7.4 to -11.6 m/s). From the second face step the car is under the surface (airborne flag set, clearance 0.5 m), and it leaves
  through the face at the lip (vy -11 m/s) into the channel.
- **The first verified placement (v1) still clipped once in 9 tick42 jumps** (r1 #3, heading -0.38 deg). A placement right after a
  crash carried the crash's contact into the first step: pitch / roll rates 1.36 / -0.68 rad/s on the first frame, then a nose
  landing and a 3.5 deg, 2.5 m/s slide into the ramp. It is the same mechanism (side slip), from a different leftover. The final
  placement holds the car still in the air first (18.2).

### 18.2 The verified placement (t42_suite.py `place_verified`)

1. The trainer holds the car at the spot with FREEZE_POS (position held; velocity and body rates zeroed every frame) for 0.4 s,
   while the rotation is written. Placed 1.5 m above the road, it touches nothing.
2. Then it is released and TELEPORTed with the speed.
3. The first two telemetry frames must show the heading within 0.25 deg, every body rate under 0.05 rad/s and side speed under
   0.3 m/s; otherwise steps 1-3 repeat (up to 5 times).

Every placement of the final runs on a live car passed on the first try (144 of 144; the yawed controls are checked against their own 7.5 deg). The 12 that failed all 5 tries came after a fatal clip in the yawed control, with the car already dead.

### 18.3 Placed jumps with the verified placement (T05 aaramp4, 150 m before the foot, throttle held; `t42_tab.py`)

Jittered set (t05j: 56 +- 0.5 m/s, +- 0.5 m lateral, seeded by the tag; r1 / r2 = the two-clocks sets), the same placements in
both arms:

| arm | jumps (boots) | lip clips | made it | take-off m/s | vy m/s | apex m | distance m |
|---|---|---|---|---|---|---|---|
| e24 (stock loop, 24 fps: 41 / 42 ms frames) | 60 (10) | **0 / 60** | 60 / 60 | 52.68 +- 0.87 | 14.75 +- 0.24 | 11.10 +- 0.37 | 225 +- 34 |
| **tick42** | 60 (10) | **0 / 60** | 60 / 60 | 52.67 +- 0.88 | 14.75 +- 0.25 | 11.10 +- 0.37 | 222 +- 35 |
| e24, placed 7.5 deg yawed (control) | 5 (2) | **5 / 5** | 0 / 5 | - | - | - | - |
| tick42, placed 7.5 deg yawed (control) | 3 (2) | **3 / 3** | 0 / 3 | - | - | - | - |
| e24, centre line 45 / 50 / 56 x 2 | 6 (1) | 0 / 6 | 2 / 6 | 47.59 +- 3.93 | 13.32 +- 1.10 | 9.11 +- 1.51 | 131 +- 34 |
| tick42, centre line | 6 (1) | 0 / 6 | 2 / 6 | 47.58 +- 3.94 | 13.32 +- 1.10 | 9.11 +- 1.51 | 131 +- 34 |

- **Before / after at tick42.** Before, on the two-clocks harness: 5 lip clips in 20 jumps (t05j 2 / 10, t05sw 3 / 10). After, on
  the verified harness: **0 in 66**, and 0 in 66 for the stock 24 fps loop.
- Jump distance and apex are unchanged within the spread. The arms differ by 0.01 m/s at take-off. The jittered set takes off
  inside the retail 41-44.5 ms cells (51.3-52.8 m/s, 10.7-11.8 m; TWO-CLOCKS s.4.3).
- 0 of 132 verified lab jumps at a 41.7 ms step and 0 of 70 retail: **there is no lip-clip difference to explain.** A constant
  41.667 ms step does not clip where an alternating 41 / 42 ms frame does not (the centre-line set gives the same outcome jump by
  jump), and nothing in the tick's collision ordering or sign sweep touches the ramp contact.

### 18.4 Flame damage at 41.667 ms, and the rate-aware factor (T05 car, s.12 protocol `flamepn4p10`; `tools\tick42\flame_rate.py`)

The player's Gas Launcher was held at the nearest T05 car, 4 m, the car 10 deg nose up. "Asked / s" is the flame damage the target
car was asked to take (combat log `dmg_req_taken`) divided by the time from the first application to the kill. s.14.3 showed that
health "lost" books the wreck code's whole loss on the killing call, so asked / s is the steady measure; lost / s is printed for
comparison with s.12.

| arm | factor per application | boots | hits / s | **asked / s burning** | lost / s | kill after first contact s |
|---|---|---|---|---|---|---|
| 1997 coupling (stock 20 fps, mirror on) | - | 2 | 78.8, 79.4 | **79.1, 79.4** | 94.5, 76.3 | 10.4, 11.8 |
| tick42, fixed 2.8 (s.12's default) | 2.8 | 3 | 24.2 | **67.7, 67.7, 67.7** | 85.4, 64.1, 83.8 | 10.3, 13.8, 10.3 |
| **tick42, rate-aware (new default)** | 3.5 | 3 | 24.0-24.4 | **84.7, 84.1, 85.3** | 103.1, *301.6*, 104.2 | 9.5, *2.6*, 8.2 |
| **tick33, rate-aware** | 2.8 | 3 | 30.2-30.6 | **84.6, 85.5, 84.4** | 105.3, *245.4*, 91.1 | 8.4, *3.5*, 10.6 |
| **tick66, rate-aware** | 2.8 | 3 | 15.2-15.3 | **85.5, 85.5, 85.0** | 128.3, 82.9, 86.6 | 7.3, 11.5, 10.8 |

*Italic*: s.14.3's early kill (the instant-kill roll on a destroyed component; stock).
- **Every tick hits once per update.** Hits / s = 1 / T, with 1 unit per application at 33.3 and 41.7 ms and 2 at 66.7 ms. So the
  units per sim second are 30, 24 and 30. That is why one fixed factor fitted 33.3 and 66.7 ms but not 41.667 ms (2.8 x 24.2 =
  67.7).
- **The rate-aware factor** (strlkproxy.c `flame_dmg_factor`, simtick.c; `I76_SIM_TICK_FLAME_DMG` unset or `auto`):
  - Each application a = max(1, int(R x T)) is scaled to what a 1997 pass at the reference frame (T_ref = 1 / I76_SIM_TICK_REF_HZ =
    41.667 ms) computed, per sim second.
  - factor = G x a_ref / (a x T_ref / T), with a_ref = max(1, int(a x T_ref / T)) and G = `I76_SIM_TICK_FLAME_DMG_REF`, default 3.5.
  - G = 2.8 / 0.8 keeps s.12's car calibration at 33.3 and 66.7 ms exactly. The factor is 3.5 at 41.667 ms, so the asked rate is
    G x 24 = 84 per s at every tick length, measured 84.6 +- 0.5 (n 9).
  - a_ref computed from a alone equals int(R x T_ref) for every stock flamer and difficulty (R = 15 / 30 / 45 / 60 x 0.75 / 1 / 2:
    11.25 .. 120) at all three tick lengths (checked by hand for all 9 values). So FlameThrower, Napalm and Pyro-Tomic keep their
    1997-at-24-fps ratios to the Gas Launcher.
  - A number for `I76_SIM_TICK_FLAME_DMG` is still a fixed factor, as before.
  - Log line, tick42: `sim-tick: flame damage rate-aware (I76_SIM_TICK_FLAME_DMG unset / auto): G 3.500 (I76_SIM_TICK_FLAME_DMG_REF) at the 1997 pass of 41.667 ms; per application x 3.500 at amount 1, x 3.500 at 2, x 3.500 at 3 (s.18)`.
- **Against 1997.** The ticks ask 84.7 per s against the stock 20 fps loop's 79.1 / 79.4 (n 2, +7 %). s.12 calibrated on health lost
  (82.0 / s, n 6), which is noisier. The car dies in about the same time: 8.2-11.5 s at the ticks without the early-kill regime,
  10.4 / 11.8 s at 1997. Matching 79 asked / s exactly would take G = 3.3; G 3.5 is kept so that tick33 and tick66 stay as
  calibrated and gated in s.12 / s.14.
- **The bar** (T05 road-closed bar, `flamepp10`, 8 m, 10 deg nose up; box switch on, flame fix on): tick42 at 3.5 deals **1400.1
  per sim s (n 2, both)**, the same as tick33 / tick66 at 2.8 in s.12 (1401.5 / 1402.3). 1997 (stock 20 fps) deals **669.2** (n 1,
  = s.12). So the bar burns about twice as fast as in 1997 at every tick length, as s.12 found. That gap is in the contact (the car
  gets half the hits per update that the bar gets), not in the tick length.
- **The four s.14 factors at 41.667 ms.** They were x 1.000008, and their wrappers were installed. Since `ed5c305` a factor within
  0.1 % of 1 is exactly 1 and installs nothing. The log line in every tick42 boot:
  `tick-factors: under the tick; ref 24.0 / s; hazard x 1.000 (0/4 steps, class-damage call 0/1), scrape repeats x 1.000 (0/2 collision calls), wreck roll pass 1.000 (0/1), radar turn x 1.000 / proportional x 1.000 (0/2)`.
  At 33.3 / 66.7 ms they are unchanged (0.8 / 1.6).

**The s.9 / s.10 harness rows at tick42 (n 1 each, headless):**

| row | measure | tick42 | reference (s.9 / s.10, tick33) |
|---|---|---|---|
| early tick on a key (T06, 40 steer-key toggles) | key -> first drawn frame ms: median, p90, max | **4.2, 8.2, 8.7** (40 / 40; 34 early ticks) | 4.7, 7.9, 9.1 |
| tracers (T13 idle + god 60 s, I76_SIM_TICK_TRCLOG) | tracks, shown / alive, segment | **10 tracks, 1.00, 8.34 m** (one 41.7 ms tick at 200 m/s), first-frame segment 1.23 m | 1.00, 6.67 m (one 33.3 ms tick) |
| sustained sounds (T06 strip, I76_SOUND_CENSUS) | starts / sim s, sustained-loop starts / sim s | **0.74, 0.23** (keep-alives held 4026) | 0.82-0.90, 0.22-0.30; stock 30 fps 0.89 / 0.91, 0.28-0.32 |
| sign posts (T05, 20 m/s rams) | knocked off, drawn gap at the knock-off m | **11 / 11** (all by the sweep), median -0.13 (-0.16..-0.01), 0 timeouts | 33 / 33, -0.09 (-0.16..-0.01) |

Only 11 of the planned 22 rams ran in the sign boot. The second ram set found 4 targets, so n is 11.

### 18.5 What the candidate needs for tick42

- **Proxy.** The flame default at 41.667 ms needs a build from i76-everywhere `ed5c305` or later. tick19f-av (2eb345d1, built from
  d664f91) predates it: there, tick42 runs the fixed 2.8 and asks 67.7 per s (-20 %).
  - Without a rebuild, the same 84.7 at 42 comes from adding `I76_SIM_TICK_FLAME_DMG = '3.5'` to tick19-42 only. A fixed factor
    applies at that one tick length; it must not go into tick19-33 / -66.
  - With an `ed5c305` build, leave `I76_SIM_TICK_FLAME_DMG` unset in every preset. A fixed number set there would override the
    rate-aware default.
- **Preset keys for tick42.** tick19-42 as made by make-presets.ps1 (`I76_SIM_TICK_MS = '41.667'`, `I76_SIM_TICK_INPUT = '1'`, the
  rest of the tick19-33 set) needs nothing more, because every s.18 default is right at 42 with its key unset:
  - `I76_SIM_TICK_FLAME_DMG` unset (rate-aware); `I76_SIM_TICK_FLAME_DMG_REF` unset (3.5);
  - `I76_SIM_TICK_REF_HZ` unset (24: the four s.14 factors and the flame reference both fall on 41.667 ms);
  - `I76_SIM_TICK_{HAZARD,SCRAPE,WRECK,RADAR}_FACTOR` unset (auto = exactly 1 at 42);
  - `I76_SIM_TICK_FLAME_AGE` unset (20 Hz: at 41.667 ms the stream ages on every tick, stream 18.62-18.63 segments in every boot).
- **The jump.** The physics at 42 is unchanged, and no lip-clip patch is needed or made.

### 18.6 Not done, and why

- **No retail or emulator run.** The retail comparison is TWO-CLOCKS s.4.3's memtrace cells (0 of 70).
- **No crest descents (the owner's approach) at 42 with the new harness.** A descent is driven, not placed, so the placement bug
  never applied. TWO-CLOCKS s.4.2 had tick42 1 of 1 and e24 1 of 1 cleared.
- **The jittered set did not stress the yaw at a driven approach.** How large a slide a player needs to clip the ramp was not swept.
  2.6 m/s of side slip (2.7 deg) clipped once and 4.3 m/s every time.
- **The flame on other flamers, AI flamers and difficulties** was not measured. The rate-aware factor's other-weapon behaviour
  follows from the code (18.4); n is 0 in game.
- **1997's asked rate has n 2.** s.12's six 1997 boots have no asked column in this form.
- **The sign row ran 11 rams, not 22.**

## 19. The tick range: what 1997 ran, one launcher per value, the table to choose from, a user override (2026-10-20, tick-range lane)

The owner (verbatim): "if we're doing only one [tick] and it's based around what original variable framerate would be on hardware, give me a
range of tick sizes to try to select the exact perfect one that I recommend, and provide an affordance if none currently exists for end users
to select their preferred tick in the range for their taste with an explanation of what they want (of course that breaks multiplayer so maybe
not too prominent)."

**Results in short.**
- **The range to try is 36-47 ms, with 41.667 ms as the physics-faithful centre** (19.1). The periods we have measured put 1997 play on a P133 /
  P166 between 35.5 ms (lowest detail, on the T05 lip) and 48.1 ms (640x480). A frame of 50 ms or more is not one car step: the stepper splits it
  (count = floor(dt x 20) + 1), so 50 is not in the range. Launchers **PLAY-TICK-36 / -39 / -42 / -44 / -47** (47 = 46.875 ms), plus the
  existing outliers -33 and -66.
- **New proxy STRLKUP-tick19g `adc4fd4932e6e843277195e043a64e3b`** (main `64d9361`: tick19f-av + `ed5c305` rate-aware flame factor + the
  overnight lane's network pools `60dce76` / `e3934e3`). Built with lab `builds\tick-range-20261020\make.ps1`; the run2 build is
  section-identical (pecmp SAME). Installed in game-tick with tick19f-av kept beside it as `STRLKUP.DLL.2eb345d1-pre-19g`. tick19-42 no
  longer carries the interim `I76_SIM_TICK_FLAME_DMG = 3.5`.
- **What changes across 36-47 ms (19.3):** the bounce tempo, exactly in proportion to the tick (heave half period = 7 car steps: 0.252 s at 36,
  0.292 at 41.667, 0.328 at 46.875; the depth does not change). The jump moves a little, monotonically: take-off -0.56 / -0.30 / +0.18 /
  +0.46 m/s and apex -0.23 / -0.13 / +0.07 / +0.20 m at 36 / 39 / 44 / 46.875 against 41.667 (paired, n 24); that is under one sd of a
  jump's own spread (0.7-1.0 m/s), and every value sits inside the retail cells (51.1-52.8 m/s, 10.6-11.8 m). Flame asks 84.5-87.6 per s at
  every tick (n 2 each). Key -> drawn frame is 4.5-5.3 ms median at every tick (n 40 each; the early tick). **So the choice inside the range is
  mostly the bounce, and 41.667 is the value that matches the 1997 coupling everywhere (s.18: the stock loop to the digit).**
- **One thing does not scale above 41.667:** the wreck debris / blast roll can pass at most once per pass, so at 44 / 46.875 ms a wreck rolls
  22.7 / 21.3 times a second instead of 24 (-5 / -11 %; log line `wreck roll pass 1.000`). Hazard, scrape and radar scale up (1.056 / 1.125).
- **User override, not in the game menus (19.4):** `PLAY-TICK.bat <ms>`, or a `tick-ms.txt` beside it with one number, replaces the tick;
  `PLAY-TICK-CHOOSE.bat` explains the tick and asks. 16.7-66.7 ms only; anything else is refused before the game starts. Tested headless by
  reading the proxy's own tick line: argument n 2, file n 2, CHOOSE n 3, refusals n 2, plain n 1, every one-value launcher n 1.

Lab only. The daily driver, the golden copy, the Downloads portable and the PC LAN copy were not touched (the LAN copy's game ran all session
and was not touched; every game of this lane had `I76_SHM_SUFFIX=<its folder>`, its own private desktop, `I76_MUTE=1` and the per-pid mute
watcher; the persisted mutes of the five lane copies were cleared at the end). No network game was started. No console gate was needed.
- Copies: `game-trng-a` / `-b` (= game-t42: the emulator save's car) for jumps, bounce and latency; `game-trng-f` / `-g` (= game-t42f: the T05
  car with the Gas Launcher) for flame; `game-trng-play` (= game-tick with tick19g, minus `_ahk` and `i76wheel.exe` so no input helper ran on
  the private desktop) for the launcher tests.
- Lab twin `builds\tick-range-20261020\Strlkup-tr1-lab.dll` `1cf37a6f` = 64d9361 + the drive block, with the drive block's mapping also
  through `shm_name` (`tr-names.py`), so all four blocks take `I76_SHM_SUFFIX` and four copies ran in parallel.
- Tools: lab `tools\tick-range\` (`tr-run.ps1`, `tr-queue.ps1`, `tr_tab.py`, `launcher-test.ps1`, `make-launchers.ps1`); `tools\tick-finish\
  make-presets.ps1 -OwnerBest` now writes the range (`-TickRange`). Queues `queue-tickrange\`. Captures `captures\tick-range-20261020`
  (gitignored; `tr-table.json` = the tables below).

### 19.1 The range, from the records

| step length | where | record |
|---|---|---|
| 26.8 / 31.1 ms | retail P166 lowest detail (the gold standard): melee / T05 | HARDWARE-MATRIX |
| 31.0 / 33.0 ms | the same on the T05 lip, two cells (ref-r166low / r166low) | TWO-CLOCKS s.4.3 |
| 31.25 / 46.875 ms (mean 41.7) | the stock 20 fps loop on Windows 10's 15.625 ms GetTickCount, the owner's 2026-10-03 daily: one 46.9 ms step (80 %) or 2 x 31.25 | FIX-INVENTORY-2026-10-17 (stock20), FFB-DATA-AUDIT |
| 32.0 / 35.5 / 37 ms | retail P133 lowest: melee / T05 lip / T05 on the ground | HARDWARE-MATRIX |
| 36 / 39.0 ms | retail P166 low + mirror + terrain textures (r166lmirtex): melee (n 3) / T05 lip | HARDWARE-MATRIX, TWO-CLOCKS s.4.3 |
| 37.7 ms (2-3 substeps) | retail P166 developer default (r166p3) on the lip | TWO-CLOCKS s.4.3 |
| 38.9 / 39.5 / 41.0 ms (mean step; sim_dt p50 41.0 / 40.0 / 42.0) | the owner's own logged retail P166 sessions in 86Box, T05, 2026-10-19 (owner-20261019-1659 / -1622 / -1652) | lab emu\results\memtrace\owner-20261019-*\summary.md |
| 41 / 42 ms | e24: our exe's stock loop at 24 fps, the 1997 stand-in | FRAME-BOUND-SYSTEMS, s.18 |
| 41.0 ms | Gold P133 lowest (g133low) on the lip | TWO-CLOCKS s.4.3 |
| 41.5 ms per substep | retail P133 developer default (r133p2): 2 substeps of ~41.5 ms (frames ~90 ms) | HARDWARE-MATRIX |
| 43.8 / 44.5 ms | r166m6 / r133p2 on the T05 lip | TWO-CLOCKS s.4.3 |
| 45.9 / 48.1 ms (21.8 / 20.8 fps) | the cells nearest the owner's 1997 settings: r166m6mir (480x360, mirror) / r166m5 (640x480, no mirror); the owner's 640x480 + mirror is 46-48 ms by the filter maths | FRAME-BOUND-SYSTEMS, TWO-CLOCKS s.7 |
| < 50 ms | the longest single car step: from 50 ms the stepper takes 2 substeps of dt / 2 (a 50 ms tick would be 2 x 25 ms) | TWO-CLOCKS s.1, HARDWARE-MATRIX |

- Not found in our records: a P200 measurement (none was run), and a measured real-hardware (non-emulated) 1997 frame time. The emulated P166
  runs software rendering about 20 % fast (EMU-MEMTRACE s.9.5, cited in HARDWARE-MATRIX), so real period frames may sit a little longer
  than the emulator cells; that pushes the long end, not the centre.
- Chosen values: **36** (the fast end of period play at playable detail), **39** (the owner's own logged sessions), **41.667** (the 1997
  coupling; the centre), **44** (medium detail / the developer default's lip step), **46.875** (the owner's 1997 settings and the stock 20
  fps single step; named 47). 33.3 (the P166 lowest-detail gold standard) and 66.7 (the 15 fps design) stay as the outliers.

### 19.2 Build, presets, launchers

- STRLKUP-tick19g as above. PLAY-TICK-NN.bat for NN = 33 / 36 / 39 / 42 / 44 / 47 / 66 (lab `tools\tick-range\make-launchers.ps1`), each
  launching `tick19-NN.psd1` (make-presets.ps1 -OwnerBest -TickRange: tick19-33 with `I76_SIM_TICK_MS` changed and Name / Summary naming the
  value and its 1997 evidence; the generator refuses a preset that carries `I76_SIM_TICK_FLAME_DMG`).
- Presets (md5): 33 57d13cd5 (unchanged), 36 bee9382b, 39 b0c3ab77, 42 97f712ac, 44 f95df0a0, 47 8dff5d4d, 66 bd9e6673 (unchanged).
- Installed in game-tick (proxy, presets, launchers, PLAY-i76.ps1; previous launchers kept as `*.pre-tick19g`, presets in
  `presets\_pre-tick19g\`) and in the twin game-dd-20261003 (presets, launchers, PLAY-i76.ps1; the twin keeps the driver's proxy 33211f11 as
  before, tick19g staged beside it as `STRLKUP.DLL.adc4fd49-tick19g`). Candidate folder re-staged (README, MD5SUMS 75 files), tick19f-av's
  set in `_superseded-tick19f-av\`.

### 19.3 The table (headless; T05 placed jumps with s.18's verified placement, 56 +- 0.5 m/s, tags r1-r4 = the same 24 placements at every tick)

| tick | car step | jumps (boots) | lip clips | made it | take-off m/s | apex m | distance m | landing pitch deg | paired vs 41.667: take-off / apex | bounce half period s (1 m and 3 m drops, n 2 boots) | flame asked / s (n 2) | hazard / scrape / wreck / radar factor | flame factor (amount 1) | key -> drawn ms median / p90 / max (n 40) | feels vs 1997, from the numbers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 33.3 | 1 x 33.3 | 24 (4) | 0 | 24 | 51.37 +- 1.02 | 10.58 +- 0.42 | 227 +- 21 | -5 +- 14 | -1.20 +- 1.02 / -0.48 +- 0.43 | 0.233 (x0.80) | 86.1, 84.5 | 0.800 / 0.800 / 0.800 / 0.800 | 2.800 | 5.3 / 7.7 / 8.6 | faster: bounce 1.25x quicker, jump 1.2 m/s slower, 0.5 m lower |
| 36 | 1 x 36 | 24 (4) | 0 | 24 | 52.01 +- 1.04 | 10.82 +- 0.43 | 225 +- 27 | +8 +- 18 | -0.56 +- 0.71 / -0.23 +- 0.30 | 0.252 (x0.86) | 85.3, 84.6 | 0.864 / 0.864 / 0.864 / 0.864 | 3.024 | 5.2 / 8.7 / 20.7 | a little faster: bounce 1.16x quicker, jump 0.6 m/s slower |
| 39 | 1 x 39 | 24 (4) | 0 | 24 | 52.27 +- 0.85 | 10.93 +- 0.36 | 200 +- 32 | +1 +- 17 | -0.30 +- 1.43 / -0.13 +- 0.61 | 0.273 (x0.93) | 86.4, 84.9 | 0.936 / 0.936 / 0.936 / 0.936 | 3.276 | 4.5 / 12.4 / 23.7 | slightly faster: bounce 1.07x quicker, jump within its spread |
| **41.667** | 1 x 41.67 | 24 (4) | 0 | 24 | 52.57 +- 0.82 | 11.06 +- 0.35 | 225 +- 30 | +6 +- 21 | - | **0.292** | 84.7, 86.8 | 1 / 1 / 1 / 1 (not installed) | 3.500 | 4.9 / 8.2 / 8.8 | **same** (s.18: the stock 24 fps loop to the digit) |
| 44 | 1 x 44 | 24 (4) | 0 | 24 | 52.75 +- 0.81 | 11.13 +- 0.34 | 232 +- 25 | +15 +- 20 | +0.18 +- 1.23 / +0.07 +- 0.52 | 0.308 (x1.06) | 85.4, 84.8 | 1.056 / 1.056 / **1.000** / 1.056 | 3.696 | 5.2 / 7.9 / 10.8 | slightly slower: bounce 0.95x the 1997 tempo, jump within its spread; wreck rolls -5 % |
| 46.875 | 1 x 46.88 | 24 (4) | 0 | 24 | 53.04 +- 0.73 | 11.25 +- 0.31 | 208 +- 34 | -3 +- 10 | +0.46 +- 0.63 / +0.20 +- 0.27 | 0.328 (x1.13) | 84.7, 85.7 | 1.125 / 1.125 / **1.000** / 1.125 | 3.938 | 5.3 / 7.8 / 8.7 | slower: bounce 0.89x the 1997 tempo, jump 0.5 m/s faster, 0.2 m higher; wreck rolls -11 % |
| 66.7 | 2 x 33.3 | 24 (4) | 0 | 24 | 51.42 +- 1.05 | 10.77 +- 0.57 | 230 +- 26 | 0 +- 7 | -1.15 +- 1.04 / -0.29 +- 0.55 | 0.267 (sampled per tick; 7 x 33.3 = 0.233) | 86.3, 87.6 | 1.600 / 1.600 / 0.800 / 1.600 | 5.600 (2.800 at amount 2) | 4.6 / 8.2 / 8.8 | car faster (as 33.3), everything else 15 / s: coarser |

- **Reference.** s.18's e24 (the stock loop, 41 / 42 ms frames, quiet machine): take-off 52.68 +- 0.87, apex 11.10 +- 0.37 (n 60); on tags r1-r2
  it equals tick42 to the digit (52.72 / 11.12), and this lane's t41.667 r1-r2 reproduce s.18's tick42 r1-r2 to the digit. Retail cells
  (TWO-CLOCKS s.4.3): 51.06-52.82 m/s, 10.55-11.98 m.
- **This lane's own e24 rows are not used.** They ran beside three other lab games; the stock loop's wall-clock frames then scattered
  (5-6 ms frames among 38-44 ms: 1138 states with 95 at 42 ms, against s.18's 697 of 1155), and its jump (51.41) and bounce (6.1 steps) moved.
  The tick rows are immune by design (fixed sim step; the t41.667 rows repeat s.18) - but **the latency rows are wall-clock**, so they were
  re-run alone on the PC (l2, the table); the parallel l1 runs read p90 11-35 ms.
- **Bounce.** Every arm is 7 car steps (s.3 of TWO-CLOCKS), so the tempo is 7 T; the undershoot is 6.1-6.3 mm everywhere. Settle 0.36 /
  0.39 / 0.42 / 0.44 / 0.47 s at 36 / 39 / 41.667 / 44 / 46.875.
- **Jump.** The take-off and apex rise with the tick (fewer per-step projection losses on the ramp face, TWO-CLOCKS s.4.4): about +0.1 m/s
  and +0.04 m per ms. Distance and landing pitch do not separate the ticks (sd 25-35 m and 10-21 deg within each).
- **Latency.** With the early tick a key press reaches the screen in 4.5-5.3 ms (median) at every tick; the p90 / max tails at 36 / 39
  (12-24 ms) are single boots and come from presses that landed while an early tick was outstanding (one at a time).
- **Flame.** The rate-aware default gives 84.5-87.6 asked per s at every tick (factor 3.5 x T / 41.667 at amount 1); the kill after first
  contact is 8.3-12.5 s except s.14.3's early-kill roll (2.2-4.2 s in one boot of 33 / 36 / 39 / 41.667).
- **Wreck roll.** Above 41.667 ms the per-pass probability is capped at 1, so the roll cannot keep 24 / s (proxy log `wreck roll pass
  1.000` at 44 and 46.875; s.14.1). A second roll per pass would be needed; not built (the visible effect is fewer debris / blast rolls from a
  burning wreck).

### 19.4 The user override (not in the game menus)

- `Interstate 76\PLAY-i76.ps1` (repo root PLAY-i76.ps1) takes `-TickMs <ms>`: a plain number 16.7..66.7 replaces the preset's
  `I76_SIM_TICK_MS` for that launch; anything else (`abc`, `41,667`, `1e2`, `16.6`, `70`), or a preset without the tick, exits 4 with the
  reason. A leading BOM (Notepad's UTF-8) is ignored. `-CheckTickMs` validates and prints `tick <T> ms: <rate> ticks/s, the car in ...`
  without starting anything; at 50 ms and over it says the car step is split in two.
- `PLAY-TICK.bat [ms]`: with an argument, or else with `tick-ms.txt` beside it (first line), it runs the check in its own visible window
  (on a refusal: the reason, "The game was not started", a key to close) and then launches tick19-33 with `-TickMs`. Without either it is
  PLAY-TICK-33 as before.
- `PLAY-TICK-CHOOSE.bat`: what the tick is, the range (1997 PCs about 36-47 ms; 41.667 = the 1997 car step), what shorter / longer does
  (from 19.3: bounce tempo and a slightly lower / higher jump; key response the same), 50 ms and over, the allowed range, and the multiplayer
  caveat (every player should run the same tick; a mixed-tick game is untested and will probably feel different per player). It asks for a
  number (Enter = 41.667), checks it, offers to save it as tick-ms.txt, and starts `PLAY-TICK.bat <ms>`.
- **Tests** (lab `tools\tick-range\launcher-test.ps1`; cmd on a private desktop runs the .bat as a double-click would; the proxy's
  `sim-tick: ON - whole sim every <T> ms` line in mciproxy.log is the reading):

| path | values | proxy tick | n |
|---|---|---|---|
| `PLAY-TICK.bat <ms>` | 45, 37.5 | 45.000, 37.500 | 2 |
| `tick-ms.txt` + `PLAY-TICK.bat` | 44, 48 | 44.000, 48.000 | 2 |
| `PLAY-TICK-CHOOSE.bat` (answers: value, n) | 46.875, 38, 43 | 46.875, 38.000, 43.000 | 3 |
| refused | abc, 70 | no i76.exe started; the window printed the reason | 2 |
| `PLAY-TICK.bat` alone | - | 33.333 | 1 |
| `PLAY-TICK-33 / -36 / -39 / -42 / -44 / -47 / -66.bat` | - | 33.333 / 36.000 / 39.000 / 41.667 / 44.000 / 46.875 / 66.667, stepper 1 x T (66: 2 x 33.33) | 1 each |

- Harness note: the agent shell sets `NoDefaultCurrentDirectoryInExePath`, with which cmd does not find `PLAY-TICK.bat` in its own folder;
  the test removes it, as an Explorer double-click has it unset.

### 19.5 Not done, and why

- **No console gate on tick19g** (menus, save screen, Esc menu, the trip at 120 fps). The code it adds over the gated tick19f-av is the
  flame factor (under the tick only) and the network pools (network games only). Run the gate on the chosen PLAY-TICK before promoting.
- **No owner feel test**: the table is the input to his choice (OWNER-TEST-LIST A0b).
- **No crest descents (the owner's driven approach) per tick**, and no AI / combat rows per tick: the AI and weapons run once per tick, so they
  scale like the car's rate (FRAME-BOUND-SYSTEMS); not measured here.
- **Wreck roll above 41.667 ms** stays 5-11 % short (19.3); not patched.
- **Mixed-tick network games**: not run (no network games in this lane; the LAN is another lane's).

### 19.6 Console gate on tick19g (2026-10-20 morning, gate lane; physical console, owner away, lab game-tick)

Closes the first bullet of s.19.5. Proxy STRLKUP-tick19g `adc4fd49` as installed in game-tick (read back every time). Same gate set as s.17.9:
`tools\tick-gaps\tg-gate.ps1` under `tools\replay\with-lock.ps1` (console lock, no host mute), `I76_SHM_SUFFIX=game-tick`, `I76_MUTE=1` + the per-pid
mute watcher inside the gate rows, and `tools\tick-av\gate-watch-reaper.ps1` for the watcher / pipe hang. Lab `tools\tick-gate19g\` (run19g.ps1 = the
stages, extras.ps1 = the one-boot rows, before-*.md5 = the folder as found); logs `queue-tickgaps\gate19g-stage*.log`.

| launcher | rows | result | gate folder (`autotest\runs\gate\`) |
|---|---|---|---|
| PLAY-TICK.bat (tick19-33) | all | **19 PASS, 2 FAIL, 2 INFO** (watermark by eye, FFB no device). The 2 FAILs: row 3 trip run 2 never reached the mission (screenshot: Options menu; engine up False, 0 fps), "1 of 2". Row 4 (save screen) all 10 checks PASS under aw; YES wrote only save018.cmp + savegame.dir | `20261020-075210` |
| PLAY-TICK.bat row 3 re-run (evidence, the first run is not voided) | 3 | 5 PASS 0 FAIL (2 of 2, 112.3 / 114 fps; rows 3 of the plain33 boot) | `-091059` |
| PLAY-TICK-42.bat | 2 3 5 6 | **8 PASS 0 FAIL** | `-081539` |
| PLAY-TICK-66.bat | 2 3 5 6 | **8 PASS 0 FAIL** | `-082427` |
| PLAY-P18-BALANCED.bat (control) | 3 6 | **6 PASS 0 FAIL** | `-083312` |
| PLAY-TICK-36.bat | 3 | PASS (2 of 2, 113 fps) | `-083804` |
| PLAY-TICK-39.bat | 3 | PASS (2 of 2, 112.7 fps) | `-084203` |
| PLAY-TICK-44.bat | 3 | engine up 2 of 2, **fps FAIL: trip 1 104.7 fps** (floor 108; trip 2 116) | `-084605` |
| PLAY-TICK-44.bat row 3 re-run (evidence) | 3 | 5 PASS 0 FAIL (115.3 fps) | `-090657` |
| PLAY-TICK-47.bat | 3 | PASS (112.3 fps) | `-085009` |
| `PLAY-TICK.bat 43` | 3 | PASS (114 fps); proxy tick line 43.000 ms (n 2 boots) | `-085409` |
| tick-ms.txt = 45 + PLAY-TICK.bat | 3 | PASS (117 fps); proxy tick line 45.000 ms (n 2 boots); tick-ms.txt removed afterwards | `-085812` |
| instant melee (headless, game-sp, lab twin `builds\tick19g-gate-20261020\Strlkup-g19sc-lab.dll` 406e4c37 = tr1 source + shellclick block via sp-fix insert-sc.py) | M1a Scene 1 (Co-op) 30 s, M1b Tombstone 30 s, M2 Tombstone 3 AI 45 s | run 1: M1a PASS, M1b PASS, **M2 FAIL** (3 AI at the start, one AI wrecked by the others at ~35 s, so 'other 3' did not hold at 40 s; game alive, 0 CRASH). Re-run: **3 PASS** | `queue-tickgaps\gate19g-stage4-*.log` (-090217, -091418) |

Totals (first runs, nothing voided): console rows 11 gate folders = every launcher listed; first-run FAIL rows: PLAY-TICK row 3 (2 lines: engine up + fps, one
event), PLAY-TICK-44 row 3 fps (1), instant melee M2 (1). Every one passed on a single re-run. Tick 36 / 39 / 44 / 47 / 43 / 45: proxy tick line equals the
launcher's value in every boot; the same trip boots show terrain-lod A x96 / B x24, the aw pointer map, CRASH 0 (every tick boot of the gate and the extras).

- **Proxy log checks:** `sim-tick: ON` at 33.333 (10 boots), 41.667 (7), 66.667 (7); 36 / 39 / 44 / 46.875 / 43 / 45 (2 boots each) all as launched.
  The flame line is now rate-aware (`G 3.500 at the 1997 pass of 41.667 ms; per application x F at amount 1 / 2 / 3`): at amount 1 F = 2.800 at 33.333,
  3.500 at 41.667, 5.600 at 66.667 (x2.800 at amount 2, the per-sim-second 2.8 the old fixed factor was), 3.024 / 3.276 / 3.696 / 3.938 / 3.612 / 3.780 at
  36 / 39 / 44 / 46.875 / 43 / 45. CRASH 0 in every log slice (lab `captures\tick-gaps-20261018\gate-*-20261020-*.mciproxy.log`, `tools\tick-gate19g\xtra-*`).
- **S and D checks:** S (player state byte-identical to the backup) and D (no other top-level file changed) PASS in all 11 gate folders; save018.cmp absent
  afterwards, savegame.dir md5 fd5f1b70 as before. A separate md5 of every top-level file of game-tick and its launchers before / after the whole
  session: only `mciproxy.log` differs. `tick-ms.txt` removed. Persisted mutes of game-tick and game-sp: none left (unmute-persisted -List: not muted).
- **Flakes, with the evidence:** (1) PLAY-TICK row 3 trip run 2 ended on the Options menu with the engine not up (also seen in the voided tick19f gate of
  2026-10-19, run 2 of 2 there too; absent in the PLAY-TICK-42 / -66 / -P18 gates and in the re-run); the game was never refused by a foreign i76.exe;
  not diagnosed, harness route (clicks). (2) PLAY-TICK-44's first trip at 104.7 fps, under 108; the other trips ran 110-117
  (3) M2 depends on no AI dying in 40 s. No foreign i76.exe appeared, so no row was refused or voided.
- Gate row text for the 2026-10-18 note "not run": see s.19.5 first bullet, now closed for the menus, save screen, Esc menu and the trip at 120 fps on
  PLAY-TICK / -42 / -66 and the trip on -36 / -39 / -44 / -47 and the two override paths.

### 19.7 The twin's PLAY-TICK had no proxy (2026-10-20 15:10, main; owner report "play-tick mouse nav is broken, can't launch")

The owner launched `PLAY-TICK*.bat` from the lab twin `game-dd-20261003` (where the promotion play-tests happen), not
from `game-tick`. The tick-range lane had put the launchers, presets and `PLAY-i76.ps1` into the twin but left its proxy at
33211f11 (promotion 17/18), with tick19g beside as `STRLKUP.DLL.adc4fd49-tick19g`. The twin's proxy log for those boots
shows the old proxy's `cursor-map: dgVoodoo cursor (I76_CURSOR_MAP_DGV): ...` line (the value `aw` not parsed: the pointer
mapped as if the shell were stretched over the client while `dgVoodoo.wide.conf` dccd379a draws it 4:3 fit, so clicks landed
off the buttons) and no `sim-tick` line at all (no fixed step: the launchers' own warning). Every other file the launch
touches is byte-identical between the twin and game-tick (u32x 06467bd2, i76shell a300db63, i76.exe 6319abf7, both dgVoodoo
confs dccd379a, PLAY-i76.ps1 fdc5fa21, tick19-33/-42 presets); only `input.map` (twin 12a6357e, game-tick a66a37f7) and the
unused best-wide-balanced preset differ.

Fix at 15:20 with no i76 running: the twin's `STRLKUP.DLL` -> `STRLKUP.DLL.33211f11-pre-19g`, tick19g copied in (read back
adc4fd49). One headless muted boot of the twin through `autotest\proxy-run.ps1` with the tick19-33 env (t01, hold 8 s,
I76_SHM_SUFFIX game-dd-20261003): `sim-tick: ON - whole sim every 33.333 ms ... 12/12 sim gates, 4/4 display hooks`,
`cursor-map: dgVoodoo cursor (I76_CURSOR_MAP_DGV=aw: the dgVoodoo picture's fit)`, terrain A x96 / B x24, in mission after
11 s, 0 CRASH, n 1. The twin's PLAY-TICK set is now the gated game-tick set (s.19.6) except for the input map. The twin is
no longer hash-identical to the driver (proxy); a promotion-19 gate on the twin must start from the candidate folder's
MD5SUMS, and the lesson is in docs/LAYOUT-PROPOSAL-2026-10-20.md (rule 4: whoever puts launchers in a folder puts the whole
set in).

## 20. The T05 jump per tick against 1997 and promotion 18; the slope-follow loss (2026-10-20 evening / 10-21 night, jump-fix lane)

The owner (2026-10-20 evening, verbatim): "the test-tick doesn't really make the jump" ... "seems like the jumping is worse?" ...
"jump is more messed up somehow- not sure what changed but test-tick does too much nose down and falling and does not make the
t05 jump; tick 44 does but i'm not sure only moving that makes sense if we broke something else". Then his ruling: "the tick
lengths where the code scaling factors are exactly 1 seems like the 'true' tick length to me and we should go with that unless
it is absolutely non-performant in some way" (41.667 ms). Main's question: does T05 jump at 41.667 as 1997 did, and what was
44 compensating?

**Results in short.**
- **41.667 ms jumps as retail 1.0 did at the same frame time.** On the owner's approach (full throttle from the hill-top crest,
  steered down the road over aaramp4), with the emulator's car:
  - 41.667 ms: take-off 49.9 +- 1.0 m/s, apex 10.0 m, distance 193 m, 10 of 10 clear.
  - Retail on the emulated P166 at ~42 ms frames: 50.0 +- 1.3 m/s, 10.0 m, 189 m, 6 of 6 (20.1).
  - The stock 24 fps loop (e24): 50.0.
- **At 33.3 ms the car leaves the lip 2.5 m/s slower:** 47.4 +- 1.1 m/s, apex 9.0 m, 123 m, 4 of 7 clear, landing pitch -16 deg.
  - "Does not make the jump" and "nose down and falling" are this short, low flight, which lands on the face of the far lip.
  - Retail at 32 ms (the gold standard's own frame time) also flies low: 48.4 m/s, 9.4 m, 154 m, 7 of 9. That is a little
    better than tick33 (20.4).
- **The per-tick quantity is the slope-follow speed loss** in the vehicle integrator (20.3).
  - Every grounded substep, the velocity is projected into the ground plane. While the body lags a change of slope, each
    substep removes s (1 - cos delta).
  - The loss is per substep, so 30 substeps a second lose 1.25x what 24 do.
  - Scaling it to the 41.667 ms rate under the tick (one variable, switch `I76_SIM_TICK_SLOPE`) moves 33.3 ms to take-off
    50.5 +- 1.1 m/s, apex 10.2 m, 229 m, 6 of 6. That is the 41.667 jump.
- **What 44 compensated:** the same term, from the other side. Fewer substeps lose less speed: 50.3 m/s at 44, 51.3 at 46.875.
  - Against 41.667, 44 adds 0.4 m/s and changes nothing that decides the jump (6 of 6 and 10 of 10).
  - Moving the default to 44 would have been splitting the difference. 41.667 is the value where this factor, like the s.14
    ones, is exactly 1.
- **Nothing broke between 2026-10-19 and tonight.**
  - tick19f-av -> tick19g changed no car physics. The diff is the flame factor and the network pools.
  - The owner's three boots tonight ran tick19g at 33.333, 44 and 33.333 ms in the twin (its proxy log).
  - "Worse" is the 33 ms jump as it has always been (TWO-CLOCKS s.4.2: 46.9 m/s, n 2).
- **Fix:** `I76_SIM_TICK_SLOPE` is on by default under the tick (i76-everywhere `ed772c2`).
  - At 41.667 it installs nothing, so the owner's default is unchanged.
  - At 33 / 36 / 39 the jump becomes the 41.667 jump.
  - Above 41.667 the factor is x 1.056 / 1.125, inside the spread (20.2).
  - Staged in lab `builds\jump-fix-20261020\` (`STRLKUP-jumpfix-ed772c2.dll` fafeeaf9, run2 pecmp SAME). **Not installed**
    anywhere.
  - The default-on build's own boots ran only under RDP and are void (20.6). Its log lines were read (20.5).

Lab only.
- **Copy `exp-jump`** = the release candidate (lab game-tick) as of 2026-10-20 17:02, with three changes:
  - the lab twin proxy;
  - the lab null renderers (the RC's dgVoodoo pair stalled half the headless boots beside five other lab games; it is kept in
    `_rollback\rc-renderers`);
  - per run, `ADDON\vppirna1.vcf`.
- The release candidate, the daily driver, golden, the twin and the LAN copy were only read.
- **Boots.**
  - Every boot was headless on its own desktop (`I76Lab-exp-jump`), with `I76_SHM_SUFFIX=exp-jump`, `I76_MUTE=1` plus the
    per-pid watcher, and `I76_MULTI_INSTANCE=1` / `I76_NO_MINIMIZE=1`.
  - The gate before every boot waited for the owner's game (he played the twin 16:50-18:09) and for `.fps-lock` (the rc-draw
    lane held it for about 4 h of the night).
  - From 20:00, other lanes' `exp-*` / `game-mpo-*` games did not block the gate (main's rule).
  - Persisted mutes of exp-jump were cleared at the end (none left).
- **Tools:** lab `tools\jump-fix\`:
  - `jf-run.ps1` (one boot), `jf-queue.ps1` (with retries);
  - `jf_suite.py` = t42_suite with the crest start placed by s.18's `place_verified`;
  - `jf_drive.py`, `jf_tab.py` (the tables);
  - `presets\`: the three base presets, by md5: tick19-33 57d13cd5, p18-best-wide-balanced 0bca8b31, lab-step-33 4b264661;
  - `emu-car\vppirna1.vcf` 1d636559.
- **Captures:** lab `captures\jump-fix-20261020`.
  - `jf-desc.json` = every jump row.
  - `_void-*` = boots that never reached the mission, and the RDP boots.
- **Arms:**
  - `t<ms>` = the RC's tick19-33 preset with `I76_SIM_TICK_MS` set to that value.
  - `p18` = promotion 18 as played (`p18-best-wide-balanced`): per-frame patches, 120 fps cap, `I76_FIXED_STEP` 24, no tick,
    same proxy.
  - `e24` / `e30` = the stock frame loop at 24 / 30 fps (the 1997 coupling at 41-42 / 33 ms).
  - `I76_COOP_AI=0` in the runs with 3 descents per boot (20.7).

### 20.1 The table: crest descents with the emulator's car (the car of every retail row); n = jumps (boots)

| arm | step ms | n | made | v hill foot | v ramp foot | take-off m/s | vy m/s | take-off pitch rate deg/s | air pitch rate deg/s | apex m | distance m | landing pitch deg | lowest pitch in air |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tick 33.333 | 33.3 | 7 (3) | **4/7** | 51.6 | 56.3 | **47.38 +- 1.06** | 13.27 | -10 +- 11 | -24.8 +- 22.7 | **8.98** | **123 +- 26** | **-16 +- 25** | -37 |
| tick 36 | 36.0 | 3 (1) | 3/3 | 52.5 | 56.9 | 48.89 +- 1.42 | 13.69 | 0 | -6.3 | 9.57 | 144 +- 19 | -4 | -4 |
| tick 39 | 39.0 | 3 (1) | 3/3 | 53.5 | 56.7 | 49.27 +- 0.12 | 13.80 | -19 | -5.3 | 9.71 | 208 +- 21 | 12 | -47 |
| **tick 41.667** | 41.7 | 10 (4) | **10/10** | 53.0 | 56.7 | **49.90 +- 0.95** | 13.97 | -12 +- 12 | -4.7 +- 4.0 | **9.96** | **193 +- 28** | **10 +- 15** | -33 |
| tick 44 | 44.0 | 6 (3) | 6/6 | 53.5 | 57.5 | 50.31 +- 0.20 | 14.09 | -15 +- 16 | -10.2 +- 17.3 | 10.12 | 193 +- 23 | 9 +- 12 | -33 |
| tick 46.875 | 46.9 | 7 (3) | 7/7 | 53.2 | 57.3 | 51.29 +- 0.94 | 14.36 | -21 +- 16 | -26.4 +- 22.1 | 10.52 | 216 +- 36 | 5 +- 9 | -59 |
| promotion 18 (as played) | 41.7 fixed | 7 (3) | 7/7 | 53.5 | 57.5 | 50.94 +- 1.43 | 14.26 | -15 +- 9 | -4.2 +- 7.0 | 10.39 | 208 +- 20 | 11 +- 14 | -38 |
| stock loop 24 fps (e24) | 41-42 | 7 (3) | 6/7 | 53.2 | 57.0 | 50.02 +- 1.48 | 14.01 | -19 +- 14 | -16.8 +- 23.8 | 10.02 | 190 +- 46 | 2 +- 24 | -48 |
| stock loop 30 fps (e30) | 33.1 | 6 (2) | 5/6 | 52.7 | 56.9 | 48.82 +- 1.44 | 13.67 | -14 +- 12 | -19.0 +- 19.3 | 9.54 | 155 +- 48 | -20 +- 25 | -40 |
| **retail 1.0, P166, ~42 ms (r166lmirtex)** | 42.2 | 6 | **6/6** | 53.5 | 55.7 | **50.0 +- 1.3** | 14.0 | -9 +- 11 | -6.5 +- 5.2 | **10.0** | **189 +- 34** | **0 +- 13** | -28 |
| retail 1.0, P166, ~37 ms (r166lmir) | 36.8 | 6 | 4/6 | 53.4 | 55.4 | 48.3 +- 0.8 | 13.5 | -24 +- 10 | -31.0 +- 21.3 | 9.3 | 155 +- 63 | -13 +- 19 | -62 |
| retail 1.0, P166 lowest (gold standard, 2026-10-16) | 32.2 | 9 | 7/9 | 52.8 | 55.1 | 48.4 +- 1.8 | 13.5 | -15 +- 9 | -18.3 +- 15.7 | 9.4 | 154 +- 48 | -20 +- 20 | -41 |
| retail 1.0, P166, m6 (frames ~48 ms, 39 % split into 2 steps) | 32.8 (mixed) | 6 | 6/6 | 52.3 | 53.9 | 49.1 +- 1.0 | 13.8 | -12 +- 15 | -15.0 +- 11.6 | 9.8 | 190 +- 45 | -1 +- 5 | -46 |

- **The retail rows.**
  - A sub-lane ran 22 new emulator descents and re-analysed the 9 of 2026-10-16 with the same definitions.
  - Results: lab `emu\results\jump-fix-20261020\results.md` and `descents.json`.
  - Scripts: `emu\tools\par\scripts\hwm-t05c1-retail-*.txt`, written by `emu\tools\memtrace\gen_t05clean_hwm.py`.
  - Checks: the arcade flag was 0 on every frame, the DEF read back identical, every placement was within 0.03 m, crest armour
    5600 / 5600.
- **Limits of the emulator as a reference.**
  - Retail splits any frame of 50 ms or more into two steps. So the owner's own 1997 settings (m6mir 52 ms, m5 55.5 ms frames)
    step at ~28 ms most of the time.
  - The airborne frames render at 22-27 ms in every cell, so retail flights are always stepped short.
  - The ~42 ms cell is the closest the emulator gets to the owner's 1997. The owner's own logged sessions of 2026-10-19 never
    reached the canyon (top speed 25 m/s).
- **Definitions** (jf_tab.py, = tc_analyse.jump_extra).
  - Take-off = the last row before the longest airborne stretch past the foot (x < 6900, clearance > 1 m).
  - Pitch = asin(forward.y), + nose up. Pitch rates are + nose up.
  - Made = landed past the far lip (x < 6745).
  - Rows are deduplicated on sim_time.
  - The p18 sim_time advances per display frame, so jf_tab's "step" column reads 8-9 ms there. Its car step is the fixed
    41.667 ms.
- **Which car.**
  - The table above uses the emulator's car (`ADDON\vppirna1.vcf` 1d636559: engine 0, armour 2800 / chassis 2000). It is the car
    of every retail row.
  - The release candidate's direct T05 boot gives the mission's stock car instead ("Jade's Car", engine 2, wheels wauto_1a). It
    is 6 m/s faster at the foot and clears at every tick (20.2).
  - In his own play the owner drives his save's car. His twin log tonight books his sign hits at 51-53 m/s closing on the road:
    the emulator car's speed range, not the stock car's 59. This is an inference: the twin's telemetry was not recorded (the
    reader attached at 17:52 got no frames).

### 20.2 The same descents with the stock T05 car (the RC's direct boot), and with the factor

| arm | n | made | v ramp foot | take-off m/s | apex m | distance m | landing pitch deg |
|---|---|---|---|---|---|---|---|
| RC car, tick 33.333 | 7 (3) | 7/7 | 62.8 | 53.74 +- 1.47 | 11.56 | 229 +- 30 | 5 +- 26 |
| RC car, tick 33.333 + factor | 7 (3) | 7/7 | 62.5 | 55.50 +- 1.14 | 12.32 | 240 +- 40 | -5 +- 27 |
| RC car, tick 41.667 | 4 (3) | 4/4 | 63.5 | 55.85 +- 1.04 | 12.48 | 233 +- 26 | 13 +- 15 |
| RC car, tick 44 | 7 (3) | 7/7 | 63.3 | 56.05 +- 0.88 | 12.57 | 283 +- 18 | 2 +- 17 |
| RC car, tick 46.875 | 7 (3) | 7/7 | 63.6 | 56.82 +- 0.94 | 12.92 | 246 +- 5 | 13 +- 1 |
| RC car, promotion 18 | 3 (3) | 3/3 | 63.5 | 56.50 +- 1.09 | 12.77 | 236 +- 27 | -5 +- 29 |
| emulator car, tick 33.333 + factor (x 0.800) | 6 (2) | **6/6** | 57.1 | **50.53 +- 1.11** | **10.22** | **229 +- 14** | 4 +- 11 |
| emulator car, tick 36 + factor (x 0.864) | 6 (2) | 6/6 | 57.4 | 49.53 +- 0.05 | 9.81 | 205 +- 32 | 7 +- 19 |
| emulator car, tick 44 + factor (x 1.056) | 6 (2) | 6/6 | 57.4 | 50.25 +- 0.97 | 10.10 | 183 +- 21 | 5 +- 13 |
| emulator car, tick 46.875 + factor (x 1.125) | 6 (2) | 6/6 | 57.5 | 50.87 +- 1.14 | 10.35 | 203 +- 44 | -1 +- 9 |

- **The take-off rises with the tick for both cars.** From 33.3 to 46.875 ms: the stock car 53.7 -> 56.8 m/s, the emulator car
  47.4 -> 51.3.
- **The factor removes the 33 ms deficit for both cars:** +1.8 and +3.2 m/s. Above 41.667 its effect (x 1.056 / 1.125) is inside
  the spread.
- **The speed lost on the ramp face** (foot -> take-off), emulator car:

  | arm | ramp-face loss, m/s |
  |---|---|
  | tick 33.3 | 8.9 |
  | tick 33.3 + factor | 6.6 |
  | tick 41.667 | 6.8 |
  | e24 | 7.0 |
  | e30 | 8.1 |
  | retail ~42 ms | 5.7 |
  | retail 32 ms | 6.7 |

### 20.3 Why: the per-substep term

Sources: the code as i76-map `subsystems/physics.md` describes it ("Speed terms while grounded on the face", "M34b"), the
disassembly of 0x43a5d0 at 0x43ba3a / 0x43ba64 read this session, and each quantity the brief named.

| candidate | runs per | scaled with the step? | effect on the jump across ticks |
|---|---|---|---|
| gravity, ballistic flight | dt | yes (0x43a6a1; no drag in flight) | none |
| aero / rolling resistance | dt | yes (acceleration x dt) | none |
| air pitch rate (ease toward -pi/20 with k = dt, held below it) | dt | yes | none in the mean |
| take-off nose-down kick (one lifted-front substep: 2 dt x -2 pi) | substep | the kick scales x dt and its chance d_f / (v dt) scales / dt, so the mean is step-free and only the spread changes (33.3: almost every take-off gets a small kick; 41.667: a larger one some of the time) | the "air pitch rate" column; not the deficit |
| suspension filter (period 15 calls) | substep | no (the bounce, s.19) | none on the take-off speed (TWO-CLOCKS s.3) |
| early tick on input | tick | the tick length is unchanged | none (TICK-LATENCY s.1.5) |
| interpolated draw | display | - | none on the state (the table reads the physics state) |
| **slope-follow projection** (v = f s + a dt, then v - (v.n) n, with n from the previous substep) | **substep** | **no: s (1 - cos delta) is removed per substep while the body lags the slope, and the lag runs on time** | **the deficit** |

- **The one-variable test.** `I76_SIM_TICK_SLOPE` scales only the speed each projection removes, by substep / 41.667 ms.
  - The projection's direction stays the engine's.
  - Airborne substeps and the substep after a landing stay stock.
- **Its counters** at 33.3 ms, emulator car, 3 descents in one boot:
  - 16,032 projections, of which 1,942 removed speed;
  - 38.1 m/s removed in all -> 30.5 (x 0.800);
  - 27 kept whole after landings.
- **The result:** the take-off came up by 3.2 m/s (47.4 -> 50.5; n 7 / 6), the apex by 1.2 m, and the clear rate went from 4 of 7
  to 6 of 6.
- **This is the 1997 engine's own behaviour.** Retail at 32 ms flies low too (48.4 m/s), and at 42 ms it flies like 41.667.
  - Under the tick the sim steps at a chosen length instead of the PC's frame time.
  - So the factor makes every tick length lose speed on slopes at the 1997 rate of the owner's frame time. The s.14 factors do the
    same for hazards, scrapes, wreck rolls and missile turns.

### 20.4 Notes and smaller findings

- **tick33 vs the stock loop at 33 ms:** tick 47.4 +- 1.1 (n 7), e30 48.8 +- 1.4 (n 6). They are 1.4 m/s apart, about 1.9
  standard errors. e24 and tick 41.667 agree (50.0 / 49.9). Not traced; it does not touch the 41.667 default.
- **The 1997 reference at the owner's settings cannot be measured on the emulator** (20.1: the 50 ms split and the fast airborne
  frames). The ~42 ms cell is the nearest.
- **Spread.** The crest descent is steered by keys at the harness's wall clock, so distances spread 20-45 m within an arm. Take-off
  speed and apex are the tight measures (sd 0.1-1.5 m/s).

### 20.5 The fix as default (ed772c2) and the staged proxy

- **`simtick.c`.**
  - Wrappers on the integrator call at 0x439c3a (for the substep's vehicle flags) and on the two cross products at 0x43ba3a /
    0x43ba64.
  - `st_factors_install` installs them when the factor is not 1.
  - Log line in every tick boot at 33.3 ms: `tick-factors: slope-follow loss x 0.800 per grounded substep (I76_SIM_TICK_SLOPE
    unset = auto; substep 33.333 ms against the 1997 41.667 ms), 3/3 sites`. At 41.667 it reads `x 1.000 ... 0/3 sites`. Both
    were read in the default-on build's boots (20.6).
  - A `tick-factors: slope:` counter line every I76_SIM_TICK_LOG seconds.
- **Builds** (lab `builds\jump-fix-20261020\`, README there):
  - `STRLKUP-jumpfix-ed772c2.dll` fafeeaf9 is the commit exactly. Its run2 build 3dbb048d is pecmp SAME in every section; the md5s
    differ only in the PE timestamp.
  - Lab twin `Strlkup-jf3-lab.dll` ceb0c98c.
- **Not installed** in the release candidate, the daily driver, golden, the twin or the LAN copy.
  - A gate (main) and an owner jump check at 33 and 41.667 come first.
  - At 41.667 the build is the current tick19g physics plus whatever main committed since.

### 20.6 Not done, and why

- **The default-on build was not measured in game.**
  - Its boots (06:24-07:18 on 10-21) ran after the session became an RDP session at 06:13 (LocalSessionManager event 25 from
    100.66.69.126). They stalled with rdpendp.dll on the stack, so they are void per AGENTS.md
    (`captures\jump-fix-20261020\_void-rdp`).
  - The same code path was measured with the switch set to `auto` on the jf1 twin (20.2).
  - The default build's log lines show that it installs at 33 / 44 and not at 41.667.
  - To do: re-run `tools\jump-fix\queue5.txt` at the console.
- **No placed-jump (56 m/s) rows with the factor.** `queue3.txt` is written but was not run; s.19.3's placed rows stand for the
  stock loss.
- **The early pitch-down kick at take-off** (20.3) is left as the engine has it; its mean is step-free.
- **The owner's 1997 settings** (46-48 ms frames) have no retail row (20.1).

### 20.7 Side finding: the co-op AI switch crashes a single-player game on a re-placement

- **What happens.** With `I76_COOP_AI=1` (the RC presets' LAN key), the second crest placement after a landing (trainer REPAIR +
  FREEZE_POS + TELEPORT) crashed every boot, in the proxy.
- **Where.** `coop_ai_object` (strlkproxy.c), called from `coop_ai_log`, reads a label-table object pointer (`o + 0x6c`) and takes
  an access violation on freed memory.
  - Seen with jf1 and tr1, so it is in tick19g's line too.
  - Map: `builds\jump-fix-20261020\mapcheck\jf1.map`.
- **Control.** With `I76_COOP_AI=0`, 3 placements per boot ran in every boot.
- **Not tested:** whether the owner can reach it without the trainer (a regen respawn also rebuilds the car).
- Not fixed here (another lane's code); for main.
