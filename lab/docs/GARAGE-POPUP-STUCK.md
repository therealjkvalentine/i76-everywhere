# Garage DONE validation popup cannot be dismissed (BACKLOG P1-19)

Static reverse-engineering, 2026-10-03. No game was run and no autotest script was started.
**Live update, same day (section 7):** reproduced. 054fb411 stuck 2 of 2 with the gate at 0, the PUMPS=0 control
closed 4 of 4. H1 is confirmed, and so is the competing explanation (the pencil is frozen; the click still works).
Fix 1 was built as u32x `696577dc`: 6 of 6 closed, sandbox gate passed (row 5 gate-environment failure shared with
054fb411).
Field report (owner, lab sandbox via TEST-FRAMERATE, u32x `054fb411`): in the Build & Repair form, DONE with a
required part missing raises "CAN'T GET VERY FAR WITHOUT AN ENGINE", and then neither mouse nor keyboard dismisses
it. The game stays stuck.

Binaries read: lab `game\i76shell.dll` md5 `fd96f871` (pack lineage: P1-P3 plus the F1 stock bytes restored, USER32
import renamed to `u32x.dll`), the pristine GOG shell `deb41008` (`..\i76-map\shell\bin`, and `game-gogtest\...\app\
i76shell.dll.orig`), and `game-gogtest\...\app\i76shell.dll` `e165f348` (pristine plus the `u32x.dll` import rename
only). **None of the three differs from pristine anywhere in the code discussed below.** The diff was run against
pristine and every changed range lies outside 0x1000b800-0x1000b972, 0x1001fbf0-0x1001fd82 and 0x1001c110-0x1001c1a5.
u32x source: `i76-everywhere\u32x\u32x_full.c` (= the `054fb411` build; the lab `src\u32x.c` is the later a467ceb).
The sandbox runs with `I76_U32X_VPTR` unset: no preset or TEST-FRAMERATE mode sets an `I76_U32X_*` name.

## 1. Verdict

| question | answer | confidence |
|---|---|---|
| which popup | the shell's own **`Modal_ImageOk` 0x1000b800**: a sprite with the text and OK button painted into it, plus a private mouse-only loop. Not a Win32 MessageBox, not `modal_fn`, not `Modal_YesNo` | certain [static] |
| does the OK hit rect match the drawn OK | **yes**: hit x 299..339, y 256..270; drawn button outline x 298..341, y 255..270 (measured from the sprite pixels) | certain [static] |
| keyboard | **no key is read** in that loop (1997 design). Stock has no keyboard way out either | certain [static] |
| why it becomes permanent with u32x | u32x's `pump_keepalive` runs inside the modal (from `GetCursorPos`) and **delivers a `WM_ACTIVATEAPP 0`** to `ShellWindowProc`, which clears the shell's input gate `[0x10043224]`. After that `Mouse_Update` returns at its first instruction, the loop makes **no USER32 call at all**, so nothing ever pumps again, the matching `WM_ACTIVATEAPP 1` is never delivered, and the gate stays 0 for good. Mouse dead, keyboard never read: a dead end | mechanism certain [static]; that it is the owner's case: **medium (~60 %)** |
| stock (no u32x) | the stock loop never calls `PeekMessage`, so a deactivation is not delivered until the popup closes. The gate stays 1 and a click on OK still works after returning to the game. **The permanent lock is ours (u32x), the missing keyboard path is 1997** | high [static] |
| the competing explanation | no frame is presented inside the loop (one `VDriver_Present` before it). If dgVoodoo's emulated cursor only moves when the app presents, the pencil freezes on DONE and the player cannot aim at OK. That would be a dgVoodoo plus 1997 interaction, recoverable by a blind click | open, ~30 %; the live test decides (section 6 step 4) |

## 2. The popup [static]

`Garage_Frame` 0x10003e70, DONE case (0x100044cd): `Sound_Service`, then `Garage_ValidateCar` 0x10007340
(0x100044d8). A zero return means stay in the garage. Every refusal is one call:

```
Modal_ImageOk(image, x0=0x77, y0=0x3d, w=0x2a, h=0x10)      ; cdecl, 5 args
  image 0x15 no engine (0x10007364)   0x16 no suspension   0x17 no brakes   0x18 wheel missing
        0x1b wheel pair mismatch      0x1a second turret   0x1c turret on a non-meshType-1 mount
```

Validation rule for the engine (0x10007340..): row 0 of the garage part rows (`[[0x1005209c]+8]`, entry 0) is NULL,
or its PartRec's file name at `+0x2e` is `"null"` (0x10043ab0).

**There are no string ids.** The message is pixels. `image` is a frame index into shape table **0x24** of
`DATABASE.MW2` (the garage sprite set `[0x100f4f90]`, loaded at 0x1003165c). The frames are `data\out\mw2db\036_0x24_shp\
fNNN.png`, and `f021.png` (0x15) reads "CAN'T GET VERY FAR WITHOUT AN ENGINE" with a boxed OK. Frames 0x15-0x18 are
282x93; 0x19-0x1c are 282x92. The frame size equals the sprite size the code passes, which confirms the index is
0-based.

`Modal_ImageOk` 0x1000b800, in full:

```
1000b844  Display_DrawSprite(sheet [0x100f4f90], image, 179, 194, 282, 93)  ; panel at UI 179..460 x 194..286
1000b88b  Display_BlitBitmap: 282x6 shadow at (185,286); 1000b8dc: 6x92 shadow at (461,200)
1000b8fb  VDriver_Present                                ; the ONLY present
1000b900  loop: Mouse_Update [0x100cc514] ; Mouse_GetLeftClick (= [obj+0x10])
1000b916        cmp eax,1 ; jne 1000b900                 ; only a fresh left press leaves the poll
1000b91b        x' = [obj+0x2c]-179, y' = [obj+0x30]-194
                0x77 < x' < 0xa1  and  0x3d < y' < 0x4d  else back to Mouse_Update (1000b906)
1000b946  Display_RestoreBackgroundRect(179,194,290,110) ; [0x100d21a8] redraw callback if set ; return
```

The hit rect in UI space is **x 299..339, y 256..270** (inclusive). The sprite's OK outline (pixel scan of `f021.png`)
is relative x 119..162, y 61..76, so UI x 298..341, y 255..270. Drawn and hit agree to 1-2 px. **Hit-rect mismatch
ruled out.**

The loop reads no key and calls no `PeekMessage`. It does not call the exe's sound slot or `KeyInput_Poll`, and it
has no timeout. It does not touch `modal_fn` `[0x100d21a4]`, so `shellstate.ps1` keeps showing the garage while the
popup is up.

**Side finding, the "Game Server Not Responding" box (lab `docs\MULTIPLAYER-LOCAL-TEST.md` F2).** That box is
`Modal_Ok` 0x1000b660, a different function: blank panel 0x11 with an empty button outline at UI 296..341 x 255..270,
hit rect x 298..339, y 255..268. Then it draws the string "OK" (0x100442b8) with `Display_DrawText(310, 294, ...)`
(0x1000b6d7), **below** the panel. So "OK drawn near y 300, hit at 255..268" is a 1997 cosmetic bug in `Modal_Ok`
only: the caption sits about 39 px under its own box. `Modal_ImageOk` has the OK inside the art and is not affected.

## 3. The input path, and where it dies [static]

`Mouse_Update` 0x1001fbf0:

```
1001fbf0  mov eax,[0x10043224] ; ... ; je 1001fd7a (return)    <- THE GATE: 0 = return before any USER32 call
1001fc80  [obj+0x40]==0 -> skip the poll (always 1; only the ctor writes it)
1001fc8d  GetCursorPos ; 1001fca3 ScreenToClient(hwnd [0x100f702c])
1001fcad  outside 0..639 / 0..479 -> keep the old position AND the old buttons
1001fcd7  GetAsyncKeyState(1/2/4) -> +0x34/+0x38/+0x3c
1001fcfe  +0x10 = 1 on a left press after a release sample, 2 while held, else 0
```

Only `ShellWindowProc` 0x1001da10 writes the gate: `WM_ACTIVATEAPP` (0x1c) at 0x1001dd60, `[0x10043224] = wParam`.
`WM_ACTIVATEAPP` is a sent/activation-event message. It is delivered only while the thread is inside a message
retrieval call (`PeekMessage`/`GetMessage`/...). `GetCursorPos`, `ScreenToClient` and `GetAsyncKeyState` do not
deliver it.

**Stock.** Inside `Modal_ImageOk` nothing retrieves messages. A deactivation (Alt+Tab, Win key, a click on another
monitor, a toast stealing focus, or DWM's ghost after ~5 s) queues the `WM_ACTIVATEAPP 0`, but the shell does not see
it until the popup closes. The gate stays 1, and the loop keeps polling the global cursor and the async button
state. The player comes back, clicks OK, and it closes. Stock keyboard: no way out, as designed.

**With u32x `054fb411`.** `My_GetCursorPos` (u32x_full.c 1388) calls `pump_keepalive()` (1206) on every call, rate
limited to 25 Hz. That runs `PeekMessageA(..., PM_REMOVE)` over the non-input ranges and dispatches what it finds.
Any such `PeekMessage` also processes incoming sent messages and activation events, so the first pump after a
deactivation runs `ShellWindowProc(WM_ACTIVATEAPP, 0)` and sets the gate to 0. From the next iteration on,
`Mouse_Update` returns at 0x1001fc02. The modal loop is then `Mouse_Update` (2 instructions) plus
`Mouse_GetLeftClick` (`[obj+0x10]`, frozen at its last value, 0) forever: one core at 100 %, zero USER32 calls,
zero pumps. u32x has no hook left in that loop. The reactivation event therefore can never be delivered, whatever
the player does. `DisableProcessWindowsGhosting` (DllMain 1882) removes the ghost but not the stall. Lab
`docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md` §3.2 found the same gate trap on the save screen. That loop recovers because
its own `KeyInput_Poll` keeps peeking. `Modal_ImageOk`, `Modal_Ok`, `Modal_YesNo`, `Modal_CdRetry`,
`Modal_VehicleRejected` and `Modal_OneButton` have no peek of their own, so for them the trap is final.

**What triggers the deactivation in the owner's session is not established.** The u32x paths themselves (VPTR off)
create no window and call no `SetForegroundWindow`. The likeliest trigger is the player: when the first OK click
"did nothing" (section 1, competing explanation, or a miss), they reached for Alt+Tab or the Win key, and from that
moment the popup was final. The live test reads the gate to settle this.

### The other u32x paths asked about (none of them swallows this popup's input) [static]

- **Pointer map.** Shell callers get `get_map()`. With the confined 640x480 corner box (the measured sandbox regime,
  MOUSE doc §9.9 control) the position passes through 1:1, as for DONE itself. There is no modal-specific regime.
  `menu_box_record` / `menu_free_pointer` act only in the exe's Esc menu (`[0x4fe534] == 0x10`). If a deactivation
  releases dgVoodoo's clip, the regime flips to FREE: UI = (x-760)/3, clamped to 0..639. That is still a valid
  in-range value, and it does not by itself stop a click.
- **Clamping** keeps every value inside 0..639/0..479, so `Mouse_Update`'s range check (F4) never freezes the buttons
  under u32x.
- **`dialog_owns_input`** passes raw coordinates only while another top-level window of the game process is
  foreground. None exists here.
- **Quit guard** acts only on a `WM_QUIT` met by the pump. There is none in the garage.
- **Keyboard.** The pump deliberately leaves 0x100-0x108 and 0x200-0x20E in the queue, which is stock-like. Keys
  pressed at the popup stay queued and replay into the garage after it closes. Nothing u32x does can make this loop
  read a key.
- **GetMessage filter.** The shell's modals use none.

## 4. Proposed fix

Two independent changes. Fix 1 removes the dead end that u32x introduced. Fix 2 adds the keyboard exit 1997 never
had, and it re-pumps, so it closes the dead end on its own as well. Neither is built into any install.

### Fix 1 (u32x, root cause): no keep-alive pump inside the shell's modal loops

Restore stock message semantics while a shell modal spins: pump only while `ShellMain`'s own loop is alive. The
shell's main loop calls `PeekMessageA(&m, NULL, 0, 0, PM_REMOVE)` each frame. A modal does not.

```c
/* u32x_full.c / src\u32x.c */
static volatile DWORD g_shell_loop_tick;          /* last unfiltered PeekMessageA from i76shell (ShellMain) */
static int sw_modalpump(void) { static int c = -1; return env_switch("I76_U32X_MODAL_PUMP", &c, 0); }

/* My_PeekMessageA, before the real call: */
    if (lo == 0 && hi == 0 && caller_is_shell(ra))
        g_shell_loop_tick = GetTickCount();

/* My_GetCursorPos and My_GetAsyncKeyState, replace the unconditional pump_keepalive() with: */
    if (!(caller_is_shell(ra) && GetTickCount() - g_shell_loop_tick > 250 && !sw_modalpump()))
        pump_keepalive();
    /* a shell caller whose ShellMain has not peeked for 250 ms is inside a modal loop (Modal_*,
     * ControlConfig capture, EntryForm wait): stock delivers nothing there, and neither do we -
     * a WM_ACTIVATEAPP 0 delivered from here closes the shell's input gate [0x10043224] with no
     * way to reopen it (GARAGE-POPUP-STUCK.md). Ghosting is handled by DisableProcessWindowsGhosting. */
```

(`My_GetAsyncKeyState` needs `const void *ra = _ReturnAddress();`.) The keyboard-filter pump in `My_PeekMessageA`
(the save screen) stays as it is: there the shell's own filtered peek delivers sent messages anyway, as in stock.
The WM_QUIT case of `b0cdf7f` is untouched, because that pump runs in `ShellMain` context, where the main loop has
just peeked. `I76_U32X_MODAL_PUMP=1` brings back today's behaviour for the control run. Cost: during a shell modal,
another process's blocking `SendMessage` to the game window waits until the modal closes. That is exactly stock.

### Fix 2 (shell, F7): Enter / Space close `Modal_ImageOk` (and keep it pumping)

The same shape as F3 (`..\i76-map\shell\FIXES.md`). It calls `KeyInput_Poll` 0x1001c110 each iteration, which runs
`PeekMessageA(WM_KEYFIRST..WM_KEYLAST)` (0x1001d630). That gives a keyboard exit, and because the loop now
retrieves messages independently of the gate, a later `WM_ACTIVATEAPP 1` is delivered and the mouse comes back. Esc
is deliberately **not** an exit (garage rule: Esc must never be needed there). `KeyInput_Poll` consumes the key, so
it would not reach the garage anyway.

Written for the **lab shell `fd96f871`**. Its pack cave occupies 0x10040340..0x10040379, and F7 goes in the free
slack after it. The cave is **position-independent** (`call $+5 / pop`), so it needs no new relocation entry and is
safe if the DLL is rebased.

```
0x1000b916 (file 0xad16)  83 F8 01 75 E5  ->  E9 65 4A 03 00            jmp 0x10040380
0x10040380 (file 0x3f780) 61 bytes, currently 00:
83 F8 01 0F 84 92 B5 FC FF E8 00 00 00 00 58 8B B0 7E C1 08 00 8B CE E8 74 BD FD FF 85 C0 0F 84 5C B5 FC FF
8B 06 83 F8 0D 0F 84 97 B5 FC FF 83 F8 20 0F 84 8E B5 FC FF E9 43 B5 FC FF
  10040380  cmp eax,1 ; je 0x1000b91b            ; unchanged mouse path (hit test)
  10040389  call 0x1004038e ; pop eax            ; eax = 0x1004038e at run time
  1004038f  mov esi,[eax+0x8c17e]                ; = [0x100cc50c], the KeyInput object
  10040395  mov ecx,esi ; call KeyInput_Poll 0x1001c110
  1004039c  test eax,eax ; je 0x1000b900         ; no key -> loop top
  100403a4  mov eax,[esi] ; cmp eax,0x0d ; je 0x1000b946 ; cmp eax,0x20 ; je 0x1000b946   ; Enter / Space -> close
  100403b8  jmp 0x1000b900
header file 0x1c0: .text VirtualSize 40 F3 03 00 -> 00 F4 03 00 (0x3f400 = SizeOfRawData; covers both caves)
```

`esi` is free in the loop (it held the shadow buffer, and the epilogue restores it). `ebp`, `edi` and the stack
bounds the hit test uses are untouched, and the loop pushes nothing, so 0x1000b946 sees the stack it expects. No
relocation lies in the 5 replaced bytes or in the cave. Assembled and disassembled with capstone (bytes above). A
scratch build of lab+F7 gave md5 `b9ad503f637f51504326621566551e77`. It is not installed and **not emulated**:
adapt `..\i76-map\shell\tools\emu_f3.py` before installing. For a pristine-based build, add it to `patch_shell.py`
after F3's 70 bytes (F3 and the pack's P1 claim the same cave start). The same 5-byte hook plus cave applies to
`Modal_Ok` 0x1000b7a2 and the other mouse-only modals (FIXES "Minor defects").

**Recommendation:** Fix 1 first. It is the regression we introduced and covers every modal at once. Add Fix 2 if
the owner wants a keyboard exit. If the live test shows the gate staying 1 while the popup is stuck (competing
explanation), Fix 1 does not apply. The follow-up there is u32x calling `InvalidateRect(game, NULL, FALSE)` at
≤10 Hz while a shell modal spins, so `ShellWindowProc`'s `WM_PAINT` (`VDriver_Present`) re-presents and dgVoodoo
redraws its cursor.

## 5. What is not established

- What deactivated the game in the owner's session, if anything (the gate reading answers it).
- Whether dgVoodoo's emulated cursor moves without an application present under this conf (the shell presents
  through dgVoodoo DirectDraw, `primary->Blt`, WIDESCREEN-2D.md).
- Whether `PeekMessage` with `PM_QS_POSTMESSAGE|PM_QS_PAINT` would skip activation events. That is a reason Fix 1
  gates the whole pump instead of narrowing its flags.
- The daily driver carries the same u32x (`054fb411`, installed by `setup-windows.ps1`), so it should behave the
  same. It was not tested there and must not be.

## 6. Live test plan (about 5 minutes, lab sandbox only, physical console)

Rules: `game\` only (never the daily driver). Check `TerminalServerSession` is False. Confirm `game\u32x.dll` md5
`054fb411` and `game\i76shell.dll` md5 `fd96f871` first. **Never press Esc**: it opens Control Configuration in the
garage, which corrupts `input.map`. Avoid Enter too until the end: keys queue during the popup and replay into the
garage. All coordinates are UI space (`Click-UI` / `garage-ui.ps1 -Click`).

Reader / poker (PowerShell, run from `autotest\saves`). `$d` = shell base - 0x10000000:

```powershell
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class GP {
 [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool i, int p);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
 [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int n, out IntPtr r);
 [DllImport("psapi.dll")] public static extern bool EnumProcessModulesEx(IntPtr h, IntPtr[] m, int cb, out int need, int f);
 [DllImport("psapi.dll")] public static extern int GetModuleBaseNameA(IntPtr h, IntPtr m, StringBuilder s, int n);
}
"@
$p = Get-Process i76 | Where-Object Path -like "*i76-uncap-lab\game\*"; $h = [GP]::OpenProcess(0x438, $false, $p.Id)
$m = New-Object IntPtr[] 512; $n = 0; [void][GP]::EnumProcessModulesEx($h, $m, 4096, [ref]$n, 1)
$base = ($m[0..($n/[IntPtr]::Size-1)] | Where-Object { $s = New-Object Text.StringBuilder 260; [void][GP]::GetModuleBaseNameA($h,$_,$s,260); $s.ToString() -ieq "i76shell.dll" })[0].ToInt64(); $d = $base - 0x10000000
function R([long]$a,[int]$n=4){ $b=New-Object byte[] $n; $r=[IntPtr]::Zero; [void][GP]::ReadProcessMemory($h,[IntPtr]$a,$b,$n,[ref]$r); $b }
function R32([long]$a){ [BitConverter]::ToInt32((R $a),0) }
function S { $mo = R32 (0x100cc514+$d); "gate={0} mouse=({1},{2}) btnL={3} edge={4}" -f (R32 (0x10043224+$d)), (R32 ($mo+0x2c)), (R32 ($mo+0x30)), (R32 ($mo+0x34)), (R32 ($mo+0x10)) }
```

| # | action | expected | settles |
|---|---|---|---|
| 1 | `garage-ui.ps1 -Start save009 -Row 9` (any bookmark that reaches the garage), then `-State` | `screen=0xC00F` garage; then run the reader block; `S` -> `gate=1` | setup (~60 s) |
| 2 | Trigger without the UI: `$rec = R32 ((R32 ((R32 ((R32 (0x1005209c+$d))+8))))) ; (R ($rec+0x2e) 8)` (note the bytes), then `$w=[IntPtr]::Zero; [void][GP]::WriteProcessMemory($h,[IntPtr]($rec+0x2e),[Text.Encoding]::ASCII.GetBytes("null`0"),5,[ref]$w)` and **read it back** (`R ($rec+0x2e) 5` = `6e 75 6c 6c 00`) | the engine row's PartRec file name is "null"; the game is only closed, never saved | deterministic engine-missing state (the owner's UI route works too) |
| 3 | `garage-ui.ps1 -Click 400,460 -Shot popup1` (DONE), then `S` | capture shows "CAN'T GET VERY FAR WITHOUT AN ENGINE" at UI 179..460 x 194..286; `gate=1` | popup up |
| 4 | Without clicking: `MoveTo-UI 150 150` -> `S` -> `-Shot cur150`; `MoveTo-UI 500 350` -> `S` -> `-Shot cur500` (dot-source `..\lib\maplib.ps1`). Owner's eye: does the pencil move on screen? | `mouse=(150,150)` then `(500,350)`: the loop polls. **Pencil frozen in the captures/on screen = competing explanation confirmed** (dgVoodoo cursor needs presents) | H2 |
| 5 | `garage-ui.ps1 -Click 318,262 -Shot after-ok1`, then `S` | popup gone, garage drawn, `gate=1`. Baseline: the hit rect is reachable under u32x | hit rect live |
| 6 | DONE again (`-Click 400,460 -Shot popup2`). Then **Alt+Tab** to the console by hand (or `Start-Process notepad`). Within 1 s: `S` | **u32x: `gate=0`** (the pump delivered WM_ACTIVATEAPP 0 inside the modal) | H1 part 1 |
| 7 | Return to the game by hand (Alt+Tab back, or click the game picture), then `garage-ui.ps1 -Click 318,262 -Shot after-ok2`. Its `Force-Foreground` printing "game window is not pumping" is itself evidence of the trap (`SendMessageTimeout(WM_NULL)` gets no answer); the click still goes out by `SetCursorPos` + `mouse_event`. Wait 3 s, `S` twice, 2 s apart; Task Manager: i76.exe about one core | **u32x: popup still up, `gate=0`, `mouse` frozen at the step-6 value**: the reported dead end, reproduced | H1 part 2 |
| 8 | `garage-ui.ps1 -Close` (WM_CLOSE is not pumped; the script kills after 4 s and restores STRLKUP.DLL) | game gone, lock removed | cleanup |
| 9 | Control, same rate: `$env:U32X_TEST_ENV = "I76_U32X_PUMPS=0"` (leg-b passes `I76_U32X_*` names through), repeat steps 1, 2, 3, 6, 7, then `-Close`; unset the variable | **`gate` stays 1 through the Alt+Tab, and the step-7 click closes the popup** (stock semantics). If it also sticks, H1 is refuted | control |

Read it like this: steps 6-7 stuck with `gate=0`, and the control in step 9 not stuck, means H1 (Fix 1, then
optionally Fix 2). Step 4 with a frozen pencil means the player could not aim. Both can be true; step 4 explains the
first failed click and step 6 explains the permanence. A stuck popup with `gate=1` and a moving `mouse` means
neither: report the capture and the `S` lines. Repeat steps 6-7 once more if time allows (n = 2 before believing
it). After Fix 1 is built: steps 1-3 and 6-7 with the new u32x, expected to behave like the step-9 control.

## 7. Live results (2026-10-03, lab sandbox, physical console)

Script: `autotest\saves\popup-repro.ps1` (steps 1-8 in one run; `-Tag`, `-Trials`, `-SkipCursorProbe`; the control by
`$env:U32X_TEST_ENV`). Runs: `autotest\saves\runs\popup\<ts>-<tag>\` (log.txt + captures). Focus change = a notepad
started and forced to the foreground by the script (the owner's Alt+Tab), closed after 2 s, then `Force-Foreground` on
the game (or, when that is refused because the game does not answer WM_NULL, a click on the picture). The OK click is
aimed through whichever mapping the shell mouse follows. After the first focus change dgVoodoo's clip is released and
the pointer stays in the FREE regime (UI = (x-760)/3), so a UI-coordinate click lands at UI (0,153). A popup is
judged "up" or "gone" from the pixels of its panel against the garage and popup references. `i76shell` `fd96f871`
throughout.

| build / switch | launches | trials | popup closed after the focus change | gate `[shell+0x43224]` while away | shell mouse after |
|---|---|---|---|---|---|
| `054fb411` | 2 | 2, each +1 retry click | **0 of 2** (retry 0 of 2) | **0 from 0.3 s on** | frozen at (0,153); i76 1.02 cores |
| `054fb411` + `I76_U32X_PUMPS=0` (step 9 control) | 2 | 4 valid (+1 invalid: DONE missed, fixed in the script) | **4 of 4** | 1 | follows, (318,262) |
| `696577dc` (Fix 1, below) | 2 | 6 | **6 of 6** | 1 | follows |
| `696577dc` + `I76_U32X_MODAL_PUMP=1` (kill switch) | 1 | 1 (+1 retry) | 0 of 1 | 0 | frozen |

- **Step 5 baseline** (focused, no focus change): the OK click closes the popup on both builds (1 of 1 each). The hit
  rect is live.
- **Step 4, the competing explanation: confirmed as well.** While the popup is up, the shell mouse reads (150,150)
  and then (500,350), so the loop polls. The drawn pencil stays on DONE in both captures (`cur150.png`, `cur500.png`
  of `20261003-121344-u32x-r1`), because nothing presents inside the loop. The player aims blind. A blind click on
  OK still works. Both are true, as section 6 allowed: step 4 explains a first "nothing happens" click, and H1 makes
  it permanent.
- **H1 confirmed**: the u32x pump delivers `WM_ACTIVATEAPP 0` inside the modal (gate 0 within 0.3 s), the gate never
  reopens, and the stock-semantics control keeps the gate at 1 and closes on the click.
- Side observations: with `054fb411` stuck, the game window does not answer WM_NULL and does not get the foreground
  back when the notepad closes (it stays on another window). The control and the fix get the foreground back.
  Inside the modal "pumping=False" is normal for all builds (stock behaviour; ghosting is off).
- The proxy `music-fix\Strlkup.dll` that leg-b installs was being rebuilt by another session during these runs
  (201,728 B at 12:06, 202,752 B later). The proxy does not touch the shell's modal, and the conditions alternated, so
  the comparison holds, but the runs did not all use one proxy binary.
- Doc bug fixed in the script: the section 6 reader names its helper `R`, which is PowerShell's `r` alias
  (`Invoke-History`). The script uses `RdB` / `Rd32`.

**Fix 1 as built** (i76-everywhere `u32x\u32x_full.c`, commit `eadd7bb`; md5 `696577dcc5ed7c2997e6099421e68000`):
`pump_from_poll(ra)` replaces `pump_keepalive()` in `My_GetCursorPos`, `My_GetAsyncKeyState` and `My_GetKeyState`.
A shell caller pumps only when ShellMain's unfiltered `PeekMessageA` ran within 250 ms (timestamp taken in
`My_PeekMessageA`). Kill switch `I76_U32X_MODAL_PUMP=1`. **Not ported to the lab's `src\u32x.c` (a467ceb line).**

**Gate of `696577dc` on the sandbox** (`autotest\runs\gate\20261003-122320`, rows 2-6, plus checks by hand):

| row | result |
|---|---|
| 2 leg-b bookmark route (save006 row 6) | PASS 3 of 3 through B1.10 |
| 3 trip route via `TEST-FRAMERATE -Mode all120` | PASS 2 of 2, 120 fps (heartbeat 120 / exe 119.8, 119.7) |
| 4 save screen | PASS: gate 1 over 10 s idle, mouse follows, SAVE x2, NO writes nothing, YES writes only the scratch, savegame.dir exact and put back |
| 5 Esc-menu Exit (gate, folder conf, global conf hidden) | FAIL **for both builds**: the direct t01 boot stays in the shell ("not in a mission after 90 s", client 640x480). Same-condition control with `054fb411`: identical failure (`runs\gate\20261003-123501`). Rerun with `696577dc`: same (`20261003-123303`). Outside the gate, `test-escmenu -Stage open` reaches mode 0x10 with both builds (tags `ctl-054fb411`, `fix-696577`). A gate-environment problem, not u32x |
| widescreen Esc-menu Exit | PASS: env `I76_ASPECT=3440x1440 I76_U32X_MENU_ASPECT=3440:1440 I76_GLIDE_REFRESH=120`, `dgVoodoo.aspect-wide.conf` swapped in and restored, t01, Esc -> mode 0x10, click at screen (2319,1329) -> 0x1 (`runs\escmenu\wide-696577-*.png`) |
| 6 melee by menus | PASS (60 fps, window responding) |
| S / D | PASS: player state byte-identical, no other top-level file changed |

**Open for the owner:** play the popup by hand on the sandbox (the fix is installed there; `game\u32x.dll.054fb411` is
the previous build). Then decide on promotion to the daily driver (twin gate first). Gate row 5 needs a look at why
the direct t01 boot stays in the shell when the global dgVoodoo.conf is hidden. The blind pencil remains (re-present
from u32x while a shell modal spins, or the shell F7 Enter/Space exit of section 4).
## 8. The "remember to save" reminder (owner report, 2026-10-03 evening)

Owner, daily driver (u32x `696577dc`): "the 'remember to save' dialog freezes everything before mission 3".

**What it is.** Not a Win32 MessageBox and not a string: it is `Modal_ImageOk` 0x1000b800 again, frame **0x20** of
shape table 0x24 (`data\out\mw2db\036_0x24_shp\f032.png`: "REMEMBER, USE THE "SAVE BOOKMARK" BUTTON TO SAVE YOUR
PLACE IN THE TRIP." with a boxed OK). Caller: the inventory/salvage screen fn 0x10018e90 (screen 0xC017), case 0xc
= ACCEPT SALVAGE, at 0x1001933c:

```
if ([[0x100d2180]] == 2 && [[0x100d2164]] == 1 && [0x100d1d90] == 0) { [0x100d1d90] = 1;
    Modal_ImageOk(0x20, 0x77, 0x3d, 0x2a, 0x10); }          ; then screen 0xC00F (garage)
```

So: once per session, on ACCEPT SALVAGE in scene 2 (the trip leg that plays mission 3), before the garage. Same
function, same hit rect (UI x 299..339, y 256..270), same mouse-only loop with no key read and no present as the
P1-19 engine popup. Keyboard never dismisses it in any build (1997 design); the drawn pencil does not move in any
build (no present inside the loop, section 7 step 4), so the screen looks frozen with every u32x build.
A blind click on OK should close it. Never seen by the gate: leg-b's route uses save006 (scene 5) and
popup-repro uses save009 (scene 1); the leg-b route with a scene-2 bookmark (sandbox `save001`, row 1) stops here.

**Does `696577dc` cause the freeze?** Not established. Statically `696577dc` restores stock message semantics in
this loop, the same as in the engine popup where it closed 6 of 6 after a focus change. A live test was prepared
but not run: the daily driver was being played (pid 16780, 19:25 on) for the whole time box, and every lab script
needs the console with no i76 process running. Script: `autotest\saves\reminder-repro.ps1` (leg-b to the
reminder via save001 row 1, state + gate + reminder flag read, pointer probe, optional `-FocusChange`, OK click,
judged by screen 0xC00F; closes only its own pid). Conditions to run, n >= 2 each: `696577dc`; `696577dc`
`-FocusChange`; `U32X_TEST_ENV=I76_U32X_MODAL_PUMP=1`; `u32x.dll.054fb411`.

**Live update (19:49-20:03, the console came free).** `reminder-repro.ps1`, sandbox, save001 row 1, no focus change,
`i76shell fd96f871`, runs `autotest\savesunseminder\<ts>-<tag>\`:

| build | valid launches | reminder up (screen 0xC017, flag 1, gate 1) | OK click | WM_NULL answered inside the modal |
|---|---|---|---|---|
| `696577dc` | 2 (r1, r3) | 2 of 2 | **closed 2 of 2** (r1: first click mis-aimed by the script's pointer map, shell mouse not following; the retry aimed 1:1 and closed; r3: first click) | False (no pump, as designed) |
| `054fb411` | 1 (r3) | 1 of 1 | closed 1 of 1, first click | True |

Three more launches (054 r1, r2; 696 r2) were invalid: leg-b's B1.5 picked row 2 or none instead of row 1 (fixed
with `-RowUy 205`). Gate stayed 1 and the shell mouse followed (150,150)/(500,350) in every valid run. **No
evidence that `696577dc` freezes this dialog** (n = 2 vs 1, no focus change; a focus-change run was not done for
lack of time). The only measured difference is that the window does not answer WM_NULL while the modal is up
(hung by Windows' definition; ghosting is off). What the owner saw is still open: candidates are the frozen pencil
(no present in the loop, every build) plus a missed blind click, or a focus change. Next: `-FocusChange` n >= 2 per
build, and ask the owner whether a click on OK (UI 318,262) was tried. All saves byte-identical after the runs.

## 9. F7 + modal pointer: a moving arrow, Enter / Space close (built and gated 2026-10-03, 20:00-20:35)

Owner's goal: the OK popups show a moving pointer and close with the keyboard. Two pieces, both now built.

**(b) Keyboard: shell patch F7** (`i76-everywhere\tools\patch-shell-f7.py`). Section 4's design, for **both** mouse-only
OK loops: `Modal_ImageOk` (hook 0x1000b916, cave 0x10040380) and `Modal_Ok` (hook 0x1000b79f, cave 0x100403c0, the
"Game Server Not Responding" box; same 5 bytes, same shape, esi free). Each cave is 61 bytes, position-independent,
calls `KeyInput_Poll` and leaves the loop through the function's own close path on Enter (0x0d) or Space (0x20).
Esc (poll code 3) and every other key are consumed and ignored, so an Esc pressed at the popup no longer queues up
for the garage. `.text` VirtualSize 0x3f340 -> 0x3f400. No relocation in any patched range (checked by the
script). The script refuses a file whose bytes at every site are not the expected originals (or exactly F7), and
reads its output back: only the 124 F7 bytes differ.
Callers covered (all `Modal_ImageOk` calls go through the one patched loop): garage 0x10004c06 (image 0x1e),
`Garage_ValidateCar` 0x10007561-0x10007609 (0x15-0x1c), inventory 0x10018e6f (0x21) and 0x1001933c (0x20, the
reminder), 0x10026131 (0x19, own hit rect); `Modal_Ok`: 0x100301ff.
**Emulated** (Unicorn, `patch-shell-f7.py <dll> --emulate`, KeyInput_Poll stubbed): 22 cases (11 per loop: click
-> hit test, no key / held button / Esc / y / n / LF / 0x10d / 0xd20 -> loop top, Enter / Space -> close, stack
balanced), **0 mismatches**; the unpatched shell gives 4 mismatches (the Enter / Space cases), so the emulator tells
the two apart. The daily driver's `i76shell.dll` is md5 `fd96f871`, the same file as the lab's (its text-entry
bytes are already in that lineage), so one output serves both: **`staging\f7\i76shell-driver-F7.dll` md5
`9d6247a61f55836ecdd3c1d9d2025554`** (sha256 `8f2b8fec…aa5f155f`).

**(a) Pointer: u32x modal pointer** (`i76-everywhere\u32x\u32x_full.c`, build **`19ab8dd1`**). While a shell caller
polls `GetCursorPos` outside ShellMain's loop (P1-19's 250 ms rule) and no frame has gone through the present hooks
for 250 ms, the existing vptr cursor window (click-through layered arrow, owned by the game window; it retrieves
and sends no message, so it cannot deliver `WM_ACTIVATEAPP`) is placed at picture origin + scale x the UI point the
shell was just handed. Picture = 4:3 fit of the client, or the whole client when the folder's `dgVoodoo.conf` has
`ScalingMode = stretched` (`I76_U32X_SHELL_FILL=0/1` overrides). Hidden when ShellMain peeks again, when the game
is not foreground, and when the shell stops polling for 300 ms. Kill switch `I76_U32X_MODAL_PTR=0`; stands down
under `I76_U32X_VPTR=1`. The shell's own frozen pencil stays where it was drawn; the arrow is the live pointer.

**P1-19 re-verified with F7.** F7's peek does deliver `WM_ACTIVATEAPP 0` while away: the gate reads **0/0/0** at
0.3 / 1 / 2 s in every focus-change trial. The same peek delivers `WM_ACTIVATEAPP 1` on return: gate **1** at "back"
in every trial, mouse follows, the popup closes. No lock.

**Live** (scripts extended: `popup-repro.ps1 -GameDir -CloseWith click,enter,space`, `reminder-repro.ps1 -CloseWith`,
both read the arrow window's rect via `lib\modalptr.ps1` and take CAPTUREBLT captures `ptr-*.png`):

| folder / conf | run (`autotest\saves\runs\...`) | condition | n | arrow at the mapped shell point | result |
|---|---|---|---|---|---|
| sandbox, folder conf (stretched_ar, 3440x1440) | `popup\20261003-200534-f7ptr-r2` | garage popup focused: probe 150,150 / 500,350, baseline click | 1 | 2 of 2, delta (0,0), moved | click closed |
| same | same | after a focus change: Enter / Space / click | 3 | 3 of 3, (0,0) | **3 of 3 closed** (one each) |
| same | `reminder\20261003-200718-f7rem-enter-fc` | reminder (save001, -RowUy 205), -FocusChange, Enter | 1 | 3 of 3 | closed -> garage 0xC00F, gate 1 |
| same | `reminder\20261003-200812-f7rem-space` | reminder, Space | 1 | 3 of 3 | closed -> garage |
| twin `game-dd-20261003` (driver DLLs + these two) | `popup\20261003-201559-twin-f7ptr` | after a focus change: Space / Enter / click | 3 | 3 of 3, (0,0) | **3 of 3 closed** |
| sandbox, `dgVoodoo.aspect-wide.conf` swapped in, global conf hidden, `I76_U32X_MENU_ASPECT=3440:1440` | `popup\20261003-202508-wide-f7ptr` | probe, baseline click, focus change + Enter / click | 1 launch, 5 probes | 5 of 5, (0,0); the arrow fills 3440 wide (UI 318 -> x 1709 = 318 x 5.375); capture: tip on the drawn OK | 3 of 3 closed |
| sandbox, `I76_U32X_MODAL_PTR=0` (control) | `popup�61003-202707-f7-ptroff-ctl` | probe + focus change + Space | 1 | no arrow window (0 of 3) | closed (F7 alone) |

`I76_ASPECT=3440x1440` was not in effect for the widescreen row: leg-b scrubs every `I76*` variable except
`I76_U32X_*`. It sets the 3D frame, which the shell's 2D popup does not use. The arrow was hidden after every
close. The first launch (`f7ptr-r1`) stopped at the capture helper (a .NET enum bug, fixed); its probe was already
on point.

**Gate** (`autotest\gate-folder.ps1 -Only 2,3,4,6`):

| folder | run | result |
|---|---|---|
| sandbox `game` (u32x `19ab8dd1`, shell `9d6247a6`) | `runs\gate\20261003-200914` | **PASS 14 FAIL 0**: leg-b 3/3 through B1.10, trip 2/2 at 120 fps, save screen (gate 1 over 10 s, NO nothing, YES scratch only, dir exact), melee, saves byte-identical |
| twin `game-dd-20261003` (same two DLLs) | `runs\gate\20261003-201714` | rows 2, 3 (PLAY.bat, 120 fps), 4, 6 and S **PASS**; row D **FAIL: dgVoodoo.conf changed**. Cause: PLAY.bat copies `dgVoodoo.wide.conf` over `dgVoodoo.conf`. The twin's conf (`fd68005a`) had drifted from the driver's. After the gate it is `c310f3f6`, the same as the driver's and as `dgVoodoo.wide.conf`. The twin gates `115416` and `141237` failed row D the same way with the earlier builds. Not caused by these DLLs |

Installed and left in place (gated): sandbox `game\u32x.dll` = `19ab8dd1`, `game\i76shell.dll` = `9d6247a6`
(backups `u32x.dll.696577dc`, `i76shell.dll.fd96f871`); twin `Interstate 76\u32x.dll` / `i76shell.dll` the same
(backups `*.pre-f7-696577dc` / `*.pre-f7-fd96f871`). Not run: Modal_Ok's F7 path live (no multiplayer session;
emulated only), Esc at the popup (never pressed in the garage; emulated), the owner's hands.
