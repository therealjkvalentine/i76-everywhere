# Far-edge fade: haze, Glide fog and the level boundary (far-edge lane, 2026-10-23)

Owner's ask (2026-10-23, verbatim): "build out both haze and glide fog for me to test, and make sure it's pretty far out, not
close, so it works pretty close to the limit of what is rendered but transitions a little more smoothly from the flat horizon
textures. since the game takes place in the desert and we are coming down mountains sometimes there isn't really a plausible
limit to view distance besides heat shimmer." And: "for the draw distance there is something to be thought about with the
boundaries of the levels, which sweep up so you can't drive on forever, but kind of make that obvious/unrealistic at a far
render distance, so we may consider treating those boundaries in a special way that fades them to the horizon better."

Base: the owner's OWNER-2300-ALL (far clip / roads / bushes 2300 m, LOD 24, tick 41.667; exp-polish2, proxy 9b7482b8 = repo
473c16a). Code: `music-fix/faredge.c` (repo 9615a0c), included before `terrainmorph.c`; two Gold sites, chained where another
switch already owns them. Lab copy: `exp-faredge` (a copy of exp-polish2); runner `tools\far-edge\fe-run.ps1`; runs under
`tools\far-edge\runs\<stamp>-<tag>\` (PNGs, env.txt, boot.txt, the proxy log excerpt, summary.txt); `results.txt` one line per boot.

## 1. What the stock far edge is

- The terrain's per-vertex shade (0x490f08..0x490f6d, 0x490fb0) is s = max(0, L.y - Sx L.x - Sz L.z) x g(z) + A with the depth
  term g(z) = clamp(0.7496 + 0.000417 z, 0.75, 1): the game's own "haze" BRIGHTENS the far ground, and saturates at 600 m (the
  stock far clip). Past 600 m the ground is lit by slope alone, so at 2300 m the edge is a hard line of slope-lit ground
  against the horizon strips (renderer.md "Terrain", "Lighting tables").
- The shade is a scalar on palette colours: no tint anywhere (renderer.md: "Nothing in the table selects a fog colour"). In
  hardware (ZGLIDE) the vertex shade picks a grey from the 64-entry luma table (index 16 + round(31 s): 32 real levels) that
  modulates the texel. So a shade-side haze can at most reach the unmodulated texel (row 0); a colour fade to the sky needs
  the Glide fog.
- The horizon strips (0x4016e0, 16 quads from the texture pairs at 0x504850, count 0x503034) are drawn through the same
  hardware polygon path (0x4260d0) before the depth-bucket flush, with their own camera (far 100000); the cockpit mesh,
  instruments, brackets and mask come after the flush. The rear mirror is a software render into a 256x64 bitmap (no Glide
  calls of its own).
- ZGLIDE.DLL (05c1dde4, the Gold driver) imports grFogMode and grFogColorValue (its own fog is armed only by a device flag bit
  2 at FirstDevice, which I'76 does not set; a SetState case 0x200000 toggles GR_FOG_WITH_ITERATED_ALPHA) and NOT grFogTable.
  dgVoodoo's glide2x.dll exports the whole Glide 2.x fog API, so the proxy resolves grFogMode / grFogColorValue / grFogTable /
  guFogTableIndexToW with GetProcAddress once ZGLIDE is up (no IAT patch). ZGLIDE opens the SST with cformat 0 (ARGB), so the
  fog colour is 0x00RRGGBB.

## 2. The switches (all off by default, Gold only; Nitro logs "not applied")

| switch | what it does | where |
|---|---|---|
| `I76_HAZE=<start>[,<strength>]` (default start 0.85, strength 1) | after the exe's shade loop and the morph's shade blend, every terrain vertex with view z > start x far gets s += (target - s) x strength x smoothstep((z - z0) / (far - z0)); target `I76_HAZE_TARGET` (default 1.0 = the brightest row). Both passes (main at its far clip, mirror at I76_MIRROR_FAR; `I76_HAZE_MIRROR=0` keeps the mirror stock). | the two leaf-emit calls 0x490f9b / 0x490f82 when stock; with I76_TERRAIN_MORPH on, chained inside `tm_emit_wrap` (one line in terrainmorph.c) |
| `I76_GLIDE_FOG=<start>[,hzd or rrggbb]` (default 0.85, hzd) | a 64-entry Glide fog table clear to start x far, smoothstep to full at the far clip (entries at guFogTableIndexToW(i) metres), colour = the mean of the bottom 4 rows of every horizon strip bitmap through the context palette 0x5dcfa8 (re-read every 2 s: mission changes) or a fixed hex; GR_FOG_WITH_TABLE set just before the hardware scene's depth-bucket flush and GR_FOG_DISABLE right after it. `I76_GLIDE_FOG_WM` = metres per ZGLIDE w unit (default 1). | the flush call 0x48fac0(cam, 1) at 0x40216d, chained after road-pool's wrap (st_call_site) |
| `I76_EDGE_FADE=1` or `<pull 0.1..0.9>` (1 = 0.4) | needs I76_HAZE: a vertex within 128 samples (640 m) of a VOID tile has its haze start pulled in, z0 = start x far x (1 - pull x (1 - d / 128)), continuous in d. Haze path only (the fog table is by w). | reads the tile table 0x644380 (rebuilt when its content changes, checked every 2 s) |
| `I76_FAR_EDGE_LOG=1` | lab: every 300 main passes the band's vertex count and distinct grey levels round(31 s); with the fog, a grDrawTriangle hook (IAT of ZGLIDE, chained after any census hook) logging w = 1 / oow inside and outside the flush bracket | |

### The level boundary, what was found

Terrain init 0x493080 fills all 16384 entries of the tile pointer table 0x644380 (128 x 128 tiles of 128 x 128 samples, 5 m)
with the one static tile 0x59c588, then the mission's ZMAP (80 x 80 zone indices, -1 = none, centred with the 24-tile border)
replaces the authored ones. The height query 0x493160 reads whatever tile the sample falls in, so outside the authored zones the
ground is the static tile (flat). The "sweeping-up" boundary is therefore AUTHORED in the outermost .ter tiles, not synthesised:
there is no height ramp to detect by rule. What can be identified cheaply is the void: a tile pointer equal to 0x59c588. The edge
fade uses the distance from the vertex to the nearest void tile (its tile's 8 neighbours, rectangle distance; exact within 640 m,
none beyond), so the last 640 m of authored ground before the void fade earlier than the open desert. Whether that band matches
the authored walls is for the owner's eye (T05's walls are wider than one tile in places).

## 3. Measurements (exp-faredge, T05, hardware path = ZGLIDE over dgVoodoo.wide.conf, 120 Hz cap)

### 3.1 The probe boot (mission start, canyon; proxy dc90909e, run `20261023-090833-probe`)

- **ZGLIDE's w is metres.** Inside the flush bracket w = 1.0 .. 2300.0 (the near plane .. the far clip, 1.77 M triangles per
  300 frames, 150-180 k past 0.9 x far); outside the bracket w = 0.1 .. 5999.6 (the cockpit at 0.1-3 m, the sky dome at its
  6000 m radius, 25-56 k triangles). So the fog table in metres is right, and the bracket keeps the sky dome and the cockpit out
  of the fog without any per-triangle work.
- **Fog table resolution.** With guFogTableIndexToW (dgVoodoo exports it) the 64 entries fall at 1024 / 1170 / 1365 / 1638 /
  2048 / 2341 m in this range: a 0.85 x 2300 ramp has two table points (2048 m = 46/255, 2341 m = 255) and the hardware
  interpolates linearly between them. Fine for a soft band; the start is coarse-grained by the table, not by the switch.
- **Haze quantisation.** Per 300 main passes 3.7 k vertices lay in the band and took 21-31 distinct values of round(31 s)
  (of the 32 real luma rows): the whole stock ladder is in use, no extra banding beyond the game's own 32 rows.
- **The level map.** T05 has 48 authored tiles of 16384 (6 x 8 tiles = 3.8 x 5.1 km); 32 touch the void, 16 are one ring in,
  none is "open". A 640 m edge band therefore covered two thirds of the level; the default became 320 m
  (`I76_EDGE_FADE=<pull>,<band m>`).
- The first two horizon-colour readers read the wrong struct (black fog in the probe boot, then the c0b0a0 fallback): the strip
  records at 0x504850 are TEXTURE records (DWORD w, DWORD h | flags, texels at +8; 0x44a740's copy size rule), fixed in b0e699f.

### 3.2 What the far edge looks like from the hill top (7972, 44035, facing west, eye 100 m up; `runs\*-hill\s04-t16.png`)

From the hill the plain's far rim at 2300 m sits about 20 px above the horizon-strip line in a 1440-row frame: the last 15 % of
the far clip (1955-2300 m) is a THIN band at the owner's "far out" setting, by geometry (atan(100/1955) - atan(100/2300) = 0.44 deg
of a 121.7 deg wide view). The mechanisms are proven with exaggerated settings (row-brightness profile of the centre columns,
`runs\zoom-*.png`):

| boot | what the centre columns show at the far edge |
|---|---|
| `094056-fogred50` (fog from 0.5 x far, colour ff0000) | the plain from 1150 m to the rim fogged red, saturating at the rim; the sky, the horizon strips, the cockpit, the HUD and the mirror untouched (`s04-t16.png`) |
| `094144-fogred85` (fog from 0.85, red) | a red band a few rows tall at the rim |
| `094232-haze50` (haze from 0.5) | the far ground lifted by 10-19 brightness units over 70 rows (washed out toward the rim, `zoom-haze50.png`) |
| `094319-hazedark85` (haze from 0.85 to target 0) | the rim's last 20 rows darkened by 8-15 units: the 0.85 band is real and about 20 px tall from the hill |
| `093301-haze` / `093349-fog` (the delivered settings, horizon colour) | within the base-vs-base frame noise (clouds move): visible only at the rim, as asked |

So at 0.85 the effect is deliberately near the limit of what is drawn; `I76_HAZE=0.7` / `I76_GLIDE_FOG=0.7` are the knobs if
the owner wants a wider transition (both take the start fraction; 0.5 .. 0.98).

### 3.3 fps cost (hill top, car held, render fps from I76_FPS_LOG=2: mean of the windows after the first 6 s; 120 Hz cap)

Two sets, because the OWNER-2300-* presets were missing the daily driver's I76_TERRAIN_TEX 8 / OBJECT_LOD 8 / SHADOW_DIST 4 /
ROAD_TEX 8 until 09:40 (main's correction); the second set has them. Other lanes were booting games between my batches, so the
spread of the second set is wider (the two fog boots differ by 5.5 fps with the same keys).

| set | base | haze + edge fade | Glide fog | haze only |
|---|---|---|---|---|
| preset without the four (09:32, proxy b2b17f19) | 107.2, 106.1 | 107.8, 107.7 | 107.5, 107.9 | 107.8 |
| corrected preset (09:44, proxy 81b761c8) | 108.1, 107.9 | 101.5, 104.9 | 107.9, 102.4 | 108.2 |

Work per frame 9.3 ms in every row except the two low haze rows (9.9 / 9.6 ms) and the low fog row (9.9 ms). Reading: the
haze and the fog cost nothing measurable in the clean first set (n 2 each, spread <= 1.1 fps, all within the base pair); in the
second set the dips are not paired with a mechanism (haze-only at 108.2 beats base, one fog boot at 107.9 and the other at
102.4) and read as console contention. The per-vertex work is a compare per terrain vertex plus a smoothstep for the ~1-4 k
vertices in the band; the fog is three Glide state calls per frame.

### 3.4 The horizon colour (four readers, one right)

The strip records at 0x504850 are texture records (DWORD w, DWORD h | flags, texels at +8), 128 x 128, stored BOTTOM-UP: rows
84..127 are black (the transparent sky above the mesa line, highest non-black row 83 on T05) and row 0 is the picture's base,
where the far rim of the ground is drawn against it. The earlier readers took a bitmap header (garbage: black fog, then the
c0b0a0 fallback), the black top (010101), the dark peaks (110c07 / 261a0f). The delivered reader (9496235) averages rows 0..7
through the context palette: T05 reads **483620**. On screen the strips above the rim read 6d5542 (base boot, rows 815-826 of the
hill frame): the same hue, lifted by the display's gamma ramp, which lifts the fog colour the same way - with the fog at 0.7 the
rim's rows read 735b43 / 705a44 / 6f5b45 against the picture's 6d5542 (base: 7e664f .. 8b7761), i.e. the rim now meets the
picture at its own colour (`runs\20261023-101413-fogv70-hill`, `zoom-fogv70.png`). The 8-bit strip's indices belong to the
8-bit build's palette; when I76_MIRROR_PAL has found the pair, mirror-pal's 8-bit -> hardware map is applied (on T05 the two
palettes differ by 34 in all, so the colour is the same either way). `I76_GLIDE_FOG=<start>,rrggbb` overrides.

## 4. Delivered (exp-polish2)

- `PLAY-OWNER-2300-HAZE.bat` + `presets\OWNER-2300-HAZE.psd1`: OWNER-2300-ALL (as corrected 09:40: the driver's four keys, the
  mirror lane's keys, I76_JUMP_NOSE) + `I76_HAZE=0.85` + `I76_EDGE_FADE=1`.
- `PLAY-OWNER-2300-FOG.bat` + `presets\OWNER-2300-FOG.psd1`: the same + `I76_GLIDE_FOG=0.85,hzd`.
- Proxy f2856def (repo 9496235, built from a clean worktree of main) installed into exp-polish2 by `tools\far-edge\fe-install.ps1`
  once no game ran, the previous DLL kept as `STRLKUP.DLL.<md5>` (the install line is in the lane report).
- Pictures for the owner: `tools\far-edge\runs\20261023-094056-fogred50-hill\s04-t16.png` (the fog mechanism, red from 0.5),
  `20261023-094232-haze50-hill` (haze from 0.5), `20261023-101325-fogv-hill` / `20261023-101413-fogv70-hill` (the horizon colour at
  0.85 / 0.7), `20261023-094412-base-hill` (the base), and the `zoom-*.png` crops of the far edge.

## 5. What is left

- **Nitro**: no sites; `apply_far_edge` logs "not applied" on Nitro. The emit calls, the flush call and the data globals need the
  Nitro map (sites_nitro.h) before the Mac pass.
- **Boundary identification**: only the void is identifiable by rule (the tile table); the walls are authored. The edge fade
  (haze path only) acts within 320 m of the void. A per-vertex fog needs GR_FOG_WITH_ITERATED_ALPHA with the vertex alpha
  under our control: ZGLIDE fills the GrVertex alpha from a record byte (not traced), which would give the fog path the same
  per-vertex control as the haze - the next step if the owner wants the walls fogged rather than brightened.
- **The band is thin at 0.85** from a 100 m eye (about 20 rows of 1440); the start fraction is the knob. The fog table is
  quantised to the Glide w ladder (1638 / 2048 / 2341 m here), so starts between those points differ only in the table's
  interpolation weights.
- **fps**: no measurable cost in the clean set; the corrected-preset set ran beside other lanes' boots and should be re-taken on
  a quiet console if a number is needed for the promotion sheet.

## 6. Atmosphere variant (owner 2026-10-23: "let's try the fade band as atmosphere rather than edge treatment"; fog from 0.7 liked)

Fog from 0.5 and 0.35 of the far clip in the horizon colour, two vantage points, corrected preset load, proxy 9496235+ (lab
`fe-batch4.ps1`, 10 boots 11:04-11:12, a quiet console held for the batch):

| route | base | fog 0.5 | fog 0.35 |
|---|---|---|---|
| valley road (mission start, driving) | 117.7, 119.7 | 119.0, 119.1 | 119.8, 119.7 |
| hill top (held) | 108.1, 107.9 (09:44) | 107.3, 108.0 | 108.7, 109.2 |

No cost (n 2 each; the spread of the base pairs covers every fog row). Captures: `runs\20261023-110831-base-start`,
`110919-fog50-start`, `111007-fog35-start`, `111055-fog50-hill`, `111142-fog35-hill` (`s04-t16.png`, 3440x1440).

What they show at ground level (the owner's view): the fog lives at the far end of the canyon, where the road meets the far
ridge. At 0.5 (from 1150 m) the far end is gently muted; at 0.35 (from 805 m) the mid-distance slopes on both sides already take
the horizon colour, which on T05 is the mesa picture's dark base (483620) - a dusk tint at midday. From the hill top 0.5 fogs the
plain's far half, 0.35 most of it.

**Delivered: `PLAY-OWNER-2300-ATMOS.bat` + `presets\OWNER-2300-ATMOS.psd1` at `I76_GLIDE_FOG=0.5,hzd`** - the whole far half
fades, the near ground and the mid-distance slopes keep their own colour, and it is the same colour the owner liked at 0.7, only
starting nearer. 0.35 is one key away if he wants more; for a midday desert the colour is the thing to tune next
(`I76_GLIDE_FOG=0.5,rrggbb`: a lighter warm grey such as 9a8a78 would read as heat haze rather than dusk; the strips' base rows
are the colour the far rim is drawn against, which is right at the edge and dark for a wide band).

## 8. Is the fog itself banded? (owner: "textures in ATMOS ... are still coarse / distracting brightness adjustments")

- The Glide 2.x fog table has 64 entries at w = guFogTableIndexToW(i) = 2^(3 + i/4) / (8 - i % 4) metres (dgVoodoo exports the
  function; the proxy uses it): 1024 / 1170 / 1365 / 1638 / 2048 / 2341 m in the band of interest. A 0.35 band (805-2300 m) has
  six entries on the ramp, a 0.5 band four, a 0.75 band two (2048 m, 2341 m) - the proxy fills every one of them (smoothstep of
  the entry's w), so the ramp is already the finest the table allows; the hardware (and dgVoodoo's emulation) interpolates
  linearly in 1/w between entries, PER PIXEL (table fog, not per vertex: the vertex carries only oow).
- Profile (luma along the road centre, columns 1690-1730, rows 880-996 = far to near, 4-row means) from the valley captures
  `110831-base-start` / `110919-fog50-start` / `111007-fog35-start`: fog / base ratios 0.97-1.02 at every row, no step; the
  road's own texture steps (rows 924-936, 952-964) are identical in all three. At ground level the fog band covers only the last
  rows below the horizon, so a stair cannot come from it; the brightness steps the owner sees in ATMOS are the terrain's own
  shade rows and texture levels (the pops lane's road profile, `tools\terrain-pops`), which the fog overlays but does not
  create. A uniform-luma table (delta per entry equal) would not change what is on screen between entries - the interpolation
  is linear in 1/w either way - so no "after" table was built.

## 9. Clutter alpha fade-in - NOT built (the owner then withdrew it: "just draw them further out"; the density sweep is s.11), the path for the record

What it needs, from this lane's findings: (a) a per-record alpha reaching ZGLIDE - the exe's projected vertex record carries a
byte ZGLIDE converts into GrVertex.a (`mov dl, [esi + 0x2f]` in Render, not yet traced to the exe's writer); (b) the bushes'
op switched from ZGLIDE's keyed opaque state to blend SRC_ALPHA / ONE_MINUS_SRC_ALPHA with alpha combine SCALE_OTHER(TEXTURE)
x LOCAL(ITERATED) (ZGLIDE's own translucent keyed op at 0x10002205 / 0x10002212 uses exactly that, so the key survives: the
keyed texels' alpha is 0); (c) the age: the clutter queue 0x45c380 instances a template per cell each frame with no identity,
so the proxy would key a table by (template, cell, index) and record the frame of admission (the (300 / d)^2 rule in
I76_CLUTTER_FADE admits deterministically, so "admitted now" = "in the list this frame and not the previous"), alpha =
min(1, frames since admission / N). (b) and (c) are bounded; (a) is the open piece (the writer of the record's alpha byte, or
setting it in the grDrawTriangle hook from a per-record side table matched by screen position). Not started: the owner's
same-day verdict on the transparent fade (s.7) took the alpha path off the shipping list for now.

## 7. Fade to transparent (I76_GLIDE_FOG_ALPHA=1) - built, lab only, NOT shipped

Assessment (ZGLIDE 05c1dde4, glide2x imports read with capstone): per render op ZGLIDE sets grColorCombine / grAlphaCombine /
grAlphaBlendFunction; its opaque ops request blend ONE / ZERO (0x10001fa0, 0x1000200b, 0x10002399, 0x100024fa), its
translucent ops SRC_ALPHA / ONE_MINUS_SRC_ALPHA with the texture alpha or texture x iterated alpha (0x10002205 / 0x10002212);
depth is a W-buffer (mode 2, LEQUAL, writes on). The sky dome (0x405200) and the horizon strips (0x4016e0) are drawn BEFORE
the depth-bucket flush, so a blended far ground has them behind it; the flush draws far to near, so nearer opaque ground covers.
The vertex alpha is not supplied by the exe for terrain in any usable way, so the proxy writes it in its grDrawTriangle hook
(GrVertex +28 = 255 x (1 - smoothstep(w))) while the blend state is overridden by IAT hooks on ZGLIDE's grAlphaBlendFunction /
grAlphaCombine (an opaque request becomes SRC_ALPHA / ONE_MINUS_SRC_ALPHA; translucent requests pass through).

Boots (`fe-batch5/6/8`, valley road + hill top, band from 0.5 x far):
- `111757-alpha50-start` .. `112109-alpha50-start` (first form, alpha combine LOCAL ITERATED): the far plain dissolves into the
  horizon picture and the sky behind it (`112109-alpha50-start\s04-t16.png`, `111846-alpha50-hill`), fps 116.0 / 116.8 on the
  road vs base 117.7 / 119.7, hill 100.7 (n 1) vs 108: alpha blending over the far half of the terrain is not free. BUT the
  bushes drew as black squares: the clutter billboards are keyed through the TEXTURE alpha, and the forced LOCAL ITERATED
  combine replaced it (owner saw this live).
- `112856-alphak50-start` .. (second form, override off while grChromakeyMode is on): unchanged - ZGLIDE does not toggle the
  chroma mode per record for the bushes; their key is the texture alpha.
- third form (8cb3da2+): alpha combine = SCALE_OTHER(TEXTURE) x LOCAL(ITERATED), ZGLIDE's own keyed translucent op: keyed
  texels keep alpha 0, 565 terrain has no alpha channel and takes the vertex alpha. Verification boot `fe-batch8` (result in s.12).

Verdict: not shipped. The owner, looking at the fades on the console: "we probably never want it to fade below the horizon
line, so there's no blue" - a transparent far ground shows the sky dome's blue where the dome sits behind it, which is exactly
what the colour fog avoids (its target IS the horizon strip colour). A transparent fade "toward the horizon colour" is the
colour fog. The switch stays as a lab instrument (the keyed-texture lesson is in the code for any future per-record alpha work).

## 10. Owner's band ruling (console, 2026-10-23): "the fade is too broad now ... maybe half as long"

- FOG: 0.85 was too thin, 0.7 liked, halved -> **0.75** (clear to 1725 m, full at 2300 m).
- ATMOS: shipped at 0.5; the halved band of the atmosphere candidates: 0.5 -> 0.75 would equal FOG, so ATMOS takes the halved
  0.35 band -> **0.675** (clear to 1550 m, full at 2300 m). Both numbers are in the presets' comments.
- Both in the horizon strip colour only (483620 on T05 through the context palette), never the sky: the colour fog by
  construction.
- Captures (hill top, `fe-batch7`): `runs\*-fog75-hill`, `runs\*-fog675-hill` (`s04-t16.png`).

## 12. Transparent-fade verification with the texture x iterated combine (3d89698, `fe-batch8`)

`runs\20261023-114128-alphat50-start\s04-t16.png` (valley road, bushes in the near field; crop `zoom-alphat50-bushes.png`):
the bushes are keyed sprites again (no black squares), the far ground still blends, 119.7 fps (base 117.7 / 119.7). So the
lab switch is clean; it stays unshipped for the owner's "no blue" reason (s.7). The lesson for any per-record alpha work on
this driver: keyed textures carry their key in the TEXTURE alpha, so an alpha combine must keep SCALE_OTHER(TEXTURE).

## 11. Clutter density sweep (owner: "just draw them further out"; preset only, `fe-batch9`, valley road, driving, corrected load)

I76_CLUTTER_DIST stays 2300; I76_CLUTTER_FADE = full density to N m, then (N / d)^2 per (template, cell) pair; "off" = the
key unset (full density to the far clip; the code also treats a value >= I76_CLUTTER_DIST as off). Render fps, n 2:

| I76_CLUTTER_FADE | fps | work ms | vs 300 |
|---|---|---|---|
| 300 (current) | 119.1, 119.9 | 8.40, 8.34 | - |
| 600 | 84.9, 85.9 | 11.80, 11.64 | -29 % |
| 1200 | 48.5, 48.6 | 20.6 | -59 % |
| off (full density to 2300 m) | 28.6, 28.6 | 35.0 | -76 % |

No pool refusals logged in any boot (record pool 11562 KB, refusal line absent). Even 600 costs ten times the ~3 % budget, so
**300 stays** in OWNER-2300-ALL (the per-instance engine path - two terrain lookups, transform, frustum, mesh transform and
lighting, one draw record per face - runs for every kept bush; density to 600 m quadruples the kept count). Captures:
`runs\20261023-120455-cf300-start`, `120233-cf600-start`, `120320-cf1200-start`, `120408-cfoff-start` (`s04-t16.png`); the
bushes the owner sees popping at ~300 m are the (300 / d)^2 admissions, and pushing that line out is a cost question, not a
switch question - sparseness (a lower density shape) is the separate decision he named.

## 13. Final state (2026-10-23 12:06)

- exp-polish2: proxy **ed0c246f** (repo 3d89698, clean worktree of main; previous bc2b0b9b and f2856def kept beside), launchers
  `PLAY-OWNER-2300-HAZE.bat` (I76_HAZE 0.85 + I76_EDGE_FADE 1), `PLAY-OWNER-2300-FOG.bat` (I76_GLIDE_FOG 0.75,hzd),
  `PLAY-OWNER-2300-ATMOS.bat` (I76_GLIDE_FOG 0.675,hzd), presets regenerated from the corrected OWNER-2300-ALL (I76_CLUTTER_FADE
  300 unchanged). No transparent launcher (s.7); I76_GLIDE_FOG_ALPHA stays a lab switch.
- Lab: `tools\far-edge\` (fe-run, fe-batch1-9, fe-install, results.txt, runs\<stamp>-<tag>-<route>\), copy `exp-faredge`,
  build worktree `builds\faredge-20261023\wt`.
