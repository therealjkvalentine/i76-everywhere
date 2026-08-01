# A force-feedback wheel on Interstate '76 — Thrustmaster T300RS (Windows)

> **STATUS 2026-08-01: WORKING AND PLAYED.** Analog steering, analog accelerator and
> brake, all 13 buttons, and **real force feedback** — confirmed in-sim on a Thrustmaster
> T300RS. Every value below was measured through **winmm `joyGetPosEx`**, the API the 1997
> engine itself reads.

**This closes the repo's oldest open question.**
[FORCE-FEEDBACK-AND-VISUALS.md](FORCE-FEEDBACK-AND-VISUALS.md) concluded FFB was a dead end
on Mac and "should work" on Windows on the strength of two community reports. It works —
first-hand, on hardware. It also resolves the contradiction that doc flagged against
[GAMEPAD-PC-MAC.md](GAMEPAD-PC-MAC.md)'s "no DirectInput — confirmed in the exe":
**input is winmm, FFB output is DirectInput.** Both were true.

## The five things that had to be right

Each was a hard blocker. None was guessable; all five were found by measuring.

### 1. Install the driver — the wheel lies about itself until you do

On the built-in Windows HID driver the T300 enumerates as:

```
VID_044F&PID_B65D    "Thrustmaster FFB Wheel"    (Standard system devices, 2006)
```

That generic string is a **pre-initialisation mode**: steering and buttons work, pedals are
dead, no FFB. Measured over 2929 samples the pedal axes held **exactly one value (32767)
each** — a live analog axis jitters; one value for 60 seconds is a dead channel, not a light
foot. Thrustmaster's package (`2026_TTRS_1.exe`, Guillemot-signed) re-enumerates it as
`PID_B66E "T300RS Racing Wheel"`.

**Don't debug pedals in software before checking this.** The generic descriptor reads exactly
like an old unsupported wheel — it was misread that way here first, costing a detour through
legacy drivers that don't exist for Windows 11.

### 2. Switch the pedals to COMBINED — SEPARATE cannot work, ever

The T300 defaults to **Separate (3-axis)**. Measured:

| Axis | Pedal | Rest | Pressed |
|---|---|---|---|
| R | accelerator | 65535 | → 0 |
| Y | brake | 65535 | → 0 |

Both rest at an **extreme**. I76's `throttle` is a **single bidirectional sink** expecting
rest = **centre**. Bind either and the engine reads full deflection at rest — runaway
throttle or permanent reverse before you touch anything.

**Combined (2-axis)** (control panel *Test Input*, or Thrustmapper *Axes* → untick Separate):

| Axis | Rest | Travel | Direction |
|---|---|---|---|
| **Y** | **32767 (dead centre)** | −32767 / +32768, symmetric | accelerator → **0**, brake → **65535** |

The stock `throttle { - joystick1 Down/Up }` binding is then correct as written — polarity
confirmed in-sim, no flip needed. Survives the V34 firmware flash.

### 3. Remove the `mouse` source from the analog sinks, or steering is dead

Pedals worked; **steering did nothing**. Cause was already documented in
[DECK-INPUT-SCIENCE.md](DECK-INPUT-SCIENCE.md) §1 and hit the Deck the same way:

> *input.map sinks can list several analog sources (`joystick1` + `mouse`). The game's
> arbitration between them is undocumented — with the OS cursor parked, the mouse source
> can pin an axis.*

Fix: list **`joystick1` only** on `steer` and `throttle`.

```
throttle { - joystick1  Down/Up   }
steer    { - joystick1  Left/Right }
```

### 4. Fix the AHK layer's stuck arrow key — it hangs the game

**A latent bug in [i76-remap.ahk](../i76-remap.ahk) that predates the wheel and affects every
platform.** `RStickGlance` guarded with `if (u = "")`, but a device with **no U axis returns
`0.0`, not empty**. The wheel reports `JoyInfo = "ZRPD"` — no U. So 0 reached the hysteresis,
computed `(0-50)*-1 = +50 > 12`, and **held the Left arrow down from the moment AHK started**.

The game booted into a jammed glance-left and never reached the menu — it looked exactly like
a hang at "PLEASE STAND BY". Now gated on the capability string:

```ahk
if (!InStr(GetKeyState("JoyInfo"), "U")) {   ; no right-stick axis: not a pad
```

This would hit **any wheel or flight stick on Mac, Deck or Windows**. It never fired before
because the only device ever tested was an Xbox pad, which has a U axis.

Worse, it *persisted across relaunches*: `PLAY-i76.ps1` force-kills AHK, which skips its
`OnExit` handler, so the synthetic `{Left down}` never got a matching key-up and stayed
latched system-wide. The launcher now sends key-ups for everything the layer can hold.

### 5. Frame generation blanks the screen — use WGC, not DXGI

With Lossless Scaling running the engine rendered nothing. Its profile had drifted to
`CaptureApi = DXGI`; [WINDOWS-PLAYBOOK.md](WINDOWS-PLAYBOOK.md) §2 specifies **WGC** for this
windowed game. Launch with `-LosslessScaling ""` to rule it out. Two `dwm.exe` crashes
(`dwmcore.dll`) were logged in the same window, so the DXGI capture path may be destabilising
the compositor rather than merely failing.

## The layout

Device sits at **winmm index 0 = `joystick1`**, the only winmm joystick present.

```
steer    { - joystick1  Left/Right }   # X, rests centred ~33100, full lock 0..65535
throttle { - joystick1  Down/Up    }   # Y, COMBINED pedals, rests 32767
```

**Buttons bind natively, and `Button5`–`Button13` all work.** Earlier in the day these were
wrongly blamed for the hang (see §4 for the real cause); the engine's parser accepts them
fine. Numbers measured by press order, not read off the control-panel diagram — its callout
lines don't reliably separate 11 from 12, and those are exactly the L3/R3 pair.

| # | Physical | Action |
|---|---|---|
| 1 | Left paddle | `hardpoint2_fire` |
| **2** | **Right paddle** | **`weapon_fire`** — fires the *selected* weapon, incl. the cockpit handgun out the side window |
| 3 / 4 / 5 | cluster | `weapon_cycle` / `e_brake` / `special1` (nitrous) |
| 6 | cluster | `hardpoint1_fire` |
| 7 / 8 / 9 | cluster | `frontal_target` / `TARGET_NEAREST_ENEMY` / `NEXT_TARGET` |
| **10** | rim | **deliberately unbound** — see below |
| 11 / 12 / 13 | L3 / R3 / PS | `toggle_lights` / `start_engine` / `HONK_HORN` |
| Hat ×4 | POV | `pilot_glance_*` |

**Nothing modal on a rim button.** `SHOW_MAP` lived on 10 and got hit by accident mid-corner —
and the map opens but won't close from the same button, stranding you mid-fight. Map stays on
the keyboard (`M`).

## Traps

- **NEVER open the in-game Control Configuration menu.** It rewrote `input.map` here: stripped
  every comment, deleted the keyboard driving bindings (`W`/`S`/`A`/`D`) and the `Grey*Arrow`
  glance set, and moved `hardpoint2_fire` from `keyboard Two` to `mouse RightBtn`. It "added"
  joystick axes that were already there. Back up first; edit the file directly.
- **Rotation: drop 900° to ~240°.** The T300 default is 2.5 turns lock-to-lock — right for a
  sim, wrong for a game whose steering was designed around the `A` and `D` keys.
- **Connect the wheel before launching.** The engine enumerates joysticks once, at startup.
- One `i76.exe` crash was logged in **`winmmbase.dll`** (0xc0000005). KB5101650 — the known
  winmm-breaking update — was *not* installed, so this is unexplained; noted because I76's
  entire input path is winmm and a wheel polls it hard.

## Open

- **AHK cannot see this wheel's buttons.** `GetKeyState("JoyInfo"/"JoyButtons"/"JoyX")` all
  read correctly, but `GetKeyState("Joy1".."Joy13")` never registered a single press, while a
  Python winmm probe on the same device read them fine. Unexplained. Native bindings made it
  moot, so the wheel layer in `i76-remap.ahk` is present but **disabled**.
- Whether FFB effects are distinguishable per event, and how they feel at a 20 FPS base.

## The instrument

[`tools/i76-joyprobe.py`](../tools/i76-joyprobe.py) reads the wheel through winmm — same API as
the engine. `--capture` waits for input instead of racing a timer, and warms up before taking
its baseline: a naive trigger fires on the *device settling*, not on the user, which cost two
capture runs before it was built this way. Its `centre-resting test` directly answers whether a
given axis can drive `throttle`.
