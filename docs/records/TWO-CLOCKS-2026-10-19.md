# The engine's clocks, and physics feel under the tick (2026-10-19)

The owner's report on PLAY-TICK (33.3 ms) against the daily driver (verbatim):
- "car seems a little fast bouncing on 33. did not make the jump on t05 with what i would say is acceptable speed."
- "daily driver went a little too long/high in the t05 jump, but the play-tick seemed to go low and seemed to have too
  much pitch down."
- "seems like we have maybe not respected the intel from the game design and code that there are two ticks in the game,
  one for some stuff and one for another?"
- Later, on PLAY-TICK-42: "tick-42 jumps better (slightly high but could depend on other factors) but i don't want to
  split the difference between two wrong things if we could/should have different ticks for different systems."

Lab only. The daily driver, the golden copy, the Downloads portable, the PC LAN copy and `game-tick` were only read.
`simtick.c` defaults are unchanged. This is measurement and a recommendation; a separate lane makes launchers.

## Short answer

1. **The 1997 engine has one simulation clock, the frame. The car's physics substep is the same tick, except on a
   slow machine.**
   - Every system in the sim block ran once per frame, the car included. Below 50 ms per frame the car took exactly one
     substep per frame, so its step *was* the frame time.
   - The stepper's 50 ms ceiling (`simclock_StepperBegin` 0x49cc20: count = floor(dt x 20) + 1) splits a frame only
     when the frame is longer than 50 ms. That happened at the developers' full-detail preset, about 10 fps, which ran
     2 substeps of about 41.5 ms per frame (HARDWARE-MATRIX r133p2 / r166p3).
   - So the "two ticks" are the frame and the ≤ 50 ms vehicle substep. On the owner's 1997 settings (about 42 ms
     frames) they were one and the same.
2. **The engine has no 20 Hz grid.** The 20 Hz / 50 ms grid in our notes is the proxy's own:
   - `I76_FRAMERATE_FIXES` (`g_tick20`, `g_ref_dt = 0.05`) emulates a stock 20 fps frame for per-frame systems when
     the display runs at 120 fps. Promotion 18 uses it.
   - The tick does not use it. The tick's only 50 ms rule is the flamer ageing clamp (`I76_SIM_TICK_FLAME_AGE=20`).
   - Everything else is either per frame or on a clock (sim time or wall time). Clock-based systems run at the same
     rate in every build.
3. **What the tick changed.**
   - tick33 moved every per-frame system from about 24 to 30 per second, the car's step and its suspension filter
     included (41.7 to 33.3 ms).
   - tick66 runs every per-frame system 15 times a second, with the car at 2 x 33.3 ms. That is the developers' stated
     15 fps design.
   - **tick42 (41.667 ms) puts every per-frame system back at the 1997 rate**, about 24 per second, the car's single
     substep included.
   - Promotion 18 steps the car at 41.7 ms, but runs everything else per display frame (120 / s), on its 20 Hz grid
     where patched.
4. **The bounce is the step. Measured, it is exactly 1.25x faster at 33.3 ms.**
   - The wheel suspension is a second-order filter run once per substep (0x49e0f0 init: period 15 calls, pole 0.7).
     Its timing therefore scales with the step.
   - Heave after a 1 m drop on flat ground, damped half period: **0.233 s at 33.3 ms (tick33, tick66, stock 30 fps)
     against 0.292 s at 41.7 ms** (stock 24 fps, tick42, promotion 18, fixed step 24). That is 7 steps in every arm.
   - Time to settle: 0.33 s against 0.42 / 0.45 s.
   - n 3 boots per arm. Every boot repeats to the printed digit.
5. **The jump.**
   - From the hill-top crest (the owner's own approach), tick33 leaves the lip at **46.9 m/s with an apex of 8.8 m**
     (n 2).
   - The 41.7 ms arms leave at 49.4-51.4 m/s with apexes of 9.8-10.6 m (n 1-6). The retail P166 reference crest
     (31 ms steps, n 10) is 48.4 +- 1.7 m/s and 9.4 +- 0.7 m.
   - So tick33 is low and promotion 18 / tick42 are high against that reference, which is what the owner felt.
   - Placed at 45 and 50 m/s, **no arm clears the canyon** (0-2 of 6), the stock loop at 24 fps included. The jump
     needs a take-off of about 50 m/s, or a 56 m/s approach, in every build.
   - At a placed 56 m/s, the 41.7 ms arms take off at 51.9-52.9 m/s with apexes of 10.6-11.2 m, inside the retail
     41-44.5 ms cells (51.3-52.8 m/s, 10.7-11.8 m). tick33 takes off at 50.6-51.5 m/s with an apex of 10.2-10.6 m.
6. **Recommendation, given the owner's ruling against a compromise tick.** The 1997 design is one clock for the
   simulation at the frame time. So the faithful build is **the tick at the owner's 1997 frame time, 41.667 ms, for the
   whole sim block**, with rendering, interpolation and input sampling at their own rates (they already are).
   - That is tick42, not a compromise between 33 and 66.
   - A two-rate tick (physics at 41.7 ms, the rest at 33.3 ms) would move AI, collisions, weapons and projectiles off
     their 1997 coupling with the car. It would also rebuild promotion 18's structure, and its patch pile with it
     (s.5).

## 1. The clocks, as the code has them

Static reading of the AiO exe 6319abf7 (= Galaxy 9a232dcc at these bytes). Names are from <re-archive> `symbols/functions.tsv`.
Sources:
- the <re-archive> `subsystems/simclock.md`, `framerate.md` and `physics.md`;
- WHOLE-SIM-TICK s.1 (the sim / render cut) and FRAME-BOUND-SYSTEMS (per-system rates);
- this lane's call scan of the exe for the stepper and clock accessors.

| clock | where | what it is | who runs on it |
|---|---|---|---|
| **frame** | `simclock_Update` 0x49c920, called at 0x4039b8 once per frame | dt = GetTickCount delta, clamped to [1, 200] ms offline. sim_dt = dt offline (networked: the synchronised delta, capped at 1 s). simclock_time 0x5a7e74 and sim_time 0x5a7e70 advance by dt | the whole sim block, once per frame: input 0x44d9e0 / 0x44dec0, collision pass 0x4349c0, every entity tick 0x461c80 (vehicles, aircraft, gates), post-ticks 0x461d50, AI + script VM 0x40a320 (`fsm_RunMachines` 0x4149f0: one state step per machine per frame), turrets 0x462a90, projectiles 0x4a0410, weapons 0x4a4130, texture animations 0x44af80; then the camera, sound listener and render |
| **vehicle substep** | stepper at entity+0x444: `simclock_StepperInit(0.05)` at 0x46312b / 0x46313a, `simclock_StepperBegin` 0x49cc20 called at 0x463888 (near path of `entity_TickVehicle` 0x463800) | count = min(floor(sim_dt x 20) + 1, 20), step = sim_dt / count. **A ceiling (no step over 50 ms), not a grid**: one substep per frame below 50 ms | per substep: `entity_UpdateState` 0x465370, `physics_StepVehicle` 0x438fd0 (contact, integration, wheel suspension filter 0x46dc10 -> 0x49e1b0, ground contact 0x437230, engine 0x46a320, which reads the whole frame's dt at 0x46a333). Far vehicles skip the stepper: one kinematic step per frame (0x43a3c0), and the stepper is re-armed at 0x463862. The network replay steps with a given dt (0x45534f `StepperBeginDt`) |
| **script clock** | `simclock_GetAccumDt` 0x49c7e0 (callers 0x413691, 0x4136da, 0x413706, 0x413738, 0x41390e, 0x41395f, 0x4149f6) | sim time, less the first 3 frames | FSM timers (startTimer, timeGreater / timeLesser, the success / fail delays) |
| **clock timers** | sim time (`simclock_GetSimTime` 0x49c7c0, 48 callers), wall time, and dt-integrated timers | rate-free by construction | weapon cooldowns with carry (0x4a6470, its < 10 ms remainder drop aside), AI behaviour timers (AI 0x41b6e0..0x420fc0: time-ups, the 5 s line-of-sight loss, just-do-it 1.5 s), the radar's 1 Hz catch-up (0x460c80 / 0x45faf0), wreck 10 s, regen 30 s, sprite and texture-animation lives, projectile life and flight, music (MCI, wall clock) |
| **display-frame count** | `simclock_GetFrameCount` 0x49c7d0 (callers 0x42ecba, 0x42f698, 0x42f6b7, 0x4457b4, 0x45ae7d, 0x45ae8c) | frames | render only: the texture cache LRU, the rear mirror (every 2nd frame), the cockpit |
| (no 20 Hz grid) | the search found no frame-time constant other than the stepper's 0.05 (DEV-INTENT-EVIDENCE C-table scan) | the 20 Hz grid is the proxy's `I76_FRAMERATE_FIXES` (strlkproxy.c `g_tick20`, `g_ref_dt = 0.05`, `I76_REF_FPS`), modelling a stock 20 fps frame | promotion 18's held per-frame systems (below) |

Developer testimony (DEV-GAME-CLUB-I76): "designed to run at 15 frames per second"; "the physics was not independent of the
time step. Everything ran in the same loop"; the suspension is "a second order digital filter" whose coefficients are
"calculated to resonate at 15 hertz" (read as a 15 Hz call rate, period 15 calls). Under the shipped stepper a 15 fps
frame runs the car as 2 x 33.3 ms, which tick66 reproduces. The two-tick intel is that pair: the frame for everything,
and the ≤ 50 ms substep for the car. It is not a separate fixed clock for physics.

### 1.1 Per system: the 1997 rate and each build's rate (per second; "per frame" systems)

1997 = retail 1.0 as the owner played it, about 42 ms frames (24 / s; one car substep per frame). The gold-standard
P166 lowest-detail cell ran 31 ms frames (32 / s); the developers' full detail about 10 fps with 2 substeps.

| system | 1997 clock | 1997 (42 ms) | tick33 | tick42 | tick66 | promotion 18 (`I76_FIXED_STEP=24`) |
|---|---|---|---|---|---|---|
| car physics substep (step length) | frame (≤ 50 ms) | 24 (42 ms) | 30 (33.3) | **24 (41.7)** | 30 (2 x 33.3 per tick) | 24 (41.7, 0-n per display frame) |
| wheel suspension filter calls | substep | 24 | 30 (x1.25) | **24** | 30 | 24 |
| engine RPM / torque smoothing (whole-frame dt per substep) | substep x frame dt | 1 x 42 ms | 1 x 33.3 | **1 x 41.7** | 2 x 66.7 (2x per tick) | 0.05 per 41.7 ms step (`I76_ENGINE_DT_FIX` ref 20 fps: 1.2x) |
| collision pass 0x4349c0 | frame | 24 | 30 | **24** | 15 | 120, window widened to the step + dedupe |
| controls (key edges, throttle notch ramp) | frame | 24 | 30 + early tick on input | **24** + early tick | 15 + early tick | 120, notch ramp scaled to 20 / s |
| AI frame tick, FSM VM, AI rolls (fire, sight ray, route search, skid, horn) | frame | 24 | 30 | **24** | 15 | 120; fire / dodge on the 20 Hz grid, skid / horn 120 (`I76_AI_ROLL_HOLD=0`) |
| turrets, projectile steps (radar-missile turn, hazards), weapon update | frame | 24 | 30, factors to 24 / s (hazard, scrape, wreck, radar) | **24 (factors 1.0)** | 15, factors to 24 / s | 120; hazard / radar on the 20 Hz grid |
| far vehicles (kinematic step) | frame | 24 | 30 | **24** | 15 | 120 |
| draw-code sim: flamer update / damage, smoke, trails, radar ping | render pass (+ mirror) | 24 | 30 (flamer aged 15 / s, damage x2.8) | **24** (flamer aged 12 / s; the x2.8 flame factor is not calibrated for 41.7) | 15 | 20 (grid) |
| weapons cadence, AI timers, script waits, radar sweep, sprites, music | clock | - | same | same | same | same |
| camera, sound listener, drawing | frame (display) | 24 | 120, interpolated | 120, interpolated | 120, interpolated | 120, car interpolated |

**Moved off their 1997 clock:**
- **tick33** moves every per-frame row x1.25, the car's step and the suspension filter included. The tick factors bring
  four damage / turn rows back to 24 / s.
- **tick66** moves them x0.63 and runs the car as 2 x 33.3 ms (the 15 fps design, not the owner's 1997).
- **Promotion 18** keeps the car at 24 / s but runs everything else at the display rate, with the 20 Hz grid where
  patched.
- **tick42** moves nothing. The drawing, the camera and the early tick on input run faster than 1997, which no sim
  rate depends on.

## 2. Harness (lab)

- **Copy:** `game-tc`, a new copy of `game-samecar`.
  - It holds the emulator save's car (ADDON `vppirna1.vcf` 1d636559, read back in every boot: armour + chassis 9600,
    mass 1846, engine 104 440).
  - i76.exe 6319abf7, null renderers.
- **Proxy twin:** `builds\two-clocks-20261019\Strlkup-tc-lab.dll` cdcb9914.
  - Source: tick-factors' `src-tf1-lab` (the tick19e source a08577c4, i76-everywhere 6efb646, plus the lab drive block).
  - **Only change:** the four shared-memory names suffixed `TC`.
- **Why the rename (safety):**
  - The trainer block `Local\I76Trainer` is always on in every proxy, the owner's included.
  - A lab game under the stock name shares it with any running copy of the game. A harness TELEPORT would then be read
    by the owner's car too.
  - The owner's daily driver was running when this lane started (16:00), so every boot here used the TC names.
  - **Any lane that runs a harness while the owner plays needs the same.**
- **Desktop:** each boot runs on its own private desktop, `I76Lab-tc`.
  - On the shared `I76Lab-wst` desktop, another lane's lab game made ours exit at start (7 boots lost; they were
    re-run).
- **Muting:** `I76_MUTE=1` plus the per-pid mute watcher. Nothing was muted host-wide, and no process was stopped
  that this lane did not start.
- **Tools:** lab `tools\two-clocks\`.
  - `tc-run.ps1`, `tc-queue.ps1`: one boot, and the queue runner.
  - `tc_drive.py`, `tc_suite.py`, `tc_probe.py`: copies of wst_drive / phys-suite / wst_probe with the TC names.
    `tc_suite.py` also has the `bounce` phase.
  - `tc_analyse.py` (tables).
  - Preset snapshots in `presets\`, by md5:
    - tick19-33 1f01e781
    - tick19-42 19e0755f
    - tick19-66 64d3b6f5
    - p18-best-wide-balanced 0bca8b31 (the driver's verbatim)
    - lab-step-33 4b264661
- **Data:**
  - captures: lab `captures\two-clocks-20261019` (gitignored), 66 boots;
  - tables: lab `emu\results\two-clocks-20261019\tc-tables.md` and `tc-data.json`.
- **Arms:**
  - **e24**: the stock frame loop at 24 fps on a 1 ms tick. It runs 41 / 42 ms frames: the 1997 coupling.
  - **e30**: the same at 30 fps, the same-step control for tick33.
  - **tick33 / tick42 / tick66**: the candidate presets.
  - **p18**: promotion 18 verbatim.
  - **fs24**: lab-step-33 minus every timing patch, plus `I76_FIXED_STEP=24` alone. This is the bisect of p18.
- **Spreads and n:**
  - Spreads are the sd over jumps or drops.
  - The arms repeat nearly to the digit within a boot condition, so n counts boots for the record. The physical
    spread is the retail one.

## 3. Suspension bounce (measured, n 3 boots per arm)

**Protocol.**
- The car is placed at rest on the flat accel start (7935, 42900; ground y 17.5) and settled.
- It is then dropped from 1 m and from 3 m above its rest height, level.
- It is then dropped from 1 m pitched nose-down 8 degrees, and from 1 m rolled 8 degrees.
- Only distinct physics states are used. Times are measured from the first state inside the 0.5 m landing band.

| arm | car step ms | 1 m drop: trough / peak after impact, s | **heave half period, s** | settle (body still), s | 8 deg roll drop: tilt gone (rest snap), s | roll drop: rate reversals |
|---|---|---|---|---|---|---|
| e24 (1997 coupling) | 42.0 | 0.250 / 0.542 | **0.292** | 0.42 | 0.29 | 2 |
| tick42 | 41.7 | 0.250 / 0.542 | **0.292** | 0.42 | 0.29 | 2 |
| p18 | 41.7 | 0.250 / 0.542 | **0.292** | 0.45 | 0.29 | 4 |
| fs24 | 41.7 | 0.250 / 0.542 | **0.292** | 0.45 | 0.29 | 3.3 |
| e30 (stock 30 fps) | 33.0 | 0.200 / 0.433 | **0.233** | 0.33 | 0.27 | 1 |
| tick33 | 33.3 | 0.200 / 0.433 | **0.233** | 0.33 | 0.28 | 1.3 |
| tick66 | 2 x 33.3 | 0.200 / 0.467 (sampled per 66.7 ms tick) | 0.267 (sampling) | 0.33 | 0.33 | 2 |

**Readings.**
- **The heave half period is 7 steps in every arm, so the bounce runs at the step's rate.**
  - The damped period is 0.58 s at 41.7 ms and 0.47 s at 33.3 ms: 1.25x faster at tick33.
  - The model predicts this: a filter with period 15 calls has a damped period of 15 steps, about 0.625 / 0.50 s.
- **Same step, same bounce:** tick33 = e30 and tick42 = e24 to the printed digit. The tick changes nothing here beyond
  the step length.
- **Amplitude does not change with the step.** The undershoot is 6.3 mm at 1 m and 5.6 mm at 3 m in every arm. The
  difference the owner feels is the tempo, not the depth.
- The 3 m drop and the pitched drop show the same timing. On the roll drop the tilt is gone at the same time (0.27-0.33
  s) in every arm, but the 41.7 ms arms rock once more (2 reversals against 1).
- **For reference, by the same filter maths:**
  - the gold-standard P166 at 31 ms runs a 0.47 s damped period;
  - the owner's 1997 settings at about 42-48 ms run 0.63-0.72 s;
  - the developers' 15 calls / s design runs 1.0 s.
- **The 40 m drop is not used.**
  - The lab teleport to 40 m up was snapped back to the ground in most arms (impact speed 2-3 m/s, not 28).
  - The retail strip drops land on a slope and slide (6 + 5 traces).
  - The table carries them for completeness only.

**Compensation at 33.3 ms (if 33.3 is kept), sound for the ride only.**
- Initialise the wheel filter with the pole mapped to the 41.7 ms response:
  - period 15 x 41.667 / 33.333 = 18.75 calls;
  - r = 0.7^(33.333 / 41.667) = 0.752.
  - These are the two immediates pushed to 0x49e0f0 by the wheel constructor 0x46d760.
- Scale the bump feed-forward gain 5.0 (0x4be4c4) by the same ratio, because it acts per call.
- This matched-pole mapping keeps the filter's time response, and it would put the heave back at 0.29 s.
- **It does not touch the other per-step parts of the car model**, so it fixes the bounce and not the jump (s.4):
  - the speed lost on the ramp face per step (`physics_IntegrateVehicleMotion` projection);
  - the overshoot snap of the attitude;
  - the lip's one-substep nose-down kick (2 x step x 2 pi: -0.42 rad/s at 33.3 ms, -0.52 at 41.7 ms, read off every
    take-off below).

## 4. The T05 jump (measured)

### 4.1 Placed jumps, 150 m before the aaramp4 foot, throttle held (n 3 boots x 2 jumps per speed; 56j = 56 +- 0.5 m/s and +- 0.5 m lateral, 2 boots x 6)

"Made it" = landed past the far ramp's lip (x < 6745). "Lip clip" = the car goes airborne on the ramp face and drops
inside the ramp (take-off vy < 5 m/s); a clip ends the boot (the car is killed). The take-off, apex and pitch columns
cover the jumps that took off.

| arm | placed | made it | lip clip | take-off m/s | apex m | distance m | take-off q rad/s | landing pitch deg |
|---|---|---|---|---|---|---|---|---|
| e24 | 45 / 50 | 0/6 / 1/6 | 0 / 0 | 43.1 / 47.2 | 7.4 / 8.9 | 113 / 110 | -0.44 / -0.49 | +6.4 / +23 |
| tick42 | 45 / 50 | 0/4 / 0/3 | 0 / 0 | 43.4 / 44.9 | 7.5 / 8.1 | 113 / 106 | -0.52 / 0.00 | +6.3 / -5.5 |
| p18 | 45 / 50 | 0/5 / 0/5 | 0 / 0 | 43.5 / 47.0 | 7.6 / 7.9 | 112 / 111 | -0.21 / +0.05 | +4.0 / +26 |
| fs24 | 45 / 50 | 2/6 / 5/6 | 0 / 0 | 43.3 / 46.8 | 7.5 / 8.8 | 120 / 129 | -0.26 / -0.44 | +3.0 / -44 |
| e30 | 45 / 50 | 0/6 / 0/6 | 0 / 0 | 43.0 / 44.6 | 7.4 / 8.0 | 113 / 107 | -0.38 / -0.32 | -8.6 / +20 |
| tick33 | 45 / 50 | 0/6 / 0/6 | 0 / 0 | 42.8 / 45.7 | 7.3 / 8.3 | 112 / 107 | -0.42 / -0.42 | **-12.6** / +22 |
| tick66 | 45 / 50 | 0/6 / 0/6 | 0 / 0 | 43.7 / 46.2 | 7.6 / 8.5 | 109 / 104 | -0.42 / -0.42 | -5.3 / +27 |
| e24 | 56 | 6/6 | 0/6 | 52.16 | 10.88 | 175 | 0.00 | -8.0 |
| e24 | 56j | 9/10 | 1/10 | 52.88 +- 0.73 | 11.19 +- 0.31 | 223 +- 36 | -0.32 | +2.3 |
| tick42 | 56 | 0/3 | **3/3** | - | - | - | - | - |
| tick42 | 56j | 7/10 | 2/10 | 51.88 +- 1.61 | 10.63 +- 0.79 | 195 +- 68 | -0.39 | -2.8 |
| p18 | 56 | 3/4 | 1/4 | 50.33 +- 1.58 | 10.14 +- 0.64 | 165 +- 9 | 0.00 | -7.4 |
| p18 | 56j | 10/12 | 2/12 | 52.54 +- 0.79 | 11.05 +- 0.34 | 229 +- 29 | -0.39 | +9.7 |
| fs24 | 56 / 56j | 6/6, 12/12 | 0, 0 | 51.83 / 52.01 | 10.75 / 10.83 | 186 / 215 | -0.09 / -0.31 | +0.4 / +2.7 |
| e30 | 56 | 3/6 | 3/6 | 49.48 +- 1.89 | 9.80 +- 0.74 | 200 +- 59 | -0.35 | -2.9 |
| tick33 | 56 | 6/6 | 0/6 | 50.57 | 10.23 | 235 | -0.42 | +1.5 |
| tick33 | 56j | 12/12 | 0/12 | 51.47 +- 1.06 | 10.60 +- 0.44 | 227 +- 29 | -0.35 | -3.7 |
| tick66 | 56 | 6/6 | 0/6 | 50.57 | 10.23 | 235 | -0.42 | +1.5 |

### 4.2 The owner's approach: full throttle from the T05 hill-top crest, steered down the road over the ramp (phys-suite `descent`; 2 boots x 3 runs, but a run that kills the car ends the boot)

| arm | runs | take-off m/s | vy m/s | apex m | distance m | made it | landing pitch deg |
|---|---|---|---|---|---|---|---|
| e24 | 1 | 49.4 | 13.8 | 9.77 | 197 | 1/1 | +17.6 |
| tick42 | 1 | 51.4 | 14.4 | 10.58 | 211 | 1/1 | +18.4 |
| p18 (the driver) | 6 | 51.1 +- 1.0 | 14.3 +- 0.3 | 10.46 +- 0.41 | 210 +- 7 | 6/6 | +19.1 |
| fs24 | 6 | 50.1 +- 0.7 | 14.0 +- 0.2 | 10.04 +- 0.28 | 202 +- 22 | 6/6 | +11.1 |
| tick33 | 2 | **46.9** | 13.1 | **8.80** | 132 | 2/2 | -3.0 |
| retail P166 reference, crest descents (31 ms steps) | 10 | 48.4 +- 1.7 | 13.6 +- 0.5 | 9.39 +- 0.65 | 154 +- 45 | 8/10 | -19.8 +- 19.2 |

### 4.3 Retail 1.0 / Gold on the emulator, placed 56 m/s (memtrace, by cell; the lip step is the cell's median)

| cell | lip step ms | n | take-off m/s | apex m | distance m | made it | take-off q rad/s | destroyed |
|---|---|---|---|---|---|---|---|---|
| ref-r166low (gold standard) | 31.0 | 7 | 51.62 +- 1.00 | 10.66 +- 0.41 | 228 +- 28 | 7/7 | -0.32 | 0/7 |
| r166low | 33.0 | 8 | 51.06 +- 1.21 | 10.55 +- 0.77 | 225 +- 17 | 8/8 | -0.40 | 3/8 |
| r133low | 35.5 | 10 | 52.08 +- 1.05 | 10.88 +- 0.44 | 208 +- 39 | 10/10 | -0.55 | 6/10 |
| r166p3 (developer default, 2-3 substeps) | 37.7 | 5 | 52.68 +- 0.95 | 11.98 +- 0.92 | 205 +- 38 | 5/5 | -0.30 | 2/5 |
| r166lmirtex | 39.0 | 3 | 52.42 +- 1.02 | 11.18 +- 0.76 | 195 +- 35 | 3/3 | -0.47 | 1/3 |
| g133low (Gold) | 41.0 | 5 | 51.55 +- 1.42 | 10.70 +- 0.71 | 199 +- 41 | 5/5 | -0.12 | 1/5 |
| r166m6 | 43.8 | 3 | 51.26 +- 1.18 | 10.87 +- 0.35 | 213 +- 46 | 3/3 | -0.18 | 2/3 |
| r133p2 (developer default, 2 substeps) | 44.5 | 5 | 52.82 +- 0.94 | 11.84 +- 0.83 | 244 +- 47 | 5/5 | -0.22 | 2/5 |

All cells are in lab `tc-tables.md`, with g166glide, ref-g166low, r166lmir and g166lmirtex. **No retail placed jump
clipped the lip** (0 of 60 placed jumps across all cells, 0 of 10 crest runs).

### 4.4 Readings

- **Clearing the canyon needs about 50 m/s at the lip in every build.**
  - Placed at 45 or 50 m/s, the car leaves at 43-47 m/s and lands in the channel or on the far lip edge. That holds for
    every arm, the stock 24 fps loop included (e24 1 of 12).
  - fs24's 7 of 12 is the margin: landings at 120-130 m, right at the far lip. Retail was never measured at these
    speeds.
  - "Did not make the jump at an acceptable speed" on tick33 is real, but at a placed 45-50 m/s it is real everywhere.
  - What differs between builds is the speed the car *reaches*. From the crest, tick33 arrives about 2.5-4.5 m/s slower
    than the 41.7 ms arms and 1.5 m/s under the retail reference.
- **tick33 loses more speed per metre of ramp.** At the same placed 56 m/s it leaves at 50.6 against 52.2 (e24 /
  tick42 jitter 51.9-52.9).
  - This is the per-step projection loss on the face (physics.md "It is a per-step loss"): more steps per second, more
    loss.
  - Its apex, 10.2-10.6 m, is below every retail cell (10.5-12.0). The 41.7 ms arms (10.6-11.2 m) sit inside the
    retail cells of 41-44.5 ms (10.7-11.8).
  - So "the play-tick went low" is the step. "The daily driver / tick42 a little high" is high against the 31 ms gold
    standard, but on the retail rows at their own step length.
- **Pitch.**
  - The take-off pitch rate is the lip's one-substep nose-down kick. tick33 / tick66 read -0.42 rad/s on every take-off.
    The 41.7 ms arms read -0.52 when the kick lands on a substep and 0 when it does not (retail: -0.12 to -0.55).
  - So tick33 does not pitch down harder at the lip.
  - The "too much pitch down" fits the lower, slower flight instead. At a placed 45 m/s tick33 lands nose-down
    (-12.6 deg) where e24 / tick42 land nose-up (+6.3 / +6.4). At 56 m/s all arms land within -8 to +10 deg.
  - The peak |pitch rate| of 1.57 in the tick33 rows is the landing contact clamp (pi/2), not the flight. That is also
    why s.4.4 of TICK-FINISH read "pitch rate 1.57 vs 0.62" for promotion 18: a landing number, not a take-off one.
- **Promotion 18's short 56 m/s jump (TICK-FINISH s.4.4, 178 m) is placement phase.** On the jittered set p18 reads
  229 +- 29 m with the take-off and apex of e24, and fs24 matches it. Its centre-line placement just sits on an unlucky
  phase. That answers s.4.4's "not traced" as far as these data go: on the jittered set neither the patch set (p18) nor
  the fixed step alone (fs24) shortens the jump (n 12 each).
- **tick42 against e24 (equal by construction?).**
  - **The suspension is equal to the digit.**
  - On the jumps they differ on the deterministic centre-line placement: tick42 clips the lip 3 of 3, and e24 0 of 6.
  - On the jittered set the difference is inside the spread: take-off 51.9 +- 1.6 against 52.9 +- 0.7; clips 2/10
    against 1/10.
  - The cause is the step phase, not the step. e24's frames alternate 41 / 42 ms (1 ms clock), where tick42 is exactly
    41.667. At a fixed placement that shifts which substep meets the ramp face. The lip clip (the car airborne on the
    face, then below it out of the ±3 m ground band; physics.md V12) is a knife edge on that phase.
  - The other differences are the tick's early tick on input (it shifts the phase again when a key changes) and the
    display interpolation. Neither enters the physics state.
- **Lip clips are a lab-only outcome so far:** 0 of 60 retail placed jumps, 0 of 10 retail crest runs.
  - The 41.7 ms lab arms clip 5 of 58 jittered or crest jumps (e24 1/10 + 0/1, tick42 2/10 + 0/1, p18 2/12 + 0/6,
    fs24 0/12 + 0/6).
  - tick33 clips 0 of 12 jittered jumps and 0 of 2 crest runs.
  - Fisher, retail 0/70 (placed + crest) against the lab's 41.7 ms arms 5/58: p 0.018. The centre-line rows are left
    out; with them the lab count only grows.
  - This is the one place a 41.7 ms build can be worse than 1997, and it needs its own trace (the lab placement teleports
    a car with a stored ground height, where retail drives to the spot).

## 5. Two clocks, one tick, or a two-rate tick (the owner's design question)

**What 1997 actually had, per system:**
- physics: per frame (one substep below 50 ms);
- everything else in the sim block: per frame;
- timers: on a clock;
- drawing: per frame.

So the faithful build is not "physics at 41.7, the rest at 33.3". It is everything at the frame time the owner played,
41.7 ms, with drawing and input free. That is tick42.

**A true two-rate tick in `simtick.c`, if wanted anyway (physics at 41.667 ms, the rest at 33.3 ms or per display
frame):**
1. **Split the gate.** `entity_TickAll` 0x461c80 (the car stepper; it also ticks aircraft, gates and spinners) and
   `physics_CollideAll` 0x4349c0 would go on their own accumulator. Input, AI / FSM, turrets, projectiles and weapons
   stay on the 33.3 ms tick.
   - That needs a second accumulator and clock set: sim_dt = 41.667 ms around the vehicle gate, 33.3 ms around the
     others.
   - Or keep one tick and let the vehicle stepper accumulate, which is promotion 18's `fixed_stepper_begin`, with 0 or
     1 car step per 33.3 ms tick.
2. **Collision.** The pass sweeps [0, sim_dt] per pass. With the car stepping only on some passes, the pass either
   misses the step's path or repeats a contact. That brings back promotion 18's `I76_COLL_WINDOW` / `I76_COLL_DEDUPE`
   (and its "hit before you reach it" history).
3. **Input pulses.** One-frame discrete requests (ignition, lights) are cleared per substep. A 33.3 ms tick with no car
   step loses them, so `I76_INPUT_LATCH` comes back.
4. **Order within a frame.** In 1997 the order was: physics, then AI / scripts / weapons on that new pose, every frame.
   - With two cadences, AI and weapons act 0-41 ms after the last car step, on a stale pose, and their effects (contact
     records, damage) reach the car on its next step.
   - Projectiles fired from a car pose that has not moved for one or two AI ticks start from the stale pose.
5. **Interpolation with two cadences.** `simtick.c` records one start / end pose pair per tick for every object.
   - Cars would need their own pair and alpha on the 41.7 ms grid; projectiles and AI-moved objects on the 33.3 ms grid.
   - The camera follows the car, so cockpit judder appears wherever the two alphas disagree.
   - The early tick on input would also have to decide which clock to pull forward.
6. **The per-frame systems would still be at x1.25.** They would need the tick factors (as now), not the 1997 coupling.

That is promotion 18's structure again, with its patch pile. A two-rate tick buys nothing over tick42 for fidelity,
because nothing in 1997 ran the car on a different clock from the rest at the owner's frame times.

**What does legitimately run on its own rate (already true under every tick):**
- drawing and interpolation (the display rate);
- the camera, the sound listener and the cosmetics (display dt);
- input sampling with the early tick on a key / pad change (it borrows the next tick; the tick length is unchanged);
- every clock-based system (s.1). They are rate-free in any build.

The 20 Hz grid is not an engine clock, and nothing needs to stay on it under a tick.

**tick42 caveats** (for the launcher lane, not measured here):
- The flame damage factor `I76_SIM_TICK_FLAME_DMG` 2.8 was calibrated at 33.3 / 66.7 ms. At 41.667 ms the flamer runs
  24 updates / s and is aged 12 / s, so the factor needs one flame run (TICK-FINISH s.12 protocol).
- The tick factors are 1.0 by construction at 41.667 ms (24 x T).
- Input latency is bounded by T: up to 41.7 ms, about 21 ms typical, before the early tick shortens it for keys and
  pads.

## 6. Recommendation

- **Make the 41.667 ms tick the physics-faithful build.** It is the whole sim at the owner's 1997 frame time:
  - the bounce equals the stock 24 fps loop to the digit;
  - the jump take-off and apex sit on the retail 41-44 ms cells;
  - no per-frame system is moved off its 1997 rate, so the tick factors fall to 1.0.
- **Do not build a two-rate tick.** Nothing in 1997 ran the car on a different clock from the rest at those frame
  times, and splitting them brings back promotion 18's collision, input and ordering patches.
- **If 33.3 ms stays as a launcher**, the matched-pole suspension mapping (s.3) is the only sound compensation, and it
  fixes the bounce, not the slower ramp and lower jump.
- **Before tick42 is promoted:**
  - the lip-clip rate at 41.7 ms needs a trace (s.4.4);
  - the flame factor needs one run at 41.667 ms.

## 7. Not done, and why

- **The emulator was not run.** No headless one-command recipe exists; `run-vm.ps1` and `PLAY-P166-LOGGED.bat` are
  owner-facing. The retail rows are the existing memtrace runs.
  - There is no retail crest descent at a 42 ms step, and no retail placed jump at 45 / 50 m/s.
  - The retail strip's drop (40 m on a slope) is not comparable with the flat drops.
- **Crest descents: n 1-2 for e24, tick42 and tick33.**
  - A run that ends with the car destroyed (the fall kill: god does not cover it) ends the boot.
  - p18 and fs24 got 6 each.
- **The lip clip is not traced.** It is a lab placement / step-phase effect until a driven approach (descent) shows it.
- **The owner's own settings** (640x480, mirror on: about 46-48 ms frames on the P166 cells) were not run as a lab
  arm. By the filter maths they bounce slower still (0.69-0.72 s damped period).
