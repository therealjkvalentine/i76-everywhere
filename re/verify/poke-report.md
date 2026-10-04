# Poke report (verify/poke.py, VERIFICATION-PROGRAM.md 2.5 / 4.4)

Two sandbox sessions on 2026-10-02, both Instant Melee on `i76_pristine_fix.exe` (`--route melee`: t01 on i76.exe ends
45-60 s after the hand-over, far too short for A1 / A2 / set / B / reset / A3 x 14), telemetry proxy
`music-fix\Strlkup.dll` (v2), profile stock20, `tools\trainer\i76tune.py` for every write (read back, pristine bytes on reset).
Session 1 (`runs\poke61002-122128`, 12:21-12:33, 11,203 frames) ran all 14 expectations; its grader had three defects
(decel metric took collision frames, the power formula ignored the engine health factor, `step_count` is not a count -
see below), so it was **regraded** from its recorded windows (`poke.py --regrade`, `poke-report-session1.md`) and the 7
entries that needed a fresh car or a corrected probe were **re-run** in session 2 (`runs\poke61002-123953`,
12:39-12:52, 9,238 frames). Sandbox after both: STRLKUP.DLL md5 54f2de9d, no lock, no `.pretest`, every exe-scope entry
read back at its pristine value (manifest `exe_entries_reset_at_end: []`).

## Combined result (best evidence per expectation)

| # | expectation | tunable | set | grade | evidence (numbers in the session tables below) |
|---|---|---|---|---|---|
| 1 | gear_ratio_3rd_rpm | gear_ratio_3rd (.data 0x4f8650) | 0.67 -> 0.5 | **PASS** (s1) | rpm = 850 + 126.81 x R x v in 3rd: A1 / A2 / B / A3 all 100% within 5 rpm (714-frame windows), B on the 0.5 curve, A3 back on 0.67 |
| 2 | gear_ratio_1st_rpm | gear_ratio_1st (.data 0x4f8648) | 1.67 -> 2.5 | **PASS** (s2) | 1st-gear grounded frames are the 40-62 km/h stretch after the wheelspin (22-86 frames); 100% within 5 rpm at both ratios |
| 3 | idle_rpm_at_rest | idle_rpm (.rdata 0x4be2d0) | 1050 -> 1500 | **PASS** (s1) | rpm at rest in idle = x exactly; first live `.rdata` write through VirtualProtectEx (TUNING.md had it "not yet exercised") |
| 4 | geared_rpm_offset | geared_rpm_offset (.rdata 0x4be2d8) | -850 -> -1200 | **PASS** (s1) | rpm = -x + 126.81 x R[g] x v in gears 1-3 |
| 5 | upshift_1to2_speed | upshift_full_1to2 (.rdata 0x4be290) | 62 -> 40 km/h | **PASS of the corrected rule** (s2) | with the threshold at 40 the first 1st -> 2nd shift came at 60.1 km/h = the 2nd -> 1st kickdown speed (`wheel_rpm_x60`, dual-use 0x4be2b4). Effective upshift = max(threshold, kickdown); engine.md does not state the interaction. Baselines 61-68 km/h (wheelspin holds the gear) |
| 6 | brake_gain_decel | brake_accel_gain (.rdata 0x4bd1d8) | 8 -> 4 | **PASS** (s2) | median full-brake deceleration 13.2 / 14.7 (A/A) -> 8.5 (B), -5.5 m/s^2 beyond the 2.9 control band, A3 12.0 |
| 7 | brake_offline_strength_live_car | brake_offline_strength (.rdata 0x4bd144) | 2300 -> 1200 | **PASS (unchanged)** (s1) | brake_effective stayed 1.17888 to 6 digits (delta 0.000): the constant is consumed at vehicle creation, as engine.md says; the decel metric of s1 is void (collision frames, see session 1) |
| 8 | engine_power_curve | engine_power (eng+0x14, per car) | 193960 -> 387920 | **PASS** (s2) | drive_power = P x f x rpm(7000-rpm)/3500^2 on 168-172 frames per observation at both P (k at eng+0xc rewritten with it); 8-s top speed 25.8 / 29.8 -> 49.8 m/s (+20.9, band 12.5), A3 28.7 |
| 9 | health_frac_offset | health_frac_offset (.rdata 0x4bc634) | -28 -> -40 | **FINDING, degenerate PASS** (s2) | predicted 112 on an undamaged car, read 100 on all 40 frames: object_HealthFraction clamps its return to [0, 100] at 0x40b6f0 (0x4bc620 / 0x4bc61c), not in damage.md. With the clamp in the formula B == A; expectations.json now sets -20 (-> 92) for a real test |
| 10 | health_frac_span | health_frac_span (.rdata 0x4bc630) | 72 -> 50 | **PASS** (s2) | health_pct 100 -> 78 -> 100 on the undamaged car (28 + x x 1), 40 frames each, exact |
| 11 | substep_max_dt | substep_max_dt (.text imm 0x46385d) | 0.05 -> 0.025 | **INCONCLUSIVE (instrument)** (s1) | the write read back, `step_count` did not move: in stock mode the proxy computes floor(sim_dt x 20) + 1 itself (strlkproxy.c:2011) and only counts under I76_FIXED_STEP. Needs a counted substep field (physics_StepVehicle calls per frame) |
| 12 | radar_missile_turn_mid | radar_missile_turn_mid (.rdata 0x4bec34) | - | **INCONCLUSIVE** | no projectile field in i76tel.h and no radar missile on the sandbox car; needs per-step missile position / nose direction |
| 13 | gravity_air_fall | gravity_air (.text imm 0x43a6a2) | -9.8 -> -4.9 | **INCONCLUSIVE** (s1, s2) | 0-3 airborne frames per 10-s probe on the melee ground; needs the `jump` scenario |
| 14 | aero_drag_top_speed | aero_drag_scale (.rdata 0x4bd1b0) | -0.1 -> -0.05 | **INCONCLUSIVE** (s1) | 12-s top speed 38.2 / 36.0 (A/A) -> 35.2 (B): within the 4.3 band; the arena run is too short and too bumpy to reach terminal speed (34-38 m/s in every window), and an AI car was shooting the probe car |

Per expectation: PASS 9 (one degenerate, one of the corrected rule), INCONCLUSIVE 5, FAIL 0 after the findings are folded in.
As first graded (before the three grader fixes and the two findings): PASS 3, FAIL 2 (engine_power_curve, substep_max_dt in s1;
health_frac_offset, upshift_1to2_speed in s2), INCONCLUSIVE 9.

## What the game did that was not planned

- **The "0 AI drivers" click did not take** (`navigate_melee` logged `clicked 187 295`): one AI car fought the probe car in
  both sessions (s1: 343 player IMPACTs, 140 of them ordnance class 0x33, 496 explosions). Session 2 ended with the
  player destroyed at frame 9238 during the last expectation (gravity_air_fall: 0 frames in B and A3). The grading is
  per selected frame, so this mostly produced INCONCLUSIVEs and the s1 health failures (cores damaged by frame 7566,
  unscaled branch, `cores_intact` false). `--ai 0` needs its click re-checked against the current melee form.
- **Arena scenery stops the car**: 2 of 8 shuttling probes in s1 and 1 in s2 ended under 5 m/s (now detected as
  `STUCK`, retried once from home the other way).
- **Clean quit exits with code 3221225477 (0xC0000005)** on i76_pristine_fix.exe after WM_CLOSE in both sessions (the
  t01 runs on i76.exe exit 0); the proxy was restored and the lock removed regardless.
- The `drive_to` steer-sign heuristic flipped repeatedly on the first take-damage run (sign convention was backwards:
  D raises `atan2(fwd.x, fwd.z)`); fixed before the poke sessions, which still show flips on hits (`sign flipped` lines
  in the logs) but arrived.

## Session 2 (runs/poke/20261002-123953, 7 expectations re-run on a fresh car; regraded)

**Regraded 2026-10-02 12:55** from the recorded run (its observation windows, telemetry and set / reset read-backs) with the current expectations.json and grader; the game was not run again for this table.

Generated 2026-10-02 12:55. Run: `C:\Users\james\i76-map\verify\runs\poke\20261002-123953` (route melee, exe i76_pristine_fix.exe md5 58d9dec0, profile stock20, proxy 9a081000). Telemetry frames 9238, events 1222. Sandbox restore: STRLKUP.DLL md5 54f2de9d after the run; quit: clean exit 0.3s after WM_CLOSE (code 3221225477); errors: []; warnings: [].

Each expectation: observe (A1), observe (A2) with nothing changed (the A/A control), set the tunable with i76tune (read back), observe (B), reset (pristine bytes / saved live value, read back), observe (A3). `formula` grades PASS when >= 98% of the frames that satisfy `when` are within tolerance in A1, A2 (default x), B (set x) and A3 (default x); increase / decrease / unchanged compare B with the A mean beyond max(2 x |A1 - A2|, min_delta). INCONCLUSIVE when no field can observe the change, the probe produced too few frames, the A/A pair disagrees, or the write did not read back.

## Results

| # | expectation | tunable (scope, addr) | default -> set | relation | observable | A1 | A2 | B | A3 | grade | why |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | gear_ratio_1st_rpm | gear_ratio_1st (exe, 0x4f8648) | 1.67 -> 2.5 | formula | rpm | ok 22/22 err<=0.0862 | ok 20/20 err<=0.0766 | ok 86/86 err<=0.1242 | ok 26/26 err<=0.0874 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 2 | upshift_1to2_speed | upshift_full_1to2 (exe, 0x4be290) | 62 -> 40 | formula | shift_speed_kmh | ok 67.84 vs 62 | ok 62.58 vs 62 | ok 60.1 vs 60 | ok 62.48 vs 62 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 3 | brake_gain_decel | brake_accel_gain (exe, 0x4bd1d8) | 8 -> 4 | decrease | decel | 13.22 | 14.68 | 8.463 | 12 | **PASS** | B moved -5.485 (decrease) beyond the control band 2.910 |
| 4 | engine_power_curve | engine_power (engine, 0x14) | 1.94e+05 -> 3.879e+05 | formula | drive_power | ok 169/169 err<=0.5934 | ok 215/215 err<=0.5199 | ok 173/173 err<=0.9768 | ok 180/180 err<=0.6998 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 4 | engine_power_curve | engine_power (engine, 0x14) | 1.94e+05 -> 3.879e+05 | increase | max(speed) | 25.85 | 32.1 | 49.85 | 35.08 | **PASS** | B moved 20.871 (increase) beyond the control band 12.511 |
| 5 | health_frac_offset | health_frac_offset (exe, 0x4bc634) | -28 -> -40 | formula | health_pct | ok 41/41 err<=0 | ok 41/41 err<=0 | ok 41/41 err<=0 | ok 41/41 err<=0 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 6 | health_frac_span | health_frac_span (exe, 0x4bc630) | 72 -> 50 | formula | health_pct | ok 41/41 err<=0 | ok 41/41 err<=0 | ok 41/41 err<=0 | ok 41/41 err<=0 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 7 | gravity_air_fall | gravity_air (exe, 0x43a6a2) | -9.8 -> -4.9 | formula | accel_1 | n/a (fewer than 5 frames satisfy `when`) | n/a (fewer than 5 frames satisfy `when`) | n/a (fewer than 5 frames satisfy `when`) | n/a (fewer than 5 frames satisfy `when`) | **INCONCLUSIVE** | A1: fewer than 5 frames satisfy `when`; A2: fewer than 5 frames satisfy `when`; B: fewer than 5 frames satisfy `when` |

Per expectation: INCONCLUSIVE 1, PASS 6 of 7.

## Details

### 1. gear_ratio_1st_rpm

- tunable `gear_ratio_1st` (exe scope, 0x4f8648; spec engine.md#Model); live before 1.67, set 2.5 (read back 2.5, ok), reset read back 1.67 (ok).
- probe {"kind": "accelerate", "s": 8}; frames per observation: A1 169, A2 168, B 168, A3 168; t = 29.8..95.8 s.
- note: A full-throttle start spins the wheels (skid flag 0x2) and the gear holds in 1 (idle) until ~40 km/h (first session), so 1st-gear grounded frames are the 40 -> 62 km/h stretch: about 20-35 frames per probe.
- `formula` rpm when `gear==2 and speed>2 and engine_on and not skid and not airborne and gear_lever==3`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 22, "matched": 22, "rate": 1.0, "max_err": 0.0862, "median_err": 0.0579}
  - A2: {"ok": true, "considered": 20, "matched": 20, "rate": 1.0, "max_err": 0.0766, "median_err": 0.0656}
  - B: {"ok": true, "considered": 86, "matched": 86, "rate": 1.0, "max_err": 0.1242, "median_err": 0.0976}
  - A3: {"ok": true, "considered": 26, "matched": 26, "rate": 1.0, "max_err": 0.0874, "median_err": 0.0738}

### 2. upshift_1to2_speed

- tunable `upshift_full_1to2` (exe scope, 0x4be290; spec engine.md#Model (Automatic gearbox)); live before 62, set 40 (read back 40, ok), reset read back 62 (ok).
- probe {"kind": "accelerate", "s": 8}; frames per observation: A1 168, A2 168, B 168, A3 168; t = 95.8..175.7 s.
- note: The 1st -> 2nd upshift at full throttle. Session 2: threshold set to 40 km/h, the first 2 -> 3 (1st -> 2nd) change still came at 60.1 km/h = wheel_rpm_x60, the full-throttle 2nd -> 1st kickdown speed (dual-use 0x4be2b4; the kickdown fires below it, so a 2nd gear entered under 60 km/h is left again within the frame). The effective upshift speed is therefore max(threshold, kickdown) - engine.md states the two thresholds but not this interaction. The baseline shifts read 61-68 km/h (wheelspin start holds the gear; A/A spread), so the test is sharp only when the threshold is moved ABOVE 62 or the kickdown is lowered with it.
- `formula` shift_speed_kmh : **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 1, "value": 67.845, "expected": 62.0, "err": 5.845}
  - A2: {"ok": true, "considered": 1, "value": 62.576, "expected": 62.0, "err": 0.576}
  - B: {"ok": true, "considered": 1, "value": 60.096, "expected": 60.0, "err": 0.096}
  - A3: {"ok": true, "considered": 1, "value": 62.479, "expected": 62.0, "err": 0.479}

### 3. brake_gain_decel

- tunable `brake_accel_gain` (exe scope, 0x4bd1d8; spec physics.md#Constants (a = brake+0x10 x throttle x 8)); live before 8, set 4 (read back 4, ok), reset read back 8 (ok).
- probe {"kind": "brake", "s": 6, "brake_s": 8}; frames per observation: A1 58, A2 48, B 74, A3 48; t = 175.7..252.4 s.
- note: a = brake+0x10 x throttle x 8, traction-capped: 2300/1951 x 8 = 9.4 m/s^2 stock, 4.7 at gain 4. The decel metric is the median over consecutive full-brake frames with |a| < 25 (arena hits excluded).
- `decrease` decel when `throttle<-0.9 and speed>3 and not airborne`: **PASS** - B moved -5.485 (decrease) beyond the control band 2.910
  - A1: 13.219930875573034
  - A2: 14.675025601638534
  - B: 8.462903225804798
  - A3: 12.003225806449313

### 4. engine_power_curve

- tunable `engine_power` (engine scope, 0x14; spec engine.md#Model (Power)); live before 1.94e+05, set 3.879e+05 (read back 3.879e+05, ok), reset read back 1.94e+05 (ok).
- probe {"kind": "accelerate", "s": 8}; frames per observation: A1 168, A2 214, B 172, A3 179; t = 252.4..352.9 s.
- note: Per-car entry (eng+0x14; i76tune rewrites k = P/3500^2 at eng+0xc with it). The formula uses the telemetry's own engine_power and the engine health factor f = max(hp/max, 0.4) (eng+0x18, rewritten on engine damage events: the first session's car took a 1200 -> 1194 engine hit and drive_power followed at 0.995 x the curve from that frame), so the per-frame test is 'eng+0x10 follows eng+0x14 live'; the max-speed metric is the behavioural check.
- `formula` drive_power when `engine_on and rpm>500 and rpm<6900`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 169, "matched": 169, "rate": 1.0, "max_err": 0.5934, "median_err": 0.248}
  - A2: {"ok": true, "considered": 215, "matched": 215, "rate": 1.0, "max_err": 0.5199, "median_err": 0.1637}
  - B: {"ok": true, "considered": 173, "matched": 173, "rate": 1.0, "max_err": 0.9768, "median_err": 0.2985}
  - A3: {"ok": true, "considered": 180, "matched": 180, "rate": 1.0, "max_err": 0.6998, "median_err": 0.2044}
- `increase` speed : **PASS** - B moved 20.871 (increase) beyond the control band 12.511
  - A1: 25.8468
  - A2: 32.1025
  - B: 49.8461
  - A3: 35.0809

### 5. health_frac_offset

- tunable `health_frac_offset` (exe scope, 0x4bc634; spec damage.md#Damage visuals (HealthFraction 28 + 72 r)); live before -28, set -40 (read back -40, ok), reset read back -28 (ok).
- probe {"kind": "idle", "s": 2}; frames per observation: A1 40, A2 41, B 40, A3 40; t = 0.7..15.3 s.
- note: object_HealthFraction clamps its return to [0, 100] at 0x40b6f0 (0x4bc620 / 0x4bc61c), which damage.md does not state: session 2 set the offset to -40 (-> 112 unclamped) on an undamaged car and read 100 on every frame. With the clamp in the formula that observation is a degenerate PASS (B == A); the value is now -20 (-> 92, below the clamp) so the next session sees the offset itself.
- `formula` health_pct when `cores_intact`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 41, "matched": 41, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - A2: {"ok": true, "considered": 41, "matched": 41, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - B: {"ok": true, "considered": 41, "matched": 41, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - A3: {"ok": true, "considered": 41, "matched": 41, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}

### 6. health_frac_span

- tunable `health_frac_span` (exe scope, 0x4bc630; spec damage.md#Damage visuals (HealthFraction 28 + 72 r)); live before 72, set 50 (read back 50, ok), reset read back 72 (ok).
- probe {"kind": "idle", "s": 2}; frames per observation: A1 40, A2 40, B 40, A3 40; t = 15.3..29.8 s.
- note: With an undamaged car side_ratio = 1 and the value is 28 + x whatever r does; the offset / span split is only separable once a side is damaged (the take-damage oracle covers that).
- `formula` health_pct when `cores_intact`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 41, "matched": 41, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - A2: {"ok": true, "considered": 41, "matched": 41, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - B: {"ok": true, "considered": 41, "matched": 41, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - A3: {"ok": true, "considered": 41, "matched": 41, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}

### 7. gravity_air_fall

- tunable `gravity_air` (exe scope, 0x43a6a2; spec physics.md#Constants (airborne gravity imm, phys_Integrate while flag 4)); live before -9.8, set -4.9 (read back -4.9, ok), reset read back -9.8 (ok).
- probe {"kind": "accelerate", "s": 10}; frames per observation: A1 213, A2 208, B 0, A3 0; t = 352.9..633.0 s.
- note: Needs airborne frames (flag 0x4); a straight run over the melee ground gives a few per probe at best. INCONCLUSIVE when fewer than min_frames: the `jump` scenario is the right vehicle for this one.
- `formula` accel_1 when `airborne and speed>5`: **INCONCLUSIVE** - A1: fewer than 5 frames satisfy `when`; A2: fewer than 5 frames satisfy `when`; B: fewer than 5 frames satisfy `when`
  - A1: {"ok": null, "considered": 3, "note": "fewer than 5 frames satisfy `when`"}
  - A2: {"ok": null, "considered": 0, "note": "fewer than 5 frames satisfy `when`"}
  - B: {"ok": null, "considered": 0, "note": "fewer than 5 frames satisfy `when`"}
  - A3: {"ok": null, "considered": 0, "note": "fewer than 5 frames satisfy `when`"}


## Session 1

All 14 expectations, regraded: `verify/poke-report-session1.md` (run `runs/poke/20261002-122128`).
