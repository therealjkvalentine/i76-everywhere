# Texture detail and object LOD with distance (static read, 2026-10-03)

Question from the owner: "could we load detailed textures for terrain (and entities) a little further out too?"
(after `I76_TERRAIN_LOD` x8, which scales the terrain quadtree split constants at 0x493080).

**Answer in short.** Yes, and both are small patches.

- Terrain texture detail is a hand-made mip chain: five separate texture files per mission (256, 64, 64, 32, 16 px
  in the usual set), chosen per terrain leaf from its nearest vertex depth. The 256 px one is used only out to
  **50 m**. One integer constant (40, at 0x492458) scales every boundary.
- Object and vehicle detail (mesh and the textures that mesh carries) is chosen from the object's on-screen radius
  in **640-wide pixels**, whatever dgVoodoo renders at. One float (1.0 at 0x4bdf94) scales every decision.
- Glide mipmapping is off. The engine uploads one size per texture, so nothing in dgVoodoo's `[Glide]` section can
  add or bias detail.

Nothing here was run. Every byte below was read from the files; every distance in metres is derived arithmetic that
needs a live check (section 6).

## 0. Files read

| tag | file | md5 |
|---|---|---|
| AiO (lab) | `i76-uncap-lab\game\i76.exe` | 85de44a7136979d7730800eeba8ca6cf |
| Galaxy 2017 | `i76-uncap-lab\game\i76.exe.2017galaxy` (= `i76_pristine.exe`, = `i76-map\ghidra\i76_ref.exe`) | 9a232dcc2c164648cff20c414c1f9698 |
| gog-extract | `i76-uncap-lab\game-gogtest\gog-extract\app\i76.exe` | 64165126c1b788a8151e9730b9091e1c |
| ZGLIDE | `i76-uncap-lab\game\ZGLIDE.DLL` (image base 0x10000000) | 05c1dde499cd8da3248557a76ba42f31 |

Note: the path given for "the Galaxy exe" (gog-extract) is **not** md5 9a232dcc; `i76.exe.2017galaxy` is. Both were
compared. Their `.text` differs from the AiO exe in the same 2,473 bytes, none of them at a site below. The
daily driver's own exe was not compared (`game-dd-20261003` holds no `i76.exe`).

Tools: capstone + pefile (scratch scripts), `i76-map\tools\i76fmt` (ZFS / pak reader) for the data tables.

## 1. Mipmaps and filtering under Glide

**ZGLIDE never enables mipmapping and uploads one level per texture.**

- Imports from glide2x.dll: `grTexMipMapMode`, `grTexFilterMode`, `grTexDownloadMipMap`, `grTexSource`,
  `grTexCalcMemRequired`, `grTexClampMode`, `grTexCombine`. There is **no `grTexLodBiasValue` import**.
- `FirstDevice` 0x10001c20 zeroes the plugin's mipmap flag and, in the same function, sets the mode from it:

  ```
  10001c47  mov ebx, 1
  10001c4c  xor edi, edi
  10001c60  893d68ee0110   mov [0x1001ee68], edi        ; mipmap flag = 0
  ...
  10001db7  call grTexFilterMode(tmu, 0, 0)             ; point sampled (dgVoodoo TMUFiltering overrides)
  10001dbc  mov eax, [0x1001ee68]
  10001dc1  push edi                                    ; lodBlend = FXFALSE
  10001dc2  cmp eax, edi / je 0x10001dcf
  10001dcb  push ebx  (mode 1 = GR_MIPMAP_NEAREST)      ; not taken: flag is 0
  10001dd5  push edi  (mode 0 = GR_MIPMAP_DISABLE)      ; taken
  10001dd7  call grTexMipMapMode                        ; the only call site
  ```
- Texture info setup 0x10001930: `largeLod = 8 - log2(width)`; `smallLod = largeLod` unless the flag is set (then
  8 = 1x1):

  ```
  10001964  mov ecx, [0x1001ee68]
  1000196f  je 0x10001979
  10001971  mov dword [ebx], 8        ; smallLod = GR_LOD_1 (mip chain)   - not taken
  10001979  mov [ebx], edx            ; smallLod = largeLod (one level)   - taken
  1000197b  mov [esi+0xc], edx        ; largeLod
  ```
  Formats: 5 (P_8), 0xa (RGB_565), 0xb (ARGB_1555). Largest side 256.
- The flag's only other writer is `SetState` 0x10002dd0, state id 8 (`10002e0e mov edx,[esp+8]; mov [0x1001ee68],edx`).
  The exe calls `renderer_fn_SetState` [0x608bc0] at nine sites with ids 9 (0x433f39, 0x434024), 0xa (0x403db5,
  0x49508b, 0x49603b, 0x4960b8, 0x4960e8), 0xb (0x42e9de) and 0xc (0x42eb2b). **Never 8.** Ids 0xb/0xc are out of
  ZGLIDE's range and do nothing.

So the plugin has a complete mipmap path (flag set -> chain built by 0x10005160, `smallLod` 8) that this exe never
turns on.

**dgVoodoo.** The stock dgVoodoo.conf (`i76-everywhere\dgVoodoo.conf`, Version 0x278) documents these `[Glide]`
texture keys only: `TMUFiltering` ("appdriven", "pointsampled", "bilinear") and `DisableMipmapping` (bool). The daily
driver conf (`dgVoodoo.daily-driver-2026-10-03.conf`, Version 0x287) has `TMUFiltering = bilinear` and no
`DisableMipmapping` line. There is no documented `[Glide]` key for LOD bias, forced mipmaps or anisotropy, and
`DisableMipmapping` can only remove mipmaps. Since the game uploads a single level and disables mipmapping itself,
dgVoodoo has nothing to work with: **no conf change can make far textures more detailed.**

## 2. Terrain: the texture level per leaf (the main finding)

`renderer_SetTerrainTextureNames` 0x4908f0 takes the mission's terrain texture name (WDEF +0x6c, e.g.
`tp041db6.map`; character 4 must be '1') and builds five names with character 4 = '2'..'6' (loop 0x490949: the first
store writes `'1'+1`). `renderer_LoadTerrainTextures` 0x4909b0 loads them as texture pairs (8-bit + .m16) into
0x5a4588[0..4] and copies entry 4 into entries 5 and 6. Without a valid name the defaults are `terr256.map`,
`terr128.map`, `terr64.map`, `terr32.map`, `terr16.map` (pointer table 0x4fad58).

Sizes read from I76.ZFS for the sets the missions name (hardware uses the .m16):

| set (example) | level 0 ('2') | level 1 ('3') | level 2 ('4') | level 3 ('5') | level 4..6 ('6') |
|---|---|---|---|---|---|
| tp04, tp03, tp05, tp06, tp07, tp08, tp09, tp18 (.m16 / .vqm) | 256x256 | 64x64 | 64x64 | 32x32 | 16x16 |
| tt14, tt03, tt01 (.map) | 256x256 | 64x64 | 64x64 | 32x32 | 16x16 |
| tt08, tt02, tt16, tt17, tt18 (.map) | 128x128 | 128x128 | 64x64 | 32x32 | 16x16 |
| tm15 (.map) | 128x128 | 64x64 | 64x64 | 32x32 | 16x16 |

(The '1' file is not in the table the leaf setup indexes.) All levels are loaded at mission load; every level is
tiled once per 8 samples = 40 m (UV = sample x 0.125, 0x4be80c).

The level is picked per quadtree leaf in the textured setup callback 0x4923f0 (installed at 0x490f96 when
`options_terrain_textures` is on; hardware forces it on):

```
0049244d  mov ecx, [0x6442d4]          ; camera
00492453  mov edx, [ecx+0x3c]          ; target bitmap
00492456  mov eax, [edx]               ; W = its first dword (width; 640 under Glide - assumed, see 6)
00492458  8d0480    lea eax, [eax+eax*4]
0049245b  c1e003    shl eax, 3         ; W * 40
0049245e  mov [esp+4], eax
00492462  b888000000 mov eax, 0x88
00492467  fild dword [esp+4]
0049246b  fmul dword [esp+8]           ; * arg2
0049246f  fstp dword [esp+4]
00492473  mov edx, [esp+4]
00492477  sar edx, 0x17                ; biased float exponent
0049247a  sub eax, edx                 ; level = 0x88 - exponent
0049247c  jns / xor eax,eax            ; < 0 -> 0
00492482  cmp eax, 7 / jl / mov eax, 6 ; > 6 -> 6
0049248c  lea eax, [eax*8 + 0x5a4588]  ; texture pair for that level
00492495  call 0x471f00                ; renderer_SelectTextureVariant (8-bit or .m16)
```

arg2 comes from the leaf emit loop 0x491a30: for each outline vertex of the leaf it computes `1.0 / z` (0x491d57,
0x491d8e: `fld [0x4be830]=1.0; fdiv [vertexpool + i*12 + 8]`) and keeps the largest (0x491dad..0x491dbc), pushed at
0x491df0. So arg2 = 1 / (view z of the leaf's nearest vertex), and

```
level = clamp( 9 - floor(log2( W * 40 / z_nearest )), 0, 6 )
```

With W = 640: level 0 while z <= 50 m, then one level per doubling.

| level | texture (tp04 set) | stock range | x4 | x7.2 | x8 |
|---|---|---|---|---|---|
| 0 | 256x256 | 0 - 50 m | 200 m | 360 m | 400 m |
| 1 | 64x64 | 50 - 100 m | 400 m | 720 m | 800 m |
| 2 | 64x64 | 100 - 200 m | 800 m | 1440 m | 1600 m |
| 3 | 32x32 | 200 - 400 m | 1600 m | 2880 m | 3200 m |
| 4-6 | 16x16 | beyond 400 m | | | |

Why 40 and 50 m: a 256-texel tile spans 40 m; at z = 50 m with the 640-wide focal length 320 that is 256 pixels, one
texel per pixel. The rule is a mip selection tuned for a 640-pixel-wide screen. dgVoodoo renders 4608 wide (x7.2),
so stock picks textures 7.2 times coarser than the rendered pixels can show. **A factor of about 7.2 restores the
designers' one-texel-per-pixel rule at the owner's resolution; x8 is just past it.** Beyond that the texture is
minified with no mipmaps and will shimmer (as stock already does at grazing angles).

Not involved: fog and shade (the depth shade term only brightens, 0.75 -> 1.0 by 600 m, 0x4910fe), the flat emitter
(only with Terrain Textures off in software), the leaf's draw mode (leaf size > 8 samples adds mode bit 2, 0x49242f).
There is no distance at which terrain goes untextured.

### Roads

`renderer_QueueRoadsAndDecals` 0x48e900: `0048ec12 fld [esp+0x68]; 0048ec16 fcomp dword [0x4be7bc]` (60.0): segment
midpoint view z < 60 m uses texture slot set 0, farther uses set +10 (`mov ecx, 0xa` / `xor ecx, ecx`). And
`0048ead7 fcomp dword [0x4be7b8]` (450.0): a segment whose midpoint view z exceeds 450 m is not drawn at all, far
clip or not. The far road texture set's sizes were not read.

## 3. Objects and vehicles: LOD by on-screen radius

`renderer_SelectObjectLod` 0x457f40 (rec, s), identical in all three exes (171 bytes). r = rec+0x10 (radius),
lod[] = rec+0x1c.. (from the file), s = view z x (1 / cam+0x08), metres per pixel:

```
00457f45  mov eax, [edi+0x30] / test / jne      ; rec+0x30 == 0 -> LOD 0
00457f50  mov al, [0x654b89]                    ; options_object_detail
00457f58  je 0x457fba                           ; off -> second half
00457f5a  xor esi, esi / lea ecx, [edi+0x1c]
00457f5f  fld [esp+0x10] / fmul [ecx]           ; s * lod[i]
00457f65  fld [edi+0x10] / fcompp               ; r ? s*lod[i]
00457f6c  test ah, 0x41 / je 0x457f7a           ; r > s*lod[i] -> found
00457f71  inc esi / add ecx, 4 / cmp esi, 3 / jl 0x457f5f
00457f7a  cmp esi, 3 / jge 0x457f84
00457f7f  xor esi, esi                          ; found at 0, 1 or 2 -> LOD 0 (1 and 2 collapse)
00457f86  ... call 0x458c10 (rigid body?)       ; none found:
00457f95  fld [edi+0x24] / fmul [esp+0x10] / fld [edi+0x10] / fxch
00457fa1  dc0dc0df4b00 fmul qword [0x4bdfc0]    ; 0.4
00457fa7  fcompp ... jne 0x457fe6               ; r >= 0.4*s*lod[2] -> 3
00457fb0  mov esi, 0xb                          ; else 11 (reduced vehicle)
```

With Object Detail on there are only three outcomes: **0** while the projected radius r/s exceeds the smallest of
lod[0..2]; then **3**; and for rigid bodies **11** once it is below 0.4 x lod[2]. LODs 1 and 2 are never chosen.
The draw (0x45d100 / 0x45d530) passes `lod & 7` to `object_SelectGeometryLod` 0x4466c0, which swaps the object's
.geo for the name in that LOD's row (16-byte names, 0x44673d), so an LOD change is a different mesh with its own
face textures. There is no separate texture-size choice per object: texture detail follows the mesh LOD.

Thresholds in the files (pixels of radius, at the 640-wide focal length 320 x zoom), read from I76.ZFS:

| class | lod[0..4] | files |
|---|---|---|
| vehicles (VDFC +0x1c) | 70, 45, 30, 25, 100000 | 37 of 48 .vdf |
| | 70, 35, 30, 25 / 160, 100, 70, 30 / 120, 90, 50, 20 / 100, 50, 20, 5 / 70, 45, 15, 5 / 10, 5, 2, 1 | the rest |
| scenery (SDFC +0x14) | 30, 10, 5, 4, 100000 | 118 of 371 .sdf |
| | 0, 100000, ... (always LOD 0) | 59 |
| | 100, 30, 15 / 100, 30, 10 / 160, 70, 5 / 50, 30, 5 ... | the rest |

For the common vehicle row: LOD 0 while radius > 30 px, i.e. z < r x 320 / 30 = 10.7 r; LOD 3 out to 26.7 r; the
reduced vehicle beyond. For a 3 m radius that is 32 m and 80 m (r is rec+0x10; its real values need a live read).
At 4608 pixels wide the switch to LOD 3 happens when the car is still 216 px in radius.

**The one constant.** Every caller builds s from one stack value, 1 / focal, computed once per pass:

```
0045803e  d90594df4b00  fld dword [0x4bdf94]   ; 1.0     renderer_QueueObjects 0x457ff0
00458044  d87608        fdiv dword [esi+8]     ; / cam+0x08
0045805d  fstp [esp+0x24]
00457ade  d90594df4b00  fld dword [0x4bdf94]   ; same in renderer_QueueObjectsMirror 0x457a90
00457ae4  d87608        fdiv dword [esi+8]
00457afa  fstp [esp+0x2c]
```

That slot is read only to form the argument of the eight `call 0x457f40` sites (main: 0x45817e, 0x4583ae, 0x458479,
0x45854a, 0x458651; mirror: 0x457c19, 0x457e20, 0x457ed9; the other accesses at those offsets are integer loop
counters at a different stack depth). The float at 0x4bdf94 has exactly these two references in `.text` in all
three exes. So writing 1/f there divides s by f in every LOD decision (Detail on and off, the 0.4 rule, shadows
that inherit the object LOD) and touches nothing else.

Related, not distance: `renderer_ApplyObjectDetail` 0x457870 stores -1 or -21 (0xffffffeb) into every object's
+0x14 from bytes 0x654b84 (rigid bodies) / 0x654b85 (others). That is a per-class on/off mask, not a range.

## 4. Other distance cut-offs for entities

| what | test | constant (VA, bits) | refs | site |
|---|---|---|---|---|
| object shadows | view z < 50 m, both rigid and non-rigid loops | 0x4bdfa0 `00 00 48 42` (50.0) | 2 | 0x4583d6, 0x4584a1 |
| road near/far texture set | midpoint z < 60 m | 0x4be7bc `00 00 70 42` (60.0) | 1 | 0x48ec16 |
| road segment drawn | midpoint z <= 450 m | 0x4be7b8 `00 00 e1 43` (450.0) | 1 | 0x48ead7 |
| ground clutter | view z <= 120 m | 0x4be0d0 `01 00 f0 42` (120.00001) | 1 | 0x45c619 |
| skid marks | quad midpoint z < 50 m | 0x4bd354 `00 00 48 42` (50.0) | 1 | 0x445127 |
| reduced vehicle | r < 0.4 x s x lod[2] | 0x4bdfc0 `9a 99 99 99 99 99 d9 3f` (0.4, f64) | 1 | 0x457fa1 |

Objects have no distance cull beyond the far plane (renderer.md 0x457bbd). Clutter is instanced only in the 3x3
block of 100 m cells around the camera, so a clutter range above about 100 m shows the block's square edge and
nothing exists past about 200 m.

## 5. Proposed switches (same style as `apply_terrain_lod`: read the exe's own bytes, verify, write, log)

All sites hold the same bytes in the AiO exe, the Galaxy 9a232dcc exe and the gog-extract exe. None is touched by
the current proxy (grep of strlkproxy.c) or by the AiO patch clusters.

| switch | site VA | expected bytes | new bytes | meaning | confidence |
|---|---|---|---|---|---|
| `I76_TERRAIN_TEX=f` (1..16) | 0x492458 (6) | `8d 04 80 c1 e0 03` | `69 c0 <u32 round(40 f)>` = `imul eax, eax, 40f` (x8: `69 c0 40 01 00 00`; x7.2: `69 c0 20 01 00 00`) | every terrain texture level boundary x f (256 px tile to 50 f m) | high for the mechanism; the look needs eyes |
| `I76_OBJECT_LOD=f` (1..16) | 0x4bdf94 (4, .rdata) | `00 00 80 3f` | f32 1/f (x8: `00 00 00 3e`; x4: `00 00 80 3e`) | objects keep LOD 0, and vehicles stay un-reduced, f times farther; main view and mirror | high for the mechanism; cost unmeasured |
| `I76_SHADOW_DIST=f` | 0x4bdfa0 (4) | `00 00 48 42` | f32 50 f (x8: `00 00 c8 43`) | shadows to 50 f m | medium (shadow rasteriser 0x4bb760 unread) |
| `I76_ROAD_TEX=f` | 0x4be7bc (4) | `00 00 70 42` | f32 60 f (x8: `00 00 f0 43`) | near road texture set to 60 f m | medium (far set's sizes not read) |
| `I76_ROAD_DIST=m` | 0x4be7b8 (4) | `00 00 e1 43` | f32 metres | road segments drawn past 450 m | medium |
| `I76_CLUTTER_DIST=m` | 0x4be0d0 (4) | `01 00 f0 42` | f32 metres, useful only up to about 150-200 | clutter range | low value: bounded by the 3x3 cell block |
| `I76_SKID_DIST=f` | 0x4bd354 (4) | `00 00 48 42` | f32 50 f | skid marks farther | medium |

Notes on each:

- **I76_TERRAIN_TEX.** The `imul` replaces `lea` + `shl` byte for byte; nothing after it reads flags (next are
  `mov`, `fild`). W x 40 x 16 = 409,600, no overflow. Equivalent power-of-two form: the immediate at 0x49245d
  (`03` -> `03 + n`) or the `0x88` at 0x492463 (-> `0x88 - n`). No new vertices, records or textures: all five
  levels are already resident, so the int16 vertex ceiling, the 4096 depth buckets and the pools are untouched.
  Risk: shimmer past the one-texel-per-pixel point (about x7.2 at 4608 wide); and the 256 px level replaces small
  ones in more of the frame, which only changes what is sampled, not what is uploaded.
- **I76_OBJECT_LOD.** Data patch, 4 bytes, needs the page made writable (`patch_bytes` does). More objects draw
  their LOD 0 mesh: more faces per frame through the draw-record pools (already x16 with `I76_FAR_CLIP`) and the
  per-object BSP buffers (fixed stack frames 0x55c / 0x50c, per object, unchanged). No terrain vertices. Depth
  buckets unchanged (same objects, same z). The real unknown is texture memory: LOD 0 meshes reference more and
  larger face textures at once, and the TMU is held at 2 MB (`MemorySizeOfTMU = 2048` is load-bearing); ZGLIDE
  evicts by age (0x10001380), so the failure mode would be upload thrash or missing textures, to be watched in a
  busy scene. Suggested first value 4, then 8 (7.2 restores the authored pixel thresholds at 4608 wide).
  An entry hook on 0x457f40 (`57 8b 7c 24 08`) would do the same with code; the data patch is smaller.
- **I76_SHADOW_DIST.** One constant, two reads. Shadow records are kind 3 / 11 and join merge groups (0x6543b4);
  more of them per frame. With Shadow Detail 2 they take the object's LOD, so `I76_OBJECT_LOD` raises their cost too.
- **Road, clutter, skid.** Single-reference floats. `I76_ROAD_DIST` matters with a raised far clip: roads stop at
  450 m today whatever the far clip is.

Order of value for the owner's request: `I76_TERRAIN_TEX=8` (terrain) and `I76_OBJECT_LOD=4..8` (entities) are the
two that answer it. The rest are optional.

### Not proposed, noted: real mipmaps

ZGLIDE's unused mipmap path could be switched on with one byte in the DLL: 0x10001c60 `89 3d 68 ee 01 10`
(`mov [flag], edi` = 0) -> `89 1d 68 ee 01 10` (`mov [flag], ebx` = 1). FirstDevice would then call
`grTexMipMapMode(tmu, GR_MIPMAP_NEAREST, FXFALSE)`, and every upload would carry a chain down to 1x1 built by
0x10005160. dgVoodoo would then mip by the real 4608-wide pixel footprint, which is the proper cure for shimmer
once detail is pushed out. Low confidence: the chain builder is unread, the path has never run with this exe,
chains cost a third more TMU memory against the 2 MB limit, and ZGLIDE is relocatable (patch by RVA 0x1c60 after
load, bytes verified). An experiment for the sandbox only, after the two switches above have been looked at.

## 6. Could not be determined statically

- **W in the terrain formula.** `[[cam+0x3c]]` is the target bitmap's first dword; taken as width 640 because the
  game submits 640x480 under Glide. If it is another value every range in section 2 scales with it. A live read of
  `[[0x6442d4]+0x3c]` settles it.
- **World record radii** (rec+0x10) for cars and scenery, so the LOD distances in metres are only the 10.7 r / 26.7 r
  rule.
- **What LOD 3 looks like** per vehicle, and which face textures the LOD 0 and LOD 3 .geo files name (not parsed).
- **Texture memory pressure** from more LOD 0 meshes under the 2 MB TMU, and whether the exe's texture cache (which
  the AiO exe patches near 0x44745b..0x44778a) copes.
- **Shimmer** from unmipped 256 px terrain tiles at range: visible only on screen.
- **Frame cost** of far LOD 0 objects and far shadows.
- **ZGLIDE's mip chain builder** 0x10005160 and its palette handling.
- **The far road texture set** (slot set +10): sizes not read.
- **The daily driver's exe**: not among the files compared.
