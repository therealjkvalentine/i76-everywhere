# weapons

**Contract.** Weapons are instances, one per mounted weapon (table 0x5aab08, stride 0x4c), grouped into a vehicle
weapon record (0x5be4d8, stride 0x2c8: 7 slots at +0x58 + k x 0x58). They fire projectiles from a pooled
ordnance table (0x655280). Hits turn into damage records through `physics_ApplyCollisionDamage`, then
`object_ClassDamage` and `entity_ApplyDamage` (`damage.md`).

Static reading of md5 9a232dcc (2026-09-27), batch `weapons-map-1` (69 names), from a reviewed read-only draft
(cluster H). The network-only gate at 0x4a4257 was checked in disassembly.

## Fire to damage, in order

1. **`weapon_Update`** 0x4a4130 runs per frame on the player record:
   - latches unlimited ammo (bit 4 of `options_play_flags`, offline) into 0x5da798;
   - `weapon_UpdateTurretsAndLocks` 0x4a3760: turret aim with lead, lock timers, gun auto-elevation;
   - `weapon_ReadPlayerTrigger` 0x4a5870 sets instance +0x3c;
   - cycle 0x4a5be0, link 0x4a6170, unlink 0x4a5f50; HUD diodes 0x4a4d50, ammo digits 0x4a4e40.
2. **Network games only** (0x4a4257): a jam roll per firing weapon, p = min(1 - condition - 0.3, 0.5) per frame (it
   clears the trigger; ammo -= int(dt x rate)), then `net_BuildWeaponFireMask` 0x4538a0. **Offline, weapons never
   jam.** A weapon at 0 HP plays `WMISS.WAV` and cannot fire.
3. **`weapon_UpdateInstanceFiring`** 0x4a6470 runs on every instance, AI included. The cooldown, interval and burst
   timers run against dt, then call `weapon_FireShot` 0x4a6e90(instance, weapdef, count, dt_left). MG (ordnance 1)
   and handgun (0x12) rounds are batched into one call per frame, so damage per second does not depend on frame
   rate.
4. **`weapon_FireShot`**:
   - muzzle flash 0x49f2f0, fire sound;
   - ammo -= count, skipped for the offline player with unlimited ammo (0x4a6f37);
   - target choice: radar target 0x4613f0, arc contact 0x461570 or heat search 0x4a82c0; EZK barrel 0x46f1d0;
   - builds a fire request -> `weapon_SpawnProjectile` 0x49fb40.
5. **`weapon_SpawnProjectile`**:
   - flame ordnance -> `weapon_FlameEmit` 0x443c90;
   - otherwise a pooled projectile, placed at the POF world transform with spread (see Quirks);
   - `weapon_ProjectileInit` 0x4a0ae0 sets life, shooter and target, speed, shot count and damage;
   - then light, tracer and smoke, and one catch-up step by the sub-frame time left.
6. **`weapon_UpdateProjectiles`** 0x4a0410 -> 0x4a0990 (life -= dt) -> `weapon_StepProjectileByType` 0x4a0800 -> the
   per-type step. Bullets and shells use `weapon_StepBullet` 0x4abe60: a ballistic step, one `physics_SweepSegment`
   0x435830 per batched round, and a terrain test 0x4a7800.
7. **Hit**: `physics_SweepSegment` -> `physics_ApplyCollisionDamage` 0x4a7c80 -> `weapon_BuildImpactDamage` 0x4a76a0.
   Damage x the difficulty factor is split over the ORDF 12 side mask; the handgun sets flag +6 bit 0. Then
   `object_ClassDamage` 0x462040 -> entity_ApplyDamage / DamageComponent. Visuals and area damage go through
   `weapon_SpawnImpactEffect` 0x4a7190 -> `entity_SpawnExplosion` 0x49ead0.
8. **Death**: the flight animation stops, the 'ordnc' references are released, the light is removed, and the
   projectile goes back to the free list.

## Tunables: .gdf / ORDF -> runtime -> code

| data field | path | code |
|---|---|---|
| GDFC 78 fire rate | weapdef+0x70 -> inst+0x28 = 1/rate | 0x4a6659 |
| GDFC 74 burst cooldown | weapdef+0x6c -> inst+0x24 | 0x4a6665 |
| GDFC 82 burst count | weapdef+0x78 -> inst+0x2c | 0x4a689d |
| GDFC 44 damage | weapdef+0x60 -> inst+0x10 -> request[5] -> pd+0x44 -> damage record (x difficulty for the offline player) | 0x4a5399, 0x4a6f0d, 0x4a0bbb, 0x4a774d |
| GDFC 48 weapon HP | weapdef+0x64 -> inst+0xc / +0x14 (condition: diodes, turret speed, WMISS at 0, network jams) | 0x4a4bf0 |
| GDFC 70 lifetime | weapdef+0x68 -> request[7] -> pd+4 / +8 (0 -> 5 s) | 0x4a0af0 |
| GDFC 86 aim speed | weapdef+0x74 -> request[2]; turret lead 0x4a3760, EZK solver 0x46f1d0 -> 0x4a8930, dropper eject | 0x4a6f04 |
| GDFC 94 ammo | inst+0x20 = min(GDFC 94, loadout) | 0x4a53ab |
| GDFC 98 spread | weapdef+0x84 -> request[11] -> 0x49fe58 | 0x4a7078 |
| GDFC 90 ordnance id | weapdef+0x80 -> request[0] -> the spawn and step switches | 0x49fb40, 0x4a0800 |
| ORDF 4 speed | ord+0x34 -> request[4] -> pd+0x38 | 0x49fc6e |
| ORDF 12 damage mask | ord+0x68 -> damage record +4, even split over amount[0..3] | 0x4a775b |
| difficulty 0x654b9c | player damage factor 2.0 / 1.0 / 0.75 (offline; AI 1.0) | 0x4a76e7 |

The weapon definition table base is 0x5d88d8 (the lab's 0x5D8800 table indexed from 1); instance layout from the
store list in 0x4a52e0.

## Quirks

- Offline weapons never jam; the condition only matters at 0 HP.
- Spread is one-sided and yaw-only. Bullets get spread only when both random draws are > 0 (about 25% of rounds),
  and then only in yaw, so most MG rounds fly straight along the POF. Rockets (2 / 8 / 0x14) get yaw only.
- GDFC 86 is an aim speed, not an eject parameter. It equals the ORDF speed for guns, cannons and mortars; EZK and
  rockets differ.
- The class 4 sub 4 lock-on logic (1.6 s, msllock*.wav) is used by no stock .gdf; ordnance ids 0x13..0x16 have no
  stock .gdf either.

## Projectile types (batch `range-s-1`)

`weapon_StepProjectileByType` 0x4a0800 switches on the ordnance id (ORDF +0) through the jump table 0x4a0938 (entry =
id - 1, re-read). Every step builds its state with `weapon_BuildProjectileStepState` 0x4a7370 and returns 0 when the
projectile dies. Stationary hazards die by life only. The radar-type missiles also die when they leave the terrain
grid.

| id | stock weapons | step | flight model |
|---|---|---|---|
| 1, 6, 0x12 | MGs and turrets; 20-30 mm, HADES, tank cannons; .45 handgun | `weapon_StepBullet` 0x4abe60 | straight or ballistic (ORDF gravity: 0 guns, 0.1 handgun), batched rounds |
| 2 | FireRite rocket | `weapon_StepRocket` 0x4aa5b0 | unguided; speed eases to the ORDF speed at 0.5 x dt |
| 3 | Aim-Nein heat missile | `weapon_StepHeatMissile` 0x4ab920 | re-acquires a heat target every step and **snaps** its facing to it: no turn limit |
| 4, 7 | HE / EZK / WP mortar, Howitzer | `weapon_StepMortarShell` 0x4ac3d0 | ballistic at 4 g |
| 5 | Cluster-Bomb | `weapon_StepClusterBomb` 0x4ace20 | mortar flight, then 9-12 bomblets, +-10 m spread, fuses over 1.8 s |
| 8 | DrRadar, Cherub | `weapon_StepRadarMissile` 0x4aa9f0 | turns only when dot(nose, target) < 0.998, by 0.75 x cross, clamped to sin 3 / 15 / 20 deg per step for < 15 / 15-150 / > 150 m flown; drops a jammed or dead target; floor = terrain + 0.5 m |
| 9, 0xa, 0xb | FlameThrower, Gas Launcher, Napalm Hose / Pyro-Tomic | none | never a projectile: `weapon_FlameEmit` 0x443c90 modes 0 / 1 / 2 (Flamers) |
| 0xc | Oil Slick | `weapon_StepOilSlick` 0x4aa150 | stationary 1 m probe; contact starts 2 s of traction loss (0x466e80) |
| 0xf, 0x10 | Landmines, Car-E-Racer; BloxDropper | `weapon_StepTumblingMine` 0x4a92e0 | tumbles and settles (restitution 0.5 normal, 0.25 tangential), then kicks the car it hits: (1, 2, 0.75) / (0.5, 0.5, 0.5) |
| 0x11 | Fire-Dropper | `weapon_StepFirePatch` 0x4aa450 | stationary probe, an impact effect every contact frame |
| 0xd, 0xe, 0x13, 0x14, 0x15, 0x16 | none in stock | - / 0x4aa2d0 wheel hazard / tumbling mine without kick / 0x4ab1c0 radar missile that ignores jammers / bullet / 0x4ac800 canister that lands and burns | |

- **Shooter immunity.** The shooter cannot be hit by its own rockets and missiles for the first 70 m, by mortars for
  1 s, and by droppers and mines for 2 s.
- **Network cap.** In network games ids 0xe..0x11 are capped at 40 live projectiles instead of 160
  (`weapon_RegisterOrdnance` 0x49f790).
- **Explosion damage** from an XDF lands on side mask 2 only (`entity_BuildExplosionDamage` 0x49ed90).

## Flamers

Flame weapons draw and damage from the renderer. All of this is per render call (i76-everywhere `music-fix`
`I76_FRAMERATE_FIXES` holds it to 20 Hz).

- `weapon_FlameEmit` adds one segment per shot (fire rate 20/s for every flamer), up to 19, and sets the stream's
  fired flag (+0x10).
- `weapon_AgeFlamerStreams` 0x443e90, at the top of each render, retracts the stream by 2 segments if the flag is
  clear, then clears it.
  - At 20 fps every frame has a shot and the stream grows to full length.
  - At 60 fps two frames in three have no shot, and the stream never gets past a segment or two.
- `weapon_UpdateFlamerStreams` 0x443fc0 rebuilds the flame's shape from the muzzle on every call, with the frame dt:
  droop 0.65 g x t^2, where t advances dt / segments per segment, and bend toward the target ~ dt.
  - It also tests each segment after the first with `weapon_FlameHitTest` 0x4354c0.
  - A hit applies `weapon_ApplyFlameDamage` 0x4a8240 with amount max(1, int(GDFC damage x f x dt)). f is 2.0 /
    1.0 / 0.75 by difficulty when the flamer's owner is the player, otherwise 1.0.
  - FlameThrower 15, Gas Launcher 30, Napalm Hose 45, Pyro-Tomic 60.
- On contact the update also spawns the ORDF car-impact explosion (`entity_SpawnExplosion` from 0x44471d; xflht1
  for stock flamers, blast damage 0), once per call.
- **Draw-path sweep (2026-09-27).** Every callee of the scene draws 0x401cc0 / 0x401fa0 and the mirror draw was
  checked for damage, sound, spawn and object-creation calls. Only this flamer chain has any.
- **The rear mirror** (`renderer_DrawRearMirror` 0x445750) calls the update again with its own camera, so with the
  mirror on, flamer damage is applied twice per frame, even at stock 20 fps.
- **Per second.** At 20 fps, a hitting segment deals 20 x max(1, int(D x f / 20)). At 60 fps, the per-frame minimum
  of 1 dominates for D x f < 60. The retraction bug works against it, so the net effect of frame rate on flamer
  damage is not a simple ratio.
- **Live (2026-09-27, sandbox, Gas Launcher held 4 s, `captures/014-framerate/flame_*.json`):** mean stream length
  over 1-4 s of firing was 0.6 segments (max 2) at stock 60 fps, 19.0 at stock 20 fps, and 18.7 at 60 fps with
  `I76_FRAMERATE_FIXES`. Ammo use was the same in all three (74-81 in 4 s). An uncapped stock game has, in effect,
  no flamers. Damage per second with the fix follows from the code (stock-20 amount, 20 applications a second);
  not yet measured on a target.

## Not yet named

Everything in the fire, step and hit chain is named (ranges `range-r-1`, `range-s-1`).

## Weapon groups, selection and keys (static reading, batch `gap-hud`)

**Record** 0x5be4d8 + i x 0x2c8: +0 vehicle; +4 selected list (primary row, then linked rows, -1 = empty); +0x24 separator row;
+0x28 dymo flags; +0x3c diode states; +0x50 row count; slots at +0x58 + k x 0x58 = {+0 HLOC index, +8 facing, +0xc mesh type
(3 for sub >= 100), +0x10 transform, +0x50 instance}. Slots 5 / 6 are the handgun arms (hardpoint > 4, not counted; `weapon_AddMount` 0x4a2e00).

**Row order.** `weapon_AddMount` qsorts the regular slots on every add with `weapon_CompareMountPriority` 0x4a51a0: key =
T[mesh x 5 + facing], lower first, ties to the lower HLOC index (0x4a52ad..0x4a52c3). T (0x4a51b9..0x4a526f): (mesh 2, facing 1) = 1,
(5, 1) = 1, (1, 1) = 2, (3, 1) = 2, (2, 2) = 3, (5, 2) = 3, (4, 2) = 4, anything else 9. inst+0x1c = row = HUD row = hardpointN key.

**Mount flag** inst+0x44 (`weapon_CreateInstance` 0x4a52e0): 4 turret (mesh 3, 0x4a5635..0x4a5657); mesh 6: 8 when facing is 3,
else 0x10 (0x4a578f..0x4a57b0; no stock mesh 6); otherwise 1 if dot(weapon z row, vehicle z row) >= 0, else 2 (0x4a57b5..0x4a5807).

**Keys** (bindings 0x4f2940, stride 0x20): weapon_fire 0x5367db (held), weapon_cycle 0x5367dc (press), weapon_link 0x5367dd
(press), hardpoint1..5_fire 0x5367de..0x5367e2 (held), through pointer table 0x5da738 (`weapon_ResetTables` 0x4a2d30).

**Per frame** (`weapon_Update` 0x4a4130, player only). Nothing below runs if no row 0..4 has condition > 0 (0x4a41c3..0x4a41fa).
- A selected weapon at 0 condition forces a cycle (0x4a41fd..0x4a4209).
- The link key toggles link mode 0x5da79c (0x4a4222..0x4a4237; 0 after `weapon_ResetTables`).
- Then, every frame: link mode on -> link 0x4a6170, off -> unlink 0x4a5f50 (0x4a423d..0x4a424f).

**Cycle** 0x4a5be0. Steps +1 from the primary over rows 0..4, wrapping (row 5 skipped, 0x4a5c6e), to the first row that is not in
the list, has an instance and has condition > 0; ammo is not checked (0x4a5c91..0x4a5d10). None: no change, no sound (0x4a5d2b).
Otherwise: listed rows' dymo go off and the list is cleared (0x4a5d3b..0x4a5dd5); primary = new row (0x4a5de3); CAMMO.WAV
(0x4a5dff); new dymo on; radar turret transform reset (0x460e60). In link mode the new primary is linked on the next frame.

**Link** 0x4a6170. Runs only while the list is the primary alone (0x4a61f9..0x4a6202); scans rows primary+1..5, wrapping to 0
(0x4a622f, 0x4a6399). It adds every row with the same mount flag (0x4a626b), the same class weapdef+0x5c (0x4a62ac; sub is not
compared) and condition > 0 (0x4a6300), except class 3 sub 4 and class 4 sub 4 (0x4a6283..0x4a62a0; no stock .gdf).
Each adds CAMMO.WAV and dymo on (0x4a6333). What this means:
- MGs and cannons link (class 2); all rockets and missiles link (4); so do mortars (3), flamers (5) and droppers (6).
- Turrets link only with turrets of their class; front weapons never link with rear ones.
- A linked weapon destroyed later stays in the group and plays WMISS.WAV when fired.

**Unlink** 0x4a5f50: with more than one entry, clears rec[2..7] (0x4a5feb), CAMMO.WAV and dymo off each (0x4a601c).

**Fire** (`weapon_ReadPlayerTrigger` 0x4a5870). Rows fire only when both handgun arms are holstered (0x4a58de, 0x4a58f3);
otherwise weapon_fire drives the aimed arm (slots 5 / 6, ammo > 0, 0x4a5a91..0x4a5ad6).
- Row 0..4 trigger = (row in rec[1..5] and fire held) or its hardpointN key held (0x4a592d..0x4a5954).
- At 0 condition: trigger cleared, WMISS.WAV (0x4a5a0e). Class 4 sub 4 needs lock timer inst+0x48 >= 1.6 (0x4a59ca).
- **Linked fire does not alternate.** Each instance runs its own cooldown, interval and burst timers
  (`weapon_UpdateInstanceFiring` 0x4a6470). All start on the same trigger: a salvo, with mixed weapons at their own rates.
- Out of ammo: trigger cleared, 1 s cooldown, WCLICK.WAV (0x4a67fd, 0x4a6819).

**Mission start.** `entity_InitVehicle` calls `renderer_InitWeaponPanel(1)` (0x463799): primary = first row with an instance,
row 0 in priority order, whatever its ammo or condition (0x4a46e4..0x4a470d); link mode off. Latch 0x5da7a0 keeps the
selection when the panel is rebuilt with arg 0 (video mode 0x44e3c8, in-game menu).

**Other readers.** AI and turret records set +4 through 0x4a4bd0 (0x409d56, 0x462a2d); the AI fires through `weapon_SetTrigger`.
Force feedback: cycle / link / unlink set 0x4f234c / 0x4f2350 / 0x4f2354 in the FFB block 0x4f2328; per-row effect ids come from
0x4fec80 [class x 7 + sub mod 100] (0x4a5a3f, 0x4a5a58).

**Open76 difference.** Open76 groups by ordnance id / GDFC +0x5a. The exe groups by class plus mount flag.
