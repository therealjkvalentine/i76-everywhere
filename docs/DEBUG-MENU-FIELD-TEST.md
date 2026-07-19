# Debug menu — field-test sheet (fill in and report back)

*The run that completes `tools/i76-debugmenu.ahk` and locks the armor map
(docs/MEMORY-MAP-INDEX.md Tier 3b). Every value change during the run is
auto-logged in the prefix, so afterwards the assistant reads the evidence
directly — you mostly just play.*

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

## Test A — smoke test (2 min)

| check | result (fill in) |
|---|---|
| Window renders with a 4-column table (not blank/garbled)? | |
| Status line shows `entity=0x…` and `view=INVENTORY`? | |
| How many `rec NN` rows? (expect ~17) | |
| `music=` value while mission music plays / after it stops? | |
| Fire your primary weapon: a row gets a `*` and its cur drops? WHICH rec #? | |

While you're at it — fire each weapon you carry once and note `rec # ↔ weapon`
(the `*` marker makes this instant). This labels the table for good:

| rec # | weapon/part |
|---|---|
| | |
| | |

## Test B — live edit (1 min)

Double-click your primary weapon's row, enter `9999`.
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
