# Third-party components, game content & attribution

This repository ships **no copyrighted game files** and **no third-party binaries**
(see [`.gitignore`](.gitignore)). It is scripts, source, configuration, and
documentation, plus three prebuilt binaries **of this project's own code**, each
committed beside its source and build script: `music-fix/Strlkup.dll` (forwards by
name to GOG's renamed `strlkup_orig.dll`), `u32x/u32x.dll` (forwards by name to
`user32`; md5 and provenance in [`u32x/README.md`](u32x/README.md)) and
`tools/i76wheel.exe`. None contains game bytes. Everything original here is
[MIT-licensed](LICENSE). This file records what the project *builds on* but does
not own or redistribute.

## The game itself — you bring your own

**Interstate '76** and all its assets (executables, `*.ZFS`, textures, audio, FMV,
missions) are **© 1997 Activision** (rights now with Microsoft). This project does
**not** include, host, or distribute any of it. You must own a legitimate copy —
the [GOG "Interstate '76 Arsenal / Gold" release](https://www.gog.com/game/interstate_76)
is the tested source. Downloaded game material lives only in a local, gitignored
`game-data/` folder on your own machine.

## Third-party tools (configured/referenced, never bundled)

Each keeps its own license; this repo only provides configuration and install
scripts that fetch them from their official sources at install time.

| Tool | Role here | Source / license |
|---|---|---|
| **dgVoodoo2** (Dege) | Glide→D3D11 wrapper (Deck/Windows pretty path) | Freeware, dgVoodoo license — [dege.freeweb.hu](http://dege.freeweb.hu/). **Not redistributed by this repo**: `setup-windows.ps1` copies it from a folder you downloaded (`-DgVoodooDir`), and `deck/deck-install.sh` fetches 2.78.2 at install time from a public archive.org mirror (`archive.org/download/dgvoodoo2_78_2_202205`). Whether Dege's licence permits redistribution has **not** been checked against the licence text, so no such claim is made here; read the readme in the dgVoodoo archive before bundling it anywhere |
| **DxWnd** (gho) | Windowing/scaling + virtual-CD music (Mac software path) | GPL — [sourceforge.net/projects/dxwnd](https://sourceforge.net/projects/dxwnd/) |
| **OpenGLide** | Glide→OpenGL wrapper (GOG-bundled) | LGPL |
| **DXVK** (doitsujin) | D3D→Vulkan (Deck/Android/Wine) | zlib/libpng — [github.com/doitsujin/dxvk](https://github.com/doitsujin/dxvk) |
| **Box64/Box86** (ptitSeb) | x86→ARM64 (Android/Winlator) | MIT — [github.com/ptitSeb/box64](https://github.com/ptitSeb/box64) |
| **Wine / Proton / Sikarugir / Winlator** | Windows compatibility layer per platform | LGPL and respective licenses |
| **UCyborg "AiO" patch** | 20 FPS physics limiter (already inside the GOG 2019 exe) | See the AiO patch readme |
| **innoextract** | Extracts the GOG installer (Deck script) | zlib — [constexpr.org/innoextract](https://constexpr.org/innoextract/) |
| **AutoHotkey 1.1** (staged, input remapper WIP) | In-container input remapping | GPL — [autohotkey.com](https://www.autohotkey.com/) |
| **Lossless Scaling** (THS) | Optional frame generation on Windows (`Setup-FrameGen.ps1`, `PLAY-i76.ps1 -LosslessScaling`) | **Commercial** (Steam). Never fetched or shipped by this repo. `Make-Portable-Zip.ps1 -IncludeFrameGen` copies *your* installed copy into *your* zip: your licence, your PCs only |
| **opentrack** | Optional head tracking (`i76-opentrack-*.ahk`, [docs/HEAD-TRACKING.md](docs/HEAD-TRACKING.md)) | ISC, with GPL-licensed components — [github.com/opentrack/opentrack](https://github.com/opentrack/opentrack). Not shipped; `Make-Portable-Zip.ps1 -IncludeHeadTrack` copies your installed copy into your own zip |
| **GE-Proton** (GloriousEggroll) | Proton build the Deck scripts select | Proton's licences (BSD-style / LGPL components) — [github.com/GloriousEggroll/proton-ge-custom](https://github.com/GloriousEggroll/proton-ge-custom). Fetched on the Deck, not shipped |
| **Steam ROM Manager** | The controller-config apply mechanism `deck/add-to-steam.py` imitates (its configset approach); no code of it is used | GPL — [github.com/SteamGridDB/steam-rom-manager](https://github.com/SteamGridDB/steam-rom-manager). Referenced, not shipped |
| **input-remapper** | Referenced by the Deck control-tier scripts and docs (`deck/setup-deck-baseline.sh`, [docs/INPUT-REMAPPER.md](docs/INPUT-REMAPPER.md)) | GPL — [github.com/sezanzeb/input-remapper](https://github.com/sezanzeb/input-remapper). Installed on the Deck by the user, not shipped |
| **ViGEm / vJoy** | Mentioned only as things that can break FFB device acquisition ([docs/FFB-LAPTOP-RECON.md](docs/FFB-LAPTOP-RECON.md)) | Not used, not shipped |
| **w64devkit** (skeeto) | Optional 32-bit gcc for `music-fix/build.ps1` | Unlicense / GPL toolchain components — [github.com/skeeto/w64devkit](https://github.com/skeeto/w64devkit). A build tool; nothing of it is in the output |
| **Microsoft Visual C++ Build Tools 2019 (x86)** | What actually builds `Strlkup.dll` and `u32x.dll` (statically linked CRT, `/MT` for the proxy) | Microsoft licence; a build tool, not shipped |
| **RAD Smacker** (`SMACKW32.DLL`) | Game-shipped FMV library. `smack-music-fix/` builds a proxy that forwards to the game's own copy (renamed `smackorg.dll`) | © RAD Game Tools; part of the game install, never in this repo. Our proxy DLL is gitignored and built locally |
| **Cheat Engine** | Recommended for pointer scans ([AGENTS.md](AGENTS.md)) | Its own licence — [cheatengine.org](https://www.cheatengine.org/). Referenced, not shipped |

### Reverse-engineering tools (research only; nothing of them is shipped)

| Tool | Role here | Source / license |
|---|---|---|
| **Ghidra** (NSA) | Static analysis behind the memory maps in `docs/` and the sibling `i76-map` repo | Apache-2.0 — [ghidra-sre.org](https://ghidra-sre.org/). Decompiler output is Activision's code in another form and is **never** committed here |
| **capstone**, **pefile**, **Unicorn**, **Frida** | Disassembly, PE parsing, emulation and live instrumentation in the Python instruments (`tools/exe-disasm.py`, `tools/exe-xref.py`, the `i76-map` tools) | BSD / MIT / GPLv2 / wxWindows Library Licence respectively. `pip`-installed locally |
| **immi101's i76fix**, **bolrog's D2DX** | Prior art read for the frame-loop hook and render-interpolation design ([docs/FRAMERATE-UNCAP-RESEARCH.md](docs/FRAMERATE-UNCAP-RESEARCH.md)). No code of either is included | Their own licences; kept only in the lab's gitignored `refs/` |
| **Visual C++ 5.0 media** | Held locally for toolchain fingerprinting of the 1997 exe (sibling `i76-map`) | Microsoft; **never distributed**, not in any of the repos |

## Data & research credits

- **Weapon DPS / range figures** in the save editor: measured by **Local Ditch Gaming**
  (Greg Schwartz / "Zaphod-AVA") — [localditch.com](https://www.localditch.com/interstate-76/weapons.html).
  Used as reference data with credit; spec fallbacks come from the game's own `.gdf` files.
- **File-format groundwork**: **"That Tony"** reversed many I76 formats (2016–17), the
  foundation later reimplementations and this repo's save/texture work build on.
- **Reimplementation projects** referenced (not included): **Open76** (Unity) and
  **Roanish/i76 "Vigalante '76"** — see [docs/MODERN-PORTS-AND-VR.md](docs/MODERN-PORTS-AND-VR.md).
- **CahootsMalone's `interstate-76-stuff`** guide and tools, and the other community sources indexed by
  problem in [docs/COMMUNITY-RESOURCES.md](docs/COMMUNITY-RESOURCES.md). Linked, not copied.

## What the portable zip is

`Make-Portable-Zip.ps1` packs **your own configured install** — game files, the dgVoodoo DLLs you
downloaded, optionally your Lossless Scaling and opentrack — for moving between computers you own. It
is not a distribution format and must not be shared; the script's header and INSTALL.md say the same.

## If you represent a rights holder

Nothing here contains your game content — only interoperability tooling and
documentation created independently. If anything looks otherwise, open an issue
and it will be addressed promptly.
