# framerate

What in the game depends on how many frames are rendered per second, and why. Static reading of md5 9a232dcc
(2026-09-27); `tools/perframe.py` builds the per-frame call tree (`status/perframe.tsv`). The "Measured" section
below records what capture 014 confirmed in game.

## How a frame runs

WinMain's gameplay loop (0x4039a0..0x403f20) does one iteration per rendered frame. There is no frame limiter and no
fixed-step scheduler: the 1 s and 10 s comparisons around 0x403d59 are network timeouts, not pacing. In order:

1. `simclock_Update` (0x4039b8) derives this frame's dt from GetTickCount (see `simclock.md`).
2. Input and network: `input_ApplyToEntity` via 0x44dec0 / 0x49d000, network 0x4532c0.
3. **0x461c80 ticks every live object.** It walks the list at 0x54b204, finds each object's class record in the
   table at 0x4f76e0 (0x34-byte records, object type at +0, type from object+0x6c) and calls slot +0xc. For vehicles
   (type 1) that is `entity_TickVehicle`, the only place with physics substeps.
4. **0x461d50** calls slot +0x10 on every object: the post-tick. For the player vehicle that is 0x463950, which runs
   0x459fa0 and `ffb_WriteSimState`.
5. 0x40a320 (script VM, AI; uses dt and 1/dt), 0x462a90, 0x4a0410 (projectiles), `weapon_Update`, 0x44af80.
6. The camera controller, an indirect call through [0x4c2720]. Twelve camera modes install their update function
   there (`mov [0x4c2720], imm`, e.g. `camera_CockpitLook` 0x406ab0, free cameras 0x405b90 / 0x4061b0). The
   0x268-byte controller block is pushed and popped on an 8-deep stack at 0x5dbb20.
7. Render: 0x401c90 → 0x401cc0 (camera matrix, shadows, sky), 0x4621e0, the HUD, then Flip.

Class table slots (types 1 vehicle, 2/4, 7..10, 20..24, 30..36, 40/41, 50..53): +4 create, +8 init, +0xc tick,
+0x10 post-tick, +0x1c get velocity, +0x20 telemetry, +0x24 ?, +0x28 damage (dispatcher 0x462040), +0x2c ?,
+0x30 destroy. The dispatchers are 0x461810..0x462080.

## Verified frame-rate dependencies

| # | what | where | why it scales with fps | effect at 60 fps vs 20 |
|---|---|---|---|---|
| 1 | Clock resolution | `simclock_Update` 0x49c929 | GetTickCount steps in 15.6 ms; dt reads 0 (clamped to 1 ms) or 15.6 ms at 60 fps | jittery dt everywhere; 1/dt spikes to 1000 |
| 2 | Uptime precision (Galaxy exe only) | 0x49c94c | seconds since boot kept in a float32 | 62.5 ms dt grid after 7 days of uptime |
| 3 | Engine RPM/torque smoothing | `physics_UpdateEngine` 0x46a333 | whole-frame dt used inside each physics substep | engine responds about 2× slower per second |
| 4 | Cloud scroll | 0x405200, 0x405455..0x4054a9 | `u = fmod(u - 1/(1001 - s), 1)` and `v` alike, once per call, no dt (s = 0x504c30 = 0.0078) | sky drifts 3× faster |
| 5 | Free-look camera keys | 0x405b90 (0x405bc4..0x405c28), 0x4061b0 (0x4061e7..0x40623f) | pitch/yaw (0x4c2918 / 0x4c291c) -= input delta × 1° (0x4bc528) per call | camera turns 3× faster. A rescaled constant (−0.3333° = stock × 20/60, uncap-lab `patch-camera-rate.ps1`) exists in the sandbox / lab only, **not** in the portable install — finding L004: "The portable i76.exe 6319abf7 differs from pristine only by the aio clusters and the u32x import rename; the .rdata constant 0x4bc528 is unchanged there (binaries/diff-9a232dcc-vs-6319abf7.tsv: .rdata run list), so no camera-rate patch is deployed." The proxy's `I76_FRAMERATE_FIXES` covers these two sites instead (corrected 2026-10-01) |
| 6 | Keyboard throttle ramp | `input_ApplyToEntity` 0x44f306 / 0x44f366 | throttle_applied += 0.4 × (1 − hold/3) per call (−0.5 × for the other key); hold time itself uses dt | keyboard throttle ramps 3× faster; fixed by `I76_FRAMERATE_FIXES` (2 sites) |
| 8 | Zoom key | camera mode 0x408a10 (0x408a2b..0x408a51) | zoom [0x4c2914] *= 1 - input [0x5367bc] × 0.01 per call, clamped to [0.85 × [0x4c2740], 4 × cam+0x10] | zoom 3× faster; fixed by `I76_FRAMERATE_FIXES` (0x408a3f) |
| 7 | Rear mirror refresh | 0x445750 | redraws when frame count ≥ next, next = frame + 2 | cosmetic: mirror refreshes 3× as often |

**Retracted (2026-09-27, re-read):** two rows that stood here were static misreads. The type-34 post-tick 0x460c80
(and its twin 0x45faf0) does `while (next < simclock_time) { next += 1.0; trail = min(trail + 3, 0x69); }`, where
0x4be130 is −1.0: a 1 Hz catch-up loop on sim time, so it is frame-rate neutral. 0x477ed0 sets +0x14 to 0 and rewrites the
+0x48..+0x50 vector every call (0x478149..0x478160), then lifts it by 25 when the terrain below is within 25, so this is
a per-call offset, not an accumulating fade. Both matched the detector's "constant step, no dt" shape. `perframe.py`
now marks candidates that also read an absolute clock (`hint = clock`).

**The static screen is exhausted.** All 16 frame-scope candidates have been read by hand. The real ones are the rows
above (free-look 0x405b90 / 0x4061b0, zoom 0x408a10, throttle) and the script VM's frame counter 0x4155f0
(two-frame latches, neutral). The rest are neutral:
- network per-packet averaging/counters: 0x454960, 0x454ff0, 0x4541b0;
- reference counts and list insertion: 0x449a00, 0x44a290, 0x4677d0, 0x4a05f0;
- a fresh copy then an offset: 0x401970;
- the catch-up loops above.

What the screen cannot see are integer steps through registers, and state held in the substep scope; the physics side
is covered by the fixed step.

Steering keys are **not** frame-dependent: steer is set absolutely to ±sqrt(hold/3), and the hold time uses dt.
`camera_CockpitLook` and the chase camera 0x407ad0 scale by dt.

## Measured (capture 014, 2026-09-27)

Confirmed live: #1 (dt on a 3.9 ms grid at 15.8 h uptime; `I76_HIRES_CLOCK` gives exact dt), #4 (clouds 0.0299 /s at
20 fps vs 0.0899 /s at 60 fps, 3.0x), #6 (keyboard throttle full in 2 frames at either rate). Acceleration shows no
difference beyond the run-to-run spread. **Cockpit bounce / chassis buzz** (8): the body's angular velocity
reverses about 3x as often at 60 fps, and the cause is the **physics substep size**. Forcing smaller substeps at a
fixed frame rate raises the buzz, and a fixed 25 ms step (`I76_FIXED_STEP=40`, an accumulator replacing
`simclock_StepperBegin`) brings 60 fps back to the 20 fps level (n = 4 per condition, ranges disjoint). Details in
`captures/014-framerate/README.md`.

### Where the step dependence lives (found, 2026-09-27)

`physics_ResolveGroundContact` 0x437230, once per substep from `physics_StepVehicle` (0x43a104) and once per frame
through `physics_SnapToGround` 0x43d070. It is a discrete contact model with no time scaling beyond one easing term:
the body is moved up along the surface normal by the deepest wheel penetration in one go (position doubles, per
step, 0x43792f); roll and pitch rates are eased toward fixed targets at 2/s (`omega += 2·step·(target − omega)`); and
when the velocity-against-normal test passes, the pose is re-oriented and both rates are set to exactly 0 (0x437f73).
The suspension forces themselves are integrated with the step (0x43b25b..0x43b3ce) and the wheel routine keeps no
state, so the only step-shaped behaviour is this projection/rest cycle. Capture 014 shows it directly: the body is at
rest (rates exactly 0.0) on 62% of frames with 25 ms steps, 11–40% with 16.7 ms, 0–4% with 5.7 ms, and 65% again
with a fixed 25 ms step at 60 fps. There is no single coefficient to rescale; the model is tuned for the stock 25 ms
step. The principled fix is the fixed step (`I76_FIXED_STEP=40`); smoothness at 60 fps then comes from rendering
interpolated poses between physics updates, which is the next piece of work.

## Leads (read, not yet pinned)

- **Superseded 2026-09-27 by `ai.md` "Frame-rate behaviour": the throttle (0x40f9c0) and steering (0x40fe80) 1/dt terms are one-frame dead-beat gains, not derivatives; 0x417bf0 / 0x419e20 cancel; 0x41b270 is per-call (rand gate).** Original note: **AI driving uses 1/dt (measured, capture 014: AI throttle chatter 26.2 /s total variation at 60 fps vs 1.56 at 20 fps; 8.96 with `I76_HIRES_CLOCK`, 5.33 with the clock plus fixed step, n = 3 each).** The AI throttle controller 0x40f9c0 multiplies a speed difference by
  `simclock_GetSimRate` (1/dt), a derivative term. With GetTickCount jitter, 1/dt swings between 16 and 21 at
  20 fps and spikes to 1000 at 60 fps (dt clamped to 1 ms). That fits the folklore "AI brake flutter / top-speed cap
  above 20 fps". Other 1/dt users: 0x40a320, 0x417bf0, 0x419e20, 0x41b270, 0x4354c0, 0x435830, 0x435cc0.
  Prediction: `I76_HIRES_CLOCK` removes most of the flutter.
- **Correction 2026-09-27: the jam roll below runs in network games only.** At 0x4a4257, `net_IsNetworkGame` = 0 skips the whole block (jam and int(dt x rate) ammo drain); offline, ammo is spent in the fire paths 0x4a6470 / 0x4a6e90 (`weapons.md`). Original note: **Weapon jam roll: effectively frame-rate neutral.** `weapon_Update` 0x4a4351..0x4a43ac: for a firing slot
  whose condition ratio r is below 0.7, p = min(1 - r - 0.3, 0.5) (0x4beac0 / 0x4beb10 / 0x4beb14). Each frame
  `rand() < p x 32767` jams it: the fire flag slot+0x3c is cleared for that frame and ammo drops by `int(dt x rate)`.
  Because the roll is independent every frame, the fraction of jammed frames is p at any frame rate, so the effective
  duty cycle does not change; jams are just shorter and more frequent at 60 fps. The truncated ammo loss is usually 0
  at either rate.
- Frame-count users: the renderer cache 0x42ec20 / 0x42f5f0 / 0x42f6b0 (probably LRU aging) and 0x45adf0.

## Fix mechanism (planned)

Every site above is either a constant step applied once per call, or a dt read that should be the substep's. Both
fit one opt-in approach in the Strlkup proxy (`music-fix/strlkproxy.c`, where `I76_HIRES_CLOCK` and
`I76_ENGINE_DT_FIX` already live). Repoint the site's `fmul/fadd [constant]` at a proxy variable recomputed each
frame as constant × dt × 20, or wrap the call and rescale its effect, so the game keeps its 20 fps feel at any
frame rate.

## Per-frame physics outside the substeps (2026-09-27, physics.md)

- Object/vehicle collision (0x4349c0) runs once per rendered frame with the frame sim dt. Sweeps cover [0, dt], and
  only the last contact in a frame reaches the car. At 60 fps collisions are tested 3x as often over shorter sweeps.
- Far vehicles (beyond the camera far radius + 25 m) take one whole-frame step of a flat kinematic model per frame
  (0x43a3c0); the fixed-step proxy does not touch this path.

- Keyboard head-look in camera mode 2 moves a fixed step per frame (range-p-1); the orbit keys (1 deg per frame), the
  end-of-match spin (8 deg per frame) and the overhead-map zoom do the same (`camera.md`). Smoke puffs live 20 frames,
  missile trails lose 4 segments per frame near expiry, and flamer streams lose 2 per frame (`renderer.md`).
  - Fixed 2026-09-27 under `I76_FRAMERATE_FIXES`. Smoke puffs update on the 20 Hz grid and are drawn extrapolated
    in between. Live, a damaged car's puffs age 19.1 steps/s at 60 fps with the fix, 57.8 without (one run each,
    hundreds of puffs; `captures/014-framerate/smoke_*.json`).
  - Missile-trail fade and flamer ageing are held to grid frames. The flame shape and per-hit amount use the
    stock-20 dt.
  - **Flamer damage was frame-rate and mirror dependent**: applied per render call per hitting segment, at least 1
    each, and again in the rear-mirror pass. With the fix it is applied only from the main pass, 20 times a second
    (`weapons.md` Flamers).
  - **AI fire decisions** roll their random gate once per frame: about 3x as many yes decisions per weapon per
    second at 60 fps (live 4.9-5.2 vs 1.3-2.4 at stock 20 fps). Held to the 20 Hz grid by the proxy (`ai.md`, Fire
    decisions).
  - Cosmetic: the HUD ammo digits roll one step per frame toward the new value (`camera.md`, HUD drawing). The proxy
    now skips the roll call between grid frames (0x4a44ca). Not measured.
  - A draw-path sweep and a per-frame rand() sweep (every per-frame function that calls rand) found no other
    gameplay dependency. The rest are visual (screen shake, smoke), menu, spawn-time, or network-only (the jam roll).
  - Flame stream length, live, Gas Launcher held 4 s: stock 60 fps 0.6 segments on average (max 2); stock 20 fps
    19.0; fixed 60 fps 18.7 (`captures/014-framerate/flame_*.json`).

## Step rate is the physics' real clock (2026-09-27, capture 014)

- **Stock step sizes.** Stock play at 20 fps steps 46.9 ms (80%) / 31.2 ms. The GetTickCount frame dts of
  46.9 / 62.5 ms are split by the stepper's floor(dt·20)+1. That is about 24 steps per second.
- **What depends on steps per second.** Body motion, the lip "pop" and the coasting speed loss all follow the number
  of contact steps per second: about -0.063 m/s per 100 m for each step/s while coasting (n = 16, residual sd 0.26).
  More steps per second (stock 60, a fixed 40) means a slower takeoff and shorter jumps.
- **The fix.** `I76_FIXED_STEP=24` reproduces stock 20. `I76_RENDER_INTERP` hides the 24 Hz cadence: vehicles are
  drawn between physics poses, and the frame loop's camera update (0x403e16) runs on the drawn pose.
- **Per-frame sound restarts.** Sounds requested every frame while a state holds retrigger on the frame grid:
  the missile-lock tones in 0x4a3760, and skid / flat / damage in 0x43d500. They are now gated to a 20 Hz start grid,
  and loops keep their per-frame keep-alive.
- **Off-screen vehicles.** Vehicles outside the camera test 0x406840 (radius 25) take `entity_TickVehicle`'s cheap
  branch, 0x43a3c0 with the whole frame's dt and no stepper. That is still frame-rate dependent (not addressed).

### Mission scripts and `rand` (FSM action 10, 0x4133ad)

**VM rate.** The script VM steps once per rendered frame. WinMain calls `ai_FrameTick` 0x40a320 at 0x403ddf, and that
calls `fsm_RunMachines` 0x4149f0 at 0x40a644. Each machine runs until its next `yield`, so one state step per machine
per frame, with no dt. `timeGreater`/`timeLesser` read the mission clock, so waits on time are frame-rate neutral. The
event frame counter [0x524550] ticks once per VM pass (0x40a658). `isShot`/`isRammed`/`isAttacked` are edges: the
damage stamp must equal this tick or the last one, and it is consumed on read (0x40b990).

**No script re-rolls `rand` while waiting.** Every one of the 330 `rand` sites in the 25 scripted missions compiles
to the same one-shot state: `true; jz; rand; drop; jmp Ltest`. The test state after it yields back to itself, not to
the roll. By site:

| class | sites | what |
|---|---|---|
| dead code | 229 | the byte-identical prelude (pc 0..1899) holds template machines no mission starts |
| one-shot | 48 | death lines, "wait N s then pick a line", start-up choices (the machine never re-enters the roll) |
| choice on a slow event | 2 | T01 pc2748 (Taurus hit, 10 s cooldown) and pc3079 (range 140/150 m hysteresis); every value plays a line |
| gated on an attack event | 51 | re-rolled once per consumed `isAttacked` edge (at most once per tick) |
| polled every tick | **0** | |

**Attack-gated rolls.** Frame-rate neutral unless damage arrives on consecutive frames.
- Library machine pc227 (22 missions, the player entity): a player pain line with p = 9/30 (hp < 70, pc267) or 5/15
  (pc277) per hit, then 20 s of silence.
- T10/T11/T14 pc743 (Taurus): a line with p = 3/8 when Groove is the attacker (pc782), 6/15 for anyone else (pc792),
  then 15 s.
- T01 m9 pc3831: Taurus, in the final fight, checks with p = 1/10 per hit whether Groove shot him. If so he re-targets,
  or (global 10 == 1) sits for 80 s.

A hit stamps ai+0xa6dc via `ai_RecordDamageEvent` 0x4157a0 (from `physics_ApplyCollisionDamage` and
`weapon_ApplyFlameDamage`). Discrete hits below 20 per second give the same number of rolls at any frame rate. A source
that records damage every frame (stock flamer stream, sustained ram contact) gives one roll per frame. The line then
comes after about 0.17 s at 20 fps and 0.06 s at 60 fps, and the 20 s / 15 s cooldowns keep the line rate within 1%.
Only T01 pc3831 has no cooldown on its re-target branch: 2 per second at 20 fps against 6 at 60 under continuous flame
from Groove. The `I76_FRAMERATE_FIXES` flame hold (20 Hz) already removes that case.

**Exe `rand` users checked.**
- `calc_sum` 0x412680 is the attack-tactic selector: a weighted draw by aggression, redrawn up to 17 times on a failed
  precondition. It runs only when a tactic exits or the order or target changes (0x412a3f, 0x412bea), not per frame.
- `renderer_DrawSpecialsPanel` 0x467e30 picks one of five `3housing*` dashboard sprites per specials slot. It is
  cosmetic and runs at vehicle init, on a keypress or from a menu.
