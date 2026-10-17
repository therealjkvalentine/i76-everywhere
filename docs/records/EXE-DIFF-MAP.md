# EXE diff map: what differs in the code between every I'76 exe we have (2026-10-17)

Lane `cross-exe-code-diff`. Static only: no game was run and no VM was started. Every exe was only read.

**The owner's questions this answers:**
- What are the released versions, and what exactly differs in their code?
- Which of those differences change physics, AI or damage?
- What exactly does Arcade Phys. do, in each exe?
- Can code explain why Gold pitches harder on jumps than retail (80 vs 53 deg), or is it only the step length?

**Where the data is:**
- Machine-readable map: lab `emu\tools\memtrace\exe_diff_map.json`. It has one row per Gold function (2,217 rows).
  Each row gives the function's retail and Nitro counterparts, how each was matched, and what differs.
- Tools: lab `emu\tools\memtrace\exediff\` (lab commit `820f093`). `run.sh` rebuilds the map, and the rebuild
  is byte-identical.
- New retail addresses: lab `addrmap-retail.md`, last section.

## Answer

1. **The exes:**
   - **Three distinct original builds** survive on this PC:
     - retail 1.0 (March 1997);
     - the Gold CD exe (February 1998);
     - Nitro Pack (March 1998).
   - Every other I'76 exe here is the Gold build plus a few bytes. That covers GOG 2017, GOG 2019 AiO, ours, the lab
     sandbox, i76fix and pristine_fix.
   - **The 1997 patches (1.05, 1.08b D3D beta) were not on this PC when this map was built** (see the "Not done / open" note). Section 1 lists them. Nothing below
     describes them.
2. **The vehicle physics is the same code in retail 1.0 and Gold.**
   - **The call tree:** from `physics_StepVehicle` the tree is 118 Gold / 87 retail functions to depth 2. Both use
     the same 75 float constants.
   - **The constants that differ** are the angle, sound and AI constants reached through that tree, plus constants
     the compiler folded differently (section 3).
   - **The timing code is the same:** the clock, the substep rule and the dt clamps.
   - **Read line by line** and the same:
     - suspension, wheel creation and engine shift curves;
     - ground height, body-pair collision and the attitude solver's constants;
     - CheckImpact and the lateral cap.
   - **Gold-only physics changes:** only the two already known (RETAIL-HANDLING-DIFF section 6). Neither acts on a
     car in the air.
3. **Jump pitch (Gold 80 deg vs retail 53 deg): no code difference found that could cause it.**
   - The airborne and landing paths are the same: integration, suspension, attitude solver, CheckImpact and
     collision damage.
   - The code says pitch depends on the step length and on the state at take-off (speed, rates, suspension
     compression), not on the exe.
   - So, from the code, the candidates are the step length (33.4 vs 30.2 ms median) and the take-off state.
   - This is a static null: no code path differs. It is not proof that dt alone explains the 27 deg. The A/B that
     decides it is in section 10.
4. **Combat code changed a lot between 1997 and 1998.** In order of how much it matters for balance:
   - **Difficulty damage multiplier (Gold only).**
     - Gold multiplies the player's weapon and flamer damage by **2.0 / 1.0 / 0.75** for difficulty byte 0 / 1 / 2.
     - Retail 1.0 has no difficulty option at all; its factor is always 1.0.
     - A fresh Gold or GOG install sits at **difficulty 0, so the player deals double damage**.
   - **Health % (`object_HealthFraction`).**
     - Retail 1.0 has a properly scaled formula.
     - **Gold broke it:** every core-damage case returns the raw 0..1 ratio. This is the "stock bug" that
       `I76_FIX_HEALTH_PCT` fixes.
     - Retail also counts the 4 wheels as core parts; Gold counts only engine, suspension and brakes.
     - Readers of this value: AI fleeing, damage smoke, script `hpLesser`, target brackets and handgun targeting.
   - **Turret slew.**
     - Retail: 1.5 rad/s (aircraft 6.0) x the weapon's hp ratio.
     - Gold: 1.7 rad/s (aircraft 6.8) x (0.75 + 0.25 x hp ratio).
     - So Gold turrets turn 13 % faster, and damage barely slows them.
   - **Heat-seeker cone.** |cos| > 0.84 (about 33 deg) in retail, 0.94 (about 20 deg) in Gold. Gold also added a
     target guard.
   - **AI behaviour state.**
     - Gold: a behaviour stack at ai+0xa874 indexed by ai+0xa93c.
     - Retail: a single slot at ai+0xa874.
     - Source: the AI/damage lane, lab `c3d1b44`; not re-derived here.
   - **The same in both:** `ai_RecordDamageEvent`, the AI path search, obstacle checks, back-away, team lists and the
     AI's arcade-aware steering model.
5. **Arcade Phys. (flag 0x10000) has the same five code sites, with the same arithmetic, in retail, Gold, Nitro and
   ours.** Two set it, three read it. Section 4.
6. **Three things our port does differently from both 1997 and 1998.**
   - **Shared with every GOG 2019 AiO install:**
     - `ai_RecordDamageEvent` reads projectile field +0x10 where retail, Gold and Nitro all read +0x44.
     - `entity_Register` stops at 256 entities where both originals overflow.
   - **Ours only:** `I76_FIX_HEALTH_PCT=1` computes min(28 + 72 r, 100 x core). That matches neither Gold's bug nor
     retail's formula (section 5).
7. **Nitro is Gold's engine five weeks later.**
   - 1,781 of 1,997 matched functions are the same instruction stream once three things are allowed for:
     relinking, stack slots, and an entity struct that grew by 4 bytes at +0x444.
   - The gameplay changes are the new entity field, collision types 0x5a / 0x5b, objective sounds, weapon-firing
     constants, and its own DEF and ZFS names (section 8).
   - The vehicle physics differs only by the moved entity fields and by x87 instruction scheduling.

## 1. The exes

| id | md5 | size | built (PE time) | what it is |
|---|---|---|---|---|
| **retail 1.0** | `6cc509ad` | 1,019,392 | 1997-03-16 06:30 | March 1997 CD (`I76_CD1.ISO`). Built with VC4.2, static C runtime, `.reloc` present. Software renderer only (320x240 / 480x360 / 640x480). Imports no `Strlkup`, no `ole32`, no MSVCRT. Carries Immersion `iforce.dll` force-feedback hooks. **The gold standard.** |
| **Gold CD** | `e1dca993` | 1,050,624 | 1998-02-19 22:21 | *Interstate '76 Gold Edition*, built with VC5. Adds D3D, Glide, Rendition and PowerVR, the `i7_sfrce` force-feedback path, `Strlkup` localisation, the difficulty option, and a 96-byte DEF |
| GOG 2017 Galaxy | `9a232dcc` | 1,050,624 | same | The Gold CD exe with the import `WINMM.dll` renamed `WIN32.dll`: **2 bytes**, at file `.rdata` VA 0x4c1683, measured today. This is i76fix's target and the i76-map reference (`ghidra\i76_ref.exe`) |
| GOG 2019 = UCyborg AiO | `60abf7bc` | 1,051,648 | same | Galaxy + 45 `.text` clusters (2,459 B) + a 132-byte tail (FIX-INVENTORY-2026-10-17 section 2; i76-map `binaries\diff-9a232dcc-vs-60abf7bc.tsv`) |
| **ours** | `6319abf7` | 1,051,648 | same | AiO + `USER32.dll` -> `u32x.dll`. Daily driver, golden copy, lab `game-envrb` / `game-rh` / `game-replay` |
| lab sandbox | `85de44a7` | 1,051,648 | same | lab `game*\i76.exe` (AiO lineage + lab file patches) |
| pristine_fix | `58d9dec0` | 1,050,624 | same | Galaxy + i76fix patch 1: 5 bytes at 0x499b25 skip the privileged CPU-speed probe |
| i76fix 25 fps | `26490278` | 1,050,624 | same | Downloads portable `i76.25fps`. Galaxy + the probe skip + a limiter jump in WinMain (0x4039b9) + 113 bytes of limiter code at the `.text` tail (0x4bbe55..) + 11 bytes of `.data` |
| **Nitro Pack** | `28b8ae27` | 1,070,080 | 1998-03-27 22:14 | Stand-alone expansion (GOG 2.1.0.17 installer). Its `nitplyr.def` / `nitro.zfs` are its own |

- **Version resources do not help.** retail, Gold and Nitro all say FileVersion 1.0.0.1. The PE time stamps and the
  LZO build strings are what tell them apart (Gold: "Feb 12 1998"; Nitro: "Mar 16 1998"; retail has no LZO).
- **Released versions that are not on this PC.** Sources: WHAT-IS-STOCK rows 14, 15 and 24; documented, not
  measured.
  - **1.05** (CGW #156, July 1997): "more than a dozen fixes", multiplayer.
  - **1.08b**: a D3D / 3Dfx beta patch reported on the Activision board in July 1997.
  - Any "1.0x" software-only patch.
  - A full scan of `C:\Users\james` and `D:\` turned up none of them (88 I'76-named exes, 8 distinct md5s, plus
    `i76.25fps` and two lab backups). The patch line between March 1997 and Gold therefore cannot be diffed here.
  - **Gold is the endpoint of that line.** Whatever 1.05 / 1.08 fixed is either in Gold or was dropped.
- **The original team's post-1.0 work:**
  - **documented:** the 1.05 multiplayer fixes, and the 1.08 D3D / 3Dfx line that became Gold;
  - **measured here:** what differs between 1.0 and Gold.
  - Nothing found says which of the changes below came with 1.05 or 1.08 and which first shipped in Gold.

## 2. Method, and how far to trust it

- **Same-link exes** (Gold, GOG, AiO, ours, lab, i76fix): a byte diff mapped to i76-map's function table
  (`famdiff.py`). FIX-INVENTORY-2026-10-17 section 2 already classifies the AiO clusters. This lane added the retail
  column for the clusters that touch gameplay (section 9).
- **Gold vs Nitro (same compiler).**
  - Matching: Ghidra Version Tracking (1,705 pairs, i76-map `status\vt-nitro.json`) plus call-graph propagation,
    1,997 pairs in all.
  - Comparison: each pair's instruction stream, with these normalised:
    - image addresses, callee identities and local branch targets;
    - stack slots;
    - entity fields at +0x444 and above (shifted by 4).
  - Result: 1,781 pairs come out the same.
- **Gold vs retail (VC5 vs VC4.2).**
  - **Why bytes cannot be compared:** the instruction streams never match. Ghidra Version Tracking matched only 128
    functions (5.8 %).
  - **Features:** `feats.py` extracts features a compiler change does not move:
    - float constants, including floats written as integer immediates (VC4.2 compares floats as integers, e.g.
      `cmp eax, 0x3e99999a` for 0.3);
    - strings, imports, data tables matched by Version Tracking, struct displacements and callees.
  - **Matching:** `match.py` starts from 23 hand-checked anchors and the VT pairs, then adds:
    - unique-string and unique-data anchors;
    - call-graph propagation: unique callee and caller, ordered callee gaps, best pair with a margin.
  - **Coverage:** 1,334 of 2,217 Gold functions.
  - **How good is the matching?**
    - **Holdout:** run without the 23 anchors, it re-finds 21.
      - The one miss is `sound_SetCdTrack` 0x423320 (a 2-instruction leaf).
      - The one "wrong" pair is `physics_StepVehicle`, matched to 0x472890: the collision block retail compiled as
        a separate function.
    - **Link order:** 95 % of pairs sit next to another pair in the same order in both exes (1,262 of 1,326).
  - **What it cannot tell you:**
    - A matched pair with equal features is "no evidence of change", not proof.
    - An unmatched Gold function is not "Gold-only". Most of the 883 are small helpers that retail inlined, or
      functions reached only through jump tables, such as the projectile step functions.
  - **Physics, damage and AI:** every claim in sections 3-6 was read side by side in disassembly (lab
    `exediff\verdicts.json`, 23 reads).
- **Coverage by subsystem.**

  | subsystem | Gold fns | retail matched | of those, float constants differ (after sign / 0 / 1 / 2 normalisation) | Nitro matched | Nitro same (normalised) |
  |---|---|---|---|---|---|
  | physics | 94 | 75 | 15 | 94 | 76 |
  | ai | 211 | 168 | 9 | 205 | 198 |
  | entity | 160 | 132 | 8 | 156 | 145 |
  | object | 134 | 124 | 2 | 134 | 128 |
  | weapon | 102 | 80 | 9 | 101 | 87 |
  | fsm | 83 | 80 | 0 | 83 | 80 |
  | world | 40 | 29 | 0 | 40 | 33 |
  | simclock | 15 | 14 | 0 | 15 | 15 |
  | camera | 52 | 24 | 6 | 42 | 40 |
  | input | 49 | 27 | 4 | 48 | 45 |
  | renderer | 415 | 133 | 12 | 361 | 327 |
  | sound | 86 | 59 | 2 | 84 | 71 |
  | net | 130 | 99 | 0 | 116 | 67 |

  - **Physics:** most of the 15 "float differs" rows are compiler artefacts, read one by one:
    - constants folded at compile time (`physics_WheelCreate`: 0.141605 = 0.56642 x 0.25);
    - helpers inlined in one exe and called in the other (the engine shift curve, `math_PlaneHeightAtXZ`);
    - one function split in two (`physics_CollideBodyPair`).
  - **Renderer:** Gold's renderer rows are mostly new D3D, Glide and texture-cache code with no 1.0 counterpart.

## 3. Physics: retail 1.0 vs Gold

| function | Gold | retail 1.0 | verdict |
|---|---|---|---|
| `simclock_Update` | 0x49c920 | 0x450fa0 | **same**. GetTickCount x 0.001 is stored as a 32-bit float in both; the first 3 frames are not accumulated; dt is clamped to [0.001, 0.2] (retail with integer compares); sim_dt is capped at 1.0 |
| `simclock_StepperBegin` | 0x49cc20 | 0x451250 | **same**: count = floor(sim_dt x 20) + 1, at most 20 |
| `physics_StepVehicle` | 0x438fd0 | 0x472360 + 0x472890 | **same algorithm** (RETAIL-HANDLING-DIFF section 1) |
| lateral cap | 0x43ce10 | 0x4759b0 | same, apart from Gold's both-front-wheels-damaged random pull |
| `physics_CheckImpact` | 0x436ff0 | 0x46fe20 | same |
| attitude solver `physics_ResolveGroundContact` | 0x437230 | 0x470030 (+0x470ca0) | same constants (0.008, 1e-4, pi/2, pi, 0.95, 0.005, 1e-8, 0.5) and the same calls in the same order |
| `physics_WheelUpdateSuspension` | 0x46dc10 | 0x42ffb0 | **same, line by line**: bump table x surface, +0.1 when stopped, target = arg + 5 x (delta - previous delta), filter, clamp |
| `physics_WheelCreate` | 0x46d760 | 0x42faf0 | same; the 0.141605 is folded at compile time |
| `physics_UpdateEngine` shift curves | 0x46a320 (+0x46a0c0) | 0x42f640 | same: 850 / 1050 / 3.538 / 1.67397 / 2.23694; the 40..106 curve is inlined in retail (1/66) |
| `world_GetGroundHeightAndNormal` | 0x43e530 | 0x477290 | same (+-3 m window) |
| `physics_CollideBodyPair` | 0x434bb0 | 0x469f80 + 0x46b340 | same: walkable classes 0xb..0xd with normal y > 0.3 only play a landing sound; 45 m and 500 thresholds |
| damage tree from `physics_ApplyCollisionDamage` | 0x4a7c80 | 0x45d7c0 | the same constant set, apart from Gold's difficulty factor (section 5) and the angle helpers |
| damage tree from `entity_DamageAndKill` | 0x463a80 | 0x429eb0 | the same 27 constants; the only differences are the smoke offset 0.2 and HealthFraction's 13 |

- **Gold-only physics code (already known):**
  1. the random +-0.3 steer pull when both front wheels are damaged (0x43cf41);
  2. the collision-arm guard when the arm has no horizontal part (0x43909b / 0x4390ca).
- **Why neither explains the jump.** A car in the air has no wheel contact and no body collision, so neither
  change can act in flight.

**Jump pitch, from the code.**
- **The airborne step** integrates the body's angular rates with the substep length; the attitude solver acts
  again at landing.
- **What sets pitch at the lip:** the four wheels' suspension forces in the last ground steps.
  - The suspension target uses a difference of difference (`5 x (delta - previous delta)`) per step.
  - The impulse the body takes therefore depends on how long each step is.
- **So a 33 ms step and a 30 ms step can take off with different pitch rates from the same approach.** That is the
  plausible code mechanism for a dt effect (not measured in isolation). No exe-specific branch is involved.
- **Two other differences between the measured Gold and retail jumps are not in this code:**
  1. the car and save in the slot;
  2. the take-off state. GOLD-STANDARD-FINGERPRINT suspects the car / save for the lab car's 34 % quicker
     acceleration.

**Frames and steps (the owner's open question), from the code.** The fuller table is FIX-INVENTORY-2026-10-17
section 0.
- **Once per rendered frame,** the game reads GetTickCount once.
  - It converts the reading to seconds in a **32-bit float**.
  - It subtracts the previous reading. That difference is the frame's `sim_dt`.
- **The physics then runs `floor(sim_dt x 20) + 1` substeps of `sim_dt / count` each.**
  - Below 50 ms that is one substep, so **the physics step is the last frame's duration**.
  - From 50 ms up the frame splits: 2 steps up to 99 ms, and so on.
- **The float storage is a hidden clock quantum, in retail and Gold alike.** It grows with Windows uptime:

  | Windows uptime | spacing of the stored time (float32 ulp) |
  |---|---|
  | under 2.3 h | under 1 ms (whole-ms dt exact) |
  | 2.3-4.6 h | 0.98 ms |
  | 4.6-9.1 h | 2 ms |
  | 9.1-18.2 h | 3.9 ms |
  | 18.2-36.4 h | 7.8 ms |
  | 36-73 h | 15.6 ms |
  | 3.0-6.1 days | 31 ms |
  | 6.1-12 days | 62.5 ms |

  - A freshly booted emulator is in the 1 ms regime.
  - A real 1997 PC up for a day would have read frame times in 7.8 ms quanta (arithmetic, not measured).
  - AiO removes this (FIX-INVENTORY).
- **The AI, the per-frame weapon effects and the input ramps run once per frame, not per step.** So frame rate
  changes them even where the physics step is the same.

## 4. Arcade Phys. (entity flag 0x10000): every code path, in every exe

The flag is entity +0x454 bit 16 (Nitro: +0x458). Every function body in each exe was scanned for the 0x10000 /
0xfffeffff immediates and the byte-wide `[+0x456], 1` form (`arcscan.py`). Five functions use it, in every exe:

| # | role | Gold (= GOG, ours) | retail 1.0 | Nitro |
|---|---|---|---|---|
| 1 | **set at vehicle init** (see below) | `physics_InitEntity` 0x438a90: option test 0x438f06 `test byte [0x654b98],1`, set 0x438f1c | 0x471df0: option test 0x472293 `test byte [0x5e14e4],1`, set 0x4722a9 | 0x4246c0: set 0x424cca |
| 2 | **set / clear from the in-game checkbox** (player only) | `physics_SetPlayerArcadeMode` 0x43d1a0 (0x43d1ce / 0x43d1dc), called by `shell_OptionArcadePhysics` 0x495b70 | 0x475c70 (0x475c97 / 0x475ca3), called by 0x44c390 | 0x428f60 |
| 3 | **steering lateral cap** | 0x43ceb4 `test dword [esi+0x454],0x10000` in 0x43ce10 | 0x475a30 `test byte [esi+0x456],1` in 0x4759b0 | 0x428c74 |
| 4 | **inverted at rest: flip or destroy** | 0x4370d3 `test ecx,0x10000` in `physics_CheckImpact` 0x436ff0 | 0x46fef0 in 0x46fe20 | 0x429615 |
| 5 | **the AI's own turn-rate model** | 0x40ffd2 in `ai_SteerToHeading` 0x40fe80 | 0x40a275 in 0x40a130 | 0x405dd2 |

**What each site does** (identical arithmetic in all exes):

1. **Init (site 1).** Every car gets flags |= 0x1001. It also gets 0x10000 when either:
   - it is the mission's script entity named `taurus` (`world_GetTaurusObject`); this applies whatever the options
     say; or
   - option bit 0 is set **and** the car is the player.
2. **Checkbox (site 2).** Flips option bit 0 and sets or clears the bit on the player's car at once. The Taurus car
   is left as it is.
3. **Lateral cap (site 3).** The yaw target is `steer x C / v`.
   - With the bit, C = A, the grip limit: 9.8 n_y^3 x vehicle grip x surface mu x (wheels in contact) / 4. That is
     about 23.4 for the melee car on the crater floor.
   - Without the bit, C = 7.84 x (wheels in contact) = 31.36, a fixed 3.2 g.
   - With the bit, `|steer x A| <= A`, so the slide flag (lat > 2A) and the slip fraction (lat > A) are never set.
     **An arcade car never slides from steering.**
4. **At rest (site 4).** The test runs when the car is inverted and at rest (|pitch|, |roll| rate < pi/5,
   |up.n| > 0.8, up.n < 0, grounded, not dead).
   - **With the bit and offline:** the up and right rows are negated (a 180 deg roll, so the car lands on its
     wheels) and sound event 4 plays.
   - **Otherwise:** `object_Destroy`, and the rates are zeroed.
5. **AI turn-rate model (site 5).** The AI predicts its own maximum turn rate with the same rule:
   - A x 0.25 with the bit;
   - 7.84 x wheels in contact without it.

   In stock missions only the Taurus car can have the bit, so this is the Taurus car's steering model.

- **Nothing else reads the bit:**
  - not the engine, braking, suspension or gravity;
  - not damage or weapons;
  - not the AI's other decisions;
  - not the network code (site 4 tests "offline" itself).
- **Arcade measured:**
  - retail's steady yaw was 0.94-1.00 rad/s with arcade on (by accident) and 1.28-1.30 rad/s with it off.
    That gap is site 3.
  - the two "turned over but not destroyed" retail T05 runs are site 4.
- **Arcade cannot be split into its parts without patching.** The steering cap and the flip share the one bit.
  RETAIL-HANDLING-DIFF section 6 gives the two test sites' file offsets in our exe.

## 5. Damage: retail 1.0 vs Gold vs ours

### Difficulty multiplier (Gold only)

- **Gold** (`weapon_BuildImpactDamage` 0x4a76a0, 0x4a76e7):
  - when the shooter is the player and the game is offline, the factor depends on the difficulty byte 0x654b9c
    (DEF +0x5c):

    | difficulty byte | factor |
    |---|---|
    | 0 | 2.0 |
    | 1 | 1.0 |
    | 2 | 0.75 |
    | anything else | 1.0 |

  - ordnance type 0x12 always gets 1.0;
  - the flamer has the same table (`weapon_UpdateFlamerStreams`, 0x4443a8).
- **Retail 1.0** (`0x45ced0`, `0x46d3d0`):
  - no factor;
  - no difficulty byte: its DEF is 88 bytes and ends at the option dword +0x54.
- **Defaults:** Gold's defaults zero the DEF block (0x4970f0), and the GOG and driver DEFs hold byte 0
  (FIX-INVENTORY item 9). So **Gold as installed deals 2x player damage. Retail is equivalent to Gold difficulty 1.**
- **What it does not touch:**
  - AI-fired damage and collision damage between cars;
  - terrain damage;
  - AI accuracy and aggression (no reader of 0x654b9c in the AI).

  The only readers of 0x654b9c are the two damage sites and the option page.

### Health % (`object_HealthFraction`: retail 0x40aae0, Gold 0x40b450)

| | retail 1.0 | Gold / GOG / ours (stock) |
|---|---|---|
| core parts | engine +0x3c4, suspension +0x3c8, brakes +0x3cc **and the 4 wheels** +0x3a8 / +0x3ac / +0x3b8 / +0x3bc | engine, suspension, brakes |
| all core parts >= 0.9999 and none dead | 28 + 72 x worst side ratio (armour / chassis) | same |
| some core part < 0.9999, d dead (< 0.02) | d = 0: **15 + 13 m**; d = 1: **5 + 8 m**; d = 2: **5 m**; d >= 3: **0.1 m** (m = smallest live core ratio) | **m, unscaled (0..1)**: the switch on d has all four cases pointing at the clamp (table 0x40b7b8 = 4 x 0x40b6f0) |

- **The scaling was lost in 1998.** Retail's formula is continuous with the healthy branch: a scratched core part
  reads 15-28 %, one dead part reads 5-13 %. Gold's reads 0-1 %. The fact that every Gold case jumps to the same
  address suggests the case bodies were removed in the 1998 build.
- **Consequences, by reader** (damage.md lists the readers):
  - **Damage smoke** (starts below 75, heaviest below 40): heaviest in both exes once a core part is scratched.
    Retail also smokes heaviest when **a wheel** is scratched; Gold does not.
  - **AI flee** (`ai_ShouldFleeWhenHurt`; target within 80 m and value < 30 + 17 x aggression): triggers in both on
    a scratched core part, because both values are below 30. Retail adds wheel damage as a trigger.
  - **Script `hpLesser(E, pct)`:**
    - pct >= 29: true in both;
    - pct between 1 and 28: Gold is always true, while retail depends on how damaged the part is;
    - so missions that test low percentages behave differently.
  - **Target brackets / readout:** retail shows 15-28 %, Gold shows 0-1 %.
  - **Handgun targeting** (< 33): the same in both.
- **Our `I76_FIX_HEALTH_PCT`:**
  - `=1` returns min(28 + 72 r, 100 x worst core ratio);
  - `=2` returns 100 x m.

  **Neither is retail's formula.** If the target is "as 1997 played", the faithful fix is retail's banded formula
  over 7 core parts (section 10).

### `ai_RecordDamageEvent` (retail 0x40fc80, Gold 0x4157a0, Nitro 0x418950)

- **All three originals gate the AI's "who shot / rammed me" stamps on projectile field +0x44 == 0.** Retail does
  it as `cmp [eax+0x44],1; sbb; neg`; Gold and Nitro read `[eax+0x44]`.
- **AiO and ours read +0x10 instead** (1 byte at 0x415817; checked again today in ours).
- **So this is a community change that 1997 and 1998 both lack.**
  - What +0x10 holds is not identified.
  - The AI/damage lane's I76AIM logger already uses this byte to tell builds apart (lab `c3d1b44`).

### Unchanged in damage

- `entity_DamageAndKill`, `entity_ApplyDamage`, terrain damage above 7.65 m/s, the landing damage call and
  collision damage all have the same constants.
- The invulnerability flag (retail 0x4dc464, Gold 0x5da7a8) is tested the same way.

## 6. AI and weapons: retail 1.0 vs Gold

| item | retail 1.0 | Gold | effect |
|---|---|---|---|
| **turret slew** (`weapon_UpdateTurretsAndLocks` retail 0x455560, Gold 0x4a3760) | dt x 1.5 rad/s (aircraft 6.0) x weapon hp ratio | dt x 1.7 rad/s (aircraft 6.8) x (0.75 + 0.25 x hp ratio) | Gold emplacements and car turrets track 13 % faster; a half-dead retail turret turns at 50 %, a Gold one at 88 %. Gold also adds the 2-degree "aligned" flags and a lock tone at 1.6 (0x4a4045) |
| **heat-seeker cone** (retail 0x46add0, called by 0x46ae70 / 0x460480; Gold inline in 0x4361e0 and 0x436120) | \|cos\| > 0.84 (about 33 deg) | \|cos\| > 0.94 (about 20 deg) + class-1 targets need entity flag bit 0 | Gold heat missiles acquire and track in a narrower cone; range 650 m in both |
| **AI behaviour** | single behaviour slot ai+0xa874 | a stack ai+0xa874[ai+0xa93c] | from lab `c3d1b44` (AI/damage lane). What the stack changes in behaviour was not traced here. Measured there: retail AI stalled about 90 m short of a parked player in melee, n 1 |
| **AI compile** | inlined helpers | the AI helpers around 0x41cd90 are built without optimisation (`push ebp / mov ebp, esp`) | no behaviour change in the cases read (`ai_IsSlidingBackward`, back-away) |
| path search, static obstacles, team lists, back-away, record damage event, the arcade-aware turn-rate model | - | - | same constants and structure |

- **`weapon_SpawnProjectile` (retail 0x458f40, Gold 0x49fb40) was rewritten.**
  - The random particle and casing angles differ: retail -20 r - 195 deg and 180 r - 90 deg; Gold uses a 0.6
    spread, 0.75 r - 0.375, and so on.
  - Gold has a different ordnance switch.
  - The ballistic effect was not determined (not read in full).
- **Gold has ordnance step functions that matched nothing in retail** (bullet, rocket, radar missile, mortar,
  cluster bomb, mine, oil, fire patch).
  - Gold reaches them through a jump table, which the call-graph matcher cannot follow.
  - So "unmatched" here does not mean "new in Gold". Their retail counterparts were not located.

## 7. Renderer, detail, input, sound, shell, CD

- **View distance clamp:**
  - retail clamps the camera far distance to [100, 1000] at init (0x43c8a0) and caps the viewport at 1500
    (0x43cb40);
  - Gold raises both caps to 100,000 (0x472220, 0x472530).

  So **no retail setting draws past 1-1.5 km**. Our 1,200-1,800 m far clips depend on Gold's cap.
- **Renderers:**
  - Gold adds D3D, Glide, Rendition and PowerVR, D3D video logging and texture caches. 282 of Gold's 415 renderer
    functions matched nothing in retail; by their names most are this new code, but unmatched does not prove absent.
  - Retail draws in software only.
- **Detail presets:** the first 14 bytes of the preset tables match (retail 0x4daf38, Gold 0x4fe200). Gold appends
  2 bytes (RETAIL-HANDLING-DIFF section 3).
- **Force feedback:** retail has Immersion `iforce.dll` hooks; Gold has its own `ffb_*` path (9 functions,
  `i7_sfrce.dll`).
- **Localisation:** Gold imports `Strlkup.dll` (our proxy's host); retail has none.
- **DEF layout:** retail 88 bytes; Gold 96 (+ difficulty at +0x5c, and 2 more detail bytes).
- **CD checks:** both look for disc 2.
  - Retail's mission load asks for disc 2 (WHAT-IS-STOCK).
  - AiO's `startup_IsMinimum` returns 0 (FIX-INVENTORY).

## 8. Nitro Pack vs Gold

- **1,781 of 1,997 matched functions are the same instruction stream after normalisation.** The other 216 split
  into these groups.
- **Compiler re-scheduling.** x87 operand order and register choice changed in most of the physics, weapon and AI
  "changed" functions: `fld a; fadd b` became `fld b; fadd a`.
  - The float constants and fields are the same, so these are not code changes.
  - The vehicle physics (`StepVehicle`, lateral cap, `CheckImpact`, the integrators, the suspension) is in this
    group, together with the entity field moves.
- **The entity struct grew.**
  - Nitro has a new field at entity +0x444. `entity_RemoveVehicle`, `entity_UpdateState` and `entity_Wreck` test it.
  - Gold's +0x444.. moved by +4 to +0xc. The flags move from +0x454 to +0x458, so Arcade is +0x458.
- **New collision types 0x5a / 0x5b** in `physics_RebuildCollision` and `physics_CollideBodyPair`.
- **Gameplay:**
  - weapon-firing constants (`weapon_UpdateInstanceFiring`: Gold 0.05 / 20 / -1, Nitro 0.18 / -1.2);
  - `entity_DamageComponent` adds a test of record bit 0x10 next to Gold's bit-0 test;
  - `entity_DamageAndKill` calls a new check before the +0x482 test;
  - `fsm_Success` / `fsm_RevealObjective` set objective bits where Gold plays `cnote.wav`;
  - Nitro's own multiplayer car file `nitmcar.def` and save `nitplyr.def`.
- **The same in Nitro and Gold:** `ai_RecordDamageEvent` (+0x44) and the five Arcade sites.

## 9. Community builds vs the Gold code, with the retail column

FIX-INVENTORY-2026-10-17 section 2 classifies the AiO clusters. This lane added what retail 1.0 does at the clusters
that touch gameplay:

| AiO cluster | AiO / ours | Gold (GOG 2017) | retail 1.0 |
|---|---|---|---|
| `ai_RecordDamageEvent` 0x415817 | gate on +0x10 | +0x44 | **+0x44** (= Gold) |
| `simclock` 0x49c7f0-0x49cbd6 | masked tick (no uptime quantisation) | float seconds (quantises with uptime) | **float seconds** (= Gold) |
| terrain sample / normal / height (0x49318f..) | unsigned bounds | signed | not read |
| `entity_Register` 0x4572d5-0x457416 | **returns at 256** (bounds fix; FIX-INVENTORY had this as "not characterised") | warns, then writes past the table | **warns, then writes past** (= Gold) |
| `renderer_DrawRearMirror` 0x4457b4 | mirror every frame | 10 Hz gate | not read |

## 10. What this means for the port and for the gold-standard comparisons

These are proposals. Nothing was changed.

1. **Difficulty.**
   - Any Gold-vs-retail combat comparison must run Gold at **difficulty byte 1** (the 1.0 x factor). At byte 0 it
     doubles the player's damage.
   - The AI/damage lane's validation run had Gold at difficulty 0 ("Wimp"; lab `c3d1b44`).
   - For the port: if the gold standard is retail 1.0, the default DEF should carry difficulty 1. That is a config
     change, not a patch.
2. **Health %.**
   - The retail-faithful fix is the banded formula over 7 core parts (section 5), not `min(28 + 72 r, 100 x core)`.
   - It can go in the existing `I76_FIX_HEALTH_PCT` hook as a new value (for example `=3`), so that `=1` stays
     available for A/B.
3. **`ai_RecordDamageEvent`.**
   - Our exe differs from both originals.
   - A 1-byte revert (0x415817: `0x10` -> `0x44`) restores 1997 and 1998 behaviour.
   - What AiO intended with +0x10 is unknown (not looked up in UCyborg's notes). Only an A/B decides whether to
     keep it.
4. **Turrets and heat-seekers are Gold balance.**
   - Retail turrets are slower, and slow down a lot when damaged.
   - Retail heat-seekers lock in a wider cone.
   - A port "based on 1.0" would have to patch these five constants back: 1.7 -> 1.5, 6.8 -> 6.0, the hp factor,
     and 0.94 -> 0.84.
5. **Jump pitch A/B that would settle section 3.** Use the existing T05 placed-jump scripts with the step forced
   equal on both exes: lab `I76_STEP_SEQ` on the lab side, or the same emulated machine with the frame rate pinned.
   - If the pitch peaks converge, the cause is dt.
   - If they do not, compare the take-off state in the traces.
6. **"Based on 1.0 instead of GOG": what the code says.**
   - Retail 1.0 cannot run the port's renderer path (no D3D or Glide, far clip capped at 1.5 km).
   - It has the static VC4.2 runtime and a different address map, so every proxy hook would need porting.
   - Its gameplay differences from Gold are a short, known list: difficulty, health %, turret slew, heat cone, AI
     behaviour stack, view cap.
   - **The cheaper route** to "1.0 behaviour" is the Gold-based exe with these few rules patched back.
   - This is the code's side only. The decision belongs in the synthesis lane.

## Not done / open

- **Patches 1.05 / 1.08 / 1.08b:** no exe on this PC, so not diffed.
  [verify 2026-10-17: I76-VERSIONS has since fetched the 1.05 (linked 1997-03-28, not summer), 1.06, 1.081 and 1.083
  exes and the demo into lab `emu/images/versions/extracted/`; they are still not in this map. Only 1.08b is missing.]
- **Instruction-level alignment:** the lateral function and the suspension were aligned instruction by instruction;
  the integrator `physics_IntegrateVehicleMotion` and the longitudinal tyre code were not. They match only on
  constants and call order, which was the same.
- **The AI behaviour-stack difference** is taken from lab `c3d1b44`, not re-derived. The 43 Gold AI functions with
  no retail match were not each located. Most are 8-60 instruction state handlers (`ai_Enter*` / `ai_Update*`)
  that retail likely inlined.
- **Turret k in retail** (hp ratio, raw) rests on one stack slot traced once. Medium confidence.
- **Weapons:** `weapon_SpawnProjectile` and the retail ordnance step functions were not read in full.
- **Nitro:** `weapon_UpdateInstanceFiring`'s new constants and the new entity +0x444 field were not interpreted.
- **Unread rows:** 72 matched retail pairs differ in float constants. The ones in physics, damage, AI and weapons
  were read (above); camera / input head-look (removed or moved angle constants), radar (retail 600) and aircraft
  rows were not.

## Files

- lab `emu\tools\memtrace\exe_diff_map.json`: per-function map, coverage, the verified rows and the Arcade sites.
- lab `emu\tools\memtrace\exediff\`:
  - `run.sh` rebuilds the map;
  - `xd.py` disassembles with floats resolved;
  - `cmpc.sh` and `who.py` give side-by-side constants and call neighbourhoods;
  - `arcscan.py` is the 0x10000 scan;
  - `tree.py` compares call-tree constants;
  - `verdicts.json` holds the 23 manual reads.
- lab `emu\tools\memtrace\addrmap-retail.md`: the new retail addresses.
