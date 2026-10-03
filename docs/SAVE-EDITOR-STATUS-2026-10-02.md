# Save editor status, 2026-10-02

*What works, what is verified byte-exact, what still needs the game. Companion to
[SAVE-FORMAT-GAPS.md](SAVE-FORMAT-GAPS.md) (the format) and [EDITOR-FIELD-TESTS.md](EDITOR-FIELD-TESTS.md)
(the in-game checklist). Written on the worktree branch after the audit requested by the owner.*

## The audit in one paragraph

Both editors (`i76-save-editor.py`, `i76-save-editor.html`) framed every inventory record 32 bytes
late. The game writes each record as a PartNode (0x20: three runtime pointers, **condition at
+0xc, state at +0x10**, 12 leftover bytes) followed by the PartRec (0x54: name, type, class,
def file, full condition, weight). The editors started at the name, so the "+96 cond / +100 loc"
they showed and wrote for a part were the **next** record's condition and state. Everything that
looked like a game quirk followed from that one offset: the "record the game truncates at EOF"
(the last record of a section has no next record), the "corrupt NitrousOxide @9588 shifted by
4 bytes" (the next thing after section A is the section-C count), "+84 inherited pointers",
"+104 mirrors the next record", the unexplained special-part cond values (15/41/100/300 were
the next record's), and the open "V-vs-S rule" and colour mysteries (every 2026-07 probe edited
the wrong record). The `savegame.dir` had the same disease (records at 0x28+60k instead of
4+60k, scene read from the next record) and was already corrected on `main` on 2026-10-01; the
`.cmp` side is corrected here. Reference: the shell's own writer in
`../i76-map/shell/SAVE.md` and `shell/work/cmp-layout.md`, and the Leg A/B harness parser
`../i76-uncap-lab/autotest/saves/parse_saves.py`.

## Disagreements found (old editors vs the game's frame)

| # | Old editor behaviour | Truth | Effect |
|---|---|---|---|
| 1 | `.cmp` records found by signature scan, name at +0 | count-prefixed sections at 0x8c4: `u32 nA`, nA x 116, `u32 nC`, nC x 116; record = PartNode + PartRec | scan missed the last record of every file and every game-rewritten turret (`+0x42 = 11` broke its "12 zero bytes" test): 1 to 14 records missing per file |
| 2 | cond at +96, location at +100 | cond at +0x0c, state at +0x10 of the record itself (= old +96-116, +100-116) | every displayed and written cond/state belonged to the next record |
| 3 | loc 1/2 = (C), 3 = (R), 4 = (V); then "4 = salvage, 2 = van-ish, 1 = car-ish" | state 1 = mounted (one record per equipped name, 21/21 game saves), 2 = van, 3 = repair queue, 4 = dropped/salvage | the (C)/(V)/(S) buckets were shuffled by one record; writes "piled parts into the car" |
| 4 | "first 116-byte train = van, later trains = repair" / "trailing section truncated" | section C = byte copies of the state-3 records, resolved by cond + state 3 + def on load | editor wrote states without touching C: the game dropped unmatched references |
| 5 | Python `parse_dir`: records at 8+60k, scene at +0x38 ("?" for the last) | records at 4+60k, scene at +0; file exactly 4+60n | `--list` showed each slot's scene from the next slot; last slot "?" |
| 6 | `i76-calibration-saves.py` (even after the 2026-10-01 patch) wrote the display name at `off-32`, i.e. over the previous record's name tail, file name and state | name at record +4 | would have corrupted the previous bookmark's record |
| 7 | HTML `padDir` / Python docs: "game drops the last entry unless 56 B slack" | reader stops at `count`; slack harmless, unnecessary | fixed on main 2026-10-01; this branch keeps slack verbatim and never shrinks |
| 8 | repack of dir records zero-filled the name after its NUL | the shell writes its 32-byte edit buffer verbatim (`\0eppers` in `saves/savegame.dir`) | records are now kept raw; byte-exact on all 5 directories |

## What works now

- **Python library + CLI** (`i76-save-editor.py`): `Cmp` (GarageRec, sections A/C, `Part` views with
  name/type/cls/dfl/full/wt/cond/state), `SaveDir`/`DirRec` (raw-preserving), `write_cmp` (rebuilds
  section C from the state-3 records, one-time `.pre-edit` + timestamped `.bak`, read-back verify),
  `write_dir` (never shrinks). `--list`, `--dump`, `--check`, `--json`, interactive edit.
- **Browser editor** (`i76-save-editor.html`): same constants (`HDR_LEN`, `N_COND`, `N_STATE`, `R_*`),
  `parseCmp` with the size formula, `withRepairQueue` on Save Bookmark, badges (C)/(V)/(R)/(S), move
  buttons van/repair/salvage, `reconcileFlags` mounted<->van. Dir side as fixed on main.
- **Calibration staging** (`i76-calibration-saves.py --game DIR --staging OUT`): eight probes + a
  directory that carries the game's records byte for byte + `CAL-MANIFEST.md`. Never writes to DIR.
- **Launchers/installers** (fixed on main 2026-10-01): `PLAY-i76.ps1`, `saves/Install-Saves.ps1`,
  `saves/install-saves.sh`, `i76-launch-stub.swift` use `4 + 60n`.

## Verified byte-exact (tests/test_save_editor.py, 132 tests)

> **Count re-run 2026-10-03:** `python -m pytest tests/` gives **156 passed** with the lab saves folder present and
> **133 passed** on the repo's sample sets alone (`I76_LAB_DIR=""`). The suite is parametrised over every save file
> it finds, so the number moves with the lab folder's contents; STATUS-2026-10-02 and the CHANGELOG wrote 172 the
> same day for the same reason.

- parse -> serialise == input on **every** sample: `saves/` (13), `saves/lab-20261002/` (9 + 2 .spc,
  today's player saves), `saves/windows-20260906/` (7), `saves/rescue-20260718/` (15 incl. the
  `save-01.cmp` orphan), and the live lab copy when present (read-only) - 46 `.cmp`/`.spc` files;
  5 `savegame.dir` files including the padded 876 B and 460 B ones.
- size formula `0x8c4 + 8 + 116*(nA+nC)` and `4 + 60n` on all of them; every record 116 B.
- game invariants on every game-written save: state-1 records == equipped names (multiset),
  section C == state-3 records (multiset), all states in 1..4, all types known. The five saves the
  2026-07 editor wrote (`saves/save008.cmp`, rescue `save004/006/007/008`) fail them - listed as
  such in the test, still round-trip.
- edit semantics: cond/state land on the record named (and not on its neighbour); queueing a part
  grows the file by exactly 116 B and section C by one copy; `.pre-edit` is the original after two
  writes; a directory written after a slot removal keeps its size; adding a slot appends 60 B.
- **HTML == Python**: `tools/tests/test-save-editor-cmp.mjs --json` runs the page's functions over
  the same files and the test compares car, variant, nA, nC, armor, equipped and every record field
  of sections A and C, plus every dir record. The node self-checks (`withRepairQueue` identity on
  consistent files, rebuild after a state edit, `setCond` touches one record) and the existing
  `test-save-editor-dir.mjs` pass.

## Verified in the sandbox (2026-10-02, probes 1 and 2 - locked into both editors)

- **Colours:** `level = floor(3 x cond / full)`, 0 red / 1 yellow / 2 green / 3 (100 %) unmarked,
  specials unmarked (`Part.level()` / `levelOf()`, 22 measured data points in the tests, 1/3 exactly
  is yellow). The colour is stored state.
- **States:** 2 = van pane, 4 = Field Salvage pane (with 1 = mounted and 3 = bench from the data).
- **The 11-weapon cap** (`Inventory_ClassifyParts`, `cmp [list+4], 0xb`): the car/van/bench WEAPONS
  list keeps the first 11 type-7/8 state-1/2/3 records in file order; the rest become state 4
  (Field Salvage) and a mounted one past the cap reads EMPTY on its hardpoint. The editors now warn
  (`Cmp.loadout_warnings()` / `loadoutWarnings()`: over-cap weapons by index, labels without an in-cap
  state-1 record, per-type counts above the garage's list allocations - engines 4, suspensions 6,
  brakes 6, specials 10, wheels 32; `List_Insert` has no bounds check) and on write move the mounted
  weapon records to the front of section A when one sits past the cap (`prepare_for_write()` /
  `prepareForWrite()`); `mounted()` matches labels the way the garage does. The lists are drawn in
  the game's order ((C) ascending, then descending; salvage by name, condition descending).
- The lab's own `save003` carries exactly 11 car/van/bench weapons with the mounted Oil Slick (#62)
  the 11th - inside the cap, no warning; CAL COLOR's three promoted salvage guns pushed it out.

## Verified in the sandbox (2026-10-02, probes 3-7; record in `i76-uncap-lab\autotest\saves\runs\garage-ui\RESULTS.md`)

- **Bench: no cap.** All 15 queued jobs listed (scrolling REPAIR ORDER panel, file order) and the
  editor-rebuilt section C loaded - a `.cmp` written by the new editors loads and plays. The HTML's
  "beyond 14 jobs" heads-up is gone.
- **Van suspensions: no cap of 3/4** (>= 5 listed). The editors no longer block "-> van" at 3/4; the
  only storage bound is the garage's list allocation (engines 4, suspensions 6, brakes 6, specials 10,
  wheels 32, weapons 11-by-cap), reported in the warnings box.
- **Paint:** swapping the vtf repaints the car (hood blue in the mission); the LOAD board prints
  "Scene N. <name>", never the variant text.
- **spc01 = "Radar Jammer"** in the Special 3 row and the SPECIALS chooser (effect in a mission untested).
- **LOAD-board label** = scene + (state == 1): "Scene 7." for scene 7/state 8, "Scene 8." for scene 7/
  state 1 - the editors' `plays()` rule. (Loading those two rows to watch the mission start was not done.)
- The inventory dialog's column heights (ENGINES 4, WEAPONS 11, WHEELS 12 rows) are display limits; the
  2026-07 "panel caps" were those.

## Still open

- the Radar Jammer's in-mission effect;
- loading the CAL LABEL rows to confirm the mission that starts (Leg B covered the state-8 case);
- PartRec +0x42 (11 on turrets) / +0x68 (0..3) and the GarageRec +0x864 slot classes.

## Retracted by this audit

- "the game truncates the last inventory record" / "savegame.dir is written 36 short" - framing.
- "4 = FIELD SALVAGE, 2 = van-ish, 1 = car-ish ... (C) rows are NOT loc-1 records" - the state-1
  records are exactly the (C) rows; the rest was read off the wrong record.
- all 2026-07 colour conclusions (COLOR CAL v1-v3, ALL PERFECT / TRUTH "colours are render-time",
  the turret "persistent colour state not in the file") - every probe set cond on the record after
  the one it named; the saves they produced are the five invariant-failing files above.
- "specials' cond means charges" - specials carry cond 0 in game-written saves.
- "the 13/14 repair jobs" counts - they mixed salvage records in; section C is the queue.
