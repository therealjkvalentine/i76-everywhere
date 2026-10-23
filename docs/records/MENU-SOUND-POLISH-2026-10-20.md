# Menu / sound polish from the owner's release-candidate play-test (2026-10-20 evening and night, lane menu-sound-polish)

Measurements finished 2026-10-21 01:28 (queued overnight behind another lane's fps lock) and 06:40 (D's launcher cases).

Owner, play-testing `Games\I76\release-candidate` (lab game-tick: proxy tick19g adc4fd49, dgVoodoo.wide.conf, u32x
06467bd2, `I76_U32X_MENU_ASPECT 3440:1440`, `I76_CURSOR_MAP=1 _U32X=exe _DGV=aw`), plus the items the coordinator added
during the night (D..G). Every run was on the lane's own copy `i76-uncap-lab\exp-polish` (a robocopy of the release
candidate, 2026-10-20 17:04) and, for the network items, the lab peer `game-mpo-b` (its own IPXWrapper instance; exp-polish
borrowed game-mpo-a's instance so nothing reached the LAN). The release candidate, daily driver, golden, lan and twin were
only read. Console runs held the lab lock; headless runs used private desktops; every boot had `I76_MUTE=1`, the per-pid
mute watcher and `I76_SHM_SUFFIX=exp-polish`.

**Staged** (nothing installed): lab `builds\menu-sound-polish-20261020\staged\` (MD5SUMS.staged, presets.diff), proxy
**`e61d1e3e59c1cdd6123917e73b8b5c0b`** = clean `git archive 747609a` music-fix, MSVC x86 /MT /O2 /Brepro, built twice
byte-identical (`run1` / `run2`). It is this repo's music-fix at 747609a, so besides this lane's four commits it carries every
music-fix commit since the release candidate's tick19g (64d9361): the LAN / AI-melee / teams / difficulty / terrain-LOD
work of the other lanes (their records), measured there, not here.

| item | owner / coordinator | state |
|---|---|---|
| A | "i lose mouse visibility/use when i click "exit game" to the replay/reconfigure/abort/exit menu but it comes back if i tab away and back" | **not reproduced** (n 9 boots, section A); no fix |
| B | "when you click to exit the game two frames flip back and forth really fast" | fixed: `I76_FADE_NO_FLIP` (staged presets on); the exit fade's 32 presents -> 0 (n 3 each) |
| C | "i would really like the barricade hit sound to interrupt a playing barricade hit sound" | fixed: `I76_SIGN_SOUND_RESTART` (staged presets on); 2nd hit 0.2 s later refused (stock n 4) -> restarted (n 3) |
| D | `--legacy-multiplayer` for people who want the stock multiplayer row | done: mp-menu 0 with the flag (n 6), 1 without (n 3) |
| E | "the game name populated with the next area name" / "I clicked on mondo burger and it said the game name was Seminole but it opened oil well well" | fixed: `I76_ARENA_NAME` (default on); names 15 / 42 -> 42 / 42, loads 48 / 48 the selected file |
| F | "The arrow keys in the pause menu control the car?" | fixed: `I76_MENU_KEYS` (default on); network, menu up: steer 0.67-0.92 / throttle 1.0 -> 0 / 0 (n 3 each) |
| G | Lee_____.ttf registrations pile up and lock the folder | fixed: `I76_FONT_PRIVATE` (default on); left 1 / 1 / 1 -> 0 / 0 / 0 per killed boot, rename OK 3 / 3 |
| H | 2026-10-21, release candidate: "still can't consistently see the pointer when I use the exit menu" | **cause found** (A's runs had recorded it): the pointer opens on the screen's bottom edge, y 1437 of 1440, 12 / 12 Esc opens. Fixed: `I76_MENU_PTR_CENTRE` (default on), y 720 in 5 / 5 opens |
| I | 2026-10-21: "the zoom or something changes as you arrow down the menu" | **reproduced** after Alt-Tab: from then on every second arrow press changes 43.5 - 45.6 % of the background (stock n 3, tick and P18). Fixed: `I76_MENU_DRAW` (default on): 0.29 - 0.49 % (n 3) |
| J | 2026-10-21: Up = look at the dash, Down = look back, "as on the Mac" | measured on a66a37f7: Up = look back (yaw 160), Down = look down (pitch -13 -> 6), n 3. Staged input.map 1c397955 swaps the two. Nothing installed |

Commits: `2a895ce` (B, C, D), `0e93834` (E, F), `747609a` (G), this record. Second session (H, I, J, 2026-10-21 evening): `17bbe96` (H, I proxy), this record's sections H - J.

## A. The pointer in the Esc menu's second level

**Route measured.** In mission, Esc opens the Spanner's Cafe "Options Menu" (Abort Mission / Play Options / Graphic Detail
/ Audio Control / Exit); ABORT MISSION opens the second level, "Abort Mission" (Replay / [Reconfigure in the campaign] /
Abort Mission / Exit Game, menu object 0x4fc440, the render-gate mode stays 0x10); its EXIT GAME opens a third page "Exit
Game - Are you gonna leave me, sweetheart? Yes / No" (0x4fcec0). Probe: lab `tools\menu-sound-polish\probe-exit.ps1`
(console, lock held): GetCursorInfo (showing flag, cursor handle), the clip, the engine's mouse globals (0x535f6c armed,
0x535f74), a relative mouse_event move and an absolute SetCursorPos each read back after 0.25 s and 1 s, on every page.

| run | route | Esc menu | second level | third page |
|---|---|---|---|---|
| a-base-2, a-base-3 (t01), k-before-1, k2-before-1..3, k2-after-1..3 (t05) | direct mission boot, tick19-42 preset env, staged proxy (k2-before: B / C / G switches off) | showing (flags 1, arrow 0x10003), clip = whole client, moves land | the same: showing, arrow, not armed, relative +120/+60 and absolute moves land and stay | showing, arrow (k2: n 6) |

n 9 boots, every reading the same: **the pointer was visible (as far as Windows reports) and usable on every page.** Not
reproduced. What differs from the owner's session: the campaign route (a bookmark, "Reconfigure" present), a real mouse,
and possibly the moment of the click. The campaign-route probe (`probe-campaign.ps1`: leg-b's bookmark route then the same
probe) did not reach the mission in the lane's runs (leg-b's TRIP click under the aw cursor map; then the console was held
by other lanes for most of the night). Static reading for the next step: the mission-over / Esc menus show the pointer with
the exe's own 0x44bcc0 (SetCursor arrow, ClipCursor NULL, ShowCursor up to >= 0) and hide it with 0x44bb40 (clip to the
client, recentre, ShowCursor down to -1, arm mouse-look 0x535f6c = 1); WM_ACTIVATEAPP (0x404a2c) calls them only in
mode 1, so an Alt-Tab during a menu (mode 0x10) changes neither: what Alt-Tab does there is ShowWindow minimise / restore
and dgVoodoo's own re-activation. **What it would take:** the owner's route on the console (bookmark -> mission -> Esc ->
ABORT MISSION, by hand or with leg-b fixed for the aw map), the same read-back; if Windows then reports the arrow hidden
(flags 0) or the armed flag 1, the fix is a proxy call of 0x44bcc0 when the second-level menu opens; if Windows reports it
showing, the loss is dgVoodoo's (its cursor emulation after a page change), and the test is the same session with
`I76_CURSOR_MAP_DGV=1` and with dgVoodoo's cursor options.

## B. Two frames flip back and forth on exit

**Cause** (static, i76.exe 6319abf7): leaving the mission and the mission-over / Exit Game path run the palette fade-out
0x479c60 -> 0x479a90 (callers 0x4036af, 0x4041da, 0x404341, 0x4044c7): 32 steps, each a palette upload ([0x5dd2c8]) and a
**present** (`call [0x5dd2e0]` at 0x479bdd), then a 10 ms wait (0.01 s x -1000 at 0x4be760). Under the hardware (Glide)
renderer the palette changes nothing on screen and nothing is drawn between the presents, so each present flips to the
other buffer: the last two frames alternate 32 times, about a third of a second.

**Fix** `I76_FADE_NO_FLIP=1` (polish.c; off by default, on in the staged tick19 presets): the present at 0x479bdd goes to
`fade_present`, which skips it while `[0x5dd2a8] == 1` (renderer_IsHardwareDevice 0x495060); the uploads and waits are
unchanged (the fade takes as long, the screen holds the last frame); the software renderer keeps its presents (there the
palette is the fade). `I76_FADE_LOG=1` (lab) logs the steps: in a-base-2 the stock path made 64 + 32 presents (mission end,
then the exit).

**Measured** (console, k2 runs: T05, Esc > ABORT MISSION > EXIT GAME > YES; the proxy's fade log, `I76_FADE_LOG` via
`I76_SIGN_SOUND_LOG`):

| | boots | presents in the exit fade |
|---|---|---|
| stock (switch off, k2-before-1..3) | 3 | 32 of 32 made (steps 1 / 8 / 16 / 24 / 32 logged "made") |
| **fix (k2-after-1..3)** | 3 | **0 of 32: all SKIPPED** |

The frame capture (a 430x180 centre crop, CopyFromScreen) ran at about 12 grabs a second, too slow for 10 ms steps: in
both conditions it saw one frame until the window closed (16-25 grabs, 2 distinct = the menu and the desktop after exit,
no A-B-A), so it neither shows the flicker before nor its absence after; the present count is the measurement. A faster
capture (DXGI desktop duplication) would be needed for the picture itself.

### B2. "The two frame stutter in the menu again" (2026-10-23, menu-stutter lane) - NOT reproduced; item B's fix intact

Owner (2026-10-23, exp-polish2 on the OWNER-2300-* trial presets, proxy bc2b0b9b = 2516fb4): "i'm getting the two frame stutter
in the menu again". The brief read it as a regression of item B by the day's work (sky-mirror, morph, mirror-detail, jump-nose,
far-edge, shade-smooth; ten DLL installs, the new preset keys).

**Item B itself holds.** The owner's own log (exp-polish2 mciproxy.log, every one of the day's 25 boots) carries
`fade: I76_FADE_NO_FLIP=1 (the palette fade's 32 presents skipped ...)`, i.e. the 0x479bdd patch verified; on the lane's copy
with the owner's preset and the live DLL the fade log reads `present SKIPPED` for 64 of 64 steps (r5, t05 boot fades; the same
instrument as the k2 rows above). Nothing in the day's commits touches 0x479bdd, [0x5dd2e0] or the menu draw 0x496870.

**The menu's own alternation, measured** (lab `tools\menu-stutter\ms-probe.ps1`: item I's instrument on a fresh robocopy of
exp-polish2 = `exp-menu`, one boot per row, direct mission boot, Esc > ABORT MISSION page, 6 grey Down + 6 Up taps, a 1/4
screenshot each, `bgdiff.py` = % of the background outside the panel differing from the page's first picture by > 40; S = menu
opened with the car standing, M = opened with W held 3 s; the taps alternate base / other buffer, the table gives the other
buffer's value):

| row | proxy | preset | map | S: other buffer | M: other buffer |
|---|---|---|---|---|---|
| r0 | bc2b0b9b (live) | OWNER-2300-ALL | t01 | 0.25 - 0.28 % | 0.99 - 1.03 % |
| r1 | bc2b0b9b | tick19-42 (before the day's keys) | t01 | 0.25 - 0.28 % | 1.02 - 1.06 % |
| r2 | da6dfbb8 (2026-10-21, lane 2's fix build; ignores the day's keys) | OWNER-2300-ALL | t01 | 0.29 - 0.32 % | 1.07 - 1.10 % |
| r6 | da6dfbb8 | tick19-42 | t01 | 0.25 - 0.28 % | 0.99 - 1.03 % |
| r3 | bc2b0b9b | OWNER-2300-FOG | t05 | 0.16 - 0.20 % | 0.26 - 0.30 % |
| r4 | bc2b0b9b | OWNER-2300-SMOOTH | t05 | 0.10 - 0.12 % | 0.24 - 0.28 % |

The day's DLL and the day's keys change nothing (r0 = r1 = r2 = r6 within 0.05 %; n 1 per cell, the spread between cells is the
run-to-run spread). What differs between the two buffers is the item I residual: the last two frames before the pause, one
frame of idle shake (S: the terrain rim, the mirror frame; `diffmap.py` pictures in `runs\r0-all-S\diff-02-04.png`) or one frame of
motion (M: road lines, horizon, mirror; `runs\r0-all-M\diff-02-04.png`). It is the same on every redraw of the page, mouse hover
included (0x496870: BeginFrame, panel blit, Flip, [0x5dd2e0]), and it is what the owner sees when he moves the pointer over the
page after an Esc while driving: a one-pixel edge shimmer, not an object drawn on alternate frames. The exit route (ABORT
MISSION click, r5, `ms-exit.ps1` with a 26 grabs/s four-crop capture): one picture held for 11.7 s after the click, no A-B-A.

Not tested (what would still make this a real regression): a flip the owner sees in the SHELL (i76shell's pages, after the
fade) - nothing in the day's code runs there, but it was not captured; the owner's wheel / i76wheel.exe as the pointer source.
Ask the owner WHICH menu and whether it flips with the pointer still: with the pointer still nothing presents (r5).

**If it is the residual**: the fix lane 2 named - one more 3D draw at pause entry so both buffers hold the paused frame.
Concretely, at shell_BeginInGameMenu 0x4953e0 (escmenu.c names it), before the panel's first draw: the loop's render block once
(0x401c90(0x4c2730) queue, [0x5dd2bc] BeginFrame, 0x4621e0(0x4c2730), 0x49b430, 0x49bee0, [0x5dd2c0] Flip) - the loop's own
Flip just put frame N in front and frame N-1 in the back buffer; one more draw of the paused state replaces N-1 with N' = N,
and every later redraw of the page shows the same picture. Under the tick the sub-tick interpolation of N' is up to one frame
newer than N (a fraction of the present shimmer); the sky scroll is per tick (I76_SIM_TICK_SKY_REF). Not built: the target is
unconfirmed and the budget went into the measurement. Switch name if built: I76_MENU_DRAW=2.

Files: lab `tools\menu-stutter\` (ms-probe.ps1, ms-exit.ps1 = probe-exit on the lane's copy with the fast capture, diffmap.py,
`runs\` with RESULTS.txt, the screenshots and the proxy log slices); the copy `exp-menu` retired after the run (a 1 s robocopy of
exp-polish2 remakes it); nothing installed anywhere; `.fps-queue` taken 11:38 - 12:40 (the far-edge and nitro-mp lanes yielded
between their boots).

## C. A barricade hit while the last one still sounds

**Cause.** A car hitting a class-4 object (road-closed barricade swend_1, sign post) plays vnvco3.wav on the car
(physics_CollideBodyPair 0x434e5c..0x434ebc -> sound_PlayOnObject 0x4231f0 -> 0x421b40). vnvco3.gpw's GAS0 header is all
-1, so: priority 50, **one instance**, one-shot, 0.386 s (11025 Hz, 4256 samples). The voice admission 0x422750 counts the
live voices of that name and, at the limit, takes one only for a strictly higher priority (0x4228b0 `jg`): the same car
asking again is refused, 0x421b40 returns 0, the hit is silent.

**Reproduced** (k-before-1, T05, the lane's barricade ram `barram.py`: a pass straight through the centres of the bars at
x 7280 / z 43915 and x 7275 / z 43920, 38 m/s): the proxy's request log `sign-sound: contact req 1 ... none playing ->
started`, `req 2 (0.20 s later) ... playing-before 124DFB0C kept (switch off) -> REFUSED`.

**Fix** `I76_SIGN_SOUND_RESTART=1` (polish.c; off by default, on in the staged tick19 presets): before the engine's call,
if a vnvco3 voice is live on that car (0x4221d0 by object + name) and the hit is new, the voice is stopped with the engine's
own stop 0x421e70 (Stop + Release + free, the path the per-frame update takes when a one-shot ends) and the engine's call
starts it again. "New" = the object hit (the part's tree root) has not (re)started it within 1.5 s, so a barricade whose bar
and legs touch over several passes restarts it once. Both paths: the engine contact (0x434ebc, chained) and the
I76_BREAKABLE_BOX sweep's knock-off (st_sign_sound, now given the sign's root). `I76_SIGN_SOUND_LOG=1` (lab) logs every
request (started / refused / restarted) and totals; the game is muted per process in the runs, so this log is the proof.

**Measured** (console, k2 runs, the same two passes per boot; the request log):

| | boots | hits that asked for the sound (bars knocked) | started | refused | restarted |
|---|---|---|---|---|---|
| stock (`I76_SIGN_SOUND_RESTART=0`, k-before-1, k2-before-1..3) | 4 | 3 per boot (3) | 2 per boot | **1 per boot: the second bar of the 7280 / 7275 pair, 0.20 s after the first** | 0 |
| **fix (k2-after-1..3)** | 3 | 3 per boot (3) | **3 per boot** | 0 | **1 per boot: that second bar** |

The third hit of each boot (pass 2, bar x 7120 / z 43920) came alone and started in both conditions. The game was muted
per process; the log is the proof (no audio capture).

## D. `--legacy-multiplayer`

`PLAY-i76.ps1 -LegacyMultiplayer` sets `I76_MP_MENU=0` for that launch over the preset and the shell (PLAY-LAN.bat sets 1
in the shell; the game's environment is built from the preset and then this), and (another lane, 4341d06) also
`I76_AIMELEE_ARENAS=0`. Every PLAY*.bat takes `--legacy-multiplayer`, `--legacy_multiplayer` or `-LegacyMultiplayer` in any
position; PLAY-TICK.bat keeps its `<ms>` (first argument that is not a flag); the folder is read before the argument loop
(SHIFT moves %0 too). Generator: lab `tools\menu-sound-polish\legacy_bat.py`; repo `tools/driver/PLAY-balanced.bat`,
`tools/mp-pack.py` (PLAY-LAN.bat); staged launchers for the release candidate, the daily driver and the LAN copy. Mac: one
`[Environment]` line `"I76_MP_MENU"="0"` in the wrapper prefix's user.reg (as tools/mp-mac-install.sh writes I76_COOP_AI), or
`open --env I76_MP_MENU=0 <app>`; Deck: `export I76_MP_MENU=0` in i76-env-mp.sh (docs/MULTIPLAYER.md section 5; documented,
not deployed).

**Measured** (headless, `dtest.ps1`: the staged launcher in exp-polish on a private desktop, the proxy log's
`mp-menu: mode N armed` and the tick line):

| launcher, arguments | n | mp-menu | tick |
|---|---|---|---|
| PLAY-TICK-42.bat | 2 | 1, 1 | 41.667 ms |
| PLAY-TICK-42.bat --legacy-multiplayer | 2 | **0, 0** | 41.667 ms |
| PLAY-LAN.bat (the shell sets I76_MP_MENU=1) | 1 | 1 | - |
| PLAY-LAN.bat --legacy_multiplayer | 1 | **0** | - |
| PLAY-TICK.bat 44 --legacy-multiplayer | 1 | **0** | **44 ms** |
| PLAY-TICK.bat --legacy-multiplayer 44 | 1 | **0** | **44 ms** |

(The first attempts of the plain and LAN cases did not start the game: the harness's own argument passing through
deskrun.py, which joins its arguments unquoted - an empty argument and a path with a space; fixed in dtest.ps1, not a
launcher fault.)

## E. The multi-melee GAME NAME and the "wrong" scenario

**Cause.** The host form (i76shell a300db63, EntryForm 0x10028610) keeps ONE ordered list: 15 stock arenas (table
0x1004b510, 0x2d bytes per entry: title +0, file +0x20) then the add-on .lvl files ([[0x100f2194]+8] - 0x3c + 4 index:
record title +0, file +0x20). The list rows (0x1002b3d2), the AREA OF PLAY box (0x1002b37e) and the file the host loads
(0x10028610 ~line 255: index < 15 the stock table, else the add-on record + 0x20) all index that one list. The only
consumer that did not was the default GAME NAME (two copies, 0x10029c5c and 0x1002a2c6): it always read the stock table,
`0x1004b510 + index * 0x2d`, so for index >= 15 it read past the 15 entries into the next table (the stock scenarios at
0x1004b7e0) and named the game after another entry. With the three AI arenas at 15..17, index 18 (Oil Well Well
(Scenario), file auto01.lvl) was named "Seminole" and index 19 (Mondo Burger) "Pretty Bus": **the owner's report is index
18: name "Seminole", mission Oil Well Well** - the name was wrong, the mission was the entry selected. (Whether his click
meant Mondo Burger and landed one row up on the Mac is a pointer question for the Mac lane: this PC's row hit test is
`(y - 0x97) / 14 + scroll`, measured exact on all 42 rows below.)

**Fix** `I76_ARENA_NAME` (polish.c, attached from mpmenu.c's shell hook; default on, `0` = stock): both copies call
`arena_name_stub`, which hands the shell the stock entry for index < 15 and the add-on record's own title for index >= 15
(index-generic: whatever the add-on list holds; copied through a 45-byte buffer, the stock entry size).

**Measured** (headless, lab `tools\menu-sound-polish\ef.py e`: exp-polish on a private desktop with the lab twin of the
staged proxy + the sp-fix lane's shell-click block (`Strlkup-msp-sc.dll`), the host form reached by clicks, each entry
picked the way a player does: list scrolled so it is the first row, first row clicked at y 158; read back the selected
index, the GAME NAME buffer 0x100d4050 and the entry's title / file):

| | entries | selected = clicked | GAME NAME = entry title |
|---|---|---|---|
| stock (`I76_ARENA_NAME=0`, e-stock) | 42 (15 stock, 3 AI, 7 scenarios, 17 co-op) | 42 / 42 | 15 / 42: every add-on wrong (15 "", 16 "Oil Well Well", 17 "Mondo Burger", 18 "Seminole", 19 "Pretty Bus", 20 "Race No Shoot", ... 25.. "") |
| **fix (e-fix)** | 42 | 42 / 42 | **42 / 42** |

n 1 per entry each. **Loads** (e-load: each entry picked as above, BROADCAST, the mission file the host loaded, 0x5049f0;
a fresh game process per load, see the crash below): **48 of 48 loaded the selected entry's own file with the entry's own
name** = all 42 entries once (m01..m15.msn, ai_hs2/4/6.lvl, auto01..07.lvl, coop01..17.lvl) + Mondo Burger, Seminole and
Oil Well Well (Scenario) twice more (n 3 each). **Joiner** (game-mpo-b joins the host's session, its own 0x5049f0): Mondo
Burger auto02.lvl = host's (n 1), Suburbia m04.msn = host's (n 2, the F network runs); the co-op scene join did not come up
headless (the lab click route stopped taking clicks on the join form after the first try; n 0 for co-op).

**Found on the way (not this lane's code, not fixed): hosting a second network session in the same game process crashes.**
e-fix's second load (leave by the stock end-of-session exit `0x4c2164 = 3`, MULTI MELEE > HOST again, BROADCAST) died at
`Strlkup.dll+0x23e97` = `mpf_parked_obj` (mpfill.c) called from `coop_ai_host_send` (map of the identical lab build),
`0xC0000005` reading freed memory, 2 s into the second session (n 1). The owner hosting a second game without restarting
would hit it. For the MP lane.

## F. The Esc menu's keys driving the car

**Stock** (static, i76.exe 0x4039e4..0x4039fc): the frame loop runs the sim block (collisions, input_ProcessFrame 0x44dec0
-> input_ApplyToEntity, the vehicle step) when the game is active and `0x4fe534 & 0x3e` is clear, **or** when 0x452d20 (a
network game) says so. The Esc menu, its sub-pages and the mission-over menu are 0x4fe534 = 0x10: single player skips the
sim (the menu pauses), a network game keeps it running, and input_UpdateControls 0x44d9e0 has filled the control block
0x5367c8..0x536803 from the keyboard and sticks, so the keys that work the menu also drive the car (on the PC map the
arrows glance / orbit the camera and A / D / W / S drive; on the Mac map, where the owner saw it, the arrows may be
bound to driving). The Mac (DxWnd) reaches the same frame loop: the cause and the fix are the same there.

**Fix** `I76_MENU_KEYS` (polish.c; default on, `0` = stock): while 0x4fe534 == 0x10 the input_ProcessFrame call 0x403a1c
(chained; under the tick it is the tick's gate) first clears the 15 dwords, so the car sees no key and zero axes:
input_ApplyToEntity's analog path sets throttle and steer to 0 (**the car coasts, wheels straight**; hold timers reset),
no gamekey fires; the menu's own keys arrive through the window procedure (0x496e10) and are untouched. The tick's early
tick on input ignores input while the menu is up (simtick.c st_input_changed). Built on escmenu.c (I76_MENU_PTR) rather
than beside it: it does not touch the Esc menu's mouse path.

**Measured** (headless `ef.py f1` / `f2`: the lab twin's shell-click block posts WM_KEYDOWN with the key's scan code; A
(steer_left) held 1.5 s and W (throttle_up) 1.0 s with the menu up, the player entity's steer +0xe0 / throttle +0xe4
sampled every 100 ms; first a control hold with no menu):

| | rounds | menu up, A held: max steer | menu up, W held: max throttle | control (no menu): max steer |
|---|---|---|---|---|
| single player t01, stock (f1c-stock) | 3 | 0 (keys in the block 5-8 of 9 samples; the sim is paused) | 0 | (the control fell in the opening, 0x20) |
| single player t01, fix (f1c-fix) | 3 | 0 | 0 | - |
| **network** (exp-polish hosts Suburbia, game-mpo-b joined), stock (f2c-stock) | 3 | **0.68, 0.67, 0.92** | **1.0, 1.0, 1.0** | 0.68 |
| **network, fix (f2c-fix)** | 3 | **0, 0, 0** (block empty 0 of 10) | **0, 0, 0** | 0.70 |

So stock single player already pauses under the menu; stock network play let the menu's keys drive the car, and with
`I76_MENU_KEYS` they do not, while the same key still steers with the menu closed.

## G. Lee_____.ttf registrations left behind

**Cause** (main's measurement, confirmed): i76.exe 0x4769e0 registers `<game folder>\Lee.fot` (the font resource file
for Lee_____.ttf) system-wide with AddFontResourceA and removes it only on its orderly shutdown path; any other end (crash,
kill, forced logoff, a harness stop) leaves one registration, and Windows keeps the files (and so the folder) in use.

**Fix** `I76_FONT_PRIVATE` (polish.c; default on, `0` = stock): i76.exe's two GDI32 font slots call AddFontResourceExA /
RemoveFontResourceExA with FR_PRIVATE: the font is the process's own, visible to its GDI text as before, and Windows drops
it when the process ends, however it ends.

**Measured** (headless `g-test.ps1`: leftover registrations for Lee.fot / Lee_____.ttf counted and cleared, boot to the
shell 45 s, the game KILLED, then: rename the folder `Interstate 76` and back, count again):

| | boots | registrations left by the boot | folder rename |
|---|---|---|---|
| stock (`I76_FONT_PRIVATE=0`) | 3 (g2) | 1, 1, 1 | failed 2 of 3 ("Access to the path ... is denied"; the third ran before the rename moved ahead of the count) |
| **fix** | 3 (g2) | **0, 0, 0** (the exe's AddFontResourceA logged in all 3: FR_PRIVATE = 1) | **OK 3 of 3** |

Earlier batch (g, rename after the count, Lee_____.ttf path only): stock kill 1 / 1 / 0, stock WM_CLOSE 1 (the game did not
close itself within 20 s at the shell), fix kill 0 / 0 / 0, fix close 0. The first stock boot of the night found 11 earlier
registrations of exp-polish's path (the lane's own earlier boots) and the g2 batch 5. Menu text with FR_PRIVATE: the Esc-menu
captures of the console runs (before = `I76_FONT_PRIVATE=0`, after = default), menu area 796x638 px: before vs after
0.046 % / 0.116 % of pixels differ by more than 40 (n 2 pairs; the second level 0.047 %), before vs before 0.087 % (the
order number and the 3D frame behind): the text draws the same.

## H. The pointer on the Esc menu, second session (2026-10-21 evening, lane 2)

Owner on the release candidate (`PLAY-TICK.bat`, proxy 8f8da929, 3440x1440): "still can't consistently see the pointer when I use
the exit menu". His three screenshots (Downloads `Screenshot 2026-10-21 180340 / 180404 / 180418.png`) are of the second-level
page ("Abort Mission": Replay / Reconfigure / Abort Mission / Exit Game), with the rows highlighted by keyboard. A Windows
screenshot never includes the pointer, so they cannot show where it was.

**Cause (measured).** The pointer was not hidden. It was **parked on the bottom edge of the screen** every time the Esc menu
opened:

| run | proxy | pointer while driving | pointer when the Esc menu opened |
|---|---|---|---|
| section A's runs (a-base-2/3, k-before-1, k2-before-1..3, k2-after-1..3) | lane 1 builds | (x, 720) | **(x, 1437)**, 9 of 9 |
| p2-b1, p2-b2 (tick19-42), p2-c1-p18 (P18 preset, no tick) | 8f8da929 (the RC) | (x, 720) | **(x, 1437)**, 3 of 3 |
| p2-d1, p2-d2, p2-f1, p2-f2, p2-f3-p18 | with the fix below | (x, 720) | **(x, 720)**, 5 of 5 |

The arrow's hotspot is its tip, so at y 1437 the whole arrow is drawn below the screen. Windows still reported it as showing
(GetCursorInfo flags 1, arrow 0x10003), which is all section A tested. Section A's JSONs had held this y the whole time.
The probes then moved the pointer onto a row with SetCursorPos, which hid the bug. A player sees no pointer until he moves
the mouse up far enough, and a click before that lands on the bottom row of nothing. With the mouse already moving while
Esc was pressed (H3), it showed at y 1308 (stock) / 591 - 595 (fix), the motion carrying it up from where it was put.

Why: the show-pointer routine 0x44bcc0 (every menu open, 0x4953e5) keeps x, sets y = `[0x5dcf30] / 2` (0x44bd38) and calls
SetCursorPos. `[0x5dcf30]` is the client height in screen pixels (read back: 1440, with `[0x5dcf2c]` = 3440), so y = 720. With
`I76_CURSOR_MAP` that SetCursorPos is the proxy's 640x480 UI -> screen map (cursormap.c `cm_SetCursorPos`), so 720 is read as
a UI y and goes to 720 x 3 = 2160, which Windows clamps to the last row. The proxy log of p2-b1 shows the round trip:
`GetCursorPos (1451,720) -> (270,240)`, then `(1451,1439) -> (270,479)`. In a real 640x480 mode `[0x5dcf30]` is 480 and the
stock code centres the pointer.

**Fix.** `I76_MENU_PTR_CENTRE` (escmenu.c; default on, `0` = stock): the load at 0x44bd38 (`mov eax, [0x5dcf30]`) reads 480
instead, so a menu opens with the pointer at UI y 240 (screen y 720), x unchanged. It applies only when the cursor map takes
i76.exe's slots (the Windows presets). Without the map there is nothing to correct (the Macs' DxWnd path, u32x alone). The
hide routine 0x44bb40 has the same arithmetic but runs while driving, with the pointer hidden, and is left alone.

**What else was tried, with real-input paths** (probe2.ps1 H1 - H4; n 3 boots with H, 2 stock + 1 fix plus d1): the
confirmation page reached by keys + Enter, no mouse move; one small move after it; Esc back; Alt-Tab away and back; the mouse
moving continuously (8 ms relative moves) through Esc and the page change. On every page Windows reported the arrow showing,
not armed (0x535f6c = 0), clip released, relative moves landing. Nothing else lost the pointer. Section A's "it comes back if I
tab away and back" fits the bottom edge: Alt-Tab hands the pointer to the desktop, and it comes back wherever the mouse is.

**What the owner should try** (once a build with H and I is installed): Esc, then look for the arrow in the middle of the screen
without touching the mouse; ABORT MISSION -> EXIT GAME by keys and by mouse.

## I. "The zoom or something changes as you arrow down the menu" (lane 2)

**The owner's screenshots, measured** (3440x1440, pixels differing by more than 40 outside the menu panel): 180340 -> 180404
(Replay -> Reconfigure highlighted) **0.01 %**; 180404 -> 180418 (-> Exit Game) **46.05 %**. In the third picture the cockpit
is drawn from another place (the dash and mirror larger and higher, PRND21 showing). The panel itself does not move.

**Ruled out first.** The arrow keys reaching the camera: the glance inputs 0x536770 / 78 / 80 stayed 0 / -13 / 0 through every
menu tap and a 1.5 s hold (grey and plain arrows, every run). input_ProcessFrame, their only writer, does not run while the
single-player menu is up. dgVoodoo's mode switch: the panel is identical between pictures and the client stays 3440x1440.

**Cause (static + measured).** With the Esc menu up in single player the frame loop draws nothing (0x4039ec -> 0x40402f). The
menu redraws only on a key or a hover: 0x496870 draws the panel over the back buffer and presents. Each arrow press therefore
flips to the other buffer and shows whatever 3D picture that buffer holds. Normally that is the last two frames drawn before
the pause, one frame of motion apart: **0.3 - 0.6 %** of the background, edges only. The window procedure's re-activation
path (WM_ACTIVATEAPP with the menu up, mode 0x10: 0x404a78) is different. It draws **one fresh 3D frame** with
renderer_DrawFrame (0x404a7d), outside the frame loop. That frame gets no camera pass (0x403e16), no cockpit / HUD pass
(0x403e80..0x403eaa), and the camera block as the frame's last pass left it, so it is a different picture. After it, every
arrow press alternates between that frame and the one that was on screen. **Alt-Tab back** triggers it, and so does anything
that takes and returns the focus: the owner's screenshot tool, or the Alt-Tab he uses to get the pointer back (H).

| run (all: t01, W held 4 s, Esc while moving, ABORT MISSION, 4 Down; Alt-Tab; 1 Down, 5 Up, 2 plain Down, a hold) | proxy | taps before Alt-Tab | taps after Alt-Tab: every other press |
|---|---|---|---|
| p2-b1, p2-b2 (tick19-42) | 8f8da929 (RC) | 0.02 - 0.58 % | **45.6 / 45.6 %** (n 2) |
| p2-c1-p18 (P18 preset, no tick) | 8f8da929 | 0.02 - 0.58 % | **43.5 %** |
| p2-d2: draw inside the tick's pose swap | e0fd672e | - | 44.8 % (no effect) |
| p2-d1: camera block put back first | 9f44d4ef | - | 45.2 % (no effect) |
| **p2-f1, p2-f2 (tick19-42), p2-f3-p18 (P18)** | **da6dfbb8** | 0.02 - 0.49 % | **0.29 - 0.49 %** (n 3) |

(The screenshot taken right after Alt-Tab is black in every run, stock and fix alike, until the next present. That is the
desktop capture of a just-restored flip-model window, not this fix.) The buffers keep their pictures across Alt-Tab: the first
press after it showed the old frame, 0.02 %, in every run. So the fresh frame was not needed to repaint anything.

**Fix.** `I76_MENU_DRAW` (simtick.c `apply_menu_draw`, applied with or without the tick; default on, `0` = stock): the
re-activation call 0x404a7d draws nothing, and the menu is drawn over the frame already in the buffer.
`I76_MENU_DRAW_LOG=1` (lab) logs each skipped draw (f1: 2, f2: 1, f3: 2). The gamma slider's redraws (0x496047 / 0x496061,
Graphic Detail) stay stock, because they must show the new gamma. Not fixed: the residual 0.3 - 0.5 %, the last two frames
before the pause. Making them identical needs one more 3D draw at pause entry. To the eye it is a one-pixel shimmer on edges.

**What the owner should try**: Esc while driving, Alt-Tab away and back (or take a screenshot), then arrow up and down. The
picture behind the menu should hold still.

## J. Up = look at the dash, Down = look back (lane 2)

**Measured** (probe2 J, cockpit, t01, n 3 boots: p2-a1, p2-f1, p2-f3-p18): on the shipped map `a66a37f7` the dedicated **Up**
arrow (GreyUpArrow -> `pilot_glance_up`) gives glance yaw **160** = **look back**, and **Down** (GreyDownArrow ->
`pilot_glance_down`) gives pitch **-13 -> 6** = **look down at the dash**. That is the opposite of what the owner wants.
`pilot_glance_up` is the engine's look-back (as HEAD-TRACKING.md found: "Up is LOOK BACK"). GOG's stock map binds it to the
Down arrow (`pilot_glance_up { + keyboard GreyDownArrow }`, `pilot_glance_down { + keyboard GreyUpArrow }`,
tools/controls-sheet/stock-2.1.0.17.json). Our map swapped them on the theory that "glance up" means look up (CONTROLS.md
"Looking up and down is the right way round").

**Which files.** The release candidate, the daily driver and `controls/input.map` are all `a66a37f7`. **The owner's Mac is
`a66a37f7` too** (`Interstate 76.app/.../GOG Games/Interstate 76/input.map`, 8843 bytes, dated 2026-10-17 16:22; md5 read over
ssh, nothing changed there). Every .MAP file in that folder has the same timestamp, so the Mac was reinstalled from the shared
map on 10-17. The "as on the Mac" he remembers is the Mac before 10-17, or the Mac answers the keys the other way under Wine
(not checked: that needs one key press on the Mac). `docs/input.map.reference` (what the Mac installer copies) has no keyboard
glance at all, only the hat.

**Staged, not installed** (lab `builds\polish2-20261021\stage\`): `input.map` **1c3979556ea9720c45a1ed9d2dc8f38a** =
a66a37f7 with exactly the two keys swapped plus a two-line comment (`input.map.diff`). `tools/lint-input-map.py`: OK against the
RC's i76.exe. Shift + arrows (tracking / overview camera) and the bare-arrow orbit in the chase view are unchanged. The keys are
free: no other block takes bare GreyUp / GreyDown in the cockpit. **Proposal:** promote it as the one map for Windows and the
Mac (controls/input.map, then the controls sheet and CONTROLS.md rows "Look up / Look down" regenerated). If the Mac really does
answer the other way, the swap belongs in the Windows copies only, and the Mac check decides that.

**What the owner should try**: copy `stage\input.map` over the test copy's `input.map` (the launcher keeps backups), then in the
cockpit: Up looks down at the dash, Down looks back. On the Mac: press Up in the cockpit on today's map and say which way it looks.

**Staged proxy for H + I:** lab `builds\polish2-20261021\staged\STRLKUP.DLL` **da6dfbb8d7337376dc72b0aede8ceff0** = the release
candidate's source (5a7f83b; the same recipe rebuilds 8f8da929 byte-identical) + `polish2.patch` (the two switches). MSVC x86
/MT /O2 /Brepro, `run1` / `run2` byte-identical. A drop-in for the release candidate: no preset change, both switches default
on. Runs: lab `tools\menu-sound-polish2\` (probe2.ps1, p2-lib.ps1, bgdiff.py; `runs\` holds every JSON, screenshot and
proxy-log slice) on the lane's copy `exp-polish2` (a robocopy of the RC). All runs on the physical console (`query session`:
console, not RDP), console lock held per run, I76_MUTE + the per-pid watcher, `I76_SHM_SUFFIX=exp-polish2`, the persisted mute
cleared at the end. I stopped two of my own queued runs before they booted and one mid-boot (I stopped its game and put the DLL
and the locks back). No other process was touched.

## Files

- Repo: `music-fix/polish.c` (all four switches + I76_FADE_NO_FLIP / I76_SIGN_SOUND_*), `music-fix/simtick.c` (two lines),
  `music-fix/mpmenu.c` (one call), `music-fix/strlkproxy.c` (include + five apply calls + two sweep call sites),
  `PLAY-i76.ps1` (-LegacyMultiplayer), `tools/driver/PLAY-balanced.bat`, `tools/mp-pack.py`, `docs/MULTIPLAYER.md`,
  `music-fix/README.md` (switch rows), `docs/OWNER-TEST-LIST.md`, this record.
- Lab: `builds\menu-sound-polish-20261020\` (src, run1 / run2, staged, MD5SUMS.staged, presets, presets.diff, launchers,
  lab-sc = the shell-click twin, never staged), `tools\menu-sound-polish\` (probe-exit, probe-campaign, barram, ef, g-test,
  dtest, legacy_bat, the queues; `runs\` = every result), `exp-polish` (the lane's copy; VERSION.md).
- Second session (H, I, J): repo `music-fix/escmenu.c` (I76_MENU_PTR_CENTRE), `music-fix/simtick.c` (I76_MENU_DRAW),
  `music-fix/strlkproxy.c` (two apply calls), `music-fix/README.md` (two rows); lab `builds\polish2-20261021\` (README, src,
  run1 / run2, staged, stage = the input.map, MD5SUMS.staged, the two superseded builds), `tools\menu-sound-polish2\`, `exp-polish2`.
