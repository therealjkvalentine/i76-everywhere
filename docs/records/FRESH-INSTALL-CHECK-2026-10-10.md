# Fresh-install check 2026-10-10: Setup-From-GOG.ps1 on clean folders, offline, game not started

Backlog R-04 ("Fresh `Setup-From-GOG.ps1` install + boot on a clean folder; blocks v1.1.0"), the half an agent can do
without the console. **The game was not started** (console unavailable), so the boot itself stays an owner test:
[OWNER-TEST-LIST.md](../OWNER-TEST-LIST.md) item 16.

## What was run

- **Input**: GOG's offline installer `setup_interstate76_2.1.0.17.exe` as unpacked by innoextract into
  `C:\Users\james\i76-map\sandbox-gog\main\app` (371 files; `i76.exe` `9a232dcc`, `i76shell.dll` `deb41008`, no
  `I76PATCH.DLL`). Copied, unchanged, into six scratch folders under `%TEMP%\i76-fresh-install-20261010-095059\<variant>\Interstate 76`.
  The source was re-hashed afterwards: unchanged.
- **Command**: what `INSTALL.bat` runs, `powershell -NoProfile -ExecutionPolicy Bypass -File Setup-From-GOG.ps1`, plus the switches an
  offline test needs: `-GameDir <scratch>` (instead of `C:\GOG Games\Interstate 76`), `-GogExe <a zero-byte dummy>` (the game is
  already in the folder, so the GOG installer is skipped; the dummy makes sure it could never run), `-ToolsDir <scratch copy of
  C:\Games\_tools\dgVoodoo2_87_3 + AutoHotkey_1.1.37.02>` (so nothing is downloaded and `C:\Games\_tools` is not written),
  `-SkipNitro` (otherwise the Nitro installer in Downloads would run), `-NoShortcut`, `-Yes`. Repo at `3f2b792`.
- **Variants**:

| folder | switches | display the setup used |
|---|---|---|
| A-default | (none) = `best-120`, `-Controls i76e` | real primary display |
| B-wide | `-Preset best-wide` | `I76_WIDE_DISPLAY=3440x1440` (the owner's panel) |
| B2-wide-realdisplay | `-Preset best-wide` | real primary display |
| C-ctlstock | `-Controls stock` | real primary display |
| D-balanced | `-Preset best-wide-balanced` | `I76_WIDE_DISPLAY=3440x1440` |
| E-stock | `-Preset stock` | real primary display |

The session was a Remote Desktop session, so the "real primary display" was the RDP desktop, **1726x1011**. That changes the
`Resolution` digits of the 16:10 conf (below); the `I76_WIDE_DISPLAY` override only reaches the widescreen step.

All six runs exited 0. No download was attempted (both tool folders were found), the desktop and `C:\Games\_tools` were unchanged
(listing and file count before/after), no `%TEMP%\i76-gog-install-*.log` appeared (no GOG installer ran).

Verification: a script (`verify.py`, scratch) hashed every file of each folder against the pristine tree and the repo; the launcher's
`-DryRun` was run for every `PLAY*.bat` the setup wrote, with that .bat's own arguments; the input.map lint ran on every folder.

## Results per check

| check | A | B | B2 | C | D | E |
|---|---|---|---|---|---|---|
| verifier checks passed | 64/64 | 71/71 | 71/71 | 62/62 | 71/71 | 61/62 (1) |
| `Strlkup.dll` = `c11f7f7d`, `strlkup_orig.dll` = GOG's `e5951e0f` | pass | pass | pass | pass | pass | pass |
| `u32x.dll` = `06467bd2`; `i76.exe` / `i76shell.dll` exactly 10 bytes off pristine; `.u32xorig` / `.orig` = pristine | pass | pass | pass | pass | pass | pass |
| 13 `presets\*.psd1` byte-equal to the repo | pass | pass | pass (2) | pass | pass | pass |
| dgVoodoo Glide / DDraw / D3DImm / Cpl = dgVoodoo 2.87.3; GOG's glide.dll, glide2x.dll, glide2x.ovl in `_openglide-backup\` unchanged | pass | pass | pass | pass | pass | pass |
| 16:10 conf = `tools\conf\dgVoodoo.daily-16x10-2026-10-03.conf` (`299a6811`) except the two `Resolution` lines; TMU 8192, `CaptureMouse = true`, FPSLimit 0 | pass | pass | pass | pass | pass | n/a |
| wide conf = `tools\conf\dgVoodoo.daily-wide-2026-10-03.conf` (`ac0ecdeb`) except `Resolution`; `CaptureMouse = false`, `stretched`, TMU 8192, [Glide] = display shape at 2160 lines (5160x2160; B2 3688x2160); `dgVoodoo.conf` = wide conf | n/a | pass | pass | n/a | pass | n/a |
| stock: `dgVoodoo.windows.conf`, FPSLimit 19.2, TMU not 8192, no 16x10 / wide conf | n/a | n/a | n/a | n/a | n/a | pass (1) |
| PLAY*.bat set | i76, stock | i76, stock, 16x10, balanced | same | i76, stock | same as B | i76 only, no preset |
| `PLAY-i76.ps1` and `i76wheel.exe` = repo | pass | pass | pass | pass | pass | pass |
| `input.map` = `controls\input.map` (`b1f352ca`), GOG's map kept as `input.map.stock-*`; `_ahk\` = AHK 1.1.37.02 + the two layer scripts | pass | pass | pass | n/a | pass | pass |
| stock controls: GOG's map patched (marker), original as `input.map.pre-windows-setup`, no layer scripts in `_ahk\` | n/a | n/a | n/a | pass | n/a | n/a |
| `tools\lint-input-map.py <folder>` | OK | OK | OK | OK | OK | OK |
| GOG files changed only where intended (`i76.exe`, `i76shell.dll`, `STRLKUP.DLL`, `input.map`, `glide.dll`, `glide2x.dll`; `glide2x.ovl` moved) | pass | pass | pass | pass | pass | pass |
| `-DryRun` for each PLAY*.bat: exit 0, no REFUSED, no WARNING | pass (best-120: 15 vars; stock: 0) | pass (best-wide 28, balanced 28, 16x10 15, stock 0) | pass | pass | pass | pass |

(1) `-Preset stock` only: line 1 of the installed `dgVoodoo.conf`, a comment, has `???` where the repo file has an em dash
(`Get-Content` / `Set-Content -Encoding ascii` in Windows PowerShell 5.1). Every key is identical; dgVoodoo ignores `;` lines.
Cosmetic, not fixed.
(2) B2: `best-wide.psd1` and `best-wide-balanced.psd1` differ from the repo in `I76_ASPECT` / `I76_U32X_MENU_ASPECT` only
(`1726x1011`, as designed); B and D (3440x1440) are byte-equal.

**The `I76_TERRAIN_LOD` guard** (`8a3f3c8`) did not fire on any shipped preset: the dry runs show `I76_TERRAIN_LOD=8` only together with
`I76_FAR_CLIP` 1800 (best-wide) or 1200 (best-wide-balanced). Negative control with the installed launcher: a scratch preset with
`I76_TERRAIN_LOD=8` and no far clip was refused (exit 3); with `I76_FAR_CLIP=1200` and `I76_COLL_WINDOW=2` it passed with the
`I76_COLL_WINDOW` warning. `tests\test_presets.py`: 20 passed.

**Idempotence**: Setup-From-GOG.ps1 run again on A (twice, a minute apart): 422 files before and after, the only change is the
time stamp line of `i76e-controls.txt`.

## Against the daily driver (read-only file list of `Games\Interstate76-2026-10-03\Interstate 76`, vs B-wide)

Driver 448 files, B-wide 425. Expected differences:

- **Different GOG build**: the driver is the 2019 AiO build (`i76.exe.u32xorig` `60abf7bc`, `I76PATCH.DLL.disabled`, `goggame.dll`,
  `gfw_high.ico`), the fresh folder 2.1.0.17 (`9a232dcc`, `goggame-1207661003.*`, `GOGLauncher.exe`, `GameuxInstallHelper.dll`,
  `Lee.fot`, `webcache.zip`). Data that differs with the build: `ADDON\vehscn.vcf/.vsf`, `DLL\WINET.DLL`, `I76PLYR.DEF`, `OpenGLid.ini`,
  `internet.lst`.
- **Written by play**: `mciproxy.log`, `histogram.txt`, `user.mel`, `victory.rec`, `trip4.spc`, `reconfig.spc`, `NSCR.DAT`,
  `I76DFLT.DEF`, `i76car.def`, `multicar.def`, `NVCL\nvcl0.vcf`, three ADDON vehicles, `save003`-`007`; the bookmarks differ
  (the driver's own vs the repo's Mac run, see INSTALL.md step 10).
- **Backups of the driver's own history**: `*.driver-<md5>`, `input.map.bak-*`, `savegame.dir.*`; the installer's own:
  `input.map.stock-*`, `input.map.as-installed`, `i76e-controls.txt`, `_openglide-backup\`.
- **Documented as not installed** (INSTALL.md): cursor-overlay, head-tracking and camsweep AHK scripts, Lossless Scaling,
  `tools\i76-music.ps1`, `enable-force-feedback.bat` (not needed), `PLAY-i76-dgvoodoo.bat`, `WHAT-THIS-IS.txt`; dgVoodoo's
  `D3D8.dll` / `D3D9.dll` (= dgVoodoo 2.87.3; the game uses Glide and DirectDraw only).
- **Launcher layout**: the driver's launchers sit one level up (`PLAY.bat` etc., portable layout); the installer writes
  `PLAY-i76.bat` etc. inside the game folder.
- **Confs**: 16:10 and wide differ only in the `Resolution` digits of this 1726x1011 RDP display; on 3440x1440 the setup's formula
  gives `4608x2880` / `1680x1050`, i.e. the driver's files byte for byte (as `51cbf6b` found at the console). The driver's
  `dgVoodoo.conf` is `907a31a4`, the pre-promotion-15 wide conf its PLAY.bat copied in last (STATUS-2026-10-10).

Differences worth the owner's attention (not errors in the installer, but a fresh install is not the driver):

- **Controls ahead of the driver**: a fresh install gets the repo's `input.map` `b1f352ca` (adds `401743a`, right stick / arrows orbit
  the external camera) and `i76-remap.ahk` `3a0c9fc2` (driver `14367db9`; Y camera cycle `a7d61c0`). STATUS-2026-10-10 lists both as
  "not in any promotion": they have never been played.
- **Launcher ahead of the driver**: `PLAY-i76.ps1` `900a05ad` (repo) vs `c27f49f9` (driver, no preset guard, no `-HeadTrack`).
- **No shell keyboard patches**: the driver's `i76shell.dll` `a300db63` carries F7 + modal keys (promotions 6-7); the installer
  deploys only the u32x import rename. Offline, `tools\patch-shell-f7.py` applies cleanly to a copy of GOG 2.1.0.17's shell
  (`deb41008` -> `68be82f2`, 124 bytes, all at F7 sites), and `patch-shell-modals.py` on top of that gives `3f2fff4f` (454 bytes,
  all in planned ranges). Not deployed, not run. Now listed in INSTALL.md's "Not installed".

## Fixes made

- **`3f2b792` Setup-From-GOG: Nitro Pack into its own folder; -SkipNitro reaches install.ps1.** Found by reading, not by running:
  the Nitro installer was given `/DIR=<base game folder>`. The 2.1.0.17 Nitro installer carries a different `zglide.dll`
  (`f28fe42b`; base `05c1dde4`) and `win32.dll` (`2573c81c`; base `4b6b5b3d`), so it would have overwritten the base game's renderer
  module, and `install.ps1` only looks for `nitro.exe` in `<parent>\Interstate 76 Nitro Pack`, so the Nitro recipe never ran. It now
  installs there (skipped if `nitro.exe` is already present, unless `-Force`). `-SkipNitro` was not passed on to `install.ps1`, which
  then still configured a Nitro Pack it found in the registry or the usual folders. **The GOG installers were not run before or after
  this change.**
- INSTALL.md (this commit): step 10, the repo bookmarks the setup copies into a folder that has none (it did, undocumented); the
  shell patches in "Not installed"; a pointer here.

## Remaining gaps

1. **Boot** (owner test 16): `best-120` / `best-wide` have still never run on the `9a232dcc` exe; dgVoodoo's acceptance of a conf with
   computed `Resolution` digits; u32x `06467bd2` at run time on this exe; music via the proxy (`mciproxy.log`); a save.
2. **The GOG installer's silent run** (UAC, registry, `/DIR`), the desktop shortcut, the dgVoodoo / AutoHotkey downloads and their
   sha256 path: not exercised (offline by rule).
3. **Nitro Pack**: the fixed path is unrun; `setup-windows.ps1 -Exe nitro.exe` was not run here.
4. **Installing over Remote Desktop** sizes the 16:10 conf to the RDP desktop (here 1726x1011 -> `[Glide] 3234x2022`,
   `[DirectX] 1440x900`) and best-wide to it as well unless `I76_WIDE_DISPLAY` is set. Run the installer at the console, or re-run
   `setup-windows.ps1` there. `I76_WIDE_DISPLAY` does not reach the 16:10 conf step (test hook asymmetry, not fixed).
5. **The installed launcher cannot check the proxy build**: every installed dry run printed
   `note: music-fix\Strlkup.dll not found beside this script`. The comparison only happens when `PLAY-i76.ps1` runs from the repo
   (it did: `Strlkup.dll matches music-fix\Strlkup.dll (274944 B md5 C11F7F7D)` on all six folders).
6. Cosmetic: the em dash in the stock conf's first comment (above); Setup-From-GOG and install.ps1 each print their own
   `=== DONE ===` block, so the run ends with two.
7. The cutscene-music fix (`smack-music-fix\SMACKW32.DLL`) is not built in the repo, so no install gets it ("not built (optional)").
