# Community release plan: i76-everywhere and i76-map

Written 2026-10-01 from a read-only survey of `C:\Users\james\i76-everywhere` (365 commits, tag `v1.0.0` on
2026-07-14, remote github.com/therealjkvalentine/i76-everywhere), `C:\Users\james\i76-map` (36,522 tracked files,
97 MB pack, **no git remote**) and `C:\Users\james\i76-uncap-lab` (no remote). Live state was read from the daily
driver (`~\Downloads\Interstate76-i76-everywhere-portable-20260801\Interstate 76`) and the sandbox
(`i76-uncap-lab\game`), never changed. Everything marked **proposed** is a suggestion, not a thing that exists.

---

## 1. What exists today

Status words: **deployed** = on the daily driver James plays; **sandbox** = on `i76-uncap-lab\game` only;
**verified** = confirmed in play or by a measurement with a number; **built** = compiles/runs, never confirmed in
play; **parked** = settled dead end; **research** = documents only.

> **Changed since this table was written (added 2026-10-03).** The rows below describe 2026-10-01/02. Read them with
> these newer facts:
>
> - **There is a new daily driver.** `tools\Make-Daily-Driver.ps1` built `C:\Users\james\Games\Interstate76-2026-10-03`
>   (golden copy `...\Interstate76-golden-2026-10-03`) on 2026-10-03: repo `Strlkup.dll`, u32x lab build `054fb411`,
>   `dgVoodoo.daily-driver-2026-10-03.conf`, preset `best-120`, `I76PATCH.DLL` disabled. "Daily driver" in the rows
>   below means the old folder in Downloads, which is now the rollback
>   ([STATUS-2026-10-02.md](STATUS-2026-10-02.md) "2026-10-03", [NEW-DAILY-DRIVER-RECIPE.md](NEW-DAILY-DRIVER-RECIPE.md)).
>   So the "60 fps proxy switches", "draw distance" and "sandbox only" statuses no longer hold for the owner's machine.
> - **Every "this dgVoodoo knob does nothing" result from the lab sandbox is void.** dgVoodoo 2.87.3 was rejecting
>   the sandbox's `dgVoodoo.conf` and running a 2020 global `%APPDATA%` file, so `FPSLimit`, `CaptureMouse`,
>   `FreeMouse`, forced refresh and the 1920x1440 pointer box were never tested. The owner's daily-driver conf was
>   accepted. [GRAPHICS-ENHANCEMENT.md](GRAPHICS-ENHANCEMENT.md) "Measured 2026-10-03",
>   [RENDERER-ALTERNATIVES.md](RENDERER-ALTERNATIVES.md) section 11.
> - **120 fps** (`I76_GLIDE_REFRESH=120`) is measured (120.1 fps) and owner-played; 120 is the ceiling of every
>   renderer tested.
> - `I76_MULTI_INSTANCE=1` (proxy, 2026-10-03): two lab copies ran side by side; a multiplayer session between
>   them was not achieved (both need UDP port 21157; the internet transport wants a game server).

| component | where | state | evidence |
|---|---|---|---|
| Windows installer from a GOG offline backup | `INSTALL.bat` -> `Setup-From-GOG.ps1` (silent Inno install, dgVoodoo, input.map, AHK layer, Strlkup proxy, shortcut) | verified on this machine (INSTALL.md) | `install.ps1` is the older "game already installed" path; both call `setup-windows.ps1` |
| Windows launcher | `PLAY-i76.ps1` (starts i76wheel, AHK remap, cursor overlay, Fighterstick, opentrack, Lossless Scaling, optional `-Ffb`, `-Mission`, savegame.dir re-pad) | deployed, verified | daily driver has `PLAY-i76.ps1`, `_ahk\`, `i76wheel.exe` |
| Settings panel | `LAUNCHER.ps1` (WinForms: dgVoodoo FPSLimit, cursor mode, music volume, health checks for u32x / shell bytes / savegame.dir / Strlkup; builds the PLAY-i76 command line) | deployed | this is the only "tuner" in the repo; `$GameDir` no longer defaults to the daily driver (2026-10-02, backlog P3-12: `I76_GAME_DIR`, then an install beside the script, then the lab sandbox; the title bar names the folder) |
| Portable zip | `MAKE-PORTABLE.bat` -> `Make-Portable-Zip.ps1` (adds `PLAY.bat`, `Setup-This-PC.bat`, save editor, README) | verified (the daily driver *is* one) | contains game files; for the owner's machines only |
| Stock 20 fps cap | GOG's `I76PATCH.DLL` (AiO) | deployed | ~~dgVoodoo `FPSLimit` is **ignored** on this build in both directions (uncap-lab `docs/framerate/README.md` matrix, n=9 cells)~~ **void 2026-10-03**: that matrix ran while dgVoodoo was rejecting the sandbox conf, so `FPSLimit` was never in effect; not re-measured. The old daily driver carries `FPSLimit = 19.2`; the 2026-10-03 one sets 0 |
| In-mission music | `music-fix\Strlkup.dll` (IAT hook: virtual cdaudio over `music\N.mp3`; aux-volume device so the in-game slider works) | deployed, verified in a mission (`docs/MUSIC.md`: `MCI_PLAY -> track 13`) | daily driver `Strlkup.dll` md5 `b910850f` is **older** than the repo's `fe82a0ee` (2026-09-27, 148,480 B) |
| Cutscene-music fix | `smack-music-fix\` (ordinal-exact SMACKW32 proxy) | Mac: verified by ear 2026-07-14. Windows: built; **not** on the daily driver (no `smackorg.dll` there) | DLL is gitignored, built from source |
| Save-screen mouse + freeze fix | `u32x.dll` USER32 proxy; source `u32x\u32x_min.c` in this repo since 2026-10-02 (the 2026-08-16 revision + DWM ghosting fix; the lab's `src\u32x.c` is the development branch) | deployed (`u32x.dll`, `i76.exe.u32xorig`, `i76shell.dll` present) | LAUNCHER treats it as required. Its verification record is spread over `docs/SAVE-FREEZE-ROOT-CAUSE.md` (v2), `READY-TO-TEST.md` (pre-test) and `tools/bisect/LAYERS.ps1`; the source, the verified binary's md5 (`a5927cea`) and its live record are now in `u32x/README.md` (corrected 2026-10-02: this said "the source is not in this repo") |
| 60 fps proxy switches | `music-fix\Strlkup.dll`: `I76_HIRES_CLOCK`, `I76_FIXED_STEP`, `I76_FRAMERATE_FIXES` (+`I76_AI_FIRE_CACHE`), `I76_ENGINE_DT_FIX`, `I76_RENDER_INTERP` (+`I76_INTERP_SMOOTH`), `I76_FPS_CAP`, `I76_FIX_HEALTH_PCT`, `I76_FIX_LABEL_TABLE`, `I76_MISSION`, `I76_SKIP_MOVIES` | sandbox; measured (music-fix/README.md "recommended switch set", i76-map capture 014); **played** in two console sessions (render-interp notes) and **console-verified by the owner 2026-10-02** with every switch on (music, F6/B at 1800 m, flamer, slider, AI, jumps, body roll); "Nothing here is deployed to the playable install" | launcher: `i76-uncap-lab\TEST-FRAMERATE.bat` (4 modes: fixed / nointerp / stock60 / stock20) |
| Draw-distance patch | `patch-farclip.ps1` (uncap-lab), render pool x16 | sandbox, verified at 1800/5000 m (`docs/DRAW-DISTANCE.md`) | `i76.exe.farorig` in the sandbox only |
| Camera-rate 60 fps constant patch | `i76.exe` `.rdata` 0x4bc528 | sandbox only (`i76.exe.camorig`); `READY-TO-TEST.md` carried a "deployed" claim and now carries the L004 correction (portable `6319abf7` = AiO + u32x rename only) — conflict resolved 2026-10-01 | superseded by `I76_FRAMERATE_FIXES` row 5 |
| Force feedback, stock engine FFB on a wheel | T300RS, `enable-force-feedback.bat`, `docs/WHEEL-T300.md`, `tools/ffb-recon.ps1`, `tools/check-ffb.ps1` | verified in-sim (CHANGELOG "FORCE FEEDBACK WORKS") | no registry key gates FFB in the exe — device presence is `[0x52bbe4] != 0` (i76-map finding L084; corrected 2026-10-02, this said "registry gate already satisfied"); the registry check in `check-ffb.ps1` is a leftover |
| Custom FFB (slip/load synthesis) | `tools/ffb/` (FfbCore, Telemetry, FfbMixer, interposer, calibrate, LFE shaker chain) | built; output/telemetry/mixer "working", **feel tuning not started**; opt-in `-Ffb` | `tools/ffb/README.md` status table; `FfbMixer.ps1` is modified and uncommitted right now |
| Pad rumble from the FFB stream (Mac) | `ffb-shim/` (replaces `i7_SFRCE.DLL`) | resolved 2026-10-01: `ffb-shim/README.md:42-49` now says "field-run and tuned on the Mac over 2026-07-19/20", agreeing with `docs/README.md` | still open: never run on Windows or with the wheel/shaker stack (backlog P3-18) |
| Rumble from audio | `sound-rumble/` (dsound proxy) | built, explicitly experimental, unverified | |
| Frame generation | `Setup-FrameGen.ps1` + Lossless Scaling profile; PLAY-i76 starts/stops it | verified 2026-08-01 (no Steam dependency) | needs the $7 commercial app; interpolates display only |
| Head tracking | `i76-opentrack-headlook.ahk` + `i76-opentrack-autostart.ahk` | verified ("Working and field-confirmed", `docs/HEAD-TRACKING.md`) | opentrack is GPL, bundled only with `-IncludeHeadTrack` |
| CH Fighterstick layer | `i76-ch-fighterstick.ahk` | **verified in play 2026-08-08** (corrected 2026-10-03: this said "built 2026-08-08, `-whatif` bench mode", from the doc's opening line. [FIGHTERSTICK.md](FIGHTERSTICK.md) "What is and is not verified", last edited later the same day in `eabf5cc`, reads: "**Confirmed in the game**, 2026-08-08, control by control": trigger, the three hats, special, glance, stick axes, held horn) | buttons 17-19 and the mode-switch renumbering do not exist on the device |
| Controller layer (XInput shift layer, rumble mixer) | `i76-remap.ahk`, `_ahk\` | deployed, verified on Mac/Windows | Deck "baseline tier" (`deck/setup-deck-baseline.sh`) **unverified on device** |
| Boot straight into a mission | `I76_MISSION` via the proxy; `PLAY-i76.ps1 -Mission t01.msn` | verified: in the mission 10 s after launch (`docs/MISSION-LAUNCH.md`) | |
| Save editor | `i76-save-editor.html` (hosted on GitHub Pages via `index.html`), `i76-save-editor.py`, `i76-save-editor.command` + `-server.py` (Mac write-back) | verified byte-identical parser; `docs/SAVE-FORMAT-GAPS.md`, `EDITOR-FIELD-TESTS.md` list open in-game checks | |
| Trainer | `tools/trainer/i76trainer.py` (status / flags / repair / ammo / teleport; refuses non-sandbox without `--any`; every write read back) | sandbox; addresses from i76-map `cheats.md` | the older AHK tools (`tools/i76-trainer.ahk`, `i76-debugmenu.ahk`, `i76-rearm.ahk`) are the 2026-07 generation |
| Shipped bookmark saves | `saves/` (scenes 2-15, `Install-Saves.ps1`) | committed `.cmp` files | user-generated data, not game assets; keep but say so |
| Mac build | `build-launchers.sh`, `*.swift` stubs, `setup-*.sh`, `interstate-76.dxw`, `mac-install.command` (BETA) | verified (software renderer via DxWnd, 1024x768, ~19.2 fps) | 60 fps and the Strlkup proxy are **untested under Wine** |
| Steam Deck | `deck/deck-install.sh` (innoextract + dgVoodoo 2.78.2 from archive.org), controller template, artwork | verified installed 2026-07-11 (Glide path + FFB) | QAM limiter 20 is the documented cap; proxy untested under Proton |
| HD textures | `texture-lab/`, `tools/i76img.py`, `tools/openglide-hd/` | **retired** (night palette artefacts); M16/VQM format crack kept | |
| Voodoo (Glide->Metal) on Mac | `docs/VOODOO-PARKED.md` | **parked** (MoltenVK pipeline persistence) | |
| Phone ports | `docs/PHONE-PORTS.md` | research only | |
| **i76-map**: subsystem specs | `subsystems/*.md` (15 files: ai, camera, cheats, damage, engine, framerate, mission, network, options, physics, renderer, simclock, sound, weapons, VOCABULARY) | static specs; 2,193/2,217 functions named (REIMPLEMENTATION.md) | every claim cites an instruction; live confirmation partial (capture 014, HealthFraction live) |
| **i76-map**: runtime header | `types/i76_runtime.h` (1,300 lines, 42 structs, 126 static offset checks, MSVC `/W4` clean), `types/i76.h` (Ghidra) | built; 15-claim disassembly sample 14 confirmed (`i76_runtime-conflicts.md`) | |
| **i76-map**: format parsers | `data/fmt/` (`roundtrip.py`: 6,368 files, 526 MB, 0 byte diffs), `data/FORMATS.md`, `FORMATS-tables.md` | verified byte-exact | `DATABASE.MW2`, `.pcx`, `.fnt` still typed/unknown |
| **i76-map**: mod CLI | `data/mod/i76mod.py` (`show` / `alias` / `car` / `--zfs`; writes only under `data/out`, re-parses every output) | built; **in-game effect pending** (`data/LIVE-TESTS.md` T1..) | |
| **i76-map**: FSM tools | `data/fmt/fsmtool.py dis|asm`, `data/FSM.md` (14 opcodes, 96 actions), `data/out/fsm/*.fsm` | all mission scripts disassembled; round trip in `roundtrip.json` | |
| **i76-map**: reimplementation docs | `REIMPLEMENTATION.md`, `OPEN76-GAPS.md` (456 lines) | written 2026-09-27 | `ARCHITECTURE.md` written 2026-10-01 (nine diagrams, call-count module map; corrected 2026-10-02 — this said "does not exist yet") |
| **i76-map**: Ghidra export | `ghidra/export/` (4,569 committed files: decompiled `.c`/`.pcode` of i76.exe), `ghidra/export-frozen/` | internal | **cannot be published** (section 5, legal) |

---

## 2. Packages

### Split or not

**Recommendation: two public repos, and keep them two.** Arguments for the split:

- Different audiences and different risk. Players need an installer and a launcher; a modder/porter needs the specs,
  header and parsers. The i76-map repo also carries material that must never be public (decompiled game code, the
  recon archive, copies of exes, extracted ZFS, 1.5 GB of captures). A player-facing repo must be small enough to
  audit at a glance for "no game files"; i76-map at 36 k tracked files is not.
- The i76-everywhere repo is already public with a URL in `OUTREACH-DRAFT.md`, `deck-install.sh` (`$REPO_RAW` curls
  from `main`) and the GitHub Pages save editor. Merging i76-map into it would churn those paths.
- The data CLI (`i76mod.py`) imports `tools\i76fmt` from i76-map; keeping the dependency inside one repo is simpler
  than vendoring it into i76-everywhere.

Against the split, and how to handle it: the player repo needs three i76-map products (the `I76_*` switch table,
the format of `savegame.dir`, and later a public pointer to the specs). Handle by **linking**, not copying: one
"For modders" paragraph in the player README pointing at i76-map, and `docs/MODDING-GUIDE.md` stays in
i76-everywhere as the bridge (it already is).

What should move between repos before release:

- `i76-uncap-lab\src\u32x.c`, `u32x.def`, `build-u32x.ps1` -> **i76-everywhere** (`u32x/`). **Done 2026-10-02** for
  the build that is actually verified: `u32x_min.c` + its `.def`, the DLL (md5 `a5927cea`), `build.ps1`,
  `deploy-u32x.ps1`, README with provenance. The lab's newer `u32x.c` stays there until it passes the bookmark route.
- `i76-uncap-lab\TEST-FRAMERATE.ps1` -> the preset logic in it becomes the player launcher's presets (below); the
  script itself stays a lab tool.
- `i76-uncap-lab\docs\framerate\{README,MEASUREMENTS,DEAD-ENDS}.md` -> i76-everywhere `docs/framerate/` (proposed).
  `README.md` here already links to `../i76-uncap-lab/docs/framerate/MEASUREMENTS.md`, a path that does not exist for
  anyone else.

### Package A: `i76-everywhere` (player-facing)

Proposed layout. Rule: **do not move anything a script or a public URL depends on** (`deck/`, `dgVoodoo.conf` at the
root (fetched by `deck-install.sh` from raw `main`), `music-fix/`, `tools/`, `i76-save-editor.html`, `index.html`,
`docs/`). New folders only; the Mac pile moves in a second step.

```
i76-everywhere/
  README.md  INSTALL.md  CHANGELOG.md  LICENSE  THIRD-PARTY.md  CONTRIBUTING.md
  INSTALL.bat  Setup-From-GOG.ps1  install.ps1  setup-windows.ps1       (unchanged paths)
  PLAY-i76.ps1  LAUNCHER.ps1  Make-Portable-Zip.ps1  MAKE-PORTABLE.bat  Setup-FrameGen.ps1
  dgVoodoo.conf  dgVoodoo.windows.conf  enable-force-feedback.bat
  presets/                                   (proposed) one file per named preset, read by PLAY-i76/LAUNCHER
    stock.ps1                                I76PATCH.DLL present, no I76_* vars           (what GOG ships, plus music)
    stock-exact-20.ps1                       I76PATCH.DLL off, I76_FPS_CAP=20              (TEST-FRAMERATE stock20)
    smooth-60.ps1                            I76PATCH.DLL off, HIRES_CLOCK FIXED_STEP=24 FRAMERATE_FIXES ENGINE_DT_FIX RENDER_INTERP
    smooth-60-bugfixes.ps1                   smooth-60 + I76_FIX_HEALTH_PCT=1 I76_FIX_LABEL_TABLE=1
  music-fix/        Strlkup.dll proxy: source, build.ps1, README (the switch table lives here)
  u32x/             (done 2026-10-02, from i76-uncap-lab/src) USER32 proxy: u32x_min.c, u32x.def, u32x.dll, build.ps1, deploy-u32x.ps1, README
  smack-music-fix/  ffb-shim/  sound-rumble/   (as is; DLLs built locally, gitignored)
  tools/            trainer/  ffb/  i76wheel.c  lint-input-map.py  pad-diagram.py  bisect/  (RE instruments pruned, section 5)
  mac/              (proposed, step 2) build-launchers.sh  *.swift  setup-*.sh  *.command  interstate-76.dxw  fix-arrows-for-mac.sh  slim-wrapper.sh
  deck/             (as is)
  saves/            shipped bookmarks (own data) + Install-Saves.ps1
  i76-save-editor.html  i76-save-editor.py  i76-save-editor-server.py  index.html  (GitHub Pages)
  docs/             (curated; section 5 lists what leaves)
```

How a preset applies (proposed, matches what `TEST-FRAMERATE.ps1` already does): `PLAY-i76.ps1 -Preset smooth-60`
sets the `I76_*` environment variables, renames `I76PATCH.DLL` <-> `I76PATCH.DLL.disabled` as the preset says, and
refuses to start if `Strlkup.dll` is not the proxy (the switches are no-ops without it). `LAUNCHER.ps1` gets a preset
drop-down and shows the proxy log lines (`hires-clock: 2/2`, `render-interp: 3/3 hooks`) after a run, the way
TEST-FRAMERATE prints them. No new mechanism: every piece exists in `TEST-FRAMERATE.ps1` and `music-fix/README.md`.

One-page README outline (proposed), replacing the current 94-line README:

1. One paragraph: Interstate '76 (GOG Gold) on Windows, Mac and Steam Deck. No game files here; bring your GOG copy.
2. **Install** (3 lines): download the GOG offline backup -> double-click `INSTALL.bat` -> desktop shortcut.
3. **Presets** table: Stock / Stock exact 20 / Smooth 60 / Smooth 60 + bug fixes, one line each with the status word
   (Smooth 60 = *experimental, measured in the sandbox, 2 console sessions*).
4. **What it fixes** (the section 4 table, short form, with links to VERIFIED-FIXES.md).
5. **Save editor** link (hosted) and screenshot.
6. **Mac / Deck** two lines each with the status word and the doc link.
7. **For modders**: one line pointing at i76-map.
8. **Legal**: three lines (MIT for our code; no Activision content; see THIRD-PARTY.md).
9. **Credits**.

### Package B: `i76-map` (modder/porter-facing)

The current repo cannot be pushed as-is (section 5). Proposed: a **new public repo built from a curated export**,
with the private repo kept as the working tree. Public layout:

```
i76-map/                                   (public)
  README.md            what this is, the status vocabulary (auto < proposed < supported < verified), how to cite a row
  ARCHITECTURE.md      (being written) engine overview for a porter
  REIMPLEMENTATION.md  OPEN76-GAPS.md
  subsystems/          the 15 spec files + VOCABULARY.md + vocabulary.json
  types/               i76_runtime.h  i76.h  i76_runtime-conflicts.md  README.md   (dx5.h / anet.h: see legal note)
  symbols/             functions.tsv  globals.tsv  tables.tsv  strings.tsv  imports.tsv  regions.tsv   (names + addresses + status; no code)
  data/                FORMATS.md  FORMATS-tables.md  FSM.md  VEHICLES.md  LIVE-TESTS.md  vehicles.csv  roundtrip.json
    fmt/               parsers (bwd2x, formats, fsm, fsmtool, roundtrip, gendoc, layouts, vehicle_sheet ...)
    mod/               i76mod.py  aliases.py  zfspatch.py  stage_livetests.py
    notes/             tracing notes
  tools/i76fmt/        the container/LZO library the parsers import
  tools/               only what a user of the above needs: gen_tables.py --verify, completeness.py, which_build.py, pe_ident.py
  evidence/            E*.json rows (data, not code)
  LICENSE  THIRD-PARTY.md  CHANGELOG.md
```

Excluded from the public export (stay in the private tree): `ghidra/export*`, `ghidra/scripts` (fine to publish, but
useless without the project), `recon-2026-09-04/`, `captures/`, `foldin/`, `functions/*.md` until reviewed for quoted
decompiler output, `status/` (internal task files; publish `status/progress.svg` and `GOAL-COVERAGE.md` only),
`agents/`, `requests/`, `outreach/`, `sandbox-*/`, `toolchain/`, `external/`, `binaries/*.toml` (keep: they are
md5s and section tables, publishable). `data/out/fsm/*.fsm` are disassemblies of Activision's mission scripts;
**proposed: do not ship them, ship the command that generates them** (`fsmtool.py dis`) and keep one short excerpt in
FSM.md.

One-page README outline (proposed) for public i76-map:

1. What it is: a plain-text, cited map of `i76.exe` (GOG Gold, md5 `9a232dcc`), its data formats and runtime
   structures, built for ports and mods. Numbers: 2,193/2,217 functions named; 30 format families, 6,368 files
   round-trip byte-exact; 42 runtime structs with offset checks.
2. Start here by goal: *port the engine* -> `ARCHITECTURE.md`, `REIMPLEMENTATION.md`, `subsystems/`; *read a file*
   -> `data/FORMATS.md` + `data/fmt/`; *change the game* -> `data/mod/i76mod.py` and i76-everywhere's
   `docs/MODDING-GUIDE.md`; *write a trainer* -> `subsystems/cheats.md`, `types/i76_runtime.h`.
3. How to read a row: address class tags (`init`/`bss`/`iat`/...), status words, "every claim cites the instruction".
4. What is not here, and why: no decompiled code, no game data, no binaries; how to rebuild the Ghidra project
   yourself from the scripts (the README's existing "Rebuild instructions").
5. Quick commands: `roundtrip.py`, `fsmtool.py dis`, `i76mod.py show`.
6. Relationship to Open76 / Roanish; how to contribute a claim (with evidence kinds).
7. Legal: interoperability RE on a DRM-free owned copy; nothing of Activision's redistributed.

---

## 3. User journey: GOG install to first drive at 60 fps

### Windows (today)

1. Buy on GOG; download the offline backup `setup_interstate76_*.exe` (and the Nitro Pack one) to Downloads. *Manual.*
2. Clone or download the repo zip. *Manual.*
3. Double-click `INSTALL.bat`. **Automated**: silent Inno install, dgVoodoo 2.87.3 download (GitHub release), `input.map`
   patch, AutoHotkey 1.1 (pinned sha256) + `_ahk\i76-remap.ahk`, `Strlkup.dll` proxy (`strlkup_orig.dll` backup),
   `i76wheel.exe` if built, `PLAY-i76.bat` + desktop shortcut. One UAC prompt.
4. Plug in the controller/wheel **before** launching. *Manual, documented.*
5. Double-click the shortcut -> `PLAY-i76.ps1`. **Automated**: AHK layers, cursor overlay, savegame.dir re-pad, music
   proxy log. 60-75 s "PLEASE STAND BY", Esc skips the intro. This is **Stock 20** (I76PATCH.DLL caps it).
6. To get 60 fps today you must: rename `I76PATCH.DLL`, set the five `I76_*` variables in the shell, start
   `i76.exe -glide` from that shell. **Not automated for players**: only `i76-uncap-lab\TEST-FRAMERATE.bat` does it,
   and only against the sandbox. **Missing before release**: the preset switch in `PLAY-i76.ps1`/`LAUNCHER.ps1`
   (section 2; done 2026-10-02, `PLAY-i76.ps1 -Preset`) and `u32x.dll` deployment in `setup-windows.ps1` (**coded
   2026-10-02**, step 5a3 via `u32x\deploy-u32x.ps1`, also run on the portable zip's staged copy; exercised offline on
   scratch copies of the pristine binaries only. The fresh-install console run in section 7 item 3 is still owed).
7. Optional: `enable-force-feedback.bat` as admin (FFB wheels), `Setup-FrameGen.ps1` (Lossless Scaling), `LAUNCHER.ps1`.

### Mac (today: 20 fps only)

1. GOG offline installer. *Manual.*
2. Wine wrapper (Sikarugir) + the repo's stubs: `build-launchers.sh`, `setup-dxwnd.sh`, `setup-music.sh`,
   `fix-arrows-for-mac.sh`, `setup-cutscene-music-fix.sh`, `setup-input-remapper.sh`. **Semi-automated**;
   `mac-install.command` is BETA (CHANGELOG v1.0.0 "Known gaps").
3. Launch `Interstate 76 - Software (DxWnd).app`; deny the microphone prompt once. Set 1024x768 in Options.
4. 60 fps: **not available**. The software renderer plus DxWnd is capped at ~19.2 fps by design (`maxfps0=52`), and the
   Strlkup proxy has never been loaded under Wine. The MCI `mpegvideo` device the music half uses, and the DxWnd
   virtual-CD hook, would both be answering `mciSendCommandA`. **Proposed test** before claiming anything: proxy with
   music disabled (`-NoMusic` equivalent) under the parked dgVoodoo/DXVK path, since the software renderer cannot
   render 60 fps worth of frames at 1024x768 anyway (unmeasured: mark as a question, not a fact).

### Steam Deck (today: 20 fps)

1. GOG offline installer to `~/Downloads` in Desktop Mode. *Manual.*
2. `curl -Ls https://raw.githubusercontent.com/therealjkvalentine/i76-everywhere/main/deck/deck-install.sh | bash`
   (or `Install-I76.desktop`). **Automated**: innoextract 1.9, dgVoodoo 2.78.2 from archive.org, configs, GE-Proton,
   Steam shortcut with artwork, controller template.
3. Game Mode, QAM framerate limit 20, play. Dock a USB FFB wheel for real force feedback.
4. 60 fps: **not available**. `I76PATCH.DLL` is present; the proxy is untested under Proton. Mechanically the Deck is
   the most likely second platform (Windows DLLs load under Proton as on Windows), so **proposed**: `deck/i76-deck-launch.sh`
   (already a `%command%` wrapper that reads `$STEAM_COMPAT_DATA_PATH`) exports the preset's `I76_*` variables; one
   on-device run with `I76MUSIC_LOG=1` tells whether the hooks landed (`hires-clock: 2/2` in `mciproxy.log`).

---

## 4. What a player can do with it

Numbers from `docs/VERIFIED-FIXES.md`, `music-fix/README.md`, `CHANGELOG.md`, uncap-lab `docs/framerate/*`.

| feature | status | the number |
|---|---|---|
| Play at 60 fps with 20-fps-faithful physics (Smooth 60 preset) | **experimental**: measured in sandbox, played in 2 console sessions, not on the daily driver | fixed step 24/s = 41.7 ms (stock 20 fps steps 46.9 / 31.2 ms); body motion at rest 0.83-0.86 vs stock 0.45-0.84 (3 of 4 runs); interpolation: frames without motion 31-33% -> 0%, roughness 1.00 -> 0.04-0.06 (n=2 missions); chase-cam jerk median 0.029 -> 0.002 m/frame^2 |
| Frame-rate bugs fixed at 60 fps (sky, free-look, zoom, throttle ramp, lock tones, radar ping, vehicle sounds, AI throttle/steer, AI fire rate, flamers, smoke, missile trails, HUD digits) | **experimental** (same preset, `I76_FRAMERATE_FIXES`) | clouds 0.0300/s at 60 fps = 20 fps value (stock 0.0899); smoke puffs 19.1 steps/s (stock 57.8); flame stream 18.7 segments at 60 fps (stock 60 fps 0.6: "in effect no flamers"); AI yes-fire decisions 1.2-1.9/weapon-s with hold vs 4.9-5.2 stock 60 (n=2); AI throttle chatter 26.2 stock -> 5.3 with clock+fixed step (n=3) |
| Exact dt (hires clock) | **experimental** | dt 50.00 ms at 20 fps, 16/17 ms at 60 (stock: 47/63 ms jitter from 15.6 ms GetTickCount) |
| Exact 20 fps cap without I76PATCH (`I76_FPS_CAP=20`) | sandbox, measured | held 20.0 fps exactly |
| Vehicle health % bug fix (`I76_FIX_HEALTH_PCT`) | verified live in sandbox, **off by default** (missions may be tuned around the bug); revised 2026-10-02 to min(28 + 72 x side, 100 x core) after the target bar rose on scratched cars (docs/HEALTH-BAR-COLOUR.md); revision measured live 2026-10-02 (`tools/trainer/tests/health_pct_live_test.py`: stock 0.99 / x100-only 99.0 / min() 49.6 on a 30% armour car with a 99% engine); `=2` keeps the x100-only reading for A/B | 99% engine: stock = heaviest smoke, fixed = none; 50%: smoke |
| Object-label table fix for huge custom missions (`I76_FIX_LABEL_TABLE`) | verified with forced capacity 16 | T01 grew 16 -> 272, 88/88 labels kept |
| In-mission music on a machine with no optical drive; in-game volume slider works | **verified, deployed** | engine state `0x524674` 0 -> 1, MCI handle `0xC0DE`; `auxSetVolume -> 700/1000` |
| Cutscene music no longer bleeds over FMVs | verified (Mac, by ear); Windows built, not deployed | 39 ordinal-exact exports; ~1 s residue on in-engine fades accepted |
| Menus/save screen: mouse lands where the cursor is, no freeze on the overwrite prompt | **deployed**; verification record to consolidate | u32x v2 (`EnumWindows` on own PID), DWM ghosting fix ("Save Bookmark screen dying ~5.9 s after it opens") |
| Saves never vanish from the load list | **deployed, verified** (PLAY-i76 re-pads `savegame.dir`) | header 0x28 + 60-byte records; engine leaves it 36 bytes short every save |
| Boot straight into a mission | verified | 10 s from launch to player entity resolved |
| Force feedback on a modern wheel (stock engine effects) | **verified** (T300RS; DFGT and WingMan community reports) | 300 deg rotation; Combined pedal mode required; close the Thrustmaster panel first |
| Custom slip/load FFB and bass shakers | built, opt-in, **untuned** | 8 channels, 28 assertions pass; WAVEHDR root cause fixed; "never yet run together" |
| Controller: LB shift layer, independent triggers, look-back rear gun, rumble mixer | verified (Mac, Windows); Deck baseline unverified | ~27 actions from 13 buttons |
| Head tracking (opentrack) | verified | |
| Frame generation (Lossless Scaling) | verified, needs a paid app | LSFG 2x on a 20 fps base; artefacts expected |
| Mouse driving + 3 mouse buttons; joystick5 -> joystick1 fix; never use the in-game bind menu | verified | lint: `tools/lint-input-map.py` |
| Save editor (weapons, armor tenths, parts, condition, scene, slots, DPS/range) | verified byte-identical | 116-byte records |
| Draw distance 600 m -> up to 5000 m | sandbox-verified, **not deployed** | crash ceiling removed by 16x render pool; 60 fps flat at 1800/5000 m |
| Trainer: repair, unlimited ammo/armour/chassis without the "cheated" marker, teleport | sandbox | marker `0x535f78` not set |
| Mod data: car armour/weapons, mission scripts, surfaces, rebuilt ZFS | built; in-game effect pending | 6,116 ZFS entries verified on rebuild |
| Mac: instant start, music, clean quit, 4:3 letterbox | verified | ~19.2 fps, 1024x768 ceiling |
| Deck: Glide path, FFB, one-liner install, library art | verified installed | dgVoodoo 2.78.2 |
| Multiplayer | **not touched** (Windows-only, glenrio.interstate76.com, Tuesdays) | proxy "Multiplayer is untested" |

Not features: widescreen (camera is 4:3 in the exe), HD textures (retired), Voodoo on Mac (parked).

---

## 5. Clean-up before release

### Duplicated or stale docs (concrete pairs)

| keep | fold in / retire | why |
|---|---|---|
| `docs/LEGITIMACY-AND-SCOPE.md` | `docs/SCOPE-AND-LEGITIMACY.md` | same content, written a day apart; `docs/README.md` links both |
| `docs/MAC-BUILD.md` | `docs/MAC-SETUP.md` (handoff brief, 2026-07-04) | MAC-SETUP describes a package (`i76-stable-gog.zip`, `I76_CD1.ISO`) that must not be referenced publicly |
| `docs/WINDOWS-PLAYBOOK.md` | `docs/MODERN-SETUP.md`, `docs/WHAT-THIS-IS-dgvoodoo.txt`, `docs/i76-research-full.txt` | pre-July notes; the playbook supersedes them |
| `music-fix/README.md` (switch table) + `docs/MUSIC.md` (diagnosis) | the "NOT YET BUILT", "needs 32-bit gcc", "Not yet observed: MCI_PLAY" paragraphs inside `music-fix/README.md` | the DLL has been built and `MCI_PLAY` was observed (MUSIC.md); the README now contradicts itself top to bottom. Rewrite as: what it does, switches, build, history link |
| `docs/VERIFIED-FIXES.md` | `docs/READY-TO-TEST.md` | READY-TO-TEST is a dated checklist (2026-08-16); its camera-rate "deployed" claim was corrected in place on 2026-10-01 (L004) and its other stale items on 2026-10-02. Still slated: close its items into VERIFIED-FIXES rows and delete |
| `README.md` "Open improvements" table | the whole table | it is a 2026-08-16 status snapshot (u32x "awaiting verification", FFB "never run together"); release README has no live backlog |
| `CHANGELOG.md` "Unreleased" | its first bullet ("raising the real frame rate is plausible... nothing field-tested") | done 2026-10-01: the bullet carries the superseding update (`CHANGELOG.md` "2026-10-01 update") and `docs/FRAMERATE-UNCAP-RESEARCH.md` its superseded header; close in v1.1.0 (backlog P3-06) |
| uncap-lab `docs/framerate/README.md` | `docs/MODERN-SETUP.md` "20 FPS... above ~30 FPS the sim over-integrates" and `WINDOWS-PLAYBOOK.md` section 1 point 4 "Do not raise it" | measured false (gravity dt-correct, jump clears at 60); the playbook still teaches the lore as fact |
| `ffb-shim/README.md` status line | `docs/README.md` row for ffb-shim | resolved 2026-10-01: the shim README now says field-run and tuned on the Mac 2026-07-19/20, matching the doc map; what remains open is "never run on Windows / with the wheel" (backlog P3-18) |
| `docs/README.md` (doc map) | its "Current state (2026-07-11)" block | three months stale; regenerate from the section 1 table |
| `THIRD-PARTY.md` dgVoodoo row | `install.ps1` (fetches 2.87.3 from GitHub), `deck-install.sh` (2.78.2 from archive.org), VERIFIED-FIXES (2.78.2 on Mac) | one row saying which version per platform and from where |
| `subsystems/framerate.md` row 5 | "the portable install's patch rescales the constant" | resolved: `../i76-map/subsystems/framerate.md:37` already cites L004 and says "sandbox / lab only" (corrected 2026-10-01) |
| `docs/GHIDRA-MEMORY-MAP.md` (990 lines), `STATIC-RE-FABLE.md`, `MEMORY-MAP-INDEX.md`, `MW2-I76-STRUCTS.md`, `RE-METHODOLOGY.md`, `RE-FIELD-GUIDE.md`, `FIND-WHAT-WRITES.md` | move to the private i76-map tree or an `docs/archive/` folder | 2026-07 RE logs superseded by i76-map; the public player repo does not need 3,000 lines of raw session logs, and they contain intermediate claims the i76-map `findings.md` has since contradicted |

### Overlapping scripts

| pair | resolution (proposed) |
|---|---|
| `Setup-From-GOG.ps1` vs `install.ps1` | keep both but make `install.ps1` the "already installed" sub-step that `Setup-From-GOG.ps1` calls; today both re-implement game-dir discovery and tool download |
| `tools/i76-music.ps1` (external MP3 player stopgap) vs `music-fix/` | PLAY-i76 already skips the stopgap when the proxy is deployed; retire `i76-music.ps1`, `tools/winmm-cdaudio/` (the winmm-proxy attempt that dgVoodoo's search-path hardening defeated) and `tools/cdaudio-image/` |
| `i76-with-remap.bat` vs `PLAY-i76.ps1` | PLAY-i76 starts AHK itself; delete the .bat |
| `tools/i76-trainer.ahk`, `i76-debugmenu.ahk`, `i76-rearm.ahk`, `i76-worldscan.ahk`, `i76-chaindiff.ahk`, `i76-mem-*.ahk`, `i76-findval.ahk`, `tools/i76-mem-scan.py`, `find-regen-*.py`, `diffscan.sh`, `chaindiff.sh`, `findval.sh`, `exe-disasm.py`, `exe-xref.py`, `tools/i76-addresses.json` | 2026-07 generation of the trainer and RE instruments; `tools/trainer/i76trainer.py` + i76-map supersede them. Move to `tools/archive/` or the private tree |
| `swap-renderer.ps1`, `test-drive.ps1`, `tools/grab-screen.ps1`, `tools/slow_t*.png`, `0x501918/`, `drive5.csv` (5.8 MB), `fx.csv`, `lfe-sweep.wav` (1.3 MB), `grep.exe.stackdump`, untracked `james` and `tools/rdp-to-console.cmd` | lab residue at the repo root; delete or move to the lab |
| `tools/ffb/*.csv`, `drive2.graph.html`, `probe/`, `trace/` | gitignored patterns exist but several CSVs are still listed; verify `git ls-files tools/ffb` is scripts only |
| `deck/build-controller-config.py` vs `build-controller-config-opt2.py`, `controller_neptune_i76.vdf` vs `_opt2.vdf` | pick one; DECK-CONTROLS.md explains the two options, the installer should ship one |
| `i76-calibration-saves.py`, `saves/rescue-20260718/` | rescue folder is a one-off recovery; keep `saves/` only |

### Unverified items to label "experimental" in the release

Smooth 60 presets (all `I76_*` switches); `I76_FIX_HEALTH_PCT` (off by default, say why); draw-distance patch (do
not ship until console-verified; or ship as `I76_FAR_CLIP=n` in the proxy, **proposed**, following the existing
verify-bytes-first pattern); custom FFB (`-Ffb`); `sound-rumble/`; `ffb-shim/` until its README and the doc map
agree; Deck baseline tier; `mac-install.command`; phone ports; multiplayer with any proxy switch.

### Legal notes

- **No game files**: `.gitignore` already excludes `game-data/`, built DLLs and `refs/`. Add a CI check (proposed):
  fail on any file > 2 MB, any `.ZFS/.MSN/.SMK/.pak/.exe` and any `*.dll` except `music-fix/Strlkup.dll`.
- **`music-fix/Strlkup.dll` is a committed binary of our own code** (148,480 B) that forwards to GOG's renamed
  `strlkup_orig.dll`. Acceptable, but publish the build command and the md5 in `CHANGELOG.md` so it is reproducible,
  and note that it contains no Activision bytes (it does not: the forwarders are by name).
- **i76-map `ghidra/export/` (4,569 files) and `export-frozen/` are decompiled Activision code and must not be
  published.** Same for `recon-2026-09-04/` (contains sibling-build exes, extracted ZFS, MW2 database dumps even if
  gitignored locally), `captures/` and `data/out/fsm/` (mission-script disassemblies). Symbol tables
  (`symbols/*.tsv`: names, addresses, status) and specs that cite instructions are the same class as any published
  memory map and are fine. `functions/*.md` need a one-pass review for pasted decompiler bodies before export.
- **`types/anet.h`** is derived from anet-0.10 (Activision's LGPL netcode release); **`dx5.h`** from the DirectX 5 SDK
  headers. Public i76-map `THIRD-PARTY.md` must list both; dx5.h may need rewriting as our own boundary types.
- **THIRD-PARTY.md exists but is incomplete** (9 tool rows at `THIRD-PARTY.md:24-32`; corrected 2026-10-02 — this said "missing"). Still absent: Lossless Scaling (commercial, referenced and optionally bundled by
  `Make-Portable-Zip.ps1 -IncludeFrameGen`: say "your licence, your PCs only"), opentrack (GPL, `-IncludeHeadTrack`),
  GE-Proton, Steam ROM Manager configset (Deck), immi101's i76fix and bolrog's D2DX (referenced in uncap-lab
  `refs/`, the frame-loop hook design), Roanish/i76 and That Tony (listed under credits, fine), CahootsMalone's
  guide, Ghidra / capstone / pefile / Unicorn / Frida (i76-map tools), w64devkit (build), the Visual C++ 5.0 media
  held locally for toolchain fingerprinting (never distributed; say so), RAD Smacker (`SMACKW32.DLL` is game-shipped;
  our proxy forwards to it; **libsmacker** is Open76's dependency only, mention it only in i76-map's OPEN76-GAPS
  context). The dgVoodoo row must state the archive.org mirror the Deck installer uses and that dgVoodoo's readme
  permits redistribution only if that is true (check Dege's licence text before claiming it; today we only fetch).
- **GOG copy required** everywhere: INSTALL.md, README, deck-install.sh all say it; keep the "you bring your own"
  sentence in the first paragraph of every README.
- **Portable zip**: `Make-Portable-Zip.ps1` contains game files by design. The release must say in INSTALL.md (it
  already does) and in the zip's own README that it is for the owner's machines only.
- **Committed saves** (`saves/*.cmp`): user-generated bookmark data, not Activision assets; CONTRIBUTING.md's
  "never commit save files" line needs an exception sentence or the folder needs to go.

---

## 6. Versioning and the CHANGELOG convention

- **SemVer on the player repo.** `v1.0.0` exists (2026-07-14). The "Unreleased" section since then holds verified
  features (FFB works, in-mission music, u32x, head tracking, frame-gen, savegame.dir guard) plus the experimental
  proxy. **Proposed**: `v1.1.0` = everything verified today, with the Smooth 60 presets shipped **off by default and
  labelled experimental**; `v2.0.0` = Smooth 60 becomes a default-offered preset after the console verification in
  section 7 (it changes what the game *is* at the physics level, which deserves a major).
- **i76-map versions by date and coverage**, not SemVer (`2026.10`, with the `GOAL-COVERAGE.md` baseline line copied
  into the release notes: functions named, bytes named, round-trip count). Tag the public export commit.
- **CHANGELOG format**: keep "Keep a Changelog" headings (`Added / Changed / Fixed / Removed`) and add one word of
  verification status in brackets on every entry: `[verified in play]`, `[measured, sandbox]`, `[built, untested]`,
  `[retracted]`. The repo's history of retractions is a feature; the convention keeps it visible.
- **Every proxy switch change** records: the switch name, the number of patch sites, the build this was measured on
  (md5 prefix), and the capture id (`i76-map captures/014-framerate`), as the last five commits already do.
- **Binary reproducibility**: `music-fix/README.md` lists the compiler and `build.ps1`; the release notes carry the
  md5 of the shipped `Strlkup.dll`.

---

## 7. Release checklist

Pre-release, Windows (at the physical console, never over RDP, `TerminalServerSession` False):

1. `git status` clean; commit or revert `tools/ffb/FfbMixer.ps1`; delete/ignore `james`, `tools/rdp-to-console.cmd`,
   `tools/ffb/ffb-lfe-demo.ps1` or commit them deliberately.
2. Diff the daily driver against pristine (`i76-map tools/which_build.py`): confirm `i76.exe` `6319abf7` = AiO + u32x,
   `Strlkup.dll` = the build being released (today it is **not**: `b910850f` vs `fe82a0ee`).
3. Fresh-install test on a clean folder: `Setup-From-GOG.ps1 -GameDir C:\Games\I76-test` -> `PLAY-i76.ps1 -GameDir ...`
   boots, music plays in a mission (`mciproxy.log` shows `MCI_PLAY`), save works, mouse lands. This proves u32x is
   installed by the installer, which today it is not.
4. Preset A/B at the console on the **sandbox**: `TEST-FRAMERATE.bat` 1/2/3/4, each twice (A/A before A/B, record n
   and spread); confirm `hires-clock: 2/2`, `fixed-step`, `render-interp: 3/3 hooks` in the log; Mission 5 jump clears
   under Smooth 60; a full mission to a save and reload.
5. Promote: copy the released `Strlkup.dll` to the daily driver as its own step, keep `*.pre-<release>` beside it,
   and play one evening before tagging.
6. Doc pass from section 5: remove READY-TO-TEST, merge the legitimacy pair, fix the ffb-shim conflict, rewrite
   music-fix/README, regenerate `docs/README.md`, `python3 tools/lint-input-map.py` on the shipped `input.map`.
7. `THIRD-PARTY.md` additions from section 5; LICENSE unchanged (MIT, with the "does not cover" paragraph).
8. CHANGELOG: close "Unreleased" into `v1.1.0` with status brackets; tag; GitHub release notes = the README preset
   table + the section 4 numbers.
9. Pages: `index.html` and `i76-save-editor.html` still load after the doc moves (all its links are `blob/main/docs/...`).

Pre-release, Mac and Deck: run the existing install path once from a clean machine/prefix each and record the result;
say "verified on <date>, <hardware>" or "untested since <date>" in the README. Do not claim 60 fps on either.

Pre-release, i76-map: `python tools\gen_tables.py --verify` and `completeness.py` pass; `ARCHITECTURE.md` finished;
build the public export with an explicit allowlist script (proposed `tools/export_public.py`: copies only the paths in
section 2, refuses if any file matches `*.c`, `*.pcode`, `*.exe`, `*.dll`, `*.ZFS`, `*.fsm`); grep the export for
`undefined4`, `FUN_`, `local_` (decompiler residue) and for the GOG install path; `THIRD-PARTY.md` lists anet-0.10
and DX5 headers; push to a new repo; tag `2026.10`.

---

## 8. Outreach

Where the community is (from `docs/COMMUNITY-RESOURCES.md`, `OUTREACH-DRAFT.md`, `WINDOWS-PLAYBOOK.md`):
interstate76.com forums and glenrio.interstate76.com (Tuesday-night multiplayer, Xetrem190's Discord); the GOG
Interstate series forum (the "20 FPS" audience; the music-during-cutscenes thread); VOGONS (dgVoodoo/Glide crowd,
dgVoodoo's author reads it); Local Ditch (localditch.com, Greg Schwartz, the stats everyone cites); r/macgaming,
r/emulation, r/retrogaming; PCGamingWiki's Interstate '76 page; CahootsMalone's `interstate-76-stuff` GitHub; Open76
(r1sc / rob518183) and Roanish/i76 GitHub; the route380 I'76 Terrarium (Japanese modding site, Asset Bible).

Order (proposed), each step gated on the previous one not producing a bug report that changes the story:

1. **PCGamingWiki edit** first: passive, factual, highest search reach. Rows: in-mission music fix (no optical drive),
   cutscene-music proxy, the `FPSLimit`-is-ignored / `I76PATCH.DLL` finding, FFB on modern wheels (T300RS, Combined
   pedal mode, close the vendor panel), input.map joystick5 fix, Mac/Deck rows. Cite the repo.
2. **GOG forum** post in the Interstate series board: lead with "your GOG copy already contains the AiO 20 fps
   limiter; here is in-mission music with no CD drive and the cutscene fix". The `OUTREACH-DRAFT.md` body, trimmed;
   remove the "optional HD texture pack" line (retired) and "~19.2 FPS" (now known to be the DxWnd cap, Mac only).
3. **interstate76.com forum**: the community-first framing from the draft; add the Tuesday-night angle (the proxy is
   untested in multiplayer: say so, ask for a tester).
4. **VOGONS**: internals thread. The measured `FPSLimit` matrix, the Strlkup IAT hook (why a winmm proxy fails under
   dgVoodoo), the 15.6 ms GetTickCount jitter and the fixed-step result, u32x's 640x480 hit-test translation.
5. **Open76 and Roanish/i76 issues**: the draft's "formats you may find useful" note, updated: link the public i76-map
   (`REIMPLEMENTATION.md`, `OPEN76-GAPS.md` section for their project, `types/i76_runtime.h`, the byte-exact parsers).
   This is the only post that needs the i76-map repo public first.
6. **Reddit** last (r/macgaming with the Mac screenshot, r/emulation with the save editor), once the forum threads
   have absorbed the first wave of "does it work on X" reports.
7. Not now: GOG Preservation Program / rights-holder contact (`OUTREACH-DRAFT.md` "Background"); it needs the
   sizzle video and a README that reads like a portfolio piece, and a release that has been in players' hands first.

Answer-in-advance lines to keep from the draft: legality (no content, own GOG copy); "do I need AI" (no); widescreen
(4:3 in the exe). Add: "does 60 fps break the jump" (measured: no, with the fixed step; stock 60 fps is the thing the
lore was about), and "is the music fix a cracked DLL" (no: it forwards to GOG's own `strlkup_orig.dll`).
