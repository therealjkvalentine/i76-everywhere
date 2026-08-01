# Changelog

All notable milestones for **i76-everywhere**. Dates are ISO. This project follows
["bring your own game"](THIRD-PARTY.md) — it ships no copyrighted content.

## Unreleased

- **A force-feedback wheel, measured end to end (Thrustmaster T300RS).** The oldest
  open question in the repo — can a real wheel drive I76 — answered on Windows with
  hardware instead of community reports. Two non-obvious blockers, both found by
  measuring through winmm (`joyGetPosEx`, the API the engine itself reads): a T-series
  wheel enumerates in a crippled **pre-initialisation mode** until its driver is
  installed (`PID_B65D` "Thrustmaster FFB Wheel", pedals frozen at a single value, no
  FFB) — installing it re-enumerates as `PID_B66E` "T300RS"; and the wheel's default
  **Separate (3-axis) pedal mode cannot drive I76 at all**, because both pedals rest at
  an *extreme* while I76's `throttle` is a single bidirectional sink expecting rest =
  *centre*, so it pins at full deflection (runaway throttle). **Combined (2-axis)** mode
  gives one centre-resting axis and the stock binding is then correct. Full axis/button
  map, FFB status and the settings that matter in
  [docs/WHEEL-T300.md](docs/WHEEL-T300.md); new instrument
  [`tools/i76-joyprobe.py`](tools/i76-joyprobe.py) (waits for input rather than racing a
  timer, and warms up before baselining — a naive trigger fires on the device settling,
  not the user). Configured and measured; **not yet driven in a mission**.
- **Frame generation without Steam.** Lossless Scaling turns out to have no Steam
  dependency at all — no `steam_api64.dll`, no Steamworks imports, and when launched
  directly it loads zero Steam client modules and keeps running with Steam fully shut
  down (verified 2026-08-01). Only the Steam-installed desktop shortcut
  (`steam://rungameid/...`) was pulling Steam in. Added an `Interstate '76 Gold Edition`
  profile with `AutoScale=true` + fixed 2× so frame-gen engages by itself — no Ctrl+Alt+S —
  and [`PLAY-i76.ps1`](PLAY-i76.ps1) now starts/stops it with the game (only if it wasn't
  already running). Physics stay at the 20 FPS base; these are interpolated *display*
  frames only. Details in [docs/WINDOWS-PLAYBOOK.md](docs/WINDOWS-PLAYBOOK.md) sec 2.
  [`Setup-FrameGen.ps1`](Setup-FrameGen.ps1) scripts the whole thing (profile +
  `-FixShortcut` + `-Revert`) so a second PC is one command.
- **Steam Deck: baseline control tier — rumble parity with Mac/Windows (untested on
  device).** The Deck ran Steam Input keyboard emulation and so never got the pad layer
  the other two platforms grew: the rumble mixer, LB shift layer, independent triggers,
  look-back rear gun. New [`deck/setup-deck-baseline.sh`](deck/setup-deck-baseline.sh)
  stages the *same* `i76-remap.ahk` plus AutoHotkey, and
  [`deck/i76-deck-launch.sh`](deck/i76-deck-launch.sh) — a `%command%` wrapper — injects it
  into the live Proton prefix (read from `$STEAM_COMPAT_DATA_PATH`, since Steam runs
  non-Steam shortcuts out of `compatdata/<appid>`, not the install-time prefix).
  [`deck/deck-push.sh`](deck/deck-push.sh) deploys it over ssh. The correct Steam setting
  is the **"Gamepad" template**, *not* "disable Steam Input" — the latter drops a Deck into
  lizard-mode keyboard/mouse. Recipe, decode sheet and rollback:
  [docs/DECK-BASELINE.md](docs/DECK-BASELINE.md). **Deployable but unverified** — the Deck
  was offline when this landed; button numbering and the XInput→haptics rumble path are
  ASSUMED until the decode sheet comes back.
- **Windows: Nitro Pack fully scripted.** `install.ps1` now auto-detects a GOG Nitro
  Pack install and applies the identical recipe (`setup-windows.ps1 -Exe nitro.exe`):
  dgVoodoo deploy + conf, input.map controls parity, `PLAY-Nitro.bat` + shortcut.
- **Windows fixes shipped from live play:** physics-safe FPS cap; handbrake on Space;
  campaign-save deployment; borderless-windowed 14:9 aspect (matches the Mac look);
  `FullscreenAttributes=fake`/windowed so the engine's modal dialogs no longer
  deadlock behind an exclusive surface; `[GlideExt] pure32bit` restored (16-bit
  fallback was causing purple night terrain); and the KB5101650 `winmmbase` boot
  crash diagnosed (uninstall the update — see docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md).
- **HD texture pack RETIRED.** The full-game enhanced-texture pack was built and then
  pulled: the in-game improvement didn't justify shipping it, and palette-indexed
  tiles rendered wrong on night missions (no palette-agnostic fix exists). The
  `-WithHDTextures` build step is gone; the research — including the cracked `.M16`
  format spec — is preserved in [docs/HD-TEXTURES-RESEARCH.md](docs/HD-TEXTURES-RESEARCH.md)
  for future work. The OpenGLide-HD fork ([tools/openglide-hd/](tools/openglide-hd/))
  remains as the unfinished true-HD route.

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
