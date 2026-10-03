# Interstate '76 docs: the index

Every file in `docs/`, grouped by topic, one line each. Rewritten 2026-10-03 (the earlier version of this page
was a Mac-era doc map from 2026-07-11 that covered about half of the folder).

**Where the files are (since 2026-10-03).** Living and parked docs are in `docs/`. The 48 dated records are in
[`docs/records/`](records/). Two records stay in `docs/` because they are still being added to:
DOC-CORRECTIONS-PENDING-SIBLINGS.md and REPO-ORGANIZATION-PROPOSAL.md. Records are not rewritten, so **a path
written inside a record dated before 2026-10-03 is the path before the move**: `docs/FPS-120.md` in a record means
`docs/records/FPS-120.md` today, and a root file such as `swap-renderer.ps1` may now be in `lab-residue/`. The move
table is in [REPO-ORGANIZATION-PROPOSAL.md](REPO-ORGANIZATION-PROPOSAL.md). Links were updated; plain-text paths
inside records were not.

**How to read the tag in front of each entry**

- **living**: kept current. If it disagrees with a record, the living doc should win, and if it does not, fix it.
- **record (date)**: a dated account of a session, a survey, a test run or a research pass. It is not rewritten;
  later facts are added as dated "superseded" notes. Read the notes at its top before acting on it. Lives in
  `records/`.
- **parked**: a settled dead end, kept so nobody re-chases it.

**Start here**

| You want | Read |
|---|---|
| What this repo adds, and how far each thing is proven | [ENHANCEMENTS.md](ENHANCEMENTS.md) |
| Every fix as symptom, cause, fix | [VERIFIED-FIXES.md](VERIFIED-FIXES.md) |
| What is open | [BACKLOG-2026-10-02.md](records/BACKLOG-2026-10-02.md) (read the superseded-rows note at its top) |
| What happened last | [STATUS-2026-10-02.md](records/STATUS-2026-10-02.md) (its last section is 2026-10-03) |
| Rules for working on this repo | [`../AGENTS.md`](../AGENTS.md) |

## Current state (2026-10-03)

- **Windows.** The daily driver is `C:\Users\james\Games\Interstate76-2026-10-03`, built on 2026-10-03 by
  `tools\Make-Daily-Driver.ps1` with preset `best-120` (120 fps, fixed physics step, render interpolation, bug
  fixes, 1800 m draw distance), a golden copy beside it, and the previous driver in Downloads kept as the rollback
  ([NEW-DAILY-DRIVER-RECIPE.md](records/NEW-DAILY-DRIVER-RECIPE.md)). 120 fps is measured and owner-played, and is the
  ceiling of every renderer tested ([RENDERER-ALTERNATIVES.md](records/RENDERER-ALTERNATIVES.md) section 11).
- **A finding that voids older results.** dgVoodoo 2.87.3 had been rejecting the lab sandbox's `dgVoodoo.conf`
  and using a 2020 global `%APPDATA%` file, so every earlier "this dgVoodoo knob does nothing" result (`FPSLimit`,
  `CaptureMouse`, `FreeMouse`, forced refresh, the 1920x1440 pointer box) is void
  ([GRAPHICS-ENHANCEMENT.md](records/GRAPHICS-ENHANCEMENT.md) last section). The owner's daily-driver conf was accepted.
- **Mac.** The shipping build is the software renderer through DxWnd in a self-contained Wine wrapper: instant
  start, 4:3 window, in-mission music, clean quit, 20 fps ([MAC-BUILD.md](MAC-BUILD.md)). The Glide to Metal
  "Voodoo" mode is parked ([VOODOO-PARKED.md](VOODOO-PARKED.md)).
- **Steam Deck.** Installed and working through Heroic, Proton and dgVoodoo on Vulkan ([STEAMDECK.md](STEAMDECK.md)).
  The proxy's 60 / 120 fps switches are untested under Proton and under Wine.
- **Multiplayer** is untested with any timing switch. Two copies run on one PC with `I76_MULTI_INSTANCE=1`; a
  session between them was not achieved (both need UDP port 21157; the internet transport wants a game server).

## 1. Status, plans and session records

| | Doc | What it is |
|---|---|---|
| living | [ENHANCEMENTS.md](ENHANCEMENTS.md) | The one catalogue of every enhancement, how to turn it on, and its evidence |
| living | [VERIFIED-FIXES.md](VERIFIED-FIXES.md) | Every symptom, root cause and fix that shipped, in one table (Mac-first, with Windows rows) |
| living | [RELEASE-PLAN.md](RELEASE-PLAN.md) | Community release plan; section 1 is the component state table (written 2026-10-01, corrected in place) |
| record 2026-10-02 | [BACKLOG-2026-10-02.md](records/BACKLOG-2026-10-02.md) | Every open problem and unknown in one prioritised table (P1 to P4) |
| record 2026-10-02 | [STATUS-2026-10-02.md](records/STATUS-2026-10-02.md) | What the autonomous session built and how each item was verified; 2026-10-03 daily-driver section |
| record 2026-10-02 | [PLAYTEST-2026-10-02.md](records/PLAYTEST-2026-10-02.md) | The owner's first console run of the whole switch set, verdict by verdict |
| record 2026-10-02 | [NEW-DAILY-DRIVER-RECIPE.md](records/NEW-DAILY-DRIVER-RECIPE.md) | Inventory of the old daily driver by md5 and the recipe for the new one; outcome box at the top |
| record 2026-10-02 | [DOC-CORRECTIONS-PENDING-SIBLINGS.md](DOC-CORRECTIONS-PENDING-SIBLINGS.md) | Corrections owed to the sibling repos (applied ones, the 2026-10-03 rejected-conf set, and the paths that moved on 2026-10-03). Stays in `docs/` |
| record 2026-08-16 | [READY-TO-TEST.md](records/READY-TO-TEST.md) | A hands-on test sheet for the old daily driver; a snapshot, corrected at the top |
| record 2026-10-03 | [REPO-ORGANIZATION-PROPOSAL.md](REPO-ORGANIZATION-PROPOSAL.md) | Proposed tidier repo layout with every path reference per move; its last section says which stages are done (lab residue, records) and which are deferred. Stays in `docs/` |
| living | [PARALLEL-SESSIONS.md](PARALLEL-SESSIONS.md) | Coordination protocol for several Claude sessions on one working tree |
| record 2026-07-19 | [OUTREACH-DRAFT.md](records/OUTREACH-DRAFT.md) | Unposted announcement drafts for v1.0 |

## 2. Frame rate and simulation (60 / 120 fps)

Switch-by-switch evidence lives in [`../music-fix/README.md`](../music-fix/README.md); presets in [`../presets/`](../presets/).

| | Doc | What it is |
|---|---|---|
| record 2026-10-02 | [FPS-120.md](records/FPS-120.md) | What capped the game at 60, the Glide refresh override, measured 120; conf-knob findings void (top note) |
| record 2026-10-02 | [FRAMERATE-COVERAGE-2026-10-02.md](records/FRAMERATE-COVERAGE-2026-10-02.md) | What the proxy fixes against everything the spec says depends on frame count |
| record 2026-10-03 | [PER-FRAME-AUDIT-2026-10-03.md](records/PER-FRAME-AUDIT-2026-10-03.md) | Actions taken once per rendered frame (hazards, radar turn, collisions, dead-weapon click, AI rolls) and their fixes; measurements at the top |
| record 2026-08-08 | [FRAMERATE-UNCAP-RESEARCH.md](records/FRAMERATE-UNCAP-RESEARCH.md) | The research verdict before the work was done ("keep 20 Hz, interpolate"); superseded by the switch set |
| living | [HANDLING-MODEL.md](HANDLING-MODEL.md) | How the car drives: the fitted yaw-rate model, measured from the live process |
| record 2026-10-02 | [HEALTH-BAR-COLOUR.md](records/HEALTH-BAR-COLOUR.md) | Why the target health bar went the wrong colour under the health-percent fix, and the corrected formula |

## 3. Graphics and renderers

| | Doc | What it is |
|---|---|---|
| record 2026-10-02 | [GRAPHICS-ENHANCEMENT.md](records/GRAPHICS-ENHANCEMENT.md) | Supersampling and antialiasing menu; the measured matrix and the pick (2x + 4x MSAA at 120) are in the last section |
| record 2026-10-02 | [RENDERER-ALTERNATIVES.md](records/RENDERER-ALTERNATIVES.md) | Survey of other Glide wrappers and back ends; section 11 has the measurements (none passes 120) |
| living | [DRAW-DISTANCE.md](DRAW-DISTANCE.md) | The far clip, the render pools and the 1800 m patch |
| record 2026-10-02 | [FARCLIP-CAMERA-CRASH.md](records/FARCLIP-CAMERA-CRASH.md) | The int16 terrain-index ceiling that crashes wide views past 2500 m |
| record 2026-10-02 | [MENU-HD-ART.md](records/MENU-HD-ART.md) | Offline pipeline for higher-resolution menu art |
| parked | [HD-TEXTURES-RESEARCH.md](HD-TEXTURES-RESEARCH.md) | The texture formats (ZFS / VQM / M16) cracked; the HD pack itself retired 2026-07-27 |
| parked | [VOODOO-PARKED.md](VOODOO-PARKED.md) | Glide to Metal on the Mac: works, but recompiles shaders every launch; the one announcement that would revive it |
| parked | [VISUAL-QUALITY-MAC.md](VISUAL-QUALITY-MAC.md) | The Voodoo-mode graphics wins on the Mac and the warm-up ceiling proof |
| parked | [DXGI-DGVOODOO-RESEARCH.md](DXGI-DGVOODOO-RESEARCH.md) | The full dgVoodoo-under-Wine research log; superseded by VOODOO-PARKED |
| living | [DXWND-TUNING.md](DXWND-TUNING.md) | DxWnd profile settings for the Mac build, grounded in the DxWnd source |
| record 2026-07-13 | [MODERN-PORTS-AND-VR.md](records/MODERN-PORTS-AND-VR.md) | Is there a Direct3D or VR port? (No.) The reimplementation projects |

## 4. Controls and input

Binding rules are in [`../AGENTS.md`](../AGENTS.md): `input.map` is the only live file.

| | Doc | What it is |
|---|---|---|
| living | [CONTROL-DOCTRINE.md](CONTROL-DOCTRINE.md) | The two-tier control design: critical actions never depend on one platform's layer |
| living | [GAMEPAD-PC-MAC.md](GAMEPAD-PC-MAC.md) | Xbox pad on PC and Mac through the native joystick path |
| living | [INPUT-REMAPPER.md](INPUT-REMAPPER.md) | The AutoHotkey layer inside the Wine / Proton prefix (shift layer, mouse buttons, wheel) |
| living | [`input.map.reference`](input.map.reference) | A known-good `input.map` (installed by the Mac installer) |
| living | [`pad-layout.svg`](pad-layout.svg), [`pad-layout-shift.svg`](pad-layout-shift.svg) | Controller diagrams generated by `tools/pad-diagram.py`; never hand-edited |
| living | [FIGHTERSTICK.md](FIGHTERSTICK.md) | A CH Fighterstick on a driving game; confirmed in the game 2026-08-08 |
| living | [WHEEL-T300.md](WHEEL-T300.md) | Thrustmaster T300RS on Windows: steering, pedals, buttons |
| living | [HEAD-TRACKING.md](HEAD-TRACKING.md) | opentrack driving the in-game view |
| living | [I76-GAMEPLAY-REFERENCE.md](I76-GAMEPLAY-REFERENCE.md) | Controls, weapons, specials: the gameplay facts that trip people up |
| living | [DECK-CONTROLS.md](DECK-CONTROLS.md) | The Steam Deck controller layout |
| record 2026-07-13 | [DECK-INPUT-SCIENCE.md](records/DECK-INPUT-SCIENCE.md) | The Deck input pipeline, and why controls were hard there |
| living | [STEAMDECK-INPUT-MODES.md](STEAMDECK-INPUT-MODES.md) | Reusable reference for hand-written Steam Input layouts |
| record 2026-08-01 | [DECK-BASELINE.md](records/DECK-BASELINE.md) | The Deck baseline control tier: deployable, not yet run on Deck hardware |

## 5. Force feedback, rumble and motion

| | Doc | What it is |
|---|---|---|
| living | [FFB-STACKS.md](FFB-STACKS.md) | Read before running FFB: the Windows wheel / shaker stack and the Mac shim side by side, and where they fight |
| record 2026-07-19 | [FFB-DEEP-DIVE.md](records/FFB-DEEP-DIVE.md) | Static RE of the game's FFB plugin interface and effect block |
| living | [FFB-DESIGN-LIBRARY.md](FFB-DESIGN-LIBRARY.md) | Working reference for designing forces for a wheel, pad, shaker or rig |
| record 2026-10-01 | [FFB-DATA-AUDIT.md](records/FFB-DATA-AUDIT.md) | Audit of the FFB and telemetry stack against the i76-map specs |
| record 2026-08-02 | [FFB-LAPTOP-RECON.md](records/FFB-LAPTOP-RECON.md) | Solved: FFB dies when extra or virtual joysticks are installed |
| record 2026-07-19 | [FFB-MORNING-TEST.md](records/FFB-MORNING-TEST.md) | Pad-rumble field test and tuning sheet |
| parked | [FORCE-FEEDBACK-AND-VISUALS.md](FORCE-FEEDBACK-AND-VISUALS.md) | Mac wheel FFB through DirectInput is a dead end (the shim route is in FFB-DEEP-DIVE); the 1024x768 software ceiling |
| record 2026-07-19 | [SIM-RUMBLE-RESEARCH.md](records/SIM-RUMBLE-RESEARCH.md) | Cited research behind the two-motor rumble mixer |
| record 2026-07-19 | [MOTION-SIM.md](records/MOTION-SIM.md) | Mapping the force stream onto a motion rig; not rig-verified |
| record 2026-10-01 | [SOUND-INTERPOSER-REVIEW.md](records/SOUND-INTERPOSER-REVIEW.md) | Review of the sound proxies against the sound spec |

## 6. Audio

| | Doc | What it is |
|---|---|---|
| living | [MUSIC.md](MUSIC.md) | Why the game had no music on Windows and how the proxy restored it |
| living | [MUSIC-TRACK-MAP.md](MUSIC-TRACK-MAP.md) | Which CD track each mission asks for |

## 7. Menus, saves and the save editor

| | Doc | What it is |
|---|---|---|
| living | [SAVE-FREEZE-ROOT-CAUSE.md](SAVE-FREEZE-ROOT-CAUSE.md) | The save / popup freeze: root cause, proof, and the `u32x` fix |
| record 2026-08-10 | [SHELL-MENU-AND-SAVE-FREEZE.md](records/SHELL-MENU-AND-SAVE-FREEZE.md) | How the shell, the menus and the cursor work; the investigation behind the fix |
| record 2026-10-01 | [MENU-USABILITY-PLAN.md](records/MENU-USABILITY-PLAN.md) | Catalogue of menu pain points with status and plan (superseded items noted at the top) |
| record 2026-10-02 | [MENU-REBUILD-DESIGN.md](records/MENU-REBUILD-DESIGN.md) | Design study for rebuilding the menu layer |
| record 2026-10-01 | [SAVES-STATE-AND-TEST-PLAN.md](records/SAVES-STATE-AND-TEST-PLAN.md) | Everything known about saves, and the sandbox test protocol |
| record 2026-10-01 | [SAVES-LEG-A-RUN-2026-10-01.md](records/SAVES-LEG-A-RUN-2026-10-01.md) | Protocol run, leg A: write a bookmark |
| record 2026-10-01 | [SAVES-LEG-B-RUN-2026-10-01.md](records/SAVES-LEG-B-RUN-2026-10-01.md) | Protocol run, leg B: load it and verify the car |
| record 2026-07-19 | [SAVE-ORPHAN-INVESTIGATION.md](records/SAVE-ORPHAN-INVESTIGATION.md) | The orphaned-save bug: what is established and what is open |
| living | [SAVE-FORMAT-GAPS.md](SAVE-FORMAT-GAPS.md) | The save format as the game writes it, against what the editor reads |
| record 2026-10-02 | [SAVE-EDITOR-STATUS-2026-10-02.md](records/SAVE-EDITOR-STATUS-2026-10-02.md) | Save editor: what works, what is byte-exact, what still needs the game |
| living | [EDITOR-FIELD-TESTS.md](EDITOR-FIELD-TESTS.md) | The save editor's in-game verification checklist |
| record 2026-10-02 | [MOUNT-VALIDATION.md](records/MOUNT-VALIDATION.md) | What decides whether an equipped item stays mounted when a save loads |
| living | [MISSION-LAUNCH.md](MISSION-LAUNCH.md) | Booting straight into a mission with `I76_MISSION` |

The editors themselves are at the repo root: [`../i76-save-editor.html`](../i76-save-editor.html),
[`../i76-save-editor.py`](../i76-save-editor.py), [`../i76-save-editor.command`](../i76-save-editor.command).

## 8. Platforms and setup

| | Doc | What it is |
|---|---|---|
| living | [MAC-BUILD.md](MAC-BUILD.md) | The shipping Apple Silicon build and its launchers |
| record 2026-07-04 | [MAC-SETUP.md](records/MAC-SETUP.md) | The original Windows-to-Mac handoff brief; superseded by MAC-BUILD and VERIFIED-FIXES |
| record 2026-07-10 | [PORTING-WINDOWS-WINS-TO-MAC.md](records/PORTING-WINDOWS-WINS-TO-MAC.md) | Which Windows-box wins carry back to the Mac |
| living | [STEAMDECK.md](STEAMDECK.md) | The Steam Deck recipe |
| living | [WINDOWS-PLAYBOOK.md](WINDOWS-PLAYBOOK.md) | The Windows setup playbook (2026-07 research, corrected in place) |
| record 2026-07 | [FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md](records/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md) | Windows results and the texture-format work, as a community report |
| record 2026-06-08 | [MODERN-SETUP.md](records/MODERN-SETUP.md) | Early notes for one Windows copy |
| record 2026-07 | [`WHAT-THIS-IS-dgvoodoo.txt`](records/WHAT-THIS-IS-dgvoodoo.txt) | The note shipped beside the first dgVoodoo config |
| record 2026-07-05 | [RUNNING-I76-EVERYWHERE.md](records/RUNNING-I76-EVERYWHERE.md) | Cited compendium of every documented way to run the game |
| record 2026-07 | [`i76-research-full.txt`](records/i76-research-full.txt) | Raw research dump behind the compendium |
| record 2026-07-14 | [PHONE-PORTS.md](records/PHONE-PORTS.md) | Android and iPhone options; research, untested |

## 9. Reverse engineering: memory, engine, formats

For the engine as a whole, the sibling repos hold the current references (`../i76-uncap-lab/docs/ENGINE-REFERENCE.md`,
`../i76-map`); see [`../AGENTS.md`](../AGENTS.md).

| | Doc | What it is |
|---|---|---|
| living | [MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md) | The reconciled memory map: pointer chains, tables, tools, and a dead-ends list. Read before the raw logs |
| record 2026-07-18 | [GHIDRA-MEMORY-MAP.md](records/GHIDRA-MEMORY-MAP.md) | Raw session log of the memory-RE push; contains claims later corrected |
| record 2026-07-18 | [STATIC-RE-FABLE.md](records/STATIC-RE-FABLE.md) | Raw static-RE findings from the same push; same caveat |
| record 2026-07-18 | [MW2-I76-STRUCTS.md](records/MW2-I76-STRUCTS.md) | Vehicle, weapon and armour structures from the file formats and the reimplementation projects |
| living | [LEVEL-FORMAT.md](LEVEL-FORMAT.md) | Level file chunks, objects, repair spots |
| living | [WEAPON-STATS.md](WEAPON-STATS.md) | The published weapon table, mirrored; doubles as a search oracle |
| living | [MODDING-GUIDE.md](MODDING-GUIDE.md) | Which lever changes what (data files, proxy switches, trainer, patches) and the traps |
| record 2026-09-04 | [FRESH-START-2026-09-04.md](records/FRESH-START-2026-09-04.md) | The from-scratch RE survey that started the i76-map work |
| record 2026-09-05 | [FRESH-START-METHOD.md](records/FRESH-START-METHOD.md) | The methodology for that work, revision 2 |
| living | [RE-METHODOLOGY.md](RE-METHODOLOGY.md) | Practical method for cracking live-memory values |
| living | [RE-FIELD-GUIDE.md](RE-FIELD-GUIDE.md) | Cited field guide to reverse-engineering vintage games |
| living | [RE-RESOURCES.md](RE-RESOURCES.md) | Reading list for live-memory work |
| living | [FIND-WHAT-WRITES.md](FIND-WHAT-WRITES.md) | Hardware-breakpoint "find what writes" and how to run it here |
| record 2026-07-19 | [DEBUG-MENU-FIELD-TEST.md](records/DEBUG-MENU-FIELD-TEST.md) | Field-test sheet for the AutoHotkey debug menu |

## 10. Community material and game data references

| | Doc | What it is |
|---|---|---|
| living | [COMMUNITY-RESOURCES.md](COMMUNITY-RESOURCES.md) | Published community work, indexed by the problem it solves. Check before reverse-engineering |
| living | [COMMUNITY-SITEMAP.md](COMMUNITY-SITEMAP.md) | Per-site inventory of every known community site |
| living | [ASSET-BIBLE.md](ASSET-BIBLE.md) | Object class names, dimensions and types (DIVER, 2000), converted |
| living | [`asset-bible/`](asset-bible/INDEX.md) | The per-category pages of the same (30 files; start at INDEX.md) |

## 11. Scope

| | Doc | What it is |
|---|---|---|
| living | [SCOPE-AND-LEGITIMACY.md](SCOPE-AND-LEGITIMACY.md) | What the project is and why modifying an owned copy is legitimate |
| living | [LEGITIMACY-AND-SCOPE.md](LEGITIMACY-AND-SCOPE.md) | The shorter scope statement (overlaps the one above; backlog P3-08 proposes folding them) |

## Docs outside this folder

[`../README.md`](../README.md) (front page), [`../INSTALL.md`](../INSTALL.md), [`../CHANGELOG.md`](../CHANGELOG.md),
[`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`../THIRD-PARTY.md`](../THIRD-PARTY.md), and the component READMEs:
[`../music-fix/`](../music-fix/README.md) (the proxy and every switch), [`../u32x/`](../u32x/README.md),
[`../smack-music-fix/`](../smack-music-fix/README.md), [`../ffb-shim/`](../ffb-shim/README.md),
[`../sound-rumble/`](../sound-rumble/README.md), [`../saves/`](../saves/README.md),
[`../texture-lab/`](../texture-lab/README.md), [`../tools/ffb/`](../tools/ffb/README.md),
[`../tools/trainer/`](../tools/trainer/README-GUI.md), [`../tools/telemetry/`](../tools/telemetry/README.md),
[`../tools/bisect/`](../tools/bisect/README.md), [`../tools/openglide-hd/`](../tools/openglide-hd/README.md).

## Rule of thumb

If a doc says an approach is "in progress", "to try" or "not yet run", check its date, then check
[ENHANCEMENTS.md](ENHANCEMENTS.md), [VERIFIED-FIXES.md](VERIFIED-FIXES.md) and the parked docs before acting.
Several once-open items are settled: the Mac shader warm-up is a platform floor, Mac wheel FFB through DirectInput
is a dead end, HD textures were retired, 120 fps is the ceiling. Do not re-open a settled dead end, and do not
trust a dgVoodoo conf finding until the conf is shown to be the one dgVoodoo loaded.
