# Owner morning 2026-10-16: what you have not tested yet

Written 2026-10-16 from the docs and logs only. No game was launched, no console used, no process touched.
Sources: [OWNER-TEST-LIST.md](OWNER-TEST-LIST.md) (items 0-42), [BACKLOG-2026-10-10.md](BACKLOG-2026-10-10.md) (section C),
[STATUS-2026-10-10.md](STATUS-2026-10-10.md), [COOP.md](COOP.md), [COOP-SPIKE.md](COOP-SPIKE.md), [MULTIPLAYER.md](MULTIPLAYER.md),
lab `nucleus-coop\README.md`, [HAPTICS-ARCHITECTURE.md](HAPTICS-ARCHITECTURE.md), [MOTION-OUTPUT.md](MOTION-OUTPUT.md),
[SOUND-HD-PACK.md](SOUND-HD-PACK.md), [STEAMDECK.md](STEAMDECK.md), the daily driver's `PROMOTIONS.md` (rows 0-16),
the lab twin's `README-TESTS.txt`, `tools\promote-18-terrain-signs.ps1`, [records/ERA-ENVELOPE.md](records/ERA-ENVELOPE.md),
[records/EMU-MEMTRACE.md](records/EMU-MEMTRACE.md), [records/EMU-1997-PLAN.md](records/EMU-1997-PLAN.md), lab `emu\README.md`, and
`git log --since=2026-10-01` of i76-everywhere (381 commits) and <lab> (147).

Paths: **driver** = `<games>\Interstate76-2026-10-03`, **twin** = `<lab>\game-dd-20261003`
(every `TEST-*.bat` below is in the twin's root). Audio may be muted by agents: `<lab>\tools\mute.ps1 -Off`.

## Three facts first

1. **You have not launched the daily driver since 2026-10-08 07:43** (its `Interstate 76\mciproxy.log` was last written then;
   `dgVoodoo.conf` is still the pre-15 copy). Promotions **15** (mouse, 10-08 21:00) and **16** (collision G, roads 1800,
   2x supersampling, I76 Debug, 10-12 17:45) have been played only on the twin, never on the driver itself.
2. **The twin is not the driver any more.** Its proxy is `33211f11` (driver `509c6df0`), with opt-in lab switches; `PLAY.bat`
   there behaves like the driver's, but every `TEST-*.bat` adds switches.
3. **`TEST-next.bat` is no longer exactly promotion 18.** Since 2026-10-13 it also carries the AI combat parity set
   (`I76_AI_STOCK_CLOCK=1` at 20 fps, skid / search / turret holds, throttle ease). Promotion 18 does not.

## Already tested by you (closed, with the record)

| what | your verdict | source |
|---|---|---|
| Collision G (barricades on time, bar as a box) | "G is fantastic ... keep G" | OWNER-TEST-LIST 3b; promoted in PROMOTIONS 16 |
| Road draw distance 1800 m | "could be a little further" -> 1800 | PROMOTIONS 16 ("owner-verified set") |
| 2x supersampling (stretched_ar, 6880x2880 + 4x) | in the owner-verified set | PROMOTIONS 16; replaces the shimmer bats of item 31 (archived 10-12) |
| TEST-next, 2026-10-12 afternoon build (hull fix + sign sweep =3) | "looks really great ... signs a little early ... 100% of the time" | OWNER-TEST-LIST 36; lab DRAW-DISTANCE-2026-10-12.md |
| Mouse fix (promotion 15) | n = 1, on the twin only | PROMOTIONS 15 |
| Widescreen 21:9 and 120 fps | approved / owner-played (2026-10-03) | PROMOTIONS 2; BACKLOG F-15 |
| Dream mission failing | answered: the stock 8-checkpoint lap counter, not our switches | OWNER-TEST-LIST 37 |
| Reference = retail 1.0 on the emulated P166, software, lowest detail; P133 dropped; stock = invariant across era configs | your rulings 2026-10-14/15 | EMU-MEMTRACE, ERA-ENVELOPE; W95-18 (item 41) is superseded |

Your Deck reports (pointer up-left 10-07, TV aspect / menus / brightness 10-13, stick inconsistent 10-14, night textures 10-14)
were each answered with a fix; **none of the fixes has been played since** (section B11).

---

## A. Ready-to-promote candidates for the daily driver

| # | candidate | what is in it | evidence | you play first | the gate |
|---|---|---|---|---|---|
| A1 | **Promotion 18** (`tools\promote-18-terrain-signs.ps1`; will be PROMOTIONS row 17) | proxy `855b08d7` (built from repo `f2ffd7c`, brings v3 telemetry and the env cleanup, all opt-in); in best-wide / balanced / best-120: `I76_TERRAIN_HULL_FIX=1`, `I76_BREAKABLE_BOX` 1 -> 4, bushes `I76_CLUTTER_DIST` 1800 (balanced 1200) + `I76_CLUTTER_FADE=200`, `I76_TERRAIN_LOD` 8 -> 32 | hull fix 16 -> 0 ground losses in 5 cockpit descents each; signs 33/33 vs 5/33 (=4: median -0.11 m, never early, n = 33); hill top 120 fps, p1 107 vs 96-101 today (n = 4) | `TEST-next.bat` or `TEST-hill-next.bat` (but see fact 3: it adds the AI parity set; ask for a `TEST-promo18.bat` if you want the exact set), and pick dense vs thin bushes (`TEST-next-dense.bat`) | **HELD** since 10-12 21:30 for the dream-mission report, which item 37 has since answered; the lead must lift the hold. **No gate phase exists yet**: `run-overnight.ps1` has no P9 (I grepped). It needs writing on the P8 pattern (gate-folder 21-23 rows, PLAY-16x10 / balanced row 3, T05 hill top, t04 drives, t11 road soak), and `$GatedStage` md5s filled before the script will apply |
| A2 | **AI combat parity set** (owner test 40) | AI hazard checks, handbrake turns, throttle ease, route search at stock-20 rates; steering on the stock 20 fps clock | twin t05 / t13 / t15 / t17, n = 5 per setting: rates match stock20; dream race within 0.7 s a lap of stock20 | `TEST-combat-parity.bat` vs `PLAY.bat` (t13, t17), and `TEST-dream-1997pace.bat` vs `TEST-dream-control.bat` | no promote script and no gate yet; "say if you want it in PLAY.bat" |
| A3 | **Physics step 30 or 31.75 ms** (owner test 42 + the P166 launcher) | TEST-next with `I76_FIXED_STEP` 33.3333 (30 ms) or 31.5 (31.75 ms), `I76_REF_FPS` and the AI clock on that reference | 30 ms: canyon landing turned over 0/24 vs PLAY.bat 9/10, calm body, every other row inside the 1997 envelope. 31.75 ms: no measurement recorded (launcher made 10-15 19:23) | `TEST-envelope-candidate.bat`, `TEST-p166-retail-step.bat`, `PLAY.bat` (decision C1) | none yet. Open per ERA-ENVELOPE: barricade check without the box switch, yaw outliers, T04 rounds 3-5, combat |
| A4 | **Cleanup side builds** (owner test 27) | u32x `188e0c07` (VPTR code removed). The proxy half (`8b904e53`) is superseded: the env cleanup rides in A1's `855b08d7` | static + string checks only (PROXY-CLEANUP-2026-10-10) | nothing; an agent gate (about 10 min of the console, nobody playing) | twin `autotest\gate-folder.ps1`: same 23 rows as `runs\gate\20261008-204529`, watch row 4 (modal arrow) |
| A5 | **PLAY-stock.bat on its own conf at TMU 2048** (owner test 5) | only if you see wrong textures in PLAY-stock | overnight P5: no signal in 4 runs | `PLAY-stock.bat` (driver) a few minutes | small promotion, not written |

---

## B. Untested features, by value (launcher / command, what to look for, time)

### B1. The daily driver itself (highest value: 15 and 16 are unplayed there)

| item | do | look for | time |
|---|---|---|---|
| Mouse + popups (items 1, C-3) | driver `PLAY.bat`: menus, TRIP > garage > DONE with no engine popup, ACCEPT SALVAGE popup, Esc menu Exit, Save Bookmark overwrite Y/N; repeat with `PLAY-balanced.bat` | arrow lands where you point; popup closes by click / Enter / Space; save written. Rollback `_rollback\16`, then `_rollback\15` | 15 min |
| Collision G + roads + 2x SS in normal play | same session, any mission (T05 barricades) | one thud per hit, barricades fly when touched, no stutter | in the above |
| **Force feedback** (items 2, C-5, H-01) | wheel plugged in before `PLAY.bat`, T01: fire, ram | stock FFB as before 10-08. Gates 15 and 16 ran with **no wheel** | 5 min |
| PLAY-16x10.bat (C-4) | once, same menu steps | still the old corner-pointer regime (`dgVoodoo.16x10.conf` CaptureMouse = true): decision C7 | 5 min |
| I76 Debug (item 33) | `DEBUG.bat` after `PLAY.bat`. For the charts: in a cmd window `set I76_TELEMETRY=1` (and `I76_SOUND_EVENTS=1`, `I76_DAMAGE_EVENTS=1`), then run `PLAY.bat` from it (the launcher passes inherited switches on) | every tab once; the Trainer tab's Repair and the T05 hill-top teleport; fps with the page open vs closed (n = 2 each). Close the old trainer window first | 15 min |

### B2. Co-op campaign (built 2026-10-07; never played by two people)

**What is ready:** the 17 co-op missions, the host as the story's hero, shared enemies, gunfire, kills, radio, objectives,
win -> next mission / loss -> retry, late join, buddy respawn, damage factor; all 17 load (wins forced), 16/16 reloads in step.
**Not done:** a natural multi-mission run, MAX SCORE (leave it off), the first mission shows the host in the buddy's car model.

**Route 1: two machines (the measured one, PC host + Mac or a second PC).** About 45 min the first time.
1. Use a **copy** of the game on each machine (the twin is fine on the PC; never the driver). Stock car data: no
   `.vdf/.wdf/.gdf/.cdf` in ADDON, `valepre4.vcf` = de680a86 (the driver's and the twin's are).
2. IPX: copy IPXWrapper 0.7.2's `ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll` beside `i76.exe` (lab copy in
   `<lab>\refs\ipxwrapper\bin\ipxwrapper-0.7.2`). Network profile Private. MULTIPLAYER.md sections 2-3.
3. With the game closed: `python tools\coop-install.py "<game folder>\Interstate 76"` on **both** (turns "The Crater"
   into the campaign; `--remove` undoes it).
4. Switches on both: in a cmd window `set I76_COOP_AI=1`, `set I76_COOP_CHAIN=1`, optionally `set I76_COOP_DAMAGE=0.5`,
   then start the copy's `PLAY.bat` from that window (Mac: the wrapper's `HKCU\Environment`).
5. Buddy first: MELEE > MULTI MELEE > JOIN > IPX and wait on the list. Host: MELEE > MULTI MELEE > HOST > IPX, The Crater,
   BROADCAST GAME. Buddy: select it, JOIN GAME (joining late also works).
6. First time on a PC pair: the firewall alert opens behind the game; Alt-Tab, tick Private, Allow.
7. Look for: enemies chase both of you, kills show on both screens, radio and notepad on the buddy, a win takes both to
   T02, a loss retries. Report any desync, a stranded loader, a crash (`mciproxy.log` CRASH line).

**Route 2: one PC, two pads (Nucleus).** Tested only as an **arena melee**, never campaign co-op: the handler sets no
`I76_COOP_*` switch, and `game-nucleus` runs a 10-05 proxy (`3df367d9`) older than the co-op code. An agent needs to
update `game-nucleus` (current proxy + `coop-install.py`) and add the three switches to the handler first (decision C11).
The two-pad melee checklist itself is ready (lab `nucleus-coop\README.md` "Owner checklist", about 15 min):
`powershell -ExecutionPolicy Bypass -File <lab>\nucleus-coop\find-pads.ps1` -> set `JOY_WINMM` in
`Interstate76.js` -> copy it to `refs\nucleus\run\handlers\` -> `refs\nucleus\run\NucleusCoop.exe` (UAC) -> 2 players side by
side -> host/join in the two windows -> End (lock) -> drive 2 minutes -> End, Ctrl+Q.

### B3. Force feedback, rumble, haptics telemetry, motion, transducers (lab copy; tools\haptics)

| item | command | look for | time |
|---|---|---|---|
| Driver FFB | see B1 | | 5 min |
| Telemetry v3, in-game half (6) | twin, switches `I76_TELEMETRY=1 I76_SOUND_EVENTS=1 I76_DAMAGE_EVENTS=1` + `python tools\telemetry\i76tel.py --check` | the automated half passed 24/24 muted; yours: any sound missing or doubled, stutter | 10 min |
| Record a real session (8) | `tools\haptics\haptics.ps1 record --udp --out tools\haptics\replays\t01-c1.i76rec --seconds 300`, drive t01 | v3 frames, SOUND_START is_player 1/0, DAMAGE_SIDE; keep the file (it becomes every offline test's input) | 10 min |
| Wheel + pad + shakers together (9) | `haptics.ps1 live --source udp`, then `--live` with all three | interference, dropouts | 15 min |
| Latency (10), wheel coexistence (11), hardpoint +0x10 (12), explosion reach (13) | as in OWNER-TEST-LIST 10-13 | ms from event to shaker; does game FFB still play with the host holding the wheel | 30 min |
| Effects one at a time (14), feel session (15) | `haptics.ps1 preview --effect <id> --live --sinks pad,lfe`; `python tools\haptics\design\report.py` + hot reload | each effect reads as what it is | 30-60 min |
| Transducer stems vs synth (26) | needs 6 and the stems built (`soundhd.py build`); `$env:I76_LFE_SOURCES` = `synth=1,stems=0` / `0,1` / `1,1` | A/A first; which felt like the sound, anything late or muddy | 40 min |
| Motion desk bench (17-20) | install FlyPT Mover (free) or SimHub; `haptics.ps1 motion all --targets flypt --send` (or `simhub`, `simhub-forza`) | the scenario table in item 17; T2 pure nose-down braking | 45 min |
| Motion from the real game (21-24) | `haptics.ps1 live --source udp --sinks motion-udp`, then `python tools\haptics\motion\i76motion.py --plot ...` | signs of surge / sway / yaw; interp vs hold; latency | 40 min |
| Real rig (25), Deck rumble | later: no rig chosen; Deck pad-layer rumble never field-tested (STEAMDECK "baseline tier") | | |

### B4. HD sound pack (tools\soundhd, pack v1; installed nowhere)

- **Agent first:** the pack's audio is not on disk (`out\pack-v1\` holds only manifests). Build:
  `tools\soundhd\.venv\Scripts\python tools\soundhd\soundhd.py build` (about 2 min), then
  `soundhd.py install --game <lab>\game-dd-20261003` (dry run) and `--apply`; `uninstall --apply` undoes it.
  The loader proof (step 1) already passed twice (overnight P4): loose ADDON `.gpw` are loaded.
- **You (item 7, about 30 min):** the same mission (t01 or t04) with the pack on and off, on your usual speakers: rams have
  weight but are not louder, MG loop seamless, idle body, horns not distorted, skids / CB / menus unchanged, CB vs engine vs
  weapons balance. Per-sound names and spectrograms: `tools\soundhd\out\pack-v1\report\index.html`.

### B5. Debug dashboard: see B1 (it is in the driver since promotion 16; the README still lists it as "not verified yet").

### B6. Cockpit dash at 2x (items 28-30; lab `game-tex`, about 45 min)

First open `texture-lab\out\cockpit-mockup\index.html` and decide whether a sharper dash is worth a session (decision C9).
Then three t01 boots in the Piranha: control (no dash files in ADDON), marker2x
(`python texture-lab\cockpit_split.py --game ..\<lab>\game-tex --out texture-lab\out\cockpit-split\gt-marker2x --marker`),
art2x (`... --out ...\gt-art2x --png-dir texture-lab\out\cockpit-mockup\tiles`). Look for the labels and crisp magenta checker
(marker), sharper-same-worse blind (art), and the kill criteria in item 29.

### B7. Shimmer / supersampling

Mostly closed: the 2x SS conf is promoted (PROMOTIONS 16). Still open from item 31: whether stock terrain texture distance
(`I76_TERRAIN_TEX` 1 or 4 instead of 8) crawls less in a way you prefer. Those bats are archived in the twin's
`_archive-2026-10-12`; ask for a fresh pair if you want it (15 min).

### B8. Terrain, signs, draw distance (twin)

| item | launcher | look for | time |
|---|---|---|---|
| Ground drop-out fix (34) | `TEST-hill-terrainfix-play.bat` 3-5 cockpit descents, then one `TEST-hill-terrainfix.bat` | ground never vanishes; `terrain-hull-fix: NOT applied` = kill. You played TEST-next with the fix but no descent result is recorded | 15 min |
| Signs on time (35-36) | `TEST-hill-next.bat`: ram the Texas 13 and US 380 shields, straight and sliding | each falls at the first ram, **when the bumper reaches it** (=4; your "a little early" was =3) | 10 min |
| Bushes / terrain detail, dense vs thin (36) | `TEST-next.bat` vs `TEST-next-dense.bat` (or the hill versions) | which you prefer; no hill-top stutter | 15 min |
| Melee at 1800 m (C-9) | twin `PLAY.bat` > MELEE, any arena, binoculars | no crash | 5 min |

### B9. AI pace and combat parity (items 38, 40; twin)

`TEST-combat-parity.bat` vs `PLAY.bat` in t13 and t17 (do attackers handbrake-turn and slide as you remember; do they drive into
oil / mines more?), then `TEST-dream-1997pace.bat` vs `TEST-dream-control.bat` (T04; can you win; does it feel 1997). About 40 min.

### B10. Era envelope and the P166 retail step (item 42 + README-TESTS; twin; neither booted by hand)

`TEST-envelope-candidate.bat` (30 ms), `TEST-p166-retail-step.bat` (31.75 ms), `PLAY.bat` (41.7 ms) as control. In each: T05 from the
hill top full throttle over the canyon ramp a few times (land and drive on, no roll-over: the 41.7 ms step turns over 9/10), a
flat straight (no side-to-side shimmy), T06's first ramp (about 72 m), some combat; compare with your 86Box P166 session.
About 40 min. `TEST-w95-18-*.bat` (item 41) are superseded; optional.

### B11. Steam Deck (items 39 + 2026-10-14 follow-up; nothing re-tested since the fixes)

| item | do | look for | time |
|---|---|---|---|
| Docked TV, once | Game Mode: Interstate 76 > gear > Properties > General > Game Resolution = Native (1080p TV) / 1920x1080 (4K) | 16:9, no bars, round radar and wheels | 5 min |
| **Pad menu v3** (proxy `8bc52939`) | docked and handheld: stick slowly and fast in four directions; TRIP > LOAD BOOKMARK > garage > DONE with stick + A only; stick, trackpad, stick; Select > Exit > Yes/No with the stick | pencil moves every time, the lit button is the one under it; if buttons light but the pencil does not move, say so (compositor). Left stick must stay "Joystick", not "Joystick Mouse" | 15 min |
| **Night textures fixed** | T06 (or M04) handheld, then docked | gauges, reticle, roads, sky like the PC's night; else Steam + R1 screenshot | 10 min |
| Brightness on TV | TV first (HDMI black level Auto/Full, HDR off, Game mode), then `I76_TV_GAMMA` 1.45 -> 1.6 or `I76_TV_BRIGHTNESS` 105-110 in `~/Games/Interstate76/i76-env.sh` | tell us the values you keep | 10 min |
| Pointer offset (10-07 fix), rumble, sound | covered by the v3 test; rumble from the shared pad layer and mission music on the Deck have no hand test recorded (STEAMDECK "Honest open items", "baseline tier") | rumble on hits; music in a mission | 10 min |
| Send | `~/Games/Interstate76/deck-launch.log`, `game/mciproxy.log` (lines `conf:`, `addon:`, `display:`, `pad-menu:`) | | |

Undo: `bash ~/i76-deploy/deck/setup-deck-tv.sh --revert`; textures `bash ~/i76-deploy/deck/setup-deck-stock-textures.sh --revert`.

### B12. Emulator: the 1997 PC (lab `emu\`)

- **Play retail 1.0 on the P166:** `powershell -ExecutionPolicy Bypass -File <lab>\emu\run-vm.ps1 pbs-p166`
  (retail 1.0 is installed on its Windows 95 disk; one VM at a time, they share the disk; check that no agent's 86Box runs
  first). Every retail mode asks for **disc 2**: Media > CD-ROM > Image > `emu\images\cd-rip\I76_CD2\I76_CD2.cue`. Settings:
  software renderer, 320x200, lowest detail. Mouse capture: click; release: middle button or Ctrl+End. The retail folder
  has the stock keypad map (keypad 8 = throttle).
- **Retail saves** 'retail T04 / T05 / T13 start' are in `emu\results\saves-retail\`; they were made in throwaway run disks,
  so an agent must copy them onto the VM disk first. The Gold-exe saves (T04 / T05 / T13) are in `emu\results\saves\` with
  snapshot `emu\images\w95pb-hdd-saves-20261015.img`.
- **Look for:** handling vs our build (retail's steady yaw is 0.94-1.00 rad/s, Gold's 1.34-1.59), the T05 canyon (no
  retail landing destroyed a car, n = 6), menu music (retail loops CD track 15; never heard: the host was muted).
  Untested: whether retail 1.0 reads Gold saves. About 30 min.

### B13. Fresh install (item 16; blocks v1.1.0)

At the console, not over Remote Desktop, with no `C:\GOG Games\Interstate 76`: double-click repo `INSTALL.bat` (one UAC for GOG's
installer; `-SkipNitro` skips the Nitro Pack), then `PLAY-i76.bat`: STAND BY, no watermark, pointer on target, TRIP > garage >
popup (the installer makes `PLAY-i76.bat` and a desktop shortcut), a bookmark into a mission at 120 fps, **music in the mission**, Esc > Save Bookmark > Y/N. Boot already passed 7/7
(overnight P6); yours are the real installer, music on GOG exe `9a232dcc` (no WINMM import: GOG's WIN32.dll plays it), best-wide,
a save. Undo: `install.ps1 -GameDir "C:\GOG Games\Interstate 76" -Preset stock`. About 30 min.

### B14. Older taste calls still queued (backlog C-6 to C-8)

Detail switches each by eye (shadows 200 m, road texture 480 m, mirror 300 m), ReShade CAS, 1997 menu music (C3), cutscene
music bleed on Windows (agent stages `smack-music-fix`), pad layer buttons (LB+D-pad, Y view cycle, right-stick orbit; the
last two are in no promotion). One word each; about 30 min in all.

---

## C. Your open decisions

| # | decision | options and what we know |
|---|---|---|
| C1 | **Physics step**, and whether players may adjust it | 41.7 ms (today: canyon turn-over 9/10) / **30 ms** (envelope candidate, 0/24, the P166 low-detail end) / **31.75 ms** (retail 1.0 on the emulated P166, measured in T05; not yet measured on the twin). A user-adjustable step ("1997 machine speed") does not exist anywhere yet: no doc or switch beyond `I76_FIXED_STEP` itself; say if you want it as a preset choice |
| C2 | **Retail vs Gold/GOG handling** | our exe is Gold physics; Gold's steady yaw is about 45 % above retail (1.34-1.59 vs 0.94-1.00 rad/s, n = 7-8) and slides more; accel, brake, gravity, rollover rule equal. EMU-MEMTRACE: "stock handling should be decided against retail". Keep Gold, or build a retail-handling switch |
| C3 | **Music in the shell** | `I76_MUSIC_SHELL=1997` (retail plays track 15 alone, looping, which the switch matches) and `I76_MUSIC_DISC_ORDER=1`: lab-tested n = 2, opt-in, in no preset. Yes / no each |
| C4 | Lift the promotion-18 hold, and bushes **thin to 1800 m** or **dense to 300 m** | hold reason answered (item 37); A1 |
| C5 | AI parity set into PLAY.bat, and 1997 race pace | A2; it changes every AI car |
| C6 | Collision box: H (`=2`) was never chosen; =4 is the planned default | A1 |
| C7 | `PLAY-16x10.bat` pointer regime | keep the old corner regime, or promote CaptureMouse false + the cursor lines into the 16:10 conf / best-120 |
| C8 | `PLAY-stock.bat` own conf at 2048 | only if B1/A5 shows wrong textures |
| C9 | Cockpit 2x worth a session | from the mock-up page (B6) |
| C10 | HD sound pack: pursue after the A/B, and the small-speaker variant | B4 |
| C11 | Campaign co-op on one PC: let an agent wire co-op into the Nucleus route | B2 route 2 |
| C12 | Deck TV values to keep | B11 |
| C13 | Release v1.1.0 (CHANGELOG still "Unreleased") | waits on B13 |

**Before bed:** `tools\rdp-to-console.cmd` and tell the agent if you want an overnight run (OWNER-TEST-LIST item 0); close the
old trainer window first.
