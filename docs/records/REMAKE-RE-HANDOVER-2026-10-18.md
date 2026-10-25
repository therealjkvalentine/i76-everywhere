# Handing the reverse-engineering to the remakes: Godot remake and Unreal port (2026-10-18)

The owner's questions, verbatim: "The Godot remake was before we had reverse engineered the engine and I don't know
that it worked yet / was never play tested and didn't seem to have the wheels on the car. That is a clean room
implementation no? And tips we can give it now that we've finished the reverse engineering work? Can we give that
version the benefit of what we learned in that process in its entirety? code and tests to reimplement
exactly/faithfully? What if anything would carry over to unreal if he wants to do a version in that too/instead?"

This extends [REIMPLEMENTATION-ENGINE-PROPOSAL-2026-10-17.md](REIMPLEMENTATION-ENGINE-PROPOSAL-2026-10-17.md) (commit
3486331), which already compares the engines and lists the spec documents. Not repeated here. Paper study: no game
run, no install touched. The remake's code was read, not changed. New files this pass:
`<work>/i76-unreal\conformance\` (the conformance pack, i76-unreal commit 7c40b07) and
`<work>/i76-remake\docs\RE-HANDOVER.md` (pointer plus top-10 tips).

## Short answers

- **Did the remake work?** It runs, mostly headless. Its built-in test driver ("bot") plays the missions unattended;
  windowed runs were screenshotted and matched the headless runs to the second. There is **no record of a person ever
  playing it**. Its physics were compared only with recordings of our patched Gold exe at 20 fps, never with retail 1.0.
- **Wheels.** Wheels are modelled in the physics and are drawn in the windowed game (a wheel mesh per slot, spinning
  and steering), but the remake's own screenshots show them **standing outboard of the bodywork**, and one shot shows
  a car with empty wheel arches. So "didn't seem to have the wheels on the car" matches its own pictures. Cause not
  diagnosed (no run here).
- **Clean room?** It is a **spec-driven** reimplementation: no disassembly or decompiler output was pasted into it.
  But the specs it was written from were themselves produced by disassembling the Gold exe, they quote exe addresses,
  and 31 batches of the remake's questions were answered by static reading of the exe. Both sides were run by the same
  family with AI sessions. Whether that wall is high enough is the family's call (section 1.4).
- **Tips now.** Ten, in `i76-remake\docs\RE-HANDOVER.md` and section 6 below. The biggest: its step is 24 Hz; the
  1997 design is a 66.7 ms tick split into 2 x 33.3 ms substeps, and the remake already has the engine's split rule,
  so the change is mostly one constant plus re-running every test.
- **"In its entirety"?** Yes, in the form the remake already uses: prose specs, numbers and tests. The numbers that
  define "faithful" are now in one machine-readable file (section 3). What should not move across is code derived
  from disassembly (the proxy's patch code, decompiler output).
- **Unreal.** Everything except the GDScript itself carries over: specs, formats, constants, loop order, the
  conformance pack, the test protocols, and the remake as a working reference to port from (section 5).

## 1. What the Godot remake actually is

### 1.1 Facts

| | |
|---|---|
| where | `<work>/i76-remake`, no git remote, GPL-3.0 (`LICENSE`) |
| history | 286 commits, first 64fc1d7 (2026-10-03, ZFS reader and LZO), last 2189102 (2026-10-07 06:05, ROADMAP milestone 58) |
| language | GDScript only, Godot 4.7 standard build (README "not .NET"); 70 source files, 24,077 lines in `src/`; 27 test scripts, 6,164 lines in `tests/` |
| docs | `README.md`, `docs/STATUS.md` (101 lines, owner summary), `ROADMAP.md` (3,196 lines, per milestone), `SPEC-GAPS.md` (1,401 lines, every guess), `SUBSYSTEM-MAP.md` (1,051), `MAC.md` (48) |
| stale | README line 9 still says "a placeholder car model. It has no missions, sound or menus yet" (milestone 2 text). STATUS.md is current |

### 1.2 What it was built from

1. **<re-archive>'s format reference** (`data\FORMATS.md`, `FORMATS-tables.md`, the `data\fmt\*.py` parsers): the loaders in
   `src/io`, `src/formats`, `src/world` (README "Asset-loading model").
2. **<re-archive>'s subsystem specs** (`subsystems\physics.md`, `engine.md`, `ai.md`, `damage.md`, `weapons.md`,
   `mission.md`, `camera.md`, `renderer.md`, `sound.md`; `data\FSM.md`). These are prose written from static reading of
   the Gold exe (md5 9a232dcc, `ghidra\i76_ref.exe`), and they cite addresses: physics.md has 538 `0x4xxxxx`
   references, ai.md 677.
3. **"Remake gap answers"**: the remake logged each guess in `SPEC-GAPS.md`; <re-archive> answered in prose, 80 dated
   "Remake gap answers" sections across 9 subsystem files (index `<re-archive>\status\remake-gap-answers-2026-10-04.md`:
   "Static readings are of md5 9a232dcc"). The remake counts 31 batches by milestone 58. <re-archive> commit f95655b5 notes
   "physics.md scrubbed of two decompiler tokens", i.e. the specs were kept as prose on purpose.
4. **Recordings of the original** used as test oracles, read from the owner's disk at run time:
   `tests/ab_drive.gd` against `<re-archive>\verify\runs\drive\*\telemetry.csv` (T01, Jade's Piranha, our exe at the stock
   ~20 fps cap); `tests/trace_compare.gd` against the lab's AI traces (`<lab>\autotest\runs\ai-traces-2026-10-06`:
   the pristine GOG AiO exe md5 60ABF7BC, stock 20 fps). Both references are the **Gold lineage at ~20 fps**; neither is
   retail 1.0.
5. **The player's own install** at run time (`I76.ZFS`, `miss16\`, `ADDON\`, the GOG `music\` folder), read-only. No
   game data in the repo (`.gitignore`).

The remake's code repeats what the specs say down to the address: 34 of its 70 source files carry exe addresses in
comments (225 distinct `0x4xxxxx` values) and 89 distinct RE function names (`physics_ComputeSteerYawRate`,
`entity_TickVehicle`, ...). Example: `src/physics/vehicle_sim.gd` line 14,
`const R_GEAR := [3.0, 0.0, 1.67, 0.96, 0.67]  # 0x4f8640`.

### 1.3 Did it run, and was it play-tested?

- **Headless bot runs**, the main evidence. STATUS.md "Which missions win": seeds 1-4, 15 minutes each, milestone 58:
  27 of 48 runs won over T01-T12, 0 of 20 over T13-T17. T01, T02, T03, T06, T09, T12 won 4 of 4; T08 3 of 4; T04,
  T05, T07, T10, T11 0 of 4. That is the bot's skill as much as the game's fidelity; the two were never separated.
- **Window shots.** `<work>/i76-remake-tools\shots\` holds 134 screenshots from milestones 4-43, taken by
  `shoot-won.ps1` from the windowed game with the bot driving at `--speed=8`. Several "won" shots match their headless
  run to the second (STATUS: T12 seed 1 won at 457.9 s windowed, 458 s headless). One divergence is logged: T01 was
  not won in the window twice while the same commit wins headless in 335-399 s. A determinism test
  (`tests/determinism.gd`) checks that the windowed frame loop and the headless loop give the same state hash.
- **Play-testing by a person: none recorded.** The ROADMAP and STATUS mention the owner only as the person whose
  console the runs borrowed ("Stopped early: the owner took the PC back", ROADMAP line 871). No milestone says a human
  drove it and judged the feel.
- **Fidelity measures it has:** `trace_compare` (one AI car's behaviour / throttle / steer / speed against the
  original's opening): T12 100.0 %, T03 99.8-100 %, t05fp03 replayed 93.9 / 92.1 % (STATUS milestone 58). The physics
  A/B is against our patched Gold exe at 20 fps. **It has never been checked against the retail 1.0 fingerprint.**

### 1.4 The wheels

- **Simulated:** yes. `src/physics/vehicle_sim.gd` keeps per-wheel suspension offset and spin; ROADMAP line 50:
  "WDFC grip / mass, WLOC wheel slots".
- **Drawn:** in the windowed game, yes. `src/game/car.gd` `I76Car.create` (lines 45-62) puts a pivot at each present
  WLOC slot and adds the wheel mesh; lines 412-417 set the suspension offset, the spin and a visual front steer of
  steer x pi/4. The mesh is `world_loader.gd` `wheel_mesh()` (line 155): the first part of the first `.wdf`'s WGEO,
  used for every slot. The mission build passes it (`main.gd` line 170); the headless `BotSession` passes `null`
  (`bot_session.gd` line 54), so test runs have no wheel meshes, which is harmless.
- **What the pictures show:** `m15-view-orbit.png` and `m15-view-reverse.png` (T01, Jade's car) show four wheels
  standing out beside the body rather than under the wheel arches. `m43-t03-s1-won.png` shows a sedan with empty,
  dark wheel arches. So the wheels exist but are misplaced or missing on some cars.
- **Not established:** the cause. Candidates to check against an original screenshot from the same camera: the WLOC
  position's frame and offset, using one `.wdf` and its first part for every slot (front and rear wheels can differ),
  and whether parked or AI cars reach the wheel path. This is a renderer bug, not a physics one: the physics never
  reads the mesh.

### 1.5 The clean-room question, short and factual

- **What open reimplementations do.** Two families. *Spec-driven* projects (OpenMW, OpenRA, Open76)
  write new code from documentation of formats and behaviour, and test against the original's observable behaviour.
  *Decompilation* projects (the sm64 and devilution style; OpenRCT2 began by replacing the original's functions one by one) reproduce the original's code from its binary. The first
  aims to share no expression with the original; the second shares it on purpose. Both need the player's own game
  data; neither ships it.
- **What the remake is.** Spec-driven, by its README's statement ("No decompiler output, disassembly or original program
  code has been copied into this repository, and none of it was consulted while writing it"). It is the classic two-side
  set-up in form: a separate repo answered questions in prose. In substance the wall is thin: the specs are
  algorithm-level descriptions of disassembled functions with their addresses, the same family ran both sides, and the
  remake's comments carry the addresses and function names.
- **What changes if the RE's constants, loop order and algorithms are fed in now.** Nothing in kind: it is the same
  channel the remake already used (numbers and prose, then tests against measurements). A step change, the loop order
  or a mass formula are facts about behaviour. What would change the character is pasting code: the proxy source
  (`music-fix/*.c`, patch bytes and hooks at exe addresses), decompiler listings, or byte tables lifted from the exe.
- **The family decides** how strict to be: keep addresses in the remake's comments (honest provenance, decomp-adjacent)
  or strip them and cite only spec section names (OpenMW-style). `docs/SCOPE-AND-LEGITIMACY.md` is the repo's stated
  posture. This record gives no legal advice beyond that.

## 2. The RE inventory to hand over

"Remake" = what the Godot remake gets; "Unreal" = what the i76sim C++ library gets. Paths: `REC` =
`i76-everywhere\docs\records`, `MAP` = `<re-archive>`, `LAB` = `<lab>`.

| item | where | what it holds (n, status) | remake gets | Unreal gets |
|---|---|---|---|---|
| **Engine loop order and the sim / draw cut** | REC `WHOLE-SIM-TICK-2026-10-17.md` s.1 | WinMain mission loop 0x40398d..0x4040c4: clock, input, pause gate, `physics_CollideAll`, input to car, `entity_TickAll` (vehicles: near path substeps, far path one step), regen, post-tick, `ai_FrameTick` (script VM + AI), turret fire, projectiles, weapons, tex anims; then camera, sound listener, draw. Sim logic inside draw code: flamer ageing and damage, smoke ageing, radar ping. Static, exe 6319abf7 | It already runs this order (`combat_world.gd` `step()`, `frame_order_on` default on): a check, not a change | The tick function's call order, as row `loop.sim_order` |
| **Step and tick** | REC `DEV-INTENT-EVIDENCE.md` C1 / C2 / P10, `DEV-GAME-CLUB-I76.md`, `PHYSICS-STEP-STUDY-DESIGN.md` (amendment 2026-10-17), `VERSIONS-AND-PHYSICS-2026-10-17.md` s.4, `STEP-LENGTH-CURVE.md` | substep < 50 ms, count = min(floor(20 dt) + 1, 20); developers designed for 15 fps (2 x 33.3 ms); everything except the vehicle step ran once per frame. Lab tick66: 15.007 ticks/s, 2.000 substeps per tick (n 4 boots) | Change 24 Hz to a 66.7 ms (or 33.3 ms) tick; its split rule already gives 2 substeps | `FixedStepClock` default 33.3 ms; tick rows in the pack, tested |
| **Vehicle physics stepper and constants** | MAP `subsystems\physics.md` (2,626 lines), `engine.md`, `simclock.md`; LAB `docs\ENGINE-REFERENCE.md` (gravity -9.8 immediate at 0x43A6A1); `docs\HANDLING-MODEL.md` (fitted yaw law; older: says "fixed 20 Hz", superseded) | Integrate, ground probe, slide law, suspension filter, attitude model, contact; 75 float constants identical in retail and Gold (EXE-DIFF-MAP) | Already ported (`src/physics/vehicle_sim.gd`); now gets a retail target | The spec plus the remake's GDScript as a reference implementation |
| **Mass and car data** | MAP `data\VEHICLES.md` s.7, `data\vehicles.csv` (294 lines) | `veh+0xa4 = VDFC.mass + ENGN.mass + BRAK.mass + SUSP.mass + 2 x WDFC.mass per wheel slot + sum(GDFC.mass of mounted weapons)`; Jade's Piranha 1951.0, Banshee 2198.0; the save's Piranha 1846.0 read back 37 of 37 boots (REC `SAME-CAR-FINGERPRINT-2026-10-17.md`) | Has the formula (`vehicle_params.gd` line 6, gives 1951.0); add the 1846 and 2198 cases as tests | Rows `mass.*` |
| **Retail fingerprint (the target)** | REC `GOLD-STANDARD-FINGERPRINT.md`, `SAME-CAR-FINGERPRINT-2026-10-17.md`, `VERSIONS-AND-PHYSICS-2026-10-17.md`; LAB `emu\results\gold-standard\retail-p166-low.json` (49 traces, 219 metrics, 20 rates, 3 fits), `retail-p133-low.json` (165 metrics); checker LAB `emu\tools\memtrace\fingerprint.py` | Retail 1.0 (1997-03-15, md5 6cc509ad) in 86Box, emulated P166 / P133, Windows 95, software renderer, lowest detail, simulation physics. The lab twin with the right car matches it within 3 % on accel / brake / yaw | Its first retail acceptance test | Phase 1 acceptance (its ROADMAP already names it) |
| **Frame replay** | REC `LAB-FRAME-REPLAY.md` (s.7.2-7.4) | The original's per-frame dt and inputs replay bit-exactly (0 mismatches in 8 replays); A/A with srand pinned 1304 of 1304 frames identical (n 3, evidence not proof); rand() callers in car motion not measured | Feed the original's inputs and compare the first frames | Same |
| **rand / srand** | REC `LAB-FRAME-REPLAY.md` s.7.2; MAP functions 004a9020, 004ad260 | `srand(time(NULL))` at mission start, 4 srand calls before placement | Already seeds everything (`determinism.gd`); keep a fixed-seed switch | Row `rand.seed_source`; seed API in i76sim |
| **AI and the mission VM** | MAP `subsystems\ai.md` (677 address references), `data\FSM.md` (14 opcodes, 96 actions, 40 missions, 25 with scripts, round-trip tested), `data\notes\fsm-actions.md`, `data\out\fsm\*.fsm` | Behaviours, route search, avoidance, fire decisions; the VM | Already ported (`src/ai`, `src/mission/fsm_vm.gd`) | Port from spec + remake |
| **AI fire and damage balance** | REC `AI-DAMAGE-BALANCE.md` (closed 2026-10-17), `AI-DAMAGE-METRICS.md` | T13 parked, retail P166: AI rounds/min 108 +- 43 (n 7; per-weapon sum 107), damage taken 2299 +- 514 /min (n 7); Gold at Champ +38 % damage (p 0.007); our exe at 8 ms steps 316 +- 105 rounds/min | A per-step fire gate makes fire cadence step-rate dependent: re-measure after the step change | Rows `ai.*` |
| **Weapons and damage** | MAP `subsystems\weapons.md` (779 lines), `damage.md` (1,033); `docs\WEAPON-STATS.md` (8 of 8 ammo figures matched live); `docs\PARTS-REFERENCE.md` | Damage chain, zones, blasts, flamer | Already ported (milestones 47-48) | Port |
| **Collision** | MAP `subsystems\physics.md` (contact model); LAB `docs\COLLISION-MISS-2026-10-08.md`, `COLL-TIMING-2026-10-12.md`, `COLL-WINDOW-DEATH-SPOT-2026-10-11.md` | Swept collision over [0, sim_dt] once per frame; stock misses at short steps (T05 barricade rams 9 of 43 stock vs 21 of 21 with the widened slab) | Know that the original's collision is once per tick, not per substep | Same |
| **Retail 1.0 vs Gold** | REC `EXE-DIFF-MAP.md` (503 lines), `I76-VERSIONS.md`, `BASE-DECISION-1.0-vs-GOG.md` s.5 | Physics code the same; Gold changed combat: difficulty damage x2.0 / 1.0 / 0.75, health-% formula, turret slew 1.5 vs 1.7 rad/s, heat-seeker cone 0.84 vs 0.94, AI behaviour stack vs one slot, `weapon_SpawnProjectile` rewritten; Gold data retunes | Pick retail rules on purpose (it reads GOG = Gold data) | Same, as config |
| **Arcade vs simulation** | REC `ARCADE-PHYSICS.md` | One entity bit (0x10000), five code sites: cuts yaw 19-30 % and flips a car upright instead of destroying it | Its `--arcade` covers only the flip | A mode flag |
| **File formats** | MAP `data\FORMATS.md`, `FORMATS-tables.md`, `data\fmt\*.py`, `data\roundtrip.json` | 43 format families, 6,368 files, 0 byte diffs, 0 parse errors (2026-10-02) | Its loaders; the parsers are the oracle for a full-corpus value diff (not done) | Phase 0 loaders and their tests |
| **Saves and music** | MAP `shell\SAVE.md`, `shell\SCREENS.md`; `docs\SAVE-FORMAT-GAPS.md`; AGENTS.md savegame.dir layout; `docs\MUSIC.md`, `MUSIC-TRACK-MAP.md`, REC `MUSIC-RETAIL-INTENT.md` | `savegame.dir` = u32 count + 60-byte records, size 4 + 60 x count; `.cmp` PartNode 0x20 then PartRec 0x54; `i76-save-editor.py --check` | Bookmark import exists; add a round-trip test with `--check` | Phase 4 |
| **Symbols** | MAP `symbols\functions.tsv` | 2,217 Gold functions (addr, size, name, hookable, subsystem; all status "proposed") | Not needed in code; a lookup when reading specs | Same |
| **Retail reference captures** | LAB `emu\results\` (`par` 317 run folders, about 120 P166 and 41 P133; `memtrace` 256; `hardware-matrix`, `same-car-20261017`, `ai-damage-runs`) | Raw captures behind every reference row | Re-mine for new rows | Same |
| **Proxy source** | `music-fix\strlkproxy.c` (8,513 lines), `simtick.c` (709), `replay.c` (370), `padmenu.c`, `cursormap.c` | About 360 hand-located call sites and patch points (337 + 20 + 3 in functions; REC `BASE-DECISION-1.0-vs-GOG.md` s.4.1): an index of *where* each behaviour lives and what was wrong with it at modern frame rates | Read as documentation of quirks (per-frame effects, latency, cursor); **do not copy code** | Same |
| **Developer testimony** | REC `DEV-GAME-CLUB-I76.md` (episodes 422-427) | Jerez (relayed): "designed to run at 15 frames per second", "everything ran in the same loop", suspension filters "resonate at 15 hertz", OK "between 10 and maybe 30 hertz"; medium confidence | Why the step is 15 Hz-based | Same |

## 3. The conformance suite

The first machine-readable pack is `<work>/i76-unreal\conformance\reference-rows.json` (65 rows, generated by
`make_reference_rows.py` from the lab reference JSONs, bands from `fingerprint.py`'s own `tolerance()`), with
`README.md` explaining how a port runs it. Key rows (P166 gold standard; mean +- sd; n samples / boots; band = pass
half-width for a candidate of 5 samples from 5 boots):

| row | reference value | n | band | source |
|---|---|---|---|---|
| substep / tick | 33.333 ms, 2 per 66.667 ms tick; never >= 50 ms | design + lab 15.007 ticks/s (n 4 boots) | exact | DEV-INTENT-EVIDENCE C1/C2; WHOLE-SIM-TICK s.3.1 |
| loop order | 12 sim calls in the s.2 order, then draw | static | exact | WHOLE-SIM-TICK s.1 |
| gravity | -9.8 m/s2 (measured 9.800 +- 1.5e-05) | 16 / 16 | 0.01 | ENGINE-REFERENCE; `g@t05` |
| mass | 1951.0 (Jade's), 1846.0 (save's Piranha, 37 of 37 boots), 2198.0 (Banshee) | | 0.05 | VEHICLES.md s.7; SAME-CAR |
| T06 strip 0-10 / 0-20 m/s | 1.168 +- 0.015 s / 4.183 +- 0.017 s | 6 / 2 | 0.05 / 0.05 | `accel.t10/t20@t06strip` |
| T06 strip distance in 10 s | 201.5 +- 0.6 m | 6 / 2 | 2.0 | `accel.d10@t06strip` |
| brake 25 -> 5 m/s | 11.881 +- 0.011 m/s2 | 6 / 2 | 0.2 | `brake.decel_25_5@t06strip` |
| steady yaw at 24 m/s, right / left / pooled | 1.107 / 1.128 / 1.117 rad/s | 6 / 6 / 12 (2 boots) | 0.023 / 0.011 / 0.015 | `yaw*.18.yaw_ss@t06strip` |
| T06 ramp A at 30 m/s: foot speed, air time, apex | 35.28 m/s, 2.265 +- 0.068 s, 28.52 m | 5 / 2 | 0.5, 0.126, 0.3 | `t06jump.*@t06strip/rampA30` |
| T05 placed 56 m/s: take-off, vy, apex | 51.62 +- 1.00 m/s, 14.45 +- 0.28 m/s, 10.66 +- 0.41 m | 7 / 7 | 1.44, 0.40, 0.59 | `jump.*@t05/placed56` |
| T05 placed 56 m/s distance (watch) | 227.6 +- 28.0 m (min 165.7, max 245.3) | 7 / 7 | 40.2 | `jump.dist@t05/placed56` |
| T05 placed jumps destroyed | 0 of 7 (P133: 6 of 10) | | Fisher p >= 0.05 | rates |
| AI fire, T13 parked | 108 +- 43 rounds/min (per-weapon sum 107) | 7 | distribution | AI-DAMAGE-BALANCE s.2, s.5 |
| rand | srand(time) at mission start, 4 calls; pinned seed gives 1304 of 1304 identical frames | 3 | exact | LAB-FRAME-REPLAY s.7.2 |

Corrections to the brief's figures, from the records:
- **"T05 56 m/s jump distance range 197-249 m" is not a retail number.** It is the span of our Gold-lineage exe's means
  across fixed steps E10-E33 (REC `ERA-ENVELOPE.md` line 28, n 5 boots per condition); WHOLE-SIM-TICK s.3.2 calls it
  "the 1997 range" loosely. Retail P166 is 227.6 +- 28.0 m (n 7), P133 207.6 +- 39.2 m (n 10), and distance is a
  watch row, not a gate.
- **"~107 rounds/min"** is the per-weapon sum (AI-DAMAGE-BALANCE s.5); the stated row is 108 +- 43 (n 7), pooled
  118 +- 48 (n 10).
- **"2 of 126" A/A fails** was true when the reference was built; the current checker's selftest reads 5 of 126
  (55 / 5 and 66 / 0, SAME-CAR s.2), drift not explained.
- **The car matters.** The fingerprint's T05 / T06 rows were driven with the bookmark's Piranha (261ci 6 cyl, 14in
  Rally, armour 9600, mass 1846), not the mission's `vppirna1` (432ci SHO V8, 1951). With the wrong car the lab read
  0-20 m/s 34 % short and yaw 29 % low; with the right one, within 3 % (SAME-CAR summary).

Other tests, not yet rows in the JSON:
- **Loop-order test.** Instrument the tick to log each stage once; assert the order and that AI, script VM, collision
  and weapons run once per tick while the vehicle step runs `substeps_per_tick` times. The remake can assert it in its
  `CombatWorld.step()`; i76sim when its tick exists.
- **Format round-trip.** For every file in the corpus, the port's decoded values equal `MAP\data\fmt\*.py`'s (JSON
  dump, 0 diffs); the corpus is the player's install, so this runs on the owner's PC only.
- **Save round-trip.** Import an original bookmark (`savegame.dir` + `saveNNN.cmp`), write it back, and pass
  `i76-save-editor.py --check`; size exactly 4 + 60 x count.
- **Mission script outcomes and AI routes.** The remake's `trace_compare.gd` is the model; re-base its captures on
  retail 1.0 when the emulator can record AI traces.

How a port runs them: headless, no drawing, a fixed seed; the mission started from its own files (`T05.MSN`,
`T06.MSN`, Instant Melee on The Crater); the car placed per the row's protocol with the row's car loadout; held keys,
never taps; one CSV line per sim state in the lab's `phys.csv` layout; then `fingerprint.py compare`, or the JSON bands
directly. Details in `conformance\README.md`.

What even our own builds do not yet pass: the lab twin at 2 x 33.3 ms (tick66) passes accel, brake, yaw and the T05
jump against P166 but flies T06 ramp A 0.33-0.47 s short (every arm, both references; cause not traced), and fails
the launch pitch and steer roll peaks (SAME-CAR s.3). A port that matches the lab there has matched our best, not
retail.

## 4. Making the spec and the tests engine-free and shared

Two ways to share:

| | A. one C++ sim library, two engines | B. one data-only contract, two sims (recommended now) |
|---|---|---|
| what | `i76-unreal\sim` (i76sim, C++17, CMake, no engine types) is the game; Unreal compiles it into its module (already: `I76SimUnity.cpp`), Godot loads it as a GDExtension | The conformance pack (JSON rows, the capture CSV layout, `fingerprint.py` as judge) plus the prose specs; each port has its own sim and exports captures |
| for | One implementation to make faithful; tests once; identical behaviour in both engines | Each port keeps its language; the remake works today; Unreal can port from it at its own pace; the judge is the original, not the other port |
| against | The only working sim is 24,077 lines of GDScript; i76sim has two classes (the clock and the file locator). A is a rewrite of the remake into C++ and takes GDScript away from the Godot side | Two sims can drift apart; every row must be checked twice |
| cost to start | months | done (this pass) for timing; physics rows need a CSV exporter in each port |

**Recommendation: B now, with A kept possible.** The pack is the contract both ports pass; the original game is the
judge. Keep i76sim engine-free (it is), so that if the M4 Max tester's C++ sim overtakes the remake, Godot can bind it later with
a thin GDExtension and the remake's tests become its regression suite. Move the pack to a neutral home when a second
consumer appears (a small `i76-conformance` repo, or `<re-archive>\conformance`); for now it lives in i76-unreal and the
remake points at it.

## 5. What carries over to Unreal

| piece | carries over? | how |
|---|---|---|
| Prose specs (MAP `subsystems\*.md`, `FSM.md`, `VEHICLES.md`, `shell\*.md`) | yes, whole | The same input the remake had |
| File formats + reference parsers + round-trip corpus | yes, whole | Loaders in i76sim, tested against `data\fmt\*.py` output |
| Loop order, tick, step rule | yes, whole | `FixedStepClock` (33.3 ms default) is in; the tick function follows `loop.sim_order` |
| Constants (gravity, gear ratios, mass formula, brake 2300 / mass, ...) | yes | Rows in the pack; the rest from physics.md / engine.md |
| Conformance pack + `fingerprint.py` + capture CSV layout | yes, whole | Already in `i76-unreal\conformance`, ctest `i76sim_conformance` passes |
| Frame replay (the original's inputs and dt) | yes | Feed i76sim the replay rows, compare per frame |
| Remake's GDScript | as a reference, not as code | Port function by function (C++ from GDScript is mechanical); its `SPEC-GAPS.md` lists every guess |
| Remake's tests and probes (`ab_drive`, `trace_compare`, `determinism`, `jump_probe`, `ramp_probe`) | as designs | Rewrite as ctests against i76sim |
| Retail vs Gold rules | yes | Config switches in i76sim, retail default |
| Developer testimony, ARCADE-PHYSICS, EXE-DIFF-MAP | yes | Reading, not code |
| Godot rendering (palette shading, LOD, sky, cockpit, HUD) | logic only | The renderer specs carry; the Godot scene code does not |
| Proxy source (`music-fix\*.c`) | no (as code) | A map of where quirks live; never copied into either port |
| Remake's GDScript loaders / sim compiled into Unreal | no | Different language; only via B-then-A above |

## 6. Top 10 for the remake (also in `i76-remake\docs\RE-HANDOVER.md`)

1. **Step.** `src/game/car.gd` line 13 `STEP_HZ := 24.0` -> 15 (66.7 ms tick; the engine's split rule the remake
   already has gives 2 x 33.3 ms substeps, AI / script / weapons once per tick) or 30 (33.3 ms tick, 1 substep, half the
   input lag). Every `1.0 / I76Car.STEP_HZ`, the tests' `DT` and SPEC-GAPS V4 / C14 / C15 / M47f follow it. Re-run all
   tests and the bot seeds after.
2. **Loop order** is already the 1997 one (`combat_world.gd` `step()`, `frame_order_on`). Add a test that pins it.
3. **First retail check.** Export the car's per-step state in the lab `phys.csv` layout and run `fingerprint.py
   compare` against `retail-p166-low.json` on T06 strip and T05 placed 56 m/s.
4. **Use the fingerprint's car**: the bookmark Piranha (261ci, 14in Rally, mass 1846), not `vppirna1` as shipped (1951).
5. **Mass**: the formula is in `vehicle_params.gd`; add 1846.0 and 2198.0 as tests.
6. **AI fire cadence**: its fire gate rolls per 24 Hz step; after the step change, measure T13 parked rounds/min
   against retail 108 +- 43 (n 7).
7. **Retail rules, not Gold**: it reads GOG (Gold) data and Gold combat rules. Decide difficulty multiplier, health %,
   turret slew 1.5, heat-seeker cone 0.84 (BASE-DECISION s.5).
8. **Simulation mode by default**; arcade is a bit with five effects (ARCADE-PHYSICS), not only the flip.
9. **Wheels**: fix placement against an original screenshot from the same camera; load each slot's own `.wdf`.
10. **Re-base its references**: `ab_drive` and `trace_compare` were recorded on the Gold lineage at 20 fps; add retail
    rows as the emulator records them; refresh the stale README.

## 7. Not established here

- Why the remake's wheels sit outboard (no run, static only).
- Whether the remake runs on today's install and Godot 4.7.2 (no fresh run; its claims are its own, 2026-10-07).
- The current fingerprint selftest count (5 of 126 per SAME-CAR vs 2 of 126 in GOLD-STANDARD): not re-run here.
- The rand() callers in car motion (LAB-FRAME-REPLAY 7.4 census not run).
- AI fire per tick at the 66.7 ms tick vs retail: WHOLE-SIM-TICK has n 1 boot per arm (82 / 139 / 351 hostile
  shots per sim minute for tick66 / tick33 / step33); TICK-LATENCY-AND-AI-FIRE never wrote its AI section and
  TICK-FINISH-2026-10-18.md does not exist yet.
- Which reference wins where P166 and P133 disagree (T05 wreck rate, jounce): owner ruling open.
