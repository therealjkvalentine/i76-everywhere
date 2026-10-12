# Owner test list (things only James at the console can check)

Kept current by the agents; newest additions at the bottom of each section. Lab copy = `C:\Users\james\i76-uncap-lab\game-dd-20261003`.
Daily driver = `C:\Users\james\Games\Interstate76-2026-10-03`. Audio may be muted by the agents: `i76-uncap-lab\tools\mute.ps1 -Off`.

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

## Daily driver (already promoted, confirm in normal play)

1. **Mouse in widescreen (promotion 15, 2026-10-08).** `PLAY.bat`. Main menu, TRIP / LOAD BOOKMARK, garage Build & Repair:
   DONE with no engine -> the "CAN'T GET VERY FAR" popup: a small arrow should follow your hand over the frozen picture; OK closes it
   (click, Enter or Space). Save Bookmark screen: overwrite prompt Y/N. In a mission: Esc menu items and Exit. Same with `PLAY-balanced.bat`.
   Anything odd -> rollback is `_rollback\15` (five files).
2. **Force feedback after promotion 15.** The gate had no wheel plugged in. Plug the wheel in before `PLAY.bat` and confirm FFB feels as before.

2b. *(Promotion regression automated 2026-10-11, P7: best-wide / best-wide-balanced / best-120 on the twin each boot and drive t04
   90 s at 120 fps, no CRASH line; the twin's presets are byte-equal to the driver's.)*

## Lab copy (candidates, not in the daily driver)

3. **Collision fix A/B.** `TEST-coll-A-control.bat` (= your PLAY.bat) vs `TEST-coll-B-window2.bat` (I76_COLL_WINDOW=2 + dedupe).
   T05 (Taurus jump mission) roadblocks, cars, buildings: does B hit what A drives through? Anything new and wrong in B (snagging on
   scenery, odd bumps, getting stuck, doubled crash sounds)? `TEST-coll-C-24fps.bat` = 24 fps reference (choppy on purpose; stock-like collisions).
   Measured offline: barricades contacted 36/36 with B vs 8/28 with A.
   *(automated 2026-10-11, P1:* rams w2 21/21 vs control 10/43 (A/A p 0.49); gate with B staged on the twin 21/0. **New finding:**
   in t04 god-mode circle drives B destroys the car at one spot about 9.5 s / 250 m along the circle (5 of 23 passes; A 0 of 21,
   p 0.05; elsewhere deaths are equal). While playing B, watch for being killed by something you barely touched; t04's start area
   is where the drives found it. Details: records/OVERNIGHT-2026-10-11.md, P1.)
4. **Terrain drop-out watch.** `TEST-terrain-watch.bat` = PLAY.bat + drop detector. Play where you saw it (open desert, road bend). If the
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

27. **Gate the 2026-10-10 proxy cleanup builds on the lab twin before any promotion.** Physical console, nobody playing
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
