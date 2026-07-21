# Changelog

All notable milestones for **i76-everywhere**. Dates are ISO. This project follows
["bring your own game"](THIRD-PARTY.md) — it ships no copyrighted content.

## Unreleased

- **Windows: Nitro Pack fully scripted.** `install.ps1` now auto-detects a GOG Nitro
  Pack install and applies the identical recipe (`setup-windows.ps1 -Exe nitro.exe`):
  dgVoodoo deploy + conf, input.map controls parity, `PLAY-Nitro.bat` + shortcut.
  The HD texture pack is installed into Nitro's `ADDON\` too (its texture tiles are
  100% byte-identical to the base game's — one build covers both).
- **OpenGLide-HD fork vendored** as a patch series + rebuild instructions in
  [`tools/openglide-hd/`](tools/openglide-hd/) — the true-HD (arbitrary-resolution)
  texture route previously living only on one machine.

## v1.0.0 — "Vacation Build" (2026-07-14)

First public milestone: Interstate '76 (GOG Gold, 1997) running well on three platforms
from a free/open-source stack, plus a save editor and reverse-engineered file formats.
Everything below was hit, diagnosed, and verified in play on this port — details in
[docs/VERIFIED-FIXES.md](docs/VERIFIED-FIXES.md).

### Play — Apple Silicon Mac (the shipping build)
- Self-contained Sikarugir **Wine 10 (wow64)** wrapper, software renderer via **DxWnd** — instant
  start, no shader compile, big letterboxed 4:3 window at 1024×768.
- **In-mission music** restored (virtual CD-audio + track relinking; GStreamer env wired into the
  launcher stub).
- **Cutscene-music bug fixed** — proxy `SMACKW32.DLL` recreates the 1997 CD-drive behavior the
  community had called unfixable (ordinal-exact 39-export forwarder).
- **Clean quit** (no lingering black "wine" window), Mac arrow-key steering fix, mouse + Xbox-pad
  input, physics-safe **~19.2 FPS** cap for the Mission 5 jump and later bridge gaps.

### Play — Steam Deck
- Installed & working: Heroic/Proton + **dgVoodoo 2.78.2** Glide path (native Vulkan — bright
  3dfx color, 2× res, MSAA) **with force feedback**, full controller layout, library artwork.
- **One-liner installer** (`deck/deck-install.sh`, zenity-guided) — extracts *your* GOG installer,
  fetches dgVoodoo from the public mirror, registers the game with artwork and controls.

### Play — modern Windows
- One-command `install.ps1`: max-graphics dgVoodoo, force feedback, optional HD texture pack built
  locally from your own files.

### Tools
- **Save editor** — browser page styled as the game's Build & Repair Form (equipped loadout,
  editable armor, van/repair inventory, measured weapon DPS + range, part swaps, condition, scene
  select). Runs three ways: one-click Mac launcher with write-back + timestamped backups, a
  terminal CLI, and a **zero-install drag-and-drop browser page** (now hostable on GitHub Pages).
- **Reverse-engineered formats**: the save format (116-byte records, item catalog from I76.ZFS)
  fully decoded in the `.py` docstring; the VQM/M16 texture formats cracked with round-trip
  encoders in `texture-lab/`.

### Docs & research
- The doc map ([docs/README.md](docs/README.md)) tags every approach **working / parked dead-end /
  other-platform / reference** so nobody re-chases a settled problem (Voodoo-on-Mac shader
  persistence, Mac force feedback, HD-on-Mac renderer switch).
- New: **phone-port research** ([docs/PHONE-PORTS.md](docs/PHONE-PORTS.md)) — Android via Winlator,
  iPhone via streaming/UTM.

### Project
- Now MIT-licensed ([LICENSE](LICENSE)) with full third-party attribution ([THIRD-PARTY.md](THIRD-PARTY.md)).
- Promoted from `mac-gaming-ports/games/interstate-76/` to a standalone repo.

### Known gaps / next
- Universal in-Wine input remapper (AutoHotkey) staged, not yet wired into the launcher.
- Mac from-scratch install still requires the manual Wine-wrapper step (`mac-install.command` is BETA).
- Mission 6 night-texture re-quantize is a Windows texture-lab job.
