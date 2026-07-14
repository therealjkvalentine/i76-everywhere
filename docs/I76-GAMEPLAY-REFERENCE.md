# Interstate '76 — gameplay reference (controls, weapons, specials)

*A facts reference for the mechanics that trip people up on the port — synthesized from the manual,
the community, and the game's own action table (dumped from `i76.exe`). Not a copy of the
copyrighted manual. Sources: [manual (ManualMachine)](https://manualmachine.com/gamespc/interstate76/1119171-user-manual/),
[Local Ditch FAQ](https://www.localditch.com/interstate-76/faq.html),
[GOG: the mission-5 jump](https://www.gog.com/forum/interstate_series/argh_help).*

## Weapons: how firing actually works

I76 has **two kinds of fire**, which is why "MB1 fires the cannon but not the side pistol":

- **`weapon_fire`** — fires the **currently-selected weapon group**, and it's **directional**: it
  shoots forward-facing weapons when you look forward, and a **side weapon** (e.g. the **.45
  Handgun** stuck out the window) when you glance out that side window. This is the "smart" fire.
- **`hardpoint1_fire` … `hardpoint5_fire`** — fire **one specific mount** regardless of where you
  look. `hardpoint1` is the forward cannon; side/roof weapons are on other hardpoints.
- **`weapon_cycle`** changes the selected group; **`weapon_link`** links weapons to fire together.

So to fire the **side-window handgun**: bind `weapon_fire` to your fire button (we put it on
**mouse LeftBtn**) and **glance out the side window** — or fire the specific hardpoint it's mounted
on. `hardpoint1_fire` alone will only ever fire the forward cannon.

## Specials: nitrous, bumpers, and the rest

"Specials" are chassis add-ons installed in the garage (Skeeter installs salvaged gear into the
**specials** slots). There are **three special slots**, activated by **`special1` / `special2` /
`special3`**. Which item is in which slot depends on your car's loadout — check the garage/equipment
screen.

| Special | What it does | Activate? |
|---|---|---|
| **Nitrous (NOS)** | **+50% acceleration, +20% top speed for ~15 s, 3 charges** | **Yes** — a special key. Great for the Mission 5 jump: punch it on the ramp |
| **Blower** | +25% acceleration (passive engine boost) | Passive |
| **Structo Bumper** | **Doubles front + rear chassis reinforcement** (armor/ram value) | **No — passive.** It just makes you tougher and better at ramming; nothing to press |
| X-Aust Brake, Curb Feelers, Mud Flaps, Heated Seats, Cup Holders | Minor/flavor items (some are jokes) | Passive |

**Key point:** only *active* specials (nitrous especially) need a keypress; armor/engine items like
the Structo Bumper work on their own.

## Our default key bindings (this port's `input.map`)

Driving: **W/S** throttle (notched — tap, don't hold), **A/D** steer, **Space** handbrake, **X**
reverse, **`,`/`.`** shift down/up. Weapons: **mouse LeftBtn** = fire (contextual) + forward cannon;
**RightBtn/MiddleBtn** = hardpoints 2/3; **`2`–`5`** and **`,`/`.`** = hardpoints; **Tab** cycle,
**F** link. Specials: **`6` / `7` / `8`** = special 1 / 2 / 3 (nitrous is whichever slot it's in —
try each). Camera/glance on the arrow cluster; **I** ignition, **B** binoculars, **M** map, **G**
horn. Full list: the `input.map` in the game folder.

**Rebinding:** edit `input.map` directly (the in-game Control Configuration menu is buggy — see
VERIFIED-FIXES), then **relaunch**. Valid key tokens include letters, numbers, `Space Enter Tab
Comma Period Minus Equal` and the `Grey*` arrow/keypad names. `Shift`/`Control` are modifiers, not
primary keys.

> **⚠️ The chord trap (bit us on `special1`):** multiple `+` lines *inside one block* mean **all
> of them at once** (a chord). To give an action **alternative** bindings (key OR button), use
> **separate blocks**:
> ```
> special1 { + keyboard Six }      ← 6 works on its own
> special1 { + joystick1 Button2 } ← OR the pad button
> ```
> vs. the broken chord (`6` did nothing because it wanted 6 AND the button together):
> ```
> special1 { + keyboard Six
>            + joystick1 Button2 } ← chord: BOTH required
> ```
`nitrous_on`/`nitrous_off` are **NOT** bindable input actions (they're internal engine states) —
nitrous is triggered through a **special** slot, not a "nitrous key."

## The Mission 5 canyon jump

The only way out of the canyon is a ramp jump, and **jump distance is inversely tied to framerate**
— above exactly 20 FPS the car falls too fast per frame and lands short (this is *the* infamous I76
obstacle). Two things make it:
1. **Cap to ≤ 20 FPS** — lower = more jump distance, so a touch under 20 clears these most reliably.
   **Mac default: DxWnd Timing → Limit ON + delay `52` ms ≈ 19.2 FPS** — this also clears the
   *later-mission* bridge/ramp gaps, which are tuned tight for the era's exact-20 sim (`50` ms = 20
   FPS is the reference). Windows/Deck: dgVoodoo `FPSLimit` 19–20. The GOG exe self-caps ~20.66, so
   the DxWnd limiter only bites when set below that. See VERIFIED-FIXES.
2. **Full acceleration down the hill + hit nitrous** (`6`/`7`/`8`, whichever slot) on the ramp.

## The 20-FPS rule (why the whole port caps at 20)

I76 ties physics, AI, and scripted events to the render framerate (1997 fixed-timestep). Above
~25–30 FPS: cars flip, the Mission 5 jump becomes impossible, flamethrower/mortar/AI break. **20 is
the cap on every platform** and must not be raised — frame-gen (Lossless Scaling) interpolates
*display* frames on top of a 20 FPS sim, it does not raise the sim rate.
