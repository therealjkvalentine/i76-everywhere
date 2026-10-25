# Terrain pass optimisation plan (2026-10-25) - design lane; an implementation lane executes it

Owner's questions: "What happened to not redrawing all vertices every frame?" and, generally, what can be optimised or
offloaded while keeping the accepted look (RENDER-FINISH-2026-10-23: OWNER-2300-ALL = SMOOTH, stateless morph 0.25 / SHADE 3 /
NEAR 100, TEX 8, SPARSE 0.5 / 450 + alpha fade 150, FEATHER fog 0.75 + alpha, LOD 24, far 2300).

Inputs: FRAME-PROFILE-2026-10-25 (PARTIAL) and its retained raw capture (lab `captures\frame-profile-20261025\a1-sample-085211.*`),
music-fix `terrainmorph.c` / `faredge.c` / `terrainpops.c` / the clutter and terrain-LOD blocks of `strlkproxy.c`, i76-map
`subsystems/renderer.md`, lab `TEXTURE-AND-OBJECT-LOD.md`, `TERRAIN-DROPOUT-HILL-2026-10-12.md`, today's no-instrument laptop runs
(`captures\analog-driver-20261025\an-r4..r6*.mciproxy.log`, same preset keys as the owner's set). No new game run: the laptop lock is
held by a live lane (analog-driver, pid 15900, i76.exe up) and the desktop console is the owner's; everything below that needed a
number has one from retained data, and the plan's own first unit is the instrument build that measures the rest.

## 0. Three verdicts and one correction, up front

| question | verdict |
|---|---|
| Incremental quadtree (keep split decisions across frames) | **Don't**, not on this engine. Bounded saving ~0.3-0.4 ms (the decision tests are ~3 % of the frame; the other ~12 % of game terrain time - vertex creation, view transform, shade, emit, clip, bucket insert - must run every frame because every vertex's view-space position and the painter's buckets change with the camera). What it breaks: the per-pass arena the rear mirror's pass reuses, the int16 vertex pool, the LOD rings moving with the camera (a cache is a freeze: `I76_TERRAIN_FREEZE` already is that experiment, judged on look), binoculars (zoom 8 changes K: every cached decision wrong at once). **Later** only inside the renderer-replacement tier, where a persistent mesh is the natural form. See s.3. |
| Batching grDrawTriangle from our side | **Possible without touching dgVoodoo** (Glide 2.x `grDrawPolygonVertexList`, ZGLIDE's Render op fans one record into n-2 `grDrawTriangle` calls: ~6,400 calls for ~3,400 records per frame), **bounded ~0.3-0.8 ms of the 3.6 ms translation bucket**, and only worth it if the probe (unit U1) shows dgVoodoo's cost is per call rather than per vertex. Do the probe; decide then. See s.4. |
| PeekMessageA 23.6 % | **Solved from the retained samples: it is not in the frame at all.** All 19,042 PeekMessage samples have terrain vertex count 0 (the ~50 s boot / load / shell period before the mission, where the loop spins on `PeekMessageA`), and 0 of the 50,325 in-mission samples are in it. The hill-leg filter was by player x alone, and the stale pre-mission x (8078) lies inside 6400..8900. No experiment needed; the 1x-vs-2x render test is no longer required for this question (the GPU at 15 % already answers the GPU-bound question). See s.5. |

**Correction to FRAME-PROFILE-2026-10-25 (two instrument artefacts).** (1) The PeekMessage row, above. (2) "terrain pass, proxy code
13.5 %, own cost 1.6-2.0 ms per pass": the profile boots ran with `I76_TERRAIN_MORPH_LOG` set (fp-run.ps1 sets it in every mode), which
turns on the morph's hash-table instrument (`tm_vput` / `tm_vfind` / `tm_lput` for every vertex and leaf, every main pass). The hot
block Strlkup+4b700 (5.3 % of all samples, 7.9 % of in-mission) is `tm_hash` (the 0x9e3779b97f4a7c15 multiply; lab
`tools\frame-profile\fp_hotblock.py` finds the six inlined copies at +4b723 / +4bbe8 / +4c0b7 / +4c7c0 / ...). The owner's build runs the
morph STATELESS ("without the instrument: no tables at all", terrainmorph.c:251): its own timer reads **75-147 us per pass** (laptop
today, 15 windows over 3 runs, p50 ~108 us; 2026-10-24/25 captures on other lanes 77-147 us), against **1,867-2,930 us** in the four
profile boots. So the proxy's terrain share in the owner's build is ~1 %, not 13.5 %, and ~1.8 ms of the profile's 11.9 ms frame was the
profiler's own instrument. (This is also most of why the owner's 90-110 fps was "not reproduced" at 74-87.)

**Corrected in-mission pie** (a1-sample, 50,325 samples with verts > 0, 11.9 ms mean frame, 1 % = 0.12 ms; exact by eip; lab
`fp_analyse.py --verts-min 1`, `fp_remine.py`):

| bucket (exclusive, by module) | % | ms | what |
|---|---|---|---|
| dgVoodoo Glide2x.dll + D3D11 / DXGI / nvwgf2um + ZGLIDE | 16.1 + 8.6 + 5.9 = **30.6** | 3.6 | the Glide -> D3D11 translation of ~6,400 triangles / ~3,400 records per frame (far-edge probe: 1.78-1.87 M triangles per 300 frames inside the flush, ~180 per frame outside it) |
| i76.exe | 28.3 | 3.4 | terrain tessellation + transform + shade + emit + clip + bucket insert ~15 (SubdivideTerrainQuad 2.3, InsertDepthBucket 2.0, GetTerrainSampleRaw 1.8, EmitTerrainPolys 1.6, ClipPolyTextured3D 1.6, 2D 1.4, rsqrt 1.4, ShadeTerrainVertex 1.3, PlaneFrom3Points 1.1, SplitTerrainEdge 0.6), flush walk / DrawPolyHW ~4, clutter 3.7, mirror 1.9, roads 1.8, rest |
| Strlkup.dll | 21.6 | 2.6 | **~15 of it the morph LOG instrument** (blocks +4b400..+4c800); the rest ~6: stateless morph + edge wrap + emit blend (~1, timer-measured), fade hook per triangle, clutter hooks, DLL-internal CRT |
| system (ntdll / KERNELBASE / msvcrt / win32u) | 18.2 | 2.2 | **ZwOpenKeyEx + ZwOpenKey 4.1 under the sound update `shell_cb_10` 0x421400** (called once per loop iteration from the main loop); **msvcrt `_tolower_l` (stricmp) + memmove + KERNELBASE MultiByteToWideChar ~4.7 under `image_LoadM16Variant` 0x471980 / `renderer_ReleaseM16Texture` 0x471b70** (reached inside the clutter and mirror chains); heap / misc ~2; no PeekMessage |

Phase-inclusive (heuristic call-chain, stale-frame risk): terrain queue 32 % (19 % of it the log instrument), draw flush 36 %, clutter
11-13 %, sim/sound 7.6 %, mirror 2.3 %, roads 2 %, loop body 7 %.

## 1. Our terrain hooks: cost model, baseline, ranked changes

### 1.1 What runs, per frame / per node / per vertex (owner's build)

The proxy touches the terrain pass at four places (terrainmorph.c, faredge.c, terrainpops.c):

| hook | where | per what | work |
|---|---|---|---|
| `tm_edge_wrap` | the five edge-split calls in the quadtree's split block (0x491681..0x4916e2) | per **edge split** (one new vertex; ~6,300 vertices per pass, ~1,500-2,000 of them inside split rings) | reads `[0x6442ec]` before / after the stock call, stores two int16 parents + a pass id: ~10 instructions, 3 array writes. No divisions. |
| `tm_stateless` pass 1 (in `tm_xform_wrap`, before the exe's view transform 0x4937c0) | once per pass, loop over vertices 4..n | per **vertex**: skip unless split this pass (`g_ep_s[i] != pid`: one compare for ~65 % of vertices); for a split vertex: 6 float loads, 2 `fabsf`, an int round, the midpoint-vs-centre branch (centre: 4 more parent loads + a min / max scan of 4), `d2`, `D2 = S^2 K`, the error step (`memcpy` bit trick = floor_pow2, no log), one early-out without a square root (`d2 <= D2 (1 - band)^2`), then at most **2 `sqrtf`** (D and d) for vertices inside or near their ring, a few compares; a listed vertex writes 5 ints / floats | ~40-60 instructions for a split vertex, ~2 for the rest; **no divides** (invB hoisted); 2 sqrt only for ~1,400-1,950 listed vertices ("vertex-passes morphing 1,364-1,950 per pass") |
| `tm_stateless` pass 2 | per **listed vertex** | 3 loads, 1 lerp (2 mul-add), 1 store: y = ym + (y - ym) t |
| `tm_emit_wrap` shade blend | per **listed vertex**, once per pass, after the exe's shade loop | 3 loads, 1 lerp, 1 store on U[3j+2] |
| `fe_haze_apply` | off in the owner's set (`I76_HAZE` unset; the feather uses `I76_GLIDE_FOG_ALPHA`) | - |
| `fe_DrawTri` (IAT hook on ZGLIDE's `grDrawTriangle`) | per **triangle**, every triangle of the frame (~6,400 inside the flush) | inside the flush with the opaque override on: per vertex `1/oow` (**a divide**), `(w - z0) * inv`, a compare, smoothstep (3 mul) and the alpha store for the far band; the alpha store (255) for every vertex; plus the probe's min / max bookkeeping (4 compares per triangle) and the `CL_TR` macro test. Outside the flush: the bookkeeping only. |
| `fe_Blend` / `fe_ACombine` / `fe_Chroma` (IAT) | per ZGLIDE state request (a few hundred per frame) | compares, occasional pass-through |
| `clutter_draw_wrap` (0x48fb7e) | per **hardware polygon draw** (~3,400 per frame) | a frame compare; for a bush record (type 4) a binary search over ~700 instance pointers (~10 steps) |
| `clutter_build` + `clutter_template_table` | once per frame + once per template (~13) | 788 cells: one engine transform + frustum call each (~0.05 ms); per (template, cell) pair one 32-bit hash (~10 k per frame, ~0.03 ms) |
| `I76_SHADE_SMOOTH` | none per vertex | the exe's 17 emitters read our constant and a 256-entry table instead of theirs; the proxy's only per-frame work is a 256-byte `memcmp` of the stock table (`ss_frame`) |
| `I76_TERRAIN_LOD` / `TEX` / `OBJECT_LOD` | none | patched constants |

Cache behaviour: the stateless morph walks `V` (12 B stride, 76 KB for 6,300 vertices), `g_ep_a/b/s` (2 + 2 + 4 B per vertex) and the
list arrays sequentially; everything fits L2. The parents' loads (`V[3a]`, `V[3b]`) are random within the same 76 KB: L1/L2 hits. There is
no table lookup, no hashing, no allocation per pass in the stateless form. The log form hashes every vertex into two 65,536-slot
tables of 48-byte slots (3 MB each) plus the leaf sets: that is the cache-missing code in the profile.

### 1.2 Baseline (proxy timers, no instrument)

| timer | value | source |
|---|---|---|
| `terrain-morph: own cost` (tm_stateless + the morph part of tm_xform_wrap + tm_emit_wrap) | **92-117 us per pass** (p50 ~108) over 15 windows in `an-r4` / `an-r5` / `an-r6`; 77-147 us in 12 further windows from 2026-10-24/25 lanes | laptop C:\i76-bench\analog, T05 route, preset keys as OWNER-2300-ALL (LOD 24, morph 0.25 / SHADE 3 / NEAR 100, SPARSE, alpha fade, FEATHER) |
| same, with `I76_TERRAIN_MORPH_LOG` | 1,867-2,930 us | desktop profile boots a1 / b2 |
| `clutter: 600 frames` (the whole engine clutter call, our hooks inside) | **1,314-1,771 us avg** (9 windows, 3 runs), 2.8-7.6 ms max; 660-783 instances tested / frame, 672-790 cells | laptop, same runs; desktop a1: 1,270 us, 765 / frame |
| `fe_DrawTri` | **not timed** (no timer exists; estimate 0.1-0.25 ms: ~19 k vertex divides + stores) | unit U1 adds it |
| `clutter_draw_wrap`, `clutter_build` / template tables | not timed (estimate ~0.1 ms together) | unit U1 |

So in the owner's build our terrain + clutter hooks cost about **0.3-0.5 ms of an ~11-12 ms frame (3-4 %)**; the clutter line's 1.3-1.8 ms
is almost all the engine's own per-instance path (below).

### 1.3 Ranked changes (our hooks)

| rank | change | expected saving | risk | equivalence test |
|---|---|---|---|---|
| H1 | **Never measure with `I76_TERRAIN_MORPH_LOG` on.** fp-run.ps1 sets it in every mode; make it opt-in (`-MorphLog`). Not a game change. | 1.8 ms **of the profile's frame**, 0 of the owner's | none | - |
| H2 | **`fe_DrawTri` divide-free fast path.** Reorder: per vertex compare `oow` against the hoisted `1 / z0` first (a vertex is in the fade band iff `oow < 1/z0`); near vertices get the 255 store only; the divide, smoothstep and `g_fe_averts_faded++` run for band vertices only (~23 % of vertices on the route: 2.07 M faded of ~5.6 M). Drop the min / max probe bookkeeping unless `I76_FAR_EDGE_LOG`. Keep the hook's order of writes. | 0.05-0.15 ms | low (same inputs, same outputs; the band test is exact: `w > z0` <=> `oow < 1/z0` for `oow > 0`) | alpha stream dump: with `I76_PASS_DUMP` (U1) log per frame a 32-bit hash of the three alphas of every triangle inside the flush; same replay route, old vs new build: **bit-exact** (the band vertices compute the same expression; the near ones store the same 255) |
| H3 | **Stateless morph micro-hoists**: keep `cut2`, `om2`, `invB` as they are (already hoisted); add a per-pass early skip of the whole loop when no vertex was split this pass (`m == 0` after pass 1 happens only on frames without a quadtree, so no); move the centre-vertex 4-parent scan behind the `D2 <= 0` / shortcut tests where possible (the shortcut needs `e`; the min / max scan only matters for `e`, so no). Honest expected gain **< 0.03 ms**: the loop is already ~0.1 ms. | ~0 | - | not worth a unit |
| H4 | SSE2 for the morph | **not worth it**: 0.1 ms total, data-dependent branches per vertex, gcc -O2 x87 build (`build.ps1`: `gcc -m32 -O2`, no `-msse2`; switching the whole DLL to SSE2 float changes rounding in every other hook and is a separate decision) | - | - |
| H5 | Per-node caching with a camera-delta threshold for the morph | **not applicable**: the stateless morph recomputes t from this pass's vertices; there is no per-node state to cache, and the table form is the instrument, not the shipped path | - | - |
| H6 | `clutter_draw_wrap`: skip the binary search unless the record pointer lies inside the bush range (already `r >= g_cla_p[0] && r < g_cl_pend`) - already done; nothing to gain | 0 | - | - |

Equivalence-test design (used by H2, C2, G2, T1): **`I76_PASS_DUMP=<file>[,<first frame>,<count>]`** (lab instrument, new, in
terrainmorph.c next to the morph log): after `tm_emit_wrap`'s blends (and after `fe_haze_apply`), write per main pass one line
`frame, n, hashV, hashU` (FNV-1a over the raw bytes of `V[0..3n]` and `U[0..3n]`) and, for frames in the window, the full arrays as
binary; in `fe_DrawTri`, per frame an FNV over every (a.x, a.y, a.oow, a.alpha, ...) triple inside the flush; in `clutter_draw_wrap`
per frame an FNV over the record pointers' (type, vertex count, texture handle) sequence. Route: `I76_REPLAY` (replay.c) replays a
stored input trace with the stored per-frame dt, so the camera pose per frame is the same on both builds (the morph's t is a function of
the pose only). Pass criterion per unit: identical hashes on every frame of the window (bit-exact), or, where a unit reassociates float
arithmetic, a per-element compare of the binary dumps with |dy| <= 1 raw height unit (0.1 m) and |ds| <= 1/255 of the shade. The dump
is also the regression test for every later unit.

## 2. Clutter (bushes)

**What the engine does per frame** (strlkproxy.c 9409-9460, lab CLUTTER-AND-MIRROR.md): for every template (~13) x every cell of the
proxy's table (672-790 cells after the per-frame frustum pre-reject; stock is 9 cells): the SPARSE / fade hash (`clutter_template_table`,
~10 k hashes, pairs kept 6.5-7.7 %) -> ~660-780 instances tested: surface type lookup 0x4927b0, terrain height (two lookups), the 5 m
rise check, the 2 m frustum sphere (`clutter_cull_wrap`), then for the ~660 that pass: `object_SelectGeometryLod(template, variant)`,
`renderer_AcquireGeometry` (the geometry cache walk, by name), the billboard transform of the template's vertices into the pool, per-vertex
lighting (0x478430, day: 1 dot + depth term), **one draw record per face** (660 records, 2 triangles each), bucket insert.

**Where the 1.3-1.8 ms goes** (a1 in-mission, bounded chain count for 0x45c380..0x45c8a0 = 13.2 %: i76.exe 4.7, **KERNELBASE 3.6, msvcrt 3.2**,
Strlkup 0.7, ntdll 0.5). The engine's arithmetic (4.7 % = 0.55 ms) is less than the CRT / kernel time under it: `_tolower_l` (a
case-insensitive string compare), `memmove`, `MultiByteToWideChar` (the ANSI -> wide conversion inside a `*A` file or module API), whose
innermost exe callers are `image_LoadM16Variant` 0x471980 and `renderer_ReleaseM16Texture` 0x471b70 (4.7 % of all in-mission samples
between them), i.e. **the hardware texture variant of a bush's texture is being resolved by name, with a file probe, per instance or per
template per frame**, and released again. (The same two functions carry the mirror texture's per-refresh re-creation; the chain data cannot
split the two callers; U1 counts them.) The proxy's own clutter hooks are 0.7 % (~0.08 ms).

Spatial pre-reject: **already done** (the 49x49 candidate block culled per frame to 670-790 cells, nearest first; per-template
filtered tables; the record-pool guard). What is left on that axis is small: (a) the per-cell engine transform + frustum call for ~790
cells (~0.05 ms) could use the camera's 2D footprint instead; (b) cells entirely beyond every template's admission distance
(`d > fade x sqrt(65535 x density / h16)` for all templates) could be dropped before hashing - at density 0.5 / fade 450 the kept rate is
~7 %, the hash costs ~3 ns each: ~0.03 ms. Neither is worth a unit on its own.

| rank | change | expected saving | risk | test |
|---|---|---|---|---|
| C0 | **Count it first (U1):** per-frame call counts + QPC sums for 0x471980 / 0x471b70 and for the KERNELBASE A-API they reach (hook `CreateFileA` / `GetFileAttributesA` / `FindFirstFileA` in the exe's IAT with the return address; the proxy has `patch_iat`), split by caller (clutter chain vs mirror refresh). | - | none | the 600-frame line |
| C1 | **Memoise the texture-variant lookup** per (template, variant): the first resolution per mission stores the result (handle / pointer) and later frames take it from a small table; released only at mission end (mirrordetail.c already keeps a per-mission cache with the same lifetime). Exact placement after C0 names the call site (likely inside `object_SelectGeometryLod` -> AcquireGeometry -> texture resolve, or in the clutter face-record setup). The mirror's own texture must stay uncached (it changes every refresh: key on the 8-bit bitmap pointer + a kind check, as mirrordetail.c does). | **0.5-0.8 ms** if C0 confirms the clutter side of the 4.7 % | medium: a stale handle after a texture cache flush (ZGLIDE's TMU eviction, `tex-census` NO-SLOT) would draw the wrong texture; invalidate the memo on any `grTexDownloadMipMap` of a cached handle (the proxy already hooks it) | screenshot pair on the replay route (bush textures identical), `clutter_draw_wrap`'s texture-handle sequence hash equal per frame, fps n 3 |
| C2 | Per-cell admission pre-test before hashing (b above) | ~0.03 ms | low | pairs-kept count unchanged per frame |
| C3 | Thin the per-instance engine path (two height lookups -> one; the rise check from the cell's cached ground) | ~0.1 ms | medium (engine code at 0x45c5bf..0x45c634) | instance count per frame identical on the replay route |

## 3. The incremental-quadtree question, answered

**What the owner's phrase refers to.** "Not redrawing all vertices every frame" was never a plan for this engine; the earlier "redraw" was
the owner's word for the terrain pops (TERRAIN-MORPH-2026-10-21 opens with it), which the morph addressed visually. Nothing was promised
or dropped on the caching side.

**What the engine rebuilds per frame** (renderer.md "terrain quadtree LOD", terrainmorph.c header, strlkproxy.c 8978-9050):
1. `renderer_QueueTerrain` 0x490a00: the footprint hull (eye + 4 far corners, gift-wrap; `I76_TERRAIN_HULL_FIX` rebuilds it), the root
   square snapped to a 32-sample grid (it moves ~2x a second while driving: RENDER-FINISH s.1), fresh arenas: leaf list 0x59c560, edge
   records, vertex pool `[0x5dd320]` (12 B), UV / shade `[0x5dd2ec]`, count `[0x6442ec]` reset.
2. The recursion 0x4911e0 per node: hull cull (bounding circle vs up to 6 planes), `h >= 32` forced split, the distance test
   `d2 > (2h)^2 K`, `2 d2 < (2h)^2`, else 5 midpoint height errors (5-9 `world_GetTerrainSampleRaw` calls) against `floor_pow2(d2) B`,
   and for leaves larger than 4 samples the surface-type scan of the border samples. Each split makes up to 5 vertices through
   `SplitTerrainEdge` (true height `0x493160(mx, mz)`, int16 index). Measured per frame: ~6,300 vertices (p90 7,150), ~2,500-3,000 leaves.
3. `0x4937c0`: every vertex transformed in place to view space (double camera, 9 mul-add).
4. `0x490f08..0x490f6d` -> `ShadeTerrainVertex` 0x490fb0 per vertex: 4 neighbour samples (`GetTerrainSampleRaw`), the slope term, an
   `rsqrt` whose result is **discarded**, the depth term g(z), clamp.
5. `EmitTerrainPolys` 0x491a30 per leaf: the quad (or a fan when the two corner triangles disagree) with the T-junction midpoints, a plane
   test per triangle (`math_PlaneFrom3PointsF`), the texture level pick 0x4923f0, the 3D clip, the 2D clip, `InsertDepthBucket`
   (1 m painter's buckets, rebuilt every frame).

In the corrected in-mission pie the game's terrain code is ~15 % (1.8 ms). Only step 2's **decision** part is cacheable: the distance
and error tests and the surface-type scan, i.e. `SubdivideTerrainQuad`'s own body (2.3 %) plus the share of `GetTerrainSampleRaw` the
tests use (~1 %): **~0.3-0.4 ms, 3 %**. Everything else is per-camera-pose work: the view transform, the depth term in the shade, the
emit's plane tests and clips, the buckets. The vertices' world positions and true heights are the part that does not change, and they
are already cheap (one heightmap read each).

**What a cache would break.**
- *The arenas.* Leaves, edges and vertices live in per-pass arenas that the rear mirror's pass (0x44594e, every 2nd frame, its own camera
  and LOD) rebuilds between two main passes. Keeping the main tree means keeping a private copy of the arenas and switching pointers per
  pass, or giving the mirror its own: the proxy's mirror-detail code already redirects some of that state, so it is possible, but it is a
  structural change to the exe's allocator, not a hook.
- *The int16 vertex pool.* Indices are the pass's running count; a persistent tree needs persistent indices (a free list) and the
  32,767 ceiling then counts live vertices across frames, not per frame.
- *The LOD rings move with the camera.* The decisions near every ring change every frame by construction; caching them is a hysteresis or
  a freeze. The proxy has both (`I76_TERRAIN_HYST`, `I76_TERRAIN_FREEZE`, RC-DRAW-FPS-2026-10-20): HYST 20 cut flip events 24 %, FREEZE
  stopped far change; neither is in the owner's set, and their saving is the same 0.3 ms with the look consequences already judged.
- *The stateless morph* keys t on the vertex's split ring and this pass's parents: unchanged under a correct cache, but a cache that
  keeps a node split past its ring (a freeze) changes t's start point, i.e. the look (RENDER-FINISH s.1 is exactly that effect at the
  root-square moves).
- *Binoculars* (zoom 8: `K = cam+8 A / (w/2)` grows 8x): every decision is invalid in one frame, so a cache needs a full rebuild on any
  K / fov / root change, plus on teleports and mission load.

**Verdict: don't / later.** The saving is bounded by ~3 % of the frame, the risk sits in the exe's allocator and the mirror pass, and the
look-side effects are the ones the render-finish lane spent two days removing. "Later" = the renderer-replacement tier
(RENDERER-ALTERNATIVES.md), where a persistent clipmap / quadtree with GPU morphing is the normal design and the whole 15 % + the 31 %
translation go away together.

## 4. The Glide -> D3D11 translation (31 % in-mission, 3.6 ms)

**Counts per frame** (far-edge probe, OWNER-2300-ALL, T05 valley road, 2026-10-23 runs): inside the hardware flush **5,900-6,220
`grDrawTriangle` calls per frame** (1.77-1.87 M per 300 frames; 4,850-4,970 of them opaque-op = terrain + roads + objects, the rest
keyed / translucent = bushes, smoke), 80-190 outside the flush (sky dome, horizon strips, cockpit, HUD), 130-180 k per 300 frames past
0.9 x far. Draw records (polygons handed to `DrawPolyHW`): not counted on this preset; by construction ~2,500-3,000 terrain leaves +
660 bush faces + roads + objects = ~3,400, i.e. **1.8-1.9 triangles per record** (a terrain leaf is a quad or a small fan: ZGLIDE's
Render op emits n-2 triangles per n-vertex polygon, one `grDrawTriangle` each).

**Where the 3.6 ms is**: glide2x.dll (dgVoodoo) 16.1 % with hot blocks +1a100 and +1200, D3D11 + DXGI + nvwgf2um 8.6 %, ZGLIDE 5.9 %
(the fan loop, the state calls, the vertex packing), i.e. **~560 ns per triangle end to end**, ~190 ns of it in ZGLIDE. dgVoodoo batches
internally (it does not issue a D3D11 draw per triangle; the driver's 3.5 % is command building for the batches), so the per-triangle
cost is its vertex conversion (GrVertex -> its own format, w/oow handling, colour / alpha packing) plus per-call overhead, in an
unknown ratio.

**Batching from our side without changing dgVoodoo:**
- Glide 2.x has `grDrawPolygonVertexList(n, GrVertex[])` and `grDrawPlanarPolygonVertexList`; dgVoodoo exports the full Glide 2.11 set
  (to verify with `GetProcAddress` at attach, as the fog entry points are). One call per record (~3,400) instead of ~6,200.
- It saves per-call overhead and the duplicated fan vertices (a quad fan sends 6 vertices, a polygon list 4; ~19 k -> ~14 k vertex
  conversions, -27 %) **if** dgVoodoo's polygon path converts once per vertex. It saves nothing if it fans internally.
- The hook point is ZGLIDE's Render op (the fan loop at ZGLIDE+0x2c00 block), not the exe: patch the loop to call our function with
  the vertex array, which issues the polygon call for records the fade / bush hooks do not touch (opaque, unkeyed) and falls back to
  the per-triangle path for the rest, so `fe_DrawTri` and the bush alpha keep working unchanged. ZGLIDE's vertex layout is already read
  by the hooks (oow at +32, alpha at +28, r at +12).
- State calls are the other half: dgVoodoo's batches break on each `grTexSource` / combine / blend change; the flush order is the
  painter's (far to near), so terrain leaves alternate texture levels (5 levels, TEX 8) and bushes interleave. Count them (U1) before
  deciding; re-ordering records is not ours to do (painter's order is the look).

**Verdict: possible, bounded ~0.3-0.8 ms, decide on the probe.** U1 adds (i) an rdtsc sum around `p_fe_DrawTri` per frame (the
synchronous per-call cost of dgVoodoo's `grDrawTriangle`; the deferred batch flush is excluded and stays), (ii) counts of
`grTexSource`, `grAlphaBlendFunction`, `grColorCombine`, `grChromakeyMode`, `grTexDownloadMipMap` per frame (IAT, three already hooked),
(iii) a `GetProcAddress` check of the polygon entry points. Gate: proceed to the batching unit only if the per-call cost is >= 150 ns
(then ~3,000 fewer calls = >= 0.45 ms) or the polygon path measures cheaper per vertex in a 1-frame A/B (toggle per frame
parity, compare the two rdtsc sums).

## 5. PeekMessageA 23.6 %: hypotheses and the decisive check (done)

Hypotheses the data could have supported: (a) present / DWM back-pressure surfacing in the next win32k call (windowed borderless,
`FullScreenMode = false`, `FullscreenAttributes = fake`); (b) an input-queue flood (1 kHz devices, one `PeekMessage` per loop
iteration at 0x403787: `call esi` with PM_REMOVE, `je 0x4037cc` on empty); (c) the proxy's own PeekMessageA IAT hooks (cursormap.c,
cursoraw.c, padmenu.c chain on the exe's slot); (d) a boot / shell period admitted by the filter.

**The decisive check was a re-mine of the retained raw samples, not a run** (lab `tools\frame-profile\fp_remine.py`, 2 minutes):
19,042 samples with the exe frame 0x403789 (15,935 at `NtUserPeekMessage+c`, 2,029 `ZwReadFile+c`, 693 `ZwYieldExecution+c`); they
come in 262 runs of 6-400 consecutive samples (60 ms to 1 s each), **all between t = 0.5 s and 49.6 s with terrain vertex count 0 and
player x 8078** (the stale pre-mission value), and **none** among the 50,325 samples with vertices > 0 (t 49.6-185 s). The analyser's
hill-leg filter (`x in 6400..8900`) admitted them; `--verts-min 1` (added) excludes them. (d) is the whole story; (a)-(c) are not in the
frame. The "main thread at 97-100 % of a core" is consistent: the pre-mission loop spins on `PeekMessage`.

What the Opus lane should still run on the desktop when the console is free, for other reasons: nothing for PeekMessage. The 1x / 2x
conf test stays optional (the GPU at 15 % and the translation at 31 % of a CPU-bound thread already say the frame is CPU-bound by
construction). The sampler's kernel column (`fp_sample.py` writes it since the record's revision; the a1 capture predates it) answers
the kernel / user split for the remaining 18 % system time on the next sampled run.

## 6. Execution plan (sized for an Opus lane; laptop first, desktop only for the owner-route fps rows)

Preconditions: lab `tools\frame-profile\fp-run.ps1` gets `-MorphLog` (default off) so no measurement build carries the instrument (H1);
every fps row is n 3 with the same preset and the console rules (keep-display, mute the process, lock); the `I76_PASS_DUMP` replay route
is recorded once on the laptop (`I76_REPLAY` trace, T05 via the player route since the direct boot currently inverts the car; movies and
cutscenes skipped; `-NoFfb`).

| unit | target | method | test | rollback | acceptance line |
|---|---|---|---|---|---|
| **U0 record + tools** (no console; this lane did it) | - | FRAME-PROFILE addendum; `fp_analyse.py --verts-min`, `fp_remine.py`, `fp_hotblock.py` in the lab | re-run on a1 reproduces the pie above | - | the corrected pie is in the record |
| **U1 instrument build** `I76_PASS_TIMERS=1` + `I76_PASS_DUMP` | 0 ms (lab only) | per 600 frames: rdtsc / QPC sums and counts for `fe_DrawTri` (inside / outside the flush), `clutter_draw_wrap`, `clutter_build` + template tables, the morph (exists), `image_LoadM16Variant` / `ReleaseM16Texture` calls (entry detours or call-site wraps once the caller is named) with the KERNELBASE A-API count and return address, `RegOpenKeyExA/W` + `NtOpenKey` per frame by caller module (IAT of i76.exe, dsound.dll, winmm.dll, Strlkup's own imports), the Glide state-call counts of s.4, the polygon entry-point check; the dump of s.1.3 | the line prints; laptop route n 3; the dump hashes are stable run to run on the replay | DLL swap | "U1: fe_DrawTri X us, clutter hooks Y us, m16 variant N calls / Z us per frame (clutter K, mirror M), registry opens R per frame from <module>, grDrawTriangle sync cost P ns, state calls S per frame, polygon entry points present / absent" |
| **U2 fe_DrawTri fast path (H2)** | 0.05-0.15 ms | reorder as in H2 | `I76_PASS_DUMP` alpha hashes bit-exact on the replay window; fps n 3 laptop | key `I76_FADE_FAST=0` for one build, then remove | "U2: alpha stream bit-exact over N frames; fe_DrawTri X -> Y us" |
| **U3 texture-variant memo (C1)** - only if U1 shows the clutter side >= 0.3 ms | 0.5-0.8 ms | C1 | texture-handle sequence hash equal per frame; screenshot pair; `tex-census` NO-SLOT 0; crash checks (hood, binoculars) n 2; fps n 3 | key off | "U3: N variant resolutions/frame -> 0; frame -X ms; handles identical" |
| **U4 sound-update registry opens** - if U1 shows them in the owner's set (not a lab switch) | 0.3-0.6 ms | name the API from the U1 return addresses; memoise per handle / move the query off the frame; separate lane (sound), not terrain | voice count / volume behaviour unchanged (soundmix.c tests), fps n 3 | key off | "U4: R registry opens/frame from <API> -> 0" |
| **U5 Glide batching probe** | - | the U1 counters, 1 boot | - | - | the s.4 gate decided: go / no-go with numbers |
| **U6 polygon-list submission for opaque unkeyed records** - only on a U5 go | 0.3-0.8 ms | ZGLIDE Render-loop patch (signature-checked, ZGLIDE 05c1dde4), per-frame parity A/B toggle for the measurement, fallback per record for faded / keyed / bush records | `I76_SHADE_CENSUS` histogram identical; screenshot pair on the replay (per-pixel equal: same vertices, same oow, same texels); crash checks; fps n 3 desktop | key off; the patch is all-or-nothing on the signature | "U6: calls 6,200 -> 3,400/frame; -X ms; census identical" |
| **U7 game-side terrain shade table (optional, the one game-code unit)** | 0.3-0.5 ms | replace the shade loop 0x490f08..0x490f6d with ours: per sample a lazily built per-tile table of the static slope term `max(0, L.y - Sx L.x - Sz L.z)` (L fixed per mission; 16 KB float per 128x128 tile on first touch, keyed by tile pointer), per vertex `s = min(1, tbl[x,z] g(z) + A)`; drops 4 neighbour reads + the discarded rsqrt per vertex (GetTerrainSampleRaw 1.8 + rsqrt 1.4 + ShadeTerrainVertex 1.3 = 4.5 % -> ~1 %); Gold through the site map, Nitro only if `g_ta_*` maps the loop | `I76_PASS_DUMP` U-hash **bit-exact** (store the float the exe computes: same operation order, no rsqrt) over the replay window; crash checks | key off | "U7: shade stream bit-exact over N frames; terrain pass -X us" |
| **Not done** | | the quadtree cache (s.3); SSE2 of the morph (H4); morph per-node caching (H5); the haze (off); shade-smooth (no per-vertex cost); the 1x / 2x test for PeekMessage (s.5); any re-ordering of the painter's buckets (the look) | | | |

Overall acceptance: hill-leg median fps on the owner's route (desktop, n 3, same preset, no morph log) up by the sum of the landed
units' measured savings within noise (the sitting-to-sitting spread is 4-5 fps: FRAME-PROFILE), every landed unit's equivalence hash
identical on the replay window, `I76_SHADE_CENSUS` unchanged, 0 CRASH / EXCEPTION over the crash-check views (t01 / t05 hood, binoculars,
zoom 8), the accepted look untouched by construction (no unit changes a vertex, a shade, an alpha or a texel; U6 changes only how the
same triangles reach Glide).

Order and sizing: U0 (done) -> U1 (half a day, laptop) -> U2 (an hour) -> U3 / U4 (a day each, only on evidence) -> U5 (one boot) -> U6
(a day, desktop rows) -> U7 (a day). Expected total if U1 confirms the system-call leads: **1.2-2.3 ms of an 11.9 ms frame (10-20 %)**, of
which our own terrain hooks contribute 0.05-0.15 ms; the rest is the engine's texture / registry churn and the translation.

## 7. For the owner: what could be offloaded to the GPU

Inside the current engine, nothing of the terrain: Glide takes screen-space vertices with 1/w, colour and UV already computed, so the
quadtree, the view transform, the shading and the clipping are the CPU's by contract, and dgVoodoo only rasterises what it is given
(the GPU sits at 15 % for that reason). What the CPU side can still give up is churn, not geometry: the texture-variant lookups and
registry opens the profile found under the clutter and sound paths, the per-call overhead of ~6,200 triangle submissions, and the
proxy's own measurement instrument (which was never in your build). The renderer-replacement tier moves the rest: a persistent terrain
mesh or clipmap on the GPU with vertex-shader morphing (the geomorph becomes free and continuous), per-pixel shading from the heightmap
normals (no vertex shade rows, no 32-row quantisation to smooth), instanced bushes with distance fade in the shader, and one draw per
material instead of one call per triangle - that is where "not redrawing all vertices every frame" is the normal way to work, and
where the 31 % translation and the 15 % terrain code both disappear.

## Files

- This record; FRAME-PROFILE-2026-10-25.md carries a correction header pointing here.
- Lab `tools\frame-profile\fp_analyse.py` (`--verts-min`), `fp_remine.py` (PeekMessage runs, system-call callers, kernel split when the
  column exists), `fp_hotblock.py` (names a Strlkup hot block by its constants). Raw data unchanged in `captures\frame-profile-20261025\`.

## Results (implementation lane, 2026-10-25; issue #92)

Bench: the laptop (i7-1165G7, GTX 1650 Ti, 1920x1080 window, dgVoodoo.lv1080.conf), the lane's own twin `C:\i76-bench\tpo\Interstate 76`
(a copy of the analog-driver lane's launch-video twin), preset OWNER-2300-ALL (no morph log), T05 via the player route (Esc on the
briefing movie, Esc on the scripted opening; I76_SKIP_MOVIES=1, I76_SKIP_CUTSCENES=0, I76_FFB_OFF=1, muted, own shm suffix), the owner's
route **pad-driven** (`rcd_drive_bench.py --mode route --input pad`, ridge leg then the 2.7 km hill leg). Every measurement DLL = the unit's
source + the analog-driver lane's `I76_DRIVE_INJECT` harness patch (lab `builds\analog-driver-20261025\drive-inject.patch`, off unless
set, the same in every variant, not committed here): the key-driven route is not usable on the laptop (30.0 fps pinned, the hill leg
stops after ~0.1 km, both this lane's and the analog lane's key runs). Timer values are the means of the 600-frame windows after the
first (the boot); n = boots. Lab scripts: `builds\terrain-opt-20261025\scripts\` (tpo-job.ps1 / tpo-batch.ps1 on the laptop,
tpo_tab.py, build-variant.ps1); raw runs `C:\i76-bench\runs\tpo-*` and copies in `builds\terrain-opt-20261025\runs\`.

**The equivalence route as specified is not available, and what replaces it.** `I76_REPLAY` replays per-frame dt; the owner's preset runs
the whole-sim tick (I76_SIM_TICK_MS 41.667, drawn interpolated at the display rate), so the drawn pose per frame is wall-clock
dependent. The static fallback was measured: with the car parked (I76_START_POS without speed) every main pass's V / U hash still
differs frame to frame and run to run (2 boots x ~3,260 passes: 0 repeats; raw V between consecutive frames moves by up to 0.28 raw units
in y, the U shade by 8e-5: the idle camera sway). So the hash streams of `I76_PASS_DUMP` are recorded (T / D / C lines, raw V / U for a
window) but cannot be compared across builds. Each unit's bit-exactness is tested **inside one run** instead: the new path and the
stock path are both evaluated on the same inputs every frame and compared bit for bit (U2 `I76_FADE_VERIFY`, U3 `I76_M16_MEMO=2`,
U7 `I76_SHADE_TABLE_VERIFY`). That is a stronger test than a cross-build hash (every vertex of every frame of a real route, no
replay drift), and it is the one used below.

### U1 instrument build (`I76_PASS_TIMERS=1`, `I76_PASS_DUMP=<file>[,first,count]`; music-fix/passtimers.c)

| per frame (inside the hardware flush unless said) | u1 boot 1 | boot 2 | boot 3 |
|---|---|---|---|
| fe_DrawTri calls | 6,684 | 6,696 | 6,610 |
| fe_DrawTri own | 54.2 ns/call = 363 us | 53.2 = 357 us | 54.0 = 357 us |
| glide2x grDrawTriangle synchronous | **133.1 ns/call** = 889 us | 127.3 = 852 us | 128.0 = 847 us |
| outside the flush | 179 calls, own 9.6 us, sync 85 us | 179, 9.5, 83 | 179, 9.7, 84 |
| clutter_draw_wrap own (3,670-3,730 records) | 1,156 us | 1,146 us | 1,133 us |
| clutter_build / template tables | 89 / 47 us | 87 / 45 us | 86 / 45 us |
| GetFaceTexture at the clutter call 0x45c7eb (inclusive) | 618 calls, 656 us | 622, 630 us | 618, 629 us |
| of it image_LoadM16Variant | 257 pak loads + 361 cached, 509 us | 255 + 368, 488 us | 255 + 363, 487 us |
| ReleaseM16Texture in the clutter call | 921 (257 with a slot set), 296 us | 907 (255), 286 us | 915 (255), 285 us |
| face textures, rest (objects 0x45d9a9 / 0x45de23, flush, mirror) | 176 us | 170 us | 170 us |
| exe _stricmp (0x44a303 = GetFaceTexture's name chain: ~1,000 of them) | 1,276, 220 us | 1,269, 211 us | 1,274, 212 us |
| msvcrt MultiByteToWideChar (the locale compares under it) | 3,200, 151 us | 3,164, 143 us | 3,172, 145 us |
| registry calls (every module's IAT, by caller) | 0.6 | 35 (episodes of 21.7 / frame from Strlkup.dll+41f5b and DSOUND+64da8) | 0.6 |
| Glide state calls: texsource (all a new address) / blend / acombine / chroma / ccombine / download | 2,038 / 1,559 / 1,239 / 833 / 75 / 1.7 | 2,043 / 1,564 / 1,242 / 834 / 75 / 1.7 | 1,998 / 1,538 / 1,223 / 818 / 74 / 1.7 |
| morph own (its timer) / whole clutter call | 101 / 1,589 us | 99 / 1,530 us | 98 / 1,531 us |
| hill / ridge median fps (timers on) | 48.2 / 51.4 | 48.4 / 53.0 | 48.8 / 51.6 |
| CRASH lines | 0 | 0 | 0 |

Baseline (origin/main source + the harness patch, base-99248470, timers absent): hill 48.2 / 48.2 / 48.6 fps, ridge 51.0 / 51.2 / 51.7,
1 % low 14.1-14.8, 0 CRASH (n 3). The instrument costs no measurable fps (48.2-48.8 vs 48.2-48.6).

Where the release / reload churn is: the hot release site is `image_UnloadObjectFaceTextures` 0x44a128 (209-223 live releases per
frame, plus ~540 of already-empty slots), i.e. every bush object's face textures are unloaded after the frame and reloaded by
GetFaceTexture -> LoadM16Variant (vfs_GetFileSize + vfs_AcquireFile by name) on the next. The registry episodes (one boot) are U4's lane;
a new caller is named: the proxy itself (Strlkup.dll+0x41f5b) alongside DSOUND.

**U1 line:** "U1: fe_DrawTri 357-363 us (+ 9.6 us outside the flush), clutter hooks 1,264-1,292 us (draw wrap 1,133-1,156, build 86-89,
tables 45-47), m16 variant 618-623 calls / 487-509 us per frame in the clutter call (255-257 of them pak loads; mirror 0), registry opens
0.6 per frame (episodes to 35) from DSOUND / Strlkup / combase, grDrawTriangle sync cost 127-133 ns, state calls ~5,750 per frame
(texsource ~2,000), polygon entry points present (grDrawPolygonVertexList, grDrawPlanarPolygonVertexList, grDrawPolygon)." **PASS**
on the line; the plan's "dump hashes stable run to run on the replay" **FAIL** (no deterministic route under the tick; above), replaced
by the in-run verifiers.

### U2 fe_DrawTri divide-free path (`I76_FADE_FAST`, default 1; `I76_FADE_VERIFY=1` lab; music-fix/faredge.c)

The feather's band test without a divide: a vertex with oow >= cut (cut = 1/az0 raised by 1e-6 relative, more than the three float
roundings involved) has 1/oow < az0 after rounding, so the stock expression would give alpha 255; it stores 255. Every other vertex
(the band, the margin, oow <= 0, NaN) runs the stock expression unchanged. The probe's w (a double divide per triangle) and its min /
max bookkeeping run only when `I76_FAR_EDGE_LOG` or the clutter trace reads them. Rollback key `I76_FADE_FAST=0`.

| | U1 (n 3) | U2 (n 3) |
|---|---|---|
| equivalence (u2v, `I76_FADE_VERIFY=1`, the whole route) | - | **0 bit mismatches** in 80,674,795 fast-path vertices (of 93,186,117 opaque-op vertices; cut oow 0.000579711, band from 1725 m) |
| fe_DrawTri own, inside the flush | 54.2 / 53.2 / 54.0 ns/call = 363 / 357 / 357 us | 54.0 / 54.6 / 52.4 ns/call = 361 / 367 / 351 us |
| glide2x sync | 133.1 / 127.3 / 128.0 ns | 129.7 / 137.2 / 131.8 ns |
| hill / ridge median fps, timers off (base / U2) | 48.2 48.2 48.6 / 51.0 51.2 51.7 | 48.9 46.6 48.6 / 51.5 51.3 51.7 |
| CRASH | 0 | 0 (7 boots) |

**U2 line:** "U2: alpha stream bit-exact over 80.7 M fast-path vertices (every frame of a 4-minute route); fe_DrawTri 357-363 -> 351-367
us." Bit-exact **PASS**; the expected 0.05-0.15 ms saving **did not appear** (the difference is inside the boot-to-boot spread of +-8 us):
the per-vertex divides were overlapped with the rest of the call (out-of-order), and the hook's ~150 cycles per call are the call,
the stores and the timer pair, not the arithmetic. Landed anyway (exact, smaller code path, the probe off the hot path); fps unchanged
within noise (46.6-48.9 vs 48.2-48.6).
