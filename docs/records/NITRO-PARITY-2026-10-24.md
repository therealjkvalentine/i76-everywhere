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
| **Esc-menu pointer recentre `I76_MENU_PTR_CENTRE` (H)** | escmenu.c, show-pointer 0x44bd38 | **off** (the code stood down on Nitro) | **ported** | Nitro runs the same show-pointer code (0x443688 reads the client height [0x653bb0] and halves it; site map reloc, 18 bytes the same) and the same cursor map on nitro.exe's SetCursorPos, so the pointer lands on the bottom edge the same way. Log: `nitro site show-pointer recentre height: gold 0x44BD38 -> nitro 0x443688, signature ok, patched`, `menu-ptr-centre: on` |
| **Stock FFB focus fix `I76_FFB_REACQUIRE` (keep-on-blur, NULL-slot guard at I7_SFRCE+0x2505, re-acquire)** | ffbfocus.c (FFB lane, Gold only) | **absent** | **ported** | Nitro ships the same I7_SFRCE.DLL (md5 687cc35b) and the same ffb code relocated: ffb_PlayEffect 0x446110 -> 0x42fb00, ForcesOn / Off 0x445b40 / 0x445b60 -> 0x42a900 / 0x42a920, device flag 0x52bbd0 -> 0x523248, effect fn 0x52bbe4 -> 0x5234dc, forces flag 0x4f2330 -> 0x4f2d58, active flag 0x504c1c -> 0x526a6c (read side by side, s.2). The owner's Nitro copy has no interposer, so his T300 runs the stock path, crash included |
| FFB device guard `I76_FFB_GUARD` | strlkproxy.c (LAN preset only on Gold) | absent | ported, same default (off unless set) | the stub's two absolute reads relocated (`nitro stub ffb-guard stub: 2 address(es) relocated`); the no-device +0x2505 fault is also covered by the focus fix's NULL-slot guard, which is default on |
| **DWM ghosting off** (save-screen wedge) | u32x.dll DllMain | **absent** (Nitro has no u32x) | **ported** `I76_NO_GHOSTING` (default 1) | `no-ghosting: on - DisableProcessWindowsGhosting called` |
| **Message boxes in front of the picture** (audit b2) | u32x.dll MessageBoxA | **absent** | **ported** `I76_NITRO_MSGBOX` (default 1), nitro.exe and NITSHELL.DLL slots | the laptop run below: nitro.exe's "Unhandled Exception" box was `placed at (856,466) 209x149, topmost` over the picture |
| Shell F7 (Enter / Space close OK popups) | i76shell file patch | not installed | **installed** (NITSHELL f7+k3) | tools/patch-nitshell-f7.py, NITRO-PORT s.7.3 |
| Shell K3 (Y / N / Esc on yes-no prompts) | i76shell file patch | not installed | **installed** (NITSHELL f7+k3) | patch-nitshell-modals.py `--only K3`; emulation K3 rows OK |
| Shell M1 (vehicle-rejected panel) | i76shell | n/a | n/a | Nitro draws its own frame 0x21 correctly (NITRO-PORT s.8.2) |
| Shell M2, K1, K2, K4 | not in Gold's shipped shell either | - | not installed | emulated only on both exes; kept out so the owner's Nitro shell = Gold's shipped set |
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
- NITSHELL.DLL `f804f50d` -> f7 + k3 `1341fee6` (tools/patch-nitshell-f7.py, patch-nitshell-modals.py --only K3), file patch.

## 3. Tests

(below)
