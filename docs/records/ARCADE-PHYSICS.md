# Arcade Phys. vs simulation physics: measured on the gold-standard rig, tied to the code (2026-10-17)

**Status: closed out 2026-10-17 (owner cut), data as gathered.** No new arcade runs; the cells not measured are listed in section 9.

Lane arcade-vs-sim. The question: what exactly does the "Arcade Phys." option change, in retail 1.0 and Gold?
- **Rig:** 86Box P166, Windows 95, software renderer, lowest detail (320x200), I76MEM memory traces. Retail exe
  `6cc509ad` (1.0), Gold exe `e1dca993` (Gold CD = GOG `9a232dcc` with the WINMM import restored). Every run read back
  its I76PLYR.DEF write (I76DRV.LOG: "88 bytes written, 88 read back, identical" retail, 96 Gold) and the entity flag
  0x10000 is checked on every frame: an "arcade" trace must have it on > 99 % of frames, a "sim" trace on 0.
- **Code side:** EXE-DIFF-MAP section 4 (five code sites, the same in every exe) and RETAIL-HANDLING-DIFF section 2.
- **Owner context:** the gold standard is simulation physics (owner ruling; OWNER-TEST-LIST item 45). Arcade is the
  mode every pre-2026-10-16-22:42 retail run was in by accident. This record measures it on purpose.
- **New runs (headless parrun, lane cap 2 VMs; host total at most 4 before the owner's pause, at most 3 after it):**
  - retail arcade: yaw3 x 3 boots (a, e, f; c and d were cut off by the pause and have no trace, b was killed), placed
    56 m/s T05 jumps x 3 boots (4 each), inverted at rest x 2 boots (5 each);
  - Gold arcade: yaw3 x 2 boots, placed jumps x 2 boots (4 each), inverted at rest x 1 boot (5);
  - simulation controls for the inverted test: retail x 5 boots, Gold x 5 boots (one drop per
    boot, because the car is destroyed).
- **Reused:** every sim reference trace (fingerprint REF_TAGS), the pre-fix retail arcade traces (melee loops, T05
  crest descents of run 224007), and the Gold sim traces (GOLD_TAGS).
- **Not touched:** daily driver, golden copy, portable install, owner disk images (parrun boots from a copy-on-write
  copy of the par bases). Read-only: the golden copy's Manual.pdf, one Gold exe copy for disassembly.
- **Lab commits:** 11a99be (tools, scripts, I76DRV `place ... INV`), 77f929c (gated-yaw analysis, run logs). The
  run queue (`emu\work\arcade\queue.ps1`, git-ignored work folder) now holds the 3-VM host cap and starts its runs
  at BelowNormal priority.
- **Sound-volume bytes:** the retail DEF these runs wrote is retail-plyr\RPLYR.DEF with the Arcade bit, so it carries
  SFX 4 (Gold's value), not retail's own default SFX 5. Kept on purpose: the simulation references were run with the
  same bytes, so the arcade and sim boots differ in the Arcade bit only. Volume is not read by any physics code.

## Summary

Cells: mean +- sd (n samples / boots). "Melee loop" = the in-session 18 m/s loops (flat ground); "yaw3" = the
12 / 18 / 25 m/s route (crater, partly sloped). Verdicts use the fingerprint pass band and Welch p.

| behaviour (retail 1.0, P166 low) | simulation | arcade | change | code site |
|---|---|---|---|---|
| lateral gain K = yaw x v / steer, 18 m/s, flat (melee loop) | 31.6 +- 0.05 (22 / 3) | 22.8 +- 0.9 (16 / 6) | **-28 %** (p 2e-16) | 3: C = A instead of 7.84 x wheels = 31.36 |
| K, 12 m/s (yaw3) | 30.4 +- 1.9 (17 / 3) | 23.5 +- 0.4 (11 / 3) | **-23 %** (p 2e-11) | 3 |
| steady yaw, full keyboard steer, 18 m/s (melee loop) | 1.30 +- 0.04 rad/s (22 / 3) | 0.91 +- 0.14 (16 / 6) | **-30 %** (p 4e-9) | 3 |
| steady yaw, 12 m/s (yaw3) | 1.66 +- 0.03 (17 / 3) | 1.34 +- 0.12 (13 / 3) | **-19 %** (p 5e-7) | 3 |
| steady yaw, 25 m/s (yaw3) | 1.03 +- 0.17 (17 / 3) | 0.92 +- 0.36 (16 / 3) | -10 %, **not resolved** (p 0.31) | 3 (sim car slides at 25: see 2.2) |
| lateral acceleration, median in the turn, 18 m/s | 2.29 g | 1.74 g | **-24 %** | 3 |
| cap slip state (flag 0x2000) in steer frames | 3-22 % | **0 % (every frame of every arcade trace)** | never set | 3 |
| tyre-solver skid flag (0x2) in steer frames, 18 m/s loop | 47 % | 26 % | about half | not an arcade site (solver) |
| slip angle in the turn, 18 m/s loop | 6.7 +- 7.4 deg | 0.7 +- 0.6 deg | -89 % | 3 |
| acceleration 0-10 / 0-20 / 0-30 m/s | 1.06 / 2.76 / 5.64 s (12 / 3) | 1.05 / 2.76 / 5.54 s (9 / 6) | same | none |
| braking 25 -> 5 m/s | 17.8 +- 1.4 m/s2 (10 / 3) | 18.2 +- 1.8 (9 / 6) | same (p 0.56) | none |
| body jounce, pitch / roll reversals per s (cruise) | 4.6 / 4.0 | 3.8 / 3.5 | same within the band (p 0.13 / 0.23) | none |
| placed 56 m/s T05 jump: take-off / apex / distance | 51.6 m/s / 10.7 m / 228 m (7 / 7) | 50.2 / 10.1 / 206 (12 / 3) | -3 % / -5 % / -9 % (p 0.02 / 0.04 / 0.16) | none (see 4.1) |
| placed jump: peak pitch | 53 +- 18 deg (7 / 7) | 50 +- 22 (12 / 3) | same (p 0.69) | none |
| placed jump: turned over / destroyed | 0 / 7, 0 / 7 | 1 / 12 (flipped back), 0 / 12 | same (p 1) | 4 after the landing |
| upside down and rotationally at rest, offline | **destroyed**, 0.06-0.075 s after roof contact (5 / 5; Gold 5 / 5 at 0.05-0.06 s) | **flipped upright** 0.035-0.065 s after roof contact (9 / 9; Gold 5 / 5) | the defining difference | 4 |
| frame time = physics step, p50 (matched yaw3 boots) | 28.3 +- 0.7 ms (9 / 3) | 29.0 +- 0.9 (9 / 3) | same (p 0.09) | none |

- **The manual's description** (Gold Manual.pdf p. 22, golden copy, read-only): "Arcade Phys. - This option
  eliminates skidding for easier handling and also prevents you from rolling your vehicles. For wannabe
  auto-vigilantes." [documented]
  - "Eliminates skidding": partly. The lateral cap never enters its slip state (0x2000 on 0 frames), and the slip
    angle drops by about 90 % at 18 m/s. But the tyre solver's own skid flag (0x2) still fires on about half as many
    frames as in simulation. [measured]
  - "Prevents you from rolling": **no.** Arcade cars still roll over: retail arcade crest descents turned over 2 of 8,
    retail arcade placed jumps 1 of 12, Gold arcade placed jumps 3 of 8, and the Gold arcade yaw3 car rolled 4 times in
    the crater. Arcade **puts the car back on its wheels** once it lies on its roof with low rotation rates. It does
    not stop the roll. [measured]
- **Arcade is not the cause of the jump-pitch gap.** Arcade changes nothing in the air: retail arcade jumps pitch
  like retail sim (61 vs 60 deg in the main landing mode), and Gold arcade jumps pitch like Gold sim (81 vs 80).
  [measured, matches the code: no arcade site is reached in flight]
- **What arcade does to Gold's jump wrecks:** Gold sim wrecked 3 of 7 placed jumps; Gold arcade turned over on
  3 of 8 just as often and survived all 3 (flipped upright, 0 of 8 destroyed; Fisher p 0.08 on destroyed). Same
  roll-over, different ending. [measured]
- **Arcade takes a fifth to a third off the turn at 12 and 18 m/s.** At 25 m/s the simulation car is already
  sliding (skid flag on about 90 % of the window frames) and its yaw drops to about the arcade value; the difference
  there is not resolved at n 16 / 3 boots.
- **Gold arcade = retail arcade**, as the code diff says (same five sites): K 22.7 vs 23.5 at 12 m/s (p 0.4),
  steady yaw 1.33 vs 1.34 at 12 m/s, the same flip in 5 of 5 vs 9 of 9. The remaining Gold-vs-retail differences
  (jump pitch, frame time) are the Gold-vs-retail differences already known with arcade off.

## 1. What the option is

### 1.1 Where the bit comes from

The bit is entity flags +0x454 bit 16 (0x10000); Nitro +0x458. Three things set it (EXE-DIFF-MAP s4):
1. **The options file / checkbox.** Option bit 0 of I76PLYR.DEF (retail +0x54, Gold +0x58; in memory
   `options_play_flags` 0x654b98 Gold, 0x5e14e4 retail). At vehicle init the player's car gets the bit if the option
   is set. The Options > "Arcade Phys." checkbox flips the option and sets or clears the bit on the player's car at
   once.
2. **A key.** `TOGGLE_ARCADE_MODE CTRL+A` is in both the 1.0 and Gold GAMEKEY.DEF (I76-VERSIONS 3.3). Not tested live
   here.
3. **The Taurus car, always.** At init any car that is the mission's FSM entity named exactly `taurus` gets the bit,
   whatever the options say.
   - Gold: `physics_InitEntity` 0x438efd calls 0x40aec0, which returns [0x51f5c4]. That pointer is set at 0x40aeb4 by
     the FSM registration loop (call at 0x4124d2) after a string compare with "taurus" (.rdata 0x4c3320).
     Disassembled this session, Gold exe 9a232dcc.
   - Mission files with a car named `taurus` (a byte scan of the retail CD's MISSIONS\*.MSN: vehicle `vppirna1`, the
     Piranha, then the name `taurus`): S02, T01, T03, T05, T10, T11, T14. T02 has the string in another table.
     [static scan, not traced]
   - Live check, not conclusive: I76MEM's nearest-AI-car flags never showed 0x10000 in 4 T05 runs (Gold and retail,
     16 AI cars). Taurus may never have been the nearest car. [measured, null]
   - So in those missions **Taurus's Piranha has arcade steering and the arcade flip, and the AI steers it with the
     arcade turn model (site 5).**

### 1.2 What the bit does (code, all exes)

| site | Gold (= GOG, ours) | retail 1.0 | effect |
|---|---|---|---|
| 3 lateral cap | 0x43ceb4 in 0x43ce10 | 0x475a30 in 0x4759b0 | yaw target `steer x C / v`, C = **A** (9.8 n_y^3 x grip x mu x wheels / 4, about 23.4 for the melee car on flat ground) instead of **7.84 x wheels = 31.36**. With C = A the lateral demand never exceeds A, so the cap's slip fraction and slip state are never set |
| 4 inverted at rest | 0x4370d3 in `physics_CheckImpact` 0x436ff0 | 0x46fef0 in 0x46fe20 | car upside down (up.n < -0.8) with pitch and roll rates < pi/5, grounded, not dead: **arcade and offline: rows negated (upright), sound 4; else `object_Destroy`** |
| 5 AI turn model | 0x40ffd2 in `ai_SteerToHeading` | 0x40a275 | the AI's predicted turn rate: A x 0.25 with the bit, 7.84 x wheels without |
| 1, 2 set | init 0x438f1c, checkbox 0x43d1a0 | 0x4722a9, 0x475c70 | as 1.1 |

Nothing else reads the bit: engine, brakes, suspension, gravity, damage, weapons, network code (site 4 tests
"offline" itself) are unchanged. **In multiplayer an arcade car on its roof is destroyed like a simulation car.**
[static, EXE-DIFF-MAP s4; not run here]


## 2. Steering (site 3)

### 2.1 The lateral cap, predicted and measured

Site 3 sets the yaw target `steer x C / v`. Simulation uses C = 7.84 x wheels in contact = 31.36 (4 wheels). Arcade
uses C = A = 9.8 n_y^3 x grip x mu x wheels / 4, about 23.4 for the melee car on flat ground. So on flat ground the
code predicts K = yaw x v / steer of 31.4 (sim) and about 23.4 (arcade), a ratio of 0.75.

| cell | RS retail sim | RA retail arcade | GS Gold sim | GA Gold arcade |
|---|---|---|---|---|
| K, 18 m/s melee loop (flat) | 31.6 +- 0.05 (22 / 3) | 22.8 +- 0.9 (16 / 6) | 31.65 +- 0.08 (15 / 5) | - (no Gold arcade loop) |
| K, 12 m/s yaw3 | 30.4 +- 1.9 (17 / 3) | 23.5 +- 0.4 (11 / 3) | 31.3 +- 0.3 (12 / 2) | 22.7 +- 2.0 (6 / 2) |
| K / n_y^3, 18 m/s yaw3 (sloped) | 40.3 +- 3.6 (10 / 3) | 21.4 +- 3.9 (8 / 3) | 41.1 +- 3.7 (12 / 2) | 21.1 +- 3.9 (6 / 2) |
| K, 25 m/s yaw3 | 30.7 +- 1.4 (17 / 3) | 18.6 +- 5.2 (12 / 3) | 31.5 +- 0.05 (12 / 2) | 17.2 +- 4.8 (8 / 2) |

- **Measured K matches the code** within 1 % for simulation (31.6 vs 31.36) and within 3 % for arcade on flat ground
  (22.8 vs about 23.4). Measured arcade / sim ratio 0.72 on the loop, 0.77 at 12 m/s; predicted 0.75. [measured +
  static]
- **The slope signature.** Arcade's C carries n_y^3 (the ground normal's vertical component, cubed); simulation's
  does not. On the sloped yaw3 stretch at 18 m/s, sim K divided by n_y^3 goes **up** to 40 (sim K itself stays 31.5:
  it does not care about the slope), while arcade K / n_y^3 comes back to about 21, near the flat-ground A. So an arcade
  car turns less on a slope or a bank; a sim car turns the same. [measured]
- **K excludes skid frames**, so it measures the cap, not the solver. At 25 m/s arcade K is lower and noisier
  (18.6 +- 5.2) than the flat-ground A. Not explained; the 25 m/s yaw3 stretch is the most sloped and the arcade
  car often failed to hold 25 m/s on it (2.2).

### 2.2 Steady yaw rate (what the driver feels)

| speed | RS | RA | RA vs RS | GS | GA | GA vs GS |
|---|---|---|---|---|---|---|
| 12 m/s (yaw3) | 1.66 +- 0.03 (17 / 3) | 1.34 +- 0.12 (13 / 3) | -19 % (p 5e-7) | 1.69 +- 0.02 (12 / 2) | 1.33 +- 0.15 (8 / 2) | -21 % |
| 18 m/s (melee loop) | 1.30 +- 0.04 (22 / 3) | 0.91 +- 0.14 (16 / 6) | -30 % (p 4e-9) | 1.33 +- 0.20 (15 / 5) | - | - |
| 18 m/s (yaw3) | 1.46 +- 0.08 (16 / 3) | 0.97 +- 0.23 (9 / 3) | -34 % (p 2e-4) | 1.46 +- 0.09 (12 / 2) | 1.18 +- 0.33 (9 / 2) | -19 % |
| 25 m/s (yaw3) | 1.03 +- 0.17 (17 / 3) | 0.92 +- 0.36 (16 / 3) | -10 % (p 0.31) | 1.23 +- 0.18 (12 / 2) | 0.89 +- 0.41 (10 / 2) | -28 % (in band) |

(fingerprint `yaw.<v>.yaw_ss`: |r| mean 1-2 s after full keyboard steer.)

- **Left and right agree** (yawL / yawR in the analysis output; e.g. 12 m/s arcade 1.34 L, 1.35 R).
- **Steer rise time is unchanged** (0 -> 0.9 in 2.41-2.42 s in all four sets): arcade does not touch the input ramp.
- **At 25 m/s the comparison is weak.** The simulation car slides there (skid flag on 92 % of the gated window frames,
  table 2.3), so its yaw is set by the slide, not by the cap. The arcade car missed the target speed on the prep run
  in many reps (speed in the window 17.5 +- 8.0 m/s against 24.1 +- 1.1 for sim): it turns less and ran into the crater
  wall or slowed in the turn before. Those reps stay in the fingerprint numbers above.

### 2.3 Gated reps (added on resume)

The yaw3 route was built for the sim car. With arcade's smaller turn, some prep runs ended off line, so I added a gate
(arcade_vs_sim.py `gated_yaw`): a rep counts only if the speed at steer onset is within 20 % of the target, the car
stays upright and there is no impact; yaw = median |r| 1.0-2.5 s after onset.

| speed | RS | RA | RA vs RS | GS | GA | GA vs GS |
|---|---|---|---|---|---|---|
| 12 | 2.06 +- 0.06 (11 / 3) | 1.75 +- 0.13 (8 / 3) | -15 % (p 2e-4) | 2.12 +- 0.03 (9 / 2) | 1.68 +- 0.18 (6 / 2) | -21 % (p 0.002) |
| 18 | 1.98 +- 0.04 (3 / 3) | 1.54 +- 0.45 (7 / 2) | -22 % (p 0.04) | 1.96 +- 0.07 (4 / 2) | 1.42 +- 0.36 (5 / 2) | -28 % (p 0.03) |
| 25 | 1.70 +- 0.27 (13 / 3) | 1.43 +- 0.49 (6 / 3) | -16 % (p 0.26) | 1.43 +- 0.33 (3 / 1) | 1.25 +- 0.78 (5 / 2) | -13 % (p 0.67) |

- The gate does not change the picture: a clear cut at 12 and 18 m/s, not resolved at 25 m/s.
- The gated window is later and narrower than the fingerprint window, so its yaw values are higher; compare
  within a table, not across.
- The gated sim cells at 18 m/s and Gold sim at 25 m/s have n 3-4 (the sim prep runs often over- or under-shot the
  speed); below the n >= 5 target.

### 2.4 Lateral acceleration and slip

- **Median lateral acceleration in the turn:** 18 m/s loop 2.29 -> 1.74 g (-24 %, p 2e-17); 12 m/s 1.90 -> 1.67 g
  (-12 %); 25 m/s 2.48 -> 1.73 g (-30 %). The **peaks** (lat_g_max) are the same within the spread at every speed
  (e.g. 18 m/s loop 3.27 vs 2.99 g, p 0.05): arcade lowers the steady turn, not the transients.
- **Cap slip state (0x2000):** sim 3-22 % of steer frames; arcade 0 of every frame in all 52 arcade traces. With
  C = A the lateral demand never exceeds the grip limit A, so the cap cannot enter it.
- **Tyre-solver skid flag (0x2):** still set in arcade, about half as often at 18 m/s on the loop (26 vs 47 %).
  The solver is not an arcade site; it sees a smaller slip because the cap asks for less yaw.
- **Slip angle at 18 m/s (loop):** 6.7 +- 7.4 -> 0.7 +- 0.6 deg; lateral sliding speed 1.86 -> 0.21 m/s.

## 3. Everything that should not change (and does not)

Retail sim (n 12 / 3 boots for accel, 10 / 3 for braking) against retail arcade (9 / 6, the pre-fix melee loops):

| metric | sim | arcade | Welch p |
|---|---|---|---|
| 0-10 / 0-20 / 0-30 m/s | 1.062 / 2.755 / 5.64 s | 1.050 / 2.76 / 5.54 s | 0.07 / 0.84 / 0.25 |
| path length in the first 10 s of throttle | 268.7 +- 5.6 m | 269.6 +- 7.2 | 0.77 |
| braking 25 -> 5 m/s | 17.75 +- 1.39 m/s2 | 18.18 +- 1.76 | 0.56 |
| braking distance from about 53 m/s | 87.9 +- 5.2 m | 86.9 +- 2.3 | 0.58 |
| cruise pitch reversals / s | 4.6 +- 1.4 | 3.8 +- 0.9 | 0.13 |
| cruise roll reversals / s | 4.0 +- 0.9 | 3.5 +- 0.8 | 0.23 |
| cruise mean abs roll | 9.8 +- 2.9 deg | 9.9 +- 2.4 | 0.97 |
| cruise mean abs pitch | 16.1 +- 2.6 deg | 18.5 +- 2.6 | 0.05 |
| cruise pitch p95 | 41.3 +- 5.7 deg | 47.0 +- 5.1 | 0.03 |

- Engine, brakes and the body's pitch / roll motion are unchanged, as the code says (no arcade site in the engine,
  brake, suspension or attitude code).
- **Cruise pitch p95 is 14 % higher in arcade** (p 0.03, inside the fingerprint band). One metric of nine at
  p < 0.05 is what chance gives; the arcade loops are pre-fix boots, not matched to the sim boots. Not claimed.
- **Frame time and step.** Matched yaw3 boots: step p50 28.3 +- 0.7 (sim) vs 29.0 +- 0.9 ms (arcade), p95 35.9 vs
  37.2, one step per frame on 99.6 vs 99.3 % of frames. Placed jumps: p50 31.1 vs 30.5 ms. The unmatched pre-fix
  melee loops show a lower arcade p95 (29.5 vs 33.8 ms); the matched boots do not, so that is a boot / era
  difference, not arcade. Gold yaw3: 32.2 (sim) vs 33.3 ms (arcade), flagged by the band at n 2 boots each, Gold
  jumps 34.5 vs 34.9 (same). [measured]

## 4. Jumps (T05 placed at 56 m/s and crest descents)

### 4.1 Flight and pitch

| cell | RS | RA | GS | GA |
|---|---|---|---|---|
| n jumps / boots (placed 56) | 7 / 7 | 12 / 3 | 7 / 5 | 8 / 2 |
| take-off speed m/s | 51.6 +- 1.0 | 50.2 +- 1.5 | 51.2 +- 1.3 | 51.0 +- 1.1 |
| apex m | 10.66 +- 0.41 | 10.11 +- 0.67 | 10.49 +- 0.54 | 10.48 +- 0.42 |
| distance m | 228 +- 28 | 206 +- 35 | 248 +- 48 | 225 +- 29 |
| peak pitch deg, all | 53 +- 18 | 50 +- 22 | 80 +- 8 | 64 +- 31 |
| peak pitch deg, without the 15-deg mode | 60 (n 6) | 61 (n 9) | 80 (n 7) | 81 (n 6) |
| pitch rate rad/s | 1.61 +- 0.15 | 1.68 +- 0.58 | 1.71 +- 0.60 | 1.78 +- 0.27 |
| ballistic ratio | 1.000 | 1.003 | 1.000 | 1.000 |

- **The 15-deg mode.** Some reps leave the ramp on a different line: take-off 52.5-52.9 m/s, pitch 15-17 deg, roll
  6-16 deg, distance 166-178 m. It occurs in sim too (RS 1 of 7) and in both arcade sets (RA 3 of 12, GA 2 of 8), never
  in GS (0 of 7). It is a take-off mode, not an arcade effect, and it is what makes the "all" pitch rows look different.
  Without it, arcade = sim on each exe, and Gold > retail by about 20 deg on each mode.
- **Retail arcade take-off 1.4 m/s slower (p 0.02), apex 0.5 m lower (p 0.04).** Small; the arcade placed reps 2-4
  of each boot start from the placement after a previous jump, the sim reference boots placed once each. The
  placement read-back (speed 56.01-56.04 m/s, 6-8 m from the target) is the same. Not claimed as arcade.
- **Crest descents** (pre-fix run 224007, RA 8 / 1 boot vs RS 9 / 9): take-off 48.4 vs 48.4, apex 9.4 vs 9.4, pitch
  47 vs 45 deg (p 0.89). Same.

### 4.2 Outcomes

| set | context | n | turned over | flipped back | destroyed |
|---|---|---|---|---|---|
| RS | placed 56 | 7 | 0 | 0 | 0 |
| RA | placed 56 | 12 | 1 | 1 | 0 |
| GS | placed 56 | 7 | 3 | 0 | 3 |
| GA | placed 56 | 8 | 3 | 3 | 0 |
| RS | crest | 9 | 1 | 0 | 1 |
| RA | crest | 8 | 2 | 1 | 0 |

- Fisher: GS vs GA destroyed 3/7 vs 0/8, p 0.08; turned over 3/7 vs 3/8, p 1. RS vs RA turned over 0/7 vs 1/12, p 1.
- **Arcade does not change how often the car turns over; it changes what happens after.** Every arcade car that
  came to rest on its roof was put back on its wheels. RA crest: one of the two turned-over cars was flipped back; the
  other kept rolling and came down on its wheels by itself.

## 5. Upside down at rest (site 4): the new test

I76DRV `place ... INV` puts the player car upside down on the flat T06 strip, either touching the ground ("inv") or
dropped from a little height ("invair"), with zero velocity and rotation, then watches. Five placements per arcade
boot; one per sim boot (the car is destroyed).

| set | n | outcome | time from roof contact |
|---|---|---|---|
| retail arcade | 9 (5 inv + 4 invair; 1 placement came out upright and is excluded) | 9 / 9 flipped upright | 0.035-0.065 s (one frame after the first at-rest frame) |
| Gold arcade | 5 (invair) | 5 / 5 flipped upright | 0.038-0.050 s |
| retail sim | 5 (invair) | 5 / 5 destroyed | 0.060-0.075 s |
| Gold sim | 5 (invair) | 5 / 5 destroyed | 0.050-0.061 s |

- **The flip** happens in one frame: up.y -1.00 -> +1.00. The rotation rates are zeroed; the car keeps a downward
  velocity of 3.9-4.4 m/s and drops 0.13-0.20 m (it was turned in place about its own centre and falls onto its
  wheels). Health drops by 3-4 of 9600 (the landing). [measured, n 14]
- **The destroy** in simulation sets the dead flags 0x80000020 with health still 9599: it is `object_Destroy`, not
  damage. [measured]
- **The trigger matches the code threshold.** Arcade flips in the driven traces (10 events: 5 yaw3 crater rolls,
  5 T05 landings) all came after 0.29-0.69 s on the roof with pitch and roll rates of 0.04-0.62 rad/s just before, all
  below pi/5 = 0.628. No car was flipped while it was still rotating faster. [measured; code: EXE-DIFF-MAP s4]
- **"At rest" means rotationally at rest only.** The test reads the pitch and roll rates, not the car's speed. Four of
  the 10 driven flips happened while the car was **sliding on its roof at 12.9-26.3 m/s** (T05 landings); arcade put it
  on its wheels mid-slide. [measured]
- **Offline only.** The code tests "offline" before the flip; in multiplayer an arcade car on its roof is destroyed.
  Not run here (no network rig).

## 6. Gold arcade vs retail arcade

The five arcade sites have the same arithmetic in both exes (EXE-DIFF-MAP s4). Measured:

| metric | RA | GA | verdict |
|---|---|---|---|
| K, 12 m/s | 23.5 +- 0.4 (11 / 3) | 22.7 +- 2.0 (6 / 2) | same (-3 %) |
| K / n_y^3, 18 m/s (sloped) | 21.4 +- 3.9 | 21.1 +- 3.9 | same |
| steady yaw 12 m/s | 1.34 +- 0.12 | 1.33 +- 0.15 | same |
| steady yaw 18 m/s (yaw3) | 0.97 +- 0.23 | 1.18 +- 0.33 | same (in band) |
| cap slip state | 0 % | 0 % | same |
| inverted at rest | 9 / 9 flipped | 5 / 5 flipped | same |
| placed-jump pitch (main mode) | 61 deg | 81 deg | the known retail-vs-Gold gap, arcade off or on |
| step p50, yaw3 | 29.0 ms | 33.3 ms | the known retail-vs-Gold frame-time gap |

So Arcade Phys. is the same option in both exes. Whatever separates retail from Gold separates them in both modes.

## 7. What this means for the questions on the table

- **"Gold flips nose-down too easily" (owner, 2026-10-17).** Not arcade. Arcade changes nothing in flight, and the
  Gold-vs-retail pitch gap is the same with arcade on (81 vs 61 deg) as off (80 vs 60). Arcade only changes what
  happens **after** the car lands on its roof: it survives. A player who remembers 1997 rollovers as survivable may
  remember arcade mode (or the Taurus car, which always has the bit).
- **Which mode the 1997 player saw.** Both exes default the option to off (both zero the flag dword in their
  defaults; RETAIL-HANDLING-DIFF s3). Off = simulation. The gold standard stays simulation (owner ruling).
- **Physics-step study (PHYSICS-STEP-STUDY-DESIGN).** Input to it, not a change to it:
  - every study run must check flag 0x10000 = 0 on every frame (arcade_vs_sim.py `load()` does it), because one
    accidental arcade boot moves K by 28 % and steady yaw by 20-30 %, far more than any step effect measured so far;
  - arcade does not change the frame time on matched boots (section 3), so the arcade traces cannot stand in for sim
    traces in the step grid, but they do not bias the step distribution either;
  - the two arcade sites that matter (3 and 4) contain no dt term in the code read for EXE-DIFF-MAP; under the fixed
    whole-sim tick they need no special handling.
- **Our port.** Ours runs Gold's code; arcade there is identical (section 6). The lab proxy switch
  `I76_RETAIL_HANDLING=1` (RETAIL-HANDLING-SWITCH) sets exactly this bit every frame, so it is "arcade on", not
  "retail handling". Its name predates the arcade finding and is misleading; proposal only: rename it
  `I76_FORCE_ARCADE`.
- **If someone wants arcade steering without the flip, or the reverse:** not possible with the option. Sites 3 and 4
  read the same bit. A patch would have to change one of the two tests (file offsets in RETAIL-HANDLING-DIFF s6).

## 8. Method, runs, caveats

- **Scripts:** `emu\tools\memtrace\gen_arcade.py` writes `emu\tools\par\scripts\arc-*.txt`. Each differs from its sim
  reference script only in the I76PLYR.DEF bytes (retail +0x54 bit 0, Gold +0x58 bit 0; Gold difficulty byte +0x5c = 0
  as in every Gold reference run). Inverted placement: I76DRV `place ... INV`, lane build `emu\work\arcade\drv`.
- **Analysis:** `python -I emu\tools\memtrace\arcade_vs_sim.py --md OUT --json OUT` (about 20 s). It uses the
  fingerprint metric code unchanged, drops any trace whose arcade share does not fit its set (none dropped), checks
  repeated jumps for replays (none), and adds K, K / n_y^3, lateral g, flag shares, the gated yaw table, the inverted
  timeline and the driven flips.
- **Runs** (`emu\results\par\20261017-*-arcvs-*`, traces in `emu\results\memtrace\`): r-yaw3 a, e, f; r-t05j a, b, c;
  r-inv-a, r-invair-a; r-invairsim 1-5; g-yaw3 a, b; g-t05j a, b; g-invair-a; g-invairsim 1-5.
  r-inv-sim-1 is excluded: the car was dead at the first sample (placed touching the ground in sim). r-yaw3-b was
  killed; r-yaw3-c / -d were cut off by the owner's pause and have no trace.
- **Emulator speed.** Most new runs ran below real time on the host (for example g-t05j-b: guest / host 0.61, 3 VMs
  on the host at BelowNormal priority). All numbers here are guest-time (GetTickCount and the frame counter), which
  stays valid (emu README, real-time check); the step distributions match the earlier boots (section 3).
- **Caveats.**
  - The retail arcade melee-loop set (16 / 6) is pre-fix boots, not matched to the sim loop boots; the yaw3 and jump
    sets are matched (same script, same base, Arcade bit only).
  - Gold arcade has 2 boots per cell (n 6-10 samples); several Gold cells are at n < 5 in the gated table.
  - The CTRL+A key (`TOGGLE_ARCADE_MODE` in GAMEKEY.DEF) was not tested.
  - The Taurus claim (1.1) is static plus a null live check; not traced.

## 9. Close-out (2026-10-17, owner cut)

The owner cut new arcade runs to save cost. Everything above stands as measured; nothing was re-run for the close-out.

**What arcade changes, exactly (code: EXE-DIFF-MAP s4, the same five sites in retail 1.0, Gold, GOG and ours):**

| site | what the Arcade bit (entity flag 0x10000) does | measured here |
|---|---|---|
| 1 init / 2 checkbox | sets the bit from I76PLYR.DEF (retail +0x54 bit 0, Gold +0x58 bit 0) or the options checkbox | yes: DEF read back on every boot, flag share > 99 % arcade / 0 sim |
| 3 lateral cap | yaw target uses C = A (about 23.4 for the melee car) instead of 7.84 x wheels = 31.36; the cap never enters its slip state | yes: K -23 to -28 %, steady yaw -19 to -30 % at 12-18 m/s, slip state 0 % of frames, retail and Gold |
| 4 inverted at rest | offline, upside down with pitch / roll rates < pi/5: flip upright instead of `object_Destroy` | yes offline: 9 / 9 retail, 5 / 5 Gold flipped; sim 5 / 5 + 5 / 5 destroyed |
| 5 AI turn model | the AI's predicted turn rate A x 0.25 instead of 7.84 x wheels | **no** (not traced; only matters for an AI car carrying the bit) |

Not changed by the bit (code and measured): engine, brakes, suspension / jounce, flight, jump take-off pitch,
frame time.

**Cells not measured (left open, not scheduled):**
- the multiplayer branch of site 4 (an arcade car on its roof is destroyed online): static only, no network rig;
- site 5 (AI turn model under arcade) and the Taurus always-arcade claim (1.1): static plus a null check, no trace;
- the CTRL+A toggle (`TOGGLE_ARCADE_MODE`);
- steady yaw at 25 m/s: -10 %, not resolved at 16 / 3 boots (the sim car is already sliding there);
- retail arcade yaw3 boots c / d (lost to the pause; the set is n 3 boots) and a matched retail arcade melee-loop set
  (the 16 / 6 set is pre-fix boots);
- Gold arcade beyond 2 boots per cell (several gated cells at n < 5);
- arcade on our exe under the whole-sim tick: not run; static prediction is no change, because sites 3 and 4 contain
  no dt term (section 7).

Lab files of this lane are committed (11a99be, 77f929c); no uncommitted arcade-lane files remain.
