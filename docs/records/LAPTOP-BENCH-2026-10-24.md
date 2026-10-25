# Laptop bench, 2026-10-24

The owner asked to move headless tests to the laptop as a second bench, because it has less graphics power and a different
monitor. The bench is set up, and the launch from this PC into the laptop's interactive session works with no password.
**The game cannot start there today.** dgVoodoo 2.87.3's DirectDraw crashes on that machine since this morning's Windows
cumulative update. I measured no fps. The owner must decide about the update (s.5).

## 1. The machine and what is on it

- the laptop bench, LAN <LAN-IP> (Tailscale <tailscale-ip>). i7-1165G7, 16 GB, GTX 1650 Ti Max-Q (driver 27.21.14.5191) plus
  Iris Xe (27.20.100.8729, which drives the panel). Panel 1920x1080, Windows 26100.9711. Python 3.11.9 is installed.
- The console user is **<user>**, in session 1, with the desktop unlocked. The ssh login is the same account, so an `/IT`
  scheduled task created over ssh runs in that desktop with no password (probe: `session 1 user <user> screen 1920x1080`). The
  other Claude session on the laptop also runs as <user> in session 1. Its files and processes were not touched.
- `<bench>\` (486 MB):
  - `rc-twin\` is the RC test twin `rc-twin-20261024`, minus logs, `STRLKUP.DLL.*` backups, `_rollback`, `_superseded*` and
    `.pre-*`. STRLKUP.DLL is fc6a5960 and i76.exe is 6319abf7, both checked against the PC.
  - `bench-run.ps1`, `raw-boot.ps1`, `itask.ps1`, `setup-bench.ps1`, `swap-dll.ps1`, `ddraw-probe-job.ps1`.
  - `tools\` holds mute-proc / unmute-persisted / start-mute-watch, focuslib, Make-Wide-Conf plus the dccd379a template,
    `rc-draw\` (rcd_tab.py, t05-route.json, rcd_drive_bench.py), set-gpu-pref, ddraw-probe, d3d11-probe and mk-conf-variants.
  - `runs\` holds the run outputs, and `.fps-lock` is the laptop's own lock while a run is up.
- The sources live in the lab at `<lab>\laptop-bench\` (`bench\` is what gets deployed, and `laptop-run.ps1` is the PC side).

## 2. How to run a test from the PC (one command)

```
powershell -File <lab>\laptop-bench\laptop-run.ps1 [-ArgLine "-Preset OWNER-2300-ALL -Conf wide2x -Tag all-2x"] [-Sync] [-SyncDll] [-Fetch]
```

- The script uses ssh with the PC's key and falls back to Tailscale. `itask.ps1` on the laptop checks three things: the
  console user is the ssh user, the desktop is unlocked (no LogonUI), and the job file `job.ps1` is written. It then
  (re)creates the task `i76bench` (`schtasks /create /ru <user> /it`), runs it, waits for the run's `.done` file and prints its
  `.result.txt`. Arguments travel as base64, which avoids quoting problems through ssh.
- `bench-run.ps1` does the same measurement as the lab's gate row 9 (`autotest\t05-route-fps.ps1`). It boots directly into
  t05.msn through the folder's own `PLAY-i76.ps1 -Preset <x>` and drives the owner's T05 route: 15 s ridge, then
  `I76_START_POS` and the 2.6 km hill leg. fps comes from `I76_FRAME_LOG` through `rcd_tab.py`. It also reports:
  - the dgVoodoo Resolution lines it ran with;
  - one proxy log line per preset key, plus the keys that have no line;
  - the CRASH line count and the UNEXPECTED / NOT-patched lines;
  - Windows error events (WER) for i76.exe since launch;
  - the GPU in use (nvidia-smi plus the GPU-engine counters).
- `-Conf wide2x` gives 1080p with 2x supersampling (`[Glide] 3840x2160`). `wide1x` is the the tester launcher's
  `-NoSupersample` (`1920x1080`). `16x10` is the folder's own 16:10 conf. `setup-bench.ps1` wrote the two wide confs with
  `tools\Make-Wide-Conf.ps1 -Width 1920 -Height 1080 -Scale 2|1` (the template's bytes are kept apart from the Resolution
  digits). It also set `I76_ASPECT = '1920x1080'` and `I76_U32X_MENU_ASPECT = '1920:1080'` in OWNER-2300-ALL and tick19-42 on
  the bench copy only. `dgVoodoo.wide.conf` is now the 2x fit, and the RC's 3440x1440 conf is kept as `dgVoodoo.wide.conf.rc-3440`.
- Other entry points:
  - `-Script raw-boot.ps1 -ArgLine "-Tag x [-Mission t05] [-Conf ...]"` is a bare boot (no launcher, no preset) that reports
    alive or crash.
  - `-Script ddraw-probe-job.ps1 -ArgLine ""` is a 2 s check of dgVoodoo's `DirectDrawCreate` against the system ddraw.
  - `-SyncDll` installs `music-fix\Strlkup.dll` (or `-Dll <path>`) into the bench twin and reads back the md5. It was checked
    with the identical fc6a5960, so the build did not change. Use it when the fixed proxy lands.
- Safety:
  - Audio is muted with `I76_MUTE=1` plus the per-pid mute watcher.
  - The display is held awake by a nudge plus ES_DISPLAY_REQUIRED inside the run.
  - A run refuses to start if any i76 process is up, and it stops only the i76.exe it started.
  - The key sender `rcd_drive_bench.py` is p19's scan-code sender plus one guard: a key-down goes out only while the game
    window is in the foreground. Otherwise the keys are released and the blocked sends are counted, so W/A/D can never type
    into the other session's terminal.
- GPU: `HKCU\Software\Microsoft\DirectX\UserGpuPreferences` has the bench i76.exe set to `GpuPreference=2;` (the NVIDIA),
  read back. This works because the ssh user is the console user. To change it, use `tools\set-gpu-pref.ps1 -Pref 2|1|0|remove`.

## 3. What works headless

| piece | status |
|---|---|
| ssh to the laptop, scp, copying the twin, md5 check | works |
| launching into the console session (`/IT` task, no password) | works: session 1, the 1920x1080 screen is visible to the task |
| display fit to 1080p (2x / 1x confs, preset aspect keys) | written and read back. The proxy read `aspect: D 1.778, fov 90 -> 106.3 deg` in every run |
| preset keys reaching the proxy | ALL preset: every key has a log line except I76_U32X_MENU_ASPECT and I76_U32X_SHELL_STRETCH (u32x keys, not logged by the proxy) |
| the game reaching a mission and driving | **no**: it crashes about 3 s after launch, before the first frame (s.4) |

## 4. First results: a crash at launch, not winmmbase

Following the owner's note, I checked winmmbase.dll first. **It is not the faulting module.** SysWOW64 winmmbase.dll is
26100.9549 and appears in none of today's crashes.

All 11 boots (the table below plus the wrapper check) faulted at **`DDRAW.dll+0x4AB0A`**, a read of address 0. DDRAW.dll here is dgVoodoo 2.87.3 DirectDraw (ab19386d,
the same file as on the PC). The fault comes right after `glide-refresh: grSstWinOpen`, at `frame 0 state 5`. The boots, n = 1 each:

| boot | result |
|---|---|
| ALL, 1080p 2x (`3840x2160`) | crash after 6 s, 4 CRASH lines, WER 1000 |
| ALL, 1080p 1x | same |
| ALL, 1x, GPU preference Intel | same |
| stock preset, the folder's 16:10 conf | same |
| bare boot to the menus, 16:10 | same |
| bare boot into t05, 16:10 | same |
| conf variants `OutputAPI = d3d11warp`, `Adapters = 1`, `d3d11_fl11_0` | same. In the WARP boot `edx` changed from 0x47 to 0x30, so the conf is being read |
| **a copy** of the laptop's own install `C:\Games\Interstate 76` (AiO exe 60abf7bc, the same dgVoodoo DLLs) | same. That install still worked in July and August: its last crashes, on 08-01, were in I7_SFRCE / winmmbase, both later in the game |
| bench twin with dgVoodoo's DDraw.dll parked (diagnostic only, put back, md5 checked) | **alive** after 40 s, but "Running software emulation mode" (no Glide) |

The crash happens outside the game too:
- `tools\ddraw-probe.ps1` in 32-bit PowerShell calls dgVoodoo's `DirectDrawCreate(NULL)`. On the laptop that call raises an
  **access violation** in session 1 and in session 0 (WER: DDraw.dll+0x44354).
- The system `SysWOW64\ddraw.dll` returns `hr=0`.
- On this PC (Windows 10 19045) the same dgVoodoo DLL returns `hr=0`.
- 32-bit DXGI and D3D11 work on the laptop (`d3d11-probe.ps1`: factory OK, 2 or 3 adapters, D3D11CreateDevice at level 11_0).

So the break is between dgVoodoo 2.87.3's DirectDraw initialisation and the laptop's Windows. It does not depend on the
preset, the conf, the GPU or the launch method.

What changed: the 2026-10-24 cumulative update. Its rollup is `Package_for_RollupFix ... 26100.9711.1.30`, with servicing stack
9703. Get-HotFix lists **KB5127647, KB5127648 and KB5127690** as installed today. The update rewrote 1326 SysWOW64 files at
07:54, including dxgi / d3d11 / d3d10warp / user32 / gdi32full / win32u / ntdll / KernelBase (26100.9711). This is the same
pattern as KB5101650 in July (FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md), which broke i76 at boot and was fixed by uninstalling
the update. This time the module is dgVoodoo's DirectDraw rather than winmmbase.

No fps numbers exist yet. The ALL vs PLAY-STABLE comparison and the 2x vs 1x comparison wait on s.5.

## 5. What the owner must do

1. **Decide about the update.** A lane does not uninstall a Windows update or reboot the laptop, because the other session is
   working there. The July fix was `wusa /uninstall /kb:5101650` plus a reboot plus pausing updates. Here, uninstall the KB that
   carries 26100.9711: Settings > Windows Update > Update history > Uninstall updates. The owner named KB5127648, and the other
   two from today are KB5127647 and KB5127690. Then reboot and pause updates. After that, `laptop-run.ps1 -Script
   ddraw-probe-job.ps1 -ArgLine ""` must print `hr=0x00000000` for the bench DDraw.dll before any fps row counts.
   - The alternative is a newer dgVoodoo build, if one exists that copes with 26100.9711. That needs a download and a re-gate of
     the conf (`DGVOODOO-CONF-REJECTED.md`), so it is the owner's call.
2. Keep the laptop logged in as <user> with the desktop unlocked and on mains power. A locked console stops `itask.ps1` with a message.
3. Then run the queued rows, three runs each because the same-rate control spread is unknown on this machine:
   - `-ArgLine "-Preset OWNER-2300-ALL -Conf wide2x -Tag all-2x"`
   - `"-Preset tick19-42 -Conf wide2x -Tag stable-2x"`
   - `"-Preset OWNER-2300-ALL -Conf wide1x -Tag all-1x"`
   - add `-SyncDll` once the fixed proxy lands.
   For reference, this PC (GTX 1080 Ti, 3440x1440 2x) read a hill leg median of 120.0 fps with a 1 % low of 96.9 for the ALL set
   (TESTER-BUILD-2026-10-23 row 9).
