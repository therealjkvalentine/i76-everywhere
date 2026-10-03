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
| `u32x_full.c` | the source of the **full build** (added 2026-10-03) | `eb3c2cc7147b41e9044907fe8942b547` | the lab's `src\u32x.c` at lab commit `68a8a39` (2026-10-02 23:37; git blob `2a6f1994`, md5 `72ecf27a`) **plus the P1-19 modal-pump fix** (section "P1-19" below; 2026-10-03). No longer byte-identical to any lab blob; the lab's `src\u32x.c` does not have the fix |
| `u32x_full.def` | its export list: the same 53 names, with `GetAsyncKeyState` and `GetKeyState` also pointed at our code (6 intercepts + 47 forwarders) | `2902622b28ab4ed5f79a59b54c50176d` | byte-identical to the lab's `src\u32x.def` at the same commit (blob `4b94a933`) |
| `u32x_full.dll` | **the gated full binary with the P1-19 fix**, 112,640 B, x86, built 2026-10-03 by `build-full.ps1` from the `u32x_full.c` above | `696577dcc5ed7c2997e6099421e68000` (sha256 `4e2c3fd0…98ed27a7`) | sandbox-gated 2026-10-03 (section "P1-19"). The previous binary, `054fb411` (what the 2026-10-03 daily driver runs), stays in the lab as `src\u32x_gated_054fb411.dll` and in the sandbox as `game\u32x.dll.054fb411`; it is still on `$KnownGood` |
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
`docs/MENU-REBUILD-DESIGN.md` as they were on the day; they are not updated. (Until 2026-10-03 the file was
byte-identical to the lab blob; the P1-19 fix below is the first change made here.)

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

## P1-19: no keep-alive pump inside the shell's modal loops (build `696577dc`, 2026-10-03)

**Symptom (owner, sandbox, `054fb411`).** Garage, Build & Repair, DONE with a part missing: "CAN'T GET VERY FAR
WITHOUT AN ENGINE" comes up and neither mouse nor keyboard closes it. Static analysis:
`..\i76-uncap-lab\docs\GARAGE-POPUP-STUCK.md`.

**Cause (measured).** The popup is the shell's `Modal_ImageOk` (0x1000b800). It does one present, then loops on
`Mouse_Update` + left-click, with no `PeekMessage` of its own. In `054fb411`, `GetCursorPos` / `GetAsyncKeyState`
ran `pump_keepalive()` inside that loop. After any focus change (Alt+Tab, a toast) the pump delivered `WM_ACTIVATEAPP 0`.
`ShellWindowProc` then cleared the shell's input gate `[i76shell+0x43224]`, and `Mouse_Update` returns before any
USER32 call while the gate is 0. Nothing pumps again, so the gate never reopens. Stock delivers nothing inside the
modal: the gate stays 1 and a click on OK works on return. Lab sandbox, focus taken by a notepad and given back,
click on OK:

| build / switch | launches | trials | popup closed | gate during the focus change |
|---|---|---|---|---|
| `054fb411` | 2 | 2 (+1 retry click each) | **0 of 2** | 0 within 0.3 s, shell mouse frozen |
| `054fb411` + `I76_U32X_PUMPS=0` (control) | 2 | 4 valid | 4 of 4 | 1 |
| `696577dc` (this fix) | 2 | 6 | **6 of 6** | 1 |
| `696577dc` + `I76_U32X_MODAL_PUMP=1` (kill switch) | 1 | 1 (+1 retry) | 0 of 1 | 0 |

**Fix.** `pump_from_poll(ra)` replaces the unconditional `pump_keepalive()` in `My_GetCursorPos`,
`My_GetAsyncKeyState` and `My_GetKeyState`. A caller inside `i76shell.dll` pumps only while ShellMain's own frame
loop is alive, i.e. its unfiltered `PeekMessageA(.., 0, 0, PM_REMOVE)` (recorded in `My_PeekMessageA`) ran within
the last 250 ms. Inside a modal it does not pump, which is stock semantics. Exe callers (the mission), the
keyboard-filter pump of the name-entry loop and the GDI/Glide present hooks are unchanged. Ghosting stays off
(`DisableProcessWindowsGhosting`). **Kill switch: `I76_U32X_MODAL_PUMP=1`** restores the `054fb411` behaviour.

**Gate (sandbox `..\i76-uncap-lab\game`, 2026-10-03; lab `autotest\runs\gate\20261003-122320` and following):**
leg-b bookmark route **3 of 3**; trip route through `TEST-FRAMERATE -Mode all120` **2 of 2 at 120 fps**; Save
Bookmark screen (gate stays 1 over 10 s idle, mouse follows, SAVE x2, NO writes nothing, YES writes only the scratch
bookmark, savegame.dir exact) **pass**; melee by menus **pass**; widescreen Esc menu (`I76_ASPECT=3440x1440`,
`I76_U32X_MENU_ASPECT=3440:1440`, `I76_GLIDE_REFRESH=120`, `dgVoodoo.aspect-wide.conf`): Exit clicked where drawn
at screen (2319,1329), `[0x4fe534]` 0x10 -> 0x1 **pass**. Gate row 5 (Esc menu with the folder's own conf and the
global conf hidden) **failed for both builds alike**: its direct t01 boot never left the shell ("not in a mission
after 90 s", client 640x480; the same-condition control with `054fb411` failed identically, 1 of 1), while
`test-escmenu -Stage open` without the gate reached mode 0x10 with both builds. That is a gate-environment
problem in the sandbox, not this change. **Not run:** the daily driver or its twin (not touched), the owner's own
hands.

**Not fixed by this.** The pencil does not move while the popup is up: inside `Modal_ImageOk` nothing presents,
so the drawn pointer stays where DONE was clicked (captured live: shell mouse at (150,150) and (500,350), pencil
still on DONE). The player aims at OK blind. A click on OK closes it (verified). Two possible follow-ups:
re-present from u32x while a shell modal spins, or the shell's F7 Enter/Space exit (lab doc section 4, Fix 2).

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
