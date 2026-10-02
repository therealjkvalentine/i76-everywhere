# Menus and shell on a modern machine: pain points, status, fixes, plan

*Survey written 2026-10-01 from the repo docs, the i76-uncap-lab proxy source, the i76-map shell track and a read-only
look at both installs. Nothing was run and nothing outside this file was edited. Every line is tagged **[fact: source]**
(measured or read from code, with where) or **[proposed]** (not built, or built but not shown to work in a running game).
Status words: **fixed** = confirmed in the field or live; **built, unverified** = bytes exist, no live run; **open**.*

Read first if you only have five minutes: section 1 (the catalogue), section 5 (the plan). Section 4 says which binary
owns what, because every fix below lands in one of four places: `i76.exe`, `i76shell.dll`, the `u32x.dll` USER32 proxy
(i76-uncap-lab), or the `Strlkup.dll` proxy (music-fix). Rule carried over from AGENTS.md: everything is tried on the
lab copy `C:\Users\james\i76-uncap-lab\game` at the physical console first; the portable install is promoted to, never
experimented on.

## 0. What is deployed right now (measured 2026-10-01, read-only)

| item | daily driver (portable 20260801) | lab copy (i76-uncap-lab\game) | note |
|---|---|---|---|
| `i76shell.dll` md5 prefix | `fd96f871` | `fd96f871` | a UCyborg-pack lineage shell (FIXES.md lists `fd96f871` with `8960fa16`/`36dab830`), not pristine `deb41008` |
| text-entry bytes 0x1B52C / 0x1B535 | `41` / `08` (stock, repaired) | `41` / `08` | F1 holds on both |
| shell USER32 import | retargeted to `u32x.dll` | same | `i76.exe.u32xorig` present on both: deploy-shellfix retargets the exe's USER32 import too |
| `u32x.dll` | 75,264 B, 2026-09-07 | 75,264 B, 2026-08-16 | **neither contains the string `DisableProcessWindowsGhosting`**: the ghosting fix (uncap-lab commit `aff1c46`) is on no install. `u32x.dll.ship` sits beside the daily driver's |
| dgVoodoo cursor | `CaptureMouse=true`, `FreeMouse=false` (dgVoodoo's emulated cursor) | same | the repo's `dgVoodoo.conf` says `CaptureMouse=false`; the installs disagree with it. SAVE-FREEZE 2026-09-07: James confirmed saving works with `true` |
| dgVoodoo window | `FullScreenMode=false`, `FullscreenAttributes=fake`, `WindowedAttributes=borderless`, `ScalingMode=stretched_ar`, `Resolution=1680x1050` (both sections), FPSLimit 19.2 | same but Glide `3360x2100`, `WindowedAttributes=border`, FPSLimit 21 | |
| `Strlkup.dll` proxy | deployed (`strlkup_orig.dll`) | deployed | carries `apply_mission_launch` and the I76_* opt-ins |
| cursor overlay | `_ahk\i76-cursor-overlay.ahk` present | absent | PLAY-i76.ps1 starts it by default |

Measured client geometry for this configuration (SAVE-FREEZE-ROOT-CAUSE v2, CONFIG-OPTIONS.md §3): the game window is
3440x1440; the 640x480 shell is drawn pillarboxed at 3.0x, screen x 760..2680. dgVoodoo's windowed `Resolution` does
not size this game's window in Glide mode (tools\bisect\README.md: four settings tried, every one gave a 3440x1440
client); the window is the game's.

## 1. Catalogue of pain points, with status and root cause

| # | pain point (as reported) | status | root cause, with reference |
|---|---|---|---|
| P1 | mouse clicks miss, "click once to wake the pointer", pointer confined to a corner | **fixed in the field**, with a caveat (below) | Shell `MouseUpdate` 0x1001fbf0 converts to client coords but never scales to 640x480 and discards every sample outside 0..639/0..479 **including button state** (i76-map shell FIXES.md F4, instructions 0x1001fca9..0x1001fcc7); exe-side `input_*` 0x44b7f0..0x44bcc0 own `ClipCursor`/`GetCursorPos` (symbols/imports.tsv). Fix in place: `u32x.dll` translating GetCursorPos/SetCursorPos/ClipCursor/PeekMessageA lParams, deployed to both binaries (deploy-shellfix.ps1). Caveat: with `CaptureMouse=true` u32x's `pointer_is_confined()` sees a 640x480 clip and passes through, so it is dgVoodoo's emulated cursor that is doing the mapping today, not u32x. 2026-09-05 automation said `CaptureMouse=true` traps the pointer in the black bar; 2026-09-07 James said saving works with it true. The two records conflict and the automation's clicks were later shown to be the unreliable instrument (memory: verify the click landed). Needs one hand check, not a patch. **Field 2026-10-02** (sandbox, `CaptureMouse=true`): the mouse is dead on the Save Bookmark screen only — every other screen clicks where the pointer is and keyboard saving works. The true/false regime test is backlog P1-02; record the winner here and in `dgVoodoo.conf` (P3-16). |
| P2 | "Overwrite an existing bookmark?" freezes the game, 100% CPU, Windows says not responding | **fixed in the field** by P1; keyboard escape **built, unverified** | `Modal_YesNo` 0x1000bc40 loops on `MouseUpdate` + `MouseClicked` only; no key read, no pump, no timeout (FIXES.md F3, 0x1000bd2d..0x1000bd90; the 2026-08-10 stack sample `i76shell+0xBD38` is this loop). F3 adds Y/N/Esc via a 70-byte cave at 0x10040340: emulated 10/10 in `tools\emu_f3.py`, never run live (LIVE-TESTS T4). |
| P3 | can type at most one character into the bookmark name | **fixed, live** (2026-09-07, James: "yep that's it") | two bytes in the pack shell narrowed `KeyInput_Poll` 0x1001c110's clear so ToAscii's output word kept a stale high byte (SAVE-FREEZE-ROOT-CAUSE "two bytes"; FIXES.md F1/P4). Repaired on both installs; `PLAY-i76.ps1` re-applies at launch; `tools\fix-shell-textentry.ps1`. The stock bounds are correct; the pack's "OOB fix" fixed nothing. |
| P4 | Save Bookmark screen goes dead after ~6 s idle (one event then nothing) | **fix built and lab-shown by automation, deployed nowhere** | DWM ghosts the window because the shell's modal edit loop (`TextField_Edit` 0x1001c7b0 inside `SaveMenu_Open`) and `Modal_YesNo` pump only keyboard messages or none (SAVE-FREEZE-ROOT-CAUSE 2026-09-06 census: deactivation at t+5.9 s, then a starving `PeekMessageA(WM_KEYFIRST..WM_KEYLAST)`). Fix: `DisableProcessWindowsGhosting()` in u32x `DllMain` (uncap-lab `aff1c46`). Not required to save when typing promptly (2026-09-07), but a player who pauses six seconds over a name hits it. Neither install's `u32x.dll` carries the call (section 0). Does not occur under Wine (no DWM). |
| P5 | a bookmark "vanishes": `savegame.dir` names `saveNNN`, disk has `save-01.cmp` (Mac) / predicted `save-001.cmp` (Windows) | **root cause found statically; 10-byte fix built, unverified** | `SaveMenu_Edit` 0x100147a0 sets the slot variable `0x10057f80 = -1` on every entry (0x10014866). Re-entering the edit (click on the name field, or NO on the prompt) after the record was already appended with slot S skips the slot assignment (0x100149d7) and saves with -1 (shell SAVE.md §4). The trigger sequence was trained by P3 ("click somewhere to get it to type"). `dir_Load` 0x10033020 then drops any record whose `.cmp` does not open, which is why the bookmark disappears rather than showing broken. Fix F2: NOP the 10 bytes at file offset 0x13c66 (FIXES.md). Live test T3 not run. Rescue exists on the Mac stub (`rescueOrphanSave`), not on Windows. |
| P6 | "it always says I am overwriting even on a new save" | **explained; not a bug; UX improvement open** | A row click takes the prompt path unconditionally; a typed name prompts only when an entry with the same scene *and* name exists (SAVE.md §4, 0x10014a78 / 0x10014d75). Field version: the name matched the loaded bookmark (SAVE-FREEZE v2). Improvement = a fresh default name (E3 below). Residual, cosmetic: a row click rewrites that entry's scene with the current scene before any confirmation (0x10014924), which is the "save009 bumped 6 to 7" report. |
| P7 | `savegame.dir` is "truncated 36 bytes short" on every save; launcher re-pads | **misdiagnosis to retire** | The header is 4 bytes, not 0x28; `4 + 60n` matched 15 of 15 game-written files, and every "short" file was one our tools re-padded (SAVE.md §1; writer `dir_WriteAndSave` 0x10032f80, reader loop bound 0x100330f3). The re-pad in `PLAY-i76.ps1` (lines 176..210) and the `Get-Health` check in `LAUNCHER.ps1` (0x28 model) are harmless but wrong, and AGENTS.md's invariant repeats it. Proposed: retire the guard, fix the launcher model, correct AGENTS.md (owned by the main session). |
| P8 | `Please insert CD "Interstate '76 CD 2"` modal, OK re-prompts forever, Cancel exits | **open on the pristine/lab exe; not seen on the daily driver since July** | Two owners, both exe: (a) `shell_cb_17` 0x470f90, called by the shell on message 0xC010 (go) before every mission; returns -1 (no movie, no prompt) when the MCI cdaudio open failed, otherwise scans CD-ROM drives (`GetDriveTypeA==5` table 0x609520) with `GetVolumeInformationA` for label `I76_CD2` and prompts through `startup_MessageBoxOkCancel` 0x471580 (i76-map status\tasks\m12-cd-prompt.md; shell\CALLBACKS.md slot 17); (b) the VFS fallback: `vfs_FindContainerForFile` 0x4b2e00 calls `cd_PromptLoop` 0x470d90 at 0x4b2faa after a failed local read; an empty wanted label matches any readable CD volume. Live reading: the prompt needs `cd2_drive_index` 0x58d92c == 0 after the scan, and the last candidate is a transient `GetVolumeInformationA("E:\")` failure on the mounted CD1 ISO (m12 "corrected reading"). Seen 6 times in ~21 lab launches (sitting-1-notes); the launcher-path theory was refuted. On the daily driver the Strlkup proxy's virtual cdaudio plus the AiO exe ran "with music, saves and no CD prompt" (FINDINGS-2026-07 §1). |
| P9 | boot is 60..75 s of PLEASE STAND BY plus intro and credits movies; no obvious skip | **partly open** | Esc (sometimes twice) skips at boot (FINDINGS-2026-07). In-mission cutscenes: WndProc 0x4048b7, Esc calls 0x49a9f0 and the mode returns to 1 (i76-map mission.md, mode 0x20). `I76_SKIP_MOVIES=1` invalidates the intro/credits names (0x4c25b0, 0x4c25a4) so the engine takes its own open-failed path at 0x403056/0x403058 (MISSION-LAUNCH.md), **but the check sits inside `apply_mission_launch` after `if (n == 0) return;`, so it only works together with `I76_MISSION`** (strlkproxy.c lines 651..704). On a normal menu boot there is no movie skip switch. |
| P10 | the shell is small / blurry / "can it be bigger" | **fact; conf-level options open** | The shell is fixed 640x480: ShellMain stores 640/480 at 0x1001e420/0x1001e42a and discards `GetClientRect`; DATABASE.MW2 backgrounds are 640x480 PCX (shell SCREENS.md, README). It is scaled by dgVoodoo's DDraw wrapper (Windows) or DxWnd (Mac). Today: `stretched_ar`, `Resampling=bilinear` (daily) / `lanczos-3` (lab conf), screen-height fit = 3.0x. Nothing makes it render at higher internal resolution. |
| P11 | in-mission Esc menu: "mouse weirdness at forced res, navigate by keyboard"; "the Options/Abort menu mouse never worked" | **open, needs a hand check after P1** | This menu is the **exe's** (`shell_BeginInGameMenu` 0x4953e0, `shell_MenuHandleMouse` 0x4972d0, pages from `plyopt1.map`/`grxdet1.map`/`audcon1.map`/`extgme1.map`), not the DLL's (shell SCREENS.md "Not the shell"; i76-map options.md, mission.md). Its mouse comes from `mouse_Poll` 0x44b8c0 through the exe's `GetCursorPos` import, which deploy-shellfix now retargets to u32x. **Field 2026-10-02:** still broken after the retarget — in fullscreen the Esc menu's mouse cannot reach the Exit button (raw coordinates); backlog P1. |
| P12 | in-game Control Configuration destroys `input.map` (steer/throttle gone, every button on the last joystick) | **mechanism known; mitigated by the launcher guard; prevention is a policy call** | 12 loss mechanisms in `InputMap_Read` 0x1000f390 / `InputMap_Write` 0x1000fd30; Done writes, Esc does not (shell INPUTMAP.md). Options: make `input.map` read-only (then `fopen("w")` at 0x1000fd41 fails; whether the null handle is checked is LIVE-TESTS T7c), or a 5-byte NOP over the write call at 0x1000efe8 (view-only menu). `PLAY-i76.ps1` restores analog sinks from a backup when they are missing. |
| P13 | the OS pointer is invisible over the game, so a waiting modal looks like a freeze | **mitigated** (overlay), cause open | `i76-cursor-overlay.ahk` draws a click-through crosshair that follows the real pointer; its header lists what was measured and ruled out (dgVoodoo, ShowCursor count, class cursor, .cur files, WM_SETCURSOR). |
| P14 | modal Win32 dialogs ("you need brakes", CD prompt) trapped behind exclusive fullscreen: black screen, no Alt+Tab | **fixed** | `FullScreenMode=false` + `FullscreenAttributes=fake` (dgVoodoo.windows.conf, FINDINGS-2026-07). |
| P15 | with Lossless Scaling running, "rename variant", "exit without salvage", "overwrite" prompts could not be interacted with (2026-08-08) | **open hypothesis** | LS presents through an always-on-top borderless overlay; a shell-drawn prompt waits under it (FINDINGS-2026-07 §1, "decisive test costs one launch": `PLAY.bat` without LS). Note `PLAY-i76.ps1` starts LS by default. Most of the symptom was later explained by P1..P4, so this may already be moot; untested. |
| P16 | turning on a Play Options cheat asks "I'm a cheater / I'm a swinger", and a cheated win counts as a fail with no salvage and no scene advance | **by design; document it** | cheats marker 0x535f78 set by the exe's option handlers; WinMain turns success into 0xb, the mission-over menu turns 0xb into 0 and adds "Turn off Cheater Options" (i76-map cheats.md, mission.md). Confirm page 0x4fd018 (plyopt1.map, Esc disabled); exit dialog 0x4fcec0 (extgme1.map, "Are you gonna leave me, Sweetheart?"); the code number on menu pages is `(level+900)*1000 + rand()%992`, rerolled per level in `shell_DrawMenuPage` 0x496870 (mission.md wave 5). |
| P17 | both installs run a pack-lineage shell that is not the pristine GOG DLL | **fact, decision open** | Pack diff vs pristine: P1 cursor-handle caching (benign), P2 GDI blit check removed (GDI path only), P3 palette toggle (GDI only), P4 the harmful ToAscii narrowing, already repaired (FIXES.md "Pack diff"). The pack's cave at 0x10040340 is the one F3 wants; `patch_shell.py` moves one of them. Decision: stay on pack+F1, or move to pristine+P1+F2/F3 built by `patch_shell.py`. |

## 2. Open items: concrete fix options

Each option names the code site, the vehicle (shell file patch / u32x runtime patch / Strlkup runtime patch / data or
conf edit / launcher), effort (S under an hour, M a sitting, L several), and risk.

### P5 orphaned bookmark (F2)

| option | site | effort | risk |
|---|---|---|---|
| **A. shell file patch** [built] | `python tools\patch_shell.py --fixes F2 --out patched\...` on pristine `deb41008`: 10 x `90` at file 0x13c66, reloc for the disp32 at 0x10014868 neutralised (shell FIXES.md). Output `patched\i76shell-F2F3F4F6.dll` already exists (md5 `4d36752b...`). | S to build, M to verify | low for F2 alone; swapping to the pristine lineage drops pack P1..P3 (benign) and must keep F1 (pristine is already correct) |
| **B. u32x runtime patch** [proposed] | u32x loads *as the shell's import*, so when its `DllMain` runs the shell is mapped: `HMODULE sh = GetModuleHandleA("i76shell.dll")`; verify 10 bytes at `sh + 0x14866` == `C7 05 <disp32> FF FF FF FF` where `disp32 = (DWORD)sh + 0x57f80` (the DLL has relocations; SCREENS.md); `VirtualProtect` + write 10 x `90`. Same instruction bytes in pack and pristine (the pack diff touches none of `SaveMenu_Edit`). | S | low; keeps the installed shell as is; verify-before-write like `patch_bytes` in strlkproxy.c |
| C. launcher rescue [proposed] | port the Mac stub's `rescueOrphanSave()`: at launch, for each `savegame.dir` record whose `.cmp` is missing, rename `save-001.cmp` (or `save-01.cmp`) to it | S | recovery only; the game still writes the orphan |

### P2 prompts answerable by keyboard (F3)

| option | site | effort | risk |
|---|---|---|---|
| **A. shell file patch** [built, emulated 10/10] | `0x1000bd51: 83 F8 01 75 D7 -> E9 EA 45 03 00` (jmp to cave 0x10040340); cave calls `KeyInput_Poll` 0x1001c110: Esc or `n` = NO (0x1000bd99), `y` = YES (0x1000bd92), Enter deliberately not YES. Two HIGHLOW relocs added; `.text` VirtualSize raised 0x3f340 to 0x3f400 (FIXES.md F3). All `Modal_YesNo` callers gain it (garage, Graphic Detail, Play Options, Save, inventory). | M | medium: cave region collides with the pack's P1 cave if applied to the pack shell; the tool targets pristine only |
| B. u32x runtime equivalent [proposed] | same jmp from `sh+0xbd51` into a cave allocated by u32x (`VirtualAlloc` executable, or a static naked function) that reproduces the F3 logic and jumps back to `sh+0xbd56/0xbd92/0xbd99`. | M | medium: needs the same register discipline the emulated cave already proved; a second implementation to verify |
| C. extend F3 to `Modal_Ok` 0x1000b660, `Modal_ImageOk` 0x1000b800, `Modal_CdRetry` 0x1000bad0, `Modal_VehicleRejected` 0x1000b980 [proposed] | same mouse-only loop shape (FIXES.md "Minor defects") | S each once A or B exists | low |

### P4 DWM ghosting

| option | site | effort | risk |
|---|---|---|---|
| **A. deploy the built fix** [built, lab-shown] | rebuild `u32x.dll` from `i76-uncap-lab\src\u32x.c` (ship build, no `U32X_LOG`), confirm the string `DisableProcessWindowsGhosting` is in the binary, `tools\instruments\deploy-shellfix.ps1 -GameDir <lab>` | S | low: one documented per-process switch; the shell patch route is unavailable (the DLL imports neither `GetProcAddress` nor the function, FIXES.md F5) |

### P8 "insert CD 2"

| option | site | effort | risk |
|---|---|---|---|
| A. instrument first [proposed, the m12 plan] | on the next prompting instance (the dialog is modal, attaching is safe) read the file name `vfs_LoadZix` 0x4b23e0 / `vfs_FindContainerForFile` 0x4b2e00 was opening and call `GetVolumeInformationW("E:\\")` from outside at the same moment (m12-cd-prompt.md last section) | M (needs the prompt to recur) | none |
| B. Strlkup IAT hook on `GetVolumeInformationA` [proposed] | IAT slot 0x4bc0c8 (callers 0x470d40, 0x470d90, 0x470ed0, 0x470f90, 0x471250): on failure for a CD-ROM root, return success with label `I76_CD2`. Satisfies both the movie scan and `cd_PromptLoop`'s "any readable volume". | S | medium: if the VFS then tries the "CD" for the file it could not open locally, the read fails again; the loop's retry behaviour after a label match is untraced. Needs A first |
| C. make `shell_cb_17` never prompt [proposed] | its arg 0 path "returns 1 without prompting" (exe-callbacks.md slot 17); the DLL passes the arg at 0x1001e0fe/0x1001e118. Patch the push to 0 (u32x runtime, shell side) or patch 0x470f90's prologue (Strlkup). Only the pre-mission movie check; leaves the VFS fallback alone | S | low for the movie path; does nothing for the VFS owner |
| D. keep the ISO mounted and let `cdaudio_probe.py` gate launches [exists for the harness] | `i76-map\tools\cdaudio_probe.py` | S | none; harness-only |

### P9 movie skip

| option | site | effort | risk |
|---|---|---|---|
| **A. decouple `I76_SKIP_MOVIES`** [proposed] | move the block at strlkproxy.c 694..702 out of `apply_mission_launch` (before `if (n == 0 ...) return;`) so it runs on a plain boot; add `-SkipMovies` without `-Mission` in `PLAY-i76.ps1` (line 334..343 currently nests it) | S | low: same two one-byte string patches, same engine open-failed path; verify `mciproxy.log` shows "movie names invalidated 2/2" and the main menu appears with no intro |
| B. a skip key for the intro [proposed] | trace the intro loop around 0x403056 for a key poll; Esc is already honoured for in-mission movies (0x4048b7). Unknown whether the boot movies poll | M | unknown |

### P10 bigger / crisper shell

| option | site | effort | risk |
|---|---|---|---|
| **A. integer scale** [proposed] | `[GeneralExt] ImageScaleFactor = 3` (nearest-point, independent of ScalingMode; 640x480 -> 1920x1440 fits a 1440-high panel exactly) with `Resampling = pointsampled`, or keep `lanczos-3` for a softer look. dgVoodoo.conf comments document both keys. Shell only sees 640x480 either way. | S | low; conf-only; does it affect the Glide 3D frame too? (ImageScaleFactor applies to "the output image coming from a wrapped API", so probably both; check) |
| B. Mac: DxWnd | already letterboxed 4:3 to screen (DXWND-TUNING.md); HQx filters need an emulated renderer, which reintroduces black menus | n/a | documented tension |

### P11 in-game Esc menu mouse

Hand check only: open Esc in a mission, hover Play Options; does it highlight where drawn? If not, the exe's `mouse_Poll`
0x44b8c0 path through u32x's `My_GetCursorPos` is the site to log (the `U32X_LOG` build already has `log_caller`).

### P12 Control Configuration

| option | site | effort | risk |
|---|---|---|---|
| A. `input.map` read-only [proposed] | launcher sets the attribute; `fopen("w")` 0x1000fd41 fails; T7c decides whether the null handle crashes | S | unknown until T7c |
| B. 5-byte NOP at 0x1000efe8 [proposed] | Done no longer writes; the menu becomes view-only (INPUTMAP.md "Binary option") | S | low; policy: some players rebind in the menu |

### P15 Lossless Scaling overlay

One launch with `-LosslessScaling ""`, trigger an overwrite prompt. If it behaves, suppress LS while a shell screen is up
(shell state is readable: `0x100d2168` / `0x100d21a0` / `0x100d21a4`, SCREENS.md) or leave LS off by default.

## 3. Ease-of-use features worth adding

### E1 Skip-to-mission / resume campaign

**Where `apply_mission_launch` stands** [fact: MISSION-LAUNCH.md, strlkproxy.c 651..704, i76-map mission.md]: writes
`startup_mission_name` 0x5049f0, NOPs the two clears (0x402d33, 0x49d1e0), sets the skip-shell dword 0x504c10 = 1, and the
mission loads with no shell at all. Three things make that far from "resume":

1. **The car.** WinMain seeds `0x5dd370 = 'vppirna1'`; only `shell_RunAndGetChoice` 0x4022e0 copies the shell's car name
   `0x5dcea9` into it, so a mission entered without the shell drives the stock Piranha (mission.md "Player car in scripted
   missions"). The `.vsf` state (`<basename>.vsf`, armour/chassis/component hp, WPST) is loaded only for trip missions and
   only for the car's basename; `vppirna1.vsf` does not exist.
2. **The garage round trip is shell-only.** Loading a bookmark is `Screen_LoadBookmark` 0x10013380: `Cmp_Read` 0x10032bf0 of
   `saveNNN.cmp`, then `Vehicle_WriteVcf` 0x10035250 and `Vehicle_WriteVehState` 0x10035930 write `addon\vehscn.vcf` /
   `.vsf` through exe callbacks 08/09/02 (shell SAVE.md, CALLBACKS.md, work\cmp-layout.md). Nothing in the exe reads a `.cmp`.
3. **No way back.** With 0x504c10 set, every end state except 7 (replay) exits the game (mission.md state 0xa row), so there
   is no post-mission garage and no save.

**Options** [proposed]:

| option | how | effort |
|---|---|---|
| **A. "Continue" = drive the shell for the player** | u32x already lives inside the shell's process. On `ShellMain` entry (or when `shell_current_screen_msg` 0x100d2168 first reads 0xC00E), post the clicks the main menu takes: LOAD BOOKMARK at UI (276,351), pick the row, Load (SCREENS.md main-menu table; the Load menu's row/Load regions still need decoding, `LoadMenu_Frame` 0x10013060). Or `PostMessageA(hwnd, 0xC01D, ...)` directly if `Screen_LoadBookmark`'s argument (which entry) is traced. Choose the entry by newest `.cmp` mtime or `savegame.dir` order. | M: the trace of how `LoadMenu_Frame` hands its selection to 0xC01D is the one unknown |
| B. launcher automation | the uncap-lab harness already does cold launch -> intro skip -> menus by coordinate clicks (`autotest\enter-trip1.ps1`, `lib\uiclick.ps1`); a `-Resume` switch in `PLAY-i76.ps1` could reuse it. Fragile (focus, timing), and it owns the console while it runs | S to wire, fragile |
| C. make the direct boot a *trip* boot | set `0x5dcea0 = 2`, copy `'vehscn'` into 0x5dd370, let `vehscn.vsf` load, and clear 0x504c10 after the first frame so the end-of-mission flow returns to the shell garage. Needs `addon\vehscn.vcf` to already be the wanted car (it is, after any shell visit) | M, and it reproduces shell state by hand: brittle |

Recommendation: A. The shell does the right thing once it is told where to click; the state globals make it verifiable
without screenshots (`tools\shellstate.ps1`).

### E2 Remember last menu choices

[fact] The only persisted menu state is the options block: the exe writes 0x60 bytes from 0x654b40 to `I76PLYR.DEF`
(`player_SaveDef` 0x497290, at mission end and on the graphics-mode key) and reads it back after every shell return
(`player_LoadPlyrDef` 0x4970f0); the shell reads the same file (`PlayerDef_Load` 0x10016f70) (i76-map mission.md,
options.md; shell CALLBACKS.md arg 8). Main-menu branch, melee car/arena and entry-form fields are not persisted.
[proposed] Low value for a trip player; E1 covers the one choice that matters. Skip.

### E3 Default a fresh save name

[fact] `SaveMenu_Edit` clears the static edit record (`0x10057f3c = 0`) and draws "Scene %d." from `*arg7` (SAVE.md §3); a
typed name only prompts when scene+name already exist. [proposed] Seed the 32-byte buffer at `0x10057f3c` after the clear
with `Scene N <HHMM>` (or the mission name) so SAVE with no typing lands in a new slot. Site: the store after 0x10014866
(same function; exact instruction to cite from `tools\sdis.py fn 0x100147a0`). Vehicle: u32x runtime cave. Effort M.
Risk low. Depends on F2 first, otherwise the no-typing path is the one that orphans.

### E4 Bigger shell window scaling

Covered in P10: the shell is 640x480 by construction; dgVoodoo scales it; `ImageScaleFactor=3` is the crisp option; the
Mac is DxWnd-letterboxed. No patch route exists for a higher internal shell resolution (every widget table and background
is in 640x480 units).

### E5 Key to skip movies

Covered in P9: in-mission Esc works; boot movies need `I76_SKIP_MOVIES` decoupled from `I76_MISSION` (option A, S).

### E6 "Insert CD 2" elimination

Covered in P8. On the daily driver this has not been reported since the Strlkup proxy and the AiO exe; the lab's
intermittent prompt needs the instrument run before any hook is written.

### E7 The debug menu

Three different things carry the name:
- `tools\i76-debugmenu.ahk` (+ `debugmenu.sh`): the Wine-side trainer window (ammo table, freeze, F6 rearm, F4 armour scan)
  from DEBUG-MENU-FIELD-TEST.md. Runs 1 and 2 done 2026-07-19; the armour map was later solved another way (entity +0x138).
- the exe's built-in debug gamekeys: dead in Gold (they reach the key queue 0x608e60 and render nothing; FRESH-START §11).
- the shell's coordinate readout: `MouseUpdate` prints `(x,y)` at (560,20) while the right button is held when
  `[0x10047720]==0`; shipped as 1; file offset 0x45f20 `01 -> 00` (FIXES.md F6). The right instrument for any mouse test.
[proposed] A Windows trainer belongs in Strlkup as opt-ins (`entity_ApplyDamage` 0x465620 early-return for the player,
Play Options dword 0x654b98 pokes; cheats.md §4), not in the menus. Out of scope for this plan beyond F6.

### E8 Launcher

[proposed, S each] `LAUNCHER.ps1`: show `-Mission`/`-SkipMovies`/`-Resume`; fix `Get-Health`'s `savegame.dir` model to
`4 + 60n`; show whether `u32x.dll` carries the ghosting call (string check); show the shell lineage md5 and F1 state (it
already shows F1). `PLAY-i76.ps1`: retire the re-pad block or re-model it to `4 + 60n`.

## 4. What is in the exe vs the shell DLL (who owns which track)

| area | binary / owner | anchors |
|---|---|---|
| game state machine; when the shell runs | `i76.exe` (i76-map main track) | state 0x4c2164: 5 running, 6 shell, 7 replay, 8 reconfigure, 9 load bookmark, 0xa exit, 0xb cheated win (mission.md); `shell_RunAndGetChoice` 0x4022e0 -> `ShellMain` at 0x4031f5; skip-shell dword 0x504c10 (cmp at 0x403197) |
| shell loading | `i76.exe` | `LoadLibraryA("I76SHELL.DLL")` inside WinMain 0x402b30 (strings.tsv 0x4c2630). Dynamic, so Strlkup's DllMain runs before the shell exists; u32x's runs after (it is the shell's import). **Shell-side runtime patches belong in u32x; exe-side ones in Strlkup.** |
| the in-mission Esc menu (Abort, Load Bookmark, Play Options, Graphic Detail, Audio, Exit, mission-over Replay/Reconfigure) | `i76.exe` | 0x495070 open, 0x4953e0 begin, 0x4956e0 show page, 0x496870 draw page (code number), 0x496e10 keys, 0x4972d0 mouse, 0x497760 mission-over, 0x497b20 strings; pages `plyopt1.map` etc.; dialogs 0x4fd018 cheat confirm, 0x4fcec0 exit; `foldin\shell-menu-items.tsv` for label -> handler |
| options block and `I76PLYR.DEF` | `i76.exe` writes/reads; shell reads | 0x654b80.. (options.md); `player_SaveDef` 0x497290, `player_LoadPlyrDef` 0x4970f0; shell `PlayerDef_Load` 0x10016f70 |
| exe-side mouse layer (sim and Esc menu) | `i76.exe` | `input_ReleaseCursor` 0x44b7f0, `input_RecenterCursor` 0x44b830, `mouse_Poll` 0x44b8c0, 0x44bb40, 0x44bcc0 (imports.tsv: GetCursorPos/SetCursorPos/ClipCursor) |
| CD check and prompt | `i76.exe` | `shell_cb_17` 0x470f90 (called by the shell on 0xC010), `cd_ProbeVolume` 0x470d40, `cd_PromptLoop` 0x470d90, `startup_MessageBoxOkCancel` 0x471580, VFS callers 0x4b23e0 / 0x4b2e00 |
| movies | `i76.exe` | intro/credits at 0x403056; in-mission 0x49a070 play, 0x49a9f0 end (Esc at WndProc 0x4048b7); names 0x4c25b0 / 0x4c25a4 |
| direct mission boot | `i76.exe` + `Strlkup.dll` | 0x5049f0, 0x402d33, 0x49d1e0, 0x504c10; `cmdline_Parse` 0x49d1d0 has no mission argument |
| every 2D screen: title, main menu, garage, inventory, parts, mission grid, entry forms, standings, Options notepad, Save/Load Bookmark, Credits, Control Configuration | `i76shell.dll` (i76-map shell track) | ShellMain 0x1001e260, ShellWindowProc 0x1001da10, messages 0xC008..0xC026, menu index 0..11; state globals 0x100d2168 / 0x100d219c / 0x100d21a0 / 0x100d21a4 (SCREENS.md) |
| `savegame.dir`, `saveNNN.cmp`, `reconfig.spc`, `trip4.spc` | `i76shell.dll` | `dir_Load` 0x10033020, `dir_WriteAndSave` 0x10032f80, `Cmp_Write` 0x10032980, `Cmp_Read` 0x10032bf0, `SaveMenu_Open/Edit/Frame` 0x100145f0 / 0x100147a0 / 0x10014cd0, `Screen_LoadBookmark` 0x10013380 |
| trip scene counter | both | exe dword 0x4c2160, passed as ShellMain arg 7, incremented by the DLL after a won mission (CALLBACKS.md) |
| `vehscn.vcf` / `.vsf` | shell writes via exe callbacks 08/09/02; exe loads | `Vehicle_WriteVcf` 0x10035250, `Vehicle_WriteVehState` 0x10035930; `bwd2_LoadVcfForObject` 0x4ad6f0 |
| modal prompts (yes/no, ok, CD retry, vehicle rejected) and the text field | `i76shell.dll` | `Modal_YesNo` 0x1000bc40 and siblings; `TextField_Edit` 0x1001c7b0; `KeyInput_Poll` 0x1001c110; key ring 0x1001d630 |
| shell mouse | `i76shell.dll` | `MouseUpdate` 0x1001fbf0 (GetCursorPos -> ScreenToClient, 640x480 constants from ShellMain 0x1001e420) |
| Control Configuration and `input.map` | `i76shell.dll` | `InputMap_Read` 0x1000f390, `InputMap_Write` 0x1000fd30, write call at 0x1000efe8 |
| menu art and strings | data: `DATABASE.MW2` (shell), `*.map` pages (exe menu) | `tools\mw2db.py`, `tools\mw2shape.py` |
| coordinate translation, ghosting, keep-alive | `u32x.dll` (i76-uncap-lab\src) | retargets USER32 for both the shell and the exe (deploy-shellfix.ps1) |
| exe-side runtime patches (music, mission boot, frame-rate fixes, opt-in bug fixes) | `Strlkup.dll` (music-fix\strlkproxy.c) | `patch_bytes` verify-before-write; `I76_*` env gating |

The exe addresses above are from the i76-map main track (md5 `9a232dcc`, the pristine 2017 build); the lab and the
daily driver run the 2019 AiO build `60abf7bc`, which the map records as "same link outside the 45 patched clusters"
(cheats.md header). Every shell address is for the DLL at its preferred base 0x10000000 and must be rebased live.

## 5. Prioritised plan

Order by (data loss first, then stuck states, then convenience), with the rule that each item is shown on the lab copy at
the console before it is promoted.

1. **F2, the orphaned bookmark** (data loss; root cause static; 10 bytes).
2. **P4, deploy the ghosting fix** (built, lab-shown; on no install).
3. **F3, keyboard answers to the yes/no prompts** (the last way to get stuck if P1 ever regresses; emulated 10/10).
4. Decouple `I76_SKIP_MOVIES` from `I76_MISSION` (S; strlkproxy.c + PLAY-i76.ps1).
5. Hand checks that cost one launch each: P1 cursor regime (CaptureMouse true vs false with the shipped u32x), P11 Esc-menu
   mouse, P15 LS overlay. Record results in SAVE-FREEZE-ROOT-CAUSE or here.
6. F6 readout (`01 -> 00` at file 0x45f20) on the lab shell for the tests above.
7. Launcher and doc hygiene for P7 (`4 + 60n`), LAUNCHER health rows for u32x build and shell lineage.
8. E3 default fresh name (after F2).
9. E1 "Continue" (after the `LoadMenu_Frame` -> 0xC01D selection trace).
10. P8 CD-2 instrument run on the lab, then the hook if the trigger is confirmed.
11. P12 policy: read-only `input.map` or the 5-byte NOP.
12. P10 `ImageScaleFactor=3` taste test.

### Item 1, fully specified: F2 orphaned bookmark

**Choice of vehicle.** Route B (u32x runtime patch) is recommended because both installs run the pack shell `fd96f871`
and `patch_shell.py` refuses anything but pristine. Route A is equally valid if James decides to move the installs to
pristine+P1 (section 1, P17).

**Bytes.** [fact: FIXES.md F2] At RVA 0x14866 in `i76shell.dll`:

```
C7 05 80 7F 05 10 FF FF FF FF      mov dword ptr [0x10057f80], 0xffffffff     ; slot := -1 on EVERY entry
```

File offset 0x13c66 (`.text`: file = RVA - 0x1000 + 0x400). Replace all 10 bytes with `90`.

**Route B code shape** [proposed], in `u32x.c` `DllMain` (`DLL_PROCESS_ATTACH`), after the ghosting call:

```c
HMODULE sh = GetModuleHandleA("i76shell.dll");
if (sh) {
    BYTE *p = (BYTE *)sh + 0x14866;
    DWORD disp = (DWORD)(DWORD_PTR)sh + 0x57f80;          /* relocated absolute of 0x10057f80 */
    BYTE expect[10] = { 0xC7, 0x05, 0,0,0,0, 0xFF, 0xFF, 0xFF, 0xFF };
    memcpy(expect + 2, &disp, 4);
    if (memcmp(p, expect, 10) == 0) { /* VirtualProtect RW, 10 x 0x90, restore, read back */ }
    else LOG("F2: bytes differ - not patched");
}
```

Gate it on `I76_SHELL_FIXES` containing `F2` (the Strlkup pattern) so a rollback is an environment change. Build x86
(`cl /O2 /LD u32x.c /link /DEF:u32x.def user32.lib`), confirm with `strings`/grep that the new build still has
`DisableProcessWindowsGhosting` (item 2 rides along), deploy with `deploy-shellfix.ps1 -GameDir C:\Users\james\i76-uncap-lab\game`.

**Why the write is safe** [fact: FIXES.md F2 "Why this is sufficient"]: `0x10057f80` is written at exactly three other
places (new-slot path 0x10014a26, row-pick sscanf 0x10014927, YES-to-overwrite 0x10014c48 / 0x10014f43), and the only read
that could see a stale value is the found-in-list path, which with F2 uses the slot the record was given when appended.

**Verification = LIVE-TESTS T3**, on the lab copy, physical console (`[System.Windows.Forms.SystemInformation]::TerminalServerSession`
must be False), `savegame.dir` and `save*.cmp` backed up first:

1. Control run with the unpatched shell: Load any bookmark -> garage -> Options -> Save Bookmark; type `ORPHANA`; click
   empty paper right of the list; click the name field; type `ORPHANB`; click SAVE. Close the game. **Prediction:** a new
   `savegame.dir` record named `ORPHANB` with file `saveS`, no `saveS.cmp`, and a new `save-001.cmp` (Windows `wsprintfA`
   gives `-001`; `-01` only under Wine). Parse the dir as `4 + 60n`, name at +4, file at +0x24.
2. Same sequence with F2 on. **Prediction:** `saveS.cmp` exists, no `save-00x.cmp`, the bookmark lists and loads after a
   restart.
3. Regression: a plain typed-name save and a row-pick overwrite (YES) both still work.

If step 1 does not orphan, SAVE.md §4's trace is wrong at step 1 or 2; read `lastwidget` / `menu_fn` with
`i76-map\shell\tools\shellstate.ps1` before concluding anything. Promote to the daily driver only after 2 and 3 pass,
keeping the previous `u32x.dll` as `u32x.dll.pre-f2`.

### Item 2, fully specified: deploy the ghosting fix

**State** [fact, measured today]: `u32x.dll` on both installs lacks the `DisableProcessWindowsGhosting` string; the source
(`i76-uncap-lab\src\u32x.c` lines 818..848) has the call; commit `aff1c46`.

**Steps.** Build the ship binary (no `U32X_LOG`; the log build is the 90 KB+ one `LAUNCHER.ps1` warns about). Check:
`Select-String -Path src\u32x.dll -Pattern DisableProcessWindowsGhosting -Encoding ascii` returns a hit, and size is in the
70..80 KB range. Deploy to the lab with `deploy-shellfix.ps1`. `-Status` must show both binaries PATCHED and the proxy present.

**Verification** (by hand; synthetic keystrokes land zero characters on this screen, SAVE-FREEZE "Still to verify by hand"):

1. Options -> Save Bookmark. Do nothing for 15 s (the unfixed build is permanently dead at ~5.9 s). Then type five characters:
   all five must appear. Click CANCEL: it must respond.
2. Save over an existing row and answer YES by mouse: `.cmp` mtime changes.
3. Non-regression: main menu hover highlights TRIP; the garage opens; a mission starts.
4. Optional instrument: the `U32X_LOG` build's census (`GetCursorPos` must hold ~30 per 500 ms through the whole wait, no
   `WM_ACTIVATE 0` line).

Then promote: copy over the daily driver's `u32x.dll` keeping `u32x.dll.ship` (already there) as the rollback.

### Item 3, fully specified: F3 keyboard answers

**Bytes** [fact: FIXES.md F3], pristine shell:

```
0x1000bd51   83 F8 01 75 D7            cmp eax,1 ; jne 0x1000bd2d
          -> E9 EA 45 03 00            jmp 0x10040340
cave 0x10040340 (70 bytes of .text slack):
             cmp eax,1 ; je 0x1000bd56                 ; unchanged mouse path
             mov ecx,[0x100cc50c] ; call 0x1001c110    ; KeyInput_Poll
             cmp eax,3 ; je 0x1000bd99                 ; Esc -> NO
             test eax,eax ; je 0x1000bd2d              ; nothing -> loop
             mov eax,[0x100cc50c] ; mov eax,[eax] ; or eax,0x20
             cmp eax,'y' ; je 0x1000bd92               ; YES
             cmp eax,'n' ; je 0x1000bd99               ; NO
             jmp 0x1000bd2d
```

Two HIGHLOW relocations for the absolutes in the cave; `.text` VirtualSize 0x3f340 -> 0x3f400 (header file 0x1c0). Enter is
not YES on purpose (the name field commits on Enter; key repeat could confirm an overwrite). Built by
`python tools\patch_shell.py --fixes F3` on `deb41008`; `tools\emu_f3.py` 10 cases, 0 mismatches.

**Vehicle.** On the pack shell the cave at 0x10040340 is occupied by the pack's P1 code, so either (a) move the installs to
pristine (then `--fixes F2,F3,F6` in one build, `patched\i76shell-F2F3F4F6.dll` minus F4, since F4 and u32x are exclusive)
or (b) port F3 into u32x with a u32x-owned cave (route B of section 2). (a) is already built; (b) is a second
implementation. Recommend (a) for the lab test, decide on lineage after it passes.

**Verification = LIVE-TESTS T4.** Options -> Save Bookmark -> click an existing row -> SAVE -> the prompt. `N` or Esc
returns to the edit screen with the `.cmp` mtime unchanged; `Y` overwrites (mtime changes); Enter does nothing. Stock
control: keys do nothing. Then the recovery case: with the prompt up and the mouse made useless (e.g. `CaptureMouse=false`
and u32x removed, large window), `N` still escapes. That is exactly the exit the 2026-08-10 freeze had no way to reach.

## 6. Facts to correct elsewhere (proposed edits, not made here)

- AGENTS.md "Other hard-won invariants": `savegame.dir` is `4 + 60n`, never truncated (SAVE.md §1). The re-pad guard in
  `PLAY-i76.ps1` and the 0x28 model in `LAUNCHER.ps1 Get-Health` follow from the wrong layout.
- SAVE-FORMAT-GAPS.md and SAVE-ORPHAN-INVESTIGATION.md: the orphan's mechanism is SAVE.md §4 (slot reset on edit re-entry),
  the editor is cleared, and `%3.3d` of -1 is `-001` on Windows, `-01` under Wine.
- The repo `dgVoodoo.conf` (`CaptureMouse=false`) and both installs (`true`) disagree; whichever the P1 hand check favours
  should become the single recorded value.
- `docs/MISSION-LAUNCH.md`: note that `I76_SKIP_MOVIES` is a no-op without `I76_MISSION` until item 4 lands.

## Sources

i76-everywhere: docs/SHELL-MENU-AND-SAVE-FREEZE.md, SAVE-FREEZE-ROOT-CAUSE.md, SAVE-ORPHAN-INVESTIGATION.md,
SAVE-FORMAT-GAPS.md, READY-TO-TEST.md, VERIFIED-FIXES.md, DEBUG-MENU-FIELD-TEST.md, MISSION-LAUNCH.md, WINDOWS-PLAYBOOK.md,
MODERN-SETUP.md, DXWND-TUNING.md, FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md §1, FRESH-START-2026-09-04.md §11; AGENTS.md;
tools/fix-shell-textentry.ps1, tools/bisect/README.md; PLAY-i76.ps1, LAUNCHER.ps1, dgVoodoo.conf, dgVoodoo.windows.conf;
i76-cursor-overlay.ahk; music-fix/strlkproxy.c.
i76-uncap-lab: src/u32x.c, tools/instruments/deploy-shellfix.ps1, docs/CONFIG-OPTIONS.md, autotest/README.md, git log.
i76-map: shell/README.md, SCREENS.md, SAVE.md, FIXES.md, CALLBACKS.md, LIVE-TESTS.md, INPUTMAP.md, shell/work/exe-callbacks.md,
shell/symbols/functions.tsv; subsystems/options.md, mission.md, cheats.md, renderer.md; foldin/shell-menu-items.tsv;
status/tasks/m12-cd-prompt.md, direct-mission-entry.md, sitting-1-notes.md; symbols/functions.tsv, globals.tsv, imports.tsv,
strings.tsv. Live install state: directory listings and byte reads of both game folders, 2026-10-01.
