# Re-implementation spec index

What a new engine for Interstate '76 needs, system by system: where the specification lives in this repository, how
complete it is, and what Open76 (`external/Open76`, the Unity reimplementation, commit e39db6e) already has. Status
words: **spec** = enough to implement from; **partial** = the structure is mapped but constants or branches are
open; **open** = not yet mapped. Updated 2026-09-27; goal tracker: `status/GOAL-COVERAGE.md`.

| system | status | spec | Open76 |
|---|---|---|---|
| Engine architecture (modules, frame order, object model) | **spec** | `ARCHITECTURE.md` (9 Mermaid diagrams, call-count module map; regenerate with `tools/callgraph_report.py`) | Unity's own |
| Runtime structures | **spec** | `types/i76_runtime.h` (42 structs, globals, offset checks) | own classes |
| File formats (all 30 families) | **spec** | `data/FORMATS.md`, parsers `data/fmt/` (6,368 files round-trip byte-exact) | parses and renders nearly everything |
| Vehicle data (.vcf .vdf .wdf .gdf compnent.cdf) | **spec** | `data/VEHICLES.md` | parsed; only armour and chassis are used |
| Mission script VM (FSM) | **spec** | `data/FSM.md` (14 opcodes, 96 actions), `data/notes/fsm-actions.md` | runs; many actions unimplemented |
| Frame loop and timing | **spec** | `subsystems/framerate.md`, `simclock.md` | Unity's loop |
| Vehicle physics step | **spec** | `subsystems/physics.md` (incl. far-vehicle model) | invented generic car model (Marco Monster-style) |
| Ground: terrain and walkable faces | **spec** | `physics.md` "How the car meets the world"; `data/FORMATS.md` .ter | Unity colliders |
| Object/vehicle collision | **spec** | `physics.md` (per-frame driver, shapes, 8-point box sampling, contact records) | Unity physics |
| Engine, gearbox, brakes | **spec** | `subsystems/engine.md` (equations, shift points, data-file -> code table) | invented |
| Damage, armour, wrecks | **spec** | `subsystems/damage.md`, `cheats.md` section 2 | per-side hit points only |
| Weapons and projectiles | **spec** | `subsystems/weapons.md` (fire chain, every projectile type's flight model, flamers) | partial |
| AI drivers | **spec** | `subsystems/ai.md` (34 behaviours, bodies named in ai-map-2 / range-n-1) | simple CarAI |
| Camera modes, cockpit | **spec** | `subsystems/camera.md` (17 views, keys, per-frame functions) | has camera modes |
| HUD, radar, cockpit instruments | **spec (drawing details partial)** | `camera.md` (radar rules, gauges), `engine.md` (needles) | partial panels |
| Renderer rules (LOD, far clip, sky, clouds, lights, shadows, mirror) | **spec** | `subsystems/renderer.md` (frame order, depth buckets, pixel LOD, terrain quadtree, time of day, lights, roads, clutter), `options.md` | renders levels |
| Sound | **spec** | `subsystems/sound.md` (manager, voices, 600 m cull, events, engsnd rows, CB radio, CD music), `data/notes/terrain-text-sound.md` | partial |
| Options, Play Options, built-in cheats | **spec** | `options.md`, `cheats.md` | |
| Game states, mission load, campaign flow | **spec (exe side)** | `subsystems/mission.md` (game states, play modes, .msn load order, salvage, vehscn.vsf); shell DLL: shell track | own menus |
| Saves (.cmp, savegame.dir, vehscn.vsf, I76PLYR.DEF) | formats **spec**; exe side **spec**; DLL writer: shell track | `data/FORMATS.md`, `mission.md` persistence, i76-everywhere `docs/SAVE-*` | none |
| Networking | **partial** (exe side named; not checked live) | `subsystems/network.md` (session, player table, 17 packet types) | none |

## Known engine quirks a faithful port must reproduce (or consciously fix)

- **Step-size dependence.** Physics is tuned to stock play at 20 fps: steps of 46.9 / 31.2 ms, about 24 per
  second. Contact push-out, rest snap, suspension IIR and coasting losses all follow the step rate
  (`framerate.md`, capture 014).
- **Terrain normal triangle choice.** It compares world coordinates with sample indices, and one branch returns a
  mirrored slope (`physics.md`).
- **Fixed per-frame effects.** Built for about 20 fps: cloud scroll, free-look and zoom rates, the keyboard throttle
  ramp, sound retriggers, and the locked-radar ping every frame (`framerate.md`; fixes in i76-everywhere
  `music-fix`).
- **Player bonus.** Offline, the player's armour and chassis are doubled and component health x4 (`damage.md`, `engine.md`).
- **Cheat detection.** Menu cheats turn a mission success into outcome 0xb (`cheats.md`).
- **Speedo in the air.** While skidding or airborne the speedometer eases toward the speed in m/s instead of mph
  (`engine.md`, confirmed live).
- **Fire decisions per frame.** AI weapons roll their random fire gate once per frame, so AI fire frequency follows
  the frame rate (`ai.md`, Fire decisions).
- **Flamers draw their own damage.** Flame damage is applied from the renderer, per rendered frame and again in the
  rear-mirror pass (`weapons.md`).
- **Other object classes.** The scene also holds helicopters (own flight model), turrets, gates, spinners and
  break-off chunks (`physics.md`).

## Next

The whole exe is named (2,193 of 2,217 functions, 99.5% of bytes, 2026-09-27; the rest are low-confidence holds).
What a port still needs is live confirmation of the static specs. In priority order:
1. flamer damage in play;
2. the helicopter model;
3. the oil-slick and special 0xb identifications;
4. the networking layer (needs two machines).
The gap list against Open76 is `OPEN76-GAPS.md` (2026-09-27): Open76 is a strong asset loader around stand-in
simulation (39 of 96 FSM actions; no mission outcome). Its section 21 lists what our specs still lack; wave 6 works
through it.
