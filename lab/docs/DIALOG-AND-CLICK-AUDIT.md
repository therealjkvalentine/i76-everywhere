# Dialog and click audit: every interactive popup, menu and message box in i76shell.dll and i76.exe

2026-10-03, static work only. **No game was run**: the console was held by the popup agent (`.console-owner` =
`f7-modal-ptr agent`, i76.exe pid 11644 running) for the whole time box. Owner's ask: "find and fix all the menu
clicking stuff through the whole exe... no more stupid stuck dialogs".

Binaries read (python pefile + capstone, linear sweep **and** a byte-pattern scan for `FF 15 [iat]`, because the linear
sweep desyncs on the jump tables in `.text` and missed 20 of 22 `MessageBoxA` sites):

| file | md5 | what it is |
|---|---|---|
| `i76-map\shell\bin\i76shell.dll` | `deb41008` | pristine GOG shell (same as `game-gogtest\...\app\i76shell.dll.orig`) |
| `game-gogtest\...\app\i76shell.dll` | `e165f348` | pristine + USER32 import renamed to `u32x.dll` |
| `game\i76shell.dll.fd96f871` | `fd96f871` | pack lineage (P1-P3, F1 stock bytes restored, u32x rename) |
| `game\i76shell.dll` (live lab, 20:00) | `9d6247a6` | `fd96f871` + **F7** (popup agent: Enter/Space in `Modal_ImageOk` and `Modal_Ok`, caves 0x10040380 / 0x100403c0) |
| `game-gogtest\...\app\i76.exe` | `64165126` | GOG exe, USER32 renamed to `u32x.dll` |
| `game\i76.exe` | `85de44a7` | lab exe; its `MessageBoxA` and the shell's `MessageBoxA`/`DialogBoxParamA` are all imported from `u32x.dll` (plain forwards in `u32x_full.def`) |

Outside the F7 bytes, the lab shell's modal code is identical to pristine (scan diff empty). Art positions come
from shape table 0x24 of `DATABASE.MW2` (`i76-map\data\out\mw2db\036_0x24_shp\fNNN.png`; lab and GOG databases
have identical tables), overlaid with the hit constants (`scratchpad\hit_overlay.png`, reproduced in the rows below).

Scratch tools (session scratchpad, not committed): `scan_shell.py` (callers of every input primitive), `iatscan.py`
(byte scan for IAT calls), `mbctx.py` (strings pushed before each call), `prev.py`.

## 0. Verdicts

1. **Every shell popup with its own loop (`Modal_*`) reads the mouse only, presents once, and never pumps.** That is
   the 1997 design. Under u32x before `696577dc` the keep-alive pump made the focus lock permanent. `696577dc` fixed
   that for all of them at once, because Fix 1 keys on "shell caller outside ShellMain's loop" and not on one function.
   The blind pencil (no present inside the loop) is shared by all six. The popup agent's uncommitted
   `I76_U32X_MODAL_PTR` block in `u32x_full.c` is generic in the same way (it keys on "shell polls outside ShellMain and
   nothing presented for 250 ms"). It should therefore cover `Modal_Ok`, `Modal_YesNo`, `Modal_VehicleRejected` and
   `Modal_CdRetry` too, and the team picker does not need it (it presents every iteration). Live-check that claim.
2. **New 1997 defect, the strongest finding: `Modal_VehicleRejected` draws a frame that does not exist.** It pushes art
   frame **0x22**, but shape table 0x24 has **34 frames (0..0x21)** in Gold's database. `Mcga_DrawRleSprite` 0x1003a8f4
   does no bounds check: entry 34 of the offset table is the first dword of frame 0's data, `0x00ab0087`, so it
   reads the frame header at `table + 0xab0087 + 8`. The MULTIPLAYER-LOCAL-TEST F1 crash is `0xC0000005 at
   I76SHELL+0x3a9a9` (`mov eax,[esi+8]`, the frame-header read), with read address `0x1384583F` and edi = 0xB3. That fits
   exactly a table at `0x12D957B0` [inferred, strong]. The earlier attribution there (to `Modal_Ok`) is therefore
   probably wrong: `Modal_Ok` draws frame 0x11, which exists. When the wild read happens to land in mapped memory, the
   box is drawn empty, and the player sees "a shell modal with hidden text" that cannot be dismissed (the IPX run, the
   ValidateVcf rejection of the modded car). Fixed by M1 below.
3. **The hit rects match the drawn buttons** in every shell modal, within 1-4 px (overlay below). The one real
   mismatch is `Modal_Ok`'s **second "OK" label**: `Display_DrawText(310, 294, "OK")` at 0x1000b6d7 sits under the panel
   (panel bottom y 286), and its button at y 255..270 already carries the art's own OK. That is the "OK drawn at y~300,
   hit at 255..268" of MULTIPLAYER-LOCAL-TEST F2. Fixed by M2.
4. **Win32 boxes: 22 `MessageBoxA` sites in the shell, 4 in the exe, 5 `DialogBoxParamA` sites in the shell.** All the
   reachable shell boxes are owned by the game window (`[0x100f702c]`). In the measured MP case one still opened
   *behind* the fullscreen picture (`#32770` at screen 1515,668), which is effectively a hang. The CD-2 prompt (exe)
   is the one a single-player can meet. Proposal (b2) below. Not built, because `u32x_full.c` carries the popup
   agent's uncommitted work.
5. Built: **`i76-everywhere\tools\patch-shell-modals.py`** (M1, M2, K1-K4), emulated 53/53 on three shell lineages.
   It composes with F7 in either order (same md5 `a300db63...`). **Not installed anywhere.**

## 1. Inventory (ranked: how likely a player meets it x how bad it is)

Columns: **input** (what the loop reads), **redraw** (does the pointer move on screen while it is up), **hit vs drawn**
(UI 640x480 coordinates), **hang** (can it hold the game with no way out), **u32x** (behaviour under our proxy:
focus, mapping in 16:10 `stretched_ar` and 21:9 `stretched`).

| # | surface | where | who meets it | input | redraw | hit vs drawn | hang | u32x / status |
|---|---|---|---|---|---|---|---|---|
| 1 | **`Modal_ImageOk`** 0x1000b800: garage DONE refusals (frames 0x15-0x1c), "REMEMBER... SAVE BOOKMARK" (0x20, ACCEPT SALVAGE scene 2), "CAN'T SALVAGE FROM A DREAM" (0x21, `Inventory_Open` 0x10018e6f), "RENAME VARIANT TO SAVE" (0x1e, `Garage_Frame` 0x10004c06), "MAYBE IN THE NEXT VERSION" (0x19, main menu OTHER) | 10 call sites | **every trip player** (the reminder fires once per session in scene 2) | mouse only (F7 adds Enter/Space) | **no**: 1 present, then the pencil freezes | OK hit 299..339 x 256..270, art OK 298..341 x 255..270: **match** | stock: no keyboard way out; under u32x `054fb411` focus change = permanent | lock fixed `696577dc`; F7 built and installed in the lab by the popup agent; modal pointer in progress (popup agent). **Not mine; do not duplicate** |
| 2 | **`Modal_YesNo`** 0x1000bc40 (Tad's Auto Salvage card): "Overwrite an existing bookmark?" (save x2), garage "Wanna save the new variant?" / "Overwrite the current variant?" x2 / "leave Field Salvage behind" | 9 sites: Garage_Frame x4, GraphicDetail 0x10012e88, PlayOptions 0x100144a2, SaveMenu_Edit 0x10014b33, SaveMenu_Frame 0x10014e33, Inventory 0x100192cf | very common (every overwrite save, every variant edit) | mouse only on the lab lineage (F3, which adds Y/N/Esc, exists only on the pristine `patch_shell.py` line and is not in any install) | no (1 present) | YES hit 255..302 x 116..141 rel (UI 370..417 x 246..271), art YES about 259..305: **4 px left**, harmless; NO matches | stock 2026-08-10 hang (F4 era); now only blind | **K3** (Y = yes, N/Esc = no) |
| 3 | **Save Bookmark** name entry `TextField_Edit` 0x1001c7b0 under `SaveMenu_Edit` 0x100147a0 | menu index 1 | every save | keys + mouse (first click only leaves edit mode; stock) | yes, presents per iteration | regions match (SCREENS.md) | was the ghosting gate trap; recovers (its `KeyInput_Poll` peeks) | ghosting off in u32x; F2 (orphaned slot) still pristine-line only. MOUSE-ESC-MENU section 3 |
| 4 | **Exe in-mission Esc menu** (`shell_BeginInGameMenu` 0x4953e0, `shell_MenuHandleMouse` 0x4972d0, pages Play Options / Graphic Detail / Audio / Abort / Exit, `shell_DialogYes/No` 0x497940/0x497960) | exe mode `[0x4fe534]==0x10` | every player | mouse through WndProc `WM_LBUTTONDOWN/UP` (0x404b1f), **no pointer sprite: the OS arrow**; keys go to the exe key ring (0x49d140); arrow/Enter navigation not traced | OS arrow, always live | page centred in the display RECT, hit in display pixels; the right edge was unreachable in widescreen (H1-H3) | no loop of its own (WinMain keeps pumping) | `I76_U32X_MENU_ASPECT` makes widescreen work (gate: 3440x1440 Exit PASS). **Risk**: 16:10 `stretched_ar` and 21:9 `stretched` need the aspect set to match the conf; a wrong value maps clicks off by up to 1.2x (MOUSE doc 2.5 H2) |
| 5 | **CD-2 prompt** "Please insert CD 'Interstate '76 CD 2'" (exe `MessageBoxA` via helper 0x471580, site 0x471630, `MB_OKCANCEL|MB_ICONEXCLAMATION`, owner = ecx) | `shell_cb_17` 0x470f90 at mission start (also the shell's `Modal_CdRetry` in between, see #11) | rare, transient (`GetVolumeInformationA` failing on the CD drive at start, m12 notes; 6 in ~21 launches once) | Win32 box: Enter/Esc/mouse | Win32 | Win32 | **yes in practice**: the box opens behind the fullscreen picture, so the game "freezes at mission start". OK re-prompts for ever, Cancel exits | proposal **b2** |
| 6 | **Win32 boxes in the shell's network code**: "There are no games to join.", "The game is full.", "Cannot open connection to game", "Could not create player (id)", "This game has closed.", "Network/Game Server not responding", "Could not start game", "Mission file %s not found", version mismatch, "You don't have mission %s!", "mission file does not match the host's", "The host has rejected you... pink boy", "Your request timed out", "Unable to create an IPX/null modem/internet connection...", "Bad Game Server Address '%s'!" | 0x10028d1f, 0x1002e582..0x1003017d (16 sites), 0x10036146, 0x100362e7; all `hWnd = [0x100f702c]` | anyone trying multiplayer | Win32 | Win32 | Win32 | **yes**: measured behind the fullscreen window (MULTIPLAYER-LOCAL-TEST F3) | proposal **b2** |
| 7 | **`Modal_VehicleRejected`** 0x1000b980 (ValidateVcf slot 26 returns 0: host 0x1002f3e0, joiner 0x1002e70a) | net host/join | **every multiplayer attempt with a modded car** (the lab and daily driver carry mods; MULTIPLAYER-CAR-CHECK) | mouse only | no | OK hit 298..340 x 255..269; **art frame 0x22 does not exist** | **crash** (F1 signature) **or** an empty box with an invisible OK | **M1** (draw frame 0x11, the blank OK panel, whose OK sits on this hit rect) + **K1** (Enter/Space) |
| 8 | **`Modal_Ok`** 0x1000b660 "Game Server Not Responding" (only caller `Net_PollMessages` 0x100301ff; text by caller drawer) | net | multiplayer | mouse only (F7 adds Enter/Space) | no | panel OK 296..341 x 255..270 = hit 298..339 x 255..268; **stray second "OK" drawn at (310,294) under the panel** | stock no keyboard; with the stray label, the player clicks the wrong OK | **M2** (drop the stray label); F7 (popup agent) |
| 9 | **"I76 Error" `Shell_ErrorBox`** 0x1000f310 (`MessageBoxA`, `MB_ICONHAND`, owner game window) from `InputMap_Read`: "input mapping error: line %d, read error / unexpected EOF", "input.map error: line %d...", "The device you chosen is not configured properly" | shell start / options | whoever has a damaged `input.map` (Control Configuration in the garage corrupts it: the standing rule) | Win32 | Win32 | Win32 | **yes** if behind the picture: the shell never shows | **b2**; plus the existing rule (never open Control Configuration in the garage) |
| 10 | **CHOOSE A TEAM picker** (`Modal_OneButton` 0x1000bdd0, a misnomer; frame 0x13, 8 team rows + DONE/CANCEL) | `EntryForm_Frame` 0x10028ba4 / 0x10028ca9 | melee/net team games | mouse only | **yes** (presents every iteration) | rows and DONE/CANCEL match; row hit boxes stop at the caption width (`PUCE PANTHERS` and `MR. BROWN'S CLOWNS` are clickable only on the left part), cosmetic | no keyboard; otherwise sound | **K4** (Enter = DONE, Esc = CANCEL) |
| 11 | **`Modal_CdRetry`** 0x1000bad0 "SUGAR, PUT DISC 2 IN NOW" OK/CANCEL (frame 0x14) | `ShellWindowProc` 0x1001e108 between the two `RequireCD2` calls (go = 0xC010) | rare (RequireCD2 normally returns -1 = present) | mouse only | no | OK 76..130, CANCEL 151..208 x 56..73 rel to (179,194): **match** | no keyboard | **K2** (Enter = OK, Esc = CANCEL) |
| 12 | **Control Configuration** key capture (`ControlConfig_CaptureInput` 0x10011710: "Press any key or button..." via `Modal_DrawTextBox`, its own `Mouse_Update` loop, joystick/keys/mouse) | Options index 7 | anyone who opens it | everything (that is its job) | n/a | n/a | it captures Esc too | known to corrupt `input.map` when entered from the garage. **Out of scope by rule** (never opened in tests). Not patched |
| 13 | Net wait boxes "STAND BY... CANCEL" / "WAITING FOR CALL... CANCEL" (frames 0x12 / 0x1f): `EntryForm_RunNetWithWaitThread` 0x100285c0 runs the DirectPlay call on the main thread and `EntryForm_WaitThreadProc` 0x10028560 (`Mouse_Update` + redraw + `Sleep`) on a second thread | net host/join/modem | multiplayer | mouse on a worker thread | yes (the thread redraws) | not measured | the main thread blocks in `WaitForSingleObject`: Windows calls it "not responding" for the whole DirectPlay timeout | not patched; `Force-Foreground` / WM_NULL probes will report hung here (MULTIPLAYER-LOCAL-TEST) |
| 14 | Shell modal_fn popups run inside ShellMain's loop (they pump): garage part pickers `Garage_OpenPartPopup`, repair popup, `Garage_SpecialPopupFrame`, `ScrollList_Frame` / `ScrollListEx_Frame` (net lists), Options / Audio / Graphic / Play Options / Exit / Load / Modem menus, main menu, entry forms | ShellMain | everyone | mouse; menus also Esc (back to Options) | yes | widget tables (SCREENS.md) | no | F4 range freeze is moot under u32x (clamped). `ScrollList_Frame` autorepeat reads the physical left button (`GetAsyncKeyState`), so it ignores swapped buttons |
| 15 | Exe start-up boxes: "not enough memory... 50MB" (0x40384e, 0x404ddf), "I'76 Gold Init_Graphic_System" (0x471630 helper), "Failed to initialize 3D hardware acceleration / Running software emulation mode" (0x476110) | exe init | rare | Win32 | Win32 | Win32 | before the picture exists, so normally in front | b2 covers them anyway |
| 16 | Unreachable leftovers: MechWarrior 2 dialogs (`0x1003fcf0`: "Terminate MechWarrior?", "Delete this 'Mech?"..., via `Shell_MessageDialog` 0x1000e930 = `DialogBoxParamA` or `MessageBoxA` 0x1003fe25), four `DialogBoxParamA` text dialogs 0x1001ca60/0x1001cae0/0x1001cb60/0x1001cbe0 (`TextDialog_Proc`), `Debug_Printf` "DEBUG Message" box 0x10008add (called from 0x10021fd2), "MechWarrior2 Message" 0x10021f9b, `HeapCreate` failure box 0x1001e365, "You must play trip 3 before trip 4" 0x1001e64c (trip4.spc) | - | none found (no rel32/imm32/4-byte reference to 0x1003fcf0 or the four text-dialog entry points) except the last three, which are edge cases | Win32 | - | - | - | listed for completeness; trip-4 box is covered by b2 |

### Hit rects against the art (frame pixels, relative to the sprite origin; open intervals made inclusive)

| frame (table 0x24) | modal | hit rect | drawn button | verdict |
|---|---|---|---|---|
| 0x11 blank OK panel | Modal_Ok | x 119..160, y 61..74 | OK box about 118..162 x 60..76 | match; **plus the stray label at UI (310,294)** |
| 0x15-0x1c, 0x1e, 0x20, 0x21 | Modal_ImageOk | x 120..160, y 62..76 | 119..162 x 61..76 | match |
| 0x22 (absent) | Modal_VehicleRejected | x 119..161, y 61..75 | **no such frame** (n = 34) | defect, M1 |
| 0x14 | Modal_CdRetry | OK 76..130, CANCEL 151..208, y 56..73 | about OK 73..132, CANCEL 150..209 x 55..74 | match |
| 0x0b | Modal_YesNo at (115,130) | YES 255..302, NO 314..356, y 116..141 | YES about 259..305, NO 313..357 | YES 4 px left, fine |
| 0x13 | team picker at (191,y) | rows x 38..(caption end), DONE 91..161, CANCEL 170..240, y 287..302 | about DONE 90..161, CANCEL 169..240 | match (rows are caption-wide only) |

## 2. Fixes

### (a) Shell byte patches: built, `i76-everywhere\tools\patch-shell-modals.py`

| id | patch | bytes | why |
|---|---|---|---|
| M1 | `Modal_VehicleRejected` art 0x22 -> 0x11 | `6A 22` -> `6A 11` at 0x1000b9a0 (file 0xada0) | stops the out-of-range sprite read (crash or empty box); the blank OK panel's button lies on the hit rect. It no longer says *why* (the art never existed in Gold); the reason is in MULTIPLAYER-CAR-CHECK |
| M2 | `Modal_Ok`: drop the stray "OK" label | `E8 D4 DE 02 00` -> `83 C4 14 90 90` at 0x1000b6d7 (file 0xaad7) | `Display_DrawText` is `ret 0x14`; `add esp,0x14` keeps the stack (emulated) |
| K1 | `Modal_VehicleRejected`: Enter/Space close | hook 0x1000ba6d -> cave 0x10038630 | as F7 |
| K2 | `Modal_CdRetry`: Enter = OK (1), Esc = CANCEL (0) | hook 0x1000bbbb -> cave 0x10038670 | |
| K3 | `Modal_YesNo`: Y = YES, N/Esc = NO (F3's keys; Enter is deliberately not yes) | hook 0x1000bd51 -> cave 0x100386b0 | skipped automatically on a file that already has F3 |
| K4 | team picker: Enter = DONE, Esc = CANCEL | hook 0x1000bfcb -> cave 0x10038710 | |

Each K cave: `cmp eax,1 / je HIT` (the mouse path, unchanged), `call $+5 / pop eax / mov esi,[eax+disp]` (the KeyInput
object `[0x100cc50c]`, position-independent), `call KeyInput_Poll`, `test / je TOP`, `cmp eax,3 / je ESC` (Esc), then
`mov eax,[esi]` and the key compares, else `jmp TOP`. `esi` is free at each loop top: it is reloaded on the hit
path, set by the exit paths, and popped in the epilogue. The caves sit in `VDriver_UnusedMethod` 0x10038630 (0x1a0
bytes, the rest `int3`). That function is dead: no call or rel32/imm32 reaches it, and no 4-byte value equal to it
exists in any of the four shells. Its 10 base relocations are neutralised (type 0). Because F4 uses the same
cave, the script and F4 exclude each other, and F4 conflicts with u32x anyway. The script fails closed on an F4 build
(tested: `i76shell-F2F3F4F6.dll` -> refused, nothing written).

Verification [emulated, offline]:

```
python tools\patch-shell-modals.py <in> <out> --emulate
  lab 9d6247a6 (fd96f871 + F7)  -> out a300db638b7da4bf530498035d4b57d6, 454 bytes differ, emulation n=53 mismatches=0
  fd96f871                      -> emulation n=53 mismatches=0; then patch-shell-f7.py -> a300db63 (same file: order-independent)
  pristine deb41008             -> emulation n=53 mismatches=0
  re-run on its own output      -> "nothing to do"; --check reports M1 M2 K1-K4 present
  pefile: 0 live relocations left in 0x10038630..0x100387cf
```

The 53 cases per file cover: a fresh click goes to the hit test; a held button and no key go to the loop top; Esc goes
to the Esc target or the top; Enter/Space/y/Y/n/x/LF go to their targets or the top; a key with a modifier byte
(0x10d, 0x0d79) goes to the top; the stack stays balanced; and for M2, esp after the replaced call equals `ret 0x14`.
**Not live-tested.** The console was never free.

### (b) u32x-side generic fixes: proposals only (`u32x_full.c` has the popup agent's uncommitted modal-pointer block)

- **b1 pointer during any shell modal**: in progress by the popup agent (`I76_U32X_MODAL_PTR`). Its trigger is
  generic, so it should cover rows 2, 7, 8 and 11 as well as `Modal_ImageOk`. The gate should add one `Modal_YesNo` case:
  the save-overwrite prompt is the most common modal. No separate work is proposed.
- **b2 Win32 message boxes in front, on the picture, with a pointer.** `MessageBoxA` and `DialogBoxParamA` are plain
  forwards in `u32x_full.def` today, and both modules import them from u32x. Proposed: make them real exports.
  ```c
  int WINAPI My_MessageBoxA(HWND h, LPCSTR t, LPCSTR c, UINT f)   /* I76_U32X_MSGBOX=0 -> plain forward */
  {
      /* 1. release the engine's clip and make the OS arrow visible (the exe hid it; the shell shows the pencil) */
      ClipCursor(NULL); while (ShowCursor(TRUE) < 0) {}
      /* 2. topmost + foreground so it is not behind dgVoodoo's fullscreen picture */
      f |= MB_TOPMOST | MB_SETFOREGROUND;
      /* 3. a CBT hook (WH_CBT, this thread, HCBT_ACTIVATE) centres the #32770 on the game window's monitor work
       *    area, the way the measured MP box at (1515,668) on a 3440x1440 screen was not */
      int r = MessageBoxA(h, t, c, f);
      /* 4. restore: the next mouse_Poll reclips (exe mode 1) / ShowCursor balance back; force-foreground the game */
      return r;
  }
  ```
  The same applies to `DialogBoxParamA` (the CBT hook can also set `HWND_TOPMOST` on the dialog). The CD-2 prompt,
  "I76 Error" and the network errors then become answerable. Risk: one more export, and a hook during a modal.
  **Gate:** a forced CD-2 prompt (sandbox: hide the drive label scan) and one network error at 3440x1440 and at
  16:10, each n >= 2; after the box closes, the sim mouse/steering must still work (reclip on mode 1).
- **b3 keyboard for the boxes the shell cannot fix**: none needed. Win32 boxes already take Enter/Esc once they are in
  front (b2).
- **b4** `dialog_owns_input()` stays as it is. With b2 the box is a top-level window of the game process, so the raw
  coordinate pass-through already applies to it.

### (c) Needs the exe

- The in-mission Esc menu keyboard path is not traced (keys go to the ring at 0x49d140; whether arrows/Enter drive
  `[0x654a20]` was not established). If the owner wants keyboard there, that is an exe patch. The widescreen mouse is
  handled by `I76_U32X_MENU_ASPECT`.
- The CD-2 prompt loop itself ("OK re-prompts for ever") is exe code (0x470f90). b2 makes it visible. Making a failed
  scan fall through (as the GOG build effectively always does) would be an exe patch at the scan fallback 0x47109c.
  It is not proposed while the m12 cause is open.

## 3. Gates before promotion (nothing here is installed)

| fix | gate (lab sandbox `game\`, console lock, saves byte-identical, never Esc in the garage, never Control Configuration) |
|---|---|
| M2 + F7 on `Modal_Ok` | needs a multiplayer route to "Game Server Not Responding" (MULTIPLAYER-LOCAL-TEST A: HOST > INTERNET > LOCAL, wait > 40 s); check the label is gone, the box closes by click on 318,262 and by Enter. n >= 2 |
| M1 + K1 | IPX host with the lab's modded car (rejected by ValidateVcf): the box must draw the plain panel (no crash in `mciproxy.log`), then close by click and by Enter. n >= 2, plus the same with the stock car (no box) as control |
| K3 | the save-overwrite prompt (`garage-ui` / save scripts): N closes as NO (nothing written), Y saves to the chosen slot (scratch save only), a click still works. **Highest value, easiest route**: do it first. Also the garage "Overwrite the current variant?" by Y/N |
| K4 | auto-melee entry form, team field: Enter keeps the team, Esc cancels, the click still works |
| K2 | only reachable with RequireCD2 failing; emulation only unless the owner wants a forced route |
| all | leg-b bookmark route + trip route (`option6-trip-test`) with the patched shell, because DONE runs through `Modal_ImageOk` / `Modal_YesNo` (memory: test the owner's route before installing). Then the twin `game-dd-20261003` (not touched here) before the daily driver |

Installing: `python tools\patch-shell-modals.py game\i76shell.dll game\i76shell.dll.modals` (on the lab file that
already has F7), keep `game\i76shell.dll` as `i76shell.dll.9d6247a6`, then swap. Restoring is a copy back.
