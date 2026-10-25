# Nitro parity audit: Gold fixes that are not graphics keys (2026-10-24 night, nitro-parity lane)

Owner, 2026-10-24: he plays Nitro in the morning (missions and network) and wants it "polished and caught up", including "other
fixes we had to make on Gold like these ones that we found". The graphics preset keys were matrixed by the Nitro port lane
(NITRO-PORT-2026-10-21.md s.11). This lane audits everything else: shell fixes, u32x fixes, default-on proxy fixes, crash guards,
music, the tick's sub-fixes and the stability fixes. The Nitro polish lane owns five items tonight and they are not touched here:
the stuck dropper sound, the screen-edge flashing, the audio balance, the bus mission and the "rename variant" text entry.

Sources: FIX-INVENTORY-2026-10-17.md, MENU-SOUND-POLISH-2026-10-20.md (items A-J), PROMOTION-18-2026-10-17.md,
OPEN-FEATURES-2026-10-24.md s.6, STABILITY-2026-10-24.md, FFB-FOCUS-2026-10-24.md, DGVOODOO-UPDATE-2026-10-24.md s.7, the Gold
DllMain against nitro_dllmain (strlkproxy.c), u32x/u32x_full.c, and a per-feature diff of the proxy log of a Gold boot against a
Nitro boot with the owner's presets (OWNER-2300-ALL / OWNER-NITRO-ALL).

## 1. The matrix

"Before" is main b2297c9 (the owner's copy runs e78aedd5, built from fdf07cf, which has the same Nitro coverage).

| Gold fix | where on Gold | Nitro before | Nitro now | evidence / reason |
|---|---|---|---|---|
| Sim-tick moving-object list forgotten at a new mission (STABILITY s.1) | simtick.c, `NA(0x5a7e18)` | applied | applied | stability lane's nitro-after-replay: 3 x `forgot 7 moving objects`; it is the same code through NA |
| Mission font free guard (second mission, exit) | nitro.c, Nitro only | applied (3/3) | applied (3/3) | no Gold counterpart needed |
| winmm heap fix (DGVOODOO-UPDATE s.7) | winmmrace.c, before the exe branch | runs (exe-agnostic) | runs | it acts only where it sees the AcGenral split. Laptop (26100.9711, where i76.exe crashes without it): nitro.exe logs `not needed so far (DllMain: no module with a split Global* set)` (n 3 boots). So Windows' shim database does not appear to give nitro.exe the split that i76.exe gets. Nothing to port |
| Music: CD emulation, run end, resume, gapless, guard, retail set | strlkproxy.c | applied | applied | NITRO-PORT s.7.1 / s.11; disc order, shell 1997 and missions 1997 describe the Gold CD (refused on purpose) |
| Menu keys (F), menu draw (I), font private (G), fade no flip (B), sign sound restart (C) | polish.c, simtick.c | applied | applied | NITRO-PORT s.11 |
| **Esc-menu pointer recentre `I76_MENU_PTR_CENTRE` (H)** | escmenu.c, show-pointer 0x44bd38 | **off** (the code stood down on Nitro) | **ported** | Nitro runs the same show-pointer code (0x443688, site map reloc, 18 bytes the same) and the same cursor map on nitro.exe's SetCursorPos. Measured on the console (s.3): with the switch off the pointer opens on the bottom edge, y 1439 of 1440 (3 of 3 opens); with it on, y 720 (9 of 9 opens). Note: [0x653bb0] reads 480 with the menu up, so on Nitro the stock path to the bottom edge is not exactly Gold's (client height read as a UI y); the effect and the fix are measured, the mechanism is not |
| **Stock FFB focus fix `I76_FFB_REACQUIRE` (keep-on-blur, NULL-slot guard at I7_SFRCE+0x2505, re-acquire)** | ffbfocus.c (FFB lane, Gold only) | **absent** | **ported** | measured with the T300 (s.3): stock loses the effects at a focus loss on Nitro too (`effects playing 0 of 3` after the return), the fix keeps 3 of 3. Nitro ships the same I7_SFRCE.DLL (md5 687cc35b) and the same ffb code relocated: ffb_PlayEffect 0x446110 -> 0x42fb00, ForcesOn / Off 0x445b40 / 0x445b60 -> 0x42a900 / 0x42a920, device flag 0x52bbd0 -> 0x523248, effect fn 0x52bbe4 -> 0x5234dc, forces flag 0x4f2330 -> 0x4f2d58, active flag 0x504c1c -> 0x526a6c (read side by side, s.2). The owner's Nitro copy has no interposer, so his T300 runs the stock path, crash included |
| FFB device guard `I76_FFB_GUARD` | strlkproxy.c (LAN preset only on Gold) | absent | ported, same default (off unless set) | the stub's two absolute reads relocated (`nitro stub ffb-guard stub: 2 address(es) relocated`); the no-device +0x2505 fault is also covered by the focus fix's NULL-slot guard, which is default on |
| **DWM ghosting off** (save-screen wedge) | u32x.dll DllMain | **absent** (Nitro has no u32x) | **ported** `I76_NO_GHOSTING` (default 1) | `no-ghosting: on - DisableProcessWindowsGhosting called` |
| **Message boxes in front of the picture** (audit b2) | u32x.dll MessageBoxA | **absent** | **ported** `I76_NITRO_MSGBOX` (default 1), nitro.exe and NITSHELL.DLL slots | the laptop run below: nitro.exe's "Unhandled Exception" box was `placed at (856,466) 209x149, topmost` over the picture |
| Shell F7 (Enter / Space close OK popups) | i76shell file patch | not installed | **installed** (NITSHELL a32ffba6 by the polish lane, s.4) | tools/patch-nitshell-f7.py, NITRO-PORT s.7.3 |
| Shell K3 (Y / N / Esc on yes-no prompts) | i76shell file patch | not installed | **installed** (the same a32ffba6, s.4) | patch-nitshell-modals.py `--only K3`; emulation K3 rows OK |
| Shell M1 (vehicle-rejected panel) | i76shell | n/a | n/a | Nitro draws its own frame 0x21 correctly (NITRO-PORT s.8.2) |
| Shell M2, K1, K2, K4 | not in Gold's shipped shell | - | installed by the polish lane (a32ffba6) | its "rename variant" item, tested live there |
| Shell text-entry clear | i76shell (fix-shell-textentry.ps1) | - | **not here** | the Nitro polish lane's "rename variant" item |
| u32x name-entry keyboard poll, modal pointer, WM_QUIT, no keep-alive pump | u32x.dll | - | not ported | pointer-side behaviour of u32x; the proxy's cursor map covers the pointer on Nitro (NITRO-PORT s.10); the text-entry one is the polish lane's |
| Save screen / F2 orphaned bookmark | i76shell / u32x | n/a | n/a | Nitro has no bookmarks (NITRO-BASE) |
| Tick sub-fixes (flame damage rate, sky / orbit at the 1997 rate, tick-factors, radar pings, race tick) | simtick.c | applied | applied | the Nitro log's sim-tick / tick-factors lines are the Gold log's line for line (same preset, n 1 each); Nitro adds the race tick and its two extra radar pings |
| Fixed-step era switches (I76_FIXED_STEP, ENGINE_DT_FIX, FRAMERATE_FIXES, COLL_DEDUPE / WINDOW, INPUT_LATCH, RENDER_INTERP, AI parity set) | strlkproxy.c | not called | not ported | not in the owner's Gold set either: the whole-sim tick replaces them (OWNER-2300-ALL has none of them) |
| Co-op guards (script NULL-object guard, host respawn, heap guard `coop-heap`, IPX pin, arena name) | strlkproxy.c / mpmenu.c / polish.c, with I76_COOP_AI | n/a | **not here** | Gold's LAN path; Nitro's network is the Nitro MP lane's (nitro_mp / nitro_ai / nitro_form). Flagged to it: the script-action NULL guard (fsm 0x40b8e0 / 0x40b940 / 0x49d5f0 / 0x49d740 / 0x468440) and the AcGenral heap guard are crash fixes from Gold co-op that Nitro co-op may need; the generator now maps 0x40b8e0 -> 0x417f50, 0x40b940 -> 0x417fb0, 0x468440 -> 0x45ad40 (exact) |
| I76_MENU_PTR (DxWnd), I76_PAD_MENU, I76_CD_FAKE / CD_LOG | opt-in / Mac / Deck | off | off | not the owner's PC path |

## 2. What was ported (code)

- `escmenu.c`: the Nitro stand-down removed; the read-back is nitro_patch_bytes' own on Nitro.
- `ffbfocus.c` (the FFB lane's file): the three exe reads (active flag, forces flag, the effect function pointer) and the keep-on-blur
  read-back go through `NA()`; Gold reads the same addresses as before (NA returns its argument on Gold).
- `strlkproxy.c`: `apply_ffb_guard` relocates its stub on Nitro (`nitro_reloc_stub`); `nitro_dllmain` calls `apply_menu_ptr_centre`,
  `apply_ffb_guard`, `nitro_no_ghosting`, `nitro_msgbox_attach`; `hook_LoadLibraryA` attaches the message-box hook to NITSHELL.DLL.
- `nitroparity.c` (new): I76_NO_GHOSTING and I76_NITRO_MSGBOX (u32x_full.c's msgbox logic, cut down: clip released, arrow shown,
  MB_TOPMOST | MB_SETFOREGROUND, a CBT hook centres the box topmost on the game window, all given back after; every box logged).
- `tools/nitro-sites/manual_sites.txt`: 0x404afb -> 0x433c6b (WndProc focus loss `call ffb_ForcesOff`, read side by side:
  `cmp [0x503e94], 1 / jne / call 0x42a920 / call 0x443610`). `sites_nitro.h` regenerated: 724 rows; the only rows that changed
  are the 9 new ones (column diff against the previous csv, source references aside).
- NITSHELL.DLL: f7 + k3 `1341fee6` built (lab `builds/parity-20261024/nitshell`) and used in the twin; not installed (s.4).

## 3. Tests

Harness (lab `builds\parity-20261024\`): `par-run.ps1` (the stability lane's stab-run.ps1: one boot of the lane's twin
`parity-nitro-20261024` = exp-nitro-owner, private desktop or `-Console`, `.fps-queue` / `.fps-lock` / `.console-owner` honoured, I76_MUTE + the
per-pid mute watcher, I76_SHM_SUFFIX, the twin's DLL put back after), `stab_side.py` (game-state writes from gameplay frames: 7 replay, 2 abort,
0xa exit), `par_side.py` (console: Esc until the menu mode [0x503e94] reads 0x10 and the OS pointer then; focus cycles through the taskbar;
Enter held = weapon fire), `route-trial.ps1` + `pncon.ps1` (the nitro-owner lane's owner-route trial on the twin through PLAY-NITRO-ALL.bat,
with `esc_until.py` for the Esc menu). Preset OWNER-NITRO-ALL as of 2026-10-24 21:30 (before the polish lane's sound keys). Captures:
`captures\parity-20261024\`. The owner's copy was never booted.

| run | build | where | route | result |
|---|---|---|---|---|
| w2-a1 | ee7a36a8 (5b8e97d's code on b2297c9) | private desktop | P01, replay, replay, exit | 0 CRASH, 2 x `new mission - forgot 7`, 3 font-guard skips, process gone after exit |
| w2-a2 | ed812c43 (w3 = 535541b + parity) | private desktop | P05, replay, abort | 0 CRASH, 1 forgot, 2 font skips, process gone |
| w5-a1 | **9e6a2378** (main 2170ae0) | private desktop | P01, replay, replay, exit | 0 CRASH, 2 forgot, 3 font skips, `nitro: 185 sites patched, 0 refused` |
| r5, r6 | ed812c43 | console, PLAY-NITRO-ALL.bat | the owner's route: menus > SCENARIOS > TAURUS > A NEW HOPE > 60 s driving > Esc > Abort Mission > Replay > 60 s > Esc > Abort > Abort > Yes > the form > BAD FUEL > 60 s > Esc > Abort > Exit Game > Yes | both complete: 0 CRASH, 3 font skips, music `track N RESUMED` after each reload, the process gone after Exit Game > Yes; the Esc menu opened at the first press 6 / 6 with the pointer at y 720 |
| r7 | **9e6a2378** | console, PLAY-NITRO-ALL.bat | the same | complete: 0 CRASH, 3 font skips, 2 RESUMED, process gone after Exit; pointer at y 720, 3 / 3 |
| r1, r2 | ed812c43 | console | the same with the original script's double Esc | not valid as route runs: the second Esc closed the menu, so the clicks fell on the 3D view (menus, 3 x 60 s driving only); 0 CRASH |
| w3-ctl2 | ed812c43, `I76_MENU_PTR_CENTRE=0` | console, P01 | Esc menu x 3 | **control: pointer at y 1439 of 1440 when the menu opens, 3 / 3** (the bug on Nitro) |
| w3-ctl1 | ed812c43, `I76_FFB_REACQUIRE=0`, trace | console, P01, T300 attached, stock FFB | 3 focus cycles (taskbar), fire before / after each, replay, exit | **control: `game inactive, forces off`, `DISFFC_STOPALL (game inactive) stopped the playing effects`, and after the return `effects playing 0 of 3 known`** (the owner's lost FFB, on Nitro); 0 CRASH |
| w2-c2, w3-c3 | ee7a36a8 / ed812c43, trace | console, P01, T300 | 3-4 focus cycles, fire, replay(s), exit | **fix: no inactive / STOPALL transition, `effects playing 3 of 3 known` throughout**; 118 weapon-slot effect Starts across the cycles (w2-c2), 0 DirectInput calls failing, 0 NULL-slot skips, 0 CRASH |
| w2-shell1 | ed812c43 | private desktop | menus boot 90 s, NITSHELL f7+k3 (1341fee6) in the twin | 0 CRASH; NITSHELL's MessageBoxA slot hooked |
| w2-gold1, w3-gold2 / gold-ctl-a7ac | ed812c43 / RC a7acc44b (535541b, no parity code) | private desktop, stab-gold-20261024, OWNER-2300-ALL, T01 | replay x 3 | **Gold unchanged: the two logs are line for line the same once numbers are masked (170 lines each)**; both stop at frame 0 in this copy tonight (no frame ever runs, with the control DLL too: an environment change in that copy, not this code; the stability lane's runs there passed at 10:23) |
| laptop npar-* | ee7a36a8 and the owner's e78aedd5 | laptop bench (Win11 26100.9711) | P01 direct boot | **both builds fault at the first frame** in dgVoodoo `DDRAW.dll+0x4AB0A` read 0 (exe frames 0x48ACD7 / 0x492ED4 / 0x49385F), n 2 + 1: Nitro does not start on the laptop with this copy's dgVoodoo set; not this lane's code, not chased. The fault's "Unhandled Exception" box came up **in front, centred, topmost** (`nitro-msgbox: box placed at (856,466) 209x149`): the message-box port working on a real box. winmm-heapfix on nitro.exe there: `not needed` (no split) |

n: the owner's route 3 complete runs (2 on ed812c43, 1 on the installed 9e6a2378) plus 3 headless transition runs (8 mission changes and 2
exits); every one 0 CRASH.

## 4. Installed

`exp-nitro-owner\Interstate 76 Nitro Pack` (no nitro.exe running from it), 2026-10-25 ~00:45:
- `strlkup.dll` **9e6a2378** (`9e6a2378968a1fa19d0c8bbbd66b566b`), built (MSVC, build.ps1) from main **2170ae0**: every commit on main,
  the Nitro MP lane's and the polish lane's included. It replaces the polish lane's 9f220ac3 (built from 8ba6f70, which already carried
  this lane's 5b8e97d), adding ffbfocus.c's exit stand-down (c975f59) and the regenerated site table; kept as `strlkup.dll.9f220ac3`.
- `nitshell.dll` left at **a32ffba6**: the polish lane installed NITSHELL F7 + M2 + K1-K4 at 00:00 and tested it live (its "rename
  variant" item); that is Gold's shipped F7 + K3 and more, so this lane's F7 + K3 build (1341fee6, lab `nitshell\`) was not installed.
- The preset is the polish lane's (sound keys added); the parity switches are all default on and need no key.
- WHAT-THIS-IS.txt has a line for this install.

## 5. Not done / open

- Co-op crash guards from Gold (script NULL-object guard, AcGenral heap guard, host respawn) on Nitro co-op: the Nitro MP lane's call.
- Nitro on the laptop bench faults at the first frame in dgVoodoo DDRAW (s.3), the owner's e78aedd5 too.
- The Gold twin stab-gold-20261024 stops at frame 0 headless tonight with any proxy (s.3).
- Owner's hand check: Esc menu pointer, wheel effects after Alt-Tab and after a Replay, in his own session.
