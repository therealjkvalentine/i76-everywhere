# Tests that need a running game

Static analysis stops here. Each test states what it settles, a falsifiable prediction, and the exact procedure.
**Run order and machine rules** (AGENTS.md): only on the test copy `C:\Users\james\i76-uncap-lab\game`, never the
daily driver. Physical console, not RDP (check `TerminalServerSession` first). Silent instance. The main session owns
the console and decides when a sitting happens. Reads use the DLL base: `delta = base(i76shell.dll) − 0x10000000`.

Reader used by every test (PowerShell, PROCESS_VM_READ | PROCESS_QUERY_INFORMATION), in `tools\shellstate.ps1`:
it prints `screen=[0x100d2168] screen_fn=[0x100d219c] menu_fn=[0x100d21a0] modal_fn=[0x100d21a4]
mouse=([[0x100cc514]+0x2c],[+0x30]) btnL=[+0x34] pending=[0x100d21ac] next=[0x100d2194] lastwidget=[0x10055d90]`
twice a second, with names from SCREENS.md.

## T1: the screen-state globals (settles SCREENS.md; promotes the navigation globals to `supported`)

Setup: pristine shell (`deb41008`, the lab copy already has the stock bytes after F1) plus the lab's normal layers.
Run `shellstate.ps1` while navigating by hand: title → main menu → Options → Load Bookmark → Esc → Options → Done →
TRIP → garage → Options → Save Bookmark → Cancel.

Prediction (each line falsifiable):
- main menu: `screen=0xC00E screen_fn=0x10025a50 menu_fn=0`
- Options from the main menu: `menu_fn=0x1000e6b0` and the drawn items match table 0x10044990 (no Save Bookmark)
- Load Bookmark: `menu_fn=0x10013060`; Esc returns `menu_fn=0x1000e6b0` via `pending=1,next=0`
- garage: `screen=0xC00F screen_fn=0x10003e70`; Options there shows Save Bookmark (table 0x10044780) because
  `[[0x100c5ad8]+0x20]==2`
- Save Bookmark open: `menu_fn=0` while the name field is active (the edit runs inside the constructor), then
  `menu_fn=0x10014cd0` after the first click outside the list
- every value is `0` or one listed in SCREENS.md; any other value falsifies the table.
- main-menu labels: on the title screen, dump the button list `[0x100d3e7c]` (id, x0..x1, y0..y1) at each sub-menu
  level and note which caption each rectangle covers. Prediction: the rectangles and labels in SCREENS.md's main-menu table (decoded statically from
  the sprites), e.g. TRIP at (167,286) 100×50 and, after it, NEW TRIP at (150,340) 70×22.

## T2: F4 + F6, mouse mapping in a large window (settles FIXES F4)

Build: `python tools\patch_shell.py --fixes F4,F6 --out patched\i76shell-F4F6.dll`. Install on the lab copy only,
**without u32x** (restore the shell's `USER32.dll` import; F4 and u32x are exclusive). dgVoodoo `CaptureMouse=false`,
fullscreen 3440×1440 keep-aspect.

Prediction:
- holding the right button shows "(x,y)" at top right; with the pointer on the rendered "Play Options" caption it reads
  x∈[202,300], y∈[119,140]; at the physical screen's left black bar it reads nothing new (rejected);
- `mouse` in `shellstate.ps1` equals the on-screen readout;
- clicks land where things are drawn: Options → Save Bookmark → YES/NO work at their visual positions.
- Control: the stock shell under the same config shows the readout only while the pointer is inside the physical
  top-left 640×480 (F6 alone makes that visible).

## T3: F2, the orphaned bookmark (settles SAVE.md §4)

Setup: lab copy, **back up `savegame.dir` and `save*.cmp` first**. Stock shell (control) first, then F2.
Procedure, exactly (this is the trigger sequence):
1. Load any bookmark → garage → Options → Save Bookmark.
2. Type `ORPHANA`. Click once on empty paper to the right of the list (not a row, not a button).
3. Click the name field. Type `ORPHANB`. Click SAVE.
4. Game closed: list the folder and parse `savegame.dir` (`4 + 60n`; name at +4, file at +0x24).

Prediction, stock: a new record named `ORPHANB` whose file field is `saveS` (S = previous max + 1), **no `saveS.cmp`**, and
a new **`save-001.cmp`** (Windows `wsprintfA`; `save-01.cmp` only under Wine). After restart, the bookmark is missing from
the load list (the reader drops it, 0x100330b9). With F2: `saveS.cmp` exists and the bookmark loads. If stock does not
produce the orphan, the §4 trace is wrong at step 1 or 2 (check `lastwidget`/`menu_fn` in the reader).

## T4: F3, keyboard answers to the overwrite prompt

Build `--fixes F3`. Options → Save Bookmark → click an existing row → SAVE → the prompt appears.
Prediction: `N` or Esc returns to the edit screen with nothing written (the `.cmp` mtime is unchanged). `Y` overwrites (mtime changes),
and Enter does nothing. Stock control: keys do nothing. Then the modal-lock case: with the stock mouse (no u32x/F4, large
window) the prompt cannot be clicked; with F3 alone, `N` still escapes. That is the recovery the 2026-08-10 freeze lacked.

## T5: `savegame.dir` is never truncated (settles the AGENTS.md invariant)

Procedure: disable the launcher's re-pad guard for one run on the lab copy (keep a copy of `savegame.dir`), make one
save, and compare sizes before and after. Prediction: after = 4 + 60·count exactly, and the last record's scene field is
nonzero and correct. That falsifies "each save leaves it 36 short" in the live game (static proof: writer 0x10032f80;
15 on-disk files, SAVE.md §1).

## T6: what the pack shell changed (DONE statically, 2026-09-26)

Decoded, not a live test: FIXES.md "Pack diff" (P1 cursor caching, P2 GDI blit check, P3 palette toggle, P4 ToAscii).
Only P4 is harmful. A live check that P1–P3 change nothing visible under Glide: none needed, since P2 and P3 are
GDI-only and P1 only changes when the cursors load.

## T7: Control Configuration and input.map (settles INPUTMAP.md)

Lab copy only; back up `input.map` first. (a) Open Options → Control Configuration, press **Esc**. Prediction: `input.map`
is byte-identical (no write, 0x1000f05f). (b) Open it again and press **Done** without changing anything. Prediction:
the file is rewritten. `steer`/`throttle` survive only if the joystick branch loaded them, and the `joystick1` tokens
become the last-enumerated joystick's name; `input.def` is appended; other extra lines vanish. (c) Set `input.map`
read-only and press Done. Prediction: no change on disk, and no crash if the handle is null-checked after 0x1000fd47
(if not, this is a crash; record it). (d) With a copy whose `steer` block starts with a keyboard line, open the menu.
Prediction per INPUTMAP.md "Possible crash": fault on open.
