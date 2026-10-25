# Developer intent for the physics step: what the code, the content and the record say (2026-10-17)

Question: what physics step did Activision's 1996-97 team build and tune Interstate '76 for? The answer feeds the
step-length study ([PHYSICS-STEP-STUDY-DESIGN.md](PHYSICS-STEP-STUDY-DESIGN.md)).

Owner priorities (2026-10-17):
1. The code is the primary method.
2. Content is the fallback.
3. With no clue, start at the middle of the bounds.

This page follows that order.

**Labels used throughout:**
- **[fact]**: read from the exe, the data or a primary document. Address or URL given.
- **[lore]**: secondary or community claim.
- **[inference]**: ours, with the reasoning shown.

**Confidence:** each clue gets high / medium / low.

**Method.**
- Static only. No game, VM or console use.
- Exes, read-only:
  - Gold / GOG `i76.exe`, md5 `9a232dcc` (`<re-archive>\sandbox-gog\main\app`);
  - retail 1.0 `I76.EXE`, md5 `6cc509ad` (`<re-archive>\sandbox-cd1997`).
- Tools: capstone, plus scratch scripts that are not kept: a disassembler, a float-constant scanner, and an xref and
  import-call finder. They are easy to rebuild from this description.
- Prior static work reused, with section names: <re-archive> `subsystems\simclock.md`, `framerate.md`, `physics.md`,
  `ai.md` and `mission.md`; the decompiled scripts in `data\out\fsm\*.fsm`.
- Addresses are the Gold exe's unless marked. Physics code is the same algorithm in retail and Gold (EXE-DIFF-MAP,
  RETAIL-HANDLING-DIFF, I76-VERSIONS s.3). `simclock_StepperBegin` / `StepperInit` are byte-identical from 1.0
  through 1.083.

## Short answer

- **The code gives a band, not a point.**
  - The engine's own ceiling is a **50 ms** substep. Every vehicle stepper is created with
    `simclock_StepperInit(stepper, 0.05)` [fact, high].
  - With the split rule floor(dt x 20) + 1, any frame of 50 ms or more runs substeps of **25 to <50 ms**.
  - The step-shaped parts of the contact model are calm from about 25 ms up. They buzz below it (measured,
    capture 014).
  - So the designed operating band is **25-50 ms** [inference, medium].
- **Three code clues point inside the band. They disagree with each other.**
  1. **About 30 ms.** `simclock_Init` presets the frame time to **0.06 s (16.7 fps)**. Under the split rule a 60 ms
     frame runs 2 steps of 30 ms [fact for the constant; inference for intent, low].
  2. **About 44-67 ms (44-50 inside the band).** The wheel ride-height filter is specified in **calls**: pole radius
     0.7, period 15 calls. Its ride frequency is 0.0876 / step Hz. That is car-like (at most 2 Hz) only for steps of
     44 ms or more. Its damped period of 15 steps is 0.75 s at 50 ms and 1.0 s at 66.7 ms (15 fps) [fact for the
     filter; inference for intent, low-medium].
  3. **About 26-35 ms for the T05 landing.** The landing-capture band is 0.5 m. A landing never needs an upward
     correction only if |vy| x step <= 0.5 m. At T05's landing speeds (14.5-19 m/s) that means a step of about
     26-35 ms [fact for the rule; inference for intent, low-medium].
- **Content.**
  - The designers scripted jump cameras that fire on the player being airborne at fixed places in 8 missions:
    T05, T06 (5 jumps), T10, T12, T16, S03, S05, S06. Two missions end on a jump (T12 `gotair`, T16 `jump1`) [fact].
  - So jumps are designed content and must work.
  - **No script tests an AI car for being airborne.** AI jumps are not scripted content [fact, high].
  - T05's camera holds **4 s** over the canyon. The measured retail flights are 2.9-5.9 s.
- **The written record names no frame rate or physics step** (WHAT-IS-STOCK s.Development hardware, 33 sources, plus
  this session's search, section 5).
  - The only target statement is the producer's: "an acceptable frame rate for the minimum platform", a Pentium 90.
  - The box minimum on the measured emulator gives 7-17 fps, i.e. 47-60 ms frames and 2-3 substeps (section 3.3).
- **New this session:**
  1. The in-game credits name the **Vehicle Dynamics Programmer: Dan Stanfill**, who was also the lead programmer.
  2. The **Gold manual's first-launch defaults by CPU** put a P166 at 640x480 with all features on, not at lowest
     detail. On the emulator that class of setting runs about 13 fps (Gold exe), so the **developers' own P166 default
     ran 2 substeps of about 37 ms**, not one of about 30 [fact for the table; inference for the step].
  3. Dev Game Club episodes 422 / 424 / 427 (2025) list "physics implementation details from an implementer!" and
     "deterministic physics" as topics. They are audio only and were not listened to. This is the best open lead for
     a first-hand step statement.
     **Update (W1 done): [DEV-GAME-CLUB-I76.md](DEV-GAME-CLUB-I76.md).** Julio Jerez (via a listener's email, ep 424):
     the suspension is his second-order digital filter (= P1), the game was "designed to run at 15 frames per
     second", the filter is "OK in between 10 and maybe 30 hertz", the step was "not regulated". Testimony, medium.
- **Reading for the study.**
  - Bounds: 25-27 ms to <50 ms.
  - The clues bracket the middle (30 vs 44-50), so the grid must cover the whole band. 40 ms is the neutral start
    (owner rule 3).
  - The first experiment to run is the one that separates clue 2 from clue 3, the landing-survival vs body-frequency
    trade-off (study design, section 5).

## 1. Code: the clock and the stepper (Gold 0x49c7f0..0x49ccb9; retail 0x450e50.., 0x451250..)

| # | clue | address | value / rule | what it says about the step | conf. |
|---|---|---|---|---|---|
| C1 | max substep | `simclock_StepperInit` 0x49cbe0, called with `push 0x3d4ccccd` (0.05) at 0x46313a (`entity_InitVehicle`), 0x463862 (`entity_TickVehicle`), 0x455321 (net) | rate = 1 / 0.05 = 20 stored at stepper+0 | every vehicle substep is < 50 ms. The authors set the accuracy / stability ceiling at 50 ms. No other ceiling exists | **high** [fact] |
| C2 | split rule | `simclock_StepperBegin` 0x49cc20: `fld sim_dt; fmul rate; call ftol; inc; cap 20`; step = sim_dt x (1/n table 0x5a7e20) | count = min(floor(20 x sim_dt) + 1, 20), step = sim_dt / count | a frame of 50-100 ms runs 2 steps of 25-50 ms; 100-150 ms runs 3 of 33-50 ms. **On any machine slower than 20 fps the substep stays in [25, 50) ms.** It uses floor + 1, not ceil, so a step is never 50 ms | **high** [fact] |
| C3 | default frame | `simclock_Init` 0x49c7f0 stores 0.06 (0x4be99c) in sim_dt 0x4fe420 and dt 0x4fe428, and 16.6667 (0x4be9a0) in both rates. Retail the same (0x450e93 `mov eax, 0x3d75c28f`) | 60 ms, 16.7 fps | the programmer's placeholder for "one frame" is 60 ms. Under C2 that is 2 x 30 ms steps. Frame 1 overwrites it (the 0.2 s clamp, simclock.md M50d), so it changes no behaviour; it only shows what was in the author's head | **low** [inference] |
| C4 | dt clamps | `simclock_Update` 0x49c920 (simclock.md) | frame dt clamped to [0.001, 0.2] s offline; sim_dt capped at 1.0 s; at most 20 substeps | the authors expected frames as long as 200 ms (5 fps, i.e. 5 x 40 ms steps) to stay playable. That fits the P90 minimum (7 fps in software, section 4) | medium [inference] |
| C5 | variant stepper | 0x49cc60 (StepperBegin with an explicit dt argument), called only at 0x45534f (network path) | same rule | network copies step on their own dt. Not used offline | high [fact] |
| C6 | frame-dt read inside a substep | `physics_UpdateEngine` 0x46a333 reads `simclock_GetDt` (whole frame) per substep: rpm ease factor 2 x frame dt | correct only at 1 substep per frame | with 2+ substeps the rpm converges count times per frame. The bug is invisible when most frames are < 50 ms. Too weak to say which way the dev machines ran | low [inference] |
| C7 | dev frame-rate tooling | Gold only: command-line switch `interval` (string 0x4fe5f0, `cmdline_Parse` 0x49d3b3 -> flag 0x504c08) turns on a frame-interval profiler (0x498af0..0x499104, `timeGetTime`). It writes `interval.txt` / `histogram.txt` with "Median of last %d frames is %3.2f fps" and "Average of biggest jerks is %d ms", reported every 2000 ms (0x7d0). Retail 1.0 has none of these strings. Both exes carry an unbound `TOGGLE_FRAMERATE` action (key table id 0x54 at 0x4f3568); the keyboard switch 0x44eb50 sends it to the default case, so no handler was found | no target value is coded | by the Gold rebuild the team measured fps **and frame-time jitter ("jerks")**, i.e. pacing mattered to them. There is no threshold, so no step. The histogram array 0x5a6af8 (80 ints) is zeroed and printed but never filled (no writer found) | high for the facts; low for intent |

**Scan for hard-coded frame-time constants** (every x87 memory operand and every 32-bit float immediate in `.text`,
matched against 0.05, 1/30, 1/15, 1/60, 0.0667, 0.06, 0.025, 0.02, 0.04, 15, 16.67, 20, 24, 25, 30, 40, 50 and 60).
176 hits in Gold, 150 in retail. By function:
- The **only time-step constants** are:
  - 0.05 in the stepper inits (C1);
  - the 0.06 / 16.67 clock presets (C3).
- The **other 0.05 hits are not frame times:**
  - entity_PredictPosition 0x417f34: |x| < 0.05 test;
  - ai_IsSlidingBackward 0x41cdf8: +0.05 bias;
  - flamer stream shape 0x444099: the stock-20 dt the proxy already knew;
  - weapon_UpdateInstanceFiring 0x4a6933: a factor inside a range < 20 test;
  - wheel init 0x46d85f: a 0.05 s timer;
  - the handgun build.
- **15 / 20 / 25 / 30 / 40 / 50 / 60** are distances, speeds, radii, counts, sound and network constants, or the rpm
  factor 60 in physics_UpdateEngine. None multiplies or divides a time step.
- **None of 15, 20, 30 or 66.7 ms appears as a step or rate in the physics range 0x434000-0x441000 or in the wheel
  code 0x46d000-0x46e200.**
- So there is **no hidden fixed-rate assumption and no debug fixed-step switch** in either exe [fact, high for the
  scanned constant set].

**Clock users outside simclock** (import call sites):
- `GetTickCount`:
  - `ai_TestControlCandidate` 0x41b27a (result discarded);
  - `sound_CdWatchdog` 0x42340d;
  - `sound_CbEnqueue` 0x42375e / 0x4237fb / 0x423962 (radio-line queue timing);
  - `renderer_TexCacheGetHandle` 0x42f74c;
  - `renderer_FadePalette` 0x479b0c.
- `timeGetTime`: the profiler only.
- **No simulation code reads the wall clock directly. Everything goes through simclock** [fact]. This matters for the
  fixed-step port (study design s.7).

## 2. Code: per-step terms (the step-shaped parts of the physics)

A term is **dt-correct** if it scales with the step, so the step only changes discretisation error. A term is
**per-step** if it acts once per substep with a constant that ignores the step. Only per-step terms let the step change
behaviour, and only their constants can carry the step they were tuned at.

### 2.1 dt-correct (no clue, by construction)

| term | address | rule |
|---|---|---|
| gravity, drive, brake, aero and rolling drag, slope | 0x43a5d0, 0x43c310, imm -9.8 at 0x43a6a1 | constant-acceleration integration with step and step^2 / 2 (0x4bd1b8) |
| steering yaw | 0x43ce10 | w = steer x v / (2L); rotation w x step |
| side-slip friction | 0x43c850 | a x step, reversal guard, no per-step cap |
| pitch / roll ease on the ground | 0x437230 | rate += 2 x step x (target - rate), guarded 0 <= k <= 0.95. Stable to a 475 ms step |
| slide yaw ease | 0x43bda0 via 0x43a5d0 | k = (2.65618 / wheelbase) x step, same guard |
| air pitch ease | 0x43a811 | k = step toward -pi/20 rad/s, only while above it |
| surface damage | 0x438fd0 step 9 | rate x step |
| hull-point sweep | 0x440740 | n = min(trunc(\|v\| x step) + 1, 7), 1 m spacing. Fully resolved while \|v\| x step < 7 m (140 m/s at 50 ms) |

The easing guards (k <= 0.95) show the authors expected the step to vary and wrote stable first-order lags. They do
not pick a step.

### 2.2 Per-step terms, with the step at which each is self-consistent

| # | term | address | per-step constant | behaviour vs step T | where it is "sensible" | conf. |
|---|---|---|---|---|---|---|
| P1 | **wheel ride-height filter** (feeds the push-out, so it places the body) | init `0x46d7a3 push 15.0`, `0x46d7b1 push 0.7` -> `0x49e0f0` (period clamped >= 4 calls; a1 = -2 r cos(2 pi / period), a2 = r^2, unit DC gain by 200-step normalisation); per-substep `0x49e1b0` | pole radius 0.7 per call, period 15 calls | damping ratio **0.648 at every T**. Natural frequency **fn = 0.0876 / T Hz**: 3.50 (25 ms), 2.92 (30), 2.63 (33.3), 2.19 (40), 1.87 (46.7), 1.75 (50), 1.31 (66.7). Damped period 15 T | ride frequency is 0.5-1.5 Hz for passenger cars and 1.5-2.0 for sedan race cars (OptimumG). fn <= 2.0 needs T >= 43.8 ms and fn <= 1.5 needs T >= 58.4 ms (above the 50 ms ceiling). A damping ratio of 0.65 is race-car-like (0.5-0.7) rather than passenger (0.2-0.3; Kasprzak). **Car-like only at the top of the band** | low-medium (assumes a car-like target was intended; the measured body motion also includes P3 / P5) |
| P2 | suspension feed-forward | 0x46dcea, constant -5.0 at 0x4be4c4 | target = offset + 5 x (h - h_prev) per call | a lead of 5 T: 125 ms at 25, 167 at 33, 250 at 50 | no physical target to compare | - |
| P3 | **push-out by the deepest wheel** | 0x437230 (0x43792f) | full penetration removed in one step, position only | penetration per step grows with v_n x T; acts like a very stiff spring sampled at the step | none on its own; with P5 it makes the body motion step-shaped | high (mechanism) |
| P4 | **overshoot snap and rate zeroing** | 0x437230 (0x437f73) | when a rotation step would pass the wheel plane, snap the up row and set pitch and roll rates to 0 | share of frames at rest: 62 % at 25 ms, 11-40 % at 16.7 ms, 0-4 % at 5.7 ms. Body-rate reversals ("buzz") about 3x at 60 fps vs 20 (capture 014, n 4 per condition) | **calm from ~25 ms up**; the lower edge matches C2's 25 ms floor | medium (measured on our exe, n 4) |
| P5 | wheel-lift rate targets | 0x437230 table | +-pi pitch, +-pi/2 roll per lifted wheel, eased at 2 / s | one lifted substep at take-off gives a pitch kick of 2T x (-2 pi) = -4 pi T rad/s: -0.31 (25 ms), -0.42 (33), -0.50 (40), -0.63 (50). The chance that the lip falls inside a step is about d_f / (v T) (physics.md M34b, model) | sets the nose-down tumble on jumps. Gold (33-37 ms) peaked at 80 +- 8 deg vs retail (30 ms) 53 +- 18 deg (n 7 each, EMU-T05-CLEAN s.5) | high (rule), medium (probability) |
| P6 | **landing capture** | 0x43a779 (0.5 at 0x4bd138), landing snap in 0x43a5d0 | airborne while clearance > 0.5 m or growing, else snap the origin to the ground, keep v | the snap distance is uniform on (0.5 - \|vy\| T, 0.5]. **It is always downward iff \|vy\| x T <= 0.5 m.** Limits: vy 10 m/s -> T <= 50 ms; 14.45 (T05 take-off vy) -> 34.6; 19 (T05 face landing) -> 26.3. Grounded clearance is about 0, so the band is 0.5 m above the resting probe: the retail T06-strip trace `20261017-004107-r166sim-fpt06strip-1` reads grounded p5 / p50 / p95 -0.028 / -0.003 / 0.222 m (5,068 frames) and airborne min 0.477 m (1,290 frames) | the 0.5 m band fits one step of fall at T05-size landings only for T <= 26-35 ms | medium for the rule and the band (S1 done); low for intent |
| P7 | grip rebuild + projection | 0x43a5d0 end | v := forward x \|v\|, then projected onto the previous step's probe normal | a per-step cos(delta) loss. Ramp-lag loss grows with steps per second: lip speed about 45-47 m/s from 50 m/s foot speed at 21-24 steps/s, 41 at 60 (model). Brake-dive loss \|v\|(1 - cos p) per step: extra decel 0.00164 v / T (0.035 v at 46.9 ms; matched live, n 4). Coasting loss -0.063 m/s per 100 m per step/s (n 16) | content-coupled (T05 margin, braking distance); no internal optimum | high (rule and live) |
| P8 | one-step lags | 0x437230 weight transfer from the previous step's acceleration (0.008 m per m/s^2); probe normal from the previous step | lag = T | none | - |
| P9 | contact latch | flag 0x10, 0x43901e | persistent terrain contact answered on alternate substeps | impulse events per second follow the step rate | none | medium |
| P10 | **once per rendered frame, not per substep** | object / vehicle collision 0x4349c0 (frame dt, only the last record survives); far vehicles 0x43a3c0 (one whole-frame kinematic step); AI 0x40a320 and the script VM (per frame, 1/sim_dt dead-beat gains, ai.md); weapons / projectiles | per frame | in 1997 frame = step below 50 ms, so these ran once per step. **A fixed-step port must run them once per tick** (study design s.7) | high |

**What the per-step terms say together.**
- P4 sets a floor near 25 ms. It is measured, and it matches C2's floor.
- P1 favours 44-50 ms: car-like ride frequency.
- P6 favours <= 26-35 ms for the biggest designed landing (T05).
- P5 and P7 tie the jumps to the step but have no internal optimum.

The code cannot say which of P1 and P6 the authors tuned against. More likely neither was tuned as such: the 15-call
period and the 0.5 m band read like hand-picked round numbers. The study must measure the trade-off instead
(design s.5, hypotheses H1-H2).

## 3. Content as evidence (fallback)

### 3.1 Designed jumps (scripted `isAirborne` tests, `<re-archive>\data\out\fsm`)

| mission | machine | test | consequence | conf. |
|---|---|---|---|---|
| T05 | m35 | player airborne inside the 50 m square of path `2ndjump` node (6810, 43910), mid-canyon (lips at x 6876 / 6744) | cinematic camera on path `watchgroove` for **4 s**, then back; re-arms after 5 s | high [fact] |
| T06 | m34-m38 | airborne within 15 m (35 m for jump5) of `jump1`..`jump5` | camera 1-2 s per jump | high |
| T10 | m17 | groove airborne within 30 m of `jump` | camera until a keypress | high |
| T12 | m0, m28 | airborne within 15 m of `gotair` node 0 (a 29 m drop off the compound shelf) | **mission success** while airborne (with DISCO dead), else every objective fails; camera 3 s | high |
| T16 | m0 | airborne within 20 m (square) of `jump1` | **mission success** (`successAll`). The ramp is the fallen water tower; about 16 m/s needed at the lip (mission.md, model) | high |
| S03 | m0 | 7 airborne tests at `bridgeoutcheck` / `deathcheck` | cameras and voice lines; a bridge-out jump | high |
| S05 | m0 | `jumpcheck` | camera `jumpcam` 4.5 s | high |
| S06 | m1 | `wincam` | camera | high |

- **Every test is on the player** (p0 = user / groove). **No mission tests an AI car for being airborne**, and no AI
  route was found that requires a jump [fact for the scripts; the route-geometry check is study task S3].
- So "AI makes its jumps" is not designed content in I'76. AI completion matters for routes and races (T04 laps,
  T05 paths such as `killskeeter`, which passes (6700, 43910) next to the landing ramp's foot) [inference until S3].
- T05's 4 s camera vs the measured flight [inference, low]:
  - The camera starts about 16 m after the lip (0.3-0.4 s) and holds 4 s.
  - Retail flights: 2.9-3.4 s to the landing ramp at 132-166 m; 4.3-5.1 s to the far side at 204-237 m (n 9 crest
    descents, EMU-T05-CLEAN s.2); placed 56 m/s: 4.6 +- 0.5 s (n 7).
  - A 4 s camera covers the whole far-side flight or ends just after a ramp landing. It does not discriminate steps:
    the ballistic flight is dt-correct.

### 3.2 The T05 canyon margin

**Geometry** (physics.md M33a, data and model):
- aaramp4: 16.3 deg face, lip at y 26.9.
- Landing lip 132 m away.
- Lip speed needed: 45.4 m/s (probe lifts the car on), 46.1 (box clears the back face), 47.0 (origin at lip height).

**Retail 1.0 on the emulated P166, simulation physics:**

| run type | foot speed m/s | take-off m/s | outcome |
|---|---|---|---|
| crest descent (n 9, one per boot) | 55.1 +- 1.8 | 48.4 +- 1.8 | the two 46 m/s take-offs fell short (97-99 m); 1 destroyed |
| placed at 56 m/s (n 7) | 55.2 +- 1.6 at the foot | 51.6 +- 1.0 | 0 / 7 destroyed |

**Margin:**
- At retail's step (31 ms p50 in T05), a full-throttle descent leaves the lip at 48.4 +- 1.8 m/s against 45.4-47.0
  needed. That is **+3-7 %, about 1 sd**.
- So the canyon was clearable but not with a comfortable margin, even at the shortest era step [fact for the numbers,
  n 9; inference for "challenging"].
- The lip speed falls as steps per second rise (P7). A longer step gives a faster take-off, a larger landing-snap
  error (P6) and a larger take-off kick (P5).

### 3.3 What the designers saw: the era hardware

**Measured on the emulator** (86Box P90 / P166, Windows 95 GetTickCount at 1 ms; WHAT-IS-STOCK s.Measured,
EMU-MEMTRACE s.3, GOLD-STANDARD-FINGERPRINT):

| machine and settings | fps (n) | frame ms | substeps x step ms |
|---|---|---|---|
| P90, software (Gold exe, melee) | 7.1 (2) | 141 | 3 x 47 |
| P90, Glide | 16.7 (3) | 60 | 2 x 30 |
| P166, software, default detail (Gold exe) | 13.3 (1) | 75 | 2 x 37.6 |
| P166, Glide | 31.7 (3) | 31.5 | 1 x 31.5 |
| **developers' first-launch default for a P166** (Gold manual: 640x480, all features on) | not measured; the default-detail row above is the nearest | about 75 if it matches that row | about 2 x 37 (to verify, E1) |
| P166, software, lowest detail, retail 1.0 sim | melee 36-37; missions 28-33 | melee p50 26.8 +- 0.9 (12 traces / 3 boots); T05 31.1 +- 1.0 (16 / 16); T06 strip 33.0 (6 / 2); T06 route 35 | 1 x same |
| same, Gold exe | 11-16 % slower | melee 31.5, T05 34.5, strip 38.0 | 1 x same |

- **Emulator calibration** (EMU-MEMTRACE s.9.5):
  - The emulated P166 runs Quake's software renderer about 20 % faster than a real P166 (44.7 +- 1.0 vs 37.3 fps,
    n 9).
  - A real P166 at the same settings would therefore step about **15-20 % longer**: about 32 ms in melee and 37-42 ms
    in missions [inference, medium; Quake as a proxy].
- **What it means:**
  - On the box minimum and at default detail, 1997 players ran **two or three substeps of 30-47 ms**.
  - Only a fast machine at lowest detail ran single steps near 27-35 ms.
  - The P90 + Glide row lands on 60 ms frames, the same figure as C3's preset. Glide was not in the March 1997
    release (WHAT-IS-STOCK row 11), so this is a coincidence to note, not evidence.
- **Period reports** (WHAT-IS-STOCK rows 19-21, 24): June-July 1997 users call the P166 "smooth as silk" (software,
  trip missions), a P133 + Millennium "very jerky and slow", and a P90 / 16 MB "choke". These are subjective. No
  period fps figure exists.

## 4. The written record

Already collected, 33 sources (WHAT-IS-STOCK s.Development hardware and targets; I76-VERSIONS s.6). Summary:
- **[fact]** Producer Scott Krager (Gamezilla, 1996): "One major goal that we set for ourselves was to ensure that we
  had an acceptable frame rate for the minimum platform." "The game will run smoothly on a P90 as well as the
  higher-end systems." Mirror:
  localditch.com/interstate-76/articles/gamezilla.html.
- **[fact]** Shipping spec: P90 minimum; P133 / 32 MB recommended (PC Gamer UK #44, demo; Arsenal box). Win95 only.
  Software renderer at 320x240 / 480x360 / 640x480 at launch. "Designed for use on a Intel Pentium processor"; the
  performance knob is Graphic Detail (README.HLP, CD 1).
- **[fact]** Team: directed by Sean Vesce; produced by Scott Krager; lead design Zachary Norman; **lead programmer
  Dan Stanfill** (MobyGames credits, via Wayback).
- **[fact, new]** Roles from the in-game credits: `DATABASE.MW2` entry 0x53, decoded at
  `<re-archive>\data\out\mw2db\083_0x53_credits.txt` (Gold era), lines 16-65, checked this session:
  - **Vehicle Dynamics Programmer: Dan Stanfill.** The physics owner was the lead programmer.
  - 3D Programmer: Julio Jerez. He was the renderer programmer, not the physics one.
  - Engine Programmers: Kurt Arnlund, Scott T. Etherton, Marshall Robin, Henry Yu.
  - Engine Optimizations: Jean-Marc Morel.
  - AI Programmer: Karl Meissner.

  The printed manuals give only a flat list. No interview with Stanfill or Morel was found.
- **[fact]** The engine is the MechWarrior 2 engine extended (Games Domain 1997-02; Vesce, Gamasutra 1999). No
  physics-rate statement.
- **[fact]** Every 1997 patch keeps the stepper byte-identical. 1.05 adds only a landing-wreck guard (I76-VERSIONS
  s.3.2).
- **[lore]** Community caps: 20 / 24 / 25 fps (UCyborg, immi101, inbetweennames, 2017-2021). Their authors say the
  physics was "not intentionally" frame-tied; the numbers were found by trial.
- **[fact, null]** No developer statement names an fps, a physics rate or a timer API. No period benchmark of this
  game was found.

## 5. Web search this session (new leads only)

Research subagent, 2026-10-17. Sources are cited as it reported them; only the credits file was re-read by me.

### Documented fact

- **Gold Edition manual, "Performance"** (OCR, https://archive.org/stream/INTERSTATE_76/INTERSTATE_76_djvu.txt; the
  text names DirectX 5, 3Dfx and Rendition, so it is the 1998 manual):
  > "When you launch Interstate '76 the first time, the game will automatically configure default settings optimized
  > for your system. ... P90/P100: 320x200 resolution with all features enabled. P133 with 16 MB of RAM: 640x480
  > resolution with terrain textures disabled. P133 with more than 16 MB of RAM: 640x480 resolution with all features
  > enabled. P166 and above: 640x480 resolution with all features enabled."

  - The text is not in the GOG `Manual.pdf` text (`recon-2026-09-04\recon\human-record\manual_text.txt`).
  - It is the likely use of Gold's start-up CPU-speed probe (I76-VERSIONS 4.2 left this open). Not traced.
  - Both manuals: Visibility Range "Near provides for better performance while Far provides for better graphics
    **and gameplay**".
  - [inference] The developers chose these presets as acceptable. On a P166 that preset is far heavier than the
    owner's lowest-detail reference: about 13 fps on the emulator at default detail, i.e. 2 substeps of about 37 ms.
- **In-game credits:** see section 4. Vehicle Dynamics Programmer: Dan Stanfill.
- **Dev Game Club** (podcast RSS https://devgameclub.libsyn.com/rss; audio only, no transcript), topics as listed:
  - ep 422 (2025-03-12): "jitteriness and physics, compounding errors, deterministic physics";
  - ep 423: "broken physics world, compounded errors";
  - ep 424: "**physics implementation details from an implementer!**", "PC compatibility testing", "acceleration and
    turning", with "Julio Jerez, Daniel Stanfield" named;
  - ep 427 (Vesce and Norman, 2025-04-23): "a 28-year scoop on engine work", "the few basic bits in a vehicle sim".

  Not listened to: downloading needs the owner's OK. MP3s:
  - https://traffic.libsyn.com/secure/devgameclub/424-DGC-I76.mp3
  - https://traffic.libsyn.com/secure/devgameclub/427-DGC-I76.mp3
  - https://traffic.libsyn.com/secure/devgameclub/422-DGC-I76.mp3
- **Usenet**, comp.sys.ibm.pc.games.action, "Interstate 76 Framerate Woes / Cyrix Owners Beware!", April 1997
  (https://groups.google.com/g/comp.sys.ibm.pc.games.action/c/mkvoHdimpSw):
  - a Cyrix 166+ "drops to around 6-7 [fps] in the second to lowest resolution with all variables set to low or off".
    This is the only 1997 fps figure found;
  - a P200 (overclocked 150): "Runs smooth as silk with all options on".
- **Threads found but unread** (Google Groups rate-limited):
  - Scott Krager, "Interstate '76 in stores tomorrow!!!!!!!", 1997-04-02
    (https://groups.google.com/g/comp.sys.ibm.pc.games.action/c/0MicfbB-q-M). The snippet quotes "Choppy frame rate
    on a P200 w/Mystique". A **developer post on frame-rate complaints**.
  - "I76 crwls on P200MMX" (1997-04-02).
  - "Interstate 76 - How NOT to program a game?" (1997-09-17; a patch "improved frame-rate").
- **Other:**
  - PCGamingWiki: "Frame rates higher than 30 FPS (24 FPS in some cases) cause stuttering, physics and enemy AI
    problems". This is lore about modern PCs.
  - archive.org `Interstate_76_STB_Velocity_128_Pack-In_Activision_CD1`: a second card bundle, with the Riva 128.

### Community lore

- VOGONS "What are the most demanding games of their respective eras?", page 3
  (https://www.vogons.org/viewtopic.php?t=91807&start=40; from a search snippet, the page returns 403). This is the
  traceable origin of the old "P166 + Voodoo 1 playable with slowdowns" line, a recollection decades later:
  - "Pentium MMX 166MHz, Rendition 2100 and Voodoo 1. It had its slowdown moments ... but it was definitely playable";
  - "a slideshow on our 200 MHz MMX PC" (Cirrus 2D card).
- Local Ditch "FPS Jumping" (2013, https://www.localditch.com/posts/fps-jumping/): at modern frame rates the mission 5
  jump fails "even with nitro"; it works at 30 fps.

### Nulls

- No transcript or captions for DGC 422-427 (since transcribed locally: DEV-GAME-CLUB-I76.md).
- No I'76 physics statement by Julio Jerez (newtondynamics.com, GitHub) or by Stanfill, Morel and the other
  programmers.
- The Prima strategy guide (Knight & Boyle 1997) exists but has no online text.
- No walkthrough gives a mission 5 jump speed.
- Next Generation p.147, PC Gamer US June 1997 and GameSpot Arsenal: unavailable.

### What it changes for the study

- The developers' recommended-class default was a multi-substep, about 37 ms regime on the emulator, and longer on a
  real P166. The P166 lowest-detail reference is the lightest configuration the authors offered, not their default.
  This supports the owner's reading that it is a lower bound. It weakly favours the middle of the band over the
  bottom.
- Tasks added to the study: E1 (first-launch defaults on the emulated P90 / P133 / P166) and W1 (DGC audio, with the
  owner's OK).

## 6. Sources for the plausibility ranges

- Matt Giaraffa (OptimumG), "Tech Tip: Springs & Dampers, Part One", PDF copy at https://lfs.net/attachment/32094:
  "0.5 - 1.5 Hz for passenger cars; 1.5 - 2.0 Hz for sedan racecars and moderate downforce formula cars; 3.0 - 5.0+
  Hz for high downforce racecars".
- Jim Kasprzak, "Understanding your Dampers", Kaz Technologies FSAE guide,
  https://www.kaztechnologies.com/wp-content/uploads/A-Guide-To-Your-Dampers-Chapter-from-FSAE-Book-by-Jim-Kasprzak-Updated.pdf:
  - textbook damping ratios 0.2-0.3, suited to passenger cars;
  - 0.5-0.7 for sprung-mass heave, pitch and roll on FSAE-type race cars;
  - 0.3-0.5 for the unsprung mass.

  This is from a search-result summary; the PDF itself was not opened. To verify before the paper.

## 7. Open static checks (cheap, no console)

- **S1, done.** The probe's grounded clearance is about 0 (P6 row). The 0.5 m band sits above the resting probe.
- **S2.** Trace who reads `TOGGLE_FRAMERATE` (id 0x54) outside 0x44eb50, e.g. a table-driven handler. An on-screen
  fps display with a colour threshold would be a direct target.
- **S3.** Route-geometry census: for every FSM path and AI route, the segments that cross a class-11 ramp, a canyon or
  a drop above 3 m.
