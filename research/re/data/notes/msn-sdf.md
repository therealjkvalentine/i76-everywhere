# Mission (.msn) chunks other than the FSM, and scenery defs (.sdf): byte layouts

Exe: pristine `ghidra/i76_ref.exe` (GOG Gold). Every citation below is an instruction address from `tools/disasm.py`. Ghidra C was used only to help read the code. Anything I could not tie to a reading instruction is marked **inferred**.

Corpus:
- 40 `sandbox-gog/main/app/miss16/*.MSN`.
- 371 `recon-2026-09-04/recon/formats/zfs_out/*.sdf`.

"body+N" means the offset from the first byte after the 8-byte chunk header (tag u32, size u32). "hdr+N" means the offset from the tag.

## 0. Walker and handler calling convention

`bwd2_Parse` 0x4b3db0 has seven cdecl arguments: `(chunk*, table*, nEntries, a4, a5, stopAtExit, end*)`. Table entries are 16 bytes each: `{tag u32, ?, handler, flags}`.

**How the walker calls a handler.** 0x4b4030..0x4b4046 makes the call `handler(p, extra, end)`:
- **`p`:**
  - `p = chunk + 8*((table[0].flags>>1)&1)` (0x4b403a..0x4b4042).
  - So when the table's first entry has flags bit 1 set (0x500348 `WDEF` 0x2006, 0x500610 `WDEF` 0x0806), `p` is the container's body, which is the first child header.
  - Every leaf table in this note (WREV/TREV/RREV/OREV/LREV/AREV = 0x2004, SDFC = 0x0800) has bit 1 clear, so leaf handlers receive the **header pointer**. Body offsets are therefore hdr+8.
- **`extra`** is selected by flags:
  - 0x0800: `extra = a4` (0x4b3fe9).
  - 0x1000: `extra = &table entry` (0x4b4006).
  - 0x2000: `extra = a5` (0x4b4021).
  - Otherwise `extra = 0`.
- **Other flag bits:**
  - 0x4: mandatory, which gives the "Error - mandatory %s chunk not found" path at 0x4b3ea8.
  - 0x100/0x200/0x400: count-chunk logic.
- **Return value:** the handler returns nonzero for success.

**Mission load.** `mission_LoadFile` 0x4b42b0 does three things in order:
1. It walks `BWD2/REV` with table 0x500328, n=2 (0x4b44c8).
2. It walks table 0x500348 with n=7 and a5 = filename (0x4b44f1): WDEF 0x4b4550, TDEF 0x4b4570, RDEF 0x4b4590, ODEF 0x4b45b0, LDEF 0x4b45d0, ADEF 0x4b45f0, EXIT.
3. Each of those handlers tail-calls a sub-walk with `(p, table, n, 0, filename, 1, end)`:

| Sub-walk | Table | n |
|---|---|---|
| WDEF 0x4b89e0 | 0x500ca0 | 3 |
| TDEF 0x493910 | 0x4fae18 | 4 |
| RDEF 0x4b8750 | 0x500cd0 | 5 |
| ODEF 0x4b7a90 | 0x500ae8 | 3 |
| LDEF 0x4b8f40 | 0x500d80 | 3 |
| ADEF 0x4b89b0 | 0x500d20 | 3 |

**Shell title peek.** A second, shell-side reader `shell_cb_22` 0x4b4a80 walks top table 0x500610 (`WDEF`→0x4b4a50 with a4 = local buffer, 0x4b4b0f..0x4b4b17). That walks 0x5005e0 (`WREV`, `WRLD`→0x4b4a10, `EXIT`) and copies the title out with `strncpy` (0x4b4b54).

**SDF load.** SDFs load through `bwd2_LoadDef` 0x4b41e0 with table 0x500b18 (`SDFC SOBJ SGEO SCHK LOBJ EXIT`, n=6) and a4 = a context struct whose [0] is the owning object. The callers are 0x4b7c30 (ODEF OBJ) and 0x4b7eb2 (LDEF OBJ via 0x4b7ea0).

**Shared with vehicles.** The vehicle table 0x4ff000/0x4ff050 reuses SOBJ 0x4b8470 and LOBJ 0x4b8ed0.

**Missing TDEF tags.** The TDEF tags ZMAP/ZONE are not in tables.txt because their table is at **0x4fae18**:

| Entry | Tag | Handler | Flags |
|---|---|---|---|
| 0x4fae18 | TREV | 0x4b4610 | 0x2004 |
| 0x4fae28 | ZMAP | 0x493960 | 0x4 |
| 0x4fae38 | ZONE | 0x4939d0 | 0x1 |
| 0x4fae48 | EXIT | 0x493bd0 | 0x1 |

A raw scan of the exe for `ZMAP`/`ZONE`/`SDFC`/`SGEO`/`SCHK` finds exactly one occurrence of each tag.

---

## 1. WRLD (331 B), handlers 0x4b8a10 (mission load) and 0x4b4a10 (shell title)

| off | w | type | name | meaning | citation | corpus (n=40) |
|---|---|---|---|---|---|---|
| 0x000 | 4 | u32 | cdTrack | CD-audio music track for the mission | 0x4b8a17 `mov eax,[ebx+8]` → 0x423320 → `[0x4ed800]` (0x423324). Played by shell_cb_20 0x423330 (0x423368 → 0x424b40 range check vs 0x524588/0x52458c, 0x42338b → 0x424670) | 1..15, 15 distinct |
| 0x004 | 13 | char[13] | introSmk | movie played before the mission | 0x4b8bd7..0x4b8bff (3 dwords + 1 byte) → 0x5dd300. WinMain pushes 0x5dd300 at 0x403716 → 0x49a070. Intro-vs-outro is **inferred** from the `int*.smk` names | '' ×24, `intNNf01.smk` |
| 0x011 | 13 | char[13] | outroSmk | movie played after the mission | 0x4b8bfc..0x4b8c20 → 0x5dd310. WinMain 0x40425f → 0x49a070 | '' ×30, `outNNf01.smk`, `preview.smk` |
| 0x01e | 13 | char[13] | palette | .ACT palette, 768 B copied to 0x4fa170 | 0x4b8a33 → 0x46ffc0. 0x4b8a88 `rep movsd` 0xc0 dwords. "Error loading palette %s" 0x4b8a46 | `tNN_16.ACT` |
| 0x02b | 13 | char[13] | lumTable | .LUM luminance table (passed with the palette to `[0x5dd2c4]`) | 0x4b8a53 → 0x46ffc0. Call at 0x4b8a9b. "Error loading luminance table" 0x4b8a6a | `tNN.LUM` |
| 0x038 | 13 | char[13] | xlucTable | .TBL translucency table, 64 KB → 0x60afa0 | 0x4b8ac8 → 0x46ffc0. 0x4b8af3 `rep movsd` 0x4000. "Translucency table not found" 0x4b8af7 | `tNN.TBL` |
| 0x045 | 13 | char[13] | objectiveText | .npt Notepad objective text | 0x4b8b6e → 0x6094f0. Loaded by 0x45dea0 (0x45df06; "Can't find objective text file %s. The Notepad will be unavailable.") | `mNN.npt` etc. |
| 0x052 | 13 | char[13] | skyTexture | sky texture .MAP | 0x4b8b49 → 0x5dce60. Used by 0x404e50 (0x404e74; "Sky Texture not found") | `nk_6cldX.MAP` |
| 0x05f | 13 | char[13] | scroungeSdf | scrounge-pickup .sdf, or '' for none | 0x4b8bb3 → 0x4b8500. "No scrounge in this mission." 0x4b8513 | `ngscrng1.sdf` ×39, '' ×1 |
| 0x06c | 13 | char[13] | terrainTexture | terrain texture set .MAP | 0x4b8bbf → 0x4908f0 ("No terrain texture specified"; default `terr16.map`) | `tpNNN...MAP` |
| 0x079 | 13 | char[13] | mapScreen | in-game map image | 0x4b8b8f → 0x5a7ec8. Used by 0x49cdf0 (0x49ce9d; "No map specified for this mission", "Can't load Map %s") | `zmap6*.MAP` |
| 0x086 | 13 | char[13] | horizonDef | .HZD horizon definition (a text file of tokens) | 0x4b8bcb → 0x401540 (text tokenizer ` ,\t\r\n`, "Horizon Texture (%s) not found." 0x4016c7) | `pNN_16.HZD`, '' ×1 |
| 0x093 | 4 | i32 | hourOfDay | 0..23. Index is `((h+2)%24)*8/24` into the 8-entry sky/sun table 0x4fa0a0 (20-B entries: +0x10 daylight flag, +0x14 sun/moon texture, +0x18 elevation angle, +0x1c brightness) | 0x4b8a21 `mov ecx,[ebx+0x9b]` → 0x477b00 (0x477b22..0x477b4f → 0x58db00; 0x477b58 name; 0x477b8e angle) | {0,6,9,15,21} |
| 0x097 | 8×20 | rec[8] | surface[8] | per-surface-type physics, indexed by the vehicle's surface type (veh+0x45c); see below | 0x4b8b26..0x4b8b47 copies 8×5 dwords → 0x644220 | see below |
| 0x137 | 4 | i32 | farClip | far clip / view distance used when option byte 0x654b8a is set, otherwise 150.0. Clamped to 100..100000 in 0x472220 | 0x4b8c2a `fild [ebx+0x13f]` → `fstp [0x4c271c]` (0x4b8c31). Read at 0x4059de → arg 5 of 0x472220 (clamp 0x472274..0x4722a7, stored in camera +0x10) | 600 ×40 |
| 0x13b | 16 | char[16] | missionTitle | title shown by the shell mission picker; the mission loader never reads it | 0x4b4a21 `lea edi,[eax+0x143]`, strcpy to the caller buffer. shell_cb_22 0x4b4b54 | '' ×39, "Jorczak's Peak" (M14) |

**Surface record** (20 B each, 8 records):

| rec off | w | type | name | citation (accessor) | consumer | corpus |
|---|---|---|---|---|---|---|
| +0x0 | 4 | f32 | grip (**inferred**) | 0x492777 (fn 0x492770) | 0x43c310/0x43c6f0/0x43ce10/0x43d240: zeroed if >0.2 and veh flag 0x400 | 1.0..9.999 |
| +0x4 | 4 | f32 | rolling drag (**inferred**) | 0x492787 (fn 0x492780) | 0x40f9c0, 0x43a5d0: term `-f*load*…` | 0.01..9.999 |
| +0x8 | 4 | f32 | bump amplitude | 0x492797 (fn 0x492790) | 0x46dc10: `height += f * noise8x8[0x4be398]` | 0 except rec5 ∈{0,0.5,9.999} |
| +0xc | 4 | u32 | unused | no xref to 0x64422c or any accessor for this field | – | 0 always |
| +0x10 | 4 | i32 | damage rate | 0x4927a7 `fild` (fn 0x4927a0) | 0x438fd0: speed>7.65 → 0x4641e0 random part damage `f*dt` | rec1 {3,5}, rec5 {12,14}, others 0 |

Every WRLD byte is read by one of the two handlers.

**Open76 check:** `pos += 30` followed by nine 13-byte names is correct. Its names match: objective = .npt, sky, scrounge, surface texture, level map = map screen, hzd. The first 30 bytes are cdTrack plus two movie names. HZD is a horizon definition, not a hazard file. The far-clip claim is **confirmed** (0x137).

## 2. TDEF: ZMAP (6401 B) and ZONE (14 B)

The TDEF walker 0x493910 fills zone map 0x5a4768 with 0xff (0x493911..0x49391e, 0x640 dwords) and clears the zone pointer array 0x5a4628 (0x50 dwords).

**ZMAP** (handler 0x493960):

| off | w | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0 | 1 | i8 | zoneCount | number of distinct terrain zones | 0x49397f `movsx edx,[eax+8]` → [0x5a4620] (0x493986) | 4..59. Always max(map)+1 |
| 1 | 6400 | i8[80][80] | zoneMap | row-major grid of zone indices, −1 = no terrain. Each entry must be < zoneCount (0x493990..0x4939b2 "zone number too large") | 0x493983 `lea esi,[eax+9]` + 0x49398c `rep movsd` 0x640 → 0x5a4768 | −1 in 255089 cells; 0..58 |

**ZONE** (handler 0x4939d0):

| off | w | type | name | meaning | citation | corpus |
|---|---|---|---|---|---|---|
| 0 | 1 | u8 | – | **unused**: the handler starts at hdr+9 | 0x4939db `lea ebx,[eax+9]` | 0xff ×40 |
| 1 | 13 | char[13] | terrainFile | .ter height file. Tried as `addon\%s` first, then the CD drive `%c:\%s`, with a copy fallback to `another.sat`. Loaded by 0x471400 → [0x5a6068..0x5a6070]. Zone i's data = base + i×0x8000 into 0x5a4628[i] (0x493ba7..0x493bbc) | 0x4939f2..0x493b51 | `xNN.ter` (matches the mission) |

**EXIT handler 0x493bd0** calls 0x493080(1, [0x654b87], 5.0). This copies the 80×80 map into a 128×128 zone-pointer grid at 0x644380 starting at cell 0xc18 (row 24, col 24, so the map is centred). Each row is 0x80 cells, row step 0x80 (0x493080 decomp; loop bound 0x50). Each zone is 0x8000 B, i.e. 128×128 u16 (**inferred** size). Open76 reads the low 12 bits as height. That is not verified here.

## 3. RDEF: RSEG / ISEG / TSEG

**RSEG** (handler 0x4b8780):

| off | w | type | name | meaning | citation | corpus (651 chunks) |
|---|---|---|---|---|---|---|
| 0 | 4 | u32 | roadType | only `type % 3` is consumed: 0 = paved (`r2anr/r2ayr` textures), 1 = dirt (`r2dnr`), 2 = wash (`r2wnr`) | 0x4b881c/0x4b88e1 `mov edx,[ecx+8]` → node+0x10. Consumer 0x48ea18..0x48ea4c `idiv 3` → 0x4fa9a0+(t%3)*0x50 | 0 ×393, 1 ×242, 2 ×15, 3072 ×1 (3072%3 = 0) |
| 4 | 4 | u32 | nPoints | point count | 0x4b8789 `mov ecx,[edx+0xc]` | 0..1771. len = 8+24n always |
| 8 | 24·n | rec | point[n] | {left x, left y, left z, right x, right y, right z} | copy 0x4b8837/0x4b8903 → node+0x2c | see below |

**Point fields:**
- **x and z (+0, +8, +0xc, +0x14)** are read by 0x48e1a0 (the reads are in the Ghidra listing at 0x48e3e2..0x48e4ed).
- **The file's y values (+4, +0x10) are ignored.** They are overwritten with the terrain height via 0x493550: 0x48e418 `fstp [edi+eax+0x10]` and 0x48e4ed `fstp [edi+edx+4]`. In the file, y holds junk: +4 ≈ the centre-line z, and +0x10 is 0 or small.
- **Splitting.** The handler splits a road into linked nodes of at most 25 points (0x4b8792..0x4b87a6 halves until ≤24 intervals), with one shared point per split. It links them into the list at 0x5db988 (id counter 0x5db98c; the last node gets +0xc = 1).

**ISEG / TSEG** use 0x4b8960 (`mov eax,1; ret`), a no-op stub. There are no ISEG/TSEG chunks in the corpus.

Open76's `Left(xyz) Right(xyz)` is correct. Its PavedHighway/DirtTrack/RiverBed names map to t%3. Its 3072 = FourLaneHighway is **not supported by the code**: the only consumer found reduces 3072 to type 0.

## 4. ODEF OBJ (100 B), handler 0x4b7ac0

In this handler `ebp = hdr+8 = body`.

| off | w | type | name | meaning | citation | corpus (2782; 11 nameless M06 records skipped) |
|---|---|---|---|---|---|---|
| 0x00 | 8 | char[8] | label | object/class file name. The **high bit of each byte** is stripped for the name (0x4ad689..0x4ad69d `and 0x7f`). The **raw** 8 bytes (with high bits) are the entity key: 0x4b7d97/0x4b7d9a → 0x457610 → 0x4ad450 table 0x54a178 | 0x4b7aca/0x4b7acd → 0x4ad640 | high bits = MSB-first instance number among same-name objects in the mission (0,1,2,…; byte 0 never set). 19 raw duplicates |
| 0x08 | 36 | f32[3][3] | rotation | right/up/forward rows → obj+0x18..0x38 | 0x4b8256..0x4b8288 (in 0x4b8230) | −1..1; rows orthonormal |
| 0x2c | 4 | f32 | posX | → obj+0x40 (double) | 0x4b828f | 52.5..11060 |
| 0x30 | 4 | f32 | posY | **overwritten by the terrain height**: ODEF always passes snap=1 | 0x4b8297 read, then 0x4b82b5 → 0x493550, 0x4b82ba `fstp [ebp+0x48]` | 0..409.4 |
| 0x34 | 4 | f32 | posZ | → obj+0x50 | 0x4b829d | 35465..51125 |
| 0x38 | 36 | – | (bounds centre/radius/half-extents in SGEO parts) | **unused in ODEF**: 0x4b8230 reads +0x40..+0x58 only when snap==0 (0x4b8337..0x4b839e). ODEF passes snap=1 (0x4b7b96/0x4b7be9 push ebx=1) | – | all 0 |
| 0x5c | 4 | u32 | classId | dispatch: see the class table below | 0x4b7b06, 0x4b7b7a..0x4b7b8f (switch 0x4b7e24/0x4b7e44), 0x4b7d29. 0x4b831e → 0x461970 → obj+0x6c | 1 ×454, 2 ×559, 3 ×506, 4 ×694, 7 ×1, 8 ×57, 9 ×13, 11 ×61, 12 ×34, 80 ×262, 82 ×128, 83 ×2 |
| 0x60 | 4 | u32 | flags (lo u16) / team (hi u16) | copied whole to obj+0x10 | 0x4b82c0 `mov edx,[ebx+0x60]` → 0x4b82cb | u16 lo ∈{0,16,…}; hi ∈{0,1,2,3} |

**Flags and team at +0x60:**
- Flags bit 0x10 means player: `obj_IsPlayer` 0x458bf8 `test [eax+0x10],0x10`. It is used by 0x4ad6f0 to substitute the chosen car, and by 0x4572b0 to set the world root.
- Team is the high u16, i.e. obj+0x12. Open76 names it team. Nothing reads it as a team yet (**inferred**). The byte obj+0x12 is also tested bitwise by many functions, so these may just be flag bits.
- The junk values 10468/49145 and 34988/49142 appear in 32/5 records.

**Class dispatch** (switch at 0x4b7b87):
- **1 (car):**
  - Label `spawn` → spawn table 0x53fd88.
  - Label `regen` → regen table 0x53ecb0.
  - Both through 0x450f90, which reads 0x08..0x37.
  - Otherwise treated as a vehicle: label+`.vcf` → 0x4ad6f0.
- **8, 9:** vehicle path.
- **2, 3, 4, 7, 10, 11, 12, 80, 82, 83:** label+`.sdf` → `bwd2_LoadDef` 0x4b7c30.
- **5, 6, 13..79, 81:** rejected (0x4b7cef).
- **80/82/83:** additionally re-parented through 0x494e20 and 0x4925f0 (0x4b7db5..).

**Longer OBJ bodies (128..1064 B) are LDEF, not ODEF.** Every ODEF OBJ in the corpus is 100 B.

### LDEF OBJ (0x68 + 12·n B), handler 0x4b8f70 ("string" objects: fences, tire walls)

| off | w | type | meaning | citation | corpus (33) |
|---|---|---|---|---|---|
| 0x00 | 8 | char[8] | label, passed raw as the geometry name | 0x4b8f82 `lea ebx,[eax+8]`, pushed twice → 0x4b8230 | afence3 ×26, afence4 ×5, aitire1 ×2 |
| 0x08 | 48 | rot+pos | read by 0x4b8230 but then **overwritten**: rotation = identity 0x4faed8 (0x4b9043..0x4b9048); pos = point[0] with y snapped | 0x4b8230 | all 0 |
| 0x38 | 36 | – | unused (snap=1) | – | 0 |
| 0x5c | 4 | u32 | classId → 0x461970 (p5=1). Segments after the first get class 3 | 0x4b831e | 2 ×27, 3 ×6 |
| 0x60 | 4 | u32 | flags → obj+0x10 | 0x4b82c0 | 0 |
| 0x64 | 4 | u32 | nPoints | 0x4b8fc5 `mov ebx,[ebx+0x64]` | 2..80. len = 0x68+12n always |
| 0x68 | 12·n | f32[3] | post positions, absolute world coordinates (y ignored: resnapped at 0x4b9027 and in the loop) | 0x4b8fe2 `lea esi,[edx+0x68]` → pool 0x5dd320 | – |

The first 0x78 bytes of the body are kept as a respawn template (0x4b8fbe..0x4b8fd2). The chain is split wherever a piece's radius exceeds 20.0.

Open76 is right on label / skip 84 / class @0x5c / u32 / count / vec3s.

## 5. SDF scenery (rev 8)

Handlers get `(hdr, ctx)`. ctx[0] = the owning object; ctx+0x3c..+0x50 are the SDFC stats; ctx+0x50 is the "has stats" flag.

### SDFC (70 B), handler 0x4b7f70

| off | w | type | name | meaning | citation | corpus (371) |
|---|---|---|---|---|---|---|
| 0x00 | 16 | char[16] | displayName | **unused** by the exe (no reader; the buffer is released after load at 0x4b4278) | – | 'Sign' ×120, 'Industrial Park …' |
| 0x10 | 4 | u32 | classHint | **unused** (editor class; matches SGEO part0 class in most files) | – | 1..83 |
| 0x14 | 20 | f32[5] | stats[5] | copied to ctx+0x3c, with ctx+0x50 = 1 (0x4b7f88). Then to the entity record +0x1c..+0x2c via 0x4572b0 (arg 3 from 0x4b7d6a). No reader of the entity fields found. Open76: size vec3 + 2 unknowns (**inferred**) | 0x4b7f7e `lea esi,[ebx+0x1c]`, `rep movsd` ×5 | (30,10,5,4,1e5) ×118; (0,1e5,1e5,1e5,1e5) ×59; (100,30,15,1e5,1e5) ×54 … |
| 0x28 | 4 | u32 | health | **unused by SDFC**. Health comes from SGEO part +0x64 (equal in 290/371). Open76 reads it here | – | 2..500000 |
| 0x2c | 13 | char[13] | explosionXdf | only for owner classes 2/3/11/12: 0x4b8c40(name, classdata+0x10) loads the XDF | 0x4b7fb4 `lea ecx,[ebx+0x34]` | 'null' ×255, xbldx1.xdf ×96, xgasx1.xdf ×16 |
| 0x39 | 13 | char[13] | destroySound | → classdata+0x18 (13 B) | 0x4b7fbe `add ebx,0x41` .. 0x4b7fda | 'null' ×276, xbuild.wav ×87 |

### SGEO (4 + 720·n B), handler 0x4b7ff0

| off | w | type | meaning | citation | corpus |
|---|---|---|---|---|---|
| 0 | 4 | u32 | nParts | 0x4b800b `mov edi,[edx+8]` | 1..49. len = 4+720n always |
| 4 | 6·n·120 | part[6][n] | **six arrays of n parts**, `arr[k] = body+4 + k·n·120` (0x4b8015..0x4b8026). 0x4b7800(arr, obj, 3, 2, n) iterates lod i∈0..2 (outer), state j∈0..1 (inner), k = 2i+j, and calls 0x4461e0(obj, name+'.geo', j, i). **Only arr[0] creates objects** (0x4b8230 with snap=0). The other five contribute only their name (+0,+4). i is the LOD, from names `A11_/A12_/A13_`; j = 1 is the damaged variant, from names `IJ1_…`/`IJ1A…` (**inferred** from names) | 0x4b803b | – |

**120-byte part** (arr[0]; read by 0x4b7800 and 0x4b8230 snap=0):

| rec off | w | type | meaning | citation | corpus (1507 arr0 parts) |
|---|---|---|---|---|---|
| 0x00 | 8 | char[8] | part geometry name (+`.geo`) | 0x4ad640 call in 0x4b7800 | no high bits |
| 0x08 | 36 | f32[9] | local rotation → obj+0x18 | 0x4b8256.. | identity in every part |
| 0x2c | 12 | f32[3] | local position → obj+0x40..0x50 | 0x4b828f..0x4b829d | −150..210 |
| 0x38 | 8 | char[8] | parent part name; 'WORLD' or 'NULL' = the owner. Lookup via 0x4b47f0(obj, [+0x38], [+0x3c]) | 0x4b7800 (strnicmp `world`) | WORLD ×920, part names |
| 0x40 | 12 | f32[3] | bounds centre → obj+0x84..0x8c | 0x4b8340 `lea edx,[ebx+0x40]` | ~0..3 |
| 0x4c | 4 | f32 | bounding radius → obj+0x90 | 0x4b8337 | 0.004..240 |
| 0x50 | 12 | f32[3] | half extents → obj+0x94..0xa8 (centre ± h) | 0x4b835d..0x4b839e | 0..210 |
| 0x5c | 4 | u32 | classId → 0x461970. Class 0x51 = attach-transform part (0x4b7800) | 0x4b831e, 0x4b83ad | 2 ×638, 55 ×385, 4 ×298, 81 ×50 … |
| 0x60 | 4 | u32 | flags → obj+0x10. Bits 10–11 select the XDF/sound pair from 0x500b78/0x500bb0 (0x4b7c7e..0x4b7c87) | 0x4b82c0 | 0, 0x1000, 0x2000, 0x3000, 0x1000001 … |
| 0x64 | 4 | u32 | hit points (classes 2/3/4/11/12 → 0x46b200: classdata[0]=[1]=hp; class 10 → 0x46f960; class 7 → 0x46d6f0) | 0x4b83cb, 0x4b8419, 0x4b8430 | 5..500000 |
| 0x68 | 12 | f32[3] | class 10: spin rates, ×2π in 0x46f8f0. Class 7: params to 0x46d6f0 | 0x4b83fb, 0x4b83ce.. | −7.1..10 |
| 0x74 | 4 | u32/f32 | class 7 only (0x46d6f0 5th arg) | 0x4b83ce `mov eax,[ebx+0x74]` | 0, 1.0, 5.0 |

Open76 reads only arr[0] with "skip 56". Its "wrecked part" is really arr[1]'s first record.

### SCHK (12 + 120·n B), handler 0x4b8050: collision chunks

| off | w | type | meaning | citation | corpus (207) |
|---|---|---|---|---|---|
| 0 | 8 | char[8] | parent part name. Looked up via 0x4b47f0 ("Chunk's parent object %s not found."). The parent gets obj+0x10 \|= 0x100000 | 0x4b8062/0x4b8065, 0x4b80a2 | e.g. HJ1_BLD1 |
| 8 | 4 | u32 | nChunks | 0x4b80ae `mov eax,[esi+0x10]` | 1..6. len = 12+120n always |
| 0xc | 120·n | rec | chunk records, stride 0x78 (0x4b81a2) | – | – |

**Chunk record:**

| rec off | w | meaning | citation | corpus (486) |
|---|---|---|---|---|
| 0x00 | 8 | chunk name → 0x4a0ff0 args 2,3 | 0x4b8175/0x4b816d | 'HJC1BLD1'… |
| 0x08 | 36 | rotation (9 dwords) | 0x4b80cb..0x4b810c | identity |
| 0x2c | 12 | position (→ doubles) | 0x4b80c8, 0x4b80d5, 0x4b80e9 | −1..134 |
| 0x38 | 8 | parent name | **unused** by SCHK | 'WORLD' ×486 |
| 0x40 | 12 | centre | **unused** (0,0,0 is substituted, 0x4b80b9..0x4b80c1) | ~1e-6 |
| 0x4c | 4 | radius | 0x4b812e | 0.1..9.0 |
| 0x50 | 12 | half extents h; the box passed is [−h, +h] | 0x4b8113/0x4b8150/0x4b8159 `fchs`, 0x4b8135..0x4b8143 | 0..8.9 |
| 0x5c | 28 | class etc. | **unused** | class 2, rest 0 |

The chunk is added by 0x4a0ff0(parent, name, &xform, &{0,0,0,r}, &{−h,+h}); a failure prints "Unable to add chunk".

### SOBJ (100 B), handler 0x4b8470

Reads only body+0..7, the name with high bits stripped + `.geo` (0x4b8479/0x4b847c → 0x4ad640 → 0x4469a0). The result is stored in owner obj+0x5c (0x4b8498).

The other 92 bytes (identity rotation, pos, 'WORLD', bounds, class 54) are **unused**. The names `EO__SOR1`, `FN__SOR1` suggest shadow geometry (**inferred**). There are 4 SOBJ chunks in the corpus.

### LOBJ (72 B), handler 0x4b8ed0: lights

| off | w | type | meaning | citation | corpus (13) |
|---|---|---|---|---|---|
| 0x00 | 4 | u32 | lightType: 0 omni, 1 spot | 0x4b8f16 `mov eax,[eax+8]` → 0x477c20 arg 2 | 1 ×13 |
| 0x04 | 24 | f32[6] | rotation rows 0–1: **unused** | – | identity |
| 0x1c | 12 | f32[3] | spot direction (row 2; negated in 0x477c20) | 0x4b8edc..0x4b8ee6 | (0,−1,0) |
| 0x28 | 12 | f32[3] | light position/offset → light rec +0x20..0x28 | 0x4b8eed..0x4b8efb | x −150..170 |
| 0x34 | 8 | – | **unused** | – | 0.63..78, 0 |
| 0x3c | 4 | f32 | cone angle (rad), clamped 10°..90°, used as cos | 0x4b8f0f `[eax+0x44]` | 0.785..1.178 |
| 0x40 | 4 | f32 | range, clamped ≥20, stored with 1/r² | 0x4b8f13 `[eax+0x48]` | 5.4..7.5, so always clamped to 20 |
| 0x44 | 4 | – | **unused** | – | 0 |

After adding the light, the owner gets obj+0x10 \|= 0x800 (0x4b8f2d). 0x477c20 skips the light entirely when the time-of-day entry's daylight flag (0x4fa0b0+idx·20) == 1, so lights only appear at night.

## 6. Proposed exe function names

| addr | proposed name | evidence |
|---|---|---|
| 0x4b42b0 | mission_LoadFile | `.msn` literal, walks 0x500328 then 0x500348 |
| 0x4b4a80 | mission_ReadTitle | shell_cb_22: walks 0x500610 → 0x4b4a10, strncpy out |
| 0x4b4a10 | wrld_h_ReadTitle | copies body+0x13b to a4 |
| 0x4b4a50 | wdef_WalkForTitle | walks 0x5005e0 |
| 0x4b8a10 | wrld_h_Load | error strings for palette/lum/translucency |
| 0x4b89e0 / 0x493910 / 0x4b8750 / 0x4b7a90 / 0x4b8f40 / 0x4b89b0 | wdef_Walk / tdef_Walk / rdef_Walk / odef_Walk / ldef_Walk / adef_Walk | push of the WREV/TREV/RREV/OREV/LREV/AREV tables |
| 0x493960 | tdef_h_ZMAP | "zone number too large in Zone Map" |
| 0x4939d0 | tdef_h_ZONE_LoadTer | `addon\%s`, `another.sat`, 0x8000 stride |
| 0x493bd0 | tdef_h_EXIT | → 0x493080 |
| 0x493080 | terrain_BuildZoneGrid | 80×80 → 128×128 at offset 0xc18 |
| 0x493bf0 / 0x493c00 | terrain_GetZoneMap / terrain_GetZoneData | return 0x5a4768 / 0x5a4628[i] |
| 0x493550 | terrain_HeightAt(x,z) | used for every y snap |
| 0x4b8780 | rdef_h_RSEG | list 0x5db988 |
| 0x4b8970 | road_GetList | returns [0x5db988] |
| 0x48e1a0 | road_InitAll | snaps y, computes centre/radius |
| 0x4b8960 | bwd2_h_Ignore | `mov eax,1; ret` |
| 0x423320 | music_SetMissionTrack | → 0x4ed800 |
| 0x477b00 | sky_SetTimeOfDay | (h+2)%24·8/24 index, sun/moon map |
| 0x4b8500 | scrounge_Load | "No scrounge in this mission." |
| 0x4908f0 | terrain_SetTextureSet | "not a valid terrain texture" |
| 0x401540 | horizon_LoadHzd | "Horizon Texture (%s) not found." |
| 0x45dea0 | notepad_LoadObjectives | "objective text file" |
| 0x49cdf0 | mapscreen_Open | "No map specified for this mission" |
| 0x404e50 | sky_LoadTextures | "Sky Texture not found" |
| 0x492770 / 0x492780 / 0x492790 / 0x4927a0 | surface_GetGrip / surface_GetDrag / surface_GetBump / surface_GetDamageRate | 20-B stride over 0x644220 (meanings **inferred**) |
| 0x472220 | camera_SetProjection(out, view, fov, aspect, far, near) | fov clamp π/4..3π/4, far clamp 100..1e5 |
| 0x4ad640 | bwd2_DecodeLabel | `and 0x7f`, `null`, append ext |
| 0x4b8230 | obj_CreateFromRecord | copies rot/pos/flags/class/bounds |
| 0x450f90 | spawn_AddPoint | tables 0x53fd88/0x53ecb0 |
| 0x458bf0 | obj_IsPlayer | `test [eax+0x10],0x10` |
| 0x457610 | entity_RegisterLabel | raw label → 0x54a178 |
| 0x4572b0 | entity_Create | "world is full" caller; SDFC stats → rec+0x1c |
| 0x4b7ea0 | sdf_LoadForObject | LoadDef 0x500b18 + XDF/sound |
| 0x4b7f70 / 0x4b7ff0 / 0x4b8050 / 0x4b8470 / 0x4b8ed0 | sdf_h_SDFC / sdf_h_SGEO / sdf_h_SCHK / sdf_h_SOBJ / sdf_h_LOBJ | table 0x500b18 |
| 0x4b7800 | sdf_BuildParts(arr[6], obj, nLod=3, nState=2, n, cb) | loops |
| 0x4461e0 | geo_SetSlot(obj, name, state, lod) | hash 0x52bbe8, +0x70 chain |
| 0x4a0ff0 | coll_AddChunk | "Unable to add chunk" |
| 0x477c20 | light_Add | clamps, table 0x58db84 |
| 0x4b8c40 | xdf_Load | walks XDFC table 0x500d50 |
| 0x4b8f70 | ldef_h_OBJ_BuildString | fence/tire chain |
| 0x4b7ac0 | odef_h_OBJ | class switch |

## 7. Open questions

- **SDFC stats[5] (body+0x14..0x27):** there is no reader yet for entity record +0x1c..+0x2c. The size and "unk" labels are Open76's.
- **ODEF +0x62 "team":** the code only copies it into obj+0x12. No team semantics were found in the code.
- **Surface record fields +0 and +4:** the names grip and drag are inferred from the physics formulas.
- **The option behind 0x654b8a:** it is toggled by the options callback 0x496110 (cases 6–9). This note does not identify which UI control it is.
