# Doc corrections pending in the sibling repos (2026-10-02)

Companion to [BACKLOG-2026-10-02.md](records/BACKLOG-2026-10-02.md) section 2. That table lists 28 pairs of stale or
contradictory claims; the pairs whose stale side lives in **this** repo were corrected in place on 2026-10-02
(commit message lists them). The pairs below have their stale side in `../i76-uncap-lab` or `../i76-map`, which
this pass did not edit. Each entry gives the file and line as of 2026-10-02, what is there, and the replacement
text, so the integrator can apply them verbatim. Line numbers are from a read on 2026-10-02 and may have drifted.

Pair numbers are the backlog's.

> **Added 2026-10-03: a new set of pending lab corrections, the rejected `dgVoodoo.conf`.** Not applied (this
> repo's passes do not edit the lab). Section ["Pending since 2026-10-03"](#pending-since-2026-10-03-the-rejected-dgvoodooconf-lab-docs)
> at the end of this file.

> **Applied 2026-10-02.** Every replacement below was applied as written: the `i76-uncap-lab` ones in lab commit
> `251ec57` (pairs 9, 10, 11, 12, 13, 26; six files under `docs/`), the `i76-map` ones in commit `cbe728d8` (pairs 14, 15,
> 24, 25). Still open after that: pair 12's re-measure (P2-04), pair 15's per-item spec citations (P4-08), pair
> 26's A/A re-test (P4-21). The "code" table at the end: the three rows in this repo are done (`e4485ca`, and
> `Telemetry.ps1` was already correct); the lab's `memlib.ps1:48` is **not** edited (lab code, outside a docs
> pass). This file is kept as the record of what was changed and why.

---

## i76-uncap-lab

### Pair 9 — `docs/framerate/MEASUREMENTS.md:349-351` (the "5-9 % slower at 60 Hz" section)

Current `:349`: `### The car IS measurably slower at 60 Hz — about 5–9% (2026-08-09, n=5 per rate)`
Current `:351`: `This is the one place the game does **not** play the same. Dunes, zero AI, throttle held 25 s:`

Replace `:349` with:

```
### ~~The car IS measurably slower at 60 Hz — about 5–9%~~ (2026-08-09, n=5 per rate) — RETRACTED: this measured terrain, not physics
```

Insert after `:349`:

```
> **Retracted (lab commit `62e0332`; annotated 2026-10-02).** Whole-run speed comparisons measure the terrain the car
> wandered over, not the physics — trap 1 in the "traps" list below (`:396-398`). Level-ground filtering dissolved
> the shortfall. The tables are kept as the record of a wrong result and how it was caught; do not cite them.
```

Replace `:351` with: `*(retracted — see above)* This was read as the one place the game does **not** play the same. Dunes, zero AI, throttle held 25 s:`

### Pair 10 — `docs/framerate/MEASUREMENTS.md:67-76` (item 4 "The sky moves too fast") and `:99-137` (the sky section)

Insert directly after the `:99` heading `## The sky: why freeze-hunting failed, and where to look next (2026-08-10)`:

```
> **Closed 2026-09-27 (pointer added 2026-10-02).** The cloud scroll is `u = fmod(u - 1/(1001 - s), 1)` (and `v`
> alike) once per call with no dt, at 0x405200 and 0x405455..0x4054a9 (s = 0x504c30 = 0.0078):
> `../i76-map/subsystems/framerate.md:36` row 4. The proxy's `I76_FRAMERATE_FIXES` puts it on the 20 Hz grid —
> measured 0.0300 /s at 60 fps = stock 20 fps (stock 60 fps: 0.0899) — and "sky confirmed in play"
> (`../i76-everywhere/music-fix/README.md` switch table). No render-path anchor is needed; the section below is
> the record of why the data-side hunt could not find it.
```

Append to item 4 at `:67` (after "**The sky moves too fast.**"): `*(closed 2026-09-27: render-side constant at 0x405200 / 0x405455, fixed by `I76_FRAMERATE_FIXES`; see the note at the top of "The sky" section)*`

### Pair 11 — `docs/framerate/BODY-MOTION-HUNT.md:50-60` ("Still open (the win condition)") and `:70-110` (next-approach plan)

Insert directly after the `:50` heading `## Still open (the win condition)`:

```
> **Closed 2026-09-27 (annotated 2026-10-02; backlog P2-12).** There is no single damper coefficient to catch. The
> step dependence is `physics_ResolveGroundContact` 0x437230's projection/rest cycle — the body is moved up along
> the surface normal by the deepest wheel penetration in one go per step, roll and pitch rates are eased toward
> fixed targets at 2/s and set to exactly 0 when the velocity-against-normal test passes — a discrete contact model
> tuned for the stock ~42 ms step (`../i76-map/subsystems/framerate.md:73-85`, "Where the step dependence lives";
> capture 014: at rest on 62 % of frames with 25 ms steps, 11-40 % with 16.7 ms, 65 % again with a fixed 25 ms step
> at 60 fps). The fix is the fixed step (`I76_FIXED_STEP=24`) plus `I76_RENDER_INTERP`; body roll was judged good in
> the owner's 2026-10-02 playtest. The parameter sweep and in-process logger plans below are superseded.
```

Prefix `:97` (`**The correct next approach (do this instead of more PowerShell polling):**`) with `*(superseded — see the closed note under "Still open")* `.

### Pair 12 — `docs/framerate/MEASUREMENTS.md:60-66` (item 3, contact/suspension impulses) and `docs/framerate/README.md:257-258` (item 3) — **pending P2-04, annotate only**

Append to both items:

```
*(2026-10-02: i76-map reads the contact model as running once per substep from `physics_StepVehicle` (0x43a104)
and once per frame through `physics_SnapToGround` 0x43d070 (`../i76-map/subsystems/framerate.md:75-85`), so the
per-frame kick is the SnapToGround pass and the fixed step is the principled fix. Not yet re-measured under
`I76_FIXED_STEP=24` — backlog P2-04: `tools/framerate/airborne-test.ps1` + `analyse-airborne.py`, stock 20 vs
fixed 60, A/A first; angular velocity at lift-off should match 20 fps.)*
```

### Pair 13 — `docs/ENGINE-REFERENCE.md:341-351` ("## 9. Open questions")

Replace the six bullets with:

```
- ~~The **authoritative** position the physics integrator writes~~ — **closed**: the pose is the 0x40-byte
  transform at object+0x18 (3x3 float rotation, three position doubles), written by the physics directly; the
  table and scene nodes are consumers (`../i76-map/status/GOAL-COVERAGE.md:25`; the proxy's render interpolation
  swaps it in and out around the render call).
- ~~Projectile system: fired rockets do not appear in the position table~~ — **closed**: the projectile pool is
  specified in `../i76-map/subsystems/weapons.md:4-33`.
- ~~Exact field offsets inside the 0x90 component record~~ — **closed**: `components[24]`, health at +0x70
  (`../i76-map/types/i76_runtime.h:302`).
- ~~Script-VM timer semantics: frames or milliseconds?~~ — **closed**: seconds on the mission clock
  (`../i76-map/data/FSM.md:151`).
- Whether the three render back ends share the same `[0x5DD2BC]`/`[0x5DD2C0]` pointers (expected, untested —
  only Glide was exercised; the i76-map census never saw the D3D back ends run).
- `I76PATCH.DLL` internals: what it hooks, and why it overshoots to ~20.66 fps (`docs/framerate/README.md:33`;
  backlog P4-06: disassemble its trampoline for the Sleep granularity).
```

### Pair 26 — `docs/ENGINE-REFERENCE.md:11-14` and `:95`, `docs/PHYSICS-60HZ.md:115-116`, `docs/ENGINE-LOOP-MAP.md:45-47,79-80`

One "Corrections from i76-map `status/findings.md`" header per file, text as follows.

**`docs/ENGINE-REFERENCE.md`**, insert after `:14` ("re-anchor before trusting anything here."):

```
> **Corrections from `../i76-map/status/findings.md` (batch 2026-09-05, propagated 2026-10-02).**
> - **L001** — 60abf7bc is the *same* 1998-02-19 link as the 2017 Galaxy exe 9a232dcc: `.text` differs in 2,459
>   bytes over 45 clusters (`binaries/diff-9a232dcc-vs-60abf7bc.tsv`) and every address outside those clusters
>   decodes identically in both files. Re-anchor only inside the listed clusters, not "everything".
> - **L024** — `0x5FCDC4` (row below) is the `DS3DLISTENER` block at 0x5fcdc0, written by `fstp [0x5fcdc4]` at
>   0x4224ab inside the function that pushes 0x5fcdc0 to DirectSound (0x42252f); the "poking it moves the camera"
>   observation had no A/A control. Re-test is backlog P4-21 (poke twice with no change, then change). The same
>   claim is in `docs/RESULTS.md:36,44` and `docs/framerate/MEASUREMENTS.md:253-265`.
```

Replace `:95` (`| `0x5FCDC4` | float3+matrix | **eye/view transform**; poking it moves the camera | [live] |`) with:

```
| `0x5FCDC4` | float3+matrix | **DS3DLISTENER block** (0x5fcdc0; L024). The earlier "eye/view transform; poking it moves the camera" reading had no A/A control — re-test scheduled (backlog P4-21) | [live, contested] |
```

**`docs/PHYSICS-60HZ.md`**, replace `:115-116`:

```
Other constants found: `0x4BC71C = 0.05` (= 1/20 s) — read only ~5×/s by `0x40FB2C`, so it is
**not** the physics timestep. `0x4BC59C = 9.8` — never read during gameplay.
```

with:

```
Other constants found — **corrected 2026-10-02 (i76-map finding L092): both addresses were a file-offset-as-VA
slip of the `.rdata` raw/VA delta (0xc00).** `0x4bc71c` actually holds −0.1f and `0x4bc59c` holds 0.2f. The
values meant are at `0x4bd31c = 0.05f` (read by `fmul` at 0x444099) and `0x4bd19c = 9.8f` (read by `fmul` at
0x43a0c9 in 0x438fd0) — both *are* read during gameplay, so "9.8 never read" is false at the corrected address.
Neither is the physics timestep; dt is the variable `0x4fe428` (`simclock_dt`, writer 0x49c920).
```

**`docs/ENGINE-LOOP-MAP.md`**, insert a header near the top (after the title):

```
> **Corrections from `../i76-map/status/findings.md` (2026-09-05, propagated 2026-10-02).**
> - **L006** — instruction addresses inside the sim-clock cluster 0x49c7f0-0x49cbd6 do **not** transfer between
>   builds: the AiO entry of 0x49c920 starts `51 ff 05 1c 7e 5a 00` where pristine starts `83 ec 08 ff 05 1c 7e
>   5a 00`. The function address holds; every instruction site quoted inside it is build-shifted.
> - **L009** — `0x504A28` (`:45`, `:47`, `:80`) is not the physics dt. It is a 1 Hz gate in WinMain 0x402b30
>   (`fsub [0x504a28]` at 0x403a3d, `fcomp` against 1.0f at 0x4bc48c); it lies above 0x501800 so it is bss, not
>   data-init. The dt is `0x4fe428` (`simclock_dt`), written by 0x49c920 and clamped to [0.001, 0.2]
>   (0x4be9ac / 0x4be9b0).
> - **L010** — `0x49C8D0` (`:79`) does not compute dt: it is a net time-offset helper (`call 0x454e00; push eax;
>   call 0x454bc0; fadd [esp+8]`, stores to 0x5a7e78 / 0x5a7e7c). dt is produced in 0x49c920 and read back through
>   `simclock_GetDt` 0x49c8b0; 0x5a7e70 / 0x5a7e78 are sim time / net offset.
```

---

## i76-map

### Pair 14 — `data/LIVE-TESTS.md:111-113` (Results table: "T1..T10 not run")

Replace the single row `| T1..T10 | | | | not run (data track does not drive the console) |` with:

```
| T1 armour chain | 2026-09-05 | 1 run (capture `012-armour`) | entity 0xc3058c0 in the AirBase melee held the eight predicted fields at +0x138..+0x1a0, each equal to the modded ADDON `.vcf` dword x2 (the sandbox loads the user's modded ADDON file: `../i76-everywhere/docs/records/SAVES-STATE-AND-TEST-PLAN.md:23`), engine 200 where the loader stores 100; zeroing +0x178[0] was followed by the vehicle's destruction (`status/tasks/armour-hunt.md:60-66`) | layout and values confirmed live; `armour` vs `armour_hud` naming still waits on the A/B control |
| T3 mass | 2026-10-01 | 1 | telemetry v2 read mass 1951.0 (ent+0xa4) on the sandbox Piranha, alongside engine_power 193960, drag 0.0003, health_pct 100 (`../i76-everywhere` commit `5f1d388`) | read live; the poke-and-observe half not run |
| T2, T4..T10 | | | | not run (data track does not drive the console) |
```

### Pair 15 — `OPEN76-GAPS.md:418-427` (section 21 "Spec gaps to reverse-engineer next")

Insert directly after the `:418` heading:

```
> **(2026-10-02)** Items 2-9 were closed statically in wave 6 (2026-09-27, `status/GOAL-COVERAGE.md:106-108`): AI
> path following, damage visuals, the special-equipment table, HUD drawing, weapon groups, engine pitch and 3D
> sound, player-car choice, CB rules — each now has a spec section in `subsystems/`. Item 1 (DATABASE.MW2 and the
> EFA / SHP / FNT / PCX decoders) remains open. Backlog P4-08: mark each closed item with the spec section that
> closed it; the list is kept as the index of what was asked.
```

(The integrator should cite the exact `subsystems/*.md` section per item; this pass did not resolve them.)

### Pair 24 — `status/VERIFICATION-PROGRAM.md:7-8` (111 `supported`, 1,882 `proposed`)

Prefix `:7` with:

```
**Numbers as of 2026-10-01; the current figures are in `status/GOAL-COVERAGE.md:134-140`** (seventh gate run:
`supported` 670, 40 % of code bytes; `anchored` 143; `proposed` the remainder of 2,217). The paragraph below is
kept as the program's starting point.
```

### Pair 25 — `subsystems/damage.md:110-111` (`input_self_destruct` "static, not yet measured live")

Replace `This is static, not yet measured live.` with:

```
Measured live by the key path: CTRL+ALT+X detonates the player's car and is scripted as `Send-SelfDestruct` in
`../i76-uncap-lab/autotest/lib/cheatlib.ps1`, used for every death-cam run
(`../i76-uncap-lab/docs/framerate/MEASUREMENTS.md:151-153`). The direct byte poke of 0x5367f9 itself is still
unpoked (corrected 2026-10-02).
```

---

## Code in this repo and the lab that still carries a corrected claim (not edited by this docs pass)

Status 2026-10-02: `LAUNCHER.ps1` and both `tools/check-ffb.ps1` rows fixed in `e4485ca`; `tools/ffb/Telemetry.ps1`
already read `TEL_FIRE_ADDR = 0x5367db` (corrected in the file on 2026-09-27, so the row below was stale when
written); `../i76-uncap-lab/autotest/lib/memlib.ps1:48` still open.

| file:line | carries | should read | backlog |
|---|---|---|---|
| `LAUNCHER.ps1:116` | `$want = 0x28 + $n * 60` | `$want = 4 + $n * 60` (and accept `size >= $want`; our padded files are longer) | P3-04 |
| `tools/check-ffb.ps1:24-27` | `$ADDR_OBJECT = 0x52bbcc` "effect object"; comment cites GHIDRA-MEMORY-MAP | `0x52bbcc` is the `Forcefeed` heap handle (`HeapCreate` at 0x445af9); device presence is `[0x52bbe4] != 0` (L083) | P3-18 |
| `tools/check-ffb.ps1:33-35` | registry-key gate check | no registry key gates FFB in the exe (L084); keep only as an informational print or drop | P3-18 |
| `tools/ffb/Telemetry.ps1` `TEL_FIRE_ADDR` | `0x5367d0` as fire | `0x5367d0` is `throttle_up`; `weapon_fire` is `0x5367db` (type 1 byte), `hardpoint1_fire` `0x5367de` (L031) | P3-24 |
| `../i76-uncap-lab/autotest/lib/memlib.ps1:48` | `InFire` = 0x5367D0 | same as above | P3-24 |

## Pending since 2026-10-03: the rejected dgVoodoo.conf (lab docs)

Fact (lab `docs/DGVOODOO-CONF-REJECTED.md`): dgVoodoo 2.87.3 rejected `game\dgVoodoo.conf` as a whole from
2026-08-09 (when `EnableInactiveAppState = true` was added to `[General]` and `[DirectX]`; also
`WindowedAttributes = border`) until 2026-10-02 and ran the 2020 global `%APPDATA%\dgVoodoo\dgVoodoo.conf`. The
docs in this repo that relied on the void results were annotated on 2026-10-03 (`AGENTS.md`, `README.md`,
`docs/records/FPS-120.md`, `docs/records/GRAPHICS-ENHANCEMENT.md`, `docs/WINDOWS-PLAYBOOK.md`, `docs/records/MODERN-SETUP.md`,
`docs/RELEASE-PLAN.md`, `docs/records/BACKLOG-2026-10-02.md`, `docs/records/MENU-USABILITY-PLAN.md`, `docs/records/MENU-REBUILD-DESIGN.md`,
`docs/records/PLAYTEST-2026-10-02.md`, `docs/records/STATUS-2026-10-02.md`, `music-fix/README.md`, `presets/smooth-120.psd1`).
The lab files below were read on 2026-10-03 only as far as a search for "reject" / "void": the mouse doc already
carries the correction in its own section 9.8, the others do not. Line numbers were not taken; the integrator should place each note at the top of the named section.

| lab file | what it says | note to add |
|---|---|---|
| `docs/CONFIG-OPTIONS.md` (whole file; AGENTS.md sends every agent here first) | indexes dgVoodoo knobs by symptom and by section; "dgVoodoo silently ignores a key in the wrong section"; `EnableInactiveAppState` as the fix for the unfocused freeze | Header: "From 2026-08-09 to 2026-10-02 dgVoodoo was rejecting this sandbox's conf as a whole (a key in a section it does not belong to rejects the file, it is not skipped) and running a 2020 global file. Every row here that reports what a key did or did not do in that window is void until re-measured on an accepted conf: `FPSLimit`, `CaptureMouse`, `FreeMouse`, forced refresh, `Resolution`, MSAA. `EnableInactiveAppState` belongs in `[Glide]` only. See `DGVOODOO-CONF-REJECTED.md`." |
| `docs/framerate/README.md` section 6 (the 60 fps ceiling; the `FPSLimit` 0/21/30/45/90/120 matrix, "n = 9 cells") | `FPSLimit` inert in both directions; forced `640x480@120` ignored; ceiling "accepted" | "Void for the conf keys (measured 2026-08-10, conf rejected). The ceiling itself is explained: dgVoodoo paces by the Glide refresh code (`I76_GLIDE_REFRESH`, i76-everywhere `docs/records/FPS-120.md`); 120 is the ceiling of every renderer tested." |
| `docs/MOUSE-ESC-MENU-AND-SAVE-SCREEN.md` (H2, the 1920x1440 pointer box; section 8) | dgVoodoo pins the pointer to a 1920x1440 box at the client origin | "The box was the global conf's `Resolution = h:1920, v:1440`, not a dgVoodoo property; on the fixed conf the pointer clip is 0,0-3440,1440 (i76-everywhere `docs/records/RENDERER-ALTERNATIVES.md` section 11)." The file's section 9.8 ("dgVoodoo had been rejecting `game\dgVoodoo.conf`") already says this; what is missing is a pointer at H2 and section 8. |
| `tools/framerate/uncap-vsync.ps1` header | says the swap interval "is the 60fps cap" | already listed as wrong in i76-everywhere `docs/records/FPS-120.md` section 1 point 2; the cap is the refresh code |
| i76-map capture 014 README line 12 | "FPSLimit=21 did not cap this build (it ran at 60 fps, vsync)" | "Void as a statement about `FPSLimit`: the conf was rejected. The 60 was the Glide refresh code." |

## Pending since 2026-10-03: paths in this repo that moved (sibling repos still name the old path)

The repo tidy of 2026-10-03 (`docs/REPO-ORGANIZATION-PROPOSAL.md`, done / deferred table) moved files. The sibling
repos were searched read-only (`git grep` over tracked files) for every moved name; these are the hits that name a
path, as opposed to a bare memory address or a file name without a folder.

**Lab residue, root -> `lab-residue/`** (`0x501918/`, `drive5.csv`, `fx.csv`, `lfe-sweep.wav`, `swap-renderer.ps1`,
`test-drive.ps1`):

| sibling file | what it says | note to add |
|---|---|---|
| i76-map `foldin/FOLDIN-REPORT.md:259` (Housekeeping) | "Move `C:\Users\james\i76-everywhere\0x501918\` (stray sky screenshots) to `i76-uncap-lab\captures\sky`" | "Since 2026-10-03 the folder is `i76-everywhere\lab-residue\0x501918\`; the move to the lab has not been done." |

The other hits for `0x501918` in both siblings are the memory address, not this folder. No sibling file names
`drive5.csv`, `fx.csv`, `lfe-sweep.wav`, `swap-renderer.ps1` or `test-drive.ps1`.

**Dated records, `docs/<NAME>` -> `docs/records/<NAME>`** (48 files; the list is in
`docs/REPO-ORGANIZATION-PROPOSAL.md` section 8). Counted with `git grep` over tracked files for `docs/<NAME>` or
`docs\<NAME>`: 26 hits in 23 lab files, 1,302 hits in 224 i76-map files. Nothing in either sibling's live tooling
opens one of these files by path (checked: i76-map `tools/foldin_verify.py`, `tools/foldin_coverage.py`,
`tools/merge.py`, `tools/gates/*`; the gates test that a `source` field is present, not that the file exists;
`foldin_coverage.py` walks the whole repo so it finds the new folder). Two generators hold the old folder as a
constant and would need it changed before a re-run.

| sibling file | names (old path `i76-everywhere\docs\...`) | what to do |
|---|---|---|
| lab `README.md` | FRAMERATE-UNCAP-RESEARCH.md | re-path to `docs/records/` |
| lab `autotest/README.md`, `autotest/gate-folder.ps1` (header) | NEW-DAILY-DRIVER-RECIPE.md | re-path (comment / prose only) |
| lab `autotest/saves/runs/garage-ui/RESULTS.md` | MOUNT-VALIDATION.md | a run record: leave, or add a dated note |
| lab `autotest/vptr-test.ps1` (header), `docs/MOUSE-ESC-MENU-AND-SAVE-SCREEN.md`, `src/u32x.c` (2 comments) | MENU-REBUILD-DESIGN.md | re-path. `src/u32x.c`: comments only, the binary does not change |
| lab `tools/framerate/rate-ab.ps1:584` (a string written into the result file) | PER-FRAME-AUDIT-2026-10-03.md | re-path the string |
| lab `tools/graphics/make-variants.py:85` and the 12 `tools/graphics/conf-*.conf` it generates | GRAPHICS-ENHANCEMENT.md | re-path in the generator, regenerate |
| lab `tools/renderers/make-renderer-copy.ps1`, `tools/renderers/switch-renderer.ps1` (headers and one error message) | RENDERER-ALTERNATIVES.md, FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md | re-path |
| i76-map `tools/gen_binaries.py:26` (`METHOD_DOC`, written into `binaries/*.toml` and one evidence `source`) | FRESH-START-METHOD.md | change the constant; regenerated files follow |
| i76-map `foldin/ledger/make_batch.py:30` (`EW = ...\i76-everywhere\docs`, then opens at least 6 moved files: STATIC-RE-FABLE, GHIDRA-MEMORY-MAP, READY-TO-TEST, FRAMERATE-UNCAP-RESEARCH, SHELL-MENU-AND-SAVE-FREEZE, FRESH-START-2026-09-04) | those | a one-off batch builder; it fails on a re-run until they are pointed at `docs\records` |
| i76-map `evidence/E40862`..`E42408` (about 195 files), `foldin/round2/claims.json`, `ledger.json`, `ledger.tsv`, `fields.tsv`, `status/tasks/foldin-r2.batch.json`, `status/tasks/p5-foldin-merge.batch.json` | the `source` field: FFB-DEEP-DIVE.md, FFB-LAPTOP-RECON.md, GHIDRA-MEMORY-MAP.md, STATIC-RE-FABLE.md, READY-TO-TEST.md, FRAMERATE-UNCAP-RESEARCH.md, SHELL-MENU-AND-SAVE-FREEZE.md, FRESH-START-2026-09-04.md | **the owner's call.** These are provenance stamps of where a claim was read on the day; rewriting 1,200 evidence rows to follow a file move is a bulk merge with its own risk. One line in i76-map `README.md` ("`i76-everywhere\docs\<record>` is `docs\records\<record>` since 2026-10-03") covers them without touching a row |
| i76-map `README.md`, `agents/drafter-c.md`, `agents/drafter-pcode.md`, `agents/reviewer.md`, `status/tasks/t0`, `t1`, `t3`, `t6`, `t7`, `tools/merge.py:4` (docstring), `binaries/*.toml` | FRESH-START-METHOD.md | re-path in the README and the three agent briefs (agents are sent to read it); the task files are records |
| i76-map `data/LIVE-TESTS.md`, `status/GOAL-COVERAGE.md` | SAVES-STATE-AND-TEST-PLAN.md, SAVES-LEG-A-RUN-2026-10-01.md | re-path |
| i76-map `subsystems/renderer.md`, `verify/README.md`, `verify/scenarios/camera-farclip.json` | FARCLIP-CAMERA-CRASH.md | re-path |
| i76-map `status/findings.md`, `foldin/FOLDIN-REPORT.md`, `foldin/community/REPORT.md`, `recon-2026-09-04/i76-fresh-start-dossier.html` | several | reports and records: leave, covered by the README line |

Outside all three repos: the owner's untracked `tools/rdp-to-console.cmd` (line 4) names `docs\FRESH-START-METHOD.md`,
and the memory note "I'76 fresh start 2026-09" names `docs/FRESH-START-*.md`. Neither was edited.

## Pairs with nothing left to edit

- **Pair 27, `docs/HEAD-TRACKING.md` (L229, L241):** the findings quote the doc's own refutation (`0x4c2964` "not the
  yaw"; "pitch injection does not work on this build") — the doc already records both as dead ends, so no
  correction was needed.
- **Pair 27, `docs/records/FRESH-START-2026-09-04.md:7` (L002, L003):** L002 (+132 B / WINMM belong to the 2019 AiO build)
  is already corrected in the paragraph as it stands; L003 ("code below 0x4bbe55 identical") was a task premise,
  not a sentence in the doc. L100 was corrected in place (section 1 point 2 and the section 2 table row).
- **Pair 28:** already done on 2026-10-01 (CHANGELOG update bullet, FRAMERATE-UNCAP-RESEARCH header); the
  RELEASE-PLAN row now says so.
