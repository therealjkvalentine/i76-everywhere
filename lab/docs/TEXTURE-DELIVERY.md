# Texture delivery into the original game: routes, size ceiling, TMU memory (static read, 2026-10-03)

Question (owner, upscaling sprint U5): the owner plays the original game (`-glide`: ZGLIDE.DLL -> dgVoodoo 2.87.3,
120 fps, widescreen). How do upscaled textures get into that game, and how big can they be?

**Answer in short.**

- **Ceiling: 256 texels per side, aspect 8:1..1:8, through every route that keeps dgVoodoo.** Glide 2 has no LOD
  above GR_LOD_256 and ZGLIDE's size scan only looks at bits 8..0 of the width (section 1). 5,341 of the 5,419 M16
  tiles in the `*6.pak` packs are 128 px or smaller on the long side, so **2x is available for 98.6% of the hardware
  textures** (vehicle panels 128x64 -> 256x128, roofs 128x128 -> 256x256), 4x for 2,294 of them (64x64 and smaller).
  The 225 loose `.m16` files (dash, terrain level 0, sky: all 256x128 or 256x256) have **no** headroom.
- **UVs are normalised; nothing on the Glide path assumes a texture's size.** The exe hands ZGLIDE `{w, h, pixels,
  palette}` straight from the M16 header (0x431ca0); ZGLIDE derives LOD and aspect from w, h per upload and turns
  the vertex UV (0..1) into Glide's 0..256 range with an aspect factor (0x10002b9b). A 128x64 panel shipped as
  256x128 keeps its UVs. (The texture *halving* and the 128 px square clamp people remember from `-d3d` live in the
  exe's Direct3D texture manager, 0x42f5f0, and never run under Glide.)
- **TMU memory is the real constraint.** ZGLIDE bump-allocates TMU memory, then recycles the oldest resident texture
  **of the same width and height**, and when no same-size victim exists it draws that polygon with the wrong texture
  and flushes the whole texture cache on the next frame (at most once per 21 frames). At 2 MB a 2x pack will hit
  that far more often. dgVoodoo's `MemorySizeOfTMU` can report more, but ZGLIDE has a bug that corrupts textures
  above 4 MB; a **one-byte ZGLIDE patch** fixes it (section 2).
- **Recommended route: (a) M16 re-encoded at 2x as loose ADDON packs**, plus the one-byte allocator fix and a
  larger `MemorySizeOfTMU` once the live test says the 2 MB belief was about the allocator. Low effort (the M16
  encoder and ADDON override are proven since July), good odds. A proxy-level texture shim (b) is the follow-on if
  palette-indexed (VQM/MAP) textures or 16-bit colour beyond 255 per tile are wanted; it does not raise the ceiling.

**Live result (2026-10-03, n = 1 per condition, t01, game-tex):** the 2x marker packs of the Piranha **render
correctly**: every body panel shows the 1-texel magenta border, X and fine checker that only a 256x128 texture can
carry, in the right place on the car (UVs correct), with the art otherwise unchanged; the control run shows stock paint.
The same with `MemorySizeOfTMU = 16384` + the one-byte ZGLIDE fix: renders the same, no corruption, no crash. t01 is a light
scene (6 entities, 2 s of chase view), so this proves the size path, not TMU behaviour under load; whether dgVoodoo
took 16384 was not read back. Section 5.

## 0. Files read

| tag | file | md5 |
|---|---|---|
| exe | `i76-uncap-lab\game\i76.exe` (AiO, = `game-tex`) | 85de44a7136979d7730800eeba8ca6cf |
| ZGLIDE | `i76-uncap-lab\game\ZGLIDE.DLL` (base 0x10000000, has relocations) | 05c1dde499cd8da3248557a76ba42f31 |
| dgVoodoo Glide | `i76-uncap-lab\game\Glide2x.dll` (dgVoodoo 2.87.3) | 8af442bc7718a792c0573b34bfddca78 |
| archive | `game-tex\I76.ZFS` (hard link of `game-alt`'s), read with `i76-map\tools\i76fmt\zfs.py` | - |

Tools: pefile + capstone scratch scripts. Prior reads this builds on: `TEXTURE-AND-OBJECT-LOD.md` (mipmaps off,
0x10001964), `CLUTTER-AND-MIRROR.md` (0x44a740, mirror texture), `i76-map\data\notes\art.md` (M16 layout,
FULLRES.LST), `i76-everywhere\docs\HD-TEXTURES-RESEARCH.md` (July pack, ADDON override).

## 1. Size: what the Glide path accepts

**Exe -> ZGLIDE.** ZGLIDE's exports are bound by name into 0x608ba8.. (0x426a1c..0x426ade): FirstDevice 0x608ba8,
Render 0x608bb0, SetState 0x608bc0, SetTexturePalette 0x608bc4, PreloadTexture 0x608bd4 (stored, **never called**:
its only reference is the store), UpdateTexture 0x608be4 (called once, 0x431cf5). Textures reach ZGLIDE as a
descriptor built per call, e.g. `renderer_UploadTexture` 0x431ca0:

```
00431cb8  mov edx, [eax+4]        ; h | flags  (M16 header, bits 29..31 are in-memory flags)
00431cbb  mov ecx, [eax]          ; w
00431cbd  shl edx, 3 / sar edx, 3 ; strip the flags
00431cc4  lea ecx, [eax+8]        ; pixels follow the header
00431cd2  call 0x42cd60           ; the tile's own 16-bit palette (h bit 31) or the default
00431cec  mov [eax+0x10], 0xff    ; colour key index
```

w and h come from the file. No caller clamps or rounds them.

**ZGLIDE.** Texture setup 0x10001930 (and the same code in the bind path 0x10001470):

```
10001940  mov ecx, 8 / mov edx, 1 / shl edx, cl / test eax, edx / jne / dec ecx / jns   ; highest set bit of w, from bit 8 down
1000195c  sub edx, ecx            ; largeLod = 8 - log2(w)   (GR_LOD_256 = 0)
100019b9  sub eax, ecx / add eax, 7 / cmp eax, 0xe / ja      ; aspect index = log2 w - log2 h + 7
100019c5  jump table 0x10001b7c   ; sets the s/t scale floats [0x1001a030]/[0x1001a034] to 1, 1/2, 1/4, 1/8
10001a6a  [esi+0x14] = 0xa (RGB_565) / 0xb (ARGB_1555) / 5 (P_8)
```

A 512-wide texture has no bit in 8..0, the loop ends at ecx = -1 and largeLod = 9, which is not a Glide 2 LOD.
So 256 is the hard ceiling in ZGLIDE as well as in the Glide 2 API that dgVoodoo implements.

The I'76 device descriptor (0x431451..0x4314ad) sets flags 0x300 at desc+8, so FirstDevice takes the
`[0x1001fd24] = 1` branch (0x10001c87): **every texture is converted to ARGB1555** (0x10001126..0x100011b5:
index 0xFF -> 0x0000 transparent, else palette RGB565 -> 1555). 2 bytes per texel in the TMU. The slot list holds
desc+0x28 = 0x400 = 1,024 textures (0x10004770).

**UVs.** Render's vertex setup (0x10002b9b..0x10002bc6 and 0x10002c67..0x10002cac):

```
s = u * [0x1001a030] * oow * 255.0      ; [0x100181a0] = 255.0
t = v * [0x1001a034] * oow * 255.0
```

Glide coordinates span 0..256 on the long side whatever the LOD, scaled by aspect. The exe's u, v are therefore
normalised (0..1 across the texture: terrain uses sample x 0.125 = one repeat per 8 samples, renderer.md 0x490f6f).
Doubling w and h keeps the aspect, the scale factors and every UV: **a 2x M16 is a drop-in at this layer.**

**Exe side, what does assume sizes** (none on the M16 -> Glide path):

- `renderer_DDraw*` texture manager 0x42f5f0 (the `-d3d` back end only): halves every dimension above 32 when the
  card reports less than 0x249f00 bytes (2.4 MB) of texture memory (0x42fb40, from IDirectDraw2::GetAvailableVidMem
  0x42faf5) unless the texture is in `FULLRES.LST` (h bit 29, set by 0x471b3e); clamps to a 128 px square when a device caps bit 0x20
  is set (0x42d263; read as D3DPTEXTURECAPS_SQUAREONLY, not confirmed). It packs w and h into 9-bit fields (0x42f675). Never reached
  under `-glide`.
- The mirror texture (`ZMIRI101.MAP`, 256x64) is a private writable copy (0x44a740) the software rasteriser draws
  into: a different mechanism, not a file replacement target.
- The decoded-texture heap `HeapCreate(..., max 0x36b000 / 0x500000 / 0x600000)` (0x447456..0x447482) is the VQM
  decode cache. `.m16` files are loaded whole through the file layer (0x46ffc0 in 0x471a1e), not into that heap.
  Not verified under load with 4x larger M16 files: worth watching in the live test.

## 2. TMU memory: how ZGLIDE manages it

All texture memory traffic is in ZGLIDE; the exe never calls PreloadTexture.

| step | code | behaviour |
|---|---|---|
| start | FirstDevice 0x10001e70 | next free `[0x1001fd20]` = `grTexMinAddress(tmu)`; TMU count `[0x1001fd40]` = `nTexelfx` from `grSstQueryHardware` (0x10001d83); 2 MB boundary `[0x1001f898]` = 2 (0x10001c26) |
| bind | 0x10001850 | binary search of the resident list by pixel pointer; hit -> stamp age, `grTexSource` |
| miss, room | 0x10001930 | `need = grTexCalcMemRequired(...)`; 2 MB boundary rule (below); fail if `next + need > grTexMaxAddress(tmu)`; else `grTexDownloadMipMap(next)`, `next += need` (8-byte aligned) |
| miss, full | 0x10001320 | if another TMU is left (`[0x1001f894] < [0x1001fd40]`): switch TMU, next = 0, retry. Else **reuse the oldest resident texture with the same w and h** (0x10001392..0x100013ab: `[eax+0x24] == w && [eax+0x28] == h`, smallest age) and download into its address |
| no victim | 0x100018f3 | `[0x10178ea0] = 1`; the polygon is drawn with whatever texture is bound |
| next frame | RefreshDisplay 0x10002ec0 | if the flag is set and the 20-frame cooldown is clear: **flush everything** (0x100017f0: next = min address, every slot freed) |

The 2 MB boundary rule in 0x10001930 (a Voodoo 1 restriction; a texture may not straddle 2 MB):

```
10001a8a  mov eax, [0x1001fd38] / test eax, eax
10001a93  jne 0x10001ab9                 ; 75 24  - skip (only PreloadTexture sets fd38)
10001a95  mov ecx, [0x1001f898] / shl ecx, 0x14 / cmp edi, ecx / jle
10001aa7  mov dword [0x1001fd20], 0x200000   ; next free = 2 MB, always
10001ab1  [0x1001f898] += 2
```

The rewind target is the constant 2 MB, not the boundary just crossed. With 2 MB of TMU the allocator never gets
past 2 MB, so the bug is harmless. With 4 MB the second boundary is never crossed either (an allocation that would
end past the top fails the `grTexMaxAddress` check first). **Above 4 MB, the first upload that crosses 4 MB rewinds
the allocator to 2 MB, onto textures the slot list still holds as resident**: later uploads overwrite live textures
(wrong textures on screen, the same failure kind as the July "post-explosion texture corruption" note). Under
dgVoodoo the boundary rule protects nothing. Fix: `0x10001a93 75 24 -> eb 24` (always skip), relative, one byte,
no relocation. `tools\upscale\zglide_tmu_patch.py` writes a patched copy; section 6 has the proxy form.

Two cautions on the "MemorySizeOfTMU = 2048 is load-bearing" note (VOGONS t=70951, reconfirmed July at wrapper
level): (1) the static read predicts 4096 is safe with stock ZGLIDE, and >4096 is safe only with the patch;
(2) the TMU-switch path (0x10001355..0x10001367) never switches back and never resets `[0x1001f898]`, and
FirstDevice sets up texture combine for TMU 0 only, so **NumberOfTMUs = 1 is what is really load-bearing**: with two
TMUs (dgVoodoo's voodoo_2 default) every texture uploaded after TMU 0 fills goes to TMU 1 and draws wrong. Which of
the two caused the original report is unknown; the live test settles it.

**Budget arithmetic** (ARGB1555, 2 bytes per texel): a 128x64 panel is 16 KB, at 2x 64 KB; a 256x256 tile 128 KB.
The Piranha's `pirana16` set (38 tiles, three damage states) is about 0.55 MB in the TMU at 1x and 2.2 MB at 2x,
of which roughly a third is on screen at a time. So the player's car alone at 2x fits the 2 MB TMU with the rest of
the scene (terrain 256x256 + 2 x 64x64 + 32x32 + 16x16, the 256x128 dash tiles, the other cars); a full 2x roster
does not, and would run on same-size recycling plus periodic full flushes. `grTexMaxAddress` under dgVoodoo and the
largest `MemorySizeOfTMU` it accepts for `voodoo_graphics` were not read: probe them (section 6, readback).

dgVoodoo `[Glide]` keys (the conf in use, `i76-everywhere\dgVoodoo.conf` comment block): `VideoCard`
(voodoo_graphics, voodoo_rush, voodoo_2, voodoo_banshee, other_greater), `OnboardRAM` (MB, frame buffer),
`MemorySizeOfTMU` (kB), `NumberOfTMUs`, `TMUFiltering` (appdriven, pointsampled, bilinear), `DisableMipmapping`,
`Resolution`, `Antialiasing`, `EnableGlideGammaRamp`, `ForceVerticalSync`, `ForceEmulatingTruePCIAccess`,
`16BitDepthBuffer`, `3DfxWatermark`, `3DfxSplashScreen`, `PointcastPalette`, `EnableInactiveAppState`. None does
texture replacement, LOD bias or forced mipmaps.

## 3. Delivery routes

| route | max size | colour | effort | risks | odds |
|---|---|---|---|---|---|
| **(a) M16 re-encode at 2x/4x into loose `ADDON\<car><scheme>6.pak/.pix`** | 256 per side: 2x for 98.6% of pack tiles, 4x for 42% | per-tile palette of 255 RGB565 colours (stored as 1555) | low: `i76img.encode_m16` / `build_m16`, `texture-lab\enhance_cars_m16.py` (same-res today: drop its resize), `tools\upscale\m16_scale_marker.py`; ADDON override proven July (melee Leprechaun magenta probe) | TMU thrash/flush with many 2x textures at 2 MB; the 255-colour quantisation of an upscaled tile can band; the whole pak must be rewritten (no per-tile override); 4x larger files in RAM | high for one car (static path has no size assumption); medium for a full roster until the TMU change is tested |
| **(b) proxy shim on ZGLIDE's glide2x imports** (the proxy already IAT-patches ZGLIDE's `_grSstWinOpen@28` on load, strlkproxy.c `hook_LoadLibraryA`) | 256 per side | full 16-bit per texel (1555 or 4444 for soft alpha), no palette | medium-high: hash on `grTexDownloadMipMap`, PNG pack lookup, and a **proxy-owned TMU allocator** (ZGLIDE sizes its slots from the original LOD, so a bigger replacement would overwrite the next texture; the shim must present virtual addresses to ZGLIDE and map them to its own LRU over real TMU space via `grTexMinAddress`/`MaxAddress`/`CalcMemRequired`/`DownloadMipMap`/`Source`) | allocator bugs show as wrong textures; hashing cost per upload (fine: uploads are rare outside flushes); hashes of palette-indexed textures differ per level palette (which is also what makes them safe at night) | medium; the only route that covers VQM/MAP-sourced textures without the July night-palette breakage |
| (c) OpenGLide-HD (`i76-everywhere\tools\openglide-hd`) | any (GL textures) | 32-bit | high: unverified end to end since July; replaces dgVoodoo, so the widescreen, u32x, 120 fps, MSAA and gamma work does not carry over; 640x480 window, 256COLOR shim, DDraw collision at boot (RENDERER-ALTERNATIVES.md) | daily-driver regression | low as a daily driver |
| (d) exe loader hook on `m16_Acquire` 0x471980 (swap the file buffer by name) | 256 (same downstream path) | as (a) | low-medium | none beyond (a); saves rebuilding whole paks | as (a); only worth it if per-tile packs matter |
| (e) a glide2x wrapper between ZGLIDE and dgVoodoo | 256: dgVoodoo's Glide 2 has no larger LOD | as (b) | as (b) | as (b) | same as (b), more plumbing |

There is no route past 256 that keeps dgVoodoo's Glide. Past 256 needs a renderer that is not Glide 2 (OpenGLide-HD,
or a new D3D11 back end for the exe's plugin interface: Render / UpdateTexture / SetState, about 20 exports).

## 4. What to upscale first, by value per TMU byte

1. Vehicle body panels 128x64 (2,366 tiles) and roofs 128x128 (660): 2x. The chase view shows them at 200..800
   screen pixels across on a 4K-rendered frame, so 128 texels is badly under-sampled today.
2. 64x64 / 64x32 parts (1,699): 2x or 4x.
3. Terrain levels 1..4 (64, 64, 32, 16 px): they only show past 50 m, and `I76_TERRAIN_TEX` already pulls the 256 px
   level out further; upscaling them adds memory for little.
4. Not possible: terrain level 0, the dash, sky and horizon strips (all 256 already).

## 5. The in-game test (run 2026-10-03 13:35)

Purpose: one live answer to "does a 2x M16 render, with correct UVs, at 2 MB TMU?", and in a second run, "does
16 MB TMU with the allocator fix run clean?"

Prepared in the lab copy `game-tex` (made with `tools\renderers\make-renderer-copy.ps1 -Source ..\..\game-alt
-Dest ..\..\game-tex -HardLinkAssets`; `game`, `game-dd-20261003` and `C:\Users\james\Games` untouched):

- `game-tex\ADDON\pirana16/26/36/46.pak/.pix`: every tile of all four Piranha paint schemes at 2x (128x64 ->
  256x128, 8x8 -> 16x16, ...) by pixel replication, with a magenta marker drawn at the new resolution: a 1-texel
  border, a 1-texel X and a 1-texel checker over the top-left quarter. At 2x those lines are half an original texel
  wide: no 1x texture can show them. Built by `i76-everywhere\tools\upscale\m16_scale_marker.py` (index-level,
  flags byte 0x80 kept; all 152 tiles re-parse cleanly).
- `game-tex\ZGLIDE.tmufix.dll` (md5 a34db025..., one byte at RVA 0x1a93) and `game-tex\dgVoodoo.tmu16.conf`
  (`MemorySizeOfTMU = 16384`, otherwise the copy's conf) for run 3. Neither is active by default.
- Runner: `i76-everywhere\tools\upscale\run-tex-scale-test.ps1` takes the console per `CONSOLE-LOCK.md` (exclusive
  `.console-owner`, no i76 running, no `.console-test.lock` in game / game-alt / game-dd-20261003; released in
  finally), boots t01 through `autotest\proxy-run.ps1 -GameDir game-tex -KeepInstalledDll`, and captures the frame
  at start, after F3 and after F4 (preset views; one of them is the chase view) to `captures\texscale\`.

Runs, in order (about a minute each):

| # | command | expect if the route works |
|---|---|---|
| 1 | `.\run-tex-scale-test.ps1 -Control` | stock Piranha paint (the 2x packs are moved aside for the run) |
| 2 | `.\run-tex-scale-test.ps1` | thin magenta border + X + fine checker on every Piranha panel, art otherwise unchanged and in place |
| 3 | `.\run-tex-scale-test.ps1 -Tag tmu16 -Conf C:\Users\james\i76-uncap-lab\game-tex\dgVoodoo.tmu16.conf -ZglideFix` | as run 2, no texture corruption |
| 4 (optional) | as 3 without `-ZglideFix` | the static read predicts corruption once uploads pass 4 MB (needs a busy scene, e.g. 60 s of driving; t01 may not get there) |

**Result.** Captures `captures	exscale61003-133505-marker2x-*`, `-133532-control-*`, `-133558-tmu16-*` (start,
F3, F4; F3 and F4 both show a chase view; a Windows Firewall prompt for game-alt's i76.exe, raised by another agent's
multiplayer run, covered the screen centre in every capture, but the car below it is clear):

| run | booted | Piranha panels |
|---|---|---|
| control (packs moved aside) | in mission after 10 s | stock orange/black paint |
| marker2x (2 MB TMU, stock ZGLIDE) | in mission after 10 s | thin magenta border, X and checker on every visible panel (hood, front, roof, fenders) at sub-original-texel width; the art keeps its place; no wrong or missing textures |
| tmu16 (16384 kB + ZGLIDE 0x1a93 fix) | in mission after 10 s | the same as marker2x |

So a 256x128 M16 replacing a 128x64 one is accepted end to end (exe file layer, ZGLIDE LOD/aspect, dgVoodoo) with
correct UVs. Not shown: behaviour under TMU pressure (a full 2x roster in a busy mission), and the TMU readback.
Harness note: the first attempt used `proxy-run -KeepInstalledDll`; game-alt's (and so game-tex's) STRLKUP.DLL is the
August music-only proxy (md5 54f2de9d) with no `I76_MISSION` boot, so all three runs sat in the shell. The runner now
installs a pinned copy of the sandbox proxy (`game-tex\Strlkup.u5test.dll`, md5 0b18d77c) through `-Dll`.

Reading the result: only the top-left quarter of each panel, magnified = UVs in texels (not expected); stock paint
in run 2 = the t01 car is not a Piranha or the scheme differs (check `t01.msn`'s player car, or test in melee);
white, black or wrong textures = size rejected or allocator failure; crash = read the proxy log `CRASH` line.

## 6. Proposed proxy code (for strlkproxy.c's owner; not applied here)

Two pieces, both on the existing `hook_LoadLibraryA` ZGLIDE branch (strlkproxy.c, `I76_GLIDE_DIR` / glide-refresh):

```c
/* I76_ZGLIDE_TMUFIX=1: ZGLIDE 0x10001930 rewinds its TMU allocator to 2 MB at every 2 MB boundary after the
 * first, corrupting resident textures when MemorySizeOfTMU > 4096. Skip the (Voodoo 1 only) boundary rule:
 * RVA 0x1a93 75 24 (jne) -> eb 24 (jmp). Relative, so no relocation fix-up; bytes verified before and after. */
static void zglide_tmufix(HMODULE z) {
    BYTE *p = (BYTE *)z + 0x1a93; DWORD old;
    if (p[0] != 0x75 || p[1] != 0x24) { mlog("  zglide-tmufix: bytes %02x %02x, expected 75 24 - NOT applied", p[0], p[1]); return; }
    if (!VirtualProtect(p, 1, PAGE_EXECUTE_READWRITE, &old)) { mlog("  zglide-tmufix: VirtualProtect failed - NOT applied"); return; }
    p[0] = 0xeb; VirtualProtect(p, 1, old, &old); FlushInstructionCache(GetCurrentProcess(), p, 1);
    mlog("  zglide-tmufix: 0x1a93 %s", p[0] == 0xeb ? "eb 24 (applied, read back)" : "write did NOT land");
}

/* I76_TEX_STATS=1: readback + census. grTexMaxAddress proves which MemorySizeOfTMU dgVoodoo actually took;
 * the download count per second and full flushes (grTexMinAddress calls after FirstDevice) show TMU pressure. */
static FxU32 (__stdcall *p_grTexMaxAddress)(GrChipID_t);
static FxU32 (__stdcall *p_grTexMinAddress)(GrChipID_t);
static void  (__stdcall *p_grTexDownloadMipMap)(GrChipID_t, FxU32, FxU32, GrTexInfo *);
static volatile LONG g_tex_dl, g_tex_bytes, g_tex_flush;
static FxU32 __stdcall hook_grTexMaxAddress(GrChipID_t t) { FxU32 r = p_grTexMaxAddress(t); static int once;
    if (!once++) mlog("  tex-stats: grTexMaxAddress(%lu) = 0x%lx", (unsigned long)t, (unsigned long)r); return r; }
static FxU32 __stdcall hook_grTexMinAddress(GrChipID_t t) { InterlockedIncrement(&g_tex_flush); return p_grTexMinAddress(t); }
static void __stdcall hook_grTexDownloadMipMap(GrChipID_t t, FxU32 a, FxU32 eo, GrTexInfo *i) {
    InterlockedIncrement(&g_tex_dl); /* + bytes from i->largeLod/aspect/format; log totals once a second from the frame hook */
    p_grTexDownloadMipMap(t, a, eo, i); }
/* in hook_LoadLibraryA, ZGLIDE branch:
 *   p_grTexMaxAddress = patch_iat(m, "glide2x.dll", "_grTexMaxAddress@4", hook_grTexMaxAddress);
 *   p_grTexMinAddress = patch_iat(m, "glide2x.dll", "_grTexMinAddress@4", hook_grTexMinAddress);
 *   p_grTexDownloadMipMap = patch_iat(m, "glide2x.dll", "_grTexDownloadMipMap@16", hook_grTexDownloadMipMap); */
```

(GrTexInfo / FxU32 are the Glide 2 types; the proxy can declare a 4-dword struct. `grTexMinAddress` is called
once in FirstDevice and once per flush, 0x100017f7, so `g_tex_flush - 1` per mission = full flushes.)

The full shim of route (b) is the same hook set plus a proxy-owned allocator; spec it only after the census says
2x textures need more than the TMU can give.

## 7. Could not be determined statically

- dgVoodoo's `grTexMaxAddress` value and the largest `MemorySizeOfTMU` it accepts for `voodoo_graphics` (readback).
- Whether the t01 player car is a Piranha and which paint scheme (all four are covered).
- What actually caused the original ">2 MB TMU crashes/corrupts" report: the 4 MB rewind (section 2) or two TMUs.
- TMU working set of a real mission at 1x and 2x (the census above).
- Whether 4x larger M16 files stress the file cache under load (watch memory in run 2/3).
