# Porting the Windows-box wins back to the Mac/Wine stack — feasibility & recipes

*2026-07-10. After the Windows box got: a full-game HD texture pack, a tuned enhancement
recipe, frame-gen smoothing, FFB, and an aspect-ratio cheat — the question is how much of
that runs back under Wine on Apple Silicon. Short answer: **the single most valuable piece
(the HD textures) transfers for free and is already proven on Mac; the frame-cap/input/music
wins already work there; the frame-gen and the dgVoodoo supersampling are the Windows-only
advantages.** Companion to [DXGI-DGVOODOO-RESEARCH.md](DXGI-DGVOODOO-RESEARCH.md),
[HD-TEXTURES-RESEARCH.md](HD-TEXTURES-RESEARCH.md), [MAC-SETUP.md](MAC-SETUP.md).*

## Why the texture pack is the free lunch (the load-bearing insight)

The HD pack is not a renderer feature. It is **loose files dropped in `ADDON/`** that the I76
engine's virtual filesystem loads *before* the ZFS — the same override GOG itself ships
(`ADDON/i2ayj_13.map` etc.). That lookup happens in the game's own code, upstream of *any*
renderer or platform. It has **already been confirmed on the Mac Wine stack**
(HD-TEXTURES-RESEARCH.md: a magenta-marker dash pak in `ADDON/` visibly replaced the panel in
the running sim on macOS). So the exact same 3,322-file pack we built and verified on Windows
drops into the Mac wrapper's `ADDON/` and works — no re-render, no re-encode, no Wine-specific
build. The pack contains **both** texture formats, so it covers every Mac renderer:

| Mac renderer (how you launch) | Texture format it reads | Covered by our pack? |
|---|---|---|
| `-gdi` software (DxWnd daily driver) | VQM `*m.pak` + `.cbk` + loose `.map` | ✅ yes |
| `-glide` (OpenGLide, the shipping Glide path) | M16 `*6.pak` (hardware textures) | ✅ yes |
| `-glide` (dgVoodoo 2.78.2 hybrid, parked) | M16 `*6.pak` | ✅ yes |

And because `nitro.zfs` textures are byte-identical to `i76.zfs` (verified), the **same pack is
also the Nitro Pack's HD pack** on Mac.

## The full transfer matrix

| Windows win | Runs on Mac/Wine? | How / why |
|---|---|---|
| **HD texture pack (ADDON override)** | ✅ **Yes — proven** | File-based, engine-level. Copy the built pack into each wrapper's `ADDON/`. See `setup-mac-hd-textures.sh`. |
| **The 47/31/22 blend recipe** | ✅ Yes | It's baked into the texture pixels — nothing platform-specific. |
| **20 FPS physics cap** | ✅ Yes — already shipping | The GOG exe's own `I76PATCH.DLL` limiter runs under Wine (measured ~20.66 FPS in-sim). No external limiter needed. |
| **Mouse-steer / gamepad / arrow-key `input.map`** | ✅ Yes — already Mac-handled | `input.map` is engine-level; `setup-mouse-and-pad.sh` + `fix-arrows-for-mac.sh` already do this. (Same mouse-analog caveat as Windows: the game needs relative mouse motion — Wine delivers it in the virtual desktop.) |
| **In-mission music** | ✅ Yes — already Mac-handled | `setup-music.sh` (virtual CD audio). |
| **Multiplayer (ANet/UPnP)** | ✅ Yes | Bundled in the GOG/AiO exe; works wherever the network does. |
| **Aspect-ratio stretch (round the reticle / fill screen)** | 🟡 Partial, different tool | On Windows we stretch via dgVoodoo scaling. On Mac use **DxWnd** window sizing (software path) or the wrapper's virtual-desktop resolution. Same 4:3-hardcoded-camera ceiling applies. |
| **dgVoodoo "max graphics" (8× MSAA, 3× supersample, forced res)** | 🟠 Degraded | The shipping Mac Glide path is **OpenGLide**, which has none of these knobs. dgVoodoo-on-Wine *does* work (2.78.2 only) but adds a ~2-min uncacheable shader warmup per launch for **zero color gain** (the game sets 3dfx gamma itself), so it's parked. Net: Mac gets the bright 3dfx look but not the 8×MSAA/3× cleanliness. |
| **Frame-gen smoothing (LSFG 20→40/60)** | ❌ **No drop-in** | Lossless Scaling is a Windows Steam app hooking WGC/DXGI. macOS has **no equivalent windowed frame-generator** (MetalFX is spatial upscaling requiring app integration, not frame interpolation). Mac stays at a real 20 FPS. See "frontier" below. |
| **Force feedback** | ❌ No | Wine's only FFB backend is Linux evdev; there is no macOS FFB path. Windows-only. |
| **The dashboard tuner (`build_tuner.py`)** | ✅ Yes (it's a browser tool) | Runs anywhere; only used to *design* the recipe, which is already baked. |

## Recommended Mac play stack after this port

1. **Textures:** run `setup-mac-hd-textures.sh` (installs the pack into every I76 wrapper's
   `ADDON/`). Instant, renderer-agnostic, reversible.
2. **Renderer:** keep the shipping choice — **OpenGLide `-glide`** for bright 3dfx color with no
   warmup, or **`-gdi`/DxWnd** for the rock-solid software window. Both now render HD textures.
3. **Cap/input/music:** already handled by the existing scripts.
4. **Accept:** native 20 FPS (no frame-gen), no 8×MSAA, no FFB. These are the Windows box's
   exclusive perks and don't port.

## The one frontier worth naming: frame-gen on Mac

There is no off-the-shelf way to get the LSFG look on macOS today. The theoretically-portable
routes, none proven:
- A **RIFE/IFRNet real-time interpolator** as a Metal compositor over the game window (nothing
  packaged for arbitrary windows exists; would be a project).
- If the dgVoodoo→DXVK→Metal hybrid is ever un-parked (needs the cereal-MoltenVK + persistent
  `VkPipelineCache` fix in DXGI-DGVOODOO-RESEARCH item 0), its D3D11 output *could* in principle
  be captured — but there's still no Mac capture-frame-gen consumer.

For now the honest recommendation is: **play the Mac version at native 20 FPS with HD textures**
(which is already a big visual upgrade), and use the Windows box when you want the 40/60-fps-look
+ MSAA + FFB experience.

## How to apply on the Mac (quick start)

```sh
# 1. copy the built pack from the Windows box (it's portable — identical game files)
#    e.g. via Taildrop / scp: the folder C:\Games\_tools\i76-build-final  ->  ~/i76-hd-pack
# 2. install it into every I76 wrapper's ADDON:
games/interstate-76/setup-mac-hd-textures.sh ~/i76-hd-pack

# OR build it natively on the Mac from your own GOG files (same pipeline, cross-platform):
#   brew install lzo   (gives liblzo2 for zfs_extract.py — no LZO2_DLL needed on macOS)
#   python3 tools/zfs_extract.py "<game>/I76.ZFS" /tmp/i76-assets
#   python3 texture-lab/decode_all.py /tmp/i76-assets /tmp/i76-staging /tmp/i76-manifest.json
#   realesrgan-ncnn-vulkan (arm64) -i /tmp/i76-staging -o /tmp/i76-enhanced -n realesrgan-x4plus-anime
#   python3 texture-lab/reencode_all.py /tmp/i76-manifest.json /tmp/i76-enhanced /tmp/i76-assets /tmp/out /tmp/i76-staging
#   setup-mac-hd-textures.sh /tmp/out
```

The Python pipeline (`decode_all.py` / `reencode_all.py` / `tools/*.py`) is already
cross-platform (PIL + numpy + ctypes-loaded liblzo2); `zfs_extract.py` finds `liblzo2.dylib`
automatically on macOS (Homebrew) and takes `LZO2_DLL` on Windows.
