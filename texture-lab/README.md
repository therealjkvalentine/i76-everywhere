# texture-lab - experiment with I76 texture enhancement

Workspace for editing Interstate '76 art and seeing it in-game. Everything here except this
README is gitignored (decoded game art is copyrighted - same rule as `game-data/`).
Pipeline background: [../docs/HD-TEXTURES-RESEARCH.md](../docs/HD-TEXTURES-RESEARCH.md).

## Layout

- `src/` - decoded original PNGs to start from, plus the level palette
  (`t01.act`, and `_palette-t01.png` to eyeball it). `zdash101.*.png` are the two 256x128
  tiles of the training vehicle's lower dashboard - the easiest art to verify in-game.
- `enhanced/` - put your edited PNGs here (same filenames, same dimensions).
- `build/` - generated pak/pix/cbk output.

## Workflow

```sh
cd games/interstate-76
GAME=~/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app/Contents/SharedSupport/prefix/"drive_c/GOG Games/Interstate 76"

# 1. (once) extract the archive somewhere and decode more art
python3 tools/zfs_extract.py "$GAME/I76.ZFS" /tmp/i76-assets
python3 tools/i76img.py decode /tmp/i76-assets/zdash201.pak /tmp/i76-assets/t01.act \
        texture-lab/src/zdash201.png --cbk-dir /tmp/i76-assets

# 2. edit PNGs (any editor / AI tool) -> save to texture-lab/enhanced/ at the SAME size.
#    Colors are re-quantized to the level's 256-color palette on encode - check
#    src/_palette-t01.png; wild new hues will snap to the nearest palette entry.
#    Keep transparent pixels transparent (they become palette index 0xFF).

# 3. rebuild the pak (tile order and .vqm names must match the original .pix manifest)
python3 tools/i76img.py makepak texture-lab/build/zdash101 texture-lab/src/t01.act HDT1.CBK \
    texture-lab/enhanced/zdash101.zdash101.png ZDASH101.vqm \
    texture-lab/enhanced/zdash101.zdash102.png ZDASH102.vqm

# 4. install (loose-file override - no repacking) and restart the game
cp texture-lab/build/zdash101.pak texture-lab/build/zdash101.pix texture-lab/build/hdt1.cbk "$GAME/ADDON/"
./play.sh

# undo: delete those files from "$GAME/ADDON/"
```

Menu-shell art is even easier: `SP256/*.BMP` in the game folder are plain 8-bit BMPs -
edit in place (keep 8-bit indexed format), no tools needed.

Upscaler used for the first demo: realesrgan-ncnn-vulkan (free, Apple Silicon) - general
model crisps edges but speckles tiny gauge text; try `realesrgan-x4plus-anime`, chaiNNer
model zoo, or SD img2img at low denoise for better results. Enhance at 4x, then downsample
back to the original size (the engine can't take bigger files - see the research doc).

## The blend recipe (2026-07-10, FINAL): 47% original / 31% ESRGAN / 22% sharpened

Pure ESRGAN softens fine detail — worst case, it *erases* the radar CRT range
rings (reads them as noise). The game-wide fix is a per-tile blend, dialled in
with the interactive tuner (`build_tuner.py`) and shipped in the pack:

- **47% original** — keeps the faithful detail (range rings, gauge text, panel grit)
- **31% ESRGAN** — the cleanup (removes dither, smooths metal gradients)
- **22% sharpened** — ESRGAN + *luminance-only* unsharp (crisp edges with **no**
  blue/colour fringing on saturated edges like the hazard stripes / red HUD bars).
  Sharpen = a **box-blur luminance unsharp, amount 116%, radius 0.8** — the exact
  math `build_tuner.py`'s slider runs, ported verbatim into `reencode_all.py` so the
  game-wide bake equals what was approved in the tuner.

*(Earlier drafts used 40/35/25 with a percent-55 Gaussian unsharp; superseded.)*

`reencode_all.py` applies this when given the staging dir as a 5th arg:
```sh
python reencode_all.py manifest.json ENHANCED/ ASSETS/ OUT/ STAGING/   # blended
python reencode_all.py manifest.json ENHANCED/ ASSETS/ OUT/            # pure ESRGAN
```
Weights + sharpen live in constants at the top of `reencode_all.py`. The tuner
(`build_tuner.py` -> a self-contained HTML page with live sliders) is how you
re-dial them; it embeds copyrighted game art so its OUTPUT is never committed.

## Vehicle skins on Windows (2026-07-09): the M16/hardware path — WORKING

Proven in-game on the Windows laptop (`-glide` + dgVoodoo): **the hardware renderer loads
the `*6.pak` M16 texture sets, not the VQM `*m.pak` ones** — and ADDON/ overrides them.
Verified with a magenta-marker probe on the melee Leprechaun (paint scheme 3 = the GTAZ
variant; the scheme number in the pak name = the VCF's paint scheme, so probe the right one).

- `enhance_cars_m16.py` — Real-ESRGAN (x4plus-anime) same-res enhancement of an M16 pak;
  per-tile RGB565 palettes mean **no level-palette quantization** (richer than VQM repaints).
- `enhance_cars.py` — same pipeline for the VQM/software sets (Mac DxWnd mode uses these).
- `make_marker.py` — magenta-marker probe pak builder (plumbing verification).
- M16 decode/encode (lossless round-trip) lives in `../tools/i76img.py`.
- Shipped first: `pirana16` (Groove/Jade's Piranha) + `sovern16` (Taurus's "Eloise"
  Sovereign) built to `cars-build/final/` and installed to the game's `ADDON/`.
- Windows asset extraction: `zfs_extract.py` now takes `LZO2_DLL` env var (conda-forge
  `lzo` package ships `Library/bin/lzo2.dll`).
