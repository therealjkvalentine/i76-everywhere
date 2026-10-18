# Lab frame-dt replay of the emulator memory traces (2026-10-16/17 night)

EMU-MEMTRACE.md section 7, items 2 and 3: replay a per-frame memory trace of the emulated 1997 PC through our exe with
the same per-frame dt, the same applied inputs and the same start state, and diff the two frame by frame.

- **Where:** proxy switch `I76_REPLAY` in `music-fix/replay.c` (main repo); tools in lab `tools\replay\`; run logs in
  lab `tools\replay\runs\` (CSV on disk, diff summaries `*.json` in git).
- **Exe:** the lab copy `game-replay` (a copy of the twin `game-dd-20261003\Interstate 76`: i76.exe 6319abf7 = ours, Gold
  physics). Proxy: a side build in lab `builds\replay\` (the committed `music-fix\Strlkup.dll` was not rebuilt).
- **Not touched:** the daily driver, the golden copy (read only, for an exe diff), the portable install. No 86Box VM was
  started by this lane. Every live run took the console lock (`tools\replay\with-lock.ps1`) and stopped only its own
  game process.
- **Session:** james was DISCONNECTED all night (query session `Disc`). There is no default playback endpoint in that
  session (Core Audio `0x80070490`), so nothing the game plays can reach a speaker; the mute check accepts that case
  and refuses any other failure.

## Summary

- **The replay works and is exact where it can be checked.** Over 12 T05 runs (23,960 replayed frames) the lab's
  sim_dt equals the trace's **bit for bit on every frame** (0 mismatches), and the applied steer / throttle / handbrake
  equal the trace's bit for bit on every frame until the lab car is destroyed (0 mismatches; a dead car's input path
  writes throttle -1).
- **The lab side is deterministic (A/A).** The same replay run twice gives bit-identical states (position, rotation,
  velocity, rates) on every frame up to the frame the car is destroyed: 6 of 6 pairs; one pair without a destruction
  (retail trace + Arcade bit) is bit-identical for all 1,346 frames.
- **Emulator vs lab, T05 descent: the lab car pulls away from the start.**
  - Yaw rate equals the emulator's for the first 47-51 frames of every clean crest start (n 10), but only because
    both are exactly 0 until the trace's first steer input (47-51 frames in); on the first steered frame the lab's
    yaw rate is already 3-12 % higher (verify 2026-10-17, recomputed from MEM.BIN and the lab logs). In the
    approach-run replays (n 6 distinct, 49-61 equal frames) 6-14 of the equal frames are steered, non-zero yaw rates
    (g05a 11, g05b 14, r05a 6, r05c 0).
  - Position: over 0.1 m after 19-37 frames, over 1 m after 48-52 frames, over 10 m after 106-120 frames (clean starts).
  - **The lab car accelerates about 20 % harder**, in every run and the same against Gold and retail traces (n 10
    clean starts): when the emulator car reaches 10 / 20 / 30 m/s the lab car is at 11.7-11.9 / 24.8-25.2 / 37.0-37.6.
- **Cause of the acceleration gap: not the same car.** The emulator's T05 car comes from the 'T05 start (emu)'
  bookmark: armour + chassis maxima 9600. The lab's direct mission boot gives the mission's default car: 6080, mass
  1951. The emulator car's mass is not logged (I76MEM does not read +0xa4). So the T05 traces cannot validate the
  physics past the first seconds; they do validate the replay (dt, inputs, placement, determinism).
- **The clean comparison is the Instant Melee** (fresh default car in both). It could not run headless (section 4).
  A one-click console script is ready: owner test below.
- **Side result (headless lab):** with two small stub DLLs (`nullglide` glide2x.dll, `nullddraw` ddraw.dll) the game
  runs missions with no display, in a disconnected session, about 1,000 frames per second. Any agent can now run lab
  missions overnight while the session is disconnected.

## 1. What was built

### Proxy: `I76_REPLAY=<file.rpl>` (lab instrument, off by default; `music-fix/replay.c`)

- **Start state:** once the player car exists, the game is in the mission loop (state 5), no pause bits and the player
  is not script-driven, and `I76_REPLAY_DELAY` seconds later (default 3): at the top of a frame (frame hook, before
  simclock_Update) the car is placed at the END state of the trace's start frame:
  - object +0x18 rotation (9 floats) and +0x40 position (3 doubles);
  - entity +0xac speed, +0xb0 1/speed, +0xbc velocity, +0xc8 body rates, +0xd4 acceleration.
- **dt:** every following frame, right after simclock_Update, sim_dt 0x4fe420 and dt 0x4fe428 get the trace frame's
  float bits; their rates (0x4fe424 / 0x4fe42c = 1/x, as simclock computes them) and sim_time / time (moved by the same
  difference) follow.
- **Inputs:** the single call of input_ApplyToEntity 0x44f1c0 (at 0x44df61, once per frame, before the vehicle ticks)
  is wrapped; after the stock code the trace frame's applied steer +0xe0, throttle +0xe4 and handbrake +0xf0 are written.
  The wrapper counts its calls: exactly 1 per frame in every run.
- **Log (`I76_REPLAY_LOG`, default `<file>.lab.csv`):** one line per replayed frame at the top of the next frame, i.e.
  after its physics, collisions and render, where I76MEM reads in the emulator. Columns: the trace frame, the mem.phys
  columns (position, velocity, speed, rates, rotation, acceleration, inputs, flags, surface, clearance, step, rpm, gear),
  health, mass, armour and its maxima. `#end` after the last row; forcing stops there.
- **`I76_REPLAY_EFLAGS=<hex mask>`:** those entity-flag bits (+0x454) are set from the trace's start value and held each
  replayed frame. `10000` = the "Arcade Phys." bit (RETAIL-HANDLING-DIFF.md, EMU-T05-CLEAN.md).
- **Headless helpers (on by default under I76_REPLAY):**
  - the window-active flag 0x504c1c is held by a small thread until frame 30 (a window that is never activated keeps it
    0, and the start-up path then calls the null camera callback at 0x403868: fault at address 0);
  - through a mission opening the MAIN_MENU key is "pressed" by writing its scan code into the last-key slot 0x5367c8
    (the slot isKeypress 0x44de40 reads); no input injection;
  - `I76_REPLAY_CLICKS` posts shell clicks (does not reach the menus headless, section 4).
- **Addresses:** our exe = the Gold CD exe (same link, physics byte-identical; emu `addrmap-gold.md`). The lab exe
  85de44a7 of `game\` differs from golden 6319abf7 in 7 runs, none in physics; the replay copy runs 6319abf7 itself.

### Lab tools (`tools\replay\`)

| tool | what it does |
|---|---|
| `rpl_make.py` | MEM.BIN + I76DRV.LOG -> replay file: start state (doubles / floats as hex bits, entity flags) and per frame sim_dt, dt, steer, throttle (bits), handbrake, phase. A missing frame (0-36 per replay) gets the one integer tick that reproduces the next record's sim_dt with the engine's float arithmetic (t = (float)(tick x 0.001f), dt = (float)(t - t_prev): exact for 11,301 of 11,306 recorded Gold frames, the 5 others being the 0.2 s load clamp) and the inputs of the record before it |
| `replay-run.ps1` | one replay on `game-replay`: installs the side-built proxy (backup, read-back, restore), boots the mission (or the shell), answers the game's own message boxes, waits for `#end`, stops its own process |
| `rpl_diff.py` | emulator vs lab per frame: dt / input bit checks, \|dpos\|, \|dspeed\|, \|dyaw\|, heading, per phase, first frame over 0.01 / 0.1 / 1 / 10 m, steady yaw in steerR / steerL |
| `rpl_aa.py` | lab vs lab (A/A): bit-identical frames, first difference |
| `batch-t05.ps1` | the T05 sets below |
| `replay-melee-console.ps1`, `REPLAY-MELEE.bat` | Instant Melee replays on the twin with real menus (connected console only) |
| `with-lock.ps1` | console lock + mute check around one job; stops nothing |
| `nullglide\` | `glide2x.dll` (the 39 functions ZGLIDE.DLL imports + 4 the proxy and u32x look up) and `ddraw.dll` (DirectDrawCreate / DirectDrawEnumerateA, full IDirectDraw / IDirectDraw2 / surface / palette / clipper vtables) that accept everything and draw nothing; `NULLGLIDE_DUMP` / `NULLDDRAW_DUMP` write what would be presented as a BMP |
| `bptrace.py` | minimal WOW64 debugger: breakpoints with register / memory peeks, main-thread EIP + stack sampling, the first fault |

## 2. Replay checks

| check | result | n |
|---|---|---|
| lab sim_dt == trace sim_dt (float bits) | 0 mismatches | 23,960 frames, 12 runs (+ 11 clean-start runs: 0) |
| applied steer / throttle / handbrake == trace (bits), before any destruction | 0 mismatches | 12 runs + 11 clean runs |
| input_ApplyToEntity calls per replayed frame | 1 | every run (`#end` line) |
| A/A, lab vs lab, same replay file | bit-identical until the car is destroyed (373 / 331 / 519 / 493 / 503 identical frames from the start, rpl_aa; first difference at the destruction frame itself); r05a+Arcade 1,346 / 1,346 | 6 pairs |
| placement read-back | first logged frame 0.08 m from the trace (the trace car moved by its own physics in that frame; dspeed -0.007 to -0.015 m/s, constant within a run, over the first 30 frames) | 12 runs (clean starts: 0.076-0.078 m, n 10) |

- **After a destruction the twins differ.** First difference exactly at the destruction frame (y, vy, speed) in all 5
  pairs that had one. Not looked into (wreck / explosion code; possibly a time-seeded random number).
- **The `near_dist` column is not usable:** the world-position table's own entry of the player lags and reads 0.5-0.9 m.

## 3. Emulator vs lab, T05 canyon descents

Replay files (start 15-30 frames before the descent, to the end of the 'after' phase), each run once unless noted:

| set | traces | start | runs |
|---|---|---|---|
| approach runs | Gold 182548 (g05a), 161149 (g05b); retail 180103 (r05a), 183650 (r05c) | crest:+30, car damaged (armour 1437-2991 of 5600) | 2 each; retail ones also with the Arcade bit (2 each) |
| clean crest | Gold 230526 reps 1-6 (gc1-6); retail sim 232300, 233326, 234716, 235353 (rc1-4) | crest:-15, repaired, rolling 1.4-1.6 m/s | 1 each; rc1 also with the Arcade bit |

The retail approach runs are arcade mode (EMU-T05-CLEAN.md: every retail trace before 2026-10-16 22:40 has entity flag
0x10000); the clean retail runs are simulation physics (0x10000 on 0 frames).

**Agreement window (clean starts, n 10):**

- yaw rate equal for the first 47-51 frames, all of them 0 on both sides (no steering yet); the first steered frame
  differs (lab 3-12 % higher; trace speed there 11.4-11.9 m/s, lab 13.6-14.2);
- |dpos| over 0.1 m after 19-37 frames, over 1 m after 48-52 frames, over 10 m after 106-120 frames;
- lab speed when the emulator car reaches 2 / 5 / 10 / 20 / 30 / 40 m/s:

  | | 2 | 5 | 10 | 20 | 30 | 40 |
  |---|---|---|---|---|---|---|
  | Gold reps (n 6) | 2.0-2.4 | 4.8-5.0 | 11.7-11.9 | 24.8-25.2 | 37.0-37.6 | 47.0-48.2 |
  | retail sim (n 4) | 2.0-2.3 | 4.7-5.3 | 11.7-11.9 | 24.8-25.0 | 37.1-37.3 | 45.9-47.1 |

  The same gap against Gold and retail traces: the emulator's two exes accelerate alike here (EMU-T05-CLEAN.md: foot
  speeds 55.1 vs 56.9), the lab car does not match either.
- **Why:** different car (section "Summary"). Carrying the trace's other start flag bit (0x100, set in the Gold approach
  traces, not in the lab) changed nothing (g05a with `I76_REPLAY_EFLAGS=100`: identical diff, n 1).

**Outcomes in the lab (approach-run replays, n 2 each):** the lab car, faster and off the trace's line, was destroyed
in every replay without the Arcade bit: g05a, g05b and r05a land inverted in the canyon (up.y -0.95 to -0.99, flags
0x80089025, the CheckImpact rollover rule); r05c (and r05c+Arcade) left the road 70 m below the crest and fell about
40 m. r05a with the Arcade bit held landed upright and finished at 45 m/s (2 of 2). In the clean-start replays one
lab car was destroyed (gc1, frame 596) and one ended at rest (gc6); not analysed further. None of this is an exe comparison: the lab car is not
the emulator's car.

## 4. Instant Melee: not run (blocked headless)

- **Direct boot of a melee arena does not create a player.** The Instant Melee traces are on M01 ("The Crater": the
  emulator's spawn points 2362.5 / 49737.5 etc. are in M01.MSN). With I76_MISSION=m01, bwd2_LoadMissionFile 0x4b42b0
  loads it as mission type 1 ('m') and no player is ever created (breakpoint trace: 0x48e1a0 reached, player root
  [0x54a264] = 0 at 0x403868, then the null camera callback faults). Melee players come from the shell's setup.
- **The shell does not take headless clicks yet.** It comes up headless (game state 6, music track 13 requested). Four
  clicks (the emulator script's MELEE / AUTO MELEE / INSTANT MELEE / ENTER AREA) were posted as mouse messages with the
  cursor map's pad position at the same UI point, after WM_ACTIVATEAPP / WM_ACTIVATE / WM_SETFOCUS: the state stayed 6.
  The shell never called GetAsyncKeyState / GetKeyState (hooked in both modules: 0 calls); its main thread sits in a
  user32 wait under ShellMain (return address 0x4031fa after shell_RunAndGetChoice). Neither the Glide LFB nor the
  DirectDraw primary was presented after start-up (both dumps black / never updated), so the shell draws by another
  path. Not solved tonight.
- **Ready for a connected console:** `tools\replay\REPLAY-MELEE.bat` (owner test). It refuses to run unless the session
  is Active. It drives the menus with `autotest\enter-melee.ps1 -NoLaunch` (no AI) on the twin with its normal
  renderer, then I76_REPLAY places the car and replays; one diff per replay in `runs\melee-console-<stamp>.txt`.
  Default set: Gold reps 1-4, retail reps 1-4 of the 2026-10-15 loops (**those retail reps are arcade mode**), retail
  reps 1-2 with the Arcade bit. The retail simulation melee loops (232325, 224135) need replay files first:
  `python -I tools\replay\rpl_make.py --run emu\results\par\20261016-232325-r166sim-mloop-1 --rep K --out tools\replay\rpl\rsim-repK.rpl`.

## 5. Notes and incidents

- **Headless boot, step by step (all in this session, all on `game-replay`):**
  - dgVoodoo Glide: "Failed to initialize 3D hardware acceleration / Running software emulation mode" box; answering it
    leads to a fault at i76.exe 0x475c36 (the software renderer). The retail-handling lane saw the same box and fault.
  - dgVoodoo with OutputAPI d3d11warp: integer divide by zero inside glide2x.dll (0x6df99836).
  - nullglide with a full 180-byte GrHwConfiguration write: smashed ZGLIDE's stack (return to address 0). Writing only
    num_sst and the first board's fields fixed it; the next fault was in dgVoodoo's DDraw.dll, hence nullddraw.
  - The system ddraw.dll in a disconnected session: the same "Failed to initialize" box.
  - nullglide + nullddraw + the active-flag thread: T05 and T06 boot; a T05 replay of 1,100-2,900 frames takes 12-15 s.
- **The game-replay copy:** made with robocopy from the twin without `smk\` (movies fail to open and are skipped),
  `Glide2x.dll.dgvoodoo` / `DDraw.dll.dgvoodoo` kept beside the stubs, dgVoodoo.conf set to d3d11warp / 640x480 (not in
  use with the stubs). It is not a playable folder.
- **A stale lock was moved aside:** the twin had `.console-test.lock` from 2026-10-15 14:19 (proxy-run, pid 32896, no
  longer running) and a `STRLKUP.DLL.pretest` identical to its STRLKUP.DLL (33211f11). The lock is now
  `.console-test.lock.stale-20261015-1419-pid32896-gone`; proxy-run's own restore cleared the .pretest.
- **One restore failed and was redone:** run g1-try1 left the side-built DLL in the twin (the copy back hit a still
  closing process). Restored by hand, md5 read back 33211f11; the harness now retries 30 s and reports.
- **Shared source:** another lane edited `strlkproxy.c` at the same time (I76_RETAIL_HANDLING); only this lane's five
  lines were committed with replay.c.

## 6. Not done / next

1. **Instant Melee replays** (the real exe A/A): owner test, or any session that is Active.
2. **Match the T05 car:** log the emulator car's mass (+0xa4) and vehicle in one VM run, or boot the lab from the same
   bookmark; then the T05 clean starts become a valid exe comparison.
3. **Headless shell:** find how the shell takes clicks and how it draws (bptrace on its WndProc / the exe's shell
   callbacks); that would make melee and bookmark loads headless.
4. **Retail sim melee replay files** (section 4) and steady-yaw comparison in the replay (rpl_diff prints it).
5. **After-destruction divergence** in the A/A (time-seeded randomness?) if replays past a destruction matter.

## 7. 2026-10-17 evening: Instant Melee replays on the console (item 51)

Lane frame-replay-fix. Every live run on the lab twin `game-dd-20261003`, under the console lock, audio muted; the
twin's `STRLKUP.DLL` was swapped for the side-built replay proxy per run and put back (md5 read back `33211f11`).

### 7.1 Why REPLAY-MELEE.bat "did not reach mission"

- **Cause: the clicks were placed 1:1 and missed.** `autotest\enter-melee.ps1 -NoLaunch` does
  `SetCursorPos(ux, uy)` and assumes the OS cursor is the shell's 640x480 point. On the twin (3440x1440 client) the
  shell's own mouse (`[0x100cc514]+0x2c/+0x30`, as f2-drive reads it) read **(0,104) for MELEE (447,311)**: every menu
  click landed off the buttons. It also pressed Esc / Enter six times blind and never checked a screen. The failure was
  n 2 at 14:53 (owner test 11) and once more at 16:27.
- **Fix: `tools\replay\melee-nav.ps1`** (lab f597ced), now called by `replay-melee-console.ps1`:
  - Esc / Enter only until the main menu is up (screen 0xC00E, sfn 0x10025a50);
  - each click is placed 1:1 first, then by the window's 4:3 fit (uiclick `Get-UiMap`), and pressed only when the shell's
    mouse reads the target;
  - the route is MELEE (447,311), AUTO MELEE (490,351), INSTANT MELEE (531,379), then the gate on the driver entry form
    (sfn 0x10028610);
  - on the form: AREA = **The Crater** (UI 80,157), A.I. DRIVERS - x3, ENTER AREA (296,462);
  - the last gate is the player entity; a screenshot is taken at every step.
- **Arena:** the form keeps the last arena used. The twin came up on **Air Base** (screenshot nav-debug-173311), while
  the Instant Melee traces are on M01 The Crater. The script now always picks The Crater.
- **Result:** reached Instant Melee in 16 of 16 runs since the click fix (15 of them with the arena pick), 16 s from
  launch. The three earlier debug runs failed on the script's own bugs: an `Rd` helper that PowerShell resolves to
  its `rd` alias (Remove-Item; the paths did not exist, nothing was removed), and a widget gate.
- **Unrelated finding:** the per-step "last widget" read (0x10055d90) stayed 0 while the sub-menus visibly opened.
  It is logged only.
- **Also fixed:**
  - `-Conds a,b,c` through `powershell -File` arrived as one string; it is split now, and missing replay files are refused.
  - With several lanes queued, a per-replay lock wait timed out after 30 min. `-InLock` runs a whole set under one
    with-lock hold: 8 replays in about 7 min.

### 7.2 A/A: the melee replay was not deterministic, and why

Gold `g166-mloop-rep1` (1,304 frames, accel:-60..park), lab vs lab (`rpl_aa`):

| proxy switches | pair | bit-identical frames | first difference |
|---|---|---|---|
| as built 2026-10-16 (3 s wall-clock wait before the placement) | 173353 / 173458 | 63 of 1,304 | frame 709, x y z (dx 9e-9 m, dy 1e-6 m; the 2nd frame with throttle applied; 3 frames after the accel phase starts at 706) |
| `I76_REPLAY_PREROLL=150` | 173805 / 174548 | 63 of 1,304 | frame 709 (sim_time now equal too) |
| `I76_REPLAY_PREROLL=150` + `I76_REPLAY_SRAND=1` | 174759 / 175845 / 192448 | **1,304 of 1,304** (3 runs, all pairs) | none |

- The exe seeds MSVCRT `rand()` with `time(NULL)` at mission start (i76-map functions/004a9020, 004ad260; 4 srand calls
  before the placement). The melee car's own motion draws from `rand()` once it moves: same inputs and dt bits, a
  different seed, and positions split at the first moving frames.
  - *verify:* that the car's motion reads `rand()` is an inference from the A/A table; the census that would show it
    (7.4 a) has not run. The 173805 / 174548 row compares a pair, not every run: on its own, 173805 (pre-roll only, no
    `srand fixed` line in the twin's mciproxy.log) is **1,304 of 1,304 identical to the srand-1 runs**. The four runs
    without the srand switch (173353, 173458, 173805, 174548) give four different trajectories, and one of them is the
    seed-1 trajectory. A clock seed would almost never reproduce seed 1's whole stream, so the car's path depends on
    only part of what the seed sets (how, unknown), and a run without srand can land on the seed-1 path by chance (1 of 4
    here). That makes 3 of 3 under srand 1 good evidence, not proof; control 7.4 (b) still matters.
  - The T05 A/A pairs were identical because the canyon run did not draw from `rand()` before the destruction. The
    after-destruction divergence there (section 2) is most likely the same seed.
- **New proxy switches** (i76-everywhere d072513, `music-fix/replay.c`, opt-in, lab only):
  - `I76_REPLAY_PREROLL=<frames>`: the wait before the placement is counted in frames, and those frames run at the
    trace's first sim_dt / dt;
  - `I76_REPLAY_SRAND=<seed>`: every `srand()` of i76.exe (IAT, MSVCRT.dll) gets the seed;
  - `I76_REPLAY_RANDLOG=1`: a per-frame census of `rand()` callers (return addresses), written to mciproxy.log.
  - They are built from a HEAD export, because `strlkproxy.c` has another lane's open edits:
    - lab `builds\replay-preroll\Strlkup.dll` f10b5cc5 (PREROLL + SRAND);
    - `builds\replay-randlog\Strlkup.dll` 8526ed31 (+ RANDLOG).
  - `music-fix/Strlkup.dll` is unchanged.
- **Consequence for the emulator comparison:** the emulator's run had its own time seed. Lab vs emulator therefore
  cannot be bit-identical once the car moves, even with an identical exe and car. The question becomes how far apart
  the two runs drift, not whether they match bit for bit.

### 7.3 Emulator vs lab, Instant Melee (pre-roll 150, srand 1; each replay once)

Gold = the Gold CD exe's traces (20261015-191227 g166-mloop, reps 1-4). Retail sim = retail 1.0 with simulation
physics (20261016-232325 r166sim-mloop, reps 1-4, replay files `rpl\rsim-repK.rpl`, made tonight). The 2026-10-15
retail loops (arcade) were not replayed.

| replay | sim_dt / input bit mismatches | accel phase starts (frame) | \|dspeed\| > 0.01 / 0.1 / 1 m/s (frames after the accel phase starts) | horizontal d > 0.1 / 1 / 10 m (frame) | speed at end of accel, trace / lab (m/s) |
|---|---|---|---|---|---|
| Gold rep1 | 0 / 0 | 706 | +38 / +113 / +173 | 802 / 914 / 1143 | 54.75 / 55.45 |
| Gold rep2 | 0 / 0 | 946 | +19 / +120 / +241 | 1050 / 1196 / 1259 | 52.02 / 55.52 |
| Gold rep3 | 0 / 0 | 967 | +42 / +131 / +401 | 1078 / 1271 / 1441 | 54.60 / 54.87 |
| Gold rep4 | 0 / 0 | 992 | +44 / +118 / +250 | 1090 / 1268 / 1427 | 54.56 / 55.27 |
| retail sim rep1 | 0 / 0 | 1127 | +47 / +48 / +500 | 1211 / 1460 / 1724 | 54.47 / 53.56 |
| retail sim rep2 | 0 / 0 | 1146 | +45 / +47 / +260 | 1243 / 1388 / 1661 | 53.67 / 52.99 |
| retail sim rep3 | 0 / 0 | 1153 | +23 / +168 / +173 | 1329 / 1354 / 1549 | 51.00 / 53.06 |
| retail sim rep4 | 0 / 0 | 1173 | +23 / +191 / +455 | 1385 / 1442 / 1697 | 53.21 / 54.19 |

**How to read the table:**

- **Divergence is late in the sense that matters.** For the first 19-47 throttle frames the lab car's speed matches
  the emulator's to within 0.01 m/s. The divergence starts at trace speed 5.3-5.6 m/s (n 3) or 11.4-12.1 m/s (n 5).
  - *verify:* the "throttle frames" here and in the table count from the start of the accel phase. The first frame
    with throttle applied (lab log `throttle` > 0) is 2-6 frames later: 708, 948, 969, 998, 1131, 1148, 1155, 1176. Counted
    from there, the 0.01 m/s threshold falls 17-43 frames in.
  - Over the first 30 throttle frames the largest gap is 0.004-0.018 m/s (n 8).
  - At frame 708 (Gold rep1, first frame with throttle) the gap is 3e-10 m/s; at 709 it is 1e-6.
- **rpl_diff's "first |dpos| > 0.01 m" misleads for melee.** In Gold rep1 it fires at 708, but that is vertical:
  dy 0.014 m against dh 8e-5 m. Over 708-713 dy swings between +0.014 and -0.056 m while dh stays under 0.0013 m.
  - rpl_diff now writes `dh` / `dy` columns; `rpl_hdiff.py` reports the horizontal and |dspeed| thresholds above.
- **Speed at the end of the 12 s throttle:**
  - Gold: the lab is faster in 4 of 4, by 0.27-3.50 m/s;
  - retail sim: the lab is slower in 2 and faster in 2, from -0.91 to +2.06 m/s;
  - the per-frame sign of dspeed in accel is mixed in every replay.
  - No constant exe-wide bias is visible at this n. The seed alone gives each side a different path.
- **Steering phases are not comparable.** By then the cars are 30-190 m and several m/s apart, so steady yaw
  (lab 0.56-2.10 rad/s, trace 1.44-2.02) compares different states. A steering comparison needs a replay that starts
  at steer-prep from the trace's state (`rpl_make --from`).

### 7.4 Next

1. **Match the emulator's seed.** Either log `holdrand` in the VM at mission start (I76MEM: msvcrt's per-thread data),
   or run the emulator with srand pinned too (I76MEM poke on the srand IAT). Then lab vs emulator can be bit-compared;
   any remaining difference is the exe / car / FPU.
2. **Not run tonight.** From 20:29 the console lock was held by the main session's LAN test, with the owner playing.
   These two runs were queued and then withdrawn, so they never took over the mouse:
   - (a) the `rand()` caller census: which return addresses draw on the frames where the car starts to move;
   - (b) a srand-only control with no pre-roll, n 2: is the pre-roll needed at all, or the seed alone?
   - The script is ready: lab `tools\replay\with-lock.ps1 -Who frame-replay-fix -WaitMinutes 30 -Command "& '<batch>'"`.
   - The batch is two calls of `replay-melee-console.ps1 -InLock -Conds g166-mloop-rep1`:
     - (a) with `-Dll builds\replay-randlog\Strlkup.dll -Preroll 150 -Srand 1 -RandLog`; the census goes to the twin's
       mciproxy.log, lines `replay: rand frame`;
     - (b) with `-N 2 -Dll builds\replay-preroll\Strlkup.dll -Srand 1`, then `rpl_aa`.
3. Steering: replay files that start at steerprep / steerR from the trace's state.
