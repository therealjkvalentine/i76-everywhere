# Reimplementing Interstate '76 in a modern engine: which engine, and how (2026-10-17)

Question from James, for Michael: "Michael would like to reimplement this game in Unreal Engine. Would this be
possible or advisable? Would Godot, Unity or another engine be much more appropriate, or is Unreal okay?"

This is a paper study: no game was run, no install touched. It surveys what the family's repositories already hold
before proposing anything, because a lot of this work turns out to exist already.

## The recommendation (one paragraph)

**Unreal would work, but it is the hardest of the options for this particular game, and it is not the best fit. Use
Godot 4.** Two reasons. First, the hard part of I'76 is not graphics. It is the 1997 vehicle physics, AI, damage and
mission scripts, which have to be rewritten by hand as ordinary code whichever engine is picked. Unreal's main
strengths (photoreal rendering, Chaos vehicles, Nanite) go unused, and its costs are real: a tens-of-gigabytes
install, C++ for anything that must match the original, binary asset files that do not diff in git, and awkward
builds for the Mac and the Steam Deck. Second, and bigger: **the family already has a working Godot reimplementation.**
`C:\Users\james\i76-remake` (Godot 4.7, GDScript, 286 commits, 2026-10-03..07, never pushed anywhere) reads the
player's own install, drives with the original's physics model, fights with the original's weapons and damage, runs
the original mission scripts T01-T17, and its built-in test driver wins 7 of the first 12 missions (27 of 48 seeded runs, milestone 58). Starting
Michael's repository **from that code** (renamed, published, cleaned) puts him months ahead, in an engine that runs
natively on the family's Apple-silicon Macs and on the Steam Deck, costs nothing ever, and uses a language
(GDScript, close to Python) that a teenager can read on day one. If Michael specifically wants to learn Unreal (for
a career, say), that is a fine goal, but then the honest framing is "a second, harder port for learning", not "the
best way to get I'76 running again".

## 1. What already exists (survey before building)

This list is the main finding of the study. Every item is local unless a URL is given.

| what | where | state | why it matters |
|---|---|---|---|
| **I76 Remake (Godot)** | `C:\Users\james\i76-remake` | milestone 58, about 30,000 lines of GDScript including tests, GPL-3.0, last commit 2026-10-07, no git remote | Phases 0-3 below are largely done here. Read `docs/STATUS.md` (plain summary), `docs/ROADMAP.md`, `docs/SPEC-GAPS.md`, `docs/SUBSYSTEM-MAP.md`, `docs/MAC.md` |
| Remake test runs | `C:\Users\james\i76-remake-tools` | Godot 4.7.2 binaries, milestone logs, screenshots | Evidence for the remake's claims |
| Format reference | `C:\Users\james\i76-map\data\FORMATS.md`, parsers `data\fmt\*.py` | all 30 file families, 6,368 files round-trip byte-exact, 0 errors | The loaders' specification and their test oracle |
| Engine spec index | `i76-map\REIMPLEMENTATION.md`, `ARCHITECTURE.md`, `subsystems\*.md` | every system marked "spec" except networking ("partial") | The prose specification a clean-room port is written from |
| Gap list against Open76 | `i76-map\OPEN76-GAPS.md` | sections 21-22: spec gaps and a top-10 for a faithful port | Shows what a naive engine port gets wrong |
| Mission scripts | `i76-map\data\FSM.md`, `data\notes\fsm-actions.md`, decompiled scripts `data\out\fsm\*.fsm` | 14 opcodes, 96 actions | The mission VM is small; the actions touch every system |
| Vehicles | `i76-map\data\VEHICLES.md`, `data\vehicles.csv`; `docs\PARTS-REFERENCE.md`, `docs\WEAPON-STATS.md` | spec | Car, part and weapon numbers, with an external cross-check |
| Shell (menus, garage, saves) | `i76-map\shell\` (SCREENS.md, SAVE.md, CALLBACKS.md) | screens, save format and callbacks mapped | The remake has no menus yet; this is their spec |
| Physics timing | `docs/records/PHYSICS-STEP-STUDY-DESIGN.md`, `DEV-INTENT-EVIDENCE.md`, `DEV-GAME-CLUB-I76.md`, `WHOLE-SIM-TICK-2026-10-17.md`, `STEP-LENGTH-CURVE.md` | the step rule is known; the developers designed for 15 fps = 2 x 33.3 ms substeps | Sets the port's fixed step |
| Versions | `docs/records/I76-VERSIONS.md`, `EXE-DIFF-MAP.md`, `VERSIONS-AND-PHYSICS-2026-10-17.md`, `BASE-DECISION-1.0-vs-GOG.md` | retail 1.0 and Gold share the same vehicle physics code; Gold changed combat and rendering | Tells the port which numbers come from which release |
| Arcade vs simulation | `docs/records/ARCADE-PHYSICS.md` | one entity bit, five code sites, measured | The gold standard is simulation mode |
| **Gold-standard target** | `docs/records/GOLD-STANDARD-FINGERPRINT.md`; checker lab `emu\tools\memtrace\fingerprint.py`; reference `emu\results\gold-standard\retail-p166-low.json` | 49 traces of retail 1.0 on an emulated P166, 219 metrics, pass bands from the measured spread | **A ready-made acceptance test for the port's driving physics** |
| Frame replay | `docs/records/LAB-FRAME-REPLAY.md` | the original's per-frame inputs and dt replay bit-exactly | Lets the port be fed exactly the inputs the original saw |
| AI and damage metrics | `docs/records/AI-DAMAGE-METRICS.md`, `AI-DAMAGE-BALANCE.md` | measuring tools exist | Acceptance tests for combat |
| Handling model | `docs/HANDLING-MODEL.md`; lab `docs\ENGINE-REFERENCE.md` | fitted yaw-rate law and constants | Second check on the ported car |
| Multiplayer | `docs/MULTIPLAYER.md`; `i76-map\subsystems\network.md` | the original protocol is named statically, not checked live | A new port should use its own LAN protocol |
| Music | `docs/MUSIC.md`, `MUSIC-TRACK-MAP.md`, `docs/records/MUSIC-RETAIL-INTENT.md` | track map and retail behaviour known | Which track plays when |
| Community work | `docs/COMMUNITY-RESOURCES.md`, `docs/records/MODERN-PORTS-AND-VR.md` | Open76 (Unity, GPL-3, mostly an asset viewer with stand-in physics); Roanish/i76 (C + SDL2 + Vulkan, very early) | Neither is a playable game; ours is further along than both |
| Original-IP successor | `C:\Users\james\time-vigalantes` (Godot 4 + C#, github.com/therealjkvalentine/time-vigalantes) | 21 commits, June 2026; its `docs/engine-decision.md` already chose Godot over Unity and Unreal | A different goal: a new game, not a remake. Same engine conclusion |

**Caveat on the remake:** its README and STATUS are its own claims. This study read them and the code layout, not a
fresh run. Per the repo's rule that docs record intent, not state, Phase 0 below starts by re-running its tests on
the owner's PC and on a Mac (`docs/MAC.md` describes the Mac route but no Mac run is recorded).

## 2. The engines compared

Scale: **good / fair / poor** for this project (a faithful I'76 reimplementation by a family with a teenager,
Windows PC plus Apple-silicon Macs plus a Steam Deck).

| criterion | Unreal Engine 5 | Unity 6 | Godot 4.7 | custom C/C++ (SDL3 + bgfx or raylib) | Rust + Bevy |
|---|---|---|---|---|---|
| Licence and money | 5 % royalty on lifetime gross above $1M per product (source 1); free for us in practice; engine source "available", not open | Personal plan free under $200K revenue and funding (2026); runtime fee cancelled Sept 2024; Pro +5 % from 2026-01-12 (source 2) | MIT, no fees, no royalties, ever (source 3) | whatever we pick; SDL3 zlib, bgfx BSD | MIT / Apache-2.0 |
| Risk the terms change on us | low-medium (Epic has been stable) | medium (the 2023 runtime-fee episode) | none (MIT cannot be withdrawn) | none | none |
| Faithful 1997 physics | must be **custom C++** (Chaos vehicles are a different model); fine | must be **custom C#**; fine | custom GDScript/C#; **already done** in the remake (`src/physics/vehicle_sim.gd`) | custom C; closest to the original's own code shape | custom Rust; fine |
| Fixed 33.3 ms step, draw at any rate | possible (own accumulator; engine tick is variable by default) | `FixedUpdate` at a set step; easy | `_physics_process` at a set rate plus an own accumulator; the remake already steps at a fixed rate and interpolates the draw | trivial: we own the loop | `FixedUpdate` schedule; easy |
| Determinism (same inputs, same result) | possible with care in C++ | possible with care; IL2CPP/Mono float differences to watch | the remake has a determinism test (`tests/determinism.gd`) | best: we control every float | good |
| Low-poly 1997 look (palette textures, 4:3 HUD, no filtering) | fights the engine (it wants PBR, Lumen, TAA) | fair | good: Compatibility or Forward+ renderer, unshaded materials | best: draw exactly what we want | fair |
| Native Apple silicon editor and game | yes since UE 5.2 (universal binaries) (source 4); needs Xcode; heavy on a laptop | yes (Apple M1+ editor) (source 5) | yes, universal binary editor and exports (source 6) | yes, if we build it; we write the Mac build | yes |
| Steam Deck / Linux | Linux build needs a cross-compile toolchain from Windows | Linux player export; fine | Linux export from any OS; fine | we build it; fine | fine |
| LAN multiplayer | strong built-in replication (server-authoritative) | Netcode for GameObjects; fair | high-level multiplayer API (ENet); fair | write our own over UDP (ENet library) | community crates |
| Mod support (players' own data, loose files) | hard: content is cooked into .pak files | fair | good: reads loose files at run time; the remake already layers `ADDON\` over `I76.ZFS` | best | good |
| Install and repo size | engine install tens of GB; projects store binary `.uasset` files, need Git LFS | several GB; scenes are YAML but noisy | engine about 150 MB single file; scenes are plain text, diff cleanly | tiny | small engine, long Rust compiles |
| Language for Michael | C++ (hard) or Blueprints (visual, but bad for porting exact maths) | C# (moderate) | GDScript (Python-like, easiest) or C# | C/C++ (hard; no editor) | Rust (hard; strict compiler) |
| Headless tests without a screen | possible (commandlets, automation); slow to start | possible (batch mode) | easy: `godot --headless -s test.gd`; the remake has 20+ test scripts | easy | easy |
| Help available (tutorials, people) | huge | huge | large and growing | small for this kind of game | small, API breaks each release (0.20, Oct 2026) (source 7) |
| Work already done for I'76 | none | Open76 (asset loading only; GPL-3) | **our remake, milestone 58** | Roanish/i76 (early) | none |
| **Overall for this project** | **fair: possible, slowest, heaviest** | **fair** | **good: recommended** | good for an expert, poor for a beginner | fair |

**Why Unreal is "possible but not advised" here, in plain words.** Unreal is built for big modern 3D worlds. I'76
is a 1997 game whose look is 640x480, 8-bit palette textures and a few hundred polygons per car. Everything that
makes it *feel* like I'76 (how the car slides, how armour breaks, how the AI attacks, what the mission script does)
has to be typed in by hand from our specs in any engine. In Unreal that typing happens in C++, with a 5-15 minute
build cycle and a much bigger toolchain, and the Mac and Deck builds each need their own setup. Nothing Unreal gives
for free shortens the hard part.

**What would change the answer:**
- Michael's main goal is to learn Unreal itself. Then Unreal, but keep the simulation in a plain C++ library with no
  Unreal types in it, so it can be tested on its own (section 6, option C).
- The family wants modern-looking graphics (new models, real lighting) rather than the original look. Unreal's
  renderer then starts to earn its cost. Even then, the physics and AI work is the same.
- Online play with strangers becomes a goal. Unreal's networking is the strongest of the four.

## 3. What of our RE carries over directly

Straight into code, as specifications (prose and tables, not disassembly):

1. **File formats and loaders:** `i76-map\data\FORMATS.md`, `FORMATS-tables.md`, `data\fmt\*.py` (the reference
   parsers; their output is the oracle for any new loader), `docs/LEVEL-FORMAT.md`, `docs/ASSET-BIBLE.md`.
   The remake has GDScript loaders for the archive (`I76.ZFS` with LZO), BWD2, .msn, .ter, .sdf, .geo, .m16,
   .map/.act, .vcf/.vdf/.vtf/.tmt, .rtm, .hzd, .elt, weapon and component definitions (`src/io`, `src/formats`).
2. **Vehicle physics, engine and gearbox:** `i76-map\subsystems\physics.md`, `engine.md`, `simclock.md`,
   `framerate.md`; `docs/HANDLING-MODEL.md`; `docs/records/ARCADE-PHYSICS.md`, `RETAIL-HANDLING-DIFF.md`.
3. **Damage and weapons:** `subsystems\damage.md`, `weapons.md`, `cheats.md`; `docs/WEAPON-STATS.md`,
   `docs/PARTS-REFERENCE.md`, `data\VEHICLES.md`.
4. **AI:** `subsystems\ai.md` (34 behaviours, route search, avoidance, fire decisions).
5. **Missions:** `data\FSM.md`, `data\notes\fsm-actions.md`, `subsystems\mission.md` (game states, load order,
   salvage, persistence).
6. **Cameras, HUD, cockpit:** `subsystems\camera.md`, `renderer.md`, `options.md`, `docs/DRAW-DISTANCE.md`.
7. **Sound and music:** `subsystems\sound.md`; `docs/MUSIC.md`, `MUSIC-TRACK-MAP.md`, `records/MUSIC-RETAIL-INTENT.md`.
8. **Menus and saves:** `i76-map\shell\SCREENS.md`, `SAVE.md`; `docs/SAVE-FORMAT-GAPS.md`.
9. **Controls:** `docs/CONTROL-DOCTRINE.md`, `docs/CONTROLS.md`, `controls/input.map` (the owner's layout, which a
   new port should offer as its default).
10. **Measurement:** the gold-standard fingerprint and checker, the frame replay, the AI-damage metrics, the
    remake's `tests/trace_compare.gd` (its own fidelity metric against a capture of the original's AI opening).

## 4. Gaps before a faithful reimplementation

Most systems are specified; what is missing is mostly confirmation and a few decoders.

| gap | how big | note |
|---|---|---|
| **Physics step in the remake** | small | The remake steps at 24 Hz (`STEP_HZ := 24.0`, `src/game/car.gd`), chosen before the 2026-10-17 finding that the developers designed for 15 fps = 2 x 33.3 ms. Moving to 33.3 ms substeps is a one-line change plus re-running every test |
| **Physics never checked against the gold standard** | medium | The remake's A/B was against recorded drives of our patched Gold exe. It has never been run through `fingerprint.py` against the retail 1.0 P166 reference. That is Phase 1's acceptance test |
| Front-end menus, garage screens, intro videos | large | The remake starts straight into a mission. Menu logic is specified in `shell\`; art and fonts come from `DATABASE.MW2` (FORMATS.md section 11). Videos are Smacker (`.smk`): not specified by us; FFmpeg's libavcodec has a Smacker decoder |
| Multiplayer | large | `network.md` is partial and never checked live. Rebuilding the original ANet protocol is optional; a new LAN protocol (port-to-port only) is simpler |
| Spec gaps logged by the remake | medium | `i76-remake\docs\SPEC-GAPS.md` lists every guess (1,400 lines); each is an RE question for i76-map |
| AI fidelity beyond the opening | medium | trace_compare: T12 100 %, T03 99.8-100 %, T05 car t05fp03 93.9 / 92.1 % when replayed. Missions T04, T05, T07, T10, T11, T13-T17 are not won by the test driver; some of that is the bot's skill, some may be fidelity. Not separated yet |
| Renderer look | small-medium | Which original renderer to imitate: Glide (bilinear, full textures, 3dfx gamma) or software (sharp, up to 1024x768). `docs/records/RENDERER-ALTERNATIVES.md`, `GRAPHICS-ENHANCEMENT.md`. A family choice, not an RE gap |
| Per-frame quirks | small | Frame-rate-dependent effects (AI fire gate per frame, flamer damage from the renderer, cloud scroll, keyboard ramps) must be pinned to the fixed tick on purpose: `REIMPLEMENTATION.md` "Known engine quirks" |
| Nitro Pack content | unknown | Our specs are the Gold / 1.0 exe. Nitro (different missions and vehicles) is out of scope until asked |
| Force feedback, wheels, head tracking | small-medium | Godot input is SDL-based (gamepads, rumble); wheel FFB would need a plugin. `docs/FFB-*.md`, `HAPTICS-ARCHITECTURE.md` describe what the original does |
| Running on a Mac | unknown until tried | `i76-remake\docs\MAC.md` is the plan; no Mac run recorded |

## 5. Phased plan, each phase with a test against the original

The acceptance tests compare against the **original game's own measurements** (the gold-standard reference,
recorded traces, screenshots), never against "it looks right". Where the remake already passes a phase, the work is
to re-run the test and record the result, not to rewrite.

| phase | goal | acceptance test against the original | remake today |
|---|---|---|---|
| **0. Loaders and viewer** | Read the player's own install (read-only); browse every car, building and map in a free camera | (a) For every file in the round-trip corpus, the new loader's decoded values equal `data\fmt` parsers' output (JSON dump, 0 diffs). (b) T01 seen from three fixed camera poses matches screenshots from the original at the same pose within a pixel-difference budget agreed beforehand. (c) It runs on the owner's PC, a family Mac and the Deck | (a) LZO decoder tested byte-exact against a reference extractor; full-corpus value diff not done. (b) not done. (c) PC yes; Mac and Deck not recorded |
| **1. Drive one car on one map** | The Instant Melee default car on The Crater, the original's simulation physics, 2 x 33.3 ms substeps | Export the car's per-frame state in the fingerprint's CSV form and run `fingerprint.py compare` against `retail-p166-low.json`: pass every gate row, or fail no more rows than the reference fails against itself (A/A: 2 of 126). Second check: feed an original trace's inputs through the frame-replay format and compare the first 50 frames | Physics ported at 24 Hz; never fingerprinted |
| **2. Weapons, armour, damage** | Fire every weapon, break armour, wreck cars | Rate of fire, range, projectile speed and damage equal `WEAPON-STATS.md` (which matched the live game 8 of 8); AI-DAMAGE-METRICS rows within the measured spread | Done in the remake (milestones 47-48); not measured against the metrics |
| **3. AI and one mission end to end** | T01 from start to MISSION COMPLETE | trace_compare against the original's T01 opening (route agreement threshold agreed beforehand); objectives tick in the same order as the original | T01 won 4 of 4 seeds by the test driver; trace_compare done for T03, T05, T12 |
| **4. The whole campaign, menus, saves** | Main menu, garage, salvage, bookmarks, T01-T17 | An original bookmark (savegame.dir + saveNNN.cmp) imports with the same car, parts and damage; each mission's script outcome matches the original for the same play (scripted replays); menu screens match `shell\SCREENS.md` | Campaign chain and original-bookmark import done; no menus |
| **5. Sound, music, videos** | Engine sound, weapons, CB radio, music per mission, intro and mission videos | Sound events match `sound.md` (600 m cull, voices, engine rows); track per mission matches `MUSIC-TRACK-MAP.md`; videos play from the player's own files | Sound, CB and music done; no videos |
| **6. LAN multiplayer** | Two to four family machines in one melee | Two machines, 10 minutes, positions agree within a set error; works PC-Mac and PC-Deck | none |
| **7. Modding and extras** | Widescreen, high-res, any frame rate (draw interpolated, sim fixed), community maps, controls | Physics fingerprint unchanged at 30, 60, 144 fps draw; a community map from Local Ditch loads | Fixed-step sim with interpolated draw already; widescreen not checked |

Rough effort, for scale only: the remake's own estimate from its milestone-2 planning was 9-12 months of one
person's focused work to a playable campaign. Most of that has since been written. Starting from the remake,
phases 0-1 are a few weekends of checking and the step change; phases 4 (menus) and 6 (multiplayer) are the large
remaining pieces. Starting from zero in Unreal, budget the full 9-12 months or more, plus C++ learning time.

## 6. The options for the family

- **A. Start the new repository from the remake (recommended).** Copy `i76-remake` with its history into the new
  repository, publish it, and make Michael its main developer. He learns the codebase by doing phases 0-1 (re-run,
  measure, change the step), then takes a whole subsystem (menus are a good first big one: visible, self-contained,
  well specified).
- **B. New Godot repository from scratch, the remake as reference.** Best for learning by building, but it repeats
  months of work the family already has. Possible as a learning exercise for Michael alongside A.
- **C. Unreal.** Put the simulation (physics, damage, AI, mission VM) in a plain C++ library with its own tests and
  no Unreal types, and use Unreal only for drawing, sound and input. Port it from the remake's GDScript and our
  specs. Highest cost, best if learning Unreal is the point.
- **D. Michael's own game.** If what Michael really wants is to *make* a car-combat game, `time-vigalantes` (Godot +
  C#, original IP) is already that project. No legal limits on shipping it, and no need for anyone's game data.

## 7. Repository layout and licence (suggestion for option A)

```
<name>/                 neutral name, e.g. "open-i76" or "i76-engine"; no Activision logo or box art
  project.godot
  src/
    io/                 archive, LZO, virtual file system over the player's install
    formats/            one file per format family; each cites its FORMATS.md section
    physics/            vehicle step, ground, collision (cites physics.md / engine.md sections)
    combat/  ai/  mission/  campaign/  audio/  world/  game/  ui/
  tests/                headless tests; each fidelity test names its original-game reference
  tools/                export to the fingerprint CSV; screenshot diff
  docs/
    STATUS.md           plain-language state, for the family
    SPEC-GAPS.md        every guess, linked to the RE question that would close it
    CLEAN-ROOM.md       the rule below
  LICENSE               GPL-3.0-or-later
  .gitignore            blocks every game file type (already in the remake)
```

- **Licence: GPL-3.0-or-later**, as the remake already has and as OpenMW, OpenRA and Open76 use. It keeps forks open.
  MIT is the alternative if the family wants others to reuse the code anywhere; Godot (MIT) allows either.
- **No game data, ever.** The program asks for the folder of the player's own copy (GOG works) and reads it
  read-only, like OpenMW, OpenRCT2, Julius, OpenRA, fheroes2. The `.gitignore` blocks game file types; CI cannot run
  the data tests on GitHub's machines, so data tests run on the owner's PC (a self-hosted runner, or by hand).
- **Clean room.** The remake's rule continues: code is written from the prose specs in i76-map and i76-everywhere,
  never from disassembly or decompiler output. RE questions go to i76-map; answers come back as prose. This is the
  separation `docs/SCOPE-AND-LEGITIMACY.md` relies on.
- **Name and trademarks.** "Interstate '76" is Activision's trademark. Use it descriptively ("a reimplementation of
  the Interstate '76 engine; requires the original game"), with a not-affiliated line, as the remake's README does.
- **Accounts.** GitHub requires users to be 13 or older; the repository can live under James's account with Michael
  as a collaborator either way.

## 8. Risks

| risk | what it looks like | what we do |
|---|---|---|
| The port feels "close" but not right | months of tuning by feel | Only the fingerprint and traces decide; remembered feel is not evidence (owner ruling) |
| Rebuilding what exists | a second loader, a second physics port | Read section 1 first; copy, do not re-derive |
| Remake claims do not hold on a fresh run | tests fail on a new machine or a Mac | Phase 0 re-runs everything before new work |
| GDScript too slow later | frame drops with many cars | The remake already plays whole missions headless faster than real time (`--speed=N`); hot spots can move to C# or a GDExtension (C++) without changing the design |
| Engine upgrades break things | Godot 4.x minor versions change physics defaults (4.7 changed Jolt details) | Our sim does not use the engine's physics at all; pin the Godot version in the README |
| Motivation | a big project stalls | Visible milestones (Phase 1 is driving on day one), a game night with the family once a phase lands |
| Legal | a shipped asset slips into git | `.gitignore` plus a pre-commit check that refuses game file types |
| Activision objects | takedown request | No assets, clean-room code, descriptive naming; the same posture as the long-lived projects above |

## 9. Open questions for the family

1. **What does Michael want most: to learn Unreal, to make I'76 playable everywhere, or to make his own game?**
   That picks between options C, A and D.
2. **Start from the remake, or start empty?** (A or B.) The remake is the family's own work, never published.
3. **Faithful only, or faithful plus modern options?** For example, arcade physics, widescreen, new HD models. The
   gold standard stays the default either way.
4. **Which look is "the original": Glide (smooth textures) or software (sharp pixels)?** Or a switch.
5. **Is multiplayer in scope, and only on the home network, or online too?**
6. Licence: GPL-3.0 (forks stay open) or MIT (anyone may reuse, even closed)?
7. Public from day one, or private until Phase 1 passes?
8. Is the Nitro Pack (its missions and cars) in scope?
9. Who owns RE questions the port raises: the i76-map track as now, or Michael?
10. The repository name.

## Sources

1. Epic Games, Unreal Engine licence and royalty reporting: <https://www.unrealengine.com/en-US/license>,
   <https://www.unrealengine.com/en-US/news/unreal-engines-improved-royalty-reporting-system> (5 % above $1M lifetime
   gross per product; Epic Games Store sales exempt; no royalty in a quarter under $10,000). The licence page
   refused automated fetch on 2026-10-17; terms quoted from search results of Epic's pages.
2. Unity, "Changes to Unity subscription plans and pricing": <https://unity.com/products/pricing-updates> (Personal up
   to $200K revenue and funding; Pro and Enterprise +5 % from 2026-01-12; Havok no longer bundled from 6.3);
   runtime-fee cancellation: <https://www.notebookcheck.net/Unity-cancels-Runtime-Fee-before-controversial-pricing-structure-even-goes-into-effect-in-Unity-6.887828.0.html>.
3. Godot licence (MIT): <https://godotengine.org/license>; Jolt default from 4.6 and 4.7 changes:
   <https://godotengine.org/releases/4.6/>, <https://docs.godotengine.org/en/4.7/tutorials/migrating/upgrading_to_godot_4.7.html>.
4. Unreal on Apple silicon: <https://www.unrealengine.com/en-US/tech-blog/unreal-engine-5-2-brings-native-support-for-apple-silicon-and-other-developments-for-macos>;
   current Xcode 26 / UE 5.8 table: <https://dev.epicgames.com/documentation/unreal-engine/ios-ipados-and-tvos-development-requirements-for-unreal-engine>;
   hardware specs: <https://dev.epicgames.com/documentation/en-us/unreal-engine/hardware-and-software-specifications-for-unreal-engine>.
5. Unity 6 system requirements (Apple M1+ editor; Ubuntu editor): <https://docs.unity3d.com/Manual/system-requirements>.
6. Godot macOS export (Universal 2, Intel + Apple silicon): <https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_macos.html>.
7. Bevy 0.20 (2026-10-08): <https://bevy.org/news/bevy-0-20/>.
8. Prior in-repo engine decision (Godot vs Unity vs Unreal): `C:\Users\james\time-vigalantes\docs\engine-decision.md`.

Not verified here: exact Unreal and Unity install sizes ("tens of GB", "several GB" are typical figures, not measured
on this PC); Unity Steam Deck specifics; the Godot 4.7 release date.
