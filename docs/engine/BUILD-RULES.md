# Build rules: what each version of the original does differently

The question purists ask first: "which version behaves which way?" This page answers it for the three original builds
that matter, one row per rule, with how each answer is known. The kit runs the GOG build's rules everywhere; the last
column names the kit switch where one exists. A row with no switch is a fact about the original, **not** a promise of a
switch.

**Builds** (md5 prefix):

| short | build | md5 | what it is |
|---|---|---|---|
| **R** | retail 1.0 | `6cc509ad` | the March 1997 CD; measured in 86Box on an emulated P166, Windows 95, software renderer |
| **G** | Gold 1.2 = GOG | `9a232dcc` | the February 1998 build GOG sells (installer 2.1.0.17); the kit's rules |
| **N** | Nitro Pack (GOG) | `28b8ae27` | Gold's engine five weeks later (EXE-DIFF-MAP s.8) |
| AiO | community 2019 | `60abf7bc` | Gold + UCyborg's fixes and its `I76PATCH.DLL` 20 fps limiter; not an original build. GOG ships neither |
| ours | the kit's daily driver | `6319abf7` | AiO + the `u32x` import rename; Gold's rules |

The 1997 patches (1.05, 1.06, 1.081, 1.083) are held and described in [I76-VERSIONS.md](../records/I76-VERSIONS.md);
no retail 1.1 measurement exists anywhere. "1997" on this page always means R.

**Confidence:** **S** = static reading of the decompiled functions of R, G and N side by side; **M** = measured with the
game running (n given). Sources at the bottom.

## 1. Rules that differ

| rule | R (1997) | G = GOG, N | how known | kit |
|---|---|---|---|---|
| **AI attack-tactic chooser** | a stub: `dirt_gunner` every time, no weighted draw, no precondition. In T14 the lead cop circles the idle player 10-90 m off, mostly out of sight, and fires 3-19 rounds in its first 20 s, then a few a minute | weighted draw by aggression, preconditions, 18 tries, `dirt_circle` fallback. In T14 the lead cop takes `road_side` from its first attack and patrols the road with the player in view | S (both choosers) + M: R T14 n = 7 (6 idle, 1 driving), G T14 n = 2 (Gold CD exe in the same emulator) | G's chooser; no switch |
| tactic weight tables | identical | identical | S (byte compare) | - |
| **turret slew** | dt x 1.5 rad/s (helicopter 6.0) x the weapon's hp ratio; ratio 1 online | dt x 1.7 rad/s (6.8) x (0.75 + 0.25 x hp ratio); x1 online | S, two independent reads (EXE-DIFF-MAP s.6 and the I26 build-versions lane); the consequence measured in I26: a 7.62 turret against a car circling 25 m off at 25 m/s hits 77 / 75 % (whole / half health) under G's rule, 75 / 7 % under R's | G's slew; no switch |
| **heat-seeker cone** | \|cos\| > 0.84 (about 33 deg) | \|cos\| > 0.94 (about 20 deg) + a class-1 target guard; range 650 m in both | S | G's cone; no switch |
| **health %** (`object_HealthFraction`; read by AI flee, damage smoke, script `hpLesser`, the .45 critical kill, the target brackets) | banded and scaled, over 7 core parts including the 4 wheels | the raw 0..1 ratio over 3 core parts (engine, suspension, brakes): the scaling was lost in 1998 | S (EXE-DIFF-MAP s.5) | `I76_FIX_HEALTH_PCT=1` = min(28 + 72 r, 100 x core), which is **neither** formula (EXE-DIFF-MAP s.6, item 6) |
| **player damage factor** (Difficulty Level) | none (x1.0) | Wimp x2.0 / Champion x1.0 / Badass x0.75; offline only; player-fired rounds and flame only, never the .45. A fresh GOG or Nitro install is on **Wimp** (byte 0 at DEF +0x5c in the installer's `I76PLYR.DEF` and `nitplyr.def`) | S; M on the kit's exe: 50cal 50 / 25 / 18 per hit (DIFFICULTY-OPTION-2026-10-20, AI-DAMAGE-METRICS s.4) | the game's own Play Options; the kit does not change it. **Champion = 1997 damage** |
| landing-wreck step guard | a car wrecked by its own landing finishes that substep | from 1.05 on, and in G, the step stops | S (I76-VERSIONS s.3.2) | G's; invisible to a car that survives |
| cloud scroll step | 1/1024 per `DrawClouds` call; with the mirror on, the full mirror (and its clouds) is redrawn every frame: 2.000 calls / frame | 1/(1001 - s) per call; the Gold capture saw 1.5 calls / frame | S; M R: 2 + 2 boots, zero spread (lab `captures\i26-gaps-20261101\emu.md` row 3b) | G's; `I76_SIM_TICK_SKY_REF` assumes G's cadence |
| tank cannon turret tier | from tier 10 | from tier 100 | not verified: from I26's deviations list; whether the exe or the data holds it is not traced | follows the install |
| data retunes | 1.0 / 1.06 ZFS | Gold ZFS: bus mass 9,000 -> 12,730, `xgasx1` Gas blast 500 -> 100, armour and loadouts, 56 vdf pointers | S (I76-VERSIONS s.2.6) | follows the install's data |

## 2. The same in every build, measured

Each was measured on R in the emulator and is the same code (S) in G and N. These are the rows a "the old version felt
different" report most often lands on.

| rule | the original | how known |
|---|---|---|
| turret lead | aims at the target predictor at the closest-approach time + 0.09 s (fit tau' 0.437 s at 50 m, 150 m/s rounds) | M: 2 boots, 491 rounds, IQR <= 0.05 m per condition ([TURRET-LEAD-RETAIL-2026-11-02](../records/TURRET-LEAD-RETAIL-2026-11-02.md)) |
| rounds and the carrier's velocity | rounds leave at the muzzle speed along the barrel; the carrier's velocity is never added (player 50cal 149.99 m/s while driving 18-26 m/s, AI MG 200.0 m/s); turrets still hit from a moving carrier (37/37 at 21-23 m/s) | M: > 200 rounds, spread < 0.1 m/s (same record) |
| AI dropper gate | drops when a straight-line prediction of the pursuer passes within 2.5 m; no speed ceiling (drops at 20-60 m/s) | M: 4 boots, 33 valid trials ([AI-DROPPER-GATE-RETAIL-2026-11-02](../records/AI-DROPPER-GATE-RETAIL-2026-11-02.md)) |
| ram credit | both cars are stamped, both ways | M: 2 boots, 8 trials, 1 contact |
| radar sweep | clockwise, 30 positions, one turn in 6.0 s, frame-rate neutral | M: 4 tests at 13-32 fps ([RADAR-SWEEP-RETAIL-2026-11-02](../records/RADAR-SWEEP-RETAIL-2026-11-02.md)) |
| cockpit needles | the same needle code; colours and pivots come from each build's data | S + M images |
| flamer stream | updated once per frame plus once from the mirror pass; G adds only the difficulty factor | S |
| vehicle physics, landings, the T05 jump | the same code and constants; the wreck rate follows the frame step (T05 G vs R in the emulator, Fisher p 0.19, not significant) | S + M |
| ordnance pool | 160 offline / 40 online | S |
| AI turn speed | stored at spawn (12.52198 m/s for T05's wheeled AI, zero spread) | M: 2 boots, 7,277 frames |

## 3. What this means for the kit

- The kit is GOG's rules (G) with fixes for what changes with the frame rate. Nothing on this page is switched to R by
  default, and only health % has a kit switch, which is its own formula, not R's.
- AI comparisons between R and G compare two different tactic choosers (section 1, row 1); a gap in AI rounds per
  minute between them is partly the chooser, not the frame rate.
- Switches that put R's rules back (turret slew, cone, banded health %, the chooser stub) are proposed for after 1.1 (the kit's first full release, `v1.1.0`),
  each behind an A/B (BASE-DECISION s.5).

## Sources

- [EXE-DIFF-MAP.md](../records/EXE-DIFF-MAP.md) (static R / G / N map), [I76-VERSIONS.md](../records/I76-VERSIONS.md)
  (the versions, the data retunes, the landing guard), [DIFFICULTY-OPTION-2026-10-20.md](../records/DIFFICULTY-OPTION-2026-10-20.md).
- The I26 build-versions lane (2026-11-03): the side-by-side static read of R, G and N, the Gold T14 emulator runs
  (session `20261103-052812-bvg-sess`) and the I26 slew probe; the I26 AI-cadence lane (R T14 n = 7, the weight tables).
- Lab captures `i26-gaps-20261101` (`emu.md`, `emu2.md`), `round-velocity-20261102`, `radar-20261102`.
