# I'76 telemetry export (`I76_TELEMETRY`)

> **Verified live 2026-10-01 (sandbox, i76.exe, t01):** 1,067 of 1,067 frames decoded with the player present, frame counter monotonic, gear / rpm / ammo / weapon name matching the live tables; a 3-second burst produced SHOT events whose `ammo left` stepped 699, 698, ... in lock with the weapon instance table, one IMPACT and one EXPLOSION (`X1_BULC1`, 8 m) - see `verification-2026-10-01.txt`. The telemetry stops while the game is outside its play loop (menus, mission over); that is by design. The rest of this file is the static reading it was written from.
> through the i76-map specs, compiled and size-checked but never run against the game. Field sources are cited so a
> live check can go straight to the instruction when a value looks wrong. First checks to make: the frame counter
> advances by 1 per datagram, `speed` matches the HUD, `gear` steps 1 -> 2 -> 3 -> 4 as `engine.md` says, one `SHOT`
> event per trigger pull with `ammo left` falling by `count`, an `IMPACT` with `PLAYER` on a wall hit.

The Strlkup proxy (`music-fix/strlkproxy.c`, section "TELEMETRY EXPORT") publishes the player's state once per
rendered frame, plus an event stream, so FFB / motion / logging tools stop scanning process memory
(`docs/FFB-DATA-AUDIT.md` section 4.2 and row 8 of section 6). Three files:

| file | role |
|---|---|
| `i76tel.h` | the layout: `i76tel_frame_t`, `i76tel_event_t`, `i76tel_shm_t`, constants. The proxy `#include`s it; `i76tel.py` parses it at start-up. One source, nothing to keep in sync by hand |
| `i76tel.py` | listener: UDP or shared memory, status line, events, CSV, `--check`, and the `--layout` table generator for this README |
| `music-fix/strlkproxy.c` | the writer (`apply_telemetry`, `tel_frame`, the three event hooks) |

## Enabling

```
set I76_TELEMETRY=1        # UDP to 127.0.0.1:7676 + shared memory Local\I76Telemetry
set I76_TELEMETRY=7700     # any port 1..65535
set I76MUSIC_LOG=1         # mciproxy.log gets the hook count line:
                           #   telemetry: on - udp 127.0.0.1:7676 open, shm Local\I76Telemetry mapped, 4/4 event hooks ...
```

Unset (the default) nothing is patched and nothing is loaded: the feature costs zero. Set, the proxy installs the
shared frame hook at 0x4039b8 (the same `call simclock_Update` site the fps cap, hires clock and frame-rate fixes
use), repoints two call sites and detours two function entries (below), loads `ws2_32.dll` by hand and creates the
mapping. Works alongside every other `I76_*` option; it reads the fixed-step accumulator when `I76_FIXED_STEP` is on
so `step_count` is exact there.

Test on the sandbox copy, not the daily-driver install (`docs/FFB-DATA-AUDIT.md` section 6).

## What is published, and when

**When.** At the top of the frame hook, i.e. the first instruction of frame N+1 of WinMain's loop, before
`simclock_Update` advances the counters. At that point frame N is complete: input, every object's tick (physics
substeps), the post-ticks (`ffb_WriteSimState` among them), the script VM, the camera, the render and the Flip
(`i76-map subsystems/framerate.md`). So the struct describes the frame that was just shown, with the physics pose
(`I76_RENDER_INTERP` restores it after the render call), and it goes out before any `I76_FPS_CAP` wait. The audit's
two candidate points were not used because both are conditional: `call 0x446110` at 0x445e83 runs only while
0x52bbd0 == 1 (a wheel driver or the shim present), and `render_wrap` exists only under `I76_RENDER_INTERP`.

**UDP.** One datagram per rendered frame: `i76tel_frame_t` (608 bytes) followed by `event_count` x `i76tel_event_t`
(36 bytes each), the events recorded since the previous datagram. At most 64 events fit; if more happened in one
frame the oldest are dropped and the reader sees a gap in `event.seq`. Maximum datagram 608 + 64 x 36 = 2912 bytes.

**Shared memory.** `Local\I76Telemetry`, 2920 bytes = `i76tel_shm_t`: `seq`, `size`, the same frame struct
(`event_count` = 0 there), then the whole 64-entry ring with `ring[event.seq % 64]`. The writer sets `seq` odd before
writing and even after; a reader copies the block, re-reads `seq`, and accepts the copy only if `seq` is even and
unchanged. New events are those with `event.seq` in `(last seen, frame.event_seq]`. Whoever maps the section first
creates it; the proxy zeroes it when it maps, and a reader must treat `seq == 0` or `magic != 'I76T'` as "nothing
published yet".

**Player chain.** `[0x54a264]` -> record -> `[+0]` object -> `[obj+0x70]` entity, accepted only while object flag
0x10 (local player, `object_IsPlayer` 0x458bf0's test) is set. Components come from `ent+0x3a8 + 4 x slot` and are
read only when the slot object's class (`+0x6c`) is the expected one: engine 21, suspension 23, brakes 22, wheels 30.
The snapshot runs under SEH; a stale record between missions costs one frame (`player_present` = 0), not the game.

## Events

| type | hook | how | payload |
|---|---|---|---|
| 1 `SHOT` | `weapon_FireShot` 0x4a6e90 (instance, weapdef, count, dt_left) | the two call sites 0x4a6b16 / 0x4a6d43 in `weapon_UpdateInstanceFiring` 0x4a6470 repointed (verify-bytes-first `patch_bytes`, as the frame-rate fixes do); player only (instance+0x18 -> vehicle weapon record -> +0 vehicle, `object_IsPlayer`) | `f` = {HUD row (inst+0x1c), ammo left after the shot (inst+0x20), damage per hit (inst+0x10), dt_left}; `i` = {weapdef index (inst+0x30), rounds in this call}. MG / handgun rounds are batched into one call per frame (`weapons.md` 3) |
| 2 `EXPLOSION` | `entity_SpawnExplosion` 0x49ead0 (name lo, name hi, p3, x, y, z, owner) | 21 call sites in 14 functions, so the entry is detoured like `cam_set_hook` does 0x472990: the 8 prologue bytes `mov eax,[esp+4]; mov ecx,[esp+8]` run in a trampoline; every explosion in the world, any owner | `f` = {x, y, z, distance to the player, -1 without one}; `i` = the 8-byte template name as two dwords (`struct.pack('<ii')` gives the bytes; the exe upper-cases its own copy, so case follows the caller) |
| 3 `IMPACT` | `physics_ApplyCollisionDamage` 0x4a7c80 (target, source, normal, impact vector, direction) | 7 call sites, entry detoured (6 bytes `sub esp, 0xd0`); every damaging contact on any object | `f` = {impact vector x, y, z, hp the **player** lost in the call}; `i` = {target is the player, source class: 0 terrain / none, 1 car, 0x33 ordnance, 0x34 explosion}. The amount is measured as armour + chassis + engine / suspension / brake / wheel hp before minus after, because the exe's own figure is computed inside and reaches the FFB lists only while 0x52bbd0 == 1 (and a node lives one frame) |

`event.frame` is the proxy frame counter (`frame.proxy_frame`) of the frame the event happened in.

## How FFB and motion tools consume it

- **Read the struct, not the process.** `Telemetry.ps1`'s `ReadProcessMemory` chain, `Tel-DetectShift`, the
  `|vy| > 2` airborne guess and the velocity-delta tick detector all have direct fields: `gear` (eng+8), `flags & 4`
  (airborne), `flags & 2` / `0x2000` / `0x400` (skid, grip limit, oil), `sim_dt` / `step_count` for the time base.
  A PowerShell loop maps the section once (`MemoryMappedFile.OpenExisting("Local\I76Telemetry")`), no `OpenProcess`.
- **Orientation.** `rot` is the object's 3x3, rows right / up / forward, row-vector convention (world = local x R + T):
  pitch = asin(rot[7]), roll = asin(rot[1]), heading = atan2(rot[6], rot[8]). OutSim's zeroed pitch / roll / position
  can be filled from `rot` and `pos`.
- **Motion bus.** Surge / sway / heave without differentiating: `accel_body` (the exe's own body-frame rotation of
  `accel`, valid while `ffb_present`), or rotate `accel` by `rot` yourself. Body rates `pitch_rate` / `yaw_rate` /
  `roll_rate` are real but snapped to 0 at rest by the contact model (`physics.md`), so they are a rest / contact square
  wave at stock steps: use them for transients, not texture.
- **Engine bed.** `rpm` is the float the tachometer uses (850..7000; stock geared revs pass 6000 before the limiter), at
  the frame rate; the LFE smoother glides between frames. `gear` edges replace the rpm-rate detector; `ffb_gear_changed`
  is the exe's own edge but is only written while `ffb_present` and its clearing is not yet read live.
- **Transients from events, not sounds.** `SHOT` x damage per hit sizes the kick; `EXPLOSION` with `f[3]` gives a blast
  scaled by distance (the block cannot: explosions reach it only as damage on the player); `IMPACT` gives direction
  from the impact vector and the amount actually lost; a landing is the falling edge of `flags & 4` with `velocity[1]`
  from the previous frame; a blowout is a wheel's `flat` rising edge.
- **Tyre state.** `wheel[i].grip` gives the live lateral cap 7.84 x sum(grip) (0x4bd1e0) instead of a fitted constant;
  `susp_offset` is the per-wheel suspension travel; the mid pair (slots 2, 3) is often `present` = 0.
- **Damage.** `armour` / `chassis` per side (front, left, right, back) with their maxes, component hp. Offline the
  player's component hp is x4 and armour x2 of the .vcf (`damage.md`), so compare ratios.

## Listener

```
python i76tel.py                     # UDP 7676, 5 Hz status line, every event
python i76tel.py --port 7700
python i76tel.py --shm               # the shared-memory path
python i76tel.py --csv run.csv       # all 149 flattened fields per frame; events to run.events.csv
python i76tel.py --check             # magic / version / size, seq and frame-counter continuity, event seq gaps
python i76tel.py --layout            # the table below
python i76tel.py --layout --readme README.md
```

Status line flags: `E` engine running, `S` skid, `A` airborne, `s` starting, `D` destroyed, `O` oil, `N` nitrous,
`G` grip limit, `K` critical kill, `W` wreck.

## Struct layout

Generated from `i76tel.h` by `python i76tel.py --layout --readme README.md`; the listener builds its `struct` format
from the same parse, so a mismatch between this table and the wire means the generator was not re-run, never that the
header and the proxy disagree (the proxy includes the header). Offsets are bytes from the start of each struct;
everything is little-endian and naturally aligned.

<!-- layout:begin -->
<!-- generated by `python i76tel.py --layout --readme README.md` from i76tel.h; do not edit by hand -->

### `i76tel_wheel_t` (36 bytes)

| offset | size | type | field | source / meaning |
|---:|---:|---|---|---|
| 0 | 4 | `int32_t` | `present` | 1 when the slot holds a type-30 object (the mid pair is often absent) |
| 4 | 4 | `int32_t` | `hp` | wheel+0x04 |
| 8 | 4 | `int32_t` | `hp_max` | wheel+0x08 |
| 12 | 4 | `float` | `grip` | wheel+0x0c: max(hp/max x base, 0.5) after any hit; lateral cap = 7.84 x sum (0x4bd1e0) |
| 16 | 4 | `float` | `ground_speed` | wheel+0x20 signed, the spin animation's speed |
| 20 | 4 | `float` | `susp_offset` | wheel+0x24 filtered suspension offset, +-0.25 r |
| 24 | 4 | `int32_t` | `unloaded` | wheel+0x40 off the ground (suppresses skid marks) |
| 28 | 4 | `int32_t` | `flat` | wheel+0x44 flat tyre |
| 32 | 4 | `int32_t` | `skid_active` | wheel+0x48 |

### `i76tel_event_t` (36 bytes)

| offset | size | type | field | source / meaning |
|---:|---:|---|---|---|
| 0 | 4 | `uint32_t` | `seq` | 1, 2, 3 ... over the whole session; a gap in a stream means the ring wrapped before a send |
| 4 | 4 | `uint32_t` | `frame` | proxy frame counter the event happened in (= i76tel_frame_t.proxy_frame of the frame that carries it) |
| 8 | 4 | `uint32_t` | `type` | I76TEL_EV_* |
| 12 | 16 | `float[4]` | `f` | per type, see the I76TEL_EV_* comments |
| 28 | 8 | `int32_t[2]` | `i` |  |

### `i76tel_frame_t` (608 bytes)

| offset | size | type | field | source / meaning |
|---:|---:|---|---|---|
| 0 | 4 | `uint32_t` | `magic` | I76TEL_MAGIC |
| 4 | 2 | `uint16_t` | `version` | I76TEL_VERSION |
| 6 | 2 | `uint16_t` | `size` | sizeof(i76tel_frame_t) |
| 8 | 4 | `uint32_t` | `seq` | publish counter, 1 per rendered frame |
| 12 | 4 | `uint32_t` | `frame` | simclock_frame_count 0x5a7e1c (the frame just completed) |
| 16 | 4 | `uint32_t` | `proxy_frame` | the proxy's own frame counter (g_frame), the one events are stamped with |
| 20 | 4 | `float` | `sim_time` | simclock_time 0x5a7e74, s |
| 24 | 4 | `float` | `sim_dt` | simclock_sim_dt 0x4fe420, the frame's physics dt, s |
| 28 | 4 | `float` | `dt` | simclock_dt 0x4fe428, the clamped frame dt, s |
| 32 | 4 | `int32_t` | `step_count` | physics substeps the player's tick ran this frame (fixed-step accumulator under I76_FIXED_STEP, else floor(sim_dt x 20) + 1 capped at 20); -1 unknown |
| 36 | 4 | `uint32_t` | `player_present` | 1 when [[0x54a264]] is a live local-player object with an entity; every field below is 0 otherwise |
| 40 | 4 | `uint32_t` | `obj_addr` | the player object (I76_Object*), for scanners that want to read on |
| 44 | 4 | `uint32_t` | `ent_addr` | its entity (obj+0x70, I76_Entity*) |
| 48 | 24 | `double[3]` | `pos` | obj+0x40 world position x, y (up), z |
| 72 | 36 | `float[9]` | `rot` | obj+0x18 rotation, rows right / up / forward (row vectors: world = local x R + T). pitch = asin(rot[7]), roll = asin(rot[1]), heading = atan2(rot[6], rot[8]) |
| 108 | 12 | `float[3]` | `velocity` | ent+0xbc world velocity, m/s |
| 120 | 4 | `float` | `speed` | ent+0xac \|velocity\|, m/s |
| 124 | 4 | `float` | `pitch_rate` | ent+0xc8 body frame, rad/s (snapped to 0 at rest by the contact model) |
| 128 | 4 | `float` | `yaw_rate` | ent+0xcc |
| 132 | 4 | `float` | `roll_rate` | ent+0xd0 |
| 136 | 12 | `float[3]` | `accel` | ent+0xd4 acceleration out of physics_IntegrateVehicleMotion, world frame, m/s^2 |
| 148 | 12 | `float[3]` | `accel_body` | FFB block 0x4f2418..0x4f2420 = accel rotated into the body frame; written only while ffb_present |
| 160 | 4 | `float` | `steer` | ent+0xe0 steer_applied, -1..1 |
| 164 | 4 | `float` | `throttle` | ent+0xe4 throttle_applied, -1..1; braking is throttle < 0 (there is no separate brake input) |
| 168 | 4 | `float` | `gear_dir` | ent+0xe8 +-1 drive direction |
| 172 | 4 | `int32_t` | `handbrake` | ent+0xf0 |
| 176 | 4 | `int32_t` | `exhaust_brake` | ent+0xf4 (special type 4 active) |
| 180 | 4 | `int32_t` | `gear_lever` | ent+0x104 0 P, 1 R, 2 N, 3 D, 4 "2", 5 "1" |
| 184 | 4 | `int32_t` | `gear` | eng+0x08 0 reverse, 1 idle/neutral, 2/3/4 = 1st/2nd/3rd (eng = [[ent+0x3c4]+0x70]) |
| 188 | 4 | `float` | `rpm` | eng+0x1c, 850..7000 |
| 192 | 4 | `float` | `speedo` | eng+0x24 mph when geared, raw m/s in the free-rev branch (stock bug) - use speed |
| 196 | 4 | `float` | `drive_power` | eng+0x10 |
| 200 | 4 | `int32_t` | `engine_hp` | eng+0x00 |
| 204 | 4 | `int32_t` | `engine_hp_max` | eng+0x04 |
| 208 | 4 | `int32_t` | `susp_hp` | [[ent+0x3c8]+0x70]+0x00 |
| 212 | 4 | `int32_t` | `susp_hp_max` | +0x04 |
| 216 | 4 | `int32_t` | `brake_hp` | [[ent+0x3cc]+0x70]+0x04 |
| 220 | 4 | `int32_t` | `brake_hp_max` | +0x08 |
| 224 | 4 | `float` | `brake_effective` | brake+0x10 = max(hp/max, 0.2) x strength |
| 228 | 4 | `uint32_t` | `flags` | ent+0x454: 0x1 engine running, 0x2 skid, 0x4 airborne, 0x8 starting, 0x20 destroyed, 0x400 oil, 0x800 nitrous, 0x2000 grip limit, 0x4000 critical kill, 0x8000 wreck |
| 232 | 4 | `uint32_t` | `surface` | ent+0x45c surface type (WRLD table index) |
| 236 | 12 | `float[3]` | `ground_normal` | ent+0x460 |
| 248 | 4 | `float` | `clearance` | ent+0x470 probe y - ground height |
| 252 | 4 | `float` | `state_timer` | ent+0x450 |
| 256 | 16 | `int32_t[4]` | `armour` | ent+0x138 front, left, right, back |
| 272 | 16 | `int32_t[4]` | `armour_max` | ent+0x158 |
| 288 | 16 | `int32_t[4]` | `chassis` | ent+0x148 |
| 304 | 16 | `int32_t[4]` | `chassis_max` | ent+0x168 |
| 320 | 216 | `i76tel_wheel_t[6]` | `wheel` | component slots 0..5 |
| 536 | 4 | `int32_t` | `weapon_row` | selected HUD row of the player's weapon record (0x5be4d8 + i x 0x2c8, +4); -1 none |
| 540 | 4 | `int32_t` | `weapon_def` | selected instance +0x30 weapdef index (0x5d88d8 + i x 0xd8); -1 none |
| 544 | 4 | `int32_t` | `weapon_ammo` | selected instance +0x20; 0x0fffffff = unlimited |
| 548 | 4 | `int32_t` | `weapon_hp` | selected instance +0x0c condition |
| 552 | 8 | `char[8]` | `weapon_name` | selected weapon root object name (.gdf), not NUL-terminated when 8 long |
| 560 | 4 | `uint32_t` | `ffb_present` | 0x52bbd0: the exe writes its FFB block 0x4f2328 only while this is 1 (wheel driver present or the shim installed) |
| 564 | 4 | `int32_t` | `ffb_rpm` | 0x4f2334 ftol(rpm) |
| 568 | 4 | `uint32_t` | `ffb_engine_running` | 0x4f2338 = flags & 1 |
| 572 | 4 | `uint32_t` | `ffb_engine_starting` | 0x4f233c = flags bit 3 |
| 576 | 4 | `uint32_t` | `ffb_gear_changed` | 0x4f2340 set to 1 when eng+8 != previous (0x4f2314); whether it is cleared on other frames is not yet read live |
| 580 | 4 | `uint32_t` | `ffb_nitrous` | 0x4f2344 = flags & 0x800 while a special slot is type 2 |
| 584 | 4 | `uint32_t` | `ffb_list_ordnance` | 0x4f2478 impact list head (nodes +0 direction deg, +4 damage); nodes live one frame and are gone by the time this is read: use I76TEL_EV_IMPACT |
| 588 | 4 | `uint32_t` | `ffb_list_concussion` | 0x4f247c |
| 592 | 4 | `uint32_t` | `ffb_list_collision` | 0x4f2484 |
| 596 | 4 | `float` | `ffb_dt` | 0x4f2488 simclock_GetDt copy |
| 600 | 4 | `uint32_t` | `event_seq` | total events recorded so far (the last event's seq) |
| 604 | 4 | `uint32_t` | `event_count` | events appended to this datagram after the struct (0 in shared memory) |

### `i76tel_shm_t` (2920 bytes)

| offset | size | type | field | source / meaning |
|---:|---:|---|---|---|
| 0 | 4 | `uint32_t` | `seq` | odd while the writer is inside, even when the block is consistent: read seq, copy, re-read seq, accept if equal and even |
| 4 | 4 | `uint32_t` | `size` | sizeof(i76tel_shm_t) |
| 8 | 608 | `i76tel_frame_t` | `frame` |  |
| 616 | 2304 | `i76tel_event_t[64]` | `ring` | I76TEL_RING entries, slot = event seq % 64 |

<!-- layout:end -->

## Known limits

- One frame of latency by construction (the struct is published when the next frame starts), nothing is interpolated.
- `IMPACT.f[3]` is a measured hp delta, not the exe's damage record; two hits in one call site cannot be told apart.
- Events from AI vehicles (`IMPACT` with `i[0]` = 0, every `EXPLOSION`) can be frequent in a firefight; the ring keeps
  the newest 64 per frame.
- `ffb_*` fields are copies of the exe's FFB block 0x4f2328 and are only written while `ffb_present` (0x52bbd0) is 1;
  the three list heads are kept for completeness but their nodes are freed before the snapshot runs - use `IMPACT`.
- `speedo` carries the stock bug (m/s in the free-rev branch); `speed` is the one to use.
- The event hooks assume the 2017 Galaxy / 2019 AiO byte patterns at the four sites; any mismatch is logged and that
  hook is skipped (`N/4 event hooks` in the log), the frame struct still publishes.
