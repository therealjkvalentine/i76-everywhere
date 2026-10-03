# New daily driver: inventory of the current one, and the recipe for the next

Written 2026-10-02 (late evening) from a read-only survey. Nothing under `C:\Users\james\Downloads` was written,
no game was started, the sandbox was only read (a dgVoodoo conf bisect was running in it at the time).
The assembly script `tools\Make-Daily-Driver.ps1` is a **draft: parsed, never run**.

The goal, in the owner's words: a new fully independent, portable daily driver directory that carries the best
new config plus every tweak from the current daily driver (aspect ratio, controls, FFB, config, everything),
playable tomorrow with a friend, saving progress as they go, plus a golden copy to promote future improvements to.

Paths used below:

| name | path |
|---|---|
| current driver (root) | `C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801` |
| current driver (game) | `...\Interstate76-i76-everywhere-portable-20260801\Interstate 76` |
| pristine GOG | `C:\Users\james\i76-map\sandbox-gog\main\app` (2017 Galaxy build, `i76.exe` md5 `9a232dcc`) |
| sandbox | `C:\Users\james\i76-uncap-lab\game` |
| proposed new driver | `C:\Users\james\Games\Interstate76-2026-10-03` (the folder `C:\Users\james\Games` exists and is empty; to be confirmed) |
| proposed golden copy | `C:\Users\james\Games\Interstate76-golden` |

---

## 1. Inventory of the current daily driver

Method: md5 of all 498 files in the driver's game folder, all 371 in the pristine folder, the sandbox's
top-level files, and the 788 files of the portable root outside the game folder. A file is listed here when it is
absent from pristine or differs from it. All stock data (`I76.ZFS`, `DATABASE.MW2`, `miss8\`, `miss16\`, `smk\`,
`music\` 16 mp3s, `SP256\`, `force\`, `BUILDER\`, `ZGLIDE.DLL`, `WIN32.dll`, `SMACKW32.DLL`, `I7_SFRCE.DLL`) is
byte-identical to pristine. Eight pristine files are absent and not needed (GOG launcher / Galaxy pieces:
`GOGLauncher.exe`, `goggame-1207661003.*`, `GameuxInstallHelper.dll`, `webcache.zip`, `glide2x.ovl`).

Size: game folder 484 MB, `Lossless Scaling\` 175 MB, bundled repo clone 3 MB.

### 1.1 Binaries

| file | driver md5 (size) | pristine | sandbox | what it is |
|---|---|---|---|---|
| `i76.exe` | `6319abf7` (1,051,648) | `9a232dcc` (1,050,624) | `85de44a7` | GOG 2019 AiO exe (`60abf7bc`) with one change: the 10-byte `USER32.dll` -> `u32x.dll` import name at file offset 0xBFF84. Confirmed by byte diff against `i76.exe.u32xorig`. The sandbox exe is this file plus 18 bytes: the far-clip file patch (0x239B..0x23D2, 0x4DDE read site) and the camera-rate constant (0xBB928) |
| `i76.exe.u32xorig` | `60abf7bc` | - | `dd245f0c` | the AiO exe before the import rename (rollback file of the u32x deploy) |
| `i76shell.dll` | `fd96f871` (352,256) | `deb41008` | **same** | pack-lineage shell (`8960fa16`) + u32x import rename (0x41228) + the text-entry repair (0x1B52C `41`, 0x1B535 `08`). Identical to the sandbox's |
| `i76shell.dll.orig` | `8960fa16` | - | same | before the u32x rename; differs from pristine GOG in 9,809 bytes (a different shell build, not a small patch) |
| `i76shell.dll.pre-toascii-fix` | `36dab830` | - | same | before the text-entry repair (2 bytes) |
| `u32x.dll` | `544e34bc` (75,264) | - | `05c9a7be` (107,008) | the **2026-08-16 build, without the ghosting fix**. Not the repo's recorded build `a5927cea` (`u32x\u32x.dll`), and not the lab build the sandbox runs now. RELEASE-PLAN's table implied `a5927cea` is deployed; it is not |
| `u32x.dll.ship` | `544e34bc` | - | - | copy of the same |
| `STRLKUP.DLL` | `b910850f` (117,248, 2026-09-05) | `e5951e0f` | `54f2de9d` | an old music-fix proxy: music only, **none of the `I76_*` frame-rate switches**. Repo `music-fix\Strlkup.dll` is `362ce032` (177,152, built 2026-10-02 23:11) |
| `strlkup_orig.dll` | `e5951e0f` (55,808) | (= pristine `Strlkup.dll`) | same | GOG's original, the proxy forwards to it |
| `I76PATCH.DLL` | `a0a113d7` (14,336) | - | absent (`I76PATCH.DLL.disabled`, same md5) | GOG's AiO 20 fps cap, **active** on the driver |
| `I7_SFRCE.DLL` | `687cc35b` | same | same | stock force-feedback module. The Mac `ffb-shim` is **not** installed here |
| `i76wheel.exe` | `4bed1589` (76,800) | - | same | mouse wheel -> keystroke helper; identical to `tools\i76wheel.exe` |
| `Glide.dll` / `Glide2x.dll` / `Glide3x.dll` | `259a4028` / `8af442bc` / `829f80cd` | OpenGLide (`3059133e` / `c319a4f3` / -) | same | dgVoodoo 2.87.3 Glide (file versions 1.1.0.1 / 2.60 / 3.10) |
| `DDraw.dll`, `D3DImm.dll`, `D3D8.dll`, `D3D9.dll` | `ab19386d`, `c6bdfc62`, `4127f3d9`, `9b8e4916` | - | same | dgVoodoo 2.87.3 DirectX wrappers |
| `dgVoodooCpl.exe` | `487da424` (2.8.7.3) | - | same | dgVoodoo control panel |
| `goggame.dll`, `gfw_high.ico`, `i76car.def`, `I76DFLT.DEF`, `DLL\WINET.DLL`, `internet.lst`, `OpenGLid.ini` | - | differ / absent | same | GOG 2019 offline-installer differences against the 2017 Galaxy build; not ours |
| `_ahk\AutoHotkeyU32.exe` | `b6af97aa` (1.1.37.02) | - | same | AutoHotkey 1.1 |

Not present anywhere on the driver: `smackorg.dll` (cutscene-music proxy), `dsound.dll`, `winmm.dll`, `nitro.exe`,
`_ffb\`.

### 1.2 dgVoodoo configuration

`Interstate 76\dgVoodoo.conf`, md5 `71bd2071`, 7,469 B, ASCII only, `Version = 0x287`. It is the same file family
as the sandbox's conf (the sandbox's `dgVoodoo.conf.bak-focus` is byte-identical to it) and as the repo's
`dgVoodoo.windows.conf` (same keys, one value apart). Key by key, against the sandbox's conf as it was before
tonight's bisect (`game\dgVoodoo.conf.pre-bisect`, md5 `9ca5a4d3`) and the 2020 global file:

| key | driver | sandbox | repo `dgVoodoo.windows.conf` | global 2020 file |
|---|---|---|---|---|
| `Version` | 0x287 | 0x287 | 0x287 | **0x270** |
| `[General] OutputAPI` | d3d11_fl10_1 | same | same | bestavailable |
| `[General] FullScreenMode` | false | same | same | **true** |
| `[General] ScalingMode` | stretched_ar | same | stretched | stretched_ar |
| `[General] KeepWindowAspectRatio` | false | same | same | true |
| `[General] CaptureMouse` | true | same | same | true |
| `[General] CenterAppWindow` | true | same | same | false |
| `[GeneralExt] FPSLimit` | **19.2** | **21** | 19.2 | absent |
| `[GeneralExt] Resampling` | bilinear | same | same | bilinear |
| `[GeneralExt] FullscreenAttributes` | fake | same | same | absent |
| `[GeneralExt] WindowedAttributes` | **borderless** | **border** | borderless | empty |
| `[GeneralExt] FreeMouse` | false | same | same | false |
| `[Glide] VideoCard` | voodoo_graphics | same | same | voodoo_rush |
| `[Glide] OnboardRAM` | 4 | same | same | 2 |
| `[Glide] MemorySizeOfTMU` / `NumberOfTMUs` | 2048 / 1 | same | same | 2048 / 1 |
| `[Glide] TMUFiltering` | bilinear | same | same | appdriven |
| `[Glide] Resolution` | **1680x1050** | **3360x2100** | 1680x1050 | h:1920, v:1440 |
| `[Glide] Antialiasing` | 8x | same | same | appdriven |
| `[Glide] EnableGlideGammaRamp` | true | same | same | true |
| `[Glide] ForceEmulatingTruePCIAccess` | true | same | same | false |
| `[Glide] ForceVerticalSync` | false | same | same | **true** |
| `[Glide] 3DfxWatermark` | false | same | same | **true** |
| `[Glide] 3DfxSplashScreen` | false | same | same | false |
| `[Glide] EnableInactiveAppState` | true | same | same | false |
| `[GlideExt] DitheringEffect` / `Dithering` / `DitherOrderedMatrixSizeScale` | pure32bit / forcealways / 0 | same | same | same |
| `[DirectX] VideoCard` / `VRAM` | internal3D / 256 | same | same | internal3D / 2048 |
| `[DirectX] Resolution` | 1680x1050 | same | same | h:1920, v:1440 |
| `[DirectX] dgVoodooWatermark` | false | same | same | **true** |
| `[DirectX] AppControlledScreenMode` | **true** | **false** | true | true |
| `[DirectX] DisableAltEnterToToggleScreenMode` | false | same | same | true |
| `[General] EnableInactiveAppState` | absent | true | absent | absent |
| `[DirectX] EnableInactiveAppState` | absent | true | absent | absent |

So the driver's deliberate differences from the sandbox are five: `FPSLimit 19.2`, `WindowedAttributes borderless`,
Glide `Resolution 1680x1050` (the sandbox renders at twice that), `AppControlledScreenMode true`, and no
`EnableInactiveAppState` outside `[Glide]`.

**The second conf: `%APPDATA%\dgVoodoo\dgVoodoo.conf`** (md5 `5d3906a0`, 15,610 B, dated 2020-11-27, written by a
dgVoodoo 2.7 control panel run for another game; `dgVoodooSetupPaths.dat` beside it names
`Downloads\NerfArenaBlast\System`). At survey time it was renamed `dgVoodoo.conf.hidden-by-bisect` by the running
bisect (`i76-uncap-lab\tools\graphics\conf-bisect.ps1`), which restores the name when it ends.

What tonight's finding means for the driver: dgVoodoo 2.87.3 was seen to reject the sandbox's local conf and take
the global one. The driver's conf has the same keys and the same syntax, so **it has to be assumed rejected in the
same way until the bisect names the lines**. If it is, what the owner has been seeing on the daily driver is the
2020 global file, not the table's "driver" column: fullscreen, `KeepWindowAspectRatio true`, internal resolution
1920x1440, vsync forced, and both watermarks on. Two cheap observations settle it at the console: is a dgVoodoo /
3dfx watermark visible in the corner on the current driver, and does the 3D scene look rendered at 1440 lines.
The only on-disk trace is the driver's `u32x.log` (2026-08-15): `scale=3.000 org=(760,0)`, a 1920x1440 4:3 image
centred on a 3440-wide desktop, which both confs would produce, so it does not decide the question.

A portable folder must not depend on that APPDATA file. The new folder needs a local conf that dgVoodoo accepts
(the integrator supplies it), and the acceptance test must be run with the global file hidden, the way the bisect
does.

Backups beside the live conf: `dgVoodoo.conf.pre-mousefix` (identical to live), `.pre-cursorAB` and
`.pre-cursordisplay` (`1a4d1ac5`: `CaptureMouse = false`), `.pre-cursor-mode` (`b7272dad`, comment differences
only).

### 1.3 Controls

- `input.map`: md5 `a937f36d`, 7,055 B, 2026-08-08, identical to the sandbox's. Lint (read-only):
  `OK ... all actions/tokens present in i76.exe, no traps`. Buttons live in the AHK layer, analog sinks in the map.
- Backups: `input.map.bak-20260808-known-good` (identical to live; the launcher's guard restores from it),
  `.bak-20260808-111958`, `.pre-wheel-ahk-20260808`, `.pre-wheelbuttons-20260802-203633`,
  `.CORRUPTED-20260802-183747` (3,234 B, the menu-corrupted specimen).
- `_ahk\` (10 files): `i76-remap.ahk` `71c1084e` (2026-08-08, the wheel layer), `i76-ch-fighterstick.ahk`,
  `i76-cursor-overlay.ahk` `73f1cf02`, `i76-opentrack-headlook.ahk`, `i76-opentrack-autostart.ahk`,
  `i76-opentrack-headlook-test.ahk`, `i76-camsweep.ahk`, AutoHotkey exe + chm + licence.
  Against the repo: fighterstick and the three opentrack scripts are identical. **`i76-remap.ahk` differs**: the
  repo copy has the Mac ffb-shim gate (`gShimOwnsRumble := true`, which switches this layer's pad rumble off) and a
  calmer rumble texture; the driver's copy drives the rumble itself. The driver has no shim, so the driver's copy
  is the right one here. `i76-cursor-overlay.ahk` also differs from the repo (4,037 vs 4,141 B).
- `i76wheel.exe`: started by `PLAY-i76.ps1` with `/up=Tab /down=5`.

### 1.4 Force feedback

- Stock path: `I7_SFRCE.DLL` (pristine) + `force\` (14 files, pristine). No shim, no config file of ours.
- Registry on this machine: `HKLM\SOFTWARE\WOW6432Node\Activision\Interstate '76` has `EXE = i76.exe` (what
  `enable-force-feedback.bat` writes) and `...\Interstate '76 Gold Edition` has `Minimum = 0`. Per i76-map L084 no
  registry value gates FFB in the exe, and the AiO exe returns 0 from `startup_IsMinimum` without reading the
  registry, so neither key is a dependency of a portable folder on the AiO exe. They are machine state and stay.
- `enable-force-feedback.bat` in the game folder, identical to the repo's.
- Custom FFB (`PLAY-i76.ps1 -Ffb`, `tools\ffb\`): not on the driver (no `_ffb\`); the launcher falls back to the
  repo path, which does not exist beside the driver's script, so it has never run from this folder.
  `tools\ffb\FfbMixer.ps1` is modified and uncommitted in the repo right now.

### 1.5 Launchers and how he starts it

Desktop shortcuts (both): `Interstate '76 (FrameGen).lnk` and `PLAY-with-FrameGen.bat - Shortcut.lnk` ->
`<root>\PLAY-with-FrameGen.bat`, working directory `<root>`, no arguments. That .bat starts the **bundled**
`Lossless Scaling\LosslessScaling.exe` (3.2.2.0), waits 3 s, then runs
`powershell -File "Interstate 76\PLAY-i76.ps1" -GameDir "<root>\Interstate 76" -Exe i76.exe` hidden.

| top-level file | what |
|---|---|
| `PLAY.bat` | the same without Lossless Scaling |
| `PLAY-with-FrameGen.bat` | above; the one the shortcuts point at |
| `Setup-This-PC.bat` / `.ps1` | writes a desktop shortcut to `PLAY.bat` |
| `Setup-FrameGen.ps1` | writes the Lossless Scaling profile (identical to the repo's) |
| `HEADTRACK.bat`, `HEADTRACK-TEST.bat`, `CAMSWEEP.bat` | start one AHK script each from `_ahk\` |
| `i76-save-editor.html` | `d1e609bf`, 2026-07-21: the **pre-correction** editor (misframed records); the repo's is `b270a635` |
| `READ-ME-FIRST*.txt` | portable notes |
| `Lossless Scaling\` | 440 files, 175 MB, the licensed app |
| `i76-everywhere\` | a July clone of the repo with `.git` (HEAD `55a7baf`); stale, nothing reads it |

`Interstate 76\PLAY-i76.ps1` is the 2026-08-08 version (`24e07cce`, 20,211 B): no `-Preset`, no cursor-overlay
start, `MusicVolume 550`. What it starts: `i76wheel.exe`, `_ahk\i76-remap.ahk`, `_ahk\i76-ch-fighterstick.ahk`,
opentrack from `C:\Program Files (x86)\opentrack\opentrack.exe` (**installed on this machine**, not in the
folder) plus its two AHK helpers, Lossless Scaling from the Steam path (which does **not** exist here, so only the
FrameGen .bat brings it up), then `i76.exe -glide` with the game folder as working directory.
`Interstate 76\PLAY-i76.bat` and `PLAY-i76-dgvoodoo.bat` are older direct launchers.

Machine state outside the folder that the current setup uses:

| what | where | needed by the new folder? |
|---|---|---|
| Lossless Scaling profile "Interstate '76 Gold Edition" (LSFG3 fixed x2, target 60, scaling off, auto-scale by window title) | `%LOCALAPPDATA%\Lossless Scaling\Settings.xml` | only for frame generation; matches by title, so it follows the game to any folder |
| opentrack + profile (`protocol-dll=freetrack`, neuralnet tracker, Insta360 camera) | `C:\Program Files (x86)\opentrack`, `Documents\opentrack-2.3\default.ini` | only for head tracking |
| global dgVoodoo conf | `%APPDATA%\dgVoodoo\` | **must not be** (1.2) |
| Activision registry keys | HKLM WOW6432Node | no (1.4) |
| AppCompat layers | none for the driver's path (entries exist for `C:\GOG Games`, `C:\I76-stable`, Program Files copies) | no |

### 1.6 Saves and player state

`python i76-save-editor.py --dir <game> --list` and `--check` (read-only): `savegame.dir` 8 records, 484 B
(exact), every file round-trips.

| slot | file | scene | state | name | car |
|---|---|---|---|---|---|
| 0 | save000 | 1 | 1 | '' | Picard Piranha / Stock (26 A + 8 C) |
| 1 | save001 | 2 | 1 | '' | Picard Piranha (39 A + 2 C) |
| 2 | save002 | 3 | 1 | '' | Picard Piranha (52 A + 8 C) |
| 3 | save003 | 5 | 8 | '' | Picard Piranha (64 A + 8 C) |
| 4 | save004 | 6 | 8 | '' | Picard Piranha (58 A + 0 C) |
| 5 | save005 | 6 | 8 | 'a' | same bytes as save006 |
| 6 | save006 | 6 | 8 | 'z' | Picard Piranha (58 A + 0 C) |
| 7 | save007 | 5 | 8 | 'tret' | Picard Piranha (64 A + 8 C), written 2026-09-07 15:36 |

Other state: `reconfig.spc` (9,560 B, 61 A + 2 C), `trip4.spc` (9,212 B; `--check` warns: 12 mounted records for
11 equipped names, `BloxDropper`), `user.mel`, `user.rpr`, `I76PLYR.DEF` (96 B), `Lee.fot`, `NSCR.DAT`,
`victory.rec`, `multicar.def`. The sandbox's saves 003-007 and `savegame.dir` differ from the driver's (the
sandbox holds a different nine-bookmark set); the driver's set is the one to carry.

Save backups inside the game folder (kept, set aside by the recipe): `save-backup-20260906-075854\`,
`-20260906-084202\`, `-20260907-145930\` (the 14-bookmark scene 2-15 set, `savegame.dir` 880 B),
`save-backup-scene7-20260905-214022\`, `weekend-state-20260907-145922\` (also a conf, a shell DLL and a
`u32x.dll` `251baee9`), `savegame.dir.pre-pad-scene7`, two `savegame.dir.trunc-*`, `reconfig.spc.bak-153849`.

### 1.7 Mods and music

- `ADDON\`: `valepre4.vcf` (2026-07-09), `a2fnsg1m.cbk` (2026-07-10), `vehscn.vcf` / `vehscn.vsf` (rewritten by
  the game, 2026-09-07), plus the stock five. `NVCL\nvcl0.vcf` (2026-08-09). These are the owner's car/mod files.
- `music\`: the 16 GOG mp3s, identical to pristine. Music works through the old proxy (`mciproxy.log`, 449 KB,
  last written 2026-09-07).
- `tools\i76-music.ps1`: the external-player stopgap; the launcher leaves it off when `strlkup_orig.dll` exists.

### 1.8 Residue (carried aside, not into the playable folder)

`DDraw.dll.old-278`, `Glide2x.dll.dgvoodoo` (same as `Glide2x.dll`), `i76.25fps`, `i76.exe.2017galaxy`
(`9a232dcc`, the pristine exe), `winmm.dll.bak`, `DDrawCompat-i76.log`, `OpenGLid.log`, `u32x.log`,
`mciproxy.log`, `grep.exe.stackdump`, `histogram.txt`, and every `*.pre-*` / `*.bak-*` / `*.trunc-*` file above.

---

## 2. Decisions the recipe makes, and why

1. **Game data: copy the current driver's game folder, not pristine and not the sandbox.** The driver is GOG's
   2019 offline (AiO) build with every stock data file md5-equal to pristine, plus the owner's `ADDON\` / `NVCL\`
   mods, `input.map`, AHK layers and saves. Pristine is the 2017 Galaxy build (different exe and shell, no
   `I76PATCH.DLL`, OpenGLide), and the sandbox carries probe saves, experiment backups and a conf under bisect.
2. **Proxy: `music-fix\Strlkup.dll` from the repo at the commit the integrator gates** (`362ce032` at survey
   time), with the driver's `strlkup_orig.dll` (`e5951e0f`) kept. The driver's old proxy is set aside as
   `STRLKUP.DLL.driver-b910850f`.
3. **u32x: the build the integrator names.** The script defaults to the repo's recorded `u32x\u32x.dll`
   (`a5927cea`, Aug-16 + ghosting fix) and refuses any md5 that is not in `u32x\deploy-u32x.ps1`'s `$KnownGood`
   unless `-AllowUnrecordedU32x` is passed. The driver's exe and shell already import `u32x.dll`, so only the DLL
   file is replaced; no import table is touched.
4. **dgVoodoo: the driver's 2.87.3 DLLs unchanged, plus the fixed conf from the integrator** (`-DgVoodooConf`,
   mandatory). The values to preserve from the driver are the "driver" column of 1.2, unless the console check
   shows the owner has really been playing the global file's settings, in which case those are "his aspect ratio".
5. **Preset: `smooth-120`** in `PLAY.bat` (the display reports 179 Hz). `lab-all` is the 60 fps lab reproduction
   with telemetry and is not a play preset. See open question 2: neither file is exactly the set played tonight.
6. **`I76PATCH.DLL` is renamed `I76PATCH.DLL.disabled` in the new folder**, as in the sandbox; otherwise every
   preset runs under GOG's 20 fps cap.
7. **Controls, FFB, wheel: the driver's own files, byte for byte** (`input.map`, its known-good backup, all of
   `_ahk\`, `i76wheel.exe`, `I7_SFRCE.DLL`, `force\`, `enable-force-feedback.bat`). The repo's `i76-remap.ahk` is
   deliberately not used (1.3).
8. **Launcher: the repo's current `PLAY-i76.ps1` + `presets\`**, started by a generated `PLAY.bat`. It sets the
   working directory to the game folder and hands the preset's variables to the game process only. Behaviour
   changes against the driver's August launcher: it also starts `_ahk\i76-cursor-overlay.ahk`, and Lossless
   Scaling is off unless `PLAY-with-FrameGen.bat` is used.
9. **Nothing is dropped.** Backups, logs and experiment leftovers go to `_carried-over\Interstate 76\`.

---

## 3. The recipe, in order

Preconditions: physical console (`[System.Windows.Forms.SystemInformation]::TerminalServerSession` is False), no
`i76` process running, the conf bisect finished and `%APPDATA%\dgVoodoo\dgVoodoo.conf` back under its own name.

1. **Freeze the inputs** and write their md5s down: `music-fix\Strlkup.dll`, the named u32x build, the fixed
   `dgVoodoo.conf`, the repo commit (`PLAY-i76.ps1`, `presets\`). If the u32x build is new, add its md5 to
   `$KnownGood` in `u32x\deploy-u32x.ps1` in the same commit that records its gate (u32x\README.md, "Promoting a
   rebuild").
2. **Dry plan** (writes nothing):
   `tools\Make-Daily-Driver.ps1 -Source <driver root> -Dest <dest> -DgVoodooConf <fixed conf> -U32xDll <build> -Plan`
3. **Build the gate twin inside the lab**, because the harness only drives processes whose path contains
   `i76-uncap-lab` (section 5):
   `-Dest C:\Users\james\i76-uncap-lab\game-dd-20261003` (the lab ignores `game-*/`). No `-GoldenDest` yet.
   The script then, in this order:
   1. refuses if the dest exists, lies inside the source, or the game is running from the source;
   2. fingerprints the source (count, bytes, newest write time);
   3. copies the driver's game folder to `<dest>\Interstate 76\`, residue to `<dest>\_carried-over\`, the top-level
      helper .bats and `Lossless Scaling\` to `<dest>\`, verifying every copy by md5;
   4. overlays `STRLKUP.DLL`, `u32x.dll`, `dgVoodoo.conf`, `PLAY-i76.ps1` (and `i76.exe` only if `-GameExe` is
      given), each time moving the driver's file to `<name>.driver-<md5 8>` beside it;
   5. copies `presets\*.psd1`, renames `I76PATCH.DLL` to `.disabled`, adds the current save editor (`.html`, `.py`)
      and the linter at the root;
   6. writes `PLAY.bat` (`-Preset smooth-120 -LosslessScaling none`), `PLAY-stock.bat`, `PLAY-with-FrameGen.bat`,
      `BACKUP-SAVES.bat`;
   7. runs the read-only checks (lint, `--check`, shell bytes, `savegame.dir` size, imports) and writes
      `MANIFEST.md` with every file's md5 and origin;
   8. fingerprints the source again and fails loudly if anything changed.
4. **Run the unattended checklist on the twin** (section 5.1).
5. **Build the real folder from the same inputs**, with the golden copy:
   `-Dest C:\Users\james\Games\Interstate76-2026-10-03 -GoldenDest C:\Users\james\Games\Interstate76-golden`.
   Compare the two `MANIFEST.md` file tables: every md5 must match the twin's as built (the twin's saves and logs
   will have moved on during the gate; compare against the twin's manifest, not its current files).
6. **Hand checks at the console** on the real folder (section 5.2), then point the desktop shortcut at the new
   `PLAY.bat` (the script creates no shortcut; `Setup-This-PC.ps1` logic can be reused by hand).
7. **Leave the old driver exactly where it is.** It is the rollback for tomorrow: its shortcut still works.

The saves copied are whatever the driver holds at the moment of step 5. If the owner plays the old driver between
the twin and the real build, the real build picks the newer saves up; the manifest shows it.

---

## 4. Playing with a friend: keeping both players' progress

- The game has one save index (`savegame.dir`) and no profiles. Progress is kept as **bookmarks**: each is a
  `saveNNN.cmp` plus a 60-byte record in `savegame.dir`. `reconfig.spc`, `tripN.spc`, `user.*` and `I76PLYR.DEF`
  are working state shared by whoever is driving.
- **Each player saves under his own bookmark name.** On the Save Bookmark screen the name field is pre-filled with
  the loaded bookmark's name: keeping it overwrites that bookmark (the game asks), typing a different name makes a
  new slot. Agree on a prefix per player (for example `J-` and the friend's initial) so a pre-filled name is never
  the other player's.
- When swapping drivers: save, back to the main menu, LOAD BOOKMARK, pick the other player's row. The garage
  inventory comes from the loaded bookmark.
- **Back up after each session**: `BACKUP-SAVES.bat` at the root copies the whole save set to
  `save-backups\<timestamp>\` (it refuses while the game runs). Restore = copy a set back with the game closed.
- **Never bind controls in the in-game menu** (it rewrites `input.map`); the launcher's guard restores the analog
  sinks from `input.map.bak-20260808-known-good` if that happens.
- **Save editor warning (the 11-weapon cap).** The garage's weapon list shows 11 records. A mounted weapon that
  falls past the 11th weapon record in file order reads EMPTY in the garage ("my weapons vanished"). So when
  adding weapons with the editor, keep at most 11 weapon records ahead of and including every mounted one, run
  `python i76-save-editor.py --dir <game> --check` afterwards, and edit only with the game closed. `trip4.spc`
  already carries a related warning (12 mounted records for 11 equipped names). Use the editor shipped at the new
  root, not the July `i76-save-editor.html` of the old driver (that one misframes records).
- The repo's `saves\` set (scenes 2-15, `saves\Install-Saves.ps1`) is not installed by the recipe; it would
  replace the owner's index. If the friend should be able to start from any scene, that is a separate, announced
  step with `BACKUP-SAVES.bat` run first.

---

## 5. Verification

### 5.0 What the lab harness can and cannot be pointed at

The task brief assumed the harness takes paths. It does only partly:

| script | game folder | note |
|---|---|---|
| `autotest\proxy-run.ps1` | `-GameDir`, but refuses anything outside `i76-uncap-lab` or under `Downloads` | installs `-Dll` (default `music-fix\Strlkup.dll`) over `STRLKUP.DLL` for the run |
| `autotest\test-escmenu.ps1` | `-GameDir`, same refusal | |
| `autotest\saves\leg-b.ps1`, `leg-a.ps1` | **hard-coded** `C:\Users\james\i76-uncap-lab\game` | also scrub `I76_*`, back the saves up inside the game folder, swap `STRLKUP.DLL` and restore it |
| `autotest\option6-trip-test.ps1` | hard-coded: it starts `TEST-FRAMERATE.ps1`, which uses `game\` | |
| `autotest\menu-route-test.ps1` | hard-coded | |
| `autotest\lib\memlib.ps1` `Mem-Open`, `focuslib.ps1` `Get-GamePid` | `-RequirePath 'i76-uncap-lab'` default | a process outside the lab is not found unless the caller passes another `-RequirePath` |

Hence the twin at `i76-uncap-lab\game-dd-20261003\Interstate 76` (its path satisfies the `RequirePath` filter and
`proxy-run`'s guard), and two small harness changes the integrator has to make before the route tests can run on
it: a `-GameDir` parameter on `leg-b.ps1` (replacing the hard-coded `$G`), and a launch parameter on
`option6-trip-test.ps1` so it starts the twin's `PLAY-i76.ps1 -Preset smooth-120` instead of `TEST-FRAMERATE.ps1`.
Both scripts swap `STRLKUP.DLL` for the run; on the twin that is a no-op when the same build is already installed,
but they leave `save-backup-<ts>\` folders behind, which is the reason the gate runs on a twin and not on the
folder that will be played.

### 5.1 Unattended checklist (integrator, on the twin, console session, global conf hidden)

Run each once as a control on the unchanged sandbox first where a pass/fail is being compared (A/A before A/B),
and record n.

| # | check | how | pass |
|---|---|---|---|
| 1 | assembly checks | read `MANIFEST.md` "Checks at assembly" | lint OK; `--check` round-trips; shell bytes `41/08`; `savegame.dir` exact; both binaries import `u32x.dll`; `strlkup_orig.dll` present; `I76PATCH.DLL` inactive |
| 2 | launcher dry run | `PLAY-i76.ps1 -GameDir <twin game> -Preset smooth-120 -DryRun` | prints the eight `I76_*` values, cwd = the game folder; the only notes are "music-fix\Strlkup.dll not found beside this script" (expected in a standalone folder) and no I76PATCH note |
| 3 | conf accepted **without** the global file | with `%APPDATA%\dgVoodoo\dgVoodoo.conf` renamed away: start, read the client rect (the bisect's `Trial` function) | borderless full-screen client, not 640x480; no watermark; restore the global file's name afterwards |
| 4 | direct mission boot with the preset | `proxy-run.ps1 -GameDir "..\game-dd-20261003\Interstate 76" -Set stock -Env @{<the smooth-120 values>} -Mission t01` | log lines `hires-clock: 2/2`, `fixed-step`, `render-interp: 3/3 hooks`, refresh override; ~120 fps on the proxy counter; music `MCI_PLAY` |
| 5 | bookmark route (leg-b B1) | `leg-b.ps1 -GameDir <twin game> -Mode b1 -WantFile save006 -WantRow 6 -RowUy 330` (the driver's set has save006 at row 6) | 3 of 3 to the mission (player entity exists, frame counter advancing). This is the route the withdrawn u32x build broke |
| 6 | option-6 equivalent | the click route TRIP -> LOAD BOOKMARK -> row -> LOAD -> ACCEPT SALVAGE -> DONE, launched through the twin's `PLAY.bat` environment | engine up, ~120 fps, 2 of 2 |
| 7 | save screen | the section 7 procedure of lab `docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md` (10 s idle on Save Bookmark, row click, SAVE twice) | overwrite prompt appears and answers; `savegame.dir` still exact afterwards (`--check`) |
| 8 | Esc menu | `test-escmenu.ps1 -GameDir <twin game> -Stage open/click/close` | only if the named u32x build claims the Esc-menu fix; with `a5927cea` the keyboard is the documented way |
| 9 | FFB device | in a mission, with the wheel plugged in before launch: `tools\check-ffb.ps1` (it finds the running game itself; run it in a mission, not at the menu) | module loaded, device present (`[0x52bbe4] != 0`) |
| 10 | input | `python tools\lint-input-map.py <twin game>` after all runs | still OK, md5 still `a937f36d` |
| 11 | manifest drift | re-hash the twin against its `MANIFEST.md` | only saves, logs, `reconfig.spc`, `user.*`, `vehscn.*` and harness backups changed; no binary, conf or map |

### 5.2 Hand checks left for the owner (real folder)

1. `PLAY.bat` from the new folder: reaches the menu; the picture has the aspect ratio and sharpness he expects; no
   dgVoodoo or 3dfx watermark.
2. Wheel: steering, pedals, buttons through the AHK layer, force feedback felt in a mission.
3. Load his latest bookmark (`tret` / scene 5 or `z` / scene 6), drive, save under a new name with the mouse,
   quit, relaunch, the new bookmark loads.
4. Music plays in a mission and the volume slider works.
5. 120 fps feel: jumps, body roll, the flamer, the oil slick sound.
6. Head tracking and frame generation, if he uses them tomorrow (`HEADTRACK.bat`, `PLAY-with-FrameGen.bat`).
7. The friend saves under his own name; `BACKUP-SAVES.bat` afterwards.

---

## 6. Golden copy

**Layout** (`-GoldenDest`, written by the script from the verified dest, file for file by md5):

```
Interstate76-golden\
  GOLDEN-DO-NOT-PLAY.txt      what this folder is, and where the playable one lives
  MANIFEST.md                 every file: path, bytes, md5, origin (copy of the driver's at assembly)
  PROMOTIONS.md               the log, one row per promotion; row 0 = the initial assembly
  PLAY.bat  PLAY-stock.bat  PLAY-with-FrameGen.bat  BACKUP-SAVES.bat  ...
  Interstate 76\              the game as assembled (saves = the snapshot at assembly, never updated)
  Lossless Scaling\           if carried
  _carried-over\              the old driver's backups and residue
  _rollback\<id>\             files replaced by promotion <id> (created by the first promotion)
```

The three folders and their roles after tonight:

| folder | role | who writes it |
|---|---|---|
| sandbox `i76-uncap-lab\game` (and `game-*` twins) | experiments and gates | harness, agents |
| golden | the last gated configuration, byte-exact; never played, never tested in | promotions only |
| daily driver `Games\Interstate76-2026-10-03` | play | the game (saves), promotions |

**A promotion** (one change, for example a new `Strlkup.dll`):

1. Gate it on the sandbox or a twin: the checklist rows that the change can affect, with a control run, n recorded.
2. In the golden copy: move each file being replaced to `_rollback\<id>\<relative path>`, copy the new file in,
   read its md5 back.
3. Add a row to `PROMOTIONS.md`: id, date, what, each file's md5 before -> after, the gate (what was run, n,
   result), the rollback folder. Update the affected rows of `MANIFEST.md`.
4. Apply the same file replacement to the daily driver with the game closed, keeping the replaced files in the
   driver's own `_rollback\<id>\`. Never copy the golden copy's save files or `input.map` over the driver's.
5. Verify: for every file in the manifest that is not player state (saves, `savegame.dir`, `*.spc`, `user.*`,
   `I76PLYR.DEF`, `vehscn.*`, logs), driver md5 == golden md5.

**Rollback**: copy `_rollback\<id>\` back over the same paths in the driver (and in golden), newest id first if
several are being undone, and add a `PROMOTIONS.md` row saying so. Because the golden copy is byte-exact, a damaged
driver can also be rebuilt from it: copy golden to a new folder and copy the driver's save set (or the newest
`save-backups\<ts>\`) into it. The old July driver in `Downloads` stays untouched as the rollback of last resort.

---

## 7. Open questions for the integrator

1. **Which `i76.exe`.** The script keeps the driver's `6319abf7` (AiO + u32x import). Every gate tonight ran on
   the sandbox's `85de44a7` (the same exe + the far-clip file patch at 1800 m with x16 pools + the camera-rate
   constant). The proxy handles both layouts by design, but the smooth-120 set on `6319abf7` with `I76PATCH.DLL`
   renamed has not been run. Either gate the twin as built (preferred: fewer file patches), or pass
   `-GameExe C:\Users\james\i76-uncap-lab\game\i76.exe` and say so in the manifest.
2. **Which preset is "the best new config".** The owner's option 6 (`TEST-FRAMERATE -Mode all120`) is `lab-all` +
   `I76_GLIDE_REFRESH=120`: it includes `I76_FAR_CLIP=1800` and `I76_TELEMETRY=1`. `smooth-120.psd1` has neither;
   `lab-all.psd1` has no 120. If 1800 m draw distance is part of what he liked, a new preset file is needed
   (`PLAY-i76.ps1 -Preset` also accepts a path to a `.psd1`), or the file-patched exe of question 1. Tonight's
   opt-in switches (`I76_COLL_WINDOW`, `I76_AI_FIXES`, `I76_FAR_ENGINE_DT`, `I76_MIRROR_RATE`) are in no preset.
3. **Which u32x build.** Four candidates exist: driver `544e34bc` (Aug-16), repo `a5927cea` (recorded), sandbox
   `game\u32x.dll` `05c9a7be` (the build STATUS calls gated at 23:30), and lab `src\u32x_new.dll`, which at survey
   time was already a **different, newer** file (`62158845`, 23:07; the lab HEAD adds `I76_U32X_VPTR`). Name the
   md5, not the file name.
4. **Is the driver's conf rejected too, and what has the owner actually been looking at?** (1.2.) The fixed conf
   should reproduce what he sees today. Decide the sandbox-only values as well: Glide `Resolution` 1680x1050 vs
   3360x2100, `WindowedAttributes`, `AppControlledScreenMode`, `FPSLimit` (ignored on this build per the
   framerate matrix, but 19.2 would matter if a future dgVoodoo honoured it under a 120 preset: remove it or set 0).
5. **Lossless Scaling by default?** The owner launches through `PLAY-with-FrameGen.bat` today (LSFG x2 on 20 fps).
   The generated `PLAY.bat` leaves it off because the preset renders 120 real frames; the FrameGen .bat is still
   written. The LS profile is machine state and will engage on the new folder if LS is running.
6. **opentrack** is installed software, not in the folder; the launcher starts it from Program Files if present.
   Fine on this machine; a truly portable copy would need `Make-Portable-Zip.ps1 -IncludeHeadTrack`'s staging.
7. **Cursor overlay**: the repo launcher starts `_ahk\i76-cursor-overlay.ahk`; the driver's August launcher never
   did. With a u32x build that fixes the save-screen mouse it may be redundant or a second pointer.
   `-NoCursorOverlay` in `PLAY.bat` restores the old behaviour.
8. **Harness changes needed for the gate** (5.0): `-GameDir` on `leg-b.ps1`, a launch parameter on
   `option6-trip-test.ps1`. Without them only rows 1-4 and 8-11 of the checklist run unattended on the twin.
9. **Final location**: `C:\Users\james\Games\Interstate76-2026-10-03` and `...\Interstate76-golden` are proposals.
10. **Doc drift found on the way**: RELEASE-PLAN section 1 says the driver's `Strlkup.dll` is older than
    `fe82a0ee` (the repo is at `362ce032` now) and implies the deployed u32x is `a5927cea` (it is `544e34bc`).
    Not corrected here; this commit touches two paths only.
