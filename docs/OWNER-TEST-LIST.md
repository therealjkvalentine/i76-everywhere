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
    - **Ran 2026-10-17 at the console (agent, owner handed it over): FAILED before measuring.** Both Gold replays (g166-mloop-rep1, -N 2) printed "Did not reach mission (menu nav may have drifted)" and "no common frames"; the game booted, took the lock, muted, exited 0. Summary: lab toolseplayunsmelee-console-20261017-145313.txt. Needs agent debugging of the melee menu navigation (no owner action); not done, to save credits.
    The only clean frame-by-frame exe vs emulator comparison (same default car), but the menus do not work headless. The script has
    never run: expect to debug it, not to measure.
    - Session connected, no other game running. From a cmd window:
      `C:\Users\james\i76-uncap-lab\tools\replay\REPLAY-MELEE.bat -Conds g166-mloop-rep1 -N 2` (2 Gold replays). It takes over mouse
      and keyboard; hands off. If it stalls at a menu, note which one and stop it (Ctrl+C in the window) instead of waiting out 240 s timeouts.
    - If both finish: run `REPLAY-MELEE.bat` with no arguments (10 replays; the 6 retail ones replay arcade traces and do not count yet).
    - **Look for:** `tools\replay\runs\melee-console-<stamp>.txt`: Gold reps with "sim_dt bit mismatches 0", "input bit mismatches 0",
      and the first frame with |dpos| over 0.1 / 1 m (late = good).
52. **Watch one retail canyon descent (low, 5 min; new 2026-10-17; records/EMU-T05-CLEAN.md).**
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
