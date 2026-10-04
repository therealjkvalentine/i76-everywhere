# engine (engine, gearbox, brakes, vehicle creation)

**Contract.** `physics_UpdateEngine` 0x46a320 runs once per substep from `physics_StepVehicle` (0x43a1e3). It sets
the rpm and the automatic gear, and produces the drive power eng+0x10 that `physics_ComputeDriveBrakeAccel` 0x43c310
turns into acceleration.

Static reading of md5 9a232dcc (2026-09-27), batch `engine-map-1` (51 names), from a reviewed read-only draft
(cluster F). The 4.0 component bonus and the single-player brake override were checked in disassembly, and the
live component values agree (wheels 400 = 100 x 4, engine 1200 = 300 x 4).

Engine data = [entity+0x3c4]+0x70. Its dt is the **whole-frame** dt (`simclock_GetDt` at 0x46a333; the proxy's
`I76_ENGINE_DT_FIX` corrects it).

## Oracle check (2026-10-02, five recorded drives, every frame; `verify/oracles/REPORT.md`)

- rpm = 850 + 126.81 x R[g] x v: 100% of grounded geared frames within 0.15 rpm, all five runs.
- Gearbox (upshift / kickdown thresholds, the 0.0625 throttle rule, no shifts while skidding or airborne):
  99.7-99.9% of frames.
- Stepper floor(dt x 20) + 1: 100%.
- Drive power and brake strength: the equations fit with P = 193,960 and m = 1,951.0 exactly, the Piranha's ENGN
  power and mass, neither of which the telemetry carried. Recorded as findings until those two fields are exported.
- Open at frame level: which frame's throttle the gearbox sees at a 0.0625 crossing; 1st -> idle is reached through
  a rest snap at about 1.1-1.5 m/s that the gearbox section does not describe.

## Live check (2026-09-27, sandbox Melee, full throttle, 70 samples at 0.3 s)

- rpm = 850 + 126.81 x R[g] x v matched 61 of 61 grounded samples, 59 of them to the exact rpm.
- Gear changes: 2->3 at about 60 km/h, 3->4 at 104-105 km/h (model: 62 / 106, within the sampling interval); a 4->3
  kickdown at 83 km/h while slowing on throttle (model: <= 98 km/h).
- One airborne sample (flag 4) was off the formula, as the free-rev branch predicts.
- The first change 1->2 logged at 28 km/h, once unexplained, is the skid rule: the gearbox does not run while the
  car is skidding (flag 0x2) or airborne (0x4), and a full-throttle launch skids. Found by the gear oracle
  (`verify/oracles/engine_gear.py`, 2026-10-02): holding the gear on skid/airborne frames is worth 7-17 points of
  match rate; with it the shift model matches 99.7-99.9% of frames over five drives.

## Model

- **Gear state** g = eng+8: 0 reverse, 1 idle/neutral, 2 / 3 / 4 = 1st / 2nd / 3rd.
  - Reverse input -> g 0. Lever P or N -> g 1.
  - The lever is entity+0x104: 0 P, 1 R, 2 N, 3 D (the default), 4 "2", 5 "1".
- **rpm** (geared, engine running, not skidding, not airborne) = 850 + 126.81 x R[g] x v, v in m/s.
  - R = {3.0 reverse, -, 1.67, 0.96, 0.67} at 0x4f8640.
  - Final drive 3.538 (0x4be2d4); wheel circumference 1.674 m (0x4be2dc; 0x4be2cc holds its reciprocal 0.5974).
  - Wheel rpm = |v| x 0.5974 x 60; mph for the speedo = wheel rpm x 1.674 / 60 x 2.2369 (0x46a567).
  - These are fixed exe constants: no car or wheel file changes the gearing.
  - Idle / neutral: 1050.
- **Free rev** (skidding, airborne, P/N): the rpm eases toward 1050 + 4950 x throttle at a rate of 2 x dt, capped
  at 6000.
- **Power** (every call): eng+0x10 = P x f x rpm x (7000 - rpm) / 3500^2.
  - P = ENGN power (eng+0x14); k = P / 3500^2 is set once at load (eng+0xc).
  - Peak at 3500 rpm, zero at 7000, negative above.
  - f = health factor = max(hp/max, floor): floor 0.275 for offline AI, 0.4 for the offline player and every
    network car (0x469fb0). A destroyed engine keeps f = floor. **f (eng+0x18) is recomputed when damage lands, not
    every call**: poking the engine hp directly left the power curve on the old f (verify poke, 2026-10-02).
- **Drive**: a = P_drive / m x entity+0x128 (x5 with flag 0x800; x1/v above 1 m/s), floored at 1e-4, x throttle,
  capped by rear-wheel traction.
  - Engine power therefore behaves like watts (a = P / (m v)).
  - The 1e-4 floor acting on negative power above 7000 rpm is the rev limiter: engine-limited speed per gear is
    104 / 182 / 261 km/h (1st / 2nd / 3rd), reverse 58 km/h.
  - Aero drag sets the real top speed in 3rd.
- **Automatic gearbox** (0x46a320 upshift, `physics_AutoDownshift` 0x46a140). One gear per substep at most.
  - Full throttle: upshifts at 62 / 106 km/h, kickdown below 60 / 98. The effective 1st -> 2nd point is
    max(upshift threshold, the 2nd -> 1st kickdown speed): with the upshift constant tuned down to 40 km/h the shift
    still came at 60.1, because the kickdown rule pulls it straight back (verify poke `upshift_1to2`).
  - Closed throttle (< 0.0625): upshifts at 25 / 40, downshifts at 12 / 31.
  - The "interpolated" shift curves (`physics_ShiftCurveTest` 0x46a0c0) are evaluated every substep (census 2026-10-02:
    649 calls in a 120 s drive) but the test never passes, because the formula uses (V - Vmax) where (V - Vmin) was
    meant. Whether it is ever true is an oracle question (verify/), not a cadence one.
- **Brakes**: a = brake+0x10 x throttle x 8, capped by four-wheel traction (x0.5 on handbrake).
  brake+0x10 = max(hp/max, 0.2) x strength.
  - **In single player the BRAK strength is replaced by 2300 / m** (`physics_BrakeSetStrength` 0x46a890, called
    with 2300/m by `physics_InitEntity`; network games and multi-melee multiply instead).
  - So offline, every car brakes at up to 18400/m m/s^2 (Piranha, 1951 kg: 9.4 m/s^2), whatever its brake file
    says.
- **Gauges** (0x459fa0). entity+0x3f8 / +0x3fc point to the needle objects (VLOC class 35 speedo, 36 tach). Each
  frame they are rotated:
  - speedo: clamp(eng+0x24 mph via 0x46a7b0, 0, 150) x 1.8533 deg;
  - tach: min(rpm, 8400) x 0.028125 deg.
- **Speedo bug** (confirmed live 2026-09-27, `captures/014-framerate/speedo1.json`). Grounded and geared,
  eng+0x24 = wheel rpm x 1.674 / 60 x 2.2369 (mph). In the free-rev branch (skidding, airborne, P/N) it eases
  toward the raw speed in **m/s** instead: eng+0x24 += 2dt x (|v| - eng+0x24) (0x46a705..0x46a75a). So the needle
  sinks to about 1/2.24 of the true reading while airborne or sliding.
  - Live trace: 33.3 m/s gave 74.5 mph on the ground. During a 40 m drop, 26.3 m/s gave 23.3 (m/s, lagging).
    Skidding at 2.72 m/s gave 2.78.
  - A port should feed mph in both branches. The fix is one constant: multiply the target at 0x46a705 by 2.2369.

## Vehicle creation: data file -> runtime -> physics

Order: VDFC handler -> `object_SetClass` -> `entity_CreateVehicle` (defaults, 4 components) -> VDF chunks (mass,
drag, WLOC) -> wheel pairs (+mass) -> compnent.cdf (ENGN / BRAK / SUSP, +mass) -> WEPN / SPEC -> pending inits
(engine k, wheel geometry) -> `entity_InitVehicle` -> `physics_InitEntity` (hull, wheelbase, blower, flags, mass,
brake 2300/m, first engine update).

| data | runtime | read by |
|---|---|---|
| VDFC +0x30 mass | entity+0xa4 (+ 2 x wheel, engine, brake, suspension and weapon masses); 1/m at +0xa8 | drive a = P/(m v); offline brake 2300/m; vehicle-vehicle momentum; impact damage |
| VDFC +0x38 drag | +0x120 | a = -0.1 x drag x v^2 (top speed) |
| VDFC +0x34 collision multiplier | +0x124 | no reader found |
| VDFC +0x18 size | +0x47c | multiplayer armour budget only |
| VDF WLOC (slots 0..5) | wheel transforms via `bwd2_LoadWheelPair` 0x4ae5e0 | track +0x114, wheelbase +0x118, steer gain +0x110 = 1/(2 wb), slide yaw gain +0xb4 = 2.65618/wb, yaw pivot +0x11c = rear wheel z; tyre radius / rest y = wheel local y, travel +-0.25 r |
| VDF collision box | hull points +0x04..+0x33, +0x34 | terrain hull sweep 0x440740 |
| VCFC wdf front / mid / rear | wheel pairs +0x3a8 / +0x3b0 / +0x3b8 | front steers, rear drives, mid optional |
| WDFC +0x28 hp | wheel +4 / +8 | grip decays to 0.5 and rolling drag rises to 2x with damage; blown radius x0.688 |
| WDFC +0x30 size factor | wheel +0xc (initial grip only) | traction and slide limits, until the first hit resets grip to hp/max |
| ENGN +0 hp / +4 power / +8 mass | engine +0/+4, +0x14 (and k), mass | health factor, power curve |
| BRAK +0 hp / +4 strength / +8 mass | brake +4/+8, +0xc (offline: replaced by 2300/m), mass | brake accel |
| SUSP +0 hp / +4 handling / +8 percent / +0xc mass | susp +0/+4, +0x14 / +0x18, +0x1c, mass | handling sets every car's slide threshold (2L, 0x43ce10) and decays to 0.5 with damage; percent only feeds the suspension's own damage check |
| VCFC armour[4] / chassis[4] | +0x138/+0x158/+0x178 and +0x148/+0x168/+0x18c (side 4 = 100) | `entity_ApplyDamage` (damage.md) |
| (no file) component hp, offline player | **x4.0** (0x4be1c0) on engine, suspension, type 20, brakes, wheels and specials | armour and chassis are x2 |
| SPEC type 3 (blower) | +0x128 = 1.25 | drive x1.25 |
| SPEC type 8 | every mounted weapon's ammo x1.1 | |
| SPEC type 4 (exhaust brake) | input sets +0xf4 | brake input x2 |
| exe-only | gear ratios, final drive, wheel circumference, 3500 / 7000 rpm, idle 1050, shift thresholds | identical for every car |

## Corrections made elsewhere

- `damage.md`: component hp for the offline player is x4, not x2.
- `physics.md`: the engine damage floor is 0.275 for offline AI and 0.4 for the player and network cars; 2300/m is the
  single-player brake strength.
- The data track's VEHICLES.md (another session's area; noted here, not edited) has VLOC 35/36 swapped: 35 is the
  speedo and 36 the tach. WLOC does have a reader (0x4ae5e0).

## Special equipment (SPEC) (gap-dmgspec, static, md5 9a232dcc, 2026-09-27)

**Object.** `entity_AttachSpecial` 0x467280 creates a `v-spcl` object, class **0x18** (row 0x4f7bc0; 0x4672b6),
in slot entity+0x3ec+4*slot, slot < 3 (0x46728e). These are component slots 17..19 of the +0x3a8 array, so specials
are damaged like components.

The data is 0x18 bytes (`entity_SpecialCreate` 0x4676b0):
- +0 type;
- +4 uses: 3 for type 2, 5 for type 1, 1 otherwise (`entity_SpecialSetType`, 0x467772 / 0x46777f / 0x467787);
- +8 / +0xc hp / max = 10 (0x4676c0..0x4676cd), x4 for the offline player (0x463754, 0x463768);
- +0x10 active;
- +0x14 activation sim time (0x467804).

Damage that reaches hp zeroes hp, uses and active (0x467741..0x46774f). Available = uses > 0 or active (0x4677a0).

**Keys.** The actions `special1/2/3` set bytes 0x5367e3 / e4 / e5 (action rows 0x4f2a40 / 60 / 80, type 2 = press).
The defaults are **6 / 7 / 8** (KEYBOARD.MAP). Key n works on slot n (0x44f5a3..0x44f63f), and only types 1, 2 and 4
react (0x44f5fd..0x44f608). Names: shell 0x5007d8.. (types 1..9, `shell_GarageListSpecials` 0x4b56d0); panel
`3<name>_on/off` 0x4f8290 / 0x4f81d0 (types 0..11). Stock .vcf files use 1..9 only (vcf-chain.md).

| id | item (shell / panel) | effect | amount | uses / duration | trigger | code |
|---|---|---|---|---|---|---|
| 0 | - / sp_empty | none | | | | panel only |
| 1 | Radar Jammer / radar | +0x454 bit 0x40000: hidden from AI radar and radar contacts, radar missiles drop their target | | 5 uses, 8 s sim time (-8.0 at 0x4be17c) | key | `entity_ActivateRadarJammer` 0x461770; expiry `entity_IsRadarJammerActive` 0x461680 |
| 2 | NitrousOxide / nitrous | flag 0x800: drive accel x5.0 (0x4bd1dc) | x5 | 3 uses, 15.0 s (0x43d2a6) | key | `physics_FireNitro` 0x43d280; 0x43c58f |
| 3 | Blower / blower | +0x128 = 1.25: drive accel x1.25 | x1.25 | permanent from spawn | passive (init) | 0x438edb; 0x43c587 |
| 4 | X-Aust Brake / xaust | +0xf4 = 1: brake input (< 0) x2 | x2 | latched, no uses | key | 0x44f608; 0x43ab46..0x43ab54 |
| 5 | Structo Bmpr / structo | chassis absorb multiplier 2.0 on sides 0 (front) and 3 (back) | x2.0 | while available | passive (hit) | `entity_ApplyDamage` 0x46565b..0x4656ce |
| 6 | Curb Feelers / curb | armour absorb multiplier 1.1, all sides | x1.1 | while available | passive (hit) | 0x465772..0x4657d8 |
| 7 | Mud Flaps / mud | chassis multiplier +0.1 (minus -0.1 at 0x4be208; 2.1 with structo) | +0.1 | while available | passive (hit) | 0x4656ef..0x465759 |
| 8 | Heated Seats / heated | every mounted weapon's ammo x1.1 (0x4beb20) | x1.1 | once at spawn | passive (init) | 0x438ecb -> 0x4a4a40 (0x4a4b14) |
| 9 | Cup Holders / cuphldr | a component hit is absorbed whole 10% of the time (type mask cleared) | 10% | while available | passive (hit) | `entity_DamageComponent` 0x465b0a..0x465b89 |
| 10 | - / dash_mary | no effect found; panel icon only | | | | 0x4f8330 |
| 11 (0xb) | - / tire_covr | tyre covers: a wheel-hazard hit does nearest-wheel hp x0.75 (0x4be1e8) instead of setting it to 25/100 | x0.75 | while fitted (no availability test) | passive (hit) | `entity_HazardHitNearestWheel` 0x466fbc..0x467138 |

Notes:
- **Multiplier meaning.** An armour side absorbs a hit when amount <= value x mult, and then loses amount / mult
  (damage.md). The chassis multiplier starts at 1.0 (0x46562b) and is used at 0x46592b; the armour multiplier is used
  at 0x465a06. Side 4 uses both on the words +0x19c / +0x188 (0x465804 / 0x465878).
- **Jammer.**
  - A press needs uses >= 1 and hp >= 1 (0x461796 / 0x46179a).
  - It plays clockon.wav and cjamm.wav and starts the timer only if the jammer is idle (0x4617c4..0x4617cf), but it
    **costs a use on every press** (0x4617d8).
  - It is active while now <= start + 8 s, hp >= 1 and the car is not dead (0x46170c..0x461735); otherwise flag
    0x40000 is cleared (0x46173f).
  - Readers: AI radar 0x45f995, radar contacts 0x45fb5c / 0x45fe5b, AI global 0x51f5c8 (0x40a67a), radar missile
    0x4aaa38 -> target cleared 0x4aaa5b, network bit 0x400 (0x464674).
  - In network games a remote car counts as jammed whenever its flag is set (0x4616ba..0x4616d8).
- **Nitrous.**
  - It finds the first available type-2 special on the player (0x43d298), calls `entity_StartTimedState`(0x800, 15.0)
    (0x43d2b1) and uses a charge (0x43d2ca).
  - Timer entity+0x450 counts down by entity_UpdateState's dt (0x46544e); expiry clears 0x8c08 (0x465605).
  - The timer is shared with oil-slick traction loss (2 s, 0x466e93) and the wreck (10 s). Static inference: nitrous
    during a spin makes the spin last 15 s, and an oil slick during nitrous cuts the boost to 2 s. A second press
    restarts the 15 s and costs a charge.
- **Blower.** Only `entity_Create` (1.0, 0x462fdd) and 0x438edb write +0x128, so a destroyed blower keeps working.
- **Exhaust brake.** The only writers of +0xf4 are 0x44f608 (1) and `entity_Create` (0, 0x462f58). So after the first
  press it stays on for the rest of the life, with no use count and no hp check.
- **Tyre covers and the hazard.**
  - `entity_HazardHitNearestWheel` 0x466eb0 is called only by `weapon_StepWheelHazard` 0x4aa3e0 (ordnance id 0xe,
    no stock weapon), not by handguns.
  - Without covers, the nearest wheel is set to hp 25 / max 100 (0x467133..0x467138). That is level 3, so the tyre
    blows.
  - With covers, each hit multiplies hp by 0.75, and the visuals update only once hp <= 25 (0x46700d). That is about
    5 hits for an AI tyre (100) and 10 for the offline player's (400).
  - Both the covers and the hazard are cut content.
- **Panel.** `renderer_UpdateSpecialsPanel` 0x467850 shows each slot's icon on/off (on = uses >= 1 and active). The
  diode (0x467948) shows hp%: 100 off, 67-99 green, 34-66 yellow, 1-33 red, 0 dark (0x4f8350). The counter
  (0x467988) shows the uses.
