# Calibration probe results, 2026-10-02 (sandbox, cal-staging probes of 17:39, captures in this folder)

Every reading below is from a 640x480 UI capture (`Capture-UI`); colours measured as the mode colour of the row band
(red (231,106,75), yellow ~(240,200,80), green (163,170,79), paper = no highlight).

## 1 CAL COLOR (save009) - condition -> highlight colour: thirds, exactly

level = floor(3 x cond / full): 0 red, 1 yellow, 2 green, 3 (cond == full) unmarked. Specials (full 0) unmarked.

| cond/full | % | colour seen | where |
|---|---|---|---|
| 600/600, 300/300, 200/200, 150/150, 400/400 | 100 | none | van / car lists |
| 191/200 | 95.5 | green | (R) BloxDropper, repair order + inventory |
| 510/600 | 85 | green | (V) 30mm Turret |
| 280/400 | 70 | green | (V) 25mm Turret |
| 110/200 | 55 | yellow | 20mm Turret (overflowed to Field Salvage) |
| 100/200, 50/100 | 50 | yellow | 30cal MG (S), 14in Rally (R) |
| 240/600 | 40 | yellow | 7.62 Turret (overflowed) |
| 107/300, 101/300 | 35.7, 33.7 | yellow | 261ci (S) x2 |
| 100/300 | 33.3 (= 1/3) | yellow | (R) 305ci V-8 |
| 47/150 | 31.3 | red | (V) Disc & Drum |
| 100/400, 37/150, 33/150, 31/150, 29/150, 25/100, 60/400, 20/200, 19/100, 12/200, 11/200, 11/100, 10/100, 7/100, 2/200 | 25 .. 1 | red | many |

## 2 CAL V VS S (save010): state 2 = van, state 4 = Field Salvage

Howitzer (state 2) listed as (V) in the car/van WEAPONS list and absent from Field Salvage; HADES Turret (state 4)
first row of Field Salvage WEAPONS and absent from the van. 11 of 11 C/V/R weapons listed, Oil Slick (C) included.

## The car/van WEAPONS list holds 11 records (the "vanished weapons" rule)

CAL COLOR carries 14 C/V/R weapons. Shown: 11. Missing: the three with the highest file index - #48 (V) 7.62 Turret,
#59 (V) 20mm Turret, #62 (C) Oil Slick. The two turrets appeared in Field Salvage; the dropper hardpoint read
"Empty" although the +1024 label for slot 1 (dropper) is "Oil Slick" and #62 is state 1. James's own save003 has
exactly 11 C/V/R weapons (4 C, 4 V, 3 R), so his Oil Slick is the 11th and mounts; the probe's three added van
turrets pushed it past the cap. With 11 weapons (save010, save011, save013) all show, the Oil Slick mounts, and the
mission HUD lists it (save013-mission.png: 50cal MG, FireRite, 50cal MG, Oil Slick). Display order: (C) records ascending by file index, then the rest
descending. Matches docs/MOUNT-VALIDATION.md (list 0x100d1db4, cap 11, name+state match at load).
Other columns: WHEELS showed 12 rows (4 C + 8 R) in save011, so the wheel list cap is >= 12; ENGINES showed 4 rows
(C, V, R, R) with a 5th queued engine not listed (box height or cap 4: open).

## 3 CAL BENCH 15 (save011): no bench cap at 13 or 14 - all 15 queued jobs are listed

The form's REPAIR ORDER panel shows 10 rows and scrolls (down arrow at (460,245)): bench-0..7.png walk the list in
file order - 13in Stock x4, 261ci x2, Stock, Aim-Nein Msl, 14in Rally x4, 305ci V-8, FlameThrower, BloxDropper -
15 of 15, colours by the thirds rule. (The inventory dialog's per-column boxes show fewer only because of their
height: ENGINES 4 rows, WEAPONS 11, WHEELS 12.) This was also the first in-game load of a section C the editor
rebuilt (15 references): accepted.

## 4 CAL SUSP 4 (save012): the van holds at least 5 suspensions

SUSPENSIONS chooser: (C) Sway Bars, (V) Stock, (V) EtherX Rally, (V) Coil Overs, (V) Sway Bars, (V) Stock - all four
distinct probe suspensions plus the base's extra Stock. No cap of 3 or 4.

## 5 CAL PAINT BLUE (save013): the vtf field repaints the car

LOAD board row reads "Scene 5. CAL PAINT BLUE" (the variant text is not on the board). In the mission the hood is
blue (save013-mission.png / save013-hood.png; the base Piranha is orange), no texture glitch visible in the first
seconds. The F6 key did not change the view in this capture (both shots are the cockpit).

## 6 CAL JAMMER (save014): spc01 is "Radar Jammer"

The Special 3 row and the SPECIALS chooser both print "Radar Jammer" for the spc01 record ((C) X-Aust Brake,
(C) NitrousOxide, (C) Radar Jammer, (V) Structo Bmpr, (V) NitrousOxide). In-mission effect of the key: not tested.
The SPECIALS chooser's CANCEL sat at (360,330) for this 5-row list.

## 7 CAL LABEL (save015 / save016): the LOAD board label is scene + (state == 1)

Board (save013-board.png): the blank-named row with scene 7 / state 8 prints "Scene 7."; the one with scene 7 /
state 1 prints "Scene 8.". As predicted from the 2026-10-01 runs: state 8 prints and loads the scene dword, state 1
prints the next scene. (Loading each to confirm which mission starts: not done.)

## Chooser mechanics (for the drivers)

Row arrows at UI x 258 (Engine y 48, Suspension 65, Brakes 82, tyres 99/116/133/150, #1 Top 175, #2 Top 192, #1 Rear
209, Dropper 226, Special 1/2/3 283/300/317). The chooser's CANCEL sits at (360,290) for lists up to 6 rows and
(360,356) for the 10-row weapons list. FIELD SALVAGE (240,460), DONE (400,460), SAVE BOOKMARK (560,460), SELECT
REPAIRS (540,251) opens the CAR/VAN INVENTORY dialog (DONE/CANCEL at (385,366)/(545,366)). Esc in the garage opens the
Options menu, and a stray click there reached Control Configuration (its device-check MessageBox stole focus;
input.map was NOT touched - lint OK, mtime unchanged) - never press Esc in the garage from a script.
LOAD board: 10 rows visible, scroll arrows at (212,167)/(212,422); after 10 clicks on the down arrow with 17 records,
row k sits at y = 193 + 23 x (k - 7).
