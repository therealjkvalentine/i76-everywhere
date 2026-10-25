# Overnight run 2026-10-17 (evening) / 18: synthesis

Four lanes ran from about 17:00 on 2026-10-17 (workflow wf_62f32d56-c6a). The workflow was stopped before its synth step ran;
this record was written afterwards from the workflow journal (`results` and `verify:*` entries) and the lanes' committed records.
Three lanes finished and were verified; the fourth (tick-latency-and-ai-fire) was stopped at 00:35 on 2026-10-18 with no result
and no verifier. Every number below is the lane's figure **as corrected by its verifier**; where a verifier marked a claim wrong
or unsupported it is listed under "Corrected" or "Retracted". Nothing was pushed. The daily driver and the golden copy were not
touched (cursor lane verifier read the driver's md5s read-only). This synthesis ran no game and took no console lock.

## What did not run (read this first)

- **tick-latency-and-ai-fire: unfinished.** Its record has section 1 (input latency, s1.1-1.4) only. The `PHYSICS_ROWS` placeholder
  was never filled and there is no AI-fire section; no verifier ever read it. Its numbers below are the lane's own, **unverified**.
  Continued in `TICK-FINISH-2026-10-18.md`.
- **frame-replay-fix:** the rand() caller census and the srand-only control (n 2) never ran (console held by the owner's LAN test
  from 20:29, LAN game from 21:30). The claim "the melee car's motion draws from rand()" is therefore inference, not measurement.
- **same-car-and-fingerprint:** emulator-side mass (`ent+0xa4`) not measured (I76DRV does not log it; 1846 is a prediction from the
  loader formula); melee contexts not compared (no headless lab melee protocol); P133 T06 strip has only 5 reps from 3 boots.
- **cursor-on-18:** the rebuilt pointer fix was gated on the lab twin only. It was not promoted and not played by the owner.
- No lane produced a new "fixed" number for the physics step, handling, or AI. Promotion 18 stays held (see item 36 of
  OVERNIGHT-2026-10-16.md).

## Lane 1: cursor-on-18 ([CURSOR-FIX-ON-18-2026-10-17.md](CURSOR-FIX-ON-18-2026-10-17.md); main cc42cc5, 1255acd, 62931ff; lab c5c3a0e, 96aef3a, 6923d9d, 264a4eb; verify 823cef0)

- **Done:** the menu-pointer fix rebuilt on the proxy the daily driver runs now. New DLL 6850f968 = the 33211f11 source plus
  `cursormap.c` only (verifier: `diff -rq` shows only cursormap.c; CR-stripped file equals git HEAD music-fix/cursormap.c).
  Build is deterministic: a control rebuild is section-identical to 33211f11, and a second candidate build is section-identical
  to the first (pecmp masks only PE header / debug timestamps).
- **Gate on the twin with the driver's post-18 files** (n 2 per set, repeats identical; verifier re-ran `pencil-blob.py` on the 4 raw
  JSONs and got the table's numbers):
  - Pointer minus drawn pencil at 7 points: up to 242 px before, within 8 px after. Click within 1 px in both sets. (The 25 %
    after point at (0,0) used a 34x55 blob, larger than the usual 30x48; still within 8 px.)
  - Intro movie: union box x 1..2870 before, 1..2678 after in the raw JSONs; the frame counter sits at x 1 in both, so only the
    right edge separates 16:10 from 4:3. The after picture's left edge (about 760) is read from the capture, not the box.
  - Garage OK popup closed 5/5, arrow on the mapped point 4/4; proxy log DGV=ar lines n 2 (and n 10 in run 181147), CRASH lines 0.
  - Owner route (gate-folder through PLAY.bat, run 20261017-181224): 21 PASS, 0 FAIL, 2 INFO; Esc-menu Exit hit where drawn.
  - PLAY-balanced 2/2 and PLAY-16x10 2/2 at 120 fps (gates 182954 and 194209, PASS 5 FAIL 0). The first 16x10 gate (182725) read
    0/2: the gate harness set LAB_CURSOR_FREE on the mouse-capturing conf. The verifier did not re-check that root cause beyond
    the record and the commit.
  - No pencil is drawn over the in-mission Esc menu in either set (all 4 JSONs x 7 points: empty blob lists, OS arrow), so DGV=ar
    changes nothing visible there.
- **Staged files (4):** conf dccd379a -> aa6414e4 (`[DirectX]` Resolution 1680x1050 -> 1920x1440), best-wide 3922146a -> 6efc4c51,
  balanced 0bca8b31 -> 0c95b996 (DGV `1` -> `ar`); best-120 unchanged (9b53c141, no DGV key); STRLKUP 33211f11 -> 6850f968.
  The promotion proposal with rollback is section 4 of the record. Nothing was copied to the daily driver.
- **Test 08 roll-off (the extra item):** the car rolled about 16 m because the hill-top move ran while T05's opening still had the
  AI driving the car. Build hs2 (a091142d) waits for latch 0x5244c0 = 0. hs2 n 2 runs (4 placements): read-back 0.29 m / 0.61 m/s
  at 1 s (run 185459) and 0.29 / 0.27 m (run 191530, uncommitted file added by the verifier); 3.14 / 2.75 m at 3 s (run 185459),
  3.56 / 2.66 m (run 191530), against hs1's 15.9 / 16.3 m (n 1 run, 2 placements).
- **Corrected by the verifier:** (a) the intro-movie union box (above); (b) the cause section quoted hs2's placement (frame 412,
  24.25 m/s) as the old build's; hs1 placed at frame 725 from (8368.1, 27.7, 44517.4) at 25.00 m/s, read-back 5.22 m /
  10.68 m/s. The cause stands.
- **Owner tests (lane, with the verifier's wording problems):** 12-cursor-fix.bat (high, 5 min; promote yes / no on pointer feel
  and the 4:3 menu) and 08 hill start (medium, 5 min; also say if the ~14.6 s wait before the move is acceptable). Verifier notes:
  the 08 step should name `<lab>\OWNER-TESTS-2026-10-17\08-hill-next.bat`; the 12 step "DONE without an
  engine" should say to sell the engine in the garage first; the 12 header comment points at OWNER-FEEDBACK-FIXES item 3, cosmetic.
- **Open decision:** promote the 4 files or not. If yes, the game-night MP pack must be rebuilt (4 files change).

## Lane 2: same-car-and-fingerprint ([SAME-CAR-FINGERPRINT-2026-10-17.md](SAME-CAR-FINGERPRINT-2026-10-17.md); main 38721e0; verify 080594d, 696258b; lab 8d1189e, a2f546b, 306dba8, 926d9bb, dadfbf8, fa00bab)

- **Finding:** the lab's T05/T06 car was the wrong car. The lab booted the mission's own car (vppirna1, Jade's: 432ci SHO V8,
  engine power 193,960, armour 6080, mass 1951); the emulator runs load the save's Piranha (261ci 6 cyl, sway bars, 14 in Rally
  tyres, armour 9600, power 104,440). Verifier confirmed the emulator side from I76DRV `ent start` in r166 T05 (13 runs), r166/g166
  fpt06strip (3), r133low t05jump56 (8) and the 3 new P133 strip runs.
- **Fix (lab only):** a loose `ADDON\vppirna1.vcf` in new lab copy `game-samecar`. Read-back 9600 / 1846 / 104,440 in 37 of 37
  boots; control without the file 6080 / 1951 / 193,960 (n 1, `diag-step33-ctl1`). Mass 1846 was predicted by the loader formula
  before the runs (the 8d1189e message), so it is a prediction, not an emulator measurement.
- **Strip, same car vs retail P166 reference:** 0-20 m/s went from -34 % to +0.6 %, yaw -29 % to -1.6 %; t20 4.13-4.21 s vs retail
  4.18; steady yaw 1.099-1.116 vs 1.117 rad/s; brake 11.75-11.77 vs 11.88 m/s2. Verifier added a same-harness old-car control
  (n 1 boot each, lab boots near-deterministic): t06-step33-r1 t20 2.73 s, yaw 0.795 -> same-car t06-step33-s1 4.20 s, 1.10.
- **Per arm (P166 / P133 references):** tick66 passes every P166 accel / brake / yaw / T05 jump gate; step33 fails yaw (pooled
  -1.6 %, left -2.4 %); tick33 fails left yaw -1.7 % and T05 take-off -2.8 %. The tick33 take-off fail comes from 2 of 15 failed
  jumps (47.6 m/s, 103 m, turned over); its other 13 jumps read 50.57 like tick66. tick66 does fail T06 ramp air time and
  launch-pitch jounce vs P166.
- **T05 lip clip:** step33 4 of 24 placed jumps vs 0 of 30 for the tick arms, Fisher p 0.0336. Jumps within a boot are not
  independent; per boot 4/8 vs 0/10, p 0.023 (verifier recomputed from raw phys.csv, vy -0.65).
- **T06 ramp A flight short in every arm:** 0.33-0.47 s less air, same apex; not traced.
- **P133 vs lab arms:** P133 low wrecks 6 of 10 placed T05 jumps vs 0 of 15 in every lab arm (C(10,6)/C(25,6) = 0.0012). The P133
  and P166 references disagree on jounce and wreck rate.
- **Instrument bug fixed:** `fingerprint.py` dropped every lab brake sample (the impact test used interpolated sim_time). The
  verifier ran the selftest on a2f546b and HEAD: gate counts identical (55/5, 66/0, Gold 85/39, arcade 31/14), A/A tables identical.
  But 926d9bb changes 9 arcade-physics melee yaw rows (n 16 -> 18, verdicts same), so "emulator rows unchanged" is not strictly
  true. The brake-drop mechanism was not re-derived.
- **Corrected by the verifier (corrected values stated):**
  - strip match is within **3 %** on accel / brake / yaw (tick66 0-10 m/s 1.1333 vs 1.1678 = -3.0 %; step33aa +2.0 %), not 0-2.5 %;
  - step33 vs its A/A twin agree within spread, not to the printed digit (0-10 m/s 1.176 vs 1.192; apex_y PASS vs FAIL; tick66
    yawR sd 0.004, brake.dist sd 0.16); lab boots are near-deterministic, not sd 0.000;
  - P133 vs P166 strip within **1.8 %** (0-10 m/s 1.1466 vs 1.1678), not 1.4 %;
  - jounce: tick66 FAILs launch pitch and steer roll peaks vs P166 and passes them vs P133; vs P133, step33 / tick33 pass launch
    pitch (+5.9, tol 10.2) and fail only steer roll; every arm fails settle time vs P133;
  - tick33 T05 jump distance **217.2 m**, not 213;
  - T06 ramp A landing **9-18 m short** (30 m/s: 14-18 m, step33 -17.85 m); at 26 m/s foot speed FAILs at +1.7-1.9 % and no lab
    jump clears z 42800 (0/5 per arm vs 5/5, p 0.008).
- **Owner tests:** none queued by the lane. **Open decision (owner):** which reference governs where they disagree, P166 low or
  P133 low (wreck rate, jounce). This confirms the 10-16 headline row "T06 strip ... not a physics result: the lab boots a different car".
- **Consequence:** every earlier lab-vs-retail delta (ERA-ENVELOPE, retail-handling, LAB-FRAME-REPLAY T05 "lab car ~20 % faster")
  carried the SHO V8 car. They need re-reading with `game-samecar`; none has been redone.

## Lane 3: frame-replay-fix ([LAB-FRAME-REPLAY.md](LAB-FRAME-REPLAY.md) section 7; main d072513, 920ebe9, 1cc3b3c, 243ceea; verify 7aada05, 77d463e; lab f597ced, 6c8db03, a217407, abbe0fb, 1110444)

- **Item 51 menu navigation fixed.** `enter-melee`'s 1:1 clicks put the shell mouse at (0,104) for MELEE (447,311), so every menu
  click missed. New `tools\replay\melee-nav.ps1` checks each step against shell state and selects The Crater (the entry form had
  kept Air Base, AI drivers 01; now The Crater, AI 00). Reached "IN MISSION" in **16 of 16** runs since the fix, 14.4-15.9 s each
  (verifier: 15 console runs plus nav-debug-173311; three earlier debug runs failed).
- **A/A divergence and its cause:** Gold rep 1 A/A with the wall-clock wait: 63 of 1304 frames identical, first difference at frame
  709 (n 2 pairs); pre-roll alone the same (n 2 pairs, 173805 / 174548: 63); with pre-roll 150 + srand 1: **1304 of 1304 bit-identical
  (n 3)**. New opt-in switches `I76_REPLAY_PREROLL` and `I76_REPLAY_SRAND`. The exe seeds from the clock: `srand(time(NULL))`
  confirmed statically at <re-archive> 004a9020 and 004ad260 (log "srand calls 4").
- **Replays:** all 8 (Gold mloop reps 1-4, retail 1.0 simulation reps 1-4, each once): sim_dt bit mismatches 0, input bit
  mismatches 0, missing 0. Lab speed within 0.01 m/s of the emulator for the first 19-47 frames of the accel phase (n 8), over 1 m/s
  after 173-500 frames; end-of-acceleration speed differences Gold +0.27..+3.50 m/s, retail -0.91..+2.06 m/s (sign mixed).
  Early 0.01 m dpos is vertical: dy 0.01387, dh 8.37e-5 at frame 708 (verified on 192448).
- **Corrected by the verifier:**
  - the "throttle on" column is the accel-phase start; the first applied throttle comes 2-6 frames later (frames 708 948 969 998
    1131 1148 1155 1176), so counted from real throttle the 0.01 m/s threshold falls **17-43** frames in, max 0.004-0.018 m/s over
    30 frames; trace speeds at onset split **n 3 (5.3-5.6) / n 5 (11.4-12.1)**, not 4 / 4;
  - A/A first difference at 709 is the 2nd throttle frame and is dy **1e-6 m** (dx 9e-9 m), not 1e-9 m (173353 vs 173458);
  - **srand 3/3 is evidence, not proof:** run 173805 (pre-roll only; twin `mciproxy.log` has no "srand fixed" line for it) is alone
    1304/1304 identical to the srand-1 runs; the 4 no-srand runs gave 4 trajectories, one equal to seed 1;
  - "the melee car's motion draws from rand()" is **unsupported** (inference: census never ran); the record now says so.
- Builds f10b5cc5 / 8526ed31 read back; `music-fix/Strlkup.dll` still 509c6df0; twin STRLKUP back to 33211f11, no `.pretest`.
  Commit 1cc3b3c shows 590 changed lines in LAB-FRAME-REPLAY; with `-w --ignore-cr-at-eol` it is +9 / -1 (line-ending churn only).
- **Blocked / not run:** the census and the srand-only control (commands in LAB-FRAME-REPLAY 7.4; about 4 min under one lock).
- **Next:** run those two batches when the console is free; get the emulator's seed (log msvcrt holdrand in I76MEM or pin srand in
  the VM) so lab vs emulator can be compared bit for bit; steering comparison from steerprep replay files.
- **Owner tests:** none queued by the lane. (Item 51 of the 10-16 list, the first replay run, was done by this lane's agent runs; whether the item can be closed is the owner's call.)

## Lane 4: tick-latency-and-ai-fire (STOPPED, no result; [TICK-LATENCY-AND-AI-FIRE-2026-10-17.md](TICK-LATENCY-AND-AI-FIRE-2026-10-17.md); main 5e3fdba, 9f0460b, 28a59f6)

Not verified. The lane was stopped at 00:35 on 2026-10-18 while blocked on a wait file that vanished. What its partial record
holds (lane figures; a verifier has not checked any of them):

- **Static (AiO 6319abf7):** "sample every frame, apply at the next tick" cannot help: keyboard down bits are set at once by the
  window procedure and released bits cleared only after a poll, so the tick already applies the latest state; the latency is the wait
  for the tick (uniform 0..T). Not built.
- **Built (off by default):** `I76_SIM_TICK_INPUT=1` early tick on input (simtick.c): a key-state change runs the tick now,
  borrowed from the accumulator (at most one outstanding), so each tick is still exactly T. Drawing form 2 (28a59f6) blends from the
  would-be pose. Instrument `I76_SIM_TICK_DRAWLOG=<path>`. DirectInput devices (wheel, pad) are not watched.
- **Latency (mission T06, 40 steer-key toggles per boot, boots listed 2 + 2 per row, step33 reference 1 + 1):** key -> first sim step,
  pooled median / p90 / max: tick33 16.4 / 31.6 / 36.0 ms -> with input 4.1 / 7.9 / 8.8; tick66 32.8 / 58.7 / 66.7 -> with input
  4.3 / 8.0 / 9.0; step33 reference 5.9 / 15.2 / 16.7. Drawing form 2 (2 boots each): tick33 4.8 / 7.9 / 8.3, tick66 4.8 / 7.7 / 8.9.
  Early ticks per boot 26-37 of 40 presses. Correctness over 14 early-tick boots: 15.018-15.032 ticks/s at 66.7 ms and
  29.956-30.013 at 33.3 ms (plain 15.022-15.028 / 30.001-30.002), 0 leaks in 4,565-9,568 checks per boot, 0 outside writes, 30 of 30
  hooks live.
- **Draw smoothness:** heading second difference next to early ticks, tick66 form 1 median 0.416 deg, max 1.490 (1 boot, 76 frames);
  form 2 median 0.003 / 0.015, max 0.212 / 0.204 (2 boots, 70 + 68 frames); other frames p99 0.02-0.05 deg.
- **Missing:** the physics rows (placeholder `PHYSICS_ROWS`) and the whole AI-fire rate section. No claim about either exists.
  A drawn-pose lag of up to one tick remains in every tick arm (the early tick removes the wait, not that lag).
- **Owner tests:** none. Continued in `TICK-FINISH-2026-10-18.md`. The record file was untracked at stop; this synthesis commits it
  unchanged apart from one status line at the top.

## Other commits in the window (17:00-01:00), not from these lanes and not verified here

f0546ea promotion 18 applied (17:21; PROMOTIONS row 17, proxy 33211f11, dense variant); a95678a GAME-NIGHT-ROLLOUT-2026-10-17 + GAME-NIGHT.md
(17:49; LAN gate not passed: Mac hosted into the arena n 1, the PC lab copy saw no games with its firewall rule at Block); 3486331
REIMPLEMENTATION-ENGINE-PROPOSAL (20:49); dd8d3e3 wine-probe deskshot / find (00:31). Read them directly; their numbers are not repeated here.

## Retracted / corrected (verifier)

- cursor-on-18: intro-movie union box 760..2678 (raw 1..2678); hs1 placement quoted from hs2.
- same-car: strip match 0-2.5 % (3 %); "agree to the printed digit"; P133 vs P166 1.4 % (1.8 %); jounce-vs-P133 sentence; tick33 distance
  213 (217.2); ramp landing 9-15 m short (9-18 m); "emulator rows unchanged" (9 rows change); brake-drop mechanism not re-derived.
- frame-replay-fix: "throttle on" offsets (17-43 from real throttle); onset split 4/4 (3/5); A/A dy 1e-9 (1e-6); rand() use unsupported;
  srand 3/3 evidence not proof.

## Incidents

- The workflow was stopped before synthesis; the tick lane's wait file vanished (cause not investigated here).
- The console was held by the owner's LAN test from 20:29 and a LAN game from 21:30, which is what blocked two replay runs.

## Agent work for the next night (no owner needed)

1. Re-read the earlier lab-vs-retail deltas with `game-samecar` (ERA-ENVELOPE, retail-handling, LAB-FRAME-REPLAY T05).
2. Run the rand() census and srand-only control (LAB-FRAME-REPLAY 7.4); log the emulator's seed.
3. Trace the short T06 ramp-A flight (rerun with I76_TERRAIN_HULL_FIX off); confirm step33's lip-clip rate at n ~30 per arm.
4. Add `ent+0xa4` mass to I76DRV for one emulator run.
5. Finish the tick lane (TICK-FINISH-2026-10-18.md): physics rows, AI-fire rate, verifier pass.

## Commits

main: cc42cc5, 1255acd, 62931ff, 823cef0 (cursor); 38721e0, 080594d, 696258b (same-car); d072513, 920ebe9, 1cc3b3c, 243ceea, 7aada05,
77d463e (replay); 5e3fdba, 9f0460b, 28a59f6 (tick). Lab commits as listed per lane.
