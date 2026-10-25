# Whole-sim fixed tick: an experiment against the per-stepper fixed step (2026-10-17)

Owner-approved lab experiment, run alongside the versions-and-physics workflow. The question: does running the game's
**whole** per-frame simulation on a fixed tick, and only drawing at the display rate, work better or worse than the
current scheme (a fixed step per vehicle stepper, everything else per rendered frame, plus about 50 patch sites)?

Design source: [PHYSICS-STEP-STUDY-DESIGN.md](PHYSICS-STEP-STUDY-DESIGN.md) s.7.2 (task L1) and its 2026-10-17
amendment (baseline 33.3 ms; the mixed-rate arm). Developer testimony: [DEV-GAME-CLUB-I76.md](DEV-GAME-CLUB-I76.md)
("designed to run at 15 frames per second", "everything ran in the same loop").

**Result (2026-10-17, lab headless twin + two real-renderer boots; numbers carry n).** The tick works: exactly 15.01 /
29.99 ticks per wall second, every sim gate once per tick, the car 2 x 33.3 ms (66.7 ms tick) or 1 x 33.3 ms (33.3 ms
tick), no interpolation leak in 0 of ~145 000 checks, 30 hooks read back from the live process every boot, and the
owner's route (game-tick, dgVoodoo) boots and passes the same checks. Against the current scheme (lab-step-33) it is
**no better and no worse on the physics** (placed 56 m/s jumps, barricades, T06 strip all inside the A/A spread),
**smoother or equal to draw** except the player car under the 66.7 ms tick, and **clearly worse on input latency**
(key to first drawn change, median 38 ms / 18 ms vs 7 ms). It also removes the patch pile's one large unexplained
effect seen here: hostile AI fire decisions per sim second are 3.5 x higher under lab-step-33 than under the 33.3 ms
tick with the same number of AI calls (n 1 boot each, to confirm). Verdict: keep the per-stepper scheme as the play
default; the 33.3 ms tick is the cleaner reference build (12 gates instead of ~50 rate patches) and worth an owner
feel test (TEST-tick-33.bat); the 66.7 ms tick is the faithful 1997 design but its 38-67 ms input lag is the price.

## 1. The cut between simulation and drawing (RE)

Static reading of our exe (AiO-based 6319abf7 = Galaxy 9a232dcc at these bytes), capstone over the live image, names
from <re-archive> `symbols/functions.tsv`. WinMain's mission loop runs 0x40398d..0x4040c4. Offline, one iteration is:

| site | call | side | notes |
|---|---|---|---|
| 0x4039b8 | `simclock_Update` 0x49c920 | clock | frame count +1, GetTickCount, dt / sim_dt / rates / time / sim time / accum_dt; the proxy's frame hook sits here |
| 0x4039bd | `input_UpdateControls` 0x44d9e0 | **sim** | key edges, one-frame discrete pulses, held bytes |
| 0x4039e4..0x4039fc | active flag 0x504c1c, state 0x4fe534 & 0x3e | gate | paused / inactive: skip to 0x40402f (no sim, no render) |
| 0x403a12 | `physics_CollideAll` 0x4349c0 | **sim** | sweeps over [0, sim_dt] |
| 0x403a1c | `input_ProcessFrame` 0x44dec0 | **sim** | -> `input_ApplyToEntity` 0x44f1c0 at 0x44df61 (throttle ramp, steer hold timers, ignition / lights copies) |
| 0x403a26..0x403d7c | network only | - | offline jumps to 0x403d86 |
| 0x403d86 | `entity_TickAll` 0x461c80 | **sim** | class slot +0xc of every object in 0x54b204: `entity_TickVehicle` 0x463800 (`camera_ClassifyDistance` 0x406840 -> near path with `simclock_StepperBegin` 0x49cc20 at 0x463888, or the far path `physics_StepVehicleFar` 0x43a3c0), aircraft, gates, spinners |
| 0x403da6 / 0x403dd0 | `net_RegenPointTick` 0x4515e0 | **sim** | multi-melee regen points (result tested) |
| 0x403dd5 | `entity_PostTickAll` 0x461d50 | **sim** | slot +0x10 (player 0x463950 -> `ffb_WriteSimState`) |
| 0x403ddf | `ai_FrameTick` 0x40a320 | **sim** | hand-off latch, `fsm_RunMachines` (script VM), every AI behaviour; FSM camera actions set the view from here |
| 0x403de7 | `entity_TickTurretFire` 0x462a90 | **sim** | |
| 0x403dec | `weapon_UpdateProjectiles` 0x4a0410 | **sim** | delayed impacts, every ordnance step, stationary hazards |
| 0x403df6 | `weapon_Update` 0x4a4130 | **sim** | firing, lock tones, HUD ammo digit roll |
| 0x403dfb | `image_UpdateTexAnims` 0x44af80 | sim (cosmetic) | time-based texture animations; gated with the sim |
| 0x403e16 | `call [0x4c2720]` camera mode | **render** | chase lag, cockpit sway 0x437f90, hood, free-look; reads `GetDt` and `GetSimDt` |
| 0x403e1c | `renderer_EvictFarEntityGeometry` 0x4066e0 | render | camera-relative |
| 0x403e27 | `shell_cb_10` 0x421400 -> `sound_UpdateListener` 0x422440 | render | DS3D listener = camera eye 0x4c2890 + the player's velocity |
| 0x403e69 | `renderer_DrawFrame` 0x401c90 | render | scene (software 0x401cc0 / hardware 0x401fa0), mirror 0x445750, HUD |
| 0x403e85..0x403eaa | BeginFrame, `renderer_DrawMask`, fonts, Flip | render | |
| 0x403ee9 | `object_ResetFrameCache` 0x468040 | render | |

**Camera-relative work, by side.**
- Sim side, reading the camera the last display frame left (the drawn pose, at most one tick behind physics, as 1997
  read the previous frame's camera): `camera_ClassifyDistance` (near / far vehicle path, radius 25), the AI's view tests.
- Render side, every display frame: terrain LOD and far-geometry eviction, the sound listener, shadows, the mirror.

**Sim logic inside draw code** (found by the 2026-10-03 per-frame audit; re-traced here with a call-site scan):
`weapon_AgeFlamerStreams` 0x443e90 (top of each scene pass), `weapon_UpdateFlamerStreams` 0x443fc0 (main pass
0x401e23 / 0x4020e8 and twice from the mirror 0x4458fe / 0x445968) -> `weapon_FlameHitTest` 0x4354c0 ->
`weapon_ApplyFlameDamage` 0x4a8240, the hit explosion 0x49ead0; `renderer_UpdateSmoke` 0x4414a0 (puff ageing, 20
calls); `renderer_QueueSmokeTrails` 0x442ba0 (tail drop per call); the radar ping in `renderer_DrawQueuedRadarBlips`
0x460190. Cosmetic per-call constants: clouds 0x405461 / 0x405484, free-look 0x405bd0.., zoom 0x408a3f.

**Clock readers.** `simclock_GetFrameCount` 0x49c7d0 is read only by render code (texture cache LRU, cockpit).
`GetDt` has 34 callers: camera modes, smoke, flamer, screen shake on the render side; input, weapons, projectiles,
FFB, engine on the sim side. `GetSimDt` / `GetSimRate`: physics, AI, the flamer hit test, cockpit sway.

## 2. What was built (lab only, opt-in, off by default)

`I76_SIM_TICK_MS=<ms>` in the Strlkup proxy, `music-fix/simtick.c` (i76-everywhere 68d3ba2; the committed
`music-fix/Strlkup.dll` and the daily driver are untouched).

- **Gate.** The 12 sim call sites above are repointed (`call rel32`, the old target chained) at gates that run only
  on a tick frame. Ticks come from a wall-clock (QPC) accumulator: at most one tick per display frame; a frame that
  owes more drops the excess (counted). Paused / inactive / shell frames run stock (`simclock_Update` every frame).
- **Clock.** On a tick frame `simclock_Update` runs, then dt = sim_dt = T, both rates 1/T, and simclock_time, sim
  time and accum_dt advance by exactly T. On other frames `simclock_Update` is not called; the frame counter 0x5a7e1c
  is still advanced (its readers are all render code).
- **Display window.** Around the camera mode (0x403e16) and the render (0x403e69): dt = sim_dt = the display
  frame's wall dt (camera smoothing and sway run at display rate), restored to T at the top of the next frame.
- **Interpolation, every moving object.** At each tick start the 0x40-byte transform (object +0x18) of every object
  in the live list 0x54b204 and in the projectile lists (0x655290 + i x 0xd0, [0x5a810c] types, linked by +0x60) is
  recorded; at the end of the sim block again. Objects that moved (and not by more than a teleport bound: 12 m per
  tick for vehicles, 150 m for others) are drawn at lerp(start, end, alpha), alpha = wall time since the tick / T,
  rotation re-orthonormalised (row lengths kept for scaled objects; > 60 deg per tick takes the newer rotation).
  Swapped in for the camera mode and the render only; the physics pose is put back right after; after a tick frame's
  render the live list is re-walked so an object the flamer killed is not written to. A pose changed between ticks
  by anything else (the trainer) is drawn as it is.
- **Cameras.** A camera set from the sim (FSM script cameras, the in-tick player camera) is interpolated between the
  last two ticks' views on display frames where no camera mode set the view.
- **Draw-code sim held to the tick** (reusing the I76_FRAMERATE_FIXES wrappers with the grid flag = "this frame
  ran a tick" and the reference dt = T): flamer ageing, update dt, damage and hit explosion from the main pass only
  (the main-pass update runs on the tick's clock), smoke ageing (drawn extrapolated between ticks), trail fade, radar
  ping. Cosmetics scaled by display dt / T: clouds, free-look, zoom (`I76_SIM_TICK_COSMETIC=0` turns that off).
- **Refuses** to apply together with `I76_FIXED_STEP`, `I76_RENDER_INTERP` or `I76_FRAMERATE_FIXES`.
- **Instruments** (`Local\I76SimTick`, `I76_SIM_TICK_LOG=<s>`): ticks, wall time, calls per gate, vehicle and
  player substeps per tick (read right after StepperBegin: `StepperNext` counts the stepper's +8 down to 0, so the
  value after the tick is always 0 - the frame log's "step count" column cannot show it), far-path ticks, leak checks
  (a moving object must start the next tick at the pose the last tick left; a pose equal to the last DRAWN pose is a
  leak, anything else an outside write), and a drawn-pose stall census per entity class (`I76_JUDDER_CENSUS=1` gives
  the same counters under `I76_RENDER_INTERP`).

Patch count with the tick on: 12 sim gates, 4 display hooks (camera call, render call, camera SetTransform, vehicle
class slot + StepperBegin call for counting), 14 draw-side holds, 7 cosmetic sites. None of them rescales a rate; the
current scheme's per-frame set (FRAMERATE_FIXES' 36 + 6 + 6 sites, COLL_WINDOW's 4, COLL_DEDUPE, INPUT_LATCH's 2, the AI
grid / clock / hold set, ENGINE_DT_FIX, REF_FPS) is off.

**Lab side build** `<lab>\builds\whole-sim-tick-20261017\Strlkup-wst2.dll` (md5 c059f270): this source plus
the lab-only drive keys with a latency probe (`drive-lat-block.c`), `I76_STEP_SEQ` and `I76_HEADLESS_ACTIVE`
(`make.ps1`). Installed only in the lab copies `game-wst` (headless, null renderers) and `game-tick` (the owner's
play copy). Harness: `<lab>\tools\whole-sim-tick\` (`wst-run.ps1`, `wst-batch.ps1`, `wst-queue.ps1`,
`wst_drive.py`, `wst_probe.py`, `wst_analyse.py`, `deskrun.py`).

**Harness notes.**
- Every boot runs on a **private desktop** (`deskrun.py`: CreateDesktop + CreateProcess with lpDesktop; the creator
  must stay alive until the child exits or the desktop dies with it and the child exits at once). No game window can
  reach the owner's desktop; keys go through the proxy's drive block, never `keybd_event`; phys-suite's
  `SetForegroundWindow` re-take is stubbed. Audio muted and read back by `with-lock.ps1`.
- Console lock: the owner's OWNER-TESTS window held `.console-owner` from 08:05 on its final `pause` (the test had
  finished at 08:11; no game ran). `wst-batch.ps1` parks such an idle owner lock (older than 60 min, no game running)
  for the length of one hold only and puts it back afterwards, unless his window has exited. Agent locks are never
  touched.

## 3. Measurements

Lab copy `game-wst` (headless twin, i76.exe 6319abf7, null renderers, 120 fps display cap) unless noted; side build
`Strlkup-wst2.dll` md5 c059f270 in every boot (read from the env record). Conditions: **tick66** / **tick33** = the
lab-step-33 preset minus every timing patch plus `I76_SIM_TICK_MS`; **step33** = lab-step-33 as its launcher runs it
(I76_FIXED_STEP 30 + the patch set) plus `I76_JUDDER_CENSUS=1`; **aa** = an independent second boot set of the same
condition (A/A). Every boot on a private desktop with its own seed; conditions interleaved, order reversed on even
rounds. Captures: lab `captures\whole-sim-tick-20261017` (gitignored), queues `queue\campaign1..4.txt`; tables from
`tools\whole-sim-tick\wst_analyse.py`. Spreads: 95 % t intervals over boots (boot = cluster); p = Fisher exact.

### 3.1 Correctness (the proxy's live counters, read from the running process at the end of each boot)

| condition | boots | ticks / wall s (min..max) | gate calls per tick (10 offline sites) | player / AI near substeps per tick | leaks / checks | hooks read back |
|---|---|---|---|---|---|---|
| tick66 | 4 | 15.007 (15.001..15.016) | 0.999..1.000 | 2.000 / 2.000 | 0 / 22 550 | 30 / 30 |
| tick66aa | 4 | 15.008 (15.004..15.012) | 1.000..1.000 | 2.000 / 2.000 | 0 / 23 498 | 30 / 30 |
| tick33 | 4 | 29.988 (29.977..29.997) | 0.999..1.000 | 1.000 / 1.000 | 0 / 43 764 | 30 / 30 |
| tick33aa | 3 | 29.990 (29.980..29.997) | 0.999..1.000 | 1.000 / 1.000 | 0 / 27 304 | 30 / 30 |
| play66 (game-tick, dgVoodoo, preset lab-tick-66) | 1 | 15.02 | 1311 each | 2 / 2 (step 33.333 ms) | 0 / 10 274 | 30 / 30 |
| play33 (game-tick, dgVoodoo, preset lab-tick-33) | 1 | 30.00 | 2618 each | 1 / 1 (step 33.333 ms) | 0 / 17 322 | 30 / 30 |

- The two network regen gates (0x403da6 / 0x403dd0) count 0 offline, as in stock. About 0.9 s of wall time per boot
  is dropped (frames owing more than one tick: the mission-load hitch), about 1 %.
- "Outside writes" (a pose changed between ticks by something other than the sim) are the harness's own car
  placements: 0 in the latency and combat boots, 12 per t05p boot (6 placements), 24 per t06 boot.
- The far-path share (`physics_StepVehicleFar`) is 76 % of vehicle ticks in every tick condition (the classification
  reads the last drawn camera, as 1997 read the previous frame's).
- **Rates per sim second (T13 idle, god, n 1 boot each).** `ai_FrameTick`'s fire gate is called 145 /s (tick66),
  287 /s (tick33), 288 /s (step33, its AI clock emulation at 30 fps): once per tick under the tick, as designed. Fire
  decisions that pass: 5.8 /s, 9.5 /s, **33.3 /s**. Hostile shots per sim minute 82 / 139 / 351, hits on the player
  59 / 34 / 186. For scale (different harness, parked T13, AI-DAMAGE-BALANCE.md s.5): retail 1.0 at the emulated P166
  fires about 107 rounds /min. The tick arms bracket retail; lab-step-33 is about 3 x over it. The flamer was not
  exercised (no flamer car in T13: flame hits 0 in every boot); hazards not measured separately.

### 3.2 Physics vs lab-step-33

T05 placed canyon jumps (56 +- 1 m/s, lateral +- 0.5 m, 6 per boot):

| condition | jumps (boots) | turned over | destroyed | take-off m/s | distance m | max air pitch deg | tumbling > 45 deg |
|---|---|---|---|---|---|---|---|
| tick66 | 18 (3) | 0 | 0 | 52.2 +- 2.1 | 208 +- 20 | 43 +- 21 | 10 / 18 |
| tick66aa | 12 (2) | 0 | 0 | 51.9 +- 3.9 | 204 +- 7 | 38 +- 45 | 5 / 12 |
| tick33 | 18 (3) | 0 | 0 | 52.6 +- 1.8 | 209 +- 18 | 40 +- 10 | 8 / 18 |
| tick33aa | 12 (2) | 0 | 0 | 52.2 +- 9.1 | 198 +- 66 | 38 +- 149 | 5 / 11 |
| step33 | 14 (3) | 2 | 1 | 52.2 +- 4.0 | 216 +- 47 | 57 +- 56 | 8 / 13 |
| step33aa | 12 (2) | 0 | 0 | 51.5 +- 2.4 | 212 +- 175 | 43 +- 111 | 5 / 11 |

Turned over: tick66 vs step33 0/18 vs 2/14 p 0.18; tick33 vs step33 0/18 vs 2/14 p 0.18; step33 vs its A/A twin
2/14 vs 0/12 p 0.48. **No difference resolved**; every mean distance inside the 1997 range (197-249 m).

T05 barricades (10 rams per boot at 20 m/s): knocked off per ram tick66 15/20 = 0.75, tick33 16/20 = 0.80, step33
13/20 = 0.65 (2 boots each; no pair differs, p > 0.4). The tick needs no collision window: the whole step's contacts
are swept once per tick. (The ram tool's "contact seen" flag reads 0 in every condition: a tool limit, not a result.)

T06 strip (1 boot per cell; the A/A twins agree to the printed digit): gravity 9.800 everywhere; accel time to 20 m/s
2.67 s (tick66) / 2.73 (tick33) / 2.73 (step33); steady yaw at 18 m/s 0.802 / 0.800 / 0.795 rad/s (n 2 each); ramp-A
30 jump air time 2.20 / 2.17 / 2.12 s. Body jounce (pitch-rate reversals per s in the accel phase) 1.00 / 1.36 / 1.18;
roll-rate reversals 0.00 / 0.27 / 0.18 (n 1: indicative only). The two schemes pass and fail the same retail-P166
fingerprint rows; the tick changes none of them.

### 3.3 Input latency (40 steer-key toggles per boot, mission T06, the proxy's latency probe)

| condition | boots | key -> first sim step ms (median, p90, max) | key -> first changed drawn frame ms (median, p90, max) |
|---|---|---|---|
| tick66 / aa | 1 + 1 | 37.5 / 25.6, 63 / 61, 67 / 67 | 37.7 / 25.9, 63 / 61, 67 / 67 |
| tick33 / aa | 1 + 1 | 18.1 / 14.7, 32 / 28, 33 / 30 | 18.5 / 14.8, 32 / 28, 33 / 30 |
| step33 / aa | 1 + 1 | 6.6 / 5.6, 14 / 13, 16 / 16 | 6.7 / 5.8, 14 / 13, 16 / 16 |

The latency is the wait for the next tick (uniform over 0..T): bounded by T, about T/2 typical (the A/A medians differ
by up to 12 ms at n 40: the wait is uniform, so medians are loose). The first changed frame follows the first sim step
within 0.3 ms in every arm: interpolation adds no lag of its own. (1997 at 15 fps had the same 0..67 ms wait plus its
frame time.)

### 3.4 Judder (drawn-pose stall census: a display frame whose drawn pose equals the last one while the object moved)

| condition | boots | player | AI vehicles | projectiles | camera |
|---|---|---|---|---|---|
| tick66 / aa | 4 + 4 | 0.7 % / 0.7 % | 0.4 % / 0.4 % | 3.3 % (T13, n 9 388) | 1.6 % / 1.6 % |
| tick33 / aa | 4 + 3 | 0.2 % / 0.1 % | 0.3 % / 0.5 % | 1.9 % (T13, n 14 491) | 1.1 % / 1.0 % |
| step33 / aa | 4 + 4 | 0.2 % / 0.2 % | 0.8 % / 0.8 % | 0 % (stepped every frame) | 1.0 % / 1.0 % |

(n = 22 000-112 000 frame-object samples per cell.) The tick draws AI cars smoother than the current scheme (which
interpolates only the player and the camera), the player equal at 33.3 ms and slightly worse at 66.7 ms. "Other
objects" stall 10-14 % in every condition including step33 (A/A spread 3 points): a census artefact of objects that
move intermittently, not a difference. Not judged by eye (headless); the owner's feel test is the remaining check.

**Not interpolated (drawn at tick rate):** smoke puffs (extrapolated between ticks instead), flamer streams and trails
(aged on the tick), the radar ping, HUD digits, texture animations; script cameras are interpolated only on frames
where no camera mode set the view.

## 4. Open problems

- AI fire decisions 3.5 x higher under lab-step-33 than under the 33.3 ms tick at the same call count (n 1 boot each):
  an interaction in the patch set's AI fire path, not explained; needs n >= 4 and a split by weapon before it is a
  finding.
- Flamer and stationary hazards not exercised (no flamer car in T13); a flamer mission boot is needed to show the
  draw-code holds keep damage per second on the tick.
- Latency is structural (the wait for the next tick). A hybrid (controls sampled and applied at display rate, the rest
  on the tick) would remove most of it but brings back a per-frame path; not built.
- The latency probe counts the first sim step and the first changed drawn pose after the key, not the photon on screen.
- n: latency 1 boot per arm (40 presses) + A/A, T06 1 boot, combat 1 boot; jumps 3 boots (18 jumps) per main arm.

## 5. Launchers (lab)

`<lab>\game-dd-20261003\TEST-tick-66.bat` and `TEST-tick-33.bat` run the lab copy `game-tick` (side build md5
c059f270, presets `lab-tick-66` / `lab-tick-33`, dgVoodoo.wide.conf) after the play66 / play33 boots passed the
correctness checks above. The daily driver, the golden copy, the Downloads portable and the committed
`music-fix/Strlkup.dll` are untouched.
