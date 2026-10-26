# mac/: install and play on an Apple Silicon Mac

The game is a Windows game; on a Mac it runs inside a self-contained Wine app. There are two routes. Players use the
**Mac Kit**; this folder holds the older scripted route and the launch stubs it builds.

## 1. Install

| Route | Who | How |
|---|---|---|
| Mac Kit | players | Unzip the kit, double-click `BUILD-I76-APPS.command`, point it at your GOG installer or game folder. It builds `Interstate 76 Gold.app` and `Interstate 76 Nitro.app` ([tools/mac-kit/README.md](../tools/mac-kit/README.md); built by `tools/package-mac-kit.ps1`) |
| Scripted wrapper (BETA) | developers | Make a Sikarugir Wine wrapper with the GOG game inside ([docs/guides/MAC-BUILD.md](../docs/guides/MAC-BUILD.md), "The working recipe"), then double-click `mac-install.command` at the repository root (it hands over to `mac/mac-install.command`) |

## 2. What it changes

Nothing outside the app. Mac Kit: the apps go to `~/Applications/Sikarugir`, the downloads (pinned by SHA-256) are
cached in `~/Library/Caches/i76-mac-kit`, and your GOG copy is patched inside the app (every GOG file replaced is
kept). Scripted route, inside the wrapper's game folder: the Wine registry keys the game needs (virtual desktop, the
window-float key), DxWnd and its profile ([`shared/renderer/interstate-76.dxw`](../shared/README.md)), the virtual CD
music, the cutscene-music proxy, an `input.map` (the previous one kept as `input.map.pre-install`) and the launcher apps.

## 3. Undo

Mac Kit: drag the apps to the Trash and delete `~/Library/Caches/i76-mac-kit`. Copy your bookmarks out first: they live
inside the app (`.../Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76/`). Scripted route: delete the
wrapper, or restore `input.map.pre-install`; `setup-saves.sh` keeps a `*.pre-sync` copy of each save it replaces.

## 4. Troubleshooting

| Symptom | Usual cause |
|---|---|
| The game page-faults at boot, or the window vanishes when it loses focus | A missing Wine registry key: re-run `mac-install.command` |
| Arrow keys do nothing | Wine delivers the Mac arrows as the other PC arrow cluster: `fix-arrows-for-mac.sh` |
| JOIN GAME does nothing | macOS Local Network permission for the app (Mac Kit README, "The first start") |
| Music under cutscenes, or no music in missions | `setup-cutscene-music-fix.sh`, `setup-music.sh`; [docs/guides/MUSIC.md](../docs/guides/MUSIC.md) |
| Physics wrong (cars flip, jumps fail) | The frame cap: [docs/guides/MAC-BUILD.md](../docs/guides/MAC-BUILD.md), "THE ONE RULE" |

More: the Mac Kit's table ([tools/mac-kit/README.md](../tools/mac-kit/README.md#if-something-goes-wrong)) and
[docs/engine/VERIFIED-FIXES.md](../docs/engine/VERIFIED-FIXES.md). Settled dead ends on the Mac (Glide to Metal, wheel
force feedback through DirectInput) are listed in [the docs hub](../docs/README.md).

## 5. Where the code behind each step lives

| Step | Code |
|---|---|
| The Mac Kit (build, verify, the pinned downloads, the patches) | [`tools/mac-kit/`](../tools/mac-kit/README.md), `tools/package-mac-kit.ps1` |
| The scripted install | `mac-install.command`, which runs `setup-dxwnd.sh`, `setup-music.sh`, `setup-cutscene-music-fix.sh`, `fix-arrows-for-mac.sh` and `build-launchers.sh` |
| Optional steps | `setup-mouse-and-pad.sh`, `setup-input-remapper.sh` (AutoHotkey sources from `../windows/`), `setup-nitro.sh`, `setup-saves.sh`, `setup-voodoo.sh` / `setup-mac-glide.sh` / `setup-dgvoodoo-cpl.sh` (the parked Voodoo mode), `slim-wrapper.sh` |
| Launch stubs | `i76-*-stub.swift`, compiled by `build-launchers.sh`; `play.sh` |
| Double-click helpers | `open-*.command` (settings panels, the pad diagram), `i76-trainer.command` |
| The renderer confs, map and saves | [`shared/`](../shared/README.md) |
| What the game loads | [src/README.md](../src/README.md) (the proxy, the cutscene-music proxy, the rumble shim, OpenGLide-HD) |

The scripts find the rest of the repository (`shared/`, `docs/`, `tools/`, `smack-music-fix/`, `music-fix/`) one folder
up.
