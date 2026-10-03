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
| `u32x_full.c` | the source of the **full build**, the one the daily driver runs (added 2026-10-03) | `72ecf27a4acaa1d9a907ce34276a2c94` | byte-identical to the lab's `src\u32x.c` at lab commit `68a8a39` (2026-10-02 23:37; git blob `2a6f1994`). Not the lab's current `u32x.c` |
| `u32x_full.def` | its export list: the same 53 names, with `GetAsyncKeyState` and `GetKeyState` also pointed at our code (6 intercepts + 47 forwarders) | `2902622b28ab4ed5f79a59b54c50176d` | byte-identical to the lab's `src\u32x.def` at the same commit (blob `4b94a933`) |
| `u32x_full.dll` | **the gated full binary**, 112,640 B, x86, link time 2026-10-02 23:36:45 | `054fb411d57c275f9a6ebcf9a99893e6` (sha256 `957cf671…cf78cabd`) | byte-identical copy of `..\i76-uncap-lab\src\u32x_gated_054fb411.dll` |
| `build-full.ps1` | rebuilds the full build to `u32x_full.build.dll` and reports which bytes differ from `u32x_full.dll` | | port of the lab's `src\build-u32x.ps1` (same compiler line) |
| `deploy-u32x.ps1` | installs / removes the proxy in a game folder | | port of the lab's `tools\instruments\deploy-shellfix.ps1`, with import/export and md5 guards |

The source files carry `-text` in `.gitattributes` so the md5s above hold on any checkout.

**Why this build and not the lab's newer `u32x.c`.** The verified-safe build is this minimal one. Its live record
([docs/records/STATUS-2026-10-02.md](../docs/records/STATUS-2026-10-02.md), "Correction, 22:30"), all on the sandbox
`..\i76-uncap-lab\game`: TRIP -> LOAD BOOKMARK -> garage -> DONE 2/2 (leg-b B1.9: 3 of 3 with this build and with
the 2026-08-16 build); `TEST-FRAMERATE` option 6 through the trip menus 2/2 at 120.0 fps, option 5 1/1 at 60.0;
Save Bookmark screen after 10 s idle: row click, SAVE twice, overwrite prompt. The lab's development branch
(`..\i76-uncap-lab\src\u32x.c`: per-call census, keep-alive pump, the Esc-menu box mapping) produced md5
`037fcb3a`, which **broke the bookmark route** (4 of 4 failing at DONE) and was withdrawn the same evening; that
work stays in the lab until it passes the same route, and then moves here as a new recorded build. Not verified
by this build: the fullscreen Esc menu's Exit button (use the keyboard there).

## The full build (`u32x_full`, md5 `054fb411`): what the daily driver runs

Added to this repo on 2026-10-03. Until then this folder held only the minimal build, and the daily driver
(`C:\Users\james\Games\Interstate76-2026-10-03`, [docs/records/NEW-DAILY-DRIVER-RECIPE.md](../docs/records/NEW-DAILY-DRIVER-RECIPE.md))
ran a DLL whose source was only in the lab repo.

**Which source.** Lab commit `68a8a39` ("u32x: no computed pointer box (frame map when no clip box was
measured); VPTR default moves the shell's corner clip onto the picture; cursor window stands down where the OS
arrow is already right", 2026-10-02 23:37:41). How it was pinned: the binary's PE link time is 2026-10-02
23:36:45, 56 s before that commit; the lab's `docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md` section 9.4 names
`054fb411` as "the 9.8 revision", which is that commit; and the rebuild below. The lab's neighbouring builds are
different binaries: the lab doc gives `62158845` for the first vptr build (commit `cc661a6`), and the build of
the commit after (`a467ceb`, the lab's current `u32x.c`) is `c508b0e6`, 112,128 B. **The gated build is not the
lab's newest source**; `a467ceb` has not been through the gate.

**Does a rebuild reproduce it.** `u32x\build-full.ps1` on 2026-10-03 (this machine, Visual Studio 2019 Build
Tools x86, linker 14.29, the lab script's line `cl /nologo /O2 /LD ... /link /DEF:... user32.lib`): 112,640 B,
same section layout, **4 bytes differ from `u32x_full.dll`, all link-time stamps** (2 bytes of the PE header's
`TimeDateStamp`, 2 bytes of the debug directory's copy of it). `.text`, `.data` and `.reloc` are identical;
`.rdata` differs only in that stamp. The md5 is therefore not reproduced (a rebuild at another second has
another md5; these were `ec3993cc` and `f22a03e7`), the code is. n = 2 rebuilds: once under the lab's file
names, once under this folder's. Another compiler version is expected to differ in code bytes; the script
says so when it does.

**How it differs from `u32x_min`.** `u32x_min.c` translates four calls and switches DWM ghosting off.
`u32x_full.c` (1,894 lines) keeps those and adds:

| addition | switch | default |
|---|---|---|
| The exe's own Esc menu: maps `WM_LBUTTONDOWN/UP` from the box the pointer can reach onto the 640x480 page and undoes the engine's per-mode rescale, so Exit and the other items can be clicked. It reads engine globals at fixed addresses, guarded by a byte signature of `0x4972d0`: an exe it does not recognise gets none of it | `I76_U32X_MENU`, `I76_U32X_MENU_BOX`, `I76_U32X_MENU_ASPECT` | on |
| `GetAsyncKeyState` / `GetKeyState` routed through our code, the shell key-path instruments, and the keep-alive pump with its WM_QUIT guard (lab commit `b0cdf7f`: the pump had been taking ShellMain's WM_QUIT, which was the garage DONE regression of build `037fcb3a`) | the switch comments in the source | see the source |
| "One pointer" (milestone A1 of [MENU-REBUILD-DESIGN.md](../docs/records/MENU-REBUILD-DESIGN.md)): a click-through arrow window over the drawn picture | `I76_U32X_VPTR=1` | **off**. In this revision, switching it on also moves the shell's clip, which broke leg-b 2 of 3 in the lab's first live run; the lab changed that one commit later. Leave it unset with this binary |
| A per-call census and log (`cl /DU32X_LOG`) | build time | not built here: it writes to a hard-coded lab path |

It also imports `gdi32.dll` (a pragma in the source). The comments in `u32x_full.c` name lab paths and
`docs/MENU-REBUILD-DESIGN.md` as they were on the day; the file is kept byte-identical to the lab blob, so they
are not updated.

**Gate evidence** (2026-10-02/03, as recorded in `deploy-u32x.ps1`'s `$KnownGood` and
[docs/records/STATUS-2026-10-02.md](../docs/records/STATUS-2026-10-02.md), last section; lab run folders
`autotest\runs\vptr\20261002-234050` and `autotest\runs\gate\`): leg-b (TRIP -> LOAD BOOKMARK -> garage ->
DONE) 3 of 3; the trip route at 120 fps; the Save Bookmark screen; the Esc menu's Exit by mouse; a melee entry.
The daily driver has run it since 2026-10-03. Not run: a fresh GOG install (`i76.exe` `9a232dcc`; the gate's
exe was `60abf7bc`), the Nitro Pack, Wine / Proton. Checked on 2026-10-03 without the game: on scratch copies of
the pristine GOG `i76.exe` and `i76shell.dll`, `deploy-u32x.ps1 -U32xDll u32x\u32x_full.dll` passes the
import/export guard, changes 10 bytes in each file, `-Status` reads it back, `-Restore` returns both md5s.

**Where it is installed.** `setup-windows.ps1` installs `u32x_full.dll` by default since 2026-10-03 (it hands
the DLL to `deploy-u32x.ps1`, which accepts only an md5 on its `$KnownGood` list; both builds are on it).
`-U32xDll u32x\u32x.dll` installs the minimal build. `Make-Portable-Zip.ps1` and `tools\Make-Daily-Driver.ps1`
still default to `u32x.dll`: pass `-U32xDll u32x\u32x_full.dll` to them (a portable zip made without it puts
the minimal build into the staged copy).

## The minimal build: notes

**Not yet done for the committed build (`a5927cea`):** a run on the daily driver, and a fresh-install run of `setup-windows.ps1` on a
clean GOG folder (RELEASE-PLAN section 7 item 3). `deploy-u32x.ps1` was exercised offline on 2026-10-02 against
scratch copies of the pristine GOG binaries (`..\i76-map\sandbox-gog\main\app`, `i76.exe` md5 `9a232dcc`):
install changes exactly 10 bytes in each of `i76.exe` and `i76shell.dll` (the import-descriptor name),
`-Status` reads the result back, `-Restore` returns both files to their original md5. No game was started.

## Build

    powershell -ExecutionPolicy Bypass -File u32x\build.ps1         # minimal build -> u32x.build.dll
    powershell -ExecutionPolicy Bypass -File u32x\build-full.ps1    # full build    -> u32x_full.build.dll

The paragraph below is about the minimal build; the full build's result is in its section above.

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
install and the portable zip both carry a recorded build (by default the full one and the minimal one
respectively). `LAUNCHER.ps1` shows the installed DLL's size class.

## Promoting a rebuild

1. `u32x\build.ps1`, note the md5.
2. `u32x\deploy-u32x.ps1 -GameDir ..\i76-uncap-lab\game -U32xDll u32x\u32x.build.dll -AllowUnverified`, read
   back `-Status`.
3. At the physical console (not RDP): the bookmark route to DONE, the Save Bookmark screen after 10 s idle, a
   melee entry. A/A first, record n (`..\i76-uncap-lab\autotest\option6-trip-test.ps1`, `saves\leg-b.ps1`).
4. Only then `build.ps1 -Replace`, and in the same commit: the md5 in the table above, a `$KnownGood` entry in
   `deploy-u32x.ps1`, and a CHANGELOG line with the status in brackets.
