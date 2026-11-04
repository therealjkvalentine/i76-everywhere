# GOG forum post: "for the purists" (draft, 2026-11-04)

For the Interstate series board on the GOG forum, once the 1.0 kit is published. Release plan s.7, 1.0 item 13; s.8
item 2. Nothing here is auto-posted: copy it, check the two bracketed lines, post from your own account. The old
"your GOG copy already contains the 20 fps limiter" lead ([OUTREACH-DRAFT.md](../records/OUTREACH-DRAFT.md)) is wrong
and is not in this text: GOG ships the Gold 1.2 exe and no `I76PATCH.DLL`.

**Before posting:** replace `<release link>`; settle the health-bar line (two versions below, one per the owner's
decision on `I76_FIX_HEALTH_PCT`); say "Windows and Mac" only if the Mac Kit is in the same release.

---

**Subject:** Interstate '76 on a modern PC, with the game left alone: music without a CD drive, widescreen, no save freeze; physics, AI and damage are GOG's

A free, open-source patch kit for the GOG copies of Interstate '76 and the Nitro Pack. It installs over your own
GOG folder (nothing of the game is in the download), keeps every original file, and can be undone. Before the list of
fixes, the part that matters to this board:

**What it does not change.** The physics, the AI and the damage are GOG's own, and we measured that rather than
assumed it. The 1997 CD version (retail 1.0) was run in an emulator on an emulated Pentium 166 next to the GOG exe
and the kit: turret aim and lead, bullet speed, the AI's dropper rule, the radar sweep, ram credit and the T05
canyon jump come out the same in all three. Where 1997 and GOG differ (the AI's attack-tactic chooser, turret slew
speed, the heat-seeker cone, the health readout, the difficulty damage factor), the kit keeps GOG's rule in every
case. The table of what each version does, with how each row was measured, is in the project:
`docs/engine/BUILD-RULES.md`. One detail from it that surprised us: a fresh GOG install starts on **Wimp**, where your
rounds hit twice as hard as in 1997; **Champion** is the 1997 damage. The kit does not touch that setting.

**What it fixes**

- **Music in missions with no CD drive.** The base game plays its soundtrack as CD audio; GOG ships the tracks as
  MP3s but the game cannot open a CD device that is not there. A small add-on DLL answers the game's CD questions
  from those MP3s. It is not a cracked file: it forwards to GOG's own `strlkup_orig.dll` and contains no game code.
- **The right music over the cutscenes** (the long-standing GOG bug, fixed with a proxy for the movie player that
  restores the 1997 CD-drive behaviour).
- **The save screen no longer freezes**, and the mouse lands where the pointer is in the menus at any resolution.
- **Widescreen** for your monitor (the 3D view; menus and cutscenes stay 4:3), a longer view distance, and the
  graphics drawn through dgVoodoo at up to 120 fps while the game's simulation keeps its own step: 24 steps a second,
  the step GOG's copy takes on Windows, fixed so that it no longer changes with the frame rate. A setting puts it at
  20 if that is the feel you know. Either way the canyon jump clears.
- **Windows 11 October 2026 update:** the Nitro Pack crashed at its first frame with the dgVoodoo version most
  guides link; the kit ships 2.87.5, which does not.
- **Your own controls are kept.** The setup leaves a customised `input.map` alone and offers the kit's beside it.
  Wheel and pad layers are optional, and force feedback on modern wheels is documented.
- [Choose one] **The enemy health readout is changed**: GOG's build shows a raw ratio over three core parts (the
  1998 build lost 1997's banding); the kit's formula is closer to 1997's but is neither, and it also delays AI
  retreat and damage smoke slightly against GOG. It can be switched off.
  / **The enemy health readout is GOG's**, quirks included; a switch (`I76_FIX_HEALTH_PCT`) changes it if you want.
- LAN play through IPXWrapper on the same kit for every machine; the co-op campaign over LAN is experimental.

**What it is not.** No HD textures, no upscaled sounds, no new content: anything like that is something a player makes
from their own files on their own machine, and the project never redistributes it. The changes to the game's own
files are small and listed (on Windows, one renamed import in the exe); the rest lives in the add-on DLLs, and every
patch is checked byte by byte against GOG's file before it is applied, so a different build gets a message, not a patch.

**Download and source:** `<release link>` (Windows 10 / 11; Mac Kit for Apple Silicon in the same release). Every
claim above has a dated measurement record in the repository, and the issue tracker is where to say what feels wrong.
If there is a 1997 rule you would want back as a switch (the old tactic chooser, the slower turrets, the banded health
readout), say which: those are planned as opt-in switches after 1.0, each behind an A/B test.

---

## Answer-in-advance lines (keep from the old draft, corrected)

- *Is this legal?* The kit has no game content; you bring your own GOG copy. The add-on DLLs are this project's own
  code (MIT); dgVoodoo and AutoHotkey are bundled unmodified under their own licences, which allow it.
- *Does it need AI / an account / the internet?* No. The optional extras (community maps) download from the sites
  that host them, with credits.
- *Widescreen?* The 3D view only; the engine's menus and movies are 4:3 and are shown pillarboxed.
- *Does 60 fps break the jump?* Not with the fixed step. The lore came from the stock game at 60 fps, where the
  physics step shrinks with the frame rate; the kit keeps the step at the GOG value whatever the frame rate.
- *Is the music fix a cracked DLL?* No. It forwards every call to GOG's own `strlkup_orig.dll` and adds the CD
  answers; the source is in the repository.
- *Does my GOG copy already have the 20 fps limiter?* No. GOG ships the Gold 1.2 exe with no `I76PATCH.DLL`; that
  limiter is part of the community AiO patch. If you installed that patch, the kit renames its DLL aside and paces the
  game itself.
