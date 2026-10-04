# Open76 vs the i76-map specs: gap list

Scope: Open76 at `C:\Users\james\i76-map\external\Open76` (commit e39db6e, "Add more FSM actions. Fix some bugs.";
about 11.5 k lines of C#) against the static specs of i76.exe md5 9a232dcc in `C:\Users\james\i76-map`
(`REIMPLEMENTATION.md`, `subsystems/*.md`, `data/FORMATS.md`, `data/FSM.md`, `data/notes/fsm-actions.md`).
Written 2026-09-27 from a read of both trees. Nothing was run and nothing was checked live.

Conventions:
- `O76/` = `external/Open76/Assets/Scripts/`. Spec references are `file.md` plus a section name.
- For each system: **Has** = what Open76 implements; **Departs** = where it differs from our spec; **Closes** = the spec
  text that fixes it; **Spec gap** = something Open76 models that our specs do not cover, with what to reverse-engineer next.
- Open76's constants are mostly its authors' guesses. A "spec gap" means "we have no answer yet", not "Open76 is right".

Headline: Open76 is a strong **asset and format viewer** (ZFS/VFS, .geo/.vqm/.map/.tmt, .sdf/.vdf/.vcf/.gdf, .msn,
.ter, roads, cockpit sprite panels, DATABASE.MW2 menu art, Smacker via libsmacker) wrapped around a **Unity-native
game layer**. Its physics, AI, damage, weapons and sound are generic stand-ins, not the original behaviour. Of 96 FSM
actions it has cases for 39. The other 57 cover 1,649 of the 17,584 static ACTION sites (9.4%), including every
mission-outcome action. A faithful port can reuse its loaders and HUD plumbing and should replace the simulation.

---

## 1. File formats (all 30 families)

- **Has.** `O76/System/VirtualFilesystem.cs`: ZFS v1 directory, LZO (`System/Compression/LZO.cs`), .pix/.pak.
  Parsers in `O76/System/Fileparsers/`: `GeoParser`, `TextureParser` (.map, .vqm+.cbk), `VtfParser` (+ .tmt), `SdfObjectParser`,
  `VdfParser`, `VcfParser`, `WdfParser`, `GdfParser`, `MsnMissionParser`, `ActPaletteParser`, `EltParser`, `GpwParser`,
  `XdfParser` (empty stub), `PcxParser`, `FntParser`, `ShpParser`, `EfaParser`, `Mw2Parser`. Smacker through
  `O76/VideoPlayer.cs` (P/Invoke to libsmacker).
- **Departs.**
  - GDFC fields are mislabelled (`GdfParser.ParseGdf`): +0x56 (86) is read as `BulletVelocity`, but it is the **aim speed**.
    The projectile speed is ORDF +0x04. +0x5a (90) is read as `WeaponGroup`, but it is the **ordnance id**
    (`VEHICLES.md` section 6; `weapons.md` Quirks). ORDF is skipped (`br.FindNext("ORDF")`, never read), and so are the lifetime
    +0x46, spread +0x62 and class/sub +0x10/+0x14 (read into `unk*` locals).
  - `XdfParser.ParseXdf` looks for a `WDFC` chunk and returns an empty object, so blast damage and radius are never read.
  - `GpwParser` reads the first u16 after `GAS0` as `AudioRange` (never used). Per `FORMATS.md` section 8 it is the **priority**
    (default 50, +20 for the player's car); max instances, play mode (one-shot/loop/shared loop), volume % and random pitch are not read.
  - `.msn` WRLD: `MsnMissionParser` skips 30 bytes and reads only the 9 file names. It ignores the hour (+0x93), the 8
    surface-physics records (+0x97), the far clip (+0x137) and the movies (`FORMATS.md` section 2).
  - `.ter`: only bits 0-11 are read (`(tpoint & 0xFFF) / 4096` on a 409.5 m TerrainData). The AI no-go bit 12 and the
    surface type in bits 13-15 are dropped (`FORMATS.md` section 5).
  - ODEF OBJ: `IsPlayer = flags == 16` (an equality, not a bit test), and the file's **y is kept**. The exe ignores y and
    snaps the object to the terrain (`FORMATS.md` section 2).
  - SDFC health is read (`SdfObjectParser` `sdf.Health`), but the exe never reads it: hit points come from the SGEO parts (`FORMATS.md` section 3).
  - WDF radius = the bounding radius of the last WGEO part (`WdfParser`, `br.Position -= 16`). The engine uses the
    wheel's WLOC local y as the rest radius (`engine.md` vehicle-creation table; physics.md w+0x1c).
- **Closes.** `data/FORMATS.md` and `FORMATS-tables.md`, with the byte-exact parsers in `data/fmt/` (6,368 files round-trip).
- **Spec gap (most valuable in this report).**
  - **DATABASE.MW2** is 100% `unknown` in FORMATS.md (shell track), but `Mw2Parser.GetMw2` decodes the container: u32 count,
    then u32 offsets, sizes by difference. Entries are typed by content: "1.10" SHP sprite sets, RIFF WAV, EFA
    (compressed PCX, magic `EF 0A 05 01` at +4), "1." FNT, and "PROD" credits text. It also gives index enums:
    32 `Background` screens, then `TextureSet` groups at index 32 + n.
    Next: port `Mw2Parser`/`EfaParser` (LZ window 4096, code = len-3 in 4 bits : dist in 12 bits)/`ShpParser` into
    `data/fmt/`, round-trip the 8.2 MB, then cite the i76shell.dll readers.
  - **.pcx and .fnt** are `typed` only ("loader not traced"). `PcxParser` and `FntParser` exist; `FntParser` is marked
    "Doesn't really work" in `Mw2Parser.GetItem`. Use them as starting layouts for the trace.

## 2. Vehicle data (.vcf .vdf .wdf .gdf compnent.cdf)

- **Has.** VCFC names, armour/chassis F/L/R/B, the spare field, up to 3 SPEC and WEPN (mount + .gdf) in `VcfParser`. VDFC name,
  type, size, 5 LOD distances, mass, collision multiplier, drag, SOBJ, VLOC, VGEO (third-person damage rows and first-person
  parts), COLP, WLOC, HLOC (facing, mesh type) and ETBL in `VdfParser`. VTF maps and .tmt in `VtfParser`.
- **Departs.**
  - compnent.cdf is never parsed: VCFC engine/suspension/brake ids are read and never used, so there is no ENGN power,
    BRAK strength or SUSP handling.
  - VDFC mass and drag are parsed and never applied. Every car is a 100 kg rigidbody (`Resources/Prefabs/CarPrefab.prefab`
    `m_Mass: 100`, `EngineForce: 1000`, `BrakeConstant: 1000`).
  - Component health is hard-coded (`Car.cs`: `VehicleStartHealth = 550`, `CoreStartHealth = 250`,
    `TireStartHealth = 100`). WDF hp (+0x28) and the size factor (+0x30) are not used (`WdfParser` keeps `Float1..5`).
  - Mid wheels (VCF mid wdf) are built as meshes but left out of the physics (`CacheManager.ImportVcf`).
  - Weapon mass is not added to the vehicle mass. The exe sums VDFC + ENGN + BRAK + SUSP + 2 x WDFC per slot + GDFC (`VEHICLES.md`).
- **Closes.** `data/VEHICLES.md` (field -> exe reader -> runtime slot) and the `engine.md` "data file -> runtime -> physics" table.
- **Spec gap.** None of substance. Open76's `HardpointMeshType` (HLOC Top/Side/Inside/Turret picks the GGEO part set by
  the 4th letter P/S/I/T of the part name) and `FacingDirection == 2` = rear-facing are worth a check against the WEPN/HLOC
  readers. VEHICLES.md does not spell out how the mesh variant is chosen.

## 3. Mission script VM (FSM)

- **Has.** `O76/System/FSMRunner.cs` (`Step`, `LateUpdate`), `FSM.cs` (tables, `IntRef` by-reference values),
  `FSMActionDelegator.cs` (`DoAction` switch on the action **name**); machine parameter binding in `LevelLoader.LoadLevel`
  (`machine.Constants[i] = FSM.Constants[InitialArguments[i]]`); entity resolution by label + high-bit instance id
  (`MsnMissionParser`, ODEF label decoding).
- **Departs** (VM level; action-level issues are in section 20):
  - **Result flag.** `DoAction` returns 0 by default, and `Step` stores the return for every action
    (`machine.ResultReg = _actionDelegator.DoAction(...)`). In the exe, actions marked `-` leave +0x10a0 alone
    (`FSM.md` section 3 "Result"). So `set`, `goto`, `cbPrior` and the like clobber the flag in Open76.
  - **No slice limit.** The exe warns past 800 instructions and calls `exit(0)` at 1000 (`FSM.md` section 2, 0x414965).
    Open76 loops forever inside `LateUpdate`.
  - **Opcodes 2, 3, 11** (`pusha`, `pushv`, `call`) throw `NotImplementedException`. An unknown opcode throws where the exe
    logs and continues. `ret n` is treated as halt (`RST`). That is equivalent only while CALL is unused (true for shipped missions).
  - **No link step.** An unknown action name only logs at run time (`default:` case). The exe aborts at link
    (`match_prototype` 0x410a10) and aborts on `playScene`.
  - **Entity table.** There are no 200 spare slots, no `NoLabel%d` append, no special `taurus` object (0x40aeb0), and no NULL
    write-back for dying objects (`fsm-actions.md` section 4). `isDead` on a deleted object should return 0.
  - **Clock.** Open76 timers are `Time.unscaledTime`, which keeps running through pause and menus. The exe uses
    `simclock_GetAccumDt` whole seconds, which pause zeroes (`simclock.md` step 3; `fsm-actions.md` startTimer/timeGreater).
- **Closes.** `data/FSM.md` sections 1-3 (chunk, VM, the 14 opcodes, frames, the scheduling cap), `fsm-actions.md` sections 0-4, and
  `data/fmt/fsm.py` (assembler/disassembler, round trip, the stack model check over 797 machines).
- **Spec gap.** None. Our spec is strictly ahead (Open76's `i76dasm/` is superseded by `fsm.py`).

## 4. Frame loop and timing

- **Has.** Unity's loop: `CarPhysics.FixedUpdate` and `RaySusp.FixedUpdate` at the project's fixed 0.02 s
  (`ProjectSettings/TimeManager.asset`, 50 Hz). AI in `Car.Update` (per frame), FSM in `FSMRunner.LateUpdate` (per frame),
  camera in `SmoothFollow.LateUpdate`.
- **Departs.**
  - The physics runs at a fixed 50 Hz. Stock runs about 24 dt-driven substeps per second (46.9 / 31.2 ms, stepper
    count = floor(dt x 20) + 1, max 50 ms; `simclock.md` "Physics substeps"; `framerate.md` "Step rate is the physics' real clock").
    Contact push-out, rest snap, the suspension IIR and coasting loss all scale with the step rate, so the step rate matters even for a correct model.
  - The frame order differs from WinMain's: input, network, object ticks, post-tick, VM + AI, projectiles, `weapon_Update`, camera, render (`framerate.md` "How a frame runs").
  - There is no far-vehicle path. The exe gives cars beyond the camera radius + 25 m one whole-frame flat step (`physics.md` Far vehicles).
- **Closes.** `simclock.md` (dt clamp [0.001, 0.2], the first-3-frame accum rule, the pause zeroing, sim_dt capped at 1 s), and
  `framerate.md` (every per-frame constant; `I76_FIXED_STEP=24` + render interpolation as the stock-matching design).
- **Spec gap.** None.

## 5. Vehicle physics step

- **Has.** `O76/CarSystems/CarPhysics.cs`: a Marco-Monster-style bicycle model on a Unity Rigidbody. Slip angles with
  cornering stiffness -5 / -5.2, `MaxGrip` 8, a speed-scaled steer (`SteerSpeedBias` 55, `MaxSteer` 0.5), force =
  `EngineForce x Throttle`, brake = `BrakeConstant`, linear rolling resistance 15, drag 0, rest-clamp below 0.5 m/s.
  It runs **only when all wheels are grounded** (`if (!allWheelsGrounded) return;`); in the air the Rigidbody falls under
  Unity gravity -9.81.
- **Departs** (`physics.md` "One substep"):
  - Drive: stock is a = P / m x mult (x 1/v above 1 m/s), capped by rear-wheel traction grip x gn/4 x sum(rear c).
    Brake: a = strength x throttle x 8, capped by 4-wheel traction (x0.5 on handbrake).
  - Resistance: -vhat (0.1 x drag x v^2 + surface drag x sum(wheel+0x14) x gn/4), plus slope = gravity projected on the ground normal.
  - Steering: yaw rate = steer x v / (2 x wheelbase), capped at 7.84 x sum(grip). Past 2x the cap the car slides
    (`ApplySideSlipFriction`, slide yaw = steer x gear x pi). The car yaws about the rear axle.
  - Air: ballistic -9.8, and the pitch rate eases to -pi/20. It stays airborne while clearance > 0.5 m.
  - Tipped (n.up < 0.1), handbrake or gear 0 force throttle -1. The upside-down rule is `physics_CheckImpact`: an arcade/Taurus car is flipped, anything else is destroyed.
  - The blown-tyre steering pull is +-0.3, and a tyre's radius drops to x0.688 when it blows.
  - Fall kill: airborne and 35 m below the last ground height. Surface damage: above 7.65 m/s.
  - Arcade flag (Play Options bit 1) and blower x1.25: `physics.md` Tunables.
- **Closes.** `physics.md` (step order, every constant with its address, entity field map, the tunables table), plus the
  helicopter model (`physics_StepAircraft`) and the far model 0x43bdf0.
- **Spec gap.** None. Open76's weight transfer (`_heightRatio`, body pitch/roll slerp) is cosmetic. Stock body motion
  comes from the contact/rest cycle and the wheel IIR.

## 6. Ground contact: terrain and walkable faces

- **Has.** One Unity `Terrain` + `TerrainCollider` per ZMAP tile (`LevelLoader.LoadLevel`). Edges are stitched from
  neighbours (the 129th sample in `MsnMissionParser`). Ray-cast suspension (`RaySusp.SpringPhysics`: spring 4000, damping 9000,
  spring length = WDF radius). Scenery uses mesh colliders (`CacheManager.ImportGeo`). `Utils.GroundHeightAtPoint` ray-casts down from y 1000.
- **Departs.**
  - Height is Unity's terrain interpolation, not bilinear on 5 m cells (`world_GetTerrainHeight` 0x493550).
  - The normal ignores the exe's triangle-choice quirk (`physics.md` "Terrain normal quirk").
  - There is no walkable-face rule: bridges and ramps are faces with plane ny > 0.4 within +-3 m of the query y (`physics.md` "How the car meets the world").
  - No per-surface grip, drag, bump or damage (WRLD records unread). No rest snap. The stock suspension is a 2nd-order IIR
    (r 0.7, period 15 calls, 5x feed-forward, travel +-0.25 r), not a force spring.
  - Road y: Open76 re-samples +0.1 m, which matches "y ignored and re-snapped" (`FORMATS.md` RSEG). Object y: kept (see section 1).
- **Closes.** `physics.md` steps 7-8 and "Step-rate dependent state"; `FORMATS.md` sections 2 and 5; the renderer terrain quadtree (visual only).
- **Spec gap.** None.

## 7. Object/vehicle collision

- **Has.** Unity physics: car mesh colliders from VGEO LOD 0 (`CacheManager.ImportVcf` "ChassisColliders"). A comment
  there guesses the original uses "two large boxes" (COLP inner/outer), which is commented out. `Sign.OnTriggerEnter`
  knocks a sign loose above 2 m/s (`AddForce(up x 500)`). Buildings swap to the wrecked part (`Building.ApplyDamage`).
- **Departs.**
  - Stock collision runs once per rendered frame with the frame dt (0x4349c0). Box shapes come from the VDF COLP; the
    box-vs-box test ray-casts 8 points on the mid-height rectangle; scenery is a node tree (boxes, meshes, spheres x0.75);
    only the last contact record in a frame survives (`physics.md` Objects and vehicles).
  - Response: restitution e = clamp(1 - 0.75 cos^2, 0.25, 1), a 4 m/s push-out, rigid-rigid momentum exchange at 0.5, and angular
    clamps pi/2, pi, pi/4. Impact damage K is 6.673e-5 (rigid other) or 1.001e-4 (static).
  - Break-off chunks bounce at 0.25 and expire after 15 s (`physics.md` classes).
- **Closes.** `physics.md` "How the car meets the world" + step 2; `damage.md` (collision damage entry).
- **Spec gap.** The **class 4 breakable knock-off** trigger (Open76: any rigidbody faster than 2 m/s). Our class table names
  init 0x46f980 / damage 0x46f9a0 but gives no threshold. Next: read 0x46f9a0 and the class-4 collide slot (+0x24).

## 8. Engine, gearbox, brakes

- **Has.** Nothing functional. `CarPhysics` declares `RPM`, `GearRatios` and `DifferentialRatio` and never uses them.
  `GearPanel.ActiveGear` is set once to 'D'. Engine start/stop is a sound timer (`Car.ToggleEngine`).
- **Departs** (`engine.md` Model): gear state 0 R / 1 N / 2-4; lever P R N D 2 1; rpm = 850 + 126.81 x R[g] x v;
  R = {3.0, -, 1.67, 0.96, 0.67}; power = P x f x rpm x (7000 - rpm) / 3500^2; engine health floor 0.275 AI / 0.4 player;
  shift 62/106 km/h up and 60/98 down at full throttle, 25/40 up and 12/31 down closed; free rev toward 1050 + 4950 x throttle;
  the offline brake strength is 2300 / m for every car; gauges: speedo 1.8533 deg/mph (0..150), tach 0.028125 deg/rpm
  (<= 8400); the speedo m/s-in-air quirk.
- **Closes.** `engine.md` completely (live-checked rpm law, 61 of 61 samples).
- **Spec gap.** None. The 1->2 shift logged at 28 km/h is our own open item (`engine.md` Live check), not an Open76 finding.

## 9. Damage, armour, wrecks

- **Has.** `Car.ApplyDamage`: the hit side comes from the Euler z of `FromToRotation(up, normal)` in 90-degree sectors.
  Projectiles hit armour and forces hit chassis. Overflow below 0 goes to a random core system (Vehicle/Brakes/Engine/Suspension).
  Death when `Vehicle` hp (550) <= 0 (`Car.Explode`: up impulse 5 x mass, `xcar` sound, components deleted).
  Damage visuals: whole-car VGEO "Health n" rows plus the TMT texture frame chosen by overall health (`SetHealthGroup`,
  `CacheManager.GetMaterial` `textureGroup`).
- **Departs** (`damage.md` Flow):
  - The damage record carries a side mask and 4 amounts. Absorption is `amount > armour x mult`: armour zeroes and the rest passes through.
  - Pass-through goes to a component zone (0..6) chosen from the hit direction. A type-9 component in slots 17..19 absorbs 10%
    of hits. Below 33% health a flagged hit (the handgun) goes to component 6.
  - A hit on a destroyed component rolls a kill: total x k > rand%100 x cur/max, k = 0.1 offline player, 2.5 otherwise.
  - Death is a critical explosion (10 s timer, flag 0x200) or a wreck. The fall-kill and impact kills go through `object_Destroy`.
  - Offline player bonus: armour and chassis x2, component hp x4 (`engine.md` Corrections).
  - Explosion area damage is horizontal only and scales with the target's radius (`damage.md` Explosion area damage).
  - Unlimited Armour / Chassis zero the amount (`cheats.md` section 1).
- **Closes.** `damage.md` (with patch sites), `cheats.md` section 2 (entity layout, repair recipe), `physics.md` smoke thresholds 0.75 / 0.6 / 0.4.
- **Spec gap.** **Damage visuals.** Open76 swaps whole-car damage meshes and TMT frames on one health number. We name
  `entity_SetSideDamageLevel` 0x466010 and the side-texture writer 0x4660d0 ('V1 FT FT.MAP') but do not document the
  thresholds, which TMT dimension is the damage axis, or when VGEO damage rows 1-3 are shown.
  Next: read 0x466010 / 0x4660d0 and the VGEO row selection; confirm live on a poked armour value.

## 10. Weapons and projectiles

- **Has.** `O76/CarSystems/WeaponsController.cs` and `Components/Weapon.cs`: weapons are sorted by rear-facing, then by
  GDFC +0x5a ("WeaponGroup"). Space fires the active group and 1-5 fire single weapons. Bursts run as coroutines.
  `cammo.gpw` plays when empty and `cwstat.gpw` when broken. The HUD shows ammo digits. `O76/Projectile.cs` flies straight
  at the GDFC +0x56 speed for 10 s, hits by trigger, and applies `DamageType.Projectile` with the damage from GDFC +0x2c.
  Specials (`SpecialsController`, `Components/Special.cs`) only count ammo (jammer 5, nitrous 3, others 1, rate 1 s) and have no effect.
  AI cars fire only through the debug key Z (`Car.FireWeapons`).
- **Departs** (`weapons.md`):
  - The speed is the ORDF speed, not GDFC 86. Lifetime is GDFC 70 (0 means 5 s), not 10 s.
  - Spread is one-sided, yaw-only, and applies to about 25% of MG rounds.
  - Every ordnance id has its own flight model: bullets ballistic with ORDF gravity; the rocket eases to speed at 0.5 dt; the
    heat missile snaps to its target; the radar missile turns only when dot < 0.998, clamped to 3/15/20 deg per step; mortar 4 g;
    cluster 9-12 bomblets; mines tumble; oil slick gives 2 s of traction loss; fire patch; flamers are renderer-driven.
  - Shooter immunity: 70 m for rockets and missiles, 1 s for mortars, 2 s for mines and droppers.
  - Damage x the difficulty factor (2.0 / 1.0 / 0.75 for the player offline) is split evenly over the ORDF damage mask.
  - MG and handgun rounds are batched per frame. Weapons never jam offline. A weapon at 0 HP plays WMISS.WAV.
  - Blower x1.25, exhaust brake x2, SPEC 8 ammo x1.1 (`engine.md` table).
- **Closes.** `weapons.md` (fire chain, GDFC/ORDF table, projectile types, flamers), `VEHICLES.md` section 6.
- **Spec gap.**
  - **Weapon grouping and cycling.** Open76 groups by ordnance id and splits front from rear (+100). We name cycle
    0x4a5be0, link 0x4a6170 and unlink 0x4a5f50 but not their grouping rule. Next: read those three with the HUD diode writer 0x4a4d50.
  - **Specials.** Jammer duration and uses, nitrous (probably flag 0x800, drive x5, `engine.md`), structo bumper, curb
    feelers, mud flaps, cup holders, special fire rate and ammo, and "special 0xb" (Open76's enum ends at 9: check the stock
    SPEC ids in `vehicles.csv`). Next: `veh_AttachSpecial` 0x467280 and the input path that fires specials.

## 11. AI drivers

- **Has.** `O76/CarSystems/CarAI.cs`:
  - `Navigate`: road-following between FSM path nodes, keeping 2 m to the right of the road (`RoadOffsetDistance`).
  - Bang-bang throttle, brake when more than 5 m/s over target, `SmoothDampAngle` steering (gain 1.5).
  - Waypoint reached within 33.5 m (`Constants.PathMinDistanceTreshold`, "estimated").
  - `SetTargetPath` starts at the **nearer end** of the path ("correct if you look at the training mission").
  - `SetFollowTarget` aims 20 m ahead of the leader.
  - `setSkill`, `setAgg` and `setMaxAttackers` are stored and never read. There is no combat AI.
- **Departs** (`ai.md`):
  - AI writes the same three inputs as the player; decisions run once per frame.
  - 34 behaviours in the table at 0x4c3e00, with a behaviour stack and an aggression-weighted attack selector 0x412680.
  - Routing is a time-sliced path search over terrain cells (no-go bit 12, surface cost 0x40e9d0).
  - Throttle = speed error / sim_dt, less drag and rolling, over capacity, capped at 0.75 + 0.25 x skill and at grip.
  - Steer = gear x skill x heading error / (sim_dt x k x v). Avoidance tests one-step-predicted candidates (terrain, cars, colliders, projectiles).
  - Perception: `ai_CanSee`, a 7 m blocked probe, and event stamps for isShot / isRammed / isAttacked. Engine-off cars are invisible.
  - The skill tables are 0x5fcb7c / 0x5fcb9c / 0x5fcbdc / 0x5fcbbc.
- **Closes.** `ai.md` (behaviour table with enter/update/exit addresses, AI block fields, frame-rate notes), `fsm-actions.md` (goto/follow/evade/race field writes).
- **Spec gap.**
  - **Path-following geometry.** Our spec does not state the waypoint arrival radius, whether `goto` starts at node 0 or
    at the nearer end, or how the car advances along a path (0x420ea0 enter, 0x420ed0 update, 0x420f80 exit). Open76's
    nearest-end rule comes from a two-car T01 path. Next: read those three and test on T01/A01.
  - **Follow formation** (0x41eef0 / 0x41ef40): what offA/offB mean (Open76: x offset + speed; `fsm-actions.md` section 6 says
    offsets) and when `isAtFollow` latches ai+0xa988.
  - **Road use.** Does routing prefer RSEG roads, and is there a lane offset? `ai.md` mentions "same road" tests
    (0x41c1d0) and road tactic modes but not road-following for goto.

## 12. Cameras and cockpit

- **Has.** `O76/Camera/CameraController.cs`:
  - F1 = cockpit at VLOC 0 with keypad head-look (targets -14 deg pitch, +-90 / 180 yaw, slerp 6/s).
  - F2 = `SmoothFollow` (distance 10, height 5, damping 2/3). F3 = VLOC 1 (hood). F4-F7 = wheel-mounted cameras.
  - Script cameras: `CameraManager.PushCamera/PopCamera` spawn a new Unity camera per push. `FSMCamera.FollowPath` moves along a path at a speed.
- **Departs** (`camera.md` Views):
  - 17 view ids with transition table 0x4c2994: cockpit (4 dt easing, sway, 2D/3D dash toggle), binoculars (zoom 0.5..8),
    orbit (track distance 1..10 x radius, cap 150, pitch 1-90), chase (15 deg, yaw pi), hood (FOV 2pi/3, offset 0 / 0.7 / 3.5),
    missile cam (5 m, 20 deg, 1 s linger), enemy/target views (3 m up, 7.5 m back, 3 s linger), overview, and the tunnel cam in class-0x5c volumes.
  - `PopCamera` calls `SetActive(false)` on the camera it returns to (a bug), and pushCam does not clear binoculars (`fsm-actions.md` pushCam).
  - `camF12`, `camPosDir` and `camTransDir` are missing.
- **Closes.** `camera.md` (views, keys, controller block, 8-deep stack), `fsm-actions.md` section 2 camera rows, and section 6 arg orders.
- **Spec gap.** None for views. The script camera functions 0x49d4a0 / 0x49d5f0 / 0x49d740 / 0x49dac0 / 0x49dda0 are named
  but their motion (path speed units, look-at smoothing, arrival test node + 2 >= n) is only partly written up. Low priority.

## 13. HUD, radar, cockpit instruments

- **Has.** Cockpit panels painted into the first-person texture through .elt sprite atlases (`O76/CarSystems/Ui/*.cs`,
  `System/SpriteManager.cs`, `System/ReferenceImage.cs`), keyed by VDF ETBL panel ids "RAD", "SYS", "GER", "CMP", "WEP" and "SPC".
  - `RadarPanel`: 30-frame sweep `zradf0NN` / lock `zradb0NN` over 5 s, 100 / 500 m ranges, 2x2 blips fading green over 5 s,
    CGROWL on a new contact, CRADAR on the sweep, range_pos/led_pos sprites.
  - `SystemsPanel`: zsye.map damage diagram, 5 health groups. `WeaponsPanel`: zdue.map on/off sprites **by hard-coded
    weapon name**, 4-digit ammo. Diodes in zdde.map (off/green/yellow/red/drk).
  - `CompassPanel`, `GearPanel` (prnd arrow). No speedo/tach needles.
- **Departs.**
  - Radar contacts are admitted to 600 m whatever the range; R only rescales the display (100 / 600, table 0x4f7608).
  - Engine-off cars are invisible to the radar. A lock pings every blip in the wedge (`camera.md` Radar).
  - Gauges: VLOC 35 speedo / 36 tach needle objects (`engine.md` Gauges).
  - GDFC rev 8 already carries the enabled/disabled sprite names (`GdfParser` reads them, `WeaponsPanel` ignores them;
    `VEHICLES.md` sounds/flash row +0x84/+0x94).
- **Closes.** `camera.md` Radar/HUD, `engine.md` Gauges, `renderer.md` "instrument overlay gate".
- **Spec gap** (REIMPLEMENTATION marks HUD drawing "partial"; Open76 shows exactly what is missing):
  - **Radar animation.** Sweep frame count and period, blip colour ageing, and when the lock sprite set replaces the sweep.
    Next: read the blip routine 0x460310..0x460a70 and the "trail = min(trail + 3, 0x69)" 1 Hz loop in 0x45faf0.
  - **Diode thresholds.** Weapon condition -> diode colour (0x4a4d50) and component health -> damage-diagram sprite suffix.
  - **ETBL label -> widget map.** Open76's label names (`num_thous_N`, `sp_dymo_N`, `bracket_N`, `separator_N`,
    `compass_window`, `prnd`, `range_pos`, `led_pos`) are search keys for the exe's .elt consumers. We have the grammar, not the consumers.

## 14. Renderer rules (LOD, far clip, sky, clouds, lights, shadows, mirror)

- **Has.** Unity rendering of .geo meshes with palette materials (`CacheManager.GetMaterial`: translucency when surface
  flag 2 is 5 or 7; vehicle 'V' textures through VTF/TMT), one Unity Terrain layer tiled at texture size / 10, roads as quad
  strips with a hard-coded texture per type (`RoadManager.CreateRoadObject`: r2ayr_51 / r2dnr_37 / r2wnr_39). The sky is
  a scrolling textured plane that follows the camera (`Sky.cs`).
  Lighting uses palette entries: light colour = palette[176], background/fog = palette[239], ambient = palette[247] (`LevelLoader`).
- **Departs** (`renderer.md` Rules):
  - Painter's algorithm in 1 m depth buckets over [-300, 3796) m.
  - Pixel-size object LOD (LODs 1-2 collapse to 0 with Object Detail on). The terrain quadtree has Low/Med/High constants.
  - Shading = depth term x N.sun x intensity + ambient, from the time-of-day table 0x4fa0b0, indexed by the WRLD hour (unread in Open76).
  - Night-only dynamic lights (4 strongest, spots) and headlight beams.
  - Roads: .rtm manifest (10 textures per type % 3), near/far texture sets at 60 m, 450 m cull.
  - Ground clutter in 100 m cells; the horizon's 16 .hzd strips; clouds as a dome; shadows within 50 m; far clip = Visibility Range ? WRLD far : 150 m.
  - The rear mirror has levels 0 / 1 / 2 (`options.md`).
- **Closes.** `renderer.md` (frame order and the full rules table), `options.md` (Visibility Range, mirror levels), and the
  software rasteriser section (a port can rebuild the lighting tables from the palette).
- **Spec gap.** None. The palette slots Open76 uses (239 = sky/background) agree with `renderer.md` "clouds off: palette 0xef".

## 15. Sound

- **Has.** Unity AudioSources: .gpw 3D with rolloff 5-75 m, .wav 2D (`CacheManager.GetAudioSource`).
  - Engine loop and start chosen by **VDFC size** (`Car.UpdateEngineSounds`: size 1..6 -> eishp / eihp / einp1 / eisv / eimarx / eitank),
    with pitch from speed over invented gear bands (`Car.Update`).
  - Surface loop vcdgrav / vcddirt chosen by a road collider tag, volume = speed x 0.025 (`CarPhysics.UpdateSurfaceSound`).
  - Landing vland / vlanding after more than 0.75 s airborne.
  - CB radio `RadioManager` (section 16).
- **Departs** (`sound.md`):
  - One manager with priority voice stealing (the player's engine loop at 0x4f); voices beyond 600 m stopped and parked; a percent-to-millibel table.
  - Engine sounds come from the **engsnd.dat** row for the ENGN id (loop, horn, three ignition sounds by engine health), not
    from VDFC size, which only feeds the multiplayer armour budget (`engine.md` table).
  - Vehicle events 1-16. Surface sounds come from the .ter surface type (table 0x4bd0d0).
  - The options value 1 is treated as 0. CD music is MCI.
- **Closes.** `sound.md`, `FORMATS.md` sections 8-9 (engsnd.dat grammar), `physics.md` (vtcoll / vland / vvbo1 triggers).
- **Spec gap.**
  - **Engine pitch.** How the engine loop's frequency follows rpm (`sound_GetEngine*`, the eng+0x2c row index).
  - **Rolling-surface sound.** Loop choice and volume versus speed.
  - **Distance attenuation.** The volume-versus-distance law under the 600 m cull.
  Next: read `sound_StartObjectSound` 0x421b40's parameter setup and the engine-loop refresh at entity+0x10c.

## 16. Options, Play Options, built-in cheats; CB radio

- **Has.** Its own menus (`O76/Menus/*`): Options (Abort/Graphic/Audio/Continue), Graphics (resolution, Unity quality, VR),
  and Audio (three placeholder `Noop` items). Debug keys: K kills the player, Z makes AI fire, S toggles the engine, E/R/T/Y work the radar (`CarInput.cs`).
  CB radio: `RadioManager` with a FIFO. Prio 1 goes to the front, prio 3 to the back, others to the back with a log line.
  A line is dropped at dequeue if its speaker is dead, and a playing line is cut when its speaker dies. `stopCB` stops the current clip only.
- **Departs.**
  - No option block (0x654b80, saved copy +0x60, the msg 6/7/8/9 protocol), no Play Options bits (arcade, no salvage, ammo,
    armour, chassis, wiper), no difficulty factor, no cheat codes (wiggleburger, getdown, flflat...), no cheats marker, and no
    0xb outcome (`options.md`, `cheats.md`).
  - CB queue rules: prio 1 **flushes**; a busy queue drops prio 5 and drops prio 6 when the head is below 5; prio < 5 flushes
    when the head is above 4. `STOPCBXX` blocks all later CB, and `killCB` flushes (`fsm-actions.md` section 4 "CB radio queue").
    CB needs voice level and channel options >= 2 (`sound.md`).
- **Closes.** `options.md`, `cheats.md` (switches, code paths, patch sites), `fsm-actions.md` CB queue.
- **Spec gap.** **CB speaker death during playback.** We know a dead speaker is dropped at enqueue (0x423620); Open76 also
  cuts a line mid-play. Next: read the CB playback pump next to 0x423620 / 0x423a80.

## 17. Game states, mission load, campaign flow

- **Has.** `MainMenu` (DATABASE.MW2 art) launches a01.msn or t01.msn directly (`MainMenu.cs` lines 195/200) and plays
  INTROF01 / CREDF01 through libsmacker. `LevelLoader.LoadLevel` builds the terrain, objects, roads, fences (LDEF) and FSM.
  For A01 it hard-codes the player car `vppirna1` -> `vppa01`.
- **Departs** (`mission.md`):
  - Game states 0..0xb and play modes 1 / 2 / 4 / 8 / 0x10 / 0x20 (pause, map screen, notepad, in-game menu, cutscene).
  - Load order WDEF, TDEF, RDEF, ODEF, LDEF, ADEF with the object-registration hooks. The objective list and failure lines come from .npt.
  - success / successAll / failAllObj with their delay, then the mission-over menu, salvage (.fsi, wreck export, tier gating),
    vehscn.vsf, and the trip-scene counter handed to the shell.
- **Closes.** `mission.md` (states table, load order, persistence), `FORMATS.md` section 9 (.npt/.fsi), and `fsm-actions.md` objectives.
- **Spec gap.** **Player car for scripted missions.** Open76 needs a hard-coded swap for A01. In the exe the car comes from
  the shell's player block (0x5dcea9 -> 0x5dd370 for play modes 2/3/4; `mission.md` state 7). How the ODEF player object
  is matched and replaced by the shell's car is not written down. Next: trace 0x5dd370's reader in the ODEF/vcf load (0x4b8230 / 0x4ad6f0).

## 18. Saves (.cmp, savegame.dir, vehscn.vsf, I76PLYR.DEF)

- **Has.** None.
- **Closes.** `FORMATS.md` (.vsf, I76PLYR.DEF 96-byte options block), `mission.md` Persistence, and i76-everywhere `docs/SAVE-*`. The shell-DLL writer is the shell track.
- **Spec gap.** None versus Open76.

## 19. Networking

- **Has.** None (only spawn/regen prefabs placed from ODEF class 1 'spawn' / 'regen' in `LevelLoader`).
- **Closes.** `network.md` (ANet session, player table, 17 packet types, 'ST' mirror) is partial and not checked live.
- **Spec gap.** None versus Open76.

---

## 20. FSM actions: Open76 coverage against `data/notes/fsm-actions.md`

**Implemented in `FSMActionDelegator.DoAction` (39):** null, true, inc, dec, set, isGreater, isLesser, isEqual, rand,
startTimer, timeGreater, isKeypress, pushCam, popCam, camObjObj, camObjDir, camPosObj, camTransObj, camIsArrived, goto,
sit, follow, isAtFollow, teleport, teleportOffset, isArrived, isWithin, isWithinNav, isWithinSqNav, isDead, isAttacked,
setSkill, setAgg, setMaxAttackers, setAvoid, cbPrior, cbFromPrior, stopCB, isCBEmpty.

**Unimplemented (57; static use count from `FSM.md` section 3):** cb 225, failAllObj 182, attack 171, isEqualId 98,
whoAttacked 95, success 87, reveal 82, killCB 72, hpLesser 68, isGroovesFault 57, startCar 53, nearestEnemy 40, control 40,
successAll 34, evade 32, destroy 30, allEnemyDead 25, hide 25, isAirborne 24, setHeliHeight 22, setSiren 21, race 19,
isWithinEnemy 18, isShot 17, triggerGate 17, guard 16, nearestBlg 15, camF12 14, camPosDir 12, setArtillery 9,
toggleAvoid 7, setLights 6, whoShot 5, setArtilleryRate 3, fail 2, playMovie 2, isRammed 1, timeLesser 1, driveControl 1,
controlDone 1; and, unused by every mission: behave, do, whoRammed, failAll, playScene, false, test, ammoLesser, isLit,
setId, camTransDir, allBlgDead, controlAll, setUserRadar, cbFrom, salvage, canSee. Total 1,649 of 17,584 static sites.
Missing all of success / successAll / fail / failAllObj / reveal means **no mission can be won or lost** in Open76.

**Implemented but wrong** (new here unless marked [§6], meaning already in `fsm-actions.md` section 6):
- `startTimer` / `timeGreater`: Open76 uses the variable's *value* as an index into a 10-slot float array
  (`fsmRunner.Timers[timerIndex] = Time.unscaledTime`). The exe writes `*t = ftol(accum seconds)` into the variable and
  compares `(float)(t0 + secs) < ftol(now) + 0.5`. Scripts that copy timers break, and a value >= 10 throws.
- `isWithinNav`: the exe measures the 2D distance to **node 0 only**. Open76 uses the distance to any polyline segment (`CarAI.IsWithinNav`).
- `isWithinSqNav`: the exe tests |dx| < r and |dz| < r against node 0 (a box). Open76 calls the polyline test with sqrt(r),
  so a 275 m box becomes a 16 m corridor.
- `teleportOffset`: the exe offsets by (dx, dz) / 100 (cm). Open76 adds them raw, in metres.
- `teleport` [§6 for the arg]: the 4th arg is the heading (0..360 deg). Open76 uses it as a height and also starts a goto on the path (`SetTargetPath`), which the exe does not.
- `isAttacked`: always 0, because `Car.Attacked` is never assigned. The exe returns ai+0xa6dc this/last frame and consumes it.
- `setAvoid`: the exe sets ai+0x9d14 = int. Open76 reads the 2nd arg as an entity index and does nothing.
- `setSkill` / `setAgg`: raw values stored and never read. The exe indexes the skill tables and sets aggression - 1 (`fsm-actions.md` rows 69/77).
- `isKeypress`: Open76 uses Space. The exe returns 0 while paused and matches the skip key's map char '"' (inferred).
- `rand`: Unity `Random.Range`, not the CRT `rand() % n`, so runs are not reproducible against the original.
- `cbPrior` / `cbFromPrior` / `stopCB`: queue semantics as in section 16.
- `camTransObj` arg order, `camObjDir` angle slots, `follow` args [§6]. `camObjObj`: Open76 maps (dx, dy, dz) to Unity
  (x, z, y) (`localPosition = (x, z, y) x 0.01`). Check it against 0x49d5f0's axis order.
- `goto`: starts at the nearer path end (section 11 spec gap). `sit`: brake = 1 plus a path clear, close to behaviour 0x1f.

---

## 21. Spec gaps to reverse-engineer next (from sections 1-17)

> **(2026-10-02)** Items 2-9 were closed statically in wave 6 (2026-09-27, `status/GOAL-COVERAGE.md:106-108`): AI
> path following, damage visuals, the special-equipment table, HUD drawing, weapon groups, engine pitch and 3D
> sound, player-car choice, CB rules — each now has a spec section in `subsystems/`. Item 1 (DATABASE.MW2 and the
> EFA / SHP / FNT / PCX decoders) remains open. Backlog P4-08: mark each closed item with the spec section that
> closed it; the list is kept as the index of what was asked.

1. DATABASE.MW2 container and EFA / SHP / FNT / PCX decoders (section 1). Import Open76's layouts into `data/fmt/` and round-trip.
2. AI path following: arrival radius, start node, waypoint advance (0x420ea0 / 0x420ed0 / 0x420f80); follow offsets (0x41ef40) (section 11).
3. Damage visuals: 0x466010 / 0x4660d0 thresholds, the TMT damage axis, VGEO row selection (section 9).
4. HUD drawing: radar sweep and blip ageing (0x460310..0x460a70), diode and damage-diagram thresholds (0x4a4d50), ETBL label consumers (section 13).
5. Specials: effects, uses, rates; the special 0xb identity (0x467280) (section 10).
6. Weapon group / cycle / link rule (0x4a5be0 / 0x4a6170 / 0x4a5f50) (section 10).
7. Engine-loop pitch versus rpm, rolling-surface sound, distance attenuation (section 15).
8. Player-car substitution for scripted missions (0x5dd370) (section 17).
9. CB playback when the speaker dies mid-line (section 16); class 4 breakable knock-off threshold (0x46f9a0) (section 7).

## 22. Prioritized top 10 for a faithful port (Open76 as the base)

1. **Physics core.** Replace `CarPhysics` / `RaySusp` / Unity gravity with the `physics.md` substep pipeline on a fixed
   ~24 Hz step (stepper semantics, `framerate.md`) plus the far-vehicle model. Feed it real data: VDFC mass and drag,
   compnent.cdf ENGN / BRAK / SUSP (parse it), WDF hp and size, the WRLD surface records, the 2300 / m offline brake. Everything
   downstream (AI, damage, feel) depends on this.
2. **Engine and gearbox** from `engine.md`: rpm law, power curve, auto shifts, free rev, health floors, gauges including the speedo quirk.
3. **Ground and collision.** Terrain height and normal sampled from the .ter words (bilinear, normal quirk, walkable faces
   ny > 0.4), ODEF y snap, COLP box shapes with 8-point sampling, the per-frame contact records and impulse constants
   (`physics.md`). Drop Unity mesh colliders from the simulation.
4. **FSM VM fidelity.** Leave the result flag alone for `-` actions, store timers as values on the accum clock, fix
   isWithinNav / isWithinSqNav / teleport / teleportOffset / setAvoid, add the 1000-instruction cap, link-time prototype
   matching, and entity-table semantics (spare slots, NULL write-back) (sections 3 and 20).
5. **Mission outcome and objectives.** success / successAll / fail / failAllObj / reveal with their delays, .npt objectives,
   game states and play modes (pause, map, notepad, cutscene), the mission-over menu (`mission.md`). Until then no mission can end.
6. **Damage model** (`damage.md`): damage records, side absorption, component zones and the kill roll, wrecks and the critical
   timer, player x2 / x4 bonuses, collision damage K, explosion area damage; then isShot / isRammed / isAttacked / whoAttacked / hpLesser.
7. **Weapons.** Fix the GDFC field mapping (86 = aim speed, 90 = ordnance id), parse ORDF / XDF, implement the per-ordnance
   step functions, spread, lifetime, shooter immunity, damage masks, the difficulty factor and flamers (`weapons.md`); specials' physics effects.
8. **AI behaviours** (`ai.md`): the behaviour stack and attack selector, the path-search routing for goto / evade / race,
   follow / guard / sit / hide, throttle and steer laws with the skill tables, avoidance, perception; then attack / guard /
   evade / race / hide / nearestEnemy / allEnemyDead / control* actions.
9. **Sound and CB.** A 600 m voice manager with priorities (GPW header fields), engsnd.dat engine sounds, vehicle events,
   and the CB queue priority and STOPCB latch rules (`sound.md`, `fsm-actions.md` section 4).
10. **Presentation.** The 17 camera views and script-camera arg orders, the pushCam/popCam fix, radar rules (600 m admit,
    engine-off invisibility), then WRLD hour / time-of-day lighting, Visibility Range far clip, pixel LOD, .rtm road
    textures, horizon and clouds (`camera.md`, `renderer.md`, `options.md`). Saves and networking come after a single-player mission plays end to end.
