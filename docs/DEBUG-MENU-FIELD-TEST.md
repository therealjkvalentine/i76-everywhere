# Debug menu — field-test sheet (fill in and report back)

*The 15-minute run that completes `tools/i76-debugmenu.ahk` and locks the armor
map (docs/MEMORY-MAP-INDEX.md Tier 3b). Every value change during the run is
auto-logged in the prefix, so afterwards the assistant can read the evidence
directly — you mostly just play and note what you saw.*

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

## Test E — LOCK THE ARMOR GRIDS (5 min — the big prize)

1. **Before the mission** (garage / Build-and-Repair DEFENSE panel), write down:
   - armor F / L / R / B: ____ / ____ / ____ / ____
   - chassis F / L / R / B: ____ / ____ / ____ / ____
2. In mission: **F7** → GRIDS view. Do you see rows whose values ≈ 10× the
   garage numbers (e.g. 57.0 → 570)? Which block — `armor? -0x800…`,
   `chassis? +0x135c…`, both, neither? ______
3. Take **one hit on a known side** (let an enemy hit your LEFT side once, or
   reverse into a wall with the rear).
4. Which rows flashed `*`, and old → new? (Rough note is fine — the exact
   numbers are in the auto-log.) ______
5. After the session: `tools/debugmenu.sh --fetch` and paste the output — or
   just say the run happened; the logs live in the prefix and can be read
   directly.

**What this unlocks:** the armor offsets become verified → the debug menu gets
real armor rows with names, a one-key "full armor", and the rumble layer gets
its "you got hit, this hard, on this side" signal.

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
