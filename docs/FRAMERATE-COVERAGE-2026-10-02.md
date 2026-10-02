# Frame-rate coverage: what the proxy fixes against what the spec says is frame-count dependent (P2-05)

*Analysis only, 2026-10-02. No game runs, no code edits. Backlog row P2-05 (`docs/BACKLOG-2026-10-02.md`).*

**Sources, with the versions the line numbers refer to.**

- `music-fix/strlkproxy.c` at commit `a2c1fa6` (the working copy at the time of writing; identical to HEAD for that file).
- i76-map `subsystems/framerate.md` (192 lines), `camera.md`, `renderer.md`, `ai.md`, `weapons.md`, `physics.md`,
  `simclock.md`: static readings of the Galaxy exe md5 `9a232dcc`.
- i76-uncap-lab `docs/framerate/MEASUREMENTS.md` section 4 (lines 30-97) and `docs/FPS-120.md` (this repo).
- Disassembly quoted below: `python tools\disasm.py <addr> --bytes` in i76-map over `ghidra/i76_ref.exe` (md5
  `9a232dcc`), plus a raw `E8`-xref scan of `.text` for call counts and a `disp32` scan for data xrefs. Old bytes are
  from that pristine image. The proxy's `patch_bytes` (strlkproxy.c 676-687) checks every site at run time, and the
  only build-to-build difference known in these ranges is the AiO simclock rewrite the hires clock already handles
  (strlkproxy.c 791-795), so the bytes should hold on the sandbox exe `4fabc303`; the integrator verifies them live.

**Mechanisms used by the proxy** (the "how covered" column below uses these letters):

| key | mechanism | where it lives |
|---|---|---|
| A | **dt-scaled constant**: the site's `fld/fmul [constant]` operand is repointed at a proxy variable recomputed every frame as `constant x frame_dt x 20` (`k = simclock_dt x 20`, line 925-927) | frame hook `frame_cap_then_clock`, 879-932 |
| B | **20 Hz grid coalescing**: `g_tick20` is set on the frames that cross a 50 ms accumulator (928-930, `g_tick20_n` counts grid frames); per-frame actions run only on grid frames, or are held and replayed on the next one | same, plus the wrappers in 989-1157 |
| C | **fixed physics step**: `simclock_StepperBegin` replaced by an accumulator of exactly `1/rate` s steps (24/s reproduces stock 20 fps) | `fixed_stepper_begin` 1552-1561, site 0x49cc20 line 1572 |
| D | **render interpolation**: vehicles drawn between their last two physics poses; cameras run on drawn poses | 1576-1937 (11 hooks, 1913-1932) |
| E | **pinned 20 fps value**: a `call simclock_Get*` repointed at a function returning the stock 20 fps value (`ai_rate20` 1006 = 20, `ai_dt20` 1010 = 0.05, `step20_dt` 1053 = max(dt, 0.05)) | `apply_framerate_fixes` 1159-1264 |
| F | **exact clock**: simclock's two `GetTickCount` calls repointed at QPC ms; the frame hook then overwrites `simclock_dt`/`sim_dt` with the exact QPC interval (918) | `apply_hires_clock` 783-809 |

## 1. Proxy inventory: 51 patch sites across five switches

| switch | sites | what | lines |
|---|---|---|---|
| `I76_HIRES_CLOCK` | 0x49c85f, 0x49c929 (Galaxy) / 0x49c85d, 0x49c927 (AiO) | GetTickCount -> QPC ms (F); exact per-frame dt via the frame hook | 797-798 / 801-802, 918 |
| `I76_ENGINE_DT_FIX` | 0x46a333 (`call simclock_GetDt` in `physics_UpdateEngine`) | `engine_substep_dt`: 2 x sim_dt / count, or 0.05 under the fixed step (E/C) | 832-840, 849 |
| `I76_FRAMERATE_FIXES` (36) | clouds 0x405461, 0x405484 (A) | cloud UV scroll | 1172-1173 |
| | free-look 0x405bd0, 0x405c1c, 0x4061e7, 0x406233 (A) | pitch/yaw steps of camera modes 0x405b90 (view 0xfefe, end-of-match orbit) and 0x4061b0 (view 0xf, F2 orbit) | 1174 |
| | zoom 0x408a3f (A) | overview camera 0x408a10 zoom step | 1179 |
| | throttle 0x44f306, 0x44f366 (A) | keyboard throttle ramp | 1187-1188 |
| | lock tones 0x4a405e, 0x4a40ad (B) | `frame_sound_wrap`: new starts on grid frames only, loops pass | 1195-1197 |
| | AI gains 0x40fa15, 0x40fa8d (`ai_rate20`), 0x40fed9 (`ai_dt20`) (E) | throttle and steering one-frame gains pinned to 20 fps | 1204-1211 |
| | radar ping 0x4605ee, 0x4608f1 (B) | `radar_ping_wrap` / `radar_ping_flush` | 1219-1221 |
| | vehicle sounds 0x43d54d, 0x43d590, 0x43d5ec, 0x43d62b (B) | skid / turn / surface / flat / damage starts | 1223-1232 |
| | flamers 0x401cec, 0x401fcc (ageing, B), 0x401e23, 0x4020e8 (update main pass, B), 0x443fca (update dt, E), 0x4357c3 (damage, B), 0x44471d (hit explosion, B) | | 1236-1242 |
| | AI fire 0x414f75, 0x462bfb, 0x462c3e (B, decision cached per weapon record for the grid window) | | 1243-1245 |
| | ammo digits 0x4a44ca (B) | | 1246 |
| | smoke puffs 0x401e50, 0x40211a (B + extrapolated draws), 0x4414b9 (dt, E) | | 1247-1249 |
| | missile trails 0x401e35, 0x4020ff (B) | | 1250-1251 |
| `I76_FIXED_STEP` | 0x49cc20 (C) | | 1572 |
| `I76_RENDER_INTERP` (11) | 0x472990 (camera SetTransform entry), 0x403e69 (render call), 0x4f7788 (vehicle tick slot), 0x46391f and 0x403e16 (camera update calls), 6 FSM camera action calls 0x413118, 0x41319a, 0x4131f1, 0x413266, 0x4132ac, 0x413327 (D) | | 1913-1932 |
| frame hook (shared) | 0x4039b8 (`call simclock_Update`) | `frame_cap_then_clock` | 940 |

## 2. Coverage table

Columns: the spec row; its address(es); whether a proxy site covers it (site, function, mechanism letter); if not,
what a player sees at 60 and 120 fps (3x and 6x the stock-20 per-frame rate; 2x/3x if the row's "stock" is 60);
severity; fix shape. Evidence cites spec lines and `strlkproxy.c` lines.

### 2.1 framerate.md "Verified frame-rate dependencies" (lines 31-40)

| # | row | address(es) | covered? | at 60 / 120 if not | severity | fix shape / notes | evidence |
|---|---|---|---|---|---|---|---|
| 1 | Clock resolution (GetTickCount 15.6 ms steps) | 0x49c929 | **Yes**: `I76_HIRES_CLOCK` (F), 0x49c85f/0x49c929 -> `hires_clock_ms`; exact dt at 918 | - | - | Residual: the ms counter still hands simclock whole ms until the frame hook overwrites both dts with the QPC interval (902-919); `g_hires_on` requires the frame hook (806-807) | framerate.md 33, 65; strlkproxy.c 744-809, 902-919 |
| 2 | Uptime precision (float32 seconds since boot, Galaxy only) | 0x49c94c | **Yes** (mitigated, not removed): the QPC clock counts ms since process start, so float32 keeps sub-ms precision for ~4.6 h of play, 7.8 ms after 24 h (comment 767-771) | - | - | A full fix would patch the `fstp dword` at 0x49c94c to a double, not needed at session lengths | framerate.md 34; simclock.md 37-40; strlkproxy.c 767-771 |
| 3 | Engine RPM/torque smoothing with whole-frame dt per substep | 0x46a333 | **Yes** for the near path: `I76_ENGINE_DT_FIX` -> `engine_substep_dt` (E/C) | - | - | **Not right on the far path** (U4 below): `physics_StepVehicleFar` 0x43a3c0 calls the same `physics_UpdateEngine` 0x46a320 once per frame (0x43a548), where the stock whole-frame dt is already correct; with the fix it gets 2 x dt (no fixed step) or 0.05 every frame (fixed step) | framerate.md 35; simclock.md 56-66; strlkproxy.c 811-850 |
| 4 | Cloud scroll (u -= 1/(1001-s) per call) | 0x405461, 0x405484 in `renderer_DrawClouds` 0x405200 | **Yes**: `g_cloud_u`/`g_cloud_v` (A), lines 1172-1173; measured invariant at 60 (0.0300 /s) | - | - | Coupled to the mirror (row 7): the level-2 mirror pass also calls 0x405200 (0x4459a1, verified in disassembly), every 2nd frame, so the 1.5 calls/frame ratio is what keeps the measured invariance. A mirror cadence change must keep the mirror's cloud step at the stock 1.0 (P5) | framerate.md 36, 65; FPS-120.md 94; strlkproxy.c 866, 925-926, 1172-1173 |
| 5 | Free-look camera keys (1 deg per input unit per call) | 0x405bc4..0x405c28 (mode 0x405b90), 0x4061e7..0x40623f (mode 0x4061b0) | **Yes**: `fl_sites` 0x405bd0, 0x405c1c, 0x4061e7, 0x406233 -> `g_cam_rate` (A), line 1174 | - | - | These four `fmul [0x4bc528]` are the only references to that constant (MEASUREMENTS.md 184-190) and they are the F2 orbit keys **and** the end-of-match spin (`track_yaw_delta` 0x53679c = 8 from WinMain 0x403be5/0x403d40 feeds 0x405c16 `fild [0x53679c]`). The lab's data patch of 0x4bc528 is superseded: the proxy computes its variable from the stock constant in code (866), never reads 0x4bc528, and its byte check is on the `fmul` operand (D8 0D 28 C5 4B 00), which a data patch does not touch - no double scaling either way | framerate.md 37; camera.md 19, 32; MEASUREMENTS.md 175-205; strlkproxy.c 1162-1174 |
| 6 | Keyboard throttle ramp (+0.4 / -0.5 x (1 - hold/3) per call) | 0x44f306, 0x44f366 | **Yes**: `g_thr_up`/`g_thr_dn` (A), 1187-1188 | - | - | | framerate.md 38, 65-66; strlkproxy.c 1181-1188 |
| 8 | Zoom key (zoom *= 1 - input x 0.01 per call), overview camera | 0x408a3f in 0x408a10 (view 0x17, F10) | **Yes**: `g_zoom_rate` (A), 1179 | - | - | This is the "overhead/map zoom" FPS-120.md lists as unfixed - it is fixed (section 4) | framerate.md 39; camera.md 27; strlkproxy.c 1175-1179 |
| 7 | Rear mirror refresh every 2 frames | `renderer_DrawRearMirror` 0x445750: `call simclock_GetFrameCount` 0x4457b4, `cmp eax,[0x52bbc8]` / `jl` 0x4457b9-bf, `add eax,2; mov [0x52bbc8],eax` 0x4457c5-c8 | **No** | mirror redraws 30/s at 60, 60/s at 120 (stock 10/s); a level-2 mirror is a full scene redraw (0x445933-0x4459b4: terrain, roads, flamers, objects, tracers, puffs, clouds, flush) | cosmetic (smoother mirror) / **render cost** at 120 | Repoint the `call 0x49c7d0` at 0x4457b4 to a function returning the 20 Hz grid count `g_tick20_n` (B): the `>= next, next += 2` logic then refreshes on every other grid tick = 10 Hz as stock. Pair it with a stock-size cloud step on the mirror pass (P5) | framerate.md 40; renderer.md 36; disassembly above |

### 2.2 framerate.md retractions, neutral list, leads (lines 42-100)

| row | address(es) | covered? | at 60 / 120 if not | severity | fix shape / notes | evidence |
|---|---|---|---|---|---|---|
| Retracted: radar contact ageing (1 Hz sim-time catch-up), 0x477ed0 per-call offset | 0x460c80 / 0x45faf0, 0x477ed0 | n/a (neutral) | - | none | no site needed | framerate.md 42-47 |
| Static-screen neutrals: network averaging 0x454960/0x454ff0/0x4541b0; refcounts 0x449a00/0x44a290/0x4677d0/0x4a05f0; horizon copy 0x401970; VM frame counter 0x4155f0 | as listed | n/a (neutral) | - | none | | framerate.md 49-55 |
| Steering keys (absolute +-sqrt(hold/3)), cockpit look 0x406ab0 and chase 0x407ad0 (dt-scaled easing) | 0x44dec0.., 0x406ab0, 0x407ad0 | n/a (neutral to first order) | - | none | camera.md 50 notes the easing "snaps at low fps (rate x dt > 0.95)" - a low-fps artefact, not a high-fps one | framerate.md 60-61; camera.md 17, 20 |
| Lead: AI throttle 1/dt one-frame gain | 0x40f9c0: reads at 0x40fa15, 0x40fa8d | **Yes**: `ai_rate20` (E), 1204-1206; measured chatter 1.62 vs stock-20 1.68 | - | - | | framerate.md 89-93; ai.md 56-70 |
| Lead: AI steering 1/dt one-frame gain | 0x40fe80: read at 0x40fed9 | **Yes**: `ai_dt20` (E), 1211; "the steering was the cause" | - | - | | ai.md 68-70; strlkproxy.c 1007-1011 |
| Lead: other 1/dt users 0x417bf0 (`ai_CanSee`), 0x419e20 (`ai_IsBlockedAhead`) | | n/a: cancel (1/dt against a sim_dt sweep) | - | none | | ai.md 64 |
| Lead: 1/dt user 0x41b270 (`ai_TestControlCandidate`) | rate reads 0x41b58f, 0x41b5ab; prediction dt read inside 0x43a560 at 0x43a562; probe dt reads 0x41a54e (cars), 0x41a047 (static colliders); rand gate 0x41b673 | **No** (three distinct effects, see U2 and U3) | see U2, U3 | gameplay (AI) | P2 (rand gate), P3 (prediction horizon) | ai.md 65; disassembly in section 5 |
| Lead: 1/dt user 0x40a320 (`ai_FrameTick`) | 0x40a4ce (`min(rate, 10000)`, 0x4bc604 = 10000.0), 0x40a4ea (`x 50`, 0x4bc608 = 50.0) | **No** | broad-phase sweep box 50/dt: 1000 m at 20, 3000 m at 60, 6000 m at 120 | none (perf: more candidate pairs) | Optional: repoint both `call simclock_GetSimRate` at `ai_rate20` (E). Not proposed; cost only | ai.md 66; disassembly |
| Lead: 1/dt users 0x4354c0 (`weapon_FlameHitTest`), 0x435830 (`physics_SweepSegment`), 0x435cc0 (twin) - "three unaudited" in FPS-120.md | 0x435522 (`GetSimRate`); 0x43583a (`GetSimDt`) + 0x435846 (`GetSimRate`); 0x435cca + 0x435cd6 | **Audited now: cancel by shape, no site needed** (medium confidence, static). 0x4354c0 multiplies the three components of its segment argument by the rate (0x435527-0x435547) to make a velocity for the sweep code, which sweeps over dt; 0x435830/0x435cc0 read dt and rate back to back at entry; the rate is parked at [esp+0x38] (`fxch st(5); fstp` 0x435880-0x435882) and multiplied onto the differences between the object's position doubles (+0x40/+0x48/+0x50) and the argument point (0x4358e2, 0x4358ee), i.e. a velocity from a displacement, while the dt parked at [esp+0x84] is handed on at 0x435a13 to the sweep: displacement x rate x dt. None is a gain on a control | - | none | Flamer length and ammo use measured sane at 60 with the fix (weapons.md 129-133) | framerate.md 92; weapons.md 114-117; FPS-120.md 123 |
| Lead: weapon jam roll | 0x4a4351..0x4a43ac | n/a: network games only (0x4a4257 gate) | - | none offline | | framerate.md 94-99; weapons.md 18-20 |
| Lead: frame-count users, renderer texture cache | `renderer_InvalidateTexture` 0x42ec20 (0x42ecba: stamps 0x5280e8 = frame), `renderer_TexCacheMakeEntry` 0x42f5f0 (0x42f698: entry+0xc = frame, an LRU stamp), `renderer_TexCacheGetHandle` 0x42f6b0 (0x42f72e-0x42f772: evicts at most once per frame **and** only when GetTickCount >= last + 166 ms (0xa6), 333 ms (0x14d) for the same handle) | n/a: **wall-time bound, neutral** - FPS-120.md's "ages 2x faster" does not hold; the frame count only orders entries and rate-limits to one eviction per frame under a 6/s wall-time cap | - | none | | framerate.md 100; FPS-120.md 125; disassembly |
| Lead: frame-count user `renderer_DrawCockpit` 0x45adf0 | 0x45ae7d-0x45ae99: `frame - [0x4f70f8] == 1` | n/a: a "drawn on the previous frame" continuity test, true at any rate | - | none | | framerate.md 100; disassembly |

### 2.3 framerate.md "Per-frame physics outside the substeps" and "Step rate" (lines 110-151)

| row | address(es) | covered? | at 60 / 120 if not | severity | fix shape / notes | evidence |
|---|---|---|---|---|---|---|
| Object/vehicle collision: once per frame with the frame sim dt, sweeps cover [0, dt], last contact wins | `physics_CollideObjects` 0x4349c0 (WinMain 0x403a12, `E8 A9 0F 03 00`, the only caller); dt reads: 0x4349da (driver), 0x434c70 (pair test 0x434bb0, passed to the swept-sphere test 0x434f00 at 0x434c7e), 0x43f9e1 (scenery tree 0x43f8c0, passed down at 0x43f9f7) | **No** | **Stock (no fixed step): dt-correct**, measured not fps-dependent (MEASUREMENTS 73-96). **Under `I76_FIXED_STEP` it is not**: the sweep covers one frame (16.7 ms at 60, 8.3 ms at 120) but the step that consumes the contact (cars copy the record into entity+0x38 and consume it on the next substep, physics.md 121-122) moves 41.7 ms worth. The contact the step uses comes from the sweep of the same frame (WinMain order: collision 0x403a12 before the ticks 0x461c80), so it looks 40% (60 fps) / 20% (120) of the step ahead. At 20 m/s that is 0.33 / 0.17 m against a 0.83 m step and a 0.45 m cactus trunk | **gameplay (unmeasured)**: tunnelling at step boundaries; grows with fps once the step is fixed | **P1**: repoint the three `call simclock_GetSimDt` at a function returning `max(sim_dt, g_fixed_step)` when the fixed step is on. Measure with `cactus-ab.ps1` before and after (n >= 10 approaches per rate) | framerate.md 112-113; physics.md 103-122; MEASUREMENTS.md 73-96; FPS-120.md 121; disassembly |
| Far vehicles: one whole-frame kinematic step, no stepper | `physics_StepVehicleFar` 0x43a3c0 (sole caller `entity_TickVehicle` 0x46384e, taken when `camera_ClassifyDistance` 0x406840 returns 2) | **Stock: neutral** (one dt-correct step per frame). **Proxy-induced dependency**: 0x43a3c0 calls `physics_UpdateEngine` 0x46a320 at 0x43a548, whose dt read 0x46a333 is repointed by `I76_ENGINE_DT_FIX` to `engine_substep_dt` - 0.05 on every frame under the fixed step (3x the stock far-path convergence per second at 60, 6x at 120), 2 x dt without it (2x at any rate) | far AI cars' RPM/torque settle 3x/6x faster than stock; they are > 849 m from the camera (renderer.md 16) | minor (AI car speed far away); sim correctness | **P4**: flag the far call and have `engine_substep_dt` return the stock whole-frame dt inside it | framerate.md 114-115, 150-151; physics.md 123-129; strlkproxy.c 832-840; disassembly |
| Keyboard head-look in camera mode 2 "moves a fixed step per frame (range-p-1)" | binoculars mode 0x4071a0 (camera_mode 2): reads `pilot_glance` 0x536770/78/80 at 0x40728b/0x4072b0/0x4072c2 as integer degrees x 1 deg (0x4bc52c) into targets 0x4c296c/64/74, then eases the angle toward the target with 2 x dt (0x4072db `fld [esp+0x20]; fadd st0,st0` = 2 x `simclock_GetDt` from 0x4071aa; 0x40732c-0x40738f `+= (target - x) x 2dt`, snap when 2dt > 0.95 or error < 0.005) | **Claim unsupported - no per-frame step found.** All 17 `.text` references to 0x536770 (and 15 to 0x536778, 13 to 0x536780) are absolute stores: the input layer sets them from `atan2` of a look direction in degrees (0x44fc58-0x44fc5d, 0x44fd06-0x44fd0b in 0x44f830; 0x44efb7-0x44efbc, 0x44f04e-0x44f053 in 0x44ed50), to preset values (the jump table 0x44ff60 -> 0x44fd2b-0x44fe25: -88/-45/0/93/45/160 deg etc.), to a register (0x44ee09-0x44ee15, 0x44f116-0x44f122) or clears them (0x44dd0a `rep stosd`, 0x44f0c1). The binocular zoom 0x5367a4 has 8 references, all `= 0x10000` resets (0x406a20, 0x406ef5, 0x407112, 0x40960e, 0x44fe2e) or reads (0x4074c4 x 1/65536) | - | none found | **Correct framerate.md line 117**: the mode-2 head-look is an absolute target eased at 2 x dt (first-order neutral, same class as the cockpit look at 4 x dt). The `range-p-1` batch this row cites appears elsewhere only as `damage.md`'s explosion section (line 61) and as evidence records E46067-E46076, which are the D3D device layer (cluster P, 0x430110..0x430950); none names a head-look site, so the row looks like a misfiled note. If a per-frame glance step exists it is in a writer not in this list, i.e. nowhere in `.text` | framerate.md 117; camera.md 18; disassembly of 0x4071a0, 0x44f830, 0x44ed50, 0x44dcc0; disp32 scan |
| Orbit keys (1 deg per frame) | 0x4061e7 / 0x406233 (view 0xf) | **Yes**: row 5 (A) | - | - | FPS-120.md lists these as unfixed; see section 4 | camera.md 19; strlkproxy.c 1165, 1174 |
| End-of-match spin (8 deg per frame) | 0x405bd0 / 0x405c1c (view 0xfefe, `track_yaw_delta` = 8) | **Yes**: row 5 (A); this is MEASUREMENTS' "death camera" | - | - | | camera.md 32; MEASUREMENTS.md 143-205 |
| Overhead-map zoom | 0x408a3f | **Yes**: row 8 (A) | - | - | | camera.md 27 |
| Smoke puffs live 20 calls | `renderer_UpdateSmoke` 0x4414a0 from 0x401e50 / 0x40211a; dt at 0x4414b9 | **Yes**: `smoke_update_wrap` (B, with extrapolated draws between grid frames), `step20_dt` (E); measured 19.1 steps/s with the fix vs 57.8 without | - | - | | framerate.md 120-122; renderer.md 61; strlkproxy.c 1115-1136, 1247-1249 |
| Missile trails lose 4 segments per call near expiry | `renderer_QueueSmokeTrails` 0x442ba0 from 0x401e35 / 0x4020ff (0x442bd6) | **Yes**: `trails_wrap` (B: expiry moved past the 2 s window between grid frames) | - | - | | framerate.md 123; renderer.md 62; strlkproxy.c 1138-1157, 1250-1251 |
| Flamer streams lose 2 segments per call | `weapon_AgeFlamerStreams` 0x443e90 from 0x401cec / 0x401fcc | **Yes**: `flame_age_wrap` (B); measured 18.7 segments vs stock-20 19.0 | - | - | | framerate.md 123, 135-136; weapons.md 110-113, 129-131; strlkproxy.c 1054, 1236-1237 |
| Flamer shape and per-hit damage from the frame dt; damage per render call, again in the mirror | `weapon_UpdateFlamerStreams` 0x443fc0 (dt read 0x443fca; main-pass calls 0x401e23 / 0x4020e8; mirror calls 0x4458fe / 0x445968 **not** wrapped), `weapon_ApplyFlameDamage` call 0x4357c3, explosion call 0x44471d | **Yes**: dt pinned (E, 1240), damage and explosion applied only from main-pass grid frames (`g_flame_dmg_ok`, B, 1055-1074). The mirror pass still rebuilds the shape and counts hits (`g_idbg_flame_hits`) but applies nothing | - | - | Damage per second with the fix follows from the code; "not yet measured on a target" (weapons.md 132-133) | framerate.md 125-127; weapons.md 114-128; strlkproxy.c 1040-1074, 1238-1242 |
| AI fire decisions: rand gate rolled per frame | `ai_ShouldFireWeapon` 0x418200 from 0x414f75 (vehicles), 0x462bfb / 0x462c3e (turrets) | **Yes**: `ai_fire_wrap` (B, decision held per weapon record for the window); measured 1.2-1.9 yes/weapon/s vs stock-20 1.3-2.4, stock-60 4.9-5.2 | - | - | `I76_AI_FIRE_CACHE=0` keeps counters, passes through | framerate.md 128-130; ai.md 125-150; strlkproxy.c 1077-1109, 1243-1245 |
| HUD ammo digits roll one step per call | `weapon_HudRollAmmoDigits` 0x4a4e40 from 0x4a44ca | **Yes**: `ammo_roll_wrap` (B); not measured | - | - | | framerate.md 131-132; camera.md 86-88; strlkproxy.c 1111-1113, 1246 |
| Draw-path sweep and per-frame rand sweep: nothing else | - | n/a | - | none | | framerate.md 133-134; weapons.md 122-123 |
| Physics step size is the real clock (body motion, lip pop, coasting loss follow steps/s) | `simclock_StepperBegin` 0x49cc20 | **Yes**: `I76_FIXED_STEP=24` (C) + `I76_RENDER_INTERP` (D) | - | - | 24 reproduces stock 20; 40 made jumps fall short (1528-1535) | framerate.md 138-146, 63-85; strlkproxy.c 1516-1574 |
| Per-frame sound restarts: missile-lock tones, skid / flat / damage | 0x4a405e, 0x4a40ad (in 0x4a3760); 0x43d54d, 0x43d590, 0x43d5ec, 0x43d62b (in 0x43d500) | **Yes**: `frame_sound_wrap` (B) | - | - | | framerate.md 147-149; strlkproxy.c 980-1000, 1189-1197, 1223-1232 |
| Off-screen vehicles: cheap branch with the whole frame's dt | 0x43a3c0 | **Stock-neutral**; proxy caveat U4 | see far vehicles above | minor | P4 | framerate.md 150-151 |

### 2.4 framerate.md "Mission scripts and rand" (lines 153-192)

| row | address(es) | covered? | notes | evidence |
|---|---|---|---|---|
| Script VM steps once per rendered frame, no dt; time waits on the mission clock | `fsm_RunMachines` 0x4149f0 from 0x40a644; frame counter 0x524550 | n/a: **neutral by audit** (330 rand sites: 0 polled every tick; waits are `timeGreater`/`timeLesser`) | A machine counting passes would run 3x/6x; none found in the 25 stock missions. Custom missions are not audited | framerate.md 155-171 |
| Attack-gated rolls under continuous damage (flamer stream, sustained ram) | `ai_RecordDamageEvent` 0x4157a0; T01 pc3831 | **Yes** for the flamer case (the flame damage hold, B); sustained ram contact still stamps per frame (collision damage is applied per contact record, once per frame) | T01 pc3831 (no cooldown) under continuous ram: 3x/6x re-target rolls - not reachable in normal play per the row | framerate.md 173-186 |
| Exe rand users: tactic selector 0x412680, specials panel 0x467e30 | | n/a: event-driven / cosmetic | | framerate.md 188-192 |

### 2.5 MEASUREMENTS.md section 4 ("What IS still frame-rate dependent", lines 30-97)

| item | what | covered? | notes | evidence |
|---|---|---|---|---|
| 1 | Post-death rotating camera spins too fast (-475 deg/s at 60 vs -143 at 20) | **Yes**: row 5, site 0x405c1c (the `fild [0x53679c]; fmul [0x4bc528]` the write-up diagnosed at 0x405c16-0x405c28) (A) | The lab's data patch (`patch-camera-rate.ps1`, 0x4bc528 -> -0.3333 deg) is a fixed-60 tuning; the proxy version is dt-exact at any rate and does not conflict with it (row 5) | MEASUREMENTS.md 143-222; strlkproxy.c 1162-1174 |
| 2 | Chassis roll too fast: frequency, not amplitude (roll reversals 15-22/s at 60 vs 4.5-9.7 at 20) | **Yes**: the cause is the substep size (framerate.md 66-85); `I76_FIXED_STEP=24` (C) brings 60 fps back to the 20 fps rest fraction (65% vs 62%), `I76_RENDER_INTERP` (D) hides the cadence | The 2026-08-17 "fix target: suspension per-frame constants" was superseded by the step-size finding | MEASUREMENTS.md 36-56; framerate.md 73-85 |
| 3 | Over-rotates in mid-air (spin acquired on the ground, 0.17-0.79 rad/s at 60 vs ~0 at 20) | **Yes, by the same mechanism** (C): the contact model's projection/rest cycle is step-size shaped (framerate.md 76-83); the jump was re-measured at 24 steps/s with ramps (capture 014 `jump.py`) | Not separately verified as "spin at takeoff" after the fix; the FPS-120 protocol step 3 repeats the jump | MEASUREMENTS.md 58-65; FPS-120.md 196-202 |
| 4 | Sky moves too fast | **Yes**: row 4 (A), measured 3.0x stock-60 -> invariant with the fix | | MEASUREMENTS.md 66-75; framerate.md 65 |
| 5 | Collisions pass through objects: **not** fps dependent at stock (speed-driven) | n/a at stock. **Reopened under the fixed step** (U1): the sweep/step mismatch did not exist when this was measured (2026-08-17, no fixed step) | | MEASUREMENTS.md 76-96 |

### 2.6 FPS-120.md section 3 rows (lines 119-131), as the record stands

| FPS-120 row | status after this audit |
|---|---|
| Object/vehicle collision 0x4349c0 | uncovered, gameplay risk under the fixed step: **P1** |
| Far vehicles 0x43a3c0 "neutral" | stock neutral; proxy caveat under `I76_ENGINE_DT_FIX`: **P4** |
| 1/dt readers 0x4354c0 / 0x435830 / 0x435cc0 "unaudited" | audited: cancel by shape, no site (2.2) |
| Rear mirror refresh "known, cosmetic" | uncovered: **P5** (with the cloud coupling the row itself notes at line 94) |
| Renderer cache aging "ages 2x faster" | corrected: wall-time bound, neutral (2.2) |
| Script VM | neutral by audit |
| Head-look mode 2, orbit keys, end-of-match spin, overhead-map zoom "unfixed" | **three of four are fixed** (rows 5 and 8); head-look mode 2 is unsupported (2.3) |
| Sky, particles, tones, ping, AI fire, HUD digits | fixed, as stated |
| UI blink / menus | not examined here either; the frame counter does not advance at menus (MEASUREMENTS.md 155-158) |
| Weapon cadence, projectiles, gravity, suspension, hold timers | dt-driven, as stated |

### 2.7 Rows from the other subsystem docs not in framerate.md

| row | address(es) | covered? | notes | evidence |
|---|---|---|---|---|
| AI projectile-dodge check behind a per-call rand gate | 0x41b651-0x41b692 in `ai_TestControlCandidate` 0x41b270; the check itself `ai_CheckIncomingProjectiles` 0x41abf0 at 0x41b698 (sole caller) | **No** (U2) | gate: `rand() % 1000 > 850 + 150 x (1 - skill)` (0x4bc91c = 1.0, 0x4bca70 = -150.0, 0x4bca74 = 850.0), i.e. p = 0.15 x skill per call; 0x41b270 is called 14 times from the avoidance search (0x41b8ca..0x41ddfa), once per candidate per frame | ai.md 39, 65; disassembly |
| AI avoidance one-step prediction | `physics_PredictVehicleMotion` 0x43a560 (sole caller 0x41b2e5) reads `simclock_GetSimDt` at 0x43a562 and predicts one **frame** ahead through the kinematic model 0x43bdf0 / 0x43a5d0; the terrain probe 0x419930 (no clock read) tests the predicted pose; the car probe 0x41a530 (dt read 0x41a54e) and static-collider probe 0x41a040 (dt read 0x41a047) sweep a velocity made from the prediction x rate (0x41b58f/0x41b5ab `min(rate, 10000) x 50 x gear`, 0x4bc9a8 = 10000.0, 0x4bca6c = 50.0) over their own dt | **No** (U3): the sweep lengths cancel (ai.md 65) but the **horizon of the predicted pose is one frame**: 50 ms at 20 fps, 16.7 at 60, 8.3 at 120 | gameplay-ish (AI reacts to terrain one frame ahead; later at high fps); unmeasured | ai.md 34-39, 65; disassembly |
| `ai_FrameTick` sweep box 50/sim_dt | 0x40a4ce, 0x40a4ea | **No**; perf only | | ai.md 66 |
| Camera easing snaps when rate x dt > 0.95 | cockpit 4 x dt, chase 2 x dt | n/a (low-fps artefact) | | camera.md 50 |
| Radar sweep / contact ageing | 0x460310, 0x45faf0 | n/a: sim-time driven | | camera.md 119-122 |
| Smoke puff size easing 2 x dt inside the update | 0x4414a0 | **Yes**: the update's dt is `step20_dt` (E) | | renderer.md 61; strlkproxy.c 1249 |
| Mirror pass calls the flamer update | 0x4458fe (level 1), 0x445968 (level 2) | **Yes** by exclusion: unwrapped, so `g_flame_dmg_ok` = 0 there and nothing is applied | | weapons.md 124-125; strlkproxy.c 1055-1059 |
| Weapon fire timers, projectile life, MG batching | 0x4a6470, 0x4a0990 | n/a: dt-driven, measured | | weapons.md 21-24; MEASUREMENTS.md 13-27 |

## 3. Uncovered rows, by severity

| id | row | severity | at 60 fps | at 120 fps | proposal |
|---|---|---|---|---|---|
| U1 | Collision sweep window vs fixed physics step (0x4349c0 tree) | **gameplay, unmeasured** | sweep covers 40% of the step | 20% | P1 |
| U2 | AI projectile-dodge rand gate rolled per candidate per frame (0x41b673 / 0x41b698) | **gameplay (AI)** | 3x the dodge checks per second | 6x | P2 |
| U3 | AI avoidance prediction horizon = one frame (0x43a562, with 0x41b58f/0x41b5ab, 0x41a54e, 0x41a047) | gameplay-ish, unmeasured | horizon 16.7 ms (stock 50) | 8.3 ms | P3 |
| U4 | Far-vehicle engine dt under `I76_ENGINE_DT_FIX` (0x43a548 -> 0x46a333) | minor (sim), proxy-induced | 3x far-car engine convergence (fixed step), 2x (without) | 6x / 2x | P4 |
| U5 | Rear mirror refresh (0x4457b4) and its cloud step (0x4459a1) | cosmetic / render cost | 30 mirror redraws/s | 60/s, each a full scene at level 2 | P5 |
| U6 | `ai_FrameTick` sweep box 50/dt (0x40a4ce, 0x40a4ea) | none (perf) | 3000 m box | 6000 m | optional, 2 sites -> `ai_rate20` |
| U7 | Renderer texture cache (0x42ec20 / 0x42f5f0 / 0x42f6b0), `renderer_DrawCockpit` 0x45adf0 | none | neutral (wall-time bound / continuity test) | - | none |
| U8 | Head-look mode 2 | none found | - | - | correct framerate.md 117 |
| U9 | Menu / shell animation | not examined | - | - | - |

Everything else in the spec is covered by a proxy site (sections 1-2) or neutral by measurement or audit.

## 4. Corrections to the record

1. **FPS-120.md line 127** ("Keyboard head-look (camera mode 2), orbit keys (1 deg/frame), end-of-match spin (8 deg/frame),
   overhead-map zoom ... **unfixed**: the proxy covers free-look A/B (4 sites) and the zoom key, not these"). Three of
   the four **are** the free-look A/B sites and the zoom key: the F2 orbit keys are camera mode 0x4061b0 (view 0xf,
   camera.md 19) whose steps are 0x4061e7/0x406233; the end-of-match spin is mode 0x405b90 (view 0xfefe, camera.md 32)
   driven by `track_yaw_delta` = 8 through 0x405c1c; the overhead-map zoom is 0x408a3f in mode 0x408a10 (view 0x17,
   camera.md 27). All are in `apply_framerate_fixes` (1174, 1179). Only "head-look mode 2" remains, and no per-frame
   step exists for it (2.3). The same row's risk-table entry (line 157, "Unfixed per-frame camera keys 2x faster:
   certain") and the camera line of the implications table (143) inherit the error.
2. **framerate.md line 117**: "Keyboard head-look in camera mode 2 moves a fixed step per frame (range-p-1)" is
   unsupported (evidence in 2.3). Recommend rewording to: binoculars head-look = absolute `pilot_glance` targets
   eased at 2 x dt, neutral; and dropping the orbit/spin/zoom items from the "not addressed" sentence since they are the
   fixed sites.
3. **renderer.md line 20** ("More per-frame effects (frame-rate dependent, **not yet fixed in the proxy**): smoke
   puffs, missile trails, flamer streams") is stale: fixed 2026-09-27 (framerate.md 120-124, strlkproxy.c 1236-1251).
   renderer.md's own row 62 and the "Open" paragraph (128, item 4) carry the same stale wording.
4. **camera.md lines 43-44** list the orbit keys, end-of-match spin and overhead zoom as frame-rate dependent
   without noting the proxy covers them (only the radar ping line 39 says "coalesced by the proxy").
5. **FPS-120.md line 125** ("Renderer cache aging ... ages 2x faster in wall time"): the eviction in
   `renderer_TexCacheGetHandle` is gated by GetTickCount (166 / 333 ms) as well as by the frame count, so it is
   wall-time bound (2.2).
6. **FPS-120.md line 123** ("three unaudited 1/dt readers"): audited here, cancel by shape (2.2).
7. **The "per-frame tick delta / 4 floors to 0 above 45.5 fps" item is MechWarrior 2 lore, not an I'76 site -
   confirmed.** `docs/FRAMERATE-UNCAP-RESEARCH.md` 106-108 attributes it, in its own words, to "anpage ... MW2
   jump-jet integer-quantization" (the gist linked at line 182). In I'76, `simclock_Update` 0x49c920 computes
   `t = (float)(GetTickCount() x 0.001)` and `dt = t - last` in float seconds, clamped to [0.001, 0.2] s offline
   (simclock.md 7-8); the only integer quantity is GetTickCount's 15.6 ms quantum, which `I76_HIRES_CLOCK` replaces,
   and the stepper is `floor(sim_dt x 20) + 1` (simclock.md 25). The reachability pass over the substep tree found one
   whole-frame dt read and no integer-ms arithmetic (simclock.md 56-66); the 16 frame-scope candidates of the static
   screen are all read (framerate.md 49-55). A "/ 4 floors to 0" above 45.5 fps implies a tick base of about 182 Hz
   (5.5 ms ticks: 4 ticks per frame at 45.5 fps), which is the AIL/Miles timer heritage the research doc itself
   cites for MW2 (line 182), not GetTickCount. FPS-120.md 108-112 is right.

## 5. Next sites: five proposed patches, in the style of the existing ones

Conventions: every site is a 5-byte `E8 rel32` call unless stated; the proxy's `patch_bytes` checks the old bytes
first; `rel = target - (site + 5)`. dt sources: `simclock_sim_dt` 0x4fe420 (the sim step, = `simclock_dt` 0x4fe428
offline), `g_fixed_step` (the fixed step length, 0 when `I76_FIXED_STEP` is off), the 20 Hz grid `g_tick20` /
`g_tick20_n`. Apply order in `DllMain` (2525-2532): P1 and P4 need `g_fixed_step`, so they go after
`apply_fixed_step`; P2/P3/P5 belong inside `apply_framerate_fixes` (they need `g_ratefix` / the grid), which raises
its `n/36` count. Each proposal is **unmeasured**; the test named with it is the acceptance test.

### P1. Collision sweep window = the physics step (gameplay; measure first)

Three `call simclock_GetSimDt` (0x49c7a0) in the collision tree, all with a single chain of callers (0x4349c0 <-
WinMain 0x403a12 only; 0x434bb0 <- 0x434ae7 / 0x434b19 in 0x4349c0 only; 0x43f8c0 <- 0x43f656 in the pair test's
scenery path and its own recursion 0x43fd5f):

| site | old bytes | function | what the value is |
|---|---|---|---|
| 0x4349da | `E8 C1 7D 06 00` | 0x4349c0 driver | stored at [esp+0x10], the velocity x dt extent of the xz AABB sweep (0x434a42) |
| 0x434c70 | `E8 2B 7B 06 00` | 0x434bb0 pair test | pushed to the swept sphere-vs-sphere test 0x434f00 (0x434c7e) |
| 0x43f9e1 | `E8 BA CD 05 00` | 0x43f8c0 scenery tree | pushed to the node sweep (0x43f9f7) |

```c
/* Collision sweep window (physics_CollideObjects 0x4349c0, once per frame from WinMain 0x403a12, physics.md
 * "Objects and vehicles"). The sweeps cover [0, frame dt] from the current pose and the car consumes the contact on
 * its next substep. With I76_FIXED_STEP the pose only moves on step frames, by one step (41.7 ms at 24/s), while
 * the sweep still covers one frame: 16.7 ms at 60 fps, 8.3 at 120. Cover one whole step instead (or the frame, if
 * it is longer: several steps per frame below the step rate), so the contact the step consumes is the one on the
 * path the step will take. Stock (no fixed step) is unchanged. Far vehicles (0x43a3c0, one whole-frame step) are
 * swept over the same window; they are > 849 m from the camera and take collision damage on the predicted contact
 * (0x4643c0 applies it at once), so a far car may be damaged up to (step - dt) early. Measure: cactus-ab.ps1 at
 * 60 and 120 with the fixed step, before and after, n >= 10 approaches per rate. */
static float __cdecl coll_dt(void) {
    float sim_dt = *(volatile float *)0x004fe420;
    return (g_fixed_step > sim_dt) ? g_fixed_step : sim_dt;
}
static void apply_coll_window(void) {                       /* I76_COLL_WINDOW=1; after apply_fixed_step */
    static const struct { DWORD site; BYTE old[5]; } s[3] = {
        { 0x004349da, { 0xE8, 0xC1, 0x7D, 0x06, 0x00 } },  /* call simclock_GetSimDt in the collision driver */
        { 0x00434c70, { 0xE8, 0x2B, 0x7B, 0x06, 0x00 } },  /* ... in the mover pair test 0x434bb0 */
        { 0x0043f9e1, { 0xE8, 0xBA, 0xCD, 0x05, 0x00 } },  /* ... in the scenery tree sweep 0x43f8c0 */
    };
    int i, n = 0;
    if (GetEnvironmentVariableA("I76_COLL_WINDOW", NULL, 0) == 0) return;
    if (g_fixed_step <= 0.0f) { mlog("  coll-window: needs I76_FIXED_STEP - not applied"); return; }
    for (i = 0; i < 3; i++) {
        BYTE w[5] = { 0xE8 };
        LONG rel = (LONG)((DWORD_PTR)coll_dt - (s[i].site + 5)); memcpy(w + 1, &rel, 4);
        n += patch_bytes(s[i].site, s[i].old, w, 5, "collision sweep dt");
    }
    mlog("  coll-window: %d/3 sweep dt reads -> max(sim_dt, fixed step %.1f ms)", n, g_fixed_step * 1000.0f);
}
```

Acceptance: the cactus hit rate at 15 m/s at 60 and 120 fps with `I76_FIXED_STEP=24` matches the measured 67-70%
(MEASUREMENTS.md 84-88) within the binomial spread, before and after; a drop **before** the patch is the finding
that justifies it, a drop **after** means the window is wrong (e.g. the step consumes a contact whose time of impact
lies past its own length - check `entity+0x38` consumption in `physics_StepVehicle` step 2 if so).

### P2. AI projectile-dodge gate on the 20 Hz grid (gameplay: AI)

One site, the sole caller of `ai_CheckIncomingProjectiles` 0x41abf0: 0x41b698 `E8 53 F5 FF FF` in
`ai_TestControlCandidate` 0x41b270 (args: `push ebp; push ebx; push esi; push edi` 0x41b694-0x41b697, `add esp,0x10`
after, result in eax tested at 0x41b6a0).

```c
/* AI dodge checks (ai_TestControlCandidate 0x41b270, i76-map subsystems/ai.md 7). Each avoidance candidate (14 call
 * sites, several per car per frame) rolls rand() % 1000 against 850 + 150 x (1 - skill) (0x41b651-0x41b692:
 * constants 0x4bc91c = 1, 0x4bca70 = -150, 0x4bca74 = 850) and, on a pass (p = 0.15 x skill per call), runs the
 * incoming-projectile check 0x41abf0. Rolled once per frame per candidate, so at 60 fps the AI looks for projectiles
 * to dodge 3x as often per second as at stock 20 (6x at 120). Held to grid frames: between them the check reports
 * "nothing incoming", as a frame that does not exist at 20 fps would. The roll itself still runs (rand() is
 * consumed as before). */
static DWORD g_idbg_dodge_calls, g_idbg_dodge_yes;         /* for the debug block */
static int __cdecl ai_dodge_wrap(DWORD a, DWORD b, DWORD c, DWORD d) {
    int r;
    if (!g_tick20) return 0;
    r = ((int (__cdecl *)(DWORD, DWORD, DWORD, DWORD))0x0041abf0)(a, b, c, d);
    g_idbg_dodge_calls++; if (r) g_idbg_dodge_yes++;
    return r;
}
/* in apply_framerate_fixes, the cs[] table: */
/*  { 0x0041b698, 0x0041abf0, (void *)ai_dodge_wrap, "AI dodge check" }, */
```

Acceptance: a counter of 0x41abf0 calls per second (the wrapper's `g_idbg_dodge_calls`, or a `fr_probe.py` read of
it) in a melee with one AI car under fire: stock 60 fps about 3x stock 20; with the hold, equal to stock 20 (the
same shape as the `aifire_*` runs, ai.md 138-147, n = 2).

### P3. AI avoidance prediction horizon pinned to 50 ms (gameplay-ish; static reading, measure)

Five sites in the same chain, all with single callers inside 0x41b270 (0x43a560 <- 0x41b2e5 only; 0x41a530 <-
0x41b3e5 only; 0x41a040 <- 0x41b62b only; the terrain probe 0x419930 reads no clock and is shared with 0x419ef6 and
0x41d4cd, so it is left alone). The pins reuse `ai_dt20` (1010) and `ai_rate20` (1006), so the prediction, the
velocity derived from it (displacement x rate x 50 x gear, 0x41b5b0-0x41b5f5) and the probes' sweeps stay mutually
consistent at 50 ms, as they are at stock 20 fps.

| site | old bytes | call | function |
|---|---|---|---|
| 0x43a562 | `E8 39 22 06 00` | `simclock_GetSimDt` | `physics_PredictVehicleMotion` 0x43a560: the horizon |
| 0x41b58f | `E8 1C 12 08 00` | `simclock_GetSimRate` | 0x41b270: the rate compared against 10000 (0x4bc9a8) |
| 0x41b5ab | `E8 00 12 08 00` | `simclock_GetSimRate` | 0x41b270: the rate used |
| 0x41a54e | `E8 4D 22 08 00` | `simclock_GetSimDt` | car probe 0x41a530: its sweep dt |
| 0x41a047 | `E8 54 27 08 00` | `simclock_GetSimDt` | static-collider probe 0x41a040: its sweep dt |

```c
/* AI avoidance horizon (ai_TestControlCandidate 0x41b270, ai.md 34-39). Each candidate control pair is tested by
 * predicting ONE FRAME of motion (physics_PredictVehicleMotion 0x43a560 reads sim_dt at 0x43a562) and probing
 * terrain (0x419930) at the predicted pose, then sweeping cars (0x41a530) and static colliders (0x41a040) by a
 * velocity rebuilt from that displacement x sim_rate x 50 x gear (0x41b58f / 0x41b5ab, 0x41b5b0-0x41b5f5) over
 * their own sim_dt (0x41a54e, 0x41a047). The sweep lengths cancel; the horizon does not: 50 ms at 20 fps, 16.7 at
 * 60, 8.3 at 120. All five reads get the 20 fps values, so the AI looks 50 ms ahead at any rate. */
/* in apply_framerate_fixes, the cs[] table: */
/*  { 0x0043a562, 0x0049c7a0, (void *)ai_dt20,   "AI avoidance prediction dt" },   */
/*  { 0x0041b58f, 0x0049c7b0, (void *)ai_rate20, "AI avoidance rate (cap test)" }, */
/*  { 0x0041b5ab, 0x0049c7b0, (void *)ai_rate20, "AI avoidance rate" },            */
/*  { 0x0041a54e, 0x0049c7a0, (void *)ai_dt20,   "AI car probe dt" },              */
/*  { 0x0041a047, 0x0049c7a0, (void *)ai_dt20,   "AI collider probe dt" },         */
```

Caveat, stated plainly: this is a static reading of a function the map calls "per-call (rand gate)"; the horizon
effect has not been measured. Acceptance: AI-car collision events per minute (the telemetry `tel_coll_hook` events,
2220-2232, filtered to AI sources) on a fixed follow route (TRIP mission 1 "keep up with Taurus", or t02 with the
AI on a race path) at 20, 60 and 120 fps, n = 2 each, before and after. If 60 and 20 already agree before the patch,
drop it.

### P4. Far-vehicle path: stock whole-frame dt for the engine update (sim correctness; cheap)

One site, the sole caller of `physics_StepVehicleFar` 0x43a3c0: 0x46384e `E8 6D 6B FD FF` in `entity_TickVehicle`
0x463800 (two dword args: `push edi; push esi` 0x46384c-0x46384d, `add esp,8` after; result unused).

```c
/* Far vehicles (physics.md "Far vehicles"): beyond the camera far radius + 25 m, entity_TickVehicle takes one
 * whole-frame kinematic step, physics_StepVehicleFar 0x43a3c0, which calls physics_UpdateEngine 0x46a320 once per
 * frame (0x43a548). There the stock whole-frame dt read at 0x46a333 is already right (one application per frame),
 * but I76_ENGINE_DT_FIX repoints that read at engine_substep_dt: 2 x dt (no fixed step: 2x the stock far-path
 * convergence at any rate) or 0.05 on every frame (fixed step: 3x at 60 fps, 6x at 120). Flag the far call and hand
 * the engine the stock value inside it. */
static int g_in_far;
static void __cdecl far_step_wrap(DWORD obj, DWORD arg) {
    g_in_far = 1;
    ((void (__cdecl *)(DWORD, DWORD))0x0043a3c0)(obj, arg);
    g_in_far = 0;
}
/* engine_substep_dt (832): first line becomes
 *     if (g_in_far) return *(volatile float *)0x004fe428;      -- simclock_dt, what simclock_GetDt returns  */
/* apply_engine_dt_fix (842): add
 *     static const BYTE far_old[5] = { 0xE8, 0x6D, 0x6B, 0xFD, 0xFF };   -- call 0x43a3c0 at 0x46384e
 *     ... patch_bytes(0x0046384e, far_old, far_new, 5, "far vehicle step call") and log "%d/2 sites" */
```

Acceptance: a far AI car's speed trace (vehicle table 0x54E11C, stride 0x20, `memlib.ps1`) on a straight follow at
60 fps with `I76_ENGINE_DT_FIX=1 I76_FIXED_STEP=24`, before and after, against stock 20; the time to reach cruise
speed from a standing start should match stock 20 after the patch. Without the patch it is ~3x shorter.

### P5. Rear mirror on the 20 Hz grid, with a stock-size cloud step on the mirror pass (cosmetic / render headroom)

Two sites in `renderer_DrawRearMirror` 0x445750:

| site | old bytes | call | what |
|---|---|---|---|
| 0x4457b4 | `E8 17 70 05 00` | `simclock_GetFrameCount` 0x49c7d0 (`mov eax,[0x5a7e1c]; ret`) | the refresh gate: `cmp eax,[0x52bbc8]; jl skip; add eax,2; mov [0x52bbc8],eax` (0x4457b9-0x4457c8); 0x52bbc8 is also written at 0x44538d (`mov [0x52bbc8], 0`, a reset in 0x445380), not read elsewhere |
| 0x4459a1 | `E8 5A F8 FB FF` | `renderer_DrawClouds` 0x405200 (args: cam 0x608c80, colour 0xef) | the level-2 mirror's cloud draw, one of three callers (main passes 0x401e6c / 0x402128) |

```c
/* Rear mirror (renderer_DrawRearMirror 0x445750, framerate.md row 7): redraws when frame_count >= next, next =
 * frame + 2, i.e. every 2nd frame - 10/s at stock 20, 30/s at 60, 60/s at 120, and at mirror level 2 each redraw is
 * a full scene (terrain, roads, flamers, objects, tracers, puffs, clouds, bucket flush, 0x445933-0x4459b4). On the
 * 20 Hz grid count the same gate gives every 2nd grid tick = 10/s at any rate, as stock. The cloud scroll (sites
 * 0x405461/0x405484, rescaled per call to dt x 20) is also advanced by the mirror's own 0x405200 call: stock is
 * 20 main + 10 mirror steps/s = 30/s, and with the mirror at 10/s each mirror call must step the stock 1.0, not the
 * rescaled dt x 20, to keep the measured 0.0300 /s (capture 014). The wrapper sets the stock step for the mirror
 * call and restores the per-frame value after. */
static int __cdecl mirror_frame_count(void) { return g_ratefix ? (int)g_tick20_n : *(volatile int *)0x005a7e1c; }
static void __cdecl mirror_clouds_wrap(void *cam, DWORD colour) {
    float u = g_cloud_u, v = g_cloud_v;
    g_cloud_u = 1.0f; g_cloud_v = -1.0f;
    ((void (__cdecl *)(void *, DWORD))0x00405200)(cam, colour);
    g_cloud_u = u; g_cloud_v = v;
}
/* in apply_framerate_fixes, the cs[] table: */
/*  { 0x004457b4, 0x0049c7d0, (void *)mirror_frame_count, "rear mirror refresh gate" }, */
/*  { 0x004459a1, 0x00405200, (void *)mirror_clouds_wrap,  "rear mirror cloud step" },  */
```

Note the mirror pass's flamer update call 0x445968 (level 2) / 0x4458fe (level 1) stays unwrapped on purpose
(2.7). Acceptance: `sky-motion.ps1` cloud px/s at 60 fps in the cockpit with the mirror at level 2, before and after,
equal to the stock-20 value within the capture-014 spread; and the mirror image visibly steps at 10 Hz (a counter on
the wrapper confirms 10 redraws/s). If James prefers a smoother mirror at high rates, `g_tick20_n` can be replaced by
a 60 Hz grid count at the cost of the cloud invariance (the wrapper would then need a 1/3 step) - the stock look is
the default here, as for every other site.

### Not proposed, and why

- `ai_FrameTick` sweep box 50/dt (U6): candidates only; a 2-site `ai_rate20` pin if 120 fps profiling shows the
  broad phase in the sampler.
- Renderer cache (U7): neutral.
- Head-look mode 2 (U8): no site exists.
- 0x4354c0 / 0x435830 / 0x435cc0: cancel.
- Script VM: neutral by audit; a custom mission that counts passes would need its own fix.

## 6. Summary for the backlog row

- 51 proxy sites cover every row framerate.md marks as a real dependency except the rear mirror (row 7), plus every
  MEASUREMENTS section-4 item (1-4 fixed by mechanism; 5 was never fps-dependent at stock).
- Five uncovered rows with any gameplay weight, all unmeasured: the collision sweep window under the fixed step (U1,
  the largest), the AI dodge gate (U2), the AI avoidance horizon (U3), the far-vehicle engine dt the proxy itself
  introduced (U4), and the mirror cadence (U5, cosmetic/perf). Patches P1-P5 above; old bytes verified against the
  pristine image; dt from `simclock_sim_dt` 0x4fe420 / `g_fixed_step` / the 20 Hz grid as stated per patch.
- Four record corrections (section 4): three of FPS-120.md's "unfixed camera keys" are fixed; the mode-2 head-look
  step does not exist in the binary; the renderer cache is wall-time bound; renderer.md's "not yet fixed" is stale.
  The MW2 "tick delta / 4" item is confirmed as not an I'76 site.

## Acceptance results (2026-10-02, sandbox, `i76-uncap-lab\tools\framerate\rate-ab.ps1`)

**P2 AI dodge gate (`I76_AI_FIXES`), measure `dodge`, t01, 20 s windows, n = 2 per condition, A/A first:**

| condition | fps | dodge checks / s | sd | vs A/A |
|---|---|---|---|---|
| fixed set, capped 20 (A/A control) | 20.0 | 2.87 | 0.10 | noise floor |
| fixed set, 60, hold off (`I76_AI_DODGE_HOLD=0`) | 59.9 | 8.90 | 0.36 | +6.0 (3.1x) |
| fixed set, 60, **hold on** | 60.0 | 3.17 | 0.40 | +0.30 (within the run spread) |
| fixed set, 120, hold off | 120.0 | 17.19 | 1.43 | +14.3 (6x) |

The gate rolls 3x / 6x more often at 60 / 120 fps than at 20, and the 20 Hz hold brings it back to the stock
rate. (`dodge_yes` was 0 in every window: no projectiles reached the AI in a 20 s drive; the call rate is the
quantity the patch controls.) Report: lab `captures\rate-ab\dodge\REPORT.md`.

**P5 mirror cadence (`I76_MIRROR_RATE`), measure `mirror`, a01 (car parked), 15 s windows, n = 2 per condition:**
`g_idbg.mirror_draws` = 10.01 / s with the switch (0 counted without it: the counter lives in the wrapper), so the
gate runs at the 20 Hz grid's half rate as designed, on the AiO sandbox exe where stock redraws the mirror every
frame. Sky drift (`sky-motion.ps1`) read 0.8 px/s in every condition except one stock-60 run at 0.0 (its quantum is
0.8 px/s with the car parked, so this only says the switch did not change it); cloud offsets drifted < 0.02 / s in
all conditions. Report: lab `captures\rate-ab\mirror\REPORT.md`.

**P1 collision window (`I76_COLL_WINDOW`), measure `cactus`, a01: not measured.** All 10 runs were excluded with
"gauntlet aborted: control or steer calibration" - `cactus-gauntlet.ps1`'s control acquisition does not work on the
direct-boot a01 the driver uses (it was written for the menu route into TRAINING). The switch applies (3/3 sites)
and the game ran; the measurement needs the gauntlet ported to the direct boot before P1 can be accepted.
