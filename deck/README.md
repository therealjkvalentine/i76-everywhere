# deck/: install and play on the Steam Deck

On the Deck the Windows game runs under Proton with dgVoodoo on Vulkan, launched from Steam's Game Mode. Players use
the **Deck Kit**; the rest of this folder is the developer's own deployment scripts and earlier routes, kept for
reference.

## 1. Install

| Route | Who | How |
|---|---|---|
| Deck Kit | players | In Desktop Mode: `bash i76-deck-kit.sh install --gog ~/Downloads/setup_interstate76_2.1.0.17.exe`, then `bash i76-deck-kit.sh steam` for the library entry ([kit/README.md](kit/README.md); zip built by `tools/package-deck-kit.ps1`) |
| Push from a PC | developers | `deck-push.sh` and the `deck-push-*.sh` scripts copy a build to a Deck over ssh and run the matching `setup-deck-*.sh` there |
| `deck-install.sh`, `Install-I76.desktop`, `setup-steamdeck.sh` | nobody | Superseded by the Deck Kit on 2026-10-25 (unpinned downloads, no proxy); kept for reference, do not hand them to users |

The full recipe, the TV profile and the open items: [docs/guides/STEAMDECK.md](../docs/guides/STEAMDECK.md).

## 2. What it changes

Everything goes into one folder (default `~/Games/Interstate76`) plus a download cache (`~/.cache/i76-deck-kit`):
`game/` is your GOG game, patched in place, with every GOG file the kit replaced kept in `game/_gog-originals/`;
beside it are the launcher `i76-deck-launch.sh`, the preset `i76-env.sh`, your overrides `i76-env.local.sh`, the
AutoHotkey pad layer and `KIT-FILES.md5`. The `steam` step adds a non-Steam library entry, its artwork and the
controller template `controller_neptune_i76_pad.vdf`. Nothing else on the Deck is touched.

## 3. Undo

Delete the library entry in Steam and the install folder; your GOG installer is untouched. Reinstall over it with
`install --replace` (the old folder is moved aside, not deleted). `bash i76-deck-kit.sh verify` re-checks every file the
kit placed.

## 4. Troubleshooting

| Symptom | Usual cause |
|---|---|
| Does not start, or crashes at once | Compatibility tool: GE-Proton 10-12 is the tested one; dgVoodoo 2.81 and newer crash under Proton (the kit pins 2.78.2) |
| No rumble, or the pad does nothing in game | Steam Input must stay on with the "Interstate 76 gamepad" template ([kit/README.md](kit/README.md#controls-the-gamepad-layout)) |
| Picture wrong on a TV | Set the entry's Game Resolution to the TV's size; the launcher's display profile (`I76_DECK_DISPLAY`) |
| Anything else | `deck-launch.log` and `game/mciproxy.log` in the install folder: every switch, the display, the proxy's lines |

## 5. Where the code behind each step lives

| Step | Code |
|---|---|
| The Deck Kit: install, Steam entry, verify | [`kit/`](kit/README.md): `i76-deck-kit.sh`, `i76-env.sh` (the preset), `pins.txt`, `dgVoodoo.conf` (the Deck's 2.78.2 conf), `tools/` |
| The launcher (switches, display profile, pad layer, rumble) | `i76-deck-launch.sh`, `i76-deck-launch-mp.sh` (network games) |
| Steam: library entry, artwork, launch options, controller layouts | `add-to-steam.py`, `add-pad-shortcut.py`, `set-launch-options.py`, `make-art.py` and `artwork/`, `controller_neptune_i76*.vdf`, `build-controller-config*.py`, `remap-controller.py`, `use-pad-layout.py` |
| The developer's Deck setups | `setup-deck-baseline.sh`, `setup-deck-pad.sh`, `setup-deck-tv.sh`, `setup-deck-wide.sh`, `setup-deck-stock-textures.sh`, each pushed by its `deck-push-*.sh`; `first-launch-fix.sh`, `install-on-deck.sh` |
| Proxy builds for the Deck | `Strlkup.deck.dll`, `Strlkup.deck-padmenu.dll` (built from [`music-fix/`](../music-fix/README.md)) |
| Diagnostics | `probe/` |
| What the game loads | [src/README.md](../src/README.md) (the proxy, the rumble shim); the map and confs in [`shared/`](../shared/README.md) |
