# tools/: developer tooling

Nothing here is needed to play. These are the builders of the kits, the test harness pieces that live in this repo,
the reverse-engineering and research scripts, and the media pipelines. A folder's own README (where there is one) has
the details; the scripts carry a header comment that says why they exist.

## Build and package

| Folder or file | What it is |
|---|---|
| [`patch-kit/`](patch-kit/README.md), `package-patch-kit.ps1` | The Windows Patch Kit: its first-start setup, updater, controls and extras scripts, the shell key patches, and the builder of the release zip |
| [`mac-kit/`](mac-kit/README.md), `package-mac-kit.ps1` | The Mac Kit: the app builder, pinned downloads, launch stubs and the builder of its zip |
| `package-deck-kit.ps1` | The Deck Kit zip (the kit itself is in [`../deck/kit/`](../deck/kit/README.md)) |
| `build-proxy.ps1` | Build the proxy `Strlkup.dll` ([`../music-fix/`](../music-fix/README.md)) |
| [`conf/`](conf/) | The widescreen dgVoodoo conf templates `Make-Wide-Conf.ps1` writes from |
| [`controls-sheet/`](controls-sheet/README.md) | The printable controls sheet and the check that keeps map, layers and sheet in agreement |
| [`openglide-hd/`](openglide-hd/README.md) | OpenGLide-HD, the Mac 3D path: our patches to OpenGLide |
| [`dxvk-pipeline-cache-persist/`](dxvk-pipeline-cache-persist/BUILD.md) | A DXVK patch for the parked Mac Voodoo mode |
| [`nitro-mac/`](nitro-mac/), [`nitro-sites/`](nitro-sites/) | Building and checking the Nitro Mac app; the Gold-to-Nitro site map the proxy uses |
| [`relay/`](relay/README.md) | The internet relay for network games (host side) |
| [`save-editor/`](save-editor/) | The save editor (terminal and Mac versions; the browser one is `../i76-save-editor.html`) |
| [`debug/`](debug/README.md), [`trainer/`](trainer/README-GUI.md), [`telemetry/`](telemetry/README.md) | I76 Debug (the debug / cheat tool the kit ships), the trainer it grew from, and the telemetry export |
| [`driver/`](driver/) | The `.bat` files the installers put in a game folder (`DEBUG.bat`, `TRAINER.bat`, ...) |
| `Make-Wide-Conf.ps1`, `Build-From-GOG.ps1`, `Make-Daily-Driver.ps1`, `Promote-To-Driver.ps1` / `PromoteLib.ps1` / `promote-*.ps1`, `consolidate-copies.ps1` / `consolidate-retry-locked.ps1` | Game-folder builders: the widescreen conf, a full build from GOG, the developer's installs and their promotions (history: each `promote-N` is one promotion) |
| `lint-input-map.py`, `fix-shell-textentry.ps1`, `i76wheel.c` / `i76wheel.exe`, `i76-music.ps1`, `cursor-mode.ps1` | Small tools the installers and launcher use |

## Test harness

| Folder or file | What it is |
|---|---|
| [`../tests/`](../tests/) | `pytest tests`: the offline suite (no game needed) |
| [`tests/`](tests/) | Node checks of the browser save editor |
| [`bisect/`](bisect/README.md) | Start from stock and add one layer at a time |
| [`lan-test/`](lan-test/README.md) | Re-run the LAN matrix across PCs and Macs |
| [`headlook-test/`](headlook-test/), [`headlook-cost/`](headlook-cost/) | The head-look layer without the game; its frame-rate cost study |
| [`roadmap/`](roadmap/) | The GitHub project board script and the QA issue template |
| `mp-pack.py`, `mp-mac-install.sh`, `mp_pool.py`, `coop-install.py`, `coop-mission.py`, `aimelee-mission.py`, `mac-test-clone.sh`, `make-desktop-shortcuts.ps1`, `ft-heartbeat.ps1`, `grab-screen.ps1`, `test-shell-f2.ps1`, `setup-debugger.sh`, `setup-sshd-windows.ps1` | Multiplayer packs and arenas for test machines, and helpers for test runs |

The game-driving harness itself (`autotest/`) lives in the lab; a public snapshot is in [`../lab/`](../lab/README.md).

## Reverse engineering and research

| Folder or file | What it is |
|---|---|
| [`ffb/`](ffb/README.md), [`haptics/`](haptics/README.md) | Force feedback and haptics: the custom FFB stack, the rig / motion host, their probes |
| [`versions-catalogue/`](versions-catalogue/), [`wine-probe/`](wine-probe/), [`cdaudio-image/`](cdaudio-image/) | Comparing game versions; a Wine probe; CD-audio from a virtual drive |
| [`upscale/`](upscale/README.md), [`menu-hd/`](menu-hd/) | Texture upscaling and HD menu art experiments |
| [`content-archive/`](content-archive/) | Community content: fetch, index and stage arenas |
| `export_public.py` / `export_public.toml` | The filter that makes the public `lab/` and `re/` snapshots |
| `exe-disasm.py`, `exe-xref.py`, `i76-mem-scan.py`, `level-objects.py`, `find-regen-*.py`, `i76-addresses.json`, `i76img.py`, `gpw-*.py`, `zfs_extract.py`, `i76-joyprobe.py`, `patch-*shell-*.py`, `parse-asset-bible.py`, `asset-bible-to-md.py`, `ffb-recon.ps1`, `ffb-udp-listen.py`, `check-ffb.ps1`, the `*.sh` and `i76-*.ahk` memory / FFB probes | Memory and file-format work; [docs/research/RE-METHODOLOGY.md](../docs/research/RE-METHODOLOGY.md) says how to use them |

## Media

| Folder or file | What it is |
|---|---|
| [`launch-video/`](launch-video/) | The launch video pipeline ([docs/release/LAUNCH-VIDEO-2026-10-25.md](../docs/release/LAUNCH-VIDEO-2026-10-25.md)) |
| [`soundhd/`](soundhd/README.md) | The HD sound pack pipeline |
| `pad-diagram.py` | The pad layout diagrams in [docs/guides/](../docs/guides/) |

## Records and docs

| File | What it is |
|---|---|
| `records-index.py` | Writes [docs/records/README.md](../docs/records/README.md), the index of every record by topic. Run it after adding a record (`--check` tells whether the index is current) |
| `place-agents-md.ps1` | Writes the `AGENTS.md` of a kept game folder from [docs/process/AGENTS-GAME-FOLDER.md](../docs/process/AGENTS-GAME-FOLDER.md) |
