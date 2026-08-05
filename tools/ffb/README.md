# Custom force feedback for Interstate '76

The engine's own FFB is a closed 1997 system: on fixed events it plays a
pre-authored effect from `force\*.frc`. It has **no concept of slip, load or road
texture** — that vocabulary postdates it. So a communicative wheel has to be
synthesised from game state, outside the engine.

## Status

| piece | state |
|---|---|
| **FFB output** (`FfbCore.ps1`) | **working** — acquires the T300, drives arbitrary force, recovers a lost device |
| **Telemetry** (`Telemetry.ps1`) | **working** — speed, velocity, yaw rate, steer, throttle, derived slip/impact |
| **Force model** (`FfbMixer.ps1`) | **working** — 8 channels, 28 assertions passing |
| **Interposer + panel** (`ffb-interposer.ps1`) | **working** — live panel, channel solo/mute, CSV logging |
| **Calibration** (`ffb-calibrate.ps1`) | **working** — measures yaw sign and steering lock from one drive |
| Feel tuning | **not started** — needs a drive; nothing here has been judged by hand yet |
| Weapon/engine effects | not started — see "the .frc files" below |

## Quick start

```powershell
# 1. watch it think, without touching the wheel. Safe any time.
tools\ffb\ffb-interposer.ps1 -DryRun

# 2. stop the model guessing: drive 30 s, both directions, sustained turns
tools\ffb\ffb-calibrate.ps1

# 3. for real
tools\ffb\ffb-interposer.ps1

# judge one channel at a time - the only way to actually tune feel
tools\ffb\ffb-interposer.ps1 -Only corner
tools\ffb\ffb-interposer.ps1 -Mute texture,scrub -Master 0.7
```

Live keys: `[space]` mute · `[+/-]` master gain · `[s]` save tune · `[q]` quit.

## The one idea that matters: slip makes the wheel go LIGHT

The obvious way to signal slip is to add force — buzz the wheel when grip goes.
That is backwards, and it is why a lot of custom FFB feels like a rumble pack
bolted to a wheel.

The weight you feel in a real car **is** the front tyres' self-aligning torque,
and that torque is a product of slip angle. As a tyre passes its limit the torque
peaks and then **collapses** — the contact patch is sliding, not gripping, so it
stops pushing back. Every driver knows the sensation: the wheel goes dead and
light just before the nose runs wide.

So understeer here does not add a signal, it **attenuates** the steady channels.
You feel grip leave. It needs no new effect primitive and it is free.

Oversteer is the opposite case and *does* add force — toward the counter-steer,
because that is the direction caster would drag the wheel and the correction you
want to make anyway.

## Channels

| channel | driven by | feel |
|---|---|---|
| `center` | steer × speed | self-aligning torque; the baseline weight |
| `corner` | lateral g (yaw × speed) | a bend has weight |
| `oversteer` | measured vs geometric yaw | push toward the catch |
| `brake` | negative longitudinal g | front axle loading up |
| `texture` | speed × suspension motion | road surface |
| `scrub` | understeer | the sound of rubber, on top of the lightness |
| `judder` | hard braking | lockup shimmy (no ABS in 1997) |
| `impact` | velocity-vector discontinuity | collisions |

Continuous channels are deliberately held **low** so transients read on top —
the discipline that makes the pad rumble mixer (`i76-remap.ahk`) work. Raising
the steady gains to feel "more" buries every transient and leaves the wheel
merely heavy.

## Design constraints that shaped this

**One output primitive.** This wheel refuses periodic effects —
`CreateEffect(GUID_Sine)` returns `REGDB_E_CLASSNOTREG` while constant force is
fine. So everything sums into a single constant force rewritten each loop:
`force = steady + texture*osc(phase) + transients`. Vibration alternates *part*
of the sum, never the whole thing — flipping everything would cancel the steady
feel and turn cornering load into a rattle.

**The sim is a fixed 20 Hz step** (Peelar; Roanish's `world_tick`). Poll at 60 Hz
and differentiate naively and you get `0, 0, spike, 0, 0, spike` — not noise you
can filter, an artefact of sampling faster than the simulation. `Telemetry.ps1`
recomputes derivatives only when a value actually changed, dividing by the time
since the previous change, and holds them in between.

**The loop tops out near 62 Hz.** `Start-Sleep`'s granularity is one scheduler
tick (~15.6 ms), so requesting 100 Hz yields 62. Telemetry is not the limit — it
polls at 3400 Hz. Every oscillator therefore stays at or under ~15 Hz to keep 4+
samples per cycle; a 22 Hz scrub does not give a 22 Hz buzz, it gives an aliased
beat that feels like a fault in the wheel.

**Units are metres.** The wheel contact points give a 4.66 m wheelbase, so the
model works in real g rather than magic constants.

## Coexistence with the game: no patch needed

FFB needs an **exclusive** DirectInput acquisition and the game takes one at
startup, which looked like a hard either/or: the engine's authored weapon effects
*or* our synthesised feel, with the second requiring a NOP over the FFB init call
at `0x402F93`.

`ffb-coexist-test.ps1` measures that **we** hold the wheel with the game genuinely
focused — foreground confirmed via `GetForegroundWindow` — every write returning
`S_OK`. So no game memory is patched and none needs to be.

**But read that claim narrowly.** It establishes that *our* acquisition survives.
It does **not** establish that the *game* can still play *its* effects while we
hold the device, and those are different questions. The engine's `0x52bbd0` flag
and `0x52bbcc` effect pointer are written once at init and never cleared, so they
cannot answer it either. Confirming it needs a trigger-pull with both running.

### The ordering rule, which is not optional

**Nothing may hold the wheel when the game starts.** The engine acquires FFB *once*
at startup and never retries — "try again next time" is a give-up, not a retry
(`docs/FFB-LAPTOP-RECON.md`). So an interposer left running from a previous session
means the game gets **no force feedback at all, for the whole session**, with
nothing on screen to say why.

This is easy to hit, because the interposer runs in its own terminal and used to
outlive the game. It was hit in the field on 2026-08-04. Two defences now:

- the interposer **exits when the game does**, releasing the device;
- `PLAY-i76.ps1` **stops any running interposer** before launching, as a backstop
  for one started by hand or hung.

The safe order is: wheel connected → game launched → interposer started, *in that
order*, and the interposer restarted after any game restart.

Losing the device mid-session is treated as a state to recover from, not an error:
`Ffb-Reacquire` takes it back and the panel logs it.

## Calibration

Two values in `Telemetry.ps1` are assumptions rather than measurements, and both
matter:

- **`TEL_YAW_SIGN`** — does positive steer produce positive yaw at `+0xcc`?
  Nothing in the struct says. Wrong, and the cornering channel helps you turn
  *into* the corner.
- **`TEL_STEER_LOCK`** — radians at full lock. Sets how readily slip triggers.

`ffb-calibrate.ps1` measures both from one drive and writes `ffb-calib.json`,
which `Telemetry.ps1` loads automatically. Sign comes from correlating steer
against observed yaw — model-free, needing only that turning one way rotates the
car one way. It is robust and has never been the problem.

**The lock fit was wrong once, badly, and the fix is worth knowing.** The obvious
estimator rearranges the bicycle model per sample —
`lock = atan(yaw·wheelbase/speed) / steer` — and takes the median. On a real drive
that reported **5.8°** with no sign of distress. The truth is ~20–30°. Two causes:

1. **Dividing by `steer` amplifies noise where steer is small.** A near-straight
   sample (`steer 0.2, yaw 0.03`) fits a tiny lock, and near-straight samples
   vastly outnumber hard-cornering ones — so the median sits in the noise rather
   than in the cornering data.
2. **Yaw lags steer** by a few tenths of a second. Mid-transition steer is already
   large while yaw is still building, fitting a lock that is too small. Sinusoidal
   steering is mostly transition.

Now: **regression through the origin** on `θ = atan(yaw·wheelbase/speed)` against
steer, `lock = Σ(steer·θ)/Σ(steer²)`. It never divides by a small steer and it
weights by `steer²`, so the hard-cornering samples that carry the information
dominate. Plus a steadiness filter, a plausibility range (10–45°), and a
**falsification check**: whatever the lock is, the model built from it must be able
to produce the yaw rates the car demonstrably reached. A 0.101 rad lock predicts
0.22 rad/s at 10 m/s where 1.6 rad/s was observed — a contradiction detectable
*without* knowing the right answer. A fit that fails any of these is not written;
the sign is kept, since that is what matters most.

Every run now also dumps `ffb-calib-samples.csv`. The first version kept nothing,
so when its fit came out wrong the only way to investigate was another 30-second
drive. Refit offline with `-FromLog ffb-calib-samples.csv`.

`ffb-calib-test.ps1` (11 assertions) synthesises drives from a **known** lock,
including the first-order yaw lag that caused the original error, and asserts
recovery — sustained and sinusoidal steering, a wider 0.60 rad lock to prove it
isn't just echoing a default, an inverted sign, and a no-information drive that
must be *rejected* rather than fitted.

## Testing

```powershell
tools\ffb\ffb-mixer-test.ps1          # 28 assertions, no game or wheel needed
tools\ffb\ffb-coexist-test.ps1        # can we and the game share the device?
tools\ffb\ffb-telemetry-probe.ps1     # rediscover struct offsets by behaviour
```

Judging a force model by driving is slow, unrepeatable and needs a human holding
the wheel — but most of what can be *wrong* with one isn't about feel at all:
sign errors, clipping, channels that never fire, transients that never decay,
NaN. `ffb-mixer-test.ps1` checks those from a desk. It cannot tell you whether
the result feels good; it tells you the model does what it claims, which is the
precondition for tuning feel rather than a substitute for it.

Two bugs it caught, both invisible in play:

1. **`$T` and `$t` are the same variable.** PowerShell names are
   case-insensitive, so `$T = $Mix.Tune` followed by `$t = $Sample.T` replaced
   the entire tune table with a number. Every gain read back as `$null` and
   `0/$null` produced **NaN forces**.
2. **The NaN test passed vacuously.** `Mix-Update` threw before returning, `$o`
   was `$null`, and `$null.Force` read as `0`. A test that cannot fail is worse
   than no test. It now counts throws as failures.

## Five things that each cost a debugging round in `FfbCore.ps1`

Recorded because none produced a useful error message:

1. **`DirectInput8Create` needs a non-NULL `hinst`.** `GetModuleHandle($null)`
   returns NULL from PowerShell → `E_INVALIDARG`. Use `LoadLibraryA("dinput8.dll")`.
2. **`DIDFT_ANYINSTANCE` is `0x00FFFF00`**, not `0x0000FF00`. Wrong mask →
   `SetDataFormat` fails `E_INVALIDARG` with no other clue.
3. **Exclusive mode needs a real window owned by this process.** NULL hwnd →
   `E_HANDLE`; `GetConsoleWindow()` is *not* sufficient and `Acquire` then fails
   `ERROR_INVALID_WINDOW_HANDLE` **after** `SetCooperativeLevel` returned OK. A
   hidden WinForms window works — and must stay referenced, or the GC destroys it
   and takes the acquisition with it.
4. **PowerShell parses `0xFFFFFFFF` as Int32 `-1`**, which will not coerce to the
   `UInt32` that `dwDuration`/`dwTriggerButton` want. Use `4294967295`.
5. **Periodic effects do not work on this wheel** (see "one output primitive").

## Telemetry map

Player entity resolves via `[[[0x54a264]]+0x70]`. Full table and the corrections
it forced live in `docs/MEMORY-MAP-INDEX.md` Tier 2. Summary:

| offset | field | confidence |
|---|---|---|
| `+0x04..0x30` | four float3 wheel contact points, local space | confirmed |
| `+0xac` | speed = \|velocity\| | confirmed by identity |
| `+0xbc` | velocity float3, world | confirmed by identity |
| `+0xc8` | angular velocity float3 — yaw rate at `+0xcc` | strong |
| `+0xd4` | acceleration / accumulated force float3 | likely, unused |
| `+0xe0` / `+0xe4` | steer / throttle, −1..1 | confirmed |
| `+0x80..0x8c` | **loop temporary** — looks like telemetry, is not | confirmed |

Two corrections worth carrying forward: `+0x08` is **not** a rotation matrix
(that error is why position was never found — the hunt was for something adjacent
to a matrix that does not exist), and velocity was listed as unfound in
`GHIDRA-MEMORY-MAP.md`.

Position is still unidentified, and **the force model does not need it** — every
channel derives from velocity, angular velocity and the control inputs.

## The .frc files — parsed, and they corroborate the mixer's shape

`parse-frc.py` reads the 14 effects in `force\`. They are RIFF `FORC` containers
(Immersion's Force Resource layout): a DirectInput target GUID, then one or more
nested `efct` chunks each holding a type name and a parameter block.

**The finding, and it is certain because it is only the type names:** these
effects are **composed, not single primitives.**

| file | composition |
|---|---|
| `TIREBLWL` / `TIREBLWR` | `Sine1` + `ConstantForce1` + `Superimpose` |
| `MISSILE2` / `MISSILE5` | `Cosine1` + `ConstantForce1` + `Sequence` |
| `ENGSTART` | `SquareLow1` + `SquareHigh2` + `Sequence4` |
| `CANNON1..4` | `UserDefined1` (hand-drawn) |
| `EXPLOSN` | `SawtoothDown1` |
| `WPNCYCLE` / `WPNLINK` / `WPNUNLNK` | `RampDown1` / `SquareHigh1` |

A tyre blowout is a steady force with a sine **superimposed**. The 1997 authors
built feel by layering a constant force with an oscillation — which is exactly
`FfbMixer.ps1`'s model (`steady + texture*osc + transients`). That is independent
corroboration of the mixer's shape from the people who tuned this game for this
class of wheel.

**What is NOT decoded: the parameter block.** Peak magnitude and duration are
presumably in it (`100` = `0x64` and `±126` recur, suggesting percent) but the
fields are not pinned, so the tool prints them raw and claims no numbers.

Two mistakes in the first version of that parser, both recorded because they are
the same species as the `+0x08` matrix error:

1. **It invented an envelope.** It read six `(time, magnitude)` int32 pairs at
   `payload+20`. But the type name is *variable* length (`Cosine1` is 7 chars,
   `SawtoothDown1` is 13), so nothing after it sits at a fixed offset — and much
   of that region is `0xCD` fill, the MSVC debug heap's uninitialised pattern
   written straight to disk. It is not data. The tell was a reported magnitude of
   `842150451` = `0x32323233` = the ASCII text `"3222"`, in a field whose
   neighbours were all ≤ 126.
2. **Every file was listed twice.** `glob("*.FRC") + glob("*.frc")` doubles the
   list on Windows, where **glob is case-insensitive** — each pattern matches all
   14 files.

Not a runtime dependency: nothing in the interposer needs this, and since our
layer coexists with the game the engine still plays these itself.

## Files

| file | role |
|---|---|
| `FfbCore.ps1` | DirectInput output. Hand-walked COM vtables, compiled at runtime — no managed DirectInput offline, no C compiler here, so this needs nothing installed. |
| `Telemetry.ps1` | vehicle dynamics reader, tick-aware |
| `FfbMixer.ps1` | the force model |
| `ffb-interposer.ps1` | main loop, observability panel, logging |
| `ffb-calibrate.ps1` | measures yaw sign + steering lock |
| `ffb-mixer-test.ps1` | 28 assertions over synthetic drives |
| `ffb-coexist-test.ps1` | device-sharing measurement |
| `ffb-telemetry-probe.ps1` | offset discovery by behaviour |
