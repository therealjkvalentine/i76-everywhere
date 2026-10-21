# Nitro Pack against stock 1997 retail: the difference map (2026-10-20)

Lane `nitro`. Owner request (verbatim): "Please analyze nitro engine to find the differences if any from stock 1997
retail". Static analysis of the three exes, a full parse of the Nitro data through the data track's byte-exact parsers,
and nine headless boots of a lab copy (exp-nitro). Nothing outside the lab copy was touched.

**The exes compared.**

| id | file | md5 | link (PE) | compiler | size |
|---|---|---|---|---|---|
| retail 1.0 (gold standard) | `I76.EXE` (CD 1) | `6cc509ad` | 1997-03-16 06:30 | VC4.2, static CRT, LINK 4.20 | 1,019,392 |
| Gold 1.2 (GOG) | `i76.exe` | `9a232dcc` | 1998-02-19 22:21 | VC5, MSVCRT, LINK 5.10 | 1,050,624 |
| **Nitro Pack** (GOG) | `nitro.exe` | `28b8ae27` | 1998-03-27 22:14 | VC5, MSVCRT, LINK 5.10, LZO 1.00 "Mar 16 1998" | 1,070,080 |
| ours (shipped) | `i76.exe` | `6319abf7` | 1998-02-19 22:21 | = Gold + AiO 2019 + u32x import rename | 1,051,648 |

**How "Nitro vs retail" was measured.** The two exes come from different compilers, so their bytes cannot be compared
directly (Version Tracking matches 5.8 % of functions across VC4.2 / VC5). Nitro and Gold share a compiler and were
linked five weeks apart. So the map runs through Gold, with an independent cross-check:
- Nitro <-> Gold: Ghidra Version Tracking plus call-graph propagation, then a normalised instruction compare (lab
  `emu\tools\memtrace\exediff`, EXE-DIFF-MAP section 8, rebuilt today byte-identical).
- Gold <-> retail: the feature matcher of EXE-DIFF-MAP (float constants, strings, imports, data, struct offsets,
  callees, plus call-graph propagation), with 23 hand-verified anchors.
- **New today, independent:** Nitro <-> retail matched directly with the same matcher, no seeds and no function pairs
  from Gold (only data-table pairs carried over). See section 1.

Evidence classes: **[code]** read in disassembly or decompiler output; **[data]** measured on the files by the parsers;
**[run]** a headless boot; **[doc]** Activision text; **[prior]** an earlier record, cited.

**2026-10-21 follow-up: [NITRO-BASE-2026-10-21](NITRO-BASE-2026-10-21.md)** - the reverse direction (can Nitro play the
original?): the GOG Nitro install ships none of the original campaign, arena or scene-movie files and its shell has no
trip; two owner copies under `Games\I76\nitro*`.

## Answer

1. **Nitro is Gold's engine five weeks later, not a new engine.** 1,997 of Nitro's 2,200 functions match a Gold
   function. 1,781 of those are the same instruction stream after relinking is normalised.
2. **Against retail 1.0, about 60 % of Nitro's functions have a located counterpart**: 1,324 by composition through
   Gold, 1,251 by the direct match. The two routes agree on 1,201 of the 1,226 they both place (98.0 %). The rest are
   VC4.2 inlining and new 1998 code (renderers, team play and race code), not "changed physics".
3. **Physics and handling: Nitro = Gold = retail's algorithm.** The same clock and the same substep rule. The car
   step, suspension, tyre and lateral model, attitude solver, collision and the arcade flag have the same constants
   and the same calls. The only physics-side code that differs from retail is Gold's two guards, which Nitro
   inherits; neither acts on a car in the air (section 2.1). Nitro's own physics differences from Gold are field moves
   (the entity grew by 4 bytes) and x87 scheduling.
4. **Car data: no handling change either.** Nitro's archive carries Gold's chassis, wheel and engine files
   byte-for-byte. So against retail it inherits only Gold's data retune: the bus 9,000 -> 12,730 kg, LOD distances,
   some armour and loadouts. Every Nitro car is a new `.vcf` on a chassis Gold already ships.
5. **Combat does differ from retail**, mostly through Gold:
   - the difficulty multiplier x2.0 / x1.0 / x0.75 on the player's damage, and Nitro's GOG DEF sits at x2.0;
   - Gold's health-% formula;
   - Gold's turret slew and heat-seeker cone.
   Nitro adds three changes of its own:
   - **droppers** (oil, fire, caltrops) fire at a speed-proportional rate, 1.2 + 0.18 x speed per second, where
     retail and Gold slow the drop rate only below 20 m/s;
   - two new garage specials, Dashboard Mary (weapon damage x1.1) and Tire Covers (wheel hp x2);
   - 7 new weapons.
6. **Data formats: unchanged.**
   - Every Nitro file is parsed byte-exact by the base parsers: 149 missions, 382 `.vcf`, 371 `.sdf`, the ZFS.
   - The FSM opcode and action set is identical: all 95 action names the Nitro scripts use are among the 96 the base
     exe knows.
   - **Race and CTF are not new file formats.** They are naming conventions inside ODEF (`check<N>`, `spawn<team>`,
     a class-0x5b flag object) that only Nitro's object handler acts on, plus a mode carried by the file extension
     (`.cbt`, `.rac`, `.cf2`-`.cf4`), which only Nitro's shell reads.
7. **Networking is a different stack.**
   - ANet 2 (`anet2.dll`, 1998-03-06, 108 exports, game-server lobby, auto-updater) replaces retail's and Gold's ANet 1
     (`ANETDLL.DLL`, 1997-03-27, 42 exports), with new transport DLLs.
   - The exe adds team spawn, scoreboard, flag ('FL' packet) and vehicle-validation code.
   - Nitro and Gold / retail cannot share a session.
8. **Renderer: Gold's plugins.** The D3D, Rendition, PowerVR, force-feedback and string DLLs are byte-identical to
   Gold's; ZGLIDE is a 1998-02-28 rebuild. Nitro keeps Gold's far-clip cap of 100,000, where retail capped at 1,000 /
   1,500 m. Every Nitro mission's own view distance (WRLD +0x137) is 600, as in the base missions.
9. **Our shipped exe `6319abf7` is the Gold family.**
   - It is GOG's Gold build `9a232dcc`, with the `WINMM` import restored, plus the 2019 AiO patch (`60abf7bc`).
   - It also has a 10-byte import rename, `USER32.dll` -> `u32x.dll` at file offset 0xbff84.
   - All three carry the same 1998-02-19 22:21:32 link stamp. It is not retail 1.0 and not Nitro.
10. **Add-on verdict.**
    - Nitro's **single-player missions** load in our exe as add-on files: P01 booted to a live player car with its
      opening script running (4 of 6 boots; the stock control came up 4 of 4).
    - Its **combat arenas** use the base format and assets and need no code (static).
    - **Race and CTF** load as arenas, but their rules (laps, flags, team spawns) are Nitro exe code. Rebuilding them
      means porting a short, known list, or re-labelling the CTF spawns. Section 7a has the list.
    - The arena boots were not reached: the Instant Melee click route did not leave the shell in this harness, the
      stock control included.

## 1. Engine identity and the matched fraction

| measure | value | evidence |
|---|---|---|
| functions (Ghidra pass 4) | retail 2,318 / Gold 2,207 / Nitro 2,200 | i76-map `ghidra\export-*\functions.csv` |
| Nitro <-> Gold matched | 1,997 (90.8 % of Nitro); 1,781 same after normalisation (addresses, stack slots, entity fields >= +0x444 shifted 4) | lab `exe_diff_map.json`, rebuilt 2026-10-20 (run.sh, byte-identical to the committed map) |
| Nitro with no Gold counterpart | 203 functions, 24,825 instructions | below |
| Nitro <-> retail, composed through Gold | 1,324 (60.2 % of Nitro, 57.1 % of retail's 2,318) | `m-nitro` x `m-retail` |
| Nitro <-> retail, direct (no seeds, no Gold function pairs; 1,171 data pairs carried over) | 1,251; agreement with the composed route 1,201 / 1,226 = 98.0 %; union 1,349 (61.3 %) | `match.py nitro.json retail.json` (lab exediff, today) |
| VT across the compiler change (control) | Gold -> retail 128 pairs (5.8 %) | i76-map `status\vt-cd1997.json` |

Of the 1,324 Nitro-retail pairs:
- 1,162 are pairs where Nitro is the same instruction stream as Gold, so whatever Gold-vs-retail says applies
  unchanged;
- 162 have Nitro-side changes, catalogued in section 8 of EXE-DIFF-MAP and below.

| subsystem | Nitro-retail pairs | of which Nitro = Gold | Gold-retail float constants differ (EXE-DIFF-MAP, read one by one there) |
|---|---|---|---|
| physics | 75 | 58 | 15: compile-time folding, inlining, one split function |
| ai | 168 | 161 | 9 |
| entity | 130 | 122 | 8 |
| weapon | 80 | 74 | 9 |
| fsm | 80 | 77 (3 changed by register order only) | 0 |
| simclock | 14 | 14 | 0 |
| world | 29 | 23 | 0 |
| net | 96 | 53 | 0 |

**Nitro-only functions (no Gold counterpart, 203):**
- the CTF flag logic: "%s's flag has been taken / returned / captured", `flagstub`, Nitro 0x444f80 / 0x4451d0 /
  0x455420 / 0x4557a0;
- race checkpoints and laps (0x444ad0 / 0x444bb0, `check%d`) and the per-mode objective text ("%d of %d Laps
  Completed / Flag Captures / Kills / Points", 0x444350);
- team spawn tables (`spawn%d`, 0x44c4a0; "Vehicle list in SpawnLoc module is full");
- per-mode scoreboards (0x44a3c0 .. 0x44c040);
- team join and messages, using `dpGetPlayerData` / `dpSetPlayerData`;
- the two new specials (0x4b0680, the 0xb case in 0x4246c0);
- about 40 large leaf functions at 0x473b30-0x4834c0 (software-rasteriser span variants, no strings);
- the remainder: CRT / exception-handling thunks.

**Identity strings [code].** "Interstate '76 Nitro Pack", `NITSHELL.DLL`, `nitro.zix` / `nitro.zfs`, `nitplyr.def`,
`nitmcar.def` (Gold: `MULTICAR.def`), `NSCORE.DAT` (Gold: `NSCR.DAT`), a `hacks` switch, and `Install\data\miss16|8`
mission paths.

## 2. Simulation

### 2.1 Frame and car step

| item | retail 1.0 | Gold | Nitro | evidence |
|---|---|---|---|---|
| clock | GetTickCount x 0.001 as float32, dt clamp [0.001, 0.2], sim_dt cap 1.0, first 3 frames skipped | same | same: `simclock_Update` Nitro 0x4a2d40 = Gold 0x49c920 instruction for instruction | [code] EXE-DIFF-MAP s.3; d-nitro "same" |
| substeps | count = floor(sim_dt x 20) + 1, at most 20; below 50 ms the car step is the frame time | same | same (`StepperBegin` Nitro 0x4a3040 = Gold 0x49cc20) | [code]; TWO-CLOCKS s.1 |
| init values | dt 0.06 (0x3d75c28f), rate 16.667 (0x41855556), reciprocal table 1/1..1/20 | same | same (`simclock_Init` 0x4a2c10) | [code] the three decompiles side by side |
| `physics_StepVehicle` | 0x472360 + 0x472890 | 0x438fd0 | 0x424da0, same instruction stream as Gold | [code] |
| landing-wreck guard (1.05) | absent | present | present (inherited) | I76-VERSIONS s.3.2 |
| both-front-wheels-damaged steer pull, collision-arm guard | absent | present | present | EXE-DIFF-MAP s.3 |

**Physics constants.** Over all 94 Gold physics functions, the only float-constant differences between Gold and Nitro
are in `simclock` (an initial-value artefact of the feature extractor; the code above is identical). The others are
`weapon_UpdateInstanceFiring`, the smoke emitter and sound. The 18 physics functions flagged "changed" differ by:
- entity offsets +4 at and above +0x444 (`IntegrateVehicleMotion`, `CheckImpact`, `ResolveGroundContact`, the lateral
  cap and the others);
- x87 operand order (`ApplySideSlipFriction`, `ApplyFriction`; read side by side, the same products and sums);
- the new collision classes 0x5a / 0x5b (`RebuildCollision`, `CollideBodyPair`), which are the CTF flag objects;
- `physics_InitEntity` (0x4246c0): Gold's per-special switch plus two new cases (2.4).

The arcade flag is the same five sites with the same arithmetic in all three exes (EXE-DIFF-MAP s.4; Nitro flag word
+0x458).

**Terrain sampling** (`world_GetTerrainSampleRaw`, Gold 0x493160, Nitro 0x494fe0) [code]:
- Gold masks the cell row with `and al, 0x80` and has no lower-bound test on the row.
- Nitro masks with `and ecx, 0xffffff80` and adds `row >= 0` / `col >= 0` tests.
- So Nitro fixed an out-of-bounds read at negative coordinates. The AiO patch later fixed the same site (EXE-DIFF-MAP
  s.9).
- The grid is the same size: index < 0x4000 after +0xc00. Retail's counterpart was not matched by the feature matcher.

**Verdict, physics:** Nitro's vehicle dynamics are retail's algorithm, with the same constants, plus Gold's two
grounded-only guards. No number in the handling code differs.

### 2.2 Car and wheel data

| item | retail 1.0 | Gold | Nitro |
|---|---|---|---|
| `compnent.cdf` (engines, brakes, suspension) | - | = retail (I76-VERSIONS s.2.6) | **= Gold, byte-identical** [data] |
| 48 chassis `.vdf`, 70 `.wdf` | - | bus 12,730 kg (retail 9,000); LOD 1 35 -> 45 on 22 cars | **= Gold, byte-identical** [data] |
| `.vcf` loadouts | - | Gold retune of some armour and loadouts | Gold's 293 identical, plus 88 new ones (P-mission cast and novelty cars on existing chassis: UFO, balloon, sandbag, hearse, ambulance, phantom ...) |
| `.gdf` weapons | 43 | same numbers as retail | Gold's 43 identical, plus 7 new: Caltrops (ord 14), Chemical Mortar (22), 4Get-U-Not Msl (20), Ball O'Flame (21) + turret, two MG variants (ord 1) |
| `.xdf` explosions | Gas 500 | Gas 100 | = Gold |
| mission surfaces (WRLD grip / drag / damage rate) | per mission | per mission | per mission. The re-issued arenas N51-N65 keep M01-M15's terrain byte for byte |

### 2.3 Difficulty and damage

- `weapon_BuildImpactDamage`: Nitro 0x4ade30 = Gold 0x4a76a0, the same instruction stream [code].
  - The player's offline damage is x2.0 / x1.0 / x0.75 for DEF byte +0x5c = 0 / 1 / 2.
  - The same rule applies in the flamer (Nitro 0x42b590, register order only).
  - Retail has no factor and no byte (EXE-DIFF-MAP s.5).
- GOG's `nitplyr.def` has +0x5c = 0 [data]: **Nitro as installed doubles the player's damage**, like GOG Gold.
- `object_HealthFraction` (Gold's broken scaling), turret slew 1.7 rad/s, and the heat cone 0.94: Nitro = Gold, the
  same streams (0x417ac0, 0x4af210, 0x421300).
- `entity_DamageAndKill` (Nitro 0x462c00): before the owner test (+0x486) it asks "team game?" and "score limit?"
  (0x448800 / 0x448810). This is kill credit in team games.

### 2.4 Weapons and specials (Nitro-only behaviour)

**Dropper cadence** (`weapon_UpdateInstanceFiring`, retail 0x458340, Gold 0x4a6470, Nitro 0x4b2000) [code]. The rule
applies to ordnance types 12 (Oil Slick), 14 (Caltrops) and 17 (Fire-Dropper). `v` is the car's speed from
`object_GetVelocity`.
- **Retail and Gold:** below 20 m/s the drop interval becomes `1 - 0.05 v (1 - 1/rate)`. That is 1.0 s at a
  standstill, rising linearly to the weapon's own rate at 20 m/s. Retail 0x458340 and Gold 0x4a6470 have the same
  expression.
- **Nitro:** the weapon definition's rate is overwritten with `1.2 + 0.18 v` drops per second, at every speed, and the
  interval is its reciprocal.
- Oil Slick (rate 60 /s):

  | speed | retail / Gold interval | Nitro interval |
  |---|---|---|
  | 0 m/s | 1.0 s | 0.83 s |
  | 10 m/s | 0.51 s | 0.33 s |
  | 20 m/s | 0.017 s | 0.21 s |
  | 40 m/s | 0.017 s | 0.12 s |

  So Nitro drops oil and caltrops more sparsely at speed.
- The formula writes into the shared weapon definition (0x5e3198 + type), not the instance.

**Specials** (`physics_InitEntity`'s per-slot switch; retail 0x471df0 and Gold 0x438a90 have cases 3 and 8 only):
- 3 Blower (x1.25 drive) and 8 Heated Seats (ammo x1.1) are unchanged.
- **10 Dashboard Mary** (Nitro 0x4b0680): every mounted weapon's damage x1.1.
- **11 Tire Covers** (case 0xb): every wheel's hp and max hp x2 at spawn. Gold already reads type 11 at a hazard hit
  (engine.md).
- The Nitro garage lists both items (`shell_GarageListSpecials` Nitro 0x4b5cf0).

**Other:**
- Turret firing, `weapon_SpawnProjectile` (ordnance switch already holds 0x14-0x16) and the projectile step functions
  are the same as Gold, apart from register order.
- `ai_RecordDamageEvent` gates on projectile +0x44 in retail, Gold and Nitro alike.
- The AI is the same as Gold: 198 of 205 matched AI functions are the same stream, and the rest differ in field moves
  and order. So AI behaviour, aim and skill scale are Gold's. AI vs retail is EXE-DIFF-MAP s.6: Gold's behaviour
  stack.

## 3. Data formats

Tool: i76-map `data\fmt\nitro_corpus.py`, outputs in `data\out\nitro\`; note `data\notes\nitro.md`.

| format | Nitro vs base | evidence |
|---|---|---|
| ZFS archive | same ZFSF v1 layout (100 per block, 68 blocks, 6,704 entries, no XOR). **All 5,624 names shared with GOG I76.ZFS are byte-identical.** Nitro-only: 985 voice .wav, 88 .vcf, 7 .gdf; base-only: 492 .wav (TRIP voices). The Gold ZFS (1998-02-16, the same date as nitro.zfs) already holds every Nitro chassis, texture, sdf and the CTF flag models | [data] |
| missions (.msn and the new .cbt / .rac / .cf2-.cf4) | the same BWD2 tree and chunk revisions (REV 2, WREV 9, TREV 4, RREV 1, OREV 3, LREV 1, AREV 1); 149 files round-trip byte-exact with 0 unknown bytes | [data] |
| ODEF OBJ record | same 100 B record. New meaning only in Nitro's handler (0x4b3660): leading `#` stripped; `spawn<N>` = team N's spawn table (5-char compare); `check<N>` = race gate (99 = final gate); class-0x5b sdf (flag stub) dropped outside team games. Retail / Gold compare `spawn` / `regen` over 8 chars (exact labels) and treat any other class-1 label as a car `.vcf` | [code] Gold 0x4b7ac0, msn-sdf.md s.4 |
| FSM | 14 opcodes, 96 prototypes, same names; `fsm_OpcodeSwitch` Nitro 0x414db0 = Gold 0x414670; `fsm_ActionDispatch` differs by register order only. All 95 action names in Nitro's 40 scripts are known to the base exe. **No checkpoint or lap action exists: race logic is not scripted** | [data] [code] |
| terrain .TER | same format and grid; N51-N65 .TER = M01-M15 .TER byte for byte | [data] |
| .vcf / .vdf / .sdf / .gdf / .wdf / .xdf | same layouts; every Nitro file parses byte-exact | [data] |
| I76PLYR.DEF | `nitplyr.def` 96 B = Gold's layout (retail 88 B); loader reads 0x60 B in both | [code] Nitro 0x49e290 / Gold 0x4970f0 |
| savegame | not compared (out of reach today) | - |

**Base files Nitro loads unchanged:** all 5,624 shared ZFS entries, Gold's `gamekey`, font and cursor files (same
names), and the renderer DLLs. **Base files Nitro does not use:** `I76.ZFS` / `I76.ZIX` (it mounts `nitro.zfs`),
`I76PLYR.DEF` (`nitplyr.def`), `MULTICAR.def` (`nitmcar.def`), `DATABASE.MW2` (the shell reads `DATABASE.TVF`), and
`I76SHELL.DLL` (`NITSHELL.DLL`).

## 4. Renderer

- **Plugins.** `zdx5draw`, `zredline`, `zpowervr`, `i7_sfrce`, `strlkup`, `smackw32` and `glide2x` are byte-identical
  to GOG Gold. `zglide` is a 1998-02-28 rebuild of Gold's 1998-02-18 one, 512 B smaller, not diffed further. GOG ships
  its own `win32.dll` build with each product.
- **Draw distance.**
  - `camera_Init` Nitro 0x469dd0 = Gold 0x472220: far clip clamped to [100, 100,000].
  - `camera_SetViewportRect`: x87 order only.
  - Retail clamped at 1,000 and 1,500 (EXE-DIFF-MAP s.7).
- **The "VIEW tag".** I'76's equivalent of the MW2-family VIEW tag is WRLD +0x137 (`farClip`, msn-sdf.md). It is 600
  in all 74 Nitro missions and in all base missions. A FarPatcher-style edit is a data patch of that field, the same
  for Nitro and base files.
- **LOD.** The LOD distances come from Gold's data (vdf LOD 1 at 45). `renderer_SubdivideTerrainQuad` carries the
  same signed-index fix as the terrain sampler.
- **Sound.** Nitro adds Aureal A3D (`CoCreateInstance` import; "Can't create A3D listener" strings in
  `sound_CreateDirectSound` 0x41bea0).

## 5. Networking

| item | retail 1.0 | Gold | Nitro |
|---|---|---|---|
| network DLL | `ANETDLL.DLL` (1997-03-27, 42 exports), 9 imports | same DLL, 10 imports (+`dpDestroyPlayer`, the 1.06 boot) | **`anet2.dll`** (1998-03-06, LINK 4.20, 108 exports: `dpEnumServers`, `dpSetGameServer`, `dpReadAnetInf` ...), 14 imports (+`dpClose`, `dpDestroy`, `dpReportCrash`, `dpSetGameServer`) |
| transports | `DLL\WINET / WIPX / WMODEM / WSERIAL` | same | `dll\WINETS2 / WIPX2 / WMODEM2 / WSERIAL2` (all different binaries); `internet.lst` Activision lobby servers; `dkupddll.dll` updater ("This upgrade is required to play in multiplayer mode") |
| packet tags (2-letter immediates in exe code) | CH JD JO PF RE SC SH SP SR ST UU XX YY | + BO | + **FL** (flag) |
| player record | | 72 B | 80 B (team field; `net_FindPlayerById` etc. 72 -> 80) |
| spawns | one table, `spawn` / `regen` | same | per-team tables, "no spawn points for team %d" |
| difficulty in network games | none | factor applies only offline (player shooter, not network) | same as Gold (same stream) |
| hack prevention | - | - | joiners' vehicles re-validated from the file unless `-hacks` (Nitro 0x446120, flag 0x526a68) |
| direct IP | - | - | not traced; ANet 2 adds game-server enumeration; the address dialogue lives in the shell / transport DLLs |

Nitro and retail / Gold cannot share a session: they use different ANet generations and transports, an 80 B vs 72 B
player record, and a new packet.

## 6. Shell and menus

`nitshell.dll` f804f50d (1998-03-20, 321,536 B) is a different shell from Gold's `i76shell.dll` (352,256 B). There
are 1,157 strings only in Nitro's and 1,397 only in Gold's. From strings only (not traced):
- modes "Race", "2/3/4 Team C.T.F.", "Not a team game" / "No Team", "%d Laps" / "%d Captures";
- arena lists from `*.cbt` / `*.rac` (and `addon\*.cbt` / `addon\*.rac`) instead of a fixed table plus
  `addon\*.lvl`;
- host weapon restrictions ("All Weapons / All Droppers / All Missile Launchers ...", "No Limits!", "Are you sure you
  want to exceed the recommended defaults?");
- passwords;
- a character-based single-player menu (`SCENARIO.DAT`: Taurus, Jade, Skeeter, Natty Dread; 19 missions P01-P19,
  plus training B01);
- "Difficulty Level" (both shells);
- the garage specials Dashboard Mary and Tire Covers.

## 7. Verdicts for the owner

### 7a. Can our exe (6319abf7 + i76shell a300db63) load Nitro arenas, missions and cars as add-on files?

**Which exe ours is (settled).** Byte comparison today:
- `6319abf7` differs from the AiO exe `60abf7bc` in 10 bytes: the import name at file offset 0xbff84, `USER32.dll` ->
  `u32x.dll`.
- `60abf7bc` differs from GOG's `9a232dcc` in 3,099 bytes plus a 1,024-byte tail. These are the AiO clusters, and
  `WIN32.dll` -> `WINMM.dll`.
- All three have the PE stamp 1998-02-19 22:21:32.

So ours is **Gold 1.2's build, patched**. I76-VERSIONS lists GOG's file as `9a232dcc` because that is what GOG ships;
the driver carries the AiO + u32x derivative of it. Everything said here about "Gold" holds for our exe, except the AiO
clusters (EXE-DIFF-MAP s.9).

**Single-player missions (P01-P19, B01): yes, measured.**

| boot (lab exp-nitro, private desktop, `I76_MISSION`) | player car up | first seen | n |
|---|---|---|---|
| control `t01.msn` (stock) | 4 of 4 | 16-29 s | 4 |
| `p01.msn` (Nitro "A New Hope", 4 Nitro `.vcf` in ADDON) | 4 of 6 (runs 3-6 all up; runs 1-2 no player within 75 s / 40 s, no message box, process alive) | 6-32 s | 6 |

In the P01 runs that came up:
- the opening script ran (scripted flag 1), then released the car;
- the player object (the mission's `vdrampg2`, flag 0x10) moved from its ODEF position z 47,332 to 47,600-48,300.

The two early misses are unexplained. They were the first two boots after staging, and the window list showed only
the game window. Treat them as an open item, not a format failure. A boot sampler (thread EIPs) was added after them
and never fired again.

What a mission needs:
- the `.MSN` / `.TER` / `_16.PCF` in `miss16` (and `miss8`);
- its Nitro-only `.vcf` (1-6 per mission) and any Nitro `.gdf` in ADDON;
- optionally the 985 Nitro voice `.wav`, otherwise the radio lines are missing (not tested).

Not reached: the full play-through, mission success and fail, and Nitro's character-based campaign flow. Our shell has
no `SCENARIO.DAT` menu; the missions are reachable by `I76_MISSION` or by a list edit.

**Combat arenas (.cbt, 24): yes, static.**
- N51-N65 are the stock arenas re-laid.
- All 24 use the base format, plain `spawn` / `regen` labels (case-insensitive, exact in the base handler) and only
  base assets.
- Route: rename to lower-case `.lvl` in ADDON with the `.TER` (COOP-LIST-ENTRIES s.1). Our shell lists it and the
  network CRC check covers it.
- Not booted: see the end of this section.

**Race (.rac, 13) and CTF (.cf2-.cf4, 17): they load as arenas, but the rules need code.** What our exe does with them,
from code:
- **Race:** `check<N>` objects are class-1 records. The base handler tries to load `check<N>.vcf`, fails and drops the
  record (0x4b8230 returns 0; whether the walker continues after that was not traced). The arena then plays as a
  melee on the race course with `SPAWN` points.
- **CTF:** every spawn is `#spawn1..4`. The base handler's 8-character compare does not take them, so the shared
  spawn table stays empty. The flag stubs load as ordinary scenery. **Prediction:** `net_PickFreeSpawnPoint` (Gold
  0x451030) calls the error routine 0x42d5d0 ("SpawnLoc_GetLocation - no spawn points") and, if that returns, takes
  `rand() % 0`, an integer divide-by-zero, at the first spawn. Not booted.

**What would have to be rewritten** (a proxy-side port: hooks in our exe, no new file format):
1. ODEF label rules in the OBJ handler: strip `#`; `spawn<N>` into per-team spawn tables (or the shared table when
   team play is off); `check<N>` into a gate table (Nitro 0x444ad0, 0x4b3660). Cheapest alternative for CTF alone:
   **rewrite the labels in the files** (`#spawn1` -> `spawn`, `regen` kept) with the data track's mod kit. That gives
   playable team melee on the CTF maps with no code.
2. The race tick: gate passed within 30 m, lap count and time (Nitro 0x444bb0, 0x444b70), objective text (0x444350),
   race standings (0x44bd60).
3. CTF: flag pick-up / carry / drop / return. This is entity +0x444 in Nitro, which our exe does not have; the proxy
   would keep its own carrier table. Also collision classes 0x5a / 0x5b (Nitro `physics_RebuildCollision` 0x421900,
   `physics_CollideBodyPair` 0x41fcc0), capture scoring (0x444f80 / 0x4451d0) and the 'FL' sync packet. Our proxy
   already carries its own packets ('AT', 'AK', 'AM'), so it would follow that pattern.
4. Mode selection: a host option, or the file extension, in place of nitshell's setup bit (0x448800 / 0x448810).
5. Optional:
   - the two specials (Dashboard Mary x1.1 damage, Tire Covers x2 wheel hp at spawn): two cases in `physics_InitEntity`'s
     special switch;
   - the shell names for specials 10 / 11;
   - the Nitro dropper cadence, only if Nitro balance is wanted. **For the retail gold standard, leave it out.**
6. Not needed: the renderer, FSM, terrain, car and weapon formats, or ZFS.

**Arena boot status.** Five Instant Melee boots (stock M01 control x2, N51, N21, N11) all stayed in the shell (no
mission name, no player, main thread in the shell loop). The control failed the same way, so this is a harness
limit, not a Nitro result. `I76_REPLAY_CLICKS` is compiled into the release-candidate proxy but logged no `replay:`
line; replay-run.ps1 uses the side-built `builds\replay\Strlkup.dll`. Next step: re-run with that DLL (or through the
AI-melee host route), with the stock M01 control first.

### 7b. Does Nitro change physics or handling relative to retail 1.0?

**No, in code and in car data.**
- **Code:** the same clock (GetTickCount float seconds, dt clamp 0.001-0.2), the same stepper (floor(dt x 20) + 1, so
  below 50 ms the car step is the frame time), the same vehicle step and every float constant in the handling chain.
  Examples, unchanged: engine shift 850 / 1050 / 3.538 / 1.67397 / 2.23694; lateral cap 7.84 x wheels; the attitude
  solver's 0.008 / 1e-4 / 0.95 / 0.005; suspension `5 x (delta - previous delta)`.
- **Inherited from Gold**, both inactive for a car in the air:
  - the landing-wreck guard;
  - the +-0.3 steer pull with both front wheels damaged;
  - the collision-arm guard.
- **Fixed in Nitro:** the terrain-sample bounds bug (negative coordinates), which matters only off the map edge.
- **Data:** engines, brakes, suspension, chassis and wheels are Gold's bytes. Against retail that is the bus (12,730 vs
  9,000 kg) and the LOD distances; no engine, brake, suspension or tyre number differs.

**What does differ, and is felt in combat, not handling:**
- difficulty x2.0 at the GOG default;
- Gold's health %, turret and heat-seeker changes;
- Nitro's dropper cadence (2.4);
- two new specials and 7 weapons;
- frame rate: Nitro's renderers, like Gold's, run faster than retail's software path, so the step length (= frame
  time) differs on the same machine. That is the TWO-CLOCKS mechanism, not a code change.

## 8. Open questions and not reached

1. The arena boots (7a): harness, not format. Re-run with the replay DLL.
2. The two P01 boots without a player (2 of 6). Re-run P01 n >= 6 with the sampler armed from the start.
3. The whole `nitshell.dll`: setup block, mode bits and arena list. Read from strings only.
4. Savegame (`savegame.dir` / `.cmp`) format in Nitro: not compared.
5. The ~40 Nitro-only rasteriser span functions (0x473b30-0x4834c0): not identified beyond "software rasteriser".
6. `startup_FindCdDrive` in GOG's nitro.exe has its scan replaced by `jmp; nop` (0x4684d9). It reads like a no-CD
   patch, but whether it is Activision's or GOG's was not established; the PE stamp is 1998-03-27.
7. The Arsenal-demo Nitro (`b73f852d`, 1998-02-04) and the Nitro patches I-IV were not compared.
8. The direct-IP path and the packet layouts of ANet 2: imports and tags only.
9. Live A/B of the dropper cadence: static only.

## Files

- **i76-map:**
  - `data\fmt\nitro_corpus.py`;
  - `data\notes\nitro.md`;
  - `data\out\nitro\{survey,missions,fsm-actions,zfs-namesets}.json`;
  - `sandbox-gog\nitro-full\` (full Nitro install extraction and `zfs_out`; git-ignored).
- **Lab:**
  - `tools\nitro\{stage-nitro.ps1, nitro-run.ps1, nitro_probe.py}`;
  - runs in `captures\nitro-20261020\` (git-ignored; `*.json` per boot, with `env.txt` and the proxy log);
  - lab copy `exp-nitro\` (from `Games\I76\release-candidate`, Nitro campaign staged, M01 restored to stock md5
    `abb41681` / `f00bad90`).
- **Matching:**
  - lab `emu\tools\memtrace\exediff\` (`run.sh` rebuilt today; `exe_diff_map.json` unchanged);
  - the direct Nitro <-> retail match (`match.py x/nitro.json x/retail.json` with composed data pairs) is reproducible
    from those features.
