# Interstate '76 — Steam Deck controller design

*You asked for the full inventory, how proven driving games map their controls, and our config as
two options to choose between. Here it is. Interstate '76 is a **car-combat sim** (1997) — closest
cousins are Twisted Metal / Vigilante 8, with a driving core like NFS/GTA. It's keyboard/joystick/
mouse native; menus are **point-and-click** (move a cursor, click items).*

## 1. Every I76 control (the inventory)

**Driving:** accelerate (`W`), brake/decelerate (`S`), steer L/R (`A`/`D`), reverse (`X`),
handbrake / e-brake (`C`), start engine (`I`), shift up/down (`.`/`,`).
**Weapons:** fire selected weapon (`Space`), cycle selected weapon (`Tab`), link/fire-all (`F`),
direct hardpoint fires (`2`–`5`), special/rear weapons (mines, oil, smoke).
**Targeting:** nearest enemy (`T`), next target (`Y`), front target (`Q`), untarget (`U`),
look-at-target (`E`).
**Camera / view:** glance out windows up/down/left/right (`↑↓←→`), change view (`V`),
binoculars (`B`), zoom (`PgUp`/`PgDn`).
**Info / systems:** map (`M`), notepad (`N`), radar range (`R`), radar camera (`K`),
headlights (`H`), horn (`G`), poetry (`P`), scores (`'`/`;`).
**Menus:** move cursor + **left-click to select**; `Esc` back/pause; skip cutscene = **click**.

> **Note on I76's weapon model:** there is no fixed "primary/secondary fire." You *select* a weapon
> group and fire it (`Space`), cycle the selection (`Tab`), and can *link* groups to fire together
> (`F`). Rear "special" weapons (mines/oil) are droppers. So "R2 = primary, L2 = secondary" maps
> best to **R2 = fire selected**, **L2 = fire-all/linked**, **R1 = change which weapon is selected**.

## 2. The Steam Deck's inputs (what we have to work with)

2 analog sticks (+ L3/R3 clicks) · D-pad · A/B/X/Y · L1/R1 (bumpers) · L2/R2 (analog triggers) ·
**L4/R4/L5/R5** (4 rear grip buttons) · 2 trackpads (+ click) · ☰ (Start) · ⧉ (Select) · gyro.
That's ~24 inputs for ~30 game actions — so the rarely-used ones live on the **left-trackpad radial
menu** (the thing you liked) and the rear buttons.

## 3. How proven games map it (for reference)

| Control | **NFS: Most Wanted** | **GTA V (vehicle)** | **Twisted Metal / Vigilante 8** |
|---|---|---|---|
| Accelerate | Btn1 / **A** | **RT** | **X / R2** |
| Brake / reverse | Btn3 / **X** | **LT** | **L2 / Square** |
| Steer | left stick (analog) | left stick (analog) | left stick (analog) |
| Handbrake | Btn2 / **B** | **RB** | **B / Circle** |
| Fire weapon | — | — | **R1 / Square** |
| Special / 2nd weapon | Nitrous = Btn7 | — | **L1 / Triangle** |
| Change weapon | — | — | **D-pad / Triangle** |
| Camera / look | — | **right stick** | right stick |
| Change view | RB | **Y** | Select |
| Look behind | Btn5 / **LB** | — | — |
| Horn | — | **LB** | — |
| Menu / map / radio | D-pad | D-pad | D-pad |

Sources: [NFS:MW controls](https://www.magicgameworld.com/need-for-speed-most-wanted-pc-keyboard-controls-guide-2005-2012/) ·
[GTA V controls (Fandom)](https://gta.fandom.com/wiki/Controls_for_GTA_V). Takeaways that shape our
options: **analog steering on the left stick**, **triggers for the two "action" inputs**, **right
stick for camera**, **face buttons for the vehicle verbs** (handbrake/view), **D-pad + a menu for
the rest**.

## 4. Two layouts to choose from

Both use **analog left stick** (real joystick, not on/off keys), **right stick = glance/look**,
**right trackpad = mouse**, **A = select menu item + skip cutscene** (fixes the "hold-Steam-to-
click" problem), **left-trackpad radial = systems menu** (map/notepad/radar), and the **rear
buttons L4/R4/L5/R5** for targeting. They differ in **where driving vs. shooting lives** — the core
of your question.

### Option 1 — "Sim-Combat" (your stated preferences)
*Triggers are weapons; you drive entirely with the left stick. Best if shooting is as important as
driving (true to I76).*

| Input | Action | | Input | Action |
|---|---|---|---|---|
| **L-stick** | **steer + throttle** (analog) | | **A** | select / skip cutscene *(fire HP1 in-sim)* |
| **R2** | fire selected weapon | | **B** | back / pause (Esc) |
| **L2** | fire-all / linked (`F`) | | **X** | reverse |
| **R1** | change selected weapon | | **Y** | change view |
| **L1** | target nearest enemy | | **L3** | handbrake |
| **R-stick** | glance up/down/left/right | | **R3** | untarget |
| **D-pad** | ↑ engine · ↓ lights · ← horn · → binoculars | | **L4/R4** | front target / next target |
| **L-trackpad** | map / notepad / radar-range / radar-cam | | **L5/R5** | zoom out / zoom in |
| **R-trackpad** | mouse (menus) · click = select | | **☰ / ⧉** | pause / map |

### Option 2 — "Racing" (NFS/GTA convention)
*Triggers are gas/brake; weapons move to the bumpers/face. Best if it should feel like a modern
driving game first.*

| Input | Action | | Input | Action |
|---|---|---|---|---|
| **L-stick** | **steer** (analog, left/right only) | | **A** | select / skip cutscene · handbrake in-sim |
| **R2** | accelerate | | **B** | reverse |
| **L2** | brake | | **X** | fire-all / linked |
| **R1** | fire selected weapon | | **Y** | change view |
| **L1** | change selected weapon | | **L3** | horn |
| **R-stick** | glance up/down/left/right | | **R3** | binoculars |
| **D-pad** | ↑ engine · ↓ lights · ← target-nearest · → next-target | | **L4/R4** | front target / untarget |
| **L-trackpad** | map / notepad / radar-range / radar-cam | | **L5/R5** | zoom out / zoom in |
| **R-trackpad** | mouse (menus) · click = select | | **☰ / ⧉** | pause / map |

## 5. Answers to your specific questions

- **Analog vs digital:** the first config was **digital** (stick emulated `WASD`). Both options
  above are **true analog** — the stick outputs a real gamepad joystick the game reads as steering/
  throttle. *One caveat:* I can't test on your hardware, so if analog steering doesn't respond,
  it's the game's winmm-joystick X-axis; the digital fallback config is one tap away.
- **Menu confirm was on ⧉ (Select) — moved to A.** In both options **A = left-click** = select a
  menu item **and** skip cutscenes (no more holding Steam). ⧉ becomes "show map."
- **Sticks confirming menus:** possible but not ideal — a button does the *same* thing in menus and
  in-sim (no per-context switching without fiddly action-sets), and the sticks are busy driving/
  looking. The **right trackpad + A** is the clean menu combo. If you want, I can also map a rear
  button to left-click as a second "confirm."
- **Stick presses (L3/R3):** were **unused** before — now handbrake/untarget (Opt 1) or horn/
  binoculars (Opt 2).
- **Previously-unmapped inputs now used:** L2, both stick-clicks, all four rear buttons (L4/R4/L5/
  R5), and the left-trackpad radial. Nothing important is left unbound; the long-tail actions
  (poetry, direct hardpoint 3–5, transmission shift, scores) remain on the Steam on-screen keyboard
  (☰+X) — tell me if you want any promoted to a button.

**Tell me: Option 1 or Option 2** (or a hybrid — e.g. "Option 1 but gas/brake on triggers"), and
whether analog steering works when you test. I'll lock it in.
