# simclock

`simclock_Update` 0x49c920 runs once per rendered frame (WinMain, 0x4039b8 in the Galaxy exe, which is where
i76fix's limiter Sleep goes). It keeps the game's time and everything else reads it:

1. `simclock_frame_count` 0x5a7e1c += 1.
2. `t = (float)(GetTickCount() * 0.001)`. `simclock_dt` 0x4fe428 = t − `simclock_last_tick` 0x5a7e10; offline it is
   clamped to [0.001, 0.2] s. `simclock_rate` 0x4fe42c = 1/dt. `simclock_time` 0x5a7e74 += dt. For the first 3 frames
   (0x5a7e18) dt is kept out of `simclock_accum_dt` 0x5a7e14.
3. When 0x4fe534 & 0x3e (pause-type states) is set offline, dt is zeroed and the rates are set to 1e30.
4. `simclock_sim_dt` 0x4fe420 is the sim step. Offline it equals dt. Networked, it is the synchronised delta built
   from 0x5a7e78 / 0x5a7e7c (0x49c8d0). It is capped at 1.0 s. `simclock_sim_rate` 0x4fe424 = 1/sim_dt;
   `simclock_sim_time` 0x5a7e70 += sim_dt.

Consumers go through accessors:
- `simclock_GetDt` 0x49c8b0: 34 callers (camera, input, weapons, FFB).
- `simclock_GetTime` 0x49c8c0: 39 callers.
- `simclock_GetSimDt` 0x49c7a0: 21 callers, including the physics range 0x434000..0x43f8c0 and the AI range.
- `simclock_GetSimRate` 0x49c7b0.
- `simclock_GetSimTime` 0x49c7c0: 48 callers (AI, network).
- `simclock_GetAccumDt` 0x49c7e0: the script VM (`fsm_ActionDispatch`).

**Physics substeps.** Each vehicle has a stepper at entity+0x444, set up by
`simclock_StepperInit(stepper, 0.05)` in `entity_InitVehicle`. Every frame `entity_TickVehicle` 0x463800 calls
`simclock_StepperBegin`: count = min(floor(sim_dt × 20) + 1, 20) and step = sim_dt / count (1/n table at 0x5a7e20,
filled by `simclock_Init`). It then loops on `simclock_StepperNext`, running the entity update 0x465370 and the physics
step 0x438fd0 once per step. So the engine is **dt-driven, with substeps of at most 50 ms**, not a fixed per-frame
step. Frame-rate sensitivity therefore has to come from the step size changing (count jumps at every multiple of
50 ms, and GetTickCount jitter changes it frame to frame) and from per-frame constants elsewhere, not from dt being
ignored.

## Defects

- **Timer resolution.** GetTickCount steps in 15–16 ms, and `timeBeginPeriod(1)` doesn't change that (measured
  2026-09-26). At 20 fps dt reads 47 or 63 ms, which is the jitter long seen in the FFB dt copy at 0x4f2488. At
  60 fps most frames read 0 (clamped to 1 ms) or 15.6 ms.
- **Uptime precision (Galaxy exe 9a232dcc only).** t is stored as a float32 of seconds since boot (`fstp dword` at
  0x49c94c), so dt snaps to a grid of 7.8 ms after 1 day of uptime, 62.5 ms after 7 days and 250 ms after 30 days.
  GOG's 2019 AiO build (60abf7bc, which the sandbox's 4fabc303 is built on) masks the tick with `and eax, 0x7fffff`,
  so t stays under 8,389 s; the counter wraps every ~2.3 h and the one negative dt is clamped.
- Fix, opt-in: `I76_HIRES_CLOCK=1` in the i76-everywhere Strlkup proxy (`music-fix/strlkproxy.c`) repoints only the
  two simclock GetTickCount calls to a QPC clock in ms since process start. It handles both layouts and verifies the
  bytes first. The write is verified in the sandbox; it has not been played yet.

## Members

| addr | name | status |
|---|---|---|
| 0x49c920 | simclock_Update | supported |
| 0x49c7f0 | simclock_Init | supported |
| 0x49c8b0 / 0x49c8c0 / 0x49c7e0 | simclock_GetDt / GetTime / GetAccumDt | supported |
| 0x49c7a0 / 0x49c7b0 / 0x49c7c0 | simclock_GetSimDt / GetSimRate / GetSimTime | proposed |
| 0x49cbe0 / 0x49cc20 / 0x49cca0 | simclock_StepperInit / StepperBegin / StepperNext | proposed |
| 0x463800 | entity_TickVehicle | proposed |

## A frame-dt read inside the substeps (2026-09-26)

A reachability pass over the substep call tree (0x438fd0 and 0x465370: 390 functions) against the clock accessors
found **one** place that uses the whole frame's dt where it should use the step: `physics_UpdateEngine` 0x46a320,
called once per substep from the physics step at 0x43a1e3, reads `simclock_GetDt` at 0x46a333. It smooths engine RPM
(+0x1c) and a second value (+0x24) with a factor of 2·dt and derives torque (+0x10) from them. Every other clock read
in that tree is a timestamp (`simclock_GetTime` / `GetSimTime`, used by wreck, network and message code) or sits on the
network path (0x43d070 via 0x451180). Consequence: engine RPM and torque converge `count` times per frame, about 2×
faster per second at 20 fps than at 60 fps. Opt-in fix `I76_ENGINE_DT_FIX=1` in the Strlkup proxy repoints that one call
at 2 × sim_dt / count, which reproduces the 20 fps (two-substep) response at any frame rate. The write is verified in the
sandbox; it has not been played.
