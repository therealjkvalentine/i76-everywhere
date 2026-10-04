# Ground clutter distance and rear-mirror resolution (static, 2026-10-03)

Owner requests 2026-10-03: (1) "increase the draw distance of those little bushes - them popping up is
distracting"; (2) "anything we can do to increase resolution in rearview?"

Everything here is read from the exe (i76.exe in this folder; the same bytes at every site in
`i76.exe.2017galaxy`, `game-gogtest/gog-extract/app/i76.exe` and the pristine `i76-map/sandbox-gog`). Nothing
has been run. Switches: `I76_CLUTTER_DIST`, `I76_CLUTTER_RISE`, `I76_MIRROR_FAR` in
`i76-everywhere/music-fix/strlkproxy.c` (code landed in i76-everywhere b7959ae, swept into a parallel commit;
DLL, README rows and presets in 41e23ee).

## 1. Ground clutter (renderer_QueueTerrainClutter 0x45c380..0x45c847)

Called once per frame from the software scene (0x401e47) and the hardware scene (0x402111); not from the mirror.
Off unless Terrain Detail `[0x654b82]` is set.

**Cell snap.** `[0x4f7180]` (x) and `[0x4f7188]` (z) hold the camera's cell as floats, initialised to -1e-7.
They are recomputed only when the camera leaves `[cell, cell+100]` on either axis (0x45c39c..0x45c40a, constants
f64 0.0 at 0x4be0b0 and f32 -100 at 0x4be0b8); the new cell is `cam - rem`, rem = IEEE remainder of cam by 100
(`fprem1`, 100.0 as `mov [ebp-8], 0x42c80000` at 0x45c419/0x45c454), plus 100 when negative: the cell's lower
corner. The camera ground height `0x493550(cam.x, cam.z)` is kept at `[ebp-0x34]`.

**Loops.** Outer: templates, list head `[0x54ac70]`, next at `+0x60` (built by the class-create callback
0x45c330 from an object's children; the count per mission is not known statically). Inner: cells, a do-while
over the offsets table at 0x4f7190 = 9 `{dx, dz}` float pairs, (-100..100)^2 in steps of 100:

| site | bytes | role |
|---|---|---|
| 0x45c4fa | `b8 94 71 4f 00` | `mov eax, 0x4f7194` (pointer to the first dz), first template |
| 0x45c507 | `b8 94 71 4f 00` | same, every later template |
| 0x45c514 / 0x45c526 | | position = cell + table + template offset (`+0x40` x, `+0x50` z, f64) |
| 0x45c825 | `3d dc 71 4f 00` | `cmp eax, 0x4f71dc` after `add eax, 8`, then `mov [ebp-8], eax; jl` |

The table is referenced only by those three immediates. Coverage: the camera is anywhere in the centre cell,
so the block reaches at least 100 m and at most 200 m in each axis direction; with a 90 degree view and a
120 m depth limit the stock block already clips the view's corners.

**Per instance tests, in order.**

1. Surface type `t = 0x4927b0(x, z)`; geometry variant `[0x4be074 + 8t]` selected by `0x4466c0(template, v)`.
   If that returns anything but 1 the WHOLE function returns (0x45c56a `jne 0x45c841`), stock behaviour.
2. Geometry present with at least 3 vertices, and `[0x4be070 + 8t]` enabled (types 0, 1, 5).
3. **Rise:** `h(x, z) - ground(camera) <= 5.0` (f64 `00 00 00 00 00 00 14 40` at 0x4be0c8, read only at
   0x45c5bf). It is one-sided: anything below the camera's ground passes, anything more than 5 m above is
   dropped. So on a slope rising away from you the far bushes are culled by this test, not by distance.
4. **Depth:** view z `<= 120.00001` (f32 `01 00 f0 42` at 0x4be0d0, read only at 0x45c619), after the transform
   `0x472d30(out, cam, x, y, z)`.
5. **Frustum:** `0x472c10(cam, &view, 2.0f) > 0` culls (call at 0x45c634, `e8 d7 65 01 00`).

Then the template's vertices are transformed into the start of the vertex pool `[0x5dd320]` (reused per
instance, no accumulation) and each face takes one draw record from the record pool (0x490590), filled with
the vertex copies inline and queued by depth (0x48fe10, kind 4).

**Capacity.** The record pool is one block of 0x5a550 = 370,000 bytes (`push 0x5a550` at 0x48f9b5 in
0x48f9b0, called once from WinMain at 0x4033a3; allocator 0x498940 commits exactly that, rounded to the page).
Records advance `[0x6543c0]` by `0x1c + 0x18 x verts` (a 4-vertex clutter face = 124 bytes) and **nothing checks
the end**: there is no bound anywhere in 0x48fe10..0x490470. The pool is reset per pass at 0x48fd7b. This pool
is not one of the five `I76_FAR_CLIP` enlarges. The depth buckets (4096 x 1 m) are not a limit below 600 m. The
terrain lookups clamp off-map positions (0x4927b0 returns type 5, 0x493550 a default height), so a bigger block
cannot index outside the map arrays.

So clutter is limited by: the 120 m depth constant, the 3x3 cell table, and the 5 m rise test; a larger block
is bounded in memory only by the unchecked record pool.

### The switch: `I76_CLUTTER_DIST=<120..600 m>` (+ `I76_CLUTTER_RISE=<0..100 m>`)

Off when unset. When set, all eight sites are checked before anything is written (all or nothing; the record
pool goes first and its failure stops the rest):

| site | stock | new |
|---|---|---|
| 0x48f9b5 | `push 0x5a550` | `push 0x2d2a80` (record pool x8, 2.9 MB) |
| 0x45c4fa | `mov eax, 0x4f7194` | `call clutter_build_stub`: rebuilds the proxy table from the engine's freshly snapped cell, returns eax = table + 4 |
| 0x45c507 | `mov eax, 0x4f7194` | `mov eax, <proxy table + 4>` |
| 0x45c825 | `cmp eax, 0x4f71dc` | `call clutter_end_stub` = `cmp eax, [g_cl_end]; ret` (flags survive `ret`; the next instruction is a `mov`) |
| 0x45c634 | `call 0x472c10` | `call clutter_cull_wrap`: refuses (returns "culled") once the pool holds more than pool - 0x5a550 bytes, else the original test |
| 0x401e47, 0x402111 | `call 0x45c380` | `call clutter_frame_wrap`: times the call; every 600 frames logs time, cells, instances, refusals and pool high water (with `I76MUSIC_LOG`) |
| 0x4be0d0 | f32 120.00001 | f32 D |
| 0x4be0c8 | f64 5.0 | f64 5 x D / 120 (the same 2.4 degree angle above the horizon), or `I76_CLUTTER_RISE` |

**Table, per frame.** Candidates: a (2R+1)^2 block, R = ceil(3 (D + M) / 100) + 1 (capped at 24), pruned to cells
whose nearest point is within 3 (D + M), sorted nearest first; M = 71 + rise + 20 m. The factor 3 covers the
widest view the proxy can produce (Hor+ hood at 21:9 is about 144 degrees; a point at depth D sits up to
D / cos(fov/2) away). Each frame each candidate's centre (at the camera's ground height) goes through the engine's
own `0x472d30` transform; it is kept if view z - M <= D and the engine's `0x472c10` test with an 81 m sphere
(half-diagonal 71 m + 10) does not cull it, with the view y zeroed so only the near/far/side planes apply (bushes
can sit far below the camera). The centre cell is always kept (the loop is a do-while). Expected kept cells: about
9 at 120 m (stock is 9), about 20-30 at 300 m, 35-50 at 400 m, 80-110 at 600 m for a 90 degree view; the
candidate test itself is a few thousand transforms per frame at 600 m.

**Safety bounds.** D 120..600, rise 0..100, table capacity 49 x 49 entries (more than any candidate set), pool
guard leaves the stock pool size free for everything queued after clutter (smoke, then the flush), so even a
pathological scene degrades to missing far bushes rather than an overflow. Every per-instance test of the engine
still runs unchanged on every instance.

**Preset values.** `exp-detail-8`: 300 m (pop-in 2.5x farther; about 2-3x the stock cell count with the visible
cell table, 6x the stock depth area). `exp-detail-16`: 400 m. 600 m is allowed but unmeasured.

### Needs a live look

- CPU per frame (the log line), at 300 / 400 / 600 m, on a bushy map; the instance count per cell is mission data.
- Whether the far bushes look right: they are billboards on the coarse terrain; with `I76_TERRAIN_LOD` low the
  ground under them is less accurate far out and they may float or sink. The rise scaling (25 m at 600 m) lets
  bushes on hills above you appear; `I76_CLUTTER_RISE=5` restores the stock rule if hilltop bushes look wrong.
- The guard should never fire (log: `refused (pool) 0`); pool high water tells how close stock was.
- Off-map: type 5 is enabled, so near a map edge bushes continue past it, as the stock 3x3 block already does.

## 2. Rear mirror (renderer_DrawRearMirror 0x445750, mirror_Init 0x445380)

**Verdict: the mirror is NOT a sub-viewport of the 3D frame. It is a software render into a 256x64 8-bit
offscreen bitmap that is the cockpit mirror's texture, re-uploaded and drawn as a texture on the cockpit's mirror
face. Its resolution is 256x64 whatever dgVoodoo's internal resolution is; at a 4608-wide internal frame the face
magnifies that texture several times, hence the blocks.**

Evidence:

- mirror_Init 0x445380 (from the vehicle setup, 0x4637ac / 0x46b8a3): finds the cockpit's mirror sub-object
  (0x457570(cockpit, 0x1d), e.g. `PP51MIRI`), its first face with a texture name; the vehicle paks name
  `ZMIRI101.MAP` (zfs_out: header 256 x 64, 16,392 bytes). 0x44a740 makes a private writable copy of the
  texture's pixels and returns a bitmap over them (kind 0 at bitmap+8) into 0x608c00; 0x44a290 gives the texture
  handle `[0x52bbc4]`; a second copy (the frame/mask) goes to 0x608c40.
- The mirror camera: `camera_Create(0x608c80, bitmap 0x608c00, fov 0.5236 (30 deg), 1.0, far 100.0, 1.0)` at
  0x445537..0x445558 (main camera: far from the options/far clip), then x and y scale negated (mirror image).
  `[0x608cbc]` = camera+0x3c = the target bitmap.
- 0x445750: clears the bitmap (0x474ea0, colour 0xea), queues the scene (level 1: objects, tracers, smoke,
  flamers; level 2: also terrain, roads, clouds), flushes with 0x48fac0. The flush draws polygons with the
  hardware rasteriser 0x4260d0 only if `[[cam+0x3c]+8] == 1` (0x48fb65..0x48fb77); the mirror bitmap is kind 0,
  so every polygon goes to the software span rasteriser 0x471fd0 (8-bit, palette, no filtering).
- Then the mask is blitted over it with a transparent colour (0x47aa50 at 0x445a16) and 0x42ec20(`[0x52bbc4]`)
  re-uploads the texture (ZGLIDE UpdateTexture). The cockpit model draws its mirror face with that texture.
- Refresh: every 2nd frame stock (0x4457b9), `I76_MIRROR_RATE` puts it on the 20 Hz grid.

### Can the resolution go up?

Not with a contained constant. 256 is the Glide 2 maximum texture size (GR_LOD_256), so the width is already at
the limit; 64 rows could become 128 (aspect 2:1 is legal) only by changing, together: the texture cache copy in
0x44a740 (shared by every texture, not mirror-specific), the mask copy at 0x608c40, the face's texture coordinates
(texel units unless proven otherwise), and ZGLIDE's upload for that handle. That is a project, not a switch, and
it doubles only the vertical resolution.

What else could make it look better, roughly in order of value:

1. **Texture filtering of the magnified mirror texture.** ZGLIDE's polygon path sets `grTexFilterMode` per
   polygon: point sampling when its per-call flag and `[0x1001f754]` (set in FirstDevice 0x10001c78) are both set,
   bilinear otherwise (0x10002aa5..0x10002af4). If the mirror face is drawn on the point-sampled path, bilinear
   would trade blocks for blur. Which path it takes needs a live look (or a read of the cockpit draw call's
   flag); the patch would be in ZGLIDE (relocatable: by RVA after load, bytes verified).
2. **Range.** The mirror's far clip is 100 m, the camera_Create minimum: `I76_MIRROR_FAR=<100..600>` (built, not
   run) patches the `push 0x42c80000` at 0x44553c. Cost is software rasterising more polygons into 256x64,
   small; at level 2 the terrain queue runs for the mirror camera too (30 degree fov, far fewer vertices than the
   main view).
3. **Detail.** `I76_OBJECT_LOD` already covers the mirror's object LOD (1/focal at 0x457ade reads 0x4bdf94).
4. **Smoothness.** `I76_MIRROR_RATE` (refresh on the 20 Hz grid).

### Needs a live look

- What `I76_MIRROR_FAR` shows at 300 m (fog, sky) and whether level 2 terrain in the mirror stays cheap.
- Whether the mirror face is point-sampled under dgVoodoo (the lever in item 1).
