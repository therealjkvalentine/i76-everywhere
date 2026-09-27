# Changing how Interstate '76 works: levers and traps

A practical guide for changing physics, cheats and game rules without breaking the game. Written 2026-09-27 from
the reverse-engineering specs in i76-map (`subsystems/*.md`); every claim there cites the instruction it comes from.
Try changes on the **sandbox** (`C:\Users\james\i76-uncap-lab\game`), never on the install you play.

## The four levers, safest first

| lever | what it changes | how | safety |
|---|---|---|---|
| **Data files** | car stats, weapons, missions, scripts, terrain surfaces | i76-map `data\mod\i76mod.py` (`show` / `set` / `car`, `--zfs` rebuilds the archive). It writes only under `data\out`, reads every edit back and re-parses it | safest: the game's own code reads the values |
| **Proxy switches** | frame-rate behaviour, timing, render smoothness | `music-fix\Strlkup.dll` environment variables (`music-fix\README.md`); the sandbox launcher `TEST-FRAMERATE.bat` sets them | opt-in; every patch checks the bytes first and logs what it applied |
| **Trainer** | live player state | `tools\trainer\i76trainer.py` (status, repair, the game's unlimited switches, ammo, teleport) | live pokes, read back; sandbox only by default |
| **New code patches** | anything else | add a patch to the proxy, following its verify-bytes-first pattern | needs the spec for the site |

## Which data field actually does what

The full table (data field -> runtime field -> the code that reads it) is in i76-map `subsystems/engine.md`
("Vehicle creation") and `subsystems/weapons.md` ("Tunables"). Traps worth knowing before editing:

- **Brake strength (BRAK +4) does nothing in single player.** `physics_InitEntity` replaces every car's brake strength
  with 2300 / total mass offline. To change braking offline, change the mass, or patch 0x46a890.
- **Gearing is not in any file.** Gear ratios, final drive, wheel circumference, the 3500 rpm peak and the 7000 rpm
  limit are exe constants (0x4f8640, 0x4be2d4, 0x4be2cc, ...), the same for every car.
- **ENGN power behaves like watts:** drive acceleration = power x rpm-curve / (mass x speed). Top speed in 3rd is set
  by VDFC drag (a = -0.1 x drag x v^2).
- **Tyre size factor (WDFC +0x30) only sets the starting grip.** The first hit on a wheel resets grip to health/max.
- **SUSP handling sets every car's slide threshold.** The SUSP percent field only feeds the suspension's own damage
  check.
- **The offline player is buffed:** armour and chassis x2, component health x4 (`entity_InitVehicle`). Balance
  changes that ignore this will feel different for the player and the AI.
- **Collision boxes come from the .vdf COLP chunk.** SCHK / VCHK only feed break-off debris.
- **Weapons never jam offline.** The condition roll only runs in network games; offline a weapon only matters at 0 HP.
  Spread is one-sided and yaw-only.
- **Missile guidance is exe code, not data.** The heat missile snaps to its target every step (no turn limit). The
  radar missile's turn clamps (sin 3 / 15 / 20 deg per step by distance flown, 0x4bec2c..0x4bec38), the 70 m
  shooter immunity and the 0.5 m terrain floor are exe constants. Only speed, damage, life and gravity scale come
  from the ORDF (i76-map `weapons.md`, Projectile types).
- **Flamer damage depends on the renderer.** It is applied per rendered frame per hitting segment (at least 1 each)
  and again in the rear-mirror pass. Balance flamers with `I76_FRAMERATE_FIXES` on, which applies it 20 times a
  second from the main pass (`weapons.md`, Flamers).
- **Vehicle health percent is broken in stock** (object_HealthFraction). Once any core component is scratched it
  reads under 1%, so AI flee, script `hpLesser` and damage smoke all trigger at the first scratch. The opt-in fix is
  `I76_FIX_HEALTH_PCT=1`. Balance scripts with it off, as players will, or ship it together with retuned scripts.
- **Big custom missions:** the object-label table (2048 labels to start) has a broken grow path (0x4ad450): heap
  corruption past 2048 labels. Stock T01 uses 88. `I76_FIX_LABEL_TABLE=1` repairs it (verified with the start
  capacity forced to 16).
- **Surface grip, rolling drag, bump and damage rate are per mission:** the WRLD chunk's 8 surface records, indexed by
  the terrain's top 3 bits.

## Physics changes that stay stable

- **Do not change the physics step rate** without `I76_FIXED_STEP`. Contact push-out, rest snap, the suspension
  filter and coasting losses all follow the number of steps per second (i76-map `framerate.md`). 24 steps/s
  reproduces stock play at 20 fps.
- **Things that run once per rendered frame** (object collision, far vehicles, the AI, several effects) change with
  frame rate. The proxy's `I76_FRAMERATE_FIXES` covers the gameplay-relevant ones: clouds, free-look, zoom, throttle
  ramp, lock and radar tones, vehicle sounds, AI throttle and steering, flamers, smoke puffs and missile-trail fade.
- **The speedometer reads m/s while skidding or airborne** (it eases toward raw m/s instead of mph, 0x46a705).
  It is display only; physics is not affected.
- **Far vehicles** (beyond about 850 m) use a flat kinematic model with a frozen height. Physics changes to the full
  model do not apply to them until they come back into range.
- **Steering feel** is a kinematic yaw rate (steer x speed / (2 x wheelbase)) capped by grip, not a tyre-force model.
  The slide path is the "simple" one for every car (flag 0x1000, confirmed live).

## Cheats and trainers

- **The game's own switches** (Play Options unlimited ammo / armour / chassis, bits 0x04 / 0x08 / 0x10 of 0x654b98)
  are the safest cheats. Set from the menu they mark the mission as cheated: a win becomes a failure (no salvage, no
  progress). Set from the trainer, the marker is not set.
- **Built-in codes** (Ctrl+Shift + typed): `getdown`, `flflat` / `frflat` / `blflat` / `brflat`, `wiggleburger`,
  `freelance`, `thirdnostril` (i76-map `cheats.md`).
- **Repair and god mode**: repair by setting the current armour, chassis and component values to their maxima (the
  trainer does this). A god-mode hook belongs in `entity_ApplyDamage` 0x465620, not in the kill roll.

## Rendering limits

- **Draw distance has two ceilings:** the far clip (mission far or 150 m, patched in DRAW-DISTANCE.md), and the depth
  buckets, which drop anything past about 3.8 km (0x48fe61).
- **Object LOD is chosen by on-screen pixel size.**

## Saves

Parked for now (James, 2026-09-27). The exe side is mapped in i76-map `subsystems/mission.md`: vehscn.vsf holds the car
and salvage after a trip win; I76PLYR.DEF holds only the options block.
