# Flying the '76: a CH Fighterstick on a driving game

**Built 2026-08-08.** [`i76-fighterstick.ahk`](../i76-fighterstick.ahk) puts a
CH Products Fighterstick USB on Interstate '76 — the grip's buttons follow F-16
HOTAS convention, and the stick's own deflection becomes the **gearbox and the
handbrake**.

```bash
AutoHotkey.exe i76-fighterstick.ahk             # run alongside the game
AutoHotkey.exe i76-fighterstick.ahk -map        # print the full reference card
AutoHotkey.exe i76-fighterstick.ahk -whatif     # BENCH TEST: names each action, sends no keys
AutoHotkey.exe i76-fighterstick.ahk -learn      # press each control, see its number
AutoHotkey.exe i76-fighterstick.ahk -selftest   # test the ADC logic, no hardware
```

**In PowerShell you need the call operator `&`**, because a quoted path at the
start of a line parses as a string literal, not a command — it fails with
`Unexpected token`, which reads exactly like "nothing happened":

```powershell
& "C:\Program Files\AutoHotkey\AutoHotkey.exe" "C:\Users\james\i76-everywhere\i76-fighterstick.ahk" -map
```

The script also keeps its **tray icon** — unlike `i76-remap.ahk`, which sets
`#NoTrayIcon` because it lives inside the Wine prefix for the length of a game
session. This one is launched by hand next to a fullscreen game; without an icon
it runs with no window, no tray entry, and no way to stop it short of Task
Manager, possibly while holding a key down. Right-click the icon to exit, which
releases any held key on the way out.

**Testing without the game.** `-whatif` is the bench: it reads the stick live and
prints the **game action** each control performs — `castle UP -> TARGET_NEAREST_ENEMY`,
`stick BACK -> e_brake ON` — while sending no keystrokes at all. Every control can
be checked in a minute without loading a mission. `-map` prints the same
information as a static card, generated from the script's own tables so the two
cannot drift apart.

## The device

| | |
|---|---|
| USB ID | `068E:00F3` — CH Products, [Fighterstick](https://devicehunt.com/view/type/usb/vendor/068E/device/00F3) |
| winmm slot | `joystick2` (the T300 wheel holds `joystick1`) |
| reports | 3 axes, 19 buttons, one POV hat |
| physically | trigger, three thumb buttons, three 4-way hats, one 8-way castle hat, a 3-position mode switch, and a throttle wheel on the base |

Windows names it only "HID-compliant game controller" and winmm calls it
"Microsoft PC-joystick driver" — neither identifies the model. The vendor ID is
what pins it down.

## Why this is a separate tool and not an input.map binding

**The engine's binding file cannot do it.** `input.map` maps an analog axis only
to an *analog* sink — `steer` and `throttle`. There is no syntax for "when this
axis passes 60%, press a button", so an axis can never drive `shift_up`. That
conversion has to happen outside the engine.

So the tool reads the stick through winmm and **synthesises the keystroke the game
already binds**. It needs no change to `input.map` whatsoever, which means it
cannot break the wheel — and `input.map` in this repo has a history of being eaten
by the in-game controls menu ([AGENTS.md](../AGENTS.md)).

Synthesising keys rather than feeding a virtual joystick also sidesteps an open
question: **whether this 1997 engine polls a second winmm joystick at all.** The
wheel is `joystick1`; the game may never look at `joystick2`. Keystrokes are read
identically no matter which device produced them, so this works either way, and
the wheel keeps `joystick1` to itself for steering, pedals and force feedback.

### Why AutoHotkey and not PowerShell

This started as a `.ps1` and was ported. Two reasons, and the second is the one
that decides it:

- **Uniformity.** Input remapping in this repo is already AHK's job —
  [`i76-remap.ahk`](../i76-remap.ahk) is the established remapper, and there are a
  dozen more AHK scripts including two that already read joystick axes.
- **Portability, which PowerShell simply cannot do.** `i76-remap.ahk` runs *inside
  the Wine/Proton prefix* on Mac and Steam Deck, unchanged from native Windows. A
  PowerShell tool is Windows-only, which is a poor fit for a repo called
  *i76-everywhere*.

The port also inherits [the AHK doctrine](../AGENTS.md) this repo paid for rather
than rediscovering it: keep `SendMode` at its default (**Event**, never `Input` —
AHK uninstalls its own hooks during `SendInput` playback, and inside the Wine
prefix only SendEvent-injected events reach the hooks), and **never** open a modal
dialog, because under DxWnd's backdrop a `MsgBox` is invisible while stealing
focus, so the game just goes input-dead.

## The stick as a gearbox — the ADC

This is the part the request was really about: turning an analog position into
discrete actions.

Layout chosen at the wheel (2026-08-08), not from first principles — the handbrake
is the gesture you make hardest and most often, so it takes the strongest, most
natural pull; reverse reads as a held state rather than a latch; and the shifts sit
out of the way of both, on the lateral axis.

| stick | action | key | semantics |
|---|---|---|---|
| pull **back** | `e_brake` | `Space` | **level** |
| push **forward** | reverse while held | `X` | **momentary** |
| **left** | `shift_down` | `Comma` | **edge** |
| **right** | `shift_up` | `Period` | **edge** |

**The three semantics are the whole design**, and getting any of them wrong makes
the stick unusable:

- **Edge** — one event per excursion. The stick must return through the release
  threshold before it fires again. Exactly how a sequential gearbox behaves: you
  cannot hold it over and climb through the gears.
- **Level** — the key is held down for as long as the stick is deflected, released
  when it recentres. A handbrake you had to tap would be useless.
- **Momentary** — pulses on the way **in and again on the way out**. This exists
  because `reverse_direction` is a **toggle**: one tap enters reverse, the next
  returns to forward. Holding the key does *not* hold reverse, so `level` would
  leave the car stuck in reverse with the stick centred. Two taps against a toggle
  produce the momentary behaviour the toggle itself cannot.

Two thresholds, not one: it triggers at **35%** deflection and releases at **20%**.
The gap is hysteresis. With a single threshold, a stick resting near it
machine-guns the action.

`-selftest` exercises this without the hardware — 25 assertions covering all three
semantics, the hysteresis band, and axis normalisation including out-of-range
clamping. The two cases worth naming: *"held over does NOT shift again"*, and
*"releasing taps back OUT of reverse"* — without that second pulse the car stays
in reverse with the stick sitting centred in your hand.

The state machine is a **pure function of (deflection, state)** for exactly this
reason; it is the part that is easy to get subtly wrong and impossible to debug
halfway through a mission.

## The buttons, as a fighter pilot would expect

Grounded in the real [F-16 stick grip](https://en.wikipedia.org/wiki/HOTAS), where
the trigger fires the gun, the "pickle" button releases weapons, the castle hat is
head-look, and the 4-way switches are Target Management (TMS) and Display
Management (DMS).

### Anatomy — use these names, always

Ambiguous naming already cost one round here (see below), so the four hats get
their proper names and nothing else:

| name | where it is | reports as |
|---|---|---|
| **cone hat** | 8-way, upper **right** of the top face | POV channel |
| **convex serrated hat** | leftmost on the top face | buttons **5–8** |
| **castle hat** | lower **right** of the top face | buttons **9–12** |
| **trim hat** | concave, halfway up the stick **shaft** | buttons **13–16** |

Plus four singles: **trigger** (1), **top red / pickle** (2), **back-side red** (3,
the mode switch), **pinky red** (4).

**Every hat's direction order is up → right → down → left.** Measured, since CH's
documentation gives four numbers per hat without saying which is which.

### The map

Roles follow the A-10C convention by button number — DMS on 5–8, TMS on 9–12,
CMS on 13–16.

| # | control | jet function (A-10C) | I'76 action | key |
|---|---|---|---|---|
| 1 | trigger | gun trigger (2-stage: PAC, then fire) | `weapon_fire` | `Enter` |
| 2 | top red — **pickle** | weapon release | `special1` | `6` |
| 3 | back-side red | — | **mode switch, deliberately unbound** | — |
| 4 | pinky red | pinky switch — laser latch / NWS | `weapon_link` | `F` |
| — | **cone hat** | view control / head-look | `pilot_glance_up/right/down/left` | grey arrows |
| 5–8 | **convex serrated — DMS** | display management: MFCD nav, sensor select | `SHOW_MAP` / `RADAR_RANGE_TOGGLE` / `SHOW_NOTEPAD` / `RADAR_CAMERA_TOGGLE` | `M` `R` `N` `K` |
| 9–12 | **castle — TMS** | target management: lock, track, designate | `TARGET_NEAREST_ENEMY` / `NEXT_TARGET` / `RESET_TARGET` / `frontal_target` | `T` `Y` `U` `Q` |
| 13–16 | **trim — CMS** | countermeasures: chaff, flares, programs | `special2` / `special3` / `weapon_cycle` / `toggle_cmbt_view` | `7` `8` `Tab` `V` |

`-map` prints this from the script itself, so the card and the code cannot drift
apart.

**Button 3 is left unbound on purpose.** It cycles the base LED through three
positions — it is the mode switch, and on CH sticks the mode renumbers the
buttons. Binding a game action to it would fire that action on every mode change.

The cone hat transfers most directly of anything here: on the real aircraft it is
head-look, and in I'76 `pilot_glance_*` is head-look. It is a **true 8-way POV
channel** on this unit, not buttons — CH's docs hedge on that ("maps to the
remaining upper button IDs up to 24 depending on configuration"), so it was worth
measuring. All eight positions report cleanly. The code folds it into 4 sectors so
diagonals fall through to the nearer cardinal rather than doing nothing.

### A retraction: the documentation was right, my names were not

This document briefly claimed CH's sheet had the lower and right hats swapped,
on the strength of a `-learn` capture. **That was wrong, and the mistake is worth
keeping.**

The button numbers were never in doubt. What was ambiguous was the checklist I
wrote to collect them: I asked for the *"lower/down"* hat and the *"side/right"*
hat, which on this grip describe the same two controls about equally badly — the
castle hat is low **on the top face**, the trim hat is low **on the shaft**. The
presses came back in the order the physical descriptions implied, not the order
my labels assumed, and I read the mismatch as the manufacturer being wrong rather
than my own instructions being unclear.

The lesson generalises past this stick: **when a measurement contradicts the
documentation, suspect the measurement's instructions first.** A diagram with
official part names settled it in one exchange.

### Still unidentified

Buttons **17, 18 and 19** (winmm reports 19 in total). Button 18 has fired once,
unattributed; 17 and 19 never have. The mode switch is the likely explanation, and
pinning it down matters — if the mode can be *detected*, it can stop silently
renumbering everything.

## What is still on the keyboard

Audited against the live `input.map`, 2026-08-08: **54 game actions carry a key,
24 of them are on the stick.** The rest, in rough order of how much you would miss
them, and all free to move onto a control:

| action | key | worth a control? |
|---|---|---|
| `toggle_lights` | `H` | yes — night missions |
| `TOGGLE_BINOCULARS` | `B` | yes — spotting |
| `HONK_HORN` | `G` | it *is* Interstate '76 |
| `start_engine` | `I` | once per mission; keyboard is fine |
| `pilot_glance_target` | `E` | snap-look at the current target |
| `hardpoint2_fire` … `hardpoint5_fire` | `2`–`5` | only if you want per-hardpoint fire rather than `weapon_cycle` |
| `zoom_factor` minus / plus / reset | `PgUp` `PgDn` `End` | a candidate for the Z wheel |
| `POETRY` | `P` | Taurus does not need a dedicated button, but he has earned one |
| `show_player_scores`, `show_team_scores` | `'` `;` | multiplayer only |
| `overview_*` (map pan and zoom) | arrows, `PgUp`/`PgDn` | only live in the map view |
| `track_*` (external camera) | arrows, `PgUp`/`PgDn` | replay and external cam only |

`-map` prints this list too, so it stays accurate as bindings move.

## Adding another controller

The pattern here is meant to be copied, not reinvented for the next device:

1. **Identify the device by USB VID/PID**, not by the name Windows shows — this
   one reports only "HID-compliant game controller" and "Microsoft PC-joystick
   driver", neither of which identifies the model.
2. **Get a diagram with the manufacturer's own part names** and use those names
   everywhere, in code comments and docs alike. Inventing your own physical
   descriptions is what caused the retraction above.
3. **Measure the button numbers with a learn mode**, in a fixed press order,
   numbered so presses can be matched to output. Never trust the sheet alone —
   and when they disagree, re-read your own instructions first.
4. **Keep one table** carrying, per control: the physical name, the game action,
   and the key. Generate the reference card *from that table* so documentation
   cannot drift from behaviour.
5. **Keep the analog-to-discrete state machine pure** and test it without the
   hardware.

## What is and is not verified

Stated plainly, because this repo's history is full of retractions for skipping
field tests.

**Measured on the hardware** (2026-08-08): every button number 1–16, the up →
right → down → left order within each hat, the lower/right hat swap above, and the
castle hat being a true 8-way POV channel.

**Not yet established:**

1. **Buttons 17, 18 and 19.** Button 18 has fired once, unattributed; 17 and 19
   never have. The 3-position mode switch is the likely answer, and it matters
   because on CH sticks the mode silently renumbers everything.
2. **Whether the 1997 engine accepts synthesised keys in a mission.** The injection
   path itself *is* verified — scancode `0x14` resolves to `VK_T` and the extended
   `0xE0,0x48` to `VK_UP`, confirmed by round-tripping through
   `GetAsyncKeyState` — so the keys genuinely reach Windows. Whether the engine's
   own input read sees them needs one mission to confirm.
3. **Whether the layout feels right at speed.** It was reasoned about at the wheel,
   not driven. Thresholds are `THRESH`/`RELEASE` at the top of the script.

### Why scan codes

Scan codes rather than virtual keys — but **not** for the reason first written
here. The original claim was "a DirectInput-era title reads scan codes", and this
game is not a DirectInput title: it is **winmm-joystick only**
(`joyGetNumDevs`/`joyGetPosEx`, no DirectInput, confirmed in the exe —
[GAMEPAD-PC-MAC.md](GAMEPAD-PC-MAC.md)). That is about its *joystick* path; its
*keyboard* path is not documented anywhere in this repo.

The choice stands on a better footing: a scan code satisfies **either** kind of
reader, because Windows resolves it to a virtual key on the way through. Verified
by round-trip — scancode `0x14` reports as `VK_T`, and extended `0xE0,0x48` as
`VK_UP`, both confirmed through `GetAsyncKeyState`. Sending a VK *only* would be
the bet, and it is the bet that silently does nothing against a scan-code reader.

## If a key sticks

The script releases every held key from an `OnExit` handler, so Ctrl+C is safe. A
held `Space` would otherwise be a handbrake the player cannot release, and it
would survive the script exiting.

Worth noting because it was briefly wrong here: the handler was *defined* but
never registered with `OnExit`, which makes it dead code that looks like a safety
net. It also fires on **every** exit path including `-selftest`, which returns
before the held-key table is ever created — so it guards against iterating an
unset variable, because an exit handler that throws is a poor way to find that out.

## Sources

- [CH Products Fighterstick](https://www.chproducts.com/Fighterstick-v13-p-181.html) — three push buttons, three 4-way hats, one 8-way POV, mode switch
- [Device Hunt — 068E:00F3](https://devicehunt.com/view/type/usb/vendor/068E/device/00F3) — vendor/product identification
- [HOTAS](https://en.wikipedia.org/wiki/HOTAS) and [Falconpedia: HOTAS](http://falcon4.wikidot.com/avionics:hotas) — F-16 grip control functions
