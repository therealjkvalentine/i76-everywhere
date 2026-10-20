# Layout proposal 2026-10-20: name folders after what they are

Written for the owner on 2026-10-20 after the morning's trap: the lab twin got the PLAY-TICK launchers but not the
tick proxy, so the owner launched a "tick" game that had no tick and a mis-mapped mouse. Nothing in the folder name said
"this copy must stay identical to the daily driver" and nothing said "this is the release candidate". Status: PROPOSAL,
nothing moved. The 2026-10-03 docs/REPO-ORGANIZATION-PROPOSAL.md (repo layout) and docs/CLEANUP-PLAN-2026-10-10.md
(repo hygiene) still stand; this one is about the game copies, the lab and the build packs.

## 1. What exists today

| where | what | size | state |
|---|---|---|---|
| `Games\Interstate76-2026-10-03` | the daily driver (promotion 18) | 668 MB | plays |
| `Games\Interstate76-golden-2026-10-03` | the reference copy of the driver (promotion rollback source) | 666 MB | keep |
| `Games\Interstate76-LAN-2026-10-17` | the family multiplayer pack as deployed everywhere (proxy cf4f81da) | 493 MB | plays |
| `Games\Interstate76-MP-pack-2026-10-17`, `-18` | superseded LAN packs | 1.2 GB | dead |
| `Downloads\I76-stable`, `I76-dgvoodoo`, `Interstate76-i76-everywhere-portable-20260801` | the August portable and its parts | - | dead (the driver was assembled from them on 2026-10-03) |
| lab `game-dd-20261003` | the driver's twin: console gates for promotions, and where the owner play-tests | 687 MB | plays; today it carries the tick19g proxy (old one kept beside) |
| lab `game-tick` | the promotion-19 candidate as gated (PLAY-TICK*.bat, tick19g) | 492 MB | the real release candidate |
| lab `game-sp`, `game-mpo-a..d` | headless harness copies (single player; four multiplayer peers on the Hyper-V adapter) | 2.6 GB | in use by lanes |
| lab, 53 other `game-*` | one-off experiment copies (tick variants, AI melee, cursor, LOD, co-op list, ...) | ~19 GB | none booted since 2026-10-19 except the trng-* set (this morning's tick-range lane) |
| lab `builds\` | 57 dated build folders | 4.7 GB | 5 are live (the three deployed packs, the promotion-19 candidate, the tick19g gate); the rest are finished experiments whose proxies are reproducible from the commits the records cite |
| lab `queue-*` (10), `OWNER-TESTS-2026-10-17`, `cal-staging`, `staging`, `nucleus-coop` | lane message queues and empty staging dirs | 0 MB | dead |
| lab `captures` 10.8 GB, `autotest\runs` 2.8 GB, `emu` 43.6 GB, `refs` 2.1 GB | evidence, the gate runs, the emulator images (the gold standard), reference installs | 59 GB | keep (evidence is never deleted) |
| repo `docs\` | 70 top-level files + 103 records; `OWNER-TEST-LIST.md` is 1,600 lines across every thread | - | hard to find things in |

Inside the game folders the same pattern repeats: backups sit beside the live file (`STRLKUP.DLL.33211f11-pre-19g`,
`PLAY-TICK.bat.pre-tick19g`, nine proxy variants in the twin), so "which file is live" needs a hash check.

## 2. Proposed structure

### 2.1 What the owner double-clicks: `C:\Users\james\Games\I76\`

```
C:\Users\james\Games\I76\
  daily-driver\         what James plays (today: Interstate76-2026-10-03, promotion 18)
  release-candidate\    the next promotion, staged for the owner's play-test (today: lab game-tick = tick19g, PLAY-TICK*)
  lan\                  the family multiplayer pack, byte-identical to what the Macs, laptop and Deck run (today: the LAN copy)
  golden\               the untouched reference of the daily driver (rollback source; today: Interstate76-golden-2026-10-03)
  _archive\             MP-pack-2026-10-17, MP-pack-2026-10-18, the Downloads portable + parts (zipped, or deleted after a month)
```

Rules that keep it readable:

- **The folder name says the role; the version lives inside.** Each of the four has a `VERSION.md` at the top: what it is,
  promotion number, proxy md5, the date it was installed, how to roll back, and for `release-candidate` what it is waiting
  on (the owner's ruling). Dates and promotion numbers leave the folder names.
- **`PLAY.bat` is the default in every folder.** Alternatives are `PLAY-<what it does>.bat` (`PLAY-16x10.bat`,
  `PLAY-stock.bat`, `PLAY-LAN.bat`). In the release candidate: `PLAY.bat` = the tick the owner picks, `PLAY-TICK-CHOOSE.bat`
  explains and asks, and the seven per-millisecond launchers go away once the ruling is in (`PLAY.bat <ms>` and
  `tick-ms.txt` already cover any value).
- **Backups go in `_rollback\<promotion or date>\`, never beside the live file.** The driver already does this
  (`_rollback\1..18`); the twin, the LAN copy and the lab copies get the same, and the `*.pre-*` files beside live ones are
  moved there.
- **A promotion is a move between these folders:** release-candidate -> daily-driver (and golden), with the replaced
  files going to `_rollback\19\`, exactly as PROMOTIONS.md rows 0-18 describe. After promotion 19 the release-candidate
  folder is empty until the next candidate is staged.

### 2.2 The lab: `C:\Users\james\i76-uncap-lab\`

```
i76-uncap-lab\
  twin-driver\          = game-dd-20261003   gates for promotions; must stay hash-identical to Games\I76\daily-driver (VERSION.md says so)
  twin-rc\              = game-tick          gates for the release candidate
  harness-sp\           = game-sp            headless single-player harness copy
  harness-mp-a..d\      = game-mpo-a..d      headless multiplayer peers (IPXWrapper instances E..H on the Hyper-V adapter)
  builds\<pack>\        one folder per DEPLOYED pack or staged candidate; experiments are zipped into builds\_archive\ when the lane's record is committed
  captures\  autotest\runs\  emu\  refs\     unchanged (evidence and references)
  tools\  src\  docs\                        unchanged
```

- The 53 retired experiment copies: each one's `mciproxy.log`, `ipxwrapper.log`, any unique `TEST-*.bat` / preset / conf is
  copied into `captures\retired-copies-20261020\<name>\` (about 1 GB of text), then the copy is deleted (about 19 GB back).
  The binaries are the golden copy plus a pack, so nothing unique is lost.
- `queue-*`, the three empty staging dirs, `OWNER-TESTS-2026-10-17`, `nucleus-coop`: deleted (0 MB, lane residue).
- `builds\`: keep `mp-pack-20261020-overnight`, `-teams`, `-polish` (the deployed chain and its rollbacks),
  `tick-finish-20261018\promotion-19-candidate`, `tick19g-gate-20261020`; the other 52 folders are zipped one archive each
  into `builds\_archive\` (4 GB -> about 1.5 GB) and deleted. Every one of them is cited by a record with the commit it was
  built from, so a proxy can be rebuilt if ever needed.
- Renames are done with a junction left at the old name (`mklink /J game-dd-20261003 twin-driver`) so the 76 lab scripts
  that name the twin and the 36 that name game-tick keep working; scripts are repointed when next touched, and the junctions
  go when `grep` finds no more users.

### 2.3 The repo docs

The 2026-10-03 proposal's deferred stage (one folder per topic under `docs\`) is still the right shape. Two additions:

- `docs\OWNER-TEST-LIST.md` becomes one short list of what is waiting on the owner NOW (rulings + the tests only the owner
  can do), and the per-thread history moves to `docs\records\` (tick, multiplayer, controls ...). Closed sections are
  archived, not kept in the live list.
- Dated status files at the top level (`STATUS-*`, `BACKLOG-*`, `OWNER-MORNING-*`, `CLEANUP-PLAN-*`, this file) move to
  `docs\records\` once acted on; the top level keeps only living documents.

## 3. Rules going forward (so it does not grow back)

1. A lane that creates a game copy names it `exp-<purpose>` and deletes it (logs harvested to captures) in the same lane
   that commits its record. A copy that must outlive a lane gets a `VERSION.md` saying what it is and who uses it.
2. A build folder is kept only while a machine runs it or it is a staged candidate; everything else is zipped at the end
   of the lane.
3. Backups never sit beside the live file: `_rollback\<id>\` in every game folder.
4. A folder that must mirror another (twin-driver = daily-driver) says so in `VERSION.md`, and any lane that puts files in
   it must put the whole set in (today's trap: launchers without the proxy).
5. Launcher names say what they do; the version is inside the folder, not in its name.

## 4. Execution plan (each stage is the owner's go; nothing in it is reversible by accident)

| stage | what | needs | time | risk |
|---|---|---|---|---|
| 0 | `VERSION.md` in the four player folders and the two twins; delete the 0 MB lane residue; zip the 52 dormant build folders | nothing running in the lab | 30 min | none (zips verified by hash before deletion) |
| 1 | harvest logs from the 53 retired lab copies to captures, verify, delete the copies | no lane using them (none since 2026-10-19 except trng-*, done) | 1 h | low: binaries are reproducible |
| 2 | create `Games\I76\`, move + rename the four player folders, junctions at the old names, update PROMOTIONS.md / AGENTS.md / the repo's 44 path references, re-create the desktop shortcuts | no game running; the owner's go | 30 min | medium: anything with the old path hard-coded (shortcuts, the trainer, the save editor) is checked by launching each once afterwards |
| 3 | lab renames with junctions; repoint scripts as touched | no lane running | 30 min | low |
| 4 | repo docs per the 2026-10-03 proposal + the OWNER-TEST-LIST split | - | 2 h | none |

Stages 0 and 1 are housekeeping an agent can do on its own once the owner says go. Stage 2 changes paths the owner
types and clicks, so it is proposed, not done. Promotion 19 can happen before or after stage 2; if before, the files move
with the folder.
