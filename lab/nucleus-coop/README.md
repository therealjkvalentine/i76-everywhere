# Nucleus Co-op handler for Interstate '76 (SEPARATE EFFORT)

Started 2026-10-03. Kept apart on purpose: nothing here touches the i76-everywhere repo, the patch set, or the
daily driver. **Status: handler written against verified option names; never run.** Nucleus Co-op v2.4.2 is
unpacked (not installed, not run) in `..\refs\nucleus\app`.

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
| first Nucleus run | **gated** on an IPX session between `game` and `game-alt` without Nucleus | test plan below |

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
   The `.cmd` sets `I76_MULTI_INSTANCE=1` and the best-120 switch set (i76-everywhere `presets\best-120.psd1`),
   then reads this file.
3. Rewrites the instance's `input.map` (a real copy) so every `joystickN` becomes `joystick<JOY_SLOT[id]>`.
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

## Rules
Lab copies only (`game-nucleus` for Nucleus runs; `game`, `game-alt` belong to other tests). Never the daily driver
or the golden copy. Nothing from here is promoted to i76-everywhere until two instances share a session and the
owner has played it.
