# shared/: the payload every platform copies into a game folder

The files here are data, not programs: the frame-rate presets, the control map, the bookmark saves and the renderer
configurations. The installers in [`windows/`](../windows/README.md), [`mac/`](../mac/README.md) and
[`deck/`](../deck/) and the kit builders in [`tools/`](../tools/) read them from here. Nothing in this folder
runs on its own, and none of it is a game file.

| File | Copied by, to | Why |
|---|---|---|
| [`presets/*.psd1`](presets/) | `windows/setup-windows.ps1` -> `<game folder>\presets\`; the Patch Kit carries seven of them in `_i76e\repo\presets\` (`tools/package-patch-kit.ps1`); `tools/Make-Daily-Driver.ps1` and `windows/Make-Portable-Zip.ps1` copy all of them | The engine-switch sets `PLAY-i76.ps1 -Preset <name>` hands to the game (frame rate, physics step, draw distance, fixes). Each file's header says what it sets and how far it is proven |
| `presets/graphics-mac.psd1`, `graphics-mac-fast.psd1` | `tools/package-mac-kit.ps1` -> the Mac Kit's `payload\graphics\base.env` / `fast.env` | One source for the Mac graphics tiers: the Mac Kit converts them to `KEY=VALUE` files |
| [`controls/input.map`](controls/input.map) | `windows/setup-windows.ps1` -> `<game folder>\input.map` (`-Controls i76e`, the default); the Mac and Deck kit builders -> `payload\gold\input.map`; `deck/setup-deck-pad.sh` -> `input.map.profile-pad`; `tools/mp-pack.py` | This project's WASD-style control map, one map for every machine. Its md5 is in [`controls/README.md`](controls/README.md), [docs/CONTROLS.md](../docs/CONTROLS.md) and on the printed sheet; `tools/controls-sheet/build.ps1` checks the three agree |
| [`saves/save*.cmp`, `saves/savegame.dir`](saves/README.md) | `windows/setup-windows.ps1` -> the game folder, only when it has no saves yet (base game only); `mac/setup-saves.sh` -> every Mac wrapper; `saves/Install-Saves.ps1` / `install-saves.sh` by hand | Mission bookmarks, so a fresh install can jump to a scene. The sub-folders (`lab-20261002/`, `windows-20260906/`, `rescue-20260718/`) are save-editor test fixtures and are not installed |
| `renderer/dgVoodoo.daily-driver-2026-10-03.conf` | `windows/setup-windows.ps1` -> `<game folder>\dgVoodoo.conf` (base game, the fast presets); the Patch Kit carries it flat in `_i76e\repo\` | The dgVoodoo configuration the developer plays on, deployed byte for byte (only the resolution digits change for another display): dgVoodoo rejects a whole file over one bad line |
| `renderer/dgVoodoo.windows.conf` | `windows/setup-windows.ps1` -> `<game folder>\dgVoodoo.conf` (Nitro and the other presets); the Patch Kit carries it flat | The earlier Windows recipe (frame cap, 8x MSAA, borderless window) |
| `renderer/dgVoodoo.conf` | `mac/setup-voodoo.sh` -> the Mac game folder (Voodoo mode); `deck/deck-install.sh` downloads it from this path on GitHub; `deck/setup-steamdeck.sh` | The dgVoodoo configuration for Wine / Proton (DXVK) |
| `renderer/dxvk.conf` | `mac/setup-voodoo.sh` -> the Mac game folder | DXVK settings for the Mac Voodoo mode (asynchronous shader compiles) |
| `renderer/interstate-76.dxw` | `mac/setup-dxwnd.sh` -> DxWnd's `dxwnd.ini` in the Mac wrapper; `mac/setup-music.sh` reads it | The DxWnd profile of the shipping Mac build ([docs/DXWND-TUNING.md](../docs/DXWND-TUNING.md)) |

The widescreen confs that `tools/Make-Wide-Conf.ps1` writes from a template live beside that tool in
[`tools/conf/`](../tools/conf/): they are templates for a generator, not files an installer copies as they are.

## Rules

- **Installed kits keep their flat layout.** The Patch Kit and the installed game folders have `presets\`,
  `controls\` and `saves\` at the top of `_i76e\repo\` and the confs beside `setup-windows.ps1`; the Windows scripts
  look in `shared\` in a clone and in their own folder otherwise. A path written in a kit or a game folder is not a
  repo path.
- **Bytes matter.** `controls/input.map` and three presets are stored with no line-ending conversion and the
  daily-driver conf is pinned CRLF (`.gitattributes`), because installed copies are compared by md5.
- **After any change to `controls/input.map`** run `tools\controls-sheet\build.ps1` (it lints the map, checks it
  against the pad and stick layers, and rebuilds the printed sheet and the table in docs/CONTROLS.md).
- **Saves are user data.** Only the developer's own bookmarks are here; see [CONTRIBUTING.md](../CONTRIBUTING.md).
