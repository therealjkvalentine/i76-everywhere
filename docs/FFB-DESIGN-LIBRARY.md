# Force feedback: a working reference

Everything needed to design forces for a wheel, a pad, a bass shaker or a motion
rig — distilled from primary sources, with the numbers that actually constrain
design. Written while building `tools/ffb/` for Interstate '76, so the worked
examples are from a 1997 game, but nothing here is specific to it.

Sources are listed at the end. Where a number is community practice rather than
a manufacturer or standards figure, it says so.

---

## 1. The one-page version

| Question | Answer |
|---|---|
| What does a wheel motor actually convey? | **DC–30 Hz.** Measured wheel output power sits in 0–5 Hz (force) and 25–30 Hz (vibrotactile). Nothing above ~110 Hz. |
| What's the force scale? | `DI_FFNOMINALMAX = 10000`, **linear**. 5000 is exactly half of 10000. |
| How fast must the loop run? | **60 Hz is professional-grade** (iRacing shipped on it for years). 111–333 Hz is the high end. You do not need 1 kHz. |
| Why does a wheel go light at the limit? | Self-aligning torque **peaks at 2–4° slip and falls to zero** as the tyre reaches max lateral force. The lightness *is* the warning. |
| Biggest mistake? | **Clipping.** Above the ceiling every force maps to the same output, so grip differences become invisible. |
| Second biggest? | Gaining up continuous channels. They **compete for the same actuator** — measured: raising FFB strength *decreased* 25–30 Hz vibrotactile power. |
| What belongs on a shaker instead? | 20–100 Hz content, strongest 30–50 Hz. Engine note, road texture, ABS buzz. A belt wheel cannot render it. |
| What does a motion rig want? | **Raw body-frame accelerations and angular rates.** Never pre-filtered — washout and tilt are the rig's job. |

---

## 2. DirectInput's effect model

The only Windows API for this. Everything is in **microseconds**, magnitudes are
**−10000…10000**, and gain is **0…10000**.

### Effect families

| Family | Struct | Notes |
|---|---|---|
| Constant | `DICONSTANTFORCE` | one magnitude. The workhorse. |
| Ramp | `DIRAMPFORCE` | start → end magnitude |
| Periodic | `DIPERIODIC` | Sine, Square, Triangle, SawtoothUp, SawtoothDown. `dwPhase` 0–35999 (hundredths of a degree), `dwPeriod` µs |
| Conditions | `DICONDITION` | spring / damper / inertia / friction |
| Custom | `DICUSTOMFORCE` | arbitrary sample buffer |

**Conditions are the interesting ones**, because the device computes them and
they respond to the user faster than any software loop can. They share one force
law and differ only in what `q` is measured from:

```
force = lPositiveCoefficient * (q - (lOffset + lDeadBand))     above the deadband
        (and the negative-coefficient mirror below it)

spring   q = axis POSITION
damper   q = axis VELOCITY
inertia  q = axis ACCELERATION
friction q = motion
```

A **negative coefficient inverts the effect** — a spring that pushes away from
the offset rather than pulling toward it. Most hardware does not apply envelopes
to conditions.

### Envelopes

`DIENVELOPE` gives attack and fade **relative to the baseline** (`lOffset` where
the type has one, else 0). The **sustain level is the type-specific magnitude**
and the **sustain time is `dwDuration`**. Attack and fade may each be above *or*
below sustain. The envelope is mirrored on the negative half of a waveform.

### Updating a running effect — the load-bearing detail

`IDirectInputEffect::SetParameters(peff, flags)` updates in place, and parameters
"take effect as if they were the parameters when the effect started" — so phase
and envelope continue smoothly, with no discontinuity.

> **Pass only `DIEP_TYPESPECIFICPARAMS` when rewriting a magnitude.**
>
> DirectInput's PID mapping emits one USB report per flag *group*. With only the
> type-specific flag it sends just the magnitude report. Add any other flag and it
> **also** sends the "basic" report on every update — doubling bus traffic and
> producing a documented loss of detail on some wheels under rapid updates. SDL
> shipped this bug (sending `DIRECTION|DURATION|ENVELOPE|STARTDELAY|TRIGGERBUTTON|
> TRIGGERREPEATINTERVAL` every time) and fixed it by dropping them, verified with
> Wireshark.

`DIEP_START` is a legitimate optimisation for *starting* (update+download+start in
one call, less data than a separate `Start()`), but adding it to a routine update
of an already-running infinite effect buys nothing and costs the extra report.

Other traps:
- **Shortening `dwDuration` below elapsed time stops the effect.**
- Unsupported parameters are **silently ignored, not an error**. Probe
  `DIEffectInfo.dwDynamicParams` for what can change while playing and
  `dwStaticParams` for what exists at all.
- Neither the axis count nor the axis list can change after creation.

### The canonical architecture

**One always-running, infinite-duration constant force whose magnitude is
rewritten every loop.** That is what racing titles do, and it is what
`tools/ffb/FfbCore.ps1` does. Vibration is synthesised by modulating that one
magnitude rather than by adding periodic effects — one primitive, one place
magnitude is decided, and the mixer stays additive.

### Device properties worth knowing

| Property | Use |
|---|---|
| `DIPROP_FFGAIN` | device-wide gain. **The only property changeable while acquired.** |
| `DIPROP_FFLOAD` | 0–100, % of device effect memory used. Needs exclusive. Your headroom gauge against `DIERR_DEVICEFULL`. |
| `DIPROP_AUTOCENTER` | must be set **unacquired**. Turn it **off** — the device's own spring otherwise fights your centering channel, invisibly. |
| `DIDEVCAPS.dwFFSamplePeriod` | minimum time between raw force commands (µs) |
| `DIDEVCAPS.dwFFMinTimeResolution` | the device's time quantum; it rounds your durations to this |

`SendForceFeedbackCommand(DISFFC_RESET)` **destroys all effects and disables the
actuators** — handles must be recreated. `DISFFC_STOPALL` merely stops playback
and keeps effects valid. Reach for the latter.

**FFB requires exclusive acquisition.** This is why a vendor control panel left
open, or a stray virtual joystick, breaks initialisation — both confirmed
first-hand in [WHEEL-T300.md](WHEEL-T300.md) and [FFB-LAPTOP-RECON.md](FFB-LAPTOP-RECON.md).

---

## 3. Force design theory

### Self-aligning torque is the signal

Steering torque ≈ `Fy × (pneumatic trail + mechanical trail) × cos(caster)`.

The number that governs everything: **self-aligning torque peaks at 2–4° of slip
and falls to zero as the tyre approaches maximum lateral force.** Lateral force
peaks *later* than SAT, because pneumatic trail collapses once the rear of the
contact patch starts sliding.

So a good FFB curve **rises, peaks, then falls** with slip. A force proportional
to lateral force — or worse, to steering angle — gets the limit exactly backwards:
it keeps getting heavier right up to the moment you've lost the front.

**The wheel going light is not a failure to convey something. It is the
conveyance.** It's the only pre-limit warning a driver gets.

### Clipping and headroom

Clipping means commanding more than the device can deliver: everything above the
ceiling maps to the same output, so differences up there stop existing. iRacing's
own wording is that excess strength causes "a loss of force feedback resolution."

Practitioner calibration: **normal cornering should use ~40–70% of range; only
kerbs and impacts should approach the ceiling.** Sustained cornering load that
clips is exactly what makes a wheel feel numb.

### The small-force floor

Belt and gear drives have static friction that swallows low-amplitude signal.
iRacing's `Min Force` exists for this, and its "linear mode" is recommended **for
direct drive only** — leaving it off boosts small forces, which is right for a
belt-driven wheel like the T300.

### Update rates in shipping sims

| Sim | FFB rate |
|---|---|
| iRacing | **60 Hz** native (physics 360 Hz; 360 Hz FFB added 2024 for direct drive) |
| Assetto Corsa | **333 Hz** (= physics tick; guidance to drop to 111 Hz for G25/G27) |
| ACC | **111 Hz** (one third of the 333 Hz physics tick) |

60 Hz carried iRacing's entire competitive history. **Getting the right shape in
the 0–30 Hz band and not clipping matters far more than loop rate.**

### Canned effects vs physics-derived

Modern sims essentially don't use DirectInput's condition and periodic effects.
Simucube's documentation calls them "non-physics based FFB effects" and notes
that mainly older titles used them; iRacing states outright that Periodic, Spring
and Damper are not used, and tells you to switch the wheel's own auto-centring
spring off because the game supplies centring.

The objection isn't aesthetic. **Synthetic rumble consumes headroom in the same
actuator that carries the grip signal.** Practitioner guidance keeps synthetic
road/texture content to roughly ≤20% of total output.

---

## 4. What hands can actually feel

| Channel | Band |
|---|---|
| Voluntary limb motion (what you can fight) | < 10 Hz |
| **Kinesthetic** perception — force, position, weight | **DC – ~30 Hz** |
| **Tactile** — vibration | ~0.4 Hz to >500 Hz, four receptor channels |
| Pacinian channel (the vibration workhorse) | ~40–500 Hz, **most sensitive 250–300 Hz** (detects ~10 nm at 250 Hz) |
| Percept boundary | ~60 Hz: "flutter" below, "vibratory hum" above |

**Force JND is 5–10% of the reference force.** That's your quantisation budget:
on a ~4 Nm base, steps finer than a few percent of current output are wasted.

### What a real sim wheel measures

A 2025 measurement study of sim racing wheels is the most directly applicable
data available:

- Output power lives in **two bands only: 0–5 Hz and 25–30 Hz**, the latter
  carrying **83–91% of vibrotactile power**.
- Harmonics at 50–55, 75–80, 100–105 Hz appear **only at 100% vibrotactile
  intensity**. **Nothing above ~110 Hz was detected.**
- **66–99% of motion power is medio-lateral** — in the plane of steering.
- Doubling vibrotactile intensity **quadrupled** 25–30 Hz power (exponential, not
  linear).
- **Raising FFB strength significantly *decreased* 25–30 Hz power.**

That last line is the important one. **The force channel and the vibration channel
compete for the same actuator.** "Keep continuous states low so transients read on
top" isn't a style preference — it's a consequence of a shared power budget.

The authors' own division of labour: **motor owns sub-5 Hz; a tactile transducer
owns 25–110 Hz.** The Pacinian sweet spot at 250 Hz is simply not reachable
through a belt-driven wheel.

---

## 5. Bass shakers

### Hardware

| Unit | Response | Resonance | Power |
|---|---|---|---|
| ButtKicker Gamer PLUS/PRO | 5–200 Hz | 9 Hz | 90–150 W RMS @ 2 Ω |
| Dayton BST-1 | 10–80 Hz | 30 Hz | 50 W @ 4 Ω |
| Aura AST-2B-4 | 20–80 Hz usable, best 30–40 Hz | 40 Hz | 50 W RMS @ 4 Ω |

Design for a usable band of **20–100 Hz with maximum output 30–50 Hz.**
ButtKicker's inertial-piston design genuinely reaches single digits; puck-style
shakers really don't.

### The two filters that aren't optional

- **High-pass ~22–25 Hz.** Infrasonic content causes large excursion for no
  perceptible benefit; ButtKicker warns it can damage the driver, and their amp
  has a fixed 25 Hz low-cut.
- **Low-pass 80–100 Hz.** Above that a shaker stops delivering tactile output and
  starts making audible mechanical buzz. Dayton says 80 Hz or under.

### Effect frequencies in practice

SimHub's ShakeIt is the de-facto standard: each effect maps a telemetry channel
through a response curve (threshold, gamma) to a 0–100% output, then synthesises
a tone whose pitch interpolates between a base and a high frequency. Published
practitioner tunings vary — there are two schools, one packing everything into
20–60 Hz where shakers are strongest, one spreading up to 180 Hz for separation:

| Effect | Typical range |
|---|---|
| Engine RPM | 20–55 Hz (background) |
| Road texture | 30–60 Hz |
| Kerbs | 35–90 Hz |
| Gear shift | 25–100 Hz (one short firm hit) |
| Impacts | 20–200 Hz wideband, or 30–45 Hz for a heavy strike |
| Wheel slip | 35–75 Hz |
| ABS / lockup | 20–90 Hz |

**The rules everyone agrees on** matter more than the exact numbers:
- **Space concurrent effects apart in frequency** or they mask each other.
- **No more than ~3 continuous effects per shaker.**
- Keep RPM/road as quiet background; transients are the accents.
- Use threshold/gamma so idle telemetry produces silence.
- **If everything feels equally strong, you're clipping.**

### Resonance is the number that matters, not the range

A tactile transducer is an inertial exciter: a moving mass on a spring. It puts out
the most force per watt **at its resonance (Fs)**, and falls away on both sides.
So the useful design target is not "somewhere in 20-100 Hz" but *centred on Fs*.

| Unit | Usable range | Fs |
|---|---|---|
| Aura AST-2B-4 (Pro) | 20-80 Hz | 40 Hz |
| Aura AST-1B-4 | 20-100 Hz | ~40 Hz |

**Below Fs, output collapses.** The mass and the frame start travelling together,
so relative motion - and therefore transmitted force - goes away. Driving 12 Hz
into a 40 Hz shaker mostly heats the voice coil.

**Reaching below the floor anyway.** Content genuinely below ~20 Hz (chassis heave,
pitch, slow body motion) is carried by **amplitude-modulating a carrier at Fs**.
Energy stays where the shaker is strong, the sidebands land at Fs +/- the
modulation rate (still in band), and the body feels the *rhythm* at the low rate.
This is standard tactile practice, not a compromise - the skin responds to the
envelope, and the envelope is the information.

**RPM → frequency:** the physically correct fundamental is firing frequency,
`RPM × cylinders / 120` — but that leaves the shaker band by mid-revs (a V8 at
4000 rpm is 267 Hz). Practice is to **compress idle→redline into ~25–55 Hz** and
let amplitude carry load.

**Vary it.** A steady unvarying tone numbs the skin and buries transients —
ShakeIt ships white-noise frequency randomisation specifically to de-monotonise
RPM. This is not comfort, it's information loss.

### Synthesise, don't tap the audio

For an old game especially: it has no LFE channel, its mix is full-range, and a
low-passed tap gives sparse rumble contaminated by music. SimXperience's SimVibe
is explicitly **"physics based, rather than audio based."** Telemetry knows things
the audio doesn't — exactly when a wheel is scrubbing, exactly how hard an impact
was.

---

## 6. Motion rigs

### The six axes and what they want

Translational **surge** (fore/aft), **sway** (lateral), **heave** (vertical);
rotational **roll**, **pitch**, **yaw**.

Motion software wants **local body-frame linear accelerations** for surge/sway/
heave, **angular velocities** for roll/pitch/yaw, plus **orientation angles** as a
separate slow channel for road slope and camber posing.

### Washout and tilt coordination — and why you send raw data

A rig has centimetres of travel to render multi-second accelerations. It exploits
a vestibular blind spot: the otoliths can't distinguish sustained linear
acceleration from a gravity component due to body tilt. So the cueing algorithm
splits each channel by frequency.

**Transients** are high-pass filtered and rendered as real platform translation —
the onset jolt when braking begins. The **washout** term then bleeds the actuator
back toward neutral below the perception threshold, recovering travel for the next
cue without the occupant noticing.

**Sustained content** goes through **tilt coordination**: the platform slowly
pitches (surge) or rolls (sway) so gravity substitutes, `β = sin⁻¹(f/g)`, with the
tilt *rate* held below the detection threshold — experimentally ~**3°/s**, with
production algorithms using 2–4°/s.

> **Therefore: send raw, unfiltered, unscaled body-frame accelerations and angular
> rates.** The filter time constants, tilt limits and travel scaling are functions
> of a specific rig's geometry, which the game cannot know. Pre-smoothing means the
> rig double-filters and kills the onset cues.

### Units and rates

The ecosystem is mixed — m/s² and g both common, radians and degrees both common —
so **emit SI, and declare the convention.** Don't clamp at the source; rig software
crops. Real telemetry spans roughly ±3 g with larger impact spikes.

**60 Hz is the de-facto baseline**, 30 Hz the practical floor. A rock-steady 60 Hz
stream beats an unstable 100 Hz one — iRacing's 60 Hz telemetry is the reference,
and there's a documented case of naively forcing 360 Hz making things *worse*.

---

## 7. The Thrustmaster T300RS specifically

| Spec | Value | Source |
|---|---|---|
| Motor | Brushless, 25 W | first-party |
| Drive | Dual-belt | first-party |
| Peak torque | ~3.9–4.5 Nm; iRacing's table says **4.4 Nm** | third-party — **Thrustmaster publishes no figure** |
| Position sensing | Hall effect, **16-bit / 65536 steps** | first-party |
| Rotation | 40°–1080°, default 900° | first-party |
| Internal FFB rate | **not published** | — |

**Effects supported** (first-party KB): **Constant, Periodic, Spring, Damper.**
Thrustmaster's own taxonomy splits these into *dynamic* effects (spring, damper —
computed in hardware from wheel position/velocity for response time) and *static*
(constant, periodic — driven entirely by game parameters).

Note what's **absent**: friction and inertia. Enumerate with `EnumEffects` and
check `DIEffectInfo.dwEffType` rather than assuming.

**Known traps:**
1. **The control panel holds the device exclusively.** Its own UI says to close it
   before starting a game. Confirmed here — leaving it open made the game's FFB
   init fail.
2. **Any other joystick in the enumeration can block exclusive acquisition.**
   Confirmed here (a 3Dconnexion emulator).
3. **Windows 11 GameInput Service** can intercept the wheel and kill FFB.
4. **Memory Integrity / Core Isolation** blocks older Thrustmaster drivers.
5. **Rotation range doesn't persist reliably** — games renegotiate it at launch,
   and changing panel settings while a game runs can kill FFB. Centring, by
   contrast, is stored in firmware.
6. **Thermal cut-back is documented** (KB 1744): sustained load makes FFB weaken
   and the base heat up. **A layer that holds a permanent non-zero constant force
   will meet this** — a reason to let the force fall to zero when parked rather
   than idling at a floor.

`REGDB_E_CLASSNOTREG` from `CreateEffect` is DirectInput's `DIERR_DEVICENOTREG`
("device not registered with DirectInput"). Community reports tie it to driver
version mismatch and the GameInput conflict; there's **no first-party
confirmation**, so treat those fixes as folklore.

---

## 8. Immersion I-FORCE — where a 1997 game's effects come from

I-FORCE was Immersion's force-feedback standard, licensed to Microsoft for the
SideWinder Force Feedback Pro. A 1997 title sits on the seam: authored in
Immersion's tooling, targeting DirectInput.

The era's vocabulary: **conditions** (spring, damper, inertia, friction);
**time-based** (periodic — square, sine, sawtooth up/down — plus constant and
ramp); and **positional** effects with no DirectInput equivalent (texture,
enclosure, ellipse, grid). Effects were *static* (authored offline, downloaded,
triggered) or *dynamic* (parameters rewritten during playback). Sequencing one
effect after another was proposed for DirectX 6, **not available in DirectX 5** —
so a 1997 title composites by starting several effects together.

Authoring produced an **IFR (Immersion Force Resource)** file. I76's `force/*.frc`
are RIFF containers with form type `FORC`, and `tools/ffb/parse-frc.py` decodes
enough to show the effects are **composed**: a tyre blowout is
`Sine + ConstantForce + Superimpose`; missiles are `Cosine + ConstantForce +
Sequence`. See [HANDLING-MODEL.md](HANDLING-MODEL.md) and `tools/ffb/README.md`.

**Device envelope of the era:** FF wheels made 3–4 lb sustained, peaking ~5 lb —
roughly the same class as a T300's ~4 Nm. The original magnitude choices are more
transferable than they look.

---

## 9. How this maps onto `tools/ffb/`

| Principle here | Where it lives |
|---|---|
| One infinite constant force, magnitude rewritten | `FfbCore.ps1` → `Ffb-Constant` |
| Only `DIEP_TYPESPECIFICPARAMS` on update | `FfbCore.ps1` |
| Auto-centre off, set unacquired | `FfbCore.ps1` → `Ffb-Open` |
| Oscillators ≤15 Hz (loop tops out ~62 Hz) | `FfbMixer.ps1` tunables |
| Losing the car makes the wheel go **light** | `FfbMixer.ps1` → `gripScale` |
| Continuous low, transients loud | the whole tune table |
| Device processing last | `Mix-Update` → `.Bus`, then per-device renderers |
| Shaker band + safety filters | `ffb-lfe.ps1` |
| Raw SI for motion rigs | `.Bus.Motion` |

The one place I76 departs from the canon: **it has no tyre model** (see
[HANDLING-MODEL.md](HANDLING-MODEL.md)), so the slip-angle curve in §3 has nothing
to read. The self-aligning-torque *principle* still governs — it just keys on
loss-of-control (spins, impacts, blown tyres) instead of slip angle.

---

## Sources

**DirectInput** — Microsoft Learn (DX9 archived reference): DIEFFECT,
`IDirectInputEffect::SetParameters`, Basic Concepts of Force Feedback, Conditions,
DICONDITION, DIPERIODIC, DIENVELOPE, DIEffectInfo, DIDEVCAPS, GetProperty, Device
Properties, SendForceFeedbackCommand, Using Force Feedback. Plus
[libsdl-org/SDL#12511](https://github.com/libsdl-org/SDL/issues/12511) for the
flag/USB-report finding.

**Force design** — [Self aligning torque (Wikipedia)](https://en.wikipedia.org/wiki/Self_aligning_torque);
iRacing support: Controller Setup and Calibration, Recommended settings for
Thrustmaster; [irFFB FAQ](https://github.com/nlp80/irFFB/wiki/FAQ);
[Simucube wheelbase effects](https://docs.simucube.com/TunerSoftware/wheelbases/wheelbaseeffects.html);
Kunos forum FFB frequency thread.

**Haptic perception** — [Decoding the Feeling: Vibration in Sim Racing Steering Wheel Haptic Feedback (PMC12694510)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12694510/);
Bolanowski et al. four-channel model; Morioka & Griffin vibration thresholds.

**Bass shakers** — ButtKicker product pages and FAQ; Dayton BST-1 and Aura AST-2B
spec sheets; [SimHub ShakeIt V3 configuration](https://github.com/SHWotever/SimHub/wiki/ShakeIt-V3-Effects-configuration);
SIMGASM, SimStaff and SimCoaches tuning guides; SimXperience SimVibe.

**Motion cueing** — [Motion simulator (Wikipedia)](https://en.wikipedia.org/wiki/Motion_simulator);
Groen & Bles tilt-rate threshold; DR Sim Manager telemetry-outputs spec;
motion4sim cueing docs; xsimulator SimTools profile FAQ.

**Thrustmaster** — support KB 107 (FFB settings), KB 1690 (rotation lock), KB 1744
(thermal cut-back); T300RS product page.

**Immersion** — Game Developer, "Cop A Feel…With Haptic Peripherals"; Immersion
TouchSense materials; Microsoft/Immersion joint development announcement, Feb 1998.
