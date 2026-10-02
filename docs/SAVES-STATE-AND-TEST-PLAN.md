# Saves: everything known, and a sandbox test protocol

*Consolidation written 2026-10-01 from the repo docs, the i76-map shell and data tracks, the i76-uncap-lab proxy and
harness, and read-only looks at the lab game folder and the committed save sets. Nothing was run in the game and nothing
outside this file was edited. Tags: **[fact: source]** = measured or read from code, with where; **[new]** = derived in
this pass from the pristine bytes or the files on disk (read-only, cited); **[proposed]** = not built or not shown live.
Status words: **solved+verified** (confirmed in the field or live), **solved+built** (bytes exist, no live run),
**mechanism known** (traced statically, no fix built), **open**.*

Rules carried over: experiments run on the lab copy `C:\Users\james\i76-uncap-lab\game`, never on the portable daily
driver (AGENTS.md; memory "never experiment on the daily driver"); launch results are invalid over RDP
(AGENTS.md RDP section: check `[System.Windows.Forms.SystemInformation]::TerminalServerSession` is False); every
A/B gets an A/A first (memory "same-rate control run").

## 0. The lab save set as it is today (measured, read-only)

`C:\Users\james\i76-uncap-lab\game`, 2026-10-01 [new]:

| file | state |
|---|---|
| `savegame.dir` | 364 B, count 6, `4 + 60*6 = 364` exactly; records: save000 scene 1, save001 scene 2, save002 scene 3, save003 scene 5, save004 scene 6, save005 scene 6 name `s`; `+0x34` = 1,1,1,8,8,8 |
| `save000..005.cmp` | 6196 / 7008 / 9212 / 10604 / 10604 / 10604 B; every size satisfies `(size - 0x8cc) % 0x74 == 0` (SAVE.md §2 formula) |
| `ADDON\vehscn.vcf` | 309 B (2026-10-01); parses: Jade's Car, vppirnha.vdf, armour 711/722/733/744, chassis 755/766/777/788 (the T1 live-test edit, LIVE-TESTS data track) |
| `ADDON\vehscn.vsf` | **absent** (the only `.vsf` on the machine is `i76-map\sandbox-gog\main\app\ADDON\vehscn.vsf`: VCST armour 600x4, chassis 600x4, velocity 0, engine 300 / brake 150 / susp 200, flags 1,1,1) |
| `reconfig.spc`, `trip4.spc`, `I76PLYR.DEF` | 10604 B (Sep 27), 9212 B (Aug 9), 96 B |
| `i76shell.dll` | 352,256 B, Sep 6 (F1 text-entry bytes repaired; `.orig` and `.pre-toascii-fix` beside it) |
| `u32x.dll` | 75,264 B, Aug 16: **does not carry `DisableProcessWindowsGhosting`** (MENU-USABILITY-PLAN §0); `i76.exe.u32xorig` present, so the exe's USER32 import is retargeted too |
| `dgVoodoo.conf` | `CaptureMouse=true`, `FreeMouse=false`, `FullScreenMode=false`, `ScalingMode=stretched_ar`, `EnableInactiveAppState=true` |

The committed sets, re-parsed with the byte-exact layout [new]:

| set | size | count | `4+60n` | note |
|---|---|---|---|---|
| `saves\savegame.dir` | 876 | 13 | 784 | padded by our tools (+92); every record complete; **save017 "So Many Turrets" has scene 15** (see §6) |
| `saves\rescue-20260718\savegame.dir` | 844 | 14 | 844 | **exact, not truncated**; README calls it truncated under the 0x28 model |
| `saves\windows-20260906\savegame.dir` | 460 | 7 | 424 | padded (+36) |

All 26 committed `.cmp` files satisfy the size formula.

## 1. Timeline of every save-related symptom James reported

| date | symptom (as reported) | root cause | status | evidence |
|---|---|---|---|---|
| 2026-07-14, 07-15, 07-19 | **Orphaned save**: `savegame.dir` names `saveNNN`, disk has `save-01.cmp`; bookmark "vanishes" | `SaveMenu_Edit` 0x100147a0 sets the slot variable `0x10057f80 = -1` on every entry (0x10014866). A second pass through the edit loop in one visit (click on the name field after leaving it, or NO on the overwrite prompt) finds the static record already appended with slot S and skips the slot assignment (0x100149d7), so the save runs with slot -1. `dir_Load` 0x10033020 then drops any record whose `.cmp` does not open (0x100330b9), which is why it vanishes instead of showing broken. `-01` is Wine's `wsprintfA`; Windows gives `-001` | **mechanism known; 10-byte fix F2 built (static), live test T3 not run**; rescue exists on the Mac stub only | i76-map shell SAVE.md §4, FIXES.md F2, LIVE-TESTS T3; SAVE-ORPHAN-INVESTIGATION.md (editor "not cleared" - now cleared by the trace); MENU-USABILITY-PLAN P5 and item 1 |
| 2026-07-14 | "Game drops the last dir entry" / LOAD board rows wear the previous entry's name | Our dir writer put names at the wrong offset (name precedes the file field) | **solved+verified** (retracted the same day) | SAVE-FORMAT-GAPS.md "RETRACTION" |
| 2026-07-14 | LOAD pad shows "SCENE 2/3/4/5" for stored dwords read as [2,3,5,6] | Two errors stacked: the editor reads record k+1's scene for record k (its `+0x38` from `8+60k` is `4+60(k+1)+0`), and the shell prints **scene+1 when the record's `+0x34 == 1`** (`cmp [edi+0x34],1` 0x10013736, `inc ecx` 0x10013742, two "Scene %d." sites 0x10013744 / 0x10013753 in `LoadMenu_DrawList`). True dwords [1,2,3,5] with `+0x34` [1,1,1,8] print 2/3/4/5: 4 of 4 | **solved [new]** (static; one glance at the LOAD board confirms) | this pass: `sdis.py fn 0x10013670`; `i76-save-editor.py` `parse_dir` lines 239-258; SAVE.md §1 layout |
| 2026-07-18 / 09-05 / 09-06 | `savegame.dir` "36 bytes short" after every save; launchers re-pad | Misframed layout: the header is 4 bytes, not 0x28; `4 + 60n` matched 15 of 15 game-written files. The re-pad is harmless (the reader stops after `count`) and unnecessary | **misdiagnosis, retire** | SAVE.md §1; MENU-USABILITY-PLAN P7; memory "misframed layout, not a game bug" |
| 2026-07-14 | `.cmp` "truncates the final record at EOF"; "+84 inherited dwords"; "corrupt NitrousOxide record @9588" | Records are PartNode (0x20) then PartRec (0x54); a PartRec-first parser starts 0x20 bytes late. 27 of 27 saves match `0x8c4 + 8 + 0x74*(nA+nC)` | **misdiagnosis, retire** | SAVE.md §2, shell\work\cmp-layout.md |
| 2026-08-08 | With Lossless Scaling on, "rename variant" / "exit without salvage" / "overwrite" prompts could not be interacted with | Hypothesis: LS's always-on-top overlay over a shell-drawn prompt. Most of it later explained by the cursor and typing faults below | **open hypothesis** (one launch with `-LosslessScaling ""` decides) | FINDINGS-2026-07 §1; MENU-USABILITY-PLAN P15 |
| 2026-08-10 | **"Saving freezes the game"**, Windows says not responding, 100% of one core | `Modal_YesNo` 0x1000bc40 loops on `MouseUpdate` + `MouseClicked` only (0x1000bd2d..0x1000bd90): no key read, no pump, no timeout. `MouseUpdate` 0x1001fbf0 converts to client coordinates but never scales to 640x480 and discards every sample outside 0..639/0..479 including button state (F4), so in a 3440x1440 client a click can never land. Sampled stack `i76shell+0xBD38` = this loop | **solved+verified** (u32x proxy, deployed to both installs; keyboard escape F3 built, emulated 10/10, not run live) | SAVE-FREEZE-ROOT-CAUSE.md (diagnosis + v2); FIXES.md F3/F4; MENU-USABILITY-PLAN P1/P2 |
| 2026-08-10 | "The mouse is in the wrong position" / "mouse won't move" | Same cause: the engine's own `ClipCursor(0,0,640,480)` traps the pointer in the physical top-left box; v1 of the proxy shipped inert (`FindWindowA` NULL); v2 derives the mapping from live geometry | **solved+verified** (v2, 2026-08-16); residual: with `CaptureMouse=true` dgVoodoo's emulated cursor does the mapping, not u32x (needs one hand check) | SAVE-FREEZE-ROOT-CAUSE v2; deploy-shellfix.ps1 header; MENU-USABILITY-PLAN P1 caveat |
| 2026-08-10 | **"Always says overwriting"** on what felt like a new save | Not a slot bug: the field is pre-filled with the loaded bookmark's name; a row click takes the prompt path unconditionally (0x10014a78 / 0x10014d75); a typed name prompts only when scene *and* name already exist | **explained (by design)**; UX fix E3 (fresh default name) proposed | SAVE-FREEZE-ROOT-CAUSE "other two issues"; SAVE.md §4; MENU-USABILITY-PLAN P6/E3 |
| 2026-07-15 | "The game bumped save009's dir scene 6 -> 7 without rewriting the cmp" | A row click writes the current scene into that entry before any confirmation (`mov [esi],eax` 0x10014924) | **mechanism known** (cosmetic, left alone) | SAVE.md §4, FIXES.md F2 residual |
| 2026-08-10 .. 09-07 | **Can type at most one character** into the bookmark name; "had to click somewhere to get it to type" | Two bytes in the pack-lineage `i76shell.dll` (`+0x1C12B` `mov ecx,0x40` / `lea edi,[esp+0xC]` vs stock `0x41` / `[esp+8]`): ToAscii's output word is never cleared, so 'a' arrives as 0xB261. Stock bounds are correct. Field-confirmed as the one fix saving needs | **solved+verified** (2026-09-07 "yep that's it"); `fix-shell-textentry.ps1`, `PLAY-i76.ps1` guard, both installs hold `41 08` | SAVE-FREEZE-ROOT-CAUSE "second cause" and 09-07; FIXES.md F1/P4; memory "diff against pristine" |
| 2026-09-05 / 09-06 | Save Bookmark screen goes dead ~6 s after opening (one event, then nothing) | DWM ghosts the window: the modal edit loop (`TextField_Edit` inside `SaveMenu_Open`) and `Modal_YesNo` pump keyboard-only or nothing; `IsHungAppWindow` was a false instrument. Fix: `DisableProcessWindowsGhosting()` in u32x `DllMain` (uncap-lab `aff1c46`) | **solved+built, lab-shown by automation, deployed nowhere** (neither install's `u32x.dll` has the call). Not needed for prompt typing; **an unattended harness will hit it** | SAVE-FREEZE-ROOT-CAUSE 09-06 "ROOT CAUSE FOUND"; MENU-USABILITY-PLAN P4 / item 2; memory "count calls, not status flags" |
| 2026-09-05 | `CaptureMouse=true` "traps the pointer in the black bar" | Automation finding; James saved fine with `true` on 09-07; the automation's clicks were later shown unreliable | **open: records conflict**; one hand check. Field 2026-10-02 with `true` on the sandbox: the mouse is dead on the Save Bookmark screen only, keyboard saving works — the true/false regime test is backlog P1-02 | SAVE-FREEZE 09-05 vs 09-07; MENU-USABILITY-PLAN P1 caveat; memory "verify the click landed" |
| 2026-07-14 | Loaded save silently loses equipped weapons / parts | Load-time mount validation unmounts names that do not fit the chassis; the game also auto-mounts pool weapons into empty validated hardpoints | **mechanism known (field)**, exact shell site not cited | SAVE-FORMAT-GAPS.md "Load-time mount validation" |
| 2026-07-14 / 07-15 | Garage part colours "corrupt"/inconsistent across loads | Salvage pane colours are re-rolled at load; van/car colours stable; the stable state is not the cond field and is unlocated | **open** (not a save-corruption bug: file bytes unchanged across loads, TRUTH test) | SAVE-FORMAT-GAPS.md "CONDITION COLORS" and 07-15 |
| never reported, live lead | Car reloads with chassis 0 / height 0 / velocity 0 after a trip mission | Exe writer `bwd2_WriteVehicleStateVsf` 0x4b06b0 zero-fills VCST and never writes velocity, body+0x39 or chassis (two pointers both start at body+0xd, 0x4b082b / 0x4b082f); the in-game reader applies chassis body+0x1d to veh+0x148/+0x168 | **open** (static only; see §2.4 and H7) | i76-map subsystems\mission.md "Writer quirks"; data\notes\vcf-chain.md §3 |

Two tooling symptoms belong in this table because they look like game bugs from the outside [new]:

| | symptom | cause | status |
|---|---|---|---|
| T-a | `saves\Install-Saves.ps1` refuses a set as "truncated" | it checks `0x28 + 60n`; every game-written index (`4 + 60n`) fails that test, e.g. the lab's 364-byte file (wants 400) and `rescue-20260718` (844, wants 880) | **our bug**, fix proposed §6 |
| T-b | `saves\README.md` scene table is shifted by one record (save017 "no scene") | `i76-save-editor.py --list` reads record k+1's scene for record k (`e+0x38` with `e = 8+60k`) | **our bug**, fix proposed §6 |

## 2. The save/load data flow as understood now

Who owns what [fact: MENU-USABILITY-PLAN §4; shell CALLBACKS.md; mission.md Persistence]:

| file | writer | reader | when |
|---|---|---|---|
| `savegame.dir` | `i76shell.dll` `dir_WriteAndSave` 0x10032f80 (`"wb"`, `fwrite` count then 60-byte records) | shell `dir_Load` 0x10033020 (`"rb"`; drops records whose `.cmp` will not open) | written only on a bookmark save (Enter in the edit loop or the SAVE region, both via `cmp_Prepare` 0x10007310 then `dir_WriteAndSave(list, slot)`); read when the Save or Load menu opens. "Rewritten on exit" (Install-Saves.ps1 comment) has no code evidence: open, see H12 |
| `saveNNN.cmp` | shell `Cmp_Write` 0x10032980 via `SaveDir_WriteAndSaveCmp` (`wsprintfA("save%3.3d.cmp")` 0x10032ff3) | shell `Cmp_Read` 0x10032bf0 from `Screen_LoadBookmark` 0x10013380 (`"%s.cmp"` of the dir record's file field) | same pair serves `reconfig.spc` (written by `Garage_Frame` 0x100050da, read by `Screen_EnterReconfig` 0x10002781) and `trip4.spc` (written only at scene 3, read by ShellMain) |
| `ADDON\vehscn.vcf` | shell `Vehicle_WriteVcf` 0x10035250 -> exe callback 08 `WriteVcf` 0x4b0bd0, then cb 02 `RegisterFile` | exe `bwd2_LoadVcfForObject` 0x4ad6f0 for the player object (basename of 0x5dd370 + ".vcf"; the mission's own vcf is never loaded for the player) | written on bookmark load (0x1001348b) and on the other garage exits |
| `ADDON\vehscn.vsf` | **two writers**: (a) shell `Vehicle_WriteVehState` 0x10035930 -> cb 09 `WriteVehStateFile` 0x4b0b00 (VCST 0x4c from a shell record whose armour/chassis come from `GarageRec+0x7fc` / `+0x80c` of slot 0: `0x1005899c` / `0x100589ac` in the listing); (b) exe `bwd2_WriteVehicleStateVsf` 0x4b06b0 at mission **success**, trip missions only (0x404186..0x4041c8) | exe in-game: VCST 0x4b0350 / WLST 0x4b0540 / WPST 0x4b0610, only when `[0x6562c4]==2` (trip) and the file exists; shell: cb 06 `ReadVehStateFile` 0x4b7190 from `Screen_EnterReconfig` (0x10002989), then `VehState_ApplyToWorkingCar` 0x100029d0 | the lab has no `vehscn.vsf` at all today |
| `I76PLYR.DEF` | exe `player_SaveDef` 0x497290 (0x60 bytes from 0x654b40: options block, at mission end and on the graphics-mode key); **also the shell** `PlayerDef_Save` 0x10017050, called four times inside `Screen_LoadBookmark` (0x10013415, 0x10013437, ...) [new] | exe `player_LoadPlyrDef` 0x4970f0 after every shell return; shell `PlayerDef_Load` 0x10016f70 | options only, never campaign progress |
| `user.rpr` | shell `RepairOrder_Write` 0x10034420 | `RepairOrder_Read` 0x100347d0 | deleted on bookmark load (`RepairOrder_Delete` at 0x100133a5) |

### 2.1 What a bookmark holds [fact: SAVE.md §1-2, cmp-layout.md]

`savegame.dir` record (60 B at `4 + 60k`): `+0 u32 scene` (= `*ShellMain arg7` = exe 0x4c2160, the trip scene counter),
`+4 char[32] name`, `+0x24 char[16] file` ("save%3.3d"), `+0x34 u32 *arg11` = the exe's previous game state when the
shell was entered (**1 = mission success, 8 = Reconfigure from the in-mission menu**: mission.md state table, so
`+0x34` records how the player reached the garage before saving [new]), `+0x38 u32 flags & 2`.

`saveNNN.cmp`: `0x8c4` GarageRec of the current slot (armour/chassis 8 x u32 tenths at `+0x7fc`, equipped names at
`+0x400`, def refs at `+0x820/+0x82d`), `u32 nA`, nA x 0x74 inventory records (PartNode 0x20: `+0xc` condition,
`+0x10` state 1 fresh / 2 owned / 3 queued / 4 dropped; then PartRec 0x54), `u32 nC`, nC x 0x74 repair-queue references.
Section A is the inventory ring **plus** the part-pool list `[0x100f5308]` when it is non-NULL (loose end: cmp-layout.md).

### 2.2 What a load restores, and what it rebuilds [fact: `sdis.py fn 0x10013380`, SAVE.md, cmp-layout.md]

`Screen_LoadBookmark` 0x10013380 (message 0xC01D, posted by the Load menu's LOAD region after it copied the chosen
record to `0x100579e8`, 0x10013262 / 0x10013264):

1. sets the garage slot index `[[0x100c5ad8]+0x38] = 0` (0x10013394); `RepairOrder_Delete`, `PartPool_Free`,
   `Inventory_ResetState`;
2. `Cmp_Read("saveNNN.cmp")`: GarageRec into slot 0; every section-A record appended to the inventory ring (pool and
   ring are not told apart on disk); section C resolved back to ring nodes by condition + state 3 + file name,
   unmatched references dropped silently;
3. **restores the scene counter**: `*0x100d2180 = record.scene` (0x100133db..0x100133e9, i.e. exe 0x4c2160) and
   `*0x100d2164 = record.+0x34` (0x100133eb..0x100133fb: the exe's "previous game state" slot) [new];
4. play mode `[[0x100c5ad8]+0x20] = 2` (trip), `PlayerDef_Save`;
5. on the `[0x10057a20] & 2` branch rebuilds the part pool from the catalogue (cb 00, `PartPool_BuildFromCatalogue`
   0x1001347f), then **writes `addon\vehscn.vcf` and `addon\vehscn.vsf` from the loaded GarageRec** (0x1001348b,
   0x100134a0) and registers them (cb 02);
6. posts the next screen; the harness observed the Car/Van Inventory (0xC017, ACCEPT SALVAGE) then the garage (0xC00F).

So the mission start reads the car from files the shell just wrote, not from the `.cmp`: the exe never reads a `.cmp`.
Rebuilt, not restored: the part pool, the garage region lists, salvage colours (render-time), ammo (never stored),
the repair order file. Restored only through the vsf: current armour/chassis to veh+0x138/+0x158 and +0x148/+0x168,
component hit points, wheel hp, WPST weapon state. Not restored by the exe: SALV (no in-game handler), the design
maxima at +0x178/+0x18c (stay at the vcf values, doubled in single player by 0x463120).

### 2.3 Where the in-mission "Load Bookmark" goes [fact: mission.md state 9; CALLBACKS.md arg 11]

The exe's Esc menu item `Load Bookmark` (0x495940) sets game state 9; WinMain takes the generic end path and calls
`shell_RunAndGetChoice` with arg 11 = 9. ShellMain's first-screen choice (0x1001e4ca..0x1001e749) is documented for
arg11 == 5 (main menu) and 2/8/1 (post-mission flow); **the 9 branch is not documented** - whether it lands on the main
menu or straight in the Load Bookmark menu (menu fn 0x10013060) is an **unknown** the protocol below reads out with
`shellstate.ps1`. The exe's in-mission menu has **no Save item** (items: Load Bookmark, Abort Mission, Play Options,
Graphic Detail, Audio Control, Exit; `foldin\shell-menu-items.tsv`): saving is shell-only, from the garage.

### 2.4 The chassis-0 lead, located [fact: mission.md "Writer quirks"; vcf-chain.md §3; this pass]

After a won trip mission the **exe** writes `ADDON\vehscn.vsf` (0x4041b3) and hands control to the shell with arg11 = 1.
`bwd2_WriteVehicleStateVsf` 0x4b06b0 zero-fills VCST, fills armour through two pointers that both start at body+0xd,
and never writes chassis (body+0x1d), velocity (+0x2d) or the height (+0x39). The shell's post-mission flow reads that
file through cb 06 (`Screen_EnterReconfig` 0x10002989) and applies it with `VehState_ApplyToWorkingCar` 0x100029d0
(304 instructions, **not traced**: whether VCST chassis reaches `GarageRec+0x80c` is the open link). If it does, every
bookmark saved after a won mission carries chassis 0 in its GarageRec, and the next shell-written vsf propagates it to
the car. Against this: the single sample `sandbox-gog\...\vehscn.vsf` has chassis 600x4 and flags 1,1,1, which fits
either writer (the exe writes export records 17-19 to +0x49..+0x4b; the shell copies all 76 bytes). The lab's own
saves have non-zero chassis in `+0x80c` (the editor's armour @2044 rows were verified against the Build and Repair form
in July), so if the leak exists it is not unconditional. H7 in §3 is the test.

## 3. Hypotheses for "corruption / won't load", each with a test

Symptom classes: (a) bookmark missing from the LOAD list; (b) wrong mission loads; (c) car wrong after load (armour,
chassis, parts, weapons); (d) the save itself hangs. (d) is P1..P4 above, solved; the rest:

| id | hypothesis | prior | confirming test | killing outcome |
|---|---|---|---|---|
| H1 | **Slot reset on edit re-entry** (F2): typed name, click off, click the name field, type, SAVE -> dir record `saveS`, file `save-001.cmp` (Windows) | high (static trace, 3 instruction sites) | LIVE-TESTS **T3** exactly: stock control first, then F2 (u32x route B or `patched\i76shell-F2F3F4F6.dll`). Parse the dir with `4+60n`; list `save-00*.cmp` | stock does not orphan on the trigger sequence -> SAVE.md §4 is wrong at step 1 or 2; read `lastwidget` / `menu_fn` with `shellstate.ps1` before concluding |
| H2 | **Non-numeric file field makes the allocator return -2** (`sscanf("%d")` fails, stack local uninitialised, `max+1` = -1) | medium (foldin S11; explains "intermittent" without a second edit pass) | craft a dir on the lab copy with one record whose file field is `COLORCAL` (keep a matching `.cmp` so `dir_Load` keeps it); one-pass typed save | a correct `saveS.cmp` appears -> the local is initialised and S11 is dead |
| H3 | **Our editor writes the wrong record's scene** (reads/writes `0x40+60k` = record k+1's `+0`); "COLOR CAL loaded save007's bytes" class of report | high for the read side (`parse_dir`, lines 239-258 [new]); write side (`i76-save-editor.html` / `-server.py`) to be checked by the same rule | editor: set slot k's scene; `python`-parse before/after with the §1 layout: record k+1 `+0` changes, record k does not | the write lands at record k `+0` -> only the read side is wrong |
| H4 | **`dir_Load` drops any record whose `.cmp` fails to open**, so file clutter / rename / glob mistakes read as "my bookmark vanished", and the next save rewrites the dir without it (entry lost for good, `.cmp` intact) | certain (0x100330b9) | rename `save002.cmp` away, boot, open Load Bookmark: 5 rows not 6; save once; restore the file: the dir no longer names it | n/a (mechanism is read from code); the test measures the data-loss consequence |
| H5 | **Save written while the vehicle record is mid-update** | low: `Cmp_Write` runs on the shell's thread inside its modal loop while the exe is blocked in `ShellMain`; no second writer | with the save screen up, read the live GarageRec (`i76shell.dll` base + 0x581a0 + 0x8c4*slot, 0x8c4 bytes, `PROCESS_VM_READ`) immediately before the SAVE click; compare with the written `.cmp` head | any byte differs -> something mutates the record between the read and `fwrite`; otherwise kill H5 |
| H6 | **Partial `savegame.dir` when the mouse proxy interrupts** | very low: `dir_WriteAndSave` is `fwrite` x (1+n) then `fclose` with no pump; u32x only wraps USER32 calls; only a crash mid-write could truncate | every run: `size == 4 + 60*count` and every record's `.cmp` opens; grep `u32x.log` (log build) for a translation call between the SAVE click and the file mtime | a dir that is not `4+60n` after a clean save would be the first ever seen (15 of 15 on disk pass) |
| H7 | **Mismatched vehscn.vsf after a trip**: exe-written file carries chassis 0 / v 0 / height 0; the shell applies it to the working car; the next bookmark and the next vsf carry chassis 0 | medium (static; one sample fits either way) | three snapshots with `i76mod.py show ... VCST`: (1) right after a won trip mission returns to the shell (exe write, before any garage click), (2) after DONE in the garage, (3) in the next mission read veh+0x148..+0x154 (`memlib.ps1`) and parse the bookmark saved in between (`GarageRec+0x80c`) | (1) shows the pre-mission chassis -> the writer does write chassis and mission.md's reading is wrong; (1) shows 0 but (2)/(3) are correct -> the shell repairs it from the GarageRec; (3) shows 0 -> the leak is real and `VehState_ApplyToWorkingCar` is the site |
| H8 | **`+0x34` (1 vs 8) steers the post-load flow** (restored into the exe's previous-state slot at 0x100133fb) | low-medium | load `save002` (`+0x34`=1) and `save003` (`+0x34`=8) back to back; record the screen sequence with `shellstate.ps1` | identical sequences -> the field is inert on load |
| H9 | **Pool parts folded into section A** when `[0x100f5308]` is non-NULL at save time: fresh catalogue copies come back as owned inventory on load (inventory inflation, "free parts") | medium (cmp-layout.md loose end) | on the Save screen read `[0x100f5308]` (base + 0xf5308); compare nA in the written `.cmp` with the ring length read live; load it and count (V) rows | `[0x100f5308]` is NULL at bookmark time -> nothing to fold |
| H10 | **Mount validation strips non-fitting equipped names** silently -> "my weapons vanished" | high (field, 07-14) | editor: equip a turret-class gun on the Piranha in a copy; load; (C) rows and `WEPN` chunks of the shell-written `vehscn.vcf` | n/a; the test fixes the exact rule (which names, which slots) |
| H11 | **Label off by one is read as "wrong mission loads"**: "Scene N." = stored scene + 1 when `+0x34 == 1` | high [new, static] | boot, open Load Bookmark on the lab set, read the six labels; predicted: Scene 2, 3, 4, 5, 6, 6 for stored 1,2,3,5,6,6 with `+0x34` 1,1,1,8,8,8 | any label differs -> re-read 0x10013736..0x10013759 |
| H12 | **`savegame.dir` is rewritten on exit** (Install-Saves.ps1 comment) | low (no code site found) | mtime of `savegame.dir` before and after a clean quit with no save | mtime unchanged -> drop the comment |

## 4. Sandbox protocol that runs without a human

### 4.0 Corrections to the brief, before the steps

- **`I76_MISSION` boots cannot save.** The proxy sets the skip-shell dword `0x504c10 = 1`, the mission loads with no
  shell, the exe's Esc menu has no Save item, and with `0x504c10` set every end state except 7 (replay) exits the game
  (mission.md state 0xa row; MENU-USABILITY-PLAN E1). The direct boot also drives `vppirna1` (no vsf), not the trip car.
  So the save leg has to go through the shell: cold boot -> main menu -> TRIP -> LOAD BOOKMARK -> LOAD -> inventory ->
  garage -> SAVE BOOKMARK. That is the path the 2026-09-05 automation already clicked through end to end.
- **The garage has a SAVE BOOKMARK button of its own.** Garage region 11 (`0x100433d8` table, 8-dword records
  `{id, type, x0, x1, y0, y1, aux, 0}`: id 11 = x 490..631, y 450..469) jumps to 0x100044ab, which sets `pending = 1`,
  `next = 1` = the Save Bookmark menu directly (jump table 0x100051f0 entry 11) [new]. The harness header
  (`autotest\setup\find-weapon-ui.ps1`) names the bottom row DONE / FIELD SALVAGE / SAVE BOOKMARK, consistent with
  region 9 (330..469, DONE: `Garage_ValidateCar` then on) and region 7 (170..309, posts 0xC017 / 0xC01F).
- **Typing is the weak link.** Synthetic `keybd_event` landed **zero** characters on this screen where a human lands
  one (SAVE-FREEZE "Still to verify by hand"). The protocol therefore has a no-typing leg (Enter on the pre-filled
  name = overwrite path) and a typing leg with three escalating injection methods; a leg that cannot type is reported
  as such, not worked around silently.
- **State 9 is the load leg's second variant**, reachable only on a normal boot (see 2.3).

### 4.1 Pre-flight (all read-only or reversible; abort on any failure)

1. `TerminalServerSession` must be False; `query session` must show `>console` (AGENTS.md). `tools\rdp-to-console.cmd`
   hands an RDP session to the console if needed.
2. No `i76*` process; `.console-test.lock` absent (TEST-FRAMERATE.ps1 convention); then take the lock.
3. **Back up** `savegame.dir`, `save*.cmp`, `ADDON\vehscn.*`, `reconfig.spc`, `trip4.spc`, `user.rpr`, `I76PLYR.DEF`
   to `save-backup-<ts>\` in the lab folder, with md5s.
4. Identity checks: `i76shell.dll` bytes `0x1B52C == 0x41`, `0x1B535 == 0x08` (F1); `deploy-shellfix.ps1 -Status` shows
   both binaries PATCHED; **`u32x.dll` must contain the string `DisableProcessWindowsGhosting`** - the harness sits on
   the Save screen longer than 5.9 s, so without it the screen dies mid-test (P4). Today's lab `u32x.dll` fails this
   check: rebuild and deploy per MENU-USABILITY-PLAN item 2 first. Record `dgVoodoo.conf` `CaptureMouse` (the click
   library handles both regimes; the value is a test condition, not a variable to change mid-run).
5. Start with the lab set as it is (six bookmarks; §0). The A/A rule: run leg A twice before leg B.

### 4.2 Leg A: save a bookmark

Coordinates are in the shell's 640x480 UI space, click = rectangle centre; the harness maps them to the screen
(`autotest\lib\uiclick.ps1` measures the live client rect; for the 3440x1440 pillarbox `screen = (760 + 3*ux, 3*uy)`).
Confirm every click by state, not by picture: `i76-map\shell\tools\shellstate.ps1` prints `screen`, `menu_fn`,
`modal_fn`, `mouse`, `lastwidget` twice a second.

| step | input | expected state (`shellstate.ps1`) | source of the coordinate |
|---|---|---|---|
| A1 | launch `game\i76.exe -glide` (no `I76_MISSION`; `I76_SKIP_MOVIES` is a no-op without it, MENU-USABILITY-PLAN P9); wait 9 s | window up | enter-mission5.ps1 |
| A2 | Esc, Enter, repeated up to 6 times at 300/800 ms | `screen = 0xC00E`, `screen_fn = 0x10025a50` (main menu) | enter-mission5.ps1 step 1; FINDINGS-2026-07 (Esc skips the intro) |
| A3 | click TRIP **(217, 311)** [rect 167..267 x 286..336] | TRIP sub-menu buttons appear (`-Buttons` dump shows id 10/11/12 rows) | SCREENS.md main-menu table (sprite-decoded) |
| A4 | click LOAD BOOKMARK **(276, 351)** [216..336 x 340..362] | `menu_fn = 0x10013060` (LoadBookmark) | SCREENS.md; harness used (298,346), inside the same rect |
| A5 | click the wanted row: **unknown statically** (the region list is built at run time into `0x10057a2c`); harness-measured rows: 3rd entry at UI **(203, 261)**, 4th at **(203, 278)** (screen 1370,782 / 1370,833); rows are ~17 UI px apart | `[0x10046e70]` = row index (write at 0x1001318c); label text per H11 | enter-mission5.ps1 `-SceneY`; read the exact row off a `Capture-UI` screenshot if the list differs |
| A6 | click LOAD **(352, 428)** (screen 1817,1284; the Load menu's jump-table case 3 copies the record to `0x100579e8` and arms 0xC01D) | `screen = 0xC01D` then **0xC017** (inventory), `screen_fn = 0x10018e90` | enter-mission5.ps1; `sdis.py fn 0x10013060` |
| A7 | click ACCEPT SALVAGE **(412, 460)** (screen 1995,1379) | `screen = 0xC00F`, `screen_fn = 0x10003e70` (garage) | enter-mission5.ps1 |
| A8 | **snapshot 1**: md5 + size of `savegame.dir`, `save*.cmp`, `ADDON\vehscn.vcf`, `ADDON\vehscn.vsf`, `reconfig.spc`, `user.rpr`, `I76PLYR.DEF` (the bookmark load has just written vehscn.vcf/.vsf) | | §2.2 |
| A9 | click SAVE BOOKMARK **(560, 460)** [garage region 11: 490..631 x 450..469] | `menu_fn = 0` while the edit loop runs inside `SaveMenu_Open` (T1 prediction), name field shows "Scene N." pre-filled with the caret | this pass: table 0x100433d8, `Garage_Frame` 0x100044ab |
| A10a | **no-typing leg**: press Enter (commit, `SaveMenu_Edit` ebx==1 -> 0x10014a78). The pre-filled name matches the loaded row's scene and name only if that row was unnamed and same-scene; otherwise it is a new slot. Expect either the overwrite prompt or a direct save | prompt: `modal` loop; the drawn text "Overwrite an existing bookmark?" | SAVE.md §3-4 |
| A10b | **typing leg**: type `AUTOSAVE1` then Enter. Injection methods in order, each verified by reading the name buffer `i76shell.dll` base + 0x57f3c (32 bytes) before Enter: (i) `keybd_event` scan codes (`Send-Key`); (ii) `SendInput` with `KEYEVENTF_SCANCODE`; (iii) `PostMessageA(hwnd, WM_KEYDOWN/WM_KEYUP, vk, lParam)` to the game window, since `KeyInput_Poll` drains `PeekMessageA(WM_KEYFIRST..WM_KEYLAST)` and translates with `ToAscii` itself (SAVE-FREEZE 08-16). If none lands, report "typing not automatable" and fall back to A10a | buffer equals the typed text | SAVE-FREEZE-ROOT-CAUSE (ring buffer, `+0x1D630`); SAVE.md §3 |
| A10c | **orphan-trigger leg (T3)**: type `ORPHANA`; click empty paper right of the list, e.g. **(500, 300)** (outside every region in 0x10047600); click the name field **(318, 138)** [183..454 x 127..150]; type `ORPHANB`; click SAVE **(354, 428)** (measured live 2026-09-05 at screen 1821,1285; x set at run time, y 417..434) | stock: dir names `ORPHANB` -> `saveS`, no `saveS.cmp`, a new `save-001.cmp`; F2: `saveS.cmp` exists | LIVE-TESTS T3; SAVE.md §4 |
| A11 | if the overwrite prompt is up: YES **(393, 258)** [369..418 x 245..272] or NO **(450, 258)** [428..472 x 245..272] (FIXES.md F3 rectangles 254..303 / 313..357 relative to (115,130)). Note: the 2026-08-10 unstick click at UI (470,255) falls in **NO** by these numbers while the doc called it YES - verify with the F6 readout before trusting either label | prompt closes; `.cmp` mtime changes on YES only | FIXES.md F3; SAVE-FREEZE "proof" |
| A12 | **snapshot 2** (same list as A8) within 1 s of the save; then CANCEL (x unknown: read off a capture; y 417..434) or Esc (-> Options menu, 0x10014f7b) | `menu_fn = 0x1000e6b0` after Esc | SAVE.md §3; SCREENS.md |
| A13 | quit: Options (garage layout 0x10044780) -> Exit Interstate '76 **(212, 400)** [row at (202,395)] -> Exit Game confirm (menu 2, table 0x10046b40, **widget coordinates not decoded**: read off a capture, or `tools\widgets.py 0x10046b40`); fallback `Stop-Process` after snapshot 2 (the dir and `.cmp` are closed at save time, so a kill loses nothing; it also answers H12 by comparison with a clean quit) | process gone | SCREENS.md Options rows |

### 4.3 Parse and diff (byte-exact)

Parsers that exist [fact: ran today]:

```
python C:\Users\james\i76-map\data\mod\i76mod.py show <game>\ADDON\vehscn.vsf            # chunk list: REV VCST WLST WPST#n EXIT
python C:\Users\james\i76-map\data\mod\i76mod.py show <game>\ADDON\vehscn.vsf VCST       # armour[4] chassis[4] velocity f39 engine/brake/susp hp flags
python C:\Users\james\i76-map\data\mod\i76mod.py show <game>\ADDON\vehscn.vsf WPST#0
python C:\Users\james\i76-map\data\mod\i76mod.py show <game>\ADDON\vehscn.vcf VCFC       # variant vdf vtf ids wdf x3 armour chassis spare
python C:\Users\james\i76-map\data\mod\i76mod.py show <game>\ADDON\vehscn.vcf WEPN#0
```

**No `.cmp` or `savegame.dir` parser exists in the data track** (FORMATS.md §10 assigns them to the shell track; `shell\tools`
has none) and `i76-save-editor.py` carries the misframed models. Until a `shell\tools\savedir.py` is written **[proposed]**,
the checks are the inline ones used in §0 of this file (Python `struct`): dir `size == 4 + 60*count`, record k at
`4 + 60k` = `{u32 scene, char[32] name, char[16] file, u32 a11, u32 flags}`; cmp `size == 0x8c4 + 8 + 0x74*(nA + nC)`
with `nA` at `0x8c4` and `nC` at `0x8c8 + 0x74*nA`; GarageRec armour/chassis = 8 x u32 at `+0x7fc`; each record
`PartNode(+0xc cond, +0x10 state)` then `PartRec(+0 name, +0x1e type, +0x3b file, +0x4c full)`.

Diff snapshot 1 vs 2:

| file | pass |
|---|---|
| `savegame.dir` | size `4 + 60n`; n = n0 + 1 (new slot) or n0 (overwrite); the new/changed record: scene = the loaded row's scene, name = typed text (or the pre-fill), file = `save%03d` of `max(existing)+1` for a new slot; `+0x34` = 1 if the loaded row had 1 (it is restored at 0x100133fb and saved back at 0x100149b6) **[prediction to confirm]** |
| `saveNNN.cmp` | exists for every dir record; size formula holds; GarageRec `+0x7fc..+0x81b` equals the live record read in A9 (H5) and the loaded bookmark's values unless the garage changed them; no `save-00*.cmp` anywhere except in the T3 stock control |
| `ADDON\vehscn.vcf/.vsf` | unchanged between snapshot 1 and 2 (a save writes neither); VCST armour/chassis x10 == GarageRec `+0x7fc` tenths of the loaded bookmark [prediction] |
| `I76PLYR.DEF` | 96 B; byte-diff only (changed by `PlayerDef_Save` on load, not expected to change on save) |
| `reconfig.spc`, `user.rpr` | unchanged by a bookmark save |
| `mciproxy.log`, `captures\save\u32x.log` (log build only) | no `ABORTED`; census shows `GetCursorPos` still ~30 per 500 ms through the whole Save screen (no `WM_ACTIVATE 0`) |

### 4.4 Leg B: load the bookmark just written and verify the car

B1 cold boot (A1-A4); B2 pick the new row (its label per H11: scene+1 when `+0x34 == 1`); B3 LOAD, ACCEPT SALVAGE,
**snapshot 3** of `ADDON\vehscn.vcf/.vsf` (now written from the just-loaded GarageRec); B4 DONE **(400, 460)** [region 9:
330..469 x 451..468] -> mission; B5 skip the cutscene (Esc + click, enter-mission5.ps1 step 5) until
`Mem-InMission` and entities > 0 (`autotest\lib\memlib.ps1`).

Verify in memory (`memlib.ps1`, `Mem-PlayerEntity` = the vehicle class-data block):

| read | expected | note |
|---|---|---|
| veh `+0x138..+0x147` armour, `+0x148..+0x157` chassis | = snapshot-3 VCST `armour[]` / `chassis[]` (restored x1 by the VCST handler 0x4b0411..0x4b0490) | the vcf path doubles (0x463120) but the vsf write is raw; if +0x138 reads 2x, the VCST restore did not run (then check `[0x6562c4] == 2` and that `vehscn.vsf` existed at load) |
| `+0x178..`, `+0x18c..` | = 2 x `vehscn.vcf` VCFC armour/chassis (design maxima) | data LIVE-TESTS T1/T2 |
| `[0x4c2160]` scene counter | = the dir record's scene | restored at 0x100133e9 |
| mission file `[0x5049f0]` | `t%02d.msn` of that scene | ShellMain 0x1001eb3d |
| equipped weapons | `WEPN` chunks of snapshot-3 `vehscn.vcf` match the `.cmp` GarageRec `+0x400` names that fit the chassis (H10) | |

**Variant B' (state 9):** from inside the mission press Esc (exe menu, mode 0x10), click `Load Bookmark` (coordinates
from the exe's `*.map` pages: **not decoded**; the exe menu takes keyboard - arrows + Enter - per the harness README),
game state -> 9, and read with `shellstate.ps1` which shell screen comes up (closes the 2.3 unknown). Then B2-B5 again.

### 4.5 Pass / fail, whole protocol

- PASS: every file invariant in 4.3 holds in both A/A runs; leg B reads the written bookmark's values in the car; no
  `save-00*.cmp` outside the T3 stock control; no process hang (`GetCursorPos` census never collapses).
- FAIL (data): any dir not `4+60n`, any `.cmp` off the size formula, any record whose `.cmp` is missing, chassis 0 in
  veh+0x148 after a load of a bookmark whose GarageRec chassis is non-zero.
- FAIL (harness, not game): typing lands nothing by all three methods -> report; `Capture-UI` byte-identical frames ->
  focus loss, rerun (`Force-Foreground`, `EnableInactiveAppState` is already true).
- Report n for every measurement and the lab's `CaptureMouse` value.

## 5. What is not automatable and needs James at the console

1. **Typing at human speed** into the name field, several characters, with the shipped (no-log) `u32x`: the one thing
   the harness has never reproduced (zero characters land). Also the overwrite prompt answered by mouse at its visual
   position, and "no wake-up click needed" (SAVE-FREEZE "Still to verify by hand").
2. **The `CaptureMouse` regime check** (true vs false with the shipped u32x: does TRIP highlight on hover, do YES/NO
   land where drawn) and the **in-mission Esc menu mouse** after the exe retarget (P11), both one launch each.
3. **Lossless Scaling** over a shell prompt (P15): `PLAY-i76.ps1 -LosslessScaling ""`, trigger an overwrite prompt.
4. **A won trip mission** for H7: the harness cannot reliably finish a mission (TESTING-SETPIECES: it could not even find
   the canyon ramp). James plays t02 or t03 to success on the lab copy, stops at the first shell screen, and the
   snapshots of §3 H7 are taken then. The FSM injection `T6-fsm-inject` (data LIVE-TESTS) could force `successAll` on
   T01 unattended - **[proposed]** as the automatable substitute, untested.
5. **Judging labels and art**: which bottom-row caption sits on garage region 7 (FIELD SALVAGE vs CATALOG), the Exit
   Game confirm layout, the Load list's first-row y. Each is one `Capture-UI` screenshot read by a person (or the F6
   coordinate readout, `01 -> 00` at file 0x45f20 on the lab shell).
6. **Promotion to the daily driver**: F2, the ghosting-fixed u32x and any dgVoodoo change go to the portable only after
   the lab passes and James says so (MENU-USABILITY-PLAN §5 rule).

## 6. Corrections to make elsewhere (proposed, not made here)

- `saves\README.md`: the scene column is shifted by one record. Correct values (SAVE.md layout, read today): save000 1,
  save001 2, save002 3, save008 5 TRUTH, save009 6 TURRET TEST, save010 7 Yay!, save011 9, save012 10 GOT IT, save013 11
  Easy Groove!, save014 12 OOOH SHIT, save015 13 TRUCK STP SECURE, save016 14 County Line, **save017 15 So Many
  Turrets** (all `+0x34 = 1`, so the LOAD board prints each as scene+1: "Scene 16." for save017). "Ships with no scene"
  and "its index record lost its scene dword" are the editor's read past EOF, not a missing byte. `rescue-20260718` is
  not truncated (844 = 4 + 60*14). The "index is written short" section describes our padding, not the game.
- `saves\Install-Saves.ps1`: the refusal test must be `size >= 4 + 60n` (today it rejects every unpadded game-written
  index, including the lab's).
- `i76-save-editor.py` `parse_dir`: entries at `4 + 60k`, scene at `+0`, name at `+4`, file at `+0x24`, state at
  `+0x34`; drop the "truncated at EOF" branch. Check the HTML/server writer for the same off-by-one before anyone
  edits a scene with it (H3). Its `.cmp` model should adopt the count-prefixed node-first layout (cmp-layout.md).
- `AGENTS.md` invariant, `PLAY-i76.ps1` re-pad block, `LAUNCHER.ps1 Get-Health`: `4 + 60n`, never truncated (already
  proposed in MENU-USABILITY-PLAN §6 and SAVE.md §1).
- SAVE-FORMAT-GAPS.md: the LOAD-label anomaly is closed (scene+1 when `+0x34 == 1`); `+0x34` is the exe game state
  the shell was entered with (1 success, 8 reconfigure).
- shell SAVE.md §6: the `*arg11` naming blocker is answered by mission.md's state table (1 / 8).
- i76-map `foldin\formats-saves-ffb-community\REPORT.md` open question 1 ("which dword is the scene and what
  'Scene %d.' prints"): answered above.

## Sources

i76-everywhere: docs/SAVE-FREEZE-ROOT-CAUSE.md, SAVE-ORPHAN-INVESTIGATION.md, SAVE-FORMAT-GAPS.md,
SHELL-MENU-AND-SAVE-FREEZE.md, READY-TO-TEST.md, VERIFIED-FIXES.md, MENU-USABILITY-PLAN.md, MISSION-LAUNCH.md;
i76-save-editor.py (docstring, `parse_dir`), i76-calibration-saves.py, saves/README.md, saves/Install-Saves.ps1,
tools/fix-shell-textentry.ps1, PLAY-i76.ps1 (re-pad and text-entry guards), AGENTS.md (invariants, RDP), CHANGELOG.md.
i76-uncap-lab: src/u32x.c (DllMain, ghosting), TEST-FRAMERATE.ps1 header, tools/instruments/deploy-shellfix.ps1,
autotest/README.md, autotest/enter-mission5.ps1, autotest/lib/uiclick.ps1, autotest/setup/find-weapon-ui.ps1,
docs/TESTING-SETPIECES.md; game folder listing and dgVoodoo.conf (read-only).
i76-map: shell/SAVE.md, SCREENS.md, FIXES.md, CALLBACKS.md, LIVE-TESTS.md, INPUTMAP.md, README.md, work/cmp-layout.md,
work/exe-callbacks.md, symbols/functions.tsv, tools/sdis.py listings of 0x10013060, 0x10013670, 0x10013380, 0x10003e70,
0x10002750, 0x10035930 and the tables 0x10047600 / 0x100433d8 / 0x100051f0 / 0x10013364; data/FORMATS.md,
data/LIVE-TESTS.md, data/fmt/l_vcf.py, data/mod/i76mod.py, data/notes/vcf-chain.md; subsystems/mission.md;
status/findings.md (L049, L054, L065); foldin/shell-menu-items.tsv, foldin/formats-saves-ffb-community/REPORT.md;
sandbox-gog/main/app/ADDON/vehscn.vsf (parsed). Memory notes applied: misframed layout, verify the click landed, same-rate
control run, never experiment on the daily driver, count calls not status flags, diff against pristine.

## Done after this plan was written (2026-10-01, same day)

- The off-by-one in §6 is fixed in `i76-save-editor.py` and `i76-save-editor.html` (all five directory functions),
  with a node regression test `tools/tests/test-save-editor-dir.mjs` run against the lab's game-written directory.
- `saves/Install-Saves.ps1`, `saves/install-saves.sh`, `PLAY-i76.ps1`, `i76-launch-stub.swift` and
  `i76-calibration-saves.py` use the real frame (4 + 60 x count).
- `saves/README.md` scene table corrected (save017 is scene 15); the rescue index was never truncated.
- Leg A is being run by a sandbox harness under `../i76-uncap-lab/autotest/saves/`; its report is
  `SAVES-LEG-A-RUN-2026-10-01.md` when it lands.
- Leg B passed (`SAVES-LEG-B-RUN-2026-10-01.md`): the Leg-A bookmark loads into t05 with the car matching its .cmp;
  an editor-modified directory (scene 5 -> 3, one byte) loads t03. State-8 records load the dword as-is; state-1
  records play scene+1. The garage DONE writes vehscn.vcf/.vsf (chassis non-zero) and reconfig.spc; the bookmark
  load itself writes only I76PLYR.DEF. The chassis-0 lead does not apply to this path.

