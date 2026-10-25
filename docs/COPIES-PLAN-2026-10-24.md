# Game copies: inventory and consolidation plan (2026-10-24, housekeeping lane, PLAN ONLY - nothing moved)

Owner, 2026-10-24: "let's clean up all these extra versions and just have dev, test, rc, and the daily driver."
Everything below was read from the PC and the laptop at about 21:00 on 2026-10-24 while the evening lanes were running.
Nothing was moved, renamed, deleted or linked. The script `tools/consolidate-copies.ps1` is written and dry-run only (run once to
check it; its dry-run output is what the numbers in 3 come from). Proxy md5s are the first 8 hex of the md5 of `STRLKUP.DLL`.

## 0. Numbers

- **PC, C:** 39 real game-copy folders (+ `Games\I76\_archive`, 1.83 GB of old packs) = **18.6 GB**; 17 more names are junctions
  (14 already point into `D:\i76-archive\i76-uncap-lab`, `game-tick` -> release-candidate, `game-dd-20261003` -> `twin-driver` -> D:).
  Two of the 39 are empty shells (`exp-mac`, `exp-rcdraw`). C: has 40 GB free of ~1 TB; D: has 925 GB free. So reclaiming is housekeeping, not an emergency.
- **Kept as the roles (8 folders, 3.5 GB):** release-candidate, daily-driver, exp-polish2 (dev), rc-twin-20261024 (test), exp-nitro-owner, exp-nitro-polish, nitro-lan, lan (until merged).
- **Archive to D: now (19 folders + `_archive`) = 9.96 GB** reclaimed on C:, nothing deleted (verified copy, then remove source, junction left where a tool names it).
- **Archive after the lanes report (12 folders) = 5.1 GB more**, so **~15 GB** back on C: in total. Real deletions: none from C: (D: has room). Only exact-duplicate deletes are listed in 3 and each needs the md5 compare first.
- **Laptop `C:\i76-bench`:** 7 game-sized folders + `scott-b.zip` = 3.0 GB, 41 GB free. Keep `rc-twin`; the rest is reproducible from the PC pack (3).
- Cruft inside the kept folders is small (mostly 0.4-0.7 MB proxy backups and 2-7 MB `mciproxy.log`): 5.5 MB in the folders that were idle at the time of the dry run, an estimated 25-40 MB over all seven once the held ones are free. The big win is the copy count, not the cruft.

## 1. Inventory

Last-mod = newest file in the folder (depth 3), not the folder time. LIVE = a game process, lock file, queue entry or a file written in the last 30 min at 21:00.
"Refs" = hits in repo docs (D), repo tools (T), lab tools (L), lab autotest (A) for scripts/docs that spell the folder name (the name `game` also matches inside other words; read it as an upper bound).

### 1a. `C:\Users\james\Games\I76`

| folder | game | GB | proxy | last-mod | junction | refs | live now? | role / fate |
|---|---|---|---|---|---|---|---|---|
| daily-driver | Gold | 0.65 | 33211f11 | 10-23 08:57 | no (aliases `Interstate76-2026-10-03`, lab `game-dd-*` names point here or at its twin) | D50 T4 L41 A67 | no | **daily driver (Gold)** |
| release-candidate | Gold | 0.49 | 53944fb2 | 10-24 20:49 | no (lab `game-tick` -> here) | D22 L15 | **yes**: launcher lane gate (mciproxy.log 20:49) | **rc (Gold)** |
| lan | Gold | 0.48 | cf4f81da | 10-20 16:43 | no (alias `Interstate76-LAN-2026-10-17`) | D3 | named in lab lock (`lanfix`) | family pack, **retire after the LAN-into-RC merge** |
| golden | Gold | 0.65 | 33211f11 | 10-20 16:43 | no | D115 T72 L21 A18 | no | untouched reference of the driver -> archive + junction |
| nitro | Nitro (stock GOG) | 0.29 | GOG stock | 10-21 08:39 | no | D12 | no (not in use; name only appears as a prefix of `nitro-mp-design` in the lock) | stock reference -> archive + junction |
| nitro-lan | Nitro | 0.29 | 6208d3ad | 10-24 08:28 | no | D (NITRO-LAN-WEEKEND) | no | **nitro rc** (family LAN pack = the rc until a daily exists) |
| nitro-plus-original | Nitro + 1997 content | 0.61 | GOG stock | 10-23 08:16 | no | D7 L1 | no | reference/base for Nitro builds -> archive + junction |
| _archive | packs | 1.83 | - | 10-18 | no | - | no | README says "delete after a month" (10-20): move to D: now, delete after 11-20 |

### 1b. `C:\Users\james\i76-uncap-lab` (real folders)

| folder | game | GB | proxy | last-mod | refs (D/T/L/A) | live now? | fate |
|---|---|---|---|---|---|---|---|
| exp-polish2 | Gold | 0.49 | e78aedd5 | 10-24 20:49 | 56/1/31/13 | **yes** (launcher lane writes PLAY-i76.ps1) | **DEV** -> rename to `dev` + junction `exp-polish2` |
| rc-twin-20261024 | Gold | 0.50 | 53944fb2 | 10-24 20:55 | 17/1/4/35 | **yes** (launcher lane; laptop job t05-a mirrors it) | **TEST** -> rename to `test` + junction |
| exp-nitro-owner | Nitro | 0.30 | e78aedd5 | 10-24 11:49 | 12/-/10/- | no | **NITRO DEV** -> rename `nitro-dev` + junction |
| exp-nitro-polish | Nitro | 0.30 | e78aedd5 | 10-24 20:53 | - | **yes** (Nitro polish lane) | **NITRO TEST** (a twin of nitro-dev) -> rename `nitro-test` after the lane |
| controls-twin-20261024 | Gold | 0.49 | fc6a5960 | 10-24 11:48 | 1/-/-/- | probably FFB focus lane (mciproxy 08:38) | twin: archive at lane end |
| dgv2875-twin-20261024 | Gold | 0.49 | fc6a5960 | 10-24 18:02 | 3/-/-/11 | launcher / dgVoodoo lane | twin: archive at lane end |
| stab-gold-20261024 | Gold | 0.48 | fc6a5960 | 10-24 10:55 | 2 | stability lane (finished? report pending) | twin: archive |
| stab-nitro-20261024 | Nitro | 0.30 | 0c4f109c | 10-24 10:01 | 1 | same | twin: archive |
| exp-nitro-mp | Nitro | 0.47 | b577183c | 10-24 11:00 (strlkup 21:00) | 20/-/18/- | **yes** (`.fps-queue`: nitro-mp-design w53-a1) | Nitro MP lane; hold |
| exp-nitro-mp-b | Nitro | 0.36 | b577183c | 10-24 08:43 | 2/-/4/- | MP lane (2nd instance) | hold, then archive |
| exp-nitro-types / -types-b | Nitro | 0.30 each | 8ba38c6a | 10-23 18:17 / 10:11 | 4 / 2 | types lane (idle?) | hold, then archive |
| exp-nitro-port | Nitro | 0.31 | e5951e0f | 10-22 13:03 | 3/-/12/- | no | archive + junction |
| exp-nitro-stockgl | Nitro | 0.29 | 6a0d40f9 | 10-21 07:23 | 1 | no | archive + junction |
| exp-nitro-mp-gold | Gold | 0.48 | adc4fd49 | 10-21 12:59 | 0/-/8/- | no | archive + junction |
| exp-faredge | Gold | 0.49 | 9b7482b8 | 10-24 10:34 | 10/-/23/- | idle, owner ruling | hold for the ruling, then archive |
| exp-rebase | Gold | 0.49 | 8f8da929 | 10-24 09:01 | 15/-/26/28 | idle | hold for the ruling, then archive |
| exp-debug | Gold | 0.48 | d7a0e9d6 | 10-20 19:10 | 7/-/8/- | no | archive + junction |
| exp-jump2 | Gold | 0.49 | 579c7922 | 10-23 09:08 | 8/-/10/- | no | archive + junction |
| exp-morph | Gold | 0.48 | a4c91532 | 10-22 14:34 | 7/-/22/- | no | archive + junction |
| exp-p19-twin | Gold | 0.48 | ccbe3694 | 10-21 11:09 | 3 | no | archive + junction |
| game-sp | Gold | 0.48 | 406e4c37 | 10-20 16:39 | 14/-/14/- | no | archive + junction |
| game | Gold (sandbox clone) | 0.92 | 9b97b622 | 10-17 17:11 | tools name it (conf-bisect, instruments/*.py, farclip-soak) | no | archive + junction (tools keep working) |
| game-fresh-gold / -nitro | Gold / Nitro | 0.47 / 0.29 | b45643d2 | 10-23 22:08 / 22:22 | 1 / 1 (A7 for gold) | no | archive (fresh-install test copies) |
| game-scott, -b | Gold | 0.47 each | 9bab51fe / 6208d3ad | 10-23 16:34 / 22:17 | D9 A18 / D3 A16 | **yes** (cmd.exe running `PLAY.bat --display` / `PLAY-PREVIEW.bat --display` from them) | Scott kit lane; hold |
| game-scott-c, -motw, -uninst | Gold | 0.47 each | 6208d3ad / 6208d3ad / e5951e0f | 10-23 22:04 / 19:09 / 22:04 | 1 each | no | archive |
| exp-mac, exp-rcdraw | - | 0 | - | empty (1-2 entries) | D2-3 L4-12 | no | archive (empty) |

Not game copies, leave alone: `autotest`, `builds`, `docs`, `tools`, `src`, `refs`, `emu`, `staging`, `cal-staging`, `downloads`, `_stuck-fonts`, `nucleus-coop` (0 GB), `laptop-bench` (0 GB), `OWNER-TESTS-2026-10-17` (0 GB), `queue-*` (0 GB result folders).

### 1c. Junctions in the lab (no space used on C:)

| name | target | live now? | note |
|---|---|---|---|
| game-mpo-c, game-mpo-d | D:\i76-archive\i76-uncap-lab\game-mpo-c / -d (0.71 / 0.68 GB) | **YES: i76.exe pids 5308 and 20420 run from them (Gold LAN fixes lane, 20:54)** | the "archived" copies are still the lane's working copies; do not move or unlink |
| game-mpo-a, -b | D:\...\game-mpo-a / -b (proxy 8dc04f03) | no | done |
| exp-nitro-port-gold | D:\...\exp-nitro-port-gold | log 20:11 today | recently used by the LAN lane; treat as live |
| exp-airespawn, exp-difficulty, -difficulty-b, exp-jump, exp-nitro, exp-nitro-base, exp-p19, exp-polish, exp-rebase-trace, autotest-p19, captures (34 GB) | D:\... | no | archived 10-23 |
| twin-driver | D:\...\twin-driver | no | target of `game-dd-20261003` (561 autotest refs: the harness control twin of the daily driver, proxy 33211f11) |
| game-dd-20261003 | -> twin-driver | no | keep: A/B control, name used by the autotest harness |
| game-tick | -> Games\I76\release-candidate | rc gate | keep: 130 doc / 168 tool refs |

### 1d. `D:\i76-archive` (already archived)

community-20261024 4.63 GB; dgvoodoo 0.06; **i76-uncap-lab 44.4 GB** (captures 34.3, autotest-p19 1.57, airespawn 0.96, nitro-base 0.61, twin-driver 0.67, game-mpo-a..d 0.51-0.71, exp-* about 0.5 each);
rc-backup-20261024 and rc-backup-20261024-2 (0.48 each; dated 10-21, **likely identical, md5-compare then drop one**); tools-20261024 0.01.

### 1e. Laptop `C:\i76-bench` (ssh read-only)

| folder | GB | note |
|---|---|---|
| rc-twin | 0.48 | **live**: laptop `.fps-lock` = `launcher-job t05-a pid 16300 20:55`; the laptop test twin; keep |
| rc-twin-dgv2875 | 0.48 | dgVoodoo 2.87.5 lane (09:38) - delete at lane end (reproducible from the PC pack) |
| scott-a, scott-b, scott-gog | 0.48, 0.48, 0.47 | Scott kit tests (10-24 11:22-18:14) - delete at lane end |
| wmr-twin, kit-a | 0.48 each | WMR / kit bench twins - delete at lane end |
| scott-b.zip | 0.44 | a zip of scott-b; delete once scott-b is gone |
| runs, controls, dgv, dlls, tools, wmr, *.ps1 | < 0.1 | job scripts and results; keep, pull results to the PC first |

Mac graphics: Mac only, nothing on this PC.

## 2. Target layout (four roles)

| role | Gold | Nitro |
|---|---|---|
| **dev** (the working copy lanes build into; the only long-lived writable copy) | `i76-uncap-lab\dev` (= exp-polish2 renamed; junction `exp-polish2` stays so 100+ doc/tool references resolve) | `i76-uncap-lab\nitro-dev` (= exp-nitro-owner renamed; junction left) |
| **test** (the gate twin; the only thing a gate or the harness runs; lanes make twins from it) | `i76-uncap-lab\test` (= rc-twin-20261024; junction left) | `i76-uncap-lab\nitro-test` (= exp-nitro-polish after its lane ends; byte-twin of nitro-dev + nitro-lan proxy) |
| **rc** (what the owner plays before promotion) | `Games\I76\release-candidate` | `Games\I76\nitro-lan` (the family Nitro pack is the release candidate until a daily Nitro exists) |
| **daily driver** | `Games\I76\daily-driver` | **none yet**; first promotion = nitro-lan -> `Games\I76\nitro-daily` (new folder, made from nitro-lan, not by renaming) |

Plus, until it merges: **one** family LAN pack folder `Games\I76\lan` (proxy cf4f81da). It is retired when the other lane has merged it into the RC (`-Release lan`), leaving a junction `lan` -> the RC for the doc aliases `Interstate76-LAN-2026-10-17`.

Not roles but kept because tools name them (all on D: behind a junction): `golden` (driver reference, promotions/rollbacks), `nitro` (stock GOG), `nitro-plus-original`, `game` (sandbox clone), `twin-driver`/`game-dd-20261003` (A/B control), `game-tick` (-> RC), game-mpo-a..d.

Open items for owner: (a) Nitro daily-driver name/timing, (b) whether `golden` should stay a fifth, read-only folder (recommended: yes, on D: behind a junction), (c) `twin-driver` as the control twin: the harness (561 refs) uses `game-dd-20261003` for A/B against the driver; leave until the harness moves to `test`.

## 3. Every other copy

Keep-until dates assume the lanes finish tonight and report by the morning of 2026-10-25; the script's lock checks decide at run time, not the dates.

| copy | action |
|---|---|
| exp-polish2, rc-twin-20261024, exp-nitro-owner, exp-nitro-polish | **rename** (same drive, atomic), junction at old name. Held tonight (files written < 30 min). Keep-for-a-lane-until 10-25 |
| lan | keep until the merge lane lands, then archive + junction. Keep-until 10-26 |
| game-scott, game-scott-b | keep-for-a-lane until the Scott kit lane ends (cmd.exe PLAY processes alive at 21:00), then archive. Until 10-26 |
| exp-nitro-mp, -mp-b, -types, -types-b | keep until the Nitro MP lane ends (a re-use of `.fps-queue`: nitro-mp-design w53-a1), then archive. Until 10-27 |
| controls-twin, dgv2875-twin, stab-gold, stab-nitro | twins from 10-24: archive when their lane reports (the convention in 5: delete at lane end; archive here because D: has room and the logs prove the gate) |
| exp-faredge, exp-rebase | keep until the owner rules on far-edge / rebase, then archive. Until 11-01 |
| golden, nitro, nitro-plus-original, game | **archive to D: + junction** (tools/docs name them; the junction keeps them working) |
| exp-debug, exp-jump2, exp-morph, exp-nitro-mp-gold, exp-nitro-port, exp-nitro-stockgl, exp-p19-twin, game-sp, game-fresh-gold, game-fresh-nitro, game-scott-c, -motw, -uninst | **archive to D: + junction** (the junction is cheap, and the repo has 1-14 doc refs each; drop a junction only when a grep shows no live tool uses it) |
| exp-mac, exp-rcdraw | archive (empty shells), no junction. They may also simply be deleted: `Get-ChildItem -Force -Recurse` shows 1-2 entries, no files |
| Games\I76\_archive | move to D:, delete after 2026-11-20 |
| game-mpo-c, game-mpo-d, exp-nitro-port-gold | **do not touch**: live. After the LAN lane ends they are already on D:; only the junction names remain |
| D: rc-backup-20261024 vs -2 | compare `Get-FileHash` over the tree; if identical, **delete one** (the only delete I recommend, with evidence from the compare). I did not hash them in this lane |
| Laptop rc-twin-dgv2875, scott-a/b/gog, kit-a, wmr-twin, scott-b.zip | delete at lane end (each is a copy of a pack that exists on the PC). Pull `runs\` to the PC first. No D: on the laptop |

**Cruft inside the kept folders** (script, phase `Cruft`, shown per file with sizes in its dry run; files are moved into `D:\i76-archive\consolidated-20261024\cruft\<role>\`, never deleted):

- `STRLKUP.DLL.<md5>-*` and `strlkup.dll.<md5>-*` backups except one whose md5 is named in the folder's `VERSION*.md` (`_rollback` is never touched). Seen: rc 8 files (about 3 MB), test 11 files (about 5 MB), dev 11+ files (STRLKUP.DLL.0c4f109c-pre-stab, .10aaf74c, .1790a308, .2eb345d1-pre-19g, .449237d6, .53750675 ...), nitro-dev `strlkup.dll.0c4f109c-pre-stab` (0.7 MB).
- `*.pre-*`, `*.driver-*`, `*.bak*`: `PLAY-TICK*.bat.pre-tick19f-av` / `.pre-tick19g`, `PLAY-i76.ps1.driver-24e07cce`, `.pre-tick19g`, `.pre-controls24`, `dgVoodoo.conf.driver-71bd2071`, `STRLKUP.DLL.driver-b910850f`, `u32x.dll.driver-544e34bc`, `savegame.dir.pre-edit` (left alone: saves are never touched).
- Kept: `strlkup_orig.dll`, `i76.exe.u32xorig`, `i76shell.dll.orig` (the real originals) and every `_rollback`.
- `input.map.*`: keep the newest backup only (`input.map.bak-20260808-known-good`, `.pre-updown-swap`, `.a66a37f7` in dev are examples).
- Logs: `mciproxy.log` (2-7 MB each), `ipxwrapper.log` (lan 3.9 MB), `histogram.txt`.
- Stale launchers (dev, test, nitro-dev, nitro-test only; rc, driver and nitro-lan only with `-IncludeRcLaunchers`, because the owner reads their README): `PLAY-TICK-33/36/39/44/47/66/CHOOSE`, `PLAY-OWNER-2300-{ATMOS,BIGBLEND,FEATHER,FOG,HAZE,MIRROR,MORPH,SHADE,SMOOTH,SPARSE,TEX,ALL-MENU}`, `PLAY-OWNER-MORPH-STATELESS`, `PLAY-OWNER-NEXT-2300`, `PLAY-OWNER-SKY-*`, `PLAY-WITH-*`. Kept: `PLAY-TICK.bat`, `-42`, `-ALT-TERRAIN`, `PLAY-LAN`, `PLAY-STABLE`, `PLAY-T05`, `PLAY-P18-BALANCED`, `PLAY-OWNER-2300-ALL`, `-ALL-T05`, `DEBUG.bat`, `_superseded*` dirs are moved whole.
- At 21:00 only the daily driver (23 files, 3.3 MB) and nitro-dev (4 files, 2.2 MB) were idle enough to list; the rest print "HELD" until their lane stops.

## 4. The script

`tools/consolidate-copies.ps1` (not run except as a dry run). Phases: `-Phase Archive|Rename|Cruft|All`; `-Only <wildcard>`; `-Execute` is required to change anything; `-Release <name>` lets a row marked `WaitFor` go once its lane reported; `-HeldOk <name>` waives only the 30-minute quiet test; `-IncludeRcLaunchers`.

Lock checks, per folder and per junction target, all of which must pass: no process whose exe or command line is under the path (word-bounded, so `game` is not blocked by `game-scott`); no `.console-test.lock`; the folder is not named in `.console-owner`, `.fps-queue` or `.fps-lock`; no file written in the last `QuietMinutes` (default 30). A move is robocopy to D:, file-count-and-byte compare, a second lock check, then removal and a junction at the old path. It refuses if the destination exists. Same-drive rename for the four dev/test folders, then the junction at the old name.

Dry-run at 21:00 (this lane): 19 ARCHIVE rows (9.96 GB), 12 WAIT rows, held: exp-polish2, rc-twin, exp-nitro-polish (written within 30 min), no row blocked wrongly. Typical commands:

```powershell
cd C:\Users\james\i76-everywhere
.\tools\consolidate-copies.ps1                          # dry run, everything
.\tools\consolidate-copies.ps1 -Execute -Phase Archive  # the 19 idle copies (junctions left)
.\tools\consolidate-copies.ps1 -Execute -Phase Rename   # dev/test/nitro-dev/nitro-test, once nobody holds them
.\tools\consolidate-copies.ps1 -Execute -Phase Cruft    # after the renames
.\tools\consolidate-copies.ps1 -Execute -Release lan,game-scott*,exp-nitro-mp*,exp-nitro-types*   # after those lanes report
```

## 5. Lab convention (text to add to `CONSOLE-LOCK.md` and the lab README)

> ### Copies (2026-10-24, owner: "just have dev, test, rc, and the daily driver")
> There are four long-lived Gold copies and their Nitro equivalents, and nothing else lives in the lab:
> `i76-uncap-lab\dev` (the working copy lanes build into), `i76-uncap-lab\test` (the gate twin), `Games\I76\release-candidate` (rc), `Games\I76\daily-driver`;
> Nitro: `nitro-dev`, `nitro-test`, `Games\I76\nitro-lan` (rc), the daily when it exists.
> - Lanes make **twins from `test`** (`<lane>-YYYYMMDD`), never new long-lived copies. Build into `dev`, gate on a twin of `test`.
> - A twin is **deleted (or archived to `D:\i76-archive`) when its lane ends**; the lane's closing report names it and says which. A twin older than 3 days with no lane is a defect.
> - Nothing is run from `dev` for an owner test, and nothing is ever experimented on in `daily-driver` or `release-candidate`.
> - A folder that docs or tools name by an old name keeps a **junction** from the old name; remove a junction only when `grep` finds no use.
> - Each kept folder carries an `AGENTS.md` (template: i76-everywhere `docs\AGENTS-GAME-FOLDER.md`).
> - Check before moving or deleting anything: `tools\consolidate-copies.ps1` (dry run) refuses folders with a live process, lock, queue entry or file written in the last 30 minutes.

## 6. Recommendation: what main runs tonight, once the lanes finish

1. Wait for: the Gold LAN fixes lane (game-mpo-c/d), the launcher lane (rc-twin, exp-polish2, RC), the Nitro polish lane (exp-nitro-polish), Nitro MP (exp-nitro-mp), the Scott kit lane (game-scott/-b), the FFB focus lane. Check: `Get-Process i76,nitro`, `.console-owner`, `.fps-queue`, the laptop `.fps-lock`.
2. `consolidate-copies.ps1` (dry run, read it), then `-Execute -Phase Archive` (19 idle copies, 9.96 GB).
3. `-Execute -Phase Rename` (dev / test / nitro-dev / nitro-test), then `grep -rn "exp-polish2\|rc-twin-20261024" tools autotest` to confirm the junction covers them (it should: junctions resolve for every path, but a script that does `Get-Item ... .Target` or compares full paths could differ).
4. `-Execute -Phase Cruft` (about 30 MB, moved not deleted).
5. Then, lane by lane, `-Release <name>` for the held rows (5.1 GB), and add the lab convention text above to `CONSOLE-LOCK.md` and `README.md`.
6. Place `docs/AGENTS-GAME-FOLDER.md` as `AGENTS.md` in the 7 kept roots (fill the role line).
7. After the LAN-into-RC merge: retire `Games\I76\lan`. After 2026-11-20: delete `_archive` on D:. Compare the two `rc-backup-*` folders and drop one.

Caveats: refs counts come from a grep over `.ps1/.py/.md/.bat/.psd1`; builds\ was not searched (too large), so a build script might still name a folder; the junctions cover that. Proxy md5s are file hashes at 21:00 and move with the lanes.

## 7. Done 2026-10-25 (housekeeping lane, waited 21:24-03:35; owner rulings supersede sections 2 and 5)

**Owner rulings applied:** THREE tiers per game - dev, test, main. No golden/reference copy. Main copies are `Games\I76\Interstate 76 Gold` and `Games\I76\Interstate 76 Nitro`.
The lane polled every 10 min for a fully quiet PC; it never came (Gold LAN fixes, Nitro parity, Nitro MP, FFB, launchers/RC gate and `gold-final` lanes ran all night), so it worked per folder:
a folder was touched only when no process used it, it was in no lock/queue line (lane aliases included) and nothing in it had been written for 30 min. Every move was copy, count+bytes compare, then remove.
`tools\consolidate-copies.ps1` was rewritten for the three-tier mapping (Archive / Rename / Cruft, `-CruftRoot`, lane aliases, saves and one-`input.map` rules, locked-file tolerance).

| old | new | state |
|---|---|---|
| `Games\I76\daily-driver` (promotion 18) | `D:\i76-archive\daily-driver-pre-20261025` (the rollback) | done, no junction (only comments and the old promotion scripts name it; its desktop shortcut was moved) |
| `Games\I76\golden` | `D:\i76-archive\consolidated-20261025\Games-I76\golden` | done, junction `golden` (lab `tools\nitro-base\inventory.py` and `stage_retail.py` read it) |
| `Games\I76\_archive`, `nitro`, `nitro-plus-original` | `D:\i76-archive\consolidated-20261025\Games-I76\...` | copied + verified; `_archive` gone; `nitro` and `nitro-plus-original` each keep ONE locked file (deferred 2) |
| lab `game`, `exp-jump2`, `exp-morph`, `exp-nitro-mp-gold`, `exp-nitro-stockgl`, `exp-p19-twin`, `game-sp`, `game-fresh-gold`, `game-scott-c`, `-motw`, `-uninst`, `controls-twin-20261024`, `dgv2875-twin-20261024`, `stab-gold-20261024`, `stab-nitro-20261024` | `D:\i76-archive\consolidated-20261025\lab\<name>` | done, junction at each old name |
| lab `exp-debug`, `exp-nitro-port`, `game-fresh-nitro`, `exp-nitro-mp-b`, `exp-nitro-types`, `-types-b`, `exp-mac`, `exp-rcdraw` | same D: pattern | copied + verified; the C: stub holds only the locked font file (deferred 2) |
| lab `exp-polish2` | `i76-uncap-lab\dev-gold` | done, junction `exp-polish2`; STRLKUP 5D6F9828, i76.exe 6319ABF7, 649 files, 531812674 bytes identical before and after |
| lab `exp-nitro-polish` | `i76-uncap-lab\test-nitro` | done, junction `exp-nitro-polish`; strlkup 9F220AC3, nitro.exe 28B8AE27, 563 files identical |
| lab `exp-nitro-owner` | `Games\I76\Interstate 76 Nitro` (main) | **copied, not moved**: 564 files, 325082770 bytes, strlkup 9E6A2378, nitro.exe 28B8AE27 all equal; the folder rename is blocked (deferred 2) |
| (new) | `i76-uncap-lab\dev-nitro` = fresh copy of main Nitro | done, same md5s |

**Cruft** (moved, never deleted, into `D:\i76-archive\cruft-20261025\<folder>\`): dev-gold 66 files 17.7 MB (stale `PLAY-OWNER-*` / `PLAY-TICK-*` launchers, 17 `STRLKUP.DLL.<md5>` backups, `.pre-*` / `.driver-*`, logs, `_ahk` pre-controls24 files), Interstate 76 Nitro 6 files 4.4 MB, dev-nitro 6 files 4.4 MB, test-nitro 4 files 2.3 MB. The md5 of STRLKUP.DLL / strlkup.dll / i76.exe / nitro.exe / strlkup_orig.dll / input.map is unchanged in all four. Saves (`savegame*`) are never touched (the dry run first listed `savegame.dir.pre-edit`; the rule was fixed before any execute); one `input.map` backup is kept (a `known-good` one if present).
**AGENTS.md** (template filled by `tools\place-agents-md.ps1`) is in `Interstate 76 Nitro`, `dev-gold`, `dev-nitro`, `test-nitro`.
**Desktop:** `Interstate 76 Nitro` -> `Games\I76\Interstate 76 Nitro\PLAY-NITRO-ALL.bat` created. Moved to `Desktop\_i76-old-shortcuts`: I76 - daily driver, I76 Nitro - ALL (test), PLAY-LAB.bat - Shortcut, I76 OWNER TESTS 2026-10-17. `I76 - LAN (family)` and `I76 - release candidate (tick test)` stay until Gold main exists; `tools\make-desktop-shortcuts.ps1` finishes the job.
**Space:** 13.3 GB moved off C: to D: (verified copies). C: free 38.6 GB at 21:24, 44.8 GB at 03:35 while the lanes kept writing; D: free 993 -> 912 GB. The two extra Nitro copies cost +0.6 GB on C:, so the net is about 12.7 GB. Cruft 28 MB.

**Deferred, and why**
1. **Gold main** (`release-candidate` -> `Interstate 76 Gold`) and **test-gold** (`rc-twin-20261024` -> `test-gold`): `rc-lane run-gate.ps1` and `gold-final` (twin-install, lan-pair) were still gating on the twin at 03:35 and will install into the RC afterwards. When they are done: `.\tools\consolidate-copies.ps1 -Execute -Phase Rename`, then `-Phase Cruft`, then `.\tools\make-desktop-shortcuts.ps1`, then `tools\place-agents-md.ps1` for both (Gold main: `-Role main -Game Gold`; test-gold: `-Role test -Game Gold`).
2. **Windows Font Cache Service holds `lee_____.ttf` open** (the game's font; Restart Manager lists pid 4 / FontCache). A folder containing that file refuses delete and rename ("Access denied"). Effects: the 10 C: stubs above keep only that file (their data is verified on D:), and `exp-nitro-owner` could not be renamed to main, so main Nitro was copied and the old folder carries `MOVED-TO-Interstate-76-Nitro.txt` (stale; lanes must not write there). I did not restart the service (a system process I did not start). **Divergence found at 03:35:** a lane wrote a newer `strlkup.dll` into `exp-nitro-owner` after the copy (md5 3F27C797, 798720 bytes, mtime 00:40; main and dev-nitro hold 9E6A2378, 796160 bytes). I did not push it into main (an ungated proxy in the playable copy is the owner's/lane's call); `consolidate-retry-locked.ps1` refuses to junction `exp-nitro-owner` while it differs. To take it: copy that one file into `Interstate 76 Nitro` and `dev-nitro`. After a reboot, log off/on, or an admin `Restart-Service FontCache`, run `tools\consolidate-retry-locked.ps1` (dry run, then `-Execute`): it removes the stubs and leaves junctions to D:, and replaces `exp-nitro-owner` by a junction to main after checking that nothing was written to it.
3. **`lan`** stays: `docs\records\LAN-FIXES-2026-10-24.md` is "staged, not deployed" and `release-candidate\PLAY-LAN.bat` still calls `Games\I76\lan`. **`nitro-lan`** stays until the Nitro MP lane says main Nitro is LAN-capable (`nitro-mp-design` was still running w55/w56). Then `-Execute -Phase Archive -Release lan,nitro-lan`.
4. **Held for lanes / rulings:** `game-scott`, `game-scott-b` (cmd.exe PLAY alive), `exp-nitro-mp` (nitro.exe running), `exp-faredge`, `exp-rebase` (owner ruling).
5. Not done in this pass: D: `rc-backup-*` compare, laptop `C:\i76-bench` deletions.
