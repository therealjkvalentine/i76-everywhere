# Same car, then the fingerprint: lab twin vs retail 1.0 on the emulated P166 and P133 (2026-10-17 night)

Lane same-car-and-fingerprint. This is physics-step study step L0 plus the first fingerprint of the tick arms.
- Data: lab `emu\results\same-car-20261017\`. Raw captures are in lab `captures\same-car-20261017\` (gitignored).
- Tools: lab `tools\same-car\`.
- Lab commits: 8d1189e, a2f546b, 306dba8, 926d9bb, dadfbf8, fa00bab.
- Not touched: the daily driver, the golden copy, the Macs, the game-night files.
- Live runs used only lab copies: a new `game-samecar`, plus 86Box (one VM at a time).
- Every live boot ran under the console lock with the audio muted (read back each hold).

## Summary

- **The lab's T05/T06 car was the wrong car.** The lab now loads the emulator's car, checked from memory on both sides.
  - The emulator runs use the save's car (bookmark SAVE001, par base `C:\I76GOLD`): a Picard Piranha with a 261ci 6 cyl, sway bars, disc & drum brakes, 14in Rally tyres, armour 900/600/600/700 and chassis 650/400/400/550.
  - The lab's direct mission boot loads the mission's own car, `vppirna1.vcf` "Jade's Car": a **432ci SHO V8 (power 193,960 vs 104,440)**, coil overs, 13in stock tyres, armour 400 x4 and chassis 360 x4.
  - That explains the "+20 % acceleration" and the "6080 vs 9600" in GOLD-STANDARD-FINGERPRINT and LAB-FRAME-REPLAY.
- **The fix is lab-only:** a loose `ADDON\vppirna1.vcf` holding the save's loadout, in a new lab copy `game-samecar` (= game-wst + that one file).
  - Both T05.MSN and T06.MSN name `vppirna1`, and a loose ADDON file overrides the archive.
  - The read-back (`sc_carprobe.py`) uses the same fields as the emulator's I76DRV `ent`:

    | | armour max F/L/R/B | chassis max | sum | mass (ent+0xa4) | engine P |
    |---|---|---|---|---|---|
    | emulator, retail P166 and P133 (I76DRV `ent start`, every T05/T06 run checked) | 1800/1200/1200/1400 | 1300/800/800/1100 | 9600 | not logged | 104,440 |
    | lab game-samecar, 37 of 37 boots | 1800/1200/1200/1400 | 1300/800/800/1100 | 9600 | **1846.0** | 104,440 |
    | lab control: same copy, override renamed away (1 boot) | 800 x4 | 720 x4 | 6080 | 1951.0 | 193,960 |

  - The mass 1846 equals the loader formula's prediction for the save's loadout (VEHICLES.md section 7; Jade's car predicts 1951, also read live).
  - The emulator's mass is not logged, so on that side it is a prediction from the same loadout, not a measurement.
- **With the same car, our exe matches retail on the T06 strip within 0-2.5 %.**
  - The earlier gaps (0-20 m/s -34 %, steady yaw -29 %) were the car, not the exe or the step.
  - Every arm now: 0-20 m/s 4.13-4.21 s vs 4.18; brake 11.75-11.77 vs 11.88 m/s2; steady yaw 1.099-1.116 vs 1.117 rad/s.
- **What still fails** (the same in step and tick arms unless noted):
  - **Left-key yaw:** -0.6 to -2.4 %. step33 and tick33 fail; tick66 passes.
  - **T06 ramp A flight:** 0.33-0.47 s shorter in the air, landing 9-15 m short, at the same apex and foot speed. Every arm, both references.
  - **T05 placed 56 m/s jump:** take-off -2 to -3 % (50.1-50.6 vs 51.6 m/s).
  - **step33 lip clips:** 4 of 24 jumps clipped the lip (vy -0.7 m/s, the car never took off). The tick arms clipped 0 of 30 (Fisher p 0.034).
  - **Platform rows** (substep mix): fail by design.
- **P133 vs P166:** our arms land with P166 on wrecks and launch jounce.
  - T05 wrecks: the P133 reference wrecks 6 of 10 placed jumps, P166 0 of 7, and every lab arm 0 of 15 (or 0 of 9).
  - The two references also disagree with each other on jounce: P133's launch pitch peak is -15 %.
- **A/A:** step33 against its twin step33aa agrees to the printed digit on every T06 row. The lab boots are deterministic: tick arms repeat bit-for-bit (sd 0.000).
  - So "n 5 independent boots" measures the harness's spread (zero), not a physical spread.
  - The pass bands come from the retail spread.

## 1. Which car, and why it differed

| | emulator (retail / Gold, P166 / P133, T05 and T06) | lab before (direct mission boot) | lab now (`game-samecar`) |
|---|---|---|---|
| where the car comes from | SAVE001.CMP in the par base `C:\I76GOLD` (bookmark 'emu T06 (scene 6)' / 'T05 start (emu)'; make-t06-base.py only changes the scene) | `vppirna1.vcf` from I76.ZFS, the T05/T06 mission car | loose `ADDON\vppirna1.vcf` (lab `tools\same-car\car\vppirna1.vcf`, md5 1d636559), built with `i76mod.py car` from the save's loadout |
| engine / suspension / brakes | 261ci 6 cyl (id 0) / Sway Bars (1) / Disc & Drum (1) | 432ci SHO V8 (2) / Coil Overs (2) / Disc & Drum (1) | as the emulator |
| tyres | 14in Rally (wauto_1b) | 13in stock (wauto_1a) | as the emulator |
| weapons (mass only) | Oil Slick, 50cal, FireRite, 50cal | Landmines, Gas Launcher, 50cal, 25mm | as the emulator |
| specials | X-Aust brake, nitrous, Structo bumper | none | **none** (vppirna1 has no SPEC chunk; none is used by the protocols, no mass) |

- The ids map engine 0 / 1 / 2 = 261 / 305 / 432 SHO. They were read from stock vcf files whose parts are known (vppa01, noal01, vppirna3).
- The save editor dump was read from the par base image with lab `emu\tools\fat.py`, read-only.
- The T05 car is the same. Every r166 / r133 T05 jump boot logs the same `ent start` maxima and P.

## 2. Arms and protocol

- Harness: lab `tools\whole-sim-tick\wst-run.ps1` (copied as `tools\same-car\sc-run.ps1`).
  - It runs headless on a private desktop with the null renderers, exe 6319abf7 and proxy `Strlkup-wst2.dll` c059f270.
  - That proxy is the whole-sim-tick side build: promotion-18 source plus the tick. It is not the daily driver's 33211f11.
- Conditions are exactly WHOLE-SIM-TICK's:
  - **step33** = lab-step-33 as its launcher runs it.
  - **tick33 / tick66** = lab-step-33 minus every timing patch, plus `I76_SIM_TICK_MS` 33.3333 / 66.6667.
  - **step33aa** = an independent second set of step33 boots (the A/A).
- Measures:
  - **t06**: phys-suite on the T06 strip (accel 11 s, brake, steer R/L at 18 m/s, drop, ramp A at 26 / 30 / 34 m/s).
  - **t05p56**: 3 placed T05 jumps per boot at 56.0 m/s on the centre line, 150 m before the foot (gen_t05jump's placement).
  - Placements were read back from the first logged row of each phase: within 0.01 m. phys-suite's own `*_placed` flags read false in both these and the earlier WST captures; that is a flag issue, not the pose.
- Boots: step33 5+5, tick33 5+5, tick66 5+5, step33aa 3+3.
  - One more step33 t06 boot (v1, the car check) is not in the tables.
  - Conditions were interleaved per round, with the order reversed on even rounds. One tick33 t05p56 boot died at load before the mission (OpenProcess failed: the game had exited) and was re-run (s3b).
  - Total 38 boots in 3 lock holds, 18:31-19:20.
- References:
  - **P166:** `emu\results\gold-standard\retail-p166-low.json`, the gold standard as built.
  - **P133:** new, `emu\results\gold-standard\retail-p133-low.json`.
    - It holds the HARDWARE-MATRIX r133low cell (melee and yaw3 boots, 10 placed T05 jumps).
    - Plus **new P133 T06 strip runs** from tonight: `ref-t06strip-retail.txt --cpu 133`, the same script, base and discs as the P166 strip.
    - 3 boots, 5 reps. Boots 2-3 lost reps 2-3 when the Abort > Replay restart timed out.
  - The P133 strip step is 38.6 +- 0.5 ms against P166's 33.0.
  - On the strip, P133 agrees with P166 on accel / brake / yaw within 1.4 %.
- Checker fix (lab 306dba8, 926d9bb):
  - `fingerprint.py`'s impact rejection now differences distinct sim states.
  - Before the fix, lab captures at 120 fps repeat each state with an interpolated sim_time. A clean 33 ms speed step then read as 165 m/s2, which dropped every lab brake sample. Steer samples could be dropped the same way.
  - Emulator rows are one per state. The self-test is identical with and without the fix (A/A 55/5 and 66/0).
  - Note: that is not the 58/2 printed in GOLD-STANDARD-FINGERPRINT; the drift predates this lane.

## 3. Pass / fail per metric

- Cells: lab mean +- sd (n samples), then the verdict. n = boots for strip metrics; yaw counts R and L.
- The pass band is fingerprint.py's: the 95 % prediction half-width from the reference's within- and between-boot spread, with the metric's floor.
- Gate rows give PASS / FAIL; watch rows give ok / OUT.
- Full tables: lab `emu\results\same-car-20261017\table.md`, `*-vs-p166.md`, `*-vs-p133.md`.

### Against retail P166 low (the gold standard)

| what | metric | P166 ref (n / boots) | step33 | step33aa (A/A) | tick33 | tick66 |
|---|---|---|---|---|---|---|
| accel | 0-10 m/s, s | 1.168 +- 0.015 (6/2) | 1.176 +- 0.011 (5) PASS | 1.192 +- 0.009 (3) PASS | 1.167 (5) PASS | 1.133 (5) PASS |
| accel | 0-20 m/s, s | 4.18 +- 0.02 (6/2) | 4.21 +- 0.01 PASS | 4.21 +- 0.01 PASS | 4.20 PASS | 4.13 PASS |
| accel | distance in 10 s, m | 202 +- 1 (6/2) | 201 PASS | 201 PASS | 201 PASS | 203 PASS |
| braking | decel 25 -> 5 m/s, m/s2 | 11.88 +- 0.01 (6/2) | 11.77 +- 0.01 PASS | 11.77 PASS | 11.77 PASS | 11.75 PASS |
| braking | stop distance, m (watch) | 36.2 +- 0.5 | 38.9 OUT | 38.9 OUT | 37.9 OUT | 39.6 OUT |
| steady yaw | right, rad/s | 1.107 +- 0.003 (6/2) | 1.097 PASS | 1.097 PASS | 1.103 PASS | 1.111 PASS |
| steady yaw | left, rad/s | 1.128 +- 0.007 (6/2) | 1.101 **FAIL** (-2.4 %) | 1.101 **FAIL** | 1.109 **FAIL** (-1.7 %) | 1.121 PASS |
| steady yaw | pooled, rad/s | 1.117 +- 0.012 (12/2) | 1.099 **FAIL** (-1.6 %) | 1.099 **FAIL** | 1.106 PASS | 1.116 PASS |
| steady yaw | held speed, m/s | 24.00 +- 0.25 | 24.08 PASS | 24.08 PASS | 24.23 PASS | 24.28 PASS |
| slide (watch) | skid share / slip deg / v_lat m/s | 0 / 1.75 / 0.73 (12/2) | 0 / 1.27 / 0.55 ok | 0 / 1.27 / 0.55 ok | 0 / 1.39 / 0.60 ok | 0 / 1.84 / 0.79 ok |
| T06 ramp A, 30 m/s | foot speed, m/s | 35.28 +- 0.08 (5/2) | 35.73 PASS | 35.72 PASS | 35.78 PASS | 35.73 PASS |
| T06 ramp A, 30 m/s | air time, s | 2.27 +- 0.07 (5/2) | 1.80 **FAIL** | 1.79 **FAIL** | 1.83 **FAIL** | 1.80 **FAIL** |
| T06 ramp A, 30 m/s | apex y, m | 28.52 +- 0.11 | 28.22 PASS | 28.21 FAIL | 28.53 PASS | 28.35 PASS |
| T05 placed 56 | take-off speed, m/s | 51.62 +- 1.00 (7/7) | 50.32 +- 2.14 (15) **FAIL** | 50.05 (9) **FAIL** | 50.18 +- 1.03 (15) **FAIL** | 50.57 (15) PASS |
| T05 placed 56 | take-off vy, m/s | 14.45 +- 0.28 | 12.26 +- 5.26 **FAIL** (lip clips) | 10.96 **FAIL** (lip clips) | 14.05 **FAIL** | 14.16 PASS |
| T05 placed 56 | apex above take-off, m | 10.66 +- 0.41 | 8.97 **FAIL** | 8.09 **FAIL** | 10.08 **FAIL** | 10.23 PASS |
| T05 placed 56 | ballistic ratio | 1.000 | 1.000 PASS | 1.000 PASS | 1.000 PASS | 1.000 PASS |
| T05 placed 56 | distance, m (watch) | 228 +- 28 | 202 ok | 190 OUT | 213 ok | 235 ok |
| T05 placed 56 | destroyed / turned over | 0/7, 0/7 | 0/15, 2/15 PASS | 0/9, 1/9 PASS | 0/15, 2/15 PASS | 0/15, 0/15 PASS |

- The T06 ramp at 26 m/s is like 30. Air time is 1.33 vs 1.67 s and the landing is 9-12 m short (FAIL in every arm).
- At 34 m/s the same rows pass (2.25-2.27 vs 2.50 s, inside a wide band).
- Body motion (lab `tools\same-car\jounce.py`, `jounce-vs-r166.md`):
  - Measured as the launch squat (accel from rest) and the roll into the 18 m/s steer step, per distinct physics state.
  - Pass rule: fingerprint's, without the boot term.

  | metric | P166 (n 6) | P133 (n 5) | step33 (5) | step33aa (3) | tick33 (5) | tick66 (5) |
  |---|---|---|---|---|---|---|
  | launch pitch-rate peak, deg/s | 71.9 +- 5.3 | 61.4 +- 5.8 (FAIL vs P166) | 67.3 PASS | 67.3 PASS | 67.3 PASS | 57.4 **FAIL** |
  | launch squat settles after, s | 0.60 +- 0.05 | 0.66 +- 0.06 | 0.52 PASS | 0.52 PASS | 0.50 FAIL | 0.47 FAIL |
  | launch pitch reversals | 2.7 +- 0.5 | 3.8 +- 0.5 (FAIL) | 3.0 PASS | 3.0 PASS | 3.0 PASS | 3.0 PASS |
  | steer roll-rate peak, deg/s | 34.0 +- 1.2 | 31.2 +- 1.2 (FAIL) | 34.5 PASS | 34.5 PASS | 34.7 PASS | 31.8 **FAIL** |
  | steer roll mean, first 2 s, deg/s | 3.3 +- 1.1 | 2.4 +- 0.2 | 2.8 PASS | 2.8 PASS | 2.9 PASS | 2.6 PASS |

  - The launch has no roll on any platform: roll reads 0.
  - Against P133, the step33 / tick33 rows fail the same peaks that P166 fails; tick66 passes them.
- **Platform rows** (substep share, step mix): every arm fails, by design. The lab steps are fixed; retail's follow the frame.

### Against retail P133 low

- Same arms, same captures. Lab `*-vs-p133.md`.
- **Accel 0-20 m/s:** P133 is 4.14 +- 0.01 (5/3). step33 / step33aa / tick33 (4.20-4.21) **FAIL**; tick66 (4.13) PASS.
- **Brake decel:** 11.74 +- 0.01. All arms PASS.
- **Steady yaw, pooled:** 1.118 +- 0.011 (10/3). step33 **FAIL**; tick33 / tick66 PASS. Left yaw fails in step33 / step33aa / tick33.
- **T05 placed jump** (P133 n 10 boots):
  - Take-off 52.08, vy 14.58, apex 10.88. Every arm FAILS take-off speed, vy and apex (-2 to -4 %).
  - **Destroyed: P133 6/10 vs every arm 0/15 (Fisher p 0.001; step33aa 0/9, p 0.011).**
  - Turned over: P133 6/10. step33 and tick33 2/15 FAIL (p 0.028), tick66 0/15 FAIL, step33aa 1/9 PASS (p 0.057).
  - The P133 wreck rate is the HARDWARE-MATRIX "possible higher wreck rate" (6/10 vs P166's 0/7).
  - Its jumps take off with a larger pitch rate (1.92 +- 0.39 vs 1.61 rad/s; ours 1.52-1.57). Our arms do not reproduce it.
- **T06 ramp A:** the P133 reference has only 1 boot at 30 m/s (reps 2-3 lost), so those rows are INFO.

## 4. Readings (what the numbers say, and what they do not)

1. **The car was the whole strip gap.**
   - Same car: 0-20 m/s moves from -34 % to +0.6 %, steady yaw from -29 % to -1.6 %, and brake decel reads -1.0 %.
   - Every lab-vs-retail comparison before tonight (ERA-ENVELOPE, retail-handling, LAB-FRAME-REPLAY's T05) carried the SHO V8 car. Those behaviour deltas should be re-read with `game-samecar` before any of them is acted on.
2. **Step vs tick, same car.**
   - On the gold standard (P166), tick66 passes every behaviour gate on accel / brake / yaw / T05 jump, and its foot speed passes too.
   - tick33 fails left yaw (-1.7 %) and the T05 take-off (-2.8 %, vy -2.8 %).
   - step33 fails yaw (pooled -1.6 %, left -2.4 %) and clips the T05 lip in 4 of 24 jumps. The tick arms clipped 0 of 30 (p 0.034). n is small: report it as a candidate, not settled.
   - On body motion, tick66 drops the launch and steer peaks by 7-15 % (the 2 x 33.3 ms step), toward P133. step33 / tick33 sit on P166.
3. **The two references disagree.** P133 differs from P166 on:
   - launch pitch peak (-15 %), steer roll peak (-8 %);
   - 0-20 m/s (-1 %);
   - T05 wreck rate (6/10 vs 0/7).

   No arm passes both everywhere. Which reference governs is the owner's ruling (gold standard = P166 low; hardware reference = P133).
4. **T06 ramp flight is short in every arm and does not move with the step.**
   - Same apex, foot speed within +1.3 %, but 0.3-0.5 s less air and 9-15 m shorter.
   - Not traced tonight. It is not the car and not the step. Candidates (unverified):
     - the airborne / landing detection on the lab's interpolated 120 fps rows vs the emulator's 30 fps rows;
     - the landing surface (`I76_TERRAIN_HULL_FIX` is in the lab-step-33 preset).
   - Next: the same comparison with the hull fix off, and the landing frame read from clearance on distinct states.
5. **n.** The lab boots repeat bit-for-bit within a tick arm (sd 0.000 on most rows; step33 varies in the 3rd digit).
   - Independent boots therefore do not add physical spread. The bands come from the retail references (P166: 2 boots on the strip, 7 on T05; P133: 3 strip boots, 10 T05 boots).
   - More retail strip boots would tighten the strip bands more than more lab boots.

## 5. Not done / blockers

- The emulator car's **mass** is not read on the emulator side: I76MEM / I76DRV `ent` do not log +0xa4. It is predicted (1846) from the loadout by the formula that reproduces the lab's live 1951 and 1846.
  - Logging it needs one I76DRV change (`ent` + mass). Not built tonight.
- **Melee contexts** (P166 / P133 melee accel, yaw3 at 12 / 25 m/s, cruise jounce) are not compared. The lab has no headless melee protocol (LAB-FRAME-REPLAY section 4).
  - The melee car is the default `valepre4.vcf` = Jade's car on both sides, so it would not need the override.
- **Special equipment** (X-Aust brake, nitrous, Structo) is not on the lab car.
  - No protocol triggers them, and they carry no mass in the loader formula.
  - A collision (Structo) protocol would need them; that needs a SPEC chunk added to the vcf.
- The P133 strip has 5 reps from 3 boots. 2 boots lost reps 2-3 at the restart (waitmem 0x505490 timeout at host speed 0.78).

## 6. How to repeat

```
lab:  powershell -File tools\same-car\sc-loop.ps1 -Queue <file of "cond measure tag" lines>   (console lock, muted)
      python -I emu\tools\memtrace\fingerprint.py compare "captures\same-car-20261017\t06-tick66-s*.phys.csv" ^
          "captures\same-car-20261017\t05p56-tick66-s*.phys.csv" --ref emu\results\gold-standard\retail-p133-low.json
      python -I tools\same-car\jounce.py r166=emu\results\memtrace\*-r166sim-fpt06strip-* tick66=captures\...\t06-tick66-s*.phys.csv --ref r166
```

`game-samecar` is any lab copy plus `tools\same-car\car\vppirna1.vcf` in `ADDON\`. Read the car back with `sc_carprobe.py` in every boot.

## 7. Owner tests

None needed for this lane's result: the car identity is read from memory on both sides.
