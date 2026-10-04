# What a car file controls: every vehicle stat, traced to where the game reads it

A vehicle in I'76 is a chain of BWD2 files. The `.vcf` names everything else; each file feeds fixed offsets of the
live vehicle. This page lists every stat in that chain, the instruction that reads it, where the value lands, and
the consumer that gives it meaning. Tags: **cited** (instruction evidence), **inferred** (meaning read from use or
values, no single instruction names it).

- Exe: GOG `i76.exe` md5 9a232dcc2c164648cff20c414c1f9698. All handlers receive the chunk *header*, so an exe
  operand `[hdr+N]` is body offset `N-8`.
- Byte layouts, generated from the parsers: `FORMATS-tables.md`. Tracing notes: `notes/vcf-chain.md`,
  `notes/vdf.md`, `notes/gdf-wdf-xdf-vtf.md`.
- Every variant's resolved stats: `vehicles.csv` (293 rows, `python data\fmt\vehicle_sheet.py`).
- Edit any of these: `python data\mod\i76mod.py alias <file>` lists the named stats; `car`/`set` edit them.

```
vppirna1.vcf ─┬─ VCFC ─┬─ vdf  ─> vppirnha.vdf  (body: mass, drag, class, size, hardpoints, geometry, collision)
              │        ├─ vtf  ─> piranha1.vtf  (paint: TMT texture remaps)
              │        ├─ engine/suspension/brake ids ─> compnent.cdf (via engsnd.dat for the engine)
              │        ├─ wdf front/mid/rear ─> wauto_1a.wdf (wheel hp, mass, size)
              │        └─ armour[4], chassis[4], spare
              ├─ SPEC x0..3 (special equipment ids)
              └─ WEPN x0..5 ─> g*.gdf (weapon) ─> ORDF (projectile) ─> x*.xdf (impact effect / blast damage)
```

## 1. Where the files are read (three contexts)

| context | loader | table | what it builds |
|---|---|---|---|
| in-game spawn | `vcf_LoadForObject` 0x4ad6f0 (from the ODEF OBJ handler 0x4b7bdc and network spawns 0x4512e5/0x45148b) | 0x4fef70 | the live vehicle: `obj` and its class data `veh = [obj+0x70]` |
| shell / garage | `vcf_LoadShellRecord` 0x4ad8c0 (from shell_cb_05 0x4b58c2) | 0x4fefb0 | a flat display record for the garage screens |
| multiplayer join check | 0x4b35a0 (shell_cb_26, caller 0x457072) | 0x500050 | legality flags + CRC32 of vdf/wdf/gdf/cdf; failure prints "*** %s has tried to join with a hacked vehicle!" |

A `.vsf` next to the `.vcf` (same stem) restores saved damage state in game (0x4ad864 loads it when the file exists).

## 2. The .vcf (VCFC, SPEC, WEPN)

| stat | VCFC offset | read at | lands in | effect |
|---|---|---|---|---|
| variant name | +0x00 char[16] | shell 0x4adbb1 | garage record +0x50 | name in the garage |
| chassis file | +0x10 char[13] | 0x4ad96b | LoadDef(.vdf) | the body; see section 3 |
| texture set | +0x1d char[13] | 0x4ad98e | LoadDef(.vtf) | paint scheme; section 6 |
| engine | +0x2a u32 | 0x4ada12 | cdf lookup via `engsnd_EngineIdToCompId` 0x469f10 | engine number in engsnd.dat: selects the ENGN row, the engine/horn/ignition sounds |
| suspension | +0x2e u32 | 0x4ada08 | SUSP row | section 4 |
| brakes | +0x32 u32 | 0x4ada0b | BRAK row | section 4 |
| front wheels | +0x36 char[13] | 0x4ad9b0 -> 0x4ae5e0(slot 0) | wheel pair | section 5 |
| mid wheels | +0x43 char[13] | 0x4ad9ce (slot 2) | wheel pair or none ('null') | 6-wheelers |
| rear wheels | +0x50 char[13] | 0x4ad9ec (slot 4) | wheel pair | |
| armour F/L/R/B | +0x5d u32[4] | 0x4adac1..0x4adb12 | veh+0x138, +0x158, +0x178 (three copies) | armour points per facet, **copied verbatim** |
| chassis F/L/R/B | +0x6d u32[4] | 0x4adb14..0x4adb69 | veh+0x148, +0x168, +0x18c | chassis (inner) points per facet |
| spare points | +0x7d u32 | shell 0x4adc70; check 0x4b3889 | garage record +0xa9c | unallocated points; dead in game (overwritten at 0x4adb6b) |
| special equipment | SPEC u32, up to 3 | 0x4ade85 -> `veh_AttachSpecial` 0x467280 | veh+0x3ec+slot*4 | 1 jammer, 2 nitrous, 3 blower, 4 exhaust brake, 5 structo bumper, 6 curb feelers, 7 mud flaps, 8 heated seats, 9 cup holders (Open76 names); a 4th SPEC is ignored |
| weapon | WEPN {u32 hardpoint, char[13] gdf} | 0x4aebea / 0x4aebed | mounted on the VDF hardpoint whose HLOC index matches (0x4aec5f) | a weapon whose hardpoint does not exist is silently skipped |

**Armour and the live entity.** The VCFC handler copies the eight values verbatim (plain `mov` / `rep movsd`) into
three banks: +0x138 armour / +0x148 chassis, +0x158 / +0x168 (maxima), +0x178 / +0x18c (the bank the HUD ratio
0x463a80 reads as numerator over +0x158), with 100 stored at +0x188 and +0x19c. **The doubling happens after load**:
0x463120 (at 0x463665..) doubles armour, maxima and chassis when `0x452d20() == 0` (not a network game), found by
the main session (`status\tasks\armour-hunt.md`). So single-player vehicles carry twice the file's armour, and
multiplayer ones carry the file value. Live A/B (capture 012, commit 6cebebe0): zeroing +0x178[0] destroyed the
vehicle in 81.6 s, while zeroing +0x138[0] did not in 150 s. That makes **+0x178 the live armour value**.
Open: the in-game .vsf restore (0x4b0350) writes saved armour to +0x138/+0x158 only and never +0x178, so restoring a
damaged state from a .vsf may not reach the bank that matters (LIVE-TESTS.md T2).

**Legality budget (multiplayer only).** With `s = VDFC.size` (6 is treated as 10 and 5 as 4, 0x4b389e), the join
check needs `spare + sum(armour) + sum(chassis) == 1600*s` (0x4b3919, else flag 0x400) and every facet `>= 50*s`
(0x4b38da, else 0x800). 187 of the 293 stock variants pass exactly; the rest are AI/mission vehicles that never join.
The check also bans wheel and weapon files from lists (tank guns, truck wheels on cars) and CRCs every referenced file.

## 3. The .vdf (chassis)

| stat | chunk / offset | read at | lands in | consumer / effect |
|---|---|---|---|---|
| display name | VDFC +0x00 char[20] | shell 0x4adf7e | garage record +0xa0 | name (a 20-char name has no NUL; strcpy over-reads by one) |
| class | VDFC +0x14 u32 | 0x4adeea -> `obj_SetClass` 0x461970 | obj+0x6c, class descriptor 0x4f76e0 | 1 car, 8 emplacement, 9 aircraft |
| size | VDFC +0x18 u32 | 0x4adf28, check 0x4b3cb4 | classdata+0x47c, 0x5db958 | armour budget class (section 2) |
| LOD distances | VDFC +0x1c f32[5] | 0x4adf41 | entity +0x1c..+0x2f | when lower-detail geometry switches in |
| **mass** | VDFC +0x30 f32 | 0x4adf0d | veh+0xa4 | `rigidbody_SetMass` 0x438340 stores m and 1/m; kill scoring uses the victim/killer mass ratio (0x40129c) |
| collision multiplier | VDFC +0x34 f32 | 0x4adf19 | classdata+0x124 | no reader found; 1.0 everywhere |
| **drag** | VDFC +0x38 f32 | 0x4adf1f | classdata+0x120 | aerodynamic term `k*v^2*drag` (0x43ad99, 0x40fb07): top speed |
| hardpoint count | VDFC +0x3c u32 | 0x4adf57 | veh record +0xa5c | how many HLOC mounts exist |
| HUD element file | VDFC +0x40 char[13] | 0x4adf31 -> `elt_Load` 0x448010 | | cockpit gauges layout (vpit_1.elt) |
| geometry | VGEO: u32 n + 7 LOD x 4 damage rows of n 100-byte parts | 0x4ae3a0 -> 0x4b75a0 | object tree + geometry cache | only row (LOD 0, intact) transforms are read; other rows supply only the mesh names. 3.6 MB of stock VDF data is never read |
| body panels | VGEO part class 65-72 | callback 0x4ae2e0 | classdata+0x408..0x41c, 0x3a0/0x3a4 | front/middle/back/top body, bumpers, head and brake lights (damage and texture targets) |
| gauges, cockpit camera | VLOC class 35/36/38/40/42 | 0x4ae000 | classdata+0x3f8/0x3fc/0x440/0x398/0x12c | tach needle, speedo needle, headlight mask, cockpit camera mount, a point |
| collision box | COLP 12 floats (Z, X, Y planes) | `colp_BuildBox` 0x4b81c0 | entity +0x18 | vehicle collision box (ignored for class 8) |
| break-off chunks | VCHK parent + n x {name, transform, radius, half extents} | 0x4ae400 -> `obj_AddChunk` 0x4a0ff0 | per-part debris | pieces that come off under damage (inferred) |
| weapon mounts | HLOC {label, index, facing, mesh type, transform} | 0x4aea00 | veh record +0x378 + i*0xfc | where WEPN weapons attach; max 7 |
| lights | LOBJ | `light_Add` 0x477c20 | light table 0x58db84 | headlight cone (clamped 10..90 deg) and range (>= 20) |
| shadow mesh | SOBJ name | 0x4b8470 | obj+0x5c | |
| garage art | VSHL, WLOC tail, SPCS | copied only (0x4adfd0, 0x4ae5b1, 0x4aeb60) | garage record | UI positions (inferred); no reader of the copies found |

## 4. compnent.cdf (engine, brakes, suspension)

The VCF ids select rows (4 of each). Brake and suspension ids index directly; the engine id goes through engsnd.dat
(`ENG NUM` -> `ENG COMP ID`, 0x469f10), so engine 5 (Marx) and 10 use row 3, and 4/20/41/50/51/99 use row 0.

| record | field | read at | lands in | effect |
|---|---|---|---|---|
| ENGN | max hp +0 | 0x4b0dca | engine+0/+4 (current/max) | engine health |
| ENGN | power +4 f32 | 0x4b0dd5 | engine+0x14 | drive force: `power * x * (1/mass) * veh+0x128` (0x43c55e) |
| ENGN | mass +8 f32 | 0x4b0dea | veh+0xa4 += | |
| BRAK | max hp +0 | 0x4b0e25 | brake+4/+8 | |
| BRAK | strength +4 f32 | 0x4b0e31 | brake+0xc; effective +0x10 = max(cur/max, 0.2) x strength (0x46a7f0) | braking force (0x43c49a); "fdmg1.wav" below half |
| BRAK | mass +8 | 0x4b0e3f | veh+0xa4 += | |
| SUSP | max hp +0 | 0x4b0d4c | susp+0/+4 | |
| SUSP | handling +4 f32 | 0x4b0d69 | susp+0x14/+0x18 | handling coefficient (0x43c7c2, inferred name) |
| SUSP | percent +8 f32 | 0x4b0d4f..0x4b0d81 | susp+0x1c = (100-x)/100 | stiffness/softness (inferred) |
| SUSP | mass +0xc | 0x4b0d86 | veh+0xa4 += | |
| NTBL/BTBL/STBL | 64 x char[16] | 0x4b0f6f.. | garage | component names ("432ci SHO V8", "4-Wheel Disc", "EtherX Rally") |

Stock values: engine power 104440 / 138010 / 193960 / 290940, mass 200-340; brakes 1.0-2.0, mass 12-20; suspension
handling 1.0-2.0, percent 0/10/20/45, mass 35-46. Every record's hp is 300 / 150 / 200.

## 5. .wdf (wheels)

| field | offset | read at | effect |
|---|---|---|---|
| name | +0x00 char[16] | 0x4ae92c | garage name ("15in Rally") |
| hit points | +0x28 i32 | 0x4ae8c0 | [wheel+0x70]+4/+8 (current/max) |
| mass | +0x2c f32 | 0x4ae8ec | veh+0xa4 += 2*m (one pair per slot) |
| size factor | +0x30 f32 | 0x4ae8cf | [wheel+0x70]+0xc: 1.0/1.2/1.4/1.6 for 13-16 in (use inferred) |
| icon | +0x34 char[14] | 0x4ae93f | garage icon |
| geometry | WGEO 16 groups: right/left x 4 LOD x 2 variants | 0x4ae980 | wheel meshes |
| +0x10..+0x27 | flag + 5 floats | never read | |

## 6. Weapons (.gdf -> ORDF -> .xdf)

| stat | where | read at | effect |
|---|---|---|---|
| class, sub | GDFC +0x10, +0x14 | 0x4aedaf, 0x4aee01 | weapon family; sub >= 100 = turret variant (mount forced to the turret location) |
| **damage per hit** | GDFC +0x2c i32 | 0x4aed77 -> weapon rec +0x60 -> instance +0x10 -> projectile +0x44 | at impact x difficulty factor, split evenly over the ORDF damage-type bits (0x4a774d..0x4a7797) |
| weapon hp | GDFC +0x30 | 0x4aed7e | the weapon's own health |
| mass | GDFC +0x34 f32 | 0x4af1b7 | added to vehicle mass |
| projectile lifetime | GDFC +0x46 f32 | 0x4aedfa | range = lifetime x ORDF speed (500 for guns, 1000 for missiles in the stock data) |
| burst cooldown | GDFC +0x4a f32 | 0x4aed8c | pause after a burst |
| **fire rate** | GDFC +0x4e f32 | 0x4aed9a | shots per second (interval 1/rate, 0x4a6659) |
| burst count | GDFC +0x52 i32 | 0x4aee11 | shots per burst |
| ordnance id | GDFC +0x5a | 0x4aedbd | links the ORDF projectile |
| **ammo** | GDFC +0x5e i32 | 0x4aeda8 -> instance +0x20 | capacity; decremented per shot (0x4a6f64) |
| spread | GDFC +0x62 f32 | 0x4aee1f | random aim error in degrees |
| sounds, muzzle flash | GDFC +0x66 / +0x73 / +0x84 / +0x94 | 0x4aef5f, 0x4aeeee, 0x4aee53, 0x4aede7 | |
| projectile speed | ORDF +0x04 f32 | 0x4aef8a | muzzle velocity |
| gravity | ORDF +0x08 f32 | 0x4aef98 | x -9.8 (0 = straight line, 4 = mortar arc) |
| damage types | ORDF +0x0c | 0x4aefbe | 1 bullet, 2 explosive, 4 fire, 8 blox |
| impact effects | ORDF 8 x char[13] | 0x4a7190 | effect/sound per surface hit (ground / car / building / other) |
| blast damage, radius | XDFC +0x1c, +0x20 f32 | 0x49ecdf -> 0x435120 | area damage of an explosion (grenade 95, big building 150) |

Published weapon table cross-check (docs\WEAPON-STATS.md): GDFC mass matches the published weight in 21 of 24 rows,
ammo in 23 of 25, and fire rate equals published damage-per-second / damage-per-round for all 6 slug throwers.

## 7. Total mass (prediction checked by the stat sheet)

`veh+0xa4 = VDFC.mass + ENGN.mass + BRAK.mass + SUSP.mass + 2 x WDFC.mass per wheel slot + sum(GDFC.mass of
mounted weapons)`, then `rigidbody_SetMass` (0x438f3b -> 0x438340). Jade's Piranha (vppirna1.vcf): 1951.0. The
Jackrabbit "Banshee": 2198.0. `vehicles.csv` has the figure for every variant; LIVE-TESTS.md T3 reads veh+0xa4 live.

## 8. Top changes a modder can make, and the field that does it

1. Armour and chassis per facet: VCFC +0x5d / +0x6d (`i76mod.py car <vcf> armour.front=900`).
2. Weapon loadout and mounts: WEPN gdf / hardpoint (`weapon1.gdf=gmheavy.gdf`).
3. Engine, brakes, suspension choice: VCFC +0x2a / +0x32 / +0x2e.
4. Weapon damage, ammo, fire rate, spread, range (GDFC) and projectile speed/arc (ORDF).
5. Vehicle mass and drag (VDFC +0x30 / +0x38): acceleration, top speed, ramming.
6. Engine power / brake strength / handling for every car at once (compnent.cdf).
7. Specials (SPEC), wheels (VCFC wdf slots, WDFC hp/mass).
8. Explosion damage and radius (XDFC).
9. Paint scheme (VCFC vtf, VTFC TMT remaps).
10. Mission-side: far clip, time of day, surface grip and damage, placements, scripts (see FSM.md and FORMATS.md).
