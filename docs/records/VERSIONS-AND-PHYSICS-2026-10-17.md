# Versions and physics: what we know after the 2026-10-17 run

Synthesis of the versions-and-physics workflow, written 2026-10-17. It adds no new measurements: it is built from the
records below and the verifier's checks. The run was finished lean after the owner cut costs. Where a number is quoted,
n is given; "n 5 vs 12" means 5 traces/boots in the first cell against 12 in the second.

Source records (all in `docs/records/`):
- [I76-VERSIONS.md](I76-VERSIONS.md): every release, and what each patch changed.
- [EXE-DIFF-MAP.md](EXE-DIFF-MAP.md): code differences between the exes.
- [FIX-INVENTORY-2026-10-17.md](FIX-INVENTORY-2026-10-17.md): every change our port makes to stock.
- [HARDWARE-MATRIX.md](HARDWARE-MATRIX.md): retail 1.0 on the emulated P133.
- [ARCADE-PHYSICS.md](ARCADE-PHYSICS.md), [STEP-LENGTH-CURVE.md](STEP-LENGTH-CURVE.md),
  [AI-DAMAGE-BALANCE.md](AI-DAMAGE-BALANCE.md): closed out (owner cut), data as gathered.
- [AI-DAMAGE-METRICS.md](AI-DAMAGE-METRICS.md), [TRAINER-LOGGER.md](TRAINER-LOGGER.md): the measuring tools.
- [BASE-DECISION-1.0-vs-GOG.md](BASE-DECISION-1.0-vs-GOG.md): which exe the port builds on.
- Context: [DEV-GAME-CLUB-I76.md](DEV-GAME-CLUB-I76.md) (the 15 fps statement),
  [PHYSICS-STEP-STUDY-DESIGN.md](PHYSICS-STEP-STUDY-DESIGN.md) (the 33.3 ms amendment),
  WHOLE-SIM-TICK-2026-10-17.md (the tick, being built by a separate agent; not yet committed).

## Headline answers

1. **Releases.** After the March 1997 disc the original team shipped patches 1.05, 1.06, 1.08b, 1.081 and 1.083,
   then Gold 1.2 (February 1998). We hold 1.05, 1.06, 1.081, 1.083 and the demo byte for byte. Only 1.08b is missing.
   GOG sells the Gold exe with a 2-byte import rename. There is no Steam release.
2. **No original-team release changed driving physics.** Every 1997 patch has the same physics constants and struct
   offsets as 1.0. The one physics-side change is a 1.05 guard that stops the vehicle step once a landing has wrecked
   the car. Gold's vehicle physics, clock and substep rule are the same code as 1.0's.
3. **What did change is combat and rendering, mostly in Gold.** Gold added a difficulty damage multiplier, broke the
   health-% formula, sped up turrets, narrowed the heat-seeker cone, added an AI behaviour stack, retuned some data,
   and added hardware renderers with a far clip up to 100 km (retail caps it at 1-1.5 km).
4. **Hardware: the emulated P133 is now the reference (owner, this run).** At lowest detail it takes one physics
   step per frame: 32.0 ms in melee (n 5) and 31.9 ms on T05 (n 10). That is within about 1.5 ms of the 33.3 ms
   baseline. At the developers' own P133 default (640x480) it runs about 11 fps with 2 substeps of 41.5 ms (n 3 melee,
   n 5 T05). That setting accelerates faster and jumps higher.
5. **Frames and steps.** Below 50 ms a frame is one physics step, and the step is the frame time. From 50 ms a frame
   splits into 2 or more equal substeps. The developers designed for 15 fps, which the engine runs as 2 x 33.3 ms. That
   is the owner's baseline step.
6. **Arcade Phys.** One entity bit, read at five code sites, identical in every exe. It cuts steering yaw by 19-30 %
   (never lets steering slide) and flips an upside-down car upright instead of destroying it. Nothing else changes.
   The gold standard is simulation physics (arcade off).
7. **AI and damage.** Our Gold-lineage exe at a 30 ms step matches retail 1.0 on the P166 in T13 combat (n 8 vs 10,
   all p >= 0.07). The daily driver's preset makes the AI much less aggressive. Further AI/damage runs wait for the
   whole-sim tick.
8. **Base decision (recommendation, owner to rule).** Keep the GOG Gold exe as the code base and play it with
   retail 1.0's rules on the whole-sim tick at 33.3 ms. No 1.0 rebuild.

## 1. Released versions, and what the original team fixed after 1.0

| version | exe link date | what it changed | physics? |
|---|---|---|---|
| Demo | 1997-03-24 | 2 missions (T03, T14) | same as 1.0 |
| **1.0 retail** | 1997-03-16 | the game; software renderer only; **the gold standard's exe** (`6cc509ad`) | reference |
| 1.05 | 1997-03-28 | about a dozen multiplayer fixes (host double kills, turret locks kept after jamming, "partial death" camera, IPX rejoin), the Mission 12 salvage-save crash, 320x200 cockpit missile labels, a missing explosion texture | one guard: the vehicle step stops once a landing bounce has wrecked the car |
| 1.06 | 1997-04-11 | host can boot players (CTRL-S, CTRL-#), chat toggle; vehicle files re-shipped (mass, drag, geometry identical) | none |
| 1.08b | ~July 1997 | first Direct3D beta | **not held** |
| 1.081 | 1997-08-02 | Direct3D built in (bilinear, MIP mapping); drops I-Force force feedback; adds the `STRLKUP.DLL` string lookup | none |
| 1.083 | 1997-10-03 | adds SideWinder force feedback (`i7_SFRCE.DLL`); its shell DLL is the one GOG ships as `I76SHELL_1083.DLL` | none |
| **Gold 1.2** | 1998-02-19 | new compiler (VC5); D3D, Glide, Rendition, PowerVR renderers; 16-bit art; difficulty levels; hack prevention; data retunes (for example bus mass 9,000 -> 12,730, Gas blast 500 -> 100, armour and loadouts on some cars) | same algorithm; two Gold-only details, neither acts in the air |
| Nitro Pack | 1998-03-27 | Gold's engine five weeks later; 20 missions, new cars and weapons | entity fields moved by 4 bytes only |
| GOG | Gold exe | `WINMM.dll` import renamed `WIN32.dll` (2 bytes); does **not** contain the 2019 AiO patch | none |

Sources: I76-VERSIONS s.1-3. The link dates were checked by the verifier from the PE headers.

The fix list for 1.05 is Activision's own text. The guard's link to the "partial death" fix is an inference. The
guard does not explain Gold's higher T05 wreck rate, because it acts only after a car is already wrecked.

## 2. Code differences between the exes

Three distinct original builds survive (retail 1.0, Gold, Nitro). Every other exe on this PC is the Gold build plus a
few bytes: GOG 2017, the GOG 2019 AiO build, ours, the lab sandbox and i76fix (EXE-DIFF-MAP s.1). The machine-readable
map has one row per Gold function (2,217 rows; verifier confirmed).

| area | retail 1.0 vs Gold | ours vs Gold |
|---|---|---|
| **Physics** | Same code: `physics_StepVehicle`, clock, substep rule, dt clamps, suspension, attitude solver, CheckImpact, collision. Same 75 float constants in the call tree. Gold adds a both-front-wheels-damaged steer pull and a collision-arm guard | No physics code patched. Everything we change, we change through time (clock, step length) |
| **Jump pitch** (Gold 80 deg vs retail 53 deg, n 7 each) | No code difference found that could cause it. Candidates: step length (33.4 vs 30.2 ms median) and take-off state. A static null, not a proof | - |
| **Damage** | Gold multiplies player weapon damage by 2.0 / 1.0 / 0.75 for difficulty 0 / 1 / 2; retail has no difficulty and no factor. Gold broke the health-% formula; retail scales it properly and counts the wheels as core parts | `I76_FIX_HEALTH_PCT=1` matches neither. Fresh Gold / GOG / our driver sit at difficulty 0, so the player deals double damage |
| **AI** | Gold has a behaviour stack where retail has one slot. Path search, obstacle checks, back-away and the damage recorder are the same | `ai_RecordDamageEvent` reads projectile +0x10 (its target) where retail and Gold read +0x44 (its damage). Retail sides with Gold (AI-DAMAGE-METRICS s.0 item 5) |
| **Weapons** | Turret slew retail 1.5 rad/s (aircraft 6.0) x hp ratio, Gold 1.7 (6.8) x (0.75 + 0.25 x hp ratio): Gold turns 13 % faster and barely slows when damaged. Heat-seeker cone retail \|cos\| > 0.84 (about 33 deg), Gold 0.94 (about 20 deg). `weapon_SpawnProjectile` rewritten (retail counterpart not located) | - |
| **Arcade** | Same five code sites, same arithmetic (section 5) | same |
| **Renderer** | Retail: software only, far distance clamped to [100, 1000] m with a 1500 viewport cap. Gold: plugin renderers and caps raised to 100,000. Detail preset tables match in their first 14 bytes; Gold's DEF is 96 bytes (retail 88), with difficulty at +0x5c | Our 1,200-1,800 m far clips depend on Gold's raised cap |

The verifier extracted the turret constants from both exes and confirmed them, and confirmed retail imports no
`Strlkup.dll` and no Glide or D3D.

## 3. Behaviour across emulated hardware and detail levels

**Owner ruling (this run): the P166 is not needed in the hardware matrix; the P133 is the reference.** No new P166
runs were made. The P166 cells already measured stay in HARDWARE-MATRIX.md as existing data. The tables there still
use them as the comparison baseline, because that is the data that exists.

All runs: retail 1.0, simulation physics (arcade share 0 in every trace), settings file written and read back
identical every run (verifier confirmed).

**Which P133 setting is the developers' default.** The retail code picks a detail preset from its CPU probe and RAM:
at least 133 MHz with at least 30 MB of RAM gets preset 2 (640x480, features on). The emulated P133 has 33,067,008
bytes, so preset 2 is its developer default. The verifier disassembled this and matched the preset bytes. On the
emulator the probe misreads the CPU (466 / 524 MHz), so preset 2 was written into the settings file.

| | **P133 lowest detail** | **P133 developer default (preset 2)** | existing P166 lowest (for comparison) |
|---|---|---|---|
| fps, melee / T05 | 29.9 / 30.2 | 11.6 / 10.5 | 36.3 / 31.5 |
| substeps per frame | 1 on 95-99 % of frames (16 runs) | 2 on 64-98 %, the rest 3 or more (9 runs) | 1 on ~97-100 % |
| physics step p50, melee | 32.0 +- 0.7 ms (n 5) | 41.5 +- 1.5 ms (n 3) | 26.8 +- 0.9 (n 12) |
| physics step p50, T05 | 31.9 +- 3.0 ms (n 10) | 41.5 +- 1.4 ms (n 5) | 31.1 +- 1.0 (n 16) |
| 0-10 m/s | 1.04 +- 0.01 s (n 5) | **0.93 +- 0.03 s (n 3)** | 1.06 (n 12) |
| 0-20 m/s | 2.72 +- 0.03 s (n 5) | **2.62 +- 0.01 s (n 3)** | 2.76 (n 12) |
| steady yaw 12 m/s | 1.70 +- 0.05 rad/s (n 6) | 1.29 +- 0.14 (n 2, one boot: lead only) | 1.66 (n 17) |
| T05 placed jump apex | 10.9 +- 0.4 m (n 10) | **11.8 +- 0.8 m (n 5)** | 10.7 (n 7) |
| T05 placed jump destroyed | **6/10** | 2/5 | 0/7 |

What this says:
- **P133 lowest detail is a single-step machine at about 32 ms**, close to the 33.3 ms baseline. Handling,
  acceleration and jump take-off, apex and distance match the existing P166 reference within tolerance. Exception:
  yaw at 12 m/s reads 2.4 % higher (one boot).
- **The developer default is the mixed-rate reference**: about 11 fps, physics stepped twice per frame at about
  41.5 ms. It accelerates faster and jumps higher than lowest detail. The existing P166 default cell shows the same
  signature (`r166p3`, existing data: 2-3 substeps, apex 12.0 m). Braking, body motion, take-off speed and wreck rate show no difference.
- **The jump wreck rate is the one open difference.** P133 lowest 6/10 vs P166 reference 0/7 (Fisher p 0.035),
  6/10 vs 3/15 with both P166 cells pooled (p 0.087). The 4 steepest take-offs (pitch rate 0.85-0.91 rad/s) were all
  destroyed and all in the early batch (4/5 destroyed early vs 2/5 late). Across 57 jumps in all cells, a take-off
  pitch rate of 0.49 rad/s or more separates destroyed from survived with 3 misclassified. About 10 more boots per arm
  in one batch would confirm or drop it.
- **Body-motion reversal counts drop on longer frames, but that is partly the instrument.** Reversals are counted
  per rendered frame (Spearman -0.83 with step, 19 cells, verifier recomputed). The mean and p95 body rates are unchanged.
- **A real P133 would probably be slower than the emulated one** (inference, untested). The emulated P166 renders about
  20 % fast. If the P133 does the same, a real P133 at preset 2 runs about 100 ms frames, right where 2 substeps
  become 3 (2 x 50 ms or 3 x 33 ms).

Gold and Glide cells measured before the cut are existing data only: Gold runs 11-16 % slower than retail at the same
detail (Gold P166 lowest 31.3 ms melee, n 8).

## 4. How frames relate to physics steps

**The rule.** Once per rendered frame the engine reads how long the last frame took (`sim_dt`, whole milliseconds).
It then cuts that time into `count = floor(sim_dt x 20) + 1` equal physics substeps, at most 20. So:
- a frame shorter than 50 ms is **one step**, and the step **is** the frame time (a 32 ms frame = one 32 ms step);
- a 50-100 ms frame is **two steps** of half the frame (an 83 ms frame = 2 x 41.5 ms);
- a 100-150 ms frame is three steps, and so on.

Every retail trace in the hardware matrix follows this rule on every frame (verifier). The physics step stays below
50 ms however slow the machine is. A slow machine takes more, shorter substeps per frame.

**Only the vehicle physics substeps.** Input, AI, weapons, collision sweeps and the rest of the simulation run once
per rendered frame, whatever the substep count (WHOLE-SIM-TICK s.1 lists the call sites).

**The developers' 15 fps target.** The renderer programmer recalled: "The game was designed to run at 15 frames per
second. Anything faster was considered a bonus," and "Everything ran in the same loop" (DEV-GAME-CLUB-I76; a
28-year recollection relayed twice). A 15 fps frame is 66.7 ms. Under the rule that is **2 x 33.3 ms physics
substeps**, with everything else once per 66.7 ms frame. The engine never runs a 66.7 ms physics step.

**The 33.3 ms baseline.** The owner set the baseline step at 33.3 ms (PHYSICS-STEP-STUDY-DESIGN amendment
2026-10-17): the 15 fps design as the engine runs it. It also sits at the retail T05 / T06 median frame times
(31-35 ms) and is the first cell of the step study.

**Mixed rate vs single rate.**
- **Single rate**: one physics step per frame, so the whole simulation runs once per step. This is the P133 and P166
  at lowest detail (about 32 ms), and what the whole-sim tick reproduces at a fixed length.
- **Mixed rate**: several physics substeps per frame, with the rest of the simulation (AI, input, weapons) once per
  frame. This is the 15 fps design (2 x 33.3 ms) and the measured P133 developer default (2 x 41.5 ms at about
  11 fps). The P133 data say mixed rate is not the same as single rate at a similar step: the default accelerates faster
  and jumps higher than lowest detail.
- **Our current driver**: a fixed 41.67 ms physics step under 120 fps rendering, with the rest of the sim per rendered
  frame and about 50 patch sites holding parts of it to a 20 Hz grid (FIX-INVENTORY s.0, s.4). The whole-sim tick
  replaces this: the whole simulation runs on one fixed tick and only drawing follows the display.

## 5. Arcade vs simulation

Arcade Phys. is entity flag 0x10000. It is set at vehicle init from the options (player only, plus the mission car
named `taurus`, always) or by the checkbox. It is read at three sites (EXE-DIFF-MAP s.4; identical in retail, Gold,
Nitro and ours).

Measured on retail 1.0, P166 lowest detail (ARCADE-PHYSICS summary; n samples / boots):

| behaviour | simulation | arcade | change |
|---|---|---|---|
| steady yaw, 18 m/s flat | 1.30 rad/s (22 / 3) | 0.91 (16 / 6) | -30 % |
| steady yaw, 12 m/s | 1.66 (17 / 3) | 1.34 (13 / 3) | -19 % |
| steady yaw, 25 m/s | 1.03 (17 / 3) | 0.92 (16 / 3) | -10 %, not resolved (p 0.31) |
| steering slip state | 3-22 % of steer frames | 0 % | never set |
| upside down at rest, offline | destroyed (5/5; Gold 5/5) | flipped upright (9/9; Gold 5/5) | the defining difference |
| acceleration, braking, body jounce, jump take-off pitch, frame time | - | - | no change |

Gold arcade matches retail arcade on every measured metric. The Gold-vs-retail jump-pitch gap is the same with arcade
on (81 vs 61 deg) as off, so arcade does not explain it. The lab switch `I76_RETAIL_HANDLING=1` is really "arcade
on"; renaming it `I76_FORCE_ARCADE` is proposed. Not measured: site 5 (the AI's own turn model), the multiplayer
branch, CTRL+A, the Taurus claim (static plus a null live check), arcade under the tick.

## 6. AI and damage: what exists, what is deferred

**Tools that exist.** I76AIM (a read-only logger in the emulated guest or on the host) with `ai_damage.py`. It reads
AI position, target, behaviour, rounds per weapon, damage dealt and taken per source, deaths and time-to-die from
memory in retail, Gold and our exe, with no hook. Cost: 0.35-0.86 % of guest time (n 3 blocks per exe). Use it in
combat runs, not physics-reference runs (AI-DAMAGE-METRICS).

**Measured (T13, player parked or holding fire; AI-DAMAGE-BALANCE, pooled):**

| cell | n | damage taken /min | time-to-die after first damage | vs retail P166 |
|---|---|---|---|---|
| retail 1.0 P166 lowest | 10 | 2314 +- 540 | 36.3 +- 11 s | reference |
| retail 1.0 P133 lowest | 8 | 2577 | 38.2 s | no difference (p 0.48 / 0.76); engagement distance shorter (86 vs 131 m, p 0.014) |
| Gold CD at Champ (x1.0), P166 | 6 | 3194 +- 496 | 33.2 s | +38 % damage (p 0.007), same time-to-die (p 0.56) |
| our exe, stock stepper, 30 ms | 8 | 2181 | 42.9 s | no difference, all p >= 0.07 |
| our exe, daily driver preset (best-wide) | 6 | 1433 +- 658 | 38.9 s | -38 % damage (p 0.012), -58 % AI rounds (p 0.004) |

- Time-to-die varies by about 31 % between identical boots. Detecting a 25 % difference needs about 14-25 boots per
  arm, depending on the metric.
- AI fire is rolled once per rendered frame. On our exe, 8 ms frames fire 2.3x the rounds of 30 ms frames (pooled
  n 7-8, p < 0.001), but damage taken does not rise (p 0.76): the extra rounds miss.
- About 70 tests are reported in the pooled tables, so a single p near 0.04 is weak evidence.
- The +38 % for Gold is not explained by step length. That it comes from Gold's data retune is an inference.

**Deferred until the whole-sim tick exists** (owner cut): the host 40 ms cells e40 / f40, the 60 vs 120 fps render
independence pair, the player-aim driver for time-to-kill, and a Gold run with retail loadouts to split exe from
data. Today's exe rolls AI fire per rendered frame, so those cells would describe the scheme the tick replaces.

## 7. Retail 1.0 or GOG as the base

Recommendation from BASE-DECISION-1.0-vs-GOG.md, **for the owner to rule on** (owner test 53):
- **Code base: the GOG Gold exe.** The proxy, the tick, the renderers and the tools stay where they are.
- **Reference: retail 1.0 with simulation physics.**
- **A switchable "retail rules" set on Gold**, each chosen by A/B against the retail reference:
  - difficulty byte 1 (x1.0);
  - the retail health-% formula as a new `I76_FIX_HEALTH_PCT` value;
  - the 1-byte `ai_RecordDamageEvent` revert at 0x415817;
  - turret slew 1.7 -> 1.5 and 6.8 -> 6.0 with retail's hp factor;
  - heat-seeker cone 0.94 -> 0.84;
  - arcade off;
  - optional data retunes in `I76.ZFS`.
- **Timing: the whole-sim tick at 33.3 ms.**
- **No 1.0 rebuild.**

Why:
- The physics is the same code.
- Our Gold-lineage exe at 30 ms already matches retail on T13 (n 8 vs 10).
- What differs is a short known list.
- Retail has no `Strlkup.dll` import (no injection point for our proxy), draws software only, and caps the far clip at
  1-1.5 km.
- Users can only buy Gold: the official patch goes 1.0 -> 1.2 only.

Revisit only if a measured, felt difference survives an A/A after the tick and the retail rules are on, and traces to
Gold code outside the list.

## 8. The trainer logger

I76 Debug now records the physics and memory log on our modern port, in I76MEM's columns and file layout, so the
emulator analysis tools read it unchanged (TRAINER-LOGGER).
- One click on the lab twin: `game-dd-20261003\Interstate 76\TEST-logged-play.bat`. It refuses daily-driver and
  Downloads folders.
- Scroll Lock marks a moment, Shift + Scroll Lock stops / starts the log. It starts and stops a log per mission on its
  own.
- It writes `step_ms` from the stepper itself, so fixed-step logs read back the real step. `fingerprint.py` was fixed
  for fixed-step logs (lab 9d3ba95). That fix broke step percentiles on stock-stepper lab captures; the fix is
  proposed, not applied.
- Cost: 87-90 us per frame, 0 frames missed up to about 1470 fps, at most about 2 % of one CPU in the dashboard. On
  the game side, 2 of 3 capped boots are inside the A/A spread. One (log-c2) is an unexplained outlier, under 4 VMs of
  host load. Needs n >= 5 per condition on a quiet host.
- Not yet run by the owner on the twin's proxy (owner test 54).

## 9. Cut by the owner, and why

The owner cut cost on 2026-10-17. Each cut is recorded in its own record.

| cut | why | record |
|---|---|---|
| P166 cells in the hardware matrix | the P133 is the reference; existing P166 data kept | HARDWARE-MATRIX |
| Gold, Voodoo / Glide and high-detail hardware cells | cost; not needed for the reference | HARDWARE-MATRIX |
| the modern frame-rate sweep of the per-frame patch scheme (rounds 2-3, campaign C, 40 ms cells) | the whole-sim tick replaces that scheme; its numbers would not choose a tick step. Round 1 (stock stepper, n 1 boot per cell) is kept as measured | STEP-LENGTH-CURVE |
| new arcade runs | cost; the defining effects are measured | ARCADE-PHYSICS |
| AI / damage runs | deferred until the tick exists; today's exe rolls AI fire per frame | AI-DAMAGE-BALANCE |
| a 1.0 rebuild | same physics code, users cannot buy 1.0, the proxy cannot attach to it | BASE-DECISION |

## 10. Retracted and superseded claims

Retracted by the verifier (corrected in the source records, commit 3a1c6e8):
- HARDWARE-MATRIX: "5 of 10 take-offs at |q| 0.85-0.91, 4 of those 5 destroyed". **Correct: 4 of 10, all 4
  destroyed.**
- EXE-DIFF-MAP: "the summer 1997 patches (1.05, 1.08b) are not on this PC". **Wrong**: 1.05 is linked
  1997-03-28, not summer, and I76-VERSIONS has since fetched 1.05, 1.06, 1.081, 1.083 and the demo. Only 1.08b is
  missing. The 1997 patches are still not in the diff map.
- Close-outs lane summary: "Taurus static only". It is static plus a null live check (wording only).

Superseded by later data (not errors when written):
- FIX-INVENTORY s.0 projected an emulated P133 at about 37 ms T05 steps (real 41-45 ms). Measured: 31.9 ms on T05
  (n 10), single step.
- STEP-LENGTH-CURVE s.4 quotes P133 lowest jumps 4/5 turned over (n 5) and the P166 rerun 2/3 (n 3). The finished
  HARDWARE-MATRIX counts are 6/10 and 3/8.
- FIX-INVENTORY RE-CHECK (a), "whether retail matches AiO or Galaxy at `ai_RecordDamageEvent`": answered. Retail
  reads +0x44 as Gold does; AiO / ours read +0x10 (AI-DAMAGE-METRICS).

Not checkable by the verifier: the 1.0 rebuild cost of 539 proxy code addresses / 337 in-function sites
(BASE-DECISION s.4.1). It is consistent with that record's own table.

## 11. Open questions

1. **P133 jump wreck rate** (6/10 vs 0/7, p 0.035; pooled p 0.087). Real, or batch drift? About 10 more boots per
   arm in one batch.
2. **Which P133 cell is "the" reference**: lowest detail (single rate, 32 ms) or the developer default (mixed rate,
   2 x 41.5 ms)? An owner decision (owner test 55).
3. **Mixed vs single rate.** Does the developer default's faster acceleration and higher jump come from the substeps
   or from the longer step? This matters for whether the tick should ever run 2 substeps per tick.
4. **Gold vs retail jump pitch (80 vs 53 deg).** Step length or take-off state? The A/B is a pinned-step T05 pair
   (EXE-DIFF-MAP s.10 item 5).
5. **Our exe turns over without being destroyed** where retail and Gold are destroyed (STEP-LENGTH-CURVE s.3). Find
   why before comparing outcome rates across exes.
6. **Gold's +38 % damage: exe or data?** Needs a Gold run with retail loadouts, after the tick.
7. **AI behaviour stack and `weapon_SpawnProjectile`**: what Gold's versions change was not traced.
8. **Widescreen and the AI far model.** `I76_ASPECT` may move the near / far physics boundary for AI cars from about
   874 to 1,256 m (arithmetic only; FIX-INVENTORY item 6).
9. **The 1997 patches in the diff map**, the missing 1.08b, Gold 1.2 = GOG byte-verified against an applied RTPatch,
   and retail / Gold save interchange: all untested.
10. **Logger cost outlier** (log-c2), and the `fingerprint.py` stock-capture regression.
11. **Whole-sim tick results**: pending from the separate agent.

## 12. Community write-up: outline only

The community draft waits for the step decision. Outline:
1. What we set out to find: what 1997 Interstate '76 actually played like.
2. The versions: 1.0 through Gold, and what the original team changed (physics never; combat and renderers in Gold).
3. How the engine turns frames into physics steps; the developers' 15 fps target as 2 x 33.3 ms.
4. Measuring the 1997 game on emulated P133 hardware: single rate at lowest detail, mixed rate at the developer default.
5. Arcade Phys. explained.
6. Gold vs 1.0 combat balance: difficulty, health %, turrets, heat-seekers, data.
7. What the modern port does with this: Gold exe, retail rules, whole-sim tick at the chosen step.
8. What is still open, and how others could help (1.08b, real P133 / P166 timings).
