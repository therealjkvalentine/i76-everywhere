# Gold-standard fingerprint: the retail P166 run as a machine-checkable target (2026-10-17 night)

Owner ruling 2026-10-15/16: the gold standard is the original retail 1.0 `I76.EXE` (1997-03-15) in 86Box on the
emulated P166, Windows 95, software renderer, lowest detail. Every fix must land on the same physics as read from game
memory on that run. This lane turns that into a file and a checker.

- **Reference:** lab `emu\results\gold-standard\retail-p166-low.json` (49 traces, 219 metrics, 20 rates, 3 fits).
  Human-readable: `reference-table.md` next to it.
- **Checker:** lab `emu\tools\memtrace\fingerprint.py` (`build`, `show`, `metrics`, `compare`, `selftest`). README:
  lab `emu\README.md`, "Gold-standard fingerprint".
- **Physics mode:** simulation (Arcade Phys. off). Every reference trace was checked: entity flag 0x10000 on 0 frames.
  The pre-fix arcade runs are not in it (EMU-T05-CLEAN.md).
- **New runs tonight** (headless par, my cap 1 VM, the box at 1-3 VMs, guest time only):
  retail sim melee loop boot 3 (n 4), `ref-melee-yaw3` (retail 3 boots x 3 reps, Gold 2 boots), `ref-t06strip`
  (retail 2 boots x 3 reps, Gold 1 boot). Placement read-back 0.00-2.54 m from target, speed 17.95-17.97 m/s.
- **Not touched:** the daily driver, the golden copy, the portable install. No live game on the lab copy.
- **Commits:** lab 04fa92c, 7e7c824, bb06e32, 3da24f4, 136d6fe.

## Summary

- **The target exists and is checkable from any trace.** One metric set is computed the same way from:
  - I76MEM run folders (emulator, any exe);
  - lab proxy telemetry `<tag>.phys.csv` + `<tag>.frames.txt` (phys-suite / envelope captures: our exe);
  - lab `I76_REPLAY` logs (`*.lab.csv`).
- **Pass bands come from the measured retail spread, not guesses.** Per metric: mean, sd, n, and the boot-level
  variance component (one-way random effects by run folder). Tolerance = the 95 % prediction half-width for the
  candidate's mean, Welch-Satterthwaite df, the metric's resolution as a floor. Details in section 2.
- **A/A (retail against retail, boots split in halves): 2 of 126 gate rows fail (1.6 %)**, both the same quantity
  (T05 step-size 5th percentile, 4.6-5.6 %). That is the gate's measured false-fail rate.
- **Sanity checks on existing traces:**

  | candidate | gate PASS / FAIL | what fails (behaviour) | what passes |
  |---|---|---|---|
  | Gold CD exe, P166 low, sim (30 traces) | 85 / 39 (31 of them step / frame rows) | yaw at 25 m/s **+19 %** (yaw3), 12 m/s +2.0 %, 18 m/s left +3.1 % (pooled +2.4 % passes); held speed +3 %; ramp-A apex at 30 m/s -1.4 % | accel, brake, gravity, drop, jump flight (take-off speed, apex, ballistic ratio 1.000), T06-strip yaw (-0.4 %), destruction rates |
  | retail 1.0 ARCADE (17 traces) | 31 / 14 | **yaw -30 %** (0.91 vs 1.30 rad/s), arcade flag rule | accel, brake, gravity |
  | lab env30 = ERA-ENVELOPE candidate, our exe (10 captures) | 33 / 41 | T06-strip accel (t20 -34 %), yaw at the strip -20 %, run-up speed +10 %, T05 take-off speed, substep rule (fixed step) | gravity, destruction / turnover rates |

- **The brief expected Gold to fail yaw by about 45 %. It does not, and should not:** that 45 % was Gold against
  retail in arcade mode (EMU-MEMTRACE correction, 2026-10-16). Against the simulation-mode reference Gold is +2.4 % at
  18 m/s in the melee crater (inside the band; left key +3.1 %, fails), +19 % at 25 m/s (fails), and matches on the T06
  strip. The arcade traces fail by -30 %: Gold / arcade = 1.33 / 0.91 = 1.46, the old 45 % gap.
- **New finding 1: the Gold-vs-retail yaw gap appears only when the car slides.**
  - T06 strip (full throttle, about 24 m/s, skid flag on 0 % of the window): retail 1.12 +- 0.01 (n 12, 2 boots),
    Gold 1.11 (n 6). Same.
  - Melee crater, 18 m/s held: retail 1.30 +- 0.04 (n 22, 3 boots, skid 33 % of the window), Gold 1.33 (n 15,
    6 boots, skid 66 %).
  - Melee, 25 m/s held (yaw3): retail 1.03 +- 0.17 (n 17, 3 boots, skid 42 %), Gold 1.22 (n 12, 2 boots, skid 76 %).
  - Earlier tonight, with 1 Gold boot and 2 retail boots, the 25 m/s gap read +26 % and the 18 m/s gap +4.6 %; one
    impacted steer sample was in each. Both shrank with the impact rejection and more boots; the 25 m/s gap held.
  - Reading: the Gold-only code (RETAIL-HANDLING-DIFF section 6) or data reaches the slide branch, not the grip-limited
    turn. Not traced statically tonight.
- **New finding 2: on the T06 strip, Gold on the emulator = retail on the emulator, and the lab is the outlier.**
  Same placements (phys-suite's), same protocol:

  | T06 strip | retail emu (n 6, 2 boots) | Gold emu (n 3) | lab env30 (n 4-5) | lab e29 / bw / next |
  |---|---|---|---|---|
  | 0-10 / 0-20 m/s, s | 1.17 / 4.18 | 1.17 / 4.17 | 1.06 / 2.76 | 1.04-1.05 / 2.71-2.75 |
  | distance in 10 s, m | 201.5 | 201.4 | 254.6 | 255-257 |
  | yaw R / L at the 1-2 s window, rad/s | 1.11 / 1.13 | 1.11 / 1.12 | 0.79 / 1.00 | 0.79-0.80 / 0.79-0.93 |
  | speed in that window, m/s | 24.0 | 24.2 | 21.4 | 26.5-28.0 |
  | ramp A foot speed from a 30 m/s placement | 35.3 | 35.4 | 38.7 | 38.8-39.0 |

  - The retail car stays in 3rd gear to 29 m/s in 11 s; the lab car is in 4th by 30 m/s at 6 s.
  - This matches LAB-FRAME-REPLAY ("the lab car accelerates ~20 % harder ... not the same car", armour maxima 9600 vs
    6080). Physics code is byte-identical between Gold CD and our exe, and Gold on the emulator matches retail, so the
    gap is lab-side.
  - **Leading candidate: a different car.** In TRIP missions the car comes from the save. The emulator runs load the
    par base's `C:\I76GOLD` saves (copied into the retail folder too), the lab copy its own. Checked read-only tonight:
    the lab copy's `ADDON\valepre4.vcf` is the stock file (md5 de680a86, = `.orig` = golden), and its `I76.ZFS` is the
    golden one (6dd57b16); the retail data `I76.ZFS` is 63.8 MB against GOG's 55.5 MB. The save's car (engine, tyres,
    armour) was not compared. **Not resolved tonight; next steps and owner test 1 below.**
  - Consequence: every lab-vs-retail behaviour comparison (ERA-ENVELOPE, retail-handling) inherits this car
    difference until it is fixed.
- **Retail steady yaw at full keyboard steer** (the brief's 12 / 18 / 25 m/s): melee yaw3 protocol 1.66 +- 0.03 /
  1.46 +- 0.08 / 1.03 +- 0.17 rad/s (n 16-17 each, 3 boots). The 18 m/s step of that protocol often does not hold its
  speed (the car slides out, skid 94 %); the melee-loop protocol holds it (17.3 +- 0.3 m/s) and gives 1.30.

## 1. What the fingerprint holds

Contexts (a metric is only compared within one): `melee` (Instant Melee loop protocol), `melee/yaw3`, `t05/crest`,
`t05/placed56`, `t06` (gen_t06.py routes, 2 boots, protocol changed between them: `stop0`), `t06strip` (phys-suite
placements).

| group | metrics | reference (retail sim, mean +- sd, n / boots) |
|---|---|---|
| mode / rules | arcade flag share; speed = \|v\|; substep rule count = min(20, floor(sim_dt x 20) + 1); parked rates | 0; max 1e-5 (melee); 100 % of frames; 0 |
| step, melee | sim_dt and step p5 / p50 / p95, mean step, steps per s, 1-step share | step p50 26.8 +- 0.9 ms, 1 step 99.7 % (12 / 3) |
| step, T05 / T06 strip | same | p50 31.1 +- 1.0 (16 / 16) / 33.0 +- 0.0 ms (6 / 2) |
| gravity | median 8-frame airborne vy slope; T06 40 m drop | 9.800 (T05 16 / 16, drop 6 / 2) |
| accel, melee | t10 / t20 / t30 | 1.06 +- 0.01 / 2.76 +- 0.01 / 5.64 +- 0.19 s (12 / 3) |
| accel, T06 strip | t10 / t20, d10 | 1.17 / 4.18 s, 201.5 m (6 / 2) |
| brake | mean decel 25 -> 5 m/s; distance 30 m/s -> 0 | melee 17.8 +- 1.4 m/s2, 25.5 +- 2.1 m (10 / 3; 2 impacts dropped); strip 11.88 +- 0.01 m/s2 |
| yaw | steady yaw R / L / pooled, held speed, gain, rise, t63, skid share, \|v_lat\|, slip angle | section Summary |
| body | cruise roll / pitch reversals per s, mean and p95 \|rate\| | melee roll 4.1 / pitch 4.6 per s (watch) |
| T05 flight | take-off speed and vy, apex, ballistic ratio apex / (vy^2 / 2g), air time, distance, landing x, peak pitch / roll and rates | placed56: take-off 51.6 +- 1.0 m/s, vy 14.45 +- 0.28, apex 10.66 +- 0.41 m, ratio 1.0000 (7 / 7) |
| T05 jump arc | distance = a + b x take-off speed, all T05 jumps | dist = -943 + 22.7 v, resid sd 22.4 m, r2 0.84 (n 16) |
| T06 ramp A | foot speed, apex y, air time, landing z per placement speed 26 / 30 / 34 | 30 m/s: foot 35.3, apex 28.5 m, air 2.27 s (5 / 2) |
| CheckImpact outcome | per jump: turned over, destroyed, flipped back (the arcade flip) | T05 crest 1 / 9 destroyed, placed56 0 / 7, flipped back 0 / 16; ramp A 0 / 14 |

- **Gate vs watch.** Gate metrics give PASS / FAIL. Watch metrics give ok / OUT: multimodal jump outcomes (distance,
  landing x, peak attitude: EMU-T05-CLEAN's three landing modes), skid share / slip / v_lat (0-or-1 per window), cruise
  wobble (random spawn), brake distance from the accel end. Rates are gated by Fisher exact (p < 0.05 fails).
- **INFO** when the reference has n < 3 or comes from one boot (between-boot spread unmeasured).

## 2. How the pass band is set

- Per metric, samples are grouped by boot (run folder; in-session repeats share one). Method of moments:
  var_w = within-boot mean square, var_b = max(0, (MSB - MSW) / n0).
- Tolerance for a candidate of n_c samples from nb_c boots:
  `t(0.975, df) x sqrt(var_w (1/n_r + 1/n_c) + var_b (1/nb_r + 1/nb_c))`, at least the floor. df = n_r - 1 if var_b = 0,
  else Welch-Satterthwaite.
- **Why boots matter:** the first build used the sample sd only. A/A then failed 15 of 120 rows. The T06 route boots
  (t06b / t06c) differ by 6 % in yaw because the protocol changed between them; the retail melee boot 3 has yawR
  1.38 vs 1.28 in boots 1-2. The boot component carries that.
- **Impact rejection:** a brake sample with any frame |dv/dt| > 100 m/s2 is dropped (2 of 12 melee brakes: 303 and
  650 m/s2, the crater wall). Normal full brake is 11-20 m/s2, single stop frames 42-64. A steer sample with any frame
  above 50 m/s2 is dropped (clean steer phases peak at 13-21; yaw3 run 015114 rep 1 had 175 and 75: yaw 0.82 and
  1.97 rad/s against 1.6-1.7 and 0.9-1.3 elsewhere).

## 3. Self-test (lab `emu\results\gold-standard\selftest-20261017.md`)

- **A/A:** boots alternated within each kind of run (context, placed or not). Half 0 against a reference from half 1:
  gate 58 PASS / 2 FAIL (T05 sim_dt p5 +5.6 %, step p5 +4.6 %, tol 1.0 / 0.67 ms). Half 1 against half 0: 66 / 0.
  Before the steer impact rejection the second half failed 5 yaw3 rows (the impacted rep).
  Most rows are INFO in the A/A because a half holds one boot of some contexts.
- **Gold CD exe** and **retail arcade:** table in the Summary.
- **Platform rows:** Gold's step is 11-16 % longer than retail's in every context (melee 31.5 vs 27.2 ms, T05 34.5 vs
  31.1, strip 38.0 vs 33.0): the known lower frame rate (EMU-MEMTRACE section 3). The lab's fixed 30 ms step fails the
  step-mix rows (one size, no 23-40 ms spread) and the substep rule (by design).

## 4. Our exe against the target (lab env30, `compare-lab-env30-20261017.md`)

- Passes: gravity (T05 and strip), drop g, destruction / turnover rates at T05 and ramp A.
- Fails beyond the car difference above: T05 crest take-off 52.4 vs 48.4 m/s (+8 %, n 15 vs 9), apex 11.0 vs 9.4 m.
  The lab's placed56 jumps take off at 41.1 m/s against 51.6: the envelope summary marks `canyon1_placed: false` for
  every env30 run, so those placements are suspect and are not a physics result.
- Replay logs (`tools\replay\runs\*.lab.csv`) read fine, but the replayed car leaves the line before the ramp
  (open-loop inputs), so their jump rows are not comparable.

## 5. Not done

- **No live lab run** (the session was disconnected; nothing needed the console tonight).
- **Gold side n:** Gold T06 strip is 1 boot, Gold yaw3 2 boots.
- **T06 strip retail n:** 2 boots. A third would tighten the strip band.
- **The cause of the lab car difference:** not traced. Next step (lab-side, no owner needed): run phys-suite's T06
  phases on the lab copy with the emulator's T06 save (par base `C:\I76GOLD\SAVE001.CMP` + `SAVEGAME.DIR`), or read
  the player's engine / gear / armour block in both and diff. Then re-run `fingerprint.py compare` on the new capture.
- **The cause of the Gold slide gap:** not traced statically.
- **Rollover rule as a rule:** only the per-jump outcome rates are in; the reference holds one destruction (T05 crest).
  A deliberate inverted-at-rest placement (place upside down, read the outcome) would make it a direct rule check.

## 6. How to use it

```
python -I emu\tools\memtrace\fingerprint.py compare <SRC...> [--label NAME] [--md OUT.md]
   SRC: run tags (g166-mloop), run folders, "C:\...\t06-env30-*.phys.csv", "C:\...\*.lab.csv"
python -I emu\tools\memtrace\fingerprint.py build           # after new retail sim runs (REF_TAGS in the script)
python -I emu\tools\memtrace\fingerprint.py selftest --md OUT.md
```

Exit code 1 when any gate row fails. A new lab build should be measured with phys-suite's T06 phases (the `t06strip`
context) and T05 placed / crest jumps, then compared; melee needs the emulator protocol (`ref-melee-loop`).

## 7. Owner tests (morning)

1. **Which car does the lab T06 start give you?** (5 min, needs the console.) Launch the lab twin as you normally
   test it, load the T06 bookmark the lab uses, and note the car name and the loadout on the salvage / repair screen.
   Then do the same in the 86Box retail VM (lab `emu\PLAY-P166-LOGGED.bat`: retail 1.0 with disc 2; your session is logged too).
   Look for: a different car or engine. If they differ, the lab-vs-retail accel / yaw gap in this file is the car,
   not the exe or the step.
2. **Feel check, retail 1.0 in simulation physics at 25 m/s in the melee crater** (10 min). In the retail VM (`emu\PLAY-P166-LOGGED.bat`),
   Options > Arcade Phys. off, Instant Melee, hold about 25 m/s (55 mph) and full-lock steer. Then the same in Gold (`PLAY-P166-LOGGED.bat --cd gold`, if your Gold install is on that disk). Look for:
   Gold sliding out more (skid 76 % vs 42 % of the window, yaw +19 %). Tell me if the difference is noticeable to you;
   it decides whether the Gold slide branch matters for the "stock" target.
