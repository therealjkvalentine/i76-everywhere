# verify/ - the verification program's runner side (phase 0, steps 1-3)

`status/VERIFICATION-PROGRAM.md` sections 2.1, 2.2 and 5. Everything here runs the **sandbox** game only
(`C:\Users\james\i76-uncap-lab\game\i76.exe`, never the Downloads install), holds `game\.console-test.lock` while it
runs, installs `i76-everywhere\music-fix\Strlkup.dll` over `game\STRLKUP.DLL` (backup `.pretest`, restored afterwards)
exactly as `TEST-FRAMERATE.ps1` does, and must run at the physical console (Glide does not start over RDP). Nothing
outside `verify\` is written.

Reused, not copied: `captures/014-framerate/fr_probe.py` (launch, direct t01 boot, player/entity wait, Esc off the
pre-start screen, scancode keys), `captures/014-framerate/focus.ps1` -> `autotest/lib/focuslib.ps1` (foreground),
`tools/telemetry/i76tel.py` (imported: header parser, decoders, CSV writer), `tools/frida_run.py` (imported:
functions.tsv loader, pristine-image reader, capstone prologue rule), `tools/census.js` (the CModule-counter design),
`tools/census_classify.py` (thresholds, and run as the legacy cross-check).

## Pieces

| file | role |
|---|---|
| `run_scenario.py <id> [--census batch.json] [--secs N] [--profile stock20\|stock60\|fixed] [--attach-after-entity \| --attach-at-spawn]` | one scripted scenario on the sandbox -> `runs\<id>\<timestamp>\` |
| `scenarios\*.json` | the replayable step lists: `mission-idle`, `drive`, `fire-each`, `melee`, `take-damage` (ram the t01 barn, trainer pokes of armour / engine / wheel); `menu-idle` (`"boot": "menu"`: plain boot, the shell main menu sits); `jump` (t01: two ramp-exit launches and a 20 m lift, >= 2 s airborne each), `radar-lock` and `camera-cycle` (melee route, i76_pristine_fix.exe: radar keys / lock / range, the F1..F11 views, binoculars, zoom, glance and orbit keys); `camera-hood`, `camera-binoc` (crash repros on the sandbox i76.exe); `camera-farclip` (F6 3 s, F1, B 3 s; run with `--exe` and `--env I76_FAR_CLIP=<m>`: the far clip x camera matrix in i76-everywhere `docs\FARCLIP-CAMERA-CRASH.md` - the crash is the int16 vertex index in `renderer_SplitTerrainEdge`, safe <= 2500 m) |
| `--env KEY=VALUE` (repeatable) / scenario `"env": {...}` | extra proxy switches for the game's environment, applied after the profile's; recorded in the manifest's `env` |
| `oracle_run.py <oracle> <run> \| --all [--runs "a/*;b/*"]` | spec equations vs recorded telemetry (section 2.4) -> `oracles\REPORT.md`; v1 runs are INCONCLUSIVE for the v2-field oracles |
| `poke.py [--only id,..] [--route melee\|t01] [--regrade <run>]` | the poke runner (section 2.5): one session, every `expectations.json` entry as A1, A2, set, B, reset, A3 -> `runs\poke\<ts>\poke.json` + `poke-report.md`; `--regrade` re-evaluates a recorded run's observation windows with the current grader, no game |
| `expectations.json` | the 4.4 mini-language entries poke.py grades (14 hand-written from the specs) |
| `run_phase1.py [--pass entity\|early]` | the unattended driver: every batch x scenario, checkpointed in `runs\PROGRESS.md`, sandbox restored after every run |
| `phase1_summary.py [--pass entity\|early\|all] [--compare other.json]` | per-function roll-up over a pass -> `runs\phase1-summary.json` / `phase1b-summary.json` |
| `census.py make-batches [--size 150] [--prefix physics,entity]` | `batches\batch-NNN.json` + `batches\excluded.json` from `symbols\functions.tsv` |
| `census.py classify <run>` / `summary <run>` | the cadence enum per hooked function -> `<run>\census.classified.json` |
| `coverage.py [--all]` | functions with zero calls across every run so far -> stdout + `coverage.json` |
| `census_frames.js` + `censuslib.py` | the Frida script (per-frame counts, callers) and its driver |
| `tellib.py` | in-process telemetry recorder (UDP 7676 -> `telemetry.csv`, `events.csv`) |
| `common.py` | paths, game-state readers (ReadProcessMemory), key table, functions.tsv lookup |

## Running

```
python verify\census.py make-batches --size 150 --prefix physics,entity      # batch-001 (150), batch-002 (80)
python verify\run_scenario.py drive --secs 90                                  # baseline, no hooks
python verify\run_scenario.py drive --census verify\batches\batch-001.json --secs 90
python verify\census.py classify verify\runs\drive\<timestamp>
python verify\census.py summary  verify\runs\drive\<timestamp>
python verify\coverage.py
```

Preflight refuses to start when an `i76*` process is running, when `game\.console-test.lock` exists, or when UDP
7676 is taken. A run takes about 35 s of boot + hand-over, then `--secs` of recording, then a clean quit (WM_CLOSE;
kill after 10 s). Ctrl-C mid-run still restores the DLL and removes the lock (`finally`).

### What a run does

1. Lock, install the proxy, start the telemetry recorder, launch `i76.exe -glide` with `I76_MISSION=t01.msn`,
   `I76_SKIP_MOVIES=1`, `I76_TELEMETRY=1`, `I76MUSIC_LOG=1` plus the profile's switches (`stock20` = `I76_FPS_CAP=20`,
   the default: the stock-era frame rate where the stepper runs 1 or 2 substeps per frame, which is what makes
   `per_substep` distinguishable; `stock60` = uncapped, 1 substep per frame; `fixed` = TEST-FRAMERATE's recommended
   set).
2. With `--census`: attach Frida (default: right after launch, 1-2 s in, which already misses part of the load since
   the entity exists at ~2.4 s; `--attach-after-entity`: once the player entity exists, pass `entity`;
   `--attach-at-spawn`: the game is started by `frida.spawn`, i.e. CreateProcess suspended - the loader and every
   static DLL's DllMain, the proxy's patches included, run while Frida injects, WinMain has not started - the batch
   is hooked (~1 s, frame 0, game state 5) and only then resumed, pass `early`), compare every target's first
   16 bytes with `ghidra\i76_ref.exe` and skip the hook when they differ (a build patch or a proxy detour sits
   there), hook the rest, start the 1 s snapshots. The manifest records `census.attach_mode`, `pass`,
   `attach_t_after_launch`, `hooks_done_t_after_launch`, `attach_frame`, `attach_game_state`, and `resumed`
   (frame / game state / entity at resume) for a spawned run.
3. Focus the window while it boots, send Esc when the play mode 0x4fe534 is 0x20 (pre-start screen), wait for the
   player entity `[[0x54a264]]+0x70`, for the frame counter 0x5a7e1c to move, and for the mission script to hand
   the camera over (`[0x4c2720] != 0x48e190`; key presses before that are lost - capture 014). That hand-over takes
   ~27 s in t01 and the car arrives at ~24 m/s.
4. Run the scenario's steps, logging every key and check with the frame, sim time, speed, gear and flags read from
   the entity (`actions.csv`). Checks are state reads, never screenshots.
5. Stop and dump the census, quit the game, restore the DLL, remove the lock, write `manifest.json`.

### Menu boot (`scenarios\menu-idle.json`, `"boot": "menu"`)

No `I76_MISSION` (so `I76_SKIP_MOVIES` has no effect: it lives inside the proxy's mission-launch patch). After launch the
runner polls the game state `0x4c2164` (mission.md: 5 = mission / data init, 6 = shell running) and taps Esc every 3 s
from 8 s on while it is not 6 (the intro movies; the shell came up at 11.6 s in the smoke run after two taps), then
sits with no input until `--secs` after launch (75 s in the early pass). There is no entity and the frame counter
stays 0, so `census.py classify` uses the `census\counts.csv` snapshots instead of the per-frame series, split at the
manifest's `start_wall_ms` (the moment the state read 6): calls only before it -> `init_only` (startup, loaders,
intro: `shell_RunPlayModeKeys` spins at ~1.3 M calls/s while the movie plays), calls after it -> `menu_only`.
Checks: `menu_up`, `menu_still_up`. WM_CLOSE at the shell exits cleanly (0.3 s).

### Scenario step ops

`{"op":"wait","s":N}`, `{"op":"tap","key":"X"}`, `{"op":"hold","key":"W","s":N}` (`"keys":["W","A"]` for a chord;
`s:-1` = until the duration ends), `{"op":"brake_to_stop","max_s":N}` (hold S until speed < 0.5 m/s),
`{"op":"check","speed_gt":v,"speed_lt":v,"gear_in":[...],"engine_on":true,"player_present":true}`.

Added for `take-damage` (2026-10-02): `{"op":"drive_to","x":X,"z":Z,"radius":R,"max_s":N,"ram_s":M}` holds W and steers
A/D in a closed loop (10 Hz) on the heading `atan2(fwd.x, fwd.z)` from obj+0x18 against the bearing to (X, Z) until
within R m, then keeps W for M s (the ram); D raises that heading (melee data: W+D reads steer -0.94 and steer < 0 turned
the heading +0.083 rad/frame). `{"op":"turn_to","heading_deg":H}` is the same loop to a heading. `{"op":"poke","what":
"armour"|"chassis"|"engine_hp"|"susp_hp"|"brake_hp"|"wheel_hp","pct":P,"side":s|"slot":k}` writes the player's value to
P% of its max through `tools\trainer\i76trainer.Game.wr` (read back; the armour / chassis HUD copies +0x178 / +0x18c
follow), logged in the manifest's `pokes`. The take-damage run (`runs\take-damage\20261002-120608`) arrived at the barn
in 17.5 s (447 m), took a 210-hp structure hit at frame 826, and the three pokes read back (armour 800 -> 80, engine
1200 -> 600, wheel 400 -> 100); 16 player IMPACT events in all.

Added for `jump` / `radar-lock` / `camera-cycle` (2026-10-02): `{"op":"launch","vy":V,"dy":D}` lifts the player object D m and sets
its velocity's y to V m/s with x/z kept (fr_probe --place's write path through the trainer, 6 writes 12 ms apart): a ramp exit at the
current heading and speed, vy 12 = ~2.5 s of flight and a 7.3 m apex; `{"op":"lift","m":M}` is fr_probe --drop (20 m = 40 frames
of fall). `check` gained `airborne`, `airborne_frames_gt`, `cam_mode_in`, `radar_locked`, `radar_range_in`. A scenario's `"watch":
["cam","radar","airborne"]` starts a 20 Hz thread that logs every change of camera_mode 0x4c2728 / the callback 0x4c2720, of the
player's radar block `[[ent+0x434]+0x70]` (+0 range index, +0xc flags: 1 on, 2 target view, 0x10 locked, +0x54 locked contact;
entity_GetRadarTarget 0x4613f0) and of the airborne flag 0x4 as `watch` rows in actions.csv (with the frame) and in the manifest's
`watch` / `airborne_spells` / `launches`. New keys in common.py: Y U K B V M N H G P C F11 F12 LSHIFT and the extended "Grey" cluster
(GREYUP/DOWN/LEFT/RIGHT, GREYPGUP/PGDN, GREYEND/HOME, sent with KEYEVENTF_EXTENDEDKEY), which input.map binds to pilot_glance_*
(bare), track_*/overview_* (Shift+), zoom_factor / track_distance (PgUp/PgDn), zoom_factor_reset (End).

Keys are DirectInput scancodes from the sandbox's **`input.map`** (the only binding file the engine reads,
i76-everywhere AGENTS.md): W throttle_up, S throttle_down (brake), A/D steer, X reverse_direction, Enter weapon_fire,
2-5 hardpoint2-5_fire (**hardpoint1_fire has no key**), I start_engine, Space e_brake, F1-F10 views.

## Output formats (`runs\<id>\<timestamp>\`)

| file | content |
|---|---|
| `telemetry.csv` | one row per rendered frame, every `i76tel_frame_t` field (`tools\telemetry\i76tel.py --layout`). `frame` = 0x5a7e1c of the completed frame, `proxy_frame` = the proxy's counter (events are stamped with it), `step_count`, `dt`, `sim_dt`, `player_present`, `flags` (0x20 destroyed, 0x8000 wreck) ... |
| `events.csv` | `i76tel_event_t` rows: SHOT (1), EXPLOSION (2), IMPACT (3); `frame` is the proxy frame |
| `actions.csv` | `t_wall,t_scn,frame,sim_time,speed,gear,flags,mode,action,detail` for every key, check, start, end |
| `mciproxy.log` | the proxy's log lines appended during this run |
| `manifest.json` | scenario, profile, env, exe/proxy md5, pid, boot timings, `start_frame`/`end_frame` (the scenario window), checks, warnings, errors, telemetry counts, `census.attest` (G-ATTEST: hooks requested/attached/skipped with reasons, errors, snapshots, fired totals) |
| `census.jsonl` | per hooked function: `addr, name, scenario, frames` (window frames), `calls` (whole run), `calls_in_window, frames_with_calls, calls_per_frame_hist` (`{"0": n0, "1": n1, ..., "64+": n}` over the window), `callers` (`{"0xRA": {n, name}}`, name = `function+offset` via functions.tsv), `first_frame, last_frame, pre_base_calls, overflow_calls, hook` (`attached` or the skip reason) |
| `census.series.bin` + `.json` | u16 little-endian calls per sim frame, row = function (`addrs[j]`), column = `base_frame + c`, `cap` columns |
| `census\snapshots.csv, counts.csv, targets.csv` | `tools/frida_run.py`-compatible cumulative counters every `--snapshot-ms`; `tools\census_classify.py --dir <run>` works on them (`census\classes.csv`) |
| `census.classified.json` | `classes` histogram, `step_count_hist`, `frames_live`, `frames_wrecked_excluded`, `first_wreck_frame`, and per function `class` + the numbers behind it (`presence, mode_count, mode_share, cv, substep_match, substep_offset, per_substep_mult, per_frame_const, event_corr, legacy_class, note`) |

### The classes (`census.py classify`)

Live frames = window frames with `player_present` and without the destroyed/wreck flags; shares are over them.

| class | rule |
|---|---|
| `never` | 0 calls in the run (coverage.py sums over runs for "every scenario") |
| `init_only` | no call after scenario start + 5 s sim time |
| `menu_only` | calls only on frames without a live player, menu-* scenarios (else `irregular`) |
| `per_substep` | on >= 95% of live frames `calls == a + b x step_count`, b >= 1 (calls per substep summed over the vehicles stepped), a >= 0 (a per-frame constant, e.g. the far vehicles' lite step); frame offsets -1/0/+1 tried (0 fits) |
| `per_frame` | on >= 95% of live frames `calls == k` (k reported, summed over objects: entity_TickVehicle = 6 = 6 vehicles ticked), or steady (presence >= 0.9, cv < 0.5: census_classify.py's per-frame rule) |
| `per_event` | present on < 50% of live frames; `event_corr` = share of its call frames within 2 frames of a telemetry event or a key |
| `irregular` | the rest |

## Known limits (2026-10-01)

- **The sandbox exe is a patched build** (md5 4fabc303; `binaries\diff-9a232dcc-vs-4fabc303.tsv`), so
  `tools\frida_run.py`'s H0 gate would refuse it; this driver hooks only entries whose live bytes equal the pristine
  image. The telemetry proxy detours `physics_ApplyCollisionDamage` 0x4a7c80 (and `weapon_FireShot` 0x4a6e90), so
  those read `not_hooked` whenever `I76_TELEMETRY=1`; their cadence comes from the telemetry events instead.
- **Counts are summed over objects.** A per-substep function called for each of 3 near vehicles reads `3 + 3 x steps`
  calls per frame; the fit reports `per_substep_mult` (b) and `per_frame_const` (a). Per-object attribution needs the
  `this` pointer (phase 2.3 trace), not the census.
- **`per_substep` needs two step counts in the run**: `stock20` gives 1 and 2 (about 80/20); `stock60` is always 1 and
  cannot separate `per_substep` from `per_frame` (the note says so).
- **t01 ends the mission about 45 s after the hand-over** (play mode 0x10, frame counter frozen; its FSM has
  `startTimer` / `failAllObj`; in one run the car had also rolled while reversing on rough ground and was destroyed).
  The live window is therefore ~900 frames at 20 fps whatever `--secs` says; a longer window needs another mission or a
  look at `data\out\fsm\t01.fsm`. The wrecked tail is excluded from the shares and counted in the summary.
- **Return addresses** come from `[esp]` at entry (`gum_invocation_context_get_return_address()` returns the hooked
  function itself under a CModule listener, frida 17.17). The 8-entry table is first-come; the overflow is `other`.
- **Not atomic**: only `calls` uses `lock incl`; the per-frame series and the caller table assume the sim's single
  thread (a hit from another thread can lose one increment).
- **Attach timing decides `init_only` vs `never`.** The hook goes in 1-2 s after launch; when it lands after the
  mission has loaded (`census.attach_entity_present: true`, run 211503 at 2.27 s) the 28 load-time functions
  (`physics_InitEntity`, `entity_Register`, `physics_WheelCreate`, ...) read `never`; at 1.0 s (runs 212220, 212619)
  they read `init_only`. Read `attach_entity_present` before trusting a `never`/`init_only` split; calls before the
  hook's base frame are `pre_base_calls`. The `early` pass (`--attach-at-spawn`) removes the race: the hooks are in
  before WinMain's first instruction, so startup, loader and init code is counted in full (the proxy's detour on
  `physics_ApplyCollisionDamage` is already visible at spawn, i.e. the proxy's DllMain has run by then).
- **Overhead is below what the clocks can see.** At the 20 fps cap hooked and unhooked runs have the same frame time
  (p50 47.1 vs 47.1 ms, mean 50.0 both); at `stock60` the display's 60 Hz is the cap and the pair reads the same again
  (p50 15.87 / p90 16.11 / p99 31.7-32.0 ms, mean 16.67 vs 16.69 ms, 59.98 vs 59.93 fps; 179 vs 182 frames over
  20 ms). That is ~1,050 CModule hits per frame (1.55 M in 1,463 frames at 20 fps, 4.54 M in 4,382 at 60) costing
  less than the ~0.5 ms a 60 Hz frame has spare. An uncapped profile (none exists: `fixed` keeps the 60 Hz display
  cap too) would be needed to put a number on it.
- **The 8-entry caller table overflows** for functions with more than 8 call sites: `physics_WheelGetGroundHeight`
  (12 wheel-slot sites in `physics_ResolveGroundContact`) puts 20,196 of 60,588 calls in `other`. NC in
  `census_frames.js` is the knob (the record layout and `dump()` offsets follow it).
- Scenarios `ai-fight` and `save-load` are not written yet (`jump`, `radar-lock`, `camera-cycle`: 2026-10-02, below); `fire-each` fires the
  2-5 hardpoint keys plus Enter (weapon_fire) because hardpoint 1 has no key. `take-damage` rams the barn and pokes;
  "take fire from one AI" is still the `melee` scenario's job (one AI car, i76_pristine_fix.exe).
- **The t01 end is not a fixed timer.** The drive / mission-idle runs end at sim 73.3-74.3 s, but the take-damage run
  (car driven 450 m north-east to the barn) ran to sim 86 s with hits still landing at 78.5 s: the FSM's
  `isWithinSqNav` / `timeGreater 30` chain (data\out\fsm\t01.fsm) ends it on where the car is, so a scenario that leaves
  the start area gets a longer window. Still not long enough for the poke runner, which uses the melee route.
- **`step_count` is not a count in stock mode.** The proxy computes `floor(sim_dt x 20) + 1` itself (strlkproxy.c:2011)
  and only counts real substeps under `I76_FIXED_STEP`. The `step_count` oracle's PASS on stock runs is therefore a
  tautology (said so in its GAPS / CAVEAT since 2026-10-02), and the poke runner cannot see a changed substep immediate
  through it; the census's per_substep series is the game-side count.
- **The melee route's "0 AI drivers" click did not take** in the poke sessions (`--ai 0`, click at 187,295 logged): the
  session saw 27 car-class and 140 ordnance impacts on the player and 496 explosions, i.e. one AI car fought it the whole
  time. Probes are graded on the frames they select, so this mostly costs INCONCLUSIVEs (arena hits, a damaged car), but
  the health-fraction expectations need an undamaged car and must run first.
- **Smoke is same-frame with health_pct**, not hit-driven: `entity_UpdateDamageSmoke` is `per_substep` in the census
  (7,681 calls) and the 0x100 bit set on the armour-poke frame itself (take-damage frame 994, no IMPACT event within 38
  frames). damage.md's "after a hit" is the call site, not the cadence (the random-surface-damage path reaches it every
  substep).

## Pass `early` (2026-10-02, `run_phase1.py --pass early`, `runs\phase1b-summary.json`)

22 runs, all ok: `mission-idle` (t01 direct boot, 60 s) for every batch and `menu-idle` (75 s) for batches 004-010 and
014, hooks in at 0.85-2.77 s after spawn with the game still suspended (frame 0, game state 5, no entity in every run).
Of the 1,201 functions the `entity` pass never saw, **321 fire here, all `init_only`** (by prefix: bwd2 60/103,
renderer 49/216, entity 26/96, object 20/65, input 17/28, vfs 16/24, heap 16/22, sound 13/32, fsm 12/53, world 11/22,
physics 11/36, weapon 11/56, image 11/33, ai 8/80, math 7/22, zfs 5/7, shell 4/79, startup 3/14, WinMain, entry,
cmdline_Parse, ...). The early-pass histogram: never 1,019, init_only 470, per_frame 297, per_event 96, irregular 54,
per_substep 53, not_hooked 10 (the entity pass's 8 plus `simclock_Init` / `simclock_Update`, whose entries the proxy's
frame cap patches). Both passes together (`phase1_summary.py --pass all`, `runs\phase1-all-summary.json`): never 880,
init_only 384, per_frame 300, per_event 279, irregular 93, per_substep 55. The shell main menu itself runs almost
nothing in the exe: `menu_only` is 4 functions (`shell_cb_10`, `sound_CdWatchdog`, `sound_CdGetMode`,
`sound_UpdateCdAudioStatus`); batch-004's menu run is a genuine void (no AI/world/object code in boot or shell). Still
never after both passes, by prefix: renderer 167, net 102 (network only), shell 75 (the DLL side's callbacks), ai 72,
entity 70, weapon 45, object 45, bwd2 43.

## The `never` pass: `jump`, `radar-lock`, `camera-cycle` x the 522 never-called camera/entity/weapon/physics/renderer/ai/object/sound/input/image/light/world functions (2026-10-02)

`census.py make-batches --from-summary runs\phase1-all-summary.pre-never.json --name never --prefix camera,weapon,physics,entity,object,ai,world,input,sound,image,light,renderer`
-> `batches
ever-001..004.json` (150 / 150 / 150 / 72). 12 runs (`runs
ever-progress.jsonl`, logs `runs
ever-*.log`), all ok, every
hook attached after the entity (150/150 or 72/72), sandbox restored after each (DLL md5 54f2de9d, no lock, no .pretest).

- **`jump`** (t01, i76.exe, 90 s): per run two `launch` (vy 12) and one `lift` (20 m) spells of 50-64, 40 and 50-64 frames (2.5 / 2.0 /
  2.5 s at 20 fps), apex +7.3 m, each ending in a landing (flag 0x4 up at the launch frame + 1 .. 2, clear 51 frames later), 155-290
  airborne frames per run; dvy/dt over consecutive airborne frames reads -9.80 (median; p10/p90 -9.82/-9.78). The telemetry `accel`
  field (ent+0xd4) is 0 on every airborne frame: the air path does not write it. t01 still ends ~50 s in (mode 6 end-orbit camera at
  the kill; `groove` reaches the car).
- **`radar-lock`** (melee, i76_pristine_fix.exe, one AI car): range toggles 1 -> 0 -> 1 (frames ~517 / 587), lock (flags 0x1 -> 0x11,
  contact set) at ~824, Y/Q re-target 912 / 941, K target-view flag 0x2 on 971..1020, F4 -> camera_mode 4 cb 0x409140 at 1050, F5 ->
  0x408c60 at 1119, F1 back to 0 at 1189, U clears the lock (0x11 -> 0x1) at 1464, re-lock 1601, cleared 1848. The first T must come after
  ~10 s of driving: the AI car starts outside the radar's 600 m (runs 134101 / 134438, T at frame 574 found no contact; their locks came
  with the later T). The loadout is one `gmmedium` MG: no missile weapon exists in the melee car, Tab cycles one row.
- **`camera-cycle`** (melee route too): F2 orbit 7 (0x4061b0), F3 chase 1 (0x407ad0), F4/F5 target 4 (0x409140 / 0x408c60, once locked),
  F6 hood 1 (0x407680), F7/F8 mounted 1 (0x408240), F9 chase, F10 overview 3 (0x408a10), F1 cockpit 0, B binoculars 2 (0x4071a0), F1/F2
  again, F11 no-op (no player projectile for a gun), V no mode change; 14-16 callback changes per run, all frame-stamped in actions.csv.
  **Not on the sandbox i76.exe**: it dies with 0xC0000005 one frame after F6 switches the callback to 0x407680 (runs camera-cycle
  131502, camera-hood 131634) and ~1 s after B (camera-cycle 132035, camera-binoc 132251), 4/4; i76_pristine_fix.exe survives both
  (camera-hood 131741 and every census run). The only sandbox patch in the camera range is 0x4059de..0x4059e3 (camera_ApplyViewOptions).
  `scenarios\camera-hood.json` / `camera-binoc.json` are the repros.
- **Census**: of the 880 `never`, 522 were hooked here and **130 fire** (camera 26/33, entity 22/70, ai 21/72, object 21/45, renderer
  12/167, physics 11/25, weapon 7/45, world 5/11, sound 2/19, image / input / light 1 each): 93 per_event, 21 irregular, 9 per_frame
  (`renderer_BlitBitmap`, `renderer_GetRearMirrorBitmap`, the weapon / specials / radar panel bitmap getters, `camera_CompareLookYaw`,
  `entity_HandgunIsBusy`, `weapon_InstanceOnVehicle`), 7 init_only (ai_*Road* at the melee start). By scenario: radar-lock 81,
  camera-cycle 66, jump 49. The jump's new ones are the wreck / chunk path (`entity_Wreck`, `object_ThrowDetachablePart`,
  `object_DetachAsChunk`, `object_CloneHierarchy`, `physics_WheelBlowTyre`, `physics_ApplyExplosionDamage`, smoke emitters) from the
  landings and the t01 kill, not an airborne-only path; `physics_ThrowWreckedVehicle` 1 call per wreck. Still never after this pass:
  **750** (`phase1_summary.py --pass all --compare`, `runs\phase1-all-summary.json`; the pre-pass copy is `phase1-all-summary.pre-never.json`):
  renderer 155, net 102, shell 75, ai 51, entity 48, bwd2 43, fsm 41, weapon 38, font 28, object 24, image 21, sound 17, math 15,
  physics 14. Overall now: never 750, init_only 391, per_event 372, per_frame 309, irregular 114, per_substep 55, not_hooked 8.

- **Pokes re-run** (`poke.py --only aero_drag_top_speed,gravity_air_fall`, melee route, `runs\poke61002-140824`, `poke-report-jump.md`):
  `gravity_air_fall` **PASS** on the new `jump` probe kind (roll 2 s, launch vy 12, 4 s): A1 / A2 / B / A3 = 50 / 53 / 81 / 48 airborne
  frames, dvy/dt median -9.80 / -9.80 / -4.90 / -9.80 (p10-p90 width 0.04) against x; graded on the new `accel_y` metric (dvy/dt of
  consecutive frames) because the telemetry `accel` field is 0 while airborne. `aero_drag_top_speed` still **INCONCLUSIVE** with 20 s
  probes: top speeds 50.1 / 30.0 (A/A) -> 46.0 (B) -> 53.7; the arena's shuttle legs do not reach terminal speed (speed still rising
  at the window's end) and one of the pair was blocked, so the A/A band (20 m/s) swamps the 6 m/s change. The first session
  (`runs\poke61002-140359`) died at the gravity A3 probe: the AI car destroyed the player during the 10 s `turn_to` (no player object).

## Results so far: batch-001 (150 physics/entity functions) on `drive`

Runs under `runs\drive\` (all t01, hand-over at ~27 s, mission end at sim 73.3 s in every run):

| run | profile | hooks | window (frames) | live | step_count | note |
|---|---|---|---|---|---|---|
| `20261001-211111` | stock20 | none | 576..1725 (1,150) | 1,009 | 1: 807, 2: 202 | baseline; the car was destroyed at frame 1585 (destroyed flag 0x20; 140 wrecked frames excluded) |
| `20261001-211503` | stock20 | batch-001 | 573..1463 (891) | 890 | 1: 712, 2: 178 | attached at 2.27 s, after the mission loaded |
| `20261001-212220` | stock20 | batch-001 | 556..1463 (908) | 907 | 1: 726, 2: 181 | attached at 1.03 s; **the reference run** |
| `20261001-212443` | stock60 | none | 1708..4378 (2,671) | 2,670 | 1: 2,670 | overhead baseline |
| `20261001-212619` | stock60 | batch-001 | 1710..4382 (2,673) | 2,672 | 1: 2,672 | overhead pair |

Histogram (`census.py summary`), 149 hooked + 1 `not_hooked` (`physics_ApplyCollisionDamage`, proxy detour):

| run | per_frame | per_substep | per_event | init_only | never | irregular |
|---|---|---|---|---|---|---|
| 211503 stock20 | 30 | 16 | 14 | 4 | 81 | 4 |
| 212220 stock20 | 31 | 16 | 14 | 32 | 53 | 3 |
| 212619 stock60 | 46 | 0 | 14 | 32 | 53 | 4 |

- **Same-rate control** (211503 vs 212220, both stock20): 121/150 identical; the 28 `never -> init_only` moves are the
  attach timing above, the one other move is `entity_GetWorldBoundCircleXZ` (`irregular` vs steady `per_frame`, cv 0.49
  against the 0.5 threshold: a function called ~30x a frame from `world_GetGroundHeightAndNormal`, count varying with
  the probes). Everything else (per_frame, per_substep, per_event lists) is identical between the two runs.
- **stock20 vs stock60** (212220 vs 212619): the 16 `per_substep` functions all read `per_frame` at 60 Hz (one substep
  per frame, as the limit above says); the other 133 agree.
- **New vs legacy classifier** (`tools\census_classify.py` on 212220): the legacy `per-frame` class holds the 16
  `per_substep` plus 22 `per_frame`; its `per-tick` (6) are all `per_frame` here; its `event` (24) splits into 14
  `per_event`, 4 `init_only` (load-time bursts after the first moving interval), 3 `per_frame` (steady but k varies:
  `physics_ComputeSteerYawRate`, `physics_EngineGetDrivePower`, `entity_ApplyRandomDamage`) and 3 `irregular`.
- **Per-substep multipliers** (212220): `physics_StepVehicle`, `physics_CheckImpact`, `physics_FindBodyTerrainContact`,
  `physics_ResolveGroundContact` = `0 + 3 x steps` (3 near vehicles stepped); the four-wheel functions
  (`physics_WheelUpdateSuspension`, `WheelSetSpeed`, `WheelGetContactPoint`, `WheelGetSuspensionOffset`) = `12 x steps`;
  `physics_WheelGetGroundHeight` = `36 x steps`; `physics_UpdateEngine` = `3 + 3 x steps` (the 3 far vehicles'
  `physics_StepVehicleFar` once a frame plus the near ones per substep: engine.md's "once per substep" holds for the
  near car, physics.md's far-vehicle path adds one per frame); `physics_ComputeDriveBrakeAccel` = `13 + 3 x steps`
  (the constant is `ai_GripLimitedThrottle`, 23,820 of 29,878 calls).
- **Per-frame anchors agree with the spec**: `physics_CollideAll` 1/frame from `WinMain+0xee7` (physics.md: "once per
  rendered frame from WinMain"), `entity_TickAll` / `entity_PostTickAll` / `entity_TickTurretFire` 1/frame from WinMain,
  `entity_TickVehicle` 6/frame (6 vehicles), `physics_StepVehicleFar` 3/frame (the 3 far ones), `physics_CollideBodyPair`
  507/frame (the pair loop), `physics_WheelSpinAnimTick` 48/frame from `image_UpdateTexAnims`.
- **Data findings to carry forward**
  - Return addresses `0x434730`, `0x434789` (callers of `physics_FitRadiusToCollisionBox`, `physics_BuildNodeCollisionShapes`)
    and `0x4b7d72`, `0x4b7da5` (callers of `entity_Register` x88, `entity_AddLabel` x88) fall in code that
    `functions.tsv` does not cover (`modules.tsv` mixed-gap@0x43470a len 358; `regions.tsv` gap-code 0x4b7d1c..0x4b7e24):
    two un-named functions that run at mission load.
  - `physics_EngineGetRpm` 0x46a790 (an 8-byte getter) reads `never` while rpm is live on the gauges: its only caller
    is `ffb_WriteSimState` 0x445ba0 (flows.csv), i.e. the force-feedback path, which no scenario drives. The gauges
    read the field directly. Not a pointer-table miss: Interceptor hooks the entry, so vtable-reached functions do fire
    (`physics_WheelCreate`, `entity_RadarCreate` via `object_SetClass+0x53`; `physics_EngineInitCurve` etc. via
    `object_RunPendingInits+0x81`).
  - The 53 `never` functions are destroy/shutdown (`entity_VehicleDestroy`, `physics_ShutdownCollision`, `entity_FreeTable`),
    damage (`physics_EngineApplyDamage`, `physics_WheelBlowTyre`, `physics_ApplyExplosionDamage`, `physics_ThrowWreckedVehicle`),
    radar keys (`entity_ToggleRadarRange`, `entity_RadarSelectNextTarget`, ...), aircraft (`physics_StepAircraft`),
    segment sweeps (`physics_SweepSegment*`, `physics_RayVsCollisionMesh`: weapon paths) and `physics_ApplyFriction`
    (physics.md: "looks unreachable while 0x1000 stays set" - consistent). They need `take-damage`, `fire-each`,
    `radar-lock` and a quit-to-menu tail, not a longer `drive`.
  - `entity_RadarLevelEnd` / `entity_VehicleLevelEnd` (6 calls each from `object_ClassLevelEndAll+0xba`) land on the
    mission-end frame, when the player is no longer present, and read `irregular`; they are level-end hooks and the
    enum has no class for that.
  - `physics_WheelIsFlat` is `irregular` (present on 77% of frames, mode 7): called from `physics_PlayTyreSounds` only
    for wheels that are grounded and moving, so it follows the driving, not the clock.
  - The telemetry proxy detours `physics_ApplyCollisionDamage`, so the only collision-damage cadence available is the
    IMPACT event count (2 in 212220).
