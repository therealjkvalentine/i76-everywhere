# Third-party components, game content & attribution

This repository ships **no copyrighted game files** and **no third-party binaries**
(see [`.gitignore`](.gitignore)). It is scripts, source, configuration, and
documentation only. Everything original here is [MIT-licensed](LICENSE). This file
records what the project *builds on* but does not own or redistribute.

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
| **dgVoodoo2** (Dege) | Glide→D3D11 wrapper (Deck/Windows pretty path) | Freeware, dgVoodoo license — [dege.freeweb.hu](http://dege.freeweb.hu/) |
| **DxWnd** (gho) | Windowing/scaling + virtual-CD music (Mac software path) | GPL — [sourceforge.net/projects/dxwnd](https://sourceforge.net/projects/dxwnd/) |
| **OpenGLide** | Glide→OpenGL wrapper (GOG-bundled) | LGPL |
| **DXVK** (doitsujin) | D3D→Vulkan (Deck/Android/Wine) | zlib/libpng — [github.com/doitsujin/dxvk](https://github.com/doitsujin/dxvk) |
| **Box64/Box86** (ptitSeb) | x86→ARM64 (Android/Winlator) | MIT — [github.com/ptitSeb/box64](https://github.com/ptitSeb/box64) |
| **Wine / Proton / Sikarugir / Winlator** | Windows compatibility layer per platform | LGPL and respective licenses |
| **UCyborg "AiO" patch** | 20 FPS physics limiter (already inside the GOG 2019 exe) | See the AiO patch readme |
| **innoextract** | Extracts the GOG installer (Deck script) | zlib — [constexpr.org/innoextract](https://constexpr.org/innoextract/) |
| **AutoHotkey 1.1** (staged, input remapper WIP) | In-container input remapping | GPL — [autohotkey.com](https://www.autohotkey.com/) |

## Data & research credits

- **Weapon DPS / range figures** in the save editor: measured by **Local Ditch Gaming**
  (Greg Schwartz / "Zaphod-AVA") — [localditch.com](https://www.localditch.com/interstate-76/weapons.html).
  Used as reference data with credit; spec fallbacks come from the game's own `.gdf` files.
- **File-format groundwork**: **"That Tony"** reversed many I76 formats (2016–17), the
  foundation later reimplementations and this repo's save/texture work build on.
- **Reimplementation projects** referenced (not included): **Open76** (Unity) and
  **Roanish/i76 "Vigalante '76"** — see [docs/MODERN-PORTS-AND-VR.md](docs/MODERN-PORTS-AND-VR.md).

## If you represent a rights holder

Nothing here contains your game content — only interoperability tooling and
documentation created independently. If anything looks otherwise, open an issue
and it will be addressed promptly.
