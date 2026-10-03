# Repo organisation proposal

Written 2026-10-03. **A proposal: nothing described here has been moved.** The only tidying done so far is that
three compiled Python files and `grep.exe.stackdump` are no longer tracked (ignore rules added). Everything else at
the repo root stays where it is until the owner picks a stage below, because the scripts find each other by path.

## 1. Why

The repo root holds 70 tracked files. A newcomer who wants to install on Windows sees Mac shell scripts, Swift
launcher stubs, AutoHotkey sources, three dgVoodoo configs, a 5.8 MB CSV and a folder named `0x501918`. `docs/` holds
94 Markdown files in one flat list. Nothing is wrong with any single file; the cost is in finding the one you need.

## 2. Current layout (tracked files, 2026-10-03)

```
/                         70 files:
  README.md INSTALL.md CHANGELOG.md CONTRIBUTING.md THIRD-PARTY.md LICENSE AGENTS.md CLAUDE.md
  index.html  i76-save-editor.html                  (the GitHub Pages site: public URLs)
  INSTALL.bat  Setup-From-GOG.ps1  install.ps1  setup-windows.ps1          (Windows install chain)
  PLAY-i76.ps1  LAUNCHER.ps1  Setup-FrameGen.ps1  enable-force-feedback.bat  i76-with-remap.bat
  MAKE-PORTABLE.bat  Make-Portable-Zip.ps1
  swap-renderer.ps1  test-drive.ps1                 (2026-07 lab scripts, named by no other script)
  mac-install.command  build-launchers.sh  slim-wrapper.sh  play.sh  fix-arrows-for-mac.sh
  setup-dxwnd.sh setup-music.sh setup-cutscene-music-fix.sh setup-input-remapper.sh setup-mouse-and-pad.sh
  setup-saves.sh setup-nitro.sh setup-voodoo.sh setup-dgvoodoo-cpl.sh        (Mac)
  setup-steamdeck.sh                                (Deck, outside deck/)
  i76-launch-stub.swift i76-nitro-stub.swift i76-settings-stub.swift i76-voodoo-stub.swift
  open-dgvoodoo-settings.command open-dxwnd-settings.command open-pad-diagram.command i76-trainer.command
  i76-remap.ahk i76-ch-fighterstick.ahk i76-cursor-overlay.ahk i76-camsweep.ahk
  i76-opentrack-headlook.ahk i76-opentrack-headlook-test.ahk i76-opentrack-autostart.ahk
  i76-xinput-pad-axistest.ahk i76-xinput-pad-decode.ahk
  i76-save-editor.py i76-save-editor-server.py i76-save-editor.command i76-calibration-saves.py
  dgVoodoo.conf dgVoodoo.windows.conf dgVoodoo.daily-driver-2026-10-03.conf dxvk.conf interstate-76.dxw
  drive5.csv fx.csv lfe-sweep.wav                   (lab output)
  0x501918/                 4 screenshots from one memory experiment
deck/                     24 files  Steam Deck installer, controller layouts, artwork, probes
docs/                     129 files (94 .md flat, asset-bible/ 30, 2 .txt, 2 .svg, input.map.reference)
music-fix/                the Strlkup.dll proxy: source, build script, binary, README (every switch)
u32x/                     the USER32 proxy: source, build, deploy, binary
smack-music-fix/  ffb-shim/  sound-rumble/          three more proxy DLL sources
presets/                  6 .psd1 switch sets for PLAY-i76.ps1
saves/                    55 files: bookmark sets and their installers
tests/                    1 file: save-editor tests
texture-lab/              archived texture scripts
tools/                    105 files: ffb/ (31), trainer/ (10), telemetry/, menu-hd/, bisect/, openglide-hd/,
                          plus about 40 loose scripts (.py, .ahk, .ps1, .sh)
```

`winmm_real.def`, named in the request for this proposal, is not tracked and not on disk at the root today; nothing
to do for it.

## 3. Proposed layout

```
/                         README.md INSTALL.md CHANGELOG.md CONTRIBUTING.md THIRD-PARTY.md LICENSE AGENTS.md CLAUDE.md
                          index.html  i76-save-editor.html        (stay: public URLs)
                          INSTALL.bat  MAKE-PORTABLE.bat            (stay as one-line shims: what a person double-clicks)
windows/                  Setup-From-GOG.ps1 install.ps1 setup-windows.ps1 PLAY-i76.ps1 LAUNCHER.ps1
                          Make-Portable-Zip.ps1 Setup-FrameGen.ps1 enable-force-feedback.bat
mac/                      mac-install.command build-launchers.sh setup-*.sh (the nine Mac ones) slim-wrapper.sh
                          play.sh fix-arrows-for-mac.sh *.swift open-*.command i76-trainer.command
deck/                     + setup-steamdeck.sh
ahk/                      the nine .ahk sources + i76-with-remap.bat
config/                   dgVoodoo*.conf dxvk.conf interstate-76.dxw
save-editor/              i76-save-editor.py i76-save-editor-server.py i76-save-editor.command
                          i76-calibration-saves.py   (tests/ follows)
proxies/                  music-fix/ u32x/ smack-music-fix/ ffb-shim/ sound-rumble/     (optional, last)
presets/  saves/  tools/  texture-lab/                 unchanged
lab-residue/              0x501918/ drive5.csv fx.csv lfe-sweep.wav swap-renderer.ps1 test-drive.ps1
                          (or deleted, the owner's call)
docs/                     README.md (the index), then one folder per topic:
                          status/ framerate/ graphics/ controls/ ffb/ audio/ menus-saves/ platforms/ re/
                          community/ scope/
```

`tools/` could be split the same way (`tools/re/`, `tools/formats/`, `tools/mem-ahk/`); it is left out here because
its loose scripts are named by fewer installers and the gain is smaller. Worth a second proposal once the root is done.

## 4. What constrains the moves

These are the reasons a plain `git mv` breaks things. Each was read from the scripts on 2026-10-03.

1. **Windows scripts resolve siblings from `$PSScriptRoot`.** The install chain is `INSTALL.bat` ->
   `Setup-From-GOG.ps1` -> `install.ps1` -> `setup-windows.ps1`, each calling the next as `Join-Path $repo '<name>'`.
   `setup-windows.ps1` then reads `dgVoodoo.windows.conf`, `saves`, `music-fix\Strlkup.dll`,
   `u32x\deploy-u32x.ps1`, `u32x\u32x.dll`, `i76-remap.ahk`, `i76-ch-fighterstick.ahk`, `PLAY-i76.ps1`, `presets`,
   `tools\i76wheel.exe` from the same folder. Moving the script without moving what it reads needs a
   `$RepoRoot = Split-Path $PSScriptRoot` line and every `Join-Path` re-pointed.
2. **`PLAY-i76.ps1` runs from two places.** In the repo it reads `music-fix\Strlkup.dll`, `presets`,
   `tools\ffb\...` and `tools\i76-music.ps1` beside itself. `setup-windows.ps1`, `Make-Portable-Zip.ps1` and
   `tools\Make-Daily-Driver.ps1` also **copy it into the game folder**, where it reads `presets` and `_ahk\` beside
   itself. Any move must keep both: it already tries `$PSScriptRoot\presets` then `$GameDir\presets`; the same
   two-place lookup is needed for the three repo-only paths. The daily driver built on 2026-10-03 has its own copy
   and is not affected by a repo move.
3. **`Make-Portable-Zip.ps1`** copies `enable-force-feedback.bat`, `i76-save-editor.html`, `PLAY-i76.ps1`,
   `presets`, `Setup-FrameGen.ps1` and three `.ahk` files from `$repo`, and runs `u32x\deploy-u32x.ps1`. It also
   treats its own folder as a possible portable root (`$here\Interstate 76`).
4. **Mac scripts resolve siblings from `$(dirname "$0")`.** `mac-install.command` runs `setup-dxwnd.sh`,
   `setup-music.sh`, `setup-cutscene-music-fix.sh`, `fix-arrows-for-mac.sh`, `build-launchers.sh` and reads
   `docs/input.map.reference`. `build-launchers.sh` compiles the `.swift` stubs beside it. `setup-dxwnd.sh` and
   `setup-music.sh` read `interstate-76.dxw`; `setup-voodoo.sh` reads `dgVoodoo.conf` and `dxvk.conf`;
   `setup-input-remapper.sh` reads three `.ahk` files; `setup-saves.sh` reads `saves/`; `setup-cutscene-music-fix.sh`
   reads `smack-music-fix/SMACKW32.DLL`; `setup-nitro.sh` reads `game-data/`, `docs/input.map.reference`,
   `fix-arrows-for-mac.sh`, `i76-nitro-stub.swift`. The Swift stubs and several `.ahk` files name scripts in their
   comments and messages.
5. **The Deck installer downloads by URL from `main`.** `deck/Install-I76.desktop` fetches
   `raw.githubusercontent.com/.../main/deck/deck-install.sh`, which fetches `$REPO_RAW/deck/<file>` and
   **`$REPO_RAW/dgVoodoo.conf`**. Two consequences: `deck/` must keep its name and the files it fetches, and
   `dgVoodoo.conf` can leave the root only in the same commit that changes `deck-install.sh`. A `.desktop` file
   already copied to someone's Deck keeps working because it fetches the installer fresh; a saved copy of an old
   `deck-install.sh` would not. `deck/deck-push.sh` and `deck/setup-deck-baseline.sh` read `$REPO/i76-remap.ahk`.
6. **GitHub Pages serves the root.** `index.html` and `i76-save-editor.html` are public URLs
   (`therealjkvalentine.github.io/i76-everywhere/i76-save-editor.html` is in the README and INSTALL.md).
   `index.html` links six docs by absolute GitHub URL (`blob/main/docs/<NAME>.md`). Those two HTML files stay at the
   root, and a docs reshuffle must update `index.html` in the same commit.
7. **Tests and tools import by path.** `tests/test_save_editor.py` loads `i76-save-editor.py` from the repo root;
   `i76-calibration-saves.py` and `LAUNCHER.ps1` name it; `tools/pad-diagram.py` reads `i76-remap.ahk` from the
   root and writes `docs/pad-layout*.svg`; `tools/ffb/FfbMixer.ps1` (the owner's uncommitted work) names
   `i76-remap.ahk`.
8. **`AGENTS.md` and the owner's memory notes name paths** (`tools/lint-input-map.py`, `docs/VERIFIED-FIXES.md`,
   `docs/CONTROL-DOCTRINE.md`, ...). A docs move has to update AGENTS.md in the same commit.
9. **Dated records quote paths as they were.** `STATUS-`, `PLAYTEST-`, `BACKLOG-`, `SAVES-LEG-*` and the other
   records should not be rewritten; after a move they will name old paths. One line at the top of `docs/README.md`
   ("paths in records dated before <date> are pre-move; see the move table") covers them.

## 5. Staged order

Each stage is one commit, leaves every entry point working, and can be stopped after. The check after each stage is
the same: `INSTALL.bat` (to the point where it asks for the GOG installer; no game needed), `PLAY-i76.ps1 -Preset ?`
and `-DryRun`, `Make-Portable-Zip.ps1` against a scratch copy, `sh -n` on every moved shell script,
`python -m pytest tests/`, `python tools/pad-diagram.py`, and the Markdown link check used on 2026-10-03 (every
relative link in tracked `.md` files resolves). The Mac and Deck installers cannot be run on this machine: after
stages 3, 4 and 4b they need one run each on the Mac and the Deck before the stage counts as done.

| stage | move | what must change in the same commit | risk |
|---|---|---|---|
| 0 (done 2026-10-03) | untrack `.pyc`, `grep.exe.stackdump`; ignore rules | nothing | none |
| 1 | lab residue -> `lab-residue/` (or delete) | one usage line in `tools/ffb/ffb-watch-effects.ps1` (an example, not a path it opens); docs mentions | none: no script opens these |
| 2 | `.ahk` sources + `i76-with-remap.bat` -> `ahk/` | `setup-windows.ps1`, `Make-Portable-Zip.ps1`, `PLAY-i76.ps1` (repo-side lookups only; the game folder keeps `_ahk\`), `setup-input-remapper.sh`, `deck/deck-push.sh`, `deck/setup-deck-baseline.sh`, `tools/pad-diagram.py`, `open-pad-diagram.command`, `tools/Make-Daily-Driver.ps1`; comments in the stubs and `.ahk` files. `tools/ffb/FfbMixer.ps1` is the owner's uncommitted file: ask first | low on Windows; Mac and Deck need a run |
| 3 | configs -> `config/` | `setup-windows.ps1`, `PLAY-i76.ps1`, `setup-voodoo.sh`, `setup-steamdeck.sh`, `setup-dxwnd.sh`, `setup-music.sh`, `i76-settings-stub.swift`, **`deck/deck-install.sh` (`$REPO_RAW/dgVoodoo.conf` -> `$REPO_RAW/config/dgVoodoo.conf`)**, `deck/install-on-deck.sh` | medium: the Deck fetch is by URL, so this stage is only live once pushed; do not split it across pushes |
| 4 | Mac scripts -> `mac/` | every moved script: `HERE` stays its own folder for sibling scripts, plus `REPO="$(cd "$HERE/.." && pwd)"` for `docs/`, `saves/`, `smack-music-fix/`, `config/`, `ahk/`, `game-data/`; `smack-music-fix/smackproxy.c` comment; `tools/debugmenu.sh`. Leave a root `mac-install.command` that `exec`s `mac/mac-install.command` (it is what a Mac user double-clicks; CONTRIBUTING and the README name it) | medium: untestable here |
| 4b | `setup-steamdeck.sh` -> `deck/` | its `$HERE/dgVoodoo.conf` -> `config/`; `docs/STEAMDECK.md`, `docs/MAC-BUILD.md` | low |
| 5 | Windows scripts -> `windows/`; root `INSTALL.bat` and `MAKE-PORTABLE.bat` become shims (`"%~dp0windows\Setup-From-GOG.ps1"`) | `$repo` / `$repoGameDir` / `$RepoRoot` in `Setup-From-GOG.ps1`, `install.ps1`, `setup-windows.ps1`, `Make-Portable-Zip.ps1`, `LAUNCHER.ps1`, `Setup-FrameGen.ps1` become `Split-Path $PSScriptRoot`; `PLAY-i76.ps1` gets a two-place lookup (constraint 2); `tools/Make-Daily-Driver.ps1`, `tools/ffb/ffb-interposer.ps1`, `music-fix/build.ps1`, `presets/stock.psd1` (comments), `index.html` if it names them | highest: this is the path most users take. Do it alone, after 1 to 4 have settled |
| 6 | save editor `.py` / `.command` -> `save-editor/`; **`.html` stays at the root** | `tests/test_save_editor.py`, `i76-calibration-saves.py`, `LAUNCHER.ps1`, `tools/Make-Daily-Driver.ps1`, `Make-Portable-Zip.ps1` (html path unchanged), `i76-save-editor-server.py` (serves the html: needs the root path), `mac-install.command`, `setup-saves.sh` | low to medium; the test suite covers it |
| 7 | docs into topic folders | about 1,400 path mentions (Appendix B), `AGENTS.md`, `index.html`, `.github/ISSUE_TEMPLATE/*.yml`, `mac-install.command` and three setup scripts that print doc names, `CLAUDE.md` is unaffected. Do it with a script that rewrites links from a move table and re-runs the link check, never by hand | medium: no code breaks, but every doc changes, so it collides with any other session's doc edits. Pick a quiet moment |
| 8 (optional) | proxy folders under `proxies/` | every installer and `PLAY-i76.ps1` (they read `music-fix\Strlkup.dll`, `u32x\...`), `.gitignore` rules, CONTRIBUTING, THIRD-PARTY | little gain for the churn; listed for completeness |

Two cheaper alternatives to stage 7 that keep every link working:

- **Keep `docs/` flat and rely on the index.** `docs/README.md` now lists every doc by topic and marks records
  against living docs. This costs nothing and is already done.
- **Move only the dated records** into `docs/records/` (about 50 files, the rows tagged "record" in `docs/README.md`). Living docs keep their paths, so AGENTS.md,
  `index.html` and the installers' printed doc names are untouched, and the flat list halves.

## 6. Recommendation

Stages 1 and 2, then the "records only" docs move, give most of the benefit (the root drops from 70 files to about
55 and stops looking like a lab bench; `docs/` halves) without moving any installer or launcher (stage 2 edits the paths they read). Stages 3 to 5 are worth
doing only together with a Mac and a Deck test session, and stage 5 only when no installer change is in flight.

## 7. Other clutter noticed (no action taken)

- `LEGITIMACY-AND-SCOPE.md` and `SCOPE-AND-LEGITIMACY.md` overlap (backlog P3-08 already proposes folding them, with
  MAC-SETUP, MODERN-SETUP, WHAT-THIS-IS and `i76-research-full.txt`).
- `docs/READY-TO-TEST.md` is a 2026-08-16 snapshot that RELEASE-PLAN wants folded into VERIFIED-FIXES.
- `tools/` has about 40 loose scripts from the 2026-07 memory-RE push (`i76-*.ahk`, `find-regen-*.py`, `*.sh`
  launchers); several are superseded by the lab's `memlib`.
- Three dgVoodoo configs at the root serve three stacks (Mac / DXVK, Windows installer, the 2026-10-03 daily
  driver). Their header comments say which; a `config/README.md` would say it once.
- `dgVoodoo.conf` (Mac, also fetched by the Deck installer) has `CaptureMouse = false`; `dgVoodoo.windows.conf` has
  `true` (backlog P3-16, still open).
- The working tree usually holds other sessions' uncommitted files. Any move stage should start from a clean
  `git status` apart from the owner's known items.

## Appendix A: every reference to each root file, by proposed move

Generated on 2026-10-03 by a whole-word search for each file name over every tracked text file (the search cannot tell a path from a mention, so read each hit). "code" = scripts, sources and configs that would break; "docs" = Markdown and text that would only go stale. The number in brackets is the count of hits in that file.

### Step 1: lab residue -> `lab-residue/` (or delete after the owner looks)

| file | code that names it | docs that name it |
|---|---|---|
| `0x501918` | none | `docs/BACKLOG-2026-10-02.md` (1), `docs/RELEASE-PLAN.md` (1) |
| `drive5.csv` | none | `docs/BACKLOG-2026-10-02.md` (1), `docs/RELEASE-PLAN.md` (1) |
| `fx.csv` | `tools/ffb/ffb-watch-effects.ps1` (1) | `docs/RELEASE-PLAN.md` (1) |
| `lfe-sweep.wav` | none | `docs/BACKLOG-2026-10-02.md` (1), `docs/RELEASE-PLAN.md` (1) |
| `swap-renderer.ps1` | none | `docs/BACKLOG-2026-10-02.md` (1), `docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md` (2), `docs/RELEASE-PLAN.md` (1), `docs/RENDERER-ALTERNATIVES.md` (1), `tools/openglide-hd/README.md` (3) |
| `test-drive.ps1` | none | `docs/BACKLOG-2026-10-02.md` (1), `docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md` (2), `docs/RELEASE-PLAN.md` (1) |

### Step 2: AutoHotkey sources -> `ahk/`

| file | code that names it | docs that name it |
|---|---|---|
| `i76-remap.ahk` | `Make-Portable-Zip.ps1` (1), `PLAY-i76.ps1` (6), `deck/deck-push.sh` (2), `deck/i76-deck-launch.sh` (4), `deck/setup-deck-baseline.sh` (6), `enable-force-feedback.bat` (1), `i76-ch-fighterstick.ahk` (5), `i76-launch-stub.swift` (2), `i76-nitro-stub.swift` (2), `i76-opentrack-headlook.ahk` (2), `i76-with-remap.bat` (2), `open-pad-diagram.command` (1), `setup-input-remapper.sh` (8), `setup-windows.ps1` (5), `tools/Make-Daily-Driver.ps1` (1), `tools/ffb/FfbMixer.ps1` (2), `tools/pad-diagram.py` (3) | `CHANGELOG.md` (5), `INSTALL.md` (1), `docs/DECK-BASELINE.md` (3), `docs/ENHANCEMENTS.md` (5), `docs/FFB-MORNING-TEST.md` (1), `docs/FFB-STACKS.md` (2), `docs/FIGHTERSTICK.md` (4), `docs/INPUT-REMAPPER.md` (5), `docs/NEW-DAILY-DRIVER-RECIPE.md` (4), `docs/RELEASE-PLAN.md` (2), `docs/VERIFIED-FIXES.md` (4), `docs/WHEEL-T300.md` (4), `tools/ffb/README.md` (2) |
| `i76-ch-fighterstick.ahk` | `Make-Portable-Zip.ps1` (1), `PLAY-i76.ps1` (2), `i76-remap.ahk` (1), `setup-windows.ps1` (1) | `docs/ENHANCEMENTS.md` (2), `docs/FIGHTERSTICK.md` (8), `docs/NEW-DAILY-DRIVER-RECIPE.md` (2), `docs/RELEASE-PLAN.md` (1) |
| `i76-cursor-overlay.ahk` | `PLAY-i76.ps1` (2) | `docs/ENHANCEMENTS.md` (2), `docs/MENU-REBUILD-DESIGN.md` (2), `docs/MENU-USABILITY-PLAN.md` (3), `docs/NEW-DAILY-DRIVER-RECIPE.md` (4) |
| `i76-opentrack-headlook.ahk` | `Make-Portable-Zip.ps1` (2), `PLAY-i76.ps1` (2), `i76-ch-fighterstick.ahk` (1), `i76-opentrack-headlook-test.ahk` (1) | `docs/ENHANCEMENTS.md` (2), `docs/FIGHTERSTICK.md` (1), `docs/HEAD-TRACKING.md` (3), `docs/NEW-DAILY-DRIVER-RECIPE.md` (1), `docs/RELEASE-PLAN.md` (1) |
| `i76-opentrack-headlook-test.ahk` | `Make-Portable-Zip.ps1` (2) | `docs/ENHANCEMENTS.md` (2), `docs/HEAD-TRACKING.md` (2), `docs/NEW-DAILY-DRIVER-RECIPE.md` (1) |
| `i76-opentrack-autostart.ahk` | `PLAY-i76.ps1` (3) | `docs/ENHANCEMENTS.md` (2), `docs/NEW-DAILY-DRIVER-RECIPE.md` (1), `docs/RELEASE-PLAN.md` (1) |
| `i76-camsweep.ahk` | none | `docs/ENHANCEMENTS.md` (2), `docs/NEW-DAILY-DRIVER-RECIPE.md` (1) |
| `i76-xinput-pad-axistest.ahk` | `i76-ch-fighterstick.ahk` (2), `setup-input-remapper.sh` (3) | none |
| `i76-xinput-pad-decode.ahk` | `setup-input-remapper.sh` (3) | none |
| `i76-with-remap.bat` | `PLAY-i76.ps1` (1), `setup-input-remapper.sh` (1) | `docs/BACKLOG-2026-10-02.md` (1), `docs/ENHANCEMENTS.md` (2), `docs/INPUT-REMAPPER.md` (3), `docs/RELEASE-PLAN.md` (1) |

### Step 3: renderer and wrapper configs -> `config/`

| file | code that names it | docs that name it |
|---|---|---|
| `dgVoodoo.conf` | `LAUNCHER.ps1` (6), `Make-Portable-Zip.ps1` (3), `PLAY-i76.ps1` (1), `Setup-FrameGen.ps1` (1), `deck/deck-install.sh` (6), `deck/install-on-deck.sh` (3), `dgVoodoo.daily-driver-2026-10-03.conf` (1), `dgVoodoo.windows.conf` (1), `i76-voodoo-stub.swift` (3), `open-dgvoodoo-settings.command` (1), `presets/best-120.psd1` (1), `setup-dgvoodoo-cpl.sh` (1), `setup-steamdeck.sh` (4), `setup-voodoo.sh` (4), `setup-windows.ps1` (6), `tools/Make-Daily-Driver.ps1` (6), `tools/bisect/LAYERS.ps1` (6), `tools/cursor-mode.ps1` (3), `tools/ffb-recon.ps1` (1) | `AGENTS.md` (3), `CHANGELOG.md` (1), `INSTALL.md` (2), `docs/BACKLOG-2026-10-02.md` (7), `docs/DOC-CORRECTIONS-PENDING-SIBLINGS.md` (5), `docs/DXGI-DGVOODOO-RESEARCH.md` (2), `docs/ENHANCEMENTS.md` (1), `docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md` (2), `docs/FPS-120.md` (7), `docs/FRESH-START-METHOD.md` (2), `docs/GRAPHICS-ENHANCEMENT.md` (9), `docs/MAC-BUILD.md` (2), `docs/MENU-REBUILD-DESIGN.md` (1), `docs/MENU-USABILITY-PLAN.md` (5), `docs/NEW-DAILY-DRIVER-RECIPE.md` (10), `docs/PHONE-PORTS.md` (5), `docs/README.md` (1), `docs/RELEASE-PLAN.md` (3), `docs/RENDERER-ALTERNATIVES.md` (7), `docs/SAVE-FREEZE-ROOT-CAUSE.md` (1), `docs/SAVES-LEG-A-RUN-2026-10-01.md` (1), `docs/SAVES-LEG-B-RUN-2026-10-01.md` (1), `docs/SAVES-STATE-AND-TEST-PLAN.md` (3), `docs/STATUS-2026-10-02.md` (2), `docs/STEAMDECK.md` (12), `docs/VERIFIED-FIXES.md` (1), `docs/VISUAL-QUALITY-MAC.md` (4), `docs/VOODOO-PARKED.md` (2), `docs/WHAT-THIS-IS-dgvoodoo.txt` (1), `docs/WINDOWS-PLAYBOOK.md` (1), `docs/i76-research-full.txt` (14), `music-fix/README.md` (1), `tools/bisect/README.md` (1) |
| `dgVoodoo.windows.conf` | `PLAY-i76.ps1` (1), `setup-windows.ps1` (3) | `docs/BACKLOG-2026-10-02.md` (3), `docs/ENHANCEMENTS.md` (2), `docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md` (2), `docs/MENU-USABILITY-PLAN.md` (2), `docs/NEW-DAILY-DRIVER-RECIPE.md` (2), `docs/RELEASE-PLAN.md` (1), `docs/WINDOWS-PLAYBOOK.md` (2) |
| `dgVoodoo.daily-driver-2026-10-03.conf` | none | `CHANGELOG.md` (1), `docs/ENHANCEMENTS.md` (2), `docs/NEW-DAILY-DRIVER-RECIPE.md` (2), `docs/RELEASE-PLAN.md` (1), `docs/STATUS-2026-10-02.md` (1) |
| `dxvk.conf` | `deck/deck-install.sh` (1), `i76-voodoo-stub.swift` (1), `setup-voodoo.sh` (4) | `docs/DECK-INPUT-SCIENCE.md` (1), `docs/DXGI-DGVOODOO-RESEARCH.md` (1), `docs/MAC-BUILD.md` (1), `docs/RENDERER-ALTERNATIVES.md` (5), `docs/VOODOO-PARKED.md` (3) |
| `interstate-76.dxw` | `i76-settings-stub.swift` (1), `setup-dxwnd.sh` (2), `setup-music.sh` (1) | `docs/ENHANCEMENTS.md` (2), `docs/MAC-BUILD.md` (3), `docs/RELEASE-PLAN.md` (2), `docs/VERIFIED-FIXES.md` (3) |

### Step 4: Mac scripts -> `mac/`

| file | code that names it | docs that name it |
|---|---|---|
| `mac-install.command` | none | `CHANGELOG.md` (1), `CONTRIBUTING.md` (1), `docs/BACKLOG-2026-10-02.md` (1), `docs/ENHANCEMENTS.md` (3), `docs/RELEASE-PLAN.md` (3) |
| `build-launchers.sh` | `mac-install.command` (1), `setup-input-remapper.sh` (1), `setup-voodoo.sh` (1) | `docs/ENHANCEMENTS.md` (2), `docs/MAC-BUILD.md` (2), `docs/RELEASE-PLAN.md` (3), `docs/VERIFIED-FIXES.md` (2), `docs/VISUAL-QUALITY-MAC.md` (2), `docs/VOODOO-PARKED.md` (2) |
| `setup-dxwnd.sh` | `mac-install.command` (1) | `docs/MAC-BUILD.md` (4), `docs/RELEASE-PLAN.md` (1), `docs/VERIFIED-FIXES.md` (2) |
| `setup-music.sh` | `mac-install.command` (1) | `docs/ENHANCEMENTS.md` (2), `docs/MAC-BUILD.md` (4), `docs/MUSIC-TRACK-MAP.md` (1), `docs/PHONE-PORTS.md` (2), `docs/PORTING-WINDOWS-WINS-TO-MAC.md` (1), `docs/RELEASE-PLAN.md` (1), `docs/STEAMDECK.md` (2), `docs/VERIFIED-FIXES.md` (3) |
| `setup-cutscene-music-fix.sh` | `mac-install.command` (1), `setup-nitro.sh` (1), `smack-music-fix/smackproxy.c` (1) | `docs/ENHANCEMENTS.md` (2), `docs/RELEASE-PLAN.md` (1), `docs/VERIFIED-FIXES.md` (3), `smack-music-fix/README.md` (1) |
| `setup-input-remapper.sh` | `deck/setup-deck-baseline.sh` (1), `i76-launch-stub.swift` (1), `i76-remap.ahk` (1), `i76-xinput-pad-axistest.ahk` (1), `i76-xinput-pad-decode.ahk` (1), `tools/debugmenu.sh` (2) | `docs/ENHANCEMENTS.md` (2), `docs/FIND-WHAT-WRITES.md` (1), `docs/INPUT-REMAPPER.md` (5), `docs/RELEASE-PLAN.md` (1), `docs/VERIFIED-FIXES.md` (4) |
| `setup-mouse-and-pad.sh` | `setup-steamdeck.sh` (1), `setup-windows.ps1` (1) | `docs/ENHANCEMENTS.md` (4), `docs/MAC-BUILD.md` (2), `docs/PORTING-WINDOWS-WINS-TO-MAC.md` (1), `docs/STEAMDECK.md` (6), `docs/VERIFIED-FIXES.md` (2), `docs/WINDOWS-PLAYBOOK.md` (2) |
| `setup-saves.sh` | `i76-save-editor.py` (2), `mac-install.command` (1) | none |
| `setup-nitro.sh` | none | none |
| `setup-voodoo.sh` | `i76-voodoo-stub.swift` (1) | `docs/VOODOO-PARKED.md` (2) |
| `setup-dgvoodoo-cpl.sh` | `open-dgvoodoo-settings.command` (2) | `docs/VOODOO-PARKED.md` (2) |
| `slim-wrapper.sh` | none | `docs/MAC-BUILD.md` (2), `docs/RELEASE-PLAN.md` (1), `docs/VOODOO-PARKED.md` (3) |
| `fix-arrows-for-mac.sh` | `mac-install.command` (1), `setup-nitro.sh` (1) | `docs/ENHANCEMENTS.md` (2), `docs/MAC-BUILD.md` (4), `docs/PORTING-WINDOWS-WINS-TO-MAC.md` (1), `docs/RELEASE-PLAN.md` (2), `docs/VERIFIED-FIXES.md` (2) |
| `play.sh` | none | `docs/DXGI-DGVOODOO-RESEARCH.md` (1), `texture-lab/README.md` (1) |
| `i76-launch-stub.swift` | `build-launchers.sh` (1), `i76-nitro-stub.swift` (1), `setup-input-remapper.sh` (1) | `docs/DXGI-DGVOODOO-RESEARCH.md` (2), `docs/INPUT-REMAPPER.md` (2), `docs/MAC-BUILD.md` (1), `docs/SAVE-EDITOR-STATUS-2026-10-02.md` (1), `docs/SAVE-ORPHAN-INVESTIGATION.md` (1), `docs/SAVES-STATE-AND-TEST-PLAN.md` (1), `docs/VERIFIED-FIXES.md` (4) |
| `i76-nitro-stub.swift` | `setup-nitro.sh` (1) | none |
| `i76-settings-stub.swift` | `build-launchers.sh` (1) | `docs/MAC-BUILD.md` (1) |
| `i76-voodoo-stub.swift` | `build-launchers.sh` (1), `dgVoodoo.daily-driver-2026-10-03.conf` (1), `dgVoodoo.windows.conf` (1) | `docs/MAC-BUILD.md` (1), `docs/VISUAL-QUALITY-MAC.md` (4), `docs/VOODOO-PARKED.md` (3) |
| `open-dgvoodoo-settings.command` | `setup-dgvoodoo-cpl.sh` (2) | `docs/VISUAL-QUALITY-MAC.md` (2), `docs/VOODOO-PARKED.md` (2) |
| `open-dxwnd-settings.command` | none | none |
| `open-pad-diagram.command` | `tools/pad-diagram.py` (1) | `README.md` (1), `docs/ENHANCEMENTS.md` (2) |
| `i76-trainer.command` | none | none |

### Step 4b: `setup-steamdeck.sh` -> `deck/`

| file | code that names it | docs that name it |
|---|---|---|
| `setup-steamdeck.sh` | none | `docs/MAC-BUILD.md` (2), `docs/STEAMDECK.md` (2) |

### Step 5: Windows scripts -> `windows/` (root keeps `INSTALL.bat` and `MAKE-PORTABLE.bat` as one-line shims)

| file | code that names it | docs that name it |
|---|---|---|
| `Setup-From-GOG.ps1` | `Make-Portable-Zip.ps1` (1), `setup-windows.ps1` (1) | `INSTALL.md` (6), `docs/BACKLOG-2026-10-02.md` (1), `docs/ENHANCEMENTS.md` (2), `docs/RELEASE-PLAN.md` (5) |
| `setup-windows.ps1` | `PLAY-i76.ps1` (5), `Setup-From-GOG.ps1` (1), `dgVoodoo.daily-driver-2026-10-03.conf` (3), `dgVoodoo.windows.conf` (3), `install.ps1` (3), `music-fix/build.ps1` (1) | `CHANGELOG.md` (3), `CONTRIBUTING.md` (1), `README.md` (1), `THIRD-PARTY.md` (1), `docs/BACKLOG-2026-10-02.md` (2), `docs/ENHANCEMENTS.md` (6), `docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md` (4), `docs/MAC-BUILD.md` (2), `docs/RELEASE-PLAN.md` (3), `docs/SOUND-INTERPOSER-REVIEW.md` (1), `docs/WHEEL-T300.md` (2), `docs/WINDOWS-PLAYBOOK.md` (2), `music-fix/README.md` (1), `u32x/README.md` (2) |
| `install.ps1` | `Make-Portable-Zip.ps1` (1), `Setup-From-GOG.ps1` (3), `index.html` (1), `setup-windows.ps1` (1) | `CHANGELOG.md` (2), `docs/ENHANCEMENTS.md` (1), `docs/HD-TEXTURES-RESEARCH.md` (1), `docs/RELEASE-PLAN.md` (5), `texture-lab/README.md` (1) |
| `PLAY-i76.ps1` | `LAUNCHER.ps1` (9), `Make-Portable-Zip.ps1` (4), `Setup-FrameGen.ps1` (1), `presets/stock.psd1` (1), `setup-windows.ps1` (4), `tools/Make-Daily-Driver.ps1` (9), `tools/ffb/ffb-interposer.ps1` (1) | `CHANGELOG.md` (4), `README.md` (1), `THIRD-PARTY.md` (1), `docs/BACKLOG-2026-10-02.md` (5), `docs/ENHANCEMENTS.md` (15), `docs/MENU-USABILITY-PLAN.md` (11), `docs/MUSIC.md` (1), `docs/NEW-DAILY-DRIVER-RECIPE.md` (10), `docs/RELEASE-PLAN.md` (10), `docs/RENDERER-ALTERNATIVES.md` (2), `docs/SAVE-EDITOR-STATUS-2026-10-02.md` (1), `docs/SAVE-FREEZE-ROOT-CAUSE.md` (2), `docs/SAVES-STATE-AND-TEST-PLAN.md` (5), `docs/SOUND-INTERPOSER-REVIEW.md` (1), `docs/STATUS-2026-10-02.md` (1), `docs/VERIFIED-FIXES.md` (1), `docs/WHEEL-T300.md` (1), `docs/WINDOWS-PLAYBOOK.md` (2), `saves/README.md` (1), `saves/windows-20260906/README.md` (1), `tools/ffb/README.md` (1) |
| `LAUNCHER.ps1` | none | `CHANGELOG.md` (4), `README.md` (1), `docs/BACKLOG-2026-10-02.md` (6), `docs/DOC-CORRECTIONS-PENDING-SIBLINGS.md` (2), `docs/ENHANCEMENTS.md` (4), `docs/MENU-USABILITY-PLAN.md` (5), `docs/RELEASE-PLAN.md` (5), `docs/SAVES-STATE-AND-TEST-PLAN.md` (1), `u32x/README.md` (1) |
| `Make-Portable-Zip.ps1` | `Setup-From-GOG.ps1` (1) | `CHANGELOG.md` (1), `INSTALL.md` (1), `THIRD-PARTY.md` (3), `docs/BACKLOG-2026-10-02.md` (1), `docs/ENHANCEMENTS.md` (2), `docs/NEW-DAILY-DRIVER-RECIPE.md` (1), `docs/RELEASE-PLAN.md` (4), `u32x/README.md` (1) |
| `Setup-FrameGen.ps1` | `Make-Portable-Zip.ps1` (3), `tools/Make-Daily-Driver.ps1` (1) | `CHANGELOG.md` (2), `THIRD-PARTY.md` (1), `docs/ENHANCEMENTS.md` (2), `docs/FRAMERATE-UNCAP-RESEARCH.md` (2), `docs/NEW-DAILY-DRIVER-RECIPE.md` (1), `docs/RELEASE-PLAN.md` (3), `docs/RENDERER-ALTERNATIVES.md` (2), `docs/WINDOWS-PLAYBOOK.md` (2) |
| `enable-force-feedback.bat` | `Make-Portable-Zip.ps1` (3), `setup-steamdeck.sh` (2), `setup-windows.ps1` (2), `tools/check-ffb.ps1` (2) | `INSTALL.md` (1), `docs/ENHANCEMENTS.md` (3), `docs/FFB-LAPTOP-RECON.md` (1), `docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md` (2), `docs/MAC-BUILD.md` (2), `docs/NEW-DAILY-DRIVER-RECIPE.md` (3), `docs/RELEASE-PLAN.md` (3), `docs/STEAMDECK.md` (4), `docs/VERIFIED-FIXES.md` (2), `docs/WHEEL-T300.md` (3), `docs/WINDOWS-PLAYBOOK.md` (4) |
| `INSTALL.bat` | `Setup-From-GOG.ps1` (1) | `INSTALL.md` (1), `docs/BACKLOG-2026-10-02.md` (1), `docs/ENHANCEMENTS.md` (2), `docs/RELEASE-PLAN.md` (4) |
| `MAKE-PORTABLE.bat` | none | `INSTALL.md` (1), `docs/ENHANCEMENTS.md` (2), `docs/RELEASE-PLAN.md` (2) |

### Step 6: save editor -> `save-editor/` (the `.html` stays at the root, or leaves a redirect: it is a public URL)

| file | code that names it | docs that name it |
|---|---|---|
| `i76-save-editor.py` | `LAUNCHER.ps1` (1), `i76-calibration-saves.py` (2), `i76-save-editor.html` (3), `tests/test_save_editor.py` (2), `tools/Make-Daily-Driver.ps1` (2) | `AGENTS.md` (1), `README.md` (3), `docs/EDITOR-FIELD-TESTS.md` (3), `docs/ENHANCEMENTS.md` (2), `docs/GHIDRA-MEMORY-MAP.md` (2), `docs/MENU-REBUILD-DESIGN.md` (1), `docs/NEW-DAILY-DRIVER-RECIPE.md` (2), `docs/README.md` (2), `docs/READY-TO-TEST.md` (1), `docs/RELEASE-PLAN.md` (2), `docs/SAVE-EDITOR-STATUS-2026-10-02.md` (2), `docs/SAVES-LEG-B-RUN-2026-10-01.md` (1), `docs/SAVES-STATE-AND-TEST-PLAN.md` (6), `docs/STATUS-2026-10-02.md` (1), `saves/README.md` (5), `saves/rescue-20260718/README.md` (1) |
| `i76-save-editor-server.py` | `i76-save-editor.command` (1), `i76-save-editor.html` (3) | `docs/MENU-REBUILD-DESIGN.md` (1), `docs/RELEASE-PLAN.md` (1) |
| `i76-save-editor.command` | `i76-save-editor-server.py` (1), `i76-save-editor.html` (2), `mac-install.command` (1) | `README.md` (1), `docs/ENHANCEMENTS.md` (2), `docs/README.md` (2), `docs/READY-TO-TEST.md` (1), `docs/RELEASE-PLAN.md` (1) |
| `i76-calibration-saves.py` | `i76-save-editor.py` (1), `tests/test_save_editor.py` (1) | `docs/EDITOR-FIELD-TESTS.md` (2), `docs/ENHANCEMENTS.md` (2), `docs/RELEASE-PLAN.md` (1), `docs/SAVE-EDITOR-STATUS-2026-10-02.md` (2), `docs/SAVES-STATE-AND-TEST-PLAN.md` (2), `docs/STATUS-2026-10-02.md` (1), `saves/README.md` (1) |
| `i76-save-editor.html` | `Make-Portable-Zip.ps1` (2), `i76-save-editor-server.py` (3), `index.html` (1), `tools/Make-Daily-Driver.ps1` (1) | `INSTALL.md` (2), `README.md` (3), `docs/BACKLOG-2026-10-02.md` (1), `docs/EDITOR-FIELD-TESTS.md` (1), `docs/ENHANCEMENTS.md` (3), `docs/MENU-REBUILD-DESIGN.md` (1), `docs/NEW-DAILY-DRIVER-RECIPE.md` (2), `docs/PHONE-PORTS.md` (3), `docs/README.md` (2), `docs/READY-TO-TEST.md` (1), `docs/RELEASE-PLAN.md` (4), `docs/SAVE-EDITOR-STATUS-2026-10-02.md` (2), `docs/SAVES-LEG-B-RUN-2026-10-01.md` (1), `docs/SAVES-STATE-AND-TEST-PLAN.md` (2) |
| `index.html` | `i76-save-editor-server.py` (1), `tools/parse-asset-bible.py` (1) | `docs/RELEASE-PLAN.md` (4) (other hits are other sites' `index.html`, not this file) |

## Appendix B: docs by topic, with inbound references

Proposed folder per doc (the grouping of `docs/README.md`), and how many places name the file today. "links" counts Markdown links and backticked paths in tracked text files; each would need its path changed.

| doc | proposed folder | named in (files) | hits |
|---|---|---|---|
| `ENHANCEMENTS.md` | `docs/status/` | 1 | 2 |
| `VERIFIED-FIXES.md` | `docs/status/` | 25 ; code: `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/config.yml`, `index.html`, `mac-install.command`, `setup-mouse-and-pad.sh`, `setup-music.sh`, `setup-windows.ps1`, `tools/lint-input-map.py` | 63 |
| `RELEASE-PLAN.md` | `docs/status/` | 9 ; code: `presets/stock.psd1` | 49 |
| `BACKLOG-2026-10-02.md` | `docs/status/` | 6 | 11 |
| `STATUS-2026-10-02.md` | `docs/status/` | 9 | 31 |
| `PLAYTEST-2026-10-02.md` | `docs/status/` | 5 | 12 |
| `NEW-DAILY-DRIVER-RECIPE.md` | `docs/status/` | 9 ; code: `tools/Make-Daily-Driver.ps1` | 16 |
| `DOC-CORRECTIONS-PENDING-SIBLINGS.md` | `docs/status/` | 3 | 5 |
| `READY-TO-TEST.md` | `docs/status/` | 5 | 11 |
| `REPO-ORGANIZATION-PROPOSAL.md` | `docs/status/` | 3 | 5 |
| `PARALLEL-SESSIONS.md` | `docs/status/` | 0 | 0 |
| `OUTREACH-DRAFT.md` | `docs/status/` | 1 | 4 |
| `FPS-120.md` | `docs/framerate/` | 14 ; code: `music-fix/strlkproxy.c`, `presets/smooth-120.psd1` | 44 |
| `FRAMERATE-COVERAGE-2026-10-02.md` | `docs/framerate/` | 6 ; code: `music-fix/strlkproxy.c` | 23 |
| `PER-FRAME-AUDIT-2026-10-03.md` | `docs/framerate/` | 5 ; code: `music-fix/strlkproxy.c` | 20 |
| `FRAMERATE-UNCAP-RESEARCH.md` | `docs/framerate/` | 7 | 12 |
| `HANDLING-MODEL.md` | `docs/framerate/` | 5 ; code: `tools/ffb/FfbMixer.ps1`, `tools/ffb/ffb-find-slip.ps1`, `tools/ffb/ffb-telemetry-udp.ps1` | 11 |
| `HEALTH-BAR-COLOUR.md` | `docs/framerate/` | 10 ; code: `music-fix/strlkproxy.c`, `presets/smooth-60-bugfixes.psd1`, `tools/trainer/tests/health_pct_live_test.py` | 16 |
| `GRAPHICS-ENHANCEMENT.md` | `docs/graphics/` | 8 ; code: `dgVoodoo.daily-driver-2026-10-03.conf` | 18 |
| `RENDERER-ALTERNATIVES.md` | `docs/graphics/` | 14 | 32 |
| `DRAW-DISTANCE.md` | `docs/graphics/` | 12 ; code: `music-fix/strlkproxy.c`, `tools/trainer/tunables.json` | 32 |
| `FARCLIP-CAMERA-CRASH.md` | `docs/graphics/` | 11 ; code: `music-fix/strlkproxy.c`, `presets/lab-all.psd1` | 26 |
| `MENU-HD-ART.md` | `docs/graphics/` | 1 | 4 |
| `HD-TEXTURES-RESEARCH.md` | `docs/graphics/` | 13 ; code: `install.ps1` | 32 |
| `VOODOO-PARKED.md` | `docs/graphics/` | 10 ; code: `build-launchers.sh`, `slim-wrapper.sh` | 18 |
| `VISUAL-QUALITY-MAC.md` | `docs/graphics/` | 4 ; code: `open-dgvoodoo-settings.command` | 9 |
| `DXGI-DGVOODOO-RESEARCH.md` | `docs/graphics/` | 12 ; code: `i76-voodoo-stub.swift`, `setup-voodoo.sh` | 23 |
| `DXWND-TUNING.md` | `docs/graphics/` | 5 ; code: `i76-settings-stub.swift` | 11 |
| `MODERN-PORTS-AND-VR.md` | `docs/graphics/` | 4 | 10 |
| `CONTROL-DOCTRINE.md` | `docs/controls/` | 7 ; code: `deck/setup-deck-baseline.sh` | 15 |
| `GAMEPAD-PC-MAC.md` | `docs/controls/` | 8 ; code: `i76-ch-fighterstick.ahk` | 16 |
| `INPUT-REMAPPER.md` | `docs/controls/` | 8 ; code: `i76-opentrack-headlook.ahk`, `i76-remap.ahk`, `i76-with-remap.bat`, `setup-input-remapper.sh` | 14 |
| `input.map.reference` | `docs/controls/` | 11 ; code: `deck/setup-deck-baseline.sh`, `i76-remap.ahk`, `mac-install.command`, `setup-nitro.sh`, `setup-windows.ps1`, `tools/i76-joyprobe.py` | 17 |
| `pad-layout.svg` | `docs/controls/` | 2 ; code: `tools/pad-diagram.py` | 2 |
| `pad-layout-shift.svg` | `docs/controls/` | 2 ; code: `tools/pad-diagram.py` | 2 |
| `FIGHTERSTICK.md` | `docs/controls/` | 7 ; code: `PLAY-i76.ps1`, `i76-ch-fighterstick.ahk`, `i76-remap.ahk` | 11 |
| `WHEEL-T300.md` | `docs/controls/` | 11 ; code: `PLAY-i76.ps1`, `i76-remap.ahk`, `tools/ffb-recon.ps1`, `tools/ffb/ffb-interposer.ps1`, `tools/lint-input-map.py` | 22 |
| `HEAD-TRACKING.md` | `docs/controls/` | 8 ; code: `i76-opentrack-autostart.ahk`, `i76-opentrack-headlook-test.ahk`, `i76-opentrack-headlook.ahk` | 20 |
| `I76-GAMEPLAY-REFERENCE.md` | `docs/controls/` | 6 ; code: `dgVoodoo.daily-driver-2026-10-03.conf`, `dgVoodoo.windows.conf` | 10 |
| `DECK-CONTROLS.md` | `docs/controls/` | 2 | 3 |
| `DECK-INPUT-SCIENCE.md` | `docs/controls/` | 6 | 14 |
| `STEAMDECK-INPUT-MODES.md` | `docs/controls/` | 2 | 6 |
| `DECK-BASELINE.md` | `docs/controls/` | 6 ; code: `deck/setup-deck-baseline.sh` | 11 |
| `FFB-STACKS.md` | `docs/ffb/` | 5 | 14 |
| `FFB-DEEP-DIVE.md` | `docs/ffb/` | 11 ; code: `tools/ffb-udp-listen.py`, `tools/i76-addresses.json`, `tools/i76-ffb-monitor.ahk` | 31 |
| `FFB-DESIGN-LIBRARY.md` | `docs/ffb/` | 4 | 7 |
| `FFB-DATA-AUDIT.md` | `docs/ffb/` | 4 ; code: `music-fix/strlkproxy.c`, `tools/telemetry/i76tel.h` | 8 |
| `FFB-LAPTOP-RECON.md` | `docs/ffb/` | 12 ; code: `tools/ffb-recon.ps1`, `tools/ffb/Telemetry.ps1`, `tools/ffb/ffb-coexist-test.ps1`, `tools/ffb/ffb-interposer.ps1`, `tools/i76-music.ps1` | 20 |
| `FFB-MORNING-TEST.md` | `docs/ffb/` | 2 | 4 |
| `FORCE-FEEDBACK-AND-VISUALS.md` | `docs/ffb/` | 7 ; code: `enable-force-feedback.bat` | 15 |
| `SIM-RUMBLE-RESEARCH.md` | `docs/ffb/` | 4 ; code: `ffb-shim/i7ffshim.c` | 6 |
| `MOTION-SIM.md` | `docs/ffb/` | 7 ; code: `tools/ffb-udp-listen.py`, `tools/i76-ffb-monitor.ahk` | 13 |
| `SOUND-INTERPOSER-REVIEW.md` | `docs/ffb/` | 1 | 2 |
| `MUSIC.md` | `docs/audio/` | 7 ; code: `PLAY-i76.ps1`, `tools/cdaudio-image/probe-cdaudio.ps1` | 29 |
| `MUSIC-TRACK-MAP.md` | `docs/audio/` | 4 ; code: `music-fix/strlkproxy.c`, `tools/i76-trainer.ahk` | 9 |
| `SAVE-FREEZE-ROOT-CAUSE.md` | `docs/menus-saves/` | 10 ; code: `u32x/u32x_min.c` | 19 |
| `SHELL-MENU-AND-SAVE-FREEZE.md` | `docs/menus-saves/` | 4 | 8 |
| `MENU-USABILITY-PLAN.md` | `docs/menus-saves/` | 5 | 24 |
| `MENU-REBUILD-DESIGN.md` | `docs/menus-saves/` | 3 | 6 |
| `SAVES-STATE-AND-TEST-PLAN.md` | `docs/menus-saves/` | 5 | 19 |
| `SAVES-LEG-A-RUN-2026-10-01.md` | `docs/menus-saves/` | 4 | 6 |
| `SAVES-LEG-B-RUN-2026-10-01.md` | `docs/menus-saves/` | 3 | 4 |
| `SAVE-ORPHAN-INVESTIGATION.md` | `docs/menus-saves/` | 3 | 5 |
| `SAVE-FORMAT-GAPS.md` | `docs/menus-saves/` | 12 | 27 |
| `SAVE-EDITOR-STATUS-2026-10-02.md` | `docs/menus-saves/` | 10 ; code: `i76-save-editor.html`, `i76-save-editor.py`, `tests/test_save_editor.py` | 16 |
| `EDITOR-FIELD-TESTS.md` | `docs/menus-saves/` | 8 ; code: `i76-calibration-saves.py` | 15 |
| `MOUNT-VALIDATION.md` | `docs/menus-saves/` | 6 ; code: `i76-save-editor.py` | 12 |
| `MISSION-LAUNCH.md` | `docs/menus-saves/` | 6 ; code: `PLAY-i76.ps1` | 13 |
| `MAC-BUILD.md` | `docs/platforms/` | 8 ; code: `index.html`, `mac-install.command`, `setup-nitro.sh` | 16 |
| `MAC-SETUP.md` | `docs/platforms/` | 3 | 5 |
| `PORTING-WINDOWS-WINS-TO-MAC.md` | `docs/platforms/` | 0 | 0 |
| `STEAMDECK.md` | `docs/platforms/` | 11 ; code: `PLAY-i76.ps1`, `deck/deck-install.sh`, `index.html`, `setup-steamdeck.sh` | 20 |
| `WINDOWS-PLAYBOOK.md` | `docs/platforms/` | 15 ; code: `Make-Portable-Zip.ps1`, `Setup-FrameGen.ps1`, `index.html`, `setup-windows.ps1` | 29 |
| `FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md` | `docs/platforms/` | 8 ; code: `swap-renderer.ps1` | 15 |
| `MODERN-SETUP.md` | `docs/platforms/` | 6 | 8 |
| `WHAT-THIS-IS-dgvoodoo.txt` | `docs/platforms/` | 3 | 4 |
| `RUNNING-I76-EVERYWHERE.md` | `docs/platforms/` | 2 | 3 |
| `i76-research-full.txt` | `docs/platforms/` | 3 | 4 |
| `PHONE-PORTS.md` | `docs/platforms/` | 5 ; code: `index.html` | 7 |
| `MEMORY-MAP-INDEX.md` | `docs/re/` | 21 ; code: `tools/ffb-udp-listen.py`, `tools/ffb/Telemetry.ps1`, `tools/ffb/ffb-find-fire.ps1`, `tools/i76-addresses.json`, `tools/i76-debugmenu.ahk`, `tools/i76-trainer.ahk` | 38 |
| `GHIDRA-MEMORY-MAP.md` | `docs/re/` | 13 ; code: `.gitignore`, `i76-camsweep.ahk`, `i76-opentrack-headlook.ahk`, `tools/ffb/ffb-find-rpm.ps1`, `tools/ffb/ffb-telemetry-probe.ps1`, `tools/i76-rearm.ahk` | 19 |
| `STATIC-RE-FABLE.md` | `docs/re/` | 5 ; code: `tools/i76-worldscan.ahk` | 7 |
| `MW2-I76-STRUCTS.md` | `docs/re/` | 6 ; code: `.gitignore` | 9 |
| `LEVEL-FORMAT.md` | `docs/re/` | 1 | 4 |
| `WEAPON-STATS.md` | `docs/re/` | 4 | 10 |
| `MODDING-GUIDE.md` | `docs/re/` | 5 | 11 |
| `FRESH-START-2026-09-04.md` | `docs/re/` | 6 | 8 |
| `FRESH-START-METHOD.md` | `docs/re/` | 2 | 8 |
| `RE-METHODOLOGY.md` | `docs/re/` | 8 ; code: `tools/ffb/ffb-find-rpm-wide.ps1` | 16 |
| `RE-FIELD-GUIDE.md` | `docs/re/` | 3 | 5 |
| `RE-RESOURCES.md` | `docs/re/` | 3 | 5 |
| `FIND-WHAT-WRITES.md` | `docs/re/` | 3 ; code: `tools/setup-debugger.sh` | 5 |
| `DEBUG-MENU-FIELD-TEST.md` | `docs/re/` | 4 | 8 |
| `COMMUNITY-RESOURCES.md` | `docs/community/` | 40 ; code: `tools/asset-bible-to-md.py`, `tools/parse-asset-bible.py` | 83 |
| `COMMUNITY-SITEMAP.md` | `docs/community/` | 3 | 5 |
| `ASSET-BIBLE.md` | `docs/community/` | 5 ; code: `tools/parse-asset-bible.py` | 8 |
| `asset-bible` | `docs/community/` | 3 | 6 |
| `SCOPE-AND-LEGITIMACY.md` | `docs/scope/` | 2 | 3 |
| `LEGITIMACY-AND-SCOPE.md` | `docs/scope/` | 3 | 3 |

Total: 1417 hits to re-path, plus every row of `docs/README.md`. `index.html` (the public GitHub Pages front page) links six docs by absolute GitHub URL: `docs/MAC-BUILD.md`, `docs/STEAMDECK.md`, `docs/WINDOWS-PLAYBOOK.md`, `docs/PHONE-PORTS.md`, `docs/VERIFIED-FIXES.md`, `docs/README.md`.
