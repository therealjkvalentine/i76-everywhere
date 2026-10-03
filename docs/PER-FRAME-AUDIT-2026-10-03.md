# Per-frame audit: actions taken once per rendered frame that nothing scales by dt

*2026-10-03. Static reading plus proxy code; **no game run** (nothing below is measured). Follows the field report at
120 fps on 2026-10-02, "the oil slick sound plays too fast" (fixed in `7c998bf` as `apply_hazard_fix`).*

**What this covers.** `docs/FRAMERATE-COVERAGE-2026-10-02.md` checked the proxy against the rows the spec already
listed. This pass looks for rows the spec does not have: an **event** (damage, a sound start, a spawn, a random roll, an
angular step) issued once per rendered frame or once per projectile step, with no dt in it and no gate in the proxy.
Rows already in the coverage doc are not repeated.

**Sources.** i76-map `ghidra/export/functions/*.c` and `callgraph.json` (exe md5 `9a232dcc`), `status/perframe.tsv`
(695 frame-scope and 390 substep-scope functions), `subsystems/{weapons,damage,sound,ai,physics,engine,simclock}.md`;
capstone disassembly of every patched site. Old bytes were compared programmatically in **both**
`i76-map\ghidra\i76_ref.exe` (`9a232dcc`) and `i76-uncap-lab\game\i76.exe` (md5 `85de44a7` today, AiO-based):
17 / 17 new sites identical, and the two existing hazard sites.

**Method.** Three screens, then a hand read of every hit:

1. Every function in frame scope that directly calls an *effect* function: sound starts (0x4231f0, 0x4250f0, 0x4232a0,
   0x422f20, 0x423230), damage (0x462040, 0x4a7c80, 0x465620, 0x463a80, 0x465af0, 0x4a8240, 0x462660, 0x46da30,
   0x4652b0), spawns (0x49ead0, 0x4a2bb0, 0x49fb40, 0x4a1b60, 0x4a1810, 0x4a7190, 0x441310), kicks and timers
   (0x43d2e0, 0x43d640, 0x466e80, 0x466e50, 0x4677d0), the sweeps that apply damage (0x435830, 0x435cc0) and `rand`:
   60 functions.
2. The same for functions `perframe.tsv` does not reach, because they are called through pointers (the AI behaviour
   table 0x4c3e00, the class table 0x4f76e0): 33 functions. **This is where the AI rolls below were**; the earlier
   "per-frame rand sweep" (framerate.md 133-134) only saw directly reachable functions.
3. Every per-type step in the `weapon_StepProjectileByType` 0x4a0800 jump table, read whole.

The earlier screens matched *constant steps* (`fld; fadd const; fstp`). The oil slick was missed because its
per-frame action is a call, not arithmetic; that is the shape screened for here.

Rates in the tables are per second while the condition holds: stock 20 fps / 60 fps / 120 fps.

## 1. Confirmed (static), with fixes built

| id | what | address(es) | per frame it does | 20 / 60 / 120 | severity | dt-scaled in stock? | fix |
|---|---|---|---|---|---|---|---|
| H1 | **Stationary hazard damage and contact test**: oil slick (id 0xc), fire patch (0x11, Fire-Dropper), wheel hazard (0xe, no stock weapon), landed canister (0x16, no stock weapon) | steps `weapon_StepOilSlick` 0x4aa150, `weapon_StepWheelHazard` 0x4aa2d0, `weapon_StepFirePatch` 0x4aa450, `weapon_StepGroundFireCanister` 0x4ac800; sweep 0x435830 (0x435cc0 for the canister) -> 0x435c92 `physics_ApplyCollisionDamage` | one sweep per shot count (pd+0x3c); each hit applies the ordnance's full per-shot damage (`weapon_BuildImpactDamage` 0x4a76a0: no dt), stamps the AI damage event and queues an FFB impact node for the player; then the impact effect + sound the `7c998bf` fix already held; the oil slick also restarts its 2 s traction-loss timer; the wheel hazard sets the nearest wheel to 25 hp or x0.75 | 20 / 60 / 120 hits per second in contact | **gameplay**: Fire-Dropper damage per second 3x / 6x; an AI car in the patch also gets 3x / 6x damage events (re-target rolls) | no | F1 |
| R1 | **Radar missile turn per step** (id 8 DrRadar, Cherub; id 0x14 twin, no stock weapon) | `weapon_StepRadarMissile` 0x4aa9f0: 0x4aabf1..0x4aac62, rotation call 0x4aaca0; `weapon_StepGuidedMissileNoJam` 0x4ab1c0: call 0x4ab400 | when dot(nose, target) < 0.998: rotates by min(0.75 x abs(cross), limit), limit = 0.0523 / 0.2588 / 0.3420 rad (sin 3 / 15 / 20 deg, floats 0x4bec2c / 34 / 38) for < 15 / 15-150 / > 150 m flown | turn limit 60 / 180 / 360 deg/s in the first 15 m, 297 / 890 / 1780 deg/s to 150 m, 392 / 1176 / 2352 deg/s beyond; the proportional part closes 75% of the error per step | **gameplay**: radar missiles out-turn any target at high fps (player's and AI's alike) | no (`weapons.md` 90 already says "per step") | F2 |
| C1 | **Collision contact repeats under the fixed step** (proxy-induced, like U4 of the coverage doc) | `physics_CollideAll` 0x4349c0 (WinMain 0x403a12) -> `physics_CollideBodyPair` 0x434bb0: sound 0x434d7e / 0x434ebc, `object_ClassCollide` 0x434ede -> `entity_CollideStoreContact` 0x4643c0 (damage call 0x4644bc), `object_CollideApplyDamage` 0x46f890 (0x46f8d4) | per contact: an impact sound, `physics_ApplyCollisionDamage` for both bodies **at once**, the AI damage event, screen shake + FFB for the player. The car consumes the contact on its next substep. With `I76_FIXED_STEP=24` a frame without a substep leaves pose and velocity bit-identical, so the next frame finds the same contact and applies all of it again | per impact: 1 (stock, any fps: at least one substep per frame) / up to 3 (fixed step, 60 fps) / up to 5 (fixed step, 120 fps); sustained contact: 20 / 60 / 120 events per second instead of 24 | **gameplay**: ram and scrape damage, both to the player and to what it hits, multiplied by the frames per step; the impact sound restarts every frame | the damage amount comes from the impact vector, no dt | F3 |
| S1 | **Dead-weapon click** | `weapon_ReadPlayerTrigger` 0x4a5870: `sound_PlayIfPlayerObject`("WMISS.WAV") at 0x4a5a0e | with fire (or the hardpoint key) held on a row at 0 condition: clears the trigger and requests the one-shot, every frame (also sets the row's FFB effect) | 20 / 60 / 120 requests per second | sound (the same repeat-until-false shape as the lock tones) | no | F4 |
| A1 | **AI skid-turn roll** | `ai_ShouldSkid` 0x41f590 (transition test, behaviour 5 dirt_brave -> 7 tactic_skid; called through the behaviour table every frame): `call [rand]` 0x41f5d4, test 0x41f5f8..0x41f600 | against a vehicle target: rand() % (8 + int((1 - skill) x 40)) == 0, then speed >= 12 m/s and the geometry tests | p per roll 1/8 (skill 1) .. 1/48 (skill 0): mean wait 0.4-2.4 s / 0.13-0.8 s / 0.07-0.4 s | **gameplay (AI)**: handbrake turns 3x / 6x as often | no | F5 |
| A2 | **AI horn roll** | `ai_WillCollideOnPath` 0x41d8b0 ('avoid clsn' interrupt test, per frame): `call [rand]` 0x41dacc -> `sound_PlayHorn` 0x41dae8 | when the avoidance probe finds a vehicle in the way: (rand() & 3) == 0 honks | 5 / 15 / 30 honk starts per second while blocked | sound | no | F5 |

### F1. Stationary hazards step on the 20 Hz grid (extends `apply_hazard_fix`, `I76_FRAMERATE_FIXES`)

`mlog`: `hazard-contact: n/6 sites repointed`.

| site | old bytes | call | wrapper |
|---|---|---|---|
| 0x4aa27f | `E8 0C CF FF FF` | `weapon_SpawnImpactEffect` in the oil slick step | `hazard_impact_wrap` (from `7c998bf`) |
| 0x4aa559 | `E8 32 CC FF FF` | the same in the fire patch step | `hazard_impact_wrap` (from `7c998bf`) |
| 0x4a08ec | `E8 5F 98 00 00` | `weapon_StepOilSlick` from the type switch | `hazard_step_oil` |
| 0x4a0900 | `E8 CB 99 00 00` | `weapon_StepWheelHazard` | `hazard_step_wheel` |
| 0x4a0914 | `E8 37 9B 00 00` | `weapon_StepFirePatch` | `hazard_step_fire` |
| 0x4a0856 | `E8 A5 BF 00 00` | `weapon_StepGroundFireCanister` | `hazard_step_canister` (held only once landed, pd+0x48) |

Between grid frames the step is not called (it returns 1, "alive"; the life timer is counted by 0x4a0990 before the
step and is untouched). On a grid frame the step has to cover the time since the last grid frame, as one 50 ms stock
frame does: `physics_SweepSegment` reads `simclock_sim_dt` / `sim_rate` itself (0x43583a / 0x435846), so both are set
to the grid window (the summed dt since the previous grid frame, clamped to [dt, 0.2]) for the call and restored. Why
the whole step and not only the damage call: the damage call sits inside the shared sweep (every bullet uses it), and
a held step is the stock 20 fps behaviour exactly. The two `7c998bf` sites stay: they are now always open on the
frames the step runs, and their counter still counts effects.

Approximation, stated: a hazard dropped between grid frames starts testing up to 50 ms late (stock: up to one frame).

**Acceptance (sandbox, telemetry on):** park in a Fire-Dropper patch (or on a slick), 10 s windows, n >= 2 per
condition, A/A first (same condition twice at capped 20):

- telemetry `IMPACT` events with source class 0x33 per second, and `EXPLOSION` events per second: stock 20 fps ~20/s
  per shot count; stock 60 ~60; stock 120 ~120; with the fix at 60 and 120: ~20;
- player health lost per second (the `IMPACT` event's f[3]) equal to capped-20 within the A/A spread;
- `g_idbg.hazard_steps` 20/s per live hazard, `g_idbg.hazard_impacts` 20/s x shot count in contact;
- drive-through at 30 m/s over a slick, 10 passes: traction loss triggers on every pass (the grid window keeps the
  coverage continuous). A miss here means the dt override is wrong.

### F2. Radar missile turn scaled by dt x 20 (`apply_perframe_fixes`, `I76_FRAMERATE_FIXES`)

`mlog`: `perframe-fixes: n/5 sites repointed` (F2, F4, F5 together).

| site | old bytes | call | wrapper |
|---|---|---|---|
| 0x4aaca0 | `E8 BB 97 FE FF` | `math_MatrixFromAxisAngle` 0x494460(out, -angle, axis) in the radar missile step | `radar_turn_wrap` |
| 0x4ab400 | `E8 5B 90 FE FF` | the same in the id 0x14 twin | `radar_turn_wrap` |

Scaled, not gated (the missile still moves every frame; a 20 Hz turn would show as a kinked trail). With
k = min(frame dt x 20, 1):

- angle equal to one of the three limit floats (clamped; exact compare, the code loads the constant as-is): x k, so the
  rate limit per second is the stock 20 fps one;
- otherwise (the proportional branch, angle = 0.75 x abs(cross)): x (1 - 0.25^k) / 0.75, so the error left after 1/k
  frames is the 25% a single stock step leaves.

At 20 fps and below both factors are exactly 1 (stock). Approximation, stated: within one 50 ms window the switch
between the clamped and the proportional regime can fall on a different frame than the single stock step would
choose; the turn per window in either pure regime is exact. The 0.998 dead band is untouched.

**Acceptance:** fire a DrRadar at a target circling at constant speed (or at a parked target from 90 deg off the
nose), log the missile's heading per frame (ordnance table 0x655280 -> object +0x30 forward row):

- peak turn rate beyond 150 m: ~392 deg/s at capped 20; stock 120 ~2350; with the fix at 60 and 120: ~392;
- hit fraction on a crossing target, n >= 10 per condition, fix-120 against capped-20 within the binomial spread, and
  stock-120 higher (if stock-120 is not higher the row is cosmetic and can be dropped);
- `g_idbg.radar_turns` advances only while a radar missile is off its dead band.

### F3. Collision sound + damage once per physics step (`apply_coll_dedupe`, on with `I76_FIXED_STEP`)

`mlog`: `coll-dedupe: n/6 sites repointed`. `I76_COLL_DEDUPE=0` keeps the counters and passes everything through.
Not applied without the fixed step (stock always runs a substep per frame, so nothing repeats).

| site | old bytes | call | wrapper |
|---|---|---|---|
| 0x434ccf | `E8 3C A8 00 00` | `physics_CollideShapes` 0x43f510 (pair test, order a, b) | `coll_shapes_wrap` |
| 0x434cf1 | `E8 1A A8 00 00` | the same, order b, a | `coll_shapes_wrap` |
| 0x434d7e | `E8 6D E4 FE FF` | `sound_PlayOnObject`("vvbo1.wav"), walkable structure | `coll_sound_wrap` |
| 0x434ebc | `E8 2F E3 FE FF` | `sound_PlayOnObject`(impact sound) | `coll_sound_wrap` |
| 0x4644bc | `E8 BF 37 04 00` | `physics_ApplyCollisionDamage` in the vehicle handler 0x4643c0 (also reached from the type 9 handler 0x46bcf0) | `coll_damage_wrap` |
| 0x46f8d4 | `E8 A7 83 03 00` | the same in `object_CollideApplyDamage` 0x46f890 (types 2, 4, 7, 0xa) | `coll_damage_wrap` |

A contact is a **repeat** when the same pair made a contact on the previous frame and neither body moved since:
a vehicle, exactly - its fixed stepper ran 0 steps in the previous frame's tick (`g_step_acc`, the collision pass runs
before the ticks); anything else - its position doubles are unchanged. On a repeat the sound and the damage calls
return without acting; the class handlers still run, so the stored contact record (entity+0x38) is rewritten exactly
as before and the physics response is not touched. A far vehicle (one whole-frame step, no stepper) always counts as
moved.

Not covered: without the fixed step at high fps a *sustained* contact is tested, sounded and damaged once per frame
(3x / 6x per second); that configuration is not the supported one (U4 below).

**Acceptance:** `I76_FIXED_STEP=24`, telemetry on, 120 fps, then 60, then capped 20 as the reference; n >= 5 rams
per condition at a fixed approach speed (the cactus gauntlet's approach, or a parked car):

- with `I76_COLL_DEDUPE=0`: `g_idbg.coll_dups` / `g_idbg.coll_events` ~0.8 at 120 fps (4 of 5 frames), ~0.6 at 60,
  0 at capped 20. **If this reads 0 at 120 the mechanism is wrong and F3 should be withdrawn**;
- telemetry `IMPACT` events (source class 1, or 0 / 2 / 4 for scenery) per ram and the player's health lost per
  ram: with the dedupe at 120 = capped 20 within the A/A spread; with `=0` about 5x;
- sustained scrape along a wall for 5 s: applied `IMPACT` events ~24/s at any frame rate.

### F4. WMISS.WAV on the 20 Hz grid (`apply_perframe_fixes`)

| site | old bytes | call | wrapper |
|---|---|---|---|
| 0x4a5a0e | `E8 DD F6 F7 FF` | `sound_PlayIfPlayerObject` 0x4250f0("WMISS.WAV") | `wmiss_wrap` |

Requests between grid frames are dropped; the key is a level, so the next grid frame asks again. The trigger clear
and the FFB write next to it still run every frame.

**Acceptance:** destroy a weapon (trainer: weapon condition 0), hold fire 5 s: `g_idbg.wmiss_req` = frame rate,
`g_idbg.wmiss_play` = 20/s at 60 and 120; by ear the click cadence equals capped 20.

### F5. AI skid-turn and horn rolls on the 20 Hz grid (`apply_perframe_fixes`)

| site | old bytes | instruction | replacement |
|---|---|---|---|
| 0x41f5d4 | `FF 15 0C C2 4B 00` | `call [0x4bc20c]` (rand) in `ai_ShouldSkid` | `call ai_skid_rand; nop` |
| 0x41dacc | `FF 15 0C C2 4B 00` | `call [0x4bc20c]` (rand) in `ai_WillCollideOnPath` | `call ai_horn_rand; nop` |

Both wrappers roll the exe's own rand on grid frames and return 1 between them; 1 fails both tests (1 % m != 0 for
m >= 8; 1 & 3 != 0). `I76_AI_ROLL_HOLD=0` counts and rolls every frame. Under `I76_FRAMERATE_FIXES` as asked, not
`I76_AI_FIXES`: they restore the stock rate and need no balance decision. If the integrator prefers to A/B them with
the dodge gate, the two table rows move to `apply_ai_fixes` unchanged.

**Acceptance:** t01 or a melee with one AI car attacking off-road, 30 s windows, n = 2, A/A first:
`g_idbg.skid_rolls` per second with `I76_AI_ROLL_HOLD=0` ~ frame rate x (fraction of frames in dirt_brave with a
vehicle target), and with the hold ~20 x the same fraction; entries into behaviour 7 (ai+0xa874 stack top) per
minute at 120 with the hold = capped 20 within the spread. Horn: `g_idbg.horn_rolls` per second while an AI car is
blocked behind another: ~20 with the hold, ~frame rate without.

### Debug counters (appended to the END of `g_idbg`, copied by the render wrapper, so `I76_RENDER_INTERP` must be on)

After `far_steps` (offset 1956 in the lab's `rate-ab` driver), 4 bytes each, in this order: `hazard_impacts` 1960,
`hazard_steps` 1964, `radar_turns` 1968, `wmiss_req` 1972, `wmiss_play` 1976, `skid_rolls` 1980, `horn_rolls` 1984,
`coll_events` 1988, `coll_dups` 1992. Offsets follow from the field order; confirm against the block address the log
prints before trusting a sampler (`hazard_impacts` is the `7c998bf` counter, which had no field until now).

## 2. Fine: read, dt-scaled or event-driven

| what | address | why it is fine |
|---|---|---|
| Projectile life timer | 0x4a0990 (`life -= dt`, pd+4) | dt |
| Bullets / shells, batching | `weapon_StepBullet` 0x4abe60 | displacement by dt; one sweep per batched round; the projectile dies on its hit; speed easing x dt |
| Rocket | 0x4aa5b0 | speed eases at 0.5 x dt; 70 m shooter immunity by distance flown |
| Heat missile | 0x4ab920 | snaps its facing to the target every step (no rate to scale: pure pursuit at any fps); re-acquires only when the target leaves the 0.94 cone (0x436120); the search 0x4a82c0 has no rand |
| Mortar, cluster bomb | 0x4ac3d0, 0x4ace20 | ballistic by dt; bomblets spawned once (0x4a9090) |
| Bomblet fuses | `weapon_UpdateDelayedImpacts` 0x4a91e0 | time compare + `fuse -= dt` |
| Tumbling mines, kick | 0x4a92e0 | tumble by dt; the settle sound once; the kick (0x43d2e0) on the hit that kills the mine: one-shot |
| Canister in flight | 0x4ac800 before pd+0x48 | mortar flight by dt |
| `weapon_SpawnImpactEffect` callers | 0x4a7190: 13 call sites | all at the projectile's death or hit except the four stationary steps (H1) and the delayed impacts (once per bomblet) |
| Explosion area damage | `entity_SpawnExplosion` 0x49ead0 -> 0x435120 | once, at spawn; explosions (class 0x34) have no tick; animation by time (expiry = now + template life) |
| Fire / burning over time | - | there is no burning state on a vehicle; the only damage-over-time is the fire patch (H1) and the flamers (covered) |
| Terrain surface damage | 0x4641e0 from the physics step | rate x step dt accumulated in +0x458, integer part applied: dt |
| Entity state timer (ent+0x450): ignition, traction loss, nitrous, wreck | `entity_UpdateState` 0x465370 | `-= step dt` |
| Traction loss, nitrous, jammer, X-Aust | 0x466e80, `physics_FireNitro` 0x43d280, 0x461770, 0x44f608 | timers by dt or sim time; started by press-type keys (action type 2) |
| Wreck debris and secondary explosions | `entity_Wreck`(obj, 0), rand() & 15 per `entity_UpdateState` call | per **substep**: 24/s under `I76_FIXED_STEP` (stock 20 fps: 20-40/s). Far vehicles (> far radius + 25 m) roll once per frame, out of sight. Stock at 60 / 120 without the fixed step: 60 / 120 rolls/s (covered by mechanism C) |
| Per-substep rolls and effects | 0x438fd0, 0x436ff0, 0x465af0, 0x46de20, 0x46ac50, 0x46b220 | substep scope: step-rate bound, so covered by the fixed step |
| Aircraft, chunks, moving objects | ticks 0x46b8b0 (type 9), 0x4a2070 (0x35), 0x46d2e0 (7), 0x46f6b0 (0xa) | dt; their explosions are guarded by state flags (0x8020), once |
| Screen shake on a hit | `renderer_ApplyScreenShake` 0x498730, mode 1 (set by 0x498910 from a > 20 damage hit) | amplitude eases to 0 at 2 x dt |
| Death sequence | `entity_Wreck`(obj, 1), `entity_DamageAndKill` death block, 0x46c8b0 | one-shot; the 10 s timer by dt; the end-of-match spin is a covered site |
| Weapon timers, lock timer, turret slew | 0x4a6470, 0x4a3760 | dt (three reads); WCLICK.WAV is edge-triggered (latch +0x48) or behind the 1 s cooldown |
| HUD: gear shift sound, status lamps, jammer | 0x45ad40, 0x45a450, 0x461770 | on change only |
| HUD blink | - | no reader of the frame counter 0x5a7e1c beyond the three audited ones (mirror, texture cache, cockpit continuity); the script VM counter 0x524550 is a two-frame latch (neutral) |
| Other AI rand users | enters 0x416be0, 0x416e50, 0x416f20, 0x41c300, 0x41c5c0, 0x41c830, 0x41c900, 0x41c9d0, 0x41cb00, 0x41e2b0, 0x41e740, 0x41ed00; updates 0x41e450, 0x420b30, 0x420fc0 (timers on sim time); 0x41e970 (state change) | on entry or behind a time stamp |
| Radar / target cycling, specials | `input_ApplyToEntity` 0x44f1c0 | press-type actions |
| Binocular glance keys | 0x44ed50: +-29 / +31 per frame up to -88 / +93 | saturates in 3 frames at any rate; an absolute target after that |
| Sustained loops | wind 0x44edae, engine special 0x424e90 / 0x424ed0 | sustained requests (keep-alive), not starts |
| Regen points, respawn | 0x4515e0 | 30 s on sim time |

## 3. Uncertain or cosmetic: not fixed

| id | what | address | reading | at 60 / 120 | why not fixed | measurement |
|---|---|---|---|---|---|---|
| U1 | Tracer length | `weapon_UpdateTracerHead` 0x441ef0 from 0x4ac398 (every bullet step) | advances a short ring (next-index table 0x52ba38, at most 4 points) by one point per step, so the tracer spans the last few **steps** of flight | 1/3 / 1/6 of the stock length (stock: speed x 50 ms per point) | cosmetic; a grid hold would make the head lag the bullet by up to 50 ms. The right fix overwrites the head between grid frames and advances on them (needs the ring's previous-index and a tail save); not built | screenshot an MG burst side-on at capped 20 and at 120: tracer length in px |
| U2 | Turret fire outer gate | `entity_TickTurretFire` 0x462a90: rand() % (2N - 2) at 0x462c0f before the wrapped `ai_ShouldFireWeapon` (0x462c3e) | the outer roll is still per frame; the inner decision is cached per grid window, so the number of windows with a trigger is the stock one but the trigger is held for fewer ms inside the window | fire time per window roughly 60% of stock for N = 2, less for larger N (a static estimate) | changes AI turret output; needs the `aifire`-style measurement first | turret shots per minute (telemetry has no AI SHOT event: count ordnance spawns) at capped 20 vs 120 with the fix set |
| U3 | wiggleburger cheat jitter | 0x498730 mode 0: two rand() & 15 targets per frame, eased by dt | smaller, faster jitter | cheat-only, cosmetic | - |
| U4 | Sustained collision contact without the fixed step | 0x434bb0 | sound + damage once per frame while touching | 3x / 6x per second | not the supported configuration (the fixed step is part of the set); F3 is a no-op there | `IMPACT` events/s scraping a wall, stock 120, no fixed step |
| U5 | Far wrecks | `entity_TickVehicle` far path -> `entity_UpdateState` once per frame | debris / secondary explosion rolls per frame | 3x / 6x | > 849 m from the camera, not visible; the explosions are spawned though (cost only) | - |
| U6 | physics.md line 124 "or when wrecked" | - | the far path is taken on object flag 0x20, which no wreck path sets (`object_SetFlagsTree` is called with 0x200 / 1 / 0x201 only); a near wreck steps through the stepper | - | doc correction for i76-map, not a site | - |

## 4. Summary

- Five new mechanisms with gameplay or sound weight, 17 sites, all built into `music-fix/strlkproxy.c`, zero
  warnings, bytes verified in both exes, **none run**: hazard damage (F1, 4 new sites + the 2 existing), radar missile
  turn (F2, 2), collision repeats under the fixed step (F3, 6), WMISS click (F4, 1), AI skid and horn rolls (F5, 2).
- The largest by effect on play are H1 (Fire-Dropper damage 6x at 120), R1 (radar missiles 6x the turn rate) and C1
  (ram damage up to 5x at 120 with the fixed step). C1 is the proxy's own doing and is the one whose mechanism the
  integrator should confirm first (the `coll_dups` ratio).
- Everything else on the list was read and is dt-driven or event-driven (section 2).
