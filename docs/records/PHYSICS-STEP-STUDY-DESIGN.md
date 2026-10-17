# Which physics step should the port use? Study design, pre-registered (2026-10-17)

The question: the port runs a **fixed** physics step, decoupled from the render rate (owner decision 2026-10-17). How
long should that step be?

The answer is meant to be written up for the I'76 community, so the method, the metrics and the decision rule are
fixed here, **before the data**.

- **Evidence base:** [DEV-INTENT-EVIDENCE.md](DEV-INTENT-EVIDENCE.md), with code clues C1-C7 and per-step terms
  P1-P10.
- **Inputs from the running workflow** "versions-and-physics-2026-10-17", consumed here and not duplicated:
  - I76-VERSIONS.md (landed);
  - EXE-DIFF-MAP.md (landed);
  - HARDWARE-MATRIX.md (running: `hwm-r133low-*` and `hwm-r166low-*` runs are in lab `emu\results\par`);
  - STEP-LENGTH-CURVE.md (our exe at 8-55 ms);
  - AI-DAMAGE-*.md (AI-DAMAGE-METRICS.md landed).

**Owner rulings that bind this design:**
- The reference exe is retail 1.0, simulation physics.
- P133 is wanted again.
- Remembered feel is not evidence.
- The P166 lowest-detail step is a lower bound, not the answer. The longest step the engine and the era tolerate is an
  upper bound.
- Order of methods:
  1. code;
  2. content;
  3. the middle of the bounds, working outward;
  4. then a blind taste A/B on the shortlist.

## 0. Summary

- **Bounds: 27 ms <= T < 50 ms.**
  - **Lower:** retail 1.0 on the emulated P166 at lowest detail steps 26.8 +- 0.9 ms in melee (p50; 12 traces,
    3 boots). That is the shortest plausible 1997 step. The code's own floor for slow machines is 25 ms (C2), and the
    contact model buzzes below about 25 ms (P4).
  - **Upper:** the engine's maximum substep, `StepperInit(0.05)` on every vehicle (C1). No 1997 machine ever ran a
    substep of 50 ms or more.
- **Candidate grid:** 27, 30, 33.3, 36.7, **40**, 43.3, 46.7, 49 ms (37.0 / 33.3 / 30 / 27.3 / 25 / 23.1 / 21.4 /
  20.4 steps/s). The 40 ms cell runs first (owner rule 3).
  - Then the two code-clue points: 30 ms (C3, P6) and 46.7 ms (P1).
  - Then the rest.
  - Then a refinement at +-1.7 ms around the leader.
- **The code's clues conflict.**
  - Landing self-consistency (P6) wants about 26-35 ms for T05-size landings.
  - Car-like body frequency (P1) wants 44 ms or more.
  - So the main pre-registered hypothesis is a trade-off: landing survival falls with T, ride realism rises with T. The
    study measures where they cross the thresholds.
- **Decision rule (section 6):**
  - Hard constraints first: within bounds; numerically calm; designed jumps and AI routes work; landing survival;
    AI / damage sane.
  - Then playability (the T05 margin and survival).
  - Then realism (body frequency, momentum).
  - Then the blind taste A/B. Each later stage only breaks ties the earlier one leaves (95 % intervals overlap).
  - If nothing discriminates: 40 ms.
- **Implementation (section 7):** a whole-simulation fixed tick. Every per-frame sim system runs once per tick with
  sim_dt = T, and only rendering runs per display frame, with interpolation.
  - This restores the 1997 coupling (one frame = one step) without the rescaling patches.
  - It is verified against the emulator at the hardware config whose step is nearest T.
- **Measure next:** section 9.
  - First: the landing-survival vs step curve with independent jumps.
  - Then the measured body ride frequency per step.
  - Then retail at long steps (P133, P166 default detail).
  - Then AI routes.
- **Resolved today: the SFX caveat.** Every retail simulation-mode emulator run since the DEF fix wrote a DEF with
  music 3, SFX 4, voice 10, flags 0 (59 runs read back from `SCRIPT.TXT`; bytes 0x4e / 0x4f / 0x50).
  - So retail's simulation-mode frame rate (melee 36.0 +- 1.4 fps, n 8) was measured with sound on, like Gold's
    (31.0 +- 0.4, n 4).
  - Only the older I76FPS table (EMU-MEMTRACE s.3, "+24-39 %") had retail at SFX 0.
  - The Gold side's SFX 4 comes from MUSIC-RETAIL-INTENT and was not re-read here.
  - One difference remains: retail plays CD audio tracks and Gold has none.

## 1. Bounds

| bound | value | basis | conf. |
|---|---|---|---|
| lower L | **27 ms** | retail emu P166 lowest detail, melee p50 26.8 (missions 31-35). Also the code's slow-machine floor of 25 ms (C2) and the measured buzz onset below about 25 ms (P4) | high for the number. The real P166 would be 15-20 % longer (emu calibration). Faster 1997-98 machines (P200 MMX, PII) could step shorter; HARDWARE-MATRIX may extend L downward, which owner rule 1 then decides |
| upper U | **< 50 ms** | `StepperInit(0.05)` at all three vehicle-stepper sites (C1). floor + 1 means a step never equals 50 ms | high |
| era as played | 30-47 ms typical | P90 software 3 x 47; P90 Glide 2 x 30; P166 default detail 2 x 37.6; P166 low 27-35 (emu), about 32-42 real | medium (emulator, n 1-3 per config) |

## 2. Candidate grid and search order

| T ms | steps/s | why it is in the grid | order |
|---|---|---|---|
| 27.0 | 37.0 | L: retail melee at P166 low | 4 |
| 30.0 | 33.3 | C3 (the 60 ms preset frame splits to 2 x 30); P6 at T05 take-off vy; the current lab candidate env30 | 2 |
| 33.3 | 30.0 | retail T05 / T06 p50 (31-35) | 4 |
| 36.7 | 27.3 | real-P166-low estimate (missions); P166 default detail 2 x 37.6 | 4 |
| **40.0** | 25.0 | middle of [27, 50) (owner rule 3) | **1** |
| 43.3 | 23.1 | P1's 2 Hz edge (43.8) | 4 |
| 46.7 | 21.4 | P1 (fn 1.87 Hz); P90 software substeps (47); our stock20 average (41.7-46.9) | 3 |
| 49.0 | 20.4 | U probe: the longest step the engine allows | 4 |

The grid runs to the end even if an early cell looks good. That guards against stopping at the first acceptable step.
After the full grid, the two neighbours of the leader at +-1.7 ms are added.

## 3. Pre-registered hypotheses (from the code, before the data)

- **H1 (P6, P5): landing survival falls as T rises.**
  - Prediction: T05 turn-over / destroyed rate rises with T. It is near 0 at 27-30 ms and clearly non-zero by 40 ms.
  - Existing hint: ERA-ENVELOPE E25 (40 ms) 7/11. That hint was measured on the lab car with a different
    stack, so it is a hint, not a prior.
- **H2 (P1): the measured body ride frequency follows fn = 0.0876 / T Hz.**
  - Push-out and the pitch ease (P3-P5) may shift it.
  - Prediction: within +-25 % of 0.0876 / T. Rejected if off by more.
- **H3 (P7): T05 take-off speed rises with T** (fewer lag steps), by about +1 m/s per 5 ms.
- **H4 (P4): the body rest share rises and buzz falls as T rises.** Every grid cell is calm (above 25 ms).
- **H5: under a whole-sim tick (section 7), behaviour depends on T and not on the render rate.**
  - Prediction: render 60 vs 120 fps at fixed T gives an A/A-sized difference.
  - The E13 / E25 anomaly in ERA-ENVELOPE (2 x 37.6 ms steps: 2/13 turn-overs; 1 x 40 ms: 7/11; Fisher p about 0.04)
    says per-frame code may matter. H5 tests that it no longer does.
- **H6 (null expected): AI lap times and damage rates are insensitive to T within the band** once AI runs once per
  tick.

## 4. Metrics

Every metric comes from memory traces with the same definitions in the emulator (I76MEM / I76AIM) and in the lab
(proxy telemetry `.phys.csv`, `I76_REPLAY` `.lab.csv`). `fingerprint.py` computes the shared ones. The new ones get
added to it (task A1).

| group | metric | definition | source fields | context | covered by |
|---|---|---|---|---|---|
| jump | clear probability vs speed | logistic fit of "landed beyond the far lip (x < 6744) and not destroyed" on take-off speed; report v50 and v90 | x, y, speed, flags 0x4 / 0x200 / 0x8020 | T05 placed, speed sweep 46-58 m/s | new (L2) |
| jump | margin | (median take-off speed of a full-throttle crest descent - v50) / v50 | as above | T05 crest | fingerprint t05/crest + L2 |
| landing | turn-over / destroyed | per jump: up.y < -0.5 within 3 s / flag 0x80000020 | rot rows, flags | T05 placed56 perturbed; T06 ramp A | fingerprint (CheckImpact outcome) |
| landing | peak pitch / roll | max \|angle\| airborne + 3 s | rot rows | same | fingerprint (watch) |
| landing | snap size | origin y jump on the landing step (tests P6) | y, clearance | same | new (A1) |
| body | ride frequency and damping | fit a damped sinusoid to clearance / pitch after a step input: the landing on T06's flat run-out, and a placed drop of 0.3 m onto flat ground; also the pitch-rate spectrum peak while cruising on the T06 strip | clearance 0x470, pitch rate 0xc8 | T06 strip, drop | new (L4, E5) |
| body | buzz / limit cycle | roll and pitch reversals per s at cruise; rest share (rates exactly 0); any sustained (>= 2 s) reversal rate > 5 /s | rates | melee cruise, T06 strip | fingerprint (body), STEP-LENGTH-CURVE |
| momentum | coast-down and brake | decel from 30 m/s coasting (excess over the integrator, P7) and stopping distance from 30 m/s | speed, acc 0xd4 | T06 strip | fingerprint (brake), new coast |
| momentum | slide | yaw rate and slip at 25 m/s full steer | yaw, v_lat | melee yaw3 | fingerprint (yaw3) |
| stability | numeric | NaN / inf, speed spikes > 100 m/s^2 off contact, parked rates != 0 | all | all | fingerprint (rules) |
| AI | route completion | share of scripted goto / race / follow paths finished within the mission timer | AI positions, FSM state | T04 laps, T05 paths, T13 | AI-DAMAGE lane + L5 |
| AI | lap time | T04 Patriot / Knight laps | AI positions | T04 | ERA-ENVELOPE rows |
| damage | rates | damage taken / dealt per sim minute; time-to-die (player parked, T13); time-to-kill | I76AIM records | T13, melee2 | AI-DAMAGE lane |
| pacing | step read-back | stepper +0x448 constant = T; steps / s = 1 / T; gravity 9.8 x T per step | stepper, vy | all | fingerprint (rules) |

**Real-car plausibility bands** (the realism stage), sources in DEV-INTENT-EVIDENCE s.6:
- ride frequency 1.0-2.0 Hz: the passenger-to-sedan-racecar range; a 1970s muscle car sits at the soft end;
- damping ratio 0.2-0.7 (fixed at 0.65 by P1, so it does not discriminate).

No band is used for roll gradient or slide until a source is found. Those metrics are compared to retail instead.

## 5. Experimental design

### 5.1 Factors and arms

- **Main factor:** T over the grid (section 2), on our exe, under the whole-sim fixed tick (section 7). Same car and
  save as the emulator reference: the lab car gap must be closed first (GOLD-STANDARD-FINGERPRINT finding 2; task
  L0).
- **Render rate** (H5): at T = 33.3 and 46.7, render capped at 60 and at 120 fps. 2 x 2 cells, n 10 jumps each.
- **Jitter arm:** T = 33.3 mean, with each step drawn from retail's T05 step list. A random start per boot is needed,
  the fix ENVELOPE-RETAIL-REBASE asked for. This separates "mean step" from "step variance": that lane saw list
  replay turn cars over (5/7 boots vs 0/7).
- **Retail reference at several steps (a natural experiment on the original exe):**
  - retail 1.0 emulated at P133 low, P166 low, P166 at the owner's 1997 settings (software, 640x480, mirror on,
    default sound) and P166 default detail;
  - HARDWARE-MATRIX supplies the configs and step distributions;
  - per jump, record the step at take-off and over the 10 steps after touch-down. Outcome against local step gives
    the original exe's own step-response curve. Our exe at the same T must fall on it (verification, section 7.3).

### 5.2 Sample size and independence

- **Binary outcomes** (turn-over, clear):
  - n = 30 independent jumps per cell, from >= 6 boots.
  - Fisher power is about 0.8 for 2 % vs 25 % at alpha 0.05.
  - For the speed-sweep logistic: 7 speeds (46-58 m/s in 2 m/s steps) x 6 = 42 per cell.
- **Continuous metrics:** >= 6 windows from >= 3 boots per cell. The pass bands use fingerprint.py's boot-level
  variance (method of moments, Welch df).
- **Independence:**
  - Earlier placed jumps landed on a few discrete states (ENVELOPE-RETAIL-REBASE 4.1: 17 of 19 failures were one
    trajectory). So every jump gets a perturbation from a pre-generated list (seeded, committed with the scripts):
    placement x and z offsets uniform +-0.5 m, speed 56 +- 1 m/s, a release delay uniform in [0, T), and a heading
    offset of +-0.3 deg.
  - Jumps are deduplicated by (take-off speed, vy) rounded to 0.01. Report n and n_eff.
  - Rates are reported per jump and per boot (cluster bootstrap by boot).
  - In-session repeats are allowed only when the A/A between repeat 1 and repeats 2+ holds; EMU-MEMTRACE s.3 showed
    it for melee.
- **Controls:**
  - Every campaign runs an A/A cell (40 ms twice, under two codes) to measure the noise floor.
  - The order of cells is randomised and reversed on alternate rounds (envrb-campaign's pattern).

### 5.3 Contexts

| context | why | runner |
|---|---|---|
| T05 placed56, perturbed | landing, take-off, flight | lab headless `envrb-run.ps1` (`t05p`); emu `gen_t05jump.py` |
| T05 speed sweep | v50 / margin | same, with SPEED from the list |
| T05 crest descent | margin at full throttle | `t05d` / `gen_t05clean.py` |
| T06 strip and ramps A-E | body, momentum, the 5 scripted jump cameras | phys-suite `t06`; `gen_t06.py` |
| flat drop 0.3 m | ride frequency | new phase (I76DRV `place` with a y offset) |
| T04 race | AI laps | ERA-ENVELOPE's T04 protocol |
| T13 parked, melee2 | damage rates, TTK | AI-DAMAGE `aidmg*` scripts; I76AIM on the host for our exe |
| T12 `gotair`, T16 `jump1` | scripted mission-ending jumps work | new route scripts (L6) |

## 6. Decision rule (fixed now)

**Stage 0, bounds.** 27 <= T < 50.

**Stage 1, hard constraints.** All must pass. Rates use the 95 % Wilson upper or lower bound as stated.
- **B1 calm:**
  - no NaN or impulse spikes off contact;
  - parked rates 0;
  - cruise reversal rate inside the retail melee band (fingerprint watch row);
  - no boot with a sustained limit cycle (> 5 reversals/s for >= 2 s).
- **B2 designed jumps work:**
  - T05 placed56: clear >= 90 % (lower bound >= 75 %);
  - T05 crest descent: clear >= 70 %;
  - T06 jump1-5: each airborne camera fires and the car lands upright in >= 90 % of tries;
  - T12 `gotair` and T16 `jump1`: success reached in >= 4 / 5.
- **B3 landing survival:** T05 placed56 turned over <= 10 % (upper bound <= 25 %), destroyed <= 5 %.
- **B4 AI and damage sane:**
  - T04 laps inside the retail band at the nearest-step config;
  - T13 time-to-die and damage per minute within +-25 % of retail at the nearest-step config;
  - every scripted AI path that retail completes is completed.

**Stage 2, playability (only cells that pass Stage 1).**
- Score P = mean of three parts:
  - **canyon challenge:** 1 if the margin is 2-10 %, falling linearly to 0 at 0 % and at 20 %. "Possible but
    challenging": retail's own margin is +3-7 %.
  - **survival:** 1 - turn-over rate.
  - **T06 clean landings.**
- Keep every cell whose P interval (bootstrap 95 %) overlaps the best cell's.

**Stage 3, realism (among those).**
- Score R = 2/3 x ride-band score + 1/3 x momentum score.
  - Ride-band score: 1 inside 1.0-2.0 Hz, falling linearly to 0 at 3.0 Hz. Measured frequency, not 0.0876 / T.
  - Momentum score: coast and brake inside the retail band at the nearest-step config, 1 or 0 per row, averaged.
- Keep the cells whose R interval overlaps the best.

**Stage 4, taste (blind A/B, section 8).**
- Among the remaining <= 4 cells, the Bradley-Terry leader wins.
- If it is not separated from the runner-up (its 95 % interval includes 0.5 for that pair), the cell nearer 40 ms
  wins.

**Fallbacks, applied in this order, each recorded in the paper:**
1. No cell passes Stage 1: relax B4 to +-50 %.
2. Then relax B3 to <= 20 %.
3. B1 and B2 are never relaxed.
4. Still none: the cell that passes the most Stage 1 rows; ties go to the cell nearer 40 ms.

A metric that cannot be measured for a cell counts as a fail for that cell. It is reported, not imputed.

## 7. The fixed step: implementation and verification

### 7.1 What exists (lab / proxy, `music-fix/strlkproxy.c`)

- `I76_FIXED_STEP=<rate>` replaces `simclock_StepperBegin` 0x49cc20 with a per-stepper accumulator. Each frame adds
  sim_dt and runs as many whole steps of 1 / rate as have accumulated (max 20). The rest is carried.
- `I76_RENDER_INTERP` draws vehicles between physics poses.
- The per-frame systems still run once per **rendered** frame, with the frame's sim_dt. A set of patches compensates:
  - `I76_COLL_WINDOW`: the collision sweep covers the step;
  - `I76_AI_STOCK_CLOCK` / `I76_AI_GRID_HZ` and `I76_AI_SKID_HOLD`: the AI runs on a step grid;
  - `I76_FRAMERATE_FIXES`: throttle ramps, cameras, flamer, smoke and fire rolls;
  - `I76_INPUT_LATCH`: one-frame keys.
- That patch set has already produced one unexplained failure: the T05 lip failure at 32 ms comes from
  `I76_FRAMERATE_FIXES` (ENVELOPE-RETAIL-REBASE 4.1).

### 7.2 What the study uses: a whole-simulation tick

- **The rule:** in 1997, below 50 ms, one rendered frame was one physics step. Every per-frame system (P10) therefore
  ran once per step. The faithful fixed-step port keeps that coupling and moves rendering out of it.
- **Loop.** The WinMain hot loop is 0x4039a0..0x403f20. The simulation part runs `n` times per display frame:
  - `simclock_Update`, with dt forced to T;
  - input;
  - the object ticks 0x461c80;
  - collision 0x4349c0;
  - the post-ticks 0x461d50;
  - AI / VM 0x40a320;
  - 0x462a90, projectiles 0x4a0410, weapons and 0x44af80.

  `n` comes from a wall-clock accumulator: floor(acc / T), at most 20, and the rest is carried. The render part
  (0x403e78..0x403eaa) then runs once with poses interpolated by alpha = acc / T.
- **Inside each tick:**
  - sim_dt 0x4fe420 = dt 0x4fe428 = T, and the rates 0x4fe424 / 0x4fe42c = 1 / T;
  - `simclock_StepperBegin` then gives count 1 and step T unchanged (T < 50 ms), so no stepper patch is needed;
  - the accumulated script clock (0x5a7e14) advances by T.
- **Input:** sampled once per display frame and latched. Each pulse is consumed by exactly one tick, and held keys
  apply to every tick.
- **Camera:** runs per display frame on the interpolated pose (the frame loop's camera update at 0x403e16 already
  takes the drawn pose under `I76_RENDER_INTERP`).
- **Effect on the patch set:**
  - unneeded under this scheme: `I76_COLL_WINDOW`, the AI clocks, skid hold, input latch, and the sim-side parts of
    `I76_FRAMERATE_FIXES` (throttle ramp, fire rolls, flamer and smoke ageing on ticks);
  - still needed, because they are display-rate: the free-look, zoom and orbit cameras and the HUD roll;
  - the frame-dt read inside the substep (C6) becomes harmless: one step per tick;
  - the far-vehicle path 0x43a3c0 steps once per tick with T, as in 1997.
- **Fallback if the loop restructure is too invasive:** keep `I76_FIXED_STEP` with REF_FPS = 1 / T and the patch set,
  and re-run the H5 cells to show render-rate independence.

### 7.3 What must be verified (each a test with a read-back)

1. **Step read-back:** stepper +0x448 = T on every tick; steps per wall second = 1 / T +- 0.5 %; no tick with count
   != 1.
2. **Clock readers see T:**
   - `simclock_GetSimDt` (21 callers), `GetSimRate`, `GetDt` (34 callers, including weapons and FFB) and
     `GetAccumDt` (the VM timers) all return T or its sum;
   - sim time advances T per tick;
   - check by logging each accessor's return at a breakpoint-free hook for 1000 ticks.
3. **Wall-clock users:**
   - `GetTickCount` is called outside simclock only by `sound_CbEnqueue` (radio-line queue), `sound_CdWatchdog`,
     `renderer_TexCacheGetHandle`, `renderer_FadePalette` and `ai_TestControlCandidate` (result discarded). None is
     simulation (DEV-INTENT s.1).
   - Confirm that radio-line timing and palette fades still behave at 120 fps display, i.e. they want wall time.
   - Confirm there are no other time sources: `timeGetTime` is profiler-only, and there are no QPC imports.
4. **Per-frame systems run once per tick:** count calls per second of 0x4349c0, 0x40a320, 0x4a0410 and 0x463800; each
   must equal 1 / T.
5. **Fingerprint against the emulator at the matched step:**
   - Pick the retail emulator config whose median step is nearest T (section 5.1, HARDWARE-MATRIX).
   - Run `fingerprint.py compare` on our exe at T against a reference built from that config.
   - Expected FAILs: only the pacing rows (one step size instead of a spread).
   - Behaviour rows must PASS (gravity, flight, accel, yaw, brake, outcome rates), plus the per-jump outcome against
     local step from 5.1.
6. **Render independence (H5):** at fixed T, render 60 vs 120 fps differs by no more than the A/A.
7. **Interpolation does not leak into the simulation:** the proxy's pose swap restores the physics pose before the
   next tick. Read back position doubles at object+0x40 before and after render: identical.

## 8. Blind taste A/B (after the measured shortlist)

Purpose: break ties among the <= 4 cells left after Stage 3. Remembered feel is not evidence. This is today's taste
on today's build, recorded blind.

### 8.1 Package (self-contained, can be sent to an outside tester)

- **One folder**, `I76-BLIND-<batch>`, holding:
  - a copy of the test install. Never the daily driver or the golden copy;
  - `PLAY.bat`;
  - `ANSWERS.txt`;
  - `README-TESTER.txt`;
  - `key.enc`.
- **Session codes:** `PLAY.bat` asks for a session code (e.g. `K7`, `Q2`), or a number from the schedule.
  - It decrypts `key.enc` (XOR with a per-batch random pad, so no step value is visible as text) to get that code's
    proxy settings, and sets them in the child process environment only.
  - The window title is "Interstate '76 - session K7".
  - **No step value appears in any file name, window title, log or the dgVoodoo / proxy config the tester can open.**
  - Telemetry and the proxy log go to `%TEMP%` with the step written as a code, or are off.
- **Schedule:** generated per tester from a seed and printed into `README-TESTER.txt`.
  - k candidates: every pair twice, once in each order. That is k(k-1) comparisons: 12 for k = 4.
  - Plus 2 A/A pairs: the same cell under two codes.
  - Split into sessions of <= 6 comparisons (about 30-40 min).
  - Codes are reused across a tester's sessions, so repeats can be checked for consistency.
- **Each comparison: two sessions, A then B, each about 5 minutes,** on the same fixed tasks:
  1. the T05 canyon from the crest (2 tries);
  2. the T06 ramps;
  3. 2 minutes of melee against one AI car.

  Start states come from bookmarks, so no driving is needed to reach them.
- **Answer sheet** (`ANSWERS.txt`, one line per comparison): `pair, first code, second code, preferred (A/B), how
  sure (1-3), jumps better (A/B/=), body motion better (A/B/=), combat better (A/B/=), note`.
- **Sealing:**
  - Before the first session, the agent commits the SHA-256 of the decrypted key file (code -> settings) to the repo.
    It reveals the key after the answers are in.
  - The owner never sees the key file before then.
  - The tester returns `ANSWERS.txt` unedited.

### 8.2 Analysis (fixed now)

- **Bradley-Terry** on the preferred column (ties split), with a 95 % bootstrap interval per cell.
- **Consistency:**
  - A/A pairs are the noise check: a tester whose A/A answers carry "how sure = 3" preferences in both A/A pairs is
    flagged. Their data stays in but is reported separately.
  - Reversed-order pairs show order bias.
- **Volunteers** (optional): the same package with a different seed and key per volunteer. Per-volunteer results are
  pooled only if the A/A checks pass.
- **Weak power is accepted:** with 2 presentations per pair, taste only breaks ties (Stage 4), and its uncertainty is
  reported as is.

## 9. Task list

**Legend:**
- **[WF]** the running workflow covers it: consume, do not duplicate.
- **[static]** no console.
- **[emu]** 86Box VMs: I76MEM / I76DRV / I76AIM, `tools\par`.
- **[lab]** our exe, headless where possible: lab `tools\envelope-rebase`, `phys-suite.py`, `autotest\proxy-run.ps1`;
  console runs take the lock.

### Static

| id | task | tool |
|---|---|---|
| S1 | grounded probe clearance (veh+0x470) on flat ground from existing traces, to quantify P6 | `mem.phys.csv` clearance column |
| S2 | trace any handler of `TOGGLE_FRAMERATE` (id 0x54) outside 0x44eb50 | capstone / Ghidra export |
| S3 | route census: FSM paths and AI routes vs class-11 ramps, canyons and drops > 3 m, all missions | `data\out\fsm`, ODEF + TER parsers in i76-map `data` |
| S4 | **done:** SFX in the retail sim runs = 4 (section 0) | `SCRIPT.TXT` filehex |

### Emulator

| id | task | tool | note |
|---|---|---|---|
| E1 | retail step distribution and fps at P133 / P166 x lowest / default / owner's 1997 settings | I76FPS, I76MEM | **[WF hardware-matrix]**; add the owner's settings row if it is missing |
| E2 | retail placed56 jumps with perturbation, one per boot, at P166 low and at the longest-step config from E1, n >= 20 each, with the local-step record | `gen_t05jump.py` + perturbation list | new. The step-response curve of the original exe |
| E3 | retail T05 speed sweep (46-58 m/s, n 4 per speed) at P166 low | `place SPEED` | new. Retail v50 and margin |
| E4 | retail drop and strip ride-frequency phases | new `gen_drop.py` (`place` with y + 0.3 m) | new |
| E5 | AI routes and damage at the E1 configs | `aidmg*`, I76AIM | **[WF ai-damage-runs]** for T13 / melee2; T04 laps and T05 paths new |

### Lab

| id | task | tool | note |
|---|---|---|---|
| L0 | **prerequisite:** the same car and save as the emulator (close the lab-car gap) | GOLD-STANDARD-FINGERPRINT s.5 | blocks every handling row |
| L1 | build the whole-sim tick (7.2) as an opt-in proxy switch, then the read-backs 7.3 #1-4 and #7 | `strlkproxy.c`; telemetry | new |
| L2 | grid campaign: T05 placed56 perturbed (n 30) + speed sweep (n 42) + crest descents, 8 cells + A/A | `envrb-campaign.ps1` pattern, perturbation list | new |
| L3 | H5 render cells and the jitter arm | same | new |
| L4 | body: drop and strip phases per cell | phys-suite + new phase | **[WF modern-fps-sweep]** gives buzz / reversal vs step: consume STEP-LENGTH-CURVE.md |
| L5 | AI: T04 laps, T05 paths, T13 / melee2 per cell | I76AIM on the host | new (per T) |
| L6 | T12 `gotair`, T16 `jump1`, T06 jump1-5 completion per cell | new route scripts | new |
| L7 | blind A/B package (8.1) for the shortlist | new `tools\blind-ab\` | after Stage 3 |

### Analysis

| id | task |
|---|---|
| A1 | add to `fingerprint.py`: landing snap size, ride-frequency fit, coast-down excess, outcome vs local step, the v50 logistic |
| A2 | per-stage scoring script that applies section 6 literally and prints the audit trail |
| A3 | paper skeleton: intent evidence -> bounds -> hypotheses -> results per stage -> decision; every number with n |

## 10. Threats to validity (stated now)

- **The emulator is about 20 % fast** on software rendering (EMU-MEMTRACE 9.5). Retail-at-config results describe
  that emulated machine; the real-box step is longer. The bounds use the emulated value. This is conservative for L.
- **Car and save differences** between the lab and the emulator (L0). Until closed, handling rows compare the wrong
  car.
- **Placement artefacts:** placed jumps start from a teleport. The crest descents are the naturalistic check.
- **Difficulty x2.0 in Gold** (I76-VERSIONS 4.3) does not touch retail-referenced rows. Any Gold comparison sets Champ.
- **Taste** is one or a few people and only breaks ties.
- **The code clues are interpretations of round constants** (15 calls, 0.5 m, 0.06 s). The study tests their
  consequences. It does not assume the authors aimed at them.
