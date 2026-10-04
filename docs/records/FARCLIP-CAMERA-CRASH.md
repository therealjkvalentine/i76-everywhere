# Far clip x camera crash: the terrain edge records index vertices with an int16

**2026-10-02, sandbox only** (`C:\Users\james\i76-uncap-lab\game`, console free, one game at a time, proxy installed and
restored per run by `i76-map\verify\run_scenario.py`, sandbox left as found: `STRLKUP.DLL` md5 54f2de9d, no lock, no
`.pretest`). Repro: `i76-map\verify\scenarios\camera-farclip.json` (t01 direct boot, F1, F6 hood view 3 s, F1, B binoculars
3 s, B off, idle to 45 s), run with `--exe` and the new `--env I76_FAR_CLIP=<m>` switch. Runs under
`i76-map\verify\runs\camera-farclip\<ts>\` (actions.csv, manifest.json, mciproxy.log with the proxy's `CRASH:` lines).

**Live state first** ([check which build is live]): `patch-farclip.ps1 -Status` on the sandbox reads **far-clip PATCHED ->
8000 m, render pools ENLARGED 128x (arena 64 MB)**, not the 5000 m / 16x that DRAW-DISTANCE.md and the brief say. The
file-patched exe (md5 4fabc303) is what runs 4 and 5 below exercised.

## Result in one paragraph

The crash is **not** the depth-bucket ceiling (3796 m), not `camera_Init`'s 100..100000 clamp, and not the draw-record
arena. It is a **16-bit vertex index**: `renderer_SplitTerrainEdge` 0x4918f0 stores each new terrain vertex's index
(`DAT_006442ec`, the per-frame transformed-vertex count) into the 12-byte edge record as a `short`, and reads it back with
`movsx`. The terrain tessellation is quantised in whole subdivision levels, each about 3.8x the vertices of the one below
(t01: ~1.4k / ~4.5k / ~16.9k / ~65.2k). The level a frame lands on depends on the far clip **and the camera**: the hood view
(fov 120 deg, `camera_EnterHoodView` passes 2.0943952) sits one level above the cockpit, binoculars (zoom 8.0, the clamp
maximum in 0x472400) two levels above. Whenever a view reaches the 65k level the count passes 32,767, the stored index
wraps negative, `fld [esi+8]` reads ~60 KB below the vertex pool and the game dies with 0xC0000005 at **exe+0x91919**.
The enlarged pools made this reachable (the stock 9,000-vertex pool overflowed first, at 0x491a11, DRAW-DISTANCE.md);
no pool size helps because the index type is the limit. **Safe range on t01: I76_FAR_CLIP <= 2500 m** (2500 survives all
three views, 2750 crashes binoculars). **The launcher's 1800 is safe** (binoculars peak 17,068 vertices, 52% of the
ceiling, and the same tessellation level as 2500).

## Matrix

Every run: t01 direct boot (`I76_MISSION=t01.msn`, stock20 profile), hand-over at ~27 s, then the scenario above.
"verts" = peak of `[0x6442ec]` per camera callback, sampled read-only at ~1 kHz from a side process (`vertsample.py`,
scratch; 0x4c2730+0x34 = zoom) - available only on the runs marked (s).

| # | exe | I76_FAR_CLIP | proxy far-clip line | F6 hood (0x407680) | B binoculars (0x4071a0) | verts cockpit / hood / binoc | run |
|---|---|---|---|---|---|---|---|
| 1 | i76_pristine_fix.exe | - (600 in file) | - | survive | survive | - | 142046 |
| 2 | i76_pristine_fix.exe | 1800 | `on (1800 m, pools x16, 6/6 sites)` | survive | survive | - | 142230 |
| 3 | i76_pristine_fix.exe | 5000 | `on (5000 m, ... 6/6 sites) - note: depth buckets ...` | survive | **CRASH** frame 790, same frame as B | - | 142402 |
| 4 | i76.exe (file: 8000 m, 128x) | - | - | **CRASH** frame 632, same frame as F6 | (not reached) | - | 142516 |
| 5 | i76.exe (file: 8000 m, 128x) | 600 | `pool constant 0 differs - not applied` | **CRASH** frame 635 | (not reached) | - | 142619 |
| 6 | i76_pristine_fix.exe | 3700 | on, 6/6 | survive | **CRASH** frame 798 | - | 142740 |
| 7 (s) | i76_pristine_fix.exe | 3700 | on, 6/6 | survive | **CRASH** frame 804 | 4,595 / 16,920 / **65,196** (zoom 8.0) | 143106 |
| 8 (s) | i76_pristine_fix.exe | 1800 | on, 6/6 | survive | survive | 1,480 / 4,499 / 17,068 | 143324 |
| 9 (s) | i76_pristine_fix.exe | 2500 | on, 6/6 | survive | survive | 1,427 / 4,499 / 17,595 | 143513 |
| 10 (s) | i76_pristine_fix.exe | 3000 | on, 6/6 | survive | **CRASH** frame 814 | 4,577 / 16,919 / **65,198** | 143659 |
| 11 | i76_pristine_fix.exe | 2750 | on, 6/6 | survive | **CRASH** frame 825 | (sampler missed the start) | 144221 |

Notes on the matrix:

- **Run 5 could not test the override.** `apply_far_clip` refuses when any of the five pool constants at 0x402f99..0x402fd0
  differs from stock (strlkproxy.c: "pool constant %d differs - not applied"), and the file patch has already multiplied
  them by 128. The in-memory read site is therefore left alone and the file's 8000 m imm stays. The pristine_fix series
  answers the question instead: the far value alone (600 -> 1800 ok, 3000+ binoculars crash, 8000 hood crash) decides.
- **3900 was not run**: the brief's "test 3700 and 3900 if 1800 survives and 5000 crashes" assumed the bucket ceiling
  (3796 m) was the knee; 3700 already crashes (run 6), so the knee is below it, and the bisect went 2500 / 3000 / 2750.
- The pristine_fix runs also log a `CRASH` **at shutdown** (`0x77027B71`, ntdll, frame 1474 state 2, after WM_CLOSE: the
  known exit-code 0xC0000005 on quit). Not this bug; listed so nobody reads it as one.
- Earlier evidence (verify\README.md): camera-cycle 131502 / camera-hood 131634 / camera-binoc 132251 on the sandbox
  i76.exe, 4/4 crashes, before the crash logger existed.

## The CRASH lines

```
run 4  (i76.exe, file 8000 m, F6)
CRASH: code 0xC0000005 at 0x00491919 (exe+0x91919) read addr 0x7DE41008 | eax FFFFEC01 ebx 7A0D0BB8 ecx 7DE50000 edx 000296D5 esi 7DE41000 edi 7A0D0C48 ebp 7A0D0BD0 esp 0012DC18 | frame 632 state 5 cam cb 0x00407680 mode 1
CRASH: stack 7A0D0BB8 7A0D0BD0 7A0D0C48 7A0D0B7C 00000000 00000000 004916E7 7A0D0C48 7A0D0AE0 7A0D0BAC 7A0D0B34 7A0D0B1C C5460000 4A3DF75A 44566872 7DEAFF94

run 5  (i76.exe, file 8000 m, I76_FAR_CLIP=600 not applied, F6)
CRASH: code 0xC0000005 at 0x0049191F (exe+0x9191F) read addr 0x7DE41008 | eax FFFFEC00 ebx 7A0D2194 ecx 7DE50000 edx FFFFC400 esi 7DE40FF4 edi 7A0D2224 ebp 7A0D21AC esp 0012DC6C | frame 635 state 5 cam cb 0x00407680 mode 1

run 3  (pristine_fix, 5000, B)
CRASH: code 0xC0000005 at 0x00491919 (exe+0x91919) read addr 0x7FA41020 | eax FFFFEC03 ebx 7F454D9C ecx 7FA50000 edx 0002967C esi 7FA41018 edi 7F454E2C ebp 7F454DB4 esp 0012DBC4 | frame 790 state 5 cam cb 0x004071A0 mode 2
CRASH: stack 7F454D9C 7F454DB4 7F454E2C 7F454D60 00000000 00000000 004916E7 7F454E2C 7F454CC4 7F454D90 7F454D18 7F454D00 C5B30000 4AA85066 4504CB89 7FAAFFB8

run 6  (pristine_fix, 3700, B):  at 0x00491919 read addr 0x7FA41014 | eax FFFFEC02 ecx 7FA50000 esi 7FA4100C | frame 798 cam cb 0x004071A0 mode 2
run 7  (pristine_fix, 3700, B):  at 0x00491919 read addr 0x7FA41014 | eax FFFFEC02 ecx 7FA50000 esi 7FA4100C | frame 804 cam cb 0x004071A0 mode 2
run 10 (pristine_fix, 3000, B):  at 0x00491919 read addr 0x7FA41008 | eax FFFFEC01 ecx 7FA50000 esi 7FA41000 | frame 814 cam cb 0x004071A0 mode 2
run 11 (pristine_fix, 2750, B):  at 0x00491919 read addr 0x7FA41020 | eax FFFFEC03 ecx 7FA50000 esi 7FA41018 | frame 825 cam cb 0x004071A0 mode 2
```

Seven crashes, one instruction pair, one register pattern: `ecx` = the vertex pool base `[0x5dd320]` (page aligned),
`eax` = -5117..-5120 (0xFFFFEC00..03), `esi` = ecx + eax*12 = 0xF000 below the pool, the return address on the stack is
0x4916e7 (`renderer_SubdivideTerrainQuad` 0x4911e0). The stack dword at +0x30 is a float -3072 .. -5728 (the current
quad's z term, incidental).

## The faulting function and instruction

`renderer_SplitTerrainEdge` 0x4918f0 (`python tools/disasm.py 0x4918f0`, `ghidra\export\functions\004918f0.c`):

```
0x491903  movsx eax, word ptr [edi]          ; edge record: vertex index A, int16
0x491906  mov   ecx, [0x5dd320]              ; transformed-vertex pool (12-byte entries, x/h/z)
0x49190d  lea   eax, [eax + eax*2]
0x491912  lea   esi, [ecx + eax*4]           ; &pool[A]
0x491915  movsx eax, word ptr [edi + 2]      ; vertex index B, int16
0x491919  fld   dword ptr [esi + 8]          ; <- fault: pool[A].z with A negative
0x49191f  fadd  dword ptr [ecx + edx*4 + 8]  ; <- fault in run 5 (A happened to be in a mapped page, B was not)
...
0x491948  mov   ecx, [0x6442ec]              ; vertex count = index of the new midpoint vertex
0x49195b  inc   ecx ; mov [0x6442ec], ecx
0x491973  fstp  [ecx + esi]                  ; writes pool[count] (no bound either; the x16/x128 pools cover it)
...
0x4919c8  mov   eax, [0x654380]              ; draw-record arena cursor (12-byte records, DRAW-DISTANCE.md)
0x4919db  mov   word ptr [eax], cx           ; new edge record: index A ...
0x4919de  mov   word ptr [eax+2], bx         ; ... and the midpoint's index, TRUNCATED TO 16 BITS
0x491a0a  mov   word ptr [eax], bx           ; second half-edge, same truncation
```

The decompile says it plainly: the vertex count read from 0x6442ec is cast to a 16-bit short and stored at offset +2 of
the edge record. Once a frame
has queued more than 32,767 vertices the next midpoint index is stored as a negative short; the next split of that edge
(the recursion in `renderer_SubdivideTerrainQuad` splits each quad's four edges, then the children's) reads it back
through `movsx` and addresses `pool + (count - 65536) * 12`. The faulting eax is always about -5118 because indices
32,768..60,417 land in mapped memory below the pool (another heap block; silently wrong vertices) and 0x7FA41000 is the
first unmapped page: eax * 12 = -0xF000 exactly. So the first *visible* failure is at index ~60,418, but the data is
corrupt from 32,768 on (the 65k-level frames would draw garbage even if they did not fault).

Why the pools do not matter: 32,767 vertices x 12 B = 393 KB; the stock pool is 0x1a5e0 = 108,000 B (9,000 vertices,
which is why the stock exe died earlier and elsewhere, at 0x491a11 / 5000 m in DRAW-DISTANCE.md), the x16 pool is
1.73 MB (144,000 vertices) and the x128 pool 13.8 MB. Beyond x4 the extra pool is unusable: the int16 index is the real
ceiling.

## Why the hood view and the binoculars, and why those far values

`renderer_QueueTerrain` 0x490a00 resets `[0x6442ec]` to 0 each frame, derives the split threshold `_DAT_006442c8 =
|cam+8| * k / (half display width)` from the camera (cam+8 is the focal term that `0x472400` scales by the zoom factor,
clamped 0.5..8.0: constants 0x4be5b8 / 0x4be5d0), computes the terrain footprint from the frustum corners
(`renderer_ComputeTerrainFootprint` 0x4929b0, clamped to the terrain grid -0xc00..0x3400) and recurses
`renderer_SubdivideTerrainQuad` over it. The subdivision stops per quad when `size^2 * _DAT_006442c8 < dist^2`
(0x4911e0 .c line 71) or the height error is small, so the vertex count depends on (far clip, fov, zoom).

Measured on t01 (the sampler rows above), the count is quantised in levels and each camera sits a fixed number of
levels above the cockpit:

| view | camera | far 1800 | far 2500 | far 3000 | far 3700 | far 5000 | far 8000 |
|---|---|---|---|---|---|---|---|
| cockpit F1 (0x406ab0) | fov pi/2, zoom 1 | 1,480 | 1,427 | 4,577 | 4,595 | (ok) | (ok, 3 s in run 4) |
| hood F6 (0x407680) | `camera_Init(..., fov 2.0943952, ...)` = 120 deg, zoom reset to 1.0 (`_DAT_005367a4 = 0x10000`) | 4,499 | 4,499 | 16,919 | 16,920 | ok (run 3) | **crash** (runs 4, 5) |
| binoculars B (0x4071a0) | cockpit camera, `0x472400(cam, _DAT_005367a4 / 65536)` = zoom **8.0** | 17,068 | 17,595 | **65,198 crash** | **65,196 crash** | crash | - |

Levels: ~1.4k, ~4.5k, ~16.9k, ~65.2k (x3.7-3.9 each; the ratio is the quadtree's 4x minus the frustum edge). Every view
steps up one level between far 2500 and 2750 (cockpit 1 -> 2, hood 2 -> 3, binoculars 3 -> **4 = crash**), and the hood
view steps again between 5000 and 8000 (3 -> 4 = crash). The int16 limit sits between levels 3 (16.9k) and 4 (65.2k),
so **any camera that reaches level 4 crashes**, and binoculars at zoom 8 are the first to get there. The cockpit zoom key
(`zoom_factor`, PgUp) drives the same `0x472400` clamp, so a fully zoomed cockpit is the same case as binoculars.

Hypotheses from the brief, checked: (a) depth buckets - `renderer_InsertDepthBucket` 0x48fe61 drops index > 0x1000
silently; no write; the crash is in the tessellator before any bucket insert, and 3000 m (< 3796) crashes while 5000 m
survives in the hood view, so the knee is not 3796; (b) `camera_Init` clamp 100..100000 vs a divide - the clamp is on
`far`, both cameras pass a valid far, no divide on the path; (c) the enlarged pools' sibling buffer - the vertex pool is
the sibling, and its *index width*, not its size, is the limit; the pools are not overflowed in any run (65k x 12 B =
782 KB < 1.73 MB).

## Safe range for I76_FAR_CLIP (and the file patch)

- **Verified safe on t01: 100 .. 2500 m** (runs 1, 2, 8, 9: cockpit, hood and binoculars all survive). **2750 and above
  crash in binoculars** (runs 11, 10, 7, 6, 3), **8000 crashes in the hood view too** (runs 4, 5).
- **The launcher's option 5 (1800 m) is safe**: binoculars peak at 17,068 vertices (52% of 32,767) and the same
  tessellation level as 2500, so a different mission's terrain would have to add a whole level to break it. 1800 is the
  recommended value; 2500 is the measured edge on the training desert and is not a margin.
- **The sandbox's file patch (8000 m, 128x) is unsafe and must come down**: `patch-farclip.ps1 -GameDir ... -FarMeters
  1800` (or `-Restore`). The 5000 m setting DRAW-DISTANCE.md describes crashes the binoculars as well (run 3); its soaks
  never pressed B or F6.
- The proxy's `I76_FAR_CLIP` cannot override a file-patched exe (run 5); on a stock-pool exe it works (6/6 sites), and the
  proxy should refuse or warn above 2500 m until the tessellator is fixed. A real fix is in the engine: widen the edge
  record's two indices (12-byte record: idx A u16, idx B u16, two dword child pointers - no spare room) or cap the
  subdivision level when `[0x6442ec]` approaches 32,767 (a check in `renderer_SplitTerrainEdge` returning without
  splitting would degrade the far terrain instead of crashing). Not attempted here.
- The depth-bucket ceiling (3796 m) is moot for now: nothing above 2500 m is safe to run until the index width is fixed.

## Files

- `i76-map\verify\scenarios\camera-farclip.json` (new), `i76-map\verify\run_scenario.py` (`--env KEY=VALUE`, repeatable,
  plus a scenario-level `"env"` dict; both applied after the profile's switches; recorded in the manifest's `env`).
- Runs: `i76-map\verify\runs\camera-farclip\20261002-14{2046,2230,2402,2516,2619,2740,3106,3324,3513,3659,4221}`.
- Sampler (scratch, not committed): `vertsample.py` - ReadProcessMemory of 0x6442ec / 0x59c568 / 0x4c2720 / 0x5a7e1c /
  cam+0x10 / cam+0x34 at ~1 kHz; outputs `verts-{1800,2500,3000,3700}.txt`.
