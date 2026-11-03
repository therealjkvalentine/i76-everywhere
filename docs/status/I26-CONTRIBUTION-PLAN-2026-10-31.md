# Contributing to I26: what we have that it needs, in the order to offer it

Status 2026-10-31. **I26** ([github.com/vahokif/I26](https://github.com/vahokif/I26)) is a from-scratch reimplementation of
Interstate '76 in Godot 4.7 / C# (.NET 8), open-sourced today with v0.11.0. The owner's direction: this project's work moves
into I26 over time, so the family can play the Godot version together and the two efforts stop duplicating each other.
This document is the plan: a deep comparison of the two code bases and a prioritised list of fixes and enhancements to
offer I26, starting with small changes that are easy to understand and easy to accept, and building up. It is written to be
carried into the I26 work as the running checklist. Companion: [REMAKE-RE-HANDOVER-2026-10-18](../records/REMAKE-RE-HANDOVER-2026-10-18.md)
(the earlier handover to a Godot remake; its "do not carry over" list still applies).

How this was produced: a read of I26's charter, contributing guide, agent notes, docs (frame-rate, deviations, joystick,
multiplayer, playing) and source (784 C# files, about 161k lines), its 141 GitHub issues and 12 releases; and an inventory of
this project's records, specs, parsers and tools classed by portability (knowledge / portable logic / proxy-only hack).

## 0. The short version

1. **I26 already has nearly everything the Patch Kit advertises.** Fixed simulation step with interpolated drawing, a
   simulation-rate setting, Hor+ widescreen, a 20 km draw distance with morphing terrain LOD, a rear-view mirror, menus with
   a modern mouse, GOG music remapped, gamepads with dead zones, a map editor, and a multiplayer stack (server-authoritative
   UDP, prediction, host migration, bots, network co-op, lobby servers with hole punching) far beyond ours. Do not propose
   any of these. Our 120 fps / widescreen / draw-distance / menu work stays where it is, as the patch for the original exe.
2. **What I26 does not have, or has not been able to check, is exactly what we have:** real hardware on Windows (wheels,
   flight sticks, pads), Macs, a Steam Deck, and the habit of measuring the original exe on real machines. I26's own docs say
   "no Windows machine, no real stick", "macOS build unsigned and untested", and its charter accepts simulation code only
   when it "reproduces traces recorded from the real game". Our frame-exact replay, telemetry, emulated-1997-hardware traces
   and byte-exact format work are that currency.
3. **Features we can add that it lacks:** head tracking (opentrack), real force feedback for wheels (I26 has pad rumble only),
   importing original GOG save games (I26 has its own save format), and a few named file-format fields it still lists as unknown.
4. **The maintainer's style is terse, measured and fast** (a release every 2 to 3 days; "could you check this in the
   original?"; gameplay deviations declined unless they are bugs; no pull request has ever been opened against the repo, so
   ours set the precedent). We go in small, with evidence, one change per PR, and wait for feedback before the next.

## 1. What binds us in I26 (read before touching anything)

From `CHARTER.md`, `CONTRIBUTING.md`, `AGENTS.md` and the way the issues went:

- **Clean room.** I26 ports only from its maintainers' own reverse-engineering notes. We never paste decompiler output,
  byte tables lifted from the exe, or our proxy's patch code. We contribute *measurements*, *behaviour descriptions*, *tests*
  and *C# written for I26*, and we say how each fact was obtained so the maintainer can check it against his own notes.
- **No game data anywhere**: not in the repo, not in issues, not in PRs. No files, extracted art, screenshots of game art, or
  text copied from the game. Tests that need the game read `I76_INSTALL` and skip without it.
- **Faithful by default.** A gameplay change needs evidence from the original. Every deliberate difference sits behind an
  option and gets one row in `docs/deviations.md`. Rendering may be better than 1997; the simulation may not differ silently.
- **Measured, not assumed.** Simulation code is accepted when it reproduces traces of the real game.
- **Unknown fields keep their offset as their name** (`Unk_0x38`); open questions are not guessed at in the code.
- **The sim is deterministic and Godot-free** (`src/I76.Sim`); presentation lives in `game/`. New sim state must be
  serialised (the snapshot guard test enforces it; bump `SnapshotHeader.CurrentVersion`); any wire change bumps the protocol
  version in `src/I76.Net/Protocol.cs`.
- **The tick is a setting** (20 Hz default = 102/2048 s; also 25, 28, 30, 40, 60). Never exactly 0.05 s.
- **Workflow:** one change per branch, `dotnet build I76.sln && dotnet test I76.sln`, visual changes checked in both looks
  (modern and `--1997`), one logical change per PR with a description of how it was checked. Comments brief and factual, in
  the style of the surrounding code. No TODO / FIXME markers (the code base has none). Default branch is `master`. CI runs
  the tests on Ubuntu and Windows without a game install.
- **Issues:** one concrete problem each, with the I26 version, the look, a log (`godot.log`), and "what the original does".
  Reports with numbers measured in the original get the fastest fixes. The maintainer declines gameplay-balance proposals.

Our own rules on top: the public-repo privacy rule (no names, machine names or private paths in anything we post); never
more than one or two PRs open at once; a PR waits for a reply before we open the next on the same area; if the maintainer
disagrees, we measure again or drop it, we do not argue.

## 2. Side by side: what each project has

| Area | I26 (v0.11.0) | This project | Verdict |
|---|---|---|---|
| Simulation step | fixed tick, offered 20 (default) 25 28 30 40 60 Hz; per-frame rules of the original run per tick; the 20 fps delta sequence (102/103 quanta) reproduced | whole-sim tick 41.667 ms in the proxy, chosen from measured jump and chassis behaviour; the 1997 "one clock" model established the same way | same model, different default; see s.5.1 |
| Drawing between steps | interpolated poses | interpolated poses (proxy) | I26 has it |
| Widescreen / FOV | Hor+ (73.7° vertical = the original's 90° at 4:3) | Hor+ patch, owner-approved at 21:9 | I26 has it |
| Draw distance / terrain | 20 km, 3-level chunk LOD morphing in the vertex shader, horizon ring, sky fade | 2.3 km with a geomorph on the original quadtree | I26 is ahead; our pop/morph measurements are only confirmation |
| Mirror | redrawn every frame (modern), the original's 256x64 at half rate (1997 look) | software mirror to 1 km with the main view's textures | I26 has it |
| Menus / shell | the original front end rebuilt, 4:3 scaled, mouse and pad driven, HD packs, 3D garage | mouse-coordinate fixes for the original shell | not applicable |
| Music | GOG mp3s remapped to disc tracks; `I76_MUSIC_SEQUENCE=retail|gog`; no CD | MCI-to-mp3 proxy; retail 1.0 sequence + resume measured | I26 has it; our retail-sequence notes may add a row (s.4, item 2.6) |
| Multiplayer | UDP server-authoritative, prediction, delta snapshots, host migration, bots, co-op story missions, Nitro race/CTF, anet lobbies, CB voice | IPX/ANet of the original + AI fill, co-op chain, relay spike | I26 is far ahead; nothing to bring except NAT-relay experience (s.4, tier 4) |
| Controls | input.map read/write, rebinding screens, pads with radial dead zones, generic sticks raw, hat/button split via winmm or joydev | WASD layout, pad shift layer, T300RS and CH Fighterstick layouts, key sheet | I26 has the system; it has never been run on real sticks or on Windows hardware |
| Force feedback | the original's I7_SFRCE logic and .FRC effects, output as **two-motor pad rumble only** | DirectInput wheel FFB: 14-channel mixer, measured stock effects, design library, live tuning page | **gap**: wheels |
| Head tracking | none (pad right-stick free look; mouse camera) | opentrack head look with glance override and ease-back | **gap** |
| Saves | own format (bookmarks.cfg, JSON car, binary snapshots); original `.sav`/`.cmp` not read | savegame.dir and saveNNN.cmp byte-exact, editor verified on 46 saves | **gap**: importing a GOG campaign |
| File formats | readers for every format the game needs; writers for missions; fields still named `Unk_` in .geo, ODEF, WRLD, parts | 43 format families, 6,368 files round-trip with 0 byte diffs; 95.3 % of parsed bytes cited to a reading instruction, 4.3 % proven unused | we can name or close several `Unk_` fields (s.4, item 1.4) |
| Mission scripting / AI | FSM VM, the Ptable tactics read from the exe, planners; `setUserRadar` logged as unhandled | FSM spec (14 opcodes, 96 actions, all 40 missions round-trip), AI spec, measured AI fire baselines | I26 has it; one small gap (s.4, item 3.5) |
| Platforms | Windows, Linux x64/arm64, macOS universal (untested), OpenGL fallback | Windows kit, Mac via Wine, Steam Deck kit | **gap**: Mac and Deck verification |
| Testing the original | Wine with a fixed-step hook, traces at 15-59 fps on one reference machine | frame-exact replay (bit-exact), telemetry, 86Box P166/P133 memory traces (49 traces, 219 metrics), Windows 10 captures | **our strongest asset** |
| Nitro Pack | full support | ported fixes for the original | not applicable |

## 3. Our assets, classed for I26

- **A. Measurement.** Frame replay of the original (0 mismatches in 8 replays, LAB-FRAME-REPLAY), telemetry over UDP and
  shared memory, the gold-standard fingerprint of retail 1.0 on an emulated P166 (GOLD-STANDARD-FINGERPRINT), the
  two-clocks study (TWO-CLOCKS-2026-10-19), the per-frame audit, the collision-sweep miss rate, weapon timing (MG-STUTTER),
  the T05 jump and T06 strip reference rows. Plus real Windows 10 machines, a laptop bench and family testers.
- **B. Hardware.** A T300RS wheel, a CH Fighterstick, XInput pads, Apple Silicon and Intel Macs, a Steam Deck (LCD), a
  21:9 and a 1080p display.
- **C. Portable logic (to be rewritten as C#).** opentrack head look (modes, glance override, 150 ms ease-back), the FFB
  mixer and effect design, the save-file layout and editor rules, the Steam Input layout, the key-sheet generator.
- **D. Format knowledge.** FORMATS.md (byte-exact, with the reading instruction for each field), FSM.md, VEHICLES.md, the
  mass formula, the surface records, the far-clip field, the ODEF bytes the engine never reads.
- **E. Bug catalogue of the original** (40 entries; VERIFIED-FIXES and the records), useful to a faithful port as "bugs you
  may have copied": the health-fraction x100, the camera-under-terrain skip, the mirror's doubled sky scroll, the collision
  sweep once per frame, the fire timer's dropped remainder, GOG's music order, the Nitro listener volume, and so on.
- **Not for I26 (proxy-only):** everything in `music-fix/` that patches addresses, dgVoodoo / DxWnd / DXVK tuning, the
  launchers and kits, shell byte patches, the trainer's memory writes, the AHK remappers as such. Their *ideas* travel; their
  code does not.

## 4. The prioritised list

**Owner direction (2026-11-01): lead with reported bugs; the clock comes last.** The community has played at 20 fps
for years and is convinced it is right, so 2.1 and the "AI gain at 28 fps" pattern (fast-rate patches that exist only
because the sim may run faster than 1997 machines did) wait until much later, and are raised simply, as an option,
obliquely. Lead instead with fixes for bugs players reported, or would report: each one change that follows from
our reading of the original (a spec citation plus a deterministic test), preferably one root-cause change that fixes a
family of symptoms. Verify against current I26 code first: open issues are often fixed already (#71's smoke is).

Each item: what, why I26 would take it, size (S under a day, M a few days, L weeks), the evidence we bring, and the shape of
the contribution. Tier 1 goes first and small; nothing in tier 3 is opened before at least two tier-1 PRs are merged and we
have a feel for the review.

### Tier 1: things the maintainer has said he cannot do himself (first two weeks)

| # | Item | Size | Why they take it | Shape |
|---|---|---|---|---|
| 1.1 | **Real-hardware verification of generic sticks and wheels on Windows.** Run I26 with the T300RS, the CH Fighterstick and an XInput pad on Windows 10; record the raw axis and button numbers Godot/DirectInput gives each (the doc predicts "X, Y, Z, Rx, Ry, Rz, then sliders; hat as buttons 11-14"), whether `NativeSticks` (winmm `joyGetPosEx`) splits the hat from button 12, and whether the Joystick Configuration screen binds throttle, steer and look correctly. Fix what is wrong; add a test in the style of `GenericJoystickTests`. | S-M | `docs/joystick.md` says in three places that this is untested: "no Windows machine, no real stick". Zero design risk: it fills in their own table. | one issue with the measured table first; then one PR per fix, each with its test, and a PR that turns the doc's "not verified" rows into verified ones |
| 1.2 | **macOS: run the shipped build on a real Mac and make the docs true.** The 0.11.0 `-macos.zip` is universal and signed ad hoc, "unsigned and untested". Run it on Apple Silicon and on Intel: Gatekeeper (what the player must do to open an unsigned app), the microphone prompt (the CB radio), the Local Network prompt (LAN discovery), MoltenVK behaviour, performance in both looks, where user data lands. Report; fix the playing.md macOS lines; propose export-preset changes if any are needed. | S | They have no Mac. This is also the family's route to playing I26 together (a family member plays on a Mac). | an issue with the report, then one docs PR |
| 1.3 | **Steam Deck: run the Linux build in Game Mode and write the Deck section.** Install the `-linux.zip` as a non-Steam game on the Deck, check the controller (Godot sees the Deck as a pad), rumble (I26 rate-limits rumble for Bluetooth pads; the Deck's is wired), performance per look, the 1280x800 picture and the shell's 4:3 frame, the on-screen keyboard for text entry. Answer issue #129's Deck question with the result. | S | #129 asks and has no maintainer reply. Our Deck kit work (DECK-2026-10-25) is the experience. | a comment on #129, then a short "Steam Deck" subsection in `docs/playing.md`; a Steam Input layout only if the default pad mapping is not enough |
| 1.4 | **Name or close the `Unk_` fields we have evidence for.** (a) `WorldSettings.Unk_0x137` is the mission far clip, read as a float and clamped 100..100000 (600 in every mission, 150 in menus and at lowest detail); I26 already treats 600 as "the original's clip" in its Draw Distance setting. (b) `WorldSettings.Unk_0x97`: I26 reads it as 8 surface records (grip, rolling, bump, `Unk_0x0c`, damage); our reading agrees and finds the fourth field unread by the engine. (c) `PlacedObject.Unk_0x38` (ODEF +0x38..+0x5b, 36 bytes): no instruction in the exe reads them (we re-use them for our own tagging in the co-op mission builder, which the game accepts). (d) `GeoFace.Unk_0x00` is a BSP node id the engine ignores and rebuilds at load; the .geo header's `Unk_0x04` / `Unk_0x20` are never read. (e) `TacticsTable` / ODEF team field: copied into the object record, no reader found (we have the same open question). | S | Charter rule 3 wants facts, and "proven unread" is a fact a port can use. Each claim comes with how we established it (which reading instruction, or the absence of one across the exe) so the maintainer can confirm in his notes. | one issue listing the five facts with their verification method; PRs only for the ones he accepts (rename + a one-line comment, tests unchanged) |
| 1.5 | **Fidelity checks that cost us nothing: run I26's headless CLI against our measured rows.** `dotnet run --project tools/I76.Cli -- run t05 ...` and the T06 strip: 0-10 m/s in 1.168 s, 0-20 m/s in 4.183 s, 201.5 m in 10 s, brake 25 to 5 m/s at 11.88 m/s², steady yaw at 24 m/s 1.117 rad/s; the T05 crest placed at 56 m/s: take-off 51.6 m/s, apex 10.66 m, 227.6 ± 28 m (retail 1.0 on the emulated P166 at its own frame times, n 5-10). Compare at the matching simulation rate. File only the discrepancies, each as one issue with the numbers and the method. | S | This is the report style that got the fastest fixes (#4 mortar range, #17 flame damage). Agreement is also worth one line: it is independent confirmation from a second RE. | issues, not PRs |

### Tier 2: measured facts about the original worth a conversation (weeks 2 to 4)

| # | Item | Size | Evidence | Shape |
|---|---|---|---|---|
| 2.1 | **What a "20 fps" GOG game really steps at on Windows 10.** I26's 20 Hz default models the reference machine's clock (frames of 102 or 103 quanta of 1/2048 s, so 49.8/50.3 ms; two frames in five take two 25 ms substeps). On Windows 10 GetTickCount moves in 15.625 ms steps, so under GOG's I76PATCH 20 fps cap a frame reads 46.9 or 62.5 ms; the 62.5 ms frames are cut in two: a substep stream of 46.9 ms (about 80 %) or 2 x 31.25 ms, 24 substeps a second, mean 41.7 ms (WHAT-IS-STOCK; capture 014, 2026-09-27). I26's own §5.1 shows the physics follows the substep size, so the two sequences are not the same car. I26's doc also says the GOG patch's limiter "runs at 60 fps with focus and 20 without"; we measured 20 with focus. | S to raise; M if a rate is added | our capture plus a fresh one with their method (`fps-drive` style, m01, straight throttle) on a Windows 10 GOG install, the delta sequence listed | one issue: the measurement, the method, the offer of more traces; if he wants it, a PR adding an offered rate (85/2048 s = 41.5 ms, "GOG on Windows 10" or "24") with its frame sequence, in the pattern of `SimRate` and `SimRateTests` |
| 2.2 | **The health-fraction bug.** `object_HealthFraction` drops the x100: a scratched car reads under 1 % where 49.6 % was meant; it feeds the AI's flee decision, the script's `hpLesser`, the smoke threshold and the target bracket colour (HEALTH-BAR-COLOUR, measured stock 0.99 vs 49.6). A faithful port reproduces it. | S | measured in the original and in our fix | one issue asking whether I26 copies it, with the numbers; the fix would be a deviations row behind an option, his call |
| 2.3 | **Collision sweep once per frame, not per substep.** At short steps the original misses rams: stock T05 barricade rams hit 9/43 against 21/21 with the window widened (BASE-DECISION-1.0-vs-GOG). At I26's 40 and 60 Hz a faithful port misses the same way; at 20 Hz it does not. | S | measured | one issue, for the 60 Hz players' benefit; no PR unless asked |
| 2.4 | **The mirror advances the sky scroll a second time**, so clouds in the mirror move at twice the speed (x1.5 in Nitro; skymirror.c header, measured). I26's 1997 look redraws the mirror at the original's rate; check whether it copied the double advance. | S | measured | issue or a one-line PR if it did |
| 2.5 | **Weapon timer details to cross-check**: the strict `dt <= interval` compare and the under-10 ms remainder drop are both in I26's `Combat.Timing` already (their §2 matches our MG-STUTTER s.1.1); the MG per-frame batching with catch-up `max_dt_left/3` and the 24 Hz "gallop" (2, 3, 2, 3 ticks) are worth a look at their 25 Hz rate. | S | static plus replay model | a comment, no issue unless the port differs |
| 2.6 | **Retail 1.0 music behaviour.** The 1997 build plays from the mission's disc track to the end of the disc, no shuffle; the shell plays track 13 (CD 15), credits 8 (16); GOG's `music\N.mp3` are out of disc order for four tracks; T16 and S01 differ between the CD and GOG (MUSIC-TRACK-MAP, MUSIC-RETAIL-INTENT). I26 has `I76_MUSIC_SEQUENCE=retail|gog`; compare the tables. | S | static | an issue only if the tables disagree |
| 2.7 | **Developer intent, for the record.** Dev Game Club episodes 422-427: "designed to run at 15 frames per second", suspension filters "resonate at 15 hertz", fine between 10 and 30 Hz (DEV-INTENT-EVIDENCE, medium confidence). I26's #57 thread ends with "there isn't really a perfect number". Offer the citation for `frame-rate.md`'s §1. | S | relayed testimony | a docs PR of two sentences, if he wants it |

### Tier 3: features I26 lacks, each behind an option with a deviations row (month 2)

| # | Item | Size | Design in one paragraph | Shape |
|---|---|---|---|---|
| 3.1 | **Head tracking from opentrack.** A UDP listener (opentrack's "UDP over network" output: six doubles, x y z yaw pitch roll, default port 4242; cross-platform, unlike the FreeTrack shared memory our AHK uses) feeding the in-car free look that the pad's right stick already drives. Rules from HEAD-TRACKING.md: yaw and pitch scaled to the cockpit's look range (the pad path already allows 80° each side), any glance key or stick input overrides it, and it eases back over 150 ms (smoothstep) when tracking stops. Presentation only: no sim state, no snapshot or protocol change. Off by default; a Play Options row and a port setting. | M | `game/Scripts/Input/HeadTracker.cs` + the hook where the right stick's look is read (deviations row "In-car free look (pad)"); a test for the packet decode and the ease-back; checked in both looks | one issue proposing it (one paragraph) before writing it; then one PR |
| 3.2 | **Force feedback for wheels and sticks on Windows.** I26 already runs the original's I7_SFRCE logic and parses the `.FRC` effects per tick, but its only sink is two-motor rumble (`IRumbleSink`, `GodotRumble`). Godot has no wheel FFB API, so the sink is a DirectInput 8 force-feedback device driven from C# (P/Invoke, no native build step): constant force for impacts and the engine, periodic for the weapons at their own rates, a spring at centre. First version: a faithful sink that plays the original's effects as the SideWinder driver did (the deviations row "Force Feedback" describes them); our 14-channel mixer (slip makes the wheel go light, road texture, scrub) comes later as a separate option if wanted. Our FFB-DESIGN-LIBRARY has the DirectInput effect model and the T300 specifics; FFB-FOCUS and FFB-LAPTOP-RECON have the two crash modes of the original's DLL to avoid. | L | `game/Scripts/Input/DirectInputForce.cs` behind "Force Feedback: Wheel (Windows)"; Linux later through SDL3 haptics if Godot exposes it | design issue first; expect iteration |
| 3.3 | **Import original save games.** Read `savegame.dir` (u32 count + 60-byte records: scene, name[32], file[16], state) and `saveNNN.cmp` (GarageRec 0x8c4, the inventory ring of 0x74-byte records, the repair queue; part states 1 mounted / 2 van / 3 repair / 4 salvage) into I26's bookmarks and trip car. Byte-exact on 46 saves (SAVE-FORMAT-GAPS, the save editor's 156 tests). Lets a GOG player carry a campaign into I26, which matters for adoption and for our own family. Formats layer (no Godot, testable with `I76_INSTALL`), plus an "Import GOG saves" button on the bookmark screen. | M | `src/I76.Formats/Save/OriginalSave.cs` + a shell action; tests skip without an install | design issue first (how the maintainer wants the trip car mapped), then one PR for the reader, one for the UI |
| 3.4 | **`setUserRadar` and `start_engine`.** FSM action 78 toggles the player's radar (our FSM.md row 78, 0x41421b); I26 logs it as "not yet handled" (it is Nitro-only and unused by shipped missions, so it only matters for custom maps). `start_engine` in `CarInput` is read by nothing in I26; in the original the ignition is a one-frame pulse (FIX-INVENTORY s.4). | S | one PR each with a test; `setUserRadar` adds sim state, so the snapshot version bumps | low value, do them when passing |
| 3.5 | **Steam Deck layout and polish** after 1.3: a Steam Input layout if needed (ours: left trackpad quick-select, right trackpad menu pointer), rumble feel, text entry. | S-M | files under `docs/` or a `deck/` folder as the maintainer prefers | after 1.3's reply |
| 3.6 | **Printable key sheet from `input.map`.** Our generator (tools/controls-sheet) builds a 4-page sheet and fails the build when the sheet and the map disagree. Rewritten against I26's `InputMapFile`. | S | a `tools/` script or a CLI command | only if asked; low |

### Tier 4: longer term, only with the maintainer's interest

- **A trace library from 1997 hardware.** Our 86Box runs of retail 1.0 on an emulated P166 and P133 (EMU-MEMTRACE, HARDWARE-MATRIX)
  can be re-run to produce traces in I26's own format (`M.CSV`-style deltas and controls) for its §6 test plan: the same
  missions at the frame times those machines really had (26.8 to 34.7 ms steps, 28 to 37 fps). This answers "what did 1997
  feel like" better than any cap. Needs his format and his say-so.
- **Multiplayer edges from our relay spike** (INTERNET-RELAY-SPIKE): a relay for symmetric NAT / CGNAT is on I26's "left for
  later" list; UPnP too. Experience, not code.
- **German voices overlay and extra-music shuffle** (our musicextra / voices logic): small, optional, probably not wanted.
- **Localisation and accessibility**: I26 has neither; neither do we. Noted so nobody proposes it as "ours".

### What we do not bring

The proxy (`music-fix/`), the 20 Hz grid switches, dgVoodoo / DxWnd / DXVK confs and presets, the launchers and kits, the
shell byte patches, the trainer, the AHK remappers, our LAN AI fill and co-op chain (I26 has bots and network co-op), our
IPX relay, and our 120 fps / widescreen / draw-distance / menu fixes, all of which I26 already does in its own way. Also
nothing from the exe: no byte tables, no decompiled routines, no addresses in code comments (addresses may appear in an
*issue* as "how we found it", never in a PR).

## 5. Disagreements and open measurement questions

1. **The default simulation rate** (tier 2.1). I26: 20 Hz at 102/2048 s because "the community plays at 20". We: the GOG
   limiter on Windows 10 produces a 46.9 / 2x31.25 ms substep stream (mean 41.7 ms), and the 1997 machines stepped at 27 to
   48 ms, never 50 or more. Neither project claims a single right number (I26's maintainer said so in #57; our WHAT-IS-STOCK
   says every cap was added later). The resolution is a measurement with their method on our hardware, offered, not asserted.
2. **What I76PATCH.DLL does.** I26: 60 fps with focus, 20 without. We: 20 fps with focus (played that way until 2026-10-03,
   capture 014). Possibly two builds of the DLL (GOG's vs the AiO patch's). Measure both before saying anything.
   *2026-11-03: half settled. GOG's installer has no `I76PATCH.DLL` (a full extraction of 2.1.0.17, 458 files, the
   Nitro pack's 7,313, and two GOG test installs the kit was applied to: none, renamed or not), so there is one DLL, the AiO
   patch's; `stock.psd1`, the kit README and the installers' messages now say so. Its 60-vs-20 behaviour is still
   unmeasured.*
3. **Suspension model.** Our HANDLING-MODEL.md says "no suspension model"; our later TWO-CLOCKS found a second-order filter run
   once per substep (period 15 calls, pole 0.7). Trust TWO-CLOCKS. I26 ports the vehicle step from the code, so it has the
   filter; our note is only that its tempo scales with the step (heave half-period 0.233 s at 33 ms vs 0.292 s at 42 ms).
4. **P166 vs P133 reference** (owner ruling pending on our side) and the untraced T06 ramp shortfall: ours to settle before
   we cite either as "the 1997 feel".

## 6. How we work in their repo

For the owner and for agents briefed on I26 work:

1. **Set-up:** .NET 8 SDK, Godot 4.7.x .NET, `I76_INSTALL` pointing at a GOG install we own; `dotnet build I76.sln && dotnet
   test I76.sln` green before any change. Keep I26 in its own checkout, one git worktree per change
   (`git worktree add ../i26-wt/NAME -b fix/NAME master`), as their AGENTS.md says.
2. **Order of work:** tier 1 before tier 2 before tier 3. One or two PRs open at a time. A tier-3 feature starts as an issue
   with a one-paragraph design and waits for a reply.
3. **A PR** is one logical change, with a test for every bug fixed and every rule implemented, a description of how it was
   checked (commands, hardware, both looks), no game data, comments in their style, no TODO markers, `Unk_` names kept unless
   the PR is the one that establishes the meaning. Sim changes: deterministic, serialised, snapshot version bumped. Wire
   changes: protocol bumped. Deviations: one row, with the option.
4. **An issue** is one problem, with the I26 version, the look, the log, the steps, and what the original does, measured. We
   offer to retest. We cite our records by name and say how a number was obtained; we do not paste exe bytes or addresses into
   their code.
5. **Tone:** short, factual, deferential to how they have things organised. Their design decisions (the sim/presentation
   split, the tick as a setting, Godot-free sim, their save format) are not up for debate from our side. If a measurement of
   ours contradicts a line in their docs, we present the measurement and the method and let him decide.
6. **Lanes:** Fable plans and writes the issue or design text; Opus implements in C# against their tests; Sonnet runs the
   hardware and platform verification matrices and writes the tables. Every brief forbids game data in the output and names
   the one problem the lane is on.
7. **Privacy:** nothing we post names a person, a machine or a private path. Family testers are "a tester on a Mac".
8. **Our own repo:** this file is the checklist; tick items here with the I26 issue or PR number and date. Records of the
   measurements we make for I26 go in `docs/records/` as usual and are linked from the issue.

## 7. Checklist

Tier 1
- [ ] 1.1 Windows real-hardware stick/wheel/pad table (issue), then fixes (PRs), then joystick.md rows
- [ ] 1.2 macOS run on Apple Silicon and Intel (issue), playing.md PR; a family member's Mac is the first target
- [ ] 1.3 Steam Deck run (comment on #129), playing.md Deck subsection
- [ ] 1.4 `Unk_` facts issue (0x137 far clip, 0x97 surface records, ODEF +0x38 unread, .geo unread fields, team field)
- [ ] 1.5 Headless CLI against our T05 / T06 reference rows; issues only for discrepancies

Tier 2
- [ ] 2.1 GOG 20 fps on Windows 10: fresh measurement with their method; issue; rate PR only if wanted
- [ ] 2.2 Health-fraction x100 issue
- [ ] 2.3 Collision sweep per frame issue
- [ ] 2.4 Mirror sky-scroll check
- [ ] 2.5 Weapon timer cross-check (comment)
- [ ] 2.6 Music tables cross-check
- [ ] 2.7 Developer-intent citation (docs PR if wanted)

Tier 3
- [ ] 3.1 opentrack head tracking (design issue, then PR)
- [ ] 3.2 Wheel force feedback on Windows (design issue first)
- [ ] 3.3 Import GOG saves (design issue first)
- [ ] 3.4 setUserRadar / start_engine
- [ ] 3.5 Deck layout and polish
- [ ] 3.6 Key sheet generator (only if asked)

Before any of it
- [ ] Build and test I26 on a Windows machine of ours; play a mission in both looks; read `docs/deviations.md` end to end
- [ ] Owner ruling: P166 or P133 as "the 1997 reference" when we quote numbers to I26

## 8. Progress log

**2026-11-01, tier 1.2 (macOS), from an earlier owner session on the family Mac (2026-10-28).** I26 0.9.0 macOS zip
(sha256 checked) on Apple Silicon, macOS 26.6.2, game files copied from the Gold and Nitro wrappers into `i76/` and
`nitro/` beside `I26.app`. Clearing the quarantine flag was not enough: the app was killed at launch (SIGKILL,
"Launchd job spawn failed") although its ad hoc signature verified. Re-signing locally with the same ad hoc identity
and the entitlements dumped from the shipped app fixed it
(`codesign --force --deep --options runtime --entitlements <dumped.plist> -s - I26.app`); the game then reached the
in-game view. Not yet checked: menus, controls, audio, the Nitro Pack, Intel Macs, and whether 0.11.0 has the same
launch failure. This is the first concrete item for the macOS issue: the release's signing step, reproduced on 0.11.0
first, with the exact error and the re-sign that works.

**2026-11-01, tier 1.2, 0.11.0 on the same Mac (Apple Silicon, macOS 26.6.2): reproduced, and the cause found.** The
shipped app (sha256 checked; downloaded with curl, so no quarantine flag) is SIGKILLed at launch: `open` fails with
"Launchd job spawn failed" (NSPOSIXErrorDomain 163), `codesign --verify --deep --strict` passes, `spctl` rejects (as
for any ad hoc app). Re-signing with Apple's `codesign` and the same entitlements makes it run. Ruled out: the code page
size (re-signed with 4 KB pages, as shipped, it runs too). The difference that remains is the DER-encoded entitlements
blob that Godot's own signer writes (release.sh: "ad-hoc signed by Godot; checked without a Mac"):
- Apple's: `70 82 01 0a 02 01 01 b0 82 01 03 ...` = [APPLICATION 16] { INTEGER 1, [CONTEXT 16] { SEQUENCE { UTF8String
  key, BOOLEAN ff } ... } }, minimal lengths, keys sorted, TRUE = ff (270 bytes).
- Shipped: `31 82 01 21 30 82 00 28 0c 82 00 1f ... 01 82 00 01 01` = a bare SET with no application wrapper and no
  version, every length in the long form, TRUE as 01, keys in file order (293 bytes). Not valid DER; macOS validates
  this blob at exec, so the kill.
Fix options for I26: sign the macOS export with a signer that writes Apple's form (rcodesign runs on Linux), or an
upstream Godot fix; plus a release.sh check that the entitlements blob starts `70 ..  02 01 01 b0`. Worth checking
upstream Godot's codesign for an existing report first. Functional run after the re-sign (Metal 4.0 Forward+, M-series):
T05 modern 8.2 ms CPU per frame median (p95 9.2-9.9), 1997 look 8.6 ms, Nitro front end renders; the gpu.* timings read
0 under Metal; one 205-235 ms hitch at the screenshot frame, one 3 s mission-build hitch behind the loading card.
Still needs a person: the normal launch window, controls, audio, CB microphone prompt, driving.

**2026-11-01, tier 1.3 (Steam Deck).** Harness ready, not run: the Deck was off. Native Linux build chosen over the
Windows build under Proton (the build the maintainer ships and can act on; Proton as an optional comparison run). The
lab harness (`i26-deck/` in the lab repo) installs 0.11.0 into its own folder, unpacks both GOG offline installers with
I26's own unpacker, and boots T05 in both looks plus Nitro with I26's frame profiler, two runs each; a Game Mode
checklist covers what needs a person (controls, rumble, on-screen keyboard, suspend, feel, battery).

**2026-11-01, first PR opened: vahokif/I26#144** (macOS launch fix, branch `fix/macos-entitlements-der` aef8758, from the
developer's fork). Godot 4.7.2's signer writes long-form DER entitlement lengths that macOS 26 refuses at exec; the
release re-signs with rcodesign and the bundle check now rejects that form. Checked on the Mac: shipped 0.11.0 fails
spawn (163); the branch build launches from a quarantined-then-cleared download. Mic-prompt docs PR + issue next.


## 9. Fidelity audit, 2026-11-01: our spec against I26 0.11.0's code

Four read-only passes (AI, physics and collision, damage and weapons, missions and FSM), each rule of our spec marked
high-confidence or live-verified compared with I26's faithful path, deliberate deviations (docs/deviations.md) left
out. Most of the port matches, often line by line; the gaps below are what is left. Code readings only: each item
needs its test before it is offered. Spec references are i76-map subsystems/*.md.

**Picked first: the police siren (#51, #48).** The GAS0 header's play mode (int32 at +12: 0 one-shot, 1 loop, 2 shared
loop) is never read; every call site hard-codes looping. aps2.gpw (the engine-10 police horn) is mode 1, priority 60,
2 voices, 0.33 s of 11 kHz audio; I26 plays it once (`CarVoices.Sirens` via `Once`), so a cop's siren is a click. 26
stock .gpw files are mode 1. Fix: read the mode in the formats layer, the siren held and looped when its file says
so; also the siren's on-edge is lost when the car node is not ready. Branch `fix/siren-gpw-loop` (local worktree).

**Candidates, ranked (reported or report-shaped first):**
| # | finding | where in I26 | player sees | issue |
|---|---|---|---|---|
| 1 | spawn bob: wheel suspension history starts at 0, so the first filter call sees the whole terrain height as a step (+-0.25 r travel ringing ~0.8 s); no 0.2 s first frame; regen the same | Vehicle.cs:30,38; SimSession.cs:181; MeleeGame.cs:252 | cars drop and bob at mission start and respawn | #141 (new in 0.11) |
| 2 | AI obstacle avoidance: chooser order from a centred wheel (+a first in the original), all-blocked fallback (full lock, best blocked score), fixed 10 m x 2.6 m car-obstacle ladder, static probe grown 3 m | PtableEscapes.cs:246-421 | AI dodges the other way, reacts later, drives into buildings; maybe #111's stuck creepers | report-shaped |
| 3 | AI line of fire ignores structures (terrain only) | Combat.cs:574,596,632; PtableEscapes.cs:52 | AI shoots through buildings | report-shaped |
| 4 | Difficulty never applied: `Combat.Difficulty` has no writer outside tests; player damage x2.0 / 1.0 / 0.75 (offline) | Combat.cs:105; Main.cs ApplyPlayOptions | Wimp and Badass play as Champ | report-shaped |
| 5 | Taurus's car lacks flag 0x10000 (always set in the original) | Main.cs:653 only | Taurus can drift; a rollover wrecks him (mission fail) | t01-t03, t10, t11, t14, s02 |
| 6 | middle wheels get no suspension (drawn at the front/rear average) | Vehicle.cs:258-265 | tank and 6-wheel middle wheels sink on crests | #124 (wheel half) |
| 7 | contact order: statics before car-car, so a wall loses to a car (the original: last written wins, statics last) | SimWorld.cs:77-80 | pins and pile-ups resolve differently | - |
| 8 | the EZK mortar is never fired by the AI (subtype 3 falls through) | Combat.cs:598 | AI EZK cars never fire it | - |
| 9 | turret lead corrects for the carrier's velocity (the original does not) | Combat.cs:662 | AI turrets on moving cars hit more | - |
| 10 | class 8/9 placements not snapped to the terrain at load (static reading, medium-high) | MissionSetup.cs:219,278 | T11's guns 2 m up | - |
Smaller: wreck debris rolls 2-3 throw no parts and draw no rand (DamageModel.cs:252); isShot/isRammed seen one frame
not two (stale FsmTick at stamp); teleport does not write the terrain y into path node 0; tactic_skid modulus 32 not 31
at skill 0.4 (x87 truncation); scenery multi-hit choice (earliest TOI vs last written).
Not bugs: #124's "Empty" cannon label is the stock .gdf's own name (`3empty_on`); #114's tanker matches the script
and the reporter recalls it in the original; #71's smoke is already right in code.
Spec errors the audit found (fix in i76-map, I26 is right): damage.md:323 specials slots 17..18 not 17..19;
weapons.md:87 heat missile keeps a valid target; weapons.md:123 flamer explosion per touching segment; weapons.md:359
the .45 is 1.0 fixed; Disputed between two passes: whether setAgg (0x40bf60) also sets the attacker cap to 1 (the AI pass read the
decompile as yes, as I26 does; the missions pass read ai.md as no): read 0x412630 before either side is changed.

## 10. Branch tracker (local worktrees under the developer's i26-wt folder; nothing pushed)

| order | branch | commit | issue | state |
|---|---|---|---|---|
| 1 | fix/difficulty-damage | e95ca09 | - | ready: +19 tests; Wimp x2 / Champ x1 / Badass x0.75 offline, x1 in melee and co-op; note the shipped default is Wimp |
| 2 | fix/siren-gpw-loop | 2680b80 | #48 #51 | ready: GAS0 play mode read; needs one listen (P16 Foxy Cat, Esc skip, first cop) |
| 3 | fix/bookmark-cancel-returns | de70f99 | - | ready: Cancel returns to the opener (garage, salvage, post-mission); not yet clicked through in game |
| 4 | fix/mission-music-wrap | 883b33c | #128 | ready: N..14 then 2..14, 15+ alone; follow-up: shell credits track table and loop |
| 5 | fix/1997-tracers | 336073b | - | ready: MG a 1 px line over the front 65 % of the step, cannon the whole step, no 4 m cap; needs a 1997-look screenshot |
| 6 | fix/modern-target-health-bar | 6a8b5b7 | - | ready: the original's 30 x sqrt(hp) geometry scaled by height/480; needs a screenshot |
| 8 | fix/wheel-suspension-prime | 17d6000 | #141 | ready: VehicleStep.PrimeWheels at every fresh placement (missions, co-op seats, melee start/join/respawn, co-op respawn and recar), as the original's entity init; T01/T08/T16 substeps at the limit while still 9-21 -> 0; four seed-sensitive install tests (Checkpoint T14, T01Follow vppt01@20, T01 diner, T06 creepers) change outcome - offer re-picked seeds |
| 7 | fix/taurus-load-cornering | d669451 | - | validated against the original: t02 race with the player parked, kit 94.8 s, I26 100.5 s, I26 with the flag 95.3 s (turn mean 43.5 m/s, as the kit); the T01 diner dice test (seeds 1-4, needs 3) drops to 2: say so in the PR and offer a threshold the maintainer prefers |

Each branch carries its own CHANGELOG `## Unreleased` section, so they conflict on merge with each other: open one PR at a
time and rebase the next onto master after a merge.

## 11. Side-by-side measurements, 2026-11-01 (the kit at 41.667 ms vs I26 0.11.0)

Evidence: lab captures/i26-compare-20261101/tables.md (raw runs, harnesses, RERUN.txt). Same install copy and car.
| measure | kit | I26 20 Hz | I26 25 Hz | reading |
|---|---|---|---|---|
| suspension bounce (1 m / 3 m drops) | 1.71 Hz, settle 0.417 s | 2.00 Hz (+17 %) | 1.56 Hz (-9 %) | same depth; tempo follows substeps/s (28 vs 24); no I26 rate gives 24 - evidence for the late, optional clock conversation |
| 0-20 m/s, 10 s speed, stop from 29.5 m/s | 4.21 s, 28.73, 39.1 m | 4.20, 28.64, 38.6 | 4.20, 28.67, 38.6 | match |
| heading after 2.5 s full steer | 135.5 / 137.0 deg | 143.0 / 140.4 | 140.5 / 138.6 | withdrawn 2026-11-01: a harness artefact (I26 entered the turn at 19.8 m/s, carrying the brake phase's throttle); in lockstep at 1/24 s I26 matches the kit to 0.1 % (captures i26-lockstep-20261101) |
| t02 Taurus race (player parked) | 94.8 s, 43.2 m/s mean | 100.5 s, 40.0 | 99.6 s, 40.2 | I26 slower; the missing Taurus flag explains it (forced on: 95.3 s) |
| rounds: time to a 355 m hit, MG / rocket | 2.375 / 1.625 s | 2.40 / 1.65 | 2.36 / 1.64 | agree within one kit frame (42 ms, about 2.5 %), one method only (shot-to-burst times at the 355 m range end); I26 rocket ease matches the spec (0x4aa5b0, 0.5 x dt); per-tick kit check pending; the "too fast" feel is unexplained (suspect the 4 m tracer cap) |
| AI flee | rare (the kit's preset fixes the x100 health bug) | at the first core-part scratch (bug kept on purpose) | same | withdrawn 2026-11-01: at engine 20 % the health value is under the flee threshold with the fix on or off (20 vs 0.2, threshold >= 30); flee 1/6 fix on, 1/3 off, timing from random tactic draws. Per-tick lockstep: I26 attack/flee decisions match the kit; the real AI gap is the turn-speed constant (gaps inventory AI-1) |
Not measured: GOG at 46.9 ms; rendered 1997-look pictures; Taurus against a moving player (the "too fast" impression did
not reproduce with the player parked). I76_MOTION / I76_INPUT / I76_MOTION_CSV are documented in dev-hooks.md but have no
code in 0.11.0.
