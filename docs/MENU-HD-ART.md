# Menu HD art pipeline (stage A3 assets, and the B-lite repack)

2026-10-02. Tool: `tools\menu-hd\build_hd.py`. Design context: `docs\MENU-REBUILD-DESIGN.md` section 4 (A3 "HD
mirror" wants true-colour assets at 3x, keyed by DATABASE.MW2 item id). Format facts: `i76-map\data\FORMATS.md`
section 11. Everything here ran offline: no game run, no download, nothing written into a game folder.

Status tags: **[measured]** = produced and checked on this machine; **[by eye]** = my reading of the contact sheets,
which the owner should overrule; **[proposed]** = not done.

## 1. What is installed (checked 2026-10-02)

| thing | state |
|---|---|
| Python 3.13 (default `python`), also 3.12, 3.8, Anaconda 3.8 | present |
| Pillow 12.3, numpy 2.4, OpenCV 4.13 (no `dnn_superres`: not the contrib build), scipy 1.17, scikit-image 0.26 | present |
| onnxruntime 1.24.4 | present, **CPU provider only** (no CUDA / DirectML) |
| torch, torchvision, realesrgan, basicsr, ncnn (python), waifu2x, xbrz, hqx, potrace, fontTools | missing |
| **`C:\Games\_tools\realesrgan\realesrgan-ncnn-vulkan.exe`** (2022 portable build) | present and working on the GTX 1080 Ti. Models: `realesrgan-x4plus`, `realesrgan-x4plus-anime`, `realesr-animevideov3` x2/x3/x4 |
| ComfyUI at `C:\ComfyUI` and `C:\Users\james\ComfyUI` | present; both `models\upscale_models` folders are empty. Its own Python environment was not inspected |
| Topaz Photo AI / Video AI in `C:\Program Files\Topaz Labs LLC` | present (commercial GUI tools; not used, not scripted) |
| `.onnx` files elsewhere (`.insightface`, `.u2net`) | face / matting models, not upscalers |

`python tools\menu-hd\build_hd.py check` prints the same survey.

So an ML upscaler **is** available locally, and the pipeline uses it as a second variant beside the classical one.

## 2. The pipeline

```
python tools\menu-hd\build_hd.py check
python tools\menu-hd\build_hd.py build   --scales 3 2                       (classical -> out\3x, out\2x)
python tools\menu-hd\build_hd.py build   --scales 3 --kinds bg,sprites --upscaler realesrgan:realesrgan-x4plus --tag realesrgan-x4plus
python tools\menu-hd\build_hd.py contact --variants 3x 3x-realesrgan-x4plus 3x-realesrgan-x4plus-anime
python tools\menu-hd\build_hd.py blite   [--source dedither | hd:<variant>] [--dither none|fs] [--all-indices]
```

Global options go before the subcommand: `--src` (default `..\i76-map\data\out\mw2db`), `--out` (default
`tools\menu-hd\out`, git-ignored), `--i76-map`, `--realesrgan-exe`. `--only 01,1a,3e` limits a run to some items.

Input is the untouched `mw2tool.py extract` output (palettised PNGs + `manifest.json`). Output layout follows the A3
loader sketch in the design doc:

```
out\<scale>x[-tag]\bg\<id>.png              true-colour background, id = MW2 item id as two hex digits (1a.png)
out\<scale>x[-tag]\sprites\<id>\<frame>.png RGBA frame at canvas size x scale
out\<scale>x[-tag]\fonts\<id>.png + .json   glyph sheet + metrics
out\<scale>x[-tag]\manifest.json            keyed by item id ("0x1a"): files, sizes, upscaler, timings, and the md5 of the
                                            source DATABASE.MW2, of each source member, of each extracted PNG, of each output
out\contact\*.png                           before/after sheets
out\blite\DATABASE.MW2 + blite.json + work\ the B-lite repack
```

### Steps, and why

1. **Palette-aware dedither** (`dedither`). The stock art is error-diffused: on the garage form 70% of horizontally
   adjacent pixels in flat paper differ [measured]. Each palette index gets a step size = the distance to the nearest
   other palette colour. A 5x5 average then admits a neighbour only if it lies within 2.2 steps of the centre pixel, and
   the result may move at most one step from the stored colour. Dither partners blend; lettering and rules (many steps
   away) do not. It runs in sRGB space, where the original quantiser diffused its error. Every upscaler gets this
   input: a GAN amplifies dither into texture otherwise.
2. **Upscale** through the pluggable interface (next section).
   - `classical`: Lanczos (8x8 taps) **in linear light**, clamped to the local min/max of the source so it cannot ring;
     then an **edge-directed pass** (a short blur along the edge tangent from the structure tensor, weighted by
     coherence: it removes the diagonal staircase on lettering and outlines and leaves texture alone); then unsharp
     0.35. `--no-edge` and `--sharpen 0` switch the last two off. It invents nothing.
   - `realesrgan:<model>`: the ncnn-vulkan exe in folder mode, x4 then area-filtered down to the exact target in
     linear light (the `animevideov3` family has native x2/x3 weights).
3. **Sprites**: colour and alpha are separate. Transparent pixels (index 255) are filled with the nearest opaque colour
   before scaling, so no filter or model can pull a matte colour into the edge (same result as premultiplied scaling,
   without the edge darkening; the PNG is straight alpha with colour continuing under the edge, so it is safe under
   either blend convention). Alpha: a frame that is one full opaque rectangle keeps a hard rectangle (it must butt
   against the background it replaces); any other shape goes through the mask scaler. Of the 460 frames, 237 are full
   rectangles [measured].
4. **Mask scaler** (`upscale_mask`; fonts and sprite alpha; never an image model). Binary masks: Scale2x/Scale3x (EPX,
   the edge-directed step that joins diagonal pixel chains), a small blur and a threshold on a 4x supersampled grid,
   area-averaged back: a smooth anti-aliased contour through the pixel staircase. Anti-aliased masks: cubic upsample
   and a soft threshold that tightens edges without deleting faint strokes.
5. **Fonts**. Three source kinds were found [measured]:
   - one ink index (0x42, 0x44, 0x45, 0x47, and the 1-bpp Japanese 0x41): binary, EPX + contour;
   - 0x46: 14 ink indices on the grey ramp (palette 1..14): an anti-aliased face, coverage = darkness;
   - 0x43: two ink indices (grey 1 + black 15): a letter with a drop shadow. Emitted as a coloured sheet, each layer
     scaled on its own.
   The sheet is white with alpha = ink (tint it as the shell's colour map would). The `.json` gives, per character
   code, the rect in the sheet, `advance = stock width x scale` and `stock_width`, plus `height = stock height x
   scale`. Every cell has a one-stock-pixel gutter. The stock font member holds a width per glyph and nothing else, so
   any inter-glyph spacing belongs to the shell's text code and is not in these files.

## 3. Plugging in another upscaler

`class Upscaler` in `build_hd.py` is the whole contract: `upscale(imgs, scale)` receives a list of opaque sRGB float
images (already dedithered, sprites already bled) and returns them at exactly `scale` times the size. Alpha, fonts,
naming and the manifest are outside it. Register a factory in `UPSCALERS` and select it with `--upscaler name[:model]`.

- **Another ncnn model** (no code): drop `<name>.param` + `<name>.bin` into `C:\Games\_tools\realesrgan\models\` and run
  `--upscaler realesrgan:<name> --tag <name>`. A different exe: `--realesrgan-exe` or `%I76_REALESRGAN%`.
- **A PyTorch / ONNX model** (SwinIR, `realesr-general-x4v3`, a 1x de-dither model): a ~30-line subclass that tiles,
  runs the session and returns floats. Not written, because nothing to run it with is installed (section 7).

## 4. What was produced (all [measured], one run each, GTX 1080 Ti, wall clock)

| variant | backgrounds (32) | sprites (460 frames) | fonts (7; 9,378 glyphs) | total | size |
|---|---|---|---|---|---|
| `out\3x` classical | 78 s (dedither 16, upscale 54, write 8) | 31 s | 7 s | 116 s | 85 MB |
| `out\2x` classical | 37 s | 18 s | 3 s | 59 s | 46 MB |
| `out\3x-realesrgan-x4plus` | 113 s (model 87) | 78 s (model 62) | from `3x` | 191 s | 117 MB |
| `out\3x-realesrgan-x4plus-anime` | 63 s (model 41) | 40 s (model 25) | from `3x` | 103 s | 71 MB |
| `out\blite` | 32 rewritten | untouched | untouched | 39 s | 7.0 MB database |

31 backgrounds are 1920x1440 at 3x; item 0x11 (408x406) is 1224x1218. Timings are single runs: treat differences under
about 10% as noise.

Contact sheets, in `tools\menu-hd\out\contact\`:

| file | shows |
|---|---|
| `bg_forms_3x.png` | 0x01 garage, 0x04 parts catalog, 0x10 control config, 0x0f Tad's card: stock nearest / classical / x4plus / x4plus-anime |
| `bg_art_3x.png` | 0x06 Fish Shack options, 0x1a title logo, 0x0e mission select, 0x1b choose vehicle: same four columns |
| `sprites_3x_1.png`, `sprites_3x_2.png` | 12 frames on a checker (menu captions, garage panels, widget line art, vehicle art) |
| `fonts_3x.png` | the six 8-bpp fonts typeset from the stock sheet and from the HD sheet + metrics |
| `blite_1x_stock_vs_blite_nearest4x.png` | stock vs B-lite, 640x480 crops enlarged 4x |

## 5. Quality notes [by eye, from the sheets]

- **Classical** is faithful and soft. Lettering keeps its exact stock shapes with the staircase smoothed; the paper
  keeps its mottling. Nothing is invented and nothing is sharper than a good 3x resample can be.
- **Real-ESRGAN x4plus** gives clean, sharp large shapes: the title logo, T.R.I.P. / CHOOSE YOUR VEHICLE display type,
  rules, the wireframe vehicle and widget line art, the OPTIONS / MELEE captions. It also **flattens the paper
  texture** to a smooth gradient, and it **rewrites small text**: on the parts catalog "Mortar" becomes "Morlar" and
  "Grenade" becomes "Orenade", on Tad's card "SERVICE" becomes "SEBVICE", and "Table No." on the Fish Shack pad
  becomes noise. This is the failure the design doc predicted, now seen on our art.
- **x4plus-anime** is the same with harder, flatter edges: best of the three on the logo, worst on photographic
  texture (the Fish Shack table top) and equally wrong on small text.
- Suggested per-screen choice, for the owner to confirm on the panel: x4plus (or anime) for 0x1a, 0x0e, 0x1b and the
  caption sprites 0x3e; classical for the paper forms **until their labels are re-typeset** (section 6), after which
  the ML output becomes usable for the paper and rules underneath.
- **Fonts**: the binary handwriting faces come out as smooth pen strokes with the stock shapes; 0x46 (anti-aliased)
  comes out cleaner than its source. These are scaled bitmaps, not vector fonts: good at 2x-3x, not a substitute for
  the vector re-trace the design doc wants for arbitrary sizes. Stock advance widths are preserved exactly (x scale).
- **Known limits**: (1) a rectangular sprite is upscaled without knowledge of the background it sits on, so paper
  texture may not line up across the seam, most likely with the ML variants; unverified in game. (2) The shell
  recolours text and some sprites through 256-byte colour maps and fades through the palette; true-colour assets need
  the renderer to apply the equivalent tint and fade. (3) 0x41 (Japanese, 8,896 glyphs) is processed but was not
  inspected. (4) Sprite tables are drawn with the palette the extraction assigned (0x40 with 0x1b's, the rest with the
  common one); a table used on a screen with another palette would be coloured wrongly here.

## 6. Text baked into the backgrounds (needs re-typesetting for A3)

Read off all 32 extracted backgrounds. "Baked" = the letters are pixels of the background, not drawn by the shell.

| items | screen | baked text |
|---|---|---|
| 0x01 | Garage: build and repair | title BUILD AND REPAIR FORM, VEHICLE:, PARTS / WEAPONS / SPCL. / DEFENSE side labels, FRONT/RIGHT/LEFT/REAR + armor / chassis, LBS. AVAILABLE, BALANCE, REPAIR ORDER, REPAIR TIME, SELECT REPAIRS, the three red "(C)/(V)/(R) indicates..." lines, total weight, FIELD SALVAGE / DONE / SAVE BOOKMARK buttons |
| 0x02 | Garage: chassis configuration | title, MAKE / MODEL, VARIANT, RENAME, PAINT SCHEME, the same side labels and defense block, PARTS CATALOG / DONE / CANCEL |
| 0x03, 0x1e | Inventory + field salvage | CAR / VAN INVENTORY, FIELD SALVAGE, the category headers (ENGINES, WEAPONS, WHEELS, BRAKES, SPECIALS, SUSPENSIONS) twice, the legend lines, "Click to move parts...", ACCEPT SALVAGE, SAVE BOOKMARK. 0x1e adds a rotated NO FIELD SALVAGE AVAILABLE stamp |
| 0x04 | Parts catalog | **the whole page is text** (every part name and number, about 70 lines of small type): the worst case for a GAN and the clearest case for re-typesetting |
| 0x05 | Auto melee, single player | title, PLAYERS, AREA OF PLAY, WEAPONS, PARTS, the stat labels (0-60 mph ...), MAKE, MODEL, CONFIGURE CHASSIS, ENTER AREA, CANCEL |
| 0x06-0x0c, 0x20 | Joe's Fish Shack pages (options, audio, exit, graphic detail, play options, save, load, modem) | the "Joe's Fish Shack" header, the script page title (Options Menu, Audio Control, Exit Game, Graphic Detail, Play Options, Save Bookmark, Load Bookmark, Modem Setup), DARLA / 13 / 1 / 7/4 handwriting, Table No. / No. Guests / Date, line numbers 1-14, Coffee / Tea / Milk |
| 0x0e | Mission select | **all of it**: T.R.I.P., AUTO MELEE, SINGLE PLAYER, MULTI PLAYER, Mission 1-17, Scenario 1-7, Area 1-10 |
| 0x0f | Tad's Auto Salvage card | card heading, EXIT WITHOUT SAVING CHANGES?, YES, NO, SERVANT CARD, the small print and table headings |
| 0x10 | Control configuration | title, the 42 handwritten action names (ACCELERATE ... TOGGLE REVERSE), CALIBRATE / RESTORE / DONE / CANCEL |
| 0x11 | Stats panel (408x406) | DRIVER, WEAPONS, PARTS, MODEL STATS + five stat labels, MAKE, MODEL, CANCEL / CONFIGURE CHASSIS / DONE |
| 0x12-0x19 | Net / modem / nullmodem / auto-melee entry forms | each title, LOCAL DRIVER, RENAME, GAME NAME or AREA OF PLAY or SCENARIOS, DRIVER, WEAPONS, PARTS, MAKE / MODEL, VARIANT, CONFIGURE CHASSIS, and the form's own buttons (JOIN GAME, BROADCAST GAME, ENTER GAME, SEND, RECEIVE, ENTER AREA, CANCEL), NO. DRIVERS, TEAM PLAY, INVITE ONLY, MAX SCORE, A.I. DRIVERS, A.I. CARS, "Lightest car to win:" |
| 0x1a | Main menu | the logo only (art, not UI text) |
| 0x1b | Choose your vehicle | CHOOSE YOUR VEHICLE over a rendered scene |
| 0x1c | Standings | STANDINGS, DRIVERS / MODEL / DEATHS / KILLS / SCORE, row numbers 1-16, DONE |
| 0x1d | Post-mission salvage and repair | a greyed garage form **with sample values baked in** (PICARD PIRANHA, part names, 600s) under a dialog: SALVAGE AND REPAIR IS NOT AVAILABLE WITH THE SALVAGE MANAGEMENT OPTION OFF., NEXT MISSION, SAVE BOOKMARK |
| 0x1f | Post-mission | YOU ARE UNCONCIOUS (the typo is stock), NEXT MISSION, SAVE BOOKMARK |
| 0x0d | Credits backdrop | none (black) |

So 30 of 32 backgrounds carry UI text; only 0x0d and (arguably) 0x1a do not. Sprite table 0x3e holds the main-menu
captions as images, and the garage tables 0x24 / 0x3c repeat panel headers (ENGINES, CANCEL...).

Re-typesetting is **[proposed]**, not built. The faces look like a Helvetica-style grotesque (forms), a condensed
display face (mission select), an italic serif script (Fish Shack titles) and hand lettering (control names); those
identifications are by eye and must be settled by overlaying candidates on the 3x nearest-neighbour original. Windows
already ships Arial, Arial Bold and Impact, so a first overlay test needs no download.

## 7. B-lite: same size, 8-bit, repacked

`blite` rewrites each background at its stock size on its **original palette**, restricted by default to the indices
that background already uses, then copies the extraction to `out\blite\work\` and repacks it with
`i76-map\data\fmt\mw2tool.py` into `out\blite\DATABASE.MW2`. The repacker and this tool both refuse game folders.

Result [measured]: 6,965,506 bytes (stock 8,204,554), md5 `fed9bbea1107525d5bfe8e2c70f717fe`. Read back through
`mw2db`: the 32 backgrounds decode to exactly the written indices with unchanged palettes, and the 51 other members
are byte-identical to stock. With the default source (dedithered, nearest colour in Lab, no dither) 21% of background
pixels change on average (0.07% to 41%), and neighbour-to-neighbour index changes drop from 44% to 24%. The file is
smaller because flat runs compress.

Limits, stated plainly:

- It adds **no resolution and no colours**. On screen it is the same picture with the dither noise removed, which
  trades grain for faint banding in the paper gradients. Whether that reads as "cleaner" is a matter of taste and has
  **not been looked at in the game**.
- `--source hd:3x-realesrgan-x4plus --dither fs` downsamples an HD variant instead; that carries the ML model's
  rewritten small text into 640x480, so it is only sensible for the art screens.
- Its real use is as the **carrier for hand-edited art**: fix a label, redraw a panel, save the PNG in `work\`, repack.
  Sprites and fonts are left stock so every index still means what the shell expects.
- Not installed anywhere and untested in play. Putting it in a game folder is a deliberate promotion step on the test
  copy (`i76-uncap-lab\game`), never the daily driver.

## 8. Downloads awaiting approval (nothing was downloaded)

Sizes and licences are from memory of the upstream projects, not re-checked online in this session: confirm each
before fetching.

| # | item | why | URL | size (approx.) | licence |
|---|---|---|---|---|---|
| 1 | `realesr-general-x4v3.pth` and `realesr-general-wdn-x4v3.pth` | the design doc's "gentler on dithering" candidate, with a denoise-strength blend; the likeliest to keep paper texture | https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0 | about 5 MB each | BSD-3-Clause |
| 2 | PyTorch for Python 3.13 (CUDA build for the 1080 Ti, or CPU) + `spandrel` | needed to run item 1 and item 3 (they are not ncnn models) | https://pytorch.org/get-started/locally/ , https://pypi.org/project/spandrel/ | about 2.5 GB CUDA or 200 MB CPU; spandrel under 1 MB | BSD-3-Clause; MIT |
| 3 | SwinIR real-world SR x4 (`003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth`) | slower, more faithful alternative for the forms | https://github.com/JingyunLiang/SwinIR/releases/tag/v0.0 | about 65 MB | Apache-2.0 |
| 4 | potrace 1.16 (win64 zip) | vector re-trace of the handwriting fonts (design doc option a) | https://potrace.sourceforge.net/#downloading | under 1 MB | GPL-2.0 |
| 5 | fontTools (`pip install fonttools`) | write the traced outlines as TTF with the stock advance widths | https://pypi.org/project/fonttools/ | about 5 MB | MIT |
| 6 | Arimo (metric-compatible Arial/Helvetica substitute) | only if the re-typeset labels should not depend on Windows' Arial | https://fonts.google.com/specimen/Arimo | under 2 MB | Apache-2.0 |
| 7 | optional: a 1x de-dither community model from OpenModelDB | compare with the built-in palette-aware dedither | https://openmodeldb.info/ | 5-70 MB | varies per model (often CC BY-NC-SA): check before use |

Not requested: waifu2x, xBRZ/hqx binaries, Upscayl, chaiNNer (nothing they add over what is installed); Topaz is
already installed if the owner wants to try a screen by hand.

## 9. Legitimacy

Upscaled derivatives of the game's art are game data. `tools\menu-hd\out\` is git-ignored; the repo carries the
pipeline and this document only, as with `HD-TEXTURES-RESEARCH.md`.

## 10. Next steps [proposed]

1. Owner looks at the five contact sheets on the panel and picks per screen (section 5).
2. If approved, items 1-2 of the download list, then an A/B of `realesr-general-x4v3` on the paper forms.
3. Re-typeset one form (0x04 parts catalog is the hardest and most valuable) over an ML-upscaled blank.
4. Vector re-trace of one handwriting font (0x46) with potrace, fitted to the stock widths.
