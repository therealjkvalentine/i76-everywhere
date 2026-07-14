> **STATUS: PARKED on the Mac.** The pipeline/tools work, but true-HD needs an OpenGLide-HD renderer switch away from the software path. A full pack exists on the Windows box. See [README.md](README.md).

# Interstate '76 HD texture pack - research & working pipeline (2026-07-04)

Verdict: **an asset-swap texture pack is fully feasible today, no engine hacks needed.** The
formats are cracked, round-trip tooling exists in [`../tools/`](../tools/), and the game's own
loose-file override mechanism (`ADDON/`) injects replacements without touching `I76.ZFS` -
proven in-game (magenta-striped dashboard test, screenshot-confirmed in the running sim).
True *higher-resolution* textures (beyond the originals' dimensions) need renderer-level work -
see "Ceilings" and "For future research".

## The asset landscape (GOG I76 Gold)

- **`I76.ZFS`** - 55 MB, "ZFSF" v1 archive, 6,116 files. Per-entry LZO1X/LZO1Y compression
  (types 2/4; 493 files stored raw). Extractor: `tools/zfs_extract.py` (needs `brew install lzo`;
  extracted all 6,116 files, zero failures, WAV/PCX spot-validated).
- **Formats** (decoders in `tools/i76img.py`, layouts verified byte-level; matches Open76):
  - `.ACT` - 256x3 RGB palette (67 in the archive, one per world/time-of-day, e.g. `t01.act`).
  - `.MAP` - `u32 w, u32 h`, then w*h 8-bit palette indices. `0xFF` = transparent.
  - `.CBK` - VQM codebook: `u32 count`, then count x 16-byte blocks (4x4 palette indices).
  - `.VQM` - `u32 w, u32 h, char[12] cbkName, u32 unk(=256)`, then u16 stream, one per 4x4
    block L-to-R/T-to-B: MSB set = low byte is a solid palette index; MSB clear = codebook
    block id.
  - `.PIX` - *text* manifest: count, then `NAME.vqm offset length` lines into the matching `.PAK`.
  - `.PAK` - concatenation of the `.PIX`-listed VQMs.
  - `.M16` - **CRACKED (2026-07-09, on the Windows box)**: the *hardware-renderer* texture
    format (every `*6.pak` set, e.g. `pirana16.pak` - what `-glide` mode loads; the `*m.pak`
    VQMs are the software renderer's). Layout:
    `u32 w | u32 h|flags<<24 | u8[w*h] indices (row-major, 0xFF = transparent) |
    u32 paletteCount | u16[paletteCount] RGB565 LE` - a per-tile LOCAL 16-bit palette
    (max 255 entries; 0xFF reserved). Solved by cross-checking `leprcn16` against the
    `leprcn1m` VQM ground truth: avg channel diff 7.75 = exactly 565 quantization. The
    mysterious "514 extra bytes" = u32 count(255) + 255*u16 palette. Decoder + lossless
    round-trip encoder now in `tools/i76img.py` (`decode_m16`/`encode_m16`).
    Per-tile palettes mean M16 replacements have FULL color freedom (no level-.ACT
    quantization) - strictly richer than what VQM repaints can carry.
- **Cockpit/dashboard art** = `zdash101..601` (day, VQM tiles in PAK/PIX, 256x128 each, codebook
  `vpit.cbk`) + `zdash106..606` (night, M16). Menu shell = loose 8-bit BMPs in `SP256/`
  (trivially editable). Loading screens = 640x480 PCX.

## Observed: night-mission palette mismatch (2026-07-12, Mac software path)

Installing the built pack on the Mac made **night missions (e.g. Mission 6 — the Spanner's Cafe
start) come out color-shifted**, while every day world looked correct. Root cause is the
VQM-vs-M16 palette difference above:

- The pack ships **night only as software VQM** (`nightm.pak`/`nightm.pix`) — no Glide `night6.pak`.
- **VQM is palette-indexed against the level's own 8-bit `.ACT`** (no per-tile palette). The pack's
  night VQM was quantized against the wrong `.ACT`, so on the software renderer the indices resolve
  to the wrong colors — *only* at night (day worlds use `tt0Nm.pak`, which matched, so they're fine).
- Stock `ADDON/` shipped **no** night files, so this is entirely a pack artifact, not a game bug —
  and it's the exact risk this doc's "night M16 not fully decoded" note warned about.

**Fix (shipped):** exclude the night VQM from the Mac install so night falls back to the correct
stock textures inside `I76.ZFS`; day worlds keep the HD upgrade. `setup-mac-hd-textures.sh` now
stashes `nightm.pak`/`.pix` into `ADDON/.night-hd-disabled/` on install (reversible — `mv` them back
to A/B). The real cure is to **re-quantize the night VQM against the night level's `.ACT`** (or ship
night as M16 for the Glide path, where per-tile palettes remove the constraint) — a texture-lab job
on the Windows box, not a Mac-side fix.

## The injection path: ADDON/ loose-file override

The engine's virtual filesystem checks **loose files before the ZFS** - game dir specials
(`MISSIONS/`, `miss8/` for .msn/.ter) and **`ADDON/` for everything else**. GOG itself ships
`ADDON/i2ayj_13.map` + `.vcf` overrides, and Open76 reimplements the same lookup. Confirmed
in-game: replacement `zdash*.pak/.pix` + private `.cbk` files dropped in `ADDON/` visibly
replaced the lower dashboard panel in the running sim.

Practical notes:
- The dash is addressed via the PAK+PIX pair, so override the **pair**, not individual VQMs.
- VQM headers name their codebook file, so replacements can ship **private codebooks**
  (e.g. `HDT1.CBK`) - never modify shared `vpit.cbk` etc.
- Round-trip is **lossless** when unique 4x4 blocks fit the codebook (dash tiles: ~1,000 of
  4,096): decode -> re-encode -> decode compared 0 differing pixels of 32,768.

## Tooling (all in ../tools/)

```sh
# extract everything (or filter by substring)
python3 zfs_extract.py I76.ZFS out/            # needs: brew install lzo
# decode to PNG (map/vqm/pak; palette = the level's .act)
python3 i76img.py decode out/zdash101.pak out/t01.act dash.png --cbk-dir out
# rebuild a pak from edited PNGs with a private codebook
python3 i76img.py makepak ADDON/zdash101 out/t01.act HDT1.CBK \
    tile1.png ZDASH101.vqm tile2.png ZDASH102.vqm
```

AI enhancement demo: Real-ESRGAN (`realesrgan-ncnn-vulkan`, macOS arm64 binary, runs fine)
4x-upscaled a 256x128 dash tile to 1024x512 in ~1 s. The general-purpose model smudges tiny
gauge numerals - a UI-tuned model or SD img2img with control would do better. For same-res
enhancement (the only thing the engine can display today), the workflow is upscale 4x -> retouch
-> downsample to original size -> `makepak` (quantizes back to the level palette).

## Ceilings (why this is "enhanced", not "HD", today)

1. **Dimensions are engine-fixed.** The 3D sim renders at high resolution (dgVoodoo `2x` =
   1280x960+), but texture *files* keep their original dimensions - the VQM/MAP loaders and the
   Glide texture budget (2MB TMU, 256x256 max per 3dfx spec) assume them. Same-size repaints
   only.
2. **8-bit palettes.** Everything quantizes to the level's 256-color `.ACT`. Subtle gradients
   band; art direction must respect the palette.
3. The `-gdi` software renderer additionally point-samples (no filtering) - enhanced art still
   helps, but the big visual win is in `-glide` hybrid mode.

## Prior-art sweep (2026-07-09, deep web search)

- **No I76 texture pack has ever been released** (VOGONS/ModDB/GOG forums/PCGW/interstate76.com
  all checked; closest = CahootsMalone's checkerboard terrain hex-poke proof and DIVER's
  16-bit road-color bugfix). Whatever ships from this lab is a first.
- **Wrapper-level replacement confirmed dead**: only Glidos does Glide texture override and
  it's DOS-titles-only; dgVoodoo texture injection was requested on VOGONS (t=66553), called
  feasible by Dege, never built (checked through 2.87.3, June 2026).
- **Open76** (r1sc) dead upstream since 2020 but fork `rob518183/Open76` active through
  June 2026; **Roanish/i76 "Vigilante '76"** (C, SDL2+Vulkan, Ghidra-based) active June 2026
  and explicitly aims at upscaled textures someday - its `docs/REVERSING.md` documents the
  engine's `texture_load()`/`vqm_decode()`. Blender GEO importer: `chasseyblue/i76-geo-importer`.
- **Vehicle texture chain** (matches what we decoded here): VCF -> VDF + VTF (paint scheme;
  VTFC chunk = 78 TMTs + 13 MAPs) -> TMT lists per-damage-state texture names -> pixels in
  `<car><scheme>{m,6}.pak`. Melee "variant" pick = paint scheme = which pak set loads.
- Taurus's car confirmed: **1969 Jefferson Sovereign "Eloise"** (`vjsovrn1.vcf` ->
  `sovergn1.vtf` -> `sovern1m/16` paks).

## For future research (true HD)

- **OpenGLide texture-replacement fork** - the Tier-2 unlock. OpenGLide (open source, bundled
  by GOG, works on this stack) already hashes textures in its TexDB; adding GlideN64-style
  hash->PNG substitution at `grTexDownloadMipMap` time (~few hundred lines) would allow
  arbitrary-resolution replacements regardless of file formats. dgVoodoo's Glide has **no**
  dump/replace facility (checked 2.78.2 and 2.87.3 confs), and its DirectX resource replacement
  doesn't apply to Glide.
- **Decode `.M16` fully** (night dashes, sky art) - the 514-byte trailer per 256x128 tile is
  probably a row table or embedded 16-bit palette; That Tony's blog
  (hackingonspace.blogspot.com) is the likely reference.
- **Which palette applies where**: dash tiles decode plausibly with any world `.act` (shared
  index ranges); a proper pack should decode against the palette of each world (`t01`/`m02`/...)
  and ship per-world variants only if they actually differ.
- **Open76** (github.com/r1sc/Open76) is the eventual no-ceiling home (arbitrary textures,
  modern renderer) - but its car physics "does not work yet", and the physics *is* I76.
- Distribution: a pack is just an `ADDON/` folder of pak/pix/cbk/map files + these tools to
  build it from PNGs - OpenRA-style, no copyrighted originals in the repo.