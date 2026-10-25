# Interstate '76 on a Mac: the I'76 Mac Kit (i76-everywhere)

This kit builds two Mac apps, **Interstate 76 Gold.app** and **Interstate 76 Nitro.app**, on your own Mac from your own GOG copy of
the game. They are the same apps the developer's family plays on (same Wine, same DxWnd window, same OpenGLide-HD 3D, same fixes,
same LAN setup). The kit contains nothing of the game: it downloads the free Mac parts from where they are published, checks each
download against a fixed fingerprint (SHA-256), and patches your copy of the game inside the new apps. Nothing is installed anywhere
else on your Mac, and it needs no administrator password, no Xcode and no Homebrew.

Tester build. Tested on one MacBook Pro (Apple M5 Pro, macOS 26) on 2026-10-25. Tell us how it went on yours.

## What you need

- A Mac with **Apple silicon** (M1 or later) and **macOS 14.6 or later**. Intel Macs: the kit has a launcher for them, but nobody has
  tried one yet.
- **Rosetta 2** (Wine runs as an Intel program). If you have never installed it, the kit tells you. To install it, open Terminal and run
  `softwareupdate --install-rosetta --agree-to-license`.
- About **6 GB free** while it builds. The two apps take about 3 GB in the end. The downloads (about 270 MB) are fetched once and kept in
  `~/Library/Caches/i76-mac-kit`.
- **Interstate '76 from GOG** ("Interstate '76 Arsenal", which includes the Nitro Pack). GOG sells it **for Windows only**, so you need
  the Windows files, in one of two ways:
  1. **The Windows offline installers** (no PC needed). On gog.com, go to *Account* > *Games* > *Interstate '76*. Choose **Windows** as
     the system and download the *offline backup game installers*: `setup_interstate76_2.1.0.17.exe` (395 MB, the game) and
     `setup_interstate76_nitro_pack_2.1.0.17.exe` (238 MB, Nitro). The kit opens them itself: it runs GOG's installer silently inside
     its own Wine (a minute or two each), or uses `innoextract` if you have it (`brew install innoextract`; not needed). The GOG
     Galaxy app for Mac cannot install this game (it is a Windows game).
  2. **The game folder from a Windows PC.** Copy the folder that holds `i76.exe` (Galaxy: *Manage installation* > *Show folder*), and
     for Nitro the folder that holds `nitro.exe`, to the Mac, for example on a USB stick. Use a **clean** GOG copy: a folder that already
     has our Windows Patch Kit in it is refused. You can turn it back into a clean copy on the PC with `UNINSTALL-i76e.bat`, or with
     Galaxy's *Verify / Repair*.

  The kit knows GOG's current files (version 2.1.0.17, which Galaxy also installs). It checks them before it changes anything, and stops
  with a message if your copy is something else (for example GOG's older 2019 build).

## Build the apps (5 to 15 minutes)

1. Unzip `Interstate76-Mac-Kit-....zip` (double-click it in Downloads). You get a folder called `Interstate76-Mac-Kit`.
2. **Double-click `BUILD-I76-APPS.command`**. The first time, macOS says it cannot check the file's developer. Right-click it, choose
   *Open*, then *Open* again. A Terminal window opens and asks where your GOG files are: the installer (.exe) or the game folder, first
   for the game, then for Nitro (*Skip* if you only want one of them).
3. Wait until it says **Finished**. The apps are in **Applications > Sikarugir** in your home folder (Finder: *Go* > *Home* >
   *Applications* > *Sikarugir*). Drag them to the Dock if you like.

The same thing from Terminal (in the kit folder):

    ./i76-mac-kit.sh build --gold ~/Downloads/setup_interstate76_2.1.0.17.exe --nitro ~/Downloads/setup_interstate76_nitro_pack_2.1.0.17.exe

`--gold` / `--nitro` also take a folder or a .zip of the folder. `--dest <folder>` builds somewhere else, and `--replace` moves an
existing app of the same name to the Trash first. **Your bookmarks (saves) live inside the app**, so copy them out before you replace
it (see *Your saves* below).

## The first start: what macOS asks, once

| when | what macOS asks | what to answer |
|---|---|---|
| the first start of each app | *"wine" (or "Interstate 76 Gold") would like to access the microphone* | Either answer works: Wine's sound driver opens the input devices when the game starts its sound. Do answer it, though: the game waits behind the question. |
| the first time you HOST or JOIN a network game | *Allow "Interstate 76 Nitro" to find and connect to devices on your local network?* | **Allow**. Without it the game list still shows games, but JOIN GAME does nothing. If you said Don't Allow: *System Settings* > *Privacy & Security* > *Local Network*, switch the app on, and start the game again. |
| the same, only if the macOS firewall is on | *Do you want the application "wineserver" to accept incoming network connections?* | **Allow** |

You are asked again only if you build the app in another place or under another name. A rebuild with `--replace` in the same place keeps
the Local Network answer, because the launcher keeps its identity (a fixed Mach-O UUID).

**Starting up.** The game shows *PLEASE STAND BY* for up to a minute, then the intro. **Esc** skips the intro. In Nitro, do not press Esc
at the main menu, because that quits the game. To quit, use the game's own EXIT, close the window, or press Cmd-Q.

**The start-up crash workaround is already set.** Under Wine the game sometimes crashed while it drew its first 3D menu. The kit sets
Wine to draw the menus without 3D (`Direct3D` `renderer` = `gdi` for `i76.exe` and `nitro.exe`; the missions are still OpenGL). With
it, 0 of 34 test starts crashed, against 4 of 23 without it. About 1 start in 10 can still stop before the menu, mostly in Nitro. If that
happens, press Cmd-Q and open the game again.

## Controls

Gold uses this project's **WASD-style layout**: W / S to drive, A / D to steer, Enter or the left mouse button to fire, Tab for the next
weapon, F1 / F3 / F6 for the views. Mouse buttons 4 / 5 and the wheel work too, through a small AutoHotkey layer inside the app. Connect a
gamepad **before** you start the game (the 1997 engine only looks for controllers at startup). Nitro keeps GOG's original Nitro keys.
Never change keys in the game's Control Configuration menu (it corrupts the key file).

## Graphics on your Mac

Macs differ a lot here. The kit picks a **graphics tier** from your chip, and you can change it at any time (with the game closed):

    ./i76-mac-kit.sh graphics ~/Applications/Sikarugir/"Interstate 76 Gold.app" fast

| tier | what it sets | measured |
|---|---|---|
| `base` (default on M1 / M2 / M3 / M4 / M5 without Pro, Max or Ultra) | smoother terrain shading and terrain that morphs in instead of popping, detail x2; stock draw distances | M2 (8 GB): about 52 fps standing in mission 5. Nothing reached 57 on that Mac, so leave the distances stock |
| `fast` (default on Pro / Max / Ultra chips) | detail x8 (sharper textures and shadows further out), roads drawn to 1800 m | M5 Pro: 60 fps median; M4 Max: 75 fps median |
| `stock` | none of our graphics keys | |
| a file of your own | `KEY=VALUE` lines (the keys are in `payload/graphics/*.env`) | |

Long view distances (`I76_FAR_CLIP`, `I76_CLUTTER_DIST` above stock) and `I76_TERRAIN_LOD` above 4 cost far more on a Mac than on a PC.
The developer's Windows set (1.8 km of everything) ran at 17-27 fps on these Macs. The 3D is rendered at the size of the game window,
which the launcher fits to your **main display** every time the game starts. There is no separate render-size setting on the Mac yet. Full
numbers: `docs/records/MAC-GRAPHICS-TUNE-2026-10-24.md` in the project.

## Playing on a LAN with others

- Everyone has to be on the same home network (not a guest network, no VPN), and Macs have to be awake and unlocked.
- **Everyone needs the same build of our add-on.** This kit carries Gold proxy `STRLKUP.DLL` 5d6f9828 and Nitro proxy `Strlkup.dll` 3f27c797, the builds the
  family's PCs and Macs play with. It also builds the co-op scenes and scenario arenas byte for byte the same as theirs (the game checks
  those files by CRC). To check your own copy, open Terminal and run
  `md5 ~/Applications/Sikarugir/"Interstate 76 Gold.app"/Contents/SharedSupport/prefix/drive_c/"GOG Games/Interstate 76/STRLKUP.DLL"`.
  If another player's build differs, use the same kit version.
- Multiplayer runs over IPX through IPXWrapper (UDP 54792), which is already set up inside the apps. Gold: MELEE > MULTI MELEE > HOST or
  JOIN. Nitro: MULTIPLAYER > JOIN > IPX.

## Your saves

Gold's bookmarks are inside the app, in
`Interstate 76 Gold.app/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76/` (`savegame.dir` and `save*.cmp`). In Finder,
right-click the app and choose *Show Package Contents* to get there. Copy them out before you delete or replace the app, and copy them back
afterwards, with the game closed.

## If something goes wrong

| what you see | what to do |
|---|---|
| *"BUILD-I76-APPS.command" cannot be opened* | Right-click it, then *Open*, then *Open*. |
| *Rosetta 2 is not installed* | Run `softwareupdate --install-rosetta --agree-to-license` in Terminal, then build again. |
| *... is not GOG's Interstate '76 (2.1.0.17 ...)* | The copy is not GOG's current one. Download the current Windows offline installer from your GOG library and give that instead. |
| *... already carries i76-everywhere files* | That folder has our Windows Patch Kit in it. Use the installer, or a clean folder. |
| *the GOG installer did not write a game folder* | Install innoextract (`brew install innoextract`) and build again, or copy the folder from a PC. |
| a download fails, or its SHA-256 does not match | Check your internet connection and build again. A file that does not match its fingerprint is never used. |
| the game window does not appear, or the start sits on a black window | Press Cmd-Q and open the game again (see *Starting up*). If that keeps happening, send us `mciproxy.log` from the game folder (path under *Your saves*). |
| the start sits for about 40 s | On some Macs a USB sound interface as the default output slows Wine's sound start. Switch the output to the built-in speakers and try again. |
| JOIN GAME does nothing | Local Network permission (see *The first start*). |

To check that the kit's files in an app are still the ones it put there, run `./i76-mac-kit.sh verify ~/Applications/Sikarugir/"Interstate 76 Gold.app"`.

## Removing it

Drag the two apps to the Trash. You can also delete `~/Library/Caches/i76-mac-kit` (the downloads). Nothing else was written.

## What is inside, and the licences

- Ours (MIT, source in the project): the launch stubs (`stubs/`, Swift), the game add-on `Strlkup.dll` (the fixes), `u32x.dll` (menu
  mouse), the byte patches (`payload/patches`, which carry only our changes and are checked against your GOG file before and after), the
  cutscene-music and rumble add-ons, the key map, the Wine settings.
- **OpenGLide-HD** (`payload/openglide`): OpenGLide (LGPL 2.1) with this project's patches (`tools/openglide-hd` in the project).
- **AutoHotkey 1.1** (GPL v2, `payload/ahk`, with its licence).
- Downloaded on your Mac, not in the zip (the addresses and fingerprints are in `pins.txt`):
  - **Sikarugir** wrapper template 1.0.11 and Wine 10.0 engine (Wine is LGPL 2.1; Sikarugir-App on GitHub). The kit removes the parts I'76
    does not use from the template, including Apple's D3DMetal, whose licence is restrictive.
  - **DxWnd** 2.06.14 (GPL v3, SourceForge).
  - **IPXWrapper** 0.7.2 (GPL v2, GitHub).
- The game: © 1997 Activision. It comes from your own GOG copy and stays on your Mac.

## For maintainers

The recipe and its test are in `docs/records/MAC-KIT-2026-10-25.md`. The pieces are these:

- `tools/mac-kit/make-patches.py` (PC): builds the patches from pristine GOG folders with the repo's own patchers.
- `tools/mac-kit/build-stubs.sh` (Mac with the Xcode tools): builds the launchers with their fixed UUIDs.
- `tools/package-mac-kit.ps1` (PC): packs the zip, with a guard that refuses any file byte-identical to a GOG file.
- `tools/mac-kit/kit-test.sh` (Mac): boots a built app headless, silent, to the menu or into a mission, and reads the add-on's log.
