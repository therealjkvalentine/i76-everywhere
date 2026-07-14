> **STATUS (2026-07-11): PARKED / partly superseded.** This is the dgVoodoo saga's root-cause log. Its "future fix: persist the pipeline cache" is now known to be a *floor, not a fix* — the Voodoo mode is parked. See [VOODOO-PARKED.md](VOODOO-PARKED.md) for the settled verdict and [README.md](README.md) for the doc map.

# dgVoodoo2 over Wine's DXGI on Apple Silicon — full research log

*(Interstate '76, Sikarugir Wine 10 (wow64), macOS 26, M5 Pro. Written 2026-07-04, the day of
the experiments. Companion to [../README.md](../README.md). This exists so a future person —
human or agent — can pick this up without re-burning the tokens.)*

## TL;DR

**dgVoodoo2 works on the free Mac stack — with three conditions discovered the hard way:**

| Condition | Why |
|---|---|
| dgVoodoo **≤ 2.8.2** (we ship 2.78.2), NOT 2.81+ | 2.81+ rewrote device/adapter enumeration init and it cannot survive Wine's DXGI answers - crashes at first present ([dxvk#5217](https://github.com/doitsujin/dxvk/issues/5217), [wine bug 58731](https://bugs.winehq.org/show_bug.cgi?id=58731)) |
| **DXVK** (engine-bundled, swapped over wined3d's d3d11), NOT wined3d | wined3d's Vulkan backend on MoltenVK refuses feature level 10.1 (`wined3d_select_feature_level: None of the requested D3D feature levels is supported`); its GL backend was not reachable for d3d11 in this build |
| Wrap **Glide only**, NOT DDraw (the "hybrid") | with both wrapped, dgVoodoo creates two D3D11 swapchains (Glide 1280x960 + shell 640x480) on two separate `WineMetalView`s in one window; winemac stacks them so the presented shell is invisible -> black screen with "healthy" presents at ~0.44fps |

Result: 2D shell renders via Wine's builtin ddraw (as before), the 3D sim renders via
dgVoodoo Glide -> DXVK -> MoltenVK -> Metal at 1280x960, **with the 3dfx gamma-lifted bright
colors matching the Windows reference build**, windowed, with dgVoodoo `FPSLimit=20` stacked on
top of the exe's own AiO 20fps limiter.

## The question that started this: "why can't we emulate *real* DXGI in Wine?"

Wine **does** implement DXGI, and thousands of games run on it — but games overwhelmingly use
the mainstream 20% of the API (factory -> adapter -> swapchain -> `Present`). dgVoodoo2 is not a
game: it's a low-level emulator of 1990s display hardware, so it leans on the exotic corners —
`IDXGIOutput::WaitForVBlank` (3dfx vblank timing), `GetGammaControl`/gamma caps (Voodoo hardware
gamma), `GetFrameStatistics`, and strict adapter-identity assumptions during enumeration. Those
are exactly the parts Wine stubs (`fixme:dxgi:...stub!`), because almost nothing else calls them.

Old dgVoodoo (≤2.8.2) treats a stubbed answer as "old/weird driver, carry on".
New dgVoodoo (2.81+) trusts its enumeration data and dereferences what isn't there.
So the honest answer: we *can* — Wine's DXGI is real enough for dgVoodoo 2.78.2 as proven here;
it is not (yet) complete enough for dgVoodoo 2.81+.

## The working architecture

```
i76.exe -glide          (32-bit, wow64, GOG 2019 exe == AiO patch, built-in 20fps limiter)
├── 2D shell: ddraw ──────────── Wine builtin ddraw -> wined3d -> OpenGL   (visible, as always)
└── 3D sim:  Glide2x.dll ─────── dgVoodoo 2.78.2 (Glide->D3D11 FL10.1, windowed, FPSLimit=20)
                                   └── d3d11.dll = DXVK-Kegworks 1.10.4-async (engine bundle,
                                       swapped into wine/lib/wine/i386-windows/)
                                         └── wine dxgi (builtin) + winevulkan -> MoltenVK -> Metal
```

Files: `Glide2x.dll` (dgVoodoo 2.78.2 x86) + `dgVoodoo.conf` in the game dir; engine
`d3d11.dll`/`d3d10core.dll` replaced by the wrapper's own `Contents/Frameworks/renderer/dxvk/wine/*`
copies (originals kept as `*.wined3d-backup`). No DllOverrides needed for the hybrid (glide2x has
no builtin; ddraw stays builtin on purpose).

## Attempt log (what we tried, in order, with the evidence)

| # | Config | Result |
|---|---|---|
| 10 | dgVoodoo **2.87.3** Glide+DDraw, wined3d d3d11 | `wined3d_select_feature_level: None of the requested D3D feature levels is supported` -> game's "Failed to initialize 3D hardware acceleration" dialog -> its usual null-deref crash (`i76+0x75406`) |
| 11 | + DXVK d3d11/d3d10core dropped in **game dir**, `WINEDLLOVERRIDES=n,b` | DXVK never engaged (game-dir copy resolves as builtin-by-name; wine loads the engine's) — same FL failure |
| 12 | + DXVK swapped into the **engine lib dirs** | DXVK banner, `D3D11CoreCreateDevice: Using feature level D3D_FEATURE_LEVEL_10_1`, MoltenVK swapchain 1280x960 created — then page fault at `0x79F119BD` (constant address, garbage read) right after `dxgi_output_WaitForVBlank ... stub!` on first present |
| 13 | + `ForceVerticalSync=false` | identical crash (dgVoodoo paces via vblank regardless) |
| 14 | + `PresentationModel=discard`, `FPSLimit=0` | identical crash — proving it's the 2.81+ init/enumeration regression, not a specific present setting |
| 15 | dgVoodoo **2.78.2** Glide+DDraw over DXVK | **No crash.** Survives the same `WaitForVBlank`/`GetGammaControl` stubs. But black window: two swapchains on two stacked `WineMetalView`s; shell presents ~0.44fps to the hidden one |
| 16 | + `DeferredScreenModeSwitch=true`, `FastVideoMemoryAccess=true` | still black (not a mode-switch/lock issue; it's view stacking) |
| 17 | **hybrid**: remove dgVoodoo DDraw, keep Glide only | **WORKS.** Shell visible via wine ddraw; sim renders via dgVoodoo at 1280x960 with bright 3dfx-gamma colors (screenshot-verified against the Windows reference) |

Crash-autopsy tooling that helped: `HKLM\...\AeDebug\Debugger = winedbg --auto %ld %ld` (backtrace
into the log), `WINEDEBUG=+fps,+timestamp,+loaddll`, MoltenVK's `[mvk-info]` swapchain lines, and
`CGWindowList`-based window-bounds sampling to catch the -16000 minimize dance.

## Known remaining rough edges

- The shell still holds Wine's ddraw **exclusive fullscreen**, so the
  minimize-on-focus-loss quirk (see README "saga") still applies when alt-tabbing in menus;
  `WindowsFloatWhenInactive=all` + auto-restore make it livable. In-sim, presentation is
  dgVoodoo's windowed D3D11.
- In-sim FPS (should be 20 from two stacked limiters) and Mission-5-ramp physics still need a
  focused play-test to formally verify.
- `warn: D3D11CoreCreateDevice: Adapter is not a DXVK adapter` — dgVoodoo enumerates through
  wine's dxgi (wined3d adapter identity) and DXVK accepts it anyway. Harmless today; this seam is
  exactly where dgVoodoo 2.81+ dies.

## The two frictions that keep the hybrid off the default (2026-07-04, follow-up session)

Both are real and neither is quickly fixable on this exact stack:

1. **Per-launch shader warmup is uncacheable here.** Pipeline path is Glide -> DXVK (D3D->SPIR-V)
   -> MoltenVK (SPIR-V->MSL->`MTLLibrary`/pipeline). DXVK's `i76.dxvk-cache` (state cache) persists
   *which* pipelines to build across launches, so DXVK-async pre-declares them - but the actual
   SPIR-V->Metal compile lives in MoltenVK, and **this MoltenVK (from `dxvk-macOS-async-v1.10.3-20230507`,
   ~MoltenVK 1.2.x) exposes no persistent pipeline cache**. Full `MVK_CONFIG_*` env dump confirmed:
   `SHADER_DUMP_DIR` (debug), `SHADER_COMPRESSION_ALGORITHM`, `SHOULD_MAXIMIZE_CONCURRENT_COMPILATION`
   exist, but there is **no `MVK_CONFIG_*PIPELINE_CACHE*` / on-disk Metal binary-archive option**.
   So ~2 min of first-session slideshow while it compiles cold, every launch. (Symptoms match
   exactly: crawl -> smooth -> one-time hitch on first explosion.)
2. **Glide wrappers read their config from the CWD; the Sikarugir launcher's CWD isn't the game
   dir.** Launched via `open Interstate 76 - Software (DxWnd).app`, dgVoodoo misses `dgVoodoo.conf` (defaults:
   `FullScreenMode=true` -> fullscreen black + "Failed to initialize 3D hardware acceleration").
   **Later confirmed NOT dgVoodoo-specific: plain OpenGLide misses `OpenGLid.INI` the same way**
   (defaults to fullscreen -> identical fullscreen-black symptom). Any Glide provider must be
   launched with CWD = game dir; `play.sh` and the I76 Launcher app do exactly that. `-gdi` reads
   no INI and is immune, so it's the only mode safe to launch via the wrapper's own `open`.

## Postscript 2: the Sikarugir launcher itself breaks Glide (and the fix)

Chasing why wrapper (`open`) launches of plain `-glide` went fullscreen-black while identical CLI
launches worked exposed a second launcher-injected killer: the Sikarugir launcher hardcodes
**`CX_FWD_COMPAT_GL_CTX=1`** (no plist key controls it). A forward-compatible GL context removes
all legacy OpenGL - OpenGLide is pure immediate-mode legacy GL - reproduced as a crash at
`i76+0x4507C` by setting just that env var on an otherwise-working CLI launch. Combined with the
CWD/INI issue, the stock launcher cannot start this game's Glide mode at all.

Fix that shipped: the wrapper's `Contents/MacOS/Sikarugir` executable is replaced with a small
compiled Mach-O stub ([`i76-launch-stub.swift`](../i76-launch-stub.swift)) that sets the env,
`cd`s into the game dir, and `execv`s wine directly (original launcher kept as `Sikarugir.orig`).
Two implementation traps for future porters: LaunchServices on macOS 26 silently refuses shell
scripts as bundle executables (must be Mach-O), and `codesign --deep` chokes on the
`launcher`/`wineskinlauncher` symlinks - sign just the new executable ad-hoc instead.

## Postscript 3: async measured — the warmup is real and survives every knob (final verdict)

The bundled DXVK is async-capable but **async is opt-in and was off during all earlier tests**
(`dxvk.enableAsync = true` in `dxvk.conf` / `DXVK_ASYNC=1`). With async confirmed active
("Using 12 async compiler threads") plus `MVK_CONFIG_SHOULD_MAXIMIZE_CONCURRENT_COMPILATION=1`,
a real play session still measured **69 seconds at 0.2-0.4 fps after mission start, then a snap
to the full 20 fps cap**. The bottleneck is per-pipeline SPIR-V->MSL conversion + Metal compile
inside MoltenVK under Rosetta, which nothing at config level can persist or hide (async skips
draws but this game's first frames need nearly every pipeline). Conclusion: the hybrid is
parked; `-gdi` ships. The fix remains item 0 below (cereal-built MoltenVK + a DXVK that
serializes `VkPipelineCache`).

## Postscript: the hybrid was retired (same day)

After all that, plain OpenGLide `-glide` (CWD-fixed) turned out to deliver the same bright
3dfx-gamma sim - the game sets Glide gamma itself, any honest Glide implementation shows it -
with **no shader warmup** (direct OpenGL, no DXVK/Metal pipeline compilation) and no dgVoodoo
version fragility. dgVoodoo+DXVK added a ~2-min uncacheable warmup for zero visual gain here, so
the shipping config is OpenGLide. Everything above remains valid (a) as the only documented
dgVoodoo-under-Wine-on-Mac recipe, (b) as the fallback if the OpenGL path breaks in a future
macOS/Wine, and (c) for the Wine-DXGI findings.

## For future research (pick-up points, in order of promise)

0. **Kill the warmup: persistent pipeline cache.** (Corrected after reading MoltenVK docs.) The
   mechanism exists and is the *standard* one: MoltenVK serializes the SPIR-V->MSL conversion
   result inside `VkPipelineCache` data - **if built with `MVK_USE_CEREAL=1`** ([MoltenVK user
   guide](https://github.com/KhronosGroup/MoltenVK/blob/main/Docs/MoltenVK_Runtime_UserGuide.md)).
   On reload it skips the expensive conversion. Two things must both be true, and neither is
   config-flippable here: (a) the bundled MoltenVK must be a cereal-enabled build (this 2023 one
   is not, judging by its env-var surface), and (b) **DXVK must write its `VkPipelineCache` to
   disk and reload it** - stock DXVK relies on driver disk caches (Mesa on Linux) and does not
   persist the Vulkan-level cache itself. So the fix is a patched stack: cereal-built MoltenVK +
   a DXVK (or wrapper shim) that serializes the pipeline cache. Note Metal's own system shader
   cache does not rescue this: the repeated cost is the in-process SPIR-V->MSL conversion, not
   only the MSL->binary compile.

1. **Real DXGI (untested, staged):** upstream DXVK's x32 `dxgi.dll` (mingw PE from
   [dxvk 1.10.3 release](https://github.com/doitsujin/dxvk/releases/tag/v1.10.3)) can be swapped
   into `wine/lib/wine/i386-windows/dxgi.dll` (back up the original; also pair upstream d3d11).
   Its Win32-surface path goes through winevulkan like everything else, so it *may* just work.
   If it does: adapters become genuinely DXVK's, `WaitForVBlank`/gamma are implemented, and
   **dgVoodoo 2.87.x might work** — retest attempt 10 config first. Risk: Gcenx deliberately
   never ships dxgi on macOS (D3DMetal coexistence and MoltenVK quirks are the suspected
   reasons); an untested pairing may hang at device/present. This is the single highest-value
   experiment nobody has published results for.
2. **Watch these to know when to retry 2.87+:** [wine bug 58731](https://bugs.winehq.org/show_bug.cgi?id=58731)
   (newer dgVoodoo fails to initialize), [dxvk#5217](https://github.com/doitsujin/dxvk/issues/5217),
   dgVoodoo changelogs for "Wine" mentions (dege has fixed Wine issues before), and Wine release
   notes for `dxgi_output_WaitForVBlank`/`GetGammaControl` gaining real implementations.
3. **The winemac two-swapchain stacking bug** is the root blocker for full DDraw+Glide wrapping.
   Fix would land in winemac.drv's view management (`cocoa_window.m` — how multiple Metal/Vulkan
   views order within one `WineWindow`). If Sikarugir/Kegworks ever advertises "multiple Vulkan
   swapchains per window", retest attempt 15's config.
4. **Implementing the DXGI stubs in Wine** is genuinely small work for someone set up to build
   wine-on-mac: `dlls/dxgi/output.c` — `WaitForVBlank` can be approximated with a
   display-link-derived sleep; `GetGammaControl`/`SetGammaControl` can return identity/no-op with
   S_OK. That plus enumeration polish is likely all dgVoodoo 2.87+ needs. (The Sikarugir engine
   is a Gcenx `wine-private` build; upstream-first is the sane route.)
5. **D3DMetal for 32-bit** would open `OutputAPI=bestavailable` -> Metal-native D3D11 with
   Apple's full DXGI surface. Watch Game Porting Toolkit release notes for 32-bit PE support
   (none as of GPTK 3 / mid-2026).
6. Version-bisect detail if needed: GitHub has full binaries for 2.87.x and **2.63**; 2.78.2 came
   from [archive.org](https://archive.org/details/dgvoodoo2_78_2_202205); 2.79.3–2.8.2 zips are
   currently 404 on dege's site (his GitHub releases for those tags carry only API zips) — the
   wayback machine has no captures. If someone finds a 2.8.2 binary, it's the newest known-good.

## Cost ledger (what the tokens bought)

Roughly 8 launch-observe-diagnose cycles at ~2-4 min each, plus web research. Permanent yield:
the three-condition recipe above, a validated bright-color hybrid build, the 2.81+ regression
diagnosis matched to public issues, the winemac view-stacking discovery (previously undocumented
anywhere we could find), crash-autopsy tooling, and this doc.