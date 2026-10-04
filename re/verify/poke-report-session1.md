# Poke report (verify/poke.py, VERIFICATION-PROGRAM.md 2.5 / 4.4)

**Regraded 2026-10-02 12:55** from the recorded run (its observation windows, telemetry and set / reset read-backs) with the current expectations.json and grader; the game was not run again for this table.

Generated 2026-10-02 12:55. Run: `C:\Users\james\i76-map\verify\runs\poke\20261002-122128` (route melee, exe i76_pristine_fix.exe md5 58d9dec0, profile stock20, proxy 9a081000). Telemetry frames 12721, events 1165. Sandbox restore: STRLKUP.DLL md5 54f2de9d after the run; quit: clean exit 0.5s after WM_CLOSE (code 3221225477); errors: []; warnings: [].

Each expectation: observe (A1), observe (A2) with nothing changed (the A/A control), set the tunable with i76tune (read back), observe (B), reset (pristine bytes / saved live value, read back), observe (A3). `formula` grades PASS when >= 98% of the frames that satisfy `when` are within tolerance in A1, A2 (default x), B (set x) and A3 (default x); increase / decrease / unchanged compare B with the A mean beyond max(2 x |A1 - A2|, min_delta). INCONCLUSIVE when no field can observe the change, the probe produced too few frames, the A/A pair disagrees, or the write did not read back.

## Results

| # | expectation | tunable (scope, addr) | default -> set | relation | observable | A1 | A2 | B | A3 | grade | why |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | gear_ratio_3rd_rpm | gear_ratio_3rd (exe, 0x4f8650) | 0.67 -> 0.5 | formula | rpm | ok 44/44 err<=0.0651 | ok 67/67 err<=0.072 | ok 37/37 err<=0.0492 | ok 34/34 err<=0.0664 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 2 | gear_ratio_1st_rpm | gear_ratio_1st (exe, 0x4f8648) | 1.67 -> 2.5 | formula | rpm | n/a (fewer than 10 frames satisfy `when`) | ok 20/20 err<=0.0758 | ok 34/34 err<=0.1261 | ok 20/20 err<=0.0803 | **INCONCLUSIVE** | A1: fewer than 10 frames satisfy `when` |
| 3 | idle_rpm_at_rest | idle_rpm (exe, 0x4be2d0) | 1050 -> 1500 | formula | rpm | ok 42/42 err<=0 | ok 44/44 err<=0 | ok 43/43 err<=0 | ok 43/43 err<=0 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 4 | geared_rpm_offset | geared_rpm_offset (exe, 0x4be2d8) | -850 -> -1200 | formula | rpm | ok 120/120 err<=0.0818 | ok 127/127 err<=0.0865 | ok 38/38 err<=0.0779 | ok 52/52 err<=0.0793 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 5 | upshift_1to2_speed | upshift_full_1to2 (exe, 0x4be290) | 62 -> 40 | formula | shift_speed_kmh | n/a (metric undefined) | ok 62.82 vs 62 | ok 60.36 vs 60 | ok 62.67 vs 62 | **INCONCLUSIVE** | A1: metric undefined |
| 6 | brake_gain_decel | brake_accel_gain (exe, 0x4bd1d8) | 8 -> 4 | decrease | decel | - | - | 6.444 | - | **INCONCLUSIVE** | metric undefined on an observation (A1 None, A2 None, B 6.444243951614256) |
| 7 | brake_offline_strength_live_car | brake_offline_strength (exe, 0x4bd144) | 2300 -> 1200 | unchanged | decel | - | 18.58 | 7.4 | 13.38 | **INCONCLUSIVE** | metric undefined on an observation (A1 None, A2 18.581904761891483, B 7.40036866359446) |
| 7 | brake_offline_strength_live_car | brake_offline_strength (exe, 0x4bd144) | 2300 -> 1200 | unchanged | mean(brake_effective) | 1.533 | 1.533 | 1.533 | 1.533 | **PASS** | B within the control band (/delta/ 0.000 <= 0.001) |
| 8 | engine_power_curve | engine_power (engine, 0x14) | 1.94e+05 -> 3.879e+05 | formula | drive_power | ok 172/172 err<=0.7759 | ok 169/169 err<=0.7001 | ok 169/169 err<=1.03 | ok 169/169 err<=0.7001 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |
| 8 | engine_power_curve | engine_power (engine, 0x14) | 1.94e+05 -> 3.879e+05 | increase | max(speed) | 26.1 | 35.3 | 43.44 | 34.9 | **INCONCLUSIVE** | B moved 12.738, within the control band 18.386 (A1 26.104, A2 35.297) |
| 9 | health_frac_offset | health_frac_offset (exe, 0x4bc634) | -28 -> -40 | formula | health_pct | n/a (fewer than 20 frames satisfy `when`) | n/a (fewer than 20 frames satisfy `when`) | n/a (fewer than 20 frames satisfy `when`) | n/a (fewer than 20 frames satisfy `when`) | **INCONCLUSIVE** | A1: fewer than 20 frames satisfy `when`; A2: fewer than 20 frames satisfy `when`; B: fewer than 20 frames satisfy `when` |
| 10 | health_frac_span | health_frac_span (exe, 0x4bc630) | 72 -> 50 | formula | health_pct | n/a (fewer than 20 frames satisfy `when`) | n/a (fewer than 20 frames satisfy `when`) | n/a (fewer than 20 frames satisfy `when`) | n/a (fewer than 20 frames satisfy `when`) | **INCONCLUSIVE** | A1: fewer than 20 frames satisfy `when`; A2: fewer than 20 frames satisfy `when`; B: fewer than 20 frames satisfy `when` |
| 11 | substep_max_dt | substep_max_dt (exe, 0x46385d) | 0.05 -> 0.025 | inconclusive | - | - | - | - | - | **INCONCLUSIVE** | not observable: needs a COUNTED substep field: in stock mode the proxy computes step_count = floor(sim_dt x 20) + 1 itself (music-fix/strlkproxy.c:2011, 'simclock_StepperBegin: floor(dt x 20) + 1'), so the field cannot see a changed max step; only I76_FIXED_STEP counts real substeps (g_step_acc). The first session set 0.025 (read back) and step_count stayed on the stock formula: an instrument artefact, not a game result. A hook counting physics_StepVehicle calls per frame (the census's per_substep series) is the observable. |
| 12 | radar_missile_turn_mid | radar_missile_turn_mid (exe, 0x4bec34) | None -> None | inconclusive | - | - | - | - | - | **INCONCLUSIVE** | not observable: needs per-step radar-missile state (position / nose direction of the player's missile, or an I76TEL_EV_PROJECTILE_STEP event): i76tel.h has no projectile fields, and the sandbox Piranha carries no radar missile launcher |
| 13 | gravity_air_fall | gravity_air (exe, 0x43a6a2) | -9.8 -> -4.9 | formula | accel_1 | n/a (fewer than 5 frames satisfy `when`) | FAIL 0/30 err<=9.8 | n/a (fewer than 5 frames satisfy `when`) | n/a (fewer than 5 frames satisfy `when`) | **INCONCLUSIVE** | A1: fewer than 5 frames satisfy `when`; B: fewer than 5 frames satisfy `when` |
| 14 | aero_drag_top_speed | aero_drag_scale (exe, 0x4bd1b0) | -0.1 -> -0.05 | increase | max(speed) | 38.2 | 36.03 | 34.14 | 11.15 | **INCONCLUSIVE** | B moved -2.977, within the control band 4.328 (A1 38.197, A2 36.033) |

Per expectation: INCONCLUSIVE 11, PASS 3 of 14.

## Details

### 1. gear_ratio_3rd_rpm

- tunable `gear_ratio_3rd` (exe scope, 0x4f8650; spec engine.md#Model); live before 0.67, set 0.5 (read back 0.5, ok), reset read back 0.67 (ok).
- probe {"kind": "accelerate", "s": 12}; frames per observation: A1 254, A2 248, B 249, A3 248; t = 0.8..72.2 s.
- `formula` rpm when `gear==4 and speed>15 and engine_on and not skid and not airborne and gear_lever==3`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 44, "matched": 44, "rate": 1.0, "max_err": 0.0651, "median_err": 0.0561}
  - A2: {"ok": true, "considered": 67, "matched": 67, "rate": 1.0, "max_err": 0.072, "median_err": 0.0587}
  - B: {"ok": true, "considered": 37, "matched": 37, "rate": 1.0, "max_err": 0.0492, "median_err": 0.0418}
  - A3: {"ok": true, "considered": 34, "matched": 34, "rate": 1.0, "max_err": 0.0664, "median_err": 0.056}

### 2. gear_ratio_1st_rpm

- tunable `gear_ratio_1st` (exe scope, 0x4f8648; spec engine.md#Model); live before 1.67, set 2.5 (read back 2.5, ok), reset read back 1.67 (ok).
- probe {"kind": "accelerate", "s": 8}; frames per observation: A1 168, A2 168, B 168, A3 169; t = 72.2..129.4 s.
- note: A full-throttle start spins the wheels (skid flag 0x2) and the gear holds in 1 (idle) until ~40 km/h (first session), so 1st-gear grounded frames are the 40 -> 62 km/h stretch: about 20-35 frames per probe.
- `formula` rpm when `gear==2 and speed>2 and engine_on and not skid and not airborne and gear_lever==3`: **INCONCLUSIVE** - A1: fewer than 10 frames satisfy `when`
  - A1: {"ok": null, "considered": 0, "note": "fewer than 10 frames satisfy `when`"}
  - A2: {"ok": true, "considered": 20, "matched": 20, "rate": 1.0, "max_err": 0.0758, "median_err": 0.0652}
  - B: {"ok": true, "considered": 34, "matched": 34, "rate": 1.0, "max_err": 0.1261, "median_err": 0.0943}
  - A3: {"ok": true, "considered": 20, "matched": 20, "rate": 1.0, "max_err": 0.0803, "median_err": 0.0652}

### 3. idle_rpm_at_rest

- tunable `idle_rpm` (exe scope, 0x4be2d0; spec engine.md#Model); live before 1050, set 1500 (read back 1500, ok), reset read back 1050 (ok).
- probe {"kind": "idle", "s": 3}; frames per observation: A1 60, A2 60, B 60, A3 60; t = 129.4..148.4 s.
- `formula` rpm when `gear==1 and speed<0.5 and engine_on and not skid`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 42, "matched": 42, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - A2: {"ok": true, "considered": 44, "matched": 44, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - B: {"ok": true, "considered": 43, "matched": 43, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}
  - A3: {"ok": true, "considered": 43, "matched": 43, "rate": 1.0, "max_err": 0.0, "median_err": 0.0}

### 4. geared_rpm_offset

- tunable `geared_rpm_offset` (exe scope, 0x4be2d8; spec engine.md#Model); live before -850, set -1200 (read back -1200, ok), reset read back -850 (ok).
- probe {"kind": "accelerate", "s": 8}; frames per observation: A1 169, A2 177, B 169, A3 168; t = 148.4..205.6 s.
- `formula` rpm when `gear in (2,3,4) and speed>2 and engine_on and not skid and not airborne and gear_lever==3`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 120, "matched": 120, "rate": 1.0, "max_err": 0.0818, "median_err": 0.0577}
  - A2: {"ok": true, "considered": 127, "matched": 127, "rate": 1.0, "max_err": 0.0865, "median_err": 0.0577}
  - B: {"ok": true, "considered": 38, "matched": 38, "rate": 1.0, "max_err": 0.0779, "median_err": 0.0564}
  - A3: {"ok": true, "considered": 52, "matched": 52, "rate": 1.0, "max_err": 0.0793, "median_err": 0.0524}

### 5. upshift_1to2_speed

- tunable `upshift_full_1to2` (exe scope, 0x4be290; spec engine.md#Model (Automatic gearbox)); live before 62, set 40 (read back 40, ok), reset read back 62 (ok).
- probe {"kind": "accelerate", "s": 8}; frames per observation: A1 167, A2 167, B 169, A3 168; t = 205.6..267.3 s.
- note: The 1st -> 2nd upshift at full throttle. Session 2: threshold set to 40 km/h, the first 2 -> 3 (1st -> 2nd) change still came at 60.1 km/h = wheel_rpm_x60, the full-throttle 2nd -> 1st kickdown speed (dual-use 0x4be2b4; the kickdown fires below it, so a 2nd gear entered under 60 km/h is left again within the frame). The effective upshift speed is therefore max(threshold, kickdown) - engine.md states the two thresholds but not this interaction. The baseline shifts read 61-68 km/h (wheelspin start holds the gear; A/A spread), so the test is sharp only when the threshold is moved ABOVE 62 or the kickdown is lowered with it.
- `formula` shift_speed_kmh : **INCONCLUSIVE** - A1: metric undefined
  - A1: {"ok": null, "considered": 0, "value": null, "expected": null, "note": "metric undefined"}
  - A2: {"ok": true, "considered": 1, "value": 62.823, "expected": 62.0, "err": 0.823}
  - B: {"ok": true, "considered": 1, "value": 60.358, "expected": 60.0, "err": 0.358}
  - A3: {"ok": true, "considered": 1, "value": 62.675, "expected": 62.0, "err": 0.675}

### 6. brake_gain_decel

- tunable `brake_accel_gain` (exe scope, 0x4bd1d8; spec physics.md#Constants (a = brake+0x10 x throttle x 8)); live before 8, set 4 (read back 4, ok), reset read back 8 (ok).
- probe {"kind": "brake", "s": 6, "brake_s": 8}; frames per observation: A1 15, A2 20, B 72, A3 20; t = 267.3..322.1 s.
- note: a = brake+0x10 x throttle x 8, traction-capped: 2300/1951 x 8 = 9.4 m/s^2 stock, 4.7 at gain 4. The decel metric is the median over consecutive full-brake frames with |a| < 25 (arena hits excluded).
- `decrease` decel when `throttle<-0.9 and speed>3 and not airborne`: **INCONCLUSIVE** - metric undefined on an observation (A1 None, A2 None, B 6.444243951614256)
  - B: 6.444243951614256

### 7. brake_offline_strength_live_car

- tunable `brake_offline_strength` (exe scope, 0x4bd144; spec engine.md#Model (Brakes: 2300/m applied at vehicle creation)); live before 2300, set 1200 (read back 1200, ok), reset read back 2300 (ok).
- probe {"kind": "brake", "s": 6, "brake_s": 8}; frames per observation: A1 24, A2 33, B 99, A3 46; t = 322.1..378.6 s.
- note: The constant is consumed by physics_InitEntity at vehicle creation: the live car's brake+0x10 and its deceleration must NOT move. A PASS here is a pass of the spec's creation-time claim; brake_strength (component scope) is the live knob.
- `unchanged` decel when `throttle<-0.9 and speed>3 and not airborne`: **INCONCLUSIVE** - metric undefined on an observation (A1 None, A2 18.581904761891483, B 7.40036866359446)
  - A2: 18.581904761891483
  - B: 7.40036866359446
  - A3: 13.384516129029704
- `unchanged` brake_effective when `player_present==1`: **PASS** - B within the control band (|delta| 0.000 <= 0.001)
  - A1: 1.53255
  - A2: 1.53255
  - B: 1.53255
  - A3: 1.53255

### 8. engine_power_curve

- tunable `engine_power` (engine scope, 0x14; spec engine.md#Model (Power)); live before 1.94e+05, set 3.879e+05 (read back 3.879e+05, ok), reset read back 1.94e+05 (ok).
- probe {"kind": "accelerate", "s": 8}; frames per observation: A1 171, A2 168, B 168, A3 167; t = 378.6..431.2 s.
- note: Per-car entry (eng+0x14; i76tune rewrites k = P/3500^2 at eng+0xc with it). The formula uses the telemetry's own engine_power and the engine health factor f = max(hp/max, 0.4) (eng+0x18, rewritten on engine damage events: the first session's car took a 1200 -> 1194 engine hit and drive_power followed at 0.995 x the curve from that frame), so the per-frame test is 'eng+0x10 follows eng+0x14 live'; the max-speed metric is the behavioural check.
- `formula` drive_power when `engine_on and rpm>500 and rpm<6900`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 172, "matched": 172, "rate": 1.0, "max_err": 0.7759, "median_err": 0.2087}
  - A2: {"ok": true, "considered": 169, "matched": 169, "rate": 1.0, "max_err": 0.7001, "median_err": 0.2004}
  - B: {"ok": true, "considered": 169, "matched": 169, "rate": 1.0, "max_err": 1.03, "median_err": 0.2671}
  - A3: {"ok": true, "considered": 169, "matched": 169, "rate": 1.0, "max_err": 0.7001, "median_err": 0.2033}
- `increase` speed : **INCONCLUSIVE** - B moved 12.738, within the control band 18.386 (A1 26.104, A2 35.297)
  - A1: 26.1042
  - A2: 35.2972
  - B: 43.4391
  - A3: 34.8962

### 9. health_frac_offset

- tunable `health_frac_offset` (exe scope, 0x4bc634; spec damage.md#Damage visuals (HealthFraction 28 + 72 r)); live before -28, set -40 (read back -40, ok), reset read back -28 (ok).
- probe {"kind": "idle", "s": 2}; frames per observation: A1 40, A2 41, B 40, A3 40; t = 431.2..448.7 s.
- note: object_HealthFraction clamps its return to [0, 100] at 0x40b6f0 (0x4bc620 / 0x4bc61c), which damage.md does not state: session 2 set the offset to -40 (-> 112 unclamped) on an undamaged car and read 100 on every frame. With the clamp in the formula that observation is a degenerate PASS (B == A); the value is now -20 (-> 92, below the clamp) so the next session sees the offset itself.
- `formula` health_pct when `cores_intact`: **INCONCLUSIVE** - A1: fewer than 20 frames satisfy `when`; A2: fewer than 20 frames satisfy `when`; B: fewer than 20 frames satisfy `when`
  - A1: {"ok": null, "considered": 0, "note": "fewer than 20 frames satisfy `when`"}
  - A2: {"ok": null, "considered": 0, "note": "fewer than 20 frames satisfy `when`"}
  - B: {"ok": null, "considered": 0, "note": "fewer than 20 frames satisfy `when`"}
  - A3: {"ok": null, "considered": 0, "note": "fewer than 20 frames satisfy `when`"}

### 10. health_frac_span

- tunable `health_frac_span` (exe scope, 0x4bc630; spec damage.md#Damage visuals (HealthFraction 28 + 72 r)); live before 72, set 50 (read back 50, ok), reset read back 72 (ok).
- probe {"kind": "idle", "s": 2}; frames per observation: A1 41, A2 40, B 40, A3 40; t = 448.7..463.3 s.
- note: With an undamaged car side_ratio = 1 and the value is 28 + x whatever r does; the offset / span split is only separable once a side is damaged (the take-damage oracle covers that).
- `formula` health_pct when `cores_intact`: **INCONCLUSIVE** - A1: fewer than 20 frames satisfy `when`; A2: fewer than 20 frames satisfy `when`; B: fewer than 20 frames satisfy `when`
  - A1: {"ok": null, "considered": 0, "note": "fewer than 20 frames satisfy `when`"}
  - A2: {"ok": null, "considered": 0, "note": "fewer than 20 frames satisfy `when`"}
  - B: {"ok": null, "considered": 0, "note": "fewer than 20 frames satisfy `when`"}
  - A3: {"ok": null, "considered": 0, "note": "fewer than 20 frames satisfy `when`"}

### 11. substep_max_dt

- tunable `substep_max_dt` (exe scope, 0x46385d; spec physics.md#Contract (stepper rate 20, max step 0.05 s)); live before 0.05, set 0.025 (read back 0.025, ok), reset read back 0.05 (ok).
- probe {"kind": "idle", "s": 3}; frames per observation: A1 60, A2 60, B 59, A3 60; t = 463.3..481.9 s.
- note: Instruction immediate (push 0.05 at 0x46385c in entity_TickVehicle). Also means the step_count oracle is tautological in stock mode (see oracles/REPORT.md).
- `inconclusive`  : **INCONCLUSIVE** - not observable: needs a COUNTED substep field: in stock mode the proxy computes step_count = floor(sim_dt x 20) + 1 itself (music-fix/strlkproxy.c:2011, 'simclock_StepperBegin: floor(dt x 20) + 1'), so the field cannot see a changed max step; only I76_FIXED_STEP counts real substeps (g_step_acc). The first session set 0.025 (read back) and step_count stayed on the stock formula: an instrument artefact, not a game result. A hook counting physics_StepVehicle calls per frame (the census's per_substep series) is the observable.

### 12. radar_missile_turn_mid

- tunable `radar_missile_turn_mid` (exe scope, 0x4bec34; spec weapons.md#Projectile types); live before None, set None (read back None, not applied), reset read back None (FAILED).
- probe {"kind": "none"}; frames per observation: A1 None, A2 None, B None, A3 None; t = 481.9..None s.
- `inconclusive`  : **INCONCLUSIVE** - not observable: needs per-step radar-missile state (position / nose direction of the player's missile, or an I76TEL_EV_PROJECTILE_STEP event): i76tel.h has no projectile fields, and the sandbox Piranha carries no radar missile launcher

### 13. gravity_air_fall

- tunable `gravity_air` (exe scope, 0x43a6a2; spec physics.md#Constants (airborne gravity imm, phys_Integrate while flag 4)); live before -9.8, set -4.9 (read back -4.9, ok), reset read back -9.8 (ok).
- probe {"kind": "accelerate", "s": 10}; frames per observation: A1 208, A2 211, B 207, A3 207; t = 481.9..545.0 s.
- note: Needs airborne frames (flag 0x4); a straight run over the melee ground gives a few per probe at best. INCONCLUSIVE when fewer than min_frames: the `jump` scenario is the right vehicle for this one.
- `formula` accel_1 when `airborne and speed>5`: **INCONCLUSIVE** - A1: fewer than 5 frames satisfy `when`; B: fewer than 5 frames satisfy `when`
  - A1: {"ok": null, "considered": 0, "note": "fewer than 5 frames satisfy `when`"}
  - A2: {"ok": false, "considered": 30, "matched": 0, "rate": 0.0, "max_err": 9.8, "median_err": 9.8}
  - B: {"ok": null, "considered": 0, "note": "fewer than 5 frames satisfy `when`"}
  - A3: {"ok": null, "considered": 1, "note": "fewer than 5 frames satisfy `when`"}

### 14. aero_drag_top_speed

- tunable `aero_drag_scale` (exe scope, 0x4bd1b0; spec physics.md#One substep (a = -0.1 x drag x v^2)); live before -0.1, set -0.05 (read back -0.05, ok), reset read back -0.1 (ok).
- probe {"kind": "accelerate", "s": 12}; frames per observation: A1 248, A2 248, B 249, A3 235; t = 545.0..617.7 s.
- note: Halving the drag scale raises the terminal speed about 1.4x; over 12 s of full throttle the top speed reached must rise by more than the A/A spread.
- `increase` speed : **INCONCLUSIVE** - B moved -2.977, within the control band 4.328 (A1 38.197, A2 36.033)
  - A1: 38.1967
  - A2: 36.0327
  - B: 34.1379
  - A3: 11.15

