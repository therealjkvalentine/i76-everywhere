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
| AI team lists | 0x507da0 / 0x51f5d0 | not found (the retail AI summary is off) |

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
- **T06 ramp: not run.** The T06 bookmark exists (`tools\memtrace\make-t06-base.py`), but there is no route yet:
  - the opening skip lands the car at 'leap' (9260, 41535);
  - ramp A is reached only through a 90 degree junction 240 m before its foot, short of the lab's 38-44 m/s.
- **P133:** removed from configs, traces and docs (owner ruling 2026-10-15).
