# FFB / telemetry data audit against the i76-map specs (2026-10-01)

Read-only audit of the force-feedback and telemetry stack (`tools/ffb/`, `ffb-shim/`, `sound-rumble/`) against
the now-complete reverse-engineering specs in `C:\Users\james\i76-map` (`types/i76.h`, `types/i76_runtime.h`,
`subsystems/engine.md`, `physics.md`, `damage.md`, `weapons.md`, `sound.md`, `camera.md`, `framerate.md`,
`simclock.md`, `symbols/functions.tsv`, `symbols/hookability.tsv`). Nothing was run, nothing under `tools/ffb`
was changed; `FfbMixer.ps1` was read from the working tree (it carries 32/10 uncommitted lines from another
session).

Evidence classes used below, per claim:

- **[live]** measured in a running game by one of the two projects (the spec's captures or the FFB scanners);
- **[static]** a cited instruction in the pristine exe (md5 9a232dcc), from the i76-map specs;
- **[inferred]** follows from static facts but no one has looked at it in game;
- **[proposed]** a change recommendation. Everything in section 6 is proposed.

Short version. The FFB stack was built by behavioural scanning before the engine map existed, and it got the
dynamics fields right. Three things it believes are now known to be wrong (the "wheel contact points" are the
hull box; the entity *does* have an orientation; the engine *does* have a suspension and roll/pitch rates), two
things it searched for and never found are one pointer chase away (gear at `[[ent+0x3c4]+0x70]+8`, and a
gear-changed edge already sits in the block it polls, at `0x4f2340`), and the FFB block it reads for RPM carries
another fourteen fields it ignores (airborne, skid, slide, oil, surface, four flat-tyre flags, body-frame
acceleration, and three impact lists with direction and damage).

---

## 1. What the stack reads today, from where, and how each address was found

### 1.1 `tools/ffb/Telemetry.ps1` (the Windows wheel / shaker path)

Player chain: `[0x54a264]` -> record -> `[rec+0]` = player object -> `[obj+0x70]` = entity (`Tel-Resolve`).
Same chain as `tools/trainer/i76trainer.py` (`Game.player`) and as the spec: `world_root 0x54a264` is the player's
`I76_WorldRecord*`, `+0x00` its `I76_Object*`, `object+0x70` the `I76_Entity*` (`i76_runtime.h` 365-369, `cheats.md`
43) [static, and [live] in both tools]. Note `types/i76.h`'s `I76_WorldCtx` comment ("world_GetRoot returns a ctx
whose +0x70 is the entity") is the misframed v0 reading; `i76_runtime.h` marks it conflict C5. The chain the tools
use is the right one.

One `ReadProcessMemory` of 0x100 bytes from the entity, then three more per poll:

| read | address | how it was found | spec status |
|---|---|---|---|
| speed `float` | ent+0xac | identity `|v| == +0xac` on a slow-rolling car (`Telemetry.ps1` header) [live] | `I76_Entity.speed` +0xac, 0x464387 / 0x43ac0a [static]; m/s. Agrees |
| velocity `float[3]` world | ent+0xbc | behavioural probe (`ffb-telemetry-probe.ps1`) [live] | +0xbc..+0xc4, 0x464372..0x464381 [static]. Agrees |
| angular velocity `float[3]` | ent+0xc8 / +0xcc / +0xd0 | yaw rate at +0xcc fitted to steering at R^2 0.9997 [live]; the other two "are not roll/pitch rate" (correlation test) | +0xc8 pitch (body x), +0xcc yaw, +0xd0 roll, body frame, `0x493e60` axis order (physics.md rows B, A) [static]. See 2.3: they *are* pitch and roll rates; the engine's contact model zeroes them at rest |
| acceleration `float[3]` | ent+0xd4 ("likely, unused") | shape | +0xd4 is the acceleration out of `physics_IntegrateVehicleMotion` 0x43a5d0, "the FFB G-vector" (0x439c4f) [static]. World frame; the FFB block carries the body-frame rotation of it at 0x4f2418 |
| steer, throttle | ent+0xe0, +0xe4 | disassembly of 0x466e30 + parked range | `steer_applied` 0x44f2a2, `throttle_applied` 0x44f290 (`input_ApplyToEntity`) [static]. Agrees |
| "four wheel contact points" | ent+0x04..+0x30 | parked values form a rectangle; wheelbase 4.66 m, track 1.98 m derived | **Wrong.** +0x04..+0x33 are the 4 body **collision hull corners** from the VDF collision box, swept against terrain by 0x440740 (`lea edi,[eax+4]; push 4` at 0x440762/0x440766; physics.md rows B, C) [static]. 4.66 m is the hull length, not the wheelbase. The real wheelbase is `float` ent+0x118 (0x438c64), front track ent+0x114, steer gain ent+0x110 = 1/(2 wb) (0x43cfdb) |
| weapon-fire input bytes | 0x5367db (+0, +3..+7) | `ffb-find-fire.ps1` saw 0x5367d0 and 0x5367de move; corrected 2026-09-27 from `globals.tsv` | `input_weapon_fire` 0x5367db, `input_hardpoint1..5_fire` 0x5367de..e2 (weapons.md, Keys) [static]. Agrees. Only a fallback |
| "GameFfb" | 0x52bbe4 | FFB-DEEP-DIVE | `I7FF_SIM_Effect` pointer (0x4460a3) [static]. The comment above the read still says 0x52bbd0 (the present flag); the code reads the pointer. Cosmetic |
| RPM `int` | 0x4f2334 (block +0x0c) | `ffb-find-rpm-wide.ps1`: whole-process alternating idle/revs scan, read 1050 / 5998 [live] | `I7FF_SimState.logic_val_0c` = `ftol(physics_EngineGetRpm(eng))` at 0x445c86; `physics_EngineGetRpm` 0x46a790 returns `I76_EngineData.rpm` = `[[ent+0x3c4]+0x70]+0x1c` [static]. Agrees; the block is a per-frame integer copy of the float |
| effect slots | 0x4f2358 + 0x1c*i, i<6: +0 active, +0xc id, +0x10 param, +0x14 magnitude | `ffb-watch-effects.ps1` live capture; DLL disassembly (deep dive) | slot 0 active: `mov [ebp+0x4f2358],1` at 0x4a670f in `weapon_UpdateInstanceFiring` 0x4a6470 [static]; id from table 0x4fec80[class*7 + sub%100] (weapons.md, 0x4a5a3f) [static]. Stride 0x1c "proposed" in i76.h. The +0x10 freq-vs-direction dispute is not settled by the specs |
| gear shift | none | "detected without ever finding a gear variable": `Tel-DetectShift` fires on rpm falling > 6000 rpm/s while speed holds | gear exists: see 2.1 |

What it writes: `Tel-SetEngineFfb` zeroes 0x52bbe4 so `ffb_DispatchSimState` 0x446110 skips the call into the stock
DLL (the fault at I7_SFRCE.DLL+0x2505). The block keeps being written because `ffb_WriteSimState` 0x445ba0 gates on
0x52bbd0, not on the pointer [static; the deep dive quotes both]. Correct.

Derived quantities the mixer consumes: LongAccel, world accel, Jolt (|dv|/dt), Slide (yaw rate minus heading
rate), Understeer/Oversteer against the two-regime handling model, HeadingApprox (travel direction), TravelPitch
(vy/|v|), Airborne (`|vy| > 2.0`), Braking (`throttle < -0.05`), SinceTick.

### 1.2 `tools/ffb/FfbMixer.ps1` and `LfeSynth.ps1`

Wheel channels: center (steer x speed), corner (yaw x speed), oversteer, brake (LongG), texture (jolt residual
after subtracting commanded long/lat accel), scrub, judder, impact (jolt edge > 5.6 m/s^2), weapon (effect-slot
edge, scaled by slot magnitude), shift (`Sample.Shift`). LFE bus: engine frequency from `Sample.Rpm` (1050..6000
-> 26..38 Hz), road from the same residual roughness, impact, weapon, heave (d(vy)/dt), scrub, explosion (slot
magnitude >= 40). Nothing in the mixer reads a game flag; every state is inferred from the dynamics.

### 1.3 `ffb-shim/i7ffshim.c` (the in-process replacement for i7_SFRCE.DLL)

Receives the block as the call argument of `I7FF_SIM_Effect` every frame; reads engine_pitch (+0xc), engine
running (+0x10), engine starting (+0x14), weapon UI one-shots (+0x24/28/2c), six hardpoint records, force vector
(+0xf0..+0xf8), "steer_right/left" (+0xfc/+0x100), speed mph (+0x104), four tyre words (+0x108..), airborne /
skidding / sliding / oilslick (+0x128/+0x130/+0x138/+0x140), surface+1 (+0x148), the three impact lists
(+0x150/+0x154/+0x15c) and dt (+0x160). Layout from FFB-DEEP-DIVE (static DLL + exe disassembly, 2026-07-19),
run live on the Mac 2026-07-19/20. It is the most complete consumer of the block in the repo, and the Windows
mixer uses almost none of what it uses.

### 1.4 `sound-rumble/dsndrumble.c`

A dsound.dll proxy: fingerprints the PCM written on `Unlock`, maps it to a .gpw name, drives pad motors from the
name's amplitude envelope. Never run against the live game (its own header). It sees names, not game events,
and only for sounds that reach DirectSound.

### 1.5 `tools/ffb/ffb-telemetry-udp.ps1`

LFS OutSim / OutGauge emitter. Sends velocity, world acceleration, yaw rate, speed, pedals; heading from the
travel direction; **pitch, roll, position, RPM, gear hard-coded to zero** "because the engine exposes no
orientation / no RPM exists" (its header, lines 57-63, 144-145, 167-169, 205-208). All four are now readable
(section 2).

---

## 2. Which of these are known exactly now: pointer chains from the player object

Let `obj = [[0x54a264]]`, `ent = [obj+0x70]`, `eng = [[ent+0x3c4]+0x70]` (component slot 7, type 21),
`wheel_i = [[ent+0x3a8+4*i]+0x70]` (slots 0/1 front, 2/3 mid (may be null), 4/5 rear; type 30).

### 2.1 Gear, RPM, speed, lever

| quantity | address | type / values | evidence |
|---|---|---|---|
| gear | `eng+0x08` | int: 0 reverse, 1 idle/neutral, 2/3/4 = 1st/2nd/3rd | `mov [edi+8],eax` 0x46a543 [static]; shifts 2->3 at ~60 km/h, 3->4 at 104-105 km/h observed in sandbox Melee (engine.md Live check, 70 samples) [live] |
| rpm | `eng+0x1c` | float; 850 + 126.81 x R[g] x v geared (R = 3.0/-/1.67/0.96/0.67 at 0x4f8640), 1050 idle, free-rev toward 1050 + 4950 x throttle capped 6000, limiter at 7000 | `fstp [edi+0x1c]` 0x46a772 [static]; formula matched 61/61 grounded samples [live] |
| rpm (int copy) | 0x4f2334 | written once per rendered frame by 0x445ba0 | 0x445c86 [static]; 1050/5998 [live]. Only while 0x52bbd0 == 1 (wheel present or shim installed) |
| speedo | `eng+0x24` | float mph when geared; **raw m/s in the free-rev branch** (airborne / skidding / P-N) | 0x46a705..0x46a75a [static]; 33.3 m/s -> 74.5 mph grounded, 26.3 m/s -> 23.3 airborne [live]. Block +0x104 is `min(this, 165)`. Do not use for speed; use ent+0xac |
| speed | `ent+0xac` | float m/s = \|velocity\| | as the mixer already does [live] |
| lever | `ent+0x104` | int 0 P, 1 R, 2 N, 3 D, 4 "2", 5 "1" | 0x467367 [static]; the HUD gear draw 0x45ad40 plays VSHIF1A.WAV on a lever change (camera.md) |
| gear-changed edge | 0x4f2340 (block +0x18) | `mov dword [0x4f2340],1` when `[eng+8] != [0x4f2314]` | 0x445c97 [static]. i76.h's "logic" in this comment is the engine data block, so `[logic+8]` is the gear. The deep dive read it as "engine object changed"; it is **the gear changing**, and 0x4f2314 (init -1 at 0x445afe) is the previous gear. Whether the exe writes 0 on other frames is not cited: read 0x4f2340 and 0x4f2314 live before relying on the edge; `eng+8` itself needs no such caveat |

So the README's "no gear variable was ever found" is answered: `[[[[[0x54a264]]+0x70]+0x3c4]+0x70]+8`. Four
pointer reads, all in heap memory already resolved per mission. `Tel-DetectShift`'s thresholds (6000 / 9000 rpm/s,
never field-tested) can go.

An [inferred] hazard of keeping the rpm-rate detector: in the free-rev branch the rpm eases toward
1050 + 4950 x throttle at 2 x dt per substep. Lifting off while airborne (speed held, so the "speed does not
fall" test passes) starts a drop of (6000 - 1050) x 2 = 9900 rpm/s, above `DropRate` 6000: a false UPSHIFT on
every lift-off in the air. A real 1st->2nd at 17 m/s drops 4492 -> 2944 rpm in one substep (>= 31000 rpm/s), so
the real events are fine; the false one is the problem.

### 2.2 Flags, surface, ground

| quantity | address | bits / values | evidence |
|---|---|---|---|
| entity flags | `ent+0x454` | 0x1 engine running; 0x2 tyres skidding; 0x4 airborne; 0x8 engine starting; 0x10 body-terrain contact latched; 0x20 destroyed; 0x40 lights; 0x100 damage-smoke emitter; 0x200 skip angular impulse; 0x400 oil slick (traction loss, 2 s); 0x800 nitrous (x5 drive, 15 s); 0x1000 side-slip friction mode (always set); 0x2000 lateral force at the grip limit ("sliding"); 0x4000 critical kill; 0x8000 wreck; 0x10000 arcade/Taurus; 0x20000 came back into range; 0x40000 radar jammer; 0x80000 unknown; bit 31 state timer running | i76.h `I76_EntityFlags`; physics.md row B (0x43d140, 0x439c98, 0x43901e, 0x4396ae); sound.md tyre loops (0x43d530 airborne, 0x43d539 bit 2, 0x43b50c bit 0x2000); engine.md specials; damage.md [static]. Live: player at rest reads 0x81001 [live] |
| the same four in the block | 0x4f2450 airborne (bit 2 = 0x4), 0x4f2458 skid (0x2), 0x4f2460 slide (0x2000), 0x4f2468 oil (0x400) | nonzero / 0 | 0x445dfb, 0x445e0a, 0x445e1b, 0x445e2d [static] |
| surface type | `ent+0x45c` | index into the WRLD surface table 0x644220 (stride 20: +0 grip, +4 drag, +8 bump amplitude, +0x10 damage rate) and into the tyre-sound table 0x4bd0d0 | 0x43a08d; 0x43d240 / 0x492780 / 0x46dc8e [static]. Block 0x4f2470 = this + 1, or 0 when the speedo reads <= 0 (0x445d2c) |
| ground normal | `ent+0x460..+0x468` | float[3]; `ent+0x46c` = 9.8 x n.y^3 | 0x43a080, 0x43a0cf [static] |
| clearance / last ground height | `ent+0x470`, `ent+0x474` | floats | 0x43a78a, 0x43a0e0 [static] |

The mixer's `Airborne = |vy| > 2` can become `flags & 4`, and its loss-of-control detector gains three exact
inputs: skid 0x2, grip-limit 0x2000, oil 0x400.

### 2.3 Orientation, position, body rates

| quantity | address | evidence |
|---|---|---|
| rotation 3x3 float, rows right / up / forward | `obj+0x18` / `+0x24` / `+0x30` | `I76_Transform` (i76_runtime.h 60-71); physics.md Conventions, 0x43aacd / 0x43ab5a / 0x43bbd1 [static] |
| position double[3] | `obj+0x40` / `+0x48` / `+0x50` | the trainer reads and writes it (`cmd_status`, `cmd_teleport`) [live] |
| pitch rate / yaw rate / roll rate, body frame | `ent+0xc8` / `+0xcc` / `+0xd0` | physics.md rows A, B (0x43b92d yaw, 0x43a808 pitch, roll by elimination; clamps pi/2, pi, pi/4 at 0x4bd170..) [static] |
| per-wheel suspension | `wheel_i+0x24` filtered offset (+-0.25 r), `+0x40` unloaded, `+0x44` flat, `+0x20` ground speed, `+0x2c` terrain height | `I76_WheelData`; 0x46dd4c, 0x46dcfb, 0x46dc9b [static] |

Three statements in the stack are therefore out of date:

1. "The engine exposes no orientation" (`Telemetry.ps1`, `ffb-telemetry-udp.ps1`, README). It is at `obj+0x18`.
   OutSim heading = atan2(forward.x, forward.z), pitch = asin(forward.y), roll = asin(right.y) (the proxy's own
   debug ring uses r[1] and r[7] exactly so). The MOTION-SIM note "entity transform at entity+0x08" is also wrong:
   the transform is on the object, not the entity.
2. "I'76 has no suspension model; +0xc8/+0xd0 are not roll/pitch rates." There is a per-wheel second-order IIR
   suspension (0x46dc10, poles 0.7, 15-call period, travel +-0.25 r) and the two rates are the body's pitch and
   roll rates. What the correlation test saw is the contact model: `physics_ResolveGroundContact` 0x437230 snaps
   both rates to exactly 0 when the velocity-against-normal test passes, so at stock steps the body is "at rest"
   on 62% of frames (framerate.md, capture 014) [live]. The conclusion "do not drive road texture from them" still
   holds; the reason is different.
3. "The 4.66 m wheelbase." It is the hull box (2.1). The handling fit absorbed it: the kinematic branch
   `(v/4.662) tan(0.76 steer)` ~ `0.204 v steer`, and the exe's is `steer x v / (2 wb)` (0x43cfdb) -> wb ~ 2.45 m
   if the fit is exact [inferred; read `ent+0x118` once to check]. The lateral branch `31.0 |steer| / v` matches
   the exe's steering cap `7.84 x sum(wheel grip)` = 31.4 m/s^2 with four wheels at grip 1.0 (0x4bd1e0, flag 0x10000
   clear) [static]; the fitted 31.0 is that constant seen from outside. With damaged tyres (grip -> 0.5 floor) the
   cap falls and the reference model will report understeer that is real. `TEL_LAT_GAIN` can be computed live as
   7.84 x sum(wheel_i+0x0c) instead of fitted.

### 2.4 Damage and death

| quantity | address | evidence |
|---|---|---|
| armour per side (0 front, 1 left, 2 right, 3 back) | `ent+0x138[4]` cur, `+0x158[4]` max, `+0x178[4]` HUD copy | 0x4659f7 / 0x4adad1 / 0x463d26 [static]; trainer reads them [live] |
| chassis per side | `ent+0x148[4]`, `+0x168[4]`, `+0x18c[4]` | 0x46591c / 0x4adb2c [static]; [live] |
| engine / suspension / brakes hp | `eng+0` / `[[ent+0x3c8]+0x70]+0` / `[[ent+0x3cc]+0x70]+4` over +4 / +4 / +8 | `COMP_HEALTH` in the trainer; 0x466ac0 [static]; [live] |
| wheel hp, flat | `wheel_i+0x04` / `+0x08`, `+0x44` | [static]; trainer repairs them [live] |
| death | `ent+0x454` bits 0x20 (destroyed), 0x4000 (critical: explosion + 10 s timer), 0x8000 (wreck); `ent+0x450` state timer; `[obj+0x10] & 0x200` dead | damage.md Flow [static] |
| hits on the player as events | FFB block lists 0x4f2478 ordnance / 0x4f247c concussion / 0x4f2484 collision; node +0x00 direction deg (float), +0x04 damage (float) | appended by `physics_ApplyCollisionDamage` 0x4a7c80 (body 0x4a7f24..0x4a81b7) through `ffb_AllocNode` 0x445f70 (deep dive) [static]; float widths [live 2026-07-20] |
| which side / zone a hit landed | `entity_DamageAndKill` 0x463a80 (entity, record): side 0..3 and zone 0..6 from the hit direction | damage.md [static]. A hook on 0x463a80 gives side + amount per hit |

### 2.5 Weapon fire and explosions

| event | source | evidence |
|---|---|---|
| a weapon fired (player or AI) | `weapon_FireShot` 0x4a6e90 (instance, weapdef, count, dt_left); MG / handgun rounds batched into one call per frame | weapons.md 3-4 [static]; hookable (5-byte prologue, hookability.tsv) |
| player trigger decided | `weapon_UpdateInstanceFiring` 0x4a6470 sets slot +0 of the FFB hardpoint record | 0x4a670f [static]; what the mixer reads today [live] |
| weapon cycle / link / unlink | 0x4f234c / 0x4f2350 / 0x4f2354 = 1 (one-shots) | 0x4a5e16 / 0x4a634d / 0x4a602c (deep dive; weapons.md) [static] |
| explosion anywhere in the world | `entity_SpawnExplosion` 0x49ead0 (template, position, ...) from `weapon_SpawnImpactEffect` 0x4a7190, the flame hit 0x44471d, the death block, wreck secondaries | weapons.md 7, damage.md Break-off [static]; hookable (8-byte prologue) |
| explosion damage reaching the player | concussion list 0x4f247c | [static] |

Whether world explosions reach the effect table (READY-TO-TEST A7) is answered statically: they do not. The
hardpoint records are per-hardpoint firing state; explosions reach the block only as damage on the player
(concussion list), and the mixer's `LfeExplodeMag >= 40` channel is keyed on a weapon's own gain value (60 for one
weapon id), i.e. it is a heavy-weapon shot, not a blast.

---

## 3. The FFB block 0x4f2328 field by field: spec vs mixer use

Writer `ffb_WriteSimState` 0x445ba0, called from `entity_VehiclePostTick` 0x463950 (class row +0x10 for type 1),
once per rendered frame after the player's tick (framerate.md step 4); dispatched by `ffb_DispatchSimState`
0x446110. Gated on 0x52bbd0 == 1.

| off | VA | i76.h name (cited store) | meaning | FFB-DEEP-DIVE agrees? | read by Telemetry.ps1 | read by i7ffshim |
|---|---|---|---|---|---|---|
| +0x00 | 0x4f2328 | size (0x446124) | 0x16c | yes | no | validates |
| +0x04 | 0x4f232c | init_4 | reset flag, vestigial | yes | no | no |
| +0x08 | 0x4f2330 | init_8 | forces on/off (0x445b40/60/80) | yes | no | master switch |
| +0x0c | 0x4f2334 | logic_val_0c = ftol(rpm) | **engine rpm** | "engine pitch value" (same thing) | **yes** | yes (as pitch, range comment stale: 850..7000, not 1000..4700) |
| +0x10 | 0x4f2338 | flag bit 0 | engine running | yes | no | yes |
| +0x14 | 0x4f233c | flag bit 3 | engine starting | yes | no | yes |
| +0x18 | 0x4f2340 | logic_8_changed | **gear changed** (eng+8 vs 0x4f2314) | no: "engine object changed" | no | as "engine_changed", unused |
| +0x1c | 0x4f2344 | flag bit 11 when a special slot is type 2 | nitrous active (0x800 = x5 drive, engine.md) | "GUESS: heavy mount" -> it is nitrous | no | as mount_mod2, unused |
| +0x20 | 0x4f2348 | slot_3ec_type3 | a blower is fitted (SPEC type 3) | "mount type 3" -> blower | no | unused |
| +0x24..+0x2c | 0x4f234c.. | undefined in i76.h | weapon cycle / link / unlink one-shots (weapons.md, 0x4a5e16 / 0x4a634d / 0x4a602c) | yes | no | yes |
| +0x30..+0xd7 | 0x4f2358.. | slot 0 active (0x4a670f); rest proposed | 6 hardpoint records, stride 0x1c: +0 firing, +4/+8 misfire flags, +0xc weapon effect id (0x4fec80 table), +0x10 freq-or-direction, +0x14 gain | yes | **yes** (active / id / +0x10 / mag) | yes |
| +0xd8..+0xe0 | 0x4f2400.. | zeroed (0x445d81..) | DLL scratch | yes | no | no |
| +0xe4..+0xec | 0x4f240c.. | [ent+0xbc] x3 | velocity.x copied three times (the three stores all read +0xbc) | yes ("vestigial") | no | no |
| +0xf0..+0xf8 | 0x4f2418.. | accel = math_Mat3MulVec3(ent+0xd4, obj+0x18) | **body-frame acceleration** (surge / heave / sway without differentiating) | yes | no | yes (force_x / y1 / y2) |
| +0xfc, +0x100 | 0x4f2424/8 | throttle_fwd / throttle_rev: [ent+0xe4] > 0.15 / < -0.15 | **throttle direction**, not steering: +0xe4 is `throttle_applied` (0x44f290) | **no**: deep dive says "steering right/left"; the shim's `GameState.steer` is throttle sign | no | yes (mislabelled) |
| +0x104 | 0x4f242c | min(physics_EngineGetSpeedo, 165) | speedo mph, m/s when free-revving (bug) | yes | no | yes |
| +0x108..+0x114 | 0x4f2430.. | physics_WheelIsFlat(slot 0/1/4/5) | four flat-tyre words, FL FR RL RR; DLL threshold 3000 | yes | no | yes |
| +0x118..+0x124 | | undefined | DLL prev | yes | no | no |
| +0x128 | 0x4f2450 | flag & 4 | airborne | yes | no | yes |
| +0x130 | 0x4f2458 | flag & 2 | skidding | yes | no | yes |
| +0x138 | 0x4f2460 | flag & 0x2000 | at the lateral grip limit | yes ("sliding") | no | yes |
| +0x140 | 0x4f2468 | flag & 0x400 | oil slick | yes | no | yes |
| +0x148 | 0x4f2470 | [ent+0x45c] + 1, 0 when stopped | surface type + 1 | yes | no | yes |
| +0x150 / +0x154 / +0x158 / +0x15c | 0x4f2478.. | list heads (nodes +0x18 next, +0x10/+0x14 zero test) | ordnance / concussion / unused / collision impact lists, nodes {dir deg f32, damage f32} on the private heap 0x52bbcc | yes | no | yes |
| +0x160 | 0x4f2488 | simclock_GetDt copy | frame dt (not the substep) | yes | no | yes |
| +0x164, +0x168 | | 0x5dcf3c, [0x5dcf7c] | exe struct ptr, HINSTANCE | yes | no | no |

Unused by the mixer and directly useful: +0x10 (engine running: silence the LFE engine bed when off),
+0x14 (ENGSTART thump), +0x18 (gear edge), +0x1c (nitrous: a sustained bed), +0x24..+0x2c (UI clicks on the
wheel, as the stock WPNCYCLE/WPNLINK effects did), +0xf0..+0xf8 (surge/sway/heave for the motion bus and the brake
channel, replacing the differentiated LongAccel and the sign-guessing), +0x108..+0x114 (tyre blowout jolt, the
stock TIREBLWL/R effects), +0x128..+0x140 (airborne, skid, grip limit, oil), +0x148 (surface for road texture),
the three lists (directional impacts with the game's own damage amount). The block is one 0x16c-byte
`ReadProcessMemory` the mixer already does; the fields are in the buffer.

One caution on the lists while 0x52bbe4 is zeroed: the stock DLL never marks a node started (+0x10/+0x14 stay 0),
so the exe frees every node on the next frame (0x445e88..0x445f66). A node lives one rendered frame. A 62 Hz
poller sees it reliably at 20 fps and often misses it at 60 fps [inferred]. The hook in section 4 avoids this.

---

## 4. Events: what is available, and the cleanest source

### 4.1 Candidates

| source | what it carries | completeness | how to tap |
|---|---|---|---|
| `sound_PlayVehicleEvent` 0x422f20 (int event, obj, params) | 1/2 engine start/stop, 3 horn, 4 vland (player landing, from 0x439eaa), 5 vvcoll, 6 vbcoll, 7 vexplode (death block), 8 vmgun, 9 vmissile, 10/11 skid loop (no caller), 16 vcsign | **incomplete**: the collision sounds (vtcoll 0x438fd0; vvch2 / vvcre2 / vvcbb3 / vnvco3 / vnvcs* from 0x4349c0), tyre loops (`physics_PlayTyreSounds` 0x43d500 by name), weapon fire sounds (`weapon_FireShot` by .gdf name) and the flat / brake-damage sounds all bypass it. Call sites for 5/6/8/9 were not enumerated (the map's xref file is keyed on globals; `functions/` has 120 exports) | hookable, 5-byte prologue |
| `sound_StartObjectSound` 0x421b40 (every voice start or refresh), or the three request fronts 0x423230 / 0x4231f0 / 0x4250f0 | every named sound with its object and position | complete at the name level; loops refresh every frame (keep-alive) so a hook must edge-detect per (name, object) | the proxy already wraps 0x423230 call sites (`frame_sound_wrap`, I76_FRAMERATE_FIXES) |
| `dsound.dll` proxy (sound-rumble) | PCM fingerprint -> name on `Play` | complete for sounds that reach DirectSound, after mixing/culling; no object, no position, no is_player; unverified live | file swap |
| FFB block lists 0x4f2478 / 0x4f247c / 0x4f2484 | hits on the player: direction (deg) + damage, three categories | player-only; one-frame lifetime with the pointer zeroed | memory read or hook |
| `weapon_FireShot` 0x4a6e90 | every shot: instance (-> hardpoint row, weapdef, ammo), count, shooter | complete for guns; flamers go through `weapon_FlameEmit` 0x443c90 | hookable |
| `entity_SpawnExplosion` 0x49ead0 | every explosion with template and world position | complete | hookable (8-byte prologue) |
| `physics_ApplyCollisionDamage` 0x4a7c80 | every impact that does damage, any vehicle, with the impact vector | complete for damaging contacts; the 4 m/s "hard hit" at 0x438fd0 also plays vtcoll | hookable (6-byte prologue) |
| `entity_DamageAndKill` 0x463a80 | hits on an entity resolved to armour side 0..3 and zone 0..6 | complete for entity damage | hookable |

### 4.2 Recommendation [proposed]

For the **LFE synth and the wheel's transient channels**, use structured game events, not sounds: a shot is
`weapon_FireShot` (count x weapdef damage gives the kick size the stock .frc gain approximated), an explosion is
`entity_SpawnExplosion` with distance from `obj+0x40` (a world blast scaled 1/d^2, which the block cannot give), a
hit is the FFB list node or `entity_DamageAndKill` (side gives the kick direction the mixer now guesses from yaw
rate), a landing is the airborne flag's falling edge (0x4f2450 or `flags & 4`) with the vertical velocity before
touchdown, a blowout is the flat word's rising edge. Sounds are the right source only for the things that *are*
sounds: the engine note (eng+0x1c is already exact), horn, CB. The dsound proxy stays the fallback for platforms
where nothing else can be loaded.

For **getting the data out**, a telemetry export in the Strlkup proxy (`music-fix/strlkproxy.c`) is the cleanest
replacement for the memory scanners, and most of the machinery exists:

- it already patches call sites with byte-verified `patch_bytes` (0x463800's class slot at 0x4f7788 for
  render-interp; the frame clock call at 0x4039b8; 36 call sites for the frame-rate fixes), so hooking the type-1
  post-tick slot at **0x4f778c** (row +0x10 = `entity_VehiclePostTick` 0x463950, 38 bytes) or wrapping the
  `call 0x446110` at 0x445e83 puts a snapshot exactly after `ffb_WriteSimState` has filled the block;
- `hookability.tsv` rates 0x4a6e90, 0x49ead0, 0x4a7c80, 0x422f20, 0x43d500, 0x463950, 0x446110 all `yes` with
  5-8 byte prologues for an entry detour of the render-interp kind;
- the shim already shows the socket pattern (`i7ffshim.c`: `WSAStartup`, `sendto` 127.0.0.1:17676, one datagram per
  tick).

Shape: one struct per frame (frame counter, sim time, dt, substep count from `g_step_acc`, `obj+0x18` transform,
ent +0xac/+0xbc/+0xc8/+0xd4/+0xe0/+0xe4/+0x104/+0x454/+0x45c/+0x460/+0x470, eng +0x08/+0x1c/+0x24/+0, six wheels
+0x04/+0x24/+0x40/+0x44/+0x20, armour/chassis 4+4, and the 0x16c block verbatim) plus an event ring filled by the
detours (kind, sim time, 3-4 operands: shooter/weapon/count, explosion position/template, damage side/amount,
impact vector). Deliver over UDP (SimHub/SimTools style, as both existing wires do) and a named shared-memory
section for the PowerShell loop (one `MapViewOfFile`, no `OpenProcess`, no 0x54a264 re-resolve, no race with the
writer because the frame counter is written last). Gate on `I76_TELEMETRY=1`, log the hook count like every other
option. The 0x52bbe4 crash workaround is orthogonal: it is needed with the stock DLL and must *not* be applied with
the shim DLL (FFB-STACKS already says so).

What this does **not** remove: the scanners remain the right tool for *finding* things. Nothing in this stack
needs them for reading any more.

---

## 5. Frame rate: what the mixer samples against what the physics does

Facts, from simclock.md / framerate.md / physics.md [static, with capture 014 [live] where noted]:

- The engine is dt-driven. `entity_TickVehicle` 0x463800 splits each frame's sim dt into `floor(dt x 20) + 1`
  substeps of at most 50 ms (`simclock_StepperBegin` 0x49cc20). Stock 20 fps on the 15.6 ms GetTickCount grid gives
  46.9 ms (80%) and 31.2 ms steps, about 24/s [live]. There is **no fixed 20 Hz step and no render interpolation**
  in the stock exe; the Telemetry.ps1 header ("fixed 20 Hz, renderer interpolates", citing Peelar/Roanish) is
  wrong for stock and true only with `I76_FIXED_STEP` + `I76_RENDER_INTERP`.
- Velocity (+0xbc), speed, yaw rate and the engine data change once per substep; the FFB block, the input
  fields (+0xe0/+0xe4) and the object transform are updated once per rendered frame (the transform is written by
  the physics per substep too, but see interp below).
- `physics_UpdateEngine` 0x46a320 eases rpm with the **whole-frame** dt inside every substep (0x46a333), so stock
  rpm response is about 2x faster per second at 20 fps than at 60 (`I76_ENGINE_DT_FIX` corrects it). Any rpm-rate
  threshold (`Tel-DetectShift`) is therefore frame-rate dependent in stock; reading `eng+8` is not.
- With `I76_RENDER_INTERP` the proxy swaps the interpolated pose into `obj+0x18` around the render call and
  restores it (strlkproxy.c 1371-1395, 1672-1675; the trainer's teleport writes twice for this reason). An external
  reader of `obj+0x18`/`+0x40` can land on either pose. Entity fields are never touched.

What the mixer does with it:

- `Tel-Sample` detects "a tick" as any change of velocity > 1e-7 and differentiates against the time since the
  last change. In stock that interval is a *frame* (one or two substeps completed inside the tick call; a read
  landing between two substeps of one frame is possible but rare), so LongAccel / Jolt / Slide are per-frame
  averages over 1-2 substeps: correct per second, with the 15.6 ms clock jitter folded in. With `I76_FIXED_STEP=24`
  the interval becomes a clean 41.7 ms (0 or 1 step per 60 fps frame), which is what the header always assumed.
- Jolt's edge detector (`> 5.6 m/s^2`, `ImpactRef x 0.08`) is in m/s^2, so it is step-size independent to first
  order; but the contact impulse itself is applied in one substep and the position advances twice in a contact
  substep (physics.md step 2), so the measured |dv| of a given hit does depend on the step size [inferred].
- The force loop runs at <= 62 Hz (`Start-Sleep` granularity), so every oscillator stays under ~15 Hz. With the
  physics at 24 Hz and the loop at 62 Hz there are 2-3 polls per physics step; the derived values are held between
  steps (by design). Nothing here needs changing for `I76_FIXED_STEP`.
- `SinceTick > 0.5 s` mutes the wheel when the sim is paused. With a fixed step of 41.7 ms the longest legitimate
  gap at any frame rate is one step; the gate is safe.

What to change [proposed]:

1. Read the FFB block's `dt` (0x4f2488) and, under the proxy, the step count, instead of inferring ticks from
   velocity deltas; or take `simclock_sim_time` 0x5a7e70 (float, += sim_dt per frame) as the time base for all
   derivatives. The velocity-change heuristic fails for a car coasting at exactly constant velocity (no change ->
   "no tick") and for the far-vehicle kinematic path.
2. Prefer state over derivatives wherever the engine already holds the state: body-frame acceleration at
   0x4f2418 (or `ent+0xd4` rotated by `obj+0x18`) for surge/sway/heave; `flags & 4` for airborne; `eng+8` for gear.
   Each removes one differentiation that is sensitive to the step size and the clock grid.
3. For road texture, the exe's own model is explicit: wheel bump = WRLD surface +0x08 amplitude x the 8x8 pattern
   0x4be398 indexed by `(int)x & 7 + ((int)z & 7) x 8`, applied per substep, plus +0.1 for a flat tyre
   (0x4be4bc). A 1 m cell at speed v is a bump train at ~v Hz: 16 Hz at 16 m/s, past the loop's usable band. The
   honest rendering is amplitude from (surface bump amplitude x speed) with the texture oscillator held at its
   present 11 Hz, and surface changes read from `ent+0x45c` (an edge there is a real event: tarmac -> dirt).
4. If the LFE synth is driven from the proxy (section 4), run the engine-bed frequency from `eng+0x1c` at the
   physics step and leave the audio-rate smoother (`LfeSmoother`) to glide between steps; the step is 41.7 ms, the
   smoother's frequency time constant is 25 ms.

---

## 6. Prioritised improvements (all proposed)

Each row: data source, file to change, how to verify. Verification is against the sandbox copy only
(`C:\Users\james\i76-uncap-lab\game`), never the install James plays on.

| # | change | source | file | verify |
|---|---|---|---|---|
| 1 | **Gear from the engine block**; delete the rpm-rate shift detector | `[[ent+0x3c4]+0x70]+0x08` (0 R, 1 N, 2-4) [live]; edge flag 0x4f2340 / previous 0x4f2314 [static] | `Telemetry.ps1` (`Tel-Sample`: extend the entity read to 0x50c bytes, add two pointer reads; `Tel-DetectShift` becomes `gear != lastGear`); `FfbMixer.ps1` shift channel unchanged | drive 0 -> 110 km/h at full throttle in Melee: expect 1 -> 2 at throttle > 0.002, 2 -> 3 at ~62 km/h, 3 -> 4 at ~106 km/h (engine.md), one transient each; jump and lift off: no transient. Log `Rpm`, `Gear`, `Speed` to CSV and check with `ffb-replay.ps1` |
| 2 | **RPM from `eng+0x1c`** with 0x4f2334 as fallback | float, 850..7000 [live] | `Telemetry.ps1`; `FfbMixer.ps1` `LfeRpmMax` 6000 -> 7000 (geared revs pass 6000 before the limiter) | tach needle vs value, as `ffb-watch-effects.ps1 -Tach` did; removes the dependency on 0x52bbd0 being set |
| 3 | **Airborne, skid, grip-limit, oil from flags** | `ent+0x454` bits 0x4 / 0x2 / 0x2000 / 0x400 [static]; block copies 0x4f2450.. | `Telemetry.ps1` (`Airborne`, new `Skid`, `GripLimit`, `Oil`); `FfbMixer.ps1`: `gripScale` from `Skid`/`GripLimit`, oil as a sustained lightness, landing transient on airborne falling edge with `-Vy` before touchdown | sandbox: handbrake turn (bit 2 on, tskid sound), 40 m drop (bit 4 on, vland on landing), oil slick weapon (bit 0x400 for 2 s); compare the flag edges with `Oversteer` and `Jolt` in the CSV |
| 4 | **Orientation and position into the OutSim stream**; stop zeroing pitch/roll/position | `obj+0x18` 3x3, `obj+0x40` doubles [live] | `ffb-telemetry-udp.ps1` (+ `Telemetry.ps1` to read `obj`); drop the "no orientation" paragraphs | parked on a known slope: pitch/roll from the matrix vs the terrain normal `ent+0x460`; position vs the trainer's `status` |
| 5 | **Body-frame acceleration from the block** for the motion bus and the brake channel | 0x4f2418..0x4f2420 = `math_Mat3MulVec3(ent+0xd4, obj+0x18)` [static]; sign convention [inferred: row-vector, world = local x R + T] | `Telemetry.ps1` (read the block fields it already has in `FxBuf`), `FfbMixer.ps1` (`Motion.SurgeA/SwayA/HeaveA`) | brake hard in a straight line: one component negative, the others ~0; the sign test settles the convention. Compare with the differentiated `LongAccel` |
| 6 | **Damage-aware weight**: lateral cap from live tyre grip; blowout transient | `7.84 x sum(wheel_i+0x0c)` (0x4bd1e0) [static]; `wheel_i+0x44` flat / block 0x4f2430.. [static]; blown front tyre pulls steering +-0.3 (0x43cf5b) | `Telemetry.ps1` (`TEL_LAT_GAIN` computed), `FfbMixer.ps1` (blowout = the stock TIREBLWL/R: constant + superimposed sine, per `parse-frc.py`; add a steady pull of sign = which front tyre) | trainer `repair` then shoot a front tyre: `Understeer` should rise as grip drops, a transient on the flat edge, a steady pull after |
| 7 | **Impacts from the FFB lists / damage hooks**, directional | nodes at 0x4f2478 / 0x4f247c / 0x4f2484: +0 direction deg (f32), +4 damage (f32) [live widths]; or `entity_DamageAndKill` side | `Telemetry.ps1` (walk the lists; IsBadReadPtr-style guard as the shim does) or the proxy export | ram a wall head-on vs side-swipe: direction near 0 / +-90; damage matches the HUD armour drop |
| 8 | **Telemetry export in the proxy** (`I76_TELEMETRY=1`): per-frame struct + event ring over UDP and shared memory; `Telemetry.ps1` gains a shared-memory source with the scanner as fallback | hooks: 0x4f778c post-tick slot (or `call 0x446110` at 0x445e83), 0x4a6e90, 0x49ead0, 0x4a7c80, 0x463a80 (all `hookable yes`) | `music-fix/strlkproxy.c`; `Telemetry.ps1` | `I76MUSIC_LOG` hook count; a Python listener (as `tools/ffb-udp-listen.py`) shows shots counted per `weapon_FireShot` call vs ammo spent; explosion positions vs the mission; the struct's frame counter monotonic at the frame rate |
| 9 | **Explosion channel from `entity_SpawnExplosion` with distance**, not from a weapon gain >= 40 | 0x49ead0 position vs `obj+0x40` | `FfbMixer.ps1` (`LfeExplodeAmp` from 1/d^2), `LfeSynth.ps1` unchanged | fire a mortar far and near; the blast amplitude should follow distance, and MG fire must never trigger it |
| 10 | **Nitrous, engine-off, ENGSTART, weapon-UI clicks** on the bus | 0x4f2344, 0x4f2338, 0x4f233c, 0x4f234c..0x4f2354 [static] | `FfbMixer.ps1` | press the nitrous key: a 15 s sustained bed; engine off: LFE engine bed silent; cycle weapons: a click |
| 11 | **Fix the labels** so the next reader is not misled | section 2.3 and 3 | `tools/ffb/README.md` Telemetry map (+0x04 hull corners, orientation at `obj+0x18`, gear found), `Telemetry.ps1` header (suspension / roll-pitch / fixed-step claims), `docs/FFB-DEEP-DIVE.md` (+0xfc/+0x100 are throttle, +0x18 is gear-changed, +0x1c nitrous, +0x20 blower), `docs/MOTION-SIM.md` (transform is on the object), `ffb-shim/i7ffshim.c` (`steer` -> throttle direction; rpm range) | review only |
| 12 | Settle hardpoint +0x10 (freq vs direction) | stores into 0x4f2368 inside 0x4a66f4..0x4a6e06 | static read with `tools/disasm.py`, or the one-drive test in FFB-STACKS | aim the same weapon two ways and watch +0x10 |

Things this audit recommends **not** doing: driving road texture from `+0xc8`/`+0xd0` (they are real rates but the
contact model makes them a rest/contact square wave); treating `eng+0x24` as speed; keeping two shift detectors.

---

## 7. Open items and what is still inferred

- Whether 0x4f2340 is cleared on non-shift frames, and whether 0x4f2314 tracks the current gear each frame: one
  `ffb-watch-effects.ps1 -Log` drive. `eng+8` does not depend on the answer.
- The sign/axis convention of 0x4f2418..0x4f2420 (body-frame acceleration): one braking test (row 5).
- The wheelbase `ent+0x118` for the sandbox car, to confirm the 2.45 m inference behind the fitted 0.76 rad "lock".
- Whether `physics_ApplyCollisionDamage`'s 0.02 x amount term at 0x4beb70 ("FFB jolt = amount x 0.02 for amount
  > 20", physics.md constants) feeds the impact nodes' magnitude or something else; it is in the function that
  appends the nodes.
- Call sites of `sound_PlayVehicleEvent` for events 5, 6, 8, 9 were not enumerated here (the map's xref file is
  keyed on data globals). Not needed if section 4's recommendation is followed.
- The shim's claim that the Mac field run was "tuned" is from July; the block semantics corrected above (+0xfc,
  +0x18, +0x1c) mean its `steer` channel never was steering.

Sources read: `tools/ffb/{Telemetry,FfbMixer,LfeSynth,FfbCore,ffb-interposer,ffb-telemetry-udp,ffb-watch-effects,
ffb-find-rpm-wide,ffb-find-slip,ffb-find-fire}.ps1`, `ffb-calib.json`, `README.md`; `ffb-shim/i7ffshim.c`;
`sound-rumble/dsndrumble.c`; `tools/trainer/i76trainer.py`; `music-fix/strlkproxy.c` (hook mechanics, fixed step,
render interp); `docs/{FFB-DEEP-DIVE,FFB-STACKS,FORCE-FEEDBACK-AND-VISUALS,MOTION-SIM,MEMORY-MAP-INDEX,READY-TO-TEST}.md`;
i76-map `types/i76.h`, `types/i76_runtime.h`, `subsystems/{engine,physics,damage,weapons,sound,camera,framerate,
simclock}.md`, `symbols/functions.tsv`, `symbols/hookability.tsv`, `evidence/E43814..E43817`.
