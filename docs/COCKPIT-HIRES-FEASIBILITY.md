# Cockpit at double resolution: feasibility and plan (research only, 2026-10-10)

Owner's goal: "double the resolution in the cockpit - i think it should be reasonable although i appreciate it's an
engine change." Target build: `-glide` (i76.exe -> ZGLIDE.DLL -> dgVoodoo 2.87.3 Glide2x), `best-wide` preset
(640x480 frame, `[Glide] Resolution` 5160x2160 presented stretched to 3440x1440, `I76_ASPECT`, HUD squeeze). The 3D
scene is already sharp because dgVoodoo rasterises the polygons at the forced resolution; the cockpit art is
1997 bitmaps magnified by bilinear filtering.

Nothing was run, patched or installed for this document. Every address is from the <re-archive> / lab static reads cited
inline (exe md5 9a232dcc / AiO 85de44a7, ZGLIDE md5 05c1dde4). The one new measurement is an offline census of the
cockpit geometry in the owner's extracted archive (section 1.4), done with a throwaway script against
`<upscale-work>\extract\` (the U1 sprint's extraction of I76.ZFS); it is reproducible from the
layout in section 1.4 and should become a tracked tool when the plan starts.

**Verdict in one paragraph.** The cockpit cannot be made sharper by shipping bigger files: every static cockpit
texture is already 256 texels on its long side, and 256 is the ceiling of the Glide 2 API that ZGLIDE speaks and
dgVoodoo implements (section 2.1). There is one route that doubles the *static* dash under dgVoodoo with **no
exe patch**: re-author the cockpit mesh so each dash face is split into four, each quarter mapped to its own
256x128 tile of a 512x256 upscale (section 3, option B). It is a data change (two ADDON pak overrides per car), the
format pieces are all decoded and round-trip, and a marker test proves or kills it in three console boots. It does
**not** touch the live gauge faces (radar, damage, weapon panel, compass, gear, mirror), which are 8-bit bitmaps the
engine paints into at hard-coded pixel positions and re-uploads; those stay 256 wide under any Glide route. The only
"everything at any resolution" path is a renderer that is not Glide 2 (OpenGLide-HD), which costs the dgVoodoo stack
the owner plays on. Recommended first experiment: the Piranha's lower dash (`PP51DASH.geo` + `zdash106.pak`) at 2x,
built offline, three boots of t01 on `game-tex`.

---

## 1. How the cockpit and gauges are drawn

### 1.1 Two cockpits, one key

F1 is the cockpit view (camera view 0xe, in-cockpit flag `0x4c2724`); pressing F1 again flips byte `0x654b88`
"cockpit panel shown" (<re-archive> `subsystems/renderer.md`, "Two cockpits, one switch", 2026-10-04e). The owner's default
is the 3D cockpit: music-fix README row `I76_HUD_SQUEEZE`: "The 3D cockpit (F1 default) is a mesh and was already
right".

| state | what draws | resolution-relevant facts |
|---|---|---|
| **3D cockpit** (`0x654b88` = 1, the default) | `renderer_DrawCockpit` 0x45adf0 draws the player's own car at **LOD slot 4** through the object draw 0x45dcc0. The instrument faces are live textures repainted by the gauge painters; speedo/tach needles are sub-objects (VLOC 35/36) rotated per frame. No 2D overlay. | Textured polygons: dgVoodoo rasterises them at 5160x2160, so edges are sharp and the **texels** are the limit. Lit like any object (L1e: "No exemption"). |
| **2D dash** (`0x654b88` = 0) | `renderer_DrawInstrumentOverlay` 0x45be20 blits up to nine bitmaps over the 3D view (table 0x4f67d8, 0x20 bytes per mode x slot), 2D sprite needles, the mirror bitmap in slot 7, reticles after. | On the Glide path each bitmap is one screen-space quad **1:1 in the 640x480 frame** (section 1.3). |
| **GOSTPIT** (`TOGGLE_GOSTPIT_DETAIL`, command 0xc, hardware only, sets 0x54ac68) | 3D cockpit not drawn; the overlay runs with radar, damage, compass only, plus radar blips as quads (0x460190). | Same bitmaps; no resolution help. |

Sources: renderer.md 2026-10-04e (K1) and 2026-10-05c (K1h/K1g4); camera.md "HUD drawing"; ARCHITECTURE.md §8.

### 1.2 The 3D cockpit's assets (what the LOD-4 mesh references)

The cockpit mesh is the car's **LOD slot 4** part set: VGEO rows whose part names have '5' as third character
(`xx51DASH`, `xx51SEAT`, `xx51SWHL`, `xx51MIRI`, `xx51RADR`, ...; <re-archive> `data/notes/vdf.md` §6 "o = 4 (inferred:
cockpit set)"). The `.geo` files live in the car's geometry pack `<car>g.pak` (e.g. `vppirnag.pak` for the Piranha).
Each face names a texture (`texture[13]`, e.g. `ZDASH101.MAP`); the engine resolves the stem through its pack
index, and in `-glide` loads the `.M16` twin (hardware set) where one exists (FINDINGS-2026-07 §5: "in `-glide` ...
the engine loads the M16 `*6.pak` sets - established in-game by installing distinct markers into both formats").

Cockpit texture inventory (census over all 48 `v*g.pak`, LOD-4 members only, 1073 .geo files parsed with zero
layout mismatches; archive files from `i76-upscale-work\extract`):

| texture (as named in .geo) | file that is loaded under -glide | size | kind | cars | 2x headroom under Glide 2? |
|---|---|---|---|---|---|
| ZDASH101/102 | `zdash106.pak` -> ZDASH101.M16, ZDASH102.M16 | 256x128 each, flags 0x80, 255-colour RGB565 palette | static dash art | 21 (Piranha, Leprechaun, all the AG/AS/AZ/CC... set) | **none** (256 wide) |
| ZDASH201/202 | `zdash206.pak` | 256x128 x2 | static | 8 (Sovereign, Dreadnought, Royale, Police, Stag, Clydesdale, Vikea, Hearse) | none |
| ZDASH301/302 | `zdash306.pak` | 256x128 x2 | static | 5 (Loadmaster, Tanker, Moth, Van, Bus) | none |
| ZDASH401/402 | `zdash406.pak` | 256x128 x2 | static | 1 (Huey; 9 faces) | none |
| ZDASH501/502 | `zdash506.pak` | 256x128 x2 | static | 1 (Grappler) | none |
| ZDASH601 | `zdash606.pak` | 256x128 | static | 1 (Cobra) | none |
| ZHR45101.TMT / ZHL45101.TMT (x5 schemes) | loose `zhr45n0N.m16` (6 frames), `zhl45n06.pak` (9 members) | 256x256 | hand/gun animation frames (.tmt) | 44 | none |
| ZSWLS101.TMT (x5) | loose `zswlsN01..36.m16` | 256x128, 36 frames | steering wheel animation | 40 | none |
| ZMIRI101.MAP | `zmiri101.map` only (no M16; renderer.md K1e4 "medium-high") | 256x64 8-bit | **software render target** (mirror) | 44 | none (and not art: see 1.5) |
| ZRADF000.TMT | `zradf000.pak` (62 VQM frames, RADAR.CBK) | 256x128 | **painter target** (radar) | 45 | none |
| ZSY_.MAP (+ _320) | `zsy_.map` | 256x128 8-bit | painter target (damage diagram) | 45 | none |
| ZBK_.MAP, ZBKS_.MAP (+ _320) | `zbk_.map`, `zbks_.map` | 256x128 8-bit | painter targets (weapon panel, specials) | 45 | none |
| ZGEAR101.MAP | `zgear101.map` | 256x32 8-bit | painter target (PRND) | 44 | height only |
| ZCM_.MAP (+ _320) | `zcm_.map` | 64x64 8-bit | painter target (compass) | 45 | 2x in size, but painted at pixel labels (1.4) |
| ZRETC_1 / ZRETC_6 | `zretc_1.map` 32x32, `zretc_6.map` 128x128 | | reticle faces (ZRETC_6 "unused" by the overlay, used by the mesh) | 45 | 2x/4x possible for these only |
| `V1 BO DY.MAP`, `V5 FT TP.MAP`, `V1 FT TP`, `V5 BK FT`, car-specific `JS11HN_1.MAP`, `DS11TP_1.MAP`, `PP51MIRR.MAP` ... | resolved per car through the VTF/TMT paint chain to `<car><scheme>6.pak` M16 tiles (FINDINGS-2026-07 §4.2) | **unknown here**; vehicle panels are mostly 128x64 / 128x128 (TEXTURE-DELIVERY §1) | the car's own interior/body skin seen from inside | 24+31 | **yes if 128 or smaller**: the proven `car_pack.py` 2x route (lab U5/CAR1) |

So in the owner's Piranha cockpit the textured surfaces are: 2 dash tiles, 1 mirror, 10 painter faces, 2 animated
M16 sets (hands, wheel), the reticles, and 103 faces of the car's own skin (`V1 BO DY` 74 + `V5 FT TP` 29) whose
resolution the CAR1 2x pack may already have raised (unverified in the cockpit view: the CAR1 captures were chase
view).

### 1.3 The exact draw path and the coordinate math

**3D cockpit face -> screen.** Object draw 0x45dcc0 -> polygon records -> `renderer_DrawPolyHW` 0x4260d0 -> ZGLIDE
`Render` (export bound into 0x608bb0). The exe hands each texture to ZGLIDE as `{w, h, pixels, palette}` from the
file header (`renderer_UploadTexture` 0x431ca0: `mov ecx,[eax]` w, `mov edx,[eax+4]` h|flags, pixels at +8, palette
via 0x42cd60, colour key index 0xff at +0x10). ZGLIDE 0x10001930 derives `largeLod = 8 - log2(w)` by scanning bits
8..0 of w, the aspect from `log2 w - log2 h + 7` (jump table 0x10001b7c), converts **every** texture to ARGB1555
(0x10001126..0x100011b5; `[0x1001fd24] = 1` branch because the I'76 device descriptor sets flags 0x300), and
uploads with `grTexDownloadMipMap`. Vertex UVs are normalised 0..1 in the .geo (`{vertex, normal, u, v}` vrefs,
FORMATS.md §7) and ZGLIDE scales `s = u * [0x1001a030] * oow * 255.0` (0x10002b9b..0x10002bc6). Mipmaps are never
enabled (`FirstDevice` zeroes the flag; TEXTURE-AND-OBJECT-LOD.md §1), filtering is `grTexFilterMode` per polygon
(point when the per-call flag and `[0x1001f754]` are set, else bilinear; CLUTTER-AND-MIRROR.md §2) and the conf
forces `TMUFiltering = bilinear` (`dgVoodoo.windows.conf` line 68). All of this is from lab
`docs\TEXTURE-DELIVERY.md` §1 (static) and its 2026-10-03 live run: a 256x128 M16 replacing a 128x64 one rendered
correctly, "UVs are normalised; nothing on the Glide path assumes a texture's size."

**Magnification.** In the start-line cockpit capture the dash face spans most of the view width. With the frame at
640 logical pixels across 3440 panel pixels (5.4x), a 256-texel tile that covers, say, 60% of the width is
magnified about `0.6 * 3440 / 256 = 8x` horizontally; bilinear filtering turns each texel into an 8-pixel blur.
That is what the owner sees. Doubling the texels halves it; a 4x split would quarter it.

**2D dash bitmap -> screen** (`renderer_BlitBitmap` 0x45b450, decompile `<re-archive>\ghidra\export\functions\0045b450.c`):
the region is `param_2[7..10]` (x0, y0, x1, y1 in bitmap pixels); on the hardware path (`piVar5[2] == 1`) it builds a
4-vertex quad at `(x, y)` to `(x + regionW, y + regionH)` **in frame pixels, 1:1 with the art**, with UVs
`x0/(w-1) .. x1/(w-1)` and `1 - y/(h-1)` (or `/w`, `/h` when `param_7 == 5`), texture = the bitmap's own pixel
buffer minus 8 (`param_2[5] - 8`, i.e. the .map header), draw mode `0xc | 0x40` (textured, screen space, colour
key), and makes the single `call 0x4260d0` at 0x45b87a - the site `hud_quad_wrap` already repoints (strlkproxy.c
~6186). The fractions in table 0x4f67d8 feed only the software scaled blit (0x47a220). Consequence: a 2x bitmap would
draw at 2x the screen size unless the quad is halved in the same wrapper (cheap), **but** the painters that draw
into these bitmaps work in bitmap pixels (next item), so the 2D dash is pixel-locked at several layers.

### 1.4 Why the gauge faces are pixel-locked

`vpit_1.elt` (34,106 bytes, named by VDFC ELT, loaded by `elt_Load` 0x448010) is a text table: `dst zrad.map` /
`label range_pos 139 4` / `label led_pos 150 84` / `dst zspeedo6.map label speedneedleloc ...` / `src zneedle6.map
label needle_1 ...`. The `dst` labels are **pixel positions inside the face bitmap**, the `src` labels are sprite
rectangles in sprite sheets (`zneedle6.map` 400x640, `zsye.map` 305x130, `zdse.map` 186x291, `znbe.map` 8x110,
`zrge.map` 24x72, `ztge.map` 11x22, `zdde.map` 70x16, `zbar_.map` 180x3, `zcme.map` 303x18). The painters blit
sprites at those pixels with the software blitter and invalidate the texture ("Weap", "Status", "RearView"):
weapon panel `renderer_InitWeaponPanel` 0x4a45c0 / diodes 0x4a4d50 / ammo roll 0x4a4e40 (`image_BlitEltSpriteScrollY`
0x4a4f44); damage diagram 0x45a450; compass scroll and 2D needles in 0x459fa0; gear 0x45ad40; radar painter
0x460310 with blips at `(trunc(99 + 51 x), trunc(65 + 51 z))` as 2x2 pixels - **constants in the exe**, not data
(camera.md "HUD drawing", renderer.md K1h). Doubling any of these faces means doubling the .elt labels, every sprite
sheet, and the hard-coded blip/needle maths, with the .map pixel buffers re-allocated - exe work in a dozen
functions. Out of scope for a texture lab; recorded here so nobody re-derives it.

The .geo layout used for the census (confirms FORMATS.md §7 and fixes one detail: the flat colour is 3 bytes):
`'OEG.'`, u32, name[16], u32 nVerts, u32 nFaces, u32 0; nVerts x float3 positions; nVerts x float3 normals; per face:
u32 index, u32 nCorners, u8[3] RGB, float4 plane, u32 0, u8[3] surface, char[13] texture, u32 parent, u32 side,
then nCorners x {u32 vertex, u32 normal, float u, float v}. Parsed 1073/1073 LOD-4 members to exactly their
length.

The Piranha's dash (`PP51DASH.GEO`, 800 bytes, 12 vertices, **4 faces**; identical UV layout in the Leprechaun and
the Sovereign's `JS51DASH` with ZDASH2xx):

| face | texture | corners | u range | v range | surface bytes |
|---|---|---|---|---|---|
| 1 | ZDASH101 | 4 | 0.000..0.087 | 0.798..1.000 | 04 01 00 |
| 2 | ZDASH102 | 4 | 0.000..0.960 | 0.000..1.000 | 04 01 00 |
| 3 | ZDASH101 | 5 | 0.000..1.000 | 0.000..1.000 | 04 01 00 |
| 4 | ZDASH102 | 3 | 0.000..1.000 | 0.866..1.000 | 04 01 00 |

Mirror face `PP51MIRI`: one quad, ZMIRI101, u 0..1, v 0..1, surface 04 05 00.

### 1.5 The mirror

Not art: `mirror_Init` 0x445380 makes a private writable copy of ZMIRI101's pixels (0x44a740), and
`renderer_DrawRearMirror` 0x445750 software-rasterises the scene into that 256x64 8-bit bitmap every 2nd frame,
keys the frame art back over it, and re-uploads ("RearView" invalidated; ZGLIDE `UpdateTexture`, the one call at
0x431cf5). Its resolution is the texture's whatever dgVoodoo renders at (ENHANCEMENTS.md "Rear mirror: farther, not
sharper"; CLUTTER-AND-MIRROR.md §2: raising 64 rows to 128 "is a project, not a switch"). Excluded from this plan.

---

## 2. What limits resolution

1. **Glide 2 has no texture larger than 256.** `GrLOD_t` in the Glide 2 SDK header: `GR_LOD_256 0x0` is the largest
   value, down to `GR_LOD_1 0x8`; aspect ratios 8:1..1:8 (`sdk2_glide.h` as shipped in voyageur/openglide, fetched
   2026-10-10: https://raw.githubusercontent.com/voyageur/openglide/master/sdk2_glide.h). ZGLIDE's size scan looks at
   bits 8..0 only; a 512-wide texture yields a LOD that is not a Glide 2 value (TEXTURE-DELIVERY §1). dgVoodoo's
   `[Glide] VideoCard` offers `voodoo_graphics, voodoo_rush, voodoo_2, voodoo_banshee, other_greater`
   (TEXTURE-DELIVERY §2 quoting the conf; same list quoted in a VOGONS post found 2026-10-10) - none is a Voodoo 4/5,
   and the question is moot because ZGLIDE is a Glide 2 client and cannot *express* a bigger texture. Whether
   dgVoodoo would accept a non-standard LOD code: **unknown and irrelevant**. "There is no route past 256 that keeps
   dgVoodoo's Glide" (TEXTURE-DELIVERY §3).
2. **Every static cockpit texture is already at 256** (table 1.2). This is why the July pack and the U-sprint's
   "dash" class could only clean, not add resolution (U2: dash class winner Manga109 x RRDB_PSNR 0.5, LPIPS 0.0026,
   judged against the same-size original).
3. **Painter faces are pixel-locked by the .elt labels and exe constants** (1.4). Also 8-bit: without an M16 twin
   they are coloured through the global table 0x608980 from the mission's `_16.act` palette, cut to 1555, index 0xff
   forced transparent (renderer.md K1e4).
4. **TMU memory.** ZGLIDE bump-allocates, recycles the oldest same-size texture, and when no same-size victim exists
   draws with the wrong texture and flushes next frame (TEXTURE-DELIVERY §2). ARGB1555 = 2 bytes/texel: a 256x128
   tile is 64 KB, a 256x256 is 128 KB. Any scheme that multiplies cockpit tiles needs `MemorySizeOfTMU` above 2048
   **with** `I76_ZGLIDE_TMUFIX=1` (the 0x1a93 one-byte fix; proven n=1 at 16384 on t01, 2026-10-03).
5. **No mipmaps, forced bilinear** (1.3): magnification is a plain bilinear blur of the texel grid, so the visible
   gain of 2x is "half the blur", exactly like the CAR1 result at play distance ("real but subtle"). In the cockpit
   the magnification is 3-4x larger than on a chase-view car, so the same 2x should read more clearly - that is the
   hypothesis the first experiment tests.
6. **Palette.** M16 tiles carry their own 255-colour RGB565 palette (immune to day/night palette swaps); a 2x
   upscale quantised to 255 colours per 256x128 tile is what CAR1 already ships (227-255 colours per tile, no
   visible banding reported).

---

## 3. Options, ranked by effort and risk

Odds are this reader's estimate; nothing below has been tried.

| rank | option | what it gives in the cockpit | engine change | effort | risk | odds |
|---|---|---|---|---|---|---|
| **1 (first)** | **B. Tile-split the static dash** - 2x upscale of ZDASHn01/n02 cut into 4 x 256x128 M16 tiles each; re-author the `xx51DASH.geo` faces so each quarter maps to its tile; ship both as ADDON pak overrides | the lower dash at 2x (the largest, closest surface); hands and wheel later the same way | **none in the exe or ZGLIDE**; two data overrides | 1-2 days offline tooling + 3 console boots | TMU pressure; seams; pack-index unknown (3.B) | 55 % |
| 2 | **A2. Car interior skin at 2x** via the existing `car_pack.py` (CAR1) | the car's own body panels seen from inside (103 of ~130 Piranha cockpit faces) if they are <=128 px | none | hours (pack exists for the Piranha; verify in the cockpit view) | none new | 80 % that they are 2x-able; gain unmeasured |
| 3 | **A1. Same-size enhanced art** (July recipe, M16 only, now on `zdash106` not `zdash101`) | de-dither / cleaner edges, no new texels | none | hours | the July verdict: "about the same" | low gain, certain delivery |
| 4 | **F. OpenGLide-HD** (hash -> PNG at any size, `tools\openglide-hd\0001`) | everything incl. painter faces (hash changes with content, so painted faces need a per-frame scheme) | replaces dgVoodoo; loses `best-wide`, MSAA, gamma stack; 256COLOR shim; DDraw collision | days to weeks; "not verified end-to-end" since July; builds and runs t01 at 180 fps (lab 2026-10-03) | daily-driver regression | 30 % as a daily driver |
| 5 | **C. Proxy shim at `grTexDownloadMipMap`** (IAT hook on ZGLIDE's glide2x imports; the proxy already hooks `_grSstWinOpen@28` and counts `_grTexDownloadMipMap@16` in the texture census) | content replacement by hash, full 16-bit colour, no night-palette issue - **but same 256 ceiling** | proxy only | medium-high (needs a proxy-owned TMU allocator because ZGLIDE sizes slots from the original LOD: TEXTURE-DELIVERY route b) | allocator bugs = wrong textures | does not meet the goal |
| 6 | **D. Our own hi-res overlay** (a D3D11/GL layer over dgVoodoo's swapchain, or a ReShade addon, drawing gauges from the game's state: speed via 0x46a7b0, rpm engine+0x1c, lever, 15 damage parts, ammo, radar list obj+0x70) | sharp gauges | none in the exe; a second presenter | weeks; must hide the stock faces (impossible without geo edits), survive Alt+Enter / mode switches, be synced per frame | a second presenter on dgVoodoo's HWND (WIDESCREEN-2D (a) fallback rates a similar idea 40 %); the 3D dash behind it stays blurry | 20 % |
| 7 | **E. Community HD packs** | - | - | - | - | **none exist**: HD-TEXTURES-RESEARCH 2026-07-09 sweep (VOGONS, ModDB, GOG forums, PCGW, interstate76.com); a 2026-10-10 search found only frame-rate patches and the Rendition wrapper notes |

Not applicable: dgVoodoo texture dump/replace. Its General readme (fetched 2026-10-10, both halves) has no such
feature; the Glide readme URL 404s; the VOGONS request thread (t=66553, cited by HD-TEXTURES-RESEARCH as "called
feasible by Dege, never built") returned 403 today, so that quote stays second-hand.

### 3.A1 / A2 Same-size and car-skin routes (no engine change)

- A1 is the retired July pipeline pointed at the right file: under `-glide` the dash is `zdash106.pak` (M16), not
  `zdash101.pak` (VQM). texture-lab/README.md's zdash101 workflow edits the software-path tile; FINDINGS-2026-07 §5
  established that `-glide` loads the `*6` sets. (Correction to record: HD-TEXTURES-RESEARCH.md calls zdash101..601
  "day, VQM" and zdash106..606 "night, M16"; the census shows the 01/06 pair is the software/hardware pair, exactly
  like `zcbh3101`/`zcbh3106` and `pirana1m`/`pirana16`. Night is a palette swap, which M16 ignores.) The U-sprint
  tooling (`tools\upscale\upscale_run.py`, dash class) supersedes `texture-lab\enhance_cars_m16.py` for this.
- A2: check whether `V1 BO DY` / `V5 FT TP` resolve to Piranha `pp11*/pp12*` M16s (the CAR1 pack in
  `game-tex\ADDON\pirana16.pak` has all 38 at 2x). One cockpit-view capture with and without the pack answers it. If
  yes, the interior door/dash-top surfaces already have the 2x route and the plan below only needs the ZDASH tiles.

### 3.B Tile-split (the recommended experiment)

**Idea.** The dash face maps u 0..1, v 0..1 of a 256x128 tile. Upscale the tile to 512x256, cut it into four
256x128 quarters `Q00 Q10 Q01 Q11`, and replace each dash face by its intersection with the four UV quadrants, each
sub-face naming the quarter tile and with UVs remapped `(u, v) -> (2u - i, 2v - j)`. Glide then samples 4x the
texels over the same screen area. The 5-corner face (table 1.4) becomes up to 4 polygons; a quadrant that the face
does not touch yields none. ZGLIDE's polygon records take 1..31 vertices (ARCHITECTURE.md §8), and the engine
rebuilds its own BSP from the faces at run time (FORMATS.md §7: "The engine ignores the file's BSP and rebuilds its
own at run time (0x45cbe0)"), so adding faces is legal.

**Files to produce (per car, Piranha first):**
1. `ADDON\vppirnag.pak` + `.pix`: every member byte-identical except `PP51DASH.GEO` (12 -> up to ~24 vertices,
   4 -> up to 16 faces, plane and normals copied from the parent face). The .pix is a text manifest with offsets
   (FORMATS.md §6), rewritten by the existing `i76img.py makepak`-style writer.
2. `ADDON\zdash106.pak` + `.pix`: the original ZDASH101.M16 / ZDASH102.M16 kept (20 other cars still reference
   them) plus eight new members, names <= 8 characters + `.M16` (the .geo texture field is 13 bytes), e.g.
   `ZDSA1Q00.M16`.
3. Marker variant first: pixel-replicated 2x (no model), one palette slot magenta, a 1-texel checker in each
   quarter and a 1-texel border at the quarter edges - the same logic as `tools\upscale\m16_scale_marker.py`, which
   also documents what each outcome means.

**Unknowns the marker run settles (each is a kill criterion):**
- Does the pack index accept new member names from an ADDON .pix? The index is built from .pix files (FORMATS.md
  §6, 0x470660) and ADDON is container slot 0 of the ZIX (vfs_LoadZix 0x4b23e0), so names in an overriding .pix
  should register; **unverified**. If not, fall back to re-using existing names: e.g. make the Piranha's four
  quarters replace ZDASH101/102 **and** the two members of another unused set (ZDASH601 is used by one car only)
  for a test, or hook `m16_Acquire` 0x471980 in the proxy to redirect names (TEXTURE-DELIVERY route d, low effort).
- Seams: bilinear filtering at a tile edge samples the clamp/wrap of that tile. Mitigation built into the tool:
  duplicate the neighbouring texel row into each quarter's edge (so the 256x128 quarter holds 254x126 unique texels)
  and inset the remapped UVs by half a texel. Surface byte 2 of the dash faces is 0x01; which bit means "UV wrap" vs
  clamp in the render-mode table 0x4f71b8 is listed in FORMATS.md §7 but not decoded here - check before relying on
  clamp.
- TMU: the Piranha dash goes from 128 KB to 512 KB resident. Run with `MemorySizeOfTMU = 4096` +
  `I76_ZGLIDE_TMUFIX=1` and the texture census (`I76_TEX_CENSUS=1`: downloads, NO-SLOT events, flushes).
- The 5-corner face: assumes UV is affine over the face so quadrant clipping can interpolate positions linearly.
  Check offline by fitting u, v against position for the 5 corners (residual ~0 expected for a planar quad-plus-one
  face); if not affine, triangulate first.
- The hands and wheel are `.tmt` animations (6 and 36 frames). Splitting them means four `.tmt` files and four
  faces per animated face, and each frame change uploads 4 tiles; the wheel at 36 x 4 x 64 KB = 9 MB of distinct
  textures through a same-size-recycling allocator. Do the dash first; decide on the animations with the census
  numbers in hand.

**What B cannot fix:** radar, damage, weapon, specials, compass, gear faces (painted, 1.4) and the mirror (1.5).
In the Piranha cockpit those are the instrument cluster; the dash shell, hands and wheel are what B sharpens. The
owner should see a cockpit mock-up (section 4, stage 0) before anyone writes the geo tool, to decide whether a
sharp shell around soft gauges is worth it.

### 3.C Why a `grTexDownloadMipMap` shim is not the answer

It sits below the 256 ceiling. Its merit is hash-based replacement of palette-indexed textures with full colour
(the night-palette breakage that retired the July pack cannot happen when the replacement is keyed by the
converted ARGB1555 content), but it must also own TMU allocation (ZGLIDE sizes slots from the original LOD; a bigger
replacement would overwrite the next texture). TEXTURE-DELIVERY §3 route (b), §6 sketch. Keep it as the later
vehicle for A1-type content if the per-pak rebuild gets tiresome; it does not double anything.

### 3.D Overlay

The data is reachable (the proxy and `tools\ffb` already read entity speed, velocity, steer; the needle inputs are
the mph getter 0x46a7b0 and engine+0x1c; the painters' sources are listed in camera.md "HUD drawing"), and the
telemetry UDP (`ffb-telemetry-udp.ps1`, LFS OutGauge layout) could feed a SimHub dashboard on a second display with
no engine work at all - that is the honest cheap form of D. An in-window overlay must present onto dgVoodoo's
swapchain or over its window and must hide the stock faces, which in the 3D cockpit are mesh faces (would need B's
geo tooling anyway to retexture them black). Rank it after B; revisit if B lands and the gauges become the only
soft thing left.

### 3.F OpenGLide-HD

The only route that lifts the ceiling for every texture, and the painted faces too (the hash changes with each
repaint, so the replacement would have to be a *filter* - upscale whatever arrives - rather than a lookup; the
patch's `PGTexture::MakeReady` hook is the right place for that, ~tens of lines). Costs: it replaces
`Glide2x.dll`, so `best-wide` (dgVoodoo `ScalingMode`, forced resolution, MSAA, gamma), the 256COLOR compat
flag, the DDraw collision at boot and the 2 MB INI rule all come back (tools\openglide-hd\README.md; lab
OPENGLIDE-HD-WINDOWS-2026-10-03.md: runs t01 at 1920x1440, 180 fps, LFB path fine). If B's result says "the owner
wants the gauges too", this is the next project, not a texture-lab job.

---

## 4. Staged plan for the texture-lab

Everything offline runs against the owner's own extraction (`i76-upscale-work\extract` or a fresh
`tools\zfs_extract.py` run) and writes to gitignored folders; only scripts are committed. Console steps follow
`<lab>\CONSOLE-LOCK.md` and target `game-tex` (never the daily driver: memory "Never experiment on the
daily driver").

**Stage 0 - decide with a picture (offline, 1-2 h).** Render a cockpit mock-up: take the start-line cockpit capture
(lab `captures\graphics\look\hudsq2-on-*.png` or a new one), and composite the ZDASH101/102 region at 1x, 2x
(U2's dash recipe) and 4x using the face UVs from 1.4 as a crude projective fit, leaving the gauges untouched.
This shows the owner what B buys and what it leaves. Also the A2 check: one cockpit capture with and without
`game-tex\ADDON\pirana16.pak` (CAR1). Decision point.

**Stage 1 - tooling (offline).** A tracked script `tools\upscale\cockpit_split.py` (name provisional) that:
reads `<car>g.pak/.pix` and `zdashN06.pak/.pix` from the archive (reuse `<re-archive>\tools\i76fmt\zfs.py` as
`m16_scale_marker.py` does); parses the LOD-4 dash .geo with the layout in 1.4; clips each ZDASH face into UV
quadrants; writes the new .geo, the repacked `<car>g.pak/.pix`, and `zdashN06.pak/.pix` with the quarter tiles
(`i76img.parse_m16` / `build_m16`); `--marker` for the pixel-replicated magenta variant, `--png-dir` to accept
real 512x256 upscales; a JSON manifest with md5s; a self-check that re-parses every member it wrote and that all
untouched members are byte-identical. Unit tests on the layout (parse all 1073 LOD-4 members to exact length, as
the census did) and on the clipper (quadrant areas sum to the face area; UVs within 0..1).

**Stage 2 - first experiment on the console (3 boots of t01, about 4 minutes).** Piranha, `game-tex`:
1. `control`: stock, cockpit view at start (`proxy-run.ps1 -GameDir ..\game-tex -Mission t01`, capture the start
   view; F1 is the default so no key is needed).
2. `marker2x-split`: the marker pak pair in `game-tex\ADDON`, same capture. Pass = a crisp 1-texel checker over the
   dash shell with the quarter borders invisible or thin; fail modes per `m16_scale_marker.py` (stock art = override
   not loaded; only one quarter magnified = UV remap wrong; white/wrong textures = allocator; crash = read the
   proxy `CRASH` line).
3. `art2x-split`: the real upscale. Side-by-side crops of the dash shell vs control; owner judges blind
   (`tools\upscale\ab_viewer.py` on the crops).
   Record in each run: proxy log `tex-census` lines (download count, NO-SLOT, flushes), fps from telemetry, and
   whether the 2D dash (press F1 once) is unchanged. Use `dgVoodoo.tmu16.conf` + `-ZglideFix` as
   `run-tex-scale-test.ps1` already does if the census shows NO-SLOT at 2048.

**Stage 3 - the owner's route and regressions (3-4 boots).** Bookmark -> garage -> mission (the car load path is
what changed; memory "Test the owner's route before installing"); one mission in another car with the same dash set
(Leprechaun melee: must still render stock ZDASH101/102 from the same pak); a night mission (M16 palettes are
per-tile, expect no change); F1 2D dash and GOSTPIT toggle unchanged.

**Stage 4 - extend.** The other five dash sets (same tool, `--car` per geometry pak: 21 + 8 + 5 + 1 + 1 + 1 cars
share six dash sets, so 6 tile builds and 37 geo edits); then the hands and wheel if the census numbers allow;
then A2 for the roster (CAR1's `car_pack.py`).

**Stage 5 - decision on the gauges.** Either accept, or open the OpenGLide-HD or overlay project with the B result
as evidence of what the owner wants.

Cost estimate: stage 0 half a day; stage 1 one to two days; stages 2-3 one console session; stage 4 a day of
compute and a few sessions.

---

## 5. Legal and redistribution

- The repo ships no game files and no derived art: THIRD-PARTY.md ("ships no copyrighted game files"),
  docs/SCOPE-AND-LEGITIMACY.md, ENHANCEMENTS.md "What this repo does not ship" ("Upscaled derivatives of the game's
  art are game data"). texture-lab's `src/`, `enhanced/`, `build/` were **removed from history on 2026-10-03**
  (commit `b376ee7` "texture-lab: game-derived sample files removed from history; folders ignored"). Keep it so:
  the mock-ups, marker paks, upscaled tiles, re-authored .geo files and repacked `.pak/.pix` are all derived
  from Activision's data and stay in gitignored or lab folders (`i76-upscale-work\`, `game-tex\ADDON`,
  `captures\`).
- Ship the **generator**: scripts that read the owner's own `I76.ZFS` (or extraction) and write into a folder the
  owner chooses, refusing to write into a folder that holds the game executables (the `mw2tool.py` rule), plus the
  model list. The output "pack" is an `ADDON\` folder the owner builds, OpenRA-style (HD-TEXTURES-RESEARCH.md,
  "Distribution").
- Model licences (U2 findings): the dash-class front-runner Manga109Attempt (CC-BY-4.0) x RRDB_PSNR (Apache-2.0)
  is the only redistributable recipe with attribution; Remacri, HDcube2/3, UltraSharpV2, AnimeSharpV2 are
  CC-BY-NC-SA. Weights live in `i76-upscale-work\models` with `LICENSES.md`, never in the repo.
- dgVoodoo is not redistributed by this repo (THIRD-PARTY.md); nothing here changes that. OpenGLide-HD builds are
  LGPL-2.1 and likewise kept out (tools\openglide-hd\README.md).

---

## 6. Corrections this research surfaces

Applied 2026-10-11 after re-verifying against the archive: item 1 (HD-TEXTURES-RESEARCH.md) and item 3 (<re-archive>
`data/FORMATS.md` 7, made explicit; its parser already used 3 bytes). Items 2 and 4 need no edit.

1. HD-TEXTURES-RESEARCH.md "Cockpit/dashboard art = zdash101..601 (day, VQM ...) + zdash106..606 (night, M16)":
   the 01/06 suffix is software/hardware (census 1.2; same as zcbh and the car paks). The texture-lab README's
   zdash101 recipe therefore never reached the `-glide` cockpit; the July "magenta-striped dashboard" proof is
   consistent with the Mac software/OpenGLide path, where VQM loads.
2. texture-lab decodes zdash101 against `t01.act`; U1 found the VQM's codebook is `VPIT.CBK` and the matching
   palette `vpit.act` differs in 617 of 768 bytes (`i76-upscale-work\findings\U1.md`). Irrelevant for the M16 route,
   load-bearing for any VQM edit.
3. FORMATS.md §7 .geo: the per-face flat colour is 3 bytes (RGB), not 4; the rest of the stated layout parses
   1073/1073 LOD-4 members exactly.
4. CLUTTER-AND-MIRROR.md and ENHANCEMENTS.md already say the mirror cannot be sharpened; this doc adds that every
   other cockpit texture is at the ceiling too, so "double the cockpit" is a mesh-and-tiles job, not a file-size
   job.

## 7. Open unknowns (say so rather than guess)

- Whether an ADDON `.pix` can introduce new member names (3.B, first kill criterion).
- Which surface-byte bit selects UV clamp vs wrap for the dash faces (render-mode table 0x4f71b8).
- The actual resolution of the car-skin textures seen in the cockpit (`V1 BO DY`, `V5 FT TP`) and whether the CAR1
  pack already raised them.
- Whether the dash faces are on ZGLIDE's point-sampled or bilinear path (CLUTTER-AND-MIRROR §2 item 1 asked the
  same for the mirror); the conf's forced bilinear makes it moot under dgVoodoo.
- dgVoodoo's behaviour on a non-Glide-2 LOD code (never exercised; ZGLIDE cannot emit one).
- First-hand text of the VOGONS dgVoodoo texture-injection thread (403 today).

## 8. Stages 0 and 1 done offline (2026-10-11)

Built from the pristine archive (`<re-archive>\sandbox-gog\main\app\I76.ZFS`, ADDON ignored); nothing launched, nothing
written to a game folder. Outputs are derived game data under `texture-lab\out\` (gitignored).

**Stage 0, mock-up:** `texture-lab\cockpit_mockup.py` -> `texture-lab\out\cockpit-mockup\index.html`. ZDASH101/102
from `zdash106.pak`, upscaled with U2's dash recipe (Manga109Attempt x RRDB_PSNR 50/50 at 4x, 2x = Lanczos of the 4x;
weights from `i76-upscale-work\models\interp`, recipe redistributable per section 5) plus a classical 2x for
comparison. Three views: the stock start-line capture (`hudsq2-on-a-target.png`) with the visible dash strip
re-rendered at 1x/2x/4x (plane mapping fitted to the capture; 1x reproduction error 5.4/255); the whole panel front-on
at the in-game horizontal magnification with crops (speedo, lamps, radio, small gauges); and the painted faces that do
not change. Findings that change the picture in section 1:
- In the default F1 view only the top ~90 of 1440 rows of the dash are on screen (the top ~12 % of the panel). The
  "dash spans most of the view width" in 1.3 is true, but as a strip; the speedo/tach art and the radio are only seen
  when looking down. Magnification at 1x: ~4.9 px/texel on ZDASH101, ~7.7 on ZDASH102 at 3440 wide.
- ZDASH101 is the speedo/tach cluster art (needles are separate), ZDASH102 the radio, glovebox and small gauges.
- Stored rows are bottom-up: v = 0 is the panel's bottom edge (PP51DASH: y = -0.163 has v = 0; the stock capture shows
  ZDASH102's last rows, the knob tabs, on the top edge). ZGLIDE does not flip.
- 14,473 (ZDASH101) and 8,945 (ZDASH102) texels are index 0xFF; the faces have no colour-key bit (surface 04 01 00),
  so they render black (ZGLIDE 1555 0x0000). The art build treats them as opaque black; `--keep-key` restores them.

**Stage 1, generator:** `texture-lab\cockpit_split.py` (the plan's provisional `tools\upscale\` name became
texture-lab, next to the mock-up). Piranha result, all three modes: PP51DASH 4 faces / 12 vertices -> 11 faces /
23 vertices (+2 collinear corners closing T-junctions); the 5-corner face splits into four (one piece keeps 5
corners), the tiny ZDASH101 corner filler stays whole in one quarter, the sloped ZDASH102 triangle splits in two.
UV is affine over every face to <= 6.4e-4 (about 0.16 texel). The split is at u = v = 256/510, not 0.5, because
ZGLIDE maps u 0..1 to texels 0..255 (s = u x 255). `zdash106.pak` keeps ZDASH101/102 byte-identical and adds
`ZD101Q00..ZD102Q11.M16` (8.3-name, 256x128, flags 0x80). Self-checks, all PASS: both paks and .pix re-decode and
re-encode byte-identically with the <re-archive> data-track parsers; 86 of 87 car-pak members byte-identical (only
PP51DASH.GEO changed); per-face UV and 3D area of the pieces equal the original to < 1e-7; pieces inside their
quadrants and on the face plane; remapped texel coordinates inside 1..255 / 1..127 with `--seam overlap` (default)
and 0..256 / 0..128 with `--seam clamp`; overlap borders equal the neighbour exactly (index builds) and within 9/255
(art build, per-quarter 255-colour palettes, quantisation RMSE 2.0-2.6/255). Render equivalence (split geo +
quarters vs original geo + whole 2x texture, 2400 px wide): replicate mean 0.18/255 (p99 2.1), art mean 2.25/255
(p99 5.8, the quantisation); the residual is spread over all edges from the sub-texel non-affinity, the seam band is
no worse than elsewhere. Tests: `tests\test_cockpit_split.py` (20, synthetic fixtures; the live test re-parses all
1073 LOD-4 .geo members in the 48 `v*g.pak` to exact length, matching the census in 1.2).

Still unknown (the marker boot answers the first three): new member names from an ADDON `.pix`; ZGLIDE's clamp vs
wrap on these faces (`--seam overlap` is safe under both); the v orientation of the label as seen in game (the art
build does not depend on it); TMU behaviour with 8 extra 64 KB tiles.

**For the overnight runner (stage 2):** owner tests 28-30 in docs/OWNER-TEST-LIST.md are the three t01 boots on
`game-tex` (control / marker2x-split / art2x-split) with the build commands and kill criteria. Build from game-tex's
own archive into `texture-lab\out\cockpit-split\gt-*`, copy the four files into `game-tex\ADDON`, remove them after
each run; same conf for all three; record `tex-census`, fps, the start-view and F1 2D-dash captures. The expected
marker picture is on the mock-up page.

## Sources

Repo: `texture-lab/README.md`, `texture-lab/{decode_all,reencode_all,dash_variants2,build_tuner}.py`,
`tools/i76img.py`, `tools/upscale/{README.md,zglide_tmu_patch.py,m16_scale_marker.py,run-tex-scale-test.ps1}`,
`tools/openglide-hd/README.md`, `tools/menu-hd/build_hd.py`, `music-fix/strlkproxy.c` (mirror ~6145, aspect ~6159,
HUD squeeze ~6167-6230, texture census ~4807), `music-fix/README.md` (`I76_HUD_SQUEEZE` row),
`docs/HD-TEXTURES-RESEARCH.md`, `docs/ENHANCEMENTS.md`, `docs/records/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md`
§4-5, `docs/records/GRAPHICS-ENHANCEMENT.md` (R4), `docs/records/MENU-HD-ART.md`, `THIRD-PARTY.md`,
`docs/SCOPE-AND-LEGITIMACY.md`, `dgVoodoo.windows.conf`.
Lab (`<lab>\docs`): `TEXTURE-DELIVERY.md`, `TEXTURE-AND-OBJECT-LOD.md`, `CLUTTER-AND-MIRROR.md`,
`WIDESCREEN-2D.md`, `OPENGLIDE-HD-WINDOWS-2026-10-03.md`; `autotest\proxy-run.ps1`.
RE (`<re-archive>`): `subsystems/renderer.md` (K1, K1e, K1e4, K1h, L1e), `subsystems/camera.md` "HUD
drawing", `ARCHITECTURE.md` §8, `data/FORMATS.md` §6-7, `data/notes/vdf.md` §5-6,
`ghidra/export/functions/0045b450.c`.
Sprint data (`<upscale-work>`): `findings/{U1,U2,U3,U5,CAR1,TERRAIN1}.md`, `extract\` (census).
Web (2026-10-10): Glide 2 header https://raw.githubusercontent.com/voyageur/openglide/master/sdk2_glide.h ;
dgVoodoo General readme http://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/ (no texture replacement feature; "Options
on the General tab affects all wrapped APIs"); Glide readme 404; VOGONS t=66553 403; conf option list quoted at
https://www.vogons.org/viewtopic.php?p=892835 ; no I'76 texture pack found (searches via gamepressure.com, vogons.org,
moddb.com results).
