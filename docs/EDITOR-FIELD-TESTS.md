# Save editor — 10-minute in-game verification checklist

*Six open questions only gameplay can answer (2026-07-14). Do them in one garage visit +
one mission start. Report results as-is — screenshots are ground truth and have corrected
the format model twice already. Every step is safe: the editor backs up on every write,
and History restores anything.*

Prep: `./i76-save-editor.command`, pick a save you don't mind poking (or Save Bookmark it
to a spare slot first and poke THAT).

| # | Test | Do | Report |
|---|---|---|---|
| 1 | **Paint (vtf @2093)** | Paint Shop → Blue / White → Save Bookmark → load in-game | Is the car blue/white? Does anything glitch (textures, damage decals)? Does the LOAD list still say "Stock (Orange)"? |
| 2 | **GROSS WT calibration** | In the in-game garage, read the form's GROSS WT | The exact number (plus armor total if it's on screen). I'll solve chassis base (candidate 1320) + armor lbs-per-point from it |
| 3 | **Bench cap (13? 14? none?)** | The save already carries 14 repair jobs. In the editor push one more part → repair (15), save, load, open the garage | How many repair jobs does the game list — 13, 14, or 15? |
| 4 | **Suspension van cap (3 or 4?)** | Editor: make sure 4 suspensions sit in the van (V), save, load, garage | Does the game still show all 4 in the van? |
| 5 | **Condition colors (67/34 are guesses)** | Editor: set three spare parts to 70% / 50% / 25% condition, save, load, garage | What highlight color does the game give each (none/green/yellow/red)? |
| 6 | **spc01 = "Radar Jammer"?** | Editor: put Radar Jammer in a special slot (6/7/8 keys), start the mission, press its key | Does the HUD name it? Any observable effect (enemy radar lock behavior)? |

Findings get locked into `i76-save-editor.html`, the `i76-save-editor.py` docstring, and this
table gets updated with ✅/❌ per row.
