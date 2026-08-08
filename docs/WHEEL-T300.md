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
| 1 | L1 left paddle | **lights** | hardpoint 1 |
| 2 | R1 right paddle | **fire selected weapon** (incl. cockpit handgun) | front target |
| 3 / 4 / 5 | cluster | cycle weapon / handbrake / nitrous | combat view / reverse / special 2 |
| **6** | cluster | **SHIFT** | — |
| 7 | SE | rear gun (hp3) | dropper (hp4) |
| 8 | OPTIONS | target nearest | untarget |
| **9** | **R2** | **horn** | look at target |
| 10 | L2 | **horn** | radar range |
| 11 | L3 | **lights** | radar camera |
| 12 | R3 | **ignition** | binoculars |
| 13 | PS | horn | poetry |

**Rebalanced 2026-08-08**, once the [Fighterstick](FIGHTERSTICK.md) took over
weapons, targeting and the gearbox. The wheel is spun with the left hand, so its
buttons became the things you reach for *without looking* — lights, horn,
ignition — rather than combat controls needing precision. Everything displaced has
a home: `weapon_link` moved to the stick's pinky, targeting to its castle hat, the
handbrake to pulling the stick back. Three horn buttons is deliberate; it is
Interstate '76.

Button 12 was also removed from `gWheelHoldSet`. It was the handbrake, which must
be *held*; it is now ignition, which must be *tapped*. Left in the hold set it
would have held `i` down for as long as R3 was pressed — a starter motor you
cannot release. **Changing what a button does means re-checking every table keyed
on its number.**
| Hat | D-pad | lights / map / ignition / notepad | gear up/down (Period/Comma) |

**R2 = link fire is the engine-native way to fire several weapons at once** — one event, one FFB
effect. That matters here: firing multiple hardpoints from a single button is what crashed
`I7_SFRCE.DLL` (below). `weapon_link` is also on keyboard `F`.

Direct hardpoint keys are **one shot per press** by design; sustained fire is what the right
paddle's `weapon_fire` hold is for. A repeat-tap mode was tried and removed — see the FFB section.

**Nothing modal on a rim button.** `SHOW_MAP` lived on 10 and got hit by accident mid-corner —
and the map opens but won't close from the same button, stranding you mid-fight. Map stays on
the keyboard (`M`).

## FFB not engaging at all? Other joysticks are the cause — SOLVED

**Short version: remove other joystick devices (especially virtual ones) and reboot.**
Full diagnosis, including the winmm-vs-DirectInput signature that identifies it, is in
[**FFB: SOLVED — a 3Dconnexion emulator was stealing the DirectInput device**](#ffb-solved--a-3dconnexion-emulator-was-stealing-the-directinput-device)
below, and in [FFB-LAPTOP-RECON.md](FFB-LAPTOP-RECON.md) with the ruled-out list.

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

---

## When the wheel works in the control panel but NOT in game

Field case, 2026-08-01, second Windows box: the wheel was **perfect in Thrustmaster's
control panel** — all buttons, full rotation, pedals COMBINED — yet in game there was
no steering, no buttons, and no FFB. It had been working on another Windows laptop
minutes earlier.

**Thrustmaster's panel talks DirectInput. The 1997 engine reads winmm.** The two see
the device through different layers, so "fine in the control panel" says nothing about
what the game gets. Always confirm through winmm (`tools/i76-joyprobe.py`).

### Cause 1 — a stale winmm calibration (CONFIRMED, fixed)

`HKCU\System\CurrentControlSet\Control\MediaResources\Joystick\DINPUT.DLL\CurrentJoystickSettings`
holds a `JoystickNConfiguration` blob per slot. On this machine the wheel's said:

| axis | driver declares (`joyGetDevCaps`) | stored config claimed |
|---|---|---|
| X | 0–65535 | 0–65535 |
| **Y / Z / R** | **0–65535** | **0–1023** |

A 64x scaling error on three axes. Every reading through winmm came out incoherent —
axes bleeding into one another, half-scale jumps, values moving during "press buttons
only". After correcting it, X read a proper centred, jittering 31681–32767.

The blob is `JOYREGHWCONFIG`; `jrvHardware` (a `JOYRANGE`) sits at **offset 12**, laid
out as `min[6], max[6], center[6]` DWORDs in X,Y,Z,R,U,V order — so max is at offset
36 and center at 60. `dwNumButtons` is at offset 4. Fix by writing 65535/32768 into
the offending axes, or by `joy.cpl` → Properties → Settings → **Reset to default** +
Calibrate.

**THERE ARE TWO COPIES AND YOU MUST FIX BOTH.** Under the same `DINPUT.DLL` key:

```
CurrentJoystickSettings\Joystick1Configuration          <- the live one
JoystickSettings\VID_044F&PID_B66E\Joystick1Configuration  <- the per-device MASTER
```

Patching only `CurrentJoystickSettings` looks like it works and then silently reverts:
the per-device copy is authoritative and is reloaded on the next enumeration. Both were
wrong here, and fixing only the first is why the first repair attempt appeared to have
no effect. After fixing both, all four axes read a clean centred 32767 at rest.

**Export the key before touching it**
(`reg export "HKCU\System\...\Joystick" backup.reg`); restoring is a double-click.

### Cause 2 — ~~FFB needs a registry key this portable copy never had~~ **WRONG, RETRACTED**

> **This was not the answer.** Left here because it is a plausible-sounding theory that
> should not be re-derived. Disassembly settled it: **FFB init at `0x445A60` is called
> unconditionally from `0x402F93`** — there is **no registry gate** on the Gold exe. The
> only `SOFTWARE\Activision` access sits beside `Minimum`/`miss8`/`miss16` (mission
> texture resolution). `enable-force-feedback.bat` is a CD-era fix that does not gate
> this build, and the GOG-installed-vs-portable difference is a coincidence.
>
> The real cause was **other joysticks in the DirectInput enumeration** — see the SOLVED
> section below.

The original (incorrect) claim: `enable-force-feedback.bat` as Administrator creates
`HKLM\SOFTWARE\WOW6432Node\ACTIVISION\Interstate '76` with `EXE=i76.exe`; it was
verified absent on that box and present after running it. Both observations were true —
the **inference** that it gated FFB was not.

### Still open on that box

Buttons were not reported through winmm even with the calibration corrected. Not
resolved. Notes for whoever picks it up:

- The device is healthy: `ConfigManagerErrorCode=0`, and OS-level FFB is registered
  (`OEMForceFeedback` CLSID plus Thrustmaster's effect table).
- Its OEM registry entry registers **10 buttons for a 13-button wheel** and **3 axes
  for a 4-axis device** — a real mismatch, though those subkeys are believed to be
  control-panel presentation rather than functional gating.
- This box has **two virtual joysticks the working laptop does not**: vJoy
  (`joystick4`) and a 3Dconnexion KMJ Emulator (`joystick8`). vJoy is no longer needed
  since head tracking moved to freetrack shared memory, so removing both is the
  obvious next experiment.
- **Do not conclude "no buttons" from a probe run while nobody is pressing any.** Two
  readings here were taken with the user away and are worthless as evidence — the same
  trap as the AHK probe above.

### Cause 3 — input.map rewritten by the in-game menu (THE ACTUAL ONE, 2026-08-02)

After all of the above, the wheel was still dead — no steering, no pedals, no
buttons. None of it was the device. `input.map` had been **rewritten by the
in-game Control Configuration menu**, which corrupts it:

| | corrupted | good |
|---|---|---|
| size | 3234 B | 5219 B |
| `steer` block | **absent** | present |
| `throttle` block | **absent** | present |
| `joystick1` references | **0** | 10 |
| other joystick refs | **16 x `joystick8`** (a 3Dconnexion emulator!) | 0 |

No analog sink means no wheel and no pedals, however healthy the hardware is —
and the buttons had been re-pointed at an entirely different device.

**Check this before touching drivers, calibration or the registry.** The order
that wasted the most time here was: driver → control panel → winmm calibration →
registry → *only then* the game's own config. Reverse it. The vendor's control
panel talks DirectInput and will look perfect while the engine, which reads winmm
and this file, gets nothing.

`tools/lint-input-map.py` now fails on this signature — missing analog sinks, and
button bindings naming a different stick than the analog sinks do. It also gained
a genuine bug fix found here: the two-analog-sources check only inspected `+`
lines, but analog sinks are `-` lines (the sign is axis polarity, not a chord),
so it had never once examined a real `steer`/`throttle` block and passed a file
carrying the documented mouse-pinning trap.

Recovery: restore a known-good `input.map` (the portable zip carries one), drop
the `mouse` source from `steer`/`throttle` per §3 above, re-lint, and **restart
the game** — it reads `input.map` and enumerates joysticks only at startup.


## FFB: SOLVED — a 3Dconnexion emulator was stealing the DirectInput device

Force feedback worked on a laptop and refused on a desktop for an entire session.
The answer was not the game, the wheel, the driver or the registry: the desktop
had **two virtual joysticks the laptop did not** — vJoy and a *3Dconnexion KMJ
Emulator*. **Removing the 3Dconnexion emulator and rebooting made FFB work
immediately.**

```
FF device detected flag : 1
FF effect object ptr    : 0x0B900000        <- first success ever recorded here
```

Afterwards `joystick1` was the **only** winmm device present; before, the wheel
shared the list with vJoy at id 3 and the emulator at id 7.

**Why it breaks FFB and not ordinary input.** The engine reads *input* through
winmm, where the wheel was always found correctly at `joystick1` — steering,
pedals and buttons all worked. But *force feedback* is opened through
**DirectInput**, which enumerates separately and needs **exclusive** acquisition.
A virtual device in that enumeration is enough to make `I7FF_InitSystem` fail,
and it tries exactly once at startup — its own words: *"Failed to open FF
Joystick. Try again next time."*

That asymmetry is the diagnostic signature worth remembering: **input works but
FFB does not** points at DirectInput enumeration, not at the wheel.

### What this rules out, permanently

Chased and eliminated before finding it — don't repeat these:

| suspect | verdict |
|---|---|
| `enable-force-feedback.bat` registry key | **irrelevant on the Gold exe.** FFB init at `0x445A60` is called *unconditionally* from `0x402F93`; there is no registry gate. The only `SOFTWARE\Activision` access sits beside `Minimum`/`miss8`/`miss16` (texture resolution). The PCGW key is a CD-era fix. |
| Lossless Scaling / frame generation | field-tested without it; failed identically |
| Thrustmaster control panel open | closed throughout |
| stale winmm axis calibration | real bug, fixed, but not this |
| `LoadLibrary` failing | never happened — see below |

### The false negative that cost the most time

`i76.exe` is 32-bit. From 64-bit tooling **both `$proc.Modules` and
`tasklist /m` enumerate only the WOW64 stubs** and report `I7_SFRCE.DLL` as not
loaded while it is loaded and working. A `LoadLibrary` test run from 64-bit
PowerShell compounded it, returning error 126 (which is meaningless across the
architecture boundary). Repeated from a 32-bit process it loads fine.

**Read `0x52bbdc` instead** — the exe's own `GetProcAddress` result for
`I7FF_InitSystem`, written only after `LoadLibrary` *and* `GetProcAddress` both
succeed. `tools/check-ffb.ps1` now uses that.

### Still open

The wheel ignores the 300-degree limit and resists turning once the Thrustmaster
control panel is closed — the panel appears to apply rotation only while running.
That is a driver/profile matter, not the game.


## Buttons: strip the NATIVE joystick1 bindings, or half the wheel double-fires

With the wheel working, "most buttons work but not exactly right" turned out to be
`input.map` still carrying the **native** `joystick1` button/hat bindings that
`setup-windows.ps1` appends for a gamepad. The AHK wheel layer already emits a key
for every button, so each of these fired **twice**:

| block | native binding | what the layer sends for that button | result |
|---|---|---|---|
| `weapon_fire` | `Button1` | `2` = hardpoint2 | left paddle fired **two weapons** |
| `special1` | `Button2` | `Enter` = weapon_fire | right paddle fired weapon **+ nitrous** |
| `weapon_cycle` | `Button3` | `Tab` | doubled |
| `e_brake` | `Button4` | `Space` | doubled |
| `pilot_glance_*` | `HatUp/Down/Left/Right` | `h`/`m`/`i`/`n` | hat glanced **and** toggled lights/map/ignition/notepad |

The left-paddle one matters most: two hardpoints from one press is precisely the
case documented above as crashing `I7_SFRCE.DLL`, and it is live again now that
FFB works.

`special1` was the visible symptom — it was bound *only* to `joystick1 Button2`,
so the layer's nitrous key (`6`) went nowhere. `Six` appeared nowhere in the file.

**The fix**, verified by cross-referencing every key the layer emits against the
map (0 dead, lint clean):

- `special1` → `+ keyboard Six`
- delete all seven remaining `+ joystick1 ButtonN` / `HatX` blocks

Safe because the keyboard bindings live in *separate earlier blocks* —
`GreyUpArrow` etc. for glance, `Enter`/`Tab`/`Space` for the rest — so head
tracking's arrow keys and the layer's keys all survive. Afterwards `joystick1`
appears **only** on `steer` and `throttle`, which is the wheel doctrine.

**Re-running `setup-windows.ps1` will put them back** — it appends the gamepad
baseline unconditionally. After any re-run on a wheel machine, strip them again
and re-lint. To find them:

```
grep -n "joystick1" input.map     # should show ONLY steer + throttle
```
