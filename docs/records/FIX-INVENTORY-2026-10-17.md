# Fix inventory: every change our port makes to stock behaviour (2026-10-17)

Lane `our-fix-inventory`. Static and document work only: no game was launched, no VM was started, nothing was written
into any game folder. The daily driver (`<games>\Interstate76-2026-10-03`) and the GOG pristine copy
(`<re-archive>\sandbox-gog\main\app`) were only read: file hashes, the `I76PLYR.DEF` bytes, presets, `PLAY*.bat`,
`PROMOTIONS.md`, and a few instructions of `i76.exe` disassembled with `tools/exe-disasm.py`.

**What the owner asked for, from this lane.** Every change our port makes to stock behaviour. For each one: what it
changes, why it was made, how it was verified and against what, which exe it assumes, and whether it touches physics,
AI or damage timing (directly, or through frame rate or step length). Any change that was verified against Gold, GOG,
W95-18 or our own feel is marked **RE-CHECK (GS)**: it needs checking against the gold standard (retail 1.0 on the
emulated P166, software renderer, lowest detail).

**Sources.** `music-fix/README.md` + `strlkproxy.c`, `presets/*.psd1`, the driver's `PROMOTIONS.md`,
docs/ENHANCEMENTS.md, docs/VERIFIED-FIXES.md, CHANGELOG.md, docs/records/{EMU-MEMTRACE, EMU-T05-CLEAN,
RETAIL-HANDLING-DIFF, GOLD-STANDARD-FINGERPRINT, ERA-ENVELOPE, WHAT-IS-STOCK, PER-FRAME-AUDIT-2026-10-03,
FRAMERATE-COVERAGE-2026-10-02}, lab `docs/AI-COMBAT-PARITY-2026-10-13.md`, `docs/DREAM-MISSION-2026-10-12.md`,
`emu/tools/memtrace/addrmap-gold.md`, `tools/envelope-rebase/seq/pacing-sim.md` (lab commit c3828d0), <re-archive>
`binaries/diff-9a232dcc-vs-*.tsv`, `subsystems/{physics,renderer,weapons}.md`.

## Summary

1. **The daily driver runs four layers of change on top of GOG.** Each layer has its own section below.
   - **(a) The exe.** `i76.exe` md5 `6319abf7` = GOG's 2019 build `60abf7bc`, which is UCyborg's AiO patch, plus our
     `USER32` -> `u32x.dll` import rename. That is 45 code clusters (2,459 bytes) away from the 2017 Galaxy exe, which
     is the Gold CD exe apart from a 2-byte import name. Section 2.
   - **(b) DLLs.** `STRLKUP.DLL` proxy `509c6df0`, `u32x.dll` `06467bd2`, the patched `i76shell.dll` `a300db63`,
     dgVoodoo's `Glide2x.dll` / `DDraw.dll`, and GOG's `I76PATCH.DLL` (the 20 fps cap) renamed away. Section 3.
   - **(c) The proxy switches.** `best-wide` sets 32 `I76_*` switches. 12 of them touch the clock, physics, AI,
     damage or input timing directly; `I76_ASPECT` possibly touches AI physics (item 6). Section 4.
   - **(d) Config.** The dgVoodoo conf, `input.map`, the AutoHotkey layers, and `I76PLYR.DEF` (detail level, and
     difficulty byte 0). Section 6.
   - **Verified today:** the driver's presets are byte-identical to the repo's 13 presets, and its proxy is the
     committed `music-fix/Strlkup.dll` (`509c6df0`).
2. **Physics code itself is untouched.**
   - No switch, and no AiO cluster, patches `physics_StepVehicle` 0x438fd0, `physics_CheckImpact` 0x436ff0, the
     attitude solver, `simclock_StepperBegin` or `entity_TickVehicle`. All of these are byte-identical between our exe
     and the Gold CD exe (addrmap-gold.md).
   - Retail 1.0 runs the same algorithm (RETAIL-HANDLING-DIFF).
   - Everything we change in the physics, we change through **time**: the clock (`I76_HIRES_CLOCK`), the step length
     (`I76_FIXED_STEP=24`), and the dt handed to a few callees.
3. **The biggest gold-standard mismatch is the step length.** **RE-CHECK (GS)**, highest priority.
   - The driver steps physics in fixed **41.67 ms** slices. That number was copied from "stock20": GOG's 20 fps cap
     on the Windows 10 15.625 ms GetTickCount (mean of 46.9 / 31.25 ms steps).
   - The gold standard steps **one step per frame at about 27-35 ms**: median 26.8 ms in melee, 31.1 ms in T05,
     34.7 ms in T06 (retail traces, lab `pacing-sim.md`).
   - ERA-ENVELOPE measured that the T05 landing turn-over rate grows with the step. Inside the era envelope it runs
     from 0 % (30 ms) to 64 % (40 ms). best-wide turned over 9 of 10 descents, and the car was lost in 4 of 5 boots.
   - EMU-T05-CLEAN measured that retail (30.2 ms median step) peaks at 53 +- 18 deg pitch, while Gold (33.4 ms) peaks
     at 80 +- 8 deg. That is n 7 each, and the step confounds it.
   - Our 41.7 ms is longer than either. The owner's "too likely to flip nose down" and "faster body jounce" fit that
     direction. It is not measured on the driver against the fingerprint.
4. **Every "20 Hz grid" fix targets stock20, not the gold standard.** **RE-CHECK (GS)**.
   - Some fixes hold per-frame work to a 20 Hz grid: `I76_FRAMERATE_FIXES`, `I76_AI_BACKAWAY_GRID`, and the AI gain
     pins at a 50 ms dt.
   - The retail P166 low-detail game runs the AI and those per-frame effects once per frame, at about 28-37 fps
     (EMU-MEMTRACE). So it makes roughly 1.5x stock20's decisions per second. Its AI dead-beat gains also see a
     ~30 ms dt on an exact 1 ms clock, not 50 ms.
   - The lab already has the retarget knobs (`I76_REF_FPS`, `I76_AI_GRID_HZ`). The envelope candidate uses
     `I76_REF_FPS=30`. Nothing in the driver uses them.
5. **The driver's AI is not at stock20 parity either.**
   - best-wide ships `I76_AI_ROLL_HOLD=0`, and it has none of the measured parity set (`I76_AI_FIXES=dodge`,
     `I76_AI_SKID_HOLD`, `I76_AI_THROTTLE_EASE`, `I76_AI_SEARCH_HOLD`, `I76_AI_STOCK_CLOCK` with `_FPS=20`).
   - Measured against stock20 (AI-COMBAT-PARITY, n 5 per mission):
     - 5-8x the AI hazard checks per second;
     - 2-4x the handbrake-turn entries, with only 18-28 % of those handbrakes reaching the physics;
     - T04 racers about 5 % quicker (AI-PACE).
   - The parity set is owner test 40. It is not in the driver.
6. **New finding (static): widescreen moves the near/far physics boundary for AI cars.**
   - `camera_ClassifyDistance` 0x406840 sends a car to the cheap far model (`physics_StepVehicleFar`: whole-frame,
     kinematic, no gravity or terrain) beyond 25 m + [0x4c2748].
   - That camera field is 600 x zoom x sqrt(1 + tan^2(fov/2)) (<re-archive> renderer.md, physics.md). It is 849 m at
     90 deg, so the switch sits at about 874 m.
   - `I76_ASPECT=3440x1440` widens the 90 deg fov to 121.7 deg. If the widened fov reaches that computation, the
     field becomes 600 x 2.052 = **1,231 m**. The switch would then sit at about 1,256 m, so AI cars between 874 and
     1,256 m from the camera would run full physics instead of the kinematic model.
   - This is arithmetic from the documented formula. Whether the patched fov reaches 0x472499 was not traced, and
     nothing was measured. **RE-CHECK (GS)**: AI behaviour, not just picture.
   - The far clip itself does not move this boundary (renderer.md: "independent of the far clip").
7. **Three real code differences between our exe and the Gold CD exe touch gameplay** (AiO clusters, section 2).
   - **(a) `ai_RecordDamageEvent` 0x415815.** It tests `[pd+0x10]` where Gold tests `[pd+0x44]`. pd+0x44 is the
     projectile's damage (<re-archive> weapons.md); pd+0x10 is unidentified. This decides whether a hit sets the AI
     "shot / rammed" timestamps. It is an AI-reaction difference, and retail 1.0's version is unchecked.
   - **(b) simclock.** AiO masks the tick; Galaxy stores a float uptime that snaps dt to 62.5 ms after 7 days of
     uptime.
   - **(c) Terrain lookups.** AiO uses unsigned bounds and Galaxy signed. They differ only off the map edge.
   - Whether retail 1.0 matches AiO or Galaxy at (a) is the one open exe question that matters for AI.
8. **Two gameplay-visible stock deviations are on by design.**
   - **`I76_FIX_HEALTH_PCT=1`** changes the health percent that damage smoke, handgun targeting, the script's
     `hpLesser`, AI fleeing and the target brackets read. It is a stock bug fix, verified only against our own exe;
     whether retail 1.0 has the bug is unchecked.
   - **`I76_BREAKABLE_BOX=1`** makes the 8 m barricade bar collide as a box instead of stock's 3 m sphere.
   - Both are **RE-CHECK (GS)** decisions: they make the game differ from every 1997 machine on purpose.
9. **Damage factor by difficulty.**
   - In our exe the player's offline weapon damage is multiplied by 2.0 / 1.0 / 0.75 for difficulty byte 0 / 1 / 2
     (0x4a76e7; shooter tested with `object_IsPlayer` at 0x4a76c5; constants read from .rdata today).
   - The driver's and GOG's `I76PLYR.DEF` both hold difficulty byte 0, so the factor is 2.0.
   - The retail 1.0 counterpart and the gold-standard runs' difficulty were not checked. The retail DEF layout ends at
     0x58 and has no byte at Gold's +0x5c. This matters for "net damage rates in both directions". **RE-CHECK (GS)**.
10. **The driver has no true stock launcher.**
    - `PLAY-stock.bat` runs preset `stock` with `I76PATCH.DLL.disabled`, so the game runs at dgVoodoo's pace (60 fps)
      on the Windows 10 tick. That is neither stock20 nor the gold standard.
11. **Some docs are stale against the driver.** Section 9 lists them.
    - ENHANCEMENTS.md says best-120 sets `I76_COLL_DEDUPE=0`; it sets 1 since promotion 16.
    - music-fix/README.md says the committed DLL is `c11f7f7d` and lacks `I76_COLL_WINDOW=2`; the committed DLL and
      the driver are `509c6df0` with it.

## 0. Frames and steps: the one rule, and what each configuration does with it

The stock engine reads its clock once per frame, as `sim_dt` in whole milliseconds from GetTickCount, with 0 read as
1 ms. It then cuts that frame into **count = floor(sim_dt x 20) + 1** physics steps, at most 20, each `sim_dt / count`
long (`simclock_StepperBegin` 0x49cc20; retail 0x451250 has the same rule). So below 50 ms one frame is one step, and
the step **is** the frame time. At exactly 50 ms or more, the frame splits into 2 or more steps.

| configuration | frame rate | clock tick | physics step | steps per frame | source |
|---|---|---|---|---|---|
| **gold standard**: retail 1.0, emulated P166, software, lowest detail | 28-37 fps by scene | 1 ms (Win95 RTM, measured) | p5 / p50 / p95: melee 24.5 / 26.8 / 33.8 ms; T05 22.1 / 31.1 / 38.3; T06 30.3 / 34.7 / 43.0 | 1 (99.5 %+) | EMU-MEMTRACE; lab `tools/envelope-rebase/seq/pacing-sim.md` |
| Gold CD exe, same machine | 23-31 fps | 1 ms | 31-38 ms (T05 median 33.4) | 1 | EMU-MEMTRACE, EMU-T05-CLEAN |
| **stock20** (GOG `I76PATCH.DLL`, Windows 10; played until 2026-10-03) | 20 fps | 15.625 ms | 46.9 ms (one step) or 2 x 31.25 ms (62.5 ms frames); 24 steps/s, mean 41.7 | 1 or 2 | WHAT-IS-STOCK; <re-archive> capture 014 |
| **daily driver** `best-wide` / `best-120` | 120 fps | QPC (`I76_HIRES_CLOCK`) | fixed 41.67 ms (`I76_FIXED_STEP=24`) | 0 on 4 frames of 5, 1 on the fifth; drawn pose interpolated | presets |
| driver `PLAY-stock.bat` | ~60 (dgVoodoo pacing; I76PATCH disabled) | 15.625 ms | 1 ms (0-tick frames) or 15.6 ms | 1 | PLAY-stock.bat text; music-fix README |
| ERA-ENVELOPE candidate (lab twin, `TEST-envelope-candidate.bat`) | 120 | QPC | fixed 30 ms (`I76_FIXED_STEP=33.3333`) | 0-1 | ERA-ENVELOPE |
| Mac build (DxWnd delay 52 ms + AiO limiter) | ~19.2 fps | Wine's clock: **not measured** | arithmetic only: a 52 ms frame gives 2 x 26 ms; 47-49 ms frames would give 1 step | 1-2 | VERIFIED-FIXES (`maxfps0=52`) |
| P133 (owner wants it back) | **not measured** | 1 ms | projection only: CPU-bound scaling (P90 / P166 Glide fps scale with clock, WHAT-IS-STOCK) puts an emulated P133 at about 0.8 x P166, so T05 steps of ~37 ms. The emulator runs ~15-20 % fast against a real P166 (EMU-MEMTRACE s9), so a real P133 lands at ~41-45 ms, near our 41.7 | 1 | projection; a run decides it |

"Frames vs steps" in one line: in stock the step length is set by how long the last frame took. In our driver the
step length is a constant, and frames only decide how many 41.67 ms steps are due. Render interpolation hides the
frames that run no step.

## 1. Which binaries

| exe | md5 | what it is | where it runs |
|---|---|---|---|
| retail 1.0 `I76.EXE` (1997-03-15) | `6cc509ad` | the March 1997 release; a different build (addresses differ, same physics algorithm) | emulator only (gold standard) |
| Gold CD `I76.EXE` | `e1dca993` | Galaxy `9a232dcc` with the import `WIN32.dll` -> `WINMM.dll` (2 bytes) | emulator |
| GOG 2017 Galaxy `i76.exe` | `9a232dcc` | the pristine reference; GOG 2.1.0.17 installs still ship it | `sandbox-gog` (read-only), fresh installs |
| GOG 2019 `i76.exe` = UCyborg AiO final | `60abf7bc` | Galaxy + 45 `.text` clusters (2,459 B) + a 132 B tail + `.rdata` (<re-archive> `binaries/diff-9a232dcc-vs-60abf7bc.tsv`) | the driver's `i76.exe.u32xorig` |
| **ours** | **`6319abf7`** | `60abf7bc` + the `USER32.dll` -> `u32x.dll` import rename | **daily driver**, golden copy, lab twin, `game-envrb`, `game-rh` (hashed today) |
| `i76_pristine_fix.exe` | `58d9dec0` | Galaxy + immi101 i76fix P1: 5 bytes at 0x499b25 (skips the CPU-speed probe with privileged instructions) | lab only; imports WIN32.dll, so the proxy's music hooks cannot attach |
| lab `game\i76.exe` | `85de44a7` | AiO lineage, lab sandbox (an older sandbox build `4fabc303` carried file patches: pools 0x402f9b-0x402fd4, far clip 0x4059de, camera rate 0x4bc528, u32x rename) | lab only |

## 2. Exe byte changes in the driver (`6319abf7` against the Gold CD / Galaxy exe)

Classification from lab `emu/tools/memtrace/addrmap-gold.md` (function names) and <re-archive>
`binaries/diff-9a232dcc-vs-60abf7bc.tsv`. "Ours" means we made the change; "AiO" means UCyborg made it and GOG shipped
it. Whether retail 1.0 matches either side is **not checked for any row**.

| cluster (VA) | function | who | what changes | touches physics / AI / damage? | re-check |
|---|---|---|---|---|---|
| 0x49c7f0-0x49cbd6 (726 B) | `simclock_Init`, `simclock_Update` | AiO | the tick is masked, so dt no longer snaps to 62.5 ms after 7 days of uptime (UCyborg: "laggy physics ... running for several days"); same globals, same stepper | **timing**: same dt on a fresh boot; `I76_HIRES_CLOCK` replaces the read anyway | no (the stepper rule is identical) |
| 0x415817 (1 B) | `ai_RecordDamageEvent` | AiO | `mov edx,[eax+0x10]` where Gold has `[eax+0x44]` (re-read today in both exes). With eax = arg+0x70 (the projectile data), pd+0x44 is the damage (<re-archive> weapons.md); pd+0x10 is not identified. The result decides whether the hit sets the AI's shot / rammed timestamps (+0xa6e4 / +0xa6e8) | **AI reaction** | **RE-CHECK (GS)**: find retail's counterpart and compare |
| 0x49318f-0x493728 (33 B) | terrain sample / normal / height | AiO | unsigned instead of signed bounds checks | physics, but only off the map edge | low |
| 0x4457b4 (5 B) | `renderer_DrawRearMirror` | AiO | the mirror's 10 Hz refresh gate is jumped over, so the mirror redraws every frame (`I76_MIRROR_RATE` restores the gate; not in a preset) | render only (cost) | no |
| 0x423419 .. 0x4253f6 | CD audio (watchdog, open, init, pause, play, TOC, volume) | AiO | MCI handling | music only | no |
| 0x470f7e-0x4710d6, 0x4b2220 (301 B) | `startup_FindCdDrive`, `shell_cb_17`, `startup_IsMinimum` | AiO | `startup_IsMinimum` -> `xor eax,eax; ret` (no "Insert CD 2" prompt) | no | no |
| 0x499b16-0x499cec | `startup_InitSystemInfo`, process-heap functions | AiO | skips the privileged-instruction CPU probe (0x499950: `cli`, `out 43h`, `in 61h`); heap changes | no known sim effect. **The CPU-speed result is not traced to any consumer**: if anything scales with it, retail on a P166 would differ | low; open |
| 0x4572d5-0x457416 (272 B) | `entity_Register` | AiO | not characterised in any doc found | **unknown** | **RE-CHECK (GS)**: diff and read |
| 0x432950, 0x446946, 0x44745b, 0x44778a, 0x4497b3-0x44a3b2 | D3D create, geometry and texture caches | AiO | renderer heaps and textures | no | no |
| 0x495331 (127 B) | `shell_CloseInGameMenu` | AiO | menu close | no | no |
| 0x4047f5, 0x46fb76, 0x49af1e, 0x49b10c, 0x4ba232, `.rdata` | WinMain, VFS cache, fonts, entry | AiO | small | no | no |
| `.rdata` IAT name | import of USER32 | **ours** | `u32x.dll` instead of `USER32.dll` (section 3) | no | no |

Not in the driver exe:
- **Mac:** PE `SizeOfStackReserve` -> 8 MB (VERIFIED-FIXES, backup `i76.exe.pre-stackpatch`). Defensive, with no sim
  effect.
- **Lab sandbox exes only:** `patch-farclip.ps1` (now done in memory) and the 0x4bc528 camera-rate file patch.

## 3. DLLs and files in the driver folder (`Interstate 76\`, hashed today)

| file | driver md5 | GOG pristine | what it does | sim effect |
|---|---|---|---|---|
| `STRLKUP.DLL` | `509c6df0` (= repo `music-fix/Strlkup.dll`) | `e5951e0f` (kept as `strlkup_orig.dll`) | our proxy: CD-audio emulation for the music, plus every `I76_*` switch (section 4); nothing acts unless its variable is set, except the music, the crash log, the trainer block and the cwd fix | through its switches only |
| `u32x.dll` | `06467bd2` (= repo `u32x/u32x_full.dll`) | - | USER32 proxy: pointer mapping, `DisableProcessWindowsGhosting` (save-screen freeze), Esc-menu mapping, modal fixes | none |
| `i76shell.dll` | `a300db63` (`.orig` = `8960fa16`) | `deb41008` | shell patches: text-entry clear restored (`tools/fix-shell-textentry.ps1`), F7 (Enter / Space close OK popups), K3 (Y / N / Esc on yes-no prompts), vehicle-rejected panel (`tools/patch-shell-*.py`) | none (menus) |
| `I76PATCH.DLL.disabled` | `a0a113d7` | (2017 install has none) | GOG / AiO 20 fps limiter, **off** in the driver | removes stock20 pacing; see section 0 |
| `Glide2x.dll`, `DDraw.dll`, `D3DImm.dll` | dgVoodoo (`8af442bc` ...) | GOG wrapper `c319a4f3` | Glide and DirectDraw to D3D11 | none directly; it sets the frame pacing, which the fixed step decouples |
| `ZGLIDE.DLL`, `win32.dll`, `SMACKW32.DLL`, `i7_sfrce.dll` | same as GOG | same | stock | - |
| `I76PLYR.DEF` | `e2a62c91` | `1bff0146` | owner options (section 6) | detail level, difficulty, Arcade Phys. off (+0x58 = 0) |
| `input.map` | `90122d37` (= repo `controls/input.map`) | `74d2da37` | the owner's WASD map | input only |
| `ADDON\` | `valepre4.vcf` (`de680a86`, = the stock file per GOLD-STANDARD-FINGERPRINT), `vppirna4.vcf`, `a2fnsg1m.cbk`, changed `vehscn.*` | - | game-written garage / car files | `vppirna4.vcf` was not compared with any stock car |

Last driver launch per `mciproxy.log`: **2026-10-08 07:43**. Promotions 15 and 16 have not been played there (BACKLOG-2026-10-16).

## 4. Proxy switches in the driver's presets

Key:
- **Phys / AI / Dmg:** direct = patches a sim site; via-step = acts through the step length or the frame grid; no = render, UI or audio.
- **Reference:** what the verification compared against.
- **Base:** which exe layouts the switch verifies before writing. "AiO" = `60abf7bc` / `6319abf7`; "both" = also Galaxy `9a232dcc`.
- `best-wide` = PLAY.bat (and `-balanced` with 1200 m); `best-120` = PLAY-16x10.bat.

| switch (value in best-wide) | what it changes | why | verified (reference, n) | base | Phys / AI / Dmg | gold standard |
|---|---|---|---|---|---|---|
| `I76_HIRES_CLOCK=1` | simclock's two GetTickCount calls -> QPC ms (exact dt; offline, the frame hook gives exact sub-ms dt) | the 15.6 ms tick jitter; AI throttle chatter | dt 50.00 ms at 20 fps (capture 014); owner played 2026-10-02 (sandbox, n 1) | both (Galaxy 0x49c85f / 0x49c929, AiO 0x49c85d / 0x49c927) | **timing: direct** | closer to the gold standard than stock20 is (Win95 measured 1 ms). Keep |
| `I76_FIXED_STEP=24` | physics always in 41.67 ms slices from an accumulator, decoupled from the frame | stock20 jump distances and chassis feel at 60 / 120 fps; 40 (25 ms) landed jumps short | stock20 body motion (capture 014); owner playtest 2026-10-02 n 1 (Mission 5 jump, body roll "good") | proxy stepper seeds 0x46312b / 0x46385c / 0x45531b | **physics: direct (step length)** | **RE-CHECK (GS), first.** The gold standard is ~27-35 ms (section 0). ERA-ENVELOPE: 41.7 ms turns over 9/10 T05 landings, the 30 ms candidate 0/24. The fingerprint's step rows fail for any fixed step by construction; the lab has `I76_STEP_SEQ` (replay the retail step sequence, lab c3828d0) |
| `I76_ENGINE_DT_FIX=1` | `physics_UpdateEngine`'s dt (0x46a333) -> 2 x sim_dt / count; with the fixed step, 0.05 s per substep | stock smooths RPM and torque with the whole frame's dt on every substep, so engine response depends on the frame rate | static; "consistent with the fixed step"; **never measured on its own** | both | **physics: direct (engine)** | **RE-CHECK (GS).** It reproduces stock20 (two substeps of a ~50 ms frame). At the gold standard each step hands the engine its own ~30 ms. Arithmetic: driver 0.05 x 24 = 1.2 s of engine smoothing per second against about 1.0 in the gold standard. Not measured. GOLD-STANDARD-FINGERPRINT blames the lab's quicker 0-20 m/s on the car / save, and this is a second candidate to rule out (E29 without switches is quick too, so the car stays first) |
| `I76_RENDER_INTERP=1` | vehicles and camera drawn between the last two physics poses (pose swapped around render, restored) | judder of the fixed step at 60 / 120 | motionless frames 31-33 % -> 0 % (n 2 missions); owner played | AiO / Galaxy hooks 0x403e69, 0x403e16 | **render; camera position lags up to one step** | no (the sim never sees it). Camera-relative tests (far classification, sound listener) see the drawn pose: at most one step, about 0.3 m |
| `I76_FRAMERATE_FIXES=1` | 36 + 6 sites held to the 20 Hz grid or scaled by dt x 20: clouds, free-look, zoom, **keyboard throttle ramp**, lock tones, radar ping, vehicle sounds, **AI throttle and steering gains (pinned to 0.05 s)**, **AI fire decisions**, **flamer ageing and damage** (main pass only, 20 / s), smoke, missile trails, ammo digits; **stationary hazard damage**, **radar-missile turn**, WMISS, AI skid / horn rolls (held only if `I76_AI_ROLL_HOLD` is not 0) | per-frame constants run 3-6x at 60 / 120 fps | clouds 0.0300 / s = stock 20 fps; hazards 20 contacts / s at 20, 60 and 120 (9 of 10 runs); WMISS 20 / s (n 2); flamer stream 18.7 vs stock20 19.0; radar turn **not measured** | both | **AI + damage + input: direct** | **RE-CHECK (GS).** Every grid and pin targets **20 per second**. The gold standard runs these once per frame at 28-37 fps (AI fire decisions, flamer ageing and damage ticks, hazard contacts, keyboard throttle ramp ~1.5x stock20). The lab has `I76_REF_FPS` for this; unused in the driver |
| `I76_AI_ROLL_HOLD=0` | the AI skid and horn rolls are **counted, not held**: rolled every rendered frame (6x stock20 at 120 fps) | 2026-10-03 the acceptance test produced no data, so "count only" | AI-COMBAT-PARITY: skid entries 2-4x stock20 (n 5, t13 / t17) | both | **AI: direct** | **RE-CHECK (GS)**, and already off stock20. Parity set: `=1` (default) + `I76_AI_SKID_HOLD=1` |
| `I76_AI_BACKAWAY_GRID=1` | the AI back_away ring (4 samples) counted on the 20 Hz grid instead of per rendered frame | T12 milk-truck opening: the AI reversed at spawn at 120 fps | T12 cut 5/5 and 3/3 = vanilla 7/7 (stock20) | AiO / Galaxy 0x41d286 | **AI: direct** | **RE-CHECK (GS):** at the gold standard's ~30 fps the ring spans ~133 ms, not 200 ms |
| `I76_INPUT_LATCH=1` | ignition / lights one-frame pulses OR-latched until a physics step consumes them | at 120 fps / 24 steps, 4 of 5 presses were lost | 50/50 vs 13/50 (n 50 per key, lab 2026-10-04) | AiO verified sites 0x44f4cf / 0x44f4dc | input (only matters with the fixed step) | no: stock has a step every frame, so nothing is lost |
| `I76_COLL_DEDUPE=1` | one collision contact applied once per physics step, not on every frame that finds it again | proxy-induced: the fixed step repeats contacts (up to 5 per impact at 120 fps) with sound, **damage** and AI damage events | part of collision G: T05 barricades 21/22 vs 7/43 (p 3.6e-10); ram damage per impact **not measured** | both | **damage: direct** | **RE-CHECK (GS):** in stock each frame is a step, so repeats cannot happen. Check ram damage per impact against the gold standard |
| `I76_COLL_WINDOW=2` + `_WHEN=stepframe` | the collision sweep and the two final accept tests use the whole step (n x 41.7 ms) on the frame whose tick runs a step | at 120 fps the sweep covered 20 % of a step, so ~2 in 3 barricade hits were missed | 36/36 vs 8/28 (lab 2026-10-09); stepframe built 10-12, promoted in 16 with G | proxy wrappers 0x403a12, 0x43e1c8, 0x43ec6a, 0x43f510 | **physics + damage: direct** | **RE-CHECK (GS):** ERA-ENVELOPE barricades knocked 7.8 / 10 in every era profile; best-wide 6.6 (outside) |
| `I76_BREAKABLE_BOX=1` | a class-4 breakable's long, thin, low default parts collide as a box, not a 0.75 r sphere (the T05 `swend_1` bar becomes a bar, not a 3 m sphere) | barricades flew off 3 m before the bumper reached them, **in stock too** | promoted in 16 on the owner's feel; G rams as above | 0x436cbd thunk | **physics: direct** | **deliberate deviation from every 1997 machine.** Owner decision; flag it as "not stock" in the release notes |
| `I76_CAM_GROUND_FIX=1` | when the eye is under the terrain, the terrain setup re-runs with the camera lifted 0.05 m (restored after) | the terrain-to-sky flash (stock skips all terrain that frame) | 0 zero-terrain frames vs 3/3 (n 3-4) | 0x490b1e | render only | no |
| `I76_ZGLIDE_TMUFIX=1` | ZGLIDE+0x1a93 `75 24` -> `eb 24` (skips the Voodoo 1 2 MB rule) with dgVoodoo TMU 8192 | texture-cache flush freezes (~80 ms each), wrong textures at 4096 | 0 flushes / rewinds / spikes (lab 2026-10-04) | ZGLIDE `05c1dde4` | render (frame hitches) | no; the Glide path only |
| `I76_GLIDE_REFRESH=120` | ZGLIDE's `grSstWinOpen` refresh code -> 120 Hz | dgVoodoo paced to 60 | 120.0-120.1 fps | ZGLIDE import hook | **frame rate** (physics decoupled by the fixed step) | no, given the fixed step |
| `I76_FAR_CLIP=1800` (balanced 1200) | the mission's 600 m far clip (0x4059de) -> value; two render pools x16 | draw distance | t01-t17 soak; owner "good" | AiO / Galaxy 0x4059de | render. **Does not move the AI near/far physics boundary** (renderer.md) | no for physics. Note: the gold standard's lowest detail has detail byte 0x654b8a = 0, so its far clip is **150 m** (0x4059e9 `0x43160000`), not 600 |
| `I76_ROAD_DIST=1800` (+ automatic `I76_ROAD_POOL`) | roads queued to 1800 m (0x4be7b8, one read site 0x48ead7); depth-bucket node pool x16 + end guard | roads ended at 450 m | t11 boots 4/4, 0 refusals; DREAM-MISSION static: no FSM or AI reader | 0x48ead7, 0x4904cd | render only | no |
| `I76_ASPECT=3440x1440` (+ `I76_HUD_SQUEEZE` default on) | aspect constant 0x4bc510 -> 4/D; 17 `push pi/2` fov sites + hood 120 deg + fov clamp widened (Hor+); HUD quads narrowed | 21:9 panel | 20/20 sites, owner approved by eye | AiO | **render, plus possibly AI physics** | **RE-CHECK (GS), new.** If the widened fov reaches the camera's far-vehicle radius (0x472499), AI cars switch to the cheap far model at ~1,256 m instead of ~874 m (summary item 6). Static check first: does the 0x472499 formula read the patched fov? |
| `I76_TERRAIN_LOD=8`, `I76_TERRAIN_TEX=8`, `I76_OBJECT_LOD=8`, `I76_SHADOW_DIST=4`, `I76_ROAD_TEX=8`, `I76_CLUTTER_DIST=300`, `I76_MIRROR_FAR=300` | render detail constants (0x493080, 0x492458, 0x4bdf94, 0x4bdfa0, 0x4be7bc, 0x4be0d0 + cell table, 0x44553c) | pop-in, sharpness | 120 fps on t01; effect "not judged" (backlog G-04) | AiO | render only. Physics terrain is `world_GetTerrainHeight` 0x493550, not the render quadtree | no |
| `I76_FIX_HEALTH_PCT=1` | `object_HealthFraction`: min(28 + 72 x worst side, 100 x worst core) instead of stock's dropped x100 | stock bug: a scratched car reads under 1 % | live: stock 0.99 / fix 49.6 on a 30 % armour, 99 % engine car | both | **AI (fleeing), scripts (`hpLesser`), damage smoke, targeting** | **RE-CHECK (GS), deliberate deviation.** Missions may be tuned around the bug; whether retail 1.0 has the same x100 drop is unchecked. AI-COMBAT-PARITY measured with this on in every condition, so the parity numbers carry it |
| `I76_FIX_LABEL_TABLE=1` | label-table growth path fixed | huge custom missions | T01 with capacity 16 grew to 272 | both | none for stock missions | no |
| `I76_CURSOR_MAP=1`, `_U32X=exe`, `_DGV=1`, `I76_U32X_SHELL_STRETCH=1`, `I76_U32X_MENU_ASPECT` | pointer mapping in menus, garage and save screen; dgVoodoo's drawn cursor | widescreen pointer | gate 23 PASS 0 FAIL (lab twin), owner n 1 on the twin | AiO + u32x | none | no |

Always on in the proxy (no variable):
- music emulation (run end exclusive since 2026-10-04; resume; guard);
- the cwd fix;
- the vectored crash log;
- the trainer control block (acts only when the trainer front end sets a flag).

None of these touch the simulation, except the trainer when it is used. It holds god mode, ammo, flats and position
on the game thread, and it forces Play Options bits.

## 5. Proxy switches that exist but are not in the driver presets

| switch | status | touches | gold-standard note |
|---|---|---|---|
| AI parity set: `I76_AI_FIXES=dodge`, `I76_AI_SKID_HOLD=1`, `I76_AI_THROTTLE_EASE=1`, `I76_AI_SEARCH_HOLD=1`, `I76_AI_TURRET_HOLD=1`, `I76_AI_STOCK_CLOCK=1` + `_FPS=20`, `I76_AI_GRID_HZ` | measured against stock20 (n 5, four missions); lab twin `TEST-combat-parity.bat`; owner test 40 | AI | **RE-CHECK (GS):** the target is stock20. `I76_AI_STOCK_CLOCK` emulates the Win10 15.625 ms tick, which the gold standard (1 ms) does not have |
| `I76_REF_FPS`, `I76_TICK_MS`, `I76_STEP_SEQ` (side build), `I76_PHYS_RATE` | lab instruments | timing | the tools for retargeting to the gold standard |
| `I76_TERRAIN_HULL_FIX`, `I76_BREAKABLE_BOX=3/4`, clutter / terrain LOD to 2500 m | promotion 18, **held** (DREAM-MISSION, now answered statically) | render; BOX 3/4 = **sign-post knock-off by a frame-hook sweep** | BOX 3/4 knocks posts 33/33 against stock24-like 5/33: far from any 1997 machine |
| `I76_COLL_WINDOW=1/3`, `_SITES`, `_SCALE` | A/B variants | collision | - |
| `I76_RETAIL_HANDLING=1` | lab only: forces entity flag 0x10000 (= Arcade Phys.) on the player | physics | its premise is withdrawn: retail's gap was arcade mode (RETAIL-HANDLING-DIFF). Do not ship |
| `I76_FAR_ENGINE_DT`, `I76_MIRROR_RATE`, `I76_SW_RES`, `I76_GLIDE_GAMMA`, `I76_FPS_CAP`, `I76_CD_FAKE`, `I76_MULTI_INSTANCE`, `I76_NO_MINIMIZE`, `I76_KEEP_ACTIVE`, music `I76_MUSIC_*`, `I76_PAD_MENU`, co-op `I76_COOP_*`, telemetry / diagnostics | opt-in | mostly none; `I76_KEEP_ACTIVE` keeps the tick running unfocused; `I76_COOP_DAMAGE` scales human damage in net games | - |
| `I76_MISSION` (+ `I76_SKIP_MOVIES`) | lab harness and `PLAY-i76.ps1 -Mission` | **which car and state the mission starts with** | **RE-CHECK (GS):** GOLD-STANDARD-FINGERPRINT's lab-vs-emulator acceleration gap (t20 -34 %) is blamed on "a different car". The lab's direct boots take their car from the lab copy; the emulator runs take theirs from the par base's saves. Same-car runs come before any physics conclusion |

## 6. Configuration (not code)

- **dgVoodoo** (`dgVoodoo.wide.conf`, copied in by PLAY.bat):
  - `[Glide] Resolution 6880x2880` (2x supersampled), `Antialiasing 4x`, `MemorySizeOfTMU 8192`,
    `EnableGlideGammaRamp true`, `ForceVerticalSync false`;
  - `[General] ScalingMode stretched_ar`, `CaptureMouse false`; `[GeneralExt] FPSLimit 0`.
  - The gold standard is the **software renderer** at 320x200. Its frame rate is what sets its step. Ours does not,
    because of the fixed step.
- **`I76PLYR.DEF`** (driver, read today):
  - graphic detail bytes `05 01 01 01 01 01 02 02 01 01 02 01 03 00 01 01`;
  - Arcade Phys. off (+0x58 = 0);
  - difficulty byte (+0x5c) 0.
  - The gold standard's lowest-detail bytes are `07 00 00 01 01 01 00 00 01 00 00 00 03 00` (RETAIL-HANDLING-DIFF).
    Byte +0x4a (0x654b8a) differs: 2 vs 0, which is 600 m vs 150 m far clip.
  - The other bytes' meanings are not mapped here. **RE-CHECK (GS):** confirm that no detail option changes anything
    the sim reads; only the far clip byte has been followed (0x4059d5).
- **Difficulty.** Byte 0 means the player's offline weapon damage x 2.0 (0x4a76e7; 1 -> 1.0, 2 -> 0.75). **RE-CHECK (GS)**
  against retail (summary item 9).
- **`input.map`.** The owner's WASD map. Keyboard steering is digital; the keyboard throttle ramps per frame, which
  `I76_FRAMERATE_FIXES` holds to 20 Hz. **RE-CHECK (GS):** the gold standard's I76DRV drives by key state, so its
  throttle ramp runs at its own frame rate.
- **AutoHotkey layers** (`i76-remap.ahk`, `i76-ch-fighterstick.ahk`, head-look, cursor overlay, `i76wheel.exe`). They
  send keys; the rumble mixer reads memory. No sim writes.
- **Force feedback** (`tools/ffb`, opt-in, `-Ffb`). One 4-byte write: the FF-present flag 0x52bbd0 = 0. That makes the
  engine's own effects a no-op while the wheel is held. No sim effect.
- **Mac** (not the driver):
  - DxWnd `maxfps0=52` (19.2 fps), with the AiO limiter also present;
  - virtual CD;
  - `fix-arrows-for-mac.sh`;
  - stack patch;
  - `SMACKW32` cutscene-music proxy.
  - The Mac step stream is unmeasured (section 0). "Verified in play" there means against the owner's feel.

## 7. Fixes with no simulation effect (listed so nothing is missing)

- **Music:**
  - the CD emulation: tracks N..14 as a run, end exclusive, slider re-applied per track;
  - opt-in disc order / shell 1997 / gapless / true pause / missions 1997 (`I76_MUSIC_RETAIL`);
  - the smack cutscene-music proxy (Mac).
- **Saves and menus:**
  - the `savegame.dir` frame (the tools read 4 + 60 x n);
  - u32x ghosting (save freeze);
  - shell text entry, F7, K3, the vehicle-rejected panel;
  - the Esc-menu Exit;
  - cursor overlay.
- **Startup:** the cwd fix, `I76_CD_FAKE` (opt-in), `I76_MULTI_INSTANCE`, `I76_NO_MINIMIZE`.
- **Render:** widescreen HUD squeeze, cam-ground fix, ZGLIDE TMU fix, Glide gamma (Deck), software-renderer
  resolution (`I76_SW_RES`).

## 8. Re-check list against the gold standard, ranked

Every item names what to run. None of them was run here.

1. **Step length.** Run the fingerprint `compare` on driver-switch captures at fixed 41.67 ms, at 30 ms (the envelope
   candidate), and with `I76_STEP_SEQ` (the retail melee / T05 sequences). Cover T05 pitch / turn-over, the T06 strip,
   and melee yaw at 18 and 25 m/s.
   - **Same car first.** Use the gold-standard runs' save, or Instant Melee, which has a fixed car.
   - Then decide `I76_FIXED_STEP`.
   - Bring the P133 run in, because its projected step brackets ours.
2. **Reference rate of the per-frame fixes.**
   - Grid: 20 Hz vs the gold standard's per-frame rate (`I76_REF_FPS=30` / `I76_AI_GRID_HZ=30` against the retail
     traces).
   - Read from the retail runs: AI fire decisions / s, flamer and hazard ticks / s, and the keyboard throttle ramp.
   - Needs the retail AI summary (lists 0x4edc30 / 0x505460 are live in I76MEM).
3. **AI parity set in the driver.** It is measured against stock20, so retarget it to the gold standard before
   promoting. At the least, `I76_AI_ROLL_HOLD` should go back to 1: shipping 0 makes 6x stock rolls at 120 fps.
4. **`ai_RecordDamageEvent` field (AiO +0x10 vs Gold +0x44).** Find retail's counterpart (same call shape, `+0xa6e4`
   / `+0xa6e8` writes) and see which field it tests. If retail = Gold, decide whether to revert the AiO byte in our
   exe.
5. **Widescreen and the far-vehicle radius.**
   - Static: does `camera_Create`'s radius at 0x472499 read the fov our 17 patched sites pass in?
   - Live (any lab copy): read [0x4c2748] with and without `I76_ASPECT`.
6. **Damage rates both ways.**
   - Difficulty factor in retail (and the gold-standard runs' setting);
   - `I76_FIX_HEALTH_PCT` on vs off;
   - `I76_COLL_DEDUPE` ram damage per impact against a retail ram (the fingerprint has destruction rates; damage per
     hit is not in it).
7. **`I76_ENGINE_DT_FIX`** on vs off at a fixed step, 0-20 / 0-30 m/s against the fingerprint (n >= 3 each, A/A first).
8. **`entity_Register` AiO cluster (272 B):** read the diff. Same for the CPU-speed probe consumer, if any.
9. **Collision G and `I76_BREAKABLE_BOX`:** barricades knocked per run against the gold standard's T05 (ERA-ENVELOPE
   used era configs on our exe, not retail).

## 9. Doc corrections found (not applied here; other lanes own these files)

| doc | says | is (evidence) |
|---|---|---|
| ENHANCEMENTS.md section 4, "Collision repeat dedupe" / "AI skid and horn roll hold" | "`best-120` sets it to `0`: count only" (dedupe) | best-120 / best-wide / balanced set `I76_COLL_DEDUPE=1` since promotion 16 (presets, PROMOTIONS row 16); `I76_AI_ROLL_HOLD=0` is still right |
| ENHANCEMENTS.md section 4, "Collision sweep window" | "`I76_COLL_WINDOW=1` [built, untested]" | `=2` + stepframe is in the driver since promotion 16; `=1` measured no effect 2026-10-09 |
| music-fix/README.md, rows `I76_COLL_WINDOW=2`, `I76_CAM_GROUND_FIX`, `I76_CURSOR_MAP` | "committed `Strlkup.dll` `c11f7f7d` ... not in the committed DLL" | committed DLL = driver = `509c6df0` (md5 read today) |
| music-fix/README.md opening | "two stock bug fixes" | the proxy now also carries deliberate behaviour changes (`I76_BREAKABLE_BOX`, collision G) that are not bug fixes against any 1997 machine |
| best-*.psd1 comment "no data yet ... count only" above `I76_COLL_DEDUPE='1'` | the comment says count only | the value 1 applies (the comment predates promotion 16) |
| memory note "sandbox carries user mods" | the lab copies carry the modded `valepre4.vcf` | lab `game\ADDON\valepre4.vcf` is `de680a86` = the driver's = stock per GOLD-STANDARD-FINGERPRINT (md5 read today) |

## 10. Not done in this lane

- No live check of any claim above. Every "touches physics / AI" verdict for render switches is static, from the
  switch's patched sites and the <re-archive> readers.
- The 45 AiO clusters were classified by function name (addrmap-gold.md). Only 0x415817 and the difficulty site were
  re-read today.
- Whether retail 1.0 matches AiO or Galaxy at each cluster: not checked.
- P133: no configs restored and no runs (static lane). The lead's brief asks for that elsewhere.
