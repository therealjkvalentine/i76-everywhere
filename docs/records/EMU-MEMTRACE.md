# Memory traces from the emulated 1997 PC (2026-10-15)

The owner's gold standard is the emulated **P166, software renderer, lowest detail** in 86Box (lab `emu\`):
320x200, visibility Near, every option off or low. All our fixes must end up on the same physics behaviour, measured
from game memory.

Since the evening of 2026-10-15 the reference exe is the **original March 1997 retail 1.0 `I76.EXE`** (owner's
decision). It runs with the owner's ripped discs. The GOG-built Gold CD exe is kept for comparison.

- **Where:** tools and raw traces are in lab `emu\`; this file has the results.
- **Not touched:** the daily driver and the golden copy. The golden exe was only read.
- **How runs were done:** headless par runs only (private desktop, no host input), with at most 2 of these VMs beside
  the owner's.
- **Tools:**
  - I76MEM, the per-frame logger;
  - I76DRV, the scripted and closed-loop driver;
  - parrun `--video`;
  - `tools\memtrace\*.py`.

  See lab `emu\README.md`, "Memory traces".
- **P133:** dropped by owner ruling. Its VM configs, traces and logs were deleted.

## Summary

> **Correction (2026-10-16 night): every retail 1.0 number below the address maps was measured in ARCADE physics.**
> The retail scripts copied the Gold-layout I76PLYR.DEF into the retail folder. Retail read its option flags from
> Gold bytes `01 00 00 00`: Arcade Phys. on. Player entity flag 0x10000 was set on every retail frame (T05 run 180103:
> 13,638 / 13,638; melee loop 185645: 13,703 / 13,703), and on no Gold frame. Gold numbers stay valid.
> Re-measured with a retail-layout file (option flags 0, flag 0x10000 on 0 frames in all 11 runs),
> EMU-T05-CLEAN.md:
> - **steady yaw, simulation physics:** retail 1.28 / 1.30 rad/s (n 8) vs Gold 1.34 / 1.41 (n 4), arcade retail
>   0.94 / 0.97 (n 4). The "Gold turns 45 % faster" finding was arcade mode; the remaining gap is 5-8 %.
> - **accel / brake unchanged:** t10 / t20 / t30 1.06 / 2.76 / 5.65 s, brake 84 m (sim, n 8).
> - **T05 from a repaired crest start:** retail sim n 9: foot speed 55.1 +- 1.8 m/s, jump 154 +- 48 m, 1 car
>   destroyed (fell short, inverted, CheckImpact rollover kill); Gold n 6: 56.9 +- 1.4 m/s, 191 +- 36 m, 0
>   destroyed. Arcade flips an inverted car upright instead, which is why no retail car was destroyed before.

- **2026-10-17 night (section 9): T06, flat road, retail AI, emulator calibration.**
  - **T06 and flat road, simulation physics:** retail (n 3) and Gold (n 6) steer and accelerate the same. Steady yaw
    1.60 / 1.62 vs 1.58 / 1.57 rad/s; 0-30 m/s 8.19 vs 8.22 s on a 1.2 % downhill. The fps differs: 28.1 vs 24.7.
  - **Ramp A from the driven approach** arrives at 33-35 m/s. That is below the lab's placed 38-44 m/s, at the edge
    between clearing and falling short: retail 1 of 3 cleared, Gold 2 of 3.
  - **Retail AI lists** 0x4edc30 / 0x505460 (team-add 0x408510), live in I76MEM.
  - **Calibration:** the emulated P166 runs Quake's 320x200 software renderer **about 20 % faster than a real P166**
    (44.7 vs 37.3 fps). Dhrystone +8 %, Whetstone -1 %, Doom -7 %. 86Box emulates no cache or memory latency: L2 and
    RAM read at L1 speed. So a real P166 probably runs I'76 about 15-20 % slower: a longer physics step, still one
    substep per frame, and the same physics constants.

- **Address maps.**
  - **Ours -> Gold CD exe:** high confidence. Same link, and every physics function is byte-identical.
  - **Gold -> retail 1.0:** matched function by function and validated live: g = 9.800, speed = |velocity|, parked
    rates exactly 0, HUD speedo = speed.
  - **The object / entity layout is the same in all three exes.**
- **Retail 1.0 is about 25 % faster than Gold** at the same P166 low-detail settings. With I76FPS, parked:
  - T04: 35.7 vs 28.4 fps;
  - T05: 33.4 vs 26.9 fps;
  - T13: 31.3 vs 22.6 fps;
  - melee, logger on: 37.4 vs 31.1 fps.

  So retail's physics step is about 26-30 ms (Gold: 31-38 ms). Both run one physics step per frame (99.5 %+ of
  frames).
- **Physics difference, 1.0 vs Gold.**
  - Static: Gold's `physics_StepVehicle` has a different lateral-factor clamp, a speed guard and terrain damage.
  - Measured: full keyboard steer at a held 18 m/s gives a **steady yaw rate of 0.94-1.00 rad/s in retail and
    1.34-1.59 rad/s in Gold**. That is n = 8 retail and n = 7 Gold repeats, with sd 0.01-0.09 within each. Gold also
    slides much more.
  - Unchanged: acceleration (0-10 / 0-20 m/s), braking, the substep rule, gravity, and the CheckImpact rollover rule.
- **Logger cost:** about 2 % of the frame rate. Detail:
  - all segments: -2.7 %;
  - the 20 s throttle segment: -1.2 %;
  - n = 4 boots each, with and without the logger;
  - in-mission coverage is 99.5 %+ of frames, with every record read after the frame's physics.
  - The no-timer variant costs -1.2 % but misses 15 % of frames, so it is not used.
- **In-session repeats** (owner ruling: no reboot per run). One boot runs 4 melee repeats, or 3 T05 repeats through
  Replay. Repeat 1 and the later repeats agree, and boot-per-run agrees with in-session (section 3). Restarts do not
  carry state.
- **T05 canyon:** 8 descents reached the ramp: 6 retail and 2 Gold.
  - **Outcome follows the foot speed:**
    - at >= 53 m/s the jumps reached or cleared the far side (Gold 57.3 m/s: 242 m; retail 53.4 m/s: 146 m);
    - at 46-50 m/s the car hit the far ramp's face and turned over (3 of 6 retail).
  - **No car was destroyed on landing.**
  - **The foot speed varies with the approach.** Each run is a 7-minute drive past the mission's enemies, and the
    car arrives with 55-70 % armour. The descent is therefore not a clean exe-vs-exe comparison yet.
- **Retail saves for the owner:** 'retail T04 start', 'retail T05 start' and 'retail T13 start', made in the retail
  exe. They are in lab `emu\results\saves-retail\`.
- **Music intent** is logged in both exes:
  - retail requests T05 -> track 6 and melee -> track 9, and plays track 15 in the shell;
  - Gold CD has no audio tracks, so its request is reset to -1.

  None of it could be heard: the host endpoint is muted.

## 1. Which exes, and the address maps

| exe | file | what it is |
|---|---|---|
| **retail 1.0** (the reference) | `C:\Program Files\Activision\Interstate '76\I76.EXE` on the w95pb disk, 1,019,392 bytes, md5 `6cc509ad` = the CD's `I76.EXE` (1997-03-15) | the March 1997 release. It needs the classic PIT (`pit_mode = 0`). It runs with disc 2 alone (`--cd I76_CD2.cue`; several runs had no disc 1 mounted) or with both discs |
| Gold CD exe | `I76GOLD.ISO \I76.EXE`, md5 `e1dca993` | the GOG 2017 Galaxy `i76.exe` (md5 `9a232dcc`) with one change: the import name `WIN32.dll` -> `WINMM.dll` (2 bytes). It is **not** a no-CD or otherwise patched exe |
| ours (lab RE, twin, driver) | golden `i76.exe`, md5 `6319abf7` | the GOG 2019 AiO exe (`60abf7bc`) plus the `u32x.dll` import rename |

### Ours -> Gold CD exe

The check is `emu\tools\memtrace\addrmap.py`; the full table is `addrmap-gold.md`.

- **Same link:** the section VAs are identical.
- **Differences:** 2,845 bytes differ in 58 runs. **None of them is in the physics, entity, stepper, CheckImpact or
  AI-vehicle code.**
- **Functions, high confidence.** Every function we use is byte-identical at the same VA:
  - `entity_TickVehicle` 0x463800;
  - `physics_StepVehicle` 0x438fd0;
  - `physics_CheckImpact` 0x436ff0;
  - the attitude solver 0x437230;
  - `object_Destroy` 0x4652b0;
  - `simclock_StepperBegin` 0x49cc20;
  - the music request functions 0x423320 / 0x423330.
- **Globals, high confidence.** Every global we read has the same set of referencing instructions, apart from
  references inside the differing runs.
- **Struct offsets, high confidence.** Byte-identical functions use them.
- **What does differ (AiO fixes):**
  - **simclock** (0x49c7f0-0x49cbd6): the same globals. AiO masks the tick; pristine stores the float uptime.
  - **Terrain lookups** 0x493160 / 0x4931c0 / 0x493550: AiO uses unsigned bounds checks, pristine signed. They differ
    only off the map edge.
  - **`ai_RecordDamageEvent` at 0x415815:** the attacker block is read at `+0x44` (Gold) vs `+0x10` (AiO). This is a
    real AI difference between our exe and the Gold CD exe.
  - Also: the MCI state handling, renderer and texture heaps, and file loading.

### Gold CD -> retail 1.0

The table is `emu\tools\memtrace\addrmap-retail.md`. Retail is a different build. Each function was matched by shape,
constants and call graph, then checked live.

| item | Gold CD | retail 1.0 |
|---|---|---|
| frame clock | 0x49c920 | 0x450fa0 |
| frame counter | 0x5a7e1c | 0x55f744 |
| sim_dt / sim_time / dt / time | 0x4fe420 / 0x5a7e70 / 0x4fe428 / 0x5a7e74 | 0x4db12c / 0x4db134 / 0x4db138 / 0x4db140 |
| `StepperBegin` (substep rule count = floor(sim_dt x 20) + 1, at most 20) | 0x49cc20 | 0x451250 (same rule) |
| vehicle tick / vehicle step | 0x463800 / 0x438fd0 | 0x429c70 / 0x472360 |
| `CheckImpact` (canyon kill: rates < pi/5, \|up.n\| > 0.8, inverted) | 0x436ff0 | 0x46fe20 (same gates and constants) |
| `object_Destroy` | 0x4652b0 | 0x42b790 |
| player root | `[0x54a264]` | `[0x4d3b64]` |
| scripted-player flag | 0x5244c0 | 0x505490 |
| game state | 0x4c2164 | 0x4a80f4 |
| CD track / playing / CD opened | 0x4ed800 / 0x524570 / 0x524674 | 0x4dc7a0 / 0x4dc7a8 / 0x4dde38 |
| AI team lists | 0x507da0 / 0x51f5d0 | **0x4edc30 / 0x505460** (team-add 0x408510; live, section 9.4) |

### Static physics difference, retail 1.0 vs Gold

> **Corrected 2026-10-16 (RETAIL-HANDLING-DIFF.md):** the three differences below are artefacts of the float-constant
> scan. Retail has the guard, the clamp and the 7.65 terrain damage as integer compares. The measured yaw / slide gap
> is the "Arcade Phys." option: it was on in every retail run (the Gold-layout I76PLYR.DEF misread by retail) and off
> in every Gold run.

`physics_StepVehicle` is not the same code. CheckImpact and the per-substep entity update are identical.

- **Gold** guards a lateral factor `1 - 0.75 (x / speed)^2` with `speed > 0.0001` and clamps it to [0.25, 1].
  Retail has neither the guard nor the clamp.
- **Gold** also tests `> 7.65` after the wheel updates and then applies terrain damage.
- **Retail** has an angle block scaled by pi and pi/4 that Gold lacks.

### Live validation (both exes, from the traces)

- g = **9.800**: the median vy slope over 8-frame airborne windows. Gold: 170 windows, p25 / p75 9.798 / 9.802.
- Speed (+0xac) = |velocity| (+0xbc) to 1e-5.
- Parked rates are exactly 0 in every settle phase (n = 15).
- The engine's HUD speedo field is within about 1 mph of speed x 2.237.
- Every frame follows the substep rule.

## 2. The logger (I76MEM.EXE) and its cost

- **Read-only:** Toolhelp32, `OpenProcess(PROCESS_VM_READ)`, `ReadProcessMemory`. It is built like the other probes
  (MSVC 2019, no CRT, PE 4.00, Win95-clean imports). It identifies the build by signature and refuses unknown exes.
- **One read per frame, after the physics.**
  - **When:** 15 ms after the frame's own start tick, i.e. the engine's GetTickCount at the top of the frame clock.
    That lands inside the render.
  - **Check:** every record is checked. The stepper count (entity +0x44c) must be 0, and the read must come at least
    4 ms after the frame start. 99.99 % of records pass.
  - **Rejected design:** the first build polled the frame counter and read at the frame start. Half its records were
    already past the physics, and it cost 1.9 ms per frame. It was dropped.
- **Per record** (324 bytes):
  - frame, start tick, sim_dt, dt, sim_time, time, game state;
  - player position (double), rotation, velocity, speed, pitch / yaw / roll rates, acceleration;
  - steer and throttle as applied, handbrake;
  - the stepper's step and count;
  - entity flags (0x4 airborne, 0x200 just landed, 0x8000 wreck), surface, ground normal, clearance;
  - armour and chassis, and engine rpm / gear / speedo (every 8 frames);
  - the nearest AI car (Gold only);
  - the music intent.
- **Cost of one ReadProcessMemory call** on Windows 95 in 86Box: 42-110 us. The logger makes 6.3 calls per frame,
  about 190-260 us.
- **Coverage:** in missions 99.5 %+ of frames are recorded (0-20 frames lost per 10-minute run). The skipped counter in
  `mem.frames.csv` counts the rest.

**Overhead.** Gold exe, Instant Melee, P166 low detail, frame rate from I76FPS in every condition, separate boots:

| condition | n | settle | throttle 20 s | after | all segments |
|---|---|---|---|---|---|
| I76FPS only | 4 | 33.51 +- 0.52 | 34.04 +- 0.65 | 34.67 +- 0.16 | 34.07 +- 0.29 |
| + I76MEM (default) | 4 | 32.47 +- 1.25 | 33.63 +- 0.17 | 33.38 +- 0.39 | 33.16 +- 0.50 (**-2.7 %**) |
| + I76MEM `/notimer` | 3 | 33.37 +- 0.28 | 33.83 +- 0.26 | 33.78 +- 0.57 | 33.66 +- 0.28 (-1.2 %) |

- **Default:** within the spread on the steady throttle segment (-1.2 %), but -2.7 % over all segments.
- **`/notimer`** (no `timeBeginPeriod(1)`) costs half as much, but it reads on Windows 95's 13 ms Sleep grid and
  **misses 13-17 % of the frames**.
- **Decision:** physics traces use the default mode. Frame-rate figures come from I76FPS-only runs.
- **Also running:** the closed-loop driver (I76DRV, a HIGHEST-priority 30 ms loop) runs during driven phases and costs
  a little more.

## 3. Reference runs

All runs used par base `w95pb-par-sb16.img`: the saves snapshot plus the Sound Blaster 16 driver, with 86Box audio
muted on the host. `tools\memtrace\gen_scripts.py` generates the scripts.

Traces are in lab `emu\results\memtrace\<run>\` (on disk, not in git; the summary JSON is in git).

- **`mem.phys.csv`:** the lab telemetry columns (`phase t sim_time sim_dt dt step_count x y z vx vy vz speed pitch_rate
  yaw_rate roll_rate rot1 rot4 rot6 rot7 rot8 flags throttle steer clearance rpm gear handbrake`), then the emulator
  columns and a `rep` column.
- **Phase names** follow the lab's phys-suite (`canyonD<rep>`, `accel`, `brake`, `steerR`, `steerL`), so the lab's
  `landing-analyse.py` and `phys-analyse.py` read the files directly.

### Instant Melee

The scripts are `ref-melee-*` and the in-session `ref-melee-loop-*` (4 repeats).

- **Phases:**
  - settle: 8 s parked;
  - accel: 12 s of full throttle from rest (keyboard, typematic repeats);
  - brake: brake to a stop;
  - steerR / steerL: 3 s of full keyboard steer at a held 18 m/s;
  - cruise: 10 s at a 25 m/s cap;
  - parked while the AI attacks.
- **Caveats:**
  - The melee spawn point is random.
  - The crater floor is not the lab's flat T06 road: the start runs downhill.
  - Accel, yaw and roll are therefore this map's numbers. Compare exe with exe, not with ERA-ENVELOPE's T06 rows.

Mean +- sd (n repeats). "boots" = one boot per repeat; "loop" = 4 repeats in one boot.

| metric | retail loop | retail boots | Gold loop | Gold boots |
|---|---|---|---|---|
| fps (logger on) | 37.5 +- 0.8 (4) | 37.2 +- 0.7 (4) | 31.0 +- 0.4 (4) | 31.2 +- 0.4 (3) |
| physics step, mean ms | 26.6 +- 0.5 | 26.8 +- 0.5 | 32.2 +- 0.4 | 31.9 +- 0.4 |
| frames with 1 step | 99.8 % | 99.7 % | 99.6 % | 99.5 % |
| sim_dt p5 / p50 / p95 ms | 24 / 26 / 29 | 24.5 / 26.5 / 29.5 | 28 / 31 / 38 | 29 / 31 / 38 |
| parked max rate | 0 | 0 | 0 | 0 |
| 0-10 / 0-20 / 0-30 m/s, s | 1.06 / 2.79 / 5.57 | 1.04 / 2.74 / 5.53 | 1.06 / 2.73 / 5.44 | 1.04 / 2.72 / 5.67 |
| distance in 10 s, m | 267 +- 11 | 271 +- 3 | 274 +- 4 | 273 +- 2 |
| brake distance, m | 87.6 +- 2.5 | 85.6 +- 2.0 | 88.8 +- 4.0 | 93.6 +- 4.0 |
| **steady yaw, right / left, rad/s** | **0.94 / 0.97** | **0.96 / 1.00** | **1.34 / 1.41** | **1.39 / 1.59** |
| steer ramp to 0.9, s | 2.41 | 2.41 | 2.40 | 2.40 |
| roll / pitch reversals per s (cruise) | 3.6 / 4.2 | 3.5 / 3.9 | 2.7 / 2.8 | 2.6 / 2.1 |

**Loop and boots agree within their spreads**, and repeat 1 of the loop sits inside the spread of repeats 2-4. Retail
loop repeats 1 / 2 / 3 / 4:

- 0-30 m/s: 5.53 / 5.40 / 5.43 / 5.91 s;
- yaw right: 0.96 / 0.96 / 0.94 / 0.89 rad/s.

In-session restarts therefore carry no state.

### T05 canyon

The scripts are `ref-t05-*` and `ref-t05-loop-*` (3 repeats through Replay).

- **Start:** the 'T05 start (emu)' bookmark.
- **Opening:** the camera sequence is skipped with Esc. The FSM's isKeypress tests for the MAIN_MENU key, and I76DRV
  taps it only while the player is script-driven.
- **Route:** closed-loop (I76DRV `drive`, the lab's pure-pursuit rule):
  1. east, south and west on the mission's roads;
  2. up the hill road's switchbacks to the crest at 12 m/s;
  3. stop;
  4. the lab's descent: full throttle on the phys-suite route over the canyon ramp aaramp4.
- **Repeats:** Options Menu > Abort Mission > **Replay** (row 1 of the trip's Abort Mission page) restarts the mission.
  Esc then skips the intro cutscene.

| run | exe | arrived at the crest with armour | foot speed m/s | jump distance m | turned over | destroyed |
|---|---|---|---|---|---|---|
| 161149 | Gold | 6114 / 9600 | 53.4 | 101 (hit the far ramp) | no | no |
| 182548 | Gold | 5253 / 9600 | **57.3** | **242** (cleared) | no | no |
| 162842 | retail | 6552 / 9600 | 49.7 | 108 (hit the far ramp) | no | no |
| 180103 | retail | 6805 / 9600 | **53.4** | **146** (far side) | no | no |
| 183450 | retail | 5948 / 9600 | 46.2 | 109 | **yes** | no |
| 183650 | retail | 5648 / 9600 | 47.9 | 99 | **yes** | no |
| 190613 rep 1 | retail | 5561 / 9600 | 49.3 | 94 | **yes** | no |

- **Not reached:** 5 further attempts did not reach the ramp.
  - 3 wrecks against enemy12 (`t05cm03`), which is parked on the hill road at (8408, 44018). The route now passes 8-10
    m south of it.
  - 2 loop repeats stuck on a slope.
- **Turn-over mechanism:** the turn-overs happened after hitting the far ramp's face below 50 m/s. They are not the
  lab's landing-bounce rollover: no car was destroyed by CheckImpact.
- **Foot speed:** 46-57 m/s within each exe, following the approach and damage. The lab's descents started repaired
  at the crest (about 60 m/s).
- **Rerun needed:** a clean comparison needs a damage-free start at the crest, i.e. a bookmark saved there.

### Frame rate (I76FPS, 70 s parked after the opening, P166 low detail)

| scene | retail 1.0 | Gold |
|---|---|---|
| T04 | 35.72 +- 0.15 (n 3) | 28.40 +- 0.29 (n 2) |
| T05 | 33.35 +- 0.39 (n 3) | 26.87 (n 1) |
| T13 | 31.30 +- 2.34 (n 3, combat) | 22.59 (n 1) |
| Instant Melee | 38.4-40.0 (n 1, no sound driver) | 33.6-34.1 (n 4, no sound driver) |

- **The Sound Blaster 16 driver** costs Gold about 5 %. T04 was 29.75 fps without it in RESULTS.md, 28.4 fps with it
  here.
- **Retail is faster in every scene** (+24-39 %). So the retail reference's physics step is about 28-30 ms, not the
  30-38 ms the Gold runs gave.

## 4. Retail 1.0 vs Gold: per behaviour

| behaviour | retail 1.0 | Gold | difference |
|---|---|---|---|
| step pattern | 1 step per frame, 26-30 ms (higher fps) | 1 step per frame, 31-38 ms | the frame rate, not the rule (same `StepperBegin`) |
| gravity | 9.800 | 9.800 | none |
| parked rates | 0 | 0 | none |
| accel 0-10 / 0-20 m/s | 1.05 / 2.76 s | 1.05 / 2.73 s | none |
| accel 0-30 m/s | 5.55 s | 5.55 s (spread 0.2) | none |
| braking from 50 m/s | 86-88 m | 89-94 m | small; Gold slightly longer |
| **steady yaw, full keyboard steer, 18 m/s** | **0.94-1.00 rad/s** | **1.34-1.59 rad/s** | **Gold turns about 45 % faster and slides** (same steer input ramp: 2.41 s) |
| roll / pitch reversals | 3.5 / 4.0 per s | 2.7 / 2.4 per s | more body motion in retail (crater floor; noisy) |
| canyon rollover rule | the same CheckImpact code | | none (static) |
| canyon jumps | 6 jumps, 3 turned over after hitting the far ramp, 0 destroyed | 2 jumps, 0 turned over | confounded by foot speed (approach damage) |
| T06 ramp | not run | not run | needs a route (notes) |
| AI | AI summary off (no team lists found) | nearest AI logged | the Gold vs AiO `ai_RecordDamageEvent` difference is static only |

**The yaw difference is the key finding** (cause: Arcade Phys. on in the retail runs only; see RETAIL-HANDLING-DIFF.md). Retail and Gold use the same keys (the steer ramp is identical) at the
same held speed. Gold's yaw rate is about 45 % higher, and Gold is in the skid state (flag 0x2) for 14-100 % of the
window, against 0-22 % in retail.

The static diff points at `physics_StepVehicle`'s lateral factor. Caveat: each exe runs with its own data (I76.ZFS,
vehicle definitions). The melee car may differ between 1.0 and Gold data, so "exe" here means exe + its data.

## 5. Video

- **86Box 6.0 has no video recorder** (screenshots only; its "Record" item is the cassette drive).
- **How video is made:**
  - `parrun --video 30` captures the 86Box window on the private desktop with **PrintWindow** (about 5 ms per frame,
    0.03-0.4 % repeated frames).
  - It pipes the frames to the lab-local ffmpeg 9.0.2: the gyan.dev essentials build, sha256 checked
    (`i76-uncap-lab\tools\ffmpeg\VERSION.txt`), not installed system-wide.
  - Encoding: libx264 ultrafast, one thread, BELOW_NORMAL priority.
- **BitBlt is not used.** The first version did a window-DC BitBlt (1 ms per frame), but on the never-shown desktop it
  returned the **owner's screen pixels** wherever other windows covered the same area. Those recordings were deleted.
- **Cost to the VMs:**
  - in missions a recording VM ran at 0.85-0.90 of real time, against 0.97 without recording (2 VMs plus the owner's);
  - guest-time measurements (frame counter, GetTickCount, sim_dt) do not depend on host speed.

Clips are in lab `emu\results\writeup\video\`:

- `retail-p166-melee-accel-brake-steer.mp4`: 50 s of the melee phases on retail 1.0.
- `gold-p166-melee-accel-brake-steer.mp4`: the same on Gold, for the yaw comparison.
- `retail-p166-t05-descent-canyon.mp4`: the full-throttle descent and the canyon jump (49 m/s, hits the far ramp,
  turns over), filmed by the mission's own jump camera.

## 6. Sound and music intent

- **Sound Blaster 16 driver.** A scripted Add New Hardware run installed it in the guest (`scripts\sb16-install.txt`):
  - the files came from the Windows 95 CABs on the data disk;
  - the Version Conflict prompts were answered "keep";
  - it found the SB16 and installed `SB16.VXD`, `SB16SND.DRV` and `SBFM.DRV`;
  - the new snapshot is `images\w95pb-hdd-sb16-20261015.img` (the base snapshots were not touched);
  - the par base is `par\base\w95pb-par-sb16.img`.
- **Audible proof: not obtained.**
  - The host's default endpoint is muted: `loopwav x 0` reports mute 1, level 0.24. That is the owner's state and was
    left unchanged.
  - A WASAPI loopback capture with 86Box unmuted recorded only zeros.
- **CD audio and music intent** (I76MEM's music fields):
  - **retail 1.0 with the ripped disc 2:**
    - the shell plays **track 15** (playing = 1, loop-one = 1);
    - melee requests **track 9**;
    - T05 requests **track 6**;
    - in missions the playing flag stays 0 until the options menu re-requests the track (playing = 1 after
      Abort Mission).
  - **Gold CD exe:** the mission's WRLD track is requested, then reset to -1, because the Gold ISO has no audio tracks
    (CD opened = 1).
  - **Comparison with the lab's music proxy** (`docs\MUSIC-TRACK-MAP.md`):
    - T05 -> 6 matches the per-mission table;
    - the retail shell's 15 matches "1997 menu 15, plays alone and loops";
    - the proxy plays runs of mp3s (AiO rule) instead of one looping track.

## 7. What the lab replay needs next

1. **A damage-free T05 start at the crest.** Done 2026-10-16 (EMU-T05-CLEAN.md): I76DRV `place` + `repair` at the
   lab's crest start, retail sim n 9, Gold n 6. Still open: more retail n for the destruction rate (1 / 9).
2. **A frame-dt replay mode in the proxy.** Feed the logged per-frame `sim_dt` (whole ms, from `mem.frames.csv`) and
   the applied steer / throttle per frame, so the lab twin steps through the same dt sequence.
3. **The same start state.** Position, rotation, velocity and rates from the trace's first frame of a phase. This is
   the lab trainer's placement, at the retail reference's step (26-30 ms, not the 30-38 ms Gold gave).
4. **Re-baseline the envelope candidate on retail.** Retail's P166 low-detail steps are about 26-30 ms (37-38 fps in
   melee, 33-36 fps in missions), shorter than the Gold-based e29 / e33 profiles. Gold's yaw (and slide) is about 45 %
   above retail. Our exe (AiO = Gold physics) carries that too, so "stock" handling should be decided against retail.
   *Done 2026-10-17 (ENVELOPE-RETAIL-REBASE.md).* Retail's steps: 27 ms in melee, 32-35 ms in missions. The candidate
   stays at 30 ms. The handling gap on the T06 strip is the lab car, not the step.
   Melee was not run, because it cannot run headless.
5. **T06 ramp and flat-road runs on retail.**
   - T06: route design from the 'leap' point after the opening skip.
   - Flat road: a straight on the T05 canyon road (z 43910, x 7380-6900) or the T06 DRIVE strip.
6. **The AI summary for retail:** find the 1.0 vehicle / team lists.

## 8. Notes and incidents

- **The saves snapshot carries the lab's `INPUT.MAP`** in `C:\I76GOLD`: throttle W, brake S, steer A / D, file dated
  2026-10-15 04:52. The stock Gold map is the keypad.
  - The first T05 attempts drove nothing: binding 0 of the input table (0x53ae90) tested scan 0x11 (W).
  - The retail folder has the stock keypad map.
  - The scripts now set the keys explicitly.
- **I76DRV's control loop ran at about 4 Hz** at normal priority, because the game never sleeps. It now runs at
  HIGHEST priority with a 30 ms period.
- **Melee spawn points are random.**
- **Two queued runs collided** on the same run id (same tag in the same second). One of them lost its screenshots
  folder, and its orphaned 86Box was closed.
- **Some queue lines carried a CR,** so the second CD (disc 1) was not mounted in those retail runs. Retail ran
  normally with disc 2 alone.
- **T06 ramp: run on 2026-10-17, section 9.3.** The T06 bookmark exists (`tools\memtrace\make-t06-base.py`). The
  2026-10-15 notes on the route:
  - the opening skip lands the car at 'leap' (9260, 41535);
  - ramp A is reached only through a 90 degree junction 240 m before its foot, short of the lab's 38-44 m/s.
- **P133:** removed from configs, traces and docs (owner ruling 2026-10-15).

## 9. Night of 2026-10-16 / 17: T06 and flat road, retail AI lists, emulator calibration, clips

All runs: P166, software renderer, lowest detail, headless par runs. Every retail run in this section used the
retail-layout `I76PLYR.DEF` (simulation physics; the correction at the top of this file), except where marked
**arcade**. Lab tools: `emu\tools\memtrace\gen_t06.py`, `jumps_emu.py`, `ai_summary.py`, `tsc_mhz.py`,
`serial_descents.py`, `gen_video.py`; `emu\tools\bench\` (the calibration kit); I76DRV `drive ... LOOKT KD`, `ent`,
`tsc`; I76MEM retail AI lists and a commit every 64 writes.

### 9.1 Tools and two lost runs

- **Descent controller v2** (I76DRV `drive` with LOOKT 800, KD 300). The look-ahead is max(25 m, 0.8 s of travel),
  and the cross product is taken 0.3 s ahead with the yaw rate. The plain lab rule (25 m, bang-bang) made the old
  retail run 183450 weave +-40 m across the straight at 45 m/s. v2 drives the straight within 2 m.
- **`ent`** logs armour, chassis and the engine block; **`tsc`** logs RDTSC / QPC / GetTickCount for the clock check
  (9.5).
- **Two 1-hour T05 loops (222447 retail, 222517 Gold) lost their traces.** The host then carried 4-6 VMs from several
  agents (speed 0.61), the runs hit the 3600 s timeout, and `MEM.BIN` came back with 0 bytes: Windows 95 had never
  updated its directory entry. I76MEM (2026-10-16b) now commits the file every 64 writes (about 25 s).
- **What the serial log kept** (`serial_descents.py`, 0.5 s resolution). Both runs were **arcade** retail / Gold, from
  the natural approach, with the v2 controller:
  - rep 1: foot 53.6 m/s (retail) and 53.8 m/s (Gold), both past the far lip;
  - rep 2: both cars stuck on the climb and never descended.
- **Approach damage does not reach the engine.** At the crest both cars had lost the front and rear armour (sides
  0 / 1194 / 59 / 0), but the engine health factor was f = 1.000. The car's power was intact.
- **No crest bookmark is possible.** I'76 has no in-mission save: the Options Menu offers Abort Mission (Replay /
  Reconfigure / Abort / Exit Game), Play Options, Graphic Detail and Audio Control. The damage-free crest start is
  therefore made in memory (I76DRV `place` + `repair`), in EMU-T05-CLEAN.md (the other lane). This section adds no T05
  statistics beyond the two descents above, plus one video descent (9.6).

### 9.2 T06 route and phases (`gen_t06.py`)

- **Geometry.** From the pristine `t06.msn` (i76mod `show RDEF/RSEG#n`):
  - **RSEG 15:** the opening skip leaves the car on x 9260, heading +z (y 13.5 -> 9.2 over 350 m, a 1.2 % downhill
    grade). It then curves west, up to a plateau at y 38.
  - **RSEG 14:** the ramp-A run-up, x 7935, from the junction at z 42520 to the foot at z 42730. It drops from
    y 38 to y 17.5 between z 42550 and 42640, and is flat after that.
- **Per repeat:**
  1. stop: the opening skip leaves the car rolling at about 29 m/s;
  2. settle 8 s: the car rolls back to 3-4 m/s on the grade, so it is not a parked test;
  3. accel 10 s;
  4. brake;
  5. steerR / steerL: 3 s of full keyboard steer at a held 18 m/s (`steady`);
  6. cruise: RSEG 15 at a 25 m/s cap (the wobble metric);
  7. the corner, then full throttle along x 7935 over ramp A (phase `jump<k>`).
- **Repeats** go through Options Menu > Abort Mission > Replay.
- **Routes tried for the corner:**
  - **arc** (125 m radius): hit an obstacle at (7989.5, 38.5, 42509) in 3 of 3 repeats (28.8 -> 17 m/s). No ODEF
    object is there, and T06 has no LDEF fences.
  - **B** (off-road to the south, then straight up x 7935): stuck at (8216, 42447) in 2 of 2.
  - **A** (on the road to the junction at 12 m/s, a tight right turn): the route used for the results.

### 9.3 T06 and flat road, retail 1.0 vs Gold (simulation physics)

Runs: retail 002005 (3 repeats in one boot); Gold 003316 and 005818 (3 + 3).

**Ramp A, route A** (`jumps_emu.py` with the lab's `jumps-analyse` judge; cleared = landed beyond z 42800):

| run / rep | exe | foot speed m/s | lateral m | apex y | distance m | outcome |
|---|---|---|---|---|---|---|
| 002005 / 1 | retail | 34.3 | +0.2 | 27.6 | 32.2 | short (in the ravine, upright) |
| 002005 / 2 | retail | 34.5 | -0.2 | 27.6 | 32.1 | short, turned over |
| 002005 / 3 | retail | 34.8 | -0.1 | 27.9 | 49.8 | **cleared** |
| 003316 / 1 | Gold | 33.2 | +0.2 | 27.9 | 50.4 | **cleared** |
| 005818 / 1 | Gold | 37.6 | +0.0 | 28.0 | 50.1 | **cleared** |
| 005818 / 3 | Gold | 28.6 | +0.4 | 26.2 | 37.7 | short |

- **Gold reached the ramp in 3 of 6 repeats.**
  - In 003316 rep 2 the car spun round under braking (fwd -1.00 after the brake) and lost the route.
  - In 003316 rep 3 and 005818 rep 2 the car overshot the 12 m/s right turn at the junction and swung back. It then
    stuck at (7992, 42540), next to the arc's obstacle. Retail made the same turn 3 of 3 times.
- **Retail arrives at 34.5 +- 0.3 m/s** (n 3); Gold 28.6-37.6 (n 3).
- **Ramp A sits at the edge between clearing and falling short.** With the driven approach, both exes arrive at
  33-35 m/s, below the lab's trainer-placed 38-44 m/s (where W95-18 cleared 30 / 30). Clearing and falling short
  then alternate in both exes. The jump distance is bimodal (32 or 50 m): the car either lands past the ravine or
  in it.
- **The same pass, filmed, cleared:** 34.1 m/s, 49.1 m (run 012715, 9.6).

**Flat road** (RSEG 15 x 9260, 1.2 % downhill; the accel starts at 3-4 m/s, see 9.2; mean +- sd):

| metric | retail (n 3) | Gold (n 6) |
|---|---|---|
| fps / physics step | 28.1 +- 0.1 / 35.3 ms | 24.7 +- 0.4 / 39.1 ms |
| 0-10 / 0-20 / 0-30 m/s, s | 0.80 / 3.43 / 8.19 | 0.81 / 3.45 / 8.22 |
| distance in 10 s, m | 225 +- 3 | 224 +- 4 |
| brake from 33 m/s, m | 50.5 +- 0.9 | 49.0 +- 2.4 (n 4; 2 repeats spun or were cut short) |
| steady yaw, right / left, rad/s (at 16-18 m/s) | **1.60 +- 0.04 / 1.62 +- 0.02** | **1.58 +- 0.07 / 1.57 +- 0.16** |
| slide share during the steer | 0 / 0 | 0 / 0.08 |
| roll / pitch reversals per s (cruise, winding road) | 1.89 +- 0.09 / 3.09 +- 0.21 | 1.71 +- 0.15 / 2.62 +- 0.29 |

- **In simulation physics, retail and Gold steer the same on this road.** The steady yaw is equal within its spread.
  The flat-road accel is the same to 0.03 s.
- **What differs is the step.** Retail runs this scene at 28 fps (35 ms step), Gold at 24.7 fps (39 ms).
- **Gold's spread is wider:** one left steer slid at 21 m/s, and two brakes spun.
- **Instant Melee repeats this** (sim physics, n 1 each, runs 011503 / 010954): yaw 1.32 / 1.28 (retail) vs 1.25 /
  1.27 (Gold); 0-30 m/s 5.45 vs 5.17 s; 34.6 vs 31.0 fps.

### 9.4 Retail AI lists

- **Found by function matching.** Gold's team-insert function 0x409850 (8 lists of 64 slots at 0x507da0, counts at
  0x51f5d0) has its retail counterpart at **0x408510**:
  - the same AI-brain offsets (+0x9d14, +0xa818, +0xa82c, +0xa714);
  - the team index computed as `and 0x70000; shr 0x10`, where Gold has `shr 0x10; and 7`;
  - lists at **0x4edc30** (0x100 apart) and counts at **0x505460**.

  The retail-handling lane found the same addresses statically. I76MEM 2026-10-16b reads them.
- **One Instant Melee run per exe** (`ai_summary.py`; the parked 30 s 'ai' phase):

| run | exe | AI cars | nearest within 30 m after | closest m | hits on the player / damage | nearest AI speed p50 |
|---|---|---|---|---|---|---|
| 011503 | retail | 1 (alive) | 8.2 s | 5.2 | 16 / 370 | 17.7 m/s |
| 010954 | Gold | 1 (alive) | 4.9 s | 3.4 | 11 / 450 | 15.0 m/s |

- **Live check:** the retail list holds the one melee opponent; its distance, speed and the damage on the player
  move together. n = 1 per exe: this shows the lists work, not that the two AIs behave alike.

### 9.5 Emulator calibration: is the emulated P166 a real P166?

**Method.** The P166 VM booted plain DOS 7 from a floppy (`tools\bench\make-bench.py`; the CMOS boots A: first) and
ran period benchmarks with published real-P166 results:

- id's Quake shareware 1.06, `timedemo demo1` and `demo3`, at the DOS default 320x200, `-nosound`;
- Doom 1.9 shareware, `-timedemo demo3`, defaults;
- Roy Longbottom's 1997 DOS Classic Benchmarks (Dhrystone `DHRY1OD`, Whetstone `WHETCOD`, the bus-read test `BUSDOS`).

The binaries were downloaded into their own folders and checked against published md5s where one exists (quake106.zip
`8cee4d03`, doom19s.zip `244d1814`; dostests.zip `c66adc9a`). They were never run on the host; images\ is gitignored.

**Sessions.** 3 sessions (runs 004453, 011531, 013305; run 233026 for Doom and BUSDOS only). Every session ran in
real time: guest RTC / host clock 0.993-1.005, and the screenshots checked show 86Box's toolbar at 99-102 %. The VM carried 1-3 86Box
instances on the host.

| benchmark | emulated P166 (n) | real Pentium 166 | ratio | source of the real figure |
|---|---|---|---|---|
| Quake timedemo demo3, 320x200 | **44.7 +- 1.0 fps** (9; session means 46.0 / 43.8 / 44.5) | **37.3 fps** | **1.20** (1.17-1.23) | thandor.net/benchmark/33 (Quake 1.08, 430VX board, `-nosound`) |
| Quake timedemo demo1, 320x200 | 46.3 +- 0.4 fps (9) | - | - | (no P166 demo1 figure found) |
| Doom -timedemo demo3 | 81.47 fps (12: 916-917 realtics for 2134 gametics) | 88.08 fps | **0.93** | thandor.net/benchmark/32 (Doom 1.9S, 430VX) |
| Dhrystone 1.1 (DHRY1OD) | 261.8 +- 1.2 VAX MIPS (3; one read from the screen) | 241.87 | **1.08** | thandor.net/benchmark/34 |
| Whetstone (WHETCOD) | 109.3 +- 0.4 MWIPS (2) | 110.62 | **0.99** | thandor.net/benchmark/35 |

**Memory hierarchy (BUSDOS).** Millions of loads per second over 4 KB (L1), 64 / 256 KB (L2) and 2048 KB (RAM):

| test | emulated P166 | real Pentium 100 (Longbottom, `BusRes.TXT` in dostests.zip, 1997) |
|---|---|---|
| 32-byte stride (a cache-line miss per load past L1) | 271 / 303 / 296-302 / 269-274 | 90.7 / 6.6 / 3.1 |
| every word (4-byte stride) | 292-294 / 295-296 / 296-299 / 291-295 | 97.2 / 31.1 / 18.7 |

- **The emulated machine has no memory hierarchy.**
  - L2 and RAM read as fast as L1. 86Box 6.0 `cpu_update_waitstates()` adds no memory cost once the internal cache is
    enabled, so a miss is free.
  - Clock-scaled to 166 MHz, a real P5 reaches about 160 L1 loads per µs. The emulated one reaches 292: the recompiler's
    pairing model also pairs loads that the real L1 does not deliver.
  - A real 66 MHz bus serves a missing line at roughly 3-5 per µs. The emulated one serves 270.
- **CPU clock.** Guest RDTSC against guest QPC is 166.666 MHz (I76DRV `tsc`, T06 runs). Against the host clock it is
  165.5-165.8 MHz in the missions (speed 0.993-0.995). 86Box ran the clock at the right rate; the difference is the
  work done per cycle.

**Verdict.**

- **The emulated P166 is not a cycle-faithful P166.** It is about right on code that stays in L1:
  - integer +8 % (Dhrystone);
  - floating point -1 % (Whetstone).

  It is faster on anything that misses the cache, because memory latency is not emulated.
- **Software 3D rendering is that case.** Quake's 320x200 software renderer, the closest period workload to I'76's,
  runs **about 20 % faster (17-23 %) than on a real P166**. That is about the speed of a real Pentium 200 (41.4) to
  Pentium MMX 233 (47.7) on the same thandor table.
- **Frame-buffer-bound code runs slower.** Doom is 7 % slower; its time goes into VGA writes, and the video card
  differs from thandor's.
- **So yes: emulation inaccuracy very likely speeds I'76 up.** If I'76's software renderer behaves like Quake's, a real
  P166 at the same settings runs it at about 1 / 1.2 of the emulated frame rate:
  - retail sim T06 28.1 fps -> about 23-24 fps (step 35 -> about 42 ms);
  - retail sim melee 34.6 fps -> about 29 fps (step 29 -> about 35 ms);
  - the range is 0.81-0.85 x fps on the Quake spread, and nearer 1.0 if I'76's frame is dominated by the blit (the Doom
    case).
- **What that changes in the physics.** Sim time is real time either way. Only the step size depends on the fps, and
  it is still one substep per frame on a real P166: the substep rule floor(sim_dt x 20) + 1 gives a second substep
  only past 50 ms. So the real-box step would be about 15-20 % longer than the emulated reference. That is between
  this rig's retail and Gold steps, and short of W95-18's 55 ms frame. No physics constant changes. The quantities that
  follow the step (jump distance, landing kill rate, roll limit cycle; ERA-ENVELOPE) would sit between the emulated
  retail and Gold values.
- **Limits.**
  - One published real system per benchmark (thandor's 430VX board; Quake 1.08 vs our 1.06).
  - The emulated board is a 430HX with an S3 Trio64.
  - The Quake ratio is a proxy for I'76, not an I'76 measurement. A real P166 running the retail exe is the only direct
    check.

### 9.6 Clips (PrintWindow capture, 30 fps, 0 repeated frames; lab `emu\results\writeup\video\`)

- `retail-sim-p166-t05-crest-descent-jump.mp4` (40 s, run 012011): a placed + repaired crest start, the v2 descent,
  foot 57.0 m/s. The car hits the far ramp's face (88 m) and turns over. Not destroyed.
- `retail-sim-p166-t06-flat-accel-brake-steer.mp4` (32 s, run 012715): settle, accel, brake, steerR, steerL on RSEG 15.
- `retail-sim-p166-t06-ramp-a.mp4` (30 s, run 012715): the route-A corner and ramp A at 34.1 m/s. Cleared, 49 m.

### 9.7 Incidents

- **VM limit exceeded on the shared host.** From 22:32 several agents' runs overlapped this lane's, and the host
  carried up to 6 VMs (this lane kept to 2). The T05 v2 loops ran at 0.61 of real time and lost their traces (9.1).
  Everything in 9.3-9.5 ran with 1-3 VMs on the host, in real time (0.94-1.00 in missions).
- **Quake quirks.**
  - Started from the command line, Quake's demo loop counter is 0. The demo's closing disconnect then goes to
    CL_NextDemo, playback runs past the end of `demo1.dem` inside PAK0, and Quake dies with "Demo message >
    MAX_MSGLEN". The fix is `+map start` first, as thandor's "new game, then timedemo".
  - `quit` outside the console opens the Y/N menu; `+toggleconsole` goes first.
  - Three sessions sat at a prompt until the host timeout. Their results were read from the data disk.
- **Dhrystone and Whetstone** ask their closing questions from the BIOS keyboard. `STUFF.COM` (107 bytes, written by
  `make-bench.py`) puts 13 Enter + 2 Space keystrokes into the BIOS buffer first.
