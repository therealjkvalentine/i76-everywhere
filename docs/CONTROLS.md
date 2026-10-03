# Controls: sit down and play

One page for the four ways to drive Interstate '76 with this repo: **all keyboard**, **keyboard and mouse**,
**gamepad**, and **HOWAS** (hands on wheel and stick). Written 2026-10-03. Every binding below is copied from a
file in this repo or from GOG's own `input.map`; the source is named under each table. Statuses are quoted from
the docs and not upgraded. Deep docs are linked, not repeated.

Two facts first. The engine reads **`input.map`** in the game folder and nothing else ([AGENTS.md](../AGENTS.md)).
And a Windows install made by `INSTALL.bat` has, as of 2026-10-03, **never been started** by anyone on this project
([INSTALL.md, Evidence](../INSTALL.md#evidence-what-was-tested)): the fresh-install rows below are read from the
files, not played.

## 0. Thirty seconds

| Setup | What you need | How to turn it on | Status (quoted) |
|---|---|---|---|
| All keyboard | A keyboard, ideally with a numeric keypad | Nothing. GOG's stock keys; section 2 | Stock game. Our patched fresh install: "the game was not started from it" (INSTALL.md) |
| Keyboard and mouse | Plus a three-button mouse | `INSTALL.bat` (`setup-windows.ps1`) adds mouse **buttons**. Mouse **steering** is not written; section 3 | Mouse steering "SOLVED 2026-07-13" on the Mac under DxWnd (VERIFIED-FIXES); untested on a Windows fresh install |
| Gamepad | An Xbox-style pad, **connected before launch** | `INSTALL.bat`, then `PLAY-i76.bat` (starts the AutoHotkey layer); section 4 | Native: "field-tested 2026-07-14: `joystick1` token confirmed" [d3]. AutoHotkey layer: "deployed, verified on Mac/Windows" (ENHANCEMENTS) |
| HOWAS | Thrustmaster T300RS + CH Fighterstick, Windows | Driver, pedals COMBINED, `PLAY-i76.ps1`; section 5 | Wheel: "STATUS 2026-08-01: WORKING AND PLAYED". Stick: "Field-confirmed working 2026-08-08". Both on the owner's own `input.map`, which is not in this repo |
| Steam Deck | The Deck | The installer pre-applies the layout | "INSTALLED on this user's Deck (2026-07-11)"; see [DECK-CONTROLS.md](DECK-CONTROLS.md) |

## 1. Keys every setup shares

The stock map of GOG 2.1.0.17, all 55 action blocks, plus what `setup-windows.ps1` appends on a fresh install.
Every letter, number and punctuation binding is ignored while Shift or Ctrl is held (the `- Keyboard Shift` /
`- Keyboard Control` lines); the glance, zoom and score keys are not.

| Action | Key | Origin |
|---|---|---|
| Accelerate / brake | `UpArrow` / `DownArrow` (see the arrow note in section 2) | stock |
| Steer | `LeftArrow` / `RightArrow` | stock |
| Analog steer / throttle | `joystick1` Left/Right, Down/Up | added by this repo (GOG's map has no analog block) |
| Gear down / up | `,` / `.` | stock |
| Handbrake | `Z`; pad `Button4` | stock; button added by this repo |
| Reverse (a toggle) | `Tab` | stock |
| Start engine | `S` | stock |
| Fire selected weapon | `Space`; mouse left; pad `Button1` | stock; mouse and pad added by this repo |
| Cycle weapon | `Enter`; pad `Button3` | stock; button added by this repo |
| Link weapons | `L` | stock |
| Hardpoints 1 to 5 | `1` `2` `3` `4` `5` | stock |
| Hardpoints 1 to 4, home row | `K` `O` `[` `]`; mouse right = hardpoint 2 | added by this repo (K since 2026-10-03, [d1]) |
| Specials 1 to 3 (nitrous is whichever slot it sits in) | `6` `7` `8` | stock |
| Target in front / next / nearest enemy / clear | `Q` / `E` / `T` / `Y` | stock |
| Radar range / radar camera | `R` / `W` | stock |
| Map / notepad / binoculars | `M` / `N` / `B` | stock |
| Lights / horn / poetry | `H` / `G` / `C` | stock |
| Combat view toggle | `V` | stock |
| Glance up, down, left, right | `GreyUpArrow` etc.; pad hat; mouse middle = glance left | stock; hat and mouse added by this repo |
| Glance at target | `Insert` | stock |
| Zoom minus / plus / reset (also map zoom and chase-camera distance) | `GreyPageUp` / `GreyPageDown` / `GreyEnd` | stock |
| Player / team scores (multiplayer) | `'` / `;` | stock |
| Camera views | `F1` cockpit, `F3` chase; `F2` `F7` `F8` `F9` `F10` others | not in `input.map`; from the comments in `i76-remap.ahk` |
| Pause menu, skip a cutscene | `Esc` | same source |

Sources: `input.map.pre-windows-setup` from an unpacked GOG 2.1.0.17 installer (stock);
[`setup-windows.ps1`](../setup-windows.ps1) section 5 (added); [`i76-remap.ahk`](../i76-remap.ahk) `@pad` lines.

**What the patch does, exactly.** It backs the map up as `input.map.pre-windows-setup`, appends
`throttle { - joystick1 Down/Up }` and `steer { - joystick1 Left/Right }`, the three mouse buttons, pad buttons
1 / 3 / 4, the hat, and `K O [ ]`. It moves the handbrake to `Space` and fire to `Enter` **only** when GOG's map
has the handbrake on `C` (an older GOG build); the 2.1.0.17 map keeps `Z` and `Space`. It runs once: a map that
already carries its marker line is skipped, so an install patched before 2026-10-03 still has hardpoint 1 on `L`
and a `- mouse` line beside `joystick1` (fault 1 in section 7).

## 2. All keyboard

Nothing to install: section 1's "stock" rows are the whole layout. Start the engine with `S`, drive, `Space`
fires, `Enter` picks the weapon, `T` targets the nearest enemy, `Z` is the handbrake, `Tab` toggles reverse.

**The arrow note.** The engine has two sets of arrow names. Driving is on the plain `UpArrow` set; glancing is on
the `Grey*Arrow` set. On Windows the dedicated arrow cluster is the Grey set: the Fighterstick layer and head
tracking both send those keys to glance, "confirmed in the game 2026-08-08" ([FIGHTERSTICK.md](FIGHTERSTICK.md)).
So on the stock map the **dedicated arrows look around and the plain set, the numeric keypad's arrows, drives**
([MAC-BUILD.md](MAC-BUILD.md) "Controls: Mac arrow keys" says the same from the Mac side) [d2]. Nobody here has
checked this on a fresh Windows install, nor whether NumLock matters. If your arrows glance instead of drive,
that is why; on a keyboard with no keypad, swap the four plain and four Grey arrow tokens in `input.map` (back
up, then lint; rules in section 7), which is what `fix-arrows-for-mac.sh` does for Mac users.

What our install changes for a keyboard player: the home-row hardpoints `K O [ ]`, and nothing else on the
2.1.0.17 map.

## 3. Keyboard and mouse

State on fresh installs as of 2026-10-03, from `setup-windows.ps1`:

- **Mouse buttons are written**: left = fire selected weapon (also the handgun on foot), right = hardpoint 2,
  middle = glance left [d4].
- **Mouse steering is not written.** Until 2026-10-03 the script wrote `- joystick1` and `- mouse` into the same
  `steer` / `throttle` block. That is the analog chord trap: with two analog sources in one block the axis pins
  dead-centre ("SOLVED 2026-07-13", [VERIFIED-FIXES.md](VERIFIED-FIXES.md)). The blocks are now `joystick1` only.
- **Mouse wheel**: `PLAY-i76.ps1` starts `i76wheel.exe` with wheel up = `Tab`, wheel down = `5` [d5]. On the
  2.1.0.17 map `Tab` is reverse, not weapon cycle (section 4, gap table). `-WheelUp` / `-WheelDown` change the keys.
- **Mouse buttons 4 and 5** (through `i76-remap.ahk`): `6` (special 1) and `3` (hardpoint 3) [d6].

**If you want mouse steering**, the recipe the docs support is a hand edit, one analog source per block:

```
steer    { - mouse  Left/Right }
throttle { - mouse  Down/Up    }      # optional; leave joystick1 here to keep pedals or a stick
```

The trade-offs, all from the code: (1) a block has one source, so a pad or wheel no longer steers; (2)
`PLAY-i76.ps1` treats a `steer` or `throttle` block without a joystick line as damage from the in-game menu and
restores the newest `input.map.*` backup that has both joystick sinks, if there is one; (3) with both blocks on
the mouse and pad buttons still bound, the lint reports "NO analog sink uses a joystick". Status: works alone
under DxWnd on the Mac (2026-07-13); not tested on Windows. It is not offered by the installer.

## 4. Gamepad

Connect the pad **before** launching: the engine lists joysticks once, at startup. Two layers:

1. **Native** (`input.map`, written by the installer): left stick steers and is the throttle, A fires, X cycles
   the weapon, Y is the handbrake, D-pad glances. No Steam Input, no emulation. Menus still need the mouse or
   keyboard. Status: A = Button1 "confirmed"; B, Y and the hat "assumed" ([GAMEPAD-PC-MAC.md](GAMEPAD-PC-MAC.md)) [d3].
2. **The AutoHotkey layer** ([`i76-remap.ahk`](../i76-remap.ahk)): triggers as two separate buttons, right-stick
   glance, an LB shift layer with all five hardpoints, look-back fire, camera cycle. `PLAY-i76.bat` /
   `PLAY-i76.ps1` starts it from `<game>\_ahk\` and stops it with the game. It works by typing keys.

![Controller layout, base layer](pad-layout.svg)

![Controller layout, LB held](pad-layout-shift.svg)

The pictures are generated from the layer's own `@pad` lines by `tools/pad-diagram.py`. Design rules:
[CONTROL-DOCTRINE.md](CONTROL-DOCTRINE.md). The layer itself: [INPUT-REMAPPER.md](INPUT-REMAPPER.md).
Steam Deck: [DECK-CONTROLS.md](DECK-CONTROLS.md).

**Known gap on a fresh GOG 2.1.0.17 install.** The AutoHotkey layers (pad, wheel and stick) type the keys of the
owner's map. Comparing the keys they send with the map the installer leaves (a comparison of files, not a play
test) gives these mismatches:

| Key sent | Meant as (who sends it) | On the fresh 2.1.0.17 map |
|---|---|---|
| `Enter` | fire (pad A tap, wheel right paddle, stick trigger) | cycle weapon |
| `Space` | handbrake (wheel 4, stick pulled back) | fire |
| `Tab` | cycle weapon (wheel 3, mouse wheel up) | reverse |
| `X` | reverse (pad L3 with stick back, wheel shift+4, stick forward) | unbound (reverse is `Tab`) |
| `C` | cycle weapon (pad B) | poetry |
| `Y` | next target (pad X, stick castle right) | clear target |
| `E` | look at target (pad R3, stick pinky, wheel shift+9) | next target |
| `I` | ignition (pad D-pad down, wheel 12 and hat down) | unbound (engine is `S`) |
| `U` / `K` / `P` | untarget / radar camera / poetry (wheel shift layer) | unbound / hardpoint 1 / unbound |
| `-` / `=` | gear down / up (pad LB + D-pad) | unbound (gears are `,` `.`) |

Also: the diagram's RB handbrake has no native binding in the installer's patch (the handbrake it writes is
Button4, Y), and native A / X / Y (by the doc's assumed button numbering) act at the same time as the layer's A / X / Y. Until this is reconciled, a
fresh install has the native layer plus the parts of the AutoHotkey layer whose keys match (triggers, hardpoints,
nitrous, glance, lights, map, notepad, horn, binoculars, front target, radar range, camera keys). To close a gap
yourself, add a separate block binding the key to the intended action in `input.map`, back up, lint.

## 5. HOWAS: hands on wheel and stick

HOWAS is this project's own word, after the flight-sim HOTAS: the left hand on a force-feedback wheel, the right
on a flight stick, feet on the pedals. The setup is a **Thrustmaster T300RS** (winmm `joystick1`) and a
**CH Fighterstick** (`joystick2`). The wheel steers and holds the things you reach for without looking; the stick
is the gearbox, the handbrake and the weapons.

**Wheel** ([WHEEL-T300.md](WHEEL-T300.md), "The layout"; "Rebalanced 2026-08-08"). `input.map` carries only
`steer { - joystick1 Left/Right }` and `throttle { - joystick1 Down/Up }`; every button is typed by `i76-remap.ahk`.

| # | Physical | Base | Hold 6 = shift |
|---|---|---|---|
| 1 | L1 left paddle | lights | hardpoint 1 [d7] |
| 2 | R1 right paddle | fire selected weapon (incl. cockpit handgun) | front target |
| 3 / 4 / 5 | cluster | cycle weapon / handbrake / nitrous | combat view / reverse / special 2 |
| 6 | cluster | SHIFT | |
| 7 | SE | rear gun (hp3) | dropper (hp4) |
| 8 | OPTIONS | target nearest | untarget |
| 9 | R2 | horn | look at target |
| 10 | L2 | horn | radar range |
| 11 | L3 | lights | radar camera |
| 12 | R3 | ignition | binoculars |
| 13 | PS | horn | poetry |
| Hat | D-pad | lights / map / ignition / notepad | gear up / down |

**Stick as a gearbox** ([FIGHTERSTICK.md](FIGHTERSTICK.md), "The stick as a gearbox"):

| Stick | Action | Key | Behaviour |
|---|---|---|---|
| pull back | handbrake | `Space` | held while deflected |
| push forward | reverse while held | `X` | taps in and taps out (reverse is a toggle) |
| left | gear down | `,` | one shift per movement |
| right | gear up | `.` | one shift per movement |

**Stick buttons** (same doc, "The map"; "Field-confirmed working 2026-08-08"):

| # | Control | Action | Key |
|---|---|---|---|
| 1 | trigger | fire selected weapon | `Enter` |
| 2 | top red (pickle) | hardpoint 2 | `2` |
| 3 | back-side red (also the mode switch) | special 1 (nitrous) | `6` |
| 4 | pinky red | glance at target | `E` |
| 5 to 8 | convex serrated hat: direct fire | hardpoint 2 / 3 / 4 / 5 | `2` `3` `4` `5` |
| 9 to 12 | castle hat: targeting | front / next / nearest / radar range | `Q` `Y` `T` `R` |
| 13 to 16 | trim hat | nitrous / notepad / combat view / map | `6` `N` `V` `M` |
| POV | cone hat: glance, held (vertical inverted) | glance down / right / up / left | arrow cluster |

Hat directions read up, right, down, left. Weapon link is on the wheel's shift layer and keyboard `F` on the
owner's map [d8].

**Before you launch** (the rules those docs give):

1. **Close the Thrustmaster control panel.** It holds the DirectInput device; the game's force feedback then
   fails to start and "the first shot crashes the game" (`I7_SFRCE.DLL`, fault offset 0x2505).
2. **No other joysticks, least of all virtual ones** (vJoy, the 3Dconnexion KMJ emulator). They break force
   feedback while steering still works; remove them and reboot.
3. One-time: install Thrustmaster's driver, set the pedals to **COMBINED**, rotation 300 degrees.
4. On a wheel machine, strip the native pad blocks the installer appends, so that `joystick1` appears only on
   `steer` and `throttle`; otherwise half the wheel double-fires (section 7, fault 4).
5. The key table in section 4 applies: this layout was played on the owner's map.

**Force feedback.** The game's own 1997 effects need no switch on the Gold exe: with the two rules above they
engage at startup [d9]. The custom force model (self-aligning weight, slip, road texture) is opt-in:
`PLAY-i76.ps1 -Ffb`, after `tools\ffb\ffb-calibrate.ps1`; status "Feel tuning: not started"
([tools/ffb/README.md](../tools/ffb/README.md)). Leave `-Ffb` off and it is off. Read
[FFB-STACKS.md](FFB-STACKS.md) before running any of it. 2026-10-03 daily driver: "Not verified: force feedback
(module loads; no wheel was attached during the gate)".

**How the launcher starts the layers.** [`PLAY-i76.ps1`](../PLAY-i76.ps1) starts, from `<game>\_ahk\`,
`i76-remap.ahk` (pad, wheel buttons, mouse 4/5), `i76-ch-fighterstick.ahk` unless `-NoStick` (it exits by itself
when no stick is found), the cursor overlay unless `-NoCursorOverlay`, opentrack and the head-look script unless
`-OpenTrack ""`, and the custom force feedback only with `-Ffb`. The game starts **last**, because the engine
lists joysticks and acquires force feedback once, at startup. On exit it stops the layers and sends key-ups for
every key they can hold. The installer puts only the first two scripts in `_ahk\`.

## 6. Head look

Start opentrack with Output = **freetrack 2.0 Enhanced** and press Start, then run `i76-opentrack-headlook.ahk`
(`PLAY-i76.ps1 -OpenTrack <path>` does both when the script is in `_ahk\`; the installer does not put it there).
Turning your head holds the glance keys; **Ctrl+Alt+H** switches to analog yaw, in which the glance keys and hats do nothing.
Status: "Working and field-confirmed" on the GOG Gold build; untested at 120 fps. Details: [HEAD-TRACKING.md](HEAD-TRACKING.md).

## 7. Something is wrong

Lint first. It checks every token against the exe and knows the traps below:

```
python tools\lint-input-map.py "<game folder>"
```

| Symptom | Cause | Fix |
|---|---|---|
| Stick, wheel or mouse steering does nothing, or sits dead-centre | The analog chord trap: two analog sources (`joystick1` and `mouse`) in one `steer` / `throttle` block | Keep one line per block ([VERIFIED-FIXES.md](VERIFIED-FIXES.md), WHEEL-T300 section 3) |
| A controller that worked is dead; `steer` / `throttle` blocks gone, file smaller | The in-game **Control Configuration** menu rewrote `input.map`. Never open it: it appends chords, drops the analog blocks and re-points buttons at other joystick slots | Restore a known-good `input.map` (an `input.map.pre-*` backup, or the portable zip's), lint, restart ([AGENTS.md](../AGENTS.md)) |
| Wheel or pad not detected | Plugged in after launch; or the wheel is on the generic driver or pedals on SEPARATE | Connect first, then launch. "Perfect in the vendor panel, dead in game" means the game's own config: lint before touching drivers ([WHEEL-T300.md](WHEEL-T300.md)) |
| Wheel buttons do two things at once | Native `joystick1` button and hat blocks beside the AutoHotkey wheel layer | Delete them so `joystick1` is only on `steer` and `throttle` (WHEEL-T300, "Buttons: strip the NATIVE joystick1 bindings") [d10] |
| A key is stuck: car crawls, view jammed sideways, hang at PLEASE STAND BY | An AutoHotkey layer was killed while holding a key | Start and stop through `PLAY-i76.ps1` (it sends the key-ups); quit the Fighterstick script from its tray icon ([FIGHTERSTICK.md](FIGHTERSTICK.md), "If a key sticks") |

A binding you added does nothing: two `+` lines in one block are a chord (both at once); alternatives go in
separate blocks ([I76-GAMEPLAY-REFERENCE.md](I76-GAMEPLAY-REFERENCE.md)). The device name is `joystick1`; bare
`Joystick` parses and binds nothing. Edits need a backup first (`input.map.pre-<change>`) and a restart.

## Where the docs disagree

Printed above is the newer statement in each case.

- **[d1]** Hardpoint 1 home-row key: `L` in [`input.map.reference`](input.map.reference) (2026-09-06), `K` in `setup-windows.ps1` (2026-10-03, because stock 2.1.0.17 has weapon link on `L`).
- **[d2]** VERIFIED-FIXES and MAC-BUILD call the `Grey*` arrows the "numpad" codes; FIGHTERSTICK.md and its script (measured 2026-08-08) say they are the dedicated cluster. Both agree the dedicated arrows glance. The same two docs fix the Mac arrows in `KEYBOARD.MAP`, which AGENTS.md (2026-07-18) says the engine never reads.
- **[d3]** ENHANCEMENTS says pad buttons "A=1 / X=3 confirmed"; GAMEPAD-PC-MAC's table retracts the X=3 confirmation (2026-07-18: it was made on the dead bare `Joystick` token). CONTROL-DOCTRINE still lists the throttle axis as `Up/Down`; the real token is `Down/Up`.
- **[d4]** Mouse buttons: ENHANCEMENTS and VERIFIED-FIXES say right = all guns, middle = dropper (the Mac script and `input.map.reference`); MAC-BUILD says buttons 1 / 2 / 3 = weapons 1 / 2 / 3; `setup-windows.ps1` writes right = hardpoint 2, middle = glance left.
- **[d5]** Mouse wheel: `PLAY-i76.ps1`'s header and `setup-windows.ps1`'s message say up = front target (`Q`), down = target nearest (`T`); the script's parameters, which are what runs, and ENHANCEMENTS say up = `Tab`, down = `5`.
- **[d6]** Mouse button 5: INPUT-REMAPPER.md says `7` (special 2); `i76-remap.ahk` (2026-07-18) sends `3`.
- **[d7]** Wheel shift+1: WHEEL-T300 says hardpoint 1; the script sends a left mouse click, which the maps bind to fire selected weapon. The prose under the same table still describes R2 as link fire (before the 2026-08-08 rebalance).
- **[d8]** Stick pinky: FIGHTERSTICK.md's map and the script's table say glance at target (`E`); the script's header comment still says weapon link (`F`). Gears: the pad layer sends `-` / `=`, the wheel and stick send `,` / `.`.
- **[d9]** `enable-force-feedback.bat`: ENHANCEMENTS and VERIFIED-FIXES say to run it; WHEEL-T300 (its later sections, from disassembly) says force-feedback init is unconditional on the Gold exe and the registry key is "irrelevant".
- **[d10]** WHEEL-T300 says re-running `setup-windows.ps1` "appends the gamepad baseline unconditionally"; the script skips a map that still carries its marker comment.
