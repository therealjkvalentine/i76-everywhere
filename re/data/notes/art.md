# Art-asset formats: .geo, .tmt, .vqm/.cbk/.map, .m16, .act/.lum/.tbl/.tab

Pristine image `ghidra/i76_ref.exe` (md5 9a232dcc…). Every citation is an instruction address from
`tools/disasm.py`; Ghidra C was used only to find things. Tags: **cited** means an exe instruction
reads the field, **unread** means the loader's byte walk skips it (checked against the function's full
disassembly), **corpus** means a statistic over `recon-2026-09-04/recon/formats/zfs_out` (every .pak member
plus loose files), and **inferred** means my interpretation, with no single instruction proving it.

Shared helpers used by every loader (their names are inferred from how they are used):
`0x46ffc0` loads a file by name and returns its buffer, `0x46fee0` returns a file's size (0 if missing), `0x46fd40` releases a file by name, and `0x470340` checks whether a file exists.
Name hash (all caches): `h=0; for c in name: h = 2*h ^ (c & 0xDF)`, then `(h*0x6CD + 0xAAB) % M`
(`0x6CD` = 1741). The cache's M is 0x7ED for geometry and textures, 0x6D for decoded VQMs, 0x71 for anim instances and 0x6CD for the FULLRES bitset.
The "12*k+0xaab" in prior notes is wrong. The multiplier is 1741: `lea ecx,[eax+eax*8]; shl ecx,4; add ecx,eax; lea ecx,[ecx+ecx*2]; lea eax,[eax+ecx*4+0xaab]` at 0x4469f4–0x4469ff. The geometry cache key is `(lo32 ^ hi32) & 0xDFDFDFDF` of the first 8 filename bytes, uppercased (0x4469c0–0x4469ef).

---

## 1. .geo mesh: loader `0x446c90` new_geometry(buf, size)

The only caller is `0x4469a0` (geometry cache get): 0x446a3e loads the file, 0x446a8e calls the parser and 0x446a9e releases the file.
The `size` argument is never read. The magic compare is the only 'OEG.' check in the image (`cmp dword [edi],0x2e47454f` at 0x446c9b), so a mismatch returns NULL.
The allocation is `(Σ nVerts_face + 4*nFaces)*16 + (nVerts+1)*24` (0x446ccf–0x446cef).

### Header (36 bytes)
| off | w | type | name | meaning | citation |
|---|---|---|---|---|---|
| 0x00 | 4 | char[4] | magic | 'OEG.' (0x2e47454f) | cited 0x446c9b |
| 0x04 | 4 | u32 | unk0 | **unread.** corpus: 0..115 plus 0xFFFFFFFF, no correlation with nVerts, nFaces, total vref count or texture count (r≈0). Not a count or size. | unread |
| 0x08 | 16 | char[16] | name | **unread.** The cache is keyed on the *filename*. corpus: equals the filename stem in 9019/9019 | unread |
| 0x18 | 4 | u32 | nVerts | vertex count, and also the normal count | cited 0x446cad, 0x446e61 → out+4 and out+8 |
| 0x1C | 4 | u32 | nFaces | face count | cited 0x446cb0, 0x446efe, 0x4471b5 |
| 0x20 | 4 | u32 | unk1 | **unread.** corpus: 0 in 9019/9019 | unread |
| 0x24 | 12·nV | f32[3] | verts | copied to out[0x18..] | cited 0x446e99–0x446eb3 |
| 0x24+12nV | 12·nV | f32[3] | normals | copied to out+0x10 array; lit per normal by 0x478430 | cited 0x446ed6–0x446ef0 |

### Face (55 + 16·n bytes, stride computed at 0x4471aa–0x4471b1)
| off | w | type | name | meaning | citation |
|---|---|---|---|---|---|
| 0x00 | 4 | u32 | index | **unread.** corpus: a permutation of 0..nF-1 in 9019/9019. It is the face's BSP node id (see b and c) | unread |
| 0x04 | 4 | u32 | n | corner count | cited 0x446f1a → out+4 |
| 0x08 | 3 | u8[3] | rgb | flat colour (r,g,b) copied to out+9..0xB. `0x4796a0(r,g,b)` (nearest entry in the 256-colour palette) gives the index stored at out+8 | cited 0x446f20–0x446f44, 0x446f49 |
| 0x0B | 16 | f32[4] | plane | nx,ny,nz,d with **n·x + d = 0** (corpus 38702/38702 checked vertices), copied to out+0xC..0x18 | cited 0x447182–0x447197 |
| 0x1B | 4 | u32 | a | **unread.** corpus: 0 in 114451/114451 | unread |
| 0x1F | 1 | u8 | surf0 | "shading class", the row of the mode table at 0x4f71b8 (below) | cited 0x446f4c → out+0x1C |
| 0x20 | 1 | u8 | surf1 | "texture options", 3 bits, the column of the mode table | cited 0x446f52 → out+0x1D |
| 0x21 | 1 | u8 | surf2 | translucency: nonzero sets render bit 0x80 | cited 0x446f58 → out+0x1E |
| 0x22 | 13 | char[13] | texture | "" means flat colour. corpus: 78128 end in '.map', 1020 end in '.tmt', none lack a '.'. If the name has no '.', the loader appends '.tmt' when that file exists (0x44703b), otherwise '.map' (0x447047) | cited 0x446f64 (empty test), 0x446f75 strchr, 0x44707f–0x447093 16-byte copy → out+0x20 |
| 0x2F | 4 | u32 | b | **BSP parent**: the `index` of the parent node, 0xFFFFFFFF for the root. **Unread as a field.** Its low 3 bytes are copied only as padding after the NUL inside the 16-byte texture copy (0x447084–0x447090 read 0x22..0x31). corpus: exactly one root per mesh (9017/9017 non-empty meshes), and every parent appears earlier in file order (105434/105434), so faces are stored in pre-order | unread (inferred meaning) |
| 0x33 | 4 | u32 | c | **side of parent**: 1 = front (child centroid on the n·x+d>0 side of the parent plane), 0 = back. corpus: c=0 → negative side 25425/25427; c=1 → positive or on-plane in 77519/79853 (the rest are split or straddling). Root c=1. Front subtree comes first. ≤1 child per side (9019/9019) | unread (inferred meaning) |
| 0x37 | 16·n | vref[n] | vrefs | {u32 vertex, u32 normal, f32 u, f32 v}, copied 1:1 to out+0x40+16i | cited 0x447107 (vertex), 0x447110 (normal), 0x447115 (u), 0x44711b (v) |

The runtime face struct (0x40+16n) is out+0x30 (next face, a linked list in file order, 0x4470a0) plus out+0x34..0x3C (centroid = Σ verts · (1/n); the table at 0x4f9d38 is used for n<16, else 1.0/n; 0x4470a3–0x44717f).
The engine **ignores the file's BSP**. `0x45cbe0` re-sorts faces at run time into its own plane tree, using out+0xC and out+0x34 (the +0x40/+0x44 children; the tree root is 0x54ad28 (read at 0x45cfd9), and child links are walked and written at 0x45d019–0x45d02f).

### Surface flags → render mode (cited)
`mode = dword[0x4f71b8 + 4*(surf0*8 + surf1)]` is read at 0x45ce83 (0x45cbe0), 0x48f6a9 (0x48f570) and 0x45c7b4 (0x45c380).
- **surf2 ≠ 0**: `mode |= 0x80` (0x45ce8d–0x45ce9f). The 0x48f570 path instead uses `mode = mode & ~0x40 | 0xA0` (0x48f6a4–0x48f6b5).
- **surf0 == 0**: 0x45ce65–0x45ce6c **writes 4 into the cached face** (the file mesh is mutated). 0x48f570 does not do this, so it indexes row 0, which holds float junk (0x42c80000 …); `& 0xFF` makes that mode 0 = untextured flat.
- The mode is then ANDed with the object's mask (obj+0x14; 0x45cea7, 0x48f6b8). If bit 4 is set but the texture fails to resolve, `mode &= ~0x14` (0x48f6f9, 0x45c7fd).

Table rows (dumped from the image):
| surf0 | row (surf1 = 0..7) | meaning |
|---|---|---|
| 0 | float junk (100.0, 0, -100.0, …) | not a valid row (see above) |
| 1, 2 | 0xE3 ×8 | 0xE3 → `0x471f20`: draws the polygon **outline as lines** (calls 0x48d2e0 per edge) = wireframe |
| 3, 4 | 04 14 06 16 44 54 46 56 | textured, unlit |
| 5 | 05 15 07 17 45 55 47 57 | textured + luma-shaded |

The table maps surf1 bit0 → 0x10, bit1 → 0x02 and bit2 → 0x40. corpus: surf0 ∈ {5: 108769, 4: 4118, 0: 1564}; surf1 ∈ {0,1,3,4,5,7}; surf2 ∈ {0: 114247, 2: 173, 1: 31}.

Render-mode bits (software rasteriser tables: 0x4f9538 setup ×512, 0x4f8d38 span driver ×512, 0x4ed930 D3D batcher ×256):
| bit | meaning | evidence |
|---|---|---|
| 0x01 | luma (lighting) shading | the spans for modes 1/3/5/7/0x45/0x47/0x55/0x57 read the .lum table 0x61b2a0 (e.g. 0x47cc55, 0x486860, 0x48a870). Mode 4's span 0x47d450 does not |
| 0x02 | UV **wrap/tile** | 0x47c6b0 `test [ebp+0x18],2`. Without it u,v are clamped to [0,1]; with it, to [-32,32] (0x47c6e9–0x47c756). 0x45cbe0 zeroes the mode if a vref's u or v is outside ±32 |
| 0x04 | textured | the setup group for 4–7 is 0x47c2f0. 0x471fd0 and 0x4260d0 clear bit 4 when no texture is present |
| 0x10 | perspective-correct | 0x47c7b5 `test cl,0x10`. When clear, u/w and v/w are converted back to affine. The 0x1x spans use fdiv (0x47dcc0 for 0x14, 0x47f850 for 0x16) and the 0x0x spans do not (0x47d450 for 0x04, 0x47efe0 for 0x06) |
| 0x40 | colour-key: texel 0xFF not drawn | span 0x480240 (driver 0x480900, mode 0x44): `cmp bl,0xff; je` skips the store (0x480557–0x48055d). Also in 0x480b30, 0x481590 and 0x481e80 |
| 0x80 | translucent through the .tbl table | the 0x84/0x94/0xA4/0xB4 spans (0x4828e0, 0x483210, 0x483cc0, 0x484630) read 0x60afa0 |
| 0x20 | set together with 0x80 by 0x48f570 | not traced |
| 0x100+ | a second table half (0x10x…) | not traced (driver-side) |

---

## 2. .tmt texture-animation table
It is resolved by `0x44a290` (face texture → texture instance), is loaded when the name's extension is not '.map' (0x44a38b), and is parsed by `0x44ab90`.
Before parsing, 0x44a45c–0x44a463 does `strncpy(buf+4, name, 15)`: **header bytes 4..0x12 are scratch space for the name** (they are zero in files).
Size law (corpus 2859/2859 exact): `len = 0x40 + 8·Π dims`.
| off | w | type | name | meaning | citation |
|---|---|---|---|---|---|
| 0x00 | 4 | u32 | w0 | **unread** (corpus: 1 always) | unread |
| 0x04 | 16 | u32[4] | scratch | overwritten with the texture name at load (0x44a463) | written, not read as data |
| 0x14 | 4 | u32 | nDims | number of dimensions (1 or 2 in corpus) | cited 0x44abae (→ entry+0x1C), 0x44abb4 |
| 0x18 | 4·nDims | u32[] | dims | sizes. Read in reverse: `stride[i] = Π word[5+nDims-k], k=0..i` (so the last-listed dimension varies fastest). The entry+0x20 array holds the cumulative products, and the total is the frame count | cited 0x44abc0–0x44abcf |
| …0x27 | | u32 | (unused dims) | 0 | unread beyond nDims |
| 0x28 | 4 | f32 | rate | frames per second. period = 1.0/rate (0x4bd3bc = 1.0) | cited 0x44ab98 → entry+0x14; used at 0x44a597–0x44a59d |
| 0x2C | 4 | u32 | flags | bit0 = auto-animate on a timer (0x44a58f). If bit0 is set, bit1 picks the looping driver 0x44b1b0 (0x44a593); otherwise 0x44b240 runs with callback 0x44adc0 ("texmgr" end hook). corpus: 0 (2847) or 3 (12) | cited 0x44aba8 → entry+0x18 |
| 0x30 | 16 | u32[4] | pad | **unread** (corpus 0) | unread |
| 0x40 | 8·N | char[8][N] | frames | 8-char frame stems. Each is copied into a 16-byte slot, NUL'd at byte 8, and gets '.map' appended | cited 0x44ac17 (memmove 8), 0x44ac2a, 0x44ac1d ('.map') |

The instance (0x44ac80, 0x48 bytes) holds +0x30 → the anim entry, +0x24.. the per-dimension index (zeroed), +4 the current frame name, +0x34 the loaded texture and +0x3C the dirty flag (2).
The image is loaded lazily by `0x4474b0` (0x44a60d). In the hardware path ([dev+0x3c]+8 == 1) it is loaded by `0x471980` (.m16) instead (0x44a5f0).

---

## 3. Images: .vqm + .cbk, .map, .m16

### Texture acquire `0x4474b0`
It strips the extension and appends '.vqm' (0x4474f7), then looks up the decoded cache (M=0x6D, 0x44755e).
If global 0x609564 ≠ 0 it loads the raw name (the .map) first (0x4475f1). Otherwise it checks that the .vqm exists (0x447609) and loads it (0x44762b). The codebook name is **read as a C string at vqm+8** (`lea esi,[edi+8]`, 0x447635; loaded 0x44763d; error "Codebook %s not found" 0x44764f).
It allocates `w*h+8` (0x4476d2–0x4476e4; on failure it evicts via 0x447e10, else prints "Texture cache overflow") and decodes with `0x44b430(vqm, cbk, out, w*h+0x18)` (0x447742).
If there is no .vqm it returns the raw .map buffer itself as the texture (0x447888). If 0x495060 is set, it post-processes with 0x471840 (0x44786e and 0x44789e).

### .vqm (corpus 6101/6101: `len == 0x18 + 2·⌈w/4⌉·⌈h/4⌉`)
| off | w | type | name | meaning | citation |
|---|---|---|---|---|---|
| 0x00 | 4 | u32 | w | width → out+0 | cited 0x44b437, 0x44b45b |
| 0x04 | 4 | u32 | h | height → out+4 verbatim. The decode uses `(h<<3)>>3` (top 3 bits are in-memory flags) | cited 0x44b45d–0x44b468 |
| 0x08 | 12 | char[12] | cbk | codebook filename, read as a C string (may fill all 12 bytes, see next row) | cited 0x447635 |
| 0x14 | 4 | u32 | unk | **unread** by 0x4474b0, 0x4478b0 and 0x44b430. **Meaning (corpus 6101/6101): `w & ~3`, and when the cbk name uses all 12 chars the low byte is 0.** The authoring tool strcpy'd the name, and its NUL terminator overwrote byte 0x14. That is why the unread word still acts as the name's terminator (0 / 256 / 512 values for 12-char names) | unread |
| 0x18 | 2·nb | u16[] | blocks | one per 4×4 block, raster order by 4-row strips, with partial blocks at the right and bottom edges. **bit15 set → solid block, all pixels = low byte**. Otherwise it indexes codebook tile `cbk+4+code*16+row*4+col` | cited 0x44b4ba, 0x44b4c5 (`and 0x8000`), 0x44b4d4 (fill), 0x44b4e5–0x44b4ec (tile) |

### .cbk (corpus 53/53: `len == 4 + 16n`)
| off | w | type | name | meaning | citation |
|---|---|---|---|---|---|
| 0x00 | 4 | u32 | n | tile count. **Unread** (the decoder has no bounds check) | unread |
| 0x04 | 16·n | u8[4][4] | tiles | row-major 4×4 palette indices | cited 0x44b4e8 (`[cbk + idx*16 + 4]`) |

### .map (raw 8-bit image; this is also the in-memory decoded-texture layout)
| off | w | type | name | meaning | citation |
|---|---|---|---|---|---|
| 0x00 | 4 | u32 | w | width | used as the texture header (0x42cd75, 0x42ee46) |
| 0x04 | 4 | u32 | h | height. Bits 29–31 are in-memory flags: bit30 = "processed" (tested 0x471a32, set 0x471b50–0x471b57), bit29 = listed in FULLRES.LST (0x471b3e–0x471b57), bit31 = has a 16-bit palette (0x42cd67, 0x42ee2b) | cited |
| 0x08 | w·h | u8 | pixels | palette indices, 0xFF = colour key (see bit 0x40) | inferred from 0x480557 |
corpus: 474/475 are exact `8+w*h` with top bits 0 (1 file is 8 bytes short; not investigated).

### .m16: acquire `0x471980(slot, name)`
It replaces the extension with '.m16' (0x4719da), checks existence (0x471a09) and loads it (0x471a1e). If bit30 of h is clear, it computes the FULLRES flag and sets `h = h & ~0x20000000 | (fullres|2)<<29` (0x471b3e–0x471b57).
Palette getter `0x42cd60`: `if (h & 0x80000000) return tex + 8 + w*((h<<3)>>3); else return default 0x52b91c` (0x42cd67–0x42cd84). The default palette is `malloc(0x204)` with `[0]=0x100` (0x4313e3, 0x4313f3), filled as **RGB565** from the 8-bit palette via masks 0xF800/0x7E0/0x1F (0x431e67/0x431e83/0x431e98), with entry 0 = 0.
| off | w | type | name | meaning | citation |
|---|---|---|---|---|---|
| 0x00 | 4 | u32 | w | width | 0x42ee46 |
| 0x04 | 4 | u32 | h\|flags | bit31 = palette follows (**confirmed**: `test ebp,0x80000000` at 0x42ee2b). corpus: top bits = 100b in every file | cited |
| 0x08 | w·h | u8 | pixels | indices into the file's own palette | inferred |
| 8+w·h | 4 | u32 | n | palette entry count | cited 0x42ef20 / 0x42ef3e |
| +4 | 2·n | u16 | palette | 16-bit colours. Copied n*2 bytes (0x42ef25–0x42ef3a) or, if a .tab is loaded, remapped `pal[i] = tab[pal[i]]` (0x42ef53–0x42ef5e). **RGB565** is inferred: the default palette of the same slot is RGB565 and .tab is defined in RGB565 (0x4ede88) | cited / inferred |
corpus: 225 files, all exact, n ∈ {255 (3087 members), 64, 1, …}.

---

## 4. Palettes and tables. Loaded by the WRLD chunk handler `0x4b8a10`
The WRLD chunk has name fields at +0x26 (palette), +0x33 (luma) and +0x40 (translucency), each 13 chars.
| file | size (corpus) | load | layout | citation |
|---|---|---|---|---|
| .act | 768 (67/67) | 0x4b8a37. 0xC0 dwords copied to 0x4fa170 (0x4b8a94), then `dev->SetPalette(dev, 0, 0x100, rgb, lum)` via [0x5dd2c4] (0x4b8a9b) | 256 × {R,G,B} u8. Byte order is proven by 0x42d970–0x42d983: byte[-2] → mask +0x10 (0xF800 = R), [-1] → G, [0] → B. Set-palette impls (0x42dbe0, 0x4345b0, 0x475a30, 0x48dc60) force entry 0 to (1,1,1) or (0,0,0) | cited |
| .lum | 65536 (35/35) | 0x4b8a57, passed to SetPalette → 0x4791e0 copies 0x4000 dwords to **0x61b2a0** (0x479242–0x47924c). If absent, it is synthesised by 0x4791e0 using 0x4796a0 | **[level][colour]**: index = level·256 + colour (**confirmed**). 0x47cc49 `and ecx,0x1f00` (level in the high byte, 32 levels used by the software spans) + colour in dl → `[edx+ecx+0x61b2a0]` at 0x47cc55 | cited |
| .tbl | 65536 (35/35) | 0x4b8acc. 0x4000 dwords copied to **0x60afa0** (0x4b8ae4–0x4b8af3). If missing: "Translucency table not found; disabled" (0x4b8af7) | **[src][dst]**: 0x47a4cf `mov ah,[esi+eax]` (source texel → high byte), 0x47a4d5 `mov al,[edi]` (framebuffer pixel → low byte), then 0x47a4da reads `[eax+0x60afa0]`. After load, `0x479780(dev,0xFF)` (0x4b8b1e) overwrites row 0xFF with 0x61afa0 (identity), so colour-key source 0xFF leaves dst unchanged | cited (the src/dst roles are inferred from the edi store pattern) |
| .tab | 131072 (29/29) | `0x42d800(pal,out16,1,fmt)`: name = current mission name (0x404c90) with its extension replaced by '.tab' (0x42da44). It is used only if the size is **exactly 0x20000** (0x42da62), and 0x8000 dwords are copied to the buffer at [0x608660] (0x42da7e). Otherwise identity (i→i). If the device masks differ from RGB565 (0x4ede88 = F800/7E0/1F/0), every entry is converted | **65536 × u16, indexed by an RGB565 colour, giving an RGB565 colour** (a per-mission colour-grade for 16-bit palettes). It is **not** [level][palette index]. Applied at 0x42ef5a `mov bx,[edi+ebx*2]` to each .m16 palette entry | cited. The schema text in other_formats.py (`TAB`) is wrong |

---

## Proposed exe function names
| addr | current | proposed | evidence |
|---|---|---|---|
| 0x446c90 | new_geometry | geo_Parse (keep new_geometry) | 'OEG.' check 0x446c9b, error string at 0x4471ce |
| 0x4469a0 | FUN_ | geo_Acquire | name hash → 0x52fb60 bucket, load/parse/release 0x446a3e–0x446a9e, refcount +8 |
| 0x4796a0 | FUN_ | pal_NearestIndex | squared-distance search over 0x6432e0 (768 B), 32³ cache 0x63b2e0 |
| 0x44a290 | FUN_ | tex_ResolveFaceTexture | '.map' vs other extension branch, tmt parse, image load 0x44a60d |
| 0x44ab90 | FUN_ | tmt_Parse | reads +0x14/+0x28/+0x2C, names at +0x40 |
| 0x44ac80 | FUN_ | texanim_NewInstance | 0x48 alloc, dirty=2, hash M=0x71 |
| 0x4474b0 | FUN_ | tex_Acquire (vqm/map) | '.vqm', codebook load, 0x44b430 |
| 0x4478b0 | FUN_ | tex_DecodeInto (size query + decode into caller buffer) | returns the size through *param_3 |
| 0x44b430 | FUN_ | vqm_Decode | 4×4 block / 0x8000 solid logic |
| 0x471980 | FUN_ | m16_Acquire | '.m16', FULLRES flag |
| 0x471840 | FUN_ | tex_MarkFullRes | FULLRES.LST bitset (M=0x6CD) → h bit29/30 |
| 0x42cd60 | FUN_ | tex_GetPalette16 | 0x80000000 test, default 0x52b91c |
| 0x42ede0 | FUN_ | tex_Upload16 (inferred) | builds a 16-bit palette with the .tab remap and hands it to the renderer |
| 0x42d800 | FUN_ | pal_Build16_LoadTab | RGB565 build, '.tab' load |
| 0x4791e0 | FUN_ | pal_SetShadeTable (lum) | copy → 0x61b2a0 |
| 0x479780 | FUN_ | tbl_SetRowIdentity | row param_2 of 0x60afa0/0x62b2c0 := 0x61afa0 |
| 0x471f20 | FUN_ | raster_Wireframe | line per edge (0x48d2e0) |
| 0x47c2f0 | FUN_ | raster_SetupTextured | UV clamp (0x02), perspective (0x10) |
| 0x45cbe0 | FUN_ | geo_EmitFacesSorted (inferred) | mode lookup, runtime plane-tree insert |
| 0x48f570 | FUN_ | geo_DrawFacesDirect (inferred) | mode lookup, draws through 0x4260d0 / 0x471fd0 |

## Bytes no loader reads
- .geo header: 0x04 unk0, 0x08 name[16], 0x20 unk1.
- .geo face: 0x00 index, 0x1B a, 0x2F b (only copied as padding), 0x33 c.
- .tmt: 0x00, 0x13, and 0x30..0x3F. Bytes 0x04..0x12 are overwritten, not read.
- .vqm: 0x14.
- .cbk: 0x00 n.
- .act/.lum/.tbl/.tab have no headers, so every byte is consumed.

## Open items
- .geo unk0: meaning unknown (no reader, and no corpus correlation found).
- Render bit 0x20, plus the 0x100 half of the mode tables.
- The .m16 pixel → palette mapping, and RGB565 inside the renderer DLL, are inferred (the DLL consumes them).
