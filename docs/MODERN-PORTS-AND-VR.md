# Interstate '76 — the D3D "port", VR, and the modern-engine landscape (2026)

*Deep-research answer to "is there a Direct3D port? a VR port?" Short version: the renderer-select
screen is the **1997 game's own** picker (not a port), native D3D is the **worst** mode, **no VR
port exists**, but two **live 2026 reimplementation projects** are the real "modern I76" story.*

## The renderer-select screen is native — and D3D is the mode to avoid

`NORMAL / WINDOW / DIRECT 3D / 3Dfx / RENDITION / POWERVR / BACK` is I76's **1997 hardware picker**.
The game shipped with software rendering plus four era-specific hardware backends (there was no
common HAL yet): flags `-software`, `-d3d`, `-glide`, `-powervr`, `-rendition`. So "DIRECT 3D" is a
*native mode*, not a separate port.

Quality ranking (the surprise): **D3D is the worst-looking**, not an upgrade.
- **Direct3D 5** — ~640×480 with **deliberately down-res'd textures** (D3D was immature in '97, so
  Activision shipped lower-res textures to match Glide's speed). Also still needs dgVoodoo to init
  on modern Windows, and is flaky under Wine. **No reason to use it.**
- **Glide (3dfx)** — 640×480 but **full-res, bilinear-filtered** textures = the prettiest. Why every
  modern guide (and our Deck build) targets Glide via dgVoodoo, which can also push internal res
  above 640×480 (4:3 only — 16:9 stretches; camera math assumes 4:3).
- **Software** — highest native res (**up to 1024×768**) but unfiltered/flatter. Our Mac build.

*(One source disputes the resolutions — claims D3D=1024×768, Glide=640×480 — but that's the minority
view; the consensus is D3D=640×480-low-textures, software=1024×768. Don't treat "D3D = higher res"
as reliable.)*

**Verdict for us:** don't switch to `-d3d` anywhere — it's strictly worse than our Glide (Deck) and
software (Mac) paths. Our stack is already at the local optimum for the 1997 binary.

## VR — none exists (yet). It's vaporware today.

- **No VR port or mod of I76** exists. No Open76 VR fork, no branch, no code.
- **vorpX won't natively touch it.** vorpX's floor is DirectX 9; I76 is software/DX5/Glide, *below*
  that. No I76 vorpX profile exists. The only theoretical route — dgVoodoo wrap I76→DX11, then
  vorpX hooks the wrapper — gives, with no game profile, a **flat 2D screen floating in the
  headset** (cinema mode), *not* true VR. Even fake stereoscopic depth is unlikely/unverified, and
  **true 6DOF is impossible** without engine-level VR support.
- The **only** credible long-term VR path is an engine reimplementation adding it. Open76 *lists*
  "HMD and VR support" as a long-term goal — **unimplemented**. So: log VR as "not currently
  possible," revisit only if a reimplementation ships it.

## The real modern-I76 story — two live 2026 projects

Neither is a drop-in yet, but both are the genuine path to modern-API / higher-res / widescreen /
uncapped-framerate I76, and both are cross-platform-capable:

- **[rob518183/Open76](https://github.com/rob518183/Open76)** — the **live 2026 fork** of the
  (otherwise dead-since-2020) [r1sc/Open76](https://github.com/r1sc/Open76) Unity reimplementation.
  Reads the *original* game assets; ~20 commits ahead of upstream (active to June 2026), adding car
  physics/skid/gearbox/audio work. **Unity → Metal**, so it *can* run natively on the Mac and Deck
  with modern resolution and widescreen. Caveat: no packaged build (needs the Unity editor + your
  assets), and the sim/combat is unfinished — a promising WIP, not a game yet. **This is the fork to
  watch, not the dead master.**
- **[Roanish/i76](https://github.com/Roanish/i76) — "Vigalante '76"** — a **new** (June 2026)
  from-scratch **C rewrite reversed from the binary via Ghidra**, **SDL2 + native Vulkan**, native
  Linux/Windows, no compat layers, planned upscaled models/textures. Very early (Vulkan does only a
  fullscreen blit; the mesh viewer rasterizes on CPU; no scene renderer/physics/AI yet) but real and
  buildable. Effectively an independent realization of Shane Peelar's announced-but-never-shipped
  "native Vulkan renderer."

## The RE landscape (for context)

- **Shane Peelar** ([inbetweennames.net](https://inbetweennames.net/blog/2021-05-04-interstate-76-reverse-engineering-efforts-the-story-so-far/))
  — reverse-engineered I76/Nitro **online play**, documented the **20 fps physics dependency**, and
  found Activision's fast-inverse-sqrt predating Quake III. Announced a Vulkan renderer in 2021 —
  never shipped.
- **"That Tony"** — reversed most I76 file formats (2016–17), the foundation the reimplementations
  build on.
- Tooling: [chasseyblue/i76-geo-importer](https://github.com/chasseyblue/i76-geo-importer) (Blender,
  2026), [rickymagal/i76_patch](https://github.com/rickymagal/i76_patch) (a `ddraw.dll` proxy
  FPS-cap — an alternative to our DxWnd 20 fps method), [CahootsMalone](https://github.com/CahootsMalone/interstate-76-stuff)
  (the dgVoodoo guide).
- **Official remaster: none** — only fan speculation.

## Note for this repo's owner

The research turned up **[therealjkvalentine/time-vigalantes](https://github.com/therealjkvalentine/time-vigalantes)**
("clean-room I76 spiritual successor, Godot 4 + C#", June 2026) — almost certainly **your own**
project. Curiously, Roanish's faithful decompile shares the "**Vigalante '76**" pun. Two different
bets on I76's future — your clean-room Godot *successor* vs. Roanish's faithful Ghidra *decompile*
— worth being aware of each other.
