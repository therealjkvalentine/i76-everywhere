# i76tune - live spec tuner

`tools\trainer\i76tune.py` changes the game's physics, weapon, AI, camera and sound constants in a **running**
Interstate '76 from a catalogue, `tunables.json`, whose entries come straight out of the reverse-engineering specs in
`i76-map\subsystems\*.md`. It is the spec made pokeable: every entry names its address, type, pristine value,
unit, meaning and the spec section it came from.

```
python i76tune.py list [group]              id, name, live value vs default, unit ('*' = differs)
python i76tune.py groups                    the catalogue groups and entry counts
python i76tune.py get <id>                  one entry in full
python i76tune.py set <id> <value> [--force]
python i76tune.py reset <id>|all
python i76tune.py preset save <file> [id..] / preset load <file>
python i76tune.py watch <id>...             5 Hz until Ctrl-C
python i76tune.py dump                      every entry's live value as JSON
python i76tune.py --offline list [group]    no game needed: image defaults + verification summary
```

## How it works

- **Process access** is `i76trainer.py`'s: `find_game` (refuses anything but the sandbox copy at
  `C:\Users\james\i76-uncap-lab\game` unless `--any`), `Game.rd / wr / u32 / f32` and the player lookup
  `[[[0x54a264]]+0x70]`. Never point it at the daily-driver install.
- **exe-scope entries** are constants in the game image: `.rdata` floats (most of them), a few `.data` tables (the
  gear ratios at `0x4f8640`, the far-clip source `0x4c271c`) and nine **instruction immediates** in `.text` (marked
  `imm`: the kill-roll factors, the Cup Holders 10%, the sound 3D distances, nitro 15 s, airborne gravity, the
  0.05 s substep). The image has no relocations, so the addresses are the same in the process. For each write the
  page is made writable with `VirtualProtectEx` (`PAGE_READWRITE`, or `PAGE_EXECUTE_READWRITE` for `.text`), the
  bytes are written, read back and the old protection is restored. Every write prints `old -> new` and `FAILED` if
  the read-back disagrees.
- **entity / engine / brake / susp / wheel entries** are per-vehicle fields, resolved through the player's car on
  every command: `entity`, `[entity+0x3c4]+0x70` (engine), `+0x3cc` (brakes), `+0x3c8` (suspension),
  `[entity+0x3a8+4*slot]+0x70` (wheels; the catalogue carries slots 0 and 4). They have no fixed default (they come
  from the .vcf / .vdf / compnent files, x4 or x2 for the offline player), so `reset` refuses them: use
  `preset save` before you change one.
- **Derived fields.** Some values are consumed through a second word that the game computes once at load. Setting
  the primary recomputes and writes the twin, and says so:
  - `engine_power` -> `engine+0xc` k = P / 3500^2 (keeps the power curve's zeros at 0 and 7000 rpm);
  - `brake_strength` -> `brake+0x10` effective = strength x max(hp/max, 0.2);
  - `mass` -> `entity+0xa8` 1/m; `wheelbase` -> `+0x110` 1/(2 wb) and `+0xb4` 2.65618/wb;
  - `wheel_circumference` -> `0x4be2cc` 1/circumference; `fall_kill_height` -> the f64 twin at `0x4bd190`;
  - `blown_tyre_pull`, `engine_pitch_base_hz` -> their negated twins; `pushout_speed` -> its squared threshold;
    `cluster_spread_span` -> the half-width.
- **Ranges.** Each entry has a sane `[min, max]`; `set` refuses values outside it unless `--force`.
- **Defaults and verification.** `--offline list` opens the pristine image `i76-map\ghidra\i76_ref.exe`
  (md5 `9a232dcc...`, or `--image <path>`), prints the catalogue with the image's value next to the catalogue
  default, and checks every exe-scope default and derived twin byte-for-byte (relative tolerance 2e-4 for the
  spec's rounded numbers such as 1.674 for the stored 1.673966). Current state: 157 of 157 exe-scope entries
  verify (`.rdata` 143, `.data` 5, `.text` 9); 29 entity/component entries are per car. `reset` writes the exact
  pristine bytes when the image is available, else the catalogue default.
- **Presets** are JSON `{id: value}`. `preset save <file>` with no ids saves every exe-scope entry whose live value
  differs from pristine (a diff); with ids it saves exactly those (that is how you snapshot per-car values before
  experimenting). `preset load` applies with the same range check and read-back as `set`.

## The catalogue groups

| group | what is in it | spec |
|---|---|---|
| engine | gear rpm factors (0x4f8640 table), final drive 3.538, wheel circumference 1.674 (+ reciprocal), idle 1050, the -850 rpm offset, free-rev 1050 + 4950 x throttle capped 6000, peak-power rpm 3500, health floors 0.275 / 0.4, speedo 2.2369 | engine.md Model |
| gearbox | 3.6 km/h scale, throttle thresholds 0.0625 / 0.875 / 0.87 / 0.002, upshift 62 / 106 (full) 25 / 40 (closed), kickdown 98 / 60, closed downshift 31 / 12, 0.5 km/h to idle. `wheel_rpm_x60` is the 60 that is both s/min and the 2nd->1st kickdown speed | engine.md Model, 0x46a320 / 0x46a140 |
| brakes | the single-player 2300/m numerator (applied at vehicle creation), the x8 brake gain, handbrake 2 m/s and the 0.5 cap | engine.md, physics.md |
| physics | gravity (slope vector, airborne imm, ground load), drag -0.1, nitrous x5, lateral grip 7.84 (0.8 g), blown-tyre pull, airborne pitch target, 7.65 m/s surface damage, 35 m fall kill, 0.05 s substep, 0.688 flat radius, suspension feed-forward, 2.65618 yaw gain, walkable ny 0.4 | physics.md Constants |
| collision | restitution 0.75 / floor 0.25, 4 m/s push-out, 0.2 rebound damp, 0.1 angular gain, impact damage K (rigid / static), FFB jolt 0.02 | physics.md |
| damage | x4 offline component bonus (init only), 33% critical threshold, kill-roll k 0.1 / 2.5 (imm), Cup Holders 10% (imm), damage levels 0.75 / 0.5 / 0.25, smoke 0.6 / 0.4, HealthFraction 28 + 72 r, the 0.9999 'intact' and 0.02 'dead' ratios | damage.md |
| specials | jammer 8 s, Heated Seats x1.1, Mud Flaps +0.1, nitro 15 s (imm) | engine.md Special equipment |
| weapons | difficulty factors 2.0 / 1.0 / 0.75 for projectiles (0x4beb54..5c) and for flamers (0x4bd318 / 32c / 330), projectile gravity -9.8 | weapons.md |
| missiles | rocket speed easing 0.5, 70 m shooter immunity, radar missile dot 0.998 / gain 0.75 / bands 15 / 150 m / clamps sin 3, 15, 20 deg / floor 0.5 m, cluster spread 20 (+-10) and 1.8 s fuse, mine restitution 0.5 / 0.25 | weapons.md Projectile types |
| ai | fire gates 6000 (guns) / 3500 (mortars) / 1000 x skill^2 (rockets), throttle cap 0.75 + 0.25 skill, turn-speed grip 7.84, flee range 80, standoff 70 m, dodge gate 850 + 150 (1 - skill), sweep box 50/sim_dt, weave 90 m and 2 s, steer limits 0.45 / 0.4 / 0.6, route radii 10 / 40 / 26.9 m, approach 60 m and 0.2, follow 2.5 / 4 / 50 / 100 / 150 m, 5 m/s, 0.75 | ai.md |
| camera | track distance 1..10 x radius, 150 m cap, orbit 1 deg per call and pitch clamps, head-look rate 4, enemy/target view 3 m up 7.5 m back 30 deg, missile cam 20 deg / 5 m | camera.md |
| renderer | 600 m far-vehicle physics radius (next camera_Init), far-clip source 0x4c271c (next view-options apply), 450 m road cull | renderer.md, options.md |
| sound | 600 m cull (360000), 3D min / max 10 / 100 / 400 m (imm), engine loop pitch 8268.75 Hz + span 1/4950 from 1050 rpm, 7 m/s tyre sounds | sound.md |
| network | 5 s respawn, 'ST' interval clamp 0.2 / 0.5 and the /3, jam probability 0.3 / 0.5 (network only) | network.md, weapons.md |
| player | mass (+1/m), aero drag, blower multiplier, collision multiplier, wheelbase (+ steer and yaw gains), yaw pivot, gear lever | physics.md entity fields |
| components | engine hp / max / P (+k) / k / health factor / rpm; brake hp / max / strength (+effective); suspension hp / max / handling; wheel hp, grip, base grip, radius for slots 0 and 4 | physics.md, engine.md |

Several `.rdata` words are **dual use** (the compiler merged equal literals); the catalogue says so in the name and
meaning: `wheel_rpm_x60`, `handbrake_traction_cap` (also the 0.5 m airborne clearance), `damage_level_hi` (also
the smoke start and the tyre-cover x0.75), `damage_level_mid` (also headlights off), `flame_factor_medium` (also a
literal 1.0 in the flame maths), `cam_track_distance_min`, `cam_orbit_pitch_min`, `net_state_interval_max`.
Change those knowing both readers move.

## Caveats

- **exe-scope changes affect every car and every AI.** A taller 3rd gear is taller for the Piranha and for every
  enemy; a lower drag scale makes the AI faster too; a kill-roll change for the AI applies to every AI car. Only the
  `player` and `components` groups are the player's car alone.
- **Some constants are consumed once.** `brake_offline_strength`, `component_bonus_offline`, `heated_seats_ammo`,
  `slide_yaw_gain_num` are read at vehicle creation; `far_vehicle_radius_base` at camera_Init; `far_clip_source` on
  a view-options apply. Set them before a mission / respawn, or write the live per-car field instead
  (`brake_strength`, `yaw_gain`).
- **The sandbox exe is patched** (music-fix proxy, framerate fixes, i76shell patches). `list` shows live vs
  pristine, so a `*` can be one of those patches rather than something you set. `reset all` would undo such a
  patch if it sits on a catalogued word (none of the known patch sites do today). Check what `*` means before
  resetting.
- **Writes are not journalled.** `set` prints the old value; keep it or `preset save` first.
- **Not a trainer.** Armour, ammo, repair, teleport and the Play Options flags are in `i76trainer.py`.

## What cannot be tuned live

- **The gear count and the shift logic.** The table has five slots (reverse, idle, 1st..3rd) indexed by code; the
  automatic's state machine, the never-firing interpolated shift curve (`physics_ShiftCurveTest`) and the
  "x1/v above 1 m/s" drive shape are instructions.
- **The offline x2 armour / chassis bonus** is `fadd st0, st0` at `0x463673`, not a constant (damage.md has the
  jne patch for it). The component x4 is a constant and is in the catalogue.
- **The flee threshold 30 + 17 x aggression** is `lea eax, [edx + eax + 0x1e]` (immediates in the instruction);
  the catalogue has the 80 m range gate that precedes it.
- **Random-gate structure** (three rand()%1000, rand()%5000): the divisors are code; the scales are tunable.
- **Frame-grid behaviour** (flame segments per frame, ammo digit roll, AI fire decision per frame): fixed by the
  proxy's `I76_FRAMERATE_FIXES`, not by a constant.
- **The AI skill tables** `0x5fcb7c / 0x5fcb9c / 0x5fcbbc / 0x5fcbdc` are in BSS (filled at load), so they have no
  image default to verify against and are left out; the per-car values at `ai+0xa81c..0xa828` could be added as an
  AI-block scope later.
- **Anything per AI car** (their masses, engines, ai block): the tool resolves only the player's vehicle.
- **The difficulty byte 0x654b9c** is a Play Option (BSS); set it in the menu. The factors it selects are tunable.

## Examples

Make 3rd gear taller (less rpm per km/h, higher engine-limited top speed; the AI gets it too):

```
python i76tune.py get gear_ratio_3rd
python i76tune.py set gear_ratio_3rd 0.55
python i76tune.py watch engine_rpm            # drive: rpm per km/h in 3rd drops by 0.55/0.67
```

Make missiles dumber (DrRadar / Cherub turn less per step and only when badly off; the AI fires them less):

```
python i76tune.py set radar_missile_turn_near 0.02
python i76tune.py set radar_missile_turn_mid 0.08
python i76tune.py set radar_missile_turn_far 0.12
python i76tune.py set radar_missile_track_dot 0.95
python i76tune.py set ai_fire_gate_missile 300        # p = 0.06 x skill^2 per decision instead of 0.2
python i76tune.py preset save dumb-missiles.json      # saves exactly these five (they differ from pristine)
```

Set offline brakes to 1500/m. The exe constant applies to cars created afterwards; the live player car has its own
word, so do both:

```
python i76tune.py set brake_offline_strength 1500     # next spawn, every car
python i76tune.py get mass                            # say 1951 kg
python i76tune.py set brake_strength 0.7688           # 1500 / 1951 for the live car; brake+0x10 follows
```

Other one-liners:

```
python i76tune.py set aero_drag_scale -0.05           # every car's terminal speed up about 1.4x
python i76tune.py set kill_roll_k_player 2.5          # player as fragile as the AI (code immediate, .text)
python i76tune.py set surface_damage_speed 1000       # no terrain surface damage
python i76tune.py set ai_throttle_cap_base 1 ; python i76tune.py set ai_throttle_cap_slope 0
python i76tune.py set cam_orbit_step -0.0058          # F2 orbit at 60 fps turns like stock 20 fps
python i76tune.py set engine_power 600                # live car: double power, k recomputed
python i76tune.py reset all                           # every exe-scope word back to pristine bytes
```

Verify the catalogue without a game:

```
python i76tune.py --offline list                      # 157 of 157 exe defaults match the pristine image
python i76tune.py --offline list gearbox
python i76tune.py --offline get peak_power_rpm
```

## Adding an entry

Append to `entries` in `tunables.json`: `id`, `group`, `name`, `addr` (VA for exe scope, offset for the others),
`type` (f32 | f64 | i32 | u32 | u8), `default` (the spec's number, or null for per-car), `unit`, `min`, `max`,
`meaning` (with the reader address), `spec` (file#section), `scope`, `section` (exe scope), optional `slot`
(wheels) and `derived` (`addr` or `off`, `type`, `formula` in `x`, with `rd(off)` / `ri(off)` reading an f32 / i32
at base+off - hp words are i32, so use `ri` for them - and `note`). Then run `--offline list`: an entry whose bytes do not match its default or section is
reported as `MISMATCH` and should be fixed or dropped before use. The addresses are for md5 9a232dcc (the GOG / AiO
link); `tools\disasm.py <function>` in i76-map shows the readers.

## Verified live (2026-10-01, sandbox)

`set gear_ratio_3rd 0.5` on a running game: 47 of 47 third-gear samples followed rpm = 850 + 126.81 x 0.5 x v and none followed the stock 0.67; `reset` read back 0.67. The gear table is in .data, so that write needed no unprotect; .rdata entries take the VirtualProtectEx path (not yet exercised).
