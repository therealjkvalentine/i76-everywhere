# Overnight console run 2026-10-11: results, harness fixes, reruns

The first real run of the lab's unattended runner (`i76-uncap-lab\autotest\overnight\run-overnight.ps1`, all seven phases,
started 18:29 at the physical console), then a follow-up agent the same evening: diagnosis of every FAIL, fixes in the
lab harness, reruns of each phase. Every game boot ran on a lab copy (the twin `game-dd-20261003`, the sandbox `game`,
the throw-away `game-dd-tel3` and `game-fresh-<ts>`); the daily driver and the golden copy were only read (P7 preset md5s).
The owner's trainer GUI and motionlab app kept running all night (telemetry over UDP; see "Still open"). Audio muted
throughout (`i76-uncap-lab\tools\mute.ps1 -Off` to unmute).

Run folders (lab, `autotest\runs\`):

| run | phases | what |
|---|---|---|
| `overnight-20261011-182933` | P1-P7 | the first run (2 h 10 min); the runner crashed writing its summary, so it has no `summary.md` |
| `overnight-20261011-202103` | P6 | fresh install with step screenshots + the trip / gate-row repro checks (`P6\row1-*`, `gate-row3-check*`) |
| `overnight-20261011-203304` | P2 | P2 after the fix (the runner then died on a log write, see fixes; restore checked by hand: 0 differences) |
| `overnight-20261011-204548` | P4, P5, P6 | after the fixes |
| `overnight-20261011-205419` | P4, P1 | P4 with the corrected priority check; P1 in full (rams to n >= 21, 8+8 drives with end screenshots, gate) |
| `overnight-20261011-220626` | P1 (no rams) | 8 x 3 drives (control, w2, 24 fps reference) and the gate with the cursor-map environment |

## Verdicts

| phase | owner item | verdict | n | evidence |
|---|---|---|---|---|
| P1 rams | 3 | **PASS**: w2 21/21 vs control 10/43, A/A p 0.49 | 64 rams | `overnight-20261011-205419\P1ams` |
| P1 drives | 3 | **real harm at one spot** (w2 5/23 passes destroyed, control 0/21); otherwise chance | 24 + 24 (+8 at 24 fps) | `182933`, `205419`, `220626` `\P1\drives` |
| P1 gate | 3 | **PASS 21/0/2** after two harness fixes (first run's 3 FAILs were harness) | 23 rows | `autotestuns\gate61011-225529` |
| P2 telemetry v3 | 6, 8 | **PASS 24/24** (rerun) | t01 2,904 frames, t05 2,906 | `overnight-20261011-203304\P2` |
| P3 haptics replay + motion | 8 | **PASS 3/3** (first run) | 2,917 datagrams; 14/14 validator checks | `overnight-20261011-182933\P3` |
| P4 HD sound loader | 7 step 1 | **PASS 4/4**, twice | 42 marked SOUND_START, 0 stock | `overnight-20261011-205419\P4`, `-204548\P4` |
| P5 PLAY-stock textures | 5 | **INFO: no signal** at TMU 8192 | 4 runs, 36 captures | `overnight-20261011-204548\P5` |
| P6 fresh install | 16 | **PASS 7/7** (rerun) | 1 install, 2 trips | `overnight-20261011-204548\P6` |
| P7 presets | promotion regression | **PASS 6/6** (first run) | 3 drives | `overnight-20261011-182933\P7` |

## P1 collision candidate (I76_COLL_WINDOW=2 + I76_COLL_DEDUPE=1)

**Rams (barricades, lab sandbox, T05, rate-ab colldedupe, interleaved ctl-a / w2 / ctl-b): PASS.** First run: the
tally saw only the last of 5 rounds (harness bug: rate-ab names its files `run1.*` on every call and all rounds shared one
OutDir), n 7 / 8 / 7: w2 8/8 vs control 3/14, Fisher p 0.001, A/A p 1.0. Rerun with one OutDir per round (`205419\P1\rams`,
3 rounds): **w2 21/21 contacted vs pooled control 10/43 (23 %), Fisher p 1.1e-9; A/A ctl-a 4/22 vs ctl-b 6/21, p 0.49.**
Matches s.7 of the lab's COLLISION-MISS-2026-10-08.md (window off 3/14 - 5/14, `=2` 14/14 - 15/15).

**Gate (gate-folder on the twin with best-wide.psd1 staged as best-wide + the two keys): PASS 21/0/2 after two harness
fixes** (`autotest\runs\gate\20261011-225529`). The first run's 18 PASS / 3 FAIL / 2 INFO: rows 3 (trip through PLAY.bat:
engine up, fps) and 6 (melee by menus) failed because `LAB_CURSOR_FREE` was not set; the twin's wide conf runs the proxy
cursor map (CaptureMouse = false), so raw-coordinate clicks never left the main menu (screenshot: pointer at UI 57,154).
The same trip by hand with `LAB_CURSOR_FREE=1`: up, 120 fps. A rerun with only that set failed rows 2 and 4 instead
(harness-booted leg-b / garage save screen without the cursor-map keys): P1 now also passes best-wide's
`I76_CURSOR_MAP*` / `I76_U32X_*` keys in `LAB_GAME_ENV`, as the 2026-10-08 promotion-15 gate (23/0) did. The 2 INFO rows
are the watermark probe (by eye) and force feedback (no wheel plugged in). All three FAILs of the first run were harness,
none were the candidate.

**Drives (t04, 90 s god-mode circle on the twin, car-terrain-logger, interleaved ABBA): one reproducible harm, the rest
chance.** Three sets of 8 + 8 (`182933`, `205419`, `220626`), plus 8 at `I76_FPS_CAP=24` as a stock-like reference:

| measure | control (best-wide) | w2 | Fisher p | note |
|---|---|---|---|---|
| player destroyed, mission over ("ended") | 4/24 | 10/24 | 0.11 | god mode does not stop it: the end dialog says "YOU ARE NOT SUPPOSED TO DIE, FOOL!" in both conditions (`*-end-15s.png`) |
| ... at one spot ~9.5 s in (x 1196, z 50400) | **0 of 21 passes** | **5 of 23 passes** | 0.05 | the car slows to 0 over ~1 s and burns (`205419\P1\drives\ov10112127-w-3-end-2s.png`); same place every time |
| ... anywhere else | 4/24 | 5/24 | 1.0 | |
| car body under the terrain (logger) | 1/24 | 3/24 | 0.6 | w2's first-run w-1: 2,177 body frames, 1,223 cockpit-eye frames at a 24.8 m wall, one drive |
| 24 fps reference | - | - | - | 0/8 ended, 2/8 under; its circle took another path and never reached the spot, so it does not answer "would stock die there" |

The first run's "w2 under 2/8, ended 5/8, lines 202" was mostly the spot (2 of the 5 ends) plus one long body-in-wall
drive. Pooled with s.7's 8 + 8 (cockpit-under 3/8 off vs 0/8 on), the under-terrain rate does not differ. **The spot does:**
every control drive that passed it drove on, and about one w2 pass in five died there, the same way each time. What is
there (an object the window now collides with - a mine, a hazard, a structure - and whether stock 20/24 fps collisions
kill there too) is not known yet. Next test, not run: trainer-teleport the car onto that line at 24 fps (cap) and at 120 +
w2, n >= 8 each, and dump the partner of the contact record (logger `rec_other`) at the stop.

## P2 telemetry v3 live (tel3 proxy `48eca564` on a flat copy of the twin)

First run: exit 1, no rows. **Harness bug**, not the proxy: the check loop said `$r = $run[1]`, and PowerShell variable
names are case-insensitive, so `$r` overwrote `$R`, the phase's result object; the next row call failed and
`result.json` held the t01 mission object. (P5 had the same bug with `foreach ($r in $runs)`.) Fixed and guarded.

Rerun (`203304`), 24/24 PASS: the three log lines the test list names (`telemetry: on ... 4/4 event hooks`,
`sound-events: on - stop taps 4/4 ... start tap on ... weapon-UI clicks 3/3`, `damage-events: on`) in both missions; no
CRASH line; `i76tel.py --check`: 2,904 / 2,906 v3 frames, 0 bad headers, 0 sequence or event-sequence gaps; SOUND_START
t01 173 (141 PLAYER, 32 other, 148 with a position), t05 129; SOUND_STOP 173 / 128 (ended / released / parked);
WEAPON_UI 5 (Tab = cycle); DAMAGE_SIDE 20 on t05 (PLAYER front 4, back 4, other 2) from the scripted drive (the trainer
rams need the shared memory, which the trainer GUI held at the v2 size: the v3 proxy logged `shm view refused`, UDP
unaffected); `haptics record --udp` wrote 2.0 MB per mission and `decode --events` reads them. Telemetry ran at 58 frames/s
with the game at 120 fps.

The runner's default commits the two recordings to `tools\haptics\replays\`; they were committed by the run and then
taken back out (this session commits to this repo only for fixes). They are in the lab run folder:
`overnight-20261011-203304\P2\t01.i76rec` (md5 `d89bfb3a`) and `t05.i76rec` (`0c0e7314`). To keep one as item 8's
reference recording: copy it to `tools\haptics\replays\t01-ovn-20261011.i76rec` and commit.

## P3 haptics replay + motion validator (first run, on P2's first-run t01 recording)

PASS: 2,917 datagrams, 0 undecodable, all v3; replay through wheel-file, pad-file, lfe-wav and motion-file wrote 5 files;
`i76motion.py --check` 14 passed, 0 failed (100 Hz packet rate, shutdown tick last). Lfe.Stems was off: the pack-v1 LFE
stems are listed (85) but not built (`tools\soundhd\soundhd.py build`), so the shaker ran Lfe.Synth only.

## P4 HD sound loader proof

First run: FAIL "target ''". **Harness bug**: SOUND_START carries the first 8 bytes of the sample's file name
(`wmflame.`, `tskid3.w`, `CAMMO.WA`), and the phase compared those with the pack's stems (`wmflame`); nothing matched.
Second run (`204548`) picked the target but failed the priority check for a second harness reason: the voice priority
is the header priority plus a class offset (wmflame: header 70, event 89), so an absolute "77" never appears.

Result (`205419`, and the same numbers in `204548`): marker pack = the stock `wmflame.gpw` header with priority +7 and a
three-beep tone at 1.5x the rate, installed by `soundhd.py install --apply` into `game-dd-tel3\ADDON`. Baseline t01: 42
`wmflame.` SOUND_START at priority 89, 11,025 Hz. Marker t01: **42 at priority 96 (= 89 + 7), 0 at 89, 16,538 Hz
(x1.500)**; the controls in the same run did not move (`wmmgun.w` 89 / 11,025 Hz, `vland.wa` 70). So a loose ADDON
`.gpw` replaces the archive copy, header included. `uninstall --apply` put ADDON back to its md5 manifest (11 files, 0
differences). What this does not cover: how the pack sounds (owner item 7's A/B by ear).

## P5 PLAY-stock textures (twin, preset stock, dgVoodoo.16x10.conf, TMU 8192 vs 2048)

First run: same `$r` / `$R` bug as P2. Rerun (`204548`), 4 interleaved t01 runs (8192, 2048, 8192, 2048), 9 captures each:
the census proves the conf in force (usable TMU 8,191 KB vs 2,047 KB); FLUSH 1 and rewind 1 in **every** run, downloads
7,195-7,230 per run; image mean |diff| A/A max 22.6 vs A/B mean 20.0. **No census or image signal** that 8192 without
TMUFIX misbehaves on this path. The captures (`P5\tmu*\f*.png`) are for the eye; a 36 s throttle-only t01 does not
exercise much texture variety, so the owner's item 5 (a few minutes of PLAY-stock) stays the real test, at low priority.

## P6 fresh install (GOG 2.1.0.17 tree, Setup-From-GOG offline switches, preset best-120)

First run: setup PASS, then "boot CRASH 0xC0000096 at exe+0x99997, engine up False". Both readings were wrong.

**The 0xC0000096 line is not the failure.** `exe+0x99997` is `cli; mov al,0xb8; out 0x43,al; in al,0x61 ...` in the
1997 CPU-speed routine at 0x499950 (the PIT timing loop, privileged in user mode). GOG 2.1.0.17's exe (`9a232dcc`) still
calls it (`call 0x499950` at 0x499b25, return address 0x499b2a = the logged stack slot); the AiO build the presets were
gated on (`60abf7bc`) removed that call (zero callers), which is why it never showed on the twin. The bytes at the fault
are identical in both builds: no proxy, u32x or dgVoodoo patch touches them. The proxy's crash log is a first-chance
vectored handler (`EXCEPTION_CONTINUE_SEARCH`); the game's own handler takes the fault and the boot goes on (Glide init
lines follow it in the log, the menus come up). The phase now reports it as its own INFO row ("boot continued past it").

**The trip failed on harness choices**, found with a screenshot after every click (`option6-trip-test.ps1 -StepShots`):
1. The bookmark pick (the last row on the first page) was `save014` 'OOOH SHIT', whose car has no parts (39 A + 0 C):
   loading it goes straight to "YOU ARE UNCONCIOUS / NEXT MISSION". Now: the first intact row (`save001`).
2. A fresh player profile shows "REMEMBER, USE THE SAVE BOOKMARK BUTTON" (OK) after ACCEPT SALVAGE, which the route did
   not expect. `option6-trip-test.ps1 -FirstRunHint` clicks OK and ACCEPT again.

Rerun (`204548`), 7/7 PASS: setup exit 0; trip through `PLAY-i76.bat` -> mission, **engine up, 120.0 fps** (heartbeat)
/ 120.1 (exe counter) on `9a232dcc` with best-120 and u32x `06467bd2`; mciproxy.log 38 lines, no switch skipped or not
applied; control trip through `PLAY-stock.bat`: up, 60 fps; Desktop, `C:\Games\_tools`, GOG installer logs and the
source tree unchanged; scratch folder deleted. The trip was repeated by hand twice more on the first rerun's folder
(`202103\P6\row1-hint-check`: up, 120 fps). **So a new user's install of the current GOG build boots and plays at 120.**

Two things a new user does get differently on `9a232dcc`:
- **Music.** That exe imports `mciSendCommandA` / `aux*` from GOG's `WIN32.dll` (its CD-audio shim over `audiere.dll` +
  `music\`), not from `WINMM.dll`, so the proxy's music redirect cannot attach (mciproxy.log says so). In-mission music is
  then GOG's shim's job; not heard tonight (muted). Setup used to print "In-mission music fix installed" regardless;
  `setup-windows.ps1` now adds a note when the exe has no WINMM import (fix below).
- The first-chance fault above at every boot (harmless as measured; a debugger would stop on it).

`0xC0000096` and the `NOTE: this exe has no WINMM.dll import` line are now expected entries for this build in
`FRESH-INSTALL-CHECK-2026-10-10.md`'s gap 1.

## P7 preset regression drives (twin, first run)

PASS 6/6: twin preset md5 = driver preset md5 for best-wide (`8de71421`), best-wide-balanced (`a2191719`), best-120
(`3c12c8d0`); each booted into t04, 90 s god-mode circle, no CRASH line, 119.9 / 119.9 / 120.0 fps, 692 / 798 / 881 m.

## Harness fixes (lab, `autotest\overnight`; lab commits listed at the end)

| symptom | cause | fix |
|---|---|---|
| P2, P5 exit 1, no rows | `$r` loop variable = `$R` result object (case-insensitive names) | renamed; `OV-AddRow` throws and `OV-SaveResult` writes a FAIL row if the object was overwritten |
| runner crash at line 216, no `summary.md`, `.console-owner` left held | a row with a null result as a hashtable key; the lock release came after it | null results counted as FAIL / NONE; summary in its own try; lock released in a finally |
| rerun died after P2 before its restore | `Add-Content` on log.txt threw while a reader held the file | `Log` retries, falls back to `log.<pid>.txt`, never throws; `lib\restore-from-run.ps1` for a late restore (used once: 0 differences) |
| `game-dd-tel3` / `game-fresh-*` "COULD NOT DELETE", half-deleted | i76.exe `AddFontResource`s `Lee_____.ttf` and never removes it; the session keeps the file open | `OV-RemoveLabTree`: `RemoveFontResourceW` per load, then delete (both folders now delete) |
| P1 rams n stuck at 7-8 after 5 rounds | rate-ab names its files `run1.*` every call; the shared OutDir kept only the last round | one OutDir per round, `ram-tally.py` reads `round<k>\` |
| P1 gate rows 3 (x2) and 6 FAIL | the twin conf has `CaptureMouse = false` (proxy cursor map) and `LAB_CURSOR_FREE` was not set: clicks went to the raw UI coordinate, the menu never left the main screen | P1 sets `LAB_CURSOR_FREE=1` when the twin conf says so; the same trip by hand with it: up, 120 fps |
| P4 target '' / priority never matched | 8-byte file names vs pack stems; absolute vs relative priority | mapped; compared as a shift from the baseline |
| P6 trip "engine up False" | dead-car bookmark; fresh-profile hint dialog | intact bookmark; `-FirstRunHint`; `-StepShots`; CPU-probe fault as INFO; tmufix "boundary rule skipped" no longer counted as a skip; PLAY-stock control trip |

New helpers: `lib\with-console.ps1` (one ad-hoc console job under the lock protocol: exclusive `.console-owner`, no i76
running, mute verified, lab games stopped and the lock released in finally), `lib\twin-trip-check.ps1` (gate row 3 alone
inside an aside / md5 restore), `lib\end-shot.py` (screenshots when a drive's mission ends).

## Fix in this repo

- `setup-windows.ps1`: after the Strlkup proxy step, a yellow note when `i76.exe` has no `WINMM.dll` import (GOG
  2.1.0.17): the music redirect cannot attach there, the other switches are unaffected. Checked against both builds
  (9a232dcc: note; the twin's 6319abf7: none); parse clean.

## Still open / for the owner

1. **I76_COLL_WINDOW=2 promotion: not yet.** The rams and the gate pass (21/21 vs 23 %, gate 21/0), but w2 kills the
   car at one spot of t04 (5 of 23 passes, 0 of 21 without it, p 0.05). Decide after the spot test above, or play t04's
   opening with `TEST-coll-B-window2.bat` (owner item 3) and see what you hit about 250 m along the first circle.
2. **Item 8 reference recording:** keep the scripted `t01.i76rec` from `overnight-20261011-203304\P2` (copy + commit) or
   record your own (better).
3. **Fresh install music on GOG 2.1.0.17:** the proxy cannot reach it; check by ear that GOG's own shim plays it (item 16).
4. **Close the trainer GUI before the next overnight run** if the t05 rams should feed DAMAGE_SIDE (it holds the
   telemetry shared memory at the v2 size; everything else used UDP and passed).
5. Not changed tonight: the daily driver, the golden copy, committed binaries (`music-fix\Strlkup.dll` read back
   `c11f7f7d` after every phase), the owner's running programs. Every lab folder a phase touched was restored
   (manifest diffs PASS; the sandbox's `mciproxy.log` only grows and is no longer counted as a difference).
