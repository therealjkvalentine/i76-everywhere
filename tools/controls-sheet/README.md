# controls-sheet: the printable quick reference, and the check that keeps it true

Output: [docs/Interstate76-Controls-Quick-Reference.pdf](../../docs/Interstate76-Controls-Quick-Reference.pdf),
four US Letter landscape pages: keyboard and mouse, gamepad, HOWAS (wheel and stick), stock 1997 keys vs ours.

## Change a binding, regenerate

1. Edit the source that owns the binding:

   | What | Where |
   |---|---|
   | A key, a mouse button, an analog axis | [`controls/input.map`](../../controls/input.map) |
   | A wheel button | `gWheelBase` / `gWheelAlt` / `gWheelHat` / `gWheelHatAlt` / `gWheelHoldSet` in [`i76-remap.ahk`](../../i76-remap.ahk) |
   | A gamepad button | the `XIPoll` code and its `@pad` comment line in `i76-remap.ahk`, **and** the matching entry under `gamepad.entries` in `controls-sheet.json` (the pad layer is code, not a table) |
   | Mouse buttons 4 / 5 | the `XButton1::` / `XButton2::` lines in `i76-remap.ahk` |
   | The mouse wheel | the `-WheelUp` / `-WheelDown` defaults in [`PLAY-i76.ps1`](../../PLAY-i76.ps1) |
   | A Fighterstick control | the `BTN` / `POV` / `AXIS` tables in [`i76-ch-fighterstick.ahk`](../../i76-ch-fighterstick.ahk) |
   | A label, a group, a physical button name, what a control is meant to do | [`controls-sheet.json`](controls-sheet.json) |

2. Run one command from the repo folder:

   ```
   powershell -ExecutionPolicy Bypass -File tools\controls-sheet\build.ps1
   ```

   It lints the map, checks every source against the others, and then writes `controls-sheet.html`, the PDF and
   the generated table in `docs/CONTROLS.md`. If anything is inconsistent it writes nothing, lists every
   finding and exits 1. `-Png` also writes one PNG per page beside the HTML (needs PyMuPDF; not committed).
   `-Exe <path to i76.exe>` names the exe for the lint; without one the lint is skipped and says so.

3. Look at the PDF, commit the changed sources together with the HTML, the PDF and `docs/CONTROLS.md`.

Requirements: Python 3 (standard library only) and Microsoft Edge for the PDF. It starts no game and no
AutoHotkey script.

## What the check fails on

`python tools/controls-sheet/build_sheet.py --check` (also run by `tests/test_controls.py`):

- an action in `controls-sheet.json` that is not in the map, or an action in the map with no label;
- a key a layer sends that the map does not bind (unless it is listed under `known_mismatches`);
- two actions on one key in the map that are not an allowed set (`allow_shared_keys`);
- `controls-sheet.json` disagreeing with the parsed `.ahk`: a pad entry whose `@pad` line is gone, a `@pad`
  line with no entry, a key the pad code sends that no entry claims, a key bound to another action than
  `expect` says, a wheel button the tables do not have;
- a native `joystick1` button in the map (the layers own every button; a native one beside them fires twice);
- a `known_mismatches` entry that is no longer a mismatch;
- the generated table in `docs/CONTROLS.md` being out of date.

## Known mismatches

Known mismatches: none (the list in `controls-sheet.json` is empty). The check found four on 2026-10-03, all in
the pad layer, and the owner ruled the same day that they be fixed there: LB + D-pad left / right typed `-` / `=`
and now type `,` / `.` (gear down / up); B typed `C` and now types `Tab` (cycle weapon); LB + RT types `1`, which
`controls/input.map` now binds to hardpoint 1. RB, which had no function, holds `Space` (handbrake). None of the
four has been played yet; the daily driver gets the map and the script by promotion after a pad test.

A mismatch that has to stay for a while goes under `known_mismatches` with id `<layer>:<control>:<key sent>`;
it is then printed on its page with a dagger. To close one, bind the key in `controls/input.map` or change the
key in `i76-remap.ahk`, remove the entry, and run the build.

## Files

| File | |
|---|---|
| `build_sheet.py` | Parser, checker and HTML generator. `--check` checks only; `--extract-stock <GOG input.map>` rewrites the stock table |
| `build.ps1` | The one command: lint, check, HTML, PDF |
| `controls-sheet.json` | The human-edited half: labels, groups, names, `expect`, allow-list, known mismatches, status lines |
| `stock-2.1.0.17.json` | GOG's 1997 bindings as facts (action, device, token), extracted from the offline installer's `input.map`; the game file itself is not in the repo |
| `controls-sheet.html` | Generated. Open it in a browser to preview; print = Letter, landscape, background graphics on |

Status lines on the sheet (`status` in the JSON) quote the docs. Do not write "verified" or "played" there
unless a doc records it; cite the doc.
