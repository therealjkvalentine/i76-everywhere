# How Interstate '76 actually drives

Measured from the live process, not inferred. The engine's vehicle handling turns
out to be simple enough to state in one line, and knowing it explains several
things about how the game feels.

> **yaw rate = sign(steer) · min( (v / L)·tan(|steer|·lock),  a·|steer| / v )**
>
> `lock` = 0.76 rad (43.5°) · `a` = 31.0 m/s² (3.16 g) · `L` = 4.662 m
> crossover at `v = √(a·L)` = **12.0 m/s = 27 mph**

The yaw rate is whichever of two limits binds:

| regime | limit | behaviour |
|---|---|---|
| below 27 mph | **steering geometry** — `(v/L)·tan(δ)` | yaw rises with speed, like a real car manoeuvring |
| above 27 mph | **lateral-acceleration ceiling** — `a·steer/v` | yaw *falls* with speed; lateral g is constant |

## What the upper branch means

Multiply the second branch by speed:

```
lateral acceleration = yaw · v = a · steer
```

**Lateral g is directly proportional to steering input and independent of speed.**
Above 27 mph the engine treats the wheel as a *lateral-acceleration command*, not
a steering angle. Full lock gives 3.16 g at any speed.

That is a 1997 arcade simplification, and it is why the cars feel go-kart-like at
speed: you dial in cornering force directly, and the car never runs out of grip
because grip is not simulated. It also means:

- **There is no tyre model.** Understeer and oversteer in the sim-racing sense
  cannot occur. The car does exactly what it is asked, every frame.
- **There is no suspension model.** See below.
- Cornering load carries no information beyond steering position, because it *is*
  steering position.

## There is no suspension model either

The angular-velocity vector at `entity+0xc8` has the yaw rate in the middle
(`+0xcc`). The other two components were assumed to be roll and pitch rate. They
are not. Over 3407 samples of real driving:

| tested | correlation |
|---|---|
| `+0xc8` vs `d(longG)/dt` — pitch test | −0.03 |
| `+0xc8` vs `d(latG)/dt` — roll test | +0.02 |
| `+0xd0` vs `d(longG)/dt` — pitch test | +0.02 |
| `+0xd0` vs `d(latG)/dt` — roll test | +0.08 |

A car pitches under braking and rolls as cornering load changes, so a genuine roll
or pitch rate would track those derivatives. These track nothing. Both sit at
`p50 = 0.000` and `p90 ≈ 0.10` against yaw's `p90` of 1.25, and where they *do*
move, 77% of the time it coincides with a `jolt > 5`. Vertical velocity peaked at
0.77 m/s across 77 seconds.

**They are rotation imparted by impacts and by leaving the ground** — not
suspension travel. There is no body roll and no pitch. Anything wanting a
road-surface signal has to use the velocity-vector discontinuity (`jolt`) instead;
a channel keyed on these two is silent except when you crash.

## Units

Metres and m/s throughout. The four wheel contact points at `entity+0x04..0x30`
give a **wheelbase of 4.662 m and a track of 1.976 m** — a large American car,
which is what I'76 drives. Observed top speed 41.7 m/s = 93 mph.

## How this was found, and three wrong answers first

Worth recording, because each wrong answer looked correct at the time and the
failure mode is general.

**1. Median of per-sample ratios, single fixed lock → 5.8°.**
Rearranging a one-branch bicycle model gives `lock = atan(yaw·L/v)/steer` per
sample. Dividing by `steer` amplifies noise wherever steer is small, and
near-straight samples vastly outnumber hard-cornering ones — so the median sat in
the noise. Yaw also lags steer by a few tenths of a second, so mid-transition
samples fit a lock that is too small.

**2. Regression through the origin, single fixed lock → 6.2°.**
A better estimator behind the same wrong model. The estimator was blamed twice
before anyone plotted the implied lock against speed:

| speed | implied lock |
|---|---|
| 15–18 m/s | 30.0° |
| 21–24 | 14.5° |
| 27–30 | 9.4° |
| 33–36 | 6.4° |
| 39–42 | 4.7° |

A constant-lock model cannot describe the lateral-g branch, so the fit lands
wherever the drive spent its time. That drive was 80–93 mph almost throughout.

**3. Lateral-g branch alone → R² = 0.9997.**
This looked like the answer, and it was half of one. That drive lay entirely above
the crossover, so the model was validated on data covering only the regime it
described. On the next drive — which included low speed — it produced **158 false
understeer samples**, because below 27 mph the car really does turn less than
`a·steer/v` predicts.

Fitting a lock *and* an understeer gradient jointly is worse still: from
high-speed data they are not separately identifiable, and a grid search runs R²
monotonically up to 0.99 while the lock diverges to 129°, where `tan()` goes
negative and the predictions invert.

**The general lesson:** a high R² proves nothing if the data covers only part of
the model's domain, and synthetic tests generated from the same assumption as the
code cannot catch a wrong assumption. `tools/ffb/ffb-calibrate.ps1` now refuses to
fit unless a drive has ≥30 usable samples on *both* sides of the crossover, and
`tools/ffb/ffb-calib-test.ps1` asserts that single-regime drives are rejected
however good their R² looks.

## Reading it out of a live process

```
world  = [0x54a264]
entity = [[world] + 0x70]

  entity+0x04..0x30 : four float3 wheel contact points, LOCAL space
  entity+0xac       : speed = |velocity|
  entity+0xbc       : velocity float3, world space
  entity+0xc8       : angular velocity float3 — YAW RATE at +0xcc
  entity+0xd4       : acceleration / accumulated force float3
  entity+0xe0       : steer applied, -1..1
  entity+0xe4       : throttle applied, -1..1 (negative = brake)
  entity+0x80..0x8c : LOOP TEMPORARY — looks like telemetry, is not
```

Full provenance and the corrections this forced to
[MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md) Tier 2 are recorded there. Two are worth
repeating: `+0x08` is **not** a rotation matrix (it is the wheel contact points, and
that error is why position was never found — the search was for something adjacent
to a matrix that does not exist), and velocity was listed as unfound.

The sim runs a **fixed 20 Hz timestep**, so poll faster than that and derivatives
come out as `0, 0, spike` — an artefact of sampling faster than the simulation, not
noise you can filter.

## Consumers

- `tools/ffb/Telemetry.ps1` — implements the model as the reference the force
  feedback compares against
- `tools/ffb/ffb-calibrate.ps1` — fits `a` and `lock` from a drive
- `tools/ffb/README.md` — how the force model uses it

Because there is no tyre model, deviation from this reference is not slip — it is
**loss of control**: spins, impacts and blown tyres. On a real drive 44 samples
deviated by more than 0.5 rad/s and every one was a spin or a hit. That turns out
to be the more useful signal in this game anyway.
