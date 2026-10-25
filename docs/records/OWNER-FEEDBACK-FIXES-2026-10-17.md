# Owner feedback fixes (2026-10-17, evening)

Three fixes from the owner's second pass over `OWNER-TESTS-2026-10-17`. All work is in the lab. The daily driver
(`<games>\Interstate76-2026-10-03`) and the golden copy were only read. Every live game run held the lab
console lock, ran with host audio muted, and put back each file it changed (md5 read back).

| item | owner said | cause | fix | measured (n) |
|---|---|---|---|---|
| 02 / 03 86Box logged | "taking way too long to click the things and esc past menus" | the shared reference click sequences wait fixed times sized for the worst case | owner-test guest script polls game state, play mode and the scripted-player flag | retail T05 handover 108.1 -> 52.6 s guest; Gold melee 89.8 -> 34.9 s (n 1 each) |
| 08 / 09 hill top | "08 does not teleport so it takes too long to get there" | the start-pos placement ran once per game process, so a Replay started at the normal T05 spawn | the proxy re-arms the placement at every load of the booted mission | Replay placed again (n 1 live) |
| daily-driver pointer | "pointer shown a little to the right and maybe down of where the cursor appears" | three mappings of the 640x480 menu that agree only at the screen centre | 4:3 `[DirectX] Resolution` + dgVoodoo's own cursor slots mapped to the 4:3 fit | pencil to pointer: up to 242 px -> 3-8 px (n 1 each, 7 points) |

## 1. 02 / 03: faster guest automation

### Before: timeline of the old script

The old timeline is measured, not estimated:
- the owner's 15:49 session (`emu\results\memtrace\owner-20261017-1549\raw\PAR-I76DRV.LOG`);
- a headless re-run of the same script with a screenshot every second (par run `20261017-162136--ownfast-r-old-1`). Its
  guest timeline matches the owner's to 1 s.

All times are guest seconds since the guest script started. The guest clock is the one the waits run on.

| phase | old (wait in script) | what the guest needed (screens) |
|---|---|---|
| desktop -> game launched | 12.7 s: `wait 4000`, two COPYs with 4 + 3 s waits | the desktop is up at 0.6 s; each COPY takes 0.5 s |
| launch -> first menu click | 45.0 s: fixed 33 s, then 4 Esc 2 s apart, then 5 s | the menu was up 13 s before the first click; Esc 3 / 4 opened and closed the Options screen |
| main menu -> mission DONE click | 33.3 s: waits of 3 / 5 / 2 / 12 / 10 s | each shell screen came up 0.5-2.5 s after its click |
| DONE -> hand-over | 17.0 s | about 10.7 s of it is mission loading ("Somewhere in the Southwest", play mode 1) |

### Fix

The fix is in `OWNER-TESTS-2026-10-17\_lib\owner_tests.py`. `script(..., fast=True)` is now the default, and
`gen_scripts.py` is unchanged because the par reference runs share it.
- **Options and bookmark files.** Both are written with `filehex` (synchronous, read back). The only COPY is the
  10.6 KB `.CMP`, followed by a 1.5 s wait.
- **Intro movies.** The script waits 15 s, then runs 6 rounds of `tapif STATE ne 6 ESC` / `waitmem STATE eq 6 2500`:
  - Esc goes out only while the game is not yet in the shell;
  - each round returns as soon as the shell starts.

  STATE is retail `0x4a80f4`, Gold `0x4c2164`.
- **Menus.** The waits are the measured screen time plus a margin: 1.2 / 2.5 / 1.0 / 3.5 / 4.0 s.
- **Mission start.**
  - The script waits for play mode 0x20 (the opening cutscene). Esc goes out only while it holds.
  - It then waits for the scripted-player flag to be 1 (the opening camera). Esc goes out only while it holds.
  - The play mode is retail `0x4db008`, Gold `0x4fe534`. The retail address was found by matching Gold's
    `0x49cdc0` byte pattern in the retail exe (one match, `0x44f7c0`).
  - A probe run (`-ownfast-r-probe-1`) sampled the mode and the flag every 0.5 s against the screenshots: mode 1
    during the loading text, 0x20 from the cockpit cutscene on, and the flag 0 until the camera starts.
- **Melee.** The fixed 25 s wait after ENTER ARENA is replaced by `waitplayer`, which returns about 4.4 s after
  the click.

### After (headless, 1 VM, at most 2 86Box processes on the host)

| run | old | fast | saved |
|---|---|---|---|
| retail T05 bookmark, guest s to hand-over | 108.1 (owner 107.0) | **52.6** (`20261017-163710--ownfast-r-final-1`) | **55.5 s** |
| ... launch -> first menu click | 45.0 | 20.1 | 24.9 |
| ... menu -> DONE | 33.3 | 13.5 | 19.8 |
| Gold Instant Melee, guest s to hand-over | 89.8 (`-ownfast-g-old-1`) | **34.9** (`-ownfast-g-final-1`) | **54.9 s** |

- **End state, retail.** The retail run ends as the old one did: in the T05 cockpit with the HUD, play mode 1, the
  flag 0, the car at x 8505 doing 24.7 m/s after the camera skip (screenshot `0083-00085s.png`).
- **End state, Gold.** The Gold run ends in the arena cockpit.
- **Speed.** Both VMs ran at 0.73-0.85 of real time. On the owner's GUI VM the saving in wall time is therefore a little
  larger than the guest seconds.
- **Static check.** `python -I owner_tests.py check` reports ALL OK.

**Not run:** the `menu` start (it uses the same boot), and a session on the logging disk itself. The headless runs used
the par base disk with the same retail / Gold folders, and the guest timeline of the owner's own session matched.

## 2. 08 / 09: the hill-top start after a Replay

### Cause

The twin's `mciproxy.log` holds every 08 / 09 session of the day:
- 08 at line 226374;
- 09 at line 226584;
- the owner's long 08 run at line 228571.

In all three, `start-pos` placed the car once, 6 s after the mission started (frame ~724).

In the long 08 run the mission was then restarted. There were 6 `grSstWinOpen` against 3 in the short sessions, and
the mission music started again. After the restarts the owner hit the signs at x 8935 / 9935, next to the stock spawn
(8077 / 8368).

The code places the car "once per game process" (COLL-TIMING-2026-10-12.md s.3): a Replay starts at the stock spawn.
09's session had no Replay. So it was never 08-specific: 08 and 09 differ only in `I76_TERRAIN_LOD` 32 / 24 and
`I76_CLUTTER_FADE` 200 / 300, and their `I76_START_POS` is identical.

### Fix

The fix is in the proxy's `I76_START_POS` block, in i76-everywhere `music-fix/strlkproxy.c`, and in a lab side build.

- **Re-arm on every load of the mission.**
  - `simclock_Init` zeroes `simclock_frame_count` (0x5a7e1c) at the top of every mission, and the frame hook runs
    before `simclock_Update`. So a drop in the count means a new mission load.
  - The placement re-arms only if the loaded name (0x5049f0) is still `I76_MISSION`.
  - With `I76_MISSION` the shell is skipped (0x504c10), and every mission end except Replay exits the game
    (<re-archive> `subsystems/mission.md`). The Esc menu does not reload: state 5, play mode 0x10.
- **Speed held at 0.** The hold now sets the speed `+0xac` / `+0xb0` to 0 as well, as the trainer's STOP does.
- **Side build.** The lab build is `builds\hill-start-20261017\STRLKUP-hill-hs1.dll` (md5 `cb247d73`): the twin's
  33211f11 source (`box-spec src-b3`) plus this patch only.
- **Who uses it.** `twin-run.ps1` swaps it in for 08 / 09 and puts the twin's own proxy back afterwards. 08 / 09 no
  longer require the twin to hold 33211f11, because they bring their own proxy.

### Measured: live, lab twin, `tools\hill-start\hill-replay-check.ps1`, n 1

The script reads the player position from memory (`[[0x54a264]]+0x40`) and triggers Replay by writing 7 to the game
state 0x4c2164, which is what the menu's Replay writes (read back as 7).

| | placed | proxy read-back 1 s after release | memory 3 s after release |
|---|---|---|---|
| first start | frame 725, from (8368, 27.7, 44517) at 25 m/s | 5.2 m off, 10.7 m/s | (7972.6, 101.5, 44050.8), 15.9 m off in x/z |
| after Replay | `mission 't05' loaded again (Replay) - armed again`, frame 1862 | 5.2 m off, 10.7 m/s | (7972.7, 101.4, 44051.3), 16.3 m off |

### Open: the roll-off

After the release the car still rolls off the mark. It turns towards +z and is about 16 m away after 3 s.
- Holding the speed at 0 changed this only from ~13.5 to 10.7 m/s. So my first explanation (the grip snap rebuilding
  the velocity from the kept speed) was wrong.
- The suspect is the T05 opening sequence, which still drives the player when the hold ends.
- That was not measured: the scripted-flag sample run was blocked by another lane's console lock (`run-overnight.ps1`,
  16:41).
- The car stays on the crest (y 101.4), so the start is on the hill top, but not at a standstill.

### Side finding: the twin's proxy was swapped by another lane

The twin's `STRLKUP.DLL` was 33211f11 at 16:00 and `7429ba3c` at 16:2x. The change was made by another lane, not by
these runs. Each run here restored what it found.

## 3. The daily-driver mouse pointer

### Same files?

Read-only md5 comparison of the daily driver and the twin `game-dd-20261003`:
- **The same:** i76.exe, i76shell.dll, u32x.dll, the dgVoodoo DLLs, `dgVoodoo.wide.conf` / `dgVoodoo.conf`
  (`dccd379a`), PLAY.bat, PLAY-i76.ps1 and the best-wide preset (`e1a9bd26`). 90 files in the game folder match.
- **Different:**
  - the proxy: the daily driver has `509c6df0`, the twin `33211f11` (now `7429ba3c`, see 2). The cursor-map code
    between them differs only in the pad-menu path.
  - I76PLYR.DEF: audio sliders and difficulty only. The video byte is the same.
  - the saves.
- **Mismatches since then.** The twin's best-wide / best-wide-balanced presets changed at 16:42 (another lane) and no
  longer match the daily driver. The measurements below ran before that, or brought the daily driver's preset.

For an exact copy, every measurement ran the daily driver's own proxy `509c6df0` (the twin keeps a byte copy). The
game was launched as PLAY.bat launches it.

### Measuring: `tools\cursor-offset\measure-cursor.ps1` (via `cursor-run.ps1`), 3440x1440, main menu

For each screen point P the script reads three things:
- **the OS pointer:** `GetCursorPos`; `GetCursorInfo` says it is showing;
- **where a click acts:** the shell's own mouse (`[[0x100cc514]+0x2c/+0x30]`, as f2-drive) put on screen;
- **where the pencil is drawn:** dgVoodoo draws it into the frame. A BitBlt capture, diffed against two captures with
  the pointer elsewhere, gives the blob's top-left, which is the hotspot (Pencil.cur hotspot (0,0)).

Pencil position minus OS pointer, in screen px:

| point | daily driver set (509c6df0, conf dccd379a) | conf with 4:3 DirectX only | **fix** |
|---|---|---|---|
| centre (1720,720) | (+2, +4) | (+4, +7) | **(+4, +7)** |
| 12 % / 12 % (990,173) | (+242, +3) | (+322, +8) | **(+4, +8)** |
| 88 % / 12 % (2450,173) | (-241, +3) | (-322, +8) | **(+3, +8)** |
| 12 % / 88 % (990,1267) | (+242, +2) | (+326, +6) | **(+4, +6)** |
| 88 % / 88 % (2450,1267) | (-239, +2) | (-318, +6) | **(+3, +6)** |
| 25 % (1240,720) | (+161, +4) | (+217, +7) | **(0, 0)** |
| 75 % (2200,720) | (-161, 0) | (-213, 0) | **(+4, +7)** |

In every run the shell's click point equals the OS pointer to within 1 px.

The remaining +3..4 / +6..8 px is constant, about 1-2 UI pixels. It is most likely the faint tip pixels of the pencil
falling under the diff threshold.

### Cause: three maps of one 640x480 page, which agree only at the centre

1. **The picture.** `dgVoodoo.wide.conf` has `[DirectX] Resolution = 1680x1050`, which is 16:10. Under ScalingMode
   `stretched_ar`, the shell's 640x480 page is drawn 2304x1440 at x 568, a scale of 3.6, not 4:3.
   - TRIP / MELEE text centres at UI 216 / 444 are drawn at x 1352 / 2172.
   - The OPTIONS label starts left of x 760.
   - So the menus have been stretched 1.2x since promotion 16, whose record says "menus 4:3".
2. **The click.** u32x's `I76_U32X_SHELL_STRETCH` maps the shell to the 4:3 fit (scale 3 from x 760).
   - The click acts under the OS pointer.
   - On the 16:10 picture, that UI point is drawn 1.2x farther from the centre: about 96 px off at the 25 % points and
     145 px at 12 %. This is derived from the picture scale, not captured.
3. **The pencil.** The proxy feeds dgVoodoo's own GetCursorPos / GetCursorInfo slots (`I76_CURSOR_MAP_DGV=1`) with
   `I76_CURSOR_MAP=1`'s map, which is stretched over the whole 3440 px client.
   - dgVoodoo then draws that UI point on its 16:10 picture at x = 568 + 0.67 x.
   - This fits all 7 points to 3 px.

So the owner's "a little to the right" is a scale error about the centre (0 at the centre, up to 242 px at the sides),
not a constant offset. Where it looks "right" depends on which half of the screen he looked at.

The promotion 15 / 16 gates did not see this. They checked clicks against the shell's own mouse (the same 4:3
assumption as u32x), not against the picture or the drawn pencil.

### Fix, built and measured on the twin

1. **`dgVoodoo.wide.conf`:** `[DirectX] Resolution 1680x1050 -> 1920x1440`. The panel enumerates this 4:3 mode, and
   it is the exact 4:3 fit at scale 3.
   - The menus are then really 4:3: TRIP / MELEE give scale 2.98 from x 764.
   - The picture then matches u32x's click map.
   - Measured with this change alone: the pencil follows 760 + 0.558 x, as predicted.
   - File: `tools\cursor-offset\dgVoodoo.wide-dx43.conf`, md5 `aa6414e4f55c5984c6bd8c2f93ae08ef`. It is one line
     different from `dccd379a`.
2. **Proxy:** `I76_CURSOR_MAP_DGV=ar`. dgVoodoo's own cursor slots get the 4:3-fit map; the game's own slots keep the
   stretched map, which the in-mission Esc menu over the full-width Glide frame needs. `=1` behaves as before.
   - The build is the daily driver's own source revision (`sign-fix-2 src-509c6df0`; its rebuild has a byte-identical
     `.text` to 509c6df0) plus this `cursormap.c` patch only.
   - Output: `builds\cursor-dgv-20261017\STRLKUP-dd-cursor-cd1.dll`, md5 `eed513954e4df5b04b0971759cb77cda`.
   - The same patch is in i76-everywhere `music-fix/cursormap.c`, and HEAD compiles.
3. **Presets:** best-wide and best-wide-balanced, `I76_CURSOR_MAP_DGV '1' -> 'ar'`.

Result: the pencil sits within 3-4 / 6-8 px of the pointer at all 7 points, and the click acts under the pointer.

### Promotion proposal (for the owner; nothing was copied to the daily driver)

| daily-driver file | now | becomes | source |
|---|---|---|---|
| `Interstate 76\STRLKUP.DLL` | `509c6df0` | `eed51395` | lab `builds\cursor-dgv-20261017\STRLKUP-dd-cursor-cd1.dll` |
| `Interstate 76\dgVoodoo.wide.conf` | `dccd379a` | `aa6414e4` | lab `tools\cursor-offset\dgVoodoo.wide-dx43.conf` |
| `Interstate 76\presets\best-wide.psd1` | `e1a9bd26` | `63807739` | lab `tools\cursor-offset\best-wide-dgvar.psd1` |
| `Interstate 76\presets\best-wide-balanced.psd1` | `75881df4` | `4fb60abf` | lab `tools\cursor-offset\best-wide-balanced-dgvar.psd1` (made from the daily driver's own file) |

- **Not touched.** `dgVoodoo.conf` is rewritten from the wide conf by PLAY.bat / PLAY-balanced.bat at every start. The
  16x10 launchers use `dgVoodoo.16x10.conf` and presets without the cursor map, so they are unchanged.
- **Rollback.** `_rollback\<n>` gets the four old files.

**Gate** (as promotions 15 / 16, on the twin with this set staged):
1. `autotest\gate-folder.ps1` via PLAY.bat with LAB_CURSOR_FREE: all PASS (conf, bookmark route, trip at 120 fps,
   save screen NO / YES with the u32x modal arrow, Esc-menu Exit where drawn, melee, saves identical).
2. `tools\cursor-offset\cursor-run.ps1` with the staged set: pencil minus pointer within 10 px, and click minus pointer
   within 2 px, at all 7 points.
3. Garage OK popup: u32x arrow on the mapped point.
4. Intro movies and garage drawn 4:3.
5. PLAY-balanced.bat 2/2.
6. The owner runs `12-cursor-fix.bat` (n 1): pencil on the pointer in the corners, buttons answer where drawn.

**Not verified yet:**
- the in-mission Esc menu, the garage popup and the movies with the new conf. The `[DirectX]` mode changes only the
  2D / DirectDraw picture, and the patch leaves the game's own slots alone, but the gate must show it.
- PLAY-balanced.bat.

## What the owner should re-test

- **02 (and 03):** hands off until the cockpit / arena. Retail should be in T05 about 55 s (guest) sooner, Gold about
  55 s sooner. Report any menu that is left open or any Esc that lands on the Options screen.
- **08 (and 09):** Esc > Replay at least once. Each start should be on the hill top. The car still rolls ~15 m after it
  is placed (known, open).
- **12-cursor-fix.bat (new):** the pencil on the pointer tip in all corners; TRIP / MELEE / OPTIONS / EXIT answer where
  drawn; the menus look 4:3 (narrower than in PLAY.bat); the garage OK popup arrow; Esc > EXIT in a mission. Then:
  promote yes / no.

## Files

- **i76-everywhere:** `music-fix/strlkproxy.c` (start-pos), `music-fix/cursormap.c` (`I76_CURSOR_MAP_DGV=ar`), this
  record.
- **lab:**
  - `OWNER-TESTS-2026-10-17\_lib\owner_tests.py` (fast scripts), `_lib\twin-run.ps1` (08 / 09 proxy swap, 12),
    `12-cursor-fix.bat`, `README.txt`;
  - `tools\hill-start\hill-replay-check.ps1` + `runs\`;
  - `tools\cursor-offset\measure-cursor.ps1`, `cursor-run.ps1`, the conf / preset variants, `runs\cursor-*.json`;
  - `builds\hill-start-20261017\`, `builds\cursor-dgv-20261017\` (README, patch script, md5; DLLs on disk);
  - par runs `emu\results\par\20261017-16*-ownfast-*`.
