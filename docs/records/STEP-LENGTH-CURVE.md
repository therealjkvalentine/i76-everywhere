# Behaviour vs physics step length on our exe (lane modern-fps-sweep, 2026-10-17)

Status: **partial.** Round 1 of the stock-stepper sweep (n = 1 boot per cell) is measured. Rounds 2-3, the new study-grid
cells (27 / 36.7 / 43.3 / 46.7 / 49 ms), the 40 ms A/A, the render-independence pair and the dgVoodoo cell are built
and queued but **not run**: the owner held the lab console lock (his own F2 test, `OWNER-TESTS f2-control`, pid 11876)
from 08:05 for the rest of this lane's window. Every number below is labelled with its n. Nothing here is a decision;
it feeds [PHYSICS-STEP-STUDY-DESIGN.md](PHYSICS-STEP-STUDY-DESIGN.md) (task L4 and the H1 / H3 / H4 / H5 checks).

Lab commits: f55c084 (sweep tools, before the pause), 2213920 (resumed: private-desktop runner, grid cells, metric
fixes). Captures: lab `captures\step-curve-20261017\` (`<measure>-<cond>-<round>.{phys.csv,frames.txt,env.txt,txt,log}`).
Analysis: `python -I tools\step-curve\sc_curve.py [--md OUT] [--json OUT]`; emulator reference
`python -I tools\step-curve\emu_ref.py tools\step-curve\emu-ref.json`.

## 1. Set-up

| item | value |
|---|---|
| exe | our exe, i76.exe md5 6319abf7 (AiO + u32x), lab copy `game-stepcurve` (a copy of game-envrb; never the daily driver) |
| proxy | `builds\envelope-rebase-20261017\Strlkup-envrb1.dll` (md5 read back before each boot) |
| renderer | null glide2x / DDraw stubs (headless); dgVoodoo copies beside them for the wrapper cell |
| detail / car / mission | the copy's I76PLYR.DEF; T06 strip (`t06.msn`) and T05 canyon (`t05.msn`), direct boot |
| physics mode | simulation: arcade share 0.00 in every boot (entity flag 0x10000 never set; `mode.arcade_share` row) |
| input | proxy `I76_RH_DRIVE` (held-key bytes from shared memory); phys-suite placements (trainer-style teleport) |
| CPU | host (not emulated). The step is set by the cap, not by CPU speed |

**Conditions.**
- `sNN`: the **stock stepper**, a 1 ms sim tick (`I76_TICK_MS=1`) and a QPC frame cap (`I76_FPS_CAP`). Below 50 ms the
  rule `floor(sim_dt x 20) + 1` gives one step per frame, so **the step is the frame time and the whole sim runs once per
  step**: the 1997 coupling, i.e. what a whole-sim fixed tick (design s.7.2) should reproduce. Read back: step p50 and
  one-step share per boot (table rows 1-3).
- `mNN`: the same, named by step ms for the grid points not covered by an fps name (m27, m37, m43, m47, m49).
- `fNN` / `f40r60`: `I76_FIXED_STEP` alone (the current decoupled stepper, engine update still on frame dt) at 120 / 60
  fps render; the H5 pair. Queued.
- `s25dgv`: s25 with dgVoodoo's Glide2x / DDraw swapped in (conf: d3d11warp, windowed, FPSLimit 0). Queued.

Mapping to the study grid (ms): 27 = m27, 30 = s33, 33.3 = s30, 36.7 = m37, **40 = s25** (A/A s25aa), 43.3 = m43,
46.7 = m47, 49 = m49. Modern context: 8.3 = s120, 16.7 = s60. Outside the band, measured in round 1: 25 = s40,
42 = s24, 48 = s21, 55 ms frames = 2 x 27.5 ms steps (s18).

**Measures per boot.** T06 strip (phys-suite `jump,drop,accel,steer`): drop g, accel t10 / t20 / d10, yaw at the 18 m/s
steer phase, turn lean and roll reversals, body reversals on the accel straight, T06 ramp A jumps at 26 / 30 / 34 m/s.
T05 placed (`canyon`, 6 placed 56 m/s jumps per boot): take-off speed, apex, distance, peak pitch / roll, outcome, landing
jounce (2 s after touchdown).

## 2. Changes made on resume (and why)

1. **Foreground.** phys-suite's `keep_focus()` re-takes the foreground every 0.5 s. Round 1 logged **90-97 re-takes per
   boot** (`focus_retakes` in each `t05p-*-r1.txt`). That is not allowed while the owner is at the console.
   `sc_session.py` now starts the game on a private desktop (`WinSta0\I76SC`, never switched to, as parrun does for 86Box).
   It runs the driver with `keep_focus` replaced by a no-op and counts the 1 Hz foreground samples owned by the game
   (must be 0). It also reads back the loaded renderer modules 20 s in, and runs game and driver at BELOW_NORMAL.
   **Not yet run live** (lock).
2. **Brake.** With `--accel 11` the car reaches about 39 m/s, and the brake phase runs off the end of the T06 plateau:
   y falls 17.5 -> 10-13 m mid-brake in every round-1 boot. So round 1's "brake 30-10" (6.2-20.2 m/s2 across cells) is
   braking mixed with a fall, and it is **withdrawn**. New boots use `--accel 7` (about 28 m/s). A plateau-only
   least-squares decel replaces the old metric, and round-1 brake rows are excluded.
3. **Step read-back regression (other lane's tool).** Lab commit 9d3ba95 (trainer-logger, 08:19) made
   `fingerprint.frame_metrics` treat a frame with `step_count == 0` as fixed-step. The lab proxy frame log writes 0 on
   every stock-stepper frame (the count is consumed by read time, as the function's own docstring says). So every stock
   lab capture now gets no step percentiles. `sc_curve.py` drops the 0 count for boots without `I76_FIXED_STEP` in their
   env. `fingerprint.py` itself is not edited; flagged in s.7.
4. `t05p-s25-r2` was cut off by the pause (3 of 6 jumps, no status line). It was moved to
   `interrupted-at-pause\` and excluded.

## 3. Round-1 results (stock stepper, step = frame time; n = 1 boot per cell)

Mean (sd) across boots. With n = 1 the sd is 0 and means nothing. T05 rows are across the 6 placed jumps of one boot,
and **those jumps are not independent**: repeats in one boot often reproduce the same take-off to 0.1 m/s.

| step ms (cell) | 8 (s120) | 17 (s60) | 25 (s40) | 30 (s33) | 30 A/A (s33aa) | 33 (s30) | **40 (s25)** | 42 (s24) | 48 (s21) | 2x27.5 (s18) |
|---|---|---|---|---|---|---|---|---|---|---|
| step p50 read back | 8.0 | 17.0 | 25.0 | 30.0 | 30.0 | 33.0 | 40.0 | 42.0 | 48.0 | 27.5 |
| one-step frames | 1.00 | 1.00 | 0.98 | 1.00 | 1.00 | 1.00 | 0.99 | 1.00 | 0.98 | 0.00 (2 per frame) |
| drop g | 9.80 | 9.80 | 9.80 | 9.80 | 9.80 | 9.80 | 9.80 | 9.80 | 9.80 | 9.80 |
| accel t20 s | 3.08 | 2.86 | 2.82 | 2.76 | 2.76 | 2.73 | 2.72 | 2.71 | 2.69 | 2.75 |
| accel d10 m | 239.5 | 249.4 | 252.6 | 254.1 | 254.4 | 254.5 | 256.5 | 257.0 | 257.5 | 254.4 |
| yaw, 18 m/s steer phase, rad/s | 0.811 | 0.805 | 0.798 | 0.799 | 0.800 | 0.799 | 0.802 | 0.825 | 0.808 | 0.806 |
| turn lean deg | 6.29 | 6.31 | 6.29 | 6.28 | 6.28 | 6.30 | 6.22 | 6.11 | 6.23 | 6.26 |
| turn roll reversals /s | 14.5 | 5.4 | 2.4 | 1.8 | 1.8 | 2.0 | 0.0 | 0.3 | 0.0 | 1.8 |
| straight: roll reversals /s | 3.5 | 2.1 | 0.5 | 0.4 | 0.3 | 0.2 | 0.0 | 0.0 | 0.0 | 0.3 |
| straight: pitch reversals /s | **25.6** | 2.9 | 0.6 | 0.4 | 0.6 | 0.5 | 0.3 | 0.4 | 0.4 | 0.4 |
| T06 ramp A 30 m/s: air pitch change deg | -11.5 | -15.8 | -36.4 | -44.5 | -46.0 | -25.9 | -31.8 | -32.9 | -37.3 | -20.6 |
| T05 take-off m/s (6 jumps) | - | - | 49.5 +- 1.8 | 50.8 +- 0.6 | 50.9 +- 1.6 | 51.7 +- 0.4 | 52.6 +- 1.1 | 54.4 +- 0.6 | 53.4 +- 0.9 | 50.5 +- 0.0 |
| T05 apex m | - | - | 9.80 | 10.32 | 10.35 | 10.67 | 11.07 | 11.85 | 11.41 | 10.53 |
| T05 distance m | - | - | 176 +- 39 | 204 +- 30 | 205 +- 42 | 218 +- 37 | 234 +- 34 | 232 +- 31 | 233 +- 31 | 210 +- 11 |
| T05 peak pitch deg | - | - | 38 +- 10 | 39 +- 22 | 47 +- 18 | 52 +- 26 | 74 +- 27 | 61 +- 36 | 64 +- 31 | 52 +- 0 |
| T05 turned over / jumps | - | - | 0/6 | 0/6 | 0/6 | 0/6 | **5/6** | 3/6 | 3/6 | 0/6 |
| T05 destroyed / jumps | - | - | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 |

(T05 was not run at 8 / 17 ms in round 1. Arcade share 0.00 in all boots.)

What round 1 shows, with n = 1 per cell (hints, not results):

- **Pacing reads back exactly.** Step p50 equals the cell and one-step frames are 0.98-1.00. At 55 ms frames the rule
  splits into 2 x 27.5 ms, as the code says. Gravity is 9.80 everywhere.
- **Straight-line motion barely depends on T inside the band.** accel t20 is 2.69-2.76 s from 25 to 48 ms; it is slower
  only at 17 / 8 ms (2.86 / 3.08). Yaw at the 18 m/s steer phase is 0.80-0.83 rad/s at every step from 8 to 55 ms.
- **Buzz is a short-step phenomenon (H4).** Pitch reversals on the straight are 25.6 /s at 8 ms and 2.9 at 17 ms, then
  0.3-0.6 from 25 ms up. Turn roll reversals go 14.5 -> 5.4 -> about 2 -> 0 at 40-48 ms. That fits the design's
  "calm above about 25 ms" (P4).
- **T05 take-off speed rises with T (H3).** 49.5 (25 ms) -> 50.8 (30) -> 51.7 (33) -> 52.6 (40) -> 53.4-54.4 (42-48).
  That is about +1 m/s per 5 ms, the size the design predicts. Apex and distance rise with it.
- **Turn-over appears at 40 ms and above (H1).** 0 of 6 jumps at 25 / 30 / 30 / 33 ms and at 2 x 27.5; 5/6 at 40 ms;
  3/6 at 42 and 48 ms. Each cell is ONE boot, so the boot is the unit: 0 of 5 boots below 40 ms had a turn-over, and
  3 of 3 at 40-48 ms did. That is the same split as ERA-ENVELOPE (30 ms 0/24, E25 = 40 ms 7/11). It is not yet a
  measured curve.
- **Our exe turns over without being destroyed** (destroyed 0 in every cell). The emulated retail / Gold runs count
  turned over = destroyed (s.4). The cause was not looked into (lab car / mission state / proxy).
- **A/A at 30 ms (s33 vs s33aa):** identical to the printed precision on the T06 rows. T05 peak pitch 39 vs 47 and
  roll 29 vs 39 (6 jumps each). So the per-jump spread in one boot is about 20 deg. That is the noise floor any T05 pitch
  difference has to beat.

## 4. Where retail P166 and P133 sit (emulator, retail 1.0, simulation, software, lowest detail)

The step on the emulated machines comes from the frame time, so each one lands at a point on this curve:

| machine (source) | step p50 melee | step p50 T05 | T05 ramp-window step p50 (per jump) | placed 56 m/s T05: peak pitch | turned over |
|---|---|---|---|---|---|
| retail P166 low, reference set (EMU-T05-CLEAN; `r166sim-t05jump56`, n 7) | 26.8 +- 0.9 (12 traces) | 31.1 +- 1.0 (16) | 30.0-33.0 | 53 +- 18 | 0/7 |
| retail P166 low, hardware-matrix rerun (`hwm-r166low-t05jump56`, n 3) | 26.5 +- 0.6 (4) | 27.7 +- 2.1 (3) | 30.5-33.0 | 81 +- 14 | **2/3** (destroyed) |
| retail P133 low (`hwm-r133low-t05jump56`, n 5) | 32 +- 0.7 (5) | 31 +- 3 (5) | 35.5-37.0 | 87 +- 7 | **4/5** (destroyed) |
| Gold P166 low (EMU-T05-CLEAN, n 7) | 31.3 +- 0.5 (8) | 34.5 +- 2.6 (13) | - | 80 +- 8 | 3/7 |

Sources: lab `emu\results\hardware-matrix\matrix.md` (hwm_analyse.py) and `hwm_jumps.py` output (per-jump step
windows), read only this session; `tools\step-curve\emu-ref.json`. The hardware-matrix runs are that lane's; it owns
their write-up (HARDWARE-MATRIX.md, not landed at the time of writing).

- **On the step axis:** retail P166 low steps **27 ms (melee) to 30-33 ms (T05 ramp)**. Retail P133 low steps
  **32 ms (melee) and 35-37 ms on the T05 ramp**. On this curve they sit at the 30-33 cells (P166) and between the
  33 and 40 cells (P133). P166 at its own detail preset p3 runs 10 fps, so 2-3 substeps of 36-45 ms (r166p3, n 2).
- **On the outcome axis they do not line up yet.** Our exe at 30 / 33 ms turned over 0 of 18 jumps (3 boots). Retail
  P166 low is 0/7 in the reference set but 2/3 in the hardware-matrix rerun. Retail P133 low is 4/5, at a ramp step
  (35-37 ms) where our curve has no cell yet. Two readings remain open:
  - (a) the turn-over threshold sits between 33 and 37 ms on both exes;
  - (b) the emulated runs differ in something besides the step (car / save state: the GOLD-STANDARD-FINGERPRINT
    suspicion; per-frame step jitter, since the emulator's in-air steps range 22-50 ms where ours are constant).
  The 36.7 ms cell (m37) and per-jump step jitter are the measurements that separate them.
- The two retail P166 sets disagree with each other (0/7 vs 2/3 turned over; peak pitch 53 vs 81 deg). That is
  n 7 vs n 3, Fisher p about 0.07, so "retail P166 never turns over at T05" is not established.

## 5. Wrappers (dgVoodoo and others)

- **Static:** no proxy switch, wrapper or AiO cluster touches the physics code. The physics sees the renderer only
  through the frame time, i.e. through sim_dt (FIX-INVENTORY-2026-10-17 s.2; EXE-DIFF-MAP s.3). So the prediction is
  that the same step gives the same behaviour under any renderer, and that a wrapper changes behaviour only by changing
  the frame time (FPSLimit, vsync, present cost).
- **Measured:** nothing yet. `s25dgv` (dgVoodoo d3d11warp at the 40 ms cap, against s25 / s25aa with the null stubs)
  is built and queued. It records the loaded glide2x / DDraw module and its size, so a wrapper that fails to load cannot
  pass as "no effect" (the dgVoodoo-conf-not-read lesson). The pass test: every T06 row within the s25 / s25aa A/A
  spread and the step distribution identical.
- Only dgVoodoo is checked. nGlide / OpenGLide (GOG's Glide path) would need the same cell with their DLLs; not built.

## 6. What feeds the study design

| design item | status from this lane |
|---|---|
| H1 landing survival falls with T | round-1 hint: 0/5 boots with turn-over below 40 ms, 3/3 at 40-48 (n = 1 boot per cell). The independent-jump L2 campaign is still needed |
| H3 take-off speed rises about +1 m/s per 5 ms | consistent: 49.5 -> 54.4 m/s over 25 -> 48 ms (6 non-independent jumps per cell) |
| H4 buzz falls with T, calm above 25 ms | consistent: straight pitch reversals 25.6 / 2.9 / 0.3-0.6 /s at 8 / 17 / >= 25 ms |
| H5 render independence at fixed T | not measured (f40 vs f40r60 queued) |
| L4 body vs step | round 1 only, n 1 |
| 40 ms A/A | not measured (s25aa queued); the 30 ms A/A (s33 / s33aa) is the only noise floor so far |
| wrapper = same physics | static yes; live cell queued |

## 7. Open / next

- **Run campaign C** (`tools\step-curve\run-c.ps1`). It takes the lock per boot, skips done cells and stops on a `STOP`
  file. About 70 boots of about 3.5 min. First a single smoke boot (`sc-run.ps1 -Cond s25 -Measure t05p -Tag smoke2`)
  to confirm the private-desktop runner: `fg_game_samples` 0, `renderer_modules` read, status ok.
- **fingerprint.py 9d3ba95 regression:** every stock-stepper lab capture (envelope-rebase, step-curve, replay) loses its
  step percentiles. Suggested fix in fingerprint: take the fixed-step branch only when step_ms is constant and differs
  from sim_dt, or when the boot's env carries I76_FIXED_STEP. Owner: the trainer-logger lane.
- **Turned over but not destroyed** on our exe vs destroyed on retail / Gold: find out why before comparing outcome
  rates across exes.
- **Independence:** T05 placed jumps within one boot repeat to 0.1 m/s. Count boots, or perturb the placement (design
  L2), before any Fisher test on jumps.
