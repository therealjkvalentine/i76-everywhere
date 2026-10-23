# Terrain pops after the geomorph: what still pops, and why (2026-10-23, terrain-pop lane)

The owner, driving exp-polish2 PLAY-OWNER-2300-ALL (stateless geomorph 0.25 of the ring, shade fade x3, big tiles blended, proxy
9b7482b8 = i76-everywhere 473c16a + the mirror lane): *"i still see the same abruptness in the darkness of the terrain and on some of
the parts not morphing smoothly."* Two classes: (A) abrupt brightness ("darkness") changes of terrain areas, (B) geometry that still
snaps. This record finds what they are, with instruments, on the lod-sweep ridge route (T05 mission start, 12 s still, 24 s drive;
lab copy exp-rebase, the owner's preset copied in). Code: `music-fix/terrainpops.c` (6f14a77 instruments; fix 1ac22b3 -> b461bf8 -> 596a597), `terrainmorph.c` row-crossing columns (13e56df).

## 0. Short answer

- **Class A ("abruptness in the darkness") is the hardware shade's 32-row quantisation, not the morph and not the texture levels.**
  Every polygon emitter maps the vertex shade to `round(31 s)` into a 64-entry grey table (s.1.1); on T05 that is ~16 distinct greys
  20-23 apart. The census of what ZGLIDE receives (s.4.3): 100 % integer vertex colours, 15-16 levels, flat ground at 185 / 164 / 143.
  While driving the ridge route, **200 terrain vertices per second within 300 m cross a row (2.4 per frame), 260/s at 300-900 m,
  1030/s beyond** (s.4.5, n 2, spread 1 %) - each a ~12 % brightness step over that vertex's fan (a 20 m tile at 150 m is ~200 px
  wide in the cockpit). The morph's shade fade walks the same steps, which is why "slow shade fade x3" did not read as a fade.
- **Fix built and installed for the owner to judge: `I76_SHADE_SMOOTH=1`** (terrainpops.c, final 596a597 / proxy 13e56df): a
  256-entry table interpolating the stock rows, 34 byte-sites, no measurable fps cost (84.6-86.3 vs 84.5-86.7). Census after:
  32-40 levels, the mass spread over 141-187 instead of three values (s.4.4-4.5). Preset `OWNER-2300-SMOOTH` (= ALL + the four daily
  driver detail keys + SMOOTH + BIG 2), launcher `PLAY-OWNER-2300-SMOOTH.bat` in exp-polish2, DLL 1790a308 installed (previous kept).
- **Class B ("parts not morphing smoothly") is, by the instrument, the big tiles' sliding**: `I76_TERRAIN_MORPH_BIG=1` blends the 64+
  sample tiles' heights against a root square that re-aligns with the camera, so carried vertices move > 16 px in one frame at 480-525
  px/s and the far band runs 1500-1650 px/s (stock 383; 132 with BIG unset or BIG=2). **BIG=2** keeps the big tiles' shade blend (what
  BIG was adopted for) with stock heights: carried 0, far 132 (s.4.2). In the deliverable. What remains after that: merges away from
  the ring (~210 px/s > 16 px, the same with the morph on or off; a merge blend needs the previous frame's state = the table form's
  cost) and the error-step births (114-119 px/s vs 943 stock).
- **Ruled out:** texture level switches (TEX x16 moves every ring out, nothing changes; 1.2-1.6 switches per frame at 640 / 1280 /
  2560 m with the daily driver's TEX x8), the morph itself as a brightness-step source (NOMORPH = ALL on the screen instrument).
- **The screen-difference instrument cannot see the shade rows** (SMOOTH = ALL on it, n 3 / 4 vs 5): at 23 captures/s and 80 px
  blocks it measures the ground texture sliding under the car. It did its job for what it can see (texture levels, morph, BIG) and
  was replaced by the in-engine count for the rows. Its PNG pairs are in the capture folders; the top of every list is the two road
  signs passing.

| pop class | cause | evidence | share | fix | cost |
|---|---|---|---|---|---|
| A: abrupt darkness changes of terrain areas | 32-row shade quantisation in the 17 hardware emitters (s.1.1) | census 15-16 levels (s.4.3); 200 / 260 / 1030 row crossings per s near / mid / far while driving, 2.4 per frame near (s.4.5) | all of class A that is terrain-shade (the other candidates measured nil) | `I76_SHADE_SMOOTH=1` (built, census-verified) | none measured (34 patched bytes, same instructions) |
| A: texture level switch of a tile | picker 0x4923f0 (s.1.2) | 1.2-1.6 per frame at 640 / 1280 / 2560 m; TEX x16 = ALL on screen | not measurable | - (I76_TERRAIN_TEX already x8 for the owner) | - |
| B: far ground sliding | BIG=1 big-tile height blend (s.4.2) | carried > 16 px 480-525 px/s, far 1500-1650 vs 132 | the largest geometry class with the morph on | `I76_TERRAIN_MORPH_BIG=2` | none |
| B: merges away from the ring | error-step merges vanish in one frame | gone > 16 px ~210 px/s, morph on or off | second | merge blend needs previous-frame state (table form, ~27 fps in F6) - not small | high |
| B: births the morph only partly covers | error-step splits inside the ring | born > 16 px 114-119 px/s (stock 943) | third | wider band / lower LOD error threshold | small, not built |
| B: roads / bushes / signs | not terrain vertices | the top screen events are the two road signs; bushes thin by distance | visible but not "terrain" | I76_ROAD_TEX x8 already; bush fade is a preset choice | - |

## 1. The mechanisms, as read in i76.exe 6319abf7 and ZGLIDE.DLL 05c1dde4

### 1.1 The hardware vertex shade is quantised to 32 rows (class A)

The terrain's per-vertex shade (0x490fb0: s = max(0, L.y - Sx L.x - Sz L.z) x g(z) + A, with the depth term
g(z) = clamp(0.7496 + 0.000417 z, 0.75, 1), s capped at 1) is a float in [0x5dd2ec]+8. It never reaches Glide as a float. Every hardware
polygon emitter (17 sites: 0x427edb, 0x427fc3, 0x42834b, 0x42861c, 0x4287bb, 0x428861, 0x429439, 0x42975a, 0x429b77, 0x42b86c, 0x42bb5a,
0x42beac, 0x42c19a, 0x42c509, 0x42c82d, 0x42c969, 0x42cc8d; e.g. 0x4282e0) does, per vertex:

```
fld   [vertex + 0x14]          ; s
fmul  [0x4bcd34]               ; x -31.0
fsubr [0x4faf18]               ; 2^52 + 2^51 magic: the low dword is round(31 s)
add   ebx, [0x5280b0]          ; + 16
mov   ebx, [ebx*4 + 0x526790]  ; the 64-entry grey table (entries -16..47)
and   ebx, 0xff
mov   [out + 0x10], ebx        ; ZGLIDE's vertex: +0x10 intensity, +0x14..0x16 the polygon colour bytes (white for textured)
```

ZGLIDE's draw (0x10002a80) then sets r = g = b = colour_byte x intensity >> 8 per GrVertex and iterates that across the triangle
(Gouraud is smooth INSIDE a triangle; the vertex values are the quantised ones). ZGLIDE's exported `SetLumaTable` is a bare `ret`: the
plugin has no table of its own; the exe's is the one that counts. The table is built by 0x426c30 from the current palette and .lum
(renderer.md 2026-10-07c: T[row] = Ymax x (Y(lum[row][white]) / Ymax)^1.4; index 16 + k holds row 31 - k, entries below 16 repeat row 31,
above 47 row 0). Computed from t05.act / t05.lum (zfs_out), rows 0..31:

```
255 255 255 255 255 255 255 255 | 232 232 209 209 187 187 165 165 | 165 145 145 125 125 106 106 87 | 87 70 70 70 54 54 39 39
```

So on T05 (period P3, L.y = cos 55 deg = 0.574) a vertex's brightness is one of ~16 distinct greys, 20-23 apart (12 % steps), and
it steps whenever its shade crosses a row boundary k = round(31 s):

- flat ground: s = 0.574 x g(z) runs 0.43 (near) .. 0.574 (far): k = 13 .. 18, greys 145 / 165 / 187 - **two steps of 22 grey, at
  z = 291 m (k 15 -> 16) and z = 157 m (k 14 -> 15), fixed rings about the camera that every flat vertex crosses as the car approaches**;
- slopes: s differs per vertex, so neighbouring vertices sit on different rows and the ring distances differ per slope;
- the geomorph's shade fade (the blended value walks from the parents' mean to the vertex's own) crosses the same rows: a 3-row fade is
  three 22-grey steps, not a ramp. The fade is linear in s; the screen is not.

Nothing in the morph can touch this: the quantisation happens after the shade loop, in the emitters. It is also why the 2026-10-21 shade
numbers (per-split shade step 0.306 -> 0.0036, "78 -> 0.9 grey on a white texel") overstated what the screen shows: a 0.0036 step in s
is nothing until it crosses a row, and then it is 22 grey.

### 1.2 Texture level switches (class A candidate 2)

The per-leaf picker 0x4923f0 chooses the terrain texture level from the leaf's nearest-vertex depth z:
level = clamp(9 - floor(log2(640 x 40 / z)), 0, 6): the 256 px texture to 50 m, then 64 / 64 / 32 / 16 px at 100 / 200 / 400 m
(T05's set is tp08: tp082sd6 .. tp086sd6). ZGLIDE uploads one level per texture and never mipmaps (lab TEXTURE-AND-OBJECT-LOD.md), so a
leaf crossing 50 / 100 / 200 / 400 m swaps its whole texture in one frame. Instrument: `I76_TEX_LEVEL_LOG`. Switch that moves every
boundary out: `I76_TERRAIN_TEX=<f>` (x16 puts the 256 px level out to 800 m).

### 1.3 Road texture set at 60 m, bush thinning, road segment culling (class B candidates)

Roads: a segment's texture slot set flips at midpoint z = 60 m (0x48ec16, `I76_ROAD_TEX`); segments appear at I76_ROAD_DIST. Bushes: full
density to I76_CLUTTER_FADE (300 m), thinned as (300 / d)^2 per bush beyond. None of these are terrain vertices; the morph does not see
them.

## 2. Instruments (terrainpops.c 6f14a77, lab, off by default)

| switch | what |
|---|---|
| `I76_SHADE_CENSUS=1` | ZGLIDE's grDrawTriangle hooked: histogram of the integer r of every vertex, reported every 600 frames (how many distinct levels carry >= 0.2 %) |
| `I76_TEX_LEVEL_LOG=<csv>` | per main terrain pass: leaves per level, leaves whose level differs from the previous frame (by the picker's z band, nearest), one event line per switch; the picker site 0x490f96 is chained behind whatever push is there (mirror-detail's stub included) |
| `I76_TERRAIN_MORPH_LOG=<csv>` | the morph lane's instrument (per pass max one-frame vertex move in px, births / merges / shade jump) |
| lab `tools\terrain-pops\tp_capture.py` | the screen at ~23 Hz (mss, green channel, 1/4-scale stack kept as frames.npy); per consecutive pair the largest 80x80 px block's mean |delta| minus the frame's median block (the car's own motion), top pairs saved as full-resolution PNGs with a x4 difference image; QPC-stamped so the rows join the proxy logs |
| lab `tools\terrain-pops\tp-run.ps1` / `tp-queue.ps1` / `tp_tab.py` | the ridge route on exp-rebase with the owner's OWNER-2300-ALL preset + the instruments, one run per console lock; the join table |

## 3. The fix built: `I76_SHADE_SMOOTH=1` (terrainpops.c 1ac22b3, lab, Gold)

The 17 `fmul [0x4bcd34]` sites are pointed at -255.0 and the 17 table displacements at a 256-entry table (16 guard entries below, 64
above, as the stock's index arithmetic needs) that interpolates the stock rows linearly: entry k = T(31 k / 255). It is rebuilt from the
frame hook whenever the stock 64 entries change (the mode slot rebuilds them from the current palette / .lum). Nothing else changes: the
same rows at the same shades, a ramp between them instead of a step. Objects and roads go through the same emitters, so they lose the
stepping too (their shade formulas are untouched). Cost: none measurable in principle (same instruction count); measured in s.4.
Signature-checked at all 34 bytes-sites, all or nothing.

## 4. Measurements (lab exp-rebase, ridge route, cockpit, the owner's OWNER-2300-ALL preset)

**Load.** Every row below carries the daily driver's four detail keys main added to the preset on 2026-10-23 (`I76_TERRAIN_TEX=8`,
`I76_OBJECT_LOD=8`, `I76_SHADOW_DIST=4`, `I76_ROAD_TEX=8`) - the corrected load. Three earlier boots (void-nopreset-*) loaded no preset
at all (the runner looked in the wrong folder: stock terrain, no morph, no tick) and are struck. With TEX x8 and the main camera's
1024-wide bitmap the texture-level rings sit at 640 / 1280 / 2560 m (the level log's switch distances say so: 639-640, 1280, 2559 m).

Conditions, all through tp-run.ps1 (proxy 509ed6b = 19ca3b5c unless said; same route, 12 s still + 24 s drive, ~23 captures/s):
**ALL** = the owner's preset as is; **SMOOTH** = ALL + `I76_SHADE_SMOOTH=1`; **TEX16** = ALL + `I76_TERRAIN_TEX=16` (rings at 1280 / 2560 m);
**NOMORPH** = ALL minus the four morph keys.

### 4.1 Screen: local brightness steps in the terrain band (tp_mask.py; y 400..1200 of 3440x1440, mirror box excluded)

Per consecutive capture pair: the largest 80x80 px block's mean |delta green| minus the median block (the car's own motion). The top
of every run's list is the two "EAST 380" road signs whipping past (the same route points in every run; pairs ~575-605 and ~730-760), so
the tail (p99 / max) is signs, not pops; the body of the distribution is what the owner sees as flicker / abruptness.

| condition | n | score p50 | p90 | p95 | pairs >= 20 grey | pairs >= 40 grey | events >= 20 in the left / centre / right third | fps (frames.csv, whole run) |
|---|---|---|---|---|---|---|---|---|
| ALL | 3 | **18.6 / 19.8 / 19.1** | 41.3 / 43.2 / 43.0 | 55.7 / 55.5 / 55.0 | **395 / 432 / 411** | 96 / 107 / 102 | 231 / 105 / 60 (all-1) | 86.7 / 84.5 / 85.4 |
| SMOOTH (b461bf8: smoothing right, +2 rows too bright, s.4.4) | 3 | 20.9 / 20.5 / 20.2 | 43.9 / 41.9 / 40.7 | 54.5 / 52.6 / 50.7 | 479 / 465 / 460 | 105 / 102 / 99 | 315 / 102 / 63 (smooth-1) | 84.3 / 86.4 / 85.6 |
| BIG=2 (shade only) | 1 | 18.7 | 43.1 | 52.0 | 402 | 107 | - | 85.0 |
| TEX16 | 1 | 19.0 | 38.4 | 52.9 | 407 | 83 | - | 86.9 |
| NOMORPH | 1 | 19.0 | 42.2 | 52.2 | 412 | 107 | - | 88.0 |
| BIG unset (ALL minus I76_TERRAIN_MORPH_BIG) | 1 | 18.9 | 41.8 | 55.3 | 404 | 104 | - | 86.5 |

- **This instrument does not see the shade rows.** With the 32-row steps removed (SMOOTH, census s.4.4: a continuum) the local step
  score is ALL's or a little above it (20.5 vs 19.2 mean; that build sat 2 rows brighter, which scales the texture's own contrast up
  ~7 %). At ~23 captures/s (4-5 game frames per pair) and 80 px blocks the body of the distribution is the ground texture sliding
  under the car and the bushes, not a vertex's 21-grey step spread over its Gouraud fan. So the screen rows say what the pops are NOT
  (texture levels, the morph, the big tiles) and cannot rank the shade rows; the in-engine count (4.5) does that.
- **Texture level switches are not a measurable share at TEX x8:** TEX16 moves every ring to twice the distance and changes nothing
  (19.0 / 407). The level log counts 1.2-1.6 switches per pass at 640 / 1280 / 2560 m (0 under 100 m); a 20 m tile at 640 m is ~50 px.
- **The morph is not a measurable share of brightness steps either:** NOMORPH reads as ALL (19.0 / 412); BIG unset reads as ALL too.
  Its effect is in geometry (4.2).
- **Void rows, kept for the record:** smooth-1..3 and smoothbig0-1 on proxies 1ac22b3 / 509ed6b / 4809f81 (capturesoid-table-*)
  read p50 7.7-8.2 and 158-186 pairs >= 20 - but the census (4.3) showed their terrain drawn at grey 38-68 instead of 143-185: the first
  table read the wrong half of the stock table (b461bf8 fixes it). A dark, compressed shade range has fewer steps for the wrong reason.
  Nothing from those rows is used.

### 4.3 Census: the vertex colour ZGLIDE receives (I76_SHADE_CENSUS, 600-frame windows, all-3 and big0-1, proxy 4809f81)

`3.8-4.0 M triangles, 11.5-11.9 M vertices, 0.00 % non-integer r; 15-16 integer levels hold >= 0.2 % each:` 38 (25-28 %), 143 (5-12 %),
164 (12-20 %), **185 (33-42 %)**, then 2, 7, 28, 36, 52, 68, 85, 104, 123, 207, 230, 254 at 0.2-3.6 %. That is the T05 table of s.1.1 to the
digit (rows 13 / 15 / 17 = 187 / 165 / 145 x the polygon colour byte 254 / 256 = 185 / 164 / 143; 38 = row 31 = shade 0, the faces turned
from the sun and the cockpit's dark polygons; 254 = row 0..7 = full bright). **Every terrain vertex on T05 is drawn at one of ~16 greys**;
flat ground alternates between three of them (185 / 164 / 143) by distance, and a vertex moving from one to the next is a 21-grey step.

The void smooth rows' census (28-29 levels, the mass at 63 / 38 / 52) is what exposed the table bug: with the right rows the comb should
hold the same mass around 143-185 spread over the entries between.

### 4.2 Geometry: one-frame vertex moves by class (the morph lane's instrument, drive phase, px/s of moves > 4 px in one pass)

| condition | near < 300 m | mid | far > 900 m | > 16 px moves: carried | born by a split | view-edge | gone (merge) | 4-16 px: carried | born | per split: max move p50 / p95 px | shade step p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOMORPH (stock terrain) | 427 | 824 | 383 | 0 | **943** | 97 | 225 | 0 | 313 | 2.3 / 35.8 | 0.217 |
| ALL (n 2) | 44 / 55 | 189 / 381 | **768 / 1623** | **260 / 524** | 114 / 119 | 17 / 31 | 24 / 198 | 508 / 1079 | 75 / 80 | 0.1 / 9.7-12.4 | 0.029-0.040 |
| SMOOTH (n 2) | 54 / 56 | 393 / 378 | 1640 / 1630 | 525 / 513 | 117 / 121 | 31 / 34 | 214 / 209 | 1092 / 1079 | 80 / 81 | 0.1 / 12.4-12.7 | 0.042 |
| TEX16 | 56 | 361 | 1460 | 467 | 116 | 40 | 206 | 938 | 80 | 0.1 / 12.2 | 0.042 |

- The morph removes the split pops as the 10-21 record said (born > 16 px: 943 -> 114-119 px/s; per split p95 35.8 -> 10-12 px).
- **What it adds:** a class that does not exist in the stock - **carried vertices moving > 16 px in one pass, 260-525 px/s, and the far
  band (> 900 m) at 2-4x the stock's** (383 -> 768-1623). That is `I76_TERRAIN_MORPH_BIG=1`: the 64+ sample tiles' blend follows the
  root square, which re-aligns as the camera moves, so their blended heights jump (75b8888 left them at t = 1 for this reason; the
  owner then asked for BIGBLEND and saw no sliding). Far away each jump is small on screen but there are many. Row big0-1 (BIG unset)
  measures it directly (4.3).
- **BIG unset (big0-1): carried > 16 px 0, far band 135 px/s (stock 383, ALL 770-1623), born 114, gone 220** - the sliding is the big
  tiles' blend and nothing else; without it the far band is quieter than the stock. Its screen score is ALL's (4.1): the sliding is a
  geometry motion, not a brightness step. big2-1 (BIG=2, shade only) is in the queue: the big tiles' shade blended, their height stock.
- **BIG=2 (big2-1): the same geometry as BIG unset** (carried 0, far 132, born 116, gone 211) with the big tiles' shade still blended:
  the big tiles' height blend is the only thing BIG=1 adds, and it is the sliding. BIG=2 is the deliverable's setting.
- Merges ("gone", 200-225 px/s > 16 px) are the same with the morph on or off: the stateless t is 0 at the ring, so a ring merge is
  free, and what remains are merges away from the ring (the error-threshold steps flipping back) - a merge blend would need the previous
  frame's state (the table form) to cover them. View-edge entries (17-40) are the instrument's floor.

### 4.4 SMOOTH on b461bf8 (smooth-1..3): the census

`3.9 M triangles, 11.8 M vertices, 0.00 % non-integer r; 40 integer levels hold >= 0.2 % each:` the stock's three flat-ground greys
(143 / 164 / 185 = 50 %) become a spread over 158-230 with 0.2-1.8 % at every intermediate value (164: 11.5 %, 185: 5.6 %, 200: 24.5 %,
the rest between). The steps are gone from the vertex colours. The modes sit 16 entries above the stock's (38 -> 51, 185 -> 200): b461bf8
passed the table's address + 16 while the emitters add 16 to k themselves, so that build drew everything about 2 rows (6-8 %) brighter;
596a597 passes the table's address (smooth-4 confirms the modes back at 38 / 185 with the spread: s.4.5). Self-check line of the build:
`rows 12..18 now 186 186 165 165 165 144 144 -> entries k 128 / 145 / 160 = 165 178 196` (the interpolation between the rows).

### 4.5 In-engine: how often a vertex crosses a shade row (proxy 13e56df, instrument 13e56df in terrainmorph.c)

Per main pass, the carried terrain vertices (in both this and the previous pass) whose `round(31 s)` differs from the previous pass -
under the stock emitters each is a one-frame step of 20-23 grey over that vertex's fan. The same count with SMOOTH says how many of
these the fix turns into 1/255 steps (the float shade is untouched; the instrument rounds it the stock's way).

| row | phase | passes | verts / pass | row crossings per s: near < 300 m | mid | far > 900 m | near per frame |
|---|---|---|---|---|---|---|---|
| all-4 | still (handbrake, idle shake) | 1066 | 6458 | 84 | 145 | 1274 | 1.0 |
| all-4 | drive | 2312 | 6199 | **202** | **263** | **1038** | **2.4** |
| all-5 | drive | 2352 | 6205 | 200 | 259 | 1026 | 2.3 |
| smooth-4 | drive | 2351 | 6222 | 209 | 405 | 2408 | 2.5 (the same crossings, now 1/255 steps) |

At ~85 fps that is 2.4 near vertices per frame stepping 12 %; a 20 m tile at 150 m spans ~200 px of the 3440 (121.7 deg cockpit).
Even the parked car (the idle shake moves the eye) makes 84 near crossings per second: the "darkness changes" the owner sees while
stopped on the ridge. smooth-4's census (offset fixed): `32 integer levels hold >= 0.2 %: 38 27.6 %, 143 3.0 %, 164 12.2 %, 180 23.9 %,
185 4.6 %` and 0.2-3 % at every value 141-187 between; self-check `entries k 128 / 145 / 160 = 165 178 196`.

## 6. Owner follow-up (afternoon): "textures in ATMOS and SMOOTH are still coarse / distracting brightness adjustments"

**What he ran.** exp-polish2's `mciproxy.log`, last boots: `shade-smooth: on ... rows 12..18 now 186 186 165 165 165 144 144 -> entries
k 128 / 145 / 160 = 165 178 196` - the fixed table (596a597 is an ancestor of the installed 2516fb4 / bc2b0b9b). SMOOTH was live; the
32-row steps were gone from the vertex colours (s.4.5's census). What remains is something else.

**Is a texture level ring a brightness step?** No - measured in the archive (I76.ZFS `tp08m6.pak`, the set T05 names, RGB565 palettes
through i76fmt):

| level | file | size | mean luma | luma sd (contrast) |
|---|---|---|---|---|
| ('1', unused by the picker) | TP081SD6.M16 | 16x16 | 133.6 | 8.1 |
| 0 | TP082SD6.M16 | 256x256 | 133.1 | 16.2 |
| 1 | TP083SD6.M16 | 64x64 | 133.2 | 12.8 |
| 2 | TP084SD6.M16 | 64x64 | 133.2 | 12.8 |
| 3 | TP085SD6.M16 | 32x32 | 133.6 | 10.2 |
| 4-6 | TP086SD6.M16 | 16x16 | 133.0 | 8.2 |

The levels differ by 0.6 grey in mean - a ring is not a darkness step and no per-level gain is needed. They differ in CONTRAST: each
ring drops the texture's grain by ~20 %, and inside the 640 m ring (TEX x8) the 256 px level is drawn minified with no mipmaps (ZGLIDE
uploads one level, lab TEXTURE-AND-OBJECT-LOD.md s.1): at 640 m a 40 m tile is ~100 px, 2.5 texels per pixel, bilinear only - aliasing
grain that moves with the car. Read with the owner's own words ("continuously faded the same way as we continuously make the transition
between textures"), the remaining "coarse brightness adjustments" are texture detail, not shade: the grain changing abruptly at the rings
and sparkling under minification. On flat ground the rings sit 1-2 px below the horizon (h 1.2 m x focal 960 px / 640 m), so a
luma-vs-distance profile cannot resolve them; the slopes are where he sees them.

**The remaining per-vertex candidates are not it:** the depth term is float per vertex (0x490fb0, s.1.1); ZGLIDE's intensity x colour is
8-bit (1-grey steps); dgVoodoo iterates Gouraud in float.

**Fix built: `I76_GLIDE_MIPMAP=1|2`** (terrainpops.c 8907869, proxy e5f4a750). ZGLIDE has a complete mip-chain path the exe never
switches on: FirstDevice (+0x1c20) zeroes the plugin's mipmap flag [0x1001ee68] and then calls grTexMipMapMode(tmu, flag ? NEAREST :
DISABLE, FXFALSE); with the flag every upload gets smallLod = GR_LOD_1 and 0x10005160 builds the chain. 1 = the one byte at +0x1c60
(`mov [flag], edi` -> `mov [flag], ebx`, ebx = 1 there): mip chains, nearest mip. 2 = lodBlend forced FXTRUE through the glide2x import:
trilinear under dgVoodoo - the levels fade into each other with distance, and with `I76_TERRAIN_TEX=32` the picker keeps the 256 px level
out to 2560 m so the hand-made rings are gone and the mips do the whole transition. Relocation-aware (ZGLIDE loaded at 046C0000 in the
owner's boots), signature-checked, Gold, off by default. Rows (pending the console after the TEX sweep): sm (SMOOTH + BIG 2), mip1,
mip2, mip2 + TEX 32, n 2, same route and instruments; the capture's local-step p50 is the grain / shimmer measure here.

## 5. Files

- Code: i76-everywhere `music-fix/terrainpops.c` (6f14a77 instruments, 1ac22b3 fix), `strlkproxy.c` (include, report, apply, frame hook, census hook).
- Builds: `i76-uncap-lab\builds\nitro-port-20261021\tpops-1ac22b3\Strlkup.dll` b29fa468 (tpops-6f14a77 42510533 = instruments only).
- Runners: `i76-uncap-lab\tools\terrain-pops\` (tp-run.ps1, tp-queue.ps1, tp_capture.py, tp_tab.py, results.txt).
- Captures: `i76-uncap-lab\captures\terrain-pops-20261023\<tag>\` (cap\pair-NN-{a,b,d}.png, cap\frames.npy, cap\caps.csv, tex.csv, morph.csv, frames.csv, mciproxy-run.log, summary.txt).
