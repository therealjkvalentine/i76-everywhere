# Interstate '76 game-data formats: the verified reference

Every file format i76.exe (GOG Gold, md5 9a232dcc2c164648cff20c414c1f9698) reads from its data, decoded to
byte-exact parsers. For each format this page gives what it is, how it is laid out, what the game does with each
field (citing the instruction that reads it), how many of its bytes are accounted for, and what is still open.

- **Parsers:** `data\fmt\`. Every format has `parse -> values -> serialise`.
- **Generated layout tables:** `FORMATS-tables.md`, produced by `gendoc.py` from the parser layouts themselves, so the
  tables cannot drift from the code.
- **Round trip:** `python data\fmt\roundtrip.py` writes `data\roundtrip.json`. The corpus is the 6,116 archive payloads
  (`recon-2026-09-04\recon\formats\zfs_out`) plus the loose files of the pristine sandbox (`sandbox-gog\main\app`).
  Modern wrappers, code, docs and GOG packaging are excluded (list in roundtrip.py).
- **Result:** 6,368 files, 526,400,305 bytes, **0 byte diffs, 0 parse errors**.
- **Deep dives:** FSM.md (mission scripts), VEHICLES.md (car stats). The tracing notes behind every citation are in
  `data\notes\*.md`.

## How coverage is counted

Each byte of each file falls in exactly one class:

- **cited**: a field whose meaning is backed by the consuming instruction in i76.exe (for DATABASE.MW2: in
  i76shell.dll, md5 deb41008321cf018ba33c27bfbbfa074).
- **unused**: the loader provably never reads it; the loader that skips it is cited.
- **typed**: named and typed, but the meaning comes from structure, values or prior art, not from a traced exe reader
  (usually because the consumer is not i76.exe).
- **unknown**: an explicit unknown run.

BWD2 chunk headers count as cited (bwd2_Parse 0x4b3db0 reads every tag and size).

| format | files | bytes | cited | unused | typed | unknown | consumer |
|---|---|---|---|---|---|---|---|
| .smk | 29 | 316,812,876 | 0 | 0 | 100% | 0 | SMACKW32.DLL (RAD Smacker 2; header and frame tables parsed) |
| .pak (+ .pix index) | 1758 + 1758 | 70,716,933 | 96.9% | 3.1% | 0 | 0 | VFS 0x470660; members .geo .vqm .m16 .tmt .map |
| .ter | 80 | 59,703,296 | 100% | 0 | 0 | 0 | tdef ZONE 0x4939d0, samplers 0x493160 / 0x493550 |
| .wav | 508 | 28,011,479 | 100% | 0 | 0 | 0 | snd_LoadSample 0x425130 |
| .m16 | 225 | 8,901,426 | 100% | 0 | 0 | 0 | m16_Acquire 0x471980 |
| DATABASE.MW2 | 1 | 8,204,554 | 84.3% | 0 | 15.7% | 0 | i76shell.dll TMPackDataBaseObj 0x10007fd0 / 0x10008240 / 0x10008320 (shell VAs), section 11 |
| .msn (BWD2) | 80 | 7,830,056 | 78.8% | 21.2% | 0 | 0 | mission_LoadFile 0x4b42b0 |
| .vdf (BWD2) | 48 | 4,172,640 | 12.4% | 87.1% | 0.45% | 0 | vcf_LoadForObject 0x4ad6f0 |
| .tab | 29 | 3,801,088 | 100% | 0 | 0 | 0 | pal_BuildColorLUT 0x42d800 |
| .cbk | 53 | 3,376,084 | 99.99% | 0.01% | 0 | 0 | vqm_Decode 0x44b430 |
| .gpw | 123 | 2,632,051 | 99.98% | 0.02% | 0 | 0 | snd_LoadSample 0x425130 |
| .vqm | 101 | 2,360,824 | 99.98% | 0.02% | 0 | 0 | tex_Acquire 0x4474b0 |
| .lum / .tbl | 35 + 35 | 4,587,520 | 100% | 0 | 0 | 0 | wrld_h_Load 0x4b8a10 |
| .map (image) | 153 | 2,245,810 | 100% | 0 | 0 | 0 | tex_Acquire 0x4474b0 |
| .sdf (BWD2) | 371 | 1,198,686 | 26.8% | 73.2% | 0 | 0 | sdf_LoadForObject 0x4b7ea0 |
| .pcx | 24 | 642,401 | 0 | 0 | 100% | 0 | loading screens (ZSoft PCX; reader not traced) |
| .pcf | 24 | 398,686 | 64.4% | 35.6% | 0 | 0 | pcf_Preload 0x4026c0 |
| .vtf (BWD2) | 117 | 146,016 | 94.8% | 5.2% | 0 | 0 | vtf_h_VTFC 0x4af8f0 |
| .wdf (BWD2) | 70 | 119,980 | 23.4% | 76.6% | 0 | 0 | wheel loaders 0x4ae5e0 / 0x4ae780 |
| .gdf (BWD2) | 43 | 119,967 | 53.8% | 46.2% | 0 | 0 | bwd2_h_WEPN 0x4aeb90 |
| .zix | 1 | 93,873 | 100% | 0 | 0 | 0 | vfs_LoadZix 0x4b23e0 |
| .vcf (BWD2) | 295 | 74,665 | 99.99% | 0.01% | 0 | 0 | vcf_LoadForObject 0x4ad6f0 |
| .act | 67 | 51,456 | 100% | 0 | 0 | 0 | wrld_h_Load 0x4b8a10 |
| .elt | 1 | 34,106 | 100% | 0 | 0 | 0 | elt_Load 0x448010 |
| input .map (text) | 6 | 32,542 | 0 | 0 | 100% | 0 | gamekey.map: input_LoadGameKeys 0x44d460; the others per AGENTS.md |
| .tmt | 104 | 24,584 | 84.8% | 15.2% | 0 | 0 | tmt_Parse 0x44ab90 |
| .fnt | 3 | 24,533 | 0 | 0 | 100% | 0 | fonts (loader not traced) |
| .npt / .hzd / .rtm / .fsi / .dat / .lst | 170 | 45,138 | 100% | 0 | 0 | 0 | text readers, see section 9 |
| .msk | 5 | 9,089 | 99.94% | 0.06% | 0 | 0 | zoom_BuildScreenMask 0x4621e0 |
| .xdf (BWD2) | 23 | 8,924 | 46.4% | 53.6% | 0 | 0 | xdf_Load 0x4b8c40 / 0x4b8d30 |
| .frc | 14 | 7,704 | 0 | 0 | 100% | 0 | i7_sfrce.dll (DirectInput Force Editor files) |
| .geo (loose) | 7 | 3,757 | 85.7% | 14.3% | 0 | 0 | geo_Parse 0x446c90 |
| compnent.cdf (BWD2) | 1 | 3,608 | 95.0% | 5.0% | 0 | 0 | cdf handlers 0x4b0d00 / 0x4b0e70 |
| .def | 4 | 1,685 | 0 | 0 | 100% | 0 | shell DLL (i76car/I76DFLT/I76UVEH/MULTICAR), **shell track** |
| .vsf (BWD2) | 1 | 232 | 96.6% | 3.4% | 0 | 0 | vcf_LoadForObject .vsf branch |
| **all** | **6,368** | **526,400,305** | **37.8%** | **1.6%** | **60.6%** | **0.0%** | |

Excluding the Smacker videos (RAD's codec) and DATABASE.MW2 (the shell's resource database, section 11), the 201 MB
that i76.exe itself parses are **95.3% cited, 4.3% proven unused, 0.4% typed, 0.0% unknown**.

## 1. BWD2: the tagged chunk container (every definition file)

- **File layout:** `'BWD2' u32 8`, then chunks `{char tag[4], u32 size including the 8-byte header, body}`.
- **Groups:** a tag ending in `DEF` (WDEF, TDEF, RDEF, ODEF, LDEF, ADEF) nests its own chunks, `xREV .. EXIT`.
- **The walker:** `bwd2_Parse` 0x4b3db0 matches each tag against a 16-byte table entry
  `{tag, ?, handler, flags}` and calls `handler(chunk header, ctx, end)` (cdecl).
- **What handlers receive:** the chunk **header** (tag at +0, size at +4, body at +8) unless bit 1 of the table's
  first entry is set. In every table here it is clear, so an exe operand `[hdr+N]` is body offset `N-8`.
- **ctx by flags:** 0x800 gives the caller's ctx, 0x1000 the table entry, 0x2000 the file name.
- **Other flag bits:** 0x4 marks a mandatory chunk. 0x20 makes a handler's failure abort the file.
- **Diagnostics:** every error string goes to `dbg_LogStub` 0x42d5d0, a 1-byte `ret`, so bad files fail silently.
- **Revisions:** REV bodies are one u32 revision, checked by 0x4b4610: vcf 3, vsf 2, vtf 2, xdf 4, wdf 5,
  sdf/vdf/gdf 8, cdf 1, msn 2.
- **EXIT:** normally has a 0-byte body. The game-written `ADDON\vehscn.vcf/.vsf` carry an 8-byte body that is a
  second EXIT header; the EXIT handler 0x4b4290 compares only the tag, so it is never read.
- **Shared 100/120-byte part record** (VGEO, GGEO, OGEO, WGEO, XGEO, VCHK; SGEO uses 120):
  name[8], rotation f32[9], position f32[3], parent[8], bbox centre f32[3], radius f32, half extents f32[3], class
  u32, flags u32, with the SDF form adding hit points and 4 class parameters. It is built by `obj_CreateFromRecord`
  0x4b8230 and grouped by `geo_SplitPartGroups` 0x4b7570 / `geo_BuildLodParts` 0x4b75a0. Only the first group of a
  build creates objects; the other groups contribute only their 8-byte geometry name. That is why so many
  geometry-chunk bytes are **unused**.

## 2. .msn / .lvl missions

Top level: `REV WDEF{WREV WRLD EXIT} TDEF{TREV ZMAP ZONE EXIT} RDEF{RREV RSEG* EXIT} ODEF{OREV OBJ* EXIT}
LDEF{LREV OBJ* EXIT} ADEF{AREV FSM EXIT} EXIT`. The walkers are 0x4b89e0 / 0x493910 (table 0x4fae18) / 0x4b8750 /
0x4b7a90 / 0x4b8f40 / 0x4b89b0.

- **WRLD (331 B, wrld_h_Load 0x4b8a10):**
  - Header: CD track (+0), intro/outro movies, then 9 file names: palette, lum, tbl, objectives .npt, sky, scrounge
    .sdf, terrain texture, map screen, horizon .hzd.
  - **Hour of day** (+0x93): selects sky, sun and whether lights show.
  - **8 surface-physics records** (+0x97, 20 B each): grip, rolling drag, bump amplitude, an unused pad, damage rate.
    They are indexed by the terrain surface type (the .ter top 3 bits).
  - **Far clip** (+0x137, 600 in every mission; clamped 100..100000).
  - **Mission title** (+0x13b, read only by the shell picker).
  - Every byte is read.
- **ZMAP (6401 B):** zone count, then an 80×80 i8 grid of terrain tile indices (−1 = none). It is centred in a
  128×128 world grid with a 24-tile border. The index check is signed.
- **ZONE (14 B):** a pad byte (never read) and the .ter name. `addon\` is tried first, then the CD, then the VFS.
- **RSEG:** road type (only `type % 3`: paved, dirt, wash), a count, then left/right edge points. **The y values are
  ignored** and re-snapped to terrain.
- **ODEF OBJ (100 B):**
  - label[8]: the object file stem; bit 7 of each byte is an instance number, and the raw 8 bytes are the entity key
    used by the FSM entity table.
  - A 3×3 rotation and a position whose **y is ignored** (snapped).
  - 36 unused bytes.
  - Class id: 1 car / spawn / regen, 8/9 vehicle, the rest scenery .sdf.
  - Flags (0x10 = player) and team.
- **LDEF OBJ:** fence and tire strings, `0x68 + 12·n` bytes with n post positions.
- **FSM:** the mission script. See FSM.md.
- **Open:** the ODEF team field is copied to obj+0x12, but no team reader has been found yet.

## 3. .sdf scenery

SDFC (70 B): display name, editor class and health are **never read**; hit points come from the SGEO parts. Five
stats go to the entity record; the explosion .xdf and destroy sound are read. SGEO is `u32 n + 6 arrays of n
120-byte parts` (3 LODs × intact/damaged). SCHK holds collision boxes (radius + half extents). LOBJ is lights, SOBJ a
shadow mesh name. Open: no reader for the five SDFC stats has been found at the entity record +0x1c.

## 4. Vehicle chain: .vcf .vdf .wdf .gdf .xdf .vtf .vsf compnent.cdf

Fully covered in VEHICLES.md. Key facts:

- VCFC armour/chassis are copied ×1 into three banks and doubled in single player by 0x463120.
- The spare field + armour + chassis must equal 1600 × size, but only in the multiplayer join check.
- VGEO is 7 LOD × 4 damage rows, and only row 0 transforms are read.
- GDFC holds damage/ammo/fire rate/lifetime/spread. ORDF holds speed, gravity, a damage-type mask and impact effects
  per surface. XDFC holds blast damage and radius.
- compnent.cdf holds power, brake strength and handling coefficients plus masses.
- The engine id resolves through engsnd.dat.

## 5. .ter terrain

- **Layout:** N tiles × 32,768 B, each 128×128 u16, row-major, 5 world units per sample, 640 per tile.
- **Bits 0-11:** height, raw × 0.1 m (bilinear 0x493550, `fmul [0x4be8a8]`).
- **Bit 12:** AI no-go flag (0x4926f0). AI paths avoid flagged samples.
- **Bits 13-15:** surface type 0-7 (0x4927b0). It indexes the WRLD surface records, the skid/turn/dust sounds (table
  0x4bd0d0) and the AI path cost (0x40e9d0). Type 1 is sand, 2 and 6 paved, 5 gravel, the rest dirt (inferred from
  the sound names).
- The loader does not check the file size against the ZMAP count.

## 6. Archive and VFS: I76.ZFS, I76.ZIX, .pak/.pix

- **I76.ZFS:** handled by i76fmt (other session). Directory blocks of 100 × 36-byte entries, payload method in
  `flags & 0xff` (0 stored, 2 LZO1X, 4 LZO1Y).
- **Hybrid repack** (`data\mod\zfspatch.py`): an empty patch reproduces the 55,535,506-byte original exactly.
  Replaced entries are written stored (method 0, legal because the loader returns raw bytes when `flags & 6 == 0`).
- **I76.ZIX** (vfs_LoadZix 0x4b23e0): file count, a volume table, a container table (slot 0 is hard-wired to `addon`,
  and `miss8`/`miss16` are appended), then `index name` lines.
- **.pix** (0x470660): `%d` count, then `%s %d %d` lines (name lowercased, offset, size), qsorted. Each .pak is the
  concatenation of its members.

## 7. Art: .geo .tmt .vqm/.cbk .map .m16 .act .lum .tbl .tab

- **.geo** (geo_Parse 0x446c90):
  - Header: 'OEG.', then an unread word and an unread name, nVerts, nFaces, and an unread zero.
  - Then vertices and normals.
  - Faces: an unread BSP node id, the corner count, flat RGB, the plane (n·x + d = 0), an unread zero, 3 surface
    bytes, texture[13], an unread BSP parent and side, then vrefs {vertex, normal, u, v}.
  - The engine ignores the file's BSP and rebuilds its own at run time (0x45cbe0).
  - The surface bytes select a row/column of the render-mode table at 0x4f71b8: wireframe, textured, luma-shaded,
    perspective-correct, UV wrap, colour key, translucent.
- **.tmt** (tmt_Parse 0x44ab90): texture animation.
  - Dimension count, dimension sizes (last varies fastest), frames per second, flags (auto-animate, looping).
  - Then 8-char frame names; file size = 0x40 + 8 × Π dims.
- **.vqm:** w, h, codebook name[12], an unread word (the authoring tool's `w & ~3`), then u16 per 4×4 block. Bit 15
  set means a solid block (fill with the low byte); otherwise the value indexes a codebook tile. **.cbk** is a u32 n
  (never read, no bounds check) followed by 16-byte tiles.
- **.map:** w, h (bits 29-31 are in-memory flags), then w·h palette indices; 0xFF is the colour key.
- **.m16:** w, h|0x80000000, w·h indices, then u32 n and n × u16 16-bit palette (RGB565 inferred).
- **.act:** 256 × RGB. **.lum:** [level][colour]. **.tbl:** [src][dst] translucency.
- **.tab:** a 65536-entry RGB565 → RGB565 per-mission colour grade, used only at exactly 0x20000 bytes.

## 8. Sound: .wav .gpw

- **.wav:** plain RIFF PCM, used when no .gpw exists.
- **.gpw:** `GAS0` + priority (default 50, +20 for the player's car) + max simultaneous instances + play mode
  (0 one-shot, 1 loop, 2 shared loop) + volume % + random-pitch flag + a frequency the loader overwrites with the
  WAVE rate. Then the RIFF WAVE. `-1` means default (0x421fb0).

## 9. Text manifests (all read by `txt_ReadLine` 0x499110, which swallows blank lines)

| file | reader | grammar and limits |
|---|---|---|
| .hzd | hzd_Load 0x401540 | exactly 16 tokens (horizon strip .map names), 16-byte slots |
| .rtm | road_LoadTextureManifest 0x48e1a0 | up to 30 names over built-in defaults (slots 10/10/5/5), 15 chars |
| .fsi | fsi_LoadFitout 0x4b1a20 | '#' comments; .wdf/.gdf by extension, eng/sus/bra/spc by prefix; skipped by play-option bit 1 |
| .npt | npt_Load 0x45dea0 | ≤ 6 objectives ('(hidden)' prefix hides one), then '(failure)' + ≤ 16 failure lines |
| .pcf | pcf_Preload 0x4026c0 | `<p/t/x/v/a/g> <name>`; trailing numbers are never parsed (written by the engine's own record mode) |
| .elt | elt_Load 0x448010 | `dst/src <map>`, `label <name> x y w h`, '#' comments |
| engsnd.dat | engsnd_Load 0x469b00 | sscanf of 11 fields per non-# line; engine number → component id and sounds |
| I76.ZIX | vfs_LoadZix 0x4b23e0 | section 6 |
| fullres.lst | tex_ApplyFullResFlag 0x471840 | hashed name set (1741 buckets, no string compare) |
| gamekey.map | input_LoadGameKeys 0x44d460 | `ACTION KEY[+KEY]`; the first binding wins |

## 10. Owned by the shell track (read by i76shell.dll, not i76.exe)

i76car.def, I76DFLT.DEF, I76UVEH.def, internet.lst, the MULTICAR.def record fields (the exe passes
0xEB-byte records to shell callback 08 unparsed), save games and `savegame.dir`. I76PLYR.DEF is read by the exe as a
96-byte options block (0x4970f0): +0x40 video mode, +0x47 terrain LOD, +0x58 play flags, +0x5c difficulty
(inferred).

## 11. DATABASE.MW2: the shell's resource database (menu art, sprites, fonts, sounds)

Parser `data\fmt\mw2db.py`, CLI `data\fmt\mw2tool.py`. Consumer: i76shell.dll, class `TMPackDataBaseObj`; every
address in this section is a shell VA (base 0x10000000). Generated field tables and the per-item load sites are in
FORMATS-tables.md.

- **Container** (`TMPackDataBaseObj_Open` 0x10007fd0): `u32 count` (fread 0x10008079), `u32 offset[count]` (fread
  0x100080b6), then the members back to back. A member's size is the next offset minus its own; the last one runs to
  the end of the file (fseek/ftell 0x10008101/0x10008111). Item ids are 1-based (`dec ecx` 0x10008258). The pristine
  file has 83 members, the first at 0x150, no gaps, 8,204,554 bytes.
- **No type field.** A screen picks the decoder by the accessor it calls: `GetDBItem` 0x10008240 returns the raw
  bytes, `GetDBItemPacked` 0x10008320 decompresses. Only the backgrounds are packed.
- **Backgrounds, items 0x01-0x20 (32):** `u32 unpacked size` + LZSS + a ZSoft PCX v5 (8 bpp, 1 plane, RLE, 0x0C +
  256 x RGB palette at the end). 31 are 640x480 and item 0x11 is 408x406.
  - LZSS: 4 KB ring zeroed (0x10008412), write position 0, flag byte LSB first (0x1000842c), bit 1 literal, bit 0 a
    u16 with the ring position in the low 12 bits and length - 3 in the high nibble (0x100084b0/0x100084b6).
  - The packer was Okumura's LZSS.C (N 4096, F 18, threshold 2, tree search) started at r = 0 on a zero buffer.
    `mw2db.lzss_pack` is a port of it and reproduces all 32 packed members bit for bit, and a plain PCX run-length
    encoder (runs cut at 63 and at each line) reproduces all 32 PCX bodies. So a background round-trips from pixels
    and palette alone.
  - Palettes: 5 distinct. 27 backgrounds share one (item 0x01's); 0x05, 0x0e and 0x1b have their own; 0x0f and 0x11
    share one. PCX DPI is 72 except 0x0d and 0x10 (300) and 0x1b (200).
- **Shape tables, items 0x21-0x40 (32 tables, 460 frames):** magic `1.10`, `u32 count`, `{u32 frame offset, u32 0}`
  per frame, then the frames. A frame is `u16 canvas height-1, u16 canvas width-1, u16 0, u16 0, i32 x0, y0, x1,
  y1` and one run list per line of the box (blitter 0x1003a8f4; box 0x1003a9a9..0x1003a9c4, lines from +0x18):
  `0` ends the line, `1 n` skips n transparent pixels, an odd byte b copies `b>>1` literal pixels, an even byte
  repeats the next byte `b>>1` times. Pixels are palette indices into the palette of the background they are drawn
  on; index 255 is used by no frame. `mw2db.shp_pack_row` reproduces the original encoder for all 32,415 lines
  (rules in its docstring). This is the MechWarrior 2 `1.10` shape format.
- **Fonts, items 0x41-0x47 (7):** magic `1.` 00 00, `u32 glyph count, u32 height, u32 flag`, `u32 offset[count]`
  indexed by character code, then glyphs `{u32 width, pixels}` (the same layout as the loose `.fnt` files).
  - 0x42, 0x43, 0x45, 0x46: 256 glyphs, height 15. 0x44: 144 glyphs, height 12. 0x47: 144 glyphs, height 10. All
    8 bpp, `width x height` palette indices with 0xff transparent (`Mcga_DrawChar` 0x1003e44c, test at 0x1003e5b5).
  - 0x41: 8,896 glyphs, height 12, **1 bpp** (rows of `max(1, ceil(width/8))` bytes, MSB left): a double-byte
    (Japanese) character set. The header flag is 0 here and 0xff in the 8-bpp fonts.
  - ShellMain loads 0x44, 0x42, 0x45, 0x46, 0x47 into the font globals 0x100cc524/28/2c/30 and 0x100cc51c/20/34/38
    (0x1001e761..0x1001e8f9).
- **Sounds, items 0x48-0x52 (11):** RIFF WAVE, 8-bit mono, 11,025 Hz (0x48 is 22,050 Hz). 0x51 and 0x52 start with
  `PIFF` instead of `RIFF`. Held whole.
- **Item 0x53:** the credits roll, 5,205 bytes of CR LF text (Credits_Open 0x10007966).
- **Coverage:** 84.3% cited, 15.7% typed (the WAVs, the text, the 1-bpp font, shape and font magic/count words).
- **Extract / repack:**

```
python data\fmt\mw2tool.py list    sandbox-gog\main\app\DATABASE.MW2
python data\fmt\mw2tool.py extract sandbox-gog\main\app\DATABASE.MW2 data\out\mw2db
python data\fmt\mw2tool.py repack  data\out\mw2db\manifest.json data\out\mw2db\DATABASE.MW2
```

  `extract` writes palettised PNGs (backgrounds with their own palette; one PNG per sprite frame and one glyph sheet
  per font, index 255 transparent), the WAVs and text as raw bytes, the distinct palettes as `.act`, and
  `manifest.json` (index, offset, size, md5, type, dimensions, frame boxes, the screen that loads the item and the
  load site). `repack` rebuilds every member from those files and compares the result with the md5 recorded at
  extraction: an untouched extraction repacks to the identical 8,204,554 bytes. RGB/RGBA PNGs are accepted and mapped
  to the nearest palette colour. The tool refuses to write into a folder that holds the game's executables.

## Open unknowns (every one is listed; nothing else in the modelled formats is unaccounted)

1. .geo header word +4 (0..115 or −1): no reader and no correlation found. It is unused by the engine, so it is safe
   to leave as is.
2. SDFC stats[5] and the ODEF team u16: copied into entity/object records, but no consumer has been found.
3. VDFC collision multiplier: stored at classdata+0x124, and nothing reads it.
4. VSHL, the WLOC wheel slots and SPCS: copied opaquely into the garage record, and no reader has been found; the UI
   position meanings are inferred.
5. Meanings labelled **inferred** in the tables (surface grip/drag names, suspension "handling"/"percent", the
   tmt/xdf "anim" parameter, the WDFC size factor) rest on formulas or values. Each has a live test or a stated reason.
6. DATABASE.MW2: no direct load site was found for items 0x05, 0x0f, 0x11 (backgrounds) and 0x41, 0x43 (fonts); the
   reader of the 1-bpp font 0x41 is not traced; the shape-frame canvas words and the font header flag are typed
   from values (the blitter and Mcga_DrawChar do not read them).
7. Not traced in i76.exe: the .pcx loading-screen reader, the .fnt font loader, and the Smacker and FFB (.frc)
   internals, which belong to external DLLs.
