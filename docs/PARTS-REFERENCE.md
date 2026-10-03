# What every part does: engines, suspensions, brakes, wheels, specials, weapons

This page explains what each part in the garage actually changes in the game. The save editor shows the same
information: [`../i76-save-editor.html`](../i76-save-editor.html) puts it after every part in the dropdowns and
the inventory list (hover a part for the full text), and `python i76-save-editor.py --parts` prints it in a
terminal. Both editors read it from one table, `PARTS_INFO` in [`../i76-save-editor.py`](../i76-save-editor.py).
The HTML page carries a copy of that table, and `tests/test_save_editor.py` fails if the copy and the original
differ.

**Every fact is tagged with where it comes from:**

| tag | meaning |
|---|---|
| **[game data]** | Read from the stock `I76.ZFS`, which is the same file (md5 `6dd57b16…`) in the lab copy and the pristine copy, using i76-map's parsers (`python data\mod\i76mod.py show zfs:compnent.cdf ENGN#0` and similar). The sandbox's `ADDON` folder replaces none of these files, so the owner's mods change nothing on this page. |
| **[RE: doc, address]** | Taken from i76-map's static reading of `i76.exe` (md5 `9a232dcc`): `subsystems/engine.md`, `physics.md`, `damage.md` and `weapons.md`, plus `data/VEHICLES.md`. Where it says "re-read", the instructions were disassembled again for this page on 2026-10-03 (capstone, pristine exe). |
| **[derived]** | Arithmetic on game data, done for this page. |
| **[community]** | Published player measurements ([WEAPON-STATS.md](WEAPON-STATS.md), Local Ditch) or the manual and FAQ ([I76-GAMEPLAY-REFERENCE.md](I76-GAMEPLAY-REFERENCE.md)). |
| **[unknown]** | Nothing found. |

**What applies to every part.** Offline, your car's component hit points (engine, suspension, brakes, wheels,
specials) are multiplied by 4 **[RE: engine.md, 0x4be1c0 = 4.0]**. Armour and chassis are multiplied by 2. The
"full condition" stored in a save is the unmultiplied number from the definition file (300 for an engine).

## Engines (`compnent.cdf` ENGN records)

The editor's ENGINES table has two numbers per row. They are the part's **full condition** (its hit points:
300, matching ENGN +0) and its **weight** (200 / 230 / 275 / 340, matching ENGN +8 mass). The editor has no
power column; the table below adds it.

| part | power [game data] | power vs the 261ci | acceleration on the Piranha [derived] | weight |
|---|---|---|---|---|
| 261ci 6 cyl (eng01) | 104,440 | 1.00x | 1.00x | 200 |
| 305ci V-8 (eng02) | 138,010 | 1.32x | ~1.30x | 230 |
| 432ci SHO V8 (eng03) | 193,960 | 1.86x | ~1.79x | 275 |
| 595ci V-10 (eng04) | 290,940 | 2.79x | ~2.59x | 340 |

- **How power becomes acceleration.** Drive acceleration = power × health × rpm curve / (mass × speed) ×
  throttle. It is capped by how much grip the rear tyres have (the car is rear-wheel drive)
  **[RE: engine.md, physics.md, 0x43c55e / 0x43c578]**. The acceleration column divides power by Jade's
  Piranha mass (1951, with the 432ci) after swapping the engine's own weight **[derived]**.
- **The gearbox is the same for every engine.** These are fixed numbers in the exe:
  - ratios 1.67 / 0.96 / 0.67 and a final drive of 3.538;
  - the rev limiter caps 1st / 2nd / 3rd at 104 / 182 / 261 km/h;
  - full-throttle upshifts happen at 62 / 106 km/h;
  - power peaks at 3500 rpm and falls to zero at 7000.

  No car file or wheel file changes any of this **[RE: engine.md, 0x4f8640, 0x46a320]**.
- **Damage** scales power by hp / max. For the player it never drops below 0.4 of full power, even with a
  destroyed engine **[RE: engine.md, 0x469fb0]**.
- **Top speed for each engine: [unknown].** Nobody has measured it. Air drag (VDFC +0x38) sets the real limit in
  3rd gear **[RE: engine.md]**.

## Suspensions (`compnent.cdf` SUSP records)

| part | handling [game data] | percent [game data] | hp | weight |
|---|---|---|---|---|
| Stock (sus01) | 1.00 | 0 | 200 | 35 |
| Sway Bars (sus02) | 1.25 | 10 | 200 | 37 |
| Coil Overs (sus03) | 1.55 | 20 | 200 | 41 |
| EtherX Rally (sus04) | 2.00 | 45 | 200 | 46 |

- **Handling** controls how hard you can corner before the car starts to slide. The slide threshold is
  2 × gravity × handling × surface grip × tyre grip × 0.25. It is computed in `physics_ComputeSteerYawRate`
  0x43ce10 and compared against at 0x43d00c for every car **[RE: engine.md; re-read]**.
  - Handling does **not** change your steering limit itself. That limit is 7.84 × tyre grip and uses the
    suspension value only on cars with flag 0x10000, which are the arcade/Taurus cars, not yours
    **[RE: physics.md 0x43cee0; re-read]**.
  - Damage lowers handling toward 0.5 **[RE: engine.md]**.
- **Percent** is used only in the suspension's own damage check **[RE: engine.md]**.
- **Spring rate, damping and ride height are not stored anywhere in the file.** Every car's wheels can travel
  ±0.25 × the wheel radius, and the suspension filter is the same fixed one for all cars
  **[RE: physics.md 0x46d820, 0x46d760]**.

## Brakes (`compnent.cdf` BRAK records)

| part | strength [game data] | hp | weight | effect offline |
|---|---|---|---|---|
| 4-Wheel Drum (bra01) | 1.0 | 150 | 12 | same as the rest |
| Disc & Drum (bra02) | 1.3 | 150 | 15 | same as the rest |
| 4-Wheel Disc (bra03) | 1.6 | 150 | 17 | same as the rest |
| Aircraft Brk (bra04) | 2.0 | 150 | 20 | same as the rest |

- **The upgrade does nothing in single player.** For a single-player car, `physics_BrakeSetStrength` 0x46a890
  throws the file's strength away and uses 2300 / mass instead. Only in network play or multi-melee is the file
  strength used, multiplied by 2300 / mass **[RE: engine.md; re-read]**.
- So offline, a better brake only adds weight. Because the strength is 2300 / mass, a heavier car brakes slightly
  worse.
- **How braking works.** Braking acceleration = strength × pedal × 8, capped by the grip of all four tyres.
  Damage scales it by max(hp / max, 0.2) **[RE: engine.md, 0x43c49a, 0x46a7f0]**.
- **The real brake upgrade is the X-Aust Brake special** (below).

## Wheels (`*.wdf`, WDFC records)

| part | size factor = starting grip [game data] | hp | weight per wheel |
|---|---|---|---|
| 13in Stock (`*_Na.wdf`) | 1.0 | 100 | 10 |
| 14in Rally (`*_Nb.wdf`) | 1.2 | 100 | 10 |
| 15in Kragers (`*_Nc.wdf`) | 1.4 | 100 | 10 |
| 16in Billets (`*_Nd.wdf`) | 1.6 | 100 | 10 |

All 70 `.wdf` files in the archive carry these same values for each letter: `wauto_*`, `wbtck_*`, `wctnk_*` and
the rest **[game data]**.

- **What grip does.** Tyre grip sets:
  - the rear-wheel drive traction;
  - the steering limit, 7.84 m/s² per unit of grip;
  - the slide threshold.

  **[RE: physics.md, 0x43c543, 0x43ce10]**
- **The size bonus does not last.** When the wheel loads, the size factor is written only into the tyre's
  *current* grip (wheel+0xc, at 0x4ae8cf). The tyre's grip *base* (wheel+0x10) is 1.0 for every wheel
  (0x46d795). The first hit that damages a tyre resets its grip to hp / max × 1.0, with a floor of 0.5
  (0x46d950..0x46d96d). From then on the size bonus is gone for that tyre, until the car is rebuilt
  **[RE: engine.md; re-read]**.
- A blown tyre's radius shrinks to 0.688 of normal **[RE: engine.md]**.

## Specials (`spc01`..`spc09`)

The def code is the special's type number. The exe builds it as `sprintf("spc%02d", type)` (0x4b1502,
format string at 0x4ffea8), so all nine name and def pairs are confirmed by the code
**[RE: re-read]**. A special is a component with 10 hp (×4 for you offline). Damage that destroys it ends its
effect, except for the two that apply once at spawn (Blower, Heated Seats) and the X-Aust latch
**[RE: engine.md, entity_SpecialCreate 0x4676b0]**. Only types 1, 2 and 4 respond to the special keys 6 / 7 / 8
(key n fires slot n) **[RE: engine.md, 0x44f5fd]**. The rest work on their own.

| special | what it does | numbers | how it's triggered | source |
|---|---|---|---|---|
| Radar Jammer (spc01) | For 8 s you are hidden from AI radar and from the radar display, and radar-guided missiles (DrRadar, Cherub) lose you as a target | 5 uses; every press costs a use, even when the jammer is already on | key | [RE: engine.md, `entity_ActivateRadarJammer` 0x461770, -8.0 at 0x4be17c]. Heat seekers should ignore it: their code is not among the jammer's readers [RE: inferred]. **Not live-tested.** |
| NitrousOxide (spc02) | Drive acceleration ×5.0 for 15 s, still capped by rear-tyre grip | 3 charges; pressing again restarts the 15 s and uses another charge | key | [RE: engine.md, `physics_FireNitro` 0x43d280, 15.0 at 0x43d2a6, ×5.0 at 0x4bd1dc; re-read]. Nitrous shares a timer with the oil-slick spin, so oil during a boost cuts the boost to 2 s [RE: static inference]. The community figure of "+50% acceleration, +20% top speed" [community] does not match the code. |
| Blower (spc03) | Drive acceleration ×1.25 | permanent | passive, set at spawn | [RE: engine.md, 0x438edb → 0x43c587; re-read]. It is only written at spawn, so it keeps working after it is shot off. |
| X-Aust Brake (spc04) | Brake input ×2, still capped by four-tyre grip | latched for the rest of the car's life: no uses, no hp check | key (press once) | [RE: engine.md, 0x44f608 sets +0xf4, 0x43ab46 doubles a negative pedal; re-read]. The manual's "passive / flavour" label [community] is wrong. |
| Structo Bmpr (spc05) | Chassis absorb multiplier 2.0 on the front and back. A hit there is fully absorbed if it is ≤ chassis × 2, and costs the chassis half as much | ×2.0 | passive | [RE: engine.md, damage.md, 0x46565b..0x4656ce; re-read] |
| Curb Feelers (spc06) | Armour absorb multiplier 1.1 on every side: a hit costs the armour damage / 1.1, about 9% less | ×1.1 | passive | [RE: engine.md, 0x465772..0x4657d8] |
| Mud Flaps (spc07) | Chassis multiplier +0.1 on every side (2.1 on the front and back with the Structo Bumper): a hit costs the chassis damage / 1.1 | +0.1 | passive | [RE: engine.md, 0x4656ef..0x465759, -0.1 at 0x4be208; re-read] |
| Heated Seats (spc08) | Every mounted weapon gets ×1.1 ammo | +10% | passive, once at spawn | [RE: engine.md, 0x438ecb → 0x4a4a40, 1.1 at 0x4beb20] |
| Cup Holders (spc09) | A hit that reaches a component does no damage 10% of the time | 10% | passive | [RE: engine.md, damage.md, `rand()%100 < 10` at 0x465b7e]. [I76-GAMEPLAY-REFERENCE.md](I76-GAMEPLAY-REFERENCE.md) lists cup holders among "minor/flavor items (some are jokes)" [community]. The code gives them a real effect. |

The panel icon `dash_mary` (type 10) has no effect found and no garage name. `tire_covr` (type 11) is cut
content: tyre covers against a wheel hazard that no stock weapon fires **[RE: engine.md]**.

## Weapons: what the shot does

Range and DPS stay where they were in the editor: measured by Local Ditch when a measurement exists, otherwise
the "~N dps spec" worked out from the `.gdf` files. This section adds what each weapon physically does.

The `t*.gdf` turret versions behave like their gun versions; they mount on the turret location (GDFC sub ≥ 100)
**[RE: VEHICLES.md]**. Two exceptions:
- the 30cal Turret fires 700 m/s rounds (the 30cal MG fires 150 m/s), with the same 500 m reach;
- the DrRadar Turret flies 450 m/s for 2.2 s (the missile flies 125 m/s for 8 s).

**[game data]**

| weapon | what it does | numbers [game data] | flight model [RE: weapons.md] |
|---|---|---|---|
| 30cal / 50cal / 7.62mm MG | Bullets in a straight line | 150 m/s × 3.33 s = 500 m. 15 / 25 / 24 per hit at 10 / 10 / 20 shots a second | `weapon_StepBullet` 0x4abe60 |
| 20 / 25 / 30mm Cannon, HADES | Shells in a straight line | 200 m/s × 2.5 s = 500 m. 45 / 60 / 150 / 165 per hit at 4 / 3 / 2 / 2 a second | 0x4abe60 |
| Tank Cannon, Police Tank Cannon (boss) | Fast shells | 900 m/s, 6000 m, 260 per hit, 1 a second plus a 2 s pause | 0x4abe60 |
| Howitzer (boss turret) | Lobbed shell | 100 m/s at 4 g, 120 per hit, 5 s pause | `weapon_StepMortarShell` 0x4ac3d0 |
| FireRite Rkt | Unguided rockets | Bursts of 3 at 4.5 a second, then a 1 s pause. 450 m/s, 1000 m, 120 explosive per hit | `weapon_StepRocket` 0x4aa5b0 |
| Aim-Nein Msl | Heat seeker | 220 explosive, 450 m/s, 1000 m, one every 2 s | `weapon_StepHeatMissile` 0x4ab920: finds a heat target again every step and points straight at it, with no turn limit |
| DrRadar Msl | Radar-guided | 410 explosive, 125 m/s × 8 s = 1000 m, one every 5 s | `weapon_StepRadarMissile` 0x4aa9f0: turns at most 3 / 15 / 20° per step (under 15 / 15-150 / over 150 m flown); gives up on a jammed or dead target |
| Cherub Msl | Radar-guided, the same guidance as DrRadar | 3200 explosive, 450 m/s, 1000 m, 3 rounds | 0x4aa9f0 |
| FlameThrower / Gas Launcher / Napalm Hose / Pyro-Tomic | A fire stream from an emitter, not a projectile | 15 / 30 / 45 / 60 fire damage per tick, 20 ticks a second | `weapon_FlameEmit` 0x443c90 (modes 0 / 1 / 2 / 2) |
| HE Mortar | Lobbed shell | 100 m/s at 4 g, 45 on a direct hit plus a 95 blast within 25 m (`xgren1.xdf`) | 0x4ac3d0 |
| WP Mortar | Lobbed shell with explosive and fire damage | The 45 direct damage is split between explosive and fire (mask 6). Blast 145 within 25 m (`xwhph1.xdf`) | 0x4ac3d0 |
| Cluster-Bomb | Splits into bomblets | Mortar flight, then 9-12 bomblets ±10 m apart going off over 1.8 s. Each does 45 plus a 45 blast within 20 m (`xclst1.xdf`) | `weapon_StepClusterBomb` 0x4ace20 |
| EZK Mortar | Lobbed shell | 8 s flight (the HE mortar's is 4 s), spread 0.01, 25 direct plus the HE 95 / 25 m blast | 0x4ac3d0 |
| Oil Slick | Spins out cars | Patches, 60 a second, each lasting 20 s; no damage. A car that touches one loses traction for 2 s | `weapon_StepOilSlick` 0x4aa150, 0x466e80 |
| Fire-Dropper | Burning patches | 60 a second, 20 s each, 15 fire damage; triggers an impact every frame a car touches it | `weapon_StepFirePatch` 0x4aa450 |
| Landmines | Mines | They tumble, settle and wait up to 1000 s. 240 explosive plus a 25 blast within 5 m (`xmine1.xdf`), and they throw the car that hits them (1, 2, 0.75) | `weapon_StepTumblingMine` 0x4a92e0 |
| Car-E-Racer | A bigger mine | 1200 explosive, 5 rounds; the weapon itself has only 20 hp | 0x4a92e0 |
| BloxDropper | Blocks | 95 damage of the "blox" type (mask 8), a softer throw (0.5, 0.5, 0.5), one every 2 s, 10 rounds | 0x4a92e0 |

**Your own shots can't hit you at first:** rockets and missiles for the first 70 m, mortars for 1 s, droppers
and mines for 2 s **[RE: weapons.md]**. Each hit's damage is split evenly across the damage types its round
carries (bullet / explosive / fire / blox) **[RE: i76-map notes, 0x4a774d]**.

## Corrections this page makes to earlier data

- **Editor catalog:** the Oil Slick and Fire-Dropper fire 60 a second in their `.gdf` files, not the 50 the
  editor listed. Fixed. The only number this changes is the Fire-Dropper's "~N dps spec" fallback.
- **Editor catalog:** the Blower (spc03) and the other specials marked "(inferred)" in the HTML are confirmed by
  the code (`spc%02d`).
- **Community data:**
  - The nitrous figure (+50% acceleration, +20% top speed) does not match the code, which multiplies drive
    acceleration by 5 for 15 s.
  - The "minor/flavor" label for the X-Aust Brake, Curb Feelers, Mud Flaps, Heated Seats and Cup Holders is
    wrong: each has a measurable effect in the code.
- **i76-map's physics.md** (lines 214 and 334, sibling repo, not edited here) says the WDFC size factor is the
  tyre's grip base. The code puts it only into the current grip, and the base stays 1.0, so the bonus is lost on
  the first hit (engine.md has this right).
- **i76-map's physics.md** (line 333) says suspension handling only matters on flag-0x10000 cars. That is true
  only of the steering limit: the slide threshold uses handling on every car (engine.md has this right).
- **Not changed, still open:**
  - The editor's community ranges for the DrRadar (3000 m) and Cherub (4000 m) are longer than the 1000 m their
    `.gdf` lifetime × speed allows.
  - The editor counts 20 lbs for each of the 4 tyre records. The `.wdf` mass is 10 per wheel, and the game adds
    2 × mass per axle slot (2 slots on the Piranha).
  - The editor's weight formula was calibrated against the in-game total, so these may cancel out; they have not
    been reconciled.

## Still unknown

- Top speed for each engine on the Piranha (needs a measured run).
- The Radar Jammer's in-game effect: read from the code, never live-tested.
- Whether the heat seeker really ignores the jammer: inferred from the jammer's reader list, not traced.
- The physical meaning of the damage types (how bullet, explosive, fire and blox damage differ once split).
