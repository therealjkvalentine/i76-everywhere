# Owner test list (things only James at the console can check)

Kept current by the agents; newest additions at the bottom of each section. Lab copy = `C:\Users\james\i76-uncap-lab\game-dd-20261003`.
Daily driver = `C:\Users\james\Games\Interstate76-2026-10-03`. Audio may be muted by the agents: `i76-uncap-lab\tools\mute.ps1 -Off`.
**Morning summary 2026-10-16: [OWNER-MORNING-2026-10-16.md](OWNER-MORNING-2026-10-16.md)** (what is still untested, ready-to-promote
candidates, your open decisions; ordered by value, each with its launcher and time).
**Status marks 2026-10-16** ([BACKLOG-2026-10-16.md](BACKLOG-2026-10-16.md)): items closed or replaced carry a `[DONE ...]`,
`[OBSOLETE ...]` or `[RETIRED ...]` tag with the evidence; numbers are unchanged. Untagged items are still open.
**Overnight 2026-10-16 / 17: [records/OVERNIGHT-2026-10-16.md](records/OVERNIGHT-2026-10-16.md)** (the morning list in one
place: new items 45-52 at the bottom, plus items 1-2 and 36; the headline on how close our exe is to the gold standard).

## Before bed (the overnight agent run)

0. **Before bed: run `tools\rdp-to-console.cmd` (ends Remote Desktop, hands the session to the console) and tell the agent; it runs
   `autotest\overnight\run-overnight.ps1`** (lab repo `C:\Users\james\i76-uncap-lab`, README beside it). Unattended, about 2.5 h: the
   automatable parts of items 3, 5, 6, 7 (step 1, the loader proof), 8 and 16 plus regression drives of the three daily-driver presets,
   all on lab copies; results in `autotest\runs\overnight-<ts>\summary.md`. Close the trainer GUI (`_tools\trainer\i76trainer_gui.py`)
   and anything else reading telemetry first: it holds the shared memory at the old size and the new proxy cannot use it. The run leaves
   the audio muted (`i76-uncap-lab\tools\mute.ps1 -Off`).
   **First run 2026-10-11 + same-evening follow-up: [records/OVERNIGHT-2026-10-11.md](records/OVERNIGHT-2026-10-11.md)** (per-phase
   verdicts, the harness bugs it exposed and fixed, what is still yours). Items marked *(automated 2026-10-11)* below were covered
   by it; only the parts that need eyes, ears or hands remain.
   *(2026-10-16: phases P1-P8 exist (P8 was the promotion-16 gate, 2026-10-12). Promotion 18 has no gate phase yet: P9 is
   not written.)*

## Daily driver (already promoted, confirm in normal play)

1. **Mouse in widescreen (promotion 15, 2026-10-08).** `PLAY.bat`. Main menu, TRIP / LOAD BOOKMARK, garage Build & Repair:
   DONE with no engine -> the "CAN'T GET VERY FAR" popup: a small arrow should follow your hand over the frozen picture; OK closes it
   (click, Enter or Space). Save Bookmark screen: overwrite prompt Y/N. In a mission: Esc menu items and Exit. Same with `PLAY-balanced.bat`.
   Anything odd -> rollback is `_rollback\15` (five files).
    - **Owner smoke test 2026-10-17 (daily driver, promotion 16, keyboard): menu pointer does not quite match the click location (being fixed: records/OWNER-FEEDBACK-FIXES-2026-10-17.md); T05: drove THROUGH the first two road signs, hit most of the others; knocked most but not all barricades; jump distance and pitch "just about perfect"; terrain still drops out when the camera gets low (G-01; promotion 18's I76_TERRAIN_HULL_FIX targets it); FFB not tried yet.**
2. **Force feedback after promotion 15.** The gate had no wheel plugged in. Plug the wheel in before `PLAY.bat` and confirm FFB feels as before.

   *(Items 1-2 still open 2026-10-16: the driver's `mciproxy.log` was last written 2026-10-08 07:43, so promotion 16 (collision G,
   roads 1800, 2x SS, I76 Debug; rollback `_rollback\16`) is also unplayed there. The promotion-16 gate also ran with no wheel.)*
   *(2026-10-17 morning list: cut to a ~10 min smoke - wheel in, `PLAY.bat`, bookmark > garage > DONE, one popup, T05 barricades,
   a few seconds of T01 fire / ram for FFB; the long menu checks already ran on the twin. records/OVERNIGHT-2026-10-16.md.)*

2b. *(Promotion regression automated 2026-10-11, P7: best-wide / best-wide-balanced / best-120 on the twin each boot and drive t04
   90 s at 120 fps, no CRASH line; the twin's presets are byte-equal to the driver's.)*

## Lab copy (candidates, not in the daily driver)

3. **[DONE 2026-10-12: promoted as collision G in promotion 16, PROMOTIONS row 16 / `7bfdf68`; the TEST-coll bats are in the
   twin's `_archive-2026-10-12`.]** **Collision fix A/B.** `TEST-coll-A-control.bat` (= your PLAY.bat) vs `TEST-coll-B-window2.bat` (I76_COLL_WINDOW=2 + dedupe).
   T05 (Taurus jump mission) roadblocks, cars, buildings: does B hit what A drives through? Anything new and wrong in B (snagging on
   scenery, odd bumps, getting stuck, doubled crash sounds)? `TEST-coll-C-24fps.bat` = 24 fps reference (choppy on purpose; stock-like collisions).
   Measured offline: barricades contacted 36/36 with B vs 8/28 with A.
   *(automated 2026-10-11, P1:* rams w2 21/21 vs control 10/43 (A/A p 0.49); gate with B staged on the twin 21/0. **New finding:**
   in t04 god-mode circle drives B destroys the car at one spot about 9.5 s / 250 m along the circle (5 of 23 passes; A 0 of 21,
   p 0.05; elsewhere deaths are equal). While playing B, watch for being killed by something you barely touched; t04's start area
   is where the drives found it. Details: records/OVERNIGHT-2026-10-11.md, P1.)
   *(2026-10-12, the t04 deaths are a stock terrain rollover, not B: lab docs/COLL-WINDOW-DEATH-SPOT-2026-10-11.md.)*
   **3b. [DONE 2026-10-12: owner chose G; bats archived.]** **Barricade timing from the T05 hill top (new 2026-10-12, your "hit before you run into them" report).** Seven bats, each
   boots T05 straight in and drops the car on the crest of the road down to the barricades, standing, facing down the hill
   (about 1 s after the mission appears; if it does not move you, the log says why):
   `TEST-hill-A-control` (window off) / `-B-window2` (as TEST-coll-B) / `-C-stepframe` (B, but the check only on the frame the
   car actually moves) / `-D-scale075` / `-E-scale050` (B with a shorter window) / `-F-window2-nointerp` (B without render
   interpolation: choppy on purpose) / `-G-stepframe-barbox` (C + the bar collides as the real bar; experimental, never run).
   Compare: does the barricade fly before the bumper touches it (expect B worst, C and F better, G on time)? Any barricade
   driven through (expect A most, D/E some, B/C/F/G none)? Signs: with B/C, a sign you pass within about 1 m of should fly.
   Why it can never be fully "on time" without G: every barricade bar collides as a 3 m ball around its middle, in stock too, so
   it flies when your nose is 3 m short. The timing part is about 1.3 m at 60 mph in B and 0.6 m in C.
   Lab docs/COLL-TIMING-2026-10-12.md. *(Built and checked offline only; not run before handing over.)*
   *(2026-10-12, owner: **G accepted** - "G is fantastic ... we should keep G if it doesn't break anything"; only a few signs, e.g.
   "the highway 360 one", took about 10 rams.)*
   **3c. [OBSOLETE: H never chosen; replaced by items 35-36 (`I76_BREAKABLE_BOX=3`, then `=4`); bat archived.]** **Sign fix - try `TEST-hill-H-signfix.bat` (new 2026-10-12).** = G + `I76_BREAKABLE_BOX=2`. The "360" sign is almost certainly
   a US 380 shield (the 380 reads as 360 in that font); its post is the same shape as every other shield. A sign is knocked down by
   the score of the ram measured only along the side of the car the post touched first: rammed straight on it falls, but when you
   swerve off the road at it the post comes in along the car's side and scores a few % (the US 380 shields in T05 stand 8-10 m out,
   further than most signs). H scores every ram on your full speed. Ram the US 380 shields (and anything G would not drop) from the
   road at an angle at normal speed: each should go down at the first ram (very slow nudges still do nothing, as in stock). Also
   check the barricades still behave as in G. Proof: `mciproxy.log` lines `breakable-speed: 1/1` and `breakable-speed: class-4 hit ...`
   ("glancing" marks a ram stock would have scored low). Lab docs/SIGN-FIX-2026-10-12.md (also the whole-game audit of the bar box:
   only the T05/T06/T15/S03 barricade bars and one T08 sign panel are affected). *(Built and checked offline; not run.)*
   **3d. [DONE 2026-10-12 17:45: gate P8 run, applied as promotion 16 (the widened owner-verified set, proxy `509c6df0`), `7bfdf68`.]**
   **Promotion of G to the daily driver: pending the console gate.** `tools\promote-17-collision-g.ps1` (proxy `a6d621fd`, best-wide /
   best-wide-balanced / best-120 + the four G keys, launcher `009c9742` with head tracking opt-in) refuses until the gate has run:
   lab `autotest\overnight\run-overnight.ps1 -Phase P8` when the console is free (about 3 h: gate 23 rows + row 3 via PLAY-16x10 and
   PLAY-balanced, T05 barricade rams G vs control n>=21, 8+8 t04 drives, hill-top start). Dry run 2026-10-12: 15 DRY / 3 PASS / 0 FAIL.
   If you try H and like it better, say so before the gate: the promotion would then carry `I76_BREAKABLE_BOX=2` instead of `=1`.
4. **[OBSOLETE: replaced by item 34 (the hull mechanism and `I76_TERRAIN_HULL_FIX`); `TEST-terrain-watch.bat` is in the twin's
   `_archive-2026-10-12`.]** **Terrain drop-out watch.** `TEST-terrain-watch.bat` = PLAY.bat + drop detector. Play where you saw it (open desert, road bend). If the
   ground vanishes, note the time; the log (`Interstate 76\mciproxy.log`, lines `TERRAIN-DROP`) and a saved frame tell us the rest.
   Expected: never (the lab copy lacked I76_CAM_GROUND_FIX when you saw it; your driver has it).
5. **`PLAY-stock.bat` textures (daily driver).** Flagged 2026-10-10 by the preset-sync agent: it runs preset `stock` (no
   I76_ZGLIDE_TMUFIX) on `dgVoodoo.16x10.conf`, which has MemorySizeOfTMU 8192 since promotion 11; 4096+ without TMUFIX gave
   "texture exchange issues" in promotion 5R. Launch it briefly: wrong / swapped textures on terrain or cars = confirmed (fix: give
   PLAY-stock its own conf at 2048, a small promotion). Low priority if you never use PLAY-stock.
   *(automated 2026-10-11, P5: no signal.* 4 interleaved t01 runs on the twin, TMU 8192 vs 2048 proven by the census (8,191 vs
   2,047 KB usable); FLUSH / rewinds / downloads equal, image A/B difference within A/A. Captures in lab
   `autotest\runs\overnight-20261011-204548\P5\tmu*`. A 36 s throttle run is thin: a few minutes of real PLAY-stock play still decides.)
6. **Haptics telemetry v3 (sound / damage events), not installed yet.** Built 2026-10-10 as `music-fix\out\Strlkup-tel3.dll`
   (static-verified only). A console agent installs it in the lab copy first (keep the old `Strlkup.dll` beside it), then runs it with
   `I76_TELEMETRY=1 I76_SOUND_EVENTS=1 I76_DAMAGE_EVENTS=1 I76MUSIC_LOG=1` and `python tools\telemetry\i76tel.py --check` alongside.
   Pass: `mciproxy.log` shows `telemetry: on ... 4/4 event hooks`, `sound-events: on - stop taps 4/4 ... start tap on ... weapon-UI clicks 3/3`
   and `damage-events: on`; the listener prints one `SOUND+` per sound you hear (own guns `PLAYER`, an AI car's `other` with a position),
   a `SOUND-` when a skid ends, `WEAPON-UI cycle/link/unlink` on those keys, and `DAMAGE` with the side you were hit on (rammed from the
   left = `side left`). Anything wrong in the game itself (missing or doubled sounds, stutter, a crash) = fail; revert to the old DLL.
   *(automated 2026-10-11, P2: PASS 24/24* on a copy of the twin, t01 + t05 scripted: all three log lines, clean v3 `--check`
   (2,904 / 2,906 frames, 0 gaps), SOUND_START PLAYER + other with positions, SOUND_STOP, WEAPON_UI cycle, DAMAGE_SIDE, no CRASH.
   Left for you: the in-game half - does anything sound missing or doubled, any stutter - since the run was muted.)
7. **HD sound pack A/B (`tools/soundhd`, pack v1, NOT installed anywhere yet).** An agent installs it into the lab copy first
   (`soundhd.py install --game <lab copy>` dry run, then `--apply`; it refuses anything outside `i76-uncap-lab\game*`, never overwrites
   your ADDON mods, and `uninstall --apply` removes exactly its 123 `.gpw`). Step 1 is the loader proof: blow up a car, and the
   explosion should play from the pack (16-bit 22 kHz). If it sounds exactly like stock, say so: that means loose ADDON `.gpw` are ignored.
   *(Step 1 automated 2026-10-11, P4: PASS, twice.* A marked `wmflame.gpw` in ADDON (header priority +7, tone at 1.5x rate): all 42
   flamer SOUND_START moved from priority 89 to 96 and from 11,025 to 16,538 Hz, controls unchanged; uninstall restored ADDON by
   md5. Loose ADDON `.gpw` are loaded. Skip step 1; the A/B by ear below is still yours.)
   Then A/B the same mission with the pack on and off (t01 or t04), on the speakers you normally play on:
   - Ram cars and buildings at speed: the hit has weight (a low drop under it) but is **not louder** than stock. Any pumping or crunch?
   - Fire the MGs (hold the trigger), a cannon and rockets: a thump per shot, and the MG loop stays seamless (no tick, no drone).
   - Idle, then rev to the limiter: more body at idle; listen for flutter or a tick at the loop point and anything odd at high rpm.
   - Ignition, healthy and damaged: the low end on the engine catching, not on the cranking.
   - Horns and sirens: fuller, not distorted (these are the most limited files).
   - Skids, gravel, CB voices, menu sounds: should be **unchanged**.
   - Eyes closed: is the balance of CB vs engine vs weapons the same as stock?
   Report per sound if you can (the names are in `tools\soundhd\out\pack-v1\report\index.html`, with a spectrogram for each).
   Transducer stem test: the haptics host now plays `pack-v1\lfe\` on SOUND_START; see item 16.

## Haptics host (tools/haptics, Phase C of docs/HAPTICS-ARCHITECTURE.md; lab copy, A/A before A/B, report n)

8. **Record a real telemetry session.** Lab game with `I76_TELEMETRY=1 I76_SOUND_EVENTS=1 I76_DAMAGE_EVENTS=1`; in a console
   `tools\haptics\haptics.ps1 record --udp --out tools\haptics\replays\t01-c1.i76rec --seconds 300`; drive t01, shoot, hit a wall,
   jump, get shot. Then `haptics.ps1 decode <file> --events`. Expected: v3 frames; SOUND_START is_player 1 for your weapons, 0 for an
   AI car's; DAMAGE_SIDE on hits. The file replaces the scripted session as every offline test's input - keep it.
   *(automated 2026-10-11, P2 + P3: two scripted v3 recordings* (lab `autotest\runs\overnight-20261011-203304\P2\t01.i76rec`,
   `t05.i76rec`, 2 MB each, decode clean) and P3 replayed the first run's t01 through every file sink with the motion validator
   14/14. Not committed here: copy one to `tools\haptics\replays\` if a scripted drive is good enough as the reference; a
   5-minute session of your own driving is still the better input.)
9. **Wheel + pad + shakers together.** `haptics.ps1 live --source udp` (files only) for one drive, then the same with `--live` and all
   three devices connected. Only question: interference or dropouts (feel comes later).
10. **Latency.** `--live --record` run: fire one shot, ram one wall, phone microphone on the shaker; event frame vs shaker onset.
11. **Wheel coexistence.** Host holding the wheel (`--live`), pull the trigger: does the game's own FFB still play anything?
12. **Hardpoint +0x10.** Same weapon aimed two ways with `tools\ffb\ffb-watch-effects.ps1`: firing frequency or direction?
13. **Explosion reach.** An AI car explodes nearby: EXPLOSION distance vs any concussion kick; sets `explosion.blast` reach_m.
14. **Effects one at a time.** `haptics.ps1 preview --effect <id> --live --sinks pad,lfe` for impact.collision, landing,
    weapon.fire, slip.grip_limit: does each read as what it is? (Devices move: owner present.)
15. **Feel session.** `python tools\haptics\design\report.py` open on a second screen; edit one effects\*.json at a time while
    `haptics.ps1 live --live` runs (hot reload), two laps per change.

## Fresh install (installer; blocks v1.1.0, backlog R-04)

16. **Fresh folder -> PLAY-i76.bat -> trip route.** Offline half done 2026-10-10 (docs\records\FRESH-INSTALL-CHECK-2026-10-10.md:
    six scratch installs, every file and md5 as expected, game never started). At the console (not over Remote Desktop: the setup
    sizes dgVoodoo to the display it sees), with no `C:\GOG Games\Interstate 76` yet: double-click `INSTALL.bat` (one UAC prompt for
    GOG's installer; it also installs the Nitro Pack into `C:\GOG Games\Interstate 76 Nitro Pack` unless run as
    `INSTALL.bat -SkipNitro`). Then the desktop shortcut / `PLAY-i76.bat` (preset best-120 on GOG 2.1.0.17's exe `9a232dcc`, which no
    preset has run on): PLEASE STAND BY, Esc past the intro, no dgVoodoo watermark or 4:3 picture; main menu pointer lands where you
    point; TRIP -> garage -> DONE with no engine -> the popup closes with a click; LOAD BOOKMARK any of the repo bookmarks
    -> in the mission: smooth 120, music playing, no flips on bumps; Esc -> Save Bookmark -> overwrite prompt Y/N -> back to the
    menu. Afterwards `mciproxy.log` in the game folder should list the switches as applied, not skipped. Optional: the same with
    `-Preset best-wide` (`PLAY-i76.bat`, `PLAY-balanced.bat`, `PLAY-16x10.bat`). Fail = skipped patches, a watermark, the mouse off in
    the menus, or no music; `install.ps1 -GameDir "C:\GOG Games\Interstate 76" -Preset stock` is the way back.
    *(boot automated 2026-10-11, P6: PASS 7/7* - offline setup at the console, PLAY-i76.bat -> TRIP -> bookmark -> mission at 120 fps
    on `9a232dcc` with best-120, no switch skipped, PLAY-stock control up too; records/FRESH-INSTALL-CHECK-2026-10-10.md, last section.
    Expect two log lines on this exe that are not faults: `CRASH: code 0xC0000096 at ... exe+0x99997` (the 1997 CPU-speed probe,
    handled by the game) and `NOTE: this exe has no WINMM.dll import` (GOG's own WIN32.dll plays the music, the proxy's music fix
    cannot attach). Still yours: the real `INSTALL.bat` with GOG's installer and UAC, **whether music plays in a mission** on this
    build, best-wide on it, a Save Bookmark.)

## Motion simulator output (tools/haptics/motion, docs/MOTION-OUTPUT.md; desk benches need no hardware and no game; A/A before A/B, report n)

Setup steps in detail: `tools\haptics\motion\README.md`. Scenario times count from the start of each scenario; the host
holds neutral for the first 3 s. Nothing here was installed or run by an agent.

17. **FlyPT Mover desk bench (install it, then replay).** Download FlyPT Mover 3.5 or 3.7 beta from flyptmover.com (free),
    unzip outside any game folder, add the **Live For Speed** source (OutSim 4123, ID 1, OutGauge 4124), a **6DOF**
    virtual rig, open its **3D view**, map surge / sway / heave / yaw / pitch / roll to the source outputs (write down
    Mover's names for them). Then `tools\haptics\haptics.ps1 motion all --targets flypt --send`. The source should turn
    green. Expected on the virtual rig: **braking** (5-7.6 s) nose-down then back; **accelerating** (4-9 s) nose-up;
    **turn** pushed left during the right turn (4.5-7 s) and right during the left turn (7.5-10 s), with yaw;
    **crest** a small heave kick ~5.4 s; **jump** still in flight (5-6.2 s), one heave kick on landing; **impact** one
    sharp jolt at 5.0 s and a small kick at 7.5 s (explosion); **dropout** settles smoothly to neutral at ~5.3 s and
    comes back after 7 s (never a jump). Screenshots of the 3D view and the source graphs go in
    `docs\records\MOTION-BENCH-<date>.md`.
18. **T2 - LFS frame world or body.** Same bench, `tools\haptics\haptics.ps1 motion braking --targets flypt --send --repeat 5`
    (the braking runs at heading 30 deg). Straight-line braking must be **pure pitch, nose-down**. Pitch and roll
    together, or nose-up, means the frame is wrong: set `"frame": "body"` on `flypt` in `tools\haptics\motion\targets.json`
    and repeat. Report which one gave pure nose-down pitch.
19. **SimHub desk bench.** Install SimHub (free), game **Live for Speed** (OutSim 63393 / OutGauge 63392), then
    `tools\haptics\haptics.ps1 motion all --targets simhub --send`. Check: speed / rpm / gear read sensibly (gear 2 on
    the wire = 1st), the motion add-on's **3D preview** does what item 17 lists, ShakeIt preview with no audio device
    (or the EVO 4 only while you are at the desk). SimTools only if you own a licence (the free DIY licence ended
    May 2026): Network interface 127.0.0.1:6123, Default axis profile, `--targets simtools`, close Mover first (both use 4123).
20. **T3 - Forza in SimHub.** Game **Forza Motorsport 7**, note the UDP port SimHub shows (5300 assumed; change
    `simhub-forza.port` in targets.json if not), `tools\haptics\haptics.ps1 motion all --targets simhub-forza --send`.
    Gear / speed / rpm right? (One gear too many = Forza counts gears differently: say so.) Does braking show as
    deceleration and the right turn as a rightward / outward g in SimHub's view? Those settle the Forza sign convention.
21. **T1 - signs from the real game (lab copy, after item 8's recording works).** `I76_TELEMETRY=1`, then
    `tools\haptics\haptics.ps1 live --source udp --sinks motion-udp` (files only) while driving t01: launch, full brake,
    a right-hand corner, the T06 ramp (aaramp5), a wall. Then
    `python tools\haptics\motion\i76motion.py --plot tools\haptics\out\live\live.native.i76motion.i76rec t1.html`.
    Expected: surge about -9.5 while braking, pitch nose-down (~-3 deg), sway positive in the right-hander with yaw rate
    positive, heave cue only at the landing, a surge cue at the wall, physics channels flat in the air. Anything with the
    opposite sign (especially surge or yaw) = the engine's accel_body / yaw_rate convention differs: report which.
22. **T4 - interp vs hold.** Two identical braking runs first (A/A), then `resample` `interp` vs `hold` in targets.json,
    same bench (item 17 or 19): does Mover's / SimHub's graph show a 24 Hz staircase with `hold`, and how much later does
    the pitch start with `interp` (one physics step, ~42 ms, expected)?
23. **T5 - motion latency.** Item 21's live command with `--record tools\haptics\replays\t5.i76rec` added; fire one
    shot / ram one wall; compare the IMPACT event's frame time with the first packet carrying the cue (cue_surge) in the
    native log. Report the milliseconds (n runs).
24. **T6 - explosion reach.** An AI car blows up near you and far away (shares the sitting with item 13): cue_heave vs the
    EXPLOSION distance in the plot. Sets `explosion_gain` / `cue_max` in the rig's motion section.
25. **T7 - real rig, later (hardware not chosen).** Only once a rig and controller exist: Mover's output module for it,
    the host still only sending UDP, the controller's E-stop in reach. Kill the host mid-drive (Ctrl+C, then end the
    process): the rig must ramp to neutral over about 1 s, not drop. Also pause the game: same ramp after 250 ms.
26. **Transducer: HD pack stems vs Lfe.Synth (`tools/haptics` Lfe.Stems).** Needs item 6 (v3 sound events) and the stems built
    (`tools\soundhd\soundhd.py build`; `haptics.ps1 stems status` says 85 on disk). Shaker only, game sound as usual, lab copy, same
    mission and route each run (t01). A/A first: two runs with the shipped rig, note whether you can tell them apart. Then three runs,
    switched with `$env:I76_LFE_SOURCES` before `haptics.ps1 live --source udp --live` (the start line prints the gains in force):
    **synth only** `synth=1,stems=0`, **stems only** `synth=0,stems=1`, **both** `synth=1,stems=1`. Compare these events:
    - your own MG (hold the trigger) and cannon: one thump per shot, loop seamless (whmgun, wlcan/whcan);
    - an AI car firing at you from near (under 30 m) and far (100 m+): lighter with distance, gone beyond ~150 m;
    - ramming a car and a wall at speed (vvcre2, vnvcs3/5) and an AI car exploding near you (vexplode, xcar);
    - your engine at idle, then revving to the limiter: rumble follows the revs (stems track rpm), no tick at the loop point;
    - ignition (eshp1, esnp1/2): the catch, not the cranking; droppers (mines, oil, caltrops: stems only, no synth effect).
    For each: which run felt more like the sound, anything late against the speakers (say which event), anything doubled or muddy in
    "both". Before the session, `python tools\haptics\design\stems_view.py` shows each stem next to the synth for the same event.

## Proxy cleanup side DLLs (lab twin only; docs/records/PROXY-CLEANUP-2026-10-10.md)

27. *(2026-10-16: the proxy half (`8b904e53`) is superseded - the env cleanup rides in promotion 18's `855b08d7`. The u32x half
    (`188e0c07`) is still open, and it is an agent gate at a free console, not a playtest.)*
    **Gate the 2026-10-10 proxy cleanup builds on the lab twin before any promotion.** Physical console, nobody playing
    (the gate takes the mouse, the keyboard and the screen for about 10 minutes). Put the side builds into the twin
    `..\i76-uncap-lab\game-dd-20261003` only, keeping its current files beside them: `music-fix\out\Strlkup.dll`
    (md5 `8b904e53`) over the twin's `Strlkup.dll`, and `u32x\u32x_full.build.dll` (md5 `188e0c07`) through
    `u32x\deploy-u32x.ps1 -GameDir <twin> -U32xDll u32x\u32x_full.build.dll -AllowUnverified`. Then
    `powershell -ExecutionPolicy Bypass -File ..\i76-uncap-lab\autotest\gate-folder.ps1 -GameDir ..\i76-uncap-lab\game-dd-20261003`.
    Expected: the same 23 rows as `autotest\runs\gate\20261008-204529`, with no new FAIL. Watch row 4: the u32x
    modal-pointer arrow on the save screen's prompt now draws without the removed VPTR code. Watch row 3 too: the frame
    rate through the launcher. `mciproxy.log` should show the usual switch lines and no `glide-dir` line. Report the
    run folder. Only after a clean gate may either DLL replace the committed `music-fix\Strlkup.dll` (`c11f7f7d`) or
    `u32x\u32x_full.dll` (`06467bd2`), or go to the daily driver.

## Cockpit dash at 2x: tile-split first boots (lab copy game-tex only; docs/COCKPIT-HIRES-FEASIBILITY.md stage 2)

Before these, look at the offline mock-up (`texture-lab\out\cockpit-mockup\index.html`, built by
`texture-lab\cockpit_mockup.py`) and decide whether a sharper dash shell around unchanged gauges is worth a session.
Three boots of t01 in the Piranha on `..\i76-uncap-lab\game-tex`, same conf and same `ZGLIDE` for all three (start with
the copy's normal conf; if the proxy log's `tex-census` shows NO-SLOT, repeat all three with
`-Conf ..\i76-uncap-lab\game-tex\dgVoodoo.tmu16.conf -ZglideFix`). Build each pair from game-tex's own archive into a
staging folder, then copy the four files (`vppirnag.pak/.pix`, `zdash106.pak/.pix`) into `game-tex\ADDON`; between
runs delete them again (nothing else in ADDON changes; the pirana*6 paint packs already there stay for all three).
Each run: capture the start view (F1 cockpit is the default), then press F1 once and capture the 2D dash; record the
`tex-census` lines (downloads, NO-SLOT, flushes) and the telemetry fps.

28. **control.** No dash files in ADDON. The reference capture and census.
29. **marker2x-split.** `python texture-lab\cockpit_split.py --game ..\i76-uncap-lab\game-tex --out texture-lab\out\cockpit-split\gt-marker2x --marker`
    (prints `self-check: PASS`; `preview-as-seen.png` there shows the expected panel). In the start view only the top
    edge of the dash is on screen: pass = blue and yellow frame lines along it and, left to right from the PRND plate,
    the small labels `101-11` (yellow), `102-01` (blue), `102-11` (yellow; `101-01` is further left, near the N plate),
    each with a fine magenta checker beside it that is crisp, not a mush (a 1-texel checker only a 2x tile can show).
    The mock-up page's "What the stage-2 marker boot should show" strip is the expected picture.
    Kill criteria: stock dash art = the overrides did not load (new member names not accepted from an ADDON .pix, the
    doc's first unknown: report it, the fallback is re-using existing names); a label mirrored or upside down, or the
    quarters' halves swapped = the v orientation is wrong (report which); one quarter magnified across the face = UV remap
    wrong; white, black or wrong textures elsewhere = TMU allocator (look at NO-SLOT); a crash = read the proxy `CRASH`
    line. A thin line along a quarter border is a seam: report it (the tool's `--seam clamp` build is the A/B).
    The 2D dash after F1 must look exactly like the control.
30. **art2x-split.** `python texture-lab\cockpit_split.py --game ..\i76-uncap-lab\game-tex --out texture-lab\out\cockpit-split\gt-art2x --png-dir texture-lab\out\cockpit-mockup\tiles`
    (the 2x tiles the mock-up wrote). Same captures. Judge crops of the dash strip against run 28 blind
    (`tools\upscale\ab_viewer.py`): sharper, same, or worse, and anything that changed colour. Kill criteria as run 29,
    plus colour banding on the dash (each quarter has its own 255-colour palette). If the dash only matters when you look
    down, say so: that decides whether stage 3 (the owner's route, the Leprechaun, a night mission) is worth doing.

## Texture shimmer: supersampling for real (lab twin game-dd-20261003; docs/records/TEXTURE-SHIMMER-2026-10-12.md)

The offline read says the wide preset gets 4x MSAA but not its 5160x2160 supersampling. The window is a borderless
*windowed* mode, and dgVoodoo renders at the window size, 3440x1440. On top of that, `I76_TERRAIN_TEX=8` stretches the
sharpest ground texture to 400 m, past what 1440 lines can show without crawling. Each bat below boots T05 at the hill
top, standing, facing down the hill. Close the game between bats.

31. **[DONE 2026-10-12: real 2x SS (`stretched_ar`, 6880x2880 + 4x) promoted in promotion 16; the shimmer bats are in the twin's
    `_archive-2026-10-12`. Only `I76_TERRAIN_TEX` 1 / 4 vs 8 by eye is left; ask for a fresh pair (OWNER-MORNING B7).]**
    **Shimmer A/B from the T05 hill top.** In order: `TEST-shimmer-A-current` (= PLAY.bat), `-C-fullscreen-ss15`
    (fake fullscreen, so the 1.5x target is really used), `-B-ss2x` (6880x2880 + 4x MSAA), `-E-ss2x-noaa` (6880x2880,
    no MSAA), `-D-terrain-tex-1` (A with stock terrain texture distances), `-F-ss15-terrain-tex-4` (C with terrain x4).
    In each: sit 5 s and look at the far ground and the road at the bottom of the hill (crawling, sparkling, moire),
    then drive down the hill in cockpit view and watch the same ground and road go past. Note: (a) crawl less / same /
    more than A, (b) the fps counter top-left (does B stay at 120?), (c) for D and F, whether the far ground got
    blurrier in a way you mind. In C, also click one menu item after Esc and use the Esc-menu Exit once: fake
    fullscreen must not move the pointer. Expected: C less crawl than A, B/E least, D shows whether x8 is the main
    cause, F is the candidate new default. Kill criteria: a black or 4:3 picture, the window not full screen, or
    the pointer off target in C/B/E = fake fullscreen does not suit this setup (report which bat).
    `TEST-shimmer-Z-native-msaa4` is for the console agent's pixel check, not for you.

## Terrain drop-out on the T05 hill descent (lab twin game-dd-20261003; lab docs/TERRAIN-DROPOUT-HILL-2026-10-12.md)

The lab read shows the terrain setup cannot refuse on the hill. Your probe runs showed that the ground's vertices were
built every frame. What is left is a stage after that: the per-polygon clip, the depth buckets, the draw, or
dgVoodoo's presentation. The twin's proxy now counts every one of those stages per frame (`I76_DRAW_PROBE`).

32. **[OBSOLETE: replaced by item 34; `TEST-hill-G-drawwatch.bat` is archived.]** **Catch the drop-out with the draw census.** Play `TEST-hill-G-drawwatch.bat` (= hill-G plus the detectors; the
    proxy must be `509c6df0`, see the twin's TEST-CURSOR.txt). Drive down the hill in cockpit view, as when you saw it.
    Do 3-5 runs, closing the game between them.
    - If the ground vanishes, **note the clock time** (to the minute) and whether it was cockpit or an outside view.
    - Leave the game normally.
    - The twin's `Interstate 76\mciproxy.log` then shows at that moment either a `draw-probe: TERRAIN-LOSS` line,
      which names the stage that dropped the ground, or nothing. Nothing means the game drew the ground and the loss is
      in dgVoodoo's presentation.
    - `TEST-hill-G-pixelwatch` is not needed: its frame read comes back black on this setup, so its one PIXEL-FLASH was
      that, not a sighting.
    - The green crosshair you saw is the launcher's pointer overlay (`_ahk\i76-cursor-overlay.ahk`), not the detector.
      Ctrl+Alt+C hides it.
    - Kill criteria: a crash or a `draw-probe: NOT applied` line in the log (report it), or the fps clearly lower than
      in `TEST-hill-G-stepframe-barbox` (the census adds a call per ground polygon).
34. **The terrain fix: does the ground stay? (new 2026-10-12, replaces item 32.)**
    - **Cause, found at the console.** In some cockpit poses the game builds the outline of the ground the view can
      see without the eye inside it. Every terrain patch near the car is then culled for that frame, and the sky
      shows through. It happened 4-5 times per descent in cockpit view and never in chase view.
    - **The fix.** `I76_TERRAIN_HULL_FIX=1` rebuilds that outline correctly.
    - **Console result** (n = 5 each, lab doc s.10-11):
      - cockpit without the fix: 16 losses in 5 descents;
      - with the fix: 0;
      - regression boots t01 and t11: in mission, no crash, frame times as before.
    - **Twin proxy.** The twin's proxy is now `a6a35e52`. The other launchers are unaffected, because both switches are
      off unless a launcher sets them.
    - **What to do.** Play `TEST-hill-terrainfix-play.bat` (the fix only, full speed). Drive down the hill in cockpit
      view, 3-5 runs, as when you saw the drop-out. Then one run of `TEST-hill-terrainfix.bat` (the same with the
      counters).
    - **If the ground still vanishes:**
      - note the clock time;
      - the twin's `Interstate 76\mciproxy.log` then shows a `draw-probe: TERRAIN-LOSS` line, which means something
        else is dropping it; report that line.
    - **Normal log lines.** `terrain-hull-fix: event` lines are frames the fix repaired.
    - **Kill criteria:**
      - a crash;
      - `terrain-hull-fix: NOT applied` in the log;
      - ground missing in a place where it showed before (a patch culled that should not be).
    - **Verdict.** If it holds, the fix is a candidate for the next promotion, as one key in best-wide.

## Signs that won't fall: the Texas 13 shields (lab twin game-dd-20261003; lab docs/SIGN-FIX-2-2026-10-12.md)

35. **[OBSOLETE: =3 was played inside TEST-next ("100% of the time", "a little early"); =4 (item 36) replaces it in promotion 18.
    `TEST-hill-signs2.bat` is still in the twin but is not needed.]** **Sign fix 2: does every sign go down at the first ram? (new 2026-10-12, replaces the H test.)**
    - **Which signs.** The Texas state shields are `sh13n` / `sh13s` ("13", NORTH / SOUTH). Two stand at the crossroads
      at the foot of the hill: 65 m up the north road and 70 m down the south road. Two more are further up the north
      road. They are the same sign as the US 380 shields in every number.
    - **Why H did nothing for them.** H changed only how hard a hit the game *notices* counts. Your H session logged
      9 noticed hits (one sign at the foot of the hill and 8 barricade bars), none at a Texas sign. The game had not
      registered those rams at all.
    - **Console result** (lab twin, straight rams at 20 m/s with a few degrees and up to 0.6 m of aim jitter;
      n = 12 Texas + 21 US 380 per condition):
      - 24 fps stock-like: 5 of 33 knocked over;
      - G: 5 of 33;
      - H: 4 of 33;
      - the fix: **33 of 33** (12/12 Texas, 21/21 US 380; p < 1e-12 against 24 fps).
    - **The fix.** `I76_BREAKABLE_BOX=3` is G plus a check of what you see. A sign post that your car's body drives
      through without the game having hit it is scored the game's own way: above walking pace it falls, a nudge stays
      a nudge. Only your car, only breakable posts (barricade bars, buildings, cars unchanged).
    - **Twin proxy.** The twin's proxy is now `df7b3b0b` (the terrain-fix build plus this). Every launcher except the
      new one behaves as before, `TEST-hill-terrainfix*` included.
    - **What to do.** Play `TEST-hill-signs2.bat`. Drive down the hill, turn at the crossroads, ram the two Texas 13
      shields, then any other signs (the US 380 shields on the road to the north, the speed-limit and construction
      signs). Try straight rams and sliding ones.
    - **Normal log lines.** In the twin's `Interstate 76\mciproxy.log`, `sign-sweep: ... scored` lines name each post
      the game itself missed. The summary line counts post entries against the ones the game hit.
    - **Kill criteria:**
      - a crash;
      - `sign-sweep: fault` in the log;
      - a sign falling when you clearly passed beside it (more than about a car's width away);
      - anything that is not a sign post breaking or behaving differently from PLAY.bat.
    - **Verdict.** If it holds, `I76_BREAKABLE_BOX=3` replaces `=1` in best-wide at the next promotion.
## Next candidate: bushes and terrain as far as the roads, signs on time (lab twin game-dd-20261003; lab docs/DRAW-DISTANCE-2026-10-12.md, SIGN-FIX-3-2026-10-12.md)

36. **TEST-next.bat / TEST-hill-next.bat, updated 2026-10-12 evening.** Your TEST-next session: "looks really great. can the brush/bush draw distance and the terrain draw distance be as far as the road draw distance? ... the collision with the signs happens a little early again but it happens 100% of the time".
    - **What "terrain draw distance" was.** The ground itself is drawn to 1800 m already. What stopped short is its *detail*: the terrain is rebuilt each frame with fewer, bigger triangles farther out, so small mounds and ridges a kilometre away were flattened and popped up as you came closer. `I76_TERRAIN_LOD` sets how far the detail reaches. It was 8, and now it is 32. The detail distance grows with the square root, so 32 reaches twice as far as 8. Captures from the hill top show the mounds around the barricade end of the valley at 32 that are missing at 8.
    - **Bushes.** They were drawn to 300 m. Now they go to 1800 m. Drawing every bush that far ran at 38 fps on the hill top, so past 200 m they thin out with distance, about as fast as they shrink on screen.
    - **Cost.** Measured on the console from the T05 hill top looking down the valley, the worst cockpit view, n = 4 each:
      - TEST-next: 120 fps, slowest 1 % of frames at 107 fps;
      - today's PLAY.bat: 120 fps, slowest 1 % at 96-101 fps;
      - the drive down the hill and the t04 desert drive: no difference;
      - binoculars: about 60 fps on the hill as before.
    - **Signs.** `I76_BREAKABLE_BOX=4` keeps every hit of =3 (33 of 33 shields knocked over again). The sign now falls when your car *on screen* reaches the post, not when the physics, which runs up to one step ahead, does. The bumper-to-post gap at the moment a sign fell:
      - before: median +0.44 m, up to 2.7 m early;
      - now: median -0.11 m, never early (n = 33 each).
    - **Alternative.** `TEST-next-dense.bat` / `TEST-hill-next-dense.bat` keep today's full bush density out to 300 m, with terrain x24 instead of x32. It costs the same on the hill top. Tell me which you prefer.
    - **Twin proxy.** The twin's proxy is `855b08d7`, built from the repo source. Every other launcher behaves as before.
    - **Kill criteria:**
      - a crash;
      - `sign-sweep: fault` or `terrain-vguard:` lines in `Interstate 76\mciproxy.log`;
      - a sign falling before the bumper touches it, or after you are clearly through it;
      - stutter in the hill-top view that PLAY.bat does not have.
    - **Not promoted yet.** Promotion 18 is on hold until the dream-mission report ("expecting you to stay on the road") is explained.
    - *(2026-10-16: still open. The hold's reason is answered by item 37 (the stock lap counter), but nobody has lifted the hold, and
      the gate phase P9 is not written. Since 2026-10-13 the TEST-next* bats also carry the AI parity set (item 40), which promotion
      18 does not.)*
    - *(2026-10-17 morning list: this is the promotion-18 hold decision (C4). Play `TEST-hill-next.bat` then `TEST-next-dense.bat`
      (both also carry the AI parity set); say lift the hold yes / no and bushes thin to 1800 m or dense to 300 m. The twin proxy
      was read back 2026-10-17 as 33211f11 (the replay build that sat there at 22:40 is gone). No P9 gate exists yet: an agent
      writes it after a yes. About 20 min.)*
    - **PROMOTED 2026-10-17 17:17 (PROMOTIONS row 17), 09 variant: proxy 33211f11, hull fix, signs =4, bushes 1800 m dense
      to 300 m, terrain x24 in best-wide / balanced / best-120; AI parity set NOT included.** Gate P9 on the twin: signs 22/22,
      hill descents 0 terrain losses (n 5), barricades 7/7 vs 3/15, owner's route 21/0, rollback `_rollback\17`.
      Feel-check list: records/PROMOTION-18-2026-10-17.md section 5.

## The dream mission (T04, the 4-lap race; lab docs/DREAM-MISSION-2026-10-12.md)

37. **[DONE 2026-10-12: answered (stock 8-checkpoint lap counter, 19/19 twin runs); the pace part continues in item 40.]**
    **Your report "the dream mission fails because it expects you to stay on the road" (answered 2026-10-12).**
    - **What it is.** Stock 1997 behaviour, not one of our switches. The race script counts a lap only when your car
      passes within 25 m of eight points on the track, in order. Cut a corner or run wide past one of them and that
      whole lap silently does not count. The AI then finishes 4 laps first, and you get "They won the race...because
      you let them!". The game never says a checkpoint was missed.
    - **The eight points**, in driving order from the grid: about 60 m up the start straight, the end of that
      straight, two on the first big curve, two down the far side, two at the far corner. The long run home to the line
      has none, so the risky places are the curves and the far corner: no cutting across the infield there.
    - **Checked on the twin.** The counter worked the same in all 19 runs: PLAY.bat's set, without the road distance,
      stock and the 1997 24 fps reference (lab doc s.4a).
    - **What our build does change.** The AI racers lap about 2 s quicker than in the 1997 game, so they finish about
      8-9 s sooner. One lost lap is now harder to make up. This comes from the frame-rate fixes every preset has had
      since promotion 2, not from promotion 16's road distance or collision fix.
    - **Also fails the race:** ramming or shooting a racer before your 4th lap ("Win the race; then kill").
    - **If you play it again,** tell me which bat you used and which failure line you saw: the "they won" line or the
      Confucius line. If you want the racers at their 1997 pace, say so; that is a proxy change with its own A/B.

38. **[OBSOLETE: item 40 corrects its reference (24 fps was wrong; stock20) and `TEST-dream-1997pace.bat` now carries the parity
    set. Test it under item 40.]** **The dream race at 1997 pace (new 2026-10-13; lab docs/AI-PACE-2026-10-12.md).**
    - **Why.** Our racers were ~2 s a lap quicker than in the 1997 game (item 37). Cause found: the AI steers with a
      controller sized to the frame time, and the 1997 clock ticks in 15.6 ms steps, so every third steering command
      overshoots and the AI weaves a little. Our exact clock removed that, so the AI drives a cleaner, quicker line.
      `I76_AI_STOCK_CLOCK=1` puts the 1997 overshoot back. Measured on the twin: Patriot 47.7 s a lap with it, 44.8
      without, 46.7 in the 1997 game (24 fps); the other racers alike.
    - **Test.** In the lab copy, `TEST-dream-1997pace.bat` (PLAY.bat + the switch, straight into T04; Esc skips the
      opening) and `TEST-dream-control.bat` (PLAY.bat, straight into T04). Race both once or twice. Does the 1997-pace
      race feel like the race you remember (the racers a bit slower and a bit less tidy in the bends)? Can you win it?
    - **Also in `TEST-next.bat` and the other TEST-next* launchers** - it changes every AI car, not only racers. Play a
      combat mission with TEST-next: do the AI cars still chase, shoot and handbrake-turn as before (checked on the twin
      in t05: they do), or does their driving look clumsy?
    - **Proxy 4c9be840** in the lab copy (855b08d7 + this switch only; rollback `STRLKUP.DLL.855b08d7-pre-stockclk`).
      Not in the daily driver; say if you want it in PLAY.bat.


40. **AI combat at the stock game's rates (new 2026-10-13 evening; lab docs/AI-COMBAT-PARITY-2026-10-13.md, docs/records/WHAT-IS-STOCK.md).**
    - **Why.** Your question: "any other AI differences to iron out so combat behaves the same in other missions?" Measured on
      the twin against the stock game capped at 20 fps (what you played before 10-03; now the lab's "stock"), in t05, t13,
      t15 and t17, five runs per setting:
      - at 120 fps the AI checks the ground for your oil / mines / fire 5-8x as often per second;
      - it starts 2-4x as many handbrake turns, and in most of them the handbrake never reaches the car;
      - it steers without the stock clock's overshoot.
      Shots, hits and damage on you were already about the same.
    - **What changed.** `TEST-combat-parity.bat` = PLAY.bat plus the parity set: the AI's decisions, handbrake turns, throttle
      ease and route search at the stock 20 fps rates, and its steering on the stock 20 fps clock. Measured with it, those
      rates match stock.
    - **Correction to item 38.** "1997 pace" was tuned to 24 fps, which was the wrong reference: it ran 1.3-1.9 s a lap
      slower than the 20 fps game. `TEST-dream-1997pace.bat` now carries the parity set and laps within 0.7 s of the 20 fps
      game. The TEST-next* launchers carry it too.
    - **Test.**
      - Play a combat mission or two with `TEST-combat-parity.bat`, then with `PLAY.bat`. t13 and t17 have chasing,
        shooting, handbrake-turning attackers; t05 the attacker on the road.
      - Do the attackers handbrake-turn and slide the way you remember?
      - If you drop oil, mines or fire, do they drive into it more often than in PLAY.bat? They should: at 120 fps today
        they see it coming 5x sooner.
    - **Proxy f6d0c668** in the lab copy (rollback `STRLKUP.DLL.4c9be840-pre-combat`). Not in the daily driver; say if you
      want it in PLAY.bat.

41. **[RETIRED 2026-10-15: W95-18 is superseded by the era envelope (records/ERA-ENVELOPE.md) and the gold standard (retail 1.0 on
    the emulated P166, records/EMU-MEMTRACE.md). Windows 95's tick is 1 ms, not 55. The two bats are still in the twin; optional.]**
    **W95-18: the box-spec feel test (new 2026-10-15; lab docs/W95-18-BASELINE-2026-10-14.md, docs/records/W95-18-BASELINE.md).**
    - **Why.** You asked to treat the 55 ms tick at 18.2 fps as the 1997 baseline. It was measured. Since then the 86Box rig has
      found Windows 95's tick to be 1 ms, so W95-18 is one era-like profile, not "the" 1997 machine.
    - **What's there.**
      - `TEST-w95-18-reference.bat`: the unmodified game at 18.2 fps on a 55 ms tick, choppy on purpose.
      - `TEST-w95-18-parity.bat`: TEST-next at 120 fps, tuned so its physics and frame-rate fixes run like W95-18.
    - **Test.**
      - T05 (the canyon, mission 5): from the hill top, full throttle down the road and over the ramp, once with each
        launcher. Both should clear, and the parity car should fly about as far as the reference (about 220 m) and land intact.
      - T06's first ramp, the same.
      - Any combat mission: does the reference's choppiness change how the AI feels to you?
    - **Proxy 33211f11** in the lab copy (rollback `STRLKUP.DLL.f6d0c668-pre-w95-18`). Not launched by hand yet. Not in the daily
      driver.
42. **Era envelope candidate: the canyon landing (new 2026-10-15; docs/records/ERA-ENVELOPE.md, lab docs/ERA-ENVELOPE-2026-10-15.md).**
    - **Why.** The car destroyed after the T05 canyon landing in PLAY.bat / TEST-next is the game's own rollover rule. The car
      bounces, ends up on its roof and is wrecked, god mode or not. It gets more likely with bigger physics steps. PLAY.bat's
      41.7 ms step turned the car over on 9 of 10 hill-top descents. A P166 at low detail (30 ms steps) never did.
    - **What's there.** `TEST-envelope-candidate.bat` in the lab copy: TEST-next with 30 ms physics steps and its frame-rate
      fixes / AI clock on a 30 fps reference.
    - **Test.**
      - T05 from the hill top: full throttle down the road and over the canyon ramp, a few times. You should land and drive on,
        with no roll-over and no wreck. Then try PLAY.bat the same way for comparison.
      - Drive a straight flat road: is the body calm (no fast side-to-side shimmy)?
      - Does the car still feel like the game: jumps (about 200 m over the canyon, 72 m on T06's first ramp), acceleration,
        steering?
    - **Known.** Barricades knock a little less often than in the stock game (6.6 of 10 vs 7.8). That comes from the
      bar-as-box switch shared with PLAY.bat and TEST-next, not from this change.
    - **Proxy 33211f11** in the lab copy (unchanged). Not booted by hand yet. Not in the daily driver.
    - *(2026-10-16: still open. The 30 ms step came from Gold-exe profiles. Retail 1.0 on the P166 at low detail runs 26-30 ms steps,
      so the candidate is still to be re-checked against retail (EMU-MEMTRACE s.7.4). `TEST-p166-retail-step.bat` (31.75 ms) has no
      measurement recorded yet.)*
    - *(2026-10-17: re-checked against retail, headless, n 100 boots: [ENVELOPE-RETAIL-REBASE.md](records/ENVELOPE-RETAIL-REBASE.md).
      **Launcher unchanged, test unchanged.**
      - Retail's step follows the scene: 27 ms in melee, 32-35 ms in missions. A matching step list turned the car over
        on the T05 landing (6 of 25), so the candidate keeps 30 ms.
      - New check, about 10 min:
        - Launch `TEST-p166-retail-step.bat` (31.75 ms).
        - T05: from the hill top, full throttle over the canyon ramp, about 8 times.
        - Does the car ever clip the ramp's lip, swing sideways and drop into the canyon instead of flying?
        - Then the same on `TEST-envelope-candidate.bat`.
        - Where the lab saw it: in jumps placed at 56 m/s, 7 of 27 at 32 ms with the frame-rate fixes, 0 of 33 at 30 ms.
          It never saw it on a hill-top descent (0 of 9 at 32 ms), so it may not show on your route.)*
44. **"A little too fast and bumpy" on TEST-p166-retail-step: the view, and the emulator's handling (new 2026-10-16; docs/records/RETAIL-HANDLING-DIFF.md,
    lab game-dd-20261003\README-TESTS.txt).** Your note on `TEST-p166-retail-step`: every jump hard but possible (31.75 ms is now
    logged as the minimum step = the fastest 1997 machine), it played like the emulator, but a little too fast and bumpy / jittery,
    maybe the big screen. Two A/B launchers in the lab copy, next to `TEST-p166-retail-step.bat`; nothing else changed:
    - **`TEST-p166-retail-step-43.bat`: the same game with a 4:3 picture** (90 degrees across like 1997, side bars; widescreen
      shows 122). A wider view streams more ground past the edges, so the same speed looks faster.
      - **Test:** the T05 hill road and a T06 straight, once with each launcher. Too fast? Too bumpy? If 4:3 feels right, it is the
        view, not the physics.
      - Open the Esc menu once: does the pointer hit the buttons where they are drawn?
    - **`TEST-p166-retail-handling.bat`: the handling the emulator had.** The emulated retail 1.0 turned about a quarter less at
      speed than our exe because its **Arcade Phys.** option was on by accident: a Gold options file read by the 1997 exe. The physics
      code is the same in both exes. So if "played like the emulator" included the steering, the emulator you saw was arcade.
      - **Not installed yet:** it needs proxy `0406e909` (built, not live-checked: the console was not usable overnight) and says so
        when it is missing. **The same thing today:** `TEST-p166-retail-step`, Esc > Options > Play Options > tick **Arcade Phys.**
        (the game remembers it, so untick it afterwards).
      - **Test:** fast corners (arcade turns less and hardly slides), and land the canyon jump on the roof once if you can (arcade
        flips the car back over; the 1997 default, arcade off, wrecks it).
    - **Say:** which of the three feels like your 1997 memory.
## I76 Debug dashboard (tools/debug, replaces the trainer window; lab copy first)

33. **I76 Debug on a real drive (new 2026-10-12).** Close the old trainer window first (it maps the telemetry shared memory at the
    old size). Start the lab game with `I76_TELEMETRY=1 I76_SOUND_EVENTS=1 I76_DAMAGE_EVENTS=1`, then `tools\debug\DEBUG.bat --tee 17676`
    and, in a second console, `tools\haptics\haptics.ps1 live --source udp --port 17676 --debug-udp` (files only; add `--live` only
    if you want the devices). Drive t01 or t05 for a few minutes: shoot, ram something, get shot, jump. Look at each tab once:
    Overview (fps, steps per frame, proxy DLL md5, the switch list matches the bat you launched), Telemetry (charts move with the
    car, the map trail follows you), Events (your shots per weapon, damage on the right side of the car diagram), Force feedback /
    Rumble / LFE / Motion (move with the haptics host running, say "No haptics host data" without it), Collision and Terrain (the
    30 s coll-window counters and any TERRAIN-DROP / camera-lift lines appear within a minute when the bat sets those switches),
    Log (filters). Trainer tab (sandbox): Repair now and the **T05 hill top** preset in t05 (lands on the crest above the
    barricades; turn west yourself, the teleport keeps your heading), one hold on and off. `TRAINER.bat` must open the same page
    on the Trainer tab; `TRAINER.bat --classic` is the old window. Report: anything empty that should not be, anything wrong,
    anything slow (the page redraws at about 15 Hz; the game's fps must not drop with the dashboard open - compare the Overview
    fps with the tab closed vs open, n = 2 each). Offline-tested only: tools\debug\README.md "Not verified yet".

33b. **Full car state store / restore + the haptics button (new 2026-10-20 evening, records/DEBUG-TOOL-2026-10-20.md).** Staged, not
    installed: needs the proxy from `i76-uncap-lab\builds\debug-tool-20261020\stage` (the main lane installs it after its gate).
    In T05: `DEBUG.bat` (Trainer tab, "full state: proxy"). Drive up the ridge toward the canyon jump, press **Ctrl+9** just before
    the lip (or mid-air), land or crash, press **Ctrl+0**: the car must reappear where it was, facing the same way, pitched the
    same, moving at the same speed, and do the same jump again with the same throttle (n 3). Then Ctrl+9 parked on the ridge and
    "Restore stopped" from the page. Waypoint 2 "Save here" at speed, drive off, "Go". Your old waypoint 1 must still "Go" (position
    only). Haptics tabs with the wheel plugged in: "Start haptics host" fills Force feedback / Rumble / LFE / Motion (dry run, the
    wheel is not driven); unplugged: the tab says no wheel or pad found. `TRAINER.bat` must open the same page on the Trainer tab.
    Report: anything that does not come back as stored (which part: heading, pitch, speed, suspension), whether Ctrl+9 / Ctrl+0
    clash with anything you use.

## Steam Deck docked to a TV (docs/STEAMDECK.md "Docked to a TV")

39. **Docked to the TV: 16:9 picture, menus with the controller, brightness (new 2026-10-13).** Your report: "the screen
    renders in a non 16:9 aspect ratio and the controller can't be used to navigate the menu. Screen looks a little darker too."
    - **Once, docked, in Game Mode:** Interstate 76 > gear > Properties > General > **Game Resolution = Native** (1080p TV) or
      **1920x1080** (4K TV). On Default the Deck hands the game 1280x800 even on a TV, and that is the 16:10 picture with bars.
    - **Aspect.** Launch from Game Mode. Main menu and mission fill the TV with no side bars; in T01 or Instant Melee the wheels
      and the radar are round and the 3D is wider, not stretched.
    - **Menus with the controller.** Left stick moves the pencil, D-pad nudges it. A on TRIP > LOAD BOOKMARK > a bookmark >
      LOAD > garage > DONE into the mission. B goes back one screen. On a garage OK popup: A on OK (the pencil may look frozen
      there; the pointer still moves), and try Start (= Enter). In the mission: Select (Esc menu), stick to Graphic Detail, A
      opens it, A on Exit, B closes the menu. Driving afterwards: unchanged.
    - **Brightness.** Still darker than handheld? First the TV: HDMI black level / RGB range on Auto or Full, HDR off for this
      input, Game or PC picture mode. Then the game: `I76_TV_GAMMA` (now 1.45; try 1.6) or `I76_TV_BRIGHTNESS` (105-110) in
      `~/Games/Interstate76/i76-env.sh`, last block. Tell me the values you keep.
    - **Undocked afterwards:** handheld looks as before (fills the panel, same brightness); the left stick now also moves the
      menu pointer there.
    - **Send** `~/Games/Interstate76/deck-launch.log` and `game/mciproxy.log` (lines `display:`, `md5`, `pad-menu:`).
    - **Installed by** `deck/deck-push-tv.sh` (proxy 2f2b8170 = 509c6df0's source + I76_PAD_MENU, launcher display profile,
      env block); rollback `bash ~/i76-deploy/deck/setup-deck-tv.sh --revert` on the Deck.
    - **2026-10-14 follow-up (your report: "the left stick as mouse in menus isn't working consistently. Sometimes it doesn't
      move the cursor and it doesn't seem to move it right over the correct mouse coordinates"; "the night mission on the
      steam deck is messed up, the textures seem wrong").** Pad menu v3, proxy **8bc52939** (docs/STEAMDECK.md "Pad menu
      v3"): the game now reads the pad's own pointer position while the stick drives, so what it highlights and clicks is
      where the stick put it even if the Deck's compositor does not move the visible arrow; v2 pulled the pointer back to
      the old spot whenever a pointer warp had not landed yet. The pencil also works in the Esc menu's Exit dialog now.
      **Re-test, docked and handheld:**
      1. Main menu: push the stick slowly, then fast, in all four directions. Does the pencil move every time? Does the
         button under the pencil light up (TRIP / MELEE / OPTIONS / EXIT), and does A open the one that is lit?
      2. TRIP > LOAD BOOKMARK > a bookmark > LOAD > garage > DONE, using only the stick and A.
      3. Mix: move with the stick, then touch the right trackpad, then the stick again. The pencil should keep following
         whichever one you used last, without jumping.
      4. In a mission: Select (Esc menu) > Exit > the Yes / No dialog: the stick moves the pencil there too; pick No.
      5. If the pencil still does not move but the buttons light up as you push: say so - that is the Deck's compositor
         ignoring the arrow warp (the game side is right), and the next step is on the Steam Input side.
      6. **Steam Input:** the left stick must stay a plain stick ("Joystick", as in the I76 gamepad layout) - not
         "Joystick Mouse" / "As Mouse". On a TV pad with its own layout, check the same.
      - **Night (T06, T12 are the night trip missions; M04, M12 the night melees) - FOUND AND FIXED 2026-10-14 20:19
        (deployed on the Deck).** The Deck's `game/ADDON` still held the July HD texture pack (3,322 files, retired in July,
        never on your PC). Its cockpit gauges, reticles, road, terrain, light and cloud tiles were re-coloured against a
        daytime palette; the game does night by swapping the palette under the same tiles, so exactly those came out in
        wrong colours at night (measured: up to 21% of the pixels of a road tile re-indexed, gauges going from 2 to 13
        colours). The pack is moved to `~/Games/Interstate76/backups/hd-pack-20261014-201947/` (nothing deleted); ADDON
        now has the same GOG stock files as the PC plus your `.vcf`/`.vsf`. dgVoodoo, the conf and the switches were fine
        and are unchanged. **Re-test:** play T06 (or M04) handheld, then docked: cockpit gauges, reticle, roads, ground
        and sky look like the PC's night (dark, but the right images and colours). Day missions now use the stock art
        too (the pack's day gain was marginal). Still wrong? Then a screenshot (Steam + R1) of the bad spot, and say
        handheld or docked. Each launch now also logs an `addon:` line (a WARNING if texture files reappear in ADDON).
        Undo: `bash ~/i76-deploy/deck/setup-deck-stock-textures.sh --revert` on the Deck. Separately, on a TV: if night is
        only too dark (not wrong), it is the TV's HDMI black level / `I76_TV_GAMMA`, as under Brightness above.
      - **Send** deck-launch.log and game/mciproxy.log again (lines `conf:`, `addon:`, `display:`, `pad-menu:` - v3 logs each warp
        that did not land and what turned the pad off).
      - **Installed by** `deck/deck-push-tv.sh` (it now saves the previous session's logs and conf to the PC first);
        backups in `~/Games/Interstate76/backups/pre-tv-<date>/`; `--revert` restores the state before the first TV install.

43. **Deck: rumble, and the menu pointer offset (new 2026-10-16; docs/STEAMDECK.md "Rumble silent, menu pointer").** Your
    report: "rumble does not work", "the mouse pointer coordinates are a little off". **Rumble cause found:** the pad layer's
    rumble has been switched off since July for the Mac's FFB shim, and the Deck never had that shim, so nothing drove the
    motors. Now the Deck launcher turns the pad layer's rumble on (`I76_AHK_RUMBLE`). **The pointer cause is not measured
    yet**: the Deck was offline, so this deploy also turns on two logs that show where the game window and the pointer
    really are.
    - **First, get it installed** (not done yet - the Deck was offline): wake the Deck on Wi-Fi and say so (the agent runs
      `deck/deck-push-tv.sh`), or run that from the PC yourself. It keeps the old files in `~/Games/Interstate76/backups/`.
    - **Steam side, once:** Steam > Settings > Controller: rumble / haptics not switched off. The I76 layout stays the
      gamepad layout (v10).
    - **Rumble, handheld:** in T01 or Instant Melee: hold A (or L3) for nitrous -> a kick then a buzz; RB handbrake -> one
      thud; LB + D-pad left/right (gears) -> a light click; D-pad down (ignition) -> a ~0.3 s crank; RT fire -> a light buzz;
      stick pinned forward -> a low growl. Say which ones you feel. **Docked with a TV pad:** the same; rumble is sent to every
      connected pad (`all`); say which pad shakes.
    - **Pointer, handheld then docked:** main menu; put the pencil tip on the left edge of TRIP, the centre of MELEE and the
      right edge of EXIT, first with the stick, then with the right trackpad. Each time: which button lights, and is the
      offset the same everywhere or bigger toward the edges? Then A on each. A photo of the screen with the pencil on a
      button edge helps.
    - **Send** `~/Games/Interstate76/deck-launch.log` (lines `rumble:`, `xprobe`, `display:`) and `game/mciproxy.log` (lines
      `cursor-map:`, `pad-menu:`), or leave the Deck on Wi-Fi and the agent collects them.
    - Rumble off again: `I76_AHK_RUMBLE=0` in `~/Games/Interstate76/i76-env.sh` (last block). Undo everything:
      `bash ~/i76-deploy/deck/setup-deck-tv.sh --revert`.

## Overnight 2026-10-16 / 17 (records/OVERNIGHT-2026-10-16.md; ordered by priority, then minutes; also do items 1-2 and 36 there)

45. **Arcade Phys.: which setting is the gold standard? (decision, high, 5 min; new 2026-10-17; records/RETAIL-HANDLING-DIFF.md).**
    - **ANSWERED 2026-10-17 (owner): simulation physics (Arcade Phys. off).** The gold standard is retail 1.0 with stock options; arcade runs are kept only as the arcade reference.
    Every retail 1.0 emulator run before 2026-10-16 22:42 had Arcade Phys. **on** by accident (a Gold-layout `I76PLYR.DEF` read by the
    1997 exe). The stock default is off in both exes, and the emu runs since lab 0e2f16c are already off - nothing to switch.
    - **Read:** `C:\Users\james\i76-everywhere\docs\records\RETAIL-HANDLING-DIFF.md`, the Answer and section 5.
    - **Decide:** gold standard = retail 1.0 with stock options (arcade off), or do you remember playing 1997 with Arcade Phys. on?
    - **Feel it (optional, part of item 44):** lab twin `TEST-p166-retail-step.bat`, Esc > Options > Play Options > tick Arcade Phys.,
      fast corners and a roof landing; **untick it afterwards** (the game saves it to the twin's `I76PLYR.DEF`).
    - **Say:** "arcade off" or "arcade on".
46. **Logged P166 play session in 86Box, retail 1.0 (high, 30 min; new 2026-10-17; records/EMU-OWNER-LOGGING.md).**
    - **Owner's 1997 settings (2026-10-17):** software renderer (no 3D card), 640x480, rear-view mirror on, sound effects and music on at defaults, detail as high as the frame rate allowed. He no longer wants feel-from-memory used as evidence for the physics step; the step is decided by the study in records/PHYSICS-STEP-STUDY-DESIGN.md.
    Your own pbs-p166 machine on a logging copy of your disk; your `w95pb-hdd.img` is untouched (sha256 re-checked). The launcher
    refuses to start if the logging disk is already in use, so no pre-check is needed.
    - Double-click `C:\Users\james\i76-uncap-lab\emu\PLAY-P166-LOGGED.bat` (disc 2 in the drive). If the game asks for disc 1 for
      a mission, close 86Box and relaunch with `PLAY-P166-LOGGED.bat --cd disc1`.
    - Start Interstate '76 from Start > Programs; 320x200, lowest detail; Options: **Arcade Phys. off**.
    - Play T05 to the canyon jump (or any mission). Exiting and restarting the game is fine (each start = one session).
    - Exit the game, Start > Shut Down, wait for "safe to turn off", close 86Box.
    - **Look for:** `C:\Users\james\i76-uncap-lab\emu\results\memtrace\owner-<date>-<time>\summary.md` lists your session(s): retail 1.0,
      in-mission fps around 33-38, Arcade Phys. off, a "T05 canyon descent" line, the mission's music track. Report any "Cannot find
      file" dialog, an empty summary, or a game that feels slower than `run-vm.ps1 pbs-p166`.
    - **Caveat:** the launcher copies the logger from `emu\probe\out`, which is now I76MEM 2026-10-16b (commits the file every
      64 writes), not the 2026-10-16a build the self-test ran. Saves made here stay on the logging disk.
47. **GOG music file order by ear (medium, 5 min; new 2026-10-17; records/MUSIC-RETAIL-INTENT.md).** Any player:
    `C:\Users\james\i76-uncap-lab\game\music\3.mp3`, `15.mp3`, `16.mp3`, `17.mp3` (the opening seconds are enough).
    - **Expected:** 3 = Interstate '76 Theme, 15 = Malochio Down, 16 = Skeeter Gettin' Medieval, 17 = Ovum Bisquit. Note any that differ
      (`I76_MUSIC_DISC_ORDER` rests on length matching only until you confirm).
48. **F2 orphaned bookmark: stock control vs the F2 shell (medium, 12 min; new 2026-10-17; records/BACKLOG-AGENT-ITEMS-2026-10-16.md U-05).**
    - **DONE 2026-10-17 by agent at the console (owner handed it over): PASS.** Control (stock shell a300db63): slot reset to -1 on re-entry, new bookmark names save015.cmp which was never written = ORPHAN (bug reproduced). F2 shell (2ab4ca90) from the same restored saves: slot 15 kept on re-entry, file written, VERDICT OK. Extra check of the plain type-and-Enter save: F2 opens the Save screen at slot 0 (stock -1) but still appends a new bookmark with its file; no existing bookmark changed. n 1 per path; saves restored to the pre-test backup (md5 read back). Driver fix lab 6cb7bae.
    Twin `C:\Users\james\i76-uncap-lab\game-dd-20261003`; saves are backed up and the shell restored automatically (md5 read back).
    1. `TEST-F2-bookmark-control.bat`: load any bookmark > garage > Options > Save Bookmark, type ORPHANA, click once on the empty
       paper right of the list (not a row or button), click the name field, type ORPHANB, SAVE, quit. Read the VERDICT.
    2. `TEST-F2-bookmark.bat`: the same with **ORPHANC / ORPHAND** - use these names even though the console text says ORPHANA / B
       (reusing ORPHANA brings up the overwrite prompt and muddies the comparison).
    3. `PLAY.bat` in the twin > Load Bookmark.
    - **Look for:** control prints ORPHAN, F2 prints OK; ORPHAND is in the load list, ORPHANB is not. Control printing OK = the stock
      trace is wrong; say so.
49. **Retail-intent music: the taste calls (medium, 15 min; new 2026-10-17; records/MUSIC-RETAIL-INTENT.md).** The gapless / pause log
    - **ANSWERED 2026-10-17 (owner): retail music across the board EXCEPT resume: `I76_MUSIC_RETAIL=1` + `I76_MUSIC_RESUME=1` (music continues where it stopped on Replay / shell entry).** The listen test is now optional (confirm the shell tracks sound right).
    checks are agent work; only your ears are needed for the choices. Unmute the PC yourself.
    - `C:\Users\james\i76-uncap-lab\builds\music-retail-20261016\MUSIC-RETAIL-TEST.bat` (retail mode; plays lab `game\`, swaps its
      proxy for the run and puts it back). Main menu 1 min (one short track looping), Options > Credits (another short one), back.
      Start a mission, choose Replay once (retail restarts the track from 0:00).
    - Then `MUSIC-RETAIL-TEST.bat control` and the same.
    - **Say:** which menu / credits music you prefer (1997 shell tracks vs today's run), and restart vs continue on Replay.
50. **Gold vs retail sliding at 25 m/s, in the emulator (medium, 15 min; new 2026-10-17; records/GOLD-STANDARD-FINGERPRINT.md).**
    The only behaviour where Gold misses retail: yaw while sliding +19 % at 25 m/s (n 12 vs 17), with Gold's held speed 3.9 % lower.
    Our exe has Gold's physics bytes, so this is the open handling question for our exe. Can share the sitting with item 46.
    - `C:\Users\james\i76-uncap-lab\emu\PLAY-P166-LOGGED.bat`, Arcade Phys. off, Instant Melee: hold about 55 mph, full lock left
      and right a few times.
    - Again with `PLAY-P166-LOGGED.bat --cd gold`, starting `C:\I76GOLD\I76.EXE` from Start > Run (the Start menu may only list retail).
    - **Look for:** does Gold visibly slide out or spin more at the same speed and lock? Does it matter to you for "stock"?
51. **Instant Melee frame replays on the twin, first run (medium, 10 min smoke, then 20-40 min; new 2026-10-17; records/LAB-FRAME-REPLAY.md).**
    - **Ran 2026-10-17 at the console (agent, owner handed it over): FAILED before measuring.** Both Gold replays (g166-mloop-rep1, -N 2) printed "Did not reach mission (menu nav may have drifted)" and "no common frames"; the game booted, took the lock, muted, exited 0. Summary: lab tools
eplay
unsmelee-console-20261017-145313.txt. Needs agent debugging of the melee menu navigation (no owner action); not done, to save credits.
    The only clean frame-by-frame exe vs emulator comparison (same default car), but the menus do not work headless. The script has
    never run: expect to debug it, not to measure.
    - Session connected, no other game running. From a cmd window:
      `C:\Users\james\i76-uncap-lab\tools\replay\REPLAY-MELEE.bat -Conds g166-mloop-rep1 -N 2` (2 Gold replays). It takes over mouse
      and keyboard; hands off. If it stalls at a menu, note which one and stop it (Ctrl+C in the window) instead of waiting out 240 s timeouts.
    - If both finish: run `REPLAY-MELEE.bat` with no arguments (10 replays; the 6 retail ones replay arcade traces and do not count yet).
    - **Look for:** `tools\replay\runs\melee-console-<stamp>.txt`: Gold reps with "sim_dt bit mismatches 0", "input bit mismatches 0",
      and the first frame with |dpos| over 0.1 / 1 m (late = good).
52. **Watch one retail canyon descent (low, 5 min; new 2026-10-17; records/EMU-T05-CLEAN.md).**
    - **PASS 2026-10-17 (owner): the re-recorded canyon clip "looks perfect".** Same day: 02/03 WASD controls good but the menu automation is too slow; 08 does not teleport to the hill top (too long to get there); daily driver: the Windows mouse pointer is drawn a little right and maybe down of the game's cursor. Fixes in progress: records/OWNER-FEEDBACK-FIXES-2026-10-17.md.
    `C:\Users\james\i76-uncap-lab\emu\results\writeup\video\retail-sim-p166-t05-clean-descent.mp4` (simulation physics, damage-free
    crest start). Optional: `...\emu\results\par\20261016-224007-r166-t05clean-a-1\video.mp4` is 8 descents in **arcade** (25 min; skim).
    - **Look for:** no pop or jitter at the placed start; does the jump look like your memory of the 1997 game?
53. **Rule on the base decision (decision, medium, 10 min; new 2026-10-17; records/BASE-DECISION-1.0-vs-GOG.md,
    summary in records/VERSIONS-AND-PHYSICS-2026-10-17.md s.7).** Paper recommendation: keep the GOG Gold exe as the code
    base, play it with retail 1.0's rules (difficulty 1, retail health %, AI damage-stamp revert, retail turret slew and
    heat-seeker cone, arcade off) on the whole-sim tick at 33.3 ms; no 1.0 rebuild.
    - **Read:** the Recommendation and sections 5-6 of BASE-DECISION.
    - **Say:** agree or not with the hybrid, and which retail-rules items you want on by default (especially the Gold
      data retunes: bus mass, Gas blast, armour / loadouts).
54. **Trainer logger, one logged mission on the twin (medium, 10 min; new 2026-10-17; records/TRAINER-LOGGER.md s.7).**
    Never run on the twin's own proxy. At the physical console:
    `C:\Users\james\i76-uncap-lab\game-dd-20261003\Interstate 76\TEST-logged-play.bat`. Play one mission, press Scroll
    Lock twice at moments you want to remember, quit the mission, close the dashboard window.
    - **Look for:** a new folder under `C:\Users\james\i76-uncap-lab\captures\trainer-log\` with `s01\`; `marks.csv` with
      2 rows; `summary.md` naming the mission, 0 missed frames, Arcade Phys. off. No stutter you can feel compared with
      `PLAY-i76.bat` (your feel is the measurement).
55. **Which P133 cell is the hardware reference (decision, medium, 5 min; new 2026-10-17; records/HARDWARE-MATRIX.md,
    records/VERSIONS-AND-PHYSICS-2026-10-17.md s.3-4).** You asked for the P133 reference only; the matrix measured two:
    - **P133 lowest detail:** one physics step per frame, 32.0 ms melee (n 5) / 31.9 ms T05 (n 10), close to the 33.3 ms
      baseline; handles like the existing P166 reference.
    - **P133 developer default (preset 2, 640x480):** about 11 fps, 2 physics substeps of 41.5 ms per frame (the
      mixed-rate shape of the 15 fps design); accelerates faster (0-10 m/s 0.93 vs 1.04 s, n 3 vs 5) and jumps higher
      (apex 11.8 vs 10.9 m, n 5 vs 10).
    - **Say:** lowest detail, developer default, or both as references. Optional: whether to spend about 10 more boots per
      arm to settle the P133 jump wreck rate (6/10 vs 0/7, p 0.035).

## Owner results 2026-10-17 (OWNER-TESTS-2026-10-17 launchers, lab `ced03f7`)

- **01 clip (item 52): FAILED as a test.** `retail-sim-p166-t05-clean-descent.mp4` shows no gameplay, only a single frozen frame near
  the end. The parrun `--video` capture failed on that run; check the other clips before trusting them, fix, re-record.
- **02 retail logged 86Box (items 46 / 50): BLOCKED.** No WASD keys: the retail folder on the logging disk has the stock keypad
  `INPUT.MAP`. Fix: write the owner's WASD map (lab `C:\I76GOLD\INPUT.MAP` / repo controls) into the retail folder of the throw-away
  copy (guest filehex, read back), and print the keys in the banner.
- **SUPERSEDED the same day (owner ruling 2026-10-17, later): the baseline / default step is 33.3 ms, not 40 ms.** It is the
  developer-stated 15 fps design target as the engine runs it (2 x 33.3 ms substeps; docs/records/DEV-GAME-CLUB-I76.md). This
  overrides every "~40 ms" in agent briefs: the owner-facing 86Box play launchers use the graphics settings that give ~33.3 ms
  median frames on the emulated P166 (melee and T05, n >= 3), and the physics-step study starts at 33.3 ms. Lab launcher for the
  modern port: game-dd-20261003\TEST-step-33.bat (I76_FIXED_STEP=30).
- **New owner preference (2026-10-17): the owner-facing 86Box play launchers default to graphics settings that give ~40 ms
  frames (= ~40 ms physics steps, ~25 fps) on the emulated P166**, not lowest detail. Measure which detail / resolution combination
  lands at ~40 ms (melee and T05, n >= 3), then set it in the 02 / 03 DEF writers. The reference measurement runs keep their own
  configs; this is the play default (and the mid-bounds starting point of PHYSICS-STEP-STUDY-DESIGN).
- **04 GOG music files by ear (item 47): PASS, all four match** (3 = Theme, 15 = Malochio Down, 16 = Skeeter Gettin' Medieval,
  17 = Ovum Bisquit). `I76_MUSIC_DISC_ORDER` is confirmed and can become a default.
- **05 retail music + resume (item 49): PASS, "perfect in each way"** (menu track loops alone, credits track, Replay continues).
  `I76_MUSIC_RETAIL=1` + `I76_MUSIC_RESUME=1` is ready for the promotion gate.
- **06 / 07 F2 bookmark (item 48): UNCLEAR.** The owner was not sure what the test asked or whether it was designed correctly.
  Redesign: explain the bug in one sentence, make the steps unambiguous (or automate the clicks), and state the expected screen.
- **08 / 09 promotion 18 (item 36): prefers 09 (dense to 300 m) over 08.** Signs / ground / stutter verdict and the hold decision
  not given yet.
- **Not run:** 03, 10 (daily driver smoke, items 1-2), 11 (item 51).
- **Second-pass feedback, fixed the same evening** ([records/OWNER-FEEDBACK-FIXES-2026-10-17.md](records/OWNER-FEEDBACK-FIXES-2026-10-17.md)):
  02 / 03 click through about twice as fast (retail T05 hand-over 108 -> 53 s guest, Gold melee 90 -> 35 s; n 1 each);
  08 / 09 also start on the hill top after a Replay (the placement was once per process); the daily-driver pointer
  offset is a scale error (pencil up to 242 px off the pointer at the sides, menus drawn 16:10), fixed on the twin
  (pencil within 8 px). **Re-test:** 02, 08 with a Replay, and the new `12-cursor-fix.bat`, then say promote yes / no
  (proposal and gate in the record).

## Console session 2026-10-18 (tick candidate 19, controls 18, co-op list, LAN cells; ~45 min)

Everything here is read-only for the daily driver: the tick build lives in the lab twin, promotion 19 happens only on your word.

| # | minutes | what | where | look for |
|---|---|---|---|---|
| 1 | 10 | **Wheel and pad feel on the tick.** Drive one lap of the T06 strip or a melee on `PLAY-TICK.bat`, then the same on `PLAY-balanced.bat` | `C:\Users\james\i76-uncap-lab\game-dd-20261003\` (PLAY-TICK launches game-tick, proxy tick19c 6846c2d4 since 16:30; game-tick is now a copy of the daily driver plus the tick presets, retail music + resume, menu-pointer fix) | steering response with the wheel and the pad: same or better than balanced? Any lag or notchiness? (records/TICK-FINISH-2026-10-18.md s.9: measured 4.2 ms with a synthetic pad; no real wheel was attached) |
| 2 | 8 | **Flamers.** A fight with a flamer car (melee loadout with the Gas Launcher, or a mission with AI flamers) on PLAY-TICK and on PLAY-balanced | same | does the flame feel strong enough on a car, and do the impact sprites look right? Lab (s.11): the tick burns a T05 car dead in ~40 s (1997 timing ~25 s, promotion 18 not dead after 38 s; n 3 each). The earlier "0 hits" was the T05 road-closed bar: with `I76_BREAKABLE_BOX=4` (in the driver's and the tick presets) no loop can burn it, stock included. Decide: a per-tick flame damage factor to match 1997, and keep or patch the box switch |
| 2b | 5 | **Your first playtest notes, re-checked on PLAY-TICK** (s.10): tracers leave the car and streak all the way (33 and 66); tyre / road / wind loops steady; menu music loops, mission music resumes after Replay / Esc; J K L ; hardpoints and O radar camera work; menu arrow sits on the pencil | same | anything still wrong, say which launcher (33 or 66) |
| 3 | 5 | **T05 signs and barricades** on PLAY-TICK | same | signs fall as the bumper touches them (lab: 0.09 m into the post), barricades knock off about 2 in 3 rams at 20 m/s |
| 4 | 5 | **Tracers and missiles at 120 fps** on PLAY-TICK (PLAY-16x10 style conf) | same | continuous from the muzzle, no freeze on the first frame |
| 5 | 3 | **Controls 18 in a mission** on the daily driver | `PLAY.bat` | J K L ; fire hardpoints 1-4, O radar camera, Shift+' team scores, C cycles weapons, grey arrows orbit the chase camera |
| 6 | 5 | **Co-op list** on the PC LAN copy | `C:\Users\james\Games\Interstate76-LAN-2026-10-17\PLAY-LAN.bat` > MULTIPLAYER > HOST > IPX | 15 stock arenas then Co-op Scene 1-17; The Crater loads the stock Crater |
| 7 | 10 | **LAN cells still open** (records/LAN-MATRIX-2026-10-18.md s.7-9; the laptop, Michael, Andrew and Deck cells all ran on 2026-10-18): 5 players, a co-op win and a late join, a 3-human Co-op Scene 17. Needs the laptop, Michael's Mac and the Deck free of the family's game; then tell the session to resume | laptop, Michael, Andrew, Deck | every machine already carries the respawn-fixed pack (proxy ac44e2c2); restart the games on the laptop and Michael's Mac to load it; host from the PC LAN copy with NO. DRIVERS raised above 4 |

Verdict wanted: promote 19 (tick) yes / no / after fixes; anything in 1-4 that feels worse than balanced, say which.

## Console session 2026-10-19 / morning 2026-10-20 (tick19f-av, the 41.667 ms tick, your playtest notes fixed, LAN in the lab tick copy, scenarios, AI melee; ~60 min)

Built and gated 2026-10-19 (records: TICK-FINISH-2026-10-18.md s.12-18, FRAME-BOUND-SYSTEMS-2026-10-19.md, TWO-CLOCKS-2026-10-19.md,
DRAW-DISTANCE.md 2026-10-19, COOP-LIST-ENTRIES-2026-10-18.md s.7-8, AI-MELEE-M1-2026-10-19.md). Everything is in lab copies; the daily driver is
untouched and still has none of it. Before you play: no automated run should be muting anything any more (the global watcher is retired; each run
mutes only the game it started, per process, and clears the mute Windows remembers for that copy when it ends, so your copies start with sound).
Lab runs can no longer touch your car: since 2026-10-19 every automated run starts its game with `I76_SHM_SUFFIX=<its folder name>` (and its own desktop), so its trainer / telemetry blocks are separate from the ones in your game (a proxy built before this ignores the key; the launch scripts then say so and do not run it beside you).
The overnight multiplayer lane (2026-10-19 night: join / leave any time, AI bots fill open slots, co-op enemies per joiner) adds its own "Morning 2026-10-20" section below when it finishes; read that one before any LAN cell.

### A. The tick candidate tick19f-av (2eb345d1) in your tick copy: `C:\Users\james\i76-uncap-lab\game-tick\PLAY-TICK.bat` (= PLAY-TICK-33), `PLAY-TICK-42.bat`, `PLAY-TICK-66.bat`

Your 2026-10-19 playtest notes, what was found (s.16-18) and what the build does now:

| your note | finding | in this build |
|---|---|---|
| sign sound missing about half the time | the posts the box sweep knocks off had no engine contact, so no contact sound (0 of 33) | the sweep plays the contact sound: 33 of 33 (n 3) |
| cutscene stutters on W with the camera outside | an early tick restarted the script camera's blend from the older view | 19 of 44 stutter frames -> 0 of 24 |
| death camera too fast? / sky speed wrong | both scaled to the tick rate, not 1997's: 240 deg/s and 0.030/s at 33 | 192 deg/s and 0.024/s at every tick length = 1997 (driver: 160 and 0.020) |
| music not consistent | no dropped cue in 12 boots; the silences are the data-track missions (M06 / S02 / S06 / S01) and retail's 0-60 s gap after a run ends | unchanged (rules you chose) |
| tracers 2x thicker / denser | a look difference: the tick redraws a tick-long streak every frame (about 4x the path coverage of 1997's dashes), same line width | unchanged; a one-frame streak like the driver's is a small change if you want it (decision 7) |
| instant melee crashes every time | the tick's object walk released references; 13 of 13 crashes on Scene 1 (Co-op) | fixed: 0 crashes in 9 + 3 + 3 rows, gate instant-melee rows 3 / 3 |
| multi melee: no AI cars | your copy had "Scene 1 (Co-op)" remembered as the arena, Hope Springs was never loaded (the wide-menu pointer was 242 px off the pencil) | the pointer is on the pencil (within 4 px; `I76_CURSOR_MAP_DGV=aw`); pick Hope Springs (4 AI) on purpose |
| two helicopters in T05 | the 1997 mission has two (stock / driver / tick all count 2) | nothing to fix |
| bouncy / fast on 33, T05 jump low with the nose down | ONE clock in 1997: the car step was the frame time, capped at 50 ms; at 33 ms the bounce runs 1.25x faster and the jump sheds speed per step; 41.667 ms = the 1997 coupling (TWO-CLOCKS) | PLAY-TICK-42.bat; the "lip clips" at 42 were the harness placing the car crooked (0 of 66 jumps clip, same as the stock loop, s.18) |
| terrain redrawn at the top of the T05 intro road | the split distance, not the height error: distance x96 / height-error x24 resolves the canyon ridge at no fps cost (112.6 vs 112-116) | all three PLAY-TICK presets carry terrain A 96 / B 24 |
| "sometimes it seems like it spawns" | not understood: say what spawns, where | |

| # | min | what | look for |
|---|---|---|---|
| A0 | 10 | **33 vs 42 vs 66, the ruling** (TWO-CLOCKS). T05 canyon jump on each; sign rams; a bounce over a ditch. The lane recommends **42 as PLAY-TICK's default** (the 1997 coupling: bounce period, jump arc and landing pitch match the stock loop; the s.14 hazard factors are exactly 1 there); 33 stays the default until you rule | the jump at 42 lands flat-ish at a sensible speed (33: low, nose down; the driver: too long / high); controls still feel right at 42; which one do you want PLAY-TICK to be? |
| A0b | 10 | **The tick range, to pick the exact value** (TICK-FINISH s.19; proxy now tick19g adc4fd49, the old one kept as `STRLKUP.DLL.2eb345d1-pre-19g`; console gate s.19.6 PASS 2026-10-20 on every launcher, S / D PASS, 0 crashes; the twin `game-dd-20261003` carries the same proxy since 15:20, s.19.7: before that its PLAY-TICK ran the old proxy = no tick and the mouse off the buttons): `PLAY-TICK-36 / -39 / -42 / -44 / -47.bat` (1997 period PCs ran 36-47 ms; 41.667 = the 1997 car step) plus the outliers -33 and -66. Same T05 jump and ditch on each. Optional, single player: `PLAY-TICK.bat 43` (any 16.7-66.7) or a `tick-ms.txt` beside it with one number; `PLAY-TICK-CHOOSE.bat` explains and asks. In a network game every player should run the same tick | the bounce slows in step with the tick (0.25 s at 36 to 0.33 s at 47, 0.29 at 42); jumps differ by under 1 m/s at take-off inside 36-47; say the value you want as PLAY-TICK's default |
| A0c | 8 | **The T05 jump, measured per tick (TICK-FINISH s.20, 2026-10-21).** Your "33 does not make the jump, too much nose down; 44 does": at 33.3 ms the car leaves the lip 2.5 m/s slower (47.4 vs 49.9 m/s, 4 of 7 clear), at 41.667 it jumps as retail 1.0 did at ~42 ms on the emulated P166 (49.9 vs 50.0 m/s, apex 10.0 m both, 10 of 10 vs 6 of 6). Cause: one per-substep term, the speed lost following a slope, which 30 steps/s lose 1.25x as fast as 24; 44 only lost a little less of it. Nothing broke since 10-19 (no car-physics change in tick19g). Your ruling stands: 41.667, where that term is exactly 1. A fix that makes 33 / 36 / 39 jump like 41.667 (I76_SIM_TICK_SLOPE, default on, nothing changes at 41.667) is STAGED, not installed: lab `builds\jump-fix-20261020\STRLKUP-jumpfix-ed772c2.dll`. Side finding for main: the LAN key I76_COOP_AI crashed a lab game on a trainer re-placement (s.20.7) | on PLAY-TICK-42: the canyon jump from the hill-top at full throttle clears and lands flat-ish; if the stage build is installed later, PLAY-TICK-33 should then jump the same as 42 (bounce still faster) |
| A0c | 10 | **Draw distance and terrain change on T05** (records/RC-DRAW-FPS-2026-10-20.md; staged, NOT installed: `i76-uncap-lab\builds\rc-draw-20261020\stage\` = every tick19-*.psd1 with far clip / roads / bushes back to 1800, the x96 split out, I76_TERRAIN_LOD_B 4 + I76_TERRAIN_HYST 20 + I76_TERRAIN_FREEZE 300,40, proxy STRLKUP-rcd 65a62504; `stage-alt\` = LOD 24 as promotion 18 + FREEZE 300,40 only). Your barn: the RC's 1200 m far clip (it came from the balanced preset); the fps: the x96 split with the far distance (mean 107.7 vs 117.9 headless, T05 route); the change while driving: x96 moved it outward (beyond 300 m 1.6-2x). Main installs after your word; then drive T05 from the start over the hill toward the barn on PLAY-TICK-42 | the barn from the hill top; far hills and ridges no longer change while you drive (lab: change beyond 300 m 605 -> ~1 px/s, split / merge events 40 -> 17 per s); the ground near the car still changes (no switch removes that; geomorphing is proposed); say if the ground looks too flat (then stage-alt); and where you read the fps (the lab cannot reproduce 99; headless reads ~7 % high, gate row 9 measures it at the console) |
| A1 | 8 | **Flamers** (s.12, s.18). Burn a car with the Gas Launcher on 33 and on 42; flame a T05 road-closed bar | a car dies after ~10 s of contact at every tick length (1997 timing; the driver needs 3x that; tick19g asks ~85 / s at every tick length with no preset key (the interim 3.5 line is gone, s.19)); the bar burns (about 2x the 1997 rate, decision 4) |
| A2 | 8 | **Per-frame hazards at the 1997 rate** (s.14). Sit in an oil slick / dropper patch, stay pinned against a car or wall, stand near a burning wreck, dodge a radar missile (DrRadar / Cherub) | each costs about what it did in 1997; missiles not lazy, not too sharp (the missile turn is from code only, unmeasured) |
| A3 | 6 | **The notes table above, re-checked in play**: sign sound on every post, W during an outside-camera cutscene, the death camera and the sky, music, instant melee into Hope Springs (4 AI) | anything still wrong, say which launcher and which row |
| A3b | 4 | **The pointer on the wide menu** (`aw`): main menu, Instant Melee arena list, garage and its reminder pop-up, the save screen (pick an empty slot: the gate's YES wrote only the scratch slot, 12 / 12 after a harness fix), the Esc menu in a mission | the hand and the drawn pencil agree everywhere; a wrong row picked anywhere = say where |
| A3c | 2 | **Terrain at the T05 start**: from the canyon road at the mission start look at the ridge behind the intro road (the lane's view: facing +x from x 8490, z 44520) | the ridge keeps its shape as you drive; if that is not the spot you meant, say where you see the redraw |
| A4 | 3 | **Suburbia on 66** (s.13, not reproduced in 10 boots): start it 3 times on PLAY-TICK-66 and drive forward 10 s | houses appear = it was the dark spawn view (half the spawns face a flat plain); still flat = screenshot |
| A5 | 2 | **66**: nothing to hunt; 66 steps everything 15 times a second so aim and steering feel coarser, tracers come in 13 m pieces | only say if 66 feels no worse |
| A5b | 30 | **86Box retail 1.0 on the emulated P166 (the 1997 reference; items 46 / 50). Fixed 2026-10-19: the game now starts by itself, home-row keys.** (1) Double-click `C:\Users\james\i76-uncap-lab\OWNER-TESTS-2026-10-17\02-86box-retail-logged.bat` (disc 2 is mounted for you); hands off for about 1.5 min while Windows boots and the game starts itself and lands in the T05 cockpit. (2) The keys are your daily-driver home-row map: W S A D drive, Enter fire, J K L ; hardpoints 1-4, O radar camera, C or Tab cycle weapon (no Shift+' team scores: retail 1.0 has none). (3) Drive T05 to the canyon jump and compare with PLAY-TICK on the hill top. (4) To exit: Esc, then arrow keys + Enter for Abort Mission > Exit Game > Yes. Then Start > Shut Down, close 86Box when it says it's safe, and the window prints `summary.md`. (5) Your desktop shortcut `i76 x86box ref` (PLAY-P166-LOGGED.bat) now also starts the game by itself, to the main menu (same keys, saves kept). | W S A D / J / O work; the jump and the landing feel like 1997; the frames in the summary (this PC measured a 41-42 ms median in T05 today, not 33: say if it feels slow); Instant Melee clicked by hand: does ENTER AREA work for you? (it would not take the agent's injected clicks) |
| A6 | - | **Verdict**: promote 19 yes / no / after fixes. Promotion 19 now also carries the LAN pieces (IPX files, the 27 arena files, the LAN keys) that the driver lacks. Candidate folder: `C:\Users\james\i76-uncap-lab\builds\tick-finish-20261018\promotion-19-candidate\` (README, MD5SUMS.txt; the next build folds in s.18's rate-aware flame default and whatever the overnight multiplayer lane lands) | |

### B. Network from the lab tick copy (PLAY-TICK now hosts and joins; records/MULTIPLAYER.md 2026-10-19 section; superseded by the overnight lane's "Morning 2026-10-20" section if it is there)

| # | min | what | look for |
|---|---|---|---|
| B1 | 3 | MELEE > MULTI MELEE > HOST | lands straight on the IPX host form (no MODEM / INTERNET / NULLMODEM page); JOIN lands on the IPX game list |
| B2 | 3 | The AREA OF PLAY list | 15 stock arenas, Hope Springs (2 / 4 / 6 AI), the 7 scenarios as "name (Scenario)" in the smaller handwriting font (only "Trailer Pk. Madn." is shortened), Scene 1..17 (Co-op) |
| B3 | 5 | Host Hope Springs from PLAY-TICK and have one family machine join | works today with the **stock arenas only**: the family machines still run the 2026-10-18 pack, and every addon arena's checksum changed |

### C. After the pack rollout (all machines at once, when the family machines are free; I do it on your word; pack `i76-uncap-lab\builds\mp-pack-20261019-final\`)

| # | min | what | look for |
|---|---|---|---|
| C1 | 10 | **Hope Springs (4 AI)** with 2+ humans | 4 computer cars on every screen, they attack, a kill shows "<AI name> was destroyed by <you>" and scores on every screen; when all 4 are dead the arena reloads with scores kept; **a joiner's kill of an AI was never measured** (the scripted joiner never finished one), so one of you other than the host kills one |
| C2 | 5 | **A scenario with a joiner** (Mondo Burger, Pretty Bus) | AI cars on both screens; joiners respawn; the host's death or a loss reloads the scenario for everybody; a win ends the game |
| C3 | 10 | **Co-op cells still open**: a co-op win and a late join after it, a 3-human Scene 17, 5 players (raise NO. DRIVERS with + first) | |

### D. Daily driver, `PLAY.bat`: controls 18 keys in a mission if not done (J K L ; hardpoints, O radar camera, grey arrows orbit) | |

### Rulings given 2026-10-20 evening (console play-test of the release candidate)
- **Tick default = 41.667 ms** ("the tick length where the code scaling factors are exactly 1 seems like the 'true' tick
  length to me and we should go with that unless it is absolutely non-performant"). PLAY-TICK.bat becomes the 41.667
  launcher in the next staged candidate set (with the terrain / fps and jump fixes below), not by hand in the folder.
- **Terrain: change LESS, not more detail.** The x96 split (A) was the wrong direction: the complaint is terrain that changes
  while driving (steep edges and far things most). The RC-draw lane re-ran with churn-while-driving as the metric and fps
  over the whole T05 route (the owner sees 99 on all of T05; the gate's trip row drives another route and read 120).
- **Jump:** 33 ms noses down too much and misses the T05 jump; 44 makes it; the jump lane measures 33 / 41.667 / 44 / 47
  against promotion 18 and the 1997 emulator and names the per-tick quantity; 41.667 must jump as 1997 did.
- **Mac / laptop:** converge to ONE app per Mac where everything works (sound, hosting with AI cars, Esc menu by mouse and
  keyboard); old Mac versions and helper folders deleted (one tarball kept per machine); no Mac daily driver to protect.
- **Launchers:** one PLAY.bat for single player and LAN at promotion 19; `--legacy-multiplayer` flag (I76_MP_MENU=0) added.
- **Debug tool:** DEBUG.bat (TRAINER.bat a shim), full-state teleport (pose + velocities), ships in the daily driver.
- **AI melee (2026-10-20 night, from Andrew's Mac):** "the game restarts when I play the (6 AI) version ... and the AI players are
  dead, but shouldn't they be respawned instead and the points tallied like they were players?" Ruling: no wave reload; dead
  AI respawn like humans, and AI kills / deaths / score are tallied and shown like players' (AI-MELEE-M1 decisions 4 and 5
  answered). A lane is building it (records/AI-MELEE-RESPAWN-2026-10-20.md).
- **AI in every arena (same night):** "Instead of special levels for ai players, shouldn't there be ai cars for all player
  slots not occupied by a human for all levels?" Ruling: yes. NO. DRIVERS sets the slots; humans take slots as they join;
  every other slot is a computer car with a scoreboard row, in every melee arena; the "(2 / 4 / 6 AI)" entries go away;
  a host switch keeps the stock behaviour. Same lane, phase 2.
- **AI difficulty (same night):** "Seem to be spanking all these guys" / "Shouldn't the game difficulty setting change it in
  the melee mode too?" Facts: the AI run at the stock skill 3 of 1..5, untied to anything. The shipped exe 6319abf7 and
  shell a300db63 DO have the Difficulty Level option (Wimp / Champ / Badass; the owner sees it in the pause menu; an
  earlier record's "retail 1.0 has no difficulty option" described the emulated disc, not our build). Ruling: the
  existing setting drives the melee AI skill (host's setting rules); the lane also measures what the setting does to
  player damage in our exe and reports what value the owner has been playing on; campaign rule unchanged by default. Lane: records/DIFFICULTY-OPTION-2026-10-20.md; the AI lane measures skill 3 / 4 / 5 and adds --ai-skill.
  **Done (staged, lab `builds\difficulty-20261020`, proxy 5b003fd2, installed nowhere):**
  - The menu's Difficulty Level now sets the host's AI in network melee: Wimp = level 4, Champ = 3 (as before), Badass =
    1. The stock scale runs 1 = best .. 5 = worst, so the first table (Badass 5) would have made Badass the softest.
  - Measured on the host n 1 per value; a joiner's setting changes nothing (n 1).
  - Offline, the setting doubles / keeps / cuts to 0.75 the PLAYER's own bullet and flame damage (measured 50 / 25 / 18 per hit).
  - **Your driver and LAN copy are on Wimp**, so x2 damage in the campaign.
  - Wanted from you: (a) play a network AI melee at Badass and at Champ once a pack carries it; (b) set the copies to
    Champ, or leave them at Wimp?

### Ruling 2026-10-21 morning: ship for Arsenal (Gold AND Nitro), multiplayer on Nitro, non-destructively
"let's do the work to understand and fix nitro same as we did for gold. we'll plan to ship for arsenal so it's complete
... from a multiplayer perspective we'd want nitro to be the basis instead of gold ... nondestructively, so that
community play of nitro multiplayer is unperturbed. perhaps it's a new menu item we'd add separately". Plan:
docs/ARSENAL-PLAN-2026-10-21.md. Owner to name the new menu entry ("AI DROP-IN" / "CO-OP / AI MELEE" / "ARENA+").

### Ruling 2026-10-21 midday: priorities and the Nitro option placement
"it's different missions entirely. we don't have to bend over backwards to combine them ... for now let's understand
nitro, get the settings dialed in for gold, get nitro working as well as gold is, implement netplay enhancements for
nitro." Menu data edits crash Nitro (an edited SCENARIO.DAT: Unhandled Exception at the console). "the right place for
the ai drop-in option is a checkbox inside the network play configuration, maybe a few of them for other features we've
added (human drop-in, etc.)" -> N2 (the entry name) is superseded by checkboxes on the host form; names of the checkboxes
still the owner's. NAME RULED (same day): **ARENA+**, "Every arena plus the original '76 missions, with AI filling
the open slots." (N2 answered: the label of the checkbox group / the mode). Gold graphics: a rebaseline ladder (records/REBASELINE-2026-10-21.md) the owner drives rung by rung
after the promotion-19 gate. Future epic noted: AI-upscaled menus and fonts (lab spike only, records/UPSCALE-SPIKE).

### Decisions wanted
1. Promote 19 (A6). 2. AI melee defaults (AI-MELEE-M1 s."defaults"): count from the arena file (2 / 4 / 6), AI hostile to all humans, wave
respawn with scores kept, AI names only in the kill message, -500 for a death by an AI. 3. Scenarios: keep "host death reloads the scenario"
or build melee respawn for the host (needs script edits per scenario, COOP-LIST-ENTRIES s.8.3). 4. Flame on a road bar burns about 2x the
1997 rate under the car-calibrated factor (s.12.4): accept, or a separate bar factor. 5. The daily driver's AI skid / horn rolls run at 5x the
1997 rate (FRAME-BOUND s. recommendations): leave, or scale in promotion 19. 6. PLAY-TICK's default tick: 33.3 (today) or 41.667 ms (the
lane's recommendation, A0). 7. Tracers under the tick: keep the tick-long streak, or draw a one-frame streak like the driver (s.17.6).

### Open / not measured (so you know): joiner AI kill, AI melee and scenarios across two machines, teams for AI (`_TEAMS=1` never run),
radar-missile turn in game, sustained-scrape damage per second, two of four T13 "god-held player dies" deaths (also in the stock loop), the
Deck joins co-op / AI arenas without the AI sync (its own proxy has no pack switches), a stuck AI car can hold up a wave (no timeout).

## Morning 2026-10-20 (what is left for humans after the cross-machine matrix; records/LAN-MATRIX-2026-10-20.md)

The machines did the rest this morning (PC + Andrew's Mac + Michael's Mac + laptop: joins, leaves, re-joins, AI fill counts,
co-op copies, 4 players, the host quitting in every kind of arena, a Mac hosting; 0 crashes). Left for you:

0. **Deck**: files DONE (15:10 arena files by main; 15:25 proxy cf4f81da + a new LAN launcher by the Deck lane,
   records/LAN-MATRIX-2026-10-20.md section 8; rollback tested, 0 differences). The Deck boots through the new launcher with
   every multiplayer hook in place (n 1), but it went to sleep at 15:34, before its join on the new pack could be measured.
   **Your step, once, on the Deck:** Steam (Game Mode) > Interstate 76 > gear > Properties > Launch Options: change
   `i76-deck-launch.sh` to `i76-deck-launch-mp.sh`, so the line reads
   `"/home/deck/Games/Interstate76/i76-deck-launch-mp.sh" %command% -glide` (it only adds network-game switches, so it is fine for
   single player too; to go back, change the name back). Then, with the PC hosting from `PLAY-LAN.bat`: MULTI MELEE > JOIN
   (straight to the list now) in Suburbia, then Hope Springs (4 AI) (with 2 humans the PC and the Deck should both show 3 AI
   cars fighting, 1 parked far away), then Scene 5 (Co-op) (an extra enemy copy comes in for the Deck). Pick any car but
   Jade's (the Deck's own Jade's Car file is refused by a stock host). Keep the Deck awake (touch it, or raise its suspend
   timeout): Game Mode sleeps after a few minutes without input and drops out of the game. Rollback: `bash
   ~/i76-overnight-20261020/polish-deck/deck-rollback-polish.sh` on the Deck. Everyone else runs proxy cf4f81da (teams + polish:
   Mac shortcut, no stray co-op copy after a host change) since 10:00.
1. **Feel of AI fill**: PC hosts "Hope Springs (4 AI)"; with 2 / 3 / 4 of you there are 3 / 2 / 1 computer cars. Too many, too few?
   (`I76_AIMELEE_FILL` changes the total; now 5 combatants.)
2. **Feel of the co-op extras**: "Scene 5 (Co-op)" with 1-3 joiners: each attacking enemy brings one extra car per joiner.
3. **Kill credit**: shoot an AI car dead as a JOINER (not the host) and check that every screen shows "... was destroyed by
   <you>" and your score. Nobody could measure it this morning (no remote aiming).
4. **Team play** (item 6 below).
5. On a Mac too, MULTI MELEE > HOST / JOIN now go straight to IPX (pack `mp-pack-20261020-polish`, proxy cf4f81da, 10:00). To leave a game: Esc >
   Abort Mission > Abort Mission > Yes.

6. **Teams** (teams lane; records/MP-TEAMS-2026-10-20.md; needs the next pack, proxy 31efcf7a): PC hosts "Hope Springs (4 AI)"
   with **TEAM PLAY** ticked; everyone picks a team in the pop-up (not Men In Black: that is the AI's team). Expect: the AI go
   for other teams only; when someone quits, the AI that comes back plays on HIS team (it hunts the others, not his mates);
   when someone joins, an AI of his team steps out first. Tell me who scored for kills - the lab could not make any.

7. **Host leaves a co-op scene** (records/LAN-MATRIX-2026-10-20.md section 7.2): when the host quits Scene N, another machine
   takes over and the scene restarts from the beginning for everyone (measured in the lab and on Andrew's Mac). Keep it, or
   should the scene go on where it was? Tell me.

## Mac converge 2026-10-20 evening (records/MAC-CONVERGE-2026-10-20.md; laptop: `~/Applications/Sikarugir/Interstate 76 Gold.app`)

Your laptop now has one I'76 app, `Interstate 76 Gold.app` (the family pack, with your saves; GATE and the test apps are gone; the
old app is in `~/i76-archive-20261020/` as a tarball). Andrew's and Michael's Macs: one app each, Desktop **Interstate 76 LAN**.

1. **Esc menu by mouse** (the fix, proxy 0ce90a90; measured on Andrew's Mac, not on the laptop because its screen was locked):
   start any mission (or MULTI MELEE > HOST), press Esc. Click **Cancel** (bottom right): the menu must close. Esc again,
   click **Play Options**, then click the LOWEST rows there and **Back** / **Cancel**: each must react where you click. Then
   with the keyboard only: arrows up / down, Enter, Esc. Report any row that lights or acts somewhere other than under the
   pointer, and anything the keyboard does not do.
2. **Sound**: menu music and engine sound in `Interstate 76 Gold.app` (it was the GATE app that had none).
3. **AI cars**: MULTI MELEE > HOST > **Hope Springs (4 AI)** (scroll the AREA OF PLAY list down; the AI arenas are after A Lot
   of Asphalt) > BROADCAST GAME: 4 computer cars attack you. The Crater, Creeper Canyon and the other stock arenas have none
   (by design). Want AI in every arena? Say so (a ruling, not built).
4. Nitro: `Interstate 76 Nitro (DxWnd).app` and `Interstate 76 - DxWnd Settings.app` were kept (they use the same app's
   folder). Delete them if you do not want them.

## AI cars respawn, score like players, and fill every arena (2026-10-20 night; records/AI-MELEE-RESPAWN-2026-10-20.md)

Staged as pack `i76-uncap-lab\builds\mp-pack-20261020-airespawn\` (proxy 8f8da929 + the three "Hope Springs (N AI)" files moved
out), **on no machine yet**. Main deploys it to every machine at once when you say so (PC LAN copy, laptop, both Macs, Deck).

1. **With Andrew (the test you asked for):** you host on any machine, Andrew joins. HOST > pick any stock arena (Suburbia,
   The Crater, Hope Springs ...) with **NO. DRIVERS 8** > BROADCAST GAME: 7 computer cars when you are alone, 6 once Andrew
   is in. Kill every computer car you can. Each one must come back about 5 s later at a spawn point; the arena must never
   restart. Press **Tab** (the scoreboard) now and then: the computer cars must have their own rows (their names, kills,
   deaths, score), Andrew's screen must show the same numbers, and "... was killed by <AI name>" must show when they get one
   of you. When Andrew leaves, a computer car must take his place. (Lab: 21 respawns, rows identical on both screens, NO.
   DRIVERS 2 / 4 / 8 in three arenas; nothing between two machines yet.)
2. **Too easy?** (You said you were "spanking all these guys".) The skill runs 1 = best .. 5 = weakest; it was 3. Your copies'
   menu Difficulty Level is Wimp, which the new proxy maps to 4 (easier). Pick: Champ (3), Badass (1), or a fixed
   `set I76_AIMELEE_SKILL=2` in PLAY-LAN.bat (`PLAY-LAN.bat --ai-skill 2` once the next launcher set is out). Measured: skill 5
   is clearly weak; at 1-3 the cars often hold 150-190 m off, and that matters more than the number. Your Piranha (4800
   points, armour 2800) out-armours 54 of the 66 cars they draw from.
3. **A stock game for a friend without the pack:** `set I76_AIMELEE_FILL=0` on the host gives the stock arenas without
   computer cars. Without it, an unpatched joiner sees no computer cars, and your message line says "<name> has no AI pack".

## Menu / sound polish from your release-candidate play-test (2026-10-20 night; records/MENU-SOUND-POLISH-2026-10-20.md)

Staged, not installed (main installs after a gate): lab `builds\menu-sound-polish-20261020\staged\` (proxy e61d1e3e, tick19
presets with the two new lines, launchers with `--legacy-multiplayer`).

| # | what | how to check | result |
|---|---|---|---|
| P1 | Esc > ABORT MISSION > the Replay / Reconfigure / Abort / Exit page: pointer visible and usable at once (your report A) | in a campaign mission from a bookmark: Esc, ABORT MISSION, move the mouse; if the pointer is gone, note whether the mouse still highlights items, then Alt-Tab back | not reproduced in the lab (direct mission boots, n 3); your route is the one left |
| P2 | no two-frame flicker on exit (B) | Esc > ABORT MISSION > EXIT GAME > YES; also finish / abort a mission | lab: the exit fade's 32 presents -> 0 (n 3 each) |
| P3 | barricade hits restart the hit sound (C) | T05: drive through the road-closed barricades near the ramps (x 7095..7280), two of them stand 5 m apart | lab: stock refused the 2nd hit of a pair 0.2 s apart (n 4), fix restarted it (n 3) |
| P4 | `PLAY.bat --legacy-multiplayer` / `PLAY-LAN.bat --legacy-multiplayer` (D) | MULTI MELEE > HOST shows MODEM / IPX / INTERNET / NULLMODEM; `PLAY-TICK.bat 44 --legacy-multiplayer` keeps the 44 ms tick | headless: mp-menu 0 with the flag (n 6), 1 without (n 3); the tick kept in both orders |
| P5 | the GAME NAME is the arena you clicked (E) | MULTI MELEE > HOST, click Mondo Burger (Scenario): the name reads "Mondo Burger (Scenario)", the AREA OF PLAY box too, and Mondo Burger loads (lab: 48 / 48 loads the selected file); on the Mac, if the name shows the row ABOVE the one you clicked, the Mac pointer is one row off (tell us) | lab: names right 42 / 42 (stock 15 / 42) |
| P6 | in a network game the Esc menu's keys no longer drive the car (F) | host or join, Esc, press the driving keys / arrows: the car coasts straight | lab network game: stock steer up to 0.92 / throttle 1.0 with the menu up, fix 0 / 0 (n 3 each) |
| P7 | the game folder can be renamed after a crash (G) | nothing to do; folders of copies that crashed no longer stay locked | lab: 0 registrations left of 3 killed boots (stock 3 of 3) |

## Decision: base Gold or Nitro (2026-10-21; records/NITRO-BASE-2026-10-21.md)

| # | what | how to check | result |
|---|---|---|---|
| N1 | **Ruling: keep the Gold exe as the base, or move to nitro.exe?** The GOG Nitro Pack is the expansion only: none of the original 17 scenes, 15 arenas (by file; N51-N65 are them re-laid), 27 scene movies or 492 radio voices, and its shell has no trip / garage-salvage / bookmarks. Moving means porting the trip shell, re-addressing the whole proxy, a limiter and the netcode (record, last section) | play-check both copies at the monitor: `C:\Users\james\Games\I76\nitro\PLAY.bat` (stock GOG Nitro) and `C:\Users\james\Games\I76\nitro-plus-original\PLAY.bat` (+ original files; single player > character Groove > Original Mission 1-17; host alone > arena list for M01-M15) | headless over Remote Desktop both showed "Unhandled Exception" in GOG's OpenGLide start-up (n 1 each); the same exe with dgVoodoo reached the menu (lab, n 1). Your ruling: |

## Decision: the name of the new Nitro multiplayer entry (2026-10-21; records/NITRO-MP-DESIGN-2026-10-21.md)

| # | what | how to check | result |
|---|---|---|---|
| N2 | **Name the separate Nitro multiplayer entry** (our AI fill / co-op / teams live only behind it; stock Nitro multiplayer, its JOIN list and the lobby stay untouched). Options, with the line the menu would show: (1) **AI DROP-IN** "Melee with computer drivers in every empty seat; friends drop in or out any time." (2) **CO-OP / AI MELEE** "Team up against computer cars: every arena, the '76 scenes and scenarios." (3) **ARENA+** "Every arena plus the original '76 missions, with AI filling the open slots." (4) **CONVOY** "Roll out together: co-op scenes and AI-filled arenas, join whenever you like." (5) **NET AUTO MELEE** "Auto Melee over the network: AI drivers fight beside and against your friends." | nothing to run; pick one (or your own words) | **Ruled 2026-10-21: ARENA+** with description (3), as check boxes on the network host form (AI DROP-IN, DROP-IN / DROP-OUT, CO-OP SCENES on Nitro's own missions); design section 0. Original '76 story missions / scenarios are not in it (Gold content not combined) |

## Owner play-test 2026-10-21 evening (release candidate = promotion-19 candidate, PLAY-TICK.bat, console)

Verdicts: fps full 120 on the hill (fixed); barricade hit sound restart "awesome / perfect" (C done); two-frame exit flicker gone (B done);
the barn is drawn but not the hill behind it (far clip; X4 at 2400 m had no stability issue, owner: fine, maybe not needed that high; main: ship 2000 after a soak);
hill edges / terrain redraw "maybe slightly better" only. Ladder drive (exp-rebase): R00 / R03 / R04 / R06 = same aggressive slope redraw; R07 (promotion 18's
LOD 24) = first improvement, much better, flat-tile shade changes and the bad canyon ones remain; X1 (LOD 48) further / better, the bad one unchanged;
X2 (R07 + hysteresis + freeze) no change; X3 (R07 + split A 96, log-verified) no change and same fps. Conclusion: the candidate's LOD_B 4 is the
regression (coarser threshold = bigger snaps); hysteresis / freeze invisible; the bad patch is not distance-gated -> height-error term or the
28,000-vertex guard. Rebaseline lane redirected: A-only / B-only rungs + a per-node trace of that patch (owner's screenshots Downloads\Screenshot 2026-10-21 1758xx.png).

Open items from this session:
- J1 **The jump falls short with the owner's car** (bookmark car, full throttle down the mountain, no nitrous: foot ~130 mph, exit 100-110 mph, barely across or short,
  in-air pitch-down "terrible", died on landing). The harness clears it 4/4 with the stock T05 car (foot 63.5 m/s, take-off 55.9). Jump lane 2 re-runs with HIS car and run
  (TICK-FINISH s.22 when done). He recalls tick 44 and promotion 18 made it.
- P8 Exit-menu pointer still inconsistent with real input (lab n 12 with synthetic input never lost it); P9 a zoom / framing change while arrowing down the Esc menu
  (screenshots Downloads\Screenshot 2026-10-21 1803xx-1804xx.png); P10 Up = look at the dash, Down = look back on Windows as on the Mac (input.map). Polish lane 2.
- Firewall prompts for the lab Nitro copy: owner allowed both (lab copy now has allow rules).
- Nothing drivable on Nitro yet for the owner (the port's console rows wait for the ladder).
- T1 **Ladder follow-up for the owner's eye:** the ladder's fps says the x24 split distance (R07 and the candidate alike) is the one expensive switch (1 % low 86-87 vs 102-106),
  while the height-error threshold /24 alone (R14, PLAY-R14.bat in exp-rebase) is nearly free (102) and was never driven. Drive R14 against R07 on the same slope: if R14 looks
  like R07, the interim set drops the split distance and keeps the frame rate. (REBASELINE-2026-10-21 s.4-s.7.)
- P8-P10 RESULTS (polish lane 2, MENU-SOUND-POLISH s.H-J, staged proxy da6dfbb8 + input.map 1c397955 in lab builds/polish2-20261021, not installed):
  P8 the pointer was never hidden: every Esc-menu open put it on the bottom screen edge (y 1437 of 1440, 12/12) through the cursor map; fix I76_MENU_PTR_CENTRE (5/5 mid-screen).
  P9 after an Alt-Tab (or a screenshot tool taking focus) the paused game drew one fresh frame from the wrong camera, so arrow presses alternated two pictures (44 % of the
  background); fix I76_MENU_DRAW (0.3-0.5 % left = edge shimmer). Stock behaviour, not the tick. P10 our map had Up = look back / Down = dash, the stock GOG map the other
  way; staged map swaps them. OWNER QUESTION: the Mac carries the identical map (same md5), so does Up look at the dash on the Mac today, or back? One key press settles
  whether the staged map ships to both or to Windows only. Tests for the owner: Esc without touching the mouse (arrow mid-screen), ABORT MISSION > EXIT GAME by keys and by
  mouse; Esc, Alt-Tab away and back, arrow up / down (picture still); Up / Down in the cockpit with the staged map.
- J1 RESULT (jump lane 2, TICK-FINISH s.22): the owner's car and run reproduce his speedo (foot 127-129 mph, leaving the ramp 111-117; the needle drops ~5 mph per tick in the
  air). The tick is not the cause and the car is not the cause. The 'pitch down' is the 1997 take-off kick: if a front wheel has already left the ramp on the last grounded
  step the nose gets -15 deg/s (one wheel) or -30 deg/s (both) and the engine holds it for the whole flight; both-wheel kicks land at -85 deg and roll over (destroyed 3 of 5
  at 41.667, 0 of 3 at 44, retail 1.0 the same: 12 both-wheel kicks in 31 descents). Phase sweeps n 25 per tick: both-wheel kicks 13 / 4 / 2 / 2 / 11 at 33 / 41.667 / P18 /
  44 / 47 ms, not monotonic = luck of timing at the lip, not the tick. 6 m off the 10 m ramp road = no launch (1 of 12 made). The earlier harness '4 of 4' was one stored
  start replayed. **RULING NEEDED J2:** a switch that eases every in-flight pitch spin back to the normal slow nose-drop (lands above -45 deg, survives) DEPARTS FROM 1997;
  ship it on or off? Proof plan is in s.22. No launcher changes the outcome today; staying inside the 10 m road is the only thing the driver controls.

- P10 RESOLVED by your answer (Up looks at the dash on the Mac): the staged input.map ships to the Windows copies only; the Macs keep theirs.
- ARENA+ RESULTS (nitro-mp lane, NITRO-MP-DESIGN s.0.5.10-0.5.12; host build 5cb92ac2 = source 91d2b14 staged in lab builds/nitro-mp-form with README + MD5SUMS, not installed):
  the two boxes ([X] ARENA+, [X] CO-OP SCENES) sit in the empty middle of the host form's car panel with your description text above them (screenshot
  captures/nitro-mp-20261021/arena-plus-hostform-shipped.png; the first placement covered the OPTIONS header and was moved). Both off = stock 604 session, nothing written;
  ARENA+ on = session type 7676; CO-OP SCENES adds Nitro's P01-P19 to the list (24 -> 43) and turns ARENA+ on. Isolation cells c1-c4 n 2 each pass (patched / stock host x
  patched / stock joiner: only a patched joiner sees an ARENA+ session; stock players never see it). The tick-vs-AI conflict is fixed (the AI hook now chains through the
  tick's gate): ARENA+ with the tick on, n 3, rows agree, AI count / joins / respawns / kills credited both ways. One access violation came from a LAB-ONLY shooter switch a
  real game never sets; it gets a guard before that instrument is used again. OPEN: the description wording ("...the original '76 missions..." vs "the Nitro missions").
- CROSS-MACHINE ARENA+ PASS (needs you or a boy at a Mac; all three Macs carry "Interstate 76 Nitro.app" with proxy ad904941, which joins fine): on the PC I bring up the
  host from the lab copy on the real network card (UDP 54792, net 00000001, the Macs' IPXWrapper defaults), HOST > IPX, tick ARENA+, BROADCAST GAME; on the Mac:
  MULTIPLAYER > MELEE > JOIN > IPX, pick "ARENA+ ..." and JOIN GAME. Say when someone is at a Mac and I run it with you watching. Mac caveats still: no tick on the
  Macs yet (24 fps cap), music unverified, EVO4 output delays startup ~40 s, Esc at the main menu quits.
- NITRO ON THE PC RESULTS (nitro-port lane, NITRO-PORT s.9): far clip on Nitro's own P05 (2 km cockpit road leg, n 5-6 per distance) = median 120 at every
  distance, 1 % low 101.7 at 1200 m vs 90.9 at 1800 and 90.7 at 2000 (2000 costs nothing over 1800 on Nitro either); the sim clock reads 1.000 on every console
  boot alone. PROBLEM: on the PC the Nitro menu pointer is held inside the top-left 640 x 480 of the 3440 x 1440 display (asking for mid-screen gives back 639, 479;
  our cursor map has no effect, n 1 each), so the Nitro menus are unusable by mouse at this resolution on the PC build; next step is to find what confines it
  (nitro.exe, NITSHELL or dgVoodoo) or fall back to the u32x window for Nitro. The Mac proxy ad904941 built byte for byte on the PC: Gold and Nitro P01 smokes
  match the previous build (n 2 each); nothing drivable to hand you on Nitro beyond P05 by harness yet.
- NITRO POINTER FIXED (nitro-port lane, NITRO-PORT s.10, proxy faff357): the confinement was ours. The cursor map looked for the game window by Gold's name only, so on
  Nitro it mapped nothing, NITSHELL read raw screen pixels, clamped them to its 640 x 480 page and wrote the clamp back as the pointer position. The map now finds the
  Nitro window and the shell gets its own 16:10 mapping (I76_CURSOR_MAP_SHELL=aw; the first fix alone left clicks up to 288 px off at the sides). Proof n 3 boots:
  pencil within 3 px of the pointer at the centre, corners and quarter points; MELEE > MULTI MELEE > JOIN clicked through to the transport row (captures
  captures/nitro-port-20261021/cursor/click-e*.png). Not yet tested: the in-mission Esc menu on Nitro. The Macs do not set the cursor map and their shell mouse followed
  the real macOS pointer, so they are probably unaffected, but JOIN on a Mac still wants one human click.
- TERRAIN MORPH RESULT (geomorph lane, TERRAIN-MORPH-2026-10-21, 4f03cd7; staged, NOT a candidate): blending each split vertex's height AND shade in over 25 % of the
  distance it appeared at (40 m minimum) removes the pop: in the no-dashboard (hood) view the 95th-percentile jump per split falls from 217 px to 2.2 px, the shade step
  from 78 grey levels to under 1, snaps over 4 px from 3442 px/s to 0, physics unchanged over 910 tick states. Cost 27 fps median in that view (91.5 vs 118.5): the
  per-vertex memory tables, not the blend. The lane is now building the stateless form (blend factor from the vertex's own ring distance, no tables; expected under
  0.3 ms) and will promote it only at a cost of 1 fps or less. LOOK NOW if you want: exp-morph PLAY-TICK-MORPH.bat (expect ~90 fps in the hood view where plain gives
  118). The forced-split ring at 12.9x in the earlier trace was a model artefact: flat ground splits at the ring because of its surface type (dirt / paved), not a force.

## 2026-10-22 afternoon (owner's answers; main)

- JUMP: X5 has no jump tweak (same physics as PLAY-TICK, 41.667 tick; it differs only in terrain / draw distance), so the clean jump was stock 1997 behaviour
  and the earlier misses were line / timing luck. Owner: leave it. The jump logger and J2 (a switch easing the held nose-dive) stay PARKED as plans
  (TICK-FINISH s.22.5).
- MAC JOINS: the Nitro data-path registry key ("Minimum"="0", NITRO-MP-DESIGN s.0.5.16) is now in the Nitro app on the laptop and Michael's Mac (backup
  system.reg.pre-minimum-20261022); Andrew's Mac was asleep (ssh timed out): to do when it is on. No DLL change.
- SKY A/B (exp-polish2, proxy 449237d6): PLAY-OWNER-SKY-STOCK (the mirror pass scrolls the sky too: x2 in the Gold cockpit, as the exe has always done) vs
  PLAY-OWNER-SKY-ONEPASS (I76_SKY_MIRROR=0: the sky moves once per frame whatever the mirror). Both = X5 terrain + 2000 m.
- MORPH LOOK: PLAY-OWNER-MORPH-STATELESS (same copy): the stateless geomorph, fps NOT measured yet; look at pops / shade on the T05 slope, hood view.
- EMULATOR: desktop "i76 x86box ref" now runs emu\PLAY-P166-GOLD.bat (Gold to its main menu by itself, ~1.5 min hands off); the retail launcher
  PLAY-P166-LOGGED.bat is unchanged. Gold path not yet booted end to end.
- GAME TYPES: replacing the ARENA+ / CO-OP boxes with two game-type entries is ~2-3 lane days; held for the owner's go on that cost.

## 2026-10-23 morning (owner's answers; main)

- SKY: owner picks ONE PASS (I76_SKY_MIRROR=0); in every new owner preset below.
- FAR CLIP at I76_TERRAIN_LOD 24 (lab autotest\owner-farclip-crash.ps1, exp-polish2, proxy 81808610 = 7dd568c; drive 6 s, F6 hood 4 s,
  B binoculars 4 s): **2500 m CRASHES the binoculars on t01, 2 of 2** (exe+0x91919 in the edge split, cam cb 0x4071a0, i.e. the int16
  vertex wall; the 28000 vertex guard does not prevent it), with and without the shade switches. 2400 m: t01 ok (n 1). **2300 m: no
  crash in 8 runs** (t01 x3, t03, t05, t09, t12, t15); binoculars 40-56 fps (2000 m: 43.5, so the binocular cost predates this). m03
  direct boot faults at frame 0 (EIP 0, before any terrain) in this copy - unrelated to the far clip, open. PgUp x8 did not visibly
  zoom (fps unchanged): the cockpit-zoom edge is NOT tested. Owner presets use 2300; the proxy's 2500 cap is too high at LOD 24.
- MORPH SHADE (terrainmorph.c 7dd568c): I76_TERRAIN_MORPH_SHADE=<1..4> (the shade fades over x times the height band) and
  I76_TERRAIN_MORPH_BIG=1|2 (the 64+ sample tiles blended: 1 = height and shade, the sliding form; 2 = shade only). Instrument, t05 direct
  boot 25 s, 2300 m, n 2 each: per-split one-pass shade step p95 0.023-0.029 (MORPH) / 0.026-0.027 (SHADE x3 + BIG 2) / 0.020-0.021
  (BIGBLEND); frame max jump p95 12-15 px in all three except one SHADE run (31 px, a different path). Run-to-run spread is as large as
  any difference: the boot drive is not a fixed route, so this says "no harm, no measured gain", and the owner's eye decides.
- TO TEST (exp-polish2): PLAY-OWNER-2300-MORPH (control) / -SHADE / -BIGBLEND, all one-pass sky + 2300 m.
- EMULATOR: play disk images\w95pb-hdd-memlog-20261023.img (copy of 20261016 as of 06:25 today, MSDOS.SYS BootDelay=0 Logo=0;
  owner_log.py picks the newest automatically); the 20261016 disk is no longer used. Owner: leave 86Box paused at the menu between uses.
- GAME TYPES: lane started (phase 1, host side in a lab copy).
- 2026-10-23 owner feedback on the three: BIGBLEND fine (no sliding seen) -> BIG 1 adopted; SHADE looked MORE abrupt -> a bug: the
  stateless shortcut's threshold was taken from the shade band (8 / fb) instead of the height band's floor (8 / frac), so with
  _SHADE 3 splits with D in 53-160 m snapped their shade from ts to 1 at d = 0.25 D. Fixed 5be4b0d, proxy 10aaf74c in exp-polish2.
  New PLAY-OWNER-2300-ALL = sky one pass + morph + BIG 1 + SHADE 3 + 2300 m. fps on the T05 mountain dipped to ~100 (owner): the
  morph's cost on the ridge climb is unmeasured - to measure (lod-sweep ridge route, n 2) before promotion.
- TERRAIN POPS (terrain-pop lane, records/TERRAIN-POPS-2026-10-23.md): your "abruptness in the darkness of the terrain" is the hardware
  shade itself, not the morph - every polygon emitter rounds the vertex shade to one of 32 grey rows (on T05 ~16 distinct greys, 20-23
  apart), so a vertex's brightness jumps ~12 % whenever its shade crosses a row; driving the ridge, 200 vertices/s within 300 m do that
  (2.4 per frame), and the morph's "slow shade fade" walked the same steps. Census of what Glide receives: 15-16 levels; with the fix 32-40
  levels, a continuum. Texture-level switches and the morph measured nil on the screen. "Parts not morphing smoothly" = BIG 1's far tiles
  sliding (their heights blend against a root square that re-aligns; carried vertices > 16 px 480-525 px/s, 0 with BIG 2 = shade only).
  LOOK: exp-polish2 PLAY-OWNER-2300-SMOOTH (= ALL + your four detail keys + I76_SHADE_SMOOTH 1 + BIG 2; DLL 1790a308 installed, the
  previous f2856def kept beside it). fps on the ridge route: 84.6-86.3 vs ALL 84.5-86.7 (n 4 / 5). Not promoted; your eyes decide.
- FAR-EDGE FADE (owner asks): options noted in the reply of 2026-10-23; no lane yet.
- RENDER LOAD vs THE DAILY DRIVER (owner's question, 2026-10-23 10:xx): the daily driver's PLAY.bat = preset best-wide carries
  I76_TERRAIN_TEX=8, I76_OBJECT_LOD=8, I76_SHADOW_DIST=4, I76_ROAD_TEX=8 (and I76_MIRROR_FAR=300); the rebaseline lane removed every
  graphics key and put back only far clip / roads / bushes / fade / terrain LOD, so every OWNER-* trial preset ran objects, shadows and
  texture levels at STOCK distances - the owner's "object detail and render distance is near". Added to all OWNER-*.psd1 in exp-polish2
  (lab commit). I76PLYR.DEF detail bytes and dgVoodoo (6880x2880, 4x AA) were already identical. Every fps row taken before this
  (far-clip edges, shade, mirror, haze/fog, pops) is at the LIGHTER load; the lanes were told to re-take the rows that matter.
