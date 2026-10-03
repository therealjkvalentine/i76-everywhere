# u32x: the USER32 proxy (menu / save-screen mouse, Save Bookmark ghosting)

`u32x.dll` sits between the game and `USER32.dll`. `i76shell.dll` (menus, garage, save screen) and `i76.exe`
both hit-test raw screen coordinates against 640x480 widget rectangles; under dgVoodoo's stretch those numbers
are out of range, so clicks land wrong and the "Overwrite an existing bookmark?" poll loop can spin forever.
The proxy translates four calls (`GetCursorPos`, `SetCursorPos`, `ClipCursor`, `PeekMessageA`), forwards the
other 49 by name to the real `user32`, and calls `DisableProcessWindowsGhosting()` once at load so DWM does not
replace the Save Bookmark screen with a ghost window after about 5.9 s idle. Root-cause write-up:
[docs/SAVE-FREEZE-ROOT-CAUSE.md](../docs/SAVE-FREEZE-ROOT-CAUSE.md).

It contains no Activision bytes: it is our own code plus forwarders by name.

## What is here, and where it came from

Moved into this repo on 2026-10-02 (backlog P3-02; [docs/RELEASE-PLAN.md](../docs/RELEASE-PLAN.md) section 2
asked for it: a deployed, load-bearing DLL whose source sat only in the private lab repo was not releasable).

| file | what | md5 | source note |
|---|---|---|---|
| `u32x_min.c` | the source of the shipped build | `9050751fac77a6666c2b7313a04dc713` | byte-identical copy of `..\i76-uncap-lab\src\u32x_min.c` (untracked there). It is the 2026-08-16 revision of the lab's `u32x.c` (lab commit `bfbc2ba`) plus one block, the ghosting call, applied by the lab's `src\patch_min.py` on 2026-09-07 |
| `u32x.def` | export list: 4 intercepts + 49 forwarders = 53 names, the union of the USER32 imports of `i76shell.dll` and `i76.exe` | `9188eca53eb351a0c664ca2f2c222dfc` | byte-identical copy of `..\i76-uncap-lab\src\u32x_min.def` |
| `u32x.dll` | **the verified binary**, 75,264 B, x86 | `a5927cea02697657ce2102be766b5616` (sha256 `140990d8…cb952ab`) | byte-identical copy of `..\i76-uncap-lab\src\u32x_min.dll`, built there 2026-09-07 15:56 by `src\build-min.ps1` (MSVC 2019 x86, `cl /O2 /LD u32x_min.c /link /DEF:u32x_min.def user32.lib`) |
| `build.ps1` | rebuilds from the two source files to `u32x.build.dll` (never over `u32x.dll` unless `-Replace`) | | port of the lab's `src\build-min.ps1` |
| `deploy-u32x.ps1` | installs / removes the proxy in a game folder | | port of the lab's `tools\instruments\deploy-shellfix.ps1`, with import/export and md5 guards |

The two source files carry `-text` in `.gitattributes` so the md5s above hold on any checkout.

**Why this build and not the lab's newer `u32x.c`.** The verified-safe build is this minimal one. Its live record
([docs/STATUS-2026-10-02.md](../docs/STATUS-2026-10-02.md), "Correction, 22:30"), all on the sandbox
`..\i76-uncap-lab\game`: TRIP -> LOAD BOOKMARK -> garage -> DONE 2/2 (leg-b B1.9: 3 of 3 with this build and with
the 2026-08-16 build); `TEST-FRAMERATE` option 6 through the trip menus 2/2 at 120.0 fps, option 5 1/1 at 60.0;
Save Bookmark screen after 10 s idle: row click, SAVE twice, overwrite prompt. The lab's development branch
(`..\i76-uncap-lab\src\u32x.c`: per-call census, keep-alive pump, the Esc-menu box mapping) produced md5
`037fcb3a`, which **broke the bookmark route** (4 of 4 failing at DONE) and was withdrawn the same evening; that
work stays in the lab until it passes the same route, and then moves here as a new recorded build. Not verified
by this build: the fullscreen Esc menu's Exit button (use the keyboard there).

**Not yet done for this build:** a run on the daily driver, and a fresh-install run of `setup-windows.ps1` on a
clean GOG folder (RELEASE-PLAN section 7 item 3). `deploy-u32x.ps1` was exercised offline on 2026-10-02 against
scratch copies of the pristine GOG binaries (`..\i76-map\sandbox-gog\main\app`, `i76.exe` md5 `9a232dcc`):
install changes exactly 10 bytes in each of `i76.exe` and `i76shell.dll` (the import-descriptor name),
`-Status` reads the result back, `-Restore` returns both files to their original md5. No game was started.

## Build

    powershell -ExecutionPolicy Bypass -File u32x\build.ps1

Needs the Visual Studio C++ x86 tools. Output is `u32x.build.dll`; the script checks the PE machine field
(0x14C) and that the image names `DisableProcessWindowsGhosting`, and prints the md5. A rebuild on 2026-10-02
(same machine, same compiler) came out at 75,264 B and differed from `u32x.dll` in 6 bytes (link-time stamps),
so the committed binary is reproducible from this source up to the timestamp. `LNK4070` is expected (the `.def`
names the library `u32x`, the scratch output is `u32x.build.dll`) and is filtered from the summary.

The diagnostic build (`cl /DU32X_LOG ...`) writes to a hard-coded lab path
(`C:\Users\james\i76-uncap-lab\captures\save\u32x.log`); it is a lab instrument and is not built here.

## Deploy

    u32x\deploy-u32x.ps1 -GameDir <folder> -Status
    u32x\deploy-u32x.ps1 -GameDir <folder>             # install u32x\u32x.dll
    u32x\deploy-u32x.ps1 -GameDir <folder> -Restore    # originals back

`-GameDir` is mandatory: there is no default that could land on the install being played on. Install copies the
DLL, then rewrites the name in the `USER32.dll` import descriptor of `i76shell.dll` and `i76.exe` to `u32x.dll`
(same length, NUL-padded), keeping `i76shell.dll.orig` and `i76.exe.u32xorig`. Before writing anything it checks
that the DLL exports every function the two binaries import from USER32 (one missing name and the game does
not load), that the DLL is 32-bit, and that its md5 is in the script's `$KnownGood` list; every write is read
back. `-U32xDll <path> -AllowUnverified` installs a test build, for the sandbox only.

`setup-windows.ps1` runs this for the base game (`-U32xDll`, `-NoU32x`; not for the Nitro Pack, whose imports
were never checked against the export list) and `Make-Portable-Zip.ps1` runs it on the staged copy, so a fresh
install and the portable zip both carry the recorded build. `LAUNCHER.ps1` shows the installed DLL's size class.

## Promoting a rebuild

1. `u32x\build.ps1`, note the md5.
2. `u32x\deploy-u32x.ps1 -GameDir ..\i76-uncap-lab\game -U32xDll u32x\u32x.build.dll -AllowUnverified`, read
   back `-Status`.
3. At the physical console (not RDP): the bookmark route to DONE, the Save Bookmark screen after 10 s idle, a
   melee entry. A/A first, record n (`..\i76-uncap-lab\autotest\option6-trip-test.ps1`, `saves\leg-b.ps1`).
4. Only then `build.ps1 -Replace`, and in the same commit: the md5 in the table above, a `$KnownGood` entry in
   `deploy-u32x.ps1`, and a CHANGELOG line with the status in brackets.
