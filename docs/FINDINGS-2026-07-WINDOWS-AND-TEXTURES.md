# Interstate '76 on modern Windows + the first texture-replacement pipeline — findings & learnings (July 2026)

*A community-oriented report of everything we verified, cracked, and dead-ended on
while getting Interstate '76 (GOG Gold, 1997) running at its best on a Windows 11
laptop — culminating in what we believe is the **first working vehicle-texture
replacement pipeline** for the game, including a public spec for the previously
undocumented `.M16` hardware-texture format.*

*Everything below was tested first-hand on 2026-07-09 unless cited otherwise.
Test rig: Windows 11 Home, GTX 1650 Ti Max-Q + Iris Xe hybrid laptop, 3440x1440
external display. Game: GOG Gold `i76.exe` MD5 `60abf7bc699da72476128ddce991a3d1`
(byte-identical to UCyborg's AiO Unofficial Patch final build). Repo tooling
referenced throughout lives in [`../tools/`](../tools/) and
[`../texture-lab/`](../texture-lab/).*

---

## Contents

1. [Running the game well: dgVoodoo2 recipe (verified)](#1-running-the-game-well)
2. [Frame smoothing: first documented I76 + LSFG result](#2-frame-smoothing)
3. [Force feedback: the registry hack is not what the wiki says](#3-force-feedback)
4. [Asset archaeology: formats, and the M16 crack](#4-asset-archaeology)
5. [The texture-replacement pipeline (proven in-game)](#5-texture-replacement-pipeline)
6. [Prior art & the 2026 community landscape (linked)](#6-prior-art)
7. [Open problems — help wanted](#7-open-problems)
8. [Methodology notes (how we verified things)](#8-methodology)
9. [Full reference index](#9-references)

---

## 1. Running the game well

**TL;DR: dgVoodoo2 (2.87.3) in windowed mode, Glide renderer, 20 FPS cap, 3x
resolution, 8x MSAA — scripted end-to-end in
[`setup-windows.ps1`](../setup-windows.ps1) with the config in
[`dgVoodoo.windows.conf`](../dgVoodoo.windows.conf).**

Verified findings:

- **The 20 FPS cap is physics-load-bearing and non-negotiable.** The sim advances
  per rendered frame (1997 fixed-timestep assumption). The GOG 2019 exe already
  contains the AiO patch's hard-coded 20 FPS limiter (`I76PATCH.DLL`); we run
  dgVoodoo `FPSLimit = 20` as belt-and-braces. Above ~30 FPS: cars flip, Mission
  5's ramp jump becomes impossible, flamethrower/mortar/AI break
  ([Local Ditch FAQ](https://www.localditch.com/interstate-76/faq.html),
  [VOGONS AiO thread](https://www.vogons.org/viewtopic.php?t=68384)).
- **Voodoo Graphics / 2 MB / `MemorySizeOfTMU = 2048` / 1 TMU is load-bearing**,
  not nostalgia: more TMU memory causes post-explosion texture corruption
  ([VOGONS t=70951](https://www.vogons.org/viewtopic.php?t=70951)). Confirmed
  corruption-free across multiple sessions with these values.
- **Windowed beats fullscreen, decisively.** With `FullScreenMode = false` and a
  forced resolution, dgVoodoo sizes the game window to the forced res — we use
  `Resolution = 3x` (640x480 → 1920x1440, an exact integer fit for a 1440-high
  display; pick your own multiple). Verified pixel-correct 4:3 for menus and sim.
- **dgVoodoo true fullscreen is just worse here, not dangerous.** On a display
  with no 1920x1440 mode, dgVoodoo mode-switches to the nearest real mode
  (1920x1080 on our 3440x1440 panel = wrong aspect; the display may blank
  momentarily during the switch — an earlier draft of this report over-read
  that as a broken desktop topology; it wasn't, the monitor had simply turned
  off). For a fullscreen *look*, use Lossless Scaling's borderless overlay
  (§2) or dgVoodoo's `fullscreenAttributes = fake`; windowed remains the
  verified recommendation.
- **Wrap DirectDraw too.** The 2D shell (menus, cutscenes, "PLEASE STAND BY") is
  DirectDraw, not Glide. Dropping dgVoodoo's `DDraw.dll` + `D3DImm.dll` beside the
  exe gives menus the same 3x upscale. One gotcha: in windowed mode the DDraw
  surface fills the window ignoring `ScalingMode` — fix with
  `WindowedAttributes = fullscreensize` + `ScalingMode = centered_ar`.
- **dgVoodoo 2.87.x config note:** `WatermarkDisplayDuration = 0` now means
  *infinite*; the real switches are `3DfxWatermark = false` (Glide) and
  `dgVoodooWatermark = false` (DirectX).
- **In-mission music needs no tricks on Windows.** GOG's `goggame.dll` MCI shim +
  `music/*.mp3` just works (the elaborate virtual-CD plumbing in this repo is a
  Wine/Mac-only need).
- Boot is 60–75 s of "PLEASE STAND BY"; ESC (sometimes twice) skips. The boot
  phase runs as a borderless fullscreen-size popup that **minimizes on focus
  loss** — restore it and it settles into the proper titled window.
- **GOG Galaxy build warning (checked 2026-07-10):** a fresh Galaxy install of
  Interstate '76 delivers the **2017 exe** (`9a232dcc...`) — *not* the 2019
  AiO-merged exe (`60abf7bc...`) that offline-installer-era copies have. Assets
  (`I76.ZFS`) are byte-identical; only the exe lineage differs. Check your MD5;
  if you're on `9a232dcc`, apply
  [UCyborg's AiO patch](https://www.vogons.org/viewtopic.php?t=68384).
  (Also: `I76PATCH.DLL` was present in neither install here — with dgVoodoo the
  `FPSLimit = 20` conf line carries the cap, verified live by the LS `20/40`
  counter.) The Galaxy install's genuinely useful extras: `Manual.pdf` and
  GOG's official multi-res `goggame-*.ico`.
- **BREAKING (2026-07-21): Windows 11 update KB5101650 (26200.8875) kills the
  2019 AiO exe at boot** — access violation in `winmmbase.dll+0x5b13` a few
  seconds into PLEASE STAND BY, every launch. Bisect-verified NOT caused by
  dgVoodoo (any DLL), the ADDON pack, `i7_sfrce.dll`, `input.map`, the
  `goggame.dll` MCI shim, or compat flags — the same folder boots fine on the
  **2017 Galaxy exe** (`9a232dcc`), and `nitro.exe` (AiO lineage, no built-in
  limiter) also still boots, so the suspect is the 2019 exe's merged-in winmm
  timer FPS limiter meeting the updated `winmmbase`. Workaround until
  Microsoft or UCyborg reacts: run the 2017 exe and let dgVoodoo's
  `FPSLimit = 19.2` carry the physics cap (it always did the capping under
  this recipe anyway — but re-verify the canonical Mission 5 jump). Keep the
  2019 exe beside it (`i76.exe.aio-2019`) to restore later; multiplayer/AiO
  netcode fixes are what you lose meanwhile. Worth reporting on the
  [VOGONS AiO thread](https://www.vogons.org/viewtopic.php?t=68384).

### 1.1 The Nitro Pack runs with the identical recipe (verified 2026-07-10)

GOG ships the Nitro Pack as a **standalone game** (own `nitro.exe`, 68 MB
`nitro.zfs` + XOR-encrypted `nitro.zix`, own missions/music/FFB files, registry
key `ACTIVISION\Interstate '76 Nitro Pack` with `FTP=I76NITW95`). Same engine,
same renderer tokens (`glide`, `gdi`, `d3d`, `redline`, `powervr`). Deployment
transfers verbatim:

- Retire its bundled OpenGLide: `glide.dll`, `glide2x.dll`, `glide2x.ovl` only.
  **Do not touch `z*.dll`** (`zglide.dll`, `zredline.dll`, …) — those are the
  engine's renderer modules, not wrappers.
- Drop in dgVoodoo x86 `Glide*.dll` + `DDraw.dll`/`D3DImm.dll` + the same
  `dgVoodoo.conf` (the 20 FPS cap matters here too — no built-in limiter).
- Launch `nitro.exe -glide`. Verified: boots and renders the Nitro Riders
  intro through dgVoodoo, same boot-phase popup behavior as the base game.
- Its GOG `input.map` is **clean** (no phantom joystick5 — that packaging bug
  is base-game-only); mouse/pad additions apply the same way.
- Music note: the GOG Nitro build ships `audiere.dll` for playback (base game
  uses the `goggame.dll` MCI shim) — in-mission music unverified so far.

## 2. Frame smoothing

**TL;DR: Lossless Scaling 3.2.2 (LSFG 3.1, Fixed x2, WGC capture) interpolates
the 20 FPS sim to 40 FPS output — verified working with the on-screen counter
reading `20 / 40` in-mission. We believe this is the first documented I76 + LSFG
result.**

- Setup: dgVoodoo `ForceVerticalSync = false` (LS must own presentation), game
  windowed, then Ctrl+Alt+S with the game focused.
  [Lossless Scaling on Steam](https://store.steampowered.com/app/993090/) (~$7).
  Settings live in `%LOCALAPPDATA%\Lossless Scaling\Settings.xml` (edit only with
  the app closed): `FrameGeneration = LSFG3`, `LSFG3Mode1 = FIXED`,
  `LSFG3Multiplier = 2`, `CaptureApi = WGC`, `DrawFps = true`.
- The physics stay correct because the *sim* still renders 20 FPS; LSFG only
  synthesizes intermediate display frames. Input latency stays 20 FPS-ish — this
  smooths looks, not feel.
- LS's developer guidance assumes a ~30 FPS minimum base
  ([dev guidance](https://steamcommunity.com/app/993090/discussions/0/4418677017727367960/),
  [artifact thread](https://steamcommunity.com/app/993090/discussions/0/598521781543772576/));
  at a 20 FPS base some HUD ghosting on fast pans is expected. I76's slow flat
  desert is favorable content; x2 artifacts less than x3.
- Dead on this hardware, for the record: NVIDIA Smooth Motion (RTX 40/50 only —
  though dgVoodoo presents real D3D11, so a manual profile on a 40/50-series card
  is an *untested but plausible* experiment), AMD AFMF (Radeon only), SVP (video
  players only).

**Is there an open-source alternative we could bundle instead of a paid app?**
Surveyed 2026-07-10 — not yet, but the door is open:

- [Magpie](https://github.com/Blinue/Magpie) (the best OSS windowed-game overlay,
  great for upscaling) explicitly has **no frame generation** and no plans for it.
- AMD's FSR3 frame gen is open source but needs engine-supplied motion vectors
  and depth — a wrapped 1997 Glide game has neither; same reason
  [OptiScaler](https://github.com/cdozdil/OptiScaler)-style injection can't help here.
- [metantonio/free-lossless](https://github.com/metantonio/free-lossless) is an
  embryonic (2-star, no releases) but architecturally correct OSS attempt:
  screen capture → RIFE interpolation (DirectML) → transparent overlay. Proof
  the shape is buildable; not yet something to ship.
- Another OSS LS alternative was [announced on Reddit in 2026](https://en.gamegpu.com/news/zhelezo/otkrytaya-alternativa-lossless-scaling-skoro-poyavitsya-na-github)
  (scaling + frame gen) but has no public repo yet.
- The serious ingredients all exist as mature OSS:
  [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan) (Vulkan RIFE,
  runs on any GPU), Windows Graphics Capture, and DXGI overlay presentation.
  **I76 is actually the easy case for a bespoke tool**: a fixed 20 FPS base
  means trivial frame pacing — capture pairs, interpolate one midpoint, present
  at a rock-solid 40. No adaptive timing, no VRR headaches. A minimal
  "i76-smooth" (or general "fixed-rate retro smoother") is a realistic
  community project; the open question is whether RIFE at 1920x1440 fits the
  50 ms budget on low-end GPUs (reduced flow resolution likely needed). See
  Open problems.

## 3. Force feedback

**TL;DR: the famous registry fix is misdescribed for zip/portable installs, and
there's a 2024 report that the GOG build's FFB just works.**

- [PCGamingWiki](https://www.pcgamingwiki.com/wiki/Interstate_'76) describes
  copying `HKLM\...\ACTIVISION\Interstate'76FRC` → `Interstate '76` to wake the
  Gold Edition's dormant Nitro-Pack FFB code. **This presumes the GOG installer
  wrote those keys.** A portable/zip install has *no* ACTIVISION keys at all, so
  the `reg copy` fails even elevated — there is nothing to copy.
- **SOLVED (observed 2026-07-10, GOG Galaxy install):** GOG's installer writes
  the **un-suffixed key directly** —
  `HKLM\SOFTWARE\WOW6432Node\ACTIVISION\Interstate '76` containing just
  `EXE = i76.exe`. No `Interstate'76FRC` key exists at all on a GOG install.
  That's the whole mystery: the PCGW rename hack is CD-era; on GOG the key is
  pre-enabled, which is why FFB "just works" there. For zip installs, *create*
  the minimal key —
  [`enable-force-feedback.bat`](../enable-force-feedback.bat) now does this
  automatically when no FRC source exists. The key is machine-wide (HKLM), so
  one run covers every copy of the game on the box.
- **Third route (untested): the original Force Feedback Patch v1.083** is still
  hosted on [Local Ditch's downloads page](https://www.localditch.com/interstate-76/downloads/)
  — the era installer that added FRC support to retail installs. Running it (or
  extracting it) should produce the exact ACTIVISION registry keys/values the
  wiki hack presumes, solving the zip-install chicken-and-egg without access to
  a GOG-installed machine. (Our GOG 2019 exe is already v1.083-lineage via the
  AiO patch — only the key material is wanted, not its binaries.)
- Countervailing evidence the hack may be unnecessary on the GOG build: a March
  2024 report of FFB working out-of-the-box on a Logitech Driving Force GT
  ([VOGONS t=61199](https://www.vogons.org/viewtopic.php?t=61199)); see also the
  [GOG forum FFB thread](https://www.gog.com/forum/interstate_series/gog_interstate_76_and_force_feedback_joystick_no_force_feedback_working).
  The FFB machinery ships complete in the game folder (`i7_sfrce.dll`,
  `force/*.frc`).
- XInput pads: drive fine via winmm (`joystick1`), but **XInput rumble ≠
  DirectInput FFB** — no force feedback on an Xbox controller, ever. A
  DirectInput FFB wheel/stick must be plugged in **before** launch (the 1997
  engine enumerates joysticks once, at startup).
- Never rebind in the in-game Control Configuration menu (community-confirmed
  append/wrong-device/crash bugs) — edit `input.map` in a text editor;
  [`setup-windows.ps1`](../setup-windows.ps1) applies the known-good mouse+pad
  blocks automatically.

## 4. Asset archaeology

### 4.1 The archive layer

`I76.ZFS` ("ZFSF" v1, 55 MB, 6,116 files) — per-entry compression: 493 stored,
1,526 **LZO1X**, 4,097 **LZO1Y**. Full layout in
[`zfs_extract.py`](../tools/zfs_extract.py) (matches
[Open76](https://github.com/r1sc/Open76)'s reader and
[Roanish/i76's Ghidra-verified notes](https://github.com/Roanish/i76/blob/master/docs/REVERSING.md)).
Windows note: `python-lzo` wheels only expose LZO1X; point the tool's `LZO2_DLL`
env var at a real `liblzo2` (easiest clean source: the
[conda-forge `lzo` package](https://anaconda.org/conda-forge/lzo) ships
`Library/bin/lzo2.dll`). All 6,116 files extracted, zero failures.

### 4.2 The vehicle asset chain (decoded and verified)

```
<car>.vcf  — variant config: display name, VDF (geometry), VTF (paint), weapons
   └─ <car>.vtf  — paint scheme: 78 TMT names + 13 MAP names ("orange/black", …)
        └─ <car><scheme>t.pak/.pix — the TMTs: per-panel tables of texture
        │    basenames across 3 damage states (…1 pristine, …2 damaged, …3 wrecked)
        ├─ <car><scheme>m.pak/.pix — SOFTWARE-renderer pixels (VQM, level-palette)
        └─ <car><scheme>6.pak/.pix — HARDWARE-renderer pixels (M16) ← -glide loads THESE
```

Panel naming grammar (e.g. `pp11ftt1`): car code (`pp` Piranha, `js` Sovereign,
`al` Leprechaun…), damage state 1–3, panel (FT front / MD mid / BK back / TP top),
face (FT/BK/RT/LT/TP/UN), paint scheme digit. Typical panel sizes 128x64; tops
128x128; a few 64x64 / 64x32 / 32x16 bits.

Cars of interest: Groove/Jade's **Picard Piranha** = `vppirna1.vcf` ("Jade's
Car") → `piranha1.vtf` → `pirana1{t,m,6}`; Taurus's **1969 Jefferson Sovereign
"Eloise"** ([fandom](https://interstate76.fandom.com/wiki/Taurus)) =
`vjsovrn1.vcf` → `sovergn1.vtf` → `sovern1{t,m,6}`. The `vppt01–17.vcf` files are
the player's campaign Piranha per mission. Real-world car basis chart:
[Local Ditch](https://www.localditch.com/interstate-76/cars/).

**Gotcha that cost us a probe cycle:** the melee "variant" picker selects the
*paint scheme*, which selects the *pak set*. The default melee Leprechaun (GTAZ)
is scheme **3** (`leprcn3m/36`), not scheme 1. Match the scheme digit or your
override silently never loads.

### 4.3 The M16 format — cracked (new public spec)

The `.M16` entries in the `*6.pak` sets were undocumented; the only public note
([CahootsMalone's terrain-texture-info](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/terrain-texture-info.md))
covers the *terrain* variant and calls the trailing bytes "unknown significance."
For **vehicle** M16s we established, and verified with a lossless round-trip
encoder plus an in-game render test:

```
u32   width
u32   height | flags << 24        (flags 0x80 observed; meaning still open)
u8    indices[width*height]       (row-major, top-down; 0xFF = transparent)
u32   paletteCount                (max 255 — 0xFF is reserved)
u16   palette[paletteCount]       (RGB565, little-endian, PER-TILE local palette)
```

How it fell: the same art exists twice (VQM for software, M16 for hardware), so
the VQM decode is pixel-aligned ground truth. Candidate decodes were scored as
mean |ΔRGB|; the winner (palette at trailer offset **4**, RGB565) scored **7.75
per channel = exactly RGB565 quantization noise**, while every other hypothesis
(level `.ACT` palettes ×67, palette-offset byte, embedded 1555/4444/BGR/BE,
direct-16bpp pixels) scored 55–95. The "mystery 514 bytes" = `u32 count(255)` +
255×u16. Variable trailer sizes across tiles (514 / 230 / 6 bytes = 255 / 113 / 1
colors) confirmed count-prefixed palettes and killed the fixed-size mip theory.

Consequence worth stating loudly: **per-tile local palettes mean M16 replacements
have full 16-bit color freedom** — unlike VQM repaints, which must quantize to the
level's shared 256-color `.ACT`. The hardware path is the *better* modding target.

Decoder/encoder: `decode_m16` / `encode_m16` in
[`i76img.py`](../tools/i76img.py) (round-trip pixel-diff 0). The VQM/CBK/MAP/
PAK/PIX codecs live in the same file; full layouts in
[HD-TEXTURES-RESEARCH.md](HD-TEXTURES-RESEARCH.md).

## 5. Texture-replacement pipeline

**TL;DR: decode → Real-ESRGAN 4x → downsample to engine size → re-encode →
drop the rebuilt `pak/pix` pair into `ADDON/` → the running game renders it.
Proven with a magenta-marker probe; first enhanced packs built for the Piranha
and the Sovereign.**

- **Injection**: the engine's virtual filesystem checks loose files in `ADDON/`
  before `I76.ZFS` (GOG itself ships overrides there). No archive repacking, no
  binary patching, trivially reversible.
- **Which files**: in `-glide` (dgVoodoo or original 3dfx) the engine loads the
  M16 `*6.pak` sets — established in-game by installing distinct markers into
  both formats and observing which renders (the magenta X came through with G=0
  purity only the M16's local palette can carry; the VQM marker's forced
  level-palette quantization to (232,48,88) did not appear).
- **The ceiling**: texture *dimensions* are engine-fixed — same-size repaints
  only. "Enhanced", not "HD", today. The 4x-upscale → retouch → downsample
  workflow still visibly improves art: dithering noise gone, panel lines and
  chrome crisp, gradients smooth.
- **Upscaler notes**: [Real-ESRGAN ncnn Vulkan](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0)
  (portable Windows build, runs on anything with Vulkan). For this flat-shaded
  low-color art the `realesrgan-x4plus-anime` model clearly beats `x4plus`
  (cleaner edges, no mud). It slightly flattens subtle shading — a better
  model/workflow per tile class is an open item.
- **Scripts** (in [`../texture-lab/`](../texture-lab/)):
  [`enhance_cars_m16.py`](../texture-lab/enhance_cars_m16.py) (hardware sets),
  [`enhance_cars.py`](../texture-lab/enhance_cars.py) (software/VQM sets, used by
  the Mac port's DxWnd mode), [`make_marker.py`](../texture-lab/make_marker.py)
  (probe builder). Built and installed first: `pirana16` (38 tiles) and
  `sovern16` (29 tiles).
- **Distribution stance**: like the rest of this repo — recipes and tools only,
  no copyrighted art committed. A "pack" is an `ADDON/` folder your own tools
  rebuild from your own game files.

## 6. Prior art

Deep-searched 2026-07-09 (VOGONS, ModDB, GOG forums, Reddit, PCGW,
interstate76.com, GitHub). Detail below because evidence-of-absence is the claim.

### Texture packs / replacement
- **No I76 texture pack has ever been released.** Closest existing work:
  CahootsMalone replaced terrain textures with numbered checkerboards by
  hex-editing PAK contents
  ([terrain-texture-info](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/terrain-texture-info.md))
  — proof of in-archive feasibility, never a pack. DIVER's old "16-bit video mode
  texture patch" was a road-color *bugfix*, not an enhancement (referenced in the
  [AiO thread](https://www.vogons.org/viewtopic.php?t=68384)).
- **Glide-wrapper-level replacement is a dead end** (as of July 2026):
  [Glidos](https://www.glidos.net/retext.html) is the only wrapper with texture
  override (capture + re-inject, 256x256 max) but supports a fixed DOS-era title
  list — I76 (Win32 Glide) is not on it. dgVoodoo texture injection was requested
  and deemed feasible by Dege but never built
  ([VOGONS t=66553](https://www.vogons.org/viewtopic.php?t=66553); checked
  changelogs through [v2.87.3](https://github.com/dege-diosg/dgVoodoo2/releases)).
  nGlide: closed source, no such feature. OpenGLide forks (voyageur, fcbarros,
  RazorbladeByte, kjliew): none add replacement.
  [psVoodoo](https://psvoodoo.sourceforge.net/): no. Possible stacking hack:
  Special K's D3D11 texture injection on top of dgVoodoo's output — untested,
  undocumented for Glide sources.

### Engine reimplementations / reverse engineering
- [**Open76**](https://github.com/r1sc/Open76) (C#/Unity, GPL-3.0) — the richest
  parser set (ACT, BWD2, GDF, GEO, MSN, SDF, MAP/VQM/CBK, VCF, VDF, VTF, WDF,
  ZFS in `Assets/Scripts/System/Fileparsers/`); renders textured cars; dead
  upstream since 2020-04 ([OSGameClones: "Semi-Playable (Halted)"](https://osgameclones.com/interstate-76/)).
  Active fork: [rob518183/Open76](https://github.com/rob518183/Open76) (commits
  through 2026-06 — Unity upgrade, input, VR, audio, projectiles).
- [**Roanish/i76 "Vigilante '76"**](https://github.com/Roanish/i76) — active
  2026; from-scratch C rewrite of the Nitro Pack binary via Ghidra (SDL2+Vulkan).
  Working: ZFS (incl. XOR-encrypted `nitro.zix`), PCX, Smacker, GEO wireframe
  viewer, game-state machine. Its
  [REVERSING.md](https://github.com/Roanish/i76/blob/master/docs/REVERSING.md)
  documents the engine's `texture_load()`/`vqm_decode()`. README lists upscaled
  textures as an aspiration — **our M16 spec plugs a hole in their docs**.
- [CahootsMalone/interstate-76-stuff](https://github.com/CahootsMalone/interstate-76-stuff)
  — ZFS tools, VCF lists, `.def` format, terrain M16 notes (partial); last commit 2025-03.
- **That Tony** (hackingonspace.blogspot.com, 2016–17) — GEO/MAP/TER/BWD2/mission
  FSM groundwork. The blog is now behind a Blogger login; readable via
  [archive.is/Fnlzm](https://archive.is/Fnlzm).
- [Shane Peelar's RE survey](https://inbetweennames.net/blog/2021-05-04-interstate-76-reverse-engineering-efforts-the-story-so-far/)
  (2021) — the history: That Tony, UCyborg's patches, Hack '76, planned Vulkan renderer.
- Others: [jpcy/piranha76](https://github.com/jpcy/piranha76) (C++, dead 2019),
  [chasseyblue/i76-geo-importer](https://github.com/chasseyblue/i76-geo-importer)
  (Blender GEO importer, active Feb 2026),
  [greg-kennedy/i76render](https://github.com/greg-kennedy/i76render) (Perl→POV-Ray, archived).
- Community modding lore:
  [custom T.R.I.P. vehicles via vppt*.vcf renames](https://www.gog.com/forum/interstate_series/custom_vehicle_in_trip),
  [DIVER's car resources](http://www.interstate76.com/resources/diver/76car.html),
  [interstate76.com](https://interstate76.com/) (still updated 2026; hosts I'82
  skins, no I76 texture packs). Xentax wiki is gone; format-RE community
  successor: [ResHax](https://reshax.com/).

### Remakes, spiritual successors & fan projects
- [**Interstate Nitro**](https://www.moddb.com/mods/interstate-nitro) — Battlefield 2
  total-conversion mod; stated goal is a remake of I76 in a modern engine
  (multiplayer car combat; ModDB hosts builds + media).
- [**InterstateOutlaws**](https://github.com/ignitr0n/InterstateOutlaws) — GPL-3.0
  vehicular-combat game (Crystal Space + CEL + ODE; C++/Python) by a US/UK/AU
  student team, explicitly inspired by the classic auto-combat games; v0.2,
  deathmatch with 6 vehicles/2 maps, dormant.
- [**Interstate '76 Wiki** (Fandom)](https://interstate76.fandom.com/wiki/Interstate_%2776)
  — lore/vehicle/mission reference; the
  [Nitro Riders page](https://interstate76.fandom.com/wiki/Interstate_%2776:_Nitro_Riders)
  covers the Nitro Pack's 20-mission prequel campaign (Taurus/Jade/Skeeter sets +
  unlockable Natty Dread set, 14 new vehicles, Chemical Mortar/Caltrops).
- Box art: [I76 box cover (Fandom/wikia)](https://static.wikia.nocookie.net/interstate76/images/4/46/Interstate_%2776_Box_Cover.jpg/revision/latest)
  — local copy in `C:\Games\_tools\i76-assets\` (kept out of the repo: Activision
  artwork, don't redistribute; link it, don't commit it).

### Content audit: GOG "Arsenal" is TWO installs (2026-07-10)
The GOG purchase (Interstate '76 Arsenal) ships the base game and the **Nitro
Pack as a separate standalone install** (its own `NITRO.EXE`; the AiO patch
covers both exes). A file audit of a "Gold Edition" base install shows what's
actually inside: campaign trips `T01–T17`, melees `M01–M15` + `A01`, scenarios
`S01–S07`, Smacker cutscenes for the base trip only — **no Nitro campaign
files**. "Gold" here = the Nitro-era engine (incl. the dormant FFB code), not
the Nitro content. If you want the 20 prequel missions + 14 vehicles, install
the Nitro Pack from the GOG library alongside — same dgVoodoo recipe applies.

### The essential game references
- [PCGamingWiki: Interstate '76](https://www.pcgamingwiki.com/wiki/Interstate_'76)
- [UCyborg's AiO Unofficial Patch (VOGONS t=68384)](https://www.vogons.org/viewtopic.php?t=68384)
  — the GOG 2019 exe *is* this patch, `I76PATCH.DLL` 20 FPS limiter included
- [Local Ditch's I76 pages](https://www.localditch.com/interstate-76/) — FAQ
  (source of the frame-cap physics list), car chart, and a
  [downloads archive](https://www.localditch.com/interstate-76/downloads/) that
  preserves the era's files: v1.05/v1.06 patches, **Force Feedback Patch
  v1.083** (see §3), Arsenal XP fix, Gold Edition upgrade, AVA Car
  Designer/Hacker Tracker utilities, SMK player, printable level maps,
  wallpapers/key cards. Their [links page](https://www.localditch.com/interstate-76/links.html)
  indexes the living community: [SuiCyco's Speed Shop](https://z.interstate76.com)
  (mechanics/strategy deep dives), [King's Custom Rods](https://kingmercury.tripod.com/)
  (hacking/modding utility archive), the [AVA league](http://www.interstate76.com/the-ava/),
  and the GOG forum. Local Ditch also runs a deep
  [MechWarrior 2 hub](https://www.localditch.com/mechwarrior/mech2/index.html) —
  see [`games/mechwarrior-2/`](../../mechwarrior-2/) in this repo.
- [CahootsMalone's dgVoodoo walkthrough](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/running-interstate-76-gog-release-using-dgvoodoo.md)
  (mirrored on the [GOG forum](https://www.gog.com/forum/interstate_series/simple_stepbystep_instructions_for_running_interstate_76_with_hardware_acceleration_using_dgvood/page1))
- Multiplayer lives: community server **glenrio.interstate76.com**, weekly
  Tuesday sessions (AiO fixes the netcode/UPnP)
- [DxWnd forum: Interstate '76 Arsenal thread](https://sourceforge.net/p/dxwnd/discussion/general/thread/8af4850d/)
  — the DxWnd-route war stories: Smacker FMV vs. flip-emulation trade-offs,
  white-flicker HUD blocks, and a **Nitro-specific menu mouse Y-offset bug**
  after missions (independent corroboration of the internal-640x480 hit-test
  behavior we mapped in §8).
- [Paul the Tall: I76 Arsenal on Mac](https://www.paulthetall.com/interstate-76-arsenal-mac/)
  — the 2013-era Mac route (CrossOver/Porting Kit CrossTie). Prior art for this
  repo's free Sikarugir/Wine-10 port (see the repo README for the modern recipe).

## 7. Open problems

Ordered by leverage; contributions welcome.

1. **True HD (arbitrary-resolution) textures — IN PROGRESS: the OpenGLide-HD
   fork exists and builds (2026-07-10).** We forked
   [voyageur/openglide](https://github.com/voyageur/openglide) and added
   hash-based dump/replace: `hdtex\dump\` harvests every unique texture the
   game downloads as `<fnv1a64>.png`; a matching `hdtex\<hash>.png` uploads in
   place of the original **at any resolution** — one hook in
   `PGTexture::MakeReady`, stb for PNG I/O, ~300 lines, directory presence is
   the only config. Builds clean 32-bit with portable
   [w64devkit](https://github.com/skeeto/w64devkit/releases) x86 (GCC 16).
   Bring-up findings, all debugger/screenshot-verified:
   - **The 2 MB TMU bug bites wrappers too**: OpenGLide's default 16 MB
     `TextureMemorySize` crashes I76 at boot — set `2`, mirroring dgVoodoo's
     `MemorySizeOfTMU=2048` ([VOGONS t=70951](https://www.vogons.org/viewtopic.php?t=70951)).
   - **Root-caused the sim-entry crash** (disassembly at `i76.exe+0x75a01`):
     the game builds a 256-entry PC_NOCOLLAPSE palette and calls
     `IDirectDrawPalette::SetEntries` through a NULL global — modern Windows
     won't create 8-bit palettized DDraw primaries, so the palette never
     existed. **GOG's own bundled OpenGLide crashes identically** — bare
     `-glide` was likely never runnable on modern Windows.
   - Fixes: the Windows **256COLOR compat layer** on i76.exe restores real
     palettes. dgVoodoo's DDraw also provides palettes but **collides with
     OpenGLide's GL window at boot** (deterministic winmmbase fault) — never
     mix the two wrappers. [`swap-renderer.ps1`](../swap-renderer.ps1)
     automates the dgVoodoo ⇄ OpenGLide-HD switch including compat-flag and
     DDraw handling.
   - Status: boots and stays alive on the fork; the in-sim dump→upscale→replace
     loop is implemented, awaiting a human-driven melee run to verify (once
     dumps land, `realesrgan-ncnn-vulkan -i hdtex\dump -o hdtex -n
     realesrgan-x4plus-anime` IS the pack — folder mode keeps hash names).
   Alternatives still open: Dege's dgVoodoo plugin sketch
   ([VOGONS t=66553](https://www.vogons.org/viewtopic.php?t=66553)), Special K
   injection over dgVoodoo's D3D11 output.
2. **M16 `flags` byte (0x80)** — meaning unknown (mip presence? transparency
   hint?). Vehicle tiles observed single-level; CahootsMalone reports terrain
   PAKs carry mip chains — reconcile the two.
3. **Terrain/world M16s** — apply the cracked spec to `tp*6.pak` sets and confirm
   the same layout (his notes suggest a palette-offset byte variant there).
4. **Full-roster enhancement** — the pipeline is two commands per car; ~30
   vehicles × 3 schemes × 2 formats. Batch job + per-tile-class model selection
   (body panels vs. glass vs. decals want different upscalers).
5. **The melee form's model-cycler** ignores synthetic clicks (nine-point grid,
   both icons, the text field — all no-ops, while every other menu control works
   at raw-screen = internal-640x480 coordinates). *Workaround found the same
   night:* the melee default variant is itself defined by GOG's own
   `ADDON\valepre4.vcf` — overwrite that VCF with any car's (e.g. `vppirna1.vcf`
   = Jade's Piranha) and the melee form defaults to that car; no UI needed.
   [`test-drive.ps1`](../test-drive.ps1) automates boot → Instant Melee → chase
   cam → screenshot (~90 s) for visual regression. The synthetic-click mystery
   itself is still open. (Also verified: `i76.exe` has no command-line mission
   launch — everything routes through the shell.)
6. **Night variants** — `zdash*06`-style night art and the `*_16.act` palettes'
   exact role in 16-bit mode.
7. **Upstreaming** — offer the M16 spec + codecs to
   [Roanish/i76](https://github.com/Roanish/i76) (their REVERSING.md lacks M16)
   and the Open76 fork; both render vehicles and could consume enhanced art
   directly.
8. **An OSS frame smoother for fixed-rate retro games** — no shippable
   open-source Lossless Scaling equivalent exists (see §2), but I76's fixed
   20 FPS base makes it the easiest possible target: WGC capture → RIFE
   ([rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan)) midpoint →
   borderless overlay at 40. Benchmark RIFE-lite at 1920x1440 on low-end
   Vulkan GPUs; if the 50 ms budget holds, this kills the last paid dependency
   in the stack.

## 8. Methodology

Techniques that did the heavy lifting, for anyone extending this work:

- **Cross-encoding ground truth**: the same art shipping in two formats (VQM +
  M16) turns format-cracking into a scoring problem — decode candidates, measure
  mean |ΔRGB| against the known-good decode. 565-quantization noise (≈7.75/channel)
  is cleanly distinguishable from wrong-hypothesis noise (55–95).
- **Structure-vs-color separation**: a candidate decode that shows correct
  *shapes* with wrong *colors* proves the index geometry (8bpp, row-major, no
  flip) before the palette is solved — halves the search space.
- **Variable-size forensics**: trailer sizes 514/230/6 across tiles instantly
  falsified fixed-size theories (embedded 256-palette, fixed mip) and suggested
  count-prefixed data. Arithmetic beats staring at hex.
- **Chromatic probe fingerprinting**: give each candidate code path a marker
  color only *it* can represent (M16 local palette: pure (255,0,255); VQM after
  level-palette quantization: (232,48,88)). One screenshot then identifies the
  active path — no debugger, no tracing.
- **Lossless round-trip as encoder proof**: decode→encode→decode with pixel-diff
  0 (mind integer rounding: `(x*31+127)//255` to invert `c*255//31`).
- **Automated in-game verification**: the 2D shell hit-tests clicks at its
  internal 640x480 coordinates read as *raw screen pixels* offset from the
  window origin (it draws its own scaled cursor, which is why the visuals look
  right while the hotspots aren't where they appear). Menu path Main→MELEE
  (446,310) → AUTO MELEE (489,350) → INSTANT MELEE (529,378) → ENTER AREA
  (299,461); F2 = chase cam. Screenshot-after-every-input beats dead reckoning.

## 9. References

Every external source used across this report, one place:

**Community patches & wikis** ·
[UCyborg AiO patch (VOGONS t=68384)](https://www.vogons.org/viewtopic.php?t=68384) ·
[PCGamingWiki](https://www.pcgamingwiki.com/wiki/Interstate_'76) ·
[Local Ditch FAQ](https://www.localditch.com/interstate-76/faq.html) ·
[Local Ditch car chart](https://www.localditch.com/interstate-76/cars/) ·
[Taurus (fandom)](https://interstate76.fandom.com/wiki/Taurus) ·
[interstate76.com](https://interstate76.com/) ·
[OSGameClones](https://osgameclones.com/interstate-76/)

**Wrappers & rendering** ·
[dgVoodoo2 releases](https://github.com/dege-diosg/dgVoodoo2/releases) ·
[dgVoodoo ReadmeGeneral](https://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/) ·
[dgVoodoo texture-injection request (VOGONS t=66553)](https://www.vogons.org/viewtopic.php?t=66553) ·
[TMU corruption (VOGONS t=70951)](https://www.vogons.org/viewtopic.php?t=70951) ·
[Glidos texture override](https://www.glidos.net/retext.html) ·
[psVoodoo](https://psvoodoo.sourceforge.net/) ·
[CahootsMalone dgVoodoo guide](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/running-interstate-76-gog-release-using-dgvoodoo.md)

**Reverse engineering & tools** ·
[Open76](https://github.com/r1sc/Open76) ·
[rob518183/Open76 fork](https://github.com/rob518183/Open76) ·
[Roanish/i76 + REVERSING.md](https://github.com/Roanish/i76) ·
[CahootsMalone/interstate-76-stuff](https://github.com/CahootsMalone/interstate-76-stuff) ·
[terrain M16 notes](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/terrain-texture-info.md) ·
[That Tony (archived)](https://archive.is/Fnlzm) ·
[Shane Peelar's RE survey](https://inbetweennames.net/blog/2021-05-04-interstate-76-reverse-engineering-efforts-the-story-so-far/) ·
[jpcy/piranha76](https://github.com/jpcy/piranha76) ·
[chasseyblue/i76-geo-importer](https://github.com/chasseyblue/i76-geo-importer) ·
[greg-kennedy/i76render](https://github.com/greg-kennedy/i76render) ·
[ResHax](https://reshax.com/) ·
[Game Extractor](https://www.watto.org/game_extractor.html)

**Frame generation & upscaling** ·
[Lossless Scaling](https://store.steampowered.com/app/993090/) ·
[LS base-fps guidance](https://steamcommunity.com/app/993090/discussions/0/4418677017727367960/) ·
[LS artifact thread](https://steamcommunity.com/app/993090/discussions/0/598521781543772576/) ·
[Real-ESRGAN ncnn Vulkan v0.2.5.0](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0)

**Input & FFB** ·
[FFB on DFGT (VOGONS t=61199)](https://www.vogons.org/viewtopic.php?t=61199) ·
[GOG forum FFB thread](https://www.gog.com/forum/interstate_series/gog_interstate_76_and_force_feedback_joystick_no_force_feedback_working) ·
[GOG forum gamepad thread](https://www.gog.com/forum/interstate_series/is_1_76_compatible_with_a_gamepad) ·
[custom TRIP vehicles](https://www.gog.com/forum/interstate_series/custom_vehicle_in_trip) ·
[DIVER's car resources](http://www.interstate76.com/resources/diver/76car.html)

**Windows toolchain** ·
[conda-forge lzo](https://anaconda.org/conda-forge/lzo) ·
[python-lzo](https://pypi.org/project/python-lzo/)

---

*Corrections and additions welcome — file an issue or PR on
[mac-gaming-ports](https://github.com/therealjkvalentine/mac-gaming-ports). If
you extend the M16 spec (flags byte, terrain variant, mips) please cite this
document so the next person can follow the chain.*
