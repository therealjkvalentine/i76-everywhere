# T05 canyon from a repaired crest start, retail 1.0 vs Gold (emulated P166, 2026-10-16 night)

Follow-up to EMU-MEMTRACE.md section 7, item 1. Reference: the retail 1.0 `I76.EXE` on the emulated P166, software
renderer, lowest detail. The Gold CD exe is the comparison.

- **Where:** lab `emu\`. Scripts are `tools\par\scripts\ref-t05clean*-<exe>.txt` (`tools\memtrace\gen_t05clean.py`).
  The analyser is `tools\memtrace\t05clean_analyse.py`.
- **Summaries:** `results\memtrace-summary-t05clean.json` and `results\memtrace-summary-melee-sim.json`.
- **Clip:** `results\writeup\video\retail-sim-p166-t05-clean-descent.mp4`.
- **Not touched:** the daily driver, the golden copy and the portable install.
- **How runs were done:** headless par runs only, with at most 2 of my VMs at once.
  - **One slip:** for about 5 minutes my queue script's VM count read empty and it started 3 extra VMs. I stopped my
    own runs and deleted their folders; no data came from them.
  - **Host load was high:** 4-7 86Box VMs from all lanes on 8 threads. Guest-time measurements do not depend on it.

## Summary

- **Every earlier retail run was in arcade physics.** The static-stepvehicle-diff lane found it; it is checked here.
  - **Cause:** the retail scripts copied the Gold-layout `I76PLYR.DEF` (0x60 bytes) into the retail folder. Retail
    reads 0x58 bytes in its own layout, so its option-flag dword at 0x54 got Gold bytes `01 00 00 00`: bit 0 =
    Arcade Phys.
  - **Measured:** player entity flag 0x10000 on every retail frame (T05 180103: 13,638 / 13,638; melee loop 185645:
    13,703 / 13,703). Gold: 0.
  - **Fixed:** `make_retail_plyr.py` writes the Gold file minus bytes 0x4e-0x4f and 0x56-0x57, 0x58 bytes, option
    flags 0. I76DRV `filehex` writes it into the retail folder and reads it back: "88 bytes written, 88 read back,
    identical" in every run.
  - **Checked:** flag 0x10000 is on 0 frames in all 11 sim runs.
- **Retail handling in simulation physics is close to Gold.** Steady yaw at full keyboard steer, held 18 m/s:
  - retail 1.28 / 1.30 rad/s (n 8);
  - Gold 1.34 / 1.41 (n 4);
  - arcade retail 0.94 / 0.97 (n 4).

  The 45 % gap in EMU-MEMTRACE was arcade mode. A 5-8 % gap remains (about 1-2 sd). Accel and brake are unchanged.
- **Clean crest start works.** Every descent starts:
  - placed at the lab's hill-top start (7972, 101.8, 44035), facing -x;
  - repaired to 5600 / 5600 armour and 4000 / 4000 chassis at the crest;
  - 0.0-0.03 m from the target in the read-back.

  Foot speed is now 52.6-57.7 m/s in both exes; the old approach gave 46-57.
- **T05 descents, simulation physics:**

  | exe | n | foot speed m/s | take-off m/s | airborne s | jump m | turned over | destroyed |
  |---|---|---|---|---|---|---|---|
  | retail 1.0 | 9 | 55.1 +- 1.8 | 48.4 +- 1.8 | 4.1 +- 1.1 | 154 +- 48 | 1 | 1 |
  | Gold | 6 | 56.9 +- 1.4 | 49.5 +- 0.9 | 4.1 +- 0.8 | 191 +- 36 | 0 | 0 |

  - **The distances overlap.** Retail runs 97-231 m, Gold 155-237 m.
  - **Retail's mean is pulled down by two short jumps** (97 / 99 m) that took off at 46 m/s.
  - **The difference is within the spread** at these n. Same controller only (v2): retail 154 +- 48 (n 9) vs Gold
    176 +- 25 (n 3).
- **The one destruction is the stock rollover rule.** Run 224110 took off at 46.1 m/s and fell short into the canyon
  (y 27 -> 3.8 at x 6772). It hit the far face down to 6.7 m/s, tumbled and came to rest inverted (up.y -0.99). It was
  destroyed (flags 0x80089221) 0.2 s after its rates dropped. That matches CheckImpact's gates (rates < pi/5,
  inverted). In arcade mode the same check flips the car upright, which is why no earlier retail run lost its car.
- **Step:** retail sim_dt p50 32.3 +- 0.8 ms in the descents (Gold 37.0), 1 physics step on 97-99 % of frames, up to
  4 steps on single slow frames (max sim_dt 124-194 ms, a few frames per run).

## 1. How the start is made

- **No mid-mission save exists.** Bookmarks hold the scene, not a pose. The start is made in memory after the T05
  bookmark loads and the opening is skipped.
- **I76DRV 2026-10-16c.** It is the first build that writes game memory: a separate
  `PROCESS_VM_WRITE` handle, used only by these two commands.
  - `place X Y Z HX HZ [MS]`: the lab trainer's TELEPORT + STOP from outside the game. For 600 ms, every 2 ms:
    rotation, position, and velocity / rates / speed = 0. Then it releases the car and reads it back.
  - `repair`: the trainer's `trn_repair`: armour / chassis copies and components at max.
- **Order per repeat:** load the route, place, repair, wait 1 s, `ent crest` (armour = maxima), descent. The first
  smoke run braked after the placement; the car rolled away at 1-3 m/s on the crest's slope, so that step was removed.
- **Controllers.**
  - v1: the lab's plain phys-suite rule, `drive 90000 25 30 8000 1 0`.
  - v2: look-ahead max(25 m, 0.8 s), 0.3 s yaw lead.

  Gold alternated v2 / v1 (3 each). Retail ran v2 only. Gold v1 vs v2 foot speeds: 57.4 +- 0.3 vs 56.3 +- 1.9.
- **Repeats.**
  - Gold: in-session (one boot, 6 descents via Abort Mission > Replay).
  - Retail: one descent per boot (`ref-t05clean1-retail`). The first retail loop lost its car on rep 1; the mission
    ended and Replay no longer applied. Reps 2-6 of that run started with a destroyed car and are excluded.

## 2. Per descent (simulation physics; arcade smoke run for comparison)

Columns:

- foot: speed at x 6900.
- take-off: speed on the last ramp frame.
- air: the longest airborne run past x 6900.
- pitch / roll: peak attitude while airborne and in the 3 s after landing.
- 0x200: frames with the just-landed flag past x 6900.

| run | exe | ctl | foot | take-off | air s | jump m | pitch deg | roll deg | 0x200 frames | outcome |
|---|---|---|---|---|---|---|---|---|---|---|
| 224110 | retail | v2 | 56.4 | 46.1 | 5.9 | 97 | 82 | 79 | 9 | **destroyed** (inverted, rollover rule) |
| 231444 (video) | retail | v2 | 56.6 | 49.7 | 3.4 | 161 | 16 | 2 | 16 | intact |
| 232247 | retail | v2 | 53.0 | 47.9 | 3.2 | 146 | 46 | 25 | 26 | intact |
| 232300 | retail | v2 | 57.3 | 50.9 | 4.8 | 231 | 57 | 50 | 25 | intact |
| 232446 | retail | v2 | 52.6 | 46.0 | 5.3 | 99 | 47 | 57 | 40 | intact |
| 233326 | retail | v2 | 56.6 | 47.8 | 2.9 | 132 | 63 | 1 | 25 | intact |
| 233938 | retail | v2 | 53.4 | 47.1 | 2.9 | 132 | 18 | 16 | 62 | intact |
| 234716 | retail | v2 | 54.7 | 49.7 | 4.8 | 224 | 58 | 51 | 6 | intact |
| 235353 | retail | v2 | 55.0 | 50.0 | 3.4 | 162 | 17 | 23 | 27 | intact |
| 230526 r1 | Gold | v2 | 54.1 | 50.5 | 4.3 | 204 | 35 | 25 | 29 | intact |
| 230526 r2 | Gold | v1 | 57.7 | 49.0 | 4.9 | 225 | 72 | 69 | 26 | intact |
| 230526 r3 | Gold | v2 | 57.4 | 49.0 | 3.3 | 156 | 26 | 21 | 18 | intact |
| 230526 r4 | Gold | v1 | 57.3 | 48.7 | 3.3 | 155 | 27 | 21 | 16 | intact |
| 230526 r5 | Gold | v2 | 57.4 | 50.7 | 3.4 | 166 | 16 | 4 | 1 | intact |
| 230526 r6 | Gold | v1 | 57.2 | 48.9 | 5.1 | 237 | 71 | 70 | 43 | intact |
| 223233 r1 | retail **arcade** | v2 | 54.5 | 49.3 | 5.0 | 233 | 88 | 86 | 47 | turned over, flipped back |
| 223233 r2 | retail **arcade** | v1 | 56.6 | 49.6 | 3.4 | 161 | 27 | 18 | 14 | turned over, flipped back |

- **Three outcomes, in both exes.**
  - Under 3.5 s airborne: lands at 132-166 m.
  - 4.3-5.1 s: lands at 204-237 m.
  - Retail only, the two take-offs at 46 m/s: 5.3-5.9 s airborne and only 97-99 m. These are falls into the canyon
    onto the far face.

  Take-off speed alone does not decide between the first two: 49.7 m/s gave 161 m and 224 m.
- **The 0x8000 wreck flag** appeared only in the destroyed run.
- **sim_dt per descent:** retail p50 31-33 ms, p95 37-40 ms; Gold p50 37 ms, p95 42-44 ms. Single frames reach
  124-194 ms (retail) and 51-131 ms (Gold).

## 3. Arcade vs simulation, retail melee (Instant Melee, in-session loops)

| metric | retail sim (n 8, 2 boots) | retail arcade (n 4, run 185645) | Gold (n 4) |
|---|---|---|---|
| fps (logger on) | 36.0 +- 1.4 | 37.5 +- 0.8 | 31.0 +- 0.4 |
| physics step, mean ms | 27.8 +- 1.0 | 26.6 +- 0.5 | 32.2 +- 0.4 |
| sim_dt p5 / p50 / p95 ms | 24.6 / 26.7 / 33.4 | 24 / 26.2 / 29.3 | 28.3 / 31 / 38.2 |
| 0-10 / 0-20 / 0-30 m/s, s | 1.06 / 2.76 / 5.65 | 1.06 / 2.79 / 5.57 | 1.06 / 2.73 / 5.44 |
| distance in 10 s, m | 268 +- 7 | 267 +- 11 | 274 +- 4 |
| brake distance, m | 84 +- 9 | 88 +- 3 | 89 +- 4 |
| **steady yaw R / L, rad/s** | **1.28 +- 0.03 / 1.30 +- 0.04** | 0.94 / 0.97 | 1.34 / 1.41 |
| roll / pitch reversals per s | 4.1 / 4.7 | 3.6 / 4.2 | 2.7 / 2.8 |

- **A/A.** Two sim boots, n 4 each: yaw R / L 1.29 / 1.31 (224135) and 1.28 / 1.29 (232325). fps 35.6 and 36.3.
- **Arcade did not change accel or brake** beyond the spread. It cut yaw by 27 % (fitted lateral limit; see
  RETAIL-HANDLING-DIFF.md).
- **Retail sim fps (36.0, n 8) is below the arcade boots (37.5, n 4).** That is about 1 sd. Not explained; host load
  was higher tonight, but guest-time fps should not depend on it.

## 4. Not done

- **Flat-road straights on retail** (0-max accel, brake from 40 m/s, coast-down) and the T06 ramp route (s7 item 5).
  Not run. The VM slots went to the arcade fix reruns. Another lane started `r166-t06` runs tonight.
- **Gold one-per-boot descents.** Gold used the in-session loop; retail used one boot per descent. EMU-MEMTRACE s3
  found that both agree.
- **Retail v1 controller.** Not run, so the retail vs Gold comparison with all runs mixes controllers. The
  same-controller row is in the summary.
- **More retail n.** The destruction rate (1 / 9 vs 0 / 6) needs more descents before it means anything.
- **Not mine:** run `20261016-224007-r166-t05clean-a-1` (lane emu-t05-clean, section 5) used the pre-fix script, so it is ARCADE. So were
  the ownlog-on run 223658 and the t05v2 runs 222447 / 222517 started earlier that evening (retail ones arcade; Gold
  valid).

## 5. Placed jumps at a fixed 56 m/s (lane emu-t05-clean, 2026-10-16/17 night)

The crest descents above still carry the descent controller: foot speed 52.6-57.7 m/s, and the car's line into the
ramp. To compare the exes with nothing else in the loop, the car was placed on the ramp's run-up with a speed.

- **Script:** `tools\par\scripts\ref-t05jump56[-1]-<exe>.txt`, generated by `tools\memtrace\gen_t05jump.py` (lab
  df772cc).
- **Placement:** I76DRV `place 7050 21.5 43910 -1 0 300 56`. The `SPEED` argument (I76DRV 2026-10-16c) is the lab
  trainer's TELEPORT with velocity: velocity, speed and 1/speed are written along the heading. That puts the car 150 m
  before the aaramp4 foot, on its centre line, at 56 m/s, as the lab phys-suite `canyonN` phase does.
- **Then:** `repair`, full throttle with the plain lab steering rule along z 43910 (phase `canyonD<k>`).
- **Read-back:** speed 56.02 m/s and lateral 0.00 m in every run. The car was 1.7-8.7 m down the road at the
  read-back because it was already moving.
- **Physics mode:** flag 0x10000 (arcade) was on 0 frames in all 14 jumps. Retail runs wrote the retail-layout DEF
  ("88 bytes written, 88 read back, identical").
- **Boots:**
  - retail: one jump per boot, n 7;
  - Gold: 7 jumps, 3 from a 4-repeat in-session loop and 4 from single boots. The loop stopped once the car was
    destroyed: Replay's `waitmem` timed out.

| per jump (mean +- sd) | retail 1.0 sim (n 7) | Gold (n 7) |
|---|---|---|
| take-off speed m/s | 51.6 +- 1.0 | 51.2 +- 1.3 |
| apex above take-off m | 10.7 +- 0.4 | 10.5 +- 0.5 |
| airborne s | 4.6 +- 0.5 | 5.2 +- 1.1 |
| jump distance m | 228 +- 28 (166-245) | 248 +- 48 (161-314) |
| landed on the far side (x < 6660) / on the far ramp's face (x ~6710, vy -19) | 6 / 1 | 6 / 1 |
| peak pitch / roll, airborne + 3 s, deg | 53 +- 18 / 47 +- 19 | 80 +- 8 / 67 +- 30 |
| turned over (up.y < -0.5) | 0 | 3 |
| **destroyed** (0x80000020; 0x8000 wreck flag with it) | **0 / 7** | **3 / 7** (x 6603, 6700, 6540) |
| sim_dt p50 / p95 ms | 30.2 / 42.8 | 33.4 / 43.7 |
| frames with 1 step | 97 % | 98 % |

- **The flight is the same.** Take-off speed, apex height and the far-side landing spot match: retail lands at
  x 6629-6648, Gold at 6627-6642 apart from two long ones. Each exe had one face landing out of 7.
- **What differs is after the take-off.**
  - Gold rotates more in the air and on landing: peak pitch 80 vs 53 deg. Pitch is not range-normalised; it
    saturates at 90.
  - Two Gold jumps flew on to 291 m and 314 m.
  - 3 of 7 Gold cars were destroyed:
    - one turned over on the far-side landing;
    - one on the face landing;
    - one at the end of the 314 m flight.
  - No retail car was destroyed.
- **Not significant at this n.** 0/7 vs 3/7 destroyed gives Fisher exact p = 0.19 (two-sided). It does not agree in
  direction with the crest descents (retail 1/9 vs Gold 0/6 there, the other way round), so the safe reading is: no
  exe difference shown.
- **Rate is a confounder:** retail steps about 30 ms, Gold about 33-37 ms at the same settings. ERA-ENVELOPE found
  the canyon kill rate grows with the physics step. The Gold vs retail survival gap, if it is real, may be the frame
  rate rather than the exe.
- **Foot speed (first frame past x 6900):** retail 55.2 +- 1.6, Gold 56.1 +- 1.2, from the same 56 m/s placement and
  full throttle. The 53-54 m/s values come from frames taken a frame after the foot (the car climbs the ramp at about
  1.7 m per frame). Take-off speed is the better input.

## 6. Retail ARCADE crest descents, n 8 (run 224007, before the DEF fix)

The emu-t05-clean lane's first crest loop: one boot, 8 descents via Replay, controllers alternating v2 / v1. The
retail exe had the Gold-layout DEF, so Arcade Phys. was on (flag 0x10000 in 100 % of frames). Kept as the arcade
reference: it is the mode every pre-fix retail number was measured in.

| | retail ARCADE crest (n 8) | retail sim crest (n 9, s.2) | Gold crest (n 6, s.2) |
|---|---|---|---|
| foot speed m/s | 56.7 +- 0.7 | 55.1 +- 1.8 | 56.9 +- 1.4 |
| take-off m/s | 48.4 +- 2.0 | 48.4 +- 1.8 | 49.5 +- 0.9 |
| jump m | 145 +- 46 (95-238) | 154 +- 48 | 191 +- 36 |
| turned over / destroyed | 2 / 0 (both flipped back) | 1 / 1 | 0 / 0 |

- **Repair check:** `ent crest` read 5600 / 5600 armour and 4000 / 4000 chassis in all 8 repeats.
- **Controller split:** v1 n 4, foot 56.9 +- 0.3; v2 n 4, foot 56.4 +- 0.9.
- **Distances:** the same trimodal outcomes as section 2, at 95 / 132-163 / 238 m. Two descents (reps 4 and 5) took
  6.2 s in the air for only 95 m: falls onto the far face.
- **Clip:** `results\par\20261016-224007-r166-t05clean-a-1\video.mp4` (all 8 descents, about 25 min, arcade mode; not
  in git). The simulation-mode clip is section 0's `retail-sim-p166-t05-clean-descent.mp4`.

## 7. Notes (emu-t05-clean lane)

- **Lane overlap:** this lane and another lane both worked this brief tonight. Sections 1-4 are the other lane's.
  Sections 5-6 and I76DRV `place` / `repair` / `SPEED` are this lane's. The other lane committed this lane's
  uncommitted `place` / `repair` code and `gen_t05clean.py` with its DEF fix (lab 0e2f16c).
- **VM cap slip (this lane too):** between 23:42 and 23:54 this lane's queue started 5 retail single-jump boots 2 min
  apart, and up to 3 of its VMs ran at once.
  - **Cause:** `python` is the WindowsApps launcher stub. It exits at once, so the Start-Process handle never showed a
    run as alive.
  - **Fix:** `work\t05clean\queue.ps1` now counts its own 86Box processes by run tag.
  - **Data:** guest-time numbers do not depend on host load. The runs are kept.
- **Flat-road and T06 (s7 item 5):** not run by this lane either. With `place SPEED` they need no route any more:
  - 0-max accel: place at rest on the T06 DRIVE strip (7935, 18, 42900), facing +z;
  - brake from 40 m/s: place there at 40 m/s and brake;
  - T06 ramp A: place 150 m before the foot at 38-44 m/s, as phys-suite did.

  `gen_t05jump.py` is the template.
