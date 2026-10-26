# Third-party components, game content & attribution

This repository ships **no copyrighted game files** and **no third-party binaries**
(see [`.gitignore`](.gitignore)). It is scripts, source, configuration, and
documentation, plus a few prebuilt binaries **of this project's own code**, each
committed beside its source and build script: `music-fix/Strlkup.dll` (forwards by
name to GOG's renamed `strlkup_orig.dll`), `u32x/u32x.dll` (forwards by name to
`user32`; md5 and provenance in [`u32x/README.md`](u32x/README.md)),
`tools/i76wheel.exe` and the Mac launch stubs `tools/mac-kit/stubs/Sikarugir-*` (Swift, built by
`tools/mac-kit/build-stubs.sh` from `mac/i76-launch-stub.swift` / `mac/i76-nitro-app-stub.swift`). None contains game bytes. Everything original here is
[MIT-licensed](LICENSE). This file records what the project *builds on* but does
not own or redistribute.

## The game itself — you bring your own

**Interstate '76** and all its assets (executables, `*.ZFS`, textures, audio, FMV,
missions) are **© 1997 Activision** (rights now with Microsoft). This project does
**not** include, host, or distribute any of it. You must own a legitimate copy —
the [GOG "Interstate '76 Arsenal / Gold" release](https://www.gog.com/en/game/interstate76)
is the tested source. Downloaded game material lives only in a local, gitignored
`game-data/` folder on your own machine.

## Third-party tools (configured/referenced, never bundled)

Each keeps its own license; this repo only provides configuration and install
scripts that fetch them from their official sources at install time. The Windows Patch Kit zip
(`tools/package-patch-kit.ps1`, a release asset, not this repository) bundles three of them unmodified, each as its
licence allows: dgVoodoo, AutoHotkey and IPXWrapper (rows below).

| Tool | Role here | Source / license |
|---|---|---|
| **dgVoodoo2** (Dege) | Glide→D3D11 wrapper (Deck/Windows pretty path) | Freeware, dgVoodoo license — [dege.freeweb.hu](http://dege.freeweb.hu/). **Not redistributed by this repo**: `windows/setup-windows.ps1` copies it from a folder you downloaded (`-DgVoodooDir`), and `deck/deck-install.sh` fetches 2.78.2 at install time from a public archive.org mirror (`archive.org/download/dgvoodoo2_78_2_202205`). Redistribution checked 2026-10-23 (TESTER-BUILD record): Dege's ReadmeGeneral §1 says "You can freely ship your game or game mod with unmodified individual dgVoodoo components (files) included", so the Patch Kit (v0.7.x) bundles the unmodified x86 components (2.87.5, with 2.87.3 as a fallback folder), md5-checked against the official GitHub release, with that readme quoted in `_i76e\dgVoodoo\README-dgVoodoo.txt` |
| **DxWnd** (gho) | Windowing/scaling + virtual-CD music (Mac software path) | GPL — [sourceforge.net/projects/dxwnd](https://sourceforge.net/projects/dxwnd/). The Mac Kit (`tools/mac-kit`) downloads 2.06.14 on the Mac from SourceForge, SHA-256-pinned (`pins.txt`); not in its zip |
| **OpenGLide** | Glide→OpenGL wrapper (GOG-bundled) | LGPL. **OpenGLide-HD** = OpenGLide + this project's patches (`tools/openglide-hd/*.patch`): its Mac build (`glide2x.dll` 429e6e94) ships in the Mac Kit zip under the LGPL, sources = upstream OpenGLide + those patches |
| **DXVK** (doitsujin) | D3D→Vulkan (Deck/Android/Wine) | zlib/libpng — [github.com/doitsujin/dxvk](https://github.com/doitsujin/dxvk) |
| **Box64/Box86** (ptitSeb) | x86→ARM64 (Android/Winlator) | MIT — [github.com/ptitSeb/box64](https://github.com/ptitSeb/box64) |
| **Wine / Proton / Sikarugir / Winlator** | Windows compatibility layer per platform | LGPL and respective licenses. The Mac Kit downloads Sikarugir's wrapper template 1.0.11 and Wine engine 10.0_6 on the Mac from Sikarugir-App's GitHub releases, SHA-256-pinned, and deletes the template's D3DMetal (Apple licence) and other unused renderers; nothing of Sikarugir is in the zip |
| **IPXWrapper** (solemnwarning) | IPX over UDP for LAN games (PC, Macs, Deck); in DOSBox-server mode, internet games through a relay (`PLAY.bat --relay`, [tools/relay/](tools/relay/README.md)) | GPL v2 — [github.com/solemnwarning/ipxwrapper](https://github.com/solemnwarning/ipxwrapper). The Mac Kit downloads 0.7.2 on the Mac, SHA-256-pinned. **The Windows Patch Kit (from 2026-10-25) bundles an unmodified build of upstream master commit [dbe9a81](https://github.com/solemnwarning/ipxwrapper/commit/dbe9a81f9da457d2bdbd5d3ed1f8b5f147426205)** (`ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll` in `_ipx\relay\`; it contains e7e9883, the loopback fix the relay route needs, which no release has yet) under the GPL v2: the licence text, upstream's readme and the **complete source of that commit** (`ipxwrapper-source-dbe9a81.zip`, a `git archive`) ship beside the DLLs, with the sha256s and the build line (i686-w64-mingw32 gcc 16.2.0 + NASM 2.16.03, `make`). `windows/PLAY-i76.ps1` accepts only those sha256s. Not in this repository |
| **UCyborg "AiO" patch** | 20 FPS physics limiter (already inside the GOG 2019 exe) | See the AiO patch readme |
| **innoextract** | Extracts the GOG installer (Deck script) | zlib — [constexpr.org/innoextract](https://constexpr.org/innoextract/) |
| **AutoHotkey 1.1** (staged, input remapper WIP) | In-container input remapping | GPL — [autohotkey.com](https://www.autohotkey.com/) |
| **Lossless Scaling** (THS) | Optional frame generation on Windows (`windows/Setup-FrameGen.ps1`, `windows/PLAY-i76.ps1 -LosslessScaling`) | **Commercial** (Steam). Never fetched or shipped by this repo. `windows/Make-Portable-Zip.ps1 -IncludeFrameGen` copies *your* installed copy into *your* zip: your licence, your PCs only |
| **opentrack** | Optional head tracking (`i76-opentrack-*.ahk`, [docs/HEAD-TRACKING.md](docs/HEAD-TRACKING.md)) | ISC, with GPL-licensed components — [github.com/opentrack/opentrack](https://github.com/opentrack/opentrack). Not shipped; `windows/Make-Portable-Zip.ps1 -IncludeHeadTrack` copies your installed copy into your own zip |
| **GE-Proton** (GloriousEggroll) | Proton build the Deck scripts select | Proton's licences (BSD-style / LGPL components) — [github.com/GloriousEggroll/proton-ge-custom](https://github.com/GloriousEggroll/proton-ge-custom). Fetched on the Deck, not shipped |
| **Steam ROM Manager** | The controller-config apply mechanism `deck/add-to-steam.py` imitates (its configset approach); no code of it is used | GPL — [github.com/SteamGridDB/steam-rom-manager](https://github.com/SteamGridDB/steam-rom-manager). Referenced, not shipped |
| **input-remapper** | Referenced by the Deck control-tier scripts and docs (`deck/setup-deck-baseline.sh`, [docs/INPUT-REMAPPER.md](docs/INPUT-REMAPPER.md)) | GPL — [github.com/sezanzeb/input-remapper](https://github.com/sezanzeb/input-remapper). Installed on the Deck by the user, not shipped |
| **ViGEm / vJoy** | Mentioned only as things that can break FFB device acquisition ([docs/records/FFB-LAPTOP-RECON.md](docs/records/FFB-LAPTOP-RECON.md)) | Not used, not shipped |
| **w64devkit** (skeeto) | Optional 32-bit gcc for `music-fix/build.ps1` | Unlicense / GPL toolchain components — [github.com/skeeto/w64devkit](https://github.com/skeeto/w64devkit). A build tool; nothing of it is in the output |
| **Microsoft Visual C++ Build Tools 2019 (x86)** | What actually builds `Strlkup.dll` and `u32x.dll` (statically linked CRT, `/MT` for the proxy) | Microsoft licence; a build tool, not shipped |
| **RAD Smacker** (`SMACKW32.DLL`) | Game-shipped FMV library. `smack-music-fix/` builds a proxy that forwards to the game's own copy (renamed `smackorg.dll`) | © RAD Game Tools; part of the game install, never in this repo. Our proxy DLL is gitignored and built locally |
| **Cheat Engine** | Recommended for pointer scans ([AGENTS.md](AGENTS.md)) | Its own licence — [cheatengine.org](https://www.cheatengine.org/). Referenced, not shipped |

### Reverse-engineering tools (research only; nothing of them is shipped)

| Tool | Role here | Source / license |
|---|---|---|
| **Ghidra** (NSA) | Static analysis behind the memory maps in `docs/` and the sibling `i76-map` repo | Apache-2.0 — [ghidra-sre.org](https://ghidra-sre.org/). Decompiler output is Activision's code in another form and is **never** committed here |
| **capstone**, **pefile**, **Unicorn**, **Frida** | Disassembly, PE parsing, emulation and live instrumentation in the Python instruments (`tools/exe-disasm.py`, `tools/exe-xref.py`, the `i76-map` tools) | BSD / MIT / GPLv2 / wxWindows Library Licence respectively. `pip`-installed locally |
| **immi101's i76fix**, **bolrog's D2DX** | Prior art read for the frame-loop hook and render-interpolation design ([docs/records/FRAMERATE-UNCAP-RESEARCH.md](docs/records/FRAMERATE-UNCAP-RESEARCH.md)). No code of either is included | Their own licences; kept only in the lab's gitignored `refs/` |
| **Visual C++ 5.0 media** | Held locally for toolchain fingerprinting of the 1997 exe (sibling `i76-map`) | Microsoft; **never distributed**, not in any of the repos |

## Data & research credits

- **Weapon DPS / range figures** in the save editor: measured by **Local Ditch Gaming**
  (Greg Schwartz / "Zaphod-AVA") — [localditch.com](https://www.localditch.com/interstate-76/weapons.html).
  Used as reference data with credit; spec fallbacks come from the game's own `.gdf` files.
- **File-format groundwork**: **"That Tony"** reversed many I76 formats (2016–17), the
  foundation later reimplementations and this repo's save/texture work build on.
- **Reimplementation projects** referenced (not included): **Open76** (Unity) and
  **Roanish/i76 "Vigalante '76"** — see [docs/records/MODERN-PORTS-AND-VR.md](docs/records/MODERN-PORTS-AND-VR.md).
- **CahootsMalone's `interstate-76-stuff`** guide and tools, and the other community sources indexed by
  problem in [docs/COMMUNITY-RESOURCES.md](docs/COMMUNITY-RESOURCES.md). Linked, not copied.

## What the portable zip is

`windows/Make-Portable-Zip.ps1` packs **your own configured install** — game files, the dgVoodoo DLLs you
downloaded, optionally your Lossless Scaling and opentrack — for moving between computers you own. It
is not a distribution format and must not be shared; the script's header and INSTALL.md say the same.

## If you represent a rights holder

Nothing here contains your game content — only interoperability tooling and
documentation created independently. If anything looks otherwise, open an issue
and it will be addressed promptly.
