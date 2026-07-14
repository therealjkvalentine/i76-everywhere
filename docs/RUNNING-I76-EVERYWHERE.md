# Running Interstate '76 everywhere — a cited compendium

*Deep-research synthesis, 2026-07-05. 103 research agents, 21 sources fetched, 104 claims
extracted, 25 adversarially verified (24 confirmed, 1 refuted). Confidence tags and citations are
per-method. This is the "what has everyone tried" reference so we don't reinvent or miss anything —
the macOS/Wine port specifics live in [../README.md](../README.md) and
[DXGI-DGVOODOO-RESEARCH.md](DXGI-DGVOODOO-RESEARCH.md).*

## The one-paragraph state of the art

Every working modern setup combines **two orthogonal fixes**: a **frame cap** (the game's
physics, AI, and even weapon audio are tied to render framerate and break above ~20-30 FPS) and a
**display wrapper** (the GOG exe exposes renderers only via hidden command-line switches, with no
in-game resolution UI). For **filling a modern screen**, the verified ceiling is sobering: you can
force high resolutions via dgVoodoo2 (Glide) or scale the window via DxWnd, but **only 4:3 renders
correctly** — the camera transforms hardcode 4:3, so 16:9 is horizontally stretched, and **no
widescreen/FOV patch exists anywhere** (WSGF rates widescreen/ultrawide/4K all unsupported). So
"fill the screen" realistically means *a big 4:3 window or pillarboxed 4:3 fullscreen*, which is
exactly what our DxWnd setup now delivers.

## Frame cap (required on every platform)

The game is framerate-coupled by design — above ~30 FPS (24 in some cases): stuttering, physics
and AI breakage, and the 7.62mm MG firing sound cuts out. **20 FPS is the community sweet spot**
(UCyborg picked 20 specifically to keep the MG audio intact; 24-25 also documented). *[high
confidence, 3-0]* Capping options, any one suffices:

| Method | Detail | Cite |
|---|---|---|
| **GOG exe's built-in limiter** | The GOG `i76.exe` **already contains** UCyborg's AiO limiter, hardcoded to 20 FPS. On every platform you already have the cap. | our own MD5 finding + [1] |
| i76fix (immi101) | Binary patch, **GOG exes only** (i76.exe MD5 `9a232dcc…`, nitro.exe `28b8ae27…`; not CD builds). Caps 25 FPS + disables the privileged CPU-measurement code. No display features at all. | [2] |
| Nitro Patch IV | 24 FPS limiter (forums.interstate76.com t=1442). | [3] |
| dgVoodoo2 `FPSLimit` | Config key; belt-and-braces when using the Glide wrapper. | [4] |
| RTSS / NVIDIA-panel cap | External frame limiter (turn OSD off — overlays crash I76 at mission end). | [3] |

Sources: [1] Peelar RE write-up; [3] PCGamingWiki; [2] immi101/i76fix.

## The GOG exe's hidden renderer switches

No launcher, no resolution menu — you pick a renderer with a command-line flag. *[high, 3-0]*

| Switch | Renderer | Notes |
|---|---|---|
| `-gdi` | Windowed **software** blit | Hidden; "may be broken on modern Windows" unpatched — **the AiO patch fixes exactly this** (below). Our Mac default. |
| `-glide` | 3Dfx Glide | Needs a Glide wrapper (OpenGLide ships with GOG; or dgVoodoo2). |
| `-d3d` | Direct3D 5 | Confirmed via dgVoodoo2 interface tracing. |
| `-redline` / PowerSGL | Rendition Vérité / PowerVR | Gold version only; dead hardware, wrapper-only today. |

The **original 1997 retail** launcher had a splash screen (Normal / Window / 3DFX / Direct3D) —
the GOG build dropped it, leaving only the switches. *[supporting]* Cites: PCGW; CahootsMalone
dgVoodoo guide [4]; GOG forum "windowed mode" thread.

## Filling the screen — the actual open problem

**The hard ceiling: 4:3 only.** dgVoodoo2 can force arbitrary resolutions in Glide/D3D, but the
game's camera is hardcoded 4:3 → 16:9 output is horizontally stretched; the only distortion-free
choices are **high 4:3 resolutions** or a wrapper's **keep-aspect (pillarboxed) scaling**. No
Hor+/FOV/widescreen hack exists — verifiers searched specifically and found none; WSGF confirms
widescreen/ultrawide/4K unsupported. *[high, 3-0]* Cites: PCGW, CahootsMalone [4], WSGF.

**DxWnd — the method we're using, and it's the documented answer for scaling.** *[high, 3-0]*
DxWnd (the author ships an "Interstate 76" profile) scales the 640×480 window or does
borderless-fullscreen. Two gotchas the community nailed down, both directly relevant to us:

- **Mouse offset when scaled up:** at native 640×480 the mouse is fine, but enlarging the window
  throws clicks "several hundred pixels away" — menus become unclickable. **Fix: Hook tab →
  enable "Inject suspended process"** (DxWnd's default `SetWindowsHook` mode is the culprit;
  forum regular BEEN_Nath_58 confirms it's a resolution-related cursor-placement bug). This is
  the single most important DxWnd setting for us. *Source: DxWnd SourceForge thread 811689bdf3
  (Zeether, 2022-02-05).*
- **"Primary buffer" renderer trick — use with caution:** on modern Windows, `-glide` can black
  out menus/cutscenes; the AiO readme suggests DxWnd with **"primary buffer" selected on the
  DirectX tab** to fix it. **BUT** the DxWnd author (gho) calls primary-buffer "probably the most
  untested DxWnd option" — it **leaks GDI handles (~4× faster)**, so menu→gameplay transitions
  get **progressively slower the longer you play**. Prefer leaving it off unless you hit black
  menus; our `-gdi`-through-DxWnd path doesn't need it. *Sources: AiO patch page [1]; DxWnd thread
  4d9d7bc900 (UCyborg + gho, DxWnd 2.05.24).*

> **For our Mac setup:** DxWnd scaling `-gdi` (or `-glide`) to a big 4:3 window works and is the
> intended use. Set **Inject suspended process** in the profile's Hook tab if the mouse drifts.
> Skip primary-buffer unless menus go black. Accept 4:3 (pillarbox to fill height) — widescreen
> is impossible in this engine.

**AiO patch's native `-gdi` repair:** UCyborg's patch makes the game's own GDI windowed software
renderer work on NT-family Windows for the first time (worked on Win9x, never on NT; even runs on
NT 4.0). This is why our `-gdi` path works at all — the GOG exe *is* the patched build. *[high,
3-0]* Cites: AiO patch page [1], VOGONS t=68384, Peelar [5].

## Platform recipes

**Windows (canonical):** AiO patch (already in GOG exe) for the cap + native windowed; add
dgVoodoo2 2.79.3 for hardware Glide (delete GOG's OpenGLide `glide*.dll`/`OpenGLid.INI`, drop in
dgVoodoo's x86 `Glide*.dll` + `D3D8/9/Imm`/`DDraw.dll`, run `i76.exe -glide`, set `FPSLimit=20`).
Caveats: mouse dead on pause menu, aspect stretching if non-4:3. *[high, 3-0]* Cite: CahootsMalone
[4], PCGW.

**Linux (W4DXR guide):** Lutris GOG install, point the runner directly at `i76.exe` (**not** the
GOG launcher), Wine prefix = Windows XP, restrict to 1 CPU core, runner `lutris-GE-Proton7-25`.
Apply the two-byte patch that skips the privileged CPU-speed routine that crashes Wine:
`printf '\xEB\x22' | dd of=i76.exe bs=1 seek=626025 count=2 conv=notrunc` (nitro.exe: `seek=630921`).
Origin: Anastasius Focht on WineHQ (bug 21924); `jz`→`jmp` at `0x98D69`. **This is the same routine
i76fix and the AiO patch neutralize — so our GOG (AiO) exe needs no such patch, which is why it
boots clean under Wine on macOS.** *[medium — W4DXR origin server down, quotes from index captures;
its claimed Xephyr-fullscreen approach was **refuted 0-3**, so treat its display/fullscreen details
as unconfirmed]* Cites: w4dxr.us/page.php?id=42, GOG Linux thread, WineHQ.

**macOS:** **No prior art survived verification** — no CrossOver/Wineskin/PortingKit writeups, no
macOS OpenGLide notes. Our repo appears to be the first documented macOS route. (This is a gap, not
a proof of absence.)

## Multiplayer over modern networks

Shane Peelar's netcode patches (built on Dan Kegel's released ANet source) restore internet play,
which otherwise breaks under NAT (the game embeds invalid IP assumptions). Base game: drop-in
`WINET.DLL` in the `DLL` folder (6-byte IP representation; host forwards **port 21157**). Nitro:
`winets2_v3.zip` replaces `anet2.dll` + `winets2.dll` and adds **automatic UPnP port forwarding**
via miniupnpc (no manual forwarding if the router supports UPnP). *[high, 3-0]* **All of this is
already bundled in the GOG/AiO exe** per our earlier file analysis. Cites: inbetweennames.net
project page [6], forums.interstate76.com t=1508, AiO page [1].

## Reimplementation & emulation

- **Open76 (r1sc):** from-scratch Unity/C# engine reading original ZFS assets. Renders ~all level
  content + vehicles, parses mission stack-machines — but **core sim incomplete** (no
  engine/gearbox, many mission actions unimplemented); OSGC = semi-playable, **development halted**.
  A native engine would trivially solve resolution/scaling, but it is not a playable replacement
  today. *[high, 3-0]* Cite: github.com/r1sc/Open76, osgameclones.
- **Era-accurate emulation (86Box/PCem/QEMU Voodoo):** **no results survived verification.** The
  Glide backend targets 2MB-tmem Voodoo Graphics and corrupts textures on larger cards, so a
  wrapper/emulator must emulate the original 2MB card — but concrete playable-speed emulation
  results remain unconfirmed. *Open frontier.*

## Coverage gaps (unverified, NOT disproven)

- Any way to run the native `-gdi` window *fullscreen/scaled without DxWnd* (Magnifier tricks, AiO
  window handling) — the exact thing we solved with DxWnd; nothing else documented.
- macOS prior art of any kind.
- Era-accurate emulation playable-speed results (UCyborg's VOGONS emulation posts).
- nGlide-specific I76 configuration.
- The specific DxWnd `v2.05.36.I76` build's provenance thread and what its shipped `.dxw`
  configures beyond what we've read from the profile itself.

## Sources

[1] PCGW Community file #1349 (AiO patch) · [2] github.com/immi101/i76fix ·
[3] pcgamingwiki.com/wiki/Interstate_'76 · [4] CahootsMalone/interstate-76-stuff dgVoodoo guide ·
[5] inbetweennames.net RE write-up (Shane Peelar) · [6] inbetweennames.net/projects/interstate76anet ·
DxWnd SourceForge threads 811689bdf3 / 4d9d7bc900 · VOGONS t=68384 · forums.interstate76.com
t=1508 / t=1442 · github.com/r1sc/Open76 · wsgf.org/dr/interstate-76 · w4dxr.us/page.php?id=42.
