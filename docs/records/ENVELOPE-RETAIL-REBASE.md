# Era-envelope candidate re-baselined on retail's step (2026-10-17 night)

EMU-MEMTRACE section 7 item 4. The ERA-ENVELOPE candidate (owner test 42, lab twin `TEST-envelope-candidate.bat`,
30 ms fixed steps) took its step from Gold-exe emulator profiles. The gold standard is retail 1.0 on the emulated P166 at
low detail (GOLD-STANDARD-FINGERPRINT.md). This lane measured retail's step distribution, built lab profiles that match it,
and ran the fingerprint compare on our exe at those profiles.

- **Where:** a new headless lab copy `game-envrb` (a copy of `game-replay` = the twin's files, i76.exe 6319abf7, the null
  renderers from LAB-FRAME-REPLAY). The proxy there is a side build, lab `builds\envelope-rebase-20261017\Strlkup-envrb1.dll`
  (md5 cbcff703). It is HEAD `music-fix` (5138677) plus three lab blocks: `I76_STEP_SEQ`, `I76_RH_DRIVE` and
  `I76_HEADLESS_ACTIVE` (section 1).
- **Runs:** 100 headless boots (97 campaign + 3 smoke), 02:13-05:40. Each boot took the console lock (`tools\replay\with-lock.ps1`); there was no
  default playback endpoint in the session (0x80070490). No 86Box VM was started by this lane.
- **Not touched:** the daily driver, the golden copy, the portable install, the twin and its proxy (33211f11).
- **Lab tools:** `tools\envelope-rebase\`. Captures are in lab `captures\envelope-rebase-20261017\` (git-ignored). Tables
  are in `tools\envelope-rebase\results\`. Lab commits c3828d0, 866d7b1.

## Summary

- **Retail's step depends on the scene, ours does not.** Retail's median physics step is 27 ms in melee, 28 in the yaw3
  melee protocol, 32 in T05, 33 on the T06 strip and 35 on the T06 route (table 2.1). In our exe a fixed step or a step
  list is the same in every scene: the 120 fps render only decides which frame a step lands on.
  - So no single lab profile matches retail's step rows in more than one context. Simulated, n 3 windows each: the
    candidate's fixed 30 ms passes 0-3 of 5 step rows per context. The pooled retail list passes 0-4.
  - A step list taken from one context passes all 5 of that context's rows (simulated: T05, strip, melee). Measured:
    `seqt05` in T05 and `seqstrip` on the strip, n 3 boots each, 5 / 5.
  - The rows that compare rendered frames (sim_dt per frame, the one-step share, the substep rule) fail for every
    120 fps profile, by design.
- **Pacing does not move the handling rows. They fail by the same amount in every profile.** T06 strip, n 3 boots per
  profile, 6 profiles:
  - t20 2.75-2.77 s against retail's 4.18;
  - d10 254-255 m against 201.5;
  - yaw at the 18 m/s strip step 0.793-0.799 rad/s against 1.12;
  - ramp-A foot speed 38.5-38.9 m/s against 35.3.
  - The spread across profiles (under 1 %) is the size of the A/A (seqpool vs seqpoolaa: 0.794 / 0.794 rad/s, t20
    2.76 / 2.77 s).
  - **Plainly: these fails are not pacing, and on the strip they are not "Gold physics" either.** Gold on the emulator
    matches retail on this strip (yaw -0.4 %, GOLD-STANDARD-FINGERPRINT). The lab car is the known different car
    (lighter / stronger; LAB-FRAME-REPLAY, GOLD-STANDARD-FINGERPRINT finding 2).
  - Gold's own yaw gap shows only in slides (melee 25 m/s, +19 %). It was not measured here: melee cannot run headless.
- **The T05 placed jump (56 m/s, 150 m before the ramp) is where the pacing shows. The car gap matters little there,
  because the placement sets the speed.**
  - The stock exe at retail's frame rate (`e32`: no fix switches, stock stepper, 31.3 fps, 1 ms tick) reproduces retail's
    flight: take-off 51.4 +- 0.6 m/s vs 51.6 and apex 10.56 vs 10.66 m (n 33 vs 7). It had 0 / 33 turn-overs and every
    take-off was clean.
  - The candidate (`env30`) takes off 1.5 m/s slower: 50.1 +- 1.5, apex 10.07, both gate FAIL. It had 0 / 33 turn-overs.
  - **Retail-matched step lists turn the car over after this landing:**
    - `seqt05`: 6 / 25 turned over, 2 destroyed (Fisher p 0.004 vs env30's 0 / 33);
    - `seqt05nc` (the same with the collision-window and barricade switches off): 3 / 18 (p 0.04);
    - `seqpool`: 2 / 33, 1 destroyed;
    - retail: 0 / 7 (p 0.30 / 0.53: retail's n is too small to call).
    - Fixed steps did not turn over: 0 / 33 at 30 ms, 0 / 27 at 32 ms.
    - Reading: the long steps in the list (p95 39-42 ms, up to 50) land on the touch-down at random. Retail's long
      steps come with what is on screen, so they need not fall there. ERA-ENVELOPE showed turn-over grows with the step.
  - **A second failure, from a fix switch:** with `I76_FRAMERATE_FIXES` (+ `I76_HIRES_CLOCK`) at 32 ms steps the car
    sometimes hits the ramp lip and falls into the canyon. It drifts 7-10 m off the centre line, gets vy -9 m/s at x 6876,
    and lands at y 2. Counts:
    - 19 / 99 placed jumps across six profiles with that switch at 32 ms (Fisher p 0.0002 vs the next line);
    - 0 / 54 at 32 ms without it (the fixed step alone, + hull fix, + render interpolation, + engine dt fix);
    - 0 / 45 at 30 ms with it (env30, fs30fr);
    - the reference rate does not matter (REF_FPS 30 vs 31.25: 2 / 12 each).
- **Gravity (rule):** 9.80 per step in every profile. In the 96 steps of one drop, every vy change was 9.8 times a
  listed step size.
  - Under a step list, the fingerprint's `g` row reads 9.77-9.78 (FAIL, -0.2 %). That is the metric: it measures slope
    against frame time, while the physics clock runs on the list.
- **Candidate decision: unchanged (fixed 30 ms).** Owner test 42 keeps its launcher. The reasoning changes (section 5):
  - 30 ms is not retail's step in any context. It sits inside retail's range everywhere (T05 p5-p95 22-38 ms).
  - The profiles that match retail's step distribution make the T05 landing worse.
  - 32 ms matches retail's T05 flight only without the frame-rate fixes, and the candidate cannot drop those today.

## 1. What was built (lab)

- **`I76_STEP_SEQ=<file>` (side build only; insert script `builds\envelope-rebase-20261017\insert-seq.py`).** Under
  `I76_FIXED_STEP`, the steps take their sizes in turn from a list (ms per line, cyclic, `I76_STEP_SEQ_START`).
  - One global accumulator advances once per frame, so every vehicle steps on the same frames with the same size, as
    the 1997 exe splits one frame dt.
  - `g_fixed_step` holds the pending step's size, for render interpolation, the collision windows and the AI clock.
  - The engine update reads the current step: stock reads the whole frame dt, and that equals the step at one step per
    frame.
  - **Read back:** in run t05-seqpool-smoke2 the player's stepper sizes followed the list for 3,615 of 3,616 steps. The
    one missing step was a frame where the player's stepper did not run (a placement); the global clock consumed it.
- **Step lists:** `tools\envelope-rebase\retail_steps.py`. Per-step sizes (sim_dt / step_count) of every reference
  frame, in trace order, by context.
  - `seq\retail-{melee,t05,t06strip}.txt`: 30,594 / 21,310 / 16,174 steps.
  - `retail-pooled.txt`: four contexts in turn, 64-step chunks, 64,750 steps, mean 31.9 ms.
- **Headless driving:** `envrb_drive.py` runs `tools\box-spec\phys-suite.py` unchanged. It swaps `user32.keybd_event`
  for writes into `Local\I76RhDrive` (the rh3 drive block: held-key bytes set before input_ApplyToEntity).
  - **The drive block's comment has the steer bits swapped.** Measured against console capture t06-env30-1: the real D
    key gives steer -0.91 and a turn toward +x. The smoke run with bit 3 = D gave +0.91 and a turn toward -x. So
    D = bit 2 and A = bit 3.
  - The first two smoke runs had them the other way round and are kept with an `-ADSWAPPED` suffix.
- **Runner:** `envrb-run.ps1`, one boot. It applies the twin's preset plus overrides, and sets `I76_FPS_CAP=120` because
  the null renderer has no vsync. The candidate's 120 fps comes from dgVoodoo's 120 Hz.
  `envrb-campaign.ps1` interleaves conditions and reverses the order on even rounds.
- **Measures:**
  - `t06`: phys-suite jump 26 / 30 / 34, drop, accel, brake, steer = the `t06strip` context;
  - `t05`: 3 descents + 3 placed 56 m/s jumps;
  - `t05p`: 6 placed; `t05d`: 6 descents.
- **Check of the headless path:** headless env30 on the strip gave t20 2.75-2.77 s, d10 254 m and yaw 0.795. Console
  env30 (2026-10-15) gave 2.76 s, 254.6 m and 0.79.

## 2. Pacing

### 2.1 Retail's physics step (ms, step-weighted; reference traces, simulation physics)

| context | traces | steps | p5 | p25 | p50 | p75 | p95 | mean |
|---|---|---|---|---|---|---|---|---|
| melee (loop) | 12 | 30,594 | 24.0 | 26.0 | 27.0 | 29.0 | 34.0 | 27.7 |
| melee yaw3 | 9 | 17,684 | 25.0 | 27.0 | 28.0 | 31.0 | 36.0 | 29.2 |
| T05 | 16 | 21,310 | 22.0 | 29.0 | 32.0 | 34.0 | 38.0 | 31.3 |
| T06 route | 6 | 24,692 | 31.0 | 33.0 | 35.0 | 37.0 | 43.0 | 35.4 |
| T06 strip | 6 | 16,174 | 23.0 | 31.0 | 33.0 | 35.0 | 40.0 | 32.8 |

One step per frame on 98-100 % of frames, so this is also retail's frame time. The brief's "26-30 ms" holds for melee
only. Missions run 31-35 ms.

### 2.2 Step rows against the reference

Simulated: `pacing_sim.py` replays the proxy's accumulator at 120 fps, 3 windows of 150 s, and applies the
fingerprint's pass band (`results\pacing-sim.md`). The rows are step p5 / p50 / p95 / mean / steps per s.

| profile | melee | yaw3 | T05 | T06 route | T06 strip |
|---|---|---|---|---|---|
| env30, fixed 30 ms (candidate) | 0 / 5 | 3 / 5 | 3 / 5 | 1 / 5 | 1 / 5 |
| fs31, fixed 32 ms | 1 / 5 | 0 / 5 | 3 / 5 | 2 / 5 | 1 / 5 |
| seqpool, pooled list | 1 / 5 | 0 / 5 | 4 / 5 | 1 / 5 | 3 / 5 |
| seqt05 / seqstrip / seqmel | 0-3 / 5 off-context | | **5 / 5** (seqt05) | 1 / 5 | **5 / 5** (seqstrip) |
| seqmel, melee list | **5 / 5** | 4 / 5 | 1 / 5 | 1 / 5 | 2 / 5 |

Measured, our exe (main campaign, n 3 boots per profile):
- T05, seqt05: step mean 31.53, p50 32.00, p5 22.00, p95 38.99, steps/s 31.71. All 5 PASS.
- Strip, seqstrip: 32.98 / 33.01 / 23.00 / 41.00 / 30.32. All 5 PASS.
- env30: 30.00 on every row. It fails p5 and p95 everywhere, and p50 on the strip (-3.0 ms, tolerance 0.5).

**Caveat (n 11).** With the 8 extra descent-only and placed-only boots added, seqt05's T05 p50 reads 32.36 and fails
(tolerance 0.85). Every boot starts the list at index 0, so a short boot replays only the start of it. Next build: a
per-boot random `I76_STEP_SEQ_START`.

## 3. Handling (the T06 strip, n 3 boots per profile; the fingerprint's `t06strip` rows)

| | retail (n) | e32 | env30 | fs31 | seqpool | seqpoolaa | seqstrip |
|---|---|---|---|---|---|---|---|
| t20, s | 4.18 (6) | 2.75 | 2.76 | 2.77 | 2.76 | 2.77 | 2.77 |
| d10, m | 201.5 (6) | 255 | 254 | 254 | 254 | 254 | 255 |
| yaw at 18 m/s placement, rad/s | 1.12 (12) | 0.799 | 0.795 | 0.796 | 0.794 | 0.794 | 0.793 |
| speed in that window, m/s | 24.0 | 28.0 | 27.8 | 27.7 | 27.8 | 27.8 | 27.8 |
| ramp A foot at 30 m/s, m/s | 35.3 (5) | 38.6 | 38.6 | 38.7 | 38.6 | 38.5 | 38.9 |
| drop g | 9.80 | 9.80 | 9.80 | 9.80 | 9.81 | - | 9.77 (metric, section Summary) |

- Every handling row fails in every profile, by the same amount. The car is the cause, not the pacing.
- **Expected yaw / slide FAIL from Gold physics: not separable here.** The strip is a grip-limited turn (skid 0 %), and
  there Gold = retail. The slide branch, where Gold yaws +19 %, is a melee measurement. Melee could not run headless
  (LAB-FRAME-REPLAY s.4: the shell takes no posted clicks), so **melee was not run** (n 0 of the brief's 3).
- Gate counts: rule 2-3 / 3 pass in every profile (`rule.substep_share` fails under any fixed step, by design).
  Behaviour 11-13 PASS / 15-17 FAIL. Platform: env30 1 / 9, seq profiles 4-5 / 9.

## 4. The T05 canyon (`results\outcomes-t05.md`; boots pooled over t05 / t05p / t05d)

| profile | placed 56: n | no take-off | turned over (destroyed) | take-off m/s | apex m | descents: n | turned over (destroyed) |
|---|---|---|---|---|---|---|---|
| retail 1.0 | 7 | 0 | 0 (0) | 51.6 | 10.66 | 9 | 1 (1) |
| e32: stock exe, 31.3 fps, 1 ms tick | 33 | 0 | 0 (0) | 51.4 +- 0.6 | 10.56 | 33 | 0 (0) |
| env30: candidate, 30 ms | 33 | 0 | 0 (0) | 50.1 +- 1.5 | 10.07 | 33 | 0 (0) |
| fs31: candidate at 32 ms | 27 | 7 | 0 (0) | 52.8 +- 1.0 | 11.16 | 9 | 0 (0) |
| seqpool | 33 | 3 | 2 (1) | 52.3 +- 1.8 | 10.96 | 28 | 3 (1) |
| seqpoolaa | 9 | 1 | 1 (0) | 51.7 +- 0.9 | 10.70 | 9 | 0 (0) |
| seqt05 | 25 | 1 | 6 (2) | 51.4 +- 2.3 | 9.95 | 33 | 1 (0) |
| seqt05nc: no coll window / box | 18 | 1 | 3 (0) | 50.3 +- 2.3 | 10.12 | - | - |

- **Descents (crest)** start from the hill top, so the lab car's run-up is faster than retail's: foot speed 62-63 vs
  55 m/s (OUT in every profile). Only the lab-vs-lab differences mean anything there. Turn-over: seqpool 3 / 28 vs env30
  0 / 33 (p 0.09).
- **Missing jumps:** a destroyed car ends the mission, so the later phases of that boot have 0 frames. seqt05 placed
  lost 6 jumps that way and seqpool's descents lost 4. Rates count only the jumps flown.
- **Take-off speed (clean jumps)** goes with the step and the switches:
  - 30 ms: 50.1;
  - 32 ms, fixed step alone: 51.4;
  - 32 ms with the frame-rate fixes: 52.2-53.4;
  - stock at 31.3 fps: 51.4;
  - retail: 51.6.

### 4.1 Bisect of the lip failure (placed 56 m/s, 32 ms fixed step unless noted)

| switches on top of the fixed step | no take-off / jumps |
|---|---|
| none (`fs31bare`) | 0 / 18 |
| + I76_TERRAIN_HULL_FIX | 0 / 12 |
| + I76_RENDER_INTERP | 0 / 12 |
| + I76_ENGINE_DT_FIX, REF 31.25 | 0 / 12 |
| + I76_FRAMERATE_FIXES + I76_HIRES_CLOCK, REF 31.25 (`fs31fr`) | 2 / 12 |
| the same, REF 30 (`fs31fr30`) | 2 / 12 |
| frame-rate fixes + hires + engine dt (`fs31rate`) | 3 / 12 |
| the whole candidate preset (`fs31`) | 7 / 27 |
| the candidate minus coll window + barricade box (`fs31nc`) | 2 / 18 |
| the candidate, one step per frame at 31.25 fps (`fs31cap`) | 3 / 18 |
| 30 ms, frame-rate fixes + hires, REF 30 (`fs30fr`) | 0 / 12 |
| 30 ms, the whole candidate (`env30`) | 0 / 33 |

- Not separated: `I76_FRAMERATE_FIXES` from `I76_HIRES_CLOCK`, or which of the frame-rate fixes it is. The player-side
  parts are the throttle-up / throttle-down ramps, and the hazard and per-frame sub-fixes.
- Not 120 fps decoupling: `fs31cap` steps once per frame and still fails.
- The failing jumps leave the centre line on the ramp: by 8.0-10 m before the lip (n 23 by a 'lands below y 5 short of x 6800' rule). Clean ones: p95 3.4 m, max 9.3 (n 295). So the drift is necessary, but it is not enough to explain the failures.
- **It bears on `TEST-p166-retail-step.bat`** (31.75 ms with the frame-rate fixes, owner test 44). That launcher was not
  measured. Owner check below.

## 5. Candidate (owner test 42)

- **Unchanged:** `TEST-envelope-candidate.bat`, fixed 30 ms, REF 30, AI clock 1.5 ms / 30 fps, proxy 33211f11. No file in
  the twin changed.
- **What changes is the stated basis.**
  - 30 ms is not "the P166 at low detail". Retail's step there is 27 ms (melee) to 32-35 ms (missions).
  - 30 ms is the step at which our fix set lands the T05 jump cleanly. Against retail it costs about 3 % take-off speed
    (50.1 vs 51.6 m/s, apex -0.6 m, n 33 vs 7).
  - The fixes and step sizes that would close that gap (32 ms) need the frame-rate-fix lip failure solved first.
- **Rejected for now:**
  - a retail step list (`I76_STEP_SEQ`): it matches the pacing rows but turns the car over on the placed landing,
    6 / 25 vs 0 / 33;
  - a fixed 32 ms: lip failures, 7 / 27.

## 6. Not done

- **Melee:** n 0 (headless shell). The pacing there is computable (section 2.2). The handling needs the console or a
  headless shell.
- **The car gap:** not addressed here (GOLD-STANDARD-FINGERPRINT next steps). Every handling row waits on it.
- **Which frame-rate fix causes the lip failure** (section 4.1). Next: split `I76_FRAMERATE_FIXES` per site, starting with
  the throttle ramps, and re-run `fs31` t05p.
- **The step list's start offset:** per boot, or keyed to the scene. A scene-keyed list (by mission) was not built.
- `I76_STEP_SEQ` is not in the i76-everywhere source; it exists only in the side build.

## 7. Files

- Lab `tools\envelope-rebase\`: retail_steps.py, pacing_sim.py, envrb-run.ps1, envrb_drive.py, envrb-campaign.ps1,
  run-night2.ps1, run-night3.ps1, summarise.py, outcomes.py; `seq\` (step lists); `results\` (summary.md,
  outcomes-t05.md, pacing-sim.md, compare\compare-*.md per profile).
- Lab `builds\envelope-rebase-20261017\`: insert-seq.py, insert-drive.py, drive-block.c, build.cmd, README.txt. The DLL
  and source snapshot are git-ignored or untracked by policy.
- Check any new capture: `python -I emu\tools\memtrace\fingerprint.py compare captures\envelope-rebase-20261017\t06-<profile>-r*.phys.csv`.
