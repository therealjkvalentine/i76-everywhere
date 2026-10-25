# Patch Kit: the player's own controls kept, CONTROLS.bat, UPDATE.bat (2026-10-25)

Lane: kit-controls-updater (Opus). Issues #96 (setup replaces the player's bindings), #97 (updater), with #99 / OWN-INPUT-MAP-2026-10-25.md
(the design lane's investigation of what fights a player's map; its findings (a)-(e) are folded in here, s.3). Trigger: an outside tester,
an experienced flight-stick player: the kit install replaced his control setup, which is painful to rebuild, and "some items of this patch
still conflicted with it, mostly related to yaw settings with my joystick's hat". The owner also asked for an updater. Code: `3cb79c6`
(scripts), `22f36ac` (README). Kit **0.8.1** built from `22f36ac` as a **draft** release (not published). Harness and logs: lab
`kit-controls\` (`fccafec`). Bench: the laptop (`<bench>\ctl\`), fresh folders from the pristine GOG zips every run.

## 1. Audit: which files hold player state, and what v0.8.0 did to them (measured)

`ctl-test.ps1` on fresh GOG Gold / Nitro + kit v0.8.0 (`935f897`): the player's marked edits **before** the kit (A), the first setup (S1),
edits **after** the install (B), the setup again (S2 = what a new kit version or `--resetup` does), uninstall (U). md5s in
`base-a080-*.log`. GOG 2.1.0.17 md5s: `input.map` 74d2da37 (Gold and Nitro identical), `I76PLYR.DEF` 1bff0146, `nitplyr.def` 4fef5d3c,
`gamekey.def` 58a49bc8, `gamekey.map` 916bf58c, `input.def` 6ba024bf.

| file | holds | v0.8.0 setup | v0.8.0 re-setup / update | v0.8.0 uninstall | 0.8.1 |
|---|---|---|---|---|---|
| `input.map` | every binding the engine reads (AGENTS.md) | **replaced** by the kit map (Gold, dec488ab -> a66a37f7; player's copy only as `input.map.stock-*`); Nitro: the player's map **patched** (blocks appended, e_brake / fire moved) | **replaced again** (player's B edit only as `.before-i76e-*`) | Gold: the pre-kit map back, the B edits dropped (left only in `.before-i76e-*`); Nitro: pre-kit back, B edits **lost, no copy** | kept unless GOG's / a kit layout; see s.2 |
| `_ahk\i76-remap.ahk`, `_ahk\i76-ch-fighterstick.ahk` | the pad / wheel / stick layers (players do edit them) | installed | edits **overwritten, no copy** | removed | edits kept, kit's as `.i76e-default`; uninstall copies an edited one to `_i76e\backup\_ahk\` |
| `I76PLYR.DEF` (Gold) | the game's options block (detail, difficulty, ...) | 3 detail bytes raised whenever they were GOG's defaults - also when the player had changed other options | not touched | **whole pre-kit file back**: options set while the kit was in are lost | raised only when the file is GOG's byte for byte; uninstall puts back only those 3 bytes if the rest changed |
| `nitplyr.def` (Nitro) | Nitro options | not touched | not touched | not touched | same |
| `gamekey.def`, `gamekey.map`, `input.def` | F-key / camera keys | not touched | not touched | not touched | not touched; backed up into `_i76e\backup\pre-kit\` |
| `KEYBOARD.MAP`, `JOYSTICK.MAP` | not read by the engine | not touched | - | - | - |
| joystick calibration | Windows registry (winmm / DirectInput) | not touched (the kit writes no registry; PLAY-i76's opentrack game-detection key is opentrack's, only with head look) | - | - | - |
| `savegame.dir`, `save*.cmp`, `Lee.fot` | bookmarks, pilot | the repo's bookmarks copied in only when there are no saves; never overwritten | kept | kept | same |
| `i76-settings.txt` | the player's launcher settings | written once by the first start, never overwritten | kept | kept | same; UPDATE keeps it |
| `presets\local.psd1` | power-user overrides | not shipped, never written | kept | **deleted** (whole `presets\`) | moved to `_i76e\backup\local.psd1` |
| `dgVoodoo.conf` | renderer | rewritten from `dgVoodoo.wide.conf` at every start (by design: settings go in `i76-settings.txt`) | same | removed (GOG ships none) | unchanged behaviour (a dgVoodooCpl edit is lost at the next start; not in scope, noted) |
| launch-time guard (`PLAY-i76.ps1`) | - | every real boot: a map without joystick `steer` / `throttle` lines (GOG's own 2.1.0.17 map has none) is replaced by `input.map.as-installed` or the newest other backup | - | - | off for mode `own`, off when no joystick is connected, never from `*.i76e-default` / `.pre-update` / `.i76e-last` |

## 2. The rule now (setup-windows.ps1 step 5 / 5b, i76e-prepare.ps1)

- **A control file is replaced only when it is GOG's (md5), absent, a version the kit has shipped, or exactly what the setup wrote last
  time.** "Shipped" = `known-kit-md5.txt`, written by the packager from git history (12 `input.map`, 73 `i76-remap.ahk`, 23
  `i76-ch-fighterstick.ahk` md5s, as stored and CRLF / LF); "wrote last time" = `<game>\i76e-installed.md5` (new). Anything else is
  the player's: **kept**, the kit's version written beside it as `input.map.i76e-default` / `_ahk\<name>.i76e-default`, one yellow line
  in the setup window and the summary ("Your own key bindings (input.map) were KEPT ... CONTROLS.bat switches").
- New controls mode **`own`** (`i76e-controls.txt`): the player's map untouched by every later setup, no key layers in `_ahk\`, mouse wheel
  up = Enter as in `stock`. Chosen by the setup when a map of the player's is found on a folder the kit never set up, and by CONTROLS.bat.
  A player who edits the kit's map after an install stays `i76e` (the launcher decides about the layers, s.3).
- Nitro (`-Controls stock`): the minimal patch is applied only to GOG's map; a player's map is kept and the patched copy of *his* map is the
  `.i76e-default`.
- **Fresh GOG `input.map` = kit-owned** (the coordinator's question): kept that way because CONTROLS.bat "mine" does restore GOG's map in that
  case - measured `u2` (no player edit): `mine` -> `_i76e\backup\pre-kit\input.map` = 74d2da37 = GOG's. The pre-kit backup is taken
  before the first setup by `i76e-prepare.ps1` (`Save-PreKit`); on a folder an older kit set up, its `input.map.stock-*` /
  `.pre-windows-setup` / `I76PLYR.DEF.pre-i76e` stand in. The design lane (OWN-INPUT-MAP s.3a) proposed never writing input.map at install;
  this lane's brief said install over GOG's untouched file, which keeps the zero-step first run for a new player.
- **Uninstall**: `input.map` goes back to the pre-kit map only where the kit had replaced or patched it (its `.stock-*` /
  `.pre-windows-setup` exist or the manifest still claims the file); a version the player changed meanwhile is kept as `input.map.i76e-last`;
  a map the kit never replaced stays. `I76PLYR.DEF`: the pre-kit file back when unchanged since the setup, else only the 3 detail bytes
  (when they still hold the kit's 2 / 2 / 1). `local.psd1` and edited layer scripts into `_i76e\backup\`.

## 3. What fought the player's map at play time (OWN-INPUT-MAP s.2, coordinator items a-e)

| finding | change | evidence |
|---|---|---|
| (a) the launcher started any layer found in `_ahk\` and never looked at the map | `PLAY-i76.ps1`, in a Patch Kit folder (`_i76e\VERSION.txt`) or mode `own`: the map is classified - kit layout by md5 (the manifest, `known-kit-md5.txt`, the kit's current map), mode `stock`, or `i76e-layers.txt` = on (CONTROLS.bat chose the kit's layout, then the player edited it) - else **own**: `i76-remap.ahk` and `i76-ch-fighterstick.ahk` are not started. One line in `play-i76.log`: `controls: own map - your own (md5 03c5e818 is not a kit layout) - pad / wheel / stick key layers OFF ...` / `controls: kit's map - the kit's layout (md5 a66a37f7) - key layers on`. Folders without `_i76e\` (the developer's installs) are unchanged. | `-DryRun` rows in `f-u1.log`: installed kit map -> on; player edit -> OFF; CONTROLS kit -> on; edit after choosing kit -> on (chosen); mine / keep -> OFF. Real-boot census s.5 |
| (b) the wheel layer took any joystick1 with no U axis, an R axis and 11+ buttons as the T300 (a twist-axis flight stick matches) and tapped h / m / i / n on every hat move | `i76-remap.ahk`: `gWheelIsT300` = joystick1's VID:PID from `joyGetDevCapsW` (wMid / wPid) is 044F:B66E / B66F / B66D / B65D (docs/WHEEL-T300.md) or its name has "T300"; WheelPoll bails otherwise | probe on the developer's PC (read-only, no game): joystick1 `044F:B66E`, joystick2 `068E:00F3`; **winmm's name is "Microsoft PC-joystick driver" for both**, so the name test alone would never match - VID:PID carries it |
| (c) the Fighterstick layer took joystick2 by index | `i76-ch-fighterstick.ahk`: scans joysticks 1-16 for 068E:00F3 (docs/FIGHTERSTICK.md) or "Fighterstick" in the name; run mode exits when none (`-device N` still forces an index for learn / test) | the same probe: the stick is 068E:00F3 at index 2, so the developer's setup resolves to the same DEV |
| (d) head look ANALOG silences a native hat glance | `PLAY-i76.ps1`: with an own map that binds `joystick* Hat*`, head look starts DIGITAL (unless the settings file or `-HeadLookMode` says otherwise; Ctrl+Alt+H still cycles); the log line says so | dry run, Nitro own map with the stock patch's hat glance: `...; head look starts DIGITAL (your map binds the joystick hat)` |
| (e) install first, then copy one's own map in: the layers stayed on | covered by (a): the classification runs at every start, so a copied-in map is "own" at the next PLAY.bat without CONTROLS.bat; and the next setup keeps it | `f-u1.log` "player edited" row |

Both AHK scripts pass AutoHotkey 1.1.37.02's load check (`/iLib`, which does fail a broken script: exit 2 on a test file);
`tools\controls-sheet\build.ps1`: sources agree (map a66a37f7, 57 actions, 0 mismatches).

## 4. CONTROLS.bat and UPDATE.bat

- **`CONTROLS.bat`** (`_i76e\i76e-controls.ps1`; `CONTROLS.bat status|keep|kit|mine` without the menu): `keep` = the file as it is, and when it
  is not a kit layout the mode becomes `own` (layers off); `kit` = the current map into `_i76e\backup\input.map.mine-<time>` (edited layer
  scripts too), then `setup-windows.ps1 -ControlsOnly -Controls i76e -ReplaceControls` (Nitro: `stock`), `i76e-layers.txt` on; `mine` = the
  newest `input.map.mine-*`, else `pre-kit\input.map`, then `-Controls own`.
- **`UPDATE.bat`** (`_i76e\i76e-update.ps1`, Windows PowerShell 5.1 only): the releases list API (`/releases?per_page=30`; the kit releases are
  pre-releases, which `/releases/latest` never returns), newest non-draft asset `Interstate76-Patch-Kit-i76-everywhere-v<x.y.z>-<sha>.zip` by
  version; `--check` (exit 10 = an update is there); download to `_i76e\update\`; SHA-256 against the asset's `digest` (refused without one);
  unpack; every file against the new kit's `_i76e\MD5SUMS`; refused if anything but top-level `.bat` / `.md` or `_i76e\` (minus the folder's
  own state: backup, update, extras.env, installed.txt, display.txt, setup.log) would be written; the old files into `_i76e\update\previous\`;
  kit files no longer shipped removed (only if unchanged); a top-level `.bat` the player edited kept as `<name>.pre-update`; then
  `i76e-prepare.ps1 -SetupOnly` for each game in the folder; a summary. `--source <zip>` (+ `--sha256` or `<zip>.sha256`) for tests.
  UPDATE.bat is one line ending `& call exit /b %%errorlevel%%`: the updater overwrites UPDATE.bat while cmd runs it, and cmd would read the
  rest of the new file from the old offset (measured: the test kit's UPDATE.bat grew by a line that echoes GARBAGE; it never printed); the
  `call exit /b` form is also what carries the exit code (plain `& exit /b` returned 0 for an `exit 10`, measured).

## 5. Tests (laptop, fresh pristine folders, `GOG Games\Interstate 76` path with spaces)

| test | result |
|---|---|
| audit v0.8.0 (Gold pre / clean, Nitro pre) | s.1 table, `base-a080-*.log` |
| same with 0.8.1 (`r-c-*.log`) | **every player file kept** through S1 / S2; Gold-pre: mode own, no layers, `.i76e-default` = a66a37f7; uninstall leaves the player's B map; Gold-clean: uninstall -> GOG's map + B as `.i76e-last`, I76PLYR.DEF b8885056 = the player's 0x5C option kept, detail bytes back; Nitro-pre: the player's map never patched, kept through uninstall; `local.psd1` -> `_i76e\backup\` |
| user route `f-u1.log` (Gold, final zip `22f36ac`): setup, edit `input.map` + `I76PLYR.DEF` + `i76-settings.txt` + `local.psd1`, `--resetup` | 4 / 4 KEPT |
| `UPDATE.bat --check` against GitHub (published v0.8.0) | from 0.8.1: "newest v0.8.0 935f897 ... Up to date", exit 0; from a folder claiming v0.7.3: "An update is available: v0.7.3 -> v0.8.0", **exit 10** |
| real download (`r-leg.log` N): `UPDATE.bat --yes` in the v0.7.3-claiming folder | downloaded v0.8.0 (5.8 MB), "SHA-256 matches the release: c39a69c3...", 109 files match MD5SUMS, applied (33 changed, 7 removed); cmd then printed "The batch file cannot be found." because v0.8.0 has no UPDATE.bat (a downgrade only) |
| simulated update `UPDATE.bat --source kit082-test.zip --yes` (newer version, changed shipped map + UPDATE.bat + README) | "kit files: 5 changed"; bindings / options / settings / local.psd1 4 / 4 KEPT; `.i76e-default` = the new kit's map 0115441f; a player who had NOT edited (`r-u2.log`) gets the new kit map (a66a37f7 -> 0115441f) |
| CONTROLS.bat status / kit / edit / mine / keep (`f-u1.log`) | kit -> 0115441f, layers on, own map in `backup\input.map.mine-*`; mine -> 03c5e818 back, mode own, `_ahk` empty of key layers; Nitro (`f-u3.log`) the same with the stock-patched layout |
| v0.8.0 install + edits, then 0.8.1 unzipped over (`r-leg.log` L, the route for existing testers) | input.map, I76PLYR.DEF, edited i76-remap.ahk KEPT; the unedited 0.8.0 fighterstick script recognised as shipped and replaced; uninstall -> GOG's map, the edit as `.i76e-last`, the edited layer script in `_i76e\backup\_ahk\` |
| uninstall after the user route | the player's binding file (mode own after `mine`) stays 03c5e818; I76PLYR.DEF options kept |
| real boots (`boot-job.ps1`, skip movies / cutscenes, `-NoFfb`, FFB off, mute) | not run: bench busy for 90 min, s.5a |

### 5a. Real boots

**Not run.** `boot-job.ps1` (lab `kit-controls\`, scheduled task `i76kc` on the laptop) waited 90 minutes (14:12-15:43) for the bench
lock and for no `i76.exe` / `nitro.exe` on the laptop; the lock passed between the terrain-static, terrain-pass-opt, win1080 and
nitro-lobby lanes the whole time, and two games ran outside the lock (a clean-install Gold folder and the lobby lane's Nitro). It gave up
without touching anything. The launcher changes are covered by the `-DryRun` rows (the same code path up to the helper start; the dry run
prints the `controls:` line and which layers a real run would start), not by a census of running AHK processes. To run it when the bench is
free: copy the kit to `<bench>\ctl\kit081.zip`, `schtasks /run /tn i76kc`, read `<bench>\ctloot-result.txt` (two boots: own map ->
expect no `i76-remap.ahk` process and input.map unchanged after exit; CONTROLS.bat kit -> expect `i76-remap.ahk` running).

## 6. Open

- The two real boots of s.5a (bench busy).
- Hardware rows not run (the developer's console): the T300's buttons / hat still drive the wheel layer with the VID:PID test, the
  Fighterstick layer still finds its stick at index 2, and the tester's case - a twist-axis stick's hat in game with his map. The probe
  shows the IDs resolve as intended; the press test needs hands (OWN-INPUT-MAP s.4 step 5).
- Naming vs the design lane: mode `own` here = its `mine` / `keep`; `input.map.i76e-default` here = its `input.map.i76e`.
- The right-stick glance and XInput parts of `i76-remap.ahk` still act on any first pad when the layer runs (only over a kit layout now).
- `dgVoodoo.conf` is rewritten at every start (a dgVoodooCpl change is lost): unchanged, by design of the settings file.
- A downgrade through UPDATE.bat prints cmd's "The batch file cannot be found." (the old kit has no UPDATE.bat); harmless.
- v0.8.1 is a draft release: publishing it is the owner's call. After publishing, `UPDATE.bat --check` in a 0.8.1 folder reads "Up to date".
