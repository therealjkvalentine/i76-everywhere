# dgVoodoo update for the 26100.9711 Windows update, 2026-10-24

This is the dgVoodoo-compatibility lane. It follows LAPTOP-BENCH-2026-10-24 s.4: the laptop took the 2026-10-24 cumulative update
(KB5127647 / KB5127648 / KB5127690, 26100.9711), and after it dgVoodoo 2.87.3's DDraw.dll crashed at start-up.

**Result.** **dgVoodoo 2.87.5** (the current official release, 2026-09-15) fixes the DirectDraw start-up crash. Its
`DirectDrawCreate` returns hr=0 on the laptop. The game boots to the menus and into missions there. On this PC it behaves the same
as 2.87.3: gate rows 1, 3 and 9 PASS with the same numbers. **It does not make the laptop playable on its own.** The same Windows
update also replaced the 32-bit `winmmbase.dll`, and with the owner's presets about 60 % of boots now die 3 s in at
`winmmbase.dll+0x5AB3`. That is the July KB5101650 pattern. dgVoodoo cannot fix it (s.4). Nothing was rolled into the RC or the
The tester packages. The fold-in list is in s.5.

## 1. Candidates

All were downloaded from the official GitHub releases (`dege-diosg/dgVoodoo2`, `gh release download`). Each sha256 matches the
digest GitHub lists for the asset. Each is kept in its own folder under `<archive>\dgvoodoo\<version>\` (zip, `sha256.txt`,
extracted `x\`).

| version | date | asset sha256 | status |
|---|---|---|---|
| 2.87.3 | 2026-06-23 | `6fb954be...f867f` | what we ship. Our DLLs are byte-identical to this release (DDraw ab19386d, D3DImm c6bdfc62, D3D8 4127f3d9, D3D9 9b8e4916, Glide 259a4028, Glide2x 8af442bc, Glide3x 829f80cd, Cpl 487da424) |
| 2.87.4 | 2026-09-02 | (download blocked) | **Windows Defender quarantined the zip as `Trojan:Win32/Kepavll!rfn` the moment it landed.** The author calls this detection a false positive, and 2.87.5 was released because of it. No exclusion was added (owner's call), so 2.87.4 was not tested |
| **2.87.5** | 2026-09-15 | `5ffde692...40850` | tested below. Defender on both machines left it alone |

There is no newer WIP. dege.freeweb.hu could not be reached from the sandbox, and a WebFetch of the page shows no WIP builds.
**Release notes:** 2.87.4 says *"Fixed the crash with Win11 26H1+ builds (version 28000.xxxx and above)"*. The 26100.9711
cumulative update appears to have brought the same change back to 24H2, and that is the crash we saw (inference, not proven).
2.87.5 adds D3D12 debug-layer fixes, D3D12BoundsChecking on by default, a D3D9 forced-resolution viewport fix and
`DirectExt\AlternativeScaling` exposed. **No conf key was renamed or dropped.** All 136 key=value lines of our `dgVoodoo.conf`
(dccd379a) exist in 2.87.5's default conf under the same section, and `Version = 0x287` is unchanged. The new keys default to
behaviour equal to 2.87.3, apart from the D3D12 bounds checking, which does not apply to our d3d11 output.

## 2. Laptop (the laptop bench, 26100.9711)

- **Start-up probe** (`laptop-run.ps1 -Script ddraw-probe-multi-job.ps1`, run `ddprobe-multi-20261024-095459`):
  - 2.87.5 DDraw c70a0ee6: `DirectDrawCreate hr=0x00000000`.
  - The bench copy, 2.87.3 ab19386d: access violation, `exit -1073741819`, the same as before.
  - System ddraw 26100.8115: `hr=0`.
- **Copy:** `<bench>\rc-twin-dgv2875\` is a copy of the bench twin with the 2.87.5 x86 DDraw / D3DImm / D3D8 / D3D9 /
  Glide / Glide2x / Glide3x / Cpl. The 2.87.3 files are kept beside them as `*.dgv2873`. The bench `rc-twin` itself was not
  touched.
- **Conf loads:** a sentinel conf (wide-1x with `dgVoodooWatermark` / `3DfxWatermark = true` and `[DirectX] Resolution = 1280x720`)
  showed the dgVoodoo watermark. The laptop has no global `%APPDATA%\dgVoodoo` conf to fall back to. The proxy cursor map works
  with 2.87.5: `dgVoodoo ddraw.dll: 2 cursor pointer(s) taken`, `scan done (ddraw 2, glide2x 0 slots)`, the same lines as 2.87.3
  on the PC.
- **Bare boots (no preset):** t05 alive 8 of 8, menus alive 2 of 2.
- **Bench drive (`bench-run.ps1`, n 3 per row):** 3 of 9 boots drove the route. The other 6 died 4 s in at
  `winmmbase.dll+0x5AB3` (WER 1000, winmmbase 10.0.26100.9549, read of 0x8).

  | row | runs that reached the hill leg | hill median / 1 % low |
  |---|---|---|
  | ALL 2x | 1 of 3 | 49.4 / 34.5 |
  | PLAY-STABLE (tick19-42) 2x | 0 of 3 | - |
  | ALL 1x | 2 of 3 | 68.1 / 50.2, 68.6 / 51.0 |

  **These fps are on the Iris Xe, not the GTX 1650 Ti.** The GPU preference is set per exe path, and the copy's i76.exe has no
  entry (`tools\set-gpu-pref.ps1 -Exe <copy>\i76.exe -Pref 2`). Do not compare them with the queued NVIDIA rows.
- **Aspect (the owner saw a stretched picture on the laptop's screen):**
  - The panel is 1920x1080 at 100 % scaling: system DPI 96 and GetSystemMetrics 1920x1080 both with and without DPI awareness,
    read in the console session (`dpi-job.ps1`). The game window measured 1920x1080 client.
  - Boots with the preset show `aspect: D 1.778` and proportioned frames.
  - **Most boots on the laptop from 10:13 to 10:48 were my bisection boots (s.4). Those remove I76_ASPECT on purpose, so their 3D
    view is the stock 4:3 field of view stretched across 16:9.** A side-by-side of the same opening frame, with and without the
    preset, shows exactly that stretch (`captures\dgv-compat\laptop\raw-auxoff-1*` vs `raw-nopreset-1*`).
  - So no conf fix was made. If the owner saw the stretch in a run with the preset (menus or 3D), that needs a capture from him.
  - One related detail. The wide confs keep `[DirectX] Resolution = 1680x1050`, which Make-Wide-Conf takes from the 16:10 conf on
    purpose, the same as the RC's 3440x1440 conf. The cursor map then reads `aw picture aspect 1680:1050`, and the DirectDraw
    menus are drawn 4:3 inside it under stretched_ar. This is unchanged from the RC.

## 3. This PC (Windows 10 19045, not updated): the 2.87.5 twin vs the 2.87.3 control

The copy is `<lab>\dgv2875-twin-20261024`: rc-twin-20261024 with the same 2.87.5 files, the 2.87.3 ones as `*.dgv2873`.
The gate (rows 1, 3, 9) ran under the console lock through `tools\dgv-compat\gate-dgv.ps1`, with the RC gate's environment:
`LAB_CURSOR_FREE=1`, `LAB_GAME_ENV` = OWNER-2300-ALL plus `I76_MUTE=1`. The control ran right after on rc-twin-20261024 (2.87.3).

| row | 2.87.5 (`gate\20261024-101401`) | 2.87.3 control (`gate\20261024-102350`) |
|---|---|---|
| 1 conf accepted (global conf hidden) | PASS, client 3440x1440 | PASS, client 3440x1440 |
| 1 watermark probe | INFO: the capture looks the same as the control's | INFO |
| 3 trip through PLAY.bat | PASS 2 of 2, 121.7 / 122 fps | PASS 2 of 2, 121.7 / 121.7 fps |
| 9 T05 route hill leg | PASS, median 119.8 fps over 2613 m (ridge 120.1, 1 % low 81.9) | PASS, median 119.8 fps over 2613 m (ridge 120.5, 1 % low 84.1) |
| S / D saves, drift | PASS / PASS | PASS / PASS |

**I saw no difference in behaviour (n 1 gate each).** The ridge 1 % low differs by 2 fps, which is inside the same-rate spread
recorded elsewhere. An earlier attempt without the RC environment failed rows 3 and 9 on 2.87.5. That was the harness (raw
clicks, SCOTT-BUILD s.6.1), not dgVoodoo. Its run `gate\20261024-100056` is void.

## 4. The second break on the laptop: winmmbase.dll 26100.9549

- The same update wrote `SysWOW64\winmmbase.dll` 26100.9549 at 07:54:30. LAPTOP-BENCH s.4's "not winmmbase" was true only
  because DDraw crashed first.
- **Fault:** `winmmbase.dll+0x5AB3`, read of `0x00000008`, with eax, ebx, edx, esi and edi all 0. It happens at frame 0, about
  3 s after launch, during the game's CD-audio start-up (`MCI_OPEN cdaudio -> virtual`, `MCI_SET`, then the aux / MCI_STATUS
  calls).
- **Crash history** (laptop WER): +0x5b13 in 26100.8875 (July, KB5101650), +0x5473 in 8521 (27 Jul and 1 Aug), +0x5AB3 in 9549
  (today). The laptop has hit a crash in this winmmbase area under three builds.
- **What I ruled out:**
  - **Our proxy's real `auxGetNumDevs` call.** I made a lab test build: 05c4db3 plus an `I76_AUX_REAL=0` switch
    (`<lab>\tools\dgv-compat\aux-real-switch.diff`, md5 5498f96b, not installed anywhere now). The same DLL crashed 3 of
    6 boots without the switch and 2 of 6 with it. With the switch the fault moved to a later winmm call, at the same offset.
  - **The in-proxy mute:** `I76_MUTE` unset crashed 8 of 8, set crashed 5 of 8.
  - **A standalone repro:** a fresh 32-bit process calling `auxGetNumDevs` right after loading winmm returned 0 in all 75 runs,
    in session 0 and session 1 (`tools\dgv-compat\auxrepro`). July's note said the same.
- **What changes the odds:**
  - No preset: 0 of 8 crashed.
  - Full OWNER-2300-ALL: about 60 % crashed (14 of 23: bench 6 of 9, raw boots 3 of 6 and 5 of 8).
  - The bisection found no single key. Groups crashed 5 of 5 (mirror / music / misc half), 4 of 5 (MP_MENU, OBJECT_LOD,
    RENDER_INTERP, ROAD_*, SHADE_SMOOTH, SHADOW_DIST), and 2 of 5, 0 of 3, 1 of 4 for smaller groups. This looks like a race whose
    timing the proxy's start-up work shifts, not one feature.
  - With dgVoodoo's DDraw.dll parked (the system ddraw; Glide still dgVoodoo 2.87.5 and opened at 120 Hz) the full preset was
    alive 6 of 6. That is not a usable configuration: the cursor map and the menus' scaling depend on dgVoodoo's DDraw. It is
    another sign the crash is timing-sensitive.
- **This PC is Windows 10 19045.** KB5127647/8/690 are Windows 11 24H2 packages, so this PC will not take them. The tester and the
  boys' Windows 11 machines will.

## 5. For main to fold in (not done by this lane)

**dgVoodoo 2.87.5, x86** (from `<archive>\dgvoodoo\2.87.5\x`, zip sha256 5ffde6927f7355ca3fdd5d785b581256a8e6539fa13e395a891ade6ba1040850):

| file in the game folder | from | md5 |
|---|---|---|
| DDraw.dll | MS\x86 | c70a0ee641c3c349176fca39e4d78777 |
| D3DImm.dll | MS\x86 | 71b3bf5a20fb0df63fa1b20a3030234e |
| D3D8.dll | MS\x86 | e215a1eef240ba696331f38841234580 |
| D3D9.dll | MS\x86 | e9a6ec6b789cb960a2aa601e07fc95e6 |
| Glide.dll | 3Dfx\x86 | ad980c1620c8bb96d66d76b387aa2a1f |
| Glide2x.dll | 3Dfx\x86 | 3fbe9528e7ec331e647d39155670abd2 |
| Glide3x.dll | 3Dfx\x86 | 4788b491a3645dd3b576d57668e10851 |
| dgVoodooCpl.exe | root | ce248253d7df5df240dffe48e81ed181 |

- **Conf changes: none.** dccd379a and the bench's wide-1x / wide-2x / 16x10 load unchanged (s.1, s.2, gate row 1).
- **Defender:** 2.87.5 was not flagged on either machine today. 2.87.4 was, and other antivirus products may flag 2.87.5 later
  (the author's note). Packages should keep the 2.87.3 files beside the new ones as a fallback.
- **The owner's decision for the laptop and Windows 11 users:**
  - **(a)** Ship 2.87.5. It is needed on 26100.9711 whatever else happens, and it is neutral on this PC.
  - **(b)** The winmmbase crash still needs either the uninstall (`wusa /uninstall /kb:<the 26100.9711 rollup>` plus a reboot
    plus pausing updates, the July fix) or a workaround that takes the game's CD-audio path off winmm. A candidate: have the
    proxy answer `auxGetNumDevs` / `auxGetDevCapsA` and the cdaudio MCI calls without calling winmm at all at that moment. Not
    measured yet: the `I76_AUX_REAL=0` build shows the next winmm call then faults, so the whole early winmm burst would need to
    move or wait.
  - **(c)** Report to Dege (VOGONS dgVoodoo thread or GitHub issues). The DDraw part is already fixed in 2.87.4+, so only a
    thank-you or confirmation is needed there. The winmmbase part is Microsoft's: Feedback Hub, with the WER bucket
    2225974601801987840 and `winmmbase.dll+0x5AB3`.

## 6. Where things are

- Laptop:
  - `<bench>\dgv\2.87.5\` holds the probe copies.
  - `<bench>\rc-twin-dgv2875\` is the game copy. Its STRLKUP.DLL is back to fc6a5960. The test build is kept as
    `STRLKUP.DLL.5498f96b-auxswitch-test`.
  - `runs\dgv-*`, `raw-aux*`, `raw-mute*`, `raw-nopreset*`, `raw-only*`, `raw-bis*`, `raw-parkedDDraw*`.
  - The bench `rc-twin` is unchanged.
- PC:
  - `<lab>\dgv2875-twin-20261024` (the copy).
  - `captures\dgv-compat\` (gate logs, laptop results, screenshots).
  - `autotest\runs\gate\20261024-101401` and `-102350`.
- Lab scripts (<lab> commit 9fe8da6, local):
  - `laptop-bench\bench\`: ddraw-probe-multi-job.ps1, aux-probe-job.ps1, aux-repro-job.ps1, dpi-job.ps1, and raw-boot.ps1, which
    gained `-Preset`, `-ExtraEnv`, a window-rect read-out and a screenshot.
  - `tools\dgv-compat\`: gate-dgv.ps1, bisect-keys.ps1, only-keys.ps1, dis-ret.py, auxrepro, aux-real-switch.diff.
- One bench run (`raw-onlyMiscB-4`) lost its job process after launch and left its own i76.exe running, which I stopped (pid
  17772, path in my copy). The next run was refused because of it. Both are counted as void.

## 7. The winmmbase crash: cause and the proxy fix (winmm-race lane, 2026-10-24)

**Cause (measured, laptop, `I76_WINMM_TRACE=1`).** This is not a timing race inside winmmbase. The cause is Windows' own
compatibility shim for i76.exe (AcGenral.DLL, which the same update also took to 26100.9549).

- The shim replaces kernel32's Global* and Local* memory functions with its own heap. Every one of them comes back from
  GetProcAddress as an AcGenral.DLL address (GlobalAlloc is AcGenral.DLL+0x72C40).
- Since this update, the shim reaches the system modules' GlobalAlloc / GlobalFree import slots (api-ms-win-core-heap-l2). It does
  not reach their GlobalLock / ReAlloc / Unlock / Size slots (api-ms-win-core-heap-obsolete-l1), which stay KERNELBASE's.
- The census found this split in nearly every module:
  - loaded at start-up: winmmbase, USER32, ole32, combase, gdi32full, SHELL32, SHLWAPI, urlmon, windows.storage, MSACM32;
  - loaded later: msacm32.drv, midimap, mfplat, WMVCore, MSCTF, Oleacc, CRYPT32.
- winmmbase builds its driver table with GlobalAlloc(GMEM_MOVEABLE), which goes to the shim and returns a plain heap pointer. It then
  calls GlobalLock, which goes to KERNELBASE.
  - KERNELBASE reads any value with bit 2 set as a moveable handle. It finds no such handle (err 6) and returns NULL. winmmbase then
    reads [NULL+8] at +0x5AB3.
  - The trace log shows both cases. Crashing boots: `test GlobalAlloc(0x42, 16) = 00A95156, GlobalLock = 00000000 (err 6)`. Surviving
    boots: bit 2 clear (`00B13B42 -> 00B13B42`).
  - Whether bit 2 is set depends on where the heap stands at that moment. That explains the ~50 % rate, and why the preset's
    allocations change the odds (no preset: 0 of 8).
- The same split also broke the mp3 player. All 3 laptop drives that survived without the fix logged `open ... type mpegvideo` FAIL
  266 (MCIERR_CANNOT_LOAD_DRIVER). Music never played on 26100.9711.

**Fix: `I76_WINMM_HEAPFIX` in the proxy** (music-fix/winmmrace.c; default auto, `=0` turns it off). Every module with a split set
gets the shim's own function in its system slots, so each module uses one allocator again: the shim's, as the shim intends.

- What it changes: only slots that are still the system's, only in modules that already have a slot pointing into the layer, and only
  for functions the layer hooks.
- When it runs:
  - From DllMain.
  - Then a thread preloads the audio / MCI modules that winmm would otherwise load inside the game's first calls: wdmaud.drv,
    msacm32.drv, midimap, mciqtz32, quartz, mfplat, WMVCore, MMDevAPI, AudioSes, dsound. It sweeps them for 500 ms, then releases the
    proxy's first real winmm call.
  - Then every 50 ms for 30 s, every 1 s up to 2 min, then every 5 s.
  - Also before the proxy's real winmm calls, at most once per 100 ms.
- Safety: each module is pinned while it is walked, and the import walk is bounds-checked.
- **No split means no change.** On this PC (Windows 10 19045) the log reads `winmm-heapfix: not needed so far (DllMain: no module with
  a split Global* set)` in 4 of 4 sessions.

The attempts in order. All boots use the owner preset.

| build | what it did | boots | crashes |
|---|---|---|---|
| no fix (fc6a5960; `=0`; and the builds below where it did not take) | - | 59 | 28, all winmmbase+0x5AB3 |
| c3ca61b / f10aa9b | winmmbase's six slots -> KERNELBASE, resolved through GetProcAddress | 40 | 16. The shim hooks GetProcAddress too, so this wrote the shim's own pointer back |
| 6d54ad5 | the same, with KERNELBASE resolved from its export table | 5 | 1, in the mute thread's COM object. The shim re-patches GlobalAlloc after DllMain, and the mixed window corrupts the heap. Dropped |
| e285a9f | winmmbase's four uncaught slots -> the shim's functions | 40 | 3, none in winmmbase: DSOUND, wdmaud.drv, the AcGenral heap |
| 7861e96 / 730d455 | every split module; then the Local* set too | 20 / 20 | 2 (AcGenral) / 4 (wdmaud x2, AcGenral, the sweep's own walk). Modules loaded inside a winmm call were used before the sweep reached them |
| 0e2d1b1 | + preload of the audio / MCI modules | 20 | 1, the sweep's own walk (a module unloaded while it was being walked) |
| 3c86f14 | + pin each module while walking it | 25 | **0** |
| **709466d = main 3ef108d, Strlkup.dll 53944fb2** | + the preload sweep repeats for 500 ms | table below | **0** |

**Result, final build.** Proxy md5 `53944fb2f1f39c7bda31868b4922d3a6`, built from main 3ef108d with build.ps1 -Ref. It is
byte-identical to the 709466d build that was tested.

| configuration (laptop, 26100.9711, dgVoodoo 2.87.5) | n | winmmbase crashes | any crash |
|---|---|---|---|
| RC twin copy (`<bench>\wmr-twin`), OWNER-2300-ALL at 1080p, t05, in-proxy mute on | 20 | 0 | 0 |
| the same with `I76_MUTE` unset (the pid watcher still mutes) | 20 | 0 | 0 |
| the same, no preset | 8 | 0 | 0 |
| The tester's setup through **PLAY-T05.bat** (PLAY.bat's stable preset, straight into t05) | 10 | 0 | 0 |
| The tester's setup through **PLAY-PREVIEW-T05.bat** (the preview preset) | 10 | 0 | 0 |
| control: The tester's setup with its shipped proxy 6208d3ad, PLAY-T05 | 6 | 0 | 0 |

The tester's setup is pristine GOG 2.1.0.17 (exe 9a232dcc) + zip tester-20261023b + dgVoodoo 2.87.5.

**The tester's configuration did not crash without the fix either** (0 of 6). GOG's exe imports no winmm; its CD audio goes through GOG's
win32.dll.
- The split is still present there. In every the tester boot the fix changed slots in 11 modules at DllMain, with no ill effect.
- The only CRASH lines in the the tester boots are the documented frame-0 PIT probe at i76.exe+0x99997, which the game handles (20 of 20).
  WER logged 0 application errors over those batches.

**Music, checked in the log (the game is muted).**
- In missions (t05 held 75 s), 4 of 4 boots logged `MCI_PLAY ... run 6..14`, `str ok: open ...6.mp3 type mpegvideo`,
  `str ok: play i76cd` and `PLAY track 6`. Before the fix this was 0 of 3, because the open failed with 266.
- Every boot reads the disc's track list (17 real mpegvideo opens) without error.
- **Menu music was not observed.** The one menus boot (90 s) was still in the intro movie.

**This PC (Windows 10 19045): gate rows 1, 3, 9** on `dgv2875-twin-20261024` with 53944fb2, run `autotest\runs\gate\20261024-175400`.
**PASS 8, FAIL 0.**
- Row 3: 121.3 / 122 fps.
- Row 9: hill median 117.4 fps over 2606 m (ridge 120.7, 1 % low 77.8). The s.3 2.87.5 control read 119.8 (ridge 120.1, 1 % low
  81.9), n 1 each. That is inside the 10 % gate, and the fix is inactive on this PC by its own log.
- The twin's proxy was put back to fc6a5960.

**Where things are.**
- Lab:
  - Bench scripts: `laptop-bench\bench\wmr-batch.ps1`, `wmr-tester.ps1`, `itask-lane.ps1` (its own task name, so lanes no longer
    replace each other's `i76bench` task) and `raw-boot.ps1 -RunsDir`.
  - PC-side runners: `laptop-bench\wmr-run.sh` and `wmr-tester-run.sh`.
  - `tools\winmm-race\`: wdis.py and the laptop's winmmbase / dsound / AcGenral 9549.
  - `captures\winmm-race\`: the per-boot proxy logs of every batch.
  - `builds\nitro-port-20261021\wmr-*`.
- Laptop:
  - `<bench>\wmr-twin`: this lane's copy of rc-twin-dgv2875.
  - `<bench>\tester-gog\game`: The tester's setup done, at 1920x1080.
  - `<bench>\wmr\*.dll` and `runs\wmr\`.

**Incident.** The first the tester batch started the .bat with its output piped, so it waited on the game and held the laptop lock from
12:48 to 17:50. I stopped only my own processes: the game, its PLAY-i76.ps1, and AutoHotkey and i76wheel from that folder.
`wmr-tester.ps1` now starts the .bat with Start-Process.
