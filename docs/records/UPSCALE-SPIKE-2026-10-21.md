# AI-upscaling menus and fonts: feasibility spike (2026-10-21)

Owner, 2026-10-21: *"another possible future epic is ai upscaling menus and fonts; could try in parallel but don't make
a mess."* This is a **lab-only** spike. Nothing went into any player copy (daily driver, golden, release candidate, LAN, twin-driver),
nothing was deployed, no game file or menu table was edited, and **no game was booted**. Section 6 explains why no boot
was needed. Tags: **[measured]** = produced on this PC in this spike; **[prior]** = from the cited record; **[by eye]** =
my reading of the images, for the owner to overrule.

This spike builds on prior work and does not replace it: `docs/records/MENU-REBUILD-DESIGN.md` (2026-10-02, options A-D,
"A3 HD mirror" as the epic) and `docs/records/MENU-HD-ART.md` (the `tools/menu-hd/build_hd.py` pipeline, Real-ESRGAN
already set up, the "GAN rewrites small text" finding). Those two documents remain the design. This spike adds new
measurements, the demo, and the verdict.

**Verdict: "not without a shell patch".** dgVoodoo already does about as well as a scaler can with 640x480 pixels. A
sharper menu needs our own code that draws at output resolution, at the drawing layer between the game and the screen.
That code would be a proxy or hook, not an edit of the menu tables. The art is worth it in places, and the fonts are
cheaper than expected (section 3.3). As an epic it is the **A3 stage** of MENU-REBUILD-DESIGN, with the Esc menu as
its smallest first target.

## 1. Inventory: what the menus and fonts are at runtime

The brief assumed PCX / MAP files in I76.ZFS and ADDON. The menus are mostly somewhere else:

| thing | where it lives | format | who draws it, at what size |
|---|---|---|---|
| Shell screens: main menu, garage, inventory, mission grid, melee/net forms, notepad menus, save/load | `DATABASE.MW2`: 32 backgrounds 0x01-0x20, 32 sprite tables 0x21-0x40, 7 bitmap fonts 0x41-0x47 [prior: MENU-REBUILD-DESIGN s.2] | LZSS'd 8-bit PCX (640x480), RLE sprites with no palette of their own, "1." bitmap fonts | `i76shell.dll` draws 8-bit pixels into two 640x480 heap buffers and blits them to the exe's DirectDraw surface with the literal rect {0,0,640,480} (`DDraw_Present` 0x10021d90) [prior] |
| The same for **Nitro** | `database.tvf` (9.38 MB): **same container**, 76 items vs Gold's 83 [measured: `mw2db.py list`]; `nitshell.dll` | same | same design, other addresses |
| Shell handwriting text (names, parts, values) | bitmap fonts 0x42 / 0x44 / 0x45 (+ 0x46 anti-aliased, 0x47 caption face, 0x43 shadowed, 0x41 Japanese) | 10-15 px glyph cells | `Display_DrawText` 0x100395b0 (225 call sites) [prior] |
| In-mission **Esc menu** and mission-over menu | `i76.exe` (`shell_BeginInGameMenu` 0x4953e0, draw 0x496870). Page art = `escape.pak` in I76.ZFS (`3*.vqm` 8-bit + `6*.vqm` 16-bit, 7 pages + x1) [measured: pix listing] | VQM | GDI text into a DIB, then `renderer_BlitBitmapSW` 0x47aa50 into the **640x480 Glide LFB** [prior: lab WIDESCREEN-2D.md] |
| **Lee_____.ttf** | game folder (Gold and Nitro, same md5 `ced1683b`) | TrueType (vector) | registered by i76.exe 0x4769e0 (private since `I76_FONT_PRIVATE`). `font_CreateFont` 0x4768f0 makes 7 HFONTs for the Esc menu (Lee + Arial Bold, descriptor table per language slot 0x654b80) and one for `shell_ToggleNotepad` 0x45e2b0. **The shell DLL does not use it** |
| `base6x7.fnt` / `base6x74.fnt` / `base6x76.fnt` | game folder | "1." bitmap fonts, 6x7-class cells | in-mission HUD text (mission messages, counters). Per-language choice in WinMain 0x402b30 on 0x654b80 -> `font_GetHudFontDesc` 0x4998f0 [measured: Ghidra export]. Drawn by `font_DrawTextWindows` 0x49b430 / `font_DrawTextFields` 0x49bee0 into the LFB [prior] |
| Cursor | `Pencil.cur` / `Nopencil.cur` (shell, `LoadCursorFromFileA`); the shell also draws its own pencil sprite; u32x has a `u32xVptr` arrow window | .cur / sprite | OS cursor or a 640x480 sprite |
| Loading screens | `loadscr.pcx`, `loadgame.pcx`, `pNNload.pcx` / `b01load.pcx` (ZFS) | 640x480 PCX | exe, through the same 640x480 path |
| `SP256\*.BMP` (52 files) | game folder | 8-bit BMP | the launcher (`Splash.exe`), **not** the game's menus (HD-TEXTURES-RESEARCH.md says "menu shell"; that line is wrong) |

### 1.1 How dgVoodoo scales them today, measured

Conf in the exp-p19 copy, which matches the daily driver's wide conf (`dgVoodoo.conf` = `dgVoodoo.wide.conf`): borderless window
3440x1440, `ScalingMode = stretched_ar`, `[GeneralExt] Resampling = bilinear`, `[Glide] Resolution = 6880x2880` +
`Antialiasing = 4x`, `[DirectX] Resolution = 1680x1050`.

Captures were not possible on a private desktop: the lab records `DIFFICULTY-OPTION`, `NITRO-BASE` and `RC-DRAW-FPS`
show they come back black. The proxy's frame dump (`I76_TEX_CENSUS=2`, grLfbReadRegion) covers only the Glide frame, not the
DDraw shell. So I used **existing console captures made under the current conf** and fitted the pipeline to them
offline. The method: sample each capture at the centres of the 640x480 source pixels to recover the source, re-scale it
with candidate models, and compare (`lab tools/upscale-spike/scaler_model.py`, result `evidence/scaler-model.json`)
[measured]:

| path | capture | best model | PSNR (next best) |
|---|---|---|---|
| Esc menu (Glide LFB) | `ss-measure-20261012/escmenu-w2xar.png` (the daily-driver conf) | 640x480 **point-sampled** to the 6880x2880 Glide target (5.375x horizontal, 3x vertical: the LFB covers the whole 21:9 frame), then halved | **53.4 dB** (plain nearest 35, bilinear 27) |
| Shell (DDraw) | `mp-menu-20261019/a-host1.png` | 640x480 **nearest to 1680x1050**, then **bilinear 1.37x** to the 2304x1440 16:10 picture at x 568..2871 | **33.9 dB** (best of 81 rect / intermediate-size / filter combinations; single-step bilinear 26) |

So the blur is not a bad filter. dgVoodoo already does "sharp bilinear" on the shell (integer-ish nearest prescale, then a short
bilinear step), and pure nearest on the Esc page. What looks blurry is **640x480 information shown at 3-5.4x**, plus the
non-integer 3.6x horizontal step of the 16:10 menu picture that the owner chose (CURSOR-FIX-ON-18 s.6). The recovered
Esc frame shows the GDI text as **1-px aliased glyphs** (`evidence/esc-recovered-crop-nn3.png`): Lee is rasterised at
640x480, without antialiasing, before any scaling.

## 2. Routes, with costs

| route | what has to change | risk | size | Gold / Nitro |
|---|---|---|---|---|
| **(a) bigger bitmaps through dgVoodoo** | Impossible as stated. The shell's buffers, present rect and every layout constant are 640x480 immediates (`VDriver_Init` 0x10037a50, `DDraw_Present`, `Button_Init` constants, the static widget tables) [prior: MENU-REBUILD-DESIGN s.3 B]. dgVoodoo has **no texture-replacement path** at all, and the DDraw shell hands it a locked 8-bit surface, not textures. The Esc page goes through the 640x480 LFB. What does work: **same-size** art (B-lite repack, `build_hd.py blite`, built 2026-10-02, untested in play) | none for same-size; "2x internal resolution" = rewrite ~700 functions + tables (XL) | same-size S..M; higher-res XL | MW2 / TVF share the container: the repacker carries over, item ids differ |
| **(b) dgVoodoo / renderer level** | Config only. Already on: 2x2 supersample + 4x MSAA on the 3D (does not touch LFB / 2D), point prescale + bilinear for the shell. Options: `Resampling = lanczos-3` / `pointsampled` (global: these also change the Glide 2x downscale, so the 3D AA suffers), `[DirectX] Resolution = 1920x1440` (integer 3x, 4:3: the narrower menu the owner turned down on 2026-10-17). Simulated in `evidence/route-b-dgvoodoo-keys-garage-1to1.png`: they trade softness for stair-steps, the same pixels either way [by eye] | low (conf; the R2 "key in wrong section" rule) | S (minutes) | identical (same conf works for nitro.exe) |
| **(c) fonts** | **Lee (Esc menu, notepad):** to rasterise at output size, the exe's GDI text must be drawn somewhere other than the 640x480 DIB, so this is an **exe** hook, not a shell patch. The Esc menu is the exe's. Options: hook `DrawText`/`TextOut` on the menu DC and record string + rect, then draw at output resolution (= route d). **Shell bitmap fonts:** a bigger `.fnt` / MW2 glyph cell only makes bigger letters, because the target is still the 640x480 buffer. Only a replay at the drawing waist (A3) helps. **New finding:** `Lee_____.ttf` **is the face of the shell's handwriting bitmap fonts 0x42/0x45** (same letterforms; `evidence/lee-ttf-vs-shell-bitmap-fonts-x4.png`) [measured / by eye]. A3 therefore needs no potrace re-trace (MENU-HD-ART step 4): typeset with Lee at native size, fitted to the stock advance widths. **HUD .fnt:** LFB-drawn. Rerouting the glyphs to Glide quads was costed at 14-24 h, odds 35 % [prior: WIDESCREEN-2D] | medium | Esc-text hook M; shell font via A3 (L); HUD text 14-24 h | Lee and `.fnt` files are byte-identical in Nitro; hook addresses need the Nitro map (`xmap.py`, as the nitro-port stages do) |
| **(d) overlay drawn by the proxy at native resolution** | **Esc menu:** the proxy already hooks Glide (`_grBufferSwap`, grLfbReadRegion users). Before the swap it can draw the page as textured quads (an HD page texture + a glyph atlas) on top of the LFB-written page. dgVoodoo rasterises those quads at 6880x2880, so they come out sharp. Needs: the page rect (0x4956e0 already computes it), the strings + rows from the menu's draw (hook the 0x496870 GDI calls), and the selection / hover state. **Shell:** no Glide surface while the shell runs, so it first needs A2 "own the present" (hook `DDraw_Present` 0x10021d90, draw the frame ourselves) and then A3's replay of the ~10 `Display_*` primitives with HD assets | Esc: a second drawer on the frame (it is the u32xVptr / cursor-overlay idea). Glide 2 textures are max 256x256, so the HD page has to be tiled. Shell: A2's coexistence with dgVoodoo is still open [prior] | Esc-menu overlay M (2-4 sittings); shell A2 M + A3 L | the Glide hook carries to Nitro (same ZGLIDE / WIN32 path, the nitro-port stage 4/5 pattern); the shell hooks are per DLL (`i76shell.dll` vs `nitshell.dll`): the A3 work is done twice, or once against a shared waist map |

Every route that adds resolution is code in our proxy (or u32x) at a drawing seam. None of them works by editing a menu data table,
so they avoid the failure that crashed Nitro today.

## 3. The demo [measured]

Lab `captures\upscale-spike-20261021\` (35 MB, git-ignored like all upscaled game art), built by
`lab tools\upscale-spike\demo.py` with the existing `tools\menu-hd\build_hd.py` (palette-aware dedither, then Real-ESRGAN
ncnn-vulkan `realesrgan-x4plus` / `-anime` from `C:\Games\_tools\realesrgan`, plus the classical path). One GPU burst of
~30 s, run while no game process was up. **Tools present but not used:** ComfyUI's venv has torch 2.8 cu126 + spandrel.
Its `upscale_models` folders are empty, so `.pth` models (realesr-general-x4v3, SwinIR, 4x-UltraSharp) are one
download away. Nothing was downloaded or installed.

Every `*-side-by-side-3440x1440.png` shows the **same crop at 1:1 panel pixels** in each column. View them full-screen on
the 3440x1440 panel. The full-frame variants are alongside (`<screen>-A-today`, `-B-...`, `-C-...`).

| screen | source of the 640x480 frame | columns |
|---|---|---|
| main menu | composed from stock DATABASE.MW2: bg 0x1a + OPTIONS / EXIT / TRIP / MELEE frames of 0x3e at their `Button_Init` rects (exact 8-bit) | today (fitted pipeline) / ESRGAN x4plus / x4plus-anime |
| garage (BUILD AND REPAIR FORM with live text) | recovered from console capture `weap\garage6.png` + snapped to palette 0x01 (mean 1.1, p99 13.9 RGB units off) | today / ESRGAN x4plus of the whole frame / classical (not AI) |
| Esc menu | recovered from `escmenu-w2xar.png` (the 53 dB model) | today (the real capture) / ESRGAN x4plus of the LFB page / **route (d) mock**: ESRGAN page with the GDI text removed, plus the 10 GDI strings re-drawn at output resolution with Lee_____.ttf / Arial Bold, fitted to the detected boxes (Lee fits at 14-15 px) |
| Lee font | Lee rasterised at the Esc menu's 640x480 size, no AA | today / ESRGAN x4plus / Lee rasterised at 3x |

What the images show [by eye]:

- **Logo and large display type:** ESRGAN is a real gain (`evidence/mainmenu-logo-1to1-*.png`). Clean edges, and the
  anime model is the flatter and crisper of the two.
- **Handwriting in the garage:** x4plus produces believable pen strokes. Classical is faithful but soft.
- **Small baked labels:** ESRGAN **rewrites words**. "chassis" -> "chaoeis" / "chossis", "indicates" -> "indicatos",
  "is" -> "io", "BALANCE" -> "BALANOE" (`evidence/garage-esrgan-rewrites-small-text-*.png`). On the Esc page "Table No." /
  "No. Guests" / "Date" / "Coffee Tea Milk" turn to near-noise. This repeats the MENU-HD-ART finding on new art. Whole-frame
  AI upscaling of a form is **not shippable**. Labels have to be re-typeset over an upscaled blank.
- **Esc menu text, route (d) mock:** the native Lee raster is the clear winner. It is sharp, keeps the right letterforms, and has no
  invented strokes (`evidence/escmenu-text-1to1-today-ai-native.png`). Caveat: in this mock the "Marge / 05 / 1 / 7/4"
  entries are anti-aliased page art, not GDI text (their darkest pixel is 89-124, against GDI's 0). They stay as AI-upscaled art.

## 4. Lab boot: not done, by the brief's own rule

The brief allows a lab boot only if route (a) or (d) needs no engine change. Route (a) cannot add resolution at all.
Route (d) needs new proxy drawing code. So the spike **stops at the images**. No game was started, no mute was
set (so none to clear), no `I76_SHM_SUFFIX` was used, and no exp-upscale copy was made.

## 5. What would it cost as an epic

| step | gives | size | depends on |
|---|---|---|---|
| 1. **Esc-menu overlay** (proxy, Glide quads before the swap): HD page texture (tiled 256x256) + Lee / Arial glyph atlas at output scale, strings and rects captured from the menu's GDI calls | the in-mission menu at native resolution: the place where the 5.375x horizontal stretch hurts most | M (2-4 sittings), odds ~60 % [estimate] | none beyond the existing Glide hook; Nitro via the address map |
| 2. A2 own-present for the shell | integer / chosen scaling, one pointer map | M | the open DDraw-vs-Glide coexistence test [prior] |
| 3. A3 HD mirror for the shell | upscaled art (ESRGAN for logo / art screens, classical or re-typeset for forms), shell text typeset with Lee at native size | L | 2; an `mw2font` / metrics table (built: `build_hd.py` fonts); per-screen art choice by the owner |
| 4. HUD text as quads | sharp mission messages | 14-24 h, 35 % [prior] | independent |

## 6. First real step

**Step 1 in a lab copy:** a `I76_ESC_HD=1` proxy switch, off by default, that draws only the Esc menu's GDI strings as
quads at output resolution over the stock page. It needs no art pipeline, no shell change, and no table edit. Gate:
`autotest/test-escmenu.ps1` clicks still land, fps is unchanged, Alt+Enter survives, and the 2D dash is unaffected. If that looks right
to the owner, add the HD page texture next, and only then open A2 / A3 for the shell.

## 7. Files

- Lab `tools\upscale-spike\`: `scaler_model.py` (the pipeline fit), `lee_vs_bitmap.py` (Lee vs the shell bitmap fonts),
  `demo.py` (the demo; `--no-gpu` reuses the cached ESRGAN outputs), `route_b.py` (dgVoodoo-key simulation).
- Lab `captures\upscale-spike-20261021\`: 4 side-by-sides + 9 full-frame variants at 3440x1440, `demo.json`,
  `evidence\` (fit json, recovered frames, 1:1 crops, the ESRGAN text-rewrite crops), `work\` (1x inputs, ESRGAN cache).
- Read only: the exp-p19 copy (conf, Lee_____.ttf, I76.ZFS, DATABASE.MW2), exp-nitro-base (database.tvf),
  <re-archive> (mw2db extraction, Ghidra export), existing lab captures.
