# DxWnd tuning for Interstate '76 — source-grounded settings map

*Grounded in the actual DxWnd **v2.06.14** source (the version we run; SourceForge
`Sources/v2_06_14_src.rar` — gho's original, newer than the abandoned 2017 github "reloaded"
fork). File:line citations are to that source. This maps each GUI control to the code that
consumes it, so we know what actually does what — not guesses.*

## Aspect ratio / black bars (fill the screen as 4:3, not stretched)

**The fix: Main tab → Position → select `Desktop` (or `Desktop work area`) + check
`Keep aspect ratio`.** Leave `Adaptive ratio` OFF.

Why, from source:
- `Keep aspect ratio` = the **KEEPASPECTRATIO** flag (`flags2`). In the two "Desktop" coordinate
  modes, DxWnd sizes the window to the whole screen and then calls `FixWorkarea()` to shrink it to
  the target aspect, centering with borders = letterbox/pillarbox
  (`dll/dxmapping.cpp:675-695`, cases `DXW_DESKTOP_WORKAREA` / `DXW_DESKTOP_FULL`).
- `FixWorkarea()` (`dll/dxwcore.cpp:1246`) preserves `iRatioX:iRatioY`, which is set **from the
  profile's window size** `sizx0:sizy0` (`dll/dxmapping.cpp:660-661`). Our profile is
  **1280:960 = exactly 4:3**, so the bars come out correct automatically.
- **Position radio → coordinates enum → `coord0` ini** (`Include/dxwnd.h:1041-1044`):
  `X,Y coordinates`=0 (**no letterbox — current setting, this is why it stretched**),
  `Desktop center`=1, `Desktop work area`=2 (fills screen minus menu bar/taskbar), `Desktop`=3
  (entire screen).
- **`Adaptive ratio` (ADAPTIVERATIO, `flags11`) would use the *screen's* w:h as the ratio**
  (`dll/dxwcore.cpp:1251-1253`) → that's the *stretch* behavior, the opposite of what you want.
  Leave it off.
- Gotcha that explains a failed attempt: **`Fix aspect ratio` on the Video tab is NOT this.** It's
  FIXASPECTRATIO (`flags13`), which only fakes the monitor's physical dimensions (HORZSIZE/VERTSIZE
  caps) to games that query them (`dll/gdi32.cpp:858`) — it does not letterbox the output. And
  plain `Keep aspect ratio` in `X,Y coordinates` mode with manual maximize only kicks in when
  DxWnd considers itself fullscreen: `IsFullScreen() = Windowize && FullScreen`
  (`dll/dxwcore.cpp` `IsFullScreen`), and `FullScreen` is only set by the **`Force windowing`**
  checkbox (FORCEWINDOWING, `dll/dxwcore.cpp:405`). So manual-maximize aspect needs
  `Force windowing` + `Keep aspect ratio`; the Desktop-coordinate route needs neither and is
  cleaner.

**ini equivalents** (target section, if setting directly): `coord0=3` (or `2`) and set the
KEEPASPECTRATIO bit in `flag0`. Easiest to do in the GUI.

## Better graphics (upscale filters) — with a real caveat

DxWnd's DirectX-tab **Filter** dropdown (`filterid0` ini; enum `Include/dxwnd.h:956-978`):
`0` none, `1` bilinear 2x, `2-4` HQ 2x/3x/4x, `7-9` PIX, `10-12` Scale2x, `13-15` Scale2K,
`16` dither, `17` halftone. HQx/Scale-family are smart pixel-art upscalers (640x480 → 2-4× with
edge smoothing) — potentially nicer than a raw bilinear stretch.

**Adversarial caveat (from source):** filters are applied only in the **emulated blit path**
(`dll/dxemublt.cpp:3120-3260`, and `oglblt.cpp` for the OpenGL blitter) — i.e. when DxWnd runs an
**emulated/surface renderer**, NOT the **"primary surface"** renderer we currently use (which
blits directly and is what avoids the black menus). So to try a filter you likely must switch the
DirectX-tab **Renderer** away from "primary surface" to an emulated mode — which risks
reintroducing the black-menu/cutscene problem. Net: filters and our black-menu fix are in tension;
try it, but be ready to revert. Also: these filters are CPU-based and run under Rosetta here, so
higher factors (3x/4x) may cost frames.

## Fullscreen without dying — SOLVED

`Terminate on window close` (Main tab) fixed the force-quit-on-exit. Filling the screen is the
aspect-ratio section above (Desktop coordinate mode). There is **no true fullscreen** on winemac
(no exclusive mode; the Desktop coordinate mode + letterbox is the equivalent).

## The hard ceiling (unchanged, confirmed again in source)

The game renders 640×480 internally; DxWnd only *scales the output*. There is **no way to make the
game render at higher internal resolution through DxWnd** (that needs the Glide/D3D path +
dgVoodoo, which reintroduces the shader warmup — see DXGI-DGVOODOO-RESEARCH.md). And the camera is
hardcoded 4:3, so "fill the screen" = a big 4:3 image with black bars, never widescreen. Upscale
filters improve *smoothness*, not internal detail.

## Source reference

Full v2.06.14 source: SourceForge `dxwnd/Sources/v2_06_14_src.rar`. Not vendored here (14 MB of
GPLv3 third-party C/C++); re-fetch if needed. Key files: `dll/dxmapping.cpp` (window sizing +
aspect), `dll/dxwcore.cpp` (FixWorkarea, IsFullScreen, filter setup), `dll/dxemublt.cpp` +
`dll/oglblt.cpp` (filter blits), `host/dxwndhostView.cpp` (GUI-checkbox → flag mapping),
`Include/dxwnd.h` (all enums/flag names).
