# Rear-view mirror detail - 2026-10-23 (rear-mirror lane)

Owner's goal (2026-10-23): the cockpit mirror "looks like a totally different world instead of a low resolution version
of the same world". Wanted: the same world at low resolution - textured terrain and roads with the main view's detail,
draw distance as far as is noticeable without a frame-rate cost.

Code: `music-fix/mirrordetail.c` (repo 6df5500+), `I76_MIRROR_FAR` range widened (strlkproxy.c). Lab: `tools/mirror-detail/`
(md-run.ps1, md-montage.py), runs under `autotest/runs/mirror-detail/`. Evidence copies: lab `exp-polish` (never the
owner's exp-polish2 while he plays it).

## 1. What the mirror draws (static, i76.exe 9a232dcc / 6319abf7; builds on lab CLUTTER-AND-MIRROR.md s.2)

The mirror is a software render into the 256x64 8-bit private copy of ZMIRI101 ([0x608cbc]), kind 0, so every record goes
to the software rasteriser 0x471fd0. What was NOT known before this lane:

- **Same records as the main view.** At mirror level 2, renderer_DrawRearMirror 0x445750 runs the same passes for the
  mirror camera 0x608c80 as the main view does for its camera: sky light 0x401bd0, renderer_QueueTerrain 0x490a00
  (0x44594e), roads 0x48e900, flamers, objects, clouds, flush 0x48fac0(cam, 1). The terrain quadtree therefore splits with
  the same K / B constants (so `I76_TERRAIN_LOD` applies to the mirror pass too) and the leaf fan 0x491a30 emits the same
  draw records. Level 1 (the option's middle setting) draws objects only, no terrain: a mirror of cars on a flat
  sky-coloured background (options.md "Rear Mirror levels").
- **Texture level and variant are chosen per camera.** The per-leaf picker 0x4923f0(leaf, 1/z) reads the width of the
  camera's own bitmap (`[[cam+0x3c]]`: 256 for the mirror, 640 for the main frame) for the level
  `clamp(9 - floor(log2(W x 40 / z)), 0, 6)` and asks 0x471f00(&set[level], cam) for the texture, so the kind-0 mirror
  gets the 8-bit variant. The draw mode comes from [0x59c570] (node > 8 samples) or [0x59c554] (<= 8).
- **Draw mode.** The emitter 0x4924b0 stores the mode at rec+8, projects through 0x4f9538[mode] and queues with 0x48fe10,
  which rewrites mode = (mode & ~0x10) | 8. Span drawers that exist for textured terrain (tables 0x4f8d38 / 0x4f9538
  read from the exe): 0xf4 -> 0xec (0x4859e0: textured, ONE shade row per polygon), 0x15 -> 0x0d (0x487190: textured,
  per-vertex Gouraud), 0x4d (0x48a580, keyed Gouraud). 0xf5 / 0xd5 / 0xe5 land on the default entry 0x47d110 (276 of 512
  modes): not drawable. The records carry a per-vertex shade (the lighting loop 0x490f08 writes [0x5dd2ec]+8 and the
  emitter copies it into each vertex), so a Gouraud mode has its data.
- **Far clip 100 m** (push 0x42c80000 at 0x44553c; `I76_MIRROR_FAR`, now 100..2500 m). camera_Create clamps 100..100000;
  the depth buckets reach 3796 m.

Instrument (`I76_MIRROR_DUMP=<N>`): wraps the "RearView" re-upload at 0x445a3c (the finished mirror, scene + frame mask),
writes the bitmap as an 8-bpp BMP with the display palette 0x5dcfa8, and logs a census per redraw: mirror / main terrain
vertices ([0x6442ec] after each QueueTerrain call), leaves, modes the picker chose, null textures, the option bytes.
Switch (`I76_MIRROR_TERRAIN_MODE=<hex>`): the mirror pass's leaves get that mode instead (main pass untouched).

## 2. Live look (exp-polish, OWNER-2300-SHADE keys, t01, proxy build mirror-w2 / w3 from the working tree)

Runs: lab `autotest/runs/mirror-detail/20261023-072311-stock-look` (stock mirror, dumps every 15 redraws, `montage.png`,
`main.png`) and `20261023-073647-I-pic-far2300-lod1-every2` (the delivered setting, same files). The PNGs stay on disk in
the lab (ignored by git); montage = four dumps x3 beside the main view.

**Census, stock mirror** (every redraw the same): mirror pass 240-280 vertices, 90-120 leaves, all mode **0x15**, no
null texture; main pass 7,250-7,400 vertices, ~3,000-3,200 leaves, modes 0x17 (big nodes, 780-915) and 0x15 (small,
~2,200-2,270); options terrain-detail 1, textures 1, mirror 2, visibility 2; bitmap 256x64 kind 0.

So the mirror's terrain was ALREADY textured, perspective-correct and Gouraud-lit with the main view's texture set (0x15 is
the main pass's own small-node mode; 0x17 = 0x15 + UV clamp for its big nodes). renderer.md's "terrain and roads use 0xf4"
does not describe this path. The mode override `I76_MIRROR_TERRAIN_MODE` is therefore moot (kept as a lab knob).

**What the picture showed.** Stock: textured, lit ground to a hard horizon ~100 m behind the car, then sky and clouds - no
mesas, no hills, while the main view has them at 200-800 m all round. That is the "different world": the mirror's 100 m
far clip, not its rasteriser. With FAR 2300: the mesas, the canyon walls, the red enemy car, cacti and the road behind the
car, at 256x64 - the same world. Mirror pass then 1,660-1,690 vertices, 480-500 leaves at the stock LOD (LOD 1).

## 3. Switches and fps cost

Render fps from `I76_FPS_LOG=5` (swap-counted; the telemetry rows count sim ticks under the tick preset: 24.1/s, dt
41.67 exactly - do not read those as fps). t01 cockpit, 6 s drive then six 5 s windows per boot; mean of the six;
120 Hz dgVoodoo refresh in the preset so 120 is the ceiling. One boot = one row unless marked.

| condition | boots | fps (mean of 6 windows) | work ms avg | cost |
|---|---|---|---|---|
| A baseline (OWNER-2300-SHADE, stock mirror 100 m) | r2, r4, r5 | 120.1 / 119.7 / 119.2 | 8.31 / 8.34 / 8.38 | - (spread 0.5 fps) |
| B I76_MIRROR_FAR=600 | 1 | 112.1 | 8.91 | 7 % |
| C FAR=2300 (mirror at the main's LOD 24) | 1 | 91.1 (76-104) | 11.1 (9.6-13.0) | 15-55 % |
| D FAR=2300 + I76_MIRROR_EVERY=2 | 1 | 104.6 | 9.6 | 13 % |
| E FAR=2300 + I76_MIRROR_LOD=1 | 1 | 116.9 | 8.54 | 2.5 % |
| F FAR=2300 + LOD=2 | 1 | 114.1 | 8.75 | 5 % |
| G FAR=2300 + LOD=4 | 1 | 108.2 | 9.25 | 11 % |
| H FAR=1200 + LOD=2 | 1 | 115.9 | 8.61 | 3.5 % |
| **I FAR=2300 + LOD=1 + EVERY=2** (delivered) | r3, r4 | 118.3 / 118.3 | 8.44 / 8.44 | **1.2 %** |
| final DLL 9b7482b8 + preset OWNER-2300-MIRROR (+ dumps every 30) | smoke | 119.2 | 8.38 | (with dump cost) |

Three boots in the I-pic round carried a leaked environment (the dump run's keys stayed in the shell; md-run scrubs
`I76_*` since lab b18c472) and are not counted. Row D's EVERY=2 at LOD 24 shows the cadence lever alone is not enough;
the mirror's own LOD is what matters: a 256x64 mirror cannot show LOD 24, and the main view's x24 split constant was
being applied to it (the per-pass K already carries the mirror's focal / half-width, so LOD 1 is "stock detail per
mirror pixel").

What each switch does (all in mirrordetail.c, Gold only, signature-checked, unset = stock):

- `I76_MIRROR_FAR=<100..2500>` (existing, range widened from 600): the mirror camera's far clip.
- `I76_MIRROR_LOD=<1..256>`: the mirror pass's terrain LOD factor relative to the stock constants, independent of
  `I76_TERRAIN_LOD`. Two data floats scaled around the mirror's QueueTerrain call and restored.
- `I76_MIRROR_EVERY=<2..8>`: redraw the mirror every N-th frame. Our 6319abf7 (AiO layout) redraws it every frame; the
  2017 Galaxy exe every 2nd; 60 redraws/s at 120 fps.
- `I76_MIRROR_DUMP=<N>`, `I76_MIRROR_TERRAIN_MODE=<hex>`: lab instruments (section 1).

## 4. Delivered

- exp-polish2: `PLAY-OWNER-2300-MIRROR.bat` + `Interstate 76\presets\OWNER-2300-MIRROR.psd1` = OWNER-2300-SHADE + the
  three keys (FAR 2300, LOD 1, EVERY 2), the measured cost in the psd1 comments.
- exp-polish2 `STRLKUP.DLL`: **NOT installed** - the owner was playing exp-polish2 again when the lane reached this step
  (i76.exe started 07:46, not ours), so the copy was not touched. Until it is, the launcher runs with the 81808610 proxy,
  which rejects FAR 2300 (old range 100..600) and ignores the two new keys: the mirror stays stock. Install with the game
  closed: lab `tools\mirror-detail\install-exp-polish2.ps1` (checks md5 81808610, keeps it as `STRLKUP.DLL.81808610`,
  installs `builds
itro-port-20261021\mirror-473c16a\Strlkup.dll` md5 9b7482b8 = repo 473c16a, reads it back, notes
  VERSION-LAB.md; `-Rollback` restores). Difference to 81808610 besides this lane: b0a2420 (nitshell GAME TYPE entries,
  Nitro only, behind I76_NITRO_GAMETYPES) - inert on Gold.
- Smoke: the final DLL with the new preset booted t01 on exp-polish, the three switches logged as applied, 119 fps.

## 5. Left

- The owner's look: whether 2300 m in the mirror is worth even 1.2 %, or 1200 m (row H at LOD 2 was 3.5 %; LOD 1 at
  1200 m + EVERY 2 was not measured, it would sit under 1 %).
- Roads and bushes in the mirror still run to the preset's 2300 m (`I76_ROAD_DIST` / `I76_CLUTTER_DIST` are global); a
  mirror-only road / clutter distance is the next lever if the cost must go lower.
- Nitro: none of the sites are in the site map yet (the switches log "not ported" and stay off).
- `I76_MIRROR_RATE` (Galaxy / 20 Hz grid) and `I76_MIRROR_EVERY` share the gate site; EVERY yields to RATE.
- renderer.md's 0xf4 row for terrain / roads needs a correction (this path emits 0x15 / 0x17).
