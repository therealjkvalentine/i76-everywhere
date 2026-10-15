# Emulated 1997 PC: measuring what "stock" really was (plan, 2026-10-14)

[WHAT-IS-STOCK.md](WHAT-IS-STOCK.md) ends on two numbers that no source pins down:

- **The Windows 95 `GetTickCount` step.** "55 ms" is second-hand only.
- **I'76's real frame rate on its target box.** Release spec: P90 minimum, P133 + 32 MB recommended, software
  renderer only. The 3dfx Glide path came later, with the patches and Gold.

Every lab profile that claims to be "1997" (`I76_TICK_MS`, `I76_FPS_CAP`, the R-1997 rows, the W95-18 pilot) rests on
those two numbers. This plan measures them on an emulated box-spec PC instead of inferring them.

Everything is set up in the lab: `../i76-uncap-lab/emu/` (README.md there is the owner's install guide and the
technical reference). The Windows 95 install is the only step that waits on the owner.

## Setup (ready)

| part | choice | why |
|---|---|---|
| emulator | 86Box v6.0 build 9001 (2026-05-31), sha256 checked against GitHub's digest; ROM set tag v6.0 | cycle-timed PC emulator with a Voodoo 1 model |
| board | ASUS P/I-P55T2P4, Intel 430HX, Award 4.51PG | 1996 Socket 7; takes all three CPUs at their real bus speeds |
| CPU | Pentium 90 (60 MHz x 1.5), 133 (66 x 2), 166 (66 x 2.5) | min spec, recommended spec, the "P166 + Voodoo" anecdote |
| RAM | 32 MB | recommended spec (a 16 MB P90 run is a one-line edit) |
| 2D | S3 Trio64 PCI 2 MB; variant: Matrox Millennium | commonest 1996 card; the Millennium matches a June 1997 report: "P133 with a Millenium ... jerky and slow" |
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
- An interpreter variant (`p133-interp`) is kept only as a cross-check.

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

In `../i76-uncap-lab/emu/images/`:

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
  (what a 1997 owner got); a second set uses fixed settings, so the CPUs are compared like for like.

| # | measure | where | answers |
|---|---|---|---|
| 1 | TICKPRB, 30 s | p133, p90, p166 (Windows 95); p133-w98 if media exists | the Windows 95 (and 98) `GetTickCount` step and its true length; whether `timeBeginPeriod(1)` changes it; real `Sleep(1)` |
| 2 | I76FPS, software renderer, retail 1.0 exe | p90, p133, p166, p133-mill | the March 1997 frame rate per CPU and 2D card, in Instant Melee (quick menu path), T04 race, T13 combat, T05 canyon jump |
| 3 | I76FPS, Glide, Gold exe + Voodoo | p90, p133, p166 | the later Voodoo frame rate. 86Box does not time the Voodoo's fill rate, so a scene counts only if its fps scales with the CPU clock (CPU-bound); otherwise it is reported as an upper bound |
| 4 | controls | p133, one scene | I76FPS period 250 vs 1000 ms (sampler overhead); p133-interp vs p133 (CPU timing model) |

**Getting to T04 / T13 / T05 without the proxy's direct boot.** The plan is campaign bookmarks:

- Play to each mission once in the VM (on p166, the fastest), save, and reuse the save for every CPU. One disk image
  serves all three CPU variants.
- The lab's Gold saves can go in on the tools CD (`make-cds.py tools --saves <dir>`). Whether retail 1.0 reads Gold
  saves is untested.
- The 1997 `GAMEKEY.MAP` lists a `TOGGLE_FRAMERATE` (Alt+F) debug key, but marks that block "Don't function in release
  build". Pressing it once in the VM costs nothing; I76FPS does not depend on it.

## How the results feed the lab

- **Tick.** TICKPRB's step on Windows 95 replaces the assumed 55 ms. The lab's `I76_TICK_MS` and the R-1997 rows in
  WHAT-IS-STOCK then use the measured value. If it is about 55 ms, the R-1997a/b findings stand and the question
  becomes which fps went with it. If it is finer, the 55 ms profiles drop to a sensitivity test, as WHAT-IS-STOCK
  already recommends.
- **Frame rate.** I76FPS's P133 software numbers become the "1997 recommended box" fps. P90 gives the floor. P166 +
  Voodoo, if CPU-bound, gives the anecdote's real number. They set `I76_FPS_CAP` for the box-spec profiles.
- **W95-18.** Another agent is running the W95-18 pilot. Its doc,
  `../i76-uncap-lab/docs/W95-18-BASELINE-2026-10-14.md`, did not exist when this plan was written. Once it does,
  read its tick and fps assumptions and set the measured values against them, as a proposal in this doc or in the
  results; never edit that doc. The same applies to the `I76_FRAME_LOG` box-spec work referenced in `strlkproxy.c`
  (lab `docs/BOX-SPEC-BASELINE-2026-10-14.md`, also not yet written).
- Results go to `../i76-uncap-lab/emu/results/` (raw logs, copied out of the disk image with `emu/tools/fat.py`).
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
  and caches. For that reason the p133-interp cross-check, and agreement with the few period reports (P133 + Millennium
  "jerky", P90 / 16 MB "choke"), are part of reading the numbers.

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
