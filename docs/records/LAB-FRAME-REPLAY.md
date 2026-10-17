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
- **Emulator vs lab, T05 descent: the first ~1.5 s agree, then the lab car pulls away.**
  - Yaw rate is **bit-identical** to the emulator's for the first 47-51 frames of every clean crest start (n 10, Gold
    and retail sim alike; up to a trace speed of 11.4-11.9 m/s, about 1.7 s) and for the first 49-61 frames of the
    approach-run replays (n 6).
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
| A/A, lab vs lab, same replay file | bit-identical until the car is destroyed (frames 372 / 331 / 515 / 489 / 499; first difference at the destruction frame itself); r05a+Arcade 1,346 / 1,346 | 6 pairs |
| placement read-back | first logged frame 0.08 m from the trace (the trace car moved by its own physics in that frame; dspeed -0.015 m/s constant over the first 30 frames) | 12 runs |

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

- yaw rate bit-identical from the start for 47-51 frames (trace speed up to 11.4-11.9 m/s);
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
