# windows/: install and play on Windows

Everything the Windows install and launch path runs. Most players never open this folder: they unzip the **Patch Kit**
from the [releases page](https://github.com/therealjkvalentine/i76-everywhere/releases) into their GOG game folder and
double-click `PLAY.bat` ([its guide](../tools/patch-kit/README.md)). This folder is the source of that kit and of the
install from a clone of the repository.

## 1. Install

| Route | Who | How |
|---|---|---|
| Patch Kit | players | Unzip into the folder with `i76.exe`, double-click `PLAY.bat`; the first start runs the setup once ([tools/patch-kit/README.md](../tools/patch-kit/README.md)) |
| From a clone | developers, testers of a branch | Double-click `INSTALL.bat` at the repository root, or `./windows/Setup-From-GOG.ps1` (installs the game from your GOG installer, then sets it up); `./windows/install.ps1 -GameDir <folder>` sets up a game that is already installed. Switches and presets: [INSTALL.md](../INSTALL.md) |

Test a change on a copy of the game, never on the install you play on ([docs/process/PROCESS.md](../docs/process/PROCESS.md)).

## 2. What it changes in the game folder

Every original is kept beside the file it replaces. In order, as `setup-windows.ps1` does it:

- dgVoodoo's Glide and DirectDraw DLLs replace GOG's Glide DLL; `dgVoodoo.conf` is written from
  [`shared/renderer/`](../shared/README.md) (only the resolution digits change for your display).
- `Strlkup.dll` becomes our proxy (GOG's kept as `strlkup_orig.dll`); `u32x.dll` is added and the USER32 import of
  `i76.exe` and `i76shell.dll` points at it (originals `i76.exe.u32xorig`, `i76shell.dll.orig`).
- `I76PATCH.DLL` (GOG's 20 fps cap) is renamed `I76PATCH.DLL.disabled`.
- `input.map` becomes this project's control map (GOG's kept as `input.map.stock-<time>`; `-Controls stock` keeps
  GOG's keys, `-Controls own` keeps yours); the AutoHotkey layers go to `_ahk\`.
- The launcher `PLAY-i76.ps1`, `presets\*.psd1`, `PLAY-i76.bat` / `PLAY-stock.bat` and a desktop shortcut are added;
  the bookmark saves are copied in only when the folder has none.
- Patch Kit only: the menus' keyboard patches in `i76shell.dll` (kept as `i76shell.dll.pre-i76e-keys`), three
  *Graphic Detail* defaults in `I76PLYR.DEF` (kept as `I76PLYR.DEF.pre-i76e`), and `_i76e\setup.log`, which lists every
  file changed.

## 3. Undo

- Patch Kit: `UNINSTALL-i76e.bat` puts every GOG file back byte for byte and keeps your own files in `_i76e\backup\`
  ([details](../tools/patch-kit/README.md#uninstall)).
- From a clone: `u32x\deploy-u32x.ps1 -GameDir <folder> -Restore` undoes the mouse DLL; the other originals sit beside
  their files (`strlkup_orig.dll`, `I76PATCH.DLL.disabled`, `input.map.stock-*`). GOG Galaxy's *Verify / Repair* restores
  the whole folder.
- Controls only: `setup-windows.ps1 -GameDir <folder> -Controls stock -ControlsOnly`, or `CONTROLS.bat` in a kit folder.

## 4. Troubleshooting

| Symptom | Usual cause |
|---|---|
| Hangs on "PLEASE STAND BY", black screen | Remote Desktop: the 3D cannot start there. Use the PC itself |
| A 3dfx watermark, a 4:3 or tiny window | dgVoodoo rejected the folder's conf and used `%APPDATA%\dgVoodoo\dgVoodoo.conf`: delete that file, re-run the setup |
| Wheel or pad dead in game, fine in its control panel | The in-game control menu rewrote `input.map`: run `python tools/lint-input-map.py <game folder>`, restore the map |
| A crash | `mciproxy.log` in the game folder: a `CRASH:` line says where |
| Physics wrong, still 20 fps | `mciproxy.log` lists every switch as applied or skipped; `I76PATCH.DLL` must be `.disabled` |

More: [INSTALL.md](../INSTALL.md#troubleshooting), the kit's table
([tools/patch-kit/README.md](../tools/patch-kit/README.md#if-something-goes-wrong)) and
[docs/engine/VERIFIED-FIXES.md](../docs/engine/VERIFIED-FIXES.md).

## 5. Where the code behind each step lives

| Step | Code |
|---|---|
| The install chain: GOG installer, then setup | `Setup-From-GOG.ps1` -> `install.ps1` -> `setup-windows.ps1` (root `INSTALL.bat` calls the first) |
| The Patch Kit's first start, update, controls, extras | [`tools/patch-kit/`](../tools/patch-kit/README.md) (`i76e-prepare.ps1` calls `setup-windows.ps1`); built by `tools/package-patch-kit.ps1` |
| The launcher and its settings | `PLAY-i76.ps1` (copied into the game folder), `LAUNCHER.ps1` (the small settings window) |
| What the game loads | the proxy [`music-fix/`](../music-fix/README.md), the mouse DLL [`u32x/`](../u32x/README.md), the payload [`shared/`](../shared/README.md); all fixes: [src/README.md](../src/README.md) |
| Widescreen confs | `tools/Make-Wide-Conf.ps1` and its templates in `tools/conf/` |
| Controller layers | `i76-remap.ahk` (pad), `i76-ch-fighterstick.ahk` (stick), `i76-opentrack-*.ahk` / `.ps1` (head look), `i76-with-remap.bat` (Proton or a bare folder); the other `i76-*.ahk` are diagnostics |
| Optional extras | `Setup-FrameGen.ps1` (Lossless Scaling), `enable-force-feedback.bat` |
| Moving an install to another PC | `Make-Portable-Zip.ps1`, `MAKE-PORTABLE.bat` |

These scripts find the rest of the repository (`tools/`, `u32x/`, `music-fix/`, `shared/`) one folder up. The Patch Kit
carries the same files flat in `_i76e\repo\` (with `presets\`, `controls\`, `saves\` at its top); the scripts handle
both layouts.
