# In-mission music fix (base game) — a Strlkup.dll IAT hook, plus the opt-in engine switches

## What it does

`Strlkup.dll` is a tiny 5-export helper that **i76.exe imports statically**, so it loads at process init. This
proxy hands all five exports on to the renamed original (`strlkup_orig.dll`, resolved by name at load, so it
works on any GOG install) and, in `DllMain`, rewrites i76.exe's
Import Address Table so the game's CD-audio calls (`mciSendCommandA`, `auxGetNumDevs` / `auxGetDevCapsA` /
`auxSetVolume`) land in our code, which emulates a CD drive: `MCI_OPEN "cdaudio"` succeeds against a virtual
device, the TOC is answered for tracks 1..17, `MCI_PLAY` track N plays GOG's `music\N.mp3` through the
**mpegvideo** MCI device, `MEDIA_PRESENT` is reported so the "Please insert CD 2" prompt never fires, and the
in-game music slider works (`auxSetVolume(0xB337B337) -> 700/1000`). Everything non-cdaudio passes straight
through to the real winmm. **Confirmed in a mission 2026-08-08** (`MCI_PLAY flags=0xC from=104012301 -> track 13`;
the full diagnosis is [docs/MUSIC.md](../docs/MUSIC.md)). Because this DLL is the one hook point every install
already loads, it also carries the **opt-in** engine switches below (frame-rate fixes, fixed physics step, render
interpolation, two stock bug fixes); all are off unless their environment variable is set, and every patched
site's bytes are verified before writing, so an unknown build is left alone.

## Switches

### Playing above 20 fps: the recommended switch set (2026-09-27)

Measured in the sandbox (i76-map `captures/014-framerate`). All of these are off unless their variable is set.

| variable | fixes | evidence |
|---|---|---|
| (music, always on) | 2026-10-01: the proxy now plays the **run** the game asks for (`MCI_PLAY` with FROM|TO, tracks N..15; before, only track N played and the exe's 5 s status poll restarted it: one song looping with gaps, visible in every field log as repeated `PLAY track 7`), and re-applies the music slider on every track change (the exe sets it once at init) | verified in the sandbox 2026-10-01 on i76.exe: `run 2..15` parsed, `setaudio ... 700` before each track, `track 2 ended -> 3` then `PLAY track 3` (track 2 truncated to 400 KB for the test). NOTE: `i76_pristine_fix.exe` (i76fix) imports `WIN32.dll` instead of `WINMM.dll`, so this proxy's music and volume hooks cannot attach there - the log now says so |
| `I76_HIRES_CLOCK=1` | jittery dt: 15.6 ms GetTickCount steps and float32 uptime decay | dt exact (50.00 ms at 20 fps, 16/17 ms at 60 fps) |
| `I76_FIXED_STEP=24` | chassis/cockpit buzz, jump behaviour: physics always steps in 41.7 ms slices, the mean step of stock play at 20 fps | stock 20 fps actually steps 46.9 ms (80%) / 31.2 ms (GetTickCount frame dts split by the stepper); 24 Hz body motion as calm as stock 20 (at rest 0.83-0.86 in 3 of 4 runs vs 0.45-0.84), acceleration unchanged. The first choice, 40 (25 ms), made jumps fall short and the body feel quick in play |
| `I76_INPUT_LATCH=1` | with `I76_FIXED_STEP`: the ignition key (`I`, start_engine) and the headlights key work about one press in five at 120 fps / 24 steps (owner report 2026-10-04). Both are one-frame rising-edge pulses copied into the player entity every rendered frame (0x44f4cf / 0x44f4dc) and consumed only by a physics step (entity_UpdateState 0x465370); a frame without a step lets the next frame's copy erase the press. The latch turns the two copies from MOV into OR (one byte each), so the request waits for the next step. Off by default; changes nothing without the fixed step | static: disassembly of 9a232dcc = AiO 6319abf7 (prediction 24/120 = 1 in 5). **Live 2026-10-04** (lab copy game-test-20261004, consolidated proxy 89a97d25, t01 parked by the trainer, scripted scancode taps held 16/33/50/100/200 ms, n=10 per hold, accepted = entity+0x454 bit 0/3 (I) or 0x40 (H) changed): best-wide 120 fps latch off I 13/50, H 7/50 (an earlier, partly aborted run: I 7/49 and 5/50); latch on I 50/50, H 50/50; stock 20 fps (`I76_FPS_CAP=20`, no fixed step) I 50/50, H 50/50. Hold time made no difference. In presets best-wide / best-120 since 2026-10-04 (repo; driver: promotion 12 draft) |
| `I76_FIX_HEALTH_PCT=1` | stock bug fix, off by default: the vehicle health percent (object_HealthFraction) drops its x100 once engine, suspension or brakes are below 99.99%, so a scratched car reads under 1%. Damage smoke, handgun targeting, script hpLesser, AI fleeing and the target brackets all see it. Fixed value: min(28 + 72 x worst side ratio, 100 x worst core ratio) - the first version (x100 alone) made the target bar rise and go green when a damaged car's engine was scratched (docs/records/HEALTH-BAR-COLOUR.md); `=2` keeps that reading for A/B. Missions may be tuned around it, so try it on the sandbox | 99% engine: no smoke (stock: heaviest smoke); 50%: smoke. min() version measured live 2026-10-02 (`tools/trainer/tests/health_pct_live_test.py`: stock 0.99 / `=2` x100-only 99.0 / `=1` min() 49.6 on a 30% armour car with a 99% engine — the field report's rising green target bar was the x100-only reading). Target-bracket colours under the fix are still open (backlog P1-01) |
| `I76_FIX_LABEL_TABLE=1` | stock bug fix: the per-mission object-label table (start capacity 2048) grows through a broken path (CRT `_msize` on a private heap, new pointer discarded, NULL written through on failure). Only huge custom missions reach it. `I76_LABEL_TEST=1` shrinks the start capacity to 16 to exercise it | T01 with capacity 16: grew to 272, all 88 labels kept, game ran |
| `I76_FRAMERATE_FIXES=1` | sky drift, free-look camera keys, zoom key, keyboard throttle ramp, missile-lock tones, radar lock ping (locked on it pinged every frame: 60/s at 60 fps; coalesced to 20/s as at 20 fps), per-frame vehicle sounds, AI throttle and steering gains, AI fire decisions (the random fire gate is rolled on the 20 Hz grid and held for the window; stock rolled it every frame: about 3x the fire decisions at 60 fps; `I76_AI_FIRE_CACHE=0` disables only this), flamers (stream ageing on the 20 Hz grid, stock-20 shape, damage 20 times a second from the main pass only: stock applied it per rendered frame, and again in the rear-mirror pass), smoke puffs (updated on the 20 Hz grid, drawn smoothly in between), missile-trail fade, HUD ammo-digit roll (20 steps/s, not measured) | clouds 0.0300 /s at 60 fps = 20 fps (stock 0.0899); sky, free-look confirmed in play; smoke puffs age 19.1 steps/s at 60 fps (stock 57.8; stock 20 fps: 20), i76-map capture 014 `smoke_*.json`; flame stream at 60 fps 18.7 segments (stock 0.6, stock 20 fps 19.0: stock 60 fps has, in effect, no flamers) |
| (with `I76_FRAMERATE_FIXES`) per-frame audit 2026-10-03 | docs/records/PER-FRAME-AUDIT-2026-10-03.md. **Stationary hazards** (oil slick, fire patch, wheel hazard, landed canister): the whole step runs on the 20 Hz grid, 6 sites - their contact test applies the ordnance damage per step, so a car in a fire patch took the Fire-Dropper's damage once per frame (6x at 120 fps), besides the effect and sound. **Radar missile turn** (DrRadar, Cherub; 0x4aaca0, 0x4ab400): the per-step turn (limit sin 3 / 15 / 20 deg, gain 0.75) is scaled by dt x 20. **WMISS.WAV** on a dead weapon with fire held (0x4a5a0e): 20 Hz grid. **AI skid-turn roll** (0x41f5d4) and **AI horn roll** (0x41dacc): rolled on the 20 Hz grid (`I76_AI_ROLL_HOLD=0` counts and rolls every frame) | measured 2026-10-03, sandbox: **hazards** (oil slick) 20 contacts/s at 20, 60 and 120 fps, 9 of 10 runs (one staging miss); **WMISS** 20/s at 20, 60 and 120 fps, 2 runs each. **Radar turn**: not measured. **AI skid / horn rolls**: the acceptance test ran but no AI car entered the behaviour, so no data; `presets\best-120.psd1` sets `I76_AI_ROLL_HOLD=0` (count only). Counters `g_idbg.hazard_impacts / hazard_steps / radar_turns / wmiss_req / wmiss_play / skid_rolls / horn_rolls` |
| (with `I76_FIXED_STEP`) collision repeats | proxy-induced: the collision pass runs every frame but with the fixed step most frames at 60 / 120 fps run no physics step, so the same contact is found again on each of them and its sound, its damage and its AI damage event repeat (up to 3 per impact at 60 fps, 5 at 120). A contact is applied once per step: 6 sites in the pair test and the two class collision handlers. `I76_COLL_DEDUPE=0` counts and passes through. Doc C1 | built; the acceptance test ran on 2026-10-03 but produced no data (the rams could not be staged), so `presets\best-120.psd1` sets `I76_COLL_DEDUPE=0` (count only). Acceptance: `g_idbg.coll_events` / `coll_dups` and telemetry IMPACT events per ram at 20 vs 120 fps |
| `I76_ENGINE_DT_FIX=1` | engine RPM/torque smoothing counted per substep | static; consistent with the fixed step |
| `I76_RENDER_INTERP=1` | the 40 Hz judder the fixed step leaves at 60 fps: vehicles and the cockpit/chase camera are drawn between their last two physics poses | every frame: 31-33% of frames without motion -> 0%, roughness 1.00 -> 0.04-0.06 (n = 2 missions) |
| `I76_COLL_WINDOW=1` (needs `I76_FIXED_STEP`) | collision sweep window vs the fixed step: `physics_CollideObjects` sweeps [0, frame dt] but the car consumes the contact on a whole 41.7 ms step, so at 60 fps the sweep covers 40% of the step (20% at 120). The three `simclock_GetSimDt` reads in the collision tree (0x4349da, 0x434c70, 0x43f9e1) return max(sim_dt, fixed step). Stock (no fixed step) unchanged. docs/records/FRAMERATE-COVERAGE-2026-10-02.md P1 | built, untested. Acceptance: `cactus-ab.ps1` hit rate at 15 m/s, 60 and 120 fps, `I76_FIXED_STEP=24`, before and after, n >= 10 per rate, against the measured 67-70% |
| `I76_AI_FIXES=1` (dodge hold needs `I76_FRAMERATE_FIXES`) | P2: the AI projectile-dodge check (`ai_CheckIncomingProjectiles` from 0x41b698) is rolled per candidate per frame, 3x as often at 60 fps; held to the 20 Hz grid (`I76_AI_DODGE_HOLD=0` counts and passes through). P3: the AI avoidance prediction looks one frame ahead (50 ms at 20 fps, 16.7 at 60); its dt/rate reads (0x43a562, 0x41b58f, 0x41b5ab, 0x41a54e, 0x41a047) are pinned to 20 fps values. Separate from `I76_FRAMERATE_FIXES` for A/B. Doc P2 / P3 | built, untested. Acceptance: dodge calls/s (`g_idbg.dodge_calls`) in a melee under fire, stock 60 about 3x stock 20, held = stock 20; AI collision events/min on a follow route at 20/60/120, n = 2, before and after (drop P3 if 60 already matches 20) |
| `I76_AI_BACKAWAY_GRID=1` (standalone; off by default) | the AI back_away interrupt test 0x41d240 fires when 4 ring samples of the AI's grip-limited throttle are all < 0.1, the ring (ai+0x9d58..+0x9d64) indexed by the AI-pass stamp `[0x524550] & 3` (`call 0x415600` at 0x41d286), one tick per rendered frame: 200 ms at stock 20 fps, 33 ms at 120, so a car still settling at spawn reverses (T12's speedy: best-wide 0/5 opening cuts vs vanilla 7/7 at 6.6 s; lab `docs/2026-10-04-milk-truck-opening-divergence.md` s7-9). The call (original bytes `E8 75 83 FF FF` verified first) goes to a naked stub returning round(sim time `[0x5a7e70]` x 20), a 20 Hz grid count; stock at 20 fps and below. Logs `ai-backaway-grid: back_away ring on the 20 Hz grid (0x41d286 ...; read back ok)`. The other 7 stamp readers (isShot / isRammed / isAttacked edges, rammed terminator) are frame-count consistent with their writer and polled every pass: left alone (audit in the source comment) | 2026-10-04: the same stub applied in-process by the T12 probe (`-GridFix`): best-wide 5/5 cut at 6.6-6.7 s, 0 reverse episodes (vs 0/5, 8-10 episodes). The proxy build (a049878b) is **built, not yet run**: the lab session was stopped for the owner's network-play test before any run. Not in any preset |
| `I76_FAR_ENGINE_DT=1` (needs `I76_ENGINE_DT_FIX`) | proxy-induced: far vehicles (`physics_StepVehicleFar`, one whole-frame step) call the engine update once per frame, where `I76_ENGINE_DT_FIX` hands it 0.05 (fixed step: 3x the stock convergence at 60 fps) or 2 x dt. The far step call 0x46384e is wrapped and the engine gets the stock whole-frame dt inside it. Doc P4 | built, untested. Acceptance: a far AI car's speed trace (vehicle table 0x54E11C, `memlib.ps1`) on a straight follow at 60 fps with the fix set, before and after, vs stock 20: time to cruise speed should match stock 20 |
| `I76_MIRROR_RATE=1` (needs `I76_FRAMERATE_FIXES`) | rear mirror redraws every 2nd frame (30/s at 60 fps, 60/s at 120, a full scene at level 2): the refresh gate 0x4457b4 reads the 20 Hz grid count, giving 10 redraws/s as stock; the mirror's own cloud call 0x4459a1 steps the stock 1.0 so the sky stays at 0.0300 /s. Two gate layouts are accepted: the Galaxy `call` and GOG's AiO build (60abf7bc, the sandbox exe's base), which had removed the gate (`jmp` over it: mirror redrawn every frame, the one Galaxy/AiO difference in that function) - the call restores it in both. Separate from `I76_FRAMERATE_FIXES` for A/B. Doc P5 | built, untested. Acceptance: `sky-motion.ps1` cloud px/s at 60 fps, cockpit, mirror level 2, before and after = stock 20 within the capture-014 spread; `g_idbg.mirror_draws` at 10/s |
| `I76_FAR_CLIP=<m>` | draw distance: the far clip the missions set (600 m) is replaced by this value at the one read site, and the renderer's two fixed pools are enlarged 16x in the same step (the stock 512 KB record arena overflowed and crashed at 5000 m). Same patch as `patch-farclip.ps1` applied to the file, now in memory and opt-in. Capped at 2500 m: the terrain tessellator keeps vertex indices in 16 bits and the hood view / binoculars overflow them between 2500 and 2750 m (crash in renderer_SplitTerrainEdge; docs/records/FARCLIP-CAMERA-CRASH.md). Nothing draws past ~3796 m anyway (depth buckets) | file patch sandbox-verified at 1800 / 5000 m, 60 fps (docs/DRAW-DISTANCE.md); in-memory form live 2026-10-01: camera far 1800 while the mission's 0x4c271c stays 600; a 10-minute session without a crash |
| `I76_VOLUME_TEST=<level>,<frame>` | test knob: at that proxy frame call the game's `sound_SetCdVolume(level)` on its own thread, the function the Options music slider reaches through `sound_ApplyMusicLevel` (in-game menu `shell_AudioMusicLevel` 0x496600 and the shell's audio callbacks) | 2026-10-01: level 3 at frame 900 -> `auxSetVolume(0x4CD7...) -> 300/1000`, `setaudio i76cd volume to 300` ok, so the slider controls the mp3 volume. Mapping is level/10 of full scale; a remote-thread call fails with MCI error 261 (aliases are per task), which is why the knob exists |
| `I76_FPS_CAP=n` | optional precise frame cap. (The reason given here, "dgVoodoo's FPSLimit did not cap this build", is **void**: on 2026-10-02 dgVoodoo 2.87.3 was found to have been rejecting the sandbox's `dgVoodoo.conf` and running a 2020 global `%APPDATA%` file, so `FPSLimit` was never in effect when that was measured. Not re-measured.) | held 20.0 fps exactly; 2026-10-03: a cap above ~64 fps delivered ~62 until the proxy requested 1 ms timer resolution (commit `2457a7c`) |
| `I76_MULTI_INSTANCE=1` | a second copy of the game exits at once: WinMain 0x402ca0 looks for the game's window class with `FindWindowA`, and a hit restores that window and returns 0. The switch turns the `je` at 0x402caf into `jmp`, so the check is skipped and two copies can run on one PC (each in its own folder) | 2026-10-03, lab: two copies ran side by side, both responding (without the switch the second process exits with code 0). A multiplayer session between them was **not** achieved: both copies need UDP port 21157, and the internet transport wants a game server |
| `I76_TERRAIN_LOD=<1..16>` | EXPERIMENT. The terrain is a quadtree rebuilt every frame; patches split by distance and height error with no blending, so the ground snaps into shape as you approach. The switch scales the two constants in `renderer_SetTerrainResolution` 0x493080 so splits happen farther out. | 2026-10-03, sandbox: 6/6 constants patched, 120 fps at x2 / x4 / x8 on t01. Whether the pop-in looks better is not judged; more vertices per frame brings the 32,767 terrain-vertex ceiling closer, so it needs a soak with the far clip. In no preset. |
| `I76_TERRAIN_TEX=<1..16>`, `I76_OBJECT_LOD=<1..16>` | EXPERIMENT. No mipmaps under Glide: the terrain picks one of five texture sizes by distance (256 px tile ends at 50 m), and objects swap to a coarse mesh by on-screen size. The first switch scales the terrain texture distance (code at 0x492458); the second scales the object rule's 1.0 at 0x4bdf94 (main view and mirror). Analysis: lab `docs/TEXTURE-AND-OBJECT-LOD.md`. | 2026-10-03, lab twin: both patched, 120.1 fps on t01 with terrain x8 (one 6 s run); the capture shows sharper far ground and distant objects in full detail. Cost on busy scenes, texture memory and shimmer not measured. In presets `exp-detail-8` / `exp-detail-16` only. |
| `I76_SHADOW_DIST=<1..16>`, `I76_ROAD_TEX=<1..16>`, `I76_ROAD_DIST=<450..3000 m>` | EXPERIMENT. Shadows are drawn only within 50 m (float at 0x4bdfa0), the sharper road texture set only within 60 m (0x4be7bc), and road segments only within 450 m whatever the far clip (0x4be7b8). Each float is read at the named sites only (exe scanned for the address). | 2026-10-03: built, not yet run. In presets `exp-detail-8` / `exp-detail-16` (shadows x4 = 200 m, road textures x8 = 480 m, roads to 1800 m). |
| `I76_ROAD_POOL=0` / `=<1..64>` (automatic with `I76_ROAD_DIST` > 450 or `I76_FAR_CLIP`) | Fix for ceiling #4 (crash exe+0x9051B with roads past ~600 m). The depth queue links every kind-1/0xb polygon into each 1 m depth bucket it spans (0x490470), one 16-byte node per bucket from a bump pool of 0x1f400 B (~8,000 nodes, `push` at 0x48f9d6, rewound per flush at 0x48fd50) with no end check; long road polygons out to 1800 m ran it off its block. The switch enlarges that pool (default x16 = 2000 KB; the value is the factor, 1 = stock size) and puts a guard at the node loop head 0x4904cd: when the next node would pass the pool end, or the bucket index would pass the 4096-entry table, the function leaves through its own exit, so that polygon keeps the buckets it already has and the rest are dropped instead of written past the end. The readers only walk the lists, nothing else assumes the size. With `I76MUSIC_LOG` it logs refusals, dropped links and the node high water every 600 frames (frames counted at the scene flush calls 0x401e8d / 0x40216d). `I76_ROAD_POOL=0` turns it off. | 2026-10-03, lab sandbox, best-wide + widescreen conf, proxy f9b0c481. Before: roads 1800 crashed t11 at boot 2/2. After: t11 boots 4/4 with every phase, and t01/t05/t13/t15/t16 survived, all with 0 refusals. Node high water 78-399 KB (the stock pool is 125 KB, so roads 1800 needs up to 3.2x). Guard proof: `I76_ROAD_POOL=1` (stock size) with roads 1800 survived t11 while refusing ~100k-800k polygons per 600 frames. Cost: only t11's cockpit, 120 to 105-115 fps (p99 13 ms; 11.8 ms at 1200 m). Lab `docs/SOAK-BEST-WIDE-2026-10-03.md` (Fix section). |
| `I76_CLUTTER_DIST=<120..600 m>` (+ `I76_CLUTTER_RISE=<0..100 m>`) | EXPERIMENT. The little bushes (Terrain Detail ground clutter, renderer_QueueTerrainClutter 0x45c380) exist only within view z 120 m (f32 0x4be0d0) and only in the 3x3 block of 100 m cells around the camera (offsets table 0x4f7190), and only where the ground is at most 5 m above the camera's ground (f64 0x4be0c8). The switch sets the view z limit to the value, runs the cell loop over a proxy table rebuilt each frame from a block up to 49x49 cells keeping only the cells the camera can see (loop start 0x45c4fa/0x45c507, loop end 0x45c825), scales the 5 m rise limit to 5 x D / 120 (same angle; `I76_CLUTTER_RISE` overrides, 5 = stock), enlarges the unbounded draw-record pool x8 (0x48f9b5) and refuses further instances once clutter would eat into the stock pool's worth of headroom (frustum call 0x45c634). With `I76MUSIC_LOG` it logs time, cells, instances and pool high water every 600 frames. Analysis: lab `docs/CLUTTER-AND-MIRROR.md`. | 2026-10-03, sandbox t01 with the detail set at 120 Hz: 300 m: 8/8 sites, 120.2 fps, ~200 us per frame, ~28 cells, 0 refusals, pool high water 188 KB; 600 m: 120.0 fps but p99 9.2 ms (frames start to miss 8.33 ms), ~650 us per frame, ~72 cells, 0 refusals, 229 KB. I76_MIRROR_FAR=300 applied, look not judged. In exp-detail-8 (300) / exp-detail-16 (400). |
| `I76_MIRROR_FAR=<100..600 m>` | EXPERIMENT. The rear mirror camera is created with a 100 m far clip (`push 100.0` at 0x44553c in mirror_Init 0x445380); this raises it. It does not change the mirror's resolution: the mirror is a software render into the 256x64 8-bit cockpit mirror texture (ZMIRI101.MAP) re-uploaded every redraw, so it stays 256x64 whatever dgVoodoo renders at (lab `docs/CLUTTER-AND-MIRROR.md`). | 2026-10-03: built, not yet run. In no preset. |
| `I76_ASPECT=<D>` (`2.389`, `21:9`, `3440x1440`) | EXPERIMENT, widescreen stage A (Hor+). The frame stays 640x480; the camera's aspect constant (3.0 at 0x4bc510) becomes 4/D and every field of view f becomes 2 atan(0.75 D tan(f/2)): 17 `push pi/2` sites (90 -> 121.7 deg at 21:9), the hood's 120 deg at 0x4075a7 (-> 144.3 deg), and the fov clamp at 0x4be5ac. dgVoodoo must present at the display aspect: `[Glide] Resolution` of that shape and `ScalingMode = stretched`. 2D sprites and text are stretched by 0.75 D. Analysis: lab `docs/WIDESCREEN-FEASIBILITY.md`. | 2026-10-03, lab twin, t01 cockpit view (`I76_ASPECT_COCKPIT_FOV=<deg>` gives the cockpit its own width; default full): 20/20 sites patched, 120.1 fps, the picture fills the 3440x1440 panel at the correct shape; the cockpit mesh, gauges and mirror cover the wider view in the start-line capture. One run; other views, menus, 2D text and a full mission not checked. Lab twin `EXPERIMENT.bat` shape 5. |
| `I76_HUD_SQUEEZE=0` (with `I76_ASPECT`; on by default when `I76_ASPECT` applies) | turns OFF the HUD sprite squeeze. With `I76_ASPECT` the frame is presented stretched by k = 0.75 D, so the HUD sprites drawn by renderer_DrawHudSprite 0x45b450 come out k times too wide. Its one Glide polygon call `call 0x4260d0` at 0x45b87a is repointed at a wrapper that narrows the quad's x by 1/k (texture coordinates unchanged, so the sprite is resampled at full resolution, not blurred). Anchor per caller: the quad's own centre for the target-bracket corners (0x45b184/1a0/1bc/1d8), the off-screen target marker (0x45b087), the target bar sprite (0x45b3cf, software renderer only: under Glide the bar is a rect fill 0x45b8c0 that spans the bracket box and stays as is), the weapon reticles zretc_1 (0x45c19b/0x45c20c/0x45c2c4) and the bottom-centred zcbh3101 sprite (0x45c314); for the 2D-dash gauge loop (0x45c0d1, wrapped to set the mode) the screen side: quads centred in the left third scale about the view's left edge, the right third about its right edge, the middle about the view centre, so a gauge cluster keeps its layout and stays against its edge. Nothing on this path spans the screen. Not on this path, still stretched: LFB text (messages, counters), the Esc menu, the binocular mask, the target bar (Glide rect), and the shell/cutscenes (DirectDraw). The 3D cockpit (F1 default) is a mesh and was already right. Analysis: lab `docs/WIDESCREEN-2D.md` (c). | 2026-10-03, lab sandbox `game\`, t01, `dgVoodoo.aspect-wide.conf`, 3440x1440 at 120 Hz, one run each way: log `hud-squeeze: 2/2 sites, quad call -> wrapper`; 2D dash (F1 again in the cockpit) speedo, tach, radar, PRND21 and the reticle round; bracket corners square around the targeted car (E); `I76_HUD_SQUEEZE=0` reproduces the x1.79 stretch. Captures lab `captures\graphics\look\hudsq2-{on,off}-*.png` (crops `-crop-bracket/-gauges/-reticle`). Owner's route (bookmark -> garage -> mission) not run. |
| `I76_GLIDE_REFRESH=<hz>` | the 60 fps ceiling: ZGLIDE.DLL opens its window with `grSstWinOpen(..., GR_REFRESH_60Hz, ...)` and dgVoodoo paces windowed presents at the refresh the app asked for, whatever the panel (179 Hz), `FPSLimit` or a forced `Resolution = WxH, 120` say (all measured 60.0; **void for the two conf keys**: dgVoodoo was rejecting the sandbox conf when they were tried, so neither was in effect. The refresh-code pacing itself is confirmed on the fixed conf, and nGlide paces the same way: docs/records/RENDERER-ALTERNATIVES.md section 11). The proxy hooks the exe's `LoadLibraryA`, and when ZGLIDE.DLL loads repoints its `glide2x.dll!_grSstWinOpen@28` import slot at a wrapper that substitutes the code for this rate (60 70 72 75 80 85 90 100 120; 0 = none). docs/records/FPS-120.md | 2026-10-02 sandbox: 120 -> 120.0 fps measured on the proxy frame counter; played by the owner at 120 the same evening; 2026-10-03: 120.1 fps on the accepted conf, and 120 is the ceiling of every renderer tested (code 9 and above are rejected) |
| `I76_TEX_CENSUS=1` / `=2` | DIAGNOSTIC, count only (off when unset; no behaviour change). Hooks ZGLIDE's glide2x imports through LoadLibraryA: texture downloads and bytes, full TMU cache flushes (`grTexMinAddress` after FirstDevice; each follows a "no slot, drawn with the wrong texture" event), resident bytes from ZGLIDE's allocator, and a `grTexMaxAddress` readback that proves which `[Glide] MemorySizeOfTMU` dgVoodoo took (2048 -> 0x1ffff0, 4096 -> 0x3ffff0). Logs every FLUSH with its swap / frame number and a summary every 600 swaps to mciproxy.log. `=2` also writes `texcensus-<swap>-{flush-front,flush-back,ctl-back}.bmp` (640x480, grLfbReadRegion) into the game folder for up to 16 flushes | 2026-10-03 lab twin (lab docs/TERRAIN-WHITE-FLASH.md): best-wide 23 mid-mission flushes on t01/t05/t11 (~95 s each), detail switches off 7, best-wide + `MemorySizeOfTMU = 4096` 0; none of the dumped flush frames showed white terrain |
| `I76_FRAME_SPIKES=<ms>` (`1` = 250) | DIAGNOSTIC, no behaviour change (off when unset). Turns on the `I76_TEX_CENSUS=1` hooks and times every swap: frame (swap to swap) and present (inside glide2x `grBufferSwap`, i.e. dgVoodoo's present and pacing). Any frame or present at or above the threshold is logged as `frame-spikes: SPIKE` with that frame's texture downloads / KB / flushes / no-slot flag / resident KB and the scene counters sampled at the scene flush: terrain vertices `[0x6442ec]` (int16 index ceiling 32,767, docs/records/FARCLIP-CAMERA-CRASH.md), draw-record arena use `[0x654380]-[0x5dd324]` and its count `[0x59c568]`, span nodes. A frame past 32,767 terrain vertices is logged as `TERRAIN-WRAP` (rising edge). Summary every 600 swaps (max frame / present, frames >= 100 ms, max downloads in one frame, vertex and arena high water). Wraps the two scene flush calls itself when the road pool is off. Lab docs/RENDER-FREEZE-2026-10-04.md. NB the soak's telemetry frame times count sim frames, which keep running through an unpresented stretch: only this swap timer sees the freeze | 2026-10-04 lab twin, 2 missions x n = 2 per condition: best-wide 5 / 12 spikes >= 100 ms per batch, longest 2.6-3.1 s, **every spike = consecutive ZGLIDE cache flushes** (~80 ms of unpresented frames per flush); MemorySizeOfTMU 4096 / 8192 + `I76_ZGLIDE_TMUFIX`: 0. Terrain vertices <= 17.9k (no wrap), arena <= 0.7 MB |
| `I76_ZGLIDE_TMUFIX=1` | ZGLIDE+0x1a93 `75 24` -> `eb 24` when ZGLIDE loads (LoadLibraryA hook; stock bytes checked first): skips the Voodoo 1 "no texture across 2 MB" rule. Its rewind target is the constant 2 MB and it runs before the `grTexMaxAddress` check, so with `[Glide] MemorySizeOfTMU` above 2048 the allocation that would pass the top of TMU memory moves next-free back to 2 MB while 2..4 MB are still resident: wrong textures (the owner's "texture exchange" with 4096, promotion 5R). **Needed for any MemorySizeOfTMU above 2048.** The census (`I76_TEX_CENSUS` / `I76_FRAME_SPIKES`) logs `BOUNDARY RULE fired` / `REWOUND ONTO RESIDENT TEXTURES` | 2026-10-04 lab twin: 4096 without it rewound in 2/2 missions (t01, t05) within ~36 s each; 8192 with it: patch logged, 0 rewinds, 0 flushes, 0 spikes, grTexMaxAddress 0x7ffff0, peak resident 4.7 MB (more than 4096 holds), 120 fps. Not promoted |
| (music run end, always on; `I76_MUSIC_TO_INCLUSIVE=1` = the old reading) | BUG FIX. The exe's `MCI_PLAY` is always `MCI_FROM|MCI_TO` in TMSF, and `dwTo` is a TOC track **start** (AiO: the start of 15). Played to that position a CD stops before it, so "12 to 15" is the run 12..14. The proxy read `to` as inclusive until 2026-10-04 and appended 15.mp3 to every mission run (16.mp3 after M09's 15). Lab docs/MUSIC-RUN-END-2026-10-04.md. The startup line `music: run end exclusive, disc order ..., shell ..., resume ...` names all four music options | see docs/MUSIC-TRACK-MAP.md, "2026-10-04 lab test" |
| `I76_MUSIC_DISC_ORDER=1` | OPT-IN, off by default. GOG's `music\N.mp3` follow the disc except four files (frame-walk lengths vs the redump TOC): disc 3 = 16.mp3, 15 = 17.mp3, 16 = 15.mp3, 17 = 3.mp3. Translates disc track -> file in the play and in the TOC lengths the exe reads. Logs `disc track N -> file M.mp3 (disc order)` | same |
| `I76_MUSIC_SHELL=1997` | OPT-IN, off by default. In the shell (game state `[0x4c2164] == 6`) the Gold DLL's menu track 13 and credits track 8 become the 1997 DLL's choices, one track each: 13 -> disc 15 (Ovum Bisquit, 17.mp3), 8 -> disc 16 (Malochio Down, 15.mp3); the remap always uses the disc-order file. The exe's 5 s shell poll replays the request when the track ends, so each loops. With `I76_MUSIC_RESUME` a resume only matches a paused run of the same kind (a remapped shell run never resumes a mission's track 15). Logs `shell 1997: state 6, run 13..14 -> disc 15 alone (file 17.mp3)` | same |
| `I76_MUSIC_RESUME` (default on; `=0` = stop and restart) / `I76_MUSIC_GUARD` (default on; `=0` off) | from the Mac side (2ea53f5): a STOP/PAUSE/CLOSE pauses the mp3 and a PLAY of the same run resumes it; a 500 ms thread puts back the music IAT slots when another layer (DxWnd) takes them, startup line `music-guard: on` | Mac, 2026-10-04 |
| (crash log, always on; `I76_CRASH_LOG=0` disables) | vectored handler: `CRASH:` line (code, address, registers, game state, camera), the first 16 stack dwords and, since 2026-10-04, `CRASH: modules` naming the module + offset of the fault address and of the first stack values that point into a DLL (VirtualQuery + GetModuleFileName). It sees **first-chance** exceptions, so a fault some DLL catches itself is logged too | the driver's `0x6E988AD3` (2026-10) = `AcGenral.DLL+0x98AD3` (offset match, not read from a live module list), the September WER signature (tools/bisect/README.md), in the exe's exit-time HeapDestroy; module line live 2026-10-04 (`i76.exe+0x919B1` named correctly) |
| (trainer, always on; `I76_TRAINER=0` disables) | `Local\I76Trainer` control block (tools/trainer/i76trn.h): a front end (tools/trainer/i76trainer_gui.py, `TRAINER.bat`) sets flags the proxy holds every frame on the game thread before the tick (god, unlimited ammo, no flats, components, freeze position) and one-shots (repair, teleport, ammo, slot ammo, play flags, stop). Forced Play Options bits are restored on release; the "cheats used" marker is not touched | 2026-10-02 sandbox: tools/trainer/tests/trainer_live_test.py 13/13 (a 40 m drop costs 156 hp with god off, 0 with god on; play flags 0x1c held, restored to 0x00) |
| (CD-prompt instrument, **opt-in `I76_CD_LOG=1`** since 2026-10-02: always-on broke the trip route, its `shell_cb_17` wrapper returned -1 on bookmark -> DONE and the mission never started; was: always on, `I76_CD_LOG=0` disables) | the `Please insert CD "Interstate '76 CD 2"` modal (backlog P1-09 / MENU-USABILITY-PLAN P8, E6; 6 of ~21 lab launches on `i76_pristine_fix.exe`). Four hooks, each verifying the stock bytes first, zero cost until the prompt path runs: an IAT hook on `MessageBoxA` (slot 0x4bc35c; `USER32.dll` on stock builds, `u32x.dll` on the AiO/lab build, both tried) logs caption, text, the CD globals (`cd2_drive` 0x58d92c, `cdrom_drives` 0x609520, `cur_cd_index` 0x4fff18, `cd_path_flag` 0x669ee4, the MCI open error/device/active flag), game state 0x4c2164, proxy frame, cwd, a live `GetVolumeInformationA` of every CD-ROM drive, the zix volume and container tables, and a return-address chain (0x470de9 = `cd_PromptLoop` VFS owner, 0x471153 = `shell_cb_17` movie owner with its arg 0 read from its frame); a call-site hook at 0x4b2faa (`FF 15 D0 62 65 00` -> `E8 rel32 90`) adds the file name the VFS was resolving, its file-table entry and container bitset; an entry hook on `startup_IsMinimum` 0x4b2220 (`81 EC 5C 01 00 00` -> `E9 rel32 90`; skipped with a note on the AiO exe, where it is already `xor eax,eax; ret`) logs each answer with the exe's own registry sequence (`RegOpenKeyExA` / `RegCreateKeyExA(KEY_ALL_ACCESS)` results, the value), the token's elevation and virtualization, the cwd and `FindFirstFile("miss8")`; an entry hook on `shell_cb_17` 0x470f90 (`81 EC A4 00 00 00` -> `E9 rel32 90`) logs each call's arg 0 and MCI state. Prompt lines and a `Minimum` answer of 1 are written even without `I76MUSIC_LOG`. **The rule (static + measured 2026-10-02):** the VFS owner fires exactly when `startup_IsMinimum` returns 1 (the lab zix is `0 \ I76_CD2` + `DIR: i76.zfs`, the ISO is I76_CD1, so the current-CD index stays -1 on every run) and `WinMain` calls `shell_cb_17(1)` at startup only in that case; `startup_IsMinimum` returns 1 whenever `RegOpenKeyExA(HKLM\SOFTWARE\Activision, KEY_READ)` or `RegCreateKeyExA(..\Interstate '76 Gold Edition, KEY_ALL_ACCESS)` fails, else "0" -> 0, "1" -> 1, else `FindFirstFileA("miss8")` in the cwd. On this machine the key exists in the real HKLM (owner Administrators, Users = ReadKey, `Minimum` = "0"), so every **non-elevated** launch is denied the create (err 5, measured with the same three calls from an x86 test program; virtualization does not redirect an existing key) and answers 1 before reading anything - the 6/21 split is launcher elevation, not cwd | live 2026-10-02 (integrator, `autotest\cd2-test.ps1`, `i76_pristine_fix.exe`, cwd C:\Windows): `startup_IsMinimum #1 -> 1`, `shell_cb_17 #1 (arg0 1) from 0x00402CE7`, `MSGBOX` from 0x00471636, chain 00471636 0047114A 00471153 00402CE7 004736C7 004BA236 - the WinMain owner, as read |
| `I76_CD_FAKE=1` | the mitigation for the pristine exes (the AiO exe carries the equivalent as a byte patch): when the stock `startup_IsMinimum` answers 1 (Minimum) but `<game dir>\miss8` exists as a directory, the proxy answers 0. Exact effect: `vfs_LoadZix` marks the miss8/miss16 container as a local directory (type 1) instead of CD volume 0, `vfs_ResolveFilePath` builds `miss16\<file>` as on every healthy launch, and `WinMain` skips its `shell_cb_17(1)` call - the stock behaviour of a full install whose registry write succeeded. The stock function still runs (its registry write, only on the value-absent path, is unchanged). This is the correct permanent form: the stock test needs a HKLM write a non-elevated process cannot make, and the directory the function itself falls back to is the ground truth. Needs the cwd fix beside it (`I76_CWD_FIX`, main): the loose `miss16\` opens are cwd-relative, so without it the prompt turns into "Sorry, unable to find required files". No effect on the AiO exe (already 0) or on a genuinely minimal install (no miss8 directory: answer unchanged). Candidate for default-on | live 2026-10-02 (integrator, same test, with the cwd fix): three calls faked 1 -> 0, no MSGBOX, the game proceeds past the prompt |
| (cwd fix, always on; `I76_CWD_FIX=0` disables) | the exe resolves its loose data (`miss16\`, `addon\`) relative to the current directory, so with the prompt out of the way (`I76_CD_FAKE`) the next cwd-relative open fails outright ("Sorry, unable to find required files"). (`startup_IsMinimum` also looks for `miss8` there, but only on the value-absent path it never reaches non-elevated: the prompt itself comes from its denied HKLM create, see the row above.) Launchers set the cwd; a bare double-click or `Start-Process` without `-WorkingDirectory` does not. The DLL sets the current directory to the game folder before the exe's entry point runs and logs the old one | 2026-10-02 sandbox: pristine exe from `C:\Windows` prompted (`startup_IsMinimum -> 1`, `MSGBOX "Please insert CD"`), with the fix: see the live note below |

```powershell
$env:I76_HIRES_CLOCK = "1"; $env:I76_FIXED_STEP = "24"; $env:I76_FRAMERATE_FIXES = "1"; $env:I76_ENGINE_DT_FIX = "1"; $env:I76_RENDER_INTERP = "1"
```

In the sandbox, `i76-uncap-lab\TEST-FRAMERATE.bat` runs this set, the same set without interpolation, stock 60 fps and
stock 20 fps, and restores the sandbox afterwards.

AI throttle chatter at 60 fps: 26.2 (stock) vs 1.56 at 20 fps. `I76_HIRES_CLOCK` alone brings it to 9.0, and adding
the fixed step to 5.3 (n = 3 each, still above 20 fps). With the fixed step alone, the physics advances on two
frames out of three at 60 fps (40 Hz), which shows as judder; `I76_RENDER_INTERP` removes it. The set was
**console-verified by the owner on 2026-10-02** in the sandbox (`TEST-FRAMERATE.bat` mode `all`, every switch on:
in-mission music, F6 hood view and B binoculars at `I76_FAR_CLIP=1800`, flamer, music slider, AI behaviour, the
Mission 5 jump without nitrous, the out-of-gas jumps, body roll speed, keyboard save). Nothing here was deployed to
the playable install on that date; the daily driver built on 2026-10-03 runs this DLL with `presets\best-120.psd1`
(docs/records/NEW-DAILY-DRIVER-RECIPE.md).

### Diagnostics

- `I76MUSIC_LOG=1` before launching writes `mciproxy.log` in the game folder — it records the IAT patch, every
  cdaudio MCI call (open / play / track number / status) and each switch's `n/n` site verification line
  (`hires-clock: 2/2`, `engine-dt-fix: 1/1`, `render-interp: 3/3 hooks, on (debug block XXXXXXXX)`). It is the thing
  to read if music misbehaves or a switch appears to do nothing.

## Deploy / revert

`setup-windows.ps1` deploys it automatically for the base game: it backs up the
original as `strlkup_orig.dll` and drops the proxy in as `Strlkup.dll`.

- **Revert:** restore `strlkup_orig.dll` over `Strlkup.dll` (delete the proxy,
  rename the backup back).

## Build

A prebuilt 32-bit `Strlkup.dll` is committed here (it is our own code and contains no Activision bytes — it
loads the GOG `strlkup_orig.dll` by name, so it works on any GOG install). Its size and md5 change with every
rebuild, so they are not quoted as a constant here: as of commit `7c998bf` (2026-10-02) it is 172,032 B, md5
`cf7329ea89660faa0d9299c754463c7b`; `git log -1 -- music-fix/Strlkup.dll` and the CHANGELOG entry of a release
give the current one (corrected 2026-10-02: this said 148,480 B, the 2026-09-27 build). To rebuild after editing
`strlkproxy.c`, run `build.ps1`:

- **Preferred: w64devkit's 32-bit gcc** (`-Gcc`, default `C:\Games\_tools\w64devkit\bin\gcc.exe`), compiling
  `strlkproxy.c` with `strlkup.def`. w64devkit is portable, no installer — but **optional**: it is not installed
  on the lab machine and the committed DLL was not built with it.
- **Fallback: MSVC x86** (what actually built every committed binary). If gcc is absent, or with `-Msvc`,
  `build.ps1` finds `vcvars32.bat` under the Visual Studio Build Tools and runs
  `cl /LD /MT /O2 strlkproxy.c /link user32.lib`. `link.exe` does not emit forwarders to another DLL from either
  the `.def` or `/EXPORT:name=strlkup_orig.name` (it reports the five as unresolved externals), so the source
  does not rely on linker forwarders at all: the four functions are `__declspec(naked)` stubs that `jmp` to the
  address `GetProcAddress(strlkup_orig.dll, …)` resolved in `DllMain`, and the DATA export
  `StrLookup_Global_Object` is handled by repointing i76.exe's IAT slot at the original's variable (see the
  comment block "FORWARDING THE FIVE Strlkup EXPORTS WITHOUT LINKER FORWARDERS" in `strlkproxy.c`). Either
  toolchain therefore produces a working DLL from the same source. (The dead `$fwd` list of `/EXPORT:`
  switches that `build.ps1` used to assemble and never pass to `cl` was removed 2026-10-02.)
- **`build-msvc.ps1` is now `build.ps1 -Msvc`.** It was written because the MSVC branch of `build.ps1` aborted
  under `$ErrorActionPreference = 'Stop'` whenever stderr was captured (an agent's tool call, `2>&1`):
  `vcvars32.bat` prints a benign "'vswhere.exe' is not recognized", and the in-`cmd` redirect covered only the
  last command of the `&&` chain (`cl`), not `vcvars32.bat`. The chain is now parenthesised so the whole of it
  goes to `build.log`, and the one native call runs under `'Continue'`. Checked 2026-10-02: `build-msvc.ps1`
  from a captured-stderr shell builds 172,032 B, x86, exit 0.
- The script is **non-destructive**: it builds to `Strlkup.build.dll`, checks the PE machine field is 0x14c
  (32-bit) and only then replaces `Strlkup.dll`. `-Install` deploys to `-GameDir`, else the running game's
  folder, else `$env:I76_GAME_DIR`, else the lab sandbox (`..\..\i76-uncap-lab\game`). The daily driver's path
  was in that fallback list until 2026-10-02 and has been removed: promoting a build to the playable install is
  a deliberate copy with a `.pre-<date>` kept beside it (AGENTS.md), never a side effect of `-Install`.

## How the music hook works

The loader has already snapped i76.exe's IAT slot for `WINMM.dll!mciSendCommandA` to the real winmm before any
`DllMain` runs, and the game doesn't call it until a mission starts, so overwriting the slot in our `DllMain`
always wins. The hook emulates the `cdaudio` device:

- `MCI_OPEN "cdaudio"` → succeeds against a virtual device id (`FAKE_CD_ID` = `0xC0DE`). The game opens with
  `flags 0x3000` = `MCI_OPEN_TYPE | MCI_OPEN_TYPE_ID`, so the device type is matched as an integer against
  `MCI_DEVTYPE_CD_AUDIO`, not as a string.
- `MCI_STATUS … MCI_TRACK` queries answer a full TOC (track type, cumulative start offsets in `MCI_FORMAT_TMSF`);
  the engine validates the disc before it will play anything.
- `MCI_PLAY` track N → plays `music\N.mp3` via the **mpegvideo** MCI device (which works fine with no CD). Track N
  maps directly to `music\N.mp3` (track 1 was the data track — there is no `1.mp3`).
- `MCI_STATUS … MEDIA_PRESENT` → reports a disc present, so the CD prompt never fires.
- `auxGetNumDevs` / `auxGetDevCapsA` advertise exactly one `AUXCAPS_CDAUDIO` aux device **when the system has
  none** (a machine with real aux hardware is untouched); the engine checks for one before it ever opens MCI.
  `auxSetVolume` is translated to `setaudio <alias> volume to N` on the mpegvideo alias, so the music slider works.
- Everything non-cdaudio is passed straight through to the real winmm.

## Opt-in: high-resolution sim clock (`I76_HIRES_CLOCK=1`, 2026-09-26)

Not music, but this DLL is the one hook point every install already loads. The whole simulation is dt-driven:
`simclock_Update` (0x49c920) reads `GetTickCount` once per frame, and physics runs in substeps of at most 50 ms
derived from that dt (i76-map batch `simclock-stepper`). `GetTickCount` steps in 15–16 ms no matter what
`timeBeginPeriod` says (measured on this machine), so at 20 fps dt reads 47 or 63 ms, and at 60 fps most frames read
0 (clamped to 1 ms) or 15.6 ms. The 2017 Galaxy exe also stores seconds-since-boot as a 32-bit float, so dt snaps to
a 62.5 ms grid after 7 days of uptime. GOG's 2019 AiO build fixes that second problem by masking the tick; nothing
fixes the first.

With `I76_HIRES_CLOCK=1` set, DllMain repoints only simclock's two `call [GetTickCount]` sites at a
QueryPerformanceCounter clock (ms since process start). It supports both layouts: Galaxy 0x49c85f/0x49c929 and
AiO 0x49c85d/0x49c927. Each site's bytes are verified before writing, so any other build is left alone.

**Status:** the write was verified in the sandbox (2/2 sites read back as `call [ptr] -> hires_clock_ms`, log line
`hires-clock: 2/2`); dt measured exact in i76-map capture 014 (50.00 ms at 20 fps, 16/17 ms at 60 fps); played in
the sandbox as part of the recommended set and console-verified by the owner on 2026-10-02 (corrected 2026-10-02:
this line said "has not been played yet"). Not deployed to the playable install.

## Opt-in: frame-rate-independent engine response (`I76_ENGINE_DT_FIX=1`, 2026-09-26)

The engine/gearbox update 0x46a320 (i76-map `physics_UpdateEngine`) runs once per physics substep but smooths RPM and
torque with the **whole frame's** dt. At 20 fps a frame has two substeps, so the engine responds about twice as fast per
second as at 60 fps, and GetTickCount jitter flips it between one and two substeps even at 20 fps. The flag repoints
that one `call simclock_GetDt` (0x46a333, the same bytes in the Galaxy and AiO builds) at a function returning
2 × sim_dt / substep count. That reproduces the two-substep (20 fps) response at any frame rate.

**Status:** the write was verified in the sandbox together with `I76_HIRES_CLOCK` (`engine-dt-fix: 1/1`); played in
the sandbox as part of the recommended set and console-verified by the owner on 2026-10-02 (corrected 2026-10-02:
this line said "has not been played"). Not measured in isolation: the standstill-to-100 km/h timing with and without
it is still worth one run. Not deployed to the playable install.

## Opt-in: render interpolation (`I76_RENDER_INTERP=1`, needs `I76_FIXED_STEP`, 2026-09-27)

Each object's pose is a 0x40-byte transform at object+0x18: a 3x3 float rotation (rows = right, up, forward) and
three position doubles. The physics writes it directly, so there is no separate render copy to interpolate. The proxy
therefore swaps an interpolated pose in around the render call and restores the physics pose right after; the
simulation never sees it.

- **Vehicle tick.** Class table slot 0x4f7788 (type 1, `entity_TickVehicle`) points at a wrapper that keeps each
  vehicle's pose from before its last 25 ms step.
- **Render.** The `call 0x401c90` at 0x403e69 (render(&camera)) is wrapped. Each vehicle ticked this frame, and still
  in the live-object list, is drawn at `lerp(previous, current, leftover / step)`. The rotation is re-orthonormalised.
  Display latency is one physics step (0.25-0.34 m at 17-30 m/s).
- **Camera.** The camera mode runs once per frame from the frame loop (`call [0x4c2720]` at 0x403e16, and on one
  path from inside the player's tick at 0x46391f). Both calls are wrapped so the mode runs with the player at its
  drawn pose, which is what a lagging chase camera needs. The first version moved the finished camera rigidly with
  the player instead; that was exact for the cockpit (1.317 m ± 0.0000 from the drawn car) but left the chase car
  wobbling against the camera, reported in play. Measured on the chase camera: car-vs-camera jerk median
  0.029 -> 0.002 m/frame^2, 95th percentile 0.34 -> 0.005. The rigid carry (via a detour of SetTransform 0x472990)
  remains as a fallback for a frame whose camera was set some other way; script cameras (`fsm_Cam*`) are left alone.
- **Guards.** A vehicle that moved more than 8 m in one step (respawn or teleport) is drawn without blending. So is one
  ticked without the fixed stepper.

The log line `render-interp: 3/3 hooks, on (debug block XXXXXXXX)` gives the address of a debug block. It holds a
16-frame ring of true and drawn positions, which `captures/014-framerate/fr_probe.py --interp` and `interp.py` read.

**Script and world cameras** (second play test: the car jittered under the jump camera and in cut-scenes).
- The FSM camera actions that `fsm_ActionDispatch` calls (0x413118..0x413327) run with every car on its drawn pose,
  and so does the frame-loop camera update.
- World cameras (anything but cockpit 0x406ab0, chase 0x407ad0 and free-look) draw cars on a quadratic B-spline
  through the last three physics poses, not the linear blend. The physics path weaves by up to 16° per step, and
  straight segments showed a kink every 41.7 ms. Per-frame direction change p95 went 23.5° -> 11.2°, for about half a
  step more lag, only in those views.
- `I76_INTERP_SMOOTH=0` turns the spline off; `=2` uses it everywhere.

**Exact frame dt.** With `I76_HIRES_CLOCK` the frame hook replaces the whole-millisecond dt (16/17 ms at 60 fps) with
the exact QPC interval, offline only.

**Engine dt with the fixed step.** `I76_ENGINE_DT_FIX` hands the engine 0.05 s per substep when the fixed step is
on, which is what stock at 20 fps does (every substep sees the whole ~50 ms frame).

**Saving.** Play the sandbox through `i76.exe`, not `i76_pristine_fix.exe`: only `i76.exe` imports `u32x.dll`
(save-screen mouse translation, ghosting fix), and saves failed in the first test session because the launcher
used the other exe.

**Not yet covered.** Things spawned at the true pose during the sim can sit up to one step ahead of the drawn car:
muzzle flashes, projectiles, smoke. Wheel/suspension animation follows the body but is not interpolated itself. AI cars
are interpolated, but only the player's poses have been measured. Multiplayer is untested (two copies can run on
one PC with `I76_MULTI_INSTANCE=1`, but no session between them was achieved).

## History

The diagnosis as it was written, kept dated so nothing is lost. Several of these paragraphs were later overtaken
(the aux hooks were built and the volume now works; `MCI_PLAY` was observed in a mission; MSVC builds the DLL);
each is marked where that happened. The companion narrative is [docs/MUSIC.md](../docs/MUSIC.md) (diagnosed
2026-08-04, fixed 2026-08-08).

### The problem (2026-08)

The base game plays its soundtrack as **CD audio through MCI** — it opens the
`cdaudio` device with `mciSendCommandA` and plays track N. GOG ships those tracks
as `music\N.mp3`, but with no CD drive the MCI `cdaudio` device won't open
(`MCIERR_CANNOT_LOAD_DRIVER`, 266), so there's no music and the game asks for the
disc. (The **Nitro Pack is unaffected** — it plays music through `audiere.dll`,
not MCI, which is why its music already works.)

### Why not just a winmm.dll proxy

The obvious fix — drop a `winmm.dll` next to the game — **does not work here**:
dgVoodoo hardens the process's DLL search path to `System32`, so the game binds
`mciSendCommandA` to the real `SysWOW64\winmm.dll` before an app-directory
`winmm.dll` can load. Verified with a module lister; DotLocal (`i76.exe.local`)
didn't override it either. (MUSIC.md later pinned the mechanism more precisely: the AppCompat shim engine
preloads `SYSTEM32\winmm.dll` by base name before the exe's own imports resolve.)

### 2026-08-04: THREE bugs, found by logging every call

The hook had been installed and deployed for days while doing nothing. Making the
log record **every** call — not just cdaudio ones — turned "no music" into three
specific, sequential bugs. Each one was invisible behind the previous.

**1. `MCI_OPEN_TYPE_ID` was explicitly rejected.** `wants_cdaudio()` began:

```c
if (!(flags & MCI_OPEN_TYPE) || !p || (flags & MCI_OPEN_TYPE_ID)) return 0;
```

and the log showed the game opening five times with `flags 0x3000` =
`MCI_OPEN_TYPE | MCI_OPEN_TYPE_ID` — the *only* form it ever uses. The hook refused
the exact call it exists to catch. With `TYPE_ID` set, `lpstrDeviceType` is not a
string but an integer device id, so a string compare can never match and
dereferencing it would be a wild read — presumably why the original bailed rather
than risk it. Correct handling is to compare the low word against
`MCI_DEVTYPE_CD_AUDIO`.

**2. Per-track status answered `0`.** After the open worked, the log showed the game
asking eighteen per-track questions (`flags 0x110` = `MCI_STATUS_ITEM | MCI_TRACK`)
and then never playing. The handler's `default: dwReturn = 0` told it every track was
type 0 and length 0 — an empty disc. **Answering `MCI_OPEN` is necessary but nowhere
near sufficient: the engine validates the disc before touching it.**

**3. `MCI_STATUS_POSITION` + `MCI_TRACK` is a TOC query, not "where is playback".**
It asks *where track N starts on the disc*, and the engine derives each track's
length from consecutive starts. Returning the playback position (0 while stopped)
made all sixteen tracks zero-length. Now it returns cumulative start offsets, and
the values check out against the format the game selects — `MCI_FORMAT_TMSF`, packed
`track | m<<8 | s<<16 | f<<24`. Track 4 starts at 229896 ms → m3 s49 f67 →
`1127285508`, exactly what the game is handed. (Worth noting because in decimal those
TOC values look like garbage and are not.)

#### Confirmed working

The engine's own state, before and after (addresses from
[MEMORY-MAP-INDEX.md](../docs/MEMORY-MAP-INDEX.md) Tier 1):

| | before | after |
|---|---|---|
| `0x524674` music-active flag | `0` | **`1`** |
| `0x4ed890` MCI device handle | `0xFFFFFFFF` | **`0x0000C0DE`** |
| `0x4ed894` aux-volume device | `0xFFFFFFFF` | `0x00000000` |

`0xC0DE` is `FAKE_CD_ID` — the engine stored our virtual device's handle. It opens
the device, sets `TMSF`, reads the full TOC for tracks 1..17, queries our fake
`AUXCAPS_CDAUDIO` aux device, and sets volume (so the in-game music slider now
works: `auxSetVolume(0xB337B337) -> 700/1000`).

**Not yet observed: `MCI_PLAY`.** Every test above was at the title/menu, and the
base game plays its soundtrack in missions. Load one with `I76MUSIC_LOG=1` (the
launcher sets it) and the log will show either `MCI_PLAY … -> track N`, which is
done, or another status query answered wrongly — in which case the log names it.

> **Superseded 2026-08-08:** `MCI_PLAY` was observed in a mission
> (`MCI_PLAY flags=0xC from=104012301 -> track 13`, then `track 2`; the engine's own choices). Log excerpt in
> [docs/MUSIC.md](../docs/MUSIC.md).

### Earlier finding (2026-08-04): the hook was installed and NEVER CALLED

With `I76MUSIC_LOG=1`, `mciproxy.log` after a full session read exactly one line:

```
--- strlkproxy: IAT patch mciSendCommandA old=75511840 new=73ff16c0 ---
```

The patch lands. Then nothing — no `MCI_OPEN`, no `MCI_PLAY`, in a mission or
anywhere else. **The game is not failing at CD audio, it is declining to attempt
it**, so hooking `mciSendCommandA` alone cannot be enough.

The cause is almost certainly the **aux gate**. The game imports
`auxGetNumDevs` / `auxGetDevCapsA` / `auxSetVolume`, and on a machine with no
optical drive the real `auxGetNumDevs()` returns **0** (measured). On 90s hardware
CD audio was mixed in *analogue* and its level set through an `aux` device, so "no
aux device" meant "no CD audio present" — and the engine checks that before it ever
opens the MCI device.

`strlkproxy.c` now also hooks those three, advertising exactly one
`AUXCAPS_CDAUDIO` aux device **when the system has none** (so a machine with real
aux hardware is untouched), and translating `auxSetVolume` to
`setaudio <alias> volume to N` — which also fixes the volume limitation below.

**This is written but NOT YET BUILT OR CONFIRMED.** See the build note.

> **Superseded:** built (MSVC x86 fallback in `build.ps1`, see [Build](#build)) and confirmed — the "Confirmed
> working" table above and the 2026-08-08 mission log show the aux device being queried and the volume set.

### Building the aux change: needs 32-bit gcc (2026-08-04)

The committed `Strlkup.dll` predates the aux hooks. Rebuilding needs a **32-bit
gcc** (w64devkit), which is not installed here.

**MSVC cannot substitute, despite being available.** The five exports are
*forwarders* to `strlkup_orig.dll`, and `link.exe` refuses to emit them from either
form:

```
strlkup.def : error LNK2001: unresolved external symbol StrLookupCreate   (.def forwarder syntax)
LINK        : error LNK2001: unresolved external symbol StrLookupCreate   (/EXPORT:name=strlkup_orig.name)
```

It insists the symbols exist locally rather than treating a dotted target as a
forward. gcc/dlltool reads the `.def` correctly, which is why the original was built
that way.

Two ways forward, neither started:

1. **Install w64devkit** (portable, no installer) and run `build.ps1` — it prefers
   gcc and only falls back to MSVC.
2. **Drop linker forwarders entirely**: implement the five exports as
   `__declspec(naked)` stubs that `jmp` to `GetProcAddress(strlkup_orig, …)`. On x86
   a plain jump preserves the stack frame for any calling convention and any
   argument list, so the signatures never need to be known. `StrLookup_Global_Object`
   is DATA and would need separate handling.

`build.ps1` is now **non-destructive** — it builds to `Strlkup.build.dll`, verifies
the architecture, and only then replaces `Strlkup.dll`. It previously built straight
over the committed, deployed binary and destroyed it on each failure.

> **Superseded:** way 2 was taken. `strlkproxy.c` forwards the four functions as `__declspec(naked)` `jmp` stubs
> to `GetProcAddress` results and repoints the game's IAT slot for the DATA export at the original's variable
> (comment block "FORWARDING THE FIVE Strlkup EXPORTS WITHOUT LINKER FORWARDERS"), so MSVC x86 builds it with no
> forwarders needed; `build.ps1`'s MSVC fallback has built every committed `Strlkup.dll` since (last 2026-09-27).
> w64devkit remains the preferred, optional path (see [Build](#build)).

### Known limitation (2026-08-04)

The game sets music volume via `auxSetVolume` on the aux device; with no aux
device that's a no-op, so it can't attenuate our mpegvideo playback — music plays
at the mpegvideo device's volume. If it's too loud, a follow-up is to also hook
`auxSetVolume` and translate it to `setaudio <alias> volume to …` on the mpegvideo
alias. (Left out for now: get music playing first.)

> **Superseded:** `auxSetVolume` is hooked and translated; `auxSetVolume(0xB337B337) -> 700/1000` was observed,
> so the in-game slider attenuates the MP3 playback.
