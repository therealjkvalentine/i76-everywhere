# i76-everywhere

**Interstate '76 (1997), fixed for modern PCs, Macs and the Steam Deck.** A free patch kit for your own GOG copy.
The original game still runs underneath: we fix and extend it around the 1997 code, so saves, add-on maps and multiplayer
keep working. No game files are in this repo, and everything the kit changes can be undone.

**[⬇ Download the Patch Kit v0.8.1 for Windows](https://github.com/therealjkvalentine/i76-everywhere/releases/latest)** ·
[Mac](#mac-and-steam-deck) · [Steam Deck](#mac-and-steam-deck) · [Report a problem](https://github.com/therealjkvalentine/i76-everywhere/issues/new/choose)

## See the difference

**1997 vs today.** The same opening, side by side: 20 fps and a 600 m horizon on the left; 120 fps and 2.3 km on the right.

https://github.com/user-attachments/assets/eaf65800-1389-4585-ac79-79e2dc9b60cc

**The physics are untouched.** The car is still simulated 24 times a second like on a 1997 Pentium, so jumps land where
they always did. Only the drawing in between is smoother.

https://github.com/user-attachments/assets/01ae6e21-621e-45e6-be50-ffe1d439f791

**See the whole desert.** Hills blend in as you approach, so they don't pop, and the far edge fades into the sky.

https://github.com/user-attachments/assets/42019368-8b5b-4a6e-bf25-291014fed874

**Look around and behind you.** Head tracking with a webcam (opentrack), and a rear-view mirror that draws the road and the hills.

https://github.com/user-attachments/assets/f0131a8d-c623-4877-af92-1e2a23dcda25

**Feel the road.** Force feedback for modern wheels, with a live tuning page in your browser.

https://github.com/user-attachments/assets/adcb8b46-3d7a-4385-9d5d-36a5fdf64612

<sub>1997 footage: [Local Ditch Gaming](https://www.youtube.com/@LocalDitchGaming), used with permission.</sub>

## What changes

- **Smooth:** 120 fps instead of 20, with the game's timing kept as designed.
- **Far:** you can see 1.8 to 2.3 km instead of 600 m, and the terrain no longer pops.
- **Wide:** your screen's real shape (16:9, 21:9). You see more of the world instead of a stretched picture.
- **Fixed:** Windows 11 start-up crashes, menus that miss your mouse clicks, and music that stops in missions.
- **Controls:** keyboard, gamepad, wheel and flight stick layouts. Your own bindings are kept if you already have some.

Experimental, in the repo but not yet in the kit: LAN play with computer cars filling the empty seats, a two-player co-op
campaign, and new Nitro Pack game types. The full list is in [docs/ENHANCEMENTS.md](docs/engine/ENHANCEMENTS.md).

## Install (Windows, 3 steps)

You need **[Interstate '76 Arsenal from GOG](https://www.gog.com/en/game/interstate76)**. It is not on Steam.

1. Open your GOG game folder (Galaxy: ⚙ next to PLAY > *Manage installation* > *Show folder*).
2. Download the kit zip, right-click it > *Properties* > tick *Unblock*, then *Extract All* into that folder.
3. Double-click **`PLAY.bat`**.

`SETTINGS.bat` changes the resolution, field of view, draw distance and the rest. `UPDATE.bat` gets new versions.
`UNINSTALL-i76e.bat` undoes everything. The full guide: [tools/patch-kit/README.md](tools/patch-kit/README.md).

## Mac and Steam Deck

- **Mac (Apple Silicon):** about 100 to 120 fps through Wine. It is a beta and needs one manual step. Start at [docs/MAC-BUILD.md](docs/guides/MAC-BUILD.md).
- **Steam Deck:** the [Deck Kit pre-release](https://github.com/therealjkvalentine/i76-everywhere/releases/tag/deck-v0.1.0)
  has the controller layout and rumble, but it has not been community tested yet. See [deck/kit/README.md](deck/kit/README.md).

## Something wrong?

Open an [issue](https://github.com/therealjkvalentine/i76-everywhere/issues/new/choose) and attach `mciproxy.log`,
`play-i76.log` and `i76-settings.txt` from the game folder. Common problems and their fixes are in
[docs/VERIFIED-FIXES.md](docs/engine/VERIFIED-FIXES.md).

## More

| | |
|---|---|
| Controls and a printable key sheet | [docs/CONTROLS.md](docs/guides/CONTROLS.md) · [PDF](docs/guides/Interstate76-Controls-Quick-Reference.pdf) |
| Save editor (runs in your browser) | [open it](https://therealjkvalentine.github.io/i76-everywhere/i76-save-editor.html) |
| Multiplayer and co-op | [docs/MULTIPLAYER.md](docs/guides/MULTIPLAYER.md) · [docs/COOP.md](docs/guides/COOP.md) |
| What's planned | [ROADMAP.md](ROADMAP.md) · [project board](https://github.com/therealjkvalentine/i76-everywhere/projects) |
| How it works: reverse engineering, file formats, measurements | [docs/README.md](docs/README.md) · [re/](re/README.md) · [docs/records/](docs/records/) |
| The long version of this page | [docs/README-DETAILS.md](docs/guides/README-DETAILS.md) |

## Get involved

- **Play it and tell me** what breaks, in an [issue](https://github.com/therealjkvalentine/i76-everywhere/issues).
- **Build it with me.** Wanted: HD art, more platforms and controllers, new missions and code review. Issues and pull requests are open.
- **Buy my family a dinner.** Every computer in the house ran tests overnight for this:
  [buymeacoffee.com/therealjkvalentine](https://buymeacoffee.com/therealjkvalentine).

## Credits

UCyborg's AiO patch, dgVoodoo (Dege), DxWnd (gho), IPXWrapper, opentrack, AutoHotkey, Local Ditch Gaming (footage and weapon
measurements), the Open76, Roanish/i76 and vahokif I26 projects, and That Tony's format work.
Interstate '76 © 1997 Activision. This is a fan project and is not affiliated with Activision.
