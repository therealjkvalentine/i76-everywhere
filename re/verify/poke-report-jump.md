# Poke report (verify/poke.py, VERIFICATION-PROGRAM.md 2.5 / 4.4)

Generated 2026-10-02 14:14. Run: `C:\Users\james\i76-map\verify\runs\poke\20261002-140824` (route melee, exe i76_pristine_fix.exe md5 58d9dec0, profile stock20, proxy 9a081000). Telemetry frames 4865, events 344. Sandbox restore: STRLKUP.DLL md5 54f2de9d after the run; quit: WM_CLOSE ignored for 10 s, killed; errors: []; warnings: [].

Each expectation: observe (A1), observe (A2) with nothing changed (the A/A control), set the tunable with i76tune (read back), observe (B), reset (pristine bytes / saved live value, read back), observe (A3). `formula` grades PASS when >= 98% of the frames that satisfy `when` are within tolerance in A1, A2 (default x), B (set x) and A3 (default x); increase / decrease / unchanged compare B with the A mean beyond max(2 x |A1 - A2|, min_delta). INCONCLUSIVE when no field can observe the change, the probe produced too few frames, the A/A pair disagrees, or the write did not read back.

## Results

| # | expectation | tunable (scope, addr) | default -> set | relation | observable | A1 | A2 | B | A3 | grade | why |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | aero_drag_top_speed | aero_drag_scale (exe, 0x4bd1b0) | -0.1 -> -0.05 | increase | max(speed) | 50.1 | 30 | 45.99 | 53.69 | **INCONCLUSIVE** | B moved 5.933, within the control band 40.191 (A1 50.101, A2 30.005) |
| 2 | gravity_air_fall | gravity_air (exe, 0x43a6a2) | -9.8 -> -4.9 | formula | accel_y(velocity_1) | ok -9.8 vs -9.8 | ok -9.8 vs -9.8 | ok -4.9 vs -4.9 | ok -9.8 vs -9.8 | **PASS** | A/A, changed and restored observations all follow the formula with their own x |

Per expectation: INCONCLUSIVE 1, PASS 1 of 2.

## Details

### 1. aero_drag_top_speed

- tunable `aero_drag_scale` (exe scope, 0x4bd1b0; spec physics.md#One substep (a = -0.1 x drag x v^2)); live before -0.1, set -0.05 (read back -0.05, ok), reset read back -0.1 (ok).
- probe {"kind": "accelerate", "s": 20}; frames per observation: A1 408, A2 408, B 408, A3 408; t = 0.6..128.3 s.
- note: Halving the drag scale raises the terminal speed about 1.4x; over 12 s of full throttle the top speed reached must rise by more than the A/A spread. Session 1 (12 s probes) was INCONCLUSIVE: 34-38 m/s in every window, terminal speed not reached; 20 s probes since 2026-10-02.
- `increase` speed : **INCONCLUSIVE** - B moved 5.933, within the control band 40.191 (A1 50.101, A2 30.005)
  - A1: 50.100502014160156
  - A2: 30.00485610961914
  - B: 45.98541259765625
  - A3: 53.69253921508789

### 2. gravity_air_fall

- tunable `gravity_air` (exe scope, 0x43a6a2; spec physics.md#Constants (airborne gravity imm, phys_Integrate while flag 4)); live before -9.8, set -4.9 (read back -4.9, ok), reset read back -9.8 (ok).
- probe {"kind": "jump", "vy": 12.0, "dy": 1.5, "s": 4}; frames per observation: A1 82, A2 82, B 81, A3 82; t = 128.3..224.1 s.
- note: Needs airborne frames (flag 0x4): the `jump` probe (run_scenario's launch op: lift 1.5 m, vy = 12 m/s, ~2.4 s of flight = ~48 frames at 20 fps) replaces the straight run, which gave 0-3 airborne frames per probe on the melee ground (sessions 1-2, INCONCLUSIVE). Graded on the median dvy/dt of consecutive airborne frames (metric accel_y): the telemetry accel field (ent+0xd4) reads 0 on every airborne frame (the air path does not write it), so the earlier accel_1 field could never pass.
- `formula` velocity_1 when `airborne and speed>5`: **PASS** - A/A, changed and restored observations all follow the formula with their own x
  - A1: {"ok": true, "considered": 1, "value": -9.8, "expected": -9.8, "err": 0.0}
  - A2: {"ok": true, "considered": 1, "value": -9.8, "expected": -9.8, "err": 0.0}
  - B: {"ok": true, "considered": 1, "value": -4.9, "expected": -4.9, "err": 0.0}
  - A3: {"ok": true, "considered": 1, "value": -9.8, "expected": -9.8, "err": 0.0}

