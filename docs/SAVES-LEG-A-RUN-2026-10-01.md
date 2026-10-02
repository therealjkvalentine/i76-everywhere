# Saves protocol, Leg A: sandbox run 2026-10-01

*Unattended run of SAVES-STATE-AND-TEST-PLAN.md section 4 (4.0-4.3, Leg A) on the lab copy
`C:\Users\james\i76-uncap-lab\game`, physical console, nobody at the machine. Harness written for this run:
`C:\Users\james\i76-uncap-lab\autotest\saves\` (`leg-a.ps1`, `parse_saves.py`, `ui_i76.py`). Per-run evidence
(log, screenshots, snapshot JSON, parsed listings, proxy log slice) under `autotest\saves\runs\<ts>-<mode>\`.
No repository source file was edited. Every claim below is from the run log or the files on disk; nothing is
inferred from a screenshot alone.*

## 0. Result in one paragraph

Leg A **passes** on both legs. Four launches: two aborted on harness bugs before any save (19:08 TRIP click
placed by the wrong mapping; 19:12 a helper named `Rd` resolved to the `Remove-Item` alias), then **run 3
(19:14, Enter path)** overwrote `save003` through the overwrite prompt, and **run 4 (19:16, typing path)** wrote
a new bookmark `save006`. Every file invariant in plan 4.3 held: `savegame.dir` is `4 + 60n` both times (364 then
424), every `.cmp` satisfies the size formula, no `save-00*.cmp` orphan appeared, `vehscn.vcf`, `reconfig.spc`,
`trip4.spc` unchanged by the save, `I76PLYR.DEF` changed on load only. **Synthetic typing lands**: keybd_event,
SendInput and PostMessage WM_KEYDOWN all put characters into the name field (the "zero characters" record is
retired for this shell build). The YES button is where FIXES.md F3 says (UI 369..418 x 245..272); the (470,255)
"unstick" click of 2026-08-10 was NO. The Save screen did **not** ghost: the edit loop sat 6.0 s in run 4 and
`IsHungAppWindow` stayed false throughout. Sandbox restored: original `STRLKUP.DLL` back (md5 54f2de9d...),
lock removed, no `i76*` process. The lab save set is now the post-test set (7 records); the pre-test set is in
`game\save-backup-20261001-190810\` with `md5.txt`.

## 1. Pre-flight (plan 4.1)

| item | result |
|---|---|
| 1. session | `TerminalServerSession = False`; `query session` shows `>console james 1 Active` |
| 2. process / lock | no `i76*` process; `.console-test.lock` absent; taken by `leg-a.ps1` for each launch and removed in `finally` |
| 3. backup | `game\save-backup-<ts>\` per launch with `md5.txt`: savegame.dir 9e15bd6e... 364 B; save000..005.cmp 96459ac3 / 939f0463 / 34acb28c / f1c4d535 / d53e1c5c / e8e1af48; reconfig.spc 0d916ca3 10604 B; trip4.spc d14f5dd4 9212 B; I76PLYR.DEF 88dfbc75 96 B; ADDON\vehscn.vcf 7c5befb2 309 B; **user.rpr and ADDON\vehscn.vsf do not exist** in the lab folder |
| 4. identity | `i76shell.dll` 0x1B52C = 0x41, 0x1B535 = 0x08 (F1 repaired); `deploy-shellfix.ps1 -Status`: i76shell.dll PATCHED, i76.exe PATCHED, u32x.dll present; `i76.exe` md5 4FABC303..., imports u32x; **`u32x.dll` does not contain `DisableProcessWindowsGhosting`** (known blocker, proceeded as instructed; outcome in section 5) |
| 4. dgVoodoo.conf | `CaptureMouse=true`, `FreeMouse=false`, `FullScreenMode=false`, `ScalingMode=stretched_ar`, `EnableInactiveAppState=true`; two `Resolution` lines (3360x2100 first, Glide 1680x1050), both 16:10 |
| 5. start set | the six-bookmark lab set of plan section 0, re-parsed identically by `parse_saves.py` before the first launch |
| proxy | `music-fix\Strlkup.dll` (md5 2347e1cb..., 155,648 B) copied over `STRLKUP.DLL` after `STRLKUP.DLL.pretest` (md5 54f2de9d..., 117,248 B); env: all `I76_*` cleared, `I76MUSIC_LOG=1` only |

## 2. Step table, run 3 (Enter path, `runs\20261001-191411-enter\`)

Times are seconds from harness start; state is the shell globals read with ReadProcessMemory
(`0x100d2168` screen, `0x100d219c` screen fn, `0x100d21a0` menu fn, mouse object `0x100cc514`, `next` `0x100d2194`),
`i76shell.dll` loaded at 0x3170000. Coordinates are UI 640x480 = OS cursor 1:1 (see section 6).

| step | t | input | state reached (read from memory) |
|---|---|---|---|
| A1 | 12.1 | `i76.exe -glide`, pid 20212, Force-Foreground while booting | window 3440x1440 at 0,0; shell DLL loaded; screen 0 (movie) |
| A2 | 14.7 | Esc, Enter x2 (second try) | `screen=0xC00E` main menu, `sfn=0x10025a50` |
| A3 | 16.6 | click TRIP (217,311), shell mouse read back (217,311) | main-menu button list `[0x100d3e7c]` count 4 -> 3 (TRIP sub-menu replaces the row) |
| A4 | 18.5 | click LOAD BOOKMARK (276,351) | `mfn=0x10013060` LoadBookmark, `next=11` |
| A5 | 19.7 | click row (203,261) | `[0x10046e70]` -1 -> 3 (4th row, label "SCENE 5.") |
| A6 | 20.6 | click LOAD (352,428) | `screen=0xC017` inventory, `sfn=0x10018e90`; record copied to `0x100579e8`: scene 5, name '', file save003, +0x34 8; scene counter `0x4c2160` = 5 |
| A7 | 21.9 | click ACCEPT SALVAGE (412,460) | `screen=0xC00F` garage, `sfn=0x10003e70` |
| A8 | 22.9 | snapshot 1 | all save files unchanged since pre-launch except `I76PLYR.DEF` (bytes 24: 6->5, 94: 250->123, written at load) |
| A9 | 23.9 | click SAVE BOOKMARK (560,460) | `next=1`, `mfn` still 0 (edit loop inside `SaveMenu_Open`), edit record scene 5, name buffer empty, **slot `0x10057f80` = -1**, fresh region list 0xe2cf1f4 and bookmark list 0xe2cf248 |
| A10a | 25.1 | Enter by keybd_event at +1.05 s | slot -1 -> 6 (record appended as max+1), **owSlot `0x10057f84` = 3** (same scene + same empty name as save003), window **not pumping** (`Modal_YesNo`), screenshot shows "Overwrite an existing bookmark?" with YES / NO |
| A11 | 25.8 | click YES (393,258) at +2.73 s | `savegame.dir` and `save003.cmp` mtime 19:14:36.967 within 10 ms; menu torn down (lists 0), screen back to garage, pumping again |
| A12 | 26.6 | snapshot 2, then 4 s watch | diff below; `IsHungAppWindow` false, pumping true through +7.8 s |
| A13 | 31.4 | WM_CLOSE | clean exit in 0.5 s; STRLKUP.DLL restored (md5 54f2de9d...), lock removed |

Diff snapshot 1 -> 2 (run 3): `save003.cmp` changed, md5 f1c4d535... -> dbd651d3..., size 10604 both;
`savegame.dir` **byte-identical** (364 B, same 6 records: the overwrite rewrote it unchanged); everything else same.

`save003.cmp` old vs new: 883 bytes differ, all inside (a) the two 11-byte part names at 0x54a and 0x568, which
swapped places ("NitrousOxid" <-> "X-Aust Brak" = Special 1/2 in the garage form), and (b) 12-byte groups at stride
0x74 from 0x8c9 on, i.e. the PartNode pointer fields of section A, which hold live heap addresses (0x02b1xxxx ->
0x0d80xxxx). GarageRec +0x7fc..+0x81b identical: armour 900/600/600/700, chassis 650/400/400/550, which is what the
Build and Repair form draws (90.0/60.0/60.0/70.0, 65.0/40.0/40.0/55.0).

## 3. Step table, run 4 (typing path, `runs\20261001-191640-type\`)

A1-A9 identical to run 3 (pid 13072, same states, same row 3 -> save003 loaded, snapshot 1 = post-run-3 set).
From A9 (t = 23.3 s, SAVE BOOKMARK clicked, slot = -1):

| step | t after SAVE BOOKMARK | input | buffer `i76shell+0x57f3c` | note |
|---|---|---|---|---|
| A10b-i | +2.31 s | keybd_event scan codes, `AUTOSAVE1`, 40 ms hold / 60 ms gap | '' (all zero) | |
| A10b-ii | +3.63 s | SendInput KEYEVENTF_SCANCODE, same text | '' | |
| A10b-iii | +4.95 s | PostMessageA WM_KEYDOWN/WM_KEYUP to the game window, same text | '' | |
| A10b-iv | +5.84 s | PostMessageA WM_CHAR, same text (extra) | '' | field already full, see below |
| screenshot | +5.9 s | | | field draws `SCENE 5. AUTOSAVE1AUTOSAVE1A1_` with the caret at the field's right edge |
| Enter | +6.00 s | keybd_event Enter | **`autosave1autosave1a1`** (20 chars) | slot -1 -> 6, owSlot 0, no prompt, direct save |
| A12 | +7.8 s | snapshot 2 | | `savegame.dir` 364 -> 424 B, md5 04cfcfd6...; **new `save006.cmp`** 10604 B md5 dbd651d3...; nothing else changed |
| watch | +8.8..+11.8 s | | | hung=false, pumping=true, garage |
| A13 | | WM_CLOSE | | clean exit; restored; lock removed |

Reading: the static record `0x10057f38` is only filled when `TextField_Edit` returns (the live edit buffer is
elsewhere), so reading `+0x57f3c` during typing says nothing; the result is read after Enter. All nine keybd_event
characters landed, all nine SendInput characters landed, and PostMessage landed two before the field was full. The
cap is the field's drawn width (183..454): 20 characters of this font fill it exactly and the field stops accepting
input, which is why WM_CHAR cannot be judged from this run. Characters are lowercase because `KeyInput_Poll` calls
`ToAscii` with a cleared key state (no shift). So: **typing is automatable with plain keybd_event on this build**;
the SAVE-FREEZE "zero characters" measurement belongs to the broken-ToAscii shell or to a ghosted window, not to
this one.

New dir record (parse_saves.py): `[6] scene 5 name 'autosave1autosave1a1' file save006 +0x34 8 flags 0`:
scene = the loaded row's scene, file = max(existing)+1, and **`+0x34` = 8 = the loaded row's value**, which
confirms the plan's 4.3 prediction (restored at 0x100133fb, saved back at 0x100149b6). `save006.cmp` has the
**same md5 as run 3's rewritten `save003.cmp`** (dbd651d3...): the `.cmp` writer is deterministic for the same
loaded state, heap addresses included.

## 4. Files written, both runs (sizes, md5s)

| file | pre-test | after run 3 | after run 4 |
|---|---|---|---|
| savegame.dir | 364 B, 6 rec, 9e15bd6e... | 364 B, 6 rec, 9e15bd6e... (identical bytes, mtime 19:14:36) | 424 B, 7 rec, 04cfcfd6... |
| save003.cmp | 10604, f1c4d535... | 10604, dbd651d3... | unchanged |
| save006.cmp | absent | absent | 10604, dbd651d3... (nA 64, nC 8, formula OK) |
| save000/001/002/004/005.cmp | 96459ac3 / 939f0463 / 34acb28c / d53e1c5c / e8e1af48 | same | same |
| ADDON\vehscn.vcf | 309 B, 7c5befb2..., mtime 18:06 | same | same |
| ADDON\vehscn.vsf | absent | absent | absent |
| reconfig.spc / trip4.spc | 0d916ca3 / d14f5dd4 | same | same |
| I76PLYR.DEF | 96 B, 88dfbc75... | 6819935d... (changed at load, 19:14:31, before the save) | same md5 again after the second load |
| save-00*.cmp orphans | none | none | none |
| mciproxy.log | | 5867 new bytes, IAT patch line present, cdaudio virtual, `MCI_PLAY ... run 13..15` at the garage, 0 ABORTED | same shape, 0 ABORTED |

`vehscn.vcf` parses as before (i76mod `VCFC`: Jade's Car, vppirnha.vdf, armour 711/722/733/744, chassis
755/766/777/788, the T1 live-test edit) and is **not rewritten by the bookmark load**: in run 4 the flag word
`[0x10057a20]` read **0** after LOAD, so the `& 2` branch of `Screen_LoadBookmark` that writes `vehscn.vcf/.vsf`
(plan 2.2 step 5) was not taken on this path. The exe's previous-state slot `[0x100d2164]` read 8 after the load
(the record's +0x34). This is the one place the plan's expectations for Leg A were not met, and it matters for
Leg B: a mission started from this load would read the T1-edited vcf, not the GarageRec. Open question for the
shell track: what sets bit 2 of `0x10057a20` (a normal boot through the menus evidently does not).

## 5. Freeze / ghost / crash

None. Per launch the Save screen was open 2.7 s (run 3: 1.05 s edit loop + 1.7 s prompt) and 6.0 s (run 4, edit
loop only). `IsHungAppWindow` was false at every sample, including +5.84 s and +6.00 s in run 4 and the four 1 s
samples after each save; `SendMessageTimeout(WM_NULL)` only failed while `Modal_YesNo` had the thread (expected: it
pumps nothing). The known blocker (no `DisableProcessWindowsGhosting` in u32x) did not bite at 6.0 s. That is
one sample at the threshold, not a refutation of the 5.9 s census; a longer idle on the screen was not tried.
No CD-2 prompt, no crash, both exits clean on WM_CLOSE (0.5 s).

## 6. Harness notes (what the two aborted launches taught, kept in `leg-a.ps1`)

- **Mouse mapping**: with `CaptureMouse=true` the shell reads the OS cursor as the UI coordinate 1:1 whatever
  `GetClipCursor` says. `uiclick.ps1`'s regime detector called the first click FREE (clip not yet applied right
  after focus) and placed the cursor at 760+3*217, 3*311, which the shell read as (639,479): TRIP missed, and
  the next click (confined) landed on an empty main menu. `leg-a.ps1` now places 1:1 and reads the shell's mouse
  object back before pressing; all 13 clicks in runs 3 and 4 read back exact before the press (run 3's TRIP click
  needed a second placement: the first read-back was stale right after Force-Foreground).
- Drawn-cursor check: the cursor pixel in each 960x720 capture sits at `(760 + 3*ux) * 960/3440, 3*uy/2`, so the
  UI -> screen formula of maplib.ps1 holds for reading screenshots.
- `Rd` cannot be a PowerShell function name (alias precedence: `rd` = Remove-Item); `[Text.Encoding]::Latin1` does
  not exist in .NET Framework; a local `$sfn` shadows a table `$SFN` (names are case-insensitive). The first of
  these aborted run 2, the second skipped the DLL restore in run 1 (restored by hand, verified by md5), the third
  only blanked the state names. Restore and lock removal now come first in `finally`.
- Row click: Load list rows drew at UI y 193/215/239/261/285/307 (23 apart), labels "SCENE 2, 3, 4, 5, 6, 6 s"
  for records scene 1,2,3 (+0x34 = 1, so +1: H11 confirmed on screen) and 5,6,6 (+0x34 = 8).
- `ui_i76.py` is the `ui.py` copy keyed on `i76.exe` under `i76-uncap-lab`; `leg-a.ps1` takes its screenshots
  inline (same GDI BitBlt of the window, 960x720 PNG) to avoid a Python start inside the 6 s window.
- `parse_saves.py` reproduces plan section 0 exactly and is what the "formula OK" claims above come from.

## 7. State of the lab folder after the run

- `STRLKUP.DLL` = original (117,248 B, md5 54f2de9da2beacb1b66a697eaf0d9ea1), no `.pretest`, no lock, no process.
- Save set: 7 records; `save003.cmp` rewritten (same car), `save006.cmp` new. To put the pre-test set back:
  copy `game\save-backup-20261001-190810\*` over (names with `__` are `ADDON\` files), delete `save006.cmp`.
  Backups 191215 and 191411 are identical to 190810; 191640 holds the post-run-3 state.
- Not done: A10c (orphan trigger T3), the second A/A repetition of the Enter leg, Leg B. The harness supports
  `-Mode enter|type`, `-RowUy`, `-TypeText`, `-NoQuit`.
