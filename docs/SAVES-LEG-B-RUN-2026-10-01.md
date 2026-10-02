# Saves protocol, Leg B: sandbox run 2026-10-01

*Unattended run of SAVES-STATE-AND-TEST-PLAN.md section 4.4 (Leg B: load the bookmark Leg A wrote, verify the car in
the mission) on the lab copy `C:\Users\james\i76-uncap-lab\game`, physical console, nobody at the machine. Harness:
`C:\Users\james\i76-uncap-lab\autotest\saves\leg-b.ps1` (leg-a.ps1's infrastructure verbatim plus the load/mission
steps), `dir_set_scene.mjs` (the browser editor's corrected `dirSetScene` applied to a copy of the directory),
`restore_set.ps1` (puts a `save-backup-<ts>\` set back and verifies md5s). Evidence per run under
`autotest\saves\runs\20261001-192903-b1\` and `runs\20261001-193139-b2\` (log.txt, step PNGs, snapshot JSON, parsed
listings, i76mod dumps, trainer-status.txt, mciproxy slice). No repository source file was edited. Every claim is from
the run logs or files on disk; screenshots only corroborate.*

## 0. Result in one paragraph

Leg B **passes** both variants. **B1**: cold boot -> TRIP -> LOAD BOOKMARK -> 7th row -> LOAD -> ACCEPT SALVAGE ->
garage -> DONE reached mission **`t05.msn`** (scene counter 5, mission number 5, type 2 = trip) 29.3 s after launch;
the record copied to `0x100579e8` was `scene=5 name='autosave1autosave1a1' file='save006' +0x34=8`, the car in the
mission read armour **1800/1200/1200/1400** and chassis **1300/800/800/1100** = exactly 2 x the `save006.cmp` GarageRec
(900/600/600/700, 650/400/400/550), engine 261ci / Sway Bars / Disc & Drum / 14in Rally, weapons 50cal MG, FireRite,
50cal MG, Oil Slick = the .cmp fit. **B2** (save006's scene dword set 5 -> 3 by the editor's `dirSetScene`, one byte at
offset 364, state byte left at 8): the Load list drew the row as "SCENE 3.", the load restored scene 3 and the mission
was **`t03.msn`**, same car. The expectation written in the brief ("scene S-2+1" = 4) was **not** what happens: for a
record with `+0x34 = 8` the mission is `t%02d.msn` of the raw dword; the shell advances the scene only for `+0x34 = 1`
(mission.md: 0x1001eaf0), which is also why Leg A saw labels "SCENE N+1" only on the state-1 rows (H11). The main
mechanism finding: **the bookmark load writes nothing but `I76PLYR.DEF`; it is the garage DONE exit that writes
`ADDON\vehscn.vcf`, creates `ADDON\vehscn.vsf`, rewrites `reconfig.spc`, and at scene 3 also `trip4.spc`** - all from
the loaded GarageRec (vcf/vsf armour 900/600/600/700, chassis 650/400/400/550; reconfig.spc and trip4.spc byte-identical
to save006.cmp). The T1-edited vcf (711..744 / 755..788) therefore never reaches the car on this path. No freeze,
ghost, crash or wrong screen; `IsHungAppWindow` false at every sample; both exits clean. Sandbox restored to the
pre-Leg-B set (12 files, 0 md5 mismatches, `vehscn.vsf` removed), original `STRLKUP.DLL`, no lock, no process.

## 1. Pre-flight (plan 4.1), identical for both runs

| item | result |
|---|---|
| 1. session | `TerminalServerSession = False`; `query session`: `>console james 1 Active` |
| 2. process / lock | no `i76*` process; `.console-test.lock` absent; taken per launch, removed in `finally` |
| 3. backup | `game\save-backup-20261001-192903\` (pre-Leg-B = post-Leg-A set, 7 records) and `save-backup-20261001-193139\` (post-B1), each with `md5.txt`. Pre-Leg-B md5s: savegame.dir 04cfcfd6 424 B; save000..006.cmp 96459ac3 / 939f0463 / 34acb28c / dbd651d3 / d53e1c5c / e8e1af48 / dbd651d3; reconfig.spc 0d916ca3; trip4.spc d14f5dd4 9212 B; I76PLYR.DEF 6819935d; ADDON\vehscn.vcf 7c5befb2 309 B (the T1 edit); **user.rpr and ADDON\vehscn.vsf absent** |
| 4. identity | `i76shell.dll` 0x1B52C = 0x41, 0x1B535 = 0x08; `deploy-shellfix -Status`: both PATCHED, u32x present; `i76.exe` md5 4FABC303...; **u32x has no `DisableProcessWindowsGhosting`** (known; Leg B never sits in a modal loop, it did not matter) |
| 4. dgVoodoo.conf | `CaptureMouse=true`, `FreeMouse=false`, `FullScreenMode=false`, `ScalingMode=stretched_ar`, `EnableInactiveAppState=true` |
| proxy | `music-fix\Strlkup.dll` (2347e1cb..., 155,648 B) over `STRLKUP.DLL` after `STRLKUP.DLL.pretest` (54f2de9d...); env `I76MUSIC_LOG=1` only; mciproxy slice (B2): 11,313 new bytes, 0 `ABORTED` |

## 2. B1 step table (`runs\20261001-192903-b1\`, pid 22452)

Times are seconds from harness start. Shell state = globals read with ReadProcessMemory (`0x100d2168` screen,
`0x100d219c` screen fn, `0x100d21a0` menu fn, mouse object `0x100cc514`), `i76shell.dll` at 0x3100000. Exe state =
static VAs: `0x4c2160` scene, `0x4c2164` game state, `0x5049f0` mission file, `0x5dcea0` play mode, `0x5dcea9` car
file, `0x5dd370` car name, `0x6562c0/0x6562c4` mission number/type, `0x5a7e1c` frame counter, shell `0x10057a20`
flags, `[0x100d2164]` -> the exe's previous-state slot. Clicks are UI 640x480 = OS cursor 1:1, each read back from the
shell's mouse object before the press (all 7 per run read back exact).

| step | t | input | state reached |
|---|---|---|---|
| B1.1 | 12.5 | `i76.exe -glide`, Force-Foreground while booting | window 3440x1440; shell DLL loaded; exe scene 1, gstate 5, msn '', playmode 0, carname `vppirna1` |
| B1.2 | 15.1 | Esc, Enter (2nd try) | `screen=0xC00E` main menu; exe gstate 6, prev-state 5 |
| B1.3 | 16.4 | click TRIP (217,311) | button list count 4 -> 3 |
| B1.4 | 18.4 | click LOAD BOOKMARK (276,351) | `mfn=0x10013060`, `next=11` |
| B1.5 | 19.5 | click row (203,**330**) | `[0x10046e70]` -1 -> **6** first try (rows 23 UI px apart, 7th row = 330); label drawn "SCENE 5. AUTOSAVE1AUTOSAVE1A1" (B1.5-row.png) |
| B1.6 | 20.5 | click LOAD (352,428) | `screen=0xC017` inventory; record at `0x100579e8`: **scene=5 name='autosave1autosave1a1' file='save006' +0x34=8 flags=0**; exe scene 1 -> **5**, playmode 0 -> **2**, prev-state **8**; shell flags `[0x10057a20]` = **0** |
| B1.7 | 21.7 | click ACCEPT SALVAGE (412,460) | `screen=0xC00F` garage; form shows 90.0/60.0/60.0/70.0, 65.0/40.0/40.0/55.0, 50cal MG / FireRite Rkt / 50cal MG / Oil Slick (B1.7-garage.png) |
| B1.8 | 23.1 | snapshot 1 | **every file identical to pre-launch, I76PLYR.DEF included** (0 bytes differ; the load's `PlayerDef_Save` wrote the same 96 bytes Leg A's load had written); vehscn.vcf still the T1 edit (7c5befb2, mtime 18:06), vsf absent |
| B1.9 | 25.6 | click DONE (400,460) | +1.0 s: shell top `none`, exe gstate 5, carfile/carname **`vehscn.vcf`**; +1.6 s: **msn `t05.msn`, mnum 5, mtype 2**, player entity 0x0d95248c allocated, frame counter still 0 |
| B1.10 | 29.7 | Esc + click once (cutscene skip), entity + 16 live entities | frame 153 and counting; entity dump below; `IsHungAppWindow` false |
| watch | 30.7..32.7 | 3 x 1 s | frame 236 / 298 / 358, entity values unchanged, hung false |
| quit 1 | 42.9 | WM_CLOSE in the mission | not an exit: exe gstate 6, prev-state **2** (abort), shell back at the **main menu** (0xC00E, scene 5) after 10 s (quit-round1.png) |
| quit 2 | 43.5 | WM_CLOSE again | clean exit in 0.5 s; STRLKUP.DLL restored (54f2de9d...), lock removed |

B1 entity (`[[0x54a264]] -> +0x70` = 0x0d95248c; `tools\trainer\i76trainer.py status`, full text in trainer-status.txt):

| read | value | vs `save006.cmp` (parse_saves.py / `i76-save-editor.py --dump 6`) |
|---|---|---|
| armour +0x138 cur / +0x158 max / +0x178 hud | 1800, 1200, 1200, 1400 (all three) | GarageRec +0x7fc = 900/600/600/700 -> **2 x** (the single-player doubling, 0x463120) |
| chassis +0x148 cur / +0x168 max / +0x18c hud | **1300, 800, 800, 1100** (all three) | +0x80c = 650/400/400/550 -> 2 x; **not 0** (plan 4.5 FAIL condition not hit) |
| components | wheels (type 30) 400/400 x4; engine (20) 1600/1600; 21: 1200/1200; 23: 800/800; 22: 600/600; 24: 40/40 x3 | all at max; from the part definitions (eng01 etc.), not the VCST hp fields (300/150/200) |
| weapons (global table 0x5AAB0C, 16 instances, all vehicles) | slots 8-11: `gmmedium` 2000, `gdumb` 60, `gmmedium` 2000, `goilslck` 2000 | = 50cal MG, FireRite Rkt, 50cal MG, Oil Slick = GarageRec +0x400 fit and the vcf WEPN chunks (hardpoints 1, 3, 2, 0); the table is not per-player, the block sat at 4-7 in B2 |
| play flags / cheat marker | 0x00 / 0 | |
| position, speed | (8284, 27, 44518), 25 m/s | mission 5 start (canyon road, B1.10b-watch.png) |

## 3. B2 step table (`runs\20261001-193139-b2\`, pid 22608): the modified directory

Before launch, with the game closed: `savegame.dir` copied to `runs\...\savegame.dir.orig`, `dir_set_scene.mjs`
(the editor's `parseDir`/`padDir`/`dirSetScene` extracted from `i76-save-editor.html`) applied
`dirSetScene(buf, 'save006', 3)`: record k = 6 found by its file-name field at +36; **exactly one byte changed, offset
364 (= 4 + 60 x 6), 5 -> 3**; 424 B both; parse: `[6] scene 3 name 'autosave1autosave1a1' file save006 +0x34 8`.
Installed (md5 26d66051...), original put back in `finally` (md5 04cfcfd6... verified).

| step | t | state reached (differences from B1 only) |
|---|---|---|
| B1.1-B1.4 | 13.0-18.9 | identical to B1 |
| B1.5 | 20.0 | row 6 first try; label drawn **"SCENE 3. AUTOSAVE1AUTOSAVE1A1"** (B1.5-row.png) - the label is the raw dword for a state-8 record |
| B1.6 | 21.0 | record `scene=3 name='autosave1autosave1a1' file='save006' +0x34=8`; exe scene **3**, playmode 2, prev-state 8, flags 0 |
| B1.7 / B1.8 | 22.2 / 23.7 | garage; snapshot 1: only `I76PLYR.DEF` changed vs pre-launch (bytes 24: 4->3, 93: 229->210, 94: 17->123, 95: 3->13 - the shell's `PlayerDef_Save` at load) and the installed dir; vcf/vsf/reconfig.spc untouched by the load (same md5 and mtime) |
| B1.9 | 26.2 | DONE: +1.6 s **msn `t03.msn`, mnum 3, mtype 2**, scene 3 |
| B1.10 | 30.6 | in mission, 14 live entities, frame 152; entity 0x0d95024c armour 1800/1200/1200/1400, chassis 1300/800/800/1100, same components; weapon block `gmmedium, gdumb, gmmedium, goilslck` at slots 4-7; position (703, 21, 50439) (B1.10b-watch.png: the orange Piranha on a canyon road) |
| quit | 43.8 / 44.4 | WM_CLOSE -> main menu (prev-state 2) -> WM_CLOSE -> clean exit 0.5 s |

So: **B2 loaded scene 3 -> `t03.msn`**, not scene 4. The brief's "S-2+1" assumed the +1 rule of the state-1 rows;
with `+0x34 = 8` restored into the exe's previous-state slot (0x100133fb) the DLL does not advance the counter.

## 4. Files written, byte-exact

| file | bookmark load (B1.6/B1.7) | garage DONE (B1.9) | mission abort via WM_CLOSE |
|---|---|---|---|
| `savegame.dir`, `save*.cmp` | unchanged | unchanged | unchanged (04cfcfd6..., all seven .cmp md5s as backed up, no `save-00*.cmp` orphan) |
| `I76PLYR.DEF` (96 B) | B1: rewritten with identical bytes (mtime 19:29:23.68); B2: 4 bytes (24: 4->3, 93-95 -> 210,123,13) | - | B1 19:29:37.87: 24: 5->4, 93-95: 210,123,13 -> 229,17,3; B2 19:32:14.74: 24: 3->2, 94: 17->12. Two writers (shell `PlayerDef_Save`, exe `player_SaveDef`), bytes 93-95 flip between the two writers' values; byte 24 went 5 -> 4 -> 3 -> 2 across abort / load / abort (meaning not pursued) |
| `ADDON\vehscn.vcf` | **unchanged** (7c5befb2, T1 edit, mtime 18:06; `[0x10057a20] & 2` not taken, as in Leg A) | **rewritten 19:29:28.454**, md5 522de647..., 309 B: 44 bytes differ from the T1 file, all inside VCFC (variant "Jade's Car" -> 'Stock (Orange)', engine_id 2 -> 0, suspension_id 2 -> 1, wdf `wauto_1a` -> `wauto_1b` front and rear, armour 711/722/733/744 -> **900/600/600/700**, chassis 755/766/777/788 -> **650/400/400/550**, spare 160 -> 0) and the four WEPN chunks (hardpoint 1 `gmmedium`, 3 `gdumb`, 2 `gmmedium`, 0 `goilslck`). B2's DONE rewrote it byte-identical (mtime 19:32:05) | - |
| `ADDON\vehscn.vsf` | absent | **created 19:29:28.454**, 232 B, md5 97528691...: REV, VCST 76 B, WLST 24 B, WPST x4, EXIT. VCST: vcf 'vehscn.vcf', armour 900/600/600/700, **chassis 650/400/400/550**, velocity 0,0,0, f39 0.0, engine_hp 300, brake_hp 150, susp_hp 200, flags 1,1,1. WLST 100,100,-1,-1,100,100. WPST hardpoint 0/1/3/2 state_a 200/400/200/400 state_b -1. Byte-identical after B2's DONE | - |
| `reconfig.spc` | unchanged | **rewritten 19:29:28.453**, 10604 B, md5 dbd651d3... = **byte-identical to save006.cmp** (`Garage_Frame`'s writer is `Cmp_Write` on the same loaded state) | - |
| `trip4.spc` | unchanged | B1 (scene 5): unchanged. **B2 (scene 3): rewritten 19:32:05.049, 9212 -> 10604 B, md5 = save006.cmp** (the plan's "written only at scene 3" confirmed; a scene-3 garage exit overwrites the scene-3 checkpoint with whatever is loaded) | - |
| `user.rpr` | absent throughout | | |
| `mciproxy.log` | B2 slice: 11,313 new bytes, IAT patch line present, 0 ABORTED (B1's slice was not cut, see 6) | | |

Timing: the DONE click landed at t = 23.3 s (B1); the four writes carry mtimes 19:29:28.453-.454 and the exe reported
`msn = t05.msn` 1.6 s after the click, so the shell writes vcf, vsf and reconfig.spc in the same millisecond on the
garage exit, before `ShellMain` returns.

## 5. B3, the chassis-0 lead

- The load path writes neither `vehscn.vcf` nor `vehscn.vsf` (`[0x10057a20]` read 0 after LOAD in B1 and B2, as in
  Leg A); the **garage DONE** does, from the loaded GarageRec slot 0. VCST chassis = **650/400/400/550** (non-zero,
  equal to GarageRec +0x80c), the live entity chassis +0x148 = 1300/800/800/1100 in both runs. A bookmark saved from
  the in-mission Reconfigure path (+0x34 = 8) therefore loads with its chassis intact; the H7 leak, if it exists, needs
  a won mission (exe-written vsf, +0x34 = 1) - not exercised here.
- Open: plan 4.4 expected `+0x138` = VCST armour **x1** if the VCST handler ran, 2x if it did not. The reading is 2x
  with `[0x6562c4] = 2` and the vsf on disk 0.6 s before the mission load, but VCST == VCFC here, so a handler that
  applies VCST and is then doubled is indistinguishable from no handler. A discriminating run needs VCST != VCFC
  (a damaged car saved from the mission); not done.
- WPST `state_a` is 400 for both 50cal MGs while the .cmp lists the two equipped 50cal MG records at cond 400 and 200
  (dump 6, items 41/42): either `state_a` is the durability (`dur` column) rather than the condition, or the
  equipped-slot to record mapping is not what the editor shows. Not resolved.

## 6. Anomalies, harness notes

- **No game anomaly**: no freeze, no ghosting, no CD prompt, no wrong scene or car; `IsHungAppWindow` false at all
  samples; the window pumped throughout; both exits clean on the second WM_CLOSE.
- **WM_CLOSE in a mission is not a quit**: the exe's WndProc sets state 2 (abort), the mission ends, `ShellMain` runs
  with arg11 = 2 and shows the main menu (scene counter kept: 5 in B1, 3 in B2); a second WM_CLOSE to the shell exits
  in 0.5 s. `leg-b.ps1` does both rounds before falling back to `Stop-Process` (not needed). The abort writes
  `I76PLYR.DEF` (exe `player_SaveDef`) and nothing else: no vsf (trip success only), no save files.
- **Shell globals after ShellMain returns**: `[0x100d2164]` points into the exe's stack frame (ShellMain arg 11), so
  the "prev-state" column reads garbage (1663041693, ...) once the shell has returned; the shell screen/menu statics
  simply keep their last values (`top=none`). Only the exe globals are meaningful in a mission.
- **Harness bug, B1 only**: a loop variable `$g` in the DONE wait overwrote `$G` (the game path; PowerShell names are
  case-insensitive, the same trap Leg A hit with `$sfn`). Effects: the B1 "mission ADDON\vehscn.vcf: absent" log line
  is false (the file was there, md5 522de647..., verified by hand 2 min later), the B1 post-quit snapshot and mciproxy
  slice failed (replaced by `runs\20261001-192903-b1\snap3-manual.txt`, taken at 19:31:34 before B2 started). The
  DLL restore, lock removal and quit used pre-computed paths and ran correctly. Fixed (`$gx`) before B2, whose
  bookkeeping is complete.
- The 7th Load row is at UI y 330 (23 px pitch from Leg A's 193..307); `leg-b.ps1 -WantRow` verifies `[0x10046e70]`
  and corrects by 23 px per row if the first click lands elsewhere (not needed in either run).
- `tools\tests\test-save-editor-dir.mjs` now reports 2 FAILs against the lab file: its `dirWithSlot`/`dirRemoveSlot`
  checks hard-code the six-record set (`4 + 60 * 7` after adding save006), and the lab has had seven records since
  Leg A. `dirSetScene` itself is correct (B2 relied on it). The test's expectations need the 7-record set, or a fixture
  copy of the old file.

## 7. State of the lab folder after the run

- `restore_set.ps1 -Backup save-backup-20261001-192903` restored `reconfig.spc`, `trip4.spc`, `I76PLYR.DEF`,
  `ADDON\vehscn.vcf` (back to the T1 edit 7c5befb2...), deleted `ADDON\vehscn.vsf`; `savegame.dir` and the seven
  `.cmp` were already identical. **Verify: 12 files, 0 mismatches**; `user.rpr` absent; parse = the pre-Leg-B listing
  (7 records, every `.cmp` on the size formula, no orphans).
- `STRLKUP.DLL` = original (117,248 B, md5 54f2de9da2beacb1b66a697eaf0d9ea1), no `.pretest`, no lock, no `i76*`
  process. Backups `save-backup-20261001-192903` (pre-Leg-B) and `-193139` (post-B1) remain in `game\` beside Leg A's.
- Not done: variant B' (in-mission Esc -> Load Bookmark, state 9); a VCST != VCFC discriminating run; the Leg A A/A
  repetition. The harness supports `-Mode b1|b2 -WantFile -WantRow -RowUy -SetScene -StopAtGarage -NoQuit`.
