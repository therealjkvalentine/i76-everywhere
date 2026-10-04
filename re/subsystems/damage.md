# damage

A hit arrives as a **damage record**: a 16-bit side mask at +4, four `amount` dwords at +8 (one per armour side),
flag bits at +6, and more words after that. `entity_DamageAndKill` 0x463a80 works out the armour side (0..3) and the
component zone (0..6) from the hit direction. `entity_ApplyDamage` 0x465620 absorbs the record with armour
(+0x138) and chassis (+0x148); whatever gets through goes to `entity_DamageComponent` 0x465af0, which damages one
component. A hit on an already-destroyed component can **roll a kill**. When the roll succeeds, entity+0x454 gets
0x20 (or 0x4020 for component 6), and the death block turns the vehicle into a wreck and sets the object dead
flag 0x200 that the script action `isDead` reads. Scripts, input, the rules and physics can also kill directly through
`object_Destroy` 0x4652b0. Static reading of md5 9a232dcc (2026-09-26). Every address below is cited in the members'
evidence; the conflict with capture 012 is written up in `status/tasks/armour-hunt.md`.

## Flow

1. `entity_ApplyDamage` 0x465620 (entity, side, record, is_player). For each side bit it checks
   `amount > armour[side] * mult`:
   - if so, `armour[side]` and the +0x178 copy are both set to 0 and the rest passes through;
   - otherwise both drop by `amount / mult` and the hit is fully absorbed.

   Chassis (+0x148 / +0x18c) and the engine words (+0x188 / +0x19c, the side-4 entries) follow the same pattern.
   Unlimited Armour / Chassis (`options_play_flags` 0x654b98 bits 8 / 0x10) zero the amount instead, but only when
   `is_player` is set (`object_IsPlayer`) and the game is not networked (0x452d20).
2. `entity_DamageComponent` 0x465af0 (entity, zone, record, allow_kill, health_pct):
   - **Absorb.** A type-9 component in slots 17..19 absorbs the whole hit 10% of the time (`rand()%100 < 10`,
     0x465b7e).
   - **Target.** If record+6 bit 0 is set and `health_pct` < **33.0**, the target is component **6**. Otherwise it is
     `zone_components[zone][rand() % zone_component_count[zone]]`, which never picks 6.
   - **Live component.** The damage goes to it through 0x462040.
   - **Destroyed component, allow_kill set.** It is killed when `total * k > (rand()%100) * cur/max`:
     - `total` is `entity_DamageRecordTotal`;
     - `cur` and `max` are `entity_ComponentHealth` and `entity_ComponentMaxHealth` summed over the first 20 slots;
     - **k = 0.1** for the local player offline (0x465caf), **2.5** otherwise (0x465cbb).
   - **Kill.** Success sets +0x454 |= 0x20, or 0x4020 when the component is 6. A destroyed component that doesn't roll
     still absorbs up to a quarter of its max health.
3. `entity_DamageAndKill` death block (0x463f80). Once +0x454 has 0x20 it prints the kill messages, then:
   - with **0x4000** (critical): flags |= 0x80008000, `state_timer` = 10.0, explosion sound, and
     `object_SetFlagsTree(obj, 0x200)`;
   - otherwise: `entity_Wreck(obj, 1)`.

   The entity update 0x465370 also wrecks anything with 0x8000 set and 0x4000 clear.
4. `object_IsDead` 0x40b840 = object+0x10 & 0x200.

Direct kills: `object_Destroy` 0x4652b0. It does nothing if 0x8020 is already set; otherwise it sets 0x20 and runs
the death block with no damage record. Its callers:
- `fsm_Destroy`
- `input_ApplyToEntity` when `input_self_destruct` 0x5367f9 is set; the multiplayer menu action 0x495a50 sets that
  byte, and so does the key handler 0x44e030
- WinMain on the team-score loss
- 0x436ff0 impact speed
- 0x438fd0 height (entity+0x474 − y > **35.0**)
- 0x454340 (network)

The network mirror 0x464890 copies remote deaths from packets.

Offline player bonus: `entity_InitVehicle` 0x463120 **doubles** armour, chassis, both maxes and both 5-entry banks (fadd st0,st0 at
0x463673), and multiplies component health (engine, suspension, type 20, brakes, wheels, specials) by **4.0**
(0x4be1c0, 0x463702..0x463754), when `object_IsPlayer` is set and the game is offline (corrected 2026-09-27; see
`engine.md`). This is the ×2 measured live
(capture 012, ADDON\valepre4.vcf values ×2).

## Explosion area damage (range-p-1, 2026-09-27)

`0x435120` (called by `entity_SpawnExplosion` with the template's radius and damage) tests only the horizontal (xz)
distance to each object, and scales the push by the target's own size (radius), not by the blast. Static reading;
not measured.

## Members

| addr | name | status |
|---|---|---|
| 0x463a80 | entity_DamageAndKill | proposed |
| 0x465620 | entity_ApplyDamage | proposed |
| 0x465af0 | entity_DamageComponent | proposed |
| 0x465fe0 | entity_DamageRecordTotal | proposed |
| 0x466ac0 | entity_ComponentHealth | proposed |
| 0x466b70 | entity_ComponentMaxHealth | proposed |
| 0x466c20 | entity_SideHealthRatio | proposed |
| 0x466010 | entity_SetSideDamageLevel | proposed |
| 0x466180 | entity_Wreck | proposed |
| 0x4652b0 | object_Destroy | proposed |
| 0x458810 | object_SetFlagsTree | proposed |
| 0x458bf0 | object_IsPlayer | proposed |
| 0x40b450 | object_HealthFraction | proposed |
| 0x40b840 | object_IsDead | proposed |
| 0x463120 | entity_InitVehicle | proposed |
| 0x462e30 | entity_Create | proposed |
| 0x5367f9 | input_self_destruct (global, uint8) | proposed |
| 0x654b98 | options_play_flags (global, uint32) | proposed |

Unnamed but placed: 0x462040 (per-component damage), 0x462660 (damage for objects with one hit-point word at
entity+0x508), 0x458f00 (sets 0x200 on the root of a +0x68 parent chain, once), 0x4660d0 (side damage textures
'V1 FT FT.MAP'...), 0x436ff0 / 0x438fd0 (physics kill checks), 0x464890 (network state apply).

## Tweak points (static; apply only to the sandbox copy, never the playable install)

These are pristine-exe addresses. File offset = VA − 0x401000 + 0x400 for .text and VA − 0x4bc000 + 0xbb400 for
.rdata; check with `python tools\disasm.py`. Byte-checked 2026-09-26: the pristine exe (9a232dcc), the
running reference (i76fix, 58d9dec0) and the sandbox's deployed `i76.exe` (4fabc303) all have the stock bytes below.

| effect | site | stock bytes | patch |
|---|---|---|---|
| No offline ×2 for the player's vehicle | 0x46365f (file 0x62a5f) `jne 0x463780` | `0f 85 1b 01 00 00` | `e9 1c 01 00 00 90` (always take the networked path: doubling skipped, the 0x463780 calls kept) |
| Player kill-roll factor (0.1 = hard to kill, 2.5 = as fragile as AI) | imm of 0x465caf (file 0x650b3) | `cd cc cc 3d` (0.1f) | any float, e.g. `00 00 20 40` (2.5f) |
| AI kill-roll factor | imm of 0x465cbb (file 0x650bf) | `00 00 20 40` (2.5f) | smaller = tougher AI |
| Critical-hit threshold, health % | .rdata 0x4be1d8 (float 33.0; read at 0x463db4 and 0x465ba5, both the same "below 33%" test) | `00 00 04 42` | e.g. 50.0 = `00 00 48 42` |
| Type-9 component absorb chance | 0x465b80 (file 0x64f80) | `0a` (10%) | 0..100 |
| Fall/height kill distance | .rdata 0x4bd18c (float 35.0, one reader 0x439ace) and 0x4bd190 (double 35.0, one reader 0x439e57) | 35.0 | larger = survive longer drops |

Runtime pokes (no patch):
- `input_self_destruct` 0x5367f9 = 1 destroys the player on the next input pass (0x44f58c).
  Measured live by the key path: CTRL+ALT+X detonates the player's car and is scripted as `Send-SelfDestruct` in
  `../i76-uncap-lab/autotest/lib/cheatlib.ps1`, used for every death-cam run
  (`../i76-uncap-lab/docs/framerate/MEASUREMENTS.md:151-153`). The direct byte poke of 0x5367f9 itself is still
  unpoked (corrected 2026-10-02).
- Setting `options_play_flags` bits 8 / 0x10 turns on the game's own Unlimited Armour / Chassis (offline only).

Capture 012's "+0x178 kills" result turned out to be confounded by fire rate: the dying arm took about 3× the damage
(`status/tasks/armour-hunt.md`). That fits the static reading, in which +0x178 only feeds the HUD, lights and
damage-model ratios. A clean live confirmation still needs repeated arms with the fire rate recorded.

## Damage visuals (gap-dmgspec, static, md5 9a232dcc, 2026-09-27)

A vehicle has 11 **damage parts**: 0 front, 1 left, 2 right, 3 back, 4 top (the armour sides), 5..10 = wheel slots
0..5. Each part has a **level** 0..4. Two functions turn a level into visuals:

- `entity_SetSideDamageLevel` 0x466010 (entity, part, level) picks the **VGEO damage row**:
  - Part 0..4: the body-panel object entity+0x408+4*slot, slot = table 0x4f7dc0 {0,1,1,2,3} (0x46601a, 0x466037).
    Left and right share the middle panel +0x40c, so the side hit last sets its mesh.
  - Part 5..10: the wheel entity+0x3a8+4*(part-5), and the object is the wheel's geometry child +0x64 (0x466027, 0x466032).
  - Level to row (jump table 0x4660b4): 0 and 1 -> row 0, 2 -> 1, 3 -> 2, 4 -> 3 (0x466052..0x466064).
    Wheels: level <= 2 -> row 0; level 3 or 4 -> `physics_WheelBlowTyre` and row 1 (0x466074..0x466086).
    Blowing the tyre sets radius x0.688 (0x46dde1), flag +0x44 and plays tblow.wav, once only.
  - `object_SetGeometryVariantTree` 0x4ba5f0 walks the subtree (+0x64 child, +0x60 sibling; 0x4ba619..0x4ba633).
    On each node, `object_SetGeometryVariant` 0x4465b0 follows the geometry-cache name chain `row` steps (+0x70 links,
    0x446618) and loads the name in the current LOD slot (node + lod*16, 0x446635..0x44663e; mesh 0x446691).
    So row m = VGEO damage state m (vdf.md sec. 6). If anything changed, 0x4620a0 resets [entity+0]+0x68/+0x70 (0x4660a8).
- `entity_SetSideDamageTextures` 0x4660d0 (parts 0..4 only, 0x4660de) steps the **TMT frame**:
  - Level to frame (jump table 0x466164): 0 -> 0, 1 and 2 -> 1, 3 -> 2, 4 -> 3.
  - For each face name in table 0x4f7e08 (5 x 10 x 13 bytes; counts at 0x4f7df0 = {6,1,1,5,1}) it calls
    `image_SetFaceTextureFrame`(panel, name, dim 0, frame, 1) (0x466146). Names: front `V1 FT FT/LF/RT/TP/UN` and
    `V5 FT TP`; left `V1 MD LF`; right `V1 MD RT`; back `V1 BK BK/LF/RT/TP/UN`; top `V1 TP TP`.
  - **TMT damage axis = dimension 0**, which has stride 1 (0x44a1e4..0x44a1f4): the fastest-varying axis, which is the
    last-listed dims word (art.md sec. 2). Frame name = entry+0x2c + 16 x sum(index x stride) (0x44a246..0x44a25f).

**Who sets the levels** (the thresholds are the same everywhere: > 0.75 -> 0, > 0.5 -> 1, > 0.25 -> 2, else 3;
floats 0x4be1e8 / 0x4be1dc / 0x4be1ec):
- Body sides: `entity_DamageAndKill` after each hit on side < 5 (0x463ee4), only while the car is not yet killed
  (+0x454 bit 0x20 cached at 0x463ae7, tested 0x463ed8). Ratio = `entity_SideHealthRatio` 0x466c20 =
  min(armour copy +0x178 / max +0x158, chassis copy +0x18c / max +0x168); side 4 or a zero max uses copy x 0.01
  (0x466c28..0x466c88). Calls at 0x463f38 / 0x463f43.
- Wheels: `entity_DamageComponent` when the hit component is a wheel (class 0x1e, 0x465e6b), ratio hp/max
  (0x465ea0), part 5+slot (0x465ee8, 0x465eee). Also the wheel-hazard hit (0x46709e, 0x4671c8) and the network
  mirror (0x464fa8, 0x465124).
- Wreck: `entity_Wreck`(obj, 1) sets all 11 parts to level 4 (0x4662de..0x466341): body row 3 with frame 3
  (0x46630f), wheels flat.

Level 1 changes only the texture; the mesh first changes at level 2 (ratio <= 0.5).

**Break-off.**
- Every hit that carries an impact point spawns a `CHUNK4` debris chunk there (`object_SpawnChunk` 0x4a2bb0,
  speed 2.5; 0x463b20..0x463b3a).
- Parts come off only while the car is a wreck. `entity_UpdateState` calls `entity_Wreck`(obj, 0) on every tick while
  0x8000 is set and 0x4000 is clear (0x465381..0x46538e); the first call (arg 1) sets the 10 s timer (0x4661f6).
  Each call rolls `rand()&15` (0x4664ed, table 0x466a9c):
  - 0: one wheel (rand%5, not yet off) via `object_DetachAsChunk` (0x466693);
  - 1: one weapon mount +0x3d0 (rand%6) as a `v-chnk` (0x46683a, 0x4668af);
  - 2-3: each child part with probability 1/2 via `object_ThrowDetachablePart`, which sets class **0x35**
    (0x4a1908 / 0x4a192e, called from 0x4668e7). These are the VCHK chunks.
  - 4-5: `CHUNK1` or `CHUNK2` thrown at (0, 15, 0) (0x466964 / 0x466994);
  - 6-7: a secondary `x1_cars1` explosion at a random offset (0x466a48);
  - 8-15: nothing.
  So debris comes per tick, not per second. Frame-rate dependence not measured.

**Damage smoke** (`entity_UpdateDamageSmoke` 0x466ca0).
- Input f = `object_HealthFraction`(obj) x 0.01 (0x463f53, 0x463f58), called only when f < 1.0 (0x463f65).
- For a vehicle (0x40b4e8), HealthFraction works from the engine +0x3c4, suspension +0x3c8 and brakes +0x3cc:
  - All three >= 0.9999: 28 + 72 x r, r = min over the 4 sides of min(armour +0x138/max, chassis +0x148/max) clamped
    to 0..1 (0x40b5f5..0x40b6d6, floats 72 / -28 at 0x4bc630 / 0x4bc634).
  - Any of the three < 0.9999: it returns the smallest live component ratio **unscaled** (0..1, 0x40b5e5 -> 0x40b6f0),
    so f <= 0.01. With all three dead (< 0.02 each) it returns 100.
- Smoke starts at f < 0.75 (0x466ca4), i.e. r < 0.653. Level 0, rate 0.0 for f > 0.6; level 1, rate 0.5 for
  f > 0.4; level 2, rate 1.0 otherwise (0x466cbe..0x466cf8).
  - The emitter is added once (`world_AddSmokeEmitter`, 0x466d59), sets +0x454 bit 0x100, and sits at local
    (0, 0.2, [+0x410]+0x9c), the back panel (0x466d13..0x466d31).
  - Later calls retune it (0x466d8e / 0x466d76). f >= 0.75 removes it (0x466dbe).
- The same value is the `health_pct` passed to `entity_DamageComponent` (0x463ebf), so its < 33 test is true as soon
  as any core component is scratched. In effect, handgun hits (record+6 bit 0) go to component 6, whose kill is
  the critical 0x4020 kind, once any engine, suspension or brake damage exists, instead of below 33% health. That
  part is a static reading, not measured.
- **The missing x100 is confirmed live** (2026-09-27, sandbox, `captures/014-framerate/hfrac_*.json`). Same 30 m
  drop, chassis afterwards at 92-100% per side:
  - engine intact: no smoke;
  - engine poked to 99% (1188/1200) first: bit 0x100 set, 40 live puffs.
  In stock play any core component under 99.99% makes a car smoke at the heaviest level. The fix is one multiply
  (x100) on the unscaled branch (0x40b5e5 -> 0x40b6f0).
- The return value is clamped to [0, 100] at 0x40b6f0 (0x4bc620 / 0x4bc61c); verified live: an armour offset that
  would give 112 reads 100.
- Verified value-for-value on the take-damage run (2026-10-02, `verify/oracles/REPORT.md`): both branches, 1,723
  frames, with the stock bug live (76.0 -> 35.2 -> 0.5 as armour, engine and a wheel were poked).
- `entity_UpdateDamageSmoke` runs per substep and reads the current value, so the smoke flag follows health_pct on
  the same frame; it is not hit-driven.
- **Every caller sees the bug:**
  - damage smoke and the < 33 test above;
  - `fsm_HpLesser` 0x40b7d0 (script hpLesser);
  - `ai_ShouldFleeWhenHurt` 0x417060 (the AI flees when the value is below 30 + 17 x skill, so in stock play it
    flees as soon as a core component is scratched);
  - the target-bracket readout 0x45af10 and the network state packers.
- **Opt-in fix:** i76-everywhere `music-fix`, `I76_FIX_HEALTH_PCT=1`, repoints the switch table 0x40b7b8 at a x100
  stub. Live: 99% engine, no smoke; 50% engine, smoke (`hfrac_eng99_fix` / `hfrac_eng50_fix`). It is off by
  default because missions may be tuned around the stock behaviour.
