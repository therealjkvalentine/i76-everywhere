# A force-feedback wheel on Interstate '76 — Thrustmaster T300RS (Windows)

> **STATUS 2026-08-01: CONFIGURED AND MEASURED, NOT YET DRIVEN IN-SIM.** Every axis
> and button number below was measured through **winmm `joyGetPosEx`** — the API the
> 1997 engine itself reads — not guessed from a diagram or a control panel. What has
> *not* happened yet is a mission: throttle polarity and whether force feedback
> actually reaches the wheel are unconfirmed until someone drives it.

This is the first wheel this project has characterised. It's also the answer to the
oldest open question in the repo: [FORCE-FEEDBACK-AND-VISUALS.md](FORCE-FEEDBACK-AND-VISUALS.md)
concluded FFB was a dead end on Mac and "should work" on Windows on community reports
alone. This is the Windows side, on real hardware.

## The two discoveries that make it work

### 1. A T-series wheel lies to you until its driver is installed

Plugged into Windows 11 with only the built-in HID driver, the T300 enumerates as:

```
VID_044F&PID_B65D    "Thrustmaster FFB Wheel"    (Standard system devices, 2006)
```

That generic string is a **pre-initialisation mode**. In it you get steering, 13
buttons and the POV hat — and *nothing else*. Measured over 2929 samples, the pedal
axes were frozen at **exactly one value (32767) each**. That's the tell: a live analog
axis jitters by a few units even untouched; one single value for 60 seconds is a dead
channel, not a light foot.

Installing Thrustmaster's driver (`2026_TTRS_1.exe`, signed by Guillemot R&D) makes
the wheel re-enumerate as its real self:

```
VID_044F&PID_B66E    "Thrustmaster T300RS Racing Wheel (USB)"   driver 2.11.57.0
```

**Do not chase pedal problems in software before checking this.** The generic-descriptor
signature is easy to misread as an old, unsupported wheel — it was misread here first.

### 2. SEPARATE pedals cannot drive I76. You must switch to COMBINED

This is the crux, and it is not obvious.

The T300 defaults to **Separate (3-axis)** pedals. Measured in that mode:

| Axis | Pedal | Rest | Pressed |
|---|---|---|---|
| R | accelerator | 65535 | → 0 |
| Y | brake | 65535 | → 0 |
| Z | clutch | 65535 | (absent/unused) |

Each pedal rests at an **extreme**. But I76's `throttle` is a **single bidirectional
sink** that expects rest = **centre** (one direction accelerates, the other brakes) —
the 1997 analog-stick convention. Bind a separate-mode pedal axis to it and the engine
reads full deflection at rest: **runaway throttle, or permanent reverse**, before you
touch anything.

Switch the wheel to **Combined (2-axis)** — in the T300RS control panel's *Test Input*
tab, or Thrustmapper's *Axes* tab, untick "Separate". Measured after the switch
(1960 samples):

| Axis | Rest | Travel | Direction |
|---|---|---|---|
| **Y** | **32767 (dead centre)** | −32767 / +32768, symmetric | accelerator → **0**, brake → **65535** |

One centred bidirectional axis. Exactly what the engine wants, and the stock
`throttle { - joystick1 Down/Up }` binding is then correct as written.

*Combined mode also means accelerating and braking together cancel out, where separate
mode lets them stack. For a 1997 car-combat game that's a non-issue.*

## The measured layout

Device sits at **winmm index 0 = `joystick1`**, and was the only winmm joystick present
(no contention with an Xbox pad).

```
steer    { - joystick1  Left/Right }   # X, rests centred ~33100, full lock 0..65535
throttle { - joystick1  Down/Up    }   # Y, COMBINED pedals, rests 32767
```

Buttons, measured by press order — **not** read off the control-panel diagram, because
the diagram's callout lines don't reliably distinguish 11 from 12, and those are the
two you most need to tell apart:

| # | Physical | Action |
|---|---|---|
| 1 | **Left paddle** | `hardpoint2_fire` |
| 2 | **Right paddle** | `hardpoint1_fire` |
| 3 | cluster | `weapon_cycle` |
| 4 | cluster | `e_brake` |
| 5 | cluster | `special1` (nitrous) |
| 6 | cluster | `weapon_fire` |
| 7 / 8 / 9 | cluster / lower | `frontal_target` / `TARGET_NEAREST_ENEMY` / `NEXT_TARGET` |
| 10 | lower | `SHOW_MAP` |
| **11** | **L3** | `toggle_lights` |
| **12** | **R3** | `start_engine` |
| **13** | **PS** | `HONK_HORN` |
| Hat ×4 | POV | `pilot_glance_*` |

Each is its own block — an **alternative** to the keyboard binding, never a chord
(see [CONTROL-DOCTRINE.md](CONTROL-DOCTRINE.md)).

## Force feedback

The registry gate ([enable-force-feedback.bat](../enable-force-feedback.bat)) was
**already satisfied** on this GOG install — `HKLM\SOFTWARE\WOW6432Node\ACTIVISION\Interstate '76`
exists with `EXE = i76.exe`, exactly as that script's own 2026-07-10 note predicted for
Galaxy installs. No Administrator step was required.

The wheel side is confirmed working: the T300RS control panel's *Test Forces* tab drives
12 named effects (Engine, Blown Tire, Explosion, Bumpy Road, Car Crash…), which means a
live DirectInput FFB stack. Set **Auto-Center → "by the game"**.

**Whether I76 actually emits effects to it is still unverified.** Note the standing
tension in [GAMEPAD-PC-MAC.md](GAMEPAD-PC-MAC.md): the exe is winmm-only for *input*
("no DirectInput — confirmed in the exe"), while the FFB story requires DirectInput
*output*. Both can be true if the Nitro Pack FFB module only initialises behind that
registry key — but that is a hypothesis, not a measurement.

## Settings worth changing

- **Rotation: drop 900° to ~240°.** The T300 defaults to 900° (2.5 turns lock-to-lock),
  which is right for a sim and wrong for a 1997 arcade car-combat game whose steering was
  designed around a keyboard. You will not survive a firefight winding 900°.
- **Firmware.** Shipped 28.00 here; the driver package carries `T300RS_LM4F_v34_00.tmf`.
  Updating to V34 was verified **not** to disturb the combined-pedal setting or the axis
  layout (re-measured after the flash: Y still rests 32767).

## The instrument

[`tools/i76-joyprobe.py`](../tools/i76-joyprobe.py) — reads the wheel through winmm, the
same API the engine uses. `--capture` waits for input rather than racing a timer, and
warms up before taking its baseline (a naive trigger fires on the *device settling*, not
on the user — that mistake cost two capture runs here).

Its `centre-resting test` output answers the one question that decides whether any given
axis can drive `throttle` at all.

## Open items

- **Throttle polarity.** Stock `-` should be correct (accelerator drives Y toward 0,
  matching a stick pushed forward = accelerate), but if accelerate/brake come out
  reversed in-sim, flip `-` ↔ `+`.
- **Does FFB actually fire in-mission**, and does it feel like anything at 20 FPS.
- **Button ergonomics** for 3–10 were assigned by position, not by play. Expect to swap.
- The AHK layer ([i76-remap.ahk](../i76-remap.ahk)) is **irrelevant to the wheel** — it
  reads XInput, and the T300 is DirectInput. No shift layer, no synthetic rumble. If real
  FFB works you get something better instead.
