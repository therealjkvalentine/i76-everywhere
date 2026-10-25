# Interstate '76 Patch Kit (i76-everywhere) v0.8.0

**Download:** https://github.com/therealjkvalentine/i76-everywhere/releases/tag/v0.8.0
(`Interstate76-Patch-Kit-i76-everywhere-v0.8.0-<sha>.zip` for Windows 10 / 11; `Interstate76-Mac-Kit-i76-everywhere-v0.8.0-<sha>.zip`
for Macs). Nothing of the game is in either zip: they install over your own GOG copy and keep every original file.

## New since v0.7.3

- **The Nitro Pack is covered by the same zip.** Unzip it into your GOG *Interstate '76 Nitro Pack* folder (the one with
  `nitro.exe`) and double-click `PLAY-Nitro.bat`: the same 41.667 ms simulation at up to 120 fps, widescreen for your monitor,
  1.2 km view, dgVoodoo 2.87.5, and Enter / Y / N / Esc in the menu popups. No compiler, no download. Gold only, Nitro only or
  both: each folder gets its own copy of the kit, and a launcher started in the wrong folder says so and changes nothing.
- **Optional extras** (`INSTALL-EXTRAS.bat`): ten community maps (five for Gold, five for Nitro) downloaded from the sites that
  host them and checked, opentrack head look, Python for the debug dashboard, German voices from your own German disc, your own
  extra music. Each extra says what it is for; one that does not apply to the game in that folder is skipped with a note.
- **A short first-run window**: what was installed, your monitor and field of view, how to start and how to undo, then
  "Press any key". The full list of changed files goes to `_i76e\setup.log`.
- **Fixes**: Alt-Tab during a Nitro mission no longer crashes the game; the 1997 CPU-speed probe at start-up is logged as one
  `pit-probe: handled probe (not a crash)` line instead of four `CRASH` lines; dgVoodoo 2.87.5 (needed on the latest Windows 11).

## Report problems

Found something wrong, or something that looks odd? Please open an issue on GitHub:
**https://github.com/therealjkvalentine/i76-everywhere/issues** - say which game (Gold or Nitro Pack), which launcher, your
monitor size and graphics card, and attach `mciproxy.log` (in the game folder) and, if the setup failed, `_i76e\setup.log`.
Screenshots help a lot.

The kit's full instructions are `README-PATCH-KIT.md` inside the zip (also below on the release page).
