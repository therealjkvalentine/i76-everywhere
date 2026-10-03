# Rebuilding the menu system: design study and recommendation

*Written 2026-10-02 from the repo docs, the i76-map shell track and read-only decodes of the pristine sandbox files.
No game was run, no existing file was edited. Every statement is tagged: **[fact: source]** = read from code, a
binary, a log or a prior live run (with where); **[inferred]** = derived from facts, not observed; **[proposed]** =
design, not built; **[open]** = a live test or a trace decides it. Shell addresses are VAs of the pristine
`i76shell.dll` (md5 `deb41008`) at its preferred base 0x10000000 (the DLL relocates: add the live delta). Exe
addresses are the pristine `i76.exe` `9a232dcc`. Effort: S = under a sitting, M = one to three sittings, L = one to
three weeks of sittings, XL = months.*

The owner's question: *"what if we wanted to rebuild the menu system so it didn't suck anymore, with pointer
confusion and stuff, and we could AI-upscale the graphics and fonts?"*

**Short answer.** Do not replace the shell. Put one layer between the shell and the screen that owns the three things
that suck (where the pointer is, how the 640x480 picture reaches the monitor, what art and fonts are drawn) and leave
the 721 functions of garage, inventory, save and network logic running exactly as shipped. The shell draws
everything through about ten `Display_*` primitives and presents through one call, so that layer is narrow. The
recommendation and the staged plan are in section 6; the first milestone is section 7.

## 1. What the shell does today

### 1.1 Who owns which menu [fact]

| menu | binary | anchors |
|---|---|---|
| title, main menu, mission grid, garage, inventory/salvage, parts catalogue, melee/net entry forms, standings, post-mission, the notepad menus (Options, Play Options, Graphic Detail, Audio, Control Configuration, Save/Load Bookmark, Exit, Credits, Modem) | `i76shell.dll`: 2 exports (`ShellMain` 0x1001e260, `ShellWindowProc` 0x1001da10), 721 Ghidra functions, 606 named | i76-map `shell\SCREENS.md`, `shell\README.md` |
| the **in-mission** Esc menu (Abort, Load Bookmark, Play Options, Graphic Detail, Audio, Exit) and the mission-over menu (Replay / Reconfigure / Abort / Exit) | `i76.exe` | `shell_BeginInGameMenu` 0x4953e0, draw 0x496870, keys 0x496e10, mouse `shell_MenuHandleMouse` 0x4972d0, mission-over 0x497760; pages `plyopt1.map`, `grxdet1.map`, `audcon1.map`, `extgme1.map`; GDI DIB with Arial Bold blitted into the 3D frame, **no pointer sprite of its own** (uncap-lab `docs\MOUSE-ESC-MENU-AND-SAVE-SCREEN.md` §2.2) |

A rebuild that only touches the DLL leaves the Esc menu as it is. Any pointer fix has to cover both binaries; today
that is what `u32x.dll` does (it is the USER32 import of both: `deploy-shellfix.ps1`).

### 1.2 Screens (private messages 0xC008..0xC026) [fact: `shell\SCREENS.md`, `shell\CALLBACKS.md`, `shell\SAVE.md`, `shell\work\cmp-layout.md`, `subsystems\mission.md`]

| screen | msg / ctor / frame fn | background (DATABASE.MW2 item) | reads | writes |
|---|---|---|---|---|
| Main menu (TRIP, MELEE, OPTIONS, EXIT and sub-menus) | 0xC00E / 0x10025980 / `MainMenu_Frame` 0x10025a50 | 0x1a; buttons = sprite set 0x3e | `I76PLYR.DEF` (`PlayerDef_Load` 0x10016f70) | pending-menu globals `0x100d2194`/`0x100d21ac`; `0x100d217c` |
| New trip | 0xC022 / `Screen_NewTrip` 0x10016b50 | none | `vppt01.vcf` (cb 05), parts catalogue (cb 00) | `addon\vehscn.vcf` / `.vsf`, scene `*arg7` |
| Load a bookmark | 0xC01D / `Screen_LoadBookmark` 0x10013380 | none | `savegame.dir` (`dir_Load` 0x10033020), `saveNNN.cmp` (`Cmp_Read` 0x10032bf0) | GarageRec array `0x100581a0`, inventory ring `0x100cc500`, play mode `[arg12+0x20]=2`, then `vehscn.vcf/.vsf` via `Vehicle_WriteVcf` 0x10035250 / `Vehicle_WriteVehState` 0x10035930 (cb 08, 09, 02) |
| Load Bookmark menu | index 11 / 0x10012fe0 / `LoadMenu_Frame` 0x10013060 | 0xc | `savegame.dir` | posts 0xC01D |
| Save Bookmark menu | index 1 / `SaveMenu_Open` 0x100145f0, `SaveMenu_Edit` 0x100147a0, `SaveMenu_Frame` 0x10014cd0 | 0xb | `savegame.dir`, scene `*0x100d2180`, `*arg11` | `savegame.dir` (`dir_WriteAndSave` 0x10032f80; `4 + 60n`), `saveNNN.cmp` (`Cmp_Write` 0x10032980; `0x8c4 + 8 + 0x74*(nA+nC)`) |
| Enter Reconfig / trip garage | 0xC01E / `Screen_EnterReconfig` 0x10002750 | none | `reconfig.spc`, `vehscn.vcf`, `vehscn.vsf` (cb 05, 06) | posts 0xC00F |
| **Garage: BUILD AND REPAIR FORM** | 0xC00F / `Garage_Open` 0x10003ac0 / `Garage_Frame` 0x10003e70 (4,992 bytes) plus about 60 `Garage_*` functions (pickers, repair queue, allocation, `Garage_ValidateCar` 0x10007340) | 0x01 | GarageRec, inventory ring, repair list `0x100520a0`, parts catalogue `0x100c6288` | `reconfig.spc` (and `trip4.spc` on scene 3), `vehscn.vcf` / `.vsf` on DONE, chassis/variant `.vcf` (cb 03); DONE posts 0xC01C |
| Inventory + field salvage | 0xC017 / `Inventory_Open` 0x10018ae0 / `Inventory_Frame` 0x10018e90 | 0x03 | ring + part-pool list `0x100f5308`; `Inventory_ClassifyParts` (11-weapon cap) | PartNode state (1 mounted, 2 van, 3 repair queue, 4 dropped/salvage) |
| Parts catalogue | 0xC01F / 0x100258f0 / 0x10025910 | 0x04 | catalogue from cb 00 | none |
| Post-mission ("salvage and repair is not available", "you are unconscious") | 0xC015 / `PostMission_Open` 0x10023fc0 / `PostMission_Frame` 0x100246e0 | 0x1d / 0x1f | `vehscn.vsf` written by the exe at mission success, `*arg11` (outcome) | working car, `0x5dcea9` car file |
| Mission grid (trip 1..17, melee scenarios, MP areas) | 0xC020 / `MissionGrid_Open` 0x1001f3e0 / 0x1001f480 | 0x0e | cb 22 world names | mission into setup block `arg10+0x5d` |
| Melee car select | 0xC00D / 0x10023b60 / 0x10023c20 | 0x1b | stock cars (cb 05) | car file `0x5dcea9` |
| Melee / net entry forms | 0xC021, 0xC024, 0xC026 / `EntryForm_Open` 0x10027f20 / `EntryForm_Frame` 0x10028610 | 0x12..0x19 | `i76car.def`, `I76UVEH.def`, `internet.lst`, anet (`anetdll.dll`, 18 `dp*` imports) | play mode 3/4/5, mission (`m01.msn`.., `s03.msn`..), setup block +0xe player, +0x2e car, net rules (cb 25, 26) |
| Standings | 0xC025 / 0x1003f830 / 0x1003f980 | 0x1c | `NSCR.DAT` | none |
| Options and children (Play Options, Graphic Detail, Audio, Control Configuration, Exit, Credits, Modem) | menu index 0, 4, 5, 6, 7, 2, 9, 3 | 6, 0xa, 9, 7, 0x10, 8, 0xd, 0x20 | `I76PLYR.DEF`, `input.map` (`InputMap_Read` 0x1000f390) | options block via the exe (`I76PLYR.DEF` is written by the exe, `player_SaveDef` 0x497290), `input.map` (`InputMap_Write` 0x1000fd30), volumes via cb 14..16 |
| Start the mission | 0xC01C -> 0xC010 (inline 0x1001e0e9) | none | cb 17 `RequireCD2` | `PostQuitMessage(0xC001)`; ShellMain returns 3 |

"Which screen is up" for any tool: `0x100d2168` (screen msg), `0x100d219c` (screen fn), `0x100d21a0` (menu fn),
`0x100d21a4` (modal fn); the UI-space mouse is `[[0x100cc514]+0x2c/+0x30]` [fact: SCREENS.md; reader
`shell\tools\shellstate.ps1`].

### 1.3 The contract between exe and shell [fact: `shell\CALLBACKS.md`, `shell\work\exe-callbacks.md`, `subsystems\mission.md`]

- **Entry.** WinMain -> `shell_RunAndGetChoice` 0x4022e0 (single call site 0x4031f5) sets game state `0x4c2164 = 6`
  and calls `ShellMain(13 args)`: 1 HMODULE, 5 main HWND, **6 the exe's DirectDraw block `0x643920` (or 0 with
  `-gdi`)**, 7 `&0x4c2160` trip scene, 9 the 27-slot callback table, 10 the 0x230-byte setup block (mission file at
  +0x5d), 11 the previous game state (the outcome: 1 won, 2 aborted, 8 reconfigure, 9 load bookmark, 5 first boot),
  12 `&0x5dce80` player block (+0x20 play mode = exe `0x5dcea0`, +0x29 car file = exe `0x5dcea9`, +0x38 current
  vehicle index), 13 the video-mode table `0x4f9e08`. While the state is 6 the exe's WndProc forwards every message
  except 0x432 to `ShellWindowProc`.
- **Loop.** `ShellMain` is one loop: cb 10 (sound service), `PeekMessageA`, then `modal_fn ?: menu_fn ?: screen_fn`,
  then present. Its **only exit is WM_QUIT** (wParam 0xC001 = play, else quit) [fact: uncap-lab MOUSE doc §8.2].
  Modal loops (`TextField_Edit` 0x1001c7b0, `Modal_YesNo` 0x1000bc40 and four siblings) run nested, pump keyboard
  only or nothing, and are the origin of the ghosting and freeze history.
- **Exit.** Return 3 = play, 0xff = quit; play mode at `[arg12+0x20]`: 2 trip, 3 auto melee, 4 scenario, 5 network.
  The exe copies the car file `0x5dcea9` to `0x5dd370` for modes 2/3/4 and the mission from the setup block to
  `0x5049f0`. A won trip mission increments the scene in the DLL (0x1001eafc) and names the next `t%2.2d.msn`.
- **The 27 callbacks** (23 used, 92 call sites): parts catalogue (00), vcf into garage (05), vehicle-state read /
  create (06, 07), **vcf and vsf writers (08, 09)**, file registration (02), save variant (03), sound (10..13),
  volumes (14..16), CD2 check (17), detail preset (18), CD music (20, 21), world name (22), net rules and anti-cheat
  (25, 26).
- **Mission end, exe side.** On a plain trip success the exe adds `<mission>.fsi` salvage, prunes it, and writes
  `ADDON\vehscn.vsf` (VCST, WLST, WPST, SALV) before returning to the shell with arg 11 = 1. A cheated win (0xb)
  gets none of that. The exe has no campaign file: the scene lives in exe memory and the DLL persists it in
  `savegame.dir` / `.cmp`.
- **Direct boot already exists.** `I76_MISSION=<name>` in the Strlkup proxy writes `0x5049f0`, NOPs the two clears
  and sets the skip-shell dword `0x504c10 = 1` [fact: `docs\MISSION-LAUNCH.md`, `music-fix\strlkproxy.c` line 720].
  Three limits [fact: `MENU-USABILITY-PLAN.md` E1, `mission.md`]: the car stays `vppirna1` (only the shell path
  copies `0x5dcea9`; no env switch sets `0x5dd370`, `0x5dcea0` or `0x4c2160`: grep of `strlkproxy.c`); the `.vsf`
  state loads only for the car's basename in a trip; and with `0x504c10` set every end state except Replay exits
  the process.
- **Saves are solved outside the game.** `i76-save-editor.py` / `.html` parse and write `.cmp`, `.spc` and
  `savegame.dir` byte-exact (46 files, 132 tests), with the mount, cap and repair-queue rules the garage applies
  [fact: `docs\SAVE-EDITOR-STATUS-2026-10-02.md`, `docs\MOUNT-VALIDATION.md`]. `i76-map\data` has byte-exact
  `.vcf` / `.vsf` codecs (`fmt\l_vcf.py`, `mod\i76mod.py`).

### 1.4 How the shell draws and presents [fact: Ghidra export `shell\ghidra\export\functions\`, `symbols\functions.tsv`]

- The shell imports **no DirectDraw**. It draws 8-bit palettised pixels into two heap buffers of 640x480
  (`VDriver_Init` 0x10037a50: `HeapAlloc(w*h)` twice, front `+0x44` and shadow `+0x58`, immediates `0x280` / `0x1e0`
  at `+0x3bc` / `+0x3c0`) and into the **exe's** DirectDraw back surface handed over in arg 6.
- **DDraw path** (arg 6 nonzero; taken under `-glide` too, because `[0x4f9f20]` stays 1 unless `-gdi`: MOUSE doc
  §2.2): `DDraw_LockBuffer` 0x10021c50 locks the back surface (vtable +0x64), `DDraw_Present` 0x10021d90 unlocks
  (+0x80) and calls `primary->Blt` (+0x14) with the **literal rect {0,0,640,480}** and `DDBLT_WAIT`. Palette through
  the exe's `IDirectDrawPalette` (`DDraw_WritePaletteEntries` 0x100212f0). On the installs those COM objects are
  dgVoodoo's, which is why dgVoodoo scales the shell.
- **GDI path** (arg 6 == 0): a `CreateDIBSection` DIB and `BitBlt` to the window DC (`Gdi_Present` 0x10022400,
  size `[0x100f700c]` x `[0x100f7010]`), palette via `SetDIBColorTable`. Cold on the installs.
- **The drawing waist.** Screen code does not poke pixels; it calls a small set of primitives (direct call sites,
  capstone sweep via `sdis.py calls`): `Display_LoadScreenBackground` 0x100387d0 (17 sites),
  `Display_RestoreBackgroundRect` 0x10038fd0 (118), `Display_DrawText` 0x100395b0 (225), `Display_DrawSprite`
  0x10039390 (35), `Display_BlitBitmap` 0x10038b70 (32), `Display_DrawLine` 0x10038a70 (17), `Display_DrawChar`
  0x10039750 (3), over a hand-written `Mcga_*` asm library (72 named entries). Drawing is incremental with dirty
  rectangles (`VDriver_AddDirtyRect` 0x10037d00), not a full redraw per frame.
- **Mouse.** `Mouse_Update` 0x1001fbf0: `GetCursorPos`, `ScreenToClient`, range check against the constants 640 /
  480 (`ui_width` `0x100f701c` stored at 0x1001e420, `ui_height` `0x100f7018` at 0x1001e42a; `GetClientRect` result
  discarded), buttons by `GetAsyncKeyState`. Never scales (FIXES.md F4). The shell draws its own pencil pointer at
  the UI position (Leg-A capture `A10b-typed.png`).

### 1.5 The pointer problem, stated exactly [fact: MOUSE doc §5a, §7; `SAVES-LEG-A-RUN-2026-10-01.md` §6; `MENU-USABILITY-PLAN.md` §0]

On the 3440x1440 panel the game window's client is 3440x1440 and the 4:3 picture is drawn at 3.0x in screen
x 760..2680.

| where | what the hand does | what is drawn |
|---|---|---|
| shell screens (`CaptureMouse=true`, the deployed minimal u32x) | OS clip `0,0-640,480`; the OS position is the UI coordinate 1:1 (13 of 13 clicks read back exact) | the shell's pencil at `760 + 3x, 3y`: the pencil moves 3 screen px per px of hand, and the real pointer lives in the top-left corner |
| in mission | `GetClipCursor` = `0,0-1920,1440` | no pointer |
| Esc menu (exe) | OS clip released, yet `SetCursorPos(3400,700)` reads back `(1919,700)`: **dgVoodoo pins the pointer to a 1920x1440 box at the client origin**; `CaptureMouse` / `FreeMouse` / `Resolution` change nothing | the OS arrow, and the menu page inside the picture: Exit is drawn at x 2056, the arrow stops at 1919. With the box mapping (uncap-lab `53a8cae`) Exit is hit from x 1296: **the hand sits 760 px left of the drawn item** |

So "pointer confusion" is three separate defects: (a) two different regimes (1:1 corner in the shell, box in the
mission), (b) no regime in which the visible pointer and the hit point coincide on a pillarboxed window, (c) the Esc
menu has no drawn pointer, so the offset is visible. The helper overlay `i76-cursor-overlay.ahk` shows the real
pointer, which makes (b) more visible, not less. [open] Whether dgVoodoo's box is anchored to the client origin or
the screen origin: the client sits at the screen origin today, so the two cannot be told apart (section 7, step 3).

State of the proxy [fact: MOUSE doc §8, `STATUS-2026-10-02.md` 22:30]: the sandbox runs `u32x_min.dll` (`a5927cea`,
Aug-16 behaviour + ghosting fix). The box-mapping build broke garage DONE (its keep-alive pump ate ShellMain's
WM_QUIT, 4 of 4); the quit-guard build `05c9a7be` is compiled and **not yet run** (gate §8.6).

## 2. DATABASE.MW2 is mostly cracked already

`data\FORMATS.md` lists DATABASE.MW2 as 100% unknown because that table counts what `i76.exe` parses. The shell
track decoded it [fact: `shell\README.md`, `shell\tools\mw2db.py`, `mw2shape.py`; item list re-run today on
`sandbox-gog\main\app\DATABASE.MW2`, 8,204,554 bytes]:

| items | kind | bytes (packed) | decoder status |
|---|---|---|---|
| container | `u32 count (83); u32 offset[count]`; item k = `[offset[k-1], offset[k])` (`TMPackDataBaseObj_GetDBItem` 0x10008240) | 336 | done (`mw2db.py`) |
| 0x01..0x20 | backgrounds: `u32 outlen` + LZSS (4 KB ring, flag byte LSB first, bit 1 = literal, else u16: pos 12 bits, len 4 bits + 3; `GetDBItemPacked` 0x10008320) of a **real PCX**: checked today on items 0x01, 0x11, 0x1a: header `0a 05 01 08`, 1 plane, 640x480 (0x11 is 408x406), palette marker 0x0c at EOF-769 | 3,741,035 | done; 32 PNGs in `shell\work\png\` (31 at 640x480). The P10 claim "640x480 PCX" holds |
| 0x21..0x40 | "1.10" sprite tables: `+4 frame count`, per frame rect + run-length lines (0 EOL, 1 skip n, odd literal, even run; blitter 0x1003a8f4). Indexed pixels **with no palette of their own**: they use the palette of the screen they are drawn on. Three are large: 0x24 (1.07 MB), 0x3c (1.02 MB), 0x3d (0.55 MB) | 3,096,150 | done (`mw2shape.py`, all 32 tables decode); 0x3e = main-menu buttons |
| 0x41..0x47 | bitmap fonts, header `"1.\0\0"`: `+4` glyph count (0x100 for 0x42/43/45/46, 0x90 for 0x44/47, **0x22c0 for 0x41**: the double-byte Japanese font, 270 KB), `+8` height in px (15, 12 or 10), `+0x10` offset table (`glyph = font + [font+0x10+ch*4]`, first dword = advance width: `Mcga_FontGetCharWidth` 0x1003e42c, `Mcga_FontGetHeight` 0x1003e419) | 352,208 | **container known, glyph pixel encoding not decoded** [open: read `Mcga_DrawChar` / `Mcga_DrawString`, the callee of 0x10039750 at 0x1003e44c] |
| 0x48..0x52 | RIFF WAV (0x51, 0x52 tagged "PIFF") | 1,009,620 | plain |
| 0x53 | credits text | 5,205 | text |

Not in DATABASE.MW2 [fact: directory listing of the sandbox]: `Pencil.cur` / `Nopencil.cur` (the shell's cursors,
`LoadCursorFromFileA` in ShellMain), `BASE6X76.FNT` / `base6x7.fnt` / `base6x74.fnt` and `loadscr.pcx` /
`loadgame.pcx` (exe side; which code reads the `.fnt` files was not checked here [open]). The Esc menu's text is GDI
Arial Bold on `.map` page art, so it is already a scalable font drawn at frame resolution.

**Cracking plan for what is left** [proposed, S..M]: (1) decode the glyph stream from `Mcga_DrawChar` and add
`mw2font.py` (render each font to a sheet; gate: every glyph's width equals `Mcga_FontGetCharWidth`); (2) a
repacker `mw2pack.py`: offset table + items; for LZSS items a **literal-only stream is valid for the decoder**
(every flag byte 0xFF, 9 bytes per 8), so no compressor is needed [inferred from the decoder; gate: `unlzss(pack(x))
== x` and a byte-identical rebuild of the stock file when items are copied through]; (3) a table of which palette
each sprite set is drawn under (the caller's background item; `mw2shape.py` takes it as an argument today).

## 3. The options

### Option A: keep the shell, own the layer between it and the screen

**Idea.** The shell stays byte-for-byte (plus the small fixes already designed: F2, F3). A proxy owns pointer,
presentation and, later, the art. Three stages, each useful alone.

**A1, one pointer (S..M).** [proposed] In `u32x.dll` (already the USER32 import of both binaries):

- One regime everywhere: the reachable box (measured `GetClipCursor`, or dgVoodoo's pin box) is mapped linearly onto
  640x480 for the shell and onto the menu page for the exe (the box mapping of `53a8cae`, generalised to the shell).
  Pointer speed becomes 1 picture pixel per pixel of hand instead of 3.
- One visible pointer: hide the OS cursor while a menu is up and draw the pointer where the click will land. The
  shell already draws its pencil there. For the Esc menu, a small click-through layered topmost window positioned at
  `picture origin + scale * UI` (the same mechanism as `i76-cursor-overlay.ahk`, moved to the mapped position, owned
  by u32x); alternative: write the sprite into the Glide frame in the existing `_grBufferSwap@4` hook.
- A variant to test first because it would make the *real* arrow correct with no drawing: size the game window to
  the 4:3 picture (client 1920x1440 at x 760, a black backdrop behind it), so dgVoodoo's box and the picture are
  the same rectangle. u32x can do it by intercepting the exe's window creation / `SetWindowPos`. Works only if the
  box is client-anchored and dgVoodoo's fake-fullscreen mode leaves the window alone [open; section 7 step 3].

Fixes: pointer confusion in the shell and the Esc menu. Does not fix: blur, small text. Risks: the u32x history
(every new intercept has produced one regression: the WM_QUIT theft); mitigated by the kill-switch pattern already
in the source and by the leg-b gate.

**A2, own the present (M).** [proposed] Take the shell's frame away from dgVoodoo's DDraw scaler and draw it
ourselves into the game window: integer or chosen-filter scale, exact picture rectangle known to the pointer map
because the same code computes both. Two ways to get the 640x480 8-bit frame and its palette:

1. hook the one presenting call: `DDraw_Present` 0x10021d90 (and `DDraw_Flip` 0x10020ff0, `DDraw_StretchBlit`
   0x10020d40), read the locked back surface or the shell's front buffer (`vdriver+0x44`) plus the palette the shell
   last wrote; or
2. hand the shell `arg6 = 0` so it takes its own GDI path, and redirect its `BitBlt` (u32x already patches the
   shell's `BitBlt` / `StretchBlt` IAT entries) to a `StretchDIBits` onto the picture rectangle.

Present with GDI `StretchDIBits` (enough for a menu; 60 Hz of 640x480 is trivial) or a D3D11 swap chain on a child
window. Fixes: blur (integer scale or a good filter under our control), any monitor aspect, and removes dgVoodoo's
cursor emulation from the shell completely. Risks: [open] how a second presenter coexists with dgVoodoo's Glide
window on the same HWND (the MOUSE doc saw one `grSstWinOpen` before the mission; whether Glide is open during the
shell on a normal boot is not recorded); the hand-over at 0xC010 and back must leave the DirectDraw objects in the
state the exe expects; the pack shell's GDI path differs from pristine (P2, P3 in FIXES.md "Pack diff").

**A3, HD mirror canvas (L).** [proposed] Hook the `Display_*` waist (section 1.4) and replay every draw operation
onto a true-colour canvas at the monitor's picture resolution (1920x1440 here) with HD assets:
`LoadScreenBackground(item)` -> the upscaled background; `RestoreBackgroundRect(r)` -> the same rect of the HD
background; `DrawSprite(set, frame, x, y)` -> the upscaled sprite at scaled coordinates; `DrawText(font, string,
x, y, colour map)` -> the string re-typeset with a vector font at native resolution; lines and bitmaps scaled.
The shell keeps drawing its 640x480 frame as the reference: any pixel of the real frame that the mirror cannot
explain (a primitive not hooked, a direct `Mcga_*` call) is shown from the real frame, scaled, so the result is
never worse than A2. The shell's logic, hit tests and coordinates stay in 640x480 units, which is why this is the
only route to higher resolution that does not touch the widget tables.

Fixes: resolution of art and fonts, with no 8-bit limit. Risks: fidelity of text metrics (the shell measures with
`Font_MeasureText` 0x10015580 and lays out in SD pixels: the HD font must be fitted to the same advance widths, or
strings will overrun boxes); the typewriter effect and escape codes in `TextLabel_StepChar` 0x100374c0; palette
fades (`DDraw_PaletteFade`) must be mirrored as a global fade; [open] the census of screen code that calls `Mcga_*`
directly.

Effort for A overall: A1 S..M, A2 M, A3 L. Each stage ships on its own.

### Option B: replace the art in place (DATABASE.MW2 repack)

**What works.** Repacking is easy (section 2). Same-size art replaces cleanly: any 640x480 8-bit PCX for a
background, any re-drawn sprite frame with the same rect, a re-drawn bitmap font with the same advance widths.

**What does not.** The shell cannot show more than 640x480 [fact]:

- buffers and present rect are immediates: `VDriver_Init` 0x10037a50 (`0x280`, `0x1e0`), `DDraw_Present` 0x10021d90
  (rect literal), `ui_width` / `ui_height` stores at 0x1001e420 / 0x1001e42a;
- every layout number is in 640x480 units and most are immediates in code, not data: the main menu's 18 buttons are
  `Button_Init` calls with constant x, y, w, h (0x10027120..0x100273cf), the notepad menus are static 0x2c-byte
  widget tables (three for Options alone), the save screen's regions are a static list at 0x10047600, the modal
  YES/NO rects are constants (0x100440c8), list rows use constants such as `(y-184)/row_h`;
- sprites carry their own rectangles in pixels and fonts their own heights; the `Mcga_*` blitters have no scale;
- the exe's DirectDraw surface for the shell is created for video mode 5 (640x480: `0x5dd360 = 0` during ShellMain).

A "2x internal resolution" patch therefore means rewriting every coordinate in about 700 functions and all static
tables, with no source: XL, and each missed constant is a misplaced widget. The honest version of B at higher
resolution is A3 (scale at the drawing waist, not in the data).

**Palette.** B is 8-bit by construction: one 256-colour palette per screen, taken from the background PCX
(`Display_GetPcxPalette` 0x10038580), and every sprite and glyph drawn on that screen is indexed into it. An
AI-processed 640x480 background must be quantised back to 256 colours **while keeping the indices the sprites and
text colours of that screen use** (reserve them; quantise the rest), or buttons change colour.

Effort: the repack tool S..M; same-resolution art refresh M; higher resolution XL. Fixes: nothing about the pointer;
at best slightly cleaner 640x480 art. Use: as the delivery vehicle for corrected or modded stock-resolution art, and
as the asset extractor for A3.

### Option C: a new external front end (launcher app)

**Architecture.** [proposed] A desktop app (the existing `i76-save-editor.html` + `i76-save-editor-server.py` are
the seed) that owns bookmarks, the garage, mission select and options, and runs the exe only for missions:
`I76_MISSION=tNN.msn` with the shell skipped, returning to the app when the process exits.

**What the exe needs at mission start** [fact: section 1.3] and where it would come from [proposed]:

| need | shell does | front end would |
|---|---|---|
| mission name `0x5049f0` | setup block +0x5d | `I76_MISSION` (exists) |
| car `0x5dd370 = 'vehscn'` | copy of `0x5dcea9` | **new proxy switch** (for example `I76_CAR`); without it the Piranha |
| `ADDON\vehscn.vcf` | `Vehicle_WriteVcf` via cb 08 (VCFC 0x81 bytes, WEPN 0x11 each, SPEC) | write it with the data track's byte-exact vcf codec from the `.cmp` GarageRec; the GarageRec -> VCFC field map is `shell_cb_03` 0x4b6850 / 0x10035250 and must be reproduced exactly |
| `ADDON\vehscn.vsf` (damage carried in) | `Vehicle_WriteVehState` via cb 09 | same, from part conditions |
| play mode `0x5dcea0 = 2`, scene `0x4c2160` | DLL writes through arg 12 / arg 7 | new proxy switches; the scene matters for tier gating of salvage (`salvage_ClampPartTier`) only through the mission number, which comes from the name [inferred] |
| options `I76PLYR.DEF` | exe reads it itself | edit the 0x60-byte block (layout in `subsystems\options.md`) |

**What comes back at mission end** [fact: `mission.md`]: with `0x504c10` set, every end state except Replay exits
the process. On a plain trip success the exe has written `ADDON\vehscn.vsf` with the car's state and SALV. The
outcome itself (`0x4c2164`: 1 won, 0 failed, 2 aborted, 0xb cheated) is in memory only, so the proxy must write a
result file at exit [proposed; `I76_TELEMETRY` shared memory could carry it]. The front end must then do what
`PostMission_Open` 0x10023fc0, `VehState_ApplyToWorkingCar` 0x100029d0 (988 bytes) and the inventory do: apply
VCST / WLST / WPST to part conditions, turn SALV entries into PartNodes (which needs the parts catalogue the exe
builds in cb 00 from every `.wdf` / `.gdf` / `.vtf`), run the repair economy (`Garage_AdjustAllocation` 0x10024db0,
1,957 bytes; `Garage_SumRepairCost` 0x10007720), honour the special cases (`trip4.spc` on scene 3, the t12 flag
`0x5dd2f0`, t17 ending, the training missions), advance the scene, and write `.cmp` / `savegame.dir` (already
byte-exact).

**What breaks or is lost.**

- Multiplayer: the lobby, DirectPlay session code and vcf anti-cheat handshake live in the shell (`anetdll`, cb 25,
  26). The front end would have to keep the stock shell for network play.
- Melee and scenarios: the entry forms fill the setup block (opponents, rules, `MULTICAR.def`); a direct boot of
  `m01.msn` does not set play mode 3 or `match_SetMultiMelee`. [open] How much of the setup block a melee needs.
- Cutscenes: WRLD intro and outro movies are played by the exe inside the mission and keep working; the boot movies
  can be skipped (`I76_SKIP_MOVIES`). The shell's music (track 0xd), Credits and Standings disappear unless
  rebuilt.
- In-mission "Load Bookmark" and "Reconfigure" (states 9, 8) become "the game exits and the app opens".
- Every mission start is a process launch: the intro of the mission needs Esc (`0x4fe534 = 0x20`), and window
  focus hand-over between two apps on a fullscreen game is its own source of trouble.
- The Esc menu is still the exe's, so C alone does not fix that pointer.
- Rule drift: every garage rule reimplemented outside the game is a rule that can disagree with the game. The
  2026-07 save editor is the precedent: a wrong frame produced five corrupt saves.

Effort: a "continue / pick bookmark / edit loadout" launcher that still enters through the shell is M (it is E1-A
of MENU-USABILITY-PLAN plus the editor that exists). A front end that really replaces the garage and the
post-mission flow is L..XL, dominated by the repair economy, the catalogue and the vcf/vsf builders, each of which
needs a byte-compare gate against shell output. Fixes: all shell-side UI pain (it is a modern app), nothing in
mission.

### Option D: an in-process replacement `i76shell.dll`

**Architecture.** [proposed] A new DLL exporting `ShellMain` and `ShellWindowProc` with the same 13 arguments,
result codes and play-mode / car / mission stores, calling the same 27 callbacks, and rendering its own UI (Dear
ImGui or a small retained toolkit over D3D11 or GDI) at native resolution in the game window. Because it uses the
exe's callbacks, the vcf/vsf writers, the parts catalogue, sound, CD music and the anti-cheat come for free, and the
mission hand-over is the stock one (no direct-boot limits, Replay / Reconfigure / Load Bookmark keep working).

**Cost.** Everything in section 1.2 has to exist again: the garage and its pickers, the repair queue and
allocation, inventory classification, the save / load screens, the mission grid, the melee and network forms with
the anet session code, standings, Control Configuration with `input.map` I/O, the post-mission flows and the
trip-scene special cases. The map is good (606 of 721 functions named, 280 supported, the save formats byte-exact)
but about 200 names are still "proposed", and the logic-heavy functions (`Garage_Frame`, `Garage_AdjustAllocation`,
`VehState_ApplyToWorkingCar`, `EntryForm_Frame`) are decompiled, not specified. Rendering: the exe gives the shell
an 8-bit DirectDraw surface at 640x480; a native-resolution UI needs its own surface or child window and must hand
the display back in the state the exe's graphics re-init expects (0x4025b7).

A cheaper hybrid exists: a *wrapper* DLL that loads the stock shell and forwards, replacing one screen at a time
(for example the save screen first). It keeps stock behaviour as the fallback per screen.

Effort: XL (months) for parity; the hybrid is L per screen. Risks: behavioural parity with no oracle except
side-by-side runs; network play is hard to test at all. Fixes: everything shell-side, at any resolution; the Esc
menu still needs A1.

### Comparison

| | pointer (shell) | pointer (Esc menu) | sharper picture | HD art and fonts | keeps stock logic | multiplayer | effort to first value | effort to finish |
|---|---|---|---|---|---|---|---|---|
| A1 one pointer | yes | yes | no | no | yes | yes | S..M | S..M |
| A2 own present | yes | via A1 | yes | no | yes | yes | M | M |
| A3 HD mirror | yes | via A1 | yes | **yes** | yes | yes | L | L |
| B repack, same size | no | no | no | marginal | yes | yes | S..M | M |
| B higher internal res | no | no | yes | yes | patched everywhere | at risk | XL | XL |
| C front end | replaced | no | n/a | native app | **reimplemented** | lost (keep shell) | M (launcher) | L..XL |
| D new shell DLL | replaced | no | yes | yes | **reimplemented** | must be rebuilt | L (one screen, hybrid) | XL |

## 4. AI upscaling pipeline for the art and fonts

**Extract** [fact: tools exist except the font decoder]: 32 backgrounds -> PNG (`mw2db.py` + `unlzss` + PIL, done);
32 sprite tables -> one PNG per frame with a transparency mask (`mw2shape.py`; each needs the palette of the screen
it is used on); 7 fonts -> glyph sheets [open: `mw2font.py`, section 2]; `Pencil.cur` / `Nopencil.cur`; the Esc
menu's `.map` pages (exe side, format in the data track).

**Classify before upscaling** [proposed]. The 640x480 art is three different kinds of image and one upscaler does
not suit all:

| kind | examples | treatment |
|---|---|---|
| scanned / painted paper, photos, texture (garage form paper, notepad, title logo) | most backgrounds | a GAN upscaler at 3x or 4x then downsample to the exact target (1920x1440 for 3.0x). Candidates: Real-ESRGAN `x4plus` (photographic), `realesr-general-x4v3` with its denoise control (gentler on dithering), `x4plus-anime` for flat line art; SwinIR or HAT as slower, more faithful alternatives. Pick per image by eye from an A/B contact sheet, and record the choice. 8-bit dithering in the source is the main enemy: de-dither (light blur or a `1x` de-dither model) before upscaling, or the model amplifies the pattern |
| **printed text baked into backgrounds** (form labels, headings such as BUILD AND REPAIR FORM) | garage, inventory, entry forms | GAN upscalers invent wrong letter shapes at this size. Mask the text, upscale the paper underneath, and **re-typeset** the labels with a matching font at native resolution (the typewriter / form faces have close free equivalents; match by overlaying on the 3x nearest-neighbour original) |
| line art and UI sprites (buttons, icons, condition bars, the pencil) | sprite sets 0x21..0x40 | upscale with alpha handled separately (upscale RGB on a neutral matte, upscale the mask on its own, recombine), or redraw: the button captions in set 0x3e are text and should be re-typeset like the labels |
| **fonts** | items 0x42..0x47 (10, 12, 15 px tall) | do not AI-upscale glyph bitmaps. Either (a) **vector re-trace**: nearest-neighbour 8x, threshold, `potrace`, hand-clean the roughly 95 printable glyphs per face, export TTF; right for the handwriting face, where the exact shapes are the charm; or (b) **substitute** a free font of the same style and fit it to the stock advance widths. In both cases the HD font must reproduce the stock widths at 1/3 scale so the shell's own measuring still fits its boxes. The Japanese font 0x41 (8,896 glyphs) is out of scope |

**Palette constraints.** In B the output must go back to 8-bit indexed with the screen's palette and reserved
indices (section 3, B). In A2 the frame is still the shell's 8-bit frame, so upscaling there means a *scaler*
(integer, or xBRZ-style on the indexed frame), not new art. In A3, C and D the HD assets are true-colour with real
alpha: no palette limit. One thing survives everywhere: the shell recolours text and some sprites through 256-byte
colour maps (`Text_InitColourTables` 0x10037380, the map argument of `Display_DrawText`), and fades through the
palette, so an HD renderer has to apply the equivalent tint and fade to its true-colour assets.

**How the results load, per option.**

| option | loader |
|---|---|
| A3 | a loose folder beside the game (`hd\bg\1a.png`, `hd\sprites\3e\05.png`, `hd\fonts\*.ttf`), keyed by DATABASE.MW2 item and frame; missing file = fall back to the scaled original. No game file is modified, so the same install runs stock when the layer is off |
| B | `mw2pack.py` writes a new DATABASE.MW2 (keep the original as `.orig`); 640x480 8-bit only |
| C | ordinary app assets |
| D | ordinary assets of the new DLL |

**Legitimacy.** Upscaled derivatives of the game's art are game data: keep them out of the public repo like the
existing `work\png\` (git-ignored); ship the *pipeline* (extract, upscale, pack on the user's machine), as
`docs\HD-TEXTURES-RESEARCH.md` and `LEGITIMACY-AND-SCOPE.md` already do for textures.

**Order of work** [proposed]: a contact sheet of three backgrounds (main menu 0x1a, garage 0x01, a notepad 0x06)
through two models each at 3x, viewed on the panel, before anything is built around them. It costs one sitting and
decides whether the art is worth the A3 stage at all.

## 5. What each option does to the known pain list

Using the catalogue in `MENU-USABILITY-PLAN.md` §1: P1/P11/P13 (pointer) are A1. P10 (small, blurry) is A2 then A3.
P2 (freeze on prompts), P4 (ghosting), P5 (orphaned bookmark) are small shell fixes already designed (F3, the
ghosting call, F2) and are independent of every option here; C and D would make them moot only by rewriting those
screens. P9 (boot movies), P8 (CD prompt) and P12 (Control Configuration eating `input.map`) are untouched by A and
B, moot in C, a rewrite in D.

## 6. Recommendation

**Option A, staged, with a thin launcher from C. Not B at higher resolution, not D.**

Reasons:

1. The pain is in three narrow places (pointer mapping, the scaler, the art), and the shell exposes each through a
   narrow waist: one mouse function, one present call, about ten drawing primitives. The logic behind them works
   and is the only complete specification of the campaign's garage and salvage rules that exists.
2. A is the only option that also fixes the Esc menu, which is the exe's and survives any shell replacement.
3. C and D reimplement rules whose misreading has already cost corrupt saves; they should be reached, if ever,
   one screen at a time behind the stock shell as the fallback, not as a cut-over.
4. Each A stage is verifiable with the harness that exists and ships alone.

| stage | what the owner gets | effort | depends on |
|---|---|---|---|
| **Week 1: A1 "one pointer"** (section 7) | one visible pointer that lands where it points, same behaviour in every shell screen and the Esc menu, pointer speed 1:1 with the picture; the AHK overlay retired | S..M | the quit-guard gate passing (MOUSE doc §8.6) |
| Week 1, riding along | F2 orphan fix as a u32x runtime patch, ghosting fix on the daily driver, F3 keyboard answers (all specified in MENU-USABILITY-PLAN §5) | S each | lab verification |
| Stage 2: A2 own present | crisp integer-scaled shell at any monitor size, pointer map and picture computed by the same code, dgVoodoo out of the shell's path | M | A1; the DDraw-vs-GDI coexistence test |
| Stage 2b: launcher | "Continue" (boot to the newest bookmark by driving the shell, E1-A), bookmark manager and loadout editor from the existing save editor, movie skip without `I76_MISSION` | M | the `LoadMenu_Frame` -> 0xC01D trace |
| Stage 3 (the epic): A3 HD mirror | upscaled backgrounds, re-typeset labels, vector fonts at native resolution, stock logic underneath | L | A2; `mw2font.py`; the upscaling contact sheet approved by eye |
| Optional, after A3 | replace single screens natively (save / load first) through a wrapper DLL (the D hybrid), using the A3 canvas as the renderer | L per screen | A3 |

What is deliberately not on the plan: a 2x internal-resolution patch of the shell (B, XL, fragile), a full external
front end that replaces the garage (C, rule drift, loses multiplayer), a clean-room shell DLL (D, months, no oracle).

## 7. First milestone: "one pointer" on the sandbox

**Goal.** In the sandbox (`C:\Users\james\i76-uncap-lab\game`, console session, owner not playing), with one u32x
build: the pointer the player sees is the pointer that clicks, in the garage, the save screen and the Esc menu, and
the bookmark route still reaches the mission. Opt-in by environment (`I76_U32X_VPTR=1`), off = today's behaviour.

**Step 0, prerequisite gate (no new code).** Run the pending gate of MOUSE doc §8.6 on the compiled quit-guard
build (`src\u32x_new.dll` `05c9a7be`): `autotest\saves\leg-b.ps1 -WantFile save003 -WantRow 3 -RowUy 262` three
times, pass = "shell left after DONE", frame counter moving, 3 of 3; then the control with `I76_U32X_QUITGUARD=0`
once (must hang at B1.9). Nothing below is built on a proxy that fails this.

**Step 1, the pointer truth table (measurement, no new code).** `autotest\saves\garage-ui.ps1 -Start save003 -Row 3`,
then on four screens (garage, Options notepad, Save Bookmark, and the Esc menu via `autotest\test-escmenu.ps1`)
record: `Get-UiMap` (clip box, client, scale, origin), the OS position after `SetCursorPos` to five probe points
across the full client (does it pin, and to what box), the shell's `mouse=(x,y)` from `garage-ui.ps1 -State`, and
where the pencil is drawn (`-Shot`). Twice, n reported. This replaces the three conflicting records of the regime
(2026-09-05, 2026-09-07, 2026-10-02) with one table and tells step 2 which box to map in the shell.

**Step 2, build** [proposed code, `src\u32x.c`, new block behind `I76_U32X_VPTR`]:

1. shell: when the reachable box is larger than 640x480, map it linearly onto UI space in `My_GetCursorPos` for
   shell callers (the Esc-menu box mapping, same function, other caller); when it is the 1:1 corner box, widen the
   clip to a picture-sized box first (`My_ClipCursor`) if step 1 shows the clip is the engine's and not dgVoodoo's;
2. Esc menu: hide the OS cursor while `[0x4fe534] == 0x10` and show a layered click-through cursor window at
   `picture origin + scale * frame(x, y)`; destroy it when the mode leaves 0x10;
3. no new message pumping, no new IAT patches; every new branch has a kill switch like the existing ones.

**Step 3, the window experiment (one launch, decides the cheaper design).** With a debug switch, place the game
window's client on the picture rectangle (1920x1440 at x 760) and read `GetClipCursor` in the mission and the pin
box in the Esc menu. If the box follows the client (760..2680), the real arrow is already correct everywhere, the
cursor window of step 2 is unnecessary, and the map loses its offset. If the box stays at the screen origin or
dgVoodoo resizes the window back, record that and keep step 2's design.

**Verification (existing harness; pass criteria fixed in advance).**

| check | how | pass |
|---|---|---|
| hit point = intended point, shell | `garage-ui.ps1 -Click x,y` on 8 UI points spread over the form (including x > 600 and y > 440), then `-State` | shell `mouse=(x,y)` within 1 px of the target, 8 of 8, in two runs |
| drawn pointer = hit point, shell | `-Shot` after each click; pencil hot spot in the 640x480 capture | within 2 px of the target, 8 of 8 |
| pointer speed | move the OS pointer 300 px right inside the box, read `mouse` before and after | UI delta 100 +- 1 (3.0x picture), not 300 |
| save screen | MOUSE doc Test B (10 s idle, row click, SAVE twice, YES) | bookmark written, `[0x10043224]` stays 1 |
| route regression | `leg-b.ps1 -WantFile save003 -WantRow 3 -RowUy 262`, 3 runs | 3 of 3 reach the mission |
| Esc menu | `test-escmenu.ps1`: click with the visible cursor on the drawn Exit and Play Options | `[0x4fe534]` leaves 0x10 on Exit; Play Options opens; cursor window position equals `760 + 3 * frame x` within 3 px in a full-window capture |
| control | everything above with `I76_U32X_VPTR=0`, once | today's regime returns (1:1 corner in the shell, hand 760 px left in the Esc menu) |
| melee route | `autotest\menu-route-test.ps1` | passes |

Then, and only then: a hand test by the owner on the sandbox (the automation has been the unreliable instrument for
pointer feel before: memory "verify the click landed"), and promotion to the daily driver as its own announced
step with the previous `u32x.dll` kept beside it.

**Not in the milestone:** any change to presentation or art; F2 / F3 (separate, already specified); the daily
driver.

## 8. Open questions this study did not settle

- dgVoodoo's pointer box: client-anchored or screen-anchored, and which API it clamps through (section 7 step 3).
- Whether Glide is open while the shell runs on a normal boot, and what a second presenter on the same HWND does to
  it (A2).
- The glyph pixel encoding of the "1." fonts (section 2) and which screens use which of the seven.
- Which screen code calls `Mcga_*` directly, bypassing `Display_*` (A3 coverage).
- How much of the 0x230-byte setup block an auto melee needs (C).
- The GarageRec -> VCFC and VehState -> VCST field maps as byte-compare gates against shell-written
  `vehscn.vcf` / `.vsf` (C, D; the Leg B harness already captures both files after a load).

## Sources

i76-everywhere: AGENTS.md; docs/MENU-USABILITY-PLAN.md, SAVE-FREEZE-ROOT-CAUSE.md, MOUNT-VALIDATION.md,
SAVE-EDITOR-STATUS-2026-10-02.md, MISSION-LAUNCH.md, SAVES-LEG-A-RUN-2026-10-01.md, STATUS-2026-10-02.md,
PLAYTEST-2026-10-02.md, BACKLOG-2026-10-02.md; music-fix/README.md, music-fix/strlkproxy.c (switch list, line 720).
i76-map: shell/README.md, SCREENS.md, SAVE.md, FIXES.md, CALLBACKS.md, work/exe-callbacks.md, work/cmp-layout.md,
symbols/functions.tsv, symbols/globals.tsv, tools/mw2db.py, tools/mw2shape.py, tools/sdis.py (`calls`),
ghidra/export/functions/10037a50.c, 10021d90.c, 10021c50.c, 10022400.c, 10039750.c; data/FORMATS.md, data/README.md;
subsystems/mission.md; `sandbox-gog\main\app\DATABASE.MW2` (item list and three PCX headers decoded today,
read-only), `shell\bin\i76shell.dll` import and export tables (pefile).
i76-uncap-lab: docs/MOUSE-ESC-MENU-AND-SAVE-SCREEN.md (§2, §5a, §7, §8), autotest/saves/leg-b.ps1, garage-ui.ps1,
autotest/README.md listing, git log of src/u32x.c.
