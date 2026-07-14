# DXVK with persistent VkPipelineCache (kills MoltenVK shader-warmup hitching)

Rebuild of the 32-bit DXVK `d3d11.dll` in the Sikarugir wrapper with one addition:
the Vulkan pipeline cache is loaded from disk at startup and saved back
periodically and at shutdown.

Verified in place 2026-07-09: run 1 logs `Loaded VkPipelineCache initial data: 0
bytes` then `Saved VkPipelineCache: 61309 bytes` (menu only — grows with play);
run 2 logs `Loaded VkPipelineCache initial data: 61309 bytes`.
`i76.vkpipeline-cache` sits next to `i76.dxvk-cache` in the game dir.

## Why

Every first-seen pipeline costs MoltenVK a SPIRV→MSL translation plus a Metal
compile — that is the in-game hitching during "shader warmup". MoltenVK
serializes its compiled MSL into the `VkPipelineCache` blob, but DXVK 1.10.x
never creates a real `VkPipelineCache` at all — the class in
`src/dxvk/dxvk_pipecache.h` is a stub whose `handle()` returns `VK_NULL_HANDLE`
— so nothing is reused, within a session or across sessions.

With the patch, run 1 primes `i76.vkpipeline-cache`; from run 2 on MoltenVK
skips the SPIRV→MSL conversion for every pipeline already in the file. This
composes with (does not replace) DXVK's own state cache (`i76.dxvk-cache`,
`DXVK_STATE_CACHE`): the state cache replays pipeline state vectors early, the
Vulkan pipeline cache makes each of those creations cheap. Keep both enabled.

## Source base — read this before "upgrading"

The wrapper-shipped `d3d11.dll` identifies as `DXVK-Kegworks v1.10.4-async`
(Kegworks was renamed Sikarugir; `github.com/Kegworks-App/*` now redirects to
`Sikarugir-App/*`). Its exact source tree is not public: it is DXVK-Sarek
v1.10.4 (`Sikarugir-App/dxvk` commit `505d9281` on branch `1.10.x-Proton-Sarek`)
plus Sporif's `dxvk-async-af418dc.patch` plus the DXVK-macOS hacks plus
"DXVK-Kegworks" rebranding.

**Attempt 1 (failed, documented so nobody repeats it):** building from Sarek
v1.10.4 + the Sporif async patch reproduces the version string but NOT the
macOS feature-level relaxations, and the game dies at
`err: D3D11CoreCreateDevice: Requested feature level not supported` — stock
DXVK hard-requires `geometryShader`, `transformFeedback`, `tessellationShader`
etc. for FL 10_0/10_1, none of which MoltenVK offers. The relaxations
(`enabled.core.features.X = supported.core.features.X` in
`src/d3d11/d3d11_device.cpp:GetDeviceFeatures`, plus "[HACK] Imported DXVK-CX21
hacks", "[d3d11-macOS] Only require Vulkan 1.1 core") live only on the macOS
branches.

**What works (this build):** `Gcenx/DXVK-macOS` branch `1.10.x`, commit
`8f1e28de` (= tag `v1.10.3-20230507-repack`; `Sikarugir-App/dxvk` mirrors the
same branch). That branch already contains the async compiler
(`dxvk.enableAsync`, `dxvk.numAsyncThreads`, `DXVK_ASYNC`) and every macOS fix.
The delta to the shipped v1.10.4-async binary is only Sarek's v1.10.3→v1.10.4
backports: per-game config entries (none for i76) and d3d9/dxgi tweaks —
nothing in the d3d11/dxvk-core path i76 uses. Confirmed in-game: FL 10_1
device created, menu renders, async threads active.

## Build (macOS, Homebrew)

```sh
brew install mingw-w64 meson ninja glslang

git clone --recursive https://github.com/Gcenx/DXVK-macOS.git dxvk
cd dxvk
git checkout 8f1e28de            # branch 1.10.x, v1.10.3-20230507-repack
git apply dxvk-persist-vkpipelinecache.patch

meson setup --cross-file build-win32.txt --buildtype release build.w32
ninja -C build.w32 src/d3d11/d3d11.dll
```

- `build-win32.txt` in the repo already names the `i686-w64-mingw32-*` binaries.
- The patch includes the `version.h.in` bump to
  `"v1.10.3-20230507-async (macOS) vkpc"` — the `vkpc` suffix is how you tell
  the patched DLL apart in logs. (`version.h.in` has no `@VCS_TAG@`
  placeholder on this branch, so meson's `vcs_tag()` copies it verbatim;
  no git-describe magic applies.)
- Compiles clean with mingw-w64 GCC 16.1 / meson 1.11.

## Post-processing (strip + Wine builtin marker)

The shipped DLL is stripped and carries Wine's builtin-DLL marker in the DOS
stub at offset 0x40. Replicate both:

```sh
cp build.w32/src/d3d11/d3d11.dll d3d11-patched.dll
i686-w64-mingw32-strip d3d11-patched.dll
printf 'Wine builtin DLL\0' | dd of=d3d11-patched.dll bs=1 seek=64 conv=notrunc
```

(Safe because mingw's `e_lfanew` is 0x80, so 0x40–0x7F is dead DOS-stub code —
same bytes `winebuild --builtin` writes.)

## Install

```sh
APP=~/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app
DIR=$APP/Contents/SharedSupport/wine/lib/wine/i386-windows
cp "$DIR/d3d11.dll" "$DIR/d3d11.dll.dxvk-unpatched"   # stock Kegworks DXVK (once)
cp d3d11-patched.dll "$DIR/d3d11.dll"
```

Current state of that directory:
- `d3d11.dll` — this patched build (3,633,152 bytes, `vkpc` in version string)
- `d3d11.dll.dxvk-unpatched` — stock `DXVK-Kegworks v1.10.4-async` (4,370,301 bytes)
- `d3d11.dll.wined3d-backup` — Wine's original WineD3D from before the port used DXVK

Do NOT touch `dxgi.dll` (Wine dxgi + DXVK d3d11 via winevulkan is how
Gcenx/Sikarugir builds pair). Rollback = copy `.dxvk-unpatched` back.

## What the patch does

`src/dxvk/dxvk_pipecache.{h,cpp}` — the stub becomes a real cache:

- ctor: reads the cache file, validates the
  `VK_PIPELINE_CACHE_HEADER_VERSION_ONE` header (vendorID / deviceID /
  pipelineCacheUUID against the adapter — stale files from another GPU or
  MoltenVK version are ignored, and `vkCreatePipelineCache` retries empty if
  the driver still rejects the blob), passes it as `pInitialData`.
  Logs `DXVK: Loaded VkPipelineCache initial data: N bytes`.
- a `dxvk-pipecache` thread saves the cache 20 s after device creation, then
  every 60 s, skipping the write when `vkGetPipelineCacheData` reports an
  unchanged size. The periodic save is REQUIRED, not a nicety: the DxWnd
  close-for-real path and `wineserver -k` both end i76 via TerminateProcess,
  destructors never run (DXVK itself bails on `isInModuleDetachment()`), and
  in verification the on-disk file always came from the periodic thread.
- dtor (clean exit): final save + `vkDestroyPipelineCache`.
- writes are atomic: `<file>.<pid>.<n>.tmp` then
  `MoveFileExW(..., MOVEFILE_REPLACE_EXISTING)`; a torn write can never be
  loaded, concurrent devices can never interleave in one temp file.
- path: `$DXVK_VK_PIPELINE_CACHE_PATH/<exe>.vkpipeline-cache`, or
  `<cwd>/<exe>.vkpipeline-cache` when unset — for i76 that is
  `.../GOG Games/Interstate 76/i76.vkpipeline-cache` (cwd = game dir at
  launch), right next to `i76.dxvk-cache`.
- log lines land in the DXVK stderr stream (`DXVK_LOG_LEVEL=info`).

`src/dxvk/dxvk_pipemanager.cpp` — passes the adapter's
`VkPhysicalDeviceProperties` into the cache for header validation. The
existing `vkCreateGraphicsPipelines`/`vkCreateComputePipelines` calls already
route through `m_cache->handle()`, so no other plumbing (meta blit/copy/resolve
pipelines still use `VK_NULL_HANDLE`; they are few and cheap).

## Verify

```
info:  DXVK: v1.10.3-20230507-async (macOS) vkpc                # patched build is live
info:  DXVK: Loaded VkPipelineCache initial data: 0 bytes       # run 1
info:  DXVK: Saved VkPipelineCache: 61309 bytes                 # ~20 s in, then per minute
info:  DXVK: Loaded VkPipelineCache initial data: 61309 bytes   # run 2
```

The file only grows as new pipelines are first seen — expect the big jump the
first time each mission/vehicle/weapon effect is rendered, and expect hitching
to persist through run 1 (priming) and vanish for everything already primed
from run 2 on. First save of each session always writes once even when nothing
changed (per-session size baseline) — that lone `Saved` line at the menu is
normal, not cache growth.
