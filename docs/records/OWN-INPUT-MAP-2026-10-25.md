# A player's own input.map: what the kit did to it, what the kit-controls lane has already fixed in the tree, what still fights it (2026-10-25, draft)

Reconciled against the working tree at 119944c + the kit-controls lane's uncommitted hunks on 2026-10-25 13:53 (`PLAY-i76.ps1`,
`setup-windows.ps1`, `tools/patch-kit/i76e-prepare.ps1`, `tools/package-patch-kit.ps1`, new `tools/patch-kit/i76e-controls.ps1` +
`i76e-update.ps1`; no `.ahk` file changed). Their record `docs/records/KIT-CONTROLS-UPDATER-2026-10-25.md` is cited by those
comments but does not exist yet. Line numbers below are the live tree's.

Lane: own-input-map (investigation / design, Fable). Trigger: an outside tester (expert, flight-stick player) installed the Patch Kit
over a fresh GOG install: *"Control set up was finicky ... it went to your defaults. Since I use a joystick, they didn't really apply.
I eventually ended up copying my input.map from another I'76 install and it seemed like some items of this patch still conflicted
with it, mostly related to yaw settings with my joystick's hat."* Read-only lane: no file but this record written, no game booted.
Paths: `<lab>` = the uncap lab, `<bench>` = the laptop bench, `<games>` = the owner's game folders.

## 0. Findings in five lines

1. **The clobber as shipped (v0.8.0) was unconditional**: the kit's first run called `setup-windows.ps1` without `-Controls`, default
   `i76e`, and step 5 wrote `controls\input.map` over any map not byte-equal to it, again on every kit update and `--resetup`.
   Measured today on the laptop (`<lab>\kit-controls\base-a080-gold-pre.log`): player map `dec488ab -> a66a37f7` at setup,
   the post-install edit `99c1379b -> a66a37f7` on `-Resetup`.
2. **Already fixed in the tree (uncommitted, kit-controls lane):** a map is replaced only when it is GOG's (md5 `74d2da37`), absent,
   or what the kit wrote last and nobody changed since (`i76e-installed.md5` manifest; `setup-windows.ps1:391-430`); anything else is
   kept with the kit's map beside it as `input.map.i76e-default` and, on a first install, mode `own` with the layers moved out of
   `_ahk\` (`:576-580`, `:780-793`). `CONTROLS.bat` (`i76e-controls.ps1`: keep / kit / mine / status) switches; the launcher's guard
   steps aside in `own` (`PLAY-i76.ps1:1260`); uninstall keeps an own map (`i76e-prepare.ps1:160-175`).
3. **The hat conflict is the wheel layer in `i76-remap.ahk`**, unchanged: `WheelPoll` reads the first winmm joystick unprefixed, treats
   any device with no U axis, an R axis and 11+ buttons as the T300 (`:322-344`) and taps `h` / `m` / `i` / `n` on every hat change
   (`:163-164`, `:384-392`). Three more layers act on a joystick regardless of the map (s.2). In the tree they are off only when the
   folder's mode is `own`; the tester's exact sequence (install, THEN copy a map in) leaves the mode `i76e` and the layers running
   (`setup-windows.ps1:577-580`) until he runs `CONTROLS.bat` -> keep.
4. **Nothing logs the controls verdict** in `play-i76.log`; the launcher still starts a layer whenever its script is in `_ahk\`
   (`PLAY-i76.ps1:997-998`, `:1017-1018`) and never classifies the map itself; `i76e-controls.txt` written by an earlier run rules.
5. **Fresh GOG folder:** the auto-detect counts GOG's md5 as kit-owned, so a kit install over an untouched GOG folder still installs
   our map and layers. That is a choice, not an accident (`:397`, `:411-414`); whether it is the one wanted is the owner's call (s.5 Q1).

## 1. The player-state files, as the tree stands now

The kit unzips into the game folder; `PLAY*.bat` run `_i76e\i76e-prepare.ps1` before every start; its first run (new `VERSION.txt`,
missing proxy / u32x / preset / launcher, or `--resetup`; `i76e-prepare.ps1:222-225`) first copies the player's files into
`_i76e\backup\pre-kit\` once (`Save-PreKit :86-103`, called `:233`), then runs `setup-windows.ps1 -GameDir .. -Preset tick19-42
-NoShortcut -Display WxH -AhkDir ..` (`:243-247`; Nitro: `-Controls stock`, or `own` when the mode file says so, `:245`).

| file | at install (live tree) | at launch (`PLAY-i76.ps1`) | backup / uninstall |
|---|---|---|---|
| `input.map` | `-Controls i76e` (still the Gold default, `setup-windows.ps1:99-100`): byte-equal to ours -> nothing (`:572-574`); **not kit-owned** (`Test-KitOwned :411-420`: not GOG's `74d2da37`, not the manifest's md5, not `as-installed` on a pre-manifest folder) -> KEPT, ours beside it as `input.map.i76e-default`, mode `own` unless the folder was already `i76e` (`Write-NoteOwn :423-430`, `:576-580`); absent -> ours (`:581-584`); GOG's or kit-owned -> replaced as before (`:585-620`). `-Controls own`: untouched, ours beside it (`:555-563`). `-Controls stock`: `Add-StockPatch :467-479` patches only a kit-owned map, else beside it. `-ReplaceControls` (`CONTROLS.bat` kit) overrides (`:104-107`). Mac `mac-install.command:104-107` and Deck `deck/i76-deck-launch.sh:240-247` still copy a map over it (the Deck on every launch) | guard runs only when the mode is not `own` (`:1260`) and, with no analog `steer` / `throttle`, only when a joystick is connected (`Test-JoystickConnected :1249-1259`, `:1265-1267`); side files `*.i76e-default`, `*.pre-update`, `*.i76e-last` are never restore candidates (`:1284`); `-DryRun` exits before it (`:964-976`) | `_i76e\backup\pre-kit\input.map` (`:86-103`); the old `.stock-<ts>` / `.before-i76e-<ts>` names remain for a replaced map (`:587-605`); uninstall: pre-kit copy back where the kit replaced it, a map changed since kept as `input.map.i76e-last`, an own map the kit never replaced left alone (`i76e-prepare.ps1:160-175`) |
| `i76e-controls.txt` | `i76e` / `stock` / `own` (`:645-648`); a run without `-Controls` keeps it (`:192-198`) | mouse-wheel-up default `Enter` for `stock` and `own` (`:981-982`); the guard's `own` test (`:1260`) | removed by uninstall (`i76e-prepare.ps1:186-188`) |
| `i76e-installed.md5` (new) | md5 of each control file the setup wrote (`Save-Manifest :404-408`, `:649-652`) | not read | removed by uninstall |
| `_ahk\i76-remap.ahk`, `_ahk\i76-ch-fighterstick.ahk` | mode `i76e`: `Install-Layer :807-822` replaces only a kit-owned copy (an edited one is kept, ours beside it as `.i76e-default`; a pre-manifest folder's copy becomes `.pre-update`); mode `stock` / `own`: moved to `_ahk\off-stock-controls\` (`:780-793`), brought back on a return to `i76e` (`:802-803`) | started whenever the script is in `_ahk\` (`:997-1000`, `:1017-1020`); no check of mode or map | uninstall copies an edited layer to `_i76e\backup\_ahk\` (`i76e-prepare.ps1:179-185`) |
| `I76PLYR.DEF` | the three detail bytes only when the file is GOG's byte for byte (`$gogPlyrMd5 :73`, `:259-266`; v0.8.0 tested the bytes alone) | not touched | uninstall restores the whole file only if unchanged since, else puts the three bytes back and keeps the rest (`:144-156`) |
| `savegame.dir`, `save*.cmp` | the repo's bookmarks only into a folder with no `save*.cmp` (`setup-windows.ps1` step 5a) | short-file guard pads only a file shorter than `4 + 60 x count` | never overwritten |
| `i76-settings.txt`, `presets\local.psd1` | not generated by the setup; written by the launcher on the first start | read (precedence SETTINGS-FILE-2026-10-25 s.2) | uninstall copies `local.psd1` to `_i76e\backup\` (`:177-178`); `i76-settings.txt` kept |
| `dgVoodoo.conf` (+ `.wide`, `.16x10`) | installed and rewritten for the display every run (`i76e-prepare.ps1:276-292`) | render keys rewrite it per launch | uninstall removes them; GOG ships none |
| `_ahk\i76-opentrack-headlook.ahk` | only by `INSTALL-EXTRAS.bat -OpenTrack` | started when opentrack is installed and running (`:1072-1121`) | - |
| `KEYBOARD.MAP`, `JOYSTICK.MAP` | not read by the engine (AGENTS.md:3-10); nothing in the kit writes them; the lint's tripwire 6 warns when they are newer than input.map | - | - |

**What the tester hit, in the live tree's terms.** v0.8.0: first run -> `i76e` -> wholesale replace; the first-run window said
only "this project's controls" (`i76e-prepare.ps1` v0.8.0:233). Tree: the same first run over a fresh GOG map still installs ours
(GOG's md5 is kit-owned); his later copy-in of his own map is then "edited after an earlier install (recorded i76e): stays i76e,
the AutoHotkey layers too" (`setup-windows.ps1:577-580`) - the map survives the next setup, but the layers keep typing over it
until `CONTROLS.bat` -> keep (`i76e-controls.ps1:91-101`, which runs `-Controls own` and moves them out). The window now says when a
map was kept (`i76e-prepare.ps1:334-337`) and which controls are in (`:317-321`).

## 2. What still fights a player's own map (unchanged by the lane; the layers are only moved aside in mode `own`)

Searched: the three AHK layers, `PLAY-i76.ps1`, the proxy (`music-fix\*.c`), `controls\*.map`, the Deck / Mac scripts, for
`POV | JoyPOV | hat | glance | yaw | look | I76_JOY_* | I76_HEADLOOK*`.

| layer | reads | acts on a joystick regardless of input.map | conflicts with a map that binds the hat / keys | where |
|---|---|---|---|---|
| **`i76-remap.ahk` wheel layer** (`WheelPoll`, 15 ms) | `JoyInfo`, `JoyButtons`, `Joy1..13`, `JoyPOV` of the FIRST winmm joystick, unprefixed | yes when the device has no U axis, has an R axis (twist on most sticks) and 11+ buttons (`:341`): the 13 buttons type the wheel keys (`gWheelBase :124-125`, `gWheelAlt :126-127`, button 6 = shift) and **the hat taps `h` `m` `i` `n` on each direction, `.` `,` shifted** (`:163-164`, `:384-392`) | **the hat conflict**: every hat move the map uses for glance / yaw also toggles headlights, opens the map, cranks the ignition or the notepad; every stick button types one of our keys | `i76-remap.ahk:320-393`; `:76-78` says native hat bindings beside it "would double-fire" - true of OUR map, the reverse of what a player's map wants |
| **`i76-remap.ahk` right-stick glance** (`RStickGlance`, 15 ms) | `JoyU`, `JoyR` unprefixed | yes on any first joystick with a U axis (`:288-298`): a throttle slider on U/R holds an arrow past 25 % deflection | arrows = whatever the map binds them to | `:276-318` |
| **`i76-remap.ahk` XInput poll** | XInput pads only (a DirectInput stick is invisible to it) | D-pad -> `h` `i` `n` `m`, triggers -> click / `2`, A -> click + Enter (`:427-605`) | a pad player's map with native `joystick1 Hat*` / `Button*` blocks gets both; not the tester's case | `:172-248`, `:425-605` |
| **`i76-ch-fighterstick.ahk`** | `joystick2` by fixed index (`DEV := 2`, `:82`); exits only when no joystick2 exists (`:608-617`); **never compares the device name** (printed only, `:618`) | ANY second joystick is driven as a Fighterstick: POV -> arrows held (`:708-727`), buttons 1-16 -> keys (`:676-690`), X / Y deflection -> `Space` / `X` / `,` / `.` (`:243-247`, `:729-735`) | a stick that enumerates second (a pad or wheel first, a vJoy / 3Dconnexion device) has its hat and grip taken over | `:82`, `:608-618`, `:674-735` |
| **`i76-opentrack-headlook.ahk`** (opentrack installed and running) | FreeTrack shared memory; `GetAsyncKeyState` | ANALOG NOPs the engine's seven input-poll stores: "keyboard / joystick glance is inert while analog is on" (`:190-203`); the override watches only the four arrow VKs and the middle mouse button (`EXT_VKS :240`, `:395-408`, `:636-647`) | a native `joystick1 HatUp` glance is silenced in ANALOG and cannot override (a hat is not a VK); the arrow keys themselves are read from the player's map (`:375-390`), so arrows are fine | `:186-203`, `:236-241`, `:632-657` |
| **`i76wheel.exe`** | the mouse wheel | types `Tab` / `5`; `Enter` up in `stock` and now `own` (`PLAY-i76.ps1:981-988`) | on a player's map, whatever he bound to `Enter` / `5`; settings lines `mouse wheel up` / `down` exist (`:330-333`) | `:100-114`, `:979-988` |
| **`PLAY-i76.ps1` guard** | the map text | in modes `i76e` / `stock` / none: a map without joystick lines in both `steer` and `throttle` (GOG's 2.1.0.17 map has neither block, `setup-windows.ps1:489-492`) is replaced by `input.map.as-installed` when a joystick is connected (`:1260-1296`), the old one kept as `.stripped-<ts>` | a keyboard-only or GOG-stock map copied in by hand while the mode file says `i76e` and a stick is plugged in: ours is back at the next boot | `:1245-1300` |
| proxy (`Strlkup.dll`) | IAT hook on `joyGetPosEx` for the sim-tick joystick watch (`simtick.c:105-154`); `I76_JOY_MAP` / `I76_JOY_SYNTH` off by default (`strlkproxy.c:10216-10338`) | observes only; the synth's POV is centred (`:10291`) | none | - |
| exit key-ups | - | key-ups for arrows, digits, our letters at game exit (`PLAY-i76.ps1:1551-1565`) | harmless | - |

Which of these the tester hit cannot be settled from the files: the wheel layer needs his stick to be winmm joystick1 with twist +
12 or more buttons (a Logitech Extreme 3D Pro / Thrustmaster T.16000M shape); the Fighterstick layer needs it to be joystick2; the
guard needs a map without analog `steer` / `throttle` and a stick plugged in. "Mostly related to yaw settings with my joystick's hat"
fits the wheel layer's hat taps best. One question to him settles it (s.5 Q2). No layer logs anything to `play-i76.log`
(`i76-remap.ahk` has `#NoTrayIcon` and no log; the stick prints to stdout, which the hidden launcher drops).

## 3. Design: what is done, what remains

Done in the tree by the kit-controls lane (verify, do not redo): the kit-owned rule + manifest, `-Controls own`, `-ReplaceControls`,
`input.map.i76e-default`, the layers moved out in `own`, the pre-kit backup, `CONTROLS.bat` keep / kit / mine / status with
`input.map.mine-<ts>` backups (`i76e-controls.ps1:69-77`, `:104-133`), the guard's `own` / no-joystick exits, the uninstall's
`i76e-last` and `I76PLYR.DEF` byte handling, the first-run window lines, `UPDATE.bat`. Remaining gaps, in order:

**(a) Classify at launch and log it.** `PLAY-i76.ps1` trusts `i76e-controls.txt`; it should also compare md5(input.map) with the
manifest / `input.map.as-installed` / the shipped md5s (a66a37f7, 12a6357e, 90122d37, 1c397955) and GOG's `74d2da37`, and write one
line through `Write-LaunchLog` (`:198`), the test's oracle: `controls: own map (md5 <8>, mode own) - pad / wheel / stick layers off,
hat untouched, mouse wheel Enter/5, head look digital` | `controls: this project's map (a66a37f7) - layers on` | `controls: 1997 keys
(stock)` | `controls: map edited since the kit wrote it (md5 <8>, mode i76e) - layers still ON; CONTROLS.bat -> keep turns them off`.
The last case is the tester's; the line is what makes it visible in the log he is asked to attach.

**(b) Layers that respect the map, not only the mode.** Mode `own` removes the scripts from `_ahk\`, so a HOWAS player who hand-edits
our map and chooses keep loses the whole wheel and stick. Pass `I76_MAP_KIND=own|i76e|stock` from the launcher (the `EnvGet`
precedent `i76-remap.ahk:240`), and in `own`: `WheelPoll` skips the `JoyPOV` block (`:384-392`) and `RStickGlance` returns at once;
the stick skips its POV block (`:708-727`); a settings line `button layers = auto | on | off` (schema `:317-333`, `param:` consumer
`:482-483`; `auto` = on for `i76e` only) lets that player force them back on with the hat still his. Both layers get a one-line
`_ahk\layers.log` (`I76_HEADLOOK_TRACE` is the pattern) so a test reads the layer's own decision.

**(c) The Fighterstick layer matches the device name** (`CH` / `Fighterstick`, `:608`) and exits otherwise: today any joystick2 is
hijacked, mode or no mode.

**(d) Head look on an own map** starts DIGITAL (no input-poll NOP) unless `head look mode` is set in the settings file, so a native
hat glance keeps working; or the ANALOG override polls the POV too (Q4).

**(e) README text** (kit README "Controls", docs/CONTROLS.md top, controls/README.md). Draft:

> **Your own input.map.** The engine reads one file, `input.map`, in the game folder; `KEYBOARD.MAP` and `JOYSTICK.MAP` are not
> read by this build, so editing them changes nothing. The kit keeps a map that is not GOG's untouched one; its own layout goes
> beside it as `input.map.i76e-default`, and `CONTROLS.bat` switches (keep mine / the kit's layout / restore mine). With your own
> map the kit's gamepad, wheel and flight-stick button layers are off, so nothing types keys behind your bindings and a hat you
> bind to glance or steering is yours alone; `play-i76.log` says which (`controls: ...`). If you copy a map in AFTER the setup,
> run `CONTROLS.bat` once and choose *keep*, or the button layers stay on. Never change bindings in the game's own Controls menu:
> it rewrites the file and drops the analog blocks.

## 4. The test (for the Opus lane; design only, not run here)

Copy: `<lab>\controls-twin-20261024` (purpose: controls; `_ahk\` carries all five layers; map `1c397955`; no `i76e-controls.txt`,
no manifest). `test-gold` only for the final confirmation. Rules (lab `README.md`, `CONSOLE-LOCK.md`): console lock (`.console-owner`,
no i76 process, no `.console-test.lock`), only your own files into the twin (never `install-rc.ps1`, CONTROLS-2026-10-24 "Incident"),
`I76_MUTE=1` + `tools\start-mute-watch.ps1 -Pid`, `tools\set-shm-suffix.ps1 -GameDir`, `I76_SKIP_CUTSCENES=1`, `I76_FFB_OFF=1`,
`tools\keep-display.ps1` if unattended. Laptop first for the headless part: `<lab>\kit-controls\ctl-test.ps1` already runs the kit's
phases from pristine zips and tabulates md5s (its tracked list has `input.map.i76e-default`); extend it with a `-DryRun` phase, the
`controls:` line and the tester's order (install first, copy the map in second), rather than writing a new harness.

The map under test, `<lab>\kit-controls\own.map`: GOG's 2.1.0.17 map (`74d2da37`) plus, appended, a marker line and native hat and
twist bindings - the tester's shape, not ours (`Rudder` and `Hat*` are engine tokens: the lint's ANALOG set, the stock-patch blocks
`setup-windows.ps1:533-536`; the lint must pass on it before the test starts):

```
# OWN-MAP-TEST 2026-10-25: a player's map, hat = look, twist = steer
steer { - joystick1  Rudder }
pilot_glance_left  { + joystick1  HatLeft }
pilot_glance_right { + joystick1  HatRight }
track_yaw_left     { + joystick1  HatLeft }
track_yaw_right    { + joystick1  HatRight }
```

Steps (PowerShell from `<lab>`; `$g = "<lab>\controls-twin-20261024\Interstate 76"`):

1. Stage: `Copy-Item "$g\input.map" "$g\input.map.pre-ownmap-$(Get-Date -f yyyyMMdd-HHmmss)"`; write `own.map` to `$g\input.map`;
   `python ..\i76-everywhere\tools\lint-input-map.py "$g\input.map" "$g\i76.exe"` -> exit 0; `$m0 = (Get-FileHash "$g\input.map" -Algorithm MD5).Hash`.
2. Setup, two orders. **Before-install** (the auto-detect): `powershell -File <repo>\setup-windows.ps1 -GameDir "$g" -ControlsOnly
   -AhkDir "$g\_ahk"` -> md5 == `$m0`; `i76e-controls.txt` = `own`; `input.map.i76e-default` = a66a37f7; `_ahk\i76-remap.ahk` and
   `i76-ch-fighterstick.ahk` in `_ahk\off-stock-controls\`. **After-install** (the tester's order): on a second copy run the setup on
   GOG's map first (ours goes in, mode `i76e`), then write `own.map` over it, run the setup again -> md5 == `$m0`, map kept, but mode
   `i76e` and the layers in `_ahk\` (the s.3(a) line must say so); then `_i76e\i76e-controls.ps1 -Choice keep -NoPause` (kit layout)
   or `setup-windows.ps1 -Controls own -ControlsOnly` -> mode `own`, layers out. Negative control: `-Controls i76e -ControlsOnly
   -ReplaceControls` must change the md5 (the old behaviour reachable only by choice).
3. Dry run: `powershell -File "$g\PLAY-i76.ps1" -GameDir "$g" -Preset tick19-42 -DryRun` -> md5 == `$m0`; stdout has
   `controls: own map (md5 <m0:8>, mode own) - ... hat untouched`; "helpers that a real run would also start" lists no AHK layers.
4. Real boot (console lock held): `..\controls-twin-20261024\PLAY-T05.bat` with the lab environment; after the player entity exists
   (`autotest\lib\memlib.ps1`): `Get-CimInstance Win32_Process -Filter "Name='AutoHotkeyU32.exe'" | % CommandLine` names neither
   `i76-remap.ahk` nor `i76-ch-fighterstick.ahk` (the cursor overlay may run); `$g\play-i76.log` has the `controls: own map` line;
   with `button layers = on` (second row) `_ahk\layers.log` has `remap: map kind own - wheel hat and right-stick glance off`. Exit
   through the launcher; md5 == `$m0` after exit, no `input.map.stripped-*`, the `.pre-ownmap-*` backup untouched. n 3 boots.
5. Hat row, hands on the device (the desktop's T300 is winmm joystick1 and its D-pad is a POV; the Fighterstick is joystick2): in the
   T05 cockpit press the D-pad left and right three times each - the view glances (the camera yaw `0x4c2970` moves, read by memlib,
   or the F6 capture) and the headlights, map and ignition do not react (`h` / `m` / `i` are the wheel layer's taps). n 3 per
   direction; again with `button layers = on` (the `I76_MAP_KIND` hat skip). Control: ours restored (`CONTROLS.bat kit`), D-pad left
   -> headlights toggle, n 2. No software stand-in exists for this row: AHK reads the hat through its own `joyGetPosEx`, outside the
   proxy's hook, so `I76_JOY_SYNTH` cannot feed it.
6. Head look row (opentrack on the desktop): with `own.map` and head look ON, the D-pad glance must still glance in the start mode;
   if ANALOG silences it, DIGITAL stays the `own` default and the record says so.
7. Restore the twin: `Copy-Item "$g\input.map.pre-ownmap-*" "$g\input.map"`; remove `i76e-controls.txt`, `i76e-installed.md5`,
   `input.map.as-installed`, `input.map.i76e-default`, `_ahk\off-stock-controls\` if the twin had none; md5 read back `1c397955`;
   release the lock.

Acceptance line: *own map `<m0:8>` byte-identical after setup (both orders), DryRun and 3 real boots (md5 before = after, no
`.stripped-*`), `play-i76.log` `controls: own map ... hat untouched` on every boot, no remap / stick AHK process during the game, hat
glances n 3+3 with no lights / map / ignition side effect (also with the layers forced on); with our map the same hat toggles the
lights (n 2); the after-install order logs `layers still ON` until CONTROLS.bat -> keep.*

## 5. Plan for Opus (ranked, on top of the kit-controls hunks) and open questions

| # | step | files | test | done when |
|---|---|---|---|---|
| 1 | the launch-time classification + `controls:` log line (s.3a), incl. the "edited since, layers still ON" case | `PLAY-i76.ps1:979-1020`, `:198` | `tests/test_settings_file.py` +1 (DryRun on an `own` folder shows the line); s.4 steps 3-4 | the line on every boot, all four cases |
| 2 | `I76_MAP_KIND` in both layers, hat / right-stick skips, `_ahk\layers.log`, `button layers` settings line (s.3b) | `i76-remap.ahk:276-318, 320-393`; `i76-ch-fighterstick.ahk:708-727`; `PLAY-i76.ps1:317-333, 482-483` | `i76-ch-fighterstick.ahk -selftest`; `tools\controls-sheet\build.ps1` (AGENTS.md rule 6) "sources agree"; s.4 step 5 | hat row passes with the layers forced on |
| 3 | Fighterstick device-name match (s.3c) | `i76-ch-fighterstick.ahk:608-618` | `-selftest`; a non-CH joystick2 on the bench -> exit 1 with the device list | no hijack of a foreign joystick2 |
| 4 | head look DIGITAL on `own` (s.3d) | `PLAY-i76.ps1:1072-1121` | s.4 step 6 | hat glance works with head look ON |
| 5 | docs: kit README "Controls" (`tools/patch-kit/README.md:21, 255-257, 310`), docs/CONTROLS.md:1-19 / 129-148 / 337-344, controls/README.md; the s.3(e) text; `tools\controls-sheet\build.ps1` | - | `tests/test_controls.py` | docs name CONTROLS.bat, the log line and the after-install rule |
| 6 | `KIT-CONTROLS-UPDATER-2026-10-25.md` is cited by five files and absent: the kit-controls lane writes it (its laptop log is the evidence) or the citations change | `setup-windows.ps1:391`, `PLAY-i76.ps1:1245`, `i76e-prepare.ps1:34`, `i76e-controls.ps1:2`, `i76e-update.ps1:2`, `package-patch-kit.ps1:17` (typo `docsecords`) | - | the file exists |
| 7 | GitHub: no issue mentions `input.map` (`gh issue list --search "input.map"`: none; #32 "Patch Kit and Windows polish" is nearest); file one (`area/installer-kit`, `area/controls`, `kind/bug`, `evidence/measured`, the tester's words, no name), `Fixes #<n>` on the commits | - | - | issue linked to both records |

Open questions:

1. **Owner: the fresh-GOG default.** The auto-detect treats GOG's `74d2da37` as kit-owned (`setup-windows.ps1:397`, `:411-414`), so a
   kit installed over an untouched GOG folder still gets our map + layers - a first-time user keeps a working pad, and a player who
   installs the kit BEFORE configuring (the tester) gets ours and must run `CONTROLS.bat`. Is that the intent, or should a stock map
   get the one interactive question at the first-run pause (`i76e-prepare.ps1:339-344`)? Not redesigned here.
2. **Which layer bit the tester**: his stick's winmm index and shape (twist? 12+ buttons? a device before it?), whether his map has
   `steer` / `throttle` joystick lines, whether opentrack was installed. Ask for `play-i76.log`, `_i76e\setup.log` and the `input.map*`
   listing (the issue form already asks for the logs).
3. **The AiO / 2019 build's stock map md5**: only 2.1.0.17's is in `$gogMapMd5`; an AiO player's untouched map classifies as own
   (safe: kept, no layers, the window says so).
4. **Head look on a hat-glance map**: extend the ANALOG override to a native POV, or keep DIGITAL as the `own` default?
5. **The after-install order** (`setup-windows.ps1:577-580`): keeping mode `i76e` with the layers on when the map was edited after an
   install is a deliberate rule ("stays i76e, the AutoHotkey layers too"); it is also the tester's path. Owner / lane call whether an
   edited map should switch to `own` by itself (s.3a makes it visible either way).

Evidence, all read 2026-10-25: the files cited by line (live tree 13:53); `<lab>\kit-controls\base-a080-gold-pre.log` (laptop, v0.8.0
kit, pristine GOG 2.1.0.17, 13:39); CONTROLS.md:104 (stock md5 74d2da37); controls/README.md:11-14 (shipped md5s);
`<lab>\controls-twin-20261024\Interstate 76\input.map` = 1c397955 with all five layers in `_ahk\`.
