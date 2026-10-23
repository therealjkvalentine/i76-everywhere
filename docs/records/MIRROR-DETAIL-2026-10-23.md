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

## 2. Live look

(pending: console busy - the owner was playing exp-polish2 and the game-types lane held .fps-lock)

## 3. Switches and fps cost

(pending)

## 4. Delivered

(pending)

## 5. Left
