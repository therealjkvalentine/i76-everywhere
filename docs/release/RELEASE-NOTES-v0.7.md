# Interstate '76 Patch Kit (i76-everywhere) v0.7: release notes

**Download:** https://github.com/therealjkvalentine/i76-everywhere/releases/tag/v0.7.3
(`Interstate76-Patch-Kit-i76-everywhere-v0.7.3-f5d5ac0.zip`, 4.2 MB). It is marked a pre-release, so GitHub's
"latest release" link does not point at it: link the tag above.

> **v0.7.4 line (update when the installer lane lands):** *v0.7.4 adds an optional extras step that downloads the
> top-10 community maps from their original sites (checked against pinned hashes) and the optional helpers. Not
> released yet.* Delete this box or replace it with the v0.7.4 link.

## What this is

A patch kit for **your own GOG copy** of Interstate '76 (the "Arsenal" / Gold Windows version). You unzip it into the
game folder and run `PLAY.bat`. It contains **none of the game**: only our fixes (a proxy DLL beside the game's own,
a mouse DLL), launchers, presets, a key map, scripts, and two third-party helpers (dgVoodoo 2.87.5, unmodified, and
AutoHotkey 1.1). It keeps the original of every file it touches, and `UNINSTALL-i76e.bat` puts the folder back
byte for byte (all 371 files of a GOG install, tested).

The game itself still runs. This is not a remake or a reimplementation: the 1997 code drives the car, the AI and the
missions, which is why saves, the ADDON folder and stock multiplayer keep working.

## What changes, with numbers

Measured on the developer's PC (GTX 1080 Ti, 3440x1440) unless it says otherwise.

| | GOG as shipped | with the kit |
|---|---|---|
| **Frame rate** | 20 fps (GOG's limiter DLL) | **120 fps**, with the car still simulated **24 times a second**, the step the game had on a 1997 Pentium 166 (41.667 ms, measured on an emulated P166). The picture is drawn in between the steps, so the physics, jumps and AI behave as the game was tuned: the mission 5 canyon jump takes off at 50.0 m/s and peaks at 10.0 m, as in 1997 |
| **Picture shape** | 4:3 stretched | your monitor's shape (21:9, 16:9, 16:10, 4:3): a wider view, nothing stretched; 2x supersampling; menus 4:3 with bars |
| **Draw distance** | 600 m | **1.8 km** (`PLAY.bat`); **2.3 km** with the preview launcher, the last quarter fading out to transparent instead of a fog wall. (2.5 km crashed in testing; 2.3 km is the safe edge, 8 of 8 runs) |
| **Terrain** | hills pop and step as you approach | the preview launcher **morphs terrain in** (geomorphing) and uses **smooth shading**; roads, bushes, shadows and textures carried farther out |
| **Rear-view mirror** | GOG's default shows only cars on a plain sky colour | road and terrain to 300 m; 1 km with the main view's ground textures in the preview |
| **Menus** | the pointer misses with a modern mouse | the pointer lands where you click; the save screen takes typing; Enter / Space / Y / N answer the popups |
| **Controls** | 1997 arrow-key layout | a WASD-style layout (printable sheet included), gamepad layer, wheel axes. Plug controllers in before starting |
| **Windows 11** | the 2026-10 cumulative update (build 26100.9711) broke start-up: dgVoodoo 2.87.3 crashed, and about 60 % of boots died in `winmmbase.dll` | dgVoodoo **2.87.5** fixes the first; our proxy's heap fix the second (0 crashes in 40 boots after, 28 in 59 before). 2.87.3 is kept as a fallback folder |

Frame rate on the hardest stretch we know (the 2.6 km hill road in mission 5, preview settings): median 118 fps,
1 % low 76 fps. If yours drops under 60, `PLAY.bat --no-supersample`.

## In the repo, not in the kit yet (experimental)

These work on the developer's home network and desk. They are in the repository with their own guides, but the Patch
Kit does not install them yet, and none has been tried outside one household.

- **LAN multiplayer with AI drop-in (Gold):** IPX through IPXWrapper; computer cars fill the empty seats of any arena,
  respawn after 5 s, and give their seat to a player who joins. The session survives the host leaving (host migration).
- **Co-op campaign (Gold):** two players through the 17 story scenes as "Co-op Scene 1 .. 17" in the arena list, the host
  as the hero, the buddy in their own car, enemies scaled for two. [docs/COOP.md](../COOP.md)
- **Nitro Pack game types:** two new entries in Nitro's own GAME TYPE popup, **"Arena Drop-In + AI"** (computer cars in
  every empty seat; a leaving player's seat goes back to the AI) and **"Co-Op"** (Nitro's campaign missions together).
  Host migration in an AI arena passed 3 of 3 in the lab. [docs/NITRO-LAN-WEEKEND.md](../NITRO-LAN-WEEKEND.md)
- **Wheel force feedback:** the game's own effects on a modern wheel, with a fix (lab-tested) that keeps them on across Alt-Tab and
  Replay; an optional
  custom force model with a **tuning page in your browser** (`http://127.0.0.1:17691/`, live sliders per channel, the
  game in a window beside it). [tools/ffb/README.md](../../tools/ffb/README.md)
- **Head look** through opentrack (start opentrack first; `Ctrl+Alt+H` cycles analog / digital / off).
- **Mac (Apple Silicon, Wine):** the Glide renderer at about 100-120 fps, music, controls; one manual step (the Wine
  wrapper). [docs/MAC-BUILD.md](../MAC-BUILD.md). Steam Deck: [docs/STEAMDECK.md](../STEAMDECK.md).
- **Not tried yet:** a PC and a Mac in one game on the newest build; anything over the internet with these changes
  (play online on the stock game).

## What is experimental in the kit itself

- `PLAY-PREVIEW.bat` (the 2.3 km fade, terrain morphing, smooth shading, the 1 km mirror, a softer nose-dive on jumps) is
  the developer's current pick and is not finished. `PLAY.bat` is the tested set.
- Monitor shapes other than 3440x1440 were checked with the game set to 1920x1080 and 2560x1440, not on real 16:9
  monitors. Off-centre or stretched pictures are exactly the reports we want.
- The GOG Galaxy build of `i76.exe` uses GOG's own music player, and a pad or wheel can lag up to one simulation step
  (42 ms) behind a key on that build.

## Install

1. Find the game folder (GOG Galaxy: settings icon next to PLAY > *Manage installation* > *Show folder*; the folder with
   `i76.exe`).
2. Download the zip from the link above, right-click > *Properties* > tick *Unblock*, then *Extract All* **into** that
   folder, so `PLAY.bat` sits next to `i76.exe`.
3. Double-click `PLAY.bat`. The first run takes about ten seconds and lists every file it changes. **Esc** skips the intro.

No admin rights, registry changes or GOG Galaxy needed. The full guide is `README-PATCH-KIT.md` in the zip.

## Reporting a bug

Open an issue at https://github.com/therealjkvalentine/i76-everywhere/issues and attach **`mciproxy.log`** from the game
folder (it records what the fixes did, your display and pointer mapping, and any crash: a line starting `CRASH:` says
where). Add your monitor size, graphics card, which launcher you used, and a screenshot if you can (Win+PrtScn).

## Credits

- **Community maps** (the optional extras pick, all credited from their readmes): Rage County by General Rage; 76th
  Precinct by Stingray (with SuperFreak and team Mod Squad); Leathertown by Skull N. Bones; Biggsville by Lt. Stinger
  (template by Debacle); Drug Bust by Captain Gram; Gumball Rally by Stingray; Intercept and Pursuit and BorderTown, TX
  by Debacle; Offroad Terror by General Rage; Great Oval by DIVER. Preserved by **Local Ditch** and **Lightfoot's Stolen
  Maps** (interstate76.com).
- **dgVoodoo 2** by Dege; **IPXWrapper** by Daniel Collins (solemnwarning); **opentrack**; **AutoHotkey**; **DxWnd** by gho.
- **Prior art and reference:** **I26** by vahokif, the Godot reimplementation that got there first on bots and host
  migration; Local Ditch (weapon numbers: Greg Schwartz / Zaphod-AVA); DIVER's Asset Bible; UCyborg's AiO patch;
  Shane Peelar's ANet netcode work; CahootsMalone, That Tony, greg-kennedy's i76render, Open76, Roanish/i76.

## Licence and rights

- Interstate '76 and all its assets are (c) 1997 Activision (rights now with Microsoft). Nothing of the game is in the
  kit or the repository; you need your own GOG copy.
- This project's own code is MIT-licensed ([LICENSE](../../LICENSE)); third-party notes in
  [THIRD-PARTY.md](../../THIRD-PARTY.md).
- dgVoodoo 2.87.5 ships unmodified (hashes in `_i76e\MD5SUMS`, byte-identical to Dege's GitHub release); AutoHotkey 1.1 is
  GPL. Some antivirus tools flag dgVoodoo's DLLs; that is a known false positive.
- Community maps are their authors'. They are **not** in the kit; the optional extras step downloads them from the
  original sites, keeps each readme beside its map, and says the files were converted (13 bytes of the 1997 layout).
