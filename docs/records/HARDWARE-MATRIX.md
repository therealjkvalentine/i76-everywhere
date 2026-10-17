# HARDWARE-MATRIX - retail 1.0 sim on the emulated P133 (lowest detail and the developers' P133 default)

Lane hardware-matrix, 2026-10-17 (resumed and finished lean after the owner's cuts).
Data: lab `emu\results\hardware-matrix\` (`cells.json`, `matrix.md`, `report.md`, `*.compare.*`).
Tools: lab `emu\tools\memtrace\gen_hwmatrix.py`, `hwm_analyse.py`, `hwm_jumps.py`, `hwm_report.py`.

## Status and scope

- **Owner cut (2026-10-17):** P166 is no longer needed in the matrix. Only the P133 reference is needed.
  - Gold, Voodoo / Glide and high-detail cells are cut. New runs for those are cut.
- **This resume launched no VMs.** Both cells the brief asked for were already fully measured by the stopped instance of
  this lane (10:54-11:56 and 06:16-07:31). They are reported here from that data.
  - On the host at the time: 2 86Box processes, neither started by this lane. They were left alone.
- P166, Gold and Glide cells already measured are kept below as **existing data**. No new ones were added.
- All runs: retail 1.0 (`cd-retail\I76.EXE` 6cc509ad), SIMULATION physics.
  - Arcade share: 0 in every trace (`mode.arcade_share`, melee n 8 / 6, T05 n 10 / 5 for the two P133 cells).
  - The retail-layout I76PLYR.DEF was written and read back identical in every run (88 bytes).
  - The detail bytes were also read back from the live options block in memory and matched in every run (report.md, "Options read back").

## The two P133 cells

| cell | settings (14 detail bytes at DEF +0x40) | why this setting |
|---|---|---|
| `r133low` | `0700000101010000010000000300`: 320x200 software, lowest detail (the gold standard's set) | (a) software lowest |
| `r133p2` | `0501010101010101000101010301`: the exe's own preset 2, 640x480 software, features on | (b) developers' first-launch default for a P133 |

**How (b) was chosen.**
- The Gold manual's first-launch table puts P133 / P166 at 640x480 with all features on (P90 / P100 at 320x200 all on).
  - Source: DEV-INTENT-EVIDENCE.md, PHYSICS-STEP-STUDY-DESIGN.md E1.
- The retail code applies the same table from its CPU probe (retail 0x44e260):
  - MHz >= 166 gives preset 3.
  - MHz >= 133 gives preset 1, or preset 2 with >= 0x1e00000 bytes of RAM.
  - Lower speeds give preset 0, which is 320x200 with features on. That matches the manual's P90 row.
- The emulated P133 has 33,067,008 bytes, read back in every run. So a real P133 with this RAM gets **preset 2**.
- A true first launch on the emulator would not give the P133 row:
  - The game's probe reads 466 / 524 MHz on the emulated P133, so it would pick preset 3.
  - So preset 2 was forced through the DEF instead.
- Presets 1 to 3 are all 640x480. Preset 2 differs from "all on" in one byte (+0x8 off). The manual and the code agree
  on the resolution class.

## Results (retail 1.0 sim, emulated P133)

Values are mean +- sd (n traces).
- The P166 reference is `zref-r166low`: the gold-standard retail P166 lowest-detail traces (existing data).
- Melee rows come from one Instant Melee per boot, plus the early melee-loop boots for `r133low`.
- Yaw3 rows come from one boot per cell, with 3 reps at each speed.
- Jumps are one placed 56 m/s T05 jump per boot: 10 boots for r133low, 5 boots for r133p2.

### Frame time and substeps

| | P166 low (ref) | **P133 low** | **P133 developer default** |
|---|---|---|---|
| fps, melee (cell median) | 36.3 | 29.9 | 11.6 |
| fps, T05 | 31.5 | 30.2 | 10.5 |
| sim_dt p50 melee, ms | 26.8 +- 0.9 (12) | 32.0 +- 0.7 (5) | 83.7 +- 2.5 (3) |
| sim_dt p50 T05, ms | 31.1 +- 1.0 (16) | 32.2 +- 3.3 (10) | 90.4 +- 4.9 (5) |
| sim_dt p50 T05 on the ground, ms | 32 | 37 [37-38] (10) | 95 [90-98] (5) |
| physics step p50 melee, ms | 26.8 | 32.0 | **41.5 +- 1.5 (3)** |
| physics step p50 T05, ms | 31.1 | 31.9 +- 3.0 (10) | **41.5 +- 1.4 (5)** |
| frames with 1 / 2 / 3+ substeps, per run | ~97-100 / 0-3 / 0-1 % | 95-99 / 1-5 / 0-1 % (16 runs) | **0 / 64-98 / 2-36 %** (9 runs) |

- In the melee runs of the developer-default cell, 93-98 % of frames were 2 substeps (3 runs). On T05 it was 64-85 % (5 runs), with the rest 3 or more.
- Every frame follows the engine's substep rule: count = floor(sim_dt x 20) + 1, step = sim_dt / count.
  - So frames of 50-100 ms take 2 substeps and frames of 100-150 ms take 3.
- Per-frame sim_dt is spread widely in the default cell. One T05 run read p5 77 / p50 90 / p95 135 ms, with a tail to 200 ms. Steps fell in 30-49 ms.

### Handling and body motion

| metric | P166 low (ref) | **P133 low** | **P133 default** |
|---|---|---|---|
| steady yaw 12 m/s, rad/s (yaw3) | 1.66 +- 0.03 (17) | 1.70 +- 0.05 (6) | 1.29 +- 0.14 (2) |
| steady yaw 18 m/s (yaw3) | 1.46 +- 0.08 (16) | 1.42 +- 0.12 (6) | 1.09 +- 0.84 (3) |
| steady yaw 25 m/s (yaw3) | 1.03 +- 0.17 (17) | 1.07 +- 0.16 (6) | 1.08 +- 0.05 (2) |
| speed held in the 25 m/s yaw phase, m/s | 24.1 +- 1.1 (17) | 24.0 +- 1.0 (6) | 21.9 +- 0.4 (2) |
| steady yaw 18 m/s (melee steer phase) | 1.30 +- 0.04 (22) | 1.34 +- 0.10 (8) | 1.38 +- 0.12 (4) |
| 0-10 m/s, s | 1.06 +- 0.01 (12) | 1.04 +- 0.01 (5) | **0.93 +- 0.03 (3)** |
| 0-20 m/s, s | 2.76 +- 0.01 (12) | 2.72 +- 0.03 (5) | **2.62 +- 0.01 (3)** |
| brake 30 m/s to stop, m | 25.5 +- 2.1 (10) | 18.8 +- 7.5 (3) | 22.4 +- 0.4 (2) |
| cruise roll-rate reversals, 1/s | 4.01 +- 0.9 (12) | 2.25 +- 0.54 (4) | 1.61 +- 0.38 (2) |
| cruise pitch-rate reversals, 1/s | 4.59 +- 1.4 (12) | 2.91 +- 1.1 (4) | 1.61 +- 1.1 (2) |
| cruise mean abs roll / pitch rate, deg/s | 9.8 / 16.1 (12) | 9.8 / 16.5 (4) | 8.5 / 16.0 (2) |
| cruise p95 abs roll / pitch rate, deg/s | 24.7 / 41.3 (12) | 21.0 / 36.5 (4) | 19.5 / 33.8 (2) |

### Placed 56 m/s T05 jump (one per boot)

| metric | P166 low (ref, 7 boots) | P166 low, matrix cell `r166low` (8 boots, existing data) | **P133 low (10)** | **P133 default (5)** |
|---|---|---|---|---|
| take-off speed, m/s | 51.6 +- 1.0 | 51.1 +- 1.2 | 52.1 +- 1.1 | 52.8 +- 0.9 |
| apex above take-off, m | 10.7 +- 0.4 | 10.5 +- 0.8 | 10.9 +- 0.4 | **11.8 +- 0.8** |
| distance, m | 228 +- 28 | 225 +- 17 | 208 +- 39 | 244 +- 47 |
| airborne, s | 4.64 +- 0.55 | 4.65 +- 0.34 | 4.16 +- 0.77 | 4.92 +- 1.0 |
| peak pitch, deg | 53 +- 18 | 71 +- 18 | 75 +- 25 | 76 +- 31 |
| lip step p50, ms | 31.0 | 33.0 | 35.5 | 44.5 |
| destroyed (95 % CI) | 0/7 (0-0.41) | 3/8 | **6/10 (0.26-0.88)** | 2/5 (0.05-0.85) |

- Fisher tests on destroyed jumps:
  - P133 low vs the P166 reference: 6/10 vs 0/7, p 0.035.
  - P133 low vs both P166 lowest cells pooled: 6/10 vs 3/15, p 0.087.
  - P133 low vs P133 default: 6/10 vs 2/5, p 0.61.
- Outcome follows the take-off pitch rate. Pooled over all cells (57 jumps), |q| >= 0.49 rad/s separates destroyed from
  survived with 3 misclassified.
  - |q| < 0.1: 12 survived, 0 destroyed.
  - |q| 0.1-0.49: 22 survived, 0 destroyed.
  - |q| >= 0.49: 3 survived, 20 destroyed.
- In P133 low, 5 of 10 take-offs were at |q| 0.85-0.91 and 4 of those 5 were destroyed. The batch matters:
  - The steep take-offs are all in the 06:26-06:50 batch: 4/5 destroyed, generated before the retail SFX 5 change.
  - The 10:54-11:23 batch: 2/5 destroyed.
  - Batch vs batch: Fisher p 0.52.
  - The same early-vs-late pattern shows in `r166low`: 2/3 destroyed in the early batch vs 1/5 in the late one.

## Answers

**1. P133 lowest vs the existing P166 retail reference.**
- The emulated P133 at lowest detail is still a **single-step** machine. 95-99 % of frames take one substep.
- Its step is about 5 ms longer in melee: 32.0 vs 26.8 ms (n 5 vs 12).
- In missions the step is essentially the same: T05 31.9 vs 31.1 ms (n 10 vs 16).
- On the T05 ground segment the P133 runs 37 vs 32 ms.
- Handling and acceleration match the P166 reference within tolerance:
  - steady yaw at 18 / 25 m/s
  - melee yaw
  - 0-10 / 0-20 / 0-30 m/s
  - take-off speed, apex and jump distance
- Exception: steady yaw at 12 m/s reads +2.4 % (1.70 vs 1.66; flagged by the compare tool, one yaw3 boot).
- Braking is inconclusive. The 18.8 m/s mean carries an sd of 7.5 over n 3, with one aberrant run.
- The reversal counts are lower: roll 2.25 vs 4.01 /s.
  - Treat this as partly the instrument. Reversals are counted per rendered frame, and every longer-frame cell reads fewer.
  - Spearman rho vs step is -0.83 over 19 cells.
  - The mean and p95 body rates (the actual jounce amplitude) are unchanged.
- The jump outcome is the one real candidate difference: 6/10 destroyed vs 0/7 on the P166 reference.
  - It weakens to p 0.087 against both P166 lowest cells pooled.
  - It is concentrated in the early batch.
  - **Verdict:** a P133-lowest run plays like the P166 reference on everything measured, with a possible higher
    jump-wreck rate that needs about 10 more boots per arm, run in one batch on each CPU, to confirm or drop.

**2. Developer default (multi-substep) vs lowest detail (single-step) on the P133.**
- The developer default runs at about 10-12 fps. That takes **2 substeps per frame**: 93-98 % of melee frames and 64-85 % of T05 frames, with the rest 3.
- Each substep is about **41.5 ms** (vs 32 ms single-step at lowest).
- So this is the emulator reference for the mixed-rate design: physics stepped twice per rendered frame at about 40 ms.
- It does behave differently on the metrics that the compare tool and the n allow:
  - **Faster acceleration off the line:** 0-10 m/s 0.93 vs 1.04 s, 0-20 m/s 2.62 vs 2.72 s (n 3 vs 5, sd 0.01-0.03).
    - Same direction as the existing P166 default cell (`r166p3`, 0.97 / 2.55).
    - Same direction as the dose-response across cells (rho -0.55 / -0.73).
  - **Higher, longer jumps:** apex 11.8 vs 10.9 m (n 5 vs 10). Distance 244 vs 208 m and airtime 4.9 vs 4.2 s, both with
    wide sd.
    - The existing `r166p3` reads the same apex rise: 12.0 m.
  - **Lower steady yaw at 12 m/s:** 1.29 vs 1.70 rad/s.
    - The 25 m/s phase could not hold speed: 21.9 vs 24.0 m/s.
    - This is one boot, n 2-3, so it is a lead, not a result.
- Not different:
  - melee steady yaw at 18 m/s (1.38 vs 1.34)
  - braking (22.4 m)
  - mean and p95 body roll / pitch rates
  - take-off speed
  - jump wreck rate (2/5 vs 6/10, p 0.61)
- The developer default's step (41.5 ms) is longer than the developer-stated 2 x 33.3 ms design.
  - The emulated P166 runs software rendering about 20 % fast (EMU-MEMTRACE s.9.5, Quake n 9).
  - If the P133 does the same, a real P133 at preset 2 would run frames of about 100 ms. That sits on the 2-to-3 substep boundary (2 x 50 or 3 x 33 ms) [inference, untested].

## Existing data kept (no new runs; owner cut)

Labelled existing data. Full tables are in lab `matrix.md` and `report.md`.

| cell | what | melee step p50 ms | note |
|---|---|---|---|
| `zref-r166low` | retail P166 lowest, gold standard | 26.8 (12) | the reference above |
| `r166low` | retail P166 lowest, matrix rerun | 26.5 (4) | jumps 3/8 destroyed |
| `r166p3` | retail P166 developer default (preset 3) | 41.9 (3), 2-3 substeps | same signature as `r133p2` |
| `r166m6`, `r166m5`, `r166p0`, `r166lmir*`, `r166lvis*`, `r166m6mir*` | retail P166 ~40 ms play-setting search (owner request) | 27.5-43 | mostly n 1; `r166lmirtex` 36 ms n 3 |
| `zref-g166low`, `g166lmirtex`, `g133low` | Gold exe, lowest / mirror+tex / P133 lowest | 31.3 / 36.0 / 37.3 | Gold runs 11-16 % slower than retail |
| `g166glide` | Gold P166 Glide | 22.0 (1) | the detail block in memory differed from the DEF (read back `0501...` vs `0700...`); cause not traced |

## Caveats

- n is small for the default cell's yaw3 (1 boot) and cruise (2 traces). Treat those rows as leads.
- Jump batches differ in time of day and script generation (SFX 4 before 08:40, SFX 5 after). Compare within a batch where it matters.
- The emulator-speed instrument check finds no effect of host speed on guest frame time: pooled rho -0.10, n 166 runs. r133low ranges 0.54-0.78 speed with rho 0.12.
- First-launch reads (no DEF) were scripted (`make_first`) but not run. They would not give the P133 row anyway, because the probe misreads the emulated CPU.

## Owner test

- None needed for this record. It is emulator-only and changes nothing in any install.
