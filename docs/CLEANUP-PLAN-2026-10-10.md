# Cleanup plan 2026-10-10 (survey only; nothing changed, nothing launched)

Written from a read-only survey of `C:\Users\james\i76-everywhere` (git, main), `C:\Users\james\i76-uncap-lab`
(git, master, no remote) and `C:\Users\james\i76-map` (git, main, no remote). The daily driver
`C:\Users\james\Games\Interstate76-2026-10-03` and the golden copy `C:\Users\james\Games\Interstate76-golden-2026-10-03`
were listed read-only once and are **out of scope for every action below**. Game copies under the lab
(`game`, `game-*`) are git-ignored lab state: proposals only (section 8).

Companion docs written the same morning and not duplicated here: `docs/BACKLOG-2026-10-10.md` (119 rows; its
R-01, R-14, R-16, S-08, H-03, R-06, R-07, R-09 overlap this plan and are cited) and `docs/OWNER-TEST-LIST.md`.
Both are still **untracked** (section 2).

Rules applied: raw captures and measurement data are evidence (archive or commit, never delete); regenerable
build junk (`__pycache__`, `.obj`, `.exp`, `.stackdump`) may go; the lab twin's `TEST-coll-*.bat` and
`TEST-terrain-watch.bat` are ACTIVE owner tests (keep); a cell says **unknown** where the evidence does not settle it.

## 0. Ranked summary (payoff / risk)

| rank | action | tier | payoff | risk | section |
|---|---|---|---|---|---|
| 1 | Remove the 8 stale worktrees + their branches (all merged, all clean; they keep 9 purged `texture-lab/` blobs alive) | A | high: completes the 2026-10-03 purge, `git worktree list` honest, 120 MB of checkouts | low (reflog keeps the SHAs 90 days) | 1 |
| 2 | Working-tree triage in i76-everywhere: delete `james`, `vehicle_sim.gd`, `grep.exe.stackdump`; commit `promote-2`, `rdp-to-console.cmd` (path comment fixed), the two new docs; ignore `waypoints.json` | A | high: `git status` clean for the first time since 2026-09 | none | 2.1 |
| 3 | `tools/ffb/FfbMixer.ps1` + `ffb-lfe-demo.ps1`: commit as one "untested on the rig" commit, or park on a branch | B (owner) | medium: the only real uncommitted code in the repo | medium: changes mixer behaviour if FFB is run | 2.1 |
| 4 | Lab: commit `CONSOLE-LOCK.md`, `tools/framerate/sweep-suspension.ps1`, `src/*` sources, `flash-probe index.tsv`; delete `TEST-FRAMERATE.bat.pre-presets` (blob in history) | A | medium | none | 2.2 |
| 5 | Lab run evidence: ignore `autotest/**/*.png` / `*.bmp` (1.39 GB of frame dumps stay on disk), commit the ~70 MB of text/scripts in 40 run folders | B | high: 10,381 untracked files -> 0; evidence survives a disk loss | low: repo grows ~70 MB | 2.2 |
| 6 | Lab: 19 run scripts hard-code a Claude scratchpad path; copy `ensure-mute.ps1` + `fixtest.py` beside them and repoint (or use `tools/mute.ps1`) | A | medium: the runs become reproducible from the repo | none (parse check only) | 4.1 |
| 7 | i76-map: `git rm --cached` the 11 tracked `.bmp` (174 MB, PNG siblings already tracked); regenerate the >5 MB ignore block; commit the 32 small untracked probes; keep both versions of `aifire_probe.json` | B | high for i76-map hygiene | low; **no history rewrite** (docs cite SHAs) | 2.3, 6 |
| 8 | Docs: fold the LEGITIMACY pair; retitle the "pending" sections that were applied; update RELEASE-PLAN's residue rows after rank 2 | B | medium | low | 5 |
| 9 | Regenerable junk: 25 `__pycache__` dirs, `.pytest_cache`, `music-fix/Strlkup.build.*`, `Strlkup.dll.pre-trainer` (blob in history), `tools/winmm-cdaudio/*.obj|.exp` | A | low (~2 MB) | none | 2.4 |
| 10 | Proxy switches: none is provably dead *and* risk-free to remove; two candidates for the next source change (`I76_GLIDE_DIR`; u32x `I76_U32X_VPTR*`), 24 README gaps | C | low now, medium later | medium: any source change = rebuild + gate | 3 |
| 11 | Refactors: promote-N shared lib (7 `Md5` copies, 5 copies of the stage-and-readback pattern), proxy `env_flag()` helper (81 hand-rolled `GetEnvironmentVariableA` sites) | C/D | medium | the proxy one needs a gate | 7 |
| 12 | Lab twin leftovers from the promoted cursor test (`PLAY-cursor-test.bat`, `best-wide-cursor.psd1`, `dgVoodoo.wide-cursor.conf` = byte-identical to `wide.conf`, three `_*-backup-*` folders, 22 `texcensus-*.bmp` dumps) | C (owner) | medium | game folder: propose only | 8 |

Tier A = safe to execute now with the check given. Tier B = execute after the one check named. Tier C = propose
to the owner. Tier D = design work.

## 1. Stale worktrees and branches (i76-everywhere)

Evidence (`git worktree list`, `git branch -vv`, `git merge-base`, `git cherry`, `git log --grep`):

| worktree (`.claude\worktrees\`) | branch tip | tip subject (short) | merge into main | clean | cherry `+` |
|---|---|---|---|---|---|
| `agent-a13b42fa8e0ffd681` | `ae59f6f` 2026-10-02 | music-fix: I76_MIRROR_RATE accepts the AiO layout | `4b7b120` | yes | 1 (tip; same subject `5cf7cf2`) |
| `agent-a15743246e7d4f139` | `f7603a4` 2026-10-02 | docs: resolve the 2026-10-02 backlog's stale-claim pairs | `af2462f` | yes | 1 (same subject `c4e037b`) |
| `agent-a224f57625222d58c` | `5863a1a` 2026-10-02 | save editor: lock in the 2026-10-02 sandbox results | `d505901`, `313c23c` | yes | 1 (same subject `003c8b8`) |
| `agent-a466beb1db5cf4bdb` | `1cee0d6` 2026-10-02 | PLAY-i76.ps1 -Preset + presets\*.psd1 | ff / cherry (same subject `e0b89ca`) | yes | 1 |
| `agent-a4e8a13093fefe04c` | `c1a696b` 2026-10-02 | Strlkup.dll rebuilt on the merged source | `d6a424c`, `48b22ed` | yes | 1 (binary only) |
| `agent-a7eef4485c3777c0f` | `e2e71ae` 2026-10-02 | per-frame audit: hazard damage, radar missile turn | `3294f45` | yes | 1 (same subject `aa096b3`) |
| `agent-aa2a8ffdafb72e63e` | `eed42e0` 2026-10-02 | health-pct fix: min(28 + 72 x side, 100 x core) | `883712a` | yes | 1 (same subject `f1db4c5`) |
| `agent-ad15703a2d328fa17` | `3a0d682` 2026-10-02 | backlog: P3 rows closed in e4485ca marked | `206482f` | yes | 1 (all 33 sampled added lines present in `docs/records/BACKLOG-2026-10-02.md`) |

Why the branches look like "400+ commits not in main": main's history was rewritten on 2026-10-03 (`b376ee7`
"texture-lab: game-derived sample files removed from history"), so the 8 branches have **no merge-base** with
main; `git cherry main <branch>` shows every commit but the tip as patch-equivalent (`-`), and the tip of each has
a merge commit in main dated 2026-10-02 (table). Sampled added lines of each tip are in main's files (the few
misses in `a15743` are the conflict side `af2462f` deliberately dropped: "AGENTS.md and SAVE-FORMAT-GAPS.md keep
the save-editor rewrite"; the misses in `a466be` are README preset rows since rewritten). Nothing unmerged.

Consequence worth acting on: each branch still lists 9 `texture-lab/{src,enhanced,build}/` files
(`git ls-tree -r <branch> --name-only | grep -c '^texture-lab/'` = 9; main = 0). The purge is incomplete while
they exist. `git count-objects -vH`: 3,719 loose objects, 29.66 MiB; worktree checkouts ~15 MB each (120 MB).

Other: no other local branches; `origin/main` (`07a5aad`, 2026-10-08) is **5 commits behind** local main (push
pending, not cleanup). No stashes in any of the three repos. `.claude/worktrees/` is excluded by
`.git/info/exclude:11`, so git status never showed them.

Action (Tier A), from `C:\Users\james\i76-everywhere`:

```powershell
# pre-check, per worktree: clean and merged
git worktree list --porcelain
foreach ($b in (git for-each-ref --format='%(refname:short)' refs/heads/worktree-*)) {
  $wt = "C:\Users\james\i76-everywhere\.claude\worktrees\" + ($b -replace '^worktree-','')
  "$b dirty=$((git -C $wt status --porcelain | Measure-Object).Count) cherry+=$((git cherry main $b | Select-String '^\+' | Measure-Object).Count)"
}
# expected: dirty=0 and cherry+=1 for all eight (the lone + is the tip, whose merge commit is in the table)
foreach ($b in (git for-each-ref --format='%(refname:short)' refs/heads/worktree-*)) {
  $wt = "C:\Users\james\i76-everywhere\.claude\worktrees\" + ($b -replace '^worktree-','')
  git worktree remove $wt          # refuses if dirty
  git branch -D $b                 # -D: no merge-base with main, so -d would refuse
}
git worktree prune
```

Verify: `git worktree list` prints only the main checkout; `git branch` prints only `main`;
`git ls-tree -r --name-only main | Select-String '^texture-lab/(src|enhanced|build)/'` prints nothing.

Owner decision (Tier C) to finish the purge physically: `git reflog expire --expire-unreachable=now --all; git gc
--prune=now` — until then the deleted SHAs are recoverable via `git reflog` (default 90 days). Verify afterwards:
`git fsck --unreachable --no-reflogs | Select-String blob | Measure-Object` is small and
`git count-objects -vH` loose count drops from 3,719.

## 2. Untracked and modified files

### 2.1 i76-everywhere (`git status --porcelain`: 1 modified, 8 untracked)

| path | what it is | evidence | action | risk | verify |
|---|---|---|---|---|---|
| `james` (13 B, 2026-09-26) | "ECHO is on." + CRLF: a stray `echo > james` | `file`, `cat`; BACKLOG-2026-10-02 P3-01 "a stray file"; BACKLOG-2026-10-10 R-01 | **delete** | none | `git status --porcelain` no longer lists it |
| `vehicle_sim.gd` (0 B, 2026-10-06 21:22) | empty Godot script stub; nothing references it | `grep -r vehicle_sim` hits only the two backlogs | **delete** | none | same |
| `grep.exe.stackdump` (1.7 KB, 2026-08-01; ignored by `*.stackdump`) | Git-for-Windows crash dump | RELEASE-PLAN.md:312 lists it as residue | **delete** | none | `Test-Path` false |
| `tools/rdp-to-console.cmd` | real tool: `tscon` hands the RDP session to the console (needed for H10 harness runs) | referenced by `docs/records/SAVES-STATE-AND-TEST-PLAN.md:181`, `DOC-CORRECTIONS-PENDING-SIBLINGS.md:312`; line 4 names `docs\FRESH-START-METHOD.md`, which moved to `docs\records\` in `21f9757` | edit line 4 to `docs\records\FRESH-START-METHOD.md`, then **commit** | none (comment only) | `Test-Path docs\records\FRESH-START-METHOD.md`; `git ls-files tools/rdp-to-console.cmd` |
| `tools/promote-2-widescreen-and-controls.ps1` (26 lines) | the applied promotion-2 script (PROMOTIONS row 2, 2026-10-03); the only promote-N not in git (`git ls-files tools | grep promote` = 11 scripts, 1..16 minus 2) | `git log --all -- tools/promote-2*` empty; BACKLOG-2026-10-10 R-01 | **commit** as a record; never run it again (it copies files from the lab twin into the driver) | none | `git ls-files tools/promote-2-widescreen-and-controls.ps1` |
| `tools/ffb/FfbMixer.ps1` (modified +32/-10) | a real fix + retune: `LfeExplodeHz` 22->25, `LfeExplodeAmp` 0.44->0.58, new `LfeExplodeDuck = 0.75`; moves the `BlastEnv` decay out of the firing-edge branch (the diff's own comment: the old placement left `$duck` `$null`, which zeroed the engine and road beds) | `git diff`; last commit to the file `0a61276` 2026-08-12; uncommitted since before 2026-10-02 (P3-01, H-03) | **owner decision**: commit as its own commit with "not yet felt on the rig" in the message (recommended; the diff is self-documenting), or `git stash` / branch `ffb-lfe-duck` if the owner wants the shipped mixer unchanged | medium: `FFB-PANEL.bat` / `ffb-lfe-live.ps1` dot-source it; any FFB session after the commit runs the new tune | parse: `powershell -NoProfile -c "[void][ScriptBlock]::Create((Get-Content -Raw tools\ffb\FfbMixer.ps1)); 'parses'"`; value: dot-source and read `(Mix-DefaultTune).LfeExplodeDuck` = 0.75 |
| `tools/ffb/ffb-lfe-demo.ps1` (233 lines) | offline per-channel shaker demo; dot-sources `FfbMixer.ps1` + `LfeSynth.ps1`; does not itself use the new `LfeExplodeDuck` (0 mentions) | header; RELEASE-PLAN s.7 item 1; REPO-ORG row 1 | **commit together with FfbMixer** (same work, same session) | low | parse check as above |
| `tools/trainer/waypoints.json` (141 B) | runtime state of the trainer GUI (3 slots; one saved 2026-10-03 11:17) | `tools/trainer/i76trainer_gui.py:42 WAYPOINTS = ...waypoints.json`; README-GUI.md:145 | add `tools/trainer/waypoints.json` to `.gitignore`; **do not commit** | none | `git check-ignore tools/trainer/waypoints.json` prints the path |
| `docs/OWNER-TEST-LIST.md`, `docs/BACKLOG-2026-10-10.md` (today 08:10 / 08:19) | the morning audit's two docs | this plan cites them | **commit** | none | `git ls-files docs/BACKLOG-2026-10-10.md docs/OWNER-TEST-LIST.md` |

After these, `git status --porcelain` in i76-everywhere should be empty (plus this plan, which the owner commits).

### 2.2 i76-uncap-lab (809 tracked files; 10,381 untracked; 1 modified)

Named items:

| path | what | evidence | action | verify |
|---|---|---|---|---|
| `CONSOLE-LOCK.md` | the one-agent-at-the-console protocol | read by `autotest/ipx-setup.ps1`, `joy-slot-test.ps1`, `preset-soak.ps1`; cited by `docs/MULTIPLAYER-LOCAL-TEST.md`, `TERRAIN-DROPOUT-2026-10-08.md`, and every `drive-run.ps1` header | **commit** | `git ls-files CONSOLE-LOCK.md` |
| `TEST-FRAMERATE.bat.pre-presets` | backup of the pre-presets launcher | its exact blob is in history: `git log --find-object (git hash-object TEST-FRAMERATE.bat.pre-presets)` -> `df3b9f0` 2026-10-03 | **delete** | the find-object line above is non-empty before deleting |
| `tools/framerate/sweep-suspension.ps1` | real instrument (A/B/A float-constant sweep for the 60 fps body buzz), 2026-10 | header | **commit** | `git ls-files tools/framerate/sweep-suspension.ps1` |
| `autotest/runs/flash-probe-20261005/index.tsv` (modified, +23 rows) | the run index for the 2026-10-05..09 drives (`coll-*`, `cx-*`) | `git diff --stat` | **commit** with the run folders below | `git diff --quiet -- autotest/runs/flash-probe-20261005/index.tsv` |
| `src/build-ds.ps1`, `build-min.ps1`, `dsstub.c`, `dsstub.def`, `patch_min.py`, `patch_wmsetcursor.py`, `u32x_min.c`, `u32x_min.def` | September sources never added (`src/.gitignore` ignores only `*.exe *.dll *.obj *.lib *.exp *.log`); `u32x_min.c` is byte-identical to `i76-everywhere/u32x/u32x_min.c` | `cmp` SAME; `git ls-files src` = 12 files | **commit** (small text) | `git status --porcelain src` shows only the backups below |
| `src/u32x.c.pre-census`, `.pre-dialog-fix`, `.pre-gdifix`, `.pre-kbdfix` (27/12/20/14 KB, 2026-09-05..06) | source snapshots before four u32x fixes; `.pre-dialog-fix` is in history (`aff1c46`), the **other three are not** | `git log --find-object` per blob | keep the three not in history: move to `src/history/` with a one-line README (they are the only record of those intermediate states); delete `.pre-dialog-fix` | `git log --find-object (git hash-object src/u32x.c.pre-dialog-fix)` non-empty before deleting it |
| `src/u32x.dll.pre-dialog-fix` and the other `src/*.dll|*.exe|*.obj|*.log` | ignored build outputs | `src/.gitignore` | leave (ignored); or delete `*.obj *.exp *.lib *.log` only (regenerable) | `git clean -ndX src` lists them first |
| `src/u32x.c` (92 KB, 2026-10-02) | **stale duplicate**: `i76-everywhere/u32x/u32x_full.c` (2026-10-08, `614d38f`) is what promote-16 built `06467bd2` from; 4,089 diff lines between them | `cmp`; `tools/promote-16-cursor-map.ps1` header | propose: replace the body with a 3-line pointer file, or add a top comment "superseded 2026-10-08 by i76-everywhere/u32x/u32x_full.c" (BACKLOG-2026-10-10 R-09 already notes two stale comments in it) | n/a (propose) |
| `builds/` (1.3 MB: `coll-window2-20261008`, `coll-window2b-20261009`, `coll-window2c-20261009`, `cursor-modal-20261008` = 4 STRLKUP.DLL + 1 u32x.dll; `promote-16-stage` = 2 presets + 1 conf) | the gated test builds named by md5 in the twin's `TEST-CURSOR.txt` (c746337f, 1e2efc07, a5b46fb8) and the promote-16 gate (`8de71421` / `a2191719`) | DLLs already ignored by `*.dll`; only the 3 staged text files show as untracked | **commit `builds/promote-16-stage`** (20 KB, documents the gate); keep the DLL folders on disk | `git ls-files builds | Measure-Object` = 3 |
| `cal-staging/` (112 KB: `save009..016.cmp`, `savegame.dir`, `CAL-MANIFEST.md`, 2026-10-02) | a calibration save set with its manifest; no doc in either repo names `cal-staging` | `grep -rn cal-staging` empty | **commit** (owner's own save files, evidence); purpose beyond the manifest: unknown | `git ls-files cal-staging | Measure-Object` = 10 |
| `game/.console-test.lock.stale-20261006` (63 B) | a renamed stale console lock in the sandbox game folder | CONSOLE-LOCK.md says no `.console-test.lock` may exist when taking the console | propose delete (game folder: section 8) | n/a |

Run evidence (`autotest/runs/*`, `autotest/saves/runs/*`): 10,381 untracked files, 1.5 GB. By type:
**.png 1,367 MB / 2,584 files** (frame dumps in `flash-probe-20261005/dumps`, `drives/*`, `garage-ui/*.png`,
`saves/runs/*`), .bmp 22.9 MB / 26, then text: .log 27.6 MB / 269, .tsv 27.6 MB / 85, .cmp 14.8 MB / 1,678
(save-test outputs), .txt 6.9 MB / 2,978, .spc 2.7 MB, .out 2.6 MB / 435, .json 1.4 MB / 519, .md 0.5 MB / 207,
.ps1 20, .py 7. The repo already tracks 504 files of exactly these kinds under `autotest/runs` (287 .txt, 109 .tsv,
34 .log, 13 .md, 9 .png montages, 8 .ps1, 7 .py), so the untracked set is a policy lapse, not a policy. Of the 40
run folders only `flash-probe-20261005` is named in a lab doc (`RENDER-FREEZE-2026-10-04.md`); the others
(`abc-20261004`, `consolidated-20261004`, `ai-traces-2026-10-06`, `twin-sync-20261005`, `escmenu`, `gate`, `joy-slot`,
`mp`, `msgbox`, `music-tmu-20261004`, `nucleus`, `preset-soak` (56 pairs), `renderers`, `two-instance`, `vptr`, 180
`saves/runs/2026100x-*` folders, `garage-ui`, `popup`, `reminder`) are referenced from their own `*.md`/index files
and from i76-everywhere promotion gates (`runs\gate\20261005-112713`, `20261008-204529`).

Action (Tier B):

```powershell
# 1. ignore the frame dumps (already-tracked PNG montages stay tracked: git keeps tracking ignored files it already has)
Add-Content .gitignore "`n# frame dumps and screenshots from autotest runs: evidence, kept on disk, too big for git (1.4 GB on 2026-10-10)`nautotest/**/*.png`nautotest/**/*.bmp"
git ls-files autotest | Select-String '\.png$' | Measure-Object   # expect 9, unchanged
# 2. commit the evidence, one commit per run family so the log stays readable
git add autotest/runs/flash-probe-20261005 autotest/runs/twin-sync-20261005 autotest/runs/consolidated-20261004 autotest/runs/abc-20261004
git add autotest/runs/ai-traces-2026-10-06 autotest/runs/music-tmu-20261004 autotest/runs/preset-soak autotest/runs/renderers
git add autotest/runs/escmenu autotest/runs/gate autotest/runs/joy-slot autotest/runs/mp autotest/runs/msgbox autotest/runs/nucleus autotest/runs/two-instance autotest/runs/vptr autotest/runs/*.out autotest/runs/*.txt
git add autotest/saves/runs
git status --porcelain | Measure-Object       # expect ~10 (the named items above) before their own commits
```

Check before step 2: `git add -n autotest/runs autotest/saves/runs | Measure-Object` and
`(git add -n ... | ForEach-Object { (Get-Item ($_ -replace "^add '|'$")).Length } | Measure-Object -Sum).Sum / 1MB`
should be about 70 MB (if it is above 150 MB a dump type was missed). Verify after: `git status --porcelain |
Measure-Object` = 0; `git ls-files autotest | Measure-Object` ~ 8,300.

Open question for the owner: the `.cmp` save outputs (14.8 MB, 1,678 files) are small but numerous; fine to
commit (recommended) or add `autotest/saves/runs/**/*.cmp` to the ignore rule.

### 2.3 i76-map (37 entries: 4 modified, 33 untracked, all under `captures/014-framerate` except the status files)

| path | what | evidence | action | verify |
|---|---|---|---|---|
| 33 untracked `captures/014-framerate/*.json|*.csv` (173 MB on disk; largest `liveall2_probe.json` 13.2 MB, `liveall_probe.json` 4.0 MB, `music2..4_probe.json` 3.5 MB each, the rest < 1.5 MB; three `tel_live*.events.csv` are 0 B) | raw probe captures, 2026-09-2x (mtimes); same kind as the 170 tracked siblings; **none** is named in `captures/014-framerate/README.md` (0 mentions each) | `.gitignore` policy: files > 5,242,880 B belong in the generated block (`python tools/manifest.py . --large 5242880 --prefix ""`) | regenerate the block (adds `liveall2_probe.json`), `git add` the other 32 (~43 MB), add a README row per file with its mtime and tag field (`"tag"` is in each json's first line) and **description: unknown** where no doc names it | `git status --porcelain captures | Measure-Object` = 0; `git check-ignore captures/014-framerate/liveall2_probe.json` |
| `captures/014-framerate/aifire_probe.json` (modified) | the working copy (3,255,184 B, mtime 2026-09-27 17:15) is a **different run** of the same probe than HEAD (3,298,057 B, committed `ef3ffbd1` the same day; same tag/config, different rows) | `head -c 300` of both; `git log -- <file>` | keep both: `Copy-Item` the working copy to `aifire_probe.rerun-20260927-1715.json`, `git checkout -- captures/014-framerate/aifire_probe.json`, `git add` the copy | `git diff --quiet -- captures/014-framerate/aifire_probe.json`; `(Get-Item ...rerun...).Length` = 3255184 |
| `status/progress.json` (modified: regenerated 24 s after the committed one, `commit_before 07c245a1`), `status/xrefs-9a232dcc.json` (one-line json, delta not readable), `foldin/shell-menu-items.tsv` (all 65 rows: `FUN_*` handler names -> `shell_Menu*`, status `auto` -> `proposed`) | outputs of the 2026-09-26 shell-menu naming pass (`f7c8d63e` "35 handlers named") regenerated and never committed | `git diff`; `git log -- status/progress.json` shows 4 commits that day | **commit** as "status/foldin: regenerate after f7c8d63e"; intent of the `auto -> proposed` column change: **unknown** (the tsv header names `tools/shell_menu_items.py` as the writer) | `python -I tools/shell_menu_items.py` (read-only mode if it has one; else skip) reproduces the tsv; `git status --porcelain status foldin` empty |

### 2.4 Regenerable junk on disk (ignored, not in any index)

25 `__pycache__` dirs (11 i76-everywhere, 5 lab, 9 i76-map), `i76-everywhere/.pytest_cache`,
`music-fix/Strlkup.build.exp`, `Strlkup.build.lib`, `build.log`, `music-fix/Strlkup.dll.pre-trainer` (157 KB,
2026-10-02; its blob is in history at `d628160`), `tools/winmm-cdaudio/winmm.exp`, `winmm_proxy.obj`,
`tools/slow_t{30..180}.png` (6, ignored), lab `src/*.obj|*.exp|*.lib|*.log`. About 2 MB.

Do **not** use `git clean -fdX`: the ignored set also holds `refs/` (43 MB of downloaded references), `tools/ffb/*.csv`
+ `*.wav` (3.6 MB of raw FFB captures = evidence), `texture-lab/*`, `docs/assets-raw/`, `lab-residue/**/*.png`,
and in the lab `captures/` (4.1 GB), `refs/` (1.9 GB), every `game*/`.

```powershell
# preview first
git clean -ndX | Select-String '__pycache__|\.pytest_cache|Strlkup\.build|build\.log|\.pre-trainer|winmm\.exp|winmm_proxy\.obj|slow_t'
# then delete exactly those
Get-ChildItem -Recurse -Directory -Filter __pycache__ C:\Users\james\i76-everywhere, C:\Users\james\i76-uncap-lab\tools, C:\Users\james\i76-map\tools, C:\Users\james\i76-map\data, C:\Users\james\i76-map\verify, C:\Users\james\i76-map\shell, C:\Users\james\i76-map\captures\002-nav | Where-Object FullName -notmatch '\\(\.claude|game[^\\]*|refs|toolchain|external|recon-2026-09-04|sandbox-[^\\]*)\\' | Remove-Item -Recurse -Force
Remove-Item C:\Users\james\i76-everywhere\.pytest_cache -Recurse -Force
Remove-Item C:\Users\james\i76-everywhere\music-fix\Strlkup.build.exp, C:\Users\james\i76-everywhere\music-fix\Strlkup.build.lib, C:\Users\james\i76-everywhere\music-fix\build.log, C:\Users\james\i76-everywhere\music-fix\Strlkup.dll.pre-trainer
Remove-Item C:\Users\james\i76-everywhere\tools\winmm-cdaudio\winmm.exp, C:\Users\james\i76-everywhere\tools\winmm-cdaudio\winmm_proxy.obj
```

Verify: `git clean -ndX | Select-String '__pycache__|Strlkup.build|pre-trainer' | Measure-Object` = 0;
`python -I -m pytest tests -q` in i76-everywhere still collects (it recreates `__pycache__`, which is fine).
Precondition for `Strlkup.dll.pre-trainer`: `git log --all --find-object (git hash-object music-fix/Strlkup.dll.pre-trainer)`
prints `d628160`.

## 3. Proxy switches (`music-fix/strlkproxy.c` 6,241 lines + `cursormap.c` 250 lines, included at line 4890)

Counts: 84 distinct `I76_*` names in the C (81 `GetEnvironmentVariableA` sites in strlkproxy.c, 4 in cursormap.c);
the README switch table names 63; **24 in C and not in the README**; 3 in the README and not in C (`I76_CD1` is a CD
label, `I76_GAME_DIR` is the launcher's, `I76_U32X_MENU` is u32x's). 29 names appear in no preset
(`presets\*.psd1`, the driver's, the twin's), no `PLAY*.bat`/`TEST*.bat`, no `PLAY-i76.ps1`/`LAUNCHER.ps1`, no lab
`autotest\` or `tools\` script. No `#if 0` blocks; every one of the 282 static functions is referenced at least
twice (no unreferenced helpers); the four names that appear twice (`coop_ai_log`, `fp_log_download`,
`install_frame_hook`, `hook_LoadLibraryA`) are forward declarations, not duplicates.

Classification of the 29 unreferenced names:

| class | switches | verdict |
|---|---|---|
| knobs / off-switches of live features | `I76_AI_FIRE_CACHE=0`, `I76_CLUTTER_RISE`, `I76_CRASH_LOG=0`, `I76_FLASH_ROWS`, `I76_HUD_SQUEEZE=0`, `I76_INTERP_SMOOTH`, `I76_ROAD_POOL`, `I76_GLIDE_REFRESH_CODE` | keep; all in the README except `GLIDE_REFRESH_CODE` |
| diagnostics | `I76_CURSOR_LOG`, `I76_FPS_LOG`, `I76_FPS_PROF` (the Mac frame-time measurements in `PORTING-WINDOWS-WINS-TO-MAC.md`), `I76_TEX_CENSUS` (the census `I76_FRAME_SPIKES` builds on; `TEST-terrain-watch` uses it indirectly), `I76_COOP_AI_DIAG`, `I76_COOP_HEAPWATCH` | keep; `FPS_LOG`/`FPS_PROF`/`COOP_HEAPWATCH` missing from the README table |
| documented elsewhere, not in the README table | `I76_COOP_ADOPT/AI/CB/CHAIN/DAMAGE/HEAPGUARD/HOSTMODEL/SHIMLOCK` (docs/COOP.md), `I76_COOP_HEAPLOCK` (nowhere), `I76_JOY_MAP`, `I76_JOY_SYNTH`, `I76_MUSIC_THREAD`, `I76_TELEMETRY` (12 docs), `I76_PHYS_RATE` (**nowhere**), `I76_MISSION`, `I76_SKIP_MOVIES` (lab autotest), `I76_SW_RES` (lab `SOFTWARE-RENDERER-HIRES.md`), `I76_COLL_WINDOW_SITES`, `I76_GLIDE_DIR` | keep; **README gap** = BACKLOG-2026-10-10 R-07 (24 rows to add; `I76_PHYS_RATE` and `I76_COOP_HEAPLOCK` have no doc anywhere: unknown semantics beyond the code) |
| not a switch | `I76_CD2` (a CD volume label in a comment, line 5219) | nothing |
| one-shot acceptance knobs whose test is done | `I76_VOLUME_TEST` (`0d425c6` 2026-10-01: slider chain verified), `I76_LABEL_TEST` (`7d8a188` 2026-09-27: capacity 16 -> 272, 88/88) | **fold, optional**: removing them loses the ability to re-run the acceptance test; harmless to keep. If removed, move the README rows to its History section |
| experiment with a negative live result, in no preset | `I76_GLIDE_DIR` (`5dbca10` 2026-10-03): "did not separate" the DirectDraw and Glide presentations (`docs/ENHANCEMENTS.md:132`, `docs/records/STATUS-2026-10-02.md:157`, BACKLOG-2026-10-10 G-02 and item 8 "abandoned, kept for the record") | **removal candidate** for the next proxy-source change. Caution: the lab's `TERRAIN-WHITE-FLASH.md:16` and `TEXTURE-DELIVERY.md:236` say the `hook_LoadLibraryA` ZGLIDE branch and the refresh wrapper are **shared** with `I76_GLIDE_REFRESH`; remove only the `g_glide_dir` subfolder-preload arm (strlkproxy.c ~4953), keep the hook. Unknown without reading the ~40 lines: whether any other arm reads `g_glide_dir` |
| measured null result, test unfinished | `I76_MIRROR_RATE` (in the README: "costs nothing measurable here. In no preset. Cloud-speed acceptance still not run") | keep |

u32x (`u32x/u32x_full.c`, 2,200 lines; 23 `I76_U32X_*` switches): the `I76_U32X_VPTR` family (8 switches:
`VPTR`, `_WIDEN`, `_WINDOW`, `_MAP`, `_HIDEOS`, `_CURSOR`, `_CURSOR_SHELL`, `_CURSOR_ALWAYS`) is the "one pointer"
experiment, **off by default and abandoned** (`u32x/README.md:31`: the mapping regime is "no longer needed for the
pointer" since the proxy's `I76_CURSOR_MAP`; BACKLOG-2026-10-10 U-10 / item 8). It is referenced by 37 lines of lab
test scripts (`autotest/vptr-test.ps1`, runs) and no preset. `I76_U32X_MENU_ASPECT` (276 references) and
`I76_U32X_SHELL_STRETCH` (promoted, 61) stay. **Removal candidate** for the next u32x source change; the committed
`u32x_full.dll` `06467bd2` is the promoted binary, so a source edit alone would make source and binary diverge.

Why nothing in section 3 is Tier A: the committed `music-fix/Strlkup.dll` (`c11f7f7d`) is the promoted driver
binary, and the source is already 3 commits ahead of it (`4822bcb`, `7f6cb8e`, `552dcb4`; BACKLOG-2026-10-10 "State
of the binaries"). Any source removal must be followed by `music-fix\build-msvc.ps1`, md5 recorded, and the lab gate
(`autotest\gate-folder.ps1` on `game-dd-20261003`, 23 rows on 2026-10-08) before the DLL is committed. Propose,
don't execute in this pass.

Verification for a future removal: `grep -c '"I76_GLIDE_DIR"' music-fix/strlkproxy.c` = 0; the README row moves to
History; `git grep -l I76_GLIDE_DIR -- presets ../i76-uncap-lab/autotest` stays empty (it is today).

Duplicated helpers / dead code noted (section 7 for the refactor): 81 hand-rolled env reads with at least three
different guard idioms (only 9 use `k && k < sizeof(v) && v[0] == '1'`; others test `v[0]` without the length
guard, or presence only); 15 raw `VirtualProtect` sites beside 102 `patch_bytes()` callers (whether each raw site
could use `patch_bytes` is unknown without reading them); `mlog` called 235 times, with `flog` and `vmlog` as the
only variants.

## 4. Scripts: stale paths, duplicates

### 4.1 Hard-coded Claude scratchpad (lab, 19 scripts, Tier A)

All under `i76-uncap-lab\autotest\runs\` and all naming
`C:\Users\james\AppData\Local\Temp\claude\C--Users-james-i76-everywhere\9efdde0c-cb16-4f2c-a58b-7b296e794ca1\scratchpad`:
`ai-traces-2026-10-06\ai-trace-batch.ps1:20`, `consolidated-20261004\run-cond.ps1:5,10,33`,
`flash-probe-20261005\drive-run.ps1:27`, `flash-probe-20261005\freeze-run.ps1:4`, `music-tmu-20261004\{music-batch,
shell-run, soak-runner, t12-probe}.ps1:3`, `music-tmu-20261004\t12sum.py:2`, `render-freeze-20261004\{ab-analyze.py:2,
chain.ps1:1, run-ab.ps1:2, run-ab2.ps1:2}`, `t12-opening-20261004\{batch.ps1:3, probe.ps1:5}`,
`twin-sync-20261005\drive-run.ps1:24`, `twin-sync-20261005\t12\probe.ps1:5`.

That scratchpad still exists (the project's scratchpads total 1.2 GB under `Temp\claude\C--Users-james-i76-everywhere\`)
and holds what they call: `ensure-mute.ps1` (1,683 B: reads and sets the default endpoint's mute, prints
`was=... now=MUTED`), `fixtest.py` (11,488 B), `build\Strlkup-89a97d25.dll`, `build\Strlkup-f9b0c481.dll`, plus
~300 one-off helpers. `god-shm.py` and `drive_stats.py`, which the drive-run headers mention, already live beside
the scripts (`$Here`). The lab has its own `tools\mute.ps1 [-Off]` (same COM call, prints `muted = True/False`).

Action: these run-folder scripts are records of how each run was made, so change the path, not the logic, and
leave a dated comment:

```powershell
$lab = 'C:\Users\james\i76-uncap-lab'
$sp  = 'C:\Users\james\AppData\Local\Temp\claude\C--Users-james-i76-everywhere\9efdde0c-cb16-4f2c-a58b-7b296e794ca1\scratchpad'
Copy-Item "$sp\ensure-mute.ps1" "$lab\autotest\lib\ensure-mute.ps1"          # the read-then-set variant the runs expect ('now=MUTED')
Copy-Item "$sp\fixtest.py"      "$lab\autotest\runs\consolidated-20261004\fixtest.py"
Copy-Item "$sp\build\Strlkup-89a97d25.dll" "$lab\builds\consolidated-20261004\STRLKUP-89a97d25.DLL"   # ignored by *.dll, kept on disk
# then in each of the 19 files: replace the literal with a repo-relative form and add the comment
#   "# 2026-10-10: was <old scratchpad path>; helpers copied into the repo"
# e.g. drive-run.ps1: $sp = Join-Path $A 'lib'    (both drive-run.ps1 define $A = ...\autotest)
```

The other 16 scripts reference scratchpad files whose names should be listed with
`Select-String -Path <file> -Pattern 'scratchpad\\[^"'' ]+'` before copying; whether every one still exists in the
scratchpad: **unknown** (not enumerated here). Verify each edited script parses:
`[void][ScriptBlock]::Create((Get-Content -Raw <file>))`; for the .py: `python -I -m py_compile <file>`. Do not run them.

Alternative with zero edits: a `SCRATCHPAD-NOTE.md` beside each run folder naming the copied helpers. Lower value.

### 4.2 Paths to moved docs

- `tools/rdp-to-console.cmd:4`: `docs\FRESH-START-METHOD.md` -> `docs\records\FRESH-START-METHOD.md` (section 2.1).
- `tools/Make-Wide-Conf.ps1:13,26`, `tools/promote-3a-road-dist-hotfix.ps1:3`, `promote-15-cam-ground-fix.ps1:7,45`,
  `promote-11-tmu-and-music.ps1:49`: all name **lab** docs (`DGVOODOO-CONF-REJECTED.md`, `WIDESCREEN-2D.md`,
  `SOAK-BEST-WIDE-2026-10-03.md`, `RENDER-FREEZE-2026-10-04.md`); all four exist in `i76-uncap-lab\docs\`. Not broken.
- Relative Markdown links in i76-everywhere (every `.md` outside `lab/`, `re/`, `.claude/`): **0 broken** (checked
  `](path.ext)` targets against disk).
- `tools/promote-11-tmu-and-music.ps1:1` and `promote-12-all-fixes.ps1:1` still read "DRAFT 2026-10-04, NOT RUN - the
  owner decides" while `PROMOTIONS.md` row 11 applied that content; which script ran: **unknown** (BACKLOG R-14).
  Propose: owner confirms, then the header gains one line "applied as promotion 11 on <date> (PROMOTIONS.md)".

### 4.3 Duplicates

- `function Md5` is defined in 7 scripts: `tools/promote-11`, `-12`, `-13`, `-15`, `-16`, `Promote-To-Driver.ps1`,
  `Make-Daily-Driver.ps1`. `promote-15/16` also hard-code `$driver`/`$golden` although `Promote-To-Driver.ps1` takes
  them as parameters. The "stage a preset line after an anchor, `Import-PowerShellDataFile` read-back, refuse if driver
  != golden" block is repeated in promote-11, 12, 13, 15, 16 (6 `Import-PowerShellDataFile`, 5 "differs between
  driver and golden"). Refactor: section 7.1. Do **not** edit the existing promote-N scripts (they are records).
- mute / cursor / click helpers: not duplicates of each other. Lab: one mute (`tools\mute.ps1`); the four scratchpad
  variants (`ensure-mute`, `ensure-muted`, `getmute`, `setmute`) live outside every repo (4.1). Cursor: the
  `autotest\calibrate\*cursor*` seven are one pipeline (probe -> solve -> validate), `lib\uiclick.ps1` is the click
  primitive 59 scripts dot-source, `log-clicks.ps1` the recorder; i76-everywhere's `tools\cursor-mode.ps1` and
  `i76-cursor-overlay.ahk` are player-facing. Nothing to fold.
- `flash-probe-20261005\drive-run.ps1` is a declared copy of `twin-sync-20261005\drive-run.ps1` (+`-God`, `-Probe`);
  both `drive_stats.py` copies: run records, leave.
- Public snapshots inside i76-everywhere are behind their sources: `lab/` (last refresh `c81181f` 2026-10-05) differs
  from `i76-uncap-lab` (HEAD 2026-10-09) in 16 `autotest`, 14 `docs`, 7 `tools` files; `re/` is a snapshot of
  i76-map `ee48d0f4`, now **36 commits** behind `bbcb580a`. Refresh: `python -I tools\export_public.py export`
  (stages to `..\i76-public-staging`; the copy into `lab/` / `re/` was done by hand in `a6eeaa5` / `79598e5`: exact
  procedure **unknown** beyond those commits). Tier B; verify with `diff -rq --exclude=runs`.
- Lab twin `game-dd-20261003\_tools\lint-input-map.py` differs from `tools\lint-input-map.py` (the other three
  `_tools` copies match). Game folder: section 8.

## 5. Docs

| doc | problem | evidence | action | verify |
|---|---|---|---|---|
| `docs/SCOPE-AND-LEGITIMACY.md` (4,088 B, 2026-07-18) vs `docs/LEGITIMACY-AND-SCOPE.md` (3,835 B) | two scope statements, different text, same job | `docs/README.md:218-219` ("overlaps the one above; backlog P3-08 proposes folding them"); RELEASE-PLAN s.7 item 6; BACKLOG-2026-10-10 R-06. Referrers of the shorter: `MEMORY-MAP-INDEX.md`, `RE-FIELD-GUIDE.md`, `records/MENU-REBUILD-DESIGN.md`, `RELEASE-PLAN.md`, `REPO-ORGANIZATION-PROPOSAL.md`, `docs/README.md` | fold the shorter's unique paragraphs ("What we actually do" list) into `SCOPE-AND-LEGITIMACY.md`, repoint the 6 referrers, `git rm` the shorter | `git grep -l LEGITIMACY-AND-SCOPE` empty; link check (4.2 method) still 0 broken |
| `docs/DOC-CORRECTIONS-PENDING-SIBLINGS.md` | title and two section headings say "Pending since 2026-10-03" though the header note says both were applied 2026-10-03 (evening); the still-open residue is itemised in BACKLOG-2026-10-10 R-09 | lines 11, 251, 271 | retitle the two headings "Applied 2026-10-03 (was: pending ...)"; add a one-line pointer to R-09 for what is still open | re-read |
| `docs/RELEASE-PLAN.md:312, 379-380` | residue rows still list `james`, `tools/rdp-to-console.cmd`, `grep.exe.stackdump`, `ffb-lfe-demo.ps1` as to-do | this plan section 2.1 | after 2.1: strike them with "done 2026-10-10" | `Select-String -Path docs\RELEASE-PLAN.md -Pattern 'grep.exe.stackdump'` shows the struck row |
| `docs/ENHANCEMENTS.md` | stale rows (u32x "696577dc... not yet", no cursor-map / co-op / `I76_CAM_GROUND_FIX` rows) | BACKLOG-2026-10-10 R-07, G-04 | tracked there; not repeated | n/a |
| `docs/records/READY-TO-TEST.md` | slated for retirement into VERIFIED-FIXES | BACKLOG-2026-10-10 R-06 | tracked there | n/a |
| `music-fix/README.md` switch table | 24 switches missing (section 3) | section 3 | tracked as R-07 | n/a |
| lab twin `game-dd-20261003\TEST-CURSOR.txt` | current to 2026-10-09; needs a closing line when the cursor-test files go (section 8) | read | propose | n/a |
| `COMMUNITY-RESOURCES.md` vs `COMMUNITY-SITEMAP.md`; `VOODOO-PARKED.md` vs `DXGI-DGVOODOO-RESEARCH.md` | not duplicates: `docs/README.md` rows 93/95 and 209/210 explain the split (superseded doc kept as the log) | docs/README.md | nothing | n/a |

## 6. Large files in git

| repo | finding | evidence | action | verify |
|---|---|---|---|---|
| i76-everywhere (`.git` 43 MB; remote GitHub) | tracked > 1 MB: `lab-residue/drive5.csv` 5.97 MB (+3 older versions 4.9/1.3/0.9 MB in history), `lab-residue/lfe-sweep.wav` 1.34 MB, `docs/Interstate76-Controls-Quick-Reference.pdf` 1.21 MB (3 versions; generated by `tools/controls-sheet/build.ps1` and shipped by promotions 1/10). Binaries: `music-fix/Strlkup.dll` 275 KB x **76 versions**, `u32x/u32x_full.dll` + `deck/Strlkup.deck.dll` 7 versions | `git ls-tree -r -l HEAD`, `git rev-list --objects --all` | **no LFS** (43 MB total is fine; the DLL versions are the promotion record by md5). Optional: move `lab-residue/drive5.csv` + `lfe-sweep.wav` to `i76-uncap-lab\captures\ffb\` (ignored there, evidence kept) and `git rm` here; history keeps them, so nothing shrinks | `git ls-files lab-residue` |
| i76-uncap-lab (`.git` 43 MB; no remote) | nothing tracked > 1 MB (two 0.6 MB PNG montages). The 1.5 GB is untracked run data (2.2) | `git ls-tree -r -l HEAD` | section 2.2 ignore rule | n/a |
| i76-map (`.git` 133 MB; no remote) | **11 tracked `.bmp` = 174.5 MB raw**: `captures/012-armour/poke-{138,178}-*.bmp` (7 x 19.8 MB) and `captures/006-variant-a/{form,form2,form3,pre}.bmp` (4 x 11 MB); every one has a tracked `.png` sibling; the `.gitignore` already applies "bitmap ignored, png committed" to the other capture series (items 9, 11, M12) | `git ls-files | grep bmp`; `ls captures/012-armour` | `git rm --cached` the 11, append their paths to `.gitignore` under the existing "screenshot bitmap (png committed)" comment; files stay on disk (manifest policy). **No history rewrite**: i76-map docs and the sibling repos cite its commit SHAs everywhere (e.g. "i76-map cbe728d8"), so a filter-repo would break every citation | `git ls-files | Select-String '\.bmp$' | Measure-Object` = 0; `Test-Path` on all 11; `git check-ignore captures/012-armour/poke-138-after.bmp` |
| i76-map untracked | `captures/014-framerate/liveall2_probe.json` 13.2 MB exceeds the 5 MB policy | `.gitignore` generated block header | regenerate the block (2.3) | `git check-ignore` prints it |

## 7. Refactors with a clear payoff (design; Tier C/D)

1. **`tools/PromoteLib.ps1`** (new; the old promote-N stay as records): `Get-Md5`, `Assert-DriverEqualsGolden
   -Rel`, `Add-PresetLine -Preset -AnchorKey -Line -StageDir` (anchor insert + `Import-PowerShellDataFile`
   read-back + optional gated-md5 check), `Assert-BinaryMd5 -Path -Want`. `promote-15` (47 lines) and `promote-16`
   (67) would be ~20 lines each; `Promote-To-Driver.ps1`'s `$Driver`/`$Golden` parameters replace the literals.
   Verify with `-Plan` on the next promotion: identical "plan:" rows to a hand-written script. Risk: none to the
   driver (the lib only stages); the single writer stays `Promote-To-Driver.ps1`.
2. **Proxy env helper**: `static int env_flag(const char *name, int dflt)` / `env_int` / `env_str` replacing the 81
   `GetEnvironmentVariableA` sites, making the `k < sizeof(v)` truncation guard uniform (today 9 of 81 have it).
   Payoff: readability, one parse rule. Risk: every switch's semantics must be preserved exactly (presence-enables
   vs `=0`-disables vs value), then rebuild (`music-fix\build-msvc.ps1`) and the 23-row gate before the DLL is
   committed. Only alongside the next functional proxy change.
3. **`patch_bytes()` for the 15 raw `VirtualProtect` sites** where the expect/want pattern fits: unknown how many
   do; read each first.
4. **Lab `src/u32x.c`** replaced by a pointer to `i76-everywhere/u32x/u32x_full.c` (4,089 diff lines; the
   everywhere copy built the promoted `06467bd2`), and `src/u32x_min.c` noted as the identical twin of
   `u32x/u32x_min.c`. One line in the lab README.
5. **Lab harness**: `tools\mute.ps1` adopted as the one mute (4.1), listed in `autotest\README.md` beside `lib\`;
   `autotest\lib` already exists (10 files, 59 dot-sourcing scripts), so no new lib is needed.
6. **i76-everywhere root clutter** (20+ `setup-*.sh`, `i76-*.ahk`, `*.swift` stubs at the root):
   `docs/REPO-ORGANIZATION-PROPOSAL.md` rows 2-8 are **deferred with stated reasons** (the Deck installer fetches
   `dgVoodoo.conf` by raw URL from main; `PLAY-i76.ps1` runs from two places; Mac/Deck scripts need one run each).
   Not re-proposed here.

## 8. Game folders (git-ignored lab state: PROPOSE ONLY; the owner acts)

`i76-uncap-lab\game-dd-20261003` (the twin, 686 MB, newest file 2026-10-09). Driver-equal today except the items
below (presets and `dgVoodoo.wide.conf` are byte-identical to the driver's; STRLKUP.DLL is the test build
`a5b46fb8` = driver `c11f7f7d` + COLL_WINDOW + SITES + COCKPIT-UNDER per `TEST-CURSOR.txt`).

| leftover | what | status | proposal |
|---|---|---|---|
| `TEST-coll-A-control.bat`, `TEST-coll-B-window2.bat`, `TEST-coll-C-24fps.bat`, `TEST-terrain-watch.bat` + `presets\lab-coll-A-control.psd1`, `lab-coll-B-window2.psd1`, `lab-coll-C-24fps.psd1`, `lab-terrain-watch.psd1` | the collision A/B/C and terrain-drop owner tests (OWNER-TEST-LIST items 3-4) | **ACTIVE, keep** | remove later with `tools\make-test-variants.ps1 -Remove` once the owner has judged |
| `PLAY-cursor-test.bat` | PLAY.bat + `dgVoodoo.wide-cursor.conf` + preset `best-wide-cursor` | superseded: the cursor map is promotion 15 (2026-10-08), `PLAY.bat` now carries it | delete |
| `Interstate 76\presets\best-wide-cursor.psd1` | best-wide + the first cursor lines; **lacks `I76_CAM_GROUND_FIX`** (the cause of BACKLOG G-01) and has the older cursor-line wording | superseded by the promoted `best-wide.psd1` (diff shows only those lines) | delete (a copy is in `_promote16-backup-20261008\presets\`) |
| `Interstate 76\dgVoodoo.wide-cursor.conf` | `wide.conf` with `CaptureMouse = false` | now **byte-identical** to `dgVoodoo.wide.conf` (`diff` empty) | delete |
| `TEST-CURSOR.txt` | the twin's change log 2026-10-07..09 | keep; append "2026-10-10: cursor-test files removed (promotion 15 carries them)" when the three above go | keep |
| `_cursor-test-backup-20261007\` (752 KB: pre-test STRLKUP.DLL `89a97d25`, `dgVoodoo.conf`, `dgVoodoo.wide.conf`, `I76*.DEF`, `input.map`, `save000..008.cmp`, MANIFEST.txt) | rollback set for the cursor test | superseded (promoted; the driver's `_rollback\15` is the real rollback) | move to `i76-uncap-lab\captures\twin-backups\` or delete; the saves are copies of the twin's own 2026-10-07 saves |
| `_promote16-backup-20261008\` (352 KB: presets + confs before the promotion-16 staging) | same | superseded | same |
| `_playtest-backup-20261004\` (244 KB: 3 confs, 2 presets, STRLKUP.DLL) | pre-playtest set | superseded (the driver has `_rollback\10..15`) | same |
| `Interstate 76\texcensus-*-flashprobe-{lifted,drop}.bmp` (22 files x 0.9 MB = 20 MB, 2026-10-09) | frame dumps from the terrain-watch / flash-probe drives | **evidence** | move to `i76-uncap-lab\captures\flash-probe-20261009\` (ignored, kept) |
| `Interstate 76\mciproxy.log` (1.37 MB, 2026-10-09 09:19) | the proxy log of the last run; `TEST-terrain-watch` tells the owner to read its `TERRAIN-DROP` lines | live | keep |
| `Interstate 76\*.pre-*` (7: `STRLKUP.DLL.pre-promo3-20261003`, `.pre-roadpool`, `i76shell.dll.pre-f7-fd96f871`, `.pre-modals-9d6247a6`, `u32x.dll.pre-f7-696577dc`, `.pre-msgbox-19ab8dd1`, `.pre-promo3-20261003`) and `*.driver-*` (5) | binary backups from 2026-09-07..10-03 | the driver's `_rollback\` holds the promoted states; these are twin-only intermediate states | move to `i76-uncap-lab\builds\twin-history\` |
| `Interstate 76\dgVoodoo.aspect-{14x9,16x10,3x2,4x3,wide}.conf` (5) | `EXPERIMENT.bat` shapes | used by `EXPERIMENT.bat` (still present) | keep while `EXPERIMENT.bat` stays |
| `_tools\lint-input-map.py` | differs from the repo's | stale copy | refresh from `tools\lint-input-map.py` |
| `_carried-over\Interstate 76\` (4.6 MB: `i76.exe.2017galaxy`, `i76.25fps`, `DDraw.dll.old-278`, `grep.exe.stackdump`, four `dgVoodoo.conf.pre-*`, `input.map.CORRUPTED-20260802-183747`, ...) | pre-2026-10-03 residue carried over by `Make-Daily-Driver.ps1` | **unknown** whether anything still needs it; the exe copies are game binaries | owner decides; at minimum keep `i76.exe.2017galaxy` (a distinct exe build) |
| `Interstate 76\Lee.fot` (1.4 KB, 2026-10-09) | a Windows font-resource file the game wrote | harmless | nothing |

Sandbox `game\` (945 MB): `.console-test.lock.stale-20261006` (63 B) and 19 `*.pre-*` / `*.bak*` / `*.old` files
(`STRLKUP.DLL.pre-coop`, `.pre-hiresclock`, `i76shell.dll.pre-toascii-fix`, `gamekey.map.pre-*`, `input.map.pre-*`,
`save000.cmp.bak-*`, `dgVoodoo.conf.bak-*`, `winmm.dll.bak`, `u32x.log.old`, `DDraw.dll.old-278`,
`I76PATCH.DLL.disabled`). Proposal: delete the stale lock; move the backups to `builds\sandbox-history\`.

Other lab game copies (all ignored; newest file date; size): `game-gogtest` 2026-10-03, **1.5 GB**; `game-test-20261004`
2026-10-04, 665 MB; `game-mpb` and `game-nucleus` 2026-10-05, 494 MB each (the co-op pair; co-op work continued
2026-10-06/07 in the proxy, so **unknown** whether they are still the active pair); `game-tex` 2026-10-03, 101-500 MB;
`game-alt` 2026-10-03, 92-491 MB; `game-oglide` 2026-10-03, 90-490 MB (the two sizes are `du` vs `find`, which
suggests hard links or junctions: unknown). Together ~6.4 GB. Owner decision only; nothing proposed beyond the list.

Observed read-only in the daily driver and **not proposed**: `_rollback\2..15`, `_save-backups`,
`Interstate 76\savegame.dir.pre-edit`, `savegame.dir.bak-20261003-192527`, `dgVoodoo.conf.driver-71bd2071`.

## 9. Disk outside the repos (information only)

`C:\Users\james\AppData\Local\Temp\claude\C--Users-james-i76-everywhere\`: 1.2 GB of session scratchpads; the
`9efdde0c-...` one is the dependency of 4.1. Windows may clear `Temp` at any time, which is the reason for 4.1.
Lab `captures\` 4.1 GB and `refs\` 1.9 GB are ignored by design (manifest policy in i76-map, `.gitignore` in the lab).

## 10. Execution order for the next agent

1. Section 1 (worktrees) and 2.1 (i76-everywhere triage, except FfbMixer: ask), 2.4 (junk). Commit in
   i76-everywhere: "tidy: stray files, promote-2 record, rdp-to-console path, waypoints ignored, 2026-10-10 docs".
2. Section 2.2 named items, then the ignore rule, then the run-evidence commits (check the ~70 MB figure first).
3. Section 4.1 (scratchpad paths) in the lab; parse-check each edited file.
4. Section 2.3 and 6 in i76-map (`git rm --cached` the bmps, regenerate the ignore block, keep both aifire runs).
5. Section 5 doc folds.
6. Leave sections 3, 7, 8 for the owner (3 and 7 need a proxy rebuild + gate; 8 is game-folder state).

Final check in each repo: `git status --porcelain` empty (i76-everywhere, i76-map) or listing only the items the
owner chose to keep untracked (lab); `git worktree list` one line; `git fsck --no-dangling` clean.
