# Graphics enhancement menu: supersampling, antialiasing, and what else the Glide path allows

*Research and config preparation, 2026-10-02. **Nothing here was run in the game**; the sandbox's
`game\dgVoodoo.conf` was read, not edited. Every cost figure below is an estimate from pixel and sample counts unless
it says "measured". The ranking is the order to test in, to be replaced by the capture results (section 6).*

The owner's request: "try 1.5x and 2x superresolution and improved antialiasing techniques - anything else you can
think of to enhance the graphics."

Stack: `i76.exe -glide` -> `ZGLIDE.DLL` -> `Glide2x.dll` (dgVoodoo **2.87.3**, file version checked) -> D3D11
FL10.1 -> GTX 1080 Ti (11 GB) -> a borderless window on the 3440x1440 179 Hz panel.

> **Read the last section first (note added 2026-10-03).** Sections 1 to 6 were written before it was known that
> dgVoodoo was rejecting the sandbox's `dgVoodoo.conf` and running a 2020 global `%APPDATA%` file. The section 1
> table (3360x2100 internal, 8x MSAA, bilinear downscale, the conf line numbers), every cost estimate built on it,
> and "`FPSLimit` ... is inert on this build" in section 3 describe a file that was not in effect. The measured
> matrix and the pick (2x internal + 4x MSAA at 120.1 fps) are in
> ["Measured 2026-10-03 on the FIXED config"](#measured-2026-10-03-on-the-fixed-config-the-earlier-matrix-was-void);
> ReShade over dgVoodoo was run on 2026-10-03 (120.1 fps, [RENDERER-ALTERNATIVES.md](RENDERER-ALTERNATIVES.md)
> section 11), so "Nothing here was run in the game" above and "Not yet run together" in section 3 are superseded.

## 1. Where the picture stands today (the facts the menu rests on)

| fact | value | source |
|---|---|---|
| Engine's logical frame | 640x480 (`grSstWinOpen(res 7)`), 2 colour buffers + 1 aux (depth) buffer | `game\mciproxy.log`: `grSstWinOpen(res 7, ..., 2/1 buffers)` |
| Presented frame | **2304x1440** at screen x 568..2872 (the 16:10 Glide frame aspect-fitted into the 1440-tall window) | lab `docs\CONFIG-OPTIONS.md` section 3, `docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md` (H2) |
| Internal render target | `[Glide] Resolution = 3360x2100` = **1.458x** the presented frame per axis (2.13x the pixels) | `game\dgVoodoo.conf` line 83 |
| Antialiasing | `[Glide] Antialiasing = 8x` (MSAA, forced; the engine asks for none: ZGLIDE imports no `grAADraw*`) | conf line 84; ZGLIDE import table |
| Downscale filter | `[GeneralExt] Resampling = bilinear` | conf line 43 |
| Texture filter | `[Glide] TMUFiltering = bilinear` (forced) | conf line 69 |
| Colour depth | `[GlideExt] DitheringEffect = pure32bit`: 32-bit output, no dither pattern (load-bearing, night-road colour bug) | conf line 104 |
| Frame rate at these settings | **120.1 fps, dt sd 0.06 ms, p99 8.45 ms** with `I76_GLIDE_REFRESH=120`, far clip 1800 m (measured, n = 1) | `docs\FPS-120.md` "Measured 2026-10-02" |

So the sandbox **already supersamples** (1.46x) and already runs 8x MSAA at 120 fps. "2x of 1680x1050" in the conf's
history is 2x of the `[DirectX]` window mode, not of what reaches the panel. The scale factors in this document and
in the variant files are relative to the **presented 2304x1440 frame**, because that is the ratio the downscale
filter sees.

**What "supersampling" means here.** dgVoodoo renders the Glide scene into a target of `[Glide] Resolution`, then
scales it to the window with the `[GeneralExt] Resampling` filter. A target larger than the presented frame is
ordered-grid supersampling: every presented pixel averages several fully shaded pixels, so it antialiases
*everything* - polygon edges, colour-keyed texture cut-outs (ZGLIDE uses `grChromakeyMode`; fences, poles and signs
drawn as textures), texture shimmer, and thin distant terrain triangles. MSAA only adds coverage samples on
*polygon* edges: a colour-keyed fence inside a polygon gets nothing from it.

**What the engine does that no wrapper key changes** (i76-map `subsystems\renderer.md`, ZGLIDE's 39 Glide imports):

- It imports `grTexMipMapMode`, `grTexFilterMode`, `grTexDownloadMipMap`, `grFogMode`, `grFogColorValue`,
  `grDepthBuffer*`, `grChromakey*`, `grLfbLock` - and **not** `grTexLodBiasValue`, `grFogTable`, `grDitherMode`,
  `grGammaCorrectionValue` or any `grAADraw*`. So: no engine mip bias, no table fog, no engine dithering or gamma
  call, no engine antialiasing. (Which modes it passes to the calls it does import has not been traced.)
- Terrain texture distance tiers are picked by the engine from hand-authored images in the paks, roads switch
  texture set at 60 m: engine logic, not Glide mipmapping (`docs\DRAW-DISTANCE.md`).
- Terrain tessellation depends on focal scale / half screen width in the engine's own 640-wide viewport. **The
  int16 terrain-index ceiling (far clip <= 2500 m) is not affected by any resolution or AA setting here**: dgVoodoo's
  forced resolution never reaches the engine.

## 2. The ranked menu

Sample arithmetic used for the cost column (colour + depth = 8 bytes per sample):

| variant | target | pixels vs presented | MSAA | samples per presented pixel (shaded / edge) | total samples vs live | target memory |
|---|---|---|---|---|---|---|
| 1x | 2304x1440 | 1.00 | off | 1 / 1 | 0.06 | 27 MB |
| 1x-msaa8 | 2304x1440 | 1.00 | 8x | 1 / 8 | 0.47 | 212 MB |
| **live** | 3360x2100 | 2.13 | 8x | 2.1 / 17 | **1.00 (120.1 fps measured)** | 452 MB |
| 1.5x | 3456x2160 | 2.25 | off | 2.25 / 2.25 | 0.13 | 60 MB |
| 1.5x-msaa4 | 3456x2160 | 2.25 | 4x | 2.25 / 9 | 0.53 | 239 MB |
| 2x | 4608x2880 | 4.00 | off | 4 / 4 | 0.24 | 106 MB |
| 2x-msaa4 | 4608x2880 | 4.00 | 4x | 4 / 16 | 0.94 | 425 MB |
| 2x-msaa8 | 4608x2880 | 4.00 | 8x | 4 / 32 | 1.88 | 849 MB |
| 3x | 6912x4320 | 9.00 | off | 9 / 9 | 0.53 | 239 MB |

The engine's pixel work is one texture and a vertex colour, and the scene is a few tens of thousands of vertices,
so the cost should follow the sample count (memory traffic), not shader work. On that estimate everything except
`2x-msaa8` costs **less** than the live conf, which holds 120 fps with a 0.06 ms spread. Treat that as a prediction
to check: one thing could break it (risk R3, LFB locks).

### Rank 1 - 2x internal resolution, with 4x MSAA (`conf-2x-msaa4`, then `conf-2x`, `conf-2x-msaa8`)

```
[Glide]
Resolution                          = 4608x2880
Antialiasing                        = 4x          ; off / 2x / 4x / 8x / appdriven
```

- **Effect.** Four shaded pixels per presented pixel instead of 2.1: colour-keyed edges, texture shimmer on the
  road and distant terrain, and the 1800 m terrain edge all get twice the sampling of today. Mip selection moves
  one level sharper (log2 of the scale), the only "LOD bias" this stack has. At exactly 2x the bilinear downscale
  is an exact 2x2 box average (each presented pixel reads its four source pixels with equal weight); at the live
  1.458x the weights are uneven from pixel to pixel, a known source of slight softness and crawl.
- **Cost at 120 fps.** `2x-msaa4` is 0.94x the live sample count: expected to hold 120. `2x` alone is a quarter
  of it. `2x-msaa8` is 1.9x live: the one to watch.
- **Risks.** R1 (size acceptance), R3 (LFB), R4 (HUD does not sharpen). None to gameplay.
- **1.5x** (`conf-1.5x`, `conf-1.5x-msaa4`: `Resolution = 3456x2160`) is almost the live setting (1.458x) and is in
  the set because the owner asked for it and as the half-way point; expect it to look like today.

### Rank 2 - the engine's own detail options and the far clip (no conf change)

Free quality that is decided before any pixel is sampled. In the in-game Options (i76-map `subsystems\renderer.md`,
`options.md`): Terrain Resolution **High** (A = 40: finer quadtree), Object Detail **on** (LODs 1 and 2 collapse to
0), Terrain Detail on (ground clutter within 120 m), Shadow Detail 2 (object-LOD shadows within 50 m), Rear Mirror
level 2 (full scene), Visibility Range on. Check what the sandbox's options are set to before comparing variants,
and keep them fixed for the whole capture session.

Far clip: `I76_FAR_CLIP=1800` is in the harness's "all" set; **2500 is the ceiling** (int16 terrain indices,
`docs\FARCLIP-CAMERA-CRASH.md`; the proxy refuses more). Interplay with this menu: the 600 m stock veil hid the
far terrain, and at 1800 m the horizon band is full of sub-pixel triangles and the smallest texture tiers - that
band is where supersampling pays most and where a too-sharp filter (lanczos, CAS) crawls most. Fog: ZGLIDE has
`grFogMode` and `grFogColorValue` but no `grFogTable`, so there is no fog table for a wrapper to stretch; the
depth haze is the engine's shade term (reaches 1.0 near 600 m) and whatever it iterates per vertex. No dgVoodoo
key changes fog. The scene is painter-sorted far to near, so a longer far clip does not cost depth precision.

### Rank 3 - sharpening after the downscale: ReShade CAS (section 4)

Supersampling plus a bilinear downscale is clean but soft. Contrast-adaptive sharpening on the presented frame
restores edge contrast without the ringing of a sharp resampling kernel. ~0.2 ms on this GPU (estimate). It also
sharpens the HUD and the shell menus (ReShade sees the final frame). Start at CAS strength 0.3-0.5.

### Rank 4 - the downscale filter (`conf-2x-bicubic`, `conf-2x-lanczos3`, `conf-3x-bicubic`)

```
[GeneralExt]
Resampling                           = bicubic     ; pointsampled / bilinear / bicubic / lanczos-2 / lanczos-3
```

dgVoodoo's readme orders them by sharpness: bilinear "smooth but blurred", lanczos-2 "slight halation around sharp
edges", bicubic "smooth but more sharper", lanczos-3 "sharpest ... stronger halation". The filters are written for
scaling in general; whether their kernels widen when *minifying* is not documented. At 2x, bilinear is already the
ideal box; a sharper kernel there trades antialiasing for crispness and can ring on HUD text and poles. At 3x a
4-tap bilinear reads only 4 of the 9 source pixels per presented pixel, so bicubic (16 taps) should use more of
what was rendered - `conf-3x` vs `conf-3x-bicubic` settles it. Cost: negligible (one pass at presented size).
`pointsampled` is never right for a downscale.

### Rank 5 - 3x internal resolution (`conf-3x`, `conf-3x-bicubic`)

```
[Glide]
Resolution                          = 6912x4320
Antialiasing                        = off
```

Nine shaded samples per pixel, half the live sample count, 239 MB. Diminishing returns over 2x-msaa4 on polygon
edges (9 vs 16 edge samples) but the best texture and cut-out antialiasing on offer. 6912 px is inside the D3D11
FL10.1 limit of 8192 (dgVoodoo readme: "Max texture size is 8K x 8K"); 4x (9216 px) is not possible. Adding MSAA
on top (3x + 4x = 956 MB, 2.1x live) is not in the set; make it only if 3x alone looks worth pursuing.

### Rank 6 - texture filtering and mipmaps

```
[Glide]
TMUFiltering                        = bilinear    ; appdriven / pointsampled / bilinear   (live: bilinear)
DisableMipmapping                   = false       ; NOT in the live conf; add it under [Glide] to use it
```

- `conf-live-tmu-appdriven` shows what the engine itself asks for through `grTexFilterMode`. If it looks the same,
  the forced bilinear is a no-op and can stay; if the engine point-samples anything (sky, HUD bitmaps), forced
  bilinear is what is softening it, and that is worth knowing.
- **There is no anisotropic filter for Glide.** `[DirectX] Filtering` is the D3D wrapper's key and does nothing in
  `[Glide]`; Glide 2 has no anisotropy and dgVoodoo adds none. Supersampling is the substitute: 2x renders the
  oblique road with one mip level more detail.
- **There is no mip/LOD bias key**, and the engine never calls `grTexLodBiasValue`. The author of dgVoodoo declined
  one (`docs\DRAW-DISTANCE.md`). `DisableMipmapping = true` (present in the CPL-written conf on this machine, so
  it is a real `[Glide]` key; confirm against 2.87.3 by writing a conf with `dgVoodooCpl.exe` in a scratch folder)
  forces the top level everywhere: sharper distance, more shimmer. Only sensible at 2x or above. Not in the
  variant set; a hand edit for a follow-up if the far road still looks soft.

### Rank 7 - deband and a subtle bloom (ReShade, taste)

The hardware textures are RGB565 (`.m16`); with 32-bit output the remaining banding is in the textures themselves
(sky and horizon gradients). `Deband.fx` smooths it at the cost of fine texture grain; keep the threshold low.
A light bloom suits headlights, tracers and the desert sky but changes the 3dfx look the conf deliberately keeps
(`EnableGlideGammaRamp`); it also blooms white HUD text. Off by default; the owner's call after seeing it.

### Rank 8 - MSAA level on its own (`conf-1x`, `conf-1x-msaa8`)

`[Glide] Antialiasing = off / 2x / 4x / 8x / appdriven`. `appdriven` equals off here (the engine never asks).
These two variants exist as references: `1x` is the no-enhancement baseline, `1x-msaa8` isolates what MSAA does
without supersampling (expect clean polygon silhouettes, raw cut-outs and shimmering textures). Per the readme,
forced MSAA is global, not per primitive.

### Rank 9 - SMAA (ReShade)

Post-process edge AA on the presented frame. After 2x supersampling there is little left for it to find and it
softens HUD text; its place is a cheap fallback if a large target turns out not to hold 120 fps (`1x` + SMAA).

### Rank 10 - gamma, brightness, dithering, depth

- `[Glide] EnableGlideGammaRamp = true` is "the bright 3dfx look"; false gives a darker, flatter picture. The
  engine sets no gamma of its own (no `grGammaCorrectionValue` import), so this key alone decides it. Keep.
- `[General] Brightness / Color / Contrast` (integers, 100 = neutral; not in the live conf, add under `[General]`)
  are available for taste.
- Dithering is already removed: `[GlideExt] DitheringEffect = pure32bit`. The other values (`dither2x2`,
  `dither4x4`) bring the Voodoo ordered-dither pattern back, and anything but pure32bit re-opens the night-road
  colour bug. `Dithering` and `DitherOrderedMatrixSizeScale` have no visible effect while the effect is pure32bit.
  There is no `DisableDitheringEffect` key in this version's conf.
- `[Glide] 16BitDepthBuffer` (default false, absent from the live conf): leave it; true only reproduces Voodoo
  z-fighting. `ForceEmulatingTruePCIAccess = true` is in the live conf and is about LFB access timing, not image
  quality (see R3). TruForm/N-patch emulation is a `[DirectX]` matter and does not exist for Glide.

### Not recommended / not available

- **DLDSR: not available on this card.** It needs an RTX GPU; a GTX 1080 Ti has classic **DSR** only. DSR raises
  the *desktop* mode (the game is a borderless window, so the whole desktop would have to be switched to e.g.
  5160x2160), then the driver downscales with a Gaussian "smoothness" filter. That is the same supersampling
  `[Glide] Resolution` already does inside dgVoodoo, with a blurrier filter, a global side effect, and a changed
  window geometry for the pointer mapping. No reason to use it here.
- **NVIDIA Control Panel overrides** (anisotropic 16x, negative LOD bias, image sharpening, FXAA) may act on
  dgVoodoo's D3D11 output, but a driver profile is keyed on the executable name: a profile for the sandbox's
  `i76.exe` also applies to the portable install's `i76.exe`. That breaks "never experiment on the daily driver",
  so none of it is in the test set. ReShade in the sandbox folder gives the same effects without leaving the folder.
- **Texture replacement.** dgVoodoo has no texture dump/replace facility. The same-size enhanced pack was built,
  measured as within RGB565 noise of the originals, and retired (`docs\HD-TEXTURES-RESEARCH.md`, `texture-lab\`);
  true HD needs a hash-replacing renderer (the unverified `tools\openglide-hd` fork) - a different stack. The
  far-distance terrain tiers can be improved data-side in the paks (`docs\DRAW-DISTANCE.md`, deferred).
- **Frame generation** (Lossless Scaling) is motion, not image quality; the conf's `ForceVerticalSync = false`
  was chosen for it. Unchanged by anything here.

## 3. Risks and compatibility

| # | risk | what to look for | status |
|---|---|---|---|
| R1 | dgVoodoo rejects or snaps a custom `[Glide] Resolution`. The compact `WxH` form is required (the `h:, v:` form failed here). 3360x2100 (taller than the 1440 panel, not an enumerated mode) works today, so 4608x2880 and 6912x4320 are expected to, but that is not proven | `capture-frame.ps1` prints the frame rectangle: it must stay 2304x1440 at x 568. A 640x480 or 4:3 window means the size was refused | untested |
| R2 | A key in the wrong section is silently ignored | every variant changes keys in place, in their existing section; `apply-conf.ps1` prints the section-qualified diff. `Resampling` is `[GeneralExt]`; `Resolution`, `Antialiasing`, `TMUFiltering` are `[Glide]`; `DitheringEffect` is `[GlideExt]` | by construction |
| R3 | **LFB access.** ZGLIDE imports `grLfbLock`. If the engine locks the frame buffer every frame (cockpit, HUD text, screen shake), dgVoodoo has to resolve the MSAA target and scale it to and from 640x480 each time; that cost grows with target size and MSAA level and would not follow the sample-count estimate | frame dt mean or p99 rising with resolution while GPU utilisation stays low; compare cockpit view against chase view | unknown - the main reason to measure |
| R4 | **HUD and cockpit do not get sharper.** They are drawn in the same 640x480 Glide frame. Polygons and textured quads are rasterised at the forced resolution (edges sharpen, texels stay 640x480-era art); anything written through the LFB is 640x480 pixels scaled up | the `hud-text` crop: expect little or no change across variants; a sharp resampling filter or CAS may halo it | expected |
| R5 | Pointer box / menu clicks. u32x and `maplib.ps1` map the pointer onto the *presented* frame (4:3 box 760..2680 inside the 16:10 frame), and `maplib` reads the aspect of the first `Resolution` line in the conf | all variants are exactly 16:10, so the presented geometry is the same as today. Confirm once on the largest variant: Esc menu in a mission, the hand reaches the items as it does on the live conf. Do not change the aspect in a test variant | by construction; one check |
| R6 | The 2D shell (menus, briefings) is DirectDraw: `[DirectX] Resolution = 1680x1050`, untouched by every variant | shell looks as before | by construction |
| R7 | VRAM: the largest variant in the set is 849 MB of targets on an 11 GB card | `nvidia-smi` memory in the protocol | fine |
| R8 | A stale variant rolls back an unrelated conf change | `apply-conf.ps1` refuses a variant that differs from the live conf in keys its header does not declare; regenerate with `make-variants.py` | handled |

**Proxy switches.** None of the proxy's switches read the conf, and none of these keys reach the engine:

- `I76_GLIDE_REFRESH=120` rewrites the *refresh* argument of `grSstWinOpen`; the resolution argument stays
  `res 7` (640x480) and dgVoodoo applies `[Glide] Resolution` on top. Independent. The refresh request is also
  what paces the game, so a variant that cannot finish a frame in 8.33 ms shows as a mean dt above 8.34 ms.
- `I76_FAR_CLIP`, `I76_FIXED_STEP`, `I76_RENDER_INTERP`, `I76_FRAMERATE_FIXES`, telemetry: engine-side, unaffected.
  A longer far clip adds triangles, not pixels; its cost does not multiply with the resolution.
- `FPSLimit` in `[GeneralExt]` is inert on this build (`docs\FPS-120.md`); the variants leave it alone.
  *(Void 2026-10-03: measured while the conf was rejected; not re-measured. The fixed conf sets `FPSLimit = 0`.)*
- ReShade's `dxgi.dll` is loaded by dgVoodoo, after the proxy's `LoadLibraryA` hook has matched `ZGLIDE.DLL` by
  name; the two do not touch the same import slots. Not yet run together.

## 4. ReShade, confined to the sandbox folder

**Does it work with dgVoodoo?** The usual recipe for dgVoodoo games is ReShade's 32-bit DLL named `dxgi.dll` beside
dgVoodoo's DLLs; it hooks the D3D11 swap chain dgVoodoo creates. dgVoodoo's own readme does not mention ReShade,
and this pairing has not been run with 2.87.3 in this sandbox. The sandbox folder has no `dxgi.dll` or `d3d11.dll`
today, so nothing is displaced.

What it sees: the **presented** back buffer, after dgVoodoo's downscale - for both swap chains, so effects also
apply to the DirectDraw shell menus. Hence: sharpening and deband pair well with supersampling; SMAA is mostly
redundant after it.

**Depth-based effects (MXAO/ambient occlusion, depth of field): treat as unavailable.** The engine allocates a
Glide depth buffer and imports the depth calls, but whether it writes depth is untraced (the scene is
painter-sorted); the depth target is at the internal resolution and multisampled, neither of which ReShade's
generic depth detection handles; and the HUD shares the frame, so AO would draw through the cockpit. If curiosity
wins: `conf-1x` (no MSAA, target = presented size), ReShade's depth display shader, one look.

Recipe (`G` = `C:\Users\james\i76-uncap-lab\game`; the game closed; never the portable install):

1. Download the ReShade setup exe from reshade.me. Either run it and pick `G\i76.exe`, API "Direct3D 10/11/12",
   or do it by hand: open the setup exe with 7-Zip, take `ReShade32.dll`, copy it to `G\dxgi.dll`.
2. Shaders into `G\reshade-shaders\Shaders` and `\Textures`: from the installer's package list take the standard
   effects and SweetFX (`SMAA.fx` with its two textures, `CAS.fx`, `Deband.fx`, a bloom such as `MagicBloom.fx`).
3. `G\ReShade.ini`: under `[GENERAL]` set `EffectSearchPaths=.\reshade-shaders\Shaders` and
   `TextureSearchPaths=.\reshade-shaders\Textures`, and `PresetPath=.\i76.ini`. Build the preset once with the
   overlay (Home key; the game captures the mouse, so do it at the shell menu) and keep `G\i76.ini` beside it.
   Technique order: `SMAA` (only without supersampling), `Deband`, bloom, `CAS` last.
4. First start compiles the shaders (a pause of several seconds); check `G\ReShade.log` for the swap-chain size
   (must be the window, not the internal target) and for compile errors.
5. Remove: delete `G\dxgi.dll`, `G\ReShade.ini`, `G\ReShade.log`, `G\i76.ini`, `G\reshade-shaders\`. Nothing is
   written outside `G` when installed by hand.

Test it as its own step after the conf variants are judged, on the winning variant, with a with/without pair and
`frame_stats.py` for the cost. A crash at start with ReShade present is ReShade's until shown otherwise: remove
the one DLL and re-run before diagnosing anything else.

## 5. The variant files

`C:\Users\james\i76-uncap-lab\tools\graphics\` (generated by `make-variants.py` from the live conf; each is a
byte-for-byte copy with only the listed keys changed and a header comment naming them):

| file | `[Glide] Resolution` | `[Glide] Antialiasing` | other |
|---|---|---|---|
| `conf-1x.conf` | 2304x1440 | off | |
| `conf-1x-msaa8.conf` | 2304x1440 | 8x | |
| `conf-1.5x.conf` | 3456x2160 | off | |
| `conf-1.5x-msaa4.conf` | 3456x2160 | 4x | |
| `conf-2x.conf` | 4608x2880 | off | |
| `conf-2x-msaa4.conf` | 4608x2880 | 4x | |
| `conf-2x-msaa8.conf` | 4608x2880 | 8x | |
| `conf-2x-bicubic.conf` | 4608x2880 | off | `[GeneralExt] Resampling = bicubic` |
| `conf-2x-lanczos3.conf` | 4608x2880 | off | `[GeneralExt] Resampling = lanczos-3` |
| `conf-3x.conf` | 6912x4320 | off | |
| `conf-3x-bicubic.conf` | 6912x4320 | off | `[GeneralExt] Resampling = bicubic` |
| `conf-live-tmu-appdriven.conf` | 3360x2100 (live) | 8x (live) | `[Glide] TMUFiltering = appdriven` |

The live conf (3360x2100, 8x, bilinear) is the thirteenth condition: run it with no variant installed.

Tools in the same folder: `apply-conf.ps1` (`-List`, `-Variant <name>`, `-Status`, `-Restore`; backs the live conf
up once as `game\dgVoodoo.conf.pre-graphics`, hash-checks every copy, refuses while an `i76`/`nitro` process runs,
refuses any folder but the lab sandbox, refuses a stale variant), `capture-frame.ps1` (full presented frame to
PNG at panel resolution), `make-crops.py` + `crops.json` (same rectangles from every shot, side-by-side sheets),
`make-variants.py` (regenerate after any change to the live conf).

## 6. Capture protocol (for the integrator)

At the physical console (not RDP), no other `i76` process, `game\.console-test.lock` free, sandbox only. About
45 s per run. Keep the in-game options and the camera view (cockpit, as booted) fixed for the whole session.

```powershell
cd C:\Users\james\i76-uncap-lab
$out = "captures\graphics\$(Get-Date -Format yyyyMMdd-HHmm)"; New-Item -ItemType Directory -Force $out | Out-Null
$variants = 'live','1x','1x','1x-msaa8','1.5x','1.5x-msaa4','2x','2x-msaa4','2x-msaa8','2x-bicubic','2x-lanczos3','3x','3x-bicubic','live-tmu-appdriven','live'
$n = 0
foreach ($v in $variants) {
    $n++; $tag = "{0:d2}-{1}" -f $n, $v
    if ($v -ne 'live') { .\tools\graphics\apply-conf.ps1 -Variant $v; if ($LASTEXITCODE) { break } }
    $env:GFX_TAG = $tag; $env:GFX_OUT = (Resolve-Path $out).Path
    .\autotest\proxy-run.ps1 -Mission t01 -Hold 0 -Env @{ I76_GLIDE_REFRESH = "120" } -Run {
        Start-Sleep 8                                   # same moment after entry every run; the car is parked
        & ..\tools\graphics\capture-frame.ps1 -Out "$env:GFX_OUT\$env:GFX_TAG.png"
        python C:\Users\james\i76-everywhere\tools\telemetry\frame_stats.py 15 $env:GFX_TAG | Tee-Object -Append "$env:GFX_OUT\frame_stats.txt"
        "$env:GFX_TAG gpu: " + (nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader) | Tee-Object -Append "$env:GFX_OUT\frame_stats.txt"
    }
    if ($v -ne 'live') { .\tools\graphics\apply-conf.ps1 -Restore }
}
.\tools\graphics\apply-conf.ps1 -Status            # must say: no graphics variant installed
python tools\graphics\make-crops.py $out
```

What the list encodes:

- **`live` first and last, `1x` twice.** The repeated conditions are the control: their difference in the crops
  (clouds drift, a vehicle moves) and in the frame stats is the noise floor. A variant difference smaller than
  that is not a finding. Report n per condition (1, except the controls at 2).
- **Same mission, same position.** `-Mission t01` boots straight in; nobody touches the controls, so the car sits
  at the spawn point. `frame_stats.py` needs `I76_TELEMETRY=1`, which the harness's default "all" set carries
  (with `I76_FAR_CLIP=1800`). Its "motionless" figure means nothing for a parked car; read fps, dt mean / sd / p99.
- **Pass line for cost:** dt mean 8.33-8.35 ms, sd under 0.2 ms, p99 under 9 ms = holds 120. Because the refresh
  request paces the game, a passing variant shows no headroom in dt; the `nvidia-smi` utilisation is the headroom
  figure (one sample, coarse - if two candidates are close, repeat them with `-Hold 30` and a looped query).
- **After each run** read the proxy log lines the harness prints: `glide-refresh` present, no `CRASH`. Check the
  rectangle `capture-frame.ps1` printed: 2304x1440 at (568, 0). Anything else is R1, and that variant's shot is
  not comparable.
- A parked car measures a static scene. If a variant passes here, one driven run (`-Hold 60`, drive by hand, or
  the cockpit-vs-chase comparison of R3) before it is called good.

**Crop list** - set the four rectangles in `tools\graphics\crops.json` once, on the `1x` shot (the shipped numbers
are placeholders), then leave the file alone for every variant:

| crop | what to put in it | what it shows |
|---|---|---|
| `terrain-edge` | the far terrain silhouette against the sky, near the 1800 m limit | sub-pixel triangle shimmer, the supersampling gain, filter ringing against the sky |
| `thin-pole` | a thin pole, fence or sign near the spawn (a colour-keyed texture if one is in view) | MSAA vs supersampling: MSAA cannot touch a cut-out edge |
| `hud-text` | HUD or cockpit lettering | R4: expected unchanged; halos from lanczos/bicubic show here first |
| `texture-near` | road or ground texture a few metres ahead of the car | texture filter (`live-tmu-appdriven`), mip sharpness, blur from the downscale |

`make-crops.py` writes each crop per variant and a 4x nearest-neighbour sheet per crop (no smoothing added by the
comparison), and prints a crude edge-energy number per crop; judge with the eye, at 100 % on the game's own panel.
Stills cannot show crawl: for the two or three finalists, drive the same stretch on each and watch the horizon band
and the road centre line.

**Deliver:** the table of fps / dt / GPU per condition, the four sheets, the R1/R3/R5 observations, and a pick.
Promotion to the live sandbox conf (and later the portable install) is a separate, announced step: edit
`game\dgVoodoo.conf`, add the comment there, mirror it in lab `docs\dgVoodoo.conf.reference` and
`docs\CONFIG-OPTIONS.md` section 1, then rerun `make-variants.py`.

## References

- lab `game\dgVoodoo.conf` (live), `docs\CONFIG-OPTIONS.md`, `docs\dgVoodoo.conf.reference`,
  `autotest\proxy-run.ps1`, `autotest\lib\maplib.ps1`, `tools\graphics\`.
- i76-map `subsystems\renderer.md`; this repo `docs\DRAW-DISTANCE.md`, `docs\FARCLIP-CAMERA-CRASH.md`,
  `docs\FPS-120.md`, `docs\HD-TEXTURES-RESEARCH.md`, `tools\telemetry\frame_stats.py`.
- dgVoodoo ReadmeGeneral (dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/, fetched 2026-10-02): resolution forms
  (static `WxH[, Hz]`, `unforced`, `2x`/`3x` integer multiples of the app resolution, `max`, `max_isf`, `desktop`),
  the resampling filter list, "forced MSAA is global", the 8K texture limit. The integer forms (`2x`) scale the
  app's 4:3 640x480 and would change the frame aspect, so the variants use explicit 16:10 sizes. The Glide readme
  URL returns 404; the `[Glide]` key list was taken from the live conf and the CPL-written conf in
  `%APPDATA%\dgVoodoo\dgVoodoo.conf`.
- ZGLIDE import census: `pefile` on `game\ZGLIDE.DLL`, 39 imports from `glide2x.dll`, 2026-10-02.

## Measured 2026-10-03 on the FIXED config (the earlier matrix was void)

The first capture matrix (2026-10-02) showed identical frames for every variant because dgVoodoo was rejecting the
sandbox conf and running a 2020 global file (lab docs/DGVOODOO-CONF-REJECTED.md). Everything in this document about
"the sandbox already supersamples 1.46x with 8x MSAA" described a file that was not in effect: the owner had been
playing 1920x1440 internal with no antialiasing. With the fixed conf (fake fullscreen, 4:3 picture 1920x1440 on the
3440x1440 panel) the variants differ as expected. t01, car frozen at one spot, `I76_GLIDE_REFRESH=120`, n = 1 each
(the current setting and 1x were run twice: same numbers), `tools\graphics\run-matrix2.ps1`:

| internal resolution | MSAA | downscale | fps | dt sd (ms) | GPU load | GPU memory |
|---|---|---|---|---|---|---|
| 1920x1440 (1x) | off | bilinear | 120.1 | 0.08 | 14 % | 986 MiB |
| 1920x1440 (1x) | 8x | bilinear | 120.1 | 0.05 | 13 % | 1271 MiB |
| 2880x2160 (1.5x) | 4x | bilinear | 120.0 | 0.66 (p99 11.2) | 20 % | 1329 MiB |
| 3840x2880 (2x) | off | bilinear | 120.1 | 0.08 | 28 % | 1140 MiB |
| **3840x2880 (2x)** | **4x** | **bilinear** | **120.1** | **0.06** | **28-37 %** | **1666 MiB** |
| 3840x2880 (2x) | 4x | bicubic / lanczos-3 | 120.1 / 120.0 | 0.18 / 0.20 | 37 % | 1666 MiB |
| 3840x2880 (2x) | 8x | bilinear | **92.7** | 1.26 | 47 % | 2257 MiB |
| 5760x4320 (3x) | off | bilinear | 120.1 | 1.02 (p99 9.8) | 45 % | 1377 MiB |
| 5760x4320 (3x) | 4x | bilinear / lanczos-3 | **90.1** | 0.09 | 56 % | 2572 MiB |
| 3840x2880 (2x), `TMUFiltering = appdriven` | 4x | bilinear | 120.1 | 0.03 | 25 % | 1666 MiB |

Reading (crops in lab `captures\graphics\try\cmp-matrix2.png`): 1x without AA shows the stair-stepped silhouettes
the owner has been looking at; any MSAA level removes them; 2x adds texture and distant-object detail (road signs,
terrain shading) on top; 3x is not visibly better than 2x in these crops and costs the 120. **Pick: 2x internal +
4x MSAA + bilinear** (an exact 2x2 box at 2x), which is the sandbox conf now. 2x + 8x MSAA and 3x + 4x MSAA fall to
~90 fps on the GTX 1080 Ti and are out for a 120 Hz preset. Not yet judged by eye in motion.
