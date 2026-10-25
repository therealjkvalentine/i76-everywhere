# Retail 1.0 vs Gold handling: why the yaw differs (2026-10-16, static + existing traces)

EMU-MEMTRACE section 4 measured a gap at a held 18 m/s with full keyboard steer. Steady yaw was 0.94-1.00 rad/s in
retail and 1.34-1.59 rad/s in Gold (n = 8 retail / 7 Gold), and Gold also slid more. This file explains that gap.

- **Lane:** static only. No game run, no VM.
- **Exes:**
  - retail 1.0 `I76.EXE`, md5 `6cc509ad` (lab `emu\work\retail`, the disc copy);
  - Gold CD exe, md5 `e1dca993`;
  - ours, the golden `i76.exe` (md5 `6319abf7`; read only).
- **Data:** the traces used are the existing ones in lab `emu\results\memtrace\`.

## Answer

- **It is not a code difference. Every retail run had "Arcade Phys." switched on; every Gold run had it off.**
  - **How it happened:** the retail launch in `gen_scripts.py` copies the Gold folder's `I76PLYR.DEF` into the retail
    folder.
  - **Why that switches it on:** that file is in the Gold layout (96 bytes). Retail reads 88 bytes with its own,
    shorter layout. Retail's option-flag dword therefore lands on Gold bytes `01 00 8e 00`, and bit 0 of that dword
    is "Arcade Phys.".
  - **Measured:** the arcade entity flag 0x10000 is set in 100 % of retail steer frames (2,129 of 2,129, 6 runs;
    verify: was "7 runs", the six runs sum to 2,129) and in 0 % of Gold steer frames (0 of 1,203, 5 runs).
  - **In the T05 traces:** it is set in every retail frame (8 runs, including tonight's `t05clean-smoke`) and in no
    Gold frame.
- **What arcade does to steering.** Both exes run the same code for this. The lateral function caps the yaw target
  at:
  - `steer x C / v`;
  - with **C = A**, the vehicle and surface grip limit, when arcade is on;
  - with **C = 7.84 x (wheels in contact) = 31.36**, a fixed 3.2 g, when arcade is off. This is the stock default.

  With arcade on, the car also never passes the grip limit, so the slide branch never runs.
- **Prediction against the traces.**
  - The fitted gain `K = |yaw| v / |steer|` (frames not sliding, steer >= 0.3, v >= 8) is:
    - retail **23.1-23.4** (median per run, 5 of 6 runs; the first run is 21.2);
    - Gold **31.5-31.7** (5 runs).
  - The ratio is **1.35**.
  - The window-mean form of this prediction reproduces `yaw_ss` (see section 4):
    - retail: 0.990 predicted vs 0.967 measured (n = 16 phases);
    - Gold: 1.413 predicted vs 1.427 measured (n = 14 phases).
  - What remains of the 1.48x gap is speed. Gold slides, so it is slower in the 1-2 s window (16.4 vs 16.9 m/s).
- **What arcade does in CheckImpact.** An inverted car at rest is flipped upright instead of being destroyed by
  `object_Destroy`. This happened in 2 of the 3 retail T05 turn-overs (runs 183450 and 183650): up.y went from -0.98
  to +0.98 (183450, frame 13252) and -0.95 to +0.95 (183650, frame 13359) in one frame. That is why "no car was destroyed".
- **`physics_StepVehicle` is the same algorithm in retail and Gold.** The three differences listed in EMU-MEMTRACE /
  addrmap-retail were artefacts of the float-constant scan. Retail has the guard, the clamp and the > 7.65 terrain
  damage too, but writes them as integer compares (`cmp dword [x], 0x38d1b717 / 0x3f800000 / 0x3e800000 /
  0x40f4cccd`). The scan only looked at FPU memory operands, so it never saw them.
- **Patch for our exe: none.** Ours has Gold's physics, which is retail's physics with arcade off (the stock default:
  both exes zero the flag dword in their defaults). Matching retail-as-measured would mean turning "Arcade Phys." on,
  not patching. A few real but small Gold-only code changes exist (section 6). None of them affects the measured yaw.

## 1. How the two vehicle steps line up

| block | Gold / ours | retail 1.0 | same? |
|---|---|---|---|
| object-collision response | inlined in 0x438fd0 (0x438fe2-0x439b4d) | separate function 0x472890, called first | same arithmetic. See the notes below the table |
| `CheckImpact` | 0x436ff0 | 0x46fe20 | same gates and constants (EMU-MEMTRACE) |
| wreck: +0xe4 = -1 if flags & 0x8020 | 0x439b5f.. | 0x47238b.. | same |
| front-wheel steer angle = steer x -pi/4 | 0x466e30 + 0x458980 per front wheel | 0x475cb0 (0x42d390 + 0x42e450) | same |
| ground / tyre solver | 0x43a5d0 (1,548 ins, inlines more) | 0x473600 (901 ins) + 0x474400 / 0x474bf0 / 0x4759b0 / 0x475100 / 0x471860 / 0x4719f0 | lateral part checked line by line (section 2). The longitudinal and contact parts were matched by call structure and constant sets only |
| speed = \|a0\|, 1/speed (1e30 if <= 1e-4) | 0x439c6b.. | 0x472435.. | same (retail integer compare) |
| airborne: kill if fallen > 35 m; else landing bounce (sound 4) + `ApplyCollisionDamage` with velocity (0, -0.2, 0) | 0x439e57 / 0x439eaa / 0x439f22 | 0x4725a6 / 0x4725e4 / 0x47264e | same |
| wheel updates, surface, ground normal, +0x46c = n_y^3 x 9.8 | 0x439f56..0x43a0c9 | 0x472674..0x4727c0 | same |
| attitude solver | 0x437230 | 0x470030 | not re-diffed (EMU-MEMTRACE: same role) |
| skid flag 0x2 from the solver | 0x43a117.. | 0x47280c (0x475c10) | same |
| **terrain damage when speed > 7.65** | 0x43a168 -> 0x4641e0(surface factor x dt) | **0x472814** `cmp [esp+0x10], 0x40f4cccd` -> 0x42a5d0 | **same**. Both damage functions are identical in shape: accumulator +0x458, 6-way random component |
| engine / sound | 0x46a320 | 0x42f640 | same arguments |

**Collision block constants.**
- Gold: lateral factor `1 - 0.75 (v.n / speed)^2`, guarded by `speed > 1e-4` and clamped to [0.25, 1] (0x4390d0-0x43914f).
- Retail: the same factor. The guard is `cmp [ebp+0xac], 0x38d1b717` at 0x47297e. The clamp is `cmp 0x3f800000` /
  `cmp 0x3e800000` at 0x4729dc-0x4729f2.
- Shared: the pi/2, pi and pi/4 angular clamps are in both exes (Gold 0x439707-0x4398f7, retail 0x47301a-0x473232).

## 2. The lateral function (Gold 0x43ce10 = retail 0x4759b0)

Gold and retail compute the same thing. The steps:

1. `A = g_eff x grip x mu x S / 4`, where:
   - `g_eff` = entity +0x46c = 9.8 n_y^3;
   - `grip` = vehicle definition +0x14;
   - `mu` = the surface friction (0x492770 / 0x475d00), set to 0 if `mu > 0.2` and flag 0x400;
   - `S` = the sum of the four wheels' +0xc.
2. `C = A` if entity flag **0x10000**, else `C = 7.84 S`.
   - Gold: `test dword [esi+0x454], 0x10000` at 0x43ceb4 (ours file offset 0x3c2b4).
   - Retail: `test byte [esi+0x456], 1` at 0x475a30.
3. Front-wheel damage pull: steer +0.3 (left wheel), -0.3 (right wheel), then clamped to [-1, 1].
4. `r = steer x C / v` if `v^2 x k > C`, else `steer x v x k`.
   - `k` = entity +0x110 = 1 / (2 x entity +0x118), set at 0x438c72 / 0x47200d.
   - The trace fit says the cap branch is the one taken at these speeds.
5. With `lat = |r v|`:
   - `lat > 2A` sets the slide flag;
   - `lat > A` gives the slip fraction `(2A - lat) / A`.
6. With arcade on, `lat <= |steer| A <= A`, so neither the slide flag nor the slip fraction is ever set from here.
   With arcade off, `lat = 31.4 |steer|` passes A once |steer| > A / 31.4 (about 0.75 for the melee car).
7. Flag 0x2000 tracks that threshold in Gold. It is set in 164 frames, the lowest at |ay| 22.0. It is clear up to
   |ay| 23.4 (n = 438). Retail never shows it (n = 1,477).

   This also measures the grip limit inside Gold: **A_gold is about 22-23.4**, the same as retail's arcade cap
   (23.1-23.4). The melee car and the crater surface therefore give the same A in both exes' data.

**The arcade flag is set in two places:**
- **Vehicle init:**
  - Gold 0x438f06 / 0x438f1c (ours file offset 0x3831c), retail 0x472293 / 0x4722a9;
  - the flag is set on the object at [0x51f5c4] (retail [0x505454]), and on the player when option bit 0 is set.
- **The "Arcade Phys." checkbox:**
  - Gold handler 0x495b70, in the control table at 0x4fc4e0 next to the localised label;
  - retail handler 0x44c390, in the table at 0x4d9b08, right after the string pointer 0x4d9b04 -> "Arcade Phys.";
  - each handler flips option bit 0 and calls 0x43d1a0 / 0x475c70, which set or clear 0x10000 on the player's entity.
- **Corroboration:** `re\subsystems\options.md` already lists 0x654b98 as "options_play_flags (1 arcade, ...)".

**How CheckImpact uses it:**
- Gold 0x4370d3: `test ecx, 0x10000`. Ours file offset 0x364d3.
- Retail 0x46fef0.
- **Arcade on, not networked:** the up and right rows are negated (the car is set upright), with sound event 4.
- **Arcade off:** `object_Destroy`.

## 3. Why the retail runs had arcade on: I76PLYR.DEF layouts

**The two readers.**
- Retail reads 0x58 bytes into 0x5e1490 (fread at 0x44d6fd; defaults at 0x44d660).
- Gold reads 0x60 bytes into 0x654b40 (0x49719e; defaults at 0x4970f0).

**The two layouts:**

| field | retail offset | Gold offset |
|---|---|---|
| player block | +0x00..+0x3f | same |
| graphic detail | +0x40..+0x4d (14 B) | +0x40..+0x4f (16 B). The preset tables 0x4daf38 / 0x4fe200 match on the first 14 bytes; Gold appends 2 |
| 4 audio sliders + 2 bytes (defaults 3, 5 or 4, 10, 8, 1, 0) | +0x4e..+0x53 | +0x50..+0x55 |
| (Gold only) | - | +0x56..+0x57 |
| option flags dword (1 arcade, 2 no salvage, 4, 8, 0x10, 0x20) | +0x54 | +0x58 |
| (Gold only) | - | +0x5c..+0x5f |

**What retail actually got from the Gold low-detail file.** The par base's `<gold game folder>\I76PLYR.DEF` is the same file
as lab `emu\work\gamefiles`.

| what | value | effect |
|---|---|---|
| graphic detail | read correctly | the frame-rate comparison stands as far as the options go |
| audio bytes | `00 00 03 04 0a 08` instead of `03 04 0a 08 01 00` | music and the second slider at 0. Bytes +0x52 / +0x53 are only written, never read |
| flags | `0x008e0001` | arcade on. Retail only tests bits 0-5, so the other bits do nothing |

**Our own installs are not affected.**
- The daily driver and the golden copy have 0 at +0x58 (read only).
- The lab `game\` has 0x18 there (armour + chassis options), with arcade off.

## 4. Check against the traces

The script is lab `emu\tools\memtrace\arcade_check.py`. It uses the steer phases only, with |steer| >= 0.3,
v >= 8 m/s, and frames where the car is not sliding.

| run | exe | arcade frames | K median (p5-p95) |
|---|---|---|---|
| 164331 melee | retail | 243 / 243 | 21.15 (20.5-22.2) |
| 170333 / 171325 / 182048 / 182939 mel2 | retail | all | 23.43 / 23.31 / 23.41 / 23.40 |
| 185645 loop (4 reps) | retail | 985 / 985 | 23.12 (18.9-23.5) |
| 164856 melee | Gold | 0 / 193 | 31.50 (31.2-31.6) |
| 170848 / 171826 / 175616 mel2 | Gold | 0 | 31.67 / 31.67 / 31.67 |
| 191227 loop (4 reps) | Gold | 0 / 617 | 31.66 (30.8-31.9) |

**K is a property of the exe's setting, not of the run.** The spread within each exe is 1 % (Gold) and, apart from
the first retail run, 1.3 % (retail).

- **Gold:** 31.6 is 0.8 % above 7.84 x 4 = 31.36. This is probably the logger reading speed and rate a substep
  apart; it was not chased.
- **First retail run (21.2):** this is the first `r166-melee` run, before the `mel2` script. The car or spawn
  surface may differ; not checked.

**Window prediction, `yaw = K x mean(|steer| / v)` over the 1-2 s window that `yaw_ss` uses:**

| exe | phases | yaw_ss measured | predicted, own K | predicted with the other exe's K | mean v | slide share |
|---|---|---|---|---|---|---|
| retail | 16 | 0.967 | 0.990 | 1.337 (Gold K) | 16.89 | 0.13 |
| Gold | 14 | 1.427 | 1.413 | 1.046 (retail K) | 16.37 | 0.77 |

- **The K ratio explains 1.35 of the 1.48 gap.** The rest is Gold's lower window speed from sliding (1.046 / 0.990).
- **Prediction for the decisive run (not run here):**
  - retail with arcade off should give K of about 31.5 and `yaw_ss` of about 1.35-1.43 (Gold-like);
  - Gold with arcade on should give K of about 23.4 and `yaw_ss` of about 0.95-1.0.

## 5. Consequences for other records

- **EMU-MEMTRACE section 1** "Static physics difference" and lab `addrmap-retail.md`: the three claimed differences
  are wrong (see the answer above).
- **EMU-MEMTRACE section 4** "Gold turns about 45 % faster and slides": this is arcade (retail) vs realistic (Gold).
  It is not a 1997 vs 1998 change. The braking (86-88 vs 89-94 m) and body-motion differences come from runs with
  the same confound and should be re-measured too.
- **T05 canyon:**
  - every retail descent ran with arcade on, so "0 destroyed" is not evidence about the stock rollover kill;
  - ERA-ENVELOPE's canyon landing kill (CheckImpact, arcade off) is unaffected.
- **Tonight's retail runs** (`t05clean`, `t05v2`) carry the same confound until the retail launch copies a
  retail-layout file.
  - verify (2026-10-16): the emu lane already switched it at 22:42 (lab `0e2f16c`, `gen_scripts.py` writes
    `tools\memtrace\retail-plyr\RPLYR.DEF`, flags 0). Runs from `r166sim-*` on are arcade off; `r166-t05clean-smoke`
    and `r166-t05clean-a` (22:32 / 22:40) still copied the Gold file (arcade frames 4,135 / 4,135 and 18,776 / 18,776).
- **Section 7 item 4 (re-baseline the envelope on retail):** the handling part needs no change of target. Retail with
  stock options steers like ours.

## 6. Patch spec for our i76.exe

- **Handling, as measured: no patch.** Our `physics_StepVehicle`, the lateral function and CheckImpact are
  byte-identical to Gold. The checks below were run on ours vs Gold; every one was identical:

  | site | VA | file offset |
  |---|---|---|
  | lateral function | 0x43ce10 | 0x3c210 |
  | CheckImpact | 0x436ff0 | 0x363f0 |
  | init | 0x438ef3 | 0x382f3 |
  | checkbox handler | 0x495b70 | 0x94f70 |
  | flag setter | 0x43d1a0 | 0x3c5a0 |

  Gold's code with arcade off is retail's code with arcade off.
- **If the owner wants retail-as-measured handling:** tick Options > "Arcade Phys.". That one option brings both the
  lower lateral cap and the upright-flip instead of the rollover kill.
  - No byte patch should split those two effects. The only global switch is 0x10000 (`f7 86 54 04 00 00 00 00 01 00`
    at file offset 0x3c2b4, and `f7 c1 00 00 01 00` at file offset 0x364d3).
- **Real Gold-only code differences found** (all optional; not recommended without an owner A/B):
  1. **Both front wheels damaged.**
     - Gold adds a random +-0.3 steer pull (`call [rand]` at 0x43cf43); retail's pulls cancel to 0.
     - Retail-equivalent patch: VA 0x43cf41, file offset **0x3c341**, `74 20` -> `eb 20`. This always takes the
       per-wheel path, where left +0.3 and right -0.3 cancel.
     - Affects only a car with both front wheels damaged.
  2. **Collision arm with no horizontal part.**
     - Gold skips the object-collision response when the arm's x^2 and z^2 are both < 1e-8 (0x43909b / 0x4390ca,
       `0f 85 7d 0a 00 00` at file offset 0x384ca).
     - Gold also zeroes the arm's y (0x4390a4, `c7 44 24 5c 00 00 00 00` at file offset 0x384a4).
     - Retail has neither. Its moving-object branch uses only the arm's x and z (`1 / (x^2 + z^2)` at 0x472cca), so
       without the guard it would divide by about 0.
     - Gold's version looks like a 1998 crash or NaN fix. **Keep it.** Retail's static-object branch was not
       aligned instruction by instruction.
  3. **Terrain damage above 7.65 m/s is not a Gold change.** Retail does it too (0x472814 -> 0x42a5d0, the same
     function as Gold 0x4641e0). There is nothing to trade off.
- **Must not change:** the substep rule, CheckImpact's gates, the rollover kill with arcade off (the canyon stock
  behaviour), or the 0x10000 test sites.

## 7. Retail AI team lists (EMU-MEMTRACE section 7 item 6)

Found statically, not yet checked live.

| item | Gold | retail 1.0 |
|---|---|---|
| insert function | 0x409840.. (0x409878-0x4098b6) | **0x408510** (0x40853a-0x40858b) |
| team index | `(obj+0x10 >> 16) & 7` | `(obj+0x10 & 0x70000) >> 16`, written as and-then-shift, which is why the Gold pattern search missed it |
| team lists | 0x507da0, 8 x 64 record pointers (stride 0x100) | **0x4edc30**, same shape |
| team counts | 0x51f5d0, 8 dwords | **0x505460** |
| matching evidence | 39 instructions reference the pair | 39 instructions reference the pair |

Retail's insert also skips objects with +0x6c == 8. I76MEM's retail signature needs these two addresses before the
retail AI summary can be turned on.

## 8. Tools and files

- **`emu\tools\memtrace\arcade_check.py`:** per run, the share of frames with the arcade flag, K, and the 0x2000
  threshold.
- **`emu\tools\memtrace\plyr_to_retail.py GOLD.DEF OUT.DEF [--arcade 0|1]`:** converts a Gold-layout DEF to the
  retail layout and reads it back.
  - Already made (in `emu\work\retail-plyr\`, not in git): `I76PLYR.DEF` (arcade off) and `I76PLYR-arcade.DEF`.
  - Both are 88 bytes: graphics `07 00 00 01 01 01 00 00 01 00 00 00 03 00`, audio `03 04 0a 08 01 00`, flags 0 / 1.
- **Not changed:** `gen_scripts.py` / `parrun.py` (other lanes are using them tonight).
  - Suggested fix: put the converted file in the par base as `<gold game folder>\I76PLYR.R10`, and have the retail launch
    `COPY <gold game folder>\I76PLYR.R10 <retail>\I76PLYR.DEF`.

## Not done

- **No VM run.** The decisive A/A + A/B was not run here. It is retail with the arcade-off file twice, and Gold with
  arcade on twice, n >= 2 each, melee loop.
  - verify (2026-10-16): one retail arcade-off run already exists from the emu lane, `20261016-224135-r166sim-mloop-1`
    (RPLYR.DEF, flags 0): arcade flag in 0 of 819 steer frames, K median 31.59 (p5-p95 30.84-31.75, n = 398 frames),
    flag 0x2000 from |ay| 22.95. That matches the prediction above (K about 31.5), n = 1 run; no A/A yet, and no
    Gold-with-arcade-on run.
- **Vehicle data:** `grip` (vehicle +0x14) and `mu` were not read from either exe's data. A_gold is about A_retail
  from the 0x2000 threshold only.
- **Not aligned instruction by instruction:** the longitudinal tyre function (0x43c310 / 0x474bf0), the per-wheel
  contact functions (0x43c960 / 0x475570), the attitude solver, and retail's static-object collision branch. They
  were matched by call graph and constants.
- **The first retail melee run (K 21.2)** was not explained.
