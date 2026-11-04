# Interstate '76 Patch Kit (i76-everywhere) v1.1.0 (draft, 2026-11-04; not published)

The release text for the GitHub release page, in the shape of [RELEASE-NOTES-v0.8.0.md](RELEASE-NOTES-v0.8.0.md).
Lines in **[brackets]** are open: two owner decisions and the facts only known at tag time. The tag is `v1.1.0` (owner, 2026-11-04). The pre-release gates are
[RELEASE-PLAN.md](../process/RELEASE-PLAN.md) section 7.

**Download:** https://github.com/therealjkvalentine/i76-everywhere/releases/tag/v1.1.0
(`Interstate76-Patch-Kit-i76-everywhere-v1.1.0-<sha>.zip` for Windows 10 / 11; `Interstate76-Mac-Kit-i76-everywhere-v1.1.0-<sha>.zip`
for Apple Silicon Macs **[if the Mac Kit ships in the same release]**). Nothing of the game is in either zip: they install
over your own GOG copy and keep every original file.

> **Why 1.1.0 and not 1.0:** the repository's `v1.0.0` tag is the July 2026 "Vacation Build" (before the kit
> existed), so the kit's first full release is `v1.1.0` (owner's call, 2026-11-04). The kit's own line before it:
> v0.7.3, v0.8.0, v0.8.1, v0.8.2 (October 2026); RELEASE-PLAN s.6 has the version rule.

## What 1.1 means

The kit's fixes are GOG's game with the things that broke on a modern PC put right, and the simulation left alone. Since
0.8.2 that claim is measured rather than assumed: the 1997 retail CD build was run in an emulator on an emulated Pentium
166 beside the GOG exe and the kit, and the physics, turret aim, bullet speed, the AI's dropper rule and the radar come out
the same. Where 1997 and GOG differ, the kit keeps GOG's rule in every case; the per-version table is
[docs/engine/BUILD-RULES.md](../engine/BUILD-RULES.md).

## New since v0.8.2

- **dgVoodoo 2.87.5 in every Windows download** (the clone install, the LAN pack and the kit): 2.87.3's DirectDraw crashes
  at the first frame on the Windows 11 October 2026 update.
- **The setup names the exe it finds.** A 1997 CD exe or a Nitro exe under the Gold name gets a plain sentence instead of a
  warning; GOG's build is recognised as Gold 1.2 (GOG ships no `I76PATCH.DLL`; that 20 fps limiter is the community AiO
  patch's, and the kit renames it aside where a player installed it).
- **Mac Kit: the rumble table is built on your Mac from your own sound files**; the zip no longer carries anything made
  from the game's data.
- **Your own `input.map` is kept** through setup, re-setup, update and uninstall (0.8.1), with the wheel / stick layers off
  it; **[confirm the hardware rows from issue #99 / #103 or say "not yet run on a wheel"]**.
- **[Owner decision, release plan s.7 1.1 item 2]** either: "the enemy health readout: the kit's formula (closer to 1997's
  banding than GOG's raw ratio, but neither) stays on in the default presets; it also delays AI retreat and damage smoke
  slightly against GOG; `I76_FIX_HEALTH_PCT=0` in `i76-settings.txt` turns it off" / or: "the default presets now show
  GOG's enemy health readout, quirks included; `I76_FIX_HEALTH_PCT=1` changes it".
- Docs: what each original version does differently and how that was measured; the difficulty note (a fresh GOG install
  starts on Wimp, where your rounds hit twice as hard as in 1997; Champion is the 1997 damage; the kit does not change it).
- **[Fill from `git log v0.8.2..<tag>` at tag time: anything player-facing landed after 2026-11-04.]**

## What is not in the download, and never will be

No textures, sounds, levels, movies or executables of the game, upscaled or otherwise: the kit installs over your own GOG
copy. Anything made from the game's data (an HD texture pack, an upscaled sound set, the rumble table) is something a player
makes from their own files on their own machine; the project does not redistribute it. What the zips do contain beyond the
project's own code: unmodified dgVoodoo 2.87.5 components (Dege's readme permits shipping them with a game mod, quoted in
`_i76e\dgVoodoo\README-dgVoodoo.txt`; 2.87.3 beside it as a fallback) and AutoHotkey 1.1 (GPL v2, with its licence).
**[Owner ruling, release plan s.7 1.1 item 11:** the Windows kit's bookmark saves (`shared/saves`: the developer's own
bookmark files, installed only into a folder with no saves) and the Mac / Deck kits' BSDIFF patches (our bytes only, including
the co-op missions derived from GOG's) stay or go.**]**

## Known issues

- **Co-op campaign host crash in T05** after the AI fill spawns a second car (issue #127): a game crash in the draw loop, seen
  once on a Mac host. Co-op over LAN is experimental in 1.1; a single-player game is not affected.
- The menus and movies stay 4:3 (pillarboxed) in widescreen; only the 3D view is wide.
- **[Any QA row still open at tag time: issues labelled `needs-qa`.]**

## Report problems

Found something wrong, or something that looks odd? Please open an issue on GitHub:
**https://github.com/therealjkvalentine/i76-everywhere/issues** - say which game (Gold or Nitro Pack), which launcher, your
monitor size and graphics card, and attach `mciproxy.log` (in the game folder) and, if the setup failed, `_i76e\setup.log`.
Screenshots help a lot.

The kit's full instructions are `README-PATCH-KIT.md` inside the zip (also below on the release page).
