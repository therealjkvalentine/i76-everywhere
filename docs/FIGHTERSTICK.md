# Flying the '76: a CH Fighterstick on a driving game

**Built 2026-08-08.** [`i76-fighterstick.ahk`](../i76-fighterstick.ahk) puts a
CH Products Fighterstick USB on Interstate '76 — the grip's buttons follow F-16
HOTAS convention, and the stick's own deflection becomes the **gearbox and the
handbrake**.

```bash
AutoHotkey.exe i76-fighterstick.ahk             # run alongside the game
AutoHotkey.exe i76-fighterstick.ahk -learn      # press each control, see its number
AutoHotkey.exe i76-fighterstick.ahk -whatif     # show actions, send no keys
AutoHotkey.exe i76-fighterstick.ahk -selftest   # test the ADC logic, no hardware
```

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

| stick | action | key | semantics |
|---|---|---|---|
| push **forward** | `shift_up` | `Period` | **edge** |
| pull **back** | `shift_down` | `Comma` | **edge** |
| yank **left** | `e_brake` | `Space` | **level** |
| push **right** | `reverse_direction` | `X` | **edge** |

**Edge versus level is the whole design**, and getting it wrong makes the stick
unusable:

- **Edge** — one event per excursion. The stick must return through the release
  threshold before it will fire again. That is exactly how a sequential gearbox
  behaves: you cannot hold it forward and climb through the gears.
- **Level** — the key is held down for as long as the stick is deflected, released
  when it recentres. A handbrake you had to tap would be useless.

Two thresholds, not one: it triggers at **55%** deflection and releases at **35%**.
The gap is hysteresis. With a single threshold, a stick resting near it
machine-guns the action.

`-selftest` exercises this without the hardware — 18 assertions covering the gate
behaviour, the hysteresis band, and axis normalisation including out-of-range
clamping. The case worth naming: *"held forward does NOT shift again."*

The state machine is a **pure function of (deflection, state)** for exactly this
reason; it is the part that is easy to get subtly wrong and impossible to debug
halfway through a mission.

## The buttons, as a fighter pilot would expect

Grounded in the real [F-16 stick grip](https://en.wikipedia.org/wiki/HOTAS), where
the trigger fires the gun, the "pickle" button releases weapons, the castle hat is
head-look, and the 4-way switches are Target Management (TMS) and Display
Management (DMS).

| grip control | F-16 function | I'76 action | key |
|---|---|---|---|
| trigger | gun | `weapon_fire` | `Enter` |
| pickle (thumb) | weapon release | `special1` | `6` |
| thumb | — | `weapon_cycle` | `Tab` |
| pinky / paddle | NWS, AR disconnect | `HONK_HORN` | `G` |
| **castle hat** (8-way) | view / head-look | `pilot_glance_up/down/left/right` | grey arrows |
| **hat 1 — TMS** | target management | nearest / next / reset / frontal | `T` `Y` `U` `Q` |
| **hat 2 — DMS** | display management | map / radar range / combat view / binoculars | `M` `R` `V` `B` |
| **hat 3 — CMS** | countermeasures | `special2` / `special3` / glance-target / start engine | `7` `8` `E` `I` |

The castle hat mapping is the one that transfers most directly — on the real
aircraft it is head-look, and in I'76 `pilot_glance_*` is head-look.

The 8-way hat is folded into 4 sectors so the diagonals fall through to the nearer
cardinal rather than doing nothing.

## Two things NOT verified

Stated plainly, because this repo's history is full of retractions for skipping
field tests.

1. **The button numbers are CH's documented default layout, not measured on this
   unit** — and the 3-position mode switch renumbers everything. If a control does
   the wrong thing, run `-learn`, press it, and correct the `BTN` table near the
   top of the script — it is a plain list of `BTN[n] := "Key"` lines.
2. **Whether the 1997 engine accepts synthesised keys in a mission.** The injection
   path itself *is* verified — scancode `0x14` resolves to `VK_T` and the extended
   `0xE0,0x48` to `VK_UP`, confirmed by round-tripping through
   `GetAsyncKeyState` — so the keys are genuinely delivered to Windows. Whether the
   engine's own input read sees them needs one mission to confirm.

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
