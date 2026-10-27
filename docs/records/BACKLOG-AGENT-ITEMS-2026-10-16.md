# Backlog agent items, 2026-10-16 (overnight lane `backlog-agent-items`)

The agent-only rows of [BACKLOG-2026-10-10.md](../status/BACKLOG-2026-10-10.md) section D that were still open in
[BACKLOG-2026-10-16.md](../status/BACKLOG-2026-10-16.md). Code and docs only: no game was started, no VM, no console lock
taken. The daily driver was read (presets, `PLAY-i76.ps1`, `i76shell.dll` md5) and not written. Host CPU was at 100 %
(other lanes' VMs) during part of the run; one pytest launcher test timed out at 120 s then and passed on re-run.

Tests: `python -m pytest tests` before **241 passed, 4 skipped**; after **244 passed, 4 skipped** (+3 new F2 tests).

## Item by item

| row | what | result | commits |
|---|---|---|---|
| F-21 | preset guard TERRAIN_LOD > 1 without FAR_CLIP | **already done** (`8a3f3c8`, `tests/test_presets.py` 13 presets); nothing to add | - |
| R-15 | repo presets = driver presets | **verified**: 13 / 13 `presets/*.psd1` byte-identical to the driver's, `PLAY-i76.ps1` identical; `setup-windows.ps1` / `Make-Wide-Conf.ps1` write `CaptureMouse = false` in the wide conf (since `808f756`) | - |
| R-01 | working-tree triage | i76-everywhere tree clean except other lanes' in-flight files (`music-fix/strlkproxy.c`, `music-fix/replay.c`), not touched. Lab: see R-16 | - |
| H-06 | lab `memlib.ps1:48` `InFire = 0x5367D0` | **done**: `ThrottleUp` 0x5367D0 + `WeaponFire` 0x5367DB + `Hardpoint1Fire` 0x5367DE (<re-archive> L031); no caller used `InFire` (git grep 0); map dot-sourced and read back. Lab `ENGINE-REFERENCE.md` rows 0x5367D0 and 0x52BBD0 / 0x52BBCC (L083) and `PHYSICS-60HZ.md` corrected | l:`ab03f33` |
| R-09 | the rest of DOC-CORRECTIONS | **done**: `src/u32x.c` 2 comments and e:`u32x/u32x_full.c` 1 comment re-pathed to `docs/records/` (same line count, binary unaffected); garage-ui `RESULTS.md` dated note; <re-archive> three agent briefs re-pathed; file marked closed | l:`40c4a6e`, m:`41cd310f`, e:`45df600` |
| U-05 | F2 orphaned bookmark | **built, emulated, staged on the twin** (below); live test is owner test T3 | e:`6779088`, m:`c2f76e9e` |
| U-13 | gate row D always FAIL | **fixed** (below) | l:`41d9abe` |
| U-12 | Click-UI free-pointer audit | **fixed in 6 scripts**, the rest listed (below) | l:`38f86a7`, verify `391c18e` |
| X-16 / C.3 | README rows for proxy switches | `I76_REF_FPS`, `I76_KEEP_ACTIVE`, `I76_FRAME_LOG` added; all 117 `"I76..."` names in the committed `music-fix` sources now appear in the README (3 missing before, 0 after) | e:`ac156cf` |
| R-16 | lab loose ends | stale lock `game\.console-test.lock.stale-20261006` moved to `autotest\runs\stale-locks\`; the 11 untracked 2026-10-12 `autotest\saves\runs` folders committed (131 files, 417,557 bytes = 408 KiB, PNGs stay ignored); `builds/**/*.exp, *.lib` ignored (68 files on disk; the commit message says 46, which was not counted - 68 is the count) | l:`568c3c5`, `f85c8ca`, `7533529` |

## U-05: F2 in detail

- Defect (<re-archive> `shell/FIXES.md` F2, `SAVE.md` s.4, static): `SaveMenu_Edit` 0x100147a0 sets the slot variable
  `[0x10057f80]` to -1 at 0x10014866 on every entry. Re-entry after the static edit record was appended skips the slot
  assignment, the save writes slot -1: `savegame.dir` names `saveNNN`, the disk gets `save-001.cmp`.
- `tools/patch-shell-modals.py` gains F2 **opt-in** (`--with-f2`, or `--only ...,F2`). The default set stays M1..K4: the
  default output on pristine `deb41008` is `8047c949` before and after the change (n = 1 each, deterministic).
- Patch: 10 bytes -> nop, HIGHLOW relocation at 0x10014868 neutralised; the tool fails closed when the stock relocation
  is missing; `--check` reports F2 and flags a live relocation left on it.
- Cross-check: `--only F2` on pristine = `6cd6b51f`, byte-identical to <re-archive> `tools/patch_shell.py --fixes F2`.
- Emulation (unicorn): slot value kept for 3 preset values, no live relocation on the range, a rebase to 0x20000000
  keeps the nops: patched 5 / 5 pass, stock control 5 / 5 MISMATCH (the check discriminates). Driver lineage
  `a300db63` + F2 = **`2ab4ca90`**, full emulation 58 / 58.
- Not done: the slot logic around the patch (the three writers of `[0x10057f80]`, the row-pick path) is the <re-archive>
  static trace, not re-derived or emulated end to end here.
- Staged on the lab twin `game-dd-20261003` (not the driver): `Interstate 76\i76shell.dll.F2` (`2ab4ca90`, built from
  the twin's own `a300db63`), `_tools\test-shell-f2.ps1`, `TEST-F2-bookmark-control.bat`, `TEST-F2-bookmark.bat`,
  README-TESTS entry. The twin's `i76shell.dll` is unchanged (`a300db63`).
- `tools/test-shell-f2.ps1`: backs up `savegame.dir` + `save*.cmp`, swaps the F2 shell in for one run (Mode F2) or not
  (Control), starts the game as PLAY.bat does and waits, restores the shell (md5 read back), parses `savegame.dir`
  (4 + 60n) and prints OK / ORPHAN plus any `.cmp` no bookmark names; refuses the driver, golden and Downloads paths.
  Checked offline on a scratch copy: swap and restore read back; verdict ORPHAN and OK on synthetic dirs; driver path
  refused (exit 2). Never run against a live game.

## U-13: gate row D

- Cause, from the run records: PLAY.bat / PLAY-balanced.bat / PLAY-16x10.bat copy a conf over `dgVoodoo.conf` before each
  start, so any gate on a folder whose conf differed failed D. 10 gate runs failed only on "CHANGED: dgVoodoo.conf"
  (20261003-115416, -141237, -201714; 20261004-225606; 20261005-082031, -082723, -113421; 20261008-205405, -205615;
  20261012-173603, the P8 PLAY-16x10 row).
- Fix: row D reads the launcher's `copy ... X.conf ... dgVoodoo.conf` lines and accepts `dgVoodoo.conf` ending equal to
  X's md5 from before the runs, reported in the detail. Any other change still fails; a .ps1 launcher accepts nothing new.
- Checked: the row-D block on 7 synthetic snapshots (all as intended, incl. the 16x10 conf failing under PLAY.bat and
  passing under PLAY-16x10.bat); parse 0 errors; `gate-folder -DryRun -Only 7` on the twin PASS 4 / FAIL 0 (run folder
  removed). Not run in a live gate.

## U-12: free-pointer audit

- Changed: `enter-mission5` (3), `enter-training` (2), `enter-trip1` (3), `setup\equip-weapon` (1),
  `setup\enum-weapon-picker` (1): raw `SetCursorPos(ux, uy)` -> `MoveTo-UI ux uy`, which is the same call in the default
  regime and the drawn position with `LAB_CURSOR_FREE=1`. `enter-melee`: ENTER AREA `Click-Screen 1648 1385` ->
  `Click-UI 296 462` (= the same point on the 3440x1440 map; `WEAPONS-MEMORY.md` lists 299,461). All parse; not run live.
- Verify (2026-10-16): `setup\equip-weapon` did not load `maplib.ps1`, so `MoveTo-UI` was undefined there and the script
  would have thrown on the first click (parse checks do not catch it). Fixed in lab `391c18e` (dot-sources maplib;
  `Get-Command MoveTo-UI` resolves). The other 5 scripts already load maplib.
- Already right: the gate rows' scripts (`option6-trip-test`, `garage-ui`, `test-escmenu` through Click-UI; `leg-b`
  handles the regime itself; `gate-folder` places and reads back).
- Left raw on purpose (listed, not changed): `calibrate\*` and `setup\find-weapon-ui` (sweeps), `saves\leg-a` (mode
  probe), `popup-repro` / `reminder-repro` (deliberate raw probes next to MoveTo-UI), `nucleus-q`, `mp-explore`,
  `msgbox-test` (screen or dialog pixels), `vptr-test` (retired VPTR), `tools\renderers\renderer-matrix`.

## Doubtful, listed not deleted

- Lab untracked, other lanes' current work (emu sources / results 2026-10-16, `tools/replay/`, `tools/retail-handling/`,
  `builds/*/src-*`, `builds/*/*.log`, `builds/music-retail-20261016/`, `builds/pad-menu*`, `builds/replay/`): not touched.
- The `builds/*/src-*` snapshot folders of 10-12..10-14 (ai-grid, ai-combat, box-spec, draw-dist, sign-fix-2): side-build
  sources kept for md5 provenance; the owner or the code lane decides whether to commit or drop them.

## Not done

- B.6 cactus2 class-4 classifier and the airborne detector on the interpolated pose (M each, need console runs to check).
- U-05 live test (owner test below). BACKLOG-2026-10-16 rows were not re-marked in place (other lanes edit that file);
  this record is the evidence for H-06, R-09, U-05 (staged), U-12, U-13, X-16, R-16.

## Owner test: F2 bookmark (about 10 minutes)

1. Twin `<lab>\game-dd-20261003`: double-click `TEST-F2-bookmark-control.bat`.
2. In the game: load any bookmark -> garage -> Options -> Save Bookmark; type `ORPHANA`; click once on empty paper right of
   the list (not a row, not a button); click the name field; type `ORPHANB`; click SAVE; quit the game.
3. The console window prints a VERDICT. Predicted: **ORPHAN** (if OK, the stock trace is wrong: say so).
4. Double-click `TEST-F2-bookmark.bat`, the same steps with a new name (e.g. `ORPHANC` / `ORPHAND`). Predicted: **OK**.
5. Start `PLAY.bat` in the twin once: the F2 bookmark should be in the Load Bookmark list, the control one missing.
Saves are backed up to `Interstate 76\save-backup-f2test-<time>` before each run; the shell is put back after the F2 run.
