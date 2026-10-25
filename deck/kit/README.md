# Interstate '76 on the Steam Deck: the Deck Kit (i76-everywhere)

This kit builds Interstate '76 Gold for the Steam Deck from **your own GOG copy** of the game. Nothing of the game is in the kit:
it unpacks the GOG installer you downloaded, patches your files in place (keeping every GOG original), and adds this project's
fixes: steady 60 fps with stock-speed physics, widescreen for the Deck screen and TVs, longer draw distance and more detail,
in-game menus you can drive with the sticks, LAN play with the family PCs and Macs, and rumble from the game's own force-feedback
signal (shots, hits, landings, wheel slip, engine).

Tester build. Tested on one Steam Deck (LCD, SteamOS, GE-Proton 10-12) on 2026-10-25. Tell us how it went on yours.

## What you need

- A Steam Deck (SteamOS 3), about 1.5 GB free, a network connection for the first install.
- **Interstate '76 from GOG** (gog.com). From your GOG library download the **offline backup installer**
  `setup_interstate76_2.1.0.17.exe` (the "Interstate '76" one, not the Nitro Pack). The kit only supports that build (it checks).
  A GOG Galaxy install folder of the same version works too.

## Install (Desktop Mode, about 5 minutes)

1. Switch to Desktop Mode (Steam button > Power > Switch to Desktop).
2. Put the GOG installer in `~/Downloads` and unzip this kit there (Dolphin: right-click the zip > Extract > Extract here).
3. Open **Konsole** in the kit folder (Dolphin: right-click in the folder > Open Terminal Here) and run:

       bash i76-deck-kit.sh install --gog ~/Downloads/setup_interstate76_2.1.0.17.exe

   It downloads three helpers, each checked against a fixed fingerprint (`pins.txt`): innoextract (unpacks the GOG installer),
   dgVoodoo 2.78.2 (the Glide graphics wrapper) and IPXWrapper (LAN games). The game goes to `~/Games/Interstate76`
   (`--dest <folder>` puts it elsewhere). If GE-Proton 10-12 is not installed yet, add `--ge-proton` and the kit installs it.
4. Add it to Steam: `bash i76-deck-kit.sh steam` (asks before closing Steam, adds the library entry with its artwork, launch
   options and controller layout, and starts Steam again). Or do it by hand, see the next section.
5. Back to Game Mode. **Interstate 76** is in your library under Non-Steam. The first start builds its Proton prefix (about a minute).

### The library entry by hand (if you prefer, or if `steam` could not)

Steam (Desktop Mode) > Games > Add a Non-Steam Game > Browse > `~/Games/Interstate76/game/i76.exe` > Add. Then the entry's
Properties:

| setting | value |
|---|---|
| Launch options | `"/home/deck/Games/Interstate76/i76-deck-launch.sh" %command% -glide` (your folder, if you used `--dest`) |
| Compatibility | Force the use of a specific Steam Play compatibility tool: **GE-Proton10-12** (Proton Experimental also starts it; GE-Proton is what was tested) |
| Controller | Controller settings > Browse Configs > Templates > **Interstate 76 gamepad** (`controller_neptune_i76_pad.vdf`, copied to Steam's templates by `steam`; by hand: copy it from the install folder to `~/.steam/steam/controller_base/templates/`) |
| Game Resolution (docked) | Default is fine; set it to the TV's 16:9 size (e.g. 1280x720) for a full-width picture on a TV |

Do **not** turn Steam Input off for this game. The gamepad layout keeps Steam Input on and gives the game a plain Xbox-style pad:
that is what the pad layer reads and what carries rumble back to the Deck.

## Controls (the gamepad layout)

The same layout as the Windows and Mac pad layer (the shared `controls/input.map` and `i76-remap.ahk`): the left stick
steers, the triggers drive, LB is the shift layer for hardpoints, gears, horn and binoculars. In the menus the left stick moves the
pointer, A clicks, B goes back, Start is Enter. The full table is the project's `docs/CONTROLS.md` and the printable sheet
`docs/Interstate76-Controls-Quick-Reference.pdf` (both generated from the map itself).

An Xbox controller paired to the Deck works the same way (Steam Input gives it the same layout when it is the active controller).

## Rumble

`i7_sfrce.dll` in the game folder is this project's force-feedback shim: the game hands it its force-feedback state every tick and
it turns that into rumble on **every connected pad** (the Deck's own controls and a paired Xbox controller): a buzz per weapon
round, a thump on hits, collisions and landings, grit when the tyres slip, a low growl with the engine. To rumble only the first
pad, put `export I76_FFB_PADS=first` in `i76-env.local.sh`. The shim logs what it sends to the prefix's `C:\AutoHotkey\`
(`ffb-events.txt`: one line per shot, hit and landing; `ffb-drive.log`: motor levels twice a second). GOG's original
`i7_sfrce.dll` (DirectInput force feedback for a wheel) is kept in `game/_gog-originals`; copy it back to use an FFB wheel instead.

## Your own settings: i76-env.local.sh

`~/Games/Interstate76/i76-env.sh` is the kit's preset (the owner's Deck set: 60 fps, the 24 Hz physics step, detail x8, far
clip and roads 1800 m, terrain morph and smooth shading, the rear-mirror detail, sparse bushes, TV / handheld picture profiles).
Do not edit it: a kit update rewrites it. Put your changes in **`i76-env.local.sh`** beside it (created by the installer with
examples); it is read after the preset, so each `export` there wins. `deck-launch.log` lists every switch that applied.

## LAN games

The preset carries the LAN switches, so the normal library entry plays LAN: MULTI MELEE > HOST or JOIN goes straight to the IPX
screens (IPXWrapper). The Deck needs no firewall step. Keep the Deck awake during a game (Game Mode suspends after a few idle
minutes: touch it now and then, or raise the suspend timeout). The project's `docs/MULTIPLAYER.md` explains hosting, co-op
scenes and the AI arenas. `i76-deck-launch-mp.sh` is kept for older setups whose preset has no LAN switches.

## Files, logs, undo

| path (in the install folder) | what |
|---|---|
| `game/` | your game, patched; `game/_gog-originals/` holds every GOG file the kit replaced |
| `i76-deck-launch.sh` | the launcher (switches, display profile, pad layer, rumble line) |
| `i76-env.sh` / `i76-env.local.sh` | the preset / your overrides |
| `deck-launch.log`, `game/mciproxy.log` | the last launch: switches, display, proxy lines |
| `KIT-FILES.md5` | every file the kit placed; `bash i76-deck-kit.sh verify` re-checks them |

To undo: delete the library entry in Steam and the install folder; your GOG installer is untouched. To reinstall over it:
`bash i76-deck-kit.sh install --gog <installer> --replace` (the old folder is moved aside, not deleted).

## What is in the kit, and from where

- Ours (this project, GPL v2 where it applies): the proxy `STRLKUP.DLL` (`music-fix/`), `u32x.dll`, the rumble shim
  `i7_sfrce.dll` (`ffb-shim/`), the byte patches (`payload/patches`, which carry only our changes and are checked against your
  GOG file before and after; built by `tools/mac-kit/make-patches.py`), the launchers, the preset, the key map, the Steam layout,
  `bspatch.py` (applies the patches with Python only).
- **AutoHotkey 1.1.37.02** (GPL v2, `payload/ahk`, with its licence): the pad layer, run inside the game's Proton prefix.
- Downloaded on your Deck, not in the zip (addresses and fingerprints in `pins.txt`): **innoextract 1.9** (zlib), **dgVoodoo
  2.78.2** (Dege; Proton needs 2.80 or older, 2.81+ crashes under Wine's DXGI), **IPXWrapper 0.7.2** (GPL v2), optionally
  **GE-Proton 10-12**.

Project: <https://github.com/therealjkvalentine/i76-everywhere> (docs/STEAMDECK.md, docs/records/DECK-2026-10-25.md).
