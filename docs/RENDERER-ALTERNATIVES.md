# Renderer alternatives: other Glide wrappers, the other back ends, and frame generation

*Survey and preparation, 2026-10-02. **Nothing here was run in the game** (the console was busy: an `i76.exe` from
the lab sandbox was running the whole time). No file in `i76-uncap-lab\game` or in the playable install was changed,
and nothing was downloaded. Every statement is tagged by where it comes from: **[measured]** on this machine (with
the doc that holds it), **[disk]** read from a file today, **[web]** fetched today (source in section 8),
**[recalled]** from general knowledge and not re-verified today, **[untested]** a prediction.*

The owner's request: "try different glide wrappers or other rendering solutions".

## 1. What is being fixed

Stack today: `i76.exe -glide` -> `ZGLIDE.DLL` -> `Glide2x.dll` (dgVoodoo 2.87.3) -> D3D11 -> GTX 1080 Ti, borderless
window on a 3440x1440 179 Hz panel. The limits of that path, all measured:

| # | limit | evidence |
|---|---|---|
| L1 | **Refresh ceiling 120.** dgVoodoo paces presents by the Glide refresh code the app passes to `grSstWinOpen` (60 by default; 90, 100, 120 work; "none" gives 60; codes above 8 are rejected). The panel is 179 Hz | `docs\FPS-120.md` "Measured" and "Above 120" [measured] |
| L2 | **Pointer box.** In the in-mission Esc menu dgVoodoo pins the pointer to a 1920x1440 box at the client origin and ignores the 760 px pillarbox, so items right of the box cannot be reached | lab `docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md` [measured] |
| L3 | **No anisotropic filter, no mip bias** for Glide in dgVoodoo | `docs\GRAPHICS-ENHANCEMENT.md` rank 6 |
| L4 | **No texture replacement** in dgVoodoo | `docs\FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md`, `docs\HD-TEXTURES-RESEARCH.md` |
| L5 | Window / focus behaviour is owned by dgVoodoo's fake-fullscreen logic (the conf carries several load-bearing keys for it) | lab `docs\CONFIG-OPTIONS.md` |

What a replacement must not break (the project's hooks):

- **Strlkup proxy** (`music-fix\Strlkup.dll`, installed as `STRLKUP.DLL`): patches `i76.exe` in memory and, through a
  `LoadLibraryA` hook, repoints **ZGLIDE's `glide2x.dll!_grSstWinOpen@28` import slot** at a wrapper that substitutes
  the refresh code (`I76_GLIDE_REFRESH`). The hook is by import name, so it attaches to *any* `glide2x.dll`; what the
  substituted refresh code *does* is up to the wrapper. Everything else in the proxy (fixed step, render
  interpolation, 20 Hz grid, far clip, telemetry, `I76_FPS_CAP`) is exe-side and independent of the wrapper.
- **u32x** (`u32x.dll`, a USER32 wrapper the exe imports): maps the pointer. Its log on this machine shows
  `scale=3.000 org=(760,0)`, the 4:3 pillarbox of the live client [disk]. It does not depend on dgVoodoo, but its
  special case for the dgVoodoo clip box (section 4 of the mouse doc) will see a different clip rectangle under any
  other wrapper: the pin test decides.
- **The 2D shell** (menus, briefings, garage) is DirectDraw, not Glide. Today dgVoodoo's `DDraw.dll` / `D3DImm.dll`
  serve it and provide the 8-bit palette the exe needs at sim entry (without one it faults at `i76.exe` 0x475a01,
  FINDINGS section 7.1 [measured, July, on the laptop]). **Changing the Glide wrapper therefore raises the question
  of who serves DirectDraw**; that is the main compatibility risk of every candidate below.
- `I76_FPS_CAP=<n>` (QPC wait in the frame hook) paces the game whenever the wrapper does not. So "a wrapper that
  simply does not pace" is enough for 179: the proxy holds the rate. That is the test for every candidate:
  `-Env @{ I76_FPS_CAP = "179" }`, then `frame_stats.py`.

One observation to keep in mind: `Win32_VideoController.CurrentRefreshRate` read **119** at about 23:00 while a
test run was in progress and **179** a few minutes later [measured, n = 1 each, cause not looked into]. Read it
(or the panel's OSD) at the start of any run that claims more than 120.

## 2. Survey table

| candidate | version / licence | could fix | compatibility with the hooks | risks | on disk? |
|---|---|---|---|---|---|
| **nGlide** (Zeus Software) | 2.10, freeware, closed source, 4.75 MB installer [web]. Back ends Direct3D 9 and Vulkan, chosen in `nglide_config.exe` [web]. Options: screen resolution ("By desktop" or a size), aspect ratio ("Fit to screen" / "Preserve original"), refresh rate ("By app" or the monitor's rate), vertical synchronization, gamma [web]. Frame rate "capped at 1000 FPS when V-sync is disabled" [web]. Alt+Enter toggles a window [web] | **L1 likely**: with vsync off it does not pace (1000 fps cap), so `I76_FPS_CAP=179` paces; with vsync on in exclusive fullscreen it should follow the real mode's refresh [untested]. **L2 likely**: no dgVoodoo pointer box; u32x's own map then applies [untested]. L3, L4: no (no anisotropy or replacement option known [recalled]; closed source) | Proxy: the import-slot hook attaches by name; `I76_GLIDE_REFRESH=120` would hand nGlide refresh code 8, which "By app" would honour as a 120 Hz request - leave it unset first. u32x: unknown clip box, pin test. DirectDraw: three options to try, in this order: keep dgVoodoo's `DDraw.dll` (may collide the way OpenGLide's GL window did; nGlide is D3D9/Vulkan, so it may not), DDrawCompat, or no wrapper + the 256COLOR compatibility layer | Exclusive fullscreen by default: a real mode switch, focus loss minimises, screenshots of an exclusive D3D9 surface can come back black. Settings live in **HKCU\Software\Zeus Software** [web], i.e. per user, not per folder (only an nGlide DLL reads them, and no install here has one). The installer writes into `SysWOW64` [web] - **do not run it**; open it with 7-Zip and take the DLLs. dgVoodoo's `D3D9.dll` in the game folder would be picked up by nGlide's D3D9 back end: `switch-renderer.ps1` removes it for this set | **no** - download D1 |
| **OpenGLide 0.09rc9** (GOG's bundled build) | `glide2x.dll` 177,664 B, 2011, md5 c319a4f3 [disk]; LGPL | L1 **maybe** (an OpenGL `SwapBuffers`; pacing is the driver's swap interval, not a Glide refresh code [untested]). L2: its window is the game's 640x480 client - no pillarbox, no scaling [measured in July: "native 640x480 window"]. L3, L4: no | Known from July (laptop, FINDINGS 7.1): crashes on a TMU report above 2 MB (`TextureMemorySize=2`), needs the 256COLOR layer, and **dgVoodoo's DDraw collides with its GL window at boot**. u32x did not exist then: untested together | A 640x480 window on a 3440x1440 panel: a pacing probe, not a daily driver. The two logs in `game\` (`OpenGLid.log`, `DDrawCompat-i76.log`) are from **another machine** (GTX 1650 Ti, `C:\Games\Interstate 76`, Windows build 26200) [disk]: nothing about this PC was learned from them | **yes** - `i76-map\sandbox-gog\main\app` |
| **OpenGLide-HD** (this repo's fork of voyageur/openglide) | patch in `tools\openglide-hd\` (381 KB); LGPL. Status 2026-07-10: builds, boots, stays alive; dump/replace loop not verified in game | **L4: the only route** (hash-based dump and replace at any resolution). L1 as OpenGLide. L2 as OpenGLide (patch 0002 adds a passthrough output window) | as OpenGLide | Needs a build (w64devkit x86, download D6). The built DLL is **not on this machine**: `%USERPROFILE%\openglide-hd` does not exist [disk] | patch only |
| **OpenGLide, crazii fork** | github.com/crazii/openglide, LGPL-2.1, 155 commits, **no releases** [web]. Adds windowed / desktop (borderless) / app modes, desktop scaling (stretch / integer / fitted), VSync option, MSAA or FXAA, shader-based combine emulation [web] | L1 maybe (VSync option; pacing by the GL swap), L2 maybe ("fitted" scaling: who maps the pointer is unknown), L3 no, L4 no (would need the HD patch ported) | as OpenGLide; untested with I'76 by anyone we found | Build needed (mingw-w64 32-bit or MSVC6; wxWidgets 2.8.10 for the config tool) [web]; "limited game testing" | no - D7 (source) |
| **dgVoodoo 2.87.5** (newer than installed) | 2.87.4 (Sep 2), 2.87.5 (Sep 15) [web]; freeware | Nothing: the release notes fetched list a driver-string rename and a D3D9 viewport fix, no Glide, pacing or pointer change [web] | drop-in | low value; only worth it if another reason appears | no - D5. Installed: **2.87.3** in `game\` (`Glide2x.dll` md5 8af442bc = `C:\Games\_tools\dgVoodoo2_87_3\3Dfx\x86\Glide2x.dll`) [disk] |
| **DXVK under dgVoodoo** (`d3d11.dll` + `dxgi.dll`, 32-bit, in the game folder) | 2.7.x: Vulkan 1.3, NVIDIA driver >= 550.54.14 [web]. 3.x (3.1.1, Sep 15): **Vulkan 1.4, NVIDIA >= 575.51.02** [web]. zlib licence. This PC's driver is 32.0.15.6094 = **560.94** [disk]: **2.7.x only** | L1 **unlikely but cheap to rule out**: the sampler put the 60 fps wait inside the NVIDIA D3D11 driver's present; DXVK replaces that driver path, so *if* dgVoodoo's pacing rides on a DXGI call, `dxgi.syncInterval = 0` / `dxgi.maxFrameRate` in `dxvk.conf` could change it. If dgVoodoo sleeps on its own timer, nothing changes [untested]. Latency: DXVK's present path and `dxvk.latencySleep` [recalled]. L2-L4: no | none of the hooks touch D3D11. ReShade would then have to load as a Vulkan layer or chain, not as `dxgi.dll` | shader compile stutter on first sight of each pipeline (the Mac build's problem, far smaller on native Vulkan); 32-bit builds are sometimes flagged by antivirus [web]. The repo's `dxvk.conf` is the Mac one (`enableAsync`, MSAA off): do not copy it | no - D2 |
| **The exe's own Direct3D back end** (`i76.exe -d3d`) through dgVoodoo's `DDraw.dll` / `D3DImm.dll` | already installed (dgVoodoo 2.87.3) | **L3 yes**: `[DirectX] Filtering` offers anisotropic up to 16x, plus `[DirectX] Resolution` and MSAA. **L2 maybe**: the Esc menu would go through the same DirectX wrapper path as the shell, where the pointer works today. L1 unknown: dgVoodoo's readme lists refresh overrides as not working for DirectX emulation; whether DX presents are paced at 60 is untested | Proxy: `I76_GLIDE_REFRESH` is a no-op (no ZGLIDE). **Other hook sites assume the Glide path?** The frame hook, far clip and interpolation are in exe code shared by both hardware paths (renderer.md: display driver kind 1 = hardware, D3D layer at 0x42d0c0) [static], but none of it was ever run with `-d3d` | `docs\MODERN-PORTS-AND-VR.md`: "D3D is the worst-looking" - 640x480, textures reduced on purpose in 1997 (web consensus, not measured here). `maplib.ps1` / `capture-frame.ps1` take the frame geometry from `[Glide] Resolution`; under `-d3d` the `[DirectX]` line applies | **yes** - no file change, only the switch |
| **`-d3d` or the software renderer through DDrawCompat** | v0.7.1 (2025-01-25), `DDrawCompat-v0.7.1.zip`, 0BSD-style free licence [web / recalled]. Settings: `VSync`, `FpsLimiter`, `DisplayRefreshRate`, `ResolutionScale`, `DisplayResolution`, `DisplayAspectRatio`, `Antialiasing`, `TextureFilter` (anisotropic), `DisplayFilter`, `FullscreenMode` (exclusive / borderless / windowed), cursor options [web] | L1 maybe (`DisplayRefreshRate`, `VSync`, its own limiter), L3 yes for `-d3d` (`TextureFilter`), L2 unknown. Also the candidate DirectDraw provider beside nGlide / OpenGLide | It is a `ddraw.dll`: replaces dgVoodoo's, `D3DImm.dll` must go. The exe's 8-bit palette need: DDrawCompat is built for exactly that class of game [recalled], untested here | per-game ini in the folder (`DDrawCompat-i76.ini`), so confined. Sets CPU affinity to one core by default (`CpuAffinity = 1` in the July log [disk]) - that changes timing; note it in any measurement | no - D4 |
| **Software renderer** (`i76.exe` with no switch, or `-gdi` window) through dgVoodoo DDraw or DxWnd | engine limit 1024x768, unfiltered, 8-bit (`docs\VERIFIED-FIXES.md`); DxWnd is the Mac build's path (GPL, v2.06.x betas [web]) | none of L1-L4 in a useful way: more pixels than Glide's 640x480 logical frame, but point-sampled, and the wrapper only upscales the result. CPU-bound | proxy untested on the software path at high rates; the Mac notes say synthetic clicks are ignored through DxWnd scaling (`VERIFIED-FIXES.md`) | a quality step down from the current picture | dgVoodoo route **yes**; DxWnd no (D8) |
| **psVoodoo** | Glide -> D3D9 pixel shaders, LGPL 2.0, SourceForge; latest builds ship inside Glidos [web]; aimed at DOS Glide through Glidos | nothing known for a Win32 Glide 2.x game | untested | dead project | no - not proposed |
| **Zeckensack's Glide wrapper** | Glide 2/3 -> OpenGL, free, proprietary, last release 2005 (0.84c) [web / recalled] | nothing: no modern features | untested | dead since 2005, tuned for DX7-9 era drivers | no - not proposed |
| **ReShade** | 6.8.0 (2026-08-02), BSD 3-clause, D3D9/10/11/12, OpenGL, Vulkan [web] | sharpening / deband on the presented frame (see `docs\GRAPHICS-ENHANCEMENT.md` section 4). None of L1-L4 | loads as `dxgi.dll` under dgVoodoo, as `d3d9.dll` under nGlide's D3D9 back end (that pairing was fixed in ReShade 1.0 [web]), as `opengl32.dll` under OpenGLide | a crash at start with it present is ReShade's until shown otherwise | no - D3 |
| **Lossless Scaling frame generation on top of 120** | 3.2.2.0 on disk [disk]. LSFG 3: fixed multiplier or **adaptive** (a target frame rate, fractional factor) [web]. Queue target 0 / 1 / 2 trades latency for stability [web]. Windowed and borderless only [web] - the sandbox is borderless | **L1 for the eye only**: 120 real -> 179 displayed (adaptive, factor 1.49) or x2 -> 240 (more than the panel shows). Nothing else | none: a separate process that captures the window (WGC in the profile). No game file changes. `ForceVerticalSync = false` is already set for it | see section 5: adds about one real frame of delay plus capture/processing, HUD and text are interpolated too, and it stacks on the game's own render interpolation | **yes** |
| AMD AFMF / NVIDIA Smooth Motion | driver frame generation | - | - | AFMF is AMD-only; Smooth Motion needs RTX 40 or newer. Neither applies to a GTX 1080 Ti | n/a |
| DSR / DLDSR, NVIDIA profile overrides | - | - | - | ruled out in `docs\GRAPHICS-ENHANCEMENT.md` (profile is keyed on `i76.exe` and would hit the playable install) | n/a |

## 3. Ranked candidates

Order = expected gain against L1-L5, divided by cost and risk. "Tonight" = no download.

1. **nGlide 2.10** (download D1, 4.75 MB). The only candidate with a plausible answer to both L1 and L2 while
   keeping the Glide picture (full-resolution textures, bilinear, the 3dfx gamma). It is also the community's
   plan B for this game (`docs\WINDOWS-PLAYBOOK.md`). Unknowns to settle in one session: who serves DirectDraw,
   exclusive fullscreen vs the Alt+Enter window, and what u32x's map sees.
2. **Lossless Scaling adaptive 179 on the current 120** (tonight). Zero risk to the game folder, reversible by
   closing a program. It does not raise the real rate; it is the fallback if nothing lifts L1.
3. **`-d3d` through the installed dgVoodoo** (tonight). One command-line switch. The only tonight-route to
   anisotropic filtering (L3) and a different pointer path (L2). The texture-quality claim against it is from the
   web, not measured: one capture beside the Glide frame settles it.
4. **GOG OpenGLide as a pacing probe** (tonight). Answers "does the engine run at the desktop rate when the
   wrapper is not dgVoodoo?" before anything is downloaded, and re-checks the July bring-up findings on this
   machine. Not a daily driver (640x480 window).
5. **DXVK 2.7.x under dgVoodoo** (download D2). A ten-minute test of whether dgVoodoo's pacing survives a
   different D3D11 implementation. Low odds, low cost.
6. **DDrawCompat** (download D4): first as the DirectDraw provider nGlide may need, then `-d3d` through it
   (`TextureFilter`, `DisplayRefreshRate`).
7. **OpenGLide-HD / crazii fork** (build needed, D6/D7): only when texture replacement (L4) is the goal; the
   crazii fork's borderless scaling and VSync make it the better base to port the HD patch to.
8. **ReShade** (D3): after a renderer is chosen; see GRAPHICS-ENHANCEMENT.
9. **dgVoodoo 2.87.5** (D5): no relevant change found. Skip unless a reason appears.
10. Software renderer, DxWnd, psVoodoo, Zeckensack: not proposed.

## 4. Inventory: what is on this machine (2026-10-02)

Searched: `C:\Games`, `C:\Users\james\Downloads`, the three repos, `C:\Program Files`, `C:\Program Files (x86)`
(Steam library to depth 3), `%LOCALAPPDATA%\Programs`, Desktop, Documents; names matching nglide, glide*.dll,
openglid*, dxvk, dxgi/d3d11.dll, reshade, losslessscaling, dxwnd, ddrawcompat, ddraw.dll, dgvoodoo, psvoodoo,
zeckensack, cnc-ddraw.

| item | path | version | size |
|---|---|---|---|
| dgVoodoo 2 full package (x86, x64, arm64; Glide, Glide2x, Glide3x, DDraw, D3DImm, D3D8, D3D9, CPL, default conf) | `C:\Games\_tools\dgVoodoo2_87_3\` | 2.87.3 | x86 `Glide2x.dll` 212,992 B (md5 8af442bc...) |
| dgVoodoo set installed in the sandbox | `C:\Users\james\i76-uncap-lab\game\` (`Glide.dll`, `Glide2x.dll`, `Glide3x.dll`, `DDraw.dll`, `D3DImm.dll`, `D3D8.dll`, `D3D9.dll`, `dgVoodooCpl.exe`, `Glide2x.dll.dgvoodoo`) | 2.87.3, identical md5 to the package | 212,992 / 258,048 / 210,944 / 418,304 / 485,888 B |
| same set in the playable install (**not to be touched**) | `C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801\Interstate 76\` | 2.87.3 | - |
| GOG's bundled OpenGLide: `glide2x.dll`, `glide2x.ovl`, `OpenGLid.INI`; plus `glide.dll` (dgVoodoo 1.x Glide 2.11 wrapper, 2007) | `C:\Users\james\i76-map\sandbox-gog\main\app\` (also `...\nitro-pack\app\`) | OpenGLide 0.09rc9 era, file version 1.0.0.0, 2011 | 177,664 B (md5 c319a4f3...); ovl 29,412; glide.dll 229,376 |
| OpenGLide settings + log from July (from the laptop, see section 2) | `game\OpenGLid.ini` (520 B, `TextureMemorySize=2`), `game\OpenGLid.log` (12,760 B) | 0.09rc9 | - |
| DDrawCompat log from July (laptop; no DDrawCompat DLL anywhere on this PC) | `game\DDrawCompat-i76.log` | v0.7.1 | 12,286 B |
| OpenGLide-HD patch (source only; no built DLL: `C:\Users\james\openglide-hd` is absent) | `C:\Users\james\i76-everywhere\tools\openglide-hd\0001-...patch` | - | 381,192 B |
| DXVK pipeline-cache patch and Mac `dxvk.conf` (no DXVK DLLs for Windows anywhere) | `i76-everywhere\tools\dxvk-pipeline-cache-persist\`, `i76-everywhere\dxvk.conf` | - | 10,791 B / 357 B |
| Lossless Scaling | `C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801\Lossless Scaling\LosslessScaling.exe` (+ `Lossless.dll` 7.5 MB) | 3.2.2.0 | 157,696 B |
| Lossless Scaling profile | `%LOCALAPPDATA%\Lossless Scaling\Settings.xml`: profile "Interstate '76 Gold Edition", `LSFG3`, mode `FIXED`, multiplier 2, target 60, flow scale 100, capture `WGC`, queue target 1, max frame latency 3 | - | - |
| 7-Zip (to open installers without running them) | `C:\Program Files\7-Zip\7z.exe` | - | - |
| Real-ESRGAN (texture upscaling, for an HD pack) | `C:\Games\_tools\realesrgan\` | - | - |
| RTSS installer (frame limiter / overlay, not installed) | `C:\Users\james\Downloads\[Guru3D]-RTSSSetup737Build28314.zip` | 7.3.7 | 17,998,383 B |
| GOG installers (a clean reference can be re-extracted) | `C:\Users\james\Downloads\setup_interstate76_2.1.0.17.exe`, `setup_interstate76_nitro_pack_2.1.0.17.exe` | 2.1.0.17 | 395 MB / 239 MB |

**Not found anywhere:** nGlide (any file), DXVK DLLs, ReShade, DxWnd, a DDrawCompat DLL, psVoodoo, Zeckensack's
wrapper, cnc-ddraw, any dgVoodoo zip other than the unpacked 2.87.3.

Two stale pointers found on the way:

- `PLAY-i76.ps1 -LosslessScaling` defaults to `C:\Program Files (x86)\Steam\steamapps\common\Lossless Scaling\LosslessScaling.exe`,
  which **does not exist** on this PC; the copy that exists is the one inside the portable folder (table above).
  With the default the launcher silently skips frame generation.
- The sandbox folder is 494 MB in 1,162 files, of which 399 MB is `smk\`, `music\`, `I76.ZFS` and `DATABASE.MW2`.

## 5. Frame generation on top of 120 (Lossless Scaling), in more detail

- **Modes** [web]: fixed (x2, x3, ... of the base rate) and adaptive (a target rate; the factor floats). For this
  panel: adaptive target 179 from a 120 base is a factor of 1.49; fixed x2 gives 240, of which the panel shows 179.
  Adaptive is the right mode. The existing profile is fixed x2 with target 60, written for the old 20 fps base
  (`Setup-FrameGen.ps1`): it must be changed for a 120 base, in a copy of the profile, with Lossless Scaling closed
  (it rewrites `Settings.xml` on exit).
- **What 120 -> 179 looks like** [untested, from how interpolation works]: at a non-integer factor almost every
  displayed frame is a generated in-between; real frames are shown only where the two clocks line up. Motion
  smoothness is that of 179; fine detail that moves (HUD digits, radar, text, the road centre line, thin poles)
  is where artefacts appear, because the tool sees one flat image and cannot mask the HUD. At a 120 base the
  motion between source frames is small, so artefacts are far milder than the 20 -> 40 case the profile was built for.
- **Latency** [recalled + arithmetic]: interpolation must hold the newest real frame until the in-between frames
  are shown, so it adds roughly one base frame (8.3 ms at 120) plus capture and processing (a few ms; queue target
  1 adds up to one more captured frame, queue target 0 is the low-latency setting [web]). That sits on top of the
  game's own render interpolation, which already delays the picture by one physics step (41.7 ms, FPS-120 section
  4). Input is consumed at the 24 Hz step in any case, so the felt change is small; it is a picture-smoothness
  feature only.
- **GPU cost** [untested]: LSFG runs on the same 1080 Ti at 3440x1440. The game holds 120 with headroom unknown
  (GRAPHICS-ENHANCEMENT: `nvidia-smi` utilisation is the headroom figure). If the base rate drops below 120 while
  LSFG runs, lower the flow scale (the tool's own guidance is a reduced flow scale above 1080p [recalled]) or the
  internal resolution / MSAA.
- **Measuring it**: `frame_stats.py` reads the game's telemetry, so it reports the *base* rate (it must stay
  120.0, sd small) - that is the "did LSFG steal GPU time from the game" check. The displayed rate is Lossless
  Scaling's own counter (draw-FPS overlay, "120 / 179"). Artefacts are judged by eye, or with a phone's slow-motion
  camera on the HUD digits.

## 6. What was prepared (lab scripts)

All in `C:\Users\james\i76-uncap-lab`. Self-tested tonight on a throwaway fake game folder (copy, hard links,
exclusions, baseline, switch, refusal paths, restore); **not** run on the real sandbox beyond `-Plan`, because a
test run was using it.

- `tools\renderers\make-renderer-copy.ps1` - builds `<lab>\game-alt` (or `-Dest <lab>\game-<name>`) from `game\`,
  read-only on the source. Skips `save-backup-*`, `save-probes-*`, logs and the lock; if a run is in progress it
  takes `STRLKUP.DLL` from `STRLKUP.DLL.pretest` and the conf from `dgVoodoo.conf.pre-graphics`, so the copy holds
  the sandbox's own files, not a test build. Default is a full copy (487 MB placed). `-HardLinkAssets` hard-links
  only `smk\`, `music\`, `I76.ZFS`, `DATABASE.MW2` (399 MB) and copies the remaining 88 MB: a hard link *is* the
  source file, so nothing the game or a script may rewrite is ever linked. Writes `.renderer-copy.json` (md5 of
  every top-level dll / exe / conf / ini) and verifies the key binaries against the source. `-Plan` prints and
  writes nothing. `-Renderer <set>` chains into the switcher.
- `tools\renderers\switch-renderer.ps1` - sets `dgvoodoo` (baseline, or another dgVoodoo version from `-Source`),
  `nglide`, `openglide-gog`, `openglide`, `custom`; overlays `dxvk`, `reshade` (`-ReShadeAs dxgi|d3d9|opengl32`);
  `-DDraw keep|park|ddrawcompat`; `-CompatLayer` (the 256COLOR layer for the copy's own `i76.exe`, an HKCU value
  keyed by that path - the one write outside the copy, recorded and undone by `-Restore`); `-Status`. On first use
  it saves every renderer slot file to `<copy>\_renderer-baseline\`; every switch returns to that baseline first,
  resolves all sources before touching anything, checks each DLL is 32-bit x86 and identifies as what it claims,
  verifies each write by md5, and appends before/after md5s to `<copy>\.renderer-switch.jsonl`. It refuses
  `<lab>\game` and any path outside the lab.
- `autotest\proxy-run.ps1 -GameDir <copy> [-GameArgs "-d3d"]` - new parameters; defaults unchanged (`..\game`,
  `-glide`). It refuses a folder outside `i76-uncap-lab`. `autotest\test-escmenu.ps1` passes the same two through.
- `.gitignore`: `game-*/`.

Harness limits under a non-dgVoodoo wrapper: `maplib.ps1` (`Capture-UI`, `Click-UI`, `Get-UIRect`) derives the
frame rectangle from `..\..\game\dgVoodoo.conf`, i.e. from dgVoodoo's scaling. Under another wrapper the *memory*
reads, the pin test's raw `SetCursorPos` / `GetCursorPos` / `GetClipCursor` values and `frame_stats.py` are valid;
the cropped captures and `Click-UI` coordinates are not, until the map is re-derived for that wrapper.

## 7. Test plan (for the integrator, at the physical console)

Preconditions for every run: not RDP (`[System.Windows.Forms.SystemInformation]::TerminalServerSession` false),
no `i76` process, `game\.console-test.lock` free, the desktop refresh read and written down. All runs on
`game-alt`, never `game\`, never the playable install.

```powershell
cd C:\Users\james\i76-uncap-lab
.\tools\renderers\make-renderer-copy.ps1                   # once; add -HardLinkAssets to save 399 MB
```

**Per candidate, the same five measurements** (n = 2 runs each for any number that will be compared; the repeat is
the noise floor):

| # | measurement | tool | pass / what to record |
|---|---|---|---|
| M1 | boots into a mission | `autotest\proxy-run.ps1 -GameDir ..\game-alt -Mission t01 -Hold 0 -Run {...}` | "in mission after N s"; the proxy log lines (no `CRASH`); `u32x.log` |
| M2 | pacing at the desktop refresh | inside `-Run`: `python C:\Users\james\i76-everywhere\tools\telemetry\frame_stats.py 15 <tag>`; three conditions: no cap, `-Env @{ I76_FPS_CAP = "179" }`, `-Env @{ I76_FPS_CAP = "120" }` | fps, dt mean / sd / p99. Pass for 179: mean 5.59 ms, sd < 0.3 ms, no 8.3 or 16.7 ms mode. Uncapped mean dt = the engine + wrapper frame cost (headroom) |
| M3 | pointer box | `autotest\test-escmenu.ps1 -Stage open -Tag <cand> -GameDir ..\game-alt`, then `-Stage close -GameDir ..\game-alt` | the two "cursor after SetCursorPos" lines and `osclip` / `client`: under dgVoodoo the cursor pushed to x = 3400 comes back clamped to the 1920-wide box. Pass: the pointer reaches the drawn right edge of the menu (x up to 2680 on this panel) |
| M4 | picture | `tools\graphics\capture-frame.ps1 -Out captures\renderers\<cand>.png` inside `-Run`, same mission, parked car, 8 s after entry | the frame rectangle it prints; compare with the dgVoodoo baseline shot via `make-crops.py` (terrain edge, thin pole, HUD text, near texture). Under exclusive fullscreen the capture may be black: note it, use a phone |
| M5 | regressions | 10 minutes by hand: Esc menu, save screen, garage DONE, hood view (F6), binoculars (B), Alt+Tab and back, quit | each of L5's known behaviours, plus sound and music |

**Order of work.**

*Tonight, no downloads:*

1. **Baseline on the copy** (control): `switch-renderer.ps1 -Status` (must read "baseline"), then M1-M4 with
   `-Env @{ I76_GLIDE_REFRESH = "120" }`. Expect the FPS-120 numbers (120.1 fps, sd 0.06 ms). This proves the copy
   and the `-GameDir` path behave like `game\`. Run it twice.
2. **Lossless Scaling adaptive on 120**: copy the profile, set `LSFG3Mode1` to adaptive with target 179 (in the
   program's UI: the XML value names for adaptive were not checked), start
   `...portable-20260801\Lossless Scaling\LosslessScaling.exe`, run step 1's command with `-Hold 120`. M2 must
   still read 120.0; record the tool's own displayed-rate counter; judge HUD digits and the horizon by eye.
   Then queue target 0 vs 1.
3. **`-d3d` through dgVoodoo**: `proxy-run.ps1 -GameDir ..\game-alt -GameArgs "-d3d"` (M1; the first question is
   whether the proxy's hooks attach and the mission boots), then M2 (no cap / 179), M3, M4. If it boots, add
   `Filtering = 16` under `[DirectX]` in `game-alt\dgVoodoo.conf` and repeat M4 on the near-road crop.
4. **GOG OpenGLide pacing probe**: `switch-renderer.ps1 -Renderer openglide-gog -CompatLayer` (DDraw parked,
   256COLOR layer on the copy's exe only), M1, then M2 with no cap and with 179. Whatever happens,
   `switch-renderer.ps1 -Restore` afterwards (removes the layer value) and confirm with `-Status`.

*After the owner approves downloads* (unpack into `C:\Users\james\i76-uncap-lab\refs\renderers\<name>\`, which is
git-ignored; never run an installer):

5. **nGlide**: `& 'C:\Program Files\7-Zip\7z.exe' x nGlide210_setup.exe -orefs\renderers\nglide`, confirm
   `glide2x.dll` and `nglide_config.exe` are there and read the readme for the environment-variable names.
   `switch-renderer.ps1 -Renderer nglide` (DDraw kept). Settings: back end Vulkan first, resolution "By desktop",
   aspect "Preserve original", vsync **off**, refresh "By app". M1. If it dies at boot or sim entry, try in turn
   `-DDraw ddrawcompat` and `-DDraw park -CompatLayer`. Then M2 (no cap; 179; and vsync on without a cap), M3, M4,
   M5; repeat M2-M3 in the Alt+Enter window and with the Direct3D back end.
6. **DXVK 2.7.x under dgVoodoo**: `switch-renderer.ps1 -Renderer dgvoodoo -Overlay dxvk -OverlaySource refs\renderers\dxvk\x32`;
   M1, M2 with `I76_GLIDE_REFRESH` unset / 120 and `I76_FPS_CAP=179`; a `dxvk.conf` with `dxgi.syncInterval = 0`
   as a second condition. If the rate is still exactly the Glide refresh, dgVoodoo's timer is the pacer: stop.
7. **DDrawCompat + `-d3d`**: `switch-renderer.ps1 -Renderer dgvoodoo -DDraw ddrawcompat` and `-GameArgs "-d3d"`;
   M1-M4; note `CpuAffinity`.
8. ReShade, OpenGLide-HD, the crazii fork: only after 1-7 pick a renderer.

**Deliver:** one table (candidate x M1-M5, with n), the pin-test lines, the crops, and a pick. Promotion of a
winner into `game\` and later the playable install is a separate, announced step.

## 8. Downloads awaiting approval (nothing was fetched)

| id | what | URL | size | licence | needed for |
|---|---|---|---|---|---|
| D1 | nGlide 2.10 installer (to be **opened with 7-Zip, not run**) | https://www.zeus-software.com/files/nglide/nGlide210_setup.exe (page: https://www.zeus-software.com/downloads/nglide) | 4.75 MB | freeware, closed source, redistribution terms in its readme | rank 1 |
| D2 | DXVK, the **last 2.7.x** release tarball (2.7.1 as far as recalled; use `x32\d3d11.dll`, `x32\dxgi.dll`). Not 3.x: it needs NVIDIA driver 575.51.02+, this PC has 560.94 | https://github.com/doitsujin/dxvk/releases | about 9 MB (not checked) | zlib | rank 5 |
| D3 | ReShade 6.8.0 setup (open with 7-Zip for `ReShade32.dll`) + the standard shader pack | https://reshade.me/downloads/ReShade_Setup_6.8.0.exe | a few MB (not checked) | BSD 3-clause | rank 8 |
| D4 | DDrawCompat v0.7.1 (`DDrawCompat-v0.7.1.zip`: one `ddraw.dll`) | https://github.com/narzoul/DDrawCompat/releases/tag/v0.7.1 | under 1 MB (not checked) | free (0BSD per the repo; confirm on download) | rank 6, and nGlide's DirectDraw fallback |
| D5 | dgVoodoo 2.87.5 (`dgVoodoo2_87_5.zip`) | https://github.com/dege-diosg/dgVoodoo2/releases | about 9 MB (not checked) | freeware | rank 9 (optional) |
| D6 | w64devkit x86 (32-bit GCC) to build OpenGLide-HD from the repo's patch; plus `git clone https://github.com/voyageur/openglide` | https://github.com/skeeto/w64devkit/releases | about 40 MB (not checked) | toolchain: GPL/various; OpenGLide: LGPL | rank 7 |
| D7 | crazii/openglide source (no binary releases) | https://github.com/crazii/openglide | small | LGPL-2.1 | rank 7 (alternative base) |
| D8 | DxWnd | https://sourceforge.net/projects/dxwnd/ | about 10 MB (not checked) | GPL | not proposed for Windows |

Sizes marked "not checked" are estimates; read the real figure off the release page before approving.

## 9. What is not known (stated so nobody reads the table as measured)

- **Every "could fix" above is a prediction** except the limits L1-L5 themselves. No alternative renderer has been
  run on this PC. The July OpenGLide and DDrawCompat work was on the laptop.
- nGlide's option list is from a third-party guide and the 1000 fps cap from the same guide; zeus-software.com
  refuses automated fetches (a bot wall), so its own readme, compatibility list (is I'76 on it?) and
  environment-variable names were **not** read today. Read `nglide_readme.txt` from the unpacked installer first.
- Whether nGlide's window or fullscreen scaler leaves the pointer alone, clips it, or scales it: unknown.
- Whether dgVoodoo's pacing is a timer inside `glide2x.dll` or rides on the D3D11 present: unknown (the sampler
  only showed the wait under the NVIDIA driver's present). The DXVK test answers it.
- Whether the proxy's exe-side hooks behave under `-d3d` or the software path: never run.
- The 119 / 179 refresh reading in section 1.

## Sources

Local: `docs\FPS-120.md`, `docs\GRAPHICS-ENHANCEMENT.md`, `docs\FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md` (7.1 and
the wrapper survey), `docs\HD-TEXTURES-RESEARCH.md`, `docs\VOODOO-PARKED.md`, `docs\MODERN-PORTS-AND-VR.md`,
`docs\RUNNING-I76-EVERYWHERE.md`, `docs\VERIFIED-FIXES.md`, `docs\WINDOWS-PLAYBOOK.md`, `swap-renderer.ps1`,
`tools\openglide-hd\README.md`, `PLAY-i76.ps1`, `Setup-FrameGen.ps1`; lab `docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md`,
`docs\CONFIG-OPTIONS.md`, `autotest\proxy-run.ps1`, `autotest\test-escmenu.ps1`, `game\OpenGLid.log`,
`game\DDrawCompat-i76.log`, `game\u32x.log`; i76-map `subsystems\renderer.md`.

Web, fetched 2026-10-02:

- nGlide 2.10, installer URL, freeware: https://wingetly.io/apps/zeus-software/n-glide ; size and system-folder
  install: https://libertycity.net/files/gta-1/144208-nglide-v2.10.html ; options, Alt+Enter window, 1000 fps cap,
  per-folder DLL use: https://www.insertmorecoins.es/en/nglide-guide-3dfx-voodoo-wrapper/ ; registry location
  (search result for the nGlide gamma key under `HKEY_CURRENT_USER\Software\Zeus Software\nGlide`); nGlide + ReShade:
  https://reshade.me/forum/troubleshooting/888-solved-nglide-reshade
- dgVoodoo releases 2.87.3 / 2.87.4 / 2.87.5: https://github.com/dege-diosg/dgVoodoo2/releases ; Glide and
  Alt+Enter (Dege): https://www.vogons.org/viewtopic.php?t=79514
- DXVK releases and driver requirements: https://github.com/doitsujin/dxvk/releases ,
  https://github.com/doitsujin/dxvk/releases/tag/v3.0 , https://github.com/doitsujin/dxvk/wiki/Driver-support ;
  2.7 requirements (Vulkan 1.3, NVIDIA 550.54.14): https://linuxiac.com/dxvk-2-7-drops-legacy-driver-support-brings-performance-boosts/
- DDrawCompat v0.7.1 and its settings: https://github.com/narzoul/DDrawCompat/releases
- OpenGLide fork: https://github.com/crazii/openglide ; psVoodoo: https://sourceforge.net/projects/psvoodoo/ ,
  https://psvoodoo.sourceforge.net/ ; Zeckensack's wrapper: https://alternativeto.net/software/zeckensack-s-glide-wrapper/about
- ReShade 6.8.0: https://reshade.me/
- Lossless Scaling (fixed / adaptive modes, windowed-only): https://store.steampowered.com/app/993090/Lossless_Scaling/ ;
  adaptive frame generation and queue target: https://techenclave.com/t/lossless-scaling-3-1-adds-adaptive-frame-generation/273906
- Not reachable today: zeus-software.com (bot wall), pcgamingwiki.com (403), web.archive.org (blocked),
  interstate76.fandom.com (402).
