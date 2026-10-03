# Debug menu — field-test sheet (fill in and report back)

*The run that completes `tools/i76-debugmenu.ahk` and locks the armor map
(docs/MEMORY-MAP-INDEX.md Tier 3b). Every value change during the run is
auto-logged in the prefix, so afterwards the assistant reads the evidence
directly — you mostly just play.*

## Run 2 result (2026-07-19) — the base was wrong; now fixed

The log revealed the real problem behind "wrong values / twice the value":

- The menu was reading `entity − 0x14C8`, which is **12 records too early** — a
  preceding "van" table. Your actual car ammo was buried at rec 12 (50cal) and
  rec 13 (7.62T). The menu now bases on the **verified** ammo table
  (`entity − 0x1228`, PART 12 live-matched to the HUD), so **row 0 = 50cal,
  row 1 = 7.62 turret**, with a **name column** and the absolute address.
- Ammo is **not** 2× the display — that was two counters moving (the real ammo
  record + a van record dropping together). They're now in separate views
  (AMMO vs VAN, cycle with F7), so it reads clean.
- The facet scan's "scanned 0 bytes" was a Wine quirk: an over-wide memory read
  fails wholesale if it touches an unmapped page. F4 now clamps to the entity's
  committed region and tries both tenths and raw encodings.
- Window is bigger (no scroll for the ammo table); F3 renames a row.

If a record still doesn't match a HUD weapon, use the **fire differential**:
fire ONE weapon a few times, and the row whose CURRENT ticks down is that
weapon (the `*` and the log both catch it). That's ground truth for naming.

## Run 1 result (2026-07-19) — what we learned, what changed

The menu WORKS: chain resolved (`entity=0x024c1948`), 17 records, live values
matched the HUD, `music=1`. The two "failures" you saw were both display, not
logic:

- **"Fired, saw no change / no `*`":** it DID detect it — the log caught
  `rec 13 4000 -> 3880` (your 7.62 turret) and `rec 10 5000 -> 4880` draining
  in lockstep. Those rows were just scrolled BELOW the visible ten. Fixed: the
  window now shows 20 rows, and off-screen rows still log + flag. (Bonus
  finding: rec 12 = 50cal, rec 13 = 7.62T, and rec 10 is an unidentified
  counter that drops by the exact same amount as the turret — noted for later.)
- **"Light green, hard to read":** values are now near-black on the white list;
  only the header/status stays green.
- **"Doesn't stay on top":** it re-asserts topmost every ~2s now. But you don't
  need to SEE it for the armor lock — F4 + `--fetch` is fully headless (below).
  If it still hides under the game, that's DxWnd's borderless-fullscreen
  grabbing focus; either play with it hidden (F8) or set the DxWnd profile to a
  smaller window for the test. Alt-Enter does nothing because DxWnd owns the
  window, not the game.
- **The old armor candidate grids (−0x800 / +0x135c) did NOT match your car**
  (they showed 80.0/100.0 and a uniform 40.0 grid, not your 57/57/76 &
  35/35/50). So this run also retired those guesses. The new **F4 facet scan**
  searches a 128 KB window for your actual DEFENSE tuple instead.

## Setup (1 min)

1. Launch the game, load any save, get INTO a mission (car exists).
2. In a terminal: `tools/debugmenu.sh` — a small table window appears top-left.
   (F8 hides/shows it. If it steals focus from the game, click the game window.)
3. Optional fresh logs: `tools/debugmenu.sh --clear` before launching.

## Test A — smoke test + label the table (3 min)

Default view is **AMMO** (`view=ammo` in the status line). Row 0's name column
should read **"50cal MG"** and row 1 **"7.62 Turret"** (auto-named by capacity).

| check | result (fill in) |
|---|---|
| Window renders, 6 columns (frz*/#/name/cur/max/addr), no scroll for ammo? | |
| Row 0 name = "50cal MG", cur ≈ your HUD 50cal (not 2× it)? | |
| Row 1 name = "7.62 Turret", cur ≈ your HUD 7.62T? | |
| addr column on row 0 ≈ 0x…0720 (the verified base)? | |
| `music=` value with music playing / after it stops? | |

**Fire-differential labelling** — the important part. Fire each weapon *alone*,
a few rounds, and watch which row gets a `*` / whose cur drops (the log records
it too). Note `row # ↔ weapon`, and whether cur drops **1:1** with the HUD or
faster (the "twice?" question — this settles it):

| row # | weapon | cur drop per shot vs HUD |
|---|---|---|
| 0 | 50cal MG | |
| 1 | 7.62 Turret | |
| | | |

Press **F7** to peek the **VAN** view (the preceding owned/repair table) and
**GRIDS** (armor candidates), then F7 back to AMMO. Use **F3** to rename any row.

## Test B — live edit (1 min)

Double-click the 50cal row (row 0), enter `9999`.
- HUD ammo shows 9999? ______
- Fires normally and counts down from there? ______

## Test C — freeze (2 min)

Check the checkbox on that same row, then fire a burst.
- HUD ammo stays pinned (re-written every 50ms)? ______
- Uncheck the box: counting down again? ______

## Test D — rearm/repair all (30 s)

Burn some ammo, take some damage, press **F6**.
- All ammo full + damage gauges back to green? ______

## Test E — LOCK THE ARMOR (the big prize) — now a ONE-KEY scan

Your garage DEFENSE panel (from the Build-and-Repair screenshot) reads:
armor F/R/L/B = **100 / 57 / 57 / 76**, chassis F/R/L/B = **70 / 35 / 35 / 50**.
(If you rebuild the car, re-read these first — the scan needs the current ones.)

1. In a mission, press **F4**. The prompt is pre-filled with those 8 numbers
   (armor F,R,L,B then chassis F,R,L,B). If your car is different, edit them —
   comma-separated, in the panel's tenths (type `57` not `570`; ×10 is applied).
2. It sweeps a 128 KB window around the entity for a `(front, 57, 57, 76)` armor
   run and a `(front, 35, 35, 50)` chassis run (front is wildcarded — it may
   already be damaged), and pops a box + logs every hit as an entity-relative
   offset. **Paste that box** (or just `--fetch`).
3. To CONFIRM a hit: take **one more hit on a known side** (e.g. reverse the
   rear into a wall), press F4 again — the offset whose non-front value dropped
   is real. Or freeze the found offsets and watch the DEFENSE gauge stop moving.

If F4 finds nothing, that tells us armor isn't a contiguous 4-facet tuple near
the entity (it may be the per-panel damage grid instead) — say so and I'll widen
the search / switch to a differential (snapshot, take a hit, F4-style diff).

**What this unlocks:** verified armor offsets → named armor rows + a one-key
"full armor" in the menu, and the "you got hit, this hard, on this side" signal
the rumble layer wants.

## Test F — optional victory lap

Freeze the armor rows that moved in E, take another hit:
- DEFENSE gauges don't budge? ______ (that's god-mode, confirming the rows)

## Known rough edges (expected, just note them)

- The GUI ListView is the one UI element never tried under this Wine — if the
  window is blank or checkboxes don't render, say so; there's a fallback plan
  (hotkey-driven rows, no ListView).
- If the game window loses fullscreen focus when the menu opens, note whether
  clicking back in fixes it.
- If `entity=` shows `NO ENTITY` while clearly in a mission, press F5 and note
  whether it recovers.
