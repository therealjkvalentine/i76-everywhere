# OpenGLide-HD on the MacBook (Wine 10 under Rosetta, `-glide`)

Recipe for putting a current OpenGLide (voyageur master + this folder's patches) behind I'76's Glide path on
the Mac: Sikarugir Wine 10 (wow64, x86_64 under Rosetta), 32-bit `i76.exe`. Written 2026-10-03 from a build and
live runs on Windows (results at the end); **nothing below has run on the Mac yet**.

Why bother: the GOG/Mac OpenGLide is 0.09rc9/rc5 and has no `Resolution=` key, and the Glide DLL tried on the
Mac on 2026-10-03 was in fact dgVoodoo 1.50 Beta2 (frames waited ~37 ms in Wine's ddraw/d3d9). OpenGLide goes
Glide -> OpenGL straight onto winemac.drv, with no D3D layer in between
(lab `docs\SOFTWARE-RENDERER-HIRES.md` section 8).

## 1. Get the DLL

The DLL is a Win32 PE that Wine loads like any other game DLL, so **the Windows build runs as-is**. Pick one route.

**A. Reuse the Windows build (simplest).** On the Windows box:

```powershell
git clone https://github.com/voyageur/openglide.git C:\Users\james\i76-uncap-lab\refs\openglide
cd C:\Users\james\i76-uncap-lab\refs\openglide
git am C:\Users\james\i76-everywhere\tools\openglide-hd\*.patch
powershell -ExecutionPolicy Bypass -File build-msvc.ps1   # VS 2019 x86 tools, /MT; needs khr-include\ (below)
```

`build-msvc.ps1` (added by `0003`) wants the Khronos `GL/glext.h` and `KHR/khrplatform.h` in `khr-include\`
(`curl -L -o khr-include/GL/glext.h https://registry.khronos.org/OpenGL/api/GL/glext.h`, and
`.../EGL/api/KHR/khrplatform.h` into `khr-include/KHR/`). Output: `glide2x.dll`, ~400 KB, imports only
OPENGL32, GLU32, GDI32, USER32, KERNEL32 (static CRT), 127 exports, every one of the 39 that `ZGLIDE.DLL`
imports present. Copy it to the Mac (AirDrop / USB). The DLL is LGPL-2.1 (OpenGLide); this repo does not
commit it (THIRD-PARTY.md: no third-party binaries).

**B. Build it on the Mac** (mingw-w64 from Homebrew, i686 target):

```sh
brew install mingw-w64
git clone https://github.com/voyageur/openglide.git ~/src/openglide && cd ~/src/openglide
git am ~/i76-everywhere/tools/openglide-hd/*.patch
CXX=i686-w64-mingw32-g++ sh build-mingw.sh            # added by 0003
file glide2x.dll                                         # PE32 executable (DLL) ... Intel 80386
```

mingw-w64 ships `GL/glext.h`, so no extra headers. `build-mingw.sh` links libgcc/libstdc++ statically; the
result imports msvcrt plus the same system DLLs. The same script built cleanly on Windows with w64devkit x86
(GCC 16.2, 591 KB, 127 exports, ZGLIDE's imports all present); not yet run through Homebrew's toolchain.

## 2. Install into the Mac game folder

In the bottle's game folder (`drive_c/GOG Games/Interstate 76/` in the Glide wrapper):

1. Keep the old DLL: `mv Glide2x.dll Glide2x.dll.pre-openglide-hd` (the current one is dgVoodoo 1.50 Beta2,
   whatever its `.openglide-backup` name says). Copy the new `glide2x.dll` in as `Glide2x.dll`.
2. No dgVoodoo `DDraw.dll` / `D3DImm.dll` next to it (dgVoodoo's DirectDraw collides with OpenGLide's GL window
   at boot). Wine's own ddraw serves the 8-bit menus; no 256COLOR layer is needed under Wine.
3. `OpenGLid.ini` (CWD-discovered; the Mach-O stub sets CWD to the game folder). It is **ignored unless
   `Version=` matches the DLL** (`0.09rc9`), so keep that line:

```ini
Configuration File for OpenGLide

Version=0.09rc9

[Options]
WrapperPriority=2
CreateWindow=1
InitFullScreen=0
EnableMipMaps=0
IgnorePaletteChange=0
Wrap565to5551=1
EnablePrecisionFix=1
EnableMultiTextureEXT=1
EnablePaletteEXT=1
EnableVertexArrayEXT=0
TextureMemorySize=2
FrameBufferMemorySize=2
NoSplash=1
WinOpenDelayMS=0
Resolution=0
```

   - `TextureMemorySize=2` / `FrameBufferMemorySize=2` are load-bearing (I'76 crashes on a >2 MB TMU report).
   - `Resolution=`: `0` = 640x480; `1.0`-`16.0` = scale factor (`2` = 1280x960); `>16` = output width, height
     from 4:3 (`2979` = 4:3 at the 2234-row panel). Start at `0`, then `2`, then the panel size.
   - Probe that it loads: after the first run `OpenGLid.log` in the game folder must show the INI path and the
     GL renderer string; with `Resolution=2` the window must open at 1280x960.
4. Launch through the existing Mach-O stub (it removes Sikarugir's `CX_FWD_COMPAT_GL_CTX=1`; a forward-compatible
   context has no fixed-function GL and crashes `-glide` at `i76+0x4507C`). Args `-glide`.

## 3. GL requirements under Wine on macOS

OpenGLide is fixed-function OpenGL 1.x (`glBegin`/`glEnd`, `glPushAttrib`, alpha test, `glTexEnv`). On macOS that
means the **legacy 2.1 context** (Apple's 4.1 core profile has none of it), which is what winemac.drv creates when
nothing asks for forward-compatibility. Extensions it checks: "required" `GL_EXT_packed_pixels`, `GL_EXT_abgr`,
`GL_EXT_bgra`; desired `ARB_multitexture`, `EXT_fog_coord`, `EXT_secondary_color`, `EXT_paletted_texture`
(absent on Apple: it falls back to RGBA textures), `EXT_texture_env_combine`, `SGIS_generate_mipmap`.
Apple's legacy context lists `GL_APPLE_packed_pixels`, not `GL_EXT_packed_pixels`, and stock OpenGLide answers a
missing "required" extension with a **modal MessageBox at boot**. Patch `0003` accepts `EXT_packed_pixels` and
`EXT_bgra` on any GL >= 1.2 context (both are core there), so that box should not appear. If a "Severe Problem:
OpenGL ... extension is required" box still appears, click OK and note which extension (`EXT_abgr` is the one not
covered; Apple's list has it).

## 4. Measure

Two independent clocks, so one cross-checks the other:

- **OpenGLide's own LFB profiler** (patch `0003`): `OGL_LFB_PROF=1` (or a path) writes `OpenGLid-lfb.log` in the
  game folder, one line per `OGL_LFB_PROF_N` swaps (default 100), per-frame averages in ms:
  `frames frame_ms frame_max_ms locksWO locksRO lock_flush_ms lockWO_ms lockRO_ms unlock_scan_ms unlock_draw_ms
  lfb_total_ms swap_ms written_px upload_rows`. `frame_ms` is swap-to-swap (fps = 1000 / frame_ms);
  `lfb_total_ms` is the LFB emulation cost; `lock_flush_ms` is queued 3D triangles drawn at lock time (3D work,
  not LFB); `swap_ms` is flush + SwapBuffers (where a GPU / Wine wait shows up).
  Set it in the stub's environment or for a CLI launch:
  `OGL_LFB_PROF=1 OGL_LFB_PROF_N=50 WINEESYNC=1 WINEMSYNC=1 wine i76.exe -glide`.
- **The proxy's frame log**: `I76_FPS_LOG` / `I76_FPS_PROF` (Strlkup proxy, Mac session build) for the exe-side
  ms per frame, as in the dgVoodoo 1.50 run (exe ~6 ms, wait ~37 ms).

A/B of the LFB fix in the same DLL: `OGL_LFB_FAST=0` restores stock OpenGLide's unlock loop. Run each
condition twice (same mission, same spot) before believing a difference.

Order of runs on the Mac: `Resolution=0` (does it boot, HUD text, Esc menu, binoculars), then `2`, then the
panel size; at each, 30 s in t01 with `OGL_LFB_PROF=1`, then once with `OGL_LFB_FAST=0`.

What to look for: if `frame_ms` is far above `lfb_total_ms + exe ms` and `swap_ms` carries the gap, the wait is
in Wine's GL present, not the LFB; if `unlock_draw_ms` dominates, the per-frame texture upload is the cost on
Apple's GL (next step would be a persistent LFB texture with `GL_APPLE_client_storage`).

## 5. What the patches change (all opt-in or behaviour-preserving)

- `0001` HD texture dump/replace (`hdtex\` directory presence is the only switch).
- `0002` passthrough output window, `WinOpenDelayMS` race guard.
- `0003` LFB profiler (`OGL_LFB_PROF`), faster write-only unlock (`OGL_LFB_FAST=0` disables), the GL 1.2
  extension check, `build-msvc.ps1` and `build-mingw.sh`.

## 6. Windows results (2026-10-03, lab `game-oglide`)

MSVC build, GTX 1080 Ti, t01 through `autotest\proxy-run.ps1`, 7 runs, no crash. Details: lab
`docs\OPENGLIDE-HD-WINDOWS-2026-10-03.md`.

- `Resolution=0` (640x480), `2` (1280x960), `1920` (1920x1440): correct 3D, cockpit, mirror; the Esc menu and
  the binocular mask (both LFB) composite correctly, at 640x480 detail scaled up. 178-180 fps everywhere
  (pinned at the 180 Hz swap pacing, so the GPU cost of resolution is not visible on this PC).
- The game takes exactly one write-only LFB lock per frame. **OpenGLide's write-only lock does no read-back**
  (colour-keyed staging buffer, composited on unlock), so the lock costs ~0 ms; the cost is the unlock's
  full-buffer scan. Stock unlock 0.31-0.38 ms per frame while driving (nothing written), 0.53-0.58 ms with
  binoculars (79k pixels written); with `0003` 0.06-0.07 ms and 0.36-0.53 ms.
- So on the Mac the LFB should cost low single-digit ms even translated by Rosetta; if frames are slow, the
  time will be in `swap_ms` (Wine's GL present), not the LFB.

## 7. Patch 0004 on the Mac (2026-10-04): gamma, MSAA, stretched output

Run on the MacBook (M5 Pro, Wine 10, built as route B). All off unless set; the Mac launcher
([`i76-hires120-stub.swift`](../../i76-hires120-stub.swift)) passes them from `hires120.env`:

| setting | what | Mac result |
|---|---|---|
| `OGL_GAMMA=1.3` | gamma on the finished frame at swap (GLSL `pow`). The owner reported OpenGLide "too dark, and not a monitor-brightness thing": ZGLIDE never calls `grGammaCorrectionValue`, the brightness came from the Voodoo's own output ramp (dgVoodoo: `EnableGlideGammaRamp`), and the prefix's `AllowSetGamma=0` would block `SetDeviceGammaRamp` anyway. Same diagnosis as on VOGONS for XQuartz/XWayland | Owner: "perfect" without MSAA. **With `OGL_MSAA` the first version changed nothing on screen**: it read the frame with `glCopyTexSubImage2D`, which does not work from Apple GL's multisampled window under Wine. Fixed by resolving the frame with `glBlitFramebufferEXT` into a single-sampled FBO first; the pass logs one sample at frame 600: `before 77 35 16 -> after 102 55 30 (expected 102 55 30)` with 4x MSAA on |
| `OGL_MSAA=4` | multisampled window via `wglChoosePixelFormatARB` | `OGL_MSAA: 4x multisample pixel format 85` (winemac grants it) |
| `OGL_OUTPUT=WxH` | output of any aspect, the 4:3 Glide frame stretched to it | launcher `HIRES_OGL_FIT=stretch` sets it to the desktop |

Launcher keys: `HIRES_DESKTOP=auto` (desktop = main display; a screen-sized Wine desktop is borderless fullscreen),
`HIRES_RETINA=1` (sets the prefix's `RetinaMode` and sizes "auto" in pixels: 3456x2234 on the 14" panel),
`HIRES_OGL_FIT=1` (4:3 pillarbox via `Resolution=`) or `stretch`.

Frame rate, t01 direct boot, Terrain Resolution Medium, 5 s windows: every configuration (1728x1117 or 3456x2234,
with or without 4x MSAA and gamma) ran **104-118 fps** in its first 25 s; three of four runs then sat near 57-60 for
the rest, one recovered to 120. The plateau did not follow the settings, so it is suspected to be macOS scheduling an
unfocused, unattended game onto the efficiency cores, not GPU cost; the owner's own (focused) session held 120. One
Retina run without MSAA logged no mission frames; not reproduced. Played look and fps: pending the owner.

## 8. The Mac play setup (2026-10-04): DxWnd for the menus, OpenGLide for the 3D

Running `-glide` in a bare Wine desktop left the 640x480 DirectDraw menus unscaled with the cursor off. DxWnd
already scales those menus and maps the cursor on the software path, so the Glide path now runs under DxWnd too
(`Interstate 76 - GL DxWnd TEST.app`: the daily DxWnd launcher, profile `cmdline0=i76.exe -glide` - DxWnd passes
`cmdline0` as the WHOLE command line, so the program name must come first or `-glide` is dropped as argv[0]).

- **Window size under DxWnd.** DxWnd reports a virtual 800x600 client area and stretches child windows to the real
  window. Patch 0005: `OGL_OUTPUT=parent` sizes the output child to that virtual area (so DxWnd maps it over the whole
  window) and `OGL_VIEWPORT=WxH` renders at the real size (here 1728x1117). Either alone is wrong: `parent` alone drew
  the 3D into an 800x600 corner, an explicit `OGL_OUTPUT=1728x1117` came out zoomed and cropped.
- **Intermittent crash at launch** (call to address 0, ~1 in 6 launches, args `GL_FRAGMENT_PROGRAM_ARB` /
  `GL_MAX_PROGRAM_ENV_PARAMETERS_ARB`): Wine's wined3d, initialising GL caps for the menus' DirectDraw, through an
  empty function pointer while OpenGLide also owns a GL context. Fix: `HKCU\Software\Wine\AppDefaults\i76.exe\Direct3D`
  `"renderer"="gdi"` (DirectDraw without 3D; the menus need none). 12/12 clean launches after, vs 2 crashes in 7 before.
- **Black screen on a replayed mission** (owner): the game closes and reopens its Glide window between missions;
  patch 0005 shows each new output child (0002 did it once per process) and rebuilds the gamma pass's GL objects per
  context. Not yet re-tested by the owner.
- Settings live in the prefix's `HKCU\Environment` (the DxWnd launcher has no env file): `OGL_OUTPUT=parent`,
  `OGL_VIEWPORT=1728x1117`, `OGL_MSAA=4`, `OGL_GAMMA=1.3`, the lean 120 `I76_*` set. DxWnd profile `sizx0/sizy0` =
  1728x1117 (the laptop's shape: a gentle stretch, no extra field of view), `maxfps0=0`.
- Verified by a scripted run (AutoHotkey inside the session, real clicks): the fullscreen Driver Entry Form, into an
  Instant Melee, 97-118 fps, full HUD, gamma sample `94 53 14 -> 118 76 27` (expected), no crash. Screenshots of this
  setup work (unlike the bare-desktop fullscreen GL window).
- Open: `OGL_VIEWPORT` is fixed at the laptop's size; on the 3440x1440 display DxWnd's window differs and it would need
  that display's value.
