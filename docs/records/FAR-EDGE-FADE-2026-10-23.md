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
picture at its own colour (`runs61023-101413-fogv70-hill`, `zoom-fogv70.png`). The 8-bit strip's indices belong to the
8-bit build's palette; when I76_MIRROR_PAL has found the pair, mirror-pal's 8-bit -> hardware map is applied (on T05 the two
palettes differ by 34 in all, so the colour is the same either way). `I76_GLIDE_FOG=<start>,rrggbb` overrides.

## 4. Delivered (exp-polish2)

- `PLAY-OWNER-2300-HAZE.bat` + `presets\OWNER-2300-HAZE.psd1`: OWNER-2300-ALL (as corrected 09:40: the driver's four keys, the
  mirror lane's keys, I76_JUMP_NOSE) + `I76_HAZE=0.85` + `I76_EDGE_FADE=1`.
- `PLAY-OWNER-2300-FOG.bat` + `presets\OWNER-2300-FOG.psd1`: the same + `I76_GLIDE_FOG=0.85,hzd`.
- Proxy f2856def (repo 9496235, built from a clean worktree of main) installed into exp-polish2 by `toolsar-edgee-install.ps1`
  once no game ran, the previous DLL kept as `STRLKUP.DLL.<md5>` (the install line is in the lane report).
- Pictures for the owner: `toolsar-edgeuns61023-094056-fogred50-hill\s04-t16.png` (the fog mechanism, red from 0.5),
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
