# Emulated 1997 PC: measuring what "stock" really was (plan, 2026-10-14)

[WHAT-IS-STOCK.md](WHAT-IS-STOCK.md) ends on two numbers that no source pins down:

- **The Windows 95 `GetTickCount` step.** "55 ms" is second-hand only.
- **I'76's real frame rate on its target box.** Release spec: P90 minimum, 32 MB recommended, software renderer
  only. The 3dfx Glide path came later, with the patches and Gold.

Every lab profile that claims to be "1997" (`I76_TICK_MS`, `I76_FPS_CAP`, the R-1997 rows, the W95-18 pilot) rests on
those two numbers. This plan measures them on an emulated box-spec PC instead of inferring them.

Everything is set up in the lab: `../<lab>/emu/` (README.md there is the owner's install guide and the
technical reference). The Windows 95 install is the only step that waits on the owner.

## Setup (ready)

| part | choice | why |
|---|---|---|
| emulator | 86Box v6.0 build 9001 (2026-05-31), sha256 checked against GitHub's digest; ROM set tag v6.0 | cycle-timed PC emulator with a Voodoo 1 model |
| board | ASUS P/I-P55T2P4, Intel 430HX, Award 4.51PG | 1996 Socket 7; takes the CPUs at their real bus speeds |
| CPU | Pentium 166 (66 MHz x 2.5); Pentium 90 (60 x 1.5) | the P166 is the reference machine; the P90 is the min spec |
| RAM | 32 MB | recommended spec (a 16 MB P90 run is a one-line edit) |
| 2D | S3 Trio64 PCI 2 MB | commonest 1996 card |
| 3D | 3Dfx Voodoo Graphics, 2 + 2 MB | Monster 3D class |
| sound, disk, CD | SB16; 2 GB IDE (one FAT16 partition); 8x ATAPI | period parts |
| OS | Windows 95 (OSR2 preferred); optional Windows 98 VM on the same hardware | the clock question is per OS |
| game, software runs | the original CD, `I76_CD1.ISO` (archive.org; `I76.EXE` 1997-03-15), with its own DirectX 3 and drivers | the March 1997 release itself |
| game, Glide runs | the 1998 Gold exe from the GOG installer, minus GOG's wrappers, with `WIN32.dll` patched back to `WINMM.dll` in the CD copy | the GOG exe as shipped cannot load on Windows 95 (its winmm wrapper needs MSVCR90) |

All variants POST in 86Box at 100% speed: the right CPU MHz, 32768K, the disk and the CD detected. 86Box loaded the
config and saved it back unchanged.

**Correction to the brief: the CPU recompiler stays ON.** The brief assumed a cycle-accurate run means the dynamic
recompiler off. For a Pentium in 86Box it is the reverse:

- The Pentium timing model (U/V pairing, AGI stalls) exists only in the recompiler, so 86Box marks P54C CPUs
  "requires dynarec".
- The interpreter would use flat per-instruction-class costs.

## The two instruments (built and self-tested, no game involved)

Both are tiny C programs without a C runtime. The build proves they can load on Windows 95:

- PE header 4.00
- every import a Windows 95 KERNEL32 / USER32 / WINMM export (`emu/tools/pe-imports.py --strict`)
- no instruction a P54C lacks

They reach the VM on a tools CD (`EMUTOOLS.ISO`).

- **TICKPRB.EXE** busy-polls `GetTickCount` and `timeGetTime` against QueryPerformanceCounter for 30 s. It
  histograms every clock step by size and by true length, in five phases:
  - baseline (as I'76 runs: the retail exe never calls `timeBeginPeriod`)
  - `Sleep(1)` / `Sleep(0)` cost
  - with `timeBeginPeriod(1)`
  - `Sleep` again under that period
  - after `timeEndPeriod`

  It also logs the CPU clock (RDTSC against QPC), which checks that the VM runs at the configured MHz. On this Windows
  10 PC it reads 15.6 ms `GetTickCount` steps, as expected.
- **I76FPS.EXE** attaches read-only to the running game and samples the engine's own frame counter. It uses
  Toolhelp32, `OpenProcess` and `ReadProcessMemory`: no injection, no proxy. It finds the counter by the shape of the
  engine's frame-clock function, "increment a global, then call `GetTickCount`", and checks that the import slot
  really is `GetTickCount`:

  | build | function | frame counter |
  |---|---|---|
  | retail 1.0 | `0x450FA0` | **`0x55F744`** (new, static) |
  | GOG Gold | `0x49C920` | `0x5A7E1C` (ENGINE-LOOP-MAP) |

  Self-test against a stand-in process with both code shapes at 50 frames/s: it read 49.9 to 50.0 fps.

**Why not our proxy's `I76_FPS_LOG`.** Static check of `music-fix/Strlkup.dll`:

- PE subsystem 6.00, which the Windows 95 loader refuses.
- VS2019 CRT imports Windows 95 lacks: IsProcessorFeaturePresent, InitializeSListHead,
  InitializeCriticalSectionAndSpinCount, GetModuleHandleExW, Get/SetFilePointerEx, DecodePointer.
- XP-era calls of its own: AddVectoredExceptionHandler, OpenThread, GetModuleHandleExA.

More decisively, **the 1997 retail exe does not import Strlkup.dll at all** (its imports: KERNEL32, USER32, GDI32,
WINMM `timeGetTime`, DSOUND, DDRAW, smackw32, anetdll), and the proxy's patches are tied to Gold addresses. An
external sampler measures the frame rate without changing the game; the proxy cannot get into the 1997 game at all.

## What the owner must provide

In `../<lab>/emu/images/`:

1. `WIN95.ISO`, the Windows 95 CD (OSR2 4.00.950B preferred; RTM / OSR1 work), and its CD key.
2. `W95BOOT.IMG`, a Windows 95 boot floppy with CD-ROM support. Needed only if the CD is not bootable.
3. Optional: `WIN98.ISO` (+ boot floppy) for the Windows 98 clock comparison.

Nothing licensed is downloaded by us, and nothing licensed is committed (`emu/.gitignore`).

**The Voodoo driver is done (2026-10-14).** `emu/images/VOODOO.ISO` holds 3dfx's own free reference drivers,
fetched from Wayback captures of www.3dfx.com/software/ (1998-04-22):

- the **Glide 2.43 Runtime** (`grtvgr.exe`, posted 10/24/97; `glide2x.dll` 1997-10-08, md5 `1dcb1619...`, plus
  `fxmemmap.vxd`);
- the **Voodoo Graphics Direct3D 2.15** package (`d3rtvg.exe`, 1998-03-03, with `VOODOO.INF`).

All 39 `glide2x.dll` functions that the Gold `ZGLIDE.DLL` imports are exported by Glide 2.43 (static check). The D3D
package also carries a 1997 `MSVCRT.DLL`, a fallback if the Gold exe finds none on Windows 95.

Source URLs, hashes and the file list are in `emu/README.md`, "The Voodoo driver CD".

## Measurement design

Conventions for every condition:

- n = 3 runs (the same-rate-control rule): the spread between repeats is measured before any difference is believed.
- 60 s of measurement after a 10 s settle.
- Log names carry `<cpu>-<renderer>-<scene>-<n>`.
- The game's own video mode and detail defaults on each machine are recorded. A first run uses those defaults
  (what a 1997 owner got); a second set uses fixed settings.

| # | measure | where | answers |
|---|---|---|---|
| 1 | TICKPRB, 30 s | p166 (Windows 95) | the Windows 95 `GetTickCount` step and its true length; whether `timeBeginPeriod(1)` changes it; real `Sleep(1)` |
| 2 | I76FPS, software renderer, retail 1.0 exe | p166 | the March 1997 frame rate, in Instant Melee (quick menu path), T04 race, T13 combat, T05 canyon jump |
| 3 | I76FPS, Glide, Gold exe + Voodoo | p166 | the later Voodoo frame rate. 86Box does not time the Voodoo's fill rate, so Glide numbers are not a reference |
| 4 | controls | p166, one scene | I76FPS period 250 vs 1000 ms (sampler overhead) |

**Getting to T04 / T13 / T05 without the proxy's direct boot.** The plan is campaign bookmarks:

- Play to each mission once in the VM (on p166), save, and reuse the save for every run.
- The lab's Gold saves can go in on the tools CD (`make-cds.py tools --saves <dir>`). Whether retail 1.0 reads Gold
  saves is untested.
- The 1997 `GAMEKEY.MAP` lists a `TOGGLE_FRAMERATE` (Alt+F) debug key, but marks that block "Don't function in release
  build". Pressing it once in the VM costs nothing; I76FPS does not depend on it.

## How the results feed the lab

- **Tick.** TICKPRB's step on Windows 95 replaces the assumed 55 ms. The lab's `I76_TICK_MS` and the R-1997 rows in
  WHAT-IS-STOCK then use the measured value. If it is about 55 ms, the R-1997a/b findings stand and the question
  becomes which fps went with it. If it is finer, the 55 ms profiles drop to a sensitivity test, as WHAT-IS-STOCK
  already recommends.
- **Frame rate.** I76FPS's P166 software numbers become the "1997 box" fps. They set `I76_FPS_CAP` for the box-spec
  profiles.
- **W95-18.** Another agent is running the W95-18 pilot. Its doc,
  `../<lab>/docs/W95-18-BASELINE-2026-10-14.md`, did not exist when this plan was written. Once it does,
  read its tick and fps assumptions and set the measured values against them, as a proposal in this doc or in the
  results; never edit that doc. The same applies to the `I76_FRAME_LOG` box-spec work referenced in `strlkproxy.c`
  (lab `docs/BOX-SPEC-BASELINE-2026-10-14.md`, also not yet written).
- Results go to `../<lab>/emu/results/` (raw logs, copied out of the disk image with `emu/tools/fat.py`).
  The summary goes here and into WHAT-IS-STOCK.

## Known limits

- The Voodoo fill rate is not modelled (see #3).
- The archive.org rip has no CD-audio tracks, so there is no in-mission music. Red Book playback costs the CPU about
  nothing.
- The retail frame-counter address is static analysis until the first in-mission I76FPS run shows it advancing. In
  the menus it must stand still.
- Two Gold-exe imports (IMM32.DLL, MSVCRT.DLL) are verified only by running the exe on Windows 95. The fallback is
  the Windows 98 VM.
- It is still an emulator: 86Box times the CPU per instruction with a pairing model, not the real Pentium pipeline
  and caches. For that reason, agreement with the few period reports is part of reading the numbers.

## Run attempt, 2026-10-14 evening: Windows 95 install blocked at the Product ID

**Result: nothing measured yet.** There is no tick figure and no fps figure. The plan's numbers are still open, and
WHAT-IS-STOCK is unchanged.

- **The owner's CD.** `WIN95.ISO` is Windows 95 **RTM 4.00.950, OEM**: files dated 1995-07-11, `SETUPPP.INF`
  ProductType=9, the OEM ("PC Manufacturer") EULA. It is not bootable.
- **What setup asks for.** The 20-digit Certificate of Authenticity number, `xxxxx-OEM-xxxxxxx-xxxxx`.
- **The supplied keys do not fit.** All six keys supplied are 25-character `xxxxx-xxxxx-xxxxx-xxxxx-xxxxx` keys, the
  XP-and-later format, and setup rejects every one.
  - The input was checked: the field shows the typed characters, cut off at 23.
  - No generic or published key was tried.
- **Next step: the owner's COA number** from the Windows 95 sticker or CD sleeve. A retail Windows 95 CD with its
  `xxx-xxxxxxx` key would also do, as would an OSR2 OEM CD with its COA.
- **Update, later the same evening.** The owner then supplied three OEM-format numbers (COA-1 to COA-3). They
  were tried in order, and setup rejected all three with the same "Invalid Product Identification Number" dialog.
  A screenshot confirmed the typing. The VM is paused on the page again.

**Everything up to that page runs unattended, and the VM is kept paused there.** Details are in lab `emu/README.md`,
"Status":

- **Boot floppy.** The CD is not bootable and has no DOS CD-ROM driver, so the floppy is built on the host from the
  CD's own files: `IO.SYS` (WINBOOT.SYS), `COMMAND.COM`, `FDISK`, `FORMAT`, and the boot sector from the CD's
  `FORMAT.COM`.
- **Setup files.** They reach DOS on a second, untranslated 100 MiB IDE disk (`emu-data.img`, built by
  `tools/mkfat.py`), together with an `MSBATCH.INF`.
- **Install stages so far:** `FDISK 1 /PRI`, then `FORMAT C: /AUTOTEST` (1,998.25 MB), then `SETUP ... MSBATCH.INF /IS`.
  This reached the setup wizard with no manual steps except the BIOS (boot order `A,CDROM,C`, CMOS saved) and the EULA.
- **Host-side driving.**
  - Screenshots come from 86Box's own screenshot button, through UI Automation (no input, no focus change).
  - Keys are scan codes through SendInput, gated on the console lock.
  - About 15 minutes of console time were used in two lock stretches.

**For W95-18: no change recommended yet.** Its 55 ms / 18.2 fps assumption is neither confirmed nor contradicted until
the VM runs.

## Run, night of 2026-10-14 / 15: Windows 95 installed, clock and frame rates measured

Details, every log and the per-run numbers are in lab `emu/results/RESULTS.md` (raw logs: `emu/results/20261014-night/`).

**The install.** The owner put five more images on his Mac. Only one installed:

- **Installed:** the **Packard Bell master CD** (Windows 95 RTM 4.00.950, 1995-09-19). Its `SETUPPP.INF` carries a
  preset product ID, so setup asks for no key.
- **Rejected:** the RTM OEM CD and an OSR2 (950B) OEM CD. Every owner COA number was rejected, and so were the
  per-build keys.
- **Rejected:** a Greek Windows 98 first edition. Its owner key was rejected.
- **Not installable:** a Japanese PC-9800 Windows 95.
- At the owner's request, the failed images are being deleted.
- The installed disk was snapshotted in three states: clean; with DirectX 3 and the retail game; with Gold and Glide 2.43.

**1. The Windows 95 clock (TICKPRB, n = 3 on each of P90 and P166):**

- **GetTickCount advances in 1 ms steps, not 55 ms.** That held in every phase (no `timeBeginPeriod`, under it, after
  it) and on both CPUs. Each step's true length is 0.999 ms against QueryPerformanceCounter.
- What is coarse is the scheduler. `Sleep(1)` lasts about 12.5-13 ms (max 13.9) without a period, and 1 ms with
  `timeBeginPeriod(1)`.
- So the "55 ms" of the old MSDN table does not describe Windows 95 RTM's GetTickCount on this emulated board.
- This is an emulator result. A real 1997 board would confirm it.

**2. Frame rates (Gold exe; Instant Melee, The Crater, 1 AI; 60 s starting 10 s into the mission; n = 3 unless noted):**

| machine | Glide (Voodoo Graphics) | software renderer |
|---|---|---|
| P90 | 16.7 fps (15.9-17.3) | 7.1 fps (n=2) |
| P166 | 31.7 fps (29.9-32.8) | 13.3 fps (n=1) |

- Both paths scale with the CPU clock. The Glide numbers are still not a reference (owner's ruling, 2026-10-15):
  86Box does not time the Voodoo fill rate.
- **Retail 1.0** (CD 1, 1997-03-15) installs and starts on Windows 95 RTM + DirectX 3, but only with 86Box's classic
  PIT. Under the default PIT its CPU-speed probe (`0x44E063`) reads 0 ticks and dies of a divide error at `0x44E0C1`,
  which is an emulator artefact.
- Every retail game mode asks for **disc 2** (volume label `I76_CD2`). With the owner's ripped disc 2 it plays
  missions; it is now the reference exe (EMU-MEMTRACE.md: P166 low detail, T04 35.7 / T05 33.4 / T13 31.3 fps).
- **The Gold exe** needs a `MSVCRT.DLL` on Windows 95 RTM. 3dfx's period copy from VOODOO.ISO fixes that; IMM32 did
  not complain.

**Measured route to these numbers:**

- 86Box mouse capture with relative SendInput moves (2 counts per guest pixel in the I'76 menus).
- The retail exe's frame counter `0x55F744` was confirmed live by I76FPS: it stands still in the menus.
- The Gold counter is `0x5A7E1C`.

**For W95-18 (proposal; the W95-18 doc is not edited):** see the recommendation in this run's report and lab
`emu/results/RESULTS.md`. In short:

- The 55 ms tick is not what this Windows 95 does. A 1 ms tick (or this PC's 15.6 ms) is the measured case.
- The box-spec frame rate on the P166 is ~32 fps with the Voodoo, but only ~13 fps in software.
- 18.2 fps sits between the two renderer paths.

## Headless parallel runs, 2026-10-15: no host input, no console lock

The 86Box VMs can now run whole sessions with no host keyboard, mouse or focus, several at once. Details, commands
and every run are in lab `emu/README.md` ("Headless parallel runs") and `emu/results/par/`. Code: lab
`emu/probe/i76drv.c`, `emu/tools/par/`.

**Why.** Until now, input reached the guest through host SendInput. 86Box reads raw input, so its window had to be in
front, which took over the console (hence the console lock).

**How.**

- **Input inside the guest.** I76DRV.EXE is a Windows 95 input player (no CRT, PE 4.00, imports checked against the
  real Win95 RTM KERNEL32 / USER32). WIN.INI `run=` starts it. It plays a text script of waits, program starts, window
  and process waits, keys (keybd_event with real scan codes), clicks (mouse_event) and the final shutdown, and logs to
  `D:` and COM1.
- **The host runner.** `parrun.py` gives each run a plain copy of a par base disk (the Gold snapshot with the WIN.INI
  hook and the low-detail `I76PLYR.DEF` patched in; the snapshots are only read), a fresh data disk and its own cfg.
- **Out of sight.** 86Box starts on a private desktop that is never shown, so it can never take the foreground.
- **Live readings.** COM1 comes back over a named pipe, carrying the guest log and a GetTickCount heartbeat. The
  runner also takes PrintWindow screenshots.
- **Shutdown and collection.** The runner waits for the guest to shut down, closes 86Box with WM_CLOSE and copies the
  logs out with `fat.py`.

**The game's input path.** Neither the retail 1.0 exe nor the Gold exe uses DirectInput (no DINPUT import or string).
Both read the keyboard from window messages and `GetAsyncKeyState`, and their key tokens follow scan-code order. In
the VM:

- keypad 8 (the stock `UpArrow` throttle, not extended) drives the car;
- the grey left arrow (extended) glances;
- every menu click lands.

**Results.** Gold exe, software renderer at the watcher's low detail (320x200), P166, Instant Melee, 20 s throttle.
The full session (boot to shutdown) ran without host input while the watcher's VM held the foreground.

| VMs on the host (incl. the watcher's) | in-mission speed vs real time | fps (parked / throttle) |
|---|---|---|
| 2 (one scripted run, n = 2) | 1.000 / 1.003 | 34.3 / 34.2, 34.5 / 34.4 |
| 3 (two parallel) | 0.974 / 0.979 | 34.1 / 34.6, 33.7 / 33.5 |
| 4 (three parallel) | 0.832 / 0.830 / 0.856 | 33.4 / 33.8, 31.3 / 33.0, 33.9 / 34.4 |

- **The fps agree with the watcher's.** Its own P166 low-detail runs gave 33.2 / 33.9 fps parked.
- **Falling behind costs real time, not validity.** Frame rates hold in guest time when a VM falls behind real time.
- **Capacity.** Each VM takes one host core. On this 4-core PC, one extra VM beside the watcher's stays real-time;
  three fall to about 0.83.
- **Menus are slow even alone.** Boot and the game's 640x480 shell menus run at 70 to 80 % in 86Box even for a lone
  VM. Only the mission segments are reported as the speed check.
- **Screenshots.** Every capture had content. A minimized 86Box window gives only a 160x28 caption.

Not covered: the Glide path and the retail exe (it needs disc 2).

### Morning 2026-10-15: software renderer at the owner's low-detail configuration (the reference)

Owner's spec: software only (the emulated Voodoo's fill rate is not modelled, so the Glide numbers are not a
reference) at 320x200 / lowest detail. Gold exe; I76FPS at 20 ms (the real period is ~30 ms on Windows 95). The window
is 60 s, starting 10 s into the mission. Full tables: lab `emu/results/RESULTS.md` sections 3-4.

| scene | P166 |
|---|---|
| Instant Melee | 33.2 / 32.6 / 33.9 fps |
| T05 | 29.4 |
| T13 | 28.5 |
| T04 | 29.8 |

- **Physics substeps** (`floor(dt*20)+1`, Gold `0x49cc20`): one step per frame.
  - The share of 2-step frames is 0.1-1 %.
  - The step length is the frame time: ~30-35 ms.
  - At the game's default detail (~13 fps) the same rule gives 2-3 steps per frame.
- **Gameplay check on the P166:**
  - Observed: menus, bookmarks, cutscenes and missions run without a crash.
  - Observed: the AI closes in, fires and damages a parked player in T13. It destroyed the car at ~45 s (n=1).
  - In melee the AI killed the parked player in 1 of 3 runs (at 56 s).
  - **Not tested:** the T05 jump (the route to the ramp is not known in the guest; straight full throttle leaves the
    road) and AI dodging. Sound was not tested either: the guest has no sound driver.
- **Saves for the owner:** bookmarks before T04 / T05 / T13 are in lab `emu/results/saves/`, with disk snapshot
  `emu/images/w95pb-hdd-saves-20261015.img`.
