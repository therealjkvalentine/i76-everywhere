# Whole-sim tick, finished and tested against promotion 18 (2026-10-18, overnight)

The owner's question (2026-10-17): "where did we leave our two tick engine fix attempt? ... get me a finished version
tested of that overnight as well and say if it's better or worse."

Earlier records: [WHOLE-SIM-TICK-2026-10-17.md](WHOLE-SIM-TICK-2026-10-17.md) (the tick),
[TICK-LATENCY-AND-AI-FIRE-2026-10-17.md](TICK-LATENCY-AND-AI-FIRE-2026-10-17.md) (the early tick on input; completed
today: s.1.5 physics rows, s.2 AI fire), [SAME-CAR-FINGERPRINT-2026-10-17.md](SAME-CAR-FINGERPRINT-2026-10-17.md). Lab
only. The daily driver, the golden copy and the Downloads portable were only read (the promotion-18 presets and md5s).
Nothing was promoted.

## Verdict

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
