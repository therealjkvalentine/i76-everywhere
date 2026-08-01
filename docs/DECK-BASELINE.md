# The Deck's BASELINE control tier — parity with the Mac/Windows pad layer

> **STATUS 2026-08-01: DEPLOYABLE, NOT YET RUN ON DECK HARDWARE.** The Deck was offline
> (Tailscale: last seen 68 days) when this landed, so it could not be deployed or played.
>
> **Verified off-device:** the AutoHotkey URL and pinned sha256 still match upstream, and
> both files extract; the `input.map` transform hits `steer`/`throttle` without touching
> `steer_left`/`throttle_up`, is idempotent, and appends the blocks if they're missing;
> `deck-push.sh` argument parsing across six invocation forms; and
> [`i76-deck-launch.sh`](../deck/i76-deck-launch.sh) driven end-to-end against a **simulated
> Proton and game** — Proton discovered from a reaper-style argv, payload staged into a cold
> prefix that only appears after warm-up, AHK started with the right Windows paths, exit code
> propagated, cleanup run, and graceful degradation with no payload / no Proton.
>
> **ASSUMED until the decode sheet comes back:** that Steam Input's Gamepad template
> enumerates as `joystick1`; the face-button numbering on that virtual pad; that
> `XInputSetState` reaches the Deck's haptics at all; and the 15-second warm-up delay
> (tune with `I76_AHK_DELAY`).

## What this is

The Deck has been running the **convenience tier** — Steam Input v4, which captures the
pad and emits keyboard/mouse ([DECK-INPUT-SCIENCE.md](DECK-INPUT-SCIENCE.md)). Meanwhile
the Mac and Windows builds grew a richer layer that the Deck never got:

- the **rumble mixer** — nitrous kick, handbrake thud, gear click, mine thud, ignition
  crank, plus a continuous engine growl that scales with throttle ([i76-remap.ahk:338](../i76-remap.ahk:338))
- the **LB shift layer** — all five hardpoints, camera cycle, gears, binoculars, horn
- **independent triggers** (winmm merges them into one axis; XInput doesn't)
- **look-back rear gun** — RT while the right stick is held back fires hardpoint 3
- right stick → arrow-key glance

This tier brings the Deck to parity by running the *same* `i76-remap.ahk` inside the
Proton prefix — one source of truth across Mac, Windows and Deck.

**What you give up:** the Steam Input v4 trackpad radial menu and the L4/L5/R4/R5 grip
bindings. Both are convenience-tier only; every critical action is covered here
([CONTROL-DOCTRINE.md](CONTROL-DOCTRINE.md)). Rollback is one command.

## Deploy

From a dev machine on the same network (or Tailscale), with the Deck **awake**:

```bash
./deck/deck-push.sh deck@steamdeck
```

SteamOS ships with sshd off and no password for `deck`. Once, in Desktop Mode:

```bash
passwd; sudo systemctl enable --now sshd
```

Or run it on the Deck directly: `./deck/setup-deck-baseline.sh`.

### Then two manual Steam steps

Neither can be scripted safely while Steam is running — `shortcuts.vdf` is read at
startup and rewritten at exit, so an outside edit gets clobbered.

**1. Launch options** — Steam → Interstate 76 → Properties → Launch Options:

```
"/home/deck/Games/Interstate76/i76-deck-launch.sh" %command% -glide
```

**2. Controller layout** — Steam → Interstate 76 → controller icon → Browse Configs →
Templates → **"Gamepad"**.

> **Do NOT "disable Steam Input".** On a Deck that falls back to *lizard mode* —
> keyboard/mouse emulation from the sticks — which is the opposite of what this tier
> needs. The **Gamepad** template keeps Steam Input on but makes it present a plain
> XInput pad: raw buttons reach the AHK layer, sticks reach `joystick1`, and rumble has
> a path back to the haptics.

## How it hangs together

```
[Deck hardware]
   │ Steam Input, "Gamepad" template — no key emulation, presents a virtual XInput pad
   ▼
[Proton prefix]
   ├── i76.exe        reads sticks via winmm joyGetPosEx  → input.map joystick1 blocks
   └── AutoHotkeyU32  reads buttons/triggers via XInput    → emits stock keys
                      writes XInputSetState                → rumble back to the haptics
```

The two consumers poll the same device through different APIs — exactly as on Mac and
Windows. [`i76-deck-launch.sh`](../deck/i76-deck-launch.sh) is what gets AHK into the
*same* prefix: it reads `$STEAM_COMPAT_DATA_PATH` at launch (Steam runs non-Steam
shortcuts from `compatdata/<appid>/`, **not** the prefix `deck-install.sh` built), copies
the payload in, waits 15 s for Proton to boot the prefix, then starts AHK and tears it
down on exit.

## Decode sheet — fill this in on the Deck (~5 min)

### 1. Does the baseline drive at all?

| Test | Expected | If not |
|---|---|---|
| Left stick left/right | car steers, analog | `joystick1` is the wrong device number under Proton — try `joystick0`/`joystick2` in `input.map` |
| Left stick up/down | accelerate / brake | if it does *nothing*, the axis token is wrong; if *inverted*, flip `-` to `+` |
| Any button at all | something happens | Gamepad template not applied, or the pad enumerated after launch |

### 2. Rumble — the headline unknown

Nobody has confirmed that `XInputSetState` from inside a Proton prefix reaches the
Deck's haptic motors. Mechanism is plausible (it's how modern games rumble on Deck), but
it is **unverified for this path**.

| Trigger | Expected feel | Felt it? |
|---|---|---|
| Hold L3 (or A held 400 ms) — nitrous | sharp kick, then a strong sustained buzz | ______ |
| Drive forward, stick pinned | low growl that rises with throttle | ______ |
| RB — handbrake | single dull thud | ______ |
| D-pad down — ignition | ~300 ms starter crank | ______ |
| LB + D-pad left/right — gears | light click | ______ |

If **nothing** rumbles: check `~/Games/Interstate76/deck-launch.log` for whether AHK
started at all. If AHK is running but silent, the XInput→haptics return path is the dead
end, and rumble on Deck needs a different carrier.

### 3. Double-input watch — the known overlap

The AHK layer and the `input.map` `joystick1` block **both** respond to the face buttons.
On Mac/Windows this is partly by design (A = fire in-sim via `Button1`, *and* Enter/click
in menus via AHK). But three buttons look like genuine doubles, and the Deck is where
you'll notice:

| Button | `input.map` says | AHK also sends | Watch for |
|---|---|---|---|
| **A** | `weapon_fire` (Button1) | click + Enter | intended — menus vs in-sim |
| **B** | `special1` / nitrous (Button2) | `C` | `C` should be unbound → harmless |
| **X** | `weapon_cycle` (Button3) | `Y` = next target | **cycles weapon AND changes target** |
| **Y** | `e_brake` (Button4) | `F3`/`F1` camera | **handbrake AND camera change** |

If X or Y visibly do two things at once, say so and the fix is to drop those two blocks
from the Deck `input.map` — the AHK layer already covers both actions. *This overlap
exists on Mac and Windows too;* it shipped that way, so parity was the right default, but
it's worth settling.

### 4. Report back

The shorthand is enough: `steer? throttle? rumble which ones? X/Y doubled?` — plus
whether you tested in Game Mode (Desktop Mode has the focus-split artifacts documented in
[DECK-INPUT-SCIENCE.md](DECK-INPUT-SCIENCE.md)).

## Troubleshooting

| Symptom | Cause |
|---|---|
| Steam shows the game "running" forever after quit | a stray `AutoHotkeyU32.exe` is holding the wineserver up — the wrapper's `cleanup` should `pkill` it; check the log |
| No pad response at all | the Gamepad template didn't apply, or Steam Input is fully disabled (lizard mode) |
| Keys fire twice | the v4 keyboard-emulation config is still active — you're running both tiers |
| `\r: command not found` | CRLF line endings; `deck-push.sh` strips them, running the script by hand may not |

Launch log: `~/Games/Interstate76/deck-launch.log` (rewritten each launch).

## Rollback

```bash
./deck/deck-push.sh deck@steamdeck --revert
```

Restores `input.map` from `.pre-baseline`, removes the payload and wrapper. Then in
Steam: clear the launch options back to `-glide` and re-select the
"Interstate 76 - Option 1 v4" template.
