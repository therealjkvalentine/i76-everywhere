# Menu-pointer fix rebuilt on promotion 18 (2026-10-17, night, lane cursor-on-18)

The menu-pointer fix of OWNER-FEEDBACK-FIXES-2026-10-17.md item 3 was built on the daily driver's OLD proxy `509c6df0`.
Promotion 18 replaced that proxy with `33211f11` the same evening, so the fix could no longer be promoted alone. This
record rebuilds it on `33211f11`'s own source, gates it on the lab twin with the driver's post-promotion-18 files, and
proposes it as a promotion. The daily driver and the golden copy were only read (md5s and the presets the staged files
were made from). Every live run held the lab console lock (run-overnight.ps1), with host audio muted.

## 1. The build: `33211f11` + the cursor patch only

| | md5 | what |
|---|---|---|
| daily driver now | `33211f11c14d47d17a5e5c32cf835dd9` | lab `builds\box-spec-20261014\STRLKUP-box-b3.dll`, source `src-b3` (= this repo `eed2c1b` music-fix; comment-only diff to `2721d68`) |
| **candidate** | **`6850f968c96b533293ba09418aa047ee`** | lab `builds\cursor-on18-20261017\STRLKUP-cursor18-c18.dll`: `src-b3` + `patch_cursor.py` (cursormap.c only) |

- **Source diff.** Only `cursormap.c` changes. `strlkproxy.c`, `padmenu.c` and `strlkup.def` are byte-identical to
  `33211f11`'s source. The patched `cursormap.c` equals this repo's HEAD `music-fix/cursormap.c` (CR stripped).
- **What the patch does.** `I76_CURSOR_MAP_DGV=ar` gives dgVoodoo's own cursor slots (ddraw.dll / glide2x.dll
  GetCursorPos / GetCursorInfo) the 4:3-fit map. The game's own slots keep `I76_CURSOR_MAP`'s stretched map, which the
  in-mission Esc menu over the full-width Glide frame needs. With `=1` or unset, it behaves as `33211f11`. The `'1'`
  test goes through the same `env_str` helper and reads the value the same way as before.
- **The toolchain reproduces the driver's proxy.** A control rebuild of `src-b3` under its original file name is
  section-identical to `33211f11`: `.text`, `.rdata`, `.data` and `.reloc` all SAME, with the PE, export and debug
  timestamps masked (`pecmp.py`). Only those timestamps differ from the md5.
- **Deterministic.** A second build of the candidate tree (`run2\`, md5 `4f9c492f`) is section-identical to `6850f968`.
  - The output file name is stored in the export table, so the builds being compared must share it.
  - A first attempt with different names differed in `.rdata` only, for that reason.

## 2. The staged set (driver-equivalent, post-promotion 18)

Made from the daily driver's own files (read-only), lab `tools\cursor-offset\stage-c18\after`:

| daily-driver file | now (promotion 18) | becomes | change |
|---|---|---|---|
| `Interstate 76\STRLKUP.DLL` | `33211f11` | `6850f968` | section 1 |
| `Interstate 76\dgVoodoo.wide.conf` | `dccd379a` | `aa6414e4` | `[DirectX] Resolution 1680x1050 -> 1920x1440` (one line; the same file as in the first proposal) |
| `Interstate 76\presets\best-wide.psd1` | `3922146a` | `6efc4c51` | `I76_CURSOR_MAP_DGV '1' -> 'ar'` (3 bytes) |
| `Interstate 76\presets\best-wide-balanced.psd1` | `0bca8b31` | `0c95b996` | the same, 3 bytes |

- **Unchanged.**
  - `best-120.psd1` (`9b53c141`): it has no `I76_CURSOR_MAP_DGV`. PLAY-16x10.bat uses `dgVoodoo.16x10.conf`.
  - u32x, i76shell, i76.exe, the 16x10 conf, input.map, PLAY-i76.ps1 and the .bat files.
  - On the twin, all 9 of these were checked to match the driver by md5 (P10 stage row, PASS).
- **Superseded.** The first proposal's DLL (`eed51395`) and presets (`63807739` / `4fb60abf`) were built from the
  pre-promotion-18 files. They must not be installed now: they would undo promotion 18's preset lines and proxy.

## 3. Gate (lab twin `game-dd-20261003`, `run-overnight.ps1 -Phase P10`)

The new phase `autotest\overnight\phases\P10-cursor18.ps1` does the following:
- stages the set above and reads it back;
- checks the 9 untouched files against the driver;
- launches the twin through its **PLAY.bat** for the pointer runs, alternating before / after;
- runs gate-folder.ps1 (all rows, through PLAY.bat), row 3 through PLAY-16x10.bat and PLAY-balanced.bat, and the
  garage popup check.

The runner restores the twin after each batch.

### 3a. Pointer, click and intro movie (run `overnight-20261017-173900`, n 2 per set)

The figures are pointer minus drawn pencil in screen px on the 3440x1440 panel, main menu. The pencil is located by
`measure-cursor.ps1` and re-mined with `pencil-blob.py` (see the note below the table).

| point | before (driver: 33211f11, conf dccd379a, DGV 1) | **after (6850f968, conf aa6414e4, DGV ar)** |
|---|---|---|
| centre | (-2, -4) | (-4, -7) |
| 12 % / 12 % (on OPTIONS) | (-242, -3) | (-4, -8) |
| 88 % / 12 % | (+241, -3) | (-3, -8) |
| 12 % / 88 % | (-242, -2) | (-4, -6) |
| 88 % / 88 % | (+239, -2) | (-3, -6) |
| 25 % | (-161, -4) | (0, 0) |
| 75 % | (+161, 0) | (-4, -7) |
| **max** | **242 px** | **8 px** |
| click (shell mouse on screen) minus pointer | max 1 px | max 1 px |
| intro movie: union box of non-black pixels, x | 1..2870 (raw; picture right edge 2870 = the 16:10 picture 568..2871) | **1..2678 (raw; picture 760..2678 by eye = the 4:3 fit 760..2679)** |

- **Repeatability.** Both repeats of each set gave the same numbers to the pixel (n 2 + 2).
- **Reproduction.** The "before" column reproduces the owner's report and the first measurement (OWNER-FEEDBACK-FIXES
  item 3) on the promotion-18 driver: the offset is 0 at the centre and up to 242 px at the sides.
- **The x = 1 edge of the movie box** is dgVoodoo's frame counter in the top-left corner. It is in both pictures (so the
  JSON's `within_43` reads false for the after set too). The right edge is what tells 16:10 and 4:3 apart; the after
  picture's left edge 760 is read from `movie-c18-after-1.png`, not from the union box.
- **A measuring bug, fixed.** At the 12 % / 12 % point the pointer is on OPTIONS. Its highlight and the tooltip at the
  bottom are larger than the pencil, so the phase's first tally (largest blob) reported 1219 / 321 px there.
  - The capture shows the pencil on the pointer tip (lab `tools\cursor-offset\runs\p10-c18\cap-c18-after-1-1.png`).
  - `measure-cursor.ps1` now takes the largest pencil-sized blob (8-48 x 16-64 px).
  - `pencil-blob.py` re-mines the saved JSONs the same way. The table above uses it.
  - At the other 6 points, the old and new tallies agree.

### 3b. Garage OK popup (same run)

The check opens the garage, presses DONE without an engine, and closes the OK popup by click and by Enter, with the
after set and the cursor keys in LAB_GAME_ENV:
- closed 5/5;
- u32x modal arrow on the mapped point 4/4;
- PASS.

The twin's proxy log over the batch shows `I76_CURSOR_MAP_DGV=ar: 4:3 fit` x 2 (the after boots) and 0 CRASH lines.

### 3c. gate-folder (owner's route), PLAY-16x10, PLAY-balanced

**gate-folder, all rows, through the twin's PLAY.bat** with the after set: run `overnight-20261017-181147`, gate
`autotest\runs\gate\20261017-181224\results.md`. Result: **21 PASS, 0 FAIL, 2 INFO**.

| row | result |
|---|---|
| 1 conf accepted without the global file | PASS: 3440x1440 client, conf `aa6414e4` (the 4:3 `[DirectX]` mode is accepted) |
| 2 bookmark route (TRIP -> LOAD BOOKMARK -> LOAD -> ACCEPT SALVAGE -> DONE -> mission) | PASS 3/3 |
| 3 trip through PLAY.bat | PASS 2/2, 120.0 / 120.3 fps |
| 4 save screen | PASS: idle mouse gate, NO writes nothing, YES writes only the scratch bookmark, u32x modal arrow on the prompt both sessions, savegame.dir exact and put back |
| 5 in-mission Esc menu: Exit clicked where it is drawn | PASS: pointer (2326,1338) read back, HIT, mode 0x10 -> 0x1 (the game's own slots keep the stretched map, as designed) |
| 6 melee by menus | PASS |
| 7 input.map lint, unchanged | PASS |
| 8 force feedback | INFO: no wheel plugged in (as in every unattended gate) |
| 1 watermark probe | INFO (by eye) |
| S saves byte-identical / D folder drift | PASS / PASS |

The twin's proxy log over the batch shows `I76_CURSOR_MAP_DGV=ar: 4:3 fit` x 10 (every boot of the gate) and 0 CRASH
lines.

**Row 3 through the other launchers** (run `overnight-20261017-182430`):

| launcher | result |
|---|---|
| PLAY-balanced.bat (best-wide-balanced `0c95b996`, wide conf `aa6414e4`) | **PASS 2/2, 120 / 120 fps** (gate `20261017-182954`) |
| PLAY-16x10.bat (best-120 `9b53c141` + 16x10 conf: neither is changed by the fix; only the DLL is new) | **PASS 2/2, 120 / 120 fps** (gate `20261017-194209`, lab `tools\cursor-offset\row3-16x10-c18.ps1` under `with-console.ps1`) |

A first 16x10 attempt inside P10 failed 0/2 (gate `20261017-182725`), but the cause was the harness, not the game:
- P10's environment set `LAB_CURSOR_FREE=1` for every run;
- the 16x10 conf captures the mouse (`CaptureMouse = true`), so the harness clicked the free-map point and missed TRIP.
  The capture shows the main menu, still waiting;
- P9 sets the variable only for a `CaptureMouse = false` conf, and P10 now does the same;
- the re-run, with the variable unset as P9 does there, passed.

**The in-mission Esc menu: what the player sees** (same run, t01 + Esc, `test-escmenu.ps1 -Stage open` +
`measure-cursor.ps1 -Where escmenu`, n 2 per set):
- At all 7 points, in both sets, the captures hold no pencil blob. The game's own cursor is off over this menu
  (`cur_en 0` in test-escmenu's read).
- `GetCursorInfo` reports the Windows arrow showing, so the player sees the OS pointer itself.
- The `ar` map therefore changes nothing visible there. Gate row 5 above shows the Exit click acts where Exit is drawn.

## 4. Promotion proposal (the owner's call; nothing was copied to the daily driver)

Install the four files of section 2 into the daily driver AND the golden copy, the way promotions 15 / 16 / 18 did
(`Promote-To-Driver.ps1` recipe):
- with the game closed;
- `_rollback\18\` gets the four old files;
- PROMOTIONS row 18;
- read back the md5s;
- sync this repo's `presets\best-wide.psd1` / `best-wide-balanced.psd1`.

Sources (lab):

    6850f968c96b533293ba09418aa047ee  builds\cursor-on18-20261017\STRLKUP-cursor18-c18.dll        -> Interstate 76\STRLKUP.DLL
    aa6414e4f55c5984c6bd8c2f93ae08ef  tools\cursor-offset\stage-c18\after\Interstate 76\dgVoodoo.wide.conf
    6efc4c51ae777a4596f8caa2e419fec3  tools\cursor-offset\stage-c18\after\Interstate 76\presets\best-wide.psd1
    0c95b996a897a1ca9a777675c102398d  tools\cursor-offset\stage-c18\after\Interstate 76\presets\best-wide-balanced.psd1

**Rollback.** Copy `_rollback\18\` back in both folders and read back `33211f11` / `dccd379a` / `3922146a` /
`0bca8b31`.

**Not touched.** `dgVoodoo.conf` is rewritten from the wide conf by PLAY.bat / PLAY-balanced.bat at every start. The
16x10 path is unchanged.

**Multiplayer pack.**
- The game-night pack copies the driver's files. Promoting this changes 4 of them, so the pack would need a rebuild to
  match.
- Whether the cursor change matters on the Macs was not checked.
- Timing is the owner's choice. This lane did not touch the pack.

**What the owner should look for** (`OWNER-TESTS-2026-10-17\12-cursor-fix.bat`, now the rebuilt set on the twin):
- the pencil on the pointer tip in all four corners;
- TRIP / MELEE / OPTIONS / EXIT answer where drawn;
- the menus and intro movies narrower (4:3) than in PLAY.bat;
- the garage OK popup arrow;
- Esc > EXIT in a mission.

Then say: promote yes / no.

## 5. Small extra: test 08's roll-off after the hill-top placement

### Cause

T05's opening drives the player's car with the AI. i76-map `subsystems/ai.md` M49a describes the latch involved:
- 0x5244c0 = "an AI control writer touched the player's car last frame";
- the keys are locked while it is set;
- the T05 opening keeps a behaviour stack on the player.

The proxy placed the car 6 s after it went live, while the opening was still running:
- with hs1 (run `tools\hill-start\runs\20261017-162948.json`) the first start was placed at frame 725, from (8368.1, 27.7,
  44517.4) at 25.00 m/s (frame 412 / (8579.7, 28.0, 44517.4) / 24.25 m/s are hs2's placement, after the opening);
- the opening's AI kept throttling and steering after the hold ended;
- 1 s after the release the car was at 10.7 m/s, turned towards +z, and 16 m off after 3 s.

This is the suspect named in OWNER-FEEDBACK-FIXES item 2. The fix's result below supports it.

### Fix: start-pos patch 2

- **Where.** This repo's `music-fix/strlkproxy.c`, and lab `builds\hill-start-20261017\patch_startpos2.py`.
- **Side build.** `STRLKUP-hill-hs2.dll` = hs1 (`33211f11` + patch 1) + patch 2, md5
  `a091142da9614b144a94414b03d2666a`, no warnings.
- **What it does.** The delay now counts only from the moment the player is live AND no longer driven by the opening:
  - play mode 0x4fe534 & 0x3e clear and the latch 0x5244c0 = 0, the same test replay.c uses;
  - if the latch never clears, the car is placed 60 s after it went live anyway, and that is logged;
  - the read-back line also logs the latch and the play mode.

### Measured

Live on the lab twin with `tools\hill-start\hill-replay-check.ps1 -Dll hs2`, TEST-hill-next.bat. n = 1 run, 2
placements: the first start and one Replay.

| | hs1 (OWNER-FEEDBACK-FIXES, n 1) | **hs2** |
|---|---|---|
| read-back 1 s after release | 5.2 m off, 10.7 m/s | **0.29 m off, 0.61 m/s, AI latch 0, play mode 0x01** (both placements) |
| memory, 3 s after release | 15.9 / 16.3 m off | **3.14 / 2.75 m off** |
| Replay re-placed | yes | yes (`armed again`, frame 921) |

- **Timing.** The opening held the latch for about 8.6 s (241 / 243 frames). The car is now placed about 14.6 s after
  it goes live instead of 6 s.
- **Remaining drift.** The ~3 m left is the drop and settle onto the crest (0.6 m/s at 1 s, y 101.8 -> 101.1). The car
  stays on the hill top, facing down the road.
- **The log shows a "not driven" line twice per start.** The latch flickers once at the start of the opening, before
  the 8.6 s drive. The placement itself happened once per start.
- **Owner test 08 / 09** (`twin-run.ps1`) now swaps in hs2. The daily driver has no `I76_START_POS` in any preset, so
  this only matters for the hill tests, and patch 2 does not touch any promoted file.

Run JSON: lab `tools\hill-start\runs\20261017-185459.json`.

(verify) A second hs2 run on disk, `tools\hill-start\runs\20261017-191530.json` (uncommitted, same DLL a091142d), agrees:
read-back 0.29 / 0.27 m at 0.61 / 0.59 m/s with the latch 0, 3.56 / 2.66 m off after 3 s, latch held 242 / 240 frames.
With it, hs2 is n 2 runs, 4 placements: 2.66-3.56 m after 3 s.

## Files

- **This repo:** this record; `music-fix/strlkproxy.c` (start-pos patch 2, section 5).
- **Lab:**
  - `builds\cursor-on18-20261017\` (README, `dlls.md5`, `patch_cursor.py`, `pecmp.py`; DLLs and src trees on disk);
  - `tools\cursor-offset\stage-c18\` (before / after sets), `best-wide*-p18-dgvar.psd1`, `pencil-blob.py`,
    `measure-cursor.ps1` (`-MovieCap`, pencil-sized blob), `runs\p10-c18\`;
  - `autotest\overnight\phases\P10-cursor18.ps1` + `run-overnight.ps1 -Phase P10`;
  - `OWNER-TESTS-2026-10-17\_lib\twin-run.ps1` (test 12 -> `6850f968` + `6efc4c51`), `README.txt`;
  - `builds\hill-start-20261017\patch_startpos2.py`, `STRLKUP-hill-hs2.dll` (section 5).

## 6. The driver's wide menu with the pointer on the pencil (2026-10-19, lane cursor-wide)

Owner, after PLAY-TICK: "mouse is in the right place on play-tick! i like the menu aspect ratio from the daily driver in
games 10-03 play.bat though." This section keeps the driver's menu picture and moves the pointer maps onto it.

- The daily driver, the golden copy and game-tick were only read.
- Every run was on the lab's own copy `game-cwide` (a robocopy of game-tick).
- Every run held the console lock, with I76_MUTE=1 and the per-pid mute.

### 6.1 What the driver's menu is, and why the tick conf's pointer is right

- **The driver's menu is 16:10, not 21:9.**
  - dgVoodoo.wide.conf dccd379a has `[DirectX] Resolution = 1680x1050` with `ScalingMode = stretched_ar`.
  - dgVoodoo stretches the 640x480 page to 1680x1050 and fits that into the 3440x1440 window.
  - The picture is therefore 2304x1440 at x 568..2871 (x scale 3.6, y scale 3).
  - The capture (lab `runs\cap-cwide-ctl-1-1.png`) shows it; dgVoodoo's frame counter sits at x 569.
- **Under the driver's preset (best-wide, `I76_CURSOR_MAP_DGV='1'`), three readers use three different maps:**
  - **The OS pointer.** This is the reference.
  - **dgVoodoo's pencil.** It is drawn at 568 + 3.6 v, where v is what dgVoodoo's GetCursorPos returns.
    - With DGV 1, v is the stretched map v = x / 5.375, so the pencil sits at 568 + 0.67 x.
    - Measured: 242 px off at the 12 % insets (s.3a).
  - **The shell's hit test.** u32x maps i76shell's pointer over the 4:3 fit (760..2680), whatever the [DirectX] mode
    (u32x_full.c get_map).
    - The button that answers is drawn at 568 + 1.2 (x - 760), up to about 190 px from the pointer at the sides.
    - Example: the control run reads shell UI (77, 58) at x 990, but the 16:10 picture draws UI 77 at x 845.
- **The tick conf aa6414e4 works because its picture is the 4:3 fit.**
  - `[DirectX] Resolution = 1920x1440` (4:3) makes dgVoodoo's picture the 4:3 fit (760..2679, scale 3).
  - That is the picture u32x already assumes.
  - `I76_CURSOR_MAP_DGV='ar'` feeds dgVoodoo the same 4:3-fit map.
  - So all three readers share one map. The cost is the narrower menu.
- **No dgVoodoo key gives both the 16:10 look and a 4:3 pointer.**
  - The wide look comes only from a non-4:3 [DirectX] mode.
  - u32x's shell map is fixed at 4:3 (or the whole client under `ScalingMode = stretched`).
  - So the fix has to be in the proxy.
  - Not tried: `CaptureMouse = true`, where dgVoodoo maps the pointer itself. It changes the confined / free regime that
    u32x and the Esc menu depend on.

### 6.2 The fix: `I76_CURSOR_MAP_DGV='aw'` (this repo `1ca6ba0`, music-fix/cursoraw.c)

- **dgVoodoo's cursor slots** get map mode 3: the 640x480 page over the fit of the picture aspect, with x and y scaled
  separately.
- **u32x keeps the shell.** Its modal arrow in the OK popups and its pumps are unchanged.
  - Its own USER32 imports go behind an adapter: GetCursorPos, SetCursorPos, ClipCursor, PeekMessageA mouse lParams,
    and SetWindowPos of its u32xVptr arrow.
  - The adapter converts between the real picture and the 4:3 picture u32x maps over.
  - u32x's 4:3 map of the adapted point is then UI = (x - 568) / 3.6.
- **i76.exe's slots** keep `I76_CURSOR_MAP`'s stretched map. The in-mission Esc-menu path is unchanged.
- **The aspect** is `I76_CURSOR_MAP_ASPECT` if set. Otherwise it is read from dgVoodoo.conf next to the exe:
  - `[DirectX] Resolution`;
  - or the whole client under `ScalingMode = stretched`.
- **Requires** `I76_CURSOR_MAP_U32X='exe'`. Every wide preset already sets it.
- **Off by default.** `'1'` and `'ar'` are unchanged.
- **Log line:** `aw picture aspect 1680:1050 ... u32x.dll 5/5 USER32 slots behind the picture adapter`.
- **Lab build:** `builds\cursor-wide-20261019\STRLKUP-cwide-1ca6ba0.dll`, md5 `519739f61c35bbab81ed00cee7fa2d6c`, no
  warnings.
  - It is built from HEAD 1ca6ba0, so it also carries the mute switch and the tick factors.
  - It is installed only in game-cwide.

### 6.3 Measured (main menu, `measure-cursor.ps1`, 7 picture points, screen px on 3440x1440, n 2 per set)

| set | proxy | preset (DGV) | conf | test points | pointer minus pencil, max | shell hit (land) minus pencil, max |
|---|---|---|---|---|---|---|
| driver as is (control) | 33211f11 | p18-best-wide = driver's best-wide 3922146a (`1`) | dccd379a | 4:3 fit | **242 px** (-242 / +241 at the insets, +-161 at 25 / 75 %) | 241 (in the 4:3 fit, wrong for this picture; see below) |
| PLAY-TICK | tick19e a08577c4 | tick19-33 (`ar`) | aa6414e4 | 4:3 fit | **8 px** | 7 |
| **new: wide menu + aw** | cwide 519739f6 | tick19-33-aw (`aw`) | **dccd379a** | 16:10 fit (844..2596) | **4 px** (centre (-2,-4), insets (-3..+1, -2..-3)) | **4** (in the 16:10 picture) |

- **Repeatability.** Both runs of each set agree to the pixel (n 2 + 2 + 2).
- **The aw menu is the driver's picture.** `cap-cwide-aw-1-1.png` shows the same 16:10 frame as the control capture.
  The pencil is on OPTIONS and OPTIONS is lit.
- **No CRASH line** in any proxy log.
- **The control's land column is computed in the 4:3 fit.** In the real 16:10 picture its hit lands about 190 px from
  the pointer at the insets (6.1).
- **Files.**
  - JSONs: lab `tools\cursor-offset\runs\cursor-cwide-{ctl,tick,aw}-1.json` and `-{ctl,tick,aw}r2-1.json`.
  - Next to them: the `proxylog-*` and `cap-cwide-*` files.
  - Table: `tools\cursor-offset\cwide-table.py`.

**In-game HUD / 3D** (`cwide-shot.ps1`, t01 direct boot, a capture 6 s after the player is live, n 1 each):
- `shot-tick.png` (the PLAY-TICK set) and `shot-aw.png` (the aw set + wide conf) show the same cockpit, HUD, mirror and
  21:9 3D frame.
- Mean absolute pixel difference: 1.0 / 255 over the HUD band, 1.8 / 255 over the frame; 0.5 % of pixels differ by more
  than 40. That is scene motion and the fps counter.
- The [Glide] keys of the two confs are identical.

### 6.4 To fold in (the main session; nothing was installed into game-tick)

The fix is a proxy change, so, per the brief, game-tick and the candidate folder were left unchanged. For the next
candidate:
1. a proxy built from `1ca6ba0` or later;
2. `I76_CURSOR_MAP_DGV = 'aw'` in the tick presets;
3. PLAY-TICK*.bat copying **dgVoodoo.wide.conf (dccd379a)** instead of dgVoodoo.tick.conf (aa6414e4).

How the two settings pair with the confs:
- `'ar'` + aa6414e4: the pointer stays right, with the 4:3 menu.
- `'aw'` + dccd379a: the pointer is right, with the driver's 16:10 menu.
- `'aw'` under aa6414e4 reads a 4:3 aspect and so equals `'ar'`.

**Not measured with aw:**
- the garage / reminder OK-popup arrow (u32x's u32xVptr window, through the SetWindowPos adapter);
- the save screen;
- the in-mission Esc menu (aw does not change the exe's slots);
- gate-folder.

All of these belong in the candidate's gate.
