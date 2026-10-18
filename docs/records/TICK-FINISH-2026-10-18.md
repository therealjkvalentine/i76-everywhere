# Whole-sim tick, finished and tested against promotion 18 (2026-10-18, overnight)

The owner's question (2026-10-17): "where did we leave our two tick engine fix attempt? ... get me a finished version
tested of that overnight as well and say if it's better or worse."

Earlier records: [WHOLE-SIM-TICK-2026-10-17.md](WHOLE-SIM-TICK-2026-10-17.md) (the tick),
[TICK-LATENCY-AND-AI-FIRE-2026-10-17.md](TICK-LATENCY-AND-AI-FIRE-2026-10-17.md) (the early tick on input; completed
today: s.1.5 physics rows, s.2 AI fire), [SAME-CAR-FINGERPRINT-2026-10-17.md](SAME-CAR-FINGERPRINT-2026-10-17.md). Lab
only. The daily driver, the golden copy and the Downloads portable were only read (the promotion-18 presets and md5s).
Nothing was promoted.

## Verdict

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
