# Overnight run 2026-10-16 / 17: synthesis

Nine lanes ran while the developer slept (user session disconnected all night; most evidence comes from headless 86Box par runs and
headless lab boots). Every number below is the lane's figure **as corrected by its verifier**; claims the verifiers marked wrong
or unsupported are listed under "Retracted" and are not findings. Nothing was pushed. The daily driver and the golden copy were
read only.

## Morning list (also appended to [../OWNER-TEST-LIST.md](../OWNER-TEST-LIST.md) as items 45-52, with notes on 1-2 and 36)

Ordered by priority, then minutes. Dropped as not owner work (verifiers): "more n for Gold's canyon kills" (a budget call agents can
settle), "which car the lab T06 gives" (an agent can read it), "ramp-lip clip by hand" (run the 31.75 ms preset headless first; the
check is already in item 42), "confirm the normal 86Box route" (owner disk sha256 unchanged), the separate arcade feel check
(folded into 45 / 44).

45. **Arcade Phys.: which setting is the gold standard? (decision, high, 5 min; new 2026-10-17; records/RETAIL-HANDLING-DIFF.md).**
    Every retail 1.0 emulator run before 2026-10-16 22:42 had Arcade Phys. **on** by accident (a Gold-layout `I76PLYR.DEF` read by the
    1997 exe). The stock default is off in both exes, and the emu runs since lab 0e2f16c are already off - nothing to switch.
    - **Read:** `docs\records\RETAIL-HANDLING-DIFF.md`, the Answer and section 5.
    - **Decide:** gold standard = retail 1.0 with stock options (arcade off), or do you remember playing 1997 with Arcade Phys. on?
    - **Feel it (optional, part of item 44):** lab twin `TEST-p166-retail-step.bat`, Esc > Options > Play Options > tick Arcade Phys.,
      fast corners and a roof landing; **untick it afterwards** (the game saves it to the twin's `I76PLYR.DEF`).
    - **Say:** "arcade off" or "arcade on".
1-2. **(existing items 1-2, now a short smoke test, high, ~10 min) Daily driver on promotion 16.** The driver has not been launched
    since 2026-10-08 07:43 (`mciproxy.log`), so promotions 15 and 16 are unplayed there; the long menu checks already ran on the twin.
    - Plug the wheel in, then `<games>\Interstate76-2026-10-03\PLAY.bat`.
    - Main menu > load a bookmark > garage > DONE; a quick look at one popup (click to close).
    - T05 over the barricades; T01 a few seconds of fire / ram for FFB.
    - **Look for:** clicks land under the arrow, barricades fly with one thud per hit, FFB as before, no crash. Rollback `_rollback\16`, then `_rollback\15`.
36. **(existing item 36, high, 20 min) Promotion 18 hold decision (C4).** Twin `<lab>\game-dd-20261003`,
    proxy read back 2026-10-17 = 33211f11 (the replay build that sat there at 22:40 is gone).
    - Play `TEST-hill-next.bat`, then `TEST-next-dense.bat` (both also carry the AI parity set).
    - **Look for:** signs fall when the bumper reaches them, the ground never vanishes on the hill descent, no hill-top stutter.
    - **Say:** lift the hold yes / no; bushes thin to 1800 m or dense to 300 m. (No P9 gate phase exists yet: an agent writes it after a yes.)
46. **Logged P166 play session in 86Box, retail 1.0 (high, 30 min; new 2026-10-17; records/EMU-OWNER-LOGGING.md).**
    Your own pbs-p166 machine on a logging copy of your disk; your `w95pb-hdd.img` is untouched (sha256 re-checked). The launcher
    refuses to start if the logging disk is already in use, so no pre-check is needed.
    - Double-click `<lab>\emu\PLAY-P166-LOGGED.bat` (disc 2 in the drive). If the game asks for disc 1 for
      a mission, close 86Box and relaunch with `PLAY-P166-LOGGED.bat --cd disc1`.
    - Start Interstate '76 from Start > Programs; 320x200, lowest detail; Options: **Arcade Phys. off**.
    - Play T05 to the canyon jump (or any mission). Exiting and restarting the game is fine (each start = one session).
    - Exit the game, Start > Shut Down, wait for "safe to turn off", close 86Box.
    - **Look for:** `<lab>\emu\results\memtrace\owner-<date>-<time>\summary.md` lists your session(s): retail 1.0,
      in-mission fps around 33-38, Arcade Phys. off, a "T05 canyon descent" line, the mission's music track. Report any "Cannot find
      file" dialog, an empty summary, or a game that feels slower than `run-vm.ps1 pbs-p166`.
    - **Caveat:** the launcher copies the logger from `emu\probe\out`, which is now I76MEM 2026-10-16b (commits the file every
      64 writes), not the 2026-10-16a build the self-test ran. Saves made here stay on the logging disk.
47. **GOG music file order by ear (medium, 5 min; new 2026-10-17; records/MUSIC-RETAIL-INTENT.md).** Any player:
    `<lab>\game\music\3.mp3`, `15.mp3`, `16.mp3`, `17.mp3` (the opening seconds are enough).
    - **Expected:** 3 = Interstate '76 Theme, 15 = Malochio Down, 16 = Skeeter Gettin' Medieval, 17 = Ovum Bisquit. Note any that differ
      (`I76_MUSIC_DISC_ORDER` rests on length matching only until you confirm).
48. **F2 orphaned bookmark: stock control vs the F2 shell (medium, 12 min; new 2026-10-17; records/BACKLOG-AGENT-ITEMS-2026-10-16.md U-05).**
    Twin `<lab>\game-dd-20261003`; saves are backed up and the shell restored automatically (md5 read back).
    1. `TEST-F2-bookmark-control.bat`: load any bookmark > garage > Options > Save Bookmark, type ORPHANA, click once on the empty
       paper right of the list (not a row or button), click the name field, type ORPHANB, SAVE, quit. Read the VERDICT.
    2. `TEST-F2-bookmark.bat`: the same with **ORPHANC / ORPHAND** - use these names even though the console text says ORPHANA / B
       (reusing ORPHANA brings up the overwrite prompt and muddies the comparison).
    3. `PLAY.bat` in the twin > Load Bookmark.
    - **Look for:** control prints ORPHAN, F2 prints OK; ORPHAND is in the load list, ORPHANB is not. Control printing OK = the stock
      trace is wrong; say so.
49. **Retail-intent music: the taste calls (medium, 15 min; new 2026-10-17; records/MUSIC-RETAIL-INTENT.md).** The gapless / pause log
    checks are agent work; only your ears are needed for the choices. Unmute the PC yourself.
    - `<lab>\builds\music-retail-20261016\MUSIC-RETAIL-TEST.bat` (retail mode; plays lab `game\`, swaps its
      proxy for the run and puts it back). Main menu 1 min (one short track looping), Options > Credits (another short one), back.
      Start a mission, choose Replay once (retail restarts the track from 0:00).
    - Then `MUSIC-RETAIL-TEST.bat control` and the same.
    - **Say:** which menu / credits music you prefer (1997 shell tracks vs today's run), and restart vs continue on Replay.
50. **Gold vs retail sliding at 25 m/s, in the emulator (medium, 15 min; new 2026-10-17; records/GOLD-STANDARD-FINGERPRINT.md).**
    The only behaviour where Gold misses retail: yaw while sliding +19 % at 25 m/s (n 12 vs 17), with Gold's held speed 3.9 % lower.
    Our exe has Gold's physics bytes, so this is the open handling question for our exe. Can share the sitting with item 46.
    - `<lab>\emu\PLAY-P166-LOGGED.bat`, Arcade Phys. off, Instant Melee: hold about 55 mph, full lock left
      and right a few times.
    - Again with `PLAY-P166-LOGGED.bat --cd gold`, starting `<gold game folder>\I76.EXE` from Start > Run (the Start menu may only list retail).
    - **Look for:** does Gold visibly slide out or spin more at the same speed and lock? Does it matter to you for "stock"?
51. **Instant Melee frame replays on the twin, first run (medium, 10 min smoke, then 20-40 min; new 2026-10-17; records/LAB-FRAME-REPLAY.md).**
    The only clean frame-by-frame exe vs emulator comparison (same default car), but the menus do not work headless. The script has
    never run: expect to debug it, not to measure.
    - Session connected, no other game running. From a cmd window:
      `<lab>\tools\replay\REPLAY-MELEE.bat -Conds g166-mloop-rep1 -N 2` (2 Gold replays). It takes over mouse
      and keyboard; hands off. If it stalls at a menu, note which one and stop it (Ctrl+C in the window) instead of waiting out 240 s timeouts.
    - If both finish: run `REPLAY-MELEE.bat` with no arguments (10 replays; the 6 retail ones replay arcade traces and do not count yet).
    - **Look for:** `tools\replay\runs\melee-console-<stamp>.txt`: Gold reps with "sim_dt bit mismatches 0", "input bit mismatches 0",
      and the first frame with |dpos| over 0.1 / 1 m (late = good).
52. **Watch one retail canyon descent (low, 5 min; new 2026-10-17; records/EMU-T05-CLEAN.md).**
    `<lab>\emu\results\writeup\video\retail-sim-p166-t05-clean-descent.mp4` (simulation physics, damage-free
    crest start). Optional: `...\emu\results\par\20261016-224007-r166-t05clean-a-1\video.mp4` is 8 descents in **arcade** (25 min; skim).
    - **Look for:** no pop or jitter at the placed start; does the jump look like your memory of the 1997 game?

## Headline: how close our exe is to the gold standard (retail 1.0, P166, Win95, software, lowest detail, simulation physics)

| metric | gold standard (n) | our exe / candidate (n) | status |
|---|---|---|---|
| physics step | 27 ms melee, 32 T05, 33 T06 strip, 35 T06 route (49 traces); follows the scene | driver fixed 41.67 ms (FIX-INVENTORY, not re-checked tonight); candidate env30 fixed 30 ms passes 0-3 of 5 step rows per context (simulated); context step lists pass 5/5 in their own context at n 3, 2/5 at n 11 | **no single profile can match**: retail's step is scene-dependent, ours is not |
| gravity | 9.8 x step | 9.8 x step (438 of 442 steps checked) | match |
| vehicle physics code | - | our i76.exe byte-identical to Gold at the lateral function, CheckImpact, vehicle init, option handler, StepVehicle (read-only compare); retail and Gold run the same algorithm | match (static) |
| handling constant K = yaw x v / steer | retail arcade off 31.59 (1 run, 398 frames, no A/A) | Gold 31.5-31.7 (5 runs); ours = Gold bytes | match; n 1 on the retail side |
| accel / brake / g / jump flight | fingerprint bands | Gold PASS on all | match (Gold; ours inferred from identical bytes) |
| yaw while sliding, 25 m/s | 1.03 rad/s (n 17) | Gold 1.22 (n 12) +19 % FAIL, held speed -3.9 % FAIL, yaw x speed +16 % | **open**; not measured on our exe (melee will not run headless) -> items 50, 51 |
| T05 placed 56 m/s take-off / apex | 51.6 m/s / 10.66 m (7 jumps) | stock exe at 31.3 fps 51.4 / 10.56 (33 jumps, near-deterministic); candidate env30 50.1 / 10.07 (33) FAIL | stock pacing matches; **candidate 3 % short** |
| T05 placed landing | retail 0/7 destroyed (Gold 3/7, p 0.19) | env30 0/33 turn-overs; step list seqt05 turned over in 5/7 boots vs env30 0/7 (p 0.02) | candidate clean |
| T05 ramp lip | 0 seen | 32 ms + frame-rate fixes + hires clock 19/99 (17 are one identical jump) vs 0/54 without; 0/45 at 30 ms | a 32 ms candidate needs the cause bisected first |
| T06 strip accel / yaw (lab exe) | t20 4.18 s (n 6), yaw 1.12 rad/s | lab t20 2.75-2.77 s (-34 %), yaw 0.79-0.80 clean (-29 %), ramp foot +10 %, equal in every profile | **not a physics result**: the lab boots a different car (lab strip accel = the retail melee default car, 1.06 / 2.76 s; emu T06 armour max 9600 vs lab 6080) |
| frame replay, T05 | trace sim_dt and inputs | forced bit-exact (0 mismatches over 23,960 frames); lab car ~20 % faster at every speed (n 10) | instrument works; comparison blocked by the car |
| music | retail rules derived statically (exe 6cc509ad) | proxy has 12 mismatches (chief: 0-60 s silence between songs); fixes built opt-in (`I76_MUSIC_RETAIL=1`, Strlkup-mr2 1b32e557), never run | open (items 47, 49) |

**Bottom line.** Our exe's physics code is Gold's, and Gold equals retail on everything measured except yaw while sliding. What is
left: pacing (no fixed step matches retail's scene-dependent step; 30 ms costs 3 % take-off speed), the unmeasured slide gap on our
exe, and a test-setup gap (the lab boots a different car) that blocks direct exe-vs-emulator handling numbers. The earlier "retail
turns about a quarter less than Gold" was the Arcade Phys. option, not code.

## Per lane

### emu-t05-clean ([EMU-T05-CLEAN.md](EMU-T05-CLEAN.md) s5-7; lab c77ec36, df772cc, 62186c9; main 8f602c9; verify f7c74ee)
- **Done:** I76DRV `place X Y Z HX HZ [MS] [SPEED]` and `repair`; a damage-free crest start (armour 5600 / 5600, chassis 4000 / 4000);
  `gen_t05jump.py` placed canyon jumps. Read-back: speed 56.00-56.03 m/s, lateral 0.00 in every placed run; at-rest crest placement 0.00 m.
- **Placed jumps 56 m/s, simulation physics, n 7 per exe** (arcade flag on 0 frames in all 14): take-off 51.62 +- 1.00 vs 51.20 +- 1.29 m/s;
  apex 10.66 vs 10.49 m; distance 228 +- 28 vs 248 +- 48 m; 6 far-side landings each (Gold's include two long ones at x 6560 / 6583);
  one face landing each. Peak pitch 53 +- 18 vs 80 +- 8 deg. Destroyed 0/7 vs 3/7 (Fisher p 0.19, not significant). Gold's 7 jumps
  are clustered (3 from one boot). sim_dt p50 30.2 vs 33.4 ms, but Gold's per-jump p50 is 29-36 ms, so the step confound is weak.
- **Retail ARCADE crest descents** (run 224007, n 8, one boot): foot 56.7 +- 0.7, take-off 48.4 +- 2.0, jump 145 +- 46 m, 2 flipped back, 0 destroyed.
- **Blocked:** stopping its own arcade run (permission classifier); no in-game crest save exists (bookmarks hold the scene, not a pose).
- **Next:** flat road / T06 ramp with `place SPEED` (template gen_t05jump.py); install the `place SPEED` I76DRV into `probe\out`
  (probe\out c3efb90f differs from the binary the runs used, bd6d7dd9; both report build 2026-10-16c).

### emu-fingerprint ([GOLD-STANDARD-FINGERPRINT.md](GOLD-STANDARD-FINGERPRINT.md); lab 04fa92c, 7e7c824, bb06e32, 3da24f4, 136d6fe; main 1b1beee; verify 788dab8)
- **Done:** reference `lab emu\results\gold-standard\retail-p166-low.json` (49 traces, 219 metrics, 20 rates, 3 fits, 0 arcade) and
  checker `emu\tools\memtrace\fingerprint.py` (boot variance component, Welch-Satterthwaite df). A/A boot halves: 2 of 126 gate rows fail (T05 step p5).
- **Gold vs retail sim:** accel, brake, g, flight PASS; yaw at 25 m/s +19 % FAIL (n 12 vs 17) plus held speed -3.9 % FAIL; 18 m/s +2.4 % PASS; T06 strip -0.4 % PASS.
- **Arcade retail** fails yaw -29.9 % (0.91 vs 1.30).
- **Lab env30 on the T06 strip:** t20 -34 %; yaw -29 % on clean samples (the checker's -20 % kept three rotated-start samples).
  Lab strip accel equals the retail melee default car exactly, so the car gap is the leading cause (not resolved).
- **Small issues:** the JSON's `meta.pass_rule` still describes the old sd-only rule; the checker should reject rotated-start /
  speed-collapse samples.
- **Next:** match the car; a third retail strip boot; static trace of Gold's slide branch; inverted-at-rest rollover check.

### lab-envelope-rebaseline ([ENVELOPE-RETAIL-REBASE.md](ENVELOPE-RETAIL-REBASE.md); lab c3828d0, 866d7b1; main a3a54b7; verify b3c325e)
- **Done:** 100 headless boots on the new lab copy `game-envrb` with side proxy cbcff703 (I76_STEP_SEQ, I76_HEADLESS_ACTIVE, I76_RH_DRIVE).
- Retail step medians as in the headline (n 49). The step list was followed in substance (verifier: 3,490 of 3,492 runs matched;
  the lane's 3,615 / 3,616 count was not reproduced exactly because the step_count column is 0).
- Strip handling rows equal within ~1 % across 6 profiles, all FAIL (the lab car). A/A seqpool / seqpoolaa yaw 0.794 / 0.794.
- T05 placed results as in the headline. Lost jumps: seqt05 8 of 33, seqpool 5 of 33. Take-off with frame-rate fixes at 32 ms: 52.1-53.4 m/s.
- Candidate unchanged at 30 ms; only its stated reason changes (the step at which our fix set lands T05 cleanly; 3 % short on take-off).
- **Blocked:** melee headless; I76_STEP_SEQ exists only in the side build.
- **Next:** split I76_FRAMERATE_FIXES / HIRES_CLOCK per site to find the lip clip; run the 31.75 ms `lab-p166-retail` preset headless
  (t05p + t05d) before anyone checks item 42 by hand; per-boot random list start, n >= 30.

### static-stepvehicle-diff ([RETAIL-HANDLING-DIFF.md](RETAIL-HANDLING-DIFF.md); lab c428b4e; main 3f468e4; verify 3f35a1a)
- **Found:** the retail-vs-Gold handling gap was a test-setup error. The retail launch copied Gold's 96-byte `I76PLYR.DEF`; retail
  reads 88 bytes with its flags at +0x54 = Gold bytes `01 00 8e 00`; bit 0 = Arcade Phys. -> entity flag 0x10000.
  Flag in 2,129 / 2,129 retail steer frames (6 runs), 0 / 1,203 Gold (5 runs); all 9 old retail T05 runs flagged.
- Lateral function identical (Gold / ours 0x43ce10, retail 0x4759b0): C = the grip limit A with arcade, 7.84 x contacts = 31.36 without.
  K retail 23.1-23.4 in 5 of 6 runs (first 21.15, slope), Gold 31.5-31.7. Arcade-off retail run 224135: K 31.59 (n 1, as predicted).
- CheckImpact with arcade flips an inverted resting car upright (183450 frame 13252, 183650 frame 13359).
- The earlier "Gold-only clamp / guard / 7.65 terrain damage" was a float-constant-scan artefact: retail has them as integer compares.
- Our golden i76.exe is byte-identical to Gold at every relevant site. **No handling patch.** Optional: front-wheel pull 0x3c341 `74 20` -> `eb 20`.
- Lab 0e2f16c had already switched the retail launch to a retail-layout DEF (22:42), before this doc was committed.
- **Next:** retail arcade-off A/A + Gold arcade-on (n >= 2, headless); re-measure braking / body reversals with arcade matched.

### lab-retail-handling (stood down; [LAB-RETAIL-HANDLING-STANDDOWN-2026-10-16.md](LAB-RETAIL-HANDLING-STANDDOWN-2026-10-16.md), written by the synthesizer)
- Duplicated the console lane (RETAIL-HANDLING-SWITCH.md, 151cf13). Builds rh1 73eb2cfd / rh2 0406e909 read back.
- **Verifier:** the switch was already committed; the agent ran a live T06 trial after reporting "no live runs" (flagpeek did not
  attach, so the switch was not shown working); **mute failed (0x80070490) and the game booted anyway** in an RDP-active session.
  `run-rh.ps1` has no mute / RDP guard: route it through `with-console.ps1` before reuse.

### lab-replay-mode ([LAB-FRAME-REPLAY.md](LAB-FRAME-REPLAY.md); main 5138677, c174331; lab 64e64b3, d08678a, c0f941c; verify b11d3d9, lab 6bedc60)
- **Done:** `I76_REPLAY` (music-fix/replay.c, off by default) + lab `tools\replay`; headless boots with nullglide / nullddraw
  (~1000 fps, 12-15 s per T05 replay).
- sim_dt forced bit-exact: 0 mismatches over 23,960 frames (12 runs) and in 11 clean-start runs. Inputs bit-exact until destruction.
  Lab A/A bit-identical up to the destruction frame (6/6 pairs; r05a + arcade 1,346 / 1,346).
- Emu vs lab, T05 clean starts (n 10): position off by > 0.1 m after 19-37 frames, > 1 m after 48-52; the lab car is faster at every
  speed (11.7-11.9 at emu 10 m/s, 37.0-37.6 at 30), against Gold and retail alike. Different car (max 9600 vs 6080, lab mass 1951):
  plausible, not proven.
- With the arcade bit held, the r05a replay survived the canyon 2/2; without it, destroyed inverted 2/2.
- **Blocked:** melee headless (`I76_MISSION=m01` creates no player; the menus ignore posted clicks).
- **Next:** build `.rpl` files from the retail sim melee loops (232325, 224135) so item 51's retail reps count; log the emu T05 car's mass (+0xa4).

### emu-owner-logging ([EMU-OWNER-LOGGING.md](EMU-OWNER-LOGGING.md); lab 245044e, b498fca; main 7c21a35; verify b98b18e)
- **Done:** `emu\PLAY-P166-LOGGED.bat` (owner's pbs-p166 config on `images\w95pb-hdd-memlog-20261016.img`, which differs only in
  WIN.INI), I76LOG, `owner_log.py` (collect, CSV, summary.md), `music.py`. Owner disk sha256 C8E7DA85 unchanged (re-hashed).
- Headless self-test: chain 4/4; logger missed 11-16 of 2,275-2,391 in-mission frames (0.46-0.70 %); all reads post-physics; the arcade
  check caught the Gold-DEF run (2,399 / 2,399) and read off in the 3 retail-DEF runs.
- Overhead unresolved: on 37.22 +- 0.13 vs off 36.70 +- 1.24 fps (n 3 each; off range 2.2; host 4-7 VMs). Three off runs failed.
- **Next:** overhead A/B n >= 4 on a quiet host; freeze I76MEM / I76LOG copies for the launcher (it now picks up the untested 2026-10-16b).

### static-music-audit ([MUSIC-RETAIL-INTENT.md](MUSIC-RETAIL-INTENT.md); main e025739, 31e7a90; verify 5e5bc9c)
- **Retail rules** (static, confirmed by the verifier): missions play N..14, tracks 15-17 alone; the watchdog polls 60 s in missions /
  5 s in the shell, then 2..14 forever; music level < 2 gates mission music; menus and movies pause / resume; Replay restarts the
  track. 1997 shell: menu 15, credits 16, never 17.
- The old retail traces' "playing 0" was the music-level gate (the Gold DEF gave music 0, SFX 0); the retail-DEF prediction holds in n 2 runs.
- 1997 CD vs GOG mission WRLD: 38/40 identical (T16 14 vs 7; S01 miss8 2 vs 1).
- Proxy: 12 mismatches; opt-in fixes `I76_MUSIC_GAPLESS`, `I76_MUSIC_TRUE_PAUSE`, `I76_MUSIC_MISSIONS=1997`, umbrella
  `I76_MUSIC_RETAIL=1`; Strlkup-mr2 1b32e557 built from e025739, never run.
- The old retail-vs-Gold fps comparison was not like for like (retail SFX 0).
- **Next:** agent log test of GAPLESS / TRUE_PAUSE with 5 s stand-in mp3s (n 2 each); retail-vs-Gold fps with SFX matched.

### backlog-refresh ([../BACKLOG-2026-10-16.md](../BACKLOG-2026-10-16.md), [../STATUS-2026-10-16.md](../STATUS-2026-10-16.md); main 7a542a9; verify d504057)
- Every 10-10 backlog row re-marked; 17 new rows X-01..X-17; 11 code items; OWNER-TEST-LIST status tags without renumbering.
- Driver: STRLKUP 509c6df0, u32x 06467bd2, shell a300db63; `mciproxy.log` last written 2026-10-08 07:43 (promotions 15 / 16 unplayed there).
- Promotion 18 held, no P9 gate. ENHANCEMENTS.md stale (0 of 8 recent switches).
- Twin STRLKUP: replaced by the replay build 8e37e9cb at 22:40 (verifier); **read again by the synthesizer 2026-10-17: 33211f11**, shell a300db63.

### backlog-agent-items ([BACKLOG-AGENT-ITEMS-2026-10-16.md](BACKLOG-AGENT-ITEMS-2026-10-16.md); 13 commits in main / lab / <re-archive>; verify 20fce6f, lab 391c18e)
- F-21 / R-15 verified (13/13 presets + PLAY-i76.ps1 = the driver's). H-06 memlib rename (ThrottleUp 0x5367D0, WeaponFire 0x5367DB,
  Hardpoint1Fire 0x5367DE; checked against the exe by the verifier). R-09 DOC-CORRECTIONS closed. X-16: all 117 switch names have
  README rows. R-16 lab tidy (11 run folders, 131 files, 417,557 bytes).
- U-05 F2: opt-in `--with-f2`; default output unchanged (8047c949); same bytes as the <re-archive> tool (6cd6b51f); emulation 5/5 vs
  control 0/5; a300db63 + F2 = 2ab4ca90 (58/58); staged on the twin (item 48).
- U-13 gate row D fix (the only failure in 10 past gate runs; checked offline). U-12: 6 menu scripts on MoveTo-UI / Click-UI;
  **`setup\equip-weapon.ps1` broke (MoveTo-UI not loaded); found and fixed by the verifier (lab 391c18e)**.
- pytest 241 -> 244 passed, 4 skipped (re-run by the verifier).

### Added after the synthesis: placed 56 m/s T05 jumps, Gold vs retail sim (duplicate emu-t05-clean instance; not verified)
A second instance of emu-t05-clean (started by accident when the coordinator relayed the Arcade finding) ran placed jumps
that the synthesizer never saw. Data: lab `emu\results\t05jump56-summary.json` (lab ae5a2c9), scripts
`emu\tools\par\scripts\ref-t05jump56-*`. Car placed on the canyon road at ~56 m/s, take-off x 6875 every run, placement
error 1.7-8.7 m, arcade flag 0 in every retail run.

| exe | n | foot m/s | air s | jump m | peak pitch deg | peak roll deg | wrecked |
|---|---|---|---|---|---|---|---|
| Gold P166 | 7 | 56.1 +- 1.2 | 5.2 +- 1.1 | 248 +- 48 | 80.1 +- 8.3 | 66.5 +- 30.1 | 3 |
| retail 1.0 sim P166 | 7 | 55.2 +- 1.6 | 4.6 +- 0.5 | 228 +- 28 | 53.4 +- 17.6 | 47.2 +- 19.2 | 0 |

- Pitch gap Welch t ~3.6; wrecks 3/7 vs 0/7, one-sided Fisher p 0.096 (suggestive only). Step p50 33.4 +- 2.8 (Gold) vs
  30.2 +- 0.4 ms (retail).
- **Caveat:** the Gold reps are in-session repeats; the ENVELOPE-RETAIL-REBASE verifier found that in-session placed jumps can
  replay identical jumps (b3c325e), so the effective n may be smaller. The versions-and-physics workflow (2026-10-17)
  re-measures this in its arcade-vs-sim and hardware-matrix lanes.
- The owner's own 2026-10-15 evening playtest ran on the Gold-CD VM (`vm\pbs-p166g`, config and disk written 19:26); his
  "too likely to flip nose down" matches the Gold column.

## Retracted (verifier: wrong or unsupported; not findings)
- emu-t05-clean: "1-step frames 96 / 97 %" (97 / 98 %); "placed kills agree in direction with the crest descents" (they do not);
  "queue ran 3 VMs at once" (evidence shows at most 2; the queue fix stands).
- emu-fingerprint: lab strip yaw -20 % / window speed 21.4 (-29 % / 27.9 on clean samples); "Gold 18 m/s n 15 from 6 boots" (5 folders).
- lab-envelope-rebaseline: Fisher p 0.004 for the seqt05 turn-overs (jumps not independent; per boot 5/7 vs 0/7, p 0.02); lip p
  0.0002 (17 of 19 are one jump); lost jumps 6 / 4 (8 / 5); take-off 52.2-53.4 (52.1-53.4); seqt05 at n 11 passes 2/5 rows;
  "g FAIL only under step lists" (the no-HIRES bisect profiles also read 9.52: the metric, not the physics).
- static-stepvehicle-diff: "7 retail runs" (6); "gen_scripts unchanged, tonight's retail runs carry the confound" (0e2f16c fixed it first).
- lab-retail-handling: "uncommitted"; "no live runs, no console lock"; "switch exercised live"; host muted.
- lab-replay-mode: "yaw bit-identical for the first 47-51 frames" (both 0 before the first steer; on the first steered frame the lab
  is 3-12 % higher); the placement dspeed row; dgVoodoo fault 0x475c36 not in this lane's log (corroborated only by be5e594); the
  m01 bptrace output is not on disk.
- emu-owner-logging: "two failed off runs" (three).
- static-music-audit: "n = 1" (n 2); "17.mp3 is the Theme" (it is Ovum Bisquit; the Theme is 3.mp3).
- backlog-refresh: twin STRLKUP 33211f11 and H-06 open (both went stale within minutes; see above).
- backlog-agent-items: "all 6 U-12 scripts work" (equip-weapon broke; fixed); 415 KB (408 KiB).

## Incidents
- **Audio:** lab-retail-handling booted the game after `mute.ps1` failed. Other lanes found no default endpoint while the session
  was disconnected; the 86Box VMs ran with `sound_muted = 1`.
- **VM cap:** emu-t05-clean's queue read the python stub's instant exit as "done" and started boots 2 min apart (at most 2 of its VMs
  overlapped per the verifier); fixed. emu-owner-logging saw 4-7 VMs on the host from all lanes together (cap 4).
- **Duplicate lanes:** emu-t05-clean overlapped another T05 lane (sections 1-4 vs 5-7); emu-owner-logging had a duplicate agent
  (a9ac35d722aaf0823) editing its files; lab-retail-handling duplicated the console lane.
- **Other commits tonight, not covered by these verifiers:** EMU-MEMTRACE s9 (8e30fa9), EXE-DIFF-MAP (5681fe9), I76-VERSIONS
  (a2cef55), FIX-INVENTORY-2026-10-17 (5665c53). Read them directly; their numbers are not repeated here.

## Agent work for the next night (no owner needed)
1. Match the car: phys-suite T06 on the emulator's save (or read the lab player block), then re-run fingerprint compare and the 10 T05 replays.
2. Retail arcade-off melee A/A and Gold arcade-on (n >= 2 each, headless).
3. Headless 31.75 ms `lab-p166-retail` preset on game-envrb (t05p + t05d), then the per-site bisect of the lip clip.
4. Sim-melee `.rpl` files (232325, 224135) for item 51.
5. Music GAPLESS / TRUE_PAUSE log test with stand-in mp3s (n 2 each).
6. Freeze the tested I76MEM / I76LOG for PLAY-P166-LOGGED (or self-test 2026-10-16b); fix `meta.pass_rule` in the reference JSON.
7. After a yes on item 36: P9 gate phase + TEST-promo18.bat. ENHANCEMENTS.md refresh.
