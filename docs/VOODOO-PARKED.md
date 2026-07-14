# Interstate '76 "Voodoo" mode on the Mac — parked (2026-07-11)

*The dgVoodoo Glide→Metal path was fully working and genuinely prettier than the shipped software
renderer — but it has one showstopper we cannot fix from our side of the stack, so we're **parking
it**. This doc is the honest ledger: how far we got, the exact blocker, the **one announcement**
that would let us un-park it, and precisely what to do when that lands. Nothing is deleted — the
stub, configs, tools and research all stay in the repo; un-parking is a one-line rebuild.*

## What "Voodoo mode" was

`i76.exe -glide` → dgVoodoo 2.78.2 `Glide2x.dll` → **D3D11 FL10.1 → DXVK → MoltenVK → Metal**. It
turned the game's native 3dfx Voodoo renderer into a modern GPU path on Apple Silicon. Shipped as
its own launcher (`Interstate 76 - Glide-dgVoodoo-DXVK-Metal.app`) alongside the software/DxWnd
default.

## How far we got — it *worked*, and looked good

All verified on an M5 Pro:

- **The whole chain runs.** dgVoodoo enumerates, DXVK creates a FL10.1 device, MoltenVK compiles to
  Metal, the game renders in a real title-barred window. (Getting here took: dgVoodoo **2.78.2**
  exactly — 2.81+ hits a Wine adapter-enumeration regression; **DXVK** swapped into the engine libs
  because wined3d refuses FL10.1; **Glide-only** wrapping because dual swapchains stack invisibly in
  winemac; and a **command-line virtual desktop** to contain the exclusive-fullscreen shell.)
- **Bright 3dfx look.** `EnableGlideGammaRamp = true` restored the gamma lift the software renderer
  lacks (it's a post-process shader, so it works through MoltenVK) — the single biggest visual win.
- **4× MSAA** (native/cheap on Apple's TBDR), **32-bit rendering** (`pure32bit` — no banding), and
  **higher internal resolution** (2×/3× supersampled 4:3). Anisotropic is impossible for Glide in
  dgVoodoo on any platform (it samples in-shader) — that one we correctly ruled out.
- **We fought the warmup hard and made real progress:** a **patched DXVK that persists the Vulkan
  pipeline cache** across runs (`tools/dxvk-pipeline-cache-persist/`), DXVK **dyasync** background
  compilation, and the MoltenVK **parallel-compile** flags (`USE_METAL_PRIVATE_API=1` +
  `SHOULD_MAXIMIZE_CONCURRENT_COMPILATION=1`, plus `FAST_MATH`). We got the warmup down from a
  ~70 s first-mission crawl to a sub-second-ish menu compile for a primed cache.

Full detail: [VISUAL-QUALITY-MAC.md](VISUAL-QUALITY-MAC.md), [DXGI-DGVOODOO-RESEARCH.md](DXGI-DGVOODOO-RESEARCH.md),
[`tools/dxvk-pipeline-cache-persist/BUILD.md`](../tools/dxvk-pipeline-cache-persist/BUILD.md).

## The showstopper — why we're parking it

**MoltenVK cannot persist the *compiled Metal pipeline* across process launches — only the MSL
source.** So every single launch re-pays a Metal-side compile of every pipeline the game uses, and
the first time each piece of content appears in a session it can hitch. We can shrink that
(parallelize it, front-load it into the menu, cache the MSL half) but we **cannot reach zero**, and
we cannot make it a one-time cost. For a 20 fps game where you just want to get in and drive, a
recurring compile pause every launch is the wrong trade versus the software renderer, which has
**no shader compile at all** and starts instantly.

Precisely, from source-level research (all cited in VISUAL-QUALITY-MAC.md):
- MoltenVK's `VkPipelineCache` serializes **MSL source only** (a `cereal` archive). On a cache hit
  it skips SPIR-V→MSL but **still** runs `Compile MSL into a MTLLibrary` → `Compile MTLFunctions
  into a pipeline` every launch.
- Caching the *compiled* pipeline needs **`MTLBinaryArchive`**, tracked in
  **[KhronosGroup/MoltenVK#1765](https://github.com/KhronosGroup/MoltenVK/issues/1765)** — **open
  since Nov 2022, unimplemented**, blocked by an Apple limitation (MTLBinaryArchive only serializes
  to a *file URL*, not client memory; Apple said a direct `NSData` path is "hoped for" but it
  hasn't shipped).
- The standard alternative, **`VK_KHR_pipeline_binary`**, is **not implemented by MoltenVK** either
  (our MoltenVK is 1.4.1 — the latest stable — and it's absent).

So this is a platform-layer gap, not something we can patch in dgVoodoo, DXVK, or our launcher.

## The announcement that un-parks this

Watch **[MoltenVK#1765](https://github.com/KhronosGroup/MoltenVK/issues/1765)** and the MoltenVK
[Whats_New changelog](https://github.com/KhronosGroup/MoltenVK/blob/main/Docs/Whats_New.md). Any one
of these flips the calculus:

1. **MoltenVK ships `MTLBinaryArchive`-backed pipeline caching** (the #1765 feature) — the compiled
   Metal pipeline becomes persistable → warmup goes near-zero on the 2nd+ launch. **This is the one
   to hope for.**
2. **MoltenVK implements `VK_KHR_pipeline_binary`** — DXVK (recent versions) can then hand us
   persistable compiled-pipeline blobs directly.
3. **Apple exposes an `NSData` (in-memory) path for `MTLBinaryArchive`** — this is the upstream
   blocker for #1, so if you see it in Apple's Metal release notes, #1 becomes possible.

A weaker but also-good signal: **DXVK-native gains a mature graphics-pipeline-library / precompile
path that MoltenVK supports** (today `VK_EXT_graphics_pipeline_library` is *not* supported by
MoltenVK and is force-disabled by the async patch).

## What to do when it lands (the un-park playbook)

1. **Update the stack:** bump MoltenVK to the version that shipped the feature (it's a dylib in the
   wrapper's `Contents/Frameworks/`); rebuild/replace DXVK against it if needed
   (`tools/dxvk-pipeline-cache-persist/BUILD.md` has the recipe).
2. **Turn on the new persistence** (env var or dxvk.conf flag — TBD by whatever the feature exposes;
   analogous to how we wired `DXVK_STATE_CACHE` + our VkPipelineCache patch).
3. **Re-measure the warmup** with the closed-loop method in VISUAL-QUALITY-MAC.md: prime once, then
   confirm a fresh launch reaches the menu and drives with **no compile pause**. The realistic
   target is "one short first-ever prime, then instant forever."
4. **If it's near-zero: un-park.** Re-add the Voodoo launcher to the build (one line — see below),
   and consider making it the **default** (it's the prettier mode: gamma + MSAA + higher res).

## Un-parking

> **Note:** [`slim-wrapper.sh`](../slim-wrapper.sh) now removes the **Voodoo GPU stack**
> (`Contents/Frameworks/renderer/` + `libMoltenVK.dylib` + `moltenvkcx`, ~140 MB) since the
> software renderer doesn't use it. If you slimmed the wrapper, un-parking also needs that stack
> back — either `slim-wrapper.sh --restore` (if the quarantine still exists) or a fresh Sikarugir
> wrapper clone. By the time Voodoo is worth un-parking (a new MoltenVK), you'd rebuild the wrapper
> on a current Wine/MoltenVK anyway.

The build side is one line. Restore this in [`build-launchers.sh`](../build-launchers.sh) (kept as a
comment) and run it:

```sh
make_app "Interstate 76 - Glide-dgVoodoo-DXVK-Metal" "com.jkv.i76.voodoo" "i76-voodoo-stub.swift" "Interstate 76 - Glide-dgVoodoo-DXVK-Metal"
```

Preserved in the repo: [`i76-voodoo-stub.swift`](../i76-voodoo-stub.swift) (the launcher, with all
the MVK/DXVK env), [`setup-voodoo.sh`](../setup-voodoo.sh), [`dgVoodoo.conf`](../dgVoodoo.conf) +
[`dxvk.conf`](../dxvk.conf) (the tuned graphics config), [`open-dgvoodoo-settings.command`](../open-dgvoodoo-settings.command)
+ [`setup-dgvoodoo-cpl.sh`](../setup-dgvoodoo-cpl.sh) (the dgVoodoo GUI), and the whole
[`tools/dxvk-pipeline-cache-persist/`](../tools/dxvk-pipeline-cache-persist/) patch. On the game
side the dgVoodoo `Glide2x.dll` + engine DXVK swap are still in place.

## Meanwhile: the Steam Deck already has what the Mac lacks

The same dgVoodoo chain on the **[Steam Deck](STEAMDECK.md)** runs on **native Vulkan** (no
MoltenVK), so the compiled pipelines cache the ordinary way and this whole problem doesn't exist.
The Deck is where the pretty Glide path lives happily today — so the Mac isn't the place to chase
it until MoltenVK closes the gap.

## The Mac build going forward

**The software renderer via DxWnd is the Mac build** — it starts instantly, has zero shader
compile, gives a big screen-filling 4:3 window with correct colors (via the in-game brightness),
and is rock-solid. That's the right daily driver for a 20 fps 1997 game. Voodoo returns the day
MoltenVK can keep its compiled pipelines.
