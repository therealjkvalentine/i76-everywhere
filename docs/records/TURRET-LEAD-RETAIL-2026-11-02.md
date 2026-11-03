# Turret lead and carrier velocity in retail 1.0: the +0.09 s lead holds, rounds never inherit the carrier (2026-11-02)

Ported 2026-11-03 from two I26 emulator lanes (lab captures `i26-gaps-20261101`, `emu2.md` row 3, and
`round-velocity-20261102`). No kit code changes: the kit runs the original's code. These are confirmations of how the
original aims and fires, for the kit's notes and for anyone comparing a reimplementation against it.

## Rig

Retail 1.0 `I76.EXE` (`6cc509ad`), 86Box at BelowNormal, emulated P166, Windows 95 RTM, 320x200 low detail, sim
physics, no kit, guest time. Projectile positions on their first 4 frames from the lab watcher (`I76WAT /proj`); the
player's and the nearest AI's pose and speed per frame from `I76MEM`; the player held or moved by the lab driver
(`I76DRV place / chase / stop / repair`). Warm Windows restart between tests, trials reset in place.

## 1. Turret lead (T11 pole turrets)

`mg2turr` (50cal, aim speed 150 = round speed 150 m/s) and `mg1turr` (30cal, aim speed 150, rounds 700 m/s); the player
held 50 m east at 0 / 15 / 30 m/s along +z or -z; each round's line from its first 4 frames meets the target's path at
offset s.

| v, m/s | 0 | 15 | 30 |
|---|---|---|---|
| s (mg2), m | 0.02 | 6.46 | 13.13 |
| s / v, s | - | 0.4305 | 0.4376 |

- Both directions alike; fit **tau' = 0.437 s** (per boot 0.437 / 0.437), centre offset -0.02 m. n: 2 boots, 491 mg2
  rounds, IQR <= 0.05 m per condition.
- The static reading, predict(clamp(t_ca, 0, 5) + 0.09 s) with t_ca the closest-approach time at the aim speed along
  the barrel, gives 0.428 / 0.436 s. Without the +0.09 s it would be 0.337 s. **The +0.09 s is real.**
- `mg1turr`: s / v 0.4315 at v 15: the lead uses the aim speed (150), not the round speed (700). It fired while leading
  in one hold only (v 15, boot 2, 41 rounds).

## 2. Rounds do not inherit the carrier's velocity

A round's ground velocity = dpos / dt over its first frames; "excess" = its component along the firing car's forward
minus its own speed field (0 if it leaves at the muzzle speed alone, + v_car if it inherits).

| case | carrier speed, m/s | rounds | measured | if inherited |
|---|---|---|---|---|
| player's forward 50cal MG while driving (4 throttle + 1 turning trial, 2 boots) | 18.3-26.3 | 114 | **149.99 m/s**, excess median -0.02 (IQR -0.04..0.01) | 168-176 |
| same gun, velocity field written to 20 m/s, pose held | 20.0 | 56 | excess 0.00 (IQR -0.02..0.01): the spawn does not read the field | 170 |
| AI `t05fp03`'s forward MG (200 m/s) | 12.1-17.4 | 21 | **199.96-200.05** | 210-217 |
| the same car's rearward gun, aimed within 25 deg of straight back | 3-12.5 away | 19 (4 boots) | 199.5-200.04 | 187-197 |
| FireRite from the player at rest / driving 21-27 / velocity field 20 | 0 / 21-27 / 20 | 24 / 30 / 12 | excess +3.8 / +3.6 / +3.9 at every speed (the ease to the rocket's speed, not the carrier) | +24..+27 |
| control: the player's MG at rest, 2 boots | 0 | 91 | 150.00, excess -0.00 | - |

Confidence high: two boots per scene, four weapons / carriers, > 200 rounds, spread < 0.1 m/s against a predicted
12-27 m/s effect.

## 3. Turrets still hit from a moving carrier

"Hit" = the round's line passes within 1.2 m laterally of the target centre at body height.

| case | carrier | target | rounds | hits |
|---|---|---|---|---|
| the player's 50cal Turret (save edited onto the trip car), at rest | 0 | a T06 car held 57 m away | 19 (2 boots) | 19/19 |
| same, driving past | 21-23 m/s | same, 60-64 m abeam-ahead | 37 (4 passes, 2 boots) | **37/37**, median miss 0.2 m |
| T11 helicopter, 7.62 turret | median 48 m/s | the player held still, 177 m | 229 | 195/229 = 85 % |
| T11 helicopter, 25 mm turret | median 9.5 m/s | same, 107 m | 45 | 43/45 = 96 % |
| T14 police turret | median 8.6 m/s | the player, 26 m (jostled up to 3 m/s) | 24 | 15/24 = 62 % (medium confidence) |

An aim that allowed for an inherited carrier velocity would miss a still target by v x flight time: about 5 m for the
player at 22 m/s, about 12 m for the helicopter at 48 m/s. Measured: 0.2 m and 0.5 m. **The original's turrets aim from
the barrel and the rounds fly at the muzzle speed alone.**

## Corrections this makes

- The kit's notes that put the 50cal at "~100 m/s" or Local Ditch's 1200 m/s: the engine's muzzle speed is 150 m/s
  (PARTS-REFERENCE), measured here at 149.99 (WEAPON-STATS and TICK-FINISH carry the note).
- `I26-CONTRIBUTION-PLAN-2026-10-31.md` s.9 item 9 and s.11's rounds row: the rounds match the original; what differed
  on the I26 side was the lead (+0.09 s missing) and the tracer, both since fixed there.
- Same code in R, G and N (static): [BUILD-RULES.md](../engine/BUILD-RULES.md) s.2.

## Open

- The lead on a moving target from a moving carrier (the t_ca term, second order) was not measured.
- Gold's turret and helicopter hit rates are static only (Gold rewrote `weapon_SpawnProjectile`).
