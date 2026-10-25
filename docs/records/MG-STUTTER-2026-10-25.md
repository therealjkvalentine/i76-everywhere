# Machine-gun stutter under the 24/s tick: mechanism, numbers, the fix and a "classic 20" option (2026-10-25)

Lane: mg-stutter (investigation / design, Fable); an Opus lane implements s.4. **Results: s.6** (58e3227: the gallop is gone, 10.00 /s; proxy 1d22df46 in the lab dev / test copies; QA #119). Trigger: an outside tester (an expert on this
game) on the tester build (tick19-42, `I76_SIM_TICK_MS=41.667`): *"You had mentioned the base frame rate was 24 fps. This causes
some stuttering with machine guns. Dropping the reference frame rate to 20 would fix this."* Paths: `<lab>` = the uncap lab.

## 0. Findings in five lines

1. **He is right about the mechanism.** Every stock MG fires on a timer of 100 ms (30cal, 50cal: `fire_rate 10.0`) or 50 ms
   (7.62mm: 20.0), and a shot can only leave on a sim frame. 100 ms is 2.4 ticks of 41.667 ms, so the shots come in a **2, 3, 2, 3
   tick pattern = 83 / 125 ms alternating** (sd 20.8 ms, measured, n 3). At 50 ms frames it is exactly 2 frames: 100 / 100 (sd 0).
2. **1997 at 20 fps had the same timer but no gallop:** the GOG limiter's 50 ms frames put every MG interval on an integer number
   of frames (replay: sd 0 in wall time for 10/s and 20/s guns). The 24-step "1997 coupling" we chose for the car physics (e24,
   ~42 ms steps) gallops exactly like our tick; the gallop is a property of the step length, not of the tick machinery.
3. **What the ear hears is the shot grid.** The MG fire sound is a 0.6-2.0 s continuous-fire **loop** requested per shot through the
   sustained path and stopped by the first sound update with no request (s.1.3): one tick-long chunk of the loop per shot, spaced
   83 / 125 ms. The muzzle flash and the tracer spawn sit on the same grid; the rounds' positions are mostly caught up (s.1.2).
4. **The fix keeps 24/s:** the timer already knows where each shot *should* have fallen (the interval remaining at the tick's start,
   which weapon_FireShot receives as the catch-up time); play the sound and the flash on the display frame nearest that time instead
   of at the tick, and hold the loop for one 1997 frame (50 ms). Replay: audible intervals 100 / 108 ms (sd 4.1) with the engine's
   10 ms leftover rule kept, **exactly 100 ms (sd 0) with it removed**; the sim, the AI, the net code and the rounds' spawn grid are
   untouched (s.3.1).
5. **"Classic 20" as a tick is possible but is not the fix:** an exact 50 ms tick splits the car step into 2 x 25 ms substeps (the
   step the owner rejected on 2026-09-27) and halves the 7.62mm's rate (its 50 ms interval meets the timer's strict compare); 49.9 ms
   avoids both (one 49.9 ms step, MG sd 3.2) but changes the physics the owner tuned at 41.667, engages the tick-factors (x1.2) and
   must match on every LAN peer. Offer it as an opt-in settings line for single player after the fix ships (s.3.2).

## 1. Mechanism (static, from the 9a232dcc / 6319abf7 disassembly and the data files)

### 1.1 The fire timer

`weapon_UpdateInstanceFiring` 0x4a6470 (called once per sim frame from `weapon_Update` 0x4a4130 at 0x4a43cc, for every instance, AI
included; ghidra export `004a6470.c`; <re-archive> `subsystems/weapons.md`, FRAME-BOUND-SYSTEMS-2026-10-19 s.1). Per instance:
cooldown `+0x24`, interval `+0x28` (= 1 / GDFC `fire_rate`), burst counter `+0x2c`, trigger pulse `+0x3c` (set by the frame's
`weapon_ReadPlayerTrigger` / the AI, cleared at the end of this update). With `dt = simclock_GetDt()` (= T under the tick):

- **No shot** when `dt <= cooldown` or `dt <= interval` (strict): both timers lose dt. So a gun whose interval EQUALS the frame
  time never fires on the frame its timer reaches 0; it fires on the next one. (The 7.62mm at an exact 50 ms tick: 10/s instead of
  20/s. 1997's 46.9 / 62.5 ms frames never hit this.)
- **Shot** otherwise: the loop takes the interval out of dt (`dt_left = dt - interval`), **drops a leftover under 10 ms**
  (`if (dt_left < 0.01) dt_left = 0`, 0x4a6623 / 0x4a6b40 - the loop then ends without firing, and the shot comes on the NEXT frame
  with the whole frame as leftover), else fires: MG rounds (ordnance 1) are counted and batched into one `weapon_FireShot`
  0x4a6e90(instance, weapdef, count, max_dt_left / 3) after the loop (0x4a6d43); every other ordnance calls it inside the loop
  (0x4a6b16) with its own dt_left. After the loop the timers are charged the leftover (`interval -= dt_left`), which is the carry: the
  next shot's timer starts from where this one really expired.
- **Virtual shot time** = tick start + interval remaining at the tick start. The carry keeps the virtual grid exact (every 100 ms)
  except for the 10 ms drop, which moves a shot to the next tick's start (the measured 9.60 /s at ~42 ms frames = 4 % lost to it;
  FRAME-BOUND s.1; `fire_timer_sim.py` predicted it to the digit).

The MG rates are the .gdf's, not the published table's rounds-per-minute column: `gmlight.gdf` (30cal) and `gmmedium.gdf` (50cal)
`fire_rate 10.0`, `gmheavy.gdf` (7.62mm) `20.0`; burst 1, cooldown 0 (`python data\mod\i76mod.py show zfs:gmlight.gdf GDFC`,
<re-archive> data track). The lab copies' "modded 10 /s 50cal" is therefore stock.

### 1.2 What the shot does per call (`weapon_FireShot` 0x4a6e90)

In order: the muzzle flash `weapon_ShowMuzzleFlash` 0x49f2f0 on the mount (call 0x4a6e9e; a 0.1 s animation + an omni light), the
fire sound (0x4a6ee0 -> `sound_PlayOnObjectSustained` 0x423230 when the weapdef's `sound_mode` is 1, 0x4a6ef2 -> the one-shot
0x4231f0 when 0), ammo, target choice, then `weapon_SpawnProjectile` 0x49fb40 with **one catch-up step by the dt_left passed in**
(for the MG batch a third of the largest leftover). So the round's position is partly caught up to the virtual time, the flash and
the sound are not: they happen on the tick. The tracer record is written by the round's step (TICK-FINISH s.?, simtick.c "tracers").

### 1.3 The sound: a continuous-fire loop chopped by the request grid

All three MGs have `sound_mode 1` and a `.gpw` loop: `wlmgun.gpw` 1314 ms, `wmmgun.gpw` 2010 ms, `whmgun.gpw` 627 ms (11025 Hz 8-bit
mono; GAS0 header priority 70, 2 instances, mode 1 = loop; read from the pristine I76.ZFS with `tools\i76fmt\zfs.py`). The sustained
path makes a mode-2 voice: keep-alive `+0x74` = 1 at the start and +1 per request (0x421c8b), **tested and cleared by the per-frame
sound update `shell_cb_10` 0x421400 (0x42151e / 0x42155f): a mode-2 voice with keep-alive 0 is stopped** (<re-archive> `sound.md`
"Sustained loops"; music-fix/simtick.c "sustained sounds between ticks"). Consequences:

| frame loop | the loop plays | spacing | source |
|---|---|---|---|
| 1997 / GOG limiter (20 fps, 50 ms frames) | from the shot's frame to the next frame's update: ~50 ms per shot (10/s guns: 50 % duty; the 7.62mm at 20/s requests every frame: continuous) | 100 / 100 ms | the update order 0x403e27 after the sim block |
| our tick 41.667 (`I76_SIM_TICK_SOUND=1`, default) | the shot tick's display frames, stopped by the next tick's update: ~42 ms per shot | 83 / 125 ms | simtick.c st_snd_keep |
| stock uncapped ~60 fps (PLAY-VANILLA, I76PATCH disabled) | one display frame, ~17 ms per shot | 100 / 117 ms | the same update |
| promotion 18 (weapons per display frame at 120 fps) | ~8 ms per shot | 100 / 108 ms | FRAME-BOUND s.1 |

The burst length and whether a restart resumes or replays the loop's head have not been measured (SOUND_START / SOUND_STOP under
`I76_SOUND_EVENTS=1` give both; s.4 step 1). What is certain from the code: the audible event per shot starts on the shot's frame.

### 1.4 Other per-shot consumers

AI guns run the same timer (FRAME-BOUND s.1, row 12: the AI pulls the trigger on tick frames anyway). The FFB gun one-shots
(0x4f234c/50/54, next to the three WEAPON_UI sites) and the HUD ammo-digit roll are per shot / per tick and stay on the tick; not
part of this lane.

## 2. Numbers

### 2.1 Measured (re-mined from the frame-bound lane's raw captures, `<lab>\captures\frame-bound-20261019\gun50-*.fbev.csv`)

T05 car's 50cal (10 /s), trigger held ~5-7 s, player frozen, every player SHOT event stamped with the frame's sim time; n 3 per arm.
`<lab>\tools\mg-stutter\mg_tab.py` (new) tabulates; the first run of each arm shown, the other two agree within 0.1 ms / 0.1 /s.

| arm | frame loop | shot interval mean / sd (ms) | pattern | rounds / s |
|---|---|---|---|---|
| e24 | the stock loop at 24 fps, 1 ms clock (~42 ms frames; the 1997 car-step coupling) | 104.2 / **20.8** | 83 x28, 125 x28 | 9.77 |
| t33 | `I76_SIM_TICK_MS=33.333` | 100.0 / 0.0 | 100 x71 | 10.14 |
| t66 | 66.667 | 99.3 / 34.0 | 67 x26, 133 x25 | 10.26 |
| p18 | promotion 18, weapons per display frame at 120 fps | 105.0 / 4.1 | 108 x37, 100 x25 | 9.68 |

No capture exists at 41.667 / 42 / 50: the frame-bound lane did not run them, the laptop bench was locked by two other lanes all
afternoon (terrain-pass-opt, nitro-lobby), the headless lab copy `game-fbs` is retired and the shipped proxy has no drive block
(the fb-run harness needs the lab twin's `Local\I76RhDrive`). The replay below is validated against the four arms above and the
FRAME-BOUND rates (e24 9.61, t33 10.00, t66 10.07, p18 9.52); the live rows are step 1 of s.4.

### 2.2 Replay (`<lab>\tools\mg-stutter\mg_cadence_sim.py`: the 0x4a6470 loop in float32, 120 s held trigger per arm)

Shot WALL intervals (the frame the shot fires in) and the VIRTUAL intervals (where the timer expired = what the fix plays on):

| arm | 10 /s MGs: wall mean / sd [pattern] rate | virtual sd | 20 /s 7.62mm: wall mean / sd [pattern] rate |
|---|---|---|---|
| tick 41.667 (tick19-42) | 104.1 / **20.8** [83, 125] 9.60 | 4.1 (100 / 108) | 52.1 / **18.0** [42, 83] 19.2 |
| tick 42 (the stock mean step) | 105.0 / 21.0 [83, 125] 9.52 | 5.0 | 52.5 / 18.2 [42, 83] 19.1 |
| tick 46.875 (the stock 3-clock-tick step) | 101.6 / 17.4 [96, 142] 9.85 | 3.5 | 50.8 / 12.9 [46, 96] 19.7 |
| tick 50 (2 x 25 ms substeps) | 100.0 / 0.0 10.00 | 0 | **100.0 / 0.0 [100] 10.0 - halved** (s.1.1) |
| tick 49.9 (one 49.9 ms step) | 100.0 / 3.2 [100 x1194, 150 x5] 10.00 | 0.6 | 50.0 / 2.5 [50, rare 100] 19.99 |
| tick 33.333 | 100.0 / 0.0 10.00 | 0 | 50.0 / 16.7 [33, 67] 20.0 |
| GOG limiter 20 fps, 15.6 ms clock (stock20 as played) | **100.0 / 0.0** 10.00 | 7.7 | **50.0 / 0.0** 20.0 |
| stock uncapped ~60 fps, 15.6 ms clock (PLAY-VANILLA) | 107.2 / 8.3 [100, 117] 9.33 | 8.9 | 54.4 / 10.1 18.4 |
| p18, weapons per display frame, 120 fps | 104.2 / 3.2 [108, 100, 104] 9.60 | 3.2 | 54.2 / 3.4 18.5 |
| **tick 41.667 + the fix, drop rule kept** | audible 104.1 / **4.1** [100, 108] 9.60 | - | 52.1 / 3.6 [50, 58] 19.2 |
| **tick 41.667 + the fix + drop rule removed** | audible **100.0 / 0.0** 10.00 | - | **50.0 / 0.0** 20.00 |

Reading: the 1997 game as played (stock20) is dead even in wall time on every MG; our tick (and the 1997 car-step coupling e24) is
the worst arm of all (sd 21 ms, a 1.5 : 1 gallop at 9.6 Hz); PLAY-VANILLA is a poor "no stutter" reference (sd 8, 17 ms chunks of
the loop) - the GOG-limiter boot (`I76PATCH.DLL` put back, as the launch-video `route-stock` does) is the reference. The fix with
the timer's drop rule removed reproduces stock20's cadence exactly and restores the .gdf's 10.00 /s (the drop costs 4 % at any
~42 ms step, 1997 included). The display-frame scheduling adds a uniform 0-8 ms (sd 2.4 ms at 120 fps), below the 1997 clock's own
7.7 ms virtual jitter.

## 3. Design

### 3.1 The fix at 24/s: play the shot where the timer put it (`I76_MG_EVEN`, proxy simtick.c; default on under the tick)

1. **Know each shot's offset.** Wrap the call at 0x4a43cc (`weapon_Update` -> 0x4a6470) on tick frames: before it, snapshot every
   instance's interval `+0x28` and cooldown `+0x24` (table 0x5aab08, stride 0x4c, count 0x5da750). In the `weapon_FireShot` wrapper
   (sites 0x4a6b16 / 0x4a6d43 are already repointed by the telemetry; chain) set `g_shot_offset = rem` when `0 < rem < T`
   (rem = the snapshot's interval, the cooldown when that is the one that ran out), else 0 (a shot that fires at the tick's start,
   including the drop-rule case and the first shot of a pull).
2. **Defer the flash and the sound** by `g_shot_offset`: repoint the three calls inside `weapon_FireShot` (0x4a6e9e flash, 0x4a6ee0
   sustained, 0x4a6ef2 one-shot) at stubs that, with a nonzero offset, push {due wall time = this tick's wall start + offset, kind,
   object, name} on a small ring and return; with offset 0 they chain through. A display-frame hook (the camera wrapper, where
   `st_snd_keep` already runs every display frame before the sound update) plays every due entry: the flash through 0x49f2f0(obj),
   the sound through the original path with the original arguments. Rounds are spawned on the tick as today (their catch-up already
   places them). Nothing else in the sim moves, so the AI, the damage, the SH fire packets and LAN parity are untouched.
3. **Hold the loop for one 1997 frame.** After a deferred (or chained) sustained MG request, keep the voice's keep-alive at 1 on every
   display frame for `I76_MG_SOUND_HOLD_MS` (default 50 = the stock 20 fps burst; 0 = today's one-tick chunk) measured from the due
   time; find the voice as `st_snd_keep` does (manager [0x524564] +0x1c list, mode 2, name / object). A 20 /s gun then stays
   continuous, a 10 /s gun chops 50 / 50 as in 1997, at any display rate. This replaces the tick-based listing for those voices.
4. **The 10 ms drop (`I76_FIRE_TIMER_FIX=1`, default on with MG_EVEN):** patch the two compares against the 0.01 constant in
   0x4a6470 (the sites that lead to 0x4a6b40) to compare against 0. Effect: the virtual grid is exact (sd 0), the rate is the .gdf's
   (10.00 /s, +4 % rounds and damage per second on ~42 ms steps; 1997 at 20 fps also had 10.00, 1997 at 24 steps had 9.6). A LAN
   peer without it fires 4 % slower - the same order as today's e24-vs-tick33 difference; note it in the pack's VERSION.
5. **Scope and safety:** player and AI instances alike (the AI's MGs sound even too); batched calls (count > 1, only above 24 /s)
   defer as one; an early tick (`I76_SIM_TICK_INPUT`) shifts the tick's wall start, which the offset is relative to, so nothing
   breaks; the ring is drained or dropped on a mission change; `I76_MG_EVEN=0` = today. Log one `mg-even:` line at attach (sites
   patched, hold ms, timer fix) and a counter line every N s under `I76_SIM_TICK_LOG`.

Alternatives considered: running 0x4a6470 per display frame (p18's way: sd 3.2, but the trigger pulse `+0x3c` is per tick, the
AI's trigger too, the net jam / fire-mask block is per frame, and the rounds would spawn between ticks: more surface, less exact);
quantising the interval to whole ticks (changes the rate +-20 %); a 33.333 ms tick (even for 10 /s guns, 33 / 67 for the 7.62mm,
and a different car step).

### 3.2 "Classic 20" as a player option (`sim rate = 24 | 20` in i76-settings.txt -> preset tick19-50, `I76_SIM_TICK_MS=49.9`)

What the tester means is the 1997 20 fps sim (50 ms frames). Which value reproduces it:
- **50 exactly**: the stepper's `count = floor(20 dt) + 1` gives 2 x 25 ms car substeps (physics.md; PHYSICS-STEP-STUDY amendment)
  = the 25 ms step the owner rejected (jumps short, body quick; memory "measure the reference as played"); and the 7.62mm halves
  (s.1.1). Not this.
- **49.9**: one 49.9 ms step; MGs even (sd 3.2, a 150 ms hiccup every ~240 shots from the drop rule, gone with the timer fix);
  7.62mm 19.99 /s. The 1997 limiter's steps were 46.9 (80 %) and 2 x 31.25 (20 %), never 50, so no single tick is "stock as played"
  AND MG-even (46.875: sd 17). 49.9 is the honest "classic 20".
- **42 (the stock mean step)**: does NOT fix the MGs (100 / 42 = 2.38: sd 21, the same gallop); it is the physics answer, not the
  cadence answer, and tick19-42 already is 41.667.

Interactions a 49.9 preset carries (all in simtick.c, read 2026-10-25): tick-factors install with base = 24 x 0.0499 = 1.198
(hazard, scrape, radar x1.2; wreck sub clamped 1.0; slope-follow per the 1997 step) - measured only at 33.3 / 44 / 66.7, a 49.9 row
is needed; interpolation and the early tick are tick-length agnostic; the step-length curve says take-off speed rises with T
(53.4-54.4 m/s at 42-48 ms; STEP-LENGTH-CURVE H3) so jumps go longer - the owner must drive it; **LAN: every peer must run the
same tick** (no tick in the join handshake; the pack's preset is the only enforcement) so the option is single-player, or a pack-level
choice; the 24-step assumptions in simtick.c (`I76_SIM_TICK_REF_HZ` 24, the `base == 1 -> not installed` shortcut) are explicit and
hold. Ship it only after the fix, as an opt-in line whose help text says "1997's 20 fps simulation: even guns, longer jumps, single
player".

## 4. Plan for Opus (ranked), tests and the acceptance line

| # | step | where | test | done when |
|---|---|---|---|---|
| 1 | **Live baseline rows** (the measurement this lane could not run): arms t41.667 / t42 / t49.9 / stock20 (preset stock + `I76PATCH.DLL` back, GetTickCount clock) / vanilla (preset stock, patch disabled) / e24, n 2 each, 20 s held trigger on the T05 50cal, player frozen (fb_live `guns`), `I76_TELEMETRY=1 I76_SOUND_EVENTS=1 I76_DAMAGE_EVENTS=1 I76_FRAME_LOG`; skip movies / cutscenes, FFB off, muted, own SHM suffix, keys through a drive-inject build (the analog lane's harness patch in `<lab>\builds\terrain-opt-20261025\build-variant.ps1`) on the laptop under its lock, or a private desktop here with `tools\replay\nullglide` stubs (CONSOLE-LOCK: never the default SHM names beside the owner) | `<lab>\tools\frame-bound\fb-run.ps1` + `fb_live.py` (add the arms to `$C`, the sound-events key), `<lab>\tools\mg-stutter\mg_tab.py` | expected: t41.667 shot sd ~21 (83 / 125), 1.0 sound start per shot, burst ~42 ms; stock20 sd ~0, burst ~50 ms; vanilla sd ~8, burst ~17 ms | the table in s.2.1 has the six arms with n 2 |
| 2 | **Implement `I76_MG_EVEN` + `I76_FIRE_TIMER_FIX`** (s.3.1) in music-fix simtick.c; defaults on under the tick; log lines; build, install in test-gold / dev-gold as the lab does | music-fix/simtick.c (next to st_snd_keep and the tracer code), strlkproxy.c (the FireShot wrapper chain) | static: the six sites report patched in mciproxy.log; `tests` build; `proxy-run.ps1 -Set tick` boots t05 | the log shows `mg-even: ... 6/6 sites` |
| 3 | **Measure after** (same harness, arms t41.667 with MG_EVEN 0 / 1, with and without the timer fix, n 2) | as 1 | **acceptance:** over >= 50 shots per boot, SOUND_START intervals of the MG loop sd <= 4 ms with the drop rule kept and <= 1 ms with it removed (today 20.8); starts per shot 1.0 +- 0.05; burst length 50 +- 8 ms (STOP - START); SHOT (spawn) count unchanged with MG_EVEN alone, rate 10.0 +- 0.1 /s with the timer fix; record damage per sim second within 243-260 (FRAME-BOUND s.1 band); the 7.62mm (any car with gmheavy, else the lab's modded loadout) shows no STOP during a 5 s hold; no CRASH / UNEXPECTED lines | the table has the before / after rows |
| 4 | **Side effects:** AI damage rate unchanged (MP-AI-DAMAGE-RATE rows, host + joiner, n 2); LAN smoke on two lab copies (the joiner hears the host's MG; SH packet count per shot unchanged); the owner's T05 drive: muzzle flash and tracer look right at 120 fps; `I76_SIM_TICK_INPUT` early-tick boots clean | `<lab>\tools\mp-ai-damage`, game-mpo-a/b; console under the lock | no regression row | the record's s.4 says so |
| 5 | **Owner / tester ear test:** blind A/B at the console, tick19-42 vs tick19-42 + MG_EVEN (+ timer fix), 30 s of 50cal fire each, order randomised, n 2; then the tester build with the fix | TESTER-BUILD route | his verdict | the tester confirms |
| 6 | **Classic 20 option** (s.3.2): preset tick19-50 = tick19-42 with `I76_SIM_TICK_MS=49.9`, settings line `sim rate`, help text, LAN note in the README; the T05 / T06 rows (take-off speed, accel) and a tick-factors row at 49.9 | PLAY-i76.ps1 schema, presets, README | STEP-LENGTH-CURVE's rows at 49.9; the owner drives it | opt-in, documented, measured |

Public issue text: no exe addresses, no names (link this record).

## 5. Files and open questions

- New: `<lab>\tools\mg-stutter\mg_cadence_sim.py` (the replay; `python mg_cadence_sim.py` prints s.2.2's full table for three guns and
  ten arms), `<lab>\tools\mg-stutter\mg_tab.py` (event-log tabulator: shot intervals, sound starts per shot, burst lengths).
- Read: ghidra `004a6470.c` / `004a6e90.c`, flows.csv (call sites), `subsystems/weapons.md` / `sound.md` / `physics.md`,
  `data/fmt/l_defs.py` (GDFC), FRAME-BOUND-SYSTEMS s.1, TWO-CLOCKS, WHOLE-SIM-TICK, STEP-LENGTH-CURVE, FIX-INVENTORY (stock20 =
  46.9 / 62.5 ms steps), music-fix/simtick.c (sustained sounds, tick-factors, `apply_simtick` 10..100 ms range).
- Open: (1) whether a stopped MG loop restarts from its head (SOUND_START "came back from parking" bit; step 1 tells); (2) the burst
  length the owner prefers (50 ms = 1997; the loop is designed for continuous play, so a longer hold is a taste question for step 5);
  (3) the FFB gun rumble stays on the tick grid - a wheel player may still feel the gallop; same mechanism, a later lane;
  (4) `I76_FIRE_TIMER_FIX` on by default (10.00 /s, the .gdf's rate) or off (9.6, 1997's 24-step rate)? Recommended on: the tester's
   reference is 1997 at 20 fps, which had 10.00.

## 6. Results (Opus implementation lane, 2026-10-25 afternoon)

Code: i76-everywhere 58e3227 (`I76_MG_EVEN`, `I76_FIRE_TIMER_FIX`, `I76_MG_SOUND_HOLD_MS`, `I76_MG_SOUND_NEW_MS` in simtick.c;
`sim rate = classic` in PLAY-i76.ps1's settings schema; music-fix/README.md row). Proxy built from main 58e3227 = **1d22df46**,
installed in the lab's dev and test copies (s.6.5). QA issue: #119.

**Rig.** The laptop bench was held by the terrain-pass lane (and later an unlocked game) all afternoon, so every row is this PC,
headless: the lane twin `mgs-20261025` (= the test copy's files, i76.exe 6319abf7, nullglide / nullddraw stubs, input.map + a
`weapon_fire { + joystick1 Button1 }` block for the harness pad) on a private desktop, own shm suffix, `I76_MUTE` + the per-pid
watcher, movies and cutscenes skipped, FFB off, the console lock per boot batch. The old frame-bound runner could not be reused (its
copy `game-fbs` is retired and the drive block it needs exists only in lab twins), so it was rebuilt: lab `tools\mg-stutter\mg-run.ps1`
/ `mg-batch.ps1` (boot), `mg_live.py` (fb_live's `guns` with the fire button through the proxy's `I76_DRIVE_INJECT` pad, the 50cal row
made primary, player frozen 12 m from the parked t05cm03, 20 s held trigger, fire continued after the kill so >= 190 shots per boot),
`mg_tab2.py` / `mg_sum.py` (each telemetry event on the wall clock of its `I76_FRAME_LOG` frame: SHOT grid in sim time, MG loop
SOUND_START intervals and STOP - START burst length in wall time, DPS from the first hit to the kill), `mg_jump.py` (the T05 canyon
jump of phys-suite's `canyon` phase on the pad throttle). Every boot: `I76_TELEMETRY=1 I76_SOUND_EVENTS=1 I76_DAMAGE_EVENTS=1`,
display capped at 120 fps unless the arm says otherwise. Captures: lab `captures\mg-stutter-20261025\<arm>-<tag>.*`.

Two tabulation notes: the MG loop names arrive as `wmmgun.w` (the voice name keeps the extension; the first `mg_tab.py` split only at
the NUL and matched nothing); the first start interval of a pull is left out of the interval statistics (the pad press is an
`I76_SIM_TICK_INPUT` early tick, whose stretched segment draws the second shot ~16.7 ms later: what the screen shows too).

### 6.1 Live baseline rows (s.4 step 1; 50cal, n 2 per arm, ~190-200 shots per boot)

| arm | shot interval, sim (mean / sd, pattern) | rounds / s | MG loop starts per shot | start interval, wall (mean / sd) | burst (STOP - START), ms | display frame |
|---|---|---|---|---|---|---|
| t41.667 (tick19-42, today) | 104.1 / **20.8-21.7** [83 x95, 125 x94] | 9.61 | 1.00 | 104.2 / **20.9-21.1** | 41.5-41.7 | 8.33 ms |
| t42 | 105.0 / 21.0-21.9 [83, 125] | 9.52 | 1.00 | 105.1 / 20.5-21.5 | 41.7-42.1 | 8.33 |
| t49.9 (no fix) | 99.8 / 0.0 [100] | 10.02 | 1.00 | 100.0 / 4.1-5.0 | 49.7-50.5 | 8.33 |
| stock20 (preset stock + I76PATCH.DLL, GOG limiter) | 100.3-100.5 / 7.6-8.4 [108, 92, 96: the 15.6 ms clock's 46.9 / 62.5 ms dt] | 9.95-9.97 | **0.50** | **200.5-200.9 / 1.8-2.8** | **150.1-150.4** | 50.0 |
| vanilla (preset stock, patch off, capped 60 fps) | 107.1-107.4 / 6.4-7.1 [108, 92] | 9.31-9.34 | 1.00 | 107.1-107.4 / 8.5-8.7 | 33.5-33.6 | 16.67 |
| e24 (stock loop at 24 fps, 1 ms clock) | 103.4-103.5 / 20.4-20.7 [83, 125] | 9.66-9.67 | 0.51 | 200.8-201.8 / 20.8-21.7 | 122.5-123.4 | 41.67 |

Against the replay (s.2.2): **t41.667 confirmed live** (sd 20.8-21.7, 83 / 125, 9.61 /s, 1.0 start per shot, one tick-long chunk
of the loop per shot); t42 and e24 gallop the same way; vanilla matches (107.2 / 8.3 predicted). **stock20 differs from what s.1.3
assumed**: the shots are even in wall time (two 50 ms frames each), but the loop is NOT chopped once per shot. The sound update of the
frame that starts a voice does not consume its keep-alive, so the loop survives the frame after its start, is refreshed by the next
shot and stops one frame later: **150 ms on / 50 ms off, one restart every second shot (5 per second)**, start intervals 200 ms sd
1.8-2.8. e24 does the same on its 42 ms frames (123 ms bursts, 0.51 starts per shot) and vanilla's bursts are two 16.7 ms frames, not
one. So 1997 at 20 fps was even, and its MG sound was a 5 Hz chop of a long loop, not a 10 Hz one. Open question s.5 (1) does not
matter for the cadence; (2) is now a choice between two measured patterns (s.6.2).

### 6.2 The fix (s.4 steps 2-3; t41.667, 50cal unless said)

Static: `mg-even: ON ... 6/6 sites ...; fire timer 10 ms leftover rule REMOVED (1/1 site ...)` in every boot's log; the two FireShot
calls chain behind the telemetry wrapper (`already calls ... - chained`). The 0.01 compare is ONE site, fcomp [0x4beb38] at 0x4a6627
(lab `tools\mg-stutter\dis_timer.py`); the other jumps to 0x4a6b40 are the trigger-up and empty-gun exits, left alone. No CRASH /
UNEXPECTED line in any boot (51 single-player boots, 6 LAN pair sessions).

| arm (build) | n | rounds / s | starts per shot | start interval, wall: sd (ms) | within 1 ms of 100 | within one frame | burst mean / sd (ms) | frame period sd during the hold |
|---|---|---|---|---|---|---|---|---|
| today (t41, MG_EVEN 0) | 3 | 9.61 | 1.00 | 20.7-21.1 | 0.0 % | 0-1.6 % | 41.5-41.9 | 1.1-2.2 |
| MG_EVEN, drop rule kept (t41m) | 3 | 9.60-9.61 | 1.00 | 5.3-12.2 | 0-0.5 % | 7-93 % | 50.4-52.2 | 1.1-2.4 |
| **MG_EVEN + timer fix = the defaults (t41mf)** | 14 | **10.00-10.02** | **1.00** | **2.5-6.6** (7.1-9.0 in the three boots with frame sd 3.1-4.3) | 39-97.5 % | 84-99.5 % | **50.1-54.1** / 1.0-6.5 | 0.4-4.3 |
| defaults + `I76_MG_SOUND_NEW_MS=50` (the 1997 pattern) | 2 | 10.02 | **0.50** | interval 200.0, sd 0.7-3.1 | 80-96 % | 99-100 % | **149.2-149.9** | 0.9-1.0 |

- **The gallop is gone**: 83 / 125 -> 100 / 100 with the occasional start one display frame early or late. **The sd <= 1 ms
  acceptance line is NOT met on this rig**: the best boots (frame period sd 0.4-1.0 ms) give 2.5-2.9 ms with 91-97.5 % of the
  intervals within 1 ms; the rest are single starts moved by one 8.3 ms frame, and their number follows the rig's frame pacing (the
  null renderer + the FPS cap on a PC that other sessions loaded: single frames up to 45-64 ms; across the 14 boots the sd rises
  with the frame period sd, 0.4 -> 2.9 ms, 1.0 -> 2.5-4.3, 1.5-2.4 -> 3.6-5.7, 3.0-4.3 -> 6.6-9.0). An interleaved A/B of the frame-choice clock (the camera wrapper's own QPC vs the frame's top, n 3 each: 3.6-5.7 vs
  3.7-5.7 ms) showed no difference beyond that noise; the frame's top is kept. A row on a vsync-paced console (the laptop when free)
  is still owed; the ear test is #119.
- With the drop rule kept the dropped shots fall on the tick's start and play on the tick frame, late by the accumulator: 100 / 108
  or 117 / 92 depending on the tick's phase against the frames (sd 5-12). The timer fix is what makes the grid exact: on by default.
- 1.0 start per shot, bursts 50 +- 8 ms: met. Rate 10.0 +- 0.1 /s: met (10.00-10.02, the .gdf's 10.0; today 9.61).
- **SHOT grid unchanged with MG_EVEN alone**: t41 and t41m give the same 192 shots, 104.06 / 20.83 ms, 83 x96 / 125 x95, 9.61 /s.
- **DPS**: this copy's difficulty doubles the .gdf damage (50 per 50cal hit, the frame-bound band was measured at 25), so the band
  is 486-520 here: today 485-491, MG_EVEN alone 473-494, the defaults 487-509, t49.9 501 (12-28 hits per boot before the kill; +4 %
  with the timer fix = the rate).
- **20 /s gun** (T05 loads no 7.62mm (`defs_loaded`), so the 50cal's definition was set to fire_rate 20 in memory, `mg_live.py
  --set-rate 20`; its loop is wmmgun, not whmgun): today 19.23-19.26 /s, 0.25 starts per shot, bursts 166-168 ms, 45-57 stops during a
  12 s hold; the defaults 20.07 /s, **one start and one stop per hold (continuous)**, n 3; t49.9 + fix 20.04 /s continuous (n 1);
  an exact 50 ms tick **halves it to 10.0 /s** (n 1, the s.1.1 trap confirmed).
- **I76_MG_SOUND_NEW_MS** (added, default 0): extra hold for a request that starts the loop. At 50 it reproduces stock20's sound
  exactly (0.50 starts per shot, 150 ms bursts, 200 ms apart) on the even grid. Which one sounds right is #119 step C.

### 6.3 Side effects (s.4 step 4) - LAN on the PC pair (game-mpo-c host, game-mpo-d joiner, The Crater, IPXWrapper at log level 4)

The laptop pair was not free; lab `tools\mp-ai-damage\mad.py` on the PC pair with a lab twin of 58e3227's tree (build-mad.sh tag
mgs3: + shellclick, cruise, skey, the joiner shooter; 197c0351):

| run | MG_EVEN | host 'AT' round gap, median of each window | joiner applied gap (live cars) | snap at apply, window medians | crashes |
|---|---|---|---|---|---|
| rate, n 2 | on (defaults) | 109 ms in 24 / 24 windows | 109-110 ms | 0.09 / 0.31 m | none |
| rate, n 1 | off (`I76_MG_EVEN=0 I76_FIRE_TIMER_FIX=0`) | 109 ms in 12 / 12 | 109-110 ms | 0.24 m | none |
| MP-AI-DAMAGE-RATE P3 (66f0781) | (none) | 109 | 109-110 | 0.08-0.15 m | none |

- `dmg`, n 2 (the joiner shoots the AI): 15-16 lab shots, the host's damage words changed 19 / 24 times and every change reached the
  joiner's drawn rows, 0-16 ms after the host's send (GetTickCount); n 1 more with the counters on: host 553 weapon shots (504 with an
  offset, 1008 flash / sound calls deferred, 926 played on their frame, 82 at the next tick, 0 dropped, 0 faults), joiner 532 (996
  deferred, 0 faults). No CRASH line on either side. The SH fire packets are sent by weapon_FireShot after the three moved calls and
  are not touched by construction; their count per shot was not measured separately.
- `I76_SIM_TICK_INPUT`: on in every tick boot (the pad press is an early tick at each pull): clean.
- Not run here: the owner's T05 drive at 120 fps for flash and tracer looks (in #119, A step 2-3).

### 6.4 Sim rate 20 (s.4 step 6; renamed from "classic" 2026-10-25)

`sim rate = 20` (or `24`, the default; steps per second; `classic` stays a silent alias for 20) in i76-settings.txt (Advanced group) sets `-TickMs 49.9`
through the launcher's existing tick path; a `simulation tick` line wins over it; the launcher prints and logs "single player - in a
LAN game every player must set the same sim rate". Dry runs: `tick 49.9 ms: 20 ticks/s, the car in one 49.9 ms step`; with both
lines: `sim rate = 20 - NOT applied: the simulation tick line ... wins`. tests/test_settings_file.py + test_presets.py: 35
passed. There is no network check of the tick; the option cannot know at launch whether the player will host or join, so "single
player" is the help text and the log line, not an enforcement.

At 49.9 ms with the defaults (n 6): 10.02 rounds / s, start interval sd 1.1-5.0 ms (frame sd 0.7-2.6), bursts 50.1-56.8 ms, the 20 /s gun continuous - even,
as at 41.667 with the fix (49.9 alone, without the fix, is already even in sim time: sd 0 shots, but the starts land on the tick frames,
sd 4.1-5.0 against the 8.33 ms display frames).

T05 canyon jump (aaramp4, placed 150 m out at 56 m/s, full throttle on the pad, GOD; 3 attempts per boot, n 2 boots per arm; half the
second / third placements of a boot did not start on the run-in, a driver limitation, those are dropped):

| arm | jumps | speed at the lip (m/s) | take-off vertical speed (m/s) | air time (s) |
|---|---|---|---|---|
| t41.667 + fix | 3 | 54.06 / 55.18 / 52.33 | 14.73 / 15.04 / 14.24 | 3.67 (1 landing in the 8 s window) |
| t49.9 + fix (classic) | 4 | 53.92 / 52.72 / 53.53 / 53.58 | 14.61 / 14.27 / 14.50 / 14.51 | 3.59 / 4.79 / 4.69 / 4.89 |

No difference beyond the run-to-run spread in take-off (STEP-LENGTH-CURVE predicts +0.5-1 m/s from 42 to 48 ms; this n cannot see
that); the air times differ by where the car lands, not by the step. **Feel notes for the owner's QA (#119 B):** classic integrates
the car in one 49.9 ms step instead of 41.667 (the same physics as a 1997 PC at a steady 20 fps; jumps a little longer by the step
curve, the hazard / scrape / radar per-frame factors engage at x1.2 under the tick), the world updates 20 times a second instead of 24
(the drawn motion stays interpolated at the display rate), and a control change waits up to 50 ms instead of 42 for the next tick
when it does not trigger the early tick. It has not been driven by a person.

### 6.5 Installed (s.4 step 4)

| copy | STRLKUP.DLL | PLAY-i76.ps1 | kept |
|---|---|---|---|
| lab dev-gold | dba46ea2 -> **1d22df46** | 3adc51b5 -> 195b834b (main 58e3227) | `<name>.<md5-8>-pre-mgs`, VERSION.md.9a37bbbb-pre-mgs |
| lab test-gold | 045f4e05 -> **1d22df46** | 3adc51b5 -> 195b834b | `<name>.<md5-8>-pre-mgs`, VERSION.md.7541ff56-pre-mgs |

Both VERSION.md files carry the entry. Not in the main copies or on the Macs (family rollout: every LAN machine needs the same
md5, and the timer fix changes the sim). Launcher dry runs of both copies with OWNER-2300-ALL: exit 0. The new PLAY-i76.ps1 also
brings main's Kit 0.8.1 launcher changes that the copies did not have yet. Lab twin `mgs-20261025` (null renderers) is this lane's;
archive or delete it when #119 is closed.

### 6.6 Open

- A start-interval row on a vsync-paced console (laptop bench), to settle the <= 1 ms line on real frame pacing.
- #119: the owner's / tester's ear test (A), the classic feel (B), the 1997 sound pattern (C).
- The FFB gun rumble is still on the tick grid (s.5 (3)); Nitro has no site map for the seven sites (`mg-even: not on Nitro`).
