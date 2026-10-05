# Nucleus Co-op handler for Interstate '76 (SEPARATE EFFORT)

Started 2026-10-03. Kept apart on purpose: nothing here touches the i76-everywhere repo, the patch set, or the
daily driver. **Status (2026-10-05): first run done (section Runs).** Two instances started from Nucleus side by side, shared one
IPX session and each held both cars. Per-player input with real devices is not verified yet. Nucleus v2.4.2 runs from
`..\refs\nucleus\run` (a copy of `app`, with `DebugLog=True` and `DisablePathCheck=True` in its Settings.ini).

## Status
| item | state | where |
|---|---|---|
| Nucleus Co-op release | v2.4.2 (2026-08-23), `NucleusApp.zip` md5 36d472cd, unpacked (zip password `nucleus`, from the release notes). Not run | `..\refs\nucleus\app` |
| Nucleus licence | **GPL-3.0** (repo `LICENSE`; GitHub API spdx `GPL-3.0`). The zip itself ships no LICENSE file | `..\refs\nucleus\LICENSE-splitscreenme-nucleus.txt` |
| Nucleus source (launch + Context code) | `GenericGameHandler.cs`, `GenericContext.cs`, `StartGame\Program.cs` at repo HEAD | `..\refs\nucleus\src` |
| published handlers | all 600 hub handlers (`hub.splitscreen.me/api/v1/allhandlers` + cdn `.nc`) downloaded and scanned. **None uses IPX, IPXWrapper or CMDBatchBefore**; one uses dgVoodoo (Super Mario 64). No Interstate '76 handler | `..\refs\nucleus\hub` |
| handler | `Interstate76.js`, every option cited | here |
| handler folder | `Interstate76\dgVoodoo.conf` (windowed template), IPXWrapper 0.7.2 DLLs (git-ignored; from `..\refs\ipxwrapper\bin\ipxwrapper-0.7.2`), `IPXWRAPPER-LICENSE.txt` | `Interstate76\` |
| IPX between two lab copies | transport works (lab doc 8.6); session not opened yet (host car failed ValidateVcf; cause now known) | `..\docs\MULTIPLAYER-LOCAL-TEST.md` 8.6-8.7, `..\docs\MULTIPLAYER-CAR-CHECK.md` |
| INTERNET (WINET) route | not viable without an anet game server (lab doc 8.3) | same |
| gate 0 (IPX between two lab copies, no Nucleus) | **PASS** 2026-10-05 (`game-nucleus` + a temporary copy) | `..\docs\MULTIPLAYER-LOCAL-TEST.md` 9.1 |
| first Nucleus run | 2026-10-05: steps 1-6 pass, 7 partial (no real devices), 8 done | section Runs |
| follow-up | 2026-10-05: `I76_NO_MINIMIZE` + `I76_TRAINER=0` in the handler, clean stop, owner checklist; no-minimize A/B without Nucleus (n = 1 each) | section Runs, follow-up; `..\docs\MULTIPLAYER-LOCAL-TEST.md` 9.4 |
| real pads, two players | **owner** | section Owner checklist |

Licences: Nucleus Co-op is GPL-3.0. IPXWrapper 0.7.2 is GPL-2.0 (`Interstate76\IPXWRAPPER-LICENSE.txt`, copied from
its `license.txt`). We redistribute neither from here: the DLLs stay git-ignored, and the handler copies the user's
own IPXWrapper files into each instance. Nucleus also bundles third-party tools (Goldberg, x360ce, XInputPlus,
devreorder, ForceBindIP, ...) under their own terms; this handler uses none of them.

## Three findings that change the plan
1. **The game has no DirectInput or XInput joystick path.** `i76.exe` and `i76shell.dll` import only WinMM
   `joyGetNumDevs / joyGetDevCapsA / joyGetPosEx` (DINPUT appears only in `i7_sfrce.dll`, force feedback). This
   agrees with i76-everywhere `docs/GAMEPAD-PC-MAC.md`. Nucleus's controller routing (x360ce, XInputPlus, devreorder,
   Proto Input Xinput/Dinput hooks) works on XInput/DirectInput only, so **Nucleus cannot give each instance its own
   pad**. The handler instead writes a per-instance `input.map` with a different `joystickN` (joystickN = winmm id
   N-1, inferred from `docs/HEAD-TRACKING.md`). Whether the engine reads a slot other than the first present one is
   **unmeasured** (`docs/FIGHTERSTICK.md` leaves it open): test plan step 2.
2. **Nucleus has no per-instance environment option.** Plain launches inherit Nucleus's own environment
   (`CreateProcess(..., envPtr = 0)`, `GenericGameHandler.cs:2117-2127`). With `Game.CMDLaunch = true` it writes a
   `.cmd` per instance (`set` lines, `CMDBatchBefore` lines, then the game line) and runs it with `cmd /c`
   (`GenericGameHandler.cs:1849-2106`), so `set` lines reach the game. Per-instance values (I76_ASPECT) come from a
   file `Game.Play` writes (`i76-nucleus.env`), read by a `for /f` line. Cost: with CMDLaunch, startup hooks are
   skipped (`:1669`): no `HookInit`, no Proto Input `FindWindowHook` (needs startup injection, PI 138). The proxy
   switch `I76_MULTI_INSTANCE=1` covers the single-instance check, so nothing is lost.
3. **NucleusCoop.exe and StartGame.exe require administrator** (embedded manifests: `requireAdministrator`). Running
   it needs the owner's UAC approval, and the games it starts run elevated. Consequence: non-elevated AutoHotkey
   layers cannot send keys into them (UIPI). Symlinking files needs admin or Developer Mode; elevation covers it.

## Verified option list (what the handler uses, and where each name was checked)
MH = `app\handlers\MasterHandler.js`, RM = `app\readme.txt`, PI = `app\readme Proto Input.txt`, SRC = `src\*.cs`,
HUB = a published handler (SM64 = Super Mario 64 `rbTfwX2jB3G9MbMtW`, Glide + dgVoodoo; RV = Re-Volt `Z6mco7mynDaqp8xrm`).

| area | options | source |
|---|---|---|
| identity | `ExecutableName`, `ExecutableContext`, `GUID`, `GameName`, `MaxPlayers`, `MaxPlayersOneMonitor`, `HandlerInterval`, `PauseBetweenStarts`, `Description` | MH 1, 24, 28-33, 54; RM 305 |
| files | `SymlinkGame`, `SymlinkExe`, `SymlinkFolders`, `KeepSymLinkOnExit`, `FileSymlinkCopyInstead` (real copy), `FileSymlinkExclusions` (neither link nor copy) | MH 13, 18, 25, 26; RM 45-56, 1109; HUB SM64 |
| per-instance edits | `Context.GetFolder(Nucleus.Folder.InstancedGameFolder)`, `Game.Folder`, `System.IO.File.Copy/ReadAllBytes/ReadAllText/WriteAllText`, `Context.EditTextFile(path, refs, news, enc)`, `Context.WriteTextFile`, `Context.HexEdit(file, hexAddr, bytes)`, `Context.PlayerID`, `Context.Width/Height`, `Context.Log` | MH 65, 81, 91-93; RM 241, 249, 400-401, 456, 471, 475; SRC GenericContext.cs 59, 141, 1082, 1441, 1621 |
| launch + env | `CMDLaunch`, `CMDOptions` (per-instance prefix), `CMDStartArgsInside`, `CMDBatchBefore` (`i|line` = instance i), `StartArguments`, `ForceProcessSearch`, `%NUCLEUS_INST_EXE_FOLDER%` | MH 37; RM 295, 309-316, 515-521; SRC GenericGameHandler.cs 1849-1951 |
| windows | `SupportsPositioning`, `Hook.ForceFocus`, `Hook.ForceFocusWindowName`, `HasDynamicWindowTitle`, `SetWindowHook`, `ResetWindows`, `KeepAspectRatio`, `ProtoInput.SetWindowPosHook` | MH 41-43; RM 110, 129, 137, 138, 384; HUB SM64 |
| pads (device screen only) | `Hook.DInputEnabled`, `Hook.DInputForceDisable`, `Hook.XInputEnabled`, `Hook.XInputReroute`, `Hook.CustomDllEnabled`, `UseDevReorder = false` | MH 44-47, 53; RM 167; HUB RV, SM64 |
| keyboard | `SupportsKeyboard`, `KeyboardPlayerFirst`, `SupportsMultipleKeyboardsAndMice`, `LockInputAtStart`, `LockInputToggleKey`, the deprecated `Hook*`/`Send*`/`Forward*` set to false | MH 27; RM 161, 163, 376; PI 59, 254-256 |
| Proto Input | `InjectStartup`, `InjectRuntime_EasyHookMethod` (+ the other two), `RegisterRawInputHook`, `GetRawInputDataHook`, `MessageFilterHook`, `ClipCursorHook`, `ClipCursorHookCreatesFakeClip`, `FocusHooks`, `SendKeyboardButtonMessages`, `DrawFakeCursor`, `BlockedMessages`, `XinputHook`, `FreezeExternalInputWhenInputNotLocked`, `OnInputLocked/OnInputUnlocked` with `ProtoInput.InstallHook/UninstallHook/EnableMessageFilter/DisableMessageFilter/StartFocusMessageLoop/StopFocusMessageLoop/SetRawInputBypass` | PI 64, 71-110, 254-281; SRC GenericGameHandler.cs 2621-2630 |
| prompts | `PromptBetweenInstances` | RM 288; HUB SM64 |

Not used, and why: `KillMutex`/`RenameNotKillMutex` (the check is FindWindowA on a class, not a mutex);
`HookInit` and `ProtoInput.FindWindowHook` (startup hooks, skipped under CMDLaunch); `UseNucleusEnvironment` (the
game keeps its state in its folder, not the profile); `UseForceBindIP`/`ChangeIPPerInstance` (IPX, not IP);
`ChangeExe` (renames i76.exe per instance; possible later for per-window AHK scoping, untested with the proxies).

## What the handler does per instance (`Game.Play`)
1. Copies `Interstate76\dgVoodoo.conf` (the lab's accepted `game\dgVoodoo.conf` md5 6be07be8, comments stripped,
   `FullScreenMode = false`, `CaptureMouse = false`, `CenterAppWindow = false`; borderless windowed) and sets
   `[Glide] Resolution` = the instance's window size; `ScalingMode` = `stretched` when the window is wider than 4:3,
   else `stretched_ar`. Written us-ascii (EditTextFile with "utf-8" would add a BOM).
2. Writes `i76-nucleus.env` with `I76_ASPECT=<W>x<H>` when the window is wider than 4:3 (the proxy accepts 1.34..3.6).
   The `.cmd` sets `I76_MULTI_INSTANCE=1`, `I76_NO_MINIMIZE=1`, `I76_TRAINER=0` (since 2026-10-05) and the best-120 switch set (i76-everywhere `presets\best-120.psd1`),
   then reads this file.
3. Leaves `input.map` (a real copy) on `joystick1` and writes `I76_JOY_MAP=0=<JOY_WINMM[id]>` into `i76-nucleus.env` (2026-10-05; was a per-instance `joystickN`, which breaks for slot 3+, see Runs).
4. Copies IPXWrapper 0.7.2 (`ipxwrapper.dll`, `wsock32.dll`, `mswsock.dll`) from the handler folder. **The patch is
   parameterised:** instance id > 0 gets the letter `'A'+id` at file 0x1BEAC (`ipxwrapper_socket_%hu` ->
   `ipxwrapperBsocket_%hu`, `...Csocket...`) and at 0x1CB7C (`Software\IPXWrapper` -> `Software\IPXWrappeB`, `...C`).
   Instance 0 keeps the stock file; id 1 equals `autotest\ipx-setup.ps1`'s patch. Each instance then has its own
   mutex namespace and its own HKCU node key. Bytes are checked before and read back after; a mismatch aborts.
   `ipxwrapper.ini` gets `logging = debug`.
5. Puts the stock `ADDON\valepre4.orig` in place of the modded `valepre4.vcf` (delete the link, then copy, so the
   source install is never written through a symlink).
6. Launch line: `start "" /D "<instance>" "<instance>\i76.exe" -glide` from the per-instance `.cmd`.

## AutoHotkey layers
`i76-remap.ahk`, the fighterstick layer and `i76wheel` send keys globally (to the foreground window), and the game
reads key state globally. Under Nucleus: **do not run them** for the first runs. They would reach whichever instance
has focus, and a non-elevated AHK cannot send into the elevated instances anyway. Per-window scoping later needs
(a) AHK run elevated, (b) `#If WinActive("ahk_pid " pid)` per instance (both processes are `i76.exe`; `ChangeExe`
would make `ahk_exe` usable, untested), and (c) each layer reading only its own player's joystick.

## Open unknowns (each one is a step in the test plan)
1. Does the engine read `joystick2` (or any slot other than the first present one)? Unmeasured.
2. Does Proto Input's key-state hook take effect through `u32x.dll` -> USER32 `GetAsyncKeyState` (EasyHook patches
   the USER32 function itself, so it should), and does the pad instance then see no keyboard while input is locked?
3. Is the window title "Interstate '76 Gold Edition" under dgVoodoo (positioning depends on it)?
4. Does dgVoodoo windowed mode accept Nucleus's resize or snap back (SetWindowHook is set)? Is the per-instance conf
   actually loaded (flip a visible key first: memory "probe that the config loads")?
5. Where does Nucleus put `Game.Folder` for a locally added `.js` (hub packages unzip to `handlers\<name>\`)? The
   first line of `Game.Play` logs it.
6. Does the `.cmd` read exactly `start "" /D "<dir>" "<exe>" -glide` (`GenericGameHandler.cs:1936-1941`)? Nucleus
   logs the line ("Launching game via command prompt with the following line").
7. Does Jint convert a JS number array to `byte[]` for `Context.HexEdit`? MasterHandler passes JS arrays to
   `PatchFile(byte[])` (MH 97-100), so it should; the read-back catches a failure.
8. ClipCursor fight: does `ClipCursorHookCreatesFakeClip` stop the alternation seen in lab doc section 5?

## First live run: test plan (lab copies only; owner present for UAC)
**Gate 0 (no Nucleus):** an IPX session between `..\game` and `..\game-alt` per `..\docs\MULTIPLAYER-LOCAL-TEST.md`
8.7, with `ADDON\valepre4.orig` copied over `valepre4.vcf` in both for the run (and put back after); both copies
need byte-identical `.vdf/.wdf/.gdf/compnent.cdf` (stock ZFS, no ADDON overrides of those). Pass = B lists A's
game, JOIN GAME, both reach the same mission. Do not start Nucleus until this passes.

1. **Source folder.** Make a third lab copy, `..\game-nucleus`, from `..\game-alt` (robocopy, without the
   save-backup-* folders). In it: `ADDON\valepre4.vcf` = `valepre4.orig` (md5 de680a86 per the car-check doc); no
   ADDON `.vdf/.wdf/.gdf/.cdf` overrides; no `ipxwrapper*.dll/wsock32.dll/mswsock.dll`; STRLKUP.DLL = a build that
   has I76_MULTI_INSTANCE and I76_ASPECT (`findstr I76_MULTI_INSTANCE STRLKUP.DLL`). Record md5s of `i76.exe`,
   `STRLKUP.DLL`, `u32x.dll`, `input.map`, `dgVoodoo.conf`, `ADDON\valepre4.vcf`. Never point Nucleus at `game`,
   `game-alt` (other agents' tests) or the daily driver.
2. **Joystick slots (no Nucleus).** Plug in both pads. Run i76-everywhere `deck\probe` (`i76-input-probe`) to list
   the winmm ids present; set `JOY_SLOT` to those ids + 1. Then, in `game-nucleus` alone, point `input.map` steer at
   the second pad's `joystickN` and check in a mission that it steers. If it does not, the engine reads one slot
   only: stop and record that. The fallback is a proxy switch that remaps `joyGetPosEx` ids per instance (new work
   in STRLKUP, outside this handler).
3. **Install Nucleus** by copying `..\refs\nucleus\app` to `..\refs\nucleus\run` (keep the unpacked copy pristine).
   Copy `Interstate76.js` to `run\handlers\` and the `Interstate76\` folder (with the 3 IPXWrapper DLLs) to
   `run\handlers\Interstate76\`. Start `NucleusCoop.exe` (UAC: the owner). Add game -> `game-nucleus\i76.exe`. If
   Nucleus offers to download or install drivers or tools (ViGEm, HidHide, ...), decline.
4. **Layout:** 2 players side by side on one monitor; keyboard on screen 1, a pad on screen 2. Play.
5. **Check at each instance start** (PromptBetweenInstances holds the next one):
   - `run\debug-log.txt` (enable debug logging in Nucleus settings): the `I76:` line (instance, dir, size,
     Game.Folder); "Launching game via command prompt with the following line: start "" /D ..."; no throw from the
     IPX byte check.
   - Instance folders (`run\content\Interstate76\Instance0`, `Instance1`): `dgVoodoo.conf` has
     `FullScreenMode = false` and `Resolution = <W>x<H>` under [Glide]; `i76-nucleus.env`; the `input.map` joystick
     lines; Instance1 `ipxwrapper.dll` reads `ipxwrapperBsocket_%hu` / `Software\IPXWrappeB`;
     `ADDON\valepre4.vcf` md5 = `.orig`.
   - `game-nucleus`: md5s unchanged from step 1, and `save*.cmp` unchanged (nothing written through a link).
   - Each game window borderless in its half. With `I76MUSIC_LOG=1` added to CMDBatchBefore for this run, the proxy
     log shows "multi-instance: single-instance check skipped" and, for a wide window, "aspect: D ...".
6. **Network:** with input unlocked, walk instance 0: MELEE > MULTI MELEE > HOST > IPX > BROADCAST GAME (the lab
   doc's coordinates are for a 640x480 full screen; read the buttons). Then instance 1: MELEE > MULTI MELEE > JOIN >
   IPX; its list should show the host's game; JOIN GAME. Both `ipxwrapper.log`: distinct nodes, socket 21155 bound twice.
7. **Input:** press End (lock). Keyboard drives only instance 0, the pad only instance 1, and keyboard keys do not
   move instance 1's car. Pass = both cars driven independently in one mission for 2 minutes.
8. **Close and restore:** close Nucleus (it ends the games). `Remove-Item HKCU:\Software\IPXWrappeC` if it appeared
   (3+ players). Keep `run\content` for the record; md5-check `game-nucleus` against step 1.

Record n, the debug log and two screenshots in `..\docs\MULTIPLAYER-LOCAL-TEST.md` (a new section 9).

## Runs

### 2026-10-05 (console 09:04-09:27, one UAC approval via `autotest\nucleus-bridge.ps1`) [measured]
Elevation: one `Start-Process -Verb RunAs` started `nucleus-bridge.ps1` (60 min queue runner). Nucleus, and every click
into it and into the elevated games, went through it (`autotest\nucleus-q.ps1`; helpers in `autotest\runs\nucleus`).
No driver or tool install was offered or accepted. Evidence: `..\refs\nucleus\run\debug-log.txt`, captures
`autotest\runs\nucleus\n*.png`. n = 1.

| step | result |
|---|---|
| 1 source folder | `game-nucleus` from `game-alt`: valepre4.vcf de680a86, I76.ZFS 6dd57b16, no ADDON vdf/wdf/gdf/cdf, no IPX dlls, STRLKUP c8b15a62 (I76_MULTI_INSTANCE, I76_ASPECT, I76_JOY_MAP). md5 i76.exe 85de44a7, u32x 05c9a7be, input.map a937f36d, dgVoodoo.conf 6be07be8. All unchanged after the run; save/def/spc files equal game-alt's |
| 2 joystick slots | no pad plugged in; settled with the proxy's synthetic pad instead (lab doc 9.2): joystick1/2 open, joystick3+ need winmm id 1. Handler now uses `I76_JOY_MAP` per instance. Real pads: owner |
| 3 install | Nucleus refused to start under C:\Users ("should not be installed here") until `[Dev] DisablePathCheck=True`. Add game: file dialog -> `game-nucleus\i76.exe`; handler picked up ("Interstate '76 Gold Edition 2 - 4") |
| first PLAY | **NullReferenceException** before launch: with CMDBatchBefore set, Nucleus computes `exeFolder.Substring(0, len - Game.BinariesFolder.Length)` and BinariesFolder was unset. Fixed: `Game.BinariesFolder = ""` |
| 4 layout | 2 players side by side (1720x1440 each, aspect 1.19 -> stretched_ar, no I76_ASPECT); keyboard+mouse = P1, Nucleus's "virtual" mouse = P2 (no pad present) |
| 5 checks | log line `start "" /D "%NUCLEUS_INST_EXE_FOLDER%" "...\Instance0\i76.exe" -glide` (unknown 6: yes). Instance files: dgVoodoo.conf FullScreenMode = false, [Glide] Resolution = 1720x1440; i76-nucleus.env `I76_JOY_MAP=0=15` / `=0=0`; Instance1 ipxwrapper.dll fad787e8 = the B patch, so `Context.HexEdit` with a JS array works (unknown 7: yes); valepre4.vcf de680a86 in both. Proxy log: `joy-map: engine id 0 (joystick1) -> winmm id 15`. Window title "Interstate '76 Gold Edition" (unknown 3: yes). Both processes ran at once. The `I76:` Context.Log line did not appear in debug-log.txt (unknown 5 open) |
| 6 network | instance 0 HOST > IPX > BROADCAST GAME -> arena; instance 1 JOIN > IPX listed "THE CRATER (1/4)" once instance 0 was un-minimised; JOIN GAME -> arena. Position tables mirrored: I0 slot 0/1 (2272.5, 1.83, 49022.52) / (2003.54, 14.73, 49155.65), I1 the same pair swapped. IPX nodes 92:DA:A4:AC:05:7A and 2F:E4:D6:9F:90:93. **PASS** |
| 7 input | unlocked: injected W (keybd_event) moved only the focused instance (I1 0 -> 18.7 m/s, I0 stayed 0). After End (lock): injected W moved neither (Proto Input's key-state hook serves raw input from the assigned device; injected keys carry none). Real keyboard + pad and the 2-minute two-car drive: **not done** (owner) |
| 8 close | Nucleus did not close on CloseMainWindow or an injected Ctrl+Q; the games and Nucleus were ended with Stop-Process. User Shell Folders unchanged; no HKCU\Software\IPXWrappeC. `run\content` kept |

Problems found, for the next run:
- **Windows are placed late, and an unfocused instance minimises.** Instance 0 started at 0,0 (left half) and
  minimised when instance 1 took focus; instance 1 also opened at 0,0. A minimised host does not answer the joiner's
  search ("No games found" until it was restored with ShowWindow(SW_SHOWNOACTIVATE) and moved to 1720,0). Proto
  Input's focus hooks are installed only on lock (OnInputLocked), so before the lock nothing stops the minimise. Next:
  install FocusHooks and the WM_ACTIVATE/WM_ACTIVATEAPP filters at start, and see whether Nucleus repositions after
  the last instance (ResetWindows, Ctrl+R).
- Clicks in a windowed instance: screen = window origin + (2.6875 x UI x, 75 + 2.6875 x UI y) for 1720x1440
  stretched_ar (the 640x480 image is letterboxed by 75 px top and bottom).
- Four Windows Firewall prompts are open (game-nucleus, game-mpb, Instance0, Instance1 `i76.exe`); not clicked. One
  covered Nucleus's "launch instance 2" OK button; the bridge moved Nucleus's prompt instead. One stray click landed on
  a firewall prompt's Name text field (selects text only; no button was pressed).
- `mciproxy.log` is written through a link into `game-nucleus` (not in the copy list): harmless, add it to
  FileSymlinkCopyInstead for per-instance logs.
- Both instances open the trainer's shared block `Local\I76Trainer` (same name): add `set I76_TRAINER=0` for Nucleus.

### 2026-10-05 follow-up (handler changes; live A/B without Nucleus, console 09:42-09:51)
| problem | cause | change |
|---|---|---|
| unfocused instance minimises | **the game itself**: WndProc `WM_ACTIVATEAPP` with wParam 0 (0x404aba) calls `ShowWindow(hwnd, SW_MINIMIZE)` (0x404acc), then clears the active flag 0x504c1c. Not dgVoodoo, not u32x (i76.exe imports ShowWindow through u32x, which forwards it unchanged). In a net game the main loop keeps running frames while inactive (0x4039e4 tests 0x452d20), so only the minimise is in the way. Same bytes in the AiO, pristine_fix and sandbox exes | proxy switch `I76_NO_MINIMIZE=1` (i76-everywhere `ef8564c`, STRLKUP md5 3df367d9): `push 6` -> `push 8` (SW_SHOWNA). The handler sets it. Proto Input focus hooks at start were not needed for this |
| does a minimised host really hide its game? | **No, in the A/B (lab doc 9.4, n = 1 each, two copies without Nucleus, full-screen conf):** switch off, A went iconic when B took focus and B still listed "THE CRATER (1/4)" after 12 s; switch on, A stayed un-minimised, B listed it and joined (cars mirrored). So the first run's "No games found" was more likely timing (5 s broadcast, list read once) or the unfinished setup (the post-hooks prompt was still open; Clean stop). The windowed Nucleus case was not repeated (needs the owner's UAC) | the switch stays: side-by-side windows should not vanish when the other player clicks. `game-nucleus\STRLKUP.DLL` is now 3df367d9 (previous kept as `.c8b15a62`) |
| trainer block shared | both instances opened `Local\I76Trainer` | `set I76_TRAINER=0` |
| `mciproxy.log` written through a link into `game-nucleus` | the file existed in the source folder, so Nucleus linked it | `mciproxy.log` added to `FileSymlinkExclusions`; each instance writes its own |
| Nucleus did not close (CloseMainWindow, Ctrl+Q) | see Clean stop | `autotest\nucleus-stop.ps1` |

## Clean stop
Why the first run's two attempts did nothing (Nucleus v2.4.2 source, `HotkeyListener.cs`, `MainWindowFunc.cs`,
`GenericGameHandler.End`; and the run's bridge log `autotest\runs\nucleus\queue`):
- **Ctrl+Q / Ctrl+E while input is locked are dropped.** `HotkeyListener.WndProc` returns early for every `WM_HOTKEY`
  while `LockInputRuntime.IsLocked`, showing "Unlock Inputs First" (only the cutscene key and pass-through custom keys
  get through). The run pressed End (lock) at 09:25:38 and never unlocked; Ctrl+Q came at 09:26:35.
- **`Process.CloseMainWindow()` closes the wrong window.** It posts WM_CLOSE to the process's main window as .NET picks
  it; during a session the main form is hidden (rect Empty) and that window was Nucleus's pending "install post hooks"
  prompt (`PromptBetweenInstances`, open since 09:21:46). Closing it is what let setup finish ("All instances accounted
  for", 09:26:06), so the input tests before that ran without the post-launch hooks.
- The final `Stop-Process` of the games made Nucleus's update thread call End ("Killing process i76 ... Access is
  denied": the process was already going).

Clean stop, in order of preference:
1. At the keyboard: press **End** to unlock input, then **Ctrl+Q** (close Nucleus; it ends the session first) or
   **Ctrl+E** (end the session, keep Nucleus open).
2. From a script (works while locked): `autotest\nucleus-stop.ps1`, run elevated (through the bridge:
   `nucleus-q.ps1 -Cmd "& C:\Users\james\i76-uncap-lab\autotest\nucleus-stop.ps1"`). It posts WM_CLOSE to the form titled
   "Nucleus Co-op" (hidden or not); `MainForm_Closed` -> `End(false)`, which skips the lock check, kills the games and
   restores windows. It waits 30 s and only then falls back to Stop-Process, and says so. **Not run yet** (needs an
   elevated session).
Debug log of a clean stop: `----------------- SHUTTING DOWN -----------------` with no "Access is denied".

## Owner checklist: real pads, two players, 2 minutes
Lab copies only (`game-nucleus`). About 15 minutes. You need two pads (or one pad + the keyboard) and to approve
Nucleus's UAC prompt.
1. **Plug the pads in**, then find their winmm ids (the only joystick API the game uses):
   `powershell -ExecutionPolicy Bypass -File C:\Users\james\i76-uncap-lab\nucleus-coop\find-pads.ps1`.
   It lists each present id with its name, then for 30 s prints `winmm id N moved` when you press a button on one pad
   at a time. Write down which id is which pad.
2. **Set `JOY_WINMM`** at the top of `Interstate76.js` (this folder): one entry per instance, instance 0 first.
   Keyboard + one pad: `[15, <pad id>]` (15 = no pad: instance 0 is the keyboard player and the IPX host).
   Two pads: `[<pad 1 id>, <pad 2 id>]`. Copy the file to `..\refs\nucleus\run\handlers\Interstate76.js`.
3. **STRLKUP.DLL** in `game-nucleus` must be the 2026-10-05 build or later (`findstr I76_NO_MINIMIZE STRLKUP.DLL`
   prints a line). Each instance's `mciproxy.log` should then show `joy-map: engine id 0 (joystick1) -> winmm id <id>`
   and `no-minimize: ... read back ok`.
4. **Start Nucleus** (`..\refs\nucleus\run\NucleusCoop.exe`, approve UAC). Pick Interstate '76, 2 players, side by side;
   keyboard on screen 1, a pad on screen 2 (the device screen does not route pads for this game; JOY_WINMM does). Play.
   Nucleus pauses between instances: click OK on each prompt once the instance sits in its menu, **including the last
   one (post hooks)**. Leave any Windows Firewall prompt alone: one PC does not need it.
5. **Network** (input unlocked, the mouse works in both windows): left window: MELEE > MULTI MELEE > HOST > IPX >
   BROADCAST GAME. Right window: MELEE > MULTI MELEE > JOIN > IPX; select "THE CRATER (1/4)"; JOIN GAME. Both windows
   should stay visible; if the left one minimises, note it (the switch did not load).
6. **Lock input: press End.** Drive for **2 minutes**: the keyboard drives only the left car, the pad only the right
   car. Note anything that crosses over (a keyboard key moving the right car, the pad moving the left one).
7. **Stop:** press End (unlock), then Ctrl+Q. If Nucleus stays open, ask an agent to run `autotest\nucleus-stop.ps1`.
   Leave `run\content` as it is; an agent checks `game-nucleus` md5s against Runs step 1.
Report: pass/fail for steps 5 and 6, what crossed over, and whether Ctrl+Q closed everything.

## Rules
Lab copies only (`game-nucleus` for Nucleus runs; `game`, `game-alt` belong to other tests). Never the daily driver
or the golden copy. Nothing from here is promoted to i76-everywhere until two instances share a session and the
owner has played it.
