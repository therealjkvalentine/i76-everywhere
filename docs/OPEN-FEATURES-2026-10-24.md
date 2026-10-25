# Open features and improvements, 2026-10-24

Everything the project's own records list as discussed and not finished, checked against later evidence. Written
2026-10-24 from a read-only pass over the backlogs (2026-10-02, -10, -16, agent items), OWNER-TEST-LIST (to the
2026-10-23 afternoon section), RELEASE-PLAN, ENHANCEMENTS, ARSENAL-PLAN, HAPTICS-ARCHITECTURE, MOTION-OUTPUT, the FFB
docs and records, SIM-RUMBLE-RESEARCH, MENU-USABILITY-PLAN, EMU-1997-PLAN, CLEANUP-PLAN, OWNER-MORNING-2026-10-16, the
dated records to 2026-10-23, `tools/haptics/README.md` and `motion/README.md`, the memory notes, and `git log` to
`cb890f3`. Nothing was run; no game folder was read or written.

**Status words.** **idea** = discussed, no design. **designed** = a written design or plan, no code. **partly built** =
some of it exists. **built, not tested** = the code exists and was never run where it counts (live game, real device,
the owner's route); "owner test pending" means only the developer can close it. **ruling** = blocked on an owner decision.

Done items are left out of the main list. Items an older backlog still shows as open but that later evidence closes
are in the appendix. Where a row cites "OTL" it means [OWNER-TEST-LIST.md](OWNER-TEST-LIST.md); "B-16" =
[BACKLOG-2026-10-16.md](BACKLOG-2026-10-16.md); "B-10" = [BACKLOG-2026-10-10.md](BACKLOG-2026-10-10.md).

**Two facts that frame the list.**
- Haptics, FFB, LFE and motion code has not changed since 2026-10-12 (`git log -- tools/haptics tools/ffb`, last commit
  `6e69260`). Everything below in section 1 is where it stood then. None of it has run against the game with a device.
- Promotion 19 (the 41.667 ms whole-sim tick + LAN pieces) is installed in `Games\I76\release-candidate` (2026-10-21
  14:03) and ships in the patch kit zip, but the daily driver is still promotion 18 (`33211f11`, 2026-10-17). The owner's
  "promote 19" verdict (OTL "Decisions wanted" 1) has not been recorded.

---

## 1. Force feedback, haptics, LFE / bass shakers, motion

The owner's request (HAPTICS-ARCHITECTURE intro, condensed there): any game event or sound as an input; a middle
layer with mapping, mixing and a design facility (stock FFB per event, the sound's spectrum, a live preview); outputs
to the DirectInput wheel, XInput pad motors, bass transducers over an audio device, and later a UDP motion feed. Phases
A and B (offline host, renderers) are built in `tools/haptics/` (C# .NET 8 host, 24 effect files, rig file
`desk-t300-evo4.json`); phase C (the console tests) has not started.

### 1.1 Force-feedback overhaul (wheel)

| item | status | source |
|---|---|---|
| Stock FFB on the wheel since promotion 15 (and 16, 18, 19): no gate since 2026-10-08 had a wheel; owner "FFB not tried yet" 2026-10-17 | owner test pending | OTL items 1-2, smoke 2026-10-17; B-16 H-01 |
| Wheel feel on the tick (steering lag / notchiness vs balanced): measured 4.2 ms with a synthetic pad only | owner test pending | OTL "Console session 2026-10-18" row 1; TICK-FINISH s.9 |
| Custom wheel FFB in the C# host (`Wheel.DirectInput`, port of `FfbCore.ps1`): never acquired a wheel in the host | built, not tested | tools/haptics/README "Stubbed ... honest list"; HAPTICS-ARCH 7 B3 |
| Feel tuning session (design report on a second screen, one effect file at a time, hot reload, two laps per change) | built, not tested (owner) | OTL item 15; HAPTICS-ARCH 7 C8; tools/ffb/README "Feel tuning: not started" |
| Wheel ownership mode C: our `i7_sfrce.dll` shim on Windows, host renders stock-reference effects AND ours (the recommended target mode) | built, not tested (Mac only; needs a mingw build on Windows) | HAPTICS-ARCH 3.3, 7 C7; FFB-STACKS "Still unproven"; B-16 H-04 |
| Coexistence: does the game's DLL still play effects while the host holds the wheel (decides whether mode C is needed) | owner test pending | OTL item 11; HAPTICS-ARCH 8 |
| Hardpoint record +0x10: firing frequency or direction (weapon effects key on it) | owner test pending (one drive) | OTL item 12; FFB-STACKS pick-up 1; FFB-DATA-AUDIT row 12 |
| Lint on the shipped tune: continuous wheel channels reach 91 % of the clamp (design rule 40-70 %) | open (feel decision, owner's) | tools/haptics/README lints |
| Re-creating the stock effects (mode C): impact / engine / terrain families from the DLL formulas; weapon families from hardpoint +0x14; `.frc` parameter block never decoded | designed | HAPTICS-ARCH 3.3, 4.3; FFB-DEEP-DIVE 3 |
| FFB-DEEP-DIVE runtime questions: surface-id to I7_* name order, block +0xe4..+0xec / +0x158 (written, never read), what [veh+0xe4] is | open (logging shim run) | FFB-DEEP-DIVE 6 |
| Blown-tyre steady pull (front tyre pulls steering +-0.3) and damage-aware lateral cap from live tyre grip | partly built (`tyre.flat.json` kick + shake; the steady pull not in any effect) | FFB-DATA-AUDIT row 6 |
| Pad / wheel early tick on GOG's Galaxy exe 9a232dcc (no WINMM import, so the joystick watch cannot attach): port the joystick watch to GOG's win32.dll shim? | ruling | TESTER-BUILD s.6.2; OTL 2026-10-23 afternoon decision 2 |
| Wheel latency of the tick: the wait for the next tick is uniform 0..T; a fix was described, not built | idea | TICK-LATENCY-AND-AI-FIRE-2026-10-17 |
| Docked USB FFB wheel on the Steam Deck (Wine evdev backend + the game's own FFB) | designed (doc steps), never run | STEAMDECK.md "Real force feedback" |

### 1.2 LFE / bass-shaker signal processing

Current chain: `Lfe.Synth` (the `LfeSynth.ps1` DSP ported: sines + noise bed, per-source rig compensation, HP 11 Hz /
LP 85 Hz x1.35 in LfeCore, soft limiter, waveOut to the EVO 4 at 16 kHz), plus `Lfe.Stems` (HD-pack 25-90 Hz stems on
SOUND_START / STOP) and `Lfe.Loopback` (WASAPI game-audio bed). All offline-tested; none has driven a shaker.

| item | status | source |
|---|---|---|
| Transducer A/B: synth only / stems only / both, per event (own MG and cannon, AI fire near and far, rams, explosions, engine idle to limiter, ignition, droppers), A/A first | owner test pending | OTL item 26; tools/haptics/README Lfe.Stems |
| Wheel + pad + shakers together for the first time: interference and dropouts | owner test pending | OTL item 9; HAPTICS-ARCH 7 C2 |
| Event-to-shaker latency (phone microphone on the shaker vs the host log); the stem path adds ~64 ms of queue; shorten the queue if impacts feel late | owner test pending | OTL item 10; SOUND-HD-PACK s.4 caveat; HAPTICS-ARCH 3.2 |
| WASAPI loopback bed: COM chain opened once, the packet path never fed real audio | built, not tested | tools/haptics/README |
| Music-aware duck for the loopback bed (proxy publishes `music_playing` from `g_playingTrack`, or gate on telemetry) | designed | HAPTICS-ARCH 5 option 2 |
| Stems are not compensated by the rig response curve (asks 1.0-1.5x across 25-90 Hz; stems may feel weaker than synth) | open | tools/haptics/README Lfe.Stems "Open or unverified" |
| The 7 dropper / nitro stems have no Lfe.Synth effect on their event at all; no nitrous / oil / engine-off bed on the bus | open (design + effect files) | tools/haptics/README; FFB-DATA-AUDIT row 10 |
| Lint: 4 continuous shaker sources (rule <= 3); heave carrier 35 Hz inside the engine's 26-38 Hz sweep; scrub 70 Hz inside the road bed's 55-72 Hz; "every bed + one transient" headroom above 0.95 | open (feel decisions, owner's) | tools/haptics/README lints |
| Filter corners: shipped HP 11 / LP 85 vs the design's 22 / 90 (rig file carries the shipped values) | ruling (or a measured choice) | tools/haptics/README; HAPTICS-ARCH 2.2 |
| Explosion level by distance: placeholder `clamp(1 - dist/100 m)`; the engine's concussion reach unknown; audit proposes 1/d^2 from EXPLOSION | owner test pending (explosion reach) | OTL items 13, 24; FFB-DATA-AUDIT row 9; B-16 H-05 |
| SHOT magnitude: a nominal 10 until a capture maps damage-per-hit to the hardpoint gain the weapon channel was tuned on | open (needs a real recording) | tools/haptics/README |
| Kerb / bottom-out from `susp_offset` edges: `KerbGain` exists, no code reads it | designed | `effects/impact.kerb.json` notes; HAPTICS-ARCH 6 item 8 |
| Second shaker channel (stereo L/R = front / rear?) unmeasured; rig response swept once (n = 1 rater, one rig) | open | HAPTICS-ARCH 2.3, 1.2 |
| Wk (ISO 2631-1) default rig curve when no sweep exists; cite it in `ffb-lfe-sweep.ps1` | designed | HAPTICS-ARCH 6 item 4 |
| Equalizer APO as a protective crossover on the shaker endpoint | idea (optional) | HAPTICS-ARCH 5 option 4, 6 item 7 |
| Real telemetry recording to replace the scripted session as every offline test's input (5 min of the owner's driving) | owner test pending (scripted v3 recordings exist, lab P2) | OTL item 8 |
| Telemetry v3 sound / damage events: in-game half (missing or doubled sounds, stutter) never listened to | owner test pending | OTL item 6 |
| `sound-rumble/` dsound proxy: retire (P9 verdict) or bench once | open (decision) | B-16 M-06; HAPTICS-ARCH 1.4 |

### 1.3 Pad rumble

| item | status | source |
|---|---|---|
| `Pad.XInput` renderer (MAX per motor, dead zone 0.30, >= 40 ms pulses): never drove a pad | built, not tested | tools/haptics/README; HAPTICS-ARCH 7 B2 |
| Effects one at a time on pad and shaker (impact.collision, landing, weapon.fire, slip.grip_limit) | owner test pending | OTL item 14 |
| SIM-RUMBLE catalogue gaps: wheel lock under braking (only `brake.judder`), throttle wheelspin, kerb strikes not in `effects/` | designed | SIM-RUMBLE-RESEARCH Part B |
| Owner's pad model and XInput slot; impulse triggers (GameInput only, not planned) | open question | HAPTICS-ARCH 2.3, 8 |
| Windows AHK pad mixer ships off (`gShimOwnsRumble := true` is Mac-correct) | open (set per platform) | FFB-STACKS pick-up 2 |
| Deck rumble re-enabled (`I76_AHK_RUMBLE`), never felt: nitrous kick, handbrake thud, gear click, crank, fire buzz, growl | owner test pending | OTL item 43; STEAMDECK.md "Rumble silent" |
| ffb-shim on the Deck (slip, impacts, terrain from the real force block) | designed (needs mingw; after AHK rumble is confirmed) | STEAMDECK.md |

### 1.4 Motion output

Owner plan (memory "sim cockpit + motion plan"): cockpit first (TR160 V5 / ASR Pro), 4 corner actuators later, driven
by the OutSim / OutGauge feed. Phases M0-M3 built (`Motion.Udp`: LFS OutSim classic / Pack2 / OutGauge, Forza Sled /
Dash, `i76motion` 144 B; validator, golden tests).

| item | status | source |
|---|---|---|
| Desk benches: FlyPT Mover (17), LFS world vs body frame (18), SimHub (19), Forza sign / gear convention (20) | owner test pending (install free software) | OTL items 17-20; MOTION-OUTPUT 8 T2-T3 |
| Signs from the real game (accel_body / yaw sign), interp vs hold, motion latency, explosion reach (21-24) | owner test pending | OTL items 21-24; MOTION-OUTPUT 8 T1, T4-T6 |
| M4 optional consumers: SimHub `.simdef`, SimXperience Open Game Telemetry (260 B, UDP 10001), SimTools plugin | designed, not started | motion/README "Stubbed"; MOTION-OUTPUT 8 |
| M5 proxy v3 motion fields (`step_total`, `wheelbase`, `wheel_radius`, `surface_bump_amp`) | designed | MOTION-OUTPUT 4.2, 8 |
| M6 `Motion.Washout` + `Actuator.Direct` (drives nothing, logs; E-stop) | designed | MOTION-OUTPUT 4.3, 6, 8 |
| Real rig: stale / neutral ramp test with the owner's controller (hardware not chosen) | idea until hardware | OTL item 25; MOTION-OUTPUT T7 |
| Engine unknowns the host works around: gravity in ent+0xd4 in flight, contact record at entity+0x38, wheel radius field, WRLD bump row base | open (RE) | MOTION-OUTPUT 9; motion/README |
| Closed ecosystems: D-BOX, Sigma, MOZA Motion Manager (HMA150) cannot take the feed without a vendor SDK | blocked (vendor) | memory sim-cockpit plan; MOTION-OUTPUT 9 |

### 1.5 Haptics plumbing and shipping

| item | status | source |
|---|---|---|
| I76 Debug "Start haptics host" with a real wheel / pad and `--live` | built, not tested | DEBUG-TOOL-2026-10-20 s.4; OTL 33b |
| The haptics host is not in any shipped folder (Debug's tab says so): package it for players, or keep it developer-only | ruling | DEBUG-TOOL-2026-10-20 s.4 |
| B4 real-time loop met its exit criterion on replay only; never with the game rendering on the same machine | built, not tested | tools/haptics/README B4 |
| Phase-A hygiene leftovers: four stale labels in `ffb-shim/i7ffshim.c` / `tools/ffb/README` (audit row 11) | open (docs) | FFB-DATA-AUDIT row 11 |

---

## 2. Audio and music

| item | status | source |
|---|---|---|
| Retail music + resume (`I76_MUSIC_RETAIL=1`, `I76_MUSIC_RESUME=1`, `I76_MUSIC_DISC_ORDER` confirmed by ear) into the daily driver | built, owner-approved; waits for promotion 19 | OTL "Owner results 2026-10-17" 04 / 05 |
| HD sound pack v1 A/B by ear, and whether to pursue it plus a small-speaker variant | owner test pending; ruling C10 | OTL item 7; OWNER-MORNING C10; SOUND-HD-PACK 6.3 |
| Cutscene-music fix on Windows (smack-music-fix; Mac-verified only, not on the driver) | built, not tested | B-16 M-02; ENHANCEMENTS 6 |
| `I76_MUSIC_THREAD`: README row, never measured | built, not tested | B-16 M-04 |
| Music on the Macs' Nitro app; Nitro's music route through GOG's WIN32.dll | open | NITRO-MAC s.6 item 3; OTL 2026-10-21 cross-machine caveats |
| "Music not consistent" (owner 2026-10-19): the silences are data-track missions and retail's 0-60 s gap - kept as the chosen rule | ruling recorded; reopen only if the owner says | OTL 2026-10-19 notes table |

---

## 3. Graphics and rendering

The owner's picks of 2026-10-23 live as `OWNER-2300-ALL` in lab `exp-polish2` (one-pass sky, stateless morph + BIG
unset + NEAR 100, SHADE 3, shade smooth, Glide fog 0.75, feather, sparse bushes, clutter alpha fade 150, 2300 m,
mirror detail; proxy `6e4e7c49`) and as the patch kit's `PLAY-PREVIEW`. None of it is in the daily driver or the RC.

| item | status | source |
|---|---|---|
| Promote the owner's graphics set (OWNER-2300-ALL) after a gate; the morph's cost on the T05 ridge climb (~100 fps seen) to measure first | built, not promoted (ruling) | OTL 2026-10-23 morning; RENDER-FINISH s.4 |
| Far clip: 2500 m crashes the binoculars at LOD 24 (int16 vertex wall); presets use 2300; the proxy cap (2500) is too high; tessellator fix for > 2500 m (F-22) | partly built (cap, workaround) | OTL 2026-10-23 morning; B-16 F-22 |
| Cockpit zoom (PgUp) at 2300 m not tested; m03 direct boot faults at frame 0 in exp-polish2 (unrelated, open) | open | OTL 2026-10-23 morning |
| Proxy-built mip chain in the `grTexDownloadMipMap` hook (ZGLIDE's mipmap mode expects the caller's levels; 5/5 crashes) = the "continuous fade between textures" | designed, not built | TERRAIN-POPS s.6-7; `5bfa496` |
| Terrain pops class B: births the morph only partly covers (wider band / lower LOD error threshold) | idea (small) | TERRAIN-POPS table |
| Ladder follow-up T1: drive R14 (height-error threshold /24 alone, nearly free) against R07 | owner test pending | OTL 2026-10-21 evening T1; REBASELINE s.4-7 |
| Far-edge: per-vertex fog for the authored walls (GR_FOG_WITH_ITERATED_ALPHA with our vertex alpha) "if the owner wants the walls fogged rather than brightened" | designed | FAR-EDGE-FADE s.5 |
| Far-edge, mirror detail and edge fade on Nitro: `I76_EDGE_FADE` and `I76_TERRAIN_FLAT_SPLIT` stay Gold-only (c349c82 ported the rest) | partly built | `c349c82`; FAR-EDGE-FADE s.5 |
| Mirror: is 2300 m in the mirror worth 1.2 %, or 1200 m; mirror-only road / clutter distance as the next lever | ruling / idea | MIRROR-DETAIL s.5 |
| Two-frame menu stutter (owner 2026-10-23 "again", not reproduced): which menu; if it is the residual, one extra scene draw (`I76_MENU_DRAW=2`) | open; fix designed | MENU-SOUND-POLISH B2 (`55d6f3f`) |
| Tracers under the tick: tick-long streak vs a one-frame streak like the driver | ruling (OTL decision 7) | OTL "Decisions wanted" 7; TICK-FINISH s.17.6 |
| True wide 2D menus (present the DirectDraw frame ourselves); today 4:3 with bars | idea | B-16 G-02 |
| Detail switches never judged by eye (shadow dist, road tex, `I76_TERRAIN_TEX` 1/4 vs 8, ReShade CAS+SMAA, nGlide / DXVK) | owner test pending | B-16 G-04, G-07, X-14 |
| Draw-distance leftovers: far mips, object cull radius, the 3796 m depth bucket | open | B-16 G-14 |
| Cockpit dash at 2x (tile-split boots 28-30; is a sharper dash worth a session) | built offline; ruling C9 | OTL items 28-30; COCKPIT-HIRES-FEASIBILITY |
| AI-upscaled menus and fonts ("another possible future epic is ai upscaling menus and fonts") | partly built (lab spike, no boot) | UPSCALE-SPIKE-2026-10-21; MENU-HD-ART; B-16 G-10 |
| Texture upscaling packs in game; OpenGLide-HD dump / replace never verified in game | partly built | B-16 G-09, G-11 |
| `I76_GLIDE_GAMMA` on Windows | built, not tested | B-16 G-12 |
| Render-interp gaps (projectiles, wheels, AI cars measured only for the player) | open | B-16 F-13 |
| Head tracking and frame generation at 120 fps (untested since promotion 0) | owner test pending | B-16 H-07 |

---

## 4. Physics, gameplay and AI

| item | status | source |
|---|---|---|
| **Promote 19** (tick 41.667 ms + LAN pieces + retail music) to the daily driver | ruling | OTL "Decisions wanted" 1, A6 |
| `I76_JUMP_NOSE=0.91` (the owner's "ever so slightly ... like 9% less"): built and measured (0/12 destroyed vs 1/12 stock); into the presets / next candidate | built, not in a preset | TICK-FINISH s.22.6; `e02d64a` |
| Base decision on paper: Gold exe with retail 1.0's rules (difficulty 1, retail health %, AI damage-stamp revert, retail turret slew and heat-seeker cone) - which retail-rules items on by default, and the Gold data retunes (bus mass, Gas blast, armour / loadouts) | ruling (item 53) | OTL item 53; BASE-DECISION-1.0-vs-GOG |
| Gold vs retail sliding at 25 m/s (+19 % yaw) - does it matter for "stock" | owner test pending (emulator) | OTL item 50; GOLD-STANDARD-FINGERPRINT |
| Difficulty: owner's copies are on Wimp (player damage x2 offline); Champ or Wimp; Badass / Champ network melee once a pack carries it | ruling | OTL "Rulings 2026-10-20 evening" difficulty (a) (b) |
| Flame on a road-closed bar burns ~2x the 1997 rate: accept or a separate bar factor | ruling (decision 4) | OTL "Decisions wanted" 4 |
| Driver's AI skid / horn rolls at 5x the 1997 rate (moot once 19 is promoted) | ruling (decision 5) | OTL "Decisions wanted" 5 |
| Per-frame hazards at the 1997 rate on the tick (oil, pinned, burning wreck, radar missile) and flamers on 42 | owner test pending | OTL 2026-10-19 A1, A2 |
| Radar-missile turn rate (code only, unmeasured) | open | B-16 F-05; OTL "Open / not measured" |
| HUD ammo-digit roll, flamer damage/s on the driver, death-camera orbit on the driver | open (agent-measurable) | B-16 F-06..F-08 |
| `I76_ENGINE_DT_FIX` isolated, `I76_FAR_ENGINE_DT` | built, not tested | B-16 F-10, F-12 |
| Sustained-scrape damage per second; two of four T13 "god-held player dies" deaths (also stock) | open | OTL "Open / not measured" |
| Car under the terrain in real play (cockpit sink) - still unexplained | open | B-16 F-02 |
| T12 milk-truck residual (FSM test not reached on the next pass) | open | B-16 F-14 |
| "Sometimes it seems like it spawns" (owner 2026-10-19) - not understood | open (needs the owner's where / what) | OTL 2026-10-19 notes table |
| Physics-step study's last stage: blind taste A/B, written up for the community (the owner also sends it to an outside tester) | designed | PHYSICS-STEP-STUDY-DESIGN s.8; memory gold-standard ruling 2026-10-17 |
| P133 reference cell: lowest detail, developer default, or both; 10 more boots per arm for the jump wreck rate | ruling (item 55) | OTL item 55; HARDWARE-MATRIX |
| I26 lesson: helicopter altitude vs tick rate as a gate row | idea | memory i26-parallel-project; PRIOR-ART-I26 |
| RE completeness: I76PATCH.DLL internals, projectile range, OPEN76-GAPS citations, renderer.md opens, `0x5FCDC4`, COLLISION-MISS s.6.6 (shape kind 2 writer, 0x48f840's list) | open | B-16 E-02..E-07 |

---

## 5. Multiplayer

### 5.1 Gold (family LAN)

| item | status | source |
|---|---|---|
| AI-respawn pack (dead AI respawn, AI scored like players, AI in every stock arena; "(N AI)" entries removed): staged `mp-pack-20261020-airespawn`, on no machine | built, not deployed (owner's go) | OTL "AI cars respawn ..." ; MULTIPLAYER.md "Update 2026-10-20 night" |
| Joiner's kill of an AI credited on every screen (never measured: no remote aiming) | owner test pending | OTL C1, Morning 2026-10-20 item 3 |
| Teams with AI (`_TEAMS=1` never run; who scored for kills) | owner test pending | OTL Morning 2026-10-20 item 6; MP-TEAMS |
| LAN cells: 5 players, a co-op win then a late join, a 3-human Scene 17 | owner test pending (family machines) | OTL 2026-10-18 row 7, C3 |
| Feel of AI fill count and co-op extras per joiner (`I76_AIMELEE_FILL`) | ruling | OTL Morning 2026-10-20 items 1-2 |
| Co-op host leaves: the new host restarts the scene - keep, or continue where it was | ruling | OTL Morning 2026-10-20 item 7; LAN-MATRIX-2026-10-20 s.7.2 |
| Scenarios: keep "host death reloads the scenario" or build host melee respawn (script edits per scenario); host stays in the death view in melee, "fix pending" | ruling / designed | OTL "Decisions wanted" 3; COOP-LIST-ENTRIES s.8.3; MULTIPLAYER.md |
| Deck in LAN games: Steam launch option to `i76-deck-launch-mp.sh`, join on the new pack never measured; the Deck's proxy has no AI-sync / pack switches | owner step pending | OTL Morning 2026-10-20 item 0; "Open / not measured" |
| `I76_COOP_AI` crashed a lab game on a trainer re-placement; the lab-only shooter switch needs a guard | open | OTL A0c note; ARENA+ results |
| Internet / off-LAN play: direct IP (UDP 21157) untested; ZeroTier / Radmin carry broadcast; IPXWrapper DOSBox mode does not work | open | MULTIPLAYER.md top; B-16 N-05; memory resume 2026-10-20 |
| Campaign co-op on one PC (Nucleus split-screen): `game-nucleus` runs an old proxy, co-op not wired into the handler | ruling C11 | B-16 N-04; OWNER-MORNING C11 |
| Co-op natural run with two people, MAX SCORE, host car model | owner test pending | B-16 N-02 |

### 5.2 Nitro (ARENA+ / GAME TYPE entries, ARSENAL-PLAN)

Owner, 2026-10-21: "let's do the work to understand and fix nitro same as we did for gold. we'll plan to ship for
arsenal so it's complete ... from a multiplayer perspective we'd want nitro to be the basis instead of gold ...
nondestructively, so that community play of nitro multiplayer is unperturbed." GAME TYPE entries ("Arena Drop-In + AI",
"Co-Op") are the default since `ddceb7a`; the weekend how-to is `docs/NITRO-LAN-WEEKEND.md`.

| item | status | source |
|---|---|---|
| Nitro crashes in HeapFree at the next mission start (after Replay or Abort > new mission), every optional switch off too: found, not fixed | open | `cb890f3`; NITRO-PORT s.11 |
| Remove the ARENA+ / CO-OP box code (F2 / F3 sites, `=0` branch) after one release | planned | NITRO-MP-DESIGN s.0.5.19 "Left" |
| The boys' shipped Mac apps take the GAME TYPE build at the next Mac proxy rollout | planned | NITRO-MP-DESIGN s.0.5.19 |
| Lobby / internet: an unknown species may be hidden by the bz911 lobby; ARENA+ is IPX / LAN only until a species is agreed with the community | blocked (community) | NITRO-MP-DESIGN 5 R3, s.0.5.8 |
| Tick in community Nitro games (every player should run the same tick); Macs have no tick yet (24 fps cap) | ruling / open | memory resume 2026-10-21; OTL 2026-10-21 Mac caveats |
| Nitro in-mission Esc menu by mouse on the PC | not tested | NITRO-PORT s.10 |
| ARENA+ description wording ("the original '76 missions" vs "the Nitro missions") | ruling | OTL 2026-10-21 ARENA+ results |
| Replacing the boxes by game types was done; the one IPX joiner type-text path (G6) never drawn | open (unobserved) | NITRO-MP-DESIGN s.0.5.18-19 |
| Nitro per-team spawn tables, anet2 internals, VFS sub-folder question | open (RE) | NITRO-MP-DESIGN 6 |
| The M4 Max tester's first-boot wined3d fault (n 1 of 2); EVO4 output delays Mac start ~40 s; Esc at the main menu quits on the Mac | open | NITRO-MAC s.6; OTL 2026-10-21 Mac caveats |
| "Get nitro working as well as gold": remaining port subsystems measured on Nitro the way Gold's were (debug tool, shell key / popup patches as NITSHELL equivalents) | partly built | ARSENAL-PLAN "Shape of the work" 1; NITRO-PORT |
| Arsenal pack: both patched exes in one pack, one README | planned | ARSENAL-PLAN 4 |

---

## 6. UI, menus and controls

| item | status | source |
|---|---|---|
| F2 orphaned-bookmark fix: console test PASS (stock ORPHAN, F2 OK); in no shipped shell (the patch kit's patcher applies F7 + M1/M2/K1-K4 only) | built, not shipped | OTL item 48; BACKLOG-AGENT-ITEMS U-05; TESTER-BUILD |
| Shell patches M2, K2, K4 and the garage "Overwrite the current variant?" prompt: emulated only, never live | built, not tested | B-16 U-06 |
| Menu pointer on GOG's 9a232dcc under the shipped cursor map (gate rows 3-6 void twice); overwrite Y/N and popup Enter / Space there | not tested (agent, after the reboot) | TESTER-BUILD s.6.3, 7, 8.5 |
| Esc / exit-menu pointer fix (`I76_MENU_PTR_CENTRE`), Alt-Tab fresh frame (`I76_MENU_DRAW`), Windows-only Up / Down look swap (staged polish2): owner's hand check | built, owner test pending | OTL 2026-10-21 P8-P10 |
| Debug tool full-state store / restore (Ctrl+9 / Ctrl+0), waypoint 2, haptics button | built, owner test pending | OTL 33b; DEBUG-TOOL-2026-10-20 |
| I76 Debug on a real drive (fps with the page open, every tab) | owner test pending | OTL item 33 |
| Control Configuration menu destroys `input.map` (mitigated by the launcher guard; prevention is a policy call) | open | B-16 U-07; MENU-USABILITY P12 |
| Lossless Scaling overlay over shell prompts | open hypothesis | B-16 U-08; MENU-USABILITY P15 |
| Resume campaign / skip-to-mission (option A: u32x drives the shell for the player) | designed | MENU-USABILITY E1 |
| Default a fresh save name (`Scene N <HHMM>`) | designed (after F2) | MENU-USABILITY E3 |
| Boot-movie skip decoupled from `I76_MISSION` | designed | MENU-USABILITY P9 / E5 |
| `PLAY-16x10.bat` old pointer regime: keep or promote the cursor lines | ruling C7 | B-16 U-02 |
| Pad: hand test of the pad-layer fixes; Mac map convergence; native B / Y; Y view cycle + right-stick orbit never promoted | owner test pending / not promoted | B-16 C-01..C-04 |
| Deck: menu pointer offset (cause unmeasured), pad menu v3 and TV profile re-test, TV gamma / brightness values to keep | owner test pending; ruling C12 | OTL items 39, 43; OWNER-MORNING C12 |
| Mac Esc menu by mouse on the laptop (fixed on the M2 tester Mac, laptop screen was locked) | owner test pending | OTL "Mac converge" item 1 |
| Instant Melee ENTER AREA in 86Box would not take injected clicks | open | OTL 2026-10-19 A5b |

---

## 7. Platform and packaging (releases, installers, Mac, Deck)

| item | status | source |
|---|---|---|
| v1.1.0: CHANGELOG still a DRAFT block covering to 2026-10-10; extend to 10-24; the tag is the owner's | ruling / docs | CHANGELOG.md; B-16 R-03; OWNER-MORNING C13 |
| Patch kit (first tested by the tester): release v0.7.3 is published on GitHub; whether to announce it or send the zip | ruling | OTL 2026-10-23 afternoon decision 1 |
| Shipped `saves\savegame.dir` carries 92 B of zero slack | ruling (trim or leave) | OTL 2026-10-23 afternoon decision 3 |
| Fresh install by the owner: real `INSTALL.bat` with GOG's installer and UAC, music in a mission on that exe, best-wide, a Save Bookmark | owner test pending | OTL item 16; B-16 R-04 |
| Non-ultrawide real hardware (16:9 GPU / DPI, the menu pointer at that size); a 4:3 monitor (dry run only) | not tested | TESTER-BUILD s.7 |
| `Build-From-GOG.ps1 -Game Nitro`: console proof pending | built, not tested | `5cee886` |
| Mac: no tick / 60 fps on the Macs (24 fps cap); the 60 / 120 switches untested under Wine | open | OTL 2026-10-21 Mac caveats; ENHANCEMENTS 9 |
| Mac: clean-machine installer (`mac-install.command` "BETA"), mic prompt | open | B-16 K-02 |
| The M4 Max tester Mac: Gold app not renamed (firewall allow entries need sudo) | blocked (owner, sudo) | NITRO-MAC s.7 |
| Deck: proxy switches under Proton beyond the TV / pad set; Deck baseline tier never run on hardware | open | ENHANCEMENTS 1, 9 |
| THIRD-PARTY.md: the dgVoodoo redistribution sentence (the patch kit relies on Dege's clause), Lossless Scaling, opentrack, GE-Proton, others | partly done | B-16 R-12; RELEASE-PLAN 5 "Legal notes" |
| <re-archive> public export (allowlist script, decompiler-residue grep, THIRD-PARTY for anet-0.10 / DX5 headers) | partly built | B-16 R-11; RELEASE-PLAN 7 |
| CI check: no file > 2 MB, no game formats, no DLL except the proxy | designed | RELEASE-PLAN 5 "Legal notes" |
| Outreach order: PCGamingWiki, GOG forum, interstate76.com, VOGONS, Open76 / Roanish, Reddit | designed, not started | RELEASE-PLAN 8 |
| Folder layout stages 0-4 (Games\I76 junctions done 2026-10-20; twin rename, retire / zip lab copies, VERSION.md rules) | partly done | LAYOUT-PROPOSAL-2026-10-20 s.4; memory resume 2026-10-20 |
| Phones (Android via the Deck recipe, iPhone streaming / VM) | idea (research only) | ENHANCEMENTS 9; PHONE-PORTS |
| Glide on the Mac (Metal): parked, one-line rebuild if shader caching ever persists | parked | VOODOO-PARKED |
| Reimplementation in a modern engine for the M4 Max tester (recommendation: Godot 4, not Unreal) | idea (paper study) | REIMPLEMENTATION-ENGINE-PROPOSAL-2026-10-17; REMAKE-RE-HANDOVER |

---

## 8. Emulator and the 1997 reference

| item | status | source |
|---|---|---|
| Gold path in 86Box (`PLAY-P166-GOLD.bat`) never booted end to end | built, not tested | OTL 2026-10-22 afternoon |
| Owner's logged P166 play session (retail 1.0, T05 to the canyon, summary.md) | owner test pending | OTL items 46, A5b |
| Owner-facing 86Box launchers at graphics giving ~40 ms frames (later ruling: 33.3 ms baseline for the study) - which detail / resolution lands there, n >= 3 | open | OTL "Owner results 2026-10-17" |
| Instant Melee frame replays (exe vs emulator frame by frame): the menu navigation failed headless | open (agent debugging) | OTL item 51; LAB-FRAME-REPLAY |
| EMU-MEMTRACE s.7 list: frame-dt replay mode in the proxy, same start state, T06 ramp + flat-road routes on retail, retail AI lists | partly done | B-16 X-07; EMU-MEMTRACE s.7 |

---

## 9. Tooling and docs

| item | status | source |
|---|---|---|
| ENHANCEMENTS.md refresh: last touched 2026-10-10; nothing on the tick, LAN / AI fill / teams, Nitro, terrain morph, far-edge, mirror, Debug, Deck TV, "multiplayer untested" sentence stale | open | B-16 R-07, N-03 |
| Shared harness takes any `i76` / `nitro` process as the game: a single-thread zombie blocks every lane until a reboot | open | TESTER-BUILD s.7; OTL 2026-10-23 ~16:00 |
| Gate row 9 (fps at the console) needs the display awake: keep-display rule in every console brief | partly done | memory display-asleep-voids-fps-rows |
| Click-UI raw-pointer scripts left on purpose (calibrate, probes, nucleus-q, mp-explore, renderer-matrix) | open (listed) | BACKLOG-AGENT-ITEMS U-12 |
| Airborne detector on the interpolated pose; cactus2 class-4 classifier | open | BACKLOG-AGENT-ITEMS "Not done" |
| Residue scripts, `records/READY-TO-TEST.md` fold into VERIFIED-FIXES, `docs/README.md` doc map regeneration | partly done | B-16 R-06, R-10; RELEASE-PLAN 5 |
| Lab `builds/*/src-*` snapshot folders: commit or drop | ruling | BACKLOG-AGENT-ITEMS "Doubtful" |
| Diff I26's physics step and format writers against ours when their source lands; read its releases before briefing a lane | idea (standing rule) | memory i26-parallel-project; PRIOR-ART-I26 s.8 |

---

## Appendix: closed since the backlogs listed them as open

| backlog row | closed by |
|---|---|
| X-01 promotion 18 held; C4 hold, bushes thin vs dense; C6 box =4 | promoted 2026-10-17 (09 variant: hull fix, signs =4, bushes dense to 300 m, terrain x24), OTL item 36 |
| G-01 terrain drop-out in cockpit (hull fix) | in promotion 18 (gate P9: 0 losses n 5) |
| C1 / X-04 physics step | ruled 41.667 ms (OTL "Rulings 2026-10-20 evening") |
| X-03 / C5 AI parity set; AI pace | superseded by the whole-sim tick at the 1997 coupling (TICK-FINISH, TWO-CLOCKS) |
| Arcade Phys. gold standard (item 45) | ruled: simulation physics |
| M-03 `I76_MUSIC_SHELL` / disc order | ruled retail music + resume; disc order confirmed by ear (item 47) |
| J1 the jump falls short; J2 ease the nose-dive | J1: stock behaviour, "leave it"; J2: ruled 0.91, built `e02d64a` |
| U-05 F2 live test | PASS 2026-10-17 (shipping it is still open, section 6) |
| U-12 Click-UI audit, U-13 gate row D, H-06 memlib labels, R-09 DOC-CORRECTIONS, X-16 README rows, R-16 lab loose ends | BACKLOG-AGENT-ITEMS-2026-10-16 |
| item 52 retail canyon clip frozen | re-recorded, "looks perfect" |
| N2 Nitro entry name; boxes vs game types | ARENA+ ruled; GAME TYPE entries default since `ddceb7a` |
| Nitro menu pointer confined to 640x480 | fixed `faff357` (NITRO-PORT s.10) |
| Mac converge (one app per Mac), Mac joins (data-path key), Up / Down map for Windows only | MAC-CONVERGE, NITRO-MP-DESIGN s.0.5.16, OTL 2026-10-21 P10 |
| AI in every arena, AI respawn instead of wave reload, AI scored like players | built (AI-MELEE-RESPAWN; deployment still open, section 5.1) |
| Difficulty drives melee AI skill | built `5b003fd2` (copy setting still a ruling) |
| One launcher + `--legacy-multiplayer`; DEBUG.bat; MULTI MELEE straight to IPX | built (MENU-SOUND-POLISH, DEBUG-TOOL) |
| Two-frame exit flicker, barricade hit-sound restart, 120 fps on the hill | owner play-test 2026-10-21: done |
| Sky scroll in the mirror pass | owner picked one pass (`I76_SKY_MIRROR=0`) |
| Far flicker with `I76_TERRAIN_MORPH_BIG=2`; bushes as black squares with the alpha fade | fixed (RENDER-FINISH; `a8f694a`) |
| Mirror cloud art | owner prefers stock; M16 sky opt-in (`2516fb4`) |
