# Porting the Windows-box wins back to the Mac/Wine stack — feasibility & recipes

*Superseded 2026-10-03 on one point: the "mouse-steer `input.map`" row. Mouse steering is no longer offered
on Windows, whose installer now writes `controls/input.map`; the Mac map is unchanged and not yet converged
(docs/CONTROLS.md, "Mac: converge later").*

*2026-07-10. After the Windows box got: a full-game HD texture pack, a tuned enhancement
recipe, frame-gen smoothing, FFB, and an aspect-ratio cheat — the question is how much of
that runs back under Wine on Apple Silicon. Short answer: **the single most valuable piece
(the HD textures) transfers for free and is already proven on Mac; the frame-cap/input/music
wins already work there; the frame-gen and the dgVoodoo supersampling are the Windows-only
advantages.** Companion to [DXGI-DGVOODOO-RESEARCH.md](../DXGI-DGVOODOO-RESEARCH.md),
[HD-TEXTURES-RESEARCH.md](../HD-TEXTURES-RESEARCH.md), [MAC-SETUP.md](MAC-SETUP.md).*

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

*(Note 2026-10-03: `setup-mac-hd-textures.sh` below is not in this repo, and `games/interstate-76/` is the path
this folder had inside mac-gaming-ports. The HD texture pack was retired on 2026-07-27:
[HD-TEXTURES-RESEARCH.md](../HD-TEXTURES-RESEARCH.md), `texture-lab/README.md`. Kept as the 2026-07-10 record.)*

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

## 2026-10-03 evening: the proxy switches on the Mac, measured

**The music-fix proxy (`music-fix/Strlkup.dll`, build of `fc3541a`) works under Wine 10 on the Mac
`i76.exe`** (GOG AiO `60abf7bc` + a one-byte PE-header stack patch). Every switch logged full site
counts in `mciproxy.log` in both renderers: far clip 6/6, aspect 20/20, HUD squeeze 2/2, framerate
fixes 36/36, render interp 11/11, terrain/object/clutter/mirror distances, fps cap, and the music
IAT hook. The proxy's own CD emulation played `music\9.mp3` through mpegvideo/GStreamer.

**dgVoodoo -> DXVK -> MoltenVK -> Metal (the parked Voodoo path): renders, but at 0.4-0.5 fps.**
Test wrapper `Interstate 76 - HiRes120 TEST.app` ([`i76-hires120-stub.swift`](../../i76-hires120-stub.swift)).
Correct picture (cockpit, Hor+ widescreen, round reticle) on the DXVK HUD at 0.4 fps with one core
pinned. **Not the proxy:** the same 0.4 fps with every `I76_*` switch off (music only), and with
`I76_GLIDE_REFRESH` / `I76_FPS_CAP` off. At the full 3456x2234 (Wine `RetinaMode=y`, screen-sized
virtual desktop, dgVoodoo `Resolution = h:3456, v:2234`) it also crashed within a minute on a Metal
assertion, `MTLTextureDescriptor has width of zero`, after a good 3456x2234 swapchain. Cause of the
0.4 fps not found; the owner's call: stay on the CPU path.

**Software renderer via DxWnd + the proxy: runs.** Test wrapper `Interstate 76 - CPU120 TEST.app`
(an APFS clone of the daily one): proxy installed, `I76PATCH.DLL` renamed, switches in the prefix's
`HKCU\Environment` (best-wide minus the Glide-only keys, `I76_ASPECT=1600x1000` = the DxWnd window's
`sizx0:sizy0`, `I76_FPS_CAP=120`), DxWnd `maxfps0` 52 -> 120 and its virtual CD off (`flagm0` bit 0)
so the proxy owns the music. The attract demo draws widescreen at the window's shape with terrain to
the horizon; game process 17-60 % of a core. Not yet measured: the frame rate, music in a mission,
the HUD squeeze on the software path, a played mission.

Software resolution ceiling: 1024x768, set in-game (Options -> Graphic Detail -> Screen Resolution;
[VERIFIED-FIXES.md](../VERIFIED-FIXES.md)). Anything above it is engine RE, not a setting.

### Later the same night: measuring the CPU path

- The frame hook (`0x4039b8`) does **not** run at the main menu or in the attract demo on the
  software path, although the game state `0x4c2164` reads 5 ("running") there. `I76_FPS_LOG` now has
  a watcher thread that says so (`fps: no mission frames; game state 5, proxy frame 0; hook site e8
  ..`), and it showed the patched call intact. So nothing undoes the hook; the menu's 3D is drawn
  through some other loop.
- `I76_MISSION=t01` does not reach the mission loop under DxWnd/software: state 5, zero hooked frames
  for 90 s, DxWnd virtual CD on or off, and also with `I76_SKIP_MOVIES=1` (movie names invalidated
  2/2). The watcher's stack samples put the main thread in a Wine wait called from `dxwnd.dll`
  (DDraw -> wined3d) at ~30 % of a core with DxWnd `maxfps0` set, and in `dxwnd.dll -> win32u` at
  ~114 % with `maxfps0=0`. Not the movie and not the net join wait (`0x452f20` =
  net_JoinHandshakeStep, re/ map): the software device's graphics init through DxWnd is the
  remaining candidate. On Windows the direct boot was only ever run with `-glide`.
- So the frame rate in a real mission is still unmeasured. The test wrapper now runs the lean set
  (the 120 fps switches only, `I76_FPS_LOG=5`) for a played mission; `mciproxy.log` will hold the
  numbers, or the watcher line if the hook does not run in missions either.
- A Wine command started from an agent's sandboxed shell (`wine cmd /c echo`) never reaches the
  wrapper's running session and prints nothing. `open`-launching the app works. Instrument from inside
  the game (the proxy log), not with side tools run from the shell.
- The test prefix's `users/<name>/Documents` etc. were symlinks into the real home folder. A clone with
  a new bundle id makes macOS ask for Documents access, and a pending privacy prompt blocks the
  caller. They are plain folders in the test prefix now.
