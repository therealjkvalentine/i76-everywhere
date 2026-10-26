# Interstate '76 Everywhere: the docs hub

Start from what you came to do. Each section below is a handful of links; each folder it points at has a README that is
the next index. Nothing here needs the game; the game is never in this repository.

## Play: I have the game and want it to run well

- [The front page](../README.md): what the project does, the download, the three-step install.
- [INSTALL.md](../INSTALL.md): the install from a clone, its switches and presets, moving an install to another PC.
- Your platform: [Windows](../windows/README.md), [Mac](../mac/README.md), [Steam Deck](../deck/README.md).
- [Controls](guides/CONTROLS.md) and the [printable key sheet](guides/Interstate76-Controls-Quick-Reference.pdf);
  pads, wheels and sticks in [guides/](#every-living-doc-by-folder).
- [Multiplayer](guides/MULTIPLAYER.md), [co-op](guides/COOP.md), [a game night](guides/GAME-NIGHT.md).
- [The long front page](guides/README-DETAILS.md): every feature in more detail.

## Install: package it for a platform, or see what the kit changes

- [shared/](../shared/README.md): the payload every platform copies (presets, control map, saves, renderer confs), file
  by file: which installer copies it where, and why.
- The kits: [Windows Patch Kit](../tools/patch-kit/README.md), [Mac Kit](../tools/mac-kit/README.md),
  [Deck Kit](../deck/kit/README.md). Their builders are `tools/package-*-kit.ps1` ([tools/](../tools/README.md)).
- What each platform's install changes in the game folder and how to undo it: the [Windows](../windows/README.md),
  [Mac](../mac/README.md) and [Deck](../deck/README.md) READMEs, sections 2 and 3.
- The platform recipes: [Windows playbook](guides/WINDOWS-PLAYBOOK.md), [Mac build](guides/MAC-BUILD.md),
  [Steam Deck](guides/STEAMDECK.md).

## Fix: change or extend something

- [src/README.md](../src/README.md): the fix catalogue (component > what it fixes > switch > record).
- [engine/ENHANCEMENTS.md](engine/ENHANCEMENTS.md): every enhancement, how to turn it on, how far it is proven.
- [engine/VERIFIED-FIXES.md](engine/VERIFIED-FIXES.md): every symptom, its cause and its fix.
- [process/PROCESS.md](process/PROCESS.md): issues are the task layer, the QA queue for what needs a person at a
  machine, and a dated record with measurements for every non-trivial change.
- [CONTRIBUTING.md](../CONTRIBUTING.md) (people) and [AGENTS.md](../AGENTS.md) (coding agents): how to work on this repo.
- [tools/](../tools/README.md) and `pytest tests` for the offline checks.

## Engine: how the game works, and its file formats

- [engine/](#every-living-doc-by-folder): handling, draw distance, force feedback, levels, saves, weapons and parts,
  the memory map, all measured on the live game.
- [re/](../re/README.md): the reverse-engineering map of the exe (architecture, subsystem specs, file formats and
  parsers in [re/data/FORMATS.md](../re/data/FORMATS.md)).
- [lab/docs/ENGINE-REFERENCE.md](../lab/docs/ENGINE-REFERENCE.md): the engine as a whole, with per-claim confidence;
  [lab/](../lab/README.md) is the public snapshot of the frame-rate lab and its test harness.
- [research/COMMUNITY-RESOURCES.md](research/COMMUNITY-RESOURCES.md): what the community published, by problem; check
  it before reverse-engineering anything.
- [research/RE-METHODOLOGY.md](research/RE-METHODOLOGY.md) and [engine/FIND-WHAT-WRITES.md](engine/FIND-WHAT-WRITES.md):
  how values were found, and the traps that gave wrong answers.

## History: what has been tried, before you re-chase it

- [records/README.md](records/README.md): every lane record, by topic, newest first.
- [research/](#every-living-doc-by-folder): feasibility studies, spikes, prior art and the parked dead ends.
- [status/](status/): dated plans, backlogs and snapshots. History, read-only.
- [release/](release/): release notes, announcements and the launch plan; [CHANGELOG.md](../CHANGELOG.md),
  [ROADMAP.md](../ROADMAP.md).

## Settled: do not re-chase

Each of these was measured and closed. Re-open one only with new evidence, and link it.

- **Glide to Metal ("Voodoo") on the Mac**: it works, but recompiles shaders on every launch; the warm-up is a
  platform floor. [research/VOODOO-PARKED.md](research/VOODOO-PARKED.md),
  [engine/VISUAL-QUALITY-MAC.md](engine/VISUAL-QUALITY-MAC.md).
- **dgVoodoo under Wine's DXGI on the Mac**: superseded by the above.
  [research/DXGI-DGVOODOO-RESEARCH.md](research/DXGI-DGVOODOO-RESEARCH.md).
- **Mac wheel force feedback through DirectInput**: a dead end; rumble comes from the game's own force data instead
  ([ffb-shim](../ffb-shim/README.md)). The Mac software renderer's 1024x768 ceiling is in the same doc.
  [engine/FORCE-FEEDBACK-AND-VISUALS.md](engine/FORCE-FEEDBACK-AND-VISUALS.md).
- **An HD texture pack**: formats cracked, pack built, shipped and retired (small gain, night missions broke).
  [research/HD-TEXTURES-RESEARCH.md](research/HD-TEXTURES-RESEARCH.md).
- **"This dgVoodoo knob does nothing" (`FPSLimit`, `CaptureMouse`, forced refresh)**: those results are void: dgVoodoo
  had rejected the conf and loaded a global one. Prove a conf is loaded before trusting any conf finding.
  [records/GRAPHICS-ENHANCEMENT.md](records/GRAPHICS-ENHANCEMENT.md) (last section),
  [records/FPS-120.md](records/FPS-120.md) (top note).
- **Above 120 fps**: 120 is the ceiling of every renderer tested.
  [records/RENDERER-ALTERNATIVES.md](records/RENDERER-ALTERNATIVES.md) section 11.
- **A cached (incremental) terrain quadtree**: not on this engine; the per-frame work it would save is small and it
  breaks the mirror pass, the vertex pool and binoculars.
  [records/TERRAIN-PASS-OPT-PLAN-2026-10-25.md](records/TERRAIN-PASS-OPT-PLAN-2026-10-25.md) section 3.
- **A Direct3D or VR port of the original**: none exists; the reimplementations are listed.
  [records/MODERN-PORTS-AND-VR.md](records/MODERN-PORTS-AND-VR.md).
- **Editing `KEYBOARD.MAP` or rebinding in the game's control menu**: the engine reads only `input.map`, and the menu
  corrupts it. [AGENTS.md](../AGENTS.md), [engine/VERIFIED-FIXES.md](engine/VERIFIED-FIXES.md).

## Conventions

- **Records are dated and measured**: n, the control run, the spread. They are not rewritten; later facts are added as
  dated notes at the top. A path written inside a record is the path on the day it was written (the repository was
  reorganised on 2026-10-03 and on 2026-10-26).
- **Living docs are undated and current** (guides/, engine/, research/, process/). If one disagrees with a record, the
  living doc should win; if it does not, fix it.
- **status/ is history.** Its plans and backlogs were current on their date; issues track what is open now.

## Every living doc by folder

- **guides/** (how-to): [CONTROLS](guides/CONTROLS.md), [GAMEPAD-PC-MAC](guides/GAMEPAD-PC-MAC.md),
  [WHEEL-T300](guides/WHEEL-T300.md), [FIGHTERSTICK](guides/FIGHTERSTICK.md), [HEAD-TRACKING](guides/HEAD-TRACKING.md),
  [INPUT-REMAPPER](guides/INPUT-REMAPPER.md), [DECK-CONTROLS](guides/DECK-CONTROLS.md),
  [STEAMDECK](guides/STEAMDECK.md), [STEAMDECK-INPUT-MODES](guides/STEAMDECK-INPUT-MODES.md),
  [MAC-BUILD](guides/MAC-BUILD.md), [DXWND-TUNING](guides/DXWND-TUNING.md), [WINDOWS-PLAYBOOK](guides/WINDOWS-PLAYBOOK.md),
  [MULTIPLAYER](guides/MULTIPLAYER.md), [COOP](guides/COOP.md), [GAME-NIGHT](guides/GAME-NIGHT.md),
  [MUSIC](guides/MUSIC.md), [SOUND-HD-PACK](guides/SOUND-HD-PACK.md), [MISSION-LAUNCH](guides/MISSION-LAUNCH.md),
  [MODDING-GUIDE](guides/MODDING-GUIDE.md), [README-DETAILS](guides/README-DETAILS.md); the key sheet
  ([PDF](guides/Interstate76-Controls-Quick-Reference.pdf)), the pad diagrams and the Deck layout page.
- **engine/** (how it works): [ENHANCEMENTS](engine/ENHANCEMENTS.md), [VERIFIED-FIXES](engine/VERIFIED-FIXES.md),
  [HANDLING-MODEL](engine/HANDLING-MODEL.md), [DRAW-DISTANCE](engine/DRAW-DISTANCE.md),
  [CONTROL-DOCTRINE](engine/CONTROL-DOCTRINE.md), [FFB-STACKS](engine/FFB-STACKS.md),
  [FFB-DESIGN-LIBRARY](engine/FFB-DESIGN-LIBRARY.md), [HAPTICS-ARCHITECTURE](engine/HAPTICS-ARCHITECTURE.md),
  [MOTION-OUTPUT](engine/MOTION-OUTPUT.md), [FORCE-FEEDBACK-AND-VISUALS](engine/FORCE-FEEDBACK-AND-VISUALS.md),
  [VISUAL-QUALITY-MAC](engine/VISUAL-QUALITY-MAC.md), [MUSIC-TRACK-MAP](engine/MUSIC-TRACK-MAP.md),
  [LEVEL-FORMAT](engine/LEVEL-FORMAT.md), [SAVE-FORMAT-GAPS](engine/SAVE-FORMAT-GAPS.md),
  [SAVE-FREEZE-ROOT-CAUSE](engine/SAVE-FREEZE-ROOT-CAUSE.md), [EDITOR-FIELD-TESTS](engine/EDITOR-FIELD-TESTS.md),
  [WEAPON-STATS](engine/WEAPON-STATS.md), [PARTS-REFERENCE](engine/PARTS-REFERENCE.md),
  [I76-GAMEPLAY-REFERENCE](engine/I76-GAMEPLAY-REFERENCE.md), [MEMORY-MAP-INDEX](engine/MEMORY-MAP-INDEX.md),
  [FIND-WHAT-WRITES](engine/FIND-WHAT-WRITES.md), [ASSET-BIBLE](engine/ASSET-BIBLE.md) (per-category pages in
  [asset-bible/](asset-bible/INDEX.md)).
- **research/** (feasibility, prior art, dead ends): [COMMUNITY-RESOURCES](research/COMMUNITY-RESOURCES.md),
  [COMMUNITY-SITEMAP](research/COMMUNITY-SITEMAP.md), [RE-METHODOLOGY](research/RE-METHODOLOGY.md),
  [RE-FIELD-GUIDE](research/RE-FIELD-GUIDE.md), [RE-RESOURCES](research/RE-RESOURCES.md),
  [PRIOR-ART-I26](research/PRIOR-ART-I26-2026-10-21.md), [INSTALLER-LESSONS-OPENRA](research/INSTALLER-LESSONS-OPENRA.md),
  [COOP-SPIKE](research/COOP-SPIKE.md), [INTERNET-PLAY-SPIKE](research/INTERNET-PLAY-SPIKE-2026-10-25.md),
  [PLAYER-COUNT-SPIKE](research/PLAYER-COUNT-SPIKE-2026-10-25.md), [OPENTRACK-COST](research/OPENTRACK-COST-2026-10-25.md),
  [CONTENT-FEASIBILITY](research/CONTENT-FEASIBILITY-2026-10-25.md) (and [content-2026-10-24/](research/content-2026-10-24/)),
  [COCKPIT-HIRES-FEASIBILITY](research/COCKPIT-HIRES-FEASIBILITY.md), the parked [VOODOO-PARKED](research/VOODOO-PARKED.md),
  [DXGI-DGVOODOO-RESEARCH](research/DXGI-DGVOODOO-RESEARCH.md) and [HD-TEXTURES-RESEARCH](research/HD-TEXTURES-RESEARCH.md).
- **process/** (how the project runs): [PROCESS](process/PROCESS.md), [RELEASE-PLAN](process/RELEASE-PLAN.md),
  [PARALLEL-SESSIONS](process/PARALLEL-SESSIONS.md), [OWNER-TEST-LIST](process/OWNER-TEST-LIST.md),
  [NITRO-LAN-WEEKEND](process/NITRO-LAN-WEEKEND.md), [AGENTS-GAME-FOLDER](process/AGENTS-GAME-FOLDER.md),
  [SCOPE-AND-LEGITIMACY](process/SCOPE-AND-LEGITIMACY.md) (which absorbed [LEGITIMACY-AND-SCOPE](process/LEGITIMACY-AND-SCOPE.md)).

Also in this folder: `input.map.reference` (the map the Mac scripted installer copies) and `media/`. The developer's
lab doctrine, which applies only on machines that have the lab's folders, is in [AGENTS.md](../AGENTS.md) below its
contributor section.
