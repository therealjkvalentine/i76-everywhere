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

## 4. Delivered (superseded by section 6 the same morning)

First delivery: exp-polish2 `PLAY-OWNER-2300-MIRROR.bat` + preset = OWNER-2300-SHADE + FAR 2300 / LOD 1 / EVERY 2, proxy
473c16a (md5 9b7482b8, installed by the coordinator; the lane had found the owner playing that copy). The owner drove it
and reported "still not seeing terrain textures ... just big one-color polys" and a sunset-orange sky in the mirror.

## 5. Left

- The owner's look: whether 2300 m in the mirror is worth even 1.2 %, or 1200 m (row H at LOD 2 was 3.5 %; LOD 1 at
  1200 m + EVERY 2 was not measured, it would sit under 1 %).
- Roads and bushes in the mirror still run to the preset's 2300 m (`I76_ROAD_DIST` / `I76_CLUTTER_DIST` are global); a
  mirror-only road / clutter distance is the next lever if the cost must go lower.
- Nitro: none of the sites are in the site map yet (the switches log "not ported" and stay off).
- `I76_MIRROR_RATE` (Galaxy / 20 Hz grid) and `I76_MIRROR_EVERY` share the gate site; EVERY yields to RATE.
- renderer.md's 0xf4 row for terrain / roads needs a correction (this path emits 0x15 / 0x17).

## 6. Second round: why "no texture, orange sky", and the fix (same morning)

Owner's screenshot (`Downloads\Screenshot 2026-10-23 080241.png`): the mirror's ground as flat ochre / orange / tan facets, the road
textured, the far terrain peach where the main view's is tan. The census had said "textured, Gouraud, perspective, mode 0x15" -
true, and three things still made it look like another world:

1. **The mirror sampled the 8-bit build's terrain art.** The terrain texture set 0x5a4588 holds, per level, the 8-bit `.map`
   (dword w, dword 0x4000xxxx | h, texels from +8) and the `.m16` (0xC000xxxx | h: texels + an embedded RGB565 palette); the
   variant picker 0x471f00(set, cam) gives a kind-0 bitmap the 8-bit one. That is a different drawing: low contrast, another
   tint (t05: peach; the .m16 sand is tan with dark speckles). The road textures' two variants happen to match, so the road
   looked right.
2. **The texture level was the 256 px mirror's.** The picker reads W from the camera's own bitmap, so the mirror got the 16 px
   tile for ~75 % of its leaves (levels 12 / 17 / 39 / 62 / 204 of 334 on t05) where the main view at the same distances uses
   the 256..32 px tiles.
3. **Not the palette.** Both ideas about the colours were wrong on inspection: the D3D upload path's `.tab` grade does not run
   here (this is the Glide plugin path, 0x42ec20 -> 0x431ca0 -> ZGLIDE UpdateTexture; the table 0x608980 is all zero and no
   `.tab` is loaded), and ZGLIDE's `SetTexturePalette` export is a stub (`xor eax, eax; ret`). The context palette 0x5dcfa8 is
   tNN_16.act plus the monitor gamma (t05: sum of differences 34 over 768 bytes), and tNN.act (the 8-bit build's, what the
   mirror's indices mean) is nearly the same palette, so an index remap is near-identity. The "orange sky" in his screenshot was
   the far terrain in the 8-bit art's tint, under a real blue sky.

Instrument additions (`I76_MIRROR_DUMP`): texture level histogram per pass, the raw-layout texture-set report, the upload table
and `.tab` dumped. (The first version of that report probed a garbage pointer with IsBadReadPtr, which the proxy's crash logger
reported as CRASH lines in six lab runs; removed.)

Switches (mirrordetail.c 8326010, Gold only, unset = stock):

- `I76_MIRROR_M16=1`: each level's `.m16` is quantised once into the display palette (its embedded palette -> nearest context
  colour, 0xff excluded) into an 8-bit copy of the same shape; the mirror pass's leaves get the copy. The main view is untouched.
- `I76_MIRROR_TEX=<f>`: the mirror's leaves re-pick the level a 640 x f px wide view would at the same distance. t05 levels with
  f = 1: 37 / 58 / 63 / 70 / 110.
- `I76_MIRROR_PAL=1`: pixels remapped tNN.act -> nearest tNN_16.act colour before the upload (25 pairs from I76.ZFS compiled in
  as `mirrorpal.h`, pair chosen by best match of the context palette). Near-identity on the stock missions; kept on as a
  safety for a mission whose two palettes differ.

Evidence (lab, PNGs on disk): `autotestuns\mirror-detail\MIRROR-DETAIL-t05-before-after.png` (stock path vs the
delivered set, dumps flipped to the screen's orientation, the on-screen mirror crop under each column) and
`MIRROR-DETAIL-t01-before-after.png`. t05 after: tan sand with its mottling, mesas in the main view's colour, blue sky.

Cost (same method as section 3, FAR 1000 per the owner's "800-1200 m is plenty"):

| condition | boots | fps (mean of the windows) | work ms | cost |
|---|---|---|---|---|
| A baseline | r6, r7 | 120.0 / 119.2 | 8.32 / 8.38 | - (spread 0.8 fps) |
| **N FAR 1000 + LOD 1 + EVERY 2 + M16 + TEX 1 + PAL** | r1, r2 | 118.8 / 120.0 | 8.40 / 8.32 | inside the spread |
| deliverable 53750675 + OWNER-2300-ALL (dumps every 40) | smoke | 120.2 | 8.31 | - |

Delivered: exp-polish2 `STRLKUP.DLL` = `builds
itro-port-20261021\mirror-8326010` (md5 53750675, repo 8326010; carries every
lane's commit up to it: jumpnose e02d64a, far-edge, terrain-pops, nitro game types), installed 09:29 with no game running; the
DLL it replaced (99af7394 = jumpnose-e02d64a, which another lane had put there after the coordinator's 9b7482b8) is kept as
`STRLKUP.DLL.99af7394` (`tools\mirror-detail\install-exp-polish2.ps1 -Rollback 99af7394`). Presets `OWNER-2300-MIRROR.psd1`
(FAR 1000 + the six keys, rows in the comments) and `OWNER-2300-ALL.psd1` (FAR 2300 -> 1000 in place, M16 / TEX / PAL added
after EVERY); launcher `PLAY-OWNER-2300-MIRROR.bat` text updated.

Left: the mirror's sky is the 8-bit cloud art through the display palette (blue-grey; the main's is the .m16 sky) - the same
.m16-copy trick would apply to the cloud texture if wanted; roads and bushes in the mirror still follow the global 2300 m;
Nitro unported; renderer.md 0xf4 row.

## 7. Third round: the daily driver's detail load, and the sky (same morning)

The trial presets had lacked the daily driver's `I76_TERRAIN_TEX=8 / I76_OBJECT_LOD=8 / I76_SHADOW_DIST=4 / I76_ROAD_TEX=8`
(now in every OWNER-*.psd1). `I76_TERRAIN_TEX` patches the picker's own `W x 40` to `W x 320` for every camera, so the stock
mirror at that load already picks as a 2048 px view at x1 would; `I76_MIRROR_TEX` is absolute against a 640 px view at x1
(its log now says both). Looks on t05 at the x8 load: TEX 1 (levels 34/57/63/64/111 of 329) and TEX 8 (223/77/33/0/0, the main
view's) are indistinguishable in dumps; 8 would sample 256 px tiles over leaves a few px wide (shimmer in motion), so **TEX 2**
is delivered (99/57/70/77/34: 10 % on the 16 px tile).

**Sky.** `I76_MIRROR_M16` now also covers the sky: the sky draw fetches the cloud texture with `0x471f00(0x504c38, cam)` at
0x4053e5 (hardware branch) and 0x405403 (software branch, the kind-0 mirror's); the latter is chained and the mirror camera gets
the 128x128 `.m16` cloud art quantised into the display palette. Its fine texels, point-sampled into 256x64, came out as speckle
(the main view bilinear-filters them), so the sky copy is box-blurred 3x3 in RGB before the quantisation; terrain copies keep
their texels. The horizon strips (0x4016e0, the far-edge lane's 0x504850 pairs) are not drawn in the mirror pass at all.
Before / after: lab `autotest\runs\mirror-detail\MIRROR-DETAIL-t05-sky-before-after.png` (8-bit cloud art: darker blue-grey;
after: the main view's pale sky, smooth).

Rows at the x8 load (OWNER-2300-ALL from exp-polish2, t05 cockpit, 5 s windows, same method):

| condition | boots | fps | work ms | cost |
|---|---|---|---|---|
| baseline = the preset with the six mirror keys dropped | r1, r2 | 120.1 / 119.9 | 8.31 / 8.32 | - |
| the six keys, MIRROR_TEX=2 | r1, r2 | 119.8 / 119.6 | 8.33 / 8.34 | 0.3 % |

Build note: the pulled main did not compile for a while (4321e4a used `g_ss_on` before its declaration; 509ed6b fixed it), and
`mirrorpal.h`'s generated first line carried a literal CR and FF (MSVC C4335), fixed in 239a123.

Delivered: exp-polish2 `STRLKUP.DLL` = `builds\nitro-port-20261021\mirror-5006d8c` (md5 5b48d79f, repo 5006d8c), the replaced
DLL kept by md5; `OWNER-2300-MIRROR.psd1` and `OWNER-2300-ALL.psd1` carry TEX 2 and the sky note (M16 covers both).
