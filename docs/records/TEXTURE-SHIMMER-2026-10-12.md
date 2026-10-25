# Texture shimmer on the lab copy: is the supersampling and MSAA really on? (2026-10-12, static)

Owner report (lab twin `<lab>\game-dd-20261003`, best-wide preset, dgVoodoo 2.87.3): "we are seeing some
shimmering on textures; are we sure we're still double-rendering it and using MSAA?"

Everything here was read from files on disk: confs, the proxy log, gate run folders and their captures, the 2026-10-03
capture matrix. Nothing was launched. The live checks are in section 4 and owner test 31.

## Short answer

1. **MSAA 4x: yes. The 5160x2160 supersampling: no.** And it was never "double" rendering on the wide preset. The
   4:3 sandbox measured 2x (3840x2880) on 2026-10-03. The widescreen conf asks for 1.5x per axis (5160x2160), and in
   the owner's windowed setup dgVoodoo does not use even that. Every gate capture of the twin (4 runs, 2026-10-08..11,
   the same conf md5 `ac0ecdeb` that PLAY.bat installs) has edges with exactly 4 coverage levels. That is the signature
   of 4 samples per presented pixel: 4x MSAA rendered at the window's own 3440x1440. A real 1.5x + 4x target shows all
   eight levels (calibrated on the 4:3 matrix, section 1). The likely mechanism: the wide conf has
   `FullScreenMode = false` (borderless window), and in windowed mode dgVoodoo renders at the window size. The 4:3
   sandbox that did supersample uses `FullScreenMode = true` + `FullscreenAttributes = fake`.
2. **The shimmer comes from three things together.** (a) Every texture is a single level with no mipmaps (proxy log:
   447/447 downloads `lod n..n`, format 11 = ARGB1555), so bilinear filtering aliases once a texel gets smaller than a
   pixel. MSAA does nothing inside a polygon. (b) `I76_TERRAIN_TEX = 8` stretches the 256 px terrain tile out to 400 m.
   At the 1440 lines actually rendered, that is 2.7 texels per pixel at the boundary even head-on, and far more at the
   grazing angles of a downhill road. (c) Item 1: there is no supersampling to average it away.
   The fixes, best first: turn the supersampling on for real (fake fullscreen, then 2x = 6880x2880). Bring
   TERRAIN_TEX down to about 4. Real mipmaps would need a ZGLIDE one-byte flip through the proxy (an experiment).
   dgVoodoo 2.87.3 has no Glide anisotropic, LOD-bias or mip-autogen key, and the NVIDIA overrides cannot act on
   textures that have no mipmaps.

## 1. Evidence: what is in force

### Which conf dgVoodoo reads

| check | result |
|---|---|
| twin `dgVoodoo.conf` vs `dgVoodoo.wide.conf` | identical, md5 `ac0ecdeb` (PLAY.bat and every TEST bat copy it in) |
| global `%APPDATA%\dgVoodoo\dgVoodoo.conf` | **present**: 2020-11-27, md5 `5d3906a0`, `Version 0x270`. If it were the one in effect: `FullScreenMode true`, `ScalingMode stretched_ar`, `[Glide] VideoCard voodoo_rush`, `Resolution h:1920, v:1440`, `Antialiasing appdriven` (= off), `MemorySizeOfTMU 2048`, `3DfxWatermark true`, `[DirectX] dgVoodooWatermark true` |
| gate row 1a (client rect, global hidden) | PASS in all four real twin gates (20261008-203527, -204529, 20261011-195049, -225529): `client 3440x1440 -> ACCEPTED`, conf md5 `AC0ECDEB`. The local file is parsed (a rejected file falls back to a 640x480 window), so with the global file present dgVoodoo still takes the folder's file first |
| gate row 1b (3DfxWatermark flipped for one boot) | **never positive.** None of the nine `1-conf-watermark.png` captures (2026-10-03..11, sandbox and twin) shows a 3dfx logo in any corner, including the runs where the conf was independently proven to load. The row is marked INFO "by eye" and nobody looked. The capture is taken about 14 s into the mission. 2.87.3 has a `WatermarkDisplayDuration` key (it is in the CPL's key table), so the logo is probably shown only briefly. Either way the row proves nothing. Replace it with a persistent sentinel (section 4) |
| global conf as the reason for the shimmer | ruled out: the global file would give a 4:3 `stretched_ar` picture with pillarbox bars, not the full-width Hor+ picture in the captures, and no AA (the captures have AA) |

So the folder conf is the one in effect. The question is what its values do.

### What the presented frame contains

`<lab>\tools\graphics\edge-aa-probe.ps1` (new, offline) walks one straight high-contrast edge per row. It
reports how many intermediate pixels the edge has and which coverage fractions they take. Calibration on the
2026-10-03 4:3 matrix (`captures\graphics\try`, the A-pillar against the sky, `-X 820 -Y 600 -W 180 -H 160`, the conf
proven in effect there):

| capture (target, MSAA) | hard rows | coverage levels seen | samples / presented px |
|---|---|---|---|
| `02-1x-noaa` (1920x1440, off) | 100 % | none | 1 |
| `06-2x-noaa` (3840x2880, off) | 34 % | 2/8, 4/8, 6/8 only | 4 |
| `05-1.5x-msaa4` (2880x2160, 4x) | 4 % | all eighths | 9 shaded, ~36 at edges |
| `01-current-2x-msaa4` (3840x2880, 4x) | 9 % | all eighths | 16 at edges |
| `04-1x-msaa8` / `10-3x-noaa` | 1 % / 6 % | all eighths | 8 / 9 |

Twin gate captures (best-wide, `1-conf-watermark.png`, left A-pillar, default region), n = 4 runs, all identical
(the spawn frame is deterministic):

```
image 3440x1440, region (430,520) 130x160, edge rows 155
rows with a hard step (no intermediate pixel): 62 (40%)
intermediate pixels per row: 0.60
coverage histogram (eighths 1..7): 1/8:0  2/8:33  3/8:0  4/8:29  5/8:0  6/8:31  7/8:0
verdict: 4 SAMPLES per presented pixel (quarter steps): 4x MSAA at the presented size, or 2x2 supersampling without MSAA
```

The conf asks for 4x MSAA and no 2x, so the reading is **4x MSAA at 3440x1440, with no supersampling**. A 5160x2160
target with 4x MSAA would have produced the all-eighths pattern of `05-1.5x-msaa4`. Nor is it 5160x2160 without
MSAA: a bilinear downscale at 1.5x mixes pixels with 3/4 and 1/4 weights, which gives levels between the quarters.

Why the window size: the 4:3 sandbox conf that measured 2x (`game\dgVoodoo.conf`) has `FullScreenMode = true` with
`FullscreenAttributes = fake`. The wide conf (and the 16x10 conf it grew from, `4608x2880`) has
`FullScreenMode = false`, `WindowedAttributes = borderless`. The lab's own note on the rejected conf
(`docs\DGVOODOO-CONF-REJECTED.md`) already says "FullScreenMode = false makes the Glide resolution the WINDOW size".
A 5160x2160 window does not fit a 1440-line desktop, and the measured client is 3440x1440: the same 2.389 shape scaled
to fit. That is consistent with dgVoodoo fitting the window first and rendering at the window size. The aspect is
right either way, so nothing on screen gave it away. **Not yet proven live**: section 4 settles it in two boots.

What this means for earlier claims: the wide preset's "1.5x supersampling, 11.1 Mpx, same sample count as 3840x2880"
(lab `docs\WIDESCREEN-FEASIBILITY.md`), and the 16x10 driver conf's "2x of the presented frame", describe files whose
resolution key did not take effect in windowed mode. They are a request, not a measurement (the same pattern as
`docs\DGVOODOO-CONF-REJECTED.md`).

### The proxy log (twin `mciproxy.log`, 2026-10-12)

- `glide-refresh: grSstWinOpen(res 7, ...)`: the game opens 640x480 (res 7) as always. dgVoodoo's forced resolution
  never reaches the engine, so the proxy cannot see the render-target size. No log line can answer item 1.
- `tex-census`: resident 2.6 MB of the 8 MB TMU, 0 flushes, 0 no-slot, about 1825 downloads per 600 swaps.
- `flash-probe: download ...`: all 447 logged downloads are `lod 0..0` (299), `lod 2..2` (147) or `lod 1..1` (1), all
  `format 11` (ARGB1555). One level per texture, never a chain, as the static read of ZGLIDE predicted
  (lab `docs\TEXTURE-AND-OBJECT-LOD.md` s.1: `FirstDevice` calls `grTexMipMapMode(GR_MIPMAP_DISABLE)`, `smallLod =
  largeLod`).
- dgVoodoo's own log: none. 2.87.3 release builds do not write one (`[Debug]` only affects debug/spec builds).

## 2. What makes the shimmer

**No mipmaps.** Each texture exists at one size. Where a polygon is far or seen edge-on, several texels fall inside
one pixel, and bilinear filtering reads only the 2x2 texels nearest the pixel centre. As the car moves, which texels
those are changes every frame, and that is the crawl. MSAA adds samples only on polygon edges; the inside of a road or
terrain polygon is shaded once per pixel either way. Only supersampling (more shaded pixels, averaged) or mipmaps
(pre-averaged texels) remove it.

**`I76_TERRAIN_TEX = 8` pushes past the point where that starts.** The engine picks the terrain texture level from the
nearest vertex depth with a rule tuned for a 640-wide screen: the 256 px tile (40 m wide, 0.156 m per texel) to
50 m x f. The rendered focal length in pixels is (render lines / 2) / 0.75, because Hor+ keeps the stock vertical FOV.
Head-on texels per pixel at the far edge of the 256 px level = 320 f / focal:

| render lines | focal (px) | f = 1 | f = 4 | f = 8 (best-wide) |
|---|---|---|---|---|
| 1440 (what the twin renders now) | 960 | 0.33 | 1.33 | **2.67** |
| 2160 (5160x2160, if it took effect) | 1440 | 0.22 | 0.89 | 1.78 |
| 2880 (6880x2880, or the old 4:3 2x) | 1920 | 0.17 | 0.67 | 1.33 |

Above 1.0 the tile aliases even head-on. A downhill road and the ground beside it are seen at a grazing angle, which
multiplies the depth-wise figure by 1/sin(angle), about 5 at 12 degrees. That is where the owner sees it. The levels
beyond 400 m (64, 32, 16 px) are hand-made coarser images and alias less. `I76_ROAD_TEX = 8` does the same for the
near road set (to 480 m instead of 60 m). The old 4:3 daily (2880 lines) ran x8 at 1.33; the move to the wide conf
plus windowed mode took it to 2.67, a plausible "it got worse" for the owner. `I76_TERRAIN_LOD` changes geometry, not
texture density. Its far sub-pixel triangles can flicker on silhouettes, but that is not the crawl on the ground.

## 3. Fixes and what each costs

| option | what it does to shimmer | cost / risk | verdict |
|---|---|---|---|
| **Fake fullscreen** (`[General] FullScreenMode = true`, the conf already has `FullscreenAttributes = fake`) | makes `[Glide] Resolution` the real target: 1.5x = 2.25 shaded px per pixel | the conf comment warns that fake fullscreen "reverts stretched to unspecified scaling". The target is exactly the panel shape (2.389), so unspecified = stretched: same picture. Pointer mapping uses the client rect (3440x1440 either way). Modal dialogs stay on top (fake = borderless window). The 4:3 sandbox has run this way since 2026-10-03. Expected 120 fps (44.6 M samples ~ the measured 3840x2880 + 4x) | **variant C**, the first thing to try |
| **2x supersampling** `6880x2880` (fullscreen fake) | 4 shaded px per pixel, an exact 2x2 box with `Resampling = bilinear`. Texture crawl roughly halves again vs 1.5x | 19.8 Mpx, under the FL10.1 8192 limit. With 4x MSAA = 79 M samples, between the measured 44 M (120 fps) and 88-100 M (90-93 fps): **expect 95-110 fps** on the GTX 1080 Ti. Without MSAA = 19.8 M (3x no-AA at 24.9 M held 120): expect 120, and 2x2 SS alone gives quarter-step edges | **variants B (4x) and E (no MSAA)** |
| **TERRAIN_TEX 8 -> 4** | puts the 256 px level back at ~1 texel per rendered pixel at 2160 lines (0.89); 2 if only 1440 lines | far ground less detailed between 200 and 400 m (64 px level there) | **variant F** (with C); D (= 1, stock) is the cause test |
| dgVoodoo Glide texture keys | `[Glide]` in 2.87.3 has `TMUFiltering` (appdriven / pointsampled / bilinear) and `DisableMipmapping` only (the CPL's key table, `dgVoodooCpl.exe` strings; plus an older `ForceBilinearFilter` key). `DisableMipmapping` can only remove mipmaps, and there are none. `Mipmapping = autogen_*`, `Filtering = <aniso>`, `KeepFilterIfPointSampled` exist **only in `[DirectX]`**; a key in the wrong section is ignored | none to try | no variant |
| `[GeneralExt] Resampling = lanczos-3 / bicubic` | only the downscale filter. At an exact 2x, bilinear is already the ideal box. At 1.5x a sharper kernel trades AA for crispness and can ring | measured 120 fps at 2x (matrix rows 08/09) | not a shimmer fix; taste after B/C |
| **Proxy mipmaps** | the real cure: dgVoodoo picks the mip by the true pixel footprint | ZGLIDE already contains the whole path: the flag at `[0x1001ee68]` makes `FirstDevice` call `grTexMipMapMode(GR_MIPMAP_NEAREST)` and every upload carry a chain to 1x1 (builder 0x10005160). The switch is one byte at RVA 0x1c60 (`89 3d` -> `89 1d`), patched after ZGLIDE loads exactly like `I76_ZGLIDE_TMUFIX` patches RVA 0x1a93. Unknowns: the chain builder is unread; **colour-keyed textures** (fences, signs, trees use `grChromakey*`) averaged into lower mips get fringes or holes; the chain costs +33 % TMU (2.6 -> ~3.5 MB of 8 MB, fine with TMUFIX); GR_MIPMAP_NEAREST shows mip band lines (one TMU, no trilinear). Doing it in the proxy instead (hook `grTexDownloadMipMap`, `grTexSource`, `grTexCalcMemRequired`, build chains ourselves) gives control over the chroma key but is 2-3 days | an experiment, after B/C/F are judged: about a day for `I76_ZGLIDE_MIPMAP=1` plus a live check of the chroma-keyed textures |
| NVIDIA control panel | anisotropic / negative LOD bias need mipmaps (none). Transparency SSAA / SGSSAA are D3D9-and-older driver paths, and dgVoodoo outputs D3D11. DSR = the same supersampling with a Gaussian filter and a desktop mode change. Profiles are keyed on `i76.exe` and would hit the daily driver | no gain, breaks "never experiment on the daily driver" | no |
| ReShade (SMAA/FXAA/TAA) | spatial edge filters cannot see texture crawl; TAA without engine motion vectors ghosts | taste | no |

## 4. A cheap, decisive live check (console agent, later; not the owner)

The client rect cannot answer this (both readings give 3440x1440), and neither can the proxy log or the watermark.
Use pixels and GPU memory:

1. **Same frame, two confs.** With the folder locked and the owner away:
   `tools\graphics\conf-probe.ps1 -GameDir "...\game-dd-20261003\Interstate 76" -UseConf "<conf>" -KeepInstalledDll -OutFile <png>`
   once with `dgVoodoo.wide.conf` (A) and once with `dgVoodoo.wide-native.conf` (Z: 3440x1440 + 4x).
   conf-probe restores the folder conf afterwards. Then
   `tools\graphics\edge-aa-probe.ps1 -Png <png>` on both. **If A and Z give the same histogram (and the PNGs are
   near-identical), the 5160x2160 is not in effect.** Then do the same with `dgVoodoo.wide-fs15.conf` (C): expect
   "8+ SAMPLES" (all eighths).
2. **GPU memory** (`nvidia-smi --query-gpu=memory.used --format=csv,noheader` while each is in the mission): the
   4:3 matrix shows target size moves it by hundreds of MiB (1x 986 / 1.5x+4x 1329 / 2x+4x 1666 MiB). A = Z within
   noise confirms item 1. C and B above them confirm the fix.
3. **Gate row 1b fix** (proposal, not done here): replace the watermark flip with a persistent sentinel such as
   `[General] Brightness = 150` and a mean-luminance check of a fixed sky crop against the unflipped boot. It is
   measurable without eyes and is not time-limited.

## 5. Variants built (lab twin, not run)

`<lab>\tools\make-test-variants.ps1 -Only 'shimmer-*'` now writes these. A variant can name its own conf
(`Conf` + `ConfSet`): the script generates `dgVoodoo.wide-<x>.conf` from `dgVoodoo.wide.conf`. It replaces each key in
place inside its section, refuses a key it cannot find, reads every key back section by section, and the bat copies
that file over `dgVoodoo.conf`. Each one boots T05 at the hill top (the shared hill env: `I76_MISSION=t05`,
`I76_SKIP_MOVIES=1`, `I76_START_POS` as the hill variants have it; at build time `7972,101.8,44035,-90,6`).

| bat | conf (md5) | changes vs PLAY.bat | look for |
|---|---|---|---|
| `TEST-shimmer-A-current` | `dgVoodoo.wide.conf` (`ac0ecdeb`) | none | the reference crawl, fps |
| `TEST-shimmer-B-ss2x` | `dgVoodoo.wide-ss2x.conf` (`b1f7d934`) | `FullScreenMode true`, `[Glide] Resolution 6880x2880`, `Antialiasing 4x` | least crawl; fps may drop below 120 |
| `TEST-shimmer-C-fullscreen-ss15` | `dgVoodoo.wide-fs15.conf` (`1fc63388`) | `FullScreenMode true` (5160x2160 + 4x as intended) | less crawl than A at 120 |
| `TEST-shimmer-D-terrain-tex-1` | `dgVoodoo.wide.conf` | `I76_TERRAIN_TEX=1` | far ground stops crawling (and blurs) = x8 is a source |
| `TEST-shimmer-E-ss2x-noaa` | `dgVoodoo.wide-ss2x-noaa.conf` (`00945db3`) | `FullScreenMode true`, `6880x2880`, `Antialiasing off` | as B, should hold 120 |
| `TEST-shimmer-F-ss15-terrain-tex-4` | `dgVoodoo.wide-fs15.conf` | C + `I76_TERRAIN_TEX=4` | the candidate new default |
| `TEST-shimmer-Z-native-msaa4` | `dgVoodoo.wide-native.conf` (`f5d64680`) | `[Glide] Resolution 3440x1440` (windowed, 4x) | instrument reference for section 4, not an owner test |

Verified offline: each preset through the twin's `PLAY-i76.ps1 -DryRun` (`I76_MISSION=t05`, `I76_START_POS`,
`I76_TERRAIN_TEX` = 8 / 1 / 4 as intended, `I76_ASPECT=3440x1440`, `I76_FAR_CLIP=1800`, no guard refusal). Each
generated conf diffed against `dgVoodoo.wide.conf`: only the header comment and the named keys differ. Every value is
one dgVoodoo accepts (the same tokens appear in accepted confs: `true`, compact `WxH`, `4x`, `off`). The fullscreen
variants still need the conf-accepted check (`conf-probe.ps1 -ClientRect -HideGlobal -UseConf` is not a combination
the script supports; the client-rect trial reads the folder conf, so copy the variant conf in first, or run the bat
and read the client size) before an owner session.

## 6. Open

- Live confirmation of item 1 (section 4). Until then, "windowed renders at the window size" is the best reading of
  the pixels, not a measurement.
- The 16x10 conf (`4608x2880`, windowed) very likely had the same limit: the daily driver's "2x" may never have been 2x.
  Its capture would show it (`edge-aa-probe.ps1` on any 16x10 cockpit capture with a pillar edge in the region).
- Whether fake fullscreen changes anything for the 2D shell's pointer (`I76_CURSOR_MAP*`, u32x): owner test 31 asks for
  one menu click and one Esc-menu Exit in C.
- The ZGLIDE mipmap flip (section 3), if B/C/F still crawl.

## Measured 2026-10-12 (live, console agent)

Sections 1 and 5 were read from files. This one is measured, and **it corrects item 1 of the short answer**: dgVoodoo
does render the `[Glide] Resolution` in every conf, windowed included. What loses it is the downscale. With
`ScalingMode = stretched` the downscale to the window **point-samples** the big target, in windowed and in fake
fullscreen alike. That keeps one rendered pixel per presented pixel and throws the other samples away. With
`ScalingMode = stretched_ar` the real filter runs. Because the forced 6880x2880 has the panel's own 2.389 shape, the
picture stays full width (no side bars in the mission or the Esc menu).

**Method.** Lab `tools\graphics\ss-measure.ps1` (new). Each boot installs the conf on the twin and runs proxy-run with the
twin's own STRLKUP.DLL (509c6df0) and the best-wide preset switches. It boots straight into T05, waits until the car is
placed at the hill top (`I76_START_POS`), then measures: nvidia-smi memory and utilisation at 1 Hz for 6 s, proxy fps
from telemetry (`phase_stats.py`), the client rect, and two full-screen captures. The captures come from a DPI-aware
process and were checked to be 3440x1440 (not DPI-virtualised). It restores `dgVoodoo.conf` = `dgVoodoo.wide.conf` in a
`finally`. Edges: lab `tools\graphics\pillar-edge.ps1` (new). It walks the right edge of the cockpit A-pillar (a 3D
polygon, near-black against terrain, rows 450..1250) and anchors on the pillar's flat side, so the terrain texture does
not fake coverage levels. For each row it takes the first pixel brighter than the pillar and computes its coverage. "AA
rows" = rows whose edge pixel is partial. The old `edge-aa-probe.ps1` read this region noisily: the 1-sample E captures
came out "8+ samples".
Captures and `results.txt`: lab `captures\ss-measure-20261012`.

| conf (bat) | mode, scaling | Glide target, AA | GPU mem MiB | GPU util % | fps | AA rows (per capture) | edge coverage levels | n |
|---|---|---|---|---|---|---|---|---|
| `wide-native` (Z) | windowed, stretched | 3440x1440, 4x | 1587 | 19 | 120.2 | 87 / 79 % | quarters (2/8, 6/8 most) | 1 |
| `wide` (A = PLAY.bat) | windowed, stretched | 5160x2160, 4x | 1985 | 32 | 120.2 | 57 / 55 % | 2/8, 6/8 | 1 |
| `wide-fs15` (C) | fake fullscreen, stretched | 5160x2160, 4x | 1985 | 35 | 120.2 | 60 / 56 % | 2/8, 6/8 | 1 |
| `wide-ss2x` (B) | fake fullscreen, stretched | 6880x2880, 4x | 2547 | 62 | 120.3 | 49 / 49 % | quarters | 1 |
| `wide-ss2x-noaa` (E) | fake fullscreen, stretched | 6880x2880, off | 1604 | 44 | 120.2 | 2 / 0 % | **none: hard edges** | 1 |
| win2x | windowed, stretched | 6880x2880, 4x | 2547, 2546 | 62, 62 | 120.8, 120.2 | 49 / 56, 49 / 40 % | quarters | 2 |
| win2x-noaa | windowed, stretched | 6880x2880, off | 1604, 1604 | 44, 44 | 120.0, 120.1 | 0 / 0, 1 / 7 % | **none: hard edges** | 2 |
| win2x-noaa + `Resampling = bicubic` | windowed, stretched | 6880x2880, off | (1861)* | 49* | 98.1* | 0 / 0 % | none | 1 |
| win2x-noaa + `Resampling = lanczos-3` | windowed, stretched | 6880x2880, off | (1858)* | 52* | 101.0* | 0 / 1 % | none | 1 |
| win2x-noaa + `ScalingMode = stretched_ar` (Y) | windowed, **stretched_ar** | 6880x2880, off | (1878, 1871)* | 49*, 46* | 115.7*, 120.2 | 64 / 68, 66 / 67 % | **exact quarter steps (2/8 4/8 6/8) = 2x2 box** | 2 |
| **`wide-win2x-ar` (S)** | windowed, **stretched_ar** | 6880x2880, 4x | (2813, 2813)* | 62*, 64* | 121.0*, 120.5* | **86 / 91, 85 / 71 %** | **all eighths incl. 1/8 3/8 5/8 = 2x2 SS x 4x MSAA** | 2 |

\* Another program (DOOM II, not started by the agent) was launched partway through the session. The idle GPU baseline
rose from 1214 to 1468 MiB, so the starred memory figures are about 255 MiB high. Subtract that and S is 2558 MiB (= B
and win2x) and Y is about 1620 MiB (= E). The bicubic and lanczos-3 fps dips coincide with it. A fourth variant
(`Resampling = pointsampled`) came up in an external camera view with no pillar in frame, so it gives no reading. Spread
of repeated runs: at most 1 MiB, 2 % utilisation and 0.8 fps (win2x, win2x-noaa, S). The rows with n = 1 lack a repeat
for lack of console time.

**What the numbers say.**
1. **The target is rendered in every conf.** Over native, memory rises +398 MiB for 5160x2160 + 4x, with A (windowed)
   and C (fake fullscreen) identical, and +960 MiB for 6880x2880 + 4x. 6880x2880 without AA (19.8 M samples) costs the
   same memory as native + 4x (19.8 M). GPU load follows the same order: 19 / 32-35 / 44 / 62 %. So "windowed renders at
   the window size" (short answer item 1, section 1) was **wrong**. Fake fullscreen changes nothing (A = C, win2x = B).
2. **The `stretched` downscale throws the samples away.** 2x without MSAA presents perfectly hard edges, in windowed (0-7 %)
   and in fake fullscreen (0-2 %). A 2x2 box would give quarter steps on most rows. With 4x MSAA added, the 2x target
   presents *fewer* partial edge pixels than native + 4x (49 % vs 79-87 %). Each presented pixel is one rendered pixel's
   4x resolve, from a target whose edge pixels are half as wide. That is what the owner saw: B and C look like A, hard
   edges, and the cost is hidden under the 120 cap. It also explains the 4-level signature in section 1: A's 1.5x target
   is point-sampled down to one 4x-MSAA pixel. `Resampling = bicubic / lanczos-3` changes nothing under `stretched`.
3. **`stretched_ar` runs the filter.** The same 2x no-AA target then presents exact 2x2-box quarter steps, and 2x + 4x
   presents every eighth with 71-91 % partial rows. That is 16 samples at edges and 4 shaded samples per pixel for the
   texture crawl. The picture stays full width in the mission and in the Esc menu. The client is 3440x1440, as with
   `stretched`, because the forced 6880x2880 has the window's aspect. The conf comment ("_ar just pillarboxes 4:3")
   described the old 4:3-shaped targets, not this one.
4. **Cost:** 62-64 % GPU on the GTX 1080 Ti against 32 % for PLAY.bat. Every conf holds 120.0-121.0 fps (the proxy's
   120 pacing), so the cost shows only as GPU load and memory.
5. **Mouse (n = 1):** with S installed, Esc in the T05 mission opened Spanner's Cafe at full width. One click on the
   drawn "Exit" (screen 2318,1330, cursor-map preset switches on) closed the menu back to the mission, so the click
   landed where it was drawn. **Not tested:** the DirectDraw main menu (MELEE / bookmarks) under `stretched_ar`. That
   is the 2D shell at 640x480, where `_ar` could pillarbox or shift the cursor map. The owner check below covers it.

Why `stretched` point-samples and `stretched_ar` does not: no dgVoodoo ReadMe was at hand (none on disk, and none
fetched). This is an empirical result for 2.87.3 on this machine, not a documented rule.

**Working conf:** `dgVoodoo.wide-win2x-ar.conf` (md5 `9c1ac5bc`). It is `dgVoodoo.wide.conf` with
`[General] ScalingMode = stretched_ar`, `[Glide] Resolution = 6880x2880` and `Antialiasing = 4x`, and is still windowed
(FullScreenMode false, borderless). Launcher: `game-dd-20261003\TEST-shimmer-S-win2x-ar.bat` (T05 hill top, best-wide
preset). Instrument twin: `TEST-shimmer-Y-win2x-ar-noaa.bat`. Both are generated by `tools\make-test-variants.ps1`.
Variants B, C and E do not supersample anything visible and can be retired. The old S-win2x / Y-win2x-noaa files
(stretched) were removed. **Owner check for S:** (a) the main menu and the bookmark / melee route: clicks land, no side
bars; (b) Esc menu Exit; (c) the hill drive: crawl vs A. Then promote, after the route test
(option6-trip-test / leg-b), before the daily driver.
TERRAIN_TEX 8 -> 4 (section 3) still stands as a second step if S alone leaves too much crawl.
