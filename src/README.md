# src/: the fix catalogue

Every fix this project ships is a small piece of our own code that sits between the 1997 game and Windows: a proxy DLL
the game loads, a patch to a byte the game reads, or a script around the launch. This page lists them by component:
what each fixes, the switch that turns it on (an `I76_*` environment variable the presets set, unless it says
"always"), and the record that measured it. The full list of enhancements with their evidence is
[docs/engine/ENHANCEMENTS.md](../docs/engine/ENHANCEMENTS.md); every symptom with its cause is
[docs/engine/VERIFIED-FIXES.md](../docs/engine/VERIFIED-FIXES.md).

**Where the code is.** The components are still at the repository root (this folder only holds this catalogue for
now). They move under `src/` in a later step, once no working copy carries uncommitted edits in them
([the layout plan](../docs/status/REPO-LAYOUT-PLAN-2026-10-26.md), section 5). Each component's README has its build
line and its full switch table.

## The proxy: `Strlkup.dll` ([`music-fix/`](../music-fix/README.md))

The game imports `Strlkup.dll` statically, so our proxy loads with it, passes the five real exports on to the original
and patches the running game. One DLL for Gold and Nitro (`nitro.c` maps each patch site to `nitro.exe`). Build:
[music-fix/README.md](../music-fix/README.md#build) (mingw or MSVC, 32-bit). Every switch is off unless a preset sets it.

| What it fixes | Switch | Source | Record |
|---|---|---|---|
| No music in missions: the CD-audio calls play GOG's mp3 tracks instead; the volume slider works | always | `strlkproxy.c` | [docs/guides/MUSIC.md](../docs/guides/MUSIC.md) |
| 20 fps cap and frame-rate-dependent physics: fixed physics step, render interpolation, high-resolution clock, frame-rate-independent engine response | `I76_FIXED_STEP`, `I76_RENDER_INTERP`, `I76_HIRES_CLOCK`, `I76_ENGINE_DT_FIX` | `strlkproxy.c` | [FPS-120](../docs/records/FPS-120.md), [FRAMERATE-COVERAGE](../docs/records/FRAMERATE-COVERAGE-2026-10-02.md) |
| The whole simulation on one fixed tick (the 1997 feel at any frame rate) | `I76_SIM_TICK_MS` | `simtick.c` | [WHOLE-SIM-TICK](../docs/records/WHOLE-SIM-TICK-2026-10-17.md), [TICK-FINISH](../docs/records/TICK-FINISH-2026-10-18.md) |
| Things that ran once per rendered frame (hazards, collisions, AI rolls, radar, the dead-weapon click) | `I76_AI_FIXES`, `I76_COLL_DEDUPE` and others | `strlkproxy.c` | [PER-FRAME-AUDIT](../docs/records/PER-FRAME-AUDIT-2026-10-03.md) |
| 600 m draw distance; terrain detail; the int16 terrain-index crash past 2500 m | `I76_FAR_CLIP`, `I76_TERRAIN_LOD` | `strlkproxy.c`, `faredge.c` | [docs/engine/DRAW-DISTANCE.md](../docs/engine/DRAW-DISTANCE.md), [FARCLIP-CAMERA-CRASH](../docs/records/FARCLIP-CAMERA-CRASH.md) |
| The hard edge at the far clip (haze, Glide fog) | `I76_EDGE_FADE`, `I76_GLIDE_FOG` | `faredge.c` | [FAR-EDGE-FADE](../docs/records/FAR-EDGE-FADE-2026-10-23.md) |
| Terrain popping as detail changes | `I76_TERRAIN_MORPH` | `terrainmorph.c` | [TERRAIN-MORPH](../docs/records/TERRAIN-MORPH-2026-10-21.md), [TERRAIN-POPS](../docs/records/TERRAIN-POPS-2026-10-23.md) |
| Terrain pass cost (bush texture variants resolved once, a shade table) | `I76_M16_MEMO`, `I76_SHADE_TABLE` | `m16memo.c`, `shadetable.c` | [TERRAIN-PASS-OPT-PLAN](../docs/records/TERRAIN-PASS-OPT-PLAN-2026-10-25.md) |
| A rear-view mirror that sees only cars on a plain sky | `I76_MIRROR_LOD`, `I76_MIRROR_M16` ... | `mirrordetail.c`, `skymirror.c` | [MIRROR-DETAIL](../docs/records/MIRROR-DETAIL-2026-10-23.md) |
| Stretched picture on wide screens (Hor+ field of view) | `I76_ASPECT`, `I76_FOV` | `strlkproxy.c` | [docs/engine/ENHANCEMENTS.md](../docs/engine/ENHANCEMENTS.md) |
| The camera dipping into the ground; the nose on jumps | `I76_CAM_GROUND_FIX`, `I76_JUMP_NOSE` | `strlkproxy.c`, `jumpnose.c` | [TICK-FINISH](../docs/records/TICK-FINISH-2026-10-18.md) |
| The target health bar's colour | `I76_FIX_HEALTH_PCT` | `strlkproxy.c` | [HEALTH-BAR-COLOUR](../docs/records/HEALTH-BAR-COLOUR.md) |
| The pointer in the menus under a stretched picture | `I76_CURSOR_MAP` | `cursormap.c`, `cursoraw.c` | [CURSOR-FIX-ON-18](../docs/records/CURSOR-FIX-ON-18-2026-10-17.md) |
| The Esc menu pointer on the Macs; menus driven by a pad; keyboard shortcuts and fades | `I76_MENU_PTR`, `I76_PAD_MENU`, `I76_MENU_KEYS` | `escmenu.c`, `padmenu.c`, `polish.c` | [MAC-CONVERGE](../docs/records/MAC-CONVERGE-2026-10-20.md), [MENU-SOUND-POLISH](../docs/records/MENU-SOUND-POLISH-2026-10-20.md) |
| Sound balance; the music slider curve; Nitro's lost effect volume | `I76_SFX_GAIN`, `I76_MUSIC_GAIN`, `I76_MUSIC_CURVE` | `soundmix.c` | [NITRO-POLISH](../docs/records/NITRO-POLISH-2026-10-24.md) |
| Your own extra music and voice folders | `I76_MUSIC_EXTRA`, `I76_VOICES` | `musicextra.c`, `voices.c` | [CONTENT-INSTALLER](../docs/records/CONTENT-INSTALLER-2026-10-25.md) |
| Force feedback lost after Alt-Tab or a restart | `I76_FFB_REACQUIRE` (on) | `ffbfocus.c` | [FFB-FOCUS](../docs/records/FFB-FOCUS-2026-10-24.md) |
| The Windows 11 24H2 start-up crash in winmm | `I76_WINMM_HEAPFIX` | `winmmrace.c` | [DGVOODOO-UPDATE](../docs/records/DGVOODOO-UPDATE-2026-10-24.md) |
| Co-op missions over the network; AI opponents and AI fill in network arenas; the game's difficulty as AI skill | `I76_COOP_AI`, `I76_AIMELEE`, `I76_AIMELEE_FILL`, `I76_COOP_SCALE`, `I76_DIFFICULTY_AI` | `strlkproxy.c`, `aimelee.c`, `mpfill.c`, `difficulty.c` | [docs/guides/COOP.md](../docs/guides/COOP.md), [AI-MELEE-AND-LATE-JOIN](../docs/records/AI-MELEE-AND-LATE-JOIN-2026-10-19.md), [MP-OVERNIGHT](../docs/records/MP-OVERNIGHT-2026-10-20.md) |
| The multiplayer connection menu (IPX pinning, arena list) | `I76_MP_MENU` | `mpmenu.c` | [COOP-LIST-ENTRIES](../docs/records/COOP-LIST-ENTRIES-2026-10-18.md) |
| Nitro Pack: Gold's fixes on `nitro.exe`, network arenas and game types | `I76_NITRO_MP`, `I76_NITRO_AI`, `I76_NITRO_GAMETYPES` | `nitro.c`, `nitro_mp.c`, `nitro_ai.c`, `nitro_form.c`, `nitroparity.c` | [NITRO-PORT](../docs/records/NITRO-PORT-2026-10-21.md), [NITRO-MP-DESIGN](../docs/records/NITRO-MP-DESIGN-2026-10-21.md), [NITRO-PARITY](../docs/records/NITRO-PARITY-2026-10-24.md) |
| Straight into a mission; two copies on one PC; skip movies in tests | `I76_MISSION`, `I76_MULTI_INSTANCE`, `I76_SKIP_MOVIES`, `I76_SKIP_CUTSCENES` | `strlkproxy.c` | [docs/guides/MISSION-LAUNCH.md](../docs/guides/MISSION-LAUNCH.md), [SKIP-CUTSCENES](../docs/records/SKIP-CUTSCENES-2026-10-25.md) |
| Lab instruments (frame replay, pass timers, census logs, self-mute) | `I76_REPLAY`, `I76_PASS_TIMERS`, `I76_MUTE` ... | `replay.c`, `passtimers.c`, `terrainpops.c`, `mutesess.c` | [LAB-FRAME-REPLAY](../docs/records/LAB-FRAME-REPLAY.md) |

The tested switch sets are the presets in [`shared/presets/`](../shared/presets/); `mciproxy.log` in the game folder
lists every switch as applied or skipped.

## The other components

| Component | What it fixes | How it is turned on | Record |
|---|---|---|---|
| [`u32x/`](../u32x/README.md) `u32x.dll` | The menu and save-screen mouse under a stretched picture; the Save Bookmark freeze (window ghosting) | always (the installer points the USER32 import of `i76.exe` and `i76shell.dll` at it) | [docs/engine/SAVE-FREEZE-ROOT-CAUSE.md](../docs/engine/SAVE-FREEZE-ROOT-CAUSE.md) |
| [`smack-music-fix/`](../smack-music-fix/README.md) `SMACKW32.DLL` | Music playing on under cutscenes where a music layer ignores the game's stop | the Mac installers place it; `windows/Setup-From-GOG.ps1` when it has been built | [MUSIC-RETAIL-INTENT](../docs/records/MUSIC-RETAIL-INTENT.md) |
| [`ffb-shim/`](../ffb-shim/README.md) `i7_sfrce.dll` | Gamepad rumble from the game's own force-feedback data (Mac, Deck) | the Mac and Deck kits place it | [FFB-DEEP-DIVE](../docs/records/FFB-DEEP-DIVE.md) |
| [`sound-rumble/`](../sound-rumble/README.md) `dsound.dll` | Rumble from the sounds the game plays (the backup path) | by hand | [SIM-RUMBLE-RESEARCH](../docs/records/SIM-RUMBLE-RESEARCH.md) |
| [`tools/patch-kit/`](../tools/patch-kit/README.md) shell-key patches | Keyboard shortcuts in the menus' popups (Enter / Space / Y / N), Gold and Nitro | always in the Patch Kit (`Apply-Shell-Keys.ps1`, our bytes only) | [TESTER-BUILD](../docs/records/TESTER-BUILD-2026-10-23.md) |
| [`tools/fix-shell-textentry.ps1`](../tools/fix-shell-textentry.ps1) | Typing in the save screen (only one character typed) | the Patch Kit's first start runs it (`i76e-prepare.ps1`); the launcher repairs it too | [docs/engine/SAVE-FREEZE-ROOT-CAUSE.md](../docs/engine/SAVE-FREEZE-ROOT-CAUSE.md) |
| [`tools/i76wheel.c`](../tools/i76wheel.c) `i76wheel.exe` | The mouse wheel as weapon keys | the launcher starts it | [docs/guides/CONTROLS.md](../docs/guides/CONTROLS.md) |
| [`tools/openglide-hd/`](../tools/openglide-hd/README.md) | The Mac 3D path (OpenGLide with our patches) | the Mac Kit ships it | [MAC-GRAPHICS](../docs/records/MAC-GRAPHICS-2026-10-24.md) |
| [`windows/`](../windows/README.md) AutoHotkey layers | Pad shift layer, wheel buttons, flight stick, head look | the launcher starts them with the game | [docs/guides/INPUT-REMAPPER.md](../docs/guides/INPUT-REMAPPER.md), [docs/engine/CONTROL-DOCTRINE.md](../docs/engine/CONTROL-DOCTRINE.md) |

## Adding or changing a fix

1. Find or file the issue, and read the component's README and its records first
   ([docs/process/PROCESS.md](../docs/process/PROCESS.md)).
2. New behaviour goes behind a new `I76_*` switch, off by default; a preset turns it on once it is measured.
3. Measure it (n runs, a control run, the spread) and write a dated record in [`docs/records/`](../docs/records/), then
   run `python tools/records-index.py`.
4. Add a row here and in [docs/engine/ENHANCEMENTS.md](../docs/engine/ENHANCEMENTS.md).
