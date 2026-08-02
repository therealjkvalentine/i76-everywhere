# A force-feedback wheel on Interstate '76 — Thrustmaster T300RS (Windows)

> **STATUS 2026-08-01: WORKING AND PLAYED.** Analog steering, analog accelerator and
> brake, all 13 buttons, and **real force feedback** — confirmed in-sim on a Thrustmaster
> T300RS. Every value below was measured through **winmm `joyGetPosEx`**, the API the 1997
> engine itself reads.
>
> **One operational rule:** close the Thrustmaster control panel before launching, or FFB
> silently fails to initialise and the first shot crashes the game. See the FFB section.

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

**Buttons run through the AHK layer, not `input.map`.** `input.map` keeps only the two analog
sinks; every button and the hat are emitted by [i76-remap.ahk](../i76-remap.ahk) as the engine's
stock keys. Native `joystick1 Button1`–`Button13` *do* all work (an earlier draft wrongly blamed
`Button5+` for a hang that was really the stuck-arrow bug in §4) — but native tops out at one
action per button, where AHK gives a **shift layer** and roughly 27 actions from 13 buttons.

**Button numbers, from Thrustmaster's manual ("MAPPING FOR PC" page).** It publishes the PC
numbering beside the PlayStation labels, and it confirms every number we had measured by press
order — the two we'd only *inferred* (L2=10, SE=7) both check out:

| PS label | PC # | | PS label | PC # |
|---|---|---|---|---|
| **L1** (left paddle) | **1** | | **SHARE / CREATE** ("SE") | **7** |
| **R1** (right paddle) | **2** | | **OPTIONS** | **8** |
| **L2** | **10** | | **L3** | **11** |
| **R2** | **9** | | **R3** | **12** |
| △ □ ○ ✕ cluster | 3 / 4 / 5 / 6 | | **PS** | **13** |
| Directional buttons | the POV hat | | | |

Note L2/R2 are **10/9** — not sequential, and not the order you'd guess from L3/R3 being 11/12.
Worth reading off the manual rather than assuming. (Measuring still beats the *control-panel
diagram*, whose callout lines don't reliably separate 11 from 12 — exactly the L3/R3 pair.)

| # | Physical | Base | Hold **6** = shift |
|---|---|---|---|
| 1 | L1 left paddle | hardpoint 2 | hardpoint 1 |
| 2 | R1 right paddle | **fire selected weapon** (incl. cockpit handgun) | front target |
| 3 / 4 / 5 | cluster | cycle weapon / handbrake / nitrous | combat view / reverse / special 2 |
| **6** | cluster | **SHIFT** | — |
| 7 | SE | rear gun (hp3) | dropper (hp4) |
| 8 | OPTIONS | target nearest | untarget |
| **9** | **R2** | **LINK FIRE** (`weapon_link`) | look at target |
| 10 | L2 | next target | radar range |
| 11 | L3 | ignition | radar camera |
| 12 | R3 | handbrake | binoculars |
| 13 | PS | horn | poetry |
| Hat | D-pad | lights / map / ignition / notepad | gear up/down (Period/Comma) |

**R2 = link fire is the engine-native way to fire several weapons at once** — one event, one FFB
effect. That matters here: firing multiple hardpoints from a single button is what crashed
`I7_SFRCE.DLL` (below). `weapon_link` is also on keyboard `F`.

Direct hardpoint keys are **one shot per press** by design; sustained fire is what the right
paddle's `weapon_fire` hold is for. A repeat-tap mode was tried and removed — see the FFB section.

**Nothing modal on a rim button.** `SHOW_MAP` lived on 10 and got hit by accident mid-corner —
and the map opens but won't close from the same button, stranding you mid-fight. Map stays on
the keyboard (`M`).

## FFB works — but CLOSE THE THRUSTMASTER CONTROL PANEL FIRST

**This is the single most important operational rule on this page.** Thrustmaster's own control
panel says it at the bottom of every tab:

> *"Always close this CONTROL PANEL window (by clicking OK) before starting your game."*

The control panel **holds the DirectInput device**. Leave it open and the game's FFB init fails —
the module's string is `I7FF_InitSystem Failed to open FF Joystick` — so its effect objects are
never created. Then **the first shot dereferences a null effect handle**:

```
i76.exe  faulted in  I7_SFRCE.DLL   0xc0000005   fault offset 0x2505
```

Reproduced three times on 2026-08-01, always the same offset, and the giveaway is that the last
one had **no force feedback at all** — "FFB stopped working" and "crashes on fire" are not two
problems, they are the same one. No FFB *because* init failed; crash *because* init failed.

**Two earlier hypotheses in this document were wrong** and are retracted:

- that firing two hardpoints from one button caused it
- that a repeat-fire mode tapping every ~120 ms caused it

Both were plausible — the module does load a per-weapon effect from `force\*.frc` on every shot
(`Weapon: Hardpoint:%d WpnId:%d Freq:%d Gain:%d Direction:%d`) — and both were removed in turn
without stopping the crash, which should have been the clue. The control panel was open across
all three. **Effect churn was never demonstrated to be the cause**, and the repeat-fire mode
removed on its account may be perfectly safe to restore.

The rule this yields is more general than the wheel:

> When a device's own vendor UI warns you to close it before gaming, that warning is about
> **exclusive device acquisition**, and it will present as the *game* being broken.

**If FFB has already failed once**, a relaunch may not be enough — the crashed process can leave
the device unreleased. Power-cycle the wheel (unplug USB and mains, ten seconds, back in) before
launching again.

## Traps

- **NEVER open the in-game Control Configuration menu.** It rewrote `input.map` here: stripped
  every comment, deleted the keyboard driving bindings (`W`/`S`/`A`/`D`) and the `Grey*Arrow`
  glance set, and moved `hardpoint2_fire` from `keyboard Two` to `mouse RightBtn`. It "added"
  joystick axes that were already there. Back up first; edit the file directly.
- **Rotation: 300°.** Field-settled 2026-08-01. The T300 defaults to 900° (2.5 turns
  lock-to-lock) — right for a sim, wrong for a game whose steering was designed around the `A`
  and `D` keys. 300° is the value that actually plays well; an earlier draft of this doc guessed
  ~240°, which is too twitchy. Set it on the control panel's *Test Input* tab.
- **Connect the wheel before launching.** The engine enumerates joysticks once, at startup.
- One `i76.exe` crash was logged in **`winmmbase.dll`** (0xc0000005). KB5101650 — the known
  winmm-breaking update — was *not* installed, so this is unexplained; noted because I76's
  entire input path is winmm and a wheel polls it hard.

## RETRACTED: "AHK can't read this wheel"

An earlier version of this document stated that AHK could not see the wheel's buttons. **That
was wrong.** AHK reads all 13 buttons fine, headless (no GUI window needed), with both the
plain `GetKeyState("Joy1")` and prefixed `GetKeyState("1Joy1")` forms, including simultaneous
presses.

The finding came from a bug in the probe scripts, not the hardware: `FileAppend, % text, f`
treats `f` as a **literal filename**, not the variable — AHK needs `%f%`. Three probes wrote
their output to a stray file called `f` while their intended logs stayed empty, and the empty
logs were read as "AHK sees nothing".

**The lesson, since this cost hours:** a probe that reports *nothing* is not evidence until the
probe itself is proven to report *something*. Give every diagnostic a positive control — the
Python winmm probe that "disproved" AHK was the control that should have been run against a
known-good AHK log first.

## Open

- Whether one button firing two hardpoints (`hardpoint1_fire` + `hardpoint2_fire` both
  naming `Button1`) actually drives both, or only the first block the parser sees.
- Whether FFB effects are distinguishable per event, and how they feel at a 20 FPS base.

## The instrument

[`tools/i76-joyprobe.py`](../tools/i76-joyprobe.py) reads the wheel through winmm — same API as
the engine. `--capture` waits for input instead of racing a timer, and warms up before taking
its baseline: a naive trigger fires on the *device settling*, not on the user, which cost two
capture runs before it was built this way. Its `centre-resting test` directly answers whether a
given axis can drive `throttle`.
