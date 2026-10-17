# AI and damage balance across exes and step lengths (2026-10-17)

Lane `ai-damage-runs` (started 2026-10-17 morning, paused when the owner took his CPU back, resumed the same day).
Goal: AI and damage balance on retail 1.0 (simulation physics) at the emulated P166 and P133, Gold at the P166, and
our exe at several step lengths, with the logger from AI-DAMAGE-METRICS.md (I76AIM build 2026-10-17c).

Tools and data (lab `i76-uncap-lab`):
- scripts: `emu\tools\memtrace\gen_aidmg.py` (lab 555429f, 8e051fd; results bdca00b), `emu\tools\par\scripts\aidmg-*.txt`;
- emulator queue: `tools\ai-damage-runs\aidr-emu-campaign.ps1` (one VM for this lane, waits while 3 or more 86Box run
  on the host, BelowNormal priority inherited by parrun and 86Box);
- host runs of our exe: `tools\ai-damage-runs\aidr-host-run.ps1`, `aidr_host.py`, `aidr-campaign.ps1`;
- analysis: `tools\ai-damage-runs\aidr_summary.py` (per-condition table, exact permutation tests),
  `aidr_weapons.py` (AI rounds per weapon), both on top of `emu\tools\memtrace\ai_damage.py`;
- run folders: emulator `emu\results\par\20261017-*-aidmgruns-*` (text files in git; `AIM.BIN` / `MEM.BIN` are
  git-ignored and kept on disk only), host `captures\ai-damage-runs-20261017\t13*-*` (git-ignored, on disk);
- the generated tables quoted below: `emu\results\ai-damage-runs\` (`t13.md/json`, `fire.md/json`, `pooled.md`,
  `wpn-parked.md`, `melee2-ai.md`, `melee2-fire.md`).

## 0. Answers first

Rates are per minute of sim time. "± x" is the sample sd, n is runs (boots). p is an exact two-sided permutation test
of the difference in means. With n 3 vs 3 the smallest p possible is 0.10, so the per-cell tables cannot show
significance; section 4 pools the parked and firing T13 variants (retail P166 n 10, P133 n 8, the others n 6-8) for
the incoming-damage metrics, as an exploratory step. About 70 tests are reported there, so a single p near 0.04 is
weak evidence.

1. **Retail 1.0 at the gold standard (P166, software, lowest detail, simulation physics): T13 with the player
   parked.** n 10 (7 parked + 3 holding fire):
   - damage taken 2314 ± 540 /min (range 1591-3181);
   - AI rounds 118 ± 48 /min, hit events on the player 31 ± 10 /min;
   - first damage at 19.3 ± 1.2 s after the mission is live;
   - the player dies every time (10 of 10), 36 ± 11 s after first damage (range 22-53 s);
   - engagement distance (per-car median at its hits, weighted) 131 ± 37 m; about 3.3 AI cars attack at once.
   - **The spread is the main result.** Time-to-die varies by ± 31 % (cv) between identical boots, and damage per
     minute by ± 23 %.
2. **Retail P133 vs P166 (steps 38-40 ms vs 32-33 ms), n 8 vs 10:** no measured difference in damage taken (2577 vs
   2314 /min, p 0.48), AI rounds (p 0.76), hits (p 0.74) or time-to-die (38.2 vs 36.3 s, p 0.76). One P133 player
   survived the 90 s parked phase (all four armour sides at 0, chassis intact; it died in the next phase).
   Engagement distance was shorter at P133 (86 vs 131 m, p 0.014).
3. **Gold CD at Champ (difficulty byte 1 = x1.0, read back in every sample) vs retail, both P166, n 6 vs 10:** Gold's
   player took more damage per minute (3194 ± 496 vs 2314 ± 540, +38 %, p 0.007). Time-to-die was the same (33.2 vs
   36.3 s, p 0.56): the extra damage lands but does not kill sooner. Gold steps 37-38 ms, but retail at the same
   step (P133, 38-40 ms) does not differ from retail P166, so the step length does not explain the gap; the exe and
   its data (different T13 loadouts, section 5) remain. That is an inference, not a test.
4. **Our exe (AiO + our proxy, host, null renderer) with the stock stepper at a 30 ms step is indistinguishable from
   retail P166** on every metric (n 8 vs 10, all p >= 0.07): damage taken 2181 vs 2314, time-to-die 42.9 vs 36.3 s
   (one of the eight survived the phase; its lower bound is used).
5. **AI fire volume follows the frame rate, as the code says it should.** `ai_ShouldFireWeapon` rolls its random
   gate once per frame (i76-map `subsystems/ai.md`, "Fire decisions", verified live 2026-09-27). Measured on our exe,
   pooled n 7-8:
   - 8 ms steps (120 fps): 292 ± 81 AI rounds /min; 30 ms: 129 ± 39 (2.3x, p < 0.001).
   - But **damage taken does not rise** (2076 vs 2181 /min, p 0.76): damage per round falls from 17 to 7.5
     (p < 0.001). The extra rounds miss. The turret (30cal, fire skill 1.0) carries most of the increase.
6. **The daily driver's preset (best-wide: fixed 41.67 ms step, I76_FRAMERATE_FIXES, 20 Hz AI grids) makes the T13
   AI much less aggressive than retail:** AI rounds 50 ± 13 vs 118 ± 48 /min (-58 %, p 0.004); hits on the player 20
   vs 31 /min (p 0.014); damage taken 1433 ± 658 vs 2314 ± 540 /min (-38 %, p 0.012). Time-to-die is not
   significantly longer (38.9 vs 36.3 s, p 0.67), apparently because death comes from internal component damage
   (item 8).
   This is the same direction as FIX-INVENTORY's "the driver's AI is off the 20 fps game", now measured on combat.
7. **Time-to-kill by the player and player kills: not measurable with this design.** The parked player never kills
   anything (0 kills in every run). AI deaths were all self-inflicted (bw 5 in 6 runs; retail P166 1 in 10, P133 1
   in 8).
8. **What kills the parked player is not the armour total.** Runs die with one armour side at 0 and the chassis near
   full (063010: rear armour 0, chassis 1299 / 1300), or survive with all four sides at 0 (081703). The
   I76DRV `ent` line's 5th engine field falls to 0 at death in both. Time-to-die is therefore a noisy, threshold-like
   metric.
9. **For the step study (PHYSICS-STEP-STUDY-DESIGN.md):**
   - **B4 as written ("T13 time-to-die and damage per minute within ± 25 % of retail") needs about 25 boots per arm
     for time-to-die and about 14 for damage per minute** at retail P166 (80 % power, two-sided 0.05, from the
     measured cv; P133 and our exe are noisier: 25-44). At ~8 min per emulator boot that is 2-3.5 h per retail
     reference cell. Section 8 lists cheaper forms.
   - H6 (AI and damage insensitive to T under a whole-sim tick): today's exe is per-frame for AI fire, so fire volume
     does depend on the frame rate (item 5). Damage taken did not, within the band tested.
   - **Not run: the 40 ms cells on our exe** (e40 = stock stepper at 25 fps, f40 = I76_FIXED_STEP=25 at 120 fps).
     The console lock was held by the owner's test session from 08:05 to past 11:35, with one other lane in between,
     so no host boot started (section 6). Both conditions are in `aidr-host-run.ps1`, ready to run.

## 1. Setup

| cell | exe | CPU | renderer, detail | DEF | difficulty | step p50 (T13) | fps (T13) |
|---|---|---|---|---|---|---|---|
| r166 | retail 1.0 `6cc509ad` | emulated P166 (pbs-p166g) | software, 320x200 lowest | RPLYR.DEF via filehex: sim (option flags 0) | none in retail (reads -1) | 32-34 ms | 28.0-28.8 |
| r133 | retail 1.0 | emulated P133 (restored lab 8972063) | same | same | none | 38-40 ms | 23.1-24.0 |
| gc166 | Gold CD `e1dca993` | emulated P166 | software (no `-glide`), 320x200 lowest | par base Gold DEF, byte 0x5c set to 1 by filehex | Champ (x1.0), read back | 37-38 ms | 24.7-25.4 |
| e30 | our exe `6319abf7` (AiO + u32x) on `game-aidr`, proxy `cbcff703` | host | null Glide | game-aidr DEF | 1 (Champ), read | 30 ms (stock stepper, 1 ms tick, 33.3 fps cap) | 33.3 |
| e8 | same | host | same | same | 1 | 8 ms (125 fps cap) | 118-125 |
| bw | same + best-wide's switches | host | same | same | 1 | fixed 41.67 ms | 113-124 |
| e40 / f40 | same | host | same | same | 1 | 40 ms stock (25 fps) / fixed 40 ms at 120 fps | section 6 |

- **Arcade check.** Every sample of every run has the player's entity flag 0x10000 clear (summary column `arcade` =
  0 in all rows). All retail rows are simulation physics.
- **Audio bytes.** Retail runs before 08:17 used RPLYR.DEF with SFX 4 (Gold's value). Runs from 08:17 on use the
  `-rd` scripts with retail's own defaults (music 3 / SFX 5 / voice 10; only byte 0x4f differs; the VMs run muted).
  Run IDs with SFX 5: 081703, 082425, 084045, 084757, 090313, 090949, 092239, the melee2 runs from 09:28 and the
  six T13 reference runs 104412-111625. No effect is expected; each retail cell mixes both, and the per-run tables
  carry the run IDs.
- **Real-time.** The emulator runs ran at 0.5-0.6 of real time with 3 VMs on the host. The rig's guest-time
  measurements (GetTickCount, frame counter) stay valid when a VM falls behind (lab `emu\README.md`, "Real-time
  check").
- **Scripts.** T13 = the `T13 start (emu)` bookmark, opening skipped. Parked: `ai` phase 90 s, player idle. Firing:
  `fire` phase 120 s, Space held 3 s / released 1 s, the default weapon firing wherever the car points. On the host
  the firing variant writes the fire byte 0x5367db (the keyboard refills it every frame, so it is best effort):
  host players fired 80-160 rounds /min against 400 on the emulator. **Host and emulator "damage dealt" are not
  comparable;** incoming-damage metrics are.
- **Excluded:** `20261017-074455-aidmgruns-t13-r133-1` (no DONE.TXT: interrupted by the pause). The host
  `t13-e30-smoke1` / `t13fire-e30-smoke2` runs are smoke tests, not counted.

## 2. T13, player parked (phase `ai`, 90 s)

| metric | r166 | gc166 | r133 | e30 | e8 | bw |
|---|---|---|---|---|---|---|
| step p50 ms | 32.1 ± 0.4 (n 7) | 37 (n 3) | 38.6 ± 0.9 (n 5) | 30 (n 5) | 8 (n 4) | 41.7 (n 4) |
| fps | 28.8 ± 0.3 | 25.4 ± 0.5 | 24.0 ± 0.4 | 33.3 | 120 ± 3 | 117 ± 3 |
| damage taken /min | 2299 ± 514 (1591..3181) | 3023 ± 699 (2352..3748) | 2741 ± 1170 (1326..3914) | 2439 ± 618 | 1808 ± 390 | 1223 ± 739 |
| AI rounds /min | 108 ± 43 | 125 ± 67 | 125 ± 51 | 149 ± 25 | 316 ± 105 | 46 ± 14 |
| hit events on player /min | 32 ± 8 | 40 ± 21 | 37 ± 13 | 45 ± 28 | 61 ± 32 | 21 ± 6 |
| event hit rate (hits / AI rounds) | 0.32 ± 0.09 | 0.32 ± 0.05 | 0.32 ± 0.08 | 0.29 ± 0.13 | 0.18 ± 0.04 | 0.46 ± 0.08 |
| damage per AI round | 24 ± 9 | 30 ± 18 | 24 ± 11 | 16 ± 4 | 6.0 ± 1.6 | 25 ± 9 |
| engagement m | 128 ± 41 | 90 ± 4 | 83 ± 35 | 101 ± 34 | 100 ± 54 | 79 ± 11 |
| attackers at once | 3.27 ± 0.15 | 2.9 ± 0.8 | 3.32 | 3.1 ± 0.6 | 3.05 ± 0.24 | 2.9 ± 0.6 |
| first damage s | 19.0 ± 1.0 | 18.0 ± 0.2 | 20.1 ± 1.1 | 16.9 ± 0.8 | 19.1 ± 1.2 | 19.2 ± 0.4 |
| player died in phase | 7 / 7 | 3 / 3 | 4 / 5 | 4 / 5 | 4 / 4 | 4 / 4 |
| time-to-die s (from first damage; survivors as lower bound) | 36.9 ± 11.6 (22..53) | 35.2 ± 8.5 (25..41) | >= 43.0 ± 16.9 (22..69) | >= 44.8 ± 18.4 | 45.0 ± 16.8 | 43.6 ± 13.8 |
| AI deaths (all self) | 1 in 7 runs | 0 | 1 in 5 runs | 0 | 0 | 5 in 4 runs |

Full per-run rows and the per-cell pairs: `emu\results\ai-damage-runs\t13.md`.

## 3. T13, player holding fire (phase `fire`, emulator; `ai` with the fire byte, host)

| metric | r166 | gc166 | r133 | e30 | e8 | bw |
|---|---|---|---|---|---|---|
| step p50 ms | 33.3 ± 0.6 (n 3) | 38.3 ± 0.6 (n 3) | 40 (n 3) | 30 (n 3) | 8 (n 3) | 41.7 (n 2) |
| fps | 28.0 ± 0.5 | 24.7 ± 0.1 | 23.1 ± 0.4 | 33.3 | 122 ± 4 | 119 ± 1 |
| damage taken /min | 2351 ± 719 | 3366 ± 197 | 2304 ± 693 | 1751 ± 637 | 2433 ± 546 | 1852 ± 17 |
| damage dealt /min | 71 ± 73 | 34 ± 55 | 37 ± 15 | (host, not comparable) | | |
| player rounds /min | 399 | 400 | 403 | 80 ± 15 | 146 ± 51 | 162 ± 5 |
| AI rounds /min | 143 ± 58 | 167 ± 14 | 126 ± 56 | 95 ± 37 | 260 ± 11 | 58 ± 2 |
| hit events on player /min | 30 ± 14 | 44 ± 3 | 26 ± 5 | 54 ± 27 | 77 ± 36 | 17 ± 3 |
| time-to-die s | 34.6 ± 13.0 | 31.3 ± 6.0 | 30.2 ± 5.8 | 39.8 ± 20.4 | 42.3 ± 18.2 | 29.4 ± 0.0 |
| player died | 3 / 3 | 3 / 3 | 3 / 3 | 3 / 3 | 3 / 3 | 2 / 2 |

The player fired about 400 rounds /min on the emulator and dealt 34-71 damage /min: the default weapon fired at
nothing in particular. No player kills. `emu\results\ai-damage-runs\fire.md`.

## 4. Pooled T13 (parked + firing), incoming-damage metrics

Pooling assumes the player's own fire does not change what the AI does to it. Player damage dealt was 1-3 % of
damage taken, and the AI's rates sit in the same ranges in both variants (sections 2-3), but this is an assumption.

| metric | r166 (n 10) | gc166 (n 6) | r133 (n 8) | e30 (n 8) | e8 (n 7) | bw (n 6) |
|---|---|---|---|---|---|---|
| damage taken /min | 2314 ± 540 | 3194 ± 496 | 2577 ± 986 | 2181 ± 679 | 2076 ± 536 | 1433 ± 658 |
| AI rounds /min | 118 ± 48 | 146 ± 49 | 125 ± 49 | 129 ± 39 | 292 ± 81 | 50 ± 13 |
| hit events /min | 31 ± 10 | 42 ± 14 | 33 ± 11 | 48 ± 26 | 67 ± 32 | 20 ± 5 |
| hit rate | 0.29 ± 0.09 | 0.29 ± 0.05 | 0.28 ± 0.09 | 0.39 ± 0.21 | 0.23 ± 0.11 | 0.41 ± 0.11 |
| damage per AI round | 22 ± 9 | 25 ± 13 | 23 ± 13 | 17 ± 4 | 7.5 ± 2.6 | 27 ± 8 |
| engagement m | 131 ± 37 | 128 ± 96 | 86 ± 30 | 96 ± 51 | 95 ± 42 | 86 ± 14 |
| first damage s | 19.3 ± 1.2 | 18.3 ± 0.5 | 20.3 ± 0.9 | 18.3 ± 4.0 | 18.9 ± 1.2 | 18.9 ± 0.6 |
| time-to-die s (lower bound for survivors) | 36.3 ± 11.3 | 33.2 ± 6.9 | 38.2 ± 14.7 | 42.9 ± 17.9 | 43.9 ± 16.0 | 38.9 ± 12.9 |
| died | 10 / 10 | 6 / 6 | 7 / 8 | 7 / 8 | 7 / 7 | 6 / 6 |

Exact permutation p (two-sided):

| pair | taken | AI rounds | hits | hit rate | dmg / round | engage | first dmg | time-to-die |
|---|---|---|---|---|---|---|---|---|
| r166 : gc166 | **0.007** | 0.28 | 0.088 | 0.87 | 0.55 | 0.93 | 0.077 | 0.56 |
| r166 : r133 | 0.48 | 0.76 | 0.74 | 0.95 | 0.72 | 0.014 | 0.075 | 0.76 |
| gc166 : r133 | 0.18 | 0.44 | 0.20 | 0.82 | 0.82 | 0.28 | 0.002 | 0.51 |
| r166 : e30 | 0.65 | 0.62 | 0.072 | 0.18 | 0.19 | 0.11 | 0.57 | 0.35 |
| r166 : bw | **0.012** | **0.004** | **0.014** | 0.035 | 0.19 | 0.013 | 0.53 | 0.67 |
| e30 : e8 | 0.76 | **< 0.001** | 0.21 | 0.084 | **< 0.001** | 0.96 | 0.88 | 0.92 |
| e30 : bw | 0.060 | **0.001** | **0.015** | 0.87 | 0.010 | 0.68 | 0.90 | 0.64 |
| e8 : bw | 0.068 | **0.001** | **0.004** | 0.019 | **0.001** | 0.72 | 0.94 | 0.54 |

Bold: p <= 0.015, or p <= 0.03 with a code-predicted mechanism (the per-frame fire roll; bw's 20 Hz / 24 Hz grids).
Gold's first damage comes earlier than retail P133's (p 0.002) and P166's (p 0.077), by about 1-2 s.
`emu\results\ai-damage-runs\pooled.md`.

## 5. AI rounds per weapon (parked T13, rounds /min, per-run values in brackets)

Retail's weapon instance stores a sound name at +0x2c where Gold stores the weapon name, so retail rows are named by
sound. The pairing in the last column is **inferred from the rates only**, not traced.

| weapon | r166 (n 7) | gc166 (n 3) | r133 (n 5) | e30 (n 5) | e8 (n 4) | bw (n 4) | retail sound name (inferred) |
|---|---|---|---|---|---|---|---|
| 30cal Turret | - | 41 ± 47 [95, 10, 17] | - | 69 ± 35 | 152 ± 40 | 11 ± 3 | wlmgun? |
| 30mm Cannon | - | 43 ± 11 | - | 49 ± 13 | 51 ± 28 | 23 ± 8 | whcan? |
| 50cal MG | - | 28 ± 24 | - | 22 ± 19 | 77 ± 57 | 5 ± 3 | wmmgun? |
| DrRadar Msl | - | 7.7 ± 2.6 | - | 9.6 ± 2.5 | 8.3 ± 1.4 | 5.3 ± 1.6 | wrhm? |
| Oil Slick | - | 5.6 ± 9.8 | - | 0 | 28 ± 56 | 0 | (none in retail) |
| whcan.wav | 47 ± 19 | - | 40 ± 16 | - | - | - | |
| wlmgun.wav | 33 ± 16 | - | 58 ± 34 | - | - | - | |
| wmmgun.wav | 18 ± 11 | - | 19 ± 14 | - | - | - | |
| wrhm.wav | 9.0 ± 1.8 | - | 8.0 ± 3.9 | - | - | - | |

- The **turret** carries most of the frame-rate effect: 152 /min at 8 ms, 69 at 30 ms, 11 under bw. Turrets fire
  through `entity_TickTurretFire` with fire skill 1.0 (ai.md), so their gate passes most often and the per-frame roll
  count matters most.
- **Missiles do not follow the frame rate** (8-10 /min at 8 and 30 ms): their rate is bound by something else
  (refire time, range, cone). bw's 5 /min is lower.
- The retail T13 loadout has no oil slick and different names; Gold's data retune (I76-VERSIONS 2.6) is consistent
  with that, not checked car by car.
- `emu\results\ai-damage-runs\wpn-parked.md`.

## 6. Our exe at 40 ms (step study grid point 1) - host cells e40 / f40

**Not run.** Both conditions were added to `aidr-host-run.ps1` (lab 8e051fd) and queued at 08:19, n 4 each,
interleaved. Each boot runs under `with-lock.ps1` plus an extra gate of 5 min without session input. The console lock
was held by the owner's OWNER-TESTS session (`f2-control`, pid 11876, alive) from 08:05. At about 11:19-11:25 another
lane (`lab-whole-sim-tick`) held it with its own game running, and by 11:35 the owner's lock text was back. No boot of
this lane started. The queue was stopped at 11:36 while it was only waiting (no lock held, no game of this lane
running). The e8 r5 / bw r5 top-ups queued behind it did not run either.

What the cells would answer, and how to run them (about 25 min of console for n 4 each):

    powershell -File C:\Users\james\i76-uncap-lab\tools\ai-damage-runs\aidr-campaign.ps1 -Conds e40,f40 -N 4
    python -I tools\ai-damage-runs\aidr_summary.py --phases ai "e40=captures\ai-damage-runs-20261017\t13-e40-r[0-9]" "f40=captures\ai-damage-runs-20261017\t13-f40-r[0-9]"

- **e40 vs r133 / gc166** (both stepping 37-40 ms): our exe at the step study's first grid point against the original
  exes at the same step.
- **e40 vs f40:** the same 40 ms physics step at 25 vs 120 rendered frames per second. If f40's AI rounds /min are near
  e8's, today's I76_FIXED_STEP leaves the AI fire roll per rendered frame (H5 fails for AI). If they are near e40's,
  it already ticks per step.

## 7. Melee2 (one AI car, player driven to the reference park position, then `ai` 60 s parked and `fire` 40 s)

n 3 per cell (one run each from the first session, two from the resumed one). Nobody died and nobody was killed in
any run.

| metric (`ai` phase, 60 s parked) | r166 | gc166 | r133 |
|---|---|---|---|
| step p50 ms | 26.7 ± 1.2 | 31 | 31 ± 1 |
| fps | 35.8 ± 1.0 | 31.8 ± 0.3 | 31.3 ± 0.7 |
| runs where the AI damaged the player | 3 / 3 | 1 / 3 | 2 / 3 |
| damage taken /min | 557 ± 112 (429..635) | 81 ± 140 (0..242) | 174 ± 240 (0..449) |
| AI rounds /min | 301 ± 271 (127..613) | 35 ± 61 | 76 ± 76 |
| hit events /min | 29 ± 14 | 1.7 ± 2.9 | 7.6 ± 10 |
| first damage s | 0.7 ± 0.8 | 42.4 (n 1) | 7.6, 35.8 |
| engagement m | 54 ± 6 | 38 (n 1) | 27, 36 |

- In melee2 the question is **whether the single AI car finds the player at all**, and that varies by exe:
  retail P166 3 / 3, Gold 1 / 3, retail P133 2 / 3 (Fisher p not significant at n 3). With damage taken in only
  6 of 9 runs, melee2 cannot carry a rate comparison. It confirms AI-DAMAGE-METRICS s.5.1: in melee the retail AI
  engages at the reference park position.
- In the `fire` phase (40 s, player holding fire) the picture is the same: rates spread from 0 to 1613 /min.
- `emu\results\ai-damage-runs\melee2-ai.md`, `melee2-fire.md`.

## 8. What this means for the step study (feeds PHYSICS-STEP-STUDY-DESIGN.md; does not redesign it)

- **E5 (retail AI and damage at the E1 configs):** P166 low and P133 low are in sections 2-4 at n 10 and n 8
  (pooled). The retail reference for B4 is therefore: damage taken 2314 ± 540 /min (P166), 2577 ± 986 (P133);
  time-to-die 36.3 ± 11.3 s (P166), 38.2 ± 14.7 (P133, one censored). Default detail and the developers' first-launch
  presets (E1's other rows) were not run for combat.
- **B4 feasibility.** From the measured cv (`pooled.md`, last table), detecting a 25 % difference with 80 % power
  (two-sided 0.05) needs per arm: damage taken /min about 14 (P166 cv 0.23; P133 cv 0.38 needs 37), time-to-die
  about 25 (cv 0.31), hit events /min about 24 (cv 0.31).
  Options, for the study owner to choose:
  1. keep B4 and budget about 25 emulator boots per reference cell (~3.5 h of one VM each) plus the same per T cell
     on the host (~2.5 min each);
  2. use damage taken /min as the B4 gate (n ~13) and report time-to-die as a watch row;
  3. lower the variance per boot: several shorter engagements per boot (repair or respawn the player between them;
     I76DRV has `repair`), giving k observations per boot.
- **H6 and the whole-sim tick (7.2).** Today's exe rolls AI fire per frame. Without the tick, fire volume moves with
  the render rate (2.3x from 30 ms to 8 ms frames). Under the planned whole-sim tick the roll runs once per tick and
  the frame-rate dependence goes away by construction; the 7.3 #4 read-back (per-frame systems once per tick) should
  include `ai_FireWeapons` 0x414ef0 and `entity_TickTurretFire` 0x462a90, counted per second.
- **The "fire rolls" part of I76_FRAMERATE_FIXES is not retail-like at the gold standard's rate.** bw rolls on a
  20-24 Hz grid; retail at P166 low ran 28-29 rolls/s and fired 2.4x as many AI rounds. The 7.2 note "fire rolls ...
  unneeded under this scheme" is right; until the tick exists, I76_REF_FPS / I76_AI_GRID_HZ would have to be retargeted
  to the reference rate (FIX-INVENTORY next step), not left at 20.
- **Fixed T near 30-33 ms matches retail P166 combat** in every measured metric (e30 vs r166). The band 27-<50 ms
  itself was not tested for AI except at 30 (and 40, section 6).

## 9. Not measured, and why

- **Player time-to-kill and player kills.** The parked player cannot aim. Needs a player-aim driver (I76DRV `drive`
  toward a target car and fire when the target is in the cone), listed as next by AI-DAMAGE-METRICS.
- **The AiO pd+0x10 recorder difference, live.** Not attempted: it needs the player to hit AI cars, which this design
  does not do.
- **Host firing equivalence.** The fire-byte poke is not a held key (section 1); a host fire run would need a key
  injection path that does not take the owner's foreground.
- **Gold at Wimp** (its shipped default, x2.0 player damage): not run here; it changes only what the player deals,
  which this design barely measures.
- **Behaviour shares** are in the per-run JSON (`ai_damage.py`) but the retail and Gold behaviour ids are not mapped
  to each other, so they are not compared.

## 10. Next

0. Run the host 40 ms cells e40 / f40 (n 4 each, about 25 min of console; section 6) when the lock is free.
1. Choose a B4 form (section 8) and size the retail reference accordingly.
2. Player-aim driver for time-to-kill (emulator and host), then T13 with the player fighting.
3. After L1 (whole-sim tick) lands: e40 / f40 again plus 60 vs 120 fps at fixed T (H5), counting fire rolls per second.
4. Map retail weapon sound names to weapon definitions (retail vehicle weapon records 0x566950) to replace the
   inferred pairing in section 5.
