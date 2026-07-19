# Interstate '76 docs — what's real, what's a dead end

*Read this first. This repo accumulated a lot of research across the Mac, Steam Deck and Windows
efforts — some of it is the shipping solution, some is a **tried-and-abandoned dead end** we keep
only so nobody re-chases it. Each doc below is tagged so you know which is which before you act on
it.*

## Current state (2026-07-11)

- **The Mac build = the software renderer via DxWnd.** One app: **`Interstate 76 - Software
  (DxWnd).app`** (+ a DxWnd-settings app). Instant start, no shader compile, big 4:3 window,
  in-mission music, clean quit, 20 FPS physics-safe, 1024×768. Wrapper slimmed to **1.4 GB**.
- **The "Voodoo" Glide→Metal mode is PARKED** — it worked and looked great but MoltenVK can't
  persist compiled Metal pipelines, so it re-compiles shaders every launch. Not worth it vs the
  instant software renderer. See `VOODOO-PARKED.md` for the one announcement that revives it.
- **The pretty Glide path + force feedback live on the Steam Deck** (native Vulkan, no MoltenVK).
- **Windows box** has its own max-graphics + texture-replacement work.

## ✅ Working — the shipping Mac build

| Doc | What it is |
|---|---|
| **[I76-GAMEPLAY-REFERENCE.md](I76-GAMEPLAY-REFERENCE.md)** | Controls, weapons/hardpoints, specials (nitrous/bumpers), the Mission 5 jump - the gameplay facts that trip people up. |
| **[VERIFIED-FIXES.md](VERIFIED-FIXES.md)** | **START HERE.** Every symptom→cause→fix that shipped, one table. The source of truth for what works. |
| [DXWND-TUNING.md](DXWND-TUNING.md) | DxWnd profile settings, grounded in the v2.06.14 source (aspect/letterbox/renderer). |
| [`../i76-save-editor.py`](../i76-save-editor.py) | **Save editor (CLI)** — lists saves, swaps any garage-inventory item for any allowed item, sets condition/grade. Save format reverse-engineered 2026-07 (uncompressed 116-byte records; item catalog from the I76.ZFS defs). Auto-backups (`.pre-edit`); works on the live wrapper saves and the repo `saves/`. |
| [`../i76-save-editor.html`](../i76-save-editor.html) | **Save editor (browser)** — self-contained HTML page styled after the game's own **Build and Repair Form**: equipped loadout, **editable armor** (same tenths as the DEFENSE panel), **van inventory (V)** and **repair order (R)** with weapon **DPS + range** (Local Ditch's measured stats, spec fallback from the .gdf files), part swaps / condition, save to any slot (new slots get an updated `savegame.dir`). Same parser as the CLI, verified byte-identical. |
| [`../i76-save-editor.command`](../i76-save-editor.command) | **One-click launcher** for the browser editor: starts [`i76-save-editor-server.py`](../i76-save-editor-server.py) (localhost-only), auto-finds the wrapper's saves (`--dir` to override), opens the page with the order pad pre-loaded, and lets **Save Bookmark write straight back to the game folder**. Every write keeps a **timestamped backup** (restore via the History dropdown); **Delete** removes a bookmark from the game recoverably (a "↩ restore" row appears on the pad). Without the launcher the page runs in drag-and-drop/download mode (artifact, Deck, Windows). |
| [`../smack-music-fix/`](../smack-music-fix/) | **Cutscene-music fix** — proxy `SMACKW32.DLL` that stops the leaked CD track when a movie starts (recreates the 1997 CD-drive behavior the devs relied on). Ordinal-exact 39-export forwarder; works on Mac (DxWnd) and GOG-Windows. Install: `setup-cutscene-music-fix.sh`. |
| [EDITOR-FIELD-TESTS.md](EDITOR-FIELD-TESTS.md) | The save editor's open in-game questions as a 10-minute checklist (paint vtf swap, GROSS WT calibration, bench/van caps, condition colors, spc01) — results get locked into the editor + format docs. |
| **[INPUT-REMAPPER.md](INPUT-REMAPPER.md)** | **Universal input remapper** — AutoHotkey v1.1 running INSIDE the Wine/Proton prefix (one config for Mac/Deck/Windows): mouse buttons 4/5 → specials, wheel → gear shift. Install: `setup-input-remapper.sh` (sha256-pinned download, `--test` hook harness); config: `i76-remap.ahk`; auto-started/reaped by the Mac launcher. In-game button test pending user field run. |

## 🅿️ Dead ends & parked — tried on the Mac, do NOT re-chase

| Doc | Verdict |
|---|---|
| **[VOODOO-PARKED.md](VOODOO-PARKED.md)** | The dgVoodoo Glide→Metal mode. **Parked** — MoltenVK can't persist compiled Metal pipelines (MoltenVK#1765, absent in 1.4.1). Has the exact trigger + un-park playbook. Don't try to "fix the warmup" — it's a platform floor. |
| [VISUAL-QUALITY-MAC.md](VISUAL-QUALITY-MAC.md) | The Voodoo graphics wins (gamma/MSAA/32-bit) + the warmup-ceiling proof. Wins were real; the mode is parked (see above). |
| [DXGI-DGVOODOO-RESEARCH.md](DXGI-DGVOODOO-RESEARCH.md) | The full dgVoodoo-under-Wine saga. Useful root-causes, but its "future fix: persist the pipeline cache" is now known to be a **floor, not a fix** — superseded by VOODOO-PARKED. |
| [FORCE-FEEDBACK-AND-VISUALS.md](FORCE-FEEDBACK-AND-VISUALS.md) | Mac **wheel** FFB via DirectInput stays dead (Wine's only FFB backend is Linux evdev) — but the 2026-07-19 disassembly **overturned the general Mac verdict**: the FFB plugin DLL can be faked ([`../ffb-shim/`](../ffb-shim/)) to get the game's own force stream as pad rumble. Also the 1024×768 software ceiling (still true). |
| [HD-TEXTURES-RESEARCH.md](HD-TEXTURES-RESEARCH.md) | HD-texture **pipeline** works (format cracked, tools in `../texture-lab/`), but true-HD on the Mac needs an OpenGLide-HD **renderer switch** away from the software path — **parked**. A full pack exists on the Windows box. |

## 🌐 Other platforms — working there, not applicable to the Mac build

| Doc | What it is |
|---|---|
| [STEAMDECK.md](STEAMDECK.md) | **Installed & working on the Deck.** Heroic+Proton+dgVoodoo; the Glide path runs great (native Vulkan). |
| [PHONE-PORTS.md](PHONE-PORTS.md) | **Research/untested.** Android = the Deck recipe again (Winlator: Wine→DXVK→Turnip) — I76 is an ideal candidate. iPhone = stream (Sunshine/Moonlight) or a QEMU VM (UTM). The save editor already works in a mobile browser. |
| [GAMEPAD-PC-MAC.md](GAMEPAD-PC-MAC.md) | Xbox gamepad on **PC & Mac** via the native winmm-joystick path (axes/buttons already in input.map). |
| [DECK-CONTROLS.md](DECK-CONTROLS.md) / [DECK-INPUT-SCIENCE.md](DECK-INPUT-SCIENCE.md) | Deck controller layout + the input pipeline. |
| [WINDOWS-PLAYBOOK.md](WINDOWS-PLAYBOOK.md) | Windows-box max graphics / FFB / frame-gen playbook. |
| [FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md](FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md) | Windows results + the M16 texture-format crack + texture-replacement pipeline. |
| [MODERN-SETUP.md](MODERN-SETUP.md) | Windows-side setup notes. |

## 🔬 Memory RE & trainers — the 2026-07-18 push, consolidated

*Several parallel threads reverse-engineered the live game process (owned GOG
copy, own process — see [SCOPE-AND-LEGITIMACY.md](SCOPE-AND-LEGITIMACY.md) /
[LEGITIMACY-AND-SCOPE.md](LEGITIMACY-AND-SCOPE.md)). Everything they learned —
including what did NOT work — is reconciled in one place.*

| Doc | What it is |
|---|---|
| **[MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md)** | **START HERE — the current truth.** The verified pointer chains (player entity, the ammo/parts inventory table, the all-vehicles entity table), armor candidates, feature applications (trainer, head-look, rumble, music), and a named **dead-ends list** so nobody re-chases them. Supersedes the raw logs where they disagree. |
| [GHIDRA-MEMORY-MAP.md](GHIDRA-MEMORY-MAP.md) / [STATIC-RE-FABLE.md](STATIC-RE-FABLE.md) | **Raw session logs** (PARTs 1–13b / §1–12), kept for provenance. Contain intermediate claims later corrected — read the index first. |
| [RE-METHODOLOGY.md](RE-METHODOLOGY.md) · [RE-FIELD-GUIDE.md](RE-FIELD-GUIDE.md) · [RE-RESOURCES.md](RE-RESOURCES.md) | Method references (cited): scan discipline, watchpoints, why single value-matches lie, CE-in-prefix. |
| [MW2-I76-STRUCTS.md](MW2-I76-STRUCTS.md) | Struct/encoding shapes from the file formats + Open76/Roanish (ammo = int32 countdown; armor = int tenths). |
| [SAVE-FORMAT-GAPS.md](SAVE-FORMAT-GAPS.md) | Save-bytes ↔ in-game-screen reconciliation for the save editor. |
| `../tools/i76-debugmenu.ahk` · `i76-rearm.ahk` · `i76-worldscan.ahk` · `i76-trainer.ahk` · `i76-chaindiff.ahk` | The working tools built on the map: **debug menu** (live-edit + freeze every inventory value, change-flagging + auto-log; launch via `tools/debugmenu.sh`, field test: [DEBUG-MENU-FIELD-TEST.md](DEBUG-MENU-FIELD-TEST.md)), repair+rearm (field-tested), all-vehicle enumeration (field-tested), live overlay/scanner, relocation-proof offset differ. Machine-readable map: `../tools/i76-addresses.json`. |
| `../tools/gpw-envelopes.py` | Sound→rumble pipeline: decodes the game's .gpw effects, emits per-sound amplitude envelopes for the AHK rumble layer (generated table stays local/gitignored). |
| [FFB-DEEP-DIVE.md](FFB-DEEP-DIVE.md) · [`../ffb-shim/`](../ffb-shim/) | **The force-feedback crack (2026-07-19):** FFB is a plugin DLL with 3 functions; the exe streams a fully-mapped force-state block every tick. The shim replaces the DLL — game FFB activates with no DirectInput device (incl. Mac), stream drives pad rumble + telemetry + UDP. Not yet field-run. |
| [MOTION-SIM.md](MOTION-SIM.md) · `../tools/i76-ffb-monitor.ahk` · `ffb-udp-listen.py` | **Home 6DOF motion sim + wheel FFB path.** Maps the shim's force stream onto SimTools/SimHub (the standard receivers); the AHK overlay + UDP listener are the "watch/tune the stream" viewers. Full DOF set needs a memory reader; wheel torque is Windows-only. Not yet rig-verified. |

## 📚 Reference / historical — context, not instructions

| Doc | What it is |
|---|---|
| [MODERN-PORTS-AND-VR.md](MODERN-PORTS-AND-VR.md) | Is there a Direct3D port / VR port? (No.) The native renderers, why D3D is the *worst* mode, the VR verdict, and the live 2026 reimplementations (Open76 fork, Roanish/i76). |
| [RUNNING-I76-EVERYWHERE.md](RUNNING-I76-EVERYWHERE.md) | Cited compendium of every documented way to run I76 (broad research). |
| [MAC-SETUP.md](MAC-SETUP.md) | The original Windows→Mac handoff brief. Historical; superseded by VERIFIED-FIXES. |
| [i76-research-full.txt](i76-research-full.txt) | Raw deep-research dump (FPS/physics/renderers). Historical. |
| [WHAT-THIS-IS-dgvoodoo.txt](WHAT-THIS-IS-dgvoodoo.txt) | dgVoodoo config notes (Windows-era). |
| [OUTREACH-DRAFT.md](OUTREACH-DRAFT.md) | Unposted community-post draft. |

## Rule of thumb for a future agent

If a doc says a Mac approach is "in progress" or "to try," **cross-check VERIFIED-FIXES.md and
VOODOO-PARKED.md first** — several once-open items are now settled (the shader warmup is a MoltenVK
floor; FFB is a Mac dead end; HD textures need a renderer switch). Don't re-open a settled dead end.
